from django import forms
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.contrib.auth.models import User

from .models import (
    UserProfile, Tenant, Stall, MarketSection, StallType,
    RentalContract, Billing, Payment, Notice, SystemSetting,
    PenaltySetting,
)

TW_INPUT = 'block w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/10 transition-all duration-200'
TW_SELECT = 'block w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-900 focus:border-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/10 transition-all duration-200'
TW_TEXTAREA = 'block w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm font-medium text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:bg-white focus:outline-none focus:ring-4 focus:ring-slate-900/10 transition-all duration-200'
TW_CHECKBOX = 'h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20'


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit tenant to Active, stall to Vacant + current selection for edit
        from core.models import Tenant, Stall
        self.fields['tenant'].queryset = Tenant.objects.filter(status='Active').order_by('full_name')
        stall_qs = Stall.objects.all().order_by('stall_number')
        # If editing and current stall is not Vacant, include it
        if self.instance and self.instance.pk and self.instance.stall_id:
            stall_qs = Stall.objects.filter(status='Vacant').order_by('stall_number') | Stall.objects.filter(pk=self.instance.stall_id)
            self.fields['stall'].queryset = stall_qs.distinct().order_by('stall_number')
        else:
            self.fields['stall'].queryset = Stall.objects.filter(status='Vacant').order_by('stall_number')

    def clean(self):
        cleaned = super().clean()
        stall = cleaned.get('stall')
        status = cleaned.get('status')
        if stall and status == 'Active':
            qs = RentalContract.objects.filter(stall=stall, status='Active')
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f'Stall {stall.stall_number} already has an active contract. One stall can only have one active tenant.')
        return cleaned


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
            'total_due': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01', 'readonly': 'readonly'}),
            'amount_paid': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01'}),
            'balance': forms.NumberInput(attrs={'class': TW_INPUT, 'step': '0.01', 'readonly': 'readonly'}),
            'due_date': DateInput(attrs={'class': TW_INPUT}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
        }

    def clean(self):
        cleaned = super().clean()
        rental = cleaned.get('rental_amount') or 0
        penalty = cleaned.get('penalty_amount') or 0
        discount = cleaned.get('discount') or 0
        # Recompute total_due and balance to prevent manual tampering
        try:
            total_due = rental + penalty - discount
        except Exception:
            total_due = rental + penalty
        cleaned['total_due'] = total_due
        amt_paid = cleaned.get('amount_paid') or 0
        try:
            balance = total_due - amt_paid
        except Exception:
            balance = total_due
        if balance < 0:
            balance = 0
            cleaned['amount_paid'] = total_due
            amt_paid = total_due
        cleaned['balance'] = balance
        # Auto-status if not explicitly Overdue
        current_status = cleaned.get('status')
        if balance == 0:
            cleaned['status'] = 'Paid'
        elif balance > 0 and amt_paid > 0:
            if current_status != 'Overdue':
                cleaned['status'] = 'Partial'
        else:
            if current_status not in ['Overdue', 'Unpaid']:
                cleaned['status'] = 'Unpaid'
        return cleaned


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
            'official_receipt_no': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Official receipt number (auto if blank)'}),
            'collected_by': forms.Select(attrs={'class': TW_SELECT}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'remarks': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional remarks'}),
        }

    def clean(self):
        cleaned = super().clean()
        billing = cleaned.get('billing')
        tenant = cleaned.get('tenant')
        stall = cleaned.get('stall')
        # Validate billing consistency
        if billing and tenant and billing.tenant_id != tenant.id:
            raise forms.ValidationError('Selected billing does not belong to the selected tenant.')
        if billing and stall and billing.stall_id != stall.id:
            raise forms.ValidationError('Selected billing does not belong to the selected stall.')
        # Auto total_amount_due if billing present
        if billing and not cleaned.get('total_amount_due'):
            cleaned['total_amount_due'] = billing.total_due
        # Overpayment guard: amount_paid cannot exceed balance
        amount_paid = cleaned.get('amount_paid') or 0
        if billing:
            # balance is what remains before this payment
            remaining = billing.balance
            # If editing, add back current payment if it was valid
            if self.instance and self.instance.pk and self.instance.status in ['Paid', 'Partial']:
                remaining += float(self.instance.amount_paid)
            if float(amount_paid) > float(remaining) + 0.01:
                raise forms.ValidationError(f'Amount paid ({amount_paid}) exceeds outstanding balance ({remaining:.2f}) for this billing period.')
        return cleaned


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
