from collections import OrderedDict
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.permissions import staff_required, admin_required, get_user_role, collector_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import transaction
from datetime import date, datetime

from core.models import Billing, Tenant, Stall, RentalContract, Payment, TenantLedger, AuditLog, SystemSetting
from core.forms import BillingForm, QuickCollectForm
from core.helpers import (
    ensure_current_month_billings, ensure_initial_billing, render_to_pdf_response,
    record_payment, maybe_apply_overdue_penalties, receipt_print_url,
    generate_receipt_number,
)


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
    # Auto-ensure current month billings for collectors/cashiers — seamless workflow: new contracts immediately billable
    try:
        if get_user_role(request.user) in {'admin', 'collector', 'cashier', 'supervisor', 'treasurer'} or request.user.is_superuser:
            ensure_current_month_billings()
            maybe_apply_overdue_penalties()
    except Exception:
        pass

    billings = Billing.objects.select_related(
        'tenant', 'stall', 'contract'
    ).all()

    # Tenant isolation: show only own billings
    if get_user_role(request.user) == 'tenant':
        billings = billings.filter(tenant__user=request.user)

    month_filter = request.GET.get('month')
    year_filter = request.GET.get('year')
    tenant_filter = request.GET.get('tenant')
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search') or request.GET.get('q') or ''
    search_query = search_query.strip()

    if month_filter:
        billings = billings.filter(billing_month=month_filter)
    if year_filter:
        billings = billings.filter(billing_year=year_filter)
    if tenant_filter:
        billings = billings.filter(tenant_id=tenant_filter)
    if status_filter:
        billings = billings.filter(status=status_filter)
    if search_query:
        billings = billings.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(tenant__business_name__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(stall__section__name__icontains=search_query) |
            Q(contract__id__icontains=search_query)
        )

    # Order so grouping is stable and each tenant's months read oldest→newest.
    billings = billings.order_by(
        'tenant__full_name', 'billing_year', 'billing_month', 'created_at', 'id'
    )

    totals = billings.aggregate(
        due=Sum('total_due'),
        paid=Sum('amount_paid'),
        balance=Sum('balance'),
    )
    total_due = totals['due'] or 0
    total_paid = totals['paid'] or 0
    total_balance = totals['balance'] or 0

    # Collapse to one visual group per tenant so a tenant with N outstanding
    # months appears as a single card in the list instead of N rows.
    groups: "OrderedDict[int, dict]" = OrderedDict()
    for b in billings:
        key = b.tenant_id
        g = groups.get(key)
        if g is None:
            g = {
                'tenant': b.tenant,
                'stalls': [],
                'billings': [],
                'total_due': Decimal('0.00'),
                'total_paid': Decimal('0.00'),
                'total_balance': Decimal('0.00'),
                'unpaid_count': 0,
                'oldest_period': None,
                'newest_period': None,
            }
            groups[key] = g
        g['billings'].append(b)
        g['total_due'] += Decimal(str(b.total_due))
        g['total_paid'] += Decimal(str(b.amount_paid))
        g['total_balance'] += Decimal(str(b.balance))
        if b.balance and b.balance > 0:
            g['unpaid_count'] += 1
        if b.stall.stall_number not in g['stalls']:
            g['stalls'].append(b.stall.stall_number)
        period = (b.billing_year, b.billing_month)
        if g['oldest_period'] is None or period < g['oldest_period']:
            g['oldest_period'] = period
        if g['newest_period'] is None or period > g['newest_period']:
            g['newest_period'] = period

    paginator = Paginator(list(groups.values()), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'month_filter': month_filter,
        'year_filter': year_filter,
        'tenant_filter': tenant_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_due': total_due,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'tenant_count': len(groups),
        'pagination_target': 'billing-table-wrapper',
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
    payments = Payment.objects.filter(billing=billing).order_by('-payment_date', '-created_at', '-id')
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


@collector_required
@transaction.atomic
def billing_collect(request, pk):
    """
    Simplified collector workflow: billing is already present (auto-generated on contract).
    Collector only enters Amount and confirms Paid. System handles Payment + Ledger + Billing update.
    """
    billing = get_object_or_404(Billing.objects.select_related('tenant', 'stall', 'stall__section', 'contract'), pk=pk)
    # Already paid? Show info
    if billing.status == 'Paid' and billing.balance == 0:
        if is_htmx(request):
            from django.http import HttpResponse
            return HttpResponse('''<script>showToast('This billing is already fully paid.', 'info'); closeModal();</script>''')
        messages.info(request, 'This billing is already fully paid.')
        return redirect('billing_list')

    from core.forms import QuickCollectForm
    if request.method == 'POST':
        form = QuickCollectForm(request.POST, billing=billing)
        if form.is_valid():
            amount = form.cleaned_data['amount_paid']
            # The amount alone decides the outcome: less than the balance is a
            # partial payment, the balance (or the 0.01 tolerance) settles it.
            if amount > billing.balance:
                amount = billing.balance

            # Single source of truth for Payment + Billing totals + Ledger credit.
            payment = record_payment(
                tenant=billing.tenant,
                billing=billing,
                amount=amount,
                payment_date=form.cleaned_data['payment_date'],
                payment_method=form.cleaned_data['payment_method'],
                collected_by=request.user,
                remarks=form.cleaned_data.get('remarks', ''),
            )
            billing = payment.billing
            amount = payment.amount_paid
            receipt_number = payment.receipt_number

            if billing.balance > 0:
                outcome = f'Partial payment — ₱{billing.balance:.2f} remaining'
            else:
                outcome = 'Paid in full'

            AuditLog.objects.create(
                user=request.user,
                action='COLLECT',
                module='Billing',
                description=f'Collected ₱{amount} ({outcome}) for {billing.tenant.full_name} - {billing.stall.stall_number} {billing.billing_month:02d}/{billing.billing_year} (Receipt {receipt_number})',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            # A collection is not finished until the receipt can be printed, so
            # both entry points end on the auto-printing receipt page.
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse(f'''<script>
                    closeModal();
                    location.href = '{receipt_print_url(payment, back="billing")}';
                </script>''')
            messages.success(
                request,
                f'Collected ₱{amount:.2f} for {billing.tenant.full_name}. {outcome}. '
                f'Receipt: {receipt_number}'
            )
            return redirect(receipt_print_url(payment, back='billing'))
        else:
            if is_htmx(request):
                return render(request, 'billing/_collect_modal.html', {'form': form, 'billing': billing})
    else:
        from core.forms import QuickCollectForm
        form = QuickCollectForm(billing=billing)

    return render(request, 'billing/_collect_modal.html', {'form': form, 'billing': billing})


@collector_required
def billing_quick_pay(request, pk):
    """Alias for billing_collect to support legacy links."""
    return billing_collect(request, pk)


def _tenant_outstanding_qs(tenant):
    """Every billing for ``tenant`` that still carries a balance, oldest first.

    Includes Paid months so the collector sees the full contract history; the
    template marks which rows are open.
    """
    return (
        Billing.objects.filter(tenant=tenant)
        .select_related('stall', 'stall__section', 'contract')
        .order_by('billing_year', 'billing_month', 'stall__stall_number')
    )


@collector_required
@transaction.atomic
def billing_tenant_collect(request, tenant_pk):
    """Grouped collection workspace for one tenant.

    Lists every billing month (past and current) tied to the tenant's
    contracts, oldest first, so the collector can review the complete picture
    before tapping Collect. The batch form below lets them tick specific
    months (or all outstanding ones) and settle them in a single action —
    each ticked month produces its own official receipt via the shared
    ``record_payment`` service so ledger, billing status and audit trail stay
    identical to the one-month modal flow.
    """
    tenant = get_object_or_404(Tenant, pk=tenant_pk)

    # Backfill months that were never generated for this tenant's contracts —
    # idempotent, safe to call on every page load. Covers ending months inside
    # a contract window so nothing is silently skipped.
    try:
        for contract in tenant.contracts.select_related('tenant', 'stall'):
            ensure_initial_billing(contract)
    except Exception:
        pass

    billings = list(_tenant_outstanding_qs(tenant))
    outstanding = [b for b in billings if b.balance and b.balance > 0 and b.status != 'Paid']
    total_outstanding = sum((Decimal(str(b.balance)) for b in outstanding), Decimal('0.00'))

    if request.method == 'POST':
        selected_ids = {int(x) for x in request.POST.getlist('billing_ids') if x.isdigit()}
        if not selected_ids:
            messages.error(request, 'Select at least one billing month to collect.')
            return redirect('billing_tenant_collect', tenant_pk=tenant.pk)

        raw_date = (request.POST.get('payment_date') or '').strip()
        try:
            pay_date = datetime.strptime(raw_date, '%Y-%m-%d').date() if raw_date else date.today()
        except ValueError:
            messages.error(request, 'Invalid payment date.')
            return redirect('billing_tenant_collect', tenant_pk=tenant.pk)

        payment_method = request.POST.get('payment_method') or 'Cash'
        if payment_method not in dict(Payment.PAYMENT_METHOD_CHOICES):
            payment_method = 'Cash'
        remarks = (request.POST.get('remarks') or '').strip()

        # Re-query with select_for_update inside the transaction so concurrent
        # collectors cannot settle the same month twice while this page loads.
        billings_map = {
            b.pk: b
            for b in Billing.objects.select_for_update().filter(
                pk__in=selected_ids, tenant=tenant
            )
        }
        # Always settle oldest first so partials line up with the contract.
        ordered = sorted(billings_map.values(), key=lambda b: (b.billing_year, b.billing_month, b.stall_id))

        # Pre-generate ONE official receipt number for the whole batch. Every
        # Payment row shares this OR so the printed document is a single
        # consolidated receipt — not three separate ones. Internal
        # ``receipt_number`` stays unique per row to satisfy the DB constraint,
        # but only the shared OR is surfaced to the collector and tenant.
        shared_or = generate_receipt_number()

        created_payments = []
        for billing in ordered:
            if billing.status == 'Paid' or Decimal(str(billing.balance)) <= 0:
                continue
            amount = Decimal(str(billing.balance))
            payment = record_payment(
                tenant=tenant,
                billing=billing,
                amount=amount,
                payment_date=pay_date,
                payment_method=payment_method,
                collected_by=request.user,
                remarks=remarks,
                official_receipt_no=shared_or,
            )
            created_payments.append(payment)

        if not created_payments:
            messages.info(request, 'Nothing to collect — the selected months are already settled.')
            return redirect('billing_tenant_collect', tenant_pk=tenant.pk)

        total_collected = sum((p.amount_paid for p in created_payments), Decimal('0.00'))
        periods = ', '.join(
            f'{p.billing_month:02d}/{p.billing_year}' for p in created_payments
        )
        AuditLog.objects.create(
            user=request.user,
            action='COLLECT_BATCH',
            module='Billing',
            description=(
                f'Batch collected {len(created_payments)} month(s) [{periods}] '
                f'for {tenant.full_name} — ₱{total_collected} '
                f'under consolidated OR {shared_or}'
            ),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(
            request,
            f'Collected {len(created_payments)} month(s) totalling ₱{total_collected:.2f} '
            f'under OR {shared_or}.',
        )
        # Stash the batch so the printable page renders every month as one
        # line item on a single consolidated receipt.
        from core.views.payments import BATCH_RECEIPT_SESSION_KEY
        request.session[BATCH_RECEIPT_SESSION_KEY] = [p.pk for p in created_payments]
        if len(created_payments) == 1:
            # Single-month batch: keep the classic one-receipt flow.
            return redirect(receipt_print_url(created_payments[0], back='billing'))
        from django.urls import reverse
        return redirect(f"{reverse('payment_batch_receipt')}?auto=1&back=billing")

    context = {
        'tenant': tenant,
        'billings': billings,
        'outstanding': outstanding,
        'total_outstanding': total_outstanding,
        'today': date.today(),
        'payment_methods': Payment.PAYMENT_METHOD_CHOICES,
    }
    return render(request, 'billing/collect_grouped.html', context)


@login_required
def billing_list_print(request):
    try:
        if get_user_role(request.user) in {'admin', 'collector', 'cashier', 'supervisor', 'treasurer'} or request.user.is_superuser:
            ensure_current_month_billings()
            maybe_apply_overdue_penalties()
    except Exception:
        pass
    billings = Billing.objects.select_related('tenant', 'stall', 'contract').all().order_by('-billing_year', '-billing_month', '-created_at', '-id')
    if get_user_role(request.user) == 'tenant':
        billings = billings.filter(tenant__user=request.user)
    month_filter = request.GET.get('month')
    year_filter = request.GET.get('year')
    tenant_filter = request.GET.get('tenant')
    status_filter = request.GET.get('status')
    search_query = (request.GET.get('search') or '').strip()
    if month_filter:
        billings = billings.filter(billing_month=month_filter)
    if year_filter:
        billings = billings.filter(billing_year=year_filter)
    if tenant_filter:
        billings = billings.filter(tenant_id=tenant_filter)
    if status_filter:
        billings = billings.filter(status=status_filter)
    if search_query:
        billings = billings.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(tenant__business_name__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(stall__section__name__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'billings': billings,
        'month_filter': month_filter,
        'year_filter': year_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'billing/print_list.html', context)


@login_required
def billing_list_export_pdf(request):
    try:
        if get_user_role(request.user) in {'admin', 'collector', 'cashier', 'supervisor', 'treasurer'} or request.user.is_superuser:
            ensure_current_month_billings()
            maybe_apply_overdue_penalties()
    except Exception:
        pass
    billings = Billing.objects.select_related('tenant', 'stall', 'contract').all().order_by('-billing_year', '-billing_month', '-created_at', '-id')
    if get_user_role(request.user) == 'tenant':
        billings = billings.filter(tenant__user=request.user)
    month_filter = request.GET.get('month')
    year_filter = request.GET.get('year')
    tenant_filter = request.GET.get('tenant')
    status_filter = request.GET.get('status')
    search_query = (request.GET.get('search') or '').strip()
    if month_filter:
        billings = billings.filter(billing_month=month_filter)
    if year_filter:
        billings = billings.filter(billing_year=year_filter)
    if tenant_filter:
        billings = billings.filter(tenant_id=tenant_filter)
    if status_filter:
        billings = billings.filter(status=status_filter)
    if search_query:
        billings = billings.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(tenant__business_name__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(stall__section__name__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'billings': billings,
        'month_filter': month_filter,
        'year_filter': year_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"billing_list_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'billing/print_list.html', context, filename=filename)


@login_required
def billing_view_print(request, pk):
    billing = get_object_or_404(Billing.objects.select_related('tenant', 'stall', 'stall__section', 'contract'), pk=pk)
    if get_user_role(request.user) == 'tenant' and billing.tenant.user != request.user:
        messages.error(request, 'You can only view your own billing.')
        return redirect('dashboard')
    payments = Payment.objects.filter(billing=billing).order_by('-payment_date', '-created_at', '-id')
    from core.models import SystemSetting
    context = {
        'billing': billing,
        'payments': payments,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'billing/print_view.html', context)


@login_required
def billing_view_export_pdf(request, pk):
    billing = get_object_or_404(Billing.objects.select_related('tenant', 'stall', 'stall__section', 'contract'), pk=pk)
    if get_user_role(request.user) == 'tenant' and billing.tenant.user != request.user:
        messages.error(request, 'You can only view your own billing.')
        return redirect('dashboard')
    payments = Payment.objects.filter(billing=billing).order_by('-payment_date', '-created_at', '-id')
    from core.models import SystemSetting
    context = {
        'billing': billing,
        'payments': payments,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"billing_{billing.billing_month:02d}-{billing.billing_year}_{billing.tenant.tenant_id}_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'billing/print_view.html', context, filename=filename)
