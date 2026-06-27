from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count
from datetime import datetime, date
from decimal import Decimal

from core.models import Stall, Tenant, RentalContract, Billing, Payment, TenantLedger, Notice, AuditLog


@login_required
def dashboard_view(request):
    today = date.today()
    current_month = today.month
    current_year = today.year

    total_stalls = Stall.objects.count()
    occupied_stalls = Stall.objects.filter(status='Occupied').count()
    vacant_stalls = Stall.objects.filter(status='Vacant').count()
    total_tenants = Tenant.objects.filter(status='Active').count()

    active_contracts = RentalContract.objects.filter(status='Active')
    total_monthly_collectibles = active_contracts.aggregate(
        total=Sum('monthly_rent')
    )['total'] or Decimal('0.00')

    monthly_payments = Payment.objects.filter(
        status__in=['Paid', 'Partial'],
        payment_date__month=current_month,
        payment_date__year=current_year
    )
    total_collected = monthly_payments.aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')

    unpaid_billings = Billing.objects.filter(
        status__in=['Unpaid', 'Partial', 'Overdue']
    )
    total_unpaid = unpaid_billings.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')

    overdue_accounts = Billing.objects.filter(
        status='Overdue'
    ).values('tenant').distinct().count()

    if total_monthly_collectibles > 0:
        collection_percentage = round(
            float(total_collected) / float(total_monthly_collectibles) * 100, 2
        )
    else:
        collection_percentage = 0.00

    recent_payments = Payment.objects.filter(
        status__in=['Paid', 'Partial']
    ).select_related('tenant', 'stall', 'collected_by').order_by('-payment_date', '-created_at')[:5]

    tenants_with_unpaid = Billing.objects.filter(
        status__in=['Unpaid', 'Overdue']
    ).values(
        'tenant', 'tenant__full_name', 'tenant__tenant_id'
    ).annotate(
        total_balance=Sum('balance')
    ).order_by('-total_balance')[:5]

    context = {
        'total_stalls': total_stalls,
        'occupied_stalls': occupied_stalls,
        'vacant_stalls': vacant_stalls,
        'total_tenants': total_tenants,
        'total_monthly_collectibles': total_monthly_collectibles,
        'total_collected': total_collected,
        'total_unpaid': total_unpaid,
        'overdue_accounts': overdue_accounts,
        'collection_percentage': collection_percentage,
        'recent_payments': recent_payments,
        'tenants_with_unpaid': tenants_with_unpaid,
    }
    return render(request, 'dashboard.html', context)
