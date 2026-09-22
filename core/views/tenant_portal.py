# core/views/tenant_portal.py
# Tenant self-service portal: a read-only, strictly isolated dashboard where a
# logged-in Tenant can review their own balance, payment milestones, upcoming
# due dates and complete transaction history. All data is scoped to the Tenant
# record linked to ``request.user``; there is no cross-tenant access.

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from datetime import date
from decimal import Decimal

from core.models import RentalContract, Billing, Payment, TenantLedger, AuditLog
from core.forms import TenantPasswordChangeForm
from core.permissions import tenant_required, get_request_tenant


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


def _zero(value):
    return value if value is not None else Decimal('0.00')


def _render_no_tenant(request):
    """Rendered when a tenant-role account has no linked Tenant record."""
    return render(request, 'tenant_portal/no_tenant.html', {}, 200)


def _must_change_password(request):
    """True if the logged-in tenant still has a temporary auto-generated password."""
    profile = getattr(request.user, 'profile', None)
    return bool(profile and profile.must_change_password)


def _tenant_summary(tenant):
    """Authoritative financial totals for a single tenant (never cross-tenant)."""
    billings = Billing.objects.filter(tenant=tenant)
    payments = Payment.objects.filter(tenant=tenant, status__in=['Paid', 'Partial'])

    outstanding_qs = billings.filter(status__in=['Unpaid', 'Partial', 'Overdue'])
    total_billed = _zero(billings.aggregate(t=Sum('total_due'))['t'])
    total_paid = _zero(payments.aggregate(t=Sum('amount_paid'))['t'])
    outstanding_balance = _zero(outstanding_qs.aggregate(t=Sum('balance'))['t'])
    overdue_qs = outstanding_qs.filter(status='Overdue')
    overdue_balance = _zero(overdue_qs.aggregate(t=Sum('balance'))['t'])
    overdue_count = overdue_qs.count()

    return {
        'total_billed': total_billed,
        'total_paid': total_paid,
        'outstanding_balance': outstanding_balance,
        'overdue_balance': overdue_balance,
        'overdue_count': overdue_count,
    }


@tenant_required
def tenant_portal_dashboard(request):
    tenant = get_request_tenant(request.user)
    if not tenant:
        return _render_no_tenant(request)

    if _must_change_password(request):
        messages.info(request, 'Please set a new password before using your portal.')
        return redirect('tenant_portal_password')

    today = date.today()
    summary = _tenant_summary(tenant)

    billings = Billing.objects.filter(tenant=tenant).select_related('stall', 'contract')
    payments = Payment.objects.filter(tenant=tenant).select_related('stall', 'billing', 'collected_by')

    active_contract = (
        RentalContract.objects.filter(tenant=tenant, status='Active')
        .select_related('stall', 'stall__section')
        .first()
    )
    active_stalls = (
        RentalContract.objects.filter(tenant=tenant, status='Active')
        .select_related('stall', 'stall__section')
        .order_by('stall__stall_number')
    )

    # Payment milestones: fully paid vs partial payments.
    fully_paid = (
        payments.filter(status='Paid')
        .order_by('-payment_date', '-created_at')[:6]
    )
    partial_paid = (
        payments.filter(status='Partial')
        .order_by('-payment_date', '-created_at')[:6]
    )

    # Upcoming due dates: still-outstanding bills with a due date from today forward.
    upcoming = (
        billings.filter(status__in=['Unpaid', 'Partial', 'Overdue'], due_date__gte=today)
        .order_by('due_date')[:6]
    )
    # If nothing is scheduled ahead, surface the most overdue items so the card is useful.
    if not upcoming:
        upcoming = (
            billings.filter(status__in=['Unpaid', 'Partial', 'Overdue'])
            .order_by('due_date')[:6]
        )

    # Recent transaction history (billing debits + payment credits) from the ledger.
    recent_ledger = (
        TenantLedger.objects.filter(tenant=tenant)
        .select_related('billing', 'billing__stall', 'payment')
        .order_by('-transaction_date', '-id')[:8]
    )

    context = {
        'tenant': tenant,
        'active_contract': active_contract,
        'active_stalls': active_stalls,
        'today': today,
        **summary,
        'fully_paid': fully_paid,
        'partial_paid': partial_paid,
        'upcoming': upcoming,
        'recent_ledger': recent_ledger,
    }
    return render(request, 'tenant_portal/dashboard.html', context)


@tenant_required
def tenant_portal_history(request):
    tenant = get_request_tenant(request.user)
    if not tenant:
        return _render_no_tenant(request)

    if _must_change_password(request):
        messages.info(request, 'Please set a new password before using your portal.')
        return redirect('tenant_portal_password')

    summary = _tenant_summary(tenant)

    base_entries = TenantLedger.objects.filter(tenant=tenant)
    available_years = sorted(
        {y for y in base_entries.values_list('transaction_date__year', flat=True) if y},
        reverse=True,
    )

    entries = base_entries.select_related('billing', 'billing__stall', 'payment')

    type_filter = (request.GET.get('type') or '').strip()
    year_filter = (request.GET.get('year') or '').strip()
    month_filter = (request.GET.get('month') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    search_query = (request.GET.get('search') or '').strip()

    if type_filter == 'billing':
        entries = entries.filter(debit__gt=0)
    elif type_filter == 'payment':
        entries = entries.filter(credit__gt=0)
    if year_filter:
        entries = entries.filter(transaction_date__year=year_filter)
    if month_filter:
        entries = entries.filter(transaction_date__month=month_filter)
    if status_filter:
        entries = entries.filter(
            Q(billing__status=status_filter) | Q(payment__status=status_filter)
        )
    if search_query:
        entries = entries.filter(
            Q(description__icontains=search_query)
            | Q(billing__stall__stall_number__icontains=search_query)
            | Q(payment__receipt_number__icontains=search_query)
        )

    entries = entries.order_by('-transaction_date', '-id')

    paginator = Paginator(entries, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'tenant': tenant,
        'page_obj': page_obj,
        'available_years': available_years,
        'type_filter': type_filter,
        'year_filter': year_filter,
        'month_filter': month_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'pagination_target': 'portal-history-wrapper',
        **summary,
    }
    template = 'tenant_portal/_history_table.html' if is_htmx(request) else 'tenant_portal/history.html'
    return render(request, template, context)


@tenant_required
def tenant_portal_password(request):
    """Tenant self-service password change.

    Reached from the portal nav, and enforced automatically on first login
    while the account still carries an admin-generated temporary password.
    """
    tenant = get_request_tenant(request.user)
    forcing = _must_change_password(request)

    if request.method == 'POST':
        form = TenantPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Keep the session valid after the password changes.
            update_session_auth_hash(request, user)
            profile = getattr(user, 'profile', None)
            if profile:
                profile.must_change_password = False
                profile.save(update_fields=['must_change_password'])
            AuditLog.objects.create(
                user=user,
                action='PASSWORD_CHANGE',
                module='Tenant',
                description=f'{user.username} changed their own password',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('tenant_portal')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = TenantPasswordChangeForm(request.user)

    return render(request, 'tenant_portal/password.html', {
        'tenant': tenant,
        'form': form,
        'forcing': forcing,
    })
