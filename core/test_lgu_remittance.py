"""Tests for LGU Feature 5: End-of-Day Collector Remittance / Abstract of Collection (AF 51)."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Billing, MarketSection, Payment, RentalContract, Stall, StallType,
    SystemSetting, Tenant, UserProfile,
)


class CollectorRemittanceTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Office of the Market Administrator',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.admin = User.objects.create_user(
            username='remadmin', password='Password!123',
            first_name='Alice', last_name='Admin',
        )
        UserProfile.objects.create(user=self.admin, role='admin')

        self.treasurer = User.objects.create_user(
            username='remtreasurer', password='Password!123',
            first_name='Tessa', last_name='Treasurer',
        )
        UserProfile.objects.create(user=self.treasurer, role='treasurer')

        self.collector1 = User.objects.create_user(
            username='col1', password='Password!123',
            first_name='Carlos', last_name='Collector',
        )
        UserProfile.objects.create(user=self.collector1, role='collector')

        self.collector2 = User.objects.create_user(
            username='col2', password='Password!123',
            first_name='Belen', last_name='Collector',
        )
        UserProfile.objects.create(user=self.collector2, role='collector')

        self.tenant_user = User.objects.create_user(
            username='remtenant', password='Password!123',
            first_name='Juan', last_name='Tenant',
        )
        UserProfile.objects.create(user=self.tenant_user, role='tenant')

        self.section = MarketSection.objects.create(name='Dry Goods')
        self.stall_type = StallType.objects.create(name='Regular')
        self.tenant1 = Tenant.objects.create(
            tenant_id='T-101', first_name='Juan', last_name='Dela Cruz',
            full_name='Juan Dela Cruz', barangay='Poblacion', contact_number='09000000101',
        )
        self.tenant2 = Tenant.objects.create(
            tenant_id='T-102', first_name='Maria', last_name='Santos',
            full_name='Maria Santos', barangay='Poblacion', contact_number='09000000102',
        )
        self.stall1 = Stall.objects.create(
            stall_number='DG-01', section=self.section, stall_type=self.stall_type,
            monthly_rate=Decimal('1000.00'), status='Occupied',
        )
        self.stall2 = Stall.objects.create(
            stall_number='DG-02', section=self.section, stall_type=self.stall_type,
            monthly_rate=Decimal('800.00'), status='Occupied',
        )
        self.remit_date = date(2026, 11, 24)
        self.other_date = date(2026, 11, 23)

        self.contract1 = RentalContract.objects.create(
            tenant=self.tenant1, stall=self.stall1, monthly_rent=Decimal('1000.00'),
            start_date=date(2026, 1, 1), end_date=date(2029, 1, 1), status='Active',
        )
        self.contract2 = RentalContract.objects.create(
            tenant=self.tenant2, stall=self.stall2, monthly_rent=Decimal('800.00'),
            start_date=date(2026, 1, 1), end_date=date(2029, 1, 1), status='Active',
        )
        self.billing1 = Billing.objects.create(
            tenant=self.tenant1, stall=self.stall1, contract=self.contract1,
            billing_month=11, billing_year=2026,
            rental_amount=Decimal('1000.00'), penalty_amount=Decimal('100.00'),
            total_due=Decimal('1100.00'), amount_paid=Decimal('1100.00'),
            balance=Decimal('0.00'), due_date=date(2026, 11, 5), status='Paid',
        )
        self.billing2 = Billing.objects.create(
            tenant=self.tenant2, stall=self.stall2, contract=self.contract2,
            billing_month=11, billing_year=2026,
            rental_amount=Decimal('800.00'), penalty_amount=Decimal('200.00'),
            total_due=Decimal('1000.00'), amount_paid=Decimal('500.00'),
            balance=Decimal('500.00'), due_date=date(2026, 11, 5), status='Partial',
        )
        self.billing3 = Billing.objects.create(
            tenant=self.tenant2, stall=self.stall2, contract=self.contract2,
            billing_month=10, billing_year=2026,
            rental_amount=Decimal('800.00'), penalty_amount=Decimal('0.00'),
            total_due=Decimal('800.00'), amount_paid=Decimal('800.00'),
            balance=Decimal('0.00'), due_date=date(2026, 10, 5), status='Paid',
        )

        # Collector 1: Full payment with penalty (Cash) -> Rent 1000.00, Penalty 100.00
        self.p1 = Payment.objects.create(
            receipt_number='DMPM-0001',
            official_receipt_no='OR-2026-0001',
            tenant=self.tenant1, stall=self.stall1, billing=self.billing1,
            billing_month=11, billing_year=2026,
            rental_amount=Decimal('1000.00'), penalty_amount=Decimal('100.00'),
            total_amount_due=Decimal('1100.00'), amount_paid=Decimal('1100.00'),
            payment_date=self.remit_date, payment_method='Cash',
            collected_by=self.collector1, status='Paid',
        )
        # Collector 1: Partial payment (50% of 800 rent + 200 penalty) via GCash -> Rent 400.00, Penalty 100.00
        self.p2 = Payment.objects.create(
            receipt_number='DMPM-0002',
            official_receipt_no='OR-2026-0002',
            tenant=self.tenant2, stall=self.stall2, billing=self.billing2,
            billing_month=11, billing_year=2026,
            rental_amount=Decimal('800.00'), penalty_amount=Decimal('200.00'),
            total_amount_due=Decimal('1000.00'), amount_paid=Decimal('500.00'),
            payment_date=self.remit_date, payment_method='GCash',
            collected_by=self.collector1, status='Partial',
        )
        # Collector 2: Full payment without penalty (Cash) -> Rent 800.00, Penalty 0.00
        self.p3 = Payment.objects.create(
            receipt_number='DMPM-0003',
            official_receipt_no='OR-2026-0003',
            tenant=self.tenant2, stall=self.stall2, billing=self.billing3,
            billing_month=10, billing_year=2026,
            rental_amount=Decimal('800.00'), penalty_amount=Decimal('0.00'),
            total_amount_due=Decimal('800.00'), amount_paid=Decimal('800.00'),
            payment_date=self.remit_date, payment_method='Cash',
            collected_by=self.collector2, status='Paid',
        )
        # Void payment on same date (must be excluded!)
        self.p_void = Payment.objects.create(
            receipt_number='DMPM-0004',
            official_receipt_no='OR-2026-0004',
            tenant=self.tenant1, stall=self.stall1, billing=self.billing1,
            billing_month=11, billing_year=2026,
            rental_amount=Decimal('1000.00'), penalty_amount=Decimal('0.00'),
            total_amount_due=Decimal('1000.00'), amount_paid=Decimal('1000.00'),
            payment_date=self.remit_date, payment_method='Cash',
            collected_by=self.collector1, status='Void',
        )
        # Payment on another date (must be excluded when filtering remit_date)
        self.p_other = Payment.objects.create(
            receipt_number='DMPM-0000',
            official_receipt_no='OR-2026-0000',
            tenant=self.tenant1, stall=self.stall1, billing=self.billing1,
            billing_month=11, billing_year=2026,
            rental_amount=Decimal('500.00'), penalty_amount=Decimal('0.00'),
            total_amount_due=Decimal('500.00'), amount_paid=Decimal('500.00'),
            payment_date=self.other_date, payment_method='Cash',
            collected_by=self.collector1, status='Paid',
        )

    def test_admin_sees_all_collectors_and_accurate_totals(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('report_remittance'), {'date': self.remit_date.isoformat()})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['collector_locked'])
        self.assertEqual(resp.context['transaction_count'], 3)
        self.assertEqual(resp.context['or_series_start'], 'OR-2026-0001')
        self.assertEqual(resp.context['or_series_end'], 'OR-2026-0003')
        # Rent: 1000 + 400 + 800 = 2200; Penalty: 100 + 100 + 0 = 200; Grand Total: 2400
        self.assertEqual(resp.context['total_rent'], Decimal('2200.00'))
        self.assertEqual(resp.context['total_penalty'], Decimal('200.00'))
        self.assertEqual(resp.context['grand_total'], Decimal('2400.00'))
        self.assertEqual(
            resp.context['total_rent'] + resp.context['total_penalty'],
            resp.context['grand_total'],
        )
        methods = {m['key']: m for m in resp.context['payment_method_breakdown']}
        self.assertEqual(methods['Cash']['count'], 2)
        self.assertEqual(methods['Cash']['amount_total'], Decimal('1900.00'))
        self.assertEqual(methods['GCash']['count'], 1)
        self.assertEqual(methods['GCash']['amount_total'], Decimal('500.00'))

    def test_treasurer_can_filter_by_specific_collector(self):
        self.client.force_login(self.treasurer)
        resp = self.client.get(
            reverse('report_remittance'),
            {'date': self.remit_date.isoformat(), 'collector': str(self.collector1.pk)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['transaction_count'], 2)
        self.assertEqual(resp.context['or_series_start'], 'OR-2026-0001')
        self.assertEqual(resp.context['or_series_end'], 'OR-2026-0002')
        self.assertEqual(resp.context['total_rent'], Decimal('1400.00'))
        self.assertEqual(resp.context['total_penalty'], Decimal('200.00'))
        self.assertEqual(resp.context['grand_total'], Decimal('1600.00'))

    def test_collector_is_locked_to_own_remittances_even_if_passing_other_collector_param(self):
        self.client.force_login(self.collector1)
        resp = self.client.get(
            reverse('report_remittance'),
            {'date': self.remit_date.isoformat(), 'collector': str(self.collector2.pk)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['collector_locked'])
        self.assertEqual(resp.context['selected_collector'], self.collector1)
        self.assertEqual(resp.context['transaction_count'], 2)
        self.assertEqual(resp.context['grand_total'], Decimal('1600.00'))
        body = resp.content.decode('utf-8')
        self.assertIn('OR-2026-0001', body)
        self.assertNotIn('OR-2026-0003', body)

    def test_print_remittance_slip_renders_branding_or_series_and_signatures(self):
        self.client.force_login(self.collector1)
        resp = self.client.get(
            reverse('report_remittance_print'),
            {'date': self.remit_date.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('Dumingag Public Market', body)
        self.assertIn('Abstract of Collection', body)
        self.assertIn('AF 51', body)
        self.assertIn('OR-2026-0001', body)
        self.assertIn('OR-2026-0002', body)
        self.assertIn('Prepared / Remitted By: Collector', body)
        self.assertIn('Verified / Received By: Municipal/Market Treasurer', body)
        self.assertIn('1,600.00', body)

    def test_tenant_cannot_access_remittance_views(self):
        self.client.force_login(self.tenant_user)
        for name in ('report_remittance', 'report_remittance_print'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302)

    def test_reports_dashboard_links_to_remittance(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('report_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('report_remittance'))
        self.assertContains(resp, 'Daily Remittance / AF 51')
