"""O transporte: publicar um comando num broker MQTT.

Isolado em `broker.py` para que `publicar.py` possa ser testado sem rede, sem
broker e sem `paho-mqtt` instalado. A regra do repo é a mesma do
`mqtt_listener`: o caminho MQTT é opcional, e a ausência da biblioteca é uma
decisão — nunca um `except: pass`.

CONFIGURAÇÃO (por ambiente, não por código)
===========================================
  AMPLIA_MQTT_BROKER      host do broker          (obrigatório)
  AMPLIA_MQTT_PORT        porta, omissível → 8883 quando há TLS, 1883 sem
  AMPLIA_MQTT_USER        utilizador
  AMPLIA_MQTT_PASS        palavra-passe
  AMPLIA_MQTT_TLS         "1" liga TLS
  AMPLIA_MQTT_PERMITIR_SEM_TLS
                          "1" desliga a recusa de plaintext (ver abaixo)

SEM TLS, O PUBLISHER RECUSA
===========================
Um downlink em claro é legível por qualquer coisa na mesma rede — e o que
circula é `valve_open`. Numa fazenda, a rede é a sala, o seeding e o wifi do
casa. Publicar a comando de irrigação sem cifrar é dar a qualquer portátil
ligado a capacidade de abrir a água de outra propriedade.

Por isso TLS é a EXCEÇÃO que precisa de ser pedida, e não o omissível:
sem `AMPLIA_MQTT_TLS=1` o publisher não publica e diz porquê. Quem
deliberadamente opera uma rede local isolada escreve
`AMPLIA_MQTT_PERMITIR_SEM_TLS=1` e fica com isso escrito no seu deploy.

Uma excepção há, e é deliberada: a telemetria INGRESS (`mqtt_listener`) segue
em claro quando o broker é local. Isso é leitura, não acção — não se deflectua
uma máquina a partir de uma leitura.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

#: Comandos que movem água ou outro recurso. Exigem TLS.
COMANDOS_FISICOS = ("valve_open", "valve_close")


class BrokerNaoConfigurado(RuntimeError):
    """Não há broker configurado. Não se publica nada, e diz-se porquê."""


def _flag(nome: str) -> bool:
    return os.environ.get(nome, "").strip().lower() in ("1", "true", "yes", "sim")


def config() -> dict:
    """Lê a configuração do broker. Levanta se estiver incompleta.

    Não tem default para o host. Um `localhost` inventado seria um publisher
    que "funciona" contra um broker de desenvolvimento e falha em produção
    com um erro de conexão que não diz qual dos dois falta.
    """
    host = os.environ.get("AMPLIA_MQTT_BROKER", "").strip()
    if not host:
        raise BrokerNaoConfigurado(
            "AMPLIA_MQTT_BROKER não está definido. Nada foi publicado: um "
            "publisher com broker inventado liga-se ao sítio errado e falha "
            "com um erro que não diz qual configuração falta."
        )
    tls = _flag("AMPLIA_MQTT_TLS")
    porta = os.environ.get("AMPLIA_MQTT_PORT", "").strip()
    return {
        "host": host,
        "porta": int(porta) if porta else (8883 if tls else 1883),
        "tls": tls,
        "user": os.environ.get("AMPLIA_MQTT_USER", "").strip() or None,
        "pass": os.environ.get("AMPLIA_MQTT_PASS", "") or None,
    }


def exigir_tls(comando: str) -> None:
    """Recusa plaintext para comando físico, a não ser que se peça explicitamente."""
    if comando not in COMANDOS_FISICOS:
        return
    if _flag("AMPLIA_MQTT_TLS"):
        return
    if _flag("AMPLIA_MQTT_PERMITIR_SEM_TLS"):
        logger.warning(
            "[broker] '%s' vai em TEXTO SIMPLES: AMPLIA_MQTT_PERMITIR_SEM_TLS=1. "
            "Qualquer coisa na mesma rede pode ler o comando e repeti-lo.",
            comando,
        )
        return
    raise BrokerNaoConfigurado(
        f"'{comando}' move recurso físico e não é publicado sem TLS. Defina "
        "AMPLIA_MQTT_TLS=1, ou — se a rede for deliberadamente isolada — "
        "AMPLIA_MQTT_PERMITIR_SEM_TLS=1 para assumir o risco à vista."
    )


def publicar_mqtt(topico: str, corpo: bytes, comando: str = "") -> None:
    """Publica um downlink. Levanta em qualquer falha — o caller decide.

    Uma função que engole a falha e devolve `None` é pior do que não existir:
    o caller marcaria o comando como `enviado` e ele nunca saiu. Aqui a falha
    SOBE, e `publicar()` grava-a em `ultimo_erro` e deixa o comando na fila.
    """
    import json

    if not comando:
        # Só para a mensagem de erro ser legível; o corpo já vai inteiro.
        try:
            comando = str(json.loads(corpo.decode("utf-8")).get("comando") or "")
        except (ValueError, UnicodeDecodeError):
            comando = ""

    exigir_tls(comando)
    cfg = config()

    try:
        import paho.mqtt.client as mqtt
    except ImportError as e:
        raise BrokerNaoConfigurado(
            "falta a biblioteca 'paho-mqtt'. Está em requirements.txt "
            f"({e}). Sem ela não há publicação; a telemetria por webhook "
            "continua a funcionar e não depende disto."
        ) from e

    # `CallbackAPIVersion.VERSION2` e' o mesmo que o `mqtt_listener` usa
    # (linha 193). `requirements.txt` traz `paho-mqtt>=2.0,<3.0`, e na 2.x a
    # construcao antiga emite `DeprecationWarning` e deixa de ser suportada —
    # um publisher que avisa em cada chamada e um listener que avisa em cada
    # mensagem sao os dois ruido que faz ninguem ler os avisos.
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv311)
    if cfg["user"]:
        client.username_pw_set(cfg["user"], cfg["pass"])
    if cfg["tls"]:
        client.tls_set()

    # `connect` + `publish` com `wait_for_publish` dá um erro de conexão no
    # ponto certo. Sem o `wait_for_publish`, `publish()` devolvia "ok" para
    # uma mensagem que ia morrer na fila do broker — e o comando ficava
    # `enviado` sem nunca ter saído da máquina.
    client.connect(cfg["host"], cfg["porta"], keepalive=30)
    client.loop_start()
    try:
        info = client.publish(topico, corpo, qos=1)
        info.wait_for_publish(timeout=10)
        if getattr(info, "rc", 0) != 0:
            raise RuntimeError(f"broker recusou a publicação (rc={info.rc})")
    finally:
        client.loop_stop()
        client.disconnect()
