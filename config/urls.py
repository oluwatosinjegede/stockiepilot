from django.contrib import admin
from django.urls import path, include

from apps.dashboard.views import dashboard
from apps.subscriptions.views import subscription_view
from core.views import home


urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth routes
    path('', include('apps.users.urls')),

    # App routes (MODULAR)
    path('products/', include('apps.products.urls')),
    path('sales/', include('apps.sales.urls')),

    # Other pages
    #path('subscription/', subscription_view, name='subscription'),
    path('subscription/', include('apps.subscriptions.urls')),

    # Core pages
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    
]