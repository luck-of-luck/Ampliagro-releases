"""O comparativo como FONTE DE VERDADE MEDIDA, e nao como hipotese.

O QUE ISTO E
============
`docs/sistema/comparativo/comparativo-100x50.xlsx` tem 100 aplicacoes x 50
capacidades. MEDIDO 2026-10-05: das 5 000 celulas, **4 928 sao `?`** — nao
medido. So 68 estao confirmadas. Ou seja, a matriz e' uma lista de
hipoteses sobre o que cada produto tem, e nao um benchmark.

Isso nao a inutiliza: da a DIMENSAO (que 50 capacidades existem e porque
contam numa decisao de compra) e o NOME delas. O que nao da e' a posicao
dos concorrentes.

A METADE QUE ESTA MODULE ENTREGA
================================
Os concorrentes, ninguem aqui os mede sem fonte. Ja o lado do Ampliagro e'
medivel a partir do codigo, e e' a metade que manda no roadmap. Por isso
este modulo responde a pergunta que responde ao dinheiro: **das 50
capacidades, quais existem no codigo, e onde.**

A DECISAO DE DESENHO QUE IMPORTA
================================
As sondas sao **DECLARADAS**, nao inferidas.

A alternativa — procurar "NF-e" no texto do codigo e dar `F` — seria um
teste que passa a falso. Encontra-se a palavra numa string de um prompt e
conclui-se que a nota existe. O mesmo vale para `provedor` de uma feature
que so esta escrita num docstring.

Por isso cada capacidade declara o que prova que ela funciona, e o que
nao prova devolve `nao_verificada`, que e' um estado honesto e util. Um
`nao_verificada` no catalogo e' um trabalho a fazer; um `F` inventado e' um
defeito — e e' exactamente o que o projecto inteiro existe para evitar
(`proveniencia.py`: "o sistema nunca promove uma afirmacao a medicao").

Consequencia deliberada: **este modulo nao diz que estamos em primeiro
lugar em lado nenhum.** Nao tem evidencia para dizer.Um objecto que
publica "somos os melhores em 43 de 50" sem medir e' o oposto do que se
quer.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any, Callable

RAIZ = pathlib.Path(__file__).resolve().parents[2]
XLSX = RAIZ / "docs" / "arquitetura" / "sistema" / "comparativo" / "comparativo-100x50.xlsx"

# Os quatro estados. Deliberadamente NAO existe "completo" sem prova.
AUSENTE = "ausente"  # medido: a capacidade nao existe
PARCIAL = "parcial"  # medido: existe parte, e sabemos qual
VERIFICADA = "verificada"  # medido: a sonda passa
NAO_VERIFICADA = "nao_verificada"  # ainda nao medido — trabalho a fazer

ORDEM = {VERIFICADA: 0, PARCIAL: 1, AUSENTE: 2, NAO_VERIFICADA: 3}


# ── as sondas: cada uma declara o que prova que a capacidade existe ────────
# Cada sonda recebe a raiz do repositorio e devolve a EVIDENCIA (uma string
# com `ficheiro:linha`) ou None. Nao devolve um booleano porque o
# porquê-importa tanto como o quê.
Sonda = Callable[[pathlib.Path], str | None]


def _procurar(*nomes: str, extensions: tuple[str, ...] = (".py",)) -> Sonda:
    """Sonda por simbolo: existe uma definicao com este nome?

     MEDIDO 2026-10-04: a primeira versao so aceitava `extension=".py"`, e a
     sonda de `M08` procurava `wizTalhaoStep` — que vive em `ia-local.js`.
     Dava `ausente` para sempre, e o estado `ausente` significa "MEDIDO: nao
     existe". Um falso `ausente` e' pior do que um falso `parcial`: diz que
    fell nao ha codigo, e quem ler acredita.
    """

    # Um padrao, e nao uma lista de prefixos: `async function` e' uma forma
    # tao comum num codebase com JS que merece estar coberta por
    # construcao. MEDIDO 2026-10-04 — o teste deste simbolo falhou DUAS
    # vezes: primeiro por `.py` apenas, depois porque a linha e'
    # `async function wizTalhaoStep` e o predicado aceitava `function `
    # mas nao `async function `.
    padroes = [
        re.compile(r"\s*(?:async\s+)?(?:function|def|class)\s+%s\b" % re.escape(nome))
        for nome in nomes
    ]

    def sonda(raiz: pathlib.Path) -> str | None:
        for pasta in (raiz / "app", raiz / "config"):
            if not pasta.is_dir():
                continue
            for ext in extensions:
                for ficheiro in pasta.rglob("*" + ext):
                    try:
                        texto = ficheiro.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    for n, linha in enumerate(texto.split("\n"), 1):
                        if any(p.match(linha) for p in padroes):
                            return "%s:%d" % (
                                ficheiro.relative_to(raiz).as_posix(),
                                n,
                            )
        return None

    return sonda


def _contem(*marcas: str, ficheiro: str = "", dentro_de: str = "") -> Sonda:
    """Sonda por conteudo num ficheiro especifico.

    `dentro_de` e' o nome de outro simbolo: a marca so conta se estiver no
    corpo dele. Evita o falso positivo classico — a palavra existe no
    ficheiro, mas noutra funcao.
    """

    def sonda(raiz: pathlib.Path) -> str | None:
        alvo = raiz / ficheiro
        if not alvo.is_file():
            return None
        try:
            linhas = alvo.read_text(encoding="utf-8", errors="replace").split("\n")
        except OSError:
            return None
        inicio = 0
        if dentro_de:
            for n, linha in enumerate(linhas):
                if linha.lstrip().startswith(("def ", "class ")) and dentro_de in linha:
                    inicio = n
                    break
        for n in range(inicio, len(linhas)):
            if any(m in linhas[n] for m in marcas):
                return "%s:%d" % (ficheiro, n + 1)
        return None

    return sonda


def _ambos(*sondas: Sonda) -> Sonda:
    """Todas as sondas tem de passar. Para capacidades com varias partes."""

    def sonda(raiz: pathlib.Path) -> str | None:
        evidencias = []
        for s in sondas:
            ev = s(raiz)
            if ev is None:
                return None
            evidencias.append(ev)
        return " + ".join(evidencias)

    return sonda


#: capability_id -> (rotulo curto, sonda, nota do que a sonda NAO prova)
#:
#: A nota e' o que impede este modulo de mentir. Cada capacidade Medida tem
#: uma razao declarada pelaqual ainda nao merece `verificada`.
SONDAS: dict[str, tuple[str, Sonda | None, str]] = {
    # --- A. Fiscal -------------------------------------------------------
    "F01": (
        "LCDPR — Livro Caixa do Produtor Rural",
        _ambos(_procurar("LCDPRGenerator"), _procurar("lcdpr_export")),
        "prova que o gerador existe; NAO prova cobertura dos nove registos",
    ),
    "F02": (
        "NF-e do produtor rural",
        None,
        "nao ha emissao nem integracao — a decisao C3 do PLANO-EXECUCAO esta' em aberto",
    ),
    "F04": (
        "Certificado A1 / ICP-Brasil",
        None,
        "MEDIDO: zero ocorrencias de icp/pkcs12/assinatura em app/ e config/",
    ),
    # --- G. Dados — a dimensao onde ja fomos auditados -------------------
    "G01": (
        "Proveniencia de dado em codigo",
        _procurar("proveniencia"),
        "prova que o modulo existe; a cobertura real mede-se por teste, nao por presenca",
    ),
    "G03": (
        "Isolamento multi-empresa por tabela",
        _contem("TABELAS_VERIFICADAS", ficheiro="app/middleware.py"),
        "prova o porto unico; MEDIDO: 6 chaves, e nao ha teste que exija cobertura total",
    ),
    # --- M. Maq/IA --------------------------------------------------------
    "M08": (
        "Assistente conversacional e MCP",
        _ambos(
            _procurar("wizTalhaoStep", extensions=(".js", ".py")),
            _procurar("catalogo_de_capacidades"),
        ),
        "prova que a superficie existe; nao mede qualidade da resposta",
    ),
    # --- O. Campo --------------------------------------------------------
    "O02": (
        "Offline — escrita sem rede",
        _contem(
            "offline",
            dentro_de="def verificar_offline",
            ficheiro="app/static/js/data-sync.js",
        )
        or _procurar("offline"),
        "prova que ha codigo de fila; o que JA foi provado em execucao foi o `deletedIds`",
    ),
    "O01": (
        "Caderno de campo digital",
        _procurar("NotaCampo"),
        "prova o modelo; MEDIDO: `app/api/views/caderno.py` e um modulo novo de outra sessao",
    ),
}


VEREDITOS_PATH = RAIZ / "docs" / "arquitetura" / "sistema" / "comparativo" / "vereditos.py"


def _carregar_vereditos() -> dict[str, tuple[str, str, str]]:
    """`vereditos.py` — adjudicados a mao, com `ficheiro:linha`.

    Esta e' a AUTORIDADE do veredicto do Ampliagro. Vive em `docs/`, nao em
    `app/`, por isso importa-se por caminho e nao por package.

    Devolve {} em vez de rebentar: um veredito em falta tem de aparecer como
    falta na resposta, nunca como um 500 no meio de uma pergunta da IA.
    """
    if not VEREDITOS_PATH.is_file():
        return {}
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_vereditos_ampliagro", VEREDITOS_PATH
        )
        if spec is None or spec.loader is None:
            return {}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        v = getattr(mod, "VEREDITOS", None)
        if not isinstance(v, dict):
            return {}
        return {
            str(k): (
                str(t[0]),
                str(t[1] if len(t) > 1 else ""),
                str(t[2] if len(t) > 2 else ""),
            )
            for k, t in v.items()
            if isinstance(t, (tuple, list)) and t
        }
    except Exception:
        return {}


def _carregar_natureza() -> dict[str, str]:
    """Folha QUEM-PASSA: LACUNA COMPETITIVA ou SEM BENCHMARK.

    Distingue 'falhar para um lider que tem evidencia de fonte' de 'falhar
    para ninguem que ninguem provou que faz'. O segundo nao e' gap competitivo.
    """
    try:
        import openpyxl
    except ImportError:
        return {}
    if not XLSX.is_file():
        return {}
    try:
        wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
        ws = wb["QUEM-PASSA"]
        cabecalho = [
            str(c or "")
            for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        ]
        try:
            i_nat = cabecalho.index("Natureza")
        except ValueError:
            wb.close()
            return {}
        out: dict[str, str] = {}
        for linha in ws.iter_rows(min_row=2, values_only=True):
            if linha and linha[0]:
                out[str(linha[0]).strip()] = str(linha[i_nat] or "")
        wb.close()
        return out
    except Exception:
        return {}


#: Estado da sonda -> letra do veredicto, so para comparar as duas coisas.
_SONDA_PARA_LETRA = {VERIFICADA: "C", PARCIAL: "E", AUSENTE: "N"}


def _carregar_capacidades() -> dict[str, dict[str, Any]]:
    """As 50 capacidades, da folha COLUNAS. A fonte da DIMENSAO."""
    try:
        import openpyxl
    except ImportError:
        return {}
    if not XLSX.is_file():
        return {}
    try:
        wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
        ws = wb["COLUNAS"]
        out: dict[str, dict[str, Any]] = {}
        for linha in ws.iter_rows(min_row=2, values_only=True):
            if linha and linha[0]:
                out[str(linha[0]).strip()] = {
                    "id": str(linha[0]).strip(),
                    "grupo": linha[1],
                    "dimensao": linha[2],
                    "porque": linha[3] or "",
                }
        wb.close()
        return out
    except Exception:
        return {}


def _medir(
    capacidade_id: str, adjudicated: tuple[str, str, str] | None = None
) -> dict[str, Any]:
    """O estado de UMA capacidade: veredicto adjudicado + contra-prova da sonda.

    `estado`    — o estado da SONDA (o que o codigo automtico viu)
    `veredicto` — a letra ADJUDICADA em vereditos.py (a autoridade)

    Os dois raramente coincidem porque a sonda so existe para 6 das 50. Onde a
    sonda existe e discorda, `divergencia` fica True e o modulo NAO escolhe:
    quem decide e' o veredito lido a mao, e a divergencia e' reportada.
    """
    rotulo, sonda, nota = SONDAS.get(capacidade_id, (None, None, "sem sonda declarada"))
    saida: dict[str, Any] = {}

    if sonda is None:
        saida.update({"estado": NAO_VERIFICADA, "evidencia": None, "nota": nota})
    else:
        try:
            evidencia = sonda(RAIZ)
        except Exception as exc:  # uma sonda que rebenta nao mede nada
            saida.update(
                {
                    "estado": NAO_VERIFICADA,
                    "evidencia": None,
                    "nota": "a sonda levantou %s: %s" % (type(exc).__name__, exc),
                }
            )
        else:
            if evidencia is None:
                saida.update({"estado": AUSENTE, "evidencia": None, "nota": nota})
            else:
                # Existe e a sonda passou — mas ISTO NAO E' `verificada`. Um simbolo
                # existente prova que ha codigo, nao que a capacidade funciona. Promover
                # a `verificada` exige um teste que exercite o comportamento, e essa e'
                # a etapa seguinte.
                saida.update({"estado": PARCIAL, "evidencia": evidencia, "nota": nota})

    # --- o veredicto adjudicado, que manda
    if adjudicated:
        letra, ficheiro, justificacao = adjudicated
        saida["veredicto"] = letra
        saida["evidencia_ficheiro"] = ficheiro or None
        saida["adjudicacao"] = justificacao or None
        letra_sonda = _SONDA_PARA_LETRA.get(saida["estado"])
        # So ha divergencia REAL quando a sonda existe de facto. Uma capacidade
        # sem sonda nao diverge: apenas nao foi automaticamente medida.
        saida["divergencia"] = bool(
            letra_sonda and letra_sonda != letra and sonda is not None
        )
    else:
        saida["veredicto"] = None
        saida["evidencia_ficheiro"] = None
        saida["adjudicacao"] = None
        saida["divergencia"] = False
    return saida


def medir_ampliagro() -> dict[str, Any]:
    """As 50 capacidades: veredicto adjudicado + contra-prova da sonda.

    `medidas` conta as adjudicadas (a autoridade), nao as que a sonda viu. Sao
    numeros diferentes de proposito: o que a medicao automatica viu e' muito menor do que
    o quanto medido a mao, e dizer '44 por medir' escondia 44 veredictos lidos.
    """
    caps = _carregar_capacidades()
    vered = _carregar_vereditos()
    natureza = _carregar_natureza()
    saida: list[dict[str, Any]] = []
    for cid in sorted(caps):
        item = dict(caps[cid])
        item.update(_medir(cid, vered.get(cid)))
        item["natureza"] = natureza.get(cid) or None
        saida.append(item)
    return {
        "capacidades": saida,
        "medidas": sum(1 for c in saida if c["veredicto"]),
        "por_medir": sum(1 for c in saida if not c["veredicto"]),
        "com_sonda": sum(1 for c in saida if c["estado"] != NAO_VERIFICADA),
        "divergencias": [c["id"] for c in saida if c["divergencia"]],
        "total": len(saida),
    }


def por_grupo() -> dict[str, dict[str, int]]:
    """O resumo por dimensao. E' o que a IA quer primeiro."""
    resultado: dict[str, dict[str, int]] = {}
    for c in medir_ampliagro()["capacidades"]:
        g = str(c["grupo"] or "sem grupo")
        d = resultado.setdefault(g, {})
        letra = c.get("veredicto") or "?"
        d[letra] = d.get(letra, 0) + 1
        d["total"] = d.get("total", 0) + 1
    return resultado


def divergencias() -> dict[str, dict[str, Any]]:
    """Onde a sonda automatica e o veredito adjudicado discordam.

    Devolve {} no caso normal. Divergencia e' um sinal de que alguma das duas
    medidas envelheceu — e o sitio onde se olha primeiro.
    """
    out: dict[str, dict[str, Any]] = {}
    for c in medir_ampliagro()["capacidades"]:
        if c.get("divergencia"):
            out[c["id"]] = {
                "dimensao": c.get("dimensao"),
                "sonda": c.get("estado"),
                "veredicto": c.get("veredicto"),
                "evidencia_ficheiro": c.get("evidencia_ficheiro"),
                "adjudicacao": c.get("adjudicacao"),
            }
    return out


def texto_para_a_ia() -> str:
    """O resumo em prosa, para a AmplIA responder sem chumbar JSON."""
    m = medir_ampliagro()
    div = m.get("divergencias") or []
    linhas = [
        "Comparativo 100x50 — o lado do Ampliagro, medido em codigo.",
        "",
        "%d de %d capacidades tem VEREDITO ADJUDICADO (C confirmado / E "
        "enfraquecido / N ausente), com ficheiro:linha. O veredicto vem de "
        "vereditos.py, que e' leitura a mao — nao de procura automatica."
        % (m["medidas"], m["total"]),
        "",
        "A contra-prova automatica (sondas) cobriu %d de %d. Onde existe e "
        "discorda do veredicto, o modulo NAO escolhe: reporta."
        % (m.get("com_sonda", 0), m["total"]),
    ]
    if div:
        linhas.append("Divergencias sonda-vs-veredicto: %s" % ", ".join(div))
    else:
        linhas.append("Divergencias sonda-vs-veredicto: nenhuma.")
    linhas += [
        "",
        "Estados da sonda: verificada = teste que exercita. parcial = ha codigo "
        "(evidencia dada), mas isso nao prova que funcione. ausente = medido, nao "
        "existe. nao_verificada = a sonda automatica nao cobre esta capacidade "
        "— NAO significa que esteja por medir.",
        "",
    ]
    for g, contagens in sorted(por_grupo().items()):
        partes = []
        for letra, nome in (
            ("C", "confirmado"),
            ("E", "enfraquecido"),
            ("N", "ausente"),
        ):
            if contagens.get(letra):
                partes.append("%s %d" % (letra, contagens[letra]))
        linhas.append("%-14s %s" % (g, " · ".join(partes)))
    if div:
        linhas.append("")
        linhas.append("Onde a sonda discorda do veredicto (a sonda e' mais fraca, ")
        linhas.append("nao mais recente — o veredicto lido a mao e' que manda):")
        for cid, d in sorted(divergencias().items()):
            linhas.append(
                "  %-5s sonda=%-12s veredicto=%-2s %s"
                % (cid, d["sonda"], d["veredicto"], d["evidencia_ficheiro"])
            )
    return "\n".join(linhas)


def catalogo_comparativo(grupo: str | None = None) -> dict[str, Any]:
    """O que o MCP expoe. Filtra por grupo."""
    m = medir_ampliagro()
    caps = m["capacidades"]
    if grupo:
        alvo = grupo.strip().lower()
        caps = [c for c in caps if alvo in str(c["grupo"] or "").lower()]
    lacunas = [
        c
        for c in caps
        if c.get("veredicto") == "N" and c.get("natureza") == "LACUNA COMPETITIVA"
    ]
    sem_bench = [
        c
        for c in caps
        if c.get("veredicto") == "N" and c.get("natureza") == "SEM BENCHMARK"
    ]
    return {
        "fonte": XLSX.relative_to(RAIZ).as_posix() if XLSX.is_file() else None,
        "fonte_do_veredicto": "docs/arquitetura/sistema/comparativo/vereditos.py",
        "aviso": (
            "A coluna dos concorrentes esta 98,6% por medir (4928 de 5000 celulas "
            "sao '?'). Este catalogo NAO diz a posicao de ninguem: so o que o "
            "Ampliagro tem, com ficheiro:linha. O veredicto e' adjudicado a mao."
        ),
        "total": m["total"],
        "com_veredicto": m["medidas"],
        "sem_veredicto": m["por_medir"],
        "com_sonda": m.get("com_sonda", 0),
        "divergencias": m.get("divergencias", []),
        "leitura": (
            "SAO DOIS NUMEROS DIFERENTES E NAO SE CONFUNDAM.\n"
            "`com_veredicto` = quantas capacidades tem VEREDITO adjudicado a mao "
            "(com ficheiro:linha). `com_sonda` = quantas a sonda automatica "
            "encontrou em codigo.\n\n"
            "O veredicto e' a autoridade; a sonda e' a contra-prova, e quando "
            "discordam a discordancia esta' em `divergencias`.\n\n"
            "NUNCA reported 'temos N de 50' a partir de `com_veredicto`: um "
            "veredicto adjudicado diz que alguem LEU o codigo, nao que um teste "
            "PASSOU. Para 'isto funciona e esta' testado', o campo e' "
            "`resumo.confirmadas` — e mesmo esse exige o teste que o sustenta.\n\n"
            "Para dizer o que FAZ falta, le `resumo.ausentes` e "
            "`resumo.lacunas_competitivas`."
        ),
        "resumo": {
            "confirmadas": sum(1 for c in caps if c.get("veredicto") == "C"),
            "enfraquecidas": sum(1 for c in caps if c.get("veredicto") == "E"),
            "ausentes": sum(1 for c in caps if c.get("veredicto") == "N"),
            "lacunas_competitivas": [c["id"] for c in lacunas],
            "sem_benchmark": [c["id"] for c in sem_bench],
        },
        "capacidades": caps,
    }
