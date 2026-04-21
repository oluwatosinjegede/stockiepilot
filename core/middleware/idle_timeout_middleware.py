from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class IdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            timeout_seconds = getattr(settings, "AUTO_LOGOUT_IDLE_SECONDS", 900)

            last_activity_raw = request.session.get("last_activity")
            last_activity = parse_datetime(last_activity_raw) if last_activity_raw else None

            if (
                last_activity
                and timezone.is_naive(last_activity)
                and timezone.is_aware(now)
            ):
                last_activity = timezone.make_aware(
                    last_activity,
                    timezone.get_current_timezone(),
                )

            if last_activity and now - last_activity > timedelta(seconds=timeout_seconds):
                logout(request)
                return redirect(settings.LOGIN_URL)

            request.session["last_activity"] = now.isoformat()

        return self.get_response(request)
