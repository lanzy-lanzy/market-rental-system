from django.shortcuts import render
from django.core.paginator import Paginator

from core.models import AuditLog
from core.permissions import admin_required


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@admin_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user').all().order_by('-created_at')

    user_filter = request.GET.get('user')
    action_filter = request.GET.get('action')
    module_filter = request.GET.get('module')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

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

    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'user_filter': user_filter,
        'action_filter': action_filter,
        'module_filter': module_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    template = 'audit/_table.html' if is_htmx(request) else 'audit/list.html'
    return render(request, template, context)
