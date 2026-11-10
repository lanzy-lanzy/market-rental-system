# core/test_collector_rbac.py
# A field collector records and collects payments — every administrative
# screen (billing generation, tenants, stalls, contracts, lookups, reports,
# ledger, notices, settings, users, audit) stays closed to that role.
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from core.helpers import record_payment
from core.models import Payment, UserProfile
from core.test_payment_service import BillingFixtureMixin
from core.views.payments import BATCH_RECEIPT_SESSION_KEY


class CollectorFixtureMixin(BillingFixtureMixin):
    """Billing fixture plus two distinct collector logins."""

    def setUp(self):
        super().setUp()
        self.collector.username = 'collector-one'
        self.collector.save(update_fields=['username'])
        UserProfile.objects.create(user=self.collector, role='collector')
        self.other = User.objects.create_user(username='collector-two', password='x')
        UserProfile.objects.create(user=self.other, role='collector')
        self.client.force_login(self.collector)

    def _payment(self, collected_by=None, amount='30.00'):
        with transaction.atomic():
            return record_payment(
                tenant=self.tenant, billing=self.billing, amount=Decimal(amount),
                payment_date='2026-01-10', payment_method='Cash',
                collected_by=collected_by or self.collector,
            )


class CollectorCannotAdministrateTests(CollectorFixtureMixin, TestCase):
    """Every management endpoint bounces the collector back to the dashboard."""

    def test_admin_screens_are_all_closed_to_a_collector(self):
        urls = [
            reverse('tenant_list'),
            reverse('tenant_add'),
            reverse('tenant_view', args=[self.tenant.pk]),
            reverse('tenant_bulk_delete'),
            reverse('stall_list'),
            reverse('stall_add'),
            reverse('contract_list'),
            reverse('contract_bulk_assign'),
            reverse('market_section_list'),
            reverse('stall_type_list'),
            reverse('report_dashboard'),
            reverse('report_collector'),
            reverse('ledger_list'),
            reverse('notice_list'),
            reverse('notice_add'),
            reverse('billing_generate'),
            reverse('billing_generate_all'),
            reverse('billing_add_modal'),
            reverse('payment_void', args=[1]),
            reverse('payment_edit_modal', args=[1]),
            reverse('settings_view'),
            reverse('settings_update'),
            reverse('user_list'),
            reverse('audit_log_list'),
        ]
        for url in urls:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302, url)
                self.assertEqual(resp['Location'], reverse('dashboard'), url)

    def test_the_denial_is_reported_to_the_collector(self):
        resp = self.client.get(reverse('billing_generate'), follow=True)
        messages = ' '.join(str(m) for m in resp.context['messages'])
        self.assertIn('do not have permission', messages)

    def test_generation_posts_cannot_be_smuggled_past_the_navigation(self):
        resp = self.client.post(reverse('billing_generate_all'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('dashboard'))

    def test_a_collector_still_holds_no_management_authority(self):
        from core.permissions import is_collector, is_management

        self.assertTrue(is_collector(self.collector))
        self.assertFalse(is_management(self.collector))
        self.assertFalse(is_management(self.other))


class CollectorCollectionWorkflowTests(CollectorFixtureMixin, TestCase):
    """The collection queue and its receipts remain fully usable."""

    def test_the_billing_queue_is_open(self):
        self.assertEqual(self.client.get(reverse('billing_list')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('billing_view', args=[self.billing.pk])).status_code, 200
        )

    def test_a_collection_can_be_recorded_and_lands_on_its_receipt(self):
        resp = self.client.post(reverse('billing_collect', args=[self.billing.pk]), {
            'amount_paid': '100.00', 'payment_method': 'Cash',
            'payment_date': '2026-01-10', 'remarks': '',
        })
        payment = Payment.objects.get()
        self.assertEqual(payment.collected_by, self.collector)
        self.assertEqual(
            resp['Location'],
            reverse('payment_print_receipt', args=[payment.pk]) + '?auto=1&back=billing',
        )

    def test_manual_payment_recording_is_open(self):
        self.assertEqual(self.client.get(reverse('payment_add')).status_code, 200)

    def test_the_collectors_own_receipt_can_be_viewed_and_reprinted(self):
        payment = self._payment()
        for name in ('payment_view', 'payment_receipt', 'payment_print_receipt'):
            with self.subTest(view=name):
                resp = self.client.get(reverse(name, args=[payment.pk]))
                self.assertEqual(resp.status_code, 200)
                self.assertIn(payment.receipt_number, resp.content.decode())

    def test_the_collector_dashboard_is_collection_focused(self):
        body = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('Collection Queue', body)
        self.assertIn('Collected Today', body)
        self.assertIn('My Receipts', body)

    def test_the_navigation_offers_no_administrative_destinations(self):
        body = self.client.get(reverse('dashboard')).content.decode()
        for admin_url in ('/tenants/', '/stalls/', '/contracts/', '/reports/',
                          '/ledger/', '/notices/', '/settings/', '/users/',
                          '/audit-logs/'):
            with self.subTest(url=admin_url):
                self.assertNotIn(f'href="{admin_url}', body)
        self.assertIn(f'href="{reverse("payment_list")}"', body)


class CollectorSeesOnlyOwnCollectionsTests(CollectorFixtureMixin, TestCase):
    """Receipts belong to the collector who recorded them."""

    def test_history_lists_only_the_collectors_own_receipts(self):
        mine = self._payment(amount='30.00')
        theirs = self._payment(collected_by=self.other, amount='40.00')
        body = self.client.get(reverse('payment_list')).content.decode()
        self.assertIn(mine.receipt_number, body)
        self.assertNotIn(theirs.receipt_number, body)

    def test_another_collectors_receipt_is_refused(self):
        theirs = self._payment(collected_by=self.other)
        for name in ('payment_view', 'payment_receipt', 'payment_print_receipt',
                     'payment_receipt_export_pdf'):
            with self.subTest(view=name):
                resp = self.client.get(reverse(name, args=[theirs.pk]))
                self.assertEqual(resp.status_code, 302)
                self.assertEqual(resp['Location'], reverse('payment_list'))

    def test_the_receipt_list_printout_is_scoped_too(self):
        mine = self._payment(amount='30.00')
        theirs = self._payment(collected_by=self.other, amount='40.00')
        body = self.client.get(reverse('payment_list_print')).content.decode()
        self.assertIn(mine.receipt_number, body)
        self.assertNotIn(theirs.receipt_number, body)

    def test_a_batch_containing_someone_elses_receipt_is_refused(self):
        mine = self._payment(amount='30.00')
        theirs = self._payment(collected_by=self.other, amount='40.00')
        session = self.client.session
        session[BATCH_RECEIPT_SESSION_KEY] = [mine.pk, theirs.pk]
        session.save()
        resp = self.client.get(reverse('payment_batch_receipt'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('payment_list'))
