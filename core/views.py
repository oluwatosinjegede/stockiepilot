from django.shortcuts import render, redirect

APP_DOWNLOAD_LINKS = {
    "ios": {
        "label": "Download on the App Store",
        "url": "https://apps.apple.com/",
        "icon": "🍎",
    },
    "android": {
        "label": "Get it on Google Play",
        "url": "https://play.google.com/store",
        "icon": "🤖",
    },
}


def _public_context(page_title: str, **extra):
    context = {
        "page_title": page_title,
        "app_download_links": APP_DOWNLOAD_LINKS,
    }
    context.update(extra)
    return context


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    return render(
        request,
        "home.html",
        _public_context(
            "StockiePilot | Inventory Intelligence for Modern Teams",
            trust_metrics=[
                {"value": "99.9%", "label": "Uptime"},
                {"value": "20K+", "label": "Monthly transactions tracked"},
                {"value": "4.9/5", "label": "Average customer rating"},
            ],
        ),
    )


def readme_page(request):
    return render(
        request,
        "legal/readme.html",
        _public_context("Readme | StockiePilot"),
    )


def privacy_policy_page(request):
    return render(
        request,
        "legal/privacy_policy.html",
        _public_context("Privacy Policy | StockiePilot", effective_date="April 16, 2026"),
    )


def terms_of_service_page(request):
    return render(
        request,
        "legal/terms_of_service.html",
        _public_context("Terms of Service | StockiePilot", effective_date="April 16, 2026"),
    )


def data_protection_page(request):
    return render(
        request,
        "legal/data_protection.html",
        _public_context("Data Protection | StockiePilot"),
    )


def fraud_warning_page(request):
    return render(
        request,
        "legal/fraud_warning.html",
        _public_context("Fraud Warning | StockiePilot"),
    )