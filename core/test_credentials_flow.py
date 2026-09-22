# core/test_credentials_flow.py
# Functional test for the streamlined tenant creation + password-change workflow.
from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Tenant, UserProfile
from core.helpers import create_tenant_login, generate_strong_password


class TenantCredentialsFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def _tenant_payload(self, tid='T-900'):
        return {
            'tenant_id': tid,
            'full_name': 'Juan Dela Cruz',
            'address': '123 Market St',
            'contact_number': '09123456789',
            'email': 'juan@example.com',
            'valid_id_type': 'Others',
            'valid_id_number': 'ID123',
            'business_name': 'Juan Sari-Sari',
            'business_type': 'Grocery',
            'emergency_contact_name': 'Maria',
            'emergency_contact_number': '09999999999',
            'status': 'Active',
            'notes': '',
        }

    def test_generated_password_is_strong(self):
        pwd = generate_strong_password()
        self.assertGreaterEqual(len(pwd), 14)
        self.assertTrue(any(c.isupper() for c in pwd))
        self.assertTrue(any(c.islower() for c in pwd))
        self.assertTrue(any(c.isdigit() for c in pwd))
        self.assertTrue(any(c in '!@#$%^&*-_=+' for c in pwd))

    def test_full_page_add_creates_login_and_shows_credentials(self):
        resp = self.client.post('/tenants/add/', self._tenant_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'tenants/credentials.html')
        tenant = Tenant.objects.get(tenant_id='T-900')
        self.assertIsNotNone(tenant.user)
        self.assertTrue(tenant.user.profile.must_change_password)
        content = resp.content.decode()
        self.assertIn(tenant.user.username, content)
        self.assertIn('generated_password', resp.context)

    def test_modal_add_creates_login(self):
        resp = self.client.post(
            '/tenants/add-modal/', self._tenant_payload('T-901'),
            headers={'hx-request': 'true'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'tenants/_credentials_fragment.html')
        tenant = Tenant.objects.get(tenant_id='T-901')
        self.assertTrue(tenant.user.profile.must_change_password)

    def test_force_password_change_and_self_service_update(self):
        tenant = Tenant.objects.create(**{k: v for k, v in self._tenant_payload('T-902').items()})
        user, temp_password = create_tenant_login(tenant)

        # Tenant logs in and is forced to the password page from the dashboard.
        self.client.force_login(user)
        resp = self.client.get('/portal/')
        self.assertRedirects(resp, '/portal/password/')

        # Submitting a new password clears the flag and grants dashboard access.
        new_password = 'Str0ng!NewPass42'
        resp = self.client.post('/portal/password/', {
            'old_password': temp_password,
            'new_password1': new_password,
            'new_password2': new_password,
        })
        self.assertRedirects(resp, '/portal/', target_status_code=200)
        user.refresh_from_db()
        self.assertFalse(user.profile.must_change_password)
        self.assertTrue(user.check_password(new_password))

        # Dashboard now accessible.
        resp = self.client.get('/portal/')
        self.assertEqual(resp.status_code, 200)

    def test_password_change_rejects_weak_new_password(self):
        tenant = Tenant.objects.create(**{k: v for k, v in self._tenant_payload('T-903').items()})
        user, temp_password = create_tenant_login(tenant)
        self.client.force_login(user)
        resp = self.client.post('/portal/password/', {
            'old_password': temp_password,
            'new_password1': '1234',
            'new_password2': '1234',
        })
        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.profile.must_change_password)  # still forced
