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


class Supplier(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="unique_supplier_name_per_company"),
        ]
        indexes = [
            models.Index(fields=["company", "name"]),
            models.Index(fields=["company", "is_active"]),
        ]
    def __str__(self):
        return self.name

class Product(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    description = models.TextField(blank=True)
    quantity = models.PositiveIntegerField(default=0)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    sku = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name"], name="unique_product_per_company"),
            models.UniqueConstraint(fields=["company", "sku"], name="unique_sku_per_company"),
        ]
        indexes = [
            models.Index(fields=["company", "name"]),
            models.Index(fields=["company", "sku"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.company})"


class ProductSupply(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="product_supplies")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="supplies")
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplies",
    )
    date_supplied = models.DateField()
    supplier_invoice_number = models.CharField(max_length=120)
    quantity_supplied = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_product_supplies",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_supplied", "-id"]
        indexes = [
            models.Index(fields=["company", "date_supplied"]),
            models.Index(fields=["company", "supplier"]),
        ]

    def save(self, *args, **kwargs):
        self.total_cost = (self.quantity_supplied or 0) * (self.unit_cost or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} supply ({self.date_supplied})"