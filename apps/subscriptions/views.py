from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from .services.paystack import (
    initialize_paystack_payment,
    verify_paystack_payment,
)
from .constants import Plans


# =========================
# HELPERS
# =========================

def get_user_company(user):
    return getattr(user, "company", None)


def validate_plan(plan):
    return plan in Plans.CHOICES


# =========================
# SUBSCRIPTION PAGE
# =========================

@login_required
def subscription_view(request):

    if request.user.role == "user":
        messages.error(request, "Company users can only access the Sales module.")
        return redirect("sales")
    
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "No company linked to your account.")
        return redirect("dashboard")

    return render(
        request,
        "subscription.html",
        {
            "current_plan": company.subscription_plan,
            "plans": Plans.CHOICES,
            "plan_labels": Plans.LABELS,
        },
    )


# =========================
# SUBSCRIBE / CHANGE PLAN
# =========================

@login_required
def subscribe(request, plan):
    if request.user.role == "user":
        messages.error(request, "Company users can only access the Sales module.")
        return redirect("sales")
    
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "No company linked to your account.")
        return redirect("dashboard")

    #  Validate plan
    if not validate_plan(plan):
        messages.error(request, "Invalid subscription plan.")
        return redirect("subscription")

    #  Prevent redundant updates
    if company.subscription_plan == plan:
        messages.info(
            request,
            f"You are already on the {Plans.LABELS.get(plan, plan)} plan.",
        )
        return redirect("subscription")

    #  Handle FREE plan (no payment required)
    if plan == Plans.FREE:
        company.subscription_plan = plan
        company.save(update_fields=["subscription_plan"])

        messages.success(request, "Switched to Free plan.")
        return redirect("subscription")

    # Initialize Paystack payment
    try:
        payment_url = initialize_paystack_payment(
            email=request.user.email,
            amount=Plans.PRICES.get(plan),
            metadata={
                "user_id": request.user.id,
                "plan": plan,
            },
        )
    except Exception as e:
        messages.error(request, "Unable to initialize payment. Try again.")
        return redirect("subscription")

    return redirect(payment_url)


# =========================
# PAYMENT CALLBACK
# =========================

@login_required
def payment_callback(request):
    if request.user.role == "user":
        messages.error(request, "Company users can only access the Sales module.")
        return redirect("sales")
    
    reference = request.GET.get("reference")

    if not reference:
        messages.error(request, "Missing payment reference.")
        return redirect("subscription")

    try:
        result = verify_paystack_payment(reference)
    except Exception:
        messages.error(request, "Payment verification failed.")
        return redirect("subscription")

    # Validate Paystack response
    if not result.get("status"):
        messages.error(request, "Payment not successful.")
        return redirect("subscription")

    data = result.get("data", {})
    metadata = data.get("metadata", {})

    plan = metadata.get("plan")
    user_id = metadata.get("user_id")

    # SECURITY VALIDATIONS
    if not validate_plan(plan):
        messages.error(request, "Invalid plan in payment data.")
        return redirect("subscription")

    if user_id != request.user.id:
        messages.error(request, "User mismatch detected.")
        return redirect("subscription")

    expected_amount = Plans.PRICES.get(plan)
    if data.get("amount") != expected_amount:
        messages.error(request, "Payment amount mismatch.")
        return redirect("subscription")

    # Apply subscription
    company = get_user_company(request.user)
    if not company:
        messages.error(request, "No company linked to your account.")
        return redirect("dashboard")

    company.subscription_plan = plan
    company.save(update_fields=["subscription_plan"])

    messages.success(
        request,
        f"Successfully activated {Plans.LABELS.get(plan, plan)} plan.",
    )

    return redirect("subscription")