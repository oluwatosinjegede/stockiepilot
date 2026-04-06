# apps/products/models.py

from django.db import models
from apps.companies.models import Company


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='products'
    )

    name = models.CharField(max_length=255)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products"
    )

    description = models.TextField(blank=True)

    quantity = models.PositiveIntegerField(default=0)

    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)

    # FIX: Remove global uniqueness
    sku = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        # UNIQUE PER COMPANY
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_product_per_company"
            ),
            models.UniqueConstraint(
                fields=["company", "sku"],
                name="unique_sku_per_company"
            ),
        ]

        # PERFORMANCE INDEXES
        indexes = [
            models.Index(fields=["company", "name"]),
            models.Index(fields=["company", "sku"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.company})"