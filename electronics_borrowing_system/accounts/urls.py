# ============================================================================
# accounts/urls.py
# ============================================================================

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Registration
    path('register/', views.register, name='register'),

    # Profile management
    path('profile/', views.profile, name='profile'),

    # Authentication with custom redirects
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),

    # Dashboard redirect utility
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),

    # Alternative: Use Django's built-in views with custom redirects
    # path('login/', auth_views.LoginView.as_view(
    #     template_name='registration/login.html',
    #     redirect_authenticated_user=True,
    #     next_page='accounts:dashboard_redirect'
    # ), name='login'),

    # Password management
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change.html',
        success_url='/accounts/profile/'
    ), name='password_change'),

    path('password-change-done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='registration/password_change_done.html'
    ), name='password_change_done'),

    # Password reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        success_url='/accounts/password-reset-done/'
    ), name='password_reset'),

    path('password-reset-done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/accounts/password-reset-complete/'
    ), name='password_reset_confirm'),

    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
