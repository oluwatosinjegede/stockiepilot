# apps/companies/services.py

from .models import Company

def create_company(name, email, phone):
    return Company.objects.create(
        name=name,
        email=email,
        phone=phone
    )