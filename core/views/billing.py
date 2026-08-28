from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.permissions import staff_required, admin_required, get_user_role
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from datetime import date, datetime

from core.models import Billing, Tenant, Stall, RentalContract, Payment, TenantLedger, AuditLog, SystemSetting
from core.forms import BillingForm


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


def compute_penalty(contract, billing_month, billing_year, due_date):
    from datetime import timedelta
    settings = SystemSetting.objects.first()
    if not settings:
        return 0
    penalty_settings = contract.penalty_settings.filter(is_active=True).first()
    if penalty_settings:
        p_type = penalty_settings.penalty_type
        p_value = penalty_settings.penalty_value
        grace = penalty_settings.grace_period
    else:
        p_type = settings.penalty_type
        p_value = settings.penalty_value
        grace = settings.grace_period
    today = date.today()
    # Honor grace period: penalty only after due_date + grace days
    if today <= due_date + timedelta(days=grace or 0):
        return 0
    if p_type == 'fixed':
        return p_value
    elif p_type == 'percentage':
        return contract.monthly_rent * (p_value / 100)
    return 0


def safe_due_date(year, month, due_day):
    """Create due date safely handling 28/29/30/31 edge — use last day of month if due_day exceeds month length."""
    import calendar
    _, last_day = calendar.monthrange(int(year), int(month))
    safe_day = min(int(due_day), last_day)
    return date(int(year), int(month), safe_day)


@login_required
def billing_list(request):
    billings = Billing.objects.select_related(
        'tenant', 'stall', 'contract'
    ).all().order_by('-billing_year', '-billing_month')

    # Tenant isolation: show only own billings
    if get_user_role(request.user) == 'tenant':
        billings = billings.filter(tenant__user=request.user)

    month_filter = request.GET.get('month')
    year_filter = request.GET.get('year')
    tenant_filter = request.GET.get('tenant')
    status_filter = request.GET.get('status')

    if month_filter:
        billings = billings.filter(billing_month=month_filter)
    if year_filter:
        billings = billings.filter(billing_year=year_filter)
    if tenant_filter:
        billings = billings.filter(tenant_id=tenant_filter)
    if status_filter:
        billings = billings.filter(status=status_filter)

    paginator = Paginator(billings, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_due = billings.aggregate(total=Sum('total_due'))['total'] or 0
    total_paid = billings.aggregate(total=Sum('amount_paid'))['total'] or 0
    total_balance = billings.aggregate(total=Sum('balance'))['total'] or 0

    context = {
        'page_obj': page_obj,
        'month_filter': month_filter,
        'year_filter': year_filter,
        'tenant_filter': tenant_filter,
        'status_filter': status_filter,
        'total_due': total_due,
        'total_paid': total_paid,
        'total_balance': total_balance,
    }
    if is_htmx(request):
        return render(request, 'billing/_table.html', context)
    return render(request, 'billing/list.html', context)


@staff_required
def billing_generate(request):
    if request.method == 'POST':
        tenant_id = request.POST.get('tenant')
        contract_id = request.POST.get('contract')
        billing_month = request.POST.get('billing_month')
        billing_year = request.POST.get('billing_year')

        contract = get_object_or_404(RentalContract, pk=contract_id)
        stall = contract.stall
        tenant = contract.tenant

        existing = Billing.objects.filter(
            tenant=tenant, stall=stall,
            billing_month=billing_month, billing_year=billing_year
        ).first()
        if existing:
            messages.warning(request, f'Billing already exists for {tenant.full_name} - {stall.stall_number} ({billing_month}/{billing_year}).')
            return redirect('billing_list')

        due_day = contract.due_day
        due_date = safe_due_date(billing_year, billing_month, due_day)
        rental_amount = contract.monthly_rent
        penalty_amount = compute_penalty(contract, billing_month, billing_year, due_date)
        total_due = rental_amount + penalty_amount

        billing = Billing.objects.create(
            tenant=tenant,
            stall=stall,
            contract=contract,
            billing_month=billing_month,
            billing_year=billing_year,
            rental_amount=rental_amount,
            penalty_amount=penalty_amount,
            discount=0,
            total_due=total_due,
            amount_paid=0,
            balance=total_due,
            due_date=due_date,
            status='Unpaid',
        )

        TenantLedger.objects.create(
            tenant=tenant,
            billing=billing,
            transaction_date=due_date,
            description=f'Rental billing for {billing_month}/{billing_year} - {stall.stall_number}',
            debit=total_due,
            credit=0,
            balance=total_due,
        )

        AuditLog.objects.create(
            user=request.user,
            action='GENERATE',
            module='Billing',
            description=f'Generated billing for {tenant.full_name} - {stall.stall_number} ({billing_month}/{billing_year})',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        messages.success(request, f'Billing generated for {tenant.full_name}. Total due: {total_due}')
        return redirect('billing_list')

    tenants = Tenant.objects.filter(status='Active')
    contracts = RentalContract.objects.filter(status='Active').select_related('tenant', 'stall')
    now = date.today()
    context = {
        'tenants': tenants,
        'contracts': contracts,
        'current_month': now.month,
        'current_year': now.year,
    }
    return render(request, 'billing/generate.html', context)


@staff_required
def billing_generate_all(request):
    if request.method == 'POST':
        now = date.today()
        billing_month = request.POST.get('billing_month', now.month)
        billing_year = request.POST.get('billing_year', now.year)

        active_contracts = RentalContract.objects.filter(status='Active').select_related('tenant', 'stall')
        count = 0
        for contract in active_contracts:
            existing = Billing.objects.filter(
                tenant=contract.tenant, stall=contract.stall,
                billing_month=billing_month, billing_year=billing_year
            ).exists()
            if existing:
                continue

            due_day = contract.due_day
            due_date = safe_due_date(billing_year, billing_month, due_day)
            rental_amount = contract.monthly_rent
            penalty_amount = compute_penalty(contract, billing_month, billing_year, due_date)
            total_due = rental_amount + penalty_amount

            billing = Billing.objects.create(
                tenant=contract.tenant,
                stall=contract.stall,
                contract=contract,
                billing_month=billing_month,
                billing_year=billing_year,
                rental_amount=rental_amount,
                penalty_amount=penalty_amount,
                discount=0,
                total_due=total_due,
                amount_paid=0,
                balance=total_due,
                due_date=due_date,
                status='Unpaid',
            )

            TenantLedger.objects.create(
                tenant=contract.tenant,
                billing=billing,
                transaction_date=due_date,
                description=f'Rental billing for {billing_month}/{billing_year} - {contract.stall.stall_number}',
                debit=total_due,
                credit=0,
                balance=total_due,
            )
            count += 1

        AuditLog.objects.create(
            user=request.user,
            action='GENERATE_ALL',
            module='Billing',
            description=f'Generated {count} billings for {billing_month}/{billing_year}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        messages.success(request, f'Generated {count} billings for {billing_month}/{billing_year}.')
        return redirect('billing_list')

    now = date.today()
    context = {
        'current_month': now.month,
        'current_year': now.year,
    }
    return render(request, 'billing/generate_all.html', context)


@login_required
def billing_view(request, pk):
    billing = get_object_or_404(
        Billing.objects.select_related('tenant', 'stall', 'stall__section', 'contract'),
        pk=pk
    )
    if get_user_role(request.user) == 'tenant' and billing.tenant.user != request.user:
        messages.error(request, 'You can only view your own billing.')
        return redirect('dashboard')
    payments = Payment.objects.filter(billing=billing).order_by('-payment_date')
    context = {
        'billing': billing,
        'payments': payments,
    }
    return render(request, 'billing/view.html', context)


@staff_required
def billing_add_modal(request):
    if request.method == 'POST':
        form = BillingForm(request.POST)
        if form.is_valid():
            billing = form.save()
            TenantLedger.objects.create(
                tenant=billing.tenant,
                billing=billing,
                transaction_date=billing.due_date,
                description=f'Billing for {billing.billing_month}/{billing.billing_year} - {billing.stall.stall_number}',
                debit=billing.total_due,
                credit=0,
                balance=billing.total_due,
            )
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Billing',
                description=f'Created billing for {billing.tenant.full_name} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Billing created.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Billing created.')
            return redirect('billing_list')
        if is_htmx(request):
            return render(request, 'billing/_modal_form.html', {'form': form, 'is_add': True})
    else:
        form = BillingForm()
    return render(request, 'billing/_modal_form.html', {'form': form, 'is_add': True})


@staff_required
def billing_edit_modal(request, pk):
    billing = get_object_or_404(Billing, pk=pk)
    if request.method == 'POST':
        form = BillingForm(request.POST, instance=billing)
        if form.is_valid():
            billing = form.save()
            # Update corresponding ledger debit and recompute chain
            try:
                ledger = TenantLedger.objects.filter(billing=billing, debit__gt=0).order_by('transaction_date').first()
                if ledger:
                    ledger.debit = billing.total_due
                    ledger.save(update_fields=['debit'])
                # Recompute running balances for this tenant
                from core.helpers import recalc_tenant_ledger
                recalc_tenant_ledger(billing.tenant)
            except Exception:
                pass
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='Billing',
                description=f'Updated billing for {billing.tenant.full_name} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                resp = HttpResponse('''<script>
                    closeModal();
                    showToast('Billing updated.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
                return resp
            messages.success(request, 'Billing updated.')
            return redirect('billing_list')
        if is_htmx(request):
            return render(request, 'billing/_modal_form.html', {'form': form, 'is_add': False, 'billing': billing})
    else:
        form = BillingForm(instance=billing)
    return render(request, 'billing/_modal_form.html', {'form': form, 'is_add': False, 'billing': billing})
