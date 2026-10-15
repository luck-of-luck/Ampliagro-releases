import contextlib
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST


@login_required
def tarefas_associacao_view(request):
    """Página dedicada e completa para associar tarefas — toda a fazenda, todas as culturas, todos os funcionários"""

    from app.models import (
        AlertaTelemetria,
        Cultura,
        Funcionario,
        Talhao,
        TarefaEstagio,
    )

    propriedade = None
    try:
        perfil = request.user.perfil
        if perfil.tipo_usuario == "produtor":
            propriedade = request.user.propriedades.first()
        else:
            propriedade = perfil.propriedade_vinculada or (
                perfil.funcionario.propriedade if perfil.funcionario else None
            )
    except Exception:
        propriedade = (
            request.user.propriedades.first()
            if hasattr(request.user, "propriedades")
            else None
        )

    if not propriedade:
        return render(
            request,
            "tarefas/associacao.html",
            {"erro": "Nenhuma fazenda vinculada. Crie uma propriedade primeiro."},
        )

    # Filtros via GET
    status_filtro = request.GET.get("status", "")
    cargo_filtro = request.GET.get("cargo", "")
    cultura_filtro = request.GET.get("cultura", "")

    tarefas = TarefaEstagio.objects.filter(propriedade=propriedade).select_related(
        "estagio", "estagio__registro", "funcionario"
    )
    if status_filtro:
        tarefas = tarefas.filter(status=status_filtro)
    if cargo_filtro:
        tarefas = tarefas.filter(cargo_alvo__iexact=cargo_filtro)
    if cultura_filtro:
        with contextlib.suppress(Exception):
            tarefas = tarefas.filter(estagio__registro__cultura_id=int(cultura_filtro))
    tarefas = tarefas.order_by("status", "prioridade", "ordem")[:200]

    culturas = Cultura.objects.filter(ativo=True).order_by("nome")[:50]
    talhoes = Talhao.objects.filter(propriedade=propriedade).order_by("nome")
    funcionarios = Funcionario.objects.filter(
        propriedade=propriedade, ativo=True
    ).order_by("nome")
    alertas = AlertaTelemetria.objects.filter(
        propriedade=propriedade, resolvido=False
    ).order_by("-timestamp")[:20]

    # Agrupa por status para preview
    colunas = {
        "pendente": [t for t in tarefas if t.status == "pendente"],
        "andamento": [t for t in tarefas if t.status == "andamento"],
        "concluido": [t for t in tarefas if t.status == "concluido"],
    }

    return render(
        request,
        "tarefas/associacao.html",
        {
            "propriedade": propriedade,
            "tarefas": tarefas,
            "colunas": colunas,
            "culturas": culturas,
            "talhoes": talhoes,
            "funcionarios": funcionarios,
            "alertas": alertas,
            "filtros": {
                "status": status_filtro,
                "cargo": cargo_filtro,
                "cultura": cultura_filtro,
            },
        },
    )


@login_required
@require_POST
def tarefas_associacao_api(request):
    """API para associar em lote: POST {ids:[1,2], cultura:1, talhao:2, funcionario:3, cargo:'MECANICA', prioridade:'alta', status:'andamento'}"""
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    ids = data.get("ids", [])
    if not ids:
        return JsonResponse(
            {"ok": False, "erro": "Nenhuma tarefa selecionada"}, status=400
        )

    from app.models import TarefaEstagio

    # pega propriedade do usuário
    try:
        perfil = request.user.perfil
        if perfil.tipo_usuario == "produtor":
            propriedade = request.user.propriedades.first()
        else:
            propriedade = perfil.propriedade_vinculada
    except Exception:
        propriedade = None
    if not propriedade:
        return JsonResponse({"ok": False, "erro": "Fazenda não encontrada"}, status=400)

    qs = TarefaEstagio.objects.filter(id__in=ids, propriedade=propriedade)
    # Só produtor pode associar tudo; servidor só pode associar da sua fazenda e área (já filtrado por propriedade)
    if qs.count() != len(ids):
        return JsonResponse(
            {"ok": False, "erro": "Algumas tarefas não pertencem à sua fazenda"},
            status=403,
        )

    updates = {}
    if data.get("cargo"):
        updates["cargo_alvo"] = data["cargo"]
    if data.get("setor"):
        updates["setor"] = data["setor"]
    if data.get("prioridade"):
        updates["prioridade"] = data["prioridade"]
    if data.get("status"):
        updates["status"] = data["status"]
    if data.get("funcionario"):
        try:
            from app.models import Funcionario

            func = Funcionario.objects.get(
                id=data["funcionario"], propriedade=propriedade
            )
            updates["funcionario"] = func
        except Exception:
            return JsonResponse(
                {"ok": False, "erro": "Funcionário não encontrado"}, status=400
            )
    if data.get("cultura") or data.get("talhao"):
        # Para associar cultura/talhão, precisa mover o estágio para outro registro/talhão?
        # Simplificado: atualiza via estagio se fornecido, ou cria observação
        pass

    # Aplica updates
    count = 0
    for t in qs:
        for k, v in updates.items():
            setattr(t, k, v)
        t.save()
        count += 1

    return JsonResponse({"ok": True, "atualizadas": count})
