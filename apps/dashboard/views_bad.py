# apps/dashboard/views.py

import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from django.utils.timezone import now, timedelta

from apps.sales.models import Sale, SaleItem
from apps.products.models import Product


DECIMAL_ZERO = Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))


@login_required
def dashboard(request):
    try:
        company = getattr(request.user, "company", None)
        if not company:
            return redirect("login")

        last_30_days = now() - timedelta(days=30)

        sales_qs = Sale.objects.filter(company=company)

        sales_items_qs = SaleItem.objects.filter(
            sale__company=company
        ).select_related("product", "sale")

        # =========================
        # COST CALCULATION (FIXED)
        # =========================
        cost_expr = ExpressionWrapper(
            F("quantity") * Coalesce(F("product__cost_price"), DECIMAL_ZERO),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )

        # =========================
        # TOTALS (FIXED)
        # =========================
        total_revenue = sales_qs.aggregate(
            total=Coalesce(Sum("total_amount"), DECIMAL_ZERO)
        )["total"]

        total_cost = sales_items_qs.aggregate(
            total=Coalesce(Sum(cost_expr), DECIMAL_ZERO)
        )["total"]

        profit = total_revenue - total_cost

        # =========================
        # DAILY TREND (FIXED)
        # =========================
        revenue_qs = (
            sales_qs
            .filter(created_at__gte=last_30_days)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))
            .order_by("date")
        )

        sales_dates = [str(i["date"]) for i in revenue_qs]
        sales_values = [float(i["total"]) for i in revenue_qs]

        # =========================
        # MONTHLY COMPARISON (FIXED)
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

        if previous_month_revenue > 0:
            growth_rate = float(
                (current_month_revenue - previous_month_revenue)
                / previous_month_revenue * 100
            )
        else:
            growth_rate = 0.0

        # =========================
        # MONTHLY TREND (FIXED)
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
        # TOP PRODUCTS (FIXED)
        # =========================
        top_products = (
            sales_items_qs
            .values("product__id", "product__name")
            .annotate(
                total_qty=Coalesce(Sum("quantity"), 0),  # int safe
                total_revenue=Coalesce(Sum("total_price"), DECIMAL_ZERO)
            )
            .order_by("-total_qty")[:5]
        )

        # =========================
        # RECENT SALES
        # =========================
        recent_sales = sales_items_qs.order_by("-sale__created_at")[:10]

        # =========================
        # METRICS
        # =========================
        total_sales = sales_qs.count()

        low_stock = Product.objects.filter(
            company=company,
            quantity__lte=5
        ).count()

        # =========================
        # ALERTS
        # =========================
        alerts = []

        if low_stock > 0:
            alerts.append(f"{low_stock} products are low on stock")

        if current_month_revenue < previous_month_revenue:
            alerts.append("Revenue dropped compared to last month")

        if profit < 0:
            alerts.append("You are running at a loss")

        if total_sales == 0:
            alerts.append("No sales recorded yet")

        # =========================
        # PIE DATA
        # =========================
        pie_labels = ["Revenue", "Cost", "Profit"]
        pie_values = [
            float(total_revenue),
            float(total_cost),
            float(profit)
        ]

        return render(request, "dashboard.html", {
            "total_revenue": float(total_revenue),
            "total_cost": float(total_cost),
            "profit": float(profit),
            "total_sales": float(total_sales),

            "current_month_revenue": current_month_revenue,
            "previous_month_revenue": previous_month_revenue,
            "growth_rate": float(growth_rate),

            "alerts": alerts,

            "sales_dates": json.dumps(sales_dates),
            "sales_values": json.dumps(sales_values),

            "monthly_labels": json.dumps(monthly_labels),
            "monthly_values": json.dumps(monthly_values),

            "pie_labels": json.dumps(pie_labels),
            "pie_values": json.dumps(pie_values),

            "top_products": top_products,
            "recent_sales": recent_sales,
        })

    except Exception as e:
        return render(request, "dashboard.html", {
            "error": str(e)
        })