"""Sidebar state for the Stalls group.

The group used to decide its open/active state with substring matching on the
URL name, which misfired in both directions: ``market_section_list`` does not
contain "stall" (group stayed collapsed and un-highlighted) while
``stall_type_list`` does (the "List" entry lit up alongside "Stall Types").
``stall_navigation`` now maps URL names to an explicit sidebar tab.
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

    def _nav(self, url):
        return self.client.get(url).content.decode()

    def test_stall_list_page_opens_group_and_highlights_list(self):
        html = self._nav(reverse('stall_list'))
        self.assertIn('nav-sub-link is-active">List<', html)
        self.assertIn('x-data="{ open: true }"', html)

    def test_stall_types_page_highlights_only_stall_types(self):
        StallType.objects.create(name='Kiosk')
        html = self._nav(reverse('stall_type_list'))
        self.assertIn('nav-sub-link is-active">Stall Types<', html)
        self.assertNotIn('nav-sub-link is-active">List<', html)
        self.assertIn('x-data="{ open: true }"', html)

    def test_sections_page_opens_group_and_highlights_sections(self):
        MarketSection.objects.create(name='Dry Goods')
        html = self._nav(reverse('market_section_list'))
        self.assertIn('nav-sub-link is-active">Sections<', html)
        self.assertIn('x-data="{ open: true }"', html)

    def test_add_stall_page_highlights_add_stall(self):
        html = self._nav(reverse('stall_add'))
        self.assertIn('nav-sub-link is-active">Add Stall<', html)
        self.assertNotIn('nav-sub-link is-active">List<', html)

    def test_exactly_one_stall_sub_link_is_active_per_page(self):
        StallType.objects.create(name='Kiosk')
        MarketSection.objects.create(name='Dry Goods')
        for url in (
            reverse('stall_list'),
            reverse('stall_add'),
            reverse('stall_type_list'),
            reverse('market_section_list'),
        ):
            html = self._nav(url)
            self.assertEqual(html.count('nav-sub-link is-active'), 1, url)

    def test_unrelated_pages_leave_the_group_closed(self):
        html = self._nav(reverse('dashboard'))
        self.assertNotIn('nav-sub-link is-active">Stall Types<', html)
        self.assertNotIn('nav-sub-link is-active">Sections<', html)
