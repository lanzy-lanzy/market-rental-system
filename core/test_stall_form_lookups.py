"""Tests covering the Stall form's Section + Stall Type wiring.

Context: the operator wants sections and stall types to be managed
purely through the UI — no seeded defaults. These tests therefore
build the lookup rows they need inside ``setUp`` rather than relying
on any migration or fixture to provide them.

What we assert:
1. ``StallForm`` exposes both fields as clean ModelChoiceFields with
   friendly empty labels and clear required/invalid messages.
2. The view + template round trip works when the lookups exist.
3. Both templates surface a per-field empty-state warning that links
   to the new dedicated management pages when the lookups are missing.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.forms import StallForm
from core.models import (
    MarketSection, Stall, StallType, SystemSetting, UserProfile,
)


class StallFormLookupTests(TestCase):
    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)
        # Lookups are created by the operator through the UI in real use,
        # so tests build the same rows here.
        self.section = MarketSection.objects.create(name='Dry Goods Section')
        self.stall_type = StallType.objects.create(name='Regular Stall')

    # --- form field wiring -------------------------------------------

    def test_form_exposes_section_and_stall_type(self):
        form = StallForm()
        self.assertIn('section', form.fields)
        self.assertIn('stall_type', form.fields)
        self.assertTrue(form.fields['section'].required)
        self.assertFalse(form.fields['stall_type'].required)
        # Empty labels guide the user instead of the bare "---------".
        self.assertIn('Select section', str(form.fields['section'].empty_label))
        self.assertIn('Select stall type', str(form.fields['stall_type'].empty_label))

    def test_form_flag_surfaces_empty_state(self):
        MarketSection.objects.all().delete()
        StallType.objects.all().delete()
        form = StallForm()
        self.assertFalse(form.section_options_available)
        self.assertFalse(form.stall_type_options_available)

    def test_form_valid_when_lookups_populated(self):
        form = StallForm(data={
            'stall_number': 'A-101',
            'section': self.section.pk,
            'stall_type': self.stall_type.pk,
            'size': Decimal('4.00'),
            'monthly_rate': Decimal('1500.00'),
            'status': 'Vacant',
            'remarks': '',
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        stall = form.save()
        self.assertEqual(stall.section, self.section)
        self.assertEqual(stall.stall_type, self.stall_type)

    def test_form_rejects_missing_section(self):
        form = StallForm(data={
            'stall_number': 'A-102',
            'section': '',
            'stall_type': '',
            'size': Decimal('4.00'),
            'monthly_rate': Decimal('1500.00'),
            'status': 'Vacant',
            'remarks': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('section', form.errors)

    def test_form_stall_type_optional(self):
        form = StallForm(data={
            'stall_number': 'A-103',
            'section': self.section.pk,
            'stall_type': '',
            'size': Decimal('4.00'),
            'monthly_rate': Decimal('1500.00'),
            'status': 'Vacant',
            'remarks': '',
        })
        self.assertTrue(form.is_valid(), form.errors.as_json())
        stall = form.save()
        self.assertIsNone(stall.stall_type)

    # --- view + template round trip ----------------------------------

    def test_stall_add_get_page_renders_dropdowns(self):
        resp = self.client.get(reverse('stall_add'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('name="section"', html)
        self.assertIn('name="stall_type"', html)
        self.assertIn('Dry Goods Section', html)
        self.assertIn('Regular Stall', html)

    def test_stall_add_post_creates_stall(self):
        resp = self.client.post(reverse('stall_add'), {
            'stall_number': 'DGS-101',
            'section': self.section.pk,
            'stall_type': self.stall_type.pk,
            'size': Decimal('4.00'),
            'monthly_rate': Decimal('1500.00'),
            'status': 'Vacant',
            'remarks': '',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        stall = Stall.objects.get(stall_number='DGS-101')
        self.assertEqual(stall.section, self.section)
        self.assertEqual(stall.stall_type, self.stall_type)

    def test_stall_form_links_to_management_pages(self):
        """The stall form should offer obvious routes to manage lookups."""
        resp = self.client.get(reverse('stall_add'))
        html = resp.content.decode()
        self.assertIn(reverse('market_section_list'), html)
        self.assertIn(reverse('stall_type_list'), html)

    def test_template_shows_empty_state_warning_when_sections_missing(self):
        MarketSection.objects.all().delete()
        resp = self.client.get(reverse('stall_add'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'No market sections are configured yet',
            resp.content.decode(),
        )
