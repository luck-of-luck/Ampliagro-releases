"""Pacote `tests`.

PORQUE ESTE FICHEIRO EXISTE
==========================

`tests/` tem ficheiros que importam uns os outros por caminho ABSOLUTO:

    from tests.lcpr_fixtures import propriedade_com_imoveis

Sem um `__init__.py`, `tests/` nao e' um pacote: o Python nao consegue resolver
`tests.lcpr_fixtures` e o pytest falha na COLECAO com

    ModuleNotFoundError: No module named 'tests.lcpr_fixtures'

Nao e' um problema de caminho nem de `sys.path` — os tres ficheiros estao lado a
lado, e o `lcpr_fixtures.py` existe. E' o pacote que nao existe.

MEDIDO 2026-10-05. Tres suites (`test_lcdpr_conformidade`, `test_lcdpr_q100_coerencia`,
`test_lcdpr_um_ficheiro` = 22 testes) davam `ERROR` na coleccao por isto, e nao
por defeito no LCDPR. A confusao era o oposto do habitual: os testes pareciam
quebrados quando o que estava quebrado era a coleccion.

Este ficheiro e' a correccao mais barata possivel: uma linha de convencao Python
que torna `tests/` importavel. Nao esconde nada e nao muda o comportamento de
nenhum teste — so faz o import que os testes ja faziam resolver.
"""
