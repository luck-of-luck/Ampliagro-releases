"""Brand identity in document heads, including standalone pages and admin."""
import re
from pathlib import Path
from urllib.parse import unquote

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import resolve

ROOT = Path(__file__).resolve().parents[1]


class BrandFaviconTests(SimpleTestCase):
    def test_all_document_heads_include_the_shared_brand(self):
        documents = []
        for path in (ROOT / 'app/templates').rglob('*.html'):
            source = path.read_text(encoding='utf-8')
            if re.search(r'<head\s*>', source, re.I):
                documents.append(path)
                head = re.split(r'</head>', source, flags=re.I)[0]
                self.assertIn('include "partials/brand-head.html"', head, str(path))
        self.assertGreaterEqual(len(documents), 6)

    def test_shared_icon_renders_and_exists(self):
        html = render_to_string('partials/brand-head.html')
        self.assertIn('image/svg+xml', html)
        self.assertIn('img/ampliagro-logo.svg?v=brand-1', html)
        self.assertIsNotNone(finders.find('img/ampliagro-logo.svg'))

    def test_default_favicon_redirect_uses_the_brand(self):
        match = resolve('/favicon.ico')
        self.assertIn('img/ampliagro-logo.svg', match.func.view_initkwargs['url'])

    def test_admin_login_inherits_brand(self):
        html = render_to_string('admin/login.html', {'site_header': 'Ampliagro'})
        self.assertIn('img/ampliagro-logo.svg?v=brand-1', html)

    def test_account_layout_inherits_brand(self):
        html = render_to_string('allauth/layouts/base.html')
        self.assertIn('img/ampliagro-logo.svg?v=brand-1', html)

    def test_standalone_pages_embed_the_same_vector(self):
        svg = (ROOT / 'app/static/img/ampliagro-logo.svg').read_text(encoding='utf-8')
        for name in ('landing.html', 'installer.html'):
            html = (ROOT / name).read_text(encoding='utf-8')
            icon = re.search(r'<link\b(?=[^>]*rel="icon")[^>]*href="([^"]+)"', html, re.S)
            self.assertIsNotNone(icon, name)
            self.assertEqual(unquote(icon.group(1).split(',', 1)[1]), svg)
