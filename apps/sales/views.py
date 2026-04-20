from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from apps.products.models import Product
from .models import Sale, SaleItem
from .services.analytics import build_sales_analytics
from apps.subscriptions.services import can_access_analytics, is_subscription_active

def _redirect_affiliate_if_needed(request):
    if request.user.is_affiliate:
        messages.error(request, "Affiliate accounts cannot access Sales.")
        return redirect("affiliate_dashboard")
    return None

# =========================
# CREATE SALE (POS READY)
# =========================
@login_required
def create_sale(request):
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

    if request.method == "POST":

        product_ids = [value for value in request.POST.getlist("product[]") if value]
        quantities = [value for value in request.POST.getlist("quantity[]") if value]

        payment_status = request.POST.get("payment_status", "paid")
        customer_name = (request.POST.get("customer_name") or "").strip()
        amount_paid_raw = request.POST.get("amount_paid")

        # ================= VALIDATION =================
        if not product_ids or not quantities:
            messages.error(request, "No products selected.")
            return redirect("create_sale")
        
        if len(product_ids) != len(quantities):
            messages.error(request, "Each selected product must have a quantity.")
            return redirect("create_sale")

        if payment_status not in ["paid", "partial"]:
            messages.error(request, "Invalid payment option.")
            return redirect("create_sale")

        total_sale_amount = Decimal("0")
        items = []

        # ================= PROCESS ITEMS =================
        for product_id, quantity in zip(product_ids, quantities):

            try:
                product = get_object_or_404(Product, id=product_id, company=company)
                qty = int(quantity)

                if qty <= 0:
                    raise ValueError

            except (ValueError, TypeError):
                messages.error(request, "Invalid product or quantity.")
                return redirect("create_sale")

            if qty > product.quantity:
                messages.error(request, f"Not enough stock for {product.name}")
                return redirect("create_sale")

            item_total = Decimal(product.selling_price) * qty

            items.append({
                "product": product,
                "quantity": qty,
                "unit_price": product.selling_price,
                "total": item_total
            })

            total_sale_amount += item_total

        # ================= PAYMENT =================
        if payment_status == "paid":
            amount_paid = total_sale_amount
            balance = Decimal("0")

        else:
            if not customer_name:
                messages.error(request, "Customer name required.")
                return redirect("create_sale")

            try:
                amount_paid = Decimal(amount_paid_raw or "0")
            except (InvalidOperation, TypeError):
                messages.error(request, "Invalid amount.")
                return redirect("create_sale")

            if amount_paid <= 0 or amount_paid >= total_sale_amount:
                messages.error(request, "Invalid part payment.")
                return redirect("create_sale")

            balance = total_sale_amount - amount_paid

        # ================= SAVE =================
        try:
            with transaction.atomic():

                sale = Sale.objects.create(
                    company=company,
                    total_amount=total_sale_amount,
                    payment_status=payment_status,
                    customer_name=customer_name if payment_status == "partial" else "",
                    amount_paid=amount_paid,
                    balance=balance,
                    status="pending" if balance > 0 else "completed",
                )

                for item in items:
                    SaleItem.objects.create(
                        sale=sale,
                        product=item["product"],
                        quantity=item["quantity"],
                        unit_price=item["unit_price"],
                    )

        except Exception as e:
            messages.error(request, f"Error creating sale: {str(e)}")
            return redirect("create_sale")

        # ================= FEEDBACK =================
        if balance > 0:
            messages.warning(request, f"{customer_name} owes ₦{balance}")
        else:
            messages.success(request, "Sale completed successfully")

        return redirect("sales")

    products = Product.objects.filter(company=company).order_by("name")

    return render(request, "sales/create_sale.html", {
        "products": products
    })


# =========================
# SALES DASHBOARD
# =========================
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

    sales = (
        Sale.objects
        .filter(company=company)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    sale_items = (
        SaleItem.objects
        .filter(sale__company=company)
        .select_related("sale", "product")
        .order_by("-sale__created_at", "-id")
    )


    # ================= SAFE ANALYTICS =================
    analytics = {
        "metrics": {},
        "charts": {},
        "insights": [],
    }
    if can_access_analytics(company):
        try:
            analytics = build_sales_analytics(sale_items)
        except Exception:
            analytics = {
                "metrics": {
                    "revenue_30d": 0,
                    "units_30d": 0,
                    "estimated_profit_30d": 0,
                    "average_order_value": 0,
                },
                "charts": {
                    "dates": "[]",
                    "revenue": "[]",
                    "product_labels": "[]",
                    "product_values": "[]",
                    "pie_values": "[]",
                },
                "insights": []
            }

    debt_sales = sales.filter(balance__gt=0)

    return render(request, "sales.html", {
        "sales": sale_items,
        "metrics": analytics.get("metrics", {}),
        "charts": analytics.get("charts", {}),
        "insights": analytics.get("insights", []),
        "debt_sales": debt_sales,
    })

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

    sale = get_object_or_404(Sale, id=sale_id, company=company)

    if sale.balance <= 0:
        messages.info(request, "This sale has already been fully settled.")
        return redirect("sales")

    amount_raw = request.POST.get("payment_amount")

    try:
        payment_amount = Decimal(amount_raw or "0")
    except (InvalidOperation, TypeError):
        messages.error(request, "Enter a valid payment amount.")
        return redirect("sales")

    if payment_amount <= 0:
        messages.error(request, "Payment amount must be greater than zero.")
        return redirect("sales")

    with transaction.atomic():
        locked_sale = Sale.objects.select_for_update().get(id=sale.id)

        if payment_amount > locked_sale.balance:
            messages.error(
                request,
                f"Payment cannot exceed outstanding balance of ₦{locked_sale.balance}.",
            )
            return redirect("sales")

        locked_sale.amount_paid += payment_amount
        locked_sale.balance -= payment_amount
        locked_sale.status = "completed" if locked_sale.balance == 0 else "pending"
        locked_sale.payment_status = "paid" if locked_sale.balance == 0 else "partial"
        locked_sale.save(update_fields=["amount_paid", "balance", "status", "payment_status"])
        remaining_balance = locked_sale.balance

    if remaining_balance == 0:
        messages.success(request, "Payment received and sale marked as completed.")
    else:
        messages.success(request, "Payment received and pending sale updated.")

    return redirect("sales")


# =========================
# SALES LIST
# =========================
@login_required
def sales_list(request):
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

    sales = (
        Sale.objects
        .filter(company=company)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    return render(request, "sales/list.html", {
        "sales": sales
    })