# Getting Started Guide

<cite>
**Referenced Files in This Document**
- [README.MD](file://README.MD)
- [requirements.txt](file://requirements.txt)
- [package.json](file://package.json)
- [settings.py](file://market_rental/settings.py)
- [urls.py](file://market_rental/urls.py)
- [core_urls.py](file://core/urls.py)
- [auth_views.py](file://core/views/auth.py)
- [seed_data.py](file://core/management/commands/seed_data.py)
- [models.py](file://core/models.py)
- [credentials.md](file://credentials.md)
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
10. [Appendices](#appendices)

## Introduction
This guide walks you through installing, configuring, and running the Market Rental System for the first time. The system is a Django web application that manages public market stall rentals, tenant records, billing, payments, penalties, notices, reports, and audit logs. It supports SQLite for local development and can connect to MySQL or PostgreSQL in production.

The project includes:
- A Django backend with role-based access control.
- Django templates styled with Tailwind CSS 4.
- HTMX and Alpine.js for interactive pages.
- Sample data seeding for quick exploration.
- Database configuration via environment variables.

**Section sources**
- [README.MD:1-16](file://README.MD#L1-L16)

## Project Structure
At a high level, the repository is organized as follows:
- `market_rental/`: Django project settings, URLs, and WSGI/ASGI entry points.
- `core/`: Main application models, views, forms, management commands, migrations, and templates.
- `accounts/`: Additional user-related app.
- `templates/`: HTML templates for all modules.
- `static/`: Static assets including Tailwind input CSS.
- `requirements.txt`: Python dependencies.
- `package.json`: Node scripts for building Tailwind CSS.

```mermaid
graph TB
Root["Repository Root"]
DjangoProject["market_rental/"]
CoreApp["core/"]
AccountsApp["accounts/"]
Templates["templates/"]
StaticAssets["static/"]
PyDeps["requirements.txt"]
NpmConfig["package.json"]
Root --> DjangoProject
Root --> CoreApp
Root --> AccountsApp
Root --> Templates
Root --> StaticAssets
Root --> PyDeps
Root --> NpmConfig
```

**Diagram sources**
- [settings.py:28-38](file://market_rental/settings.py#L28-L38)
- [urls.py:7-12](file://market_rental/urls.py#L7-L12)
- [core_urls.py:56-198](file://core/urls.py#L56-L198)

**Section sources**
- [README.MD:478-515](file://README.MD#L478-L515)
- [settings.py:28-38](file://market_rental/settings.py#L28-L38)
- [urls.py:7-12](file://market_rental/urls.py#L7-L12)
- [core_urls.py:56-198](file://core/urls.py#L56-L198)

## Core Components
Key components relevant to getting started:
- Django project configuration and database setup.
- Authentication flow and login/logout endpoints.
- Seed command to populate sample data.
- Role model and permissions.
- URL routing for core features.

What you will use during setup:
- Python virtual environment and pip.
- npm and Tailwind CLI for static assets.
- Django management commands (`migrate`, `createsuperuser`, `seed_data`).
- Environment variables for secrets and database connection.

**Section sources**
- [settings.py:73-152](file://market_rental/settings.py#L73-L152)
- [auth_views.py:9-35](file://core/views/auth.py#L9-L35)
- [seed_data.py:193-229](file://core/management/commands/seed_data.py#L193-L229)
- [models.py:7-24](file://core/models.py#L7-L24)
- [core_urls.py:56-63](file://core/urls.py#L56-L63)

## Architecture Overview
The system follows a standard Django architecture:
- HTTP requests enter through Django’s URL router.
- Views render templates and interact with models.
- Data is persisted in a relational database (SQLite locally; MySQL/PostgreSQL in production).
- Static files are served by WhiteNoise in production and directly in development.

```mermaid
graph TB
Browser["Web Browser"]
DjangoURLs["Django URL Router<br/>market_rental/urls.py"]
CoreURLs["Core App URLs<br/>core/urls.py"]
AuthView["Auth View<br/>login_view()"]
DashboardView["Dashboard View"]
Models["Models<br/>Tenant, Stall, Billing, Payment, etc."]
DB["Database<br/>SQLite / MySQL / PostgreSQL"]
StaticFiles["Static Files<br/>WhiteNoise / Dev Server"]
Browser --> DjangoURLs
DjangoURLs --> CoreURLs
CoreURLs --> AuthView
CoreURLs --> DashboardView
AuthView --> Models
DashboardView --> Models
Models --> DB
Browser --> StaticFiles
```

**Diagram sources**
- [urls.py:7-12](file://market_rental/urls.py#L7-L12)
- [core_urls.py:56-63](file://core/urls.py#L56-L63)
- [auth_views.py:9-35](file://core/views/auth.py#L9-L35)
- [settings.py:166-180](file://market_rental/settings.py#L166-L180)

## Detailed Component Analysis

### Installation Steps

#### Step 1: Prepare Your Python Environment
- Install Python 3.10+ on your machine.
- Create a virtual environment in the repository root:
  - Windows: `python -m venv venv`
  - macOS/Linux: `python3 -m venv venv`
- Activate the virtual environment:
  - Windows: `venv\Scripts\activate`
  - macOS/Linux: `source venv/bin/activate`

Verify activation by checking your shell prompt or running `which python`.

**Section sources**
- [README.MD:478-494](file://README.MD#L478-L494)

#### Step 2: Install Python Dependencies
Install requirements using pip:
```bash
pip install -r requirements.txt
```

This installs Django, database drivers, static file serving, and report generation libraries.

**Section sources**
- [requirements.txt:1-10](file://requirements.txt#L1-L10)

#### Step 3: Install Frontend Dependencies and Build Styles
Install Node.js if not installed, then install npm packages and build Tailwind CSS:
```bash
npm install
npm run build:css
```

For development, you may also watch changes:
```bash
npm run watch:css
```

**Section sources**
- [package.json:5-12](file://package.json#L5-L12)

#### Step 4: Configure the Database

##### Option A: SQLite (Recommended for Development)
No extra configuration is required. Django uses SQLite by default when no `DATABASE_URL` is set and `DB_ENGINE` is not explicitly configured to another engine.

The default SQLite database file path is derived from the project base directory.

**Section sources**
- [settings.py:145-152](file://market_rental/settings.py#L145-L152)

##### Option B: MySQL/MariaDB (Local Development)
Set these environment variables before running migrations:
- `DB_ENGINE=mysql`
- `MYSQL_DB=market_rental`
- `MYSQL_HOST=127.0.0.1`
- `MYSQL_PORT=3306`
- `MYSQL_USER=root`
- `MYSQL_PASSWORD=`

On first run, the application attempts to create the database if it does not exist. If this fails due to permissions, create the database manually in MySQL and ensure the user has privileges.

**Section sources**
- [settings.py:121-144](file://market_rental/settings.py#L121-L144)

##### Option C: Production Database (MySQL or PostgreSQL)
Provide a single `DATABASE_URL` environment variable. Examples:
- PostgreSQL: `postgresql://user:password@host:port/dbname`
- MySQL: `mysql+pymysql://user:password@host:port/dbname`

When `DATABASE_URL` is present, it takes precedence over other database options. SSL is enforced in non-debug mode.

**Section sources**
- [settings.py:73-120](file://market_rental/settings.py#L73-L120)

#### Step 5: Set Required Environment Variables
Create a `.env` file at the repository root for local secrets and optional overrides. At minimum:
- `DJANGO_SECRET_KEY`: A strong secret key for production.
- `DJANGO_DEBUG=false` in production.
- `DJANGO_ALLOWED_HOSTS`: Comma-separated allowed hosts in production.
- `DATABASE_URL`: For production databases.
- Optional: `DB_ENGINE`, `MYSQL_*` variables for local MySQL.

The settings module loads `.env` automatically and falls back to sensible defaults in development.

**Section sources**
- [settings.py:9-26](file://market_rental/settings.py#L9-L26)

#### Step 6: Run Migrations
Apply database schema changes:
```bash
python manage.py migrate
```

If you switched to MySQL or PostgreSQL, confirm connectivity before running this command.

**Section sources**
- [settings.py:109-152](file://market_rental/settings.py#L109-L152)

#### Step 7: Create a Superuser
Create an admin account:
```bash
python manage.py createsuperuser
```

You can access the Django admin at `/admin/`.

**Section sources**
- [urls.py:8-9](file://market_rental/urls.py#L8-L9)

#### Step 8: Seed Sample Data
Populate the database with sample tenants, stalls, contracts, billings, payments, notices, and staff users:
```bash
python manage.py seed_data
```

Optional reset mode clears existing data before seeding:
```bash
python manage.py seed_data --reset
```

After seeding, the command prints staff usernames and passwords, plus tenant credentials.

**Section sources**
- [seed_data.py:193-229](file://core/management/commands/seed_data.py#L193-L229)

#### Step 9: Collect Static Files (Production)
In production, collect and compress static files:
```bash
python manage.py collectstatic
```

WhiteNoise serves compressed static files when `DEBUG=False`.

**Section sources**
- [settings.py:166-180](file://market_rental/settings.py#L166-L180)

#### Step 10: Start the Development Server
Run the Django development server:
```bash
python manage.py runserver
```

Open your browser and navigate to the landing page or login page.

**Section sources**
- [core_urls.py:56-58](file://core/urls.py#L56-L58)

### First-Time User Setup

#### Default Credentials
After running the seed command, you can log in with the following accounts:

Staff accounts:
- Admin: username `admin`, password `admin123`
- Collector: username `collector1`, password `collector123`
- Cashier: username `cashier1`, password `cashier123`
- Supervisor: username `supervisor1`, password `supervisor123`
- Treasurer: username `treasurer1`, password `treasurer123`

Tenant accounts:
- All seeded tenants use the same password.
- Tenant usernames correspond to their tenant IDs (for example, `TEN-001`).

Login URL:
- `/accounts/login/` is mapped to the named route `login`.

Important notes:
- Some documentation references older demo values; always verify current accounts after seeding.
- Change default passwords before using the system in production.

**Section sources**
- [seed_data.py:36-45](file://core/management/commands/seed_data.py#L36-L45)
- [credentials.md:6-38](file://credentials.md#L6-L38)
- [urls.py:10-11](file://market_rental/urls.py#L10-L11)

#### Basic Navigation Guidance
After logging in:
- Landing page: `/`
- Dashboard: `/dashboard/`
- Tenants: `/tenants/`
- Stalls: `/stalls/`
- Contracts: `/contracts/`
- Billing: `/billing/`
- Payments: `/payments/`
- Reports: `/reports/`
- Ledger: `/ledger/`
- Notices: `/notices/`
- Settings: `/settings/`
- Audit Logs: `/audit-logs/`
- Users: `/users/`
- Tenant Portal: `/portal/`

These routes are defined in the core application URLs.

**Section sources**
- [core_urls.py:56-198](file://core/urls.py#L56-L198)

### Verification Steps
Use these checks to confirm proper setup:
1. Visit the landing page and confirm it renders without errors.
2. Log in with a seeded staff account.
3. Open the dashboard and verify summary cards load.
4. Navigate to Tenants and confirm sample tenants appear.
5. Navigate to Billing and confirm generated bills exist.
6. Check Payments and verify recorded payments.
7. Open Reports and generate a simple report.
8. Confirm static assets load correctly (CSS should be applied).
9. Verify the database contains expected tables and rows.

If any step fails, consult the troubleshooting section below.

**Section sources**
- [core_urls.py:56-198](file://core/urls.py#L56-L198)
- [seed_data.py:221-229](file://core/management/commands/seed_data.py#L221-L229)

## Dependency Analysis
The application depends on:
- Django for web framework, ORM, authentication, and admin.
- Database drivers for MySQL and PostgreSQL.
- WhiteNoise for static file serving in production.
- Report generation libraries for PDF and Excel exports.
- Tailwind CSS CLI for building styles.

```mermaid
graph TB
Django["Django"]
DBDrivers["Database Drivers<br/>psycopg, PyMySQL"]
Whitenoise["WhiteNoise"]
Reports["Report Libraries<br/>openpyxl, weasyprint, reportlab, xhtml2pdf"]
Tailwind["Tailwind CLI"]
Django --> DBDrivers
Django --> Whitenoise
Django --> Reports
Tailwind --> StaticAssets["Static CSS Output"]
```

**Diagram sources**
- [requirements.txt:1-10](file://requirements.txt#L1-L10)
- [package.json:9-12](file://package.json#L9-L12)

**Section sources**
- [requirements.txt:1-10](file://requirements.txt#L1-L10)
- [package.json:5-12](file://package.json#L5-L12)

## Performance Considerations
- Use production database drivers and connection pooling where supported.
- Enable `collectstatic` and WhiteNoise compression in production.
- Keep `DEBUG=False` in production to avoid unnecessary overhead.
- Ensure database indexes exist for frequently queried fields such as billing month/year and payment dates.
- Avoid large unpaginated queries in reports; use pagination and filters.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide

### Common Installation Issues

#### Missing Python Dependencies
Symptoms:
- Import errors for Django or database drivers.
- Commands fail with missing module errors.

Resolution:
- Reinstall dependencies: `pip install -r requirements.txt`
- Ensure the virtual environment is activated.

**Section sources**
- [requirements.txt:1-10](file://requirements.txt#L1-L10)

#### Tailwind CSS Not Loading
Symptoms:
- Page appears unstyled or partially styled.
- Console shows 404 for CSS files.

Resolution:
- Install npm packages: `npm install`
- Build styles: `npm run build:css`
- In development, consider watching changes: `npm run watch:css`
- Verify `static/css/output.css` exists.

**Section sources**
- [package.json:5-12](file://package.json#L5-L12)

#### Database Connection Errors
Symptoms:
- Migration or runtime errors related to database connectivity.
- MySQL database creation failures.

Resolution:
- For SQLite: ensure write permissions to the database file location.
- For MySQL: verify `DB_ENGINE=mysql` and correct `MYSQL_*` variables.
- For production: verify `DATABASE_URL` format and network access.
- If automatic database creation fails, create the database manually and grant privileges.

**Section sources**
- [settings.py:73-152](file://market_rental/settings.py#L73-L152)

#### Login Fails with Seeded Accounts
Symptoms:
- Invalid username or password messages.
- Collector account appears inactive.

Resolution:
- Confirm you ran `python manage.py seed_data`.
- Verify current credentials printed by the seed command.
- If necessary, activate the collector account or recreate users via the admin panel or shell.

**Section sources**
- [auth_views.py:12-24](file://core/views/auth.py#L12-L24)
- [credentials.md:31-38](file://credentials.md#L31-L38)
- [seed_data.py:221-229](file://core/management/commands/seed_data.py#L221-L229)

#### Static Files Not Served in Production
Symptoms:
- 404 errors for CSS/JS in production.
- Unstyled pages behind a proxy.

Resolution:
- Run `python manage.py collectstatic`.
- Ensure WhiteNoise is enabled and `DEBUG=False`.
- Verify `ALLOWED_HOSTS` and CSRF trusted origins are configured.

**Section sources**
- [settings.py:166-190](file://market_rental/settings.py#L166-L190)

### Verification Checklist
- [ ] Virtual environment created and activated.
- [ ] Python dependencies installed.
- [ ] npm packages installed and CSS built.
- [ ] Database migrations applied.
- [ ] Superuser created.
- [ ] Sample data seeded.
- [ ] Development server starts successfully.
- [ ] Login works with seeded credentials.
- [ ] Dashboard and core pages render correctly.
- [ ] Static assets load without 404 errors.

**Section sources**
- [core_urls.py:56-198](file://core/urls.py#L56-L198)
- [seed_data.py:221-229](file://core/management/commands/seed_data.py#L221-L229)

## Conclusion
You now have a working Market Rental System installation. Use the seeded staff accounts to explore the dashboard, tenants, stalls, contracts, billing, payments, reports, and settings. Before deploying to production, configure secure secrets, a production database, proper hostnames, and updated user credentials.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Appendix A: Key URLs Reference
- Landing: `/`
- Login: `/login/`
- Logout: `/logout/`
- Admin: `/admin/`
- Dashboard: `/dashboard/`
- Tenant Portal: `/portal/`

**Section sources**
- [urls.py:7-12](file://market_rental/urls.py#L7-L12)
- [core_urls.py:56-63](file://core/urls.py#L56-L63)

### Appendix B: Role Model Overview
The system defines roles for administrators, collectors, cashiers, supervisors, treasurers, and tenants. Roles are stored alongside Django’s built-in User model.

```mermaid
classDiagram
class UserProfile {
+string role
+string phone
+string address
+bool must_change_password
}
class User {
+string username
+string email
+bool is_staff
+bool is_superuser
+bool is_active
}
UserProfile --> User : "OneToOne"
```

**Diagram sources**
- [models.py:7-24](file://core/models.py#L7-L24)

**Section sources**
- [models.py:7-24](file://core/models.py#L7-L24)