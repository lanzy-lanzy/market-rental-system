from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date

from core.models import Notice, Tenant, AuditLog
from core.forms import NoticeForm


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@login_required
def notice_list(request):
    notices = Notice.objects.select_related('tenant').all().order_by('-date_issued', '-created_at')

    type_filter = request.GET.get('type')
    tenant_filter = request.GET.get('tenant')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if type_filter:
        notices = notices.filter(notice_type=type_filter)
    if tenant_filter:
        notices = notices.filter(tenant_id=tenant_filter)
    if date_from:
        notices = notices.filter(date_issued__gte=date_from)
    if date_to:
        notices = notices.filter(date_issued__lte=date_to)

    paginator = Paginator(notices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'type_filter': type_filter,
        'tenant_filter': tenant_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    template = 'notices/_table.html' if is_htmx(request) else 'notices/list.html'
    return render(request, template, context)


@login_required
def notice_add(request):
    if request.method == 'POST':
        form = NoticeForm(request.POST)
        if form.is_valid():
            notice = form.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='Notice',
                description=f'Created notice {notice.notice_number} for {notice.tenant.full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'Notice {notice.notice_number} created successfully.')
            return redirect('notice_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = NoticeForm(initial={'date_issued': date.today()})
    return render(request, 'notices/form.html', {'form': form, 'is_add': True})


@login_required
def notice_print(request, pk):
    notice = get_object_or_404(Notice.objects.select_related('tenant'), pk=pk)
    context = {
        'notice': notice,
    }
    return render(request, 'notices/print.html', context)


@login_required
def notice_mark_served(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        notice.is_served = True
        notice.served_date = date.today()
        notice.save()
        AuditLog.objects.create(
            user=request.user,
            action='MARK_SERVED',
            module='Notice',
            description=f'Marked notice {notice.notice_number} as served',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Notice {notice.notice_number} marked as served.')
    return redirect('notice_list')
