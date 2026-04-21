import hashlib
import hmac
import json
import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from apps.affiliates.services import credit_affiliate_commission_for_company_payment
from apps.subscriptions.services import activate_subscription

from .models import Payment
from .services import create_affiliate_commission_for_payment

logger = logging.getLogger(__name__)

@login_required
def pay_signup(request):
    user = request.user
    company = user.company

    amount = 15000  # ₦15000 (in Naira)
    
    callback_url = request.build_absolute_uri('/billing/payment-success/')

    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "email": user.email,
        "amount": amount * 100,  # kobo
        "callback_url": callback_url,
        "metadata": {
            "company_id": company.id,
            "payment_type": "signup",
        },
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=15)
        response.raise_for_status()
        res_data = response.json()
    except requests.RequestException:
        logger.exception("Failed to initialize Paystack signup payment", extra={"user_id": user.id})
        return redirect('dashboard')

    if res_data.get("status") and res_data.get("data", {}).get("authorization_url"):
        return redirect(res_data["data"]["authorization_url"])
    
    logger.warning("Paystack initialization returned non-success response", extra={"response": res_data})
    return redirect('dashboard')


def payment_success(request):
    return render(request, "billing/payment_success.html")


@csrf_exempt
def paystack_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    if not settings.PAYSTACK_SECRET_KEY:
        logger.error("PAYSTACK_SECRET_KEY missing while processing webhook")
        return HttpResponse(status=500)

    payload = request.body
    signature = request.headers.get('x-paystack-signature')
    if not signature:
        return HttpResponse(status=400)

    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(signature, computed_signature):
        return HttpResponse(status=400)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    if data.get('event') == 'charge.success':
        payment_data = data.get('data', {})

        customer = payment_data.get('customer', {})
        email = customer.get('email')
        reference = payment_data.get('reference')
        amount = (payment_data.get('amount') or 0) / 100

        if not email or not reference or amount <= 0:
            logger.warning("Invalid webhook payload", extra={"payload": payment_data})
            return HttpResponse(status=400)

        gateway = payment_data.get("channel", "paystack")
        metadata = payment_data.get("metadata") or {}
        payment_type = metadata.get("payment_type", "subscription")

        user = get_user_model().objects.filter(email=email).select_related('company').first()
        if not user or not getattr(user, 'company', None):
            logger.warning("Webhook user/company not found", extra={"email": email})
            return HttpResponse(status=200)
        
        company = user.company

        payment, created = Payment.objects.get_or_create(
            transaction_reference=reference,
            defaults={
                'company': company,
                'payment_type': payment_type,
                'amount': amount,
                'payment_gateway': gateway,
                'status': 'success',
            },
        )

        if created:
            create_affiliate_commission_for_payment(payment)
            credit_affiliate_commission_for_company_payment(
                company=company,
                payment_amount=payment.amount,
                reference=reference,
                paying_user=user,
            )
            activate_subscription(company)

    return HttpResponse(status=200)