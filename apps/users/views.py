from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone

from apps.companies.models import Company
from apps.subscriptions.services import create_initial_subscription
from apps.billing.services import create_signup_invoice
from apps.users.models import Affiliate, CompanyUserApproval, EmailVerification
from apps.affiliates.services import (
    attach_referral_to_new_user,
    register_affiliate_for_user,
    send_affiliate_activation_email,
)
from apps.users.services import (
    send_verification_email,
    send_password_reset_email,
    send_company_authorization_email,
)

User = get_user_model()


# =========================
# REGISTER VIEW
# =========================
@transaction.atomic
def register_view(request):
    existing_companies = Company.objects.order_by("name")
    affiliates = Affiliate.objects.filter(is_active=True).order_by("full_name")

    if request.method == "POST":

        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        selected_company_id = request.POST.get("existing_company_id", "").strip()
        new_company_name = request.POST.get("new_company_name", "").strip()
        affiliate_id = request.POST.get("affiliate_id", "").strip()
        referral_code = (request.GET.get("ref") or request.POST.get("referral_code") or "").strip()
        register_as_affiliate = request.POST.get("register_as_affiliate") == "on"

        # =========================
        # VALIDATION
        # =========================
        if not all([email, password, confirm_password, full_name, phone]):
            messages.error(request, "All required fields must be filled")
            return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})
        
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

        if User.objects.filter(email=email).exists():
            messages.error(request, "User already exists")
            return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

        if not selected_company_id and not new_company_name:
            messages.error(request, "Select an existing company or enter a new company name.")
            return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

        try:
            if selected_company_id:
                company = Company.objects.filter(id=selected_company_id).first()
                if not company:
                    messages.error(request, "Selected company not found.")
                    return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})
                is_company_admin = False
                onboarding_status = "pending_approval"
            else:
                selected_affiliate = None
                if affiliate_id:
                    selected_affiliate = Affiliate.objects.filter(id=affiliate_id, is_active=True).first()
                    if not selected_affiliate:
                        messages.error(request, "Selected affiliate was not found.")
                        return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

                existing_company = Company.objects.filter(name__iexact=new_company_name).first()
                if existing_company:
                    messages.error(request, "Company name already exists. Please select it from the list.")
                    return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

                company = Company.objects.create(
                    name=new_company_name,
                    email=email,
                    phone=phone,
                    address=address,
                    referred_by_affiliate=selected_affiliate,
                )
                is_company_admin = True
                onboarding_status = "pending_email_verification"

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
                is_staff=is_company_admin,
                role="staff" if is_company_admin else "user",
                onboarding_status=onboarding_status,
            )

            if register_as_affiliate:
                user.is_affiliate = True
                user.save(update_fields=["is_affiliate"])
                affiliate_profile, _ = register_affiliate_for_user(user)
                send_affiliate_activation_email(request, affiliate_profile)

            if referral_code:
                attach_referral_to_new_user(user, referral_code)

            # =========================
            # SUBSCRIPTION + BILLING
            # =========================
            if is_company_admin:
                create_initial_subscription(company)
                create_signup_invoice(company)
            # =========================
            # EMAIL VERIFICATION (SAFE)
            # =========================
            try:
                verification = EmailVerification.objects.create(user=user)
                send_verification_email(user, verification.token, request=request)
            except Exception as e:
                # DO NOT break registration because of email
                print("EMAIL ERROR:", str(e))
                messages.warning(
                    request,
                    "Account created, but email could not be sent. Please request verification email."
                )

            if not is_company_admin:
                try:
                    approval_request = CompanyUserApproval.objects.create(user=user, company=company)
                    send_company_authorization_email(approval_request, request=request)
                except Exception as e:
                    print("APPROVAL EMAIL ERROR:", str(e))
                    messages.warning(
                        request,
                        "Account created in pending approval state, but company authorization email could not be sent."
                    )

            if is_company_admin:
                messages.success(request, "Account created successfully. Please verify your email.")
            else:
                messages.success(
                    request,
                    "Account created and marked pending company approval. Verify your email and wait for company authorization.",
                )
            return redirect('login')

        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})

    return render(request, "auth/register.html", {"existing_companies": existing_companies, "affiliates": affiliates})


@transaction.atomic
def affiliate_register_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        payout_details = request.POST.get("payout_details", "").strip()

        if not full_name or not email:
            messages.error(request, "Full name and email are required.")
            return render(request, "auth/affiliate_register.html")

        if Affiliate.objects.filter(email=email).exists():
            messages.error(request, "Affiliate with this email already exists.")
            return render(request, "auth/affiliate_register.html")

        Affiliate.objects.create(
            full_name=full_name,
            email=email,
            phone=phone,
            payout_details=payout_details,
        )
        messages.success(request, "Affiliate registration successful.")
        return redirect("register")

    return render(request, "auth/affiliate_register.html")

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

    user.is_email_verified = True
    if user.onboarding_status == "pending_approval":
        messages.success(
            request,
            "Email verified. Your account is pending company approval before login is allowed.",
        )
    elif user.onboarding_status == "rejected":
        messages.error(request, "This account access request was rejected by the company.")
    else:
        user.is_active = True
        user.onboarding_status = "active"
        messages.success(request, "Email verified successfully. You can now login.")
    user.save()

    verification.is_used = True
    verification.save()

    return redirect('login')

def approve_company_user(request, token):
    approval = get_object_or_404(CompanyUserApproval, token=token)

    if approval.status != "pending":
        messages.info(request, f"This request has already been {approval.status}.")
        return redirect("login")

    user = approval.user
    approval.status = "approved"
    approval.reviewed_at = timezone.now()
    approval.save(update_fields=["status", "reviewed_at"])

    user.onboarding_status = "active"
    user.is_active = True
    user.save(update_fields=["onboarding_status", "is_active"])

    messages.success(request, f"Access approved for {user.email}. The user can now sign in.")
    return redirect("login")


def reject_company_user(request, token):
    approval = get_object_or_404(CompanyUserApproval, token=token)

    if approval.status != "pending":
        messages.info(request, f"This request has already been {approval.status}.")
        return redirect("login")

    user = approval.user
    approval.status = "rejected"
    approval.reviewed_at = timezone.now()
    approval.save(update_fields=["status", "reviewed_at"])

    user.onboarding_status = "rejected"
    user.is_active = False
    user.save(update_fields=["onboarding_status", "is_active"])

    messages.success(request, f"Access rejected for {user.email}.")
    return redirect("login")


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
            send_verification_email(user, verification.token, request=request)
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
        
        if user.onboarding_status == "pending_approval":
            messages.error(request, "Your account is pending company approval.")
            return render(request, "auth/login.html")

        if user.onboarding_status == "rejected":
            messages.error(request, "Your company access request was rejected.")
            return render(request, "auth/login.html")


        if not user.is_email_verified:
            messages.error(request, "Please verify your email before logging in")
            return redirect('resend_verification')

        login(request, user)
        if user.role == "user":
            return redirect("sales")
        return redirect('dashboard')

    return render(request, "auth/login.html")

# =========================
# FORGOT PASSWORD
# =========================
def forgot_password_view(request):

    if request.method == "POST":

        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.error(request, "Email is required")
            return render(request, "auth/forgot_password.html")

        user = User.objects.filter(email=email).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            try:
                send_password_reset_email(user, uid, token, request=request)
            except Exception as e:
                print("PASSWORD RESET EMAIL ERROR:", str(e))

        messages.success(
            request,
            "If that email is registered, a password reset link has been sent."
        )
        return redirect("forgot_password")

    return render(request, "auth/forgot_password.html")


# =========================
# RESET PASSWORD
# =========================
def reset_password_view(request, uidb64, token):

    user = None

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "Invalid or expired password reset link")
        return redirect("forgot_password")

    if request.method == "POST":

        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if not password or not confirm_password:
            messages.error(request, "All fields are required")
            return render(request, "auth/reset_password.html", {"uidb64": uidb64, "token": token})

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "auth/reset_password.html", {"uidb64": uidb64, "token": token})

        if len(password) < 6:
            messages.error(request, "Password must be at least 6 characters")
            return render(request, "auth/reset_password.html", {"uidb64": uidb64, "token": token})

        user.set_password(password)
        user.save(update_fields=["password"])

        messages.success(request, "Password reset successful. Please login.")
        return redirect("login")

    return render(request, "auth/reset_password.html", {"uidb64": uidb64, "token": token})


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
    