import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now, timedelta

from .models import Category, Product, ProductSupply, Supplier
from .services.procurement import create_product_with_supply, create_supplier, record_product_supply
from apps.sales.models import SaleItem
from apps.subscriptions.services import can_create_product


def _redirect_affiliate_if_needed(request):
    if request.user.is_affiliate:
        messages.error(request, "Affiliate accounts cannot access Products.")
        return redirect("affiliate_dashboard")
    return None

def _require_inventory_role(request):
    if request.user.role not in ["owner", "staff"]:
        messages.error(request, "Permission denied.")
        return False
    return True

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

        if not _require_inventory_role(request):
            return redirect("products")

        action = request.POST.get("action")
        if action == "create_category":
            return _create_category(request)
        if action == "add_stock":
            return _add_stock(request, company)

        return _create_product(request, company)

    products = Product.objects.filter(company=company).select_related("category").order_by("-id")

    categories = Category.objects.all()
    suppliers = Supplier.objects.filter(company=company, is_active=True).order_by("name")

    analytics = _build_product_analytics(products)

    return render(
        request,
        "products.html",
        {
            "products": products,
            "categories": categories,
            "suppliers": suppliers,
            "today": date.today(),
            **analytics,
        },
    )

@login_required
def supplier_list_view(request):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect
    company = getattr(request.user, "company", None)
    if not company:
        messages.error(request, "No company assigned.")
        return redirect("dashboard")

    suppliers = Supplier.objects.filter(company=company).order_by("name")
    analytics = _build_supplier_analytics(company, suppliers)
    return render(request, "products/suppliers.html", {"suppliers": suppliers, **analytics})


@login_required
def create_supplier_view(request):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect
    company = getattr(request.user, "company", None)
    if not company:
        messages.error(request, "No company assigned.")
        return redirect("dashboard")
    if not _require_inventory_role(request):
        return redirect("products")

    if request.method == "POST":
        try:
            create_supplier(company, request.POST)
            messages.success(request, "Supplier created successfully.")
            return redirect("suppliers")
        except ValidationError as exc:
            messages.error(request, str(exc))

    return render(request, "products/create_supplier.html")


def _create_product(request, company):
    if not can_create_product(company):
        messages.error(
            request,
            "Product limit reached for your current plan or your subscription is inactive. Upgrade to continue.",
        )
        return redirect("subscription")

    try:
        product, supply = create_product_with_supply(
            company=company,
            user=request.user,
            product_data=request.POST,
            supply_data=request.POST,
        )
        messages.success(
            request,
            f"Product created with opening supply of {supply.quantity_supplied} units for {product.name}.",
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "Error saving product.")
     

    return redirect("products")

def _add_stock(request, company):
    product_id = request.POST.get("product_id")

    product = Product.objects.filter(id=product_id, company=company).first()
    if not product:
        messages.error(request, "Product not found.")
        return redirect("products")

    try:
        supply = record_product_supply(company, request.user, product, request.POST)
        messages.success(
            request,
            f"Added {supply.quantity_supplied} unit(s) to {product.name}. Current stock: {product.quantity}.",
        )
    except ValidationError as exc:
        messages.error(request, str(exc))

    return redirect("products")


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
        SaleItem.objects.filter(
            product__company=products.first().company if total_products else None,
            sale__created_at__gte=date_from,
        )
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
            "pie_values": json.dumps(
                [max(total_products - low_stock_count - out_of_stock_count, 0), low_stock_count, out_of_stock_count]
            ),
        },
    }


def _build_supplier_analytics(company, suppliers):
    supplier_rows = []
    total_supplied_units = 0
    total_sales_revenue = Decimal("0")

    for supplier in suppliers:
        supply_qs = ProductSupply.objects.filter(company=company, supplier=supplier)
        supply_agg = supply_qs.aggregate(total_units=Sum("quantity_supplied"), total_spend=Sum("total_cost"))
        product_ids = list(supply_qs.values_list("product_id", flat=True).distinct())

        sales_agg = SaleItem.objects.filter(
            sale__company=company,
            product_id__in=product_ids,
        ).aggregate(units_sold=Sum("quantity"), revenue=Sum("total_price"))

        supplied_units = supply_agg["total_units"] or 0
        sales_revenue = sales_agg["revenue"] or Decimal("0")
        row = {
            "supplier": supplier,
            "products_count": len(product_ids),
            "supplied_units": supplied_units,
            "supply_spend": supply_agg["total_spend"] or Decimal("0"),
            "units_sold": sales_agg["units_sold"] or 0,
            "sales_revenue": sales_revenue,
        }
        supplier_rows.append(row)
        total_supplied_units += supplied_units
        total_sales_revenue += sales_revenue

    supplier_rows.sort(key=lambda row: row["sales_revenue"], reverse=True)
    top_supplier = supplier_rows[0] if supplier_rows else None
    active_supplier_count = sum(1 for row in supplier_rows if row["supplier"].is_active)

    insights = [
        f"{len(supplier_rows)} supplier(s) are tracked, {active_supplier_count} currently active.",
        f"Suppliers have delivered {total_supplied_units} total unit(s).",
    ]
    if top_supplier and top_supplier["sales_revenue"] > 0:
        insights.append(
            f"Top supplier by product sales: {top_supplier['supplier'].name} (₦{top_supplier['sales_revenue']:.2f})."
        )
    if total_sales_revenue > 0:
        insights.append(f"Products linked to suppliers generated ₦{total_sales_revenue:.2f} in sales.")

    pie_rows = [row for row in supplier_rows if row["sales_revenue"] > 0][:5]
    others_revenue = sum((row["sales_revenue"] for row in supplier_rows[5:] if row["sales_revenue"] > 0), Decimal("0"))
    pie_labels = [row["supplier"].name for row in pie_rows]
    pie_values = [float(row["sales_revenue"]) for row in pie_rows]
    if others_revenue > 0:
        pie_labels.append("Other Suppliers")
        pie_values.append(float(others_revenue))

    return {
        "supplier_rows": supplier_rows,
        "supplier_insights": insights,
        "suppliers_total": len(supplier_rows),
        "active_suppliers_total": active_supplier_count,
        "supplied_units_total": total_supplied_units,
        "supplier_sales_total": total_sales_revenue,
        "top_supplier_name": top_supplier["supplier"].name if top_supplier else "—",
        "supplier_charts": {
            "labels": json.dumps([row["supplier"].name for row in supplier_rows[:7]]),
            "product_values": json.dumps([row["products_count"] for row in supplier_rows[:7]]),
            "revenue_values": json.dumps([float(row["sales_revenue"]) for row in supplier_rows[:7]]),
            "pie_labels": json.dumps(pie_labels),
            "pie_values": json.dumps(pie_values),
        },
    }


@login_required
def get_product_price(request, product_id):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

    company = request.user.company

    product = get_object_or_404(Product, id=product_id, company=company)

    return JsonResponse({"price": float(product.selling_price or 0), "stock": product.quantity or 0})

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

            duplicate_exists = Product.objects.filter(company=company, name__iexact=name).exclude(id=product.id).exists()

            if duplicate_exists:
                messages.error(request, "A product with this name already exists.")
                return redirect("edit_product", product_id=product.id)

            product.name = name
            product.selling_price = Decimal(request.POST.get("price"))
            product.quantity = int(request.POST.get("quantity"))
            product.cost_price = Decimal(request.POST.get("cost_price"))

            product.save()

            messages.success(request, "Updated.")

        except Exception:
            messages.error(request, "Invalid data.")

        return redirect("products")

    return render(request, "products/edit.html", {"product": product})

@login_required
def delete_product(request, product_id):
    affiliate_redirect = _redirect_affiliate_if_needed(request)
    if affiliate_redirect:
        return affiliate_redirect

    product = get_object_or_404(Product, id=product_id, company=request.user.company)

    product.delete()

    messages.success(request, "Deleted.")

    return redirect("products")