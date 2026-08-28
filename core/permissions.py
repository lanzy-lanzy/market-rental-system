from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

# Canonical role groups
ADMIN_ROLES = {'admin'}
STAFF_ROLES = {'admin', 'collector', 'cashier', 'supervisor', 'treasurer'}
COLLECTOR_ROLES = {'admin', 'collector', 'cashier'}
SUPERVISOR_ROLES = {'admin', 'supervisor', 'treasurer'}
ALL_ROLES = {'admin', 'collector', 'cashier', 'supervisor', 'treasurer', 'tenant'}

ROLE_LABELS = {
    'admin': 'Administrator',
    'collector': 'Market Collector',
    'cashier': 'Cashier',
    'supervisor': 'Market Supervisor',
    'treasurer': 'Treasurer',
    'tenant': 'Tenant',
}

def get_user_role(user):
    try:
        return user.profile.role
    except Exception:
        # Fallback for superuser without profile
        if user.is_superuser:
            return 'admin'
        return None

def is_admin(user):
    role = get_user_role(user)
    return role == 'admin' or user.is_superuser

def is_staff_role(user):
    role = get_user_role(user)
    return role in STAFF_ROLES

def role_required(allowed_roles):
    allowed = set(allowed_roles)
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            role = get_user_role(request.user)
            # Allow superuser regardless of profile
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if role not in allowed:
                messages.error(request, 'You do not have permission to access that page.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

# Convenience decorators
admin_required = role_required(ADMIN_ROLES)
staff_required = role_required(STAFF_ROLES)
collector_required = role_required(COLLECTOR_ROLES)
supervisor_required = role_required(SUPERVISOR_ROLES)

def tenant_isolation_queryset(request, queryset, tenant_field='tenant__user'):
    """
    If current user is tenant, restrict queryset to own tenant record only.
    Otherwise return queryset unfiltered.
    Usage: qs = Tenant.objects.all(); qs = tenant_isolation_queryset(request, Tenant.objects.filter(...), 'user')
    For Billing/Payment/TenantLedger: tenant_field='tenant__user'
    """
    role = get_user_role(request.user)
    if role == 'tenant':
        return queryset.filter(**{tenant_field: request.user})
    return queryset
