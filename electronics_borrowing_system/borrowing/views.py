# borrowing/views.py - FIXED VERSION (No scope errors)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from datetime import datetime, date, timedelta
import json
import logging

logger = logging.getLogger(__name__)

# Temporary storage for compatibility
TEMP_REQUESTS_STORAGE = []

# Check if models are available at module level
try:
    from .models import BorrowRequest, BorrowRecord

    MODELS_AVAILABLE = True
    print("✅ Database models loaded successfully")
except ImportError:
    MODELS_AVAILABLE = False
    print("⚠️ Database models not available, using temp storage")


def convert_request_to_dict(request_obj):
    """Convert model instance to dict format for template compatibility"""
    if not request_obj:
        return {}

    return {
        'id': request_obj.id,
        'user_id': request_obj.student.id,
        'user_name': request_obj.student.get_full_name() or request_obj.student.username,
        'purpose': request_obj.purpose,
        'expected_return_date': request_obj.expected_return_date.strftime(
            '%Y-%m-%d') if request_obj.expected_return_date else '',
        'student_notes': getattr(request_obj, 'student_notes', ''),
        'status': request_obj.status,
        'created_at': request_obj.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(request_obj,
                                                                                   'created_at') else request_obj.request_date.strftime(
            '%Y-%m-%d %H:%M'),
        'total_parts': request_obj.records.count() if hasattr(request_obj, 'records') else getattr(request_obj,
                                                                                                   'total_parts', 0)
    }


def get_requests_from_database(user=None):
    """Get requests from database with error handling"""
    if not MODELS_AVAILABLE:
        return None

    try:
        if user:
            return BorrowRequest.objects.filter(student=user)
        else:
            return BorrowRequest.objects.all()
    except Exception as e:
        print(f"Database error: {e}")
        return None


def get_requests_from_temp_storage(user_id=None):
    """Get requests from temporary storage"""
    if user_id:
        return [req for req in TEMP_REQUESTS_STORAGE if req.get('user_id') == user_id]
    return TEMP_REQUESTS_STORAGE


@login_required
def dashboard(request):
    """Compatible dashboard that works with both database and temp storage"""

    # Check if user is admin and redirect
    if request.user.is_staff:
        print(f"Admin user {request.user.username} accessing dashboard - redirecting to admin")
        return redirect('/borrowing/admin/')

    # Try database first, fall back to temp storage
    user_requests_db = get_requests_from_database(user=request.user)

    if user_requests_db is not None:
        # Database version
        try:
            context = {
                'active_borrows': user_requests_db.filter(status__in=['approved', 'borrowed']).count(),
                'pending_requests': user_requests_db.filter(status__in=['submitted', 'pending']).count(),
                'recent_requests': [convert_request_to_dict(req) for req in
                                    user_requests_db.order_by('-created_at')[:5]],
                'available_parts_count': 50,
                'total_requests': user_requests_db.count(),
            }
        except Exception as e:
            print(f"Database query error: {e}")
            user_requests_db = None

    if user_requests_db is None:
        # Temp storage version
        user_requests = get_requests_from_temp_storage(request.user.id)
        context = {
            'active_borrows': len([req for req in user_requests if req.get('status') == 'approved']),
            'pending_requests': len([req for req in user_requests if req.get('status') == 'pending']),
            'recent_requests': user_requests[-5:],
            'available_parts_count': 50,
            'total_requests': len(user_requests),
        }

    return render(request, 'borrowing/dashboard.html', context)


@login_required
def create_request(request):
    """Compatible create request function"""

    # Redirect admin users to admin dashboard
    if request.user.is_staff:
        messages.info(request, 'المديرين لا يحتاجون لإنشاء طلبات استعارة')
        return redirect('/borrowing/admin/')

    if request.method == 'POST':
        purpose = request.POST.get('purpose', '').strip()
        expected_return_date = request.POST.get('expected_return_date', '').strip()
        student_notes = request.POST.get('student_notes', '').strip()

        if not purpose or not expected_return_date:
            messages.error(request, _('الرجاء ملء جميع الحقول المطلوبة.'))
            return render(request, 'borrowing/create_request.html', {'form': {}})

        # Try database first
        if MODELS_AVAILABLE:
            try:
                with transaction.atomic():
                    # Create the request
                    borrow_request = BorrowRequest.objects.create(
                        student=request.user,
                        purpose=purpose,
                        expected_return_date=expected_return_date,
                        student_notes=student_notes,
                        status='submitted'
                    )

                    # Add sample record
                    BorrowRecord.objects.create(
                        request=borrow_request,
                        part_name='Arduino Uno',
                        quantity=1
                    )

                    messages.success(request, _(f'تم إنشاء طلب الاستعارة بنجاح! رقم الطلب: {borrow_request.id}'))
                    return redirect('/borrowing/')

            except Exception as e:
                print(f"Database error during request creation: {e}")
                messages.error(request, _('حدث خطأ في قاعدة البيانات. جاري المحاولة بالطريقة البديلة...'))

        # Fall back to temp storage
        request_data = {
            'id': len(TEMP_REQUESTS_STORAGE) + 1,
            'user_id': request.user.id,
            'user_name': request.user.get_full_name() or request.user.username,
            'purpose': purpose,
            'expected_return_date': expected_return_date,
            'student_notes': student_notes,
            'parts': [{'name': 'Arduino Uno', 'quantity': 1}],
            'status': 'pending',
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'total_parts': 1
        }

        TEMP_REQUESTS_STORAGE.append(request_data)
        messages.success(request, _(f'تم إنشاء طلب الاستعارة بنجاح! رقم الطلب: {request_data["id"]}'))
        return redirect('/borrowing/')

    # GET request - show empty form
    context = {
        'form': {},
        'available_parts': [
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
    """Compatible request list function"""

    # Redirect admin users to admin dashboard
    if request.user.is_staff:
        return redirect('/borrowing/admin/')

    # Try database first
    user_requests_db = get_requests_from_database(user=request.user)

    if user_requests_db is not None:
        try:
            requests_list = [convert_request_to_dict(req) for req in user_requests_db.order_by('-created_at')]
        except Exception as e:
            print(f"Database query error: {e}")
            user_requests_db = None

    if user_requests_db is None:
        # Fall back to temp storage
        requests_list = get_requests_from_temp_storage(request.user.id)

    # Sort by creation date (newest first)
    requests_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    context = {
        'requests': requests_list,
        'total_requests': len(requests_list),
        'pending_count': len([req for req in requests_list if req.get('status') in ['pending', 'submitted']]),
        'approved_count': len([req for req in requests_list if req.get('status') == 'approved']),
    }
    return render(request, 'borrowing/request_list.html', context)


@login_required
def request_detail(request, pk):
    """Compatible request detail function"""

    request_data = None

    # Try database first
    if MODELS_AVAILABLE:
        try:
            if request.user.is_staff:
                borrow_request = get_object_or_404(BorrowRequest, pk=pk)
            else:
                borrow_request = get_object_or_404(BorrowRequest, pk=pk, student=request.user)

            request_data = convert_request_to_dict(borrow_request)
        except Exception as e:
            print(f"Database error in request_detail: {e}")
            request_data = None

    # Fall back to temp storage if database failed
    if request_data is None:
        for req in TEMP_REQUESTS_STORAGE:
            if req.get('id') == int(pk):
                if request.user.is_staff or req.get('user_id') == request.user.id:
                    request_data = req
                    break

    if not request_data:
        messages.error(request, _('Request not found.'))
        if request.user.is_staff:
            return redirect('/borrowing/admin/')
        else:
            return redirect('/borrowing/')

    context = {
        'request_data': request_data,
    }
    return render(request, 'borrowing/request_detail.html', context)


@staff_member_required
def admin_dashboard(request):
    """FIXED: Compatible admin dashboard with no scope errors"""

    print(f"Admin dashboard accessed by: {request.user.username} (staff: {request.user.is_staff})")

    # Try database first
    database_success = False
    if MODELS_AVAILABLE:
        try:
            all_requests_qs = BorrowRequest.objects.all().order_by('-created_at')

            # Filter requests by status using standard QuerySet methods
            pending_requests = all_requests_qs.filter(status__in=['submitted', 'pending'])
            active_borrows = all_requests_qs.filter(status__in=['approved', 'borrowed'])

            # Calculate overdue requests
            today = date.today()
            overdue_requests = all_requests_qs.filter(
                status__in=['approved', 'borrowed'],
                expected_return_date__lt=today
            )

            # Convert to format expected by template
            context = {
                'pending_requests': [convert_request_to_dict(req) for req in pending_requests[:10]],
                'active_borrows': [convert_request_to_dict(req) for req in active_borrows[:10]],
                'overdue_requests': [convert_request_to_dict(req) for req in overdue_requests[:10]],
                'total_pending': pending_requests.count(),
                'total_active': active_borrows.count(),
                'total_overdue': overdue_requests.count(),
                'all_requests': [convert_request_to_dict(req) for req in all_requests_qs[:10]],
            }

            database_success = True
            print(
                f"✅ Database queries successful: {context['total_pending']} pending, {context['total_active']} active")

        except Exception as e:
            print(f"❌ Database error in admin_dashboard: {e}")
            database_success = False

    # Fall back to temp storage if database failed or not available
    if not database_success:
        print("📝 Using temporary storage fallback")

        pending_requests = [req for req in TEMP_REQUESTS_STORAGE if req.get('status') in ['pending', 'submitted']]
        active_borrows = [req for req in TEMP_REQUESTS_STORAGE if req.get('status') == 'approved']

        # Mock overdue logic for temp storage
        overdue_cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M')
        overdue_requests = [req for req in active_borrows if req.get('created_at', '9999-12-31 23:59') < overdue_cutoff]

        context = {
            'pending_requests': pending_requests[:10],
            'active_borrows': active_borrows[:10],
            'overdue_requests': overdue_requests[:10],
            'total_pending': len(pending_requests),
            'total_active': len(active_borrows),
            'total_overdue': len(overdue_requests),
            'all_requests': TEMP_REQUESTS_STORAGE[-10:],
        }

    print(
        f"📊 Final context: {context['total_pending']} pending, {context['total_active']} active, {context['total_overdue']} overdue")
    return render(request, 'borrowing/admin_dashboard.html', context)


@staff_member_required
@require_http_methods(["POST"])
def approve_request(request, pk):
    """Compatible approve request function"""

    # Try database first
    if MODELS_AVAILABLE:
        try:
            with transaction.atomic():
                borrow_request = get_object_or_404(BorrowRequest, pk=pk)

                if borrow_request.status not in ['submitted', 'pending']:
                    messages.warning(request, _('لقد تم معالجة هذا الطلب مسبقاً.'))
                    return redirect('/borrowing/admin/')

                # Approve the request
                borrow_request.status = 'approved'
                borrow_request.approved_by = request.user
                borrow_request.approval_date = timezone.now()
                borrow_request.save()

                messages.success(request, _(f'تم الموافقة على الطلب #{pk} بنجاح!'))
                logger.info(f"Request {pk} approved by {request.user.username}")
                return redirect('/borrowing/admin/')

        except Exception as e:
            print(f"Database error during approval: {e}")
            messages.error(request, _('حدث خطأ في قاعدة البيانات. جاري المحاولة بالطريقة البديلة...'))

    # Fall back to temp storage
    for req in TEMP_REQUESTS_STORAGE:
        if req.get('id') == int(pk):
            req['status'] = 'approved'
            req['approved_at'] = timezone.now().strftime('%Y-%m-%d %H:%M')
            req['approved_by'] = request.user.username
            messages.success(request, _(f'تم الموافقة على الطلب #{pk} بنجاح!'))
            logger.info(f"Request {pk} approved by {request.user.username}")
            break
    else:
        messages.error(request, _('الطلب غير موجود.'))

    return redirect('/borrowing/admin/')


@staff_member_required
@require_http_methods(["POST"])
def reject_request(request, pk):
    """Compatible reject request function"""

    rejection_reason = request.POST.get('reason', 'لم يتم تحديد سبب')

    # Try database first
    if MODELS_AVAILABLE:
        try:
            with transaction.atomic():
                borrow_request = get_object_or_404(BorrowRequest, pk=pk)

                if borrow_request.status not in ['submitted', 'pending']:
                    messages.warning(request, _('لقد تم معالجة هذا الطلب مسبقاً.'))
                    return redirect('/borrowing/admin/')

                # Reject the request
                borrow_request.status = 'rejected'
                borrow_request.rejection_reason = rejection_reason
                borrow_request.save()

                messages.success(request, _(f'تم رفض الطلب #{pk}.'))
                logger.info(f"Request {pk} rejected by {request.user.username}: {rejection_reason}")
                return redirect('/borrowing/admin/')

        except Exception as e:
            print(f"Database error during rejection: {e}")
            messages.error(request, _('حدث خطأ في قاعدة البيانات. جاري المحاولة بالطريقة البديلة...'))

    # Fall back to temp storage
    for req in TEMP_REQUESTS_STORAGE:
        if req.get('id') == int(pk):
            req['status'] = 'rejected'
            req['rejected_at'] = timezone.now().strftime('%Y-%m-%d %H:%M')
            req['rejected_by'] = request.user.username
            req['rejection_reason'] = rejection_reason
            messages.success(request, _(f'تم رفض الطلب #{pk}.'))
            logger.info(f"Request {pk} rejected by {request.user.username}: {rejection_reason}")
            break
    else:
        messages.error(request, _('الطلب غير موجود.'))

    return redirect('/borrowing/admin/')


@login_required
def debug_requests(request):
    """Debug view to see all stored requests"""
    if not request.user.is_staff:
        messages.error(request, _('ممنوع الدخول.'))
        return redirect('/borrowing/')

    # Try database first
    if MODELS_AVAILABLE:
        try:
            all_requests = BorrowRequest.objects.all()
            requests_data = [convert_request_to_dict(req) for req in all_requests]

            return JsonResponse({
                'storage_type': 'database',
                'total_requests': len(requests_data),
                'requests': requests_data,
                'models_available': True
            }, indent=2)
        except Exception as e:
            print(f"Database error in debug_requests: {e}")

    # Fall back to temp storage
    return JsonResponse({
        'storage_type': 'temporary',
        'total_requests': len(TEMP_REQUESTS_STORAGE),
        'requests': TEMP_REQUESTS_STORAGE,
        'models_available': MODELS_AVAILABLE
    }, indent=2)


@staff_member_required
def clear_temp_storage(request):
    """Clear storage - for testing only"""
    global TEMP_REQUESTS_STORAGE

    if MODELS_AVAILABLE:
        try:
            # Clear database records (be careful!)
            if request.GET.get('confirm') == 'yes':
                deleted_count = BorrowRequest.objects.count()
                BorrowRequest.objects.all().delete()
                messages.success(request, _(f'تم مسح {deleted_count} طلب من قاعدة البيانات.'))
            else:
                count = BorrowRequest.objects.count()
                messages.warning(request,
                                 _(f'يوجد {count} طلب في قاعدة البيانات. أضف ?confirm=yes للرابط لتأكيد المسح.'))
        except Exception as e:
            print(f"Cannot clear database: {e}")
            messages.error(request, _(f'لا يمكن مسح قاعدة البيانات: {e}'))

    # Always clear temp storage
    cleared_count = len(TEMP_REQUESTS_STORAGE)
    TEMP_REQUESTS_STORAGE.clear()

    if cleared_count > 0:
        messages.success(request, _(f'تم مسح {cleared_count} طلب من التخزين المؤقت.'))
    else:
        messages.info(request, _('التخزين المؤقت فارغ بالفعل.'))

    return redirect('/borrowing/admin/')
