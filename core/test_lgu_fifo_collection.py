from datetime import date, timedelta
from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from core.models import AuditLog, Billing, Payment, UserProfile
from core.test_payment_service import BillingFixtureMixin


class LguFifoCollectionTests(BillingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.collector, role='collector')
        self.client.force_login(self.collector)

        # Month 1 (Jan 2026) already exists from BillingFixtureMixin (100.00 due, Overdue)
        self.billing.penalty_amount = Decimal('20.00')
        self.billing.total_due = Decimal('120.00')
        self.billing.balance = Decimal('120.00')
        self.billing.due_date = date.today() - timedelta(days=40)
        self.billing.status = 'Overdue'
        self.billing.save()

        # Month 2 (Feb 2026): 100.00 rent + 10.00 penalty = 110.00
        self.billing_feb = Billing.objects.create(
            tenant=self.tenant,
            stall=self.stall,
            contract=self.contract,
            billing_month=2,
            billing_year=2026,
            rental_amount=Decimal('100.00'),
            penalty_amount=Decimal('10.00'),
            total_due=Decimal('110.00'),
            amount_paid=Decimal('0.00'),
            balance=Decimal('110.00'),
            due_date=date.today() - timedelta(days=10),
            status='Overdue',
        )

        # Month 3 (Mar 2026): 100.00 rent + 0.00 penalty = 100.00
        self.billing_mar = Billing.objects.create(
            tenant=self.tenant,
            stall=self.stall,
            contract=self.contract,
            billing_month=3,
            billing_year=2026,
            rental_amount=Decimal('100.00'),
            penalty_amount=Decimal('0.00'),
            total_due=Decimal('100.00'),
            amount_paid=Decimal('0.00'),
            balance=Decimal('100.00'),
            due_date=date.today() + timedelta(days=20),
            status='Unpaid',
        )
        self.url = reverse('billing_tenant_collect', args=[self.tenant.pk])

    def test_workspace_renders_rent_penalty_breakdown_soa_and_overdue_notice_links(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Monthly Rent')
        self.assertContains(resp, 'Penalty / Surcharge')
        self.assertContains(resp, 'Arrears-First (FIFO) Cash')
        self.assertContains(resp, reverse('billing_tenant_soa', args=[self.tenant.pk]))
        self.assertContains(resp, f"{reverse('notice_add')}?tenant={self.tenant.pk}")
        self.assertContains(resp, 'Issue Overdue Notice')

    def test_fifo_partial_allocates_oldest_first_and_shares_single_or(self):
        # Tender 170.00: settles Jan (120.00 Full) + applies 50.00 Partial to Feb; Mar untouched
        resp = self.client.post(self.url, {
            'collection_mode': 'fifo',
            'amount_tendered': '170.00',
            'payment_method': 'Cash',
            'payment_date': date.today().isoformat(),
            'remarks': 'FIFO walk-in payment',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('payment_batch_receipt'), resp['Location'])

        self.billing.refresh_from_db()
        self.billing_feb.refresh_from_db()
        self.billing_mar.refresh_from_db()

        self.assertEqual(self.billing.status, 'Paid')
        self.assertEqual(self.billing.balance, Decimal('0.00'))
        self.assertEqual(self.billing_feb.status, 'Partial')
        self.assertEqual(self.billing_feb.amount_paid, Decimal('50.00'))
        self.assertEqual(self.billing_feb.balance, Decimal('60.00'))
        self.assertEqual(self.billing_mar.status, 'Unpaid')
        self.assertEqual(self.billing_mar.balance, Decimal('100.00'))

        payments = list(Payment.objects.filter(tenant=self.tenant).order_by('billing_year', 'billing_month'))
        self.assertEqual(len(payments), 2)
        self.assertEqual(payments[0].official_receipt_no, payments[1].official_receipt_no)
        self.assertEqual(payments[0].amount_paid, Decimal('120.00'))
        self.assertEqual(payments[1].amount_paid, Decimal('50.00'))
        self.assertTrue(AuditLog.objects.filter(action='COLLECT_FIFO').exists())

    def test_fifo_cash_exceeding_total_outstanding_computes_change_due(self):
        # Total outstanding across Jan+Feb+Mar = 330.00; tender 500.00 -> change 170.00
        # Ensure no extra auto-created months interfere by keeping contract end_date in March 2026
        self.contract.end_date = date(2026, 3, 31)
        self.contract.save(update_fields=['end_date'])
        Billing.objects.filter(tenant=self.tenant, billing_month__gt=3).delete()

        resp = self.client.post(self.url, {
            'collection_mode': 'fifo',
            'amount_tendered': '500.00',
            'payment_method': 'Cash',
            'payment_date': date.today().isoformat(),
            'remarks': '',
        })
        self.assertEqual(resp.status_code, 302)

        msgs = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any('Change due: ₱170.00' in m for m in msgs), msgs)

        for b in (self.billing, self.billing_feb, self.billing_mar):
            b.refresh_from_db()
            self.assertEqual(b.status, 'Paid')
            self.assertEqual(b.balance, Decimal('0.00'))

    def test_fifo_rejects_zero_or_invalid_amount(self):
        resp = self.client.post(self.url, {
            'collection_mode': 'fifo',
            'amount_tendered': '0',
            'payment_method': 'Cash',
            'payment_date': date.today().isoformat(),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Payment.objects.count(), 0)

    def test_selected_checkbox_mode_still_works(self):
        resp = self.client.post(self.url, {
            'collection_mode': 'selected',
            'billing_ids': [str(self.billing_mar.pk)],
            'payment_method': 'Cash',
            'payment_date': date.today().isoformat(),
        })
        self.assertEqual(resp.status_code, 302)
        self.billing_mar.refresh_from_db()
        self.assertEqual(self.billing_mar.status, 'Paid')
        self.assertEqual(self.billing_mar.balance, Decimal('0.00'))
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, 'Overdue')
