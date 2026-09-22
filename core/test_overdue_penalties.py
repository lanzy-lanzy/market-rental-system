# core/test_overdue_penalties.py
# Tests for automatic overdue marking + penalty accrual (gap #6 fix).
from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from core.models import (
    MarketSection, Stall, Tenant, RentalContract, Billing, TenantLedger, SystemSetting,
)
from core.helpers import apply_overdue_penalties, maybe_apply_overdue_penalties


class OverduePenaltyTests(TestCase):
    def setUp(self):
        cache.clear()
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Market', office_name='Office',
            receipt_prefix='DMPM', default_due_day=5,
            penalty_type='percentage', penalty_value=Decimal('2.00'), grace_period=5,
        )
        self.section = MarketSection.objects.create(name='A')
        self.stall = Stall.objects.create(stall_number='S-01', section=self.section, monthly_rate=Decimal('100.00'))
        self.tenant = Tenant.objects.create(tenant_id='T-700', full_name='Overdue Test', address='x', contact_number='0900')
        self.contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.stall, start_date=date(2020, 1, 1),
            monthly_rent=Decimal('100.00'), due_day=5, status='Active',
        )

    def _billing(self, due_date, status='Unpaid', month=None, year=None):
        billing = Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=month or due_date.month, billing_year=year or due_date.year,
            rental_amount=Decimal('100.00'), penalty_amount=Decimal('0.00'),
            discount=Decimal('0.00'), total_due=Decimal('100.00'),
            amount_paid=Decimal('0.00'), balance=Decimal('100.00'),
            due_date=due_date, status=status,
        )
        TenantLedger.objects.create(
            tenant=self.tenant, billing=billing, transaction_date=due_date,
            description='billing', debit=Decimal('100.00'), credit=Decimal('0.00'),
            balance=Decimal('100.00'),
        )
        return billing

    def test_past_due_is_marked_overdue_and_penalized_once(self):
        billing = self._billing(date.today() - timedelta(days=30))
        overdue, penalized = apply_overdue_penalties()
        billing.refresh_from_db()
        self.assertEqual((overdue, penalized), (1, 1))
        self.assertEqual(billing.status, 'Overdue')
        self.assertEqual(billing.penalty_amount, Decimal('2.00'))   # 2% of 100
        self.assertEqual(billing.total_due, Decimal('102.00'))
        self.assertEqual(billing.balance, Decimal('102.00'))
        self.assertTrue(TenantLedger.objects.filter(billing=billing, debit=Decimal('2.00')).exists())
        # Ledger running balance ends at the full outstanding (100 rent + 2 penalty).
        self.assertEqual(TenantLedger.objects.filter(tenant=self.tenant).order_by('-id').first().balance, Decimal('102.00'))

    def test_idempotent_second_run_applies_nothing(self):
        billing = self._billing(date.today() - timedelta(days=30))
        apply_overdue_penalties()
        overdue, penalized = apply_overdue_penalties()
        billing.refresh_from_db()
        self.assertEqual((overdue, penalized), (0, 0))
        self.assertEqual(billing.penalty_amount, Decimal('2.00'))    # not double-charged
        self.assertEqual(TenantLedger.objects.filter(billing=billing, debit=Decimal('2.00')).count(), 1)

    def test_within_grace_period_untouched(self):
        billing = self._billing(date.today() - timedelta(days=2))  # due+5 grace not elapsed
        apply_overdue_penalties()
        billing.refresh_from_db()
        self.assertEqual(billing.status, 'Unpaid')
        self.assertEqual(billing.penalty_amount, Decimal('0.00'))

    def test_seeded_overdue_still_gets_penalty(self):
        # A billing flagged Overdue directly (e.g. by seed data) but never penalized.
        billing = self._billing(date.today() - timedelta(days=40), status='Overdue')
        overdue, penalized = apply_overdue_penalties()
        billing.refresh_from_db()
        self.assertEqual(penalized, 1)
        self.assertEqual(overdue, 0)              # already Overdue, not newly marked
        self.assertEqual(billing.penalty_amount, Decimal('2.00'))

    def test_maybe_trigger_runs_only_once_per_day(self):
        billing = self._billing(date.today() - timedelta(days=30))
        maybe_apply_overdue_penalties()          # claims the day and runs
        billing.refresh_from_db()
        self.assertEqual(billing.penalty_amount, Decimal('2.00'))
        # Add another overdue bill in a distinct period; second same-day trigger is a no-op (throttled).
        second = self._billing(date.today() - timedelta(days=31), status='Unpaid', month=6, year=2019)
        maybe_apply_overdue_penalties()
        second.refresh_from_db()
        self.assertEqual(second.status, 'Unpaid')
        self.assertEqual(second.penalty_amount, Decimal('0.00'))
