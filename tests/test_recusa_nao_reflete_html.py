"""A recusa de tenancy nao pode reflectir HTML.

O QUE ESTE TESTE TRAVA
======================
`TenantIsolationMiddleware._rejeitar` responde de duas maneiras:

  `/api/...`   -> `JsonResponse`         (escapa JSON)
  outros       -> `HttpResponseForbidden` (NAO escapa — MEDIDO)

`HttpResponseForbidden` mete o texto no corpo tal e qual. Um `<script>`
na mensagem chega intacto ao browser.

HOJE ISTO NAO E' EXPLORAVEL
===========================
E' importante dizer isto com clareza, porque um achado que se|autocorrige
antes de ser explorado nao e' o mesmo que um achado numa parede:

  - o texto de 403 vem de `param`, uma chave de `TABELAS_VERIFICADAS` —
    codigo nosso, nao input do utilizador;
  - o texto de 503 so mete `type(exc).__name__`, porque `OperationalError`
    nao tem atributo `.name` (medido: cai sempre no nome da classe).

Ou seja: a seguranca actual depende de uma coisa que ninguem escreveu para
ser uma condicao de seguranca. Se o Django passar a expor `.name` — e
`.name` traz texto do driver, que traz o nome da coluna que o codigo
pediu — a reflexao aparece sem ninguem editar uma linha deste ficheiro.

Por isso o `escape` fica. Custa uma linha e fecha a classe.

O QUE ESTE TESTE NAO AFIRMA
===========================
Nao afirma que houve uma vulnerabilidade explorada. Afirma que a recusa
nao devolve HTML cru, para que a proxima mensagem que alguem escrever
nao possa ser uma via de XSS por acidente.
"""

import json

from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from django.test import RequestFactory, TestCase

from app.middleware import TenantIsolationMiddleware

PAYLOAD = "<script>alert('xss')</script>"
OUTRO_PAYLOAD = '"><img src=x onerror=alert(1)>'


class RecusaNaoRefleteHtmlTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("p", password="x")
        self.rf = RequestFactory()

    def _fora_da_api(self):
        req = self.rf.get("/painel/")
        req.user = self.u
        return req

    # ------------------------------------------------------------------
    def test_a_recusa_fora_da_api_nao_devolve_o_script_intacto(self):
        """O `<script>` na pode chegar cru ao browser."""
        resp = HttpResponseForbidden(PAYLOAD)
        self.assertTrue(
            PAYLOAD in resp.content.decode(),
            "pre-condicao: HttpResponseForbidden NAO escapa. Se isto deixar "
            "de ser verdade, o `escape` do `_rejeitar` pode ser removido — "
            "mas so depois de o medir.",
        )
        # e portanto o `_rejeitar` tem de escapar:
        mw = TenantIsolationMiddleware(lambda r: None)
        escapado = mw._rejeitar(self._fora_da_api(), PAYLOAD, status=403)
        corpo = escapado.content.decode()
        self.assertNotIn(
            "<script>",
            corpo,
            "a recusa devolveu HTML cru. O texto da mensagem entrou no "
            "browser sem escape.",
        )
        self.assertIn("&lt;script&gt;", corpo)

    # ------------------------------------------------------------------
    def test_a_recusa_na_api_continua_a_ser_json_valido(self):
        """O caminho `/api/` nao pode ser estragado pelo escape.

        Escapar duas vezes mostra `&lt;` ao utilizador, e um cliente que
        le JSON recebe uma mensagem corrompida. Este teste existe para
        dizer que o `escape` e' SÓ no caminho HTML.
        """
        mw = TenantIsolationMiddleware(lambda r: None)
        req = self.rf.get("/api/dashboard/")
        req.user = self.u
        resp = mw._rejeitar(req, PAYLOAD, status=403)
        corpo = json.loads(resp.content.decode("utf-8"))
        self.assertEqual(corpo["error"], PAYLOAD, "o JSON alterou-se")
        self.assertNotIn(
            "&lt;",
            resp.content.decode("utf-8"),
            "o JSON foi escapado duas vezes. `JsonResponse` ja escapa.",
        )

    # ------------------------------------------------------------------
    def test_a_mensagem_que_o_produtor_le_continua_util(self):
        """Escapar nao pode transformar a mensagem em ruido.

        `&amp;` onde o produtor queria ler "e" e' um custo de legibilidade
        que eles nao entendem. O texto tem de continuar legivel E
        seguro.
        """
        mw = TenantIsolationMiddleware(lambda r: None)
        msg = "Verificacao de propriedade indisponivel (OperationalError)."
        resp = mw._rejeitar(self._fora_da_api(), msg, status=503)
        corpo = resp.content.decode()
        self.assertEqual(corpo, msg)
        # NOTA: o caminho nao-api devolve 403 (HttpResponseForbidden e' fixo
        # em 403). O `status=503` que este teste passa e' o que o
        # middleware FAZ no caminho autenticado quando a base rebenta —
        # ver `test_tenancy_da_503_real.py`, que exercise esse caminho de
        # verdade com a base a rebentar. Aqui so interessa que a mensagem
        # continua legivel depois de escapada.
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------------------------------
    def test_varios_payloads_nao_passam(self):
        """Nao e' so `<script>`. Fecha as duas formas mais comuns."""
        mw = TenantIsolationMiddleware(lambda r: None)
        for payload in (PAYLOAD, OUTRO_PAYLOAD, "<img src=x onerror=alert(1)>"):
            with self.subTest(payload=payload):
                resp = mw._rejeitar(self._fora_da_api(), payload, status=403)
                corpo = resp.content.decode()
                self.assertNotIn("<", corpo)
                self.assertNotIn(">", corpo)
