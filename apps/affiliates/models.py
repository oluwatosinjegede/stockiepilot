from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AffiliateProfile(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("active", "Active"),
        ("suspended", "Suspended"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_profile",
    )
    referral_code = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("10.00"))
    email_confirmed = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def activate(self):
        self.status = "active"
        self.email_confirmed = True
        self.activated_at = timezone.now()
        self.save(update_fields=["status", "email_confirmed", "activated_at"])

    def __str__(self):
        return f"{self.user.email} - {self.referral_code}"


class AffiliateActivationToken(models.Model):
    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.CASCADE,
        related_name="activation_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.affiliate.user.email} - {self.token}"


class AffiliateWallet(models.Model):
    affiliate = models.OneToOneField(
        AffiliateProfile,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    updated_at = models.DateTimeField(auto_now=True)

    def credit(self, amount: Decimal):
        self.balance += amount
        self.total_earned += amount
        self.save(update_fields=["balance", "total_earned", "updated_at"])

    def debit(self, amount: Decimal):
        if amount > self.balance:
            raise ValueError("Insufficient wallet balance")
        self.balance -= amount
        self.total_withdrawn += amount
        self.save(update_fields=["balance", "total_withdrawn", "updated_at"])

    def __str__(self):
        return f"{self.affiliate.user.email} Wallet"


class AffiliateReferral(models.Model):
    STATUS_CHOICES = (
        ("registered", "Registered"),
        ("paid", "Paid"),
        ("commissioned", "Commissioned"),
        ("cancelled", "Cancelled"),
    )

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.CASCADE,
        related_name="referrals",
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_referrals_received",
    )
    referred_email = models.EmailField()
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="registered")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("affiliate", "referred_user")

    def __str__(self):
        return f"{self.affiliate.user.email} -> {self.referred_email}"


class AffiliateWalletTransaction(models.Model):
    TXN_TYPES = (
        ("credit", "Credit"),
        ("debit", "Debit"),
    )

    wallet = models.ForeignKey(
        AffiliateWallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(max_length=10, choices=TXN_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet.affiliate.user.email} - {self.transaction_type} - {self.amount}"
