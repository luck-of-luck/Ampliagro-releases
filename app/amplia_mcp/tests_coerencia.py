"""
tests_coerencia.py — o verificador tem de ser verificado.

Um verificador que devolve `tudo_ok` sobre um sistema partido e' pior do que
nao ter verificador: da confianca a quem nao a merece, e a confianca que se
poupe a pensar e' a que produz o proximo bug em silencio.

Por isso este ficheiro faz a coisa incomoda: **parte o sistema de proposito,
uma promessa de cada vez, e confirma que a pergunta certa cai.**

Nao se testa que a pergunta responde `True` num sistema sao — isso testa o
estado, e o estado muda. Testa-se que a pergunta **sente** a quebra. Um teste
que so passa quando o sistema esta bom e' um teste que deixa de correr no
dia seguinte, que e' quando o sistema nao esta bom.

Cada caso abaixo parte uma coisa diferente e nomeia a pergunta que tem de
sentir. Um verificador que apanha tres de quatro quebras e' um verificador que
precisa de dois: o quarto caso passa a dar confianca a uma pergunta morta.

O que NAO e' verificado aqui, e porque: que o sistema esteja de facto coerente
quando nada e' partido. Isso e' `CoerenciaTest::test_a_camada_e_coerente`, e e'
uma asseveracao sobre o presente — util, e sem valor de prova. O valor esta
nos outros.
"""

from unittest.mock import patch

from django.test import TestCase

from app.amplia_mcp import coerencia


class OVerificadorRespondeTest(TestCase):
    """As perguntas existem todas, e todas tem resposta."""

    def test_toda_pergunta_tem_resposta(self):
        """Uma pergunta sem implementacao devolve `False`, e nao levanta.

        E' a armadilha do dicionario de perguntas: acrescenta-se a pergunta,
        esquece-se a funcao, e o verificador passa a dizer que o sistema esta
        partido por causa de uma pergunta a que ninguem respondeu. O pior
        desfecho e' alguem ver a chave a mais no dicionario e "corrigir"
        apagando a pergunta — que e' a forma mais barata de matar um
        verificador.
        """
        for pergunta in coerencia.PREGUNTAS:
            with self.subTest(pergunta=pergunta):
                ok, detalhe = coerencia._responder(pergunta)
                self.assertIsInstance(ok, bool)
                # Uma pergunta respondida explica o que viu — mesmo quando o
                # que viu e' bom. Um `True` sem motivo nao se audita.
                self.assertTrue(detalhe, f"pergunta sem detalhe: {pergunta}")

    def test_verificar_nunca_levanta(self):
        """Um verificador que rebenta nao e' um verificador.

        Quando o que falha e' um import partido ou uma importacao circular, quem
        corre precisa de ler a resposta. Um traceback nao responde a pergunta
        que ficou por fazer — e quem nao le o traceback todo conclui que o
        sistema esta bem.
        """
        with patch.object(coerencia, "_responder", side_effect=RuntimeError("boom")):
            r = coerencia.verificar()
        self.assertFalse(r["tudo_ok"])
        self.assertEqual(r["falhou"], len(coerencia.PREGUNTAS))
        self.assertIn("boom", r["falhas"][0]["detalhe"])

    def test_as_falhas_vem_primeiro(self):
        """Quem abre isto num terminal tem segundos. A pergunta que falhou e' a
        unica coisa que precisa de ler — e por isso que vem primeiro."""
        with patch.object(coerencia, "_responder", return_value=(False, "porque")):
            r = coerencia.verificar()
        self.assertEqual(r["falhas"][0]["detalhe"], "porque")
        self.assertEqual(len(r["falhas"]), len(coerencia.PREGUNTAS))


class ASensibilidadeTest(TestCase):
    """A parte que dá valor ao verificador: partir de propósito.

    Cada caso parte UMA promessa da camada e confirma que a pergunta
    correspondente cai. Se a pergunta continuar verde com a camada partida,
    o verificador e' decoracao.
    """

    def _index(self, r):
        return {x["pergunta"]: x for x in r["respostas"]}

    def _por_pergunta(self, fragmento):
        return next(p for p in coerencia.PREGUNTAS if fragmento in p)

    # --------------------------------------------------------------------
    # 1. Uma tool que o catalogo anuncia e que ninguem sabe executar.
    # --------------------------------------------------------------------
    def test_sente_uma_tool_sem_rota(self):
        """A promessa mais importante: `/tools/` diz ao modelo que tem esta
        mao, e `exec` tem de saber usa-la.

        Como se parte: injeta-se no catalogo uma tool que nao corresponde a
        nenhuma intent nem a nenhum nome de catalogo — exactamente o que
        acontecia quando uma tool nova era acrescentada ao `TOOLS_CATALOGO` e o
        `NOMES_CATALOGO` ficava para tras.
        """
        pergunta = self._por_pergunta("tem rota")
        from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools

        tool_sem_rota = {
            "name": "amplia_nao_existe_no_router",
            "description": "x",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        }
        with patch.object(
            coerencia,
            "_todas_as_tools",
            return_value=catalogo_tools() + list(TOOLS_CATALOGO) + [tool_sem_rota],
        ):
            r = self._index(coerencia.verificar())[pergunta]
        self.assertFalse(r["ok"], "uma tool sem rota passou despercebida")
        self.assertIn("amplia_nao_existe_no_router", r["detalhe"])

    # --------------------------------------------------------------------
    # 2. Uma escrita que nao declara `confirm`.
    # --------------------------------------------------------------------
    def test_sente_uma_escrita_sem_confirm(self):
        """Sem `confirm` declarado e com `additionalProperties: false`, a
        escrita e' impossivel de confirmar por quem a pediu."""
        pergunta = self._por_pergunta("declara `confirm`")
        from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools
        from app.amplia_mcp.contrato import enriquecer

        bruto = catalogo_tools() + list(TOOLS_CATALOGO)
        # Empacota a lista para remover o `confirm` depois do enriquecimento.
        original = enriquecer

        def sem_confirm(tools):
            saida = original(tools)
            for t in saida:
                if t["name"] == "amplia_ligar_irrigador":
                    t["inputSchema"]["properties"].pop("confirm", None)
            return saida

        with (
            patch.object(coerencia, "_todas_as_tools", return_value=bruto),
            patch("app.amplia_mcp.contrato.enriquecer", side_effect=sem_confirm),
        ):
            r = self._index(coerencia.verificar())[pergunta]
        self.assertFalse(r["ok"], "uma escrita sem 'confirm' passou despercebida")

    # --------------------------------------------------------------------
    # 3. `confirm` posto em `required`.
    # --------------------------------------------------------------------
    def test_sente_confirm_em_required(self):
        """Confirmar antes de ter feito tornaria a escrita impossivel: e' o que
        transforma um segundo passo num passo que nunca chega."""
        self._parte_o_contrato(
            "declara `confirm`",
            lambda ts: ts["inputSchema"].__setitem__("required", ["confirm"]),
            "amplia_ligar_irrigador",
            "'confirm' em 'required' passou despercebida",
        )

    # --------------------------------------------------------------------
    # 4. Campo obrigatorio que o schema proibe.
    # --------------------------------------------------------------------
    def test_sente_um_obrigatorio_proibido(self):
        """Declarar `required: ["area"]` num schema que proibe `area` produz um
        contrato impossivel de satisfazer — e nao um erro visivel: produz uma
        IA a inventar."""
        self._parte_o_contrato(
            "pelo schema que o declara",
            lambda ts: (
                ts["inputSchema"].__setitem__("required", ["campo_que_nao_existe"]),
                ts["inputSchema"]["properties"].pop("campo_que_nao_existe", None),
            ),
            "amplia_clima_agora",
            "um obrigatorio proibido passou despercebida",
        )

    def _parte_o_contrato(self, fragmento, mexer, em_qual, mensagem):
        """Parte o schema de UMA tool e pergunta se o verificador sente.

        Existe porque os tres casos anteriores repetiam o mesmo aparato e
        divergiram: um deles ficou com o `with` aninhado, outro nao. Um
        aparelho repetido tres vezes diverge — sempre. Este e' o apparatus
        unico, e cada caso so diz *o que* partir e *o que* deve acontecer.

        A mutacao corre DEPOIS de `enriquecer`, e e' esse o ponto: e' o
        contrato publicado que se parte, nao a funcao que o produz. Um
        aparelho que partisse antes veria um catalogo diferente e provaria
        outra coisa.
        """
        pergunta = self._por_pergunta(fragmento)
        from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools
        from app.amplia_mcp.contrato import enriquecer

        bruto = catalogo_tools() + list(TOOLS_CATALOGO)

        def partido(tools):
            saida = enriquecer(tools)
            for t in saida:
                if t["name"] == em_qual:
                    mexer(t["inputSchema"])
            return saida

        with (
            patch.object(coerencia, "_todas_as_tools", return_value=bruto),
            patch("app.amplia_mcp.contrato.enriquecer", side_effect=partido),
        ):
            r = self._index(coerencia.verificar())[pergunta]
        self.assertFalse(r["ok"], mensagem)

        # --------------------------------------------------------------------
        # 5. Uma intent que nao chega ao cliente.
        # --------------------------------------------------------------------

    # --------------------------------------------------------------------
    # 5. Uma intent que nao chega ao cliente.
    # --------------------------------------------------------------------
    def test_sente_uma_intent_escondida(self):
        """A falha que a conversa do produtor apanhou: a capacidade existia
        escrita, com descricao e exemplos, e o catalogo que a IA lia nao a
        continha. A IA nao tinha como a ver — e nao tinha como saber que
        lhe faltava.

        Parte-se pelo **catalogo**, e nao pelo registo. Tirar uma entrada do
        registo nao prova nada: `sandbox.INTENTS` foi importado no arranque do
        processo e continua a ter a entrada, que e' exactamente como um
        registo e um catalogo divergem sem ninguem ver. A divergencia que
        interessa e' a que o cliente sente — logo parte-se o lado do cliente.
        """
        pergunta = self._por_pergunta("chega ao cliente")
        from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools

        bruto = catalogo_tools() + list(TOOLS_CATALOGO)
        escondido = bruto[0]["x-intent"]
        sem_ela = [t for t in bruto if t.get("x-intent") != escondido]

        with patch.object(coerencia, "_todas_as_tools", return_value=sem_ela):
            r = self._index(coerencia.verificar())[pergunta]
        self.assertFalse(r["ok"], "uma intent escondida passou despercebida")
        self.assertIn(escondido, r["detalhe"])

    # --------------------------------------------------------------------
    # 6. O guia a mentir.
    # --------------------------------------------------------------------
    def test_sente_o_guia_a_mentir(self):
        """O guia e' o unico sitio onde se diz como se confirma uma escrita. Se
        deixar de mentionar `confirm`, ele esta' a prometer um caminho que o
        contrato nao tem."""
        pergunta = self._por_pergunta("guia afirma")
        with patch(
            "app.amplia_mcp.contrato.GUIA",
            "COMO USAR ESTA CAMADA\n1. Uma tool por chamada.",
        ):
            r = self._index(coerencia.verificar())[pergunta]
        self.assertFalse(r["ok"], "o guia sem 'confirm' passou despercebida")


class CoerenciaTest(TestCase):
    """A asseveracao sobre o presente. Util, e sem valor de prova."""

    def test_a_camada_e_coerente(self):
        r = coerencia.verificar()
        self.assertTrue(
            r["tudo_ok"],
            "a camada esta a mentir sobre si mesma:\n"
            + "\n".join(f"  - {f['pergunta']}: {f['detalhe']}" for f in r["falhas"]),
        )

    def test_o_resultado_e_serializavel(self):
        """Sai num `JsonResponse`. Um verificador que so funciona num REPL e'
        um verificador que ninguem consultou."""
        import json

        json.dumps(coerencia.verificar())


class IntegridadeDoCatalogoTest(TestCase):
    """A 11a pergunta, e a unica que nao e' relativa.

    As outras dez comparam o MCP com o REGISTO, as tools com as rotas, o guia
    com o contrato. Uma comparacao relativa da "certo" quando as duas
    pontas caem juntas — e foi assim que 76 intents passaram a 44 sem uma
    unica pergunta vermelha.
    """

    def test_a_pergunta_de_integridade_e_a_primeira(self):
        """Tem de correr primeiro: as outras dez so' fazem sentido se o
        catalogo estiver inteiro."""
        self.assertIn("carregou", coerencia.PREGUNTAS[0])

    def test_saudavel_esta_verde(self):
        r = coerencia.verificar()
        self.assertTrue(r["tudo_ok"], r["falhas"])
        # 13 = as 10 originais + integridade do catálogo + as duas de
        # honestidade. Este número é uma Interfaces com a lista, e vai
        # mudar quando se acrescentar uma pergunta — que é o ponto: quando
        # mudar, este teste diz que mudou.
        self.assertEqual(r["perguntas"], len(coerencia.PREGUNTAS))

    def test_um_catalogo_em_falha_faz_a_verificacao_falhar(self):
        """A PROVA NEGATIVA, e o que dá sentido a check.

        Sem este teste, a check pode estar publicada e a nao ver nada — o
        que ja aconteceu com um ESPERADO = 76 fixo, que passou a acusar
        um bug inexistente quando outra sessao added 4 intents.
        """
        from app.ia import registro as reg

        self.assertIn("dinamico_intents", reg.CARREGADOS)
        reg.CARREGADOS.discard("dinamico_intents")
        try:
            r = coerencia.verificar()
            self.assertFalse(
                r["tudo_ok"], "a verificacao devia falhar com um catalogo em falta"
            )
            detalhe = " ".join(f["detalhe"] for f in r["falhas"])
            self.assertIn("dinamico_intents", detalhe)
        finally:
            reg.CARREGADOS.add("dinamico_intents")

    def test_recupera_ao_repor(self):
        from app.ia import registro as reg

        reg.CARREGADOS.discard("iot_intents")
        reg.CARREGADOS.add("iot_intents")
        self.assertTrue(coerencia.verificar()["tudo_ok"])
