"""Ler, editar e apagar dashboards pela IA. O CRUD que faltava à Fase 2.

O QUE JÁ EXISTIA, E O QUE FALTAVA
==================================
`preset_palco` (criar/atualizar) existe com confirmação e guarda. Faltavam
três perguntas que o produtor faz e a IA não respondia:

- "quais dashboards tenho?" (ler);
- "adiciona X / tira Y do dashboard Z" (editar por peça, não a lista toda);
- "apaga o dashboard Z" (excluir com confirmação).

POR QUE NÃO É UM INTENT SÓ, E POR QUE NÃO SÃO TRÊS HANDLERS NOVOS DO ZERO
=========================================================================
São três PERGUNTAS diferentes ("quais", "muda", "apaga") — e a doutrina do
produto proíbe duas ferramentas para a MESMA pergunta, não uma ferramenta
por pergunta. Leitura não pede confirmação; edição e exclusão pedem, pela
mesma `pode_escrever` do `h_preset_palco`, com o mesmo `confirm` vindo da
resposta do produtor. O fluxo de confirmação é o dele, não uma cópia: plano
-> `needs_confirm` -> guarda -> gravar/remover.

Editar por peça NÃO cria operação nova no serviço: lê a composição atual,
soma/subtrai tipos, e grava a lista inteira (`planear`/`gravar`). Prometer
`adicionar` como operação que "muda alguma coisa" seria mentir — ver
`palco_presets.OPERACOES`.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _do_produtore_nomes(user) -> list[str]:
    from app.ia import palco_presets

    return [str(p.nome) for p in palco_presets.listar(user)]


def h_preset_listar(user, params, ctx):
    """Quais dashboards o produtor guardou. Leitura: sem confirmação."""
    from app.ia import palco_presets

    presets = palco_presets.listar(user)
    if not presets:
        return {
            "ok": True,
            "resposta": (
                "Ainda não guardaste nenhum dashboard. Pede para guardar uma "
                "tela ('guarda essa tela') e ela aparece aqui."
            ),
            "dados": {"presets": []},
        }
    linhas = [
        f"• {p.nome} ({len((dict(p.estrutura or {})).get('widgets') or [])} widgets)"
        + (" [fixado]" if p.fixado else "")
        for p in presets
    ]
    return {
        "ok": True,
        "resposta": f"Os teus dashboards ({len(presets)}):\n" + "\n".join(linhas),
        "dados": {
            "presets": [
                {
                    "nome": p.nome,
                    "slug": p.slug,
                    "widgets": len((dict(p.estrutura or {})).get("widgets") or []),
                    "fixado": bool(p.fixado),
                    "estrutura": deepcopy(p.estrutura or {}),
                }
                for p in presets
            ]
        },
    }


def h_preset_editar(user, params, ctx):
    """Adiciona/tira widgets de um dashboard. Escrita: sempre com confirmação."""
    from app.ia import chamado as ch
    from app.ia import palco, palco_presets

    params = params or {}
    nome = str(params.get("nome") or params.get("preset") or "").strip()
    if not nome:
        return {
            "ok": False,
            "erro": (
                "diz qual dashboard mudar (nome). Para ver os teus: "
                "'quais dashboards tenho'."
            ),
        }
    alvo = palco_presets._por_nome_ou_slug(user, nome)
    if alvo is None:
        outros = _do_produtore_nomes(user)
        return {
            "ok": False,
            "erro": (
                f"não achei dashboard {nome!r}. "
                + (
                    f"Os teus: {', '.join(outros[:8])}."
                    if outros
                    else "Não tens nenhum dashboard guardado."
                )
            ),
        }
    for campo in ("adicionar", "remover"):
        valor = params.get(campo, [])
        if not isinstance(valor, list) or any(not isinstance(t, str) for t in valor):
            return {
                "ok": False,
                "erro": f"{campo} deve ser uma lista de tipos de widgets.",
            }
    adicionar = [
        str(t).strip() for t in (params.get("adicionar") or []) if str(t).strip()
    ]
    remover = [str(t).strip() for t in (params.get("remover") or []) if str(t).strip()]
    if not adicionar and not remover:
        return {
            "ok": False,
            "erro": (
                "diz o que mudar: adicionar=[tipos] e/ou remover=[tipos]. "
                "Os ids estão em `amplia://widgets`."
            ),
        }
    desconhecidos = sorted({t for t in adicionar if t not in palco.CATALOGO_IA})
    if desconhecidos:
        return {
            "ok": False,
            "erro": "Widgets desconhecidos: " + ", ".join(desconhecidos),
        }
    atuais = deepcopy((alvo.estrutura or {}).get("widgets") or [])
    nova = [w for w in atuais if w.get("tipo") not in set(remover)]
    presentes = {w.get("tipo") for w in nova}
    nova += [{"tipo": t} for t in dict.fromkeys(adicionar) if t not in presentes]
    if len(nova) > palco.MAX_WIDGETS:
        return {
            "ok": False,
            "erro": f"O limite é {palco.MAX_WIDGETS} widgets por dashboard.",
        }
    if not nova:
        return {
            "ok": False,
            "erro": (
                "a mudança esvaziaria o dashboard. Um dashboard sem widgets "
                "não serve para nada — apaga-o em vez disso, se for o caso."
            ),
        }
    plano = palco_presets.planear(
        user,
        alvo.nome,
        nova,
        operacao="atualizar",
        layout=(alvo.estrutura or {}).get("layout", ""),
        fixado=alvo.fixado,
    )
    if not plano.get("ok"):
        return plano
    confirmado = bool(params.get("confirm") or params.get("confirmado"))
    if not confirmado:
        partes = []
        if adicionar:
            partes.append(
                "adiciono " + ", ".join(sorted(set(adicionar) - set(desconhecidos)))
            )
        if remover:
            partes.append("tiro " + ", ".join(sorted(set(remover))))
        detalhe = " e ".join(partes) or "aplico a mudança"
        aviso_desc = (
            f" (ignoro {', '.join(desconhecidos)}, que não conheço)"
            if desconhecidos
            else ""
        )
        return {
            "ok": True,
            "resposta": (
                f'No dashboard "{alvo.nome}", {detalhe}{aviso_desc}? Fica no teu menu.'
            ),
            "dados": {
                "palco_preset": "plano",
                "nome": plano["nome"],
                "widgets": [w["tipo"] for w in plano["widgets"]],
                "criado_ou_atualizado": plano["operacao"],
                "destino": plano["destino"],
                "desconhecidos": desconhecidos,
            },
            "needs_confirm": True,
        }
    pode, motivo = ch.pode_escrever(user, plano.get("slug"), pedido_explicito=True)
    if not pode:
        return {"ok": False, "erro": motivo}
    gravado = palco_presets.gravar(user, plano)
    if not gravado.get("ok"):
        return gravado
    return {
        "ok": True,
        "resposta": (
            f'Dashboard "{alvo.nome}" atualizado '
            f"({gravado['preset']['widgets']} widgets). Fica no teu menu."
        ),
        "dados": {"palco_preset": gravado, "escrito_por_ia": True},
    }


def h_preset_apagar(user, params, ctx):
    """Apaga um dashboard. Escrita destrutiva: sempre com confirmação."""
    from app.ia import chamado as ch
    from app.ia import palco_presets

    params = params or {}
    nome = str(params.get("nome") or params.get("preset") or "").strip()
    if not nome:
        return {
            "ok": False,
            "erro": (
                "diz qual dashboard apagar (nome). Para ver os teus: "
                "'quais dashboards tenho'."
            ),
        }
    alvo = palco_presets._por_nome_ou_slug(user, nome)
    if alvo is None:
        outros = _do_produtore_nomes(user)
        return {
            "ok": False,
            "erro": (
                f"não achei dashboard {nome!r}. "
                + (
                    f"Os teus: {', '.join(outros[:8])}."
                    if outros
                    else "Não tens nenhum dashboard guardado."
                )
            ),
        }
    n = len((alvo.estrutura or {}).get("widgets") or [])
    confirmado = bool(params.get("confirm") or params.get("confirmado"))
    if not confirmado:
        return {
            "ok": True,
            "resposta": (
                f'Apago o dashboard "{alvo.nome}" com {n} '
                + ("widget? Não tem volta." if n == 1 else "widgets? Não tem volta.")
            ),
            "dados": {
                "palco_preset": "plano_apagar",
                "nome": alvo.nome,
                "slug": alvo.slug,
                "widgets": n,
            },
            "needs_confirm": True,
        }
    pode, motivo = ch.pode_escrever(user, alvo.slug, pedido_explicito=True)
    if not pode:
        return {"ok": False, "erro": motivo}
    apagado = palco_presets.remover(user, alvo.slug)
    if not apagado.get("ok"):
        return apagado
    return {
        "ok": True,
        "resposta": f'Dashboard "{apagado["nome"]}" apagado.',
        "dados": {"palco_preset": apagado},
    }


INTENTS_PRESET_CRUD = {
    "preset_listar": {
        "descricao": (
            "INSTRUÇÃO IA: use para 'quais dashboards tenho', 'meus painéis', "
            "'lista meus dashboards'. Só lê, nunca pede confirmação."
        ),
        "exemplos": [
            "quais dashboards tenho",
            "meus painéis",
            "lista meus dashboards",
            "mostra meus dashboards guardados",
        ],
        "flags": ["palco.read"],
        "handler": h_preset_listar,
    },
    "preset_editar": {
        "params_schema": {
            "nome": {"type": "string"},
            "adicionar": {"type": "array", "items": {"type": "string"}},
            "remover": {"type": "array", "items": {"type": "string"}},
        },
        "descricao": (
            "INSTRUÇÃO IA: use para 'adiciona X no dashboard Y', 'tira Z do "
            "dashboard Y', 'muda os widgets do dashboard'. Recebe nome e "
            "listas adicionar/remover com ids de `amplia://widgets`. "
            "**Pede confirmação sempre**, como `preset_palco`."
        ),
        "exemplos": [
            "adiciona o kpi de caixa no dashboard Custo",
            "tira o gráfico de safras do meu painel",
            "remove o kpi-alertas do dashboard Financeiro",
            "muda os widgets do dashboard Custo",
        ],
        "flags": ["palco.write"],
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou mudar os widgets desse dashboard. Confere a lista nova e confirma?"
        ),
        "handler": h_preset_editar,
    },
    "preset_apagar": {
        "params_schema": {"nome": {"type": "string"}},
        "descricao": (
            "INSTRUÇÃO IA: use para 'apaga o dashboard X', 'exclui meu painel', "
            "'deleta o dashboard'. Recebe nome. **Pede confirmação sempre**: "
            "apagar não tem volta."
        ),
        "exemplos": [
            "apaga o dashboard Custo",
            "exclui meu painel antigo",
            "deleta o dashboard de teste",
            "remove o dashboard Financeiro",
        ],
        "flags": ["palco.write"],
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou apagar esse dashboard com tudo dentro. Não tem volta. Confirmas?"
        ),
        "handler": h_preset_apagar,
    },
}
