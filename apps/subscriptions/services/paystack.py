import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.subscriptions.constants import Plans


# =========================
# PLAN PRICING
# =========================
PLAN_PRICES = {
    Plans.BASIC: 2500,
    Plans.PRO: 5000,
    Plans.ENTERPRISE: 15000,
}


# =========================
# INITIALIZE PAYMENT
# =========================
@login_required
def initialize_paystack_payment(request, plan):
    company = request.user.company

    if plan not in PLAN_PRICES:
        messages.error(request, "Invalid plan")
        return redirect("subscription")

    amount = PLAN_PRICES[plan] * 100  # Paystack uses kobo

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
            "company_id": company.id
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
            plan = data["metadata"]["plan"]

            company = request.user.company
            company.subscription_plan = plan
            company.save()

            messages.success(request, f"Payment successful. Plan upgraded to {plan.capitalize()}")
            return redirect("dashboard")

    messages.error(request, "Payment verification failed")
    return redirect("subscription")