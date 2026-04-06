from decimal import Decimal, InvalidOperation
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.db import IntegrityError
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce

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

        # 🔒 RBAC
        if request.user.role != "staff":
            messages.error(request, "Only staff can manage products.")
            return redirect("products")

        # PLAN LIMIT
        plan = getattr(company, "subscription_plan", "free")
        limit = PLAN_LIMITS.get(plan, 10)

        if limit is not None:
            if Product.objects.filter(company=company).count() >= limit:
                messages.error(request, "Upgrade your plan.")
                return redirect("subscription")

        # FORM DATA
        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        quantity = request.POST.get("quantity")
        category_id = request.POST.get("category")
        description = request.POST.get("description", "")
        cost_price = request.POST.get("cost_price")
        sku_input = request.POST.get("sku")

        # VALIDATION
        if not name or not price or not quantity:
            messages.error(request, "Name, price and quantity are required.")
            return redirect("products")

        try:
            price = Decimal(price)
            quantity = int(quantity)
            cost_price = Decimal(cost_price) if cost_price else price

            if price <= 0 or quantity < 0 or cost_price < 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid numeric values.")
            return redirect("products")

        # CATEGORY SAFE FETCH
        category = None
        if category_id:
            category = Category.objects.filter(id=category_id).first()

        # DUPLICATE NAME CHECK (PER COMPANY)
        if Product.objects.filter(company=company, name__iexact=name).exists():
            messages.error(request, "Product already exists.")
            return redirect("products")

        # ================= SAFE SKU =================
        if sku_input:
            sku = sku_input.strip()
        else:
            sku = f"SKU-{company.id}-{uuid.uuid4().hex[:8].upper()}"

        # ENSURE SKU UNIQUE
        while Product.objects.filter(sku=sku).exists():
            sku = f"SKU-{company.id}-{uuid.uuid4().hex[:8].upper()}"

        # ================= CREATE =================
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
    products = (
        Product.objects
        .filter(company=company)
        .select_related("category")
        .order_by("-id")
    )

    categories = Category.objects.all()

    # ================= ANALYTICS =================
    low_stock_count = products.filter(quantity__lte=5).count()

    inventory_value = products.aggregate(
        total=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("quantity") * Coalesce(F("cost_price"), Value(0)),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            ),
            Value(0)
        )
    )["total"] or 0

    # ================= SMART ALERTS =================
    smart_alerts = [
        f"{p.name} is low in stock"
        for p in products if p.quantity <= 5
    ]

    return render(request, "products.html", {
        "products": products,
        "categories": categories,
        "low_stock_count": low_stock_count,
        "inventory_value": float(inventory_value),
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
        "price": float(product.selling_price),
        "stock": product.quantity
    })