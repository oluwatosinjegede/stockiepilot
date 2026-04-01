# apps/subscriptions/middleware.py

from django.shortcuts import redirect
from django.utils import timezone

class SubscriptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated:
            company = request.user.company

            if company:
                subscription = company.subscriptions.last()

                if not subscription or subscription.status != 'active':
                    return redirect('/billing/subscribe/')

        return self.get_response(request)