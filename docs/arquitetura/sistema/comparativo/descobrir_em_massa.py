"""Descobrimiento em massa: que coluna consegue CADA pagina provar?

Com 53 paginas alcancaveis e 50 colunas, a pergunta util nao e' "o que a Aegro
faz" — e' "que citacao existe **nesta** pagina que prove **alguma** das 50
colunas". Este script cruza as duas coisas e devolve, por pagina, as colunas
que a pagina consegue sustentar.

Cada coluna tem uma fila de candidatos: do mais forte ao mais fraco. O mais
forte e' uma frase inteira ("fotos georreferenciadas"); o mais fraco e' uma
palavra ("georreferencia") que pode aparecer num menu.

O resultado **nao escreve no registo** — escreve um relatorio. Escrever no
registo e' um passo a parte, e e' onde a leitura humana decide se a citacao
prova mesmo o que a coluna pede. Um script que escreve automaticamente volta a
ser o gerador de `S` falsos que acabámos de tirar.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from verificar_evidencia import _normalizar, textos  # noqa: E402

#: coluna -> candidatos, do mais forte ao mais fraco
CANDIDATOS: dict[str, list[str]] = {
    # ---- Fiscal
    "F01": ["Livro Caixa Digital", "LCDPR"],
    "F02": ["NF-e", "Nota Fiscal Eletr", "electronic invoice"],
    "F03": ["MDF-e", "manifesto"],
    "F04": ["SEFAZ", "certificado digital", "A1", "ICP-Brasil"],
    "F05": ["Reforma Tribut", "IBS", "CBS", "taxa de"],
    "F06": ["NCM", "TIPI"],
    "F07": ["DRE"],
    "F08": ["presumido", "regime de lucro real"],
    # ---- Financeiro
    "F10": ["accounts payable", "contas a pagar", "contas a pagar", "supplier invoice"],
    "F11": ["fluxo de caixa", "cash flow"],
    "F12": ["OFX", "bank reconciliation", "conciliação"],
    "F13": ["cost per", "custo por hectare", "custo de produção", "per-acre"],
    "F14": ["budget", "orçamento", "planejado", "planned vs"],
    "F15": ["benchmark", "benchmarking", "compare safras"],
    "F16": [
        "crédito rural",
        "credito rural",
        "crop insurance",
        "seguro agrícola",
        "financial services",
        "ag lending",
    ],
    "F17": ["income tax", "imposto de renda", "IRPF", "tax projection"],
    "F18": [
        "payroll",
        "folha de pagamento",
        "mão de obra",
        "mao de obra",
        "labour",
        "seasonal worker",
    ],
    # ---- Campo
    "O01": ["field record", "caderno de campo", "field log", "scouting report"],
    "O02": [
        "offline",
        "without internet",
        "sem internet",
        "no connection",
        "sin conexi",
    ],
    "O03": ["geotagged", "georreferenciad", "geo-tagged", "geotag"],
    "O04": [
        "task management",
        "gestão de tarefas",
        "tarefas",
        "work order",
        "ordem de serviço",
    ],
    "O05": ["crop plan", "planeamento de safra", "planning", "cronograma", "calendar"],
    "O06": ["map", "mapa", "boundary", "polygon", "GIS"],
    "O07": ["NDVI", "satellite", "satélite", "satelit", "vegetation index"],
    "O08": ["drone", "aerial", "UAV"],
    "O09": ["IPM", "MIP", "pest", "praga", "disease"],
    # ---- Pecuaria
    "P01": ["ear tag", "brinco", "RFID", "individual animal", "livestock"],
    "P02": ["vaccin", "vacina", "health record", "sanit"],
    "P03": ["weight gain", "GMD", "arroba", "carcass", "cow-calf", "lactation"],
    # ---- Logistica
    "L01": ["inventory", "estoque", "batch", "lote"],
    "L02": ["weighbridge", "romaneio", "pesagem", "scale ticket", "balança"],
    "L03": ["purchasing", "compras", "purchase order", "procurement"],
    "L04": ["beneficiamento", "drying", "secagem", "storage", "armazenagem", "silo"],
    "L05": [
        "forward contract",
        "contrato de safra",
        "grain contract",
        "futures",
        "hedge",
    ],
    # ---- Maquinas e IA
    "M01": ["telemetry", "telemetria", "machine data", "implement data"],
    "M02": ["John Deere", "Operations Center"],
    "M03": ["Stara", "Climate FieldView", "Solinftec", "Trimble"],
    "M04": ["ISOBUS", "ISO 11783"],
    "M05": ["OTA", "over-the-air", "firmware update"],
    "M07": ["on-device", "local AI", "edge AI", "WebGPU"],
    "M08": ["MCP", "Model Context Protocol", "chatbot", "assistant", "copilot"],
    "M09": ["API", "developer"],
    # ---- Dados
    "G01": ["provenance", "data lineage", "audit trail"],
    "G02": ["audit log", "audit trail", "activity log"],
    "G03": ["multi-tenant", "row-level security", "tenant isolation"],
    "G04": ["multi-farm", "multiple farm", "multi-property"],
    "G05": ["carbon", "carbono", "emission", "MRV", "ESG", "sustainability"],
    "X02": ["integration", "integração", "conector", "ERP"],
    "X06": ["WhatsApp"],
    "X07": ["export", "exportação", "CSV", "data portability"],
}

if __name__ == "__main__":
    ALVOS = json.loads(
        pathlib.Path(__file__)
        .parent.joinpath("paginas_alcancaveis.json")
        .read_text(encoding="utf-8")
    )
    print("=" * 92)
    print(
        f"DESCOBERTA EM MASSA — {len(ALVOS)} paginas alcancaveis x {len(CANDIDATOS)} colunas"
    )
    print("=" * 92)

    # `ALVOS` e' {produto: url}. `list()` sobre um dicionario devolve as CHAVES, e
    # foi o que aconteceu na primeira versao: o verificador tentou buscar
    # "Aegro" como se fosse um URL. Tem de ser `.values()`.
    tx = textos(list(ALVOS.values()), usar_cache=True)

    total = 0
    for produto, url in ALVOS.items():
        estado, t = tx.get(url, ("SEM ACESSO", ""))
        if estado != "OK" or len(t) < 400:
            continue
        n = _normalizar(t)
        achados = []
        for cid, cands in CANDIDATOS.items():
            for c in cands:
                k = n.count(_normalizar(c))
                if k:
                    achados.append((cid, c, k))
                    break  # o mais forte basta
        if achados:
            total += len(achados)
            print(f"\n  {produto}")
            for cid, c, k in achados:
                print(f"    {cid}  {c!r} x{k}")

    print()
    print("=" * 92)
    print(f"TOTAL de celulas potencialmente provaveis: {total}")
    print("Isto NAO escreve no registo. Le e decide.")
