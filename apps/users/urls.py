from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    #  ADD THIS
    path('resend-verification/', views.resend_verification, name='resend_verification'),

    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
]