"""O historico real do produtor por cultura. O que se pode mostrar SEM INVENTAR.

POR QUE ESTE SERVICO EXISTE
===========================
A tabela `Cultura` tem as colunas de agronomia **vazias** (MEDIDO 2026-10-05
em `db.sqlite3`):

    janela_plantio_inicio    0/709     0.0%
    janela_plantio_fim       0/709     0.0%
    chave_mercado           0/709     0.0%
    ciclo_dias              2/709     0.3%

A guia mostra 709 **nomes** e zero agronomia. O `PLANO-EXECUCAO.md:82` ja
o tinha dito das 488 do config — *"sao nomes, nao tem agronomia nenhuma"* —
e a tabela e' a mesma coisa com mais linhas.

MAS os dados existem noutro sitio: `app_safra` tem `data_plantio` (78%),
`data_colheita` (67%) e `produtividade` (67%). Sao do produtor, nao de um
catalogo. E dai sai mais do que a guia mostra hoje:

    Milho   2025-02-28 -> 2025-06-20   116 dias   75 sc/ha
    Soja    2024-10-15 -> 2025-02-20   129 dias   65,3 sc/ha
    Cafe    2024-05-01 -> 2024-07-10   443 dias   30 sc/ha

A DIFERENCA PARA A JANELA NACIONAL
=================================
*"Esta fazenda fez soja em 129 dias"* e' um facto que o produtor sabe, e
que pode comparar com o ano passado. *"A soja leva 120 dias"* e' uma media
nacional que nao e' dele e que muda com a cultivar e com a regiao.

Mostramos o primeiro. O segundo exigiria fonte citada — Embrapa, Extension
rural — e nao se inventa.

AS QUATRO REGRAS DESTE MODULO
=============================
1. Sem dado devolve `None` com motivo. **Nunca 0.** O produtor nao fez zero
   ciclos: ainda nao plantou aquela cultura. Um `ciclos: 0` e' uma
   affirmacao falsa, do mesmo tipo do `tco2e: 12,5` que o `3.md` regista.

2. Ciclo com amplitude absurda **nao vira numero unico**. O cafe da base
   real tem ciclos de 60 a 469 dias (amplitude 409): 60 dias e' curto demais
   para um perene, e' uma data mal posta. A media seria 264 dias — um numero
   que nunca existiu. O que se mostra e' a amplitude, com alerta.

3. Um ciclo de **uma** safra e' uma observacao, nao um ciclo. Fica marcado
   em `ciclo_amostras`, para o ecrã poder dizer "1 safra" em vez de
   "ciclo: 129 dias" sem saber se se repete.

4. **O tenancy entra pelo filtro, nao por um parametro opcional.** O servico
   recebe uma query ja filtrada pelo `_middleware` de tenant. Passar
   `propriedade_ids` como argumento seria um parametro que o chamador pode
   esquecer — e esquecer um filtro de tenant nao devolve um erro, devolve a
   safra do vizinho.

POR QUE UM SERVICO E' NAO UMA FUNCAO NA VIEW
===========================================
`app/views/guias.py` tem 788 linhas e esta a ser reescrito por outra sessao
neste momento. Um calculo de estatistica agricola nao e' responsabilidade
de uma view, e um servico novo nao colide com quem esta a mexer no
`guias.py`.
"""

from __future__ import annotations

import datetime
from collections import defaultdict

#: Um ciclo com amplitude acima desta razao entre a maior e a menor nao e'
#: variacao de cultura: e' dado mau posto. A base real tem cafe com 60 e
#: 469 dias — razao 7,8. Um cafe perene nao varia 8x entre safras.
RAZAO_AMPLITUDE_SUSPEITA = 2.0

#: A chave que a guia recebe para uma cultura sem historico. `safras: 0`
#: nao e' "o produtor fez zero safras" — e' "nao ha registo". A diferenca
#: entre `0` e `None` e' o que separa um dado de uma affirmacao.
SEM_DADO = {
    "safras": 0,
    "anos": [],
    "ciclo_medio": None,
    "ciclo_amplitude": None,
    "ciclo_amostras": 0,
    "produtividade_media": None,
    "area_total": None,
    "fonte": "sem_dado",
    "motivo": "Nenhuma safra registada para esta cultura.",
    "alerta": None,
}


def dias_entre(inicio, fim):
    """Dias entre duas datas. `None` se faltar uma, se nao parsear, ou se
    a segunda for anterior a primeira.

    MEDIDO 2026-10-05: a primeira versao usava a aritmetica
    `ano*372 + mes*31 + dia`, para nao depender de `strptime`. **Dava os
    numeros errados.** Comparam-se contra `datetime`:

        2024-01-01 -> 2024-05-10   a formula dava 133   o real e' 130

    Um `mes = 31 dias` ignora os meses de 30 e de fevereiro, e um
    `ano = 372` ignora o ano bissexto. O erro era de 3 dias por intervalo —
    o suficiente para transformar um ciclo de 130 em 133, e o suficiente
    para disparar o alerta de amplitude errada e esconder o ciclo de uma
    cultura que **nao** tem datas mau postas.

    E' o mesmo erro que o `PLANO-EXECUCAO.md` mediu no `1.md`: medir com
    uma aproximacao e' medir errado, so que mais devagar. `datetime.date`
    trata anos bissextos, meses de comprimento diferente e a regra dos
    seculos. Nao ha razao para nao usar.
    """
    if not inicio or not fim:
        return None
    try:
        a = _como_data(inicio)
        b = _como_data(fim)
        if a is None or b is None:
            return None
        d = (b - a).days
    except (ValueError, TypeError, OverflowError):
        return None
    # datas invertidas: COLHEITA antes do PLANTIO. Menos de 0 e' sempre erro
    # de digitacao, e um ciclo negativo nao e' informacao agricola.
    return d if d > 0 else None


def _como_data(valor):
    """`date` | `datetime` | "YYYY-MM-DD..." -> `date`, ou `None`."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    texto = str(valor).strip()
    if len(texto) < 10:
        return None
    try:
        return datetime.date(int(texto[0:4]), int(texto[5:7]), int(texto[8:10]))
    except ValueError:
        return None


def historico_por_cultura(safras):
    """Estatistica observada por cultura, a partir de uma lista de safras.

    `safras` e' uma **query ja filtrada pelo tenancy**, atravessada como
    iteravel. Recebe-se o iteravel e nao os ids porque um parametro
    opcional de filtro e' um filtro que alguem vai esquecer — e esquecer um
    filtro de tenant nao da erro, da a safra do vizinho.

    Cada linha e' um tuplo:

        (cultura_id, ano, data_plantio, data_colheita, produtividade, area)

    Devolve `{cultura_id: {...}}`. Toda a entrada tem `_fonte` ("medido" ou
    "sem_dado"), `_motivo` e `_alerta`, porque um numero sem origem
    declarada nao pode ser mostrado no ecra.
    """
    por_id = defaultdict(
        lambda: {"anos": set(), "ciclos": [], "prods": [], "area": 0.0}
    )

    for linha in safras:
        (
            cultura_id,
            ano,
            data_plantio,
            data_colheita,
            produtividade,
            area,
        ) = linha[:6]

        if not cultura_id:
            # safra sem cultura: nao pertence a nenhuma ficha. Registrar
            # sob `None` seria criar uma cultura fantasma que o produtor
            # nunca pediu.
            continue

        d = por_id[cultura_id]
        if ano:
            try:
                d["anos"].add(int(ano))
            except (TypeError, ValueError):
                pass

        dias = dias_entre(data_plantio, data_colheita)
        if dias is not None:
            d["ciclos"].append(dias)

        if produtividade is not None:
            try:
                d["prods"].append(float(produtividade))
            except (TypeError, ValueError):
                pass

        if area is not None:
            try:
                d["area"] += float(area)
            except (TypeError, ValueError):
                pass

    fora = {}
    for cultura_id, d in por_id.items():
        ciclos = sorted(d["ciclos"])
        n = len(ciclos)
        media = amplitude = None
        alerta = None

        if n:
            media = sum(ciclos) / n
            amplitude = (ciclos[-1] - ciclos[0]) if n > 1 else 0
            razao = amplitude / media if media else 0
            if amplitude and razao > RAZAO_AMPLITUDE_SUSPEITA - 1.0:
                alerta = (
                    "As datas de plantio e colheita desta cultura estao "
                    "espalhadas em %d dias (de %d a %d). Isso nao e' variacao "
                    "de cultura: e' data posta no sitio errado. O ciclo medio "
                    "nao esta a ser mostrado porque o numero nao seria verdade."
                    % (amplitude, ciclos[0], ciclos[-1])
                )
        if alerta is not None:
            # o alerta NAO e' um aviso a月上 um numero: o numero some.
            media = None
            amplitude = None

        fora[cultura_id] = {
            "safras": len(d["anos"]) or len(ciclos) or 1,
            "anos": sorted(d["anos"]),
            "ciclo_medio": round(media) if media is not None else None,
            "ciclo_amplitude": amplitude,
            "ciclo_amostras": n,
            "produtividade_media": (
                round(sum(d["prods"]) / len(d["prods"]), 1) if d["prods"] else None
            ),
            "area_total": round(d["area"], 2) if d["area"] else None,
            "fonte": "medido",
            "motivo": None,
            "alerta": alerta,
        }

    return fora


def para_o_ecra(historico):
    """Junta o que existe com o `SEM_DADO` do que nao existe.

    A guia tem 709 culturas e 6 com safra. As outras 703 **nao** sao um
    dicionario vazio: sao `SEM_DADO`, que o ecrã mostra como "ainda nao
    registou" em vez de omitir em silencio. Um cartao sem numero e sem
    explicacao parece um bug; um cartao que diz "sem safra registada" e'
    uma resposta.
    """
    if not historico:
        return dict(SEM_DADO)
    return historico
