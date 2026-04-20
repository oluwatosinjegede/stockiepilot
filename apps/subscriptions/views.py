from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .constants import BillingCycle, PLAN_DEFINITIONS, Plans
from .services import (
    get_company_subscription,
    get_plan_features,
    is_subscription_active,
    upgrade_subscription,
)

def get_user_company(user):
    return getattr(user, "company", None)


def validate_plan(plan):
    return plan in Plans.CHOICES

def validate_billing_cycle(cycle):
    return cycle in BillingCycle.CHOICES

@login_required
def subscription_view(request):
    if request.user.is_affiliate:
        messages.error(request, "Affiliate accounts cannot access Subscription.")
        return redirect("affiliate_dashboard")

    if request.user.role == "user":
        messages.error(request, "Company users can only access the Sales module.")
        return redirect("sales")
    
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "No company linked to your account.")
        return redirect("dashboard")
    
    selected_cycle = request.GET.get("billing_cycle", BillingCycle.MONTHLY)
    if not validate_billing_cycle(selected_cycle):
        selected_cycle = BillingCycle.MONTHLY

    subscription = get_company_subscription(company)
    active = is_subscription_active(company)

    now = timezone.now()
    trial_days_remaining = 0
    if subscription.trial_end and subscription.status == "trialing":
        trial_days_remaining = max((subscription.trial_end - now).days, 0)

    plan_cards = []
    for plan_name in Plans.CHOICES:
        features = get_plan_features(plan_name)
        plan_cards.append(
            {
                "key": plan_name,
                "label": Plans.LABELS[plan_name],
                "monthly": features["monthly"],
                "annual": features["annual"],
                "features": features,
            }
        )

    return render(
        request,
        "subscription.html",
        {
            "current_plan": subscription.plan_name,
            "subscription": subscription,
            "plan_cards": plan_cards,
            "selected_billing_cycle": selected_cycle,
            "trial_days_remaining": trial_days_remaining,
            "trial_expired": subscription.status in {"expired", "past_due"} and not active,
            "is_active": active,
            "pricing": PLAN_DEFINITIONS,
        },
    )

@login_required
def subscribe(request, plan):
    if request.user.is_affiliate:
        messages.error(request, "Affiliate accounts cannot access Subscription.")
        return redirect("affiliate_dashboard")

    if request.user.role == "user":
        messages.error(request, "Company users can only access the Sales module.")
        return redirect("sales")
    
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "No company linked to your account.")
        return redirect("dashboard")

    if not validate_plan(plan):
        messages.error(request, "Invalid subscription plan.")
        return redirect("subscription")

    billing_cycle = request.POST.get("billing_cycle") or request.GET.get("billing_cycle") or BillingCycle.MONTHLY
    if not validate_billing_cycle(billing_cycle):
        messages.error(request, "Invalid billing cycle.")
        return redirect("subscription")

    if plan == Plans.FREE:
        messages.error(request, "Free plan is only available as an onboarding trial.")
        return redirect("subscription")

    upgraded = upgrade_subscription(company, plan_name=plan, billing_cycle=billing_cycle, auto_renew=True)

    messages.success(
        request,
        f"Subscription updated to {Plans.LABELS[plan]} ({billing_cycle}). Next renewal: {upgraded.current_period_end.date()}.",
    )

    return redirect("subscription")