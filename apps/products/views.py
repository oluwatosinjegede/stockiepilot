from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce

from .models import Product, Category

# 🔥 SAFE fallback (NO circular import)
PLAN_LIMITS = {
    "free": 10,
    "basic": 50,
    "pro": None,
    "enterprise": None,
}


# =========================
# PRODUCTS VIEW (SAFE)
# =========================
@login_required
def products_view(request):
    company = getattr(request.user, "company", None)

    if not company:
        messages.error(request, "No company assigned.")
        return redirect("dashboard")

    # ================= CREATE =================
    if request.method == "POST":

        limit = PLAN_LIMITS.get(company.subscription_plan)

        if limit is not None:
            if Product.objects.filter(company=company).count() >= limit:
                messages.error(request, "Upgrade your plan.")
                return redirect("subscription")

        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        quantity = request.POST.get("quantity")
        category_id = request.POST.get("category")

        if not name or not price or not quantity:
            messages.error(request, "All fields required.")
            return redirect("products")

        try:
            price = Decimal(price)
            quantity = int(quantity)

            if price <= 0 or quantity < 0:
                raise ValueError

        except Exception:
            messages.error(request, "Invalid input.")
            return redirect("products")

        category = Category.objects.filter(id=category_id).first() if category_id else None

        if Product.objects.filter(company=company, name__iexact=name).exists():
            messages.error(request, "Product already exists.")
            return redirect("products")

        Product.objects.create(
            company=company,
            name=name,
            category=category,
            selling_price=price,
            cost_price=price or Decimal("0.00"),
            quantity=quantity,
            sku=f"SKU-{company.id}-{name[:5].upper()}"
        )

        messages.success(request, "Product created.")
        return redirect("products")

    # ================= FETCH =================
    products = (
        Product.objects
        .filter(company=company)
        .select_related("category")
        .order_by("-id")
    )

    categories = Category.objects.all()

    # ================= SAFE ANALYTICS =================
    low_stock_count = products.filter(quantity__lte=5).count()

    try:
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
    except Exception:
        inventory_value = 0

    # 🔥 SAFE ALERTS (NO CRASH)
    smart_alerts = []
    for p in products:
        if p.quantity <= 5:
            smart_alerts.append(f"{p.name} is low in stock")

    return render(request, "products.html", {
        "products": products,
        "categories": categories,
        "low_stock_count": low_stock_count,
        "inventory_value": float(inventory_value),
        "total_products": products.count(),
        "smart_alerts": smart_alerts,
    })


# =========================
# AJAX
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