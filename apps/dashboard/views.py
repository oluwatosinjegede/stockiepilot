# apps/dashboard/views.py

import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, Coalesce
from django.utils.timezone import now, timedelta

from apps.sales.models import Sale, SaleItem
from apps.products.models import Product


@login_required
def dashboard(request):
    company = getattr(request.user, "company", None)

    if not company:
        return redirect("login")

    last_30_days = now() - timedelta(days=30)

    # =========================
    # BASE QUERYSETS
    # =========================
    sales_qs = Sale.objects.filter(company=company)

    sales_items_qs = SaleItem.objects.filter(
        sale__company=company
    ).select_related("product", "sale")

    # =========================
    # SAFE EXPRESSIONS
    # =========================
    revenue_expr = Coalesce(F("total_amount"), 0)

    cost_expr = ExpressionWrapper(
        F("quantity") * Coalesce(F("product__cost_price"), 0),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    item_total_expr = ExpressionWrapper(
        F("quantity") * Coalesce(F("price"), 0),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    # =========================
    # REVENUE TREND
    # =========================
    revenue_qs = (
        sales_qs
        .filter(created_at__gte=last_30_days)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Coalesce(Sum("total_amount"), 0))
        .order_by("date")
    )

    sales_dates = [str(i["date"]) for i in revenue_qs]
    sales_values = [float(i["total"]) for i in revenue_qs]

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

    sales_count_values = [i["count"] for i in sales_count_qs]

    # =========================
    # TOTALS
    # =========================
    total_revenue = sales_qs.aggregate(
        total=Coalesce(Sum("total_amount"), 0)
    )["total"]

    total_cost = sales_items_qs.aggregate(
        total=Coalesce(Sum(cost_expr), 0)
    )["total"]

    profit = total_revenue - total_cost

    # =========================
    # TOP PRODUCTS (Postgres-safe)
    # =========================
    top_products = (
        sales_items_qs
        .values("product__id", "product__name")
        .annotate(
            total_qty=Coalesce(Sum("quantity"), 0),
            total_revenue=Coalesce(Sum(item_total_expr), 0)
        )
        .order_by("-total_qty")[:5]
    )

    # =========================
    # RECENT SALES (with computed total)
    # =========================
    recent_sales = (
        sales_items_qs
        .annotate(total_price_calc=item_total_expr)
        .order_by("-sale__created_at")[:10]
    )

    # =========================
    # METRICS
    # =========================
    total_sales = sales_qs.count()

    total_products = Product.objects.filter(company=company).count()

    low_stock = Product.objects.filter(
        company=company,
        quantity__lte=5
    ).count()

    sales_last_30_days = sales_qs.filter(
        created_at__gte=last_30_days
    ).aggregate(
        total=Coalesce(Sum("total_amount"), 0)
    )["total"]

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

        # Metrics
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "profit": profit,
        "total_sales": total_sales,
        "total_products": total_products,
        "low_stock": low_stock,
        "sales_last_30_days": sales_last_30_days,

        # Charts
        "sales_dates": json.dumps(sales_dates),
        "sales_values": json.dumps(sales_values),
        "sales_count_values": json.dumps(sales_count_values),

        "pie_labels": json.dumps(pie_labels),
        "pie_values": json.dumps(pie_values),

        # Tables
        "top_products": top_products,
        "recent_sales": recent_sales,
    })