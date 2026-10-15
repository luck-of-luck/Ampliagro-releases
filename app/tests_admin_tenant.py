"""Testes do tenant_switcher, depois da correccao de 04/10/2026.

Cobre o que a correccao mudou e o que nao pode partir:
  1. staff troca de tenant e a sessao fica com o tenant_id
  2. a accao fica registada (antes era silenciosa)
  3. tid invalido nao da 500 — e' o `isdigit()` que evita
  4. nao-staff nao chega
  5. a rota e' resolvida por NOME, nunca escrita a mao
"""

import logging
import os
import sys

import django
import pathlib

RAIZ = str(pathlib.Path(__file__).resolve().parents[1])
sys.path.insert(0, RAIZ)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from django.test import Client, TestCase  # noqa: E402
from django.urls import reverse  # noqa: E402

from app.models import Propriedade  # noqa: E402


class TenantSwitcherTest(TestCase):
    def setUp(self):
        # Resolver por NOME e' obrigatorio: um path escrito a mao devolve 404
        # quando a rota muda, e 404 faz os testes passarem a mentira.
        self.url = reverse("tenant-switcher")

        self.staff = User.objects.create_user("staff_t", password="x")
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save()

        self.comum = User.objects.create_user("comum_t", password="x")
        self.dono = User.objects.create_user("dono_t", password="x")

        self.prop_a = Propriedade.objects.create(
            user=self.dono, nome="Faz A", area_total=1, uf="MT", cidade="X"
        )
        self.prop_b = Propriedade.objects.create(
            user=self.dono, nome="Faz B", area_total=2, uf="MT", cidade="X"
        )

    def test_staff_troca_de_tenant(self):
        c = Client()
        c.force_login(self.staff)
        r = c.post(self.url, {"tenant_id": self.prop_b.id})
        self.assertEqual(r.status_code, 302, "o POST tem de redirigir, nao renderizar")
        self.assertEqual(c.session.get("tenant_id"), self.prop_b.id)

    def test_troca_de_tenant_e_registada(self):
        """A accao privilegiada nao pode ser silenciosa."""
        registos = []

        class Capta(logging.Handler):
            def emit(self, record):
                registos.append(record.getMessage())

        logger = logging.getLogger("app.views.admin_tenant")
        handler = Capta()
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        try:
            c = Client()
            c.force_login(self.staff)
            c.post(self.url, {"tenant_id": self.prop_b.id})
        finally:
            logger.removeHandler(handler)

        self.assertTrue(
            any("tenant_trocado" in m for m in registos),
            f"a troca de tenant nao foi registada: {registos!r}",
        )

    def test_tid_invalido_nao_da_500(self):
        """Sem o `isdigit()`, o filter do Django levanta ValueError -> 500."""
        c = Client()
        c.force_login(self.staff)
        r = c.post(self.url, {"tenant_id": "abc"})
        self.assertNotEqual(r.status_code, 500, "tid nao numerico deu 500")
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(
            c.session.get("tenant_id"), "um tid invalido nao pode mudar a sessao"
        )

    def test_limpar_tenant(self):
        c = Client()
        c.force_login(self.staff)
        c.post(self.url, {"tenant_id": self.prop_a.id})
        self.assertEqual(c.session.get("tenant_id"), self.prop_a.id)
        c.post(self.url, {"tenant_id": ""})
        self.assertIsNone(c.session.get("tenant_id"))

    def test_nao_staff_nao_chega(self):
        c = Client()
        c.force_login(self.comum)
        r = c.post(self.url, {"tenant_id": self.prop_b.id})
        self.assertIn(r.status_code, (302, 403))
        self.assertIsNone(c.session.get("tenant_id"), "um nao-staff mudou o tenant")
