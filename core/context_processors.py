# core/context_processors.py

from .models import SystemSetting


def system_settings(request):
    settings = SystemSetting.objects.first()
    return {'system_settings': settings}
