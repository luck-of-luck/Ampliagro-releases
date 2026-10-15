import json
import os
import secrets
from datetime import datetime

import structlog
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from app.cultures.seletor import opcoes_para_seletor
from app.hierarquia import hierarquia_required
from app.models import *

from .utils import *

# Recuperação de senha: janela de validade do código e teto de tentativas.
# O código é uma credencial — precisa expirar e não pode ser adivinhado sem
# custo. Ver app/views/tests_auth.py para o contrato travado por testes.
RECOVERY_TTL_SEGUNDOS = 600
RECOVERY_MAX_TENTATIVAS = 5
RECOVERY_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem I/O/0/1
logger = structlog.get_logger(__name__)


def _next_seguro(request, padrao):
    """Resolve o ?next= respeitando host — `url_has_allowed_host_and_scheme`
    bloqueia `//evil.com` e o truque `/\\evil.com` que a checagem manual
    `startswith('/')` deixava passar (o browser normaliza `\\` para `/`).

    O `startswith("/")` tambem e' obrigatorio, e NAO e' redundante com a
    funcao do Django. MEDIDO, 2026-10-04: `url_has_allowed_host_and_scheme`
    aceita `guias`, `%2F` e `%2Fguias%2F` — nao sao URLs de outro host, logo
    passam. Mas `redirect()` chama `resolve_url()`, que para uma string que
    nao comeca por `/` tenta `reverse()` como se fosse o NOME DE UMA VIEW. O
    resultado e' `NoReverseMatch` e um HTTP 500 DEPOIS do utilizador ter sido
    autenticado — o login seemingly funciona e o producer fica numa pagina de
    erro, sem sessao apparently criada.

    O 500 e'facil de alcançar por accidento: um `next` ja percent-encoded
    (o browser reencaminha `?next=%2Fguias%2F` sem descodificar) chega aqui
    como `%2Fguias%2F`. Confirmado com cliente de teste: `next=/` e
    `next=/guias/` redireccionam; `next=guias`, `next=%2F` e `next=%2Fguias%2F`
    devolvem 500. So e' preciso estar autenticado para o ramo ser alcancado,
    o que significa que o 500 acontece DEPOIS de o login ter seemingly
    sucesso — a pior altura para um erro.

    Um caminho tem de comecar por `/` para ser um caminho. `//evil.com` e
    `/\\evil.com` comecam por `/` e sao barrados pela checagem de host; um
    caminho que nao comeca por `/` nunca e' um caminho, e cai no padrao."""
    bruto = request.POST.get("next") or request.GET.get("next") or ""
    if bruto.startswith("/") and url_has_allowed_host_and_scheme(
        bruto,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return bruto
    return padrao


def _gerar_codigo():
    """Código com PRNG criptográfico. `random` é Mersenne Twister: previsível
    a partir de poucas amostras — nunca usar em credencial."""
    return "".join(secrets.choice(RECOVERY_ALFABETO) for _ in range(6))


def _recuperacao_limpar(request):
    """Limpa o estado de recuperação da sessão. `pop` (e não `del`) porque o
    `login()` rotaciona a session key e já descarta essas chaves — `del` estoura
    KeyError e devolvia 500 DEPOIS do usuário ter sido autenticado."""
    request.session.pop("recovery_code", None)
    request.session.pop("recovery_user_id", None)
    request.session.pop("recovery_created_at", None)
    request.session.pop("recovery_tentativas", None)


UF_LIST = [
    ("", "-- UF --"),
    ("AC", "AC"),
    ("AL", "AL"),
    ("AP", "AP"),
    ("AM", "AM"),
    ("BA", "BA"),
    ("CE", "CE"),
    ("DF", "DF"),
    ("ES", "ES"),
    ("GO", "GO"),
    ("MA", "MA"),
    ("MT", "MT"),
    ("MS", "MS"),
    ("MG", "MG"),
    ("PA", "PA"),
    ("PB", "PB"),
    ("PR", "PR"),
    ("PE", "PE"),
    ("PI", "PI"),
    ("RJ", "RJ"),
    ("RN", "RN"),
    ("RS", "RS"),
    ("RO", "RO"),
    ("RR", "RR"),
    ("SC", "SC"),
    ("SP", "SP"),
    ("SE", "SE"),
    ("TO", "TO"),
]


def login_view(request):
    erro_login = None

    if request.method == "POST":
        acao = request.POST.get("acao", "login")

        if acao == "login":
            tipo_acesso = request.POST.get("tipo_acesso", "produtor")
            nome_fazenda = (request.POST.get("nome_fazenda") or "").strip()
            usuario = request.POST.get("usuario")
            senha = request.POST.get("senha")

            # Servidor (profissional contratado) — exige fazenda + credenciais
            if tipo_acesso == "servidor" or nome_fazenda:
                if not nome_fazenda:
                    erro_login = "Informe o nome da fazenda que te cadastrou."
                else:
                    user = authenticate(request, username=usuario, password=senha)
                    if user is not None:
                        try:
                            perfil = user.perfil
                            tipos_servidor = [
                                "servidor",
                                "operario",
                                "agronomo",
                                "mecanico",
                                "administrativo",
                            ]
                            if perfil.tipo_usuario not in tipos_servidor:
                                erro_login = "Este usuário não é um servidor válido. Peça ao produtor para cadastrá-lo como servidor."
                            elif (
                                not perfil.ativo_servidor
                                and perfil.tipo_usuario == "servidor"
                            ):
                                erro_login = "Servidor desativado pelo produtor. Contate a fazenda."
                            else:
                                fazenda_ok = False
                                if (
                                    (
                                        perfil.propriedade_vinculada
                                        and perfil.propriedade_vinculada.nome.lower()
                                        == nome_fazenda.lower()
                                    )
                                    or (
                                        perfil.funcionario
                                        and perfil.funcionario.nome_fazenda_login
                                        and perfil.funcionario.nome_fazenda_login.lower()
                                        == nome_fazenda.lower()
                                    )
                                    or (
                                        perfil.propriedade_vinculada
                                        and nome_fazenda.lower()
                                        in perfil.propriedade_vinculada.nome.lower()
                                    )
                                ):
                                    fazenda_ok = True
                                if fazenda_ok:
                                    login(request, user)
                                    return redirect(_next_seguro(request, "/servidor/"))
                                else:
                                    erro_login = f'Fazenda "{nome_fazenda}" não confere com o vínculo do servidor. Verifique o nome exato.'
                        except PerfilUsuario.DoesNotExist:
                            erro_login = "Perfil de servidor não encontrado."
                    else:
                        erro_login = "Usuário ou senha inválidos para servidor."
            elif tipo_acesso == "produtor":
                # Login padrão do Produtor
                user = authenticate(request, username=usuario, password=senha)

                if user is not None:
                    login(request, user)
                    if not user.propriedades.exists():
                        return redirect("onboarding")
                    return redirect(_next_seguro(request, "/"))
                else:
                    erro_login = "Usuário ou senha inválidos. Verifique os campos."

        elif acao == "cadastro":
            form_cadastro = CadastroForm(request.POST)
            if form_cadastro.is_valid():
                username = form_cadastro.cleaned_data["usuario"]
                senha = form_cadastro.cleaned_data["senha"]

                # AUTH_PASSWORD_VALIDATORS existe (config/settings/base.py) mas
                # `create_user` NÃO o executa — sem esta chamada o cadastro aceitou
                # senha "1". `validate_password` é a única forma de o produtor
                # receber o mesmo feedback do Django admin.
                try:
                    password_validation.validate_password(senha, None)
                except ValidationError as exc:
                    form_cadastro.add_error("senha", exc)
                    return render(
                        request, "login.html", {"form_cadastro": form_cadastro}
                    )

                if User.objects.filter(username__iexact=username).exists():
                    form_cadastro.add_error(
                        "usuario", "Este nome de usuário já está em uso."
                    )
                    return render(
                        request, "login.html", {"form_cadastro": form_cadastro}
                    )

                # `create_user` grava antes do `login()`. Se o login estourar, o
                # usuário ficava órfão no banco e o cadastro nunca funcionava
                # (ValueError de múltiplos backends). A transação garante que
                # ou os dois acontecem, ou nada acontece.
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=username,
                            password=senha,
                            email=form_cadastro.cleaned_data["email"],
                        )
                        # O sinal `garantir_perfil_usuario` (app/signals.py) já
                        # criou o perfil no post_save do User. Aqui só se garante
                        # o papel — `create` estouraria UNIQUE(user_id).
                        PerfilUsuario.objects.update_or_create(
                            user=user, defaults={"tipo_usuario": "produtor"}
                        )
                        # `login()` exige o atributo `backend` quando há mais de
                        # um backend configurado (axes + ModelBackend + allauth).
                        # `create_user` não o define — sem esta linha, 500.
                        user.backend = "django.contrib.auth.backends.ModelBackend"
                        login(request, user)
                except IntegrityError:
                    # corrida: outro POST criou o mesmo username entre o
                    # `filter` acima e o INSERT.
                    form_cadastro.add_error(
                        "usuario", "Este nome de usuário já está em uso."
                    )
                    return render(
                        request, "login.html", {"form_cadastro": form_cadastro}
                    )
                return redirect("onboarding")
            else:
                return render(request, "login.html", {"form_cadastro": form_cadastro})

        elif acao == "recuperar_senha":
            # Passo 1: valida identidade e emite o código.
            # Anti-enumeração: a resposta é IDÊNTICA para usuário inexistente,
            # e-mail errado ou fazenda sem vínculo. Antes, cada caso devolvia
            # uma mensagem diferente e permitia enumerar contas cadastradas.
            nome_fazenda = request.POST.get("fazenda", "").strip()
            usuario = request.POST.get("usuario", "").strip()
            email = request.POST.get("email", "").strip()
            generico = {
                "ok": True,
                "msg": "Se os dados conferem, enviamos um código de verificação.",
            }

            user = None
            if usuario and email:
                user = (
                    User.objects.filter(username=usuario, email=email)
                    .order_by("id")
                    .first()
                )
            if user is None or not user.is_active:
                # Mesmo formato de sucesso: não revela se a conta existe.
                return JsonResponse(generico)

            # Vínculo com a fazenda tem de bater, senão um e-mail adivinhado
            # somado à conta alheia bastava para iniciar a recuperação.
            try:
                perfil = user.perfil
            except PerfilUsuario.DoesNotExist:
                return JsonResponse(generico)

            fazenda_ok = bool(
                (
                    perfil.propriedade_vinculada
                    and perfil.propriedade_vinculada.nome.lower()
                    == nome_fazenda.lower()
                )
                or (
                    perfil.funcionario
                    and perfil.funcionario.nome_fazenda_login
                    and perfil.funcionario.nome_fazenda_login.lower()
                    == nome_fazenda.lower()
                )
                or user.propriedades.filter(nome__iexact=nome_fazenda).exists()
            )
            if not fazenda_ok:
                return JsonResponse(generico)

            code = _gerar_codigo()
            request.session["recovery_code"] = code
            request.session["recovery_user_id"] = user.pk
            request.session["recovery_created_at"] = timezone.now().isoformat()
            request.session["recovery_tentativas"] = 0

            try:
                send_mail(
                    subject="Código de acesso Ampliagro",
                    message=(
                        f"Olá, {user.first_name or user.username}.\n\n"
                        f"Seu código de acesso é: {code}\n"
                        f"Ele expira em {RECOVERY_TTL_SEGUNDOS // 60} minutos.\n"
                        "Se não foi você, ignore esta mensagem."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None)
                    or "nao-responda@ampliagro.local",
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                # Falha de e-mail não pode virar 500 nem vazar detalhe. Loga
                # server-side (com contexto) e segue com o fluxo de resposta.
                logger.exception(
                    "falha_envio_codigo_recuperacao", username=user.username
                )

            # O código é uma CREDENCIAL: em produção ele só existe no e-mail.
            # Devolvê-lo no corpo HTTP transformava "recuperar senha" em
            # "entrar sem senha" — qualquer um com usuário+e-mail+fazenda
            # autenticava.
            #
            # POR QUE UM PORTÃO EXPLÍCITO, E NÃO `settings.DEBUG`
            # --------------------------------------------------------
            # A versão anterior devolvia o código sempre que DEBUG estava
            # ligado. DEBUG é o interruptor mais ligado que existe neste
            # projeto: `config/settings/dev.py` põe
            #     DEBUG = os.environ.get("DEBUG", "True")
            # ou seja, em dev o default é LIGADO. Um portão cuja condição
            # default é "mostrar" não é um portão: é uma constante de
            # configuração que alguém vai esquecer que existe.
            #
            # O portão passa a ser uma variável que ninguém liga por
            # acidente, e que fica AUDITÁVEL quando é ligada — porque
            # "quem viu um código de recuperação" tem de ser uma pergunta
            # com resposta, não um palpite. Por isso o log abaixo é
            # `warning` e não `debug`: se alguém activar isto em produção,
            # o registo tem de dizer que aconteceu.
            #
            # Ausência da variável = ausente. O `login.html:373` já trata
            # a ausência (`res.code ? ... : ...`), portanto o fluxo local
            # continua a funcionar sem quebrar.
            resposta = dict(generico)
            if os.environ.get("AMPLIA_DEV_MOSTRAR_CODIGO") == "1":
                resposta["code"] = code
                logger.warning(
                    "codigo_recuperacao_exposto_no_http",
                    username=user.username,
                    debug=settings.DEBUG,
                )
            return JsonResponse(resposta)

        elif acao == "verificar_codigo":
            # Passo 2: confere o código e autentica (AJAX)
            codigo = request.POST.get("codigo", "").strip().upper()
            sess_code = request.session.get("recovery_code")
            sess_uid = request.session.get("recovery_user_id")
            criado_em = request.session.get("recovery_created_at")
            tentativas = request.session.get("recovery_tentativas", 0)

            if not sess_code or not sess_uid:
                return JsonResponse(
                    {"ok": False, "erro": "Sessão expirada. Tente novamente."}
                )

            # Janela de validade: sem TTL, um código emitido de manhã valia a
            # noite inteira (a sessão vive 24h — SESSION_COOKIE_AGE).
            if criado_em:
                try:
                    idade = (
                        timezone.now() - datetime.fromisoformat(criado_em)
                    ).total_seconds()
                except (TypeError, ValueError):
                    idade = RECOVERY_TTL_SEGUNDOS + 1
                if idade > RECOVERY_TTL_SEGUNDOS:
                    _recuperacao_limpar(request)
                    return JsonResponse(
                        {
                            "ok": False,
                            "erro": "Código expirado. Solicite um novo.",
                        }
                    )

            # Teto de tentativas: o django-axes só instrumenta `authenticate()`,
            # que esta rota NÃO chama — o código era adivinhável indefinidamente.
            if tentativas >= RECOVERY_MAX_TENTATIVAS:
                _recuperacao_limpar(request)
                return JsonResponse(
                    {
                        "ok": False,
                        "erro": ("Muitas tentativas. Solicite um novo código."),
                    }
                )

            if not secrets.compare_digest(codigo, sess_code):
                request.session["recovery_tentativas"] = tentativas + 1
                restantes = RECOVERY_MAX_TENTATIVAS - (tentativas + 1)
                return JsonResponse(
                    {
                        "ok": False,
                        "erro": (
                            "Código incorreto."
                            + (
                                f" Restam {restantes} tentativa(s)."
                                if restantes > 0
                                else ""
                            )
                        ),
                    }
                )

            try:
                user = User.objects.get(pk=sess_uid, is_active=True)
            except User.DoesNotExist:
                _recuperacao_limpar(request)
                return JsonResponse({"ok": False, "erro": "Erro ao localizar usuário."})

            # `login()` rotaciona a session key e descarta o resto da sessão —
            # por isso a limpeza usa `pop` e vem DEPOIS do login, nunca `del`
            # antes (a versão anterior estourava KeyError e devolvia 500 com o
            # usuário já autenticado, sem nunca mostrar a tela de sucesso).
            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, user)
            _recuperacao_limpar(request)

            # Flag para disparar pop-up de mudança de senha na home
            request.session["just_recovered_password"] = True

            return JsonResponse({"ok": True, "redirect": "/"})

    # `next` viaja ate o TEMPLATE, e' o que faz o campo hidden existir.
    # MEDIDO, 2026-10-04: `login.html:96-97` e `159-160` tem `{% if next %}`,
    # mas o contexto final so levava `erro_login`. A variavel nunca chegava, o
    # hidden nunca era desenhado, e o `?next=` que o dashboard constroi ao
    # perder a sessao (ver `hasWidgetSession` em index.html) era descartado:
    # o producer entrava, o login funcionava, e aterrava em `/` em vez de
    # voltar a pagina de onde saiu. Um campo hidden que nunca e' renderizado
    # e' um template que mente sobre o que faz.
    #
    # Passa por `_next_seguro` pelo mesmo motivo do redirect: o valor vai
    # parar num `Location:`. Validar no template (JS) seria tarde e seria
    # ignorado — quem decide e' esta funcao, e o template so copia.
    #
    # `primeiro_acesso` e' o que faz a janela perguntar "e a primeira vez?".
    # Sao DUAS fontes, e nao uma so, porque as duas erram em situacoes
    # diferentes:
    #
    #   * `?primeiro=1` — o desktop manda sempre (ver `destinoDaApp` em
    #     `ampliagro-app/desktop/electron/setup.js`). E' o sinal de QUE
    #     o produtor esta' a abrir a app, e nao de que nao ha contas.
    #
    #   * `User.objects.count() == 0` — a base esta' mesmo vazia. Um
    #     servidor web novo, aberto no `/login/` sem o parametro, tambem
    #     e' um primeiro acesso e nao tem como o saber.
    #
    # A ORDEM do `or` e' o que mantem a pergunta honesta: o parametro nunca
    # e' lido sozinho, e a base vazia nunca e' lida sozinha. Quem decide e'
    # o template — ele PERGUNTA, e' o produtor que responde. Um flag lida
    # sozinha deixaria de ser uma pergunta e passaria a ser um facto que
    # mente: `?primeiro=1` numa base com 40 contas perguntaria uma coisa
    # que ja tem resposta, e o produtor de uma segunda maquina nunca
    # veria a pergunta.
    return render(
        request,
        "login.html",
        {
            "erro_login": erro_login,
            "next": _next_seguro(request, ""),
            "primeiro_acesso": request.GET.get("primeiro") == "1"
            or not User.objects.exists(),
            "base_vazia": not User.objects.exists(),
        },
    )


@require_POST
@login_required
def limpar_flag_recuperacao(request):
    """Consome a flag que dispara o pop-up de troca de senha. POST-only e
    autenticado: antes, um GET anônimo permitia apagar estado de sessão alheio
    (CSRF trivial) e a rota respondia a qualquer origem."""
    request.session.pop("just_recovered_password", None)
    return JsonResponse({"ok": True})


@require_POST
@login_required
def logout_view(request):
    """Logout por POST. Django 5 já exige POST, mas declaritar aqui fecha o
    logout forçado via `<img src="/logout/">` de um site terceiro (CSRF).
    O frontend já envia POST com token (app/templates/index.html:326)."""
    logout(request)
    return redirect("login")


def demo_login_view(request):
    """Login 1-clique para JOSIF/FEBRACE — cria/atualiza usuário demo e entra direto.

    GATED: só funciona com DEBUG ou com AMPLIAGRO_DEMO_ENABLED ligado. Sem esse
    portão, qualquer visitante anônimo de produção criava e autenticava uma
    conta com senha fixa (demo123) — backdoor total. `demo.bat` roda local com
    DEBUG=True, então a demonstração continua funcionando.
    """
    from django.core.management import call_command

    from app.models import PerfilUsuario

    if not (settings.DEBUG or getattr(settings, "AMPLIAGRO_DEMO_ENABLED", False)):
        logger.warning(
            "acesso_demo_bloqueado",
            path=request.path,
            hint="defina AMPLIAGRO_DEMO_ENABLED=1 para habilitar",
        )
        return redirect("login")

    user, created = User.objects.get_or_create(
        username="demo", defaults={"email": "demo@ampliagro.local"}
    )
    if created:
        user.set_password("demo123")
        user.save()
    else:
        # garante senha demo123 sempre funciona (para demo.bat)
        if not user.check_password("demo123"):
            user.set_password("demo123")
            user.save()
    # garante perfil
    PerfilUsuario.objects.get_or_create(
        user=user, defaults={"tipo_usuario": "produtor"}
    )
    # garante pelo menos 1 propriedade demo para não cair no onboarding vazio — se não houver, seed será chamado pelo demo.bat, mas garante fallback
    if not user.propriedades.exists():
        try:
            call_command("seed_mvp_demo", verbosity=0)
        except Exception:
            logger.warning("falha_seed_demo")
        # recarrega user se seed criou propriedades em outro user? garante relink
        user.refresh_from_db()
    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    # backend precisa para login sem authenticate
    request.session.save()
    return redirect(_next_seguro(request, "/"))


@login_required
def onboarding_view(request):
    from app.cultures.desktop import culturas_da_instalacao

    if request.user.propriedades.exists():
        return redirect("dashboard-spa")
    # A lista de culturas VOLTOU ao template em 13/10/2026, e volta pela MESMA
    # via de antes: `{{ culturas|json_script:"onb-culturas" }}`. Nao e' uma
    # restauracao innocua — e' o requisito de produto "na entrada da fazenda,
    # perguntar em multi-selecao quais culturas produzimos", que e' o que passa
    # a decidir quais guias, widgets e perguntas de IA aparecem.
    #
    # O risco de XSS que a NOTA anterior registava REALMENTE existiu, e o fix
    # tambem: `Cultura.nome` e' gravavel via API (`CulturaViewSet`,
    # `LeituraGlobalEscritaStaff`, tabela global PARTILHADA, sem escopo por
    # propriedade), portanto um nome com `</script>` executava JavaScript para
    # todo o utilizador que chegasse ao onboarding. XSS armazenado
    # cross-tenant, nao self-XSS.
    #
    # O que muda hoje e' que esse caminho esta de volta A ESTAR ABERTO. Por isso
    # as duas regras abaixo nao sao estilo, sao a correcção:
    #
    #   1. a chave do contexto chama-se `culturas` e o template consome-a
    #      SÓ por `json_script`. `json_script` e' o que escapa. Um
    #      `{{ culturas|safe }}` ou um `data-culturas="{{ culturas }}"`
    #      reconstituem o XSS — e `tests_onboarding.py` verifica ambos.
    #   2. o payload vai para dentro de `<script type="application/json">`,
    #      que o browser nunca executa. O JS do template le-o por
    #      `JSON.parse` do `textContent`.
    #
    # O formato (agrupado, filtrado, activo-so) e' de
    # `app.cultures.seletor.opcoes_para_seletor`. A view nao sabe nada sobre
    # grupos nem rotulos: e' o que impede a view e o template divergirem,
    # que foi exactamente a doenca que o teste de concordancia guarda.
    return render(
        request,
        "onboarding.html",
        {
            "uf_list": UF_LIST,
            "culturas": opcoes_para_seletor(),
            "desktop_culturas": culturas_da_instalacao(),
            "user_email": request.user.email or "",
            "user_name": request.user.first_name or request.user.username,
        },
    )


@require_POST
@login_required
def onboarding_save(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    user = request.user
    nome_fazenda = data.get("nome_fazenda", "").strip()
    documento = data.get("documento", "").strip()
    estado = data.get("estado", "").strip()
    cidade = data.get("cidade", "").strip()
    area = data.get("area", 0)
    lat = data.get("lat")
    lon = data.get("lon")
    geometria = data.get("geometria") or {}

    # `porte` saiu daqui: era lido e descartado, e Propriedade nao tem esse
    # campo. A pergunta "Segmentacao" no onboarding nao gravava nada.
    # `documento` agora vira cpf_cnpj — antes o produtor digitava o CPF/CNPJ e o
    # valor era descartado em silencio, mesmo com o campo do modelo pronto.
    #
    # Cidade/UF NAO sao mais obrigatorios: o produtor pode so desenhar o contorno
    # no mapa e complementar depois. Se o desenho troux cidade (geocodificacao
    # reversa), ela entra; se nao, a propriedade nasce sem cidade em vez de travar.
    if not nome_fazenda:
        return JsonResponse(
            {"ok": False, "erro": "Informe o nome da propriedade"}, status=400
        )

    # Coordenada so entra se for plausivel: sem isso o mapa Mandaria null/NaN
    # para o banco e o `clima` receberia lixo.
    try:
        lat_f = float(lat) if lat is not None else None
        lon_f = float(lon) if lon is not None else None
    except (TypeError, ValueError):
        lat_f = lon_f = None
    if lat_f is not None and not (-90 <= lat_f <= 90):
        lat_f = None
    if lon_f is not None and not (-180 <= lon_f <= 180):
        lon_f = None
    if lat_f is None or lon_f is None:
        lat_f = lon_f = None

    try:
        area_float = float(area) if area else 0
    except (ValueError, TypeError):
        area_float = 0

    if area_float <= 0:
        return JsonResponse(
            {"ok": False, "erro": "Informe a área total da propriedade"}, status=400
        )

    # NOTA: esta funcao NAO esta no caminho do pedido. O POST do cadastro vai
    # para `app.api.views.user.onboarding_save` (`/api/onboarding/save/` em
    # `app/api/urls.py`), e e' la que a propriedade e' criada e as cultures
    # gravadas. Esta aqui e' a versao antiga, que ficou para tras.
    #
    # Fica intacta de proposito. Um segundo `onboarding_save` que finge gravar
    # culturas e' pior do que um morto: da' a ler que o vinculo
    # propriedade<->Cultura e' gravado aqui, e nao e'.
    Propriedade.objects.create(
        user=user,
        nome=nome_fazenda,
        area_total=area_float,
        uf=estado or "MT",
        cidade=cidade,
        cpf_cnpj=documento if documento else "",
        latitude=lat_f,
        longitude=lon_f,
        geometria=geometria if isinstance(geometria, dict) else {},
    )

    PerfilUsuario.objects.get_or_create(
        user=user,
        defaults={
            "idioma": "pt-br",
            "tema": "light",
        },
    )

    return JsonResponse({"ok": True, "redirect": "/dashboard/"})
