"""Idempotent management command to seed default deploy users: admin, collector, and tenant."""

import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import SystemSetting, Tenant, UserProfile


class Command(BaseCommand):
    help = "Seed default admin, collector, and tenant user accounts (idempotent)."

    def handle(self, *args, **options):
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
        )

        self._ensure_user(
            username="collector",
            password=collector_password,
            email="collector@dumingag.example.com",
            first_name="Market",
            last_name="Collector",
            role="collector",
            phone="09171234567",
        )

        tenant_user = self._ensure_user(
            username="tenant",
            password=tenant_password,
            email="tenant@dumingag.example.com",
            first_name="Sample",
            last_name="Tenant",
            role="tenant",
            phone="09170000001",
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
            changed_fields = []
            if not user.is_active:
                user.is_active = True
                changed_fields.append("is_active")
            if is_staff and not user.is_staff:
                user.is_staff = True
                changed_fields.append("is_staff")
            if is_superuser and not user.is_superuser:
                user.is_superuser = True
                changed_fields.append("is_superuser")
            if changed_fields:
                user.save(update_fields=changed_fields)
            self.stdout.write(f"  User already exists: {username} (role={role})")

        UserProfile.objects.update_or_create(
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
        tenant_id = "TEN-001"
        tenant = Tenant.objects.filter(tenant_id=tenant_id).first()
        if tenant is not None and tenant.user is None:
            tenant.user = user
            tenant.save(update_fields=["user"])
            return
        if tenant is not None:
            # Find next unused TEN-XXX id if TEN-001 is already linked elsewhere
            idx = 1
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
            business_name="Sample Market Stall",
            business_type="Dry Goods",
            status="Active",
        )
