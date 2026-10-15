"""Os prompts do AmplIA — a Orientação a Pedir, não a Ler de suppressor.

O que esta superfície resolve
-----------------------------
Um servidor MCP expõe três coisas: `tools` (o que se pode chamar),
`resources` (o que se pode ler) e `prompts` (o que se pode PEDIR). O
AmplIA tinha as duas primeiras e não tinha a terceira.

A consequência é mais concreta do que "falta uma feature". Um agente que
chega a um servidor com 79 tools e nenhum prompt não sabe duas coisas que
o código já sabe:

  1. que as tools de escrita pedem confirmação, e que a resposta `needs_confirm`
     não é um erro — é uma pergunta que o produtor tem de responder;
  2. que quando uma tool não existe, a resposta traz `sugestoes` com os
     nomes verdadeiros, e o certo é chamar um desses nomes em vez de tentar
     de novo o mesmo.

Descobrir as duas por tentativa-e-erro custa chamadas ao servidor e, no caso
do ponto 2, produz `IAExecucao` com `ok=False` de tudo o que se inventou.
Uma linha de orientação poupa as duas coisas.

POR QUE SÃO DERIVADOS
---------------------
O texto dos prompts sai do catálogo a cada chamada, pela mesma razão do
`vocabulario`: uma lista escrita à mão divergiu do código e custou um turno
inteiro de tool calls inúteis (FILA #27). Um prompt que lista nomes de
ferramentas à mão volta a ser um mapa que ninguém actualiza. As ferramentas
citadas aqui são as que o catálogo diz que pedem confirmação — não as que
alguém lembrou de escrever.
"""

from __future__ import annotations

from typing import Any


def _escritas() -> list[str]:
    """Os nomes das tools que alteram dados, do catálogo."""
    from app.ia.sandbox import INTENTS, somente_leitura

    return sorted(n for n, s in INTENTS.items() if not somente_leitura(s))


def _campos_pedidos(limite: int = 12) -> str:
    """As tools que passam primeiro por uma pergunta antes de agir.

    Um `required_field` transforma a tool numa conversa de duas voltas. Um
    agente que não o saiba chama uma vez, recebe "Qual o nome?", e tem de
    perceber que a segunda chamada tem de ser a mesma tool com o campo
    preenchido. Dizer isso à partida é a diferença entre uma chamada e cinco.
    """
    from app.ia.sandbox import INTENTS

    linhas = []
    for nome in sorted(INTENTS):
        campos = list((INTENTS[nome] or {}).get("required_fields") or [])
        if campos:
            linhas.append(f"  {nome}: {', '.join(campos)}")
    if not linhas:
        return "Nenhuma tool pede campos antes de agir."
    corpo = "\n".join(linhas[:limite])
    resto = len(linhas) - limite
    sufixo = f"\n  ... e mais {resto}." if resto > 0 else ""
    return corpo + sufixo


def prompt_ferramentas() -> str:
    """Como se escreve uma chamada, e que nomes existem.

    Este é o prompt que devolve a resposta à FILA #27, agora do lado do
    cliente MCP: os nomes verdadeiros, todos, e a instrução de que um nome
    fora da lista não existe.
    """
    from app.amplia_mcp import vocabulario

    v = vocabulario()
    return (
        "Para chamar uma ferramenta da AmplIA, escreve no teu formato de tool "
        "call o nome EXATO, com o prefixo `amplia_`.\n\n"
        f"{v['texto']}\n\n"
        "Se pedires uma tool e a resposta vier com `codigo: "
        "tool_fora_do_catalogo` ou `tool_desconhecida`, o campo `sugestoes` "
        "traz os nomes que EXISTEM. Chama um deles. Não repitas o nome "
        "inventado: ele não vai passar a existir à segunda tentativa."
    )


def prompt_seguranca() -> str:
    """As regras que decidem se uma chamada é executada ou perguntada.

    Não é um aviso genérico. Cada regra abaixo corresponde a uma coisa que
    o `sandbox.executar` faz de facto, e saber qual delas está a correr
    evita que o agente trate uma resposta como erro.
    """
    escritas = _escritas()
    return (
        "Regras do AmplIA para quem chama ferramentas.\n\n"
        "1. ESCRITA PEDE CONFIRMAÇÃO. Se a resposta trouxer "
        "`needs_confirm: true`, isso não é erro — é o servidor a perguntar "
        "ao produtor. Mostra-lhe o que vais fazer e espera o assentimento. "
        "Não repitas a chamada a hoping que passa.\n\n"
        "2. A CONFIRMAÇÃO VAI NO CAMPO `confirm`, não na conversa. Passa "
        '`{"confirm": true}` nos argumentos da MESMA tool. Numa sessão com '
        "conversa, o servidor também aceita `entrada` como campo de topo: é "
        "a frase do produtor, e é o que desatasca um pedido de confirmação.\n\n"
        "3. TOOLS DE LEITURA NÃO PEDEM NADA. Se uma tool de leitura responder "
        "com `needs_confirm`, ela não declara flag de capacidade — trata-a como "
        "escrita e pede ao produtor.\n\n"
        "4. UM NOME INVENTADO NÃO FALHA EM SILÊNCIO — VOLTA SUGESTÕES. A "
        "resposta tem `codigo: tool_fora_do_catalogo` (ou `tool_desconhecida`) "
        "e o campo `sugestoes` com os nomes que EXISTEM. Chama um deles. Não "
        "repitas o nome inventado: ele não passa a existir à segunda "
        "tentativa.\n\n"
        "5. NÃO TENTES A MESMA ESCRITA EM LOOPS. Cada chamada deixa uma linha "
        "em `IAExecucao`. Duas tentativas de ligar a irrigação são duas "
        "linhas, e quem lê a auditoria depois tem de adivinhar qual foi a "
        "intencional.\n\n"
        "Tools que alteram dados neste momento:\n" + ", ".join(escritas)
    )


def prompt_campos() -> str:
    """Que tools perguntam antes de agir, e o quê."""
    return (
        "Estas ferramentas do AmplIA pedem campos ao produtor antes de "
        "agir. Uma chamada só não chega: a primeira devolve `state: "
        "COLETANDO_DADOS` com uma pergunta, e a segunda tem de ser a mesma "
        "tool com o campo preenchido.\n\n"
        f"{_campos_pedidos()}\n\n"
        "Não inventes o valor. Se o produtor não disse, a resposta certa é a "
        "pergunta — e a pergunta é o que o servidor te devolveu."
    )


#: Os prompts publicados. A chave é o nome que o cliente pede; a função é
#: chamada a cada `get_prompt`, para que um intent novo apareça sem ninguém
#: editar este ficheiro.
PROMPTS: dict[str, dict[str, Any]] = {
    "amplia_ferramentas": {
        "description": (
            "Os nomes verdadeiros das 76 ferramentas, como uma linha de cada "
            "vez, e o que fazer quando o nome que inventaste não existe."
        ),
        "montar": prompt_ferramentas,
    },
    "amplia_seguranca": {
        "description": (
            "As regras que decidem se uma chamada é executada ou perguntada ao "
            "produtor. Ler antes da primeira escrita."
        ),
        "montar": prompt_seguranca,
    },
    "amplia_campos": {
        "description": (
            "Que ferramentas param para perguntar um campo, e qual. Evita a "
            "conversa de cinco voltas em vez de duas."
        ),
        "montar": prompt_campos,
    },
}


def catalogo_prompts() -> list[dict[str, Any]]:
    """O que o MCP expõe em `list_prompts`. Só o metadado, não o texto."""
    return [
        {"name": nome, "description": spec["description"]}
        for nome, spec in PROMPTS.items()
    ]


def montar(nome: str) -> str | None:
    """Devolve o texto de um prompt, ou `None` se não existir.

    `None` e não uma string vazia: um prompt desconhecido tem de ser um
    `None` para o servidor dizer "não existe", e uma string vazia seria lida
    pelo cliente como "existe mas não diz nada" — que é a falha que
    `read_resource` tinha e que foi corrigida à parte.
    """
    spec = PROMPTS.get(nome)
    return spec["montar"]() if spec else None
