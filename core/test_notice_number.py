from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User

from core.forms import NoticeForm
from core.helpers import generate_notice_number
from core.models import Notice, Tenant


class NoticeNumberTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(tenant_id='NOTICE-TEST', full_name='Notice Tenant', address='x', contact_number='0900')
        self.prefix = f'N-{timezone.localdate().year}-'
        self.data = {'tenant': self.tenant.pk, 'notice_type': 'Payment Reminder',
                     'date_issued': timezone.localdate().isoformat(), 'content': 'Please pay rent.'}

    def test_form_previews_number_without_creating_notice(self):
        form = NoticeForm()
        self.assertEqual(form.initial['notice_number'], self.prefix + '001')
        self.assertTrue(form.fields['notice_number'].disabled)
        self.assertEqual(Notice.objects.count(), 0)

    def test_creates_sequential_numbers_ignoring_submitted_number(self):
        for suffix in ['001', '002']:
            form = NoticeForm({**self.data, 'notice_number': 'CUSTOM'})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().notice_number, self.prefix + suffix)

    def test_stale_forms_receive_unique_numbers_on_save(self):
        first, second = NoticeForm(self.data), NoticeForm(self.data)
        self.assertTrue(first.is_valid(), first.errors)
        self.assertTrue(second.is_valid(), second.errors)
        self.assertNotEqual(first.save().notice_number, second.save().notice_number)

    def test_continues_highest_sequence_and_ignores_legacy_format(self):
        Notice.objects.create(tenant=self.tenant, notice_type='Payment Reminder', notice_number=self.prefix+'009', date_issued=timezone.localdate(), content='x')
        Notice.objects.create(tenant=self.tenant, notice_type='Payment Reminder', notice_number='LEGACY-1', date_issued=timezone.localdate(), content='x')
        self.assertEqual(generate_notice_number(), self.prefix+'010')

    def test_create_view_accepts_no_manual_number(self):
        user = User.objects.create_superuser(username='notice-admin', password='test')
        self.client.force_login(user)
        response = self.client.post(reverse('notice_add'), self.data)
        self.assertRedirects(response, reverse('notice_list'))
        self.assertEqual(Notice.objects.get().notice_number, self.prefix+'001')
