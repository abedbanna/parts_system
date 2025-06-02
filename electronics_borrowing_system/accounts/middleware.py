# ============================================================================
# accounts/middleware.py (Create this file)
# ============================================================================

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext as _


class AdminRedirectMiddleware:
    """Middleware to handle admin user redirects automatically"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Process view before it's called"""

        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None

        # Get current path
        current_path = request.path

        # Define admin paths
        admin_paths = ['/admin/', '/borrowing/admin/']
        student_paths = ['/borrowing/', '/borrowing/dashboard/']

        # Check if admin user is trying to access student area
        if request.user.is_staff and any(current_path.startswith(path) for path in student_paths):
            # Allow if explicitly requested or has valid reason
            if 'admin_view_student' in request.GET:
                return None

            # Optionally redirect admin to admin area
            if current_path == '/borrowing/' or current_path == '/borrowing/dashboard/':
                messages.info(request, _('تم توجيهك إلى لوحة الإدارة'))
                return redirect('/borrowing/admin/')

        # Check if regular user is trying to access admin area
        elif not request.user.is_staff and any(current_path.startswith(path) for path in admin_paths):
            messages.error(request, _('ليس لديك صلاحية للوصول إلى هذه الصفحة'))
            return redirect('/borrowing/')

        return None


# ============================================================================
# settings.py (Add this to your settings)
# ============================================================================

# Add to MIDDLEWARE (insert after AuthenticationMiddleware)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.AdminRedirectMiddleware',  # Add this line
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Login/Logout redirects
LOGIN_REDIRECT_URL = '/accounts/dashboard/'  # Will redirect to appropriate dashboard
LOGOUT_REDIRECT_URL = '/'

# Custom admin settings
ADMIN_USERS_REDIRECT_TO = '/borrowing/admin/'
STUDENT_USERS_REDIRECT_TO = '/borrowing/'

# ============================================================================
# core/views.py (Updated dashboard logic)
# ============================================================================

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    """Smart dashboard that redirects based on user type"""

    # Redirect admins to admin dashboard
    if request.user.is_staff:
        return redirect('/borrowing/admin/')

    # Redirect students to borrowing dashboard
    else:
        return redirect('/borrowing/')


def home(request):
    """Home page with smart redirects for logged-in users"""

    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('/borrowing/admin/')
        else:
            return redirect('/borrowing/')

    # Show home page for anonymous users
    return render(request, 'core/home.html')


# ============================================================================
# borrowing/decorators.py (Create this file for custom decorators)
# ============================================================================

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _


def admin_required(view_func):
    """Decorator that requires user to be admin/staff"""

    def check_admin(user):
        return user.is_authenticated and user.is_staff

    decorator = user_passes_test(
        check_admin,
        login_url='/accounts/login/',
        redirect_field_name='next'
    )
    return decorator(view_func)


def student_required(view_func):
    """Decorator that requires user to be a regular student (not admin)"""

    def check_student(user):
        return user.is_authenticated and not user.is_staff

    decorator = user_passes_test(
        check_student,
        login_url='/accounts/login/',
        redirect_field_name='next'
    )
    return decorator(view_func)


def smart_login_required(admin_redirect='/borrowing/admin/', student_redirect='/borrowing/'):
    """Smart login decorator that redirects based on user type"""

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/accounts/login/')

            # Check if user should be redirected
            if request.user.is_staff and not request.path.startswith('/borrowing/admin/'):
                return redirect(admin_redirect)
            elif not request.user.is_staff and not request.path.startswith('/borrowing/'):
                return redirect(student_redirect)

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


# ============================================================================
# Usage in borrowing/views.py
# ============================================================================

from .decorators import admin_required, student_required


@admin_required
def admin_dashboard(request):
    """Admin dashboard - only accessible by staff"""
    # Your existing admin dashboard code
    pass


@student_required
def student_dashboard(request):
    """Student dashboard - only accessible by students"""
    # Your existing student dashboard code
    pass
