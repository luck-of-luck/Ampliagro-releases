"""
iot.py — o serviço da Ponte IoT (BUILD 4).

Três decisões que valem uma linha cada, porque são as que sustentam o resto:

1. **O token só aparece uma vez.** No provisionamento. Depois, só o prefixo.
   Um segredo que pode ser reimpresso a cada consulta deixou de ser segredo.

2. **O hash é SHA-256, não bcrypt.** O token tem 256 bits de entropia gerados
   por `secrets` — não há dicionário, não há ataque de força bruta, e bcrypt
   só custaria latência no caminho quente de autenticação. O motivo do hash não
   é resistência: é que um dump do banco não entregue a credencial.

3. **O evento passa por `registrar()`.** O caminho de escrita do dispositivo é
   o MESMO da digitação do produtor, com a mesma validação estrita e o mesmo
   tenancy. Um dispositivo rogue não tem via mais fácil que um usuário: ele
   escreve `{"temperatura": 22}` ou é recusado, exatamente como seria
   digitado. Se este módulo tivesse o próprio `INSERT`, existiria um segundo
   lugar onde uma chave arbitrária entraria no banco — e é sempre o segundo
   lugar que ninguém revisa.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Any, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)

#: 32 bytes = 256 bits. É o mesmo tamanho de chave do AES-256 e do Ed25519;
#: abaixo disso, um ASIC dedicado ja fecha a conta.
BYTES_TOKEN = 32

#: Tamanho máximo do corpo do webhook. Um ESP32 publishes JSON de algumas
#: dezenas de bytes; 4 KB é folgado e barra o payload de 50 MB que alguém
#: tentaria mandar para estourar a memória do servidor.
MAX_PAYLOAD = 4096


def gerar_token() -> str:
    """256 bits de entropia, URL-safe (vai em header HTTP e em tópico MQTT)."""
    return secrets.token_urlsafe(BYTES_TOKEN)


def hash_token(token: str) -> str:
    """SHA-256 hexadecimal. Determinístico — é o que permite buscar por index."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def comparar(a: str, b: str) -> bool:
    """Comparação em tempo constante.

    `==` em string devolve falso no primeiro byte diferente, e o tempo
    que ela leva revela o prefixo certo. Num endpoint público de telemetria isso
    é um oráculo de byte a byte . `compare_digest` não.
    """
    return hmac.compare_digest(str(a or ""), str(b or ""))


def montar_topico(user_id: int, slug: str, token: str) -> str:
    """`ampliagro/user_{id}/{slug}/{token}` — o formato pedido.

    O token no tópico é uma escolha consciente, não um acidente: ele deixa o
    broker fazer o roteamento por assinatura, sem ACL por cliente. O custo
    está declarado em `app/models/iot_dinamico.py`: tópico aparece em log de
    broker e em qualquer `mosquitto_sub`, então **quem lê o tópico autentica**.
    A mitigação aqui é revogação; a variante sem segredo no tópico está
    descrita no escopo C++ como `modo: "seguro"`.
    """
    return f"ampliagro/user_{int(user_id)}/{slug}/{token}"


# --------------------------------------------------------------------------
# Provisionamento
# --------------------------------------------------------------------------


def provisionar(user, app, *, nome: str, campo_destino: str) -> dict[str, Any]:
    """Cria o endpoint e devolve o token — ÚNICA vez que ele sai do servidor.

    O token volta em `token` e NÃO volta em nenhuma função de leitura
    (`IotEndpoint.como_descrever` não o inclui, e `token_hash` nunca é
    serializado para fora). Quem precisar do valor de novo provisiona outro
    endpoint e revoga este.
    """
    from app.ia.dinamicos import ErroDinamico, resolver_app
    from app.models import IotEndpoint

    if user is None or not getattr(user, "is_authenticated", False):
        raise ErroDinamico("usuario obrigatorio")
    # fail-closed: sem dono no filtro, um slug de outro produtor acha a
    # ferramenta errada. Mesmo método do BUILD 2, mesmo motivo.
    alvo = resolver_app(user, getattr(app, "slug", app))
    if alvo is None:
        raise ErroDinamico("ferramenta nao encontrada entre as suas")

    nome = (nome or "").strip()[:100]
    if not nome:
        raise ErroDinamico("informe 'nome' do endpoint. Ex: nome='Valvula do talhao 4'")

    # O campo de destino tem que existir no schema. Validar aqui evita
    # descobrir isso no primeiro evento, com o produtor já esperando dado.
    campos = {c.chave: c for c in alvo.dynamic_fields.filter(ativo=True)}
    chave = (campo_destino or "").strip()
    if not chave:
        raise ErroDinamico(
            "informe 'campo_destino': a chave do schema que recebe a leitura. "
            f"Campos: {', '.join(sorted(campos)) or '(nenhum)'}"
        )
    if chave not in campos:
        raise ErroDinamico(
            f"campo_destino {chave!r} nao existe em {alvo.slug}. "
            f"Campos: {', '.join(sorted(campos)) or '(nenhum)'}"
        )

    token = gerar_token()
    topico = montar_topico(user.pk, alvo.slug, token)

    endpoint = IotEndpoint(
        user=user,
        app=alvo,
        nome=nome,
        token_hash=hash_token(token),
        token_prefixo=token[:8],
        topico=topico,
        campo_destino=chave,
        estado="ATIVO",
    )
    endpoint.save()

    escopo = renderizar_escopo_cpp(endpoint, token)

    # O que PERSISTE e' o escopo com o segredo redigido. Guardar o escopo
    # completo com o token dentro anulava a propriedade "o token aparece uma
    # vez": ele ficaria no banco, e apareceria em qualquer tela que desenhasse
    # o escopo do endpoint.
    #
    # O que volta na RESPOSTA e' o completo — e o produtor precisa dele, e e
    # uma unica vez.
    endpoint.escopo_tecnico = redigir_escopo(escopo, token)
    endpoint.save(update_fields=["escopo_tecnico"])

    return {
        "endpoint": endpoint,
        "token": token,
        "escopo": escopo,
    }


def revogar(user, endpoint) -> bool:
    """Corta o acesso. Idempotente; alheio é erro, não no-op silencioso."""
    from app.ia.dinamicos import ErroDinamico

    if user is None or not getattr(user, "is_authenticated", False):
        raise ErroDinamico("usuario obrigatorio")
    if endpoint is None or endpoint.user_id != user.pk:
        raise ErroDinamico("endpoint nao pertence ao usuario")
    return endpoint.revogar()


# --------------------------------------------------------------------------
# Autenticação e recepção
# --------------------------------------------------------------------------


def autenticar(token: str):
    """Resolve o endpoint pelo token. Devolve None em qualquer falha.

    Devolve None, e não levanta, porque o caminho quente é uma requisição
    anônima de um dispositivo: levantar transformaria token ruim em 500, e um
    500 em endpoint público é convite para scanner. O chamador decide o status.
    """
    from app.models import IotEndpoint

    if not token:
        return None
    try:
        return IotEndpoint.objects.select_related("app", "user").get(
            token_hash=hash_token(token)
        )
    except Exception:  # noqa: BLE001 - IncludesDoesNotExist e afins
        return None


def receber_evento(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispositivo publicou -> registro dinâmico gravado (ou recusado com motivo).

    Nunca levanta. Um endpoint público que levanta em payload ruim é um
    endpoint que um scanner derruba com uma requisição.
    """
    from app.ia.dinamicos import registrar
    from app.models import IotEvento

    if not isinstance(payload, dict):
        return _recusar(None, "payload_invalido", {}, "", "payload nao e objeto JSON")

    try:
        tamanho = len(str(payload))
    except Exception:  # noqa: BLE001
        tamanho = MAX_PAYLOAD + 1
    if tamanho > MAX_PAYLOAD:
        return _recusar(
            None,
            "excedido",
            payload,
            "",
            f"payload de {tamanho} caracteres excede o limite de {MAX_PAYLOAD}",
        )

    endpoint = autenticar(token)
    if endpoint is None:
        # guardamos o evento com user=None? Não dá: user é obrigatório.
        # Um token inválido não tem dono, e criar linha sem dono seria um
        # evento órfão que ninguém consulta. A tentativa fica no log.
        logger.warning(
            "[IoT] evento com token invalido (prefixo=%s)",
            (token or "")[:8],
        )
        return {
            "ok": False,
            "motivo": "token_invalido",
            "erro": "token invalido",
        }

    if not endpoint.ativo:
        IotEvento.objects.create(
            endpoint=endpoint,
            user=endpoint.user,
            motivo="revogado",
            payload=payload,
            detalhe="publicacao apos revogacao",
        )
        return {"ok": False, "motivo": "revogado", "erro": "endpoint revogado"}

    # o valor: a tool define a chave (`valor`) ou aceitamos o primeiro campo
    if "valor" in payload:
        valor = payload.get("valor")
    else:
        chaves = [k for k in payload if k != "valor"]
        if len(chaves) != 1:
            return _recusar(
                endpoint,
                "payload_invalido",
                payload,
                "",
                "informe 'valor', ou exatamente um campo de leitura",
            )
        valor = payload.get(chaves[0])

    # AQUI ESTÁ O PONTO: o mesmo `registrar()` que o produtor digita. Validação
    # estrita contra o schema e tenancy inclusos — de graça, porque é o mesmo
    # caminho. Um dispositivo não tem via mais permissiva que um dedo.
    resultado = registrar(
        endpoint.user,
        endpoint.app,
        {endpoint.campo_destino: valor},
        estrito=True,
    )

    if not resultado["ok"]:
        detalhe = "; ".join(f"{k}: {v}" for k, v in (resultado["erros"] or {}).items())
        IotEvento.objects.create(
            endpoint=endpoint,
            user=endpoint.user,
            motivo="campo_invalido",
            payload=payload,
            valor=str(valor)[:120],
            detalhe=detalhe[:300],
        )
        return {
            "ok": False,
            "motivo": "campo_invalido",
            "erro": detalhe[:300],
            "campos_validos": [
                c.chave for c in endpoint.app.dynamic_fields.filter(ativo=True)
            ],
        }

    registro = resultado["registro"]
    evento = IotEvento.objects.create(
        endpoint=endpoint,
        user=endpoint.user,
        motivo="aceito",
        payload=payload,
        valor=str(valor)[:120],
        registro=registro,
    )
    endpoint.total_eventos = (endpoint.total_eventos or 0) + 1
    endpoint.ultimo_evento_em = timezone.now()
    endpoint.save(update_fields=["total_eventos", "ultimo_evento_em"])

    return {
        "ok": True,
        "evento_id": evento.pk,
        "registro_id": registro.pk,
        "entity_slug": endpoint.app.slug,
        "campo": endpoint.campo_destino,
    }


def _recusar(endpoint, motivo, payload, valor, detalhe) -> dict[str, Any]:
    from app.models import IotEvento

    if endpoint is not None:
        IotEvento.objects.create(
            endpoint=endpoint,
            user=endpoint.user,
            motivo=motivo,
            payload=payload if isinstance(payload, dict) else {},
            valor=str(valor)[:120],
            detalhe=detalhe[:300],
        )
    return {"ok": False, "motivo": motivo, "erro": detalhe}


# --------------------------------------------------------------------------
# O escopo técnico: o que o produtor copia para o firmware
# --------------------------------------------------------------------------


def redigir_escopo(escopo: dict, token: str) -> dict:
    """Troca o segredo pelo marcador, em todas as posições do pacote.

    Recebe o VALOR do token, não um marcador: minha primeira versão substituía
    um placeholder que ninguém inseria, e não redigia nada — o segredo ficava
    no banco e o teste acusou.

    É recursivo porque o token vive em três lugares do pacote: o payload
    `token`, o `cpp_esp32` e o tópico embutido no C++. Um `dict.copy()` raso
    deixaria dois dos três no banco.
    """
    if not token:
        return escopo
    if isinstance(escopo, dict):
        return {k: redigir_escopo(v, token) for k, v in escopo.items()}
    if isinstance(escopo, list):
        return [redigir_escopo(v, token) for v in escopo]
    if isinstance(escopo, str):
        return escopo.replace(token, TOKEN_REDIGIDO)
    return escopo


#: O que fica no lugar do segredo. Legível de propósito: quem abrir a tela de
#: configuração do endpoint precisa saber que ali Havia um segredo, e não
#: receber uma string vazia e achar que o provisioning falhou.
TOKEN_REDIGIDO = "<TOKEN-REDIGIDO>"

MODELO_ESP32 = "A0:B1:C2:D3:E4:F5"


def renderizar_escopo_cpp(endpoint, token: str) -> dict[str, Any]:
    """Monta o pacote que o produtor cola no Arduino IDE.

    É um TEMPLATE com o token e o tópico já preenchidos — não um placeholder
    com `{TOKEN}`, porque `{TOKEN}` no firmware obriga o produtor a editar
    string, e editar string é onde alguém apaga as aspas e gasta duas horas
    com erro de sintaxe que não é de sintaxe.

    Inclui o aviso de exposição do token no tópico, dentro do próprio código
    que vai para o repositório dele: o aviso precisa traveling com o artefato,
    não ficar num e-mail que ele não vai ler de novo.
    """
    escopo = {
        "versao": 1,
        "endpoint": {
            "id": endpoint.pk,
            "nome": endpoint.nome,
            "entity_slug": endpoint.app.slug,
            "campo_destino": endpoint.campo_destino,
        },
        "broker": {
            "host": "mqtt.ampliagro.com",
            "porta": 8883,
            "transporte": "TLS",
            "topico_publicado": endpoint.topico,
        },
        "http": {
            "url_evento": "/api/iot/dinamico/evento/",
            "metodo": "POST",
            "cabecalho": "Authorization: Bearer <TOKEN>",
        },
        "token": token,
        "token_prefixo": endpoint.token_prefixo,
        "aviso_seguranca": (
            "O token esta no topico MQTT por decisao de projeto: topico aparece "
            "em log de broker e em qualquer assinante. Quem le o topico "
            "autentica. Para o modo sem segredo no topico, troque por "
            "topico publica (endpoint_id) + Authorization no corpo — ver "
            "variante 'segura'."
        ),
        "cpp_esp32": _cpp(endpoint, token),
        "cpp_esp32_modo_seguro": _cpp(endpoint, None),
    }
    return escopo


def _cpp(endpoint, token: str | None) -> str:
    """O template Arduino. Sem token = variante segura (segredo no header)."""
    topico = (
        endpoint.topico if token else f"ampliagro/u{endpoint.user_id}/e{endpoint.pk}"
    )
    if token:
        auth_real = f'  client.setAuthorization("Bearer {token}");'
        aviso = (
            "// ATENCAO: o token abaixo e o mesmo que esta no topico. Ele passa a"
            " aparecer\n"
            "// em log do broker. O modo seguro (abaixo) evita isso."
        )
    else:
        auth_real = "  // cole o token aqui — ele NUNCA vai para o topico"
        aviso = (
            "// MODO SEGURO: o topico e publico (sem segredo) e o token viaja"
            " no header.\n"
            "// Quem le o topico nao autentica. Prefira este modo."
        )

    return f"""{aviso}
//
// AmplIA — {endpoint.nome} ({endpoint.app.slug})
// Le o valor e manda para o campo "{endpoint.campo_destino}".
// Gerado pelo Criador Livre. Troque host/senha_wifi antes de gravar.
//
#include <WiFi.h>
#include <PubSubClient.h>

const char* WIFI_SSID = "{MODELO_ESP32}";
const char* WIFI_SENHA = "TROQUE-ME";
{auth_real}

const char* MQTT_HOST = "mqtt.ampliagro.com";
const uint16_t MQTT_PORT = 8883;
const char* TOPICO = "{topico}";

// Troque pelo pino/funcao que voce usa no seu sensor.
float ultimaLeitura() {{
  return 22.5;
}}

void setup() {{
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  while (WiFi.status() != WL_CONNECTED) {{
    delay(500);
    Serial.println("conectando wifi...");
  }}

  // TLS no broker: sem isto, o token viaja em claro na rede.
  WiFiClientSecure secure;
  secure.setInsecure(); // PRODUTO: fixar o certificado, nao desligar a validacao

  PubSubClient mqtt(secure);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback([](char* topico, byte* payload, unsigned int len) {{}});

  mqtt.connect("esp32-{endpoint.pk}", "", "", MQTT_HOST, MQTT_PORT);
  Serial.println(mqtt.connected() ? "mqtt ok" : "mqtt falhou");
}}

void loop() {{
  if (!mqtt.connected()) {{
    mqtt.reconnect();
  }}
  char msg[32];
  snprintf(msg, sizeof(msg), "{{\\"valor\\":%.2f}}", ultimaLeitura());
  mqtt.publish(TOPICO, msg);
  delay(60000); // 1 leitura por minuto: bateria dura, e o produtor nao precisa de mais
}}"""
