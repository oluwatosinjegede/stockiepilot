# apps/billing/views.py

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

import requests
from django.conf import settings
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from .models import Payment
from .services import create_affiliate_commission_for_payment

import json
import hmac
import hashlib
from django.http import HttpResponse

from apps.subscriptions.services import activate_subscription

@login_required
def pay_signup(request):

    user = request.user
    company = user.company

    amount = 15000  # ₦15000 (in Naira)
    
    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "email": user.email,
        "amount": amount * 100,  # kobo
        "callback_url": "http://127.0.0.1:8000/billing/payment-success/",
        "metadata": {
             "company_id": company.id,
            "payment_type": "signup",
        }
    }

    response = requests.post(url, json=data, headers=headers)
    res_data = response.json()

    if res_data["status"]:
        return redirect(res_data["data"]["authorization_url"])

    return redirect('dashboard')


def payment_success(request):
    return render(request, "billing/payment_success.html")

@csrf_exempt
def paystack_webhook(request):

    payload = request.body
    signature = request.headers.get('x-paystack-signature')

    # Verify Paystack signature
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        payload,
        hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        return HttpResponse(status=400)

    data = json.loads(payload)

    if data['event'] == 'charge.success':

        payment_data = data['data']

        email = payment_data['customer']['email']
        amount = payment_data['amount'] / 100
        reference = payment_data['reference']
        gateway = payment_data.get("channel", "paystack")
        metadata = payment_data.get("metadata") or {}
        payment_type = metadata.get("payment_type", "subscription")

        # Find user/company
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user = User.objects.get(email=email)
        company = user.company

        # Save payment
        payment = Payment.objects.create(
            company=company,
            payment_type=payment_type,
            amount=amount,
            payment_gateway=gateway,
            transaction_reference=reference,
            status='success'
        )

        create_affiliate_commission_for_payment(payment)

        # 🔥 Activate subscription
        activate_subscription(company)

    return HttpResponse(status=200)