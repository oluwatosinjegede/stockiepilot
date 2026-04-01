    
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, null=True, blank=True)
    address = models.TextField(blank=True)

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

    def __str__(self):
        return self.name