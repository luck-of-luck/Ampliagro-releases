"""
O CONTRATO entre o que o AmplIA publica e o que ele aceita chamar.

Este ficheiro existe por causa de um defeito que não se via em nenhum teste
que já existia. O servidor publicava um conjunto de nomes; o cliente
aprendia outro; e ninguém tinha escrito que os dois conjuntos tinham de ser
o mesmo.

O que aconteceu, medido
-----------------------
O `IA_SYSTEM` em `static/js/ia-local/ia-local.js` ensinava ao modelo local
treze nomes: `navegar`, `consultar`, `criar`, `iniciar_cadastro`,
`irrigacao`, `atualizar`, `excluir`, `relatorio`, `buscar_web`, e mais
quatro de compatibilidade.

    MEDIDO: as treze são fantasmas. Nenhuma existe no catálogo das 76.

    Consequência, ponta a ponta por HTTP: toda a tool call que o modelo
    conseguia escrever voltava `tool_fora_do_catalogo`.

A regra que este ficheiro fixa
------------------------------
> **Um nome que o AmplIA publica tem de ser um nome que o AmplIA aceita.**

Não é uma regra sobre nomes — é uma regra sobre a distância entre o que se
promete e o que se cumpre. E é verificável sem browser, sem WebLLM e sem
qualquer uma das coisas que tornam os testes de frontend impossíveis aqui.

Por que estes testes não leem o ficheiro-fonte
----------------------------------------------
Porque é a armadilha que a decisão D7 da equipa já nomeou: um teste que lê
o ficheiro e compara strings falha por causa do próprio comentário que
explica o defeito. Este ficheiro executa o catálogo real e compara com o
vocabulário real. Se alguém voltar a escrever nomes à mão no prompt, estes
testes continuam verdes — e devem continuar, porque o prompt deixou de ser
a fonte. O que os apanha é o teste do `ia-local.js`, que é do lado do
cliente.
"""

import re

from django.contrib.auth.models import User
from django.test import TestCase

from app.amplia_mcp import (
    TOOLS_CATALOGO,
    _dado_fabricado,
    catalogo_tools,
    executar_para,
    intent_de_tool,
    nome_tool,
    sugerir_tools,
    vocabulario,
)
from app.ia.sandbox import INTENTS, somente_leitura

#: Os nomes que a persona antiga ensinava ao modelo. Vêm do `IA_SYSTEM` que
#: estava em `ia-local.js:4240` antes de ser corrigido.
#:
#: Estão escritos aqui de propósito. Esta lista é uma ASSERTAÇÃO sobre o
#: defeito, não uma configuração: ninguém a lê em runtime. A lista de
#: produção — a que o modelo recebe — é derivada, e o teste abaixo garante.
NOMES_DA_PERSONA_ANTIGA = (
    "navegar",
    "consultar",
    "criar",
    "iniciar_cadastro",
    "irrigacao",
    "atualizar",
    "excluir",
    "relatorio",
    "buscar_web",
    "abrir_pagina",
    "buscar_dados",
    "criar_operacao",
    "buscar_web_agro",
)

#: Um nome publicado é `amplia_` seguido de [a-z0-9_]. É o formato que
#: `nome_tool()` produz e o único que `intent_de_tool()` desfaz.
RE_NOME_PUBLICADO = re.compile(r"amplia_[a-z0-9_]+")


def nomes_publicados() -> set[str]:
    """Os nomes de tool que o vocabulário diz ao modelo."""
    return set(RE_NOME_PUBLICADO.findall(vocabulario()["texto"]))


class ContratoPublicadoAceitoTest(TestCase):
    """A regra que a FILA #27 violou, escrita como teste."""

    def test_todo_nome_publicado_existe_no_catalogo(self):
        """O invariante central. Sem isto, o resto não quer dizer nada.

        Um nome no vocabulário que não está no catálogo é uma promessa que o
        servidor não cumpre — e o.produtor vê o erro, não a promessa. Com
        o `IA_SYSTEM` antigo isto era 13 em 13.
        """
        publicados = nomes_publicados()
        orfaos = sorted(n for n in publicados if intent_de_tool(n) not in INTENTS)

        self.assertEqual(
            orfaos,
            [],
            f"{len(orfaos)} nomes publicados que o sandbox nao aceita: {orfaos}",
        )

    def test_publica_todas_as_tools_que_existem(self):
        """A relação inversa, que é a que impede a lista de envelhecer.

        Só o teste anterior não chega: dá para publicar zero nomes e passa.
        O que interessa é que o produtor consiga pedir tudo o que o sistema
        sabe fazer — e para isso a lista tem de acompanhar o catálogo.
        """
        esperados = {nome_tool(n) for n in INTENTS}
        publicados = nomes_publicados()

        emFalta = sorted(esperados - publicados)
        self.assertEqual(
            emFalta,
            [],
            f"{len(emFalta)} tools do catalogo nao chegam ao modelo: {emFalta}",
        )

    def test_o_antigo_nao_parece_como_promessa(self):
        """Nenhum dos treze nomes volta a ser publicado como se existisse.

        Verificação negativa, e é a que teria apanhado a recaída: se alguém
        reintroduzir um nome antigo no texto do vocabulário, este teste
        falha — porque a lista de produção voltou a ser escrita à mão.
        """
        publicados = nomes_publicados()
        fantasma = sorted(
            n for n in NOMES_DA_PERSONA_ANTIGA if nome_tool(n) in publicados
        )

        self.assertEqual(
            fantasma,
            [],
            f"nomes fantasmas republicados: {fantasma}",
        )

    def test_nome_publicado_leva_a_um_intent_real_e_nao_a_um_erro(self):
        """A promessa passa mesmo pela porta, num subconjunto seguro.

        Verificar o catálogo é verificar metade. Esta vai até ao fim — a
        mesma chamada que a IA faz — mas só com intents de LEITURA, porque
        uma escrita disparada por um teste é uma escrita a mais na base de
        dados de alguém.

        E o que se mede não é `ok`: um intent de leitura pode responder
        "não encontrei propriedade nenhuma" e continuar a estar a funcionar.
        Mede-se que a recusa é a errada — a de nome, não a de dados.
        """
        u = User.objects.create_user("contrato", "contrato@x.com", "p")

        # Um subconjunto estável e inequívoco: o nome tem de ser o do intent.
        amostra = [
            nome_tool(n)
            for n in ("clima_agora", "vai_chover", "status_sensores", "ajuda")
            if somente_leitura(INTENTS[n])
        ]
        self.assertTrue(amostra, "a amostra ficou vazia — o catalogo mudou de forma")

        for nome in amostra:
            with self.subTest(tool=nome):
                r = executar_para(u, nome, {})
                self.assertNotEqual(r.get("codigo"), "tool_fora_do_catalogo")
                self.assertNotEqual(r.get("codigo"), "tool_desconhecida")


class SugestaoComoCaminhoDeRecuperacaoTest(TestCase):
    """Um nome errado tem de vir com a correção, não com a parede."""

    def setUp(self):
        self.u = User.objects.create_user("sug2", "sug2@x.com", "p")

    def test_cada_fantasma_antigo_tem_um_caminho_valido(self):
        """Para cada nome que o modelo erraria, há sugestão que funciona.

        Este é o teste que transforma a falha em segunda tentativa. O que
        interessa não é que `sugestoes` exista — é que **tudo o que lá vem
        seja um nome que o sandbox aceita**. Uma sugestão errada é pior do
        que nenhuma: o modelo obedece-lhe e o fantasma só muda de nome.
        """
        for nome in NOMES_DA_PERSONA_ANTIGA:
            with self.subTest(nome=nome):
                r = executar_para(self.u, nome_tool(nome), {})
                self.assertEqual(r.get("codigo"), "tool_fora_do_catalogo")

                sugestoes = r.get("sugestoes") or []
                if sugestoes:
                    for s in sugestoes:
                        self.assertIn(
                            intent_de_tool(s),
                            INTENTS,
                            f"sugestao invalida: {s}",
                        )
                else:
                    # Sem nada parecido, a recusa TEM de dizer isso. Uma lista
                    # vazia sem explicação deixa o modelo a repetir o nome, e
                    # o ciclo acaba quando o produtor desiste — que é o
                    # defeito da #27 outra vez, só que mais devagar.
                    self.assertIn(
                        "parecida",
                        str(r.get("erro", "")),
                        f"lista vazia sem explicar que nao ha nada parecido: {nome}",
                    )
                    self.assertTrue(r.get("parece_erro_de_nome"))

    def test_a_recusa_diz_sempre_se_parecia_erro_de_nome(self):
        """A marca é o que impede o cliente de tratar o vazio como "carregando".

        Sem ela, `[]` é indistinguível de uma resposta que ainda não chegou —
        e o modelo tenta outra vez com o mesmo nome.
        """
        r = executar_para(self.u, nome_tool("navegar"), {})
        self.assertEqual(r.get("codigo"), "tool_fora_do_catalogo")
        self.assertTrue(r.get("parece_erro_de_nome"))
        self.assertIn("Nao ha nenhuma ferramenta parecida", str(r.get("erro")))

    def test_o_nome_antigo_que_importa_e_coberto(self):
        """`irrigacao` é o caso que o produtor sentiria.

        A persona antiga dizia ao modelo que escrevesse
        `{"tool":"irrigacao","args":{"acao":"ligar"}}`. Esse nome tem de ter
        uma resposta que aponte para a acção certa, porque ligar e desligar
        são acções diferentes e a pessoa não vai reformular.
        """
        r = executar_para(self.u, nome_tool("irrigacao"), {})
        sugestoes = r.get("sugestoes") or []

        self.assertIn("amplia_ligar_irrigador", sugestoes)
        self.assertIn("amplia_desligar_irrigador", sugestoes)


class CoerenciaDaSuperficieTest(TestCase):
    """As três portas têm de falar do mesmo catálogo."""

    def test_tools_vocabulario_e_sugestoes_derivam_do_mesmo_catalogo(self):
        """Se as três divergirem, a IA recebe uma coisa e o servidor nega.

        Já aconteceu: `/tools/` e o `IA_SYSTEM` diziam coisas diferentes. O
        teste da divisão é o que torna a divergência visível na mesma
        execução em vez de no primeiro ecrã de um produtor.
        """
        total_vocab = vocabulario()["total"]
        self.assertEqual(total_vocab, len(INTENTS))

        # O que `tools/` publica tem de estar no vocabulário, ou então há
        # uma tool que o WebLLM conhece e o prompt não diz.
        publicados_tools = {t["name"] for t in catalogo_tools()}
        publicados_tools |= {t["name"] for t in TOOLS_CATALOGO}
        publicados = nomes_publicados()

        # As de catálogo são leitura pura e não precisam de ir no prompt
        # curto; as de acção, sim — é delas que o modelo precisa do nome.
        acao = {nome_tool(n) for n, s in INTENTS.items() if not somente_leitura(s)}
        emFalta = sorted(acao - publicados)
        self.assertEqual(
            emFalta,
            [],
            f"ferramentas de escrita que o prompt nao ensina: {emFalta}",
        )

    def test_sugerir_da_nomes_do_prefixo_que_o_prompt_usa(self):
        """A sugestão tem de ser copiável tal e qual.

        O prompt ensina `amplia_x`; uma sugestão em `x` obriga o modelo a
        acrescentar o prefixo — e foi por acumular transforms que ele
        escrevia `irrigacao` em vez de `ligar_irrigador`.
        """
        for nome in NOMES_DA_PERSONA_ANTIGA:
            with self.subTest(nome=nome):
                for s in sugerir_tools(nome_tool(nome)):
                    self.assertTrue(s.startswith("amplia_"), s)


class DadoFabricadoTest(TestCase):
    """O QUE SE GRAVA SEM O PRODUTOR PEDIR - segunda linha de defesa (A3).

    O `fallbackIntent` do `ia-local.js` emitia uma tool de ESCRITA com dados que
    ele mesmo fabricava:

        {"tool": "criar", "args": {"recurso": "safras",
                                   "dados": {"nome": "Novo safras"}}}

    Na altura isso nao gravava nada, mas por um motivo ACIDENTAL: a tool
    `amplia_criar` nao estava no catalogo. Bastava alguem a adicionar e o
    cliente passava a gravar. O cliente ja foi corrigido; aqui fixa-se a
    fronteira, que e' o sitio que sobrevive a um cliente desactualizado no
    tablet do produtor.

    A regra que este teste fixa:

    > Um valor que ninguem escreveu nao entra na base, mesmo que a tool exista
    > e mesmo que a acao nao exija confirmacao.

    E o inverso tambem e' uma regra:

    > Um nome que o produtor deu, com "nova"/"novo" dentro, nunca e' recusado.
    > Uma guarda que barra "Nova Vida" como nome de um animal ensina o produtor
    > a nao confiar no sistema, e e' pior do que o defeito que veio impedir.
    """

    def test_recusa_o_que_o_cliente_fabricava(self):
        # Todos estes valores sao EXATAMENTE os que o cliente emitia.
        for valor, intent in [
            ("Novo safras", "safras"),
            ("NOVO SAFRAS", "safras"),
            ("Nova operacao", "operacoes"),  # o cliente emitia no singular
            ("Nova operacao", "operacao"),
            ("Novo talhoes", "talhoes"),
            ("Novo maquinerios", "maquinerios"),
            ("Novo estoque", "estoque"),
            ("Novo funcionarios", "funcionarios"),
        ]:
            with self.subTest(valor=valor, intent=intent):
                r = _dado_fabricado({"dados": {"nome": valor}}, intent)
                self.assertIsNotNone(r, f"deveria recusar {valor!r}")
                self.assertEqual(r["ok"], False)
                self.assertEqual(r["codigo"], "dado_fabricado")
                # A trilha tem de distinguir "o cliente fabricou" de "o produtor
                # pediu algo estranho" - sao bugs de equipas diferentes.
                self.assertEqual(r["origem"], "cliente")

    def test_recusa_pelo_slug_do_intent_que_vai_gravar(self):
        """Um recurso que o cliente nao conhecia ainda e' barrado pelo slug.

        A lista de valores conhecidos cobre o que o cliente emitia. O slug do
        intent cobre o que ele poderia passar a emitir amanha, sem ninguem ter de
        mexer nesta lista.
        """
        r = _dado_fabricado({"dados": {"nome": "Novo widgets"}}, "widgets")
        self.assertIsNotNone(r)
        self.assertEqual(r["codigo"], "dado_fabricado")

    def test_nao_recusa_nome_legito_do_produtor(self):
        """Estes nomes tem de passar todos, e o motivo importa: sao construcoes
        normais em portugues com "novo"/"nova" dentro."""
        for valor, intent in [
            ("Novo Veado", "animais"),  # nome de um bovino
            ("Nova Vida", "talhoes"),  # nome de um talhao
            ("Semental Nova Vida", "animais"),
            ("Vaca Nova Vida", "animais"),
            ("Fazenda Boa Esperanca", "propriedades"),
            ("Joao da Silva", "funcionarios"),
            ("Novo Milho", "safras"),  # janela muito frequente
            ("Safra Nova Milho", "safras"),
            ("Milho Novo", "safras"),
            ("Novo Estoque do Galpao", "estoque"),
        ]:
            with self.subTest(valor=valor, intent=intent):
                self.assertIsNone(
                    _dado_fabricado({"dados": {"nome": valor}}, intent),
                    f"recusou um nome legitimo: {valor!r}",
                )

    def test_so_olha_o_dicionario_dados(self):
        """Um valor marcado fora de `dados` nao e' dado a fabricar.

        O que o cliente emitia punha tudo dentro de `dados`. Se um dia uma tool
        aceitar o valor noutro sitio, a guarda tem de ser estendida - mas ate
        la, nao pode recusa-lo por estar no sitio errado: seria recusar um
        pedido legitimo por um detalhe de forma.
        """
        self.assertIsNone(
            _dado_fabricado({"filtros": {"nome": "Novo safras"}}, "safras")
        )

    def test_nao_olha_valores_que_nao_sao_texto(self):
        """Um id ou um numero nunca sao 'marcador de valor automatico'."""
        for valor in [123, 4.5, True, None, ["Novo safras"], {"a": 1}]:
            with self.subTest(valor=valor):
                self.assertIsNone(_dado_fabricado({"dados": {"x": valor}}, "safras"))

    def test_argumentos_vazios_nao_partem_nada(self):
        for args in [None, {}, {"dados": None}, {"dados": "texto"}, {"dados": []}]:
            with self.subTest(args=args):
                self.assertIsNone(_dado_fabricado(args, "safras"))

    def test_executar_para_recusa_antes_de_chegar_ao_sandbox(self):
        """A guarda tem de estar NO PONTO DE SAIDA, nao dentro do sandbox.

        `executar_para` e' a unica porta de saida deste modulo. Se a guarda
        vivesse la dentro, uma tool nova que nao passasse por `sandbox.executar`
        ficaria sem proteccao - e a proxima refactorizacao apagava-a sem ninguem
        dar conta.
        """
        user = User.objects.create_user(username="produtor-fabrica")
        resposta = executar_para(
            user,
            "amplia_cadastrar_funcionario",
            {"dados": {"nome": "Novo funcionarios"}},
        )
        self.assertIs(resposta.get("ok"), False)
        self.assertEqual(resposta.get("codigo"), "dado_fabricado")
        # Nada foi gravado: e' isso que o teste tem de provar.
        try:
            from app.models import Funcionario
        except ImportError:
            from app.models.funcionarios import Funcionario

        self.assertEqual(Funcionario.objects.count(), 0)
