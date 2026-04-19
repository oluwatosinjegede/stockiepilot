from django.contrib import admin
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "referred_by_affiliate", "created_at")
    search_fields = ("name", "email")