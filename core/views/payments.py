from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.permissions import staff_required, admin_required, get_user_role
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import transaction
from datetime import date

from core.models import (
    Payment, Billing, Tenant, Stall, RentalContract,
    TenantLedger, AuditLog, SystemSetting
)
from core.forms import PaymentForm
from core.helpers import (
    render_to_pdf_response, record_payment, recalc_billing_from_payments,
)


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@login_required
def payment_list(request):
    payments = Payment.objects.select_related(
        'tenant', 'stall', 'collected_by'
    ).all().order_by('-payment_date', '-created_at')

    # Tenant isolation: tenants see only own payments
    if get_user_role(request.user) == 'tenant':
        payments = payments.filter(tenant__user=request.user)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    tenant_filter = request.GET.get('tenant')
    stall_filter = request.GET.get('stall')
    collector_filter = request.GET.get('collector')
    status_filter = request.GET.get('status')
    payment_method = request.GET.get('payment_method')
    search_query = (request.GET.get('search') or request.GET.get('q') or '').strip()

    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    if tenant_filter:
        payments = payments.filter(tenant_id=tenant_filter)
    if stall_filter:
        payments = payments.filter(stall_id=stall_filter)
    if collector_filter:
        payments = payments.filter(collected_by_id=collector_filter)
    if status_filter:
        payments = payments.filter(status=status_filter)
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    if search_query:
        payments = payments.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(receipt_number__icontains=search_query) |
            Q(official_receipt_no__icontains=search_query) |
            Q(collected_by__first_name__icontains=search_query) |
            Q(collected_by__last_name__icontains=search_query) |
            Q(collected_by__username__icontains=search_query)
        )

    paginator = Paginator(payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_amount = payments.aggregate(total=Sum('amount_paid'))['total'] or 0

    context = {
        'page_obj': page_obj,
        'total_amount': total_amount,
        'date_from': date_from,
        'date_to': date_to,
        'tenant_filter': tenant_filter,
        'stall_filter': stall_filter,
        'collector_filter': collector_filter,
        'status_filter': status_filter,
        'payment_method': payment_method,
        'search_query': search_query,
        'pagination_target': 'payment-table-wrapper',
    }
    template = 'payments/_table.html' if is_htmx(request) else 'payments/list.html'
    return render(request, template, context)


@staff_required
@transaction.atomic
def payment_add(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            draft = form.save(commit=False)
            # Single source of truth: creates Payment, updates Billing, posts ledger credit.
            payment = record_payment(
                tenant=draft.tenant,
                billing=draft.billing,
                amount=draft.amount_paid,
                payment_date=draft.payment_date,
                payment_method=draft.payment_method,
                collected_by=request.user,
                remarks=draft.remarks,
                official_receipt_no=draft.official_receipt_no,
            )

            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Payment',
                description=f'Recorded payment {payment.receipt_number} for {payment.tenant.full_name} - {payment.amount_paid}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            messages.success(
                request,
                f'Payment recorded. Receipt: {payment.receipt_number}, Amount: {payment.amount_paid}'
            )
            return redirect('payment_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentForm(initial={'payment_date': date.today()})

    tenants = Tenant.objects.filter(status='Active')
    context = {
        'form': form,
        'tenants': tenants,
        'is_add': True,
    }
    return render(request, 'payments/form.html', context)


@login_required
def payment_view(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related('tenant', 'stall', 'stall__section', 'billing', 'collected_by'),
        pk=pk
    )
    if get_user_role(request.user) == 'tenant' and payment.tenant.user != request.user:
        messages.error(request, 'You can only view your own payments.')
        return redirect('dashboard')
    ledger_entries = TenantLedger.objects.filter(payment=payment).order_by('transaction_date')
    context = {
        'payment': payment,
        'ledger_entries': ledger_entries,
    }
    return render(request, 'payments/view.html', context)


@login_required
def payment_receipt(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related('tenant', 'stall', 'stall__section', 'collected_by'),
        pk=pk
    )
    if get_user_role(request.user) == 'tenant' and payment.tenant.user != request.user:
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(request, 'You can only view your own payment receipt.')
        return redirect('dashboard')
    settings = SystemSetting.objects.first()
    context = {
        'payment': payment,
        'settings': settings,
    }
    return render(request, 'payments/receipt.html', context)


@login_required
def payment_print_receipt(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related('tenant', 'stall', 'stall__section', 'collected_by'),
        pk=pk
    )
    if get_user_role(request.user) == 'tenant' and payment.tenant.user != request.user:
        messages.error(request, 'You can only view your own payment receipt.')
        return redirect('dashboard')
    settings = SystemSetting.objects.first()
    context = {
        'payment': payment,
        'settings': settings,
    }
    return render(request, 'payments/print_receipt.html', context)


@login_required
def payment_receipt_export_pdf(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related('tenant', 'stall', 'stall__section', 'collected_by'),
        pk=pk
    )
    if get_user_role(request.user) == 'tenant' and payment.tenant.user != request.user:
        messages.error(request, 'You can only view your own payment receipt.')
        return redirect('dashboard')
    from core.models import SystemSetting
    context = {
        'payment': payment,
        'settings': SystemSetting.objects.first(),
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
    }
    filename = f"receipt_{payment.receipt_number}_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'payments/print_receipt.html', context, filename=filename)


@staff_required
@transaction.atomic
def payment_add_modal(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            draft = form.save(commit=False)
            payment = record_payment(
                tenant=draft.tenant,
                billing=draft.billing,
                amount=draft.amount_paid,
                payment_date=draft.payment_date,
                payment_method=draft.payment_method,
                collected_by=request.user,
                remarks=draft.remarks,
                official_receipt_no=draft.official_receipt_no,
            )

            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Payment',
                description=f'Recorded payment {payment.receipt_number} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Payment recorded.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Payment recorded.')
            return redirect('payment_list')
        if is_htmx(request):
            return render(request, 'payments/_modal_form.html', {'form': form, 'is_add': True})
    else:
        form = PaymentForm(initial={'payment_date': date.today()})
    return render(request, 'payments/_modal_form.html', {'form': form, 'is_add': True})


@staff_required
@transaction.atomic
def payment_edit_modal(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    old_billing = payment.billing
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            payment = form.save()
            # Recompute the affected billing(s) authoritatively from valid payments.
            billing = recalc_billing_from_payments(payment.billing)
            if old_billing and old_billing.pk != billing.pk:
                recalc_billing_from_payments(old_billing)
            # Update ledger entry for this payment
            ledger_qs = TenantLedger.objects.filter(payment=payment)
            if ledger_qs.exists():
                ledger_qs.update(credit=payment.amount_paid, transaction_date=payment.payment_date, description=f'Payment {payment.receipt_number} - {payment.payment_method}')
            else:
                # Create if missing
                TenantLedger.objects.create(
                    tenant=payment.tenant,
                    billing=billing,
                    transaction_date=payment.payment_date,
                    description=f'Payment {payment.receipt_number} - {payment.payment_method}',
                    debit=0,
                    credit=payment.amount_paid,
                    balance=0,
                    payment=payment,
                )
            from core.helpers import recalc_tenant_ledger
            # Recalc both old and new tenant ledgers if tenant changed
            recalc_tenant_ledger(payment.tenant)
            if old_billing and old_billing.tenant_id != payment.tenant_id:
                # Need tenant from old_billing
                try:
                    recalc_tenant_ledger(old_billing.tenant)
                except Exception:
                    pass
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='Payment',
                description=f'Updated payment {payment.receipt_number} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Payment updated.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Payment updated.')
            return redirect('payment_list')
        if is_htmx(request):
            return render(request, 'payments/_modal_form.html', {'form': form, 'is_add': False, 'payment': payment})
    else:
        form = PaymentForm(instance=payment)
    return render(request, 'payments/_modal_form.html', {'form': form, 'is_add': False, 'payment': payment})


@staff_required
@transaction.atomic
def payment_void(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        old_status = payment.status
        payment.status = 'Void'
        payment.save()

        # Payment is now Void, so recompute the bill from the remaining valid payments.
        recalc_billing_from_payments(payment.billing)

        ledger_entries = TenantLedger.objects.filter(payment=payment)
        tenant_to_recalc = payment.tenant
        for entry in ledger_entries:
            entry.delete()
        # Recompute chain for tenant to fix subsequent balances
        from core.helpers import recalc_tenant_ledger
        recalc_tenant_ledger(tenant_to_recalc)

        AuditLog.objects.create(
            user=request.user,
            action='VOID',
            module='Payment',
            description=f'Voided payment {payment.receipt_number} (was {old_status})',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        messages.success(request, f'Payment {payment.receipt_number} has been voided.')
    return redirect('payment_list')


@login_required
def payment_list_print(request):
    payments = Payment.objects.select_related('tenant', 'stall', 'collected_by').all().order_by('-payment_date', '-created_at')
    if get_user_role(request.user) == 'tenant':
        payments = payments.filter(tenant__user=request.user)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    tenant_filter = request.GET.get('tenant')
    stall_filter = request.GET.get('stall')
    collector_filter = request.GET.get('collector')
    status_filter = request.GET.get('status')
    payment_method = request.GET.get('payment_method')
    search_query = (request.GET.get('search') or '').strip()
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    if tenant_filter:
        payments = payments.filter(tenant_id=tenant_filter)
    if stall_filter:
        payments = payments.filter(stall_id=stall_filter)
    if collector_filter:
        payments = payments.filter(collected_by_id=collector_filter)
    if status_filter:
        payments = payments.filter(status=status_filter)
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    if search_query:
        payments = payments.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(receipt_number__icontains=search_query) |
            Q(official_receipt_no__icontains=search_query) |
            Q(collected_by__username__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'payments': payments,
        'date_from': date_from,
        'date_to': date_to,
        'tenant_filter': tenant_filter,
        'stall_filter': stall_filter,
        'collector_filter': collector_filter,
        'status_filter': status_filter,
        'payment_method': payment_method,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'payments/print_list.html', context)


@login_required
def payment_list_export_pdf(request):
    payments = Payment.objects.select_related('tenant', 'stall', 'collected_by').all().order_by('-payment_date', '-created_at')
    if get_user_role(request.user) == 'tenant':
        payments = payments.filter(tenant__user=request.user)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    tenant_filter = request.GET.get('tenant')
    stall_filter = request.GET.get('stall')
    collector_filter = request.GET.get('collector')
    status_filter = request.GET.get('status')
    payment_method = request.GET.get('payment_method')
    search_query = (request.GET.get('search') or '').strip()
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    if tenant_filter:
        payments = payments.filter(tenant_id=tenant_filter)
    if stall_filter:
        payments = payments.filter(stall_id=stall_filter)
    if collector_filter:
        payments = payments.filter(collected_by_id=collector_filter)
    if status_filter:
        payments = payments.filter(status=status_filter)
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    if search_query:
        payments = payments.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(receipt_number__icontains=search_query) |
            Q(official_receipt_no__icontains=search_query) |
            Q(collected_by__username__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'payments': payments,
        'date_from': date_from,
        'date_to': date_to,
        'status_filter': status_filter,
        'payment_method': payment_method,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"payments_list_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'payments/print_list.html', context, filename=filename)
