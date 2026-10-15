"""Trava a limpeza da Fase 5.

O perigo desta migration é ela mesma: `DROP TABLE` em migration vai para
produção no próximo `migrate`, e o nome da tabela está escrito à mão. Estes
testes existem para que uma edição futura da lista não derrube tabela de
model vivo em silêncio.
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
from django.apps import apps

RAIZ = Path(__file__).resolve().parent.parent
MIGRATION = importlib.import_module("app.migrations.0057_remove_tabelas_orfas")

# O que a auditoria encontrou: seis tabelas de model removido, mais
# app_operacao (dados arquivados em docs/arquivo/).
ORFAS_ESPERADAS = {
    "app_filacontrole",
    "app_holding",
    "app_holding_membros",
    "app_holding_propriedades",
    "app_pesagementrega",
    "app_operacao",
    "authtoken_token",
}


def test_migration_cobre_exatamente_as_orfas_conhecidas():
    assert set(MIGRATION.TABELAS_ORFAS) == ORFAS_ESPERADAS


def test_migration_nao_dropa_tabela_de_model_vivo():
    """O invariante que importa: nenhum model pode usar esses nomes."""
    vivas = {m._meta.db_table for m in apps.get_models(include_auto_created=True)}
    assert not (set(MIGRATION.TABELAS_ORFAS) & vivas), (
        "a migration passaria a dropar tabela de um model vivo"
    )


def test_migration_nao_inclui_artefato_local_de_depuracao():
    """bkp_*_ghost_* só existe na máquina de dev; prod nunca teve."""
    assert not [t for t in MIGRATION.TABELAS_ORFAS if t.startswith("bkp_")]


def test_sql_usa_if_exists_para_ser_idempotente():
    sql = MIGRATION.SQL_DROP.upper()
    assert sql.count("DROP TABLE IF EXISTS") == len(ORFAS_ESPERADAS)


def test_ferramenta_relata_sem_remover():
    """Dry-run: sai com 0 e diz que não removeu nada (não escreve no banco)."""
    proc = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "limpar_tabelas_orfas.py")],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "nada foi removido" in proc.stdout


def test_ferramenta_rejeita_opcao_inexistente():
    proc = subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts" / "limpar_tabelas_orfas.py"),
            "--nao-existe",
        ],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        timeout=300,
    )
    assert proc.returncode != 0


@pytest.mark.parametrize(
    "flag", ["--executar", "--incluir-backups", "--forcar-com-dados"]
)
def test_ferramenta_expoe_as_flags_de_risco(flag):
    """As três saídas destrutivas precisam existir e ser explícitas."""
    proc = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "limpar_tabelas_orfas.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        timeout=300,
    )
    assert proc.returncode == 0
    assert flag in proc.stdout
