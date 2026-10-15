"""O fixture de isolamento não pode apagar DADO — só CACHE.

O QUE ACONTECEU
===============
MEDIDO 2026-10-05. `conftest.py::_limpa_caches_de_modulo` percorre os módulos de
`app` já importados e, para qualquer atributo cujo nome comece por `_CACHE` ou
**termine** em `_CACHE`, faz `setattr(mod, attr, type(valor)())` — trocando o
conteúdo por um vazio.

`app/ia/sandbox.py` tinha `SEM_CACHE`: a lista dos intents que escrevem e que,
por isso, não podem ser servidos de cache. O nome acabava em `_CACHE`.

Sintoma medido: `app/tests_wizard_pergunta.py::test_o_intent_nao_tem_cache`
passava sozinho e falhava com os irmãos, com
`'concluir_tarefa' not found in set()`.

O primeiro conserto foi renomear para `INTENTS_SEM_CACHE` — **e não resolveu**,
porque também acaba em `_CACHE`. Só passou com `INTENTS_NAO_CACHEAVEIS`, e
depois de o tipo passar a `frozenset`.

A REGRA DESTE FICHEIRO
======================
> Uma cache é estrutura de memoização: reconstrói-se por atribuição.
> Um dado imutável é conteúdo autoral: trocá-lo por um vazio perde
> informação que ninguém sabe reconstruir.

Um padrão de nome não distingue as duas — é coincidência de grafia. O que as
distingue é o tipo, e é por isso que o fixture salta `frozenset`.

O QUE ISTO NÃO PROTEGE
=======================
Não protege uma constante mutável cujo nome acabe em `_CACHE`. Para essa, a
resposta é o nome — e é por isso que `INTENTS_NAO_CACHEAVEIS` não se chama
`..._CACHE`. Este teste avisa se alguém voltar a dar-lhe um nome de cache.
"""

import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


class OConftestNaoApagaDadoImutavel(unittest.TestCase):
    def test_o_fixture_salta_frozenset(self):
        """A regra, escrita no codigo que a executa.

        Le o `conftest.py` e confirma que `frozenset` aparece antes do
        `setattr`. Um teste que le o fonte passa a falhar no dia em que
        alguem tira a guarda — que e' mais barato que descobrir por um teste
        vermelho que.Invariant() apagou uma lista de seguranca.
        """
        fonte = (RAIZ / "conftest.py").read_text(encoding="utf-8")
        corpo = fonte.split("def _limpa_caches_de_modulo", 1)
        self.assertEqual(len(corpo), 2, "nao encontrei _limpa_caches_de_modulo")
        m = corpo[1]

        pos_guarda = m.find("isinstance(valor, frozenset)")
        pos_setattr = m.find("setattr(mod, attr")
        self.assertNotEqual(pos_guarda, -1, "a guarda de frozenset desapareceu")
        self.assertNotEqual(pos_setattr, -1, "o setattr desapareceu")
        self.assertLess(
            pos_guarda,
            pos_setattr,
            "a guarda de `frozenset` tem de vir ANTES do `setattr` — depois ja limpou",
        )

    def test_nenhuma_constante_de_politica_acaba_em_cache(self):
        """O nome nao pode voltar a mentir.

        Um atributo `frozenset` que escreva "nao mexas em mim" no nome, e que
        o fixture nao toca, e' uma constante de politica. Se o nome voltar a
        acabar em `_CACHE`, ha duas protecoes a menos — e a segunda (o tipo)
        continua a segurar, o que torna o teste verde sem o bug ter voltado
        a ser possivel.
        """
        dados_imutaveis = {}
        for nome, mod in list(sys.modules.items()):
            if not nome.startswith("app."):
                continue
            for attr in dir(mod):
                if attr.startswith("_"):
                    continue
                try:
                    valor = getattr(mod, attr)
                except Exception:
                    continue
                if isinstance(valor, frozenset) and valor:
                    dados_imutaveis[f"{nome}.{attr}"] = valor

        mal_rotulados = sorted(
            f"{n} (acaba em '{n.rsplit('.', 1)[-1][-14:]}')"
            for n in dados_imutaveis
            if n.rsplit(".", 1)[-1].endswith("_CACHE")
        )
        self.assertEqual(
            mal_rotulados,
            [],
            f"dados imutaveis com nome de cache: {mal_rotulados}. "
            "O fixture nao os apaga (o tipo protege), mas o nome volta a "
            "prometer que sao caches — e alguem vai confiar no nome.",
        )

    def test_a_lista_de_nao_cacheaveis_esta_viva(self):
        """A prova de que a protecção funciona, e de que o dado é o certo.

        Este teste corre dentro da suite, ou seja **depois** do fixture de
        isolamento de cada teste anterior. Se a lista estivesse a ser apagada,
        chegava aqui vazia — e era este o sintoma que se via no outro ficheiro.
        """
        from app.ia.sandbox import INTENTS_NAO_CACHEAVEIS

        self.assertIsInstance(INTENTS_NAO_CACHEAVEIS, frozenset)
        self.assertGreater(len(INTENTS_NAO_CACHEAVEIS), 20)
        for esperado in ("concluir_tarefa", "criar_entidade", "inserir_registro"):
            with self.subTest(intent=esperado):
                self.assertIn(
                    esperado,
                    INTENTS_NAO_CACHEAVEIS,
                    "um intent que escreve ficou de fora da lista de "
                    "não-cacheaveis — o isolamento pode ter apagado",
                )
