from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Billing, MarketSection, Payment, RentalContract, Stall, StallType,
    SystemSetting, Tenant, UserProfile,
)


class BillingCollectionSheetTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Market Administration Office',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.collector = User.objects.create_user(
            username='field_collector', password='Collector!Pass123',
            first_name='Juan', last_name='Collector',
        )
        UserProfile.objects.create(user=self.collector, role='collector')

        self.other_collector = User.objects.create_user(
            username='other_collector', password='Collector!Pass123',
        )
        UserProfile.objects.create(user=self.other_collector, role='collector')

        self.admin = User.objects.create_user(username='admin_cs', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')

        self.tenant_user = User.objects.create_user(username='tenant_cs', password='Tenant!Pass123')
        UserProfile.objects.create(user=self.tenant_user, role='tenant')

        self.dry_goods = MarketSection.objects.create(name='Dry Goods')
        self.wet_market = MarketSection.objects.create(name='Wet Market')
        self.stall_type = StallType.objects.create(name='Regular Stall')

        # Intentionally create stalls out of route order to verify route sorting
        self.stall_wm_01 = Stall.objects.create(
            stall_number='WM-01', section=self.wet_market, stall_type=self.stall_type,
            monthly_rate=Decimal('1200.00'), status='Occupied',
        )
        self.stall_dg_02 = Stall.objects.create(
            stall_number='DG-02', section=self.dry_goods, stall_type=self.stall_type,
            monthly_rate=Decimal('1500.00'), status='Occupied',
        )
        self.stall_dg_01 = Stall.objects.create(
            stall_number='DG-01', section=self.dry_goods, stall_type=self.stall_type,
            monthly_rate=Decimal('1000.00'), status='Occupied',
        )

        self.tenant_a = Tenant.objects.create(
            tenant_id='TNT-A', full_name='Ana Santos',
            address='Poblacion', contact_number='09171110001',
            user=self.tenant_user,
        )
        self.tenant_b = Tenant.objects.create(
            tenant_id='TNT-B', full_name='Ben Reyes',
            address='San Jose', contact_number='09171110002',
        )
        self.tenant_c = Tenant.objects.create(
            tenant_id='TNT-C', full_name='Cora Lim',
            address='San Pedro', contact_number='09171110003',
        )

        self.contract_a = RentalContract.objects.create(
            tenant=self.tenant_a, stall=self.stall_dg_01,
            start_date=date(2025, 1, 1), monthly_rent=Decimal('1000.00'), status='Active',
        )
        self.contract_b = RentalContract.objects.create(
            tenant=self.tenant_b, stall=self.stall_dg_02,
            start_date=date(2025, 1, 1), monthly_rent=Decimal('1500.00'), status='Active',
        )
        self.contract_c = RentalContract.objects.create(
            tenant=self.tenant_c, stall=self.stall_wm_01,
            start_date=date(2025, 1, 1), monthly_rent=Decimal('1200.00'), status='Active',
        )

        # DG-01 (Ana): 1 Overdue + 1 Unpaid + 1 Paid (Paid must be excluded)
        self.bill_a_paid = Billing.objects.create(
            tenant=self.tenant_a, stall=self.stall_dg_01, contract=self.contract_a,
            billing_month=1, billing_year=2026,
            rental_amount=Decimal('1000.00'), penalty_amount=Decimal('0.00'),
            total_due=Decimal('1000.00'), amount_paid=Decimal('1000.00'),
            balance=Decimal('0.00'), due_date=date(2026, 1, 5), status='Paid',
        )
        self.bill_a_overdue = Billing.objects.create(
            tenant=self.tenant_a, stall=self.stall_dg_01, contract=self.contract_a,
            billing_month=2, billing_year=2026,
            rental_amount=Decimal('1000.00'), penalty_amount=Decimal('100.00'),
            total_due=Decimal('1100.00'), amount_paid=Decimal('0.00'),
            balance=Decimal('1100.00'), due_date=date(2026, 2, 5), status='Overdue',
        )
        self.bill_a_unpaid = Billing.objects.create(
            tenant=self.tenant_a, stall=self.stall_dg_01, contract=self.contract_a,
            billing_month=3, billing_year=2026,
            rental_amount=Decimal('1000.00'), penalty_amount=Decimal('0.00'),
            total_due=Decimal('1000.00'), amount_paid=Decimal('0.00'),
            balance=Decimal('1000.00'), due_date=date(2026, 3, 5), status='Unpaid',
        )

        # DG-02 (Ben): 1 Partial
        self.bill_b_partial = Billing.objects.create(
            tenant=self.tenant_b, stall=self.stall_dg_02, contract=self.contract_b,
            billing_month=3, billing_year=2026,
            rental_amount=Decimal('1500.00'), penalty_amount=Decimal('50.00'),
            total_due=Decimal('1550.00'), amount_paid=Decimal('550.00'),
            balance=Decimal('1000.00'), due_date=date(2026, 3, 5), status='Partial',
        )

        # WM-01 (Cora): 1 Unpaid
        self.bill_c_unpaid = Billing.objects.create(
            tenant=self.tenant_c, stall=self.stall_wm_01, contract=self.contract_c,
            billing_month=3, billing_year=2026,
            rental_amount=Decimal('1200.00'), penalty_amount=Decimal('0.00'),
            total_due=Decimal('1200.00'), amount_paid=Decimal('0.00'),
            balance=Decimal('1200.00'), due_date=date(2026, 3, 5), status='Unpaid',
        )

        self.client.force_login(self.collector)

    def test_route_ordering_and_aggregates_exclude_paid(self):
        resp = self.client.get(reverse('billing_collection_sheet'))
        self.assertEqual(resp.status_code, 200)
        rows = resp.context['rows']
        # Sorted strictly by Section then Stall Number: DG-01, DG-02, WM-01
        self.assertEqual(
            [(r['section'].name, r['stall'].stall_number) for r in rows],
            [('Dry Goods', 'DG-01'), ('Dry Goods', 'DG-02'), ('Wet Market', 'WM-01')],
        )
        # DG-01 should aggregate only the 2 unpaid/overdue months (excluding Paid)
        dg01 = rows[0]
        self.assertEqual(dg01['unpaid_months'], 2)
        self.assertEqual(dg01['rent_due'], Decimal('2000.00'))
        self.assertEqual(dg01['penalty_due'], Decimal('100.00'))
        self.assertEqual(dg01['total_balance'], Decimal('2100.00'))
        self.assertEqual(dg01['status'], 'Overdue')

        html = resp.content.decode()
        self.assertIn(reverse('billing_tenant_collect', args=[self.tenant_a.id]), html)
        self.assertIn(reverse('billing_tenant_soa', args=[self.tenant_a.id]), html)

    def test_filter_by_section_status_and_search(self):
        resp_sec = self.client.get(
            reverse('billing_collection_sheet'), {'section': self.wet_market.pk},
        )
        self.assertEqual(
            [r['stall'].stall_number for r in resp_sec.context['rows']], ['WM-01'],
        )

        resp_overdue = self.client.get(
            reverse('billing_collection_sheet'), {'status': 'overdue'},
        )
        self.assertEqual(
            [r['stall'].stall_number for r in resp_overdue.context['rows']], ['DG-01'],
        )

        resp_partial = self.client.get(
            reverse('billing_collection_sheet'), {'status': 'Partial'},
        )
        self.assertEqual(
            [r['stall'].stall_number for r in resp_partial.context['rows']], ['DG-02'],
        )

        resp_search = self.client.get(
            reverse('billing_collection_sheet'), {'search': 'Cora'},
        )
        self.assertEqual(
            [r['stall'].stall_number for r in resp_search.context['rows']], ['WM-01'],
        )

    def test_collected_today_kpi_banner_scoped_to_logged_in_collector(self):
        today = timezone.localdate()
        Payment.objects.create(
            receipt_number='OR-TODAY-1', tenant=self.tenant_a, stall=self.stall_dg_01,
            billing=self.bill_a_paid, billing_month=1, billing_year=2026,
            rental_amount=Decimal('1000.00'), total_amount_due=Decimal('1000.00'),
            amount_paid=Decimal('1000.00'), payment_date=today,
            collected_by=self.collector, status='Paid',
        )
        # Void payment should not be counted
        Payment.objects.create(
            receipt_number='OR-TODAY-VOID', tenant=self.tenant_b, stall=self.stall_dg_02,
            billing=self.bill_b_partial, billing_month=3, billing_year=2026,
            rental_amount=Decimal('1500.00'), total_amount_due=Decimal('1550.00'),
            amount_paid=Decimal('500.00'), payment_date=today,
            collected_by=self.collector, status='Void',
        )
        # Another collector's payment should not be counted
        Payment.objects.create(
            receipt_number='OR-TODAY-OTHER', tenant=self.tenant_b, stall=self.stall_dg_02,
            billing=self.bill_b_partial, billing_month=3, billing_year=2026,
            rental_amount=Decimal('1500.00'), total_amount_due=Decimal('1550.00'),
            amount_paid=Decimal('550.00'), payment_date=today,
            collected_by=self.other_collector, status='Partial',
        )

        resp = self.client.get(reverse('billing_collection_sheet'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['collected_today_count'], 1)
        self.assertEqual(resp.context['collected_today_total'], Decimal('1000.00'))
        html = resp.content.decode()
        self.assertIn('Collected Today', html)
        self.assertIn('1,000.00', html)

    def test_htmx_partial_reload_and_oob_print_link(self):
        resp = self.client.get(
            reverse('billing_collection_sheet'),
            {'section': self.dry_goods.pk, 'status': 'Overdue'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn('<!DOCTYPE html>', html)
        self.assertIn('id="collection-sheet-content"', html)
        self.assertIn('DG-01', html)
        self.assertNotIn('WM-01', html)
        self.assertIn('hx-swap-oob="true"', html)
        self.assertIn('status=Overdue', html)

    def test_rbac_and_sidebar_nav(self):
        # Collector has access and sees Collection Sheet in sidebar
        resp = self.client.get(reverse('billing_collection_sheet'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nav-sub-link is-active">Collection Sheet<', resp.content.decode())

        # Admin also has access
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('billing_collection_sheet')).status_code, 200)

        # Tenant is blocked
        self.client.force_login(self.tenant_user)
        resp_t = self.client.get(reverse('billing_collection_sheet'))
        self.assertEqual(resp_t.status_code, 302)

    def test_print_collection_sheet_has_field_columns_and_filters(self):
        resp = self.client.get(
            reverse('billing_collection_sheet_print'),
            {'section': self.dry_goods.pk},
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Field Collection Sheet', html)
        self.assertIn('Dry Goods', html)
        self.assertIn('Amount Paid', html)
        self.assertIn('OR #', html)
        self.assertIn('Signature', html)
        self.assertIn('DG-01', html)
        self.assertIn('DG-02', html)
        self.assertNotIn('WM-01', html)


class TenantStatementOfAccountTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Market Administration Office',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.collector = User.objects.create_user(username='soa_collector', password='Collector!Pass123')
        UserProfile.objects.create(user=self.collector, role='collector')

        self.tenant_user = User.objects.create_user(username='soa_tenant', password='Tenant!Pass123')
        UserProfile.objects.create(user=self.tenant_user, role='tenant')

        self.other_tenant_user = User.objects.create_user(username='soa_other_tenant', password='Tenant!Pass123')
        UserProfile.objects.create(user=self.other_tenant_user, role='tenant')

        self.section = MarketSection.objects.create(name='Dry Goods')
        self.stall_type = StallType.objects.create(name='Corner Stall')
        self.stall = Stall.objects.create(
            stall_number='DG-101', section=self.section, stall_type=self.stall_type,
            monthly_rate=Decimal('1500.00'), status='Occupied',
        )

        self.tenant = Tenant.objects.create(
            tenant_id='TNT-SOA-1', full_name='Elena Mendoza',
            business_name='Elena Dry Goods', address='Poblacion',
            contact_number='09179990001', user=self.tenant_user,
        )
        self.other_tenant = Tenant.objects.create(
            tenant_id='TNT-SOA-2', full_name='Mario Cruz',
            address='Poblacion', contact_number='09179990002',
            user=self.other_tenant_user,
        )

        self.contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.stall,
            start_date=date(2025, 1, 1), monthly_rent=Decimal('1500.00'), status='Active',
        )

        # Paid month (excluded from SOA outstanding list)
        Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=1, billing_year=2026,
            rental_amount=Decimal('1500.00'), penalty_amount=Decimal('0.00'),
            total_due=Decimal('1500.00'), amount_paid=Decimal('1500.00'),
            balance=Decimal('0.00'), due_date=date(2026, 1, 5), status='Paid',
        )
        # Overdue month
        Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=2, billing_year=2026,
            rental_amount=Decimal('1500.00'), penalty_amount=Decimal('150.00'),
            total_due=Decimal('1650.00'), amount_paid=Decimal('0.00'),
            balance=Decimal('1650.00'), due_date=date(2026, 2, 5), status='Overdue',
        )
        # Partial month
        Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=3, billing_year=2026,
            rental_amount=Decimal('1500.00'), penalty_amount=Decimal('0.00'),
            total_due=Decimal('1500.00'), amount_paid=Decimal('500.00'),
            balance=Decimal('1000.00'), due_date=date(2026, 3, 5), status='Partial',
        )

    def test_soa_renders_official_header_itemized_billings_and_grand_total(self):
        self.client.force_login(self.collector)
        resp = self.client.get(reverse('billing_tenant_soa', args=[self.tenant.id]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        self.assertIn('Statement of Account (SOA)', html)
        self.assertIn('Dumingag', html)
        self.assertIn('Dumingag Public Market', html)
        self.assertIn('Elena Mendoza', html)
        self.assertIn('DG-101', html)
        self.assertIn('Feb 2026', html)
        self.assertIn('Mar 2026', html)
        self.assertNotIn('Jan 2026', html)

        totals = resp.context['soa_totals']
        self.assertEqual(totals['item_count'], 2)
        self.assertEqual(totals['overdue_count'], 1)
        self.assertEqual(totals['total_rent'], Decimal('3000.00'))
        self.assertEqual(totals['total_penalty'], Decimal('150.00'))
        self.assertEqual(totals['total_paid'], Decimal('500.00'))
        self.assertEqual(totals['grand_total_due'], Decimal('2650.00'))
        self.assertIn('2,650.00', html)

    def test_soa_for_settled_tenant(self):
        self.client.force_login(self.collector)
        resp = self.client.get(reverse('billing_tenant_soa', args=[self.other_tenant.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['soa_totals']['grand_total_due'], Decimal('0.00'))
        self.assertIn('No outstanding balance', resp.content.decode())

    def test_soa_tenant_isolation(self):
        # Own tenant can view own SOA
        self.client.force_login(self.tenant_user)
        resp_own = self.client.get(reverse('billing_tenant_soa', args=[self.tenant.id]))
        self.assertEqual(resp_own.status_code, 200)

        # Other tenant is blocked from viewing Elena's SOA
        self.client.force_login(self.other_tenant_user)
        resp_other = self.client.get(reverse('billing_tenant_soa', args=[self.tenant.id]))
        self.assertEqual(resp_other.status_code, 302)
