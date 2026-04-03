import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate
from django.utils.timezone import now, timedelta

from apps.sales.models import Sale, SaleItem
from apps.products.models import Product


@login_required
def dashboard(request):
    company = getattr(request.user, "company", None)

    if not company:
        return redirect("login")

    # =========================
    # DATE RANGE
    # =========================
    last_30_days = now() - timedelta(days=30)

    # =========================
    # BASE QUERYSETS (REUSE)
    # =========================
    sales_qs = Sale.objects.filter(company=company)
    sales_items_qs = SaleItem.objects.filter(sale__company=company).select_related("product", "sale")

    # =========================
    # REVENUE TREND (DAILY)
    # =========================
    revenue_qs = (
        sales_qs
        .filter(created_at__gte=last_30_days)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Sum("total_amount"))
        .order_by("date")
    )

    sales_dates = [str(item["date"]) for item in revenue_qs]
    sales_values = [float(item["total"] or 0) for item in revenue_qs]

    # =========================
    # SALES COUNT TREND
    # =========================
    sales_count_qs = (
        sales_qs
        .filter(created_at__gte=last_30_days)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    sales_count_values = [item["count"] for item in sales_count_qs]

    # =========================
    # COST CALCULATION (DB LEVEL)
    # =========================
    cost_expression = ExpressionWrapper(
        F("quantity") * F("product__cost_price"),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    # =========================
    # TOTALS (REVENUE / COST / PROFIT)
    # =========================
    total_revenue = sales_qs.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    total_cost = sales_items_qs.aggregate(
        total=Sum(cost_expression)
    )["total"] or 0

    profit = total_revenue - total_cost

    # =========================
    # PIE CHART DATA
    # =========================
    pie_labels = ["Revenue", "Cost", "Profit"]
    pie_values = [
        float(total_revenue),
        float(total_cost),
        float(profit)
    ]

    # =========================
    # TOP PRODUCTS
    # =========================
    top_products = (
        sales_items_qs
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_revenue=Sum("total_price")
        )
        .order_by("-total_qty")[:5]
    )

    # =========================
    # RECENT SALES
    # =========================
    recent_sales = sales_items_qs.order_by("-sale__created_at")[:10]

    # =========================
    # BASIC METRICS
    # =========================
    total_sales = sales_qs.count()

    total_products = Product.objects.filter(company=company).count()

    low_stock = Product.objects.filter(
        company=company,
        quantity__lte=5
    ).count()

    sales_last_30_days = (
        sales_qs
        .filter(created_at__gte=last_30_days)
        .aggregate(total=Sum("total_amount"))["total"] or 0
    )

    # =========================
    # CONTEXT (JSON SAFE)
    # =========================
    return render(request, "dashboard.html", {

        # Metrics
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "profit": profit,
        "total_sales": total_sales,
        "total_products": total_products,
        "low_stock": low_stock,
        "sales_last_30_days": sales_last_30_days,

        # Line Charts
        "sales_dates": json.dumps(sales_dates),
        "sales_values": json.dumps(sales_values),
        "sales_count_values": json.dumps(sales_count_values),

        # Pie Chart
        "pie_labels": json.dumps(pie_labels),
        "pie_values": json.dumps(pie_values),

        # Tables
        "top_products": top_products,
        "recent_sales": recent_sales,
    })