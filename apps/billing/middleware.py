# apps/billing/middleware.py

from django.shortcuts import redirect
from django.utils import timezone

class SubscriptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated:
            company = getattr(request.user, 'company', None)

            if company:
                subscription = company.subscriptions.last()

                if not subscription or subscription.end_date < timezone.now():
                    return redirect('billing:subscription_required')

        return self.get_response(request)