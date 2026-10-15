"""O comparativo 100x50 como intent da IA.

POR QUE ISTO E' UM INTENT E' NAO UM RELATORIO
=============================================
MEDIDO 2026-10-05 (agente 7). O `comparativo-100x50.xlsx` tem 5.000 celulas
comprovadas por 4.917 marcadores `?`. Nao cabe num contexto, e nem deve: a IA
que recebe 50 linhas para decidir o que construir vai ler a primeira e
inventar o resto.

Por isso o intent devolve **três coisas e mais nenhuma**:

    1. a contagem — `{"C": 11, "E": 24, "N": 22, ...}`
    2. os **divergentes** face a planilha, com a razao
    3. o **aviso** que impede a leitura errada

E tem uma regra de gold que vem do resto do codebase: se a pergunta nao pede
detalhe, devolve a contagem e os 10 divergentes mais graves. Quem quiser o
resto pede explicitamente.

O NOME, E POR QUE NAO E' `comparativo`
=======================================
MEDIDO 2026-10-05. Este intent nasceu com o nome `comparativo` e colidiu com
`app/amplia_mcp/comparativo.py`, que outro agente construiu em paralelo e que
expoe a tool `amplia_comparativo`. Duas tools com o mesmo nome: o cliente MCP
recebia a descricao errada, e `test_tools_em_formato_openai` acusou
`86 != 87` — uma tool duplicada.

Os dois fazem trabalho legitimo e diferente, e por isso **nenhum foi
apagado**:

    `amplia_comparativo`           que capacidades existem no codigo, e onde
    `amplia_comparativo_revisao`   onde e' que a planilha se passa

O sufixo `_revisao` nao e' cosmético: diz que esta ferramenta **audita uma
afirmacao**, enquanto a outra **produz** uma medicao. Uma audita a palavra do
outro — se a planilha passa, e' aqui que se descobre.

O QUE A IA **NAO** PODE FAZER COM ISTO
======================================
- Nao tratar `E` como "nao existe". `E` significa "a prova nao sustenta o
  `C`", nao "falta". Uma capacidade pode existir e estar mal citada.
- Nao tratar o resultado como ranking. So' a coluna do Ampliagro e' medida.
- Nao ler `indeterminado` como `N`. "Nao sei" nao e' "nao ha", e o codigo
  trata os dois em sitios diferentes de proposito.
"""

from __future__ import annotations


def _params(params: dict | None) -> dict:
    return params or {}


def h_comparativo(user, params, ctx):
    """Handler do intent `comparativo`."""
    from app.services.comparativo_ambiental import remedir, resumo_para_a_ia

    p = _params(params)
    quer_detalhe = bool(p.get("detalhe")) or p.get("formato") == "markdown"
    limite = int(p.get("limite") or (50 if quer_detalhe else 10))

    rel = remedir()

    if rel.fonte_ilegivel:
        return {
            "ok": False,
            "erro": "planilha_ilegivel",
            "detalhe": rel.fonte_ilegivel,
            "resolucao": (
                "A planilha nao pode ser lida. Sem ela nao ha veredicto — e um "
                "comparativo que nao se abre escreve-se com a memoria, que e' "
                "de onde saem os 'C' falsos."
            ),
        }

    d = rel.para_dict()
    d["ok"] = True
    # MEDIDO 2026-10-05. Esta chave chamava-se `resumo_texto`, e nenhuma das
    # outras 116 occurrences de `"resposta"` nos handlers e' uma repeticao —
    # `resposta` e' o nome que o protocolo le. `SmokeTodasIntentsTest` faz
    # `texto = (out.get("resposta") or "") + (out.get("erro") or "")` e
    # falhava com "comparativo_revisao sem resposta nem erro": o handler
    # respondia, mas com uma chave que ninguem lia.
    #
    # Um dicionario com a resposta dentro e' um dicionario mudo. E o pior
    # sitio: o health check da suite passou a dizer que a intent estava
    # partida, quando o que estava partido era o nome da chave.
    d["resposta"] = resumo_para_a_ia()
    d["suspeitas"] = [
        {
            "id": v.dimensao.id,
            "dimensao": v.dimensao.nome,
            "planilha": v.dimensao.veredicto,
            "porque": v.como_provar,
        }
        for v in rel.suspeitas
    ]

    if not quer_detalhe:
        d["divergentes"] = d["divergentes"][:limite]
        d["nota_truncamento"] = (
            f"{len(rel.divergentes)} divergentes no total; a mostrar "
            f"{min(limite, len(rel.divergentes))}. Pede `detalhe: true` para "
            f"todas."
        )

    # ── o carimbo que impede a leitura errada ────────────────────────────
    #
    # O `E` e' onde este resultado e' perigoso: 24 dimensoes. Sem esta frase,
    # a IA le "24 E" e conclui "faltam 24 coisas", e sai a construir as 24 —
    # metade das quais ja existe.
    d["como_ler"] = (
        "`E` NAO e' falta: e' 'a evidencia citada nao sustenta C' — a "
        "capacidade pode existir e estar mal citada, ou existir e nao ser "
        "provada por essa linha. `N` e' ausencia. `indeterminado` e' 'nao "
        "consigo decidir' e **nao** e' `N`. Remedir diz que a prova e' "
        "executavel; nao diz que a dimensao esteja coberta na integra."
    )

    return d


INTENT_COMPARATIVO_REVISAO = {
    "comparativo_revisao": {
        "descricao": (
            "INSTRUCAO IA: use para perguntar 'em que dimensoes competitive "
            "o Ampliagro esta atras', 'o que falta face aos concorrentes', "
            "'revê o comparativo'. Le a coluna do Ampliagro da planilha "
            "100x50 e **remede-a no codigo**, devolvendo os divergentes com "
            "a razao. Use ANTES de planear trabalho: um comparativo com 'C' "
            "onde nao ha capacidade faz o proximo agente construir a coisa "
            "errada com a certeza de que ja existe. NAO use para comparar "
            "com concorrentes — so' a coluna do Ampliagro e' medida; as 100 "
            "aplicacoes estao marcadas '?' e nao sao um ranking. "
            "Parametros: detalhe (bool, todas as divergentes, padrao 10), "
            "formato ('markdown' devolve tabela), limite (int)."
        ),
        "exemplos": [
            "em que dimensoes competitive estamos atras",
            "o que falta face aos concorrentes",
            "revê o comparativo 100x50",
            "o que da para afirmar que temos",
            "qual é a nossa lacuna real",
        ],
        # O vocabulario de flags e' `<dominio>.read` — `campo.read`, `fin.read`,
        # `iot.read`, `pecuaria.read` (medido no registo). A flag e' lida por
        # `sandbox.somente_leitura`, que e' **fail-closed**: sem flags, ou com
        # flag de escrita, o intent e' tratado como escrita. `comparativo.read`
        # cumpre a regra — mas nao ha dominio `comparativo` no resto do
        # registo, e um nome de flag invented nao ganha o direito a existir
        # so' porque o teste passa.
        #
        # `competencia.read` diz o que o intent faz: mede a posicao do
        # Ampliagro contra um referencial. E' leitura pura — abre a planilha,
        # le o codigo, devolve texto. Nao escreve nada.
        "flags": ["competencia.read"],
        "handler": h_comparativo,
        # `params_schema` declarado tem precedencia sobre a deducao a partir
        # dos exemplos (`amplia_mcp._schema_de_params`). Sem ele, o
        # `inputSchema` da tool saia com `properties: {}` — e um schema vazio
        # faz o modelo passar tudo como string, ou nao passar nada. Os
        # exemplos acima sao perguntas em portugues, sem parametros, de onde
        # nao se deduce um unico campo.
        "params_schema": {
            "detalhe": {
                "type": "boolean",
                "description": (
                    "true devolve TODAS as divergentes. false (padrao) devolve "
                    "as 10 mais graves — o suficiente para decidir o proximo "
                    "passo, e pequeno o suficiente para caber no contexto."
                ),
            },
            "formato": {
                "type": "string",
                "enum": ["json", "markdown"],
                "description": (
                    "'markdown' devolve uma tabela pronta para colar na "
                    "planilha ou num PR. 'json' (padrao) e' estruturado."
                ),
            },
            "limite": {
                "type": "integer",
                "description": (
                    "Numero maximo de divergentes a devolver. Default 10, ou "
                    "todos quando `detalhe: true`."
                ),
            },
        },
    }
}


def registar(registrador) -> None:
    """Regista o intent. `registrador` recebe o dicionario de intents."""
    registrador.update(INTENT_COMPARATIVO_REVISAO)
