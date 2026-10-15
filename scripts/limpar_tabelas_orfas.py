"""Lista (e opcionalmente remove) tabelas órfãs do banco.

Órfã = existe no banco, mas nenhum model Django a declara. Nasce quando um
model é removido e a migration que o_dropou nunca foi escrita: a tabela
fica para sempre, no SQLite de dev e no Postgres de produção.

Uso:
    python manage.py shell < scripts/limpar_tabelas_orfas.py          # só relatório
    python scripts/limpar_telas_orfas.py --executar                    # remove
    python scripts/limpar_tabelas_orfas.py --executar --incluir-backups

Padrão é relatório: nada é removido sem --executar. Tabelas com dados são
separadas das vazias no relatório, porque remover uma com conteúdo é
decisão de quem conhece o negócio — a ferramenta não adivinha.
"""

import argparse
import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import django

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402

# Tabelas que o Django gerencia e que não pertencem a nenhum model.
GERENCIADAS = {
    "django_migrations",
    "django_session",
    "django_content_type",
    "django_admin_log",
    "django_auth_permission",
    "sqlite_sequence",
    "spatial_ref_sys",
}
GERENCIADAS_PREFIXO = ("django_celery_beat_",)


def tabelas_do_banco():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s"
            if connection.vendor == "postgresql"
            else "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return [r[0] for r in cur.fetchall()]


def tabelas_de_model():
    nomes = set()
    for model in apps.get_models(include_auto_created=True):
        nomes.add(model._meta.db_table)
    return nomes


def linhas(t):
    with connection.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{t}"')  # noqa: S608 — nome vem do catálogo do banco
        return cur.fetchone()[0]


def referenciada_no_codigo(nome):
    """Procura o nome da tabela no código-fonte: se algo usa SQL cru, não toca."""
    achados = []
    for pasta in ("app", "config", "scripts"):
        for py in (RAIZ / pasta).rglob("*.py"):
            if py.resolve() == Path(__file__).resolve():
                continue
            if nome in py.read_text(encoding="utf-8", errors="ignore"):
                achados.append(str(py.relative_to(RAIZ)))
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--executar",
        action="store_true",
        help="remove de fato (sem isso, só relatório)",
    )
    ap.add_argument(
        "--incluir-backups", action="store_true", help="inclui as tabelas bkp_*_ghost_*"
    )
    ap.add_argument(
        "--forcar-com-dados",
        action="store_true",
        help="remove tambem as orfas que tem linhas (so depois de conferir o CSV/dump)",
    )
    args = ap.parse_args()

    do_banco = tabelas_do_banco()
    de_model = tabelas_de_model()

    def e_backup(t):
        return t.startswith("bkp_")

    orfas = [
        t
        for t in do_banco
        if t not in de_model
        and t not in GERENCIADAS
        and not t.startswith(GERENCIADAS_PREFIXO)
        and (e_backup(t) == args.incluir_backups)
    ]

    vazias, com_dados, puladas = [], [], []
    for t in sorted(orfas):
        refs = referenciada_no_codigo(t)
        if refs:
            puladas.append((t, refs))
            continue
        (vazias if linhas(t) == 0 else com_dados).append(t)

    print(f"banco: {connection.settings_dict['NAME']}")
    print(
        f"tabelas no banco: {len(do_banco)} | de model: {len(de_model)} | órfãs: {len(orfas)}\n"
    )

    print(f"ÓRFÃS VAZIAS ({len(vazias)}) — remover sem risco:")
    for t in vazias:
        print(f"  {t}")

    print(f"\nÓRFÃS COM DADOS ({len(com_dados)}) — revisar antes:")
    for t in com_dados:
        print(f"  {t}  ({linhas(t)} linhas)")

    if puladas:
        print(f"\nIGNORADAS — o nome aparece em código ({len(puladas)}):")
        for t, refs in puladas:
            print(f"  {t}  <- {', '.join(refs)}")

    if not args.executar:
        print("\n(nada foi removido — rode com --executar para aplicar)")
        return

    alvo = list(vazias)
    if args.forcar_com_dados:
        alvo += com_dados
    elif com_dados:
        print(f"\n{len(com_dados)} tabela(s) com dados NAO foram removidas.")
        print("Se voce ja conferiu que sao redundantes, use --forcar-com-dados:")
        for t in com_dados:
            print(f"  {t}  ({linhas(t)} linhas)")

    if not alvo:
        return

    print("\n=== removendo ===")
    for t in alvo:
        with connection.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{t}"')  # noqa: S608
        print(f"  removida: {t}")


if __name__ == "__main__":
    main()
