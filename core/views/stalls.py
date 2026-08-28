from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import Stall, MarketSection, StallType, RentalContract, AuditLog
from core.forms import StallForm
from core.permissions import staff_required


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@login_required
def stall_list(request):
    stalls = Stall.objects.select_related('section', 'stall_type').all().order_by('stall_number')
    section_filter = request.GET.get('section')
    status_filter = request.GET.get('status')

    if section_filter:
        stalls = stalls.filter(section_id=section_filter)
    if status_filter:
        stalls = stalls.filter(status=status_filter)

    paginator = Paginator(stalls, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    sections = MarketSection.objects.all()
    context = {
        'page_obj': page_obj,
        'sections': sections,
        'section_filter': section_filter,
        'status_filter': status_filter,
    }

    if is_htmx(request):
        return render(request, 'stalls/_table.html', context)
    return render(request, 'stalls/list.html', context)


@staff_required
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


@staff_required
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


@staff_required
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


@login_required
def stall_view(request, pk):
    stall = get_object_or_404(Stall.objects.select_related('section', 'stall_type'), pk=pk)
    contracts = RentalContract.objects.filter(stall=stall).select_related('tenant').order_by('-start_date')
    context = {
        'stall': stall,
        'contracts': contracts,
    }
    return render(request, 'stalls/view.html', context)


@staff_required
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


@staff_required
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
