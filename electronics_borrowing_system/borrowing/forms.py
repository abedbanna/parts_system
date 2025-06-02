# ============================================================================
# FILE: borrowing/forms.py
# ============================================================================

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date


class BorrowRequestForm(forms.Form):
    """Form for borrowing requests that matches frontend structure"""

    purpose = forms.CharField(
        label=_('Purpose of Use'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _('Describe why you need these parts...'),
            'class': 'form-control',
            'id': 'id_purpose'
        }),
        required=True,
        error_messages={
            'required': _('Purpose is required.')
        }
    )

    expected_return_date = forms.DateField(
        label=_('Expected Return Date'),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'id': 'id_expected_return_date'
        }),
        required=True,
        error_messages={
            'required': _('Expected return date is required.')
        }
    )

    student_notes = forms.CharField(
        label=_('Additional Notes'),
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': _('Any additional information...'),
            'class': 'form-control',
            'id': 'id_student_notes'
        }),
        required=False
    )

    def clean_expected_return_date(self):
        """Validate that return date is in the future"""
        return_date = self.cleaned_data.get('expected_return_date')
        if return_date and return_date <= date.today():
            raise ValidationError(_('Return date must be in the future.'))
        return return_date


class PartForm(forms.Form):
    """Form for individual parts - used for validation"""

    part_name = forms.CharField(
        max_length=200,
        required=True,
        error_messages={
            'required': _('Part name is required.')
        }
    )

    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        required=True,
        error_messages={
            'required': _('Quantity is required.'),
            'min_value': _('Quantity must be at least 1.')
        }
    )

    condition = forms.ChoiceField(
        choices=[
            ('excellent', _('Excellent')),
            ('good', _('Good')),
            ('fair', _('Fair'))
        ],
        initial='excellent',
        required=True
    )


class BorrowRequestProcessor:
    """
    Handles processing of the complete borrowing request
    including main form and dynamic parts
    """

    def __init__(self, data=None):
        self.data = data or {}
        self.main_form = BorrowRequestForm(data)
        self.parts = []
        self.errors = {}

        if data:
            self._extract_parts()

    def _extract_parts(self):
        """Extract part data from POST data"""
        part_index = 0

        while f'part_name_{part_index}' in self.data:
            part_data = {
                'part_name': self.data.get(f'part_name_{part_index}', '').strip(),
                'quantity': self.data.get(f'quantity_{part_index}', '1'),
                'condition': self.data.get(f'condition_{part_index}', 'excellent')
            }

            # Only add parts that have a name
            if part_data['part_name']:
                part_form = PartForm(part_data)
                self.parts.append({
                    'form': part_form,
                    'data': part_data,
                    'index': part_index
                })

            part_index += 1

    def is_valid(self):
        """Check if main form and all parts are valid"""
        main_valid = self.main_form.is_valid()

        if not main_valid:
            self.errors['main'] = self.main_form.errors

        # Validate we have at least one part
        if not self.parts:
            self.errors['parts'] = [_('At least one part is required.')]
            return False

        # Validate each part
        parts_valid = True
        for part in self.parts:
            if not part['form'].is_valid():
                parts_valid = False
                self.errors[f'part_{part["index"]}'] = part['form'].errors

        return main_valid and parts_valid

    def get_cleaned_data(self):
        """Get cleaned data for saving"""
        if not self.is_valid():
            return None

        return {
            'main_data': self.main_form.cleaned_data,
            'parts_data': [part['form'].cleaned_data for part in self.parts]
        }

    def get_errors_summary(self):
        """Get formatted error summary"""
        error_list = []

        if 'main' in self.errors:
            for field, errors in self.errors['main'].items():
                error_list.extend([f"{field}: {error}" for error in errors])

        if 'parts' in self.errors:
            error_list.extend(self.errors['parts'])

        for key, errors in self.errors.items():
            if key.startswith('part_'):
                for field, field_errors in errors.items():
                    part_num = key.split('_')[1]
                    error_list.extend([f"Part {int(part_num) + 1} {field}: {error}" for error in field_errors])

        return error_list
