Create a complete web-based **Public Market Rental and Collection Management System** for a municipal public market.

The system should help the Market Administrator manage stall rentals, tenant records, payment collections, penalties, reports, and rental monitoring in one centralized platform.

Use the following technology stack:

* Backend: Django
* Frontend: Django Templates
* Styling: Tailwind CSS 4
* Interactivity: HTMX and Alpine.js
* Database: SQLite for development, PostgreSQL/MySQL ready for production
* No CDN: All CSS and JavaScript libraries must work offline
* Mobile responsive design
* Clean admin dashboard
* Role-based access control

System Title:
**Public Market Rental and Collection Management System**

Main Objective:
To develop a digital system that manages public market stall rentals, tenant information, monthly rental collections, payment history, penalties, and reports for better transparency, faster collection monitoring, and improved public market administration.

User Roles:

1. Administrator

* Full system access
* Manage users and roles
* Manage market sections
* Manage stalls
* Manage tenants
* Manage rental rates
* Manage payments
* Generate reports
* View dashboard analytics

2. Market Collector

* View assigned tenants and stalls
* Record rental payments
* Issue official receipt details
* View unpaid and overdue accounts
* Generate daily collection summary

3. Market Supervisor / Treasurer

* View collection reports
* Monitor unpaid rentals
* Verify payment records
* View tenant balances
* Export reports

4. Tenant / Stallholder

* View stall rental information
* View payment history
* View balance and due dates
* View notices or reminders

Core Modules:

1. Dashboard Module
   Create a dashboard with summary cards and charts.

Dashboard should display:

* Total number of stalls
* Occupied stalls
* Vacant stalls
* Total tenants
* Total monthly collectibles
* Total collected amount
* Total unpaid rentals
* Overdue accounts
* Collection percentage
* Recent payments
* Tenants with unpaid balances

2. Tenant Management Module
   Create a complete tenant profile system.

Tenant information should include:

* Tenant ID
* Full name
* Address
* Contact number
* Email address optional
* Valid ID information
* Business name
* Type of business
* Emergency contact
* Status: Active, Inactive, Suspended, Terminated
* Date registered
* Uploaded documents optional

Features:

* Add tenant
* Edit tenant
* View tenant profile
* Search tenant
* Filter by status
* View assigned stall
* View payment history
* View outstanding balance

3. Stall Management Module
   Create a module for managing public market stalls.

Stall information should include:

* Stall number
* Market section
* Stall type
* Stall size
* Monthly rental rate
* Occupancy status: Vacant, Occupied, Reserved, Under Maintenance
* Assigned tenant
* Remarks

Market sections may include:

* Dry goods section
* Fish section
* Meat section
* Vegetable section
* Fruit section
* Eatery / carenderia section
* Grocery section
* Rice and grains section
* Other section

Features:

* Add stall
* Edit stall
* Assign tenant to stall
* Transfer tenant to another stall
* Mark stall as vacant
* Mark stall under maintenance
* View stall rental history
* Filter stalls by section and status

Important rule:
A stall can only be assigned to one active tenant at a time.

4. Rental Contract / Assignment Module
   Create a module for managing tenant-stall rental assignments.

Rental assignment details:

* Tenant
* Stall
* Start date
* End date optional
* Monthly rental amount
* Payment due day
* Security deposit optional
* Contract status: Active, Expired, Terminated, Pending
* Remarks

Features:

* Create rental assignment
* Renew rental contract
* Terminate rental contract
* View rental history
* Prevent duplicate active stall assignment
* Automatically calculate monthly collectibles based on active contracts

5. Collection and Payment Module
   Create a module for recording rental payments.

Payment details:

* Payment reference number
* Tenant
* Stall number
* Billing month
* Billing year
* Rental amount
* Penalty amount
* Discount optional
* Total amount due
* Amount paid
* Payment date
* Payment method: Cash, GCash, Bank Transfer, Check
* Official receipt number
* Collected by
* Payment status: Paid, Partial, Unpaid, Overdue
* Remarks

Features:

* Record payment
* Accept partial payment
* Automatically update balance
* Generate payment receipt
* Print receipt
* Search payment records
* Filter by date, tenant, stall, collector, and payment status
* Prevent duplicate full payment for the same tenant, stall, and billing month

6. Billing Module
   Create automatic monthly billing for active tenants.

Features:

* Generate monthly rental bill
* Generate bill per tenant
* Generate bills by market section
* Generate bills for all active tenants
* Automatically compute rental amount
* Automatically compute penalties for overdue payments
* Track unpaid bills
* Track partial payments
* Mark bills as paid after full payment

Billing information:

* Tenant
* Stall
* Billing month
* Due date
* Rental amount
* Penalty
* Total due
* Amount paid
* Remaining balance
* Status

7. Penalty and Due Date Module
   Create penalty settings for late payments.

Features:

* Configure due date per rental contract
* Configure penalty type:

  * Fixed amount
  * Percentage-based penalty
* Configure grace period
* Automatically mark account as overdue
* Automatically compute penalty after due date
* Allow admin to waive penalty with remarks

8. Collection Report Module
   Create reports for monitoring collections.

Reports should include:

* Daily collection report
* Weekly collection report
* Monthly collection report
* Annual collection report
* Collection by market section
* Collection by collector
* Paid tenants report
* Unpaid tenants report
* Overdue accounts report
* Tenant ledger report
* Stall occupancy report
* Vacant stall report

Report features:

* Date range filter
* Export to PDF
* Export to Excel
* Print report
* Summary totals
* Prepared by and verified by section

9. Tenant Ledger Module
   Create a ledger for each tenant.

Ledger should display:

* Billing month
* Rental amount
* Penalty
* Amount paid
* Balance
* Payment date
* Official receipt number
* Payment status
* Running balance

Features:

* View tenant ledger
* Print tenant ledger
* Export ledger
* Show complete payment history

10. Notice and Reminder Module
    Create a simple notice system.

Features:

* Generate notice of unpaid rental
* Generate overdue reminder
* Generate payment reminder
* Print notice
* View tenant notices
* Mark notice as served
* Add remarks

Notice templates:

* Payment reminder notice
* Notice of overdue rental
* Final demand notice
* Stall vacancy notice

11. User and Role Management Module
    Create system users with role-based permissions.

Features:

* Add user
* Edit user
* Deactivate user
* Assign role
* Change password
* Track user activity logs

Roles:

* Administrator
* Market Collector
* Market Supervisor
* Treasurer
* Tenant

12. Audit Trail Module
    Create activity logs for accountability.

Track actions such as:

* Tenant created
* Tenant updated
* Stall assigned
* Payment recorded
* Payment edited
* Bill generated
* Penalty waived
* Report exported
* User login/logout

Audit log fields:

* User
* Action
* Module
* Date and time
* IP address optional
* Description

13. Settings Module
    Create a settings page for system configuration.

Settings should include:

* Municipality name
* Public market name
* Office name
* Receipt prefix
* Default monthly due day
* Penalty settings
* Market sections
* Stall types
* Payment methods
* System logo
* Theme color

Recommended Database Models:

* User
* Role / Profile
* Tenant
* Stall
* MarketSection
* StallType
* RentalContract
* Billing
* Payment
* PenaltySetting
* TenantLedger
* Notice
* AuditLog
* SystemSetting

UI Design Requirements:

* Modern municipal dashboard design
* Mobile-first responsive layout
* Sidebar navigation
* Top navigation bar
* Dashboard cards
* Tables with search and filters
* Modal forms using HTMX
* Toast notifications
* Confirmation dialogs
* Status badges
* Clean printable receipt layout
* Clean printable report layout
* Dark mode optional

Important Business Rules:

1. One stall can only have one active tenant.
2. One tenant may rent multiple stalls if allowed by the administrator.
3. Monthly billing should be generated only for active rental contracts.
4. Full payment should mark the bill as Paid.
5. Partial payment should update the remaining balance.
6. Unpaid bills after the due date should be marked as Overdue.
7. Penalties should be automatically computed based on settings.
8. Payment records should not be deleted permanently. Use void/cancel status instead.
9. All payment edits must be logged in the audit trail.
10. Reports must be printable and exportable.

Suggested Pages:

* Login page
* Dashboard
* Tenant list
* Tenant profile
* Add/Edit tenant
* Stall list
* Stall details
* Market sections
* Rental contracts
* Billing list
* Generate billing page
* Payment collection page
* Payment history
* Tenant ledger
* Notices
* Reports
* User management
* Settings
* Audit logs

Receipt Layout Requirements:

Create a printable payment receipt containing:

* Municipality / public market name
* Receipt number
* Tenant name
* Stall number
* Billing month
* Rental amount
* Penalty
* Discount
* Total amount paid
* Remaining balance
* Payment date
* Collector name
* Signature line

Reports Layout Requirements:

Reports should include:

* Header with municipality and public market name
* Report title
* Date range
* Table of records
* Total amount collected
* Total unpaid balance
* Prepared by
* Verified by
* Signature lines

Development Requirements:

* Use Django class-based or function-based views properly
* Use Django forms or ModelForms
* Use Django authentication
* Use permissions per role
* Use HTMX for dynamic table filtering, modals, and form submissions
* Use Alpine.js for sidebar toggle, dropdowns, and UI interactions
* Use Tailwind CSS 4 local build
* No external CDN
* Use clean folder structure
* Add sample seed data
* Add validation and error handling
* Add pagination for large tables
* Add search and filter functions
* Add printable pages
* Make the system production-ready

Expected Output:

Generate a complete Django web application with:

* Database models
* Admin panel registration
* Views
* URLs
* Forms
* Templates
* Static files
* Tailwind CSS setup
* HTMX and Alpine.js local setup
* Authentication and role-based dashboard
* CRUD modules
* Billing and payment computation
* Report generation
* Printable receipt
* Sample data
* Clear setup instructions

Make the design professional, clean, responsive, and suitable for a municipal public market office.
