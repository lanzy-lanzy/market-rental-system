# core/test_payment_service.py
# Tests for the shared record_payment()/recalc service that backs collection.
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase

from core.models import (
    MarketSection, Stall, Tenant, RentalContract, Billing, Payment, TenantLedger, SystemSetting,
)
from core.helpers import record_payment, generate_receipt_number


class RecordPaymentServiceTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.section = MarketSection.objects.create(name='A')
        self.stall = Stall.objects.create(stall_number='S-01', section=self.section, monthly_rate=Decimal('100.00'))
        self.tenant = Tenant.objects.create(
            tenant_id='T-500', full_name='Test Tenant', address='x', contact_number='0900',
        )
        self.contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.stall, start_date=date(2026, 1, 1),
            monthly_rent=Decimal('100.00'), due_day=5, status='Active',
        )
        self.billing = Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=1, billing_year=2026, rental_amount=Decimal('100.00'),
            penalty_amount=Decimal('0.00'), discount=Decimal('0.00'),
            total_due=Decimal('100.00'), amount_paid=Decimal('0.00'),
            balance=Decimal('100.00'), due_date=date(2026, 1, 5), status='Unpaid',
        )
        # Mirror real flow: billing creation posts a debit to the ledger.
        TenantLedger.objects.create(
            tenant=self.tenant, billing=self.billing, transaction_date=date(2026, 1, 5),
            description='billing', debit=Decimal('100.00'), credit=Decimal('0.00'),
            balance=Decimal('100.00'),
        )
        self.collector = User.objects.create_user(username='coll', password='x')

    def _pay(self, amount, **kw):
        with transaction.atomic():
            return record_payment(
                tenant=self.tenant, billing=self.billing, amount=amount,
                payment_date=date(2026, 1, 10), payment_method='Cash',
                collected_by=self.collector, **kw,
            )

    def test_full_payment_settles_billing(self):
        payment = self._pay(Decimal('100.00'))
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, 'Paid')
        self.assertEqual(self.billing.balance, Decimal('0.00'))
        self.assertEqual(self.billing.amount_paid, Decimal('100.00'))
        self.assertEqual(payment.status, 'Paid')
        ledger = TenantLedger.objects.get(payment=payment)
        self.assertEqual(ledger.credit, Decimal('100.00'))

    def test_two_partials_settle_and_stay_consistent(self):
        p1 = self._pay(Decimal('40.00'))
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, 'Partial')
        self.assertEqual(self.billing.balance, Decimal('60.00'))
        self.assertEqual(p1.status, 'Partial')

        p2 = self._pay(Decimal('60.00'))
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, 'Paid')
        self.assertEqual(self.billing.balance, Decimal('0.00'))
        self.assertEqual(p2.status, 'Paid')
        self.assertNotEqual(p1.receipt_number, p2.receipt_number)

    def test_overpayment_is_clamped_not_dropped(self):
        # Service applies only the outstanding balance to the ledger/billing,
        # while still recording the full amount received on the payment.
        payment = self._pay(Decimal('150.00'))
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, 'Paid')
        self.assertEqual(self.billing.balance, Decimal('0.00'))
        self.assertEqual(Decimal(payment.amount_paid), Decimal('150.00'))
        ledger = TenantLedger.objects.get(payment=payment)
        self.assertEqual(ledger.credit, Decimal('100.00'))  # clamped to balance
        # Ledger never over-settles into a negative balance.
        self.assertEqual(TenantLedger.objects.filter(tenant=self.tenant).order_by('-id').first().balance, Decimal('0.00'))

    def test_receipt_numbers_sequence_within_period(self):
        period = date.today().strftime('%Y%m')
        first = generate_receipt_number()
        self.assertTrue(first.startswith(f'DMPM-{period}-'))
        self.assertTrue(first.endswith('-000001'))
        self._pay(Decimal('30.00'))
        second = generate_receipt_number()
        self.assertTrue(second.endswith('-000002'))
