from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import (
    AuditLog, Billing, MarketSection, RentalContract, Stall, StallType, SystemSetting,
)
from core.forms import StallForm
from core.permissions import management_required
from core.helpers import render_to_pdf_response


STALL_STATUS_LOOKUP = {value.lower(): value for value, _ in Stall.STATUS_CHOICES}
CONTRACT_STATUS_LOOKUP = {value.lower(): value for value, _ in RentalContract.STATUS_CHOICES}


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


def _normalize_stall_status(raw_status):
    raw = (raw_status or '').strip()
    if not raw:
        return ''
    return STALL_STATUS_LOOKUP.get(raw.lower(), raw)


def _normalize_contract_status(raw_status):
    raw = (raw_status or '').strip()
    if not raw:
        return ''
    return CONTRACT_STATUS_LOOKUP.get(raw.lower(), raw)


def _filter_stalls(request):
    active_contracts_prefetch = Prefetch(
        'contracts',
        queryset=RentalContract.objects.filter(status='Active').select_related('tenant'),
        to_attr='active_contracts',
    )
    base_qs = (
        Stall.objects.select_related('section', 'stall_type')
        .prefetch_related(active_contracts_prefetch)
        .order_by('-created_at', '-id')
    )

    section_filter = (request.GET.get('section') or '').strip()
    status_filter = _normalize_stall_status(request.GET.get('status'))
    search_query = (request.GET.get('search') or request.GET.get('q') or '').strip()

    selected_section = None
    if section_filter:
        if section_filter.isdigit():
            base_qs = base_qs.filter(section_id=int(section_filter))
            selected_section = MarketSection.objects.filter(pk=int(section_filter)).first()
        else:
            base_qs = base_qs.none()

    if search_query:
        base_qs = base_qs.filter(
            Q(stall_number__icontains=search_query) |
            Q(section__name__icontains=search_query) |
            Q(stall_type__name__icontains=search_query) |
            Q(remarks__icontains=search_query)
        )

    status_counts_qs = base_qs.order_by().values('status').annotate(total=Count('id'))
    status_counts = {row['status']: row['total'] for row in status_counts_qs}
    all_count = sum(status_counts.values())

    stalls = base_qs
    if status_filter:
        stalls = stalls.filter(status=status_filter)

    filter_params = {}
    if search_query:
        filter_params['search'] = search_query
    if section_filter:
        filter_params['section'] = section_filter
    if status_filter:
        filter_params['status'] = status_filter
    filter_querystring = urlencode(filter_params)

    return {
        'stalls': stalls,
        'section_filter': section_filter,
        'selected_section': selected_section,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': Stall.STATUS_CHOICES,
        'status_counts': {
            'all': all_count,
            'Vacant': status_counts.get('Vacant', 0),
            'Occupied': status_counts.get('Occupied', 0),
            'Reserved': status_counts.get('Reserved', 0),
            'Maintenance': status_counts.get('Maintenance', 0),
        },
        'filter_querystring': filter_querystring,
    }


def _build_stall_rental_history(stall, request):
    zero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))

    years_set = set()
    for start_dt, end_dt in RentalContract.objects.filter(stall=stall).values_list('start_date', 'end_date'):
        if start_dt:
            years_set.add(start_dt.year)
        if end_dt:
            years_set.add(end_dt.year)
    for b_year in Billing.objects.filter(stall=stall).values_list('billing_year', flat=True).distinct():
        if b_year:
            years_set.add(b_year)
    available_years = sorted(years_set, reverse=True)

    current_contract = (
        RentalContract.objects.filter(stall=stall, status='Active')
        .select_related('tenant')
        .order_by('-start_date', '-id')
        .first()
    )
    if current_contract:
        current_contract.contract_number = f"CTR-{current_contract.id:05d}"

    raw_year = (request.GET.get('year') or '').strip()
    history_year_filter = ''
    history_year_int = None
    if raw_year.isdigit():
        history_year_int = int(raw_year)
        history_year_filter = str(history_year_int)

    history_status_filter = _normalize_contract_status(request.GET.get('status'))

    matching_qs = RentalContract.objects.filter(stall=stall)
    if history_status_filter:
        matching_qs = matching_qs.filter(status=history_status_filter)
    if history_year_int is not None:
        matching_qs = matching_qs.filter(
            Q(start_date__year=history_year_int)
            | Q(end_date__year=history_year_int)
            | (
                Q(start_date__year__lte=history_year_int)
                & (Q(end_date__isnull=True) | Q(end_date__year__gte=history_year_int))
            )
            | Q(billings__billing_year=history_year_int)
        ).distinct()

    matching_ids = list(matching_qs.values_list('id', flat=True))

    contracts = list(
        RentalContract.objects.filter(id__in=matching_ids)
        .select_related('tenant')
        .annotate(
            total_billed=Coalesce(Sum('billings__total_due'), zero),
            total_paid=Coalesce(Sum('billings__amount_paid'), zero),
            total_balance=Coalesce(Sum('billings__balance'), zero),
            billing_count=Count('billings', distinct=True),
        )
        .order_by('-start_date', '-created_at', '-id')
    )
    for contract in contracts:
        contract.contract_number = f"CTR-{contract.id:05d}"

    total_billed = sum((c.total_billed for c in contracts), Decimal('0.00'))
    total_paid = sum((c.total_paid for c in contracts), Decimal('0.00'))
    total_balance = sum((c.total_balance for c in contracts), Decimal('0.00'))
    unique_tenant_count = len({c.tenant_id for c in contracts})
    total_all_contracts = RentalContract.objects.filter(stall=stall).count()

    history_params = {}
    if history_year_filter:
        history_params['year'] = history_year_filter
    if history_status_filter:
        history_params['status'] = history_status_filter
    history_querystring = urlencode(history_params)

    return {
        'contracts': contracts,
        'current_contract': current_contract,
        'total_all_contracts': total_all_contracts,
        'history_summary': {
            'contract_count': len(contracts),
            'unique_tenants': unique_tenant_count,
            'total_billed': total_billed,
            'total_paid': total_paid,
            'total_balance': total_balance,
        },
        'history_year_filter': history_year_filter,
        'history_status_filter': history_status_filter,
        'available_years': available_years,
        'contract_status_choices': RentalContract.STATUS_CHOICES,
        'history_querystring': history_querystring,
    }


@management_required
def stall_list(request):
    filtered = _filter_stalls(request)
    paginator = Paginator(filtered['stalls'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    sections = MarketSection.objects.all()
    context = {
        'page_obj': page_obj,
        'sections': sections,
        'section_filter': filtered['section_filter'],
        'selected_section': filtered['selected_section'],
        'status_filter': filtered['status_filter'],
        'search_query': filtered['search_query'],
        'status_choices': filtered['status_choices'],
        'status_counts': filtered['status_counts'],
        'filter_querystring': filtered['filter_querystring'],
        'pagination_target': 'stall-table-wrapper',
        'is_htmx_request': bool(is_htmx(request)),
    }

    if is_htmx(request):
        return render(request, 'stalls/_table.html', context)
    return render(request, 'stalls/list.html', context)


@management_required
def stall_add(request):
    if request.method == 'POST':
        form = StallForm(request.POST)
        if form.is_valid():
            stall = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Stall',
                description=f'Created stall {stall.stall_number}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'Stall {stall.stall_number} created successfully.')
            return redirect('stall_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StallForm()
    return render(request, 'stalls/form.html', {'form': form, 'is_add': True})


@management_required
def stall_edit(request, pk):
    stall = get_object_or_404(Stall, pk=pk)
    if request.method == 'POST':
        form = StallForm(request.POST, instance=stall)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='Stall',
                description=f'Updated stall {stall.stall_number}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'Stall {stall.stall_number} updated successfully.')
            return redirect('stall_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StallForm(instance=stall)
    return render(request, 'stalls/form.html', {'form': form, 'is_add': False, 'stall': stall})


@management_required
def stall_delete(request, pk):
    stall = get_object_or_404(Stall, pk=pk)
    if request.method == 'POST':
        stall_number = stall.stall_number
        stall.delete()
        AuditLog.objects.create(
            user=request.user,
            action='DELETE',
            module='Stall',
            description=f'Deleted stall {stall_number}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Stall {stall_number} deleted successfully.')
    return redirect('stall_list')


@management_required
def stall_view(request, pk):
    stall = get_object_or_404(Stall.objects.select_related('section', 'stall_type'), pk=pk)
    history = _build_stall_rental_history(stall, request)
    context = {
        'stall': stall,
        **history,
        'is_htmx_request': bool(is_htmx(request)),
    }
    if is_htmx(request):
        return render(request, 'stalls/_rental_history.html', context)
    return render(request, 'stalls/view.html', context)


@management_required
def stall_add_modal(request):
    if request.method == 'POST':
        form = StallForm(request.POST)
        if form.is_valid():
            stall = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Stall',
                description=f'Created stall {stall.stall_number} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Stall created.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Stall created.')
            return redirect('stall_list')
        if is_htmx(request):
            return render(request, 'stalls/_modal_form.html', {'form': form, 'is_add': True})
    else:
        form = StallForm()
    return render(request, 'stalls/_modal_form.html', {'form': form, 'is_add': True})


@management_required
def stall_edit_modal(request, pk):
    stall = get_object_or_404(Stall, pk=pk)
    if request.method == 'POST':
        form = StallForm(request.POST, instance=stall)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='Stall',
                description=f'Updated stall {stall.stall_number} (modal)',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            if is_htmx(request):
                from django.http import HttpResponse
                return HttpResponse('''<script>
                    closeModal();
                    showToast('Stall updated.', 'success');
                    setTimeout(function() { location.reload(); }, 500);
                </script>''')
            messages.success(request, 'Stall updated.')
            return redirect('stall_list')
        if is_htmx(request):
            return render(request, 'stalls/_modal_form.html', {'form': form, 'is_add': False, 'stall': stall})
    else:
        form = StallForm(instance=stall)
    return render(request, 'stalls/_modal_form.html', {'form': form, 'is_add': False, 'stall': stall})


@management_required
def stall_list_print(request):
    filtered = _filter_stalls(request)
    context = {
        'stalls': filtered['stalls'],
        'section_filter': filtered['section_filter'],
        'selected_section': filtered['selected_section'],
        'status_filter': filtered['status_filter'],
        'search_query': filtered['search_query'],
        'status_counts': filtered['status_counts'],
        'filter_querystring': filtered['filter_querystring'],
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': timezone.now(),
    }
    return render(request, 'stalls/print_list.html', context)


@management_required
def stall_list_export_pdf(request):
    filtered = _filter_stalls(request)
    context = {
        'stalls': filtered['stalls'],
        'section_filter': filtered['section_filter'],
        'selected_section': filtered['selected_section'],
        'status_filter': filtered['status_filter'],
        'search_query': filtered['search_query'],
        'status_counts': filtered['status_counts'],
        'filter_querystring': filtered['filter_querystring'],
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': timezone.now(),
    }
    filename = f"stalls_list_{date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'stalls/print_list.html', context, filename=filename)


@login_required
def stall_view_print(request, pk):
    stall = get_object_or_404(Stall.objects.select_related('section', 'stall_type'), pk=pk)
    history = _build_stall_rental_history(stall, request)
    context = {
        'stall': stall,
        **history,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': timezone.now(),
    }
    return render(request, 'stalls/print_view.html', context)


@login_required
def stall_view_export_pdf(request, pk):
    stall = get_object_or_404(Stall.objects.select_related('section', 'stall_type'), pk=pk)
    history = _build_stall_rental_history(stall, request)
    context = {
        'stall': stall,
        **history,
        'system_settings': SystemSetting.objects.first(),
        'user': request.user,
        'now': timezone.now(),
    }
    filename = f"stall_{stall.stall_number}_{date.today().isoformat()}.pdf"
    return render_to_pdf_response(request, 'stalls/print_view.html', context, filename=filename)
