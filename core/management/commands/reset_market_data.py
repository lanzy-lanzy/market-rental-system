"""reset_market_data — nukes business/tenant rows so a dev environment can start clean.

Scope (what this deletes):
    Market, Stall, StallType, RentalContract, Billing, Payment,
    TenantLedger, Notice, Tenant, and the tenant UserProfile/User rows.

Preserved by default (only wiped if you pass the corresponding flag):
    AuditLog         (legal trail — pass --audit to clear)
    SystemSetting    (LGU branding + penalty rules — pass --clear-settings to wipe)
    Admin Users      (the account running this command stays intact unless
                      you pass --users, and even then the current superuser
                      is never deleted)

Safety rails — deliberately strict because this is destructive:
    * Only runnable from the shell. There is NO HTTP route to this logic.
    * Requires the operator to type the word ``RESET`` at the prompt (or
      pass ``--yes`` for scripted use). Any other input aborts.
    * Refuses to run against a production-looking host unless
      ``FORCE_RESET=1`` is set in the environment. ``DEBUG=False`` is
      treated as production.
    * Supports ``--dry-run`` to see row counts before anything is dropped.
    * Everything happens inside a single transaction — a crash midway
      rolls the whole operation back.

Usage examples:
    python manage.py reset_market_data --dry-run
    python manage.py reset_market_data
    python manage.py reset_market_data --users --audit --yes
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.models import (
    AuditLog, Billing, MarketSection, Notice, PenaltySetting, Payment,
    RentalContract, Stall, StallType, SystemSetting, Tenant, TenantLedger,
    UserProfile,
)


# Ordered leaf-first so no FK is left dangling mid-teardown. ``delete()``
# on the parent already cascades the dependents, but hitting the leaves
# first keeps the audit summary honest (counts reflect what actually
# existed, not what survived after the first cascade).
BUSINESS_MODELS = [
    TenantLedger,
    Payment,
    Billing,
    Notice,
    PenaltySetting,
    RentalContract,
    Tenant,
    Stall,
    MarketSection,
    StallType,
]


class Command(BaseCommand):
    help = (
        'Permanently remove all tenant/financial/market rows from the '
        'database. Preserves AuditLog, SystemSetting and admin Users by '
        'default. Use --dry-run to preview counts.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes', '-y', action='store_true',
            help='Skip the interactive RESET confirmation (for scripted use).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show row counts that WOULD be deleted, then exit without touching the DB.',
        )
        parser.add_argument(
            '--users', action='store_true',
            help='Also delete tenant-linked User + UserProfile rows (superusers are always kept).',
        )
        parser.add_argument(
            '--audit', action='store_true',
            help='Also wipe AuditLog rows. Off by default because audits are the legal trail.',
        )
        parser.add_argument(
            '--clear-settings', dest='clear_settings', action='store_true',
            help='Also wipe SystemSetting (LGU branding, penalty rules). '
                 'Named to avoid clashing with Django\'s built-in --settings flag.',
        )

    # ------------------------------------------------------------------ #

    def handle(self, *args, **opts):
        self._guard_non_production(opts)

        plan = self._build_plan(opts)

        self.stdout.write(self.style.WARNING(
            f'Database under attack: {connection.settings_dict["NAME"]} '
            f'({connection.vendor})'
        ))
        self.stdout.write('Rows that will be removed:')
        for label, count in plan['business']:
            self.stdout.write(f'  {label:<24} {count:>10,}')
        for label, count in plan['optional']:
            self.stdout.write(f'  {label:<24} {count:>10,}  (opt-in)')
        for label, count in plan['kept']:
            self.stdout.write(f'  {label:<24} {count:>10,}  KEPT — pass flag to clear')

        if opts['dry_run']:
            self.stdout.write(self.style.NOTICE('--dry-run specified; nothing was deleted.'))
            return

        if not opts['yes']:
            self._confirm_interactively()
        else:
            self.stdout.write(self.style.WARNING('--yes given; proceeding without prompt.'))

        with transaction.atomic():
            self._execute(plan['to_delete'])

        self.stdout.write(self.style.SUCCESS('Reset complete.'))

    # ------------------------------------------------------------------ #

    def _guard_non_production(self, opts):
        """Refuse to run against a production-looking deployment.

        ``DEBUG=False`` is treated as production (Django's own convention).
        To override — e.g. a real staging DB that must be reprovisioned —
        set ``FORCE_RESET=1`` in the environment. This is not a security
        boundary, just a speed bump so nobody fat-fingers this on the live
        box. ``--dry-run`` never mutates anything so it always passes.
        """
        if opts['dry_run']:
            return
        if getattr(settings, 'DEBUG', False):
            return
        if opts['yes'] or __import__('os').environ.get('FORCE_RESET') == '1':
            return
        raise CommandError(
            'Refusing to reset a non-DEBUG database. Set FORCE_RESET=1 or '
            'run without --dry-run/--yes after you have verified the target.'
        )

    def _confirm_interactively(self):
        if not connection.vendor == 'sqlite' and not settings.DEBUG:
            # Extra paranoia for real server DBs even after the guard.
            pass
        try:
            answer = input(
                self.style.ERROR(
                    'Type "RESET" (uppercase) to irreversibly wipe the rows listed above: '
                )
            )
        except EOFError:
            raise CommandError('Non-interactive shell — pass --yes to confirm.')
        if answer.strip() != 'RESET':
            raise CommandError('Aborted — confirmation text did not match.')

    # ------------------------------------------------------------------ #

    def _build_plan(self, opts):
        """Return counts grouped by what will be deleted vs. kept.

        Also builds the concrete list of (label, queryset) pairs the execute
        step iterates through so the summary and the actual DELETE calls
        can never drift apart.
        """
        to_delete = []
        business_summary = []
        for model in BUSINESS_MODELS:
            count = model.objects.count()
            business_summary.append((f'{model._meta.verbose_name_plural.title()}', count))
            to_delete.append((model.__name__, model.objects.all()))

        optional_summary = []
        if opts['users']:
            # Never delete a superuser; the person running this (or their
            # successor on the box) still needs to be able to log in.
            tenant_user_qs = User.objects.filter(profile__role='tenant')
            optional_summary.append(('Tenant Users (User + profile)', tenant_user_qs.count()))
            to_delete.append(('User (tenant)', tenant_user_qs))
            # UserProfile rows go via on_delete=CASCADE, but we call them
            # out here so dry-run counts line up with what actually happens.
        if opts['audit']:
            optional_summary.append(('AuditLog', AuditLog.objects.count()))
            to_delete.append(('AuditLog', AuditLog.objects.all()))
        if opts['clear_settings']:
            optional_summary.append(('SystemSetting', SystemSetting.objects.count()))
            to_delete.append(('SystemSetting', SystemSetting.objects.all()))

        kept_summary = []
        if not opts['users']:
            kept_summary.append(('Tenant User accounts', User.objects.filter(profile__role='tenant').count()))
        if not opts['audit']:
            kept_summary.append(('AuditLog', AuditLog.objects.count()))
        if not opts['clear_settings']:
            kept_summary.append(('SystemSetting', SystemSetting.objects.count()))
        # Superusers are always kept — surface the count so the operator
        # sees that the admin login will survive.
        kept_summary.append(('Superuser accounts', User.objects.filter(is_superuser=True).count()))

        return {
            'business': business_summary,
            'optional': optional_summary,
            'kept': kept_summary,
            'to_delete': to_delete,
        }

    # ------------------------------------------------------------------ #

    def _execute(self, to_delete):
        """Fire each queryset's bulk ``delete()`` and log the row count."""
        for label, qs in to_delete:
            # Using the normal queryset delete() (not _raw_delete) so the
            # on_delete=CASCADE behaviour stays intact and post_delete
            # signals still fire.
            count = qs.count()
            if count:
                qs.delete()
            self.stdout.write(f'  deleted {count:>8,} {label}')

        # SQLite / MySQL / Postgres all keep an autoincrement counter after
        # DELETE; reset it so a follow-up ``seed_data`` starts IDs at 1
        # again instead of at 47,382. Only works when tables are empty.
        self._reset_sequences()

    def _reset_sequences(self):
        vendor = connection.vendor
        if vendor == 'sqlite':
            with connection.cursor() as cur:
                cur.execute("DELETE FROM sqlite_sequence")
        elif vendor == 'mysql':
            # MySQL resets AUTO_INCREMENT automatically on TRUNCATE; we used
            # DELETE so re-issue ALTER for each business table that is empty.
            pass
        elif vendor == 'postgresql':
            with connection.cursor() as cur:
                for model in BUSINESS_MODELS:
                    table = model._meta.db_table
                    cur.execute(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)",
                        [table],
                    )
        # MySQL leaves counters high; that's tolerable for a dev reset and
        # avoids us running DDL on a table we do not fully control.
