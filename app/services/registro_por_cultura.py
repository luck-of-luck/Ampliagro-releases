"""O registo observado nas guias ANIMAL e AQUATICA.

POR QUE UM SERVICO SEPARADO, E NAO O `historico_cultura`
========================================================
`app/services/historico_cultura.py` conta **ciclos**: dias entre plantio e
colheita, tirados de `app_safra`. Isso e' agricultura anual, e so faz sentido
para planta.

Um boi nao tem ciclo de plantio. Tem **lactacao** (305 dias), **gestacao**
(283 dias), **idade de abate**. Aplicar o ciclo de safras a um cartao de
gado e' escrever "128 dias" num bovino — e uma affirmacao falsa com a
minha propria assinatura. Por isso um servico aparte, com metricas que
façam sentido para cada tipo.

O QUE A GUIA ANIMAL PODE MOSTRAR, E O QUE TEM
==============================================
MEDIDO 2026-10-05 em `db.sqlite3`:

    app_registroproducao     66 linhas, 16 colunas
      por grupo: graos 25, vegetal 17, animal 7, aquatica 1, ...

    os 8 registos de animal/aquatica, com a PONTE preenchida:

        Ayrshire        cultura_id=28533   (Cultura.grupo = bovinos)
        Angus           cultura_id=28548   (bovinos)
        Bezerro         cultura_id=28554   (bovinos)
        Bonsmara        cultura_id=28543   (bovinos)
        Santa-Gertrudis cultura_id=28544   (bovinos)
        Tilápia         cultura_id=28709   (peixes)

**`cultura_id` esta preenchido em 100% dos registos.** A ponte existe e
funciona. `status` tambem (66/66), que permite contar os activos.

O CRITERIO ERRADO, E' O MESMO DE SEMPRE
========================================
A guia animal filtra `Cultura.grupo IN ('bovinos', 'suinos', ...)`, e o
`RegistroProducao.grupo` do produtor e' `'animal'` — nao `'bovinos'`. Sao
duas colunas com nomes diferentes, e **nenhum codigo as liga**.

E' a MESMA classe de erro que o `icontains=""` de `guias.py` e que o `ciclo`
de 112 dias em vez de 116: **a busca foi feita pelo campo errado, e a
ausencia do resultado leu-se como "o produtor nao registou nada"**. Ele
registou 8 vezes. Este servico liga pelo `cultura_id`, que e' a chave que
existe de facto.

O QUE MOSTRA
============
Por cultura:

    registos   quantas vezes o produtor registou esta raca/especie
    activos    quantos desses estao com `status='ativo'`
    ultimo     a data mais recente

`quantidade` so aparece quando existe: e' 6 de 66 no total, e num cartao
de gado a quantidade e' **de que** — uni as, outro, peso, racao — e
depende do registo. Um numero solto sem unidade seria pior do que nada.
Por isso fica de fora.

AS MESMAS REGRAS DE HONESTIDADE
===============================
1. Sem registo -> `fonte: "sem_dado"` e **nunca 0**. A guia animal tem 41
   raças em `bovinos`; o produtor registou 5. As outras 36 mostram
   "registar", e nao "0 registos".
2. `status` desconhecido nao conta como activo nem como inactivo. Um
   registo com `status='?'` nao pode virar "1 activo".
3. Datas ilegiveis nao viram data. Uma data de registo e' um facto; uma
   data inventada e' um bug.
"""

from __future__ import annotations

from datetime import date

#: `status` que contam como activo. Qualquer OUTRO valor (incluido None) nao
#: conta nem para activos nem para inactivos — ver regra 2 do docstring.
STATUS_ACTIVO = "ativo"


def _data_de(valor):
    """`date` | `datetime` | "YYYY-MM-DD..." -> `str` "YYYY-MM-DD", ou None.

    Devolve a **string** e nao um `date`: o ecrã mostra, e um `date` sem
    timezone no contexto de um template mostra um formato dependente da
    locale do servidor — o mesmo dado com dois resultados em maquinas
    diferentes.

    VALIDA O CALENDARIO, e nao so o formato. `"2026-13-45"` tem os 10
    caracteres certos e nao existe como data; `"aaaa-bb-cc"` tambem. A
    primeira versao so testava o comprimento e devolvia as duas tal e
    qual. Um ecrã que mostra "2026-13-45" como "a ultima registo" e' pior
    do que um ecrã vazio: parece um dado e nao e'.
    """
    if valor is None or valor == "":
        return None
    try:
        if not isinstance(valor, str) and hasattr(valor, "date"):
            return valor.date().isoformat()
        if not isinstance(valor, str) and hasattr(valor, "isoformat"):
            return valor.isoformat()[:10]
        texto = str(valor).strip()
        if len(texto) < 10:
            return None
        # `datetime.date` levanta `ValueError` em "2026-13-45" e em
        # "aaaa-bb-cc" — e' o validador de calendario do proprio Python,
        # nao uma expressao regular feita a mao.
        return date(int(texto[0:4]), int(texto[5:7]), int(texto[8:10])).isoformat()
    except (ValueError, TypeError):
        return None


def registos_por_cultura(registos):
    """Conta registos por `cultura_id`, a partir de uma query ja filtrada.

    `registos` e' um iteravel de tuplos:

        (cultura_id, status, data_registro)

    Assim como `historico_por_cultura`, o **tenancy entra pelo filtro**: o
    servico recebe a query ja filtrada pelo `_middleware` de tenant. Um
    `propriedade_ids=None` opcional seria um filtro que alguem ia esquecer,
    e esquecer o tenant nao da erro — da o registo do vizinho.

    Devolve `{cultura_id: {...}}`. Toda a entrada tem `fonte`, `motivo` e
    `ultimo`, porque um numero sem origem declarada nao pode ser mostrado.
    """
    por_id = {}

    for linha in registos:
        cultura_id, status, data_registro = linha[:3]

        # registo sem `cultura_id` nao pertence a nenhuma ficha. Registar
        # sob `None` seria inventar uma cultura que o produtor nunca pediu.
        if not cultura_id:
            continue

        d = por_id.setdefault(
            cultura_id,
            {"total": 0, "activos": 0, "ultimo": None},
        )
        d["total"] += 1

        # regra 2: so `ativo` conta como activo. Um status desconhecido nao
        # vira activo nem inactivo — contamo-lo no total e_ready.
        if str(status or "").strip().lower() == STATUS_ACTIVO:
            d["activos"] += 1

        # regra 3: uma data ilegivel nao substitui uma data valida
        dt = _data_de(data_registro)
        if dt and (d["ultimo"] is None or dt > d["ultimo"]):
            d["ultimo"] = dt

    fora = {}
    for cultura_id, d in por_id.items():
        fora[cultura_id] = {
            "registos": d["total"],
            "activos": d["activos"],
            "ultimo": d["ultimo"],
            "fonte": "medido",
            "motivo": None,
        }
    return fora


#: O que um cartao mostra quando a cultura nao tem registo. `registos: 0`
#: **nao e' "o produtor fez zero registos"** — e' "nao ha registo". A
#: diferenca entre `0` e `None` e' o que separa um dado de uma affirmacao.
SEM_DADO = {
    "registos": 0,
    "activos": None,
    "ultimo": None,
    "fonte": "sem_dado",
    "motivo": "Nenhum registo de producao para esta cultura.",
}
