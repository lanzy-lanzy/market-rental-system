from datetime import date

from django.test import TestCase

from core.forms import RentalContractForm
from core.models import MarketSection, RentalContract, Stall, Tenant


class AssignedStallMapTests(TestCase):
    """Regression coverage for the tenant -> stall auto-select in the contract form."""

    @classmethod
    def setUpTestData(cls):
        cls.section = MarketSection.objects.create(name='Vegetable Section')
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

    def _contract(self, tenant, stall, status, start, end):
        return RentalContract.objects.create(
            tenant=tenant, stall=stall, status=status, start_date=start, end_date=end,
            monthly_rent=stall.monthly_rate, due_day=5, security_deposit=1000)

    def test_prefers_active_contract_and_its_rate(self):
        self._contract(self.tenant, self.occupied_stall, 'Active', date(2026, 1, 1), date(2026, 12, 31))
        mapping = RentalContractForm._assigned_stall_map()
        entry = mapping[str(self.tenant.pk)]
        self.assertEqual(entry['stall'], str(self.occupied_stall.pk))
        self.assertEqual(entry['number'], 'RGS-01')
        self.assertEqual(entry['rate'], '3000.00')

    def test_falls_back_to_most_recent_expired_contract(self):
        old = self._contract(self.renewal_tenant, self.vacant_stall, 'Expired', date(2024, 1, 1), date(2024, 12, 31))
        newer = self._contract(self.renewal_tenant, self.occupied_stall, 'Terminated', date(2025, 1, 1), date(2025, 12, 31))
        mapping = RentalContractForm._assigned_stall_map()
        self.assertEqual(mapping[str(self.renewal_tenant.pk)]['stall'], str(newer.stall_id))
        self.assertNotEqual(mapping[str(self.renewal_tenant.pk)]['stall'], str(old.stall_id))

    def test_assigned_vacant_stall_is_selectable_in_new_form(self):
        self._contract(self.renewal_tenant, self.vacant_stall, 'Expired', date(2024, 1, 1), date(2024, 12, 31))
        form = RentalContractForm()
        stall_values = {str(pk) for pk in form.fields['stall'].queryset.values_list('pk', flat=True)}
        self.assertIn(str(self.vacant_stall.pk), stall_values)
        self.assertNotIn(str(self.occupied_stall.pk), stall_values)

    def test_widget_exposes_assignment_map_for_the_frontend(self):
        self._contract(self.tenant, self.occupied_stall, 'Active', date(2026, 1, 1), date(2026, 12, 31))
        form = RentalContractForm()
        import json
        emitted = json.loads(form.fields['tenant'].widget.attrs['data-assigned-stalls'])
        self.assertEqual(emitted[str(self.tenant.pk)]['number'], 'RGS-01')
        rendered = str(form['tenant'])
        self.assertIn('data-assigned-stalls', rendered)
