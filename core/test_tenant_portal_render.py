"""Tenant portal rendering regression tests.

Guards against the failure mode where the tenant self-service portal
(``/portal/``) is served as raw template source or as a fragment rather
than as a fully rendered HTML document. Each test asserts that the
response is a proper ``base.html``-wrapped page — HTTP 200, ``text/html``
content type, DOCTYPE present, no unrendered Django tags leaking into the
body, and the correct tenant-scoped data visible.

Also locks in the RBAC contract: only tenant-role accounts may enter the
portal, superusers/staff are redirected, and the "no linked Tenant"
fallback renders its own styled page instead of raising 500.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import (
    Billing, MarketSection, Payment, RentalContract, Stall, StallType,
    SystemSetting, Tenant, TenantLedger, UserProfile,
)


class TenantPortalRenderBase(TestCase):
    """Shared fixture: a fully populated tenant with contract + billing + ledger."""

    def setUp(self):
        SystemSetting.objects.create(
            municipality_name='Dumingag', market_name='Dumingag Public Market',
            office_name='Office', receipt_prefix='DMPM', default_due_day=5,
        )
        self.tenant_user = User.objects.create_user(
            username='tenantjuan', password='Tenant!Pass123',
            first_name='Juan', last_name='Dela Cruz',
        )
        UserProfile.objects.create(user=self.tenant_user, role='tenant')

        self.tenant = Tenant.objects.create(
            user=self.tenant_user,
            first_name='Juan', last_name='Dela Cruz',
            business_name='Juan Sari-Sari', barangay='Poblacion',
            contact_number='09000000001', tenant_id='DMPM-T001',
        )
        section = MarketSection.objects.create(name='Dry Goods')
        stall_type = StallType.objects.create(name='Regular Stall')
        self.stall = Stall.objects.create(
            stall_number='DGS-01', section=section, stall_type=stall_type,
            monthly_rate=Decimal('500.00'), status='Occupied',
        )
        today = date.today()
        self.contract = RentalContract.objects.create(
            tenant=self.tenant, stall=self.stall,
            monthly_rent=Decimal('500.00'),
            start_date=today - timedelta(days=90),
            end_date=today + timedelta(days=275),
            status='Active',
        )
        self.billing = Billing.objects.create(
            tenant=self.tenant, stall=self.stall, contract=self.contract,
            billing_month=today.month, billing_year=today.year,
            rental_amount=Decimal('500.00'),
            total_due=Decimal('500.00'), balance=Decimal('500.00'),
            due_date=today + timedelta(days=5), status='Unpaid',
        )
        TenantLedger.objects.create(
            tenant=self.tenant, billing=self.billing, transaction_date=today,
            description=f'Rent {today.month:02d}/{today.year} - {self.stall.stall_number}',
            debit=Decimal('500.00'), credit=Decimal('0.00'),
            balance=Decimal('500.00'),
        )


class TenantPortalDashboardRendersTests(TenantPortalRenderBase):
    """The /portal/ dashboard must arrive as a fully rendered HTML page."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tenant_user)
        self.response = self.client.get(reverse('tenant_portal'))

    def test_dashboard_returns_http_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_dashboard_content_type_is_html(self):
        self.assertEqual(self.response['Content-Type'], 'text/html; charset=utf-8')

    def test_dashboard_is_fully_rendered_not_raw_source(self):
        """No Django template syntax may leak into the rendered body.

        If ``{% extends %}`` / ``{{ tenant }}`` appear verbatim in the
        response, the file was streamed instead of rendered — exactly
        the "raw source code on screen" symptom we are guarding against.
        """
        body = self.response.content.decode('utf-8')
        for marker in (
            '{% extends', '{{ tenant', '{% block content',
            '{% if outstanding_balance', '{% for billing in upcoming',
            '{{ total_paid|', '{{ active_contract.monthly_rent',
        ):
            self.assertNotIn(
                marker, body,
                msg=f'Unrendered Django syntax found in response: {marker!r}',
            )

    def test_dashboard_wrapped_in_base_template(self):
        """Confirms ``{% extends 'base.html' %}`` actually executed."""
        body = self.response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertIn('<html lang="en"', body)
        # base.html ships a distinctive sidebar + htmx bootstrap that no
        # standalone fragment would include.
        self.assertIn('htmx.min.js', body)
        self.assertIn('alpine.min.js', body)
        self.assertIn('My Portal', body)

    def test_dashboard_shows_tenant_scoped_data(self):
        self.assertContains(self.response, 'Juan Dela Cruz')
        self.assertContains(self.response, 'DMPM-T001')
        self.assertContains(self.response, 'DGS-01')
        # Total billed = 500.00 rendered with the peso sign entity.
        self.assertContains(self.response, '500.00')

    def test_dashboard_does_not_leak_other_tenants(self):
        other_user = User.objects.create_user(username='other', password='Other!Pass123')
        UserProfile.objects.create(user=other_user, role='tenant')
        Tenant.objects.create(
            user=other_user, first_name='Maria', last_name='Other',
            barangay='Poblacion', tenant_id='DMPM-T999',
        )
        body = self.client.get(reverse('tenant_portal')).content.decode('utf-8')
        self.assertNotIn('DMPM-T999', body)
        self.assertNotIn('Maria Other', body)


class TenantPortalHistoryRendersTests(TenantPortalRenderBase):
    """The /portal/history/ page uses the same view pattern and must also render."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tenant_user)

    def test_history_renders_full_page_for_normal_get(self):
        response = self.client.get(reverse('tenant_portal_history'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        body = response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertIn('Transaction History', body)
        # No raw template tags.
        self.assertNotIn('{% extends', body)
        self.assertNotIn('{{ tenant', body)
        self.assertNotIn('{% include', body)

    def test_history_returns_fragment_for_htmx_get(self):
        """HTMX requests must receive only the fragment (no <html> wrapper)."""
        response = self.client.get(
            reverse('tenant_portal_history'), HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        # The fragment carries a specific wrapper id used as the swap target.
        self.assertIn('portal-history-wrapper', body)
        # And is NOT wrapped in the base template.
        self.assertNotIn('<!DOCTYPE html>', body)
        self.assertNotIn('htmx.min.js', body)


class TenantPortalPasswordRendersTests(TenantPortalRenderBase):
    """The /portal/password/ page must render as a styled form."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tenant_user)

    def test_password_page_renders_form(self):
        response = self.client.get(reverse('tenant_portal_password'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertIn('Change Password', body)
        self.assertIn('name="new_password1"', body)
        self.assertIn('name="new_password2"', body)
        self.assertIn('name="old_password"', body)
        self.assertIn('csrfmiddlewaretoken', body)
        # No raw template tags.
        self.assertNotIn('{% extends', body)
        self.assertNotIn('{% csrf_token %}', body)


class TenantPortalAccessControlTests(TenantPortalRenderBase):
    """Portal renders only for tenant-role users; other roles are bounced."""

    def test_staff_get_redirected_away_from_portal(self):
        staff = User.objects.create_user(username='boss', password='Boss!Pass123')
        UserProfile.objects.create(user=staff, role='admin')
        self.client.force_login(staff)
        response = self.client.get(reverse('tenant_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('dashboard'))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('tenant_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_tenant_without_linked_record_gets_styled_notice(self):
        orphan = User.objects.create_user(username='orphan', password='Orphan!Pass123')
        UserProfile.objects.create(user=orphan, role='tenant')
        self.client.force_login(orphan)
        response = self.client.get(reverse('tenant_portal'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertIn('No tenant record linked', body)
        # Not raw source.
        self.assertNotIn('{% extends', body)


class TenantPortalEdgeCaseTests(TenantPortalRenderBase):
    """Empty-state paths must still render, never blow up or dump source."""

    def test_dashboard_renders_with_no_billings(self):
        Billing.objects.all().delete()
        TenantLedger.objects.all().delete()
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse('tenant_portal'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertNotIn('{% extends', body)
        # Empty-state copy appears.
        self.assertIn('fully paid up', body)

    def test_dashboard_renders_with_no_active_contract(self):
        RentalContract.objects.filter(tenant=self.tenant).update(status='Terminated')
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse('tenant_portal'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertNotIn('{% extends', body)

    def test_dashboard_forces_password_change_when_flag_set(self):
        profile = self.tenant_user.profile
        profile.must_change_password = True
        profile.save(update_fields=['must_change_password'])
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse('tenant_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('tenant_portal_password'))
