from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "subscription_plan",
        "subscription_status",
        "subscription_billing_cycle",
        "subscription_trial_end",
        "subscription_renewal",
        "created_at",
    )
    search_fields = ("name", "email")

    @staticmethod
    def _latest_subscription(obj):
        return obj.subscriptions.order_by("-created_at").first()

    def subscription_status(self, obj):
        sub = self._latest_subscription(obj)
        return sub.status if sub else "-"

    def subscription_billing_cycle(self, obj):
        sub = self._latest_subscription(obj)
        return sub.billing_cycle if sub else "-"

    def subscription_trial_end(self, obj):
        sub = self._latest_subscription(obj)
        return sub.trial_end if sub else None

    def subscription_renewal(self, obj):
        sub = self._latest_subscription(obj)
        return sub.current_period_end if sub else None