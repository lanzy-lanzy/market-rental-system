from django import forms
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.contrib.auth.models import User

from .models import (
    UserProfile, Tenant, Stall, MarketSection, StallType,
    RentalContract, Billing, Payment, Notice, SystemSetting,
    PenaltySetting,
)

TW_INPUT = 'block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors duration-200'
TW_SELECT = 'block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors duration-200'
TW_TEXTAREA = 'block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-200 transition-colors duration-200'
TW_CHECKBOX = 'h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-200'


class DateInput(forms.DateInput):
    input_type = 'date'


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['user', 'role', 'phone', 'address']
        widgets = {
            'user': forms.Select(attrs={'class': TW_SELECT}),
            'role': forms.Select(attrs={'class': TW_SELECT}),
            'phone': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter phone number'}),
            'address': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Enter address'}),
        }


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            'tenant_id', 'full_name', 'address', 'contact_number', 'email',
            'valid_id_type', 'valid_id_number', 'business_name', 'business_type',
            'emergency_contact_name', 'emergency_contact_number', 'status', 'notes',
        ]
        widgets = {
            'tenant_id': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., T-001'}),
            'full_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter full name'}),
            'address': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Enter complete address'}),
            'contact_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., 09123456789'}),
            'email': forms.EmailInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter email address'}),
            'valid_id_type': forms.Select(attrs={'class': TW_SELECT}, choices=[
                ('', 'Select ID Type'),
                ('Driver License', 'Driver License'),
                ('Passport', 'Passport'),
                ('UMID', 'UMID'),
                ('SSS ID', 'SSS ID'),
                ('GSIS ID', 'GSIS ID'),
                ('PRC ID', 'PRC ID'),
                ('PhilHealth ID', 'PhilHealth ID'),
                ('Postal ID', 'Postal ID'),
                ('Barangay ID', 'Barangay ID'),
                ('Others', 'Others'),
            ]),
            'valid_id_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter ID number'}),
            'business_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter business name'}),
            'business_type': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., Grocery, Clothing'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter emergency contact name'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., 09123456789'}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'notes': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Additional notes'}),
        }


class StallForm(forms.ModelForm):
    class Meta:
        model = Stall
        fields = ['stall_number', 'section', 'stall_type', 'size', 'monthly_rate', 'status', 'remarks']
        widgets = {
            'stall_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., A-101'}),
            'section': forms.Select(attrs={'class': TW_SELECT}),
            'stall_type': forms.Select(attrs={'class': TW_SELECT}),
            'size': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Size in sqm', 'step': '0.01'}),
            'monthly_rate': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Monthly rental rate', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'remarks': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional remarks'}),
        }


class MarketSectionForm(forms.ModelForm):
    class Meta:
        model = MarketSection
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Section name'}),
            'description': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional description'}),
        }


class StallTypeForm(forms.ModelForm):
    class Meta:
        model = StallType
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Stall type name'}),
            'description': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional description'}),
        }


class RentalContractForm(forms.ModelForm):
    class Meta:
        model = RentalContract
        fields = ['tenant', 'stall', 'start_date', 'end_date', 'monthly_rent', 'due_day', 'security_deposit', 'status', 'remarks']
        widgets = {
            'tenant': forms.Select(attrs={'class': TW_SELECT}),
            'stall': forms.Select(attrs={'class': TW_SELECT}),
            'start_date': DateInput(attrs={'class': TW_INPUT}),
            'end_date': DateInput(attrs={'class': TW_INPUT}),
            'monthly_rent': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Monthly rent amount', 'step': '0.01'}),
            'due_day': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Day of month (e.g., 5)'}),
            'security_deposit': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Security deposit amount', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'remarks': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional remarks'}),
        }


class BillingForm(forms.ModelForm):
    class Meta:
        model = Billing
        fields = [
            'tenant', 'stall', 'contract', 'billing_month', 'billing_year',
            'rental_amount', 'penalty_amount', 'discount', 'total_due',
            'amount_paid', 'balance', 'due_date', 'status',
        ]
        widgets = {
            'tenant': forms.Select(attrs={'class': TW_SELECT}),
            'stall': forms.Select(attrs={'class': TW_SELECT}),
            'contract': forms.Select(attrs={'class': TW_SELECT}),
            'billing_month': forms.Select(attrs={'class': TW_SELECT}, choices=[
                (1, 'January'), (2, 'February'), (3, 'March'),
                (4, 'April'), (5, 'May'), (6, 'June'),
                (7, 'July'), (8, 'August'), (9, 'September'),
                (10, 'October'), (11, 'November'), (12, 'December'),
            ]),
            'billing_year': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Year (e.g., 2026)'}),
            'rental_amount': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'penalty_amount': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'total_due': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'amount_paid': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'balance': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'due_date': DateInput(attrs={'class': TW_INPUT}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'tenant', 'stall', 'billing', 'billing_month', 'billing_year',
            'rental_amount', 'penalty_amount', 'discount', 'total_amount_due',
            'amount_paid', 'payment_date', 'payment_method', 'official_receipt_no',
            'collected_by', 'status', 'remarks',
        ]
        widgets = {
            'tenant': forms.Select(attrs={'class': TW_SELECT}),
            'stall': forms.Select(attrs={'class': TW_SELECT}),
            'billing': forms.Select(attrs={'class': TW_SELECT}),
            'billing_month': forms.Select(attrs={'class': TW_SELECT}, choices=[
                (1, 'January'), (2, 'February'), (3, 'March'),
                (4, 'April'), (5, 'May'), (6, 'June'),
                (7, 'July'), (8, 'August'), (9, 'September'),
                (10, 'October'), (11, 'November'), (12, 'December'),
            ]),
            'billing_year': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Year (e.g., 2026)'}),
            'rental_amount': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'penalty_amount': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'total_amount_due': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'amount_paid': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'payment_date': DateInput(attrs={'class': TW_INPUT}),
            'payment_method': forms.Select(attrs={'class': TW_SELECT}),
            'official_receipt_no': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Official receipt number'}),
            'collected_by': forms.Select(attrs={'class': TW_SELECT}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'remarks': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional remarks'}),
        }


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['tenant', 'notice_type', 'notice_number', 'date_issued', 'is_served', 'served_date', 'remarks', 'content']
        widgets = {
            'tenant': forms.Select(attrs={'class': TW_SELECT}),
            'notice_type': forms.Select(attrs={'class': TW_SELECT}),
            'notice_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., N-2026-001'}),
            'date_issued': DateInput(attrs={'class': TW_INPUT}),
            'is_served': forms.CheckboxInput(attrs={'class': TW_CHECKBOX}),
            'served_date': DateInput(attrs={'class': TW_INPUT}),
            'remarks': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional remarks'}),
            'content': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 6, 'placeholder': 'Notice content'}),
        }


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = [
            'municipality_name', 'market_name', 'office_name', 'receipt_prefix',
            'default_due_day', 'penalty_type', 'penalty_value', 'grace_period',
            'logo', 'theme_color',
        ]
        widgets = {
            'municipality_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Municipality/City name'}),
            'market_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Public market name'}),
            'office_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Office name'}),
            'receipt_prefix': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., MR-'}),
            'default_due_day': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Day of month'}),
            'penalty_type': forms.Select(attrs={'class': TW_SELECT}),
            'penalty_value': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'grace_period': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Days'}),
            'logo': forms.FileInput(attrs={'class': TW_INPUT}),
            'theme_color': forms.TextInput(attrs={'class': TW_INPUT, 'type': 'color'}),
        }


class PenaltySettingForm(forms.ModelForm):
    class Meta:
        model = PenaltySetting
        fields = ['contract', 'penalty_type', 'penalty_value', 'grace_period', 'due_day', 'is_active']
        widgets = {
            'contract': forms.Select(attrs={'class': TW_SELECT}),
            'penalty_type': forms.Select(attrs={'class': TW_SELECT}),
            'penalty_value': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'grace_period': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Days'}),
            'due_day': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Day of month'}),
            'is_active': forms.CheckboxInput(attrs={'class': TW_CHECKBOX}),
        }


class UserCreationForm(BaseUserCreationForm):
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': TW_SELECT}),
        required=True,
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter phone number'}),
        required=False,
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Enter address'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Username'}),
            'first_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': TW_INPUT, 'placeholder': 'Email address'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': TW_INPUT, 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': TW_INPUT, 'placeholder': 'Confirm password'})
