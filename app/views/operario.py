import json

import structlog
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required
from app.models import *

from .utils import *

logger = structlog.get_logger(__name__)


@kanban_required
def operario_kanban_view(request):
    """Kanban para operários/servidores — mostra tarefas da fazenda filtradas por área/cargo + drag&drop."""
    from django.db.models import Q

    from app.models import AlertaTelemetria, TarefaEstagio

    propriedade = get_user_propriedade(request.user)
    funcionario = get_user_funcionario(request.user)
    try:
        perfil = request.user.perfil
        is_servidor = perfil.tipo_usuario != "produtor"
        area = perfil.area_servidor or ""
        pode_criar = (
            perfil.get_dashboard_config().get("pode_criar", True)
            if hasattr(perfil, "get_dashboard_config")
            else True
        )
    except Exception:
        # FALHA FECHADA. Se a leitura do perfil falhar, nao concede privilegio.
        # Falha para o MENOS privilegio: ve o kanban do proprio produtor, que
        # e' o que ja veria, e nao escreve nada.
        logger.warning(
            "kanban_perfil_ilegivel",
            user_id=request.user.pk,
            path=request.path,
            hint="fallback sem privilegio; ver get_dashboard_config",
            exc_info=True,
        )
        is_servidor = False
        area = ""
        pode_criar = False

    # Queryset base por propriedade
    if propriedade:
        # Tenta buscar tarefas denormalizadas por propriedade + cargo/area do servidor
        base_qs = TarefaEstagio.objects.filter(
            Q(propriedade=propriedade) | Q(estagio__registro__user=propriedade.user)
        ).select_related("estagio", "estagio__registro", "funcionario", "propriedade")
        # Servidor vê só da sua área se filtrado
        if is_servidor and area and area != "GERAL":
            # mostra tarefas do seu cargo/área ou sem cargo (geral) ou diretamente atribuídas a ele
            base_qs = base_qs.filter(
                Q(cargo_alvo__iexact=area)
                | Q(cargo_alvo="")
                | Q(funcionario=funcionario)
                | Q(setor__icontains=area)
            )
        elif is_servidor:
            base_qs = base_qs.filter(
                Q(funcionario=funcionario)
                | Q(cargo_alvo="")
                | Q(funcionario__isnull=True)
            )
    else:
        base_qs = TarefaEstagio.objects.none()

    # Se produtor e sem tarefas, cria demos para apresentação (FEBRACE)
    #
    # GATED: o mesmo portao do login demo (app/views/auth.py:458) — DEBUG ou
    # AMPLIAGRO_DEMO_ENABLED. Sem isto, RENDERIZAR a pagina de um produtor sem
    # tarefas gravava seis tarefas falsas e um RegistroProducao "Demo" na
    # fazenda REAL dele, indistinguiveis das verdadeiras. E' o inverso do
    # `sem_dado`: aqui o vazio era preenchido com mentira. E era sticky — o
    # produtor que apagasse as suas tarefas voltava a ter seis que nao pediu.
    # REGRAS DA FASE 0 — sem `fonte_dado`, a escrita não entra:
    #   - não gravar na base de dados linha sem origem declarada.
    #   - apenas mostrar template sem dados, sem criar TarefaEstagio
    #     nem RegistroProducao na fazenda real do usuario.
    if propriedade:
        demo_habilitado = settings.DEBUG or getattr(
            settings, "AMPLIAGRO_DEMO_ENABLED", False
        )
        if not is_servidor and propriedade and not base_qs.exists() and demo_habilitado:
            # REGRAS DA FASE 0 — sem `fonte_dado`, a escrita não entra:
            #   - não gravar na base de dados linha sem origem declarada.
            #   - apenas mostrar template sem dados, sem criar TarefaEstagio
            #     nem RegistroProducao na fazenda real do usuario.
            # DEMO: cria dados de demonstracao com nomes claros de "Demo"
            # para nao serem confundidos com dados reais.
            from app.models import Cultura, RegistroProducao, EstagioCultura

            cultura_demo, _ = Cultura.objects.get_or_create(
                nome="Soja Demo", grupo="graos", ativo=True
            )
            reg = RegistroProducao.objects.create(
                user=request.user,
                cultura=cultura_demo,
                grupo="vegetal",
                nome="Safra Demo 2024/25",
                status="ativo",
                location="Talhao Demo",
                data_registro=timezone.now().date(),
            )
            # Cria estagios primeiro
            estagio_plantio = EstagioCultura.objects.create(
                registro=reg, nome="Plantio", ordem=1, concluido=False
            )
            estagio_crescimento = EstagioCultura.objects.create(
                registro=reg, nome="Crescimento", ordem=2, concluido=False
            )
            estagio_colheita = EstagioCultura.objects.create(
                registro=reg, nome="Colheita", ordem=3, concluido=False
            )
            # Cria tarefas demo
            tarefas_demo = [
                ("[DEMO] Preparar solo", estagio_plantio, "TRATORISTA"),
                ("[DEMO] Plantio direto", estagio_plantio, "TRATORISTA"),
                ("[DEMO] Aplicar herbicida", estagio_crescimento, "TRATORISTA"),
                ("[DEMO] Adubar cobertura", estagio_crescimento, "TRATORISTA"),
                ("[DEMO] Monitorar pragas", estagio_crescimento, "AGRONOMO"),
                ("[DEMO] Colher soja", estagio_colheita, "TRATORISTA"),
            ]
            for i, (nome, estagio, cargo) in enumerate(tarefas_demo, 1):
                TarefaEstagio.objects.create(
                    estagio=estagio,
                    descricao=nome,
                    cargo_alvo=cargo,
                    setor="CAMPO",
                    concluida=False,
                    ordem=i,
                )

    tarefas = list(base_qs.order_by("ordem", "-criado_em")[:100])
    # Agrupa
    colunas = {
        "pendente": [t for t in tarefas if t.status == "pendente"],
        "andamento": [t for t in tarefas if t.status == "andamento"],
        "concluido": [t for t in tarefas if t.status == "concluido"],
    }
    # Compat: se status ainda pendente mas concluida True, move para concluido
    for t in tarefas:
        if t.concluida and t.status != "concluido":
            colunas["concluido"].append(t)
            if t in colunas["pendente"]:
                colunas["pendente"].remove(t)
            if t in colunas["andamento"]:
                colunas["andamento"].remove(t)

    alertas = []
    if propriedade:
        alertas = list(
            AlertaTelemetria.objects.filter(
                propriedade=propriedade, resolvido=False
            ).order_by("-timestamp")[:8]
        )
        # filtra alertas por área para servidor
        if is_servidor and area == "MECANICA":
            alertas = [
                a
                for a in alertas
                if a.metric in ["temp_motor", "combustivel", "bateria", "nivel"]
            ]
        elif is_servidor and area == "CAMPO":
            alertas = [
                a
                for a in alertas
                if a.metric in ["umidade_solo", "chuva", "temperatura"]
            ]

    context = {
        "propriedade": propriedade,
        "funcionario": funcionario,
        "is_operario": is_servidor,
        "is_servidor": is_servidor,
        "area": area,
        "pode_criar": pode_criar,
        "tarefas": tarefas,
        "colunas": colunas,
        "alertas": alertas,
        "total": len(tarefas),
    }
    return render(request, "operario/kanban.html", context)


@perfil_required
def operario_perfil_view(request):
    """Perfil do operário - dados pessoais, ponto, EPIs, etc."""
    propriedade = get_user_propriedade(request.user)
    funcionario = get_user_funcionario(request.user)

    context = {
        "propriedade": propriedade,
        "funcionario": funcionario,
        "is_operario": True,
    }
    return render(request, "operario/perfil.html", context)


@produtor_required
def operario_registrar_view(request):
    """Página para o produtor cadastrar operários com login"""
    propriedades = Propriedade.objects.filter(user=request.user)
    funcionarios = Funcionario.objects.filter(propriedade__user=request.user)

    context = {
        "propriedades": propriedades,
        "funcionarios": funcionarios,
    }
    return render(request, "operario/registrar.html", context)


@require_POST
@produtor_required
def operario_criar_login(request):
    """API para criar login para um funcionário existente"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    funcionario_id = data.get("funcionario_id")
    username = data.get("username")
    senha = data.get("senha")

    if not funcionario_id or not username or not senha:
        return JsonResponse(
            {"ok": False, "erro": "Funcionário, usuário e senha são obrigatórios"},
            status=400,
        )

    try:
        funcionario = Funcionario.objects.get(
            id=funcionario_id, propriedade__user=request.user
        )
    except Funcionario.DoesNotExist:
        return JsonResponse(
            {"ok": False, "erro": "Funcionário não encontrado"}, status=404
        )

    if User.objects.filter(username__iexact=username).exists():
        return JsonResponse(
            {"ok": False, "erro": "Este nome de usuário já está em uso"}, status=400
        )

    # Mesma política do cadastro de produtor: `create_user` não roda
    # AUTH_PASSWORD_VALIDATORS, então sem esta checagem o produtor criava login
    # de funcionário com senha "1".
    try:
        password_validation.validate_password(senha, None)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "erro": "; ".join(exc.messages)}, status=400)

    # Definir nome da fazenda para login se não tiver
    if not funcionario.nome_fazenda_login:
        funcionario.nome_fazenda_login = funcionario.propriedade.nome
        funcionario.save()

    # Criar usuário + perfil em transação: se qualquer passo falhar, não sobra
    # login pela metade no banco.
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=senha,
                email=funcionario.email or "",
                first_name=funcionario.nome.split()[0] if funcionario.nome else "",
            )

            # Criar perfil — suporta servidor (nova área) ou operário legado.
            # O sinal `garantir_perfil_usuario` (app/signals.py) já criou o
            # perfil no post_save do User; aqui se define o papel, então é
            # `update_or_create` e não `create` (UNIQUE(user_id)).
            area = (data.get("area_servidor") or "").strip().upper()
            # valida area
            areas_validas = [c[0] for c in PerfilUsuario.AREA_SERVIDOR_CHOICES]
            if area and area not in areas_validas:
                area = ""
            # se area informada, cria como servidor; senão mantém operario
            tipo = "servidor" if area else "operario"
            # permissoes custom (opcional)
            permissoes = data.get("permissoes") or {}
            if not isinstance(permissoes, dict):
                permissoes = {}
            perfil, _ = PerfilUsuario.objects.update_or_create(
                user=user,
                defaults={
                    "tipo_usuario": tipo,
                    "area_servidor": area or "GERAL",
                    "permissoes": permissoes,
                    "propriedade_vinculada": funcionario.propriedade,
                    "funcionario": funcionario,
                    "vinculado_por": request.user,
                    "ativo_servidor": True,
                },
            )

            # Vincular funcionário ao usuário
            funcionario.user = user
            funcionario.save()
    except IntegrityError:
        return JsonResponse(
            {"ok": False, "erro": "Este nome de usuário já está em uso"}, status=400
        )

    return JsonResponse(
        {
            "ok": True,
            "user_id": user.id,
            "username": user.username,
            "tipo_usuario": tipo,
            "area_servidor": perfil.area_servidor,
            "nome_fazenda_login": funcionario.nome_fazenda_login,
        }
    )


@require_POST
@produtor_required
def operario_remover_login(request):
    """API para remover login de um funcionário"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    funcionario_id = data.get("funcionario_id")

    if not funcionario_id:
        return JsonResponse(
            {"ok": False, "erro": "ID do funcionário obrigatório"}, status=400
        )

    try:
        funcionario = Funcionario.objects.get(
            id=funcionario_id, propriedade__user=request.user
        )
    except Funcionario.DoesNotExist:
        return JsonResponse(
            {"ok": False, "erro": "Funcionário não encontrado"}, status=404
        )

    if funcionario.user:
        user = funcionario.user
        funcionario.user = None
        funcionario.save()
        user.delete()  # Remove o usuário e o perfil (CASCADE)
        return JsonResponse({"ok": True, "message": "Login removido com sucesso"})

    return JsonResponse(
        {"ok": False, "erro": "Funcionário não possui login cadastrado"}, status=400
    )


@login_required
@hierarquia_required("cadastro-funcionario")
def adicionar_funcionario_view(request):
    """Placeholder for adding funcionario"""
    return render(
        request,
        "cadastro-funcionario.html",
        {"propriedades": Propriedade.objects.filter(user=request.user)},
    )
