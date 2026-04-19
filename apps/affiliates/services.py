from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    AffiliateActivationToken,
    AffiliateProfile,
    AffiliateReferral,
    AffiliateWallet,
    AffiliateWalletTransaction,
)


def generate_referral_code(user) -> str:
    base = (user.full_name or user.email.split("@")[0]).replace(" ", "").upper()[:6]
    suffix = str(user.id or "")[-4:] if user.id else "0001"
    return f"SP{base}{suffix}"


def send_affiliate_activation_email(request, affiliate: AffiliateProfile):
    token = AffiliateActivationToken.objects.create(affiliate=affiliate)
    activation_link = request.build_absolute_uri(
        reverse("activate_affiliate", kwargs={"token": token.token})
    )

    subject = "Activate your StockiePilot affiliate account"
    message = (
        f"Hello {affiliate.user.full_name or affiliate.user.email},\n\n"
        f"Please activate your affiliate account by clicking the link below:\n"
        f"{activation_link}\n\n"
        "If you did not request this, you can ignore this email."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[affiliate.user.email],
        fail_silently=False,
    )


@transaction.atomic
def activate_affiliate_by_token(token_value):
    token = AffiliateActivationToken.objects.select_related("affiliate", "affiliate__user").get(
        token=token_value,
        is_used=False,
    )
    token.is_used = True
    token.save(update_fields=["is_used"])

    affiliate = token.affiliate
    affiliate.activate()
    AffiliateWallet.objects.get_or_create(affiliate=affiliate)
    return affiliate


@transaction.atomic
def register_affiliate_for_user(user):
    profile, created = AffiliateProfile.objects.get_or_create(
        user=user,
        defaults={
            "referral_code": generate_referral_code(user),
            "status": "pending",
        },
    )
    AffiliateWallet.objects.get_or_create(affiliate=profile)
    return profile, created


@transaction.atomic
def attach_referral_to_new_user(new_user, referral_code: str):
    if not referral_code:
        return None

    try:
        affiliate = AffiliateProfile.objects.get(
            referral_code=referral_code.strip().upper(),
            status="active",
            email_confirmed=True,
        )
    except AffiliateProfile.DoesNotExist:
        return None

    referral, _ = AffiliateReferral.objects.get_or_create(
        affiliate=affiliate,
        referred_user=new_user,
        defaults={
            "referred_email": new_user.email,
            "status": "registered",
        },
    )
    return referral


@transaction.atomic
def credit_affiliate_commission_for_payment(referred_user, payment_amount: Decimal, reference: str = ""):
    try:
        referral = AffiliateReferral.objects.select_related(
            "affiliate", "affiliate__wallet"
        ).get(
            referred_user=referred_user,
            status__in=["registered", "paid"],
        )
    except AffiliateReferral.DoesNotExist:
        return None

    commission = (payment_amount * referral.affiliate.commission_rate) / Decimal("100.00")
    wallet, _ = AffiliateWallet.objects.get_or_create(affiliate=referral.affiliate)

    wallet.credit(commission)

    AffiliateWalletTransaction.objects.create(
        wallet=wallet,
        transaction_type="credit",
        amount=commission,
        description=f"Commission from referral payment: {referred_user.email}",
        reference=reference,
    )

    referral.payment_amount = payment_amount
    referral.commission_amount = commission
    referral.status = "commissioned"
    referral.paid_at = timezone.now()
    referral.save(
        update_fields=["payment_amount", "commission_amount", "status", "paid_at"]
    )

    return referral
