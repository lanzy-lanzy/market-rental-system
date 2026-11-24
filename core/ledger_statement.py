from decimal import Decimal
from types import SimpleNamespace

from django.utils import timezone

from core.models import Billing, Payment

ZERO = Decimal('0.00')


def _unique_remarks(values):
    seen = []
    for val in values:
        text = (val or '').strip()
        if text and text not in seen:
            seen.append(text)
    return '; '.join(seen)


def tenant_statement(tenant):
    """Build a statement from charges and valid receipts, never cached ledger balances.

    Charges include the bill's current penalties. Receipts are applied only to
    their own bill; excess cash cannot settle another bill. No financial
    records are changed when viewing or printing a statement.
    """
    bills = list(Billing.objects.filter(tenant=tenant).select_related('stall', 'contract'))
    payments = list(Payment.objects.filter(
        billing__tenant=tenant, status__in=['Paid', 'Partial']
    ).order_by('payment_date', 'created_at', 'id'))
    by_id = {bill.pk: bill for bill in bills}
    applied = {bill.pk: ZERO for bill in bills}
    receipts = {bill.pk: [] for bill in bills}
    excess = ZERO
    for payment in payments:
        bill = by_id[payment.billing_id]
        credit = min(max(payment.amount_paid, ZERO), max(bill.total_due - applied[bill.pk], ZERO))
        applied[bill.pk] += credit
        excess += max(payment.amount_paid - credit, ZERO)
        receipts[bill.pk].append(payment)
    total_due = sum((b.total_due for b in bills), ZERO)
    total_paid = sum(applied.values(), ZERO)
    today = timezone.localdate()
    for bill in bills:
        bill.balance = max(bill.total_due - applied[bill.pk], ZERO)
        bill.status = ('Paid' if bill.balance == ZERO else 'Partial' if applied[bill.pk] > ZERO
                       else 'Overdue' if bill.due_date < today else 'Unpaid')
    entries = []
    for bill in sorted(bills, key=lambda b: (b.billing_year, b.billing_month, b.stall.stall_number), reverse=True):
        payment_remarks = _unique_remarks(p.remarks for p in receipts[bill.pk])
        contract_remarks = (bill.contract.remarks or '').strip() if bill.contract_id else ''
        entry_remarks = payment_remarks or contract_remarks
        entries.append(SimpleNamespace(
            billing=bill,
            payments=receipts[bill.pk],
            paid=applied[bill.pk],
            balance=bill.balance,
            status=bill.status,
            remarks=entry_remarks,
        ))

    if any(b.status == 'Overdue' for b in bills):
        account_status = 'Overdue'
    elif any(b.status == 'Partial' for b in bills):
        account_status = 'Partial'
    elif any(b.status == 'Unpaid' for b in bills):
        account_status = 'Unpaid'
    elif bills:
        account_status = 'Paid'
    else:
        account_status = 'No Bills'

    latest_payment_remark = next((p.remarks.strip() for p in reversed(payments) if (p.remarks or '').strip()), '')
    contract_remark = next(
        (b.contract.remarks.strip() for b in bills if b.contract_id and (b.contract.remarks or '').strip()),
        '',
    )
    account_remarks = _unique_remarks([
        getattr(tenant, 'notes', ''),
        latest_payment_remark,
        contract_remark if not getattr(tenant, 'notes', '').strip() and not latest_payment_remark else '',
    ])

    return {
        'entries': entries,
        'total_debits': total_due, 'total_credits': total_paid,
        'running_balance': total_due - total_paid,
        'unapplied_amount': excess,
        'paid_bills': sum(b.balance == ZERO for b in bills),
        'unpaid_bills': sum(b.balance > ZERO for b in bills),
        'account_status': account_status,
        'account_remarks': account_remarks,
    }
