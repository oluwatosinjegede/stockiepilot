# apps/subscriptions/urls.py

from django.urls import path
from .views import (
    subscription_view,
    subscribe,
)

from .services.paystack import (
    initialize_paystack_payment,   #  view wrapper
    verify_paystack_payment        # view wrapper
)
urlpatterns = [
    path('', subscription_view, name='subscription'),

    path('subscribe/<str:plan>/', subscribe, name='subscribe'),

    # PAYSTACK (through views, not services)
    path('pay/<str:plan>/', initialize_paystack_payment, name='paystack_init'),
    path('verify/', verify_paystack_payment, name='paystack_verify'),
]