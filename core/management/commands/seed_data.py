from datetime import date, timedelta
from calendar import monthrange

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import (
    UserProfile, SystemSetting, MarketSection, StallType, Stall,
    Tenant, RentalContract, Billing, Payment, TenantLedger, Notice, AuditLog,
)


class Command(BaseCommand):
    help = 'Seed the database with sample data for the Public Market Rental System'

    def handle(self, *args, **options):
        self._create_system_settings()
        self._create_users()
        self._create_market_sections()
        self._create_stall_types()
        self._create_stalls()
        self._create_tenants()
        self._create_contracts()
        self._create_billings()
        self._create_payments()
        self._create_ledger_entries()
        self._create_notices()
        self._create_audit_logs()

    def _get_or_none(self, model, **kwargs):
        try:
            return model.objects.get(**kwargs)
        except model.DoesNotExist:
            return None

    def _create_system_settings(self):
        if SystemSetting.objects.exists():
            self.stdout.write('System settings already exist, skipping.')
            return
        SystemSetting.objects.create(
            municipality_name='Dumingag Municipality, LGU DUMINGAG',
            market_name='Dumingag Public Market',
            office_name='Market Administration Office',
            receipt_prefix='DMPM-',
            default_due_day=5,
            penalty_type='percentage',
            penalty_value=2.00,
            grace_period=5,
        )
        self.stdout.write(self.style.SUCCESS('Created 1 system setting'))

    def _create_users(self):
        users_data = [
            {'username': 'admin', 'password': 'admin123', 'is_staff': True, 'is_superuser': True,
             'profile': {'role': 'admin', 'phone': '', 'address': ''}},
            {'username': 'collector1', 'password': 'collector123',
             'profile': {'role': 'collector', 'phone': '09171234567', 'address': 'Dumingag'}},
            {'username': 'supervisor1', 'password': 'supervisor123',
             'profile': {'role': 'supervisor', 'phone': '09181234568', 'address': 'Dumingag'}},
            {'username': 'treasurer1', 'password': 'treasurer123',
             'profile': {'role': 'treasurer', 'phone': '09191234569', 'address': 'Dumingag'}},
        ]
        created_count = 0
        for ud in users_data:
            if User.objects.filter(username=ud['username']).exists():
                continue
            profile_data = ud.pop('profile')
            user = User.objects.create_user(**ud)
            if ud['username'] == 'collector1':
                user.first_name = 'Juan'
                user.last_name = 'Santos'
            elif ud['username'] == 'supervisor1':
                user.first_name = 'Maria'
                user.last_name = 'Cruz'
            elif ud['username'] == 'treasurer1':
                user.first_name = 'Pedro'
                user.last_name = 'Reyes'
            user.save()
            UserProfile.objects.create(user=user, **profile_data)
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} staff users'))

    def _create_market_sections(self):
        section_names = [
            'Dry Goods Section',
            'Fish Section',
            'Meat Section',
            'Vegetable Section',
            'Fruit Section',
            'Eatery/Carenderia Section',
            'Grocery Section',
            'Rice and Grains Section',
        ]
        created_count = 0
        for name in section_names:
            _, created = MarketSection.objects.get_or_create(name=name)
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} market sections'))

    def _create_stall_types(self):
        types_data = [
            {'name': 'Regular Stall', 'description': 'Standard size stall'},
            {'name': 'Premium Stall', 'description': 'Larger stall with premium location'},
            {'name': 'Kiosk', 'description': 'Small kiosk space'},
            {'name': 'Table Space', 'description': 'Table-only space'},
        ]
        created_count = 0
        for td in types_data:
            _, created = StallType.objects.get_or_create(name=td['name'], defaults=td)
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} stall types'))

    def _create_stalls(self):
        dry = self._get_or_none(MarketSection, name='Dry Goods Section')
        fish = self._get_or_none(MarketSection, name='Fish Section')
        meat = self._get_or_none(MarketSection, name='Meat Section')
        veg = self._get_or_none(MarketSection, name='Vegetable Section')
        fruit = self._get_or_none(MarketSection, name='Fruit Section')
        eatery = self._get_or_none(MarketSection, name='Eatery/Carenderia Section')
        grocery = self._get_or_none(MarketSection, name='Grocery Section')
        rice = self._get_or_none(MarketSection, name='Rice and Grains Section')

        regular = self._get_or_none(StallType, name='Regular Stall')
        premium = self._get_or_none(StallType, name='Premium Stall')
        kiosk = self._get_or_none(StallType, name='Kiosk')
        table = self._get_or_none(StallType, name='Table Space')

        stalls_data = [
            {'stall_number': 'DGS-01', 'section': dry, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 1500, 'status': 'Occupied'},
            {'stall_number': 'DGS-02', 'section': dry, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 1500, 'status': 'Vacant'},
            {'stall_number': 'FS-01', 'section': fish, 'stall_type': premium, 'size': 6.0, 'monthly_rate': 2500, 'status': 'Occupied'},
            {'stall_number': 'FS-02', 'section': fish, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 1800, 'status': 'Vacant'},
            {'stall_number': 'FS-03', 'section': fish, 'stall_type': table, 'size': 2.0, 'monthly_rate': 800, 'status': 'Occupied'},
            {'stall_number': 'MS-01', 'section': meat, 'stall_type': premium, 'size': 6.0, 'monthly_rate': 3000, 'status': 'Vacant'},
            {'stall_number': 'MS-02', 'section': meat, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 2000, 'status': 'Occupied'},
            {'stall_number': 'VS-01', 'section': veg, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 1200, 'status': 'Vacant'},
            {'stall_number': 'VS-02', 'section': veg, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 1200, 'status': 'Occupied'},
            {'stall_number': 'VS-03', 'section': veg, 'stall_type': table, 'size': 2.0, 'monthly_rate': 600, 'status': 'Vacant'},
            {'stall_number': 'FRS-01', 'section': fruit, 'stall_type': regular, 'size': 4.0, 'monthly_rate': 1300, 'status': 'Vacant'},
            {'stall_number': 'FRS-02', 'section': fruit, 'stall_type': table, 'size': 2.0, 'monthly_rate': 700, 'status': 'Occupied'},
            {'stall_number': 'ECS-01', 'section': eatery, 'stall_type': premium, 'size': 8.0, 'monthly_rate': 2800, 'status': 'Vacant'},
            {'stall_number': 'ECS-02', 'section': eatery, 'stall_type': kiosk, 'size': 3.0, 'monthly_rate': 1500, 'status': 'Occupied'},
            {'stall_number': 'ECS-03', 'section': eatery, 'stall_type': kiosk, 'size': 3.0, 'monthly_rate': 1500, 'status': 'Vacant'},
            {'stall_number': 'GS-01', 'section': grocery, 'stall_type': premium, 'size': 8.0, 'monthly_rate': 3000, 'status': 'Vacant'},
            {'stall_number': 'GS-02', 'section': grocery, 'stall_type': regular, 'size': 5.0, 'monthly_rate': 2000, 'status': 'Vacant'},
            {'stall_number': 'RGS-01', 'section': rice, 'stall_type': regular, 'size': 6.0, 'monthly_rate': 1800, 'status': 'Vacant'},
            {'stall_number': 'RGS-02', 'section': rice, 'stall_type': regular, 'size': 6.0, 'monthly_rate': 1800, 'status': 'Vacant'},
            {'stall_number': 'RGS-03', 'section': rice, 'stall_type': kiosk, 'size': 3.0, 'monthly_rate': 1000, 'status': 'Vacant'},
        ]
        created_count = 0
        for sd in stalls_data:
            _, created = Stall.objects.get_or_create(
                stall_number=sd['stall_number'],
                defaults=sd,
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} stalls'))

    def _create_tenants(self):
        tenants_data = [
            {'tenant_id': 'TEN-001', 'full_name': 'Juan dela Cruz', 'address': '123 Rizal St, Dumingag',
             'contact_number': '09170000001', 'email': 'juan@email.com',
             'business_name': 'Juan Rice Trading', 'business_type': 'Rice and Grains'},
            {'tenant_id': 'TEN-002', 'full_name': 'Maria Santos', 'address': '456 Bonifacio Ave, Dumingag',
             'contact_number': '09170000002', 'email': 'maria@email.com',
             'business_name': 'Maria Fresh Fish', 'business_type': 'Fish Vendor'},
            {'tenant_id': 'TEN-003', 'full_name': 'Pedro Reyes', 'address': '789 Mabini St, Dumingag',
             'contact_number': '09170000003', 'email': 'pedro@email.com',
             'business_name': 'Pedro Meat Shop', 'business_type': 'Meat Vendor'},
            {'tenant_id': 'TEN-004', 'full_name': 'Ana Gonzales', 'address': '321 Luna St, Dumingag',
             'contact_number': '09170000004', 'email': 'ana@email.com',
             'business_name': 'Ana\'s Fresh Produce', 'business_type': 'Vegetable Vendor'},
            {'tenant_id': 'TEN-005', 'full_name': 'Jose Rizal II', 'address': '654 Del Pilar St, Dumingag',
             'contact_number': '09170000005', 'email': 'jose@email.com',
             'business_name': 'Jose\'s Fruit Stand', 'business_type': 'Fruit Vendor'},
            {'tenant_id': 'TEN-006', 'full_name': 'Luzviminda Mercado', 'address': '987 Aguinaldo St, Dumingag',
             'contact_number': '09170000006', 'email': 'luz@email.com',
             'business_name': 'Luz\'s Eatery', 'business_type': 'Food Service'},
            {'tenant_id': 'TEN-007', 'full_name': 'Antonio Lopez', 'address': '147 Jacinto St, Dumingag',
             'contact_number': '09170000007', 'email': 'antonio@email.com',
             'business_name': 'Antonio Dry Goods', 'business_type': 'Dry Goods'},
            {'tenant_id': 'TEN-008', 'full_name': 'Teresa Cruz', 'address': '258 Natividad St, Dumingag',
             'contact_number': '09170000008', 'email': 'teresa@email.com',
             'business_name': 'Teresa\'s Store', 'business_type': 'Grocery'},
        ]
        created_count = 0
        for td in tenants_data:
            if Tenant.objects.filter(tenant_id=td['tenant_id']).exists():
                continue
            tenant_id = td['tenant_id']
            user_data = {
                'username': tenant_id,
                'password': 'tenant123',
            }
            user = User.objects.create_user(**user_data)
            UserProfile.objects.create(user=user, role='tenant')
            Tenant.objects.create(user=user, **td)
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} tenants'))

    def _create_contracts(self):
        if RentalContract.objects.exists():
            self.stdout.write('Rental contracts already exist, skipping.')
            return

        now = timezone.localtime(timezone.now())
        current_year = now.year
        current_month = now.month

        tenant1 = self._get_or_none(Tenant, tenant_id='TEN-001')
        tenant2 = self._get_or_none(Tenant, tenant_id='TEN-002')
        tenant3 = self._get_or_none(Tenant, tenant_id='TEN-003')
        tenant4 = self._get_or_none(Tenant, tenant_id='TEN-004')
        tenant5 = self._get_or_none(Tenant, tenant_id='TEN-007')

        stall1 = self._get_or_none(Stall, stall_number='RGS-01')
        stall2 = self._get_or_none(Stall, stall_number='FS-01')
        stall3 = self._get_or_none(Stall, stall_number='MS-02')
        stall4 = self._get_or_none(Stall, stall_number='VS-02')
        stall5 = self._get_or_none(Stall, stall_number='DGS-01')

        contracts_data = [
            {'tenant': tenant1, 'stall': stall1, 'start_date': date(current_year - 1, 1, 1),
             'end_date': date(current_year + 1, 12, 31), 'monthly_rent': 1800, 'due_day': 5,
             'security_deposit': 3600, 'status': 'Active'},
            {'tenant': tenant2, 'stall': stall2, 'start_date': date(current_year - 1, 3, 1),
             'end_date': date(current_year + 1, 12, 31), 'monthly_rent': 2500, 'due_day': 5,
             'security_deposit': 5000, 'status': 'Active'},
            {'tenant': tenant3, 'stall': stall3, 'start_date': date(current_year - 1, 6, 1),
             'end_date': date(current_year + 1, 12, 31), 'monthly_rent': 2000, 'due_day': 5,
             'security_deposit': 4000, 'status': 'Active'},
            {'tenant': tenant4, 'stall': stall4, 'start_date': date(current_year - 1, 9, 1),
             'end_date': date(current_year + 1, 12, 31), 'monthly_rent': 1200, 'due_day': 5,
             'security_deposit': 2400, 'status': 'Active'},
            {'tenant': tenant5, 'stall': stall5, 'start_date': date(current_year, 1, 1),
             'end_date': date(current_year + 1, 12, 31), 'monthly_rent': 1500, 'due_day': 5,
             'security_deposit': 3000, 'status': 'Active'},
        ]
        created_count = 0
        for cd in contracts_data:
            if cd['tenant'] is None or cd['stall'] is None:
                continue
            _, created = RentalContract.objects.get_or_create(
                tenant=cd['tenant'],
                stall=cd['stall'],
                status='Active',
                defaults=cd,
            )
            if created:
                created_count += 1

        for stall in [stall1, stall2, stall3, stall4, stall5]:
            if stall:
                Stall.objects.filter(pk=stall.pk).update(status='Occupied')

        self.stdout.write(self.style.SUCCESS(f'Created {created_count} rental contracts'))

    def _create_billings(self):
        now = timezone.localtime(timezone.now())
        current_year = now.year
        current_month = now.month

        prev_year = current_month - 1 if current_month > 1 else current_year - 1
        prev_month = current_month - 1 if current_month > 1 else 12

        contracts = RentalContract.objects.filter(status='Active')
        created_count = 0

        for contract in contracts:
            for year, month in [(current_year, current_month), (prev_year, prev_month)]:
                _, last_day = monthrange(year, month)
                due_date = date(year, month, min(contract.due_day, last_day))
                total_due = contract.monthly_rent
                _, created = Billing.objects.get_or_create(
                    tenant=contract.tenant,
                    stall=contract.stall,
                    contract=contract,
                    billing_month=month,
                    billing_year=year,
                    defaults={
                        'rental_amount': contract.monthly_rent,
                        'penalty_amount': 0,
                        'discount': 0,
                        'total_due': total_due,
                        'amount_paid': 0,
                        'balance': total_due,
                        'due_date': due_date,
                        'status': 'Unpaid',
                    },
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created_count} billings'))

    def _create_payments(self):
        if Payment.objects.exists():
            self.stdout.write('Payments already exist, skipping.')
            return

        now = timezone.localtime(timezone.now())
        current_year = now.year
        current_month = now.month

        prev_year = current_month - 1 if current_month > 1 else current_year - 1
        prev_month = current_month - 1 if current_month > 1 else 12

        collector = self._get_or_none(User, username='collector1')

        contracts = list(RentalContract.objects.filter(status='Active'))
        if len(contracts) < 4:
            self.stdout.write('Not enough contracts for sample payments.')
            return

        # Current month: 2 payments (contracts 0, 1)
        # Previous month: 2 payments (contracts 0, 2)
        # Leave 1 unpaid, 1 overdue for current month
        payment_configs = [
            {
                'contract_idx': 0, 'year': current_year, 'month': current_month,
                'status': 'Paid', 'paid_date': date(current_year, current_month, 3),
                'receipt_num': 1,
            },
            {
                'contract_idx': 1, 'year': current_year, 'month': current_month,
                'status': 'Paid', 'paid_date': date(current_year, current_month, 4),
                'receipt_num': 2,
            },
            {
                'contract_idx': 0, 'year': prev_year, 'month': prev_month,
                'status': 'Paid', 'paid_date': date(prev_year, prev_month, 3),
                'receipt_num': 3,
            },
            {
                'contract_idx': 2, 'year': prev_year, 'month': prev_month,
                'status': 'Paid', 'paid_date': date(prev_year, prev_month, 2),
                'receipt_num': 4,
            },
        ]
        payment_methods = ['Cash', 'GCash', 'Cash', 'Bank Transfer']
        created_count = 0
        receipt_prefix = 'DMPM-'

        for i, pc in enumerate(payment_configs):
            contract = contracts[pc['contract_idx']]
            billing = self._get_or_none(
                Billing, contract=contract,
                billing_month=pc['month'], billing_year=pc['year'],
            )
            if billing is None:
                continue
            receipt_number = f"{receipt_prefix}{pc['year']}-{pc['receipt_num']:04d}"
            payment = Payment.objects.create(
                receipt_number=receipt_number,
                tenant=contract.tenant,
                stall=contract.stall,
                billing=billing,
                billing_month=pc['month'],
                billing_year=pc['year'],
                rental_amount=contract.monthly_rent,
                penalty_amount=0,
                discount=0,
                total_amount_due=contract.monthly_rent,
                amount_paid=contract.monthly_rent,
                payment_date=pc['paid_date'],
                payment_method=payment_methods[i],
                official_receipt_no=receipt_number,
                collected_by=collector,
                status='Paid',
            )
            Billing.objects.filter(pk=billing.pk).update(
                amount_paid=contract.monthly_rent,
                balance=0,
                status='Paid',
            )
            created_count += 1

        # Set 1 current month billing as Overdue (contract idx 3)
        if len(contracts) >= 4:
            overdue_contract = contracts[3]
            overdue_billing = self._get_or_none(
                Billing, contract=overdue_contract,
                billing_month=current_month, billing_year=current_year,
            )
            if overdue_billing:
                Billing.objects.filter(pk=overdue_billing.pk).update(status='Overdue')

        self.stdout.write(self.style.SUCCESS(f'Created {created_count} payments'))

    def _create_ledger_entries(self):
        if TenantLedger.objects.exists():
            self.stdout.write('Ledger entries already exist, skipping.')
            return
        payments = Payment.objects.filter(status='Paid')
        created_count = 0
        for payment in payments:
            billing = payment.billing
            entry, created = TenantLedger.objects.get_or_create(
                tenant=payment.tenant,
                billing=billing,
                transaction_date=payment.payment_date,
                defaults={
                    'description': f"Payment {payment.receipt_number} - {payment.payment_method}",
                    'debit': 0,
                    'credit': payment.amount_paid,
                    'balance': 0,
                    'payment': payment,
                },
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} ledger entries'))

    def _create_notices(self):
        if Notice.objects.exists():
            self.stdout.write('Notices already exist, skipping.')
            return
        now = timezone.localtime(timezone.now())

        tenants = Tenant.objects.filter(tenant_id__in=['TEN-001', 'TEN-003'])
        if len(tenants) < 2:
            self.stdout.write('Not enough tenants for sample notices.')
            return

        notices_data = [
            {
                'tenant': tenants[0],
                'notice_type': 'Payment Reminder',
                'notice_number': 'DMPM-NOT-2026-0001',
                'date_issued': date(now.year, now.month, 10),
                'is_served': True,
                'served_date': date(now.year, now.month, 10),
                'content': (
                    f"Dear {tenants[0].full_name},\n\n"
                    f"This is a reminder that your rental payment for stall "
                    f"is due on the 5th of each month. Please settle your account "
                    f"at the Market Administration Office to avoid penalties.\n\n"
                    f"Thank you,\n"
                    f"Dumingag Public Market Administration"
                ),
            },
            {
                'tenant': tenants[1],
                'notice_type': 'Overdue Notice',
                'notice_number': 'DMPM-NOT-2026-0002',
                'date_issued': date(now.year, now.month, 15),
                'is_served': False,
                'served_date': None,
                'content': (
                    f"Dear {tenants[1].full_name},\n\n"
                    f"Your rental account is now OVERDUE. Please settle your "
                    f"outstanding balance immediately to avoid further penalties "
                    f"and possible suspension of your rental contract.\n\n"
                    f"Thank you,\n"
                    f"Dumingag Public Market Administration"
                ),
            },
        ]
        created_count = 0
        for nd in notices_data:
            _, created = Notice.objects.get_or_create(
                notice_number=nd['notice_number'],
                defaults=nd,
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created_count} notices'))

    def _create_audit_logs(self):
        if AuditLog.objects.exists():
            self.stdout.write('Audit logs already exist, skipping.')
            return
        admin = self._get_or_none(User, username='admin')
        collector = self._get_or_none(User, username='collector1')
        supervisor = self._get_or_none(User, username='supervisor1')

        now = timezone.localtime(timezone.now())
        logs_data = [
            {'user': admin, 'action': 'Login', 'module': 'Auth',
             'description': 'Admin user logged into the system',
             'ip_address': '192.168.1.100'},
            {'user': collector, 'action': 'Login', 'module': 'Auth',
             'description': 'Collector user logged into the system',
             'ip_address': '192.168.1.101'},
            {'user': collector, 'action': 'Create Payment', 'module': 'Payments',
             'description': 'Recorded payment DMPM-2026-0001 for TEN-001',
             'ip_address': '192.168.1.101'},
            {'user': supervisor, 'action': 'Login', 'module': 'Auth',
             'description': 'Supervisor user logged into the system',
             'ip_address': '192.168.1.102'},
            {'user': supervisor, 'action': 'View Report', 'module': 'Reports',
             'description': 'Generated monthly collection report',
             'ip_address': '192.168.1.102'},
            {'user': admin, 'action': 'Update Settings', 'module': 'Settings',
             'description': 'Updated system penalty configuration',
             'ip_address': '192.168.1.100'},
        ]
        created = AuditLog.objects.bulk_create(
            [AuditLog(**ld) for ld in logs_data],
        )
        self.stdout.write(self.style.SUCCESS(f'Created {len(created)} audit log entries'))
