# core/context_processors.py

from django.conf import settings

from .models import SystemSetting
from .permissions import MANAGEMENT_ROLES, get_user_role


def system_settings(request):
    settings = SystemSetting.objects.first()
    return {'system_settings': settings}


def user_roles(request):
    """Expose the current role so templates can hide out-of-scope navigation.

    ``is_collector`` drives the restricted collector menu (collection queue,
    own payment history and receipts only) while ``can_manage_records`` keeps
    the administrative entries visible for admin/cashier/supervisor/treasurer.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'user_role': None, 'is_collector': False, 'can_manage_records': False}
    role = get_user_role(user)
    return {
        'user_role': role,
        'is_collector': role == 'collector' and not user.is_superuser,
        'can_manage_records': role in MANAGEMENT_ROLES or user.is_superuser,
    }


def static_version(request):
    """Cache-busting version for built static assets.

    Returns the mtime of ``static/css/output.css`` so templates can render
    e.g. ``output.css?v=<mtime>``. Every rebuild of the Tailwind CSS changes
    the URL, forcing browsers to fetch the fresh file instead of serving a
    stale cached copy (which previously required a hard refresh).
    """
    try:
        mtime = int((settings.BASE_DIR / "static" / "css" / "output.css").stat().st_mtime)
    except OSError:
        mtime = ""
    return {"STATIC_VERSION": mtime}
