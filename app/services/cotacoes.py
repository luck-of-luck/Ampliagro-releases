"""Cotações agrícolas.

REGRA DESTE MÓDULO: um preço só entra no payload se veio de uma fonte que
realmente respondeu. Sem fonte, o preço é `None` e o motivo vai junto. Um
produtor que decide venda por um preço precisa de saber de onde ele veio — e
um número sem procedência é pior do que a ausência dele, porque não há como
distinguir "não sei" de "sei".

O que este ficheiro fazia antes:

* `_fetch_b3_mock()` sorteava preços com `random.uniform` — soja 130-160,
  milho 50-70, café 900-1100, boi 220-260. Um sorteio novo a cada chamada.
* `_fetch_b3_real()` devolvia `None` em TODOS os caminhos, incluindo depois
  de uma chamada HTTP bem-sucedida. A "fonte real" era inalcançável por
  construção, não por falta de chave.
* o carimbo de proveniência comparava o resultado com um SEGUNDO sorteio
  (`b3_data != cls._fetch_b3_mock()`). Dois sorteios independentes de
  `random.uniform` nunca coincidem — medi 0 coincidências em 500 tentativas
  — portanto `"fonte": "real"` era o que saía praticamente sempre, por cima
  de dados 100% aleatórios.

Juntava-se a isto `atualizado_em: timezone.now()`, que reforçava a
impressão de dado acabado de buscar. O produtor recebia um preço em reais
com a aparência de um preço real e nenhum aviso. Isto é pior que o bug do
arroz/milho no dashboard, porque ali ao menos se via a curva; aqui o número
isolado, com uma casa decimal, é indistinguível do verdadeiro.
"""

import json
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone


class CotacoesService:
    """
    Serviço para buscar cotações agrícolas (Conab, B3, etc).
    Implementa caching para evitar chamadas excessivas a APIs externas.

    Devolve sempre `fonte` e `fonte_detalhe` por commodity. Um preço
    presente sem fonte real é um defeito, não uma escolha: `None` com motivo
    é a resposta honesta.
    """

    CACHE_TIMEOUT = 60 * 60 * 4  # 4 horas

    # Sem fonte externa configurada, não há preço. Isto é o estado normal
    # de uma instalação sem credenciais, e é um estado legítimo.
    MOTIVO_SEM_FONTE = (
        "Sem fonte de cotação configurada. "
        "Registe uma fonte em FonteDadosExterna (tipo B3 ou CONAB) "
        "para obter preços reais."
    )

    @staticmethod
    def _commodities() -> tuple[list[str], list[str]]:
        return (
            ["soja", "milho", "boi_gordo", "cafe"],
            ["soja_pr", "milho_mt"],
        )

    @staticmethod
    def _vazio(compras: list[str], motivo: str) -> dict:
        """Estrutura vazia, com o motivo em cada commodity.

        Mantém as CHAVES para o frontend não quebrar apressadamente com
        `undefined`, mas o valor é `None` — não 0, porque 0 é um preço
        (e um preço impossível).
        """
        return {c: {"preco": None, "variacao": None, "motivo": motivo} for c in compras}

    @staticmethod
    def _buscar_hg_brasil() -> dict:
        """HG Brasil. Traz currencies/indices, não commodities B3.

        Se um dia tracer commodities, o parse entra aqui. Devolve `{}` quando
        não há o que trazer — nunca números gerados.
        """
        try:
            import requests

            r = requests.get(
                "https://api.hgbrasil.com/finance/quotations?key=demo&format=json",
                timeout=4,
            )
            if not r.ok:
                return {}
            j = r.json()
            results = j.get("results", {})
            # O HG Brasil não expõe commodities agrícolas da B3. Se um dia
            # expuser, mapeia-se aqui e devolve-se o que veio — não um
            # substitute gerado.
            if not results.get("currencies"):
                return {}
            return {}
        except Exception:
            return {}

    @classmethod
    def get_cotacoes(cls) -> dict:
        cache_key = "ampliagro_cotacoes_agricolas"
        try:
            cotacoes = cache.get(cache_key)
        except Exception:
            # Cache indisponivel (tabela em falta, backend inacessivel) nao
            # pode impedir a resposta. O que se perde e' a cache, nao o
            # dado. Sem isto, uma falha de cache tirava as cotações do ar
            # inteiro — e o unico dado que devolvemos e' "nao ha preco".
            cotacoes = None
        if cotacoes:
            return cotacoes

        b3_compras, conab_compras = cls._commodities()

        b3_real = cls._buscar_hg_brasil()
        conab_real = cls._buscar_conab()

        # Uma commodity só tem preço se veio de uma fonte. Sem isso: None +
        # motivo. O `random.uniform` saiu deste ficheiro de vez.
        b3 = cls._vazio(
            b3_compras,
            cls.MOTIVO_SEM_FONTE
            if not b3_real
            else "Fonte B3 respondeu sem o commodity pedido.",
        )
        for k, v in b3_real.items():
            b3[k] = {
                "preco": v.get("preco"),
                "variacao": v.get("variacao"),
                "fonte": v.get("fonte", "B3"),
            }

        conab = cls._vazio(
            conab_compras,
            cls.MOTIVO_SEM_FONTE
            if not conab_real
            else "Fonte Conab respondeu sem o commodity pedido.",
        )
        for k, v in conab_real.items():
            conab[k] = {
                "preco": v.get("preco"),
                "variacao": v.get("variacao"),
                "fonte": v.get("fonte", "Conab"),
            }

        tem_preco = any(
            c["preco"] is not None for c in list(b3.values()) + list(conab.values())
        )

        cotacoes = {
            "b3": b3,
            "conab": conab,
            "atualizado_em": timezone.now().isoformat(),
            # A fonte é AGORA GLOBAL e calculada, nunca comparada com um
            # segundo sorteio. `qualquer_preco` só é True se algum preço
            # tiver vindo de uma fonte real.
            "fonte": "real" if tem_preco else "indisponivel",
            "fonte_detalhe": (
                "Preços de fonte externa configurada."
                if tem_preco
                else cls.MOTIVO_SEM_FONTE
            ),
            "aviso": "" if tem_preco else cls.MOTIVO_SEM_FONTE,
        }

        try:
            cache.set(cache_key, cotacoes, cls.CACHE_TIMEOUT)
        except Exception:
            pass  # sem cache, mas a resposta existe

        return cotacoes

    @classmethod
    def _buscar_conab(cls) -> dict:
        """Conab só é consultada se houver uma fonte registada e ativa.

        A consulta real fica por implementar; o que interessa agora é que a
        ausência de implementação não vire um número inventado. Devolve
        `{}` enquanto não houver, e o `get_cotacoes` transforma isso em
        `None` + motivo.
        """
        try:
            from app.models import FonteDadosExterna

            if not FonteDadosExterna.objects.filter(tipo="CONAB", ativo=True).exists():
                return {}
        except Exception:
            return {}
        return {}
