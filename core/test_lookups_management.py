"""Tests for the MarketSection / StallType template-driven management.

The operator asked to manage these two lookup tables through the UI
rather than by seeding. The implementation adds:

*   Full management pages at ``/stalls/sections/`` and
    ``/stalls/stall-types/`` with add / edit / delete actions.
*   HTMX quick-add endpoints (``…/quick-add/``) so a stall form can
    grow its dropdown without leaving the page.
*   Guard rails: sections still referenced by a stall cannot be
    deleted (``Stall.section`` is ``CASCADE`` — deleting would wipe
    live stalls); deleting a stall type is allowed because the FK is
    ``SET_NULL``, but the operator is warned about how many stalls
    will lose their type.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    AuditLog, MarketSection, Stall, StallType, SystemSetting, UserProfile,
)


class _LookupTestBase(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)


class MarketSectionManagementTests(_LookupTestBase):
    def test_list_page_renders(self):
        MarketSection.objects.create(name='Dry Goods Section')
        resp = self.client.get(reverse('market_section_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Dry Goods Section', resp.content.decode())

    def test_create_persists_and_audits(self):
        resp = self.client.post(
            reverse('market_section_create'),
            {'name': 'Fish Section', 'description': 'Wet area'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MarketSection.objects.filter(name='Fish Section').exists())
        log = AuditLog.objects.filter(module='MarketSection', action='CREATE').first()
        self.assertIsNotNone(log)

    def test_create_rejects_duplicate_name(self):
        MarketSection.objects.create(name='Fish Section')
        resp = self.client.post(
            reverse('market_section_create'),
            {'name': 'Fish Section', 'description': ''},
            follow=True,
        )
        # Should redirect back with an error, no second row created.
        self.assertEqual(MarketSection.objects.filter(name='Fish Section').count(), 1)
        self.assertEqual(resp.status_code, 200)

    def test_update_renames(self):
        s = MarketSection.objects.create(name='Old')
        self.client.post(reverse('market_section_update', args=[s.pk]),
                         {'name': 'New', 'description': ''}, follow=True)
        s.refresh_from_db()
        self.assertEqual(s.name, 'New')

    def test_delete_succeeds_when_unused(self):
        s = MarketSection.objects.create(name='Temp')
        self.client.post(reverse('market_section_delete', args=[s.pk]), follow=True)
        self.assertFalse(MarketSection.objects.filter(pk=s.pk).exists())

    def test_delete_blocked_when_in_use(self):
        s = MarketSection.objects.create(name='In Use')
        Stall.objects.create(stall_number='S-1', section=s, monthly_rate=Decimal('100.00'))
        resp = self.client.post(reverse('market_section_delete', args=[s.pk]), follow=True)
        # Row must survive.
        self.assertTrue(MarketSection.objects.filter(pk=s.pk).exists())
        messages = [str(m) for m in resp.context['messages']]
        self.assertTrue(any('Cannot delete' in m for m in messages), messages)

    def test_quick_add_creates_and_returns_fresh_select(self):
        resp = self.client.post(
            reverse('market_section_quick_add'),
            {'name': 'Eatery Section'},
            headers={'hx-request': 'true'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(MarketSection.objects.filter(name='Eatery Section').exists())
        html = resp.content.decode()
        self.assertIn('<select', html)
        self.assertIn('Eatery Section', html)
        # The new option must be marked selected so it becomes the current pick.
        self.assertIn('selected', html)
        # HX-Trigger lets surrounding JS close the mini-form if desired.
        self.assertEqual(resp['HX-Trigger'], 'sectionAdded')

    def test_quick_add_is_idempotent_for_existing_name(self):
        MarketSection.objects.create(name='Kiosk Area')
        resp = self.client.post(
            reverse('market_section_quick_add'),
            {'name': 'Kiosk Area'},
            headers={'hx-request': 'true'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(MarketSection.objects.filter(name='Kiosk Area').count(), 1)

    def test_quick_add_with_blank_name_is_noop(self):
        resp = self.client.post(
            reverse('market_section_quick_add'),
            {'name': '   '},
            headers={'hx-request': 'true'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(MarketSection.objects.exists())

    def test_non_staff_cannot_reach_management(self):
        outsider = User.objects.create_user(username='joe', password='Joe!Pass123')
        UserProfile.objects.create(user=outsider, role='tenant')
        self.client.force_login(outsider)
        resp = self.client.get(reverse('market_section_list'), follow=True)
        # Redirected away with an error message.
        self.assertNotEqual(resp.resolver_match.url_name, 'market_section_list')


class StallTypeManagementTests(_LookupTestBase):
    def test_list_page_renders(self):
        StallType.objects.create(name='Kiosk')
        resp = self.client.get(reverse('stall_type_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Kiosk', resp.content.decode())

    def test_create_persists(self):
        self.client.post(reverse('stall_type_create'),
                         {'name': 'Table Space', 'description': 'Small'}, follow=True)
        self.assertTrue(StallType.objects.filter(name='Table Space').exists())

    def test_update_renames(self):
        t = StallType.objects.create(name='Old')
        self.client.post(reverse('stall_type_update', args=[t.pk]),
                         {'name': 'New', 'description': ''}, follow=True)
        t.refresh_from_db()
        self.assertEqual(t.name, 'New')

    def test_delete_clears_type_on_stalls_but_keeps_them(self):
        """StallType is SET_NULL — deleting must null out FKs, not remove stalls."""
        section = MarketSection.objects.create(name='Dry')
        stall_type = StallType.objects.create(name='Kiosk')
        Stall.objects.create(stall_number='S-1', section=section,
                             stall_type=stall_type, monthly_rate=Decimal('100.00'))
        resp = self.client.post(reverse('stall_type_delete', args=[stall_type.pk]), follow=True)
        self.assertFalse(StallType.objects.filter(pk=stall_type.pk).exists())
        stall = Stall.objects.get(pk=Stall.objects.first().pk)
        self.assertIsNone(stall.stall_type)
        messages = [str(m) for m in resp.context['messages']]
        self.assertTrue(any('cleared' in m for m in messages), messages)

    def test_quick_add_creates_and_returns_fresh_select(self):
        resp = self.client.post(
            reverse('stall_type_quick_add'),
            {'name': 'Premium'},
            headers={'hx-request': 'true'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(StallType.objects.filter(name='Premium').exists())
        self.assertIn('Premium', resp.content.decode())
        self.assertIn('selected', resp.content.decode())

    def test_stall_form_links_to_both_management_pages(self):
        resp = self.client.get(reverse('stall_add'))
        html = resp.content.decode()
        self.assertIn(reverse('market_section_list'), html)
        self.assertIn(reverse('stall_type_list'), html)
