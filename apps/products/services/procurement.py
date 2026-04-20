from datetime import date
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.products.models import Product, ProductSupply, Supplier, Category



def create_supplier(company, data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Supplier name is required.")

    try:
        supplier = Supplier.objects.create(
            company=company,
            name=name,
            contact_person=(data.get("contact_person") or "").strip(),
            phone=(data.get("phone") or "").strip(),
            email=(data.get("email") or "").strip(),
            address=(data.get("address") or "").strip(),
            notes=(data.get("notes") or "").strip(),
            is_active=bool(data.get("is_active", True)),
        )
    except IntegrityError as exc:
        raise ValidationError("Supplier with this name already exists for your company.") from exc

    return supplier


@transaction.atomic
def create_product_with_supply(company, user, product_data, supply_data):
    name = (product_data.get("name") or "").strip()
    if not name:
        raise ValidationError("Product name is required.")

    price = Decimal(product_data.get("price") or "0")
    if price <= 0:
        raise ValidationError("Selling price must be greater than zero.")

    quantity_supplied = int(product_data.get("quantity") or 0)
    if quantity_supplied < 0:
        raise ValidationError("Quantity must be zero or greater.")

    cost_price = Decimal(product_data.get("cost_price") or price)
    sku_input = (product_data.get("sku") or "").strip()

    category = None
    category_id = product_data.get("category")
    if category_id:
        category = Category.objects.filter(id=category_id).first()

    supplier = None
    supplier_id = supply_data.get("supplier")
    if supplier_id:
        supplier = Supplier.objects.filter(id=supplier_id, company=company, is_active=True).first()
        if not supplier:
            raise ValidationError("Selected supplier is invalid.")

    supplier_invoice_number = (supply_data.get("supplier_invoice_number") or "").strip()
    if supplier and not supplier_invoice_number:
        raise ValidationError("Supplier invoice number is required when a supplier is selected.")

    date_supplied = supply_data.get("date_supplied") or date.today()
    notes = (supply_data.get("supply_notes") or "").strip()

    sku = sku_input or f"SKU-{company.id}-{uuid.uuid4().hex[:6]}"
    while Product.objects.filter(company=company, sku=sku).exists():
        sku = f"SKU-{company.id}-{uuid.uuid4().hex[:6]}"

    product = Product.objects.create(
        company=company,
        name=name,
        category=category,
        description=(product_data.get("description") or "").strip(),
        selling_price=price,
        cost_price=cost_price,
        quantity=0,
        sku=sku,
    )

    supply = ProductSupply.objects.create(
        company=company,
        product=product,
        supplier=supplier,
        date_supplied=date_supplied,
        supplier_invoice_number=supplier_invoice_number or "N/A",
        quantity_supplied=max(quantity_supplied, 0),
        unit_cost=cost_price,
        notes=notes,
        created_by=user,
    )

    product.quantity = max(quantity_supplied, 0)
    product.cost_price = cost_price
    product.save(update_fields=["quantity", "cost_price"])

    return product, supply


@transaction.atomic
def record_product_supply(company, user, product, supply_data):
    supplier = None
    supplier_id = supply_data.get("supplier")
    if supplier_id:
        supplier = Supplier.objects.filter(id=supplier_id, company=company, is_active=True).first()
        if not supplier:
            raise ValidationError("Selected supplier is invalid.")

    quantity_supplied = int(supply_data.get("quantity_supplied") or 0)
    if quantity_supplied <= 0:
        raise ValidationError("Supplied quantity must be greater than zero.")

    unit_cost = Decimal(supply_data.get("unit_cost") or product.cost_price or "0")
    supplier_invoice_number = (supply_data.get("supplier_invoice_number") or "").strip()

    if supplier and not supplier_invoice_number:
        raise ValidationError("Supplier invoice number is required when a supplier is selected.")

    supply = ProductSupply.objects.create(
        company=company,
        product=product,
        supplier=supplier,
        date_supplied=supply_data.get("date_supplied") or date.today(),
        supplier_invoice_number=supplier_invoice_number or "N/A",
        quantity_supplied=quantity_supplied,
        unit_cost=unit_cost,
        notes=(supply_data.get("supply_notes") or "").strip(),
        created_by=user,
    )

    product.quantity = (product.quantity or 0) + quantity_supplied
    product.cost_price = unit_cost
    product.save(update_fields=["quantity", "cost_price"])
    return supply
