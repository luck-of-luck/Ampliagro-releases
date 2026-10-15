"""Dizer se quem chegou e' pessoa ou maquina - e porquê.

PORQUE ISTO E' SERVER-SIDE E NAO JAVASCRIPT
===========================================
Um detector em JavaScript corre dentro da pagina que ele deve proteger. Quem
querer passar desliga o JavaScript e chega ao mesmo sitio, ou le a fonte do
detector em dois segundos e diz-lhe o que procurar. Nao e' seguranca, e'
decoracao.

Tudo o que este modulo usa chega no **pedido HTTP**, antes de haver resposta:
o `User-Agent`, os cabecalhos que so um browser p oe, e o **comportamento ao
longo do tempo** (quantos pedidos, com que cadencia, sobre que recursos). Um
crawler que nunca executa nada continua a deixar pegadas. Um scraper que
mexe nos cabecalhos imita um browser - e para imitar tem de mudar o que o
browser mudaria, que e' o que a pontuacao mede.

A HONESTIDADE DE UM DETECTOR DE BOT
==================================
Nao existe assinatura de bot verdadeira para sempre. Googlebot e' identificado
pelo IP, nao pelo user-agent; um scraper competente diz-se Chrome. Qualquer
pontuacao tem falso positivo - e um falso positivo aqui significa um produtor
fechado fora da propria fazenda.

Por isso o modulo, por omissao, **SO REGISTA**. Bloquear e' uma decisao
consciente, de quem sabe o que o sistema tem a perder.

O QUE CADA SINAL PODE E NAO PODE
==================================
- `User-Agent` vazio ou de ferramenta (curl, wget, python-requests): forte, mas
  com falso positivo - um produtor atras de um proxy corporativo tem um UA
  estranho. Sozinho nunca bloqueia.
- Ausencia de `Accept-Language` / `Accept-Encoding`: o `curl` minimo nao os
  manda. Sozinho tambem nunca bloqueia.
- Ausencia de `Sec-Fetch-*` e `Sec-CH-UA`: e' o sinal mais forte. Headers que
  o browser p oe e que `fetch()` nao manda; um cliente que os falsifica sem
  passar por um proxy fica com um perfil que nao corresponde a nenhuma
  combinacao real de browser.
- Cadencia: e' um sinal, nao o mais forte. Um produtor num link lento gera
  rajadas parecidas, por isso o mesmo numero de pedidos nao conta igual
  conforme o que o pedido pede.
- Ausencia de `Referer` em recurso: humano que navega clica e chega com
  `Referer`. `fetch()` nao. Sinal fraco, conta pouco.
- User-agent que se diz browser: sinal **negativo**. Um bot que se apresenta
  como Chrome esta a fazer o que os bots fazem, mas um produtor com proxy
  tambem, e nao e' o nosso alvo. Por isso desconta.

A pontuacao e' a soma. So passa do limiar quem junta **varios** sinais fracos,
que e' a diferenca entre "isto e' um humano" - afirmacao que nao se sustenta -
e "isto nao parece humano" - que se sustenta.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from django.conf import settings
from django.http import HttpResponse

log = logging.getLogger("ampliagro.bot")

#: User-agent de ferramentas de linha de comando e de clientes de biblioteca.
#: Nao sao "bots" no sentido maligno: sao integracoes legitimas - a IA local,
#: por exemplo. Por isso contam como sinal, e nao como veredicto.
_UA_FERRAMENTA = re.compile(
    r"\b("
    r"curl|wget|libwww-perl|python-requests|python-urllib|httpx|aiohttp|"
    r"go-http-client|java/|okhttp|apache-httpclient|node-fetch|axios|"
    r"postman|insomnia|scrapy|selenium|playwright|puppeteer|headlesschrome|"
    r"phantomjs|bot\b|crawler|spider|slurp|bingpreview|facebookexternalhit|"
    r"ahrefs|semrush|mj12|dotbot|petalbot|gptbot|claudebot|ccbot|perplexity"
    r")",
    re.IGNORECASE,
)

#: Tokens de browser sem interface grafica.
_UA_HEADLESS = re.compile(
    r"\b(headlesschrome|phantomjs|electron|puppeteer|playwright|selenium)\b",
    re.IGNORECASE,
)

#: Navegadores reais. A presenca de um destes e' um sinal negativo leve.
_UA_BROWSER_REAL = re.compile(
    r"\b(Chrome|Firefox|Safari|Edg|OPR|Brave)\b", re.IGNORECASE
)


@dataclass
class Perfil:
    """O que se deduziu de UM pedido."""

    pontuacao: int = 0
    sinais: list[str] = field(default_factory=list)
    user_agent: str = ""

    @property
    def e_bot(self) -> bool:
        return self.pontuacao >= getattr(settings, "BOT_LIMIAR", 8)

    @property
    def nivel(self) -> str:
        if self.pontuacao == 0:
            return "humano"
        if self.pontuacao < getattr(settings, "BOT_LIMIAR", 8):
            return "suspeito"
        return "bot"


def perfil_do_request(request) -> Perfil:
    """Classifica UM pedido. Sem estado, sem cache, sem base de dados.

    Deliberadamente sem estado: o que decide se alguem e' bot e' o conjunto de
    pedidos ao longo do tempo, e isso vive no `Registo`. Esta funcao responde
    so a "este pedido, sozinho, cheira a que lado".
    """
    p = Perfil()
    ua = (request.META.get("HTTP_USER_AGENT") or "").strip()
    p.user_agent = ua

    def soma(pontos, nome):
        p.pontuacao += pontos
        p.sinais.append(f"{nome}(+{pontos})")

    if not ua:
        # So este sinal ja passa do limiar, sozinho. Nao ha browser, curl,
        # wget ou cliente de biblioteca que omita o User-Agent; e' o pedido
        # mais perto de "nao ha ninguem atras disto" que se pode fazer sem
        # ver comportamento. Com +6 ficava abaixo do limiar e passava, o que
        # era o oposto do pretendido.
        soma(9, "sem user-agent")
        return p

    if _UA_FERRAMENTA.search(ua):
        # fetch/axios/requests sao integracoes legitimas. +3 e nao +10: um
        # produtor com uma aplicacao destas nao deve ser expulso.
        soma(3, "user-agent de ferramenta")

    if _UA_HEADLESS.search(ua):
        soma(4, "user-agent headless")

    if not request.META.get("HTTP_ACCEPT_LANGUAGE"):
        soma(2, "sem Accept-Language")
    if not request.META.get("HTTP_ACCEPT_ENCODING"):
        # +1 e nao +2: `Accept-Encoding` falta em HTTP/2 sem compressao e em
        # varios clientes legitimos. Um sinal que da falso positivo nao serve
        # para fechar ninguem.
        soma(1, "sem Accept-Encoding")

    # O sinal mais forte: headers que o browser poe e o fetch() nao manda.
    if not (
        request.META.get("HTTP_SEC_FETCH_SITE")
        or request.META.get("HTTP_SEC_FETCH_MODE")
        or request.META.get("HTTP_SEC_CH_UA")
    ):
        soma(3, "sem Sec-Fetch-*")

    if not request.META.get("HTTP_REFERER") and request.path.startswith("/static/"):
        soma(1, "recurso sem Referer")

    if _UA_BROWSER_REAL.search(ua):
        p.pontuacao = max(0, p.pontuacao - 1)
        p.sinais.append("user-agent de browser(-1)")

    return p


class Registo:
    """Comportamento ao longo do tempo: cadencia e concentracao.

    Guarda so' o que o sinal precisa. O `request_id` e' descartado de
    proposito: um registo de quem pediu o que e' um registo de dados pessoais,
    e este modulo nao precisa dele para nada.

    Em memoria e por processo. Num deploy com varios workers cada um ve' so
    uma fraccao do trafego, o que reduz a sensibilidade - e' o motivo
    declarado para isto nao ser a unica defense. O limite duro (o cache do
    Django) e' o que segura o que a memoria nao segura.
    """

    #: Teto de rotas distintas por cliente. Sem isto, um crawler que varre o
    #: site cresce o dicionario sem limite e o registo passa a ser o vector
    #: de negacao de servico.
    MAX_ROTAS = 300
    MAX_MARCAS = 500
    JANELA = 60.0

    def __init__(self):
        self._vistos: dict[str, list[float]] = {}
        self._recursos: dict[str, set[str]] = {}

    def regista(self, chave: str, caminho: str, agora: float) -> None:
        marcas = self._vistos.setdefault(chave, [])
        marcas.append(agora)
        corte = agora - self.JANELA
        if len(marcas) > self.MAX_MARCAS:
            marcas[:] = [t for t in marcas if t >= corte][-self.MAX_MARCAS :]
        if not caminho.startswith("/static/"):
            rotas = self._recursos.setdefault(chave, set())
            rotas.add(caminho.split("?")[0])
            if len(rotas) > self.MAX_ROTAS:
                # Descarta as mais antigas do conjunto, para o dicionario
                # nao crescer sem limite.
                self._recursos[chave] = set(sorted(rotas)[-self.MAX_ROTAS :])

    def pontua(self, chave: str, agora: float) -> tuple[int, list[str]]:
        """Sinal de DISPERSAO. A cadencia nao e' contada aqui.

        A cadencia vive no cache (`conta_na_janela`), que e' partilhado entre
        workers. Contar tambem aqui seria contar duas vezes, e o numero que
        apareceria no log nao corresponderia a nenhum dos dois.

        E a dispersao fica por processo, com uma consequencia declarada: com
        N workers, este sinal ve' so 1/N do que o cliente fez. Por isso nunca
        chega sozinho ao limiar — junta-se a Headers e a Cadencia.
        """
        pontos = 0
        descricao: list[str] = []
        corte = agora - self.JANELA
        n = len([t for t in self._vistos.get(chave, ()) if t >= corte])

        # Marcha por muitas rotas distintas sem voltar a nenhuma: e' um mapa do
        # site a ser feito, nao alguem a trabalhar.
        rotas_distintas = len(self._recursos.get(chave, ()))
        if n >= 20 and rotas_distintas >= 15:
            pontos += 3
            descricao.append(f"{n} pedidos por {rotas_distintas} rotas(+3)")
        return pontos, descricao


#: Um registo por processo. As operacoes sao curtas e o pior caso de uma
#: corrida e' um ponto a mais ou a menos num pedido - o `dict` do Python trata
#: isso sob o GIL, e nao vale um lock.
_REGISTO = Registo()


def chave_do_cliente(request) -> str:
    """Identidade do cliente, com Cloudflare em cima.

    A ORDEM E' O TODO. Cada camada e' so possivel porque a de cima esta a
    reescrever o campo de baixo — e cada uma e' tambem um risco, porque cada
    uma e' um campo que o cliente pode escolher, se a de cima nao a impuser.

    1. `CF-Connecting-IP`: o que o CloudFACE poe, por o hostname do cliente.
       So com `BOT_USAR_CF_IP` ligado, e so quando o origin NAO for
       directamente acessivel pela internet — se for, alguem chega ao origin
       sem passar pelo Cloudflare e inventa o cabecalho. Ver a nota de
       seguranca no `settings`.
    2. `X-Forwarded-For`: o primeiro elemento e' o cliente original, se o
       proxy fez o trabalho dele. So com `BOT_CONFIA_XFF`.
    3. `REMOTE_ADDR`: o que o socket viu. Sem isto, atras de um proxy, todos
       os clientes sao o proxy e o limite conta-os como um so.

    Nunca `USER_AGENT` como chave: e' o campo que o cliente escolhe
    deliberadamente, e usá-lo para limitear e' o mesmo que nao ter limite.
    """
    if getattr(settings, "BOT_USAR_CF_IP", False):
        cf = request.META.get("HTTP_CF_CONNECTING_IP")
        if cf:
            return cf.strip()
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff and getattr(settings, "BOT_CONFIA_XFF", False):
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "desconhecido"


#: Prefixo das chaves no cache. Nao e' cosmetico: o Redis do Ampliagro e'
#: partilhado com o Celery e com o cache de qualquer outra coisa, e uma chave
#: sem namespace colide com o que ja la esta.
_PREFIXO = "ampliagro:bot"


def conta_na_janela(chave: str, janela: int) -> int:
    """Quantos pedidos este cliente fez na janela. Atomico e partilhado.

    PORQUE O CACHE E NAO O `Registo`
    ==============================
    O `Registo` vive na memoria do processo. Com gunicorn a 4 workers, cada um
    ve' um quarto do trafego — e um scraper a 60 pedidos/min passava a
    15 por worker, abaixo de qualquer limiar. O cache de producao e' Redis
    (`django_redis`), partilhado por todos os processos e por todas as
    maquinas: a contagem passa a ser a contagem real.

    O padrao `add` + `incr` e' o que torna isto correcto sob concorrencia.
    `incr` sozinho rebenta em chave inexistente; `add` sozinho perde a
    contagem sempre que a janela se renova. Com os dois, o primeiro pedido da
    janela cria a chave e os seguintes somam sem corrida.

    FAIL-OPEN, deliberadamente: se o Redis estiver em baixo, este metodo
    devolve 0 e o site continua a servir. Um limitador que derruba o ERP
    quando a sua propria dependencia cai e' pior que o problema que resolve.
    """
    from django.core.cache import cache

    k = f"{_PREFIXO}:n:{chave}"
    try:
        if cache.add(k, 1, janela):
            return 1
        return int(cache.incr(k))
    except ValueError:
        # A chave expirou entre o `add` e o `incr`. Nao e' um erro: e' a
        # janela a rodar. Contar como 1 e' o comportamento certo.
        return 1
    except Exception:  # noqa: BLE001 - o cache nao pode derrubar o pedido
        log.warning("cache indisponivel ao contar pedidos; a Falhar Aberto")
        return 0


def _isento(caminho: str) -> bool:
    return any(
        caminho.startswith(p) for p in (getattr(settings, "BOT_ISENTOS", ()) or ())
    )


class BotDeteccaoMiddleware:
    """Regista sempre. Bloqueia so com `BOT_BLOQUEAR = True`.

    A posicao no `MIDDLEWARE` e' DEPOIS do `AuthenticationMiddleware`, e essa
    ordem e' deliberada: e' so ai que `request.user` existe, e sem ele nao ha
    como distinguir um produtor com login de um raspador. O preco e' abrir a
    sessao antes de recusar — uma linha em `django_session` por pedido
    recusado. Aceito: pagamos uma linha para poder garantir que nao fechamos
    o sistema a quem trabalha nele.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "BOT_DETECTOR_LIGADO", False):
            return self.get_response(request)
        if _isento(request.path):
            return self.get_response(request)

        agora = time.monotonic()
        chave = chave_do_cliente(request)
        p = perfil_do_request(request)

        # A CADENCIA vem do cache: e' partilhada entre workers. A DISPERSAO vem
        # do `Registo`, que e' por processo — e essa assimetria e' declarada,
        # nao escondida: com 4 workers, cada um so' viu um quarto das rotas
        # que o cliente visitou. A dispersao e' um sinal *fracionario* e
        # por isso nunca chega sozinho ao limiar.
        janela = int(getattr(settings, "BOT_JANELA_SEGUNDOS", 60))
        limite = getattr(settings, "BOT_PEDIDOS_POR_MINUTO", 90)

        n = conta_na_janela(chave, janela)
        if n > limite:
            # +4 e nao a pontuacao toda: um cliente acima do limite pode ser um
            # produtor com uma tela parada a recarregar, e fechar esse e' o
            # erro que este modulo existe para nao cometer. A pontuacao tem de
            # somar com o resto para o portao fechar.
            p.pontuacao += 4
            p.sinais.append(f"{n} pedidos/{janela}s, limite {limite}(+4)")
        elif n > limite * 0.8:
            p.pontuacao += 2
            p.sinais.append(f"{n} pedidos/{janela}s, perto do limite(+2)")

        extra, descricao = _REGISTO.pontua(chave, agora)
        p.pontuacao += extra
        p.sinais.extend(descricao)

        _REGISTO.regista(chave, request.path, agora)
        request.perfil_bot = p

        if not p.e_bot:
            return self.get_response(request)

        # QUEM TEM SESSAO PASSA SEMPRE.
        #
        # Esta e' a razao de o middleware estar DEPOIS do
        # AuthenticationMiddleware, e nao antes: e' so ai que `request.user`
        # existe. Um produtor com login recebe 403 porque a IA o skepeou e
        # fecha-lhe o painel? Nao — e' o unico garante real contra falso
        # positivo, porque um raspador nunca tem sessao.
        #
        # O preco e' abrir a sessao antes de recusar. E' um custo medido e
        # aceito: pagamos uma linha em `django_session` para conseguir dizer
        # com certeza que nao estamos a fechar o sistema a quem trabalha nele.
        utilizador = getattr(request, "user", None)
        if utilizador is not None and getattr(utilizador, "is_authenticated", False):
            log.info(
                "perfil=%s pontuacao=%d sinais=%s chave=%s caminho=%s "
                "deixado_passar=autenticado",
                p.nivel,
                p.pontuacao,
                "|".join(p.sinais),
                chave,
                request.path,
            )
            return self.get_response(request)

        bloquear = bool(getattr(settings, "BOT_BLOQUEAR", False))
        log.info(
            "perfil=%s pontuacao=%d sinais=%s chave=%s caminho=%s bloqueado=%s",
            p.nivel,
            p.pontuacao,
            "|".join(p.sinais),
            chave,
            request.path,
            bloquear,
        )
        if bloquear:
            return _resposta()
        return self.get_response(request)


def _resposta() -> HttpResponse:
    """Resposta a um bot.

    **403 e nao 404**: mentir sobre a existencia da pagina e' uma proteccao
    real contra quem procura, e um 403 bem formado diz ao scraper que a
    resposta e' deliberada - o que faz muita gente desistir.

    O corpo nao diz *porque*. Um detector que explica as suas regras e' um
    detector que se pode evitar.
    """
    return HttpResponse(
        "Pedido recusado.\n",
        status=403,
        content_type="text/plain; charset=utf-8",
    )
