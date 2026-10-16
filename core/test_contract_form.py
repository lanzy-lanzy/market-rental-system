import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.forms import RentalContractForm
from core.models import (
    AuditLog, Billing, MarketSection, RentalContract, Stall, Tenant, UserProfile,
)


class AssignedStallMapTests(TestCase):
    """Regression coverage for the tenant -> stall auto-select in the contract form."""

    @classmethod
    def setUpTestData(cls):
        cls.section, _ = MarketSection.objects.get_or_create(name='Vegetable Section')
        cls.occupied_stall = Stall.objects.create(
            stall_number='RGS-01', section=cls.section, monthly_rate=3000, status='Occupied')
        cls.vacant_stall = Stall.objects.create(
            stall_number='A-909', section=cls.section, monthly_rate=3500, status='Vacant')
        cls.tenant = Tenant.objects.create(
            tenant_id='TEN-101', full_name='Active Holder', address='Poblacion',
            contact_number='09000000101', status='Active')
        cls.renewal_tenant = Tenant.objects.create(
            tenant_id='TEN-102', full_name='Renewal Tenant', address='Poblacion',
            contact_number='09000000102', status='Active')

    def _contract(self, tenant, stall, status, start, end=None):
        return RentalContract.objects.create(
            tenant=tenant, stall=stall, status=status, start_date=start,
            end_date=end or date(start.year + 2, start.month, min(start.day, 28)),
            monthly_rent=stall.monthly_rate, due_day=5, security_deposit=1000)

    def test_lists_active_stall_with_its_rate(self):
        self._contract(self.tenant, self.occupied_stall, 'Active', date(2026, 1, 1))
        entries = RentalContractForm._assigned_stall_map()[str(self.tenant.pk)]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['stall'], str(self.occupied_stall.pk))
        self.assertEqual(entries[0]['number'], 'RGS-01')
        self.assertEqual(entries[0]['rate'], '3000.00')
        self.assertEqual(entries[0]['status'], 'Active')

    def test_every_stall_of_a_multi_stall_tenant_is_listed(self):
        second = Stall.objects.create(stall_number='RGS-02', section=self.section,
                                      monthly_rate=1000, status='Occupied')
        self._contract(self.tenant, self.occupied_stall, 'Active', date(2026, 1, 1))
        self._contract(self.tenant, second, 'Active', date(2026, 3, 1))
        entries = RentalContractForm._assigned_stall_map()[str(self.tenant.pk)]
        self.assertCountEqual([e['number'] for e in entries], ['RGS-01', 'RGS-02'])

    def test_active_stalls_are_offered_before_lapsed_ones(self):
        lapsed = Stall.objects.create(stall_number='RGS-09', section=self.section,
                                     monthly_rate=900, status='Vacant')
        self._contract(self.renewal_tenant, lapsed, 'Expired', date(2024, 1, 1))
        self._contract(self.renewal_tenant, self.occupied_stall, 'Active', date(2026, 1, 1))
        entries = RentalContractForm._assigned_stall_map()[str(self.renewal_tenant.pk)]
        self.assertEqual([e['status'] for e in entries], ['Active', 'Expired'])

    def test_falls_back_to_the_most_recent_lapsed_contract(self):
        older = self._contract(self.renewal_tenant, self.vacant_stall, 'Expired', date(2024, 1, 1))
        newer = self._contract(self.renewal_tenant, self.occupied_stall, 'Terminated', date(2025, 1, 1))
        entries = RentalContractForm._assigned_stall_map()[str(self.renewal_tenant.pk)]
        self.assertEqual(entries[0]['stall'], str(newer.stall_id))
        self.assertNotEqual(entries[0]['stall'], str(older.stall_id))

    def test_assigned_vacant_stall_is_offered_in_the_new_form(self):
        self._contract(self.renewal_tenant, self.vacant_stall, 'Expired', date(2024, 1, 1))
        offered = set(RentalContractForm().fields['stalls'].queryset.values_list('pk', flat=True))
        self.assertIn(self.vacant_stall.pk, offered)
        self.assertNotIn(self.occupied_stall.pk, offered)

    def test_widget_exposes_assignment_map_for_the_frontend(self):
        self._contract(self.tenant, self.occupied_stall, 'Active', date(2026, 1, 1))
        form = RentalContractForm()
        emitted = json.loads(form.fields['tenant'].widget.attrs['data-assigned-stalls'])
        self.assertEqual(emitted[str(self.tenant.pk)][0]['number'], 'RGS-01')
        self.assertIn('data-assigned-stalls', str(form['tenant']))


class ContractStallChoiceTests(TestCase):
    """A new contract picks from a vacant-only checklist; an edit keeps one stall."""

    @classmethod
    def setUpTestData(cls):
        cls.section, _ = MarketSection.objects.get_or_create(name='Grocery Section')
        cls.vacant = Stall.objects.create(stall_number='GS-21', section=cls.section,
                                          monthly_rate=1200, status='Vacant')
        cls.occupied = Stall.objects.create(stall_number='GS-22', section=cls.section,
                                            monthly_rate=1400, status='Occupied')
        cls.reserved = Stall.objects.create(stall_number='GS-23', section=cls.section,
                                            monthly_rate=1600, status='Reserved')
        # Vacant on the status column yet still under an Active contract.
        cls.drifted = Stall.objects.create(stall_number='GS-24', section=cls.section,
                                           monthly_rate=800, status='Vacant')
        cls.tenant = Tenant.objects.create(tenant_id='TEN-103', full_name='Chooser',
                                           address='Poblacion', contact_number='09000000103',
                                           status='Active')
        RentalContract.objects.create(tenant=cls.tenant, stall=cls.drifted, status='Active',
                                      start_date=date(2026, 1, 1), monthly_rent=800,
                                      due_day=5, security_deposit=0)

    def test_new_form_offers_only_assignable_vacant_stalls(self):
        offered = {stall.stall_number
                   for stall in RentalContractForm().fields['stalls'].queryset}
        self.assertEqual(offered, {'GS-21'})

    def test_checklist_renders_each_stall_with_its_rate(self):
        rendered = str(RentalContractForm()['stalls'])
        self.assertIn('GS-21', rendered)
        self.assertIn('1200', rendered)
        self.assertIn('name="stalls"', rendered)

    def test_edit_form_keeps_the_single_stall_select(self):
        contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.occupied, status='Active', start_date=date(2026, 1, 1),
            monthly_rent=1400, due_day=5, security_deposit=0)
        form = RentalContractForm(instance=contract)
        self.assertNotIn('stalls', form.fields)
        offered = {stall.stall_number for stall in form.fields['stall'].queryset}
        # The stall being edited stays selectable even though it is Occupied.
        self.assertLessEqual({'GS-21', 'GS-22'}, offered)
        self.assertNotIn('GS-23', offered)


class MultiStallContractTests(TestCase):
    """A tenant may rent several stalls at once, as long as each stall is free."""

    @classmethod
    def setUpTestData(cls):
        cls.section, _ = MarketSection.objects.get_or_create(name='Dry Goods Section')
        cls.held = Stall.objects.create(stall_number='DGS-01', section=cls.section,
                                        monthly_rate=1500, status='Occupied')
        cls.free = Stall.objects.create(stall_number='DGS-02', section=cls.section,
                                        monthly_rate=1750, status='Vacant')
        cls.also_free = Stall.objects.create(stall_number='DGS-03', section=cls.section,
                                             monthly_rate=2250, status='Vacant')
        cls.tenant = Tenant.objects.create(
            tenant_id='TEN-201', full_name='Multi Stall Merchant', address='Poblacion',
            contact_number='09000000201', status='Active')
        cls.existing = RentalContract.objects.create(
            tenant=cls.tenant, stall=cls.held, status='Active', start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), monthly_rent=1500, due_day=5, security_deposit=3000)

    def _payload(self, stalls, **overrides):
        data = {
            'tenant': self.tenant.pk,
            'stalls': [str(stall.pk) for stall in stalls],
            'start_date': '2026-10-01', 'end_date': '2027-09-30',
            'due_day': 5, 'security_deposit': '1500', 'status': 'Active', 'remarks': '',
        }
        data.update(overrides)
        return data

    def test_ticking_two_stalls_creates_one_contract_for_each(self):
        form = RentalContractForm(data=self._payload([self.free, self.also_free]))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertCountEqual(
            [c.stall.stall_number for c in form.saved_contracts], ['DGS-02', 'DGS-03'])
        self.assertEqual(self.tenant.contracts.filter(status='Active').count(), 3)

    def test_each_contract_takes_its_own_stall_rate(self):
        form = RentalContractForm(data=self._payload([self.free, self.also_free]))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        rents = {c.stall.stall_number: c.monthly_rent for c in form.saved_contracts}
        self.assertEqual(rents, {'DGS-02': Decimal('1750.00'), 'DGS-03': Decimal('2250.00')})

    def test_a_typed_rent_is_honoured_for_a_single_stall(self):
        form = RentalContractForm(data=self._payload([self.free], monthly_rent='999.00'))
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(contract.monthly_rent, Decimal('999.00'))

    def test_blank_rent_falls_back_to_the_stall_rate(self):
        form = RentalContractForm(data=self._payload([self.free]))
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(contract.monthly_rent, Decimal('1750.00'))

    def test_at_least_one_stall_is_required(self):
        form = RentalContractForm(data=self._payload([]))
        self.assertFalse(form.is_valid())
        self.assertIn('at least one vacant stall', str(form.errors))

    def test_a_stall_taken_between_render_and_submit_is_rejected(self):
        RentalContract.objects.create(tenant=self.tenant, stall=self.also_free, status='Active',
                                      start_date=date(2026, 10, 1), monthly_rent=2250,
                                      due_day=5, security_deposit=0)
        form = RentalContractForm(data=self._payload([self.free, self.also_free]))
        self.assertFalse(form.is_valid())
        self.assertIn('not one of the available choices', str(form.errors))

    def test_second_active_contract_for_the_same_tenant_is_accepted(self):
        form = RentalContractForm(data=self._payload([self.free]))
        self.assertTrue(form.is_valid(), form.errors)
        contract = form.save()
        self.assertEqual(self.tenant.contracts.filter(status='Active').count(), 2)
        self.assertEqual(contract.stall, self.free)

    def test_stall_that_already_has_an_active_contract_is_rejected(self):
        other = Tenant.objects.create(tenant_id='TEN-202', full_name='Other Merchant',
                                      address='Poblacion', contact_number='09000000202',
                                      status='Active')
        payload = self._payload([self.held])
        payload['tenant'] = other.pk
        form = RentalContractForm(data=payload)
        self.assertFalse(form.is_valid())
        # The Vacant-only checklist rejects it up front, and the DB per-stall
        # constraint backs that up.
        self.assertIn('not one of the available choices', str(form.errors))
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RentalContract.objects.create(
                    tenant=other, stall=self.held, status='Active',
                    start_date=date(2026, 10, 1), end_date=date(2027, 9, 30),
                    monthly_rent=1500, due_day=5, security_deposit=3000)


class ContractAddViewTests(TestCase):
    """The new-contract screen posts a vacant-stall checklist, page and modal alike."""

    @classmethod
    def setUpTestData(cls):
        cls.section, _ = MarketSection.objects.get_or_create(name='Grocery Section')
        cls.free_a = Stall.objects.create(stall_number='GS-31', section=cls.section,
                                          monthly_rate=1200, status='Vacant')
        cls.free_b = Stall.objects.create(stall_number='GS-32', section=cls.section,
                                          monthly_rate=1800, status='Vacant')
        cls.taken = Stall.objects.create(stall_number='GS-33', section=cls.section,
                                         monthly_rate=2400, status='Occupied')
        cls.tenant = Tenant.objects.create(tenant_id='TEN-401', full_name="Anne O'Keefe",
                                           address='Poblacion, Dumingag',
                                           contact_number='09000000401', status='Active')

    def setUp(self):
        self.admin = User.objects.create_user(username='encoder', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def _payload(self, stalls):
        return {
            'tenant': self.tenant.pk,
            'stalls': [str(stall.pk) for stall in stalls],
            'start_date': '2026-10-01', 'end_date': '2027-09-30',
            'due_day': 5, 'security_deposit': '1000', 'status': 'Active', 'remarks': '',
        }

    def test_get_lists_only_assignable_stalls_as_a_checklist(self):
        resp = self.client.get('/contracts/add/')
        offered = {stall.pk for stall in resp.context['form'].fields['stalls'].queryset}
        self.assertEqual(offered, {self.free_a.pk, self.free_b.pk})

    def test_page_post_creates_billable_contracts_and_logs_the_batch(self):
        resp = self.client.post('/contracts/add/', self._payload([self.free_a, self.free_b]),
                                follow=True)
        self.assertEqual(resp.redirect_chain[0][0], '/contracts/')
        contracts = self.tenant.contracts.order_by('stall__stall_number')
        self.assertEqual([str(c.monthly_rent) for c in contracts], ['1200.00', '1800.00'])
        self.assertEqual(Billing.objects.filter(contract__in=contracts).count(), 2)
        for stall in (self.free_a, self.free_b):
            stall.refresh_from_db()
            self.assertEqual(stall.status, 'Occupied')
        self.assertIn('Created 2 contracts', ' '.join(str(m) for m in resp.context['messages']))
        self.assertEqual(AuditLog.objects.filter(action='BULK_ASSIGN').count(), 1)

    def test_a_stall_held_by_another_contract_is_rejected_without_side_effects(self):
        resp = self.client.post('/contracts/add/', self._payload([self.free_a, self.taken]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tenant.contracts.count(), 0)

    def test_nothing_ticked_re_renders_the_form_with_the_selection_hint(self):
        resp = self.client.post('/contracts/add/', self._payload([]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('at least one vacant stall', str(resp.context['form'].errors))

    def test_modal_post_reports_the_count_in_the_toast(self):
        resp = self.client.post('/contracts/add-modal/', self._payload([self.free_a, self.free_b]),
                                headers={'hx-request': 'true'})
        self.assertIn('Created 2 contracts for Anne O', resp.content.decode())
        self.assertEqual(self.tenant.contracts.count(), 2)
        self.assertEqual(AuditLog.objects.filter(action='BULK_ASSIGN').count(), 1)
