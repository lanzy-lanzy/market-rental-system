from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q

from core.models import UserProfile, AuditLog
from core.forms import UserCreationForm, UserProfileForm
from core.permissions import admin_required


def is_htmx(request):
    return getattr(request, 'htmx', None) or request.headers.get('HX-Request') == 'true'


@admin_required
def user_list(request):

    users = User.objects.select_related('profile').all().order_by('username')
    role_filter = request.GET.get('role')
    search_query = request.GET.get('search')

    if role_filter:
        users = users.filter(profile__role=role_filter)
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'role_filter': role_filter,
        'search_query': search_query,
    }
    template = 'users/_table.html' if is_htmx(request) else 'users/list.html'
    return render(request, template, context)


@admin_required
def user_add(request):

    if request.method == 'POST':
        user_form = UserCreationForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save(commit=False)
            password = request.POST.get('password')
            if password:
                user.set_password(password)
            user.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            AuditLog.objects.create(
                user=request.user,
                action='CREATE',
                module='User',
                description=f'Created user {user.username} with role {profile.get_role_display()}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'User {user.username} created successfully.')
            return redirect('user_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserCreationForm()
        profile_form = UserProfileForm()
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'is_add': True,
    }
    return render(request, 'users/form.html', context)


@admin_required
def user_edit(request, pk):

    user = get_object_or_404(User, pk=pk)
    profile = get_object_or_404(UserProfile, user=user)

    if request.method == 'POST':
        user_form = UserCreationForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            password = request.POST.get('password')
            if password:
                user.set_password(password)
                user.save()
            profile_form.save()
            AuditLog.objects.create(
                user=request.user,
                action='UPDATE',
                module='User',
                description=f'Updated user {user.username}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            messages.success(request, f'User {user.username} updated successfully.')
            return redirect('user_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserCreationForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'is_add': False,
        'edit_user': user,
    }
    return render(request, 'users/form.html', context)


@admin_required
def user_deactivate(request, pk):

    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        status = 'deactivated' if not user.is_active else 'activated'
        AuditLog.objects.create(
            user=request.user,
            action='DEACTIVATE' if not user.is_active else 'ACTIVATE',
            module='User',
            description=f'{status.title()} user {user.username}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'User {user.username} has been {status}.')
    return redirect('user_list')
