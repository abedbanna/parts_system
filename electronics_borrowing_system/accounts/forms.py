# ============================================================================
# accounts/forms.py (Updated for Profile approach) - Fixed imports
# ============================================================================

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import UserProfile


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True, label=_('First Name'))
    last_name = forms.CharField(max_length=30, required=True, label=_('Last Name'))
    student_id = forms.CharField(max_length=20, required=True, label=_('Student ID'))
    department = forms.CharField(max_length=100, required=True, label=_('Department'))
    phone = forms.CharField(max_length=15, required=False, label=_('Phone Number'))

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            # Create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.student_id = self.cleaned_data['student_id']
            profile.department = self.cleaned_data['department']
            profile.phone = self.cleaned_data['phone']
            profile.user_type = 'student'
            profile.save()

        return user


class ProfileUpdateForm(forms.ModelForm):
    # Include User fields
    first_name = forms.CharField(max_length=30, required=True, label=_('First Name'))
    last_name = forms.CharField(max_length=30, required=True, label=_('Last Name'))
    email = forms.EmailField(required=True, label=_('Email'))

    class Meta:
        model = UserProfile
        fields = ('student_id', 'department', 'phone', 'avatar')
        labels = {
            'student_id': _('Student ID'),
            'department': _('Department'),
            'phone': _('Phone Number'),
            'avatar': _('Avatar'),
        }
        widgets = {
            'avatar': forms.FileInput(attrs={'accept': 'image/*'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            # Update User fields
            profile.user.first_name = self.cleaned_data['first_name']
            profile.user.last_name = self.cleaned_data['last_name']
            profile.user.email = self.cleaned_data['email']
            profile.user.save()
            profile.save()
        return profile
