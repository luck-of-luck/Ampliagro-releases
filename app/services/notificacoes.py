"""Envio de notificações. Um caminho só, e nunca levanta.

PORQUE ESTE FICHEIRO EXISTE
===========================
`app/api/views/financeiro_banco.py:242` importava
`app.services.notificacoes.send_push_notification`, e esse módulo não
existia. O resultado não era um erro discreto: era HTTP 500 em
`POST /api/notificacao-templates/<pk>/testar/`. O `test_um_500_nao_e_uma_recusa`
de `tests/test_superficie_servidor.py` existe exactamente para apanhar este
500, e continuava a falhar — porque o módulo nunca foi escrito.

O QUE ESTE MÓDULO FAZ, E O QUE NÃO FAZ
=======================================
Grava a notificação **in-app** (`Notificacao`), que é o que o painel lê e o
que os outros seis pontos do projecto já faziam directamente
(`proativo.py:541`, `alert_engine.py:149`, `alert_engine.py:171`,
`gerar_alertas.py:87`, `signals.py:175`, `user.py:383`).

**Não** faz Web Push. PushSubscription guarda `endpoint`, `p256dh` e `auth`
— as chaves de uma subscrição VAPID — mas não há `pywebpush`, nem `vapid`
no `requirements.txt`, e não há chave VAPID em lado nenhum. Enviar "push"
sem isso é escrever a metade do caminho e chamar-lhe notificação: o produtor
nunca recebe nada e o registo diz que recebeu.

Por isso a assinatura aceita `sub` (a subscrição) e devolve um dicionário
com o que aconteceu. Quem chamar pode ver que não foi enviado, e o
produtor não fica à espera de um alerta que não existe.

A regra que este ficheiro segue: **nunca levantar**. A acção "testar
notificação" é uma acção de diagnóstico; se ela rebenta, o servidor
revogado ou a staff que a carregou vê um 500 e não sabe se o problema foi a
notificação ou a aplicação. A mesma regra de `sandbox.executar` e de
`app/ia/dinamicos.py`: quem chama é UI ou agente, e uma excepção não
tratada transforma um erro de negócio num 500 sem informação.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Níveis aceitos pelo `Notificacao.nivel`. Um nível fora desta lista é
#: um `ValueError` do Django no `choices`, e um 500 por escrever "urgent".
_NIVEIS = ("info", "warning", "critical")


def send_push_notification(
    sub: Any,
    titulo: str,
    mensagem: str,
    *,
    link: str = "",
    nivel: str = "info",
) -> dict[str, Any]:
    """Registar a notificação de `sub.user`. Devolve o que aconteceu.

    `sub` é uma `PushSubscription` — mas o que interessa é o `user` que
        lhe está ligado, e é por isso que a assinatura aceita o objecto e não o
        id: nenhum caller tem de ir buscar o user à mão, e nenhum pode
        enganar-se do user e notificar a pessoa errada.

         Nunca levanta. Devolve sempre:

             {"ok": bool, "entregue": bool, "motivo": str, "notificacao_id": int|None}

         `entregue=False` com `ok=True` significa "foi registado, não foi
         empurrado". São coisas diferentes e a diferença é o que impede um
         produtor de ficar à espera de um aviso que ninguém lhe vai mandar.
    """
    try:
        user = getattr(sub, "user", None) or sub
        if user is None:
            return {
                "ok": False,
                "entregue": False,
                "motivo": "subscricao sem utilizador",
                "notificacao_id": None,
            }

        nivel_norm = str(nivel or "info").lower()
        if nivel_norm not in _NIVEIS:
            nivel_norm = "info"

        from app.models import Notificacao

        obj = Notificacao.objects.create(
            user=user,
            titulo=str(titulo or "")[:200],
            mensagem=str(mensagem or ""),
            nivel=nivel_norm,
            link=str(link or "")[:200],
        )
    except Exception as exc:  # noqa: BLE001 — ver a nota do topo do ficheiro
        logger.warning(
            "[notificacoes] falha ao registar notificacao: %s: %s",
            type(exc).__name__,
            exc,
        )
        return {
            "ok": False,
            "entregue": False,
            "motivo": f"{type(exc).__name__}: {exc}",
            "notificacao_id": None,
        }

    # A entrega real de Web Push não existe neste projecto. Registado o
    # aviso, é isto que se pode dizer com verdade.
    logger.info(
        "[notificacoes] notificacao #%s para %s (nivel=%s) — registada, "
        "nao empurrada (Web Push nao configurado)",
        obj.pk,
        getattr(user, "username", "?"),
        nivel_norm,
    )
    return {
        "ok": True,
        "entregue": False,
        "motivo": "registada no painel; Web Push nao configurado",
        "notificacao_id": obj.pk,
    }


# ══════════════════════════════════════════════════════════════════════════
# DESPACHO MULTICANAL — o que o `NotificacaoTemplate.canais` promete
# ══════════════════════════════════════════════════════════════════════════
#
# MEDIDO 2026-10-05 (agente 7). `NotificacaoTemplate.canais` e' um
# `JSONField` cuja ajuda diz `Ex: ['push', 'email', 'whatsapp']`, e **nada no
# codebase iterava essa lista**. A unica accao que envia — `testar`, em
# `app/api/views/financeiro_banco.py` — fazia sempre `send_push_notification`,
# queimando o canal configurado.
#
# Ou seja: um template com `canais: ["email"]` registava uma notificacao no
# painel e **nunca** mandava email, e a resposta dizia `ok: true`. E' a mesma
# classe de defeito do Caderno (rota que o cliente chama e nao existe) e do
# custo-por-talhao (coluna que o escritor nunca preenche): **o esquema promete,
# o codigo nao cumpre, e nada se queixa.**
#
# Este despacho existe para tornar a lista verdadeira — e para dizer, canal a
# canal, o que saiu e o que nao saiu. Um dispatcher que devolvesse um unico
# booleano repetiria o defeito com mais uma camada.

#: Canais implementados. Chave e' o valor que vai em `canais`.
#:
#: `inapp` e' o registo no painel — o que o sistema sabe fazer, e o que
#: **entrega** de verdade (o produtor ve no ecra). `push` e' Web Push para o
#: dispositivo, que **nao existe** neste projecto: o canal responde
#: `entregue: False` com o motivo. Sao canais distintos e nao se podeem
#: confundir: `["push"]` nao e' um atalho para `["inapp"]`, e um teste que
#: tratasse como se fosse estaria a declarar entregue uma coisa que nao saiu
#: do servidor.
_CANAIS = ("inapp", "push", "email", "whatsapp")

#: Canais que entregam **ao dispositivo**. `entregue` na resposta da API
#: (`financeiro_banco.py: testar`) conta estes e so estes — e' o sentido que
#: esse campo sempre teve, e que `app/tests_notificacoes.py` trava.
CANAIS_DE_DISPOSITIVO = ("push",)

#: Backends de email que **nao** entregam a ninguem. Escrever para estes e'
#: nao enviar: e' imprimir num terminal e, em teste, guardar numa lista. Um
#: dispatcher que dissesse "email enviado" com um destes seria a mentira que
#: este repositorio nao tolera.
EMAIL_NAO_ENTREGA = (
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
)


def canais_conhecidos() -> tuple[str, ...]:
    """Os nomes que `NotificacaoTemplate.canais` aceita."""
    return _CANAIS


def _email_realmente_configurado() -> tuple[bool, str]:
    """Se o backend de email entrega a alguem, e porque nao se e' que nao."""
    from django.conf import settings

    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if not backend:
        return False, "EMAIL_BACKEND nao definido"
    if backend in EMAIL_NAO_ENTREGA:
        return False, f"backend {backend.rsplit('.', 1)[-1]} nao entrega a ninguem"
    return True, backend


def _destinatario(user) -> str:
    email = (getattr(user, "email", "") or "").strip()
    return email if "@" in email else ""


def _disparar_inapp(user, titulo, mensagem, nivel, link) -> dict:
    """Regista no painel. Este canal **entrega** — o produtor ve no ecrã."""
    from app.models import Notificacao

    obj = Notificacao.objects.create(
        user=user,
        titulo=str(titulo or "")[:200],
        mensagem=str(mensagem or ""),
        nivel=nivel,
        link=str(link or "")[:200],
    )
    return {
        "entregue": True,
        "motivo": "registada no painel",
        "notificacao_id": obj.pk,
    }


def _disparar_push(user, titulo, mensagem, nivel, link) -> dict:
    """Web Push para o dispositivo. **Nao existe** — e este canal diz isso.

    MEDIDO 2026-10-05. A primeira versao deste dispatcher tratava `push` como
    alias de `inapp`, e isso era **uma mentira com nome**: registava no painel
    e respondia `entregue: True` a um pedido de Web Push, que nunca saiu do
    servidor. O nome do canal e' o que o produtor le na configuracao; um
    `push` que entrega no painel e' pior do que um `push` que nao entrega,
    porque parece funcionar.

    `PushSubscription` guarda `endpoint`, `p256dh` e `auth` — as chaves de
    uma subscricao VAPID — mas nao ha `pywebpush` nem `vapid` no
    `requirements.txt`, e nao ha chave VAPID em lado nenhum (ver a nota do
    topo deste ficheiro).

    O registo no painel continua a existir, e e' o que `inapp` faz. Sao dois
    canais: um entrega ao ecra, o outro entregaria ao dispositivo, e so um
    dos dois existe hoje.
    """
    return {
        "entregue": False,
        "motivo": (
            "Web Push nao configurado: nao ha pywebpush/vapid no "
            "requirements.txt nem chave VAPID. O aviso fica registado no "
            "painel (canal 'inapp'), mas nao chega ao dispositivo."
        ),
    }


def _disparar_email(user, titulo, mensagem, nivel, link) -> dict:
    """Email. Nao ha backend de producao — e o dispatcher diz-o."""
    ok_backend, detalhe = _email_realmente_configurado()
    if not ok_backend:
        return {
            "entregue": False,
            "motivo": f"email nao enviado: {detalhe}",
        }
    para = _destinatario(user)
    if not para:
        return {"entregue": False, "motivo": "utilizador sem email valido"}
    try:
        from django.core.mail import send_mail

        enviados = send_mail(
            subject=str(titulo or "")[:200],
            message=str(mensagem or ""),
            from_email=None,
            recipient_list=[para],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 — ver a nota do topo do ficheiro
        return {
            "entregue": False,
            "motivo": f"email falhou: {type(exc).__name__}",
        }
    return {
        "entregue": enviados > 0,
        "motivo": f"email enviado para {para}" if enviados else "email nao enviado",
    }


def _disparar_whatsapp(user, titulo, mensagem, nivel, link) -> dict:
    """WhatsApp pela API oficial da Meta. Entrega, ou diz porquê que nao.

    MEDIDO 2026-10-05 (agente 9). Este era um stub que devolvia sempre
    `entregue: False` com "nenhum provedor declarado no projecto". O stub
    estava certo no espirito — nao fingia entrega — mas deixava a autonomia do
    sistema invisivel: as regras de contas vencidas, de custo e de praga
    escreviam para a base de dados e o produtor so' sabia se abrisse o ecra.

    Agora ha provedor (`app/services/whatsapp.py`, Meta Cloud API). Sem token
    ou sem template, continua a dizer exactamente o que falta — o que e'
    diferente de dizer "nao ha provedor", porque o nome do que falta e' o que
    permite ao produtor resolver em vez de desistir.

    Entre as duas metades: a Meta **nao permite iniciar conversa**. Um alerta
    proativo ("a conta venceu") e' exactamente o caso proibido, e por isso
    depende de um template aprovado. Sem `WHATSAPP_TEMPLATE_ALERTA` nao ha
    entrega — e o modulo diz isso, em vez de tentar e falhar em silencio.
    """
    from app.services import whatsapp as WA

    ok, porque = WA.configurado()
    if not ok:
        perfil = getattr(user, "perfil", None)
        tel = (getattr(perfil, "telefone", "") or "").strip() if perfil else ""
        return {
            "entregue": False,
            "motivo": (
                f"whatsapp nao configurado: {porque}"
                + (f" (o utilizador tem {tel})" if tel else "")
                + ". Para ligar: conta Meta Business com a Cloud API, um token "
                "de acesso, e um template aprovado pela Meta para alertas."
            ),
        }

    perfil = getattr(user, "perfil", None)
    tel = (getattr(perfil, "telefone", "") or "").strip() if perfil else ""
    if not tel:
        return {
            "entregue": False,
            "motivo": "whatsapp configurado, mas o utilizador nao tem telefone "
            "no PerfilUsuario — nao ha para onde entregar",
        }

    return WA.enviar(tel, titulo, mensagem, link)


_HANDLERS = {
    "inapp": _disparar_inapp,
    "push": _disparar_push,
    "email": _disparar_email,
    "whatsapp": _disparar_whatsapp,
}


def disparar_canais(
    canais,
    user,
    titulo: str,
    mensagem: str,
    *,
    nivel: str = "info",
    link: str = "",
) -> dict[str, Any]:
    """Dispara pelos canais pedidos e devolve o que aconteceu **por canal**.

    Nunca levanta, pela mesma raza de `send_push_notification`: quem chama e'
    UI ou agente, e uma excepção aqui transforma um aviso de entrega num 500
    sem informacao.

    Devolve:

        {
          "ok": bool,             # algum canal foi reconhecido e chamado
          "entregue": bool,       # algum canal ENTREGOU de facto
          "por_canal": {canal: {"entregue": bool, "motivo": str, ...}},
          "desconhecidos": [...],  # canais que nao existem
          "pedidos": [...],
        }

    `entregue` no topo e' **conjuncao nao, disjunca sim**: verdadeiro se
    pelo menos um canal entregou. Um dispatcher que devolvesse um unico
    booleano perderia justamente a informacao que interessa — *qual* canal
    funcionou.
    """
    nivel_norm = str(nivel or "info").lower()
    if nivel_norm not in _NIVEIS:
        nivel_norm = "info"

    if isinstance(canais, str):
        pedidos = [canais]
    else:
        pedidos = [str(c).strip().lower() for c in (canais or []) if str(c).strip()]

    # Sem lista de canais: o sistema so tem um caminho que sabe fazer, e
    # assumi-lo seria inventar preferencia. Fica registado, e o dispatcher
    # diz por que nao fez nada.
    if not pedidos:
        return {
            "ok": False,
            "entregue": False,
            "por_canal": {},
            "pedidos": [],
            "desconhecidos": [],
            "motivo": (
                "o template nao tem canais configurados. Sem lista explicita "
                "nao se assume nenhum — o unico caminho que o sistema sabe "
                "fazer (in-app) fica de fora."
            ),
        }

    por_canal: dict[str, Any] = {}
    desconhecidos: list[str] = []

    for canal in dict.fromkeys(pedidos):
        handler = _HANDLERS.get(canal)
        if handler is None:
            desconhecidos.append(canal)
            por_canal[canal] = {
                "entregue": False,
                "motivo": (f"canal desconhecido. Conhecidos: {', '.join(_CANAIS)}"),
            }
            continue
        try:
            por_canal[canal] = handler(user, titulo, mensagem, nivel_norm, link)
        except Exception as exc:  # noqa: BLE001 — ver a nota do topo do ficheiro
            logger.warning(
                "[notificacoes] canal %s falhou: %s: %s",
                canal,
                type(exc).__name__,
                exc,
            )
            por_canal[canal] = {
                "entregue": False,
                "motivo": f"{type(exc).__name__}: {exc}",
            }

    conhecidos = [c for c in por_canal if c not in desconhecidos]
    entregues = [c for c in conhecidos if por_canal[c].get("entregue")]

    return {
        "ok": bool(conhecidos),
        "entregue": bool(entregues),
        "por_canal": por_canal,
        "pedidos": list(dict.fromkeys(pedidos)),
        "desconhecidos": desconhecidos,
        "motivo": (
            f"entregue em {len(entregues)}/{len(conhecidos)} canais"
            if conhecidos
            else "nenhum canal pedido e' conhecido"
        ),
    }
