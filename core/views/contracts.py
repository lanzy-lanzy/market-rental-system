import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import IntegrityError, transaction
from datetime import date

from core.models import RentalContract, Tenant, Stall, Billing, AuditLog
from core.forms import RentalContractForm, BulkAssignStallsForm
from core.permissions import staff_required
from core.helpers import ensure_initial_billing, render_to_pdf_response
from django.contrib.auth.decorators import login_required


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


def activate_new_contracts(contracts):
    """Occupy every stall a submission covered and open its first billing.

    Returns how many contracts received a freshly generated billing.
    """
    billed = 0
    for contract in contracts:
        stall = contract.stall
        if stall.status != 'Occupied':
            stall.status = 'Occupied'
            stall.save(update_fields=['status'])
        try:
            _, created = ensure_initial_billing(contract)
            billed += 1 if created else 0
        except Exception:
            pass
    return billed


def describe_contracts(contracts):
    """(tenant name, stall numbers) for audit and flash messages."""
    first = contracts[0]
    return first.tenant.full_name, ', '.join(c.stall.stall_number for c in contracts)


@staff_required
def contract_list(request):
    contracts = RentalContract.objects.select_related(
        'tenant', 'stall', 'stall__section'
    ).all().order_by('-start_date', '-created_at', '-id')

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
            try:
                with transaction.atomic():
                    form.save()
                    contracts = form.saved_contracts
                    billing_count = activate_new_contracts(contracts)
            except IntegrityError:
                # Another user claimed one of these stalls after the form rendered.
                messages.error(request, 'One of the selected stalls was just taken. '
                                        'Please re-select and try again.')
                return render(request, 'contracts/form.html', {'form': form, 'is_add': True})
            tenant_name, stall_numbers = describe_contracts(contracts)
            if len(contracts) > 1:
                AuditLog.objects.create(
                    user=request.user,
                    action='BULK_ASSIGN',
                    module='RentalContract',
                    description=(
                        f'Created {len(contracts)} contracts for {tenant_name} '
                        f'on stalls: {stall_numbers}'
                    ),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'Created {len(contracts)} contracts for {tenant_name} '
                    f'on {stall_numbers}.')
            else:
                AuditLog.objects.create(
                    user=request.user,
                    action='CREATE',
                    module='RentalContract',
                    description=f'Created contract for {tenant_name} - {stall_numbers}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, 'Rental contract created successfully.')
            if billing_count:
                messages.info(request, f'Auto-generated billing for {billing_count} contract(s) ready for collection.')
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
    billings = Billing.objects.filter(contract=contract).order_by('-billing_year', '-billing_month', '-created_at', '-id')
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
            try:
                with transaction.atomic():
                    form.save()
                    contracts = form.saved_contracts
                    activate_new_contracts(contracts)
            except IntegrityError:
                messages.error(request, 'One of the selected stalls was just taken. '
                                        'Please re-select and try again.')
                if is_htmx(request):
                    return render(request, 'contracts/_modal_form.html',
                                  {'form': form, 'is_add': True})
                return render(request, 'contracts/form.html', {'form': form, 'is_add': True})
            tenant_name, stall_numbers = describe_contracts(contracts)
            AuditLog.objects.create(
                user=request.user,
                action='BULK_ASSIGN' if len(contracts) > 1 else 'CREATE',
                module='RentalContract',
                description=(
                    f'Created {len(contracts)} contracts for {tenant_name} '
                    f'on stalls: {stall_numbers} (modal)' if len(contracts) > 1
                    else f'Created contract for {tenant_name} - {stall_numbers} (modal)'
                ),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            toast = ('Contract created.' if len(contracts) == 1 else
                     f'Created {len(contracts)} contracts for {tenant_name} on {stall_numbers}.')
            # json.dumps keeps an apostrophe in a tenant name from ending the JS string.
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('<script>\n'
                                    'closeModal();\n'
                                    f'showToast({json.dumps(toast)}, "success");\n'
                                    'setTimeout(function() { location.reload(); }, 500);\n'
                                    '</script>')
            messages.success(request, toast)
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
    contracts = RentalContract.objects.select_related('tenant', 'stall', 'stall__section').all().order_by('-start_date', '-created_at', '-id')
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
    contracts = RentalContract.objects.select_related('tenant', 'stall', 'stall__section').all().order_by('-start_date', '-created_at', '-id')
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
    billings = Billing.objects.filter(contract=contract).order_by('-billing_year', '-billing_month', '-created_at', '-id')
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
    billings = Billing.objects.filter(contract=contract).order_by('-billing_year', '-billing_month', '-created_at', '-id')
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


@staff_required
def contract_bulk_assign(request):
    """Assign one Tenant to multiple Vacant Stalls in a single operation.

    Creates one Active RentalContract per selected stall. Each contract inherits
    the stall's monthly_rate. Stalls are atomically marked Occupied and initial
    billing is auto-generated for each.
    """
    if request.method == 'POST':
        form = BulkAssignStallsForm(request.POST)
        if form.is_valid():
            tenant = form.cleaned_data['tenant']
            stalls = form.cleaned_data['stalls']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data.get('end_date')
            due_day = form.cleaned_data['due_day']
            security_deposit = form.cleaned_data.get('security_deposit') or 0
            remarks = form.cleaned_data.get('remarks', '')

            created_contracts = []
            try:
                with transaction.atomic():
                    for stall in stalls:
                        # Lock the stall row to prevent concurrent assignment
                        locked_stall = Stall.objects.select_for_update().get(pk=stall.pk)
                        if locked_stall.status != 'Vacant':
                            raise ValueError(
                                f'Stall {locked_stall.stall_number} is no longer vacant.'
                            )
                        contract = RentalContract.objects.create(
                            tenant=tenant,
                            stall=locked_stall,
                            start_date=start_date,
                            end_date=end_date,
                            monthly_rent=locked_stall.monthly_rate,
                            due_day=due_day,
                            security_deposit=security_deposit,
                            status='Active',
                            remarks=remarks,
                        )
                        locked_stall.status = 'Occupied'
                        locked_stall.save(update_fields=['status'])
                        created_contracts.append(contract)

                # Auto-generate billing for each contract (outside the lock to
                # keep the critical section small)
                billing_count = 0
                for contract in created_contracts:
                    try:
                        _, created = ensure_initial_billing(contract)
                        if created:
                            billing_count += 1
                    except Exception:
                        pass

                stall_numbers = ', '.join(c.stall.stall_number for c in created_contracts)
                AuditLog.objects.create(
                    user=request.user,
                    action='BULK_ASSIGN',
                    module='RentalContract',
                    description=(
                        f'Bulk-assigned tenant {tenant.full_name} to '
                        f'{len(created_contracts)} stall(s): {stall_numbers}'
                    ),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'Successfully assigned {tenant.full_name} to '
                    f'{len(created_contracts)} stall(s): {stall_numbers}. '
                    f'{"Billing auto-generated." if billing_count else ""}'
                )
                return redirect('contract_list')

            except ValueError as e:
                messages.error(request, str(e))
                # Keep the bound form so the encoder's stall selection survives
                # the re-render; only the conflicting choice needs changing.
            except Exception as e:
                messages.error(request, f'Assignment failed: {e}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BulkAssignStallsForm()
        # Pre-select tenant if coming from a tenant profile page
        prefill_tenant_id = request.GET.get('tenant')
        if prefill_tenant_id:
            form.initial['tenant'] = prefill_tenant_id

    # Provide the assignable stall count for the info banner, matching the
    # queryset the form actually offers.
    vacant_count = (
        Stall.objects.filter(status='Vacant')
        .exclude(contracts__status='Active').count()
    )
    return render(request, 'contracts/bulk_assign.html', {
        'form': form,
        'vacant_count': vacant_count,
    })
