from calendar import month_abbr
from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (
    Billing, MarketSection, Payment, RentalContract, SystemSetting, Tenant,
)
from core.permissions import ALL_ROLES, get_user_role, role_required, staff_required


SHEET_STATUS_CHOICES = [
    ('', 'All Outstanding'),
    ('Overdue', 'Overdue'),
    ('Unpaid', 'Unpaid'),
    ('Partial', 'Partial'),
]

SHEET_STATUS_LOOKUP = {
    'all': '',
    'all outstanding': '',
    'overdue': 'Overdue',
    'unpaid': 'Unpaid',
    'partial': 'Partial',
}

STATUS_PRIORITY = {
    'Overdue': 3,
    'Partial': 2,
    'Unpaid': 1,
}


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


def _normalize_sheet_status(raw_status):
    raw = (raw_status or '').strip()
    if not raw:
        return ''
    return SHEET_STATUS_LOOKUP.get(raw.lower(), raw)


def _format_billing_period(month, year):
    if 1 <= (month or 0) <= 12:
        return f"{month_abbr[month]} {year}"
    return f"{month}/{year}"


def _build_collection_sheet_data(request):
    section_filter = (request.GET.get('section') or '').strip()
    status_filter = _normalize_sheet_status(request.GET.get('status'))
    search_query = (request.GET.get('search') or request.GET.get('q') or '').strip()

    billings_qs = (
        Billing.objects.select_related('tenant', 'stall', 'stall__section', 'stall__stall_type', 'contract')
        .filter(balance__gt=Decimal('0.00'))
        .exclude(status='Paid')
    )

    selected_section = None
    if section_filter:
        if section_filter.isdigit():
            billings_qs = billings_qs.filter(stall__section_id=int(section_filter))
            selected_section = MarketSection.objects.filter(pk=int(section_filter)).first()
        else:
            billings_qs = billings_qs.none()

    if status_filter:
        billings_qs = billings_qs.filter(status=status_filter)

    if search_query:
        billings_qs = billings_qs.filter(
            Q(stall__stall_number__icontains=search_query)
            | Q(stall__section__name__icontains=search_query)
            | Q(tenant__full_name__icontains=search_query)
            | Q(tenant__tenant_id__icontains=search_query)
            | Q(tenant__business_name__icontains=search_query)
        )

    # Sort strictly by Market Section & Stall Number (collector route order), then oldest billing first
    billings_qs = billings_qs.order_by(
        'stall__section__name',
        'stall__stall_number',
        'tenant__full_name',
        'billing_year',
        'billing_month',
        'id',
    )

    grouped = OrderedDict()
    for billing in billings_qs:
        key = (billing.stall_id, billing.tenant_id)
        if key not in grouped:
            grouped[key] = {
                'stall': billing.stall,
                'section': billing.stall.section,
                'tenant': billing.tenant,
                'unpaid_months': 0,
                'overdue_months': 0,
                'rent_due': Decimal('0.00'),
                'penalty_due': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'amount_paid': Decimal('0.00'),
                'total_balance': Decimal('0.00'),
                'status': billing.status,
                'oldest_period': _format_billing_period(billing.billing_month, billing.billing_year),
                'latest_period': _format_billing_period(billing.billing_month, billing.billing_year),
            }
        row = grouped[key]
        row['unpaid_months'] += 1
        if billing.status == 'Overdue':
            row['overdue_months'] += 1
        row['rent_due'] += billing.rental_amount or Decimal('0.00')
        row['penalty_due'] += billing.penalty_amount or Decimal('0.00')
        row['total_due'] += billing.total_due or Decimal('0.00')
        row['amount_paid'] += billing.amount_paid or Decimal('0.00')
        row['total_balance'] += billing.balance or Decimal('0.00')
        row['latest_period'] = _format_billing_period(billing.billing_month, billing.billing_year)
        if STATUS_PRIORITY.get(billing.status, 0) > STATUS_PRIORITY.get(row['status'], 0):
            row['status'] = billing.status

    rows = list(grouped.values())

    summary = {
        'total_accounts': len(rows),
        'total_unpaid_months': sum(r['unpaid_months'] for r in rows),
        'overdue_accounts': sum(1 for r in rows if r['status'] == 'Overdue'),
        'total_rent_due': sum((r['rent_due'] for r in rows), Decimal('0.00')),
        'total_penalty_due': sum((r['penalty_due'] for r in rows), Decimal('0.00')),
        'total_balance': sum((r['total_balance'] for r in rows), Decimal('0.00')),
    }

    today = timezone.localdate()
    today_payments = Payment.objects.filter(
        collected_by=request.user,
        payment_date=today,
    ).exclude(status__in=['Void', 'Cancelled'])
    collected_today_count = today_payments.count()
    collected_today_total = (
        today_payments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    )

    filter_params = {}
    if section_filter:
        filter_params['section'] = section_filter
    if status_filter:
        filter_params['status'] = status_filter
    if search_query:
        filter_params['search'] = search_query
    filter_querystring = urlencode(filter_params)

    return {
        'rows': rows,
        'summary': summary,
        'sections': MarketSection.objects.all().order_by('name'),
        'section_filter': section_filter,
        'selected_section': selected_section,
        'status_filter': status_filter,
        'status_choices': SHEET_STATUS_CHOICES,
        'search_query': search_query,
        'filter_querystring': filter_querystring,
        'collected_today_count': collected_today_count,
        'collected_today_total': collected_today_total,
        'today': today,
    }


@staff_required
def billing_collection_sheet(request):
    data = _build_collection_sheet_data(request)
    context = {
        **data,
        'is_htmx_request': bool(is_htmx(request)),
    }
    if is_htmx(request):
        return render(request, 'billing/_collection_sheet_table.html', context)
    return render(request, 'billing/collection_sheet.html', context)


@staff_required
def billing_collection_sheet_print(request):
    data = _build_collection_sheet_data(request)
    context = {
        **data,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': timezone.now(),
    }
    return render(request, 'billing/print_collection_sheet.html', context)


@role_required(ALL_ROLES)
def billing_tenant_soa(request, tenant_id):
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    role = get_user_role(request.user)
    if role == 'tenant' and not request.user.is_superuser and tenant.user_id != request.user.id:
        messages.error(request, 'You do not have permission to view that Statement of Account.')
        return redirect('tenant_portal')

    active_contracts = list(
        RentalContract.objects.filter(tenant=tenant, status='Active')
        .select_related('stall', 'stall__section', 'stall__stall_type')
        .order_by('stall__section__name', 'stall__stall_number')
    )

    outstanding_billings = list(
        Billing.objects.filter(tenant=tenant, balance__gt=Decimal('0.00'))
        .exclude(status='Paid')
        .select_related('stall', 'stall__section', 'contract')
        .order_by('billing_year', 'billing_month', 'stall__stall_number', 'id')
    )

    items = []
    for billing in outstanding_billings:
        items.append({
            'billing': billing,
            'period_label': _format_billing_period(billing.billing_month, billing.billing_year),
            'stall_number': billing.stall.stall_number,
            'section_name': billing.stall.section.name,
            'rental_amount': billing.rental_amount or Decimal('0.00'),
            'penalty_amount': billing.penalty_amount or Decimal('0.00'),
            'total_due': billing.total_due or Decimal('0.00'),
            'amount_paid': billing.amount_paid or Decimal('0.00'),
            'balance': billing.balance or Decimal('0.00'),
            'due_date': billing.due_date,
            'status': billing.status,
        })

    soa_totals = {
        'item_count': len(items),
        'overdue_count': sum(1 for item in items if item['status'] == 'Overdue'),
        'total_rent': sum((item['rental_amount'] for item in items), Decimal('0.00')),
        'total_penalty': sum((item['penalty_amount'] for item in items), Decimal('0.00')),
        'total_due': sum((item['total_due'] for item in items), Decimal('0.00')),
        'total_paid': sum((item['amount_paid'] for item in items), Decimal('0.00')),
        'grand_total_due': sum((item['balance'] for item in items), Decimal('0.00')),
    }

    context = {
        'tenant': tenant,
        'active_contracts': active_contracts,
        'items': items,
        'soa_totals': soa_totals,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': timezone.now(),
        'statement_date': timezone.localdate(),
    }
    return render(request, 'billing/statement_of_account.html', context)
