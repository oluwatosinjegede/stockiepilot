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

