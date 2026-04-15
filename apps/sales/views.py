from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from apps.products.models import Product
from .models import Sale, SaleItem
from .services.analytics import build_sales_analytics


# =========================
# CREATE SALE (POS READY)
# =========================
@login_required
def create_sale(request):

    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")

    if request.method == "POST":

        product_ids = request.POST.getlist("product[]") or [request.POST.get("product")]
        quantities = request.POST.getlist("quantity[]") or [request.POST.get("quantity")]

        payment_status = request.POST.get("payment_status", "paid")
        customer_name = (request.POST.get("customer_name") or "").strip()
        amount_paid_raw = request.POST.get("amount_paid")

        # ================= VALIDATION =================
        if not product_ids or not quantities:
            messages.error(request, "No products selected.")
            return redirect("create_sale")

        if payment_status not in ["paid", "partial"]:
            messages.error(request, "Invalid payment option.")
            return redirect("create_sale")

        total_sale_amount = Decimal("0")
        items = []

        # ================= PROCESS ITEMS =================
        for i in range(len(product_ids)):

            try:
                product = get_object_or_404(Product, id=product_ids[i], company=company)
                qty = int(quantities[i])

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

    sale_items = (
        SaleItem.objects
        .filter(sale__company=company)
        .select_related("sale", "product")
        .order_by("-sale__created_at", "-id")
    )


    # ================= SAFE ANALYTICS =================
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


# =========================
# SALES LIST
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