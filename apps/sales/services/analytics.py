import json
from datetime import timedelta

from django.db.models import Sum, F
from django.db.models.functions import TruncDate
from django.utils import timezone


def _to_float(value):
    return float(value or 0)


def build_sales_analytics(sales_items_qs):
    """Prepare chart-ready analytics and AI-style insights for the sales page."""
    today = timezone.now().date()
    last_30_start = today - timedelta(days=29)

    base_qs = sales_items_qs.filter(sale__created_at__date__gte=last_30_start)

    totals = base_qs.aggregate(
        revenue=Sum("total_price"),
        units=Sum("quantity"),
        est_cost=Sum(F("product__cost_price") * F("quantity")),
    )

    revenue = _to_float(totals["revenue"])
    units = int(totals["units"] or 0)
    est_cost = _to_float(totals["est_cost"])
    estimated_profit = revenue - est_cost
    average_order_value = (revenue / units) if units else 0

    by_day = (
        base_qs.annotate(day=TruncDate("sale__created_at"))
        .values("day")
        .annotate(revenue=Sum("total_price"), units=Sum("quantity"))
        .order_by("day")
    )

    chart_dates = [str(item["day"]) for item in by_day]
    chart_revenue = [_to_float(item["revenue"]) for item in by_day]

    top_products = (
        base_qs.values("product__name")
        .annotate(revenue=Sum("total_price"), units=Sum("quantity"))
        .order_by("-revenue")[:5]
    )
    product_labels = [item["product__name"] for item in top_products]
    product_values = [_to_float(item["revenue"]) for item in top_products]

    last_7_start = today - timedelta(days=6)
    last_14_start = today - timedelta(days=13)

    recent_7_revenue = _to_float(
        base_qs.filter(sale__created_at__date__gte=last_7_start).aggregate(total=Sum("total_price"))["total"]
    )
    prior_7_revenue = _to_float(
        base_qs.filter(
            sale__created_at__date__gte=last_14_start,
            sale__created_at__date__lt=last_7_start,
        ).aggregate(total=Sum("total_price"))["total"]
    )

    if prior_7_revenue > 0:
        trend_delta = ((recent_7_revenue - prior_7_revenue) / prior_7_revenue) * 100
    elif recent_7_revenue > 0:
        trend_delta = 100.0
    else:
        trend_delta = 0.0

    top_product_name = product_labels[0] if product_labels else "N/A"
    top_product_share = ((product_values[0] / revenue) * 100) if product_values and revenue else 0

    insights = [
        f"AI signal: Weekly revenue trend is {trend_delta:+.1f}% compared to the previous week.",
        f"AI signal: {top_product_name} contributes {top_product_share:.1f}% of 30-day revenue.",
        f"AI signal: Estimated gross margin is {(estimated_profit / revenue * 100) if revenue else 0:.1f}%.",
    ]

    return {
        "metrics": {
            "revenue_30d": revenue,
            "units_30d": units,
            "estimated_profit_30d": estimated_profit,
            "average_order_value": average_order_value,
        },
        "charts": {
            "dates": json.dumps(chart_dates),
            "revenue": json.dumps(chart_revenue),
            "product_labels": json.dumps(product_labels),
            "product_values": json.dumps(product_values),
            "pie_values": json.dumps([
                round(revenue, 2),
                round(est_cost, 2),
                round(estimated_profit, 2),
            ]),
        },
        "insights": insights,
    }
