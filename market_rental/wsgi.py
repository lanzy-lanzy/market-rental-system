"""
WSGI config for market_rental project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "market_rental.settings")

application = get_wsgi_application()

# Ensure default staff accounts and sample tenants exist on fresh Seenode deploys
# without resetting existing credentials or duplicating existing records.
from core.seed_on_deploy import ensure_seeded_on_deploy  # noqa: E402

ensure_seeded_on_deploy()
