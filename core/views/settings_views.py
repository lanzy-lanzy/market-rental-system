from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from core.models import SystemSetting, AuditLog
from core.forms import SystemSettingForm


def is_admin(user):
    return hasattr(user, 'profile') and user.profile.role == 'admin'


@login_required
def settings_view(request):
    settings = SystemSetting.objects.first()
    if request.method == 'POST':
        if not is_admin(request.user):
            messages.error(request, 'You do not have permission to update settings.')
            return redirect('settings_view')
        form = SystemSettingForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='SystemSettings',
                description='Updated system settings',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, 'System settings updated successfully.')
            return redirect('settings_view')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SystemSettingForm(instance=settings)
    context = {
        'form': form,
        'settings': settings,
    }
    return render(request, 'settings/view.html', context)


@login_required
def settings_update(request):
    if not is_admin(request.user):
        messages.error(request, 'You do not have permission to update settings.')
        return redirect('settings_view')
    if request.method == 'POST':
        settings = SystemSetting.objects.first()
        if not settings:
            settings = SystemSetting()
        form = SystemSettingForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='SystemSettings',
                description='Updated system settings via update endpoint',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, 'Settings updated.')
        else:
            messages.error(request, 'Please correct the errors below.')
    return redirect('settings_view')
