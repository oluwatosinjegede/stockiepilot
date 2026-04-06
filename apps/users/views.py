from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required

from apps.companies.models import Company
from apps.subscriptions.services import create_initial_subscription
from apps.billing.services import create_signup_invoice
from apps.users.models import EmailVerification
from apps.users.services import send_verification_email

User = get_user_model()


# =========================
# REGISTER VIEW
# =========================
@transaction.atomic
def register_view(request):

    if request.method == "POST":

        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        company_name = request.POST.get("company_name")

        # =========================
        # VALIDATION
        # =========================
        if not all([email, password, confirm_password, full_name, phone, company_name]):
            messages.error(request, "All required fields must be filled")
            return render(request, "auth/register.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "auth/register.html")

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return render(request, "auth/register.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "User already exists")
            return render(request, "auth/register.html")

        try:
            # =========================
            # CREATE COMPANY
            # =========================
            company = Company.objects.create(
                name=company_name,
                email=email,
                phone=phone,
                address=address
            )

            # =========================
            # CREATE USER (INACTIVE)
            # =========================
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                company=company,
                full_name=full_name,
                phone=phone,
                address=address,
                is_active=False,
                is_staff=True,          # IMPORTANT
                role="staff"            # IMPORTANT
            )

            # =========================
            # SUBSCRIPTION + BILLING
            # =========================
            create_initial_subscription(company)
            create_signup_invoice(company)

            # =========================
            # EMAIL VERIFICATION (SAFE)
            # =========================
            try:
                verification = EmailVerification.objects.create(user=user)
                send_verification_email(user, verification.token)
            except Exception as e:
                # DO NOT break registration because of email
                print("EMAIL ERROR:", str(e))
                messages.warning(
                    request,
                    "Account created, but email could not be sent. Please request verification email."
                )

            messages.success(request, "Account created successfully. Please verify your email.")
            return redirect('login')

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return render(request, "auth/register.html")

    return render(request, "auth/register.html")


# =========================
# EMAIL VERIFICATION
# =========================
def verify_email(request, token):

    verification = get_object_or_404(
        EmailVerification,
        token=token,
        is_used=False
    )

    user = verification.user

    user.is_active = True
    user.is_email_verified = True
    user.save()

    verification.is_used = True
    verification.save()

    messages.success(request, "Email verified successfully. You can now login.")
    return redirect('login')


# =========================
# RESEND VERIFICATION
# =========================
def resend_verification(request):

    if request.method == "POST":

        email = request.POST.get("email", "").strip().lower()

        user = User.objects.filter(email=email).first()

        if not user:
            messages.error(request, "User not found")
            return render(request, "auth/resend_verification.html")

        if user.is_email_verified:
            messages.info(request, "Email already verified")
            return render(request, "auth/resend_verification.html")

        try:
            verification = EmailVerification.objects.create(user=user)
            send_verification_email(user, verification.token)
            messages.success(request, "Verification email resent successfully")

        except Exception as e:
            print("EMAIL ERROR:", str(e))
            messages.error(request, "Failed to send email. Please try again later.")

    return render(request, "auth/resend_verification.html")


# =========================
# LOGIN VIEW
# =========================
def login_view(request):

    if request.method == "POST":

        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")

        if not email or not password:
            messages.error(request, "Email and password are required")
            return render(request, "auth/login.html")

        user = authenticate(request, username=email, password=password)

        if user is None:
            messages.error(request, "Invalid credentials")
            return render(request, "auth/login.html")

        if not user.is_email_verified:
            messages.error(request, "Please verify your email before logging in")
            return redirect('resend_verification')

        login(request, user)
        return redirect('dashboard')

    return render(request, "auth/login.html")


# =========================
# LOGOUT VIEW
# =========================
def logout_view(request):
    logout(request)
    return redirect('login')


# =========================
# CHANGE PASSWORD
# =========================
@login_required
def change_password(request):

    if request.method == "POST":

        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if not request.user.check_password(current_password):
            messages.error(request, "Incorrect current password")
            return redirect('change_password')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('change_password')

        if len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return redirect('change_password')

        request.user.set_password(new_password)
        request.user.save()

        messages.success(request, "Password updated successfully")
        return redirect('dashboard')

    return render(request, "auth/change_password.html")


@login_required
def create_user_view(request):

    if request.user.role != "staff":
        messages.error(request, "Permission denied.")
        return redirect("dashboard")

    if request.method == "POST":

        email = request.POST.get("email")
        password = request.POST.get("password")
        full_name = request.POST.get("full_name")

        if not email or not password:
            messages.error(request, "All fields required.")
            return redirect("dashboard")

        if User.objects.filter(email=email).exists():
            messages.error(request, "User already exists.")
            return redirect("dashboard")

        User.objects.create_user(
            email=email,
            username=email,
            password=password,
            company=request.user.company,
            full_name=full_name,
            role="user",       # 🔥 ORDINARY USER
            is_staff=False
        )

        messages.success(request, "User created successfully.")
        return redirect("dashboard")