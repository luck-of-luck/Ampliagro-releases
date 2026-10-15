"""Tabela de cache partilhada entre processos.

O `LocMemCache` guardava o payload do painel na memória de cada processo. Com
um só processo de dev isso não se via; com o autoreload do Django, ou com o
Daphne, cada processo tinha a sua cópia — e a invalidação feita num deles
(`app/cache_painel.py`) não chegava aos outros. O sintoma era um painel que
volta ao número antigo sem que ninguém tenha escrito nada, e só de vez em
quando.

`config/settings/base.py` passou a usar `DatabaseCache`, que é partilhado por
construção e não introduz dependência nova. Esta migração cria a tabela de que
ele precisa.

A criação é feita com `RunPython` a chamar `createcachetable` pelo nome, e não
por `import`: `createcachetable` é um **comando de gestão**, não uma classe
importável — `from django.core.cache.backends.db import CreateCacheTable` dá
`ImportError`. E a migração tem de correr com a configuração em que o
`DatabaseCache` já está activo, que é a razão de o comando ser chamado em vez
de a tabela ser escrita à mão.
"""

from django.core.management import call_command
from django.db import migrations

NOME_TABELA = "cache_tabela_painel"


def _criar(apps, schema_editor):
    verboso = int(schema_editor.connection.alias == "default")
    call_command("createcachetable", NOME_TABELA, verbosity=verboso)


def _remover(apps, schema_editor):
    # O comando não sabe desfazer; a tabela é descartada directamente.
    schema_editor.execute(f"DROP TABLE IF EXISTS {NOME_TABELA}")


class Migration(migrations.Migration):
    # Depende da 0057 para ser folha única: sem isto o grafo fica com dois
    # nós-folha e o `migrate` recusa correr.
    dependencies = [("app", "0057_remove_tabelas_orfas")]

    operations = [
        migrations.RunPython(_criar, _remover),
    ]
