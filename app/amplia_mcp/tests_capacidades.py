"""Testes de `capacidades.py` — o catálogo que a IA lê para saber o que sabe.

Este módulo tem uma história documentada de falso positivo: `ajuda`,
`listar_tarefas` e `gerar_lcdpr` já saíram como "de pessoa" porque os
exemplos diziam "equipa" ou "você". E tem um bug medido: a descrição do
intent `feedback` começa com `"INSTRUÇÃO IA (ML):"` — parênteses ANTES dos
dois-pontes — e o `startswith("INSTRUÇÃO IA:")` não casava, deixando o texto
interno vazar para o `o_que_faz`.

Os testes abaixo existem para as duas coisas não voltarem.
"""

from django.test import SimpleTestCase

from app.amplia_mcp.capacidades import (
    _RE_INSTRUCAO,
    catalogo_de_capacidades,
    indice_pessoa_maquina,
)


class PrefixoInstrucaoTest(SimpleTestCase):
    """O regex que separa a instrução ao modelo da descrição útil."""

    def test_tira_o_prefixo_com_dois_pontes(self):
        m = _RE_INSTRUCAO.match("INSTRUÇÃO IA: use para 'x'.")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(0).strip(), "INSTRUÇÃO IA:")

    def test_tira_o_prefixo_com_parenteses_antes_dos_dois_pontes(self):
        """O caso que `startswith` não apanhava.

        `feedback` começa com "INSTRUÇÃO IA (ML):". Com `startswith` ou com
        `split(":", 1)` este texto passava inteiro para o `o_que_faz`, e o
        modelo lia uma instrução de engenharia como se fosse descrição.
        """
        m = _RE_INSTRUCAO.match("INSTRUÇÃO IA (ML): usuário satisfeito ('obrigado')")
        self.assertIsNotNone(
            m, "o regex tem de apanhar o parêntese antes dos dois-pontes"
        )
        self.assertEqual(m.group(0).strip(), "INSTRUÇÃO IA (ML):")

    def test_nao_toca_em_texto_sem_prefixo(self):
        texto = "Lista automações 20 RegraAuto por porte/meio."
        self.assertIsNone(_RE_INSTRUCAO.match(texto))


class DescricaoNaoVazaTest(SimpleTestCase):
    """Nenhuma descrição publicada pode conter a instrução interna."""

    def test_nenhuma_capacidade_publicada_vaza_instrucao(self):
        cat = catalogo_de_capacidades()
        vazam = [
            c["capacidade"]
            for c in cat["capacidades"]
            if "INSTRU" in (c["o_que_faz"] or "")
        ]
        self.assertEqual(
            vazam, [], f"descrição com instrução interna exposta ao modelo: {vazam}"
        )

    def test_todas_as_intents_sao_publicadas(self):
        """Um catálogo incompleto é a falha silenciosa que o `registro.saude()`
        existe para tornar visível — aqui confirma-se pelo outro lado."""
        cat = catalogo_de_capacidades()
        self.assertEqual(cat["total"], cat["todas_as_capacidades"])


class IndicePessoaMaquinaTest(SimpleTestCase):
    """O índice que este módulo foi construído para tornar fiável."""

    #: Os três que o docstring nomeia como falso positivo histórico.
    #: `ajuda` e `criar_lembrete` não têm flags; `listar_tarefas` é `tarefa.*`;
    #: `gerar_lcdpr` é `fin.*`. Nenhum dos domínios é pessoa/coisa.
    NAO_DEVE_SER_PESSOA = ("ajuda", "listar_tarefas", "gerar_lcdpr")

    def _ids_pessoa(self):
        idx = indice_pessoa_maquina()
        return {x["capacidade"] for x in idx["pessoas"]} | {
            x["capacidade"] for x in idx["ambos"]
        }

    def test_os_tres_falsos_positivos_historicos_continuam_fora(self):
        intrusos = sorted(set(self.NAO_DEVE_SER_PESSOA) & self._ids_pessoa())
        self.assertEqual(
            intrusos,
            [],
            f"regressão: {intrusos} voltaram a ser classificados como pessoa",
        )

    def test_o_par_pessoa_maquina_esta_separado(self):
        """A distinção que o 'vaqueiro' malukesou: pessoa tem `cargo`,
        máquina tem `tipo`. `nome` é comum às duas e não pode servir."""
        idx = indice_pessoa_maquina()
        pessoas = {x["capacidade"] for x in idx["pessoas"]}
        coisas = {x["capacidade"] for x in idx["coisas"]}
        self.assertIn("cadastrar_funcionario", pessoas)
        self.assertIn("cadastrar_maquina", coisas)
        self.assertNotIn("cadastrar_funcionario", coisas)
        self.assertNotIn("cadastrar_maquina", pessoas)

    def test_talhao_e_coisa_e_nao_pessoa(self):
        idx = indice_pessoa_maquina()
        coisas = {x["capacidade"] for x in idx["coisas"]} | {
            x["capacidade"] for x in idx["ambos"]
        }
        self.assertIn("cadastrar_talhao", coisas)

    def test_o_indice_nao_e_vazio(self):
        """Um índice com uma entrada é pior do que nenhum: dá a impressão de
        estar resolvido. Medido: 3 de 80 antes, muito mais agora."""
        idx = indice_pessoa_maquina()
        total = len(idx["pessoas"]) + len(idx["coisas"]) + len(idx["ambos"])
        self.assertGreater(
            total,
            10,
            f"índice praticamente vazio ({total}) — voltou ao problema antigo",
        )

    def test_toda_a_gente_tem_funcion_no_nome(self):
        """O invariant mais forte que existe sobre este índice, e que NÃO é meu.

        Vem de `app/ia/tests_capacidades_ia.py::APessoaNaoEAMaquina`.
        "pessoa" neste índice significa registo de pessoal — e só isso. A
        primeira versão desta função punha `sanidade`, `pecuaria`, `apiario`
        e `mip` no domínio de pessoa; com isso `alerta_pragas` entrou em
        "pessoa" e esse teste foi ao vermelho.

        Está aqui também, para que a regra sobreviva a quem não leia o
        ficheiro do outro lado.
        """
        idx = indice_pessoa_maquina()
        for x in idx["pessoas"]:
            self.assertIn(
                "funcion",
                x["capacidade"],
                f"{x['capacidade']} não é cadastro de pessoa",
            )
