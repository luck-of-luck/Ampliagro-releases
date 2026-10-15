"""
Hierarquia Ampliagro — Produtor vs Servidor
Tudo do produtor é restrito para servidores, exceto quando a área exige.

Níveis:
  produtor: 100 (dono)
  servidor ADMIN/FINANCEIRO: 80
  servidor AGRONOMIA: 70
  servidor CAMPO/PECUARIA: 60
  servidor MECANICA/ESTOQUE: 50
  servidor GERAL: 30
  operario/mecanico legado: 40-50

Cada view tem um `REQUER` (nível mínimo ou área). O servidor só entra se sua área estiver liberada
ou se sua permissão JSON liberar explicitamente (paginas_extra).
Antes de renderizar, o view chama `assert_hierarquia(request, view_name)` e devolve 403 antes de mostrar qualquer dado.
"""

from functools import wraps

from app.models.usuario import PerfilUsuario

# Nível por tipo/área
NIVEL_PRODUTOR = 100
NIVEL_AREA = {
    "ADMIN": 80,
    "FINANCEIRO": 80,
    "AGRONOMIA": 70,
    "CAMPO": 60,
    "PECUARIA": 60,
    "MECANICA": 50,
    "ESTOQUE": 50,
    "GERAL": 30,
}

# Views que são exclusivas do produtor (servidor nunca entra, mesmo com permissão extra)
PRODUTOR_SOMENTE = {
    "cadastro-propriedade",
    "cadastro-funcionario",
    "adicionar-funcionario",
    "operario_criar_login",
    "operario_remover_login",
    "config-sistema",
    "config-sistema_view",
}

# Todas as áreas de servidor. Usado pelas páginas /servidor/*, que são
# alcançáveis por qualquer área — o QUE o servidor vê é filtrado dentro da
# própria view, não aqui. Ver o bloco "MODELO DE 2 CAMADAS" em PERMISSAO_POR_VIEW.
TODAS_AS_AREAS = [
    "GERAL",
    "MECANICA",
    "CAMPO",
    "PECUARIA",
    "ESTOQUE",
    "AGRONOMIA",
    "ADMIN",
    "FINANCEIRO",
]

# Mapeamento view -> áreas que podem acessar (além do produtor que sempre pode)
# Se view não estiver aqui, é considerada "produtor somente"
PERMISSAO_POR_VIEW = {
    # Cadastros
    "cadastro-safra": ["CAMPO", "AGRONOMIA", "GERAL"],
    "cadastro-talhao": ["CAMPO", "AGRONOMIA"],
    "cadastro-insumo": ["CAMPO", "AGRONOMIA", "ESTOQUE"],
    "cadastro-maquinario": ["MECANICA"],
    "cadastro-estoque": ["MECANICA", "ESTOQUE"],
    "cadastro-animal": ["PECUARIA"],
    "cadastro-apiario": ["PECUARIA"],
    "cadastro-aquatico": ["PECUARIA"],
    "cadastro-financeiro": ["FINANCEIRO", "ADMIN"],
    "cadastro-caminhao": ["MECANICA", "ADMIN"],
    "cadastro-rota": ["MECANICA", "ADMIN"],
    # Rastreabilidade & Custos (Plano v2.0)
    "cadastro-rastro": ["ESTOQUE", "CAMPO", "AGRONOMIA"],
    "rastreabilidade-lista": ["ESTOQUE", "CAMPO", "AGRONOMIA", "GERAL"],
    "rastreabilidade-cadeia": ["ESTOQUE", "CAMPO", "AGRONOMIA", "GERAL"],
    "cadastro-centro-custo": ["ADMIN", "FINANCEIRO"],
    "custos-producao": ["ADMIN", "FINANCEIRO", "GERAL"],
    # Orcado x realizado por talhao. Le a mesma coisa que `custos-producao`
    # (dinheiro do produtor) mas compara com o orcado do Plano de Safra -
    # por isso pede FINANCEIRO, que `custos-producao` exige tambem. `GERAL`
    # fica de fora de proposito: quem ve o custo gasto de todos os talhoes
    # vai ver aqui o desvio face ao que foi planeado, e essa e' uma leitura
    # de gestao, nao de campo.
    "orcamento-realizado": ["ADMIN", "FINANCEIRO"],
    "dre-view": ["ADMIN", "FINANCEIRO"],
    "lancamento-detalhado": ["ADMIN", "FINANCEIRO"],
    # Ferramentas / leitura
    "telemetria": ["MECANICA", "CAMPO", "AGRONOMIA", "PECUARIA", "GERAL"],
    "sensores": ["MECANICA", "CAMPO", "AGRONOMIA"],
    "dispositivos": ["MECANICA", "CAMPO"],
    "mapa": ["CAMPO", "AGRONOMIA", "MECANICA"],
    "previsao-clima": ["CAMPO", "AGRONOMIA", "PECUARIA"],
    "previsao-safra": ["CAMPO", "AGRONOMIA"],
    # ── Páginas do servidor: liberadas para TODAS as áreas ────────────────
    #
    # MODELO DE 2 CAMADAS (leia antes de "apertar" esta lista):
    #   camada 1 — este mapa: a view é ALCANÇÁVEL?
    #   camada 2 — dentro da view: o que o servidor REALMENTE vê?
    #
    # Todas as páginas /servidor/* passam pela camada 1 para qualquer área, e
    # quem restringe o conteúdo é a própria view, pelo area_servidor:
    #   estoque    -> só MECANICA/ESTOQUE/ADMIN/GERAL; MECANICA só vê PECA/FERRAMENTA
    #   agenda     -> fora de GERAL, filtra por cargo_alvo/setor da área
    #   alertas    -> MECANICA vê métricas de motor, CAMPO vê métricas de solo
    #   dashboard  -> as cards por área (MECANICA/CAMPO/PECUARIA)
    #
    # Apertar a lista aqui NÃO aumenta a segurança: só troca o 403 da camada 1
    # por um 403 da camada 2 (mesma tela de erro, mesma ausencia de dados) e
    # quebra o contrato em que o produtor libera acesso via
    # permissoes["paginas_extra"], verificado em pode_acessar() ANTES desta lista.
    "servidor-dashboard": TODAS_AS_AREAS,
    "servidor-config": TODAS_AS_AREAS,
    "servidor-estoque": TODAS_AS_AREAS,
    "servidor-agenda": TODAS_AS_AREAS,
    "servidor-alertas": TODAS_AS_AREAS,
    "servidor-kanban": TODAS_AS_AREAS,
    "operario-kanban": TODAS_AS_AREAS,
    # Gestão / relatórios — só produtor + ADMIN
    "resumo-gerencial": ["ADMIN", "FINANCEIRO"],
    "dashboard-os": ["ADMIN"],
    "estoque-geral": ["ESTOQUE", "MECANICA", "ADMIN"],
    "equipe-agenda": ["ADMIN", "GERAL"],
    # Ferramentas — faltavam mapeamentos (viravam 403 produtor-somente)
    "ndvi-view": ["AGRONOMIA", "CAMPO", "GERAL"],
    "compliance-view": ["AGRONOMIA", "CAMPO", "GERAL", "ADMIN"],
    "cashflow_view": ["ADMIN", "FINANCEIRO"],
    "comparativo_safras_view": ["ADMIN", "FINANCEIRO", "AGRONOMIA"],
    "simulador-financeiro": ["ADMIN", "FINANCEIRO", "GERAL"],
    "simulador-colheita": ["ADMIN", "FINANCEIRO", "CAMPO", "GERAL"],
    "simulador_lucro": ["ADMIN", "FINANCEIRO", "CAMPO", "GERAL"],
    # Perfil e tema — todos podem (servidor precisa trocar foto, tema, senha)
    "perfil-config": [
        "GERAL",
        "MECANICA",
        "CAMPO",
        "PECUARIA",
        "ESTOQUE",
        "AGRONOMIA",
        "ADMIN",
        "FINANCEIRO",
    ],
    "config-dia": [
        "GERAL",
        "MECANICA",
        "CAMPO",
        "PECUARIA",
        "ESTOQUE",
        "AGRONOMIA",
        "ADMIN",
        "FINANCEIRO",
    ],
    "config-noturno": [
        "GERAL",
        "MECANICA",
        "CAMPO",
        "PECUARIA",
        "ESTOQUE",
        "AGRONOMIA",
        "ADMIN",
        "FINANCEIRO",
    ],
    "config-sistema": [
        "GERAL",
        "MECANICA",
        "CAMPO",
        "PECUARIA",
        "ESTOQUE",
        "AGRONOMIA",
        "ADMIN",
        "FINANCEIRO",
    ],
    "config-page": [
        "GERAL",
        "MECANICA",
        "CAMPO",
        "PECUARIA",
        "ESTOQUE",
        "AGRONOMIA",
        "ADMIN",
        "FINANCEIRO",
    ],
    "perfil": [
        "GERAL",
        "MECANICA",
        "CAMPO",
        "PECUARIA",
        "ESTOQUE",
        "AGRONOMIA",
        "ADMIN",
        "FINANCEIRO",
    ],
}


def nivel_do_usuario(user):
    """Retorna nível hierárquico do usuário (int)."""
    try:
        perfil = user.perfil
    except Exception:
        return 0
    if perfil.tipo_usuario == "produtor":
        return NIVEL_PRODUTOR
    if perfil.tipo_usuario == "servidor":
        return NIVEL_AREA.get(perfil.area_servidor or "GERAL", 30)
    # legados operario/mecanico etc
    legacy = {"administrativo": 80, "agronomo": 70, "mecanico": 50, "operario": 30}
    return legacy.get(perfil.tipo_usuario, 30)


def propriedades_visiveis(user):
    """Propriedades que o usuário pode ver.

    MEDIDO 2026-10-05 (agente 7). Antes disto isto tinha um **tecto duro de 3**:
    as proprias, mais `perfil.propriedade_vinculada_id` (uma), mais
    `perfil.funcionario.propriedade_id` (uma). Nao ha excecao e nao ha caminho
    para a quarta. Um agronomo com 12 clientes batia nele, e um contador que
    servia 40 fazendas batia nele — que sao os dois clientes que os
    concorrentes Serve (o Aegro vende multi-cliente, a Lucro Rural vende
    "produtor e contador" na mesma propriedade).

    Agora as tres fontes somam-se a `MembroPropriedade`, que nao tem tecto.
    As tres **antigas** ficam, de proposito:

    - `propriedade_vinculada_id` e' o caminho legado do "servidor" e ja e'
      usado por sinais e por `pode_acessar`; remove-lo seria umalthide curto.
    - `funcionario.propriedade_id` e' o vinculo do trabalhador rural, e um
      trabalhador que pertence a fazenda de outro tem de a ver.
    - Ambas sao `UNION` com as novas, entao quem tinha acesso antes nao o
      perde — a mudanca e' so **aditiva**, e e' por isso que nenhum teste
      antigo de tenancy parte.

    **Isolar continua intacto.** `MembroPropriedade` da acesso por linha e
    nomeado; nao da acesso por consequencia. Um membro de uma fazenda nao
    ganha acesso as outras do mesmo dono — e' essa linha, ou nada.
    """
    from app.models import MembroPropriedade, Propriedade

    qs = Propriedade.objects.filter(user=user)

    try:
        # MEDIDO 2026-10-05. Antes era `perfil = user.perfil`, e isso **lia uma
        # copia em cache**. O sinal `garantir_perfil_usuario`
        # (`app/signals.py`) acede a `user.perfil` ao criar a conta, o que
        # popula o cache do descritor inverso one-to-one. A partir dai, qualquer
        # codigo que carregue o perfil por outra via e lhe escreva
        # — `PerfilUsuario.objects.get_or_create(user=u)` e depois
        # `perfil.propriedade_vinculada = p; perfil.save()` — grava na base de
        # dados e **nao** no objecto em cache. Reproduzido:
        #
        #     db diz: 2
        #     user.perfil.propriedade_vinculada_id: None
        #
        # Ou seja: o vinculo estava gravado e `propriedades_visiveis` nao o via.
        # Nao e' um caso de teste — e' o caminho normal de "vincular um servidor
        # a uma propriedade".
        #
        # A correccao e' reler do banco em vez de confiar no cache. Custa uma
        # query e a uma funcao que ja faz varias.
        from app.models import PerfilUsuario

        perfil = PerfilUsuario.objects.filter(user=user).first()
        if perfil is None:
            # Sem perfil, so as proprias. Fail-closed: um `User` sem
            # `PerfilUsuario` nao e' um produtor, e trata-lo como "acesso
            # total" abriria brecha.
            return qs
    except Exception:
        return qs

    ids = set()

    # 1. Membros: a fonte nova, sem tecto.
    ids.update(
        MembroPropriedade.objects.filter(user=user, ativo=True).values_list(
            "propriedade_id", flat=True
        )
    )

    # 2. Vinculo legado do servidor (no max. uma).
    if getattr(perfil, "propriedade_vinculada_id", None):
        ids.add(perfil.propriedade_vinculada_id)

    # 3. Funcionario rural (no max. uma).
    try:
        func = getattr(perfil, "funcionario", None)
        if func and getattr(func, "propriedade_id", None):
            ids.add(func.propriedade_id)
    except Exception:
        pass

    if ids:
        qs = qs | Propriedade.objects.filter(id__in=ids)
    return qs.distinct()


def _perfil_ou_negado(user):
    """Perfil do usuário, ou None quando ele não tem um.

    Fail-closed: o chamador deve NEGAR o acesso quando isto devolve None. Um
    `User` sem `PerfilUsuario` não é um produtor — é uma conta sem papel
    definido (criada pelo admin, por import legado ou por um caminho que
    esqueceu o perfil). O sinal `garantir_perfil_usuario` (app/signals.py)
    garante que contas novas sempre tenham um, então tratar a ausência como
    "produtor de acesso total" só abria brecha.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.perfil
    except PerfilUsuario.DoesNotExist:
        return None
    except Exception:
        return None


def pode_acessar(user, view_name):
    """True se user pode acessar view_name. Produtor sempre pode."""
    if not user.is_authenticated:
        return False
    perfil = _perfil_ou_negado(user)
    if perfil is None:
        # Sem perfil definido, o usuário não é produtor. Nega por padrão —
        # mascarar aqui esconderia o dado faltando em vez de exigir correção.
        return False
    if perfil.tipo_usuario == "produtor":
        return True
    # servidor: verifica PRODUTOR_SOMENTE primeiro
    if view_name in PRODUTOR_SOMENTE:
        return False
    # verifica lista de áreas permitidas
    permitidas = PERMISSAO_POR_VIEW.get(view_name)
    if permitidas is None:
        # view não mapeada = produtor somente por padrão (segurança)
        return False
    # área do servidor está na lista?
    if perfil.area_servidor in permitidas:
        return True
    # permissão extra JSON liberada pelo produtor
    extras = (perfil.permissoes or {}).get("paginas_extra", [])
    if view_name in extras:
        return True
    # libera GERAL para todos servidores se view permite GERAL
    return bool("GERAL" in permitidas and perfil.area_servidor == "GERAL")


def assert_hierarquia(request, view_name):
    """Se não pode acessar, retorna HttpResponseForbidden com template de erro hierarquia. Caso contrário None."""
    from django.shortcuts import render

    if pode_acessar(request.user, view_name):
        return None
    # monta contexto para tela de erro
    try:
        perfil = request.user.perfil
        area = (
            perfil.get_area_servidor_display()
            if perfil.area_servidor
            else perfil.get_tipo_usuario_display()
        )
        titulo = perfil.get_dashboard_config().get("titulo", area)
    except Exception:
        area = "—"
        titulo = "—"
    return render(
        request,
        "globais/erro_hierarquia.html",
        {
            "view_name": view_name,
            "area": area,
            "titulo_area": titulo,
        },
        status=403,
    )


def hierarquia_required(view_name):
    """Decorator que bloqueia antes de renderizar se não tiver hierarquia."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            # deixa login e anonimos passarem para o login_required tratar
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            resp = assert_hierarquia(request, view_name)
            if resp is not None:
                return resp
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# ── Otimização: get_propriedade com select_related/prefetch (P0) ──
def get_propriedade_optimizada(user):
    """
    Retorna a Propriedade que deve ser usada pelo produtor ou servidor logado,
    com select_related/prefetch para evitar N+1 em dashboard, safra, talhao, etc.
    Uso: prop = get_propriedade_optimizada(request.user)

    - Produtor: sempre usa a sua propriedade (user=user).
    - Servidor (não possui propriedade própria): usa a propriedade VINCULADA
      ao seu perfil (perfil.propriedade_vinculada). Sem isso, TODO o dashboard
      do servidor cai em "Sem dados" porque a query filtrava apenas user=user.
    """
    from app.models import Propriedade

    qs = Propriedade.objects.select_related("user").prefetch_related(
        "safras__cultura",
        "safras__talhao",
        "talhoes__cultura_atual",
    )

    # 1) Propriedade de propriedade própria (produtor)
    prop = qs.filter(user=user).first()
    if prop is not None:
        return prop

    # 2) Fallback: propriedade vinculada ao perfil do servidor
    if getattr(user, "is_authenticated", False):
        try:
            perfil = user.perfil
        except Exception:
            perfil = None
        vinculada_id = getattr(perfil, "propriedade_vinculada_id", None)
        if vinculada_id:
            return qs.filter(id=vinculada_id).first()

    return None


def get_queryset_optimizado(model, user, filters=None, select=None, prefetch=None):
    """
    Helper genérico para ViewSets: já filtra por propriedade do user
    e aplica select_related/prefetch.
    """
    from app.models import Propriedade

    prop_ids = Propriedade.objects.filter(user=user).values_list("id", flat=True)
    qs = model.objects.filter(propriedade_id__in=prop_ids)
    if filters:
        qs = qs.filter(**filters)
    if select:
        qs = qs.select_related(*select)
    if prefetch:
        qs = qs.prefetch_related(*prefetch)
    return qs


def pode_ver_financeiro(user):
    """Financeiro = dado sensível: produtor sempre; servidor só com a flag
    pode_ver_financeiro ligada no dashboard config (área FINANCEIRO por padrão)."""
    if not getattr(user, "is_authenticated", False):
        return False
    perfil = _perfil_ou_negado(user)
    if perfil is None:
        # Dado financeiro é o mais sensível do sistema. Sem perfil definido,
        # o padrão é NÃO ver — a versão anterior devolvia True e tratava
        # qualquer conta sem perfil como produtor.
        return False
    if perfil.tipo_usuario == "produtor":
        return True
    try:
        return bool(perfil.get_dashboard_config().get("pode_ver_financeiro", False))
    except Exception:
        return False


def propriedades_financeiras(user):
    """Propriedades com financeiro visível: próprias, ou vinculada se permitido."""
    from app.models import Propriedade

    if pode_ver_financeiro(user):
        return propriedades_visiveis(user)
    try:
        if user.perfil.tipo_usuario == "produtor":
            return Propriedade.objects.filter(user=user)
    except Exception:
        pass
    return Propriedade.objects.none()


class PodeVerFinanceiro:
    """Permission DRF p/ ViewSets financeiros (contas, lançamentos, etc.)."""

    message = "Sem permissão para dados financeiros."

    def has_permission(self, request, view):
        return pode_ver_financeiro(request.user)

    def has_object_permission(self, request, view, obj):
        return pode_ver_financeiro(request.user)
