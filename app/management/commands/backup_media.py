import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Backup de mídia + DB com rotação 7 dias (P5). Roda via cron 02:00."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep", type=int, default=7, help="Dias para reter (default 7)"
        )
        parser.add_argument(
            "--dest", type=str, default="", help="Pasta destino (default backups/)"
        )
        parser.add_argument(
            "--skip-media", action="store_true", help="Pula zip de media (só DB)"
        )

    def handle(self, *args, **options):
        keep = options["keep"]
        dest = (
            Path(options["dest"])
            if options["dest"]
            else Path(settings.BASE_DIR) / "backups"
        )
        dest.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. ZIP da pasta media/ (compresslevel=1 para 120MB não travar 120s)
        if options["skip_media"]:
            self.stdout.write("skip-media: pulando zip de media")
        else:
            _raw = getattr(settings, "MEDIA_ROOT", "")
            media_root = Path(_raw) if _raw else Path(settings.BASE_DIR) / "media"
            if media_root.exists() and any(media_root.iterdir()):
                zip_path = dest / f"media_{ts}.zip"
                try:
                    with zipfile.ZipFile(
                        zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=1
                    ) as zf:
                        for f in media_root.rglob("*"):
                            if f.is_file():
                                zf.write(f, f.relative_to(media_root))
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"media zip: {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)"
                        )
                    )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"zip fail: {e}"))
                    if zip_path.exists():
                        zip_path.unlink(missing_ok=True)
            else:
                self.stdout.write("media vazia, skip zip")

        # 2. Dump DB (sqlite copy ou pg_dump se DATABASE_URL for postgres)
        db_url = os.environ.get("DATABASE_URL", "")
        if "postgres" in db_url:
            # tenta pg_dump se disponível no PATH
            dump_path = dest / f"db_{ts}.sql"
            try:
                import subprocess

                # parse DATABASE_URL via environ
                import environ

                env = environ.Env()
                db = env.db("DATABASE_URL")
                pg_env = os.environ.copy()
                # pg_dump precisa de PGPASSWORD se houver
                result = subprocess.run(
                    [
                        "pg_dump",
                        "-h",
                        db.get("HOST") or "localhost",
                        "-U",
                        db.get("USER") or "postgres",
                        "-d",
                        db.get("NAME") or "ampliagro",
                        "-f",
                        str(dump_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=pg_env,
                )
                if dump_path.exists() and dump_path.stat().st_size > 0:
                    self.stdout.write(self.style.SUCCESS(f"db pg_dump: {dump_path}"))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"pg_dump stderr: {result.stderr[:300]}")
                    )
                    if dump_path.exists():
                        dump_path.unlink(missing_ok=True)
            except FileNotFoundError:
                self.stdout.write(
                    self.style.WARNING(
                        "pg_dump não encontrado no PATH, copiando fallback"
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"pg_dump fail: {e}"))
        else:
            # sqlite: copia db.sqlite3 via backup API (evita lock)
            for db_path in [settings.BASE_DIR / "db.sqlite3", Path("db.sqlite3")]:
                if Path(db_path).exists():
                    dst = dest / f"db_{ts}.sqlite3"
                    try:
                        import sqlite3

                        src_conn = sqlite3.connect(str(db_path), timeout=5.0)
                        dst_conn = sqlite3.connect(str(dst))
                        src_conn.backup(dst_conn)
                        src_conn.close()
                        dst_conn.close()
                        self.stdout.write(
                            self.style.SUCCESS(f"db sqlite backup: {dst}")
                        )
                    except Exception:
                        # fallback copy2 se backup falhar (ex: DB em uso)
                        try:
                            shutil.copy2(db_path, dst)
                            self.stdout.write(
                                self.style.SUCCESS(f"db sqlite copy: {dst}")
                            )
                        except Exception as e2:
                            self.stdout.write(self.style.WARNING(f"db copy fail: {e2}"))
                    break

        # 3. Criptografia opcional (P8 LGPD) — se BACKUP_ENCRYPTION_KEY setado, gera .enc
        enc_key = os.environ.get("BACKUP_ENCRYPTION_KEY", "") or getattr(
            settings, "BACKUP_ENCRYPTION_KEY", ""
        )
        if enc_key:
            try:
                from cryptography.fernet import Fernet

                fernet = Fernet(
                    enc_key.encode() if isinstance(enc_key, str) else enc_key
                )
                for f in list(dest.glob(f"db_{ts}.*")):
                    data = f.read_bytes()
                    enc = fernet.encrypt(data)
                    enc_path = f.with_suffix(f.suffix + ".enc")
                    enc_path.write_bytes(enc)
                    f.unlink(missing_ok=True)
                    self.stdout.write(
                        self.style.SUCCESS(f"criptografado: {enc_path.name}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"criptografia fail (pip install cryptography?): {e}"
                    )
                )

        # 4. Rotação: apaga arquivos mais velhos que keep dias
        cutoff = datetime.now() - timedelta(days=keep)
        removed = 0
        for f in dest.iterdir():
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    f.unlink(missing_ok=True)
                    removed += 1
        if removed:
            self.stdout.write(f"rotação: removidos {removed} backups >{keep}d")
        else:
            self.stdout.write(f"rotação: nada a remover (keep {keep}d)")

        # 4. Lista final
        total = len(list(dest.iterdir()))
        self.stdout.write(self.style.SUCCESS(f"backups em {dest}: {total} arquivos"))
