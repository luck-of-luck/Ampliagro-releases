"""
Invalidação do cache do painel — o produtor escreve, o painel tem de mostrar.

## O problema

`app/api/views/user.py::dashboard_data` guarda o payload agregado do painel em

    cache.set(f"dash:{request.user.id}", payload, 30)     # user.py:345

e `::widget_data` guarda o payload dos widgets em

    cache.set(f"widget_data:{request.user.id}:{0|1}", payload, 30)   # user.py:870

para não refazer ~20 agregações a cada abertura. O problema é que essas chaves
**nunca eram apagadas**: um `grep -r "cache.delete"` no repositório inteiro
devolve **zero ocorrências**. Não havia um único `post_save`/`post_delete` a
tocar naquilo.

A consequência prática é a que o produtor mais sente: ele lança uma despesa,
guarda, volta ao painel, e o número é o de antes — ou, num pior caso num payload
ainda vazio, o painel insiste em zeros enquanto o dado está lá na base de dados.
Até 30 segundos de uma mentira, num ecrã que parece autoritário.

O `LocMemCache` agrava: a janela vale **por processo**. Com mais do que um
worker, cada um tem a sua cópia, e "30 s" deixa de ser um limite.

## A correção

Um único ponto de invalidação, ligado aos modelos que o `dashboard_data` lê.
Não escrevemos o payload de novo — apagamos a chave, e a próxima leitura
recalcula a partir da base de dados. É a opção mais barata e a que não pode
divergir do que o painel mostra.

**Uma porta por prefixo, não uma chave solta.** A primeira versão apagava só
`dash:<uid>` e dava o assunto por resolvido. Não era: `widget_data` abre uma
segunda porta com a mesma janela de 30 s sobre os mesmos dados, e é a que
alimenta os widgets do dashboard. O mesmo sintoma, noutro ecrã — o produtor
via o número velho nos widgets depois de lançar a despesa. Agora
`PREFIXOS_DO_PAINEL` lista as portas e `invalidar_painel` apaga todas as
chaves do utilizador, variantes `full=1` incluídas. O teste em
`tests_cache_painel_portas.py` fixa o invariant: uma escrita apaga tudo o que
começa por uma chave de painel daquele utilizador.

## Porquê sinais e não "cache.delete() em cada viewset"

Sete viewsets escrevem estes dados (`financial`, `production`, `maquinario`,
`pecuaria`, `user`, …). Se a invalidação mora em cada viewset, a próxima
viewset nova volta a esquecer-se dela, e o mesmo bug regressa em silêncio.

Um sinal de `post_save`/`post_delete` cobre toda a escrita — API, admin do
Django, management commands, IA, testes — sem ninguém ter de se lembrar.
É a diferença entre "isto foi corrigido" e "isto não volta a partir de agora".

## Nota: LocMemCache em multi-processo

Isto resolve a mentira do número velho (o dado muda, o painel atualiza). Não resolve o
`LocMemCache` partilhado — para isso o cache tem de ser Redis/Memcached, que é
uma decisão de infraestrutura e não cabe aqui.
"""

import structlog
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = structlog.get_logger(__name__)

# Modelos cujos dados entram no payload de `dashboard_data`.
# Todos têm (directa ou indirectamente) um caminho até `Propriedade.user`.
MODELOS_DO_PAINEL = [
    "app.Propriedade",
    "app.LancamentoFinanceiro",
    "app.Safra",
    "app.Talhao",
    "app.Maquinario",
    "app.Funcionario",
    "app.Animal",
]


def _user_de(instance):
    """Descobre o dono do registo sem rebentar se o caminho não existir.

    Todas as relações possíveis a partir de cada modelo, por ordem de
    confiança. Um `getattr` directo é mais barato que uma consulta e não falha
    quando a FK é nula.
    """
    # Directo: Propriedade.user, Funcionario.user
    uid = getattr(instance, "user_id", None)
    if uid:
        return uid

    # Indirecto: tudo o mais desce até Propriedade
    prop = getattr(instance, "propriedade", None)
    if prop is not None:
        uid = getattr(prop, "user_id", None)
        if uid:
            return uid

    # Rede de segurança: um nível a mais (ex.: Talhao -> Safra -> Propriedade)
    for attr in ("safra", "talhao", "lote", "insumo", "parent"):
        rel = getattr(instance, attr, None)
        if rel is None:
            continue
        uid = getattr(rel, "user_id", None)
        if uid:
            return uid
        prop = getattr(rel, "propriedade", None)
        if prop is not None:
            uid = getattr(prop, "user_id", None)
            if uid:
                return uid
    return None


# Prefixos de TODOS os payloads de painel com cache, por utilizador.
#
# Não é só `dash:`. `widget_data` (app/api/views/user.py) abre uma segunda
# porta com a MESMA janela de 30 s e a MESMA origem de dados — e é a porta que
# alimenta os widgets do dashboard. Apagar só `dash:` deixava o produtor a ver
# o número velho nos widgets durante 30 s depois de lançar a despesa: o mesmo
# sintoma que este módulo existe para matar, só noutro ecrã.
#
# Um prefixo por porta, e `invalidar_painel` apaga todos. A próxima porta com
# cache é uma linha nesta lista — não um bug a redescobrir.
PREFIXOS_DO_PAINEL = (
    "dash",  # dashboard_data         -> dash:<uid>
    "widget_data",  # widget_data             -> widget_data:<uid>:<0|1>
)


def _chaves_do_usuario(uid):
    """Todas as chaves de painel de um utilizador, em todos os formatos."""
    for prefixo in PREFIXOS_DO_PAINEL:
        yield f"{prefixo}:{uid}"
        # `widget_data` tem uma variante `full=1` (o `0|1` da chave). Sem
        # esta segunda variante, o payload completo sobrevivia à invalidação
        # enquanto o resumo morria — metade do dashboard a mentir.
        for variante in (0, 1):
            yield f"{prefixo}:{uid}:{variante}"


def invalidar_painel(instance, **kwargs):
    """Apaga TODAS as chaves de painel do dono do registo que mudou."""
    try:
        uid = _user_de(instance)
        if not uid:
            return
        cache.delete_many(list(_chaves_do_usuario(uid)))
    except Exception:
        # Uma falha de cache nunca pode impedir que o dado seja gravado.
        # O que não pode é ser silenciosa: fica no log.
        logger.warning(
            "falha_invalidar_cache_painel",
            model=type(instance).__name__,
            pk=getattr(instance, "pk", None),
        )


def _ligar():
    """Liga os sinais. Chamado no `AppConfig.ready()`."""
    from django.apps import apps

    for label in MODELOS_DO_PAINEL:
        try:
            model = apps.get_model(label, require_ready=False)
        except LookupError:
            # O modelo foi renomeado/removido: o resto da invalidação
            # continua a funcionar, e a lista acima é o que se corrige.
            logger.warning("modelo_do_painel_desconhecido", model=label)
            continue
        post_save.connect(
            invalidar_painel, sender=model, dispatch_uid=f"dash_cache_save_{label}"
        )
        post_delete.connect(
            invalidar_painel, sender=model, dispatch_uid=f"dash_cache_delete_{label}"
        )


_ligado = False


def ligar():
    """Idempotente — chamar duas vezes não duplica sinais."""
    global _ligado
    if _ligado:
        return
    _ligado = True
    _ligar()
