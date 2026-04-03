# apps/products/views.py

from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce

from apps.subscriptions.views import Plans
from .models import Product, Category




# =========================
# PLAN LIMITS
# =========================
PLAN_LIMITS = {
    Plans.FREE: 10,
    Plans.BASIC: 50,
    Plans.PRO: None,
    Plans.ENTERPRISE: None,
}


# =========================
# PRODUCTS VIEW (ANALYTICS READY)
# =========================
@login_required
def products_view(request):
    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "User is not assigned to a company.")
        return redirect("dashboard")

    # =========================
    # CREATE PRODUCT
    # =========================
    if request.method == "POST":

        # PLAN LIMIT CHECK
        limit = PLAN_LIMITS.get(company.subscription_plan)

        if limit is not None:
            current_count = Product.objects.filter(company=company).count()

            if current_count >= limit:
                messages.error(
                    request,
                    "You have reached your product limit. Upgrade your plan."
                )
                return redirect("subscription")

        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        quantity = request.POST.get("quantity")
        category_id = request.POST.get("category")

        # VALIDATION
        if not name or not price or not quantity:
            messages.error(request, "All fields are required.")
            return redirect("products")

        try:
            price = Decimal(price)
            quantity = int(quantity)

            if price <= 0 or quantity < 0:
                raise ValueError

        except (InvalidOperation, ValueError):
            messages.error(request, "Invalid price or quantity.")
            return redirect("products")

        # CATEGORY SAFE FETCH
        category = None
        if category_id:
            category = Category.objects.filter(id=category_id).first()

        # DUPLICATE CHECK
        if Product.objects.filter(company=company, name__iexact=name).exists():
            messages.error(request, "Product already exists.")
            return redirect("products")

        # CREATE
        Product.objects.create(
            company=company,
            name=name,
            category=category,
            selling_price=price,
            cost_price=price,  # fallback (important)
            quantity=quantity,
            sku=f"SKU-{company.id}-{name[:5].upper()}"
        )

        messages.success(request, "Product created successfully.")
        return redirect("products")

    # =========================
    # FETCH PRODUCTS
    # =========================
    products = (
        Product.objects
        .filter(company=company)
        .select_related("category")
        .order_by("-id")
    )

    categories = Category.objects.all()

    # =========================
    # ANALYTICS (NEW 🔥)
    # =========================

    # LOW STOCK COUNT
    low_stock_count = products.filter(quantity__lte=5).count()

    # INVENTORY VALUE (SAFE)
    inventory_value = products.aggregate(
        total=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("quantity") * Coalesce(F("cost_price"), 0),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            ),
            0
        )
    )["total"]

    # TOTAL PRODUCTS
    total_products = products.count()

    # =========================
    # CONTEXT
    # =========================
    context = {
        "products": products,
        "categories": categories,

        # PLAN INFO
        "plan": company.subscription_plan,
        "limit": PLAN_LIMITS.get(company.subscription_plan),

        # ANALYTICS 🔥
        "low_stock_count": low_stock_count,
        "inventory_value": float(inventory_value or 0),
        "total_products": total_products,
    }

    return render(request, "products.html", context)


# =========================
# AJAX: PRODUCT PRICE
# =========================
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