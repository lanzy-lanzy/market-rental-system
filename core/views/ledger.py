from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Q

from core.models import Tenant, TenantLedger, AuditLog


@login_required
def ledger_list(request):
    tenants = Tenant.objects.filter(
        status='Active',
        contracts__status='Active'
    ).distinct().order_by('full_name')

    search = request.GET.get('search', '').strip()
    if search:
        tenants = tenants.filter(
            Q(full_name__icontains=search) |
            Q(tenant_id__icontains=search)
        )

    paginator = Paginator(tenants, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'ledger/list.html', context)


@login_required
def ledger_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    entries = TenantLedger.objects.filter(tenant=tenant).select_related(
        'billing', 'payment'
    ).order_by('transaction_date', 'created_at')

    paginator = Paginator(entries, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_debits = entries.aggregate(total=Sum('debit'))['total'] or 0
    total_credits = entries.aggregate(total=Sum('credit'))['total'] or 0
    running_balance = total_debits - total_credits

    if page_obj.has_previous():
        prev_entries = entries[:page_obj.start_index()]
        prev_balance = sum(
            (e.debit or 0) - (e.credit or 0) for e in prev_entries
        )
    else:
        prev_balance = 0

    context = {
        'tenant': tenant,
        'page_obj': page_obj,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'running_balance': running_balance,
        'prev_balance': prev_balance,
    }
    return render(request, 'ledger/view.html', context)


@login_required
def ledger_print(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    entries = TenantLedger.objects.filter(tenant=tenant).select_related(
        'billing', 'payment'
    ).order_by('transaction_date', 'created_at')

    total_debits = entries.aggregate(total=Sum('debit'))['total'] or 0
    total_credits = entries.aggregate(total=Sum('credit'))['total'] or 0
    running_balance = total_debits - total_credits

    context = {
        'tenant': tenant,
        'entries': entries,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'running_balance': running_balance,
    }
    return render(request, 'ledger/print.html', context)
