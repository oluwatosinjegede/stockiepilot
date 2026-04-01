from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from apps.subscriptions.views import Plans  # use central plan config
from .models import Product, Category


# =========================
# PLAN LIMITS (SaaS CONTROL)
# =========================
PLAN_LIMITS = {
    Plans.FREE: 10,
    Plans.BASIC: 50,
    Plans.PRO: None,
    Plans.ENTERPRISE: None,
}


# =========================
# PRODUCTS VIEW
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

        # 🔥 ENFORCE PLAN LIMIT FIRST
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

        # =========================
        # VALIDATION
        # =========================
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

        # =========================
        # CATEGORY (SAFE FETCH)
        # =========================
        category = None
        if category_id:
            category = Category.objects.filter(id=category_id).first()

        # =========================
        # DUPLICATE CHECK
        # =========================
        if Product.objects.filter(company=company, name__iexact=name).exists():
            messages.error(request, "Product already exists.")
            return redirect("products")

        # =========================
        # CREATE PRODUCT
        # =========================
        Product.objects.create(
            company=company,
            name=name,
            category=category,
            selling_price=price,
            quantity=quantity
        )

        messages.success(request, "Product created successfully.")
        return redirect("products")

    # =========================
    # FETCH PRODUCTS
    # =========================
    products = (
        Product.objects
        .filter(company=company)
        .select_related("category")   # performance
        .order_by("-id")
    )

    categories = Category.objects.all()

    return render(request, "products.html", {
        "products": products,
        "categories": categories,
        "plan": company.subscription_plan,  # 🔥 useful in UI
        "limit": PLAN_LIMITS.get(company.subscription_plan),
    })


# =========================
# AJAX: GET PRODUCT PRICE
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