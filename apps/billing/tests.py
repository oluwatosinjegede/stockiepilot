from django.test import TestCase
from decimal import Decimal

from apps.billing.models import AffiliateCommission, Payment
from apps.billing.services import create_affiliate_commission_for_payment
from apps.companies.models import Company
from apps.users.models import Affiliate


class AffiliateCommissionServiceTests(TestCase):
    def setUp(self):
        self.affiliate = Affiliate.objects.create(
            full_name="Ref Partner",
            email="partner@example.com",
        )
        self.company = Company.objects.create(
            name="Referred Co",
            email="owner@referred.co",
            referred_by_affiliate=self.affiliate,
        )

    def test_creates_10_percent_commission_for_subscription_payment(self):
        payment = Payment.objects.create(
            company=self.company,
            payment_type="subscription",
            amount=Decimal("1000.00"),
            payment_gateway="paystack",
            transaction_reference="ref-sub-001",
            status="success",
        )

        commission = create_affiliate_commission_for_payment(payment)

        self.assertIsNotNone(commission)
        self.assertEqual(commission.commission_amount, Decimal("100.00"))
        self.assertEqual(AffiliateCommission.objects.count(), 1)

    def test_skips_commission_for_non_subscription_payment(self):
        payment = Payment.objects.create(
            company=self.company,
            payment_type="signup",
            amount=Decimal("1000.00"),
            payment_gateway="paystack",
            transaction_reference="ref-signup-001",
            status="success",
        )

        commission = create_affiliate_commission_for_payment(payment)

        self.assertIsNone(commission)
        self.assertEqual(AffiliateCommission.objects.count(), 0)
