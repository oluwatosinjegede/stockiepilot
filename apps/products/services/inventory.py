# apps/products/services/inventory.py

from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Sum
from apps.sales.models import SaleItem


def calculate_inventory_metrics(products, company):

    last_30_days = now() - timedelta(days=30)

    alerts = []

    for product in products:

        sales = (
            SaleItem.objects
            .filter(
                product=product,
                sale__company=company,
                sale__created_at__gte=last_30_days
            )
            .aggregate(total=Sum("quantity"))["total"] or 0
        )

        velocity = sales / 30 if sales else 0

        if product.quantity <= 5:
            alerts.append(f"⚠️ Low stock: {product.name}")

        if sales == 0 and product.quantity > 0:
            alerts.append(f"🧊 Dead stock: {product.name}")

        if velocity > 5:
            alerts.append(f"🔥 Fast selling: {product.name}")

    return alerts