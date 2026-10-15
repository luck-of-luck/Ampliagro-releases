"""Testes da lincagem servidor/funcionário: vinculada, páginas e navbar."""

import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from app.models import (
    Cultura,
    EstagioCultura,
    PerfilUsuario,
    Propriedade,
    RegistroProducao,
    Safra,
    Talhao,
    TarefaEstagio,
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


def _mkservidor(name, area, prop, **kw):
    u = _mkuser(name)
    PerfilUsuario.objects.update_or_create(
        user=u,
        defaults={
            "tipo_usuario": "servidor",
            "area_servidor": area,
            "propriedade_vinculada": prop,
            **kw,
        },
    )
    # O sinal post_save já criou o perfil (e populou o cache de `u.perfil`) com
    # tipo "produtor". Sem recarregar, `propriedades_visiveis` leria
    # `propriedade_vinculada_id = None` e a fazenda vinculada sumiria.
    u.refresh_from_db()
    return u


class ServidorLincagemTest(TestCase):
    def setUp(self):
        self.produtor = _mkuser("prod")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Fazenda P", area_total=50, uf="MT", cidade="X"
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Talhão Serv", area_hectare=10, ativo=True
        )
        cultura = Cultura.objects.create(nome="SojaSrv", grupo="graos")
        Safra.objects.create(
            propriedade=self.prop, cultura=cultura, ano=2026, area_plantada=10
        )
        self.campo = _mkservidor("campo1", "CAMPO", self.prop)
        self.estoque = _mkservidor("est1", "ESTOQUE", self.prop)

    def _get(self, user, url):
        c = Client()
        c.force_login(user)
        return c.get(url)

    def test_visiveis_inclui_vinculada(self):
        from app.hierarquia import propriedades_visiveis

        self.assertIn(self.prop, propriedades_visiveis(self.campo))
        self.assertIn(self.prop, propriedades_visiveis(self.produtor))

    def test_talhao_mostra_vinculada(self):
        r = self._get(self.campo, "/cadastro/talhao/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Talhão Serv")

    def test_safra_mostra_vinculada(self):
        r = self._get(self.campo, "/cadastro/safra/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "SojaSrv")

    def test_telemetria_campo_ok_estoque_403(self):
        r = self._get(self.campo, "/telemetria/")
        self.assertEqual(r.status_code, 200)
        r2 = self._get(self.estoque, "/telemetria/")
        self.assertEqual(r2.status_code, 403)

    def test_navbar_esconde_telemetria_do_estoque(self):
        r = self._get(self.estoque, "/servidor/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'data-pill="telemetria"')
        r2 = self._get(self.campo, "/servidor/")
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'data-pill="telemetria"')

    def test_paginas_servidor_200(self):
        for url in [
            "/servidor/",
            "/servidor/agenda/",
            "/servidor/alertas/",
            "/servidor/kanban/",
        ]:
            r = self._get(self.campo, url)
            self.assertIn(r.status_code, (200, 302), url)
        r = self._get(self.estoque, "/servidor/estoque/")
        self.assertEqual(r.status_code, 200)

    def test_estoque_bloqueado_para_campo(self):
        r = self._get(self.campo, "/servidor/estoque/")
        self.assertEqual(r.status_code, 403)
        r2 = self._get(self.campo, "/servidor/")
        self.assertNotContains(r2, 'data-pill="estoque"')

    def test_servidor_sem_vinculo_nao_quebra(self):
        u = _mkuser("solto")
        PerfilUsuario.objects.update_or_create(
            user=u,
            defaults={"tipo_usuario": "servidor", "area_servidor": "CAMPO"},
        )
        for url in ["/servidor/", "/cadastro/talhao/", "/cadastro/safra/"]:
            r = self._get(u, url)
            self.assertEqual(r.status_code, 200, url)

    def test_produtor_inalterado(self):
        r = self._get(self.produtor, "/cadastro/talhao/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Talhão Serv")


PAYLOAD_XSS = "</script><script>window.__PWNED__=1</script>"


class ServidorXSSConfigTest(TestCase):
    """XSS armazenado via PerfilUsuario.permissoes -> config_json|safe.

    permissoes e um JSONField editavel pelo produtor. Ele flui para
    get_dashboard_config() e era injetado no <script> com |safe, entao um
    "</script>" no titulo fechava a tag e executava JS no navegador do
    servidor logado (roubo de sessao / escalada entre tenants).
    """

    def setUp(self):
        self.produtor = _mkuser("prod_xss")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Faz XSS", area_total=10, uf="MT", cidade="X"
        )
        self.srv = _mkservidor(
            "srv_xss",
            "CAMPO",
            self.prop,
            permissoes={"titulo": PAYLOAD_XSS, "descricao": PAYLOAD_XSS},
        )

    def test_payload_nao_quebra_o_script(self):
        c = Client()
        c.force_login(self.srv)
        r = c.get("/servidor/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        # O payload literal nao pode aparecer: significaria breakout do <script>
        self.assertNotIn(PAYLOAD_XSS, html)
        self.assertNotIn("<script>window.__PWNED__", html)
        # A config ainda chega ao browser, escapada como \u003C
        self.assertIn("servidor-cfg", html)
        self.assertIn("\\u003C", html)

    def test_config_json_script_e_json_valido(self):
        c = Client()
        c.force_login(self.srv)
        html = c.get("/servidor/").content.decode("utf-8")
        inicio = html.index('id="servidor-cfg"')
        bruto = html[inicio:].split(">", 1)[1].split("</script>")[0]
        dados = json.loads(bruto)
        self.assertEqual(dados["titulo"], PAYLOAD_XSS)
        self.assertEqual(dados["icone"], "bi-tree")  # base da area preservada


class ServidorTarefasTest(TestCase):
    """Dashboard e agenda devem usar a MESMA regra de tarefas.

    Regressao: o dashboard filtrava por `estagio__registro__user=propriedade.user`
    (apenas pelo dono da fazenda) enquanto a agenda usava
    `Q(propriedade=) | Q(estagio__registro__user=)`. Tarefas vinculadas pela
    propriedade apareciam na agenda e sumiam do dashboard.
    """

    def setUp(self):
        self.produtor = _mkuser("prod_tar")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Faz T", area_total=10, uf="MT", cidade="X"
        )
        self.srv = _mkservidor("srv_tar", "GERAL", self.prop)
        # TarefaEstagio.estagio e NOT NULL: montar a cadeia minima
        registro = RegistroProducao.objects.create(
            user=self.produtor, nome="Reg T", grupo="vegetal"
        )
        estagio = EstagioCultura.objects.create(
            registro=registro, nome="Est T", ordem=1
        )
        self.tarefa = TarefaEstagio.objects.create(
            estagio=estagio, propriedade=self.prop, descricao="Tarefa por propriedade"
        )
        # Tarefa do MESMO dono, mas SEM propriedade: so via estagio__registro__user
        reg2 = RegistroProducao.objects.create(
            user=self.produtor, nome="Reg T2", grupo="vegetal"
        )
        self.tarefa_via_registro = TarefaEstagio.objects.create(
            estagio=EstagioCultura.objects.create(
                registro=reg2, nome="Est T2", ordem=1
            ),
            descricao="Tarefa via registro",
        )
        # Caso que o filtro antigo perdia: tarefa DA fazenda (propriedade=self.prop)
        # criada no registro de OUTRO usuario (agronomo, por exemplo).
        # `estagio__registro__user=produtor` nao casa -> sumia do dashboard.
        agronomo = _mkuser("agronomo_tar")
        reg3 = RegistroProducao.objects.create(
            user=agronomo, nome="Reg T3", grupo="vegetal"
        )
        self.tarefa_de_terceiro = TarefaEstagio.objects.create(
            estagio=EstagioCultura.objects.create(
                registro=reg3, nome="Est T3", ordem=1
            ),
            propriedade=self.prop,
            descricao="Tarefa da fazenda criada por terceiro",
        )

    def _tarefas_no_contexto(self, url):
        c = Client()
        c.force_login(self.srv)
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        return list(r.context["tarefas"])

    def test_tarefa_por_propriedade_aparece_no_dashboard(self):
        self.assertIn(self.tarefa, self._tarefas_no_contexto("/servidor/"), "dashboard")

    def test_tarefa_por_propriedade_aparece_na_agenda(self):
        self.assertIn(
            self.tarefa, self._tarefas_no_contexto("/servidor/agenda/"), "agenda"
        )

    def test_as_duas_regras_encontram_as_duas_tarefas(self):
        """Nenhuma das 2 vias pode ficar de fora, em qualquer das 2 telas."""
        for url in ("/servidor/", "/servidor/agenda/"):
            with self.subTest(url=url):
                achadas = self._tarefas_no_contexto(url)
                self.assertIn(self.tarefa, achadas, url)
                self.assertIn(self.tarefa_via_registro, achadas, url)

    def test_dashboard_encontra_tarefa_criada_por_terceiro(self):
        """Regressao do filtro antigo: `estagio__registro__user=propriedade.user`
        perdia tarefas da fazenda cujo registro pertence a outro usuario
        (agronomo,客场). A agenda ja achava; o dashboard nao."""
        self.assertIn(
            self.tarefa_de_terceiro,
            self._tarefas_no_contexto("/servidor/"),
            "dashboard precisa achar tarefa da fazenda criada por terceiro",
        )

    def test_tarefa_de_outra_fazenda_nao_vaza(self):
        outro = _mkuser("outro_prod")
        prop2 = Propriedade.objects.create(
            user=outro, nome="Faz Estranha", area_total=10, uf="MT", cidade="X"
        )
        reg3 = RegistroProducao.objects.create(
            user=outro, nome="Reg X", grupo="vegetal"
        )
        alheia = TarefaEstagio.objects.create(
            estagio=EstagioCultura.objects.create(registro=reg3, nome="Est X", ordem=1),
            propriedade=prop2,
            descricao="Task de outra fazenda",
        )
        for url in ("/servidor/", "/servidor/agenda/"):
            with self.subTest(url=url):
                self.assertNotIn(alheia, self._tarefas_no_contexto(url), url)


class ServidorDesativadoTest(TestCase):
    """ativo_servidor=False precisa realmente bloquear o acesso."""

    def setUp(self):
        self.produtor = _mkuser("prod_off")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Faz Off", area_total=10, uf="MT", cidade="X"
        )
        self.srv = _mkservidor("srv_off", "CAMPO", self.prop, ativo_servidor=False)

    def test_dashboard_bloqueia_servidor_desativado(self):
        c = Client()
        c.force_login(self.srv)
        r = c.get("/servidor/")
        self.assertContains(r, "Servidor desativado", status_code=200)
        # E a sessao foi encerrada de fato
        self.assertNotIn("_auth_user_id", c.session)

    # --- as outras 4 rotas -------------------------------------------------
    # Estas faltavam. O teste acima passava verde com a revogacao a funcionar
    # so no dashboard: `_perfil_e_propriedade` (estoque, agenda, alertas) e
    # `kanban_allowed` (kanban) nao olhavam `ativo_servidor`. Um servidor
    # desactivado pelo produtor, com sessao ja iniciada, continuava a ler as
    # tarefas e os alertas de telemetria da fazenda.
    #
    # O que se mede aqui nao e' a resposta — e' que a resposta NAO contem os
    # dados da fazenda. Um 302 com o motivo certo passa; um 200 a servir a
    # agenda nao passa.

    def test_estoque_bloqueia_servidor_desativado(self):
        c = Client()
        c.force_login(self.srv)
        r = c.get("/servidor/estoque/")
        self.assertNotEqual(
            r.status_code, 200, "estoque respondeu 200 a um servidor desactivado"
        )
        self.assertIn(
            r.status_code,
            (302, 403),
            "resposta inesperada: %d (302 e' o correcto)" % r.status_code,
        )

    def test_agenda_bloqueia_servidor_desativado(self):
        c = Client()
        c.force_login(self.srv)
        r = c.get("/servidor/agenda/")
        self.assertNotEqual(
            r.status_code, 200, "agenda respondeu 200 a um servidor desactivado"
        )

    def test_alertas_bloqueia_servidor_desativado(self):
        c = Client()
        c.force_login(self.srv)
        r = c.get("/servidor/alertas/")
        self.assertNotEqual(
            r.status_code, 200, "alertas respondeu 200 a um servidor desactivado"
        )

    def test_kanban_bloqueia_servidor_desativado(self):
        c = Client()
        c.force_login(self.srv)
        r = c.get("/servidor/kanban/")
        # o kanban redirecciona para o login; o que nao pode e' 200 com tarefas
        self.assertNotEqual(
            r.status_code, 200, "kanban respondeu 200 a um servidor desactivado"
        )

    def test_kanban_mesma_regra_que_o_dashboard(self):
        """A regiao que o dashboard tem de coincidir com a do kanban."""
        from app.views.utils import kanban_allowed

        self.srv.perfil.ativo_servidor = False
        self.srv.perfil.save()
        self.assertFalse(
            kanban_allowed(self.srv),
            "kanban_allowed ainda deixa passar um servidor desactivado",
        )

        # e volta a passar quando o produtor reactiva
        self.srv.perfil.ativo_servidor = True
        self.srv.perfil.save()
        self.assertTrue(
            kanban_allowed(self.srv), "kanban_allowed bloqueia quem esta activo"
        )
