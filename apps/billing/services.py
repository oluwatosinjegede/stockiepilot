import uuid
from decimal import Decimal
from django.utils import timezone

from .models import AffiliateCommission, Invoice

def generate_invoice(company, amount, description="Subscription Payment"):

    invoice = Invoice.objects.create(
        company=company,
        invoice_number=str(uuid.uuid4()),
        amount=amount,
        due_date=timezone.now(),
        description=description
    )
    return invoice



def create_signup_invoice(company):
    

    return Invoice.objects.create(
        company=company,
        invoice_number=str(uuid.uuid4()),
        amount=5000,
        description="Signup Fee",
        due_date=timezone.now()
    )



def activate_subscription_after_payment(payment):

    subscription = payment.invoice.subscription

    subscription.status = 'active'
    subscription.extend_subscription()


def create_affiliate_commission_for_payment(payment):
    company = payment.company
    affiliate = getattr(company, "referred_by_affiliate", None)

    if not affiliate:
        return None

    if payment.payment_type != "subscription":
        return None

    commission_rate = Decimal("10.00")
    commission_amount = (payment.amount * commission_rate) / Decimal("100")

    commission, _ = AffiliateCommission.objects.get_or_create(
        payment=payment,
        defaults={
            "affiliate": affiliate,
            "company": company,
            "commission_rate": commission_rate,
            "commission_amount": commission_amount,
        },
    )
    return commission