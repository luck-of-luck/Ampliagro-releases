"""Governança de comandos IoT (P3): timeout, retry e rate-limit.

- Todo comando criado pela IA expira (padrão 30 min): passou disso em
  pendente/enviado, vira erro (gateway offline não trava a fila).
- Rate-limit: máx 10 comandos/device/hora (anti-toggling repetido).
- Deduplicação: comando igual pendente pro mesmo device = reuso, não fila nova.
"""

from datetime import timedelta

LIMITE_COMANDOS_HORA = 10
TIMEOUT_MIN_PADRAO = 30


def enfileirar_comando(device, comando, payload=None, timeout_min=TIMEOUT_MIN_PADRAO):
    """Cria (ou reusa) comando com expiração. Retorna (cmd, criado)."""
    from django.utils import timezone

    from app.models import ComandoDevice

    agora = timezone.now()
    dup = (
        ComandoDevice.objects.filter(
            device=device, comando=comando, status__in=["pendente", "enviado"]
        )
        .order_by("-criado_em")
        .first()
    )
    if dup:
        return dup, False
    recentes = ComandoDevice.objects.filter(
        device=device, criado_em__gte=agora - timedelta(hours=1)
    ).count()
    if recentes >= LIMITE_COMANDOS_HORA:
        raise RuntimeError(
            f"rate-limit: {recentes} comandos nesta hora para {device.nome} (máx {LIMITE_COMANDOS_HORA})"
        )
    cmd = ComandoDevice.objects.create(
        device=device,
        comando=comando,
        payload=payload or {},
        expira_em=agora + timedelta(minutes=timeout_min),
    )
    return cmd, True


def expirar_comandos(timeout_min=None):
    """Marca como erro os pendente/enviado expirados. Retorna qtd."""
    from django.utils import timezone

    from app.models import ComandoDevice

    agora = timezone.now()
    qs = ComandoDevice.objects.filter(status__in=["pendente", "enviado"])
    # Bulk update para comandos com expira_em definido
    n = qs.filter(expira_em__isnull=False, expira_em__lte=agora).update(
        status="erro", ultimo_erro="timeout: sem ack do gateway"
    )
    # Fallback para comandos legados sem expira_em: usar criado_em + timeout
    limite = agora - timedelta(minutes=timeout_min or TIMEOUT_MIN_PADRAO)
    n += qs.filter(expira_em__isnull=True, criado_em__lte=limite).update(
        status="erro", ultimo_erro="timeout: sem ack do gateway"
    )
    return n
