"""Gera a chave local da IA (IA_LOCAL_KEY) e grava no .env.

A chave autoriza SERVIÇOS LOCAIS (mqtt_listener, cron, scripts) no sandbox.
Nunca vai para o navegador/JS: o painel usa sessão. Não compartilhe, não logue.
"""

import pathlib
import secrets

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Gera IA_LOCAL_KEY no .env (chave só da IA local)"

    def handle(self, *args, **options):
        base = pathlib.Path(__file__).resolve().parents[3]
        env_path = base / ".env"
        key = secrets.token_urlsafe(32)
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        lines = [ln for ln in lines if not ln.startswith("IA_LOCAL_KEY=")]
        lines.append(f"IA_LOCAL_KEY={key}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"IA_LOCAL_KEY gravada no .env (uso: header X-IA-Key). "
                f"Reinicie o servidor. Chave: {key[:6]}... (guardada, não exibida)"
            )
        )
