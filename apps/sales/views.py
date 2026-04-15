from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from apps.products.models import Product
from .models import Sale, SaleItem
from .services.analytics import build_sales_analytics


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

        # ================= VALIDATION =================
        if not product_id or not quantity:
            messages.error(request, "All fields are required.")
            return redirect("create_sale")

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except:
            messages.error(request, "Invalid quantity.")
            return redirect("create_sale")

        product = get_object_or_404(Product, id=product_id, company=company)

        if quantity > product.quantity:
            messages.error(request, "Not enough stock.")
            return redirect("create_sale")

        sale_total = Decimal(product.selling_price) * quantity

        # ================= PAYMENT =================
        if payment_status not in ["paid", "partial"]:
            messages.error(request, "Invalid payment option.")
            return redirect("create_sale")

        if payment_status == "paid":
            amount_paid = sale_total
            balance = Decimal("0")

        else:
            if not customer_name:
                messages.error(request, "Customer name required.")
                return redirect("create_sale")

            try:
                amount_paid = Decimal(amount_paid_raw or "0")
            except:
                messages.error(request, "Invalid amount.")
                return redirect("create_sale")

            if amount_paid <= 0 or amount_paid >= sale_total:
                messages.error(request, "Invalid part payment.")
                return redirect("create_sale")

            balance = sale_total - amount_paid

        # ================= SAVE =================
        try:
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
                )

        except Exception as e:
            messages.error(request, str(e))
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

    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")

    #  CORRECT QUERY
    sales = (
        Sale.objects
        .filter(company=company)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    #  ANALYTICS
    analytics = build_sales_analytics(sales)

    #  DEBT SALES
    debt_sales = sales.filter(balance__gt=0)

    return render(request, "sales.html", {
        "sales": sales,
        "metrics": analytics.get("metrics", {}),
        "charts": analytics.get("charts", {}),
        "insights": analytics.get("insights", []),
        "debt_sales": debt_sales,
    })


# =========================
# SALES LIST (OPTIONAL VIEW)
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
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    return render(request, "sales/list.html", {
        "sales": sales
    })