# core/test_bulk_assign.py
# Coverage for the one-to-many tenant -> stalls assignment.
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from core.forms import BulkAssignStallsForm
from core.models import (
    AuditLog, Billing, MarketSection, RentalContract, Stall, Tenant, UserProfile,
)


class BulkAssignStallsFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.section = MarketSection.objects.create(name='Dry Goods Section')
        cls.free_a = Stall.objects.create(stall_number='DGS-11', section=cls.section,
                                          monthly_rate=1500, status='Vacant')
        cls.free_b = Stall.objects.create(stall_number='DGS-12', section=cls.section,
                                          monthly_rate=2250, status='Vacant')
        cls.occupied = Stall.objects.create(stall_number='DGS-13', section=cls.section,
                                            monthly_rate=1800, status='Occupied')
        # Vacant on the status column yet still carrying an Active contract,
        # which is exactly the drift the per-stall DB constraint would reject.
        cls.drifted = Stall.objects.create(stall_number='DGS-14', section=cls.section,
                                           monthly_rate=900, status='Vacant')
        cls.tenant = Tenant.objects.create(tenant_id='TEN-301', full_name='Two Stall Merchant',
                                           address='Poblacion, Dumingag',
                                           contact_number='09000000301', status='Active')
        RentalContract.objects.create(tenant=cls.tenant, stall=cls.drifted, status='Active',
                                      start_date=date(2026, 1, 1), monthly_rent=900,
                                      due_day=5, security_deposit=0)

    def _payload(self, stall_ids, **overrides):
        data = {
            'tenant': self.tenant.pk,
            'stalls': [str(stall.pk) for stall in stall_ids],
            'start_date': '2026-10-01',
            'due_day': 5,
            'security_deposit': '500',
            'remarks': '',
        }
        data.update(overrides)
        return data

    def test_offers_only_stalls_that_can_take_an_active_contract(self):
        offered = {stall.stall_number
                   for stall in BulkAssignStallsForm().fields['stalls'].queryset}
        self.assertEqual(offered, {'DGS-11', 'DGS-12'})

    def test_several_vacant_stalls_validate_in_one_submission(self):
        form = BulkAssignStallsForm(data=self._payload([self.free_a, self.free_b]))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertCountEqual(form.cleaned_data['stalls'], [self.free_a, self.free_b])

    def test_at_least_one_stall_is_required(self):
        form = BulkAssignStallsForm(data=self._payload([]))
        self.assertFalse(form.is_valid())
        self.assertIn('at least one vacant stall', str(form.errors))

    def test_a_stall_holding_an_active_contract_cannot_be_chosen(self):
        form = BulkAssignStallsForm(data=self._payload([self.drifted]))
        self.assertFalse(form.is_valid())
        self.assertIn('not one of the available choices', str(form.errors))

    def test_end_date_must_be_after_the_start_date(self):
        form = BulkAssignStallsForm(data=self._payload(
            [self.free_a], end_date='2026-10-01'))
        self.assertFalse(form.is_valid())
        self.assertIn('later than the start date', str(form.errors))

        valid = BulkAssignStallsForm(data=self._payload(
            [self.free_a], end_date='2027-09-30'))
        self.assertTrue(valid.is_valid(), valid.errors)

    def test_start_date_defaults_to_today(self):
        bound = BulkAssignStallsForm()['start_date']
        self.assertEqual(bound.value(), date.today())


class BulkAssignViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.section = MarketSection.objects.create(name='Fruit Section')
        cls.free_a = Stall.objects.create(stall_number='FS-11', section=cls.section,
                                          monthly_rate=1500, status='Vacant')
        cls.free_b = Stall.objects.create(stall_number='FS-12', section=cls.section,
                                          monthly_rate=2000, status='Vacant')
        cls.taken = Stall.objects.create(stall_number='FS-13', section=cls.section,
                                         monthly_rate=2500, status='Occupied')
        cls.tenant = Tenant.objects.create(tenant_id='TEN-302', full_name='Market Vendor',
                                           address='Poblacion, Dumingag',
                                           contact_number='09000000302', status='Active')

    def setUp(self):
        self.admin = User.objects.create_user(username='encoder', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def _payload(self, stalls, **overrides):
        data = {
            'tenant': self.tenant.pk,
            'stalls': [str(stall.pk) for stall in stalls],
            'start_date': '2026-10-01',
            'due_day': 5,
            'security_deposit': '1000',
            'remarks': 'Bulk assigned',
        }
        data.update(overrides)
        return data

    def test_creates_one_contract_per_stall_at_each_stalls_own_rate(self):
        resp = self.client.post('/contracts/bulk-assign/', self._payload([self.free_a, self.free_b]))
        self.assertEqual(resp.status_code, 302)

        contracts = self.tenant.contracts.order_by('stall__stall_number')
        self.assertEqual(contracts.count(), 2)
        self.assertTrue(all(c.status == 'Active' for c in contracts))
        self.assertEqual([str(c.monthly_rent) for c in contracts], ['1500.00', '2000.00'])
        for stall in (self.free_a, self.free_b):
            stall.refresh_from_db()
            self.assertEqual(stall.status, 'Occupied')
        self.assertEqual(Billing.objects.filter(contract__in=contracts).count(), 2)
        log = AuditLog.objects.filter(action='BULK_ASSIGN').first()
        self.assertIsNotNone(log)
        self.assertIn('FS-11', log.description)

    def test_an_occupied_stall_in_the_post_is_rejected_without_side_effects(self):
        resp = self.client.post('/contracts/bulk-assign/',
                                self._payload([self.free_a, self.taken]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tenant.contracts.count(), 0)
        self.free_a.refresh_from_db()
        self.assertEqual(self.free_a.status, 'Vacant')

    def test_a_stall_claimed_after_validation_rolls_the_whole_batch_back(self):
        def race_stall(*args, **kwargs):
            # Another encoder grabbed the stall between form validation and the lock.
            Stall.objects.filter(pk=self.free_a.pk).update(status='Occupied')
            return Stall.objects

        with mock.patch.object(Stall.objects, 'select_for_update', side_effect=race_stall):
            resp = self.client.post('/contracts/bulk-assign/', self._payload([self.free_a]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tenant.contracts.count(), 0)
        self.assertIn('no longer vacant', ' '.join(str(m) for m in resp.context['messages']))
        # The encoder's selection must survive the re-render.
        self.assertTrue(resp.context['form'].is_bound)
        self.assertEqual(resp.context['form'].data.getlist('stalls'), [str(self.free_a.pk)])

    def test_no_stalls_selected_is_rejected(self):
        resp = self.client.post('/contracts/bulk-assign/', self._payload([]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tenant.contracts.count(), 0)

    def test_tenant_query_parameter_prefills_the_tenant(self):
        resp = self.client.get(f'/contracts/bulk-assign/?tenant={self.tenant.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.context['form'].initial['tenant']), str(self.tenant.pk))
