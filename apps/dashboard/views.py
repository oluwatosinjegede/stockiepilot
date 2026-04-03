# apps/dashboard/views.py

import json
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value, Exists, OuterRef
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from django.utils.timezone import now, timedelta

from apps.sales.models import Sale, SaleItem
from apps.products.models import Product

logger = logging.getLogger(__name__)

DECIMAL_ZERO = Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))


@login_required
def dashboard(request):
    company = getattr(request.user, "company", None)
    if not company:
        return redirect("login")

    try:
        # =========================
        # DATE RANGE FILTER
        # =========================
        days = int(request.GET.get("range", 30))
        date_from = now() - timedelta(days=days)

        # =========================
        # BASE QUERYSETS
        # =========================
        sales_qs = Sale.objects.filter(company=company)
        sales_items_qs = SaleItem.objects.filter(
            sale__company=company
        ).select_related("product", "sale")

        # =========================
        # COST EXPRESSION
        # =========================
        cost_expr = ExpressionWrapper(
            F("quantity") * Coalesce(F("product__cost_price"), DECIMAL_ZERO),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )

        # =========================
        # TOTALS
        # =========================
        total_revenue = sales_qs.aggregate(
            total=Coalesce(Sum("total_amount"), DECIMAL_ZERO)
        )["total"]

        total_cost = sales_items_qs.aggregate(
            total=Coalesce(Sum(cost_expr), DECIMAL_ZERO)
        )["total"]

        profit = total_revenue - total_cost

        # =========================
        # DAILY REVENUE TREND
        # =========================
        revenue_qs = (
            sales_qs
            .filter(created_at__gte=date_from)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))
            .order_by("date")
        )

        sales_dates = [str(i["date"]) for i in revenue_qs]
        sales_values = [float(i["total"]) for i in revenue_qs]

        # =========================
        # AI FORECAST (LINEAR)
        # =========================
        forecast_days = 7
        forecast_dates, forecast_values = [], []

        if len(sales_values) >= 2:
            n = len(sales_values)

        if n >= 2:
            x = list(range(n))
            y = sales_values

            x_mean = sum(x) / n
            y_mean = sum(y) / n

            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            m = numerator / denominator if denominator != 0 else 0
            c = y_mean - m * x_mean

            forecast_values = [
                max(0, m * i + c)
                for i in range(n, n + forecast_days)
            ]

            future_x = np.arange(len(y), len(y) + forecast_days)
            forecast_values = [max(0, float(m * i + c)) for i in future_x]

            last_date = revenue_qs.last()["date"] if revenue_qs.exists() else now().date()

            forecast_dates = [
                str(last_date + timedelta(days=i + 1))
                for i in range(forecast_days)
            ]

        # =========================
        # PROFIT TREND
        # =========================
        profit_qs = (
            sales_items_qs
            .filter(sale__created_at__gte=date_from)
            .annotate(date=TruncDate("sale__created_at"))
            .values("date")
            .annotate(
                revenue=Coalesce(Sum("total_price"), DECIMAL_ZERO),
                cost=Coalesce(Sum(cost_expr), DECIMAL_ZERO),
            )
            .order_by("date")
        )

        profit_dates = [str(i["date"]) for i in profit_qs]
        profit_values = [float(i["revenue"] - i["cost"]) for i in profit_qs]

        # =========================
        # MONTHLY TREND
        # =========================
        monthly_trend = (
            sales_qs
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))
            .order_by("month")
        )

        monthly_labels = [str(i["month"]) for i in monthly_trend]
        monthly_values = [float(i["total"]) for i in monthly_trend]

        # =========================
        # MONTHLY GROWTH
        # =========================
        current_month = now().replace(day=1)
        previous_month = (current_month - timedelta(days=1)).replace(day=1)

        current_month_revenue = sales_qs.filter(
            created_at__gte=current_month
        ).aggregate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))["total"]

        previous_month_revenue = sales_qs.filter(
            created_at__gte=previous_month,
            created_at__lt=current_month
        ).aggregate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))["total"]

        growth_rate = (
            float((current_month_revenue - previous_month_revenue) / previous_month_revenue * 100)
            if previous_month_revenue > 0 else 0.0
        )

        # =========================
        # INVENTORY VALUE
        # =========================
        inventory_value = Product.objects.filter(company=company).aggregate(
            total=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("quantity") * Coalesce(F("cost_price"), DECIMAL_ZERO),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ),
                DECIMAL_ZERO
            )
        )["total"]

        # =========================
        # DEAD STOCK (OPTIMIZED)
        # =========================
        sold_subquery = SaleItem.objects.filter(
            product=OuterRef("pk"),
            sale__company=company
        )

        dead_stock_count = Product.objects.filter(
            company=company
        ).annotate(
            has_sales=Exists(sold_subquery)
        ).filter(
            has_sales=False
        ).count()

        # =========================
        # LOW STOCK
        # =========================
        low_stock = Product.objects.filter(
            company=company,
            quantity__lte=5
        ).count()

        # =========================
        # TOP PRODUCTS
        # =========================
        top_products = (
            sales_items_qs
            .values("product__name")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), 0),
                total_revenue=Coalesce(Sum("total_price"), DECIMAL_ZERO)
            )
            .order_by("-total_qty")[:5]
        )

        # =========================
        # ALERT ENGINE
        # =========================
        alerts = []

        if profit < 0:
            alerts.append("⚠️ Business is running at a LOSS")

        if growth_rate < 0:
            alerts.append("📉 Revenue dropped vs last month")

        if dead_stock_count > 0:
            alerts.append(f"🧊 {dead_stock_count} dead stock products")

        if inventory_value > total_revenue:
            alerts.append("💰 Too much capital tied in inventory")

        if low_stock > 0:
            alerts.append(f"📦 {low_stock} products low on stock")

        if not sales_qs.exists():
            alerts.append("🚫 No sales recorded yet")

        # =========================
        # FINAL RESPONSE
        # =========================
        context = {
            "total_revenue": float(total_revenue),
            "total_cost": float(total_cost),
            "profit": float(profit),
            "inventory_value": float(inventory_value),

            "growth_rate": growth_rate,
            "alerts": alerts,

            "sales_dates": json.dumps(sales_dates or []),
            "sales_values": json.dumps(sales_values or []),

            "forecast_dates": json.dumps(forecast_dates),
            "forecast_values": json.dumps(forecast_values),

            "profit_dates": json.dumps(profit_dates or []),
            "profit_values": json.dumps(profit_values or []),

            "monthly_labels": json.dumps(monthly_labels or []),
            "monthly_values": json.dumps(monthly_values or []),

            "dead_stock_count": dead_stock_count,
            "top_products": top_products,
        }

        return render(request, "dashboard.html", context)

    except Exception as e:
        logger.exception("Dashboard Error")
        return render(request, "dashboard.html", {
            "error": "Dashboard failed to load. Contact admin."
        })