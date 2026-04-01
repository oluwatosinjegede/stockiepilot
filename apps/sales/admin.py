from django.contrib import admin
from .models import Sale, SaleItem


# =========================
# INLINE (Sale Items inside Sale)
# =========================

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['total_price']


# =========================
# SALE ADMIN
# =========================

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'company', 'total_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['company__name']
    ordering = ['-created_at']
    inlines = [SaleItemInline]


# =========================
# SALE ITEM ADMIN
# =========================

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ['sale', 'product', 'quantity', 'unit_price', 'total_price']
    search_fields = ['product__name']