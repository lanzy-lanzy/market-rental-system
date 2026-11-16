import base64
import mimetypes

from django import template
from django.contrib.staticfiles import finders

register = template.Library()


@register.simple_tag(takes_context=True)
def document_logo_src(context):
    """Embed letterhead images so browser print and offline PDF engines agree."""
    settings = context.get('system_settings') or context.get('settings')
    logo = getattr(settings, 'logo', None)
    if logo:
        try:
            with logo.open('rb') as image:
                data = image.read()
            mime = mimetypes.guess_type(logo.name)[0] or 'image/png'
            return f'data:{mime};base64,{base64.b64encode(data).decode("ascii")}'
        except (OSError, ValueError):
            pass
    path = finders.find('images/lgu_dumingag_logo.png')
    if path:
        with open(path, 'rb') as image:
            return 'data:image/png;base64,' + base64.b64encode(image.read()).decode('ascii')
    return ''
