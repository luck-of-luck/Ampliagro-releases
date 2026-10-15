"""ERP Agro — 008/2400 — SAP JBS 10M, PROTHEUS Eurochem, John Deere IA, CPR R$8,5bi."""


def sap_jbs(cabecas, preco_kg=8.2, peso_car=21):
    return {
        "receita": cabecas * peso_car * preco_kg,
        "ganho_vs_sem_sap": cabecas * peso_car * 0.7,
    }


def john_deere_ia(area_ha, herb_ha=400):
    economia = area_ha * herb_ha * 0.30
    return {"economia_herbicida": economia, "pct": 30}
