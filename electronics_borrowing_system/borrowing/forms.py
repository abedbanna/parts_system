# borrowing/forms.py

from django import forms
from django.forms import modelformset_factory, inlineformset_factory
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from .models import BorrowRequest, BorrowRecord


class BorrowRequestForm(forms.ModelForm):
    """Enhanced form for creating borrow requests"""

    class Meta:
        model = BorrowRequest
        fields = [
            'purpose',
            'expected_return_date',
            'urgency',
            'student_notes',
            'attachment'
        ]
        widgets = {
            'purpose': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('اشرح الغرض من استخدام هذه العناصر والمشروع المطلوب...'),
                'class': 'form-control'
            }),
            'expected_return_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
                'max': (date.today() + timedelta(days=90)).strftime('%Y-%m-%d')
            }),
            'urgency': forms.Select(attrs={
                'class': 'form-select'
            }),
            'student_notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': _('أي ملاحظات إضافية (اختياري)...'),
                'class': 'form-control'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
            })
        }
        help_texts = {
            'expected_return_date': _('متى تتوقع إرجاع العناصر؟ (يجب أن يكون خلال 3 أشهر)'),
            'urgency': _('مدى الحاجة الملحة لهذه العناصر'),
            'attachment': _('يمكن إرفاق مخطط الدائرة أو وصف المشروع (اختياري)')
        }

    def clean_expected_return_date(self):
        """Validate expected return date"""
        expected_date = self.cleaned_data.get('expected_return_date')

        if expected_date:
            min_date = date.today() + timedelta(days=1)
            max_date = date.today() + timedelta(days=90)

            if expected_date < min_date:
                raise ValidationError(_('تاريخ الإرجاع يجب أن يكون غداً على الأقل.'))

            if expected_date > max_date:
                raise ValidationError(_('تاريخ الإرجاع لا يمكن أن يكون أكثر من 3 أشهر من الآن.'))

        return expected_date

    def clean_attachment(self):
        """Validate attachment file"""
        attachment = self.cleaned_data.get('attachment')

        if attachment:
            # Check file size (max 10MB)
            if attachment.size > 10 * 1024 * 1024:
                raise ValidationError(_('حجم الملف يجب أن يكون أقل من 10 ميجابايت.'))

            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
            file_extension = '.' + attachment.name.split('.')[-1].lower()

            if file_extension not in allowed_extensions:
                raise ValidationError(
                    _('نوع الملف غير مدعوم. الأنواع المدعومة: {}').format(
                        ', '.join(allowed_extensions)
                    )
                )

        return attachment


class BorrowRecordForm(forms.ModelForm):
    """Form for individual borrow records"""

    class Meta:
        model = BorrowRecord
        fields = [
            'part_name',
            'part_description',
            'part_number',
            'quantity',
            'unit_cost'
        ]
        widgets = {
            'part_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('اسم القطعة')
            }),
            'part_description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': _('وصف القطعة (اختياري)')
            }),
            'part_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('رقم القطعة (اختياري)')
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'value': '1'
            }),
            'unit_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': _('التكلفة (اختياري)')
            })
        }

    def clean_quantity(self):
        """Validate quantity"""
        quantity = self.cleaned_data.get('quantity')

        if quantity and quantity <= 0:
            raise ValidationError(_('الكمية يجب أن تكون أكبر من صفر.'))

        if quantity and quantity > 100:
            raise ValidationError(_('الكمية لا يمكن أن تكون أكثر من 100.'))

        return quantity


# Create formset for multiple records
BorrowRecordFormSet = inlineformset_factory(
    BorrowRequest,
    BorrowRecord,
    form=BorrowRecordForm,
    extra=3,  # Start with 3 empty forms
    min_num=1,  # Require at least 1 record
    max_num=20,  # Maximum 20 records per request
    validate_min=True,
    validate_max=True,
    can_delete=True
)


class AdminApprovalForm(forms.Form):
    """Form for admin approval/rejection"""

    ACTION_CHOICES = [
        ('approve', _('الموافقة')),
        ('reject', _('الرفض'))
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

    admin_notes = forms.CharField(
        label=_('ملاحظات الإدارة'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': _('أي ملاحظات للطالب...')
        }),
        required=False
    )

    rejection_reason = forms.CharField(
        label=_('سبب الرفض'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': _('سبب رفض الطلب...')
        }),
        required=False
    )

    def clean(self):
        """Validate that rejection reason is provided when rejecting"""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')

        if action == 'reject' and not rejection_reason:
            raise ValidationError({
                'rejection_reason': _('سبب الرفض مطلوب عند رفض الطلب.')
            })

        return cleaned_data


class ReturnItemsForm(forms.Form):
    """Form for marking items as returned"""

    condition_notes = forms.CharField(
        label=_('ملاحظات الحالة'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': _('حالة العناصر المرتجعة، أي أضرار، إلخ...')
        }),
        required=False
    )

    def __init__(self, *args, borrow_request=None, **kwargs):
        super().__init__(*args, **kwargs)

        if borrow_request:
            # Add condition fields for each record
            for record in borrow_request.records.all():
                field_name = f'condition_{record.id}'
                self.fields[field_name] = forms.ChoiceField(
                    label=f'{record.part_name} - {_("الحالة")}',
                    choices=BorrowRecord.CONDITION_CHOICES,
                    initial='excellent',
                    widget=forms.Select(attrs={'class': 'form-select'})
                )


class BulkActionForm(forms.Form):
    """Form for bulk actions on multiple requests"""

    ACTION_CHOICES = [
        ('approve', _('الموافقة على المحدد')),
        ('reject', _('رفض المحدد')),
        ('mark_borrowed', _('تسليم المحدد')),
        ('mark_returned', _('استقبال المحدد')),
        ('send_reminder', _('إرسال تذكير للمحدد'))
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    selected_requests = forms.CharField(
        widget=forms.HiddenInput()
    )

    notes = forms.CharField(
        label=_('ملاحظات'),
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': _('ملاحظات للعملية المجمعة...')
        }),
        required=False
    )


class SearchFilterForm(forms.Form):
    """Form for searching and filtering requests"""

    search = forms.CharField(
        label=_('البحث'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('البحث في الطلبات، أسماء القطع، أو رقم الطلب...')
        }),
        required=False
    )

    status = forms.ChoiceField(
        label=_('الحالة'),
        choices=[('', _('جميع الحالات'))] + list(BorrowRequest.STATUS_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )

    urgency = forms.ChoiceField(
        label=_('الأولوية'),
        choices=[('', _('جميع الأولويات'))] + list(BorrowRequest.URGENCY_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )

    date_from = forms.DateField(
        label=_('من تاريخ'),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        required=False
    )

    date_to = forms.DateField(
        label=_('إلى تاريخ'),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        required=False
    )

    order_by = forms.ChoiceField(
        label=_('الترتيب'),
        choices=[
            ('-created_at', _('الأحدث أولاً')),
            ('created_at', _('الأقدم أولاً')),
            ('-expected_return_date', _('تاريخ الإرجاع - الأبعد أولاً')),
            ('expected_return_date', _('تاريخ الإرجاع - الأقرب أولاً')),
            ('urgency', _('الأولوية')),
            ('status', _('الحالة'))
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='-created_at',
        required=False
    )

    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to:
            if date_from > date_to:
                raise ValidationError({
                    'date_to': _('تاريخ النهاية يجب أن يكون بعد تاريخ البداية.')
                })

        return cleaned_data


class StudentCancelForm(forms.Form):
    """Form for students to cancel their own requests"""

    cancel_reason = forms.CharField(
        label=_('سبب الإلغاء'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': _('لماذا تريد إلغاء هذا الطلب؟')
        }),
        required=True
    )

    confirm = forms.BooleanField(
        label=_('أؤكد رغبتي في إلغاء هذا الطلب'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        required=True
    )


# Custom widget for dynamic part selection
class PartSelectionWidget(forms.TextInput):
    """Custom widget with autocomplete for part selection"""

    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control part-autocomplete',
            'data-autocomplete-url': '/borrowing/api/parts-autocomplete/',
            'placeholder': _('ابدأ بكتابة اسم القطعة...')
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    class Media:
        css = {
            'all': ('borrowing/css/autocomplete.css',)
        }
        js = ('borrowing/js/autocomplete.js',)


# Processor class for handling complex form data (as referenced in your original views)
class BorrowRequestProcessor:
    """Process and validate borrow request form data"""

    def __init__(self, data=None, files=None):
        self.data = data or {}
        self.files = files or {}
        self.errors = []
        self.cleaned_data = {}

    def is_valid(self):
        """Validate all form data"""
        self.errors = []

        # Validate main form data
        main_form = BorrowRequestForm(self.data, self.files)
        if main_form.is_valid():
            self.cleaned_data['main_data'] = main_form.cleaned_data
        else:
            self.errors.extend([str(error) for error_list in main_form.errors.values() for error in error_list])

        # Validate records data
        parts_data = []

        # Extract parts data from POST (assumes formset pattern)
        total_forms = int(self.data.get('records-TOTAL_FORMS', 0))
        for i in range(total_forms):
            prefix = f'records-{i}'

            if self.data.get(f'{prefix}-DELETE'):
                continue  # Skip deleted forms

            part_name = self.data.get(f'{prefix}-part_name', '').strip()
            if not part_name:
                continue  # Skip empty forms

            try:
                quantity = int(self.data.get(f'{prefix}-quantity', 1))
                if quantity <= 0:
                    self.errors.append(_('الكمية يجب أن تكون أكبر من صفر.'))
                    continue
            except (ValueError, TypeError):
                self.errors.append(_('الكمية يجب أن تكون رقماً صحيحاً.'))
                continue

            part_data = {
                'part_name': part_name,
                'part_description': self.data.get(f'{prefix}-part_description', ''),
                'part_number': self.data.get(f'{prefix}-part_number', ''),
                'quantity': quantity
            }

            # Handle unit cost if provided
            unit_cost = self.data.get(f'{prefix}-unit_cost')
            if unit_cost:
                try:
                    part_data['unit_cost'] = float(unit_cost)
                except (ValueError, TypeError):
                    pass  # Unit cost is optional

            parts_data.append(part_data)

        if not parts_data:
            self.errors.append(_('يجب إضافة قطعة واحدة على الأقل.'))

        self.cleaned_data['parts_data'] = parts_data

        return len(self.errors) == 0

    def get_cleaned_data(self):
        """Get cleaned form data"""
        return self.cleaned_data

    def get_errors_summary(self):
        """Get list of error messages"""
        return self.errors
