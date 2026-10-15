import json

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required, propriedades_visiveis
from app.models import *

from .utils import *


@login_required
@hierarquia_required("cadastro-animal")
def cadastro_animal_view(request):
    from app.hierarquia import propriedades_visiveis

    props = propriedades_visiveis(request.user)
    propriedades = props
    animais = Animal.objects.filter(propriedade__in=props).select_related("propriedade")
    producoes = (
        ProducaoAnimal.objects.filter(animal__propriedade__in=props)
        .select_related("animal")
        .order_by("-data")[:50]
    )

    # Stats
    total_cabecas = sum(a.quantidade for a in animais)
    total_especies = len({a.especie for a in animais})
    from datetime import date

    mes_atual = date.today().replace(day=1)
    producao_mes = sum(
        float(p.quantidade_produzida) for p in producoes if p.data >= mes_atual
    )
    valor_estimado = sum(float(p.valor_estimado or 0) for p in producoes)

    animais_stats = {
        "total_cabecas": total_cabecas,
        "total_especies": total_especies,
        "producao_mes": producao_mes,
        "valor_estimado": valor_estimado,
    }

    racoes = (
        Racao.objects.filter(propriedade__in=props)
        .select_related("propriedade")
        .order_by("-criado_em")[:50]
    )

    from datetime import date

    return render(
        request,
        "cadastro-animal.html",
        {
            "propriedades": propriedades,
            "animais": animais,
            "producoes": producoes,
            "racoes": racoes,
            "animais_stats": animais_stats,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-apiario")
def cadastro_apiario_view(request):
    props = propriedades_visiveis(request.user)
    propriedades = props
    colmeias = ApiarioColmeia.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade")
    producoes = (
        ProducaoApiario.objects.filter(colmeia__propriedade__user=request.user)
        .select_related("colmeia")
        .order_by("-data_extracao")[:50]
    )

    colmeias_ativas = colmeias.filter(ativa=True).count()
    from datetime import date

    mes_atual = date.today().replace(day=1)
    mel_mes = sum(
        float(p.producao_mel_kg) for p in producoes if p.data_extracao >= mes_atual
    )
    valor_mel = sum(float(p.valor_venda or 0) for p in producoes)

    return render(
        request,
        "cadastro-apiario.html",
        {
            "propriedades": propriedades,
            "colmeias": colmeias,
            "producoes": producoes,
            "colmeias_ativas": colmeias_ativas,
            "mel_mes": mel_mes,
            "valor_mel": valor_mel,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-aquatico")
def cadastro_aquatico_view(request):
    from datetime import date

    props = propriedades_visiveis(request.user)
    propriedades = props
    lotes = LoteAquatico.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )
    despescas = (
        Despesca.objects.filter(lote__propriedade__user=request.user)
        .select_related("lote")
        .order_by("-data")[:50]
    )

    # Stats
    total_individuos = sum(l.quantidade for l in lotes)
    total_especies = len({l.especie for l in lotes})
    mes_atual = date.today().replace(day=1)
    despesca_mes = sum(float(d.quantidade_kg) for d in despescas if d.data >= mes_atual)
    valor_estimado = sum(float(d.valor_estimado or 0) for d in despescas)

    aquaticos_stats = {
        "total_individuos": total_individuos,
        "total_especies": total_especies,
        "despesca_mes": despesca_mes,
        "valor_estimado": valor_estimado,
    }

    return render(
        request,
        "cadastro-aquatico.html",
        {
            "propriedades": propriedades,
            "lotes": lotes,
            "despescas": despescas,
            "aquaticos_stats": aquaticos_stats,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-caminhao")
def cadastro_caminhao_view(request):
    # cadastro-caminhao.html não existia (500) → reutiliza logistica-caminhao.html que já tem CRUD completo
    from app.models import Propriedade

    props = propriedades_visiveis(request.user)
    propriedades = props
    # Maquinarios tipo CAMINHAO para pré-popular stats se template precisar
    caminhoes = Maquinario.objects.filter(
        propriedade__user=request.user, tipo="CAMINHAO"
    ).select_related("propriedade")
    return render(
        request,
        "logistica-caminhao.html",
        {"propriedades": propriedades, "caminhoes": caminhoes},
    )


@login_required
@hierarquia_required("cadastro-estoque")
def cadastro_estoque_view(request):
    props = propriedades_visiveis(request.user)
    propriedades = props
    itens = EstoqueItem.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )

    from datetime import date, timedelta

    today = date.today()
    vencimento_limite = today + timedelta(days=30)
    qtd_total = sum(float(i.quantidade) for i in itens)
    itens_vencendo = itens.filter(
        data_validade__lte=vencimento_limite, data_validade__gte=today
    ).count()
    itens_vencendo_lista = itens.filter(
        data_validade__lte=vencimento_limite, data_validade__gte=today
    ).order_by("data_validade")[:20]
    # Adiciona dias_restantes
    for i in itens_vencendo_lista:
        i.dias_restantes = (i.data_validade - today).days
    categorias_count = len({i.categoria for i in itens})

    return render(
        request,
        "cadastro-estoque.html",
        {
            "propriedades": propriedades,
            "itens": itens,
            "qtd_total": qtd_total,
            "itens_vencendo": itens_vencendo,
            "itens_vencendo_lista": itens_vencendo_lista,
            "categorias_count": categorias_count,
            "today": today,
            "vencimento_limite": vencimento_limite,
        },
    )


@login_required
@hierarquia_required("cadastro-financeiro")
def cadastro_financeiro_view(request):
    from django.db.models import Count, Q, Sum
    from django.db.models.functions import TruncMonth

    props = propriedades_visiveis(request.user)
    propriedades = props
    lancamentos = (
        LancamentoFinanceiro.objects.filter(propriedade__user=request.user)
        .select_related("propriedade", "talhao", "safra")
        .order_by("-data")
    )

    # agregação DB em vez de 24 queries + loops Python
    agg = lancamentos.aggregate(
        receitas_total=Sum("valor", filter=Q(tipo="RECEITA")),
        despesas_total=Sum("valor", filter=Q(tipo="DESPESA")),
    )
    receitas_total = float(agg["receitas_total"] or 0)
    despesas_total = float(agg["despesas_total"] or 0)
    saldo_total = receitas_total - despesas_total

    from datetime import date

    mes_atual = date.today().replace(day=1)
    lancamentos_mes = lancamentos.filter(data__gte=mes_atual).count()

    # Resumo mensal dos últimos 12 meses — 1 query com TruncMonth
    meses_pt = [
        "Jan",
        "Fev",
        "Mar",
        "Abr",
        "Mai",
        "Jun",
        "Jul",
        "Ago",
        "Set",
        "Out",
        "Nov",
        "Dez",
    ]
    trunc = (
        lancamentos.filter(data__gte=date(mes_atual.year - 1, mes_atual.month, 1))
        .annotate(mes=TruncMonth("data"))
        .values("mes")
        .annotate(
            receitas=Sum("valor", filter=Q(tipo="RECEITA")),
            despesas=Sum("valor", filter=Q(tipo="DESPESA")),
            count=Count("id"),
        )
        .order_by("mes")
    )

    # mapa mes -> dados (TruncMonth retorna date ou datetime dependendo do backend)
    def _to_date(v):
        if not v:
            return None
        return v.date() if hasattr(v, "date") and callable(v.date) else v

    mapa = {
        _to_date(r["mes"]).replace(day=1): r
        for r in trunc
        if r["mes"] and _to_date(r["mes"])
    }
    resumo_mensal = []
    for i in range(11, -1, -1):
        # andar mês a mês corretamente
        y, m = mes_atual.year, mes_atual.month - i
        while m <= 0:
            m += 12
            y -= 1
        mes_ref = date(y, m, 1)
        r = mapa.get(mes_ref, {})
        rec = float(r.get("receitas") or 0)
        des = float(r.get("despesas") or 0)
        resumo_mensal.append(
            {
                "mes": f"{meses_pt[mes_ref.month - 1]}/{mes_ref.year}",
                "receitas": rec,
                "despesas": des,
                "saldo": rec - des,
                "count": r.get("count") or 0,
            }
        )

    from datetime import date

    from app.models.financeiro_banco import ContaBancaria

    return render(
        request,
        "cadastro-financeiro.html",
        {
            "propriedades": propriedades,
            "contas_bancarias": ContaBancaria.objects.filter(
                propriedade__user=request.user
            ),
            "lancamentos": lancamentos[:100],
            "receitas_total": receitas_total,
            "despesas_total": despesas_total,
            "saldo_total": saldo_total,
            "lancamentos_mes": lancamentos_mes,
            "resumo_mensal": resumo_mensal,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-funcionario")
def cadastro_funcionario_view(request):
    props = propriedades_visiveis(request.user)
    propriedades = props
    funcionarios = Funcionario.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade", "user")

    funcionarios_ativos = funcionarios.filter(ativo=True).count()
    folha_mensal = sum(float(f.salario) for f in funcionarios if f.ativo)
    funcionarios_com_login = [f for f in funcionarios if f.user]
    funcionarios_sem_login = [f for f in funcionarios if not f.user and f.ativo]

    from datetime import date

    return render(
        request,
        "cadastro-funcionario.html",
        {
            "propriedades": propriedades,
            "funcionarios": funcionarios,
            "funcionarios_ativos": funcionarios_ativos,
            "folha_mensal": folha_mensal,
            "funcionarios_com_login": funcionarios_com_login,
            "funcionarios_sem_login": funcionarios_sem_login,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-insumo")
def cadastro_insumo_view(request):
    props = propriedades_visiveis(request.user)
    propriedades = props
    insumos = Insumo.objects.filter(propriedade__user=request.user).select_related(
        "propriedade"
    )
    aplicacoes = (
        AplicacaoInsumo.objects.filter(insumo__propriedade__user=request.user)
        .select_related("insumo", "talhao")
        .order_by("-data")[:50]
    )
    talhoes = Talhao.objects.filter(propriedade__user=request.user)

    qtd_total = sum(float(i.quantidade) for i in insumos)
    valor_estoque = sum(
        float(i.quantidade) * float(i.valor_unitario or 0) for i in insumos
    )
    categorias_count = len({i.categoria for i in insumos})

    from datetime import date

    return render(
        request,
        "cadastro-insumo.html",
        {
            "propriedades": propriedades,
            "insumos": insumos,
            "aplicacoes": aplicacoes,
            "talhoes": talhoes,
            "qtd_total": qtd_total,
            "valor_estoque": valor_estoque,
            "categorias_count": categorias_count,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-maquinario")
def cadastro_maquinario_view(request):
    props = propriedades_visiveis(request.user)
    propriedades = props
    maquinarios = Maquinario.objects.filter(
        propriedade__user=request.user
    ).select_related("propriedade")

    maquinarios_ativos = maquinarios.filter(ativo=True).count()
    maquinarios_em_manut = maquinarios.filter(
        proxima_manutencao__isnull=False, ativo=True
    ).count()
    horas_total = sum(float(m.horas_uso) for m in maquinarios)

    # Manutenções placeholder (futuro: modelo ManutencaoMaquinario)
    manutencoes = []

    from datetime import date

    return render(
        request,
        "cadastro-maquinario.html",
        {
            "propriedades": propriedades,
            "maquinarios": maquinarios,
            "maquinarios_ativos": maquinarios_ativos,
            "maquinarios_em_manut": maquinarios_em_manut,
            "horas_total": horas_total,
            "manutencoes": manutencoes,
            "today": date.today(),
        },
    )


@login_required
@hierarquia_required("cadastro-propriedade")
def cadastro_propriedade_view(request):
    props = propriedades_visiveis(request.user)
    propriedades = props
    try:
        from app.models.holding import Holding

        holdings = Holding.objects.filter(membros=request.user)
    except Exception:
        holdings = []
    area_total = sum(float(p.area_total) for p in propriedades)
    ufs_count = len({p.uf for p in propriedades if p.uf})
    biomas_count = len({p.bioma for p in propriedades if p.bioma})

    return render(
        request,
        "cadastro-propriedade.html",
        {
            "propriedades": propriedades,
            "holdings": holdings,
            "area_total": area_total,
            "ufs_count": ufs_count,
            "biomas_count": biomas_count,
        },
    )


@login_required
@hierarquia_required("cadastro-rota")
def cadastro_rota_view(request):
    # cadastro-rota.html não existia (500) → reutiliza logistica-rotas.html (model Rota ainda não existe, API retorna placeholder)
    from app.models import Propriedade

    props = propriedades_visiveis(request.user)
    propriedades = props
    return render(
        request,
        "logistica-rotas.html",
        {"propriedades": propriedades},
    )


@login_required
@hierarquia_required("cadastro-safra")
def cadastro_safra_view(request):
    from app.hierarquia import propriedades_visiveis

    props = propriedades_visiveis(request.user)
    propriedades = props
    culturas = Cultura.objects.all()
    # fix: filtra por propriedade__user (safra tem FK direta) para não perder safras sem talhão
    safras = (
        Safra.objects.filter(propriedade__in=props)
        .select_related("propriedade", "cultura", "talhao")
        .order_by("-ano", "-id")
    )

    area_total = sum(float(s.area_plantada) for s in safras)
    producao_total = sum(float(s.producao_total or 0) for s in safras)
    receita_total = sum(float(s.receita_estimada or 0) for s in safras)

    from datetime import date

    ano_atual = date.today().year
    anos = list(range(ano_atual - 5, ano_atual + 5))

    # Resumo por cultura — fix filtro direto por propriedade
    from django.db.models import Count, Sum

    resumo_culturas = (
        Safra.objects.filter(propriedade__in=props)
        .values("cultura__nome")
        .annotate(
            count=Count("id"),
            area_total=Sum("area_plantada"),
            producao_total=Sum("producao_total"),
            receita_total=Sum("receita_estimada"),
        )
        .order_by("-area_total")
    )

    for r in resumo_culturas:
        if r["area_total"]:
            r["produtividade_media"] = float(r["producao_total"] or 0) / float(
                r["area_total"]
            )
        else:
            r["produtividade_media"] = 0

    return render(
        request,
        "cadastro-safra.html",
        {
            "propriedades": propriedades,
            "culturas": culturas,
            "safras": safras,
            "area_total": area_total,
            "producao_total": producao_total,
            "receita_total": receita_total,
            "anos": anos,
            "ano_atual": ano_atual,
            "resumo_culturas": resumo_culturas,
        },
    )


@login_required
def cadastro_cultura_view(request):
    culturas = Cultura.objects.all()
    props = propriedades_visiveis(request.user)
    propriedades = props
    talhoes = Talhao.objects.filter(propriedade__user=request.user)
    grupos = Cultura.GRUPOS
    meses_nomes = [
        "",
        "Jan",
        "Fev",
        "Mar",
        "Abr",
        "Mai",
        "Jun",
        "Jul",
        "Ago",
        "Set",
        "Out",
        "Nov",
        "Dez",
    ]
    if request.method == "POST":
        data = (
            json.loads(request.body.decode("utf-8"))
            if request.content_type == "application/json"
            else request.POST
        )
        nome = (data.get("nome") or "").strip()
        grupo = (data.get("grupo") or "outro").strip()
        if len(nome) < 2:
            return JsonResponse({"error": "Nome obrigatório (mín 2)"}, status=400)
        # Grupo óbvio não pode ser alterado: valida contra config
        try:
            from app.api.culture_config import load_cultures_config

            cfg = load_cultures_config()
            # se cultura conhecida, força grupo correto
            for g in cfg.get("groups", []):
                for sg in g.get("subgroups", []):
                    for c in sg.get("cultures", []):
                        if (
                            c.get("django_nome", "").lower() == nome.lower()
                            or c.get("title", "").lower() == nome.lower()
                        ):
                            grupo = c.get("django_grupo") or grupo
                            break
        except Exception:
            pass
        cultura = Cultura.objects.create(
            nome=nome,
            grupo=grupo,
            unidade_comercial=data.get("unidade_comercial") or "sacas",
            ibge_codigo=data.get("ibge_codigo") or None,
            chave_mercado=data.get("chave_mercado") or "",
            ciclo_dias=data.get("ciclo_dias") or None,
            janela_plantio_inicio=data.get("janela_plantio_inicio") or None,
            janela_plantio_fim=data.get("janela_plantio_fim") or None,
        )
        return JsonResponse({"ok": True, "id": cultura.id, "nome": cultura.nome})
    return render(
        request,
        "cadastro-cultura.html",
        {
            "culturas": culturas,
            "propriedades": propriedades,
            "talhoes": talhoes,
            "grupos": grupos,
            "meses_nomes": meses_nomes,
        },
    )


@login_required
@hierarquia_required("cadastro-talhao")
def cadastro_talhao_view(request):
    from app.hierarquia import propriedades_visiveis

    props = propriedades_visiveis(request.user)
    propriedades = props
    talhoes = Talhao.objects.filter(propriedade__in=props).select_related(
        "propriedade", "cultura_atual"
    )
    culturas = Cultura.objects.all()

    talhoes_ativos = talhoes.filter(ativo=True).count()
    area_total = sum(float(t.area_hectare) for t in talhoes)
    talhoes_com_geo = talhoes.exclude(coordenadas={}).count()

    return render(
        request,
        "cadastro-talhao.html",
        {
            "propriedades": propriedades,
            "talhoes": talhoes,
            "culturas": culturas,
            "talhoes_ativos": talhoes_ativos,
            "area_total": area_total,
            "talhoes_com_geo": talhoes_com_geo,
        },
    )


@login_required
def cadastro_receituario_view(request):
    safras = Safra.objects.filter(propriedade__user=request.user).select_related(
        "cultura", "talhao"
    )[:50]
    talhoes = Talhao.objects.filter(propriedade__user=request.user)
    receituarios = (
        ReceituarioAgronomico.objects.filter(safra__propriedade__user=request.user)
        .select_related("safra", "talhao")
        .order_by("-criado_em")[:50]
    )
    return render(
        request,
        "cadastro-receituario.html",
        {"safras": safras, "talhoes": talhoes, "receituarios": receituarios},
    )


@login_required
def cadastro_vra_view(request):
    safras = Safra.objects.filter(propriedade__user=request.user).select_related(
        "cultura"
    )[:50]
    talhoes = Talhao.objects.filter(propriedade__user=request.user)
    prescricoes = PrescricaoVRA.objects.filter(
        safra__propriedade__user=request.user
    ).select_related("safra", "talhao", "cultura")[:50]
    return render(
        request,
        "cadastro-vra.html",
        {"safras": safras, "talhoes": talhoes, "prescricoes": prescricoes},
    )


@login_required
def cadastro_mip_view(request):
    talhoes = Talhao.objects.filter(propriedade__user=request.user)
    culturas = Cultura.objects.all()
    mips = (
        MonitoramentoPraga.objects.filter(talhao__propriedade__user=request.user)
        .select_related("talhao", "cultura", "safra")
        .order_by("-data")[:50]
    )
    return render(
        request,
        "cadastro-mip.html",
        {"talhoes": talhoes, "culturas": culturas, "mips": mips},
    )
