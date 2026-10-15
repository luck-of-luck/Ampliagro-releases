"""Configuração de pytest para a RAIZ do projecto.

POR QUE ESTE FICHEIRO EXISTE, E POR QUE ESTE NÃO É O DE `tests/`
================================================================
`tests/conftest.py` carrega apenas quando se corre `pytest tests/`. A
`pytest.ini:11` diz `testpaths = tests app`, e o `-p no:cacheprovider` que uso
não muda isso — mas **`pytest app/` isolado nunca carrega o conftest de
`tests/`**, e nesse caso duas coisas acontecem:

1. **O override que protegia a base de desenvolvimento desaparece.** O
   `tests/conftest.py:20-46` explica, com Symptomas medidos, que um override
   malicioso de `django_db_setup` fez `pytest` correr contra o `db.sqlite3` de
   desenvolvimento. A protecção é boa — e só existe num lado.

2. **As fixtures desaparecem.** `user_factory`, `propriedade_factory` e as
   restantes vivem em `tests/conftest.py`. Qualquer teste em `app/` que as use
   dá erro de fixture em vez de correr.

O que este ficheiro faz
=======================
Duplica as fixtures em vez de as mover, deliberadamente. Um conftest na raiz
é carregado **em conjunto** com o de `tests/` — e o de `tests/` tem a
prioridade para os testes que estão debaixo dele. Duplicar é o que garante
que `pytest app/` isolado funciona **e** que `pytest tests/` continua a
funcionar sem uma linha alterada.

E o `DJANGO_SETTINGS_MODULE` é posto aqui, **antes** de qualquer import de
Django. Isto é o que o `MERGED.md` não corrigiu: o `tests/conftest.py:8` faz
`config.settings` — que é o **dev**. Com `pytest.ini:2` a dizer
`config.settings.test`, quem ganha depende da ordem de carregamento, e o
resultado é que `pytest app/` sem este ficheiro corre a base de DESENVOLVAMENTO
com os settings de DESENVOLVAMENTO. Um teste que passa assim não está a testar
nada.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# O path do projecto, para `config` e `app` importarem quando o cwd é outro.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# TEM de ser `.test`, e tem de ser antes de `django.setup()`. Ver a nota de
# cima: `config.settings` (dev) faz `pytest app/` correr contra a base de
# desenvolvimento.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

import django  # noqa: E402

django.setup()

import pytest  # noqa: E402


@pytest.fixture
def user_factory():
    """Cria utilizadores de teste. Duplicado de `tests/conftest.py`."""
    from django.contrib.auth.models import User

    def _create_user(username="testuser", password="testpass123", **kwargs):
        return User.objects.create_user(username=username, password=password, **kwargs)

    return _create_user


@pytest.fixture
def propriedade_factory():
    """Cria propriedades de teste. Duplicado de `tests/conftest.py`."""
    from app.models import Propriedade

    def _create(user, nome="Fazenda Teste", **kwargs):
        return Propriedade.objects.create(
            user=user,
            nome=nome,
            area_total=kwargs.pop("area_total", 100),
            **kwargs,
        )

    return _create


@pytest.fixture
def db_reset(db):
    """Garante base de teste isolada, sem substituir a fixture do pytest-django.

    Deliberadamente **não** substitui `django_db_setup`. O `tests/conftest.py:20-46`
    mediu o estrago de o fazer: `pytest` a correr contra `db.sqlite3` de
    desenvolvimento, sem rollback. Este fixture existe para tornar o
    requisito visível num lugar, e não para o contornar.
    """
    return db


# ─────────────────────────────────────────────────────────────────────────────
# O cache não sobrevive entre testes
# ─────────────────────────────────────────────────────────────────────────────
#
# MEDIDO 2026-10-05. Este é o defeito mais caro que restava na suite, e é
# silencioso.
#
# O SINTOMA
# ----------
# Quatro testes passavam sozinhos e falhavam na suite completa:
#
#   tests/test_manifesto_confere_com_codigo.py::test_john_deere_nao_tem_implementacao
#   tests/test_manifesto_confere_com_codigo.py::test_isobus_nao_tem_implementacao
#   tests/test_custo_por_talhao.py::test_o_ecra_diz_sem_medicao_e_nao_zero
#   app/tests_templates.py::ComentarioDjangoNaoVazaTest::test_nenhum_comentario_multilinha
#
# Um `pytest ficheiro.py` é verde; um `pytest tests/ app/` é vermelho. E o
# ficheiro pode mudar entre os dois, porque outro processo o está a escrever
# (ver `9.md` §0).
#
# PORQUÊ É CACHE
# --------------
# `app/api/cultures.py:590` e `app/api/utils.py:356` têm caches **a nível de
# módulo** (`_CULTURES_CONFIG_CACHE`), e `app/api/culture_config.py:18` usa o
# cache do Django (`CACHE_KEY = "cultures_config_v2"`). Nada disto é invalidado
# entre testes: o primeiro teste que carrega o config enche o cache, e todos os
# seguintes leem aquilo — incluindo os que mudaram o `cultures-config.json` no
# disco.
#
# `app/api/core.py:57` escreve `cache.set("healthz_test", "ok", 10)` num health
# check, e `user.py`/`financial.py` fazem cache de payloads por `user.id`. Dois
# testes que usem o mesmo `user.id` (que num SQLite recomeçado é sempre 1)
# partilham o payload.
#
# Porque isto é pior do que uma falha
# -----------------------------------
# Um teste que passa isolado e falha na suite treina a pessoa a **não confiar
# na suite**. E o pior sítio possível para aprender essa lição é um CI: a
# equipa vê vermelho, não sabe porquê, e passa a ignorar. Foi o que aconteceu
# com `app/tests_wizard_pergunta.py`, que reprovava uma guarda *mais forte*
# do que a exigida — e o sinal passou a ser lido como ruído.
#
# A REGRA
# -------
# Nenhum teste pode herdar estado de outro. Um teste tem de passar porque o
# código está certo, nunca porque o teste anterior deixou algo no caminho.
#
# A IMPLEMENTAÇÃO
# ---------------
# `autouse=True`, portanto aplica-se a **todos** os testes sem ninguém se
# lembrar de o pedir. Limpa:
#
#   1. o cache do Django (`django.core.cache.cache.clear()`);
#   2. os caches a nível de módulo que guardam config lida do disco.
#
# O ponto 2 não é óbvio e é o que faz este ficheiro valer a pena: sem ele, um
# teste que escreve o `cultures-config.json` e outro que o lê continuam a ver
# o valor antigo, e a falha aparece só na suite completa.
# ─────────────────────────────────────────────────────────────────────────────


def _limpa_caches_de_modulo():
    """Repõe o valor inicial de todos os caches de configuração a nível de módulo.

    MEDIDO 2026-10-05: os dois caches que provocavam a falha de ordem estão em
    `app.api.views.cultures` (`_CULTURES_CONFIG_CACHE`) e `app.api.culture_config`
    (que usa o cache do Django, já limpo por `dj_cache.clear()`).

    Não se pode fazer por lista de nomes — a lista fica desatualizada no
    momento em que alguém acrescenta um cache, e um cache novo não limpo é
    exactamente o bug que este ficheiro veio corrigir. Por isso a lista é uma
    *semente*, e depois procura-se o padrão em todos os módulos já importados de
    `app`.

    UM PADRÃO É GULOSO DEMAIS (MEDIDO 2026-10-05)
    =============================================
    O padrão original aceitava qualquer atributo cujo nome **terminasse** em
    `_CACHE`. `app/ia/sandbox.py` tinha uma constante chamada `SEM_CACHE` —
    uma lista dos intents que escrevem e que, por isso, **não** podem ser
    servidos de cache.

    O nome acabava em `_CACHE`. O fixture limpava-o. O resultado medido foi
    `app/tests_wizard_pergunta.py::test_o_intent_nao_tem_cache` a passar
    sozinho e a falhar com os irmãos, com `'concluir_tarefa' not found in
    set()`.

    O nome foi mudado para `INTENTS_NAO_CACHEAVEIS`, e **isso não resolvia**:
    a primeira tentativa, `INTENTS_SEM_CACHE`, também acaba em `_CACHE`. Só
    passou quando o nome deixou de ter esse final.

    A CORREÇÃO DE RAIZ
    ------------------
    Um padrão de nome não consegue distinguir uma cache de um dado: é uma
    coincidência de grafia. O que as distingue é o que são.

      - uma **cache** é estrutura de memoização — enche-se durante a
        execução e reconstrói-se por atribuição a partir da fonte;
      - um **conjunto de política** é dado autoral — ninguém o escreve em
        tempo de execução, e reconstruí-lo vazio perde informação sem forma
        de a recuperar.

    Por isso `_limpa_caches_de_modulo` deixa de tocar em `frozenset`. E a
    constante passou a ser `frozenset`: é imutável, que é o que um dado de
    política deve ser — ninguém a pode alterar por engano. As duas mudanças
    Together fecham o buraco: mesmo que alguém escreva `ALGUMA_COISA_CACHE`
    com dados imutáveis, o fixture não a toca.

    E se um dia um `frozenset` precisar de ser limpo entre testes, é porque
    não era um frozenset. `tests/test_conftest_nao_apaga_dado_imutavel.py`
    guarda esta regra.
    """
    import sys

    limpos = []

    # 1. Os módulos que sabemos que têm cache. Semente, não lista fechada.
    sementes = (
        "app.api.views.cultures",
        "app.api.culture_config",
        "app.api.views.utils",
    )

    # 2. Todos os módulos de `app` já importados — porque um cache pode ter sido
    #    acrescentado sem ninguém actualizar a semente.
    candidatos = set(sementes)
    for nome in list(sys.modules):
        if nome.startswith("app."):
            candidatos.add(nome)

    for nome in sorted(candidatos):
        mod = sys.modules.get(nome)
        if mod is None:
            continue
        for attr in dir(mod):
            if not (attr.startswith("_CACHE") or attr.endswith("_CACHE")):
                continue
            try:
                valor = getattr(mod, attr)
            except Exception:
                # Uma property ou descritor que levante ao ler não é um cache.
                continue
            # IMUTÁVEL É DADO, NÃO CACHE. Ver a nota da docstring: uma cache é
            # estrutura de memoização e reconstrói-se por atribuição; um
            # `frozenset` é conteúdo autoral, e trocá-lo por um vazio perde
            # informação que ninguém consegue reconstruir.
            if isinstance(valor, frozenset):
                continue
            # Só interessa um cache **preenchido**. `None` é o estado inicial.
            if isinstance(valor, (dict, list, set)) and valor:
                try:
                    setattr(mod, attr, type(valor)())
                    limpos.append(f"{nome}.{attr}")
                except Exception:
                    # Um cache com um tipo próprio (LRUCache) pode não
                    # aceitar `type(valor)()`. Não é motivo para rebentar a
                    # suite: o teste que depender dele falha de forma
                    # visível, que é o objectivo.
                    pass
            elif isinstance(valor, tuple) and valor:
                try:
                    setattr(mod, attr, ())
                    limpos.append(f"{nome}.{attr}")
                except Exception:
                    pass

    return limpos


@pytest.fixture(autouse=True)
def limpar_cache_entre_testes(request):
    """Limpa o cache antes **e** depois de cada teste.

    Antes: para o caso em que o teste anterior deixou rastro.
    Depois: para que este teste não deixe rastro para o seguinte. O "depois"
    parece redundante e não é — é o que garante que a limpeza não depende da
    ordem nem de alguém se lembrar de limpar.

    A EXCEÇÃO
    ==========
    Alguns testes **medem o cache**: `app/ia/tests_cache_decisao.py` verifica
    que um passo é registado mesmo sem cache, e `app/tests_wizard_pergunta.py`
    verifica que um intent que escreve não tem TTL. Para estes, a limpeza é o
    próprio objecto do teste, e limpá-los antes invalida a medição.

    O mechanism é o marker `@pytest.mark.keep_cache`. Sem ele, a excepção
    seria "lembra-te de pôr isto", e um teste de cache escrito sem o marker
    falha por motivos que não tem nada a ver com o que testa — que é a
    classe de defeito que este ficheiro veio eliminar.
    """
    from django.core.cache import cache as dj_cache

    manter = request.node.get_closest_marker("keep_cache") is not None

    def _limpa():
        if manter:
            return
        try:
            dj_cache.clear()
        except Exception:
            # Uma base de teste ainda não migrada pode não ter a tabela de
            # cache. Não vale a pena rebentar por isto — o objectivo é isolar
            # o cache, não validar a base.
            pass
        _limpa_caches_de_modulo()

    if manter:
        # Mesmo assim limpa **antes**: o objectivo é que o teste comece limpo,
        # não que veja o rastro do teste anterior. O que não se faz é limpar
        # no fim, porque é o estado final que o teste quer observar.
        try:
            dj_cache.clear()
        except Exception:
            pass
        _limpa_caches_de_modulo()
        yield
        return

    _limpa()
    yield
    _limpa()
