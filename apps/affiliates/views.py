from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .models import AffiliateActivationToken, AffiliateProfile
from .services import activate_affiliate_by_token, send_affiliate_activation_email


@login_required
def affiliate_dashboard(request):
    affiliate = get_object_or_404(
        AffiliateProfile.objects.select_related("wallet", "user"),
        user=request.user,
    )

    referrals = affiliate.referrals.select_related("referred_user").order_by("-created_at")
    paid_referrals = referrals.filter(status__in=["paid", "commissioned"])
    wallet = getattr(affiliate, "wallet", None)

    context = {
        "affiliate": affiliate,
        "wallet": wallet,
        "referrals": referrals,
        "paid_referrals": paid_referrals,
        "paid_count": paid_referrals.count(),
        "total_commission": paid_referrals.aggregate(total=Sum("commission_amount"))["total"] or 0,
    }
    return render(request, "affiliates/dashboard.html", context)


@login_required
def resend_affiliate_activation(request):
    affiliate = get_object_or_404(AffiliateProfile, user=request.user)

    if affiliate.email_confirmed and affiliate.status == "active":
        messages.info(request, "Your affiliate account is already active.")
        return redirect("affiliate_dashboard")

    send_affiliate_activation_email(request, affiliate)
    messages.success(request, "Activation email sent successfully.")
    return redirect("affiliate_dashboard")


def activate_affiliate(request, token):
    try:
        affiliate = activate_affiliate_by_token(token)
    except AffiliateActivationToken.DoesNotExist:
        messages.error(request, "Invalid or already used activation link.")
        return redirect("login")

    messages.success(
        request,
        f"Affiliate account activated successfully for {affiliate.user.email}.",
    )
    return redirect("login")


@staff_member_required
def admin_affiliate_earnings(request):
    affiliates = AffiliateProfile.objects.select_related("user", "wallet").prefetch_related("referrals")
    return render(
        request,
        "affiliates/admin_earnings.html",
        {"affiliates": affiliates},
    )
