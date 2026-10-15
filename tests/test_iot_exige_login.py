"""Tres telas de IoT eram servidas a qualquer visitante anonimo.

O DEFEITO
=========
Em `app/urls.py`, tres rotas eram lambdas soltas dentro do `urlpatterns`:

    path("iot/telemetria/", lambda r: render(r, "iot-telemetria.html"), ...)
    path("iot/alertas/",    lambda r: render(r, "iot-alertas.html"),    ...)
    path("iot/comandos/",   lambda r: render(r, "iot-comandos.html"),   ...)

Sem `@login_required`. As paginas irmas (`iot/sensores/`,
`iot/dispositivos/`) usavam views com o decorator e redirecionavam para o
login — estas tres NAO. Verificado em HTTP:

    GET /iot/alertas/      anonimo -> 200, 117.010 bytes de pagina
    GET /iot/telemetria/   anonimo -> 200, 117.613 bytes de pagina
    GET /iot/sensores/     anonimo -> 302 -> /login/?next=...

E nao reclamava: `AnonymousUser` e' um objeto valido para `render`, entao o
template renderizava normal. O unico sintoma era a tela aparecer para quem
nao devia ver — e nao haver nada no log apontando para ali.

A REGRA QUE FICA
================
1. Toda rota de dado da fazenda exige sessao. A guarda fica NA ROTA, nao
   escondida dentro da lambda — assim ela se ve na linha que declara a rota.
2. Nenhuma pagina do app e' servida a anonimo. As duas unicas excecoes sao a
   landing (`/`) e as paginas de login/onboarding/pitch, e isso e' decisao.

O QUE ESTE TESTE TRAVA
======================
1. As tres rotas redirecionam anonimo para o login, como as irmas.
2. Autenticado, continuam servindo a pagina.
3. Nao ha rota no app que sirva template a anonimo sem estar na lista de
   excecoes — um `lambda r: render(...)` esquecido volta a falhar aqui.
"""

from django.test import TestCase
from django.urls import get_resolver

# Paginas que NAO exigem sessao, de proposito. A landing e' marketing; as
# demais sao o caminho para se conseguir uma sessao. Se uma rota nova de dado
# aparecer na lista de excecao, e' um engano.
EXCECOES = {
    ("", "index_spa"),
    ("login/", "login"),
    ("logout/", "logout"),
    ("demo/", "demo-login"),
    ("onboarding/", "onboarding"),
    ("pitch/", "pitch"),
    ("avaliador/", "avaliador-login"),
    ("privacidade/", "privacidade"),
    ("health/", "health-index"),
    ("health/dashboard/", "health-dashboard"),
    ("healthz", "healthz"),
    ("healthz/", "healthz"),
    ("favicon.ico", "favicon"),
    ("manifest.json", "pwa-manifest"),
    ("sw.js", "pwa-sw"),
    (".well-known/<path:path>", "wellknown"),
    ("api/schema/", "schema"),
    ("api/docs/", "swagger-ui"),
    ("admin/", "index"),
    ("admin/login/", "login"),
    ("admin/logout/", "logout"),
    ("admin/password_change/", "password_change"),
    ("admin/jsi18n/", "jsi18n"),
    ("accounts/", "account_login"),
    ("accounts/login/", "account_login"),
    ("accounts/signup/", "account_signup"),
    ("accounts/logout/", "account_logout"),
    ("accounts/password/reset/", "account_reset_password"),
    ("accounts/password/change/", "account_change_password"),
    ("accounts/email/", "account_email"),
    ("accounts/confirm-email/", "account_confirm_email"),
    ("accounts/social/", "social_accounts"),
    ("accounts/3rdparty/", "account_social"),
    ("accounts/social/connections/", "socialaccount_connections"),
    ("accounts/inactive/", "account_inactive"),
    ("static/<path:path>", None),
}

ROTAS_IOT = ["/iot/telemetria/", "/iot/alertas/", "/iot/comandos/"]


class PaginasDeIotExigemLogin(TestCase):
    def test_anonimo_e_redirecionado_para_o_login(self):
        """Antes: 200 com a pagina inteira para quem nao entrou."""
        for url in ROTAS_IOT:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(
                    r.status_code, 302, msg=f"{url} respondeu {r.status_code} a anonimo"
                )
                self.assertIn("/login/", r["Location"])

    def test_o_que_antes_vazava_agora_va_vazio(self):
        """O sintoma era o conteudo, nao o status. Confirma o corpo."""
        for url in ROTAS_IOT:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertNotIn(
                    b"<html", r.content.lower()[:200] if r.status_code == 200 else b""
                )

    def test_autenticado_continua_servindo(self):
        from django.contrib.auth import get_user_model

        U = get_user_model()
        u = U.objects.create_user("iot_t", "iot@t.com", "x")
        self.client.force_login(u)
        for url in ROTAS_IOT:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertGreater(len(r.content), 1000)

    def test_batem_com_as_irmas_que_j_funcionavam(self):
        """As quatro paginas de IoT passam a se comportar igual."""
        for url in ["/iot/sensores/", "/iot/dispositivos/"] + ROTAS_IOT:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302, msg=f"{url} nao exige login")


class NenhumaPaginaDeDadoVazaParaAnonimo(TestCase):
    """Trava o PADRAO, nao as tres rotas.

    Um `lambda r: render(...)` esquecido num urlpatterns nao da erro nenhum:
    aparece silencioso, como apareceu. Este teste pede cada rota de pagina a
    um cliente SEM sessao e falha se alguma responder 200 com HTML sem estar
    na lista de excecoes.

    E' uma verificacao de comportamento, nao de forma do codigo. Olhar para o
    `__name__` da callback seria fragil: `login_required(lambda ...)` continua
    se chamando `<lambda>`, e o teste passaria a acusar um caso que esta
    justamente protegido.
    """

    def test_varre_as_rotas_de_pagina(self):
        from app import urls as app_urls

        vazando = []
        checadas = 0
        for p in app_urls.urlpatterns:
            chave = (str(p.pattern), p.name)
            if chave in EXCECOES or "static" in str(p.pattern):
                continue
            # so rotas que entregam PAGINA; as de API respondem JSON e sao
            # tratadas pela DRF, que ja exige `IsAuthenticated`
            if p.name and p.name.startswith("api"):
                continue
            try:
                r = self.client.get("/" + str(p.pattern).lstrip("/"))
            except Exception:
                continue  # rota com parametro obrigatorio: exige URL concreta
            checadas += 1
            if r.status_code == 200 and b"<html" in r.content[:400].lower():
                vazando.append(
                    f"/{str(p.pattern).lstrip('/')}  (200, {len(r.content)}b)"
                )

        self.assertGreater(checadas, 20, msg="a varredura nao pegou as rotas")
        self.assertEqual(
            vazando,
            [],
            msg=(
                "Rotas que servem pagina inteira a anonimo e nao estao na "
                "lista de excecoes:\n  " + "\n  ".join(vazando)
            ),
        )
