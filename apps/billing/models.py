# apps/billing/models.py

from django.db import models
from django.utils import timezone

class SubscriptionPlan(models.Model):
    PLAN_TYPES = (
        ('basic', 'Basic'),
        ('pro', 'Professional'),
        ('enterprise', 'Enterprise'),
    )

    name = models.CharField(max_length=50, choices=PLAN_TYPES, unique=True)
    description = models.TextField(blank=True)

    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2)

    max_products = models.IntegerField(default=100)
    max_users = models.IntegerField(default=3)
    max_branches = models.IntegerField(default=1)

    analytics_enabled = models.BooleanField(default=False)
    pos_enabled = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscription_plans"

    def __str__(self):
        return self.name
    

class Invoice(models.Model):

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    subscription = models.ForeignKey('subscriptions.Subscription', on_delete=models.SET_NULL, null=True, blank=True)

    invoice_number = models.CharField(max_length=100, unique=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "invoices"

    def __str__(self):
        return self.invoice_number
    

class Payment(models.Model):

    STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )

    PAYMENT_TYPE = (
        ('signup', 'Signup Fee'),
        ('subscription', 'Subscription'),
        ('upgrade', 'Upgrade'),
    )

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')

    payment_gateway = models.CharField(max_length=50)  # paystack, flutterwave
    transaction_reference = models.CharField(max_length=255, unique=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')

    gateway_response = models.JSONField(null=True, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments"
        indexes = [
            models.Index(fields=['transaction_reference']),
            models.Index(fields=['status']),
        ]

    def mark_success(self, response_data=None):
        self.status = 'success'
        self.gateway_response = response_data
        self.paid_at = timezone.now()
        self.save()

        if self.invoice:
            self.invoice.status = 'paid'
            self.invoice.paid_at = timezone.now()
            self.invoice.save()

    def __str__(self):
        return self.transaction_reference
    

class FeatureAccess(models.Model):
    FEATURE_CHOICES = (
        ('analytics', 'Analytics'),
        ('pos', 'POS'),
        ('multi_branch', 'Multi Branch'),
        ('api', 'API Access'),
    )

    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='features')
    feature_name = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = ('plan', 'feature_name')


class PaymentEvent(models.Model):
    event_type = models.CharField(max_length=100)
    reference = models.CharField(max_length=255)
    payload = models.JSONField()

    processed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
         db_table = "payment_events"


class AffiliateCommission(models.Model):
    affiliate = models.ForeignKey("users.Affiliate", on_delete=models.CASCADE, related_name="commissions")
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="affiliate_commissions")
    payment = models.OneToOneField("billing.Payment", on_delete=models.CASCADE, related_name="affiliate_commission")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "affiliate_commissions"

    def __str__(self):
        return f"{self.affiliate.email} - {self.commission_amount}"