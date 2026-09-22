# System Credentials — Public Market Rental and Collection Management System

> Generated: 2026-08-28 | Source: `core/management/commands/seed_data.py:54-63` + live DB verification
> Login URL: `/accounts/login/` (named `login` in `templates/registration/login.html:52`)

## Staff Accounts

| Role | Username | Password | Status | Notes | Source |
|------|----------|----------|--------|-------|--------|
| **Admin** | `admin` | `admin123` | Active | is_staff + is_superuser | `seed_data.py:55` |
| **Collector** | `collector1` | `collector123` | **Activated (was inactive)** | Name: Juan Santos, Phone: 09171234567 | `seed_data.py:57-58`, `seed_data.py:70-72` |
| **Cashier** | `cashier1` | `cashier123` | **Active (newly created)** | Name: Cashier One, Role: cashier — was not seeded by default; created manually via shell | `core/models.py:11` defines role |
| **Supervisor** | `supervisor1` | `supervisor123` | Active | Name: Maria Cruz | `seed_data.py:59` |
| **Treasurer** | `treasurer1` | `treasurer123` | Active | Name: Pedro Reyes | `seed_data.py:61` |

## Tenant Accounts

All seeded tenants use password `tenant123` (`seed_data.py:197`):

| Username (Tenant ID) | Full Name | Business | Status |
|----------------------|-----------|----------|--------|
| `TEN-001` | Juan dela Cruz | Juan Rice Trading | **Inactive** |
| `TEN-002` | Maria Santos | Maria Fresh Fish | Active |
| `TEN-003` | Pedro Reyes | Pedro Meat Shop | Active |
| `TEN-004` | Ana Gonzales | Ana's Fresh Produce | Active |
| `TEN-005` | Jose Rizal II | Jose's Fruit Stand | Active |
| `TEN-006` | Luzviminda Mercado | Luz's Eatery | Active |
| `TEN-007` | Antonio Lopez | Antonio Dry Goods | Active |
| `TEN-008` | Teresa Cruz | Teresa's Store | Active |

## Key Details

- **Collector fix applied:** `collector1` was `is_active=False` (verified via `User.objects.select_related('profile')` query). Updated to `is_active=True` on 2026-08-28.
- **Cashier creation:** No cashier was seeded (`seed_data.py:54-63` only seeds admin/collector/supervisor/treasurer). Created `cashier1 / cashier123` with `UserProfile.role='cashier'` — verified `check_password=True`.
- **Login template note:** `templates/registration/login.html:107` displays `collector / collector123` as demo — this is inaccurate; correct username is `collector1`.
- **Roles defined:** `core/models.py:10-11`, `core/permissions.py:8-9` (`STAFF_ROLES`, `COLLECTOR_ROLES` includes `collector` + `cashier`).
- **System settings:** `SystemSetting` in `seed_data.py:41-50` — LGU Dumingag / Dumingag Public Market, receipt prefix `DMPM-`, due day 5, penalty 2% (percentage).

## How to Manage Users

### Via Admin Panel (as admin)
1. Login as `admin / admin123`
2. Go to Users list (`/users/` — `core/views/users.py:19`)
3. Create / edit / toggle active status

### Via Shell
```bash
# Create cashier (already done)
python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','market_rental.settings'); django.setup(); from django.contrib.auth.models import User; from core.models import UserProfile; u=User.objects.create_user(username='cashier1', password='cashier123'); UserProfile.objects.create(user=u, role='cashier')"

# Activate collector
python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','market_rental.settings'); django.setup(); from django.contrib.auth.models import User; User.objects.filter(username='collector1').update(is_active=True)"

# Reseed all sample data (idempotent)
python manage.py seed_data
```

## Verification Command
```bash
python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','market_rental.settings'); django.setup(); from django.contrib.auth.models import User; [print(f'{u.username} | active={u.is_active} | role={u.profile.role}') for u in User.objects.select_related('profile').order_by('username')]"
```

## Security Warning
Default passwords are for development only. Change via `/users/<id>/edit/` or `user.set_password()` before production.
