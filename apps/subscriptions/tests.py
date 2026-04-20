from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Company
from apps.products.models import Product
from apps.subscriptions.constants import BillingCycle, Plans
from apps.subscriptions.models import Subscription
from apps.subscriptions.services import (
    can_access_multi_branch,
    can_create_product,
    create_initial_subscription,
    get_company_subscription,
    is_subscription_active,
    renew_subscription,
    upgrade_subscription,
)
from apps.users.models import User


class SubscriptionLifecycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Trial Co", email="trial@example.com")

    def test_new_company_gets_30_day_free_trial_subscription(self):
        sub = create_initial_subscription(self.company)
        self.assertEqual(sub.plan_name, Plans.FREE)
        self.assertEqual(sub.status, Subscription.STATUS_TRIALING)
        self.assertEqual(sub.amount, Decimal("0"))
        self.assertIsNotNone(sub.trial_start)
        self.assertIsNotNone(sub.trial_end)
        self.assertGreaterEqual((sub.trial_end - sub.trial_start).days, 29)

    def test_trial_expiry_blocks_active_status(self):
        sub = create_initial_subscription(self.company)
        sub.trial_end = timezone.now() - timedelta(days=1)
        sub.current_period_end = sub.trial_end
        sub.save(update_fields=["trial_end", "current_period_end"])

        self.assertFalse(is_subscription_active(self.company))
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.STATUS_EXPIRED)

    def test_monthly_renewal_date_calculation(self):
        sub = create_initial_subscription(self.company)
        sub = upgrade_subscription(self.company, Plans.BASIC, BillingCycle.MONTHLY)
        current_end = sub.current_period_end

        renew_subscription(sub, payment_success=True)
        sub.refresh_from_db()

        self.assertEqual((sub.current_period_end - current_end).days, 30)

    def test_annual_renewal_date_calculation(self):
        sub = create_initial_subscription(self.company)
        sub = upgrade_subscription(self.company, Plans.PRO, BillingCycle.ANNUAL)
        current_end = sub.current_period_end

        renew_subscription(sub, payment_success=True)
        sub.refresh_from_db()

        self.assertEqual((sub.current_period_end - current_end).days, 365)

    def test_failed_renewal_moves_subscription_to_past_due(self):
        sub = create_initial_subscription(self.company)
        sub = upgrade_subscription(self.company, Plans.BASIC, BillingCycle.MONTHLY)

        renew_subscription(sub, payment_success=False)
        sub.refresh_from_db()

        self.assertEqual(sub.status, Subscription.STATUS_PAST_DUE)


class PlanEnforcementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Limits Co", email="limits@example.com")
        self.user = User.objects.create_user(
            email="owner@limits.example.com",
            password="pass1234",
            full_name="Owner",
            phone="1234567890",
            role="staff",
            is_staff=True,
            company=self.company,
            is_active=True,
            is_email_verified=True,
            onboarding_status="active",
        )
        self.client.force_login(self.user)
        create_initial_subscription(self.company)

    def _create_product(self, idx):
        Product.objects.create(
            company=self.company,
            name=f"Product {idx}",
            quantity=2,
            selling_price=Decimal("50.00"),
            cost_price=Decimal("25.00"),
            sku=f"SKU-{idx}",
        )

    def test_free_plan_product_limit_enforcement(self):
        self._create_product(1)
        self._create_product(2)
        self.assertFalse(can_create_product(self.company))

    def test_basic_plan_10_product_limit_enforcement(self):
        upgrade_subscription(self.company, Plans.BASIC, BillingCycle.MONTHLY)
        for idx in range(1, 11):
            self._create_product(idx)

        self.assertFalse(can_create_product(self.company))

    def test_pro_plan_has_unlimited_products(self):
        upgrade_subscription(self.company, Plans.PRO, BillingCycle.MONTHLY)
        for idx in range(1, 25):
            self._create_product(idx)

        self.assertTrue(can_create_product(self.company))

    def test_enterprise_only_feature_restriction(self):
        upgrade_subscription(self.company, Plans.PRO, BillingCycle.MONTHLY)
        self.assertFalse(can_access_multi_branch(self.company))

        upgrade_subscription(self.company, Plans.ENTERPRISE, BillingCycle.MONTHLY)
        self.assertTrue(can_access_multi_branch(self.company))

    def test_inactive_subscription_blocks_product_creation_endpoint(self):
        sub = get_company_subscription(self.company)
        sub.status = Subscription.STATUS_EXPIRED
        sub.current_period_end = timezone.now() - timedelta(days=1)
        sub.save(update_fields=["status", "current_period_end"])

        response = self.client.post(
            reverse("products"),
            {
                "name": "Blocked Product",
                "price": "100",
                "quantity": "1",
                "sku": "SKU-BLOCKED",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("subscription"))


class UpgradeDowngradeFlowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Upgrade Co", email="upgrade@example.com")
        create_initial_subscription(self.company)

    def test_upgrade_from_monthly_to_annual(self):
        sub = upgrade_subscription(self.company, Plans.BASIC, BillingCycle.MONTHLY)
        self.assertEqual(sub.amount, Decimal("2500"))

        sub = upgrade_subscription(self.company, Plans.BASIC, BillingCycle.ANNUAL)
        self.assertEqual(sub.billing_cycle, BillingCycle.ANNUAL)
        self.assertEqual(sub.amount, Decimal("20000"))

    def test_upgrade_then_downgrade_flow(self):
        sub = upgrade_subscription(self.company, Plans.PRO, BillingCycle.MONTHLY)
        self.assertEqual(sub.plan_name, Plans.PRO)

        sub = upgrade_subscription(self.company, Plans.BASIC, BillingCycle.MONTHLY)
        self.assertEqual(sub.plan_name, Plans.BASIC)
        self.assertEqual(sub.amount, Decimal("2500"))
