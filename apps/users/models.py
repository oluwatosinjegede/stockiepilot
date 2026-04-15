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

    is_email_verified = models.BooleanField(default=False)

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