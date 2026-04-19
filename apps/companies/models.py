    
from django.db import models
from django.db.models.functions import Lower


class Company(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, null=True, blank=True)
    address = models.TextField(blank=True)
    referred_by_affiliate = models.ForeignKey(
        "users.Affiliate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_companies",
    )

    subscription_plan = models.CharField(
        max_length=20,
        choices=[
            ("free", "Free"),
            ("basic", "Basic"),
            ("pro", "Pro"),
            ("enterprise", "Enterprise"),
        ],
        default="free"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="companies_company_name_ci_unique",
            )
        ]

    def __str__(self):
        return self.name