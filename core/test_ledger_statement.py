from decimal import Decimal
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from core.helpers import record_payment
from core.ledger_statement import tenant_statement
from core.models import TenantLedger
from core.test_payment_service import BillingFixtureMixin


class LedgerStatementTests(BillingFixtureMixin, TestCase):
    def pay(self, amount):
        with transaction.atomic():
            return record_payment(
                tenant=self.tenant, billing=self.billing, amount=Decimal(amount),
                payment_date=self.billing.due_date, collected_by=self.collector,
            )

    def test_fully_paid_ignores_stale_ledger_and_cached_bill_values(self):
        self.pay('100')
        TenantLedger.objects.filter(tenant=self.tenant).update(balance=999, debit=300)
        self.billing.__class__.objects.filter(pk=self.billing.pk).update(amount_paid=0, balance=100)
        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['running_balance'], Decimal('0'))
        self.assertEqual(statement['total_debits'], Decimal('100'))
        self.assertEqual(statement['paid_bills'], 1)
        self.assertTrue(all(e.billing.balance == 0 for e in statement['entries']))
        self.assertEqual(statement['entries'][0].balance, 0)

    def test_partial_and_void_receipts(self):
        self.pay('40')
        void = self.pay('60')
        void.status = 'Void'
        void.save()
        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['total_credits'], Decimal('40'))
        self.assertEqual(statement['running_balance'], Decimal('60'))
        self.assertEqual(statement['unpaid_bills'], 1)
        self.assertEqual(len(statement['entries']), 2)
        self.assertEqual(statement['entries'][0].billing.status, 'Partial')

    def test_excess_is_separate_and_never_negative_due(self):
        self.pay('150')
        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['running_balance'], 0)
        self.assertEqual(statement['total_credits'], 100)
        self.assertEqual(statement['unapplied_amount'], 50)

    def test_screen_print_and_pdf_share_totals_and_bill_balances(self):
        self.pay('100')
        self.collector.is_superuser = True
        self.collector.save()
        self.client.force_login(self.collector)
        for route in ['ledger_view', 'ledger_print']:
            response = self.client.get(reverse(route, args=[self.tenant.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['running_balance'], 0)
            self.assertContains(response, 'Account Balance After Entry')
            self.assertContains(response, 'Due: &#8369;0.00')
        with patch('core.views.ledger.render_to_pdf_response') as render:
            from django.http import HttpResponse
            render.return_value = HttpResponse('pdf')
            self.client.get(reverse('ledger_view_export_pdf', args=[self.tenant.pk]))
            self.assertEqual(render.call_args.args[2]['running_balance'], 0)

    def test_excess_on_one_bill_does_not_hide_another_unpaid_bill(self):
        self.pay('150')
        self.billing.pk = None
        self.billing.billing_month = 2
        self.billing.save()
        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['running_balance'], Decimal('100'))
        self.assertEqual(statement['paid_bills'], 1)
        self.assertEqual(statement['unpaid_bills'], 1)
        self.assertEqual(statement['unapplied_amount'], Decimal('50'))

    def test_empty_account_has_zero_totals(self):
        self.billing.delete()
        statement = tenant_statement(self.tenant)
        self.assertEqual(statement['entries'], [])
        self.assertEqual(statement['running_balance'], Decimal('0'))
        self.assertEqual(statement['paid_bills'], 0)
