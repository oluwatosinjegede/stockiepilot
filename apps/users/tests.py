from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.companies.models import Company
from apps.affiliates.models import AffiliateProfile
from apps.users.models import Affiliate, CompanyUserApproval, User


class CompanyApprovalFlowTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Acme Corp",
            email="owner@acme.com",
        )
        self.user = User.objects.create_user(
            email="member@acme.com",
            username="member@acme.com",
            password="testpass123",
            company=self.company,
            full_name="Member User",
            phone="1234567890",
            onboarding_status="pending_approval",
            is_active=False,
            is_email_verified=True,
            role="user",
            is_staff=False,
        )
        self.approval = CompanyUserApproval.objects.create(
            user=self.user,
            company=self.company,
        )

    def test_approve_company_user_marks_user_active(self):
        response = self.client.get(
            reverse("approve_company_user", args=[self.approval.token])
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))

        self.user.refresh_from_db()
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, "approved")
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.onboarding_status, "active")

    def test_user_can_login_after_approval(self):
        self.client.get(reverse("approve_company_user", args=[self.approval.token]))

        response = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": "testpass123"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("sales"), fetch_redirect_response=False)

class IdleLogoutMiddlewareTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Idle Corp",
            email="idle@corp.com",
        )
        self.user = User.objects.create_user(
            email="idleuser@corp.com",
            username="idleuser@corp.com",
            password="testpass123",
            company=self.company,
            full_name="Idle User",
            phone="1234567890",
            onboarding_status="active",
            is_active=True,
            is_email_verified=True,
            role="user",
            is_staff=False,
        )

    def test_logs_out_user_after_five_minutes_of_inactivity(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["last_activity"] = (
            timezone.now() - timedelta(seconds=settings.AUTO_LOGOUT_IDLE_SECONDS + 1)
        ).isoformat()
        session.save()

        response = self.client.get(reverse("sales"), follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, settings.LOGIN_URL)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_keeps_user_logged_in_when_not_idle_for_timeout_window(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["last_activity"] = (
            timezone.now() - timedelta(seconds=settings.AUTO_LOGOUT_IDLE_SECONDS - 1)
        ).isoformat()
        session.save()

        response = self.client.get(reverse("sales"), follow=False)

        self.assertEqual(response.status_code, 200)
        self.assertIn("_auth_user_id", self.client.session)
        

class AffiliateRegistrationTests(TestCase):
    def test_affiliate_can_register(self):
        response = self.client.post(
            reverse("affiliate_register"),
            {
                "full_name": "Jane Partner",
                "email": "jane.partner@example.com",
                "phone": "1234567890",
                "password": "securepass123",
                "confirm_password": "securepass123",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("affiliate_login"), fetch_redirect_response=False)
        user = User.objects.get(email="jane.partner@example.com")
        self.assertTrue(user.is_affiliate)
        self.assertTrue(AffiliateProfile.objects.filter(user=user).exists())

    def test_regular_login_blocks_affiliate_accounts(self):
        user = User.objects.create_user(
            email="affiliate@example.com",
            username="affiliate@example.com",
            password="testpass123",
            full_name="Affiliate",
            phone="1234567890",
            is_active=True,
            is_email_verified=True,
            onboarding_status="active",
            is_affiliate=True,
            role="user",
            is_staff=False,
        )
        AffiliateProfile.objects.filter(user=user).update(status="active", email_confirmed=True)

        response = self.client.post(
            reverse("login"),
            {"email": user.email, "password": "testpass123"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("affiliate_login"), fetch_redirect_response=False)

    def test_company_registration_can_optionally_attach_affiliate(self):
        affiliate_user = User.objects.create_user(
            email="agent@example.com",
            username="agent@example.com",
            password="securepass123",
            full_name="Referral Agent",
            phone="5551231234",
            is_active=True,
            is_email_verified=True,
            onboarding_status="active",
            is_affiliate=True,
            role="user",
            is_staff=False,
        )

        affiliate_profile = AffiliateProfile.objects.get(user=affiliate_user)
        affiliate_profile.status = "active"
        affiliate_profile.email_confirmed = True
        affiliate_profile.save(update_fields=["status", "email_confirmed"])

        response = self.client.post(
            reverse("register"),
            {
                "email": "new-owner@example.com",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "full_name": "New Owner",
                "phone": "1234567890",
                "address": "123 Main St",
                "existing_company_id": "",
                "new_company_name": "Affiliate Referred Co",
                "affiliate_id": str(affiliate_profile.id),
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        company = Company.objects.get(name="Affiliate Referred Co")
        self.assertEqual(company.referred_by_affiliate.email, affiliate_user.email)
