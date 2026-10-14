from decimal import Decimal

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase

from core.forms import TenantForm
from core.helpers import recalc_billing_from_payments
from core.models import (
    Billing, MarketSection, Notice, Payment, RentalContract, Stall, SystemSetting,
    Tenant, TenantLedger, UserProfile,
)

SEED_STALLS = 20
SEED_TENANTS = 12
SEED_CONTRACTS = 11
CENT = Decimal('0.01')


def allowed_choices(form, name):
    """business_type carries choices on the field, valid_id_type only on its widget."""
    field = form.fields[name]
    choices = getattr(field, 'choices', None) or field.widget.choices
    return {value for value, _label in choices if value}


class SeedDataConsistencyTests(TestCase):
    """The seeded dataset must obey the same invariants the app enforces at runtime."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_data', '--reset', verbosity=0)
        cls.payments = Payment.objects.count()

    def test_reference_catalog_is_seeded(self):
        self.assertEqual(MarketSection.objects.count(), 8)
        self.assertEqual(Stall.objects.count(), SEED_STALLS)
        self.assertEqual(Tenant.objects.count(), SEED_TENANTS)
        self.assertEqual(RentalContract.objects.count(), SEED_CONTRACTS)
        self.assertTrue(SystemSetting.objects.exists())

    def test_tenants_store_split_names_and_composed_values(self):
        form = TenantForm()
        business_types = allowed_choices(form, 'business_type')
        id_types = allowed_choices(form, 'valid_id_type')
        for tenant in Tenant.objects.all():
            self.assertRegex(tenant.tenant_id, r'^TEN-\d{3}$')
            self.assertTrue(tenant.first_name and tenant.last_name)
            self.assertEqual(
                tenant.full_name,
                ' '.join(p for p in (tenant.first_name, tenant.middle_name, tenant.last_name) if p))
            self.assertEqual(
                tenant.address,
                ', '.join(p for p in (tenant.street, tenant.barangay, tenant.municipality,
                                      tenant.province) if p))
            self.assertIn(tenant.business_type, business_types)
            self.assertIn(tenant.valid_id_type, id_types)
            self.assertTrue(tenant.valid_id_number)

    def test_every_tenant_has_a_matching_login(self):
        for tenant in Tenant.objects.all():
            user = tenant.user
            self.assertIsNotNone(user, f'{tenant.tenant_id} has no login')
            self.assertEqual(user.username, tenant.tenant_id)
            self.assertEqual(user.first_name, tenant.first_name)
            self.assertEqual(UserProfile.objects.get(user=user).role, 'tenant')

    def test_active_contract_is_unique_per_stall_and_drives_stall_status(self):
        for stall in Stall.objects.all():
            active = RentalContract.objects.filter(stall=stall, status='Active')
            self.assertLessEqual(active.count(), 1, f'{stall.stall_number} has multiple active contracts')
            if active.exists():
                self.assertEqual(stall.status, 'Occupied')
            else:
                self.assertNotEqual(stall.status, 'Occupied')

    def test_billing_totals_match_the_posted_payments(self):
        for billing in Billing.objects.all():
            collected = Decimal(
                Payment.objects.filter(billing=billing, status__in=['Paid', 'Partial'])
                .aggregate(total=Sum('amount_paid'))['total'] or 0)
            applied = min(collected, Decimal(billing.total_due))
            self.assertEqual(Decimal(billing.amount_paid).quantize(CENT), applied.quantize(CENT),
                             f'billing {billing.pk} amount_paid')
            self.assertEqual(Decimal(billing.balance).quantize(CENT),
                             (Decimal(billing.total_due) - applied).quantize(CENT),
                             f'billing {billing.pk} balance')

    def test_ledger_balance_closes_on_the_outstanding_total(self):
        for tenant in Tenant.objects.all():
            entries = TenantLedger.objects.filter(tenant=tenant)
            if not entries.exists():
                continue
            running = sum((Decimal(e.debit) - Decimal(e.credit) for e in entries), Decimal('0.00'))
            outstanding = sum((Decimal(b.balance) for b in Billing.objects.filter(tenant=tenant)),
                              Decimal('0.00'))
            self.assertEqual(running.quantize(CENT), outstanding.quantize(CENT),
                             f'ledger drift for {tenant.tenant_id}')

    def test_recalculation_helper_is_a_no_op_on_seeded_amounts(self):
        # Status may legitimately read Overdue once the accrual run has dated a
        # partially paid bill, so only the money must be stable.
        for billing in Billing.objects.filter(payments__isnull=False).distinct()[:10]:
            before = (Decimal(billing.amount_paid), Decimal(billing.balance))
            after = recalc_billing_from_payments(billing)
            self.assertEqual(
                (Decimal(after.amount_paid), Decimal(after.balance)), before,
                f'recalc moved billing {billing.pk}')

    def test_receipts_are_unique_and_prefixed(self):
        prefix = SystemSetting.objects.first().receipt_prefix.rstrip('-')
        numbers = list(Payment.objects.values_list('receipt_number', flat=True))
        self.assertTrue(numbers, 'no payments seeded')
        self.assertEqual(len(numbers), len(set(numbers)))
        for number in numbers:
            self.assertTrue(number.startswith(f'{prefix}-'), number)

    def test_open_balances_produce_printable_notices(self):
        self.assertTrue(Notice.objects.exists())
        for notice in Notice.objects.all():
            self.assertTrue(notice.content.strip())
            self.assertIn(notice.tenant.full_name, notice.content)

    def test_seeding_twice_does_not_duplicate_rows(self):
        call_command('seed_data', verbosity=0)
        self.assertEqual(Tenant.objects.count(), SEED_TENANTS)
        self.assertEqual(Stall.objects.count(), SEED_STALLS)
        self.assertEqual(RentalContract.objects.count(), SEED_CONTRACTS)
        self.assertEqual(Payment.objects.count(), self.payments)
        self.assertEqual(Billing.objects.count(), Billing.objects.values(
            'tenant', 'stall', 'billing_month', 'billing_year').distinct().count())
