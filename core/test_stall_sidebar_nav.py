"""Streamlined Operations sidebar and unified Stalls workspace navigation tests.

The Operations sidebar uses single direct links for Tenants, Stalls, and
Contracts instead of multi-item accordions (List / Add / Lookups / Sections /
Stall Types). Inside the Stalls workspace, an in-page tab bar switches cleanly
between Stalls, Sections, and Stall Types with a 1-click Add Stall action.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import MarketSection, StallType, SystemSetting, UserProfile


class StallSidebarNavigationTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def _html(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.content.decode()

    def _sidebar(self, html):
        start = html.index('<aside')
        end = html.index('</aside>') + len('</aside>')
        return html[start:end]

    def test_operations_sidebar_has_direct_links_without_creation_sublinks(self):
        html = self._html(reverse('stall_list'))
        sidebar = self._sidebar(html)
        self.assertIn(f'href="{reverse("tenant_list")}"', sidebar)
        self.assertIn(f'href="{reverse("stall_list")}"', sidebar)
        self.assertIn(f'href="{reverse("contract_list")}"', sidebar)
        # No accordion clutter in the sidebar for Tenants, Stalls, or Contracts
        for clutter in (
            'Add Stall',
            'Sections',
            'Stall Types',
            'Lookups',
            'Add Tenant',
            'New Contract',
            'Bulk Assign',
        ):
            self.assertNotIn(clutter, sidebar)

    def test_single_stalls_sidebar_link_is_active_across_all_stall_pages(self):
        StallType.objects.create(name='Kiosk')
        MarketSection.objects.create(name='Dry Goods')
        for url in (
            reverse('stall_list'),
            reverse('stall_add'),
            reverse('market_section_list'),
            reverse('stall_type_list'),
        ):
            sidebar = self._sidebar(self._html(url))
            self.assertIn(f'href="{reverse("stall_list")}" class="nav-link is-active"', sidebar, url)

    def test_workspace_tabs_highlight_active_tab_per_page(self):
        StallType.objects.create(name='Kiosk')
        MarketSection.objects.create(name='Dry Goods')

        cases = [
            (reverse('stall_list'), 'list'),
            (reverse('stall_add'), 'list'),
            (reverse('market_section_list'), 'sections'),
            (reverse('stall_type_list'), 'types'),
        ]
        for url, expected_tab in cases:
            html = self._html(url)
            self.assertIn('data-stalls-workspace-tabs', html, url)
            self.assertEqual(html.count('workspace-tab inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition is-active'), 1, url)
            self.assertIn(f'data-workspace-tab="{expected_tab}"\n         aria-current="page"', html, url)

    def test_workspace_tabs_include_one_click_add_stall_modal_trigger(self):
        for url in (
            reverse('stall_list'),
            reverse('market_section_list'),
            reverse('stall_type_list'),
        ):
            html = self._html(url)
            self.assertIn(reverse('stall_add_modal'), html, url)

    def test_unrelated_pages_leave_stalls_sidebar_link_inactive(self):
        sidebar = self._sidebar(self._html(reverse('dashboard')))
        self.assertNotIn(f'href="{reverse("stall_list")}" class="nav-link is-active"', sidebar)
