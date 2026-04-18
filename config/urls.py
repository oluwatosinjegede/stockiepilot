from django.contrib import admin
from django.urls import path, include

from apps.dashboard.views import dashboard
from core.views import (
    home,
    manifest_view,
    service_worker_view,
    readme_page,
    privacy_policy_page,
    terms_of_service_page,
    data_protection_page,
    fraud_warning_page,
)


urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth routes
    path('', include('apps.users.urls')),

    # App routes (MODULAR)
    path('products/', include('apps.products.urls')),
    path('sales/', include('apps.sales.urls')),

    # Other pages
    path('subscription/', include('apps.subscriptions.urls')),

    # PWA routes
    path('manifest.webmanifest', manifest_view, name='manifest'),
    path('sw.js', service_worker_view, name='service_worker'),

    # Core pages
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),

    # Public/legal pages
    path('readme/', readme_page, name='readme_page'),
    path('privacy-policy/', privacy_policy_page, name='privacy_policy_page'),
    path('terms-of-service/', terms_of_service_page, name='terms_of_service_page'),
    path('data-protection/', data_protection_page, name='data_protection_page'),
    path('fraud-warning/', fraud_warning_page, name='fraud_warning_page'),
]