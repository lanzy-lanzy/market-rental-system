from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.forms import BillingForm, PaymentForm
from core.helpers import record_payment
from core.ledger_statement import tenant_statement
from core.models import Billing, Payment, UserProfile
from core.test_payment_service import BillingFixtureMixin


class NoDiscountTests(BillingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.collector.is_superuser = True
        self.collector.save()
        UserProfile.objects.create(user=self.collector, role='admin')
        self.client.force_login(self.collector)

    def test_billing_and_payment_forms_exclude_discount(self):
        self.assertNotIn('discount', BillingForm().fields)
        self.assertNotIn('discount', PaymentForm().fields)

    def test_billing_form_ignores_posted_discount_and_zeroes_it(self):
        form = BillingForm(data={
            'tenant': self.tenant.pk,
            'stall': self.stall.pk,
            'contract': self.contract.pk,
            'billing_month': 2,
            'billing_year': 2026,
            'rental_amount': '500.00',
            'penalty_amount': '50.00',
            'discount': '100.00',
            'total_due': '450.00',
            'amount_paid': '0.00',
            'balance': '450.00',
            'due_date': '2026-02-05',
            'status': 'Unpaid',
        })
        self.assertTrue(form.is_valid(), form.errors)
        billing = form.save()
        self.assertEqual(billing.total_due, Decimal('550.00'))
        self.assertEqual(billing.balance, Decimal('550.00'))
        self.assertEqual(billing.discount, Decimal('0.00'))

    def test_billing_payment_receipt_and_ledger_templates_hide_discount(self):
        with transaction.atomic():
            payment = record_payment(
                tenant=self.tenant,
                billing=self.billing,
                amount=Decimal('100.00'),
                payment_date=date(2026, 1, 10),
                collected_by=self.collector,
                remarks='Paid on time',
            )
        urls = [
            reverse('billing_add_modal'),
            reverse('billing_edit_modal', args=[self.billing.pk]),
            reverse('billing_view', args=[self.billing.pk]),
            reverse('payment_add'),
            reverse('payment_add_modal'),
            reverse('payment_view', args=[payment.pk]),
            reverse('payment_receipt', args=[payment.pk]),
            reverse('payment_print_receipt', args=[payment.pk]),
            reverse('ledger_view', args=[self.tenant.pk]),
            reverse('ledger_print', args=[self.tenant.pk]),
        ]
        for url in urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotContains(resp, 'Discount', msg_prefix=f'Discount found on {url}')
            self.assertNotContains(resp, 'less discounts', msg_prefix=f'discounts text found on {url}')

    def test_batch_receipt_excludes_discount_column_and_context(self):
        with transaction.atomic():
            payment = record_payment(
                tenant=self.tenant,
                billing=self.billing,
                amount=Decimal('100.00'),
                payment_date=date(2026, 1, 10),
                collected_by=self.collector,
            )
        session = self.client.session
        session['last_batch_payment_ids'] = [payment.pk]
        session.save()
        resp = self.client.get(reverse('payment_batch_receipt'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('discount_total', resp.context)
        self.assertNotContains(resp, 'Discount')


class LedgerStatusAndRemarksTests(BillingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.collector.is_superuser = True
        self.collector.save()
        UserProfile.objects.create(user=self.collector, role='admin')
        self.client.force_login(self.collector)

    def test_statement_computes_entry_and_account_status_and_remarks(self):
        self.tenant.notes = 'Priority market vendor'
        self.tenant.save(update_fields=['notes'])
        with transaction.atomic():
            record_payment(
                tenant=self.tenant,
                billing=self.billing,
                amount=Decimal('40.00'),
                payment_date=date(2026, 1, 10),
                collected_by=self.collector,
                remarks='Partial cash deposit',
            )
        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['account_status'], 'Partial')
        self.assertIn('Priority market vendor', statement['account_remarks'])
        self.assertIn('Partial cash deposit', statement['account_remarks'])
        self.assertEqual(statement['entries'][0].status, 'Partial')
        self.assertEqual(statement['entries'][0].remarks, 'Partial cash deposit')

    def test_statement_marks_overdue_and_falls_back_to_contract_remarks(self):
        self.contract.remarks = 'Corner stall near entrance'
        self.contract.save(update_fields=['remarks'])
        self.billing.due_date = timezone.localdate() - timedelta(days=10)
        self.billing.save(update_fields=['due_date'])

        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['account_status'], 'Overdue')
        self.assertEqual(statement['account_remarks'], 'Corner stall near entrance')
        self.assertEqual(statement['entries'][0].status, 'Overdue')
        self.assertEqual(statement['entries'][0].remarks, 'Corner stall near entrance')

    def test_ledger_list_detail_print_and_report_render_status_and_remarks(self):
        with transaction.atomic():
            record_payment(
                tenant=self.tenant,
                billing=self.billing,
                amount=Decimal('100.00'),
                payment_date=date(2026, 1, 10),
                collected_by=self.collector,
                remarks='Settled via cashier window',
            )

        for url in [
            reverse('ledger_list'),
            reverse('ledger_list_print'),
            reverse('ledger_view', args=[self.tenant.pk]),
            reverse('ledger_print', args=[self.tenant.pk]),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertContains(resp, 'Status', msg_prefix=url)
            self.assertContains(resp, 'Remarks', msg_prefix=url)
            self.assertContains(resp, 'Paid', msg_prefix=url)
            self.assertContains(resp, 'Settled via cashier window', msg_prefix=url)

        report_resp = self.client.get(
            reverse('report_ledger'),
            {'date_from': '2026-01-01', 'date_to': '2026-01-31'},
        )
        self.assertEqual(report_resp.status_code, 200)
        self.assertContains(report_resp, 'Status')
        self.assertContains(report_resp, 'Remarks')
        self.assertContains(report_resp, 'Paid')
        self.assertContains(report_resp, 'Settled via cashier window')
