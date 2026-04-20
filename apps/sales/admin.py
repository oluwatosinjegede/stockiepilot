from django.contrib import admin

from .models import PaymentReceipt, Sale, SaleInvoice, SaleItem, SalePayment


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ["total_price"]

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "total_amount", "amount_paid", "balance", "payment_status", "status", "created_at"]
    list_filter = ["company", "status", "payment_status", "created_at"]
    search_fields = ["company__name", "customer_name"]
    ordering = ["-created_at"]
    inlines = [SaleItemInline]

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ["sale", "product", "quantity", "unit_price", "total_price"]
    search_fields = ["product__name", "sale__company__name"]
    list_filter = ["sale__company"]


@admin.register(SaleInvoice)
class SaleInvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "company", "sale", "payment_status", "due_status", "created_at"]
    list_filter = ["company", "payment_status", "due_status", "created_at"]
    search_fields = ["invoice_number", "sale__customer_name", "company__name"]


@admin.register(SalePayment)
class SalePaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "sale", "amount", "payment_method", "reference", "created_at"]
    list_filter = ["company", "payment_method", "created_at"]
    search_fields = ["sale__customer_name", "reference", "company__name"]


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ["receipt_number", "company", "sale", "amount_paid", "remaining_balance", "payment_date"]
    list_filter = ["company", "payment_date", "created_at"]
    search_fields = ["receipt_number", "sale__customer_name", "company__name"]