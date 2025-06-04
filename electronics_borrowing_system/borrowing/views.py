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


# Improved parts search views for borrowing/views.py

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
import json


@login_required
@require_GET
def parts_autocomplete(request):
    """AJAX endpoint for parts autocomplete using your inventory"""
    query = request.GET.get('q', '').strip()

    # Return empty results for short queries
    if len(query) < 2:
        return JsonResponse({
            'results': [],
            'message': 'Query too short',
            'query': query
        })

    results = []
    error_message = None

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
            ).select_related('category').order_by(
                'category__name_ar',
                'name_ar'
            )[:20]  # Limit to 20 results for performance

            for part in parts:
                # Only include parts that are available for borrowing
                if part.is_available_for_borrowing:
                    results.append({
                        'id': part.id,
                        'name': part.name,  # Uses your model's property
                        'name_ar': part.name_ar,
                        'name_en': part.name_en,
                        'part_number': part.part_number or '',
                        'description': part.description or '',  # Uses your model's property
                        'description_ar': part.description_ar or '',
                        'description_en': part.description_en or '',
                        'quantity': part.available_quantity,
                        'total_quantity': part.total_quantity,
                        'category': part.category.name if part.category else 'غير محدد',
                        'category_id': part.category.id if part.category else None,
                        'location': part.location or '',
                        'shelf_number': part.shelf_number or '',
                        'full_location': f"{part.location} {part.shelf_number}".strip(),
                        'condition': part.condition,
                        'condition_display': part.get_condition_display(),
                        'status': part.status,
                        'status_display': part.get_status_display(),
                        'manufacturer': part.manufacturer or '',
                        'model': part.model or '',
                        'is_low_stock': part.is_low_stock,
                        'minimum_stock': part.minimum_stock,
                        'image_url': part.image.url if part.image else None,
                        # Add specifications summary
                        'has_specifications': bool(part.specifications),
                        'specs_count': len(part.specifications) if part.specifications else 0,
                    })

            print(f"✅ Found {len(results)} parts for query: '{query}'")

        except Exception as e:
            error_message = f"Database error: {str(e)}"
            print(f"❌ Error in parts autocomplete: {e}")
            results = []
    else:
        error_message = "Inventory system not available"
        print("⚠️ Inventory system not available for autocomplete")

    # Prepare response
    response_data = {
        'results': results,
        'total_found': len(results),
        'query': query,
        'inventory_available': INVENTORY_AVAILABLE,
    }

    if error_message:
        response_data['error'] = error_message

    # Add cache headers for performance
    response = JsonResponse(response_data)
    response['Cache-Control'] = 'max-age=300'  # Cache for 5 minutes
    return response


@login_required
@require_GET
def get_part_details(request, part_id):
    """Get detailed information about a specific part from your inventory"""
    if not INVENTORY_AVAILABLE:
        return JsonResponse({
            'error': 'Inventory system not available',
            'message': 'The inventory system is currently not connected'
        }, status=503)

    try:
        part = get_object_or_404(ElectronicPart, id=part_id, is_active=True)

        # Get recent transaction history for this part
        recent_transactions = []
        if hasattr(part, 'transactions'):
            recent_transactions = list(
                part.transactions.order_by('-created_at')[:5].values(
                    'transaction_type', 'quantity', 'created_at', 'reason'
                )
            )

        # Get specifications in a more structured format
        specifications = []
        if part.specifications:
            for key, value in part.specifications.items():
                specifications.append({
                    'name': key,
                    'value': value
                })

        data = {
            'id': part.id,
            'name': part.name,
            'name_ar': part.name_ar,
            'name_en': part.name_en,
            'part_number': part.part_number or '',
            'description': part.description,
            'description_ar': part.description_ar or '',
            'description_en': part.description_en or '',

            # Quantities
            'available_quantity': part.available_quantity,
            'total_quantity': part.total_quantity,
            'minimum_stock': part.minimum_stock,
            'is_low_stock': part.is_low_stock,

            # Category information
            'category': {
                'id': part.category.id,
                'name': part.category.name,
                'name_ar': part.category.name_ar,
                'name_en': part.category.name_en,
            } if part.category else None,

            # Location
            'location': part.location or '',
            'shelf_number': part.shelf_number or '',
            'full_location': f"{part.location} {part.shelf_number}".strip(),

            # Status and condition
            'condition': part.condition,
            'condition_display': part.get_condition_display(),
            'status': part.status,
            'status_display': part.get_status_display(),
            'is_available_for_borrowing': part.is_available_for_borrowing,

            # Technical details
            'manufacturer': part.manufacturer or '',
            'model': part.model or '',
            'specifications': specifications,
            'notes': part.notes or '',

            # Purchase information
            'purchase_date': part.purchase_date.strftime('%Y-%m-%d') if part.purchase_date else None,
            'purchase_price': str(part.purchase_price) if part.purchase_price else None,
            'supplier': part.supplier or '',

            # Media
            'image_url': part.image.url if part.image else None,
            'has_image': bool(part.image),

            # Administrative
            'added_by': part.added_by.get_full_name() if part.added_by else 'غير معروف',
            'created_at': part.created_at.strftime('%Y-%m-%d %H:%M') if hasattr(part, 'created_at') else None,
            'updated_at': part.updated_at.strftime('%Y-%m-%d %H:%M') if hasattr(part, 'updated_at') else None,

            # Recent activity
            'recent_transactions': recent_transactions,
            'has_recent_activity': len(recent_transactions) > 0,
        }

        return JsonResponse(data)

    except ElectronicPart.DoesNotExist:
        return JsonResponse({
            'error': 'Part not found',
            'message': f'Part with ID {part_id} does not exist or is not active'
        }, status=404)
    except Exception as e:
        print(f"Error getting part details for ID {part_id}: {e}")
        return JsonResponse({
            'error': 'Server error',
            'message': 'An error occurred while fetching part details'
        }, status=500)


# Enhanced search function for inventory browsing
@login_required
@require_GET
def inventory_search(request):
    """Advanced search endpoint for inventory browsing"""
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', None)
    condition = request.GET.get('condition', None)
    available_only = request.GET.get('available_only', 'true').lower() == 'true'
    limit = min(int(request.GET.get('limit', 50)), 100)  # Max 100 results

    if not INVENTORY_AVAILABLE:
        return JsonResponse({
            'error': 'Inventory system not available',
            'results': [],
            'total': 0
        })

    try:
        # Build the query
        parts_query = ElectronicPart.objects.filter(is_active=True)

        # Apply text search
        if query and len(query) >= 2:
            parts_query = parts_query.filter(
                Q(name_ar__icontains=query) |
                Q(name_en__icontains=query) |
                Q(part_number__icontains=query) |
                Q(description_ar__icontains=query) |
                Q(description_en__icontains=query) |
                Q(manufacturer__icontains=query) |
                Q(model__icontains=query)
            )

        # Apply category filter
        if category_id:
            parts_query = parts_query.filter(category_id=category_id)

        # Apply condition filter
        if condition:
            parts_query = parts_query.filter(condition=condition)

        # Apply availability filter
        if available_only:
            parts_query = parts_query.filter(
                status='available',
                available_quantity__gt=0
            )

        # Get total count before limiting
        total_count = parts_query.count()

        # Apply ordering and limit
        parts = parts_query.select_related('category').order_by(
            'category__name_ar', 'name_ar'
        )[:limit]

        # Build results
        results = []
        categories_found = set()

        for part in parts:
            if available_only and not part.is_available_for_borrowing:
                continue

            categories_found.add(part.category.name if part.category else 'غير محدد')

            results.append({
                'id': part.id,
                'name': part.name,
                'name_ar': part.name_ar,
                'name_en': part.name_en,
                'part_number': part.part_number or '',
                'description': part.description or '',
                'quantity': part.available_quantity,
                'total_quantity': part.total_quantity,
                'category': part.category.name if part.category else 'غير محدد',
                'location': f"{part.location} {part.shelf_number}".strip(),
                'condition': part.get_condition_display(),
                'status': part.get_status_display(),
                'manufacturer': part.manufacturer or '',
                'model': part.model or '',
                'is_low_stock': part.is_low_stock,
                'is_available_for_borrowing': part.is_available_for_borrowing,
                'image_url': part.image.url if part.image else None,
            })

        return JsonResponse({
            'results': results,
            'total_found': len(results),
            'total_in_db': total_count,
            'categories_found': list(categories_found),
            'query': query,
            'filters': {
                'category_id': category_id,
                'condition': condition,
                'available_only': available_only,
            }
        })

    except Exception as e:
        print(f"Error in inventory search: {e}")
        return JsonResponse({
            'error': 'Search failed',
            'message': str(e),
            'results': [],
            'total': 0
        }, status=500)


# Helper function to validate part availability before form submission
@login_required
@require_http_methods(["POST"])
@csrf_exempt  # Only if you handle CSRF manually
def validate_parts_availability(request):
    """Validate that all requested parts are still available"""
    try:
        data = json.loads(request.body)
        parts_to_check = data.get('parts', [])

        if not INVENTORY_AVAILABLE:
            return JsonResponse({
                'valid': True,  # Allow submission if inventory not available
                'message': 'Inventory system not available for validation'
            })

        validation_results = []
        all_valid = True

        for part_request in parts_to_check:
            part_name = part_request.get('name', '')
            requested_quantity = int(part_request.get('quantity', 1))

            # Find the part
            part = None
            if part_request.get('part_id'):
                part = ElectronicPart.objects.filter(
                    id=part_request['part_id'],
                    is_active=True
                ).first()
            else:
                # Search by name
                part = ElectronicPart.objects.filter(
                    Q(name_ar__icontains=part_name) |
                    Q(name_en__icontains=part_name) |
                    Q(part_number__icontains=part_name),
                    is_active=True
                ).first()

            if part:
                can_borrow = part.can_borrow(requested_quantity)
                validation_results.append({
                    'part_name': part_name,
                    'requested_quantity': requested_quantity,
                    'available_quantity': part.available_quantity,
                    'can_borrow': can_borrow,
                    'is_available_for_borrowing': part.is_available_for_borrowing,
                    'part_id': part.id
                })

                if not can_borrow:
                    all_valid = False
            else:
                validation_results.append({
                    'part_name': part_name,
                    'requested_quantity': requested_quantity,
                    'can_borrow': False,
                    'error': 'Part not found in inventory'
                })
                all_valid = False

        return JsonResponse({
            'valid': all_valid,
            'results': validation_results,
            'inventory_available': INVENTORY_AVAILABLE
        })

    except Exception as e:
        print(f"Error in parts validation: {e}")
        return JsonResponse({
            'valid': False,
            'error': str(e)
        }, status=500)


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
    """Compatible admin dashboard with inventory stats"""

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
                'models_available': True,
                'inventory_available': INVENTORY_AVAILABLE,
                'inventory_parts_count': len(get_available_parts()) if INVENTORY_AVAILABLE else 0
            }, indent=2)
        except Exception as e:
            print(f"Database error in debug_requests: {e}")

    # Fall back to temp storage
    return JsonResponse({
        'storage_type': 'temporary',
        'total_requests': len(TEMP_REQUESTS_STORAGE),
        'requests': TEMP_REQUESTS_STORAGE,
        'models_available': MODELS_AVAILABLE,
        'inventory_available': INVENTORY_AVAILABLE,
        'inventory_parts_count': len(get_available_parts()) if INVENTORY_AVAILABLE else 0
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
