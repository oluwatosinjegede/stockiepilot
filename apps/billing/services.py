import uuid
from django.utils import timezone

from .models import Invoice
import uuid
from django.utils import timezone

def generate_invoice(company, amount, description="Subscription Payment"):
    from .models import Invoice

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