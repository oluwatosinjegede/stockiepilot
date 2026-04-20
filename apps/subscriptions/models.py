from datetime import timedelta

from django.db import models
from django.utils import timezone

from .constants import BillingCycle, PLAN_DEFINITIONS, Plans

class SubscriptionPlan(models.Model):
    """Legacy plan model retained for backward compatibility."""

    BILLING_CHOICES = ((BillingCycle.MONTHLY, "Monthly"), (BillingCycle.ANNUAL, "Annual"))

    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CHOICES, default=BillingCycle.MONTHLY)
    max_products = models.IntegerField(default=100)
    max_users = models.IntegerField(default=5)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Subscription(models.Model):
    STATUS_TRIALING = "trialing"
    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = (
        (STATUS_TRIALING, "Trialing"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAST_DUE, "Past Due"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_CANCELED, "Canceled"),
    )

    BILLING_CYCLE_CHOICES = (
        (BillingCycle.MONTHLY, "Monthly"),
        (BillingCycle.ANNUAL, "Annual"),
    )

    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="subscriptions")
    plan_name = models.CharField(max_length=20, choices=[(p, p.title()) for p in Plans.CHOICES], default=Plans.FREE)
    plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan",
        on_delete=models.PROTECT,
        related_name="subscriptions",
        null=True,
        blank=True,
    )

    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default=BillingCycle.MONTHLY)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIALING)
    auto_renew = models.BooleanField(default=False)

    started_at = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    upgraded_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    # legacy fields maintained during transition

    start_date = models.DateTimeField(default=timezone.now)

    end_date = models.DateTimeField(null=True, blank=True)

    trial_end_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        indexes = [models.Index(fields=["company"]), models.Index(fields=["status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} - {self.plan_name}"
    
    @property
    def is_trial(self):
        return self.status == self.STATUS_TRIALING and self.trial_end and self.trial_end >= timezone.now()

    @property
    def is_active(self):
        now = timezone.now()
        if self.status == self.STATUS_ACTIVE and self.current_period_end and self.current_period_end >= now:
            return True
        if self.status == self.STATUS_TRIALING and self.trial_end and self.trial_end >= now:
            return True
        return False

    def mark_expired(self):
        self.status = self.STATUS_EXPIRED
        self.auto_renew = False
        self.current_period_end = self.current_period_end or timezone.now()
        self.end_date = self.current_period_end
        self.save(update_fields=["status", "auto_renew", "current_period_end", "end_date", "updated_at"])

    def set_period_dates(self, start_at=None):
        start_at = start_at or timezone.now()
        self.current_period_start = start_at
        if self.billing_cycle == BillingCycle.ANNUAL:
            self.current_period_end = start_at + timedelta(days=365)
        else:
            self.current_period_end = start_at + timedelta(days=30)
        self.start_date = self.started_at
        self.end_date = self.current_period_end

    def renew(self, payment_success=True):
        if not self.auto_renew or self.status == self.STATUS_CANCELED:
            return self

        if not payment_success:
            self.status = self.STATUS_PAST_DUE
            self.save(update_fields=["status", "updated_at"])
            return self

        start_at = self.current_period_end or timezone.now()
        self.set_period_dates(start_at=start_at)
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=[
            "current_period_start",
            "current_period_end",
            "start_date",
            "end_date",
            "status",
            "updated_at",
        ])
        return self

    def sync_legacy_dates(self):
        self.start_date = self.started_at
        self.end_date = self.current_period_end
        self.trial_end_date = self.trial_end



def _ensure_plan_records(sender, **kwargs):
    for plan_name, meta in PLAN_DEFINITIONS.items():
        SubscriptionPlan.objects.get_or_create(
            name=plan_name,
            defaults={
                "price": meta["monthly"],
                "billing_cycle": BillingCycle.MONTHLY,
                "max_products": meta["max_products"] or 999999,
                "max_users": 999,
            },
        )

models.signals.post_migrate.connect(_ensure_plan_records)