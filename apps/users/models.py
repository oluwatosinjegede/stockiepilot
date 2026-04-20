from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import uuid

from django.utils import timezone


# =========================
# CUSTOM USER MANAGER
# =========================
class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if not password:
            raise ValueError("Superuser must have a password")

        return self.create_user(email, password, **extra_fields)


# =========================
# USER MODEL
# =========================
class User(AbstractUser):

    username = models.CharField(max_length=150, blank=True, null=True)

    email = models.EmailField(unique=True)

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # TEMPORARY (for migration safety)
    full_name = models.CharField(max_length=255)

    phone = models.CharField(max_length=30)
    address = models.TextField(blank=True)

    profile_photo = models.FileField(upload_to="profile_photos/", blank=True, null=True)

    is_email_verified = models.BooleanField(default=False)
    is_affiliate = models.BooleanField(default=False)

    ONBOARDING_STATUS_CHOICES = (
        ("pending_email_verification", "Pending Email Verification"),
        ("pending_approval", "Pending Company Approval"),
        ("active", "Active"),
        ("rejected", "Rejected"),
    )
    onboarding_status = models.CharField(
        max_length=40,
        choices=ONBOARDING_STATUS_CHOICES,
        default="pending_email_verification",
    )

    ROLE_CHOICES = (
        ("staff", "Staff"),
        ("user", "User"),
        ("staff", "Company Admin"),
        ("user", "Company User"),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")

    created_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # email is the only required field

    objects = UserManager()

    def __str__(self):
        return self.email
    
    @property
    def is_company_admin(self):
        return self.role == "staff"
    

class EmailVerification(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE)

    token = models.UUIDField(default=uuid.uuid4, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.token}"


class CompanyUserApproval(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="approval_requests")
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="approval_requests")
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
         return f"{self.user.email} -> {self.company.name} ({self.status})"


class Affiliate(models.Model):
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    payout_details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"