from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.companies.models import Company
from apps.products.models import Product
from apps.sales.services import create_sale_with_payment
from apps.users.models import User


class CreateSaleWithPaymentTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Retail", email="acme@example.com")
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="pass1234",
            full_name="Owner User",
            phone="1234567890",
            role="owner",
            company=self.company,
        )
        self.product = Product.objects.create(
            company=self.company,
            name="Product A",
            quantity=10,
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            sku="SKU-A",
        )

    def test_paid_sale_saves_customer_and_payment_method(self):
        sale, _invoice, _receipt = create_sale_with_payment(
            company=self.company,
            user=self.user,
            sale_data={
                "payment_status": "paid",
                "customer_name": "Jane Doe",
                "payment_method": "transfer",
            },
            items_data=[{"product": self.product, "quantity": 2}],
        )

        self.assertEqual(sale.customer_name, "Jane Doe")
        self.assertEqual(sale.amount_paid, Decimal("200.00"))
        self.assertEqual(sale.balance, Decimal("0.00"))
        self.assertEqual(sale.payments.first().payment_method, "transfer")

    def test_paid_sale_requires_customer_and_payment_method(self):
        with self.assertRaises(ValidationError):
            create_sale_with_payment(
                company=self.company,
                user=self.user,
                sale_data={"payment_status": "paid", "customer_name": "", "payment_method": ""},
                items_data=[{"product": self.product, "quantity": 1}],
            )
