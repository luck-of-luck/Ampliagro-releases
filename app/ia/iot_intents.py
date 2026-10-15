"""
iot_intents.py — as tools da Ponte IoT (BUILD 4).

Duas tools:

    provisionar_endpoint_iot  gera credencial + tópico + escopo C++
    revogar_endpoint_iot      corta o acesso

O PRODUTOR não é programador, mas programa. A resposta da provisionação é o
"escopo técnico" pronto — o JSON com o tópico, o token e o C++ do ESP32 já
preenchido — porque pedir que alguém copie `{TOKEN}` de um e-mail para dentro de
uma string C++ é pedir erro de aspas.

O token é devolvido UMA vez, e a própria resposta avisa que ele foi entregue à
conversa. Não é cuidado vazio: se a conversa for compartilhada com o contador,
o token está na tela do contador. Por isso o `aviso` é parte do payload, e não
uma nota no rodapé.
"""

from __future__ import annotations

from typing import Any

from app.ia.dinamicos import ErroDinamico, resolver_app
from app.ia.iot import provisionar, revogar
from app.models import IotEndpoint


def _endpoint_do_usuario(user, param_id):
    """Resolve o endpoint SEMPRE escopado no dono.

    Mesmo `resolver_app` do BUILD 2: filtro sem `user` devolve o endpoint de
    outro produtor, e revogar o endpoint alheio é Denial of Service em cima de
    máquina de outro.
    """
    ep = IotEndpoint.objects.filter(user=user, pk=param_id).first()
    if ep is None:
        raise ErroDinamico("endpoint nao encontrado entre os seus")
    return ep


def h_provisionar_endpoint_iot(user, params, ctx):
    """Cria a credencial de um dispositivo e entrega o escopo técnico.

    ESCRITA, e por isso pede confirmação: provisionar é criar acesso. A
    confirmação aqui tem peso maior que nas outras tools — o que está em jogo
    é quem mais pode publicar dados nesta conta, e o produtor precisa ver o que
    está Naming antes de autorizar.
    """
    slug = str(params.get("entity_slug") or params.get("slug") or "").strip()
    if not slug:
        return {
            "ok": False,
            "erro": "informe 'entity_slug' (o slug da ferramenta que voce criou)",
        }

    app = resolver_app(user, slug)
    if app is None:
        return {
            "ok": False,
            "erro": f"ferramenta {slug!r} nao encontrada entre as suas",
        }

    nome = str(params.get("nome") or params.get("device_nome") or "").strip()
    if not nome:
        return {
            "ok": False,
            "erro": "informe 'nome' do dispositivo. Ex: nome='Valvula do talhao 4'",
        }

    campo = str(params.get("campo_destino") or "").strip()
    if not campo:
        campos = (
            ", ".join(c.chave for c in app.dynamic_fields.filter(ativo=True))
            or "(nenhum)"
        )
        return {
            "ok": False,
            "erro": (
                "informe 'campo_destino': qual chave do schema recebe a leitura do "
                f"dispositivo. Campos desta ferramenta: {campos}"
            ),
        }

    if not params.get("confirm"):
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": (
                f'Vou criar o endpoint IoT "{nome}" para a ferramenta "{app.nome}", '
                f"escrevendo em '{campo}'. Isso gera uma credencial que qualquer "
                "possua pode usar para publicar nesta conta. Confirme com "
                "confirm=true."
            ),
            "dados": {
                "entity_slug": app.slug,
                "nome": nome,
                "campo_destino": campo,
            },
        }

    try:
        resultado = provisionar(user, app, nome=nome, campo_destino=campo)
    except ErroDinamico as e:
        return {"ok": False, "erro": str(e)}

    ep = resultado["endpoint"]
    escopo = resultado["escopo"]

    return {
        "ok": True,
        "resposta": (
            f'Endpoint "{ep.nome}" criado em {app.nome}.\n'
            f"Topico MQTT: {ep.topico}\n"
            f"Token (so aparece agora): {resultado['token']}\n\n"
            "Le a leitura no campo: " + ep.campo_destino + "\n"
            f"Codigo C++ pronto (copie para o firmware):\n{escopo['cpp_esp32']}\n\n"
            "AVISO: o token foi entregue nesta conversa e nao pode ser recuperado "
            "depois. Se esta conversa for compartilhada, revogue o endpoint e "
            "provisione outro. Para recuperar o codigo depois, use "
            "consultar_endpoints_iot."
        ),
        "dados": {
            "endpoint_id": ep.pk,
            "entity_slug": app.slug,
            "topico": ep.topico,
            "campo_destino": ep.campo_destino,
            "token_prefixo": ep.token_prefixo,
            "escopo_tecnico": escopo,
        },
    }


def h_revogar_endpoint_iot(user, params, ctx):
    """Corta o acesso do dispositivo. Idempotente.

    Confirma porque revogar derruba a telemetria de uma máquina de campo — e o
    produtor precisa saber que vai ficar sem dado até reprovisionar.
    """
    ep_id = params.get("endpoint_id") or params.get("id")
    if not ep_id:
        return {
            "ok": False,
            "erro": "informe 'endpoint_id'. Use consultar_endpoints_iot para ver os seus.",
        }

    try:
        ep = _endpoint_do_usuario(user, ep_id)
    except ErroDinamico as e:
        return {"ok": False, "erro": str(e)}

    if not params.get("confirm"):
        return {
            "ok": True,
            "needs_confirm": True,
            "resposta": (
                f'Vou revogar o endpoint "{ep.nome}" ({ep.topico}). O dispositivo '
                "para de publicar e a telemetria dele para de chegar. Confirme "
                "com confirm=true."
            ),
            "dados": {"endpoint_id": ep.pk},
        }

    mudou = revogar(user, ep)
    return {
        "ok": True,
        "resposta": (
            f'Endpoint "{ep.nome}" revogado.'
            if mudou
            else f'Endpoint "{ep.nome}" ja estava revogado.'
        ),
        "dados": {"endpoint_id": ep.pk, "estado": "REVOGADO", "mudou": mudou},
    }


def h_consultar_endpoints_iot(user, params, ctx):
    """Lista os endpoints do produtor. SEM token — só prefixo.

    Leitura pura: não pede confirmação, e é o que o produtor chama quando quer
    "qual era o tópico da minha válvula?".
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return {"ok": False, "erro": "usuario obrigatorio"}

    slug = str(params.get("entity_slug") or "").strip()
    qs = IotEndpoint.objects.filter(user=user).select_related("app")
    if slug:
        app = resolver_app(user, slug)
        if app is None:
            return {"ok": False, "erro": f"ferramenta {slug!r} nao encontrada"}
        qs = qs.filter(app=app)

    lista = list(qs.order_by("-criado_em")[:50])
    if not lista:
        return {
            "ok": True,
            "resposta": (
                "Voce ainda nao tem endpoint IoT. Use provisionar_endpoint_iot "
                "após criar a ferramenta dinamica."
            ),
            "dados": {"total": 0},
        }

    linhas = []
    for ep in lista:
        linhas.append(
            f"#{ep.pk} {ep.nome} | {ep.app.slug} | {ep.estado} | "
            f"topico={ep.topico} | token={ep.token_prefixo}… | "
            f"campo={ep.campo_destino} | eventos={ep.total_eventos}"
        )
    return {
        "ok": True,
        "resposta": f"{len(lista)} endpoint(s):\n" + "\n".join(linhas),
        "dados": {
            "total": len(lista),
            "endpoints": [e.como_descrever() for e in lista],
        },
    }


INTENTS_IOT = {
    "provisionar_endpoint_iot": {
        "descricao": (
            "INSTRUÇÃO IA: use quando o produtor quiser conectar uma placa fisica "
            "(ESP32, Arduino, LoRa) a uma ferramenta que ele criou. Gera uma "
            "credencial revogavel, o topico MQTT e devolve o codigo C++ pronto. "
            "Informe: entity_slug, nome, campo_destino (qual chave do schema "
            "recebe a leitura). AVISO ao produtor: o token aparece so nesta "
            "resposta."
        ),
        "exemplos": [
            "conecta uma placa na valvula de irrigacao",
            "cria o endpoint iot pro controle de temperatura",
            "quero ligar o esp32 nesse app que criei",
            "provisiona o dispositivo do talhao 4",
        ],
        "params_schema": {
            "entity_slug": {
                "type": "string",
                "description": "Slug da ferramenta dinamica",
            },
            "nome": {"type": "string", "description": "Nome do dispositivo"},
            "campo_destino": {
                "type": "string",
                "description": "Chave do schema que recebe a leitura do dispositivo",
            },
            "confirm": {
                "type": "boolean",
                "description": "true apos o produtor confirmar",
            },
        },
        "flags": ["iot.write"],
        # ESTE INTENT ESCREVE FORA DA FAZENDA, E O QUE ELE FAZ NAO SE DESFAZ.
        #
        # `provisionar_endpoint_iot` cria uma CREDENCIAL e devolve um token que
        # so aparece nesta resposta. Um alvo errado nao e' um registo errado que
        # se apaga: e' uma placa que fica a reportar para a conta errada — e
        # continua, em silêncio, ate alguem reparar. O produtor nao tem nenhuma
        # forma de saber, porque do ponto de vista dele o sistema funciona.
        #
        # A razao de o gate ser aqui e nao no handler: o `sandbox.py` so pede
        # confirmacao por CONFIANCA baixa (`_exige_confianca`, sandbox.py:576).
        # Confianca alta e' o caso comum, e nesse caso o intent executava no
        # escuro. Confianca e' "a IA entendeu bem?"; isto e' "o efeito e'
        # reversivel?", e so o registo responde a segunda.
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou criar uma credencial de telemetria e mostrar o token. A placa "
            "começa a reportar para este dispositivo imediatamente. "
            "Confirmar?"
        ),
        "handler": h_provisionar_endpoint_iot,
    },
    "revogar_endpoint_iot": {
        "descricao": (
            "INSTRUÇÃO IA: use para CORTAR o acesso de um dispositivo. O token "
            "morre e a telemetria para. Use quando o produtor vender a placa, "
            "perder o aparelho, ou desconfiar do acesso. Informe endpoint_id."
        ),
        "exemplos": [
            "desconecta a placa da valvula",
            "revoga o acesso do esp32",
            "vendi o sensor, corta o acesso",
        ],
        "params_schema": {
            "endpoint_id": {"type": "integer", "description": "Id do endpoint"},
            "confirm": {
                "type": "boolean",
                "description": "true apos o produtor confirmar",
            },
        },
        "flags": ["iot.write"],
        # O MESMO RAZAO DO `provisionar_endpoint_iot`, pelo outro lado.
        #
        # Este CORTA o acesso. Errou o alvo e' um sensor que cala sem deixar
        # rasto: o painel deixa de receber leituras e ninguem sabe se o
        # aparelho avariou, se a rede caiu ou se foi a IA. O produtor perde o
        # dado E o diagnostico — que e' pior do que o produto criar uma placa
        # a mais.
        #
        # E note-se a assimetria com a Confidence gate do `sandbox.py`: esta
        # e' uma operacao que o produtor pediu DE PROPOSITO ("vendi o sensor,
        # corta o acesso"), o que significa que a confianca tende a ser alta.
        # E' exactamente o caso em que a confidence gate nao dispara.
        "requires_confirmation": True,
        "prompt_confirmacao": (
            "Vou REVOGAR o acesso deste dispositivo. A telemetria para de "
            "chegar e o token morre. Confirmar? (Se o alvo estiver errado, a "
            "placa continua viva e ninguem descobre porque parou.)"
        ),
        "handler": h_revogar_endpoint_iot,
    },
    "consultar_endpoints_iot": {
        "descricao": (
            "INSTRUÇÃO IA: use para LISTAR os dispositivos conectados as suas "
            "ferramentas. Devolve topico, prefixo do token e quantos eventos "
            "chegaram. NUNCA devolve o token completo."
        ),
        "exemplos": [
            "quais placas estao conectadas",
            "lista os dispositivos iot",
            "qual o topico da minha valvula",
            "quantos eventos chegaram do esp32",
        ],
        "params_schema": {
            "entity_slug": {
                "type": "string",
                "description": "Filtra por ferramenta (opcional)",
            }
        },
        "flags": ["iot.read"],
        "handler": h_consultar_endpoints_iot,
    },
}
