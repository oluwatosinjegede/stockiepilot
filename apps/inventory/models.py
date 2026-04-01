# apps/inventory/models.py

from django.db import models


class Inventory(models.Model):
    product = models.OneToOneField(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='inventory'
    )

    quantity_in_stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)

    last_restocked_date = models.DateTimeField(null=True, blank=True)

    def is_low_stock(self):
        return self.quantity_in_stock <= self.low_stock_threshold

    def __str__(self):
        return f"{self.product.name} Stock: {self.quantity_in_stock}"