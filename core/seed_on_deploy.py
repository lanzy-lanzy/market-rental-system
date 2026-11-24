"""Safe, idempotent auto-seeding hook for Seenode / cloud deployments.

When an ephemeral container redeploys with a fresh SQLite database, this helper
ensures default staff accounts (admin, collector) and at least 3 realistic
tenants with contracts, billings, payments, and ledgers are populated once.

Existing admin and collector credentials are NEVER reset, and existing tenant
data is NEVER erased or duplicated.
"""

import logging
import os
import sys

from django.db import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

_SEED_CHECKED = False

SKIP_COMMANDS = {
    "test",
    "makemigrations",
    "collectstatic",
    "check",
    "shell",
    "dbshell",
    "flush",
    "dumpdata",
    "loaddata",
    "seed_users",
    "seed_data",
    "showmigrations",
    "sqlmigrate",
    "createsuperuser",
    "changepassword",
}


def should_auto_seed(argv=None):
    """Return True when automatic deploy seeding should run in this process."""
    enabled = os.environ.get("AUTO_SEED_ON_DEPLOY", "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return False

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False

    args = list(sys.argv if argv is None else argv)
    if args:
        prog = os.path.basename(args[0]).lower()
        if "pytest" in prog:
            return False
        if any(arg in SKIP_COMMANDS for arg in args[1:3]):
            return False
    return True


def ensure_seeded_on_deploy(*, force_check=False, argv=None):
    """Idempotently seed users and demo tenants when the database is empty.

    Safe to call from ``post_migrate`` and WSGI startup:
    - Executes at most once per process (unless ``force_check=True``).
    - Skips during tests and non-serving management commands.
    - Never resets existing admin/collector passwords.
    - Never overwrites or duplicates data when >= 3 tenants already exist.
    """
    global _SEED_CHECKED
    if _SEED_CHECKED and not force_check:
        return False

    if not should_auto_seed(argv=argv):
        return False

    from django.contrib.auth.models import User
    from django.core.management import call_command

    from core.models import RentalContract, Tenant

    try:
        needs_users = not (
            User.objects.filter(username="admin").exists()
            and User.objects.filter(username="collector").exists()
        )
        needs_data = Tenant.objects.count() < 3 or not RentalContract.objects.exists()
    except (OperationalError, ProgrammingError):
        # Migrations have not created tables yet; skip silently.
        return False

    _SEED_CHECKED = True

    if not needs_users and not needs_data:
        return False

    seeded = False
    try:
        if needs_users:
            call_command("seed_users", verbosity=0)
            seeded = True
        if needs_data:
            call_command("seed_data", verbosity=0)
            seeded = True
    except (OperationalError, ProgrammingError) as exc:
        logger.warning("Auto-seed skipped due to database state: %s", exc)
        return False
    except Exception:
        logger.exception("Auto-seed on deploy failed")
        return False

    if seeded:
        logger.info(
            "Auto-seed on deploy completed: %s tenants, %s contracts.",
            Tenant.objects.count(),
            RentalContract.objects.count(),
        )
    return seeded
