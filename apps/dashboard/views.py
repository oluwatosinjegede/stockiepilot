import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .services import build_dashboard_context

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    company = getattr(request.user, "company", None)
    if not company:
        return redirect("login")

    try:
        days = int(request.GET.get("range", 30))
        days = days if days in (1, 7, 30, 90) else 30
        context = build_dashboard_context(company=company, days=days)
        context["selected_range"] = days
        return render(request, "dashboard.html", context)

    except Exception:
        logger.exception("Dashboard Error")
        return render(
            request,
            "dashboard.html",
            {"error": "Dashboard failed to load. Contact admin."},
        )