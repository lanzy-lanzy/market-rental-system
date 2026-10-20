from decimal import Decimal
from datetime import date
import json

from django import forms
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from django.contrib.auth.forms import PasswordChangeForm as BasePasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import (
    UserProfile, Tenant, Stall, MarketSection, StallType,
    RentalContract, Billing, Payment, Notice, SystemSetting,
    PenaltySetting,
)

# Design-system widget classes (liquid glass + neumorphic).
# `.field` carries the inset neumorphic well; utilities only handle layout.
TW_INPUT = 'field block w-full rounded-[0.9rem] px-3.5 py-2.5 text-sm font-medium text-ink transition-all duration-200'
TW_SELECT = 'field block w-full rounded-[0.9rem] py-2.5 pl-3.5 pr-10 text-sm font-medium text-ink transition-all duration-200'
TW_TEXTAREA = 'field block w-full rounded-[0.9rem] px-3.5 py-2.5 text-sm font-medium text-ink transition-all duration-200'
TW_CHECKBOX = 'h-4 w-4 rounded border-ivory-300 text-emerald-600 focus:ring-emerald-500/30'


class DateInput(forms.DateInput):
    input_type = 'date'


class UserProfileForm(forms.ModelForm):
    """Profile details for a staff account.

    The ``user`` FK is deliberately excluded: it is assigned by the view
    (``profile.user = user``) once the account row exists. Leaving it in the
    form made it a required field that the template never renders, so every
    user creation failed validation with "This field is required." and the
    account was never created — the new collector could therefore never sign in.
    """

    class Meta:
        model = UserProfile
        fields = ['role', 'phone', 'address']
        widgets = {
            'role': forms.Select(attrs={'class': TW_SELECT}),
            'phone': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter phone number'}),
            'address': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Enter address'}),
        }


class TenantForm(forms.ModelForm):
    BUSINESS_TYPE_CHOICES = [
        ('', 'Select Business Type'),
        ('Dry Goods', 'Dry Goods'),
        ('Fish and Seafood', 'Fish and Seafood'),
        ('Meat and Poultry', 'Meat and Poultry'),
        ('Vegetables', 'Vegetables'),
        ('Fruits', 'Fruits'),
        ('Eatery / Carenderia', 'Eatery / Carenderia'),
        ('Grocery / Sari-sari Store', 'Grocery / Sari-sari Store'),
        ('Rice and Grains', 'Rice and Grains'),
        ('Clothing / Apparel', 'Clothing / Apparel'),
        ('Electronics / Appliances', 'Electronics / Appliances'),
        ('Services (Barber, Salon, Repair)', 'Services (Barber, Salon, Repair)'),
        ('Others', 'Others'),
    ]

    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'First name'}))
    middle_name = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Middle name (optional)'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Last name'}))
    street = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'House no., street / purok'}))
    barangay = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Barangay'}))
    municipality = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Municipality / City'}))
    province = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Province'}))

    class Meta:
        model = Tenant
        fields = [
            'first_name', 'middle_name', 'last_name',
            'street', 'barangay', 'municipality', 'province',
            'contact_number', 'email',
            'valid_id_type', 'valid_id_number', 'valid_id_image',
            'business_name', 'business_type',
            'emergency_contact_name', 'emergency_contact_number', 'status', 'notes',
        ]
        widgets = {
            'contact_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., 09123456789'}),
            'email': forms.EmailInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter email address'}),
            'valid_id_type': forms.Select(attrs={'class': TW_SELECT}, choices=[
                ('', 'Select ID Type'),
                ('Driver License', 'Driver License'),
                ('Passport', 'Passport'),
                ('UMID', 'UMID'),
                ('National ID', 'National ID'),
                ('SSS ID', 'SSS ID'),
                ('GSIS ID', 'GSIS ID'),
                ('PRC ID', 'PRC ID'),
                ('PhilHealth ID', 'PhilHealth ID'),
                ('Postal ID', 'Postal ID'),
                ('Barangay ID', 'Barangay ID'),
                ('Others', 'Others'),
            ]),
            'valid_id_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter ID number'}),
            'valid_id_image': forms.ClearableFileInput(attrs={'class': TW_INPUT}),
            'business_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter business name'}),
            'business_type': forms.Select(attrs={'class': TW_SELECT}),
            'emergency_contact_name': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'Enter emergency contact name'}),
            'emergency_contact_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., 09123456789'}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'notes': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Additional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields['business_type']
        field.choices = self.BUSINESS_TYPE_CHOICES
        # Select renders from widget.choices, which starts empty for a CharField.
        field.widget.choices = self.BUSINESS_TYPE_CHOICES
        instance = self.instance
        if instance and instance.pk:
            # Legacy rows only stored full_name/address — pre-fill the split fields
            # so editing never silently blanks the composed values.
            if not instance.first_name and instance.full_name:
                parts = instance.full_name.split()
                if len(parts) >= 2:
                    self.fields['first_name'].initial = parts[0]
                    self.fields['last_name'].initial = parts[-1]
                    self.fields['middle_name'].initial = ' '.join(parts[1:-1])
                else:
                    self.fields['first_name'].initial = instance.full_name
            if not instance.street and instance.address:
                segs = [s.strip() for s in instance.address.split(',') if s.strip()]
                for seg_field, seg in zip(('street', 'barangay', 'municipality', 'province'), segs):
                    self.fields[seg_field].initial = seg
            if instance.business_type and instance.business_type not in dict(self.BUSINESS_TYPE_CHOICES):
                choices = self.BUSINESS_TYPE_CHOICES + [(instance.business_type, instance.business_type)]
                field.choices = choices
                field.widget.choices = choices
        else:
            self.fields['municipality'].initial = 'Dumingag'
            self.fields['province'].initial = 'Zamboanga del Sur'

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.full_name = ' '.join(
            p.strip() for p in (instance.first_name, instance.middle_name, instance.last_name) if p and p.strip()
        )
        instance.address = ', '.join(
            p.strip() for p in (instance.street, instance.barangay, instance.municipality, instance.province) if p and p.strip()
        )
        if not instance.tenant_id:
            from core.helpers import generate_tenant_id
            instance.tenant_id = generate_tenant_id()
        if commit:
            instance.save()
        return instance

    def clean(self):
        """Block duplicate tenant records.

        A tenant is considered duplicated when the composed ``full_name``
        matches an existing one ignoring case and extra whitespace — the most
        common source of redundant entries in the field. On edit the record's
        own row is excluded so existing data still saves cleanly.
        """
        cleaned = super().clean()
        first = (cleaned.get('first_name') or '').strip()
        middle = (cleaned.get('middle_name') or '').strip()
        last = (cleaned.get('last_name') or '').strip()
        composed = ' '.join(p for p in (first, middle, last) if p)
        cleaned['full_name'] = composed
        if not composed:
            return cleaned

        import re
        normalized = re.sub(r'\s+', ' ', composed).strip().lower()

        # Fast path: exact (case-insensitive) match on stored full_name.
        candidates = Tenant.objects.filter(full_name__iexact=composed)
        # Fallback pass: tolerate the "JUAN   P.  DELA CRUZ" style typos where
        # iexact would miss because of duplicated spaces or trailing punctuation.
        if not candidates:
            candidates = Tenant.objects.all()

        exclude_pk = self.instance.pk if (self.instance and self.instance.pk) else None
        for existing in candidates:
            if exclude_pk and existing.pk == exclude_pk:
                continue
            existing_norm = re.sub(r'\s+', ' ', existing.full_name or '').strip().lower()
            if existing_norm == normalized:
                self.add_error(
                    None,
                    forms.ValidationError(
                        f'A tenant named "{existing.full_name}" already exists '
                        f'(Tenant ID: {existing.tenant_id}, Status: {existing.status}). '
                        'Please edit the existing record instead of creating a duplicate.'
                    ),
                )
                break
        return cleaned


class StallForm(forms.ModelForm):
    # Explicit ModelChoiceFields so we can (a) give the dropdowns clean
    # empty labels ("— Select section —"), (b) order the choices, and
    # (c) raise an actionable error if the underlying lookup table is
    # empty — otherwise a ModelChoiceField would silently accept nothing
    # and the operator just sees a blank <select> with no explanation.
    section = forms.ModelChoiceField(
        queryset=MarketSection.objects.order_by('name'),
        label='Section',
        required=True,
        empty_label='— Select section —',
        error_messages={
            'required': 'Please choose a market section for this stall.',
            'invalid_choice': 'The selected section no longer exists. Pick a current one.',
        },
        widget=forms.Select(attrs={'class': TW_SELECT}),
    )
    stall_type = forms.ModelChoiceField(
        queryset=StallType.objects.order_by('name'),
        label='Stall Type',
        required=False,
        empty_label='— Select stall type (optional) —',
        error_messages={
            'invalid_choice': 'The selected stall type no longer exists. Pick a current one.',
        },
        widget=forms.Select(attrs={'class': TW_SELECT}),
    )

    class Meta:
        model = Stall
        fields = ['stall_number', 'section', 'stall_type', 'size', 'monthly_rate', 'status', 'remarks']
        widgets = {
            'stall_number': forms.TextInput(attrs={'class': TW_INPUT, 'placeholder': 'e.g., A-101'}),
            'size': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Size in sqm', 'step': '0.01'}),
            'monthly_rate': forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Monthly rental rate', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': TW_SELECT}),
            'remarks': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 3, 'placeholder': 'Optional remarks'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Re-point the querysets on instantiation so a form bound before a
        # section was created still sees the latest rows on the next render.
        self.fields['section'].queryset = MarketSection.objects.order_by('name')
        self.fields['stall_type'].queryset = StallType.objects.order_by('name')
        # Surfaced to the templates so they can render an inline warning
        # instead of a silent empty dropdown when lookups are missing.
        self.section_options_available = self.fields['section'].queryset.exists()
        self.stall_type_options_available = self.fields['stall_type'].queryset.exists()

    def clean_section(self):
        if not self.section_options_available:
            raise forms.ValidationError(
                'No market sections are configured yet. Ask an administrator '
                'to add at least one under Settings → Market Sections before '
                'creating a stall.'
            )
        return self.cleaned_data.get('section')


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
        self.assignable_stalls = (
            Stall.objects.filter(status='Vacant')
            .exclude(contracts__status='Active').order_by('stall_number')
        )
        # A brand new contract may cover several stalls at once, so the encoder
        # picks from a vacant-only checklist and one contract is created per
        # stall. An existing contract always maps to exactly one stall.
        self.is_new_contract = not (self.instance and self.instance.pk)
        if self.is_new_contract:
            self.fields['stall'].required = False
            self.fields['monthly_rent'].required = False
            self.fields['monthly_rent'].widget.attrs['placeholder'] = "Blank = each stall's own rate"
            self.fields['stalls'] = forms.ModelMultipleChoiceField(
                queryset=self.assignable_stalls,
                label='Stalls (select one or more)',
                help_text='Only vacant stalls are listed. Each ticked stall gets its own contract at its own monthly rate.',
                error_messages={'required': 'Select at least one vacant stall.'},
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500/20'}),
            )
            self.fields['stalls'].label_from_instance = (
                lambda stall: f'{stall.stall_number} — ₱{stall.monthly_rate}'
            )
        else:
            # Keep the stall being edited selectable even though it is Occupied.
            self.fields['stall'].queryset = (
                self.assignable_stalls | Stall.objects.filter(pk=self.instance.stall_id)
            ).distinct().order_by('stall_number')

        # Lets the form pre-select a stall the tenant already holds.
        self.fields['tenant'].widget.attrs['data-assigned-stalls'] = json.dumps(
            self._assigned_stall_map()
        )

    def save(self, commit=True):
        """Create one contract per ticked stall; ``saved_contracts`` holds them all."""
        if not self.is_new_contract:
            self.saved_contracts = [super().save(commit=commit)]
            return self.saved_contracts[0]

        stalls = list(self.cleaned_data.get('stalls') or [])
        single_rent = self.cleaned_data.get('monthly_rent')
        self.saved_contracts = []
        for stall in stalls:
            # Several stalls never share one rate, so each falls back to its own.
            rent = (single_rent if len(stalls) == 1 and single_rent is not None
                    else stall.monthly_rate)
            contract = RentalContract(
                tenant=self.cleaned_data['tenant'],
                stall=stall,
                start_date=self.cleaned_data['start_date'],
                end_date=self.cleaned_data['end_date'],
                monthly_rent=rent,
                due_day=self.cleaned_data['due_day'],
                security_deposit=self.cleaned_data.get('security_deposit') or 0,
                status=self.cleaned_data['status'],
                remarks=self.cleaned_data.get('remarks', ''),
            )
            if commit:
                contract.save()
            self.saved_contracts.append(contract)
        self.instance = self.saved_contracts[0]
        return self.instance

    @staticmethod
    def _assigned_stall_map():
        """tenant pk -> every stall on record for that tenant, for auto-select.

        A tenant may hold several stalls, so the value is a list with the
        currently Active stalls first and lapsed ones after (newest first in
        each group), letting a renewal jump straight back to any stall they
        already occupied.
        """
        groups = {}
        for contract in RentalContract.objects.select_related('stall').order_by('-start_date'):
            group = groups.setdefault(contract.tenant_id, {'active': [], 'lapsed': []})
            entry = {
                'stall': str(contract.stall_id),
                'number': contract.stall.stall_number,
                'rate': str(contract.stall.monthly_rate),
                'status': contract.status,
            }
            bucket = group['active'] if contract.status == 'Active' else group['lapsed']
            if entry['stall'] not in [item['stall'] for item in bucket]:
                bucket.append(entry)
        return {str(tenant_id): group['active'] + group['lapsed']
                for tenant_id, group in groups.items()}

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
            'terms_and_conditions', 'logo', 'theme_color',
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
            'terms_and_conditions': forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 16, 'placeholder': 'One clause per line'}),
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

    def clean_username(self):
        """Reject usernames that differ only in case, but let a user keep its own.

        Django's ``UserCreationForm.clean_username()`` looks the username up
        without excluding the instance being edited, so every *edit* failed
        with "A user with that username already exists." Excluding the current
        instance keeps the duplicate check for new accounts while allowing an
        existing account to be edited (and renamed) normally.
        """
        username = self.cleaned_data.get('username')
        if not username:
            return username
        queryset = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise ValidationError(
                self.instance.unique_error_message(User, ['username']),
                code='unique',
            )
        return username


class TenantPasswordChangeForm(BasePasswordChangeForm):
    """Self-service password change for tenants in their portal.

    Inherits old/new/confirm validation and Django's password validators;
    only restyles widgets to match the Tailwind form look used elsewhere.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'old_password': 'Enter your current password',
            'new_password1': 'Enter a new password',
            'new_password2': 'Re-enter the new password',
        }
        for name, field in self.fields.items():
            field.widget.attrs.update({
                'class': TW_INPUT,
                'placeholder': placeholders.get(name, ''),
                'autocomplete': 'new-password' if name != 'old_password' else 'current-password',
            })


class BulkAssignStallsForm(forms.Form):
    """Assign one Tenant to multiple Vacant Stalls in a single operation.

    Creates one Active RentalContract per selected stall, each inheriting that
    stall's monthly_rate. Validates that every chosen stall is still Vacant at
    submission time to prevent double-assignment races.
    """
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.none(),
        widget=forms.Select(attrs={'class': TW_SELECT}),
        label='Tenant',
    )
    stalls = forms.ModelMultipleChoiceField(
        queryset=Stall.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500/20'}),
        label='Select Vacant Stalls',
        help_text='Choose one or more vacant stalls to assign to this tenant.',
        error_messages={'required': 'Select at least one vacant stall.'},
    )
    start_date = forms.DateField(
        widget=DateInput(attrs={'class': TW_INPUT}),
        label='Start Date',
        initial=date.today,
    )
    end_date = forms.DateField(
        widget=DateInput(attrs={'class': TW_INPUT}),
        label='End Date (optional)',
        required=False,
    )
    due_day = forms.IntegerField(
        min_value=1, max_value=28, initial=5,
        widget=forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Day of month (e.g., 5)'}),
        label='Due Day',
    )
    security_deposit = forms.DecimalField(
        max_digits=10, decimal_places=2, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': TW_INPUT, 'placeholder': 'Per stall (optional)', 'step': '0.01'}),
        label='Security Deposit per Stall (\u20b1)',
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 2, 'placeholder': 'Optional remarks for all contracts'}),
        label='Remarks',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].queryset = Tenant.objects.filter(status='Active').order_by('full_name')
        # Only stalls that can legally receive a new Active contract. The status
        # column can drift out of sync after manual edits, so the active
        # contract is checked too rather than trusting 'Vacant' alone.
        self.fields['stalls'].queryset = (
            Stall.objects.filter(status='Vacant')
            .exclude(contracts__status='Active')
            .order_by('stall_number')
        )

    def clean_stalls(self):
        stalls = self.cleaned_data['stalls']
        # Re-check vacancy at submission time to prevent race conditions
        non_vacant = [s.stall_number for s in stalls if s.status != 'Vacant']
        if non_vacant:
            raise forms.ValidationError(
                f'The following stalls are no longer vacant: {", ".join(non_vacant)}. Refresh and try again.'
            )
        return stalls

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'End date must be later than the start date.')
        return cleaned


class QuickCollectForm(forms.Form):
    """
    Simplified collector workflow: the amount alone decides the outcome.
    Amount >= outstanding balance settles the bill as Paid, anything less is
    recorded as a Partial payment — there is no manual status override.
    """
    amount_paid = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': TW_INPUT + ' !pl-8', 'step': '0.01', 'placeholder': '0.00', 'autofocus': 'autofocus', 'style': 'padding-left: 2rem;'}),
        label='Amount Paid (₱)',
        help_text='Defaults to outstanding balance. Enter less to record a partial payment.'
    )
    payment_method = forms.ChoiceField(
        choices=Payment.PAYMENT_METHOD_CHOICES,
        initial='Cash',
        widget=forms.Select(attrs={'class': TW_SELECT}),
        label='Method'
    )
    payment_date = forms.DateField(
        widget=DateInput(attrs={'class': TW_INPUT}),
        label='Payment Date'
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': TW_TEXTAREA, 'rows': 2, 'placeholder': 'Optional note (e.g., OR number)'}),
        label='Remarks'
    )

    def __init__(self, *args, billing=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.billing = billing
        if billing and not self.is_bound:
            # Default amount to outstanding balance
            self.fields['amount_paid'].initial = billing.balance if billing.balance > 0 else billing.total_due
            from datetime import date
            self.fields['payment_date'].initial = date.today()

    def clean_amount_paid(self):
        amt = self.cleaned_data.get('amount_paid')
        if self.billing:
            if amt is None or amt <= 0:
                raise forms.ValidationError('Amount must be greater than 0.')
            # Allow overpay slightly? Clamp to balance + small tolerance
            if amt > self.billing.balance + Decimal('0.01'):
                raise forms.ValidationError(f'Amount exceeds outstanding balance ₱{self.billing.balance:.2f}. For overpayment use partial then full.')
        return amt
