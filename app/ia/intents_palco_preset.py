"""Gravar a mesa da IA num preset do produtor. Fase 2, o caminho de execucao.

ONDE ESTA O QUE
================
O servico esta em `app/ia/palco_presets.py`. Aqui so' ha' o `intent`, que traduz
o que a IA diz para o que o servico faz. A separacao nao e' picky: o servico
precisa de ser usavel por uma view (o botao "Salvar como meu Dashboard") sem
passar por `sandbox.executar`, e o intent precisa de estar no `REGISTO` para a IA
o ver. Sao dois consumidores, uma regra.

A TRAVA, E ONDE ELA VIVE
=========================
`chamado_intents.py:225-240` diz a regra e o motivo:

    *"A TRAVA VIVE AQUI, NO HANDLER, e nao num `if` discreto."*

E porque nao num `if` no servico: uma restricao que depende de alguem se lembrar
de a aplicar e' uma restricao que uma sessao cansada burla. Aqui a restricao e'
`requires_confirmation` no spec, e o `sandbox` aplica-a — e quem escreve um
handler novo tem de escrever o nome da flag, nao lembrar-se de um `if`.

O `user` NAO VEM DO CORPO
=========================
`chamado_intents.py:296-299`, textual: *"nenhuma delas aceita um `user`: o produtor
e' o `user` que vem do sandbox, e um campo de produtor no corpo do pedido e' a
forma mais curta de um vazamento entre contas."* Aqui nao ha `user` em `params`.
"""

from __future__ import annotations

from typing import Any


def _lista_widgets(params: dict[str, Any]) -> list[dict[str, Any]] | None:
    """A composicao que a IA mandou, ou `None` se nao mandou nenhuma.

    Aceita as tres formas porque a IA as produz todas: a lista directa (o que o
    sandbox normaliza), o envelope `{"widgets": [...]}` (o que `render_preset`
    devolve em `dados`), e a chave `widget_composicao` (o caminho da Fase 1).
    """
    for chave in ("widgets", "widget_composicao", "composicao"):
        bruto = params.get(chave)
        if bruto:
            if isinstance(bruto, dict):
                bruto = bruto.get("widgets")
            if isinstance(bruto, list) and bruto:
                return bruto
    return None


def h_preset_palco(user, params, ctx):
    """A IA grava a mesa num preset do produtor. **Apos confirmacao.**

    ESCRITA, e por isso confirma: um preset e' trabalho do produtor — ele
    renomeou, organizou, apagou o que nao serve. Uma IA que escreve neles sem
    perguntar reescreve o trabalho de quem os organiza, e o produtor ve a tela
    mudar sem ter pedido (`chamado.py:52-63`).

    O que a IA **nao** pode fazer aqui, por construcao:
    - gravar num preset de outro produtor (o `user` nao vem do corpo);
    - criar um widget novo (o catalogo e' `palco.CATALOGO_IA`);
    - inventar um numero (a composicao so' nomeia widgets; os valores vem do
      `dados` do intent que respondeu a pergunta);
    - gravar sem o produtor dizer que sim.
    """
    from app.ia import chamado as ch
    from app.ia import palco_presets

    params = params or {}
    # O `pedido_explicito` NAO vem de `params`. Vem de `confirm`, que e' a
    # resposta do produtor e nao uma palavra do modelo. Se um dia este `pop`
    # desaparecer, `test_a_ia_nao_pode_forcar_a_excepcao_pelos_params` falha.
    params.pop("pedido_explicito", None)
    params.pop("slug", None)
    widgets = _lista_widgets(params)
    nome = str(params.get("nome") or params.get("preset") or "").strip()
    confirmado = bool(params.get("confirm") or params.get("confirmado"))

    if widgets is None:
        return {
            "ok": False,
            "erro": (
                "diz que mesa quer gravar: nome e a lista de widgets "
                "(widgets=[{tipo, titulo}]). Os ids estao em `amplia://widgets`."
            ),
            "catalogo": _catalogo_resumido(),
        }

    plano = palco_presets.planear(
        user,
        nome,
        widgets,
        operacao=str(params.get("operacao") or "criar"),
        layout=str(params.get("layout") or ""),
        fixado=bool(params.get("fixado", False)),
    )
    if not plano.get("ok"):
        return plano

    if not confirmado:
        # A RESPOSTA, nao um erro. O produtor tem de ver o que ia acontecer
        # ANTES de acontecer, e o "nao" tem de ser uma resposta e' — por isso
        # aqui nao se levanta nada: devolve-se o que se faria, e o sandbox fica
        # a espera da resposta.
        return {
            "ok": True,
            "resposta": _pergunta(user, plano),
            "dados": {
                "palco_preset": "plano",
                "nome": plano["nome"],
                "widgets": [w["tipo"] for w in plano["widgets"]],
                "criado_ou_atualizado": plano["operacao"],
                "destino": plano["destino"],
                "fixado": plano["fixado"],
                "descartados": plano["descartados"],
            },
            "needs_confirm": True,
        }

    # A GUARDA, e dentro do handler — `chamado_intents.py:5`: "pode_escrever é
    # chamado dentro de cada handler de escrita, antes de gravar". Sem esta
    # chamada, este handler era um `PresetPalco` reescrevível exactamente como
    # `models/palco.py` descreve que não deve existir.
    #
    # `pedido_explicito` vem de `confirm`, que é a RESPOSTA do produtor, e não
    # um campo que o modelo preencha. Se algum dia vier de `params`, a guarda
    # passa a ser decorativa e este comentario a mentira.
    pode, motivo = ch.pode_escrever(user, plano.get("slug"), pedido_explicito=True)
    if not pode:
        return {"ok": False, "erro": motivo}

    gravado = palco_presets.gravar(user, plano)
    if not gravado.get("ok"):
        return gravado

    p = gravado["preset"]
    return {
        "ok": True,
        "resposta": (
            f"{'Criei' if gravado['criado'] else 'Atualizei'} o dashboard "
            f'"{p["nome"]}" com {p["widgets"]} '
            + ("widget." if p["widgets"] == 1 else "widgets.")
            + " Fica no teu menu."
        ),
        "dados": {"palco_preset": gravado, "escrito_por_ia": True},
    }


def _catalogo_resumido() -> list[str]:
    from app.ia import palco

    return sorted(palco.CATALOGO_IA)


def _pergunta(user, plano: dict[str, Any]) -> str:
    """A pergunta que o produtor responde.

    Primeira pessoa, sem markdown: `voz.py` lava o `**` na fronteira, mas uma
    resposta com asteriscos duplos no ecra do telefone e' um produtor a adivinhar
    o resto. E o `sandbox` lava depois — aqui ja' vai limpo.
    """
    tipos = ", ".join(w["tipo"] for w in plano["widgets"][:4])
    mais = f" e mais {len(plano['widgets']) - 4}" if len(plano["widgets"]) > 4 else ""
    verbo = "Atualizo" if plano["destino"] else "Crio"
    return (
        f'{verbo} o dashboard "{plano["nome"]}" com {tipos}{mais}? '
        "Fica no teu menu, e podes renomear ou apagar quando quiseres."
    )


INTENTS_FASE2 = {
    "preset_palco": {
        "descricao": (
            "INSTRUÇÃO IA: use quando o produtor PEDIR QUE UMA TELA FIQUE GUARDADA "
            "no dashboard dele ('guarda essa tela', 'cria um dashboard de custo', "
            "'quero ver sempre estes numeros', 'salva isso como dashboard'). "
            "Recebe nome e widgets (tipo, titulo). "
            "**Pede confirmacao sempre**: um dashboard e' trabalho do produtor "
            "e esta e' a UNICA forma de a IA escrever num preset que nao seja "
            "o Chamado Amplia — e so' a pedido dele. "
            "NÃO use para montar a tela: isso e' `render_preset`. Os ids dos "
            "widgets estao em `amplia://widgets` (kpi-custo, kpi-caixa, "
            "kpi-produtividade, chart-safras, ...)."
        ),
        "exemplos": [
            "guarda essa tela",
            "cria um dashboard de custo",
            "fixa essa mesa no meu painel",
            "salva isso como dashboard",
            "quero ver sempre estes numeros",
        ],
        "flags": ["palco.create", "palco.write"],
        "requires_confirmation": True,
        # O PRODUTOR, NAO O MODELO. `prompt_de_confirmacao` (texto.py:109)
        # escolhe este texto antes da `descricao`, e a razao de existir e' essa:
        # a `descricao` e' escrita PARA O MODELO, e echoa-la ao produtor punha a
        # unica barreira antes de mexer no trabalho dele com texto de
        # engenharia (sandbox.py:772-777).
        #
        # E' ESTATICO de proposito: `texto.py:122` aceita `params` mas nao os
        # interpola, para nao prometer o que o codigo nao faz. Logo nao se pode
        # meter aqui o nome do dashboard. Compensa-se porque o produtor acabou de
        # ver a tela que mandou guardar — "essa" e' a unica que faz sentido.
        "prompt_confirmacao": (
            "Vou guardar esta tela como um dashboard teu. Fica no teu menu, e "
            "podes renomear, reordenar ou apagar quando quiseres. Confirmas?"
        ),
        "handler": h_preset_palco,
    },
}
