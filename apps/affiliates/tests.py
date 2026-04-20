from decimal import Decimal

from django.test import TestCase

from apps.affiliates.models import AffiliateProfile, AffiliateReferral, AffiliateWalletTransaction
from apps.affiliates.services import (
    credit_affiliate_commission_for_company_payment,
    credit_affiliate_commission_for_payment,
    register_affiliate_for_user,
)
from apps.companies.models import Company
from apps.users.models import User


class AffiliateCommissionCreditTests(TestCase):
    def setUp(self):
        self.affiliate_user = User.objects.create_user(
            email="affiliate@example.com",
            username="affiliate@example.com",
            password="testpass123",
            full_name="Affiliate Partner",
            phone="1234567890",
            is_active=True,
            is_email_verified=True,
            onboarding_status="active",
            is_affiliate=True,
            role="user",
            is_staff=False,
        )
        self.affiliate_profile, _ = register_affiliate_for_user(self.affiliate_user)
        self.affiliate_profile.status = "active"
        self.affiliate_profile.email_confirmed = True
        self.affiliate_profile.save(update_fields=["status", "email_confirmed"])

        self.company = Company.objects.create(name="Acme", email="owner@acme.test")
        self.admin_user = User.objects.create_user(
            email="owner@acme.test",
            username="owner@acme.test",
            password="testpass123",
            full_name="Company Owner",
            phone="1234567890",
            is_active=True,
            is_email_verified=True,
            onboarding_status="active",
            is_affiliate=False,
            role="staff",
            is_staff=True,
            company=self.company,
        )
        self.company_user = User.objects.create_user(
            email="user@acme.test",
            username="user@acme.test",
            password="testpass123",
            full_name="Company User",
            phone="1234567890",
            is_active=True,
            is_email_verified=True,
            onboarding_status="active",
            is_affiliate=False,
            role="user",
            is_staff=False,
            company=self.company,
        )

        self.referral = AffiliateReferral.objects.create(
            affiliate=self.affiliate_profile,
            referred_user=self.admin_user,
            referred_email=self.admin_user.email,
            status="registered",
        )

    def test_credit_payment_is_idempotent_per_reference_and_accumulates_for_new_references(self):
        credit_affiliate_commission_for_payment(
            referred_user=self.admin_user,
            payment_amount=Decimal("1000.00"),
            reference="ref-001",
        )
        self.referral.refresh_from_db()
        wallet = self.affiliate_profile.wallet
        wallet.refresh_from_db()

        self.assertEqual(self.referral.status, "commissioned")
        self.assertEqual(self.referral.payment_amount, Decimal("1000.00"))
        self.assertEqual(self.referral.commission_amount, Decimal("100.00"))
        self.assertEqual(wallet.balance, Decimal("100.00"))

        # Same reference should not duplicate payout.
        credit_affiliate_commission_for_payment(
            referred_user=self.admin_user,
            payment_amount=Decimal("1000.00"),
            reference="ref-001",
        )
        wallet.refresh_from_db()
        self.referral.refresh_from_db()

        self.assertEqual(wallet.balance, Decimal("100.00"))
        self.assertEqual(
            AffiliateWalletTransaction.objects.filter(reference="ref-001").count(),
            1,
        )

        # New payment reference should add a new commission.
        credit_affiliate_commission_for_payment(
            referred_user=self.admin_user,
            payment_amount=Decimal("500.00"),
            reference="ref-002",
        )
        wallet.refresh_from_db()
        self.referral.refresh_from_db()

        self.assertEqual(wallet.balance, Decimal("150.00"))
        self.assertEqual(self.referral.payment_amount, Decimal("1500.00"))
        self.assertEqual(self.referral.commission_amount, Decimal("150.00"))

    def test_company_payment_falls_back_to_registered_company_referral(self):
        credited = credit_affiliate_commission_for_company_payment(
            company=self.company,
            payment_amount=Decimal("800.00"),
            reference="company-ref-001",
            paying_user=self.company_user,
        )

        self.assertIsNotNone(credited)
        self.assertEqual(credited.referred_user, self.admin_user)
        self.referral.refresh_from_db()
        self.affiliate_profile.wallet.refresh_from_db()
        self.assertEqual(self.referral.commission_amount, Decimal("80.00"))
        self.assertEqual(self.affiliate_profile.wallet.balance, Decimal("80.00"))
