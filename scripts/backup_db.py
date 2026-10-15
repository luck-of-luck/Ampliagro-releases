import datetime
import subprocess
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")


def main():
    db_url = env("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")
    backup_dir = BASE_DIR / "_backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if db_url.startswith("sqlite"):
        db_path = BASE_DIR / "db.sqlite3"
        if db_path.exists():
            backup_path = backup_dir / f"backup_sqlite_{timestamp}.sqlite3"
            import shutil

            shutil.copy2(db_path, backup_path)
            print(f"Backup do SQLite concluído: {backup_path}")
        else:
            print("Arquivo db.sqlite3 não encontrado.")
    elif db_url.startswith("postgres"):
        backup_path = backup_dir / f"backup_pg_{timestamp}.sql"
        print(f"Fazendo backup do PostgreSQL para {backup_path}...")
        try:
            subprocess.run(["pg_dump", db_url, "-f", str(backup_path)], check=True)
            print("Backup PostgreSQL concluído com sucesso!")
        except Exception as e:
            print(f"Erro ao executar pg_dump: {e}")
    else:
        print("Tipo de banco de dados não suportado para backup automatizado (ainda).")


if __name__ == "__main__":
    main()
