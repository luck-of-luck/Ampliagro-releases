"""Nenhum backend de autenticacao pode ficar sem `get_user`.

MEDIDO 2026-10-05. `config/settings/base.py` tinha

    AUTHENTICATION_BACKENDS = [
        "axes.backends.AxesStandaloneBackend",   # <-- NAO tem get_user
        "django.contrib.auth.backends.ModelBackend",
        "allauth.account.auth_backends.AuthenticationBackend",
    ]

MEDIDO, os dois MRO:

    AxesStandaloneBackend    -> [AxesStandaloneBackend, object]        sem get_user
    AxesBackend              -> [AxesBackend, AxesStandaloneBackend,
                                ModelBackend, BaseBackend]              com get_user

O QUE ACONTECE
==============
O Django, ao carregar uma sessao, faz

    backend = load_backend(request.session[BACKEND_SESSION_KEY])
    user = backend.get_user(user_id)

e o `BACKEND_SESSION_KEY` e' gravado no login como o PRIMEIRO backend que
devolveu um utilizador. Se for um backend sem `get_user`, o resultado e' um
500 em TODA a pagina:

    AttributeError: 'AxesStandaloneBackend' object has no attribute 'get_user'
    File "app/middleware.py", line 197, in __call__
        if user and getattr(user, "is_authenticated", False):

Hoje nao acontece: o Standalone devolve `None` de `authenticate()`, e quem
ganha o login e' o `ModelBackend` — MEDIDO, o backend gravado na sessao
apos um login real e' `django.contrib.auth.backends.ModelBackend`. E' por
isso que o sistema funciona.

E' uma BOMBA-RELOGIO, nao um bug activo: o dia em que o axes passar a
autenticar alguem (uma mudanca na configuracao do axes, uma versao
diferente, um `AXES_*` que deixe de devolver None), o utilizador fica com
500 em tudo e sem forma de se desenrascar. Nao ha como recuperar pela
interface.

A CORRECCAO
===========
`AxesBackend`, que e' o que a documentacao do django-axes manda usar:

  - herda o `authenticate` do `AxesStandaloneBackend` — o lockout de
    forca bruta continua exactamente igual
  - ganha o `get_user` do `ModelBackend` — a sessao passa a carregar

Trocar o backend nao troca a protecao; desfaz a bomba.

O QUE ESTE TESTE FAZ
====================
Nao substitui o teste de integracao (que precisa de um servidor). Verifica
o que e' estavel no ficheiro e o que medivel sem servidor:

  1. todo o backend da lista tem `get_user` (importando a classe de verdade)
  2. o lockout continua presente: o backend tem de herdar o `authenticate`
     do Standalone
  3. `AxesStandaloneBackend` nao volta para a lista — ela continua being
     usada como COMPONENTE do `AxesBackend`, que e' o uso certo

O teste 1 e' o que importa: e' exactamente a condicao que, se falhar, da
500.
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SETTINGS = RAIZ / "config" / "settings" / "base.py"


def backends_declarados():
    txt = SETTINGS.read_text(encoding="utf-8")
    m = re.search(r"AUTHENTICATION_BACKENDS\s*=\s*\[(.*?)\]", txt, re.S)
    assert m, "nao encontrei AUTHENTICATION_BACKENDS nos settings"
    return re.findall(r'"([^"]+)"', m.group(1))


class BackendDeAutenticacaoTest(unittest.TestCase):
    def test_todo_o_backend_tem_get_user(self):
        """A condicao que, se falhar, da 500 em todas as paginas."""
        from django.utils.module_loading import import_string

        sem = []
        for caminho in backends_declarados():
            try:
                cls = import_string(caminho)
            except Exception as e:  # noqa: BLE001
                sem.append("%s (nao importou: %s)" % (caminho, e))
                continue
            if not hasattr(cls, "get_user"):
                sem.append(caminho)

        self.assertEqual(
            sem,
            [],
            "estes backends de AUTHENTICATION_BACKENDS nao tem `get_user`: "
            "%s\n\n"
            "MEDIDO: `AxesStandaloneBackend` tem MRO `[AxesStandaloneBackend, "
            "object]` — so `authenticate()`. Ao carregar a sessao o Django "
            "faz `backend.get_user(user_id)` e o resultado e'\n\n"
            "    AttributeError: 'AxesStandaloneBackend' object has no "
            "attribute 'get_user'\n\n"
            "em TODA a pagina, porque a sessao guarda o PRIMEIRO backend que "
            "autenticou. Usar `AxesBackend`, que herda o `authenticate` do "
            "Standalone e ganha o `get_user` do ModelBackend." % sem,
        )

    def test_o_lockout_de_forca_bruta_continua(self):
        """Trocar o backend nao pode desligar o axes.

        `AxesBackend` herda o `authenticate` do `AxesStandaloneBackend`.
        Se algum dia essa heranca mudar, o lockout desaparece em silencio —
        e um lockout desligado nao avisa ninguem.
        """
        from django.utils.module_loading import import_string

        lista = backends_declarados()
        if "axes.backends.AxesBackend" not in lista:
            self.skipTest("o axes nao esta na lista; nada a verificar sobre o lockout")

        cls = import_string("axes.backends.AxesBackend")
        mro = [c.__name__ for c in cls.__mro__]
        self.assertIn(
            "AxesStandaloneBackend",
            mro,
            "`AxesBackend` deixou de herdar do `AxesStandaloneBackend`. O "
            "MRO e' %s. O `authenticate` que faz o lockout de forca bruta "
            "vem dai — e um lockout desligado nao avisa ninguem." % mro,
        )
        self.assertIn(
            "ModelBackend",
            mro,
            "`AxesBackend` deixou de herdar do `ModelBackend`, e e' de la "
            "que vem o `get_user`. MRO: %s." % mro,
        )

    def test_o_standalone_so_aparece_como_componente(self):
        """O Standalone e' correcto como base do AxesBackend; nao como backend.

        Nao e' um teste de abstraccao: fixa que o nome do Standalone nao
        volta a entrar na lista de backends, onde seria o bug de novo.
        """
        lista = backends_declarados()
        self.assertNotIn(
            "axes.backends.AxesStandaloneBackend",
            lista,
            "o `AxesStandaloneBackend` voltou a AUTHENTICATION_BACKENDS. "
            "Ele nao tem `get_user` — e' uso para HERDAR, nao para servir.",
        )


if __name__ == "__main__":
    unittest.main()
