from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.companies.models import Company
from apps.products.models import Product

class Sale(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("paid", "Paid in Full"),
        ("partial", "Part Payment"),
        ("zero", "Zero Payment"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("unpaid", "Unpaid"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sales")
    products = models.ManyToManyField(Product, through="SaleItem", related_name="sales", blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="paid")
    customer_name = models.CharField(max_length=255, blank=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "created_at"]), models.Index(fields=["company", "status"])]


    def recalculate_totals(self):
        from django.db.models import Sum

        total = self.items.aggregate(total=Sum("total_price"))["total"] or Decimal("0")
        total_paid = self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")

        self.total_amount = total
        self.amount_paid = min(total_paid, total)
        self.balance = max(total - self.amount_paid, Decimal("0"))

        if self.amount_paid <= 0:
            self.payment_status = "zero"
            self.status = "unpaid"
        elif self.balance > 0:
            self.payment_status = "partial"
            self.status = "pending"
        else:
            self.payment_status = "paid"
            self.status = "completed"

    def __str__(self):
        return f"{self.company.name} - ₦{self.total_amount}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["sale", "product"], name="unique_product_per_sale")]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

class SaleInvoice(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name="invoice")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sale_invoices")
    invoice_number = models.CharField(max_length=50, unique=True)
    payment_status = models.CharField(max_length=20, default="pending")
    due_status = models.CharField(max_length=20, default="due")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number


class SalePayment(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sale_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_sale_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "created_at"]), models.Index(fields=["sale", "created_at"])]

    def __str__(self):
        return f"Payment ₦{self.amount} for sale #{self.sale_id}"


class PaymentReceipt(models.Model):
    sale_payment = models.OneToOneField(SalePayment, on_delete=models.CASCADE, related_name="receipt")
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="receipts")
    invoice = models.ForeignKey(SaleInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="receipts")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="payment_receipts")
    receipt_number = models.CharField(max_length=50, unique=True)
    payment_date = models.DateTimeField(default=timezone.now)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    generated_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.receipt_number