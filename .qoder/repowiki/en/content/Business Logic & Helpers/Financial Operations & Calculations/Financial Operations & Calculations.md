# Financial Operations & Calculations

<cite>
**Referenced Files in This Document**
- [core/helpers.py](file://core/helpers.py)
- [core/models.py](file://core/models.py)
- [core/views/billing.py](file://core/views/billing.py)
- [core/views/payments.py](file://core/views/payments.py)
- [core/views/ledger.py](file://core/views/ledger.py)
- [core/management/commands/apply_penalties.py](file://core/management/commands/apply_penalties.py)
- [PENALTY_GUIDE.md](file://PENALTY_GUIDE.md)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
This document explains the financial operations and calculations module that powers billing generation, payment recording, penalty computation, and tenant ledger management. It focuses on:
- Billing lifecycle from contract creation to payment settlement.
- Penalty calculation with grace periods and idempotent accrual.
- Running balance recalculation for auditability.
- Decimal arithmetic for financial precision.
- Transaction atomicity and concurrency control using `select_for_update`.
- The single source of truth pattern for financial data consistency.
- Error recovery mechanisms such as retry loops and best-effort throttling.

The goal is to make these financial workflows understandable for both technical and non-technical readers while preserving implementation accuracy.

## Project Structure
The financial logic is primarily implemented in a shared helper module and consumed by views and management commands. The key files are:
- `core/helpers.py`: Core financial functions including billing, payments, penalties, and ledger recalculation.
- `core/models.py`: Data models for tenants, contracts, billings, payments, ledgers, settings, and audit logs.
- `core/views/billing.py`: Collector and admin workflows for generating billings and collecting payments.
- `core/views/payments.py`: Payment entry, editing, voiding, and receipt printing.
- `core/views/ledger.py`: Tenant-ledger listing and reporting.
- `core/management/commands/apply_penalties.py`: CLI command to apply overdue penalties.
- `PENALTY_GUIDE.md`: Plain-English explanation of penalty rules and behavior.

```mermaid
graph TB
subgraph "Views"
BV["Billing Views<br/>billing.py"]
PV["Payment Views<br/>payments.py"]
LV["Ledger Views<br/>ledger.py"]
end
subgraph "Financial Services"
H["Core Helpers<br/>helpers.py"]
end
subgraph "Data Layer"
M["Models<br/>models.py"]
end
subgraph "Operations"
C["Apply Penalties Command<br/>apply_penalties.py"]
G["Penalty Guide<br/>PENALTY_GUIDE.md"]
end
BV --> H
PV --> H
LV --> H
C --> H
H --> M
G -.-> H
```

**Diagram sources**
- [core/views/billing.py:18-22](file://core/views/billing.py#L18-L22)
- [core/views/payments.py:15-18](file://core/views/payments.py#L15-L18)
- [core/views/ledger.py:8-9](file://core/views/ledger.py#L8-L9)
- [core/management/commands/apply_penalties.py:1-14](file://core/management/commands/apply_penalties.py#L1-L14)
- [core/helpers.py:15-15](file://core/helpers.py#L15-L15)
- [PENALTY_GUIDE.md:202-213](file://PENALTY_GUIDE.md#L202-L213)

**Section sources**
- [core/helpers.py:1-595](file://core/helpers.py#L1-L595)
- [core/models.py:1-336](file://core/models.py#L1-L336)
- [core/views/billing.py:1-765](file://core/views/billing.py#L1-L765)
- [core/views/payments.py:1-653](file://core/views/payments.py#L1-L653)
- [core/views/ledger.py:1-183](file://core/views/ledger.py#L1-L183)
- [core/management/commands/apply_penalties.py:1-14](file://core/management/commands/apply_penalties.py#L1-L14)
- [PENALTY_GUIDE.md:1-221](file://PENALTY_GUIDE.md#L1-L221)

## Core Components
This section documents the core financial functions and their responsibilities.

- Billing generation (`get_or_create_billing`): Idempotent creation of monthly billings per contract, computing due dates, rental amounts, penalties, totals, and initial ledger entries. It ensures no duplicate billings exist for the same tenant, stall, month, and year.
- Payment recording (`record_payment`): Single source of truth for posting a payment. It locks the target billing row, creates a unique payment record, recomputes billing totals authoritatively, posts a ledger credit, and recalculates the running tenant ledger balance.
- Penalty computation (`compute_penalty_for_contract`): Centralized formula resolver that determines whether a late penalty applies based on system or contract-specific settings, grace period, and due date.
- Ledger management (`recalc_tenant_ledger`): Recomputes running balances across all ledger entries for a tenant in chronological order, ensuring debit/credit chain consistency after edits, voids, or penalties.

Key design principles:
- Decimal arithmetic throughout to avoid floating-point drift.
- Transaction atomicity around critical financial writes.
- Concurrency safety via `select_for_update` on billing rows.
- Idempotency guards to prevent double-charging penalties and duplicate billings.
- Single source of truth for billing state derived from valid payments.

**Section sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:155-205](file://core/helpers.py#L155-L205)
- [core/helpers.py:321-348](file://core/helpers.py#L321-L348)
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

## Architecture Overview
The financial architecture follows a service-oriented approach where views orchestrate user interactions and delegate financial operations to `core.helpers`. Models represent the authoritative data store, and management commands trigger background-like processes (e.g., penalty accrual).

```mermaid
sequenceDiagram
participant User as "Collector/Admin"
participant BillingView as "Billing View<br/>billing_collect"
participant Helper as "Core Helpers<br/>record_payment"
participant DB as "Database<br/>Billing/Payment/TenantLedger"
participant LedgerHelper as "Core Helpers<br/>recalc_tenant_ledger"
User->>BillingView : Submit collection form
BillingView->>Helper : record_payment(tenant, billing, amount, ...)
Helper->>DB : SELECT ... FOR UPDATE (lock billing)
Helper->>DB : INSERT Payment
Helper->>DB : Recalculate billing totals from payments
Helper->>DB : INSERT TenantLedger credit
Helper->>LedgerHelper : recalc_tenant_ledger(tenant)
LedgerHelper->>DB : Update running balances
Helper-->>BillingView : Return Payment object
BillingView-->>User : Redirect to official receipt
```

**Diagram sources**
- [core/views/billing.py:415-489](file://core/views/billing.py#L415-L489)
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:321-348](file://core/helpers.py#L321-L348)
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

## Detailed Component Analysis

### Billing Generation: `get_or_create_billing`
Responsibilities:
- Normalize billing month/year and locate existing billing records.
- Compute due date safely, handling month-end edge cases.
- Calculate rental amount, penalty amount, total due, and initial balance.
- Create the billing record and an initial ledger debit entry.
- Recalculate the tenant ledger to maintain consistent running balances.

Concurrency and idempotency:
- Uses database-level uniqueness constraints to prevent duplicates.
- Safe for concurrent calls because it checks existence before creating.

Decimal usage:
- All monetary values are converted to `Decimal` and quantized to two decimal places.

```mermaid
flowchart TD
Start(["Start get_or_create_billing"]) --> Normalize["Normalize billing_month/billing_year"]
Normalize --> CheckExisting["Check existing billing for tenant/stall/month/year"]
CheckExisting --> Exists{"Exists?"}
Exists --> |Yes| ReturnExisting["Return existing billing, created=False"]
Exists --> |No| ComputeDue["Compute safe due_date"]
ComputeDue --> ComputeAmounts["Compute rental_amount + penalty_amount = total_due"]
ComputeAmounts --> CreateBilling["Create Billing record"]
CreateBilling --> CreateLedgerDebit["Create TenantLedger debit entry"]
CreateLedgerDebit --> RecalcLedger["Recalculate tenant ledger"]
RecalcLedger --> ReturnNew["Return new billing, created=True"]
```

**Diagram sources**
- [core/helpers.py:155-205](file://core/helpers.py#L155-L205)
- [core/helpers.py:125-129](file://core/helpers.py#L125-L129)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)

**Section sources**
- [core/helpers.py:155-205](file://core/helpers.py#L155-L205)
- [core/helpers.py:125-129](file://core/helpers.py#L125-L129)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)

### Payment Recording: `record_payment`
Responsibilities:
- Clamp payment amount to outstanding balance to prevent over-settlement.
- Lock the target billing row with `select_for_update`.
- Generate a unique receipt number and create the payment record within an atomic transaction.
- Recompute billing totals authoritatively from all valid payments.
- Post a ledger credit reflecting the actual applied amount.
- Recalculate the tenant ledger running balance.

Concurrency and error recovery:
- Retries receipt number generation up to five times on integrity errors.
- Ensures billing state is always derived from valid payments, not cached fields.

```mermaid
sequenceDiagram
participant Caller as "Caller"
participant Record as "record_payment"
participant Billing as "Billing Row"
participant Payment as "Payment Row"
participant Ledger as "TenantLedger"
Caller->>Record : record_payment(...)
Record->>Billing : SELECT ... FOR UPDATE
Record->>Record : Quantize amount and clamp to pre_balance
Record->>Payment : INSERT Payment (atomic)
Record->>Billing : Recalculate totals from valid payments
Record->>Ledger : INSERT credit entry
Record->>Record : recalc_tenant_ledger(tenant)
Record-->>Caller : Return Payment
```

**Diagram sources**
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:321-348](file://core/helpers.py#L321-L348)

**Section sources**
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:321-348](file://core/helpers.py#L321-L348)

### Penalty Computation: `compute_penalty_for_contract`
Responsibilities:
- Resolve penalty settings from contract overrides or system defaults.
- Determine grace period and effective due date.
- Apply fixed or percentage penalty formulas only after grace period expires.
- Return zero if no penalty applies.

Idempotency:
- Called during billing creation and penalty accrual; repeated runs do not compound penalties because accrual is guarded by checking current `penalty_amount`.

```mermaid
flowchart TD
Start(["Start compute_penalty_for_contract"]) --> ResolveSettings["Resolve penalty_type/value/grace from contract or system"]
ResolveSettings --> CheckGrace["Compare today vs due_date + grace_period"]
CheckGrace --> GraceOK{"Within grace?"}
GraceOK --> |Yes| Zero["Return 0.00"]
GraceOK --> |No| TypeCheck{"Type == 'fixed'?"}
TypeCheck --> |Yes| Fixed["Return fixed penalty_value"]
TypeCheck --> |No| Percentage["Return percentage of monthly_rent"]
Percentage --> End(["End"])
Fixed --> End
Zero --> End
```

**Diagram sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)

**Section sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [PENALTY_GUIDE.md:15-25](file://PENALTY_GUIDE.md#L15-L25)
- [PENALTY_GUIDE.md:44-63](file://PENALTY_GUIDE.md#L44-L63)

### Ledger Management: `recalc_tenant_ledger`
Responsibilities:
- Iterate through tenant ledger entries in chronological order.
- Compute running balance as cumulative debits minus credits.
- Update any stale balance fields to ensure consistency.

Usage:
- Invoked after billing creation, payment recording, and penalty accrual.
- Ensures the ledger remains a reliable audit trail even after edits or voids.

```mermaid
flowchart TD
Start(["Start recalc_tenant_ledger"]) --> LoadEntries["Load tenant ledger entries ordered by date/id"]
LoadEntries --> InitRunning["Initialize running balance = 0.00"]
InitRunning --> Loop{"For each entry"}
Loop --> UpdateRunning["running += debit - credit; quantize to 0.01"]
UpdateRunning --> CheckStale{"balance != running?"}
CheckStale --> |Yes| UpdateBalance["Update entry.balance = running"]
CheckStale --> |No| NextEntry["Next entry"]
UpdateBalance --> NextEntry
NextEntry --> Done(["Done"])
```

**Diagram sources**
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

**Section sources**
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

### Billing Lifecycle: Contract Creation to Payment Settlement
End-to-end flow:
1. Contract creation triggers initial billing generation for relevant months.
2. Billings are auto-created for active contracts at list entry points.
3. Overdue penalties are applied after grace periods expire.
4. Collectors record payments through a single source of truth function.
5. Payments update billing totals and post ledger credits.
6. Ledgers are recalculated to reflect accurate running balances.

```mermaid
sequenceDiagram
participant Admin as "Admin"
participant Contract as "RentalContract"
participant BillingGen as "ensure_initial_billing / ensure_current_month_billings"
participant BillingSvc as "get_or_create_billing"
participant PenaltySvc as "apply_overdue_penalties"
participant Collector as "Collector"
participant PaymentSvc as "record_payment"
participant LedgerSvc as "recalc_tenant_ledger"
Admin->>Contract : Create contract
Contract->>BillingGen : Ensure initial/current billings
BillingGen->>BillingSvc : get_or_create_billing(month/year)
BillingSvc-->>BillingGen : Billing created
Note over BillingSvc : Initial debit posted to TenantLedger
loop Daily or request-time
PenaltySvc->>BillingSvc : Compute penalties (grace-aware)
PenaltySvc->>LedgerSvc : Recalc affected tenants
end
Collector->>PaymentSvc : Record payment
PaymentSvc->>LedgerSvc : Recalc tenant ledger
PaymentSvc-->>Collector : Official receipt
```

**Diagram sources**
- [core/helpers.py:208-257](file://core/helpers.py#L208-L257)
- [core/helpers.py:155-205](file://core/helpers.py#L155-L205)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

**Section sources**
- [core/helpers.py:208-257](file://core/helpers.py#L208-L257)
- [core/helpers.py:155-205](file://core/helpers.py#L155-L205)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

### Penalty Calculation Algorithms with Grace Periods
Key behaviors:
- Penalty applies only after `today > due_date + grace_period`.
- Supports fixed and percentage penalty types.
- One-time charge per billing; repeated sweeps do not compound.
- System defaults can be overridden per contract.

Operational notes:
- The sweep marks billings overdue and accrues penalties when conditions are met.
- A throttled trigger ensures at most one run per day per cache instance.

```mermaid
flowchart TD
Start(["Sweep apply_overdue_penalties"]) --> LoadBillings["Load unpaid/partial/overdue billings"]
LoadBillings --> ForEach["For each billing"]
ForEach --> ResolveGrace["Resolve grace period from contract/system"]
ResolveGrace --> EffectiveDue["effective_due = due_date + grace"]
EffectiveDue --> CheckToday{"today <= effective_due?"}
CheckToday --> |Yes| Skip["Skip — still within grace"]
CheckToday --> |No| CheckPenaltyAmt{"penalty_amount == 0?"}
CheckPenaltyAmt --> |Yes| Accrue["Accrue one-time penalty via compute_penalty_for_contract"]
Accrue --> UpdateFields["Update penalty_amount, total_due, balance"]
UpdateFields --> PostLedger["Post TenantLedger debit for penalty"]
PostLedger --> MarkOverdue["Set status = Overdue if balance > 0"]
CheckPenaltyAmt --> |No| MarkOverdue
MarkOverdue --> Next["Next billing"]
Skip --> Next
Next --> RecalcTenants["Recalc affected tenant ledgers"]
RecalcTenants --> End(["End"])
```

**Diagram sources**
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)

**Section sources**
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [PENALTY_GUIDE.md:29-40](file://PENALTY_GUIDE.md#L29-L40)
- [PENALTY_GUIDE.md:131-140](file://PENALTY_GUIDE.md#L131-L140)

### Running Balance Recalculation
Purpose:
- Maintain a consistent running balance across all ledger entries for a tenant.
- Correct stale balances after edits, voids, or penalty accruals.

Algorithm:
- Order entries chronologically.
- Accumulate debits and credits to compute running balance.
- Update any mismatched balance fields.

**Section sources**
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

## Dependency Analysis
The financial module has clear dependencies between views, helpers, and models. Views depend on helpers for financial operations; helpers depend on models for persistence.

```mermaid
graph LR
BV["Billing Views"] --> H["Helpers"]
PV["Payment Views"] --> H
LV["Ledger Views"] --> H
CMD["Apply Penalties Command"] --> H
H --> M["Models"]
```

**Diagram sources**
- [core/views/billing.py:18-22](file://core/views/billing.py#L18-L22)
- [core/views/payments.py:15-18](file://core/views/payments.py#L15-L18)
- [core/views/ledger.py:8-9](file://core/views/ledger.py#L8-L9)
- [core/management/commands/apply_penalties.py:1-14](file://core/management/commands/apply_penalties.py#L1-L14)
- [core/helpers.py:15-15](file://core/helpers.py#L15-L15)

**Section sources**
- [core/views/billing.py:18-22](file://core/views/billing.py#L18-L22)
- [core/views/payments.py:15-18](file://core/views/payments.py#L15-L18)
- [core/views/ledger.py:8-9](file://core/views/ledger.py#L8-L9)
- [core/management/commands/apply_penalties.py:1-14](file://core/management/commands/apply_penalties.py#L1-L14)
- [core/helpers.py:15-15](file://core/helpers.py#L15-L15)

## Performance Considerations
- Use `select_related` in views to reduce N+1 queries when loading related entities like tenants, stalls, and contracts.
- Batch operations should minimize repeated ledger recalculations; prefer targeted recalculations for affected tenants.
- Receipt number generation scans existing records; consider indexing by prefix patterns if volume grows significantly.
- Penalty sweeps iterate billings; ensure appropriate filtering and indexes on status, due_date, and billing_month/year.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Duplicate billings: Ensure `get_or_create_billing` is used instead of direct inserts; verify unique constraints on tenant/stall/month/year.
- Incorrect billing totals: Always use `recalc_billing_from_payments` to derive totals from valid payments; avoid manual updates to `amount_paid` or `balance`.
- Stale ledger balances: Call `recalc_tenant_ledger` after any edit, void, or penalty accrual.
- Double penalties: Confirm idempotency guard in `apply_overdue_penalties`; check that `penalty_amount` is non-zero after first accrual.
- Concurrency conflicts: Ensure payment collection uses `select_for_update` on billing rows; wrap critical sections in `transaction.atomic`.
- Receipt collisions: `record_payment` retries receipt number generation up to five times on integrity errors.

**Section sources**
- [core/helpers.py:351-420](file://core/helpers.py#L351-L420)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:321-348](file://core/helpers.py#L321-L348)
- [core/helpers.py:260-273](file://core/helpers.py#L260-L273)

## Conclusion
The financial operations module enforces precision, consistency, and reliability through:
- Decimal arithmetic for all monetary calculations.
- Transactional atomicity and row-level locking to handle concurrency safely.
- Idempotent billing and penalty processes to prevent duplicate charges.
- A single source of truth for billing state derived from valid payments.
- Robust ledger recalculation to maintain auditability.

These patterns collectively ensure that billing generation, payment recording, penalty computation, and ledger management remain consistent under real-world operational conditions.