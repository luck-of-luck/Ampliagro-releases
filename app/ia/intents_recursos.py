"""Campos do produto acessíveis ao copiloto pelo catálogo real da API."""

import json

from app.ia import recursos


def h_recursos_catalogo(user, params, ctx):
    resultado = recursos.executar_seguro(
        recursos.catalogo, user, params.get("recurso"), params.get("filtros")
    )
    if resultado.get("ok") is False:
        return resultado
    return {
        "ok": True,
        "resposta": (
            "Recursos disponíveis: " + ", ".join(resultado["recursos"])
            if "recursos" in resultado
            else "Campos de "
            + params["recurso"]
            + ":\n"
            + "\n".join(
                f"{nome}: {campo['rotulo']} ({campo['tipo']}; "
                + ("somente leitura" if campo["somente_leitura"] else "editável")
                + ")"
                for nome, campo in resultado["campos"].items()
            )
        ),
        "dados": resultado,
    }


def h_recurso_ler(user, params, ctx):
    resultado = recursos.executar_seguro(
        recursos.operar,
        user,
        params.get("recurso"),
        "ler" if params.get("id") else "listar",
        identificador=params.get("id"),
        filtros=params.get("filtros"),
    )
    if resultado.get("ok"):
        texto = json.dumps(
            resultado["dados"]["resultado"], ensure_ascii=False, indent=2, default=str
        )
        resultado["resposta"] = texto[:12000] + (
            "\nExibição abreviada; refine os filtros." if len(texto) > 12000 else ""
        )
    return resultado


def resumo_alteracao(params):
    campos = json.dumps(
        recursos._limpar(params.get("campos") or {}), ensure_ascii=False, default=str
    )
    return f"{params.get('operacao', 'Alterar')} {params.get('recurso', 'recurso')} #{params.get('id', '?')}: {campos[:600]}. Confirma?"


def h_recurso_alterar(user, params, ctx):
    if params.get("operacao") not in {"editar", "excluir"}:
        return {"ok": False, "erro": "Use editar ou excluir."}
    if not params.get("confirm"):
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": "Confirme a alteração do registro e dos campos informados.",
        }
    return recursos.executar_seguro(
        recursos.operar,
        user,
        params.get("recurso"),
        params["operacao"],
        identificador=params.get("id"),
        dados=params.get("campos"),
        filtros=params.get("filtros"),
    )


_COMUNS = {"recurso": {"type": "string"}, "filtros": {"type": "object"}}
INTENTS_RECURSOS = {
    "recursos_catalogo": {
        "descricao": "Descobre os recursos reais do sistema. Com recurso, informa os campos, tipos e operações. Consulte antes de editar; filtros podem selecionar cultura nos registros dinâmicos.",
        "exemplos": ["quais campos posso editar", "liste os recursos do sistema"],
        "flags": ["dados.read"],
        "params_schema": _COMUNS,
        "handler": h_recursos_catalogo,
    },
    "recurso_ler": {
        "descricao": "Lê qualquer recurso do catálogo na conta do usuário. Com id lê um registro; sem id lista uma página. filtros aceita search, limit (até 50), offset e os filtros do módulo.",
        "exemplos": ["consultar dados do recurso", "ler campos do registro"],
        "flags": ["dados.read"],
        "params_schema": {**_COMUNS, "id": {"type": "integer"}},
        "handler": h_recurso_ler,
    },
    "recurso_alterar": {
        "descricao": "Edita campos ou exclui um registro do recurso. Reutiliza validações e permissões do módulo. Mover entre locais/propriedades é editar o relacionamento permitido. Leia o registro e o catálogo primeiro, informe id real e apenas campos solicitados. Exige confirmação.",
        "exemplos": ["editar campos de um registro", "excluir registro do sistema"],
        "flags": ["dados.write"],
        "requires_confirmation": True,
        "prompt_confirmacao": "Vou aplicar a operação e os campos solicitados ao registro indicado. Confirma?",
        "resumo_confirmacao": resumo_alteracao,
        "params_schema": {
            **_COMUNS,
            "id": {"type": "integer"},
            "operacao": {"type": "string", "enum": ["editar", "excluir"]},
            "campos": {"type": "object"},
        },
        "handler": h_recurso_alterar,
    },
}
