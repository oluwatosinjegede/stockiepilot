import json
from decimal import Decimal, InvalidOperation
import uuid
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now, timedelta

from .models import Category, Product
from apps.sales.models import SaleItem
from apps.subscriptions.services import can_create_product


def _redirect_affiliate_if_needed(request):
    if request.user.is_affiliate:
        messages.error(request, "Affiliate accounts cannot access Products.")
        return redirect("affiliate_dashboard")
    return None

@login_required
def products_view(request):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect
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
        
        if action == "add_stock":
            return _add_stock(request, company)

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
    
    if not can_create_product(company):
        messages.error(
            request,
            "Product limit reached for your current plan or your subscription is inactive. Upgrade to continue.",
        )
        return redirect("subscription")

    # FORM DATA
    name = request.POST.get("name", "").strip()
    price = request.POST.get("price")
    quantity = request.POST.get("quantity")
    category_id = request.POST.get("category")
    description = request.POST.get("description", "").strip()
    cost_price = request.POST.get("cost_price")
    sku_input = request.POST.get("sku")  # FIXED

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

    existing_product = Product.objects.filter(company=company, name__iexact=name).first()
    if existing_product:
        existing_product.quantity = (existing_product.quantity or 0) + quantity
        existing_product.selling_price = price
        existing_product.cost_price = cost_price
        if category:
            existing_product.category = category
        if description:
            existing_product.description = description
        existing_product.save(
            update_fields=[
                "quantity",
                "selling_price",
                "cost_price",
                "category",
                "description",
            ]
        )
        messages.success(
            request,
            f"Added {quantity} unit(s) to {existing_product.name}. Current stock: {existing_product.quantity}.",
        )
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

def _add_stock(request, company):
    product_id = request.POST.get("product_id")
    quantity_input = request.POST.get("stock_quantity", "").strip()

    if not product_id:
        messages.error(request, "Product is required.")
        return redirect("products")

    try:
        quantity_to_add = int(quantity_input)
        if quantity_to_add <= 0:
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "Enter a valid stock quantity greater than 0.")
        return redirect("products")

    product = Product.objects.filter(id=product_id, company=company).first()
    if not product:
        messages.error(request, "Product not found.")
        return redirect("products")

    product.quantity = (product.quantity or 0) + quantity_to_add
    product.save(update_fields=["quantity"])

    messages.success(
        request,
        f"Added {quantity_to_add} unit(s) to {product.name}. Current stock: {product.quantity}.",
    )
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
    out_of_stock_count = 0
    total_stock_units = 0
    avg_stock_per_product = 0
    top_products = []
    date_from = now() - timedelta(days=30)
    stock_trend_map = defaultdict(int)

    for p in products:
        qty = p.quantity or 0
        cost = float(p.cost_price or 0)

        inventory_value += qty * cost
        total_stock_units += qty
        stock_trend_map[p.created_at.date().isoformat()] += qty

        if qty <= 5:
            low_stock_count += 1
            alerts.append(f"{p.name} is low in stock")
            if qty == 0:
                out_of_stock_count += 1

    if total_products:
        avg_stock_per_product = total_stock_units / total_products

    top_products_qs = products.order_by("-quantity")[:7]
    top_products = list(top_products_qs)

    sorted_dates = sorted(stock_trend_map.keys())
    cumulative = 0
    stock_levels = []
    for dt in sorted_dates:
        cumulative += stock_trend_map[dt]
        stock_levels.append(cumulative)

    sales_snapshot = (
        SaleItem.objects
        .filter(product__company=products.first().company if total_products else None, sale__created_at__gte=date_from)
        .values("product__name")
        .annotate(total_qty=Sum("quantity"), total_revenue=Sum("total_price"))
        .order_by("-total_revenue")[:5]
    ) if total_products else []

    insights = [
        f"Inventory coverage: {total_stock_units} units across {total_products} products.",
        f"Average stock per product is {avg_stock_per_product:.1f} units.",
        f"{low_stock_count} product(s) need replenishment soon.",
    ]

    if sales_snapshot:
        top_sale = sales_snapshot[0]
        insights.append(
            f"Top sales driver (30d): {top_sale['product__name']} with {top_sale['total_qty'] or 0} unit(s) sold."
        )
    if out_of_stock_count:
        insights.append(f"{out_of_stock_count} product(s) are currently out of stock.")

    return {
        "total_products": total_products,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "avg_stock_per_product": round(avg_stock_per_product, 1),
        "inventory_value": round(inventory_value, 2),
        "smart_alerts": alerts,
        "insights": insights,
        "charts": {
            "trend_dates": json.dumps(sorted_dates),
            "trend_values": json.dumps(stock_levels),
            "product_labels": json.dumps([p.name for p in top_products]),
            "product_values": json.dumps([p.quantity or 0 for p in top_products]),
            "pie_values": json.dumps([
                max(total_products - low_stock_count - out_of_stock_count, 0),
                low_stock_count,
                out_of_stock_count,
            ]),
        },
    }


# =========================
# AJAX
# =========================
@login_required
def get_product_price(request, product_id):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

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
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

    company = request.user.company
    product = get_object_or_404(Product, id=product_id, company=company)

    if request.method == "POST":

        try:
            name = request.POST.get("name", "").strip()
            if not name:
                raise ValueError("name_required")

            duplicate_exists = Product.objects.filter(
                company=company,
                name__iexact=name
            ).exclude(id=product.id).exists()

            if duplicate_exists:
                messages.error(request, "A product with this name already exists.")
                return redirect("edit_product", product_id=product.id)

            product.name = name
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
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

    product = get_object_or_404(Product, id=product_id, company=request.user.company)

    product.delete()

    messages.success(request, "Deleted.")

    return redirect("products")