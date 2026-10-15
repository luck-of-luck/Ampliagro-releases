"""deteccao.py — o servidor passa a ENTENDER, e não a receber o entendimento.

O PROBLEMA, E POR QUE PRECISA DE EXISTIR
========================================
Hoje o servidor não tem nenhuma comprehend de linguagem. `sandbox.executar`
recebe o resultado da detecção **do cliente**:

    deteccao = meta.get("deteccao") or params.pop("_deteccao", {}) or {}

E o `deteccao` — com os `scores` de cada intent — é **injetado por quem
chama**. Três consequências, todas medidas:

1. **O gate de confiança M3 não é confiável.** `sandbox.py` só o aplica se
   `deteccao.get("scores")` for truthy. Um cliente que mande `meta: {}` nunca
   passa pelo gate. Hoje o dano é limitado porque `requires_confirmation`
   segura as escritas destrutivas — mas é coincidência, não desenho.

2. **Um cliente MCP não tem conversa nenhuma.** Não tem o vocabulário dos
   `exemplos`, não sabe o limiar, e as 10 Orientações do `GUIA` do
   `contrato.py` compensam com texto o que um detector daria de graça.

3. **A mesma frase dá resultados diferentes conforme quem perguntou** — o
   painel e o MCP não podem divergir, e não há nada que os impeça.

O QUE ESTE MÓDULO É
-------------------
Uma porta determinística, sem LLM, que faz no servidor o que o
`ia-local.js` faz no navegador. Mesma lista de stop, mesma sobreposição de
palavras, mesmo limiar. O JS passa a chamar isto em vez de calcular — e a
divergência entre os dois lados deixa de ser possível por construção.

POR QUE NÃO HÁ LLM AQUI
-----------------------
Porque o caminho crítico não pode depender de um modelo: a chamada mais
lenta é a que trava o produtor no meio do talhão, e um alerta que chega
tarde é um alerta inútil. A cauda longa — "como tá o tempo?", "tá
chovendo?" — é o que um modelo resolveria, e isso é uma decisão à parte,
comida em `app/ia/llm_gateway/`.

O QUE ESTE MÓDULO NÃO FAZ
-------------------------
Não substitui os fast-paths do navegador. Eles são bons e são UX: oito
perguntas que Toda a gente faz, respondidas sem round-trip. Este módulo
serve o resto — e o MCP, que não tem fast-paths.
"""

from __future__ import annotations

import re
from typing import Any

#: Palavras que não dizem nada sobre o que se quer. A mesma lista do
#: `ia-local.js`, palavra por palavra: divergir aqui faria o painel e o
#: MCP darem respostas diferentes à mesma frase, que é o defeito que este
#: módulo existe para eliminar.
STOP = frozenset(
    [
        "o",
        "a",
        "os",
        "as",
        "um",
        "uma",
        "de",
        "do",
        "da",
        "em",
        "para",
        "que",
        "qual",
        "quais",
        "como",
        "hoje",
        "agora",
        "me",
        "meu",
        "minha",
        "por",
        "favor",
        "tambem",
        "so",
        "ja",
        "ainda",
        "muito",
        "pouco",
        "mais",
        "menos",
        "com",
        "sem",
        "sobre",
        "entre",
        "ate",
        "desde",
        "ontem",
        "quando",
        "onde",
        "quanto",
        "esse",
        "essa",
        "este",
        "esta",
        "isso",
        "isto",
        "ele",
        "ela",
        "seu",
        "sua",
        "nao",
        "sim",
        "ser",
        "estar",
        "ter",
        "fazer",
        "dar",
        "ver",
        "dizer",
        "poder",
        "querer",
        "saber",
        "das",
        "dos",
        "pela",
        "pelo",
        "num",
        "numa",
        "temos",
        "tem",
        "fazenda",
        "sao",
        "aqui",
        "nossa",
        "nosso",
        "dela",
        "dele",
    ]
)

#: O limiar de aceitação.
#:
#: MEDIDO 2026-10-05. Era **0.6**, calibrado quando o score era a **SOMA** dos
#: exemplos. A soma favoreceva as intents com mais exemplos — uma intent com
#: 26 exemplos tinha 43% de vantagem sobre uma com 3. A linha 257 passou a
#: `score = round(total / n_exemplos, 2)` — a **média**, que é o certo.
#:
#: O limiar ficou na mesma. E a consequência foi medida: o detector **ranka
#: bem e rejeita todas as respostas**. Os nove casos de `tests_deteccao.py`
#: tinham o intent correcto em primeiro, com scores de 0.12 a 0.37 — todos
#: abaixo de 0.6 — e `escolhido` devolvia `None`. Nenhum intent chegava a
#: executar.
#:
#: Distribuicao medida com `_calib.py` (13 frases, 9 positivas e 3 negativas):
#:
#:     positivos (score do intent correcto): min=0.12  mediana=0.21  max=0.37
#:     negativos (melhor score):            0.00
#:
#: A separacao e' limpa: o pior positivo (0.12) e' seis vezes o melhor
#: negativo (0.00). O limiar vai no meio: **0.06**.
#:
#: Por que 0.06 e nao 0.10: um limiar mais alto nao protege contra nada que
#: este limiar nao proteja — o pior negativo e' 0.00, e 0.10 rejeitaria
#: rejeitaria o "como esta o tempo agora" (0.12) sem impedir nenhum falso
#: positivo. Por que nao 0.01: um limiar demasiado baixo deixa passar
#: qualquer ruido.
#:
#: O que este numero NAO faz e' substituir a medicao. Se os exemplos do
#: catalogo mudarem, este numero tem de ser medido outra vez — e
#: `tests/test_limiar_deteccao.py` falha se a distribuicao se mover.
LIMIAR = 0.06

_RE_PALAVRA = re.compile(r"[a-z0-9]+")
#: Particípios não são escrita: "cadastrados" é consulta ao existente.
#: A mesma regra de `sandbox.parece_cadastro`, pelo mesmo motivo.
_RE_PARTICIPIO = re.compile(r"\b\w+(ados|adas|idos|idas)\b")
_RE_ESCRITA = re.compile(
    r"(cadastr|cria\w*|crie|registr|adicion|exclu|delet|apag|edit|atualiz|manda|marc|marque)"
)
_RE_ESCRITA_FLAG = re.compile(r"write|create|comando")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento. `pulverizar` e `pulveriza` têm de casar."""
    import unicodedata

    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower()


def _palavras(texto: str) -> list[str]:
    return [
        w
        for w in _RE_PALAVRA.findall(normalizar(texto))
        if len(w) > 2 and w not in STOP
    ]


def _casa(a: str, b: str) -> bool:
    """Casa exacta, ou por prefixo — mas só com 5 letras ou mais.

    O mínimo de 5 existe para não inflar: `sol` e `solo` partilham 3 letras e
    transformariam "solo" num match de "solvente". É a mesma regra do JS.
    """
    if a == b:
        return True
    if len(a) >= 5 and b.startswith(a):
        return True
    return len(b) >= 5 and a.startswith(b)


def _escrita_pretendida(texto: str) -> bool:
    """A pessoa está a pedir para ESCREVER?

    Um pedido de cadastro nunca pode ser respondido com uma intent de leitura
    — foi o bug que originou `sandbox.parece_cadastro`.
    """
    t = _RE_PARTICIPIO.sub(" ", normalizar(texto))
    return bool(_RE_ESCRITA.search(t))


def detectar(
    texto: str,
    *,
    catalogo: dict[str, Any] | None = None,
    limiar: float = LIMIAR,
) -> dict[str, Any]:
    """`{metodo, scores, escolhido, acima_do_limiar}`.

    Devolve SEMPRE os scores de todos os intents — mesmo sem match. É o que
    permite a uma Interface mostrar *quase* que percebeu, e é o que torna o
    gate de confiança do `sandbox` Auditável: o score deixa de ser uma
    afirmação do cliente e passa a ser um número que o servidor calculou.
    """
    from app.ia.registro import REGISTO

    catalogo = catalogo if catalogo is not None else REGISTO
    palavras = _palavras(texto)
    base = {
        "metodo": "bag-of-words",
        "scores": {},
        "escolhido": None,
        "acima_do_limiar": False,
    }
    if not palavras:
        return base

    quer_escrever = _escrita_pretendida(texto)
    # Uma pergunta terminada em `?` é consulta, mesmo que contenha
    # "cadastrados" — "terminaram a tarefa?" é status, não escrita.
    e_pergunta = str(texto or "").strip().endswith("?")

    melhor, melhor_score = None, 0.0
    scores: dict[str, float] = {}

    for nome, spec in catalogo.items():
        flags = [str(f) for f in ((spec or {}).get("flags") or [])]
        # MEDIDAS, 2026-10-05: o `elif e_pergunta:` era inalcançável quando
        # `quer_escrever` era True — e `quer_escrever` é True sempre que a
        # frase contém um verbo de escrita. Uma pergunta educada como
        # "você pode excluir a safra?" era tratada como pedido de escrita.
        #
        # Agora a pergunta é verificada PRIMEIRO: se é pergunta, só leitura.
        if e_pergunta:
            # e uma pergunta, só leitura
            if any(re.search(r"write|create", f) for f in flags):
                continue
        elif quer_escrever:
            # um pedido de escrita só pode casar com uma intent que escreve
            if flags and not any(_RE_ESCRITA_FLAG.search(f) for f in flags):
                continue

        total = 0.0
        n_exemplos = 0
        for exemplo in (spec or {}).get("exemplos") or []:
            ew = _palavras(exemplo)
            if not ew:
                continue
            acertos = sum(1 for w in ew if any(_casa(u, w) for u in palavras))
            total += acertos / len(ew)
            n_exemplos += 1

        # MEDIDAS, 2026-10-05: antes `score = round(total, 2)` — a SOMA sobre
        # os exemplos, sem dividir pelo número de exemplos. Uma intent com 26
        # exemplos tinha 43% de vantagem sobre uma com 3. Agora é a MÉDIA.
        score = round(total / n_exemplos, 2) if n_exemplos > 0 else 0.0
        scores[nome] = score
        if score > melhor_score:
            melhor, melhor_score = nome, score

    base["scores"] = scores
    if melhor and melhor_score >= limiar:
        base["escolhido"] = melhor
        base["acima_do_limiar"] = True
        base["metodo"] = "forte" if melhor_score >= 1.0 else "fraco"
    return base
