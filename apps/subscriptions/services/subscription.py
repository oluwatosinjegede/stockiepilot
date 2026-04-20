from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.subscriptions.constants import BillingCycle, PLAN_DEFINITIONS, Plans
from apps.subscriptions.models import Subscription


TRIAL_DAYS = 30


def get_plan_features(plan_name):
    return PLAN_DEFINITIONS.get(plan_name or Plans.FREE, PLAN_DEFINITIONS[Plans.FREE])


def get_company_subscription(company):
    subscription = company.subscriptions.order_by("-created_at").first()
    if subscription:
        return subscription
    return create_initial_subscription(company)


def is_subscription_active(company):
    subscription = get_company_subscription(company)
    now = timezone.now()

    if subscription.status == Subscription.STATUS_TRIALING:
        if subscription.trial_end and subscription.trial_end >= now:
            return True
        subscription.status = Subscription.STATUS_EXPIRED
        subscription.auto_renew = False
        subscription.save(update_fields=["status", "auto_renew", "updated_at"])
        return False

    if subscription.status == Subscription.STATUS_ACTIVE and subscription.current_period_end and subscription.current_period_end >= now:
        return True

    if subscription.status == Subscription.STATUS_CANCELED and subscription.current_period_end and subscription.current_period_end >= now:
        return True

    return False


def can_create_product(company):
    subscription = get_company_subscription(company)
    if not is_subscription_active(company):
        return False

    from apps.products.models import Product

    features = get_plan_features(subscription.plan_name)
    max_products = features.get("max_products")
    if max_products is None:
        return True
    return Product.objects.filter(company=company).count() < max_products


def can_access_analytics(company):
    subscription = get_company_subscription(company)
    if not is_subscription_active(company):
        return False
    return get_plan_features(subscription.plan_name).get("analytics_level") != "none"


def can_access_multi_branch(company):
    subscription = get_company_subscription(company)
    if not is_subscription_active(company):
        return False
    return bool(get_plan_features(subscription.plan_name).get("multi_branch"))


@transaction.atomic

def create_initial_subscription(company):
    """Every new company starts on free 30-day trial."""

    existing = company.subscriptions.filter(
        status__in=[Subscription.STATUS_TRIALING, Subscription.STATUS_ACTIVE, Subscription.STATUS_PAST_DUE]
    ).order_by("-created_at").first()
    if existing:
        return existing

    now = timezone.now()
    trial_end = now + timedelta(days=TRIAL_DAYS)

    subscription = Subscription.objects.create(
        company=company,
        plan_name=Plans.FREE,
        billing_cycle=BillingCycle.MONTHLY,
        amount=Decimal("0"),
        status=Subscription.STATUS_TRIALING,
        auto_renew=False,
        started_at=now,
        current_period_start=now,
        current_period_end=trial_end,
        trial_start=now,
        trial_end=trial_end,
        upgraded_at=None,
        canceled_at=None,
        start_date=now,
        end_date=trial_end,
        trial_end_date=trial_end,
    )
    if hasattr(company, "subscription_plan"):
        company.subscription_plan = Plans.FREE
        company.save(update_fields=["subscription_plan"])
    return subscription


@transaction.atomic
def upgrade_subscription(company, plan_name, billing_cycle=BillingCycle.MONTHLY, auto_renew=True):
    """Create/update entitlement record after successful payment."""

    if plan_name not in Plans.CHOICES:
        raise ValueError("Invalid plan selected")

    subscription = get_company_subscription(company)
    now = timezone.now()
    plan_meta = get_plan_features(plan_name)

    amount = plan_meta["annual" if billing_cycle == BillingCycle.ANNUAL else "monthly"]

    subscription.plan_name = plan_name
    subscription.billing_cycle = billing_cycle
    subscription.amount = amount
    subscription.status = Subscription.STATUS_ACTIVE
    subscription.auto_renew = auto_renew
    subscription.started_at = now
    subscription.current_period_start = now
    if billing_cycle == BillingCycle.ANNUAL:
        subscription.current_period_end = now + timedelta(days=365)
    else:
        subscription.current_period_end = now + timedelta(days=30)
    subscription.trial_start = subscription.trial_start
    subscription.trial_end = subscription.trial_end
    subscription.upgraded_at = now
    subscription.sync_legacy_dates()
    subscription.save()
    if hasattr(company, "subscription_plan"):
        company.subscription_plan = plan_name
        company.save(update_fields=["subscription_plan"])
    return subscription


@transaction.atomic
def cancel_subscription(company):
    subscription = get_company_subscription(company)
    subscription.status = Subscription.STATUS_CANCELED
    subscription.auto_renew = False
    subscription.canceled_at = timezone.now()
    subscription.save(update_fields=["status", "auto_renew", "canceled_at", "updated_at"])
    return subscription


def renew_subscription(subscription, payment_success=True):
    return subscription.renew(payment_success=payment_success)


def process_expired_trials():
    now = timezone.now()
    stale_trials = Subscription.objects.filter(status=Subscription.STATUS_TRIALING, trial_end__lt=now)
    for sub in stale_trials:
        sub.status = Subscription.STATUS_EXPIRED
        sub.auto_renew = False
        sub.save(update_fields=["status", "auto_renew", "updated_at"])