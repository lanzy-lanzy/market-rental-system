from django.core.management.base import BaseCommand
from datetime import date, timedelta
from django.db.models import Sum
from core.models import Billing, TenantLedger, AuditLog, SystemSetting
from core.views.billing import compute_penalty
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Apply overdue status and retroactive penalties to unpaid billings (grace-aware).'

    def handle(self, *args, **options):
        today = date.today()
        settings = SystemSetting.objects.first()
        default_grace = settings.grace_period if settings else 5

        billings = Billing.objects.filter(status__in=['Unpaid', 'Partial']).select_related('contract', 'tenant', 'stall')
        updated = 0
        penalized = 0

        for billing in billings:
            # Determine grace for this billing
            penalty_setting = billing.contract.penalty_settings.filter(is_active=True).first() if hasattr(billing.contract, 'penalty_settings') else None
            grace = penalty_setting.grace_period if penalty_setting else default_grace
            effective_due = billing.due_date + timedelta(days=grace or 0)

            # Mark overdue if past effective due
            if today > effective_due and billing.status != 'Overdue':
                billing.status = 'Overdue'
                billing.save(update_fields=['status'])
                updated += 1

            # Apply retroactive penalty if still zero and overdue
            if today > effective_due and billing.penalty_amount == 0:
                penalty = compute_penalty(billing.contract, billing.billing_month, billing.billing_year, billing.due_date)
                if penalty and penalty != billing.penalty_amount:
                    old_total = billing.total_due
                    billing.penalty_amount = penalty
                    billing.total_due = billing.rental_amount + penalty - (billing.discount or 0)
                    # Recalculate balance based on already paid
                    billing.balance = billing.total_due - billing.amount_paid
                    if billing.balance <= 0:
                        billing.balance = 0
                        billing.status = 'Paid'
                    elif billing.amount_paid > 0:
                        billing.status = 'Partial'
                    # keep Overdue if still unpaid and overdue
                    if today > effective_due and billing.balance > 0:
                        billing.status = 'Overdue'
                    billing.save(update_fields=['penalty_amount', 'total_due', 'balance', 'status'])
                    # Create ledger debit adjustment for penalty
                    delta = penalty
                    # Get last ledger balance for tenant to chain correctly
                    last_entry = TenantLedger.objects.filter(tenant=billing.tenant).order_by('-transaction_date', '-id').first()
                    last_balance = last_entry.balance if last_entry else 0
                    # If last entry is this billing's original debit, we adjust; simpler to create adjustment entry
                    TenantLedger.objects.create(
                        tenant=billing.tenant,
                        billing=billing,
                        transaction_date=today,
                        description=f'Overdue penalty for {billing.billing_month:02d}/{billing.billing_year} - {billing.stall.stall_number}',
                        debit=delta,
                        credit=0,
                        balance=last_balance + delta,
                    )
                    penalized += 1
                    # Audit
                    system_user = User.objects.filter(is_superuser=True).first()
                    AuditLog.objects.create(
                        user=system_user,
                        action='AUTO_PENALTY',
                        module='Billing',
                        description=f'Auto-applied penalty {penalty} to billing {billing.id} for {billing.tenant.full_name} {billing.stall.stall_number} {billing.billing_month}/{billing.billing_year}',
                    )

        # Also handle already Overdue but not yet penalized (in case first loop missed)
        # Already covered by penalized logic

        self.stdout.write(self.style.SUCCESS(f'Overdue marked: {updated}, penalties applied: {penalized}'))

        # Second pass: recompute chain balances for tenants with penalized billings to ensure consistency
        # For any tenant that had penalty applied, recompute chronological ledger balances
        if penalized > 0:
            affected_tenants = Billing.objects.filter(penalty_amount__gt=0).values_list('tenant_id', flat=True).distinct()
            for tenant_id in affected_tenants:
                entries = TenantLedger.objects.filter(tenant_id=tenant_id).order_by('transaction_date', 'id')
                running = 0
                for e in entries:
                    running = running + e.debit - e.credit
                    if e.balance != running:
                        TenantLedger.objects.filter(pk=e.pk).update(balance=running)
            self.stdout.write(self.style.SUCCESS('Ledger balances recomputed for affected tenants.'))
