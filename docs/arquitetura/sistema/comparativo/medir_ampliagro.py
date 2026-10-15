"""As 50 colunas do comparativo, e a medicao do Ampliagro em cada uma.

A COLUNA DO AMPLIaGRO E' MEDIDA. As dos concorrentes nao — ver `concorrentes.py`,
que traz a marca de evidencia por celula.

Duas regras que o script respeita, e que vem da §A.0 do `docs/sistema/9.md`:

1. **Testes nao contam como implementacao.** `test_*.py`, `tests_*.py` e a pasta
   `tests/` ficam de fora. Um teste que menciona `blockchain` prova que alguem
   escreveu a palavra num teste.
2. **Achado precisa de linha.** Cada `IMPL` devolve `ficheiro:linha`. Sem
   linha nao ha evidencia, e sem evidencia nao ha celula marcada.

Uma nota sobre o que este ficheiro NAO e': nao e' um juizo. Mede o que ha no
codigo. A leitura competitive — quem ganha onde — e' da folha `ANALISE`, e
essa carrega o mesmo peso de evidencia.

AS 10 COLUNAS QUE SAIRAM
========================
A lista chegou a 60 e foi cortada para 50. O criterio foi "e' isto uma
capacidade, e medivel?". As razoes, para que o corte nao seja silencioso:

  F09  Escrituracao contabilizavel (SPED/ECD) — nenhum ERP de talhao vende; e'
       o espaco da contabilidade. A propria upCampo diz que nao cobre
       "amplitude de regras tributarias e obrigacoes acessorias".
  P04  Aquisicao de animais — fundida em P03. Sem identificacao individual a
       aquisicao nao se mede.
  P05  Inseminacao — fundida em P03, mesma condicao previa.
  X01  Preco — comercial, nao capacidade. Vai para a folha COMERCIAL.
  X03  Suporte e formacao — comercial.
  X04  Roadmap publico — promessa. E promessa mede-se pelo codigo.
  X05  Carbono pronto para MRV — duplica G05, e o Ampliagro mede zero nas duas.
  L06  Rastreabilidade de lote ponta a ponta — e' espaco dos ERPs de ALIMENTO
       (Aptean, Datacor), nao do ERP de talhao.
  M06  Sensores de solo e estacao meteorologica — a infra mede telemetria
       (M01); a estacao e' do INMET e nao e' um diferencial de produto.
  O08  Drones — **mantida**, apesar de fraca. Cortar dentro do que e'
       verificavel, nao dentro do queWish-for.
"""

from __future__ import annotations

import io
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[3]

ARQ_TESTE = re.compile(
    r"(^|[\\/])tests?[\\/]|test_\w+\.py$|tests_\w+\.py$|conftest\.py$"
)
IGNORAR = re.compile(
    r"node_modules|\.venv|staticfiles|_backups|\\migrations\\|__pycache__|\.pyc$"
)


def ficheiros(*globs: str):
    """Ficheiros de execucao. Testes fora."""
    vistos: set[pathlib.Path] = set()
    for g in globs:
        for p in RAIZ.glob(g):
            s = str(p)
            if IGNORAR.search(s) or ARQ_TESTE.search(s) or p in vistos:
                continue
            vistos.add(p)
            yield p


def procurar(
    padrao: str,
    *globs: str,
    excluir: tuple[str, ...] = (),
) -> tuple[str, str]:
    """(estado, evidencia). Estado e' 'IMPL' ou 'FALTA'. Evidencia tem sempre linha."""
    r = re.compile(padrao, re.I)
    for g in globs:
        for p in ficheiros(g):
            if any(x in p.name for x in excluir):
                continue
            with p.open(encoding="utf-8", errors="replace") as fh:
                linhas_arq = fh.read().splitlines()
            for i, ln in enumerate(linhas_arq, 1):
                if not r.search(ln):
                    continue
                if ln.strip().startswith("#"):
                    continue
                return "IMPL", f"{p.relative_to(RAIZ).as_posix()}:{i}"
    return "FALTA", ""


# Cada constante e' uma TUPLA de globs, nunca uma string. `procurar` faz
# `for g in globs`, e uma string seria iterada caractere a caractere — o `*`
# de `app/**/*.py` viraria um padrao absoluto, e o pathlib levanta
# `NotImplementedError: Non-relative patterns are unsupported`. Foi o que
# aconteceu na primeira versao.
PY = ("app/**/*.py",)
JS = ("app/static/js/**/*.js",)
TPL = ("app/templates/**/*.html",)
CFG = ("config/**/*.py",)
PYJS = PY + JS
ALL = PY + JS + TPL + CFG

# =====================================================================
# AS 50 COLUNAS: (id, grupo, nome, porque conta na decisao de compra)
# =====================================================================
COLUNAS: list[tuple[str, str, str, str]] = [
    # ---- A. Fiscal e tributario (8)
    (
        "F01",
        "A. Fiscal",
        "LCDPR — Livro Caixa do Produtor Rural",
        "O ficheiro que um produtor acima de R$ 4,8 mi tem de entregar na Receita. Opcional por lei, obrigatorio por medo.",
    ),
    (
        "F02",
        "A. Fiscal",
        "NF-e do produtor rural",
        "A nota que o bois vende. Sem isto emite-se noutro sitio e digita-se duas vezes.",
    ),
    (
        "F03",
        "A. Fiscal",
        "MDF-e — manifesto eletronico",
        "Aegro da'-lo gratis e sem limite, ate no plano gratuito. E' argumento de venda, nao funcionalidade.",
    ),
    (
        "F04",
        "A. Fiscal",
        "Certificado A1 / ICP-Brasil",
        "Sem assinatura ICP-Brasil nao ha LCDPR valido. Art. 23-A §2 da IN SRF 83/2001.",
    ),
    (
        "F05",
        "A. Fiscal",
        "Reforma Tributaria (IBS/CBS)",
        "Transicao 2026-2033. Todo ERP brasileiro adulto tem. Nao ter e' perder clientes.",
    ),
    (
        "F06",
        "A. Fiscal",
        "NCM / TIPI",
        "Classificacao fiscal do produto. Sem ela o imposto sai errado sem aviso.",
    ),
    (
        "F07",
        "A. Fiscal",
        "DRE rural por cultura e safra",
        "O produtor quer o lucro da soja separado do milho. E' a pergunta que o contador faz.",
    ),
    (
        "F08",
        "A. Fiscal",
        "Presumido x Resultado",
        "20% da receita bruta ou Livro Caixa: duas apuracoes, resultados diferentes.",
    ),
    # ---- B. Financeiro (9)
    (
        "F10",
        "B. Financeiro",
        "Contas a pagar e a receber",
        "A base de tudo. Requisito, nao diferencial.",
    ),
    (
        "F11",
        "B. Financeiro",
        "Fluxo de caixa",
        "A pergunta que o produtor faz todo dia: 'quanto tenho?'",
    ),
    (
        "F12",
        "B. Financeiro",
        "Conciliacao bancaria por OFX",
        "Aegro posiciona isto no plano Avancado — sinal de que o mercado ainda o cobra.",
    ),
    (
        "F13",
        "B. Financeiro",
        "Custo por talhao e por hectare",
        "A ferramenteira de decisao agricola. E' onde a Aegro marca territorio.",
    ),
    (
        "F14",
        "B. Financeiro",
        "Orcado x realizado",
        "Aegro chama a isto o produto: desvios antes de virarem preco.",
    ),
    (
        "F15",
        "B. Financeiro",
        "Benchmark de mercado entre produtores",
        "Aegro Compare Safras: dados anonimizados de outrosisfazendeiros. Nao se copia sem base instalada.",
    ),
    (
        "F16",
        "B. Financeiro",
        "Credito rural e seguro agricola",
        "A fonte de capital do produtor. Quase nenhum ERP de talhao cobre — e e' o maior ciclo de receita do agro.",
    ),
    (
        "F17",
        "B. Financeiro",
        "Projecao de IR ao longo do ano",
        "A Lucro Rural vende isto nomeadamente: 'vale comprar o trator agora?'",
    ),
    (
        "F18",
        "B. Financeiro",
        "Folha de pagamento rural",
        "Salario, producao por trabalhador, saida de safrista. Territorio TOTVS e Senior.",
    ),
    # ---- C. Campo e operacao (10)
    (
        "O01",
        "C. Campo",
        "Caderno de campo digital",
        "O registo oficial da lavoura. Tem de ser exportavel para o RFB.",
    ),
    (
        "O02",
        "C. Campo",
        "Offline real — escrita sem rede",
        "O produtor esta por definicao sem rede no talhao. Escrever offline nao e' extra, e' condicao.",
    ),
    (
        "O03",
        "C. Campo",
        "Fotos georreferenciadas",
        "Nota sem foto e' opiniao; foto com coordenada e' prova. Aegro e' explicito nisto.",
    ),
    (
        "O04",
        "C. Campo",
        "Gestao de tarefas com responsavel",
        "Quem faz o que, ate quando. Sem dono, o talhao nao anda.",
    ),
    (
        "O05",
        "C. Campo",
        "Planejamento de safra e cronograma",
        "Planejar e' metade do trabalho agricola.",
    ),
    (
        "O06",
        "C. Campo",
        "Mapas e geoespaciamento de talhoes",
        "Sem poligono nao ha custo por talhao, nem NDVI, nem nada disso.",
    ),
    (
        "O07",
        "C. Campo",
        "Imagens de satelite (NDVI)",
        "Add-on da Aegro. Entrou na lista de quem passa — mas e' add-on.",
    ),
    (
        "O08",
        "C. Campo",
        "Drones e imageamento aereo",
        "Alta altitude, baixa frequencia. Medivel por assinatura.",
    ),
    (
        "O09",
        "C. Campo",
        "MIP — manejo integrado de pragas",
        "Monitoramento com registo georreferenciado. Add-on da Aegro; forca da Senior (Shield).",
    ),
    # ---- D. Pecuaria (3)
    (
        "P01",
        "D. Pecuaria",
        "Rebanho individual (brinco)",
        "O animal tem identidade. Sem brinco nao ha manejo individual nem premium.",
    ),
    (
        "P02",
        "D. Pecuaria",
        "Calendario sanitario e vacinacao",
        "Obrigatorio na maior parte das estradas e em todas as exportacoes.",
    ),
    (
        "P03",
        "D. Pecuaria",
        "Producao por animal e por ciclo",
        "Aegro mede 'lucro por arroba de cada ciclo'. E' a unidade economica real da pecuaria.",
    ),
    # ---- E. Estoque e logistica (5)
    (
        "L01",
        "E. Logistica",
        "Estoque de insumos com lote e validade",
        "A baixa automatica do insumo no ato da aplicacao e' o que fecha o custo por talhao.",
    ),
    (
        "L02",
        "E. Logistica",
        "Romaneio, pesagem e balanca",
        "Sofre pela balanca. E' a unica coluna em que balanca e ERP fazem par.",
    ),
    (
        "L03",
        "E. Logistica",
        "Compras e pedidos",
        "Cotacao, ordem de compra, recebimento. Aegro Avancado.",
    ),
    (
        "L04",
        "E. Logistica",
        "Beneficiamento e armazenagem",
        "Silox, secagem, beneficiamento. A upCampo declara; e' onde os ERPs de talhao param.",
    ),
    (
        "L05",
        "E. Logistica",
        "Contratos de safra e torrentes",
        "Safra garantida com desconto. O ciclo de caixa mais rentavel do agro — e ausente do Ampliagro.",
    ),
    # ---- G. Maquinas, IoT e IA (9)
    (
        "M01",
        "G. Maq/IA",
        "Telemetria de maquina",
        "Ler o que a maquina ja faz. A Aegro integra Deere, Stara e FieldView.",
    ),
    (
        "M02",
        "G. Maq/IA",
        "John Deere Operations Center",
        "Integracao nativa. A upCampo e' a outra que a declara.",
    ),
    (
        "M03",
        "G. Maq/IA",
        "Stara, Climate FieldView, Solinftec",
        "O ecosistema brasileiro de maquinario. A upCampo declara Solinftec.",
    ),
    (
        "M04",
        "G. Maq/IA",
        "ISOBUS (ISO 11783)",
        "E' o que separa 'recebo dados' de 'leio a maquina'.",
    ),
    (
        "M05",
        "G. Maq/IA",
        "OTA — actualizacao de firmware",
        "Declarado no manifesto Agro 5.0 §VII. Medido: nao existe.",
    ),
    (
        "M07",
        "G. Maq/IA",
        "IA que corre no dispositivo",
        "WebLLM no WebGPU. Nenhum dos concorrentes researched vende.",
    ),
    (
        "M08",
        "G. Maq/IA",
        "Assistente conversacional e MCP",
        "A upCampo publica a UPi (WhatsApp) e conector MCP para ChatGPT e Claude. E' o par mais proximo do Ampliagro.",
    ),
    (
        "M09",
        "G. Maq/IA",
        "API publica documentada",
        "Sem API o produto nao cresce. A upCampo publica a sua explicitamente.",
    ),
    # ---- H. Governanca e dados (6)
    (
        "G01",
        "H. Dados",
        "Proveniencia de dado em codigo",
        "Saber se um numero foi medido, declarado ou inventado. app/validators.py tem cinco estados.",
    ),
    (
        "G02",
        "H. Dados",
        "Auditoria de execucao de IA",
        "Cada accao da IA registada. app/models/ia.py tem treze campos.",
    ),
    (
        "G03",
        "H. Dados",
        "Isolamento multi-empresa por tabela",
        "Servidor desligado nao pode ler a fazenda. app/middleware.py fecha a porta.",
    ),
    (
        "G04",
        "H. Dados",
        "Multi-propriedade e multi-safra",
        "Varias fazendas e ciclos na mesma conta.",
    ),
    (
        "G05",
        "H. Dados",
        "Carbono, ESG e MRV",
        "Fluere, Carbonova e CO2Token vendem isto. O Ampliagro mediu zero.",
    ),
    (
        "X02",
        "H. Dados",
        "Conectores prontos",
        "Aegro liga Dominio, Fortes, Contmatic; a upCampo liga Sankhya, Aliare, ViaSoft.",
    ),
    (
        "X06",
        "H. Dados",
        "WhatsApp como interface de operacao",
        "A Aegrozap registabesastecimento, estoque e manutencao por texto, audio ou foto. A UPi da upCampo responde sobre custo, estoque, praga e frota. WhatsApp e' onde o produtor brasileiro ja esta — ignores e' perder o canal.",
    ),
    (
        "X07",
        "H. Dados",
        "Exportacao de dados em formato aberto",
        "PDF/Excel/CSV. O portao de saida e' o que impede o aprisionamento — e a unica defesa que o produtor tem quando o fornecedor sobe o preco.",
    ),
]

assert len(COLUNAS) == 50, f"devem ser 50 colunas, tenho {len(COLUNAS)}"

#: O que mede cada coluna no Ampliagro: (padrao, globs, excluir)
MEDIDA: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "F01": (r"linha_lcdpr|gerar_arquivo", PY, ("lcdpr.py",)),
    "F02": (r"sefaz|autorizacao_nfe|sign_nfe|emissao.{0,3}nfe", ALL, ()),
    "F03": (r"\bmdf\b|mdf_e|manifesto_eletronico", ALL, ()),
    "F04": (r"icp.?brasil|certificado.{0,3}a1|a1.{0,3}certificado", ALL, ()),
    "F05": (r"reforma.{0,3}tribut|\bIBS\b|\bCBS\b|taxa_industrial", ALL, ()),
    "F06": (r"\bncm\b", ALL, ()),
    "F07": (r"\bdre\b", ALL, ()),
    "F08": (r"presumido|regime.{0,3}real", ALL, ()),
    "F10": (r"class.{0,3}(ContaPagar|ContaReceber|Pagamento)", PY, ()),
    "F11": (r"fluxo.{0,3}caixa|FluxoCaixa", ALL, ()),
    "F12": (r"\bofx\b", ALL, ()),
    "F13": (r"custo_por_ha|apropria", ALL, ()),
    "F14": (r"orcado|previsto.{0,10}realizado|planejado.{0,10}realizado", ALL, ()),
    "F15": (r"benchmark|compara.{0,3}safras|preco_medio_insumo", ALL, ()),
    "F16": (r"credito.{0,3}rural|seguro.{0,3}agricola|apolice", ALL, ()),
    "F17": (r"projecao.{0,3}ir|simula.{0,3}imposto|irpf", ALL, ()),
    "F18": (r"folha.{0,3}pagamento|producao.{0,10}funcionario", ALL, ()),
    "O01": (r"NotaCampo|caderno.{0,3}campo|nota_campo", ALL, ()),
    "O02": (r"serviceWorker|indexedDB|offline", JS + TPL, ()),
    "O03": (r"geoloc|latitude|longitude", ALL, ()),
    "O04": (r"AtividadePlanejada|class.{0,3}Tarefa", PY, ()),
    "O05": (r"planejamento.{0,3}safra|PlanoSafra|calendario_agricola", ALL, ()),
    "O06": (r"poligono|geoespa|GeoJSON|talhao.{0,3}mapa", ALL, ()),
    "O07": (r"\bndvi\b|sentinel|s2gee", ALL, ()),
    "O08": (r"\bdrone\b|dji_|imageamento.?aereo", ALL, ()),
    "O09": (r"\bmip\b|manejo_integrado", ALL, ()),
    "P01": (r"brinco|tag_id|identificacao_individual", ALL, ()),
    "P02": (r"calendario_sanitar|vacinacao|Vacinacao", ALL, ()),
    "P03": (r"peso_vivo|gmd|arroba|producao.{0,3}animal", ALL, ()),
    "L01": (r"\blote\b|validade", ALL, ()),
    "L02": (r"romaneio|pesagem|balanca|\btara\b", ALL, ()),
    "L03": (r"ordem.{0,3}compra|PedidoCompra|Compras", ALL, ()),
    "L04": (r"beneficiamento|silox|secagem|armazenagem", ALL, ()),
    "L05": (r"contrato.{0,3}safra|aforamento|entrega.{0,3}futura|torrentes", ALL, ()),
    "M01": (r"telemetria|operations.?center|fieldview", ALL, ("top_globais.py",)),
    "M02": (r"operations.?center|john.?deere", ALL, ("top_globais.py",)),
    "M03": (r"solinftec|\bstara\b|field.?view", ALL, ("top_globais.py",)),
    "M04": (r"isobus|iso.?bus|iso.?11783", ALL, ()),
    "M05": (r"espota|esp_update|firmware/upload|ota_upload", ALL, ()),
    "M07": (r"WebLLM|createEngine|webgpu|SmolLM2", JS, ()),
    "M08": (r"amplia_mcp|IAExecucao", PY, ()),
    "M09": (r"schema_view|@api_view|def health", PY, ()),
    "G01": (r"ESTADOS_FONTE|class Estado|proveniencia", PY, ()),
    "G02": (r"class IAExecucao", PY, ()),
    "G03": (r"ServidorRevogadoMiddleware|exigir_servidor_ativo", PY, ()),
    "G04": (r"class Propriedade|class Safra", PY, ()),
    "G05": (
        r"ghg_protocol|\bmrv\b|credito.{0,3}de.{0,3}carbono|blockchain|\bcbam\b",
        ALL,
        (),
    ),
    "X02": (r"integracao|connector|conector", PY, ()),
    "X06": (r"whatsapp|telegram|twilio", ALL, ()),
    "X07": (r"csv|\.pdf|exportar", PYJS, ()),
}

assert set(MEDIDA) == {
    c[0] for c in COLUNAS
}, f"MEDIDA e COLUNAS estao desalinhadas: {set(MEDIDA) ^ {c[0] for c in COLUNAS}}"


def medir() -> dict[str, tuple[str, str]]:
    r: dict[str, tuple[str, str]] = {}
    for cid, *_ in COLUNAS:
        padrao, globs, excluir = MEDIDA[cid]
        r[cid] = procurar(padrao, *globs, excluir=excluir)
    return r


if __name__ == "__main__":
    m = medir()
    print("=" * 80)
    print(f"AMPLIAGRO MEDIDO — {len(COLUNAS)} colunas, {len(m)} medidas")
    print("=" * 80)
    grupo_atual = ""
    for cid, grupo, nome, _ in COLUNAS:
        if grupo != grupo_atual:
            grupo_atual = grupo
            print(f"\n{grupo}")
        estado, ev = m[cid]
        marca = "[IMPL ]" if estado == "IMPL" else "[FALTA]"
        print(f"  {marca} {cid} {nome[:46]:48} {ev}")

    impl = sum(1 for v in m.values() if v[0] == "IMPL")
    print()
    print(
        f"  IMPL: {impl}/{len(COLUNAS)}    FALTA: {len(COLUNAS) - impl}/{len(COLUNAS)}"
    )
