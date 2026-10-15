"""O caminho de FALHA do tenancy, EXECUTADO — nao lido.

Os testes de `test_tenancy_fail_closed.py` leem o fonte e conferem que a
palavra `status=503` existe. Isso apanha alguem que troque o status, mas
NAO apanha um `OperationalError` que nao chegue ao `except`, nem um
`get_response` chamado antes da verificacao.

Este teste EXECUTA o caminho: uma base que rebenta a meio da verificacao,
e uma flag que diz se o pedido chegou alguma vez a chamar a view.

O QUE ESTE TESTE TRAVA
======================
O que aconteceu em 2026-10-05: cinco migrations por fazer fzeram o codigo
pedir `cod_municipio` a uma base sem a coluna. O `OperationalError` foi
engolido e o pedido seguiu SEM verificacao nenhuma. O log dizia
"cross-tenant pode passar" e ninguem o leu.

A versao anterior disto registava o erro e passava. A de agora recusa com
503. Este teste FALHA se voltar a passar — e a falha diz exactamente o que
significa, porque um teste que so diz "assert False" nao ajuda ninguem a
descobrir porque.
"""

import json
from unittest import mock

from django.contrib.auth.models import User
from django.db.utils import OperationalError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from app import models as _m
from app.middleware import TenantIsolationMiddleware


class TenancyFalhaExecutadaTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("produtor_a", password="x")
        self.rf = RequestFactory()
        self.passou = False
        self.mw = TenantIsolationMiddleware(self._view)

    def _view(self, request):
        """A view. Se esta funcao for chamada, o pedido chegou ao fim."""
        self.passou = True
        return HttpResponse("view")

    def _pedido(self):
        req = self.rf.get(f"/api/dashboard/?propriedade_id={self.u.pk}")
        req.user = self.u
        return req

    # ------------------------------------------------------------------
    def test_pedido_legitimo_passa(self):
        """O caminho feliz tem de continuar a passar.

        Fail-closed que recusa tudo nao e' fail-closed: e' o sistema
        partido, que e' o outro extremo do mesmo erro de desenho.
        """
        resp = self.mw(self._pedido())
        self.assertTrue(self.passou, "um pedido legitimo nao chegou a view")
        self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------
    def test_base_partida_da_503_e_nao_passa(self):
        """A prova que interessa.

        Uma coluna em falta na base e' o modo de falha real — e nao uma
        excepcao exotica: e' o que acontece quando ha migrations por
        aplicar, que e' o estado normal de um sistema em竂construcao.

        O pedido tem de ser RECUSADO, e nao seguir sem verificacao.
        """

        def explodir(*args, **kwargs):
            raise OperationalError("no such column: app_propriedade.cod_municipio")

        with (
            mock.patch.object(_m.Propriedade.objects, "filter", side_effect=explodir),
            self.assertLogs("app.middleware", level="ERROR") as logs,
        ):
            resp = self.mw(self._pedido())

        self.assertFalse(
            self.passou,
            "O PEDIDO PASSOU SEM VERIFICACAO DE TENANCY. Com a base "
            "partida, isto e' uma fuga de dados entre produtores — o modo "
            "de falha mais caro que existe neste ficheiro.",
        )
        self.assertEqual(
            resp.status_code,
            503,
            "a falha de base tem de ser 503. Um 200 aqui e' 'confia em mim'.",
        )
        self.assertTrue(
            any("cross-tenant pode passar" in l for l in logs.output),
            "o log tem de dizer que a versao fail-open passaria dados de "
            "outro produtor. E' o aviso que impede isto de voltar a ser "
            "estranho.",
        )

    # ------------------------------------------------------------------
    def test_o_503_diz_indisponivel_e_nao_acusa_o_vizinho(self):
        """A mensagem nao pode acusar o vizinho.

        Se disser "nao pertence ao utilizador", o produtor culpa o vizinho
        por um problema de migracao nosso. Custa horas a descobrir.
        """

        def explodir(*args, **kwargs):
            raise OperationalError("no such column: x")

        with (
            mock.patch.object(_m.Propriedade.objects, "filter", side_effect=explodir),
            self.assertLogs("app.middleware", level="ERROR"),
        ):
            resp = self.mw(self._pedido())

        corpo = json.loads(resp.content.decode("utf-8"))
        msg = corpo["error"]
        self.assertIn("indisponivel", msg.lower())
        for acusacao in ("nao pertence", "outro utilizador", "outro produtor"):
            self.assertNotIn(
                acusacao,
                msg.lower(),
                f"o 503 acusa o vizinho: {acusacao!r}. A falha e' nossa.",
            )
