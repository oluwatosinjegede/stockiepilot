from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.sales.models import PaymentReceipt, Sale, SaleInvoice, SaleItem, SalePayment



def _next_doc_number(prefix, company):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{company.id}-{timestamp}"


def generate_invoice_for_sale(sale):
    invoice, created = SaleInvoice.objects.get_or_create(
        sale=sale,
        defaults={
            "company": sale.company,
            "invoice_number": _next_doc_number("INV", sale.company),
            "payment_status": sale.payment_status,
            "due_status": "settled" if sale.balance <= 0 else "due",
        },
    )
    if not created:
        invoice.payment_status = sale.payment_status
        invoice.due_status = "settled" if sale.balance <= 0 else "due"
        invoice.save(update_fields=["payment_status", "due_status"])
    return invoice


def recalculate_sale_balance(sale):
    sale.recalculate_totals()
    sale.save(update_fields=["total_amount", "amount_paid", "balance", "payment_status", "status"])
    generate_invoice_for_sale(sale)
    return sale


def generate_receipt_for_payment(sale_payment):
    sale = sale_payment.sale
    invoice = getattr(sale, "invoice", None)
    return PaymentReceipt.objects.create(
        sale_payment=sale_payment,
        sale=sale,
        invoice=invoice,
        company=sale.company,
        receipt_number=_next_doc_number("RCT", sale.company),
        payment_date=sale_payment.created_at,
        amount_paid=sale_payment.amount,
        remaining_balance=sale.balance,
        generated_by=sale_payment.created_by,
    )


@transaction.atomic
def record_sale_payment(sale, amount, payment_method, user, reference="", notes=""):
    amount = Decimal(amount or "0")
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if amount > sale.balance:
        raise ValidationError(f"Payment cannot exceed outstanding balance of ₦{sale.balance}.")

    payment = SalePayment.objects.create(
        sale=sale,
        company=sale.company,
        amount=amount,
        payment_method=(payment_method or "").strip(),
        reference=(reference or "").strip(),
        notes=(notes or "").strip(),
        created_by=user,
    )
    recalculate_sale_balance(sale)
    receipt = generate_receipt_for_payment(payment)
    return payment, receipt


@transaction.atomic
def create_sale_with_payment(company, user, sale_data, items_data):
    if not items_data:
        raise ValidationError("At least one sale item is required.")

    payment_type = sale_data.get("payment_status", "paid")
    if payment_type not in {"paid", "partial", "zero"}:
        raise ValidationError("Invalid payment type.")

    customer_name = (sale_data.get("customer_name") or "").strip()
    payment_method = (sale_data.get("payment_method") or "").strip()
    amount_paid = Decimal(sale_data.get("amount_paid") or "0")

    total = Decimal("0")
    for item in items_data:
        qty = int(item["quantity"])
        product = item["product"]
        if qty <= 0:
            raise ValidationError("Item quantities must be greater than zero.")
        if qty > product.quantity:
            raise ValidationError(f"Not enough stock for {product.name}.")
        total += Decimal(product.selling_price) * qty

    if not customer_name:
        raise ValidationError("Customer name is required for all sales.")
    if not payment_method:
        raise ValidationError("Payment method is required for all sales.")

    if payment_type == "paid":
        amount_paid = total
    elif payment_type == "partial":
        if amount_paid <= 0 or amount_paid >= total:
            raise ValidationError("Partial payment must be greater than 0 and less than the total.")
    else:  # zero
        amount_paid = Decimal("0")

    sale = Sale.objects.create(company=company, customer_name=customer_name)

    for item in items_data:
        product = item["product"]
        qty = int(item["quantity"])
        SaleItem.objects.create(sale=sale, product=product, quantity=qty, unit_price=product.selling_price)
        product.quantity = (product.quantity or 0) - qty
        product.save(update_fields=["quantity"])

    if amount_paid > 0:
        payment = SalePayment.objects.create(
            sale=sale,
            company=company,
            amount=amount_paid,
            payment_method=payment_method,
            reference=(sale_data.get("reference") or "").strip(),
            notes=(sale_data.get("notes") or "").strip(),
            created_by=user,
        )
    else:
        payment = None

    recalculate_sale_balance(sale)
    invoice = generate_invoice_for_sale(sale)
    receipt = generate_receipt_for_payment(payment) if payment else None

    return sale, invoice, receipt
