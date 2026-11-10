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


# ── Sidebar "Stalls" group ────────────────────────────────────────────────
# Maps every stall-related URL name to the sidebar sub-link that should be
# highlighted. Matching on substrings of the URL name is not reliable here:
# ``market_section_list`` does not contain "stall" (so the group used to stay
# collapsed and un-highlighted), while ``stall_type_list`` does (so the
# "List" entry lit up while the operator was on Stall Types). An explicit map
# keeps the group open on every stall screen and lights up exactly one entry.
STALL_NAV_TABS = {
    'stall_list': 'list',
    'stall_view': 'list',
    'stall_edit': 'list',
    'stall_delete': 'list',
    'stall_list_print': 'list',
    'stall_list_export_pdf': 'list',
    'stall_view_print': 'list',
    'stall_view_export_pdf': 'list',
    'stall_edit_modal': 'list',
    'stall_add': 'add',
    'stall_add_modal': 'add',
    'market_section_list': 'sections',
    'market_section_create': 'sections',
    'market_section_update': 'sections',
    'market_section_delete': 'sections',
    'market_section_quick_add': 'sections',
    'stall_type_list': 'types',
    'stall_type_create': 'types',
    'stall_type_update': 'types',
    'stall_type_delete': 'types',
    'stall_type_quick_add': 'types',
}


def stall_navigation(request):
    """Expose which Stalls sub-link the current page belongs to.

    ``stall_nav_tab`` is one of ``list`` / ``add`` / ``sections`` / ``types``
    or ``None`` for pages outside the Stalls group. The sidebar uses it for
    both the group's open state and the single active sub-link.
    """
    match = getattr(request, 'resolver_match', None)
    url_name = match.url_name if match else None
    return {'stall_nav_tab': STALL_NAV_TABS.get(url_name)}


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
