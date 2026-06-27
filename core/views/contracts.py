from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date

from core.models import RentalContract, Tenant, Stall, Billing, AuditLog
from core.forms import RentalContractForm


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@login_required
def contract_list(request):
    contracts = RentalContract.objects.select_related(
        'tenant', 'stall', 'stall__section'
    ).all().order_by('-start_date')

    status_filter = request.GET.get('status')
    tenant_filter = request.GET.get('tenant')
    stall_filter = request.GET.get('stall')

    if status_filter:
        contracts = contracts.filter(status=status_filter)
    if tenant_filter:
        contracts = contracts.filter(tenant_id=tenant_filter)
    if stall_filter:
        contracts = contracts.filter(stall_id=stall_filter)

    paginator = Paginator(contracts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'tenant_filter': tenant_filter,
        'stall_filter': stall_filter,
    }
    if is_htmx(request):
        return render(request, 'contracts/_table.html', context)
    return render(request, 'contracts/list.html', context)


@login_required
def contract_add(request):
    if request.method == 'POST':
        form = RentalContractForm(request.POST)
        if form.is_valid():
            contract = form.save()
            contract.stall.status = 'Occupied'
            contract.stall.save()
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


@login_required
def contract_edit(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)
    if request.method == 'POST':
        form = RentalContractForm(request.POST, instance=contract)
        if form.is_valid():
            contract = form.save()
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


@login_required
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


@login_required
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


@login_required
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


@login_required
def contract_add_modal(request):
    if request.method == 'POST':
        form = RentalContractForm(request.POST)
        if form.is_valid():
            contract = form.save()
            contract.stall.status = 'Occupied'
            contract.stall.save()
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


@login_required
def contract_edit_modal(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)
    if request.method == 'POST':
        form = RentalContractForm(request.POST, instance=contract)
        if form.is_valid():
            form.save()
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
