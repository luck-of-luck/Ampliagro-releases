"""Gera a planilha do comparativo: 100 aplicacoes x 50 colunas.

O QUE ESTA PLANILHA E'
======================
Um **framework** com uma folha medida. A MEDICAO DO AMPLIAGRO NAO ESTA NA
MATRIZ — esta na folha `AMPLIAGRO`, uma linha por dimensao, com
`ficheiro:linha`. A MATRIZ e' so dos concorrentes: 100 linhas por 50
dimensoes, com a marca de evidencia de cada celula, e o `?` e' a celula
honesta.

PORQUÊ O AMPLIAGRO NAO ESTA NA MATRIZ
=====================================
Nao por esquecimento, e por uma razao de legibilidade. Uma propriedade do
prodito nao pode ser escrita na linha de cada *concorrente*: na linha do
Aegro, a celula do Ampliagro dizia o que o *Ampliagro* tem, ao lado das
celulas que dizem o que o *Aegro* tem — e a linha deixava de responder a
"quem tem o quê, por dimensao". Pior: escrevia-se la o veredicto da
*primeira* dimensao (F01) nas 100 linhas, o que fazia o Ampliagro parecer
ter LCDPR e mais nada. Retirada a coluna, a MATRIZ passou a ser a verdade:
100 x 50, e so dos concorrentes.

O QUE ESTA PLANILHA NAO E'
==========================
Nao e' um ranking. Um ranking exige medir os 100 nos 50 eixos. Isso nao foi
feito, e a folha `LEIA-ME` diz isso na primeira linha para ninguem discover
pelo canto de baixo.

FOLHAS
======
  LEIA-ME       o aviso, a escala de marcas e o que e' medido vs. pesquisado
  COLUNAS       as 50 dimensoes e porque cada uma conta numa decisao
  MATRIZ        100 concorrentes x 50 dimensoes (sem o Ampliagro: ver acima)
  AMPLIAGRO     as 50 dimensoes com o veredicto e a `ficheiro:linha` do
                Ampliagro — uma linha por dimensao
  QUEM-PASSA    por coluna, quem tem evidencia de S, e onde o Ampliagro esta
  COMERCIAL     preco e modelo — o que nao e' capacidade
  FONTES        o que foi lido
"""

from __future__ import annotations

import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from concorrentes import CONCORRENTES
from evidencia import EVIDENCIA
from medir_ampliagro import COLUNAS
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from vereditos import VEREDITOS

DESTINO = pathlib.Path(
    r"C:\Trabalho\Projetos\Ativos\Ampliagro\docs\sistema\comparativo\comparativo-100x50.xlsx"
)

VERMELHO = PatternFill("solid", fgColor="F8CBAD")
AMARELO = PatternFill("solid", fgColor="FFE699")
VERDE = PatternFill("solid", fgColor="C6E0B4")
CINZA = PatternFill("solid", fgColor="E7E6E6")
AZUL = PatternFill("solid", fgColor="BDD7EE")
CAB = PatternFill("solid", fgColor="203864")
CAB_TEXTO = Font(color="FFFFFF", bold=True, size=10)

#: A COR E' A PROVA. Um `F` pintado de cinzento — a mesma cor do `?` — diz ao
#: leitor "nao verifiquei isto" sobre uma celula que foi verificada por fetch.
#: Foi o que acontecia: `F` e `D` nao estavam neste dicionario e caiam no
#: fallback `.get(marca, CINZA)`. **Fica a provacao, fica a cor.**
MARCA_COR = {
    "S": VERDE,
    "F": VERDE,  # provado por fetch da fonte oficial
    "D": AZUL,  # documentado por terceiro (ex.: comunicado de bolsa)
    "P": AMARELO,  # fonte lida, mas prova MENOS do que a coluna pede
    "N": VERMELHO,
    "?": CINZA,
    "C": VERDE,
    "E": AMARELO,
}

LEGENDA = {
    "F": "PROVADO — a citacao foi buscada na pagina oficial e contem a frase. "
    "Ver `evidencia.py` para o URL e o fragmento literal.",
    "D": "DOCUMENTADO por terceiro — o fornecedor nao se prova, quem o "
    "confirma e' outra fonte (ex.: a SLC Agricola, de bolsa, sobre a Fluere)",
    "P": "PARCIAL — a fonte foi lida e **nao prova o que a coluna pede**. "
    "Ex.: 'financial services' != credito rural; 'audit trail' != "
    "proveniencia tipada. **Nao desce a `?`**: um quase-e' um achado, "
    "uma ausencia nao e'.",
    "S": "CONFIRMADO na fonte oficial lida",
    "N": "NAO tem (a fonte nega, ou a ausencia e' obvia)",
    "?": "NAO VERIFICADO — nao encontrei fonte. **Nao e' zero.**",
    "C": "CONFIRMADO no codigo do Ampliagro (linha lida)",
    "E": "ENFRAQUECIDO — a capacidade existe mas a evidencia e' um campo, "
    "uma constante ou um nome de view",
}


def cabecalho(ws, linha, valores, larguras=None):
    for i, v in enumerate(valores, 1):
        c = ws.cell(row=linha, column=i, value=v)
        c.fill = CAB
        c.font = CAB_TEXTO
        c.alignment = Alignment(wrap_text=True, vertical="center")
    if larguras:
        for i, w in enumerate(larguras, 1):
            ws.column_dimensions[get_column_letter(i)].width = w


def construir():
    wb = Workbook()

    # ---------------------------------------------------------------- LEIA-ME
    ws = wb.active
    ws.title = "LEIA-ME"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 105

    # --- contagens CALCULADAS (nunca mais texto fixo) ---
    # Estas duas entram em texto ja escrito, por isso sao calculadas ANTES das
    # linhas do LEIA-ME. A versao anterior desta nota dizia "83 celulas com
    # fonte lida, 4.917 por verificar" em texto fixo — e ja nao era verdade:
    # eram 72 e 4.928. Um numero fixo divergido e' a mesma mentira que o
    # `?` evita, so que mais barata de escrever.
    _marcas = Counter(
        (EVIDENCIA.get((nm, cid)) or ("", "", "", "?", ""))[3]
        for nm, *_ in CONCORRENTES
        for cid, *_r in COLUNAS
    )
    _celulas_total = len(CONCORRENTES) * len(COLUNAS)
    _com_fonte = _marcas["F"] + _marcas["D"] + _marcas["P"]
    _por_verificar = _marcas["?"]
    # Milhar com ponto, como o resto da folha escreve — o `4928` ao lado de um
    # `5.000` na mesma frase lia-se como numero diferente.
    _n_total_txt = f"{_celulas_total:,}".replace(",", ".")
    _fonte_txt = f"{_com_fonte:,}".replace(",", ".")
    _verificar_txt = f"{_por_verificar:,}".replace(",", ".")

    linhas = [
        ("TITULO", "Comparativo 100 aplicacoes x 50 dimensoes"),
        ("", ""),
        ("AGENTE", "9"),
        ("DATA", "2026-10-05"),
        ("PROJECTO", r"C:\Trabalho\Projetos\Ativos\Ampliagro"),
        ("", ""),
        (
            "O QUE ESTE FICHEIRO E",
            "Um FRAMEWORK com uma folha medida. A medicao do Ampliagro foi lida "
            "no codigo, linha a linha, e o veredicto de cada dimensao esta na "
            "folha AMPLIAGRO, uma linha por dimensao, com a referencia "
            "ficheiro:linha. A folha MATRIZ e' so dos 100 concorrentes: "
            f"{_fonte_txt} das {_n_total_txt} celulas trazem marca de fonte "
            f"lida (F, D ou P) e {_verificar_txt} estao marcadas `?`.",
        ),
        ("", ""),
        (
            "O QUE ESTE FICHEIRO NAO E",
            "NAO E' UM RANKING. Um ranking exige medir os 100 produtos nos 50 eixos. "
            f"Isso nao foi feito — e e' por isso que {_verificar_txt} das "
            f"{_n_total_txt} celulas estao marcadas `?`. Um preenchimento sem "
            "`?` teria 5.000 certezas sobre 100 produtos que nao pesquisei, e e' "
            "assim que um numero falso ganha aspecto de numero certo.",
        ),
        ("", ""),
        (
            "A ARMADILHA QUE JA CAIU NESTE TRABALHO — 1a vez",
            "O medidor automatico deu 43/50 para o Ampliagro. Quatro dos 'achados' "
            "eram falsos: F14 'Orcado x realizado' batia numa docstring do servidor "
            "MCP; F15 'Benchmark' numa docstring sobre machine learning; M02 'John "
            "Deere' num prompt de exemplo ('ex.: trator John Deere'); M04 'ISOBUS' "
            "num item de uma lista de widgets CLONADOS.",
        ),
        (
            "A ARMADILHA QUE JA CAIU NESTE TRABALHO — 2a vez (auditoria de ancoras, 2026-10-05)",
            "As ancoras 'C' foram relidas uma a uma. SUB-declarou: M04 — "
            "refutou-se corretamente o falso positivo dos widgets clonados, "
            "declarando-o ausente, sem procurar a implementacao real "
            "(vra.py:13 tem o NAMESPACE iso11783). "
            "SUPER-declarou: cinco 'C' ancoravam em nome de campo, registo no admin "
            "ou decorator — que e' a propria definicao de E neste ficheiro (F13, "
            "P03, L01, M09) — e o G03 apontava para o middleware ERRADO (:41 "
            "revoga servidor; o isolamento por tabela e' :136), e ainda assim C, "
            "sendo que :201 nunca le o corpo JSON. Os cinco foram corrigidos para "
            "E. As contagens desta linha sao HISTORICAS e nao sao recalculadas: o "
            "numero de ancoras 'C' de hoje e' o da linha 'O NUMERO DESTA "
            "PLANILHA', que e' CALCULADA a partir de vereditos.py.",
        ),
        ("", ""),
        ("A ESCALA DE MARCAS", ""),
    ]
    for k, v in linhas:
        ws.cell(row=ws.max_row + 1, column=1, value=k).font = Font(bold=True)
        c = ws.cell(row=ws.max_row, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    # --- contagem CALCULADA (nunca mais texto fixo) ---
    _cc = Counter(v[0] for v in VEREDITOS.values())
    _n_total = len(VEREDITOS)
    _tem_lider = {
        cid
        for cid, _g, _n, _p in COLUNAS
        if [
            nm
            for nm, *_ in CONCORRENTES
            if (EVIDENCIA.get((nm, cid)) or ("", "", "", "?", ""))[3] in ("F", "D", "P")
        ]
    }
    _lacunas = [c for c, v in VEREDITOS.items() if v[0] == "N"]
    _lacunas_com_lider = [c for c in _lacunas if c in _tem_lider]
    _sem_bench = [c for c in _lacunas if c not in _tem_lider]

    ws.cell(
        row=ws.max_row + 1, column=1, value="O NUMERO DESTA PLANILHA (calculado)"
    ).font = Font(bold=True)
    _c = ws.cell(row=ws.max_row, column=2)
    _c.value = (
        f"{_cc['C']} confirmados · {_cc['E']} enfraquecidos · {_cc['N']} ausentes "
        f"(total {_n_total}). Das {_cc['N']} ausencias, {len(_lacunas_com_lider)} sao "
        f"LACUNAS COMPETITIVAS (existe lider com evidencia de fonte) e {len(_sem_bench)} sao "
        f"SEM BENCHMARK (nenhum dos 100 tem evidencia de fonte — falhar para quem ninguem "
        f"provou que faz nao e' gap competitivo). Sem benchmark: "
        f"{', '.join(_sem_bench) if _sem_bench else '—'}. "
        f"Lacunas competitivas: {', '.join(_lacunas_com_lider) if _lacunas_com_lider else '—'}."
    )
    _c.alignment = Alignment(wrap_text=True, vertical="top")

    for m, desc in LEGENDA.items():
        r = ws.max_row + 1
        c = ws.cell(row=r, column=1, value=m)
        c.fill = MARCA_COR[m]
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
        ws.cell(row=r, column=2, value=desc).alignment = Alignment(wrap_text=True)

    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="AS 50 COLUNAS SAIRAM DE 60").font = Font(bold=True)
    ws.cell(
        row=r,
        column=2,
        value="Cortar 10 e' parte do metodo, nao uma falha. O criterio foi "
        "'e' isto uma capacidade, e medivel?'. Preco, suporte e roadmap "
        "sao comerciais. Rastreabilidade de lote ponta a ponta e' espaco "
        "dos ERPs de ALIMENTO. As razoes estao no docstring de "
        "`medir_ampliagro.py`.",
    ).alignment = Alignment(wrap_text=True)

    # ---------------------------------------------------------------- COLUNAS
    ws = wb.create_sheet("COLUNAS")
    cabecalho(
        ws,
        1,
        ["ID", "Grupo", "Dimensao", "Porque conta numa decisao de compra"],
        [8, 16, 46, 88],
    )
    for i, (cid, grupo, nome, porque) in enumerate(COLUNAS, 2):
        ws.cell(row=i, column=1, value=cid)
        ws.cell(row=i, column=2, value=grupo)
        ws.cell(row=i, column=3, value=nome)
        c = ws.cell(row=i, column=4, value=porque)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    # ---------------------------------------------------------------- MATRIZ
    # A MATRIZ e' DOS CONCORRENTES. O Ampliagro nao tem coluna aqui, por
    # desenho, e nao por esquecimento.
    #
    # Havia uma coluna "AMPLIAGRO (medido no codigo)" e ela era preguicosa:
    # escrevia `VEREDITOS[COLUNAS[0][0]]` — o veredicto da PRIMEIRA dimensao
    # (F01) — nas 100 linhas. Quem abrisse a folha lia "C / LCDPR" na coluna do
    # Ampliagro ao lado da linha do Aegro, e levava a ideia de que o Ampliagro
    # tinha LCDPR e mais nada. Alem disso `amp_col` dava 5+50+1 = 56, que era
    # exatamente a coluna do cabecalho "Evidencia": a coluna do Ampliagro
    # APAGAVA o cabecalho "Evidencia", e o "Evidencia" nunca chegou a ter
    # dado nenhum (uma coluna so por concorrente nao tem significado ao lado
    # de 50 dimensoes). Retirada a coluna, a MATRIZ passou a ser o que
    # promete: 100 concorrentes x 50 dimensoes. O Ampliagro esta na folha
    # `AMPLIAGRO`, uma linha por dimensao, com o `ficheiro:linha`.
    ws = wb.create_sheet("MATRIZ")
    cabecalho(
        ws,
        1,
        ["#", "Aplicacao", "Pais", "Segmento", "Fonte"]
        + [f"{c[0]}\n{c[2][:22]}" for c in COLUNAS],
        [5, 30, 7, 22, 22] + [7] * len(COLUNAS),
    )

    for i, (nome, pais, seg, fonte) in enumerate(CONCORRENTES, 1):
        r = i + 1
        ws.cell(row=r, column=1, value=i)
        ws.cell(row=r, column=2, value=nome).font = Font(bold=True)
        ws.cell(row=r, column=3, value=pais)
        ws.cell(row=r, column=4, value=seg)
        ws.cell(row=r, column=5, value=fonte)
        for j, (cid, *_resto) in enumerate(COLUNAS, 6):
            reg = EVIDENCIA.get((nome, cid))
            marca = reg[3] if reg else "?"
            c = ws.cell(row=r, column=j, value=marca)
            c.fill = MARCA_COR.get(marca, CINZA)
            c.alignment = Alignment(horizontal="center")
            if reg and reg[4]:
                c.comment = Comment(reg[4][:300], "agente 9")

    ws.freeze_panes = "F2"

    # ---------------------------------------------------------------- AMPLIaGRO
    ws = wb.create_sheet("AMPLIAGRO")
    cabecalho(
        ws,
        1,
        [
            "ID",
            "Grupo",
            "Dimensao",
            "Veredicto",
            "Evidencia (ficheiro:linha)",
            "O que a linha diz",
            "Leitura",
        ],
        [8, 16, 42, 11, 40, 68, 54],
    )
    LEITURA = {
        "C": "A linha produz a capacidade. Aprovado.",
        "E": "A capacidade existe, mas a evidencia e' um campo, uma constante ou "
        "um nome de view. Nao e' implementacao — e' estrutura.",
        "N": "Nenhum achado em codigo de execucao (testes excluidos).",
    }
    for i, (cid, grupo, nome, _p) in enumerate(COLUNAS, 2):
        est, ev, nota = VEREDITOS[cid]
        ws.cell(row=i, column=1, value=cid)
        ws.cell(row=i, column=2, value=grupo)
        ws.cell(row=i, column=3, value=nome)
        c = ws.cell(row=i, column=4, value=est)
        c.fill = MARCA_COR[est]
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
        ws.cell(row=i, column=5, value=ev or "(nenhum)")
        ws.cell(row=i, column=6, value=nota).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
        ws.cell(row=i, column=7, value=LEITURA[est]).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
    ws.freeze_panes = "A2"

    # ---------------------------------------------------------------- QUEM PASSA
    ws = wb.create_sheet("QUEM-PASSA")
    cabecalho(
        ws,
        1,
        [
            "ID",
            "Dimensao",
            "Lideres com evidencia",
            "N.",
            "Ampliagro",
            "Ampliagro le?",
            "Natureza",
            "Leitura",
        ],
        [8, 42, 60, 5, 11, 13, 22, 76],
    )
    for i, (cid, _grupo, nome, _p) in enumerate(COLUNAS, 2):
        leaders = [
            n
            for n, *_ in CONCORRENTES
            if (EVIDENCIA.get((n, cid)) or ("", "", "", "?", ""))[3] in ("F", "D", "P")
        ]
        est = VEREDITOS[cid][0]
        ws.cell(row=i, column=1, value=cid)
        ws.cell(row=i, column=2, value=nome)
        ws.cell(
            row=i,
            column=3,
            value=", ".join(leaders) if leaders else "— nenhum com evidencia",
        )
        c = ws.cell(row=i, column=4, value=len(leaders))
        c.alignment = Alignment(horizontal="center")
        c2 = ws.cell(row=i, column=5, value=est)
        c2.fill = MARCA_COR[est]
        c2.font = Font(bold=True)
        c2.alignment = Alignment(horizontal="center")
        le = {"C": "Passa", "E": "De passagem", "N": "Nao passa"}[est]
        c3 = ws.cell(row=i, column=6, value=le)
        c3.alignment = Alignment(horizontal="center")
        # natureza: e' gap competitivo ou ausencia de benchmark?
        if est != "N":
            natureza = "—"
        elif leaders:
            natureza = "LACUNA COMPETITIVA"
        else:
            natureza = "SEM BENCHMARK"
        c4 = ws.cell(row=i, column=7, value=natureza)
        c4.alignment = Alignment(horizontal="center")
        if natureza != "—":
            c4.font = Font(bold=True)
        leitura = (
            f"{len(leaders)} lider(es) com evidencia de fonte. "
            + {
                "C": "O Ampliagro confirma por codigo.",
                "E": "O Ampliagro tem a estrutura, nao a implementacao.",
                "N": "O Ampliagro nao tem. "
                + (
                    "Coluna onde o investimento tem retorno mais alto."
                    if cid in {"F16", "F05", "F02", "L05", "M05", "G05"}
                    else ""
                ),
            }[est]
        )
        ws.cell(row=i, column=8, value=leitura).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
    ws.freeze_panes = "A2"

    # ---------------------------------------------------------------- COMERCIAL
    ws = wb.create_sheet("COMERCIAL")
    cabecalho(
        ws,
        1,
        ["Aplicacao", "Modelo", "Preco declarado", "Fonte", "Nota"],
        [26, 30, 30, 24, 76],
    )
    COMERCIAL = [
        (
            "Aegro",
            "SaaS por ha/plano",
            "~R$ 374/mes (base)",
            "aegro.com.br",
            "'3 milhoes de hectares', 10 anos. 6 planos; Imagens, Maquinas, Livro "
            "Caixa e MIP sao add-ons.",
        ),
        (
            "Lucro Rural",
            "SaaS por plano",
            "Produtor R$ 374/mes · Contador R$ 348/mes",
            "lucrorural.com.br",
            "Plano separado para escritorio de contabilidade, por volume de produtores.",
        ),
        (
            "upCampo",
            "SaaS anual + por ha",
            "desde R$ 15.000/ano · R$ 15/ha/ano ate 1.000 ha",
            "upcampo.com.br",
            "'usuarios ilimitados'. Declara NAO fazer contabilidade — posicao, "
            "nao limitacao.",
        ),
        (
            "Senior / GATec",
            "Licencamento",
            "Sob consulta",
            "site.senior.com.br",
            "Ecosistema de partner (GATec) para dentro do ERP.",
        ),
        (
            "TOTVS PIMS Agro",
            "Licencamento + ISV",
            "Sob consulta",
            "produtos.totvs.com",
            "Java corporate; fora de escala para o produtor de talhao.",
        ),
        (
            "Fluere Carbon",
            "Projeto",
            "'Resultados em 30-60 dias'",
            "fluere.ag",
            "Valida com UFSM, FAPESP, CNPq. O preco nao e' publicado.",
        ),
        (
            "AMPLIAGRO",
            "Self-hosted (PostgreSQL + Docker)",
            "Sem licenca",
            "—",
            "O preco zero e' defensavel. O custo de entrada e' a instalacao — e "
            "e' ai que um ERP comercial ganha.",
        ),
    ]
    for i, linha in enumerate(COMERCIAL, 2):
        for j, v in enumerate(linha, 1):
            ws.cell(row=i, column=j, value=v).alignment = Alignment(
                wrap_text=True, vertical="top"
            )
    ws.freeze_panes = "A2"

    # ---------------------------------------------------------------- FONTES
    ws = wb.create_sheet("FONTES")
    cabecalho(ws, 1, ["Fonte", "O que foi lido", "Data"], [52, 96, 14])
    FONTES = [
        (
            "aegro.com.br/solucoes/gestao-rural",
            "orcado por talhao, orcado vs. realizado, baixa automatica de estoque, NDVI",
            "2026-10-05",
        ),
        (
            "aegro.com.br/produtos/plano-aegro-lucratividade",
            "OFX, fotos georreferenciadas, 500 ha, add-ons",
            "2026-10-05",
        ),
        (
            "aegro.com.br/produtos/plano-aegro-premium",
            "BI, Compare Safras, categorias",
            "2026-10-05",
        ),
        (
            "aegro.com.br (FAQ)",
            "NF-e e MDF-e gratis; Aegrozap; integracoes; exportacao",
            "2026-10-05",
        ),
        (
            "lucrorural.com.br",
            "LCDPR, NCM 98%, presumido x resultado, projecao de IR",
            "2026-10-05",
        ),
        (
            "upcampo.com.br",
            "UPi no WhatsApp, conector MCP, API publica, preco, 'nao faz contabilidade'",
            "2026-10-05",
        ),
        (
            "site.senior.com.br/agronegocio/funcionalidades-erp-agronegocio",
            "LCDPR, Mapfy, Simple Farm, Shield, Mao de Obra",
            "2026-10-05",
        ),
        (
            "documentacao.senior.com.br (integracao GATec)",
            "nativa com ERP/WMS/TMS",
            "2026-10-05",
        ),
        ("fluere.ag", "MRV, GHG Protocol, SBTi, CBAM, ISSB", "2026-10-05"),
        ("erpresearch.com", "paisagem global de ERP agro 2026", "2026-10-05"),
        ("gitnux.org / worldmetrics.org", "paisagem de ag-tech 2026", "2026-10-05"),
        ("agrichain.com", "contratos, balanca, liquidacao", "2026-10-05"),
        (
            "Codigo do Ampliagro",
            "medido por `docs/sistema/comparativo/medir_ampliagro.py` e adjudicado em `vereditos.py`",
            "2026-10-05",
        ),
    ]
    for i, linha in enumerate(FONTES, 2):
        for j, v in enumerate(linha, 1):
            ws.cell(row=i, column=j, value=v).alignment = Alignment(
                wrap_text=True, vertical="top"
            )

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(DESTINO)
    return DESTINO


if __name__ == "__main__":
    p = construir()
    print(f"  escrita: {p}")
    print(f"  tamanho: {p.stat().st_size:,} bytes".replace(",", "."))
