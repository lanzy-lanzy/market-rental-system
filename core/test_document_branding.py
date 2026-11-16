import base64
from types import SimpleNamespace
from unittest.mock import Mock

from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class DocumentBrandingTests(SimpleTestCase):
    def test_default_logo_is_embedded_without_settings(self):
        html = render_to_string('includes/document_logo.html', {})
        self.assertIn('data:image/png;base64,', html)
        self.assertIn('Municipality logo', html)
        self.assertIn('width="64"', html)

    def test_uploaded_logo_takes_precedence(self):
        logo = ContentFile(b'custom-image', name='logos/custom.png')
        html = render_to_string('includes/document_logo.html', {
            'system_settings': SimpleNamespace(logo=logo, municipality_name='Test Town'),
        })
        self.assertIn(base64.b64encode(b'custom-image').decode(), html)
        self.assertIn('Test Town logo', html)

    def test_missing_upload_falls_back_to_bundled_logo(self):
        logo = Mock()
        logo.open.side_effect = FileNotFoundError()
        html = render_to_string('includes/document_logo.html', {
            'system_settings': SimpleNamespace(logo=logo, municipality_name='Test Town'),
        })
        self.assertIn('data:image/png;base64,', html)

    def test_receipt_settings_alias_is_supported(self):
        logo = ContentFile(b'receipt-logo', name='logos/receipt.png')
        html = render_to_string('includes/document_logo.html', {
            'settings': SimpleNamespace(logo=logo, municipality_name='Receipt Town'),
        })
        self.assertIn(base64.b64encode(b'receipt-logo').decode(), html)
        self.assertIn('Receipt Town logo', html)
