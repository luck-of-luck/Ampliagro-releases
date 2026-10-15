"""Evidências recentes de sensores para o copiloto local, sem prescrição inventada."""

from datetime import timedelta

from django.utils import timezone

from app.models import RegraAlertaTelemetria, TelemetryData


def sensores_para_cenario(user, propriedade):
    if propriedade.user_id != user.pk:
        return {"tem_algo": False, "lista": [], "motivo": "propriedade fora da conta"}
    agora = timezone.now()
    leituras = list(
        TelemetryData.objects.filter(
            propriedade=propriedade,
            propriedade__user=user,
            device__propriedade=propriedade,
            device__ativo=True,
            timestamp__gte=agora - timedelta(hours=24),
            timestamp__lte=agora,
        )
        .select_related("device", "talhao")
        .order_by("-timestamp", "-pk")[:501]
    )
    regras = list(
        RegraAlertaTelemetria.objects.filter(
            propriedade=propriedade,
            ativa=True,
            tipo__in=["threshold_min", "threshold_max"],
            valor_ref__isnull=False,
        ).order_by("pk")[:100]
    )
    grupos = {}
    for leitura in leituras[:500]:
        grupos.setdefault((leitura.device_id, leitura.metric), []).append(leitura)
    lista = []
    for historico in grupos.values():
        atual = historico[0]
        # Não substituir uma leitura recente inválida por uma antiga aparentemente boa.
        if atual.qualidade not in {"good", "calibrated"}:
            continue
        for regra in regras:
            if regra.metric != atual.metric:
                continue
            fora = (
                atual.value < regra.valor_ref
                if regra.tipo == "threshold_min"
                else atual.value > regra.valor_ref
            )
            if not fora:
                continue
            lista.append(
                {
                    "leitura_id": atual.pk,
                    "device_id": atual.device_id,
                    "device": atual.device.nome,
                    "metric": atual.metric,
                    "valor": str(atual.value),
                    "unidade": atual.unit,
                    "timestamp": atual.timestamp.isoformat(),
                    "qualidade": atual.qualidade,
                    "talhao_id": atual.talhao_id,
                    "talhao": atual.talhao.nome
                    if atual.talhao_id and atual.talhao.propriedade_id == propriedade.pk
                    else None,
                    "regra_id": regra.pk,
                    "limite": str(regra.valor_ref),
                    "tipo_limite": regra.tipo,
                    "amostras_na_janela": len(historico),
                    "severidade": regra.severidade,
                }
            )
    return {
        "tem_algo": bool(lista),
        "lista": lista[:20],
        "janela_horas": 24,
        "leituras_truncadas": len(leituras) > 500,
    }


def achados_sensores(sensores, previsao):
    achados = []
    for fato in sensores.get("lista", []):
        mensagem = (
            f"{fato['device']}: {fato['metric']} = {fato['valor']} {fato['unidade']}, "
            f"fora do limite configurado {fato['limite']} ({fato['tipo_limite']}). "
            f"Leitura de {fato['timestamp']}; {fato['amostras_na_janela']} amostras recentes. "
        )
        if fato["metric"] in {"ph_solo", "ph_agua"}:
            mensagem += (
                "Plano proposto: verificar calibração e repetir a medição no local; "
                "vincular a análise de solo ou água, cultura e estágio antes de definir produto e dose. "
                "O limite configurado é um gatilho de investigação, não uma prescrição de correção. "
            )
        else:
            mensagem += "Plano proposto: verificar o sensor e as condições do local antes de alterar o manejo. "
        if previsao.get("ok"):
            dias = previsao.get("dias", [])[:3]
            mensagem += (
                "Conferir a janela de manejo com a previsão: "
                + "; ".join(
                    f"{d.get('dia')}: {d.get('mm')} mm, {d.get('prob')}% de chuva"
                    for d in dias
                )
                + ". "
            )
        else:
            mensagem += "Previsão indisponível: falta validar a janela climática. "
        mensagem += "Nenhum insumo foi aplicado e nenhum equipamento foi acionado."
        achados.append(
            {
                "titulo": f"Sensor fora do limite: {fato['metric']} — {fato['device']}"[
                    :160
                ],
                "mensagem": mensagem,
                "nivel": "critico" if fato["severidade"] == "critical" else "atencao",
                "regra": "sensor_contextual",
                "evidencia": f"device:{fato['device_id']}:regra:{fato['regra_id']}:dia:{fato['timestamp'][:10]}",
                "leitura_id": fato["leitura_id"],
                "talhao_id": fato["talhao_id"],
            }
        )
    return achados
