from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.db import transaction, connections, router
from django.contrib.auth.models import User as AuthUser

from core.models import Tenant, Stall, RentalContract, Billing, Payment, AuditLog
from core.forms import TenantForm
from core.permissions import staff_required, admin_required, get_user_role, is_admin
from django.contrib.auth.decorators import login_required
from core.helpers import render_to_pdf_response, create_tenant_login


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
        'can_bulk_delete': is_admin(request.user),
    }
    if is_htmx(request):
        return render(request, 'tenants/_table.html', context)
    return render(request, 'tenants/list.html', context)


@staff_required
def tenant_add(request):
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES)
        if form.is_valid():
            tenant = form.save()
            # Auto-provision the tenant login with a secure username + temp password.
            user, password = create_tenant_login(tenant)

            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Tenant',
                description=f'Created tenant {tenant.tenant_id} - {tenant.full_name} (login {user.username})',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

            # Render the credentials on a dedicated page so the admin can copy/share them.
            return render(request, 'tenants/credentials.html', {
                'tenant': tenant,
                'generated_username': user.username,
                'generated_password': password,
            })
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TenantForm()
    return render(request, 'tenants/form.html', {'form': form, 'is_add': True})


@staff_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, instance=tenant)
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


@admin_required
@transaction.atomic
def tenant_bulk_delete(request):
    """Hard-delete multiple tenants in a single action.

    Design notes
    ------------
    * Row-level ``select_for_update()`` is only issued when the active
      backend advertises ``features.has_select_for_update``. SQLite (the
      default dev DB here, and Django's feature flag is ``False``) raises
      ``NotSupportedError`` on that call, which previously made every bulk
      POST return a 500 while leaving tenants untouched. SQLite already
      serialises writes at the DB level inside a transaction, so no extra
      lock is required there.
    * Tenants are genuinely removed via ``Model.delete()`` — their linked
      contracts, billings, ledger entries and notices cascade away through
      the ``on_delete=CASCADE`` foreign keys defined on the models. The
      portal ``User`` account (and therefore the ``UserProfile``) is
      deleted as well so the login disappears.
    * Any tenant with real financial history — at least one ``Payment``
      row, OR any ``Billing`` with ``amount_paid > 0`` — is refused with a
      per-tenant warning rather than being silently wiped, because those
      records feed the collection ledger, receipts and reports.
    * Only POST is honoured; success, block and error outcomes all land
      back on ``tenant_list`` with a ``messages`` summary.
    """
    if request.method != 'POST':
        return redirect('tenant_list')

    raw_ids = request.POST.getlist('selected_tenants')
    pk_list = []
    for raw in raw_ids:
        try:
            pk_list.append(int(raw))
        except (TypeError, ValueError):
            continue
    # De-duplicate while preserving the collector's selection order so the
    # confirmation messages list names in the sequence the admin ticked.
    seen = set()
    ordered_pk_list = []
    for pk in pk_list:
        if pk in seen:
            continue
        seen.add(pk)
        ordered_pk_list.append(pk)
    pk_list = ordered_pk_list

    if not pk_list:
        messages.warning(request, 'No tenants were selected for deletion.')
        return redirect('tenant_list')

    alias = router.db_for_write(Tenant)
    supports_lock = connections[alias].features.has_select_for_update
    base_qs = Tenant.objects.using(alias)
    tenants = list(
        base_qs.select_for_update().filter(pk__in=pk_list)
        if supports_lock else base_qs.filter(pk__in=pk_list)
    )
    if not tenants:
        messages.error(
            request,
            'The selected tenants could not be found. Please refresh and try again.',
        )
        return redirect('tenant_list')

    # Preload history flags so a bulk action runs in a fixed number of
    # queries rather than N round-trips per tenant.
    tenant_ids = [t.pk for t in tenants]
    ids_with_payments = set(
        Payment.objects.filter(tenant_id__in=tenant_ids)
        .values_list('tenant_id', flat=True)
    )
    ids_with_paid_billings = set(
        Billing.objects.filter(tenant_id__in=tenant_ids, amount_paid__gt=0)
        .values_list('tenant_id', flat=True)
    )

    deleted_names = []
    blocked_names = []
    missing_ids = set(pk_list) - {t.pk for t in tenants}

    for tenant in tenants:
        if (
            tenant.pk in ids_with_payments
            or tenant.pk in ids_with_paid_billings
        ):
            blocked_names.append(f'{tenant.full_name} ({tenant.tenant_id})')
            continue
        user_pk = tenant.user_id
        # ``delete()`` cascades to contracts/billings/payments/ledger/notices
        # via on_delete=CASCADE. Only the Tenant row itself is emitted here.
        tenant.delete(using=alias)
        if user_pk:
            # Drop the linked portal login. This also cascades the UserProfile
            # (OneToOne with on_delete=CASCADE), so nothing is orphaned.
            AuthUser.objects.using(alias).filter(pk=user_pk).delete()
        deleted_names.append(f'{tenant.full_name} ({tenant.tenant_id})')

    # Single audit row summarising the whole batch keeps the log readable.
    summary_parts = []
    if deleted_names:
        summary_parts.append(f'deleted {len(deleted_names)}: ' + ', '.join(deleted_names))
    if blocked_names:
        summary_parts.append(f'blocked {len(blocked_names)}: ' + ', '.join(blocked_names))
    if summary_parts:
        AuditLog.objects.using(alias).create(
            user=request.user,
            action='DELETE',
            module='Tenant',
            description='Bulk delete — ' + '; '.join(summary_parts),
            ip_address=request.META.get('REMOTE_ADDR'),
        )

    # User-facing feedback — mirror the three possible outcomes so the admin
    # always sees what actually changed.
    if deleted_names:
        messages.success(
            request,
            f'Deleted {len(deleted_names)} tenant(s): ' + ', '.join(deleted_names) + '.',
        )
    if blocked_names:
        messages.warning(
            request,
            f'{len(blocked_names)} tenant(s) were NOT deleted because they have '
            'payment history (recorded receipts or partially paid billings): '
            + ', '.join(blocked_names)
            + '. Use Terminate instead, or void the payments first.',
        )
    if missing_ids:
        messages.warning(
            request,
            f'{len(missing_ids)} selected record(s) no longer exist and were skipped.',
        )
    if not deleted_names and not blocked_names and not missing_ids:
        messages.error(request, 'Bulk delete failed — nothing was removed.')

    return redirect('tenant_list')


@login_required
def tenant_view(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    # Tenant isolation: tenants can only view own profile
    role = get_user_role(request.user)
    if role == 'tenant' and tenant.user != request.user:
        messages.error(request, 'You can only view your own tenant profile.')
        return redirect('dashboard')
    contracts = RentalContract.objects.filter(tenant=tenant).select_related('stall', 'stall__section').order_by('-start_date', '-created_at', '-id')
    billings = Billing.objects.filter(tenant=tenant).order_by('-billing_year', '-billing_month', '-created_at', '-id')
    payments = Payment.objects.filter(tenant=tenant).order_by('-payment_date', '-created_at', '-id')[:10]

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
        form = TenantForm(request.POST, request.FILES)
        if form.is_valid():
            tenant = form.save()
            # Auto-provision the tenant login (fixes prior gap where no user was made).
            user, password = create_tenant_login(tenant)
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Tenant',
                description=f'Created tenant {tenant.tenant_id} - {tenant.full_name} (login {user.username}, modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            ctx = {
                'tenant': tenant,
                'generated_username': user.username,
                'generated_password': password,
            }
            if is_htmx(request):
                # Swap the modal body with the generated credentials.
                return render(request, 'tenants/_credentials_fragment.html', ctx)
            return render(request, 'tenants/credentials.html', ctx)
        if is_htmx(request):
            return render(request, 'tenants/_modal_form.html', {'form': form, 'is_add': True})
    else:
        form = TenantForm()
    return render(request, 'tenants/_modal_form.html', {'form': form, 'is_add': True})


@staff_required
def tenant_edit_modal(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, instance=tenant)
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
    contracts = RentalContract.objects.filter(tenant=tenant).select_related('stall', 'stall__section').order_by('-start_date', '-created_at', '-id')
    billings = Billing.objects.filter(tenant=tenant).order_by('-billing_year', '-billing_month', '-created_at', '-id')
    payments = Payment.objects.filter(tenant=tenant).order_by('-payment_date', '-created_at', '-id')[:10]
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
    contracts = RentalContract.objects.filter(tenant=tenant).select_related('stall', 'stall__section').order_by('-start_date', '-created_at', '-id')
    billings = Billing.objects.filter(tenant=tenant).order_by('-billing_year', '-billing_month', '-created_at', '-id')
    payments = Payment.objects.filter(tenant=tenant).order_by('-payment_date', '-created_at', '-id')[:10]
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
