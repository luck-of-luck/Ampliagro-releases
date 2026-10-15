"""Diz, por nome, o que segura a HTTPS quando o Caddy esta a terminar o TLS.

O QUE ESTE MODULO FAZ, E PORQUE EXISTE
=======================================

`config/settings/prod.py` endurece cinco coisas: `SECURE_SSL_REDIRECT`,
`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`,
`SECURE_HSTS_INCLUDE_SUBDOMAINS` e `SECURE_HSTS_PRELOAD`. Os valores chegam do
ambiente — e `docker-compose.prod.yml:30-37` explica, com razao, que o redirect
tem de ficar desligado numa instalacao sem certificado, porque forca-lo produz
um 301-em-loop que ninguem serve.

Isso e' um padrao correcto. O que o padrao NAO cobre e' a terceira
instalacao: a que TEM certificado, tem o Caddy a reenviar `X-Forwarded-Proto`
corretamente, e mesmo assim ficou com o redirect desligado porque o `.env` foi
copiado de um exemplo de outra instalacao.

Nessa instalacao, `SECURE_HSTS_SECONDS` pode continuar a valer um ano e
`request.is_secure()` e' verdadeiro quando chega ao browser — mas o
`Strict-Transport-Security` so e' emitido em resposta segura, e o browser
descarta o header de uma resposta http. O HSTS fica escrito no ficheiro e
nao existe no mundo. Nao ha aviso, porque nada no codigo esta errado.

Este modulo e' a torna que faz esse estado aparecer. Nao corrige nada, e nao
deve: cada um destes cinco valores e' uma decisao do operador, e um modulo que
os mudasse seria um modulo que decide por ele. Le, nomeia a chave de ambiente
que manda em cada um, e diz o que observar para confirmar.

O QUE NAO E' (para ninguem contar isto como mais do que e')
==========================================================

Nao e' uma vulnerabilidade. Um contentor de producao com o `.env` certo tem
os cinco valores ligados, e `prod.py` faz-los valer. Isto e' um medidor de
posto, do mesmo modo que `check_health.py` mede saude sem curar nada.

Nao e' um scanner. Nao procura XSS, nem injecao, nem segredos. Nao substitui
`check --deploy`, que ve as mesmas chaves mas nao diz o que observar nem qual
o ficheiro que as define.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Chave de setting -> (o que significa ligada, o que observar para confirmar).
#:
#: `observar` e' a MEIA CONFIGURACAO que o modelo nao pode ler do codigo: so o
#: browser diz se o HSTS pegou. E' por isso que esta tupla existe e nao um
#: simple booleano.
REGRAS: dict[str, tuple[str, str]] = {
    "SECURE_SSL_REDIRECT": (
        "a ligacao sem TLS e' desviada para https em vez de servida",
        "abra http://<dominio> num curl e confirme 301 para https, sem "
        "passar pelo Django duas vezes",
    ),
    "SESSION_COOKIE_SECURE": (
        "o cookie de sessao so e' enviado por https",
        "em https, o cookie sessionid deve aparecer com o atributo Secure",
    ),
    "CSRF_COOKIE_SECURE": (
        "o token CSRF so e' enviado por https",
        "em https, o cookie csrftoken deve aparecer com o atributo Secure",
    ),
    "SECURE_HSTS_SECONDS": (
        "o browser passa a recusar http sem perguntar",
        "curl -sI https://<dominio> | grep -i strict-transport-security — o "
        "header so aparece se a resposta foi considerada segura",
    ),
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": (
        "a promessa do HSTS vale para todos os subdominios",
        "os subdominios tem de ter HTTPS valido antes de ligar isto; um "
        "subdominio sem certificado deixa de responder e nao ha como recuar",
    ),
    "SECURE_HSTS_PRELOAD": (
        "o dominio entra na lista de preload dos browsers",
        "so para dominio de producao estavel: preload e' de curto prazo e "
        "difcil de tirar",
    ),
}


@dataclass(frozen=True)
class Lacuna:
    """Uma protecao desligada, e o que a religaria."""

    chave: str
    valor: object
    significa: str
    observar: str
    definida_no_ambiente: bool

    def em_texto(self) -> str:
        onde = (
            f"definida no ambiente (valor {self.valor!r})"
            if self.definida_no_ambiente
            else f"NAO esta no ambiente (valor {self.valor!r} veio do default do "
            f"settings)"
        )
        return f"{self.chave} esta desligada -> {self.significa}. Onde: {onde}."


#: `prod.py:41` e `prod.py:44` leem estas com `int(os.environ.get(...))`. E' o
#: segundo vocabulario que o modulo tem de servir, ao lado das flags de `prod.py:31-50`.
NUMERICAS = ("SECURE_HSTS_SECONDS",)


def _ligada(valor, *, numerica: bool = False) -> bool:
    """O valor e' uma proteccao ligada?

    Ha DOIS vocabularios em `prod.py`, e um modulo que use so um deles da
    respostas erradas a metade das chaves:

      * As flags (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
        `CSRF_COOKIE_SECURE`, os dois `INCLUDE_SUBDOMAINS`/`PRELOAD`) sao lidas
        com `.lower() in ("true", "1", "t")` — `prod.py:31-35`, `36-40`, `41-45`,
        `47-49`, `50-54`.
      * `SECURE_HSTS_SECONDS` e' lida com `int(...)` — `prod.py:46`. Nao e' uma
        flag: e' uma contagem de segundos. `"31536000"` e' um ano e `"0"` e'
        desligado, e nenhum dos dois esta em `("true","1","t")`.

    Por isso `numerica=True` traduz por valor, e nao por vocabulario de flag.
    Sem isto, `_ligada("31536000")` devolvia `False` e o medidor contava o HSTS
    de um ano como desligado — o erro exacto que este modulo existe para evitar.
    """
    if numerica:
        try:
            return int(valor) > 0
        except (TypeError, ValueError):
            return False
    if isinstance(valor, str):
        return valor.lower() in ("true", "1", "t")
    return bool(valor)


def lacunas(settings) -> list[Lacuna]:
    """As protecoes desligadas, por ordem de `REGRAS`."""
    encontradas = []
    for chave, (significa, observar) in REGRAS.items():
        valor = getattr(settings, chave, None)
        if valor is None:
            # A chave nao existe nesta configuracao. Nao e' uma lacuna: e' um
            # esquema diferente (settings de teste, por exemplo), e dizer que
            # falta protecao onde o campo nem existe seria inventar.
            continue
        if _ligada(valor, numerica=chave in NUMERICAS):
            continue
        encontradas.append(
            Lacuna(
                chave=chave,
                valor=valor,
                significa=significa,
                observar=observar,
                definida_no_ambiente=chave in os.environ,
            )
        )
    return encontradas


def relatorio(settings) -> str:
    """O texto para o operador. Diz o que falta E o que observar."""
    faltam = lacunas(settings)

    if not faltam:
        return (
            "Posto de seguranca completo: as "
            f"{len(REGRAS)} protecoes de transporte estao ligadas."
        )

    linhas = [
        f"Posto de seguranca: {len(faltam)} de {len(REGRAS)} protecoes "
        "de transporte estao desligadas.\n"
    ]
    for lacuna in faltam:
        linhas.append(f"  - {lacuna.em_texto()}")
        linhas.append(f"      Para confirmar depois de ligar: {lacuna.observar}\n")

    linhas.append(
        "Isto NAO e' uma falha do codigo: cada valor e' uma decisao de quem "
        "instala. Numa instalacao sem certificado o redirect tem de ficar "
        "desligado (ver `docker-compose.prod.yml:30-37`): forca-lo produz um "
        "301-em-loop que ninguem serve. O que este texto evita e' achar que o "
        "valor esta ligado porque esta escrito no ficheiro quando a resposta "
        "nao leva o cabecalho."
    )
    return "\n".join(linhas)
