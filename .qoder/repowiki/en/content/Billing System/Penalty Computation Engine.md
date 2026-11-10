# Penalty Computation Engine

<cite>
**Referenced Files in This Document**
- [core/helpers.py](file://core/helpers.py)
- [core/views/billing.py](file://core/views/billing.py)
- [core/models.py](file://core/models.py)
- [core/management/commands/apply_penalties.py](file://core/management/commands/apply_penalties.py)
- [core/test_overdue_penalties.py](file://core/test_overdue_penalties.py)
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
This document explains the penalty computation engine used by the market rental system to calculate and apply late penalties on unpaid billing records. It focuses on:

- The core penalty calculation logic that resolves contract-specific or system-wide settings.
- The two supported penalty types: fixed amounts and percentage-based calculations.
- Grace period logic that prevents penalties during the initial grace period after due dates.
- How penalties are applied to billing records and how they affect total_due and balance.
- The periodic application mechanism through maybe_apply_overdue_penalties() and its role in maintaining billing accuracy.

The documentation is designed for both technical readers and non-technical users who need to understand why and how penalties are added to bills.

## Project Structure
The penalty engine spans several layers:

- Models define system-wide defaults, per-contract overrides, and billing fields affected by penalties.
- Helper functions implement the authoritative penalty math and the automated sweep.
- Billing views compute penalties when generating billings and trigger periodic penalty application.
- A management command provides a manual entry point for applying overdue penalties.
- Tests validate idempotency, grace period behavior, and throttling.

```mermaid
graph TB
subgraph "Models"
SS["SystemSetting"]
PS["PenaltySetting"]
BI["Billing"]
TL["TenantLedger"]
end
subgraph "Logic"
CPFC["compute_penalty_for_contract()"]
AOP["apply_overdue_penalties()"]
MAOP["maybe_apply_overdue_penalties()"]
end
subgraph "Views"
BL["billing_list()"]
BG["billing_generate() / billing_generate_all()"]
end
subgraph "CLI"
AP["apply_penalties command"]
end
SS --> CPFC
PS --> CPFC
CPFC --> BI
BG --> CPFC
BL --> MAOP
MAOP --> AOP
AOP --> BI
AOP --> TL
AP --> AOP
```

**Diagram sources**
- [core/models.py:42-68](file://core/models.py#L42-L68)
- [core/models.py:319-335](file://core/models.py#L319-L335)
- [core/models.py:190-218](file://core/models.py#L190-L218)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/views/billing.py:174-246](file://core/views/billing.py#L174-L246)
- [core/management/commands/apply_penalties.py:1-13](file://core/management/commands/apply_penalties.py#L1-L13)

**Section sources**
- [core/models.py:42-68](file://core/models.py#L42-L68)
- [core/models.py:190-218](file://core/models.py#L190-L218)
- [core/models.py:319-335](file://core/models.py#L319-L335)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/views/billing.py:174-246](file://core/views/billing.py#L174-L246)
- [core/management/commands/apply_penalties.py:1-13](file://core/management/commands/apply_penalties.py#L1-L13)

## Core Components
The penalty engine is built around these key components:

- SystemSetting: stores market-wide defaults such as penalty_type, penalty_value, and grace_period.
- PenaltySetting: allows per-contract overrides of penalty type, value, and grace period.
- Billing: holds rental_amount, penalty_amount, total_due, amount_paid, balance, due_date, and status.
- TenantLedger: records audit trail entries including penalty debits.
- compute_penalty_for_contract(): central function that computes the one-time penalty based on resolved settings and grace period.
- apply_overdue_penalties(): scans unpaid or overdue billings, applies penalties once, updates totals, and maintains ledger consistency.
- maybe_apply_overdue_penalties(): throttles the sweep to run at most once per day per cache instance.
- billing views: compute penalties when generating billings and trigger periodic penalty application.
- apply_penalties management command: manual CLI wrapper for applying overdue penalties without throttling.

**Section sources**
- [core/models.py:42-68](file://core/models.py#L42-L68)
- [core/models.py:190-218](file://core/models.py#L190-L218)
- [core/models.py:319-335](file://core/models.py#L319-L335)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/management/commands/apply_penalties.py:1-13](file://core/management/commands/apply_penalties.py#L1-L13)

## Architecture Overview
The penalty engine integrates configuration, calculation, application, and auditing into a cohesive flow:

- Configuration resolution:
  - If a contract has an active PenaltySetting, it overrides system defaults.
  - Otherwise, SystemSetting values are used.
- Calculation:
  - If today is within due_date + grace_period, penalty is zero.
  - For fixed type, penalty equals penalty_value.
  - For percentage type, penalty equals monthly_rent × (penalty_value / 100).
- Application:
  - Only one penalty per billing; repeated runs do not double-charge.
  - Updates billing.penalty_amount, billing.total_due, and billing.balance.
  - Creates a TenantLedger debit row for audit trail.
  - Recalculates tenant ledger running balances.
- Throttling:
  - maybe_apply_overdue_penalties() ensures the sweep runs at most once per day per instance.
- Entry points:
  - Automatic: billing_list(), billing print/export views.
  - Manual: apply_penalties management command.

```mermaid
sequenceDiagram
participant View as "billing_list()"
participant Trigger as "maybe_apply_overdue_penalties()"
participant Sweep as "apply_overdue_penalties()"
participant Resolver as "compute_penalty_for_contract()"
participant DB as "Billing / TenantLedger"
View->>Trigger : request billing list
Trigger->>Trigger : claim daily cache slot
Trigger->>Sweep : run if first call today
Sweep->>DB : query Unpaid/Partial/Overdue billings
Sweep->>Resolver : resolve settings and compute penalty
Resolver-->>Sweep : penalty amount
Sweep->>DB : update penalty_amount, total_due, balance
Sweep->>DB : create TenantLedger debit row
Sweep->>DB : recalc_tenant_ledger(tenant)
Sweep-->>View : overdue_marked, penalties_applied
```

**Diagram sources**
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/models.py:190-218](file://core/models.py#L190-L218)

## Detailed Component Analysis

### Penalty Calculation Logic: compute_penalty_for_contract()
This function is the single source of truth for penalty math. It:

- Reads SystemSetting as the global default.
- Checks for an active PenaltySetting on the contract; if present, uses it instead.
- Computes effective_due = due_date + grace_period.
- Returns zero if today is within the grace period.
- Applies fixed or percentage logic:
  - Fixed: penalty equals penalty_value.
  - Percentage: penalty equals monthly_rent × (penalty_value / 100), quantized to two decimals.

```mermaid
flowchart TD
Start(["Start compute_penalty_for_contract"]) --> ReadSettings["Read SystemSetting"]
ReadSettings --> CheckContract{"Active PenaltySetting exists?"}
CheckContract --> |Yes| UseContract["Use contract penalty_type/value/grace"]
CheckContract --> |No| UseSystem["Use system penalty_type/value/grace"]
UseContract --> ComputeDue["Compute effective_due = due_date + grace"]
UseSystem --> ComputeDue
ComputeDue --> GraceCheck{"today <= effective_due?"}
GraceCheck --> |Yes| ReturnZero["Return 0.00"]
GraceCheck --> |No| TypeCheck{"penalty_type == 'fixed'?"}
TypeCheck --> |Yes| Fixed["Return penalty_value"]
TypeCheck --> |No| Percent["Return monthly_rent * (penalty_value / 100)"]
Fixed --> End(["End"])
Percent --> End
ReturnZero --> End
```

**Diagram sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)

**Section sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)

### Periodic Penalty Application: apply_overdue_penalties()
This function performs the automated sweep:

- Loads SystemSetting and determines default_grace if no settings exist.
- Queries billings with status Unpaid, Partial, or Overdue.
- For each billing:
  - Resolves grace from PenaltySetting or default_grace.
  - Skips if today is within effective_due.
  - If penalty_amount is still zero, computes penalty via compute_penalty_for_contract().
  - Updates billing.penalty_amount, total_due, and balance.
  - Creates a TenantLedger debit row describing the overdue penalty.
  - Records an AuditLog entry.
  - Recomputes billing status based on updated balance.
- After processing all billings, recalculates tenant ledgers for affected tenants.

```mermaid
flowchart TD
Start(["Start apply_overdue_penalties"]) --> LoadSettings["Load SystemSetting and default_grace"]
LoadSettings --> QueryBillings["Query Unpaid/Partial/Overdue billings"]
QueryBillings --> Loop{"For each billing"}
Loop --> ResolveGrace["Resolve grace from PenaltySetting or default_grace"]
ResolveGrace --> EffectiveDue["effective_due = due_date + grace"]
EffectiveDue --> GraceSkip{"today <= effective_due?"}
GraceSkip --> |Yes| NextBilling["Skip this billing"]
GraceSkip --> |No| CheckPenalty{"penalty_amount == 0?"}
CheckPenalty --> |No| NextBilling
CheckPenalty --> |Yes| ComputePenalty["Compute penalty via compute_penalty_for_contract()"]
ComputePenalty --> UpdateFields["Update penalty_amount, total_due, balance"]
UpdateFields --> CreateLedger["Create TenantLedger debit row"]
CreateLedger --> AuditLog["Create AuditLog entry"]
AuditLog --> RecalcStatus["Recompute billing.status from balance"]
RecalcStatus --> SaveBilling["Save billing changes"]
SaveBilling --> NextBilling
NextBilling --> Done["Recalc tenant ledgers for affected tenants"]
Done --> End(["Return overdue_marked, penalties_applied"])
```

**Diagram sources**
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/models.py:190-218](file://core/models.py#L190-L218)

**Section sources**
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)

### Throttled Trigger: maybe_apply_overdue_penalties()
This function wraps the sweep behind a daily cache key:

- Uses a cache.add(key, 1, timeout=24 hours) to ensure only one run per day per instance.
- Calls apply_overdue_penalties(today).
- Catches exceptions and deletes the cache key to allow retry on next request.

```mermaid
sequenceDiagram
participant Caller as "billing_list() / print/export views"
participant Maybe as "maybe_apply_overdue_penalties()"
participant Cache as "Django cache"
participant Sweep as "apply_overdue_penalties()"
Caller->>Maybe : request
Maybe->>Cache : add(key, 1, 24h)
alt First call today
Cache-->>Maybe : success
Maybe->>Sweep : run sweep
Sweep-->>Maybe : results
else Subsequent calls today
Cache-->>Maybe : already claimed
Maybe-->>Caller : no-op
end
```

**Diagram sources**
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)

**Section sources**
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)

### Billing Views Integration: compute_penalty() and Generation Flows
The billing views include a local compute_penalty() function used when manually generating billings:

- Resolves settings similarly to compute_penalty_for_contract().
- Honors grace period before computing penalty.
- Supports fixed and percentage types.
- Used in billing_generate() and billing_generate_all() to set penalty_amount and total_due.

Additionally, billing_list() triggers ensure_current_month_billings() and maybe_apply_overdue_penalties() to keep billings current and penalties applied automatically.

```mermaid
sequenceDiagram
participant Admin as "Admin UI"
participant Generate as "billing_generate()/billing_generate_all()"
participant Calc as "compute_penalty()"
participant DB as "Billing / TenantLedger"
Admin->>Generate : submit generate form
Generate->>Calc : compute_penalty(contract, month, year, due_date)
Calc-->>Generate : penalty_amount
Generate->>DB : create Billing with total_due = rental + penalty
Generate->>DB : create TenantLedger debit row
Generate-->>Admin : redirect to billing list
```

**Diagram sources**
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:174-246](file://core/views/billing.py#L174-L246)

**Section sources**
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/views/billing.py:174-246](file://core/views/billing.py#L174-L246)

### Management Command: apply_penalties
A thin CLI wrapper over apply_overdue_penalties():

- Invokes apply_overdue_penalties() directly without throttling.
- Prints summary counts for overdue marked and penalties applied.

**Section sources**
- [core/management/commands/apply_penalties.py:1-13](file://core/management/commands/apply_penalties.py#L1-L13)

### Data Model Relationships
The models involved in penalty computation and application:

- SystemSetting: global defaults for penalty_type, penalty_value, grace_period.
- PenaltySetting: per-contract override for penalty_type, penalty_value, grace_period, due_day, is_active.
- Billing: fields updated by penalties include penalty_amount, total_due, balance, status.
- TenantLedger: records penalty debits and running balances.

```mermaid
classDiagram
class SystemSetting {
+string municipality_name
+string market_name
+string office_name
+string receipt_prefix
+int default_due_day
+string penalty_type
+decimal penalty_value
+int grace_period
+image logo
+string theme_color
+text terms_and_conditions
}
class PenaltySetting {
+RentalContract contract
+string penalty_type
+decimal penalty_value
+int grace_period
+int due_day
+bool is_active
}
class Billing {
+Tenant tenant
+Stall stall
+RentalContract contract
+int billing_month
+int billing_year
+decimal rental_amount
+decimal penalty_amount
+decimal discount
+decimal total_due
+decimal amount_paid
+decimal balance
+date due_date
+string status
}
class TenantLedger {
+Tenant tenant
+Billing billing
+date transaction_date
+string description
+decimal debit
+decimal credit
+decimal balance
+Payment payment
}
SystemSetting <.. PenaltySetting : "defaults vs overrides"
PenaltySetting --> RentalContract : "per-contract rule"
Billing --> RentalContract : "uses contract settings"
TenantLedger --> Billing : "audit trail"
```

**Diagram sources**
- [core/models.py:42-68](file://core/models.py#L42-L68)
- [core/models.py:319-335](file://core/models.py#L319-L335)
- [core/models.py:190-218](file://core/models.py#L190-L218)

**Section sources**
- [core/models.py:42-68](file://core/models.py#L42-L68)
- [core/models.py:190-218](file://core/models.py#L190-L218)
- [core/models.py:319-335](file://core/models.py#L319-L335)

## Dependency Analysis
Key dependencies and relationships:

- compute_penalty_for_contract() depends on SystemSetting and PenaltySetting to resolve settings.
- apply_overdue_penalties() depends on Billing, TenantLedger, and AuditLog to update state and maintain audit trails.
- maybe_apply_overdue_penalties() depends on Django cache for throttling.
- billing views depend on helpers for penalty computation and periodic application.
- Tests assert expected behavior for grace periods, idempotency, and throttling.

```mermaid
graph LR
SS["SystemSetting"] --> CPFC["compute_penalty_for_contract()"]
PS["PenaltySetting"] --> CPFC
CPFC --> AOP["apply_overdue_penalties()"]
AOP --> BI["Billing"]
AOP --> TL["TenantLedger"]
MAOP["maybe_apply_overdue_penalties()"] --> AOP
BL["billing_list()"] --> MAOP
BG["billing_generate() / billing_generate_all()"] --> CPFC
T["tests"] --> AOP
T --> MAOP
```

**Diagram sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/test_overdue_penalties.py:1-96](file://core/test_overdue_penalties.py#L1-L96)

**Section sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/views/billing.py:29-51](file://core/views/billing.py#L29-L51)
- [core/views/billing.py:63-70](file://core/views/billing.py#L63-L70)
- [core/test_overdue_penalties.py:1-96](file://core/test_overdue_penalties.py#L1-L96)

## Performance Considerations
- Decimal arithmetic is used throughout to avoid float drift in financial totals.
- The sweep queries billings with select_related to reduce N+1 queries.
- maybe_apply_overdue_penalties() throttles execution to once per day per instance using cache.add.
- Ledger recalculation is performed only for affected tenants to minimize overhead.
- Idempotency guard ensures penalties are applied only once per billing, preventing redundant writes.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:

- Penalties not appearing:
  - Ensure SystemSetting exists; without it, penalties default to zero.
  - Verify PenaltySetting is active if contract-specific rules are intended.
  - Confirm today is beyond due_date + grace_period.
- Double-charging concerns:
  - The sweep checks billing.penalty_amount == 0 before applying; repeated runs should not double-charge.
  - Tests assert idempotency across multiple runs.
- Grace period confusion:
  - Within grace period, penalty remains zero and billing status may remain Unpaid or Partial.
  - Once past grace, status becomes Overdue and penalty is applied once.
- Throttling behavior:
  - maybe_apply_overdue_penalties() runs only once per day per instance; subsequent same-day triggers are no-ops.
  - If you need immediate back-filling, use the apply_penalties management command.

**Section sources**
- [core/helpers.py:132-152](file://core/helpers.py#L132-L152)
- [core/helpers.py:423-500](file://core/helpers.py#L423-L500)
- [core/helpers.py:503-520](file://core/helpers.py#L503-L520)
- [core/test_overdue_penalties.py:47-95](file://core/test_overdue_penalties.py#L47-L95)
- [PENALTY_GUIDE.md:1-221](file://PENALTY_GUIDE.md#L1-L221)

## Conclusion
The penalty computation engine provides a robust, auditable mechanism for calculating and applying late penalties:

- Settings resolution supports both system-wide defaults and per-contract overrides.
- Two penalty types—fixed and percentage—are computed consistently.
- Grace period logic protects tenants from penalties during the initial cushion period.
- Penalties are applied idempotently to billing records, updating total_due and balance while recording ledger entries.
- maybe_apply_overdue_penalties() ensures periodic application without overloading the system.
- Tests and documentation confirm expected behavior, making the engine reliable for daily operations.

[No sources needed since this section summarizes without analyzing specific files]