r"""
contrato.py — o que um cliente MCP realmente vê.

ESTE MÓDULO É A RESPOSTA A UM PAR DE PERGUNTAS QUE O CATÁLOGO NÃO RESPONDE
------------------------------------------------------------------------

O `app/amplia_mcp/__init__.py` publica as tools. Publicar não é o mesmo que
**declarar**: o `inputSchema` que sai de lá é um subproduto deduzido dos
exemplos de prosa que cada intent traz, e essa dedução tem duas lacunas que
foram medidas, não supostas.

**Lacuna 1 — os campos obrigatórios não são publicados.**

`required_fields` é a verdade declarada: é a lista que o `sandbox` usa para
saber o que falta. Nove intents têm `required_fields` e **nenhuma** das nove
publica `required` no schema. O modelo não sabe o que é obrigatório sem
tentar, e cada tentativa é uma ida ao estado `COLETANDO_DADOS` — que devolve
"Qual é o nome?" e espera a próxima chamada. Num agente externo MCP isso é um
beço sem saída, porque não existe canal para responder.

**Lacuna 2 — a confirmação de uma escrita é literalmente ilegível.**

O schema fecha com `additionalProperties: false`, e `confirm` **não está
declarado** em 19 das 24 tools de escrita (as outras 5 declaram, porque os
intents dinâmicos escreveram o `params_schema` à mão). Uma propriedade que o
schema proíbe e que o sistema exige é um beço: o `sandbox` só executa uma
escrita com `params["confirm"]`, e a única forma de o entregar é violar o
contrato que o próprio servidor publicou.

As duas medem-se assim (L3, `scratch/test_lacuna_schema.py`):

    (a) tools com campos obrigatórios e sem 'required'   9
    (b) tools de escrita: 24 · com 'confirm' no schema: 5
    (c) tools de escrita com additionalProperties=False: 24

POR QUE UM MÓDULO NOVO E NÃO UMA LINHA EM `_schema_de_params`
-----------------------------------------------------------

Porque `_schema_de_params` está a ser editado por outra sessão neste momento
(regra R1 do `docs/COORDENACAO_IA.md`), e porque a RESPOSTA que um cliente
recebe não é a mesma coisa que a INTENÇÃO que um autor de intent escreve.

São duas camadas com perguntas diferentes, e a confusão entre as duas é o que
produz catálogos que mentem:

- `__init__.py` responde **"o que esta intent faz e que campos aceita"** — e
  essa resposta pertence a quem escreve a intent.
- este módulo responde **"como é que um agente fala com isto"** — e essa
  resposta pertence ao protocolo, que muda por decisão de arquitectura, não
  por feature nova.

A divisão paga-se com um teste de fonte (`tests.py::ContratoTest`), que falha
se as duas camadas divergirem: se alguém acrescentar um `required` em
`_schema_de_params` e esquecer aqui, o teste vermelho diz exactamente onde. Sem
o teste, teriamos duas listas — que é a mesma divergência silenciosa que a
doutrina D7 do repositório já condemnou noutro sítio.

O QUE ESTE MÓDULO NÃO FAZ
--------------------------

- Não inventa tool. Só enriquece as que já existem.
- Não executa nada, e não tem permissão para: o caminho de execução continua a
  ser `executar_para` → `sandbox.executar`.
- Não altera o `inputSchema` de origem. Devolve cópias — um cliente não pode
  estragar o catálogo de outro.
"""

from __future__ import annotations

import copy
from typing import Any

#: O campo que confirma uma escrita. É o nome que o `sandbox` lê
#: (`params.get("confirm")`) e é o nome que o produtor diz: "sim", "confirmo",
#: "pode fazer". Um cliente MCP manda `true`.
PARAM_CONFIRMACAO = "confirm"

#: Tipo declarado para um campo que o código exige mas que a dedução a partir
#: dos exemplos não encontrou. Inteiro OU string, deliberadamente: alguns
#: handlers aceitam "3" e outros exigem 3, e estreitar aqui faria o modelo
#: errar a chamada por causa de um tipo que o handler sabe converter.
_TIPO_PERMISSIVO: dict[str, Any] = {"type": ["string", "number", "integer"]}


def _spec_de(intent: str) -> dict[str, Any]:
    """A spec do intent, de onde vier que venha.

    Duas fontes, nesta ordem, e a segunda é o que impede o servidor de morrer:

    1. `app.ia.registro.REGISTO` — o registo que se descobre a si próprio.
    2. `app.ia.sandbox.INTENTS` — o agregador, que existe em qualquer desenho.

    Porquê a segunda. Este import directo matou o servidor MCP inteiro uma
    vez, e não por um erro de sintaxe: `app/ia/registro.py` foi apagado do
    disco durante um bloco de outra sessão, e `rodar()` morreu a construir o
    catálogo — `ModuleNotFoundError: No module named 'app.ia.registro'`, na
    linha 318, antes de qualquer `list_tools`. Um servidor MCP que não
    arranca não é um servidor degradado: não existe, e o cliente só diz
    "ligação falhou", que não aponta para nada.

    A queda é de propósito e é BARATA: `_spec_de` é chamado por tool, para
    Lee um dicionário. Devolver `{}` quando a fonte preferida falta apenas
    faz o schema ficar mais pobre — o que o `enriquecer` já sabe completar
    sozinho. Devolver uma excepção, ao contrário, tira o servidor inteiro do
    ar por causa de um dicionário.

    O registo foi restaurado. Esta rede fica de propósito: o ficheiro pode
    voltar a ser reescrito ou removido, e um `except ImportError` de duas
    linhas é mais barato que um dia de servidor em baixo.
    """
    try:
        from app.ia.registro import REGISTO
    except ImportError:
        from app.ia.sandbox import INTENTS as REGISTO

    return REGISTO.get(intent) or {}


def _garantir_propriedade(schema: dict[str, Any], campo: str) -> None:
    """Garante que `campo` é aceitável pelo schema.

    Declarar `required: ["area"]` num schema que proíbe `area` produz um
    contrato impossível de satisfazer: o modelo é obrigado a enviar um campo
    que o schema diz ser inválido. Este é o tipo de erro que não dá 500 —
    dá confusão silenciosa, e a IA "resolve" inventando.
    """
    props = schema.setdefault("properties", {})
    if campo not in props:
        props[campo] = dict(_TIPO_PERMISSIVO)


def enriquecer(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Devolve as tools com o contrato completo. Não muta a entrada.

    Faz três coisas, nesta ordem, e a ordem importa:

    1. **`required`** — de `required_fields`, que é a verdade do `sandbox`.
       Só entra o que o schema consegue aceitar; o resto é acrescentado como
       propriedade permissiva em (2), porque um campo obrigatório que não pode
       ser enviado é pior do que um campo que não existe.

    2. **propriedades em falta** — todo campo obrigatório passa a existir no
       schema. Um intent que pede `brinco` e cujos exemplos só mostram
       `{...}` fica com `brinco` declarado.

    3. **`confirm`** — em toda a tool que não é só-leitura. **Não** entra em
       `required`: a confirmação é uma SEGUNDA chamada, por desenho. Se
       entrasse, o modelo teria de confirmar antes de ter feito o que está a
       confirmar — o pedido de confirmação do `sandbox` seria impossível de
       satisfazer e a escrita nunca sairia.

    A `x-read-only` é o critério, e não a flag solta, porque é o mesmo
    critério que `sandbox.somente_leitura` aplica: um intent sem flag nenhuma é
    tratado como escrita, em fail-closed.
    """
    saida: list[dict[str, Any]] = []

    for original in tools:
        t = copy.deepcopy(original)
        schema = t.setdefault("inputSchema", {})
        schema.setdefault("type", "object")
        props = schema.setdefault("properties", {})

        intent = t.get("x-intent")
        spec = _spec_de(intent) if intent else {}
        exige = [c for c in (spec.get("required_fields") or []) if c]

        for campo in exige:
            _garantir_propriedade(schema, campo)
        if exige:
            schema["required"] = list(dict.fromkeys(exige))

        if not t.get("x-read-only"):
            props.setdefault(
                PARAM_CONFIRMACAO,
                {
                    "type": "boolean",
                    "description": (
                        "true confirma a execucao. A primeira chamada devolve "
                        "needs_confirm e NAO executa: e a segunda chamada, com "
                        "este campo a true, que executa. Nao o ponhas na "
                        "primeira — seria confirmar antes de ter feito."
                    ),
                },
            )

        saida.append(t)

    return saida


def para_mcp(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """O formato MCP: `name` / `description` / `inputSchema`, sem as chaves `x-`."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        }
        for t in enriquecer(tools)
    ]


def para_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """O formato OpenAI function-calling, que é o que o WebLLM consome.

    Traduzir aqui, e não no JS da aba: uma tradução só, testada, e o contrato
    MCP fica intacto para o outro lado. Esta função substitui a comprehension
    que estava dentro de `views.tools` — que, além de estar no sítio errado,
    chamava `catalogo_tools()` **duas vezes** e refazia todos os schemas
    deduzidos dos exemplos numa passagem que não precisava de duas.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        }
        for t in enriquecer(tools)
    ]


# --------------------------------------------------------------------------
# O guia — o texto que diz como se fala com isto
# --------------------------------------------------------------------------
# Existe porque um agente que não sabe disto inventa. E um agente que inventa
# não falha de forma visível: chama uma tool que existe com argumentos que
# não, recebe 200 com `ok: false`, e concludes que a fazenda está vazia.
#
# Cada linha aqui já custou um defeito real. Nenhuma é opinião de estilo.

GUIA = """\
COMO USAR ESTA CAMADA

1. UMA tool por chamada. `POST /api/amplia/exec/` aceita exatamente uma.
   Nao existe lote, por desenho: um pedido do modelo que executa varias
   acoes sem intervencao e' o que o pedido de confirmacao existe para
   impedir.

2. O NOME tem de existir no catalogo. O servidor recusa pelo catalogo, nao
   pelo formato do nome — `amplia_algo_que_nao_existe` volta
   `tool_fora_do_catalogo`, com a lista do que existe. Inventar nome de tool
   e' o modo normal de um modelo pequeno errar.

3. ERRO DE TOOL E' RESULTADO, NAO ERRO DE HTTP. A resposta e' 200 com
   `"ok": false`. Um 4xx faria o cliente tentar de novo — e executar a acao
   duas vezes.

4. ESCREVA E' DOIS PASSOS. A primeira chamada devolve `needs_confirm: true` e
   NAO executa. A segunda repete o mesmo nome e os mesmos argumentos com
   `"confirm": true`. Sem o segundo passo, nada acontece — por desenho.

5. FALTA CAMPO? A resposta traz `state: "COLETANDO_DADOS"` e a pergunta.
   Responda reenviando a tool com o campo que faltava preenchido, e com
   `"entrada"` igual ao que o produtor disse. A pergunta ja vem escrita na
   resposta; nao a repita ao produtor.

6. `entrada` E' A FRASE DO PRODUTOR. Va em `meta` e vai para a trilha de
   auditoria e para a maquina de estados. E' o que permite dizer "sim" para
   confirmar, e o que faz "cancelar" cancelar.

7. NINGUM DADO INVENTADO. Se a resposta trouxer `fonte_dado: sem_dado`,
   isso NAO e zero: e' a ausencia de medicao. Dizer "zero" afirma que a
   despesa foi zero, e a verdade e' que nunca foi registada nenhuma.

8. PARA SABER O QUE EXISTE, PERGUNTE. `amplia_capacidades` responde, e
   responde a partir do codigo — nao e' uma lista escrita a mao que diverge
   no primeiro dia em que alguem mexe numa feature.
"""


def resumo_contrato(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """A aritmetica do contrato. Para o `/diagnostico/` e para os testes.

    Devolve a CONTA, nao uma avaliacao: quantas tools, quantas de escrita,
    quantas com confirmacao declarada, quantas com obrigatorios publicados.
    Um numero que se move quando o codigo se mexe e' a unica coisa que
    sobrevive a uma conversa; um elogio ao design nao sobrevive a nada.
    """
    Completo = enriquecer(tools)
    escrita = [t for t in Completo if not t.get("x-read-only")]
    com_confirm = [
        t
        for t in escrita
        if PARAM_CONFIRMACAO in t["inputSchema"].get("properties", {})
    ]
    com_obrigatorios = [t for t in Completo if t["inputSchema"].get("required")]
    fecha = [
        t for t in Completo if t["inputSchema"].get("additionalProperties") is False
    ]
    return {
        "tools": len(Completo),
        "escrita": len(escrita),
        "leitura": len(Completo) - len(escrita),
        "escrita_com_confirm_declarado": len(com_confirm),
        "escrita_sem_confirm_declarado": [
            t["name"] for t in escrita if t not in com_confirm
        ],
        "tools_com_obrigatorios_publicados": len(com_obrigatorios),
        "tools_com_schema_fechado": len(fecha),
    }
