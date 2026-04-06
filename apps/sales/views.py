from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from apps.products.models import Product
from .models import Sale, SaleItem

from django.db.models import Sum

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

        #  Stock validation (signals will deduct)
        if quantity > product.quantity:
            messages.error(request, "Not enough stock.")
            return redirect("create_sale")

        #  Atomic transaction
        with transaction.atomic():

            sale = Sale.objects.create(company=company)

            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=quantity,
                unit_price=product.selling_price,
                total_price=Decimal(product.selling_price) * quantity
            )

            #  REMOVED stock deduction (handled by signals)

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

    return render(request, "sales.html", {
        "sales": sales
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