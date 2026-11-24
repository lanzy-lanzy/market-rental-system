"""Tests for report status filtering (unpaid/overdue/balance) and history year filtering."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import io

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AuditLog, Billing, MarketSection, Payment, RentalContract, Stall,
    StallType, SystemSetting, Tenant, TenantLedger, UserProfile,
)


class ReportStatusFilterTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Office',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.admin = User.objects.create_user(
            username='repadmin', password='Password!123',
            first_name='Admin', last_name='User',
        )
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

        self.section = MarketSection.objects.create(name='Dry Goods')
        self.stall_type = StallType.objects.create(name='Regular')

        self.year = 2026
        self.month = 3
        today = date(self.year, self.month, 15)

        def make_billing(idx, first, last, status, total_due, amount_paid, balance):
            tenant = Tenant.objects.create(
                tenant_id=f'T-{idx:03d}',
                first_name=first,
                last_name=last,
                full_name=f'{first} {last}',
                barangay='Poblacion',
                contact_number=f'090000000{idx:02d}',
            )
            stall = Stall.objects.create(
                stall_number=f'DG-{idx:02d}',
                section=self.section,
                stall_type=self.stall_type,
                monthly_rate=Decimal('1000.00'),
                status='Occupied',
            )
            contract = RentalContract.objects.create(
                tenant=tenant,
                stall=stall,
                monthly_rent=Decimal('1000.00'),
                start_date=today - timedelta(days=60),
                end_date=today + timedelta(days=300),
                status='Active',
            )
            return Billing.objects.create(
                tenant=tenant,
                stall=stall,
                contract=contract,
                billing_month=self.month,
                billing_year=self.year,
                rental_amount=Decimal('1000.00'),
                penalty_amount=Decimal('50.00') if status == 'Overdue' else Decimal('0.00'),
                total_due=Decimal(total_due),
                amount_paid=Decimal(amount_paid),
                balance=Decimal(balance),
                due_date=today - timedelta(days=10) if status == 'Overdue' else today + timedelta(days=5),
                status=status,
            )

        self.b_paid = make_billing(1, 'Alice', 'Paid', 'Paid', '1000.00', '1000.00', '0.00')
        self.b_unpaid = make_billing(2, 'Bob', 'Unpaid', 'Unpaid', '1000.00', '0.00', '1000.00')
        self.b_partial = make_billing(3, 'Carla', 'Partial', 'Partial', '1000.00', '400.00', '600.00')
        self.b_overdue = make_billing(4, 'Dan', 'Overdue', 'Overdue', '1050.00', '0.00', '1050.00')

    def test_unpaid_report_default_shows_outstanding(self):
        url = reverse('report_unpaid_tenants')
        resp = self.client.get(url, {'month': self.month, 'year': self.year})
        self.assertEqual(resp.status_code, 200)
        ids = {b.pk for b in resp.context['page_obj']}
        self.assertEqual(ids, {self.b_unpaid.pk, self.b_partial.pk, self.b_overdue.pk})
        self.assertNotIn(self.b_paid.pk, ids)

    def test_unpaid_report_filters_unpaid_overdue_balance_paid_all(self):
        url = reverse('report_unpaid_tenants')

        cases = [
            ('unpaid', {self.b_unpaid.pk}),
            ('overdue', {self.b_overdue.pk}),
            ('balance', {self.b_unpaid.pk, self.b_partial.pk, self.b_overdue.pk}),
            ('partial', {self.b_partial.pk}),
            ('paid', {self.b_paid.pk}),
            ('all', {self.b_paid.pk, self.b_unpaid.pk, self.b_partial.pk, self.b_overdue.pk}),
            ('OVERDUE', {self.b_overdue.pk}),
        ]
        for status_param, expected in cases:
            resp = self.client.get(url, {'month': self.month, 'year': self.year, 'status': status_param})
            self.assertEqual(resp.status_code, 200)
            actual = {b.pk for b in resp.context['page_obj']}
            self.assertEqual(actual, expected, msg=f'Failed for status={status_param}')

    def test_unpaid_report_search_and_status_persist_in_export_links_and_htmx(self):
        url = reverse('report_unpaid_tenants')
        resp = self.client.get(
            url,
            {'month': self.month, 'year': self.year, 'status': 'balance', 'search': 'Carla'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('report-tenants-wrapper', body)
        self.assertNotIn('<!DOCTYPE html>', body)
        self.assertIn('Carla Partial', body)
        self.assertNotIn('Bob Unpaid', body)
        self.assertIn('status=balance', body)
        self.assertIn('search=Carla', body)

    def test_paid_report_supports_status_switching(self):
        url = reverse('report_paid_tenants')
        resp_default = self.client.get(url, {'month': self.month, 'year': self.year})
        self.assertEqual({b.pk for b in resp_default.context['page_obj']}, {self.b_paid.pk})

        resp_balance = self.client.get(url, {'month': self.month, 'year': self.year, 'status': 'balance'})
        self.assertEqual(
            {b.pk for b in resp_balance.context['page_obj']},
            {self.b_unpaid.pk, self.b_partial.pk, self.b_overdue.pk},
        )

    def test_overdue_report_status_filter_and_htmx(self):
        url = reverse('report_overdue')
        resp_default = self.client.get(url)
        self.assertEqual({b.pk for b in resp_default.context['page_obj']}, {self.b_overdue.pk})

        resp_unpaid = self.client.get(url, {'status': 'unpaid'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp_unpaid.status_code, 200)
        body = resp_unpaid.content.decode('utf-8')
        self.assertIn('report-overdue-wrapper', body)
        self.assertNotIn('<!DOCTYPE html>', body)
        self.assertEqual({b.pk for b in resp_unpaid.context['page_obj']}, {self.b_unpaid.pk})
        self.assertIn('status=unpaid', body)

        resp_balance = self.client.get(url, {'status': 'balance'})
        self.assertEqual(
            {b.pk for b in resp_balance.context['page_obj']},
            {self.b_unpaid.pk, self.b_partial.pk, self.b_overdue.pk},
        )

    def test_report_dashboard_includes_balance_count_and_status_links(self):
        resp = self.client.get(reverse('report_dashboard'), {'month': self.month, 'year': self.year})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['balance_count'], 3)
        body = resp.content.decode('utf-8')
        self.assertIn('status=unpaid', body)
        self.assertIn('status=overdue', body)
        self.assertIn('status=balance', body)

    def test_excel_export_respects_status_and_search_filters(self):
        import openpyxl

        url = reverse('report_export_excel')
        resp = self.client.get(url, {
            'report': 'unpaid',
            'month': self.month,
            'year': self.year,
            'status': 'overdue',
        })
        self.assertEqual(resp.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], 'Dan Overdue')

        resp_bal = self.client.get(url, {
            'report': 'unpaid',
            'month': self.month,
            'year': self.year,
            'status': 'balance',
            'search': 'Carla',
        })
        self.assertEqual(resp_bal.status_code, 200)
        wb2 = openpyxl.load_workbook(io.BytesIO(resp_bal.content))
        rows2 = list(wb2.active.iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(rows2), 1)
        self.assertEqual(rows2[0][1], 'Carla Partial')


class HistoryYearFilterTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag',
            market_name='Dumingag Public Market',
            office_name='Office',
            receipt_prefix='DMPM',
            default_due_day=5,
        )
        self.admin = User.objects.create_user(
            username='histadmin', password='Password!123',
            first_name='Admin', last_name='Hist',
        )
        UserProfile.objects.create(user=self.admin, role='admin')

        self.tenant_user = User.objects.create_user(
            username='histtenant', password='Password!123',
            first_name='Maria', last_name='Clara',
        )
        UserProfile.objects.create(user=self.tenant_user, role='tenant')
        self.tenant = Tenant.objects.create(
            user=self.tenant_user,
            tenant_id='T-HIST',
            first_name='Maria',
            last_name='Clara',
            full_name='Maria Clara',
            barangay='Poblacion',
            contact_number='09000000111',
        )
        section = MarketSection.objects.create(name='Wet Market')
        stall_type = StallType.objects.create(name='Regular')
        self.stall = Stall.objects.create(
            stall_number='WM-01',
            section=section,
            stall_type=stall_type,
            monthly_rate=Decimal('500.00'),
            status='Occupied',
        )
        self.contract = RentalContract.objects.create(
            tenant=self.tenant,
            stall=self.stall,
            monthly_rent=Decimal('500.00'),
            start_date=date(2024, 1, 1),
            end_date=date(2027, 1, 1),
            status='Active',
        )
        self.billing_2024 = Billing.objects.create(
            tenant=self.tenant,
            stall=self.stall,
            contract=self.contract,
            billing_month=5,
            billing_year=2024,
            rental_amount=Decimal('500.00'),
            total_due=Decimal('500.00'),
            balance=Decimal('500.00'),
            due_date=date(2024, 5, 5),
            status='Unpaid',
        )
        self.billing_2026 = Billing.objects.create(
            tenant=self.tenant,
            stall=self.stall,
            contract=self.contract,
            billing_month=2,
            billing_year=2026,
            rental_amount=Decimal('500.00'),
            total_due=Decimal('500.00'),
            balance=Decimal('500.00'),
            due_date=date(2026, 2, 5),
            status='Unpaid',
        )
        self.entry_2024 = TenantLedger.objects.create(
            tenant=self.tenant,
            billing=self.billing_2024,
            transaction_date=date(2024, 5, 1),
            description='Rent 05/2024 Alpha',
            debit=Decimal('500.00'),
            credit=Decimal('0.00'),
            balance=Decimal('500.00'),
        )
        self.entry_2026 = TenantLedger.objects.create(
            tenant=self.tenant,
            billing=self.billing_2026,
            transaction_date=date(2026, 2, 1),
            description='Rent 02/2026 Beta',
            debit=Decimal('500.00'),
            credit=Decimal('0.00'),
            balance=Decimal('1000.00'),
        )

    def test_tenant_portal_history_year_filter_and_htmx(self):
        self.client.force_login(self.tenant_user)
        url = reverse('tenant_portal_history')

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['available_years'], [2026, 2024])
        self.assertContains(resp, 'name="year"')

        resp_2024 = self.client.get(url, {'year': '2024'})
        self.assertEqual(resp_2024.status_code, 200)
        self.assertEqual([e.pk for e in resp_2024.context['page_obj']], [self.entry_2024.pk])

        resp_htmx = self.client.get(url, {'year': '2026', 'search': 'Beta'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp_htmx.status_code, 200)
        body = resp_htmx.content.decode('utf-8')
        self.assertIn('portal-history-wrapper', body)
        self.assertNotIn('<!DOCTYPE html>', body)
        self.assertEqual([e.pk for e in resp_htmx.context['page_obj']], [self.entry_2026.pk])

        # Invalid year parameter does not crash
        resp_bad = self.client.get(url, {'year': 'not-a-year'})
        self.assertEqual(resp_bad.status_code, 200)
        self.assertEqual(resp_bad.context['page_obj'].paginator.count, 2)

    def test_tenant_portal_history_pagination_preserves_year(self):
        self.client.force_login(self.tenant_user)
        for i in range(18):
            TenantLedger.objects.create(
                tenant=self.tenant,
                billing=self.billing_2024,
                transaction_date=date(2024, 6, 1 + (i % 20)),
                description=f'2024 Entry #{i}',
                debit=Decimal('10.00'),
                credit=Decimal('0.00'),
                balance=Decimal('500.00'),
            )
        resp = self.client.get(reverse('tenant_portal_history'), {'year': '2024'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['page_obj'].paginator.num_pages, 2)
        body = resp.content.decode('utf-8')
        self.assertIn('year=2024&page=2', body)

    def test_audit_log_year_filter_and_htmx_and_pagination(self):
        self.client.force_login(self.admin)

        log_2024 = AuditLog.objects.create(
            user=self.admin, action='CREATE', module='Billing', description='Old 2024 event',
        )
        AuditLog.objects.filter(pk=log_2024.pk).update(
            created_at=timezone.make_aware(datetime(2024, 4, 10, 9, 0, 0)),
        )
        log_2026 = AuditLog.objects.create(
            user=self.admin, action='UPDATE', module='Payment', description='New 2026 event',
        )
        AuditLog.objects.filter(pk=log_2026.pk).update(
            created_at=timezone.make_aware(datetime(2026, 3, 12, 10, 0, 0)),
        )

        url = reverse('audit_log_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(2024, resp.context['available_years'])
        self.assertIn(2026, resp.context['available_years'])
        self.assertContains(resp, 'name="year"')

        resp_2024 = self.client.get(url, {'year': '2024'})
        self.assertEqual(resp_2024.status_code, 200)
        self.assertEqual([l.pk for l in resp_2024.context['page_obj']], [log_2024.pk])

        resp_htmx = self.client.get(url, {'year': '2026', 'search': 'New'}, HTTP_HX_REQUEST='true')
        self.assertEqual(resp_htmx.status_code, 200)
        body = resp_htmx.content.decode('utf-8')
        self.assertIn('audit-table-wrapper', body)
        self.assertNotIn('<!DOCTYPE html>', body)
        self.assertEqual([l.pk for l in resp_htmx.context['page_obj']], [log_2026.pk])

        # Invalid year does not crash
        resp_bad = self.client.get(url, {'year': 'xyz'})
        self.assertEqual(resp_bad.status_code, 200)

        # Pagination preserves year
        for i in range(18):
            l = AuditLog.objects.create(
                user=self.admin, action='CREATE', module='Stall', description=f'Event {i}',
            )
            AuditLog.objects.filter(pk=l.pk).update(
                created_at=timezone.make_aware(datetime(2024, 5, 1 + (i % 20), 8, 0, 0)),
            )
        resp_page = self.client.get(url, {'year': '2024'})
        self.assertEqual(resp_page.status_code, 200)
        self.assertGreater(resp_page.context['page_obj'].paginator.num_pages, 1)
        self.assertIn('year=2024&page=2', resp_page.content.decode('utf-8'))
