"""Superficie de acesso a /servidor/ — a divida que a IA-6 diagnosticou.

O PROBLEMA QUE ESTE TESTE EXISTE PARA APANHAR
===============================================

`app/tests_servidor.py::ServidorDesativadoTest` faz UM pedido:
`c.get("/servidor/")`. Passa VERDE. E a revogacao continua furada em
`/servidor/estoque/`, `/servidor/agenda/`, `/servidor/alertas/`,
`/servidor/kanban/` e `/api/servidor/config/`.

Isto e' o que o s6 chamou de "AGRAVANTE": um teste que verifica a
revogacao numa rota e passa, dando a impressao de que a revogacao esta
coberta. Nao esta. **A disciplina existe num sitio e nao se propaga.**

PORQUE QUE AS ROTAS SAO DESCOBERTAS E NAO ESCRITAS
====================================================

Se eu escrever

    for url in ["/servidor/", "/servidor/estoque/", ...]:

amanha alguem acrescenta `/servidor/relatorios/` e este teste continua
a passar sem cobrir a rota nova. **Um teste de superficie tem de seguir a
superficie.** Por isso le `app.urls` e filtra. Uma rota nova entra no
teste sem ninguem editar este ficheiro.

O QUE E' "ACESSO RECUSADO"
==========================

Nao vao exigir 403. O comportamento ja instituido no dashboard, escrito
no `servidor_dashboard_view`, e' responder **200 com a mensagem
"Servidor desativado" e encerrar a sessao** (o `logout()`).
Exigir 403 seria reescrever o contrato e o teste falharia por um motivo
errado.

Logo, acesso recusado e qualquer um de:
  * redirect (301/302)
  * sessao encerrada (`_auth_user_id` desapareceu do `session`)
  * corpo que diz "desativado"

E VAO VERIFICAR TAMBEM QUE A DENAO FICOU PRESENTE
==================================================

Um teste que so verifica a resposta HTTP passa se a view devolver uma
pagina de erro vazia. Aqui exige-se que o servidor nao leia dados
da fazenda. E' a razao de este buraco existir.

ESTE TESTE FALHA AGORA. DEIXEI-O A FALHAR.
===========================================

Nao ha `xfail`, nao ha `skip`, nao ha `pytest.mark.skipif`. Um teste
que documenta um buraco e passa nao documenta nada — e a propria
circunstancia que a IA-6 descreveu: "o teste passa VERDE com a brecha
aberta".

A suite fica vermelha de proposito. Se o repo exige suite verde para
integrar, entao a integracao tem de esperar pela correccao — que e' o
sentido.
"""

import inspect
import json
import re
import sys
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

from app.models import PerfilUsuario, Propriedade, Talhao


def rotas_de_servidor():
    """Todas as rotas cujo padrao comeca por 'servidor/' ou 'api/servidor/'.

    DESCOBERTA, NAO ESCRITA. Um URLPattern novo entra aqui sem ninguem
    tocar neste ficheiro.
    """

    def visit(resolver, prefixo=""):
        achadas = []
        for p in resolver.url_patterns:
            if isinstance(p, URLPattern):
                padrao = prefixo + str(p.pattern)
                if padrao.startswith("servidor/") or padrao.startswith("api/servidor/"):
                    achadas.append("/" + padrao)
            elif isinstance(p, URLResolver):
                achadas.extend(visit(p, prefixo + str(p.pattern)))
        return achadas

    return sorted(set(visit(get_resolver())))


def _mkuser(name):
    return User.objects.create_user(username=name, password="x1234567")


def _mkservidor_desativado(name, prop):
    u = _mkuser(name)
    PerfilUsuario.objects.update_or_create(
        user=u,
        defaults={
            "tipo_usuario": "servidor",
            "area_servidor": "CAMPO",
            "propriedade_vinculada": prop,
            "ativo_servidor": False,
        },
    )
    u.refresh_from_db()
    return u


class SuperficieRevogacaoTest(TestCase):
    """Toda a rota de /servidor/ tem de respeitar ativo_servidor=False."""

    def setUp(self):
        self.produtor = _mkuser("prod_superficie")
        self.prop = Propriedade.objects.create(
            user=self.produtor,
            nome="Faz Superficie",
            area_total=10,
            uf="MT",
            cidade="X",
        )
        self.srv = _mkservidor_desativado("srv_superficie", self.prop)

    def _pedir(self, url):
        c = Client()
        c.force_login(self.srv)
        r = c.get(url)
        return c, r

    @staticmethod
    def _recusado(c, r):
        """Acesso recusado? Devolve (bool, motivo)."""
        if r.status_code in (301, 302, 303, 307, 308):
            return True, "redirect para %s" % r.get("Location", "?")
        if "_auth_user_id" not in c.session:
            return True, "sessao encerrada"
        corpo = ""
        if hasattr(r, "content") and r.content:
            corpo = r.content.decode("utf-8", "replace").lower()
        if "desativado" in corpo:
            return True, "resposta diz 'Servidor desativado'"
        return False, "200 com a pagina servida"

    def test_toda_rota_de_servidor_respeita_a_revogacao(self):
        rotas = rotas_de_servidor()

        # A discoverca e' o ponto. Se nao houver rotas, o teste e' inútil.
        self.assertTrue(
            rotas,
            "Nenhuma rota de /servidor/ encontrada — a descoberta "
            "partiu. Um teste de superficie que nao ve superficie nao "
            "testa nada.",
        )

        furadas = []
        for url in rotas:
            with self.subTest(rota=url):
                c, r = self._pedir(url)
                recusado, motivo = self._recusado(c, r)
                if not recusado:
                    furadas.append("%s  ->  HTTP %d  %s" % (url, r.status_code, motivo))
                self.assertTrue(
                    recusado,
                    "ROTA VAZADA: %s respondeu HTTP %d e a sessao "
                    "continua viva. Um servidor com ativo_servidor=False "
                    "continua a ler a fazenda por aqui." % (url, r.status_code),
                )

        self.assertEqual(
            furadas,
            [],
            "Estas rotas NAO respeitam a revogacao de acesso:\n  "
            + "\n  ".join(furadas),
        )

    def test_a_descoberta_encontra_as_rotas_conhecidas(self):
        """Rede de seguranca: se a descoberta partir, o teste acima e' vazio.

        Sem isto, `test_toda_rota...` passava com `rotas == []` se o
        `get_resolver` falhasse em silencio.
        """
        rotas = set(rotas_de_servidor())
        for esperada in (
            "/servidor/",
            "/servidor/estoque/",
            "/servidor/agenda/",
            "/servidor/alertas/",
        ):
            self.assertIn(
                esperada,
                rotas,
                "A rota %s desapareceu da descoberta. Ou foi removida "
                "(bom), ou a descoberta partiu (e este ficheiro deixou de "
                "cobrir a superficie). NAO tires a rota do teste sem "
                "decidir o que a substitui." % esperada,
            )

    def test_o_dashboard_continua_a_ser_o_padrao_de_recusa(self):
        """O dashboard e' a referencia: e' ele que define o contrato.

        Se esta falhar, as outras devem ser julgadas por outra regra.
        """
        c, r = self._pedir("/servidor/")
        recusado, motivo = self._recusado(c, r)
        self.assertTrue(
            recusado,
            "O dashboard deixou de recusar servidor desativado (%s). "
            "Este ficheiro mede as outras rotas por THIS contrato; se "
            "ele mudou, o contrato mudou e as regras tem de ser "
            "reescritas — nao o teste." % motivo,
        )
        self.assertNotIn(
            "_auth_user_id",
            c.session,
            "O dashboard respondeu que recusa mas NAO encerrou a sessao. "
            "Recusar no ecra sem fechar a porta nao e' revogar acesso.",
        )


# ###########################################################################
# FASE A — INVENTARIO DE /api/
#
# A PERGUNTA: quantas rotas /api/ existem?
#
# `rotas_de_servidor()` (L68-86) percorre `url_patterns` recursivamente e
# filtra por "servidor/" | "api/servidor/". A travessia ja desce dentro do
# DRF router (o router e' um URLResolver, por isso os `^talhoes/(?P<pk>...)$`
# aparecem). O FILTRO e' a razao de o resto de /api/ ser invisivel: e' ele
# que nunca chega a perguntar pelas outras 400+.
#
# `rotas_de_api()` abaixo e' a MESMA travessia, sem o filtro. Nao substitui
# nenhuma das duas — mede outra coisa. Convive.
# ###########################################################################


def rotas_de_api():
    """TODAS as rotas cujo padrao comeca por 'api/'. Sem filtro de dominio."""

    def visit(resolver, prefixo=""):
        achadas = []
        for p in resolver.url_patterns:
            if isinstance(p, URLPattern):
                achadas.append("/" + prefixo + str(p.pattern))
            elif isinstance(p, URLResolver):
                achadas.extend(visit(p, prefixo + str(p.pattern)))
        return achadas

    return sorted(set(a for a in visit(get_resolver()) if a.startswith("/api/")))


# ###########################################################################
# FASE B — DETECCAO
#
# O QUE ESTA MEDICAO NAO E'
# ==========================
# Nao e' "servidor revogado recebe 403 em todas as /api/". Isso seria uma
# montanha de falsos positivos: a maioria das rotas /api/ sao de PRODUTOR, e
# um servidor (mesmo revogado) a receber 200 numa rota de produtor nao e' um
# furo de REVOGACAO — e' uma questao de AUTORIZACAO (o servidor nunca devia
# estar ali).
#
# O QUE E'
# ========
# O produtor desliga o servidor -> `ativo_servidor = False` -> mas o servidor,
# com a sessao AINDA ABERTA, continua a ler dados de uma fazenda.
#
# Duas fazendas, dois marcadores, e por isso dois testes independentes:
#
#   MARCA_B — fazenda de UM OUTRO produtor. Um servidor ler isto e' leitura
#             atravessando a fronteira do tenancy. Esta e' a propriedade
#             pedida: e' o teste que FALHA se houver vazamento cross-tenant.
#
#   MARCA_A — a fazenda a que o servidor ESTA LIGADO. O produtor desligou-o e
#             ele continua a ler. Nao e' Attributo de tenancy: e' a revogacao
#             propriamente dita, e a que o docstring de
#             `app/views/api.py::servidor_config_api` descreve.
#
# O controlo (mesma varredura com um servidor ACTIVO) separa as duas coisas.
# Sem ele, "200 com dado" nao diz nada: pode ser falta de revogacao ou pode
# ser que a rota nao filtra por fazenda nem para ninguem.
# ###########################################################################

MARCA_A = "FAZENDA-A-MARCADOR-VINCULAR-2B8D41"
MARCA_B = "FAZENDA-B-MARCADOR-NAO-VINCULAR-9F3A7C"

#: Marcador dos modelos GLOBAIS semeados so para desbloquear a cadeia de FKs.
#: Nao contem MARCA_A nem MARCA_B — e' isso que impede que um catalogo
#: shared vire um falso vazamento.
NEUTRO = "CATALOGO-NEUTRO-%s"

#: Teto de pks de prop B tentados por rota de detalhe. Documentado no
#: relatorio: se este numero baixar, o numero de rotas exercitadas tambem.
PKS_POR_ROTA = 2

# --------------------------------------------------------------------------
# Padroes -> URLs concretas
# --------------------------------------------------------------------------
# O padrao de uma rota do DRF router NAO e' um `path()` do Django: e' um
# `re_path()` com regex, escrito `^talhoes/(?P<pk>[^/.]+)/$`. O cliente de
# test do Django quer um URL de verdade, nao uma regex. Duas sintaxes de
# parametro, uma so saida.

RE_GRUPO_DRF = re.compile(r"\(\?P<(\w+)>[^)]*\)")  # (?P<pk>[^/.]+)
RE_CONVERTER = re.compile(r"<(?:(\w+):)?(\w+)>")  # <int:pk>


def _params_do_padrao(padrao):
    """Nomes de parametro de URL, excluindo o de formato."""
    drf = [m for m in RE_GRUPO_DRF.findall(padrao) if m != "format"]
    conv = [m[1] for m in RE_CONVERTER.findall(padrao) if m[1] != "format"]
    return drf + conv


def _so_via_formato(padrao):
    """A rota so resolve com sufixo de formato (.json/.csv)?"""
    return "(?P<format>" in padrao or "<drf_format_suffix:format>" in padrao


def _corpo_do_padrao(padrao):
    """Tira as ancoras de regex e deixa um path navegavel.

    O `^` do DRF NAO esta no principio: o padrao ja leva o prefixo do
    include, por isso o que o `str()` devolve e' `/api/^talhoes/(?P<pk>...)$`.
    So `^` no inicio nao apanha nada e o URL ficava `/api/^talhoes/1/` — que
    da 404 e nao mede nada.
    """
    c = padrao.replace("^", "")
    if c.endswith("$"):
        c = c[:-1]
    return c


def _montar_url(corpo, pk, por_nome):
    c = RE_GRUPO_DRF.sub(lambda m: str(por_nome.get(m.group(1), pk)), corpo)
    c = RE_CONVERTER.sub(lambda m: str(por_nome.get(m.group(2), pk)), c)
    return c.replace("\\.", ".")


def _pk_do_segmento(segmento, pk_por_nome):
    """pk de prop B do modelo que o segmento da rota nomeia.

    `/api/^talhoes/(?P<pk>...)/$` -> o pk de um Talhao de prop B. Sem isto, a
    rota de detalhe leva um pk de outro modelo e responde 404 — e um 404 nao
    diz nada sobre revogacao. E' a diferenca entre "a rota foi exercitada" e
    "a rota foi exercitada a serio".
    """
    seg = segmento.strip("^$").lower()
    for chave in (seg, seg.rstrip("s"), seg + "s", seg.replace("-", "")):
        if chave in pk_por_nome:
            return pk_por_nome[chave]
    return None


def _handler(callback):
    """(modulo.qualname, linha) do handler real — para o relatorio apontar.

    O `callback` que o Django guarda para uma view do DRF e' o
    `csrf_exempt(...)` do `as_view()`, cujo `__qualname__` e'
    `View.as_view.<locals>.view` e cuja linha e' a do `dispatch` do DRF — ou
    seja, nao aponta para nada. Desembrulha-se o `.cls` e, no caso das
    `@api_view`, o `.func` que o DRF esconde dentro da classe.
    """
    alvo = callback
    cls = getattr(callback, "cls", None)
    if cls is not None:
        verbos = (
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "list",
            "retrieve",
            "create",
            "update",
            "partial_update",
            "destroy",
        )
        for verb in verbos:
            # So os metodos PROPRIOS da classe. `cls.__dict__` e' o que separa
            # o `list` de um ViewSet do `options` herdado de APIView — que nao
            # pertence a este handler.
            metodo = cls.__dict__.get(verb)
            if metodo is None:
                continue
            if isinstance(metodo, (staticmethod, classmethod)):
                metodo = metodo.__func__
            # `@api_view` nao guarda a funcao num atributo: poe um `handler`
            # dentro da classe, fechado sobre `func`. A funcao de dentro do
            # fecho e' a que se quer; o `handler` tem `<locals>` no qualname.
            for cell in getattr(metodo, "__closure__", None) or ():
                cand = cell.cell_contents
                if callable(cand) and "<locals>" not in getattr(
                    cand, "__qualname__", ""
                ):
                    alvo = cand
                    break
            else:
                alvo = metodo
            break
        else:
            alvo = cls

    mod = getattr(alvo, "__module__", "?") or "?"
    nome = getattr(alvo, "__qualname__", None) or getattr(alvo, "__name__", repr(alvo))
    linha = 0
    try:
        linha = inspect.getsourcelines(alvo)[1]
    except (OSError, TypeError):
        pass
    return "%s.%s" % (mod, nome), linha


# --------------------------------------------------------------------------
# Semente: so modelos que realmente pertencem a uma fazenda
# --------------------------------------------------------------------------
# Isolar o sinal e' o trabalho mais importante desta medicao. Se o marcador
# fosse semeado num modelo GLOBAL (Cultura e' um catalogo sem propriedade;
# ZARC, RelatorioTemplate, ErroReport sao do utilizador, nao da fazenda),
# QUALQUER rota que liste esse modelo acusaria um vazamento que nao existe.
# Por isso a semeia so aceita modelos com um caminho de FK ate `Propriedade`,
# e `Propriedade` e' o unico marcador de fronteira que o repo garante.


def _caminho_ate_propriedade(model, vistos=None):
    """Lookups de FK que levam de `model` ate `Propriedade`. None = global."""
    vistos = vistos or set()
    if model in vistos:
        return None
    vistos = vistos | {model}
    for f in model._meta.get_fields():
        if not getattr(f, "concrete", False) or not f.is_relation:
            continue
        if f.related_model is Propriedade:
            return f.name
        if f.related_model is None or f.related_model is User:
            continue
        sub = _caminho_ate_propriedade(f.related_model, vistos)
        if sub:
            return "%s__%s" % (f.name, sub)
    return None


# Ordem = dependencias. Um modelo cujo pai nao foi semeado e' registado como
# nao-semeado, nunca silenciosamente ignorado.
MODELOS_SEMEAR = (
    # nivel 0 — sem pai (FK directa a Propriedade)
    "Safra",
    "Funcionario",
    "Maquinario",
    "Insumo",
    "EstoqueItem",
    "Animal",
    "AnimalIndividual",
    "Racao",
    "LoteAquatico",
    "ApiarioColmeia",
    "ContaBancaria",
    "LancamentoFinanceiro",
    "CentroCusto",
    "Inventario",
    "OrdemCompra",
    "Piquete",
    "EstacaoMeteo",
    "Gateway",
    "PetExotico",
    "Experimento",
    "Parcelamento",
    "ProtocoloSanitario",
    "RastroItem",
    "RegraAlertaTelemetria",
    "FonteDadosExterna",
    # nivel 1 — pais do nivel 0
    "Device",
    "InventarioItem",
    "AnaliseSolo",
    "MonitoramentoPraga",
    "TalhaoGeometria",
    "Pesagem",
    "ProducaoAnimal",
    "ProducaoApiario",
    "Despesca",
    "LeituraSensor",
    "TelemetryData",
    "AlertaTelemetria",
    "ManutencaoMaquinario",
    "ConciliacaoBancaria",
    "LancamentoDetalhado",
    "AplicacaoInsumo",
    "MovimentoEstoque",
    # nivel 2
    "CustoProducao",
    "PlanoSafra",
    "AtividadePlanejada",
    "PrescricaoVRA",
    "RastreabilidadeSafra",
    "ReceituarioAgronomico",
    "MedicaoExperimental",
)

_CAMPOS_TEXTO = {
    "nome",
    "titulo",
    "descricao",
    "observacoes",
    "label",
    "slug",
    "codigo",
    "identificador",
    "tipo",
    "categoria",
    "status",
    "unidade",
    "classe",
    "especie",
    "raca",
    "sexo",
    "name",
    "tipo_registro",
    "motivo",
    "mensagem",
    "assunto",
    "texto",
    "descricao_curta",
    "titulo_social",
}


def _resolver_pai(model, f, prop, produtor, cache, log):
    """Valor para uma FK/M2M. None = nao ha valor (ou nao e obrigatoria)."""
    alvo = f.related_model
    if alvo is Propriedade:
        return prop
    if alvo is User:
        return produtor
    if f.null:
        return None
    if cache.get(alvo) is not None:
        return cache[alvo]
    if _caminho_ate_propriedade(alvo) is None and _semear(
        alvo, None, None, NEUTRO % model.__name__, cache, log
    ):
        # O pai e' um CATALOGO (Cultura, p.ex.): nao tem propriedade, por isso
        # nao pode levar marcador — levar tornaria qualquer rota que o liste
        # num falso vazamento. Semeia-se neutro so para desbloquear a cadeia
        # (Safra -> CustoProducao -> PrescricaoVRA -> ...).
        return cache[alvo]
    log.append(
        "%s.%s: pai %s por semear"
        % (model.__name__, f.name, getattr(alvo, "__name__", "?"))
    )
    return _FALTA


_FALTA = object()


def _semear(model, prop, produtor, marcador, cache, log):
    """Cria uma linha de `model` que pertence a `prop`, com `marcador` no nome.

    As M2M nao se atribuem no `create()` — `Safra.talhoes` e' ManyToManyField e
    `objects.create(talhoes=talhao)` levanta TypeError. Vao depois, com
    `.set()`, que e' o que o erro manda usar.
    """
    if model in cache:
        return cache[model]
    obj = None
    m2m = {}
    try:
        kwargs = {}
        for f in model._meta.get_fields():
            if not getattr(f, "concrete", False) or f.primary_key:
                continue
            if f.many_to_many:
                valor = _resolver_pai(model, f, prop, produtor, cache, log)
                if valor is _FALTA:
                    cache[model] = None
                    return None
                if valor is not None:
                    m2m[f.name] = valor
                continue
            if f.is_relation:
                valor = _resolver_pai(model, f, prop, produtor, cache, log)
                if valor is _FALTA:
                    cache[model] = None
                    return None
                if valor is not None:
                    kwargs[f.name] = valor
                continue
            if f.has_default() or f.null:
                continue
            t = f.get_internal_type()
            if t in ("CharField", "TextField"):
                if f.choices:
                    kwargs[f.name] = f.choices[0][0]
                else:
                    kwargs[f.name] = marcador
            elif t in (
                "IntegerField",
                "BigIntegerField",
                "PositiveIntegerField",
                "PositiveSmallIntegerField",
                "SmallIntegerField",
                "FloatField",
            ):
                kwargs[f.name] = 1
            elif t == "DecimalField":
                # Decimal, nao string: `DecimalField.validators` compara com
                # `Decimal` e `"1.00"` rebenta com TypeError.
                kwargs[f.name] = Decimal("1.00")
            elif t == "BooleanField":
                kwargs[f.name] = False
            elif t == "DateTimeField":
                kwargs[f.name] = timezone.now()
            elif t == "DateField":
                kwargs[f.name] = timezone.now().date()
            elif t == "JSONField":
                kwargs[f.name] = {}
        obj = model.objects.create(**kwargs)
        for nome, valor in m2m.items():
            getattr(obj, nome).set([valor])
    except Exception as exc:  # noqa: BLE001 — a semeia e' best-effort e registada
        log.append("%s: %s: %s" % (model.__name__, type(exc).__name__, str(exc)[:90]))
        obj = None
    cache[model] = obj
    return obj


class _Medicao:
    """Resultado da varredura. Nao e' cache entre sessoes: vive numa classe."""

    def __init__(self):
        self.exercitadas = []  # (url, padrao, handler, linha, sem_parametro)
        self.nao_testaveis = []  # (padrao, motivo)
        self.status = {}  # status_code -> n
        self.com_B = []  # (url, padrao, handler, linha)
        self.com_A = []  # (url, padrao, handler, linha)
        self.controle_B = 0  # URLs onde o DONO de B le o proprio dado
        self.controle_B_rotas = []
        self.semeados = []
        self.semente_falhas = []
        self.status_control = {}
        self.leu_ativo = []  # (url, revogado leu?, activo leu B?, activo leu A?)
        self.rotas_exercitadas = set()  # padroes que produziram >=1 URL
        self.sem_parametro_200 = 0  # URLs sem parametro que responderam 200


def _varrer(clientes, pool, por_nome, pk_por_nome):
    """Um GET por URL concreta. Devolve _Medicao. Nao flakear: ordem fixa."""
    revogado, ativo, dono_b = clientes
    m = _Medicao()

    for padrao in rotas_de_api():
        if _so_via_formato(padrao):
            m.nao_testaveis.append((padrao, "so via sufixo de formato (.json/.csv)"))
            continue
        params = _params_do_padrao(padrao)
        corpo = _corpo_do_padrao(padrao)
        sem_parametro = not params

        if sem_parametro:
            tentativas = [pool[0]]
        else:
            # 1o: o pk do modelo que o 1o segmento da rota nomeia (uma rota de
            # detalhe so diz alguma coisa com o pk do modelo certo). 2o: um pk
            # qualquer, para a rota nao ficar por exercitar.
            segmento = re.split(r"[/?]", corpo.lstrip("/"))[0]
            alvo = _pk_do_segmento(segmento, pk_por_nome)
            tentativas = [alvo if alvo is not None else pool[0]]
            if PKS_POR_ROTA > 1:
                tentativas.append(
                    pool[0] if alvo != pool[0] else pool[min(1, len(pool) - 1)]
                )

        for pk in tentativas[:PKS_POR_ROTA]:
            url = _montar_url(corpo, str(pk), por_nome)
            if "<" in url or "(?P" in url or not url.startswith("/"):
                m.nao_testaveis.append((padrao, "sem URL concreta"))
                break
            m.exercitadas.append((url, padrao, sem_parametro))

    handlers = {}
    for url, padrao, _sem_parametro in m.exercitadas:
        m.rotas_exercitadas.add(padrao)
        if padrao not in handlers:
            handlers[padrao] = _handler(_resolver_callback(padrao))
        handler, linha = handlers[padrao]

        r = revogado.get(url)
        cod = r.status_code
        m.status[cod] = m.status.get(cod, 0) + 1
        # NAO ha `continue` quando o codigo nao e' 200.
        #
        # Havia, e o teste pagou por isso. O `continue` estava DEPOIS deste
        # bloco, o que punha a deteccao de fuga E o anti-vacuity atras da
        # mesma porta: so se mediava o que o servidor REVOGADO tinha lido. Ao
        # tapar o furo (`ServidorRevogadoMiddleware` responde 403 em `/api/`),
        # o revogado deixou de ler, o `continue` disparava na primeira URL, e o
        # anti-vacuity mediava ZERO — a sonda ficava cega no mesmo instante em
        # que a correccao funcionava. Medido: 70/377 URLs antes, 0/377 depois.
        #
        # A leitura de markers e' o que decide se houve fuga, e um 403 nao traz
        # markers: `tem_b`/`tem_a` ficam falso e nada e' registado. O que tem de
        # correr sempre e' a pergunta "o dono de B le o proprio dado?", porque
        # e' a pergunta que distingue "nada vazou" de "nao havia nada para
        # vazar".
        if cod == 200 and _sem_parametro:
            m.sem_parametro_200 += 1

        corpo = r.content.decode("utf-8", "replace")
        tem_b = MARCA_B in corpo
        tem_a = MARCA_A in corpo
        if tem_b:
            m.com_B.append((url, padrao, handler, linha))
        if tem_a:
            m.com_A.append((url, padrao, handler, linha))

        # Controlo: o MESMO pedido com um servidor ACTIVO, so nas rotas onde
        # houve leitura. E' o que separa "falta a revogacao" de "a rota nao
        # filtra por fazenda nem para ninguem".
        if tem_b or tem_a:
            rc = ativo.get(url)
            m.status_control[rc.status_code] = (
                m.status_control.get(rc.status_code, 0) + 1
            )
            m.leu_ativo.append(
                (
                    url,
                    tem_a or tem_b,
                    MARCA_B in rc.content.decode("utf-8", "replace"),
                    MARCA_A in rc.content.decode("utf-8", "replace"),
                )
            )

        # Anti-vacuidade: o DONO de B tem de ler o proprio marcador em B. Se
        # nunca o le, "nenhum vazamento de B" nao prova nada — a sonda esta
        # vazia. E' o que impede um verde falso.
        if MARCA_B in dono_b.get(url).content.decode("utf-8", "replace"):
            m.controle_B += 1
            m.controle_B_rotas.append(url)

    return m


_CALLBACKS = {}


def _resolver_callback(padrao):
    """Handler do padrao — memorizado, a travessia e' cara."""
    if padrao in _CALLBACKS:
        return _CALLBACKS[padrao]
    alvo = padrao

    def visit(resolver, prefixo=""):
        for p in resolver.url_patterns:
            if isinstance(p, URLPattern):
                if "/" + prefixo + str(p.pattern) == alvo:
                    return p.callback
            elif isinstance(p, URLResolver):
                achado = visit(p, prefixo + str(p.pattern))
                if achado is not None:
                    return achado
        return None

    cb = visit(get_resolver())
    _CALLBACKS[padrao] = cb
    return cb


# Uma varredura por sessao de teste. Os dados de tras de cada URL sao os
# mesmos em todos os metodos desta classe (o `TestCase` faz rollback do setUp
# entre eles), por isso o resultado e' memorizado — senao a varredura corre
# duas vezes e a suite passa de 60s.
_MEDICAO = None


class SuperficieApiRevogacaoTest(TestCase):
    """Mede furos de revogacao na camada /api/. NAO corrige nada."""

    def setUp(self):
        self.prod_a = User.objects.create_user(
            username="prod_api_a", password="x1234567"
        )
        self.prod_b = User.objects.create_user(
            username="prod_api_b", password="x1234567"
        )
        self.prop_a = Propriedade.objects.create(
            user=self.prod_a, nome=MARCA_A, area_total=10, uf="MT", cidade="X"
        )
        self.prop_b = Propriedade.objects.create(
            user=self.prod_b, nome=MARCA_B, area_total=20, uf="MT", cidade="X"
        )
        self.talhao_a = Talhao.objects.create(
            propriedade=self.prop_a, nome=MARCA_A, area_hectare="5.00"
        )
        self.talhao_b = Talhao.objects.create(
            propriedade=self.prop_b, nome=MARCA_B, area_hectare="5.00"
        )

        # Dois servidores IGUAIS, so com o flag diferente. O `ativo` e' o
        # controlo: sem ele, "200 com dado" nao distingue revogacao de
        # autorizacao.
        self.srv_revogado = _mkuser("srv_api_revogado")
        PerfilUsuario.objects.update_or_create(
            user=self.srv_revogado,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "CAMPO",
                "propriedade_vinculada": self.prop_a,
                "ativo_servidor": False,
            },
        )
        self.srv_revogado.refresh_from_db()

        self.srv_ativo = _mkuser("srv_api_ativo")
        PerfilUsuario.objects.update_or_create(
            user=self.srv_ativo,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "CAMPO",
                "propriedade_vinculada": self.prop_a,
                "ativo_servidor": True,
            },
        )
        self.srv_ativo.refresh_from_db()

        # Semente das DUAS fazendas, so em modelos com caminho ate
        # Propriedade (ver `_caminho_ate_propriedade`).
        from app import models as app_models

        log = []
        # O Talhao ja existe (criado acima, com marcador). POE-lo no cache e'
        # o que deixa semear Safra/AnaliseSolo/MonitoramentoPraga/
        # TalhaoGeometria, que apontam para ele.
        cache_a = {Talhao: self.talhao_a}
        cache_b = {Talhao: self.talhao_b}
        for nome in MODELOS_SEMEAR:
            model = getattr(app_models, nome, None)
            if model is None:
                log.append("%s: nao existe em app.models" % nome)
                continue
            caminho = _caminho_ate_propriedade(model)
            if caminho is None:
                log.append(
                    "%s: modelo GLOBAL (sem caminho ate Propriedade) "
                    "- excluido da sonda" % nome
                )
                continue
            _semear(model, self.prop_a, self.prod_a, MARCA_A, cache_a, log)
            _semear(model, self.prop_b, self.prod_b, MARCA_B, cache_b, log)
            if cache_b.get(model) is not None:
                self._semeados = getattr(self, "_semeados", [])
                self._semeados.append((nome, caminho))
        self._semeados = getattr(self, "_semeados", [])
        self.semente_falhas = log

    # -- infra ------------------------------------------------------------
    def _medicao(self):
        global _MEDICAO
        if _MEDICAO is not None:
            return _MEDICAO

        from app import models as app_models

        # Pool de pks REAIS de prop B, em ordem estavel. Um pk de prop B e'
        # o que torna a rota de detalhe uma sonda de verdade:
        # GET /api/talhoes/<pk de B>/.
        pool = []
        pk_por_nome = {}
        for nome, caminho in self._semeados:
            model = getattr(app_models, nome)
            row = model.objects.filter(**{caminho: self.prop_b}).order_by("pk").first()
            if row is not None:
                pool.append(str(row.pk))
                pk_por_nome[nome.lower()] = str(row.pk)
        pool.append(str(self.talhao_b.pk))
        pool.append(str(self.prop_b.pk))
        pk_por_nome["talhao"] = str(self.talhao_b.pk)
        pk_por_nome["propriedade"] = str(self.prop_b.pk)
        pool = list(dict.fromkeys(pool)) or ["1"]

        # `pk` NAO e' fixado aqui de proposito: quem decide o pk de uma rota de
        # detalhe e' `_pk_do_segmento`, para que `/api/talhoes/<pk>/` leve o pk
        # de um Talhao de prop B e nao o de outro modelo qualquer.
        por_nome = {"talhao_id": self.talhao_b.pk}

        def cliente(user):
            c = Client(raise_request_exception=False)
            c.force_login(user)
            return c

        _MEDICAO = _varrer(
            (cliente(self.srv_revogado), cliente(self.srv_ativo), cliente(self.prod_b)),
            pool,
            por_nome,
            pk_por_nome,
        )
        _MEDICAO.semeados = self._semeados
        _MEDICAO.semente_falhas = self.semente_falhas
        return _MEDICAO

    def _imprime(self, titulo, linhas):
        sys.stdout.write("\n" + "=" * 78 + "\n%s\n" % titulo + "=" * 78 + "\n")
        for linha in linhas:
            sys.stdout.write(linha + "\n")
        sys.stdout.flush()

    # -- FASE A -----------------------------------------------------------
    def test_a_descoberta_de_api_encontra_a_superficie(self):
        rotas = rotas_de_api()

        self._imprime(
            "INVENTARIO DE /api/ — %d rotas" % len(rotas),
            ["   %s" % r for r in rotas],
        )

        self.assertTrue(
            rotas,
            "Nenhuma rota /api/ encontrada. A descoberta partiu — e um "
            "teste de superficie que nao ve superficie nao mede nada.",
        )
        # Rede de seguranca contra a descoberta estar a ver de menos: se
        # `rotas_de_api()` so devolvesse o que `rotas_de_servidor()` ja
        # devolve, a FASE B seria um teste de /servidor/ com outro nome.
        de_servidor = set(rotas_de_servidor())
        extra = [r for r in rotas if r not in de_servidor]
        self.assertGreater(
            len(extra),
            50,
            "A descoberta de /api/ devolveu so %d rotas novas em relacao a "
            "/servidor/. Suspeita de que o filtro de dominio regressou." % len(extra),
        )
        for esperada in ("/api/servidor/config/", "/api/talhoes-por-propriedade/"):
            self.assertIn(esperada, rotas)

    def test_o_censo_das_rotas_nao_testaveis(self):
        """O buraco da cobertura e' tao importante como os furos."""
        m = self._medicao()
        self._imprime(
            "RESUMO - %d rotas /api/ | %d exercitadas | %d NAO testaveis | "
            "%d URLs sem parametro, das quais %d devolveram 200"
            % (
                len(rotas_de_api()),
                len(m.rotas_exercitadas),
                len(m.nao_testaveis),
                len([u for u in m.exercitadas if u[2]]),
                m.sem_parametro_200,
            ),
            [],
        )
        self._imprime(
            "ROTAS /api/ NAO TESTAVEIS - %d de %d"
            % (len(m.nao_testaveis), len(rotas_de_api())),
            ["   %-58s %s" % (p[:58], mot) for p, mot in m.nao_testaveis],
        )
        self._imprime(
            "DISTRIBUICAO DE STATUS (servidor revogado) - %d URLs exercitadas"
            % len(m.exercitadas),
            [
                "   HTTP %s -> %d" % (k, v)
                for k, v in sorted(m.status.items(), key=lambda kv: -kv[1])
            ],
        )
        self.assertEqual(
            len(m.rotas_exercitadas) + len(m.nao_testaveis),
            len(rotas_de_api()),
            "A contagem nao bate: %d rotas exercitadas + %d nao testaveis != "
            "%d rotas /api/. Ou uma rota foi contada duas vezes, ou uma "
            "rota nenhuma das vezes."
            % (len(m.rotas_exercitadas), len(m.nao_testaveis), len(rotas_de_api())),
        )

    # -- FASE B -----------------------------------------------------------
    def test_a_sonda_nao_esta_vazia(self):
        """Anti-falso-verde: se o dono de B nao le B, 'nenhum furo' e' mentira."""
        m = self._medicao()
        self.assertTrue(
            self._semeados,
            "Nenhum modelo semeado. A sonda nao tem dado nenhum para procurar.",
        )
        self._imprime(
            "MODELOS SEMEADOS (prop A e prop B) - %d" % len(self._semeados),
            ["   %-26s via %s" % (n, c) for n, c in self._semeados],
        )
        self._imprime(
            "SEMENTE NAO APLICADA - %d" % len(self.semente_falhas),
            ["   %s" % l for l in self.semente_falhas],
        )
        self._imprime(
            "ANTI-VACUIDADE - o DONO de prop B le o proprio marcador em %d de "
            "%d URLs exercitadas" % (m.controle_B, len(m.exercitadas)),
            ["   %s" % u for u in m.controle_B_rotas],
        )
        self.assertGreater(
            m.controle_B,
            0,
            "O DONO da fazenda B leu o proprio marcador em ZERO URLs. A sonda "
            "esta vazia: um 'nenhum vazamento de B' VERDE aqui seria um falso "
            "verde. Nao ha semente visivel para a camada /api/ ler.",
        )

    def test_um_servidor_revogado_nao_le_dados_de_outra_fazenda(self):
        """A propriedade pedida: revogado + sessao viva => 0 bytes de prop B."""
        m = self._medicao()
        self._imprime(
            "LEITURA DE PROPRIEDADE ALHEIA (prop B) — %d em %d URLs, com o "
            "servidor REVOGADO" % (len(m.com_B), len(m.exercitadas)),
            [
                "   %-52s %-52s %s:%d" % (u[:52], p[:52], h, ln)
                for u, p, h, ln in m.com_B
            ]
            or ["   nenhuma"],
        )
        self.assertEqual(
            m.com_B,
            [],
            "FURO DE REVOGACAO CONFIRMADO — %d rota(s) /api/ devolveram "
            "HTTP 200 com dados da fazenda de outro produtor a um servidor "
            "com ativo_servidor=False e sessao aberta:\n  %s"
            % (
                len(m.com_B),
                "\n  ".join(
                    "%s  ->  %s  (linha %d)" % (u, hh, ll) for u, _, hh, ll in m.com_B
                ),
            ),
        )

    def test_um_servidor_revogado_nao_continua_a_ler_a_fazenda_vinculada(self):
        """A revogacao propriamente dita: desligado e' nao ler mais nada."""
        m = self._medicao()
        self._imprime(
            "LEITURA DA FAZENDA VINCULADA (prop A) — %d em %d URLs, com o "
            "servidor REVOGADO" % (len(m.com_A), len(m.exercitadas)),
            [
                "   %-52s %-52s %s:%d" % (u[:52], p[:52], h, ln)
                for u, p, h, ln in m.com_A
            ]
            or ["   nenhuma"],
        )
        self._imprime(
            "CONTROLE — mesmo pedido com um servidor ACTIVO nas rotas acima "
            "(o que distingue revogacao de autorizacao)",
            [
                "   HTTP %s -> %d" % (k, v)
                for k, v in sorted(m.status_control.items(), key=lambda kv: -kv[1])
            ],
        )
        self.assertEqual(
            m.com_A,
            [],
            "REVOGACAO NAO SE PROPAGOU A /api/ — %d rota(s) devolveram HTTP "
            "200 com dados da fazenda a que o servidor esta ligado, com "
            "ativo_servidor=False e sessao viva. A camada /api/ nao le "
            "PerfilUsuario.ativo_servidor em lado nenhum (grep confirmado em "
            "app/api/*.py e app/api/views/*.py): IsAuthenticated prova que ha "
            "sessao, nao que a sessao ainda e' valida.\n  %s"
            % (
                len(m.com_A),
                "\n  ".join(
                    "%s  ->  %s  (linha %d)" % (u, hh, ll) for u, _, hh, ll in m.com_A
                ),
            ),
        )


# ###########################################################################
# FASE C — A ESCRITA
#
# A FASE B mediu LEITURA. Esta fase mede ESCRITA, e a pergunta e' outra:
#
#   O produtor desliga o servidor -> `ativo_servidor = False` -> mas o servidor,
#   com a sessao AINDA ABERTA, consegue ESCREVER nos dados da fazenda?
#
# PORQUE QUE ISTO NAO E' A MESMA PERGUNTA
# =======================================
#
# Ler e' reversivel. Um POST que grava e' um facto: o registo existe, a coluna
# mudou, e o produtor que desligou o servidor ve-o na aplicacao sem saber que
# foi la. Por isso aqui nao basta o codigo de estado — `um 400 NAO e' furo`
# (a validacao recusou e nada foi escrito) e `um 405 e' metodo errado`.
# **O QUE SE CONTA E' O RASTO.** Cada POST e' feito dentro de um savepoint que
# e' revertido a seguir, e o que se mede e':
#
#   1. o codigo de estado;
#   2. o SQL de escrita efectivamente emitido (`CaptureQueriesContext`), sem a
#      `django_session`, que o login suja em qualquer pedido;
#   3. o DIFF DE LINHAS no banco: contagem de todos os modelos de `app.models`
#      antes e depois, mais os campos mutaveis das tabelas que estas rotas
#      prometem mexer.
#
# (3) e' o que separa `200 que nao escreveu` de `200 que escreveu`. Uma rota
# que responde 200 e devolve `[]` nao escreveu nada; uma que responde 200 e
# devolve `{"ok": true}` pode ter gravado uma linha. So o diff diz.
#
# A CLASSIFICACAO ANTES DE CONTAR
# ===============================
#
# Nem toda a rota POST e' um endpoint de utilizador, e contar todas como se
# fossem seria dishonesto nas duas direcoes:
#
#   (a) ENDPOINT DE UTILIZADOR — cria/guarda dados. Tem de respeitar a revogacao.
#   (b) MAQUINA / INGESTAO — `/api/iot/mqtt/webhook/`, `/api/iot/push/`,
#       `/api/iot/dinamico/evento/`. Nao tem sessao de utilizador: autenticam por
#       `X-API-Key` de `Gateway` ou por token revogavel no header. Um servidor
#       revogado NAO LHES DIREITA — mas sao reportadas à parte, e nao contadas
#       como "a revogacao funciona aqui".
#   (c) ACAO QUE GERA DERIVADOS — `/api/relatorio/gerar/`, `/api/amplia/exec/`,
#       `/api/ia/executar/`, `*/recalcular/`. Aqui o efeito pode ser LER e
#       GRAVAR ao mesmo tempo, por isso mede-se como escrita.
#
# `CLASSIFICACAO` abaixo e' a leitura de `app/urls.py`, `app/api/urls.py`,
# `app/iot/urls.py`, `app/ia/urls.py` e `app/amplia_mcp/urls.py`, e a razao de
# cada uma esta escrita ao lado. `POSTS_SO_POST` amarra o padrao ao payload
# MINIMO e ESPECIFICO: um 400 por falta de campo nao prova furo nem prova
# seguranca, e cada payload foi lido da view/serializer antes de ser escrito.
# ###########################################################################

#: (classe, razao) por fragmento do padrao. A chave e' o padrao EXATO que
#: `rotas_de_api()` devolve, para nao casar porsubstring e errar a rota.
CLASSIFICACAO = {
    # ---------------------------------------------------------------- (a)
    # CADERNO DE CAMPO. MEDIDO 2026-10-04 (agente 4).
    #
    # Estas tres rotas nasceram DEPOIS deste teste, e o teste fez o que deve:
    # falhou com `?` — "rota so-POST sem classificacao". Uma rota nao
    # classificada nao e' contada nem como furo nem como cobertura, ou seja,
    # nao conta. Nao e' um falso positivo: e' o mecanismo a dizer que ha
    # uma porta nova que ninguem olhou.
    #
    # A CLASSIFICACAO e' (a) — endpoint de utilizador que cria dados — e o
    # que a obriga a respeitar a revogacao. `app/api/views/caderno.py` gained
    # essa verificacao em `exigir_sessao_json` no mesmo dia, precisamente por
    # causa desta falha: se a classificacao tivesse sido (c), ninguem notaria.
    "/api/caderno/notas/": (
        "a",
        "Nota de campo. Cria `NotaCampo` do utilizador autenticado. O "
        "decorator `exigir_sessao_json` chama `servidor_ativo()` e devolve "
        "403 a um servidor revogado (app/api/views/caderno.py).",
    ),
    "/api/caderno/fotos/": (
        "a",
        "Fotografia de nota de campo. Mesmo decorator, mesma revogacao.",
    ),
    "/api/caderno/voice/": (
        "a",
        "Audio ditado na ronda. Mesmo decorator, mesma revogacao.",
    ),
    # ---------------------------------------------------------------- (b)
    # MAQUINA / INGESTAO. Nao tem sessao de utilizador: autenticam por
    # `X-API-Key` de um `Gateway` ou por token revogavel no header. Um
    # servidor revogado NAO LHES DIREITA — nao porque a revogacao as fecha,
    # mas porque nunca houve sessao para fechar.
    "/api/iot/mqtt/webhook/": (
        "b",
        "Webhook TTN/ChirpStack. `csrf_exempt`; a autenticacao e' por "
        "config/token de aplicacao, NAO por sessao (app/iot/views.py:257).",
    ),
    "/api/iot/push/": (
        "b",
        "Push de telemetria. Exige `X-API-Key` de um `Gateway` "
        "(app/iot/views.py:106). Sem esse header devolve 401.",
    ),
    "/api/iot/push/<str:device_eui>/": (
        "b",
        "Idem, com o device no path. Mesma autenticacao por `Gateway.api_key`.",
    ),
    # ---------------------------------------------------------------------
    # MEDIDO 2026-10-06. Esta rota apareceu depois deste teste e o teste fez
    # o que deve: falhou com `?` - "rota so-POST sem classificacao".
    #
    # Antes de classificar, verifiquei o codigo - porque `?` nao e' convite
    # a escolher uma letra, e' convite a abrir a porta e escolher a letra
    # que parecer certa. `comando_ack` chama `_resolve_auth(request)` e
    # devolve 401 sem `X-API-Key`: e' (b), a mesma categoria do `push`.
    #
    # O motivo de o ACK estar aqui e' o mesmo do `push`: uma credencial que
    # empurra telemetria pode confirmar um comando. Dar-lhe menos credenciais
    # do que a telemetria seria tornar a coisa mais perigosa mais facil.
    "/api/iot/comando/ack/": (
        "b",
        "ACK de comando executado pelo gateway. `csrf_exempt`; "
        "`_resolve_auth` + 401 sem `X-API-Key` (app/iot/views.py:267). "
        "Ancorado na propriedade do `Gateway`: um ACK de outra "
        "propriedade e' 403.",
    ),
    "/api/iot/dinamico/evento/": (
        "b",
        "Receptor do ESP32. `csrf_exempt` + `Authorization: Bearer <token>` "
        "revogavel (app/views/iot_dinamico.py:33). O device nao tem sessao.",
    ),
    # ---------------------------------------------------------------- (c)
    # ACAO QUE GERA DERIVADOS. O efeito pode ser LER e GRAVAR ao mesmo tempo,
    # por isso mede-se como escrita. As quatro ultimas sa' POST mas SO LEEM:
    # aparecem aqui para o rasto as medir e nao as termos por decoradas.
    "/api/^custo-producao/recalcular/$": (
        "c",
        "Recalcula `CustoProducao`: `get_or_create` + `save()` por safra "
        "(app/api/views/custos.py:48). Le a safra e escreve o custo.",
    ),
    "/api/^custos-producao/recalcular/$": (
        "c",
        "Alias registado do anterior (mesmo viewset, `basename` diferente).",
    ),
    # --- CADERNO DE CAMPO (app/api/views/caderno.py) ---
    #
    # MEDIDO 2026-10-04, e nao por suposicao: li os tres handlers e vi o que
    # cada um faz. `nota_create` grava; as outras duas respondem 501 e nao
    # escrevem nada. A distincao e' o que separa "rota de escrita" de "rota
    # que parece de escrita", e e' exactamente o que este inventario mede.
    # A chave e' o PATH LITERAL, nao um regex: `rotas_so_post()` devolve o
    # padrao tal como `rotas_de_api()` o viu. Foi por causa disto que uma
    # primeira versao destas tres entradas usou `/api/^caderno/notas/$` e nunca
    # casou — o inventarioContinuou a dizer "NAO CLASSIFICADA" com a entrada
    # a dois caracteres de estar certa.
    "/api/caderno/notas/": (
        "a",
        "`NotaCampo.objects.create` (app/api/views/caderno.py:311). E' a nota de "
        "campo do produtor: conteudo, data e proveniencia. O que o produtor "
        "afirma entra como `declarado`, nunca `medido`, e o cliente nao "
        "escolhe o estado.",
    ),
    "/api/caderno/fotos/": (
        "c",
        "POST mas SO LE: responde 501 (app/api/views/caderno.py:375). O "
        "`pwa/sync.js:144` chama esta rota e ela nao existe de facto. Medido "
        "como derivada e nao como escrita para nao contar por suposicao.",
    ),
    "/api/caderno/voice/": (
        "c",
        "POST mas SO LE: responde 501 (app/api/views/caderno.py:347). O "
        "`pwa/sync.js:252` chama esta rota e ela nao existe de facto. Mesmo "
        "caso da anterior.",
    ),
    "/api/^prescricoes-vra/(?P<pk>[^/.]+)/generate_iso_xml/$": (
        "c",
        "Deriva o XML e GRAVA-O em `PrescricaoVRA.iso_xml` "
        "(app/api/views/vra.py:73). O comentario da propria view diz que a "
        "atribuicao e' o que grava.",
    ),
    "/api/^notificacao-templates/(?P<pk>[^/.]+)/testar/$": (
        "c",
        "Manda push a superusers (app/api/views/financeiro_banco.py:238). "
        "`get_queryset` NAO filtra por user — e' global. Efeito externo.",
    ),
    "/api/^contas-bancarias/(?P<pk>[^/.]+)/importar_ofx/$": (
        "c",
        "POST mas SO LE: o parser OFX esta por implementar e devolve "
        "`importadas: 0` (app/api/views/financeiro_banco.py:63). Medido "
        "como escrita para nao contar por suposicao.",
    ),
    "/api/simulacao/": (
        "c",
        "Motor de simulacao (lucro, cenarios, montecarlo…). POST-only por "
        "desenho de API; e' calculo puro sobre params "
        "(app/api/views/financial.py:59).",
    ),
    "/api/^lancamentos-detalhados/conciliacao_upload/$": (
        "c",
        "POST mas SO LE: faz parse de OFX/CSV e devolve sugestoes de match "
        "(app/api/views/custos.py:398). Medido como escrita para provar.",
    ),
    "/api/^zarc/verificar_janela_plantio/$": (
        "c",
        "POST mas SO LE: consulta ZARC por cultura/UF/municipio/data "
        "(app/api/views/vra.py:312). `ZARC` e' catalogo publico da Embrapa.",
    ),
    "/api/amplia/ingestao/audio/sinais/": (
        "c",
        "POST mas SO LE: extrai sinais de um relato de voz "
        "(app/amplia_mcp/views.py:324).",
    ),
    "/api/amplia/palco/render/": (
        "c",
        "POST mas SO LE por decisao declarada: 'Nao grava nada. A mesa e' "
        "efemera' (app/api/views/amplia_palco.py:71).",
    ),
    "/api/amplia/exec/": (
        "c",
        "MCP. Executa UMA tool governada pelo sandbox; 31 dos intents do "
        "catalogo tem flag de escrita (app/amplia_mcp/views.py:211).",
    ),
    "/api/ia/executar/": (
        "c",
        "Sandbox auditado: `sandbox.executar` grava `IAExecucao` + `IAEvento` "
        "em QUALQUER intent, e escreve no dominio nos de flag write "
        "(app/ia/views.py:152).",
    ),
    "/api/relatorio/gerar/": (
        "c",
        "Cria `RelatorioGerado` ANTES de tentar gerar, e o 501 de 'nao ha "
        "gerador' deixa a linha gravada (app/api/views/relatorios.py:104).",
    ),
    # ---------------------------------------------------------------- (c)
    # ACAO QUE GERA DERIVADOS / VALIDA SEM PERSISTIR. Estas 4 rotas sao POST
    # mas NAO criam registos no banco de dados do utilizador — processam a
    # entrada e devolvem um resultado (ficheiro, validacao, resposta IA).
    # Tem de respeitar a revogacao, mas o efeito e' so leitura + saida.
    "/api/financeiro/lcdpr/gerar/": (
        "c",
        "Gera ficheiro LCDPR .txt para download. POST mas so LE e gera "
        "saida (app/api/views/financial.py:579). O `_responder` so aceita "
        "GET internamente; a view POST existe para formularios web.",
    ),
    "/api/ia/chave/testar/": (
        "c",
        "Valida chave de API na nuvem SEM gravar (app/ia/views.py:549). "
        "Throttle local; so consulta o provedor e devolve valido/invalido.",
    ),
    "/api/ia/nuvem/": (
        "c",
        "Chat na nuvem (Gemini). POST mensagens, devolve resposta (app/ia/views.py:638). "
        "Sem chave ou falha cai para motor local — nao persiste nada.",
    ),
    "/api/ia/ver-imagem/": (
        "c",
        "IA ve imagem (Gemini multimodal). POST imagem+pergunta, devolve "
        "descricao (app/ia/views.py:591). Imagem nao e' persistida.",
    ),
    # ---------------------------------------------------------------- (a)
    # ENDPOINT DE UTILIZADOR: cria ou guarda dados. Tem de respeitar a
    # revogacao. As duas marcadas <<< NAO PROPRIAM escopo: escrevem na
    # fazenda LIGADA a um servidor, por `propriedade_vinculada`.
    "/api/^tarefas-estagio/(?P<pk>[^/.]+)/mover/$": (
        "a",
        "Kanban. Para nao-produtores `get_queryset` inclui "
        "`Q(propriedade=propriedade_vinculada)` e `mover` faz "
        "`tarefa.save()` (app/api/views/production.py:281). <<< escreve na "
        "FAZENDA LIGADA, e nao na conta do servidor.",
    ),
    "/api/tarefas/associar/": (
        "a",
        "Associacao em lote. Resolve a propriedade por "
        "`perfil.propriedade_vinculada` para nao-produtores e faz "
        "`t.save()` em cada tarefa (app/views_tarefas_associacao.py:100). "
        "<<< escreve na FAZENDA LIGADA. Nao tem `@login_required` nem "
        "verificacao de `ativo_servidor`: a unica defesa e' o middleware.",
    ),
    "/api/salvar-geometria/": (
        "a",
        "`TalhaoGeometria.objects.update_or_create` + `talhao.save()` "
        "(app/api/views/production.py:417).",
    ),
    "/api/^propriedades/(?P<pk>[^/.]+)/geocode/$": (
        "a",
        "Actualiza `latitude/longitude/cidade/uf` da propriedade "
        "(app/api/views/production.py:563).",
    ),
    "/api/^experimentos/(?P<pk>[^/.]+)/fechar/$": (
        "a",
        "`exp.status='concluido'; exp.save()` (app/api/views/experimento.py:102).",
    ),
    "/api/^prescricoes-vra/bulk_create_from_talhao/$": (
        "a",
        "Cria uma `PrescricaoVRA` por talhao, em transacao (app/api/views/vra.py:83).",
    ),
    "/api/^medicoes-experimentais/lote/$": (
        "a",
        "Cria `MedicaoExperimental` em lote (app/api/views/experimento.py:224).",
    ),
    "/api/^operarios/(?P<pk>[^/.]+)/remover_login/$": (
        "a",
        "`funcionario.user = None` e `user.delete()` — apaga uma conta "
        "(app/api/views/user.py:1440).",
    ),
    "/api/^push-subscriptions/(?P<pk>[^/.]+)/desativar/$": (
        "a",
        "`sub.ativa = False; sub.save()` (app/api/views/financeiro_banco.py:217).",
    ),
    "/api/^conciliacoes-bancarias/(?P<pk>[^/.]+)/fechar/$": (
        "a",
        "Fecha a conciliacao e grava `saldo_sistema_fim`, `saldo_banco_fim`, "
        "`diferenca` e `status` (app/api/views/financeiro_banco.py:169).",
    ),
    "/api/^parcelamentos/(?P<pk>[^/.]+)/marcar_pago/$": (
        "a",
        "`parcelamento.status='PAGA'; save()` (app/api/views/financeiro_banco.py:127).",
    ),
    "/api/^parcelamentos/(?P<pk>[^/.]+)/cancelar/$": (
        "a",
        "`parcelamento.status='CANCELADA'; save()` (app/api/views/financeiro_banco.py:137).",
    ),
    "/api/onboarding/save/": (
        "a",
        "Cria `Propriedade` do utilizador + `PerfilUsuario.get_or_create` "
        "(app/api/views/user.py:475).",
    ),
    "/api/notificacao/<int:pk>/ler/": (
        "a",
        "`Notificacao.objects.filter(user=..., id=pk).update(lida=True)` "
        "(app/api/views/user.py:410).",
    ),
    "/api/widgets-layout-sync/": (
        "a",
        "`WidgetUsuario.objects.update_or_create(user=request.user, ...)` por "
        "widget (app/api/views/user.py:1074).",
    ),
    "/api/amplia/palco/clonar/": (
        "a",
        "`PresetPalco.objects.get_or_create` — um dashboard passa a existir no "
        "menu do utilizador (app/api/views/amplia_palco.py:188).",
    ),
    "/api/amplia/palco/avaliar/": (
        "a",
        "`AssinaturaPalco.objects.get_or_create` — dataset de treino do ML "
        "(app/api/views/amplia_palco.py:110).",
    ),
    "/api/amplia/alertas/visto/": (
        "a",
        "Marca o alerta proativo como visto (app/amplia_mcp/views.py:460).",
    ),
    "/api/amplia/proativo/devolver/": (
        "a",
        "Devolve um cenario a fila, queimando uma tentativa "
        "(app/amplia_mcp/views.py:390).",
    ),
    "/api/ia/evento/": (
        "a",
        "`IAEvento.objects.create` (app/ia/views.py:179).",
    ),
    "/api/ia/imagem-estoque/": (
        "a",
        "`IAArtefato.objects.update_or_create` com o rascunho de estoque "
        "(app/ia/views.py:256).",
    ),
    "/api/ia/confirmar-estoque/": (
        "a",
        "`EstoqueItem.objects.create` — o unico caminho que grava no estoque "
        "REAL e nao num rascunho (app/ia/views.py:342).",
    ),
    "/api/ia/web-search/": (
        "a",
        "Proxy de busca web. NAO tem caminho de escrita nenhum: nao toca em "
        "modelo (app/views/ia_proxy.py:16). Medido na mesma para nao contar "
        "por suposicao.",
    ),
}

#: Payload MINIMO e ESPECIFICO por padrao. Um 400 por falta de campo nao
#: prova furo nem prova seguranca, por isso cada payload foi escrito DEPOIS de
#: ler a view — nao copiado de outra rota. `json` = corpo JSON; `form` =
#: form-encoded (a view le `request.POST`); `ofx`/`csv` = multipart.
#: Um padrao ausente daqui cai em `sem_payload` e o teste de C.2 VERMELHO:
#: uma rota nao medida nao pode contar como "recusada".
POSTS_SO_POST = {
    # -- IOT / ACK DE COMANDO --------------------------------------------------
    # MEDIDO 2026-10-06. `comando_ack` e' uma rota so-POST que existia sem
    # entrada aqui. Sem esta entrada ela caia em `sem_payload`, o teste de
    # C.2 dava vermelho, e o de C.4 via `HTTP None sem token` - que parece
    # "a rota nao responde" e na verdade quer dizer "a rota nunca foi
    # medida".
    #
    # `device_eui` e' do dispositivo da FAZENDA LIGADA (`talhao_a` -> gateway).
    # Nao e' decorativo: e' o que faz o handler passar do 401 e ancorar na
    # propriedade. Sem um EUI real, o teste mediria um 403 - e um 403 aqui
    # seria a DEFESA a funcionar, nao a rota avariada.
    "/api/iot/comando/ack/": {
        "json": lambda c: {
            # O mesmo valor que `/api/iot/push/` usa. Nao e' um device real
            # de proposito: o 401 vem do `_resolve_auth`, ANTES de qualquer
            # lookup de dispositivo. Um EUI real faria o handler passar do
            # 401 e o 403 seguinte seria a defesa a funcionar - o que
            # tornaria o teste menos claro sobre o que esta' a medir.
            "device_eui": "X",
            "comando_id": "cmd-medicao",
            "status": "executado",
        },
    },
    # -- CADERNO DE CAMPO -----------------------------------------------------
    # MEDIDO 2026-10-04: campos lidos de `NotaCampoSerializer.Meta.fields` e
    # das validacoes em `caderno.py`. O minimo e' `conteudo` (obrigatorio) +
    # `talhao_id` (que e' o que amarra a nota a uma fazenda do produtor — sem
    # ele a nota fica sem dono, que e' o defeito que o proprio serializer
    # descreve). `fonte_dado` e' `read_only`: o cliente nao escolhe o estado,
    # e o `sync.js` envia `declarado`.
    "/api/caderno/notas/": {
        "json": lambda c: {
            "conteudo": "Nota de campo para medir a lavoura",
            "talhao_id": c["talhao_a"].pk,
        },
    },
    # Estas duas respondem 501 sem escrever. Payload minimo propositadamente
    # VAZIO: o que se quer medir e' que o 501 acontece ANTES de qualquer
    # validacao, e um payload com conteudo PODIA dar 400 em vez de 501 —
    # media a coisa errada.
    "/api/caderno/fotos/": {"json": lambda c: {}},
    "/api/caderno/voice/": {"json": lambda c: {}},
    # -- (a) ---------------------------------------------------------------
    # CADERNO DE CAMPO. MEDIDO 2026-10-04 (agente 4).
    #
    # Estas tres rotas entraram no inventario como "sem payload" — e o
    # proprio teste recusou: *"uma rota que fica por medir nao conta, nem
    # como furo nem como cobertura"*. Declarar o payload minimo e' o que as
    # faz entrar na matriz de escrita revogada.
    #
    # O campo da nota e' `conteudo`, NAO `texto`. E `fotos`/`voice` devolvem
    # 501 de proposito (o codigo diz o que falta), por isso o payload delas
    # e' vazio — nao e' desleixo: um 501 e' um >= 400, que e' o que este
    # teste mede, e o 403 do servidor revogado chega ANTES da view.
    #
    # Payload de "massa" que nem chegue ao serializer nao serviria: daria 400
    # para revogado e para activo, e nao distinguiria os dois. O que
    # distingue e' o 403 do decorator `exigir_sessao_json`.
    "/api/caderno/notas/": {
        "json": lambda c: {"conteudo": "Nota de teste de superficie."},
    },
    "/api/caderno/fotos/": {
        "json": lambda c: {},
    },
    "/api/caderno/voice/": {
        "json": lambda c: {},
    },
    "/api/^tarefas-estagio/(?P<pk>[^/.]+)/mover/$": {
        "json": lambda c: {"status": "concluido"},
    },
    "/api/tarefas/associar/": {
        "json": lambda c: {"ids": [c["tarefa_a"].pk], "status": "andamento"},
    },
    "/api/salvar-geometria/": {
        "json": lambda c: {
            "talhao_id": c["talhao_a"].pk,
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [[-56.0, -15.0], [-55.9, -15.0], [-55.9, -14.9], [-56.0, -15.0]]
                ],
            },
        },
    },
    "/api/^propriedades/(?P<pk>[^/.]+)/geocode/$": {"json": lambda c: {}},
    "/api/^experimentos/(?P<pk>[^/.]+)/fechar/$": {"json": lambda c: {}},
    "/api/^prescricoes-vra/bulk_create_from_talhao/$": {
        "json": lambda c: {
            "safra_id": c["safra_a"].pk,
            "dose_ha": 1,
            "tipo_insumo": "HERBICIDA",
            "unidade": "L",
        },
    },
    "/api/^medicoes-experimentais/lote/$": {
        "json": lambda c: {
            "medicoes": [
                {
                    "uid": "lote-probe-1",
                    "experimento_uid": str(getattr(c.get("exp_a"), "uid", "") or ""),
                }
            ]
        },
    },
    "/api/^operarios/(?P<pk>[^/.]+)/remover_login/$": {"json": lambda c: {}},
    "/api/^push-subscriptions/(?P<pk>[^/.]+)/desativar/$": {"json": lambda c: {}},
    "/api/^conciliacoes-bancarias/(?P<pk>[^/.]+)/fechar/$": {
        "json": lambda c: {"saldo_sistema_fim": "100.00", "saldo_banco_fim": "100.00"},
    },
    "/api/^parcelamentos/(?P<pk>[^/.]+)/marcar_pago/$": {"json": lambda c: {}},
    "/api/^parcelamentos/(?P<pk>[^/.]+)/cancelar/$": {"json": lambda c: {}},
    "/api/onboarding/save/": {
        "json": lambda c: {
            "nome_fazenda": "Fazenda Escrita Probe",
            "area": 50,
            "estado": "MT",
            "cidade": "Cuiaba",
        },
    },
    "/api/notificacao/<int:pk>/ler/": {"json": lambda c: {}},
    "/api/widgets-layout-sync/": {
        "json": lambda c: {
            "widgets": {"kpi-custo": {"gridX": 0, "gridY": 0, "gridW": 1, "gridH": 1}}
        },
    },
    "/api/amplia/palco/clonar/": {
        "json": lambda c: {
            "nome": "Mesa Probe",
            "estrutura": {
                "widgets": [{"tipo": "kpi-custo", "titulo": "P", "config": {}}]
            },
        },
    },
    "/api/amplia/palco/avaliar/": {
        "json": lambda c: {
            "assinatura": "ASSINATURA-PROBE-FASE-C",
            "veredito": "like",
            "estrutura": {
                "widgets": [{"tipo": "kpi-custo", "titulo": "P", "config": {}}]
            },
        },
    },
    "/api/amplia/alertas/visto/": {"json": lambda c: {"alerta_id": c["alerta_a"].pk}},
    "/api/amplia/proativo/devolver/": {"json": lambda c: {"cenario_id": 1}},
    "/api/ia/evento/": {
        "json": lambda c: {"tipo": "acesso", "resumo": "probe fase C", "dados": {}},
    },
    "/api/ia/imagem-estoque/": {"form": {"texto": "Adubo 10 kg"}},
    "/api/ia/confirmar-estoque/": {
        "json": lambda c: {
            "itens": [{"nome": "Adubo Probe", "quantidade": 10, "unidade": "kg"}]
        },
    },
    "/api/ia/web-search/": {"json": lambda c: {"q": "soja"}},
    # -- (c) ---------------------------------------------------------------
    "/api/^custo-producao/recalcular/$": {
        "json": lambda c: {"safra_ids": [c["safra_a"].pk]},
    },
    "/api/^custos-producao/recalcular/$": {
        "json": lambda c: {"propriedade_id": c["prop_a"].pk},
    },
    "/api/^prescricoes-vra/(?P<pk>[^/.]+)/generate_iso_xml/$": {"json": lambda c: {}},
    "/api/^notificacao-templates/(?P<pk>[^/.]+)/testar/$": {"json": lambda c: {}},
    "/api/^contas-bancarias/(?P<pk>[^/.]+)/importar_ofx/$": {
        "ofx": "OFXHEADER:100\nDATA:ON\n<STMTTRN>\n<TRNAMT>-10.00\n</STMTTRN>\n",
    },
    "/api/simulacao/": {
        "json": lambda c: {
            "tipo": "lucro",
            "params": {
                "area_ha": 100,
                "produtividade_sc_ha": 50,
                "preco_sc": 150,
                "custo_ha": 80,
            },
        },
    },
    "/api/^lancamentos-detalhados/conciliacao_upload/$": {
        "csv": "data;descricao;valor\n01/10/2026;venda;100,00\n",
    },
    "/api/^zarc/verificar_janela_plantio/$": {
        "json": lambda c: {
            "cultura_id": c["cultura"].pk,
            "uf": "MT",
            "municipio": "X",
            "data": "2026-10-04",
        },
    },
    "/api/amplia/exec/": {
        "json": lambda c: {
            "tool": "amplia_concluir_tarefa",
            "args": {"id": c["tarefa_a"].pk},
        },
    },
    "/api/ia/executar/": {
        "json": lambda c: {
            "intent": "concluir_tarefa",
            "params": {"id": c["tarefa_a"].pk},
        },
    },
    "/api/relatorio/gerar/": {"json": lambda c: {"template_id": c["rtpl"].pk}},
    "/api/amplia/ingestao/audio/sinais/": {
        "json": lambda c: {"texto": "aplicar 10 kg de adubo"},
    },
    "/api/amplia/palco/render/": {
        "json": lambda c: {
            "widgets": [{"tipo": "kpi-custo", "titulo": "P", "config": {}}]
        },
    },
    # -- NOVAS (c) ------------------------------------------------------------
    "/api/financeiro/lcdpr/gerar/": {"json": lambda c: {}},
    "/api/ia/chave/testar/": {"json": lambda c: {"chave": "sk-probe"}},
    "/api/ia/nuvem/": {
        "json": lambda c: {"mensagens": [{"role": "user", "content": "teste"}]}
    },
    "/api/ia/ver-imagem/": {
        "json": lambda c: {
            "imagem": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        }
    },
    # -- (b) ---------------------------------------------------------------
    "/api/iot/mqtt/webhook/": {"json": lambda c: {"foo": 1}},
    "/api/iot/push/": {"json": lambda c: {"device_eui": "X", "temperature": 22.5}},
    "/api/iot/push/<str:device_eui>/": {"json": lambda c: {"temperature": 22.5}},
    "/api/iot/dinamico/evento/": {"json": lambda c: {"valor": 22.5}},
}
#: `EXTRAS_COLECCAO` mede-as para a affirmacao "nao escreve em lado nenhum"
#: cobrir a superficie e nao so as rotas so-POST.
EXTRAS_COLECCAO = (
    (
        "/api/talhoes/",
        {
            "json": {
                "nome": "Talhao Probe",
                "area_hectare": "1.00",
                "propriedade": "REPLACE_PROP_A",
            }
        },
    ),
    (
        "/api/registros-producao/",
        {"json": {"registro": "REPLACE_REG_A", "nome": "Reg Probe", "status": "ativo"}},
    ),
    (
        "/api/tarefas-estagio/",
        {
            "json": {
                "estagio": "REPLACE_EST_A",
                "descricao": "Tarefa Probe",
                "propriedade": "REPLACE_PROP_A",
            }
        },
    ),
    (
        "/api/estoque/",
        {
            "json": {
                "nome": "Item Probe",
                "quantidade": 1,
                "unidade": "un",
                "propriedade": "REPLACE_PROP_A",
            }
        },
    ),
)


def rotas_so_post(dono):
    """Padroes /api/ que respondem 405 a um GET — ou seja, SO ACEITAM POST.

    A DESCOBERTA e' feita com o DONO da fazenda, nunca com o servidor revogado:
    um `ServidorRevogadoMiddleware` que exista devolve 403 ANTES do despacho de
    metodo, e-nesse caso um GET de revogado nunca chega a ser 405 — a
    descoberta via 405 estoura e o inventario fica vazio sem dar por isso.

    405 e' resposta de METODO, nao de tenancy, e o DRF decide-o em
    `APIView.dispatch` ANTES de chamar o handler: por isso o `pk` da rota de
    detalhe e' irrelevante aqui e pode ser `1`. Se a resposta nao for 405, a
    rota tem GET e therefore nao entra no inventario de escrita.
    """
    achadas = []
    c = Client(raise_request_exception=False)
    c.force_login(dono)
    for padrao in rotas_de_api():
        if _so_via_formato(padrao):
            continue
        corpo = _corpo_do_padrao(padrao)
        url = _montar_url(corpo, "1", {})
        if "<" in url or "(?P" in url or not url.startswith("/api/"):
            continue
        if c.get(url).status_code == 405:
            achadas.append((padrao, corpo, _params_do_padrao(padrao)))
    return achadas


def _resolver_url(corpo, params, contexto):
    """URL concreta da rota, com pks REAIS das linhas da fazenda A.

    Um pk inventado da 404 e um 404 que nao diz nada sobre revogacao. O que
    interessa e' que o id aponte para a linha que a view vai procurar — e' o
    que transforma "a rota foi exercitada" em "a rota foi exercitada a serio".
    """
    if not params:
        return _montar_url(corpo, "1", {})
    nome = params[0]
    valor = {
        "pk": contexto["pk_por_param"].get(nome, 1),
        "talhao_id": contexto["talhao_a"].pk,
        "device_eui": "PROBE-EUI-inexistente",
    }.get(nome, contexto["pk_por_param"].get(nome, 1))
    return _montar_url(corpo, valor, {"talhao_id": contexto["talhao_a"].pk})


# --------------------------------------------------------------------------
# O RASTO
# --------------------------------------------------------------------------


class _Rollback(Exception):
    """Nao e' um erro: e' a forma de medir cada POST isolado."""


_SQL_ESCRITA = re.compile(r"^\s*(INSERT|UPDATE|DELETE|REPLACE)\b", re.I)

#: Campos mutaveis das tabelas que estas rotas prometem mexer. Um `count()` diz
#: se entrou uma linha; nao diz se `status` mudou de 'pendente' para
#: 'concluido'. E' a segunda metade do rastro.
CAMPOS_MUTAVEIS = {
    "TarefaEstagio": ["status", "concluida", "ordem", "descricao"],
    "Propriedade": ["latitude", "longitude", "cidade", "uf", "nome", "area_total"],
    "PrescricaoVRA": ["iso_xml"],
    "Experimento": ["status", "data_fim"],
    "RelatorioGerado": ["status", "erro_msg"],
    "Notificacao": ["lida", "titulo"],
    "PushSubscription": ["ativa"],
    "CustoProducao": ["insumos", "receita", "custo_total"],
    "Funcionario": ["user"],
    "TalhaoGeometria": ["centroide_lat", "centroide_lon", "area_calculada_ha"],
    "Talhao": ["coordenadas"],
}

_MODELOS = None


def _modelos():
    """Modelos de `app.models` — a contagem que prova INSERTS."""
    global _MODELOS
    if _MODELOS is None:
        from django.db import models as djmodels

        from app import models as app_models

        out = []
        for nome in dir(app_models):
            m = getattr(app_models, nome, None)
            if (
                isinstance(m, type)
                and issubclass(m, djmodels.Model)
                and m._meta.managed
                and m._meta.app_label != "migrations"
            ):
                out.append((nome, m))
        _MODELOS = out
    return _MODELOS


def _txt(v):
    if v is None:
        return "\x00None"
    if isinstance(v, (int, float, Decimal, bool, str, bytes)):
        return repr(v)
    # Geometrias GEOS e instancias de model: `str()` e' ESTAVEL, `id()` NAO e'.
    # Uma versao anterior desta funcao usava `id(v)`, e o Django devolve um
    # objecto NOVO a cada leitura — o diff via "uma alteracao" em `Talhao.
    # coordenadas` em todas as rotas, sem que nada tivesse mudado. Falso
    # positivo em 36 rotas de uma vez.
    return "obj:%s" % str(v)[:60]


def _instantaneo():
    """(contagens, estados) do banco. Duas fotos para as comparar."""
    contagens = {}
    for nome, model in _modelos():
        try:
            contagens[nome] = model.objects.count()
        except Exception:  # noqa: BLE001 — um model que nao conta nao prova nada
            contagens[nome] = None
    estados = {}
    for nome, campos in CAMPOS_MUTAVEIS.items():
        model = dict(_modelos()).get(nome)
        if model is None:
            continue
        estados[nome] = [
            (o.pk, tuple(_txt(getattr(o, c, None)) for c in campos))
            for o in model.objects.order_by("pk")
        ]
    return contagens, estados


def _rastro(antes, depois):
    """(criados, actualizados) — o que entrou e o que mudou."""
    cont_a, est_a = antes
    cont_b, est_b = depois
    criados, actualizados = [], []
    for nome, n in sorted(cont_b.items()):
        m = cont_a.get(nome)
        if m is not None and n is not None and n != m:
            criados.append("%s %s->%s (+%d)" % (nome, m, n, n - m))
    for nome, linhas_b in sorted(est_b.items()):
        linhas_a = dict(est_a.get(nome, []))
        for pk, vals in linhas_b:
            if pk not in linhas_a:
                criados.append("%s pk=%s (nova linha)" % (nome, pk))
                continue
            mudados = [
                "%s: %s -> %s" % (c, linhas_a[pk][i][:26], vals[i][:26])
                for i, c in enumerate(CAMPOS_MUTAVEIS[nome])
                if linhas_a[pk][i] != vals[i]
            ]
            if mudados:
                actualizados.append("%s pk=%s  %s" % (nome, pk, "; ".join(mudados)))
    return criados, actualizados


class _MedicaoC:
    def __init__(self):
        self.inventario = []  # (padrao, url, handler, linha, classe, razao)
        self.sem_payload = []  # padroes sem payload valido
        self.revogado = {}  # padrao -> dict
        self.activo = {}  # padrao -> dict
        self.extras_revogado = []
        self.extras_activo = []
        self.semente = []


_MEDICAO_C = None


def _medir_post(cliente, url, payload):
    """Um POST, medido, e DEPOIS revertido.

    O savepoint existe por uma razao que e' a razao do teste ser honesto:
    `palco/clonar/` cria um `PresetPalco` que passa a existir no menu, e
    `onboarding/save/` cria uma propriedade. Sem rollback, a escrita da rota N
    muda o que a rota N+1 ve — e o resultado passa a depender da ordem. Com
    rollback, cada POST e' medido contra o MESMO banco.
    """
    from django.db import connection, transaction
    from django.test.utils import CaptureQueriesContext

    resultado = {}
    try:
        with transaction.atomic():
            antes = _instantaneo()
            with CaptureQueriesContext(connection) as ctx:
                if "csv" in payload or "ofx" in payload:
                    import django.core.files.uploadedfile as uf

                    if "csv" in payload:
                        up = uf.SimpleUploadedFile(
                            "extrato.csv", payload["csv"].encode(), "text/csv"
                        )
                    else:
                        up = uf.SimpleUploadedFile(
                            "extrato.ofx", payload["ofx"].encode(), "application/x-ofx"
                        )
                    resposta = cliente.post(url, data={"arquivo": up})
                elif "form" in payload:
                    resposta = cliente.post(url, data=payload["form"])
                else:
                    resposta = cliente.post(
                        url,
                        data=json.dumps(payload["json"]),
                        content_type="application/json",
                    )
            criados, actualizou = _rastro(antes, _instantaneo())
            sql = [
                q["sql"]
                for q in ctx.captured_queries
                if _SQL_ESCRITA.match(q["sql"] or "")
                # A sessao e' reescrita em qualquer pedido autenticado. Contar
                # esse UPDATE como "a view escreveu" seria verdademente falso —
                # e `django_session` (nao `auth_session`) e' o nome da tabela.
                and "_session" not in (q["sql"] or "")
            ]
            resultado = {
                "status": resposta.status_code,
                "criados": criados,
                "actualizou": actualizou,
                "sql": sql,
                "corpo": resposta.content.decode("utf-8", "replace")[:200].replace(
                    "\n", " "
                ),
            }
            raise _Rollback
    except _Rollback:
        pass
    return resultado


class SuperficieApiEscritaTest(TestCase):
    """MEDE a escrita revogada nas rotas POST de /api/. NAO corrige nada.

    Este TestCase repete o escenario de `SuperficieApiRevogacaoTest` (mesmas
    duas propriedades, mesmos dois servidores, mesmo seeding) e acrescenta o
    que a FASE B nao fazia: um POST por rota, com rastro medido no banco.
    """

    # -- infra ------------------------------------------------------------
    def setUp(self):
        self.prod_a = User.objects.create_user(
            username="prod_esc_a", password="x1234567"
        )
        self.prop_a = Propriedade.objects.create(
            user=self.prod_a, nome=MARCA_A, area_total=10, uf="MT", cidade="X"
        )
        self.talhao_a = Talhao.objects.create(
            propriedade=self.prop_a, nome=MARCA_A, area_hectare="5.00"
        )
        self.srv_revogado = _mkuser("srv_esc_revogado")
        PerfilUsuario.objects.update_or_create(
            user=self.srv_revogado,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "CAMPO",
                "propriedade_vinculada": self.prop_a,
                "ativo_servidor": False,
            },
        )
        self.srv_revogado.refresh_from_db()

        self.srv_ativo = _mkuser("srv_esc_ativo")
        PerfilUsuario.objects.update_or_create(
            user=self.srv_ativo,
            defaults={
                "tipo_usuario": "servidor",
                "area_servidor": "CAMPO",
                "propriedade_vinculada": self.prop_a,
                "ativo_servidor": True,
            },
        )
        self.srv_ativo.refresh_from_db()

        self._preparar()

    def _preparar(self):
        """Linhas de prop A que as rotas de detalhe precisam de apontar."""
        from app import models as app_models

        log, cache = [], {Talhao: self.talhao_a}
        semeados = {}
        for nome in MODELOS_SEMEAR:
            model = getattr(app_models, nome, None)
            if model is None:
                continue
            if _caminho_ate_propriedade(model) is None:
                continue
            obj = _semear(model, self.prop_a, self.prod_a, MARCA_A, cache, log)
            if obj is not None:
                semeados[nome] = obj
        self._semeados = semeados
        self._semente_log = log

        M = app_models
        self.reg_a = M.RegistroProducao.objects.filter(user=self.prod_a).order_by(
            "pk"
        ).first() or M.RegistroProducao.objects.create(user=self.prod_a, nome=MARCA_A)
        self.est_a = M.EstagioCultura.objects.filter(registro=self.reg_a).order_by(
            "pk"
        ).first() or M.EstagioCultura.objects.create(
            registro=self.reg_a, nome=MARCA_A, ordem=1
        )
        # Kanban da fazenda LIGADA: e' a linha que `mover` vai escrever.
        self.tarefa_a = M.TarefaEstagio.objects.create(
            estagio=self.est_a,
            descricao=MARCA_A,
            propriedade=self.prop_a,
            cargo_alvo="",
            status="pendente",
        )
        self.notif_a = M.Notificacao.objects.create(user=self.prod_a, titulo=MARCA_A)
        self.ntpl = M.NotificacaoTemplate.objects.create(
            titulo=MARCA_A, mensagem="oi {nome}", ativa=True, variaveis=["nome"]
        )
        self.psub_a = M.PushSubscription.objects.create(
            user=self.prod_a, endpoint="https://x.invalid/p", ativa=True
        )
        self.alerta_a = M.IAAlertaProativo.objects.create(
            user=self.prod_a,
            propriedade=self.prop_a,
            titulo=MARCA_A,
            mensagem="x",
            fingerprint="f" * 64,
        )
        # TEMPLATE DE RELATORIO DO SERVIDOR ACTIVO. `gerar_relatorio` filtra
        # `RelatorioTemplate.objects.filter(pk=..., user=request.user)`, entao
        # o template tem de ser DO SERVIDOR para a escrita ser alcancavel. Um
        # template do produtor daria 404 nos dois lados e o CONTROLO nao
        # provaria nada.
        self.rtpl_ativo = M.RelatorioTemplate.objects.create(
            user=self.srv_ativo, nome="TPL-SERVIDOR-ACTIVO", formato="pdf"
        )
        self.cultura = M.Cultura.objects.filter(ativo=True).order_by("pk").first()
        self.func_a = (
            M.Funcionario.objects.filter(propriedade=self.prop_a).order_by("pk").first()
        )

        self.contexto = {
            "talhao_a": self.talhao_a,
            "safra_a": semeados.get("Safra"),
            "presc_a": semeados.get("PrescricaoVRA"),
            "exp_a": semeados.get("Experimento"),
            "cultura": self.cultura,
            "prop_a": self.prop_a,
            "tarefa_a": self.tarefa_a,
            "alerta_a": self.alerta_a,
            "rtpl": self.rtpl_ativo,
            "reg_a": self.reg_a,
            "est_a": self.est_a,
            "pk_por_param": {
                "pk": None,  # preenchido por rota, abaixo
                "talhao_id": self.talhao_a.pk,
                "device_eui": "PROBE",
            },
        }
        # Um template por SERVIDOR, para o `/api/relatorio/gerar/` nao ficar
        # sem dono em nenhum dos lados do controlo.
        self.rtpl_revogado = M.RelatorioTemplate.objects.create(
            user=self.srv_revogado, nome="TPL-SERVIDOR-REVOGADO", formato="pdf"
        )

    def _cliente(self, user):
        c = Client(raise_request_exception=False)
        c.force_login(user)
        return c

    def _medicao(self):
        global _MEDICAO_C
        if _MEDICAO_C is not None:
            return _MEDICAO_C
        m = _MedicaoC()
        m.semente = list(self._semente_log)

        for padrao, corpo, params in rotas_so_post(self.prod_a):
            handler, linha = _handler(_resolver_callback(padrao))
            classe, razao = CLASSIFICACAO.get(padrao, ("?", "NAO CLASSIFICADA"))
            spec = POSTS_SO_POST.get(padrao)

            # O pk da rota de detalhe: a linha DA FAZENDA LIGADA que a view
            # vai procurar. Sem isto o POST da 404 por um id que nao existe e
            # nao mede nada.
            self.contexto["pk_por_param"]["pk"] = self._pk_para(padrao)
            url = _resolver_url(corpo, params, self.contexto)
            m.inventario.append((padrao, url, handler, linha, classe, razao))
            if spec is None:
                m.sem_payload.append(padrao)
                continue
            payload = {}
            for k, v in spec.items():
                payload[k] = v(self.contexto) if callable(v) else v
            m.revogado[padrao] = _medir_post(
                self._cliente(self.srv_revogado), url, payload
            )
            m.activo[padrao] = _medir_post(self._cliente(self.srv_ativo), url, payload)

        for url, template in EXTRAS_COLECCAO:
            corpo = dict(template["json"])
            for token, valor in (
                ("REPLACE_PROP_A", self.prop_a.pk),
                ("REPLACE_REG_A", self.reg_a.pk),
                ("REPLACE_EST_A", self.est_a.pk),
            ):
                if corpo.get(token) is not None:
                    corpo[token] = valor
            payload = {"json": corpo}
            m.extras_revogado.append(
                (url, _medir_post(self._cliente(self.srv_revogado), url, payload))
            )
            m.extras_activo.append(
                (url, _medir_post(self._cliente(self.srv_ativo), url, payload))
            )

        _MEDICAO_C = m
        return m

    def _pk_para(self, padrao):
        """pk de prop A do modelo que a rota nomeia.

        E' a linha que a view vai buscar. Um pk que nao existe da 404, e um
        404 nao mede revogacao nenhuma — so mede que o id nao existe.
        """
        s = self._semeados
        if "tarefas-estagio" in padrao:
            return self.tarefa_a.pk
        if "tarefas/associar" in padrao:
            return self.tarefa_a.pk
        if "notificacao-templates" in padrao:
            return self.ntpl.pk
        if "push-subscriptions" in padrao:
            return self.psub_a.pk
        if "propriedades" in padrao:
            return self.prop_a.pk
        if "notificacao/<int:pk>" in padrao:
            return self.notif_a.pk
        if "operarios" in padrao:
            return getattr(self.func_a, "pk", 1) or 1
        if "prescricoes-vra" in padrao:
            return getattr(s.get("PrescricaoVRA"), "pk", 1) or 1
        if "experimentos" in padrao:
            return getattr(s.get("Experimento"), "pk", 1) or 1
        if "conciliacoes-bancarias" in padrao:
            return getattr(s.get("ConciliacaoBancaria"), "pk", 1) or 1
        if "parcelamentos" in padrao:
            return getattr(s.get("Parcelamento"), "pk", 1) or 1
        if "contas-bancarias" in padrao:
            return getattr(s.get("ContaBancaria"), "pk", 1) or 1
        return 1

    def _imprime(self, titulo, linhas):
        sys.stdout.write("\n" + "=" * 78 + "\n%s\n" % titulo + "=" * 78 + "\n")
        for linha in linhas:
            sys.stdout.write(linha + "\n")
        sys.stdout.flush()

    def _linha_matriz(self, padrao):
        r = self._medicao().revogado.get(padrao, {})
        a = self._medicao().activo.get(padrao, {})
        return "  %-58s rev=%-3s act=%-3s rev_rastro=%s act_rastro=%s" % (
            padrao.replace("/api/", "")[:58],
            r.get("status"),
            a.get("status"),
            (r.get("criados") or r.get("actualizou") or "-"),
            (a.get("criados") or a.get("actualizou") or "-"),
        )

    # -- FASE C.1 — o inventario ------------------------------------------
    def test_o_inventario_das_rotas_so_post_e_o_que_diz_o_codigo(self):
        m = self._medicao()
        self._imprime(
            "INVENTARIO DAS ROTAS SO-POST DE /api/ — %d rotas" % len(m.inventario),
            [
                "  [%s] %-56s %s:%d\n         %s"
                % (classe, padrao.replace("/api/", "")[:56], handler, linha, razao)
                for padrao, url, handler, linha, classe, razao in m.inventario
            ],
        )
        self.assertTrue(
            m.inventario,
            "Nenhuma rota so-POST encontrada. A descoberta via 405 partiu — e um "
            "teste de escrita sem superficie nao mede nada. Se um middleware "
            "novo passou a responder 403 antes do despacho de metodo, a "
            "descoberta tem de mudar de donor, nao ser abandonada.",
        )
        por_classe = {}
        for padrao, _u, _h, _l, classe, _r in m.inventario:
            por_classe[classe] = por_classe.get(classe, 0) + 1
        self._imprime(
            "CLASSIFICACAO — %s"
            % ", ".join("%s=%d" % kv for kv in sorted(por_classe.items())),
            [],
        )

        # Rede de seguranca: a lista nao pode encolher em silencio. O numero
        # medido hoje e' 33; um numero muito menor significa que rotas novas
        # nasceram OR que a descoberta viu de menos.
        self.assertGreaterEqual(
            len(m.inventario),
            30,
            "O inventario de rotas so-POST caiu para %d. Ou a descoberta "
            "voltou a ver de menos, ou as rotas so-POST foram removidas. "
            "Nao tires rotas do teste sem decidir o que as substitui."
            % len(m.inventario),
        )
        # E nenhuma rota pode ficar por classificar: uma rota sem classe nao
        # entra em nenhuma contagem, e uma contagem que nao cobre tudo nao
        # conta nada.
        self.assertEqual(
            [(p, cl) for p, _u, _h, _l, cl, _r in m.inventario if cl == "?"],
            [],
            "Rotas so-POST sem classificacao a/b/c em CLASSIFICACAO. Uma rota "
            "nao classificada nao e' contada nem como furo nem como cobertura.",
        )
        for esperada in (
            "/api/^tarefas-estagio/(?P<pk>[^/.]+)/mover/$",
            "/api/tarefas/associar/",
            "/api/amplia/exec/",
            "/api/ia/executar/",
            "/api/relatorio/gerar/",
            "/api/iot/mqtt/webhook/",
            "/api/salvar-geometria/",
            "/api/onboarding/save/",
        ):
            self.assertIn(
                esperada,
                [p for p, _u, _h, _l, _c, _r in m.inventario],
                "A rota so-POST %s desapareceu do inventario." % esperada,
            )

    # -- FASE C.2 — a pergunta --------------------------------------------
    def test_um_servidor_revogado_nao_escreve_em_nenhuma_rota_de_utilizador(self):
        m = self._medicao()
        furadas, nao_mediveis = [], []
        for padrao, url, handler, linha, classe, razao in m.inventario:
            if classe not in ("a", "c"):
                continue
            r = m.revogado.get(padrao)
            if r is None:
                nao_mediveis.append("%s (sem payload)" % padrao)
                continue
            rastro = (r["criados"], r["actualizou"])
            if r["status"] < 400 or any(rastro):
                furadas.append(
                    "%s  ->  HTTP %s  criado=%s  actualizado=%s\n"
                    "        SQL: %s\n"
                    "        handler %s (linha %d)"
                    % (
                        padrao,
                        r["status"],
                        r["criados"] or "nada",
                        r["actualizou"] or "nada",
                        "; ".join(s[:90] for s in r["sql"][:3]) or "nenhum",
                        handler,
                        linha,
                    )
                )
        self._imprime(
            "ESCRITA REVOGADA — %d rotas (a)+(c) exercitadas" % len(m.revogado),
            [self._linha_matriz(p) for p in sorted(m.revogado)],
        )
        self._imprime(
            "RASTO DO SERVIDOR REVOGADO — o que ficou gravado",
            [
                "  %-56s HTTP %s  %s"
                % (
                    p[:56],
                    m.revogado[p]["status"],
                    (m.revogado[p]["criados"] + m.revogado[p]["actualizou"]) or "nada",
                )
                for p in sorted(m.revogado)
                if m.revogado[p]["criados"] or m.revogado[p]["actualizou"]
            ]
            or ["  nada, em nenhuma das rotas"],
        )
        self.assertEqual(
            nao_mediveis,
            [],
            "Estas rotas (a)/(c) ficaram por medir por falta de payload "
            "minimo:\n  %s" % "\n  ".join(nao_mediveis),
        )
        self.assertEqual(
            furadas,
            [],
            "ESCRITA REVOGADA CONFIRMADA — %d rota(s) /api/ aceitaram um POST "
            "de um servidor com ativo_servidor=False e sessao viva. O produtor "
            "desligou o servidor e o servidor ainda mexeu nos dados:\n  %s"
            % (len(furadas), "\n  ".join(furadas)),
        )

    # -- FASE C.3 — o que o servidor ACTIVO escreve ------------------------
    def test_o_controlo_o_servidor_ativo_responde_e_alcanca_a_escrita(self):
        """O 403 do revogado so' vale se o ACTIVO nao leva o mesmo 403.

        Sem este teste, um payload invalido da a mesma resposta aos dois e o
        'revogado foi recusado' nao prova nada. Aqui o ACTIVO tem de
        (a) passar, e (b) EM ALGUM LUGAR deixar rastro — e esse 'em algum
        lugar' e' o que prova que as sondas nao sao vazias.
        """
        m = self._medicao()
        escreveram = [
            (
                p,
                m.activo[p]["status"],
                m.activo[p]["criados"],
                m.activo[p]["actualizou"],
            )
            for p in sorted(m.activo)
            if m.activo[p]["criados"] or m.activo[p]["actualizou"]
        ]
        self._imprime(
            "CONTROLO — servidor ACTIVO, mesmos POSTs, mesma fazenda",
            [
                "  %-56s HTTP %-3s %s"
                % (
                    p[:56],
                    m.activo[p]["status"],
                    (m.activo[p]["criados"] or m.activo[p]["actualizou"] or "-"),
                )
                for p in sorted(m.activo)
            ],
        )
        self._imprime(
            "O ACTIVO DEIXOU RASTRO EM %d ROTAS" % len(escreveram),
            [
                "  %-46s HTTP %-3s %s" % (p.replace("/api/", "")[:46], s, (c + a) or "")
                for p, s, c, a in escreveram
            ],
        )

        activos = [p for p, _u, _h, _l, cl, _r in m.inventario if cl in ("a", "c")]
        self.assertTrue(
            activos,
            "Nenhuma rota de utilizador (a)/(c) no inventario.",
        )
        self.assertGreater(
            len([p for p in activos if m.activo.get(p, {}).get("status", 999) < 400]),
            0,
            "NENHUMA rota (a)/(c) respondeu <400 ao servidor ACTIVO. Ou a "
            "superficie mudou, ou os payloads deste ficheiro ficaram invalidos "
            "— e entao o 'o revogado foi recusado' de C.2 nao prova nada, "
            "porque nenhum dos dois lados foi aceite.",
        )
        self.assertGreater(
            len(escreveram),
            0,
            "O servidor ACTIVO passou em pelo menos uma rota e NAO deixou "
            "rastro em nenhuma. As sondas de escrita estao vazias: nenhum "
            "payload chega ao INSERT, e portanto o 403 do revogado pode ser "
            "simplesmente um payload que nunca escrevera.",
        )
        # A rota que escreve NA FAZENDA LIGADA tem de estar entre elas: e' a
        # que tornaria o buraco real se a revogacao nao a fechasse.
        self.assertTrue(
            any(
                p == "/api/^tarefas-estagio/(?P<pk>[^/.]+)/mover/$"
                for p, _s, _c, _a in escreveram
            ),
            "O ACTIVO nao escreveu em `/api/tarefas-estagio/<pk>/mover/`, que "
            "e' a rota que escreve na fazenda LIGADA. Ou o payload esta "
            "errado, ou a rota deixou de escrever — e as duas coisas sao "
            "motivos para nao confiar no resto desta medicao.",
        )

    # -- FASE C.4 — a classe (b), à parte ---------------------------------
    def test_as_rotas_de_maquina_nao_dependem_de_sessao_de_utilizador(self):
        """Classe (b): nao sao furo de revogacao, e nao contam como tal.

        Nao ha sessao de utilizador nestes endpoints — autenticam por
        `X-API-Key` de `Gateway` ou por token no header. Um servidor revogado
        NAO LHES DIREITA. O que se mede e' que um cliente SEM token leva 401,
        para ficar registado que alack de autenticacao nao e' a revogacao a
        funcionar.
        """
        m = self._medicao()
        linhas = []
        sem_401 = []
        for padrao, url, handler, linha, classe, razao in m.inventario:
            if classe != "b":
                continue
            linhas.append(
                "  [%s] %-46s %s:%d\n         %s" % (classe, url, handler, linha, razao)
            )
            activo = m.activo.get(padrao, {})
            if activo.get("status") not in (401, 404, 400):
                sem_401.append(
                    "%s -> HTTP %s sem token" % (padrao, activo.get("status"))
                )
        self._imprime("ROTAS DE MAQUINA (classe b) — %d" % len(linhas), linhas)
        self.assertTrue(
            linhas,
            "Nenhuma rota de maquina classificada. A classe (b) pode ter sido perdida.",
        )
        self.assertEqual(
            sem_401,
            [],
            "Estas rotas de maquina aceitaram um POST autenticado so por "
            "sessao de utilizador, sem token de Gateway:\n  %s" % "\n  ".join(sem_401),
        )

    # -- FASE C.5 — as rotas de coleccao ---------------------------------
    def test_nem_as_rotas_de_coleccao_do_router_aceitam_escrita(self):
        """`/api/talhoes/`, `/api/registros-producao/`, `/api/tarefas-estagio/`,
        `/api/estoque/` NAO sao so-POST (a FASE B exercitou-as por GET), mas o
        POST delas e' a maior superficie de escrita de /api/. Tre delas abrem
        explicitamente a porta a um nao-produtor via `propriedade_vinculada`.
        """
        m = self._medicao()
        self._imprime(
            "POST NAS ROTAS DE COLECCAO DO ROUTER (nao so-POST)",
            [
                "  %-34s rev=%-3s act=%-3s rev_rastro=%s"
                % (
                    url,
                    r["status"],
                    m.extras_activo[i][1]["status"],
                    (r["criados"] + r["actualizou"]) or "-",
                )
                for i, (url, r) in enumerate(m.extras_revogado)
            ],
        )
        furadas = [
            "%s -> HTTP %s  %s" % (url, r["status"], (r["criados"] + r["actualizou"]))
            for url, r in m.extras_revogado
            if r["status"] < 400 or r["criados"] or r["actualizou"]
        ]
        self.assertEqual(
            furadas,
            [],
            "O servidor REVOGADO escreveu por uma rota de coleccao do router:\n  %s"
            % "\n  ".join(furadas),
        )

    # -- FASE C.6 — o 500 que NAO e' recusa ------------------------------
    def test_um_500_nao_e_uma_recusa_o_500_da_notificacao_de_teste_e_bug(self):
        """Distinguir 500 de "recusou" — medido, nao arguments.

        `/api/notificacao-templates/<pk>/testar/` responde 500 ao servidor
        ACTIVO. A causa esta escrita na propria view: `from
        app.services.notificacoes import send_push_notification`, e esse
        modulo NAO EXISTE no repo (grep por `def send_push_notification` em
        app/: zero resultados). Um 500 aqui nao e' a revogacao a funcionar e
        nao e' um furo de revogacao: e' um modulo em falta. Este teste fica
        VERMELHO de proposito ate o modulo existir — um 500 que ninguem
        mede fica 500 para sempre.
        """
        m = self._medicao()
        padrao = "/api/^notificacao-templates/(?P<pk>[^/.]+)/testar/$"
        self.assertIn(
            padrao,
            m.activo,
            "A rota /api/notificacao-templates/<pk>/testar/ nao esta no "
            "inventario de rotas so-POST. Ou deixou de ser so-POST, ou a "
            "descoberta parou de a ver — e as duas coisas tornam este teste "
            "vazio em vez de vermelho.",
        )
        activo = m.activo[padrao]
        self._imprime(
            "500 vs RECUSA — /api/notificacao-templates/<pk>/testar/",
            [
                "  servidor REVOGADO: HTTP %s  %s"
                % (
                    m.revogado.get(padrao, {}).get("status"),
                    m.revogado.get(padrao, {}).get("corpo", "")[:90],
                ),
                "  servidor ACTIVO  : HTTP %s  %s"
                % (activo.get("status"), activo.get("corpo", "")[:90]),
            ],
        )
        self.assertNotEqual(
            activo.get("status"),
            500,
            "Este teste foi corrigido: `/api/notificacao-templates/<pk>/testar/` "
            "deixou de dar 500. Confirma que `app/services/notificacoes.py` "
            "passou a existir e que `send_push_notification` esta importavel — "
            "ou entao que a view deixou de o chamar, e nesse caso o 500 era "
            "outra coisa e o comentario deste teste esta errado.",
        )
