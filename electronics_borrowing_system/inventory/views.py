# ============================================================================
# inventory/views.py
# ============================================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
import json

# For development, use temporary storage that mimics the models
TEMP_INVENTORY = []
TEMP_CATEGORIES = [
    {'id': 1, 'name_ar': 'الدوائر المتكاملة', 'name_en': 'Integrated Circuits', 'icon': 'fas fa-microchip'},
    {'id': 2, 'name_ar': 'المقاومات', 'name_en': 'Resistors', 'icon': 'fas fa-bolt'},
    {'id': 3, 'name_ar': 'المكثفات', 'name_en': 'Capacitors', 'icon': 'fas fa-battery-half'},
    {'id': 4, 'name_ar': 'المتحكمات', 'name_en': 'Microcontrollers', 'icon': 'fas fa-memory'},
    {'id': 5, 'name_ar': 'الحساسات', 'name_en': 'Sensors', 'icon': 'fas fa-search'},
]


@staff_member_required
def inventory_dashboard(request):
    """Main inventory dashboard for admins"""

    # Calculate statistics
    total_parts = len(TEMP_INVENTORY)
    available_parts = len([p for p in TEMP_INVENTORY if p.get('status') == 'available'])
    low_stock_parts = len([p for p in TEMP_INVENTORY if p.get('available_quantity', 0) <= p.get('minimum_stock', 1)])
    borrowed_parts = len([p for p in TEMP_INVENTORY if p.get('status') == 'borrowed'])

    # Recent additions (last 5)
    recent_additions = TEMP_INVENTORY[-5:] if TEMP_INVENTORY else []

    # Low stock alerts
    low_stock_items = [p for p in TEMP_INVENTORY if p.get('available_quantity', 0) <= p.get('minimum_stock', 1)]

    # Parts by category
    category_stats = {}
    for part in TEMP_INVENTORY:
        cat_id = part.get('category_id', 1)
        if cat_id not in category_stats:
            category_stats[cat_id] = 0
        category_stats[cat_id] += 1

    context = {
        'total_parts': total_parts,
        'available_parts': available_parts,
        'low_stock_parts': low_stock_parts,
        'borrowed_parts': borrowed_parts,
        'recent_additions': recent_additions,
        'low_stock_items': low_stock_items,
        'categories': TEMP_CATEGORIES,
        'category_stats': category_stats,
    }

    return render(request, 'inventory/dashboard.html', context)


@staff_member_required
def add_part(request):
    """Add new electronic part to inventory"""

    if request.method == 'POST':
        try:
            # Extract form data
            part_data = {
                'id': len(TEMP_INVENTORY) + 1,
                'name_ar': request.POST.get('name_ar'),
                'name_en': request.POST.get('name_en'),
                'description_ar': request.POST.get('description_ar', ''),
                'description_en': request.POST.get('description_en', ''),
                'category_id': int(request.POST.get('category', 1)),
                'part_number': request.POST.get('part_number'),
                'manufacturer': request.POST.get('manufacturer', ''),
                'model': request.POST.get('model', ''),
                'total_quantity': int(request.POST.get('total_quantity', 1)),
                'available_quantity': int(request.POST.get('total_quantity', 1)),
                'minimum_stock': int(request.POST.get('minimum_stock', 1)),
                'condition': request.POST.get('condition', 'excellent'),
                'status': 'available',
                'location': request.POST.get('location', ''),
                'shelf_number': request.POST.get('shelf_number', ''),
                'purchase_price': float(request.POST.get('purchase_price', 0)) if request.POST.get(
                    'purchase_price') else None,
                'supplier': request.POST.get('supplier', ''),
                'notes': request.POST.get('notes', ''),
                'added_by': request.user.username,
                'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
                'is_active': True,
            }

            # Validate required fields
            if not all([part_data['name_ar'], part_data['part_number']]):
                messages.error(request, 'الاسم العربي ورقم القطعة مطلوبان')
                return render(request, 'inventory/add_part.html', {
                    'categories': TEMP_CATEGORIES,
                    'form_data': request.POST
                })

            # Check for duplicate part number
            if any(p.get('part_number') == part_data['part_number'] for p in TEMP_INVENTORY):
                messages.error(request, 'رقم القطعة موجود بالفعل')
                return render(request, 'inventory/add_part.html', {
                    'categories': TEMP_CATEGORIES,
                    'form_data': request.POST
                })

            # Add to inventory
            TEMP_INVENTORY.append(part_data)

            messages.success(request, f'تم إضافة القطعة {part_data["name_ar"]} بنجاح')
            return redirect('inventory:dashboard')

        except (ValueError, TypeError) as e:
            messages.error(request, f'خطأ في البيانات المدخلة: {str(e)}')

    context = {
        'categories': TEMP_CATEGORIES,
        'conditions': [
            ('excellent', 'ممتاز'),
            ('good', 'جيد'),
            ('fair', 'مقبول'),
        ]
    }
    return render(request, 'inventory/add_part.html', context)


@staff_member_required
def part_list(request):
    """List all inventory parts with search and filtering"""

    # Get search and filter parameters
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    condition = request.GET.get('condition', '')

    # Filter parts
    parts = TEMP_INVENTORY.copy()

    if search:
        parts = [p for p in parts if
                 search.lower() in p.get('name_ar', '').lower() or
                 search.lower() in p.get('name_en', '').lower() or
                 search.lower() in p.get('part_number', '').lower()]

    if category:
        parts = [p for p in parts if str(p.get('category_id')) == category]

    if status:
        parts = [p for p in parts if p.get('status') == status]

    if condition:
        parts = [p for p in parts if p.get('condition') == condition]

    # Pagination
    paginator = Paginator(parts, 10)  # 10 parts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'parts': page_obj,
        'categories': TEMP_CATEGORIES,
        'search': search,
        'selected_category': category,
        'selected_status': status,
        'selected_condition': condition,
        'total_parts': len(parts),
    }

    return render(request, 'inventory/part_list.html', context)


@staff_member_required
def part_detail(request, pk):
    """View detailed information about a specific part"""

    # Find part
    part = None
    for p in TEMP_INVENTORY:
        if p.get('id') == int(pk):
            part = p
            break

    if not part:
        messages.error(request, 'القطعة غير موجودة')
        return redirect('inventory:part_list')

    # Get category info
    category = next((c for c in TEMP_CATEGORIES if c['id'] == part.get('category_id')), None)

    context = {
        'part': part,
        'category': category,
    }

    return render(request, 'inventory/part_detail.html', context)


@staff_member_required
def edit_part(request, pk):
    """Edit existing part"""

    # Find part
    part = None
    part_index = None
    for i, p in enumerate(TEMP_INVENTORY):
        if p.get('id') == int(pk):
            part = p
            part_index = i
            break

    if not part:
        messages.error(request, 'القطعة غير موجودة')
        return redirect('inventory:part_list')

    if request.method == 'POST':
        try:
            # Update part data
            updated_part = part.copy()
            updated_part.update({
                'name_ar': request.POST.get('name_ar'),
                'name_en': request.POST.get('name_en'),
                'description_ar': request.POST.get('description_ar', ''),
                'description_en': request.POST.get('description_en', ''),
                'category_id': int(request.POST.get('category', 1)),
                'manufacturer': request.POST.get('manufacturer', ''),
                'model': request.POST.get('model', ''),
                'total_quantity': int(request.POST.get('total_quantity', 1)),
                'minimum_stock': int(request.POST.get('minimum_stock', 1)),
                'condition': request.POST.get('condition', 'excellent'),
                'status': request.POST.get('status', 'available'),
                'location': request.POST.get('location', ''),
                'shelf_number': request.POST.get('shelf_number', ''),
                'purchase_price': float(request.POST.get('purchase_price', 0)) if request.POST.get(
                    'purchase_price') else None,
                'supplier': request.POST.get('supplier', ''),
                'notes': request.POST.get('notes', ''),
                'updated_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            })

            # Update available quantity if total changed
            if updated_part['total_quantity'] != part['total_quantity']:
                diff = updated_part['total_quantity'] - part['total_quantity']
                updated_part['available_quantity'] = part['available_quantity'] + diff
                if updated_part['available_quantity'] < 0:
                    updated_part['available_quantity'] = 0

            # Validate required fields
            if not all([updated_part['name_ar'], updated_part.get('part_number')]):
                messages.error(request, 'الاسم العربي ورقم القطعة مطلوبان')
                return render(request, 'inventory/edit_part.html', {
                    'part': part,
                    'categories': TEMP_CATEGORIES,
                    'form_data': request.POST
                })

            # Update in inventory
            TEMP_INVENTORY[part_index] = updated_part

            messages.success(request, f'تم تحديث القطعة {updated_part["name_ar"]} بنجاح')
            return redirect('inventory:part_detail', pk=pk)

        except (ValueError, TypeError) as e:
            messages.error(request, f'خطأ في البيانات المدخلة: {str(e)}')

    context = {
        'part': part,
        'categories': TEMP_CATEGORIES,
        'conditions': [
            ('excellent', 'ممتاز'),
            ('good', 'جيد'),
            ('fair', 'مقبول'),
            ('damaged', 'تالف'),
        ],
        'statuses': [
            ('available', 'متاح'),
            ('borrowed', 'مُستعار'),
            ('maintenance', 'تحت الصيانة'),
            ('discontinued', 'متوقف'),
        ]
    }
    return render(request, 'inventory/edit_part.html', context)


@staff_member_required
def delete_part(request, pk):
    """Delete or deactivate a part"""

    if request.method == 'POST':
        # Find and remove part
        for i, part in enumerate(TEMP_INVENTORY):
            if part.get('id') == int(pk):
                part_name = part.get('name_ar', 'Unknown')
                del TEMP_INVENTORY[i]
                messages.success(request, f'تم حذف القطعة {part_name} بنجاح')
                break
        else:
            messages.error(request, 'القطعة غير موجودة')

    return redirect('inventory:part_list')


@staff_member_required
def low_stock_report(request):
    """Report of parts with low stock"""

    low_stock_parts = [
        p for p in TEMP_INVENTORY
        if p.get('available_quantity', 0) <= p.get('minimum_stock', 1)
    ]

    context = {
        'low_stock_parts': low_stock_parts,
        'categories': TEMP_CATEGORIES,
    }

    return render(request, 'inventory/low_stock_report.html', context)


@staff_member_required
def inventory_stats_api(request):
    """API endpoint for inventory statistics"""

    stats = {
        'total_parts': len(TEMP_INVENTORY),
        'available_parts': len([p for p in TEMP_INVENTORY if p.get('status') == 'available']),
        'borrowed_parts': len([p for p in TEMP_INVENTORY if p.get('status') == 'borrowed']),
        'low_stock_parts': len(
            [p for p in TEMP_INVENTORY if p.get('available_quantity', 0) <= p.get('minimum_stock', 1)]),
        'maintenance_parts': len([p for p in TEMP_INVENTORY if p.get('status') == 'maintenance']),
        'categories': len(TEMP_CATEGORIES),
        'total_value': sum(
            p.get('purchase_price', 0) * p.get('total_quantity', 0) for p in TEMP_INVENTORY if p.get('purchase_price')),
    }

    return JsonResponse(stats)


@staff_member_required
def create_sample_inventory(request):
    """Create sample inventory data for testing"""

    sample_parts = [
        {
            'id': len(TEMP_INVENTORY) + 1,
            'name_ar': 'أردوينو أونو R3',
            'name_en': 'Arduino Uno R3',
            'description_ar': 'لوحة تطوير إلكترونية مبنية على متحكم ATmega328P',
            'description_en': 'Development board based on ATmega328P microcontroller',
            'category_id': 4,
            'part_number': 'ARD-UNO-R3',
            'manufacturer': 'Arduino',
            'model': 'Uno R3',
            'total_quantity': 10,
            'available_quantity': 7,
            'minimum_stock': 2,
            'condition': 'excellent',
            'status': 'available',
            'location': 'المخزن الرئيسي',
            'shelf_number': 'A1-001',
            'purchase_price': 25.50,
            'supplier': 'شركة الإلكترونيات المتقدمة',
            'notes': 'مناسب لمشاريع الطلاب المبتدئين',
            'added_by': request.user.username,
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'is_active': True,
        },
        {
            'id': len(TEMP_INVENTORY) + 2,
            'name_ar': 'لوحة التجارب الكبيرة',
            'name_en': 'Full Size Breadboard',
            'description_ar': 'لوحة تجارب بلاستيكية بدون لحام، 830 نقطة اتصال',
            'description_en': 'Solderless plastic breadboard with 830 tie points',
            'category_id': 1,
            'part_number': 'BB-FULL-830',
            'manufacturer': 'Generic',
            'model': 'BB830',
            'total_quantity': 25,
            'available_quantity': 20,
            'minimum_stock': 5,
            'condition': 'excellent',
            'status': 'available',
            'location': 'المخزن الرئيسي',
            'shelf_number': 'B2-010',
            'purchase_price': 3.75,
            'supplier': 'مؤسسة الكترونكس',
            'notes': 'أساسية لجميع المشاريع',
            'added_by': request.user.username,
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'is_active': True,
        },
        {
            'id': len(TEMP_INVENTORY) + 3,
            'name_ar': 'حساس الموجات فوق الصوتية',
            'name_en': 'Ultrasonic Sensor HC-SR04',
            'description_ar': 'حساس لقياس المسافة باستخدام الموجات فوق الصوتية',
            'description_en': 'Distance measurement sensor using ultrasonic waves',
            'category_id': 5,
            'part_number': 'US-HC-SR04',
            'manufacturer': 'Generic',
            'model': 'HC-SR04',
            'total_quantity': 15,
            'available_quantity': 12,
            'minimum_stock': 3,
            'condition': 'excellent',
            'status': 'available',
            'location': 'المخزن الثانوي',
            'shelf_number': 'C1-005',
            'purchase_price': 2.25,
            'supplier': 'شركة الحساسات المتطورة',
            'notes': 'يعمل بفولتية 5 فولت',
            'added_by': request.user.username,
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'is_active': True,
        },
        {
            'id': len(TEMP_INVENTORY) + 4,
            'name_ar': 'مجموعة مقاومات',
            'name_en': 'Resistor Kit',
            'description_ar': 'مجموعة مقاومات متنوعة من 220 أوم إلى 10 كيلو أوم',
            'description_en': 'Assorted resistor kit from 220Ω to 10kΩ',
            'category_id': 2,
            'part_number': 'RES-KIT-01',
            'manufacturer': 'Generic',
            'model': 'Mixed',
            'total_quantity': 50,
            'available_quantity': 45,
            'minimum_stock': 10,
            'condition': 'excellent',
            'status': 'available',
            'location': 'المخزن الرئيسي',
            'shelf_number': 'A3-020',
            'purchase_price': 1.50,
            'supplier': 'متجر القطع الإلكترونية',
            'notes': 'مجموعة أساسية للمبتدئين',
            'added_by': request.user.username,
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'is_active': True,
        },
        {
            'id': len(TEMP_INVENTORY) + 5,
            'name_ar': 'شاشة عرض LCD 16x2',
            'name_en': 'LCD Display 16x2',
            'description_ar': 'شاشة عرض بلورية سائلة 16 حرف × 2 سطر',
            'description_en': 'Liquid Crystal Display 16 characters × 2 lines',
            'category_id': 1,
            'part_number': 'LCD-16x2-HD44780',
            'manufacturer': 'Generic',
            'model': 'HD44780',
            'total_quantity': 8,
            'available_quantity': 5,
            'minimum_stock': 2,
            'condition': 'good',
            'status': 'available',
            'location': 'المخزن الثانوي',
            'shelf_number': 'D1-015',
            'purchase_price': 4.25,
            'supplier': 'شركة الشاشات المتخصصة',
            'notes': 'تحتاج إلى مقاوم متغير للتحكم بالتباين',
            'added_by': request.user.username,
            'created_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'is_active': True,
        }
    ]

    # Add sample parts to inventory
    TEMP_INVENTORY.extend(sample_parts)

    messages.success(request, f'تم إنشاء {len(sample_parts)} قطعة تجريبية بنجاح')
    return redirect('inventory:dashboard')
