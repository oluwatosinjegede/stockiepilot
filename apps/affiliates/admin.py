from django.contrib import admin

from .models import (
    AffiliateActivationToken,
    AffiliateProfile,
    AffiliateReferral,
    AffiliateWallet,
    AffiliateWalletTransaction,
)


@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "referral_code", "status", "commission_rate", "email_confirmed", "activated_at")
    search_fields = ("user__email", "referral_code")
    list_filter = ("status", "email_confirmed")


@admin.register(AffiliateWallet)
class AffiliateWalletAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "balance", "total_earned", "total_withdrawn", "updated_at")
    search_fields = ("affiliate__user__email",)


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "referred_email", "payment_amount", "commission_amount", "status", "paid_at")
    search_fields = ("affiliate__user__email", "referred_email")
    list_filter = ("status",)


@admin.register(AffiliateWalletTransaction)
class AffiliateWalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "transaction_type", "amount", "description", "reference", "created_at")
    search_fields = ("wallet__affiliate__user__email", "reference")


@admin.register(AffiliateActivationToken)
class AffiliateActivationTokenAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "token", "is_used", "created_at")
    list_filter = ("is_used",)
