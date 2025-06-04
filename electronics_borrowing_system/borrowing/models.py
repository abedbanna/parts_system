# borrowing/views.py - Complete implementation with your inventory model

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
    print("✅ Borrowing models loaded successfully")
except ImportError:
    MODELS_AVAILABLE = False
    print("⚠️ Borrowing models not available, using temp storage")

# Import your actual inventory models
try:
    from inventory.models import ElectronicPart, Category, InventoryTransaction

    INVENTORY_AVAILABLE = True
    print("✅ Inventory models loaded successfully")
except ImportError:
    INVENTORY_AVAILABLE = False
    print("⚠️ Inventory models not available")


def get_available_parts():
    """Get available parts from your inventory system"""
    if not INVENTORY_AVAILABLE:
        return []

    try:
        # Get parts that are available for borrowing using your model's method
        available_parts = ElectronicPart.objects.filter(
            is_active=True
        ).select_related('category').order_by('category__name_ar', 'name_ar')

        # Filter only parts that are actually available for borrowing
        borrowable_parts = [part for part in available_parts if part.is_available_for_borrowing]

        return borrowable_parts
    except Exception as e:
        print(f"Error fetching inventory parts: {e}")
        return []


def get_popular_parts():
    """Get most popular/frequently borrowed parts"""
    if not INVENTORY_AVAILABLE:
        return []

    try:
        # Get parts with highest available quantity (you can modify this logic)
        popular_parts = ElectronicPart.objects.filter(
            is_active=True,
            status='available',
            available_quantity__gt=0
        ).order_by('-available_quantity')[:10]

        return popular_parts
    except Exception as e:
        print(f"Error fetching popular parts: {e}")
        return []


def get_categories_with_parts():
    """Get categories with their available parts"""
    if not INVENTORY_AVAILABLE:
        return {}

    try:
        categories = {}

        # Get all active categories with parts
        active_categories = Category.objects.filter(
            is_active=True,
            parts__is_active=True,
            parts__status='available',
            parts__available_quantity__gt=0
        ).distinct().prefetch_related('parts')

        for category in active_categories:
            # Get available parts for this category
            available_parts = [
                part for part in category.parts.all()
                if part.is_available_for_borrowing
            ]

            if available_parts:
                categories[category.name] = available_parts

        return categories
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return {}


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


@login_required
def dashboard(request):
    """Student dashboard with inventory integration"""

    # Check if user is admin and redirect
    if request.user.is_staff:
        print(f"Admin user {request.user.username} accessing dashboard - redirecting to admin")
        return redirect('/borrowing/admin/')

    # Try database first, fall back to temp storage
    user_requests_db = None
    if MODELS_AVAILABLE:
        try:
            user_requests_db = BorrowRequest.objects.filter(student=request.user)
        except Exception as e:
            print(f"Database query error: {e}")

    if user_requests_db is not None:
        # Database version
        try:
            context = {
                'active_borrows': user_requests_db.filter(status__in=['approved', 'borrowed']).count(),
                'pending_requests': user_requests_db.filter(status__in=['submitted', 'pending']).count(),
                'recent_requests': [convert_request_to_dict(req) for req in
                                    user_requests_db.order_by('-created_at')[:5]],
                'available_parts_count': len(get_available_parts()) if INVENTORY_AVAILABLE else 50,
                'total_requests': user_requests_db.count(),
            }
        except Exception as e:
            print(f"Database query error: {e}")
            user_requests_db = None

    if user_requests_db is None:
        # Temp storage version
        user_requests = [req for req in TEMP_REQUESTS_STORAGE if req.get('user_id') == request.user.id]
        context = {
            'active_borrows': len([req for req in user_requests if req.get('status') == 'approved']),
            'pending_requests': len([req for req in user_requests if req.get('status') == 'pending']),
            'recent_requests': user_requests[-5:],
            'available_parts_count': len(get_available_parts()) if INVENTORY_AVAILABLE else 50,
            'total_requests': len(user_requests),
        }

    return render(request, 'borrowing/dashboard.html', context)


@login_required
def create_request(request):
    """Enhanced create request function with your inventory integration"""

    # Redirect admin users to admin dashboard
    if request.user.is_staff:
        messages.info(request, 'المديرين لا يحتاجون لإنشاء طلبات استعارة')
        return redirect('/borrowing/admin/')

    if request.method == 'POST':
        # Debug: Log all POST data
        print("=== POST DATA RECEIVED ===")
        for key, value in request.POST.items():
            print(f"{key}: {value}")

        purpose = request.POST.get('purpose', '').strip()
        expected_return_date = request.POST.get('expected_return_date', '').strip()
        student_notes = request.POST.get('student_notes', '').strip()

        if not purpose or not expected_return_date:
            messages.error(request, _('الرجاء ملء جميع الحقول المطلوبة.'))
            return render(request, 'borrowing/create_request.html', get_form_context())

        # Collect parts data from form
        parts_data = []
        part_index = 0

        while f'part_name_{part_index}' in request.POST:
            part_name = request.POST.get(f'part_name_{part_index}', '').strip()
            if part_name:  # Only process non-empty parts
                quantity = int(request.POST.get(f'quantity_{part_index}', 1))
                condition = request.POST.get(f'condition_{part_index}', 'excellent')

                # Try to find the part in your inventory
                inventory_part = None
                if INVENTORY_AVAILABLE:
                    try:
                        # Search by name (both Arabic and English) or part number
                        inventory_part = ElectronicPart.objects.filter(
                            Q(name_ar__icontains=part_name) |
                            Q(name_en__icontains=part_name) |
                            Q(part_number__icontains=part_name),
                            is_active=True
                        ).first()

                        # Check availability using your model's method
                        if inventory_part and not inventory_part.can_borrow(quantity):
                            messages.error(request,
                                           f'الكمية المطلوبة من {part_name} ({quantity}) أكثر من المتوفر ({inventory_part.available_quantity})')
                            return render(request, 'borrowing/create_request.html', get_form_context())
                    except Exception as e:
                        print(f"Error checking inventory for {part_name}: {e}")

                parts_data.append({
                    'name': part_name,
                    'quantity': quantity,
                    'condition': condition,
                    'inventory_part': inventory_part
                })

            part_index += 1

        if not parts_data:
            messages.error(request, _('يرجى إضافة قطعة واحدة على الأقل.'))
            return render(request, 'borrowing/create_request.html', get_form_context())

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

                    # Create records for each part
                    for part_data in parts_data:
                        borrow_record = BorrowRecord.objects.create(
                            request=borrow_request,
                            part_name=part_data['name'],
                            quantity=part_data['quantity'],
                            condition_borrowed=part_data['condition']
                        )

                        # Link to your inventory if available
                        if part_data['inventory_part']:
                            inventory_part = part_data['inventory_part']
                            borrow_record.inventory_part = inventory_part
                            borrow_record.part_description = inventory_part.description
                            borrow_record.part_number = inventory_part.part_number
                            borrow_record.save()

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
            'parts': [{'name': p['name'], 'quantity': p['quantity']} for p in parts_data],
            'status': 'pending',
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'total_parts': len(parts_data)
        }

        TEMP_REQUESTS_STORAGE.append(request_data)
        messages.success(request, _(f'تم إنشاء طلب الاستعارة بنجاح! رقم الطلب: {request_data["id"]}'))
        return redirect('/borrowing/')

    # GET request - show form with your inventory data
    return render(request, 'borrowing/create_request.html', get_form_context())


def get_form_context():
    """Get context data for the form using your inventory"""
    available_parts = get_available_parts()
    popular_parts = get_popular_parts()
    categories = get_categories_with_parts()

    # Convert to format expected by template
    available_parts_list = []
    for part in available_parts:
        available_parts_list.append({
            'id': part.id,
            'name': part.name,  # Uses your model's property that returns name based on language
            'name_ar': part.name_ar,
            'name_en': part.name_en,
            'category': part.category.name if part.category else 'Unknown',
            'quantity': part.available_quantity,
            'total_quantity': part.total_quantity,
            'description': part.description,  # Uses your model's property
            'part_number': part.part_number,
            'location': f"{part.location} {part.shelf_number}".strip(),
            'condition': part.get_condition_display(),
            'manufacturer': part.manufacturer,
            'model': part.model,
            'specifications': part.specifications,
            'is_low_stock': part.is_low_stock,
        })

    # Convert popular parts
    popular_parts_list = []
    for part in popular_parts:
        popular_parts_list.append({
            'id': part.id,
            'name': part.name,
            'category': part.category.name if part.category else 'Unknown',
            'quantity': part.available_quantity,
            'description': part.description,
        })

    # Convert categories
    categories_dict = {}
    for category_name, parts in categories.items():
        categories_dict[category_name] = []
        for part in parts:
            categories_dict[category_name].append({
                'id': part.id,
                'name': part.name,
                'quantity': part.available_quantity,
                'description': part.description,
                'part_number': part.part_number,
                'location': f"{part.location} {part.shelf_number}".strip(),
            })

    return {
        'form': {},
        'available_parts': available_parts_list,
        'categories': categories_dict,
        'popular_parts': popular_parts_list,
        'inventory_available': INVENTORY_AVAILABLE,
        'total_parts_count': len(available_parts_list)
    }


@login_required
def parts_autocomplete(request):
    """AJAX endpoint for parts autocomplete using your inventory"""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    if INVENTORY_AVAILABLE:
        try:
            # Search in your inventory using both Arabic and English names
            parts = ElectronicPart.objects.filter(
                Q(name_ar__icontains=query) |
                Q(name_en__icontains=query) |
                Q(part_number__icontains=query) |
                Q(description_ar__icontains=query) |
                Q(description_en__icontains=query),
                is_active=True
            ).select_related('category')[:15]  # Limit to 15 results

            for part in parts:
                # Only include parts that are available for borrowing
                if part.is_available_for_borrowing:
                    results.append({
                        'id': part.id,
                        'name': part.name,
                        'name_ar': part.name_ar,
                        'name_en': part.name_en,
                        'part_number': part.part_number,
                        'description': part.description,
                        'quantity': part.available_quantity,
                        'total_quantity': part.total_quantity,
                        'category': part.category.name if part.category else 'Unknown',
                        'location': f"{part.location} {part.shelf_number}".strip(),
                        'condition': part.get_condition_display(),
                        'manufacturer': part.manufacturer,
                        'model': part.model,
                        'is_low_stock': part.is_low_stock,
                    })
        except Exception as e:
            print(f"Error in parts autocomplete: {e}")

    return JsonResponse({'results': results})


@login_required
def get_part_details(request, part_id):
    """Get detailed information about a specific part from your inventory"""
    if not INVENTORY_AVAILABLE:
        return JsonResponse({
            'error': 'Inventory system not available'
        }, status=503)

    try:
        part = get_object_or_404(ElectronicPart, id=part_id, is_active=True)

        data = {
            'id': part.id,
            'name': part.name,
            'name_ar': part.name_ar,
            'name_en': part.name_en,
            'part_number': part.part_number,
            'description': part.description,
            'description_ar': part.description_ar,
            'description_en': part.description_en,
            'quantity': part.available_quantity,
            'total_quantity': part.total_quantity,
            'minimum_stock': part.minimum_stock,
            'category': {
                'id': part.category.id,
                'name': part.category.name,
                'name_ar': part.category.name_ar,
                'name_en': part.category.name_en,
            } if part.category else None,
            'location': part.location,
            'shelf_number': part.shelf_number,
            'condition': part.condition,
            'condition_display': part.get_condition_display(),
            'status': part.status,
            'status_display': part.get_status_display(),
            'manufacturer': part.manufacturer,
            'model': part.model,
            'specifications': part.specifications,
            'purchase_date': part.purchase_date.strftime('%Y-%m-%d') if part.purchase_date else None,
            'purchase_price': str(part.purchase_price) if part.purchase_price else None,
            'supplier': part.supplier,
            'image_url': part.image.url if part.image else None,
            'is_low_stock': part.is_low_stock,
            'is_available_for_borrowing': part.is_available_for_borrowing,
            'notes': part.notes,
        }

        return JsonResponse(data)
    except Exception as e:
        print(f"Error getting part details: {e}")
        return JsonResponse({
            'error': 'Part not found or error occurred'
        }, status=404)


@login_required
def request_list(request):
    """Compatible request list function"""

    # Redirect admin users to admin dashboard
    if request.user.is_staff:
        return redirect('/borrowing/admin/')

    # Try database first
    user_requests_db = None
    if MODELS_AVAILABLE:
        try:
            user_requests_db = BorrowRequest.objects.filter(student=request.user).order_by('-created_at')
        except Exception as e:
            print(f"Database query error: {e}")

    if user_requests_db is not None:
        try:
            requests_list = [convert_request_to_dict(req) for req in user_requests_db]
        except Exception as e:
            print(f"Database query error: {e}")
            user_requests_db = None

    if user_requests_db is None:
        # Fall back to temp storage
        requests_list = [req for req in TEMP_REQUESTS_STORAGE if req.get('user_id') == request.user.id]

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
    """Enhanced approve request function with inventory integration"""

    # Try database first
    if MODELS_AVAILABLE:
        try:
            with transaction.atomic():
                borrow_request = get_object_or_404(BorrowRequest, pk=pk)

                if borrow_request.status not in ['submitted', 'pending']:
                    messages.warning(request, _('لقد تم معالجة هذا الطلب مسبقاً.'))
                    return redirect('/borrowing/admin/')

                # Check inventory availability and update quantities
                if INVENTORY_AVAILABLE:
                    for record in borrow_request.records.all():
                        if record.inventory_part:
                            inventory_part = record.inventory_part

                            # Check if we can still borrow this quantity
                            if not inventory_part.can_borrow(record.quantity):
                                messages.error(request,
                                               f'عذراً، الكمية المطلوبة من {record.part_name} غير متوفرة حالياً')
                                return redirect('/borrowing/admin/')

                            # Actually borrow the parts (updates inventory)
                            success = inventory_part.borrow(record.quantity)
                            if not success:
                                messages.error(request,
                                               f'فشل في حجز {record.part_name} من المخزون')
                                return redirect('/borrowing/admin/')

                            # Create inventory transaction record
                            InventoryTransaction.objects.create(
                                part=inventory_part,
                                transaction_type='borrow',
                                quantity=-record.quantity,  # Negative because it's borrowed
                                previous_quantity=inventory_part.available_quantity + record.quantity,
                                new_quantity=inventory_part.available_quantity,
                                performed_by=request.user,
                                reason=f'Approved borrow request #{borrow_request.id}',
                                reference_id=str(borrow_request.id)
                            )

                # Approve the request
                borrow_request.status = 'approved'
                borrow_request.approved_by = request.user
                borrow_request.approval_date = timezone.now()
                borrow_request.save()

                messages.success(request, _(f'تم الموافقة على الطلب #{pk} بنجاح! تم تحديث المخزون.'))
                logger.info(f"Request {pk} approved by {request.user.username}")
                return redirect('/borrowing/admin/')

        except Exception as e:
            print(f"Database error during approval: {e}")
