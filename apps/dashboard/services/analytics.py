import json
from collections import defaultdict
from statistics import mean

from django.db.models import DecimalField, Exists, ExpressionWrapper, F, OuterRef, Sum, Value
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils.timezone import now, timedelta

from apps.products.models import Product
from apps.sales.models import SaleItem

DECIMAL_ZERO = Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))


def _safe_float(value):
    return float(value or 0)


def _build_revenue_projection(sales_dates, sales_values, horizon_days=7):
    """
    Lightweight predictive projection that combines:
    - recent weighted moving average (short-term signal)
    - linear trend slope (direction signal)
    """
    if len(sales_values) < 3:
        return {
            "dates": [],
            "values": [],
            "confidence": 0,
            "scenario_floor": [],
            "scenario_ceiling": [],
        }

    lookback = min(10, len(sales_values))
    recent = sales_values[-lookback:]
    weight_total = sum(range(1, lookback + 1))
    wma = sum(value * weight for value, weight in zip(recent, range(1, lookback + 1))) / weight_total

    x = list(range(len(sales_values)))
    x_mean = mean(x)
    y_mean = mean(sales_values)
    denominator = sum((xi - x_mean) ** 2 for xi in x)
    slope = (
        sum((x[i] - x_mean) * (sales_values[i] - y_mean) for i in range(len(sales_values))) / denominator
        if denominator
        else 0
    )

    baseline = max(0, (wma * 0.7) + (sales_values[-1] * 0.3))
    forecast_values = [max(0, baseline + (slope * day)) for day in range(1, horizon_days + 1)]

    variation = [abs(sales_values[i] - sales_values[i - 1]) for i in range(1, len(sales_values))]
    volatility = (mean(variation) / y_mean) if y_mean else 0
    confidence = max(15, min(95, round((1 - min(volatility, 1.5)) * 100)))

    last_date = sales_dates[-1] if sales_dates else now().date()
    forecast_dates = [str(last_date + timedelta(days=index)) for index in range(1, horizon_days + 1)]

    spread = max(0.08, min(0.35, volatility if volatility else 0.12))
    floor = [round(max(0, value * (1 - spread)), 2) for value in forecast_values]
    ceiling = [round(value * (1 + spread), 2) for value in forecast_values]

    return {
        "dates": forecast_dates,
        "values": [round(value, 2) for value in forecast_values],
        "confidence": confidence,
        "scenario_floor": floor,
        "scenario_ceiling": ceiling,
    }


def build_dashboard_context(company, days=30):
    date_from = now() - timedelta(days=days)

    sales_qs = company.sales.all()
    sales_items_qs = SaleItem.objects.filter(sale__company=company).select_related("product", "sale")

    cost_expr = ExpressionWrapper(
        F("quantity") * Coalesce(F("product__cost_price"), DECIMAL_ZERO),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    total_revenue = sales_qs.aggregate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))["total"]
    total_cost = sales_items_qs.aggregate(total=Coalesce(Sum(cost_expr), DECIMAL_ZERO))["total"]
    profit = total_revenue - total_cost

    revenue_qs = (
        sales_qs.filter(created_at__gte=date_from)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))
        .order_by("date")
    )

    revenue_map = {item["date"]: _safe_float(item["total"]) for item in revenue_qs}
    sales_dates = list(revenue_map.keys())
    sales_values = list(revenue_map.values())

    projection = _build_revenue_projection(sales_dates, sales_values)

    profit_qs = (
        sales_items_qs.filter(sale__created_at__gte=date_from)
        .annotate(date=TruncDate("sale__created_at"))
        .values("date")
        .annotate(revenue=Coalesce(Sum("total_price"), DECIMAL_ZERO), cost=Coalesce(Sum(cost_expr), DECIMAL_ZERO))
        .order_by("date")
    )

    profit_dates = [str(item["date"]) for item in profit_qs]
    profit_values = [_safe_float(item["revenue"] - item["cost"]) for item in profit_qs]

    monthly_trend = (
        sales_qs.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Coalesce(Sum("total_amount"), DECIMAL_ZERO))
        .order_by("month")
    )
    monthly_labels = [item["month"].strftime("%b %Y") for item in monthly_trend if item["month"]]
    monthly_values = [_safe_float(item["total"]) for item in monthly_trend]

    current_month = now().replace(day=1)
    previous_month = (current_month - timedelta(days=1)).replace(day=1)

    current_month_revenue = sales_qs.filter(created_at__gte=current_month).aggregate(
        total=Coalesce(Sum("total_amount"), DECIMAL_ZERO)
    )["total"]
    previous_month_revenue = sales_qs.filter(created_at__gte=previous_month, created_at__lt=current_month).aggregate(
        total=Coalesce(Sum("total_amount"), DECIMAL_ZERO)
    )["total"]

    growth_rate = (
        _safe_float((current_month_revenue - previous_month_revenue) / previous_month_revenue * 100)
        if previous_month_revenue > 0
        else 0.0
    )

    inventory_value = Product.objects.filter(company=company).aggregate(
        total=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("quantity") * Coalesce(F("cost_price"), DECIMAL_ZERO),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                )
            ),
            DECIMAL_ZERO,
        )
    )["total"]

    sold_subquery = SaleItem.objects.filter(product=OuterRef("pk"), sale__company=company)
    dead_stock_count = Product.objects.filter(company=company).annotate(has_sales=Exists(sold_subquery)).filter(
        has_sales=False
    ).count()
    low_stock = Product.objects.filter(company=company, quantity__lte=5).count()
    out_of_stock = Product.objects.filter(company=company, quantity=0).count()
    total_products = Product.objects.filter(company=company).count()

    top_products = (
        sales_items_qs.values("product__name")
        .annotate(total_qty=Coalesce(Sum("quantity"), 0), total_revenue=Coalesce(Sum("total_price"), DECIMAL_ZERO))
        .order_by("-total_revenue")[:5]
    )

    weekday_totals = defaultdict(float)
    for item in revenue_qs:
        weekday_totals[item["date"].strftime("%A")] += _safe_float(item["total"])

    peak_sales_day = max(weekday_totals.items(), key=lambda x: x[1])[0] if weekday_totals else "N/A"

    inventory_segments = {
        "In Stock": max(total_products - low_stock, 0),
        "Low Stock": low_stock,
        "Out of Stock": out_of_stock,
    }

    top_products_list = list(top_products)

    alerts = []
    if profit < 0:
        alerts.append("Business is currently operating at a loss.")
    if growth_rate < 0:
        alerts.append("Revenue decreased compared to last month.")
    if dead_stock_count > 0:
        alerts.append(f"{dead_stock_count} products have not sold yet.")
    if inventory_value > total_revenue:
        alerts.append("Inventory value is higher than total revenue — cashflow risk detected.")
    if low_stock > 0:
        alerts.append(f"{low_stock} products are low on stock.")
    if not sales_qs.exists():
        alerts.append("No sales recorded yet. Start with promotional campaigns and bundle offers.")

    ai_insights = [
        f"AI signal: Forecast confidence is {projection['confidence']}% for the next 7 days.",
        f"AI signal: Peak revenue contribution usually happens on {peak_sales_day}.",
        f"AI signal: Expected 7-day revenue ≈ ₦{sum(projection['values']):,.2f} (base case).",
    ]

    return {
        "total_revenue": _safe_float(total_revenue),
        "total_cost": _safe_float(total_cost),
        "profit": _safe_float(profit),
        "inventory_value": _safe_float(inventory_value),
        "growth_rate": growth_rate,
        "alerts": alerts,
        "ai_insights": ai_insights,
        "prediction_confidence": projection["confidence"],
        "sales_dates": json.dumps([str(day) for day in sales_dates]),
        "sales_values": json.dumps(sales_values),
        "forecast_dates": json.dumps(projection["dates"]),
        "forecast_values": json.dumps(projection["values"]),
        "forecast_floor": json.dumps(projection["scenario_floor"]),
        "forecast_ceiling": json.dumps(projection["scenario_ceiling"]),
        "profit_dates": json.dumps(profit_dates),
        "profit_values": json.dumps(profit_values),
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_values": json.dumps(monthly_values),
        "dead_stock_count": dead_stock_count,
        "low_stock_count": low_stock,
        "out_of_stock_count": out_of_stock,
        "total_products": total_products,
        "top_products": top_products_list,
        "top_product_labels": json.dumps([item["product__name"] for item in top_products_list]),
        "top_product_revenue": json.dumps([_safe_float(item["total_revenue"]) for item in top_products_list]),
        "top_product_quantity": json.dumps([_safe_float(item["total_qty"]) for item in top_products_list]),
        "inventory_segment_labels": json.dumps(list(inventory_segments.keys())),
        "inventory_segment_values": json.dumps(list(inventory_segments.values())),
    }
