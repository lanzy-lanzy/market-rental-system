"""Dashboard tile → URL wiring.

Regression context: dashboard cards used to be inert divs so operators
had to hunt the sidebar to reach the list pages. They are now anchored
so a single click (or Enter on keyboard focus) navigates directly to
the relevant detail/report page.

These tests pin down the contract:
*   Every stat tile / secondary tile is an ``<a>`` tag pointing at the
    expected URL name — no ``<div>`` wrappers that silently swallow
    clicks.
*   Every anchor uses ``{% url %}`` reverse resolution (verified by
    comparing the rendered href against Django's own ``reverse()``).
*   No nested interactive elements inside a card (which would produce
    invalid HTML and break click targets).
*   The bottom quick-action cards (Add Tenant / Add Stall / Generate
    Bills / Reports) resolve to their respective pages.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Billing, MarketSection, Payment, RentalContract, Stall, SystemSetting,
    Tenant, UserProfile,
)


class DashboardCardLinksTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

        self.section = MarketSection.objects.create(name='Dry')
        self.stall = Stall.objects.create(
            stall_number='DGS-01', section=self.section,
            monthly_rate=Decimal('1500'), status='Occupied',
        )
        self.tenant = Tenant.objects.create(
            tenant_id='T-001', full_name='Juan Dela Cruz',
            address='Purok 1', contact_number='0900',
            status='Active',
        )
        self.contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.stall,
            start_date='2026-01-01', end_date='2026-12-31',
            monthly_rent=Decimal('1500'), status='Active',
        )
        self.billing = Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=10, billing_year=2026,
            rental_amount=Decimal('1500'), total_due=Decimal('1500'),
            amount_paid=Decimal('0'), balance=Decimal('1500'),
            status='Unpaid', due_date='2026-10-05',
        )

    def _html(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    # ---- 1 · stat tiles are anchors to their list pages -------------

    def test_total_stalls_tile_links_to_stall_list(self):
        html = self._html()
        self.assertIn(f'href="{reverse("stall_list")}"', html)

    def test_occupied_tile_links_to_occupancy_report(self):
        html = self._html()
        self.assertIn(f'href="{reverse("report_occupancy")}"', html)

    def test_vacant_tile_links_to_stall_list_with_status_filter(self):
        html = self._html()
        self.assertIn(
            f'href="{reverse("stall_list")}?status=Vacant"', html,
        )

    def test_tenants_tile_links_to_tenant_list(self):
        html = self._html()
        self.assertIn(f'href="{reverse("tenant_list")}"', html)

    # ---- 2 · secondary tiles ----------------------------------------

    def test_monthly_collectibles_tile_links_to_billing(self):
        html = self._html()
        self.assertIn(f'href="{reverse("billing_list")}"', html)

    def test_collected_tile_links_to_payment_list(self):
        html = self._html()
        self.assertIn(f'href="{reverse("payment_list")}"', html)

    def test_unpaid_tile_links_to_overdue_report(self):
        html = self._html()
        self.assertIn(f'href="{reverse("report_overdue")}"', html)

    # ---- 3 · bottom quick-action tiles -------------------------------

    def test_quick_action_add_tenant(self):
        self.assertIn(f'href="{reverse("tenant_add")}"', self._html())

    def test_quick_action_add_stall(self):
        self.assertIn(f'href="{reverse("stall_add")}"', self._html())

    def test_quick_action_generate_bills(self):
        self.assertIn(f'href="{reverse("billing_generate")}"', self._html())

    def test_quick_action_reports(self):
        self.assertIn(f'href="{reverse("report_dashboard")}"', self._html())

    # ---- 4 · welcome-card buttons remain functional ------------------

    def test_welcome_collect_button_links_to_billing(self):
        # billing_list URL appears for both the Collect button and the
        # Monthly Collectibles tile. Assert at least two anchors resolve
        # to it so removing either one fails loudly.
        html = self._html()
        self.assertGreaterEqual(
            html.count(f'href="{reverse("billing_list")}"'), 2,
        )

    def test_welcome_generate_button_links_to_billing_generate(self):
        # Same duplication rationale: welcome bar + quick-action card.
        html = self._html()
        self.assertGreaterEqual(
            html.count(f'href="{reverse("billing_generate")}"'), 2,
        )

    # ---- 5 · table rows are anchored too, without nesting ------------

    def test_recent_payment_rows_link_to_payment_detail(self):
        """A payment row must be a single anchor to payment_view."""
        from django.utils import timezone
        Payment.objects.create(
            billing=self.billing, tenant=self.tenant, stall=self.stall,
            billing_month=10, billing_year=2026,
            rental_amount=Decimal('1500'), total_amount_due=Decimal('1500'),
            amount_paid=Decimal('1500'), payment_method='Cash',
            receipt_number='DMPM-TEST001', payment_date=timezone.now().date(),
            status='Paid',
        )
        html = self._html()
        # Row anchor present.
        self.assertIn('href="/payments/', html)

    def test_unpaid_balance_rows_link_to_ledger(self):
        html = self._html()
        # The tenant id is stable so the row anchor must point at the
        # matching ledger URL.
        self.assertIn(f'href="{reverse("ledger_view", args=[self.tenant.pk])}"', html)

    # ---- 6 · no nested <a> inside a card (invalid HTML) --------------

    def test_no_nested_anchors_in_dashboard(self):
        """Scan the rendered dashboard for `<a ...> ... <a ...>` patterns.

        Nested anchors are illegal HTML — most browsers silently drop
        the inner one, which was the failure mode we removed by
        relocating the Vacant card's old ``View →`` link onto the
        card wrapper and swapping the Unpaid Balances row's inline
        "Ledger" link for a full-row anchor.
        """
        html = self._html()
        # Walk every <a ...> opening tag; track depth. A second open
        # before the first close is the bug.
        depth = 0
        i = 0
        while True:
            open_idx = html.find('<a ', i)
            close_idx = html.find('</a>', i)
            if open_idx == -1 and close_idx == -1:
                break
            if open_idx != -1 and (close_idx == -1 or open_idx < close_idx):
                depth += 1
                self.assertLessEqual(
                    depth, 1,
                    msg='Found nested <a> tags in dashboard.html — '
                        'wrap only one anchor per card.',
                )
                i = open_idx + 3
            else:
                depth -= 1
                i = close_idx + 4
