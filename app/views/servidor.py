import json

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required
from app.models import *

from .utils import *

# ── Helpers compartilhados pelas 4 páginas do servidor ─────────────────────
# Antes cada view repetia o mesmo try/except de perfil + a mesma resolucao de
# propriedade. Divergencias entre as copias viraram bug real: o dashboard
# filtrava tarefas por um caminho e a agenda por outro (ver tarefas_da_propriedade).


def _perfil_e_propriedade(request, tipos_bloqueados=("produtor",)):
    """Resolve (perfil, propriedade) do usuario logado.

    Retorna (None, None) quando o caller deve redirecionar: perfil ausente
    (registro orfao) ou tipo de usuario nao permitido nesta area.
    Unica fonte de verdade para "de qual fazenda eu sou" — evita cada view
    inventar sua propria regra.
    """
    perfil = getattr(request.user, "perfil", None)
    if perfil is None or perfil.tipo_usuario in tipos_bloqueados:
        return None, None

    # REVOGACAO. O produtor desactiva o servidor em `lgpd.py`
    # (`perfil.ativo_servidor = False`). Isso bloqueia o proximo login e
    # expulsa do dashboard — mas SEM esta linha, quem ja tivesse sessao
    # iniciada continuava a ler estoque, agenda e alertas de telemetria da
    # fazenda depois de ser desactivado.
    #
    # `ativo_servidor` tem `default=True`, portanto isto nao affects operarios,
    # agronomos nem mecanicos: so quando o produtor o desligue explicitamente.
    #
    # A correcao esta AQUI e nao em cada view porque este docstring diz que e'
    # a "unica fonte de verdade". Tres das quatro rotas ja passam por aqui; a
    # quarta (o dashboard) e' corrigida logo abaixo.
    if not perfil.ativo_servidor:
        return None, None
    propriedade = perfil.propriedade_vinculada or (
        perfil.funcionario.propriedade if perfil.funcionario else None
    )
    return perfil, propriedade


def tarefas_da_propriedade(propriedade):
    """Tarefas da fazenda — regra UNICA para dashboard e agenda.

    Antes: dashboard usava `estagio__registro__user=propriedade.user` (so pelo
    dono da fazenda) e agenda usava `Q(propriedade=) | Q(estagio__registro__user=)`.
    Consequencia: tarefas vinculados por `propriedade` apareciam na agenda e
    sumiam do dashboard do mesmo servidor.
    """
    if not propriedade:
        return TarefaEstagio.objects.none()
    return TarefaEstagio.objects.filter(
        Q(propriedade=propriedade) | Q(estagio__registro__user=propriedade.user)
    ).select_related("estagio", "funcionario")


@login_required
@hierarquia_required("servidor-dashboard")
def servidor_dashboard_view(request):
    """Dashboard do servidor — estático, filtrado por área e permissões do produtor."""
    # REVOGACAO: verificar ativo_servidor ANTES do helper para poder fazer logout
    try:
        perfil = request.user.perfil
    except Exception:
        return redirect("login")

    # Se produtor caiu aqui por engano, manda para dashboard normal
    if perfil.tipo_usuario == "produtor":
        return redirect("index_spa")

    # REVOGACAO — a mesma regra que `_perfil_e_propriedade` aplica as outras
    # tres rotas. Esta view verifica ativo_servidor ANTES para poder fazer logout.
    if not perfil.ativo_servidor:
        from django.contrib.auth import logout

        logout(request)
        return render(
            request, "login.html", {"erro_login": "Servidor desativado pelo produtor."}
        )

    if perfil.tipo_usuario not in [
        "servidor",
        "operario",
        "mecanico",
        "agronomo",
        "administrativo",
    ]:
        return redirect("login")

    # Agora usa o helper para obter a propriedade (ja passou na revogacao)
    perfil, propriedade = _perfil_e_propriedade(request)
    if perfil is None:
        return redirect("index_spa")

    if perfil.tipo_usuario == "produtor":
        return redirect("index_spa")

    # Config por área (usado pelo servidor.js para montar a página)
    try:
        config = perfil.get_dashboard_config()
    except Exception:
        config = {
            "titulo": "Geral",
            "icone": "bi-grid",
            "paginas": ["tarefas"],
            "pode_criar": True,
            "pode_editar": True,
        }

    # Dados filtrados para a área — entregues ao template para script modificar

    from app.models import (
        AlertaTelemetria,
        EstoqueItem,
        Maquinario,
        TarefaEstagio,
        TelemetryData,
    )

    ctx = {
        "perfil": perfil,
        "propriedade": propriedade,
        "config": config,
    }

    # Mecânica
    if config.get("titulo") == "Mecânica" or perfil.area_servidor == "MECANICA":
        maquinas = (
            Maquinario.objects.filter(propriedade=propriedade)
            if propriedade
            else Maquinario.objects.none()
        )
        # estoque mecânico: categoria PECA/FERRAMENTA + filtro nome mecânico
        estoque_mec = (
            EstoqueItem.objects.filter(
                propriedade=propriedade, categoria__in=["PECA", "FERRAMENTA"]
            )
            if propriedade
            else EstoqueItem.objects.none()
        )
        # agenda revisão: maquinário com próxima manutenção
        agenda = maquinas.filter(proxima_manutencao__isnull=False).order_by(
            "proxima_manutencao"
        )[:10]
        ctx.update(
            {"maquinas": maquinas, "estoque_mec": estoque_mec, "agenda_revisao": agenda}
        )

    # Campo / Agronomia
    if perfil.area_servidor in ["CAMPO", "AGRONOMIA"] or "talhoes" in config.get(
        "paginas", []
    ):
        from app.models import Safra, Talhao

        ctx["talhoes"] = (
            Talhao.objects.filter(propriedade=propriedade).select_related("propriedade")
            if propriedade
            else []
        )
        ctx["safras"] = (
            Safra.objects.filter(propriedade=propriedade).select_related(
                "cultura", "talhao"
            )[:10]
            if propriedade
            else []
        )

    # Pecuária
    if perfil.area_servidor == "PECUARIA":
        from app.models import Animal, ProducaoAnimal

        ctx["animais"] = (
            Animal.objects.filter(propriedade=propriedade).select_related("propriedade")
            if propriedade
            else []
        )
        ctx["producoes"] = (
            ProducaoAnimal.objects.filter(animal__propriedade=propriedade)
            .select_related("animal")
            .order_by("-data")[:10]
            if propriedade
            else []
        )

    # Alertas e tarefas sempre visíveis (filtradas por propriedade)
    if propriedade:
        ctx["alertas"] = AlertaTelemetria.objects.filter(
            propriedade=propriedade, resolvido=False
        ).select_related("regra", "device")[:10]
        # Tarefas ligadas à fazenda — mesma regra da agenda (ver helper)
        ctx["tarefas"] = tarefas_da_propriedade(propriedade)[:15]

        # Telemetria recente para o dashboard mecânico/ campo
        ctx["telemetria_recente"] = TelemetryData.objects.filter(
            propriedade=propriedade
        ).order_by("-timestamp")[:8]

    return render(request, "servidor/dashboard.html", ctx)


@login_required
@hierarquia_required("servidor-estoque")
def servidor_estoque_view(request):
    """Página Servidor — Estoque filtrado por área (MECANICA/ESTOQUE)."""
    perfil, propriedade = _perfil_e_propriedade(request)
    if perfil is None:
        return redirect("index_spa")
    # Hierarquia: só MECANICA/ESTOQUE/ADMIN veem estoque
    if perfil.area_servidor not in [
        "MECANICA",
        "ESTOQUE",
        "ADMIN",
        "GERAL",
    ] and not perfil.has_permission("estoque_mecanico"):
        from app.hierarquia import assert_hierarquia

        resp = assert_hierarquia(request, "cadastro-estoque")
        if resp:
            return resp
    from app.models import EstoqueItem

    itens = (
        EstoqueItem.objects.filter(propriedade=propriedade).order_by(
            "categoria", "nome"
        )
        if propriedade
        else []
    )
    # Filtra por área: MECANICA só vê PEÇA/FERRAMENTA
    if perfil.area_servidor == "MECANICA":
        itens = [i for i in itens if i.categoria in ["PECA", "FERRAMENTA"]]
    return render(
        request,
        "servidor/estoque.html",
        {
            "perfil": perfil,
            "propriedade": propriedade,
            "itens": itens,
            "config": perfil.get_dashboard_config(),
        },
    )


@login_required
@hierarquia_required("servidor-agenda")
def servidor_agenda_view(request):
    """Página Servidor — Agenda de revisões e tarefas por área."""
    perfil, propriedade = _perfil_e_propriedade(request)
    if perfil is None:
        return redirect("index_spa")
    from app.models import Maquinario

    maquinas = (
        Maquinario.objects.filter(propriedade=propriedade).order_by(
            "proxima_manutencao"
        )
        if propriedade
        else []
    )
    tarefas = tarefas_da_propriedade(propriedade)
    if perfil.area_servidor and perfil.area_servidor != "GERAL":
        tarefas = tarefas.filter(
            Q(cargo_alvo__iexact=perfil.area_servidor)
            | Q(setor__icontains=perfil.area_servidor)
            | Q(funcionario__user=request.user)
            | Q(cargo_alvo="")
        )
    return render(
        request,
        "servidor/agenda.html",
        {
            "perfil": perfil,
            "propriedade": propriedade,
            "maquinas": maquinas,
            "tarefas": tarefas[:20],
        },
    )


@login_required
@hierarquia_required("servidor-alertas")
def servidor_alertas_view(request):
    """Página Servidor — Alertas filtrados por área + associação com tarefas."""
    perfil, propriedade = _perfil_e_propriedade(request)
    if perfil is None:
        return redirect("index_spa")
    from app.models import AlertaTelemetria

    alertas = (
        AlertaTelemetria.objects.filter(propriedade=propriedade, resolvido=False)
        # select_related: o template usa a.propriedade.nome e a.device.nome por
        # alerta. Sem isto, 20 alertas = 41 queries (N+1). Medido 50 -> 10.
        .select_related("propriedade", "device")
        .order_by("-timestamp")[:20]
        if propriedade
        else []
    )
    # Filtra por métrica da área
    if perfil.area_servidor == "MECANICA":
        alertas = [
            a
            for a in alertas
            if a.metric in ["temp_motor", "combustivel", "bateria", "nivel", "offline"]
        ]
    elif perfil.area_servidor == "CAMPO":
        alertas = [
            a
            for a in alertas
            if a.metric in ["umidade_solo", "chuva", "temperatura", "chuva_acum"]
        ]
    tarefas_assoc = (
        TarefaEstagio.objects.filter(
            propriedade=propriedade, setor=perfil.area_servidor
        )
        # o template usa t.estagio.nome — sem select_related é 1 query por tarefa
        .select_related("estagio")
        .order_by("-criado_em")[:10]
        if propriedade
        else []
    )
    return render(
        request,
        "servidor/alertas.html",
        {
            "perfil": perfil,
            "propriedade": propriedade,
            "alertas": alertas,
            "tarefas_assoc": tarefas_assoc,
        },
    )
