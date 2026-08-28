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


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


def generate_receipt_number():
    settings = SystemSetting.objects.first()
    prefix = (settings.receipt_prefix if settings else 'RCP').strip().rstrip('-')
    if not prefix:
        prefix = 'RCP'
    today = date.today()
    last_payment = Payment.objects.filter(
        receipt_number__startswith=f'{prefix}-'
    ).order_by('-created_at').first()
    if last_payment:
        try:
            last_num = int(last_payment.receipt_number.split('-')[-1])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1
    return f'{prefix}-{today.strftime("%Y%m")}-{new_num:06d}'


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

    paginator = Paginator(payments, 20)
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
    }
    template = 'payments/_table.html' if is_htmx(request) else 'payments/list.html'
    return render(request, template, context)


@staff_required
@transaction.atomic
def payment_add(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.receipt_number = generate_receipt_number()
            # Auto-fill official receipt if blank (spec requires OR)
            if not payment.official_receipt_no:
                payment.official_receipt_no = payment.receipt_number
            payment.collected_by = request.user
            payment.save()

            billing = payment.billing
            total_paid_so_far = Payment.objects.filter(
                billing=billing, status__in=['Paid', 'Partial']
            ).exclude(pk=payment.pk).aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            total_paid_so_far += payment.amount_paid

            if total_paid_so_far >= billing.total_due:
                billing.amount_paid = total_paid_so_far
                billing.balance = 0
                billing.status = 'Paid'
            elif total_paid_so_far > 0:
                billing.amount_paid = total_paid_so_far
                billing.balance = billing.total_due - total_paid_so_far
                billing.status = 'Partial'
            billing.save()

            # Ledger: create credit entry then recompute chain for tenant
            # Use tenant-wide last balance for correct chaining
            last_tenant_entry = TenantLedger.objects.filter(tenant=payment.tenant).order_by('-transaction_date', '-id').first()
            current_balance = last_tenant_entry.balance if last_tenant_entry else 0
            # If no prior tenant entry but billing has debit, use that debit as baseline (billing total)
            if not last_tenant_entry:
                billing_debit_entry = TenantLedger.objects.filter(billing=billing, debit__gt=0).first()
                if billing_debit_entry:
                    current_balance = billing_debit_entry.balance

            TenantLedger.objects.create(
                tenant=payment.tenant,
                billing=billing,
                transaction_date=payment.payment_date,
                description=f'Payment {payment.receipt_number} - {payment.payment_method}',
                debit=0,
                credit=payment.amount_paid,
                balance=max(0, current_balance - float(payment.amount_paid)),
                payment=payment,
            )
            # Recompute full ledger chain to ensure consistency
            from core.helpers import recalc_tenant_ledger
            recalc_tenant_ledger(payment.tenant)

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


@staff_required
def payment_add_modal(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.receipt_number = generate_receipt_number()
            if not payment.official_receipt_no:
                payment.official_receipt_no = payment.receipt_number
            payment.collected_by = request.user
            payment.save()

            billing = payment.billing
            total_paid_so_far = Payment.objects.filter(
                billing=billing, status__in=['Paid', 'Partial']
            ).exclude(pk=payment.pk).aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            total_paid_so_far += payment.amount_paid

            if total_paid_so_far >= billing.total_due:
                billing.amount_paid = total_paid_so_far
                billing.balance = 0
                billing.status = 'Paid'
            elif total_paid_so_far > 0:
                billing.amount_paid = total_paid_so_far
                billing.balance = billing.total_due - total_paid_so_far
                billing.status = 'Partial'
            billing.save()

            last_tenant_entry = TenantLedger.objects.filter(tenant=payment.tenant).order_by('-transaction_date', '-id').first()
            current_balance = last_tenant_entry.balance if last_tenant_entry else 0
            if not last_tenant_entry:
                billing_debit_entry = TenantLedger.objects.filter(billing=billing, debit__gt=0).first()
                if billing_debit_entry:
                    current_balance = billing_debit_entry.balance
            TenantLedger.objects.create(
                tenant=payment.tenant,
                billing=billing,
                transaction_date=payment.payment_date,
                description=f'Payment {payment.receipt_number} - {payment.payment_method}',
                debit=0,
                credit=payment.amount_paid,
                balance=max(0, current_balance - float(payment.amount_paid)),
                payment=payment,
            )
            from core.helpers import recalc_tenant_ledger
            recalc_tenant_ledger(payment.tenant)

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
def payment_edit_modal(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    old_billing = payment.billing
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            payment = form.save()
            # Recalculate billing totals after amount/method change
            billing = payment.billing
            total_valid = Payment.objects.filter(billing=billing, status__in=['Paid', 'Partial']).aggregate(total=Sum('amount_paid'))['total'] or 0
            if total_valid >= billing.total_due:
                billing.amount_paid = total_valid
                billing.balance = 0
                billing.status = 'Paid'
            elif total_valid > 0:
                billing.amount_paid = total_valid
                billing.balance = billing.total_due - total_valid
                billing.status = 'Partial'
            else:
                billing.amount_paid = 0
                billing.balance = billing.total_due
                billing.status = 'Unpaid'
            billing.save()
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

        billing = payment.billing
        valid_payments = Payment.objects.filter(
            billing=billing, status__in=['Paid', 'Partial']
        ).exclude(pk=payment.pk)
        total_valid = valid_payments.aggregate(total=Sum('amount_paid'))['total'] or 0

        if total_valid == 0:
            billing.amount_paid = 0
            billing.balance = billing.total_due
            billing.status = 'Unpaid'
        elif total_valid >= billing.total_due:
            billing.amount_paid = total_valid
            billing.balance = 0
            billing.status = 'Paid'
        else:
            billing.amount_paid = total_valid
            billing.balance = billing.total_due - total_valid
            billing.status = 'Partial'
        billing.save()

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
