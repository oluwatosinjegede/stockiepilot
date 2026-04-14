from decimal import Decimal, InvalidOperation
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Category, Product


PLAN_LIMITS = {
    "free": 10,
    "basic": 50,
    "pro": None,
    "enterprise": None,
}


@login_required
def products_view(request):
    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "No company assigned.")
        return redirect("dashboard")

    if request.method == "POST":

        if request.user.role not in ["owner", "staff"]:
            messages.error(request, "Permission denied.")
            return redirect("products")

        action = request.POST.get("action")

        if action == "create_category":
            return _create_category(request)

        return _create_product(request, company)

    products = Product.objects.filter(company=company).select_related("category").order_by("-id")

    try:
        categories = Category.objects.all()
    except:
        categories = []

    analytics = _build_product_analytics(products)

    return render(
        request,
        "products.html",
        {
            "products": products,
            "categories": categories,
            **analytics,
        },
    )


# =========================
# CREATE PRODUCT (FIXED)
# =========================
def _create_product(request, company):

    # SAFE SUBSCRIPTION
    subscription = getattr(company, "subscription", None)

    if subscription and getattr(subscription, "plan", None):
        plan_name = subscription.plan.name.lower()
    else:
        plan_name = "free"

    limit = PLAN_LIMITS.get(plan_name, 10)

    if limit is not None and Product.objects.filter(company=company).count() >= limit:
        messages.error(request, "Plan limit reached.")
        return redirect("subscription")

    # FORM DATA
    name = request.POST.get("name", "").strip()
    price = request.POST.get("price")
    quantity = request.POST.get("quantity")
    category_id = request.POST.get("category")
    description = request.POST.get("description", "").strip()
    cost_price = request.POST.get("cost_price")
    sku_input = request.POST.get("sku")  # ✅ FIXED

    if not name or not price or not quantity:
        messages.error(request, "All fields are required.")
        return redirect("products")

    try:
        price = Decimal(price)
        quantity = int(quantity)
        cost_price = Decimal(cost_price) if cost_price else price
    except:
        messages.error(request, "Invalid numbers.")
        return redirect("products")

    category = Category.objects.filter(id=category_id).first() if category_id else None

    if Product.objects.filter(company=company, name__iexact=name).exists():
        messages.error(request, "Product already exists.")
        return redirect("products")

    # SKU
    sku = sku_input.strip() if sku_input else f"SKU-{company.id}-{uuid.uuid4().hex[:6]}"

    while Product.objects.filter(company=company, sku=sku).exists():
        sku = f"SKU-{company.id}-{uuid.uuid4().hex[:6]}"

    try:
        Product.objects.create(
            company=company,
            name=name,
            category=category,
            description=description,
            selling_price=price,
            cost_price=cost_price,
            quantity=quantity,
            sku=sku,
        )
    except IntegrityError:
        messages.error(request, "Error saving product.")
        return redirect("products")

    messages.success(request, "Product created.")
    return redirect("products")


# =========================
# CATEGORY
# =========================
def _create_category(request):
    name = request.POST.get("category_name", "").strip()

    if not name:
        messages.error(request, "Category name required.")
        return redirect("products")

    if Category.objects.filter(name__iexact=name).exists():
        messages.error(request, "Category exists.")
        return redirect("products")

    Category.objects.create(name=name)
    messages.success(request, "Category created.")
    return redirect("products")


# =========================
# SAFE ANALYTICS (NO ORM CRASH)
# =========================
def _build_product_analytics(products):

    total_products = products.count()
    low_stock_count = 0
    inventory_value = 0
    alerts = []

    for p in products:
        qty = p.quantity or 0
        cost = float(p.cost_price or 0)

        inventory_value += qty * cost

        if qty <= 5:
            low_stock_count += 1
            alerts.append(f"{p.name} is low in stock")

    return {
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "inventory_value": round(inventory_value, 2),
        "smart_alerts": alerts,
    }


# =========================
# AJAX
# =========================
@login_required
def get_product_price(request, product_id):

    company = request.user.company

    product = get_object_or_404(Product, id=product_id, company=company)

    return JsonResponse({
        "price": float(product.selling_price or 0),
        "stock": product.quantity or 0
    })


# =========================
# EDIT
# =========================
@login_required
def edit_product(request, product_id):

    company = request.user.company
    product = get_object_or_404(Product, id=product_id, company=company)

    if request.method == "POST":

        try:
            product.name = request.POST.get("name")
            product.selling_price = Decimal(request.POST.get("price"))
            product.quantity = int(request.POST.get("quantity"))
            product.cost_price = Decimal(request.POST.get("cost_price"))

            product.save()

            messages.success(request, "Updated.")

        except:
            messages.error(request, "Invalid data.")

        return redirect("products")

    return render(request, "products/edit.html", {"product": product})


# =========================
# DELETE
# =========================
@login_required
def delete_product(request, product_id):

    product = get_object_or_404(Product, id=product_id, company=request.user.company)

    product.delete()

    messages.success(request, "Deleted.")

    return redirect("products")