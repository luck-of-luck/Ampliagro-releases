"""Tabela órfã: o model foi removido do código, mas a migration que o
apagaria nunca foi escrita — então a tabela fica para sempre, tanto no
SQLite de dev quanto no Postgres de produção.

Estas sete foram criadas por models que não existem mais (Fase 5 da
auditoria). Todas estavam vazias no banco de dev, exceto `app_operacao`
(13 linhas de simulação manual de aplicação de defensivos), cujos dados
foram arquivados antes:

- docs/arquivo/app_operacao_20260929.csv  (legível, para consultar)
- backups/orfas_20260929.sql              (dump completo, para restaurar)

`DROP TABLE IF EXISTS` é portátil entre SQLite e PostgreSQL e é inofensivo
em quem já não tem a tabela. Os backups `bkp_*_ghost_20260917` NÃO entram
aqui: são artefatos locais de depuração, não existem em produção.
"""

from django.db import migrations

TABELAS_ORFAS = [
    "app_filacontrole",
    "app_holding",
    "app_holding_membros",
    "app_holding_propriedades",
    "app_pesagementrega",
    "app_operacao",
    "authtoken_token",
]

SQL_DROP = "; ".join(f'DROP TABLE IF EXISTS "{t}"' for t in TABELAS_ORFAS) + ";"


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0056_alter_prescricaovra_cultura_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_DROP,
            # Recriar a tabela exigiria o DDL exato de cada backend; restaurar
            # por backup é mais honesto do que uma reversão que volta só o
            # esqueleto.
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
