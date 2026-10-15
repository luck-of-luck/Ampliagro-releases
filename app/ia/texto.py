"""texto.py — o texto que o produtor lê, separado do texto que o modelo lê.

O PROBLEMA, E POR QUE PRECISA DE UM MÓDULO
==========================================
Cada intent tem UMA descrição, e essa descrição é escrita para o MODELO:
    "INSTRUÇÃO IA: use para 'gera pedido de compra'. Cria como RASCUNHO e
     confirma."

É a forma certa de escrever uma instrução de uso. E é exactamente a forma
errada de fazer uma pergunta a uma pessoa.

`app/ia/sandbox.py` ecoava essa descrição no pedido de confirmação, e o
produtor lia, literalmente:
    Você confirma a execução de 'INSTRUÇÃO IA: use para 'gera pedido de
    compra / faz pedido de diesel/adubo'. Cria como RASCUNHO e confirma.'?
    (Diga 'sim' ou 'não')

A única barreira antes de apagar uma safra estava embebida em texto de
engenharia. E o pior não é o texto: é que **ninguémodyleu e ninguém
decidiu**. A descrição certainava para o modelo; o sandbox reutilizou-a
para a pessoa; e a escolha passou despercebida porque nenhuma das duas
metades estava errada sozinha.

DUAS CULPAS, UMA SÓ
-------------------
Não é um bug do `sandbox` (que lia o que o spec lhe dava) nem dos autores
dos intents (que escreveram a instrução certo). É a COLA: um texto escrito
para um destinatário a ser mostrado a outro. Por isso a correcção não é
"limpar a descrição" — a descrição está certa para o modelo e tem de
continuar. A correcção é ter DOIS textos, e este módulo é o que os separa.

O QUE ESTE MÓDULO FAZ
---------------------
- `RE_INSTRUCAO` — o prefixo que os autores escrevem para o modelo.
- `sem_instrucao()` — tira o prefixo.
- `descricao_humana()` — a descrição sem o prefixo, primeira frase.
- `prompt_de_confirmacao()` — o texto que vai para o produtor. Prefere o
  campo `prompt_confirmacao` que o autor escreve; cai na descrição limpa
  quando o autor não escreveu um.

POR QUE UM MÓDULO E NÃO UM HELPER NO SANDBOX
-------------------------------------------
Porque `app/amplia_mcp/capacidades.py` precisa do MESMO regex, e ter o mesmo
padrão em dois sítios é ter duas fontes: corrige-se um e o outro fica errado.
O MCP já tinha uma cópia (com um bug: `startswith` em vez de regex, que
deixava passar o intent `feedback`). Este módulo é a cópia única, e
`capacidades.py` passou a importar daqui.

O QUE NÃO FAZ
--------------
Não reescreve descrições e não inventa texto. Se o autor não escreveu
`prompt_confirmacao`, o que o produtor vê é a descrição DELE, limpa do
prefixo — nunca uma frase escrita por este módulo. Um prompt de confirmação
inventado é pior que um feio: pode prometer o que o código não faz.
"""

from __future__ import annotations

import re
from typing import Any

#: O prefixo de "INSTRUÇÃO IA:" que os autores escrevem para o MODELO.
#:
#: REGEX e não `startswith`, e há um motivo medido: a descrição do intent
#: `feedback` começa com `"INSTRUÇÃO IA (ML):"` — parênteses ANTES dos dois
#: pontos. `.startswith("INSTRUÇÃO IA:")` não casa, e o texto interno ia
#: parar ao `o_que_faz` que o modelo lê. Foi o único de 80 a vazar, e
#: continuaria a vazar com `startswith` corrigido à pressa.
#:
#: `\b[^:]*:` e não `split(":", 1)`: com "INSTRUÇÃO IA (ML):" o `split`
#: cortava no primeiro dois-pontes, que não é o fim do prefixo.
RE_INSTRUCAO = re.compile(r"^INSTRU[CÇ][AÃ]O\s+IA\b[^:]*:\s*", re.I)

#: Frases a cortar quando só se quer a primeira. A descrição do produtor é
#: uma frase; as instruções de uso que se seguem são para o modelo.
_FRASE = re.compile(r"(?<=[.!?])\s+")


def sem_instrucao(texto: str | None) -> str:
    """`texto` sem o prefixo de instrução interna, e sem espaços a mais."""
    t = str(texto or "").strip()
    m = RE_INSTRUCAO.match(t)
    if m:
        t = t[m.end() :].strip()
    return t


def descricao_humana(spec: dict[str, Any], *, limite: int = 160) -> str:
    """A descrição de um spec, sem instrução interna e em uma frase.

    Quando não há descrição nenhuma, devolve o que o próprio spec diz — e
    não um texto inventado aqui. Um prompt de confirmação inventado é pior
    que um feio: pode prometer o que o código não faz.
    """
    d = sem_instrucao((spec or {}).get("descricao"))
    # Um bloco depois de uma linha em branco é convenção de uso interno.
    d = d.split("\n\n")[0].strip()
    if d:
        d = _FRASE.split(d)[0].strip()
    return d[:limite]


def prompt_de_confirmacao(
    spec: dict[str, Any], *, params: dict[str, Any] | None = None, limite: int = 200
) -> str:
    """O que o produtor vê quando lhe pedemos "confirma?".

    Ordem de escolha:
      1. `prompt_confirmacao` — escrito pelo autor para a pessoa. É o
         preferido, porque só ele conhece o objecto concreto ("Apagar a
         safra soja 2026/27? Ela e as tarefas dela somem.").
      2. a descrição limpa — o que o autor escreveu, sem a parte que é para
         o modelo.

    Um spec pode fornecer `resumo_confirmacao(params)` para mostrar o alvo e
    os campos concretos. As descrições estáticas continuam sem interpolação.
    """
    resumo = (spec or {}).get("resumo_confirmacao")
    if callable(resumo):
        return str(resumo(params or {}))[:800]
    p = str((spec or {}).get("prompt_confirmacao") or "").strip()
    if p:
        return p[:limite]
    return descricao_humana(spec, limite=limite)
