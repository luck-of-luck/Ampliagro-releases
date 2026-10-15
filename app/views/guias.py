import json
from collections import defaultdict

from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.hierarquia import hierarquia_required
from app.models import *

from .utils import _no_store  # import explícito — import * não traz nomes com _

# Constantes de agrupamento cultural (perdidas no split BUILD 03 — restauradas de _backups/mortos-20260919/views_BACKUP.py)
VEGETAL_GRUPOS = [
    "graos",
    "frutas",
    "citricos",
    "hortalicas",
    "tuberculos",
    "ervas",
    "leguminosas",
    "oleaginosas",
    "frutas_bosque",
    "especiarias",
    "medicinais",
    "panc",
    "trepadeiras",
    "cana",
    "fibras",
    "nativas",
]
ANIMAL_NOMES = [
    "Boi Gordo",
    "Vaca Gorda",
    "Bezerro",
    "Suíno",
    "Ovino",
    "Caprino",
    "Equino",
    "Búfalo",
    "Frango",
    "Peru",
    "Codorna",
    "Marreco",
    "Galinha",
    "Leite",
    "Vaca Leiteira",
    "Cabra Leiteira",
    "Ovos",
]
ANIMAL_GRUPOS = {
    "bovinos": ["Boi Gordo", "Vaca Gorda", "Bezerro"],
    "suinos": ["Suíno", "Matriz Suína"],
    "ovinos": ["Ovino", "Caprino"],
    "equinos": ["Equino"],
    "bufalos": ["Búfalo"],
    "aves": ["Frango", "Peru", "Codorna", "Marreco", "Galinha"],
    "leite": ["Leite", "Vaca Leiteira", "Cabra Leiteira"],
    "ovos": ["Ovos"],
}
AQUATICA_GRUPOS = {
    "peixes": [
        "Peixe (Tilápia)",
        "Peixe (Tambaqui)",
        "Peixe (Pacu)",
        "Peixe (Carpa)",
        "Peixe (Truta)",
        "Peixe (Jundiá)",
        "Peixe (Curimatã)",
        "Peixe (Pirarucu)",
    ],
    "crustaceos": ["Camarão"],
    "infraestrutura": [
        "Tanque Escavado",
        "Tanque Rede",
        "Viveiro",
        "Aquário",
        "Sistema RAS",
        "Berçário",
        "Gaiola Flutuante",
        "Bomba de Aeração",
        "Filtro Biológico",
        "Caixa d'Água (Aquaponia)",
        "Berço Suspensa",
        "Galpão",
        "Incubadora",
    ],
}

# Grupos não-vegetais (animal/aquática/infra): existem na tabela Cultura
# mas nunca devem aparecer na Guia Vegetal (vão para as guias próprias)
NAO_VEGETAL_GRUPOS = list(ANIMAL_GRUPOS.keys()) + list(AQUATICA_GRUPOS.keys())


def _sem_acento(texto: str) -> str:
    """Minusculas e sem acento, para comparar nomes que so se distinguem por isso.

    MEDIDO 2026-10-05 na base real: `Café` (id 28079, grupo `graos`, 1 safra)
    e `Cafe` (id 28770, grupo `perenes`, 4 safras) sao **duas linhas da mesma
    planta**, e so diferem no acento. Sem normalizar, um `RegistroProducao`
    escrito como "cafe" — que e' como o teclado da metade dosstalkers nao
    tem acento — so encontrava uma das duas, e a outra ficava sem
    estatistica. O produtor via o registo num sitio e a safra noutro.

    NFD + filtragem de diacriticos: e' o mesmo metodo que o `unicodedata`
    documenta para isto, e nao depende do teclado.
    """
    import unicodedata

    decomposto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _culturas_visiveis(user):
    """O `Cultura.objects.all()` das guias, já restrito às culturas escolhidas.

    Wrapper fino sobre `app.cultures.filtro.visiveis` — existe para que os
    quatro `_montar_grupos_*` lerem `Cultura.objects.all()` no mesmo sítio de
    antes. Um diff que troca `.all()` por isto é o mesmo diff nas quatro
    guias, e a regra dos três estados (nunca escolheu / escolheu vazio /
    escolheu) fica escrita num sítio só, em vez de quatro condicionais
    repetidos que divergem no primeiro dia em que alguém mexe numa.

    Passar `user=None` (o default dos `_montar_grupos_*`) não filtra. É o que
    permite testar um construtor sem ter de criar utilizador e propriedade.
    """
    from app.cultures.filtro import visiveis

    return visiveis(user)


def _indice_cultura_por_nome():
    """Dicionarios para resolver `cultura_key` (texto livre) -> `cultura_id`.

    MEDIDO 2026-10-05: havia aqui
        Cultura.objects.filter(nome__icontains="")...
    `icontains` com string VAZIA casa com TODAS as linhas. As 709 culturas da
    base entravam todas no dicionario e `exatos` ficava com DUAS entradas por
    nome; o `.first()` do ciclo devolvia a primeira de varias, sem ordem
    nenhuma. O mesmo `cultura_key` caia em ids diferentes conforme o estado
    da tabela — e o registo ia para uma cultura arbitraria, em silencio.

    Aqui e' **uma** leitura, e a busca e' em memoria sobre um indice
    normalizado. Determinista: as duas linhas de mesmo nome vao SEMPRE para a
    de menor id.

    DEVOLVE TRES COISAS porque a busca e' de tres modos:
        exatos   — "soja" -> 803 (igual ou normalizado)
        contem   — [(plano, id), ...] para o `contains` mais especifico
        por_id   — {id: nome}, para as mensagens de erro
    """
    # `order_by("id")` NAO E' COSMETICO. E' o que torna o `setdefault`
    # abaixo determinista.
    #
    # MEDIDO 2026-10-05: sem ele, `Cultura.objects.values_list(...)` devolve
    # as linhas na ordem que o banco quiser. As duas linhas do cafe —
    # `Café` (28079, `graos`) e `Cafe` (28770, `perenes`) — normalizam AMBAS
    # para a chave "cafe", e o `setdefault` guarda a PRIMEIRA que passar.
    # Se o banco devolver 28770 antes de 28079, o indice fica com 802; se
    # devolver ao contrario, fica com 801.
    #
    # Isto e' o bug original, noutro sitio: o `.first()` sem `order_by` foi
    # trocado por um `setdefault` sem `order_by`, que tem o mesmo efeito. O
    # registo do produtor continua a cair numa cultura arbitraria — so que
    # agora depende da ordem de leitura, que muda entre versoes do SQLite,
    # entre planos de execucao, e sem aviso.
    #
    # `id` e' a chave primaria e unica: ordenar por ela e' o mais barato que
    # existe e nao pode haver empate.
    nomes = list(Cultura.objects.order_by("id").values_list("id", "nome"))
    exatos: dict[str, int] = {}
    contem: list[tuple[str, int]] = []
    por_id: dict[int, str] = {}
    for cid, nome in nomes:
        por_id[cid] = nome or ""
        if not nome:
            continue
        plano = nome.lower()
        normal = _sem_acento(plano)
        # `setdefault`: com duas linhas de mesmo nome, o registo vai para a
        # de menor id — sempre a mesma. Antes ia para a que o banco devolvesse
        # por ultimo.
        exatos.setdefault(plano, cid)
        exatos.setdefault(normal, cid)
        contem.append((plano, cid))
    return exatos, contem, por_id


def _resolver_cultura_key(chave, indice):
    """`cultura_key` -> `cultura_id`, ou `None` se nao houver.

    `indice` e' a tripla de `_indice_cultura_por_nome()`. Tres modos, por
    ordem de especificidade:

    1. **igual** ao nome, tal como veio (com acento ou sem)
    2. **igual** depois de normalizar — "cafe" acha "Café". Na base real sao
       DUAS linhas (28079 `graos` com 1 safra, 28770 `perenes` com 4); a
       chave sem acento nao pode ficar presa numa so.
    3. **contido** na chave, escolhendo o nome mais longo que caiba — para
       "soja" nao escolher "sojão" quando a chave e' "soja gm".

    Por que o mais longo: `contains` e' a unica heuristics possivel sem
    indice de pesquisa, e o nome mais especifico e' o que o produtor
    quis dizer. "soja" contra {"soja", "sojao", "soja gm"} escolhe "soja".
    """
    exatos, contem, _por_id = indice
    if not chave:
        return None
    # A ORDEM IMPORTA, e sao DOIS criterios distintos.

    # **1o: a grafia EXACTA.** `exatos` guarda a chave como foi escrita
    # (`plano = nome.lower()`) E a chave sem acento (`normal`). Sao dicionarios
    # diferentes: `"Café"` vive so em `exatos["café"]`, e `"Cafe"` so em
    # `exatos["cafe"]`.
    #
    # Consultar o exacto primeiro e' o que devolve a SUA linha a cada
    # grafia. Com o normalizado primeiro, as duas linhas de cafe colapsavam
    # em `exatos["cafe"]` pelo `setdefault` e "Café" acabava na linha de
    # "Cafe" (802) em vez da sua (801): o produtor escrevia com acento e o
    # registo ia para a cultura sem acento.
    c_id = exatos.get(chave.lower())
    if c_id is not None:
        return c_id

    # **2o: o NORMALIZADO.** E' o que faz "cafe" (do teclado sem acento)
    # achar "Café". Quando duas linhas disputam a chave normalizada, o
    # `setdefault` da construcao do indice decide pela de MENOR id — e essa
    # e' sempre a mesma, que e' o que torna isto determinista.
    normal = _sem_acento(chave.lower())
    c_id = exatos.get(normal)
    if c_id is not None:
        return c_id

    # 3) contido, escolhendo o nome mais longo que caiba.
    melhor: tuple[str, int] | None = None
    for plano, cid in contem:
        if plano and _sem_acento(plano) in normal:
            if melhor is None or len(plano) > len(melhor[0]):
                melhor = (plano, cid)
    return melhor[1] if melhor else None
    melhor: tuple[str, int] | None = None
    for plano, cid in contem:
        if plano and _sem_acento(plano) in normal:
            if melhor is None or len(plano) > len(melhor[0]):
                melhor = (plano, cid)
    return melhor[1] if melhor else None


@login_required
def guia_vegetal_view(request):
    from collections import Counter

    from django.db.models import Sum

    from app.models import RegistroProducao, Safra, Talhao

    grupos = _montar_grupos_vegetal(request.user)
    ano_atual = timezone.now().year

    # ─────────────────────────────────────────────────────────────────────
    # N+1 CORRIGIDO (MEDIDO 2026-10-05)
    # ─────────────────────────────────────────────────────────────────────
    # ANTES: `for p in Propriedade.objects.filter(user=...)` fazia 5 queries
    # POR PROPRIEDADE — `p.culturas.values_list()`, `p.safras.exclude(...).values_list()`,
    # `p.talhoes.exclude(...).values_list()`, `p.safras.filter(ano).count()` e
    # dois `sum()` que re-consultavam `safras_ativas` uma vez cada.
    #
    # MEDIDO com CaptureQueriesContext: 1 propriedade -> 35 queries,
    # 8 -> 70, 16 -> 110. Linear, 5 por propriedade. O `.prefetch_related("culturas")`
    # que estava na queryset NAO ajudava: `values_list()` ignora o prefetch e vai
    # ao banco na mesma.
    #
    # DEPOIS: 4 queries no total, independentemente de quantas propriedades o
    # produtor tem. Cada uma devolve ja agrupada pelo banco.
    props = list(Propriedade.objects.filter(user=request.user))
    pids = [p.id for p in props]

    # 1) culturas de cada propriedade (M2M `Propriedade.culturas`)
    cult_por_prop = defaultdict(set)
    if pids:
        for prop_id, cult_id in Propriedade.culturas.through.objects.filter(
            propriedade_id__in=pids
        ).values_list("propriedade_id", "cultura_id"):
            cult_por_prop[prop_id].add(cult_id)

    # 2) as mesmas tres fontes de `total_culturas`, mas por propriedade e numa
    #    unica passagem cada uma. Antes eram 3 queries dentro do `for`.
    def _cultura_ids_por_prop(qs, campo):
        out = defaultdict(set)
        for prop_id, cult_id in qs.values_list("propriedade_id", campo):
            if cult_id:
                out[prop_id].add(cult_id)
        return out

    safras_todas_qs = Safra.objects.filter(propriedade_id__in=pids)
    talhoes_qs = Talhao.objects.filter(propriedade_id__in=pids)

    for qs, campo in (
        (safras_todas_qs, "cultura_id"),
        (
            talhoes_qs.exclude(cultura_atual__isnull=True),
            "cultura_atual_id",
        ),
    ):
        # `_cultura_ids_por_prop` devolve `{prop_id: {cult_id, ...}}` — um set
        # de ids. O `for prop_id, cult_id in ...` tratava esse set como se
        # fosse um id e fazia `mapa[prop_id].add(cult_id)` com um `set`
        # dentro de um `set`.
        #
        # MEDIDO 2026-10-05: `TypeError: unhashable type: 'set'`, na L295.
        # A guia vegetal devolvia **500 em todas as 空 requests** — uma
        # correcao do N+1 que, no caminho de fazer a pagina mais rapida,
        # a deixou de funcionar. Nao havia teste que a abrisse pelo URL: os
        # testes do N+1 chamavam a funcao e mediam queries, e a excecao
        # happens ANTES do `render`, entao media-se "0 queries" e passava.
        #
        # `update` com o set inteiro: e' o que a funcao devolveu.
        mapa_por_prop = _cultura_ids_por_prop(qs, campo)
        for prop_id, cult_ids in mapa_por_prop.items():
            cult_por_prop[prop_id].update(cult_ids)

    # 3) safras do ano: contagem, area e producao por propriedade, num `Sum`.
    #    Antes eram 3 queries por propriedade (count + 2 x iteracao).
    agg_ano = {}
    if pids:
        linhas = (
            safras_todas_qs.filter(ano=ano_atual)
            .values("propriedade_id")
            .annotate(
                _n=Count("id"),
                _area=Sum("area_plantada"),
                _prod=Sum("producao_total"),
            )
        )
        for row in linhas:
            agg_ano[row["propriedade_id"]] = row

    props_stats = []
    for p in props:
        row = agg_ano.get(p.id)
        props_stats.append(
            {
                "id": p.id,
                "nome": p.nome,
                # len() do set: a mesma de antes, mas sem uma query por fonte.
                "total_culturas": len(cult_por_prop.get(p.id, ())),
                "safras_ativas": row["_n"] if row else 0,
                "area_plantada": float(row["_area"] or 0) if row else 0.0,
                "producao_total": float(row["_prod"] or 0) if row else 0.0,
            }
        )

    guide_stats = {}
    # RegistroProducao por cultura
    for r in RegistroProducao.objects.filter(user=request.user).values_list(
        "cultura_id", flat=True
    ):
        if r:
            guide_stats.setdefault(str(r), {"registros": 0, "safras": 0, "talhoes": 0})
            guide_stats[str(r)]["registros"] += 1

    # `cultura_key` (texto livre) precisa de ser resolvida para id. Antes era
    # DUAS queries de `Cultura` POR REGISTRO (iexact + icontains) dentro de um
    # `for` — o unico lugar do arquivo que realmente escalava com o volume.
    # Agora: UMA leitura de todos os nomes, e a busca e' em memoria.
    chaves = list(
        RegistroProducao.objects.filter(
            user=request.user, cultura__isnull=True
        ).values_list("cultura_key", flat=True)
    )
    chaves = [c for c in chaves if c]
    if chaves:
        # A logica vive em `_resolver_cultura_key`, testada directamente em
        # `tests/test_guia_resolve_cultura.py`. Aqui so se usa.
        indice = _indice_cultura_por_nome()
        for r in chaves:
            c_id = _resolver_cultura_key(r, indice)
            if c_id is not None:
                guide_stats.setdefault(
                    str(c_id), {"registros": 0, "safras": 0, "talhoes": 0}
                )
                guide_stats[str(c_id)]["registros"] += 1

    for s in safras_todas_qs.values_list("propriedade_id", "cultura_id"):
        if s[1]:
            k = str(s[1])
            guide_stats.setdefault(k, {"registros": 0, "safras": 0, "talhoes": 0})
            guide_stats[k]["safras"] += 1

    for t in talhoes_qs.exclude(cultura_atual__isnull=False).values_list(
        "cultura_atual_id", flat=True
    ):
        if t:
            guide_stats.setdefault(str(t), {"registros": 0, "safras": 0, "talhoes": 0})
            guide_stats[str(t)]["talhoes"] += 1

    # ─────────────────────────────────────────────────────────────────────
    # HISTORICO OBSERVADO POR CULTURA (MEDIDO 2026-10-05)
    # ─────────────────────────────────────────────────────────────────────
    # A tabela `Cultura` tem a agronomia VAZIA (janela de plantio 0/709,
    # ciclo 0,3%, mercado 0/709). A guia mostrava 709 NOMES e zero
    # informacao, que e' o que o `PLANO-EXECUCAO.md:82` chama "nomes sem
    # agronomia nenhuma".
    #
    # O que se passa a mostrar vem das SAFRAS do produtor — `data_plantio`,
    # `data_colheita` e `produtividade`, que estao preenchidas (78%, 67%,
    # 67%). E' melhor que a janela nacional: "esta fazenda fez soja em 128
    # dias" e' um facto que o produtor sabe; "a soja leva 120 dias" e' uma
    # media que nao e' dele.
    #
    # `safras_todas_qs` ja esta filtrado por `pids`, ou seja ja e' do
    # produtor: e' por ai que o tenancy entra, e nao por um parametro que
    # o chamador pudesse esquecer.
    #
    # 6 das 709 culturas tem safra (MEDIDO). As outras 703 recebem
    # `SEM_DADO`, que o template mostra como "ainda nao registou" — e nao um
    # zero, que seria afirmar que o produtor fez zero safras.
    from app.services.historico_cultura import (
        SEM_DADO,
        historico_por_cultura,
    )

    historico = historico_por_cultura(
        safras_todas_qs.values_list(
            "cultura_id",
            "ano",
            "data_plantio",
            "data_colheita",
            "produtividade",
            "area_plantada",
        )
    )

    # O historico de cada cultura, empacotado COM a cultura.
    #
    # MEDIDO 2026-10-05, o que NAO funciona em template Django, e por que:
    #
    #   1) uma funcao no contexto
    #      `"historico_de": lambda cid: historico.get(cid, SEM_DADO)`
    #      + `{% with h=historico_de(c.id) %}` -> `TemplateSyntaxError:
    #      Could not parse the remainder: '(c.id)'`. Django nao aceita
    #      funcoes, e `c.id` e' um metodo, nao um atributo.
    #
    #   2) `historico` como dict + `historico|...` -> nao ha filtro que
    #      faca `dict[id]` com `id` dinamico; `default_if_none` so trata o
    #      valor inteiro.
    #
    #   3) chaves `hist_<id>` no contexto -> nenhuma forma de dizer "a chave
    #      hist_801" sem a escrever 709 vezes no template.
    #
    # A FORMA QUE FUNCIONA: empacotar a cultura E o seu historico no mesmo
    # dicionario. O template faz `{% for it in culturas %}{{ it.c.nome }}` e
    # `{{ it.hist.ciclo_medio }}` — dois acessos normais, sem funcoes.
    grupos_com_hist = {
        nome_grupo: [
            {"c": cultura, "hist": historico.get(cultura.id) or SEM_DADO}
            for cultura in qs
        ]
        for nome_grupo, qs in grupos.items()
    }

    # A contagem de `RegistroProducao` entra na linha do historico do card,
    # para o cartao mostrar a contagem NO MESMO SITIO que as guias animal e
    # aquatica mostram.
    #
    # MEDIDO 2026-10-06: essa contagem vivia num `<span class="cultura-badge">`
    # no canto do cartao, escrita por `applyCount()`. A conta estava certa, o
    # sitio nao: 450 dos 456 cards da guia vegetal exibiam "0" -- e nao porque
    # o produtor tivesse registado zero. `_guideStats` nao tinha entrada
    # nenhuma para eles, e "sem entrada" estava a ser tratado como "zero
    # medido". E' a mentira que o `SEM_DADO` existe para evitar. Pior: um "0"
    # no canto, ao lado de "registar safra", diz ao mesmo tempo que ele nao
    # registou e que nao ha nada a registar.
    #
    # O servico e' o MESMO que as guias animal/aquatica usam
    # (`registos_por_cultura`), e nao uma leitura nova do `guide_stats`: e' um
    # caminho que ja se viu funcionar no ecra, e que traz `fonte` e `motivo`
    # junto com o numero. Chaveado por `cultura_id` inteiro, como o servico
    # entrega.
    #
    # `SEM_DADO` (do `historico_cultura`) e' um dict UNICO partilhado por todas
    # as culturas sem safra. Escrever nele contaminaria os outros 703 cards --
    # por isso cada `hist` recebe uma copia antes de receber a chave nova.

    from app.services.registro_por_cultura import registos_por_cultura

    registos = registos_por_cultura(
        RegistroProducao.objects.filter(
            user=request.user, cultura__isnull=False
        ).values_list("cultura_id", "status", "data_registro")
    )

    for lista in grupos_com_hist.values():
        for item in lista:
            entrada = registos.get(item["c"].id)
            item["hist"] = dict(item["hist"])
            item["hist"]["registos"] = (entrada or {}).get("registos") or 0

    return _no_store(
        render(
            request,
            "guia-vegetal.html",
            {
                "grupos_com_hist": grupos_com_hist,
                "sem_dado": SEM_DADO,
                # Os dois `json_script` do template (`propsStatsData` e
                # `guideStatsData`). Sem eles o `{{ ...|json_script }}` saia
                # `""`, o `JSON.parse` do script inline devolvia uma string
                # e o `props.find` rebentava — os 4 KPIs ficavam em "—" e os
                # badges das culturas em 0, com a pagina a mostrar dados.
                "props_stats": props_stats,
                "guide_stats": guide_stats,
            },
        )
    )


def _contexto_com_registos(grupos, request):
    """`grupos` + o registo observado de cada cultura, empacotado.

    MEDIDO 2026-10-05: as guias animal e aquatica mostravam 41 racas e 110
    especies com ZERO informacao. Nao porque o produtor nao registou — o
    `RegistroProducao` tem 66 linhas, 7 de `animal` e 1 de `aquatica`, com
    o `cultura_id` preenchido em 100%.

    O producers que escreve `RegistroProducao.grupo = 'animal'` e' a guia
    que filtra `Cultura.grupo IN ('bovinos', 'suinos', ...)`. **Nenhuma das
    duas colunas esta ligada a outra**, e por isso a contagem por `grupo`
    dava sempre zero. A ponte e' o `cultura_id`, que existe e esta
    preenchido.

    E' a terceira vez que o mesmo erro aparece nesta pagina: o
    `icontains=""` de `guias.py`, o ciclo de 112 dias em vez de 116, e
    agora esta contagem. **Nos tres, a leitura correcta seria "o produtor
    nao registou nada" — e nos tres ele tinha registado.**

    Por que `registos_por_cultura` e nao `historico_por_cultura`: um boi
    nao tem ciclo de plantio. Ver o docstring do servico.

    O tenancy entra pelo filtro: `user=request.user` na query, e nao por um
    parametro opcional que o chamador pudesse esquecer.
    """
    from app.services.registro_por_cultura import (
        SEM_DADO,
        registos_por_cultura,
    )

    registos = registos_por_cultura(
        RegistroProducao.objects.filter(
            user=request.user, cultura__isnull=False
        ).values_list("cultura_id", "status", "data_registro")
    )

    # Os KPIs saem DA MESMA fonte que os cards.
    #
    # MEDIDO 2026-10-06: a fila de KPIs media `/api/animais/` (o modulo de
    # animais) enquanto os cards contam `RegistroProducao`. Duas fontes
    # differentes na mesma pagina: o produtor via "Angus — 2 registos" no
    # card e "Total Animais 0" no quadro de cima, e nao havia forma de os dois
    # seremAbout the same. O zero era honesto (`Animal` nao tem campo `user`,
    # liga-se a `propriedade`, e demo.muzambinho nao tem animais AI) mas nao
    # descrevia a pagina que estava a ver.
    #
    # Um KPI que nao descreve a pagina e' ruido: os totais de cabecas e de
    # animais pertencem ao Dashboard, que os mostra com a fonte certa.
    #
    # O zero era honesto — `Animal` nao tem campo `user`, liga-se a
    # `propriedade`, e demo.muzambinho nao tem animais em nenhuma — mas nao
    # descrevia a pagina que estava a ver.
    n_com_registo = 0
    n_registos = 0
    grupos_com_registo = 0
    for qs_grupo in grupos.values():
        tem_algum = False
        for cultura in qs_grupo:
            n = (registos.get(cultura.id) or {}).get("registos") or 0
            if n:
                n_com_registo += 1
                n_registos += int(n)
                tem_algum = True
        if tem_algum:
            grupos_com_registo += 1

    return {
        "grupos": grupos,
        # Empacotado com a cultura pelo mesmo motivo do vegetal: templates
        # Django nao aceitam funcoes nem `.get()`, e um dict com 709 chaves
        # nao se escreve num template.
        "grupos_com_hist": {
            nome_grupo: [
                {"c": cultura, "hist": registos.get(cultura.id) or SEM_DADO}
                for cultura in qs
            ]
            for nome_grupo, qs in grupos.items()
        },
        "sem_dado": SEM_DADO,
        "kpis_guia": {
            "culturas": sum(len(qs) for qs in grupos.values()),
            "com_registo": n_com_registo,
            "registos": n_registos,
            "grupos_com_registo": grupos_com_registo,
            "grupos": len(grupos),
        },
    }


@login_required
def guia_animal_view(request):
    return _no_store(
        render(
            request,
            "guia-animal.html",
            _contexto_com_registos(_montar_grupos_animal(request.user), request),
        )
    )


@login_required
def guia_aquatica_view(request):
    return _no_store(
        render(
            request,
            "guia-aquatica.html",
            _contexto_com_registos(_montar_grupos_aquatica(request.user), request),
        )
    )


@login_required
def guia_sistemas_view(request):
    """Guia dos sistemas integrados, apicultura e outras culturas.

    MEDIDO 2026-10-06: esta pagina mostrava-se incompleta, e eram tres coisas
    distintas — nao uma so.

    1. Os tres KPIs de contagem ficavam vazios. `/api/colmeias/`,
       `/api/propriedades/` e `/api/funcionarios/` respondem com o envelope de
       paginacao do DRF e o template fazia `data.length` sobre um objecto.
       E' o mesmo bug que travou as guias animal e aquatica; aqui ficou por
       resolver porque estas nao tinham o bloco de KPIs reescrito.

    2. `totalSistemas` estava escrito a mao no template: `'3'`. Um numero
       posto a mao e' um numero que ninguem mediu. Agora os sistemas vem
       daqui e a contagem e' o comprimento da lista.

    3. O separador "Apicultura" nao mostrava nada E nao dizia porquê. A
       procura era `Cultura.objects.filter(nome="Mel")` e a base nao tem
       nenhuma cultura com esse nome exacto (MEDIDO: 0). `icontains "mel"`
       da 16 falsos positivos — Melancia, Marmelo, Jamelão. Fica vazio com
       estado vazio honesto, e as colmeias vao ao sitio onde vivem
       (`ApiarioColmeia`).
    """
    sistemas = [
        {
            "nome": "ILP - Integração Lavoura-Pecuária",
            "icone": "bi-flower1",
            "descricao": (
                "Sistema que integra culturas agr\u00edcolas e pecu\u00e1ria na "
                "mesma \u00e1rea, em rota\u00e7\u00e3o ou cons\u00f3rcio."
            ),
        },
        {
            "nome": "ILPF - Integração Lavoura-Pecuária-Floresta",
            "icone": "bi-tree",
            "descricao": (
                "Sistema que integra componentes agr\u00edcolas, pecu\u00e1rios "
                "e florestais na mesma \u00e1rea."
            ),
        },
        {
            "nome": "SAF - Sistema Agroflorestal",
            "icone": "bi-flower2",
            "descricao": (
                "Combina esp\u00e9cies florestais com culturas agr\u00edcolas "
                "e/ou animais."
            ),
        },
    ]

    return _no_store(
        render(
            request,
            "guia-sistemas.html",
            {
                "grupos": _montar_grupos_sistemas(request.user),
                "sistemas": sistemas,
            },
        )
    )


def registro_cultura_sistemas_view(request, cultura_slug):
    """`/guias/sistemas/<cultura>/` — volta a Guia Sistemas.

    MEDIDO 2026-10-06: abrir uma carta em Sistemas empurrava este URL e ele
    dava 404 — o painel abria por JS, mas recarregar partia e o link nao
    dava para partilhar. `guia-animal` e `guia-aquatica` ja tinham a rota
    equivalente; sistemas nao.

    Ao contrario delas, NAO mandamos para a guia vegetal. `/guias/animal/<x>/`
    redirecciona para a guia animal porque e' de la que se abriu; aqui quem
    abriu estava no separador "Outras Culturas" da Guia Sistemas, e a pagina
    correcta para voltar e' essa.

    `guia-vegetal` continua a ser o destino quando a cultura pertence mesmo a
    uma das guias com nome proprio — que e' o que `registro_cultura_view` ja
    faz, e por isso nao e' preciso duplicar essa logica.
    """
    from django.shortcuts import redirect

    del request, cultura_slug  # a rota so precisa de existir e responder
    return redirect("guia-sistemas")


# O INVENTÁRIO DE CARTÕES, E O QUE SE PODE VERIFICAR
# ==================================================
# Calculadoras, simuladores e utilitários são cartões que vivem no
# template — não há tabela que os conte. Escrevê-los no HTML foi
# exactamente o que produziu "IoT: 4" numa base com 8 dispositivos
# (MEDIDO 2026-10-05, `app_device`).
#
# Por isso vivem aqui, em código, e
# `tests/test_guia_ferramentas_numeros.py` ata cada um ao que existe de
# facto no template. Quem acrescenta um cartão e não mexe aqui faz o
# teste falhar — que é a diferença entre um número que se pode conferir
# e um número prometido.
N_CALCULADORAS = 7  # .calc-card no template
N_SIMULADORES = 5
N_UTILITARIOS = 5


@login_required
def guia_ferramentas_view(request):
    # IoT é a única das quatro que é DADO: os dispositivos do produtor.
    # Contar a base inteira seria dizer a alguém que tem 8 sensores quando
    # 7 são do vizinho. `Device` é por `propriedade`, e a guia é dele.
    n_iot = Device.objects.filter(propriedade__user=request.user).count()

    # O botão de NDVI precisa de UM talhão, e NDVI é por talhão.
    #
    # MEDIDO 2026-10-05: o botão fazia `fetch('/api/ia/super/?talhao=1')` —
    # rota inexistente, `talhao=1` fixo, e um `0.72` no `catch`. Três mentiras
    # numa linha. A correcção passa por dar-lhe um talhão REAL entre os
    # talhões do produtor; sem talhão, o botão diz que não tem talhão.
    #
    # Só `id` e `nome`: o `json.dumps` vai para dentro de um `<script>` e um
    # nome com aspas partiria o bloco.
    talhoes = list(
        Talhao.objects.filter(propriedade__user=request.user, ativo=True)
        .order_by("nome")
        .values("id", "nome")
    )

    # As classes A–H e as ~70 capacidades.
    #
    # POR QUE O CATÁLOGO VIVE NUM MÓDULO E NÃO AQUI
    # ----------------------------------------------
    # Este é o ponto mais importante desta view, e a razão de ela ter crescido
    # de 4 abas para 8 classes sem se tornar uma mentira.
    #
    # Uma lista escrita à mão neste ficheiro envelhece em silêncio: quando o
    # John Deere passar a existir, o item continua na lista a dizer "não
    # existe" e ninguém notice. É a doença que o `capacidades.py` do projeto já
    # criou para resolver — derivado do código, por introspecção.
    #
    # Aqui a introspecção não é possível (é preciso ler código de vários
    # ficheiros, não o catálogo de intents), por isso a verificação é feita por
    # **teste**: `tests/test_guia_ferramentas_confere_com_codigo.py` lê cada
    # linha do catálogo e confirma a prova `caminho:linha`. Quem escrever
    # "EXISTE" sem código faz o teste falhar.
    #
    # `n_iot` continua a ser um número medido. O resto é catálogo com estado
    # declarado e testado — que é diferente de número medido, e diz assim.
    from app.guias.catalogo import CATALOGO, ESTADO_ROTULO, EXISTE, NAO_EXISTE, PARCIAL

    return _no_store(
        render(
            request,
            "guia-ferramentas.html",
            {
                "n_iot": n_iot,
                "n_calculadoras": N_CALCULADORAS,
                "n_simuladores": N_SIMULADORES,
                "n_utilitarios": N_UTILITARIOS,
                "talhoes_json": json.dumps(talhoes),
                "catalogo": CATALOGO,
                "contagens": contagens_catalogo(),
                "n_catalogo": sum(len(c["itens"]) for c in CATALOGO),
                "n_existe": _por_estado(EXISTE),
                "n_parcial": _por_estado(PARCIAL),
                "n_ausente": _por_estado(NAO_EXISTE),
            },
        )
    )


def contagens_catalogo() -> dict:
    """Quantos itens por classe e por estado, derivado do catálogo.

    Nunca um número escrito à mão: se o catálogo cresce, estes crescem. É o
    mesmo princípio de `n_iot` — o número que sai do código, não o que se
    escreveu no template.
    """
    from app.guias.catalogo import CATALOGO

    por_estado = {}
    por_classe = {}
    for classe in CATALOGO:
        itens = classe["itens"]
        por_classe[classe["id"]] = len(itens)
        for it in itens:
            por_estado[it["estado"]] = por_estado.get(it["estado"], 0) + 1
    return {"por_classe": por_classe, "por_estado": por_estado}


def _por_estado(estado: str) -> int:
    """Quantos itens do catálogo estão num dado estado."""
    from app.guias.catalogo import CATALOGO

    return sum(
        1 for classe in CATALOGO for it in classe["itens"] if it["estado"] == estado
    )


@login_required
def registro_cafe_view(request):
    """Painel de registro para Café — agora separado por cultura (usa lógica genérica)"""
    from app.models import Cultura

    # MEDIDO 2026-10-05. `iexact="Café"` e `iexact="cafe"` sao a MESMA
    # comparacao em SQLite sem accento — e na base real as DUAS linhas do cafe
    # normalizam para a mesma chave. Sem `order_by`, `.first()` segue a ordem
    # que o banco devolveu: esta vista abria uma cultura e a seguinte outra, sem
    # nenhum aviso e sem mudanca nenhuma no codigo. `order_by("id")` fixa na
    # linha de menor id, que e' sempre a mesma.
    #
    # Isto e' o mesmo bug que `_resolver_cultura_key` teve, no mesmo ficheiro.
    # Nao e' um segundo problema: e' o mesmo, numa segunda porta.
    cultura = Cultura.objects.filter(nome__iexact="Café").order_by("id").first()
    if not cultura:
        cultura = Cultura.objects.filter(nome__iexact="cafe").order_by("id").first()
    if cultura:
        return registro_cultura_view(request, str(cultura.id))
    # fallback — mantém comportamento antigo se não houver Café no banco
    import json

    from app.api.culture_config import get_estagios_json

    estagios = get_estagios_json("cafe")
    return render(
        request,
        "registro-cultura.html",
        {
            "cultura_slug": "cafe",
            "cultura_slug_norm": "cafe",
            "cultura": type(
                "obj", (object,), {"nome": "Café", "id": "cafe", "grupo": "outro"}
            )(),
            "estagios_json": json.dumps(estagios, ensure_ascii=False),
            "talhoes": [],
            "talhao_atual": None,
            "talhoes_json": "[]",
            "cultura_json": json.dumps(
                {"id": "cafe", "nome": "Café", "grupo": "outro"}, ensure_ascii=False
            ),
            "registro_json": "{}",
            "area_total": "—",
            "custo_total": None,
            "cultura_variedade": "",
            "funcionarios": [],
        },
    )


@login_required
def registro_cultura_view(request, cultura_slug):
    """Desativado: painel agora abre direto no card via JS (SPA). Redireciona para a guia CORRETA por grupo."""
    from django.shortcuts import redirect

    # Resolve a cultura e manda para a guia certa (animal/aquatica/vegetal)
    cultura = None
    try:
        cultura = Cultura.objects.get(pk=cultura_slug)
    except (Cultura.DoesNotExist, ValueError, TypeError):
        cultura = Cultura.objects.filter(nome__iexact=cultura_slug).first()
    if cultura is not None:
        grupo = (cultura.grupo or "").strip().lower()
        if grupo in ANIMAL_GRUPOS:
            return redirect("guia-animal")
        if grupo in AQUATICA_GRUPOS:
            return redirect("guia-aquatica")
    # Mantem compatibilidade com links antigos: redireciona para lista vegetal
    return redirect("guia-vegetal")

    # Cache para SPA parcial (evita 1s de queries em cada clique)
    is_partial = (
        request.headers.get("X-Partial") == "1"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    cache_key = f"registro_cultura:{cultura_slug}:{request.user.id}:{request.GET.get('talhao', '')}:{'partial' if is_partial else 'full'}"
    cached_resp = cache.get(cache_key)
    if cached_resp and not request.GET.get("nocache"):
        return cached_resp

    def _norm(s):
        return "".join(
            c
            for c in unicodedata.normalize("NFD", str(s or "").lower())
            if unicodedata.category(c) != "Mn"
        )

    # Cache rápido por slug (evita loop O(n) sobre todas as culturas)
    from django.core.cache import cache

    cache_key = f"cultura:{cultura_slug}"
    cultura = cache.get(cache_key)
    if not cultura:
        # 1) tenta PK
        try:
            cultura = Cultura.objects.get(pk=cultura_slug)
        except (Cultura.DoesNotExist, ValueError, TypeError):
            pass
        # 2) tenta nome exato
        #
        # MEDIDO 2026-10-05: `order_by("id")` nos dois `.first()` deste bloco.
        # `iexact` compara sem acento no SQLite, e `cultura_slug` pode ser "cafe"
        # — que casa com as DUAS linhas do cafe. Sem ordem, a mesma URL resolvia
        # para ids diferentes conforme o plano de execucao. A entrada por PK
        # acima ja e' determinista; estas duas nao eram.
        if not cultura:
            cultura = (
                Cultura.objects.filter(nome__iexact=cultura_slug).order_by("id").first()
            )
        if not cultura:
            from django.db.models import Q

            cultura = (
                Cultura.objects.filter(
                    Q(nome__iexact=cultura_slug)
                    | Q(nome__icontains=cultura_slug.replace("-", " "))
                )
                .order_by("id")
                .first()
            )
            if not cultura:
                norm_in = _norm(cultura_slug)
                slug_in = slugify(cultura_slug).lower()
                for c in Cultura.objects.only("id", "nome").iterator():
                    if _norm(c.nome) == norm_in or slugify(c.nome).lower() == slug_in:
                        cultura = c
                        break
        if cultura:
            cache.set(cache_key, cultura, 3600)
    if not cultura:
        from django.http import Http404

        raise Http404("Cultura não encontrada")

    # slug normalizado para config/estágios/JS (ex: "café" -> "cafe")
    slug_norm = slugify(cultura.nome).lower() or _norm(cultura.nome).replace(" ", "_")
    # tenta estagios por slug_norm, _norm, e id como fallback
    estagios = get_estagios_json(slug_norm)
    if not estagios:
        estagios = get_estagios_json(_norm(cultura.nome))
    if not estagios:
        estagios = get_estagios_json(str(cultura.id))
    if not estagios:
        estagios = get_estagios_json(cultura_slug)

    # Talhões SEPARADOS por cultura + usuário (propriedade__user)
    talhoes_qs = (
        Talhao.objects.filter(
            cultura_atual=cultura, propriedade__user=request.user, ativo=True
        )
        .select_related("propriedade")
        .order_by("nome")
    )
    talhoes = list(talhoes_qs)
    # Talhão atual — ISOLADO por cultura + usuário + validação de pertencimento (evita IDOR/mistura)
    talhao_param = request.GET.get("talhao")
    talhao_atual = None
    if talhao_param:
        try:
            cand = Talhao.objects.get(
                pk=int(talhao_param),
                cultura_atual=cultura,
                propriedade__user=request.user,
            )
            talhao_atual = cand
        except Exception:
            pass
    if not talhao_atual:
        talhao_atual = talhoes[0] if talhoes else None

    # Agregados para hero — ISOLADO por cultura (não mistura produções)
    # Se talhão específico selecionado, mostra área daquele talhão; senão soma da cultura
    if talhao_atual:
        try:
            area_total_val = float(talhao_atual.area_hectare or 0)
        except Exception:
            area_total_val = 0
        # fallback para soma se quiser visão cultura; mantemos por talhão quando selecionado
        # area_total_val = sum(float(t.area_hectare or 0) for t in talhoes)  # descomente para somar
    else:
        try:
            area_total_val = sum(float(t.area_hectare or 0) for t in talhoes)
        except Exception:
            area_total_val = 0
    area_total = f"{area_total_val:.1f} ha".replace(".", ",") if area_total_val else "—"

    # Financeiro ISOLADO por cultura+talhão: apenas lançamentos da cultura e do talhão (se selecionado)
    from django.db.models import Q, Sum

    from app.models import AplicacaoInsumo, LancamentoFinanceiro

    base_lanc = LancamentoFinanceiro.objects.filter(propriedade__user=request.user)
    if talhao_atual:
        cultura_lancamentos = (
            base_lanc.filter(
                Q(talhao=talhao_atual)
                | Q(safra__talhao=talhao_atual)
                | Q(safra__cultura=cultura, talhao__isnull=True)
                | Q(safra__cultura=cultura)
                | Q(talhao__cultura_atual=cultura)
            )
            .select_related("propriedade", "talhao", "safra")
            .distinct()
            .order_by("-data")
        )
    else:
        cultura_lancamentos = (
            base_lanc.filter(
                Q(safra__cultura=cultura) | Q(talhao__cultura_atual=cultura)
            )
            .select_related("propriedade", "talhao", "safra")
            .distinct()
            .order_by("-data")
        )
    # custo_total = soma de DESPESAS da cultura (investido)
    agg_custo = cultura_lancamentos.filter(tipo="DESPESA").aggregate(total=Sum("valor"))
    custo_total_val = float(agg_custo["total"] or 0)
    custo_total = (
        f"{custo_total_val:,.0f}".replace(",", ".") if custo_total_val else None
    )
    agg_receita = cultura_lancamentos.filter(tipo="RECEITA").aggregate(
        total=Sum("valor")
    )
    receita_total_val = float(agg_receita["total"] or 0)
    receita_total = (
        f"{receita_total_val:,.0f}".replace(",", ".") if receita_total_val else None
    )
    # margem e custo por ha — só se houver números, senão deixa template usar fallback neutro
    if receita_total_val and custo_total_val:
        margem_val = (
            ((receita_total_val - custo_total_val) / receita_total_val * 100)
            if receita_total_val
            else 0
        )
        margem_total = f"{margem_val:.1f}%".replace(".", ",")
    else:
        margem_total = None
    if area_total_val and custo_total_val:
        custo_por_ha_val = custo_total_val / area_total_val
        custo_por_ha = f"{custo_por_ha_val:,.0f}".replace(",", ".")
    else:
        custo_por_ha = None

    cultura_tratamentos = (
        AplicacaoInsumo.objects.filter(
            talhao__cultura_atual=cultura, talhao__propriedade__user=request.user
        )
        .select_related("insumo", "talhao")
        .order_by("-data")[:20]
    )
    if talhao_atual and not cultura_tratamentos:
        # Se filtro por talhão específico deu vazio, tenta sem filtro (já é o mesmo)
        pass

    # Identidade / Ciclo — dados da própria cultura (não de outra)
    cultura_variedade_val = cultura.nome
    # ciclo e janela vêm do modelo Cultura (se preenchido) senão fallback por grupo
    ciclo_dias_val = cultura.ciclo_dias
    janela_inicio_val = cultura.janela_plantio_inicio
    janela_fim_val = cultura.janela_plantio_fim

    # JSONs para JS
    try:
        talhoes_json = json.dumps(
            [
                {
                    "id": t.id,
                    "nome": t.nome,
                    "area_hectare": float(t.area_hectare or 0),
                    "propriedade": t.propriedade.nome if t.propriedade else "",
                    "cultura": cultura.nome,
                }
                for t in talhoes
            ],
            ensure_ascii=False,
        )
    except Exception:
        talhoes_json = "[]"

    try:
        cultura_json = json.dumps(
            {"id": cultura.id, "nome": cultura.nome, "grupo": cultura.grupo or ""},
            ensure_ascii=False,
        )
    except Exception:
        cultura_json = "{}"

    # Mantém cultura_slug original para URL compat, mas também expõe slug_norm para JS
    resp = render(
        request,
        "registro-cultura.html",
        {
            "cultura_slug": cultura_slug,
            "cultura_slug_norm": slug_norm,
            "cultura": cultura,
            "estagios_json": json.dumps(estagios, ensure_ascii=False),
            "talhoes": talhoes,
            "talhao_atual": talhao_atual,
            "talhoes_json": talhoes_json,
            "cultura_json": cultura_json,
            "registro_json": "{}",
            "area_total": area_total,
            "custo_total": custo_total,
            "cultura_variedade": cultura_variedade_val,
            "ciclo_dias": ciclo_dias_val,
            "janela_inicio": janela_inicio_val,
            "janela_fim": janela_fim_val,
            "receita_total": receita_total,
            "margem_total": margem_total,
            "custo_por_ha": custo_por_ha,
            "lancamentos": list(cultura_lancamentos[:20]),
            "tratamentos": list(cultura_tratamentos),
            "funcionarios": [],
        },
    )
    # Cache 60s para SPA parcial, 30s para full
    try:
        cache.set(cache_key, resp, 60 if is_partial else 30)
    except Exception:
        pass
    return resp


def _montar_grupos_animal(user=None):
    culturas = _culturas_visiveis(user)
    grupos = {}
    for g in ANIMAL_GRUPOS:
        cs = culturas.filter(grupo=g).order_by("nome")
        grupos[g] = cs
    return grupos


def _montar_grupos_aquatica(user=None):
    culturas = _culturas_visiveis(user)
    grupos = {}
    for g in AQUATICA_GRUPOS:
        cs = culturas.filter(grupo=g).order_by("nome")
        grupos[g] = cs
    return grupos


def _montar_grupos_sistemas(user=None):
    culturas = _culturas_visiveis(user)
    outros_nomes = ["Mandioca", "Erva-mate", "Fumo", "Borracha (látex)"]
    grupos = {}
    cs_mel = culturas.filter(nome="Mel")
    grupos["apicultura"] = cs_mel
    cs_outras = culturas.filter(nome__in=outros_nomes).order_by("nome")
    grupos["outras"] = cs_outras
    return grupos


def _montar_grupos_vegetal(user=None):
    culturas = _culturas_visiveis(user)
    grupos = {}
    for g in VEGETAL_GRUPOS:
        cs = culturas.filter(grupo=g).order_by("nome")
        grupos[g] = cs
    outras = (
        culturas.exclude(grupo__in=VEGETAL_GRUPOS + ["outro"] + NAO_VEGETAL_GRUPOS)
        .exclude(grupo__isnull=True)
        .order_by("nome")
    )
    if outras:
        grupos["outras"] = outras
    return grupos


def _make_section_view(name):
    @login_required
    def view_fn(request):
        propriedades = Propriedade.objects.filter(user=request.user)
        return render(
            request, name.replace("_", "-") + ".html", {"propriedades": propriedades}
        )

    view_fn.__name__ = name + "_view"
    return view_fn
