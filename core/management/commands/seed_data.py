"""Seed fresh, model-accurate demo data for the Public Market Rental System.

Financial rows are written through core.helpers (get_or_create_billing,
record_payment, apply_overdue_penalties) so Billing, Payment and TenantLedger
always agree with each other.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.forms import TenantForm
from core.helpers import (
    apply_overdue_penalties,
    get_or_create_billing,
    record_payment,
    safe_due_date,
)
from core.models import (
    AuditLog,
    Billing,
    MarketSection,
    Notice,
    PenaltySetting,
    RentalContract,
    Stall,
    StallType,
    SystemSetting,
    Tenant,
    UserProfile,
)

STAFF_PASSWORDS = {
    'admin': ('admin123', 'Market Administrator', 'admin', ''),
    'collector1': ('collector123', 'Juan Santos', 'collector', '09171234567'),
    'cashier1': ('cashier123', 'Rosa Mendoza', 'cashier', '09171234568'),
    'supervisor1': ('supervisor123', 'Maria Cruz', 'supervisor', '09171234569'),
    'treasurer1': ('treasurer123', 'Pedro Reyes', 'treasurer', '09171234570'),
}

TENANT_PASSWORD = 'tenant123'
MONTHS_BACK = 4

SECTIONS = [
    'Dry Goods Section',
    'Fish Section',
    'Meat Section',
    'Vegetable Section',
    'Fruit Section',
    'Eatery/Carenderia Section',
    'Grocery Section',
    'Rice and Grains Section',
]

STALL_TYPES = [
    ('Regular Stall', 'Standard 4 sqm stall'),
    ('Premium Stall', 'Larger stall in a premium location'),
    ('Kiosk', 'Small kiosk space'),
    ('Table Space', 'Table-only selling space'),
]

# (number, section, type, size sqm, monthly rate)
STALLS = [
    ('DGS-01', 'Dry Goods Section', 'Regular Stall', 4, 1500),
    ('DGS-02', 'Dry Goods Section', 'Regular Stall', 4, 1500),
    ('DGS-03', 'Dry Goods Section', 'Kiosk', 3, 1000),
    ('FS-01', 'Fish Section', 'Premium Stall', 6, 2500),
    ('FS-02', 'Fish Section', 'Regular Stall', 4, 1800),
    ('FS-03', 'Fish Section', 'Table Space', 2, 800),
    ('MS-01', 'Meat Section', 'Premium Stall', 6, 3000),
    ('MS-02', 'Meat Section', 'Regular Stall', 4, 2000),
    ('VS-01', 'Vegetable Section', 'Regular Stall', 4, 1200),
    ('VS-02', 'Vegetable Section', 'Regular Stall', 4, 1200),
    ('VS-03', 'Vegetable Section', 'Table Space', 2, 600),
    ('FRS-01', 'Fruit Section', 'Regular Stall', 4, 1300),
    ('FRS-02', 'Fruit Section', 'Table Space', 2, 700),
    ('ECS-01', 'Eatery/Carenderia Section', 'Premium Stall', 8, 2800),
    ('ECS-02', 'Eatery/Carenderia Section', 'Kiosk', 3, 1500),
    ('ECS-03', 'Eatery/Carenderia Section', 'Kiosk', 3, 1500),
    ('GS-01', 'Grocery Section', 'Premium Stall', 8, 3000),
    ('GS-02', 'Grocery Section', 'Regular Stall', 5, 2000),
    ('RGS-01', 'Rice and Grains Section', 'Regular Stall', 6, 1800),
    ('RGS-02', 'Rice and Grains Section', 'Kiosk', 3, 1000),
]

# Names and addresses are stored split, then composed into full_name/address the
# same way TenantForm.save() does, so seeded and hand-encoded tenants match.
TENANTS = [
    dict(tenant_id='TEN-001', first_name='Juan', middle_name='Dela', last_name='Cruz',
         street='Purok 4, Rizal Street', barangay='Poblacion', contact_number='09170000001',
         email='juan.delacruz@example.com', valid_id_type='National ID', valid_id_number='0123-4567-8901',
         business_name='Juan Rice Trading', business_type='Rice and Grains',
         emergency_contact_name='Ana Cruz', emergency_contact_number='09170000011'),
    dict(tenant_id='TEN-002', first_name='Maria', middle_name='San', last_name='Santos',
         street='Bonifacio Avenue', barangay='Baranduan', contact_number='09170000002',
         email='maria.santos@example.com', valid_id_type='Driver License', valid_id_number='N01-23-456789',
         business_name='Maria Fresh Fish', business_type='Fish and Seafood',
         emergency_contact_name='Lourdes San', emergency_contact_number='09170000012'),
    dict(tenant_id='TEN-003', first_name='Pedro', middle_name='', last_name='Reyes',
         street='Mabini Street', barangay='Buisel', contact_number='09170000003',
         email='pedro.reyes@example.com', valid_id_type='UMID', valid_id_number='12-345678-9',
         business_name='Reyes Meat Shop', business_type='Meat and Poultry',
         emergency_contact_name='Celia Reyes', emergency_contact_number='09170000013'),
    dict(tenant_id='TEN-004', first_name='Ana', middle_name='L.', last_name='Gonzales',
         street='Luna Street', barangay='Cumog', contact_number='09170000004',
         email='ana.gonzales@example.com', valid_id_type='Postal ID', valid_id_number='PS-5566771',
         business_name="Ana's Fresh Produce", business_type='Vegetables',
         emergency_contact_name='Rosa Gonzales', emergency_contact_number='09170000014'),
    dict(tenant_id='TEN-005', first_name='Jose', middle_name='R.', last_name='Rizal',
         street='Del Pilar Street', barangay='Dalupit', contact_number='09170000005',
         email='jose.rizal@example.com', valid_id_type='Passport', valid_id_number='P4433221X',
         business_name="Jose's Fruit Stand", business_type='Fruits',
         emergency_contact_name='Emily Rizal', emergency_contact_number='09170000015'),
    dict(tenant_id='TEN-006', first_name='Luzviminda', middle_name='', last_name='Mercado',
         street='Aguinaldo Street', barangay='Gapo', contact_number='09170000006',
         email='luz.mercado@example.com', valid_id_type='Barangay ID', valid_id_number='BRG-2024-0087',
         business_name="Luz's Carenderia", business_type='Eatery / Carenderia',
         emergency_contact_name='Nena Mercado', emergency_contact_number='09170000016'),
    dict(tenant_id='TEN-007', first_name='Antonio', middle_name='B.', last_name='Lopez',
         street='Jacinto Street', barangay='Gumel', contact_number='09170000007',
         email='antonio.lopez@example.com', valid_id_type='SSS ID', valid_id_number='33-4444444-4',
         business_name='Antonio Dry Goods', business_type='Dry Goods',
         emergency_contact_name='Pacencia Lopez', emergency_contact_number='09170000017'),
    dict(tenant_id='TEN-008', first_name='Teresa', middle_name='', last_name='Villanueva',
         street='Natividad Street', barangay='Langap', contact_number='09170000008',
         email='teresa.villanueva@example.com', valid_id_type='GSIS ID', valid_id_number='G-88991122',
         business_name="Teresa's Store", business_type='Grocery / Sari-sari Store',
         emergency_contact_name='Imelda Villanueva', emergency_contact_number='09170000018'),
    dict(tenant_id='TEN-009', first_name='Ramiro', middle_name='S.', last_name='Tolentino',
         street='Sakmar Street', barangay='Napilan', contact_number='09170000009',
         email='ramiro.tolentino@example.com', valid_id_type='PRC ID', valid_id_number='0123456',
         business_name='Tolentino Tailoring', business_type='Clothing / Apparel',
         emergency_contact_name='Josefina Tolentino', emergency_contact_number='09170000019'),
    dict(tenant_id='TEN-010', first_name='Fe', middle_name='', last_name='Alcantara',
         street='Real Street', barangay='Santa Cruz', contact_number='09170000010',
         email='fe.alcantara@example.com', valid_id_type='PhilHealth ID', valid_id_number='99-0011223344',
         business_name='Alcantara Phone Repair', business_type='Services (Barber, Salon, Repair)',
         emergency_contact_name='Romeo Alcantara', emergency_contact_number='09170000020'),
    dict(tenant_id='TEN-011', first_name='Ernesto', middle_name='M.', last_name='Bautista',
         street='National Road', barangay='Santo Niño', contact_number='09170000011',
         email='ernesto.bautista@example.com', valid_id_type='National ID', valid_id_number='9876-5432-1098',
         business_name='Bautista Hardware', business_type='Others',
         emergency_contact_name='Rowena Bautista', emergency_contact_number='09170000021'),
    dict(tenant_id='TEN-012', first_name='Divina', middle_name='', last_name='Garcia',
         street='Magsaysay Street', barangay='Tapol', contact_number='09170000012',
         email='divina.garcia@example.com', valid_id_type='Driver License', valid_id_number='N02-11-223344',
         business_name='Garcia General Merchandise', business_type='Grocery / Sari-sari Store',
         emergency_contact_name='Cecilia Garcia', emergency_contact_number='09170000022'),
]

# tenant_id, stall, start offset in months, term in months, due day, status, deposit months
CONTRACTS = [
    ('TEN-001', 'RGS-01', -20, 36, 5, 'Active', 2),
    ('TEN-002', 'FS-01', -18, 36, 5, 'Active', 2),
    ('TEN-003', 'MS-02', -14, 24, 10, 'Active', 2),
    ('TEN-004', 'VS-02', -12, 24, 5, 'Active', 1),
    ('TEN-005', 'FRS-02', -10, 24, 15, 'Active', 1),
    ('TEN-006', 'ECS-02', -8, 24, 5, 'Active', 2),
    ('TEN-007', 'DGS-01', -6, 24, 5, 'Active', 2),
    ('TEN-008', 'GS-02', -5, 24, 20, 'Active', 1),
    ('TEN-009', 'VS-01', -14, 12, 5, 'Expired', 2),
    ('TEN-010', 'ECS-03', -20, 18, 5, 'Terminated', 1),
    ('TEN-011', 'MS-01', -1, 24, 5, 'Pending', 2),
]

# Oldest -> newest of the seeded months. 'paid' settles the balance, 'partial'
# pays 60%, 'none' leaves the bill open so the overdue/penalty run has work to do.
PAYMENT_PLANS = {
    'TEN-001': ['paid', 'paid', 'paid', 'paid'],
    'TEN-002': ['paid', 'paid', 'paid', 'partial'],
    'TEN-003': ['paid', 'paid', 'none', 'none'],
    'TEN-004': ['paid', 'none', 'none', 'none'],
    'TEN-005': ['none', 'none', 'none', 'none'],
    'TEN-006': ['paid', 'paid', 'partial', 'paid'],
    'TEN-007': ['paid', 'paid', 'paid', 'none'],
    'TEN-008': ['paid', 'paid', 'paid', 'paid'],
    'TEN-009': ['paid', 'paid', 'none', 'none'],
    'TEN-010': ['paid', 'none', 'none', 'none'],
}

# One active tenant is kept contract-free so the new-contract flow has a subject.
PENALTY_OVERRIDE_TENANT = 'TEN-005'
MAINTENANCE_STALL = 'DGS-03'


def compose(*parts, separator=', '):
    return separator.join(part.strip() for part in parts if part and part.strip())


class Command(BaseCommand):
    help = 'Seed the database with sample data for the Public Market Rental System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Flush every table first, then seed a fresh dataset.')

    def handle(self, *args, **options):
        self._validate_choice_fields()
        if options['reset']:
            call_command('flush', interactive=False)
            self.stdout.write(self.style.WARNING('Database flushed — seeding fresh data.'))

        today = date.today()
        months = [self._shift_month(today, -back) for back in range(MONTHS_BACK - 1, -1, -1)]

        self._create_system_settings()
        users = self._create_users()
        self._create_market_structure()
        tenants = self._create_tenants()
        contracts = self._create_contracts(tenants, today)
        self._create_billings(contracts, months)
        payments = self._create_payments(contracts, tenants, users, months, today)
        overdue, penalized = apply_overdue_penalties(today)
        notice_count = self._create_notices(tenants, today)
        self._create_audit_logs(users, tenants, payments, today)

        self.stdout.write(self.style.SUCCESS(
            f'\nSeed complete: {Tenant.objects.count()} tenants, {Stall.objects.count()} stalls, '
            f'{RentalContract.objects.count()} contracts, {Billing.objects.count()} billings, '
            f'{len(payments)} payments, {overdue} marked overdue, {penalized} penalties accrued, '
            f'{notice_count} notices.'))
        self.stdout.write('Staff logins:')
        for username, (password, _full_name, _role, _phone) in STAFF_PASSWORDS.items():
            self.stdout.write(f'  {username} / {password}')
        self.stdout.write(f'Tenant logins: TEN-001 … TEN-012 / {TENANT_PASSWORD}')

    def _validate_choice_fields(self):
        """Fail fast if demo rows drift from the dropdowns the forms actually offer."""
        form = TenantForm()
        for name in ('business_type', 'valid_id_type'):
            field = form.fields[name]
            # business_type sets choices on the field; valid_id_type only on its widget.
            choices = getattr(field, 'choices', None) or field.widget.choices
            allowed = {value for value, _label in choices if value}
            for row in TENANTS:
                if row[name] not in allowed:
                    raise CommandError(
                        f"{row['tenant_id']} sets {name}='{row[name]}', which is not one of the "
                        f"form choices: {', '.join(sorted(allowed))}")

    def _shift_month(self, anchor, offset):
        index = anchor.year * 12 + (anchor.month - 1) + offset
        return date(index // 12, index % 12 + 1, 1)

    def _get_or_none(self, model, **kwargs):
        try:
            return model.objects.get(**kwargs)
        except model.DoesNotExist:
            return None

    def _month_key(self, value):
        return (value.year, value.month)

    def _create_system_settings(self):
        if SystemSetting.objects.exists():
            return
        SystemSetting.objects.create(
            municipality_name='Municipality of Dumingag',
            market_name='Dumingag Public Market',
            office_name='Market Administration Office',
            receipt_prefix='DMPM-',
            default_due_day=5,
            penalty_type='percentage',
            penalty_value=Decimal('2.00'),
            grace_period=5,
            theme_color='#006627',
        )

    def _create_users(self):
        created = 0
        for username, (password, full_name, role, phone) in STAFF_PASSWORDS.items():
            user = self._get_or_none(User, username=username)
            if user is None:
                first, _, last = full_name.partition(' ')
                user = User.objects.create_user(
                    username=username, password=password, email=f'{username}@dumingag.example.com',
                    first_name=first, last_name=last,
                    is_staff=role == 'admin', is_superuser=role == 'admin')
                created += 1
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'role': role, 'phone': phone,
                          'address': 'Dumingag, Zamboanga del Sur', 'must_change_password': False})
        self.stdout.write(self.style.SUCCESS(f'Created {created} staff users'))
        return {username: self._get_or_none(User, username=username) for username in STAFF_PASSWORDS}

    def _create_market_structure(self):
        for name in SECTIONS:
            MarketSection.objects.get_or_create(name=name)
        for name, description in STALL_TYPES:
            StallType.objects.get_or_create(name=name, defaults={'description': description})

        sections = {section.name: section for section in MarketSection.objects.all()}
        types = {stall_type.name: stall_type for stall_type in StallType.objects.all()}
        created = 0
        for number, section, stall_type, size, rate in STALLS:
            _stall, was_created = Stall.objects.get_or_create(
                stall_number=number,
                defaults={'section': sections[section], 'stall_type': types[stall_type],
                          'size': Decimal(size), 'monthly_rate': Decimal(rate), 'status': 'Vacant'})
            created += was_created
        self.stdout.write(self.style.SUCCESS(
            f'Created {created} stalls across {len(sections)} sections'))

    def _create_tenants(self):
        tenants = {}
        for row in TENANTS:
            tenant = self._get_or_none(Tenant, tenant_id=row['tenant_id'])
            if tenant is None:
                address = compose(row['street'], row['barangay'], 'Dumingag', 'Zamboanga del Sur')
                tenant = Tenant.objects.create(
                    tenant_id=row['tenant_id'],
                    first_name=row['first_name'], middle_name=row['middle_name'],
                    last_name=row['last_name'],
                    full_name=compose(row['first_name'], row['middle_name'], row['last_name'],
                                      separator=' '),
                    street=row['street'], barangay=row['barangay'],
                    municipality='Dumingag', province='Zamboanga del Sur', address=address,
                    contact_number=row['contact_number'], email=row['email'],
                    valid_id_type=row['valid_id_type'], valid_id_number=row['valid_id_number'],
                    business_name=row['business_name'], business_type=row['business_type'],
                    emergency_contact_name=row['emergency_contact_name'],
                    emergency_contact_number=row['emergency_contact_number'],
                    status='Active')
                user = User.objects.create_user(
                    username=row['tenant_id'], password=TENANT_PASSWORD, email=row['email'],
                    first_name=row['first_name'], last_name=row['last_name'])
                UserProfile.objects.update_or_create(
                    user=user, defaults={'role': 'tenant', 'phone': row['contact_number'],
                                         'address': address, 'must_change_password': False})
                tenant.user = user
                tenant.save(update_fields=['user'])
            tenants[row['tenant_id']] = tenant
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(tenants)} tenants with tenant logins'))
        return tenants

    def _create_contracts(self, tenants, today):
        stalls = {stall.stall_number: stall for stall in Stall.objects.all()}
        contracts = {}
        created = 0
        for tenant_id, stall_number, start_offset, term_months, due_day, status, deposit in CONTRACTS:
            tenant, stall = tenants[tenant_id], stalls[stall_number]
            contract = RentalContract.objects.filter(tenant=tenant, stall=stall, status=status).first()
            if contract is None:
                start = self._shift_month(today, start_offset)
                contract = RentalContract.objects.create(
                    tenant=tenant, stall=stall, start_date=start,
                    end_date=start + timedelta(days=term_months * 30),
                    monthly_rent=stall.monthly_rate, due_day=due_day,
                    security_deposit=stall.monthly_rate * deposit, status=status,
                    remarks='Term lapsed — awaiting renewal.' if status == 'Expired' else '')
                created += 1
            contracts[(tenant.pk, stall.pk, status)] = contract

        # Stall status is derived from the contracts, never typed by hand.
        Stall.objects.update(status='Vacant')
        occupied, reserved = [], []
        for (_tenant_pk, stall_pk, status) in contracts:
            if status == 'Active':
                occupied.append(stall_pk)
            elif status == 'Pending':
                reserved.append(stall_pk)
        Stall.objects.filter(pk__in=occupied).update(status='Occupied')
        Stall.objects.filter(pk__in=reserved).update(status='Reserved')
        Stall.objects.filter(stall_number=MAINTENANCE_STALL).update(status='Maintenance')

        override_tenant = tenants.get(PENALTY_OVERRIDE_TENANT)
        override = next((contract for (tenant_pk, _stall_pk, status), contract in contracts.items()
                         if tenant_pk == override_tenant.pk and status == 'Active'), None)
        if override:
            PenaltySetting.objects.update_or_create(
                contract=override,
                defaults={'penalty_type': 'percentage', 'penalty_value': Decimal('3.00'),
                          'grace_period': 3, 'due_day': override.due_day, 'is_active': True})
        self.stdout.write(self.style.SUCCESS(f'Created {created} rental contracts'))
        return contracts

    def _create_billings(self, contracts, months):
        created = 0
        for contract in contracts.values():
            if contract.status == 'Pending':
                continue
            for month_start in months:
                month = self._month_key(month_start)
                if month < self._month_key(contract.start_date):
                    continue
                if contract.end_date and month > self._month_key(contract.end_date):
                    continue
                _billing, was_created = get_or_create_billing(
                    contract, month_start.month, month_start.year)
                created += was_created
        self.stdout.write(self.style.SUCCESS(f'Created {created} billings with matching ledger debits'))

    def _create_payments(self, contracts, tenants, users, months, today):
        collector, cashier = users['collector1'], users['cashier1']
        payments = []
        for contract in contracts.values():
            plan = PAYMENT_PLANS.get(contract.tenant.tenant_id)
            if plan is None or contract.status == 'Pending':
                continue
            for month_start, action in zip(months, plan):
                if action == 'none':
                    continue
                billing = Billing.objects.filter(
                    contract=contract, billing_month=month_start.month,
                    billing_year=month_start.year).first()
                # A billing that already carries payments stays as-is, so a second
                # seed run cannot top up partials or settle overdue balances.
                if billing is None or billing.balance <= 0 or billing.payments.exists():
                    continue
                balance = Decimal(billing.balance)
                amount = (balance if action == 'paid'
                          else (balance * Decimal('0.60')).quantize(Decimal('0.01')))
                due_date = safe_due_date(billing.billing_year, billing.billing_month, contract.due_day)
                with transaction.atomic():
                    payments.append(record_payment(
                        tenant=contract.tenant, billing=billing, amount=amount,
                        payment_date=min(due_date + timedelta(days=1), today),
                        payment_method=['Cash', 'GCash', 'Bank Transfer', 'Check'][len(payments) % 4],
                        collected_by=cashier if action == 'partial' else collector,
                        remarks='Partial settlement — balance carried over.'
                                if action == 'partial' else ''))
        self.stdout.write(self.style.SUCCESS(
            f'Recorded {len(payments)} payments through record_payment'))
        return payments

    def _create_notices(self, tenants, today):
        settings = SystemSetting.objects.first()
        prefix = settings.receipt_prefix.rstrip('-')
        open_billings = list(Billing.objects.filter(status__in=['Unpaid', 'Overdue', 'Partial'])
                             .select_related('tenant', 'stall', 'contract'))

        # Rank tenants by total exposure so the harsher notices go to the deeper
        # debtors, and keep one tenant per notice so the set reads like a real
        # collection drive instead of piling onto a single vendor.
        bills_by_tenant = {}
        for billing in open_billings:
            bills_by_tenant.setdefault(billing.tenant_id, []).append(billing)
        ranked = sorted(bills_by_tenant.values(),
                        key=lambda bills: -sum((Decimal(b.balance) for b in bills), Decimal('0.00')))
        drafts, served_tenants = [], []
        for notice_type, qualifies in (
                ('Final Demand', lambda bills: len(bills) >= 2),
                ('Overdue Notice', lambda bills: any(b.status == 'Overdue' for b in bills)),
                ('Payment Reminder', lambda bills: True)):
            for bills in ranked:
                tenant = bills[0].tenant
                if tenant.pk in served_tenants or not qualifies(bills):
                    continue
                served_tenants.append(tenant.pk)
                billing = max(bills, key=lambda b: Decimal(b.balance))
                drafts.append((notice_type, tenant, self._demand_text(settings, notice_type, billing)))
                break

        tenant = tenants['TEN-009']
        stall = tenant.contracts.order_by('-start_date').first().stall
        drafts.append(('Vacancy Notice', tenant,
                       self._vacancy_text(settings, tenant, stall, today)))

        created = 0
        for index, (notice_type, tenant, content) in enumerate(drafts, start=1):
            number = f'{prefix}-NOT-{today.year}-{index:04d}'
            if Notice.objects.filter(notice_number=number).exists():
                created += 1
                continue
            Notice.objects.create(
                tenant=tenant, notice_type=notice_type, notice_number=number, date_issued=today,
                is_served=index <= 2, served_date=today if index <= 2 else None, content=content)
            created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} notices'))
        return created

    def _demand_text(self, settings, notice_type, billing):
        tenant, stall = billing.tenant, billing.stall
        lead = ('This is a FINAL DEMAND for the amount below. Failure to settle within ten (10) days '
                'shall cause the cancellation of your stall privilege and referral for collection '
                'proceedings.\n\n' if notice_type == 'Final Demand' else '')
        return (
            f'To: {tenant.full_name} ({tenant.tenant_id})\n\n'
            f'{lead}'
            f'Our records show an outstanding balance of ₱{Decimal(billing.balance):,.2f} for '
            f'Stall {stall.stall_number} of the {stall.section.name}, covering '
            f'{billing.billing_month:02d}/{billing.billing_year} (due '
            f'{billing.due_date.strftime("%B %d, %Y")}), including ₱{Decimal(billing.penalty_amount):,.2f} '
            f'in surcharges. Please settle this account at the {settings.office_name}.\n\n'
            f'{settings.market_name} — {settings.office_name}')

    def _vacancy_text(self, settings, tenant, stall, today):
        return (
            f'To: {tenant.full_name} ({tenant.tenant_id})\n\n'
            f'Stall {stall.stall_number} of the {stall.section.name} has been declared VACANT '
            f'effective {today.strftime("%B %d, %Y")} following the lapse of your rental '
            f'contract. Please vacate the premises and claim your security deposit at the '
            f'{settings.office_name} within fifteen (15) days.\n\n'
            f'{settings.market_name} — {settings.office_name}')

    def _create_audit_logs(self, users, tenants, payments, today):
        if AuditLog.objects.exists() or not payments:
            return
        first, last = payments[0], payments[-1]
        rows = [
            (users['admin'], 'UPDATE', 'SystemSettings',
             'Configured billing, penalty and contract term defaults'),
            (users['admin'], 'CREATE', 'Tenant',
             f'Created tenant {tenants["TEN-012"].tenant_id} - {tenants["TEN-012"].full_name} '
             f'(login {tenants["TEN-012"].user.username})'),
            (users['admin'], 'CREATE', 'RentalContract',
             f'Approved contract for stall {first.stall.stall_number} — {first.tenant.full_name}'),
            (users['collector1'], 'COLLECT', 'Payment',
             f'Collected {first.receipt_number} — ₱{first.amount_paid:,.2f} from {first.tenant.full_name}'),
            (users['cashier1'], 'COLLECT', 'Payment',
             f'Posted {last.receipt_number} — ₱{last.amount_paid:,.2f} ({last.status}) '
             f'for {last.tenant.full_name}'),
            (users['supervisor1'], 'TERMINATE', 'RentalContract',
             f'Terminated contract of {tenants["TEN-010"].full_name} for violation of market guidelines'),
            (users['collector1'], 'MARK_SERVED', 'Notice',
             f'Served notices for the {today.strftime("%B %Y")} collection drive'),
        ]
        AuditLog.objects.bulk_create([
            AuditLog(user=user, action=action, module=module, description=description,
                     ip_address='192.168.1.10')
            for user, action, module, description in rows])
