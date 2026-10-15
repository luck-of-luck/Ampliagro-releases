import os
import sys

# Set up Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from datetime import date

import requests as req_lib

from app.api.views import IBGE_TABELAS, _to_float, fmt_num

# Test cultura-bovino
cultura_id = "cultura-bovino"
uf = "SP"
mapping = IBGE_TABELAS.get(cultura_id)
print(f"Mapping: {mapping}")

if mapping:
    tabela, codigo, nome = mapping

    # Determine classification
    if tabela == 5457:
        classificacao = "c782"
        class_col = "D4"
        year_col = "D3"
        var_id = "allxp"
    elif tabela == 289:
        classificacao = "c193"
        class_col = "D4"
        year_col = "D3"
        var_id = "allxp"
    elif tabela == 291:
        classificacao = "c194"
        class_col = "D4"
        year_col = "D3"
        var_id = "allxp"
    elif tabela == 3939:
        classificacao = "c79"
        class_col = "D3"
        year_col = "D4"
        var_id = "105"
    elif tabela == 3940:
        classificacao = "c654"
        class_col = "D3"
        year_col = "D4"
        var_id = "4146,215"
    else:
        classificacao = "c194"
        class_col = "D4"
        year_col = "D3"
        var_id = "allxp"

    nivel = "n3/35" if uf == "SP" else "n1/1"
    cy = date.today().year
    url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/{nivel}/{classificacao}/{codigo}/p/{cy - 9}-{cy}/v/{var_id}/f/n?formato=json"

    print(f"\nURL: {url}")
    print(f"class_col={class_col}, year_col={year_col}")

    try:
        resp = req_lib.get(url, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.ok:
            data = resp.json()
            print(f"Rows: {len(data)}")

            if isinstance(data, list) and len(data) > 0:
                # Show header
                print(f"Header cols: {list(data[0].keys())}")

                var_by_year = {}
                rows = data[1:] if len(data) > 1 else []

                for row in rows:
                    ano = (row.get(f"{year_col}N") or "").strip()
                    var_name = (row.get(f"{class_col}N") or "").strip()
                    unid = (row.get("MN") or "").strip()
                    valor = _to_float(row.get("V"))

                    print(
                        f"  ano={ano}, var_name={var_name}, unid={unid}, valor={valor}"
                    )

                    if not ano or not var_name or var_name in ("Variavel", "Ano"):
                        continue
                    if valor is None:
                        continue

                    if var_name not in var_by_year:
                        var_by_year[var_name] = {}
                    var_by_year[var_name][ano] = {"valor": valor, "unid": unid}

                print(f"\nvar_by_year keys: {list(var_by_year.keys())}")

                # Build hist_map
                var_to_metric = {
                    "Quantidade produzida": "producao_total",
                    "Quantidade produzida na extracao vegetal": "producao_total",
                    "Quantidade produzida na silvicultura": "producao_total",
                    "Area plantada": "area_plantada",
                    "Area plantada ou destinada a colheita": "area_plantada",
                    "Area destinada a colheita": "area_plantada",
                    "Area colhida": "area_plantada",
                    "Rendimento medio da producao": "produtividade",
                    "Valor da producao": "receita_estimada",
                    "Valor da producao na extracao vegetal": "receita_estimada",
                    "Valor da producao na silvicultura": "receita_estimada",
                    "Efetivo dos rebanhos": "cabecas_total",
                    "Producao da aquicultura": "producao_total",
                }

                hist_map = {}
                prod_hist = []

                for var_name, years_dict in var_by_year.items():
                    mkey = var_to_metric.get(var_name)
                    if not mkey:
                        print(f"  UNMAPPED variable: {var_name}")
                        continue
                    sorted_years = sorted(years_dict.keys())
                    vals = []
                    for ano in sorted_years:
                        v = years_dict[ano]
                        vals.append({"ano": ano, "valor": v["valor"]})
                    if vals:
                        hist_map[mkey] = vals
                        if mkey == "producao_total":
                            prod_hist = vals

                print(f"hist_map keys: {list(hist_map.keys())}")

                if hist_map:
                    is_ppm_livestock = tabela == 3939
                    is_ppm_aquaculture = tabela == 3940

                    if is_ppm_livestock:
                        qty_var = "Efetivo dos rebanhos"
                        val_var = "Efetivo dos rebanhos"
                    elif is_ppm_aquaculture:
                        qty_var = "Producao da aquicultura"
                        val_var = "Valor da producao"
                    else:
                        qty_var = "Quantidade produzida"
                        val_var = "Valor da producao"

                    print(f"qty_var={qty_var}, val_var={val_var}")

                    if var_by_year.get(qty_var):
                        latest_year = sorted(var_by_year.get(qty_var, {}).keys())[-1]
                    else:
                        all_years = sorted(
                            {
                                ano
                                for vdict in var_by_year.values()
                                for ano in vdict
                            }
                        )
                        latest_year = all_years[-1] if all_years else ""

                    print(f"latest_year={latest_year}")

                    qtd = var_by_year.get(qty_var, {}).get(latest_year, {})
                    valor_p = var_by_year.get(val_var, {}).get(latest_year, {}) or qtd

                    print(f"qtd={qtd}")
                    print(f"valor_p={valor_p}")

                    if is_ppm_livestock:
                        metrics_list = [
                            {
                                "key": "cabecas_total",
                                "label": "Efetivo do Rebanho",
                                "value": fmt_num(qtd.get("valor")),
                                "unit": qtd.get("unid", "cabecas"),
                            },
                        ]
                        if valor_p.get("valor"):
                            metrics_list.append(
                                {
                                    "key": "receita_estimada",
                                    "label": "Valor da Producao",
                                    "value": fmt_num(valor_p.get("valor")),
                                    "unit": valor_p.get("unid", "R$"),
                                }
                            )
                    else:
                        receita_val = fmt_num(valor_p.get("valor")) if valor_p else "—"
                        receita_unit = valor_p.get("unid", "R$") if valor_p else "R$"
                        metrics_list = [
                            {
                                "key": "producao_total",
                                "label": "Producao Total",
                                "value": fmt_num(qtd.get("valor")),
                                "unit": qtd.get("unid", "t"),
                            },
                            {
                                "key": "receita_estimada",
                                "label": "Valor da Producao",
                                "value": receita_val,
                                "unit": receita_unit,
                            },
                        ]

                    print("\nFinal metrics:")
                    for m in metrics_list:
                        print(f"  {m['key']}: {m['value']} {m['unit']}")
                else:
                    print("EMPTY hist_map! No metrics generated.")
            else:
                print(f"Unexpected data format: {type(data)}")
        else:
            print(f"SIDRA error: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")
else:
    print("No mapping found")
