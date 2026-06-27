from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
    prefix = settings.receipt_prefix if settings else 'RCP'
    today = date.today()
    last_payment = Payment.objects.filter(
        receipt_number__startswith=f'{prefix}-'
    ).order_by('-created_at').first()
    if last_payment:
        last_num = int(last_payment.receipt_number.split('-')[-1])
        new_num = last_num + 1
    else:
        new_num = 1
    return f'{prefix}-{today.strftime("%Y%m")}-{new_num:06d}'


@login_required
def payment_list(request):
    payments = Payment.objects.select_related(
        'tenant', 'stall', 'collected_by'
    ).all().order_by('-payment_date', '-created_at')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    tenant_filter = request.GET.get('tenant')
    stall_filter = request.GET.get('stall')
    collector_filter = request.GET.get('collector')
    status_filter = request.GET.get('status')

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
    }
    template = 'payments/_table.html' if is_htmx(request) else 'payments/list.html'
    return render(request, template, context)


@login_required
@transaction.atomic
def payment_add(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.receipt_number = generate_receipt_number()
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

            ledger_entries = TenantLedger.objects.filter(
                billing=billing
            ).order_by('-transaction_date')
            current_balance = ledger_entries.first().balance if ledger_entries.exists() else billing.total_due
            new_balance = current_balance - payment.amount_paid

            TenantLedger.objects.create(
                tenant=payment.tenant,
                billing=billing,
                transaction_date=payment.payment_date,
                description=f'Payment {payment.receipt_number} - {payment.payment_method}',
                debit=0,
                credit=payment.amount_paid,
                balance=new_balance,
                payment=payment,
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
    settings = SystemSetting.objects.first()
    context = {
        'payment': payment,
        'settings': settings,
    }
    return render(request, 'payments/print_receipt.html', context)


@login_required
def payment_add_modal(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.receipt_number = generate_receipt_number()
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

            ledger_entries = TenantLedger.objects.filter(billing=billing).order_by('-transaction_date')
            current_balance = ledger_entries.first().balance if ledger_entries.exists() else billing.total_due
            new_balance = current_balance - payment.amount_paid

            TenantLedger.objects.create(
                tenant=payment.tenant,
                billing=billing,
                transaction_date=payment.payment_date,
                description=f'Payment {payment.receipt_number} - {payment.payment_method}',
                debit=0,
                credit=payment.amount_paid,
                balance=new_balance,
                payment=payment,
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


@login_required
def payment_edit_modal(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
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


@login_required
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
        for entry in ledger_entries:
            entry.delete()

        AuditLog.objects.create(
            user=request.user,
            action='VOID',
            module='Payment',
            description=f'Voided payment {payment.receipt_number} (was {old_status})',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        messages.success(request, f'Payment {payment.receipt_number} has been voided.')
    return redirect('payment_list')
