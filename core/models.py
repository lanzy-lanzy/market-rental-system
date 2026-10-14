# core/models.py - Public Market Rental and Collection Management System

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('collector', 'Collector'),
        ('cashier', 'Cashier'),
        ('supervisor', 'Supervisor'),
        ('treasurer', 'Treasurer'),
        ('tenant', 'Tenant'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='tenant')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


# Standard house rules printed on every rental contract. Stored on SystemSetting
# so the Market Administrator can revise them without a code change.
DEFAULT_CONTRACT_TERMS = """1. Rental fees shall be paid on or before the agreed due day of every month, either at the Market Administrator's Office or to the authorized city/municipal collector. An official receipt shall be issued for every payment.
2. A surcharge shall be automatically imposed on payments made beyond the grace period, in accordance with the penalty rate adopted by the Local Government Unit.
3. The stall or lot shall be used exclusively for the business line declared in this contract. Any change of use, merchandise line, or business name requires prior written approval of the Market Administrator.
4. Sub-letting, assignment, transfer, or sharing of the stall with another person without written consent is prohibited and is a ground for cancellation of this contract and forfeiture of the security deposit.
5. The tenant shall keep the stall clean, orderly, and sanitary, both inside and in front of it, and shall comply with all sanitary, fire safety, and solid waste rules of the municipality.
6. Operating hours, stall layout, signage, and the movement of goods and persons within the market shall follow the directives of the Market Administrator. No structural alteration or permanent installation shall be made without written approval.
7. The sale of illegal, substandard, expired, unweighed, or unlicensed goods — including dangerous drugs, contraband, and smuggled articles — is strictly prohibited within the market premises.
8. The tenant shall be liable for damage to market properties caused by the negligence of the tenant, his or her employees, or occupants.
9. The security deposit posted is not an offset against unpaid rentals. It shall be refunded only after full settlement of all monetary obligations and restoration of the stall to its original condition.
10. This contract may be cancelled or terminated for violation of any of its provisions, for non-payment, or for public need and market development projects of the Local Government Unit, without prejudice to existing monetary obligations.
11. Any act of corruption, imposition of unauthorized fees, or collection without an official receipt may be reported to the Market Administrator or the Local Chief Executive.
12. Disputes arising from this contract shall first be settled amicably; otherwise they shall be governed by the Market Code or Ordinance of the municipality and existing national laws."""


class SystemSetting(models.Model):
    PENALTY_TYPE_CHOICES = [
        ('fixed', 'Fixed'),
        ('percentage', 'Percentage'),
    ]
    municipality_name = models.CharField(max_length=200)
    market_name = models.CharField(max_length=200)
    office_name = models.CharField(max_length=200)
    receipt_prefix = models.CharField(max_length=20)
    default_due_day = models.PositiveIntegerField(default=5)
    penalty_type = models.CharField(max_length=20, choices=PENALTY_TYPE_CHOICES, default='percentage')
    penalty_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grace_period = models.PositiveIntegerField(default=5)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    theme_color = models.CharField(max_length=7, default='#003366')
    terms_and_conditions = models.TextField(
        default=DEFAULT_CONTRACT_TERMS,
        blank=True,
        help_text='One clause per line. Printed on every rental contract.',
    )

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f"{self.municipality_name} - {self.market_name}"


class MarketSection(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class StallType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Stall(models.Model):
    STATUS_CHOICES = [
        ('Vacant', 'Vacant'),
        ('Occupied', 'Occupied'),
        ('Reserved', 'Reserved'),
        ('Maintenance', 'Maintenance'),
    ]
    stall_number = models.CharField(max_length=20, unique=True)
    section = models.ForeignKey(MarketSection, on_delete=models.CASCADE, related_name='stalls')
    stall_type = models.ForeignKey(StallType, on_delete=models.SET_NULL, null=True, related_name='stalls')
    size = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Vacant')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['stall_number']

    def __str__(self):
        return f"{self.stall_number} - {self.section.name}"


class Tenant(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Suspended', 'Suspended'),
        ('Terminated', 'Terminated'),
    ]
    tenant_id = models.CharField(max_length=20, unique=True)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tenant')
    full_name = models.CharField(max_length=200)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    address = models.TextField()
    street = models.CharField(max_length=200, blank=True)
    barangay = models.CharField(max_length=100, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    contact_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    valid_id_type = models.CharField(max_length=100, blank=True)
    valid_id_number = models.CharField(max_length=100, blank=True)
    valid_id_image = models.ImageField(upload_to='tenant_ids/', blank=True, null=True)
    business_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=100, blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    date_registered = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f"{self.tenant_id} - {self.full_name}"


class RentalContract(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Expired', 'Expired'),
        ('Terminated', 'Terminated'),
        ('Pending', 'Pending'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='contracts')
    stall = models.ForeignKey(Stall, on_delete=models.CASCADE, related_name='contracts')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    due_day = models.PositiveIntegerField(default=5)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['stall', 'status'],
                name='unique_active_contract_per_stall',
                condition=models.Q(status='Active'),
            ),
        ]

    def __str__(self):
        return f"{self.tenant.full_name} - {self.stall.stall_number} ({self.get_status_display()})"


class Billing(models.Model):
    STATUS_CHOICES = [
        ('Unpaid', 'Unpaid'),
        ('Paid', 'Paid'),
        ('Partial', 'Partial'),
        ('Overdue', 'Overdue'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='billings')
    stall = models.ForeignKey(Stall, on_delete=models.CASCADE, related_name='billings')
    contract = models.ForeignKey(RentalContract, on_delete=models.CASCADE, related_name='billings')
    billing_month = models.PositiveIntegerField()
    billing_year = models.PositiveIntegerField()
    rental_amount = models.DecimalField(max_digits=10, decimal_places=2)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Unpaid')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-billing_year', '-billing_month']
        unique_together = ['tenant', 'stall', 'billing_month', 'billing_year']

    def __str__(self):
        return f"{self.tenant.full_name} - {self.stall.stall_number} - {self.billing_month}/{self.billing_year}"


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('GCash', 'GCash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Check', 'Check'),
    ]
    STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Partial', 'Partial'),
        ('Void', 'Void'),
        ('Cancelled', 'Cancelled'),
    ]
    receipt_number = models.CharField(max_length=50, unique=True)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payments')
    stall = models.ForeignKey(Stall, on_delete=models.CASCADE, related_name='payments')
    billing = models.ForeignKey(Billing, on_delete=models.CASCADE, related_name='payments')
    billing_month = models.PositiveIntegerField()
    billing_year = models.PositiveIntegerField()
    rental_amount = models.DecimalField(max_digits=10, decimal_places=2)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    official_receipt_no = models.CharField(max_length=50, blank=True)
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='collected_payments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Paid')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.receipt_number} - {self.tenant.full_name} ({self.amount_paid})"


class TenantLedger(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ledger_entries')
    billing = models.ForeignKey(Billing, on_delete=models.CASCADE, related_name='ledger_entries')
    transaction_date = models.DateField()
    description = models.CharField(max_length=255)
    debit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['transaction_date']
        verbose_name_plural = 'Tenant Ledgers'

    def __str__(self):
        return f"{self.tenant.full_name} - {self.transaction_date} ({self.description})"


class Notice(models.Model):
    NOTICE_TYPE_CHOICES = [
        ('Payment Reminder', 'Payment Reminder'),
        ('Overdue Notice', 'Overdue Notice'),
        ('Final Demand', 'Final Demand'),
        ('Vacancy Notice', 'Vacancy Notice'),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='notices')
    notice_type = models.CharField(max_length=30, choices=NOTICE_TYPE_CHOICES)
    notice_number = models.CharField(max_length=50, unique=True)
    date_issued = models.DateField()
    is_served = models.BooleanField(default=False)
    served_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_issued']

    def __str__(self):
        return f"{self.notice_number} - {self.get_notice_type_display()} - {self.tenant.full_name}"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    module = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} ({self.created_at})"


class PenaltySetting(models.Model):
    PENALTY_TYPE_CHOICES = [
        ('fixed', 'Fixed'),
        ('percentage', 'Percentage'),
    ]
    contract = models.ForeignKey(RentalContract, on_delete=models.CASCADE, related_name='penalty_settings')
    penalty_type = models.CharField(max_length=20, choices=PENALTY_TYPE_CHOICES, default='percentage')
    penalty_value = models.DecimalField(max_digits=10, decimal_places=2)
    grace_period = models.PositiveIntegerField(default=5)
    due_day = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_active']

    def __str__(self):
        return f"Penalty for {self.contract} - {self.get_penalty_type_display()} {self.penalty_value}"
