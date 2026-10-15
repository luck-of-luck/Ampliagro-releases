"""Operações individuais nos widgets persistidos do produtor."""

from copy import deepcopy

from django.db import transaction

from app.ia import chamado, palco, palco_presets
from app.models.palco import PresetPalco


def h_widget_ler(user, params, ctx):
    alvo = palco_presets._por_nome_ou_slug(user, params.get("preset"))
    if alvo is None:
        return {"ok": False, "erro": "Dashboard não encontrado nesta conta."}
    widgets = deepcopy((alvo.estrutura or {}).get("widgets", []))
    tipo = params.get("widget")
    if tipo:
        widgets = [w for w in widgets if w.get("tipo") == tipo]
        if not widgets:
            return {"ok": False, "erro": "Widget não encontrado nesse dashboard."}
    return {
        "ok": True,
        "resposta": f"{alvo.nome}: "
        + ", ".join(w.get("titulo", w["tipo"]) for w in widgets),
        "dados": {"preset": alvo.slug, "widgets": widgets},
    }


@transaction.atomic
def h_widget_alterar(user, params, ctx):
    """Move atomicamente entre presets; nunca reconstrói as outras peças."""
    operacao = params.get("operacao")
    if operacao not in {"editar", "mover", "excluir"}:
        return {"ok": False, "erro": "Use editar, mover ou excluir."}
    alvo = palco_presets._por_nome_ou_slug(user, params.get("preset"))
    destino = (
        palco_presets._por_nome_ou_slug(user, params.get("destino"))
        if params.get("destino")
        else alvo
    )
    if alvo is None or destino is None:
        return {
            "ok": False,
            "erro": "Dashboard de origem ou destino não encontrado nesta conta.",
        }
    if destino.pk != alvo.pk and operacao != "mover":
        return {"ok": False, "erro": "Destino só é aceito para mover."}
    # Ordem estável evita deadlocks em movimentos simultâneos A→B e B→A.
    bloqueados = {
        p.pk: p
        for p in PresetPalco.objects.do_produtore(user)
        .select_for_update()
        .filter(pk__in=[alvo.pk, destino.pk])
        .order_by("pk")
    }
    if alvo.pk not in bloqueados or destino.pk not in bloqueados:
        return {"ok": False, "erro": "Um dashboard foi removido. Consulte novamente."}
    alvo, destino = bloqueados[alvo.pk], bloqueados[destino.pk]
    estruturas = {p.pk: deepcopy(p.estrutura or {}) for p in (alvo, destino)}
    widgets = estruturas[alvo.pk].setdefault("widgets", [])
    indice = next(
        (i for i, w in enumerate(widgets) if w.get("tipo") == params.get("widget")),
        None,
    )
    if indice is None:
        return {"ok": False, "erro": "Widget não encontrado na origem."}
    widget = widgets[indice]
    if operacao == "editar":
        if not any(k in params for k in ("titulo", "config")):
            return {"ok": False, "erro": "Informe titulo e/ou config para editar."}
        if "titulo" in params:
            if (
                not isinstance(params["titulo"], str)
                or not params["titulo"].strip()
                or len(params["titulo"]) > 120
            ):
                return {
                    "ok": False,
                    "erro": "Título deve ter entre 1 e 120 caracteres.",
                }
            widget["titulo"] = params["titulo"].strip()
        if "config" in params:
            if not isinstance(params["config"], dict):
                return {
                    "ok": False,
                    "erro": "Config deve ser um objeto de parâmetros do widget.",
                }
            widget["config"] = {
                **widget.get("config", {}),
                **deepcopy(params["config"]),
            }
    elif operacao == "excluir":
        widgets.pop(indice)
    else:
        outros = estruturas[destino.pk].setdefault("widgets", [])
        if destino.pk != alvo.pk:
            if any(w.get("tipo") == widget["tipo"] for w in outros):
                return {"ok": False, "erro": "O destino já contém esse tipo de widget."}
            if len(outros) >= palco.MAX_WIDGETS:
                return {
                    "ok": False,
                    "erro": "O dashboard de destino atingiu o limite de widgets.",
                }
        tamanho = len(outros) - (destino.pk == alvo.pk)
        posicao = params.get("posicao", tamanho + 1)
        if type(posicao) is not int or not 1 <= posicao <= tamanho + 1:
            return {
                "ok": False,
                "erro": f"Posição deve ser um inteiro entre 1 e {tamanho + 1}.",
            }
        widgets.pop(indice)
        outros.insert(posicao - 1, widget)
    if not params.get("confirm"):
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": f"Confirma {operacao} {widget['tipo']} em {alvo.nome}?",
            "dados": {"antes": alvo.estrutura, "depois": estruturas},
        }
    for p in bloqueados.values():
        pode, motivo = chamado.pode_escrever(user, p.slug, pedido_explicito=True)
        if not pode:
            return {"ok": False, "erro": motivo}
    for p in bloqueados.values():
        p.estrutura = estruturas[p.pk]
        p.save(update_fields=["estrutura"])
    return {
        "ok": True,
        "resposta": f"Widget {widget['tipo']}: operação {operacao} concluída.",
        "dados": {
            "meus_presets": [
                {"slug": p.slug, "nome": p.nome, "estrutura": p.estrutura}
                for p in bloqueados.values()
            ],
            "presets_atualizados": [p.slug for p in bloqueados.values()],
            "escrito_por_ia": True,
        },
    }


INTENTS_WIDGET = {
    "widget_ler": {
        "descricao": "Lê os widgets, títulos e configurações de um preset do usuário. Consulte antes de alterar.",
        "exemplos": ["mostra os widgets do dashboard", "ler configuração do widget"],
        "flags": ["palco.read"],
        "params_schema": {"preset": {"type": "string"}, "widget": {"type": "string"}},
        "handler": h_widget_ler,
    },
    "widget_alterar": {
        "descricao": "Edita titulo/config, exclui ou move um widget pelo tipo em um preset. posicao começa em 1; destino opcional move entre presets. Preserva os outros widgets. Sempre exige confirmação.",
        "exemplos": [
            "mover widget para outro dashboard",
            "editar título do widget",
            "excluir widget do preset",
        ],
        "flags": ["palco.write"],
        "requires_confirmation": True,
        "prompt_confirmacao": "Vou aplicar a edição, movimentação ou exclusão solicitada no widget. Confirma?",
        "params_schema": {
            "preset": {"type": "string"},
            "widget": {"type": "string"},
            "operacao": {"type": "string", "enum": ["editar", "mover", "excluir"]},
            "destino": {"type": "string"},
            "posicao": {"type": "integer", "minimum": 1},
            "titulo": {"type": "string", "maxLength": 120},
            "config": {"type": "object"},
        },
        "handler": h_widget_alterar,
    },
}
