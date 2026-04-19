from django.contrib import admin

from .models import AffiliateCommission, Invoice, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_reference", "company", "payment_type", "amount", "status", "created_at")
    search_fields = ("transaction_reference", "company__name")
    list_filter = ("payment_type", "status", "created_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "company", "amount", "status", "created_at")
    search_fields = ("invoice_number", "company__name")
    list_filter = ("status", "created_at")


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "company", "commission_rate", "commission_amount", "created_at")
    search_fields = ("affiliate__email", "company__name")

