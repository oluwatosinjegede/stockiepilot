from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from apps.products.models import Product
from .models import Sale, SaleItem

from .services.analytics import build_sales_analytics

#from django.db.models import Sum

# =========================
# CREATE SALE
# =========================

@login_required
def create_sale(request):
    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")

    if request.method == "POST":
        product_id = request.POST.get("product")
        quantity = request.POST.get("quantity")
        payment_status = request.POST.get("payment_status", "paid")
        customer_name = (request.POST.get("customer_name") or "").strip()
        amount_paid_raw = request.POST.get("amount_paid")

        # Validation
        if not product_id or not quantity:
            messages.error(request, "All fields are required.")
            return redirect("create_sale")

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Invalid quantity.")
            return redirect("create_sale")

        #  Ensure product belongs to company
        product = get_object_or_404(Product, id=product_id, company=company)
        sale_total = Decimal(product.selling_price) * quantity

        #  Stock validation (signals will deduct)
        if quantity > product.quantity:
            messages.error(request, "Not enough stock.")
            return redirect("create_sale")
        
        if payment_status not in {"paid", "partial"}:
            messages.error(request, "Invalid payment option selected.")
            return redirect("create_sale")

        if payment_status == "paid":
            amount_paid = sale_total
            balance = Decimal("0")
        else:
            if not customer_name:
                messages.error(request, "Customer name is required for part payment.")
                return redirect("create_sale")

            try:
                amount_paid = Decimal(amount_paid_raw or "0")
            except Exception:
                messages.error(request, "Invalid amount paid.")
                return redirect("create_sale")

            if amount_paid < 0:
                messages.error(request, "Amount paid cannot be negative.")
                return redirect("create_sale")

            if amount_paid >= sale_total:
                messages.error(request, "Part payment must be less than total sale amount.")
                return redirect("create_sale")

            balance = sale_total - amount_paid

        #  Atomic transaction
        with transaction.atomic():

            sale = Sale.objects.create(
                company=company,
                payment_status=payment_status,
                customer_name=customer_name if payment_status == "partial" else "",
                amount_paid=amount_paid,
                balance=balance,
                status="pending" if balance > 0 else "completed",
            )

            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                unit_price=product.selling_price,
                total_price=sale_total
            )

            #  REMOVED stock deduction (handled by signals)

        if balance > 0:
            messages.warning(
                request,
                f"Sale saved with debit. {customer_name} owes ₦{balance}."
            )
        else:
            messages.success(request, "Sale created successfully.")
        return redirect("sales")

    # GET request
    products = Product.objects.filter(company=company).order_by("name")

    return render(request, "sales/create_sale.html", {
        "products": products
    })


# =========================
# SALES LIST (MAIN)
# =========================

@login_required
def sales_view(request):
    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")

    sales = (
        SaleItem.objects
        .filter(sale__company=company)
        .select_related('product', 'sale')  #  optimized join
        .order_by("-sale__created_at")
    )

    if request.user.role not in ["staff", "user"]:
        return redirect("dashboard")
    
    analytics = build_sales_analytics(sales)

    if balance > 0:
            messages.warning(
                request,
                f"Sale saved with debit. {customer_name} owes ₦{balance}."
            )
        else:
            messages.success(request, "Sale created successfully.")

    return render(request, "sales.html", {
        "sales": sales,
        "metrics": analytics["metrics"],
        "charts": analytics["charts"],
        "insights": analytics["insights"],
        "debt_sales": debt_sales,
    })
    

# =========================
# SALES LIST (ALT VIEW)
# =========================

@login_required
def sales_list(request):
    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")

    sales = (
        Sale.objects
        .filter(company=company)
        .prefetch_related('items__product')
        .order_by("-created_at")
    )

    return render(request, "sales/list.html", {
        "sales": sales
    })