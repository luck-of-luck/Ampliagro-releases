"""Regra determinista, em vez de uma constante.

O que este teste impede: voltar a `startswith("INTENTS")` e voltar a perder
o `comparativo_revisao` — sem ninguem dar por isso, porque a capacidade
continua a funcionar (o `intents.py` importa-a) e so a LISTA muda.

O teste antigo (`test_o_prefixo_agarraria_o_nome`) trata da regra do NOME
DO MODULO (`intents_comparativo` e' um catalogo?). Esta trata da regra do
NOME DO ATRIBUTO (`INTENT_COMPARATIVO_REVISAO` e' um catalogo?) — e e' essa
que estava errada.

MEDIDO 2026-10-05, antes da correccao:

    so_registro       REGISTO= 85   comparativo_revisao=True
    intents_primeiro  REGISTO= 84   comparativo_revisao=False   <-- perdia 1

Depois: 85 nas 11 ordens de import testadas.

A razao de o filtro ser `INTENT` e nao `INTENTS`: todos os catalogos
existentes comecam por `INTENTS`, e o unico que comeca so por `INTENT` e'
precisamente o que estava a ser ignorado. Um filtro mais largo nao quebra
nenhum catalogo bom; um mais estreito perde um.
"""

import importlib
import unittest

from app.ia import registro


class OPrefixoDoCatalogoTest(unittest.TestCase):
    def test_o_prefixo_agarra_intent_sem_s(self):
        """O caso exacto que estava partido.

        `INTENT_COMPARATIVO_REVISAO` comeca por `INTENT` e nao por `INTENTS`.
        Com o filtro antigo, este dicionario nao era recolhido e o registo
        perdia a capacidade — mas so quando `app.ia.intents` ainda nao tinha
        corrido a linha que a junta.
        """
        self.assertEqual(
            registro._PREFIXO_CATALOGO,
            "INTENT",
            "o prefixo voltou a ser `INTENTS` (ou outra coisa). "
            "`INTENT_COMPARATIVO_REVISAO` deixa de ser reconhecido e "
            "`comparativo_revisao` volta a depender da ordem de import.",
        )
        self.assertTrue(
            "INTENT_COMPARATIVO_REVISAO".startswith(registro._PREFIXO_CATALOGO)
        )

    def test_o_prefixo_ainda_agarra_todos_os_catalogos_reais(self):
        """Alargar o filtro não pode perder nenhum dos catálogos bons.

        Um filtro largo demais é um defeito novo: passaria a recolher
        dicionários que não são catálogos. Este teste lista os reais, para
        que a alargadura não chegue a tocar em nenhum.
        """
        for nome in (
            "INTENTS",
            "INTENTS2",
            "INTENTS3",
            "INTENTS4",
            "INTENTS_DINAMICO",
            "INTENTS_IOT",
            "INTENTS_PROATIVO",
            "INTENTS_CHAMADO",
            "INTENT_COMPARATIVO_REVISAO",
        ):
            with self.subTest(atributo=nome):
                self.assertTrue(nome.startswith(registro._PREFIXO_CATALOGO))

    def test_o_catalogo_do_comparativo_e_recolhido(self):
        """`_modulos_catalogo()` tem de ver `intents_comparativo` por si só.

        Antes, ele só aparecia pelo `INTENTS.update(...)` do agregador — e
        esse caminho só existe depois de o agregador acabar de executar.
        """
        achados = dict(registro._modulos_catalogo())
        self.assertIn(
            "intents_comparativo.INTENT_COMPARATIVO_REVISAO",
            achados,
            "o catálogo do comparativo não é recolhido. A capacidade só "
            "chega ao registo pelo agregador, e isso é uma dependência de "
            "ordem de importação disfarçada de desenho.",
        )
        self.assertIn(
            "comparativo_revisao",
            achados["intents_comparativo.INTENT_COMPARATIVO_REVISAO"],
        )


class ORegistoEDeterministicoTest(unittest.TestCase):
    """O registo tem de dar a mesma resposta a quem perguntou primeiro."""

    def test_o_registo_nao_depende_da_ordem_de_importacao(self):
        """Medido dentro do mesmo processo, por construção do registo.

        A versão forte deste teste — importar em 11 processos separados e
        comparar contagens — precisa de subprocessos e de Django de pé em
        cada um, e não cabe num `unittest`. Aqui verifica-se a condição que
        a torna verdadeira: o registo cobre TUDO o que os catálogos do disco
        declaram, sem depender do agregador.
        """
        declarado = set()
        for _catalogo, intents in registro._modulos_catalogo():
            declarado |= set(intents)
        self.assertFalse(
            declarado - set(registro.REGISTO),
            "entradas declaradas por catálogos e ausentes do registo: "
            f"{sorted(declarado - set(registro.REGISTO))}",
        )

    def test_a_entrada_que_dependia_da_ordem_esta_la(self):
        """Nomeado, para a regressão ser legível sem histórico de git."""
        self.assertIn(
            "comparativo_revisao",
            registro.REGISTO,
            "`comparativo_revisao` ausente do registo. Antes da correção só "
            "entrava pelo `INTENTS.update()` do agregador — e perdia-se "
            "sempre que alguém importasse `app.ia.intents` primeiro.",
        )

    def test_a_reconstrucao_nao_poe_nada_a_faltar(self):
        """`por_flag()` é o leitor que decide se uma intent escreve ou lê.

        A docstring de `por_flag` regista que ele reconstrói o registo quando
        este fica atrasado. A garantia que importa: depois de correr, não
        há buraco.
        """
        registro.por_flag()
        declarado = set()
        for _catalogo, intents in registro._modulos_catalogo():
            declarado |= set(intents)
        self.assertFalse(
            declarado - set(registro.REGISTO),
            "depois de `por_flag()` ainda faltam entradas: "
            f"{sorted(declarado - set(registro.REGISTO))}",
        )


if __name__ == "__main__":
    unittest.main()
