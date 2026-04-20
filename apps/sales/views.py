from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.products.models import Product
from apps.subscriptions.services import can_access_analytics, is_subscription_active

from .models import PaymentReceipt, Sale, SaleInvoice, SaleItem
from .services import create_sale_with_payment, record_sale_payment
from .services.analytics import build_sales_analytics



def _redirect_affiliate_if_needed(request):
    if request.user.is_affiliate:
        messages.error(request, "Affiliate accounts cannot access Sales.")
        return redirect("affiliate_dashboard")
    return None

def _require_sales_role(request):
    if request.user.role not in ["owner", "staff"]:
        messages.error(request, "Permission denied.")
        return False
    return True

@login_required
def create_sale(request):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")
    
    if not _require_sales_role(request):
        return redirect("sales")
    
    if not is_subscription_active(company):
        messages.error(request, "Your subscription is inactive or expired. Upgrade required.")
        return redirect("subscription")

    if request.method == "POST":
            product_ids = [v for v in request.POST.getlist("product[]") if v]
            quantities = [v for v in request.POST.getlist("quantity[]") if v]
            if not product_ids or not quantities or len(product_ids) != len(quantities):
                messages.error(request, "Each selected product must have a quantity.")
                return redirect("create_sale")

            items = []

            try:
                for product_id, quantity in zip(product_ids, quantities):
                    product = get_object_or_404(Product, id=product_id, company=company)
                    qty = int(quantity)
                    items.append({"product": product, "quantity": qty})

                    sale, invoice, receipt = create_sale_with_payment(
                company=company,
                user=request.user,
                sale_data=request.POST,
                items_data=items,
            )
            except (ValidationError, ValueError) as exc:
                messages.error(request, str(exc))
                return redirect("create_sale")
            except Exception as exc:
                messages.error(request, f"Error creating sale: {exc}")

                
            return redirect("create_sale")

    if sale.balance > 0:
        messages.warning(request, f"Sale created. Outstanding balance: ₦{sale.balance}")
    else:
        messages.success(request, "Sale completed successfully")
        if receipt:
            return redirect("payment_receipt_detail", receipt_id=receipt.id)
        return redirect("sale_invoice_detail", sale_id=sale.id)

    products = Product.objects.filter(company=company).order_by("name")

    return render(request, "sales/create_sale.html", {"products": products})

@login_required
def sales_view(request):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

    company = getattr(request.user, "company", None)
    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")
    if not is_subscription_active(company):
        messages.error(request, "Your subscription is inactive or expired. Upgrade required.")
        return redirect("subscription")

    sales = Sale.objects.filter(company=company).prefetch_related("items__product", "invoice").order_by("-created_at")
    sale_items = SaleItem.objects.filter(sale__company=company).select_related("sale", "product").order_by("-sale__created_at", "-id")

    analytics = {"metrics": {}, "charts": {}, "insights": []}
    if can_access_analytics(company):
        try:
            analytics = build_sales_analytics(sale_items)
        except Exception:
            analytics = {
                "metrics": {"revenue_30d": 0, "units_30d": 0, "estimated_profit_30d": 0, "average_order_value": 0},
                "charts": {"dates": "[]", "revenue": "[]", "product_labels": "[]", "product_values": "[]", "pie_values": "[]"},
                "insights": [],
            }

    debt_sales = sales.filter(balance__gt=0)
    return render(
        request,
        "sales.html",
        {
            "sales": sale_items,
            "metrics": analytics.get("metrics", {}),
            "charts": analytics.get("charts", {}),
            "insights": analytics.get("insights", []),
            "debt_sales": debt_sales,
        },
    )

@login_required
def update_sale_payment(request, sale_id):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect
    if request.method != "POST":
        return redirect("sales")

    company = getattr(request.user, "company", None)
    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")
    if not _require_sales_role(request):
        return redirect("sales")

    sale = get_object_or_404(Sale, id=sale_id, company=company)
    if sale.balance <= 0:
        messages.info(request, "This sale has already been fully settled.")
        return redirect("sales")

    try:
        payment_amount = Decimal(request.POST.get("payment_amount") or "0")
    except (InvalidOperation, TypeError):
        messages.error(request, "Enter a valid payment amount.")
        return redirect("sales")

    try:
        _payment, receipt = record_sale_payment(
            sale=sale,
            amount=payment_amount,
            payment_method=request.POST.get("payment_method", ""),
            user=request.user,
            reference=request.POST.get("reference", ""),
            notes=request.POST.get("notes", ""),
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("sales")

    if sale.balance == 0:
        messages.success(request, "Payment received and sale marked as completed.")
    else:
        messages.success(request, "Payment received and pending sale updated.")

    return redirect("payment_receipt_detail", receipt_id=receipt.id)

@login_required
def sale_invoice_detail(request, sale_id):
    company = getattr(request.user, "company", None)
    sale = get_object_or_404(Sale, id=sale_id, company=company)
    invoice = get_object_or_404(SaleInvoice, sale=sale, company=company)
    return render(request, "sales/invoice_detail.html", {"sale": sale, "invoice": invoice})

@login_required
def payment_receipt_detail(request, receipt_id):
    company = getattr(request.user, "company", None)
    receipt = get_object_or_404(
        PaymentReceipt.objects.select_related("sale", "invoice", "sale_payment", "company", "generated_by"),
        id=receipt_id,
        company=company,
    )

    return render(request, "sales/receipt_detail.html", {"receipt": receipt, "sale": receipt.sale})