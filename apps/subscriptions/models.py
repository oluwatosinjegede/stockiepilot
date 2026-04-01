from django.utils import timezone
from datetime import timedelta
from django.db import models

class SubscriptionPlan(models.Model):

    BILLING_CHOICES = (
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES)

    max_products = models.IntegerField(default=100)
    max_users = models.IntegerField(default=5)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
class Subscription(models.Model):

    STATUS_CHOICES = (
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    BILLING_CYCLE = (
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )

    #  FIXED: correct app reference
    plan = models.ForeignKey(
        'subscriptions.SubscriptionPlan',
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )

    #plan = models.ForeignKey('subscriptions.SubscriptionPlan', on_delete=models.PROTECT)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial'
    )

    billing_cycle = models.CharField(
        max_length=10,
        choices=BILLING_CYCLE,
        default='monthly'
    )

    start_date = models.DateTimeField(default=timezone.now)

    #  FIX: allow null initially (avoid migration issues)
    end_date = models.DateTimeField(null=True, blank=True)

    auto_renew = models.BooleanField(default=True)

    trial_end_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    # =========================
    # BUSINESS LOGIC METHODS
    # =========================

    def is_active(self):
        return (
            self.status == 'active'
            and self.end_date
            and self.end_date >= timezone.now()
        )

    def is_trial(self):
        return (
            self.status == 'trial'
            and self.trial_end_date
            and self.trial_end_date >= timezone.now()
        )

    def has_expired(self):
        return self.end_date and self.end_date < timezone.now()

    def activate(self):
        """Activate subscription after payment"""
        self.status = 'active'
        self.start_date = timezone.now()
        self.set_end_date()
        self.save()

    def set_end_date(self):
        """Automatically set end date based on billing cycle"""
        if self.billing_cycle == 'monthly':
            self.end_date = timezone.now() + timedelta(days=30)
        else:
            self.end_date = timezone.now() + timedelta(days=365)

    def extend_subscription(self):
        """Extend existing subscription"""
        if not self.end_date:
            self.set_end_date()
        else:
            if self.billing_cycle == 'monthly':
                self.end_date += timedelta(days=30)
            else:
                self.end_date += timedelta(days=365)

        self.status = 'active'
        self.save()

    def mark_expired(self):
        """Mark subscription as expired"""
        if self.has_expired():
            self.status = 'expired'
            self.save()

    def __str__(self):
        return f"{self.company.name} - {self.plan.name}"