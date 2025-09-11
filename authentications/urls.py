from django.urls import path
from . import views

urlpatterns = [
    path('sign-up/with_phone_number/', views.register_user),
    path('register_with_apple/', views.apple_login),
    path('apple-login/', views.apple_login),
    path('login/', views.request_login_otp),
    path('users/', views.list_users),
    path('profile/', views.user_profile),
    path('otp/create/', views.create_otp),
    path('otp/verify/', views.verify_login_otp),
    path('password-reset/request/', views.request_password_reset),
    path('password-reset/confirm/', views.reset_password),
    path('password-change/', views.change_password),
    path('reset/otp-verify/', views.verify_otp_reset),
]
