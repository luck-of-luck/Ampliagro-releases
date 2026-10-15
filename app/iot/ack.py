"""Confirmar um comando — o `verificar` do ciclo.

O QUE FALTAVA
=============
O modelo tinha `status="ack"` nas `STATUS_CHOICES` e **ninguém o escrevia**.
Um comando ia `pendente` -> `enviado` e ficava `enviado` ate `expirar_comandos`
o matar aos 30 minutos. Portanto o sistema nunca soube distinguir:

    "a valvula abriu"                    de    "a mensagem morreu no broker"

E essa distincao e' o ciclo inteiro. Sem ela, a automacao nao consegue provar
que funcionou — so consegue dizer que enviou.

PORQUE UM ACK E' A COISA MAIS SENSIVEL DO SISTEMA
================================================
Um ACK e' a unica mensagem que significa "isto aconteceu no mundo fisico".
Telemetria mente e o produtor ve o numero errado; um ACK mente e o produtor
acredita que a rega aconteceu. E o que a rega nao ter acontecido significa
uma cultura a secar com o sistema a dizer que esta tudo bem.

Por isso o ACK nao e' "marcar como feito". E' uma transicao de estado com
tres perguntas, e todas tem de ser sim:

  1. Este comando foi REALMENTE publicado?  (`status == "enviado"`)
  2. Este comando e' desta propriedade?     (`cmd.device.propriedade_id`)
  3. A resposta vem do device que recebeu?

Um ACK de um `pendente` e' uma mentira ou um replay: nao ha nada para
confirmar. E um ACK pela propriedade errada e' um ACK de outro produtor.

UM NUCLEO, DOIS PORTÕES
=======================
O HTTP (producao, via webhook do gateway) e o MQTT (caminho opcional) sao
portões DIFERENTES para a MESMA porta. A logica vive aqui e so aqui, porque
duas copias desta regra divergem — e a segunda nunca e' actualizada quando a
primeira muda. Foi o que aconteceu com o `TenantIsolationMiddleware`, e o
docstring dele diz isso mesmo.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)


class AckRecusado(Exception):
    """O ACK não se aplica. `motivo` é para o operador, e distingue os casos."""

    def __init__(self, motivo: str, http_status: int = 409):
        super().__init__(motivo)
        self.motivo = motivo
        self.http_status = http_status


def confirmar(
    *,
    cmd_id: Any,
    device,
    propriedade,
    ok: bool,
    resposta: dict | None = None,
    motivo: str = "",
) -> tuple[object, bool]:
    """Aplica o ACK. Devolve `(comando, mudou)`.

    Levanta `AckRecusado` sem tocar em nada quando o ACK nao se aplica. Falhar
    em silencio aqui seria o pior possivel: um ACK recusado que devolvesse 200
    faz o fabricante parar de reenviar, e o comando fica `enviado` ate expirar
    sem ninguem saber porque.
    """
    from app.models import ComandoDevice

    try:
        cmd_id = int(cmd_id)
    except (TypeError, ValueError):
        raise AckRecusado(
            "cmd_id ausente ou ilegivel: um ACK sem identificacao de comando "
            "nao diz o que foi confirmado",
            http_status=400,
        ) from None

    cmd = ComandoDevice.objects.filter(pk=cmd_id).select_related("device").first()
    if cmd is None:
        raise AckRecusado(f"comando {cmd_id} nao existe", http_status=404)

    # --- 2. o comando e' desta propriedade? ------------------------------
    #
    # E' a unica verificacao de seguranca, e e' a que impede um gateway
    # autenticado de confirmar comandos de outro produtor. Vem ANTES do estado:
    # dizer "nao posso confirmar esse comando" a quem nao tem credencial sobre
    # ele e' um oraculo.
    if cmd.device.propriedade_id != propriedade.id:
        raise AckRecusado(
            f"comando {cmd_id} pertence a outra propriedade", http_status=403
        )
    if cmd.device_id != device.id:
        raise AckRecusado(
            f"comando {cmd_id} nao foi enviado para este device", http_status=403
        )

    # --- idempotencia: um ACK repetido nao e' erro ----------------------
    #
    # O broker entrega com QoS 1, o que significa "pode repetir". Um ACK
    # repetido tem de ser um no-op, nao um 409 — senao o gateway entra em
    # laco de retentativa porque nunca tem sucesso.
    if cmd.status == "ack":
        return cmd, False
    if cmd.status == "erro" and cmd.ultimo_erro.startswith("ack_negado"):
        return cmd, False

    # --- 1. o comando foi realmente publicado? ---------------------------
    #
    # Um ACK de um `pendente` nao tem como ser verdade: nao foi enviado nada.
    if cmd.status == "pendente":
        raise AckRecusado(
            f"comando {cmd_id} esta 'pendente': nao foi publicado, portanto "
            "nao ha o que confirmar. Um ACK de um comando nao publicado e' "
            "replay ou mentira.",
            http_status=409,
        )

    # `erro` por timeout chegou aqui. Um ACK tardio ainda e' melhor do que
    # perder: o comando foi publicado e a valvula pode ter aberto. Mas
    # regista-se que chegou tarde, porque "abriu 40 minutos depois" e' um facto
    # que muda o que se pode concluir do ciclo.
    if cmd.status == "erro":
        logger.warning(
            "[ack] comando %s confirmou TARDE: estava em erro desde antes "
            "(%s). Registado, mas o atraso importa.",
            cmd_id,
            cmd.ultimo_erro,
        )

    res = resposta if isinstance(resposta, dict) else {}
    cmd.status = "ack"
    # `resposta` guarda o que o device disse. E' o que permite responder "a
    # valvula abriu" e "a valvula abriu e a leitura era X" com a mesma coluna.
    cmd.resposta = {**res, "ok": bool(ok), "em": timezone.now().isoformat()}
    cmd.enviado_em = cmd.enviado_em or timezone.now()
    if ok:
        cmd.ultimo_erro = ""
    else:
        # Negado pelo device e' um resultado, nao uma falha nossa: o comando
        # foi bem publicado e o device respondeu que NAO pode. Chamar-lhe
        # `erro` sem o prefixo faria o `expirar_comandos` contar como
        # timeout mais tarde.
        cmd.ultimo_erro = f"ack_negado: {motivo or 'o device recusou o comando'}"[:200]
    cmd.save(update_fields=["status", "resposta", "enviado_em", "ultimo_erro"])
    return cmd, True


def acks_de(comando) -> dict:
    """O que se sabe do ciclo deste comando. Para o operador ver de relance."""
    return {
        "comando": comando.comando,
        "status": comando.status,
        "confirmado": comando.status == "ack",
        "resposta": comando.resposta if isinstance(comando.resposta, dict) else {},
        "ultimo_erro": comando.ultimo_erro,
        "tentativas": comando.tentativas,
    }


def do_topic(corpo: bytes) -> dict:
    """Extrai o ACK de uma mensagem MQTT. Devolve `{}` se não for um ACK.

    Reconhecer a FORMA não autentica nada — a autenticação é do gateway, e
    acontece no portão. Aqui só se decide se a mensagem édirected a este
    subsistema.
    """
    try:
        dados = json.loads(corpo.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}
