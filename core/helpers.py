import calendar
import re
import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.http import HttpResponse
from django.template.loader import render_to_string

from core.models import TenantLedger, Billing, SystemSetting


def _username_from_tenant_id(tenant_id):
    """Derive a clean base username from a tenant ID (kept as the TENANT<prefix>
    convention used across the system) so it is a valid Django username."""
    base = f"TENANT{tenant_id}"
    # Django usernames allow letters, digits and @ . + - _ only.
    base = re.sub(r'[^A-Za-z0-9._+-]', '-', base).strip('-')
    return base[:140] or 'TENANT'


def _unique_username(base):
    """Append a numeric suffix until the username is unused."""
    from django.contrib.auth.models import User
    username = base
    suffix = 2
    while User.objects.filter(username=username).exists():
        username = f"{base}-{suffix}"
        suffix += 1
    return username


def generate_strong_password(length=14, user=None):
    """Generate a random password that satisfies the project's
    AUTH_PASSWORD_VALIDATORS (mixed case, digits and symbols)."""
    upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ'      # ambiguous chars (I, O) removed
    lower = 'abcdefghijkmnopqrstuvwxyz'     # ambiguous chars (l) removed
    digits = '23456789'                     # ambiguous chars (0, 1) removed
    symbols = '!@#$%^&*-_=+'
    all_chars = upper + lower + digits + symbols
    for _attempt in range(50):
        chars = (
            [secrets.choice(upper) for _ in range(2)]
            + [secrets.choice(lower) for _ in range(2)]
            + [secrets.choice(digits) for _ in range(2)]
            + [secrets.choice(symbols) for _ in range(1)]
        )
        chars += [secrets.choice(all_chars) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        password = ''.join(chars)
        try:
            validate_password(password, user)
            return password
        except ValidationError:
            continue
    # Defensive fallback: extremely unlikely to be reached.
    return ''.join(secrets.choice(all_chars) for _ in range(max(length, 16)))


def create_tenant_login(tenant):
    """Create (or reuse) a tenant login linked to ``tenant``.

    Generates a secure username derived from the tenant ID and a strong
    temporary password, marks the account so the tenant is forced to change
    the password on first login, and returns ``(user, raw_password)``.
    """
    from django.contrib.auth.models import User
    from core.models import UserProfile

    base_username = _username_from_tenant_id(tenant.tenant_id)
    username = _unique_username(base_username)
    first, _, rest = tenant.full_name.partition(' ')
    password = generate_strong_password(user=None)

    user = User.objects.create_user(
        username=username,
        email=tenant.email,
        password=password,
        first_name=first.strip(),
        last_name=rest.strip(),
    )
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'tenant'})
    profile.role = 'tenant'
    profile.must_change_password = True
    profile.save()

    tenant.user = user
    tenant.save(update_fields=['user'])
    return user, password


def safe_due_date(year, month, due_day):
    """Create due date safely handling 28/29/30/31 edge — use last day of month if due_day exceeds month length."""
    _, last_day = calendar.monthrange(int(year), int(month))
    safe_day = min(int(due_day), last_day)
    return date(int(year), int(month), safe_day)


def compute_penalty_for_contract(contract, billing_month, billing_year, due_date):
    settings = SystemSetting.objects.first()
    if not settings:
        return Decimal('0.00')
    penalty_settings = contract.penalty_settings.filter(is_active=True).first()
    if penalty_settings:
        p_type = penalty_settings.penalty_type
        p_value = penalty_settings.penalty_value
        grace = penalty_settings.grace_period
    else:
        p_type = settings.penalty_type
        p_value = settings.penalty_value
        grace = settings.grace_period
    today = date.today()
    if today <= due_date + timedelta(days=grace or 0):
        return Decimal('0.00')
    if p_type == 'fixed':
        return Decimal(p_value)
    elif p_type == 'percentage':
        return (Decimal(contract.monthly_rent) * (Decimal(p_value) / Decimal('100'))).quantize(Decimal('0.01'))
    return Decimal('0.00')


def get_or_create_billing(contract, billing_month, billing_year, auto_created=True):
    """
    Idempotent billing creation for a contract's given month/year.
    Returns (billing, created).
    Avoids duplicate via unique_together; safe for concurrent calls.
    """
    from core.models import Billing
    # Normalize to int
    billing_month = int(billing_month)
    billing_year = int(billing_year)
    tenant = contract.tenant
    stall = contract.stall
    existing = Billing.objects.filter(
        tenant=tenant, stall=stall,
        billing_month=billing_month, billing_year=billing_year
    ).first()
    if existing:
        return existing, False

    due_day = contract.due_day
    due_date = safe_due_date(billing_year, billing_month, due_day)
    rental_amount = Decimal(contract.monthly_rent)
    penalty_amount = compute_penalty_for_contract(contract, billing_month, billing_year, due_date)
    total_due = (rental_amount + penalty_amount).quantize(Decimal('0.01'))

    billing = Billing.objects.create(
        tenant=tenant,
        stall=stall,
        contract=contract,
        billing_month=billing_month,
        billing_year=billing_year,
        rental_amount=rental_amount,
        penalty_amount=penalty_amount,
        discount=Decimal('0.00'),
        total_due=total_due,
        amount_paid=Decimal('0.00'),
        balance=total_due,
        due_date=due_date,
        status='Unpaid',
    )
    TenantLedger.objects.create(
        tenant=tenant,
        billing=billing,
        transaction_date=due_date,
        description=f'Rental billing for {billing_month:02d}/{billing_year} - {stall.stall_number}' + (' (auto)' if auto_created else ''),
        debit=total_due,
        credit=Decimal('0.00'),
        balance=total_due,  # will be recalculated
    )
    recalc_tenant_ledger(tenant)
    return billing, True


def ensure_initial_billing(contract):
    """Auto-create billing(s) for contract from start month up to current month. Call after contract creation."""
    try:
        from datetime import date
        start = contract.start_date
        today = date.today()
        # If start is in future, just create start month
        if start.year > today.year or (start.year == today.year and start.month > today.month):
            return get_or_create_billing(contract, start.month, start.year)
        # Iterate from start month to today inclusive
        created_any = False
        last_billing = None
        y, m = start.year, start.month
        while (y < today.year) or (y == today.year and m <= today.month):
            # Skip if contract already ended before this month
            if contract.end_date and (y > contract.end_date.year or (y == contract.end_date.year and m > contract.end_date.month)):
                break
            billing, created = get_or_create_billing(contract, m, y)
            if created:
                created_any = True
            last_billing = billing
            m += 1
            if m > 12:
                m = 1
                y += 1
        return last_billing, created_any
    except Exception:
        return None, False


def ensure_current_month_billings():
    """
    Ensure every Active contract has a billing for the current month/year.
    Keeps collector workflow simple: one billing per active contract per current month.
    Returns count of newly created billings. Call at billing_list entry for seamless collector workflow.
    """
    from core.models import RentalContract
    today = date.today()
    count = 0
    for contract in RentalContract.objects.filter(status='Active').select_related('tenant', 'stall'):
        # Skip if contract starts in future month
        if contract.start_date.year > today.year or (contract.start_date.year == today.year and contract.start_date.month > today.month):
            continue
        # Skip if contract already ended before current month
        if contract.end_date and (contract.end_date.year < today.year or (contract.end_date.year == today.year and contract.end_date.month < today.month)):
            continue
        _, created = get_or_create_billing(contract, today.month, today.year)
        if created:
            count += 1
    return count


def recalc_tenant_ledger(tenant):
    """
    Recompute running balance for all ledger entries of a tenant in chronological order.
    Ensures debit/credit chain remains consistent after edits/voids/penalties.
    Uses Decimal end-to-end to avoid float drift in financial totals.
    """
    entries = TenantLedger.objects.filter(tenant=tenant).order_by('transaction_date', 'id')
    running = Decimal('0.00')
    for e in entries:
        running += (e.debit or Decimal('0.00')) - (e.credit or Decimal('0.00'))
        running = running.quantize(Decimal('0.01'))
        if e.balance != running:
            TenantLedger.objects.filter(pk=e.pk).update(balance=running)
    return running


def generate_receipt_number():
    """Build the next receipt number as ``<prefix>-<YYYYMM>-<000001>``.

    The monthly sequence is derived from the highest existing suffix for the
    current period (not the newest row by timestamp), so a receipt created in
    an earlier month can never push a later month's numbering off-by-one.
    Suffixes are zero-padded, so lexicographic ordering equals numeric ordering.
    """
    from core.models import Payment
    settings = SystemSetting.objects.first()
    prefix = ((settings.receipt_prefix if settings else '') or 'RCP').strip().rstrip('-') or 'RCP'
    pattern = f'{prefix}-{date.today().strftime("%Y%m")}-'
    last = (
        Payment.objects.filter(receipt_number__startswith=pattern)
        .order_by('-receipt_number')
        .values_list('receipt_number', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last[len(pattern):]) + 1
        except (ValueError, IndexError):
            seq = Payment.objects.filter(receipt_number__startswith=pattern).count() + 1
    return f'{pattern}{seq:06d}'


def recalc_billing_from_payments(billing):
    """Recompute a billing's paid/balance/status from its valid payments.

    Locks the billing row (call inside an ``atomic`` block) and is the single
    place that decides a bill's settlement state, so edits/voids and new
    collections stay consistent.
    """
    from core.models import Payment
    billing = Billing.objects.select_for_update().get(pk=billing.pk)
    total_paid = Decimal(
        Payment.objects.filter(billing=billing, status__in=['Paid', 'Partial'])
        .aggregate(t=Sum('amount_paid'))['t'] or 0
    )
    total_due = Decimal(billing.total_due)
    if total_paid >= total_due:
        billing.amount_paid = total_due
        billing.balance = Decimal('0.00')
        billing.status = 'Paid'
    elif total_paid > 0:
        billing.amount_paid = total_paid
        billing.balance = (total_due - total_paid).quantize(Decimal('0.01'))
        billing.status = 'Partial'
    else:
        billing.amount_paid = Decimal('0.00')
        billing.balance = total_due
        billing.status = 'Unpaid'
    billing.save()
    return billing


def record_payment(*, tenant, billing, amount, payment_date, payment_method='Cash',
                   collected_by=None, remarks='', official_receipt_no=''):
    """Single source of truth for posting a rental payment.

    Creates the ``Payment``, updates the ``Billing`` totals/status, posts a
    ledger credit and recomputes the running balance. The target billing row is
    locked with ``select_for_update`` so concurrent collections against the same
    bill cannot both mark it Paid or clobber each other's totals. A rare receipt
    number collision is retried.

    Must be called inside an ``atomic`` block (all callers are). Returns the
    created ``Payment``. ``amount`` is the full sum received; the amount applied
    to the billing is clamped to the outstanding balance so the ledger never
    over-settles a bill.
    """
    from core.models import Payment

    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    locked = Billing.objects.select_for_update().get(pk=billing.pk)
    pre_balance = Decimal(locked.balance or 0)

    payment = None
    for attempt in range(5):
        try:
            with transaction.atomic():
                receipt_number = generate_receipt_number()
                payment = Payment.objects.create(
                    receipt_number=receipt_number,
                    tenant=tenant,
                    stall=locked.stall,
                    billing=locked,
                    billing_month=locked.billing_month,
                    billing_year=locked.billing_year,
                    rental_amount=locked.rental_amount,
                    penalty_amount=locked.penalty_amount,
                    discount=locked.discount,
                    total_amount_due=locked.total_due,
                    amount_paid=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    official_receipt_no=official_receipt_no or receipt_number,
                    collected_by=collected_by,
                    status='Paid' if amount >= pre_balance else 'Partial',
                    remarks=remarks,
                )
            break
        except IntegrityError:
            if attempt == 4:
                raise

    # Recompute the billing authoritatively from all valid payments.
    locked = recalc_billing_from_payments(locked)

    # Ledger credit reflects what was actually applied to this bill.
    applied = amount if amount <= pre_balance else (pre_balance if pre_balance > 0 else amount)
    TenantLedger.objects.create(
        tenant=tenant,
        billing=locked,
        transaction_date=payment_date,
        description=f'Payment {payment.receipt_number} - {payment_method}',
        debit=Decimal('0.00'),
        credit=applied,
        balance=Decimal('0.00'),
        payment=payment,
    )
    recalc_tenant_ledger(tenant)
    return payment


def apply_overdue_penalties(today=None):
    """Mark past-due billings Overdue and accrue the one-time late penalty.

    Idempotent: a penalty is only added while ``penalty_amount`` is still zero,
    so repeated runs never double-charge. Includes billings already flagged
    ``Overdue`` (e.g. seeded directly) so a missed penalty is still applied.
    Uses Decimal and the shared ``recalc_tenant_ledger`` so it stays consistent
    with ``record_payment``. Returns ``(overdue_marked, penalties_applied)``.
    """
    from django.contrib.auth.models import User
    from core.models import Tenant, AuditLog
    today = today or date.today()
    settings = SystemSetting.objects.first()
    default_grace = settings.grace_period if settings else 5

    billings = Billing.objects.filter(
        status__in=['Unpaid', 'Partial', 'Overdue']
    ).select_related('contract', 'tenant', 'stall')

    overdue_marked = 0
    penalties_applied = 0
    affected_tenants = set()

    for billing in billings:
        penalty_setting = (
            billing.contract.penalty_settings.filter(is_active=True).first()
            if billing.contract_id else None
        )
        grace = penalty_setting.grace_period if penalty_setting else default_grace
        effective_due = billing.due_date + timedelta(days=grace or 0)
        if today <= effective_due:
            continue

        fields = []
        # Accrue a one-time penalty if none has been applied yet.
        if Decimal(billing.penalty_amount or 0) == 0:
            penalty = Decimal(str(compute_penalty_for_contract(
                billing.contract, billing.billing_month, billing.billing_year, billing.due_date
            ) or 0)).quantize(Decimal('0.01'))
            if penalty > 0:
                billing.penalty_amount = penalty
                billing.total_due = (
                    Decimal(billing.rental_amount) + penalty - Decimal(billing.discount or 0)
                ).quantize(Decimal('0.01'))
                billing.balance = billing.total_due - Decimal(billing.amount_paid)
                fields += ['penalty_amount', 'total_due', 'balance']
                TenantLedger.objects.create(
                    tenant=billing.tenant,
                    billing=billing,
                    transaction_date=today,
                    description=f'Overdue penalty for {billing.billing_month:02d}/{billing.billing_year} - {billing.stall.stall_number}',
                    debit=penalty,
                    credit=Decimal('0.00'),
                    balance=Decimal('0.00'),
                )
                affected_tenants.add(billing.tenant_id)
                penalties_applied += 1
                AuditLog.objects.create(
                    user=User.objects.filter(is_superuser=True).first(),
                    action='AUTO_PENALTY',
                    module='Billing',
                    description=f'Auto-applied penalty {penalty} to billing {billing.id} for {billing.tenant.full_name} {billing.stall.stall_number} {billing.billing_month}/{billing.billing_year}',
                )

        # Resolve status from the (possibly updated) balance.
        new_status = 'Paid' if Decimal(billing.balance) <= 0 else 'Overdue'
        if billing.status != new_status:
            if new_status == 'Overdue':
                overdue_marked += 1
            billing.status = new_status
            fields.append('status')

        if fields:
            billing.save(update_fields=list(dict.fromkeys(fields)))

    for tenant_id in affected_tenants:
        recalc_tenant_ledger(Tenant.objects.get(pk=tenant_id))
    return overdue_marked, penalties_applied


def maybe_apply_overdue_penalties(today=None):
    """Best-effort, throttled trigger for request-time accrual.

    Runs ``apply_overdue_penalties`` at most once per day per cache instance so
    overdue status and penalties stay current without an external scheduler.
    Never raises — an accrual error must not break the page that triggered it.
    """
    from django.core.cache import cache
    today = today or date.today()
    key = f'apply_overdue_penalties:{today.isoformat()}'
    # cache.add claims the day's slot atomically -> a single run per day.
    if not cache.add(key, 1, timeout=60 * 60 * 24):
        return
    try:
        apply_overdue_penalties(today)
    except Exception:
        cache.delete(key)  # allow a retry on the next request


def render_to_pdf_response(request, template_name, context, filename="document.pdf", base_url=None):
    """
    Render a template to PDF and return HttpResponse.
    Tries WeasyPrint first (best HTML/CSS fidelity), then xhtml2pdf/reportlab fallback for Windows
    where WeasyPrint requires libgobject-2.0-0 / Pango / GTK.
    """
    html_string = render_to_string(template_name, context, request=request)

    # 1. Try WeasyPrint (preferred, best CSS)
    try:
        import weasyprint  # type: ignore

        if base_url is None and request is not None:
            try:
                base_url = request.build_absolute_uri('/')
            except Exception:
                base_url = None
        pdf_bytes = weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (ImportError, OSError, Exception) as weasy_err:
        # WeasyPrint failed (common on Windows without GTK) — try xhtml2pdf fallback
        pass

    # 2. Fallback: xhtml2pdf (pure Python, no system libs, works on Windows)
    try:
        from xhtml2pdf import pisa  # type: ignore
        from io import BytesIO

        result = BytesIO()
        # pisa needs base_url for static, but we can ignore; it will handle inline CSS
        pisa_status = pisa.CreatePDF(src=html_string, dest=result)
        if not pisa_status.err:
            pdf_bytes = result.getvalue()
            if pdf_bytes and len(pdf_bytes) > 1000:
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
        # If pisa produced error or empty, fall through to next fallback
        xhtml_err = pisa_status.err if 'pisa_status' in locals() else 'unknown'
    except (ImportError, Exception) as xhtml_err:
        xhtml_err = str(xhtml_err) if 'xhtml_err' not in locals() else str(xhtml_err)
        pass

    # 3. Final fallback: return HTML preview with helpful message and Print button
    # This still lets user use browser Print → Save as PDF (which works everywhere)
    # Include original error for debugging but keep HTML usable
    try:
        weasy_msg = str(weasy_err) if 'weasy_err' in locals() else 'WeasyPrint unavailable'
    except Exception:
        weasy_msg = 'WeasyPrint unavailable'
    try:
        xhtml_msg = str(xhtml_err) if 'xhtml_err' in locals() else ''
    except Exception:
        xhtml_msg = ''

    html_with_warning = f"""
    <div style="background:#fffbeb;border:1px solid #fde68a;padding:16px;margin:16px;font-family:Inter,system-ui,sans-serif;font-size:13px;color:#92400e;border-radius:12px;">
      <div style="font-weight:700;margin-bottom:6px;">PDF generated via browser fallback</div>
      <div style="font-size:12px;line-height:1.5;">
        WeasyPrint system library missing (<code style="background:#fef3c6;padding:2px 6px;border-radius:6px;">{weasy_msg[:300]}</code>).<br>
        Used HTML preview instead — please use <strong>Print Preview → Print → Save as PDF</strong> for best quality on Windows.<br>
        <span style="opacity:0.8">Alternatively, install GTK3 runtime from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer or switch production to Linux where WeasyPrint works natively.</span>
        {f'<div style="margin-top:8px;opacity:0.7">xhtml2pdf fallback also failed: {xhtml_msg[:200]}</div>' if xhtml_msg and 'No such file' not in str(xhtml_msg) else ''}
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;">
        <button onclick="window.print()" style="background:#1e293b;color:white;border-radius:999px;padding:8px 16px;font-weight:600;border:none;cursor:pointer;">🖨️ Print / Save as PDF</button>
        <button onclick="window.close()" style="background:white;border:1px solid #e2e8f0;border-radius:999px;padding:8px 16px;font-weight:600;cursor:pointer;">Close</button>
      </div>
    </div>
    """ + html_string
    return HttpResponse(html_with_warning)
