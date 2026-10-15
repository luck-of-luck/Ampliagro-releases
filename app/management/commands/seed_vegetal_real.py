"""
Seed vegetal apenas com dados reais (IBGE SIDRA / AgroDoc).
Uso:
  python manage.py seed_vegetal_real --dry-run   # lista o que entraria
  python manage.py seed_vegetal_real --apply     # insere só validados
"""

import json
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand

from app.models import Cultura

# Mapeamento curado de vegetais com fonte real confirmada
# ibge_codigo = SIDRA 1612 (ou 1618 quando aplicável) — validado via apisidra.ibge.gov.br
# agrodoc = produto CEPEA quando existe série histórica
VEGETAL_REAL_MAP = {
    # grãos / leguminosas / oleaginosas — SIDRA 1612
    "Soja": {"grupo": "leguminosas", "ibge": 2713, "agrodoc": "soja"},
    "Milho": {"grupo": "graos", "ibge": 2712, "agrodoc": "milho"},
    "Arroz": {"grupo": "graos", "ibge": 2691, "agrodoc": "arroz"},
    "Trigo": {"grupo": "graos", "ibge": 2696, "agrodoc": "trigo"},
    "Feijão": {"grupo": "leguminosas", "ibge": 2716, "agrodoc": "feijao"},
    "Feijão-carioca": {
        "grupo": "leguminosas",
        "ibge": 2716,
        "agrodoc": "feijao-carioca",
    },
    "Feijão-preto": {"grupo": "leguminosas", "ibge": 2716, "agrodoc": "feijao-preto"},
    "Algodão": {"grupo": "fibras", "ibge": 2707, "agrodoc": "algodao"},
    "Café": {"grupo": "graos", "ibge": 2700, "agrodoc": "cafe"},
    "Cana-de-açúcar": {"grupo": "cana", "ibge": 2689, "agrodoc": "acucar"},
    "Amendoim": {"grupo": "leguminosas", "ibge": 2693, "agrodoc": "amendoim"},
    "Girassol": {"grupo": "oleaginosas", "ibge": 2720, "agrodoc": "girassol"},
    "Sorgo": {"grupo": "graos", "ibge": 2714, "agrodoc": "sorgo"},
    "Cevada": {"grupo": "graos", "ibge": 2710, "agrodoc": "cevada"},
    "Aveia": {"grupo": "graos", "ibge": 2709, "agrodoc": "aveia"},
    # hortaliças / tubérculos — SIDRA tem série para estes
    "Batata": {"grupo": "tuberculos", "ibge": 2698, "agrodoc": "batata"},
    "Mandioca": {"grupo": "tuberculos", "ibge": 2694, "agrodoc": "mandioca"},
    "Tomate": {"grupo": "hortalicas", "ibge": 2699, "agrodoc": "tomate"},
    "Cebola": {"grupo": "hortalicas", "ibge": 2701, "agrodoc": "cebola"},
    "Alho": {"grupo": "hortalicas", "ibge": 2702, "agrodoc": "alho"},
    "Cenoura": {"grupo": "hortalicas", "ibge": 2703, "agrodoc": "cenoura"},
    # frutas — SIDRA 1612 frutas + AgroDoc hortifruti
    "Banana": {"grupo": "frutas", "ibge": 2006, "agrodoc": "banana"},
    "Laranja": {"grupo": "citricos", "ibge": 2008, "agrodoc": "laranja"},
    "Manga": {"grupo": "frutas", "ibge": 2010, "agrodoc": "manga"},
    "Uva": {"grupo": "trepadeiras", "ibge": 2007, "agrodoc": "uva"},
    "Maçã": {"grupo": "frutas", "ibge": 2009, "agrodoc": "maca"},
    "Mamão": {"grupo": "frutas", "ibge": 2011, "agrodoc": "mamao"},
    "Melancia": {"grupo": "frutas", "ibge": 2012, "agrodoc": "melancia"},
    "Melão": {"grupo": "frutas", "ibge": 2013, "agrodoc": "melao"},
}

IBGE_SIDRA_URLS = [
    "https://apisidra.ibge.gov.br/values/t/1612/n1/all/v/215/p/2024/c81/{code}",
    "https://apisidra.ibge.gov.br/values/t/1612/n1/all/v/215/p/2023/c81/{code}",
    "https://apisidra.ibge.gov.br/values/t/1612/n1/all/v/215/p/2022/c81/{code}",
]


def ibge_has_data(code: int) -> bool:
    for tmpl in IBGE_SIDRA_URLS:
        url = tmpl.format(code=code)
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                body = r.read().decode("utf-8")
                data = json.loads(body)
                if isinstance(data, list) and len(data) > 1:
                    for row in data[1:]:
                        if row.get("V") and row["V"] not in ("-", "..", "0", "0,0"):
                            return True
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue
    return False


class Command(BaseCommand):
    help = "Insere apenas culturas vegetais com fonte real (IBGE/AgroDoc)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Só lista, não insere"
        )
        parser.add_argument("--apply", action="store_true", help="Insere validados")
        parser.add_argument(
            "--skip-ibge-check",
            action="store_true",
            help="Não consulta IBGE (confia no mapa)",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"] or not opts["apply"]
        skip_check = opts["skip_ibge_check"]

        self.stdout.write(
            self.style.MIGRATE_HEADING("=== Vegetal — auditoria só dados reais ===")
        )
        total = len(VEGETAL_REAL_MAP)
        ok, fail, inserted = [], [], 0

        for nome, meta in sorted(VEGETAL_REAL_MAP.items()):
            ibge = meta["ibge"]
            has = True
            if not skip_check:
                has = ibge_has_data(ibge)
            status = "REAL" if has else "SEM DADO (pular)"
            line = f"{nome:22} grupo={meta['grupo']:12} ibge={ibge} agrodoc={meta['agrodoc']:14} -> {status}"
            if has:
                ok.append(nome)
                self.stdout.write(self.style.SUCCESS("  + " + line))
            else:
                fail.append(nome)
                self.stdout.write(self.style.WARNING("  - " + line))

        self.stdout.write("")
        self.stdout.write(
            f"Validados com fonte real: {len(ok)}/{total} | Sem dado: {len(fail)}"
        )
        if dry:
            self.stdout.write(
                self.style.NOTICE(
                    "Dry-run: nada inserido. Rode com --apply para inserir."
                )
            )
            # salva mapa para conferência — product-data/ + espelho raiz compat
            out = {k: v for k, v in VEGETAL_REAL_MAP.items() if k in ok}
            from pathlib import Path

            _vp = Path("product-data/vegetal_real_map.json")
            _vp.parent.mkdir(parents=True, exist_ok=True)
            with open(_vp, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            try:
                with open("vegetal_real_map.json", "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            self.stdout.write(f"Mapa salvo em {_vp} (espelho raiz por compat)")
            return

        # --apply
        for nome in ok:
            meta = VEGETAL_REAL_MAP[nome]
            obj, created = Cultura.objects.get_or_create(
                nome__iexact=nome,
                defaults={
                    "nome": nome,
                    "grupo": meta["grupo"],
                    "unidade_comercial": "sacas"
                    if meta["grupo"] in ("graos", "leguminosas")
                    else "kg",
                    "ibge_codigo": meta["ibge"],
                    "agrodoc_produto": meta["agrodoc"],
                    "ativo": True,
                },
            )
            if not created:
                changed = False
                if not obj.ibge_codigo:
                    obj.ibge_codigo = meta["ibge"]
                    changed = True
                if not obj.agrodoc_produto:
                    obj.agrodoc_produto = meta["agrodoc"]
                    changed = True
                if changed:
                    obj.save(update_fields=["ibge_codigo", "agrodoc_produto"])
            else:
                inserted += 1

        # Expansão Super: todas PAM 5457 que ainda não estão no mapa (59 totais)
        try:
            from app.api.views.utils import IBGE_TABELAS

            extra = 0
            for cultura_id, (tabela, codigo, nome_ibge) in IBGE_TABELAS.items():
                if tabela != 5457:
                    continue
                # nome limpo: remove * e pega antes do parêntese
                nome_limpo = nome_ibge.split("(")[0].strip().replace("*", "").strip()
                # normaliza para title case
                nome_title = " ".join(
                    w.capitalize() for w in nome_limpo.lower().split()
                )
                # ignora se já está no mapa curado (case-insensitive)
                if any(nome_title.lower() == k.lower() for k in VEGETAL_REAL_MAP):
                    continue
                # verifica se já existe no banco (evita duplicata)
                if Cultura.objects.filter(nome__iexact=nome_title).exists():
                    # atualiza ibge se faltar
                    obj2 = Cultura.objects.filter(nome__iexact=nome_title).first()
                    if obj2 and not obj2.ibge_codigo:
                        obj2.ibge_codigo = codigo
                        obj2.save(update_fields=["ibge_codigo"])
                    continue
                # determina grupo por cultura_id
                grupo = "outro"
                if cultura_id.startswith("cultura-"):
                    # tenta inferir pelo nome_ibge
                    low = nome_title.lower()
                    if any(
                        x in low
                        for x in [
                            "soja",
                            "milho",
                            "arroz",
                            "trigo",
                            "feijao",
                            "sorgo",
                            "aveia",
                            "cevada",
                            "triticale",
                            "centeio",
                            "girassol",
                            "mamona",
                        ]
                    ):
                        grupo = "graos"
                    elif any(
                        x in low
                        for x in [
                            "banana",
                            "manga",
                            "mamao",
                            "abacate",
                            "laranja",
                            "limao",
                            "abacaxi",
                        ]
                    ):
                        grupo = "frutas"
                    elif any(
                        x in low
                        for x in ["tomate", "cebola", "alho", "batata", "mandioca"]
                    ):
                        grupo = "hortalicas"
                obj3, created3 = Cultura.objects.get_or_create(
                    nome__iexact=nome_title,
                    defaults={
                        "nome": nome_title,
                        "grupo": grupo,
                        "unidade_comercial": "kg",
                        "ibge_codigo": codigo,
                        "ativo": True,
                    },
                )
                if created3:
                    extra += 1
            if extra:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Super expansão: +{extra} PAM 5457 adicionais (total vegetal real)."
                    )
                )
                inserted += extra
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Super expansão falhou: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Inseridas {inserted} novas vegetais (reais). Demais preservadas."
            )
        )
        out = {k: v for k, v in VEGETAL_REAL_MAP.items() if k in ok}
        from pathlib import Path as _P2

        _vp2 = _P2("product-data/vegetal_real_map.json")
        _vp2.parent.mkdir(parents=True, exist_ok=True)
        with open(_vp2, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        try:
            with open("vegetal_real_map.json", "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
