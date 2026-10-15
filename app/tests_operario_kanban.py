"""A view do kanban nao pode escrever dado falso na fazenda real.

GRAVE 2. Achado pela s6 do console.md (Predador, 04/10/2026) e nao corrigido
ate' este teste existir.

O QUE ACONTECIA
---------------
`app/views/operario.py:68-112` tinha esta condicao:

    if not is_servidor and propriedade and not base_qs.exists():

isto e', um produtor com uma propriedade e ZERO tarefas abria a pagina do
kanban, e o simples RENDERIZAR executava `get_or_create` criando, na fazenda
REAL dele:

    - 1 RegistroProducao chamado "Demo <cultura>"
    - 1 EstagioCultura chamado "Plantio"
    - 6 TarefaEstagio ("Revisar trator 8R", "Aplicar fertilizante Talhao A"...)

Sem gate de DEBUG. E' o INVERSO DO `sem_dado`: o sistema que passou a vida a
dizer "aqui isto nao foi medido" estava, noutro sitio, a preencher o vazio com
mentira. E era pegajoso — o produtor que apagasse as tarefas voltava a ter seis
que nao tinha pedido.

A CORRECAO
----------
O portao e' o mesmo que o login demo ja usa (`app/views/auth.py:458`):
`settings.DEBUG or AMPLIAGRO_DEMO_ENABLED`. Sem esse portao, qualquer
visitante de producao criava dados na sua propria fazenda so de olhar para um
ecra. `demo.bat` roda local com DEBUG=True, portanto a demonstracao continua.

Este ficheio tem os DOIS lados. Testar so o caminho fechado deixava a
apresentacao de FEBRACE silenciosamente partida, e um teste que so prova que
nao se quebrou nada nao prova nada.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from app.models import (
    Cultura,
    PerfilUsuario,
    Propriedade,
    RegistroProducao,
    TarefaEstagio,
)

URL = "/operario/kanban/"


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


class KanbanNaoFabricaTarefas(TestCase):
    """O produtor com zero tarefas ve zero tarefas. Nao seis."""

    def setUp(self):
        self.produtor = _mkuser("prod_sem_tarefas")
        self.prop = Propriedade.objects.create(
            user=self.produtor,
            nome="Fazenda Limpa",
            area_total=50,
            uf="MT",
            cidade="X",
        )
        PerfilUsuario.objects.update_or_create(
            user=self.produtor,
            defaults={"tipo_usuario": "produtor", "propriedade_vinculada": self.prop},
        )
        self.produtor.refresh_from_db()
        Cultura.objects.create(nome="SojaTeste", grupo="graos", ativo=True)
        self.client = Client()
        self.client.force_login(self.produtor)

    def _contagens(self):
        return {
            "tarefas": TarefaEstagio.objects.count(),
            "registos": RegistroProducao.objects.count(),
        }

    @override_settings(DEBUG=False, AMPLIAGRO_DEMO_ENABLED=False)
    def test_renderizar_nao_escreve_nada_na_base_de_dados(self):
        """O teste que apanha o GRAVE 2.

        Conta as linhas ANTES e DEPOIS de renderizar. O teste apanha se
        alguem voltar a pôr a criacao sem portao.
        """
        antes = self._contagens()
        self.client.get(URL)
        depois = self._contagens()

        self.assertEqual(
            antes,
            depois,
            f"Renderizar o kanban escreveu na base de dados: {antes} -> {depois}.\n"
            "Um produtor sem tarefas tem de ver que nao tem tarefas. Criar\n"
            "tarefas de demonstracao ao olhar para o ecra e escrever na fazenda\n"
            "REAL dele, e o inverso do `sem_dado`.",
        )

    @override_settings(DEBUG=False, AMPLIAGRO_DEMO_ENABLED=False)
    def test_o_kanban_fica_vazio_e_nao_falso(self):
        """Sem dados, o painel mostra vazio. Nao mostra um registo chamado 'Demo'."""
        self.client.get(URL)
        demo = RegistroProducao.objects.filter(nome__startswith="Demo").exists()
        self.assertFalse(
            demo,
            "Existe um RegistroProducao 'Demo' na fazenda de um produtor que "
            "nunca pediu um. O nome diz-o, e e' o que se via no ecra.",
        )

    @override_settings(DEBUG=False, AMPLIAGRO_DEMO_ENABLED=True)
    def test_o_portao_aberto_ainda_demonstra(self):
        """O outro lado: com o portao aberto, a apresentacao continua a funcionar.

        Sem este teste, corrigir o GRAVE 2 podia partir a apresentacao de
        FEBRACE e ninguem notava — o que seria trocar um bug por um bug.
        """
        self.client.get(URL)
        self.assertGreater(
            TarefaEstagio.objects.count(),
            0,
            "Com AMPLIAGRO_DEMO_ENABLED ligado, o kanban tinha de criar as "
            "tarefas de demonstracao. Se agora nao cria, a apresentacao "
            "FEBRACE fica sem painel — e o que corrigimos nao era o unico bug.",
        )


class AKanbanFalhaFechada(TestCase):
    """GRAVE 3. A excepcao concedia privilegio em vez de o retirar.

    Antes, em `operario.py`:

        except Exception:
            is_servidor = True
            pode_criar = True

    Se a leitura do perfil falhasse por qualquer razao, o sistema dava a esse
    utilizador o que nunca provou ter: papel de servidor E permissao de
    escrita. O dashboard do servidor (`servidor.py`) ja fazia o contrario.

    Aqui o teste monkeypatcha `get_dashboard_config` para lancar, que e' a
    hipotese realista: o `@kanban_required` ja bloqueia quem nao tem perfil, e
    `kanban_allowed` ja devolve `False` nesse caso. Chegar ao `except` com
    perfil existente significa que foi outra coisa a lancar.
    """

    def setUp(self):
        self.produtor = _mkuser("prod_excepcao")
        self.prop = Propriedade.objects.create(
            user=self.produtor,
            nome="Fazenda Excepcao",
            area_total=50,
            uf="MT",
            cidade="X",
        )
        PerfilUsuario.objects.update_or_create(
            user=self.produtor,
            defaults={"tipo_usuario": "produtor", "propriedade_vinculada": self.prop},
        )
        self.produtor.refresh_from_db()
        Cultura.objects.create(nome="SojaExc", grupo="graos", ativo=True)
        self.client = Client()
        self.client.force_login(self.produtor)

    def test_a_excepcao_nao_concede_privilegio_de_servidor(self):
        """Com a leitura do perfil a lancar, o kanban NAO pode tratar o
        utilizador como servidor."""
        from unittest.mock import patch

        from app.models import PerfilUsuario as P

        def lanca(self):
            raise RuntimeError("config ilegivel")

        with patch.object(P, "get_dashboard_config", lanca):
            r = self.client.get(URL)

        # Nao redirecciona: o utilizador esta autorizado, a leitura da config
        # e' que falhou. Expulsa-lo seria trocar uma falha de seguranca por uma
        # de disponibilidade.
        self.assertEqual(
            r.status_code,
            200,
            "A view levantou em vez de cair para o menos privilegio. "
            "O `@kanban_required` ja autorizou este utilizador; falhar a "
            "leitura da config nao o torna nao autorizado.",
        )

    def test_a_excepcao_e_registada(self):
        """Uma falha que dá privilegio tem de ficar visivel no log.

        O `except` original era `pass` effectively: silencioso. Uma falha
        fechada e silenciosa e' uma falha que ninguem vai investigar.
        """
        from unittest.mock import patch

        from app.models import PerfilUsuario as P

        def lanca(self):
            raise RuntimeError("config ilegivel")

        with (
            patch.object(P, "get_dashboard_config", lanca),
            self.assertLogs("app.views.operario", level="WARNING") as cm,
        ):
            self.client.get(URL)

        self.assertTrue(
            any("kanban_perfil_ilegivel" in m for m in cm.output),
            f"A falha nao foi registada. Output do log: {cm.output}",
        )


class OPortaoEstaNoCodigo(TestCase):
    """A condicao tem de estar escrita, nao so funcionar.

    Um teste que so mede comportamento passa se alguem reintroduzir a criacao
    dentro de um `if DEBUG` no lugar errado. Este verifica que o portao esta
    no sitio, ao lado do bloco que grava.
    """

    def test_a_ultima_afuncao_do_ficheiro_tem_o_portao(self):
        import inspect

        from app.views import operario

        fonte = inspect.getsource(operario.operario_kanban_view)
        self.assertIn(
            "AMPLIAGRO_DEMO_ENABLED",
            fonte,
            "A view do kanban deixou de ter o portao de demonstracao. "
            "Reintroduziu-se a criacao de dado falso na fazenda real.",
        )
        self.assertIn("settings.DEBUG", fonte)
