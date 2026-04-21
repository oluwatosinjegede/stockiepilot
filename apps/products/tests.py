from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.companies.models import Company
from apps.products.models import Product
from apps.products.services.procurement import record_product_supply
from apps.users.models import User


class RecordProductSupplyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Acme Ltd",
            email="hello@acme.test",
        )
        self.user = User.objects.create_user(
            email="owner@acme.test",
            password="password123",
            full_name="Owner User",
            phone="1234567890",
            company=self.company,
            role="staff",
        )
        self.product = Product.objects.create(
            company=self.company,
            name="Widget",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("8.00"),
            quantity=10,
            sku="W-001",
        )

    def test_record_product_supply_adds_to_existing_quantity(self):
        supply = record_product_supply(
            company=self.company,
            user=self.user,
            product=self.product,
            supply_data={
                "quantity_supplied": "5",
                "unit_cost": "9.50",
                "supplier_invoice_number": "INV-100",
                "date_supplied": date.today(),
            },
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 15)
        self.assertEqual(supply.quantity_supplied, 5)

    def test_record_product_supply_accepts_stock_quantity_alias(self):
        record_product_supply(
            company=self.company,
            user=self.user,
            product=self.product,
            supply_data={
                "stock_quantity": "4",
                "unit_cost": "9.00",
                "supplier_invoice_number": "INV-101",
                "date_supplied": date.today(),
            },
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 14)

    def test_record_product_supply_rejects_non_positive_quantity(self):
        with self.assertRaises(ValidationError):
            record_product_supply(
                company=self.company,
                user=self.user,
                product=self.product,
                supply_data={"quantity_supplied": "0"},
            )


from apps.products.models import ProductSupply, Supplier
from apps.products.views import _build_supplier_analytics
from apps.sales.models import Sale, SaleItem


class SupplierAnalyticsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Globex", email="hello@globex.test")
        self.user = User.objects.create_user(
            email="staff@globex.test",
            password="password123",
            full_name="Staff User",
            phone="1234567890",
            company=self.company,
            role="staff",
        )
        self.supplier_a = Supplier.objects.create(company=self.company, name="Alpha Supplies")
        self.supplier_b = Supplier.objects.create(company=self.company, name="Beta Wholesale")
        self.product_a = Product.objects.create(
            company=self.company,
            name="Coffee",
            selling_price=Decimal("30.00"),
            cost_price=Decimal("12.00"),
            quantity=40,
            sku="CF-1",
        )
        self.product_b = Product.objects.create(
            company=self.company,
            name="Tea",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("9.00"),
            quantity=20,
            sku="TE-1",
        )

        ProductSupply.objects.create(
            company=self.company,
            product=self.product_a,
            supplier=self.supplier_a,
            date_supplied=date.today(),
            supplier_invoice_number="INV-A",
            quantity_supplied=50,
            unit_cost=Decimal("11.00"),
        )
        ProductSupply.objects.create(
            company=self.company,
            product=self.product_b,
            supplier=self.supplier_b,
            date_supplied=date.today(),
            supplier_invoice_number="INV-B",
            quantity_supplied=30,
            unit_cost=Decimal("8.50"),
        )

        sale = Sale.objects.create(company=self.company, total_amount=Decimal("130.00"))
        SaleItem.objects.create(sale=sale, product=self.product_a, quantity=3, unit_price=Decimal("30.00"), total_price=Decimal("90.00"))
        SaleItem.objects.create(sale=sale, product=self.product_b, quantity=2, unit_price=Decimal("20.00"), total_price=Decimal("40.00"))

    def test_supplier_analytics_returns_chart_and_kpis(self):
        suppliers = Supplier.objects.filter(company=self.company)
        analytics = _build_supplier_analytics(self.company, suppliers)

        self.assertEqual(analytics["suppliers_total"], 2)
        self.assertEqual(analytics["supplied_units_total"], 80)
        self.assertEqual(analytics["top_supplier_name"], "Alpha Supplies")
        self.assertIn("pie_values", analytics["supplier_charts"])
