---
kind: error_handling
name: 'Django-centric error handling: messages, exceptions, and best-effort fallbacks'
category: error_handling
scope:
    - '**'
source_files:
    - core/helpers.py
    - core/views/contracts.py
    - core/views/auth.py
    - core/views/billing.py
    - core/views/payments.py
    - core/views/dashboard.py
    - core/views/ledger.py
    - core/views/lookups.py
    - core/management/commands/reset_market_data.py
    - market_rental/settings.py
---

## Approach

The Market Rental System is a Django application. It does not define custom exception classes or a centralized error-reporting framework. Error handling is distributed across views, helpers, management commands, and templates, relying on:

- **Django's built-in exceptions** (`ValidationError`, `IntegrityError`, `ProtectedError`, `ObjectDoesNotExist`/`.DoesNotExist`) for domain and data-layer errors.
- **Python built-ins** (`ValueError`, `OSError`, `EOFError`, `ImportError`, `Exception`) for control flow and environment failures.
- **Django Messages framework** (`django.contrib.messages`) to surface user-facing feedback after an error path is taken.
- **Best-effort try/except blocks** that swallow or downgrade errors so the page still renders (PDF generation, billing accrual, bulk assignment).
- **No global error middleware** — `market_rental/settings.py` uses only standard Django middleware (`SecurityMiddleware`, `CommonMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, `MessageMiddleware`, `XFrameOptionsMiddleware`). There is no custom exception handler or `handler500` override.

## Key files and patterns

### Views (`core/views/*.py`)

Views catch specific exceptions where meaningful and fall back to a generic `except Exception`:

- `contracts.py`: raises `ValueError` when a stall is no longer vacant during bulk assignment; catches it to render a `messages.error`; also wraps per-stall billing creation in its own `try/except Exception: pass` so one bad contract doesn't abort the whole batch.
- `billing.py`, `payments.py`, `dashboard.py`: wrap risky operations in `except Exception:` and silently continue or return defaults.
- `ledger.py`, `dashboard.py`: catch `Tenant.DoesNotExist` to handle missing tenants gracefully.
- `lookups.py`: catches `ProtectedError` from Django ORM cascade deletes to inform the user that referenced objects prevent deletion.
- `auth.py`: returns `messages.error('Invalid username or password.')` on form validation failure rather than raising.

### Helpers (`core/helpers.py`)

The shared helper module centralizes the most important error-handling logic:

- `generate_strong_password()` retries up to 50 times against `validate_password`, catching `ValidationError` and looping until a valid password is produced.
- `ensure_initial_billing()` wraps its entire loop in `try/except Exception: return None, False` — a best-effort helper that never raises.
- `record_payment()` retries receipt-number generation up to 5 times on `IntegrityError` (collision), then recomputes billing totals authoritatively via `select_for_update` + `recalc_billing_from_payments`.
- `apply_overdue_penalties()` is idempotent: penalties are only accrued while `penalty_amount == 0`, preventing double-charges on repeated runs.
- `maybe_apply_overdue_penalties()` is explicitly documented as "best-effort" and "Never raises" — it catches all exceptions, deletes the cache key to allow retry, and ensures overdue accrual cannot break the request that triggered it.
- `render_to_pdf_response()` implements a three-stage fallback: WeasyPrint → xhtml2pdf → HTML preview with a browser Print button. Each stage catches `(ImportError, OSError, Exception)` and falls through to the next; the final response always returns usable HTML even when both PDF engines fail.

### Management commands (`core/management/commands/reset_market_data.py`)

Uses Django's `CommandError` for command-level failures:
- Raises `CommandError('Non-interactive shell — pass --yes to confirm.')` when run without confirmation.
- Raises `CommandError('Aborted — confirmation text did not match.')` when the user types the wrong confirmation string.
- Catches `EOFError` to distinguish interactive cancellation from non-interactive execution.

### Settings and configuration (`market_rental/settings.py`)

- `_ensure_mysql_database()` swallows all connection errors (`except Exception: pass`) because it is a best-effort local bootstrap step; the real failure surfaces later when Django connects.
- No custom `handler404` / `handler500` is configured; Django's default debug/error pages apply when `DEBUG=True`.

### Templates and templatetags

- `core/templatetags/market_tags.py` wraps template-side lookups in `try/except` blocks so a missing setting or model field does not crash the rendered page.
- `core/context_processors.py` catches `OSError` around file-system access.

## Conventions observed

1. **User-facing errors go through `messages.error(request, ...)`** inside view handlers rather than being raised as HTTP exceptions. This is the pattern used by `auth.login_view`, `contracts.bulk_assign`, and the various delete views.
2. **Domain/data integrity violations raise Python exceptions** (`ValueError`, `IntegrityError`, `ProtectedError`, `Tenant.DoesNotExist`) which views then translate into user messages. There are no custom sentinel error types defined in this repo.
3. **Helper functions are defensive**: they prefer returning `(value, created)` tuples or `None` over raising, especially for background/best-effort work (`ensure_initial_billing`, `maybe_apply_overdue_penalties`).
4. **Concurrency-sensitive writes use `transaction.atomic()` plus `select_for_update()`**, and retry on `IntegrityError` for unique-key collisions (receipt numbers, stall assignments).
5. **External dependencies are wrapped in layered fallbacks**: PDF rendering tries WeasyPrint, then xhtml2pdf, then falls back to HTML with instructions. Missing libraries produce a warning banner rather than a 500 error.
6. **Idempotency is the primary defense against duplicate side effects**: penalty accrual checks `penalty_amount == 0`; billing creation uses `get_or_create` semantics; receipt numbering derives from the highest existing suffix.
7. **There is no repository-wide error taxonomy** — no `errors/` package, no base exception class, no structured error codes. Errors are handled ad hoc at the call site.