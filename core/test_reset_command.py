"""Tests for the ``reset_market_data`` management command.

These exercise the safety rails (dry-run, production guard, RESET prompt)
and the actual teardown path against the test database — which Django
already isolates into an in-memory SQLite file, so a runaway DELETE
cannot touch the real ``db.sqlite3``.
"""

from datetime import date
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import (
    AuditLog, Billing, MarketSection, Notice, Payment, RentalContract,
    Stall, StallType, SystemSetting, Tenant, TenantLedger, UserProfile,
)


class ResetMarketDataTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.section = MarketSection.objects.create(name='A')
        self.stall_type = StallType.objects.create(name='Dry Goods')
        self.stall = Stall.objects.create(
            stall_number='RST-01', section=self.section,
            stall_type=self.stall_type, monthly_rate=Decimal('150.00'),
            status='Occupied',
        )
        self.tenant_user = User.objects.create_user(username='tenant_owner', password='x')
        UserProfile.objects.create(user=self.tenant_user, role='tenant')
        self.tenant = Tenant.objects.create(
            tenant_id='TEN-RST', full_name='Wipe Me', address='Zamboanga',
            contact_number='0900', status='Active', user=self.tenant_user,
        )
        self.contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.stall, start_date=date(2026, 1, 1),
            monthly_rent=Decimal('150.00'), due_day=5, status='Active',
        )
        self.billing = Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=1, billing_year=2026,
            rental_amount=Decimal('150.00'), penalty_amount=Decimal('0.00'),
            discount=Decimal('0.00'), total_due=Decimal('150.00'),
            amount_paid=Decimal('150.00'), balance=Decimal('0.00'),
            due_date=date(2026, 1, 5), status='Paid',
        )
        self.collector = User.objects.create_user(username='coll', password='x')
        UserProfile.objects.create(user=self.collector, role='collector')
        self.payment = Payment.objects.create(
            receipt_number='RCP-RST-1', tenant=self.tenant, stall=self.stall,
            billing=self.billing, billing_month=1, billing_year=2026,
            rental_amount=Decimal('150.00'), penalty_amount=Decimal('0.00'),
            discount=Decimal('0.00'), total_amount_due=Decimal('150.00'),
            amount_paid=Decimal('150.00'), payment_date=date(2026, 1, 10),
            payment_method='Cash', collected_by=self.collector, status='Paid',
        )
        self.ledger = TenantLedger.objects.create(
            tenant=self.tenant, billing=self.billing,
            transaction_date=date(2026, 1, 5), description='billing',
            debit=Decimal('150.00'), credit=Decimal('0.00'),
            balance=Decimal('150.00'),
        )
        self.notice = Notice.objects.create(
            tenant=self.tenant, notice_type='Demand',
            notice_number='N-RST-1', date_issued=date(2026, 1, 20),
            content='please pay',
        )
        self.audit = AuditLog.objects.create(
            user=self.collector, action='TEST', module='Fixture',
            description='keep me unless --audit',
        )

    # --- helpers --------------------------------------------------------

    def _run(self, *args, **kwargs):
        out = StringIO()
        call_command('reset_market_data', *args, stdout=out, stderr=out, **kwargs)
        return out.getvalue()

    def _business_rows_present(self):
        return any([
            Tenant.objects.exists(), RentalContract.objects.exists(),
            Billing.objects.exists(), Payment.objects.exists(),
            TenantLedger.objects.exists(), Notice.objects.exists(),
            Stall.objects.exists(), MarketSection.objects.exists(),
            StallType.objects.exists(),
        ])

    # --- tests ----------------------------------------------------------

    def test_dry_run_preserves_everything(self):
        out = self._run('--dry-run')
        self.assertIn('nothing was deleted', out)
        # Sanity: the counts printed should reflect what actually exists.
        self.assertIn('Tenants', out)
        self.assertTrue(self._business_rows_present())
        self.assertTrue(Tenant.objects.filter(pk=self.tenant.pk).exists())
        self.assertTrue(Payment.objects.filter(pk=self.payment.pk).exists())

    def test_reset_wipes_business_tables_and_keeps_opt_ins(self):
        # DEBUG=True in tests so the production guard passes; --yes skips
        # the interactive prompt.
        out = self._run('--yes')
        self.assertIn('Reset complete', out)

        # Business tables cleared.
        self.assertFalse(Tenant.objects.exists())
        self.assertFalse(RentalContract.objects.exists())
        self.assertFalse(Billing.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(TenantLedger.objects.exists())
        self.assertFalse(Notice.objects.exists())
        self.assertFalse(Stall.objects.exists())
        self.assertFalse(MarketSection.objects.exists())
        self.assertFalse(StallType.objects.exists())

        # Opt-in tables survived — this is the whole point of the flags.
        self.assertTrue(AuditLog.objects.filter(pk=self.audit.pk).exists())
        self.assertTrue(SystemSetting.objects.exists())
        # Tenant User is kept unless --users is passed; the collector row
        # and the tenant owner row are both still there.
        self.assertTrue(User.objects.filter(pk=self.tenant_user.pk).exists())

    def test_users_flag_removes_tenant_users_but_not_superuser(self):
        # Seed one superuser to prove the command never touches it.
        su = User.objects.create_superuser(
            username='root', email='r@example.com', password='x'
        )
        self._run('--yes', '--users')
        self.assertFalse(User.objects.filter(pk=self.tenant_user.pk).exists())
        self.assertTrue(User.objects.filter(pk=su.pk).exists())
        # Collector is staff, not tenant, so it survives even with --users.
        self.assertTrue(User.objects.filter(pk=self.collector.pk).exists())

    def test_audit_flag_clears_logs(self):
        self._run('--yes', '--audit')
        self.assertFalse(AuditLog.objects.exists())

    def test_clear_settings_flag(self):
        self._run('--yes', '--clear-settings')
        self.assertFalse(SystemSetting.objects.exists())

    def test_confirmation_required_without_yes(self):
        """Bad interactive input aborts before any deletion."""
        with override_settings(DEBUG=True):
            with mock.patch('builtins.input', return_value='nope'):
                with self.assertRaises(CommandError):
                    call_command('reset_market_data', stdout=StringIO())
        # Nothing was deleted.
        self.assertTrue(Tenant.objects.filter(pk=self.tenant.pk).exists())

    def test_exact_reset_word_proceeds(self):
        with override_settings(DEBUG=True):
            with mock.patch('builtins.input', return_value='RESET'):
                call_command('reset_market_data', stdout=StringIO())
        self.assertFalse(Tenant.objects.exists())

    @override_settings(DEBUG=False)
    def test_refuses_non_debug_without_force(self):
        """Production-shaped settings raise unless FORCE_RESET=1 is set."""
        with self.assertRaises(CommandError) as ctx:
            call_command('reset_market_data', stdout=StringIO())
        self.assertIn('non-DEBUG', str(ctx.exception))
        # Data untouched.
        self.assertTrue(Tenant.objects.filter(pk=self.tenant.pk).exists())

    @override_settings(DEBUG=False)
    def test_force_reset_env_allows_run(self):
        with mock.patch.dict('os.environ', {'FORCE_RESET': '1'}):
            self._run('--yes')
        self.assertFalse(Tenant.objects.exists())
