from decimal import Decimal, InvalidOperation
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce
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

        action = request.POST.get("action", "create_product")

        if action == "create_category":
            return _create_category(request)

        return _create_product(request, company)

    products = Product.objects.filter(company=company).select_related("category").order_by("-id")
    categories = Category.objects.all()

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

def _create_product(request, company):
    subscription = getattr(company, "subscription", None)

    if subscription and getattr(subscription, "plan", None):
        plan_name = subscription.plan.name.lower()
    else:
        plan_name = "free"

        limit = PLAN_LIMITS.get(plan_name, 10)

        if limit is not None and Product.objects.filter(company=company).count() >= limit:
            messages.error(request, "Plan limit reached. Upgrade required.")
            return redirect("subscription")

        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        quantity = request.POST.get("quantity")
        category_id = request.POST.get("category")
        description = request.POST.get("description", "").strip()
        cost_price = request.POST.get("cost_price")
        ku_input = request.POST.get("sku")

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

    category = None
    if category_id:
        category = Category.objects.filter(id=category_id).first()

        if Product.objects.filter(company=company, name__iexact=name).exists():
            messages.error(request, "Product already exists.")
            return redirect("products")

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
            sku=sku,
        )
    except IntegrityError:
        messages.error(request, "SKU conflict. Try again.")
        return redirect("products")

    messages.success(request, "Product created successfully.")
    return redirect("products")


def _create_category(request):
    name = request.POST.get("category_name", "").strip()
    description = request.POST.get("category_description", "").strip()

    if not name:
        messages.error(request, "Category name is required.")
        return redirect("products")

    if Category.objects.filter(name__iexact=name).exists():
        messages.error(request, "Category already exists.")
        return redirect("products")

    Category.objects.create(name=name, description=description)
    messages.success(request, "Category created successfully.")
    return redirect("products")

def _build_product_analytics(products_queryset):
    totals = products_queryset.aggregate(
        total_products=Count("id"),
        low_stock_count=Count("id", filter=Q(quantity__lte=5)),
        inventory_value=Coalesce(Sum(F("quantity") * F("cost_price")), 0),
    )

    low_stock_products = products_queryset.filter(quantity__lte=5).values_list("name", flat=True)

    return {
        "total_products": totals["total_products"],
        "low_stock_count": totals["low_stock_count"],
        "inventory_value": totals["inventory_value"],
        "smart_alerts": [f"{name} is low in stock" for name in low_stock_products],
    }

@login_required
def get_product_price(request, product_id):

    company = getattr(request.user, "company", None)

    if not company:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    product = get_object_or_404(Product, id=product_id, company=company)

    return JsonResponse({"price": float(product.selling_price or 0), "stock": product.quantity or 0})

@login_required
def edit_product(request, product_id):

    company = getattr(request.user, "company", None)

    product = get_object_or_404(Product, id=product_id, company=company)

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        quantity = request.POST.get("quantity")
        cost_price = request.POST.get("cost_price")

        try:
            product.name = name
            product.selling_price = Decimal(price)
            product.quantity = int(quantity)
            product.cost_price = Decimal(cost_price) if cost_price else product.selling_price

            product.save()

            messages.success(request, "Product updated successfully.")

        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid data.")

        return redirect("products")

    return render(request, "products/edit.html", {"product": product})


@login_required
def delete_product(request, product_id):

    company = getattr(request.user, "company", None)

    product = get_object_or_404(Product, id=product_id, company=company)

    product.delete()

    messages.success(request, "Product deleted.")
    
    return redirect("products")