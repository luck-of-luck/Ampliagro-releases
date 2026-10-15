"""O `?next=` do login: dois defeitos, um deles um 500 DEPOIS de autenticar.

Porque este ficheiro existe
===========================
O dashboard manda o produtor para `/login/?next=...` quando a sessao morre a
meio do uso (`hasWidgetSession` + o redirect em `app/templates/index.html`).
Isto e' o unico caminho que leva a pessoa de volta a pagina de onde saiu — e
nada o testava. MEDIDO, 2026-10-04, os dois ramos estavam partidos:

**1. `next` nunca chegava ao template.** `login.html:96-97` e `159-160` tem
`{% if next %}` e um `<input type="hidden" name="next">`. Mas o contexto final
de `login_view` so levava `erro_login`. A variavel nunca chegava, o hidden
nunca era desenhado, e o `?next=/guias/` era descartado: o produtor entrava, o
login funcionava, e aterrava em `/` em vez de voltar aos guias. Um campo hidden
que nunca e' renderizado e' um template que mente sobre o que faz.

**2. `next` sem barra inicial dava 500 DEPOIS do login funcionar.**
`_next_seguro` confiava so em `url_has_allowed_host_and_scheme`, que e' uma
checagem de HOST e nao de CAMINHO. Ela aceita `guias`, `%2F` e `%2Fguias%2F`:
nao sao URLs de outro dominio, logo passam. Mas `redirect()` chama
`resolve_url()`, que para uma string que nao comeca por `/` tenta `reverse()`
como se fosse o NOME DE UMA VIEW — e `NoReverseMatch` explode. Medido:

    next=/              -> 302 /
    next=/guias/        -> 302 /guias/
    next=guias          -> 500 NoReverseMatch
    next=%2F            -> 500 NoReverseMatch
    next=%2Fguias%2F    -> 500 NoReverseMatch

O 500 so e' alcancado autenticado, o que e' o pior sitio possivel para um
erro: o login PARECE ter funcionado e o produtor fica numa pagina de falha sem
sessao util. E'e facil de alcanca por acidente, porque um `next` ja
percent-encoded chega assim — o browser reencaminha `?next=%2Fguias%2F` sem o
descodificar.

O QUE ESTE TESTE TRAVA
======================
1. `next` sobrevive ao ciclo completo: GET login -> hidden no form -> POST ->
   redirect para o caminho pedido. E' o que o dashboard depende.
2. Nenhum `next` produz 500. O login tem de ser ou redirecionar, ou mostrar o
   form com erro — nunca explodir.
3. Nenhum `next` faz open redirect. `//evil.com` e o truque `/\\evil.com`
   continuam barrados pela checagem de host; este ficheiro nao a substitui,
   vigia a complemento dela.
"""

import re

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Propriedade


def produtor(**kwargs):
    """Um User que CHEGA ao ramo do `next` em `login_view`.

    Nao e' um User qualquer: `auth.py:168` desvia para `/onboarding/` quem
    nao tem `propriedades`. Um produtor sem fazenda nunca chega ao
    `_next_seguro`, e um teste que passa por esse ramo sem o saber mede
    outra coisa — mediria o onboarding e daria 'verde' com o `next` partido.
    """
    user = User.objects.create_user(
        kwargs.pop("username", "next_probe"), "next@x.com", "Test1234!"
    )
    Propriedade.objects.create(user=user, nome="Fazenda do Teste", area_total=10)
    return user


#: `next` que tem de dar 302 para o proprio caminho.
CAMINHOS = ["/", "/guias/", "/guias/vegetal/"]

#: `next` que tem de cair no padrao `/`. Nenhum pode dar 500.
REJEITADOS = [
    "",  # ausente
    "guias",  # sem barra inicial -> nao e' caminho, e' nome de view
    "%2F",  # percent-encoded: o browser reencaminha assim
    "%2Fguias%2F",
    "//evil.com",  # host diferente
    "https://evil.com",  # esquema + host diferentes
    "/\\evil.com",  # o browser normaliza `\\` para `/` -> `//evil.com`
    "http://127.0.0.1:9999/",  # nem o proprio host, por outra porta
]


class NextSobreviveAoCicloCompletoTest(TestCase):
    """O que o dashboard depende: `?next=` tem de chegar ao redirect."""

    @classmethod
    def setUpTestData(cls):
        cls.user = produtor(username="next_probe")

    def test_o_hidden_next_e_desenhado_no_form(self):
        for caminho in CAMINHOS:
            with self.subTest(next=caminho):
                r = self.client.get("/login/", {"next": caminho})
                self.assertEqual(r.status_code, 200)
                html = r.content.decode("utf-8", "replace")
                self.assertRegex(
                    html,
                    rf'name="next"[^>]*value="{re.escape(caminho)}"',
                    msg=f"o form do login nao carrega next={caminho!r}. "
                    "Sem isto o produtor entra e aterra em '/' em vez de "
                    "voltar a pagina de onde saiu.",
                )

    def test_o_login_redireciona_para_o_next(self):
        for caminho in CAMINHOS:
            with self.subTest(next=caminho):
                # Cliente novo por caso: o login anterior deixa uma sessao.
                c = self.client_class()
                c.force_login(self.user)
                r = c.post(
                    "/login/",
                    {
                        "acao": "login",
                        "tipo_acesso": "produtor",
                        "usuario": self.user.username,
                        "senha": "Test1234!",
                        "next": caminho,
                    },
                )
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r["Location"], caminho)


class NextNuncaExplodeNemRedirecionaParaForaTest(TestCase):
    """Um `next` estragado da' 302 para `/`. Nunca 500, nunca `evil.com`."""

    @classmethod
    def setUpTestData(cls):
        cls.user = produtor(username="next_probe2")

    def test_nenhum_next_produz_500(self):
        """MEDIDO: `guias`, `%2F` e `%2Fguias%2F` davam NoReverseMatch.

        A checagem de host do Django aceita estes tres (nao sao URLs de outro
        host), e `redirect()` tratava-os como nome de view. Este e' o teste
        que pega nel.
        """
        # Aqui afirma-se so que NAO deu 500. O destino (302 para `/`) mede-se
        # em `test_nenhum_next_redireciona_para_fora_do_site`: um teste que
        # afirma as duas coisas falha com uma mensagem que ja nao diz qual
        # das duas foi.
        for bruto in REJEITADOS:
            with self.subTest(next=bruto):
                c = self.client_class()
                c.force_login(self.user)
                r = c.post(
                    "/login/",
                    {
                        "acao": "login",
                        "tipo_acesso": "produtor",
                        "usuario": self.user.username,
                        "senha": "Test1234!",
                        "next": bruto,
                    },
                )
                self.assertNotEqual(
                    r.status_code,
                    500,
                    msg=f"next={bruto!r} deu 500. O login tem de redirecionar "
                    "ou mostrar o form — um 500 aqui deixa o produtor numa "
                    "pagina de erro depois de o login ter funcionado.",
                )

    def test_nenhum_next_redireciona_para_fora_do_site(self):
        """Afirma o DESTINO, que e' o que a proteccao promete.

        `assertNotIn('evil.com', ...)` sozinho passa se a resposta for um 500
        sem Localizacao — e o 500 e' exactamente o defeito que este ficheiro
        veio travar. Por isso o 302 vem primeiro.
        """
        for bruto in REJEITADOS:
            with self.subTest(next=bruto):
                c = self.client_class()
                r = c.post(
                    "/login/",
                    {
                        "acao": "login",
                        "tipo_acesso": "produtor",
                        "usuario": self.user.username,
                        "senha": "Test1234!",
                        "next": bruto,
                    },
                )
                self.assertEqual(
                    r.status_code, 302, msg=f"next={bruto!r} nao redirecionou"
                )
                destino = r["Location"]
                self.assertEqual(
                    destino,
                    "/",
                    msg=f"next={bruto!r} foi para {destino!r} em vez do padrao",
                )

    def test_next_rejeitado_nao_volta_para_o_form(self):
        """O `next` que sobra no contexto tambem tem de estar limpo.

        Se o template renderizar `value="https://evil.com"`, o proximo POST
        reenvia esse valor — e a protecao passa a depender do browser. A
        decisao e'da view, nao do template.
        """
        for bruto in REJEITADOS:
            if bruto == "":
                continue
            with self.subTest(next=bruto):
                r = self.client.get("/login/", {"next": bruto})
                html = r.content.decode("utf-8", "replace")
                self.assertNotIn("evil.com", html)
                self.assertNotIn("9999", html)
