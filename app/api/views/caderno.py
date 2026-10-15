"""Caderno de Campo — API. O outro lado do que o `sync.js` tentava fazer.

POR QUE ESTE FICHEIRO EXISTE
============================
`app/static/js/pwa/sync.js` tem três métodos que fazem POST para
`/api/caderno/notas/`, `/api/caderno/fotos/` e `/api/caderno/voice/`. **Nenhuma
das três rotas existia.** O produtor escrevia a nota no talhão, o
`OfflineDB` guardava, o sync levava 404, e o `catch` fazia `console.error`.

Isto é a pior classe de bug do ERP: o produtor tem um caderno no telemóvel que
não existe em lado nenhum, e nunca soube. Numa app cuja promessa é
"offline-first", a funcionalidade offline por definição estava a perder
tudo.

O QUE ESTE FICHEIRO NÃO FAZ
============================
Não é um substituto do `AtividadePlanejada` nem do `LancamentoFinanceiro`. E
não finge ser a generalização que o nome sugere: `notas/` é o que existe
com as linhas de frontend de frontend à espera; `fotos/` e `voice/` ficam de fora e são
decididos à parte, porque um upload de media precisa de
`MEDIA_ROOT`, quotas e limpeza — e um POST que devolve 404 é melhor do que um
POST que aceita o ficheiro e o perde noutro sítio.

A honestidade aqui é preferível ao silêncio: `fotos/` devolve **501** com
texto a dizer o que falta, não 404 que parece "a app não sabe".
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from functools import wraps

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from rest_framework import serializers

from app.models import Cultura, FotoNota, NotaCampo, Propriedade, Talhao
from app.models.caderno import COORD_DECIMAL_PLACES, FORMATOS_FOTO
from app.validators import MAX_UPLOAD_MB


def exigir_sessao_json(view):
    """Substitui o `login_required` nas rotas de sync.

    O `login_required` do Django responde com um **redirect 302 para
    `/login/`**, e o `fetch` do browser segue-o: recebe uma pagina HTML de
    login com **200**. O `sync.js` veria um `response.ok` e marcaria a nota
    como sincronizada — o sync diria "guardado" e a nota nunca chegaria a
    lado nenhum. E' o mesmo bug do 404, com um disfarce melhor.

    Numa rota chamada por `fetch`, a resposta a "quem estas" e' 401, nao uma
    pagina de login. Este decorator mantem o `login_required` para o
    comportamento de sessao e troca apenas o formato do erro.

    REVOGACAO — porque esta e' a THIRD porta, e nao a primeira
    -------------------------------------------------------
    MEDIDO 2026-10-04 (agente 4). Estas tres rotas criam dados do produtor.
    `tests/test_superficie_servidor.py` classifica-as como (a) — "tem de
    respeitar a revogacao" — e `rg ativo_servidor` neste ficheiro dava ZERO.
    Eram, portanto, rotas de escrita que aceitavam um servidor desligado pelo
    proprio produtor: exactamente o furo que o `ServidorRevogadoMiddleware`
    fechou e que estas escapavam.

    Porque o check e' AQUI e nao em cada view: sao tres views e ha de ser
    UM sitio. Uma regra que tem de valer em N sitios nao pode ser lembrada em
    N sitios — e o ficheiro de onde ela vem diz isso mesmo
    (`app/services/revogacao.py`).

    Porque 403 e nao 401: 401 e' "nao sei quem eres". aqui o servidor sabe
    quem e' — e foi desligado. `401` deixaria o `sync.js` a tentar de novo
    para sempre, e um item que nunca sai da fila e' um item que o produtor
    acredita estar guardado.
    """

    @csrf_protect
    @require_POST
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {
                    "ok": False,
                    "erro": "sessãoRequired",
                    "detalhe": "sem sessão válida; a nota continua no aparelho",
                },
                status=401,
            )

        # A MESMA regra que o middleware, pelo MESMO modulo. Um servidor
        # revogado nao escreve, e o produtor fica a saber que a nota esta
        # ainda no aparelho em vez de a ver evaporar.
        from app.services.revogacao import MENSAGEM, servidor_ativo

        if not servidor_ativo(request.user):
            return JsonResponse(
                {
                    "ok": False,
                    "erro": "servidorRevogado",
                    "detalhe": MENSAGEM + " O registo continua no aparelho.",
                },
                status=403,
            )

        return view(request, *args, **kwargs)

    return wrapper


class NotaCampoSerializer(serializers.ModelSerializer):
    """Aceita o payload do `sync.js` e valida o tenant.

    O `talhao_id` e a `cultura_id` vêm do browser e **são verificados contra
    o `user`**. Um `talhao_id` de outra fazenda que chegue a ser gravado é a
    mesma classe de fuga que o `TenantIsolationMiddleware` barra nas views —
    e aqui não passa pelo middleware, porque o sync é feito pelo
    `fetch` do browser com a sessão do produtor. A validação no serializer é
    a única defesa que este caminho tem.
    """

    class Meta:
        model = NotaCampo
        fields = [
            "id",
            "talhao_id",
            "cultura_id",
            "propriedade_id",
            "conteudo",
            "tipo",
            "latitude",
            "longitude",
            "registada_em",
            "offline_id",
            "fonte_dado",
            "criado_em",
        ]
        read_only_fields = ["id", "criado_em", "fonte_dado"]

        # `registada_em` e' NOT NULL no modelo, mas **opcional na entrada**:
        # o `sync.js:111-119` nao o manda. Sem isto, toda a nota escrita
        # offline — que e' a unica nota que o Caderno de Campo existe para
        # guardar — era rejeitada com 400.
        extra_kwargs = {
            "registada_em": {
                "required": False,
                "allow_null": True,
                "default": timezone.now,
            }
        }

    # MEDIDO 2026-10-04: com `"talhao_id"` em `Meta.fields`, o
    # `ModelSerializer` gerava um `ReadOnlyField` — o sufixo `_id` e' de
    # *escrita*, nao de leitura, e o DRF descartava-o de `validated_data`.
    # Consequencias, as duas medidas em `tests_caderno.py`:
    #   * `talhao_id` chegava ao `create()` como `None` — a nota ficava sem
    #     talhao, sem dono, invisivel em qualquer mapa;
    #   * `validate_talhao_id` nunca corria, porque o campo nao chegava ao
    #     payload validado — e um `talhao_id` de outra fazenda devolvia
    #     **201**. Fuga cross-tenant por um nome de campo.
    #
    # Declarados explicitamente como `PrimaryKeyRelatedField`, com o
    # `queryset` restringido ao utilizador no `__init__`, a tenancy passa a
    # ser validada pelo proprio DRF e o `validate()` abaixo passa a ser a
    # segunda barreira, nao a unica.
    talhao_id = serializers.PrimaryKeyRelatedField(
        queryset=Talhao.objects.none(),
        source="talhao",
        allow_null=True,
        required=False,
    )
    cultura_id = serializers.PrimaryKeyRelatedField(
        queryset=Cultura.objects.none(),
        source="cultura",
        allow_null=True,
        required=False,
    )
    propriedade_id = serializers.PrimaryKeyRelatedField(
        queryset=Propriedade.objects.none(),
        source="propriedade",
        allow_null=True,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            # `queryset` ja restringido: um `talhao_id` alheio da um 400 do
            # proprio DRF, sem passar por codigo nosso.
            self.fields["talhao_id"].queryset = Talhao.objects.filter(
                propriedade__user=user
            )
            self.fields["propriedade_id"].queryset = Propriedade.objects.filter(
                user=user
            )
            # `Cultura` e' partilhada (ver `app/api/perms.py::LeituraGlobalEscritaStaff`),
            # logo todas sao validas para leitura. O que nao pode e' o produtor
            # escolher uma cultura ligada a uma propriedade alheia, e isso e'
            # verificado em `validate()`.
            self.fields["cultura_id"].queryset = Cultura.objects.all()

    def validate_registada_em(self, valor):
        """O `sync.js:111-119` **nao** manda `registada_em`.

        A nota foi escrita offline, no talhao, e o IndexedDB tem a hora
        certa; o payload so manda `talhao_id`, `cultura_id`, `conteudo`,
        `tipo`, `latitude`, `longitude` e `offline_id`. Um serializer que
        exigisse a hora aqui rejeitaria toda a nota do produtor — que e'
        exactamente o bug que se quer fechar.

        Este metodo trata o caso em que o campo **veio** mas vazio (`""` ou
        `null`): o `default` acima trata o caso em que nao veio. Sao dois
        pathways diferentes do DRF e precisam dos dois.

        A ausencia assume-se explicitamente como `now()`, e o `criado_em`
        (auto) fica a dizer a verdade de quando o servidor recebeu. O que
        **nao** se faz e' inventar uma data de campo como o `ia-local.js`
        fazia: ali a data entrava como se fosse a hora do produtor; aqui a
        lacuna esta escrita no sitio onde se decide.
        """
        return valor or timezone.now()

    def validate(self, attrs):
        """Validação de tenancy ao nível do objecto, não do campo.

        MEDIDO 2026-10-04: o `validate_talhao_id` **nunca corria**. Com
        `"talhao_id"` em `Meta.fields`, o DRF gera um campo chamado
        `talhao_id`, e o `validate_<nome>` só é invocado para o nome real do
        campo — o validador de `talhao` e o de `talhao_id` sao nomes
        diferentes. Resultado: `test_talhao_alheio_e_rejeitado` gravava uma
        nota num talhao de outra fazenda e devolvia **201**. Uma fuga
        cross-tenant por um nome de campo.

        Por isso a verificacao vive aqui, em `validate()`, que corre sempre.
        `validate_talhao_id` fica como reforco para o caso em que o campo
        chegue presente — belt and braces, porque a falha e' silenciosa e
        custa um produto inteiro.

        E porque `talhao_id`/`cultura_id`/`propriedade_id` estao declarados
        com `source="talhao"`/`"cultura"`/`"propriedade"`, o `attrs` traz os
        **objectos resolvidos**, nao os ids. Ler `attrs.get("talhao_id")` dava
        `None` em silencio.
        """
        erros = {}

        user = self.context["request"].user

        talhao = attrs.get("talhao")
        propriedade = attrs.get("propriedade")

        if (
            talhao is not None
            and not Talhao.objects.filter(id=talhao.pk, propriedade__user=user).exists()
        ):
            erros["talhao_id"] = "talhao_id não pertence a nenhuma propriedade sua"

        if (
            propriedade is not None
            and not Propriedade.objects.filter(id=propriedade.pk, user=user).exists()
        ):
            erros["propriedade_id"] = "propriedade_id não pertence ao seu utilizador"

        # A propriedade tem de ser a mesma do talhao. Sem esta checagem um
        # `talhao_id` proprio com `propriedade_id` alheio produz uma nota que
        # pertence a uma fazenda e esta escrita noutra.
        if talhao is not None and propriedade is not None and not erros:
            if talhao.propriedade_id != propriedade.pk:
                erros["propriedade_id"] = (
                    "o talhao seleccionado nao pertence a esta propriedade"
                )

        if erros:
            raise serializers.ValidationError(erros)

        return attrs

    def validate_talhao_id(self, valor):
        # Com `source="talhao"`, o valor aqui e' o **objecto** `Talhao`, nao
        # o id. Filtrar por `id=<Talhao>` levanta `TypeError` e devolve 500 —
        # que foi a primeira coisa que os testes apanharam.
        if valor is None:
            return valor
        user = self.context["request"].user
        if not Talhao.objects.filter(id=valor.pk, propriedade__user=user).exists():
            raise serializers.ValidationError(
                "talhao_id não pertence a nenhuma propriedade sua"
            )
        return valor

    def validate_propriedade_id(self, valor):
        if valor is None:
            return valor
        user = self.context["request"].user
        if not Propriedade.objects.filter(id=valor.pk, user=user).exists():
            raise serializers.ValidationError(
                "propriedade_id não pertence ao seu utilizador"
            )
        return valor

    def validate_conteudo(self, valor):
        if not valor or not str(valor).strip():
            raise serializers.ValidationError("uma nota sem texto não é uma nota")
        return str(valor).strip()


@exigir_sessao_json
def nota_create(request):
    """`POST /api/caderno/notas/` — o que o `sync.js:105` chama.

    Idempotente por `offline_id`: o browser pode reenviar a mesma nota em
    cada sync (a `markNoteSynced` só corre depois de um 2xx, e uma nota
    escrita offline vai repetir enquanto o servidor estiver em baixo). Sem
    isto, um produtor offline uma tarde acabava com a mesma nota gravada
    vinte vezes.
    """
    try:
        body = json.loads(request.body.decode() or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "erro": "JSON inválido"}, status=400)

    ser = NotaCampoSerializer(data=body, context={"request": request})
    if not ser.is_valid():
        return JsonResponse(
            {"ok": False, "erro": "nota inválida", "campos": ser.errors},
            status=400,
        )

    offline_id = ser.validated_data.get("offline_id")
    if offline_id is not None:
        existing = NotaCampo.objects.filter(
            user=request.user, offline_id=offline_id
        ).first()
        if existing:
            return JsonResponse(
                {"ok": True, "id": existing.pk, "duplicado": True},
                status=200,
            )

    # `validated_data` traz as chaves pelo `source` declarado no serializer: sao
    # `talhao`, `cultura` e `propriedade` — os **objectos** ja resolvidos, nao
    # os ids. Ler `talhao_id` dava `None` e gravava a nota sem talhao.
    #
    # `registada_em` e' `timezone.now()` quando ausente: um default assumido e
    # declarado, nunca uma data inventada. Ver `validate_registada_em`.
    dados = ser.validated_data
    talhao = dados.get("talhao")

    nota = NotaCampo.objects.create(
        user=request.user,
        registada_em=dados.get("registada_em") or timezone.now(),
        **{
            k: v
            for k, v in dados.items()
            if k not in ("registada_em", "talhao", "cultura", "propriedade")
        },
        talhao=talhao,
        cultura=dados.get("cultura"),
        propriedade=dados.get("propriedade")
        or _propriedade_do_talhao(talhao, request.user),
    )
    return JsonResponse(
        {"ok": True, "id": nota.pk, "offline_id": nota.offline_id}, status=201
    )


def _propriedade_do_talhao(talhao, user):
    """A propriedade do talhão, se ele for do utilizador.

    Serve para o `GET` trazer o nome da fazenda sem o browser ter de mandar
    `propriedade_id` — que no `sync.js` não é enviado.
    """
    if talhao is None:
        return None
    # O serializer ja restringiu o queryset ao utilizador, mas a funcao e'
    # chamada com objectos vindos de `validated_data` — e um objecto nao
    # valida a si proprio. A confirmacao e' o que torna a funcao segura
    # independentemente de quem a chame.
    #
    # Devolve a **Propriedade**, nao o `pk`: `objects.create(propriedade=1)`
    # levanta `ValueError`, porque a FK espera a instancia.
    return Propriedade.objects.filter(id=talhao.propriedade_id, user=user).first()


@exigir_sessao_json
def nota_voice(request):
    """`POST /api/caderno/voice/` — 501, e diz porquê.

    O `sync.js:252` chama esta rota. Devolver 404 punha o produtor a tentar
    outra vez; devolver **501 Not Implemented** com o motivo é dizer "isto
    não existe ainda, e aqui está o que falta".

    O que falta, medido: transcrição (o `transformers.js`/Whisper já existe em
    `app/static/js/ia-local/whisper-audio.js`, mas produz texto — não grava
    nota), modelo de `Audio` com `FileField` e `MEDIA_ROOT`, e a política de
    retenção. Nenhuma dessas três é um detalhe.
    """
    return JsonResponse(
        {
            "ok": False,
            "erro": "Caderno de voz ainda não implementado",
            "falta": [
                "modelo de áudio com FileField e MEDIA_ROOT",
                "endpoint de transcrição (o Whisper local existe mas não grava)",
                "política de retenção e quota de ficheiros",
            ],
            "referencia": "app/static/js/pwa/sync.js:252",
        },
        status=501,
    )


@exigir_sessao_json
def nota_fotos(request):
    """`POST /api/caderno/fotos/` — o que o `sync.js:144` chama.

    MEDIDO 2026-10-05. Antes devolvia **501** com a lista do que faltava.
    A lista era a especificacao, e esta e' a implementacao dela:

        ~~validacao de tipo MIME e tamanho~~   -> `FORMATOS_FOTO` +
                                                    `validate_upload_size`,
                                                    no modelo
        ~~MEDIA_ROOT em producao~~             -> `base.py:219` resolve;
                                                    Caddy serve `/media/`
        ~~associacao da foto a uma NotaCampo~~  -> `FotoNota.nota`

    O que **nao** foi feito, e deliberado: transcricao de voz. `voice/`
    continua em 501, porque essa precisa de decisao de produto (guardar
    audio ou so o texto?) e nao de codigo.

    POR QUE A FOTO PRECISA DO `nota_id` E NAO SO DO `offline_id`
    ============================================================
    A fila offline pode trazer a foto **antes** da nota: o produtor fotografa
    as 9h, escreve a nota as 9h05 num sitio sem rede, e o sync comeca pela
    ordem em que os pedidos acabaram. Se a foto exigir que a nota ja exista,
    a primeira sincronizacao de uma manha inteira perde todas as fotos — que
    e' o pior sitio possivel para perder: no campo, sem rede, sem segunda
    oportunidade.

    Por isso o `nota` e' nulo e a ligacao faz-se pelo `offline_id` que veio
    do mesmo `store` do IndexedDB. A foto fica orfa, e a nota busca-a depois.
    Rejeitar a foto "porque a nota ainda nao existe" seria devolver 400 ao
    browser que nao tem outro sitio para a meter.
    """
    # O browser envia multipart; `request.FILES` e' a unica forma de o ler.
    ficheiro = request.FILES.get("image") or request.FILES.get("ficheiro")
    if ficheiro is None:
        return JsonResponse(
            {
                "ok": False,
                "erro": "sem ficheiro",
                "detalhe": "envia o campo 'image' como multipart/form-data",
            },
            status=400,
        )

    # --- extensao e tamanho ------------------------------------------------
    # O `FileExtensionValidator` roda na atribuicao do campo, mas um 400 de
    # `ValidationError` no meio de uma gravacao da' um 500. Validar aqui
    # primeiro da uma mensagem que o browser consegue mostrar.
    nome = (ficheiro.name or "").lower()
    extensao = nome.rsplit(".", 1)[-1] if "." in nome else ""
    if extensao not in FORMATOS_FOTO:
        return JsonResponse(
            {
                "ok": False,
                "erro": "formato de imagem nao aceite",
                "recebido": extensao or "(sem extensao)",
                "aceites": FORMATOS_FOTO,
            },
            status=400,
        )

    limite = MAX_UPLOAD_MB * 1024 * 1024
    if getattr(ficheiro, "size", 0) > limite:
        return JsonResponse(
            {
                "ok": False,
                "erro": "ficheiro demasiado grande",
                "limite_mb": MAX_UPLOAD_MB,
            },
            status=400,
        )

    # --- nota de origem ----------------------------------------------------
    offline_id_nota = request.POST.get("nota_offline_id") or request.POST.get(
        "offline_id"
    )
    nota = None
    if offline_id_nota:
        try:
            nota = NotaCampo.objects.filter(
                user=request.user, offline_id=int(offline_id_nota)
            ).first()
        except (TypeError, ValueError):
            nota = None

    # Idempotencia: o browser reenvia enquanto nao recebe 2xx. Sem isto, uma
    # manha offline produz a mesma foto duas vezes.
    offline_id_foto = request.POST.get("foto_offline_id") or request.POST.get("foto_id")
    if offline_id_foto:
        try:
            ja_existe = FotoNota.objects.filter(
                user=request.user, offline_id=int(offline_id_foto)
            ).first()
        except (TypeError, ValueError):
            ja_existe = None
        if ja_existe is not None:
            return JsonResponse(
                {"ok": True, "id": ja_existe.pk, "duplicado": True}, status=200
            )

    # --- coordenadas -------------------------------------------------------
    # Vem do `navigator.geolocation` do telefone, no momento da captura. Sem
    # isto, a foto e' uma imagem e um `sem_dado` silencioso.
    def _coord(nome_campo):
        """Le uma coordenada do `request.POST` como `Decimal` arredondado.

        MEDIDO 2026-10-05. Este metodo ja foi escrito duas vezes e falhou as
        duas, e a segunda vez e' a instructive.

        **Primeira tentativa**: `float` + `round(x, 6)`. Recebia HTTP 400 em
        todas as fotos georreferenciadas, com *"Certifique-se de que nao tenha
        mais de 6 casas decimais"*.

        **Segunda tentativa**: `decimal_places=7` no modelo. Continuou a
        falhar. Porque o problema nunca foi a precisao.

        **A causa real**: `DecimalField.to_python()` converte o `float`
        `-15.7942` para `Decimal`, mas o `Decimal` de um `float` em Python
        guarda a **notacao cientifica** — `Decimal(-15.7942)` e'
        `Decimal('-1.57942E+1')`. O `DecimalValidator` conta os caracteres a
        seguir ao ponto e encontra o expoente: "7 casas decimais". A
        mensagem acusava o produtor de ter enviado um numero com casas a mais
        que nunca teve.

        **A correccao**: passar `Decimal` com a string ja arredondada. E'
        `Decimal("%.7f" % valor)` — a string formata com 7 casas, e o
        `Decimal` dela tem 7 casas. O que entra e' o que e' guardado.

        Isto e' a mesma familia do bug do `talhao_id` do Caderno: uma
        validacao correcta, alimentada pelo tipo errado.
        """
        bruto = (request.POST.get(nome_campo) or "").strip()
        if not bruto:
            return None
        try:
            # `Decimal(str(valor))` preserva a notacao que o utilizador
            # escreveu; `Decimal(float)` inventa notacao cientifica.
            return Decimal(bruto).quantize(
                Decimal(1).scaleb(-COORD_DECIMAL_PLACES),
                rounding=ROUND_HALF_UP,
            )
        except (ArithmeticError, ValueError):
            return None

    lat = _coord("latitude")
    lon = _coord("longitude")
    precisao = _coord("precisao_metros") or _coord("accuracy")

    if lat is not None and not (Decimal(-90) <= lat <= Decimal(90)):
        return JsonResponse(
            {"ok": False, "erro": "latitude fora do intervalo"}, status=400
        )
    if lon is not None and not (Decimal(-180) <= lon <= Decimal(180)):
        return JsonResponse(
            {"ok": False, "erro": "longitude fora do intervalo"}, status=400
        )

    propriedade = nota.propriedade if nota else None
    if propriedade is None:
        prop_id = request.POST.get("propriedade_id")
        if prop_id:
            propriedade = Propriedade.objects.filter(
                id=prop_id, user=request.user
            ).first()

    # `update_fields` nao serve aqui: `coordenada_confiavel` depende de valores
    # calculados, e um `create` nao tem esse problema.
    foto = FotoNota(
        nota=nota,
        user=request.user,
        propriedade=propriedade,
        legenda=(request.POST.get("legenda") or request.POST.get("caption") or "")[
            :200
        ],
        latitude=lat,
        longitude=lon,
        precisao_metros=precisao,
        # So' e' confiavel se veio coordenada **e** precisao. Uma coordenada
        # sem precisao e' um ponto sem qual de exacteza — util, mas nao
        # georreferenciada no sentido que uma auditoria exige.
        coordenada_confiavel=bool(lat is not None and lon is not None and precisao),
        ficheiro=ficheiro,
    )
    if offline_id_foto:
        try:
            foto.offline_id = int(offline_id_foto)
        except (TypeError, ValueError):
            foto.offline_id = None

    try:
        # `full_clean` e' metodo do modelo. O `exclude` existe porque o
        # `ImageField` valida o valor **gravado** — antes de gravar, o
        # `UploadFile` ainda nao tem nome em disco, e o validador leria
        # `value.name` e levantaria numa situacao que vai correr bem.
        foto.full_clean(exclude=["ficheiro"])
    except ValidationError as e:
        return JsonResponse(
            {
                "ok": False,
                "erro": "foto invalida",
                "campos": getattr(e, "message_dict", None) or str(e),
            },
            status=400,
        )

    try:
        foto.save()
    except ValidationError as e:
        # O `FileExtensionValidator` e' o validador que costuma rebentar aqui:
        # `validate_upload_size` passa, mas a extensao nao, e a gravacao
        # levanta depois da resposta 200 ja estar a ser construida.
        return JsonResponse(
            {
                "ok": False,
                "erro": "foto invalida",
                "campos": getattr(e, "message_dict", None) or str(e),
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "id": foto.pk,
            "nota_id": nota.pk if nota else None,
            "coordenada_confiavel": foto.coordenada_confiavel,
        },
        status=201,
    )
