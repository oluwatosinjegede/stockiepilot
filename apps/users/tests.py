from django.test import TestCase
from django.urls import reverse

from apps.companies.models import Company
from apps.users.models import CompanyUserApproval, User


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
