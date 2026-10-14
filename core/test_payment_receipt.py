# core/test_payment_receipt.py
# A collection is only finished once the official receipt can be printed.
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from core.helpers import record_payment
from core.models import Payment, UserProfile
from core.test_payment_service import BillingFixtureMixin


class CollectEndsOnTheReceiptTests(BillingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.collector, role='collector')
        self.client.force_login(self.collector)

    def _collect(self, amount, htmx=False):
        url = reverse('billing_collect', args=[self.billing.pk])
        data = {'amount_paid': str(amount), 'payment_method': 'Cash',
                'payment_date': '2026-01-10', 'remarks': ''}
        if htmx:
            return self.client.post(url, data, headers={'hx-request': 'true'})
        return self.client.post(url, data)

    def _receipt_url(self, payment):
        return reverse('payment_print_receipt', args=[payment.pk]) + '?auto=1&back=billing'

    def test_partial_collection_ends_on_the_printable_receipt(self):
        resp = self._collect(Decimal('40.00'))
        payment = Payment.objects.get()
        self.assertEqual(payment.status, 'Partial')
        self.assertEqual(resp['Location'], self._receipt_url(payment))

    def test_full_collection_ends_on_the_printable_receipt(self):
        resp = self._collect(Decimal('100.00'))
        payment = Payment.objects.get()
        self.billing.refresh_from_db()
        self.assertEqual(self.billing.status, 'Paid')
        self.assertEqual(resp['Location'], self._receipt_url(payment))

    def test_htmx_collect_navigates_the_open_modal_to_the_receipt(self):
        resp = self._collect(Decimal('100.00'), htmx=True)
        payment = Payment.objects.get()
        self.assertIn(f"location.href = '{self._receipt_url(payment)}'", resp.content.decode())

    def test_billing_screen_offers_a_reprint_of_a_recorded_receipt(self):
        self._collect(Decimal('100.00'))
        payment = Payment.objects.get()
        body = self.client.get(reverse('billing_view', args=[self.billing.pk])).content.decode()
        self.assertIn(reverse('payment_print_receipt', args=[payment.pk]), body)


class ReceiptPageTests(BillingFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.collector, role='collector')
        self.client.force_login(self.collector)
        self.print_url = None

    def _payment(self):
        with transaction.atomic():
            payment = record_payment(
                tenant=self.tenant, billing=self.billing, amount=Decimal('100.00'),
                payment_date='2026-01-10', payment_method='Cash', collected_by=self.collector,
            )
        self.print_url = reverse('payment_print_receipt', args=[payment.pk])
        return payment

    def test_print_dialog_only_opens_when_the_collect_flow_asks(self):
        self._payment()
        self.assertIn('window.print()', self.client.get(self.print_url + '?auto=1').content.decode())
        self.assertNotIn("addEventListener('load'", self.client.get(self.print_url).content.decode())

    def test_back_link_points_at_the_billing_list(self):
        self._payment()
        body = self.client.get(self.print_url + '?auto=1&back=billing').content.decode()
        self.assertIn('href="/billing/"', body)

    def test_an_unknown_back_target_renders_no_link(self):
        self._payment()
        body = self.client.get(self.print_url + '?back=/dashboard/').content.decode()
        self.assertNotIn('Back to list', body)

    def test_the_toolbar_is_left_off_the_printed_page(self):
        self._payment()
        body = self.client.get(self.print_url).content.decode()
        self.assertIn('.no-print { display: none !important; }', body)

    def test_a_tenant_sees_their_own_receipt_without_a_staff_back_link(self):
        payment = self._payment()
        tenant_user = User.objects.create_user(username='tenant-login', password='x')
        UserProfile.objects.create(user=tenant_user, role='tenant')
        self.tenant.user = tenant_user
        self.tenant.save(update_fields=['user'])
        self.client.force_login(tenant_user)
        body = self.client.get(self.print_url + '?back=billing').content.decode()
        self.assertIn(payment.receipt_number, body)
        self.assertNotIn('Back to list', body)


class ManualPaymentEndsOnTheReceiptTests(BillingFixtureMixin, TestCase):
    """/payments/add/ is the other way a collection happens, and it prints too."""

    def setUp(self):
        super().setUp()
        UserProfile.objects.create(user=self.collector, role='cashier')
        self.client.force_login(self.collector)

    def _payload(self):
        return {
            'tenant': self.tenant.pk, 'stall': self.stall.pk, 'billing': self.billing.pk,
            'billing_month': 1, 'billing_year': 2026,
            'rental_amount': '100.00', 'penalty_amount': '0.00', 'discount': '0.00',
            'total_amount_due': '100.00', 'amount_paid': '100.00',
            'payment_date': '2026-01-10', 'payment_method': 'Cash',
            'official_receipt_no': '', 'collected_by': self.collector.pk,
            'status': 'Paid', 'remarks': '',
        }

    def test_recording_a_payment_by_hand_ends_on_its_receipt(self):
        resp = self.client.post(reverse('payment_add'), self._payload())
        payment = Payment.objects.get()
        self.assertEqual(
            resp['Location'],
            reverse('payment_print_receipt', args=[payment.pk]) + '?auto=1&back=payments')
