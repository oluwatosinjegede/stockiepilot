from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

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