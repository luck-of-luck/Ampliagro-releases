"""ZARC por safra — o aviso que evita o produtor perder a indenização.

Este é o endpoint da §21.1: o que o Ampliagro pode fazer que os quatro
concorrentes que pesquisei não fazem — **avisar o produtor**, e não avaliar
risco para a seguradora.

O teste que importa mais aqui é `test_ausencia_responde_200_com_none`:
quando não há ZARC para a geografia, a resposta é **200 com
`dentro_da_janela: null`**, não 404 e não `False`. Um `404` diria ao produtor
"a tua lavoura não existe" (não é verdade) e um `False` diria "está fora da
janela" (também não é verdade — não temos o dado).
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from app.models import (
    Cultura,
    PerfilUsuario,
    Propriedade,
    Safra,
)
from app.models.producao import ZARC


class ZarcApiTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        for u in (self.ana, self.bob):
            p = PerfilUsuario.objects.get(user=u)
            p.tipo_usuario = "produtor"
            p.save()

        self.prop = Propriedade.objects.create(
            user=self.ana, nome="Fazenda", area_total=100, uf="MT", cidade="Sorriso"
        )
        self.cultura = Cultura.objects.create(nome="Soja", ativo=True)
        ZARC.objects.create(
            cultura=self.cultura,
            uf="MT",
            municipio="Sorriso",
            data_inicio_plantio=date(2026, 9, 15),
            data_fim_plantio=date(2026, 10, 20),
            ciclo_dias=120,
        )
        self.client = APIClient()

    def _safra(self, data_plantio, prop=None):
        return Safra.objects.create(
            propriedade=prop or self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada="50.00",
            producao_total="30000.00",
            data_plantio=data_plantio,
        )

    def test_dentro_da_janela(self):
        s = self._safra(date(2026, 10, 1))
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/zarc/verificar_safra/", {"safra_id": s.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIs(r.data["dentro_da_janela"], True)

    def test_fora_da_janela(self):
        s = self._safra(date(2026, 11, 15))
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/zarc/verificar_safra/", {"safra_id": s.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIs(r.data["dentro_da_janela"], False)
        self.assertIsNotNone(r.data["aviso"])

    def test_ausencia_responde_200_com_none(self):
        """Sem ZARC para a geografia: 200, `None`, com motivo.

        Nem 404 (a safra existe), nem `False` (não sabemos). E o motivo diz
        o que o sistema não tem.
        """
        longe = Propriedade.objects.create(
            user=self.ana, nome="Longe", area_total=10, uf="MS", cidade="Ponta Porã"
        )
        s = self._safra(date(2026, 10, 1), prop=longe)
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/zarc/verificar_safra/", {"safra_id": s.id})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(
            r.data["dentro_da_janela"],
            "ausencia virou veredito: o produtor foi avisado de um risco que "
            "o sistema nao tem como avaliar",
        )
        self.assertIsNotNone(r.data["motivo"])

    def test_anonymous_nao_acessa(self):
        s = self._safra(date(2026, 10, 1))
        r = self.client.get("/api/zarc/verificar_safra/", {"safra_id": s.id})
        self.assertIn(r.status_code, (401, 403))

    def test_nao_ve_safra_alheia(self):
        """A geografia é dado sensível — diz onde está a fazenda."""
        s = self._safra(date(2026, 10, 1))
        self.client.force_authenticate(self.bob)
        r = self.client.get("/api/zarc/verificar_safra/", {"safra_id": s.id})
        self.assertEqual(r.status_code, 403)

    def test_safra_inexistente_404(self):
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/zarc/verificar_safra/", {"safra_id": 999999})
        self.assertEqual(r.status_code, 404)

    def test_sem_parametro_400(self):
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/zarc/verificar_safra/", {})
        self.assertEqual(r.status_code, 400)
