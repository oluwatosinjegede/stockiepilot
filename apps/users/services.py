# apps/users/services.py

from django.core.mail import send_mail
from django.urls import reverse

def send_verification_email(user, token):
    verification_link = f"https://stockiepilot.up.railway.app{reverse('verify_email', args=[token])}"

    send_mail(
        subject="Verify your StockiePilot account",
        message=f"Click the link to verify your account:\n{verification_link}",
        from_email="noreply@stockiepilot.com",
        recipient_list=[user.email],
    )