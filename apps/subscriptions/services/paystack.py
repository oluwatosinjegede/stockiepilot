import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.subscriptions.constants import BillingCycle, PLAN_DEFINITIONS, Plans
from apps.subscriptions.services import upgrade_subscription

def _get_plan_amount_in_kobo(plan, billing_cycle):
    if plan not in PLAN_DEFINITIONS:
        return None
    cycle_key = "annual" if billing_cycle == BillingCycle.ANNUAL else "monthly"
    amount = PLAN_DEFINITIONS[plan][cycle_key]
    return int(amount * 100)


# =========================
# INITIALIZE PAYMENT
# =========================
@login_required
def initialize_paystack_payment(request, plan):
    company = request.user.company

    if plan == Plans.FREE:
        messages.error(request, "Free plan is only available as an onboarding trial.")
        return redirect("subscription")

    billing_cycle = request.GET.get("billing_cycle", BillingCycle.MONTHLY)
    if billing_cycle not in BillingCycle.CHOICES:
        messages.error(request, "Invalid billing cycle selected.")
        return redirect("subscription")

    amount = _get_plan_amount_in_kobo(plan, billing_cycle)
    if amount is None:
        messages.error(request, "Invalid plan")
        return redirect("subscription")

    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "email": request.user.email,
        "amount": amount,
        "callback_url": "https://stockiepilot.up.railway.app/subscription/verify/",
        "metadata": {
            "plan": plan,
             "company_id": company.id,
            "billing_cycle": billing_cycle,
        }
    }

    response = requests.post(url, json=data, headers=headers)
    res_data = response.json()

    if res_data.get("status"):
        return redirect(res_data["data"]["authorization_url"])

    messages.error(request, "Payment initialization failed")
    return redirect("subscription")


# =========================
# VERIFY PAYMENT
# =========================
@login_required
def verify_paystack_payment(request):
    reference = request.GET.get("reference")

    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
    }

    response = requests.get(url, headers=headers)
    res_data = response.json()

    if res_data.get("status"):
        data = res_data["data"]

        if data["status"] == "success":
            metadata = data.get("metadata") or {}
            plan = metadata.get("plan")
            billing_cycle = metadata.get("billing_cycle", BillingCycle.MONTHLY)

            company = request.user.company
            if plan not in Plans.CHOICES or plan == Plans.FREE:
                messages.error(request, "Invalid subscription plan returned from payment.")
                return redirect("subscription")
            if billing_cycle not in BillingCycle.CHOICES:
                billing_cycle = BillingCycle.MONTHLY

            upgrade_subscription(
                company=company,
                plan_name=plan,
                billing_cycle=billing_cycle,
                auto_renew=True,
            )

            messages.success(
                request,
                f"Payment successful. Plan upgraded to {plan.capitalize()} ({billing_cycle}).",
            )
            return redirect("subscription")

    messages.error(request, "Payment verification failed")
    return redirect("subscription")