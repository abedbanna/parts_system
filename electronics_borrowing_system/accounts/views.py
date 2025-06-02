# ============================================================================
# accounts/views.py (Updated with Admin Redirect Logic)
# ============================================================================

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import StudentRegistrationForm, ProfileUpdateForm


def register(request):
    """Student registration view"""
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _('Account created successfully!'))
            return redirect('core:dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    """User profile view"""
    # Create profile if it doesn't exist
    if not hasattr(request.user, 'profile'):
        from .models import UserProfile
        UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, _('Profile updated successfully!'))
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user.profile)
    return render(request, 'accounts/profile.html', {'form': form})


def custom_logout(request):
    """Custom logout view with admin-specific redirect"""

    # Check if user is admin/staff before logging out
    is_admin_user = request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)

    # Log the user out
    logout(request)

    # Set appropriate success message
    if is_admin_user:
        messages.success(request, _('تم تسجيل خروج المدير بنجاح'))
    else:
        messages.success(request, _('تم تسجيل الخروج بنجاح'))

    # Redirect based on user type
    if is_admin_user:
        # Redirect admin users to admin login or admin dashboard
        return redirect('/admin/login/?next=/borrowing/admin/')  # Admin login with redirect to borrowing admin
        # Alternative options:
        # return redirect('/admin/')  # Direct to Django admin
        # return redirect('/borrowing/admin/')  # Direct to borrowing admin (requires login)
        # return redirect('/')  # Home page
    else:
        # Redirect regular users to home page
        return redirect('/')


# Alternative version with more detailed admin handling
def custom_logout_advanced(request):
    """Advanced logout with multiple admin redirect options"""

    user_was_admin = False
    user_was_superuser = False

    if request.user.is_authenticated:
        user_was_admin = request.user.is_staff
        user_was_superuser = request.user.is_superuser

    # Logout the user
    logout(request)

    # Handle different types of admin users
    if user_was_superuser:
        messages.success(request, _('تم تسجيل خروج المدير العام بنجاح'))
        return redirect('/admin/')  # Django admin for superusers

    elif user_was_admin:
        messages.success(request, _('تم تسجيل خروج المدير بنجاح'))
        # Check if they came from borrowing admin
        if 'borrowing' in request.META.get('HTTP_REFERER', ''):
            return redirect('/borrowing/admin/')  # Back to borrowing admin
        else:
            return redirect('/admin/')  # General admin

    else:
        messages.success(request, _('تم تسجيل الخروج بنجاح'))
        return redirect('/')  # Home page for regular users


# Login view with admin redirect
def custom_login(request):
    """Custom login view that redirects admins appropriately"""
    from django.contrib.auth.views import LoginView
    from django.urls import reverse_lazy

    class CustomLoginView(LoginView):
        template_name = 'accounts/login.html'

        def get_success_url(self):
            # Get the 'next' parameter from URL
            next_url = self.request.GET.get('next')
            if next_url:
                return next_url

            # Check user type and redirect accordingly
            if self.request.user.is_superuser:
                return '/admin/'  # Django admin for superusers
            elif self.request.user.is_staff:
                return '/borrowing/admin/'  # Borrowing admin for staff
            else:
                return '/'  # Home for regular users

    return CustomLoginView.as_view()(request)


# Utility function to determine user dashboard
def get_user_dashboard_url(user):
    """Helper function to get the appropriate dashboard URL for a user"""
    if not user.is_authenticated:
        return '/'

    if user.is_superuser:
        return '/admin/'  # Django admin
    elif user.is_staff:
        return '/borrowing/admin/'  # Borrowing admin
    else:
        return '/borrowing/'  # Student borrowing dashboard


# View to redirect users to their appropriate dashboard
@login_required
def dashboard_redirect(request):
    """Redirect users to their appropriate dashboard"""
    dashboard_url = get_user_dashboard_url(request.user)
    return redirect(dashboard_url)
