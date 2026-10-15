"""Talhões que não são da demonstração, numa base que é uma demonstração.

Uso
---
    python manage.py saneear_talhoes_demo            # só mostra (dry-run)
    python manage.py saneear_talhoes_demo --apagar   # apaga, com backup antes
    python manage.py saneear_talhoes_demo --apagar --tambem-safras

O PROBLEMA, E POR QUÉ ESTA DEMO
===============================
A "Fazenda Modelo - Primavera do Leste" foi criada por `seed_mvp_demo.py`
para uma apresentação (JOSIF/FEBRACE). O seed define QUATRO talhões —

    Talhão A - Soja .............. 420 ha
    Talhão B - Milho Safrinha ..... 380 ha
    Talhão C - Pastagem ........... 280 ha
    Reserva Legal ................. 160 ha
                                 ─────
                                 1.240 ha

— e `area_total: 1240.00`. A conta bate.

Depois, o banco foi acumulando. Testes que usam `unittest.TestCase` em vez
de `django.test.TestCase` escrevem no `db.sqlite3` de DESENVOLVIMENTO e não
façam rollback; o mesmo acontece com experiments manuais e com seeds de
funcionalidades. Resultado verificado nesta base:

    18 talhões somam 3.047 ha  numa propriedade declarada com 1.240 ha

Os 14 a mais (1.807 ha) têm nomes que ninguém põe num cadastro de produção:
`Talhão Soja Teste 2026`, `Alpisteuiu`, `Alpisteuiuooo`, `Café graudissimo`,
`Talhão Arroz Guia`. E é aí que nasceu a safra de 45.000 ha — o talhão
`Alpiste 001` (15 ha) veio de um teste de fuzz, a safra foi escrita em cima, e
o registo ficou.

O QUE ESTE COMANDO APAGA, E O QUE NÃO APAGA
===========================================
Apaga: os talhões cujo nome NÃO é um dos quatro do seed.

Não apaga, e diz que não apaga:

  * as safras. `Safra.talhao` é `SET_NULL`: o talhão vai, a safra fica. Uma
    safra que sobrevive sem talhão continua a contar a sua área — e a safra de
    45.000 ha é a razão de este comando existir. Apagar o talhão e achar que
    o problema morreu é o pior resultado possível: o painel ficaria igual, com
    a illusion de estar limpo.
    Por isso `--tambem-safras` existe, e por omissão NÃO apaga nada disso.

  * a propriedade, a `area_total`, o financeiro, o maquinário, os animais.

A REGRA QUE ESTE COMANDO HERDA
==============================
De `limpar_contas_teste.py`: **o nome sozinho nunca chega.** Aqui o critério
não é um padrão de nome, é a COMPARAÇÃO COM A LISTA DO SEED — a lista é a
definição do que é a demonstração, e um talhão novo que alguém tenha criado a
mão para testar fica FORA do alvo. Não é adivinhação: é a mesma constante que
o gerador usa.

E o aviso inverso: se a propriedade não for a do seed, o comando não faz
nada. Noutra fazenda, um talhão chamado "Guia" pode ser real.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

#: Os talhões que `seed_mvp_demo.py::TALHOES_MODELO` cria. Esta lista é a
#: definição de "o que é a demonstração" — e é a MESMA constante do gerador,
#: importada em vez de reescrita, para que as duas não possam divergir.
try:
    from app.management.commands.seed_mvp_demo import TALHOES_MODELO

    NOMES_DA_DEMO = {t["nome"] for t in TALHOES_MODELO}
    NOME_DA_DEMO = "Fazenda Modelo - Primavera do Leste"
except Exception:  # pragma: no cover - seed ausente
    NOMES_DA_DEMO = {
        "Talhão A - Soja",
        "Talhão B - Milho Safrinha",
        "Talhão C - Pastagem",
        "Reserva Legal",
    }
    NOME_DA_DEMO = "Fazenda Modelo - Primavera do Leste"


class Command(BaseCommand):
    help = "Lista (e com --apagar, remove) talhoes que nao pertencem a demo"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apagar",
            action="store_true",
            help="apaga mesmo. Sem esta flag, o comando SÓ mostra.",
        )
        parser.add_argument(
            "--tambem-safras",
            action="store_true",
            help=(
                "apaga também as safras que ficariam órfãs. SEM esta flag "
                "as safras sobrevivem (SET_NULL) e continuam a contar área."
            ),
        )
        parser.add_argument(
            "--sim",
            action="store_true",
            help="não pede confirmação interactiva (para uso em script)",
        )

    # ------------------------------------------------------------------
    def _propriedade_demo(self):
        from app.models import Propriedade

        return Propriedade.objects.filter(nome=NOME_DA_DEMO).first()

    def candidatos(self, prop):
        """Talhões da demo cujo nome não está na lista do seed."""
        from app.models import Talhao

        return [
            t
            for t in Talhao.objects.filter(propriedade=prop).order_by("id")
            if t.nome not in NOMES_DA_DEMO
        ]

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        from app.models import Safra, Talhao

        prop = self._propriedade_demo()
        if prop is None:
            self.stdout.write(
                self.style.WARNING(
                    f"não encontrei a propriedade '{NOME_DA_DEMO}'. Este "
                    "comando só age sobre a demonstração — noutra fazenda, "
                    "um talhão chamado 'Guia' pode ser real."
                )
            )
            return

        cands = self.candidatos(prop)
        if not cands:
            self.stdout.write(
                self.style.SUCCESS(
                    f"'{prop.nome}' está limpa: os talhões são os do seed."
                )
            )
            return

        ids = [t.id for t in cands]
        area_talhoes = float(
            Talhao.objects.filter(propriedade=prop).aggregate(s=Sum("area_hectare"))[
                "s"
            ]
            or 0
        )
        area_lixo = sum(float(t.area_hectare or 0) for t in cands)
        area_demo = float(
            Talhao.objects.filter(propriedade=prop, nome__in=NOMES_DA_DEMO).aggregate(
                s=Sum("area_hectare")
            )["s"]
            or 0
        )
        safras_orfas = list(
            Safra.objects.filter(talhao_id__in=ids).select_related("cultura")
        )

        self.stdout.write("")
        self.stdout.write(
            f"'{prop.nome}' (id={prop.id}) tem {Talhao.objects.filter(propriedade=prop).count()} "
            f"talhões a somar {area_talhoes:,.2f} ha, e declara {float(prop.area_total):,.2f} ha."
        )
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(f"{len(cands)} talhão(ões) que NÃO são do seed:")
        )
        for t in cands:
            n = Safra.objects.filter(talhao=t).count()
            self.stdout.write(
                f"  - id={t.id:3} {t.nome[:44]:46} {float(t.area_hectare or 0):>9,.2f} ha"
                + (f"  ({n} safra(s))" if n else "")
            )
        self.stdout.write("")
        self.stdout.write(f"  área dos talhões do seed .... {area_demo:,.2f} ha")
        self.stdout.write(f"  área a remover ............. {area_lixo:,.2f} ha")
        self.stdout.write(
            f"  área declarada ............. {float(prop.area_total):,.2f} ha"
        )
        self.stdout.write("")
        if abs(area_demo - float(prop.area_total)) < 0.01:
            self.stdout.write(
                self.style.SUCCESS(
                    "  Depois, a soma dos talhões bate com a área declarada."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"  ATENÇÃO: os talhões do seed somam {area_demo:,.2f} ha e a "
                    f"propriedade declara {float(prop.area_total):,.2f} ha. Mesmo "
                    "depois de remover, os dois não batem — a área declarada "
                    "está errada, ou falta um talhão do seed."
                )
            )

        # ── O aviso que não pode faltar ──────────────────────────────
        if safras_orfas:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("SAFRAS NESTES TALHÕES"))
            self.stdout.write(
                f"  {len(safras_orfas)} safra(s) apontam para eles. `Safra.talhao` é "
                "SET_NULL:"
            )
            for s in safras_orfas:
                self.stdout.write(
                    f"    id={s.id:3} {s.cultura.nome:18} {s.ano}  {float(s.area_plantada or 0):>12,.2f} ha"
                )
            if not options["tambem_safras"]:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        "  SEM --tambem-safras, estas safras SOBREVIVEM e continuam a\n"
                        "  contar área. A de 45.000,00 ha continua no painel. Apagar o\n"
                        "  talhão não resolve o problema — só tira a contraprova."
                    )
                )
            else:
                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        f"  COM --tambem-safras, as {len(safras_orfas)} safras são "
                        "apagadas.\n  Isto inclui a de 45.000,00 ha — e é a sua "
                        "finalidade aqui,\n  mas apaga produção e receita que "
                        "podem ser as que a demo mostra."
                    )
                )

        self.stdout.write("")
        if not options["apagar"]:
            self.stdout.write(
                self.style.WARNING(
                    "dry-run: nada foi apagado. Use --apagar para apagar "
                    "(e --tambem-safras se quiser as safras também)."
                )
            )
            return

        if not options["sim"] and not self._confirmar(cands, safras_orfas, options):
            self.stdout.write("cancelado")
            return

        backup = self._backup()
        if backup:
            self.stdout.write(self.style.SUCCESS(f"backup: {backup}"))

        with transaction.atomic():
            n_t = Talhao.objects.filter(id__in=ids).delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f"apagados {n_t} registo(s) de talhao")
            )
            if options["tambem_safras"] and safras_orfas:
                ids_s = [s.id for s in safras_orfas]
                n_s = Safra.objects.filter(id__in=ids_s).delete()[0]
                self.stdout.write(self.style.SUCCESS(f"apagadas {n_s} safra(s)"))

        novo = float(
            Talhao.objects.filter(propriedade=prop).aggregate(s=Sum("area_hectare"))[
                "s"
            ]
            or 0
        )
        self.stdout.write("")
        self.stdout.write(
            f"área dos talhões agora: {novo:,.2f} ha (declarada: {float(prop.area_total):,.2f} ha)"
        )

    # ------------------------------------------------------------------
    def _confirmar(self, cands, safras, options) -> bool:
        nomes = ", ".join(t.nome for t in cands[:6])
        extra = " ..." if len(cands) > 6 else ""
        extra_safras = (
            f"\n   e {len(safras)} safra(s) que apontam para eles"
            if options.get("tambem_safras") and safras
            else ""
        )
        resp = input(
            f"apagar {len(cands)} talhao(ões) ({nomes}{extra}){extra_safras}? [s/N] "
        )
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
            destino = src.with_name(src.name + ".bak antes-de-saneear-talhoes")
            shutil.copy2(src, destino)
            return str(destino)
        except Exception as e:  # noqa: BLE001
            self.stderr.write(f"nao foi possivel fazer backup: {e}")
            return None
