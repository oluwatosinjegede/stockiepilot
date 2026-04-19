from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Affiliate, User

@admin.register(User)
class CustomUserAdmin(UserAdmin):

    # Fields shown in admin list
    list_display = ('email', 'username', 'company', 'is_staff')

    # Add company field to admin form
    fieldsets = UserAdmin.fieldsets + (
        ("Company Info", {"fields": ("company",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Company Info", {"fields": ("company",)}),
    )

    search_fields = ('email', 'username')
    ordering = ('email',)


@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("full_name", "email", "phone")