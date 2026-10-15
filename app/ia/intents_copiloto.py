"""Estado do acompanhamento local exposto ao mesmo painel e catálogo MCP."""

from django.conf import settings

from app.ia.agendador_local import estado
from app.models import ProativoPreferencia


def h_copiloto_status(user, params, ctx):
    motor = estado()
    propriedades = list(
        ProativoPreferencia.objects.filter(user=user).values(
            "propriedade_id", "propriedade__nome", "ativo"
        )
    )
    ativos = [p["propriedade__nome"] for p in propriedades if p["ativo"]]
    return {
        "ok": True,
        "resposta": (
            "Acompanhamento local "
            + (
                "em execução"
                if motor["ativo"]
                else "não está em execução neste processo"
            )
            + ". "
            + (
                "Propriedades ativadas: " + ", ".join(ativos)
                if ativos
                else "Nenhuma propriedade ativada. Use: ative copiloto propriedade ID."
            )
        ),
        "dados": {
            "local_habilitado": bool(getattr(settings, "AMPLIA_LOCAL_COPILOTO", False)),
            "ativo": motor["ativo"],
            "ultima_execucao": motor["ultima_execucao"],
            "ultimo_erro": motor["ultimo_erro"],
            "propriedades": propriedades,
            "intervalo_segundos": 300,
        },
    }


INTENTS_COPILOTO = {
    "copiloto_status": {
        "descricao": "Informa se a varredura local está rodando e quais propriedades desta conta têm acompanhamento ativado.",
        "exemplos": [
            "status do copiloto",
            "copiloto está acompanhando minha propriedade",
        ],
        "flags": ["proativo.read"],
        "handler": h_copiloto_status,
    },
}
