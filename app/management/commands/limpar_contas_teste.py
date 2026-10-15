"""Contas de teste que ficaram no banco de DESENVOLVIMENTO.

Uso
---
    python manage.py limpar_contas_teste            # só lista (dry-run)
    python manage.py limpar_contas_teste --apagar   # apaga, com backup antes

O PROBLEMA QUE ISTO RESOLVE
---------------------------
Um teste que herda `unittest.TestCase` em vez de `django.test.TestCase`
não tem rollback nem banco isolado: o `create_user("ctx")` grava no
`db.sqlite3` de DESENVOLVIMENTO. E nao é uma hipótese — aconteceu nesta
base (ver FILA #54 em `docs/COORDENACAO_IA.md`), e o efeito é pior do que
a conta a mais:

* a 2.ª execução do teste falha com `UNIQUE constraint failed`, por isso o
  erro aparece como "o teste está mal" e não como "o teste sujou a base";
* a base de desenvolvimento fica com contas que não pertencem a ninguém e
  que aparecem em qualquer lista de produtores;
* e o teste fica verde sem nunca ter sido verde de forma fiável.

Este comando encontra essas contas. NÃO as apaga sozinho: primeiro faz
backup, e sem `--apagar` não faz nada além de mostrar.

O QUE CONTA COMO CONTA DE TESTE
-------------------------------
Só nomes que **ninguém de produção usaria** e que **não têm negócio
associado**. Um produtor que se chame `demo` fica de fora se tiver
propriedades — o filtro de "tem negócio" é o que separa lixo de dados.

Um nome sozinho nunca chega. As três condições são juntas:

1. o nome casa um padrão de teste conhecido (`test*`, `probe*`, `ctx*`,
   `pNN`, `palco_vivo*`, `amplia_teste*`, `debug_*`, …);
2. a conta não é staff nem superuser — nobody de teste é administrador;
3. **não tem propriedade, e não é dono de nada** (`Propriedade.user`).
   Isto é o que protege o produtor real: se alguém tem talhão, safra ou
   animal, a conta fica, seja qual for o nome.

Fora disto o comando não mexe. Apagar dados de outra pessoa por causa do
nome é exactamente o tipo de erro que o resto deste repositório passou a
auditar.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

#: Nomes que só um teste cria. Deliberadamente ANCORADO no início (`^`) ou
#: no fim (`$`): `test_agenda` casa, `contestador` NÃO casa. Uma lista sem
#: âncoras apagaria um produtor chamado "Palco" só por conter "palco".
PADROES_TESTE = (
    r"^test",
    r"^debug_",
    r"^probe\d*$",
    r"^ctx\d*$",
    r"^p\d+$",
    r"^palco_vivo",
    r"^amplia_teste",
    r"^prod_teste",
    r"^prod_[0-9a-f]{6,}$",  # growers criados por seed de teste
    r"_teste$",
    r"^mecanico\.demo$",  # seed da demo, sem propriedade
)

RE = re.compile("|".join(PADROES_TESTE))


class Command(BaseCommand):
    help = "Lista (e com --apagar, remove) contas de teste do banco de dev"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apagar",
            action="store_true",
            help="apaga mesmo. Sem esta flag, o comando SÓ lista.",
        )
        parser.add_argument(
            "--sim",
            action="store_true",
            help="não pede confirmação interactiva (para uso em script)",
        )

    # ------------------------------------------------------------------
    # detecção
    # ------------------------------------------------------------------
    @staticmethod
    def _tem_negocio(user) -> bool:
        """A conta tem propriedade ou é dona de alguma coisa?"""
        try:
            from app.models import Propriedade
        except Exception:  # pragma: no cover - app sem o model
            return False
        return Propriedade.objects.filter(user=user).exists()

    def candidatos(self):
        User = get_user_model()
        achados = []
        for u in User.objects.all().order_by("date_joined"):
            nome = u.username or ""
            if not RE.search(nome):
                continue
            if u.is_superuser or u.is_staff:
                # Nobody de teste é administrador. Se for, é de alguém.
                continue
            if self._tem_negocio(u):
                continue
            achados.append(u)
        return achados

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        cands = self.candidatos()
        if not cands:
            self.stdout.write(self.style.SUCCESS("nenhuma conta de teste encontrada"))
            return

        User = get_user_model()
        self.stdout.write(
            f"{len(cands)} conta(s) de teste sem negocio no banco de desenvolvimento:"
        )
        for u in cands:
            self.stdout.write(f"  - {u.username}")

        if not options["apagar"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "dry-run: nada foi apagado. Use --apagar para apagar."
                )
            )
            return

        if not options["sim"] and not self._confirmar(cands):
            self.stdout.write("cancelado")
            return

        backup = self._backup()
        if backup:
            self.stdout.write(self.style.SUCCESS(f"backup: {backup}"))

        with transaction.atomic():
            # Por id, não por lista de usernames: entre o dry-run e o delete
            # o username pode ter mudado, e apagar "o que estava na lista"
            # depois de outra escrita é como se apaga a conta errada.
            ids = [u.pk for u in cands]
            apagadas = User.objects.filter(pk__in=ids).delete()[0]
        self.stdout.write(self.style.SUCCESS(f"apagadas {apagadas} conta(s)"))

    def _confirmar(self, cands) -> bool:
        nomes = ", ".join(u.username for u in cands[:10])
        extra = " ..." if len(cands) > 10 else ""
        resp = input(f"apagar {len(cands)} conta(s) ({nomes}{extra})? [s/N] ")
        return resp.strip().lower() in {"s", "sim", "y", "yes"}

    def _backup(self) -> str | None:
        """Cópia do ficheiro SQLite antes de apagar. Devolve o caminho."""
        try:
            db = settings.DATABASES.get("default", {})
            if db.get("ENGINE") != "django.db.backends.sqlite3":
                return None
            nome = db.get("NAME") or "db.sqlite3"
            src = Path(nome)
            if not src.is_absolute():
                src = Path.cwd() / nome
            if not src.exists():
                return None
            destino = src.with_name(src.name + ".bak antes-de-limpar-contas")
            shutil.copy2(src, destino)
            return str(destino)
        except Exception as e:  # noqa: BLE001
            self.stderr.write(f"nao foi possivel fazer backup: {e}")
            return None
