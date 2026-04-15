# apps/sales/models.py

from django.db import models
from apps.companies.models import Company
from apps.products.models import Product


# =========================
# SALE (HEADER)
# =========================

class Sale(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid in Full'),
        ('partial', 'Part Payment'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='sales'
    )

    products = models.ManyToManyField(
        Product,
        through="SaleItem",
        related_name="sales",
        blank=True,
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='paid'
    )

    customer_name = models.CharField(
        max_length=255,
        blank=True
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='completed'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def recalculate_totals(self):
        from django.db.models import Sum
        from decimal import Decimal

        total = self.items.aggregate(total=Sum("total_price"))["total"] or Decimal("0")
        self.total_amount = total

        if self.payment_status == "paid":
            self.amount_paid = total
            self.balance = Decimal("0")
        else:
            self.balance = max(total - Decimal(self.amount_paid or 0), Decimal("0"))

        self.status = "pending" if self.balance > 0 else "completed"


    def __str__(self):
        return f"{self.company.name} - ₦{self.total_amount}"


# =========================
# SALE ITEM (LINE ITEMS)
# =========================

class SaleItem(models.Model):

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "product"],
                name="unique_product_per_sale",
            )
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"