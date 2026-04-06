from decimal import Decimal, InvalidOperation
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.db import IntegrityError

from .models import Product, Category


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

    # ================= CREATE =================
    if request.method == "POST":

        if request.user.role != "owner":
            messages.error(request, "Only admins can manage products.")
            return redirect("products")

        #  SAFE SUBSCRIPTION
        subscription = getattr(company, "subscription", None)

        if subscription and getattr(subscription, "plan", None):
            plan_name = subscription.plan.name.lower()
        else:
            plan_name = "free"

        limit = PLAN_LIMITS.get(plan_name, 10)

        if limit is not None:
            if Product.objects.filter(company=company).count() >= limit:
                messages.error(request, "Plan limit reached. Upgrade required.")
                return redirect("subscription")

        # ================= FORM =================
        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        quantity = request.POST.get("quantity")
        category_id = request.POST.get("category")
        description = request.POST.get("description", "")
        cost_price = request.POST.get("cost_price")
        sku_input = request.POST.get("sku")

        if not name or not price or not quantity:
            messages.error(request, "Name, price and quantity are required.")
            return redirect("products")

        try:
            price = Decimal(price)
            quantity = int(quantity)
            cost_price = Decimal(cost_price) if cost_price else price

        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid numeric values.")
            return redirect("products")

        #  SAFE CATEGORY
        try:
            category = Category.objects.filter(id=category_id).first() if category_id else None
        except:
            category = None

        if Product.objects.filter(company=company, name__iexact=name).exists():
            messages.error(request, "Product already exists.")
            return redirect("products")

        # ================= SKU =================
        sku = sku_input.strip() if sku_input else f"SKU-{company.id}-{uuid.uuid4().hex[:8].upper()}"

        while Product.objects.filter(company=company, sku=sku).exists():
            sku = f"SKU-{company.id}-{uuid.uuid4().hex[:8].upper()}"

        try:
            Product.objects.create(
                company=company,
                name=name,
                category=category,
                description=description,
                selling_price=price,
                cost_price=cost_price,
                quantity=quantity,
                sku=sku
            )
        except IntegrityError:
            messages.error(request, "SKU conflict. Try again.")
            return redirect("products")

        messages.success(request, "Product created successfully.")
        return redirect("products")

    # ================= FETCH =================
    products = Product.objects.filter(company=company).order_by("-id")

    #  SAFE CATEGORY FETCH
    try:
        categories = Category.objects.all()
    except:
        categories = []

    # ================= SAFE ANALYTICS =================
    low_stock_count = 0
    inventory_value = 0
    smart_alerts = []

    for p in products:
        qty = p.quantity or 0
        cost = float(p.cost_price or 0)

        if qty <= 5:
            low_stock_count += 1
            smart_alerts.append(f"{p.name} is low in stock")

        inventory_value += qty * cost

    return render(request, "products.html", {
        "products": products,
        "categories": categories,
        "low_stock_count": low_stock_count,
        "inventory_value": round(inventory_value, 2),
        "total_products": products.count(),
        "smart_alerts": smart_alerts,
    })


# ================= AJAX =================
@login_required
def get_product_price(request, product_id):

    company = getattr(request.user, "company", None)

    if not company:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    product = get_object_or_404(Product, id=product_id, company=company)

    return JsonResponse({
        "price": float(product.selling_price or 0),
        "stock": product.quantity or 0
    })