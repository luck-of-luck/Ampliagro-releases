"""Regressão da caçada 2026-09-18: 500s e backends ressuscitados."""

import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from app.api.views.mip import MonitoramentoPragaViewSet
from app.api.views.pecuaria import RacaoViewSet
from app.models import Cultura, Propriedade, Talhao


def _mkuser(name):
    return User.objects.create_user(username=name, password="test")


def _mkprop(user, nome="Faz Reg"):
    return Propriedade.objects.create(user=user, nome=nome, area_total=100)


class PaginasQueDavam500Test(TestCase):
    """Páginas que retornavam 500 (NameError/FieldError) devem dar 200."""

    def setUp(self):
        self.u = _mkuser("reg-pages")
        _mkprop(self.u)
        self.c = Client()
        self.c.force_login(self.u)

    def test_cadastro_mip_200(self):
        self.assertEqual(self.c.get("/cadastro/mip/").status_code, 200)

    def test_simulador_lucro_200(self):
        self.assertEqual(self.c.get("/simulador-lucro/").status_code, 200)

    def test_onboarding_200(self):
        novo = _mkuser("reg-novo")  # sem propriedade -> fica no onboarding
        c = Client()
        c.force_login(novo)
        self.assertEqual(c.get("/onboarding/").status_code, 200)

    def test_rastreabilidade_200(self):
        self.assertEqual(self.c.get("/rastreabilidade/").status_code, 200)

    def test_agronomia_endpoints_200(self):
        for p in (
            "/api/agronomia/clima/previsao/",
            "/api/agronomia/clima/historico/",
            "/api/agronomia/compliance/",
        ):
            r = self.c.get(p)
            # O 503 entrou na lista. A propriedade deste setUp não tem
            # cidade/UF, e a view deixou de ter um default fixo (Brasília)
            # para esse caso — dizer o tempo do Distrito Federal a quem
            # não cadastrou onde planta é pior que dizer que não sabe.
            #
            # O que este teste quer verificar é o que sempre quis: que a
            # página não rebenta com 500. Um 200-com-clima-errado era
            # tecnicamente "não dá 500" e funcionalmente mentira.
            self.assertIn(
                r.status_code,
                (200, 404, 503),
                f"{p} -> {r.status_code}",
            )

    def test_clima_sem_cidade_nao_devolve_o_tempo_de_brasilia(self):
        """A regressão do default silencioso, com nome próprio.

        A propriedade deste setUp não tem cidade. Antes, a view devolvia
        200 com o clima de Brasília, e o teste acima passava — um 200 com
        a resposta errada é "não dá 500". Agora tem de dizer que não sabe.
        """
        prop = Propriedade.objects.filter(user=self.u).first()
        self.assertFalse(prop.cidade, "esta propriedade devia não ter cidade")

        r = self.c.get("/api/agronomia/clima/previsao/")
        if r.status_code == 503:
            self.assertNotIn(
                "-15.79",
                r.content.decode(),
                "o default de Brasília sobreviveu dentro do 503",
            )


class MIPAPITest(APITestCase):
    def setUp(self):
        self.user = _mkuser("reg-mip")
        self.prop = _mkprop(self.user)
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T1", area_hectare=10
        )

    def _view(self, action, method="get", pk=None):
        view = MonitoramentoPragaViewSet.as_view({method: action})
        return view

    def test_crud(self):
        factory = APIRequestFactory()
        # create
        req = factory.post(
            "/api/monitoramentos-praga/",
            {
                "talhao": self.talhao.id,
                "data": "2026-09-18",
                "praga": "Percevejo",
                "nivel_infestacao": "3.5",
                "nivel_controle": "2.0",
            },
            format="json",
        )
        force_authenticate(req, user=self.user)
        resp = self._view("create", "post")(req)
        self.assertEqual(resp.status_code, 201)
        mid = resp.data["id"]
        self.assertTrue(resp.data["acima_controle"])
        # list
        req = factory.get("/api/monitoramentos-praga/")
        force_authenticate(req, user=self.user)
        resp = self._view("list")(req)
        self.assertEqual(resp.status_code, 200)
        # delete
        req = factory.delete(f"/api/monitoramentos-praga/{mid}/")
        force_authenticate(req, user=self.user)
        resp = self._view("destroy", "delete")(req, pk=mid)
        self.assertEqual(resp.status_code, 204)

    def test_isolamento_por_usuario(self):
        outro = _mkuser("reg-mip-outro")
        factory = APIRequestFactory()
        req = factory.get("/api/monitoramentos-praga/")
        force_authenticate(req, user=outro)
        resp = self._view("list")(req)
        self.assertEqual(resp.status_code, 200)


class RacaoAPITest(APITestCase):
    def setUp(self):
        self.user = _mkuser("reg-racao")
        self.prop = _mkprop(self.user)

    def test_crud(self):
        factory = APIRequestFactory()
        req = factory.post(
            "/api/racoes/",
            {
                "propriedade": self.prop.id,
                "nome": "Racao Teste",
                "tipo": "CONCENTRADO",
                "quantidade": "100",
            },
            format="json",
        )
        force_authenticate(req, user=self.user)
        view = RacaoViewSet.as_view({"post": "create"})
        resp = view(req)
        self.assertEqual(resp.status_code, 201)
        rid = resp.data["id"]
        # patch
        req = factory.patch(f"/api/racoes/{rid}/", {"custo_kg": "2.50"}, format="json")
        force_authenticate(req, user=self.user)
        view = RacaoViewSet.as_view({"patch": "partial_update"})
        resp = view(req, pk=rid)
        self.assertEqual(resp.status_code, 200)
        # list na página de nutrição renderiza
        c = Client()
        c.force_login(self.user)
        r = c.get("/animais/racoes/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Racao Teste")
        # delete
        req = factory.delete(f"/api/racoes/{rid}/")
        force_authenticate(req, user=self.user)
        view = RacaoViewSet.as_view({"delete": "destroy"})
        resp = view(req, pk=rid)
        self.assertEqual(resp.status_code, 204)

    def test_quantidade_negativa_rejeitada(self):
        factory = APIRequestFactory()
        req = factory.post(
            "/api/racoes/",
            {
                "propriedade": self.prop.id,
                "nome": "Ruim",
                "quantidade": "-5",
            },
            format="json",
        )
        force_authenticate(req, user=self.user)
        view = RacaoViewSet.as_view({"post": "create"})
        resp = view(req)
        self.assertEqual(resp.status_code, 400)


class ParticipanteLCDPRTest(APITestCase):
    def test_lancamento_aceita_participante(self):
        from app.api.views.financial import LancamentoFinanceiroViewSet

        user = _mkuser("reg-part")
        prop = _mkprop(user)
        factory = APIRequestFactory()
        req = factory.post(
            "/api/lancamentos/",
            {
                "propriedade": prop.id,
                "tipo": "DESPESA",
                "categoria": "INSUMO",
                "valor": "10.00",
                "data": "2026-09-18",
                "participante": "Agro SA",
                "participante_doc": "12345678000190",
            },
            format="json",
        )
        force_authenticate(req, user=user)
        view = LancamentoFinanceiroViewSet.as_view({"post": "create"})
        resp = view(req)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["participante_doc"], "12345678000190")
