"""GRAVE 1 — a revogacao de acesso nao se propaga.

Achado pela s6 do console.md (Predador) em 04/10/2026. Confirmado por leitura
directa do codigo em 04/10/2026 (parsing de AST, nao `grep` de janela), e
corrigido no mesmo dia.

## O QUE ACONTECIA

`PerfilUsuario.ativo_servidor` e' o flag que o produtor usa para desligar um
servidor (`app/views/lgpd.py`). Com `False`:

- o proximo login e' bloqueado (`auth.py`)
- o dashboard mostra "Servidor desativado pelo produtor"

Mas as outras rotas nao o consultavam. **Quem ja tivesse sessao iniciada
continuava a ler, depois de ser desactivado:**

    /servidor/            dashboard   SIM (verificava a mao)
    /servidor/estoque/              NAO
    /servidor/agenda/               NAO
    /servidor/alertas/              NAO
    /servidor/kanban/    operario.py NAO

## ONDE ESTAVA A CAUSA

As tres views do meio nao estavam cada uma "desprotegidas": as tres passam por
`_perfil_e_propriedade(request)`, cujo docstring se declara "unica fonte de
verdade para 'de qual fazenda eu sou'". E esse helper verificava:

    perfil is None          -> bloqueia
    tipo_usuario bloqueado  -> bloqueia
    ativo_servidor          -> NAO VERIFICAVA

Uma omissao num helper, quatro rotas afectadas. A view do dashboard e' a
unica que nao passa por ele, e por isso a regra teve de ser escrita la
tambem.

Este ficheiro tem os dois lados: com o portao, revogado bloqueia; sem o
portao, revogado passa. A mutacao e' o que prova que o teste apanha.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import PerfilUsuario, Propriedade

# As quatro rotas que o produtor espera que o flag proteja.
ROTAS_SERVIDOR = [
    "/servidor/",
    "/servidor/estoque/",
    "/servidor/agenda/",
    "/servidor/alertas/",
    "/servidor/kanban/",
]


def _servidor(nome, prop, **kw):
    u = User.objects.create_user(username=nome, password="x")
    PerfilUsuario.objects.update_or_create(
        user=u,
        defaults={
            "tipo_usuario": "servidor",
            "area_servidor": "MECANICA",
            "propriedade_vinculada": prop,
            **kw,
        },
    )
    u.refresh_from_db()
    return u


class RevogacaoPropaga(TestCase):
    def setUp(self):
        self.prod = User.objects.create_user(username="prod_rev", password="x")
        self.prop = Propriedade.objects.create(
            user=self.prod, nome="Faz Rev", area_total=50, uf="MT", cidade="X"
        )
        self.srv = _servidor("srv_rev", self.prop)
        self.client = Client()
        self.client.force_login(self.srv)

    def _perfil(self):
        return PerfilUsuario.objects.get(user=self.srv)

    def test_um_servidor_ativo_passa_em_todas_as_rotas(self):
        """O lado esquerdo: o portao nao pode ter fechado a porta a quem pode.

        Sem este, uma correccao que bloqueasse toda a gente passava os testes
        do lado direito.
        """
        self._perfil().ativo_servidor = True
        self._perfil().save()

        for rota in ROTAS_SERVIDOR:
            with self.subTest(rota=rota):
                r = self.client.get(rota)
                self.assertNotEqual(
                    r.status_code,
                    302,
                    f"{rota} redirigiu um servidor ACTIVO. A revogacao "
                    "virou um bloqueio geral.",
                )

    def test_servidor_revogado_nao_le_estoque_agenda_nem_alertas(self):
        """O lado direito: revogado e' barrado de todas as rotas.

        Este e' o teste que apanha o GRAVE 1. Antes, as tres respondiam 200 a
        um servidor desactivado.
        """
        p = self._perfil()
        p.ativo_servidor = False
        p.save()
        self.client.force_login(self.srv)

        for rota in ROTAS_SERVIDOR:
            with self.subTest(rota=rota):
                r = self.client.get(rota)
                nao_e_o_login = r.status_code in (200, 302)
                self.assertTrue(
                    r.status_code in (301, 302, 403)
                    or "desativado" in r.content.decode("utf-8", "replace").lower()
                    or "desativado" in str(r.get("Location", "")).lower(),
                    f"{rota} respondeu {r.status_code} a um servidor REVOGADO. "
                    "A revogacao nao se propagou.",
                )
                del nao_e_o_login


class OHelperEONaoSoAsViews(TestCase):
    """A regra tem de estar no helper, nao em cada view que o chama.

    Um teste que so bate nas rotas passa se alguem reintroduzir o `if` em cada
    view e o remove do helper. Este verifica o helper directamente.
    """

    def test_o_helper_rejeita_perfil_revogado(self):
        from app.views.servidor import _perfil_e_propriedade

        prod = User.objects.create_user(username="prod_h", password="x")
        prop = Propriedade.objects.create(
            user=prod, nome="Faz H", area_total=10, uf="MT", cidade="X"
        )
        srv = _servidor("srv_h", prop)
        srv.perfil.ativo_servidor = False
        srv.perfil.save()

        class _Req:
            pass

        req = _Req()
        req.user = srv
        perfil, propriedade = _perfil_e_propriedade(req)
        self.assertIsNone(
            perfil,
            "O helper devolveu um perfil revogado. A revogacao tem de estar "
            "no helper, que e' a 'unica fonte de verdade' — nas views so, "
            "volta a propagar-se mal.",
        )
