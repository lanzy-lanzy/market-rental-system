from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse

from core.models import Tenant, Stall, RentalContract, Billing, Payment, AuditLog, UserProfile
from core.forms import TenantForm
from core.permissions import staff_required, admin_required, get_user_role
from django.contrib.auth.decorators import login_required
from core.helpers import render_to_pdf_response


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@staff_required
def tenant_list(request):
    tenants = Tenant.objects.all().order_by('-created_at', '-id')
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')

    if status_filter:
        tenants = tenants.filter(status=status_filter)
    if search_query:
        tenants = tenants.filter(
            Q(full_name__icontains=search_query) |
            Q(tenant_id__icontains=search_query) |
            Q(business_name__icontains=search_query)
        )

    paginator = Paginator(tenants, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'pagination_target': 'tenant-table-wrapper',
    }
    if is_htmx(request):
        return render(request, 'tenants/_table.html', context)
    return render(request, 'tenants/list.html', context)


@staff_required
def tenant_add(request):
    if request.method == 'POST':
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            username = f"TENANT{tenant.tenant_id}"
            import secrets
            import string
            password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
            user = User.objects.create_user(
                username=username,
                email=tenant.email,
                password=password,
                first_name=tenant.full_name.split()[0] if tenant.full_name.split() else '',
                last_name=' '.join(tenant.full_name.split()[1:]) if len(tenant.full_name.split()) > 1 else '',
            )
            UserProfile.objects.create(user=user, role='tenant')
            tenant.user = user
            tenant.save()

            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Tenant',
                description=f'Created tenant {tenant.tenant_id} - {tenant.full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            messages.success(request, f'Tenant {tenant.full_name} created successfully. Username: {username}, Password: {password}')
            return redirect('tenant_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TenantForm()
    return render(request, 'tenants/form.html', {'form': form, 'is_add': True})


@staff_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='Tenant',
                description=f'Updated tenant {tenant.tenant_id} - {tenant.full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'Tenant {tenant.full_name} updated successfully.')
            return redirect('tenant_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TenantForm(instance=tenant)
    return render(request, 'tenants/form.html', {'form': form, 'is_add': False, 'tenant': tenant})


@admin_required
def tenant_delete(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        tenant.status = 'Terminated'
        tenant.save()
        if tenant.user:
            tenant.user.is_active = False
            tenant.user.save()
        AuditLog.objects.create(
            user=request.user,
            action='TERMINATE',
            module='Tenant',
            description=f'Terminated tenant {tenant.tenant_id} - {tenant.full_name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Tenant {tenant.full_name} has been terminated.')
    return redirect('tenant_list')


@login_required
def tenant_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    # Tenant isolation: tenants can only view own profile
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only view your own tenant profile.')
        return redirect('dashboard')
    contracts = RentalContract.objects.filter(tenant=tenant).select_related('stall', 'stall__section')
    billings = Billing.objects.filter(tenant=tenant).order_by('-billing_year', '-billing_month')
    payments = Payment.objects.filter(tenant=tenant).order_by('-payment_date')[:10]

    total_balance = billings.aggregate(total=Sum('balance'))['total'] or 0

    context = {
        'tenant': tenant,
        'contracts': contracts,
        'billings': billings,
        'payments': payments,
        'total_balance': total_balance,
    }
    return render(request, 'tenants/view.html', context)


@staff_required
def tenant_search(request):
    q = request.GET.get('q', '')
    tenants = Tenant.objects.filter(
        Q(full_name__icontains=q) |
        Q(tenant_id__icontains=q) |
        Q(business_name__icontains=q),
        status='Active'
    )[:20]
    if is_htmx(request):
        return render(request, 'tenants/_search_results.html', {'tenants': tenants})
    data = [{'id': t.id, 'tenant_id': t.tenant_id, 'full_name': t.full_name, 'business_name': t.business_name} for t in tenants]
    return JsonResponse(data, safe=False)


@staff_required
def tenant_add_modal(request):
    if request.method == 'POST':
        form = TenantForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Tenant',
                description=f'Created tenant {tenant.tenant_id} - {tenant.full_name} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Tenant created.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, f'Tenant created.')
            return redirect('tenant_list')
        if is_htmx(request):
            return render(request, 'tenants/_modal_form.html', {'form': form, 'is_add': True})
    else:
        form = TenantForm()
    return render(request, 'tenants/_modal_form.html', {'form': form, 'is_add': True})


@staff_required
def tenant_edit_modal(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='Tenant',
                description=f'Updated tenant {tenant.tenant_id} - {tenant.full_name} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Tenant updated.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, f'Tenant updated.')
            return redirect('tenant_list')
        if is_htmx(request):
            return render(request, 'tenants/_modal_form.html', {'form': form, 'is_add': False, 'tenant': tenant})
    else:
        form = TenantForm(instance=tenant)
    return render(request, 'tenants/_modal_form.html', {'form': form, 'is_add': False, 'tenant': tenant})


@staff_required
def tenant_list_print(request):
    """Print preview for tenants — respects same search/status filters as list, shows all matching records."""
    tenants = Tenant.objects.all().order_by('-created_at', '-id')
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')
    if status_filter:
        tenants = tenants.filter(status=status_filter)
    if search_query:
        tenants = tenants.filter(
            Q(full_name__icontains=search_query) |
            Q(tenant_id__icontains=search_query) |
            Q(business_name__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'tenants': tenants,
        'status_filter': status_filter,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'tenants/print_list.html', context)


@staff_required
def tenant_list_export_pdf(request):
    """Export tenants list as PDF — same filtered queryset as print preview."""
    tenants = Tenant.objects.all().order_by('-created_at', '-id')
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')
    if status_filter:
        tenants = tenants.filter(status=status_filter)
    if search_query:
        tenants = tenants.filter(
            Q(full_name__icontains=search_query) |
            Q(tenant_id__icontains=search_query) |
            Q(business_name__icontains=search_query)
        )
    from core.models import SystemSetting
    context = {
        'tenants': tenants,
        'status_filter': status_filter,
        'search_query': search_query,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"tenants_list_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'tenants/print_list.html', context, filename=filename)


@staff_required
def tenant_view_print(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only view your own tenant profile.')
        return redirect('dashboard')
    contracts = RentalContract.objects.filter(tenant=tenant).select_related('stall', 'stall__section')
    billings = Billing.objects.filter(tenant=tenant).order_by('-billing_year', '-billing_month')
    payments = Payment.objects.filter(tenant=tenant).order_by('-payment_date')[:10]
    total_balance = billings.aggregate(total=Sum('balance'))['total'] or 0
    from core.models import SystemSetting
    context = {
        'tenant': tenant,
        'contracts': contracts,
        'billings': billings,
        'payments': payments,
        'total_balance': total_balance,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    return render(request, 'tenants/print_view.html', context)


@staff_required
def tenant_view_export_pdf(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only view your own tenant profile.')
        return redirect('dashboard')
    contracts = RentalContract.objects.filter(tenant=tenant).select_related('stall', 'stall__section')
    billings = Billing.objects.filter(tenant=tenant).order_by('-billing_year', '-billing_month')
    payments = Payment.objects.filter(tenant=tenant).order_by('-payment_date')[:10]
    total_balance = billings.aggregate(total=Sum('balance'))['total'] or 0
    from core.models import SystemSetting
    context = {
        'tenant': tenant,
        'contracts': contracts,
        'billings': billings,
        'payments': payments,
        'total_balance': total_balance,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': __import__('django.utils.timezone', fromlist=['now']).now(),
    }
    filename = f"tenant_{tenant.tenant_id}_{__import__('datetime').date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'tenants/print_view.html', context, filename=filename)
