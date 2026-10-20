# core/test_user_account_management.py
# Regression tests for the staff-account (collector) creation + sign-in flow.
#
# Regression: UserProfileForm used to include the ``user`` FK as a required
# field that the template never rendered, so EVERY staff-account creation
# failed validation ("This field is required.") and the account was never
# created — a newly added collector could therefore never sign in.
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.test import TestCase

from core.models import UserProfile


class StaffAccountCreationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='boss', password='Admin!Pass123')
        UserProfile.objects.create(user=self.admin, role='admin')
        self.client.force_login(self.admin)

    def _payload(self, username='collector1', role='collector'):
        return {
            'username': username,
            'email': f'{username}@example.com',
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'password1': 'Zamb#2026!Dum',
            'password2': 'Zamb#2026!Dum',
            'role': role,
            'phone': '09123456789',
            'address': 'Poblacion 1, Dumingag',
        }

    def test_profile_form_does_not_require_user_field(self):
        """The ``user`` FK is assigned by the view, so it must not be a form field."""
        from core.forms import UserProfileForm

        self.assertNotIn('user', UserProfileForm().fields)

    def test_creating_a_collector_actually_creates_the_account(self):
        response = self.client.post('/users/add/', self._payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            User.objects.filter(username='collector1').exists(),
            'The collector account was not created — the form failed validation.',
        )

    def test_new_collector_has_profile_with_collector_role(self):
        self.client.post('/users/add/', self._payload(), follow=True)
        user = User.objects.get(username='collector1')
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, 'collector')

    def test_new_collector_password_is_usable_and_authenticates(self):
        self.client.post('/users/add/', self._payload(), follow=True)
        user = User.objects.get(username='collector1')
        self.assertTrue(user.has_usable_password())
        self.assertIsNotNone(authenticate(username='collector1', password='Zamb#2026!Dum'))

    def test_new_collector_can_sign_in_through_the_login_form(self):
        self.client.post('/users/add/', self._payload(), follow=True)
        self.client.logout()

        response = self.client.post(
            '/login/',
            {'username': 'collector1', 'password': 'Zamb#2026!Dum'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', 'ignore')
        self.assertNotIn('Invalid username or password', body)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'collector1')

    def test_new_collector_reaches_the_dashboard_and_billing(self):
        self.client.post('/users/add/', self._payload(), follow=True)
        self.client.logout()
        self.client.post(
            '/login/',
            {'username': 'collector1', 'password': 'Zamb#2026!Dum'},
            follow=True,
        )
        self.assertEqual(self.client.get('/dashboard/').status_code, 200)
        self.assertEqual(self.client.get('/billing/').status_code, 200)

    def test_editing_a_collector_keeps_the_account_usable(self):
        self.client.post('/users/add/', self._payload(), follow=True)
        user = User.objects.get(username='collector1')

        payload = self._payload()
        payload['first_name'] = 'Juan Jr.'
        response = self.client.post(f'/users/{user.id}/edit/', payload, follow=True)
        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Juan Jr.')
        self.assertTrue(user.has_usable_password())
        self.assertIsNotNone(authenticate(username='collector1', password='Zamb#2026!Dum'))

    def test_tenant_role_is_still_refused_from_the_users_page(self):
        """Tenant logins must be created from the Tenants page, not here."""
        payload = self._payload(username='orphan_login', role='tenant')
        response = self.client.post('/users/add/', payload, follow=True)
        self.assertFalse(User.objects.filter(username='orphan_login').exists())
        self.assertEqual(response.redirect_chain[-1][0], '/tenants/add/')
