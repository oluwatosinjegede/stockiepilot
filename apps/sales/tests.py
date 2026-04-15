from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.companies.models import Company
from apps.products.models import Product
from apps.sales.models import Sale
from apps.users.models import User


class CreateSaleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Acme Retail",
            email="acme@example.com",
        )
        self.user = User.objects.create_user(
            email="staff@example.com",
            password="pass1234",
            full_name="Staff User",
            phone="1234567890",
            company=self.company,
        )
        self.client.force_login(self.user)

        self.product_a = Product.objects.create(
            company=self.company,
            name="Product A",
            quantity=10,
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            sku="SKU-A",
        )
        self.product_b = Product.objects.create(
            company=self.company,
            name="Product B",
            quantity=8,
            selling_price=Decimal("50.00"),
            cost_price=Decimal("30.00"),
            sku="SKU-B",
        )

    def test_create_sale_with_multiple_products(self):
        payload = {
            "product[]": [str(self.product_a.id), str(self.product_b.id)],
            "quantity[]": ["2", "3"],
            "payment_status": "paid",
        }

        response = self.client.post(reverse("create_sale"), payload, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Sale.objects.count(), 1)

        sale = Sale.objects.prefetch_related("items__product").get()
        self.assertEqual(sale.items.count(), 2)
        self.assertEqual(sale.total_amount, Decimal("350.00"))
        self.assertEqual(sale.amount_paid, Decimal("350.00"))
        self.assertEqual(sale.balance, Decimal("0"))
        self.assertEqual(sale.status, "completed")

        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.quantity, 8)
        self.assertEqual(self.product_b.quantity, 5)

    def test_rejects_mismatched_product_and_quantity_rows(self):
        payload = {
            "product[]": [str(self.product_a.id), str(self.product_b.id)],
            "quantity[]": ["2"],
            "payment_status": "paid",
        }

        response = self.client.post(reverse("create_sale"), payload)

# Create your tests here.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 0)

def test_updates_pending_sale_with_additional_payment(self):
        sale = Sale.objects.create(
            company=self.company,
            total_amount=Decimal("500.00"),
            payment_status="partial",
            customer_name="Olaseni",
            amount_paid=Decimal("200.00"),
            balance=Decimal("300.00"),
            status="pending",
        )

        response = self.client.post(
            reverse("update_sale_payment", kwargs={"sale_id": sale.id}),
            {"payment_amount": "150.00"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal("350.00"))
        self.assertEqual(sale.balance, Decimal("150.00"))
        self.assertEqual(sale.status, "pending")
        self.assertEqual(sale.payment_status, "partial")

    def test_marks_pending_sale_completed_when_fully_paid(self):
        sale = Sale.objects.create(
            company=self.company,
            total_amount=Decimal("500.00"),
            payment_status="partial",
            customer_name="Olaseni",
            amount_paid=Decimal("400.00"),
            balance=Decimal("100.00"),
            status="pending",
        )

        response = self.client.post(
            reverse("update_sale_payment", kwargs={"sale_id": sale.id}),
            {"payment_amount": "100.00"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal("500.00"))
        self.assertEqual(sale.balance, Decimal("0.00"))
        self.assertEqual(sale.status, "completed")
        self.assertEqual(sale.payment_status, "paid")

    def test_rejects_payment_greater_than_balance(self):
        sale = Sale.objects.create(
            company=self.company,
            total_amount=Decimal("500.00"),
            payment_status="partial",
            customer_name="Olaseni",
            amount_paid=Decimal("400.00"),
            balance=Decimal("100.00"),
            status="pending",
        )

        response = self.client.post(
            reverse("update_sale_payment", kwargs={"sale_id": sale.id}),
            {"payment_amount": "120.00"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        sale.refresh_from_db()
        self.assertEqual(sale.amount_paid, Decimal("400.00"))
        self.assertEqual(sale.balance, Decimal("100.00"))
        self.assertEqual(sale.status, "pending")