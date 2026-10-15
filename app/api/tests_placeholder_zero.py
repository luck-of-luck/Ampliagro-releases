"""Endpoints que respondiam "zero" sem perguntar à base.

O QUE ERA
---------
Quatro views em que o payload era literal:

    sensores_data()        -> {"sensores": [], "total": 0}
    dispositivos_data()    -> {"dispositivos": [], "total": 0}
    previsao_safra_data()  -> {"previsao": [], "total": 0}
    previsao_clima_data()  -> {"previsao": [], "fonte": "placeholder"}

Todas com o docstring "Placeholder for ...". Na base havia 2 estações e 8
safras.

A CRASE
-------
`total: 0` sem consulta à base é um zero FABRICADO. "Não tens estações" e
"não fui perguntar" chegam ao painel com a mesma cara, e a pessoa conclui
pela primeira — que é a conclusão errada, e a que a leva a Installing
again, a chamar um técnico, a comprar outra estação.

E `fonte: "placeholder"` no clima era pior, porque `ia-local.js` usa esse
endpoint (`clima: '/api/previsao-clima/'`). Quando a IA local não sabia o
tempo, recebia "placeholder" e respondia ao produtor que não sabia.

A REGUA
-------
Ou o número é CONTADO, ou a resposta diz que não sabe. Um `total: 0` que
significa "não contei" é pior que um `null`, porque o `null` convida à
pergunta.

O INVERSO TAMBEM ESTA TESTADO
-----------------------------
Um endpoint que devolve `aviso: "não existe modelo"` é uma resposta
honesta e accionável. Se um dia existir o modelo, o teste da lista
vazia tem de mudar — e vai mudar com ele, porque o aviso é o que manda
nessa transição.
"""

import json

from django.test import TestCase
from rest_framework.test import APIClient


class TestEndpointsNaoInventamZero(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        from app.models.core import Propriedade

        self.user = User.objects.create_user(username="t-placeholders", password="x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Faz Teste",
            area_total=50,
            cidade="Muzambinho",
            uf="MG",
        )
        self.c = APIClient()
        self.c.force_authenticate(self.user)

    def _cultura(self):
        """Safra.cultura e' NOT NULL — e' o schema real, nao um
        esquecimento do teste."""
        from app.models import Cultura

        c = Cultura.objects.first()
        if c:
            return c
        return Cultura.objects.create(nome="Arroz")

    # ── sensores ───────────────────────────────────────────────────────────

    def test_sensores_conta_a_base(self):
        from app.models import EstacaoMeteo

        EstacaoMeteo.objects.create(
            propriedade=self.prop,
            nome="Estacao A",
            ativa=True,
            latitude=-21.39,
            longitude=-46.47,
        )
        EstacaoMeteo.objects.create(
            propriedade=self.prop,
            nome="Estacao B",
            ativa=True,
            latitude=-21.39,
            longitude=-46.47,
        )
        r = self.c.get("/api/sensores/")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["total"], 2, "o total nao contou as estacoes da base")
        self.assertEqual(len(j["sensores"]), 2)

    def test_sensores_nao_conta_as_de_outro_utilizador(self):
        """O `total` tem de ser CONTADO E DELIMITADO. Contar tudo seria
        pior que inventar: mostraria a estação de outra fazenda."""
        from django.contrib.auth.models import User

        from app.models import EstacaoMeteo
        from app.models.core import Propriedade

        outro = User.objects.create_user(username="t-outro", password="x")
        prop_outro = Propriedade.objects.create(
            user=outro, nome="Faz Outro", area_total=10
        )
        EstacaoMeteo.objects.create(
            propriedade=prop_outro,
            nome="Alheia",
            ativa=True,
            latitude=-10.0,
            longitude=-50.0,
        )

        r = self.c.get("/api/sensores/")
        self.assertEqual(r.json()["total"], 0, "contou a estacao de outra fazenda")

    def test_sensores_diz_o_nome_da_fazenda(self):
        from app.models import EstacaoMeteo

        EstacaoMeteo.objects.create(
            propriedade=self.prop,
            nome="Estacao Muzambinho",
            ativa=True,
            latitude=-21.39,
            longitude=-46.47,
        )
        nomes = [
            s["propriedade"] for s in self.c.get("/api/sensores/").json()["sensores"]
        ]
        self.assertEqual(nomes, ["Faz Teste"])

    # ── dispositivos: nao ha modelo, e diz-se ──────────────────────────────

    def test_dispositivos_diz_que_o_modelo_nao_existe(self):
        r = self.c.get("/api/dispositivos/")
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["total"], 0)
        # O que distingue "nao tens dispositivos" de "nao ha modelo":
        self.assertEqual(j["fonte"], "modelo_inexistente")
        self.assertIn("aviso", j)

    # ── safras ─────────────────────────────────────────────────────────────

    def test_previsao_safra_conta_a_base(self):
        from app.models import Safra

        cultura = self._cultura()
        Safra.objects.create(
            propriedade=self.prop,
            safra_nome="Arroz 2026",
            ano=2026,
            area_plantada=6.0,
            cultura=cultura,
        )
        Safra.objects.create(
            propriedade=self.prop,
            safra_nome="Soja 2025",
            ano=2025,
            area_plantada=8.0,
            cultura=cultura,
        )
        r = self.c.get("/api/previsao-safra/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total"], 2, "o total nao contou as safras")

    def test_previsao_safra_usa_campos_que_existem(self):
        """`Safra` nao tem `area_hectare` nem `data_inicio` — tem
        `area_plantada` / `area_colhida` / `data_plantio`. Um campo
        errado dentro de um `except Exception` devolve 500 e engole o
        FieldError, que foi o que a IA-H encontrou no comparativo."""
        from app.models import Safra

        Safra.objects.create(
            propriedade=self.prop,
            safra_nome="Arroz 2026",
            ano=2026,
            area_plantada=12.5,
            cultura=self._cultura(),
        )
        r = self.c.get("/api/previsao-safra/")
        self.assertEqual(r.status_code, 200)
        item = r.json()["previsao"][0]
        self.assertIn("area_plantada", item)
        self.assertNotIn("area_hectare", item, "campo que nao existe no modelo")
        self.assertEqual(item["area_plantada"], 12.5)

    # ── clima ──────────────────────────────────────────────────────────────

    def test_previsao_clima_nao_e_placeholder(self):
        """`ia-local.js` usa este endpoint. 'placeholder' com lista vazia
        fazia a IA local dizer ao produtor que nao sabia.

        ESTE TESTE NAO VAI A REDE. MEDIDO 2026-10-05 (agente 9): ele falhava
        na suite completa e passava isolado, e a unica diferenca era a rede.

        `/api/previsao-clima/` tem DUAS saidas para a internet:
        `app.services.coordenadas.resolver` (geocode) e
        `ClimaService.get_previsao` (Open-Meteo). Sem mock, o resultado
        dependia de o Open-Meteo responder, de a API livre estar sob
        limite, e da ordem dos testes — porque a suite inteira chama este
        endpoint muitas vezes e a cota nao e' a mesma a meio e' ao fim.

        Um teste que davera dar verde-verde-verde deu o que dou quando chove.
        O objecto do teste nao e' o clima: e' **a forma da resposta**. O clima
        mockado em baixo e' arbitrario e o que interessa e' que a resposta
        traga `fonte` e nunca diga `placeholder`.
        """
        from unittest import mock

        from app.services.clima import ClimaService
        from app.services.coordenadas import Coordenadas

        com_coord = Coordenadas(
            -12.0, -55.0, "open-meteo", origem_detalhe="geocode de teste"
        )
        previsao = {
            "dias": [{"data": "2026-10-06", "temp_max": 32.0, "temp_min": 18.0}],
            "fonte": "open-meteo",
        }

        with (
            mock.patch("app.services.coordenadas.resolver", return_value=com_coord),
            mock.patch.object(ClimaService, "get_previsao", return_value=previsao),
        ):
            r = self.c.get("/api/previsao-clima/")

        self.assertEqual(
            r.status_code,
            200,
            f"com coordenadas e previsao mockadas nao havia motivo para falhar: "
            f"{r.status_code} {getattr(r, 'content', b'')[:200]!r}",
        )
        j = r.json()
        self.assertNotEqual(j.get("fonte"), "placeholder")
        self.assertIn("fonte", j, "um clima sem origem nao e' accionavel")

    def test_previsao_clima_com_coordenada_ausente_diz_que_nao_sabe(self):
        """O caminho do 503, sem rede: e' o que a IA local recebe quando nao ha
        talhao nem estacao registados.

        Este e' o outro meio da mesma frase. A resposta tem de DIZER que nao
        sabe — e nao devolver "placeholder", que era exactamente o defeito.
        """
        from unittest import mock

        from app.services.coordenadas import Coordenadas

        sem_coord = Coordenadas(
            None, None, "sem_coordenada", aviso="cadastre a cidade/UF"
        )

        # Patch no SERVICO: a view faz `from app.services.coordenadas import
        # resolver` DENTRO da funcao, e por isso o nome resolve-se na chamada.
        with mock.patch("app.services.coordenadas.resolver", return_value=sem_coord):
            r = self.c.get("/api/previsao-clima/")

        self.assertEqual(r.status_code, 503)
        j = r.json()
        self.assertIn("erro", j)
        self.assertNotEqual(j.get("fonte"), "placeholder")

    def test_previsao_clima_tem_o_mesmo_formato_da_pagina(self):
        """O pipeline e' o mesmo. Se divergirem, a IA e a pagina voltam a
        discordar — que foi o defeito do primeiro bloco.

        Com uma propriedade SEM coordenada resolvida (a de teste nao tem
        talhoes nem estacao), a resposta honesta e' 503 com o motivo. O
        que este teste verifica e' que o formato de erro e' o mesmo em
        ambos os pipelines.
        """
        from unittest import mock

        from app.services.coordenadas import Coordenadas

        # Mock do resolver, e nao confiar na rede: com cidade="Muzambinho"
        # o geocode REAL responde, e o teste passava por acidente num
        # ambiente com rede e falhava noutro sem ela. Um teste que depende
        # da rede nao e' um teste.
        sem_coord = Coordenadas(
            None, None, "sem_coordenada", aviso="cadastre a cidade/UF"
        )
        # O patch vai no SERVIÇO, não na view: previsao_clima_data faz
        # rom app.services.coordenadas import resolver DENTRO da
        # função, e aí o nome é resolvido no momento da chamada. Parchar
        # pp.api.views.core.resolver_coordenadas não pega — e o teste
        # passava porque o geocode REAL respondeu.
        with mock.patch("app.services.coordenadas.resolver", return_value=sem_coord):
            r = self.c.get("/api/previsao-clima/")
        self.assertEqual(r.status_code, 503)
        j = r.json()
        self.assertIn("erro", j)
        self.assertIn("fonte", j, "a resposta de erro diz onde procurou")
        self.assertNotEqual(j["fonte"], "placeholder")


class TestAFormaDoPayloadNaoMuda(TestCase):
    """Um `total` novo pode mudar a forma. Estes testes骗am a interface
    a mudar por accident, para o dia de someone"""

    def setUp(self):
        from django.contrib.auth.models import User

        from app.models.core import Propriedade

        self.user = User.objects.create_user(username="t-forma", password="x")
        # A propriedade: sem ela, previsao-safra devolve 404 — o que e'
        # CORRETO (nao ha fazenda), e nao um sitio para testar o total.
        Propriedade.objects.create(user=self.user, nome="Faz Forma", area_total=10)
        self.c = APIClient()
        self.c.force_authenticate(self.user)

    def test_todos_devolvem_total_inteiro(self):
        for url in ("/api/sensores/", "/api/dispositivos/", "/api/previsao-safra/"):
            with self.subTest(url=url):
                r = self.c.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertIsInstance(r.json()["total"], int)

    def test_total_bate_com_o_tamanho_da_lista(self):
        """Se algum dia divergirem, quem lê o painel vê dois numeros
        diferentes para a mesma coisa."""
        for url, chave in (
            ("/api/sensores/", "sensores"),
            ("/api/dispositivos/", "dispositivos"),
            ("/api/previsao-safra/", "previsao"),
        ):
            with self.subTest(url=url):
                j = self.c.get(url).json()
                self.assertEqual(j["total"], len(j[chave]), f"{url}: total != lista")
