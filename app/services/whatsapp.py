"""Cliente de WhatsApp pela API oficial da Meta (Cloud API).

POR QUE ISTO EXISTE, E POR QUE NAO E' UM STUB
=============================================

MEDIDO 2026-10-05 (agente 9). Dos 100 concorrentes da matriz, **2** tem
"WhatsApp como interface de operacao" — Aegro e upCampo. E' a capacidade com
menor densidade e maior valor: e' o canal onde o produtor rural esta, e onde um
alerta de "a conta venceu" chega antes de ele abrir a aplicacao.

`_disparar_whatsapp` em `notificacoes.py` foi deixado honesto: dizia "nao ha
provedor". Isso era correcto e continuava a ser um buraco — a autonomia que o
sistema tem (as regras de contas vencidas, de custo, de praga) escrevia para a
base de dados e o produtor so' via se abrisse o ecra. Um alerta que ninguem
recebe nao e' autonomia, e' uma tabela.

POR QUE A META E NAO "UM PROVEDOR QUALQUER"
===========================================

As opcoes que aparecem em projectos agro sao quase todas o WhatsApp nao
oficial: Evolution API, Baileys, WAHA. Todas automatizam um numero pessoal
através do protocolo do WhatsApp Web. Isso:

  * viola os Termos de Servico da Meta, e a conta e' banida sem recurso;
  * em Brazil, automacao de mensagem comercial por canal nao oficial e' o
    terreno onde a ANPD e o Conar ja actedram;
  * e' exactamente o "numero plausivel sem nada por tras" que o resto deste
    projecto recusa — so que agora com o telefone de um agricultor real no
    meio.

A Cloud API e' o caminho oficial: conta Meta Business, numero dedicado,
templates aprovados. Mais atrito para o produtor, e e' o unico que se pode
sustentar num produto.

O ATRITO REAL, DITO COM AS SUAS PALAVRAS
========================================

A Cloud API **nao permite** iniciar conversa. Uma mensagem so sai para um
contacto que tenha escrito nos ultimos 24 horas, senao tem de usar um
**template aprovado** pela Meta.

Isto e' um limite da plataforma, nao nossa, e tem uma consequencia que muda o
desenho: um alerta proativo ("a conta venceu") cai exactamente no caso
proibido. Portanto:

  * SEM template configurado, este modulo **nao envia** e diz porquê;
  * COM template, envia, e o `body_parameters` sao preenchidos com o numero
    que o alerta contem — que e' o que torna a mensagem util.

Quem implementa isto tem de saber disto antes de comecar, e nao descobrir
quando o produtor reclama que o alerta nunca chegou.

O QUE ESTE MODULO NAO FAZ
==========================

Nao guarda token. Nao inventa numero. Nao finge entrega: so' devolve
`entregue: True` quando a Meta devolveu 2xx **e** um `messages[0].id`. Um 200
com corpo de erro — que a API faz, e' a parte que apanha toda a gente — e'
lido como falha.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

# A versao da Graph API e' fixada. Sair dela sem querer muda o formato da
# resposta sem aviso, e um `id` numa versao nova pode vir noutro sítio.
VERSAO_GRAPH = "v21.0"

# A Meta limita o texto. Estes sao os limites do canal, nao preferencias.
MAX_CORPO = 1024
MAX_TITULO = 60


def _cfg(nome: str) -> str:
    """Le uma configuracao do projecto, sem inventar valor por omissao."""
    from django.conf import settings

    v = getattr(settings, nome, "") or ""
    return str(v).strip()


def configurado() -> tuple[bool, str]:
    """Se este canal entrega a alguem, e — se nao — o que falta, por nome.

    Devolve a mesma forma de `_email_realmente_configurado`, para que o
    dispatcher saiba dizer a mesma coisa dos dois sem um segundo caminho.
    """
    token = _cfg("WHATSAPP_ACCESS_TOKEN")
    phone_id = _cfg("WHATSAPP_PHONE_NUMBER_ID")
    template = _cfg("WHATSAPP_TEMPLATE_ALERTA")

    falta = []
    if not token:
        falta.append("WHATSAPP_ACCESS_TOKEN")
    if not phone_id:
        falta.append("WHATSAPP_PHONE_NUMBER_ID")
    if not template:
        falta.append(
            "WHATSAPP_TEMPLATE_ALERTA (a Meta nao deixa iniciar conversa: "
            "um alerta proativo so sai por template aprovado)"
        )
    if falta:
        return False, "faltam: " + ", ".join(falta)
    return True, "Meta Cloud API"


# Codigo de chamada por pais. O ISO serve para identificar o pais; o que
# aparece a frente do numero e' este.
CODIGO_DE_CHAMADA = {
    "BR": "55",
    "PT": "351",
    "US": "1",
    "AR": "54",
    "BO": "591",
    "PY": "595",
    "UY": "598",
    "CO": "57",
    "PE": "51",
    "VE": "58",
}


def normalizar_e164(bruto: str, pais: str = "BR") -> str:
    """`' (61) 99888-7777'` -> `'+5561998887777'`.

    A Cloud API exige E.164 e **rejeita** o numero se nao vier assim. Devolver
    500 porque o produtor escreveu o telefone como o escreve no teclado e' a
    forma mais facil de um sistema aparentemente completo falhar no primeiro
    uso real.

    Erros devolvem string vazia. Um telefone que nao da para normalizar nao e'
    um telefone, e inventar um numero a partir dele seria pior que nao enviar.
    """
    digitos = re.sub(r"\D", "", bruto or "")
    if not digitos:
        return ""

    # O prefixo dos digitos e' o codigo DE CHAMADA ("55"), nao o codigo ISO do
    # pais ("BR"). A primeira versao comparava os digitos com o ISO, e o
    # resultado era que '+5561998887777' — o numero que um produtor escreve
    # correctamente — devolvia vazio. O caminho que mais importa era o unico
    # que nao funcionava.
    chamada = CODIGO_DE_CHAMADA.get(pais.upper(), "")

    if chamada:
        if digitos.startswith(chamada) and len(digitos) > len(chamada) + 8:
            return "+" + digitos
        # 10 digitos = fixo; 11 = celular com o nono digito. Sem indicativo
        # nao ha como saber de que pais e' — e adivinhar seria pior do que
        # recusar.
        # Prefixo de longa distancia: '061998887777' e' 0 + 61 + 998887777.
        # O '0' e' do operador, nao do numero. Um produtor que copia de um
        # telefone fixo antigo escreve com ele.
        if digitos.startswith("0") and len(digitos) == 12:
            digitos = digitos[1:]
        if len(digitos) in (10, 11):
            return "+" + chamada + digitos

    return ""


def _payload(destino: str, titulo: str, mensagem: str, link: str) -> dict:
    """Monta o corpo que a Meta espera. Separado do envio para ser testavel."""
    corpo = f"*{titulo}*\n\n{mensagem}" if titulo else mensagem
    if link:
        corpo += f"\n\n{link}"
    # Corta pelo ULTIMO separador dentro do limite, para nao partir um link ao
    # meio — cortar no meio de uma URL torna-a inutil.
    if len(corpo) > MAX_CORPO:
        corte = corpo.rfind("\n\n", 0, MAX_CORPO)
        if corte < MAX_CORPO // 2:
            corte = MAX_CORPO
        corpo = corpo[:corte].rstrip()

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destino,
        "type": "template",
        "template": {
            "name": _cfg("WHATSAPP_TEMPLATE_ALERTA"),
            "language": {"code": _cfg("WHATSAPP_TEMPLATE_LANG") or "pt_BR"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": corpo[:MAX_CORPO]}],
                }
            ],
        },
    }


def enviar(destino: str, titulo: str, mensagem: str, link: str = "") -> dict:
    """Envia uma mensagem por template. Devolve o que aconteceu, nao o que queriamos.

    `entregue: True` exige 2xx **e** `messages[0].id`. A Meta responde 200 com
    `{"error": {...}}` quando o template nao esta aprovado ou o numero esta mal
    escrito — quem so' olha para o status code manda ao produtor "entregue" e
    nunca chega.
    """
    ok, porque = configurado()
    if not ok:
        return {"entregue": False, "motivo": f"whatsapp {porque}"}

    e164 = normalizar_e164(destino)
    if not e164:
        return {
            "entregue": False,
            "motivo": (
                f"telefone nao utilizavel como E.164: {destino!r}. "
                "E' preciso o indicativo — com so o numero local a Meta "
                "rejeita, e nao ha forma de adivinhar de que pais e'"
            ),
        }

    corpo = _payload(e164, titulo, mensagem, link)
    url = (
        f"https://graph.facebook.com/{VERSAO_GRAPH}/"
        f"{_cfg('WHATSAPP_PHONE_NUMBER_ID')}/messages"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_cfg('WHATSAPP_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            bruto = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            erro = json.loads(e.read().decode("utf-8"))
            detalhe = erro.get("error", {}).get("message") or str(erro)
        except Exception:
            detalhe = f"HTTP {e.code}"
        return {"entregue": False, "motivo": f"Meta recusou: {detalhe}"[:400]}
    except Exception as e:
        return {"entregue": False, "motivo": f"rede: {e}"[:200]}

    # HTTP 200 nao e' entrega. A Meta usa o corpo para o erro.
    if "error" in bruto:
        err = bruto["error"]
        # O `code` e' a parte accionavel — '131008' diz "template nao
        # aprovado"; a `message` so' repete isso em ingles. Quem depura isto
        # precisa do numero, nao da frase.
        codigo = err.get("code")
        texto = err.get("message") or str(err)
        return {
            "entregue": False,
            "motivo": (
                f"Meta recusou ({codigo}): {texto}" if codigo
                else f"Meta recusou: {texto}"
            )[:400],
        }

    msg_id = (bruto.get("messages") or [{}])[0].get("id", "")
    if not msg_id:
        return {
            "entregue": False,
            "motivo": f"resposta sem id de mensagem: {str(bruto)[:200]}",
        }
    return {"entregue": True, "motivo": "aceite pela Meta", "message_id": msg_id}
