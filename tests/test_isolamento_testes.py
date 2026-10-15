"""Carrega a fixture de isolamento do `conftest.py` da RAIZ.

`import conftest` resolve para `tests/conftest.py` quando o teste vive em
`tests/` — e aquele ficheiro **nao** tem a fixture que estes testes
verificam. Carregar o da raiz por caminho de ficheiro e' a unica forma de ter
certeza de qual se esta a ler.

Este bloco tem de ficar **antes** de qualquer `def`, porque os testes
abaixo fazem `from _conftest_raiz import ...` ao tempo de execucao.
"""

import importlib.util
import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("_conftest_raiz", _RAIZ / "conftest.py")
_conftest_raiz = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_conftest_raiz)


# ═══════════════════════════════════════════════════════════════════════════
# Nenhum teste pode herdar estado de outro.
#
# POR QUE ESTE FICHEIRO EXISTE
# MEDIDO 2026-10-05. Quatro testes passavam sozinhos e falhavam na suite
# completa: dois do `test_manifesto_confere_com_codigo.py`, um do
# `test_custo_por_talhao.py` e um do `app/tests_templates.py`.
#
# Um `pytest ficheiro.py` verde e um `pytest tests/ app/` vermelho. E o
# ficheiro pode mudar entre os dois, porque outro processo o esta a escrever.
#
# O QUE HAVIA POR TRAS
# Caches. `app/api/views/cultures.py:577` tem `_CULTURES_CONFIG_CACHE` a nivel
# de modulo, e `app/api/culture_config.py:18` usa o cache do Django
# (CACHE_KEY = "cultures_config_v2"). Nada disto e' invalidado entre testes.
#
# O segundo e' o mais serio porque e' **por `user.id`**: num SQLite recomecado,
# o primeiro utilizador e' sempre o `id` 1. Dois testes que usem utilizadores
# diferentes leem o payload um do outro.
#
# Porque e' pior do que uma falha
# Um teste que passa isolado e falha na suite ensina a **nao confiar na
# suite**. E o pior sitio possivel para aprender essa licao e' um CI: a equipa
# ve vermelho, nao sabe porque, e passa a ignorar o sinal. Foi o que aconteceu
# com `app/tests_wizard_pergunta.py` — reprovava uma guarda *mais forte* do
# que a exigida, e passou a ler-se como ruido.
#
# O QUE ESTES TESTES PROVAM
# Que a fixture `limpar_cache_entre_testes` (em `conftest.py`) existe e faz o
# que diz. Nao a chamam — verificam-na pelo **efeito**.
# ═══════════════════════════════════════════════════════════════════════════


def test_o_cache_do_django_aceita_escrever():
    """Ponto de partida: `cache.set` funciona.

    Parece tautologico e nao e. Se o backend de cache estiver mal configurado
    nos testes e a escrever no vazio, o teste de baixo passa por motivos
    errados — e uma proteccao que passa pela razao errada nao e' proteccao.
    """
    from django.core.cache import cache

    cache.set("chave_de_teste", "valor", 60)
    assert cache.get("chave_de_teste") == "valor"


def test_o_cache_nao_sobrevive_ao_teste_seguinte():
    """O teste anterior pôs `chave_de_teste`. Este tem de chegar a nao a ver.

    Este e' O teste. Sem a fixture `limpar_cache_entre_testes` do
    `conftest.py`, a cache do Django persiste entre testes e esta assertiva
    falha — que e' exactamente o sintoma dos quatro testes da Cabecera.
    """
    from django.core.cache import cache

    assert cache.get("chave_de_teste") is None, (
        "a cache do Django sobreviveu ao teste anterior. A fixture "
        "`limpar_cache_entre_testes` do conftest.py deixou de funcionar, ou "
        "alguem a removeu.\n\n"
        "Isto e' o defeito que fez quatro testes passarem isolados e "
        "falharem na suite. Sem a limpeza, quem passa a ignorar o sinal — e o "
        "sinal que se ignora e' o vermelho do CI."
    )


def test_o_cache_de_modulo_das_culturas_comeca_vazio():
    """`app/api/views/cultures.py` tem um cache a nivel de modulo.

    E' o cache mais problematico: guarda o `cultures-config.json` lido do
    disco, e um teste que escreve o JSON continua a ler o valor antigo. O
    sintoma aparece so na suite completa, e em nenhum teste isolado.
    """
    import importlib

    mod = importlib.import_module("app.api.views.cultures")
    cache_mod = getattr(mod, "_CULTURES_CONFIG_CACHE", None)
    assert not cache_mod, (
        f"`app.api.views.cultures._CULTURES_CONFIG_CACHE` ainda tem "
        f"{type(cache_mod).__name__} com conteudo. A limpeza de caches a nivel "
        "de modulo nao esta a alcanca-lo.\n\n"
        "Consequencia: um teste que escreva o `cultures-config.json` e outro "
        "que o leia veem versoes diferentes do ficheiro, e o segundo falha so "
        "na suite completa."
    )


def test_a_limpeza_respeita_caches_ja_vazios():
    """Limpar um cache que ja esta vazio nao pode rebentar.

    A fixture e' `autouse` e corre em **todos** os testes. Se levantasse
    excepcao num cache vazio, transformava um defeito de isolamento num
    `ERROR` em toda a suite — que e' pior, porque some a causa.
    """
    primeira = _conftest_raiz._limpa_caches_de_modulo()
    segunda = _conftest_raiz._limpa_caches_de_modulo()
    assert isinstance(primeira, list)
    assert isinstance(segunda, list)


def test_a_fixture_autouse_existe_no_conftest():
    """A proteccao tem de ser `autouse=True`.

    Se alguem a tornar uma fixture normal, deixa de se aplicar a quem nao a
    pede — e os quatro testes da Cabecera voltam a falhar na suite sem que
    nada diga porque.

    Le-se o **texto do ficheiro**, nao `inspect.getsource`.

    MEDIDO 2026-10-05: usava `inspect.getsource()`, que le o `__pycache__` /
    o `linecache` e levanta `OSError: lineno is out of bounds` quando o
    ficheiro mudou entre a importacao e a leitura — que e' precisamente o
    que acontece neste repositorio, com processos concorrentes a escrever.
    Um teste que rebenta por ler a fonte errada do ficheiro que quer
    verificar, nao protege o que quer proteger: e' o teste que trains a
    ignorar o vermelho.
    """
    # `_RAIZ` ja esta resolvido no topo do ficheiro. Nao se usa `inspect`.
    src = (_RAIZ / "conftest.py").read_text(encoding="utf-8")

    # O bloco da fixture, com o suficiente contexto para nao apanhar outro.
    m = re.search(
        r"@pytest\.fixture\(autouse=True\)\s*\n(?:@[^\n]*\n)*\s*def\s+"
        r"limpar_cache_entre_testes\b",
        src,
    )
    assert m, (
        "o conftest.py da raiz nao tem a fixture `limpar_cache_entre_testes` "
        "com `autouse=True`.\n\n"
        "Sem ela, quatro testes passam isolados e falham na suite — e "
        "ninguem sabe porque."
    )


def test_a_limpeza_cobre_o_cache_das_culturas():
    """A limpeza tem de alcancar o cache que causa a falha.

    Este teste **enche** o cache, chama a limpeza, e verifica que ficou vazio.
    E' o inverso do de cima: em vez de confiar que a limpeza cobre tudo,
    prova que cobre este caso especifico.
    """
    import importlib

    mod = importlib.import_module("app.api.views.cultures")
    mod._CULTURES_CONFIG_CACHE = {"grupos": [{"id": "x"}]}
    assert mod._CULTURES_CONFIG_CACHE, "pre-condicao: o cache esta cheio"

    _conftest_raiz._limpa_caches_de_modulo()

    assert not mod._CULTURES_CONFIG_CACHE, (
        "a limpeza nao alcanca `_CULTURES_CONFIG_CACHE`. Este e' o cache que "
        "fazia dois testes passarem isolados e falharem na suite."
    )
