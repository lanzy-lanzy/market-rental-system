# Project Overview

<cite>
**Referenced Files in This Document**
- [README.MD](file://README.MD)
- [settings.py](file://market_rental/settings.py)
- [models.py](file://core/models.py)
- [permissions.py](file://core/permissions.py)
- [dashboard.py](file://core/views/dashboard.py)
- [input.css](file://static/css/input.css)
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
The Market Rental System is a municipal public market rental and collection management solution. It centralizes stall assignments, tenant records, billing, payments, penalties, notices, reports, user roles, and audit trails into one Django-based web application. Its purpose is to digitize market operations, improve transparency, reduce manual collection work, and provide administrators, collectors, supervisors, and tenants with clear, role-appropriate access to market data.

Key objectives include:
- Digitizing market stall rentals and tenant administration.
- Automating monthly billing and penalty computation.
- Streamlining payment recording, receipt generation, and balance updates.
- Providing transparent dashboards, reports, and audit logs for accountability.
- Supporting both development convenience and production-grade deployment.

Target audience:
- Administrators: full system control, user and settings management, reporting, and oversight.
- Market Collectors: focused workspace for recording collections and viewing assigned or open accounts.
- Supervisors and Treasurers: monitoring unpaid rentals, verifying payments, and exporting reports.
- Tenants: self-service portal to view rental information, balances, due dates, notices, and payment history.

Why this system was built:
Municipal markets traditionally rely on paper-based processes that are slow, error-prone, and difficult to audit. This system replaces those workflows with a structured digital process that enforces business rules such as one active tenant per stall, automatic overdue marking, penalty computation, and immutable audit trails. The result is faster collections, clearer visibility into revenue, and stronger compliance.

**Section sources**
- [README.MD:1-21](file://README.MMD#L1-L21)
- [README.MD:23-59](file://README.MD#L23-L59)
- [README.MD:411-422](file://README.MD#L411-L422)

## Project Structure
At a high level, the project follows a standard Django layout:
- `market_rental/` contains Django project configuration, including settings, URLs, and WSGI/ASGI entry points.
- `core/` holds the main application models, permissions, views, forms, templates, management commands, and tests.
- `accounts/` provides additional account-related functionality.
- `templates/` organizes UI templates by feature area such as billing, contracts, payments, reports, stalls, tenants, users, notices, ledger, and tenant portal.
- `static/` contains local CSS and JavaScript assets, including Tailwind CSS input styles.
- `api/`, `backups/`, and documentation files support integration, maintenance, and design guidance.

```mermaid
graph TB
Client["Browser<br/>Tenant, Collector, Supervisor, Administrator"] --> Django["Django Backend<br/>market_rental/urls + core views"]
Django --> Models["Domain Models<br/>core/models.py"]
Django --> Permissions["Role & Permission Layer<br/>core/permissions.py"]
Django --> Templates["Django Templates<br/>templates/*"]
Django --> Database["Database<br/>SQLite / MySQL / PostgreSQL"]
Templates --> Static["Static Assets<br/>Tailwind CSS + HTMX"]
```

**Diagram sources**
- [settings.py:28-51](file://market_rental/settings.py#L28-L51)
- [models.py:7-336](file://core/models.py#L7-L336)
- [permissions.py:1-125](file://core/permissions.py#L1-L125)
- [input.css:1-10](file://static/css/input.css#L1-L10)

**Section sources**
- [settings.py:28-51](file://market_rental/settings.py#L28-L51)
- [README.MD:478-515](file://README.MD#L478-L515)

## Core Components
The system’s core revolves around domain entities that represent real-world market objects and their relationships:

- User and Profile:
  - `UserProfile` extends Django’s `User` with role metadata such as admin, collector, cashier, supervisor, treasurer, and tenant.
  - Roles drive access control and dashboard routing.

- Market Infrastructure:
  - `MarketSection` and `StallType` classify market areas and stall categories.
  - `Stall` tracks stall number, section, type, size, monthly rate, status, and remarks.

- Tenant and Contract Lifecycle:
  - `Tenant` stores personal, contact, identification, business, and status details.
  - `RentalContract` links a tenant to a stall with start/end dates, monthly rent, due day, security deposit, and contract status.
  - A database constraint ensures only one active contract per stall.

- Billing and Payments:
  - `Billing` represents monthly collectibles derived from active contracts, including rental amount, penalty, discount, total due, amount paid, balance, due date, and status.
  - `Payment` records actual collections with receipt numbers, payment method, official receipt number, collector, and status.
  - `TenantLedger` maintains running debit/credit entries tied to billings and payments.

- Notices, Settings, Penalties, and Audit:
  - `Notice` supports payment reminders, overdue notices, final demands, and vacancy notices.
  - `SystemSetting` centralizes municipality/market branding, receipt prefix, default due day, penalty configuration, logo, theme color, and contract terms.
  - `PenaltySetting` allows per-contract penalty type, value, grace period, due day, and activation state.
  - `AuditLog` records user actions, modules, descriptions, timestamps, and optional IP addresses.

This model set directly implements the documented requirements for tenants, stalls, contracts, billing, payments, ledgers, notices, settings, penalties, and audit trails.

```mermaid
erDiagram
USER {
uuid id PK
string username
string email
boolean is_superuser
}
USER_PROFILE {
int id PK
int user_id FK
string role
string phone
text address
boolean must_change_password
}
MARKET_SECTION {
int id PK
string name UK
text description
}
STALL_TYPE {
int id PK
string name UK
text description
}
STALL {
int id PK
string stall_number UK
int section_id FK
int stall_type_id FK
decimal size
decimal monthly_rate
string status
text remarks
timestamp created_at
timestamp updated_at
}
TENANT {
int id PK
string tenant_id UK
int user_id FK
string full_name
string contact_number
string email
string status
date date_registered
}
RENTAL_CONTRACT {
int id PK
int tenant_id FK
int stall_id FK
date start_date
date end_date
decimal monthly_rent
int due_day
decimal security_deposit
string status
text remarks
timestamp created_at
timestamp updated_at
}
BILLING {
int id PK
int tenant_id FK
int stall_id FK
int contract_id FK
int billing_month
int billing_year
decimal rental_amount
decimal penalty_amount
decimal discount
decimal total_due
decimal amount_paid
decimal balance
date due_date
string status
timestamp created_at
timestamp updated_at
}
PAYMENT {
int id PK
string receipt_number UK
int tenant_id FK
int stall_id FK
int billing_id FK
int billing_month
int billing_year
decimal rental_amount
decimal penalty_amount
decimal discount
decimal total_amount_due
decimal amount_paid
date payment_date
string payment_method
string official_receipt_no
int collected_by_user_id FK
string status
text remarks
timestamp created_at
timestamp updated_at
}
TENANT_LEDGER {
int id PK
int tenant_id FK
int billing_id FK
date transaction_date
string description
decimal debit
decimal credit
decimal balance
int payment_id FK
timestamp created_at
}
NOTICE {
int id PK
int tenant_id FK
string notice_type
string notice_number UK
date date_issued
boolean is_served
date served_date
text remarks
text content
timestamp created_at
}
SYSTEM_SETTING {
int id PK
string municipality_name
string market_name
string office_name
string receipt_prefix
int default_due_day
string penalty_type
decimal penalty_value
int grace_period
image logo
string theme_color
text terms_and_conditions
}
PENALTY_SETTING {
int id PK
int contract_id FK
string penalty_type
decimal penalty_value
int grace_period
int due_day
boolean is_active
}
AUDIT_LOG {
int id PK
int user_id FK
string action
string module
text description
string ip_address
timestamp created_at
}
USER ||--o| USER_PROFILE : "has profile"
TENANT ||--o| RENTAL_CONTRACT : "signs"
STALL ||--o| RENTAL_CONTRACT : "is rented by"
TENANT ||--o{ BILLING : "owes"
STALL ||--o{ BILLING : "generates"
RENTAL_CONTRACT ||--o{ BILLING : "produces"
TENANT ||--o{ PAYMENT : "pays"
STALL ||--o{ PAYMENT : "paid for"
BILLING ||--o{ PAYMENT : "settled by"
TENANT ||--o{ TENANT_LEDGER : "ledgered"
BILLING ||--o{ TENANT_LEDGER : "referenced"
PAYMENT ||--o{ TENANT_LEDGER : "posted"
TENANT ||--o{ NOTICE : "receives"
RENTAL_CONTRACT ||--o{ PENALTY_SETTING : "uses"
USER ||--o{ AUDIT_LOG : "performs"
```

**Diagram sources**
- [models.py:7-336](file://core/models.py#L7-L336)

**Section sources**
- [models.py:7-336](file://core/models.py#L7-L336)
- [README.MD:378-393](file://README.MD#L378-L393)

## Architecture Overview
The Market Rental System uses a layered architecture:
- Presentation layer: Django templates styled with Tailwind CSS and enhanced with HTMX interactivity.
- Application layer: Django views and helpers implement business logic for dashboards, billing, payments, reports, and tenant portals.
- Domain layer: Django models define market entities and enforce constraints such as unique active contracts per stall and unique billing per tenant-stall-month-year.
- Data layer: SQLite for development, with MySQL or PostgreSQL supported through environment-driven configuration.

```mermaid
graph TB
subgraph "Presentation"
TPL["Django Templates<br/>billing, payments, reports, tenant portal"]
CSS["Tailwind CSS<br/>static/css/input.css"]
HTMX["HTMX Interactivity<br/>modals, filters, dynamic updates"]
end
subgraph "Application"
VIEWS["Views<br/>dashboard, billing, payments, reports, tenants, stalls"]
PERM["Permissions<br/>role decorators and tenant isolation"]
end
subgraph "Domain"
MODELS["Models<br/>Tenant, Stall, Contract, Billing, Payment, Ledger, Notice, Audit"]
end
subgraph "Data"
DB["Database<br/>SQLite / MySQL / PostgreSQL"]
end
TPL --> VIEWS
CSS --> TPL
HTMX --> TPL
VIEWS --> PERM
VIEWS --> MODELS
MODELS --> DB
```

**Diagram sources**
- [settings.py:28-69](file://market_rental/settings.py#L28-L69)
- [input.css:1-10](file://static/css/input.css#L1-L10)
- [permissions.py:61-87](file://core/permissions.py#L61-L87)
- [models.py:157-277](file://core/models.py#L157-L277)

### User Role Hierarchy
Roles determine what users can see and do:
- Administrator: full access across all modules.
- Cashier: administrative staff capable of managing records and collecting payments.
- Supervisor/Treasurer: supervisory access to reports, verification, and export functions.
- Market Collector: limited to recording collections and viewing relevant queues; excluded from billing generation and broader administration.
- Tenant: self-service portal scoped to their own tenant record.

```mermaid
flowchart TD
Start(["User Login"]) --> CheckRole{"Role Check"}
CheckRole --> |Administrator| AdminDashboard["Full Dashboard<br/>Users, Stalls, Tenants, Contracts, Reports"]
CheckRole --> |Cashier| ManagementDashboard["Management Dashboard<br/>Records + Collections"]
CheckRole --> |Supervisor| SupervisorDashboard["Supervisor Dashboard<br/>Reports + Verification"]
CheckRole --> |Treasurer| TreasurerDashboard["Treasurer Dashboard<br/>Reports + Export"]
CheckRole --> |Collector| CollectorDashboard["Collector Dashboard<br/>Own Collections + Open Queue"]
CheckRole --> |Tenant| TenantPortal["Tenant Portal<br/>Own Rentals, Balances, History, Notices"]
```

**Diagram sources**
- [permissions.py:6-30](file://core/permissions.py#L6-L30)
- [permissions.py:41-87](file://core/permissions.py#L41-L87)
- [dashboard.py:41-60](file://core/views/dashboard.py#L41-L60)

**Section sources**
- [permissions.py:6-30](file://core/permissions.py#L6-L30)
- [permissions.py:41-87](file://core/permissions.py#L41-L87)
- [dashboard.py:41-60](file://core/views/dashboard.py#L41-L60)

### Key Business Workflows
- Monthly Billing Generation:
  - Active contracts produce billings for each billing month/year.
  - Billing includes rental amount, penalty, discount, total due, and computed balance.
  - Unique constraints prevent duplicate billing for the same tenant, stall, month, and year.

- Payment Recording:
  - Payments reference a billing, tenant, stall, and collector.
  - Full payment marks billing as Paid; partial payment updates balance.
  - Receipt numbers and official receipt numbers ensure traceability.

- Overdue and Penalty Handling:
  - Overdue status is applied after due dates based on settings.
  - Penalty settings allow fixed or percentage-based penalties with grace periods.
  - Dashboard and collector views may trigger overdue penalty checks.

- Tenant Isolation:
  - Tenant users see only their own data via permission helpers.
  - Collector users see only their own collections and open queues.

```mermaid
sequenceDiagram
participant Admin as "Administrator"
participant View as "Billing View"
participant Model as "Billing Model"
participant Payment as "Payment View"
participant Ledger as "TenantLedger Model"
Admin->>View : Generate monthly billing
View->>Model : Create Billing for active contracts
Model-->>View : Billing records with due dates and totals
Admin->>Payment : Record payment
Payment->>Model : Update Billing amount_paid and balance
Payment->>Ledger : Post debit/credit entry
Ledger-->>Payment : Running balance recorded
```

**Diagram sources**
- [models.py:190-277](file://core/models.py#L190-L277)
- [dashboard.py:96-101](file://core/views/dashboard.py#L96-L101)

**Section sources**
- [models.py:157-277](file://core/models.py#L157-L277)
- [dashboard.py:96-101](file://core/views/dashboard.py#L96-L101)

## Detailed Component Analysis

### Technology Stack
- Backend: Django with function/class-based views, authentication, middleware, and context processors.
- Frontend: Django templates with Tailwind CSS 4 and HTMX for dynamic interactions.
- Styling: Local Tailwind build with an “Emerald Glass” design system, neumorphic components, and print-ready receipts/reports.
- Database: SQLite by default for zero-config development; MySQL via XAMPP or managed services; PostgreSQL supported through `DATABASE_URL`.
- Deployment: Environment-driven secrets, static file compression, CSRF and session security, and Vercel-friendly host configuration.

**Section sources**
- [settings.py:1-20](file://market_rental/settings.py#L1-L20)
- [settings.py:28-69](file://market_rental/settings.py#L28-L69)
- [settings.py:109-152](file://market_rental/settings.py#L109-L152)
- [settings.py:166-199](file://market_rental/settings.py#L166-L199)
- [input.css:1-10](file://static/css/input.css#L1-L10)
- [input.css:19-84](file://static/css/input.css#L19-L84)

### Role-Based Access Control
The permission layer defines canonical role groups and decorators:
- `ADMIN_ROLES`, `MANAGEMENT_ROLES`, `COLLECTOR_ROLES`, `SUPERVISOR_ROLES`, `STAFF_ROLES`, `ALL_ROLES`.
- Helper functions like `is_admin`, `is_staff_role`, `is_collector`, `is_management`.
- Decorators such as `admin_required`, `management_required`, `staff_required`, `collector_required`, `supervisor_required`.
- Tenant isolation utilities restrict non-admin users to their own tenant data.

```mermaid
classDiagram
class Permissions {
+ADMIN_ROLES
+MANAGEMENT_ROLES
+COLLECTOR_ROLES
+SUPERVISOR_ROLES
+STAFF_ROLES
+ALL_ROLES
+get_user_role(user)
+is_admin(user)
+is_staff_role(user)
+is_collector(user)
+is_management(user)
+role_required(allowed_roles)
+tenant_isolation_queryset(request, queryset, tenant_field)
+tenant_required(view_func)
+get_request_tenant(user)
}
```

**Diagram sources**
- [permissions.py:6-30](file://core/permissions.py#L6-L30)
- [permissions.py:32-87](file://core/permissions.py#L32-L87)
- [permissions.py:89-125](file://core/permissions.py#L89-L125)

**Section sources**
- [permissions.py:6-30](file://core/permissions.py#L6-L30)
- [permissions.py:32-87](file://core/permissions.py#L32-L87)
- [permissions.py:89-125](file://core/permissions.py#L89-L125)

### Dashboard and Collector Workspace
The dashboard routes users based on role:
- Tenants are redirected to the tenant portal unless they are superusers.
- Collectors receive a focused dashboard showing their own collections, today’s and monthly totals, receipts issued, open billings, and recent payments.
- Staff dashboards compute market-wide metrics such as stalls, tenants, collectibles, collected amounts, unpaid balances, overdue accounts, and collection percentages.
- Overdue penalty application is attempted best-effort during dashboard rendering.

```mermaid
flowchart TD
Entry(["Dashboard Request"]) --> RoleCheck["Resolve User Role"]
RoleCheck --> TenantRoute{"Is Tenant?"}
TenantRoute --> |Yes| TenantPortal["Redirect to Tenant Portal"]
TenantRoute --> |No| CollectorRoute{"Is Collector?"}
CollectorRoute --> |Yes| CollectorDash["Compute Own Collections<br/>Open Billings<br/>Recent Payments"]
CollectorRoute --> |No| StaffDash["Compute Market Metrics<br/>Overdue Checks<br/>Recent Payments"]
CollectorDash --> Render["Render Dashboard Template"]
StaffDash --> Render
```

**Diagram sources**
- [dashboard.py:12-38](file://core/views/dashboard.py#L12-L38)
- [dashboard.py:41-60](file://core/views/dashboard.py#L41-L60)
- [dashboard.py:96-164](file://core/views/dashboard.py#L96-L164)

**Section sources**
- [dashboard.py:12-38](file://core/views/dashboard.py#L12-L38)
- [dashboard.py:41-60](file://core/views/dashboard.py#L41-L60)
- [dashboard.py:96-164](file://core/views/dashboard.py#L96-L164)

### Billing, Payments, and Ledgers
- Billing:
  - Represents monthly obligations for active contracts.
  - Enforces uniqueness per tenant, stall, billing month, and billing year.
  - Tracks rental amount, penalty, discount, total due, amount paid, balance, due date, and status.

- Payments:
  - Records actual collections with receipt numbers, payment methods, official receipt numbers, and collectors.
  - Supports statuses such as Paid, Partial, Void, Cancelled.

- Ledgers:
  - Maintain running balances per tenant, linking transactions to billings and payments.

```mermaid
flowchart TD
Start(["Active Contract"]) --> GenerateBilling["Generate Billing<br/>Monthly Rent + Penalty + Discount"]
GenerateBilling --> DueDate["Set Due Date<br/>Based on Contract/System Setting"]
DueDate --> PaymentFlow{"Payment Received?"}
PaymentFlow --> |Partial| PartialPay["Record Partial Payment<br/>Update Balance"]
PaymentFlow --> |Full| FullPay["Record Full Payment<br/>Mark Billing Paid"]
PartialPay --> LedgerEntry["Post Ledger Debit/Credit"]
FullPay --> LedgerEntry
LedgerEntry --> End(["Updated Balance<br/>Audit Trail"])
```

**Diagram sources**
- [models.py:157-187](file://core/models.py#L157-L187)
- [models.py:190-277](file://core/models.py#L190-L277)

**Section sources**
- [models.py:157-187](file://core/models.py#L157-L187)
- [models.py:190-277](file://core/models.py#L190-L277)

### Design System and UI
The frontend uses Tailwind CSS 4 with a custom “Emerald Glass” design system:
- Color palette: municipal emerald primary, Philippine gold accent, warm ivory canvas, deep ink text.
- Visual language: liquid glass surfaces, neumorphic shadows, panels, stat cards, badges, chips, alerts, navigation, tables, and printable documents.
- Print-ready receipts and reports with structured headers, tables, totals, and signature lines.

```mermaid
graph TB
Base["Base Styles<br/>Canvas, Typography, Forms"] --> Components["Components<br/>Glass, Neumorphism, Panels, Buttons"]
Components --> Layout["Layout<br/>Tables, Stat Cards, Navigation"]
Layout --> Documents["Documents<br/>Receipts, Reports, Print Styles"]
```

**Diagram sources**
- [input.css:19-84](file://static/css/input.css#L19-L84)
- [input.css:86-197](file://static/css/input.css#L86-L197)
- [input.css:202-747](file://static/css/input.css#L202-L747)
- [input.css:749-800](file://static/css/input.css#L749-L800)

**Section sources**
- [input.css:19-84](file://static/css/input.css#L19-L84)
- [input.css:86-197](file://static/css/input.css#L86-L197)
- [input.css:202-747](file://static/css/input.css#L202-L747)
- [input.css:749-800](file://static/css/input.css#L749-L800)

## Dependency Analysis
High-level dependencies:
- Views depend on models for data access and on permissions for authorization.
- Dashboard logic aggregates stalls, tenants, contracts, billings, and payments.
- Settings configure database engines, static files, middleware, and security.
- Templates consume context variables provided by views and use Tailwind classes defined in the CSS input file.

```mermaid
graph LR
Views["core/views/*"] --> Models["core/models.py"]
Views --> Permissions["core/permissions.py"]
Views --> Settings["market_rental/settings.py"]
Templates["templates/*"] --> Views
Templates --> CSS["static/css/input.css"]
Models --> Database["SQLite / MySQL / PostgreSQL"]
```

**Diagram sources**
- [dashboard.py:1-10](file://core/views/dashboard.py#L1-L10)
- [settings.py:28-69](file://market_rental/settings.py#L28-L69)
- [input.css:1-10](file://static/css/input.css#L1-L10)

**Section sources**
- [dashboard.py:1-10](file://core/views/dashboard.py#L1-L10)
- [settings.py:28-69](file://market_rental/settings.py#L28-L69)
- [input.css:1-10](file://static/css/input.css#L1-L10)

## Performance Considerations
- Use efficient queries with `select_related` and aggregation where possible, as seen in dashboard calculations.
- Avoid heavy computations on every request; apply overdue penalties best-effort and consider background tasks for large datasets.
- Leverage database indexes on frequently filtered fields such as billing month/year, payment date, and status.
- Compress and cache static assets in production using WhiteNoise and manifest storage.
- Keep tenant-scoped queries narrow to minimize overhead for tenant portal users.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Database connection errors:
  - Verify `DATABASE_URL` for hosted databases or `.env` variables for local MySQL/MariaDB.
  - Ensure the database exists when using MySQL locally; the settings attempt to create it if missing.

- Static files not loading:
  - Run `collectstatic` in production to generate hashed filenames.
  - Confirm `STATIC_URL` and `STATIC_ROOT` paths and WhiteNoise middleware.

- Permission denied errors:
  - Check user role and decorator usage in views.
  - Ensure tenant isolation helpers are applied where tenant-only data is accessed.

- Overdue penalties not applying:
  - Review `maybe_apply_overdue_penalties` invocation and exception handling in dashboard views.
  - Validate penalty settings and due dates in contracts and system settings.

**Section sources**
- [settings.py:73-152](file://market_rental/settings.py#L73-L152)
- [settings.py:166-199](file://market_rental/settings.py#L166-L199)
- [dashboard.py:55-60](file://core/views/dashboard.py#L55-L60)
- [dashboard.py:96-101](file://core/views/dashboard.py#L96-L101)

## Conclusion
The Market Rental System provides a comprehensive, role-aware platform for municipal public market administration. By digitizing stall assignments, tenant records, billing, payments, penalties, notices, reports, and audit trails, it improves transparency, streamlines collections, and strengthens accountability. The Django backend, Tailwind CSS styling, HTMX interactivity, and flexible database options make it suitable for both development and production environments. With clear business rules, robust permissions, and a consistent design system, the system serves administrators, collectors, supervisors, treasurers, and tenants effectively.

[No sources needed since this section summarizes without analyzing specific files]