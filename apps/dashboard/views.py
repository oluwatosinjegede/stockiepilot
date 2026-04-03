import json

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import (
    Sum, Count, F, DecimalField, ExpressionWrapper
)
from django.db.models.functions import TruncDate, Coalesce
from django.core.serializers.json import DjangoJSONEncoder
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

    recent_sales_qs = sales_qs.filter(created_at__gte=last_30_days)

    sales_items_qs = (
        SaleItem.objects
        .filter(sale__company=company)
        .select_related("product", "sale")
        .only(
            "id",
            "quantity",
            "total_price",
            "product__id",
            "product__name",
            "product__cost_price",
            "sale__created_at"
        )
    )

    # =========================
    # COST EXPRESSION (DB LEVEL)
    # =========================
    cost_expression = ExpressionWrapper(
        F("quantity") * F("product__cost_price"),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    # =========================
    # REVENUE TREND (DAILY)
    # =========================
    revenue_qs = (
        recent_sales_qs
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Coalesce(Sum("total_amount"), 0))
        .order_by("date")
    )

    sales_dates = [str(item["date"]) for item in revenue_qs]
    sales_values = [float(item["total"]) for item in revenue_qs]

    # =========================
    # SALES COUNT TREND
    # =========================
    sales_count_qs = (
        recent_sales_qs
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )

    sales_count_values = [item["count"] for item in sales_count_qs]

    # =========================
    # PROFIT TREND (ADVANCED)
    # =========================
    profit_qs = (
        sales_items_qs
        .filter(sale__created_at__gte=last_30_days)
        .annotate(date=TruncDate("sale__created_at"))
        .values("date")
        .annotate(
            revenue=Coalesce(Sum("total_price"), 0),
            cost=Coalesce(Sum(cost_expression), 0),
        )
        .annotate(
            profit=F("revenue") - F("cost")
        )
        .order_by("date")
    )

    profit_values = [float(item["profit"]) for item in profit_qs]

    # =========================
    # TOTALS (REVENUE / COST / PROFIT)
    # =========================
    total_revenue = sales_qs.aggregate(
        total=Coalesce(Sum("total_amount"), 0)
    )["total"]

    total_cost = sales_items_qs.aggregate(
        total=Coalesce(Sum(cost_expression), 0)
    )["total"]

    profit = total_revenue - total_cost

    # Prevent negative pie distortion
    safe_profit = max(0, float(profit))

    # =========================
    # PIE CHART DATA
    # =========================
    pie_labels = ["Revenue", "Cost", "Profit"]
    pie_values = [
        float(total_revenue),
        float(total_cost),
        safe_profit
    ]

    # =========================
    # TOP PRODUCTS
    # =========================
    top_products = (
        sales_items_qs
        .values("product__id", "product__name")
        .annotate(
            total_qty=Coalesce(Sum("quantity"), 0),
            total_revenue=Coalesce(Sum("total_price"), 0)
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

    sales_last_30_days = recent_sales_qs.aggregate(
        total=Coalesce(Sum("total_amount"), 0)
    )["total"]

    # =========================
    # RESPONSE
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

        # Charts
        "sales_dates": json.dumps(sales_dates, cls=DjangoJSONEncoder),
        "sales_values": json.dumps(sales_values, cls=DjangoJSONEncoder),
        "sales_count_values": json.dumps(sales_count_values, cls=DjangoJSONEncoder),
        "profit_values": json.dumps(profit_values, cls=DjangoJSONEncoder),

        # Pie
        "pie_labels": json.dumps(pie_labels, cls=DjangoJSONEncoder),
        "pie_values": json.dumps(pie_values, cls=DjangoJSONEncoder),

        # Tables
        "top_products": top_products,
        "recent_sales": recent_sales,
    })