"""
Motor de regras/alertas para telemetria.

Avalia cada batch de leituras contra RegraAlertaTelemetria + regras agronômicas
do culture_config (CultureBusinessEngine).

Acoplado ao ingestion: após salvar TelemetryData, chama evaluate_batch().
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg
from django.utils import timezone

logger = logging.getLogger(__name__)


def evaluate_batch(propriedade, device, readings, now=None):
    """
    readings: lista de dicts já normalizados [{"metric","value","timestamp",...}]
    Cria AlertaTelemetria quando regra dispara. Retorna lista de alertas criados.
    Usa debounce: não recria mesmo alerta se já existe não-resolvido na janela.
    """
    from app.models import AlertaTelemetria, Notificacao, RegraAlertaTelemetria

    now = now or timezone.now()
    created = []
    regras = RegraAlertaTelemetria.objects.filter(propriedade=propriedade, ativa=True)

    # index regras por metric
    by_metric = {}
    for r in regras:
        by_metric.setdefault(r.metric, []).append(r)

    for rd in readings:
        metric = rd["metric"]
        val = Decimal(str(rd["value"]))
        ts = rd["timestamp"]
        for regra in by_metric.get(metric, []):
            disparou = False
            msg = ""
            if (
                regra.tipo == "threshold_max"
                and regra.valor_ref is not None
                and val > regra.valor_ref
            ):
                disparou = True
                msg = f"{metric} acima do limite: {val} > {regra.valor_ref}{rd.get('unit', '')}"
            elif (
                regra.tipo == "threshold_min"
                and regra.valor_ref is not None
                and val < regra.valor_ref
            ):
                disparou = True
                msg = f"{metric} abaixo do limite: {val} < {regra.valor_ref}{rd.get('unit', '')}"
            elif regra.tipo == "delta":
                # variação rápida: compara com média da janela
                janela = now - timedelta(minutes=regra.janela_min)
                # média recente desta métrica na propriedade (última janela)
                from app.models import TelemetryData

                agg = TelemetryData.objects.filter(
                    propriedade=propriedade, metric=metric, timestamp__gte=janela
                ).aggregate(avg=Avg("value"))
                avg = agg["avg"]
                if avg is not None:
                    delta_pct = (
                        abs(float(val) - float(avg)) / max(abs(float(avg)), 1) * 100
                    )
                    thr = float(regra.config.get("delta_pct", 30))
                    if delta_pct >= thr:
                        disparou = True
                        msg = f"{metric} variação brusca: {delta_pct:.1f}% em {regra.janela_min}min (ref {avg:.2f} → {val})"
            elif regra.tipo == "anomalia":
                # z-score simples: compara com histórico 24h
                import statistics

                from app.models import TelemetryData

                janela = now - timedelta(hours=24)
                vals = list(
                    TelemetryData.objects.filter(
                        propriedade=propriedade, metric=metric, timestamp__gte=janela
                    ).values_list("value", flat=True)[:200]
                )
                if len(vals) >= 20:
                    try:
                        mean = statistics.mean(float(v) for v in vals)
                        stdev = statistics.pstdev(float(v) for v in vals)
                        if stdev > 0:
                            z = abs(float(val) - mean) / stdev
                            thr = float(regra.config.get("z_threshold", 3))
                            if z >= thr:
                                disparou = True
                                msg = f"{metric} anomalia (z={z:.1f}): {val} vs média {mean:.2f}±{stdev:.2f}"
                    except Exception as e:
                        logger.warning("alert_engine: %s", e)
            elif regra.tipo == "offline":
                # tratado separadamente por job periódico; não dispara por leitura
                continue

            if disparou:
                # automação física (opt-in na regra): enfileira comando.
                # Dedupe (pendente reusa) + rate-limit 10/h protegem de flood.
                if regra.acao_fisica in ("abrir_valvula", "fechar_valvula"):
                    try:
                        from app.ia.comandos import enfileirar_comando

                        alvo = regra.device_alvo or device
                        if alvo is not None:
                            comando = (
                                "valve_open"
                                if regra.acao_fisica == "abrir_valvula"
                                else "valve_close"
                            )
                            enfileirar_comando(
                                alvo,
                                comando,
                                {"via": "regra_auto", "regra_id": regra.id},
                            )
                    except Exception as e:
                        logger.warning("alert_engine: %s", e)
                # debounce: se já existe alerta não-resolvido para mesma regra+device na janela, skip
                debounce_min = int(regra.config.get("debounce_min", 60))
                exists = AlertaTelemetria.objects.filter(
                    regra=regra,
                    device=device,
                    resolvido=False,
                    criado_em__gte=now - timedelta(minutes=debounce_min),
                ).exists()
                if exists:
                    continue
                alerta = AlertaTelemetria.objects.create(
                    regra=regra,
                    propriedade=propriedade,
                    device=device,
                    metric=metric,
                    valor=val,
                    severidade=regra.severidade,
                    mensagem=msg or f"Regra '{regra.nome}' disparada",
                    timestamp=ts,
                )
                created.append(alerta)
                # Notificação in-app (produtor + servidores da fazenda)
                try:
                    Notificacao.objects.create(
                        user=propriedade.user,
                        titulo=f"Alerta: {regra.nome}",
                        mensagem=msg,
                        nivel="critical"
                        if regra.severidade == "critical"
                        else "warning"
                        if regra.severidade == "warning"
                        else "info",
                        link=f"/telemetria/?alerta={alerta.id}",
                    )
                    # notifica servidores vinculados
                    try:
                        from app.models import PerfilUsuario

                        for perfil in PerfilUsuario.objects.filter(
                            propriedade_vinculada=propriedade, tipo_usuario="servidor"
                        ).select_related("user"):
                            if (
                                perfil.area_servidor == regra.cargo_tarefa
                                or not regra.cargo_tarefa
                            ):
                                Notificacao.objects.create(
                                    user=perfil.user,
                                    titulo=f"Alerta: {regra.nome}",
                                    mensagem=msg,
                                    nivel="warning"
                                    if regra.severidade != "critical"
                                    else "critical",
                                    link=f"/operario/kanban/?alerta={alerta.id}",
                                )
                    except Exception as e:
                        logger.warning("alert_engine: %s", e)
                except Exception as e:
                    logger.warning("alert_engine: %s", e)
                # Auto-criação de tarefa Kanban (associação)
                try:
                    if regra.criar_tarefa:
                        from app.models import (
                            Cultura,
                            EstagioCultura,
                            RegistroProducao,
                            TarefaEstagio,
                        )

                        # encontra/cria registro + estágio para alertas
                        cultura = Cultura.objects.filter(ativo=True).first()
                        if cultura:
                            reg, _ = RegistroProducao.objects.get_or_create(
                                user=propriedade.user,
                                cultura=cultura,
                                nome="Alertas Automáticos",
                                defaults={"grupo": "vegetal", "status": "ativo"},
                            )
                            est, _ = EstagioCultura.objects.get_or_create(
                                registro=reg,
                                nome="Alertas",
                                defaults={
                                    "ordem": 99,
                                    "cor": "#ef4444",
                                    "icone": "bi-exclamation-triangle",
                                },
                            )
                            # evita duplicata de tarefa igual nas últimas 2h
                            titulo = (
                                regra.titulo_tarefa
                                or f"Verificar: {regra.nome} ({metric}={val})"
                            )
                            if not TarefaEstagio.objects.filter(
                                estagio=est,
                                descricao=titulo,
                                criado_em__gte=now - timedelta(hours=2),
                            ).exists():
                                # associa à propriedade para filtro rápido do kanban
                                TarefaEstagio.objects.create(
                                    estagio=est,
                                    descricao=titulo + f" — {msg}",
                                    cargo_alvo=regra.cargo_tarefa or regra.metric,
                                    setor=regra.setor_tarefa or "",
                                    prioridade=regra.prioridade_tarefa or "alta",
                                    status="pendente",
                                    propriedade=propriedade,
                                    ordem=0,
                                )
                except Exception as e:
                    logger.warning("alert_engine: %s", e)
            elif regra.tipo in ("threshold_max", "threshold_min"):
                # auto-resolve: métrica voltou ao normal → fecha alertas abertos
                try:
                    AlertaTelemetria.objects.filter(
                        regra=regra, device=device, resolvido=False
                    ).update(resolvido=True)
                except Exception as e:
                    logger.warning("alert_engine: %s", e)
    return created


def evaluate_culture_alerts(propriedade, readings, now=None):
    """Integra CultureBusinessEngine: avalia métricas contra regras agronômicas da cultura."""
    from app.models import Cultura

    now = now or timezone.now()
    metric_to_field = {
        "chuva": "chuva",
        "umidade_solo": "umidade_solo",
        "temperatura": "temperatura",
    }
    cultura_ids = list(propriedade.culturas.values_list("id", flat=True))
    if not cultura_ids:
        from app.models import Safra

        cultura_ids = list(
            Safra.objects.filter(propriedade=propriedade)
            .values_list("cultura_id", flat=True)
            .distinct()
        )
    created = []
    for cid in cultura_ids:
        try:
            cultura = Cultura.objects.get(id=cid)
        except Cultura.DoesNotExist:
            continue
        # A normalização do slug mora em `culture_config` e é a MESMA que o
        # índice de culturas usa. Antes era uma cópia local com `.replace()`
        # para `é`/`á`/`ç` minúsculos, que deixava 43 das 488 culturas
        # (MEDIDO) sem encontrar a sua regra. Uma normalização em dois sítios
        # é a origem do defeito; por isso há uma.
        # Import local: `culture_config` importa `app.models`, e este módulo
        # é importado por `app.models` — um import no topo seria circular.
        from app.api.culture_config import cultura_slug

        slug = cultura_slug(cultura.nome)
        try:
            from app.api.culture_config import get_business_engine

            engine = get_business_engine(slug)
        except Exception as e:
            logger.warning("alert_engine: %s", e)
            continue
        ctx = {
            r["metric"]: float(r["value"])
            for r in readings
            if r["metric"] in metric_to_field
        }
        if not ctx:
            continue
        ctx["stage_start_date"] = now.date()
        ctx["max_days"] = 30
        try:
            alerts = engine.get_active_alerts(None, context=ctx)
            for a in alerts:
                from app.models import AlertaTelemetria

                if AlertaTelemetria.objects.filter(
                    propriedade=propriedade,
                    metric=a.get("type", "cultura"),
                    mensagem=a.get("message", ""),
                    criado_em__gte=now - timedelta(hours=1),
                ).exists():
                    continue
                alerta = AlertaTelemetria.objects.create(
                    propriedade=propriedade,
                    device=None,
                    metric=a.get("type", "cultura"),
                    valor=0,
                    severidade="warning"
                    if a.get("level") == "warning"
                    else a.get("level", "info"),
                    mensagem=f"[{cultura.nome}] {a.get('message')}",
                    timestamp=now,
                )
                created.append(alerta)
        except Exception as e:
            logger.warning("alert_engine: %s", e)
            continue
    return created


def check_offline_devices():
    """Job periódico: marca gateways/devices offline e cria alertas."""
    from app.models import (
        AlertaTelemetria,
        Device,
        Gateway,
        RegraAlertaTelemetria,
    )

    now = timezone.now()
    for dev in Device.objects.filter(ativo=True).select_related(
        "propriedade", "gateway"
    ):
        # threshold = intervalo * 2 + 5min
        threshold = timedelta(seconds=dev.intervalo_seg * 2 + 300)
        last = dev.ultimo_push
        if last and now - last > threshold:
            # cria alerta offline se houver regra
            #
            # Só `tipo="offline"`. Antes isto também filtrava
            # `metric="bateria"`, e `metric` é a métrica do SENSOR
            # (temperatura, umidade_solo, ph_solo...) — não tem relação com
            # estar calado. Efeito: só recebia alerta de offline quem tivesse,
            # por coincidência, uma regra de bateria marcada como offline.
            # Para todos os outros devices o `continue` abaixo pulava o
            # device inteiro: ele ficava `ativo=True` para sempre, sem alerta
            # e sem log. `evaluate_batch` não cobre este caso (faz `continue`
            # explícito em `offline`), então este job é o único caminho.
            regras = RegraAlertaTelemetria.objects.filter(
                propriedade=dev.propriedade,
                tipo="offline",
                ativa=True,
            )
            # usa regra genérica se não houver específica
            if not regras.exists():
                continue
            for regra in regras:
                if AlertaTelemetria.objects.filter(
                    regra=regra,
                    device=dev,
                    resolvido=False,
                    criado_em__gte=now - timedelta(hours=1),
                ).exists():
                    continue
                AlertaTelemetria.objects.create(
                    regra=regra,
                    propriedade=dev.propriedade,
                    device=dev,
                    metric="offline",
                    valor=0,
                    severidade=regra.severidade,
                    mensagem=f"Device {dev.nome} offline há {(now - last).total_seconds() / 60:.0f} min",
                    timestamp=now,
                )
    for gw in Gateway.objects.filter(status="online"):
        if gw.ultimo_contato and now - gw.ultimo_contato > timedelta(minutes=30):
            gw.status = "offline"
            gw.save(update_fields=["status"])
