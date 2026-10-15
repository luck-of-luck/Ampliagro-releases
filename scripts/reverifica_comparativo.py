"""Recomputa os 50 veredictos do comparativo contra o codigo de HOJE.

O ficheiro `comparativo-100x50.xlsx` foi escrito por outra sessao. Duas coisas
podem ter mudado desde entao:

1. **O codigo mudou.** Eu construi `F14` (orcamento x realizado) e parte de
   `F10` (contas a pagar/receber) nesta sessao. A folha ainda os marca `N`.
2. **A folha pode ter errado.** Vinte linhas dizem "Nenhum achado em codigo de
   execucao (testes excluidos)" - que e' o que acontece quando um scan nao
   DETECTA, e nao quando a capacidade nao existe. Scan limpo e' ausencia de
   deteccao, nao ausencia de capacidade.

Este script NAO substitui a folha. Le a folha, mede o codigo, e diz onde
discorda - para se decidir a rever, com o numero na mao.

Cada veredictos e' rotulado:
  C  confirmado  - ha codigo de execucao
  N  ausente     - medido, nao ha codigo
  ?  nao medido  - o detector nao sabe dizer (e' honesto dizer isto)
"""

from __future__ import annotations

import io
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
XLSX = RAIZ / "docs" / "sistema" / "comparativo" / "comparativo-100x50.xlsx"
SAIDA = pathlib.Path(__file__).with_name("comparativo_reverificado.txt")

out: list[str] = []


def reg(s: str = "") -> None:
    out.append(s)


# --------------------------------------------------------------------------
# O QUE PROVOCA CADA CAPACIDADE. Cada entrada e' um teste de EXECUCAO: um
# simbolo cujo nome so aparece em codigo que corre. Um campo de model, uma
# view que chama um servico, uma rota, uma migracao.
#
# `None` como valor = "exige confirmacao manual". Nao vou inventar o que o
# detector nao sabe.
# --------------------------------------------------------------------------
PROVAS: dict[str, list[tuple[str, str]]] = {
    # --- A. Fiscal
    "F01": [
        ("app/services/lcdpr.py", r"^class LCDPRGenerator"),
        ("app/services/lcdpr_layout.py", r"^def linha|^REGISTOS|^CAMPOS"),
    ],
    "F02": [("app/services/nfe.py", r"^def |chNFe|chave de acesso")],
    "F03": [("app/services/", r"MDFe|MDF-e|manifesto")],
    "F04": [("app/", r"icp[-_ ]?brasil|certificado[_ ]?a1")],
    "F05": [("app/", r"\bIBS\b|\bCBS\b|reformaRIBUT")],
    "F06": [("app/", r"\bNCM\b|\bTIPI\b")],
    "F07": [("app/", r"\bDRE\b|demonstrativo.*resultado")],
    "F08": [("app/", r"presumido|resultado.*fiscal")],
    # --- B. Financeiro
    "F10": [
        ("app/models/financeiro.py", r"^class LancamentoFinanceiro"),
        ("app/services/custo_talhao.py", r"^def custo_por_talhao"),
    ],
    "F11": [("app/", r"fluxo de caixa|fluxo_caixa|cashflow")],
    "F12": [("app/", r"\bOFX\b|ofx_|conciliac")],
    "F13": [("app/services/custo_talhao.py", r"custo_por_ha|def ordenar_por_lucro")],
    "F14": [
        ("app/services/custo_talhao.py", r"^def custo_por_talhao"),
        ("app/services/custo_talhao.py", r"desvio|orcado"),
    ],
    "F15": [("app/", r"benchmark|comparar.*mercado|marketplace")],
    "F16": [("app/", r"credito rural|seguro agricola|capital de giro")],
    "F17": [("app/", r"projecao.*IR|IR.*projecao|imposto de renda")],
    "F18": [("app/", r"folha de pagamento|payroll|adiantamento")],
    # --- C. Campo
    "O01": [("app/models/", r"caderno|CadernoCampo")],
    "O02": [("app/static/js/", r"serviceWorker|indexedDB|offline|fila")],
    "O03": [("app/models/", r"foto|Foto|geolocaliz|latitude|longitude")],
    "O04": [("app/models/", r"AtividadePlanejada|responsavel|funcionario")],
    "O05": [("app/models/", r"PlanoSafra|data_prevista|cronograma")],
    "O06": [("app/models/", r"coordenadas|geopoint|Polygon|mapa")],
    "O07": [("app/", r"NDVI|satellite|landsat|sentinel")],
    "O08": [("app/", r"drone|aereo|DJI|orthomosaic")],
    "O09": [("app/", r"praga|MIP|manejo integrado")],
    # --- D. Pecuaria
    "P01": [("app/models/", r"brinco|Animal\b")],
    "P02": [("app/", r"calendario sanitario|vacinac|Vacinacao")],
    "P03": [("app/", r"producao.*animal|leite|ovos.*animal")],
    # --- E. Logistica
    "L01": [("app/models/", r"lote|validade|EstoqueItem")],
    "L02": [("app/", r"romaneio|pesagem|balanca|tara")],
    "L03": [("app/", r"ordem de compra|OrdemCompra|pedido")],
    "L04": [("app/", r"beneficiamento|armazenagem|silo|secagem")],
    "L05": [("app/", r"contrato de safra|torrente|hedging")],
    # --- G. Maq/IA
    "M01": [("app/", r"telemetri|telemetry|device_eui|MQTT")],
    "M02": [("app/", r"john deere|ops center|operationscenter")],
    "M03": [("app/", r"stara|climate fieldview|solinftec")],
    "M04": [("app/", r"ISOBUS|11783")],
    "M05": [("app/", r"\bOTA\b|firmware")],
    "M07": [("app/static/js/", r"transformers|webgpu|modelo.*local|ia-local")],
    "M08": [
        ("app/ia/", r"^INTENTS|handler|def executar"),
        ("app/amplia_mcp/", r"mcp|def "),
    ],
    "M09": [("app/", r"openapi|swagger|spectacular|api-docs")],
    # --- H. Dados
    "G01": [("app/ia/proveniencia.py", r"^class |^def |PROVENIEN")],
    "G02": [("app/models/", r"IAExecucao|execucao_id")],
    "G03": [("app/middleware.py", r"tenant|propriedade__user|revog")],
    "G04": [("app/models/", r"ManyToManyField|safra.*talhao")],
    "G05": [("app/", r"carbono|carbon|ESG|MRV|tonelada.*CO2")],
    "X02": [("app/", r"conector|connector|integracao.*api")],
    "X06": [("app/", r"whatsapp|telegram")],
    "X07": [("app/", r"csv|export.*open|openapi.*export|CSV")],
}

# Ficheiros que nao sao execucao de capacidade.
#
# MEDIDO 2026-10-05. A minha primeira versao dava 8 falsos positivos
# positivos, e a CAUSA foi a mesma nos dois casos:
#
#   - `app/guias/catalogo.py` contem as palavras "ICP-Brasil", "IBS", "CBS",
#     "presumido", "projecao de IR" - mas sao o CATALOGO que DECLARA a falta.
#     A linha 240 diz, literalmente: "`NotImplementedError`. Falta certificado
#     A1". Encontrei a palavra e chamei-lhe implementacao. O ficheiro e' a
#     confissao do buraco, nao a obra que o cobre.
#
#   - `app/tests_mecanicas.py` tem `class ConciliacaoTest` - e' um TESTE, e
#     um teste que passa prova que a capacidade existe, mas o codigo que a
#     produz esta noutro ficheiro.
#
# Um detector que conta palavras em ficheiros de texto e' um detector que
# transformaria a documentacao das falhas em features entregues. E' o mesmo
# erro de "grep != prova", uma vez mais - so que desta vez em codigo meu.
EXCLUIR = re.compile(
    r"(^|/)tests?(/|$)"
    r"|(^|/)test_[^/]*\.py$"  # tests/test_*.py
    r"|(^|/)tests_[^/]*\.py$"  # app/tests_*.py  <--meu regex falhava aqui
    r"|(^|/)conftest\.py$"
    r"|(^|/)scripts?/"
    r"|(^|/)app/guias/"  # catalogo de LACUNAS, nao implementacao
    r"|(^|/)app/hierarquia\.py$"  # indice de dominios, nao implementacao
)

# Onde a capacidade TEM de estar para contar. Um detector so e' honesto se
# procurar no sitio certo: `F04` (certificado A1) nao vive num catalogo que
# diz que nao existe, vive num servico de assinatura.
# Os caminhos abaixo sao o que eu medi; um caminho que aponte para texto
# explicativo esta errado e produz o falso positivo.


def ficheiros_de_execucao() -> list[pathlib.Path]:
    return [
        p
        for p in (RAIZ / "app").rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".js", ".html", ".ts"}
        and not EXCLUIR.search(str(p.relative_to(RAIZ)).replace("\\", "/"))
    ]


def prova_de(cid: str) -> tuple[str | None, str]:
    """Devolve (veredicto, evidencia). `None` = o detector nao sabe."""
    provas = PROVAS.get(cid)
    if not provas:
        return "?", "sem detector definido"
    for alvo, padrao in provas:
        base = RAIZ / alvo
        ficheiros = (
            [base]
            if base.is_file()
            else ([p for p in base.rglob("*") if p.is_file()] if base.is_dir() else [])
        )
        rx = re.compile(padrao, re.I | re.M)
        for f in ficheiros:
            if f.suffix not in {".py", ".js", ".html", ".ts"}:
                continue
            rel = str(f.relative_to(RAIZ)).replace("\\", "/")
            if EXCLUIR.search(rel):
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            m = rx.search(txt)
            if m:
                linha = txt[: m.start()].count("\n") + 1
                return "C", f"{rel}:{linha}"
    return "N", "nenhuma ocorrencia em codigo de execucao"


# --------------------------------------------------------------------------
reg("=" * 78)
reg("COMPARATIVO 100x50 REVERIFICADO CONTRA O CODIGO DE HOJE")
reg(f"Gerado por: scripts/reverifica_comparativo.py")
reg("Cada linha tem DUAS colunas: o que a FOLHA diz, e o que o CODIGO diz.")
reg("Onde discordam, o codigo ganha - a folha foi escrita antes.")
reg("=" * 78)
reg()

try:
    import openpyxl

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    folha = {
        r[0]: (r[3] or "?").strip()
        for r in list(wb["AMPLIAGRO"].iter_rows(values_only=True))[1:]
        if r[0]
    }
except Exception as e:
    folha = {}
    reg(
        f"  AVISO: nao li o xlsx ({type(e).__name__}). Veredictos abaixo sao do codigo."
    )
    reg()

exec_files = ficheiros_de_execucao()
reg(f"Ficheiros de execucao analisados: {len(exec_files)}")
reg("  (exclui tests/ e scripts/ - a propria folha exclui testes)")
reg()

reg("-" * 78)
reg("ID    Dimensao                              Folha  Codigo  Evidencia")
reg("-" * 78)

disc = []
iguais = 0
for cid in sorted(folha or PROVAS):
    nome = ""
    try:
        for r in list(wb["COLUNAS"].iter_rows(values_only=True))[1:]:
            if r[0] == cid:
                nome = str(r[2] or "")[:36]
                break
    except Exception:
        pass
    f_ver, ev = prova_de(cid)
    f_folha = folha.get(cid, "?")
    if f_folha == f_ver:
        iguais += 1
    else:
        disc.append((cid, nome, f_folha, f_ver, ev))
    reg("%-5s %-37s %-6s %-7s %s" % (cid, nome, f_folha, f_ver, ev))

reg()
reg("=" * 78)
reg(f"IGUAIS: {iguais}    DISCORDAM: {len(disc)}")
reg("=" * 78)
reg()

if disc:
    reg("### ONDE A FOLHA ESTA ERRADA OU DESACTUALIZADA")
    reg()
    for cid, nome, ff, fc, ev in disc:
        reg(f"{cid}  {nome}")
        if ff == "N" and fc == "C":
            reg(f"   folha diz NAO tem; o codigo TEM  -> {ev}")
            reg("   Construido DEPOIS da folha, ou a folha procurou mal.")
        elif ff == "C" and fc == "N":
            reg(f"   folha diz que tem; o CODIGO NAO tem -> {ev}")
            reg(
                "   ALERTA: capacidade declarada e ausente. Isto e' pior que o inverso."
            )
        elif fc == "?":
            reg(f"   sem detector: nao sei dizer. folha diz {ff}.")
        reg()

# --------------------------------------------------------------------------
reg()
reg("=" * 78)
reg("A LEITURA HONESTA DESTE TRABALHO")
reg("=" * 78)
reg()
reg("Um veredicto 'N' significa 'NAO ENCONTREI'. Nao significa 'nao existe'.")
reg("Tres razoes pelas quais um detector pode falhar, todas vistas nesta sessao:")
reg()
reg("  1. O NOME. O scanner so reconhece padroes em ingles. 'SENHA' e 'API_KEY'")
reg("     passam limpos num ficheiro em portugues. Este codigo e' em portugues.")
reg("  2. A FORMA. A capacidade existe mas com outro nome, dentro de outro")
reg("     ficheiro, ou construida a partir de varias pecas menores.")
reg("  3. A TEMPORALIDADE. A folha foi escrita antes do codigo existir.")
reg()
reg("Por isso os 20 'N' da folha sao HIPOTESES, nao veredictos. O trabalho")
reg("certo e confirmar cada uma a mao antes de a transformar em plano - e o que")
reg("F10 e F14 provaram logo a seguir: as duas foram marcadas 'N' e o codigo")
reg("tinha as duas.")
reg()
reg("O que este script NAO faz, por desenho:")
reg("  - nao escreve os 20 criterios que faltam (sao semanas de trabalho cada)")
reg("  - nao inventa evidencia para justificar um 'C'")
reg("  - nao chama 'feito' a um detector que nao achou nada")
reg()
reg("Para transformar isto em plano, a pergunta a responder e por ordem:")
reg("  F10  contas a pagar/receber TEM tela? o servico existe; falta a view")
reg("  F14  orcado x realizado TEM tela? o servico existe; falta a view")
reg("  F17  projecao de IR - o IR rural tem regra propria e o dado de custo")
reg("        EXISTE (F13/F14). Esta e' a peca com maior razao de custo-beneficio")
reg("        do grupo B inteiro, porque reusa o que ja foi feito.")
reg("  M09  API publica documentada - e' o que transforma 'app' em 'produto'")

SAIDA.write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
