from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Billing, MarketSection, RentalContract, Stall, StallType,
    SystemSetting, Tenant, UserProfile,
)


class StallSearchStatusFilterTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Market Administration Office',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.admin = User.objects.create_user(username='admin_stalls', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

        self.dry_goods = MarketSection.objects.create(name='Dry Goods')
        self.wet_market = MarketSection.objects.create(name='Wet Market')
        self.regular_type = StallType.objects.create(name='Regular Stall')

        self.vacant_stall = Stall.objects.create(
            stall_number='DG-001',
            section=self.dry_goods,
            stall_type=self.regular_type,
            size=Decimal('6.00'),
            monthly_rate=Decimal('1500.00'),
            status='Vacant',
        )
        self.occupied_stall = Stall.objects.create(
            stall_number='DG-002',
            section=self.dry_goods,
            stall_type=self.regular_type,
            size=Decimal('8.00'),
            monthly_rate=Decimal('2000.00'),
            status='Occupied',
        )
        self.reserved_stall = Stall.objects.create(
            stall_number='WM-001',
            section=self.wet_market,
            stall_type=self.regular_type,
            size=Decimal('5.00'),
            monthly_rate=Decimal('1200.00'),
            status='Reserved',
        )

        self.tenant = Tenant.objects.create(
            tenant_id='TNT-001',
            full_name='Maria Santos',
            address='Poblacion',
            contact_number='09171234567',
        )
        RentalContract.objects.create(
            tenant=self.tenant,
            stall=self.occupied_stall,
            start_date=date(2025, 1, 1),
            monthly_rent=Decimal('2000.00'),
            status='Active',
        )

    def test_list_renders_vacant_and_occupied_options(self):
        resp = self.client.get(reverse('stall_list'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('value="Vacant"', html)
        self.assertIn('value="Occupied"', html)
        self.assertIn('>Vacant<', html)
        self.assertIn('>Occupied<', html)
        self.assertIn('DG-001', html)
        self.assertIn('DG-002', html)
        self.assertIn('WM-001', html)

    def test_filter_status_vacant_exact_and_lowercase(self):
        for param in ('Vacant', 'vacant'):
            resp = self.client.get(reverse('stall_list'), {'status': param})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context['status_filter'], 'Vacant')
            stalls = list(resp.context['page_obj'])
            self.assertEqual(stalls, [self.vacant_stall])
            html = resp.content.decode()
            self.assertIn('DG-001', html)
            self.assertNotIn('DG-002', html)
            self.assertNotIn('WM-001', html)

    def test_filter_status_occupied_exact_and_lowercase(self):
        for param in ('Occupied', 'occupied'):
            resp = self.client.get(reverse('stall_list'), {'status': param})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context['status_filter'], 'Occupied')
            stalls = list(resp.context['page_obj'])
            self.assertEqual(stalls, [self.occupied_stall])
            html = resp.content.decode()
            self.assertIn('DG-002', html)
            self.assertIn('Maria Santos', html)
            self.assertNotIn('DG-001', html)

    def test_filter_combined_with_section_and_search(self):
        Stall.objects.create(
            stall_number='WM-002',
            section=self.wet_market,
            stall_type=self.regular_type,
            monthly_rate=Decimal('1100.00'),
            status='Vacant',
            remarks='Corner unit',
        )
        resp = self.client.get(
            reverse('stall_list'),
            {'status': 'vacant', 'section': self.wet_market.pk, 'search': 'Corner'},
        )
        self.assertEqual(resp.status_code, 200)
        stalls = list(resp.context['page_obj'])
        self.assertEqual(len(stalls), 1)
        self.assertEqual(stalls[0].stall_number, 'WM-002')

    def test_htmx_partial_reload_returns_table_and_oob_links(self):
        resp = self.client.get(
            reverse('stall_list'),
            {'status': 'vacant'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn('<!DOCTYPE html>', html)
        self.assertIn('id="stall-table"', html)
        self.assertIn('DG-001', html)
        self.assertNotIn('DG-002', html)
        self.assertIn('hx-swap-oob="true"', html)
        self.assertIn('status=Vacant', html)

    def test_pagination_preserves_status_filter(self):
        for idx in range(1, 13):
            Stall.objects.create(
                stall_number=f'VAC-{idx:03d}',
                section=self.dry_goods,
                stall_type=self.regular_type,
                monthly_rate=Decimal('1000.00'),
                status='Vacant',
            )
        resp_p1 = self.client.get(reverse('stall_list'), {'status': 'Vacant', 'page': 1})
        self.assertEqual(resp_p1.status_code, 200)
        self.assertEqual(resp_p1.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(resp_p1.context['page_obj']), 10)
        self.assertIn('status=Vacant&page=2', resp_p1.content.decode())

        resp_p2 = self.client.get(reverse('stall_list'), {'status': 'Vacant', 'page': 2})
        self.assertEqual(resp_p2.status_code, 200)
        self.assertEqual(len(resp_p2.context['page_obj']), 3)
        for stall in resp_p2.context['page_obj']:
            self.assertEqual(stall.status, 'Vacant')

    def test_print_list_filters_by_status_and_displays_header(self):
        resp = self.client.get(reverse('stall_list_print'), {'status': 'occupied'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Status: Occupied', html)
        self.assertIn('DG-002', html)
        self.assertIn('Maria Santos', html)
        self.assertNotIn('DG-001', html)
        self.assertNotIn('WM-001', html)

    def test_vacant_stall_with_past_contract_shows_vacant_once(self):
        past_tenant = Tenant.objects.create(
            tenant_id='TNT-002',
            full_name='Pedro Cruz',
            address='Poblacion',
            contact_number='09170000002',
        )
        RentalContract.objects.create(
            tenant=past_tenant,
            stall=self.vacant_stall,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            monthly_rent=Decimal('1500.00'),
            status='Expired',
        )
        resp = self.client.get(reverse('stall_list'), {'status': 'Vacant'})
        html = resp.content.decode()
        self.assertEqual(html.count('— Vacant'), 1)
        self.assertNotIn('Pedro Cruz', html)


class StallRentalHistoryTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Market Administration Office',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.admin = User.objects.create_user(username='admin_hist', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

        self.section = MarketSection.objects.create(name='Dry Goods')
        self.stall_type = StallType.objects.create(name='Corner Stall')
        self.stall = Stall.objects.create(
            stall_number='A-101',
            section=self.section,
            stall_type=self.stall_type,
            size=Decimal('10.00'),
            monthly_rate=Decimal('2500.00'),
            status='Occupied',
        )

        self.past_tenant = Tenant.objects.create(
            tenant_id='TNT-101',
            full_name='Juan Dela Cruz',
            address='Barangay 1',
            contact_number='09171111111',
        )
        self.current_tenant = Tenant.objects.create(
            tenant_id='TNT-102',
            full_name='Elena Reyes',
            address='Barangay 2',
            contact_number='09172222222',
        )

        self.past_contract = RentalContract.objects.create(
            tenant=self.past_tenant,
            stall=self.stall,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            monthly_rent=Decimal('2000.00'),
            status='Expired',
        )
        self.current_contract = RentalContract.objects.create(
            tenant=self.current_tenant,
            stall=self.stall,
            start_date=date(2025, 1, 1),
            end_date=None,
            monthly_rent=Decimal('2500.00'),
            status='Active',
        )

        # Past contract billings (fully paid: 4000 billed, 4000 paid, 0 balance)
        Billing.objects.create(
            tenant=self.past_tenant,
            stall=self.stall,
            contract=self.past_contract,
            billing_month=1,
            billing_year=2024,
            rental_amount=Decimal('2000.00'),
            total_due=Decimal('2000.00'),
            amount_paid=Decimal('2000.00'),
            balance=Decimal('0.00'),
            due_date=date(2024, 1, 5),
            status='Paid',
        )
        Billing.objects.create(
            tenant=self.past_tenant,
            stall=self.stall,
            contract=self.past_contract,
            billing_month=2,
            billing_year=2024,
            rental_amount=Decimal('2000.00'),
            total_due=Decimal('2000.00'),
            amount_paid=Decimal('2000.00'),
            balance=Decimal('0.00'),
            due_date=date(2024, 2, 5),
            status='Paid',
        )

        # Current contract billings (5000 billed, 3000 paid, 2000 balance)
        Billing.objects.create(
            tenant=self.current_tenant,
            stall=self.stall,
            contract=self.current_contract,
            billing_month=1,
            billing_year=2025,
            rental_amount=Decimal('2500.00'),
            total_due=Decimal('2500.00'),
            amount_paid=Decimal('2500.00'),
            balance=Decimal('0.00'),
            due_date=date(2025, 1, 5),
            status='Paid',
        )
        Billing.objects.create(
            tenant=self.current_tenant,
            stall=self.stall,
            contract=self.current_contract,
            billing_month=2,
            billing_year=2025,
            rental_amount=Decimal('2500.00'),
            total_due=Decimal('2500.00'),
            amount_paid=Decimal('500.00'),
            balance=Decimal('2000.00'),
            due_date=date(2025, 2, 5),
            status='Partial',
        )

    def test_stall_view_shows_comprehensive_rental_history(self):
        resp = self.client.get(reverse('stall_view', args=[self.stall.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()

        self.assertIn('Rental History', html)
        self.assertIn('Juan Dela Cruz', html)
        self.assertIn('Elena Reyes', html)
        self.assertIn(f'CTR-{self.past_contract.id:05d}', html)
        self.assertIn(f'CTR-{self.current_contract.id:05d}', html)
        self.assertIn('Dec 31, 2024', html)
        self.assertIn('Jan 01, 2028', html)
        self.assertIn('Current', html)

        summary = resp.context['history_summary']
        self.assertEqual(summary['contract_count'], 2)
        self.assertEqual(summary['unique_tenants'], 2)
        self.assertEqual(summary['total_billed'], Decimal('9000.00'))
        self.assertEqual(summary['total_paid'], Decimal('7000.00'))
        self.assertEqual(summary['total_balance'], Decimal('2000.00'))

        # Verify rendered formatted totals
        self.assertIn('9,000.00', html)
        self.assertIn('7,000.00', html)
        self.assertIn('2,000.00', html)

    def test_stall_view_filter_by_status(self):
        resp = self.client.get(reverse('stall_view', args=[self.stall.pk]), {'status': 'expired'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['history_status_filter'], 'Expired')
        contracts = resp.context['contracts']
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0].id, self.past_contract.id)
        self.assertEqual(resp.context['history_summary']['total_billed'], Decimal('4000.00'))
        self.assertEqual(resp.context['history_summary']['total_balance'], Decimal('0.00'))

    def test_stall_view_filter_by_year_preserves_accurate_contract_totals(self):
        # Add a 2026 billing on the open-ended active contract to ensure year filtering
        # does not corrupt contract-level totals via reverse-FK JOIN filtering.
        Billing.objects.create(
            tenant=self.current_tenant,
            stall=self.stall,
            contract=self.current_contract,
            billing_month=1,
            billing_year=2026,
            rental_amount=Decimal('2500.00'),
            total_due=Decimal('2500.00'),
            amount_paid=Decimal('0.00'),
            balance=Decimal('2500.00'),
            due_date=date(2026, 1, 5),
            status='Unpaid',
        )

        resp_2024 = self.client.get(reverse('stall_view', args=[self.stall.pk]), {'year': '2024'})
        self.assertEqual(resp_2024.status_code, 200)
        self.assertEqual([c.id for c in resp_2024.context['contracts']], [self.past_contract.id])

        resp_2025 = self.client.get(reverse('stall_view', args=[self.stall.pk]), {'year': '2025'})
        self.assertEqual(resp_2025.status_code, 200)
        contracts_2025 = resp_2025.context['contracts']
        self.assertEqual([c.id for c in contracts_2025], [self.current_contract.id])
        self.assertEqual(contracts_2025[0].total_billed, Decimal('7500.00'))
        self.assertEqual(contracts_2025[0].total_paid, Decimal('3000.00'))
        self.assertEqual(contracts_2025[0].total_balance, Decimal('4500.00'))

    def test_stall_view_htmx_partial_reload(self):
        resp = self.client.get(
            reverse('stall_view', args=[self.stall.pk]),
            {'year': '2024'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn('<!DOCTYPE html>', html)
        self.assertIn('id="stall-rental-history-body"', html)
        self.assertIn('Juan Dela Cruz', html)
        self.assertNotIn('Elena Reyes', html)
        self.assertIn('year=2024', html)

    def test_stall_view_print_includes_rental_history_and_filters(self):
        resp = self.client.get(reverse('stall_view_print', args=[self.stall.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Rental History', html)
        self.assertIn(f'CTR-{self.past_contract.id:05d}', html)
        self.assertIn(f'CTR-{self.current_contract.id:05d}', html)
        self.assertIn('Juan Dela Cruz', html)
        self.assertIn('Elena Reyes', html)
        self.assertIn('9,000.00', html)
        self.assertIn('7,000.00', html)
        self.assertIn('2,000.00', html)

        # Print view also honors optional status/year filters
        resp_filtered = self.client.get(
            reverse('stall_view_print', args=[self.stall.pk]),
            {'status': 'Active'},
        )
        self.assertEqual(resp_filtered.status_code, 200)
        filtered_html = resp_filtered.content.decode()
        self.assertIn('Elena Reyes', filtered_html)
        self.assertNotIn('Juan Dela Cruz', filtered_html)

    def test_stall_view_empty_rental_history(self):
        empty_stall = Stall.objects.create(
            stall_number='B-202',
            section=self.section,
            stall_type=self.stall_type,
            monthly_rate=Decimal('1000.00'),
            status='Vacant',
        )
        resp = self.client.get(reverse('stall_view', args=[empty_stall.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('No rental history recorded', html)
        self.assertEqual(resp.context['history_summary']['contract_count'], 0)
        self.assertEqual(resp.context['history_summary']['total_billed'], Decimal('0.00'))
