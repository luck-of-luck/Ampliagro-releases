"""Solo+Água — 009/2400 — SPD palhada 7t +1% MO vs irrigação BME280."""


def spd_materia_organica(palhada_t_ha=7, anos=5, mo_inicial=2.0):
    # 7t palhada → +0,2% MO/ano (7t/5t base =1,4×0,2=0,28)
    ganho_ano = 0.2 * (palhada_t_ha / 5)
    mo_final = mo_inicial + ganho_ano * anos
    sc_ganho = ganho_ano * 45  # 1% MO = +45% produtividade ≈ +9 sc/ha em 60 sc
    return {
        "mo_inicial": mo_inicial,
        "mo_final": round(mo_final, 2),
        "ganho_ano_pct": round(ganho_ano, 2),
        "sc_ganho_ha": round(sc_ganho, 1),
    }


def irrigacao_pivo(umidade_solo_pct, chuva_prev_mm, limiar=60):
    if umidade_solo_pct < limiar and chuva_prev_mm < 10:
        return {
            "acao": "LIGAR pivo 40mm",
            "motivo": f"solo {umidade_solo_pct}% <{limiar}% + chuva {chuva_prev_mm}mm <10mm",
        }
    return {"acao": "NÃO ligar", "motivo": "solo OK ou chuva prevista"}
