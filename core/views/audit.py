from datetime import date

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import AuditLog
from core.permissions import admin_required


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@admin_required
def audit_log_list(request):
    base_logs = AuditLog.objects.all()
    available_years = sorted(
        {dt.year for dt in base_logs.dates('created_at', 'year', order='DESC')},
        reverse=True,
    )
    if not available_years:
        available_years = [date.today().year]

    logs = base_logs.select_related('user').order_by('-created_at', '-id')

    user_filter = request.GET.get('user')
    action_filter = request.GET.get('action')
    module_filter = request.GET.get('module')
    raw_year = (request.GET.get('year') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search_query = (request.GET.get('search') or request.GET.get('q') or '').strip()

    year_filter = ''
    if raw_year:
        try:
            year_int = int(raw_year)
            year_filter = str(year_int)
            logs = logs.filter(created_at__year=year_int)
            if year_int not in available_years:
                available_years = sorted(set(available_years) | {year_int}, reverse=True)
        except (ValueError, TypeError):
            year_filter = ''

    if user_filter:
        logs = logs.filter(user_id=user_filter)
    if action_filter:
        logs = logs.filter(action__icontains=action_filter)
    if module_filter:
        logs = logs.filter(module__icontains=module_filter)
    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)
    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)
    if search_query:
        logs = logs.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(action__icontains=search_query) |
            Q(module__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(ip_address__icontains=search_query)
        )

    paginator = Paginator(logs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'available_years': available_years,
        'user_filter': user_filter,
        'action_filter': action_filter,
        'module_filter': module_filter,
        'year_filter': year_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'pagination_target': 'audit-table-wrapper',
    }
    template = 'audit/_table.html' if is_htmx(request) else 'audit/list.html'
    return render(request, template, context)
