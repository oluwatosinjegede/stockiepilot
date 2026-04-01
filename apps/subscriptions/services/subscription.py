# apps/subscriptions/services/subscription.py

from apps.subscriptions.constants import Plans


def create_initial_subscription(company):
    """
    Assign default FREE plan to new company
    """
    if not company.subscription_plan:
        company.subscription_plan = Plans.FREE
        company.save(update_fields=["subscription_plan"])