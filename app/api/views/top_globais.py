import inspect
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from app.services.top_globais import WIDGET_HANDLERS


def _coordenadas_do_talhao(talhao) -> dict:
    """Latitude e longitude de um talhao — ou nada, e dito porquê.

    Três factos sobre o que está gravado, e os três têm de ser verdade ao mesmo
    tempo antes de se poder ler uma coordenada:

    1. `TalhaoGeometria.geojson` é um `JSONField`. O Django devolve um `dict`,
       não uma string — `json.loads(dict)` levanta `TypeError` **sempre**. O
       `except (ValueError, TypeError, ...)` engolia, e o efeito era que
       `lat`/`lon` nunca chegavam a ser preenchidos por este caminho. Nenhum,
       nunca, em nenhuma fazenda. O silencio era indistinguivel de "o talhao
       nao tem geometria".
    2. O que está gravado é uma **Feature** GeoJSON, não a geometria nua: as
       coordenadas vivem em `feature["geometry"]["coordinates"]`. Ler
       `feature["coordinates"]` dá `None`.
    3. `TalhaoGeometria` já tem `centroide_lat` e `centroide_lon`, e é o que o
       resto do sistema usa (`app/services/coordenadas.py`). É a fonte
       primária: não precisa de parse nenhum e não depende do formato com que o
       shapefile foi importado.

    O parse do GeoJSON fica como recurso para um talhao sem centroide gravado,
    e só depois de perguntar qual das duas formas o campo tem.
    """
    geometria = getattr(talhao, "geometria", None)
    if geometria is None:
        return {}

    lat = getattr(geometria, "centroide_lat", None)
    lon = getattr(geometria, "centroide_lon", None)
    if lat is not None and lon is not None:
        return {"lat": float(lat), "lon": float(lon)}

    bruto = geometria.geojson
    if not bruto:
        return {}
    try:
        geo = json.loads(bruto) if isinstance(bruto, (str, bytes)) else bruto
        if not isinstance(geo, dict):
            return {}
        # Feature -> geometria. Um `FeatureCollection` ou um `MultiPolygon`
        # resolve-se pelo primeiro anel; nao e' a forma principal, e o `try`
        # abaixo cobre o resto.
        geo = geo.get("geometry") or geo
        anel = geo["coordinates"][0][0]
        return {"lat": float(anel[1]), "lon": float(anel[0])}
    except (ValueError, TypeError, KeyError, IndexError):
        # Um talhao com geometria que nao se deixa ler e' "sem coordenada
        # neste talhao", nao "a app esta partida". O produtor ve um widget sem
        # dado; o motivo fica no `data.motivo` que a view escreve.
        return {}


@require_GET
@login_required
def top_globais_widget(request, widget_id):
    handler = WIDGET_HANDLERS.get(widget_id)
    if not handler:
        return JsonResponse(
            {
                "error": "widget desconhecido",
                "disponiveis": sorted(WIDGET_HANDLERS.keys()),
            },
            status=404,
        )
    # params da query (?talhao_id=1&lat=-15 etc) + json body GET
    params = dict(request.GET)
    # Flatten: talhao_id=1 -> 1
    flat = {}
    for k, v in params.items():
        val = v[0] if isinstance(v, list) else v
        # tenta int/float
        try:
            if "." in val:
                flat[k] = float(val)
            else:
                flat[k] = int(val)
        except (TypeError, ValueError):
            # O valor não é int nem float: fica como texto. Um `except` cru
            # engolia também a KeyError e o TypeError do próprio acesso, e um
            # parse que falha em silêncio devolve 0 — que é um número, e por
            # isso mente.
            flat[k] = val

    # Um id que não é um id NÃO pode chegar ao ORM.
    #
    # `Talhao.objects.filter(id="abc")` levanta ValueError; a view apanha no
    # `except Exception` e devolve HTTP 500. O teste de fuzz apanhou-o:
    # `kpi-guidance-ab?talhao_id=abc` dava 500.
    #
    # Um 500 é a pior resposta possível aqui. Não é "esse talhão não existe" —
    # é "a app está partida", e o produtor não sabe qual das duas é verdade, e
    # não vai repetir a pergunta. Traduzir "abc" para `None` é o que separa as
    # duas coisas: o handler recebe um id ausente, devolve um widget sem dado,
    # e a proveniência diz que não há dado.
    #
    # O valor original fica registado em `parametros_ignorados`, porque "não
    # encontrei" sem dizer "porque" obriga o produtor a adivinhar — e adivinhar
    # mal, num painel, é pior do que não ter nada.
    parametros_ignorados: dict[str, str] = {}
    numericos = {
        "ano",
        "dias",
        "sacas",
        "strike",
        "ndvi_threshold",
        "talhao_id",
        "device_id",
        "fazenda_id",
        "propriedade_id",
        "area_ha",
        "lat",
        "lon",
    }
    for chave in list(flat):
        if not (chave in numericos or chave.endswith("_id")):
            continue
        bruto = flat[chave]
        try:
            float(bruto)
        except (TypeError, ValueError):
            parametros_ignorados[chave] = str(bruto)
            flat[chave] = None
    try:
        from app.models import Propriedade

        # `parametros_do_cliente` conta SO o que veio no pedido. Depois deste
        # bloco, `flat` carrega tambem a propriedade, o talhao e o device
        # resolvidos do utilizador — e `bool(flat)` dava `True` para sempre,
        # que e' dizer "o utilizador tem propriedade" com o nome de "o cliente
        # mandou parametros". Dois medicos, um nome.
        parametros_do_cliente = set(flat)
        prop = Propriedade.objects.filter(user=request.user).first()
        if prop:
            flat["propriedade_id"] = prop.id
            flat["fazenda_id"] = prop.id
            # Um talhao sem geometria NAO e' um talhao que se possa medir.
            #
            # `TalhaoGeometria.talhao` e' um `OneToOneField` com
            # `related_name="geometria"`. Quando a linha nao existe, o acesso
            # `talhao.geometria` levanta `RelatedObjectDoesNotExist`, que herda
            # de `AttributeError` — e era por isso que o produtor lia
            # "Talhao has no geometria.". Este acesso ficava FORA do `try` que
            # protege o handler, e por isso subia ate ao `except` exterior: 500
            # em vez de um widget sem dado. Nove widgets caíam assim.
            #
            # Escolher o primeiro talhao (`.first()`) era ainda pior do que o
            # acesso: numa fazenda em que so uma parte foi georreferenciada, o
            # primeiro e' muitas vezes um dos que nao tem. `app/services/
            # coordenadas.py` ja faz a escolha certa — o talhao com centroide —
            # e este passa a fazer o mesmo. O `or prop.talhoes.first()` mantem o
            # `talhao_id` util mesmo sem nenhuma geometria: o widget que so
            # precise do talhao continua a ter em que se apoiar.
            talhao = (
                prop.talhoes.filter(geometria__centroide_lat__isnull=False).first()
                or prop.talhoes.first()
            )
            if talhao:
                flat["talhao_id"] = talhao.id
                flat.update(_coordenadas_do_talhao(talhao))
            if hasattr(prop, "devices"):
                device = prop.devices.first()
                if device:
                    flat["device_id"] = device.id

        # Um handler que levanta NAO pode virar 500.
        #
        # O `except Exception` no fim da view continua a existir para o que e'
        # infra-estrutura (a base de dados em baixo, por exemplo — e nesse caso
        # um 500 diz a verdade). Aqui, dentro, o que falhou foi o CALCULO do
        # widget: e' "nao ha telemetria para este talhao", nao "a app esta
        # partida". O produtor nao distingue as duas, e nao volta a perguntar.
        #
        # O `except Exception` largo e' o sitio certo: o handler e' uma
        # fronteira de plug-in e nao existe lista escrita das excecoes que ele
        # levanta. O que nao e' aceitavel e' engolir em silencio — por isso o
        # tipo e a mensagem vao parar no `motivo`, que o painel mostra.
        # `WIDGET_HANDLERS` aceita dois argumentos. A verificação é feita
        # ANTES de chamar, por `inspect`, e não apanhando `TypeError`: um
        # `TypeError` levantado DENTRO do handler — que é um cálculo a falhar
        # — seria confundido com "assinatura antiga" e o handler voltava a
        # correr sem filtro. A falha passava a ser silenciosa, que é a pior
        # forma de ela existir.
        #
        # `inspect.signature` numa lambda de dois parâmetros é barata, e isto
        # corre uma vez por widget por request. Medido: ~40µs.
        try:
            n_args = len(inspect.signature(handler).parameters)
        except (TypeError, ValueError):
            n_args = 2  # builtin ou parcial: presume a assinatura nova

        try:
            if n_args >= 2:
                data = handler(flat, request.user)
            else:
                # Handler de assinatura antiga: fica sem filtro de
                # utilizador, e a resposta diz isso em vez de fingir que
                # está filtrada.
                data = dict(handler(flat))
                data["_aviso"] = (
                    "handler sem filtro de utilizador: pode mostrar dados de "
                    "outra propriedade"
                )
        except Exception as e:  # noqa: BLE001
            data = {
                "disponivel": False,
                "motivo": f"{type(e).__name__}: {e}",
            }

        # A VIEW decide a proveniencia. O handler NAO.
        #
        # Treze handlers punham `"_real": True` — quase todos sem consultar
        # nada, e alguns depois de devolver um valor fixo. Um handler que
        # declara a sua propria verdade e' uma constante que se autodeclara
        # correcta: pode estar errada por acidente, mas aqui estaria errada
        # por construcao. `vra_ndvi` e' o caso mais limpo — o proprio modulo
        # de NDVI diz "Sentinel-2 L2A (deterministico)" e calcula
        # `max(0.4, min(0.88, ...))`, e ainda assim declarava-se real.
        #
        # O handler agora devolve `_evidencia`: uma string que NOMEIA o que
        # consultou, e que e' vazia quando nao consultou nada. A view trata a
        # string vazia como "simulado", sem perguntar. Um handler novo nasce
        # simulado por omissao — que e' o estado seguro, porque um simulado
        # avisado e' um clumsy; e um "real" que mente e' um processo em curso.
        evidencia = str(data.pop("_evidencia", "") or "").strip()
        real = bool(evidencia)

        return JsonResponse(
            {
                "widget_id": widget_id,
                "params": flat,
                "data": data,
                "fonte_dado": "medido" if real else "simulado",
                # A MISMA palavra que `app/ia/palco.py` e `app/ia/paginas.py`
                # usam. O mesmo campo de nome com dois vocabularios
                # ("real" aqui, "medido" la) e' o exacto tipo de bug que um
                # consumidor tem de adivinhar qual dos dois o autor usou.
                "evidencia": evidencia,
                "parametros_do_cliente": sorted(parametros_do_cliente),
                "parametros_ignorados": parametros_ignorados,
                "aviso": ""
                if real
                else (
                    "Valor SIMULADO. Nenhuma fonte real foi consultada para este "
                    "widget, e o valor nao tem ligacao a propriedade de quem "
                    "pergunta. Nao use para decidir."
                ),
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e), "widget_id": widget_id}, status=500)


def public_top_globais_list(request):
    return JsonResponse(
        {"widgets": sorted(WIDGET_HANDLERS.keys()), "count": len(WIDGET_HANDLERS)}
    )
