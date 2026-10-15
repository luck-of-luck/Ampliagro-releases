"""O dashboard nao pode ler a sessao a partir de um cookie HTTP-only.

ESTE E' O BUG MAIS GRAVE QUE JA MEDI NESTE REPO
===============================================
MEDIDO no browser com uma sessao valida (`demo.muzambinho`, uid 60,
1 propriedade, 7 safras, 12 lancamentos):

    document.cookie ............  "csrftoken"   (so este)
    getCookie('sessionid') ......  null
    hasWidgetSession() ..........  false
    /api/dashboard/ .............  NUNCA chamada
    window.dashboardData ........  null
    window.widgetDataCache ......  null

O PRODUTOR VIA "sem dado" EM TUDO.

A CAUSA
=======
`config/settings/base.py` tem

    SESSION_COOKIE_HTTPONLY = True     # o default do Django, e' o certo
    CSRF_COOKIE_HTTPONLY    = False

Um cookie HTTP-only nao e' legivel por `document.cookie` — por desenho, e
e' o que o torna seguro contra XSS. Logo `getCookie('sessionid')` **nunca**
devolve nada, e `hasWidgetSession()` era `false` **para todos os
utilizadores autenticados, sempre**. Nao e' um caso raro nem uma condicao
de corrida: e' uma constante.

O EFEITO ERA SILENCIOSO
======================
Os guardas `if (!hasWidgetSession()) return` faziam o fetch do payload NAO
correr. `dashboardData` ficava `null`, e cada widget caia no ramo "sem
dado". Sem erro, sem 403, sem nada no console — e "sem dado" e'
indistinguivel de "o produtor nao tem nada". Um produtor com 85,6 ha
cadastrados via um painel que dizia que nao|area nenhuma.

POR QUE A CORRECCAO ANTERIOR NAO CHEGOU
=======================================
MEDIDO 2026-10-04, na propria funcao: testava `sessionid || csrftoken`. O
`csrftoken` e' emitido pelo `{% csrf_token %}` ANTES de qualquer login, e
por isso um visitante anonimo contava como sessao — e os guardas de
`saveWidgetsLayout` nunca protegiam ninguem (POST 403 a cada re-render,
engolido por `.catch(function(){})`).

A correccao trocou para so `sessionid`. Resolveu o anonimo e **partiu o
autenticado**: `sessionid` nao e' visivel. Trocar um sinal inutil por um
inalcancavel troca um bug por um pior — e ambos silenciosos.

A CORRECCAO
===========
O sinal vem de onde e' verdade: o SERVIDOR. `base.html` poe
`data-authenticated` no `<body>`, preenchido por `user.is_authenticated` —
o mesmo valor que ja desvia o nome no menu. Ordem das fontes:

  1. `data-authenticated`     — o servidor, sem ambiguidade
  2. `AMPLIAGRO_UID`          — ausente em anonimo
  3. `getCookie('sessionid')` — so se SESSION_COOKIE_HTTPONLY passar a
     False. Hoje nunca. Fica por compatibilidade, nao por confianca.

MEDIDO DEPOIS DA CORRECCAO, no mesmo browser:

    hasWidgetSession() .......  true
    /api/dashboard/ ..........  200   (antes: nunca)
    /api/widget-data/ ........  200   (antes: nunca)
    kpi-area .................  85,6 ha        (antes: "sem dado")
    kpi-caixa ................  R$ 853.000,00  (antes: "sem dado")
    kpi-roi ..................  459,1%         (antes: "sem dado")
    kpi-custo ................  R$ 2.170,56    (antes: "sem dado")
    kpi-funcionarios .........  2 ativos       (antes: "sem dado")
    "sem dado" na pagina .....  2              (antes: 13)

UMA NOTA SOBRE ESTES TESTES
===========================
A primeira versao media as posicoes no texto CRU e falhava: a funcao tem
um comentario longo, e a PROSA menciona `getCookie('sessionid')` antes de
mencionar `data-authenticated`. O teste media a ordem em que eu escrevi a
explicacao, nao a ordem em que o codigo corre.

E' o mesmo erro duas vezes nesta sessao: medir pelo conversor em vez dos
bytes, e procurar uma cadeia lida de uma captura de ecra. Um teste mede
ONDE O CODIGO ESTA, nao onde o texto esta escrito. Por isso
`_corpo_sem_comentarios()` remove a prosa antes de medir.
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
JS = RAIZ / "app" / "static" / "js" / "pagina-index.js"
BASE = RAIZ / "app" / "templates" / "base.html"
SETTINGS = RAIZ / "config" / "settings" / "base.py"


def corpo_sem_comentarios(js):
    """O corpo de `hasWidgetSession()` com a prosa removida."""
    m = re.search(
        r"window\.hasWidgetSession\s*=\s*function\s*\(\)\s*\{(.*?)\n\};",
        js,
        re.S,
    )
    if not m:
        return None
    corpo = m.group(1)
    corpo = re.sub(r"/\*.*?\*/", "", corpo, flags=re.S)
    corpo = re.sub(r"^\s*//.*$", "", corpo, flags=re.M)
    return re.sub(r"[ \t]+", " ", corpo)


class SessaoHttpOnlyTest(unittest.TestCase):
    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")
        self.base = BASE.read_text(encoding="utf-8")
        self.corpo = corpo_sem_comentarios(self.js)
        self.assertIsNotNone(self.corpo, "nao encontrei window.hasWidgetSession no JS")

    # ------------------------------------------------------------------
    # O SERVIDOR TEM DE EXPOR O SINAL
    # ------------------------------------------------------------------
    def test_o_template_expoe_a_flag_de_autenticacao(self):
        self.assertIn(
            "data-authenticated",
            self.base,
            "`base.html` nao expoe `data-authenticated` no <body>. Sem a flag "
            "o JS so pode tentar ler o cookie http-only, invisivel por "
            "desenho.",
        )
        m = re.search(r'data-authenticated="([^"]*)"', self.base)
        self.assertIsNotNone(m, "o atributo existe mas sem valor")
        self.assertIn(
            "user.is_authenticated",
            m.group(1),
            "a flag tem de vir de `user.is_authenticated` — a unica fonte "
            "que sabe. MEDIDO: com sessao devolve '1', sem sessao '0'.",
        )

    # ------------------------------------------------------------------
    # A ORDEM DAS FONTES
    # ------------------------------------------------------------------
    def test_has_widget_session_consulta_a_flag_do_servidor(self):
        self.assertIn(
            "data-authenticated",
            self.corpo,
            "`hasWidgetSession()` nao le `data-authenticated`. Continua a "
            "depender do cookie http-only, que `document.cookie` nunca ve. "
            "O dashboard fica vazio para todos os utilizadores.",
        )

    def test_a_flag_vem_antes_de_qualquer_cookie(self):
        i = self.corpo.find("data-authenticated")
        j = self.corpo.find("getCookie(")
        self.assertTrue(i != -1, "a flag do servidor nao e' lida")
        self.assertLess(
            i,
            j,
            "a flag do servidor tem de vir antes de QUALQUER getCookie(). "
            "O `csrftoken` e' emitido ANTES do login — usa-lo como sinal de "
            "sessao faz um visitante anonimo passar por utilizador. E o "
            "`sessionid` e' http-only e devolve sempre null.",
        )

    def test_nenhum_return_false_antes_da_flag(self):
        i = self.corpo.find("data-authenticated")
        j = self.corpo.find("return false")
        if j != -1:
            self.assertGreater(
                j,
                i,
                "ha um `return false` ANTES de a flag ser lida. A flag e' "
                "consultada e o resultado descartado — que e' o mesmo bug "
                "com mais codigo.",
            )

    # ------------------------------------------------------------------
    # O QUE MOTIVOU A MUDANCA
    # ------------------------------------------------------------------
    def test_o_sessionid_continua_http_only(self):
        """Fixa o QUE motivou a correccao.

        Se alguem mudar isto para False, `hasWidgetSession()` volta a ter um
        sinal legivel — mas perde-se a proteccao do cookie de sessao contra
        XSS. A decisao de seguranca nao e' incidental: se mudar, este teste
        avisa e a decisao tem de ser tomada de proposito.
        """
        s = SETTINGS.read_text(encoding="utf-8")
        m = re.search(r"SESSION_COOKIE_HTTPONLY\s*=\s*(\w+)", s)
        self.assertIsNotNone(
            m,
            "SESSION_COOKIE_HTTPONLY sumiu dos settings — a correccao do JS "
            "assume que o cookie NAO e' legivel",
        )
        self.assertEqual(
            m.group(1),
            "True",
            "SESSION_COOKIE_HTTPONLY passou a %s. O JS ja nao depende do "
            "cookie (le a flag do servidor), mas mudar isto expoe o cookie "
            "de sessao a JavaScript e a XSS." % m.group(1),
        )


if __name__ == "__main__":
    unittest.main()
