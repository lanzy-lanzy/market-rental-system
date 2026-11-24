from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from core.models import SystemSetting, Tenant


class SeedUsersCommandTests(TestCase):
    def test_seed_users_creates_admin_collector_and_tenant_idempotently(self):
        call_command("seed_users")
        call_command("seed_users")

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.check_password("admin123"))
        self.assertEqual(admin.profile.role, "admin")

        collector = User.objects.get(username="collector")
        self.assertTrue(collector.is_active)
        self.assertTrue(collector.check_password("collector123"))
        self.assertEqual(collector.profile.role, "collector")

        tenant_user = User.objects.get(username="tenant")
        self.assertTrue(tenant_user.is_active)
        self.assertTrue(tenant_user.check_password("tenant123"))
        self.assertEqual(tenant_user.profile.role, "tenant")
        self.assertTrue(Tenant.objects.filter(user=tenant_user).exists())
        self.assertTrue(SystemSetting.objects.exists())

    def test_seed_users_does_not_reset_existing_admin_and_collector_credentials(self):
        call_command("seed_users")

        admin = User.objects.get(username="admin")
        admin.set_password("MyCustomAdmin!2026")
        admin.save(update_fields=["password"])
        admin.profile.phone = "09998887777"
        admin.profile.save(update_fields=["phone"])

        collector = User.objects.get(username="collector")
        collector.set_password("MyCustomCollector!2026")
        collector.save(update_fields=["password"])
        collector.profile.phone = "09991112222"
        collector.profile.save(update_fields=["phone"])

        # Re-running seed_users must NEVER reset credentials or overwrite profiles
        call_command("seed_users")

        admin.refresh_from_db()
        admin.profile.refresh_from_db()
        collector.refresh_from_db()
        collector.profile.refresh_from_db()

        self.assertTrue(admin.check_password("MyCustomAdmin!2026"))
        self.assertFalse(admin.check_password("admin123"))
        self.assertEqual(admin.profile.phone, "09998887777")

        self.assertTrue(collector.check_password("MyCustomCollector!2026"))
        self.assertFalse(collector.check_password("collector123"))
        self.assertEqual(collector.profile.phone, "09991112222")
