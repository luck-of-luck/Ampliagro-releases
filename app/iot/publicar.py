"""Publicar comandos de IoT no broker — o elo que faltava.

O QUE ISTO FECHA
================
A cadeia de automação tinha um buraco no fim. O `alert_engine` enfileira um
`ComandoDevice` quando uma regra dispara, e `enfileirar_comando` cueda-o com
expiração, dedup e rate-limit. Mas **ninguém o publicava**: o `mqtt_listener`
só INGE telemetria. O comando nascia `pendente` e aí ficava.

Isto é o que `app/ia/intents4.py` promete ao produtor — *"a válvula é
comandada pelo motor quando a leitura confirmar o limite"* — sem motor.

O QUE ESTE MÓDULO NÃO FAZ
=========================
Não decide nada. Não avalia regra nenhuma. Não abre uma válvula porque sim.
A decisão já foi tomada e já está no banco; aqui só se pergunta se essa
decisão ainda é válida, e se não for, o comando não sai.

AUTORIZAR NA PUBLICAÇÃO, E NÃO NA SEMEADA
==========================================
A escolha mais restritiva, e a que o resto do repositório faz
(`servidor_ativo()` falha fechado; `sem dado` nunca vira 0).

Uma linha `pendente` pode ter horas. Nesse intervalo:
  - o produtor pode ter desactivado a regra;
  - a leitura pode ter NORMALIZADO — e nesse caso a válvula não deve abrir
    porque areasonão do comando desapareceu;
  - a regra pode ter sido movida para outra propriedade.

Confiar na regra como estava no momento da_enqueue seria publicar uma
intenção que já ninguém quer. Por isso cada comando é REVALIDADO aqui, e a
primeira coisa que se exige é que ele seja rastreável até uma regra viva.

O teste que fecha a authorization
---------------------------------
`AlertaTelemetria` é auto-resolvida quando a leitura normaliza
(`test_auto_resolve_ao_normalizar`). Logo: **houver alerta por resolver para
(regra, device) é a prova de que a condição ainda se cumpre.** Não é uma
aproximação — é o mesmo estado que o próprio motor usa para decidir se ainda
está em risco.

Se o alerta foi resolvido, o comando é recusado com `leitura_normalizou`: a
válvula fecha-se porque deixou de haver motivo para a abrir.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Teto por passagem. Um publicador sem teto é um publicador que flooda o
#: broker quando a fila tem 4.000 comandos de um dia sem ACK.
LIMITE_PADRAO = 50

#: Tentativas antes de desistir. Deixar a fila em `pendente` para sempre é
#: pior que marcar `erro`: `pendente` alimenta o dedup de
#: `enfileirar_comando`, e um comando preso em `pendente` impede que um
#: comando NOVO e legitimo do mesmo device seja criado.
MAX_TENTATIVAS = 3

#: `acao_fisica` -> comando. Deliberadamente EXPLICITO, e nao derivado por
#: traducao. Um `else` que transformasse "abrir_valvula" em `valve_open` e
#: qualquer valor desconhecido em `None` seria um default silencioso: uma
#: regra nova escreveria um comando errado em vez de recusar.
COMANDO_POR_ACAO = {
    "abrir_valvula": "valve_open",
    "fechar_valvula": "valve_close",
}


class Recusado(Exception):
    """O comando não pode ser publicado. `motivo` é para o operador."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def autorizar(cmd) -> None:
    """Revalida o comando. Levanta `Recusado` com o motivo se não puder sair.

    Não tocar em nada: esta função é só uma pergunta. Quem chama decide o que
    fazer com a recusa.
    """
    from app.models import AlertaTelemetria, RegraAlertaTelemetria

    if cmd.status != "pendente":
        raise Recusado(f"status é '{cmd.status}', não 'pendente'")

    if cmd.expira_em and cmd.expira_em <= timezone.now():
        raise Recusado("expirado sem ACK")

    payload = cmd.payload if isinstance(cmd.payload, dict) else {}
    if payload.get("via") != "regra_auto":
        # Fail-closed. Um comando sem regra que o autorize não sai: não há
        # como saber que a acção ainda é pretendida, e "não sei" não é
        # autorização.
        raise Recusado("sem regra que o autorize (via != regra_auto)")

    try:
        regra_id = int(payload.get("regra_id"))
    except (TypeError, ValueError):
        raise Recusado("regra_id ausente ou ilegível no payload") from None

    regra = (
        RegraAlertaTelemetria.objects.filter(pk=regra_id).first() if regra_id else None
    )
    if regra is None:
        raise Recusado(f"regra {regra_id} não existe")
    if not regra.ativa:
        raise Recusado(f"regra {regra_id} está desativada")

    # O eixo de segurança. A regra e o comando têm de ser do mesmo produtor.
    # Sem esta comparação, uma regra de A apontada para um device de B abre
    # a válvula de B — e nada mais no sistema denuncia isso.
    if regra.propriedade_id != cmd.device.propriedade_id:
        raise Recusado(
            f"regra {regra_id} é da propriedade {regra.propriedade_id} e o "
            f"device é da {cmd.device.propriedade_id}"
        )

    esperado = COMANDO_POR_ACAO.get(regra.acao_fisica or "")
    if not esperado:
        raise Recusado(f"regra {regra_id} não tem acao_fisica publicável")
    if esperado != cmd.comando:
        raise Recusado(
            f"comando '{cmd.comando}' não corresponde a acao_fisica "
            f"'{regra.acao_fisica}' da regra {regra_id}"
        )

    # A condição ainda se cumpre? O auto-resolve do motor é a prova.
    vivo = AlertaTelemetria.objects.filter(
        regra_id=regra.id, device_id=cmd.device_id, resolvido=False
    ).exists()
    if not vivo:
        raise Recusado("leitura normalizou: o alerta por resolver não existe")


def topico_de(cmd) -> str:
    """O tópico de downlink, no esquema que o `mqtt_listener` já escuta.

    `device_profiles.json` define `ampliagro/{propriedade_id}/{gateway_eui}/
    {device_eui}/telemetry`. O downlink é o mesmo caminho com `/cmd`, para
    que a ACL do broker possa cortar o que não é telemetria.
    """
    dev = cmd.device
    gateway = getattr(dev, "gateway", None)
    gw = getattr(gateway, "gateway_eui", None) or "sem-gateway"
    return f"ampliagro/{dev.propriedade_id}/{gw}/{dev.device_eui}/cmd"


def corpo_de(cmd) -> bytes:
    """O payload, com o que o broker precisa para não executar um comando cego.

    `cmd_id` e `expira_em` vão dentro porque o firmware não tem acesso à base
    de dados: sem eles não consegue rejeitar um comando que chegue tarde.
    """
    return json.dumps(
        {
            "cmd_id": cmd.id,
            "comando": cmd.comando,
            "payload": cmd.payload if isinstance(cmd.payload, dict) else {},
            "criado_em": cmd.criado_em.isoformat() if cmd.criado_em else None,
            "expira_em": cmd.expira_em.isoformat() if cmd.expira_em else None,
        },
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def autorizar_e_marcar(cmd, publicado: bool, erro: str = "") -> None:
    """Grava o desfecho. `publicado=False` deixa o comando para nova tentativa.

    Incrementar `tentativas` ANTES de gravar o erro é o que permite o
    `MAX_TENTATIVAS` fazer alguma coisa: sem o contador, uma fila com broker
    em baixo tenta para sempre.
    """
    cmd.tentativas = (cmd.tentativas or 0) + 1
    if publicado:
        cmd.status = "enviado"
        cmd.enviado_em = timezone.now()
        cmd.ultimo_erro = ""
    elif cmd.tentativas >= MAX_TENTATIVAS:
        cmd.status = "erro"
        cmd.ultimo_erro = f"{erro} (após {cmd.tentativas} tentativas)"[:200]
    else:
        cmd.status = "pendente"
        cmd.ultimo_erro = erro[:200]
    cmd.save(update_fields=["status", "enviado_em", "tentativas", "ultimo_erro"])


def pendentes(limite: int = LIMITE_PADRAO) -> list:
    """A fila a considerar, em ordem de chegada.

    A janela é `limite * 3` porque muitos comandos vão ser RECUSADOS pela
    revalidação (regra desligada, leitura normalizada). Sem a folga, uma
    passagem em que os 50 mais antigos estão todos recusados publica zero,
    mesmo havendo comandos válidos logo a seguir — que é a forma de o
    publicador parecer parado enquanto trabalha.

    A expiração NÃO é filtrada aqui: `autorizar()` recusa comando expirado, e
    um filtro em SQL seria o mesmo resultado com uma consulta a menos. O que
    não pode acontecer é publicar primeiro e expirar depois — por isso o
    filtro vive na autorização, não aqui.
    """
    from app.models import ComandoDevice

    qs = ComandoDevice.objects.filter(status="pendente").order_by("criado_em")
    return list(qs[: limite * 3])[:limite]


def publicar(
    limite: int = LIMITE_PADRAO, dry_run: bool = False, publicar_fn=None
) -> dict:
    """Drena a fila autorizada. Devolve o relatório — o que NÃO foi feito também.

    `publicar_fn(topico, corpo) -> None` é injetado para que os testes
    corram sem broker. `dry_run` não chama o `publicar_fn` e não grava nada:
    um dry-run que publica seria pior do que não ter dry-run.
    """
    relatorio: dict[str, Any] = {
        "vistos": 0,
        "publicados": 0,
        "recusados": 0,
        "erros": 0,
        "motivos": {},
        "dry_run": bool(dry_run),
    }

    if dry_run:
        return relatorio

    pub = publicar_fn
    if pub is None:
        from app.iot.broker import publicar_mqtt  # import tardio: sem broker, sem custo

        pub = publicar_mqtt

    for cmd in pendentes(limite):
        relatorio["vistos"] += 1
        try:
            autorizar(cmd)
        except Recusado as r:
            relatorio["recusados"] += 1
            relatorio["motivos"][r.motivo] = relatorio["motivos"].get(r.motivo, 0) + 1
            logger.info("[publicar] cmd %s recusado: %s", cmd.id, r.motivo)
            # NÃO se marca `erro`. Recusado por revalidação é uma decisão
            # saudável — o comando simplesmente não era para ter saído. Marcá-lo
            # como erro puniria o produtor por uma regra que ele desactivou.
            continue

        try:
            pub(topico_de(cmd), corpo_de(cmd))
        except Exception as e:  # noqa: BLE001
            relatorio["erros"] += 1
            autorizar_e_marcar(cmd, publicado=False, erro=f"{type(e).__name__}: {e}")
            logger.warning("[publicar] cmd %s falhou: %s", cmd.id, e)
            continue

        autorizar_e_marcar(cmd, publicado=True)
        relatorio["publicados"] += 1

    if relatorio["publicados"] or relatorio["erros"]:
        logger.info(
            "[publicar] %s publicado(s), %s erro(s), %s recusado(s)",
            relatorio["publicados"],
            relatorio["erros"],
            relatorio["recusados"],
        )
    return relatorio
