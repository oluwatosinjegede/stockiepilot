from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    #  ADD THIS
    path('resend-verification/', views.resend_verification, name='resend_verification'),

    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.reset_password_view, name='reset_password'),

    path('create-user/', views.create_user_view, name='create_user'),
]