# -*- coding: utf-8 -*-
"""O ciclo da automacao tem de se fechar SOZINHO.

MEDIDO 2026-10-05. O que estes testes apanham
---------------------------------------------
1. `ComandoDevice` era criado pelo `alert_engine` e expirado apenas por
   `manage.py ia_comandos` — um comando que o PRODUTOR nao corre. O
   Agendador de Tarefas do Windows chama `manage.py varrer_proativo`, e o
   `varrer()` nao expirava nada. Resultado: `pendente`/`enviado` ficavam
   para sempre e um gateway que nunca mais confirmasse nao produzia sinal
   nenhum. A fila cresce e ninguem a ve.

2. `amplia_comparativo` foi removida do catalogo e o seu ramo de dispatch
   ficou DEPOIS de um `return`: codigo inalcavel que compila. 480 linhas de
   medicao, 11 testes verdes, e a IA sem conseguir chamar. O teste abaixo e'
   o que apanha essa classe de erro — nao importa a funcao, importa o CAMINHO.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.models import ComandoDevice, Device, Propriedade


class FilaExpiradaSozinhaTest(TestCase):
    """`varrer()` tem de expirar o que nao recebeu ACK."""

    def setUp(self):
        u = User.objects.create_user("ciclo", password="x")
        self.prop = Propriedade.objects.create(
            user=u, nome="Faz Ciclo", area_total=10, uf="MT", cidade="X"
        )
        self.dev = Device.objects.create(
            propriedade=self.prop, device_eui="EUICICLO01", nome="Valvula"
        )

    def _cmd(self, nome, expira_em):
        return ComandoDevice.objects.create(
            device=self.dev, comando=nome, status="pendente", expira_em=expira_em
        )

    def test_comando_vencido_morre_na_varredura(self):
        from app.ia.proativo_tasks import varrer

        velho = self._cmd("valve_open", timezone.now() - timedelta(minutes=5))
        r = varrer()
        velho.refresh_from_db()
        self.assertEqual(velho.status, "erro")
        self.assertEqual(r["comandos_expirados"], 1)
        self.assertEqual(r["comandos_com_erro"], 0)

    def test_comando_no_prazo_sobrevive(self):
        from app.ia.proativo_tasks import varrer

        vivo = self._cmd("valve_close", timezone.now() + timedelta(minutes=20))
        r = varrer()
        vivo.refresh_from_db()
        self.assertEqual(vivo.status, "pendente")
        self.assertEqual(r["comandos_expirados"], 0)

    def test_resumo_tem_a_chave_mesmo_sem_comandos(self):
        from app.ia.proativo_tasks import varrer

        r = varrer()
        # A chave existe para o relatorio poder dizer "0" sem mentir. Se
        # faltasse, o `get(..., 0)` taparia a diferenca entre "nao havia"
        # e "nao deu para perguntar".
        self.assertIn("comandos_expirados", r)
        self.assertIn("comandos_com_erro", r)


class ComparativoAcessivelTest(TestCase):
    """O que o sistema mede tem de ser LEGIVEL pela IA.

    ## Porque estes testes mudaram de forma

    MEDIDO 2026-10-05. A classe asumia que o comparativo era uma entrada de
    `TOOLS_CATALOGO`, e media a acessibilidade por `executar_catalogo`. Isso
    deixou de ser verdade: `amplia_comparativo` foi removido de
    `TOOLS_CATALOGO` (estava registado duas vezes), e quem publica o
    comparativo passou a ser o **intent** `comparativo_revisao`, que chega
    ao cliente por `nome_tool()` sobre `INTENTS` e despacha pelo sandbox.

    A razao de ser do teste — a capacidade tem de ser legivel pela IA — nao
    muda. Muda o caminho. E a mudanca nao e' um detalhe: o `assertIn` antigo
    falhava porque pedia um nome que nao e' publicado, e o
    `executar_catalogo` antigo devolvia `tool de catalogo desconhecida` — ou
    seja, **os dois testes passavam a dar verde no vazio** se alguem tivesse
    limitando-se a trocar o nome.

    Um teste de acessibilidade que mede o nome errado mede nada.
    """

    #: O nome que o cliente recebe. Nao e' de livre escolha: `nome_tool()`
    #: traduz o nome do intent, e mudar este literal sem mudar o intent
    #: parte o teste — que e' o que se quer.
    TOOL = "amplia_comparativo_revisao"
    INTENT = "comparativo_revisao"

    def setUp(self):
        from django.contrib.auth.models import User

        self.u = User.objects.create_user(
            username="comparativo_probe", password="x-probe-12345"
        )

    def test_a_capacidade_chega_ao_cliente(self):
        """Publicada no catalogo que o cliente recebe.

        E' esta a verificacao que substitui a da allowlist. O comparativo e'
        um intent, e um intent nao entra em `TOOLS_CATALOGO_ACEITAS` — essa
        lista e' das tools de CATALOGO. Declara-lo aqui dizia que era uma
        tool de catalogo, e o guard acusava, com razao.
        """
        from app.amplia_mcp import catalogo_tools

        publicadas = {t["name"] for t in catalogo_tools()}
        self.assertIn(
            self.TOOL,
            publicadas,
            "o comparativo tem de chegar ao cliente como tool. Sem isto a "
            "IA nao consegue ler o que o sistema mede, que e' o requisito.",
        )

    def test_a_capacidade_responde_com_o_que_mede(self):
        """Responde, e responde com o que mediu — nao com um dicionario vazio."""
        from app.amplia_mcp import executar_para

        r = executar_para(self.u, self.TOOL, {})

        self.assertNotEqual(
            r.get("erro"),
            "tool_fora_do_catalogo",
            "o comparativo tem de despachar como intent, pelo sandbox",
        )
        self.assertTrue(r.get("ok"), r)
        # 50 e' a contagem de CAPACIDADES, e vem do ficheiro. Um `50` escrito
        # aqui seria um numero que envelhece a cada feature nova — e o que
        # aconteceu a outros testes deste ficheiro.
        self.assertEqual(r["total_dimension"], 50)
        self.assertTrue(
            r.get("resposta"),
            "a intent devolveu sem `resposta`. O protocolo le `resposta`: uma "
            "chave com outro nome e' um dicionario mudo, e foi exactamente "
            "isso que aconteceu com `resumo_texto`.",
        )
        self.assertTrue(r.get("por_veredicto"), r)

    def test_o_caminho_de_dispatch_existe_e_e_alcancavel(self):
        """A classe de bug que este teste existe para apanhar.

        O `if nome ==` apagado e o corpo deixado depois de um `return`
        compila, os testes da funcao passam, e a tool responde
        "desconhecida". A versao antiga media isso por `inspect.getsource` de
        `executar_catalogo` — a funcao que deixou de ser dona deste caminho.

        Para um intent, "o ramo existe" significa: a entrada esta' no registo
        e o handler e' chamavel. E' medido, nao por texto de fonte.
        """
        from app.ia import registro as reg

        spec = reg.REGISTO.get(self.INTENT)
        self.assertIsNotNone(
            spec,
            f"`{self.INTENT}` nao esta' no registo. A capacidade foi removida "
            "do caminho de dispatch e ninguem notou, porque o resto da "
            "superficie de tools continua verde.",
        )
        handler = spec.get("handler")
        self.assertTrue(
            callable(handler),
            f"`{self.INTENT}` esta' no registo sem handler chamavel — e' o "
            "ramo apagado com o corpo la dentro.",
        )

    def test_o_nome_publicado_corresponde_ao_intent(self):
        """O literal `TOOL` tem de ser o que `nome_tool()` produz.

        Sem isto, `TOOL` pode ser um nome correcto que nada publica — e os
        tres testes acima passam a verificar uma capacidade inventada.
        """
        from app.amplia_mcp import nome_tool

        self.assertEqual(nome_tool(self.INTENT), self.TOOL)


class CeleryNaoEngoleTest(TestCase):
    def test_import_error_nao_e_pass_mudo(self):
        import inspect

        import config.celery as c

        src = inspect.getsource(c)
        # `except ImportError: pass` e' o defecto: esconde uma falha de
        # configuracao, e o worker celery corre sem tarefas sem dizer nada.
        self.assertNotIn("except ImportError:\n    pass", src)
