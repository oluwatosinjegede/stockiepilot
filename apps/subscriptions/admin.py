from django.contrib import admin

from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "billing_cycle", "max_products", "max_users")
    search_fields = ("name",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "plan_name",
        "billing_cycle",
        "status",
        "trial_end",
        "current_period_end",
        "auto_renew",
    )
    list_filter = ("status", "plan_name", "billing_cycle", "auto_renew")
    search_fields = ("company__name", "company__email")