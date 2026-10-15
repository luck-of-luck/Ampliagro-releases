"""O limiar de aceitacao do detector tem de estar calibrado, nao adivinhado.

O QUE ACONTECEU
===============
MEDIDO 2026-10-05. `app/ia/deteccao.py:257` mudou o score da **SOMA** dos
exemplos para a **MEDIA**:

    antes:  score = round(total, 2)                     # SOMA
    agora:  score = round(total / n_exemplos, 2)        # MEDIA

A mudanca e' CORRECTA. Com a soma, uma intent com 26 exemplos tinha 43% de
vantagem sobre uma com 3: o numero media a quantidade de exemplos, nao a
similaridade. A media mede o que se quer medir.

O que ficou desactualizado foi o `LIMIAR`, que ficou em 0.6 — calibrado para a
soma. E a consequencia foi grave:

    os nove casos de tests_deteccao.py rankavam o intent CORRECTO em primeiro,
    com scores de 0.12 a 0.37 — todos abaixo de 0.6
    -> escolhido = None
    -> nenhum intent chegava a executar

**O detector rankava bem e rejeitava todas as respostas.** Nao ha sintoma
visivel disso no ecra: a IA respondia "nao percebi", que e' indistinguivel de
uma IA que nao percebe mesmo.

DISTRIBUICAO MEDIDA
===================
    positivos (score do intent correcto): min=0.12  mediana=0.21  max=0.37
    negativos (melhor score):            0.00

A separacao e' limpa. O limiar vai no meio: 0.06.

O QUE ESTES TESTES PROVAM
=========================
Que a separacao continua a existir. Nao que o numero 0.06 e' correcto para
sempre — que se os exemplos do catalogo mudarem, o numero tem de ser medido
outra vez, e estes testes dizem-o.
"""

import pytest

from app.ia.deteccao import LIMIAR, detectar

# (frase, intent esperado) — os casos que TEM de passar por cima do limiar.
POSITIVOS = [
    ("como esta o tempo agora", "clima_agora"),
    ("vai chover amanha", "vai_chover"),
    ("quando pulverizar", "melhor_pulverizar"),
    ("quanto rendeu a safra de soja", "resumo_safra"),
    ("listar maquinas", "listar_maquinas"),
    ("talhoes", "resumo_talhoes"),
    ("registrar o trator novo", "cadastrar_maquina"),
    ("excluir a safra milho 2025", "excluir_safra"),
]

# Frases que NAO podem chegar a nenhuma intent.
NEGATIVOS = [
    "xyzzy plugh",
    "aaaa bbbb",
    "asdkjhaskdjh qwerty zzz",
]


def _score_do_esperado(frase, esperado):
    d = detectar(frase)
    return d["scores"].get(esperado, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Os positivos passam
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("frase,esperado", POSITIVOS)
def test_o_intent_correcto_passa_o_limiar(frase, esperado):
    """Cada caso de `tests_deteccao.py` tem de chegar a `escolhido`.

    Com o limiar em 0.6 e a media em vez da soma, **todos** estes davam
    `escolhido = None`. E `None` nao levanta excepcao: a IA respondia "nao
    percebi" e o produtor achava que a IA era burra.
    """
    d = detectar(frase)
    assert d["acima_do_limiar"], (
        f"{frase!r} -> {d['escolhido']!r} com score {d['scores'].get(esperado)} "
        f"(limiar {LIMIAR}).\n\n"
        "O detector rankou o intent certo e rejeitou-o. Ou o LIMIAR esta "
        "descalibrado, ou a metrica do score voltou a ser a SOMA — a media "
        "e' a correcta, e `deteccao.py:257` documenta porquê."
    )
    assert d["escolhido"] == esperado, (
        f"{frase!r} passou o limiar mas escolheu {d['escolhido']!r}. "
        f"Esperado {esperado!r}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Os negativos nao passam
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("frase", NEGATIVOS)
def test_o_lixo_nao_passa_o_limiar(frase):
    """Lixo nao pode chegar a executar nada."""
    d = detectar(frase)
    assert not d["acima_do_limiar"], (
        f"{frase!r} passou o limiar com {d['escolhido']!r} "
        f"(score {max(d['scores'].values()) if d['scores'] else 0})."
    )
    assert d["escolhido"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. A SEPARACAO — que e' o numero que realmente importa
# ─────────────────────────────────────────────────────────────────────────────


def test_ha_separacao_entre_positivos_e_negativos():
    """O pior positivo tem de estar claramente acima do melhor negativo.

    Este e' o teste que substitui "o limiar e' 0.06". Um limiar so e' util se
    houver um **intervalo** em que nao ha sobreposicao. Se este teste falha,
    a resposta nao e' mexer no numero: e' que a metrica do score mudou, ou
    que os exemplos do catalogo mudaram, e o limiar tem de ser re-medido.
    """
    piores_pos = [(_score_do_esperado(f, e), f) for f, e in POSITIVOS]
    piores_neg = [(max(detectar(f)["scores"].values() or [0.0]), f) for f in NEGATIVOS]

    min_pos = min(s for s, _ in piores_pos)
    max_neg = max(s for s, _ in piores_neg)

    assert min_pos > max_neg, (
        "NAO HA SEPARACAO. O pior positivo faz %.2f e o melhor negativo faz "
        "%.2f.\n\n"
        "positivo mais fraco: %r (%.2f)\n"
        "negativo mais forte: %r (%.2f)\n\n"
        "Quando ha sobreposicao, **mexer no limiar e' a resposta errada** — so "
        "havera um numero que deixe passar o pior positivo, e esse numero "
        "deixa passar o melhor negativo tambem. Ou a metrica do score mudou "
        "(`deteccao.py:257`), ou os exemplos do catalogo mudaram."
        % (
            min_pos,
            max_neg,
            min(piores_pos, key=lambda x: x[0])[1],
            min_pos,
            max(piores_neg, key=lambda x: x[0])[1],
            max_neg,
        )
    )

    # E o limiar tem de estar DENTRO do intervalo. Se estiver fora, ou rejeita
    # um positivo ou aceita um negativo — e nenhuma das duas e' um numero que
    # merite estar no codigo.
    assert min_pos > LIMIAR > max_neg, (
        f"o limiar ({LIMIAR}) esta fora do intervalo util "
        f"({max_neg}, {min_pos}). Ou rejeita o pior positivo, ou aceita o "
        "melhor negativo."
    )


def test_o_limiar_nao_esta_zerado():
    """`LIMIAR = 0` aceitaria qualquer intent com score > 0.

    Seria a pior possivel falha para um limiar: aceita o primeiro que aparece,
    que e' o que o plano §1.1 critica no motor de plantio, visto pelo outro
    lado.
    """
    assert LIMIAR > 0, "um limiar zero nao e' um limiar"


def test_o_limiar_nao_tao_alto_que_rejeite_tudo():
    """O sintoma do `0.6`: o detector ranka bem e rejeita tudo.

    Este teste existe para o dia em que alguem reintroduzir a SOMA no score.
    Com a soma, os scores sobem para 1.5-2.5 e um limiar de 0.06 aceitaria
    quase tudo — que e' o erro oposto, e igualmente mau.
    """
    scores = [_score_do_esperado(f, e) for f, e in POSITIVOS]
    maximo = max(scores)
    assert maximo < 1.0, (
        f"o score maximo e' {maximo:.2f}. Com a metrica correcta (media) os "
        "scores ficam em 0.12-0.37. Um valor acima de 1 sugere que o score "
        "voltou a ser a SOMA dos exemplos — `deteccao.py:257`."
    )
