"""Direct CRUD for the two lookups that power the Stall form dropdowns:
``MarketSection`` and ``StallType``.

Design notes
------------
*   Staff can view and manage both lists — this intentionally mirrors the
    ``staff_required`` gate on the stall views so a market clerk adding a
    new stall can also add a missing section in one trip.
*   Deleting a ``MarketSection`` is refused when any Stall still points at
    it, because ``Stall.section`` is a ``CASCADE`` FK and would silently
    destroy live stalls. ``StallType`` is ``SET_NULL`` so a delete is
    allowed but we warn the operator about the count of stalls that will
    lose their type.
*   The *quick-add* endpoints are the fragments the stall form uses to
    append a new option to an open dropdown without leaving the page.
    They return only the re-rendered ``<select>`` HTML so HTMX can swap
    it in place.
"""

from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.forms import MarketSectionForm, StallTypeForm
from core.models import AuditLog, MarketSection, Stall, StallType
from core.permissions import staff_required


# ─────────────────────────────── MarketSection ───────────────────────────────

@staff_required
def market_section_list(request):
    """Full-page manager: list existing sections + inline add/edit/delete."""
    from django.db.models import Count
    # Annotate each section with the number of stalls using it so the
    # template can disable Delete without extra queries.
    sections = (
        MarketSection.objects
        .annotate(stall_count=Count('stalls'))
        .order_by('name')
    )
    context = {
        'sections': sections,
        'add_form': MarketSectionForm(),
        'active_nav': 'market_section_list',
    }
    return render(request, 'stalls/sections.html', context)


@staff_required
@require_POST
def market_section_create(request):
    form = MarketSectionForm(request.POST)
    if form.is_valid():
        section = form.save()
        AuditLog.objects.create(
            user=request.user, action='CREATE', module='MarketSection',
            description=f'Created market section {section.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Section "{section.name}" added.')
        return redirect(request.POST.get('next') or 'market_section_list')
    messages.error(request, 'Please correct the errors in the section form.')
    return redirect(request.POST.get('next') or 'market_section_list')


@staff_required
@require_POST
def market_section_update(request, pk):
    section = get_object_or_404(MarketSection, pk=pk)
    form = MarketSectionForm(request.POST, instance=section)
    if form.is_valid():
        updated = form.save()
        AuditLog.objects.create(
            user=request.user, action='UPDATE', module='MarketSection',
            description=f'Renamed market section to {updated.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Section "{updated.name}" updated.')
    else:
        messages.error(request, 'Could not update the section. Check the name is unique.')
    return redirect(request.POST.get('next') or 'market_section_list')


@staff_required
@require_POST
def market_section_delete(request, pk):
    section = get_object_or_404(MarketSection, pk=pk)
    used_by = Stall.objects.filter(section=section).count()
    if used_by:
        messages.error(
            request,
            f'Cannot delete "{section.name}" — {used_by} stall(s) are still assigned '
            f'to it. Reassign them first.',
        )
        return redirect('market_section_list')
    name = section.name
    try:
        section.delete()
    except ProtectedError:
        messages.error(request, f'"{name}" is protected by other records and cannot be deleted.')
        return redirect('market_section_list')
    AuditLog.objects.create(
        user=request.user, action='DELETE', module='MarketSection',
        description=f'Deleted market section {name}',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    messages.success(request, f'Section "{name}" deleted.')
    return redirect('market_section_list')


@staff_required
@require_POST
def market_section_quick_add(request):
    """HTMX endpoint hit from the Stall form.

    Creates (or reuses) a MarketSection from a single ``name`` POST field
    and re-renders the ``section`` <select> with the new row pre-selected
    so the operator can keep filling the stall form without leaving it.
    Using ``get_or_create`` means duplicate names are collapsed rather
    than raising a validation error the operator would have to see.
    """
    name = (request.POST.get('name') or '').strip()
    section = None
    if name:
        section, created = MarketSection.objects.get_or_create(name=name)
        if created:
            AuditLog.objects.create(
                user=request.user, action='CREATE', module='MarketSection',
                description=f'Quick-created market section {section.name} from stall form',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
    response = render(request, 'stalls/_section_select.html', {
        'sections': MarketSection.objects.order_by('name'),
        'selected_id': section.pk if section else None,
    })
    response['HX-Trigger'] = 'sectionAdded'
    return response


# ──────────────────────────────── StallType ──────────────────────────────────

@staff_required
def stall_type_list(request):
    from django.db.models import Count
    types = (
        StallType.objects
        .annotate(stall_count=Count('stalls'))
        .order_by('name')
    )
    context = {
        'types': types,
        'add_form': StallTypeForm(),
        'active_nav': 'stall_type_list',
    }
    return render(request, 'stalls/stall_types.html', context)


@staff_required
@require_POST
def stall_type_create(request):
    form = StallTypeForm(request.POST)
    if form.is_valid():
        created = form.save()
        AuditLog.objects.create(
            user=request.user, action='CREATE', module='StallType',
            description=f'Created stall type {created.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Stall type "{created.name}" added.')
    else:
        messages.error(request, 'Please correct the errors in the stall type form.')
    return redirect(request.POST.get('next') or 'stall_type_list')


@staff_required
@require_POST
def stall_type_update(request, pk):
    obj = get_object_or_404(StallType, pk=pk)
    form = StallTypeForm(request.POST, instance=obj)
    if form.is_valid():
        updated = form.save()
        AuditLog.objects.create(
            user=request.user, action='UPDATE', module='StallType',
            description=f'Renamed stall type to {updated.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Stall type "{updated.name}" updated.')
    else:
        messages.error(request, 'Could not update the stall type. Check the name is unique.')
    return redirect(request.POST.get('next') or 'stall_type_list')


@staff_required
@require_POST
def stall_type_delete(request, pk):
    obj = get_object_or_404(StallType, pk=pk)
    affected = Stall.objects.filter(stall_type=obj).count()
    name = obj.name
    try:
        obj.delete()  # SET_NULL on Stall.stall_type — safe.
    except ProtectedError:
        messages.error(request, f'"{name}" is protected by other records and cannot be deleted.')
        return redirect('stall_type_list')
    AuditLog.objects.create(
        user=request.user, action='DELETE', module='StallType',
        description=f'Deleted stall type {name}',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    if affected:
        messages.warning(
            request,
            f'Stall type "{name}" deleted — {affected} stall(s) had their type cleared.',
        )
    else:
        messages.success(request, f'Stall type "{name}" deleted.')
    return redirect('stall_type_list')


@staff_required
@require_POST
def stall_type_quick_add(request):
    name = (request.POST.get('name') or '').strip()
    obj = None
    if name:
        obj, created = StallType.objects.get_or_create(name=name)
        if created:
            AuditLog.objects.create(
                user=request.user, action='CREATE', module='StallType',
                description=f'Quick-created stall type {obj.name} from stall form',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
    response = render(request, 'stalls/_stall_type_select.html', {
        'types': StallType.objects.order_by('name'),
        'selected_id': obj.pk if obj else None,
    })
    response['HX-Trigger'] = 'stallTypeAdded'
    return response
