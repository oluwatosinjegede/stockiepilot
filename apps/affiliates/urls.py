from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.affiliate_dashboard, name="affiliate_dashboard"),
    path("activate/<uuid:token>/", views.activate_affiliate, name="activate_affiliate"),
    path("resend-activation/", views.resend_affiliate_activation, name="resend_affiliate_activation"),
    path("admin/earnings/", views.admin_affiliate_earnings, name="admin_affiliate_earnings"),
]
