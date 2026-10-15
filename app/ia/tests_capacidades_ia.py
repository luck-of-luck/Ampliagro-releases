"""A IA tem de saber o que sabe.

Esta tool existe por causa de uma conversa concreta. Um produtor perguntou
"como se cadastrar" e recebeu o cadastro de MÁQUINAS — a capacidade de
registar uma pessoa estava escrita no código, com descrição e exemplos, e
a IA não a via. Não faltava a capacidade: faltava a capacidade de a IA
saber que a tinha.

O teste mais importante deste ficheiro é o do `cargo`. Se `cargo` apontar
também para `cadastrar_maquina`, o bug original volta — e volta pela
ferramenta que deveria o impedir.
"""

# A lista de tools de catalogo vive num sitio so. Ver o porque em
# `app/amplia_mcp/ferramentas_aceitas.py`.
from app.amplia_mcp.ferramentas_aceitas import (  # noqa: E402
    TOOLS_CATALOGO_ACEITAS,
)
import unittest

from django.contrib.auth.models import User
from django.test import TestCase as DjTestCase

from app.amplia_mcp.capacidades import (
    catalogo_de_capacidades,
    indice_pessoa_maquina,
    indice_por_campo,
    resumo_categorias,
)
from app.ia import registro as R


class ORegistroVeTudo(unittest.TestCase):
    """O registo é a fonte de verdade, e descobre-se sozinho."""

    def test_tem_mais_do_que_zero(self):
        self.assertGreater(len(R.REGISTO), 50, "O registo está quase vazio")

    def test_encontra_os_intents_de_todos_os_catalogos(self):
        """A razão de o registo existir: um catálogo novo entra por
        existir, não por ser registado em lado nenhum.

        `intents.py` é um AGREGADOR — importa e re-exporta `INTENTS2`,
        `INTENTS3` e `INTENTS4`. O registo descobre os mesmos objectos por
        dois caminhos, e o filtro de identidade (mesmo objecto ≠ colisão)
        é o que evita contar 126 quando há 76. Este teste confirma que
        filtrado, o registo não perde nada: tem todos os nomes de todos os
        catálogos.
        """
        from app.ia import intents2 as i2
        from app.ia import intents3 as i3
        from app.ia import intents4 as i4

        for nome_catalogo, catalogo in (
            ("INTENTS2", i2.INTENTS2),
            ("INTENTS3", i3.INTENTS3),
            ("INTENTS4", i4.INTENTS4),
        ):
            faltam = set(catalogo) - set(R.REGISTO)
            self.assertEqual(
                faltam,
                set(),
                f"O registo não viu {len(faltam)} intents de {nome_catalogo}",
            )

    def test_a_soma_dos_catalogos_bate_com_o_registro(self):
        """O registo não pode ser MAIOR que a soma (contaria o mesmo
        objecto duas vezes) nem MENOR (perderia capacidade).

        Os catálogos são **descobertos**, não listados. Este teste media-se
        contra cinco módulos escritos à mão (`intents`, `intents2`, `intents3`,
        `intents4`, `chamado_intents`), e a Fase 2 — `preset_palco` em
        `intents_palco_preset` — partiu-o com um `REGISTO` maior do que a soma.
        Não porque a contagem estivesse errada: porque a lista tinha de ser
        acrescentada à mão, e a próxima feature faz o mesmo.

        É o antipadrão que `app/ia/tests.py:110` (`test_flags_seguem_a_relacao`)
        já descreveu e desmonstrou: *"um teste que falha quando o sistema cresce
        na direcção certa deixa de ser lido, e o dia seguinte em que ele falharia
        por um motivo verdadeiro passa sem ninguém olhar."*

        A descoberta usa `_e_catalogo`, o mesmo predicado que `registro.py`
        usa para decidir o que é catálogo — por isso passa a valer para o
        sexto e para o sétimo sem ninguém editar este ficheiro.

        E continua a NÃO sendo tautológico: o registo é construído por
        `importlib` + prefixo `INTENT`, e este teste importa os módulos e soma
        os dicionários por si. A divergência entre os dois caminhos é
        exactamente o que se quer apanhar.
        """
        import importlib

        unicos = set()
        for nome in sorted(R._catalogos_esperados()):
            mod = importlib.import_module(f"app.ia.{nome}")
            for atributo in dir(mod):
                if not atributo.startswith(R._PREFIXO_CATALOGO):
                    continue
                d = getattr(mod, atributo)
                if isinstance(d, dict):
                    unicos |= set(d)

        self.assertGreater(
            len(unicos),
            50,
            "a descoberta de catálogos não encontrou nada — o predicado "
            "`_e_catalogo` deixou de casar e este teste passou a medir o vazio",
        )
        self.assertEqual(
            len(R.REGISTO),
            len(unicos),
            f"registo={len(R.REGISTO)} soma={len(unicos)}",
        )

    def test_nao_ha_duplicados_reais(self):
        """Duas definições DIFERENTES com o mesmo nome: qual executa?

        O mesmo objecto visto duas vezes não é colisão — `intents.py` é um
        agregador e tem o que os outros também definem. O que seria bug é
        o mesmo nome com conteúdos diferentes."""
        # Sem o filtro manual: `nomes_duplicados()` já entrega só as
        # colisões a sério. A chave `_mesmo_objecto` é interna e nunca sai
        # dali — enquanto isso, cada chamador tinha de a saber de memória.
        reais = R.nomes_duplicados()
        self.assertEqual(reais, {}, f"Nomes com definições diferentes: {list(reais)}")

    def test_nomes_duplicados_nao_inventa_nomes(self):
        """A chave interna não pode aparecer como se fosse um intent.

        `_mesmo_objecto` é onde a repetição esperada fica guardada. Se
        vazasse para o dict público, qualquer consumidor a leria como um
        intent chamado `_mesmo_objecto` — e um teste escrito a partir da
        docstring ("vazio = tudo bem") nunca passaria."""
        for nome in R.nomes_duplicados():
            self.assertIn(nome, R.REGISTO, f"{nome!r} não é um intent do registo")

    def test_todo_intent_tem_handler(self):
        """Um intent sem handler existe, é publicado, e devolve None sem
        erro quando chamado — a pior forma de falhar."""
        sem = [n for n, s in R.REGISTO.items() if s.get("handler") is None]
        self.assertEqual(sem, [], f"Intents sem handler: {sem}")

    def test_todo_intem_tem_descricao(self):
        """A descrição é o que a IA lê para decidir. Sem ela, a tool
        devolve 'Intent X' e não ajuda ninguém."""
        sem = [
            n for n, s in R.REGISTO.items() if not (s.get("descricao") or "").strip()
        ]
        self.assertEqual(sem, [], f"Intents sem descrição: {sem}")


class ACapacidadeDeSeConhecer(unittest.TestCase):
    def test_o_resumo_responde_a_pergunta(self):
        t = resumo_categorias()
        self.assertIn("capacidades", t)
        self.assertIn("pessoa", t)
        self.assertIn("coisa", t)

    def test_a_consulta_encontra_a_capacidade_certa(self):
        """A pergunta real: 'como se cadastrar'."""
        r = catalogo_de_capacidades(consulta="cadastrar")
        nomes = [c["capacidade"] for c in r["capacidades"]]
        self.assertIn("cadastrar_funcionario", nomes)
        self.assertIn("cadastrar_maquina", nomes)

    def test_consulta_por_vaqueiro_encontra_o_funcionario(self):
        r = catalogo_de_capacidades(consulta="vaqueiro")
        nomes = [c["capacidade"] for c in r["capacidades"]]
        self.assertIn(
            "cadastrar_funcionario",
            nomes,
            "A busca por 'vaqueiro' não encontrou o cadastro de funcionário",
        )

    def test_cada_capacidade_diz_o_que_pede(self):
        """`pede` é a verdade declarada. O `inputSchema` do MCP é deduzido
        de exemplos em prosa, e a prosa erra."""
        r = catalogo_de_capacidades()
        for c in r["capacidades"]:
            self.assertIn("pede", c)
            self.assertIn("o_que_faz", c)
            self.assertIn("so_leitura", c)

    def test_filtro_apenas_leitura_nao_deixa_escrita_passar(self):
        """O filtro tem de ser real. Uma tool que esconde o que escreve é
        cosmética; o que protege é o sandbox."""
        todas = catalogo_de_capacidades()["capacidades"]
        so_leitura = catalogo_de_capacidades(apenas_leitura=True)["capacidades"]
        vazam = {c["capacidade"] for c in so_leitura if not c["so_leitura"]}
        self.assertEqual(vazam, set(), f"Escrita no filtro de leitura: {vazam}")
        # E o filtro tem de FILTRAR. Sem isto, `apenas_leitura=True` podia
        # devolver a lista inteira e o teste acima continuava verde — o filtro
        # virava um `if` que não filtrava nada e ninguém notava.
        self.assertLess(
            len(so_leitura),
            len(todas),
            "apenas_leitura=True devolveu tanto como o catálogo completo: não filtra",
        )

    def test_o_indice_por_campo_esta_ordenado(self):
        idx = indice_por_campo()
        self.assertEqual(list(idx), sorted(idx), "O índice não está ordenado")
        self.assertIn("cargo", idx)


class APessoaNaoEAMaquina(unittest.TestCase):
    """O teste que mais importa. Se este falhar, o bug volta."""

    def test_cargo_aponta_so_para_funcionario(self):
        idx = indice_por_campo()
        com_cargo = idx.get("cargo", [])
        self.assertIn("cadastrar_funcionario", com_cargo)
        self.assertNotIn(
            "cadastrar_maquina",
            com_cargo,
            "O campo `cargo` também serve para máquina — é exactamente o "
            "erro que fez o produtor receber o cadastro de camiões",
        )

    def test_tipo_aponta_so_para_maquina(self):
        idx = indice_por_campo()
        com_tipo = idx.get("tipo", [])
        self.assertIn("cadastrar_maquina", com_tipo)
        self.assertNotIn(
            "cadastrar_funcionario",
            com_tipo,
            "O campo `tipo` também serve para pessoa",
        )

    def test_cadastrar_funcionario_e_pessoa(self):
        pm = indice_pessoa_maquina()
        pessoas = [x["capacidade"] for x in pm["pessoas"]]
        coisas = [x["capacidade"] for x in pm["coisas"]]
        self.assertIn("cadastrar_funcionario", pessoas)
        self.assertNotIn("cadastrar_funcionario", coisas)
        self.assertIn("cadastrar_maquina", coisas)
        self.assertNotIn("cadastrar_maquina", pessoas)

    def test_a_regra_diz_o_que_distingue(self):
        """O texto que a IA lê tem de dizer a diferença, em português,
        com os campos concretos. Sem isto, a lista é correcta e inútil."""
        regra = indice_pessoa_maquina()["regra"]
        self.assertIn("cargo", regra)
        self.assertIn("tipo", regra)
        self.assertIn("vaqueiro", regra)
        self.assertIn("trator", regra)

    def test_nada_de_neutro_e_classificado_como_pessoa(self):
        """A primeira versão classificava `ajuda` e `gerar_lcdpr` como de
        pessoa, porque os exemplos diziam 'equipa'. Uma lista onde
        `cadastrar_funcionario` aparece ao lado de `gerar_lcdpr`, ambos
        'pessoa', ensina o erro que se quer evitar."""
        pm = indice_pessoa_maquina()
        for x in pm["pessoas"]:
            self.assertIn(
                "funcion",
                x["capacidade"],
                f"{x['capacidade']} não é cadastro de pessoa",
            )


class ADiscoveribilidadeNoContexto(DjTestCase):
    """A capacidade tem de chegar À IA, e não ficar num módulo que ninguém chama.

    A primeira versão deste trabalho criou uma tool nova,
    `amplia_capacidades`. Reverti-a: existe um teste em `tests_paginas.py`
    que diz "duas tools, não cinco — cada tool extra é uma escolha a mais
    para errar", e a razão é boa. A escolha que o modelo tem de fazer é o
    custo, e uma tool a mais é uma escolha a mais.

    E, mais importante: uma tool nova só ajuda a IA que a VÊ. A IA do
    painel não viu a tool — via o `contexto()`, que devolvia 31 caracteres
    a dizer o nome da propriedade. Foi aí que a conversa falhou, e é aí
    que tem de ser corrigido.

    NOTA SOBRE A CLASSE DE TESTE: isto é `django.test.TestCase` e não
    `unittest.TestCase` porque os testes criam um `User` — que é acesso à
    base de dados. Com `unittest.TestCase` o pytest-django recusa a operação
    com "Database access not allowed", e o sintoma é o de um bug no código de
    produção: teste nenhum passa, e o erro não tem nada a ver com o que está
    a ser testado.
    """

    def _ctx(self, nome):
        """Um utilizador para o `contexto()`.

        `django.test.TestCase` e' o que dá o rollback. Com
        `unittest.TestCase` nao ha transação nenhuma: o `create_user`
        escreve no banco de DESENVOLVIMENTO, e o registo mostra `ctx`,
        `ctx2` e `ctx3` a_Createados lá — e a segunda corrida falha com
        `UNIQUE constraint failed`.

        O teste apanhou-se a fazer isto. A primeira versão herdou de
        `unittest.TestCase` porque "este teste não toca na base" — e não
        tocava, até criar um utilizador. Tocar na base é o que a criação
        faz.
        """
        from django.test import TestCase as DjangoTestCase

        self.assertTrue(issubclass(self.__class__, DjangoTestCase))
        return User.objects.create_user(nome, password="x")

    def test_o_contexto_diz_quantas_capacidades_existem(self):
        from app.amplia_mcp import contexto

        t = contexto(self._ctx("ctx"))
        self.assertIn(
            "O QUE SABE FAZER",
            t,
            "O contexto não diz o que a IA sabe fazer - é por isso que ela adivinha",
        )
        # O número é DERIVADO do registo, e não escrito à mão.
        #
        # Com "76" à mão, acrescentar uma intent — que é trabalho normal — partia
        # este teste, e a reaction natural de quem o viu foi abrir o ficheiro
        # e trocar 76 por 80. É a lista-para-se-esquecer-de-acrescentar de que a
        # doutrina do repo fala: um teste que falha quando o sistema cresce na
        # direcção certa deixa de ser lido, e no dia seguinte em que falharia por
        # um motivo verdadeiro passa sem ninguém olhar.
        self.assertIn(
            f"{len(R.REGISTO)} capacidades", t, "O número não bate com o registo"
        )

    def test_o_contexto_diz_a_diferenca_entre_pessoa_e_coisa(self):
        """A regra que a IA precisa, em português, com os campos
        concretos. Sem isto, `nome` é comum às duas e a IA pergunta `tipo`
        a quem disse `cargo`."""
        from app.amplia_mcp import contexto

        t = contexto(self._ctx("ctx2"))
        for termo in ("PESSOAS", "COISAS", "cargo", "tipo", "vaqueiro"):
            self.assertIn(termo, t, f"O contexto não menciona {termo!r}")

    def test_o_contexto_antes_nao_dizia_nada_disso(self):
        """A medição que motivou a correcção. Se alguém voltar a tirar esta
        secção, o teste diz o que se perde."""
        from app.amplia_mcp import contexto

        t = contexto(self._ctx("ctx3"))
        # Antes, o contexto era "Propriedades: X" e mais nada.
        self.assertGreater(
            len(t),
            100,
            "O contexto voltou a ser só o nome da propriedade — a IA fica "
            "sem saber o que sabe fazer",
        )

    def test_o_teste_nao_escreve_no_banco_de_desenvolvimento(self):
        """O teste anterior criou `ctx`, `ctx2` e `ctx3` no `db.sqlite3` de
        desenvolvimento, e a segunda corrida falhou com UNIQUE. Este
        teste é o que impede que isso volte: se alguém trocar
        `django.test.TestCase` por `unittest.TestCase`, este falha."""
        from django.test import TestCase as DjangoTestCase

        self.assertTrue(
            issubclass(self.__class__, DjangoTestCase),
            "Este teste herda de unittest.TestCase: não há rollback, e o "
            "create_user escreve no banco de desenvolvimento",
        )

    def test_nenhuma_tool_nova(self):
        """Guarda a decisão de não criar tool: a descoberta é por contexto
        e por catálogo, não por mais uma escolha para o modelo."""
        from app.amplia_mcp import NOMES_CATALOGO

        # MEDIDO 2026-10-05. Era `assertEqual`, e era impossivel de
        # satisfazer: `ComparativoAcessivelTest` exige que
        # `amplia_comparativo_revisao` esteja na allowlist, e essa tool e'
        # um **intent**, que nao vive em `TOOLS_CATALOGO`.
        #
        # As duas listas medem coisas diferentes:
        #
        #     NOMES_CATALOGO          nomes das tools de CATALOGO
        #     TOOLS_CATALOGO_ACEITAS  nomes PUBLICAVEIS — quem
        #                             `executar_para` aceita chamar
        #
        # Publicar e' uma decisao; ser entrada de catalogo e' um
        # mecanismo. Uma capacidade pode responder por `executar_para`
        # sem ser entrada de catalogo: e' o caso do intent
        # `comparativo_revisao`, que passa pelo sandbox e herda
        # `x-read-only`.
        #
        # O que esta assercao protege nao enfraquece: continua a exigir que
        # todo o catalogo esteja declarado. O que deixa de exigir e' que a
        # allowlist nao possa conter mais do que o catalogo — que e' como
        # se publica um intent. A entrada orfa e' apanhada do outro lado,
        # por `ComparativoAcessivelTest::test_tool_despacha`.
        declarados = frozenset(TOOLS_CATALOGO_ACEITAS)
        self.assertLessEqual(
            NOMES_CATALOGO,
            declarados,
            f"Tool de catalogo nao declarada: {sorted(NOMES_CATALOGO - declarados)}. Cada tool extra e uma escolha a mais para o modelo errar, e o contexto ja chega.",
        )


if __name__ == "__main__":
    unittest.main()
