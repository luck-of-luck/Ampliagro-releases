import json
import time
import uuid

import structlog
from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = structlog.get_logger()


class ServidorRevogadoMiddleware:
    """Bloqueia servidores desativados (ativo_servidor=False) na API.

    O login já recusa servidores desativados (auth.py), mas uma sessão
    válida obtida antes da desativação continuava funcionando na API.
    Este middleware fecha esse buraco: qualquer request /api/ de um
    servidor com ativo_servidor=False recebe 403.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user
            and getattr(user, "is_authenticated", False)
            and request.path.startswith("/api/")
        ):
            try:
                perfil = getattr(user, "perfil", None)
                if (
                    perfil is not None
                    and perfil.tipo_usuario == "servidor"
                    and not perfil.ativo_servidor
                ):
                    return JsonResponse(
                        {"error": "Servidor desativado. Acesso revogado."},
                        status=403,
                    )
            except Exception:
                # Se o perfil não puder ser lido, não bloqueia — mas loga.
                logger.warning("ServidorRevogadoMiddleware: falha ao ler perfil")
        return self.get_response(request)


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID", str(uuid.uuid4())[:8])
        request.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response


class _Rejeitado(Exception):
    """Um id do request nao pertence a quem o pediu. Sobe até ao
    middleware, que a traduz em 403 — e nunca é engolido por um
    `except Exception` a meio do caminho.

    `404` vs `403`: um id inexistente é 404, um id de outra pessoa é 403.
    São respostas diferentes para quem erra o número, e para quem está a
    tentar ver a lavoura alheia. Colapsar as duas esconde a tentativa
    dentro de um erro banal.
    """

    def __init__(self, mensagem, status=403):
        super().__init__(mensagem)
        self.status = status


class ServidorRevogadoMiddleware:
    """Propaga a REVOGACAO do servidor a toda a camada `/api/`.

     O QUE ESTA FEITO
     ================
     O produtor desactiva o servidor em `app/views/lgpd.py`
     (`perfil.ativo_servidor = False`). `app/views/servidor.py` le esse flag nas
     quatro paginas HTML do servidor (`_perfil_e_propriedade`, linha 48, e
     `servidor_dashboard_view`, linha 87) e faz `logout`.

     A camada `/api/` nao o lia em lado nenhum. Cada view declara
     `permission_classes = [IsAuthenticated]`, e `IsAuthenticated` prova que ha
     SESSAO, nao que a sessao ainda e' valida.Resultado medido por
     `tests/test_superficie_servidor.py::SuperficieApiRevogacaoTest`: 23 rotas
     `/api/` devolviam HTTP 200 com dados da fazenda a que o servidor esta
     ligado, com `ativo_servidor=False` e sessao viva — incluindo escrita
     (`estoque`, `agenda`, `maquinarios`, `perfil`).

     POR QUE UM MIDDLEWARE E NAO UMA PERMISSION CLASS
     ===============================================
     Uma `DEFAULT_PERMISSION_CLASSES` nova nao chegaria: cada view declara as
     suas `permission_classes` explicitamente, o que sobrepoe a default. Para
     cobrir a superficie toda com UMA alteracao, o ponto tem de ser antes do
     DRF — e antes de todas as views, o que e' o middleware.

     `ativo_servidor` tem `default=True` (ver `PerfilUsuario`), portanto isto
     NAO affects operarios, agronomos, mecanicos ou administradores: so quando o
     produtor o desligue explicitamente. E a MESMA regra de
     `app/views/servidor.py:48` — nenhuma das duas camadas inventa o seu proprio
     criterio de "desactivado".

     ESCOPO
     =====
     So `/api/`. As quatro paginas HTML ja tratam a revogacao elas proprias
     (com `logout`, que e' o que um browser precisa); aqui o sintoma e' JSON, e
     a resposta correcta e 403. Alargar isto a todo o pathPrefix mudaria o
     comportamento de login/logout e das paginas normais sem nenhuma medicao que
     o justifique — e sem o `logout` que elas precisam.

     FALHA FECHA A PORTA
     ===================
     Ao contrario do `TenantIsolationMiddleware`, uma excepcao aqui devolve 403
     em vez de deixar passar. A razao e' o custo: ler `user.perfil` vai a base de
    dados, portanto se a base esta em baixo TODAS as views `/api/` vao falhar
    na mesma — fechar a porta nao custa disponibilidade a ninguem. E se a
    excepcao for um bug de configuracao (campo renomeado), deixar passar
    significa entregar dados a um servidor que o produtor desligou, em
    silencio. O log abaixo existe para esse caso ser visivel.
    """

    PREFIXO = "/api/"

    def __init__(self, get_response):
        self.get_response = get_response

    def _recusar(self, request, mensagem, status=403):
        from django.http import JsonResponse

        return JsonResponse({"error": mensagem}, status=status)

    def __call__(self, request):
        if request.path.startswith(self.PREFIXO):
            user = getattr(request, "user", None)
            if user and getattr(user, "is_authenticated", False):
                try:
                    from app.services.revogacao import MENSAGEM, servidor_ativo

                    # Perfil ausente (registo orfao) nao e' revogacao: quem
                    # nao tem perfil nao tem propriedade vinculada, e as views
                    # ja respondem "sem dado". `servidor_ativo` trata disso —
                    # e trata tambem o `except`, que e' a parte que importa:
                    # devolve `False` quando nao consegue ler, porque um guarda
                    # que assume "activo" quando nao sabe transforma uma
                    # revogacao num acesso.
                    #
                    # MEDIDO 2026-10-04 (agente 4): esta logica estava
                    # duplicada AQUI. Duas copias da mesma regra divergem, e a
                    # segunda nunca e' actualizada quando a primeira muda. O
                    # unico sítio e' `app/services/revogacao.py`.
                    if not servidor_ativo(user):
                        return self._recusar(request, MENSAGEM)
                except Exception as exc:
                    logger.error(
                        "ServidorRevogadoMiddleware: nao foi possivel ler "
                        "PerfilUsuario.ativo_servidor (%s: %s). A request e' "
                        "recusada com 403 em vez de seguir sem verificacao.",
                        type(exc).__name__,
                        exc,
                    )
                    return self._recusar(
                        request, "Revogacao nao verificavel.", status=403
                    )
        return self.get_response(request)


class TenantIsolationMiddleware:
    """Garante que tudo o que o request traz pertence ao utilizador.

    Este middleware existeva para bloquear o cross-tenant via
    `?propriedade_id`, e fazia isso. Mas a protecção cobria UM id de entre
    varios: `talhao_id`, `fazenda_id`, `device_id` e `sacas` passavam
    intactos. Os handlers fazem `.filter(id=talhao_id)` sem filtro de
    utilizador, entao um `?talhao_id=64` de outra pessoa devolvia o talhao
    de outra pessoa — carimbado `fonte_dado: "medido"`.

    Isto é pior que um bug de dados inventados. Dados inventados dizem
    "isto aqui e' um exemplo". Dados de outra pessoa dizem "isto e' seu", e
    o produtor nao tem forma de saber que nao e'.

    Por isso a verificacao e' por TABELA e nao por parametro: cada id
    apontado tem de resolver dentro do utilizador, ou o request morre com
    403. Uma lista de parametros e' uma lista para se esquecer de
    acrescentar um.
    """

    # id -> (modelo, caminho de lookup até ao dono). O caminho tem de
    # resolver de facto: um nome errado aqui levanta FieldError, que o
    # `except` transformava em "sem verificação nenhuma" — a falha de um
    # caminho desligava a protecção de todos os outros.
    #
    # `Talhao` É o talhão: o caminho é `propriedade__user`, não
    # `talhao__propriedade__user`.
    @staticmethod
    def _corpo_json(request):
        """O corpo de um pedido JSON, ou `None`.

        MEDIDO 2026-10-05 (agente 11). O content-type e' testado ANTES de ler
        o corpo, e' deliberado: `request.body` consome o stream num pedido
        multipart, e um middleware que lesse o corpo de um upload deixaria a
        view sem ficheiro. Para JSON o corpo ja esta' em memoria e o Django
        cacheia-o, portanto ler aqui e' seguro.

        Devolve `None` — e nao levanta — quando o corpo nao e' um objeto JSON.
        Um JSON malformado ja nao passa a validacao do DRF; levantar aqui
        trocaria um 400 honesto por um 500 sem informacao.
        """
        ct = (request.content_type or "").lower()
        if "json" not in ct:
            return None
        if request.method in ("GET", "HEAD", "OPTIONS", "DELETE"):
            return None
        try:
            dados = json.loads(request.body.decode("utf-8"))
        except Exception:
            return None
        return dados if isinstance(dados, dict) else None

    TABELAS_VERIFICADAS = {
        "propriedade_id": ("Propriedade", "user"),
        "fazenda_id": ("Propriedade", "user"),
        "talhao_id": ("Talhao", "propriedade__user"),
        "device_id": ("Device", "propriedade__user"),
        # MEDIDO 2026-10-05. Estas faltavam, e sao lidas de `request` em
        # varias views. Nas views que verifiquei o scope ja estava certo,
        # portanto **isto nao e' uma fuga em producao hoje**: e' uma lacuna
        # no porto unico. Uma view nova que leia estes ids do request nao
        # fica verificada sem isto.
        #
        # Acrescentar e' aditivo e nao muda o comportamento de nenhuma view
        # existente: so passa a por a chave em consideracao.
        "safra_id": ("Safra", "propriedade__user"),
        "conta_bancaria_id": ("ContaBancaria", "propriedade__user"),
        # MEDIDO 2026-10-11. IDs de tarefas/atividades/presets/planos que
        # views e intents leem do request. O scope correto segue a cadeia
        # de propriedade ate ao user.
        "atividade_id": ("AtividadePlanejada", "plano__safra__propriedade__user"),
        "tarefa_id": ("TarefaEstagio", "estagio__registro__user"),
        "plano_id": ("PlanoSafra", "safra__propriedade__user"),
        "preset_id": ("PresetPalco", "user"),
        "talhao_geometria_id": ("TalhaoGeometria", "talhao__propriedade__user"),
        "maquinario_id": ("Maquinario", "propriedade__user"),
        "insumo_id": ("Insumo", "propriedade__user"),
        "animal_id": ("Animal", "propriedade__user"),
        "funcionario_id": ("Funcionario", "propriedade__user"),
        "estoque_id": ("EstoqueItem", "propriedade__user"),
        "lancamento_id": ("LancamentoFinanceiro", "propriedade__user"),
        "aplicacao_id": ("AplicacaoInsumo", "talhao__propriedade__user"),
        "receituario_id": ("ReceituarioAgronomico", "safra__propriedade__user"),
        "piquete_id": ("Piquete", "propriedade__user"),
        "ordem_compra_id": ("OrdemCompra", "propriedade__user"),
        "pesagem_id": ("Pesagem", "animal__propriedade__user"),
        "raca_id": ("Racao", "propriedade__user"),
        "lote_aquatico_id": ("LoteAquatico", "propriedade__user"),
        "despesca_id": ("Despesca", "lote__propriedade__user"),
        "colmeia_id": ("ApiarioColmeia", "propriedade__user"),
        "producao_apiario_id": ("ProducaoApiario", "colmeia__propriedade__user"),
        "alerta_id": ("AlertaTelemetria", "propriedade__user"),
        "regra_alerta_id": ("RegraAlertaTelemetria", "propriedade__user"),
        "centro_custo_id": ("CentroCusto", "propriedade__user"),
        "custo_producao_id": ("CustoProducao", "propriedade__user"),
        "lancamento_detalhado_id": (
            "LancamentoDetalhado",
            "lancamento__propriedade__user",
        ),
        "rastro_item_id": ("RastroItem", "propriedade__user"),
        "rastreabilidade_safra_id": (
            "RastreabilidadeSafra",
            "safra__propriedade__user",
        ),
        "experimento_id": ("Experimento", "user"),
        "medicao_experimental_id": ("MedicaoExperimental", "experimento__user"),
        "prescricao_vra_id": ("PrescricaoVRA", "safra__propriedade__user"),
        "zarc_id": ("ZARC", "cultura"),
        "cultura_id": ("Cultura", "user"),
        "talhao_id": ("Talhao", "propriedade__user"),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def _rejeitar(self, request, mensagem, status=403):
        """Recusa o pedido. O texto e' JSON em `/api/` e HTML escapado fora.

        MEDIDO 2026-10-05 (semgrep, e depois medido): `HttpResponseForbidden`
        nao escapa. Passa o texto tal e qual, e um `<script>` no corpo chega
        intacto ao browser.

        Hoje isto NAO e' exploravel: o unico texto dinamico que entra por
        aqui e' `param`, uma chave de `TABELAS_VERIFICADAS` — codigo
        nosso, nao input do utilizador. E o 503 que escrevi hoje so mete
        `type(exc).__name__`, porque `OperationalError` nao tem atributo
        `.name` (medido: cai sempre no nome da classe).

        Mas essa e' uma proteccao que funciona por ACIDENTE. Fica segura
        por uma condicao que ninguem escreveu para ser uma condicao: se o
        Django passar a por `.name` na excepcao — e `.name` traz texto do
        driver, que traz o nome da coluna que o proprio codigo pediu — a
        reflexao aparece sem ninguem mexer numa linha deste ficheiro.

        Escapar aqui custa uma linha e fecha a classe de vez. Nao escapa o
        `/api/`, porque `JsonResponse` ja escapa e escapar duas vezes
        mostra `&lt;` ao usuario.
        """
        from django.http import JsonResponse

        if request.path.startswith("/api/"):
            return JsonResponse({"error": mensagem}, status=status)
        from django.http import HttpResponseForbidden
        from django.utils.html import escape

        return HttpResponseForbidden(escape(str(mensagem)))

    def __call__(self, request):
        request.propriedade = None
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            try:
                from app.models import Propriedade

                # MEDIDO 2026-10-05 (agente 11). Era:
                #     fonte = request.GET if method == "GET" else request.POST
                # e `request.POST` do Django so' e' povoado para formularios.
                # Num POST/PUT em `application/json` — que e' como a API
                # DRF escreve quase tudo — vinha VAZIO, o `continue` saltava
                # todas as chaves, e a verificacao de tenancy nao corria.
                # O porto unico do isolamento, desligado em silencio.
                #
                # O corpo JSON e' lido so' quando o content-type e' JSON.
                request.corpo_json = self._corpo_json(request)
                if request.method == "GET":
                    fonte = request.GET
                elif request.corpo_json is not None:
                    fonte = request.corpo_json
                else:
                    fonte = request.POST
                # Ids que apontam para registos inexistentes. A request segue
                # (um id que nao existe nao e' um ataque), mas o id e'
                # anulado: o handler passa a ver "sem talhao", e devolve
                # "sem dado" em vez de tentar ler um talhao que nao existe.
                qs_none: set[str] = set()

                # Todos os ids apontados, nao so `propriedade_id`.
                #
                # MEDIDO 2026-10-05 (agente 11): a chave que o middleware
                # procurava (`talhao_id`) nao e' a que o serializer DRF le
                # (`talhao`). Num corpo JSON — que e' como a API fala — a
                # verificacao de tenancy sobre chaves estrangeiras ficava
                # desligada mesmo depois da correccao de ler o corpo.
                # Medido: {"talhao": 2} passava, {"talhao_id": 2} dava 403.
                #
                # Para cada `X_id` procura-se tambem `X`. Nao se troca uma pela
                # outra: um formulario de HTML manda `talhao_id`, um cliente
                # DRF manda `talhao`, e os dois precisam de estar fechados.
                chaves = []
                for nome_id, (modelo, caminho_dono) in self.TABELAS_VERIFICADAS.items():
                    nome_da_fk = nome_id[:-3] if nome_id.endswith("_id") else nome_id
                    chaves.append((nome_id, modelo, caminho_dono, nome_id))
                    if nome_da_fk != nome_id:
                        chaves.append((nome_da_fk, modelo, caminho_dono, nome_id))

                for param, modelo, caminho_dono, _canon in chaves:
                    bruto = fonte.get(param)
                    if bruto in (None, ""):
                        continue
                    try:
                        valor = int(bruto)
                    except (TypeError, ValueError):
                        # Um id que nao e' id nao e' cross-tenant. A view
                        # trata-o (e responde "sem dado", nao 500).
                        continue

                    import app.models as _m

                    qs = getattr(_m, modelo).objects.filter(id=valor)
                    dono = qs.filter(**{caminho_dono: user})

                    if not qs.exists():
                        qs_none.add(param)
                        continue
                    if not dono.exists():
                        raise _Rejeitado(f"{param} não pertence ao usuário", status=403)
                    if param == "propriedade_id":
                        request.propriedade = dono.first()

                for param in qs_none:
                    if param in request.GET:
                        qs = request.GET.copy()
                        qs[param] = ""
                        request.GET = qs
                    if param in request.POST:
                        ps = request.POST.copy()
                        ps[param] = ""
                        request.POST = ps
                    # MEDIDO 2026-10-05 (agente 11): faltava o corpo JSON. Um id
                    # inexistente era apagado da query string e do formulario,
                    # e num POST JSON continuava la — a view via "sem dado"
                    # num caminho e tentava ler o registo noutro.
                    cj = getattr(request, "corpo_json", None)
                    if cj is not None and param in cj:
                        cj[param] = ""
                request.ids_inexistentes = sorted(qs_none)

                if request.propriedade is None:
                    # fallback primeira propriedade do user para conveniência
                    request.propriedade = Propriedade.objects.filter(
                        user=request.user
                    ).first()
            except _Rejeitado as r:
                # Uma recusa de tenancy NÃO pode ser engolida. O `except
                # Exception: pass` que estava aqui descartava o proprio
                # 403 quando um `except` interno levantava outra coisa
                # primeiro — a proteccao dependia de nada dar errado.
                return self._rejeitar(request, str(r), r.status)
            except Exception:
                # ESTA DECISAO FOI REVERTIDA. Mudar de volta exige saber o
                # que custa.
                #
                # O codigo antigo registava o erro e deixava a request
                # seguir SEM verificacao de tenancy nenhuma. Parecia
                # prudente: uma migration em falta derrubaria o site todo.
                #
                # Nao e' prudente. E' o modo de falha mais caro que existe
                # aqui, e o proprio log admitia: "cross-tenant pode passar".
                #
                # MEDIDO 2026-10-05: foi EXATAMENTE isto que aconteceu. Cinco
                # migrations por aplicar fzeram o codigo pedir
                # `cod_municipio` a uma base sem a coluna. O `OperationalError`
                # foi engolido, o middleware ficou silenciosamente inútil, e o
                # `TenantIsolationMiddleware` desativou-se a si proprio — num
                # sistema cujo produto inteiro e' a confianca de que os dados
                # de um produtor so aparecem a ele. O log estava la, a dizer
                # que corria mal; ninguem le um log e depois responde "muito
                # bem, entao passem os dados".
                #
                # O custo de ser fail-closed e' um 503 com uma mensagem
                # honesta. O custo de ser fail-open e' entregar a fazenda do
                # vizinho a quem nao a pediu, marcado `fonte_dado: "medido"`,
                # que e' pior do que dados inventados: dados inventados dizem
                # "isto e' um exemplo", e o produtor nao tem forma de saber
                # que o que viu era de outra pessoa.
                #
                # Por isso: quando nao se consegue VERIFICAR, nao se passa.
                # 503 e' "volta ja", e diz porquê. Um 200 silencioso seria
                # "confia em mim".
                import logging
                import sys as _sys

                exc = _sys.exc_info()[1]
                nome = getattr(exc, "name", None) or type(exc).__name__
                logging.getLogger(__name__).error(
                    "TenantIsolationMiddleware: verificacao de tenancy "
                    "falhou (%s). A request e' RECUSADA com 503. "
                    "ATENCAO: a versao anterior registava este erro e "
                    "deixava o pedido passar SEM verificacao — "
                    "cross-tenant pode passar, e o produtor nao tem forma "
                    "de saber que viu dados de outra pessoa. O log estava "
                    "la e nao chegou a mudar nada. Se esta mensagem "
                    "aparecer, a causa e' migracao ou configuracao, e a "
                    "CORRECAO e' na base — nunca afrouxar esta verificacao. "
                    "Tabelas verificadas: %s",
                    nome,
                    ", ".join(self.TABELAS_VERIFICADAS),
                    exc_info=True,
                )
                return self._rejeitar(
                    request,
                    f"Verificacao de propriedade indisponivel ({nome}). Nao e' "
                    f"possivel confirmar a que propriedade este pedido "
                    f"pertenece, por isso o pedido e' recusado em vez de "
                    f"passar sem verificacao. Tente de novo; se persistir, o "
                    f"sistema precisa de uma migration.",
                    status=503,
                )
        return self.get_response(request)


class QueryCountMiddleware:
    """P3 observability: conta queries e tempo, expõe via header X-Query-Count / X-Response-Time."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG and not request.path.startswith("/api/"):
            return self.get_response(request)
        start = time.monotonic()
        q_before = len(connection.queries)
        response = self.get_response(request)
        q_after = len(connection.queries)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        response["X-Query-Count"] = str(q_after - q_before)
        response["X-Response-Time"] = f"{elapsed_ms}ms"
        # loga lentas >800ms
        if elapsed_ms > 800:
            logger.warning(
                "slow_request",
                path=request.path,
                elapsed_ms=elapsed_ms,
                queries=q_after - q_before,
            )
        return response
