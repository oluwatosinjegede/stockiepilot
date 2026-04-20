from django.contrib import admin

from .models import Category, Product, ProductSupply, Supplier


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "contact_person", "phone", "is_active", "created_at")
    list_filter = ("company", "is_active", "created_at")
    search_fields = ("name", "company__name", "contact_person", "phone", "email")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "category", "quantity", "selling_price", "cost_price")
    list_filter = ("company", "category")
    search_fields = ("name", "sku", "company__name")


@admin.register(ProductSupply)
class ProductSupplyAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "company",
        "supplier",
        "date_supplied",
        "supplier_invoice_number",
        "quantity_supplied",
        "unit_cost",
        "total_cost",
    )
    list_filter = ("company", "supplier", "date_supplied")
    search_fields = ("product__name", "supplier__name", "supplier_invoice_number", "company__name")


