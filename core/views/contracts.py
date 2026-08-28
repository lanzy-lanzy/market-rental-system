from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date

from core.models import RentalContract, Tenant, Stall, Billing, AuditLog
from core.forms import RentalContractForm
from core.permissions import staff_required
from core.helpers import ensure_initial_billing, render_to_pdf_response
from django.contrib.auth.decorators import login_required


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@staff_required
def contract_list(request):
    contracts = RentalContract.objects.select_related(
        'tenant', 'stall', 'stall__section'
    ).all().order_by('-created_at', '-id')

    status_filter = request.GET.get('status')
    tenant_filter = request.GET.get('tenant')
    stall_filter = request.GET.get('stall')
    search_query = (request.GET.get('search') or request.GET.get('q') or '').strip()

    if status_filter:
        contracts = contracts.filter(status=status_filter)
    if tenant_filter:
        contracts = contracts.filter(tenant_id=tenant_filter)
    if stall_filter:
        contracts = contracts.filter(stall_id=stall_filter)
    if search_query:
        contracts = contracts.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(tenant__business_name__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(stall__section__name__icontains=search_query)
        )

    paginator = Paginator(contracts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'tenant_filter': tenant_filter,
        'stall_filter': stall_filter,
        'search_query': search_query,
        'pagination_target': 'contract-table-wrapper',
    }
    if is_htmx(request):
        return render(request, 'contracts/_table.html', context)
    return render(request, 'contracts/list.html', context)


@staff_required
def contract_add(request):
    if request.method == 'POST':
        form = RentalContractForm(request.POST)
        if form.is_valid():
            contract = form.save()
            contract.stall.status = 'Occupied'
            contract.stall.save()
            # Auto-generate billing(s) for this contract so collector sees amount immediately
            try:
                billing, created = ensure_initial_billing(contract)
                if created:
                    messages.info(request, f'Auto-generated billing for {billing.billing_month:02d}/{billing.billing_year} (₱{billing.total_due}) ready for collection.')
            except Exception:
                pass
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='RentalContract',
                description=f'Created contract for {contract.tenant.full_name} - {contract.stall.stall_number}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, 'Rental contract created successfully.')
            return redirect('contract_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RentalContractForm()
    return render(request, 'contracts/form.html', {'form': form, 'is_add': True})


@staff_required
def contract_edit(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)
    old_stall = contract.stall
    old_status = contract.status
    if request.method == 'POST':
        form = RentalContractForm(request.POST, instance=contract)
        if form.is_valid():
            contract = form.save()
            # Sync stall statuses on edit: handle stall change and status change
            new_stall = contract.stall
            if old_stall and old_stall.pk != new_stall.pk:
                # Old stall may become vacant if no other active contract
                has_other = RentalContract.objects.filter(stall=old_stall, status='Active').exclude(pk=contract.pk).exists()
                if not has_other:
                    old_stall.status = 'Vacant'
                    old_stall.save()
            # New stall status based on contract status
            if contract.status == 'Active':
                if new_stall.status != 'Occupied':
                    new_stall.status = 'Occupied'
                    new_stall.save()
                try:
                    ensure_initial_billing(contract)
                except Exception:
                    pass
            else:
                # If contract no longer active, check if new stall should be vacant
                has_other_new = RentalContract.objects.filter(stall=new_stall, status='Active').exclude(pk=contract.pk).exists()
                if not has_other_new and new_stall.status == 'Occupied':
                    new_stall.status = 'Vacant'
                    new_stall.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='RentalContract',
                description=f'Updated contract for {contract.tenant.full_name} - {contract.stall.stall_number}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, 'Rental contract updated successfully.')
            return redirect('contract_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RentalContractForm(instance=contract)
    return render(request, 'contracts/form.html', {'form': form, 'is_add': False, 'contract': contract})


@staff_required
def contract_delete(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)
    if request.method == 'POST':
        stall = contract.stall
        tenant_name = contract.tenant.full_name
        stall_number = contract.stall.stall_number
        contract.delete()
        has_other_active = RentalContract.objects.filter(
            stall=stall, status='Active'
        ).exclude(pk=contract.pk).exists()
        if not has_other_active:
            stall.status = 'Vacant'
            stall.save()
        AuditLog.objects.create(
            user=request.user,
            action='DELETE',
            module='RentalContract',
            description=f'Deleted contract for {tenant_name} - {stall_number}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, 'Rental contract deleted.')
    return redirect('contract_list')


@staff_required
def contract_view(request, pk):
    contract = get_object_or_404(
        RentalContract.objects.select_related('tenant', 'stall', 'stall__section'),
        pk=pk
    )
    billings = Billing.objects.filter(contract=contract).order_by('-billing_year', '-billing_month')
    context = {
        'contract': contract,
        'billings': billings,
    }
    return render(request, 'contracts/view.html', context)


@staff_required
def contract_terminate(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)
    if request.method == 'POST':
        contract.status = 'Terminated'
        contract.end_date = date.today()
        contract.save()
        has_other_active = RentalContract.objects.filter(
            stall=contract.stall, status='Active'
        ).exclude(pk=contract.pk).exists()
        if not has_other_active:
            contract.stall.status = 'Vacant'
            contract.stall.save()
        AuditLog.objects.create(
            user=request.user,
            action='TERMINATE',
            module='RentalContract',
            description=f'Terminated contract for {contract.tenant.full_name} - {contract.stall.stall_number}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, 'Contract terminated successfully.')
    return redirect('contract_list')


@staff_required
def contract_add_modal(request):
    if request.method == 'POST':
        form = RentalContractForm(request.POST)
        if form.is_valid():
            contract = form.save()
            contract.stall.status = 'Occupied'
            contract.stall.save()
            try:
                ensure_initial_billing(contract)
            except Exception:
                pass
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='RentalContract',
                description=f'Created contract for {contract.tenant.full_name} - {contract.stall.stall_number} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Contract created.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Contract created.')
            return redirect('contract_list')
        if is_htmx(request):
            return render(request, 'contracts/_modal_form.html', {'form': form, 'is_add': True})
    else:
        form = RentalContractForm()
    return render(request, 'contracts/_modal_form.html', {'form': form, 'is_add': True})


@staff_required
def contract_edit_modal(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)
    old_stall = contract.stall
    if request.method == 'POST':
        form = RentalContractForm(request.POST, instance=contract)
        if form.is_valid():
            contract = form.save()
            new_stall = contract.stall
            if old_stall and old_stall.pk != new_stall.pk:
                has_other = RentalContract.objects.filter(stall=old_stall, status='Active').exclude(pk=contract.pk).exists()
                if not has_other:
                    old_stall.status = 'Vacant'
                    old_stall.save()
            if contract.status == 'Active':
                if new_stall.status != 'Occupied':
                    new_stall.status = 'Occupied'
                    new_stall.save()
                try:
                    ensure_initial_billing(contract)
                except Exception:
                    pass
            else:
                has_other_new = RentalContract.objects.filter(stall=new_stall, status='Active').exclude(pk=contract.pk).exists()
                if not has_other_new and new_stall.status == 'Occupied':
                    new_stall.status = 'Vacant'
                    new_stall.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='RentalContract',
                description=f'Updated contract for {contract.tenant.full_name} - {contract.stall.stall_number} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Contract updated.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Contract updated.')
            return redirect('contract_list')
        if is_htmx(request):
            return render(request, 'contracts/_modal_form.html', {'form': form, 'is_add': False, 'contract': contract})
    else:
        form = RentalContractForm(instance=contract)
    return render(request, 'contracts/_modal_form.html', {'form': form, 'is_add': False, 'contract': contract})


@staff_required
def contract_list_print(request):
    contracts = RentalContract.objects.select_related('tenant', 'stall', 'stall__section').all().order_by('-created_at', '-id')
    status_filter = request.GET.get('status')
    search_query = (request.GET.get('search') or '').strip()
    if status_filter:
        contracts = contracts.filter(status=status_filter)
    if search_query:
        contracts = contracts.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(stall__section__name__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'contracts': contracts,
        'status_filter': status_filter,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'contracts/print_list.html', context)


@staff_required
def contract_list_export_pdf(request):
    contracts = RentalContract.objects.select_related('tenant', 'stall', 'stall__section').all().order_by('-created_at', '-id')
    status_filter = request.GET.get('status')
    search_query = (request.GET.get('search') or '').strip()
    if status_filter:
        contracts = contracts.filter(status=status_filter)
    if search_query:
        contracts = contracts.filter(
            Q(tenant__full_name__icontains=search_query) |
            Q(tenant__tenant_id__icontains=search_query) |
            Q(stall__stall_number__icontains=search_query) |
            Q(stall__section__name__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'contracts': contracts,
        'status_filter': status_filter,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"contracts_list_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'contracts/print_list.html', context, filename=filename)


@staff_required
def contract_view_print(request, pk):
    contract = get_object_or_404(RentalContract.objects.select_related('tenant', 'stall', 'stall__section'), pk=pk)
    billings = Billing.objects.filter(contract=contract).order_by('-billing_year', '-billing_month')
    from core.models import SystemSetting
    context = {
        'contract': contract,
        'billings': billings,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'contracts/print_view.html', context)


@staff_required
def contract_view_export_pdf(request, pk):
    contract = get_object_or_404(RentalContract.objects.select_related('tenant', 'stall', 'stall__section'), pk=pk)
    billings = Billing.objects.filter(contract=contract).order_by('-billing_year', '-billing_month')
    from core.models import SystemSetting
    context = {
        'contract': contract,
        'billings': billings,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"contract_{contract.id}_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'contracts/print_view.html', context, filename=filename)
