import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local development variables (DB_ENGINE, MySQL credentials, secrets)
# from a .env file. Real environment variables always take precedence.
load_dotenv(BASE_DIR / ".env")

# Local development remains zero-config, while every production secret and
# connection setting is supplied by the hosting environment.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-key-not-for-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes", "on"}

configured_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [host.strip() for host in configured_hosts.split(",") if host.strip()]
if not DEBUG:
    # Vercel assigns a production and preview hostname; accept both while
    # retaining the option to add a custom domain through DJANGO_ALLOWED_HOSTS.
    ALLOWED_HOSTS.extend([".vercel.app", "localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "market_rental.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.system_settings",
                "core.context_processors.static_version",
            ],
        },
    },
]

WSGI_APPLICATION = "market_rental.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL")
# DB_ENGINE lets you flip between the zero-config SQLite file and XAMPP's
# MySQL/MariaDB server without touching code (set it in .env).
DB_ENGINE = os.environ.get("DB_ENGINE", "sqlite").lower()


def _ensure_mysql_database(db_name, host, port, user, password):
    """Create the local MySQL database if it does not already exist.

    Django's migrate command cannot create the schema itself, so connect
    to the server without selecting a database and issue an idempotent
    CREATE. Failures are swallowed here; the real connection error will
    surface when Django next tries to reach the server.
    """
    try:
        import pymysql

        connection = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            autocommit=True,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        finally:
            connection.close()
    except Exception:  # pragma: no cover - best-effort local bootstrap
        pass


if DATABASE_URL:
    # Production / hosted databases are still driven entirely by the
    # environment (e.g. a managed MySQL service). This takes precedence
    # over DB_ENGINE.
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=not DEBUG,
        )
    }
elif DB_ENGINE == "mysql":
    # Local development against the MySQL/MariaDB server bundled with XAMPP.
    # The defaults match a stock XAMPP install (root user, empty password);
    # override any value through the .env file.
    MYSQL_DB = os.environ.get("MYSQL_DB", "market_rental")
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")

    _ensure_mysql_database(MYSQL_DB, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD)

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": MYSQL_DB,
            "USER": MYSQL_USER,
            "PASSWORD": MYSQL_PASSWORD,
            "HOST": MYSQL_HOST,
            "PORT": MYSQL_PORT,
            "CONN_MAX_AGE": 600,
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    # Fallback: zero-config SQLite file.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Production: hash static filenames (output.<hash>.css) so browsers fetch a
# brand-new URL whenever file contents change. Requires `collectstatic`
# on deploy. Dev (DEBUG=True) keeps plain filenames and relies on the
# `?v={{ STATIC_VERSION }}` querystring added in templates instead.
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"] + [
        origin.strip()
        for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
        if origin.strip()
    ]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
