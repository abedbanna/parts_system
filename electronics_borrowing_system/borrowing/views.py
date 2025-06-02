# ============================================================================
# FILE: borrowing/views.py
# ============================================================================

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, date
import json
import logging

# Import our custom forms
try:
    from .forms import BorrowRequestForm, BorrowRequestProcessor
except ImportError:
    # Fallback if forms.py doesn't exist yet
    from django import forms


    class BorrowRequestForm(forms.Form):
        purpose = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)
        expected_return_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
        student_notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)


    class BorrowRequestProcessor:
        def __init__(self, data=None):
            self.data = data or {}

        def is_valid(self):
            return True

        def get_cleaned_data(self):
            return {'main_data': self.data, 'parts_data': []}

logger = logging.getLogger(__name__)

# Temporary storage for demo purposes (replace with actual database models)
TEMP_REQUESTS_STORAGE = []


@login_required
def dashboard(request):
    """Main dashboard for borrowing system"""
    # Get user's requests from temporary storage
    user_requests = [req for req in TEMP_REQUESTS_STORAGE if req.get('user_id') == request.user.id]

    context = {
        'active_borrows': len([req for req in user_requests if req.get('status') == 'approved']),
        'pending_requests': len([req for req in user_requests if req.get('status') == 'pending']),
        'recent_requests': user_requests[-5:],  # Last 5 requests
        'available_parts_count': 50,  # Mock number
    }
    return render(request, 'borrowing/dashboard.html', context)


@login_required
def create_request(request):
    """Create new borrowing request"""

    if request.method == 'POST':
        # Debug: Log the POST data
        logger.info(f"POST data received: {request.POST}")

        # Process the form data
        processor = BorrowRequestProcessor(request.POST)

        if processor.is_valid():
            # Get cleaned data
            cleaned_data = processor.get_cleaned_data()

            # Create request data structure
            request_data = {
                'id': len(TEMP_REQUESTS_STORAGE) + 1,
                'user_id': request.user.id,
                'user_name': request.user.get_full_name() or request.user.username,
                'purpose': cleaned_data['main_data']['purpose'],
                'expected_return_date': str(cleaned_data['main_data']['expected_return_date']),
                'student_notes': cleaned_data['main_data'].get('student_notes', ''),
                'parts': cleaned_data['parts_data'],
                'status': 'pending',
                'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
                'total_parts': len(cleaned_data['parts_data'])
            }

            # Save to temporary storage (replace with actual database save)
            TEMP_REQUESTS_STORAGE.append(request_data)

            # Log success
            logger.info(f"Request created successfully: {request_data['id']}")

            # Success message
            parts_count = len(cleaned_data['parts_data'])
            success_msg = _(f'Borrowing request created successfully! {parts_count} parts requested.')
            messages.success(request, success_msg)

            # Return JSON response for AJAX requests
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': str(success_msg),
                    'request_id': request_data['id']
                })

            return redirect('borrowing:dashboard')

        else:
            # Handle validation errors
            error_summary = processor.get_errors_summary()
            logger.warning(f"Form validation failed: {error_summary}")

            for error in error_summary:
                messages.error(request, error)

            # Return JSON response for AJAX requests
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'errors': error_summary
                })

    # GET request - show empty form
    form = BorrowRequestForm()

    context = {
        'form': form,
        'available_parts': [  # Mock available parts
            'Arduino Uno R3',
            'Breadboard Full Size',
            'LED Kit (Red, Green, Blue)',
            'Resistor Kit (220Ω - 10kΩ)',
            'Jumper Wires Set',
            'Servo Motor SG90',
            'Ultrasonic Sensor HC-SR04',
            'LCD Display 16x2'
        ]
    }
    return render(request, 'borrowing/create_request.html', context)


@login_required
def request_list(request):
    """List user's borrowing requests"""
    # Get user's requests from temporary storage
    user_requests = [req for req in TEMP_REQUESTS_STORAGE if req.get('user_id') == request.user.id]

    # Sort by creation date (newest first)
    user_requests.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    context = {
        'requests': user_requests,
        'total_requests': len(user_requests),
        'pending_count': len([req for req in user_requests if req.get('status') == 'pending']),
        'approved_count': len([req for req in user_requests if req.get('status') == 'approved']),
    }
    return render(request, 'borrowing/request_list.html', context)


@login_required
def request_detail(request, pk):
    """View borrowing request details"""
    # Find request in temporary storage
    request_data = None
    for req in TEMP_REQUESTS_STORAGE:
        if req.get('id') == int(pk) and req.get('user_id') == request.user.id:
            request_data = req
            break

    if not request_data:
        messages.error(request, _('Request not found.'))
        return redirect('borrowing:request_list')

    context = {
        'request_data': request_data,
    }
    return render(request, 'borrowing/request_detail.html', context)


@staff_member_required
def admin_dashboard(request):
    """Admin dashboard for managing requests"""
    pending_requests = [req for req in TEMP_REQUESTS_STORAGE if req.get('status') == 'pending']
    active_borrows = [req for req in TEMP_REQUESTS_STORAGE if req.get('status') == 'approved']

    # Mock overdue logic (requests approved more than 7 days ago)
    from datetime import datetime, timedelta
    overdue_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M')
    overdue_requests = [req for req in active_borrows if req.get('created_at', '9999-12-31 23:59') < overdue_cutoff]

    context = {
        'pending_requests': pending_requests,
        'active_borrows': active_borrows,
        'overdue_requests': overdue_requests,
        'total_pending': len(pending_requests),
        'total_active': len(active_borrows),
        'total_overdue': len(overdue_requests),
        'all_requests': TEMP_REQUESTS_STORAGE[-10:],  # Last 10 requests
    }
    return render(request, 'borrowing/admin_dashboard.html', context)


@staff_member_required
@require_http_methods(["POST"])
def approve_request(request, pk):
    """Approve a borrowing request"""
    # Find and update request in temporary storage
    for req in TEMP_REQUESTS_STORAGE:
        if req.get('id') == int(pk):
            req['status'] = 'approved'
            req['approved_at'] = timezone.now().strftime('%Y-%m-%d %H:%M')
            req['approved_by'] = request.user.username
            messages.success(request, _(f'Request #{pk} approved successfully!'))
            logger.info(f"Request {pk} approved by {request.user.username}")
            break
    else:
        messages.error(request, _('Request not found.'))

    return redirect('borrowing:admin_dashboard')


@staff_member_required
@require_http_methods(["POST"])
def reject_request(request, pk):
    """Reject a borrowing request"""
    # Find and update request in temporary storage
    rejection_reason = request.POST.get('reason', 'No reason provided')

    for req in TEMP_REQUESTS_STORAGE:
        if req.get('id') == int(pk):
            req['status'] = 'rejected'
            req['rejected_at'] = timezone.now().strftime('%Y-%m-%d %H:%M')
            req['rejected_by'] = request.user.username
            req['rejection_reason'] = rejection_reason
            messages.success(request, _(f'Request #{pk} rejected.'))
            logger.info(f"Request {pk} rejected by {request.user.username}: {rejection_reason}")
            break
    else:
        messages.error(request, _('Request not found.'))

    return redirect('borrowing:admin_dashboard')


@login_required
def debug_requests(request):
    """Debug view to see all stored requests"""
    if not request.user.is_staff:
        messages.error(request, _('Access denied.'))
        return redirect('borrowing:dashboard')

    return JsonResponse({
        'total_requests': len(TEMP_REQUESTS_STORAGE),
        'requests': TEMP_REQUESTS_STORAGE
    }, indent=2)


# Helper function to clear storage (for testing)
@staff_member_required
def clear_temp_storage(request):
    """Clear temporary storage - for testing only"""
    global TEMP_REQUESTS_STORAGE
    TEMP_REQUESTS_STORAGE.clear()
    messages.success(request, _('Temporary storage cleared.'))
    return redirect('borrowing:admin_dashboard')
