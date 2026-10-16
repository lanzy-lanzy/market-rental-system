"""Regression tests for the tenant bulk-delete endpoint.

Two bugs originally made the operation silently fail:

1. ``tenant_bulk_delete`` unconditionally called ``select_for_update()``,
   which raises ``NotSupportedError`` on SQLite — every POST returned 500
   and no tenant changed. The view must now feature-gate the lock.
2. The view soft-terminated instead of deleting, so "the selected tenants
   remain in the system" persisted. It now hard-deletes when safe and
   refuses when real payment history is present.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    AuditLog, Billing, MarketSection, Payment, RentalContract, Stall,
    SystemSetting, Tenant, TenantLedger, UserProfile,
)


class TenantBulkDeleteTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.section = MarketSection.objects.create(name='A')
        self._stall_seq = 0

        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    # --- helpers --------------------------------------------------------

    def _new_stall(self):
        """One stall per tenant: RentalContract enforces a UNIQUE
        (stall, status) pair, so reusing a single stall across fixtures
        would collide on the second Active contract."""
        self._stall_seq += 1
        return Stall.objects.create(
            stall_number=f'BD-{self._stall_seq:02d}', section=self.section,
            monthly_rate=Decimal('150.00'), status='Occupied',
        )

    def _make_tenant(self, tenant_id, full_name, *, with_user=False,
                     with_billing=False, with_payment=False):
        user = None
        if with_user:
            user = User.objects.create_user(username=f'u_{tenant_id}', password='x')
            UserProfile.objects.create(user=user, role='tenant')
        tenant = Tenant.objects.create(
            tenant_id=tenant_id, full_name=full_name, address='Zamboanga',
            contact_number='0900', status='Active', user=user,
        )
        stall = self._new_stall()
        contract = RentalContract.objects.create(
            tenant=tenant, stall=stall, start_date=date(2026, 1, 1),
            monthly_rent=Decimal('150.00'), due_day=5, status='Active',
        )
        billing = None
        if with_billing or with_payment:
            billing = Billing.objects.create(
                tenant=tenant, stall=stall, contract=contract,
                billing_month=1, billing_year=2026,
                rental_amount=Decimal('150.00'), penalty_amount=Decimal('0.00'),
                discount=Decimal('0.00'), total_due=Decimal('150.00'),
                amount_paid=Decimal('150.00' if with_payment else '0.00'),
                balance=Decimal('0.00' if with_payment else '150.00'),
                due_date=date(2026, 1, 5),
                status='Paid' if with_payment else 'Unpaid',
            )
            TenantLedger.objects.create(
                tenant=tenant, billing=billing,
                transaction_date=date(2026, 1, 5), description='billing',
                debit=Decimal('150.00'), credit=Decimal('0.00'),
                balance=Decimal('150.00'),
            )
        if with_payment:
            collector = User.objects.create_user(
                username=f'coll_{tenant_id}', password='x'
            )
            UserProfile.objects.create(user=collector, role='collector')
            Payment.objects.create(
                receipt_number=f'RCP-BD-{tenant_id}', tenant=tenant,
                stall=stall, billing=billing,
                billing_month=1, billing_year=2026,
                rental_amount=Decimal('150.00'), penalty_amount=Decimal('0.00'),
                discount=Decimal('0.00'), total_amount_due=Decimal('150.00'),
                amount_paid=Decimal('150.00'), payment_date=date(2026, 1, 10),
                payment_method='Cash', collected_by=collector, status='Paid',
            )
        return tenant

    def _bulk_post(self, tenants, *, follow=True):
        data = {'selected_tenants': [str(t.pk) for t in tenants]}
        return self.client.post(
            reverse('tenant_bulk_delete'), data, follow=follow
        )

    # --- tests ----------------------------------------------------------

    def test_get_redirects_to_list(self):
        resp = self.client.get(reverse('tenant_bulk_delete'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('tenant_list'))

    def test_empty_selection_warns(self):
        resp = self.client.post(
            reverse('tenant_bulk_delete'), {'selected_tenants': []}, follow=True
        )
        messages = [m.message for m in resp.context['messages']]
        self.assertTrue(any('No tenants were selected' in m for m in messages), messages)

    def test_non_admin_is_blocked(self):
        """@admin_required bounces a collector POST before the view body runs."""
        coll = User.objects.create_user(username='coll2', password='x')
        UserProfile.objects.create(user=coll, role='collector')
        self.client.force_login(coll)
        tenant = self._make_tenant('TEN-B1', 'Juan Dela Cruz')
        resp = self.client.post(reverse('tenant_bulk_delete'), {
            'selected_tenants': [str(tenant.pk)],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('dashboard'))
        # Tenant must still exist because the view never ran.
        self.assertTrue(Tenant.objects.filter(pk=tenant.pk).exists())

    def test_hard_deletes_clean_tenants_on_sqlite(self):
        """The core regression: SQLite used to raise NotSupportedError."""
        t1 = self._make_tenant('TEN-B2', 'Maria Claw', with_user=True)
        t2 = self._make_tenant('TEN-B3', 'Pedro Rock', with_user=True)
        linked_user_ids = [t1.user_id, t2.user_id]

        resp = self._bulk_post([t1, t2])

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.redirect_chain[0][0], reverse('tenant_list'))
        # Both tenant rows and their portal User rows are gone.
        self.assertFalse(Tenant.objects.filter(pk__in=[t1.pk, t2.pk]).exists())
        self.assertFalse(User.objects.filter(pk__in=linked_user_ids).exists())

        messages = [m.message for m in resp.context['messages']]
        self.assertTrue(any('Deleted 2 tenant' in m for m in messages), messages)

        log = AuditLog.objects.filter(action='DELETE', module='Tenant').latest('id')
        self.assertIn('Bulk delete', log.description)
        self.assertIn('Maria Claw', log.description)
        self.assertIn('Pedro Rock', log.description)

    def test_cascades_contracts_billings_ledger(self):
        """on_delete=CASCADE cleans up dependents of a deleted tenant."""
        tenant = self._make_tenant('TEN-B4', 'Ana Empty', with_billing=True)
        billing_ids = list(Billing.objects.filter(tenant=tenant).values_list('id', flat=True))
        contract_ids = list(RentalContract.objects.filter(tenant=tenant).values_list('id', flat=True))
        ledger_ids = list(TenantLedger.objects.filter(tenant=tenant).values_list('id', flat=True))
        self.assertTrue(billing_ids and contract_ids and ledger_ids)

        self._bulk_post([tenant])

        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())
        self.assertFalse(Billing.objects.filter(id__in=billing_ids).exists())
        self.assertFalse(RentalContract.objects.filter(id__in=contract_ids).exists())
        self.assertFalse(TenantLedger.objects.filter(id__in=ledger_ids).exists())

    def test_refuses_tenants_with_payment_history(self):
        clean = self._make_tenant('TEN-B5', 'Fresh Fran')
        paid = self._make_tenant('TEN-B6', 'Paid Paula', with_payment=True)

        resp = self._bulk_post([clean, paid])

        self.assertFalse(Tenant.objects.filter(pk=clean.pk).exists())
        self.assertTrue(Tenant.objects.filter(pk=paid.pk).exists())
        # Payments stay intact so the audit trail is not silently wiped.
        self.assertTrue(Payment.objects.filter(tenant=paid).exists())

        messages = [m.message for m in resp.context['messages']]
        self.assertTrue(any('Deleted 1 tenant' in m for m in messages), messages)
        self.assertTrue(
            any('were NOT deleted because they have payment history' in m for m in messages),
            messages,
        )

    def test_missing_ids_are_reported(self):
        tenant = self._make_tenant('TEN-B7', 'Real Rita')
        ghost_pk = tenant.pk + 10_000
        self.assertFalse(Tenant.objects.filter(pk=ghost_pk).exists())

        resp = self.client.post(reverse('tenant_bulk_delete'), {
            'selected_tenants': [str(tenant.pk), str(ghost_pk)],
        }, follow=True)

        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())
        messages = [m.message for m in resp.context['messages']]
        self.assertTrue(any('no longer exist' in m for m in messages), messages)

    def test_duplicate_ids_are_de_duplicated(self):
        tenant = self._make_tenant('TEN-B8', 'Solo Sam')
        resp = self.client.post(reverse('tenant_bulk_delete'), {
            'selected_tenants': [str(tenant.pk), str(tenant.pk), str(tenant.pk)],
        }, follow=True)
        self.assertFalse(Tenant.objects.filter(pk=tenant.pk).exists())
        # Exactly one "Deleted 1 tenant" message, not three.
        messages = [m.message for m in resp.context['messages']]
        self.assertTrue(any('Deleted 1 tenant' in m for m in messages), messages)
        deleted_logs = AuditLog.objects.filter(action='DELETE', module='Tenant')
        self.assertEqual(deleted_logs.count(), 1)
