# core/context_processors.py

from django.conf import settings

from .models import SystemSetting


def system_settings(request):
    settings = SystemSetting.objects.first()
    return {'system_settings': settings}


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
