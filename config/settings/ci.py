"""
Settings de CI: as migrate's MESMAS, e a base num ficheiro.

POR QUE ISTO EXISTE
===================

MEDIDO 2026-10-06. Tres checks vermelhos no PR #40, e as tres causas sao
uma so: o CI corria comandos de gestao com `config.settings.test`, que tem
`MIGRATION_MODULES = DisableMigrations()` e `NAME: ":memory:"`.

  * `manage.py migrate` nao criava tabela nenhuma — o modulo de migracoes esta
    desactivado, por desenho, para o `pytest` ser rapido.
  * mesmo que criasse, `:memory:` morre com o processo.
  * o passo seguinte, `criar_conta_demo`, abre um processo NOVO e recebe uma
    base vazia: `no such table: auth_user`. A migracao tinha "passado".

E havia uma terceira camada por cima: a instalacao no CI era
`pip install -r requirements.txt || <oito pacotes> || true`. O `|| true`
tapava a falha do manifesto, o fallback instalava oito pacotes, e o
`structlog>=23.0,<24.0` que esta em `requirements.txt:211` nunca chegava a
ser instalado. O primeiro sintoma era `ModuleNotFoundError: No module named
'structlog'`; a causa era a rede de seguranca.

O QUE ESTE FICHEIRO FAZ, E O QUE NAO FAZ
========================================

Faz: herda de `test.py` (o mesmo `SECRET_KEY` de teste, os mesmos hashers
rapidos) e DESTRUI as duasOptimizacoes que so servem ao `pytest`.

  * `MIGRATION_MODULES` volta a ser o do Django: as migracoes correm. E' o que
    `manage.py migrate` precisa.
  * a base fica num ficheiro, para `migrate` e `criar_conta_demo` verem a
    MESMA base em processos diferentes.

Nao faz: nao toca no `pytest`. `pytest-django` le `config.settings.test`,
que continua com `:memory:` e sem migracoes. Uma suite de 2811 testes que
corre em segundos vale mais do que a velocidade do `migrate`, e sao coisas
diferentes.

Nao e' settings de producao: o `SECRET_KEY` e' o de teste, herdado de
`test.py`, que ja o documenta como tal. Nao ha como este ficheiro ser usado
por engano em producao — `prod.py` nao o importa.
"""

import os
import tempfile

from .test import *  # noqa: F401,F403

# --------------------------------------------------------------------------
# 1. A base tem de sobreviver AO PROCESSO.
#
# `:memory:` vive dentro do processo. `manage.py migrate` cria as tabelas e
# perde-as a seguir; `manage.py criar_conta_demo`, no comando seguinte, abre
# um processo novo e encontra uma base vazia. E' por isso que o job `js`
# falhava com `no such table: auth_user` DEPOIS de a migracao ter saido com
# zero.
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(tempfile.gettempdir(), "ampliagro_ci.sqlite3"),
        "TEST": {"NAME": None},  # pytest nao usa este ficheiro
    }
}

# --------------------------------------------------------------------------
# 2. As migracoes tem de CORRER.
#
# `test.py` põe `MIGRATION_MODULES = DisableMigrations()`, e o comentario de
# `app/ia/tests_palco.py:216` explica por que: a migration 0054 cria uma
# linha de DADOS (`0054_palco_ia_build5.RunPython`), e um teste que dependesse
# dela mediria uma coisa que o ambiente de teste apaga de proposito.
#
# Este ficheiro e' o outro lado dessa decisao. Aqui o comando e' `migrate`, e
# um `migrate` que nao migra e' um comando que mente.
#
# Um dicionario VAZIO, e nao `None`. MEDIDO: `MIGRATION_MODULES = None` rebenta
# com `TypeError: argument of type 'NoneType' is not iterable` em
# `migrations/loader.py:67`, que faz `if app_label in settings.MIGRATION_MODULES`.
# O Django consulta a chave, portanto um dicionario vazio e' o valor que diz
# "nao ha nenhum modulo substituido" — que e' o que queremos.
# --------------------------------------------------------------------------
MIGRATION_MODULES = {}
