"""
proativo_intents.py — as tools do Motor Proativo.

O DESVIO DELIBERADO: A TOOL NÃO ACEITA `user_id` DO MODELO
==========================================================
O enunciado propõe `amplia_emit_proactive_alert(user_id, mensagem, nivel)`.
O parâmetro `user_id` foi **removido do schema**, e o motivo é de segurança,
não de estilo:

    Um `user_id` preenchido pelo modelo é um `user_id` preenchido por um modelo
    de 1,7B que alucina. O pior caso não é o modelo errar o número: é ele
    repetir — ou ser induzido a repetir — um número que estava em outro lugar
    do contexto, e o alerta sair no nome da pessoa errada. Isso polui a trilha
    de auditoria de outro produtor e faz o alerta aparecer no celular de quem
    não tem nada a ver com ele.

    O produtor não é "o dono da sessão" nesta arquitetura: o alerta proativo
    nasce de um WORKER, e um worker não tem sessão. Quem emite é o
    servidor, que sabe exatamente de quem é o cenário.

Por compatibilidade, se `user_id` vier (um prompt antigo, um script), a tool
**recusa** quando não bate com o contexto — em vez de ignorar em silêncio, que
seria pior: o modelo receberia "ok" e tentaria de novo.

A tool é `write` e pede confirmação, como toda escrita. Mas o caso comum dela
é o servidor chamando por dentro, e nesse caminho ela não pede confirmação de
ninguém: uma confirmação que ninguém pode responder é um aviso que ninguém vê.
O `.dados` distingue os dois caminhos (`origem: "worker" | "modelo"`).
"""

from __future__ import annotations

from typing import Any

from app.ia.proativo import (
    avaliar_usuario,
    emitir_alerta,
    montar_cenario,
    regras_deterministicas,
)


def _propriedade_de(user, params) -> Any:
    """Resolve a propriedade do USUÁRIO. `params` não escolhe dono.

    A propriedade é o que amarra o alerta a um lugar: um alerta sem fazenda é
    um alerta que o produtor não sabe onde aplicar. E a propriedade vem do
    contexto do produtor, nunca de um id que o modelo possa ter inventado.

    O `propriedade_id` que NÃO é seu é RECUSADO, não ignorado
    ----------------------------------------------------------

    MEDIDO 2026-10-06, por
    `app/tests_escrita_tenancy.py::test_ligar_proatividade_recusa_propriedade_
    alheia`: o codigo era

        qs = Propriedade.objects.filter(user=user)
        if pid:
            prop = qs.filter(pk=pid).first()
            if prop is not None:
                return prop
        # senão: a primeira com proatividade ligada; sem isso, a primeira do user

    `qs` filtra por `user`, o que parece a protecao. Mas quando `pid` e' de
    outro produtor, `qs.filter(pk=pid).first()` devolve `None` e o codigo
    CAIA PARA O `return qs.first()` — devolvendo a propriedade do utilizador
    certo, sem dizer nada.

    MEDIDO: `amplia_ligar_proatividade` com `propriedade_id` alheio e
    `confirm=true` respondeu

        {'ok': True, 'resposta': 'Motor proativo DESLIGADO em Minha.'}

    O pedido nao falhou por理由を de seguranca — falhou por ACCIDENTE, porque
    o utilizador happens to ter uma propriedade sua para cair nela. Com
    `confirm=false` o modelo recebia `needs_confirm` a falar de UMA propriedade
    que nao pediu e, ao confirmar, escrevia nela.

    Um filtro que devolve `None` e um filtro que devolve a propriedade errada
    sao o mesmo erro em dois formatos. A diferenca e' que o `None` ao menos
    parava.

    A regra: se o modelo mandou um `propriedade_id`, esse id tem de ser seu. Se
    nao for, a resposta e' um erro que DIZ QUE O ID E' DE OUTRO — porque
    "propriedade inexistente" e "propriedade de outro" sao diagnosticos
    diferentes e o produtor so pode corrigir o segundo.
    """
    from app.models import ProativoPreferencia, Propriedade

    qs = Propriedade.objects.filter(user=user)
    pid = params.get("propriedade_id")

    if pid:
        prop = qs.filter(pk=pid).first()
        if prop is not None:
            return prop

        # O id foi dado e não é seu. Dizer qual dos dois é, sem dizer de quem.
        existe = Propriedade.objects.filter(pk=pid).exists()
        motivo = (
            "a propriedade existe mas e' de outro produtor"
            if existe
            else "a propriedade nao existe"
        )
        raise _PropriedadeAlheia(
            f"propriedade_id {pid} recusado: {motivo}. Cada produtor so opera "
            "nas propriedades dele. Pedir a ligacao sem `propriedade_id` usa a "
            "propriedade principal da sua conta.",
        )

    # sem id: a primeira com proatividade ligada; sem isso, a primeira do user
    pref = ProativoPreferencia.objects.filter(user=user, ativo=True).first()
    if pref is not None:
        return pref.propriedade
    return qs.first()


class _PropriedadeAlheia(Exception):
    """O `propriedade_id` do pedido e' de outro produtor.

    Excecao e nao `None` porque `None` e' ambigo: `h_ligar_proatividade` trata
    `None` como "escolhe a primeira sua", e foi essa ambiguidade que deixou
    passar o pedido alheio. Um sinal diferente para "pedido recusado" e para
    "nao ha preferencia, escolhe uma" e' o que separa os dois casos.
    """


def h_emitir_alerta_proativo(user, params, ctx):
    """Registra um alerta proativo. Chamada pelo worker OU pelo LLM.

    Os dois caminhos usam a MESMA governança (`emitir_alerta` → `pode_emitir`).
    Um caminho com teto próprio é um caminho sem teto.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {"ok": False, "erro": "usuario obrigatorio"}

    # o user_id do modelo, se vier, é conferido — não é confiado
    cid = params.get("user_id")
    if cid is not None and str(cid).strip():
        try:
            if int(cid) != int(user.pk):
                return {
                    "ok": False,
                    "erro": (
                        f"user_id {cid} nao corresponde ao usuario em contexto. "
                        "O alerta proativo e' sempre do dono do cenario; um modelo "
                        "nao escolhe para quem e o aviso."
                    ),
                }
        except (TypeError, ValueError):
            return {"ok": False, "erro": f"user_id invalido: {cid!r}"}

    # `cenario_id` e' o parametro que o navegador manda, e ele e' MAIS FORTE que
    # `user_id`: o id aponta para uma fila que ja sabe de quem e de qual
    # fazenda e o cenario. O dono e a propriedade saem DA LINHA, nunca do
    # parametro — entao um modelo que invente o numero aponta para o cenario
    # errado e recebe "nao encontrado", e um modelo que invente a fazenda nao
    # tem onde colar o aviso, porque a fazenda nao vem dele.
    cenario = None
    cenario_id = params.get("cenario_id")
    if cenario_id is not None and str(cenario_id).strip():
        from app.models import IACenarioPendente

        cenario = IACenarioPendente.objects.filter(pk=cenario_id, user=user).first()
        if cenario is None:
            return {
                "ok": False,
                "erro": (
                    f"cenario_id {cenario_id} nao existe ou nao e seu. O alerta "
                    "proativo so vem de um cenario que o servidor montou para "
                    "voce; um id que o proprio modelo inventou nao aponta para "
                    "nada."
                ),
            }
        prop = cenario.propriedade
    else:
        # Ver `_PropriedadeAlheia`: um `propriedade_id` de outro produtor e' um
        # pedido recusado, nao "nao ha preferencia, escolhe uma". Traduzir aqui
        # e' o que impede a excepcao de chegar ao servidor como 500.
        try:
            prop = _propriedade_de(user, params)
        except _PropriedadeAlheia as e:
            return {"ok": False, "erro": str(e)}

    if prop is None:
        return {"ok": False, "erro": "nenhuma propriedade sua para receber o alerta"}

    mensagem = str(params.get("mensagem") or "").strip()
    titulo = str(params.get("titulo") or "").strip()
    if not mensagem:
        return {"ok": False, "erro": "informe 'mensagem' do alerta"}
    # sem título, o primeiro corte da mensagem vira título — a notificação do
    # celular mostra o título, e um título de 4 palavras não identifica nada
    if not titulo:
        titulo = mensagem.split(".")[0][:80] or "Alerta proativo"

    nivel = str(
        params.get("nivel_severidade") or params.get("nivel") or "atencao"
    ).lower()
    if nivel not in ("critico", "atencao", "info"):
        return {
            "ok": False,
            "erro": f"nivel {nivel!r} invalido. Use: critico, atencao ou info.",
        }

    r = emitir_alerta(
        user,
        prop,
        titulo=titulo,
        mensagem=mensagem,
        nivel=nivel,
        origem="llm",
        regra="raciocinio_llm",
        evidencia={
            "propriedade": prop.nome,
            "criterio": params.get("criterio", "")[:200]
            if params.get("criterio")
            else "",
        },
    )

    if not r["ok"]:
        # O cenario NAO e fechado aqui. Se o alerta foi barrado por teto, o
        # produtor ainda tem o cenario na fila para reavaliar amanha com o
        # orcamento refeito. Fechar aqui seria trocar "ele nao foi avisado
        # agora" por "ele nem vai ter a chance de ser avisado depois".
        return {
            "ok": False,
            "erro": f"alerta suprimido pela governanca: {r['motivo']}",
            "dados": {
                "suprimido": True,
                "fingerprint": r.get("fingerprint"),
                "cenario_id": cenario_id or None,
            },
        }

    # Agora sim: o alerta existe, e o cenario cumpriu o papel. A ordem e' alerta
    # primeiro, cenario depois — invertida, uma falha no meio deixaria o
    # produtor sem alerta e sem cenario.
    if cenario is not None:
        cenario.marcar_concluido("concluido")

    return {
        "ok": True,
        "resposta": (
            f"Alerta registrado para {prop.nome}. O produtor vera na proxima "
            "sincronizacao do app."
        ),
        "dados": {
            "alerta_id": r["alerta_id"],
            "nivel": r["nivel"],
            "propriedade": prop.nome,
            "origem": "llm",
            "cenario_id": cenario_id or None,
        },
    }


def h_ligar_proatividade(user, params, ctx):
    """Liga ou desliga o motor proativo de uma propriedade. Consentimento.

    Existe porque proatividade é um ACESSO, não um recurso. Sem o opt-in, o
    sistema avisa sozinho e o produtor não pediu — e o primeiro produtor que
    recebe um alerta que não pediu desliga as notificações, e o sistema perde
    os dois casos em que realmente importava.
    """
    from app.models import ProativoPreferencia

    try:
        prop = _propriedade_de(user, params)
    except _PropriedadeAlheia as e:
        return {"ok": False, "erro": str(e)}
    if prop is None:
        return {"ok": False, "erro": "nenhuma propriedade sua"}

    if not params.get("confirm"):
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": (
                f"Vou {'LIGAR' if params.get('ativo') else 'DESLIGAR'} o motor "
                f"proativo em {prop.nome}. Ele cruza as tarefas com a previsao e "
                "avisa antes de um risco. Desligado por padrao. Confirme com "
                "confirm=true."
            ),
            "dados": {"propriedade": prop.nome, "ativo": bool(params.get("ativo"))},
        }

    pref, _ = ProativoPreferencia.objects.get_or_create(user=user, propriedade=prop)
    pref.ativo = bool(params.get("ativo"))
    pref.save(update_fields=["ativo", "atualizado_em"])
    return {
        "ok": True,
        "resposta": f"Motor proativo {'LIGADO' if pref.ativo else 'DESLIGADO'} em {prop.nome}.",
        "dados": {"propriedade": prop.nome, "ativo": pref.ativo},
    }


def h_avaliar_cenario(user, params, ctx):
    """Roda a avaliação do cenário AGORA, sem esperar o worker.

    Serve a dois casos: o produtor quer ver "vê o que você pensaria agora" e o
    time de suporte reproduzir um alerta. É a mesma função que o worker chama —
    dois caminhos de avaliação divergindo é como o bug da previsão de 3 dias
    nasceu.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {"ok": False, "erro": "usuario obrigatorio"}
    r = avaliar_usuario(user)
    if r["alertas"] == 0 and r.get("motivo"):
        return {"ok": True, "resposta": r["motivo"], "dados": r}
    return {
        "ok": True,
        "resposta": (
            f"Avaliei suas propriedades: {r['alertas']} alerta(s) novo(s), "
            f"{r['suprimidos']} suprimido(s) pela governanca."
        ),
        "dados": r,
    }


INTENTS_PROATIVO = {
    "emitir_alerta_proativo": {
        "descricao": (
            "INSTRUÇÃO IA: use para avisar o produtor sobre um risco operacional "
            "que voce encontrou sozinho. NAO escureca valores, nao invente "
            "tarefa. A mensagem precisa dizer o que fazer, nao so o que esta "
            "errado. A governanca decide se o alerta sai: se ela disser "
            "'suprimido', NAO tente de novo."
        ),
        "exemplos": [
            "avisa que a chuva vai lavar a aplicacao",
            "alerta sobre a janela de pulverizacao",
            "avisa que a rota precisa mudar por causa da chuva",
        ],
        "params_schema": {
            "mensagem": {
                "type": "string",
                "description": "O aviso, com a sugestao de acao",
            },
            "titulo": {"type": "string", "description": "Titulo curto (opcional)"},
            "nivel_severidade": {
                "type": "string",
                "description": "critico | atencao | info",
            },
            "criterio": {
                "type": "string",
                "description": "Por que voce acha que e' risco (evidencia)",
            },
            "cenario_id": {
                "type": "integer",
                "description": (
                    "O cenario que voce recebeu para analisar. Repita o id "
                    "exatamente como veio. E' ele que diz para quem e sobre qual "
                    "fazenda o aviso e'."
                ),
            },
        },
        "flags": ["proativo.write"],
        # ESCRITA — e por isso PEDE CONFIRMACAO.
        #
        # Sem esta flag, `sandbox.py:569` nao entra: o handler corre
        # logo e grava. O gate de confianca M3 nao cobre — so avisa, e
        # so quando o cliente manda um score, o que nao e' o caso comum.
        "requires_confirmation": True,
        # Texto PARA O PRODUTOR. `texto.py:113` usa este campo e so cai
        # na descricao — que e' escrita para o MODELO — quando o vazio.
        "prompt_confirmacao": (
            "Guardar este alerta no teu painel? Fica registado ate o resolveres."
        ),
        "handler": h_emitir_alerta_proativo,
    },
    "ligar_proatividade": {
        "descricao": (
            "INSTRUÇÃO IA: use para LIGAR ou DESLIGAR o motor proativo de uma "
            "propriedade. Ele cruza as tarefas do produtor com a previsao e avisa "
            "sozinho antes de um risco. Comeca DESLIGADO por padrao — o produtor "
            "precisa autorizar."
        ),
        "exemplos": [
            "liga a antecipacao de riscos",
            "desliga os avisos automaticos",
            "quero que voce me avise antes da chuva",
        ],
        "params_schema": {
            "ativo": {"type": "boolean", "description": "true liga, false desliga"},
            "propriedade_id": {
                "type": "integer",
                "description": "Propriedade (opcional; padrao: a primeira)",
            },
            "confirm": {
                "type": "boolean",
                "description": "true apos o produtor confirmar",
            },
        },
        "flags": ["proativo.write"],
        # A PROPRIA DESCRICAO DESTE INTENT DIZ QUE O PRODUTOR PRECISA AUTORIZAR.
        # "Comeca DESLIGADO por padrao — o produtor precisa autorizar." E o gate
        # era o que autorizava. Sem ele, o motor liga-se e comeca a mandar
        # avisos sozinho — que e' exactamente o que a descricao promete que
        # nao aconteca.
        #
        # E' o accumulativo mais consequente dos quatro: ligado, este intent
        # poe `emitir_alerta_proativo` a correr em ciclo. Cada execucao e' um
        # alerta que o produtor ve sem ter pedido. Nao ha rollback, e o custo
        # e' o painel inteiro: o produtor ve tres alertas, depois cinco, e
        # deixa de os ler. O alerta a que se acostuma a ignorar e' o que
        # custa a proxima lavra.
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou LIGAR o motor proativo. A partir de agora ele cruza as suas "
            "tarefas com a previsao e manda avisos sozinho, sem eu perguntar. "
            "Confirmar?"
        ),
        "handler": h_ligar_proatividade,
    },
    "avaliar_cenario": {
        "descricao": (
            "INSTRUÇÃO IA: use para rodar AGORA o que o motor proativo faria. "
            "Retorna quantos alertas sairam e quantos a governanca suprimiu."
        ),
        "exemplos": [
            "o que voce acharia de errado agora",
            "roda a antecipacao de riscos",
            "verifica se ha risco no meu calendario",
        ],
        "params_schema": {},
        "flags": ["proativo.read"],
        "handler": h_avaliar_cenario,
    },
}
