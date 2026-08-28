from core.models import TenantLedger

def recalc_tenant_ledger(tenant):
    """
    Recompute running balance for all ledger entries of a tenant in chronological order.
    Ensures debit/credit chain remains consistent after edits/voids/penalties.
    """
    entries = TenantLedger.objects.filter(tenant=tenant).order_by('transaction_date', 'id')
    running = 0
    for e in entries:
        running += float(e.debit or 0) - float(e.credit or 0)
        # Avoid float precision issues; round to 2 decimals
        running = round(running, 2)
        if float(e.balance) != running:
            TenantLedger.objects.filter(pk=e.pk).update(balance=running)
    return running
