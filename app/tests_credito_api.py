"""A API de crédito tem de ser útil E segura.

A parte útil é obvious: devolve fatores com fonte. A parte que este ficheiro
testa a sério é a **segurança**, porque o que exposto é dado financeiro do
produtor — a mesma classe que `hierarquia.py` trata como "o mais sensível do
sistema" (`pode_ver_financeiro`, linha 389).

Três coisas que uma API de crédito pode fazer mal, e que este ficheiro fixa:

1. **Deixar ver a propriedade alheia.** O `TenantIsolationMiddleware` protege
   query params; esta view recebe `propriedade_id` na query string, e o
   middleware valida-o por TABELA (`app/middleware.py:60-70`). O teste
   verifica que mesmo autenticado, o produtor B não lê a fazenda do A.
2. **Colapsar 404 e 403.** Um `id` inexistente e um `id` alheio são respostas
   diferentes: a primeira é alguém que errou o número, a segunda é alguém a
   tentar ver a lavoura do vizinho. Juntas, a tentativa desaparece dentro de um
   erro banal.
3. **Escrever.** A view é read-only. Se aceitasse POST, o produtor poderia
   fabricar o histórico de custo que o banco ia ler.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from app.models import (
    Cultura,
    LancamentoFinanceiro,
    PerfilUsuario,
    Propriedade,
    Safra,
)


class CreditoAPITest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", password="x")
        self.bob = User.objects.create_user("bob", password="x")

        # `PerfilUsuario` é criado automaticamente (signal) — recriá-lo viola
        # `UNIQUE(user_id)`. E `hierarquia.py:394-398` diz que, sem perfil, o
        # padrão é NÃO ver. Basta garantir que o perfil é de produtor.
        for u in (self.ana, self.bob):
            perfil = PerfilUsuario.objects.get(user=u)
            perfil.tipo_usuario = "produtor"
            perfil.save()

        self.prop_ana = Propriedade.objects.create(
            user=self.ana, nome="Fazenda da Ana", area_total=100
        )
        self.prop_bob = Propriedade.objects.create(
            user=self.bob, nome="Fazenda do Bob", area_total=50
        )

        cultura = Cultura.objects.create(nome="Soja", ativo=True)
        self.safra = Safra.objects.create(
            propriedade=self.prop_ana,
            cultura=cultura,
            ano=2026,
            area_plantada=Decimal("50.00"),
            producao_total=Decimal("30000.00"),
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop_ana,
            descricao="Venda",
            valor=Decimal("90000.00"),
            tipo="RECEITA",
            categoria="VENDA_PROD",
            data=date(2026, 3, 10),
            safra=self.safra,
        )

        self.client = APIClient()

    # ------------------------------------------------------------------
    # Funcionalidade
    # ------------------------------------------------------------------

    def test_fatores_respondem_com_o_payload(self):
        self.client.force_authenticate(self.ana)
        r = self.client.get(
            "/api/credito/fatores/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn("fatores", r.data)
        self.assertEqual(r.data["fatores"]["receitas_periodo"]["valor"], 90000.0)

    def test_historico_responde_com_safras(self):
        self.client.force_authenticate(self.ana)
        r = self.client.get(
            "/api/credito/historico/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["safras"]), 1)
        self.assertEqual(r.data["safras"][0]["ano"], 2026)

    def test_payload_nao_decide_credito(self):
        """A API expõe `decisao_de_credito: null` — sempre."""
        self.client.force_authenticate(self.ana)
        r = self.client.get(
            "/api/credito/fatores/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertIsNone(r.data["decisao_de_credito"])

    # ------------------------------------------------------------------
    # Segurança — a parte que interessa
    # ------------------------------------------------------------------

    def test_anonymous_nao_acessa(self):
        r = self.client.get(
            "/api/credito/fatores/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertIn(r.status_code, (401, 403))

    def test_produtor_nao_ve_propriedade_alheia(self):
        """O Bob está autenticado e tem perfil — e mesmo assim não lê a Ana."""
        self.client.force_authenticate(self.bob)
        r = self.client.get(
            "/api/credito/fatores/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertEqual(
            r.status_code,
            403,
            "produtor B leu a fazenda de A: o filtro de posse nao funciona",
        )

    def test_propriedade_inexistente_e_404_nao_403(self):
        """Errar o número é 404. Ver o do outro é 403. São respostas distintas.

        Colapsar as duas esconde a tentativa dentro de um erro banal — é o que
        `TenantIsolationMiddleware` aviza em docstring.
        """
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/credito/fatores/", {"propriedade_id": 999999})
        self.assertEqual(r.status_code, 404)

    def test_propriedade_alheia_e_403_nao_404(self):
        self.client.force_authenticate(self.bob)
        r = self.client.get(
            "/api/credito/fatores/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertEqual(r.status_code, 403)

    def test_sem_parametro_e_400(self):
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/credito/fatores/", {})
        self.assertEqual(r.status_code, 400)

    def test_parametro_nao_numerico_e_400(self):
        self.client.force_authenticate(self.ana)
        r = self.client.get("/api/credito/fatores/", {"propriedade_id": "abc"})
        self.assertEqual(r.status_code, 400)

    def test_historico_tambem_respeita_a_posse(self):
        """O segundo action não pode ser uma porta lateral."""
        self.client.force_authenticate(self.bob)
        r = self.client.get(
            "/api/credito/historico/", {"propriedade_id": self.prop_ana.id}
        )
        self.assertEqual(r.status_code, 403)

    # ------------------------------------------------------------------
    # Read-only
    # ------------------------------------------------------------------

    def test_write_e_recusado(self):
        """POST/PUT/DELETE não podem fabricar histórico de custo."""
        self.client.force_authenticate(self.ana)
        url = "/api/credito/fatores/"
        for metodo in ("post", "put", "delete", "patch"):
            with self.subTest(metodo=metodo):
                r = getattr(self.client, metodo)(
                    url, {"propriedade_id": self.prop_ana.id}
                )
                self.assertIn(
                    r.status_code,
                    (404, 405),
                    f"{metodo} foi aceite: um produtor pode fabricar o "
                    "historico que o banco le",
                )
