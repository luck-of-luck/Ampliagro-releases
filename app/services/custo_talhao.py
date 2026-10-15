"""Orcado x realizado por talhao.

O Ampliagro tem as QUATRO entradas que esta conta exige - e nao tinha a conta.
O que existia (`h_lucro_talhao` em `app/ia/intents3.py`) era um ranking com
tres defeitos que mexem em dinheiro:

1. **Contava despesa nao paga como custo.** Filtrava so por `tipo`, ignorando
   `pago`. Um boleto que o produtor ainda nao quitou aparece como se ja tivesse
   custado dinheiro. O LCDPR e' de regime de caixa (`app/services/lcdpr.py`
   escreve Q100 a partir de `data_pagamento`), e a conta de custo tem de falar a
   mesma lingua - senao o produtor compara um numero de caixa com um numero de
   regime de competencia e nao sabe qual dos dois esta errado.

2. **Descartava a despesa sem talhao.** `filter(talhao=t)` salta tudo o que tem
   `talhao=None` (combustivel, frete,mao-de-obra). O lucro por talhao
   saia inflado e nenhum aviso: o dinheiro simplesmente sumiu do racio. Um
   produtor que reconcile o extrato com a tela ve a diferenca e perde a
   confianca na tela.

3. **N+1.** Um `aggregate()` por talhao dentro do `for`. Com 60 talhoes sao 121
   consultas para um numero que cabe em uma.

O que este modulo NAO faz, por desenho:

- **Nao rateia nada.** Despesa sem talhao fica visivel como `nao_alocado`, com o
  valor e o motivo. Distribuir por area seria inventar o destino do dinheiro, e
  um custo atribuido ao talhao errado produz uma decisao agronomica errada.
- **Nao estima o que nao foi registado.** Sem `orcamento_estimado` a coluna do
  orcado vem `None`, e `None` renderiza como "--", nunca como 0. Zero e' um
  orcado de zero; ausencia de orcado e' ausencia de orcado - sao coisas
  diferentes e o produtor precisa de ver a diferenca.
- **Nao inventa area.** Talhao sem `area_hectare` nao recebe R$/ha.

Todos os valores monetarios sao `Decimal` ate ao fim. Este modulo nao devolve um
unico `float`: `(0.1 + 0.2)` em dinheiro e' a razao classica de um relatorio
nao bater com o extrato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum

ZERO = Decimal("0")

# Um lancamento so conta como custo quando o dinheiro saiu. `PAGO` e' o regime do
# LCDPR; `COMPROMETIDO` e' o que ficou por pagar e por isso NAO entra no
# realizado, mas tambem nao desaparece - vai para a coluna ao lado.
PAGO = "pago"
COMPROMETIDO = "comprometido"


@dataclass(frozen=True)
class LinhaCusto:
    """Uma linha do quadro de orcado x realizado.

    `orcado` e `None` quando nao ha orcado registado. A distincao entre `None`
    e `0` atravessa toda a dataclass de proposito.
    """

    talhao_id: int
    talhao: str
    area_ha: Decimal | None
    orcado: Decimal | None
    receita_orcada: Decimal | None
    realizado_receita: Decimal
    realizado_despesa: Decimal
    comprometido_despesa: Decimal
    despesas_com_registro: int
    receitas_com_registro: int
    talhao_vazio: bool = False

    # --- derivados -------------------------------------------------------
    @property
    def lucro_orcado(self) -> Decimal | None:
        if self.receita_orcada is None or self.orcado is None:
            return None
        return self.receita_orcada - self.orcado

    @property
    def lucro_realizado(self) -> Decimal:
        return self.realizado_receita - self.realizado_despesa

    @property
    def desvio(self) -> Decimal | None:
        """Realizado menos orcado. Positivo = gastou mais do que planeou."""
        if self.orcado is None:
            return None
        return self.realizado_despesa - self.orcado

    @property
    def desvio_pct(self) -> Decimal | None:
        if not self.orcado:
            return None
        return (self.desvio / self.orcado * 100).quantize(Decimal("0.01"))

    @property
    def custo_por_ha(self) -> Decimal | None:
        if not self.area_ha:
            return None
        return (self.realizado_despesa / self.area_ha).quantize(Decimal("0.01"))

    @property
    def lucro_por_ha(self) -> Decimal | None:
        if not self.area_ha:
            return None
        return (self.lucro_realizado / self.area_ha).quantize(Decimal("0.01"))

    @property
    def tem_dados(self) -> bool:
        return bool(self.receitas_com_registro or self.despesas_com_registro)

    def as_dict(self) -> dict[str, Any]:
        """Serializavel. `None` sobrevive como `None` - nunca vira 0."""
        return {
            "talhao_id": self.talhao_id,
            "talhao": self.talhao,
            "area_ha": _json(self.area_ha),
            "orcado": _json(self.orcado),
            "receita_orcada": _json(self.receita_orcada),
            "lucro_orcado": _json(self.lucro_orcado),
            "realizado_receita": _json(self.realizado_receita),
            "realizado_despesa": _json(self.realizado_despesa),
            "comprometido_despesa": _json(self.comprometido_despesa),
            "lucro_realizado": _json(self.lucro_realizado),
            "desvio": _json(self.desvio),
            "desvio_pct": _json(self.desvio_pct),
            "custo_por_ha": _json(self.custo_por_ha),
            "lucro_por_ha": _json(self.lucro_por_ha),
            "despesas_com_registro": self.despesas_com_registro,
            "receitas_com_registro": self.receitas_com_registro,
            "tem_dados": self.tem_dados,
        }


@dataclass
class ResultadoCusto:
    linhas: list[LinhaCusto] = field(default_factory=list)
    nao_alocado_receita: Decimal = ZERO
    nao_alocado_despesa: Decimal = ZERO
    nao_alocado_registros: int = 0
    ano: int | None = None

    @property
    def total_receita(self) -> Decimal:
        return sum((l.realizado_receita for l in self.linhas), ZERO)

    @property
    def total_despesa(self) -> Decimal:
        return sum((l.realizado_despesa for l in self.linhas), ZERO)

    @property
    def area_total(self) -> Decimal:
        return sum((l.area_ha for l in self.linhas if l.area_ha), ZERO)

    @property
    def lucro_total(self) -> Decimal:
        return self.total_receita - self.total_despesa

    @property
    def lucro_por_ha(self) -> Decimal | None:
        if not self.area_total:
            return None
        return (self.lucro_total / self.area_total).quantize(Decimal("0.01"))

    @property
    def tem_dados(self) -> bool:
        return any(l.tem_dados for l in self.linhas) or self.nao_alocado_registros > 0

    @property
    def talhoes_sem_lancamento(self) -> list[str]:
        return [l.talhao for l in self.linhas if not l.tem_dados]

    def por_ordem_de_custo(self) -> list[LinhaCusto]:
        """Pior primeiro: quem mais consumiu. `None` vai para o fim - um talhao
        sem area e' um dado incompleto, nao 'o mais barato'."""
        return sorted(
            self.linhas,
            key=lambda l: (l.custo_por_ha is None, -(l.custo_por_ha or ZERO)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "ano": self.ano,
            "linhas": [l.as_dict() for l in self.linhas],
            "total_receita": _json(self.total_receita),
            "total_despesa": _json(self.total_despesa),
            "lucro_total": _json(self.lucro_total),
            "area_total": _json(self.area_total),
            "lucro_por_ha": _json(self.lucro_por_ha),
            "nao_alocado": {
                "receita": _json(self.nao_alocado_receita),
                "despesa": _json(self.nao_alocado_despesa),
                "registros": self.nao_alocado_registros,
            },
            "talhoes_sem_lancamento": self.talhoes_sem_lancamento,
            "tem_dados": self.tem_dados,
        }


def ordenar_por_lucro(resultado) -> list[LinhaCusto]:
    """Melhor primeiro: quem deu mais resultado.

    Este e' o ranking que responde a pergunta "qual talhao deu mais lucro".
    `ResultadoCusto.por_ordem_de_custo` responde a outra - "onde o dinheiro foi
    gasto". Sao duas perguntas differentes e nao produzem a mesma ordem: um
    talhao pequeno com muita receita ganha, um grande com pouca receita perde.
    O produto mostra as duas, com o nome certo por cima de cada lista.

    Funcao de modulo e nao metodo, e' propositado: `por_ordem_de_custo` e' um
    metodo da dataclass e chama-se `resultado.por_ordem_de_custo()`. Uma funcao
    de topo com o mesmo nome e' o caminho classico para alguém escrever
    `resultado.ordenar_por_lucro()` e levar `AttributeError` em producao. Sao
    nomes diferentes de proposito.

    `None` vai para o fim: um talhao sem area e' um dado incompleto, nao 'o mais
    rentavel'.
    """
    return sorted(
        resultado.linhas,
        key=lambda l: (l.lucro_por_ha is None, -(l.lucro_por_ha or ZERO)),
    )


def _json(valor):
    """`Decimal` -> `float` so na fronteira do payload, e so uma vez.

    A conta inteira corre em `Decimal` - `(0.1 + 0.2)` em dinheiro e' a razao
    classica de um relatorio nao bater com o extrato. Mas o contrato deste
    payload e' JSON e `json.dumps` nao conhece `Decimal`. Medido em
    2026-10-05: `Lote3IntentsTest::test_109_lucro_talhao` rebentava com
    `TypeError: Object of type Decimal is not JSON serializable` no momento em
    que o `as_dict` comecou a devolver o quadro completo.

    A conversao fica entao no limite. O texto que o produtor le e' formatado a
    partir do `Decimal`, nao deste float - logo o numero que ele ve no texto nao
    passa por esta conversao.
    """
    if valor is None:
        return None
    return float(valor)


def _talhoes_do_usuario(user, propriedade=None):
    from app.models import Talhao

    qs = Talhao.objects.filter(propriedade__user=user, ativo=True)
    if propriedade:
        qs = qs.filter(propriedade=propriedade)
    return qs.order_by("nome", "id")


def custo_por_talhao(user, propriedade=None, ano=None) -> ResultadoCusto:
    """Monta o quadro orcado x realizado.

    Tres consultas, independente do numero de talhoes. Antes eram
    `2 * len(talhoes) + 1`.
    """
    from app.models import LancamentoFinanceiro

    talhoes = list(_talhoes_do_usuario(user, propriedade))
    resultado = ResultadoCusto(ano=ano)
    if not talhoes:
        return resultado

    base = LancamentoFinanceiro.objects.filter(propriedade__user=user)
    if propriedade:
        base = base.filter(propriedade=propriedade)
    if ano:
        base = base.filter(data__year=ano)

    # --- 1. realizado, agrupado em uma query ----------------------------
    # `pago=True` e' o filtro que decide o que e' custo. Repare no par
    # `Count("id", filter=Q(pago=True))`: a contagem e' do MESMO conjunto que
    # o dinheiro, senao "3 despesas" contaria tambem as Comprometidas e o
    #  nao fecharia com a coluna ao lado.
    por_talhao = (
        base.filter(talhao__isnull=False)
        .values("talhao_id")
        .annotate(
            rec=Sum("valor", filter=Q(tipo="RECEITA", pago=True)),
            des=Sum("valor", filter=Q(tipo="DESPESA", pago=True)),
            comp=Sum("valor", filter=Q(tipo="DESPESA", pago=False)),
            n_rec=Sum(1, filter=Q(tipo="RECEITA", pago=True)),
            n_des=Sum(1, filter=Q(tipo="DESPESA", pago=True)),
        )
    )
    agregado = {l["talhao_id"]: l for l in por_talhao}

    # --- 2. o que nao esta alocado a nenhum talhao ------------------------
    sem_talhao = base.filter(talhao__isnull=True).aggregate(
        rec=Sum("valor", filter=Q(tipo="RECEITA", pago=True)),
        des=Sum("valor", filter=Q(tipo="DESPESA", pago=True)),
        n=Sum(1),
    )
    resultado.nao_alocado_receita = sem_talhao["rec"] or ZERO
    resultado.nao_alocado_despesa = sem_talhao["des"] or ZERO
    resultado.nao_alocado_registros = sem_talhao["n"] or 0

    # --- 3. orcado, por safra --------------------------------------------
    # O orcado vive no PlanoSafra. Um talhao sem plano e' um talhao sem
    # orcado - e a celula fica None. Nao se divide aiquid, nao se projeta.
    orcados = _orcamentos_por_talhao(user, propriedade, ano)

    for t in talhoes:
        agg = agregado.get(t.id, {})
        orc = orcados.get(t.id)
        resultado.linhas.append(
            LinhaCusto(
                talhao_id=t.id,
                talhao=t.nome,
                area_ha=t.area_hectare if t.area_hectare else None,
                orcado=orc["custo"] if orc else None,
                receita_orcada=orc["receita"] if orc else None,
                realizado_receita=agg.get("rec") or ZERO,
                realizado_despesa=agg.get("des") or ZERO,
                comprometido_despesa=agg.get("comp") or ZERO,
                despesas_com_registro=agg.get("n_des") or 0,
                receitas_com_registro=agg.get("n_rec") or 0,
                talhao_vazio=orc["vazio"] if orc else False,
            )
        )

    return resultado


def _orcamentos_por_talhao(user, propriedade, ano):
    """Orcado por talhao, vindo do PlanoSafra.

    Duas fontes, nesta ordem de autoridade:
      - `PlanoSafra.orcamento_estimado` - o orcadado do plano;
      - `AtividadePlanejada.custo_estimado` - a soma das atividades, quando nao
        ha valor de plano.

    Soma-las seria contar a mesma.activity duas vezes.
    """
    from app.models import Safra

    safras = Safra.objects.filter(propriedade__user=user)
    if propriedade:
        safras = safras.filter(propriedade=propriedade)
    if ano:
        safras = safras.filter(ano=ano)
    safras = safras.select_related("talhao")

    mapa: dict[int, dict[str, Any]] = {}

    def _slot(talhao_id):
        return mapa.setdefault(
            talhao_id,
            {"custo": None, "receita": None, "vazio": False, "atividades": ZERO},
        )

    for s in safras:
        if not s.talhao_id:
            continue
        slot = _slot(s.talhao_id)
        # `is not None`, nao truthiness: `Decimal("0")` e' falsy, e receita
        # estimada em zero e' um orcado - "vendi a preco de equilibrio" -,
        # nao a ausencia de uma estimativa. `if s.receita_estimada:` apagava
        # o zero e o talhao aparecia como "sem orcado de receita".
        if s.receita_estimada is not None:
            slot["receita"] = s.receita_estimada

    # Atividades planejadas: uma query so, filtrada pelas safras que interessam.
    ids = [s.id for s in safras if s.talhao_id]
    if ids:
        from app.models import AtividadePlanejada, PlanoSafra

        for p in PlanoSafra.objects.filter(safra_id__in=ids):
            # Mesmo motivo da receita: `Decimal("0")` e' falsy. O guard `if
            # p.orcamento_estimado:` descartava o orcado zero e o talhao
            # aparecia como "sem orcado" - que e' a leitura oposta da
            # verdade. A coluna e' NOT NULL, entao um plano que existe SEMPRE
            # tem um numero; nao ha caso em que o `if` devesse proteger
            # alguma coisa.
            if p.orcamento_estimado is not None:
                slot = _slot(p.safra.talhao_id)
                slot["custo"] = p.orcamento_estimado
            # O valor da atividade e' o fallback quando o plano nao tem orcado.
            total_at = (
                AtividadePlanejada.objects.filter(plano_id=p.id).aggregate(
                    s=Sum("custo_estimado")
                )["s"]
                or ZERO
            )
            if total_at:
                slot = _slot(p.safra.talhao_id)
                slot["atividades"] = slot["atividades"] + total_at

    # O plano manda; a soma das atividades so entra se o plano foi silencioso.
    for slot in mapa.values():
        if slot["custo"] is None and slot["atividades"]:
            slot["custo"] = slot["atividades"]
        if slot["custo"] is None and slot["receita"] is None:
            slot["vazio"] = True

    return mapa


def resumo_para_ia(resultado: ResultadoCusto, limite: int = 6) -> str:
    """Texto curto para a IA. Diz o que falta, nao so o que ha.

    O texto e' a resposta ao intent `lucro_talhao` - therefore mostra **lucro**,
    ordenado por lucro por hectare. A conta de custo por hectare vive no
    `ResultadoCusto.as_dict()`, que a tela consome. Ouvi-me dizer "o talhao X
    deu mais lucro" e responder com o custo porque a funcao que construi chamei
    `resumo_para_ia` e sobrei a partir de `por_ordem_de_custo`: o produtor
    perguntava por ganho e recebia por gasto, e os dois numeros podem apontar
    para talhoes opostos.
    """
    if not resultado.tem_dados:
        return (
            "Sem lançamentos vinculados a talhão — vincule receitas/despesas ao "
            "talhão para ver o custo por área."
        )

    if resultado.nao_alocado_registros and not any(
        l.tem_dados for l in resultado.linhas
    ):
        # Money exists and is real - it just has no talhao. Saying "no data"
        # here would hide a spend the producer can see on the bank statement.
        return (
            f"Há {resultado.nao_alocado_registros} lançamento(s) na fazenda "
            f"(R$ {resultado.nao_alocado_despesa:,.2f} em despesa), mas nenhum "
            "está vinculado a um talhão — sem isso não dá para dizer o custo "
            "de nenhum deles. Vincule os lançamentos ao talhão na ficha "
            "financeira."
        )

    com_lucro = [l for l in ordenar_por_lucro(resultado) if l.tem_dados][:limite]
    if not com_lucro:
        return (
            "Há lançamentos na fazenda mas nenhum vinculado a um talhão, "
            "então não dá para dizer o lucro de nenhum deles."
        )

    partes = []
    for l in com_lucro:
        bits = [f"lucro R$ {l.lucro_realizado:,.2f}"]
        if l.lucro_por_ha is not None:
            bits.append(f"R$ {l.lucro_por_ha:,.2f}/ha")
        if l.desvio is not None:
            sinal = "+" if l.desvio > 0 else ""
            bits.append(
                f"{sinal}{l.desvio_pct:,.1f}% do orçamento "
                f"(R$ {l.realizado_despesa:,.2f} gasto)"
            )
        partes.append(f"{l.talhao} ({', '.join(bits)})")

    texto = (
        f"Lucro por talhão, de {resultado.lucro_total:,.2f} no total "
        f"({resultado.area_total:,.2f} ha): " + "; ".join(partes) + "."
    )

    if resultado.nao_alocado_registros:
        texto += (
            f" R$ {resultado.nao_alocado_despesa:,.2f} de despesa não está "
            "vinculada a nenhum talhão, portanto não entra nesta conta."
        )
    sem = resultado.talhoes_sem_lancamento
    if sem:
        txt = ", ".join(sem[:4]) + ("…" if len(sem) > 4 else "")
        texto += f" Sem lançamento: {txt}."
    return texto
