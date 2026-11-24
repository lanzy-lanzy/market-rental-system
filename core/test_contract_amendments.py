from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from core.forms import BulkAssignStallsForm, ContractAmendmentForm
from core.models import (
    AuditLog, ContractAmendment, MarketSection, RentalContract,
    Stall, SystemSetting, Tenant, UserProfile,
)


class ContractAmendmentTests(TestCase):
    """Coverage for contract renovation/expansion notice and rate amendment workflow."""

    @classmethod
    def setUpTestData(cls):
        SystemSetting.objects.get_or_create(
            municipality_name='Municipality of Dumingag',
            market_name='Dumingag Public Market',
            office_name='Office of the Market Administrator',
            receipt_prefix='MR-',
        )
        cls.section, _ = MarketSection.objects.get_or_create(name='Dry Goods Section')
        cls.stall = Stall.objects.create(
            stall_number='AM-01', section=cls.section, monthly_rate=Decimal('1500.00'), status='Occupied'
        )
        cls.vacant_stall = Stall.objects.create(
            stall_number='AM-02', section=cls.section, monthly_rate=Decimal('1800.00'), status='Vacant'
        )
        cls.tenant = Tenant.objects.create(
            tenant_id='TEN-601', full_name='Maria Santos', address='Poblacion, Dumingag',
            contact_number='09170000601', status='Active',
        )
        cls.contract = RentalContract.objects.create(
            tenant=cls.tenant,
            stall=cls.stall,
            start_date=date(2026, 1, 15),
            monthly_rent=Decimal('1500.00'),
            due_day=5,
            security_deposit=Decimal('3000.00'),
            status='Active',
        )

    def setUp(self):
        self.admin = User.objects.create_user(username='market_admin', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def test_amendment_form_validates_rent_and_effective_date(self):
        # Same rent rejected
        same_rent = ContractAmendmentForm(
            data={
                'reason': 'renovation',
                'effective_date': '2026-06-01',
                'new_monthly_rent': '1500.00',
                'remarks': 'No change',
            },
            contract=self.contract,
        )
        self.assertFalse(same_rent.is_valid())
        self.assertIn('new_monthly_rent', same_rent.errors)

        # Effective date before contract start_date rejected
        early_date = ContractAmendmentForm(
            data={
                'reason': 'expansion',
                'effective_date': '2025-12-01',
                'new_monthly_rent': '2000.00',
                'remarks': 'Too early',
            },
            contract=self.contract,
        )
        self.assertFalse(early_date.is_valid())
        self.assertIn('effective_date', early_date.errors)

        # Valid amendment
        valid = ContractAmendmentForm(
            data={
                'reason': 'expansion',
                'effective_date': '2026-06-01',
                'new_monthly_rent': '2100.00',
                'remarks': 'Expanded stall floor area by 4 sqm',
            },
            contract=self.contract,
        )
        self.assertTrue(valid.is_valid(), valid.errors)

    def test_amend_view_updates_monthly_rent_and_records_history_and_audit(self):
        get_resp = self.client.get(f'/contracts/{self.contract.pk}/amend/')
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Amend Contract Rate')

        post_resp = self.client.post(f'/contracts/{self.contract.pk}/amend/', {
            'reason': 'renovation',
            'effective_date': '2026-05-01',
            'new_monthly_rent': '1850.00',
            'remarks': 'Roof and counter renovation completed',
        })
        self.assertRedirects(post_resp, f'/contracts/{self.contract.pk}/')

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.monthly_rent, Decimal('1850.00'))

        amendment = ContractAmendment.objects.get(contract=self.contract)
        self.assertEqual(amendment.reason, 'renovation')
        self.assertEqual(amendment.previous_monthly_rent, Decimal('1500.00'))
        self.assertEqual(amendment.new_monthly_rent, Decimal('1850.00'))
        self.assertEqual(amendment.effective_date, date(2026, 5, 1))
        self.assertEqual(amendment.created_by, self.admin)

        audit = AuditLog.objects.filter(action='AMEND_RATE', module='RentalContract').first()
        self.assertIsNotNone(audit)
        self.assertIn('1500.00 -> ₱1850.00', audit.description)

    def test_amend_view_htmx_modal_flow(self):
        get_resp = self.client.get(
            f'/contracts/{self.contract.pk}/amend/',
            headers={'hx-request': 'true'},
        )
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'hx-post=')

        post_resp = self.client.post(
            f'/contracts/{self.contract.pk}/amend/',
            {
                'reason': 'expansion',
                'effective_date': '2026-07-01',
                'new_monthly_rent': '2200.00',
                'remarks': 'Added adjacent display bay',
            },
            headers={'hx-request': 'true'},
        )
        self.assertEqual(post_resp.status_code, 200)
        body = post_resp.content.decode()
        self.assertIn('closeModal()', body)
        self.assertIn('Stall Expansion', body)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.monthly_rent, Decimal('2200.00'))

    def test_tenant_user_cannot_amend_contract(self):
        tenant_user = User.objects.create_user(username='tenant_u', password='Tenant!Pass123')
        UserProfile.objects.create(user=tenant_user, role='tenant')
        self.client.force_login(tenant_user)

        resp = self.client.post(f'/contracts/{self.contract.pk}/amend/', {
            'reason': 'renovation',
            'effective_date': '2026-05-01',
            'new_monthly_rent': '100.00',
            'remarks': 'Unauthorized attempt',
        })
        self.assertNotEqual(resp.status_code, 200)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.monthly_rent, Decimal('1500.00'))
        self.assertEqual(ContractAmendment.objects.count(), 0)

    def test_detail_and_print_views_show_end_date_notice_and_amendment_history(self):
        ContractAmendment.objects.create(
            contract=self.contract,
            reason='expansion',
            effective_date=date(2026, 6, 1),
            previous_monthly_rent=Decimal('1500.00'),
            new_monthly_rent=Decimal('2100.00'),
            remarks='Corner stall expansion',
            created_by=self.admin,
        )
        self.contract.monthly_rent = Decimal('2100.00')
        self.contract.save(update_fields=['monthly_rent'])

        detail_resp = self.client.get(f'/contracts/{self.contract.pk}/')
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'End of Contract')
        self.assertContains(detail_resp, 'January 15, 2029')
        self.assertContains(detail_resp, 'subject to change')
        self.assertContains(detail_resp, 'Stall Expansion')
        self.assertContains(detail_resp, 'Corner stall expansion')

        print_resp = self.client.get(f'/contracts/{self.contract.pk}/print/')
        self.assertEqual(print_resp.status_code, 200)
        self.assertContains(print_resp, 'End of Contract')
        self.assertContains(print_resp, 'January 15, 2029')
        self.assertContains(print_resp, 'subject to change')
        self.assertContains(print_resp, 'Rate &amp; Terms Amendment History')
        self.assertContains(print_resp, 'Corner stall expansion')

        list_resp = self.client.get('/contracts/')
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'End of Contract')
        self.assertContains(list_resp, 'Jan 15, 2029')

    def test_bulk_assign_defaults_end_date_to_three_years(self):
        form = BulkAssignStallsForm(data={
            'tenant': self.tenant.pk,
            'stalls': [str(self.vacant_stall.pk)],
            'start_date': '2026-04-01',
            'end_date': '',
            'due_day': 5,
            'security_deposit': '500',
            'remarks': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['end_date'], date(2029, 4, 1))
