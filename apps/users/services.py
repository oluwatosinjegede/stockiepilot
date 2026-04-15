from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

def _resolve_base_url(request=None):
    if request is not None:
        return request.build_absolute_uri('/')
    return getattr(settings, 'BASE_URL', '').strip() or 'http://localhost:8000/'


def _build_absolute_url(path, request=None):
    return urljoin(_resolve_base_url(request), path)


def _send_email(subject, recipient_email, text_body, html_body=None):
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    if html_body:
        message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)


def send_verification_email(user, token, request=None):
    verification_link = _build_absolute_url(reverse('verify_email', args=[token]), request=request)

    context = {
        'user': user,
        'verification_link': verification_link,
    }
    text_body = render_to_string('auth/emails/verify_email.txt', context)
    html_body = render_to_string('auth/emails/verify_email.html', context)

    _send_email(
        subject='Verify your StockiePilot account',
        recipient_email=user.email,
        text_body=text_body,
        html_body=html_body,
    )


def send_password_reset_email(user, uid, token, request=None):
    reset_link = _build_absolute_url(reverse('reset_password', args=[uid, token]), request=request)

    context = {
        'user': user,
        'reset_link': reset_link,
    }
    text_body = render_to_string('auth/emails/reset_password.txt', context)
    html_body = render_to_string('auth/emails/reset_password.html', context)

    _send_email(
        subject='Reset your StockiePilot password',
        recipient_email=user.email,
        text_body=text_body,
        html_body=html_body,
    )


def send_company_authorization_email(approval_request, request=None):
    approve_link = _build_absolute_url(
        reverse("approve_company_user", args=[approval_request.token]),
        request=request,
    )
    reject_link = _build_absolute_url(
        reverse("reject_company_user", args=[approval_request.token]),
        request=request,
    )

    context = {
        "approval_request": approval_request,
        "user": approval_request.user,
        "company": approval_request.company,
        "approve_link": approve_link,
        "reject_link": reject_link,
    }
    text_body = render_to_string("auth/emails/company_user_authorization.txt", context)
    html_body = render_to_string("auth/emails/company_user_authorization.html", context)

    _send_email(
        subject=f"Approval required: {approval_request.user.email} requested access to {approval_request.company.name}",
        recipient_email=approval_request.company.email,
        text_body=text_body,
        html_body=html_body,
    )