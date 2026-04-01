import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
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
    # REVENUE TREND (DAILY)
    # =========================
    revenue_qs = (
        Sale.objects
        .filter(company=company, created_at__gte=last_30_days)
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
    sales_qs = (
        Sale.objects
        .filter(company=company, created_at__gte=last_30_days)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    sales_count_values = [item["count"] for item in sales_qs]

    # =========================
    # TOP PRODUCTS
    # =========================
    top_products = (
        SaleItem.objects
        .filter(sale__company=company)
        .values("product__name")
        .annotate(
            total_qty=Sum("quantity"),
            total_revenue=Sum("total_price")
        )
        .order_by("-total_qty")[:5]
    )

    # =========================
    # RECENT SALES (FIXED)
    # =========================
    recent_sales = (
        SaleItem.objects
        .filter(sale__company=company)
        .select_related("product", "sale")
        .order_by("-sale__created_at")[:10]
    )

    # =========================
    # BASIC METRICS
    # =========================
    total_revenue = (
        Sale.objects.filter(company=company)
        .aggregate(total=Sum("total_amount"))["total"] or 0
    )

    total_sales = Sale.objects.filter(company=company).count()

    total_products = Product.objects.filter(company=company).count()

    low_stock = Product.objects.filter(
        company=company,
        quantity__lte=5
    ).count()

    sales_last_30_days = (
        Sale.objects
        .filter(company=company, created_at__gte=last_30_days)
        .aggregate(total=Sum("total_amount"))["total"] or 0
    )

    # =========================
    # CONTEXT (JSON SAFE)
    # =========================
    return render(request, "dashboard.html", {

        # Metrics
        "total_revenue": total_revenue,
        "total_sales": total_sales,
        "total_products": total_products,
        "low_stock": low_stock,
        "sales_last_30_days": sales_last_30_days,

        # Charts (FIXED)
        "sales_dates": json.dumps(sales_dates),
        "sales_values": json.dumps(sales_values),
        "sales_count_values": json.dumps(sales_count_values),

        # Tables
        "top_products": top_products,
        "recent_sales": recent_sales,
    })