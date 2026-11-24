"""Idempotent management command to seed default deploy users: admin, collector, and tenant.

Existing user credentials and profiles are NEVER overwritten or reset on re-run
unless the explicit ``--reset-passwords`` flag is supplied.
"""

import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import SystemSetting, Tenant, UserProfile


class Command(BaseCommand):
    help = "Seed default admin, collector, and tenant user accounts without resetting existing credentials."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            default=False,
            help="Explicitly reset passwords of existing seeded accounts (disabled by default).",
        )

    def handle(self, *args, **options):
        reset_passwords = options.get("reset_passwords", False)
        self._ensure_system_settings()

        admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")
        collector_password = os.environ.get("SEED_COLLECTOR_PASSWORD", "collector123")
        tenant_password = os.environ.get("SEED_TENANT_PASSWORD", "tenant123")

        self._ensure_user(
            username="admin",
            password=admin_password,
            email="admin@dumingag.example.com",
            first_name="Market",
            last_name="Administrator",
            role="admin",
            is_staff=True,
            is_superuser=True,
            reset_passwords=reset_passwords,
        )

        self._ensure_user(
            username="collector",
            password=collector_password,
            email="collector@dumingag.example.com",
            first_name="Market",
            last_name="Collector",
            role="collector",
            phone="09171234567",
            reset_passwords=reset_passwords,
        )

        tenant_user = self._ensure_user(
            username="tenant",
            password=tenant_password,
            email="tenant@dumingag.example.com",
            first_name="Sample",
            last_name="Tenant",
            role="tenant",
            phone="09170000001",
            reset_passwords=reset_passwords,
        )
        self._ensure_tenant_record(tenant_user)

        self.stdout.write(
            self.style.SUCCESS("Seeded default users: admin, collector, tenant.")
        )

    def _ensure_system_settings(self):
        if SystemSetting.objects.exists():
            return
        SystemSetting.objects.create(
            municipality_name="Municipality of Dumingag",
            market_name="Dumingag Public Market",
            office_name="Market Administration Office",
            receipt_prefix="DMPM-",
            default_due_day=5,
            penalty_type="percentage",
            penalty_value=Decimal("2.00"),
            grace_period=5,
            theme_color="#006627",
        )

    def _ensure_user(
        self,
        *,
        username,
        password,
        email,
        first_name,
        last_name,
        role,
        phone="",
        is_staff=False,
        is_superuser=False,
        reset_passwords=False,
    ):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "is_active": True,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(f"  Created user: {username} (role={role})")
        else:
            if reset_passwords:
                user.set_password(password)
                user.save(update_fields=["password"])
                self.stdout.write(f"  Reset password for existing user: {username} (role={role})")
            else:
                self.stdout.write(
                    f"  User already exists (credentials preserved): {username} (role={role})"
                )

        # Preserve existing profile attributes; only create if missing.
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "role": role,
                "phone": phone,
                "address": "Dumingag, Zamboanga del Sur",
                "must_change_password": False,
            },
        )
        return user

    def _ensure_tenant_record(self, user):
        if Tenant.objects.filter(user=user).exists():
            return
        tenant_id = "TEN-099"
        if Tenant.objects.filter(tenant_id=tenant_id).exists():
            idx = 99
            while Tenant.objects.filter(tenant_id=f"TEN-{idx:03d}").exists():
                idx += 1
            tenant_id = f"TEN-{idx:03d}"

        Tenant.objects.create(
            tenant_id=tenant_id,
            user=user,
            first_name=user.first_name or "Sample",
            middle_name="",
            last_name=user.last_name or "Tenant",
            full_name=f"{user.first_name} {user.last_name}".strip() or "Sample Tenant",
            street="Poblacion",
            barangay="Poblacion",
            municipality="Dumingag",
            province="Zamboanga del Sur",
            address="Poblacion, Dumingag, Zamboanga del Sur",
            contact_number="09170000001",
            email=user.email,
            valid_id_type="National ID",
            valid_id_number="0000-0000-0099",
            business_name="Sample Market Stall",
            business_type="Dry Goods",
            status="Active",
        )
