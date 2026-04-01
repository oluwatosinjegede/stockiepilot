# apps/subscriptions/services.py

from django.utils import timezone
from datetime import timedelta

from apps.subscriptions.models import Subscription, SubscriptionPlan


# =========================
# CREATE INITIAL SUBSCRIPTION
# =========================
def create_initial_subscription(company, plan_name='basic'):

    # Safe plan retrieval
    plan, _ = SubscriptionPlan.objects.get_or_create(
        name=plan_name,
        defaults={
            "price": 15000,
            "billing_cycle": "monthly",
            "max_products": 100,
            "max_users": 5
        }
    )

    # Prevent duplicate active/trial subscriptions
    existing = company.subscriptions.filter(
        status__in=['trial', 'active']
    ).last()

    if existing:
        return existing

    # Create trial subscription
    subscription = Subscription.objects.create(
        company=company,
        plan=plan,
        status='trial',
        start_date=timezone.now(),
        trial_end_date=timezone.now() + timedelta(days=7),
        end_date=timezone.now() + timedelta(days=7)
    )

    return subscription


# =========================
# ACTIVATE SUBSCRIPTION
# =========================
def activate_subscription(company):

    subscription = company.subscriptions.last()

    if not subscription:
        return None

    # Use model logic instead of duplicating
    subscription.activate()

    return subscription


# =========================
# EXTEND SUBSCRIPTION (RENEWAL)
# =========================
def renew_subscription(company):

    subscription = company.subscriptions.last()

    if not subscription:
        return None

    subscription.extend_subscription()

    return subscription


# =========================
# EXPIRE SUBSCRIPTION CHECK
# =========================
def check_and_expire_subscriptions():

    subscriptions = Subscription.objects.filter(status='active')

    for sub in subscriptions:
        if sub.has_expired():
            sub.mark_expired()