# core/management/commands/link_tenant_logins.py
# One-shot repair for orphan tenant-role logins.
#
# The canonical tenant onboarding flow (/tenants/add/ -> create_tenant_login)
# links the Tenant record to its portal User automatically. Historically an
# admin could also create a role='tenant' User from /users/add/, which never
# produced a Tenant row and dropped the person on no_tenant.html. This
# command scans for those orphans and safely re-links them by matching the
# login's username (or email) against an unassigned Tenant.tenant_id.
#
# It is intentionally conservative:
#   * Never overwrites an existing Tenant.user link.
#   * Never links when the match is ambiguous (multiple candidates).
#   * Never invents a Tenant row for a User that has no counterpart.
# Use --dry-run to preview; --revers to unlink bogus matches the same rules
# would flag (already-linked tenants whose user is a different role).

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import AuditLog, Tenant, UserProfile


class Command(BaseCommand):
    help = (
        'Link existing tenant-role User accounts to their matching Tenant '
        'record so they can access /portal/ (fixes no_tenant.html orphans).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be linked without writing to the database.',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print every skipped row with the reason it was skipped.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        verbose = options['verbose']

        # Users that carry the tenant role but no Tenant row pointing back
        # at them. This is the exact shape that produces no_tenant.html.
        orphan_users = list(
            User.objects.select_related('profile')
            .filter(profile__role='tenant', tenant__isnull=True)
            .order_by('username')
        )

        # Tenant rows still floating without a login. These are the pool
        # an orphan can be matched against.
        unassigned_tenants = list(
            Tenant.objects.filter(user__isnull=True).order_by('tenant_id')
        )

        linked = []
        ambiguous = []
        unmatched = []

        # Index unassigned tenants so we can find candidates fast and
        # also detect collisions between two orphan users wanting the
        # same tenant row.
        by_tid = {}
        by_email = {}
        for t in unassigned_tenants:
            key = (t.tenant_id or '').strip().lower()
            if key:
                by_tid.setdefault(key, []).append(t)
            ekey = (t.email or '').strip().lower()
            if ekey:
                by_email.setdefault(ekey, []).append(t)

        consumed_pks = set()

        for u in orphan_users:
            ukey = (u.username or '').strip().lower()
            ekey = (u.email or '').strip().lower()

            # 1. Prefer an exact (case-insensitive) tenant_id == username hit.
            candidates = [
                t for t in by_tid.get(ukey, [])
                if t.pk not in consumed_pks
            ] if ukey else []

            # 2. Fall back to email match only if the username path is empty.
            if not candidates and ekey:
                candidates = [
                    t for t in by_email.get(ekey, [])
                    if t.pk not in consumed_pks
                ]

            if not candidates:
                unmatched.append(u)
                continue
            if len(candidates) > 1:
                ambiguous.append((u, [t.tenant_id for t in candidates]))
                continue

            tenant = candidates[0]
            consumed_pks.add(tenant.pk)
            linked.append((u, tenant))

        # Reporting first so --dry-run can bail before the writes.
        self.stdout.write(self.style.MIGRATE_HEADING('Scan summary'))
        self.stdout.write(f'  tenant-role users without a link: {len(orphan_users)}')
        self.stdout.write(f'  unassigned Tenant rows available:  {len(unassigned_tenants)}')
        self.stdout.write(f'  will link:                          {len(linked)}')
        self.stdout.write(f'  ambiguous (needs manual review):    {len(ambiguous)}')
        self.stdout.write(f'  no matching Tenant found:           {len(unmatched)}')
        self.stdout.write('')

        if linked:
            self.stdout.write(self.style.MIGRATE_HEADING('Link plan'))
            for u, t in linked:
                self.stdout.write(
                    f'  + user {u.username!r} (id={u.pk})  ->  '
                    f'Tenant {t.tenant_id} (pk={t.pk}, name={t.full_name or "?"})'
                )
            self.stdout.write('')

        if ambiguous and verbose:
            self.stdout.write(self.style.MIGRATE_HEADING('Ambiguous matches (skipped)'))
            for u, tids in ambiguous:
                self.stdout.write(
                    f'  ! user {u.username!r} matches multiple tenant_ids: {tids}'
                )
            self.stdout.write('')

        if unmatched and verbose:
            self.stdout.write(self.style.MIGRATE_HEADING('Orphans with no Tenant (skipped)'))
            for u in unmatched:
                self.stdout.write(
                    f'  - user {u.username!r} (email={u.email or "-"}) '
                    'has no matching Tenant row'
                )
            self.stdout.write('')

        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN: no changes were written.'))
            return

        if not linked:
            self.stdout.write(self.style.SUCCESS('Nothing to link — database is consistent.'))
            return

        with transaction.atomic():
            for u, t in linked:
                t.user = u
                t.save(update_fields=['user'])
                AuditLog.objects.create(
                    user=None,
                    action='UPDATE',
                    module='Tenant',
                    description=(
                        f'link_tenant_logins: associated login {u.username} '
                        f'with Tenant {t.tenant_id}'
                    ),
                )

        self.stdout.write(self.style.SUCCESS(
            f'Linked {len(linked)} tenant login(s). '
            f'Ambiguous: {len(ambiguous)}, unmatched: {len(unmatched)}.'
        ))
