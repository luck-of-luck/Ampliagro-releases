"""
proativo_tasks.py — o worker proativo: agenda, execução e teto de frota.

O QUE O WORKER FAZ, E O QUE ELE NÃO FAZ
========================================
O worker FAZ: avaliar o cenário de cada produtor com proatividade ligada,
aplicar as regras determinísticas, e gravar alertas pelo caminho governado.

O worker NÃO FAZ: chamar o LLM.

Isso é a consequência direta de o SmolLM2 rodar **no navegador** (WebLLM). Um
task do lado servidor não tem modelo carregado, e carregar 1,1 GB no servidor
seria o oposto da promessa offline-first. E, mais importante: se o alerta
dependesse do LLM, ele só chegaria quando a aba do produtor estivesse aberta —
ou seja, os alertas mais urgentes seriam exatamente os que não chegariam.

O caminho do LLM existe, e é o navegador que o percorre: o worker deixa o
cenário **persistido na fila** (`IACenarioPendente`), e o navegador o recolhe
quando estiver ocioso, respeitando o serializador de GPU da BUILD 1. O
resultado vem por `amplia_emitir_alerta_proativo`, que é a MESMA porta
governada — e o `cenario_id` que o navegador manda é o que amarra o alerta ao
cenário que o originou.

UM WORKER QUE FUNCIONA SEM WORKER
=================================
O `config/celery.py` do projeto está, hoje, um comentário: "Celery is
temporarily disabled". O pacote está instalado, as settings existem, mas não
ha `Celery()` app nem `beat_schedule`.

Entregar uma feature que só roda se alguém primeiro consertar a infra é a
mesma armadilha que a BUILD 1 documentou para o áudio: entraria no ar e nunca
funcionaria. Então o núcleo é uma **função pura** (`varrer()`), e o Celery é
um envelope opcional por cima. Chamar por cron, por management command ou por
worker dá o mesmo resultado.

O QUE IMPEDE O LOOP
===================
Três tetos independentes, e o de frota é o que a maioria dos designs de worker
esquece:

  1. `pode_emitir` — dedup por fingerprint + teto diário + teto semanal
     (no `proativo.py`), que corta o loop por PRODUTOR;
  2. `MAX_USUARIOS_POR_VARRAGURA` — corta o loop por ALCANCE: sem ele, um
     usuário com 30 propriedades consome a varredura inteira e os outros
     deixam de ser avaliados, sem que nada indique isso;
  3. `MAX_ALERTAS_FROTA_POR_VARRAGURA` — corta o loop por LASTRO: o worker
     pode produzir mais do que a rede de notificação aguenta, e notificação em
     excesso é alerta perdido, não ruído.

E o teto de tempo: `TIMEOUT_POR_USUARIO_S`. O orçamento é de I/O externo
(previsão do tempo), não de CPU — e I/O sem teto é uma fila que não drena.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from django.utils import timezone

from app.ia.proativo import (
    MAX_ALERTAS_DIA,
    MAX_ALERTAS_FROTA_POR_VARRAGURA,
    MAX_USUARIOS_POR_VARRAGURA,
    TIMEOUT_POR_USUARIO_S,
    avaliar_usuario,
    purgar_cenarios_vencidos,
)
from app.services.revogacao import servidor_ativo

logger = logging.getLogger(__name__)


def varrer(*, teto_usuarios: int | None = None, agora=None) -> dict[str, Any]:
    """Uma varredura completa. É a função que o cron chama.

    Devolve o resumo, porque o teto de frota precisa saber quantos alertas
    saíram — e um retorno vazio não permite decidir quando parar.
    """
    agora = agora or timezone.now()
    from app.models import ProativoPreferencia

    teto_usuarios = teto_usuarios or MAX_USUARIOS_POR_VARRAGURA
    resumo = {
        "usuarios_avaliados": 0,
        "usuarios_pulado": 0,
        "usuarios_com_erro": 0,
        "usuarios_revogados": 0,
        "alertas": 0,
        "suprimidos": 0,
        "cenarios": 0,
        "cenarios_purgados": 0,
        "comandos_expirados": 0,
        "comandos_com_erro": 0,
        "parou_por_teto": False,
        "motivo_parada": "",
    }

    # Cenário vencido é cenário que mente: a previsão já mudou e o produtor
    # ainda não sabe. Purgar no começo da varredura — e não num job separado —
    # porque quem enche a fila é esta mesma varredura, e um job separado é um
    # job que alguém esquece de agendar.
    resumo["cenarios_purgados"] = purgar_cenarios_vencidos(agora=agora)

    # Comando de IoT sem ACK e' comando que mente: o produtor ve "enviado" e
    # acredita que a valvula abriu. Purgar aqui, pelo mesmo motivo do cenario
    # acima, e NAO num job separado: `manage.py ia_comandos` era manual, e
    # manual nao acontece as 7h12. Sem esta linha, `pendente` e `enviado`
    # ficavam para sempre e nada indicava um gateway que nunca mais confirmou
    # — que e' o modo de falha mais caro: fila a crescer e ninguem a ver.
    try:
        from app.ia.comandos import expirar_comandos

        resumo["comandos_expirados"] = expirar_comandos()
        if resumo["comandos_expirados"]:
            logger.warning(
                "[proativo] %s comando(s) IoT expirado(s) por falta de ACK.",
                resumo["comandos_expirados"],
            )
    except Exception as e:  # noqa: BLE001
        # "Seguiu" NAO e' "deu certo". O 0 acima nao significa "nao havia
        # comandos vencidos" — significa "nao deu para perguntar". Sao coisas
        # diferentes e o operador precisa de ver a diferenca as 7h12.
        logger.exception("[proativo] expirar_comandos falhou: %s", e)
        resumo["comandos_com_erro"] = 1

    # Um usuário pode ter mais de uma propriedade ligada. A avaliação é por
    # usuário (o teto diário é por usuário), então a lista é de DISTINTOS.
    # A contagem vem ANTES do fatiamento. Fatiando primeiro e contando depois,
    # a conta dá sempre 1 — e o log passa a dizer "1 usuário fora do teto"
    # quando eram 40, que é o número que alguém lê para entender por que um
    # produtor não foi avaliado.
    todos = list(
        ProativoPreferencia.objects.filter(ativo=True)
        .values_list("user_id", flat=True)
        .distinct()
    )
    total = len(todos)
    user_ids = todos[:teto_usuarios]

    if total > teto_usuarios:
        resumo["usuarios_pulado"] = total - teto_usuarios
        resumo["parou_por_teto"] = True
        resumo["motivo_parada"] = f"teto de {teto_usuarios} usuarios por varredura"
        logger.warning(
            "[proativo] %s usuario(s) fora do teto desta varredura; serao "
            "avaliados na proxima.",
            resumo["usuarios_pulado"],
        )

    from django.contrib.auth.models import User

    t0 = time.monotonic()
    for uid in user_ids:
        if resumo["alertas"] >= MAX_ALERTAS_FROTA_POR_VARRAGURA:
            resumo["parou_por_teto"] = True
            resumo["motivo_parada"] = (
                f"teto de frota ({MAX_ALERTAS_FROTA_POR_VARRAGURA})"
            )
            break

        # orçamento de tempo por usuário: o custo é o I/O do tempo
        if time.monotonic() - t0 > TIMEOUT_POR_USUARIO_S * len(user_ids):
            resumo["parou_por_teto"] = True
            resumo["motivo_parada"] = "orcamento de tempo da varredura"
            break

        user = User.objects.filter(pk=uid, is_active=True).first()
        if user is None:
            resumo["usuarios_pulado"] += 1
            continue

        # REVOGACAO, e este worker NAO passa por HTTP.
        #
        # MEDIDO 2026-10-04: `ServidorRevogadoMiddleware` nao entra aqui (nao ha
        # `request`), e `avaliar_usuario()` so bloqueia quando o proprio caller
        # falha — o `try` de baixo transformava a excecao em
        # `usuarios_com_erro` e seguia para o utilizador seguinte. Resultado: um
        # servidor desligado pelo produtor continuava a receber alertas
        # proativos, com a fazenda dele como origem, sem qualquer erro visivel.
        #
        # A fonte da regra e' `app/services/revogacao.py` — o mesmo sitio que as
        # views usam. Fail-closed por construcao: `servidor_ativo()` devolve
        # `False` quando nao consegue ler o flag.
        #
        # E CONTA-SE SEPARADAMENTE. Somar isto ao `usuarios_pulado` seria o
        # erro que este ficheiro jafelliu uma vez com `usuarios_com_erro`: o
        # relatorio passa a dizer "pulados: 5 (teto)" quando o que houve foi
        # revogacao, e ninguem consegue mais separar as tres causas.
        if not servidor_ativo(user):
            resumo["usuarios_revogados"] += 1
            logger.info(
                "[proativo] user=%s esta com ativo_servidor=False; nao avaliado.",
                uid,
            )
            continue

        try:
            r = avaliar_usuario(user, agora=agora)
        except Exception as e:  # noqa: BLE001
            # Um usuário com dado corrompido não pode derrubar a varredura dos
            # outros. Log e segue — que é o comportamento que a varredura
            # inteira precisa ter, senão uma exceção isolada vira cessação
            # silenciosa de todo o motor.
            #
            # Mas "seguiu" NÃO é "deu certo". A falha entra na PRÓPRIA contagem,
            # separada do `usuarios_pulado`. Antes elas somavam no mesmo número,
            # e o relatório dizia "pulados: 5 (teto)" quando na verdade o teto
            # era 40 e o que houve foi a API de tempo no ar: o operador subia
            # para aumentar o teto — que não era o problema — enquanto o produtor
            # ficava sem aviso, e o Agendador registrava sucesso.
            logger.exception("[proativo] falhou ao avaliar user=%s: %s", uid, e)
            resumo["usuarios_com_erro"] += 1
            continue

        resumo["usuarios_avaliados"] += 1
        resumo["alertas"] += r.get("alertas", 0)
        resumo["suprimidos"] += r.get("suprimidos", 0)
        resumo["cenarios"] += r.get("cenarios", 0)

    logger.info(
        "[proativo] varredura: %s usuario(s) avaliado(s), %s revogado(s), "
        "%s pulado(s), %s com erro, %s alerta(s), %s suprimido(s), %s cenario(s)%s",
        resumo["usuarios_avaliados"],
        resumo["usuarios_revogados"],
        resumo["usuarios_pulado"],
        resumo["usuarios_com_erro"],
        resumo["alertas"],
        resumo["suprimidos"],
        resumo["cenarios"],
        f" — parou: {resumo['motivo_parada']}" if resumo["parou_por_teto"] else "",
    )
    return resumo


# --------------------------------------------------------------------------
# O envelope Celery — opcional, e honesto sobre ser opcional
# --------------------------------------------------------------------------

try:  # pragma: no cover - depende de infra, e a infra pode não estar de pé
    from celery import shared_task
    from celery.schedules import crontab

    _CELERY = True
except Exception:  # noqa: BLE001
    _CELERY = False

    def shared_task(fn=None, **kwargs):  # type: ignore
        """No-op que preserva a assinatura, para o módulo importar sem Celery."""

        def deco(f):
            f.delay = lambda *a, **k: f(*a, **k)
            return f

        return deco(fn) if fn else deco


@shared_task(name="amplia.proativo.varrer", soft_time_limit=600, time_limit=660)
def varrer_task():
    """Envelope Celery. O `soft_time_limit` existe para o worker não ser morto
    pelo OOM killer do broker: um worker que leva 11 minutos e é morto reinicia
    a tarefa do zero, e o ciclo se repete."""
    return varrer()


#: A frequência. Duas vezes ao dia, 7h12 e 17h12 — antes da ida ao campo e
#: antes do encerramento do dia. Não é "de hora em hora": um produtor que recebe
#: alerta de manhã e de tarde já tem a informação; de hora em hora seria ruído
#: com caloria.
#:
#: O ENVELOPE EXISTE, MAS NÃO SE ARMA SOZINHO. Precisa de AMPLIA_CELERY_BEAT=1.
#:
#: Isto não é sobrecarga. Há DOIS agendadores vivos neste repositório: este
#: crontab do Celery, e o Agendador de Tarefas do Windows instalado por
#: `tools/bat/setup_tarefa_proativa.bat`. Ambos apontam para 7h12 e 17h12.
#:
#: Armados os dois, cada varrredura acontece duas vezes. O dedup segura o alerta
#: duplicado — e por isso o defeito é PERIGOSO, não visível: parece funcionar.
#: Mas o `cenario` é enfileirado duas vezes, a IA raciocina sobre o mesmo
#: problema duas vezes, e o produtor vê o mesmo cardaço aparecer duas vezes no
#: feed. Nenhum log mostra erro. Só o custo aparece, e o custo é o que mais
#: demora a notar numa fazenda.
#:
#: A máquina de produção é o Windows: o Agendador já estava lá, é nativo, não
#: tem daemon para cair, e mostra o último resultado. Por isso o Celery fica
#: DESARMADO por padrão. Quem for usar Celery de verdade (contas grandes,
#: vários workers em paralelo) liga com AMPLIA_CELERY_BEAT=1 — e, ao fazer isso,
#: desinstala as tarefas do Windows. Um só agendador, sempre.
BEAT_SCHEDULE = (
    {
        "amplia-proativo-varrer": {
            "task": "amplia.proativo.varrer",
            "schedule": crontab(hour="7,17", minute="12"),
        }
    }
    if _CELERY and os.environ.get("AMPLIA_CELERY_BEAT") == "1"
    else {}
)


CELERY_DISPONIVEL = _CELERY
