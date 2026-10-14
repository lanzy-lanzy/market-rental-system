# 📘 How Late Penalties Are Applied — A Plain-English Guide

> **Audience:** market office staff, cashiers, collectors, and tenants who want to understand *why* and *how much* a late penalty is added to a bill.

---

## 1. The One-Sentence Rule

> **If you do not pay your rent by the due date + a small grace period, the system automatically adds a one-time late penalty to your bill.**

Nothing else. No daily compounding, no monthly stacking. Once added, the penalty stays the same until the bill is settled.

---

## 2. What Decides the Penalty?

Three settings control everything:

| Setting | Where it lives | What it means |
|---|---|---|
| **Penalty Type** | Admin → Settings (or per contract) | `Percentage` (a % of rent) or `Fixed` (a peso amount) |
| **Penalty Value** | Same place | The actual number, e.g. `2` for 2% or `50` for ₱50 |
| **Grace Period** | Same place | Extra days after the due date before the penalty kicks in |

💡 A contract can **override** the system defaults. If an admin configured a special rule for a stall, that rule wins. Otherwise, the market-wide default applies.

---

## 3. When Does the Penalty Actually Fire?

Every night (or on the next staff page load), the system checks every unpaid bill:

```
today  >  due_date + grace_period   →  apply penalty
otherwise                            →  no penalty yet, wait
```

- **`due_date`** = the day-of-month chosen on the contract (usually the 5th).
- **`grace_period`** = extra cushion days (usually 5).
- The penalty is added **only once**, no matter how many times the check runs.

---

## 4. The Formula (Super Simple)

### 🅐 Percentage mode

```
Penalty = Monthly Rent × (Penalty Value ÷ 100)
```

### 🅑 Fixed mode

```
Penalty = Penalty Value     (peso, no calculation)
```

### 🧾 Final Bill

```
Total Due = Rent + Penalty − Discount
Balance   = Total Due − Amount Already Paid
```

---

## 5. Worked Example #1 — Percentage (most common)

**Setup**

- Monthly rent = **₱1,000**
- Penalty Type = **Percentage**
- Penalty Value = **2** (that's 2%)
- Grace Period = **5 days**
- Due Day = **5th of the month**
- Bill for = **October 2026**

**Timeline for Maria, who runs a vegetable stall**

| Date | What's happening | Penalty? |
|---|---|---|
| Oct 5, 2026 | Due date arrives — she hasn't paid yet | ❌ none — grace period starts |
| Oct 6–10 | Grace period (5 days) | ❌ none — still safe |
| **Oct 11** | Grace period over | ⚠️ system will charge as soon as it runs |
| **Oct 14** (today) | Sweep runs | ✅ penalty applied |

**Calculation**

```
Penalty   = 1,000 × (2 ÷ 100) = ₱20.00
```

**Bill now looks like:**

| Field | Amount |
|---|---:|
| Rental amount | ₱1,000.00 |
| **Penalty** | **₱20.00** |
| Discount | ₱0.00 |
| **Total Due** | **₱1,020.00** |
| Amount paid so far | ₱0.00 |
| **Balance** | **₱1,020.00** |

Maria now owes **₱1,020**.

---

## 6. Worked Example #2 — Fixed Penalty

Same Maria, but the admin sets the market rule to **Fixed ₱50**.

- Rent = ₱1,000
- Penalty = **₱50 flat** (no math, no percentage)

**Total Due = 1,000 + 50 = ₱1,050.00**

Notice: another tenant, Jun, pays rent of ₱5,000.

- Percentage 2% → Jun's penalty = ₱100
- Fixed ₱50 → Jun's penalty = ₱50 (same as Maria's)

📌 **This is the key difference**:

- **Percentage** — the penalty *grows* with rent. Higher-rent stalls owe a bigger penalty.
- **Fixed** — every late tenant pays *the same amount*, no matter their rent.

---

## 7. Worked Example #3 — What If Maria Pays Later?

Continuing Example #1 — the sweep runs again **every day**.

| Date | Sweep runs? | Penalty added? | Why |
|---|---|---|---|
| Oct 14 | ✅ | ✅ ₱20 (first time) | Grace ended, penalty_amount was still 0 |
| Oct 15 | ✅ | ❌ none | Penalty is already ₱20 — idempotency guard blocks re-charging |
| Oct 30 | ✅ | ❌ none | Still just ₱20, no compounding |
| Nov 5 (new bill) | ✅ | ❌ on the Oct bill. New Nov bill evaluated independently |

So Maria is charged **only ₱20 total** for being late in October, no matter how long she waits.

---

## 8. Worked Example #4 — Within Grace, No Charge

Pedro's due date is also **Oct 5**. He pays on **Oct 9** (day 4 of the 5-day grace).

- Today (Oct 9) ≤ due_date (Oct 5) + 5 days (Oct 10)? **Yes**
- Penalty = **₱0.00**
- Total due stays at **₱1,000**

✅ Pedro paid on time in the system's eyes — no penalty.

---

## 9. How This Is Explained to a Tenant (Talking Points)

If a tenant asks *"Bakit may dagdag sa bill ko?"* / *"Why is there an extra charge?"*, say:

1. *"Your bill was due on the **5th**. After a **5-day grace period**, the system automatically added the penalty."*
2. *"For a market rule of **2% of rent**, on your ₱1,000 rent, the penalty is only **₱20**."*
3. *"This penalty is charged **only once per bill** — it does not grow bigger each day."*
4. *"To avoid the penalty next month, please settle on or before **due date + 5 days**."*

---

## 10. Quick Reference Card

| If this happens… | Then the penalty is… |
|---|---|
| Paid on or before `due_date` | **₱0** |
| Paid between `due_date+1` and `due_date+grace` | **₱0** (grace) |
| Not paid after `due_date+grace` | **One-time charge** = rent × value ÷ 100 (percentage), or flat value (fixed) |
| Not paid for many months after that | **Same penalty** on that bill — it does not compound |
| New bill issued next month | Evaluated **independently** — a new penalty may apply to *that* bill |
| Contract has its own `PenaltySetting` | Contract rule **overrides** the global rule |
| Market has no `SystemSetting` yet | **₱0** — nothing gets charged |

---

## 11. Where to Configure This (For Admins)

1. **Global default** — Sidebar → **Settings**:
   - *Penalty Type* (Fixed / Percentage)
   - *Penalty Value*
   - *Grace Period* (days)
   - *Default Due Day* (1–28)

2. **Per-contract override** — Open a contract → **Penalty Settings** tab → Add an active rule.
   - Only the **first active** rule per contract is used.

3. **Manual re-check anytime** — Staff can also run:

   ```bash
   python manage.py apply_penalties
   ```

   The system already runs this automatically once per day on the billing/dashboard pages, so this command is only needed for testing or back-fills.

---

## 12. Under the Hood (For Developers)

- **Formula resolver**: `core.helpers.compute_penalty_for_contract()` — the single source of truth for penalty math.
- **Sweep service**: `core.helpers.apply_overdue_penalties()` — iterates past-due billings, marks them `Overdue`, stamps the one-time penalty, and mirrors the charge into `TenantLedger`.
- **Throttled trigger**: `core.helpers.maybe_apply_overdue_penalties()` — wraps the sweep behind a daily cache key (`apply_overdue_penalties:<YYYY-MM-DD>`), so it runs at most once per day per instance. Wired into `billing_list`, billing print/export, and the staff dashboard.
- **Manual entry point**: `core/management/commands/apply_penalties.py` — thin CLI wrapper over the service, unthrottled.
- **Models involved**:
  - `SystemSetting.penalty_type / penalty_value / grace_period` — global defaults
  - `PenaltySetting(contract, penalty_type, penalty_value, grace_period, due_day, is_active)` — per-contract override
  - `Billing.penalty_amount / total_due / balance / status` — the stamped result
  - `TenantLedger` — one debit row per applied penalty for audit trail
- **Idempotency guard**: The sweep only stamps a penalty when `Decimal(billing.penalty_amount or 0) == 0`, guaranteeing a single charge per billing across repeated runs.

---

## TL;DR

> **"Rent + a small extra if you're late — charged once, never double."**
> The extra is either a fixed peso amount or a percentage of rent, and only starts counting *after* the due date plus the grace period.
