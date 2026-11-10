---
kind: business_term
name: Business Glossary
category: business_term
scope:
    - '**'
---

### collector
- Definition：A staff user role restricted to payment collection and recording actions; they cannot access other administrative sections of the system.
- Aliases：payment collector

### tenant portal
- Definition：The tenant-facing web interface (separate from the admin/staff dashboard) where tenants view their billing history, upcoming due dates, and account information.
- Aliases：tenant dashboard

### bulk assign
- Definition：The bulk tenant-to-stall assignment workflow that lets an admin select multiple vacant stalls in one operation and create a separate `RentalContract` per stall under a single tenant.
- Aliases：bulk stall assignment

### overdue sweep
- Definition：The automatic process that iterates past-due billings, marks them Overdue, applies a one-time penalty (fixed or percentage), updates total_due/balance, and writes a matching TenantLedger entry. It is throttled to once per calendar day via cache.
- Aliases：apply_overdue_penalties、penalty sweep

### grace period
- Definition：A number of days after a billing's due_date during which no late penalty accrues; penalties start on due_date + grace_period + 1.
- Aliases：grace window

### fixed penalty
- Definition：A flat-amount late fee independent of rent (e.g., ₱50), as opposed to a percentage-based rate.

### percentage penalty
- Definition：A late fee calculated as monthly_rent × penalty_value / 100, where penalty_value is expressed as a plain percent number (e.g. 2.00 = 2%).

### batch receipt
- Definition：A single receipt document that covers multiple unpaid/overdue months selected together by a collector, rather than one receipt per month.
- Aliases：multi-month receipt

### grouped overdue display
- Definition：The billing-collection UI layout that groups a tenant's overdue months together so a collector can see all unpaid periods at once before collecting.
