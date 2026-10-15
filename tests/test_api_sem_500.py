"""Nenhuma rota /api/ pode responder 500 a um pedido normal.

MEDIDO 2026-10-04: `/api/agenda-analises/` devolvia HTTP 500 em **todos** os
pedidos, por um import local que apontava um nivel abaixo
(`app/api/views/kanban.py:74`, `from .serializers import ...`, que dentro de
`app/api/views/` resolve para `app.api.views.serializers` — modulo que nao
existe). Nenhum teste apanhou.

PORQUE UM TESTE DE FUMACA E NAO UM TESTE DESTA VIEW
---------------------------------------------------
O que se quer apanhar nao e "esta view tem os campos certos", e "nenhuma rota
rebenta". Um `ImportError` dentro do corpo de uma view so aparece quando a view
corre — e as sondas que existem medem outra coisa: o
`tests/test_superficie_servidor.py` varre 377 URLs e conta **estados de
resposta**, mas a pergunta que faz e "vazou dados?". Um 500 entra na contagem de
`status` e passa, porque o teste nunca pergunta "respondeu?".

Este e o contrapeso: responde a pergunta que a sonda de superficie nao faz.

O QUE NAO ESTE TESTE FAZ
------------------------
Nao afirma que a rota esta certa — so que nao rebenta. Um 200 com `{}` passa.
Rotas com dependencia externa ficam de fora: o clima sem fonte devolve 503, e
uma exceccao de third-party transformada em 500 por
`raise_request_exception=False` seria um falso positivo.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import PerfilUsuario, Propriedade

#: Rotas sem rede externa. O clima fica de fora de proposito (503 sem fonte).
ROTAS = [
    "/api/agenda-analises/",
    "/api/agenda/",
    "/api/estoque/",
    "/api/pecuaria/",
    "/api/maquinarios/",
    "/api/funcionarios-resumo/",
    "/api/leituras-sensor/",
    "/api/dashboard/",
    "/api/financeiro/",
    "/api/perfil/",
    "/api/talhoes-por-propriedade/",
    "/api/servidor/config/",
]


class Nenhum500NaApiTest(TestCase):
    """Cada rota responde, ou recusa com motivo. Nunca rebenta."""

    def setUp(self):
        self.user = User.objects.create_user(username="fumo500", password="x1234567")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Fumo", area_total=10, uf="MT", cidade="X"
        )
        PerfilUsuario.objects.update_or_create(
            user=self.user,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "CAMPO",
                "propriedade_vinculada": self.prop,
            },
        )
        self.client = Client(raise_request_exception=False)
        self.client.force_login(self.user)

    def test_nenhuma_rota_responde_500(self):
        rebentadas = {}
        for url in ROTAS:
            r = self.client.get(url)
            if r.status_code >= 500:
                rebentadas[url] = r.status_code

        self.assertEqual(
            rebentadas,
            {},
            "Rotas /api/ a responder 500. Um import errado dentro do corpo de "
            "uma view so aparece no request — e as sondas que existem medem "
            "vazamento de dados, nao resposta:\n  "
            + "\n  ".join(f"{u} -> {s}" for u, s in sorted(rebentadas.items())),
        )

    def test_agenda_de_analises_responde(self):
        """
        A regressao concreta, com nome. `agenda_analises_data` tinha
        `from .serializers import SafraSerializer, TalhaoSerializer`, que
        resolve para `app.api.views.serializers` — modulo inexistente. O
        `reverse()` desta rota funciona, o `urls.py` aponta para ela, e nada
        falha ate ao request. Por isso o teste e pelo STATUS, e nao pela view.
        """
        r = self.client.get("/api/agenda-analises/")

        self.assertNotEqual(
            r.status_code,
            500,
            f"`/api/agenda-analises/` voltou a dar 500: {r.content[:200]}",
        )
        self.assertIn(
            r.status_code,
            (200, 403),
            f"Resposta inesperada ({r.status_code}). Um 401/404 aqui significa que a "
            f"rota mudou de nome e este teste ficou a medir nada: {r.content[:120]}",
        )
