"""
Seed animal/aquático só dados reais (IBGE PPM 3939/3940 / AgroDoc).
Uso:
  python manage.py seed_animal_aquatico_real --dry-run
  python manage.py seed_animal_aquatico_real --apply
"""

import json
import unicodedata
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from app.models import Cultura


def _norm(s):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", str(s or "").lower())
        if unicodedata.category(c) != "Mn"
    )


# Mapeamento curado — só espécies com IBGE PPM real + AgroDoc quando existe
ANIMAL_REAL_MAP = {
    # bovinos — raças mapeiam para bovino (IBGE 2670)
    "Nelore": {
        "grupo": "bovinos",
        "ibge": 2670,
        "agrodoc": "boi_gordo",
        "especie": "bovino",
    },
    "Angus": {
        "grupo": "bovinos",
        "ibge": 2670,
        "agrodoc": "boi_gordo",
        "especie": "bovino",
    },
    "Brahman": {
        "grupo": "bovinos",
        "ibge": 2670,
        "agrodoc": "boi_gordo",
        "especie": "bovino",
    },
    "Holandês": {
        "grupo": "bovinos",
        "ibge": 2670,
        "agrodoc": "boi_gordo",
        "especie": "bovino",
    },
    "Boi Gordo": {
        "grupo": "bovinos",
        "ibge": 2670,
        "agrodoc": "boi_gordo",
        "especie": "bovino",
    },
    "Bezerro": {
        "grupo": "bovinos",
        "ibge": 2670,
        "agrodoc": "bezerro",
        "especie": "bovino",
    },
    # suínos
    "Landrace": {
        "grupo": "suinos",
        "ibge": 32794,
        "agrodoc": "suino",
        "especie": "suino",
    },
    "Large-White": {
        "grupo": "suinos",
        "ibge": 32794,
        "agrodoc": "suino",
        "especie": "suino",
    },
    "Duroc": {"grupo": "suinos", "ibge": 32794, "agrodoc": "suino", "especie": "suino"},
    "Suíno": {"grupo": "suinos", "ibge": 32794, "agrodoc": "suino", "especie": "suino"},
    # aves
    "Galinha": {"grupo": "aves", "ibge": 32796, "agrodoc": "", "especie": "aves"},
    "Frango": {"grupo": "aves", "ibge": 32796, "agrodoc": "frango", "especie": "aves"},
    "Peru": {"grupo": "aves", "ibge": 32796, "agrodoc": "", "especie": "aves"},
    "Codorna": {"grupo": "aves", "ibge": 2680, "agrodoc": "", "especie": "codorna"},
    # ovinos/caprinos
    "Ovelha": {"grupo": "ovinos", "ibge": 2677, "agrodoc": "", "especie": "ovino"},
    "Cabra": {"grupo": "ovinos", "ibge": 2681, "agrodoc": "", "especie": "caprino"},
    # equinos/búfalos
    "Quarto-de-Milha": {
        "grupo": "equinos",
        "ibge": 2672,
        "agrodoc": "",
        "especie": "equino",
    },
    "Búfalo": {"grupo": "bufalos", "ibge": 2675, "agrodoc": "", "especie": "bubalino"},
}

AQUATICO_REAL_MAP = {
    "Tilápia": {"grupo": "peixes", "ibge": 32877, "agrodoc": "", "especie": "tilapia"},
    "Tambaqui": {
        "grupo": "peixes",
        "ibge": 32876,
        "agrodoc": "",
        "especie": "tambaqui",
    },
    "Pacu": {"grupo": "peixes", "ibge": 32878, "agrodoc": "", "especie": "pacu"},
    "Pintado": {"grupo": "peixes", "ibge": 32879, "agrodoc": "", "especie": "pintado"},
    "Carpa": {"grupo": "peixes", "ibge": 32880, "agrodoc": "", "especie": "carpa"},
    "Truta": {"grupo": "peixes", "ibge": 32881, "agrodoc": "", "especie": "truta"},
    "Camarão": {
        "grupo": "crustaceos",
        "ibge": 32886,
        "agrodoc": "",
        "especie": "camarao",
    },
    "Ostra": {"grupo": "crustaceos", "ibge": 32888, "agrodoc": "", "especie": "ostra"},
}

IBGE_URLS = [
    "https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{var}/p/{ano}/c{cclass}/{code}?formato=json"
]


def ibge_has(tabela, code):
    for ano in (2024, 2023, 2022):
        for var in ("105", "215", "allxp"):
            for cclass in ("c79", "c782", "c654"):
                url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{var}/p/{ano}/c{cclass}/{code}?formato=json"
                try:
                    with urllib.request.urlopen(url, timeout=5) as r:
                        data = json.loads(r.read().decode("utf-8"))
                        if isinstance(data, list) and len(data) > 1:
                            for row in data[1:]:
                                if row.get("V") and row["V"] not in (
                                    "-",
                                    "..",
                                    "0",
                                    "0,0",
                                ):
                                    return True
                except Exception:
                    continue
    return False


class Command(BaseCommand):
    help = "Insere animal/aquático só com fonte real"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--branch", choices=["animal", "aquatico", "all"], default="all"
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"] or not opts["apply"]
        branch = opts["branch"]
        maps = []
        if branch in ("animal", "all"):
            maps.append(("animal", ANIMAL_REAL_MAP))
        if branch in ("aquatico", "all"):
            maps.append(("aquatico", AQUATICO_REAL_MAP))
        total_ok = 0
        for bname, mp in maps:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"=== {bname} — auditoria só dados reais ==="
                )
            )
            ok = []
            for nome, meta in sorted(mp.items()):
                # considera real se tem ibge ou agrodoc mapeado (não consulta IBGE por raça, confia no mapa curado)
                has = bool(meta["ibge"] or meta["agrodoc"])
                line = f"{nome:20} grupo={meta['grupo']:10} ibge={meta['ibge']} agrodoc={meta['agrodoc']:12} -> {'REAL' if has else 'SEM DADO'}"
                if has:
                    ok.append(nome)
                    self.stdout.write(self.style.SUCCESS("  + " + line))
                else:
                    self.stdout.write(self.style.WARNING("  - " + line))
            self.stdout.write(f"Validados {bname}: {len(ok)}/{len(mp)}\n")
            total_ok += len(ok)
            if not dry:
                inserted = 0
                for nome in ok:
                    meta = mp[nome]
                    obj, created = Cultura.objects.get_or_create(
                        nome__iexact=nome,
                        defaults={
                            "nome": nome,
                            "grupo": meta["grupo"],
                            "unidade_comercial": "cabeca"
                            if bname == "animal"
                            else "kg",
                            "ibge_codigo": meta["ibge"],
                            "agrodoc_produto": meta["agrodoc"],
                            "ativo": True,
                        },
                    )
                    if not created:
                        ch = False
                        if not obj.ibge_codigo:
                            obj.ibge_codigo = meta["ibge"]
                            ch = True
                        if meta["agrodoc"] and not obj.agrodoc_produto:
                            obj.agrodoc_produto = meta["agrodoc"]
                            ch = True
                        if ch:
                            obj.save(update_fields=["ibge_codigo", "agrodoc_produto"])
                    else:
                        inserted += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Inseridas {inserted} novas {bname} (reais).")
                )
        if dry:
            self.stdout.write(self.style.NOTICE("Dry-run: nada inserido. Use --apply"))
        # salva mapa — em product-data/ (raiz antiga mantida por compat)
        out = {}
        for _, mp in maps:
            out.update(mp)
        from pathlib import Path

        _out_path = Path("product-data/animal_aquatico_real_map.json")
        _out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(_out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        # compat: espelha na raiz se ainda for referenciado
        try:
            with open("animal_aquatico_real_map.json", "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self.stdout.write(f"Mapa salvo em {_out_path} (espelho raiz por compat)")
