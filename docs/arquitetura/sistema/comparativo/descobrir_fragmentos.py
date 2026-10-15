"""Descobre QUAIS fragmentos existem em cada pagina — todos de uma vez.

Uma celula por vez seria 40 downloads. O cache ja tem as paginas; aqui testo
centenas de candidatos contra o texto ja guardado e digo quais existem. O que
sair daqui vira o registo de evidencia.

Este e' o inverso do costume: em vez de eu escrever a citacao e tentar
prova-la, pergunto 'que citacoes existem?' e uso essas.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verificar_evidencia import _normalizar, textos  # noqa: E402

#: url -> lista de candidatos que quero provar
ALVOS: dict[str, list[str]] = {
    "https://aegro.com.br/": [
        "NF-e",
        "MDF-e",
        "SEFAZ",
        "Aegrozap",
        "offline",
        "sem internet",
        "talhão",
        "talhoes",
        "custo",
        "pecuária",
        "arroba",
        "arbas",
        "maquin",
        "telemetria",
        "Insumos",
        "insumos",
        "estoque",
        "safra",
        "comparativo",
        "benchmark",
        "credito rural",
        "seguro",
        "georreferenciad",
        "foto",
        "MIP",
        "praga",
        "exportar",
        "CSV",
        "OPL",
        "retenção",
        "fiscal",
        "contabilid",
    ],
    "https://aegro.com.br/solucoes/gestao-rural/": [
        "planejado vs. realizado",
        "orçamento",
        "orcamento",
        "talhão",
        "baixa o insumo",
        "estoque",
        "NDVI",
        "satélite",
        "MIP",
        "maquin",
        "John Deere",
        "Stara",
        "Climate FieldView",
        "georreferenciad",
        "safra",
        "custo",
    ],
    "https://aegro.com.br/produtos/plano-aegro-lucratividade/": [
        "OFX",
        "fotos georreferenciadas",
        "500 ha",
        "usuários ilimitados",
        "orçado",
        "realizado",
        "custo de produção",
        "fazenda",
    ],
    "https://aegro.com.br/produtos/plano-aegro-premium/": [
        "BI",
        "Compare Safras",
        "benchmark",
        "categorias",
        "Aegro Imagens",
        "Livro Caixa",
        "MIP",
        "telemetria",
    ],
    "https://www.upcampo.com.br/": [
        "WhatsApp",
        "MCP",
        "ChatGPT",
        "Claude",
        "API",
        "John Deere",
        "Sankhya",
        "Aliare",
        "ViaSoft",
        "Solinftec",
        "Davis",
        "Agrosystem",
        "contabilidade",
        "amplitude de regras tributárias",
        "romaneios",
        "georreferenciado",
        "praga",
        "preço",
        "R$",
        "hectare",
    ],
    "https://lucrorural.com.br/": [
        "LCDPR",
        "NCM",
        "imposto de renda",
        "IR",
        "presumido",
        "resultado",
        "DRE",
        "fluxo de caixa",
        "SEFAZ",
        "importa",
        "prejuízo",
        "prejuizo",
        "rateio",
        "sócio",
        "socio",
        "condomínio",
        "condominio",
        "seguro",
        "crédito rural",
        "credito rural",
        "capital",
    ],
    "https://site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio/": [
        "Livro Caixa Digital do Produtor Rural",
        "Mapfy",
        "Simple Farm",
        "Shield",
        "Mão de Obra",
        "Balança Controle Agronômico",
        "offline",
        "georreferenciados",
        "Sat",
        "Receituário",
        "Scouting",
        "MIP",
        "Safra",
        "floresta",
        "automotiva",
        "celular",
    ],
    "https://fluere.ag/": ["MRV", "carbono", "GEE", "inventário", "crédito", "Escopo"],
    "https://carbonova.ai/": [
        "MRV",
        "Inventário de Carbono",
        "GEE",
        "Escopos",
        "crédito",
        "monitor",
        "verific",
        "report",
    ],
    "https://carbonova.ai/solucoes-inventario-carbono-ia": [
        "MRV",
        "Inventário de Emissões",
        "Escopos 1, 2 e 3",
        "GEE",
        "auditável",
        "Tempo Real",
    ],
    "https://www.fluere.ag/solucoes": [
        "MRV",
        "carbono",
        "GEE",
        "crédito",
        "inventário",
    ],
}

PAGINAS = list(ALVOS)

if __name__ == "__main__":
    print("=" * 78)
    print("DESCOBERTA DE FRAGMENTOS — o que existe de facto em cada pagina")
    print("=" * 78)
    tx = textos(PAGINAS, usar_cache=True)

    for url in PAGINAS:
        estado, texto = tx.get(url, ("SEM ACESSO", ""))
        print()
        print(f"--- {url}")
        if estado != "OK" or len(texto) < 100:
            print(f"    {estado}, {len(texto)} chars — sem texto para procurar")
            continue
        print(f"    {len(texto):,} chars")
        normal = _normalizar(texto)
        achados, falhados = [], []
        for cand in ALVOS[url]:
            n = normal.count(_normalizar(cand))
            (achados if n else falhados).append((cand, n))
        if achados:
            print("    >>> EXISTEM:")
            for c, n in achados:
                print(f"          {c!r} x{n}")
        if falhados:
            print(
                f"    nao existem ({len(falhados)}): "
                + ", ".join(repr(c) for c, _ in falhados)
            )
