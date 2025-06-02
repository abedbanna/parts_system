# ============================================================================
# accounts/views.py (Updated for Profile approach)
# ============================================================================

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import StudentRegistrationForm, ProfileUpdateForm


def register(request):
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


from django.contrib.auth import login, logout  # ← FIXED: Added logout import

def custom_logout(request):
    """Custom logout view - FIXED REDIRECT"""
    logout(request)
    messages.success(request, 'تم تسجيل الخروج بنجاح')
    return redirect('/')  # ← FIXED: Simple redirect instead of 'core:home'
