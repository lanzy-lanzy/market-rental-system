from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.permissions import staff_required, admin_required, get_user_role
from django.core.paginator import Paginator
from django.db.models import Sum, Q

from core.models import Tenant, TenantLedger, AuditLog, SystemSetting
from core.helpers import render_to_pdf_response


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@login_required
def ledger_list(request):
    role = get_user_role(request.user)
    if role == 'tenant':
        try:
            own_tenant = Tenant.objects.get(user=request.user)
            return redirect('ledger_view', pk=own_tenant.pk)
        except Tenant.DoesNotExist:
            messages.info(request, 'Your tenant profile is not linked. Contact administrator.')
            return redirect('dashboard')
    tenants = Tenant.objects.filter(
        status='Active',
        contracts__status='Active'
    ).distinct().order_by('-id')

    search = request.GET.get('search', '').strip()
    if search:
        tenants = tenants.filter(
            Q(full_name__icontains=search) |
            Q(tenant_id__icontains=search)
        )

    paginator = Paginator(tenants, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'search': search,
        'pagination_target': 'ledger-table-wrapper',
    }
    if is_htmx(request):
        return render(request, 'ledger/_table.html', context)
    return render(request, 'ledger/list.html', context)


@login_required
def ledger_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only view your own ledger.')
        return redirect('ledger_list')
    entries = TenantLedger.objects.filter(tenant=tenant).select_related(
        'billing', 'payment'
    ).order_by('-transaction_date', '-created_at', '-id')

    paginator = Paginator(entries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_debits = entries.aggregate(total=Sum('debit'))['total'] or 0
    total_credits = entries.aggregate(total=Sum('credit'))['total'] or 0
    running_balance = total_debits - total_credits

    # For descending order, running balance prev calc not needed for top display; keep simple
    prev_balance = 0

    context = {
        'tenant': tenant,
        'page_obj': page_obj,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'running_balance': running_balance,
        'prev_balance': prev_balance,
        'pagination_target': 'ledger-entries-wrapper',
    }
    return render(request, 'ledger/view.html', context)


@login_required
def ledger_print(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only print your own ledger.')
        return redirect('ledger_list')
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
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
    }
    return render(request, 'ledger/print.html', context)


@login_required
def ledger_view_export_pdf(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only print your own ledger.')
        return redirect('ledger_list')
    entries = TenantLedger.objects.filter(tenant=tenant).select_related('billing', 'payment').order_by('transaction_date', 'created_at')
    total_debits = entries.aggregate(total=Sum('debit'))['total'] or 0
    total_credits = entries.aggregate(total=Sum('credit'))['total'] or 0
    running_balance = total_debits - total_credits
    context = {
        'tenant': tenant,
        'entries': entries,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'running_balance': running_balance,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
    }
    filename = f"ledger_{tenant.tenant_id}_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'ledger/print.html', context, filename=filename)


@login_required
def ledger_list_print(request):
    role = get_user_role(request.user)
    if role == 'tenant':
        try:
            own_tenant = Tenant.objects.get(user=request.user)
            return redirect('ledger_view', pk=own_tenant.pk)
        except Tenant.DoesNotExist:
            messages.info(request, 'Your tenant profile is not linked. Contact administrator.')
            return redirect('dashboard')
    tenants = Tenant.objects.filter(status='Active', contracts__status='Active').distinct().order_by('-id')
    search = request.GET.get('search', '').strip()
    if search:
        tenants = tenants.filter(Q(full_name__icontains=search) | Q(tenant_id__icontains=search))
    context = {
        'tenants': tenants,
        'search': search,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'ledger/print_list.html', context)


@login_required
def ledger_list_export_pdf(request):
    role = get_user_role(request.user)
    if role == 'tenant':
        try:
            own_tenant = Tenant.objects.get(user=request.user)
            return redirect('ledger_view', pk=own_tenant.pk)
        except Tenant.DoesNotExist:
            messages.info(request, 'Your tenant profile is not linked. Contact administrator.')
            return redirect('dashboard')
    tenants = Tenant.objects.filter(status='Active', contracts__status='Active').distinct().order_by('-id')
    search = request.GET.get('search', '').strip()
    if search:
        tenants = tenants.filter(Q(full_name__icontains=search) | Q(tenant_id__icontains=search))
    context = {
        'tenants': tenants,
        'search': search,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"ledger_tenants_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'ledger/print_list.html', context, filename=filename)
