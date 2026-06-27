# core/admin.py - Public Market Rental and Collection Management System

from django.contrib import admin
from .models import (
    UserProfile, SystemSetting, MarketSection, StallType, Stall,
    Tenant, RentalContract, Billing, Payment, TenantLedger,
    Notice, AuditLog, PenaltySetting,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone']
    search_fields = ['user__username', 'user__email', 'phone']
    list_filter = ['role']


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['municipality_name', 'market_name', 'office_name', 'receipt_prefix', 'default_due_day']
    search_fields = ['municipality_name', 'market_name', 'office_name']


@admin.register(MarketSection)
class MarketSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(StallType)
class StallTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(Stall)
class StallAdmin(admin.ModelAdmin):
    list_display = ['stall_number', 'section', 'stall_type', 'monthly_rate', 'status']
    search_fields = ['stall_number', 'section__name']
    list_filter = ['status', 'section', 'stall_type']


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['tenant_id', 'full_name', 'contact_number', 'business_name', 'status', 'date_registered']
    search_fields = ['tenant_id', 'full_name', 'contact_number', 'business_name']
    list_filter = ['status', 'date_registered']


@admin.register(RentalContract)
class RentalContractAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'stall', 'start_date', 'end_date', 'monthly_rent', 'status']
    search_fields = ['tenant__full_name', 'stall__stall_number']
    list_filter = ['status', 'start_date']


@admin.register(Billing)
class BillingAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'stall', 'billing_month', 'billing_year', 'total_due', 'amount_paid', 'balance', 'status', 'due_date']
    search_fields = ['tenant__full_name', 'stall__stall_number']
    list_filter = ['status', 'billing_year', 'billing_month']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'tenant', 'stall', 'amount_paid', 'payment_date', 'payment_method', 'collected_by', 'status']
    search_fields = ['receipt_number', 'official_receipt_no', 'tenant__full_name', 'stall__stall_number']
    list_filter = ['status', 'payment_method', 'payment_date']


@admin.register(TenantLedger)
class TenantLedgerAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'transaction_date', 'description', 'debit', 'credit', 'balance']
    search_fields = ['tenant__full_name', 'description']
    list_filter = ['transaction_date']


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ['notice_number', 'tenant', 'notice_type', 'date_issued', 'is_served']
    search_fields = ['notice_number', 'tenant__full_name']
    list_filter = ['notice_type', 'is_served', 'date_issued']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'module', 'ip_address', 'created_at']
    search_fields = ['user__username', 'action', 'module', 'description']
    list_filter = ['action', 'module', 'created_at']

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(PenaltySetting)
class PenaltySettingAdmin(admin.ModelAdmin):
    list_display = ['contract', 'penalty_type', 'penalty_value', 'grace_period', 'due_day', 'is_active']
    search_fields = ['contract__tenant__full_name', 'contract__stall__stall_number']
    list_filter = ['penalty_type', 'is_active']
