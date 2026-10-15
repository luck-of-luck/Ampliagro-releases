"""Reforma Tributária (IBS/CBS) — a estrutura sem os números inventados.

## O que é isto

O gap F05 da matriz 100×50. **Zero código no Ampliagro** — verifiquei:
zero ocorrências de `IBS`, `CBS`, `IBPTax` ou `reforma_tribut` em todo o
repositório. É um gap real, não um falso negativo.

E é o gap mais **datado** dos 50: a transição é 2026–2033, ou seja, **está a
começar agora**, e é obrigação legal — não é uma feature que se difer para
trás. Dois líderes na matriz já a têm. Um produtor que facturar em 2027 e não
consiguir emitir o imposto fica proibido de operar.

## O que este módulo NÃO faz, e porquê

**Não tem alíquotas.** Tentei ler a fonte oficial
(`gov.br/fazenda/pt-br/assuntos/reforma-tributaria`) e a página exige
autenticação. Sem a tabela oficial em mãos, qualquer número que eu escrevesse
seria **inventado** — e um índice tributário inventado é pior do que a
ausência: o produtor confia nele, paga errado, e o erro só aparece numa
fiscalização.

Por isso o contrato é:

- `AliquotaReforma` guarda a alíquota **com a fonte que a justifica**, e
  `fonte` é obrigatório. Uma linha sem fonte é um número sem dono.
- `calcular_ibs_cbs()` devolve `None` com `motivo` quando a alíquota não está
  carregada. **Nunca 0.** "Não tenho a tabela" e "o imposto é zero" são
  coisas diferentes, e confundir as duas aqui é o mesmo defeito do
  `deducoes` do DRE.
- O serviço **diz onde buscar a tabela**, não apenas que não a tem.

## Por que o sistema guarda a tabela em vez de a calcular

Porque a tabela muda (definição legal, com reductions por produto, e a
alíquota de teste é diferente da definitiva). Um `@staticmethod` com
`0.009` dentro do código é um número que alguém muda na SVN sem actualizar
nada, e o produtor vê um imposto errado sem nenhuma pista de porquê.

Guardar a tabela com `vigencia_inicio`/`vigencia_fim` faz com que o valor
usado seja sempre rastreável a uma data e a uma fonte — que é o que uma
fiscalização pede.

## O que falta para isto estar pronto

1. Carregar a tabela oficial (Receita Federal / Ministério da Fazenda), com a
   URL e a data de publicação em `fonte`.
2. Decidir o tratamento das **reduções** agro (alimentos, cesta básica) —
   isso é política fiscal e é decisão do produtor/contabilista, não do sistema.
3. Ligar a `NFe` emitida — hoje o `nfe_auto.py` é manual e não tem os campos
   de IBS/CBS do XML (que existem no grupo de Tributos do XML da NF-e).

Nada disto é código. É fonte e decisão.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q

from app.models.financeiro_reforma import AliquotaReforma, ItemTributario

# Onde a tabela oficial vive. Guardamos a referência para que o produtor
# possa buscar em vez de receber um número sem origem.
FONTE_TABELA_OFICIAL = (
    "Ministério da Fazenda / Receita Federal — tabela oficial de IBS e CBS "
    "(LC 214/2025 e alterações). Tabela oficial publicada em "
    "gov.br/fazenda; o acesso exige autenticação, por isso o Ampliagro não "
    "embute os valores."
)

MOTIVO_SEM_TABELA = (
    "A tabela oficial de IBS/CBS não está carregada. Busque-a em "
    "gov.br/fazenda e carregue com a fonte e a data de publicação — sem a "
    "fonte, a alíquota não entra."
)

# Convénios do grupo de Tributos da NF-e (tag `IBSCBS`, grupo 9906).
CONVENIOS_IBS = ("IBSV", "IBSC", "IBS")


def aliquota_vigente(codigo: str, quando: date | None = None) -> dict:
    """Alíquota de um tributo na data indicada, ou a ausência com motivo.

    Devolve sempre `valor`, `fonte` e `motivo` — a mesma forma dos factores de
    crédito, pela mesma razão: quem decide precisa de saber de onde veio o
    número, e "não sei" tem de ser distinguível de "zero".
    """
    quando = quando or date.today()
    linha = (
        AliquotaReforma.objects.filter(codigo=codigo)
        .filter(Q(vigencia_inicio__lte=quando) | Q(vigencia_inicio__isnull=True))
        .filter(Q(vigencia_fim__gte=quando) | Q(vigencia_fim__isnull=True))
        .order_by("-vigencia_inicio")
        .first()
    )

    # `fonte` em branco não é fonte. O campo é obrigatório no formulário, mas
    # campo obrigatório no formulário não impede `objects.create()` — e um
    # índice tributário sem dono é pior do que a ausência do índice. Por isso
    # se verifica aqui, e não se confia no campo.
    sem_fonte = linha is None or not (linha.fonte or "").strip()

    if linha is None or linha.aliquota is None or sem_fonte:
        return {
            "codigo": codigo,
            "valor": None,
            "unidade": None,
            "fonte": None,
            "motivo": MOTIVO_SEM_TABELA,
            "quando": quando,
        }

    return {
        "codigo": codigo,
        "valor": float(linha.aliquota) / 100.0,
        "unidade": "percentual",
        "fonte": linha.fonte,
        "motivo": None,
        "vigencia_inicio": linha.vigencia_inicio,
        "vigencia_fim": linha.vigencia_fim,
        "reducao_percentual": (
            float(linha.reducao_percentual) / 100.0
            if linha.reducao_percentual is not None
            else None
        ),
        "quando": quando,
    }


def calcular_ibs_cbs(base_calculo: Decimal, quando: date | None = None) -> dict:
    """IBS e CBS sobre uma base, com o que falta declarado.

    **A ordem importa e não é óbvia:** o CBS é calculado sobre a base, e o IBS
    também — mas ambos são *sobre a mesma base*, não um sobre o outro. Somar os
    dois ao valor da base é o cálculo correcto do imposto **da venda**, e não
    uma soma de taxes. (Isto não substitui a regra oficial de "por dentro",
    que o Ministério define por convénio — ver `MOTIVO_SEM_TABELA`.)

    Devolve `None` para o que não pode ser apurado. Um retorno com
    `ibs: 0.00` e `cbs: 0.00` seria uma afirmação fiscal falsa.
    """
    quando = quando or date.today()
    ibs = aliquota_vigente("IBS", quando)
    cbs = aliquota_vigente("CBS", quando)

    pode = ibs["valor"] is not None and cbs["valor"] is not None

    if pode:
        valor_ibs = float(base_calculo) * ibs["valor"]
        valor_cbs = float(base_calculo) * cbs["valor"]
        # Redução agro, se houver e se a alíquota a trouxer.
        for fat in (ibs, cbs):
            if fat.get("reducao_percentual"):
                pass  # a redução depende do item, não do tributo — ver nota abaixo
    else:
        valor_ibs = None
        valor_cbs = None

    return {
        "base_calculo": float(base_calculo),
        "quando": quando,
        "ibs": valor_ibs,
        "cbs": valor_cbs,
        "total": None
        if valor_ibs is None or valor_cbs is None
        else round(valor_ibs + valor_cbs, 2),
        # O imposto entra no preço, não se soma a ele. Separado para quem
        # separado do preço ao consumidor.
        "preco_com_imposto": None
        if valor_ibs is None or valor_cbs is None
        else round(float(base_calculo) + valor_ibs + valor_cbs, 2),
        "aliquotas": {"ibs": ibs, "cbs": cbs},
        "apuravel": pode,
        "motivo": None if pode else MOTIVO_SEM_TABELA,
        "reducao_agro": (
            "As reduções de alíquota para produtos agro dependem do item e do "
            "convénio (grupo 9906 da NF-e). Não são aplicadas aqui: aplicá-las "
            "sem o item classificado seria inventar uma redução."
        ),
    }


def itens_sem_classificacao(propriedade_id: int) -> list[dict]:
    """Itens de NF-e sem código de tributo — o que impede o imposto.

    Não é uma lista de "faltam": é a lista do que **não pode ser apurado**,
    que é o que o produtor tem de resolver. Um item sem NCM é um item cujo
    imposto ninguém sabe.
    """
    qs = ItemTributario.objects.filter(
        lancamento__propriedade_id=propriedade_id
    ).filter(Q(cbs_codigo="") | Q(cbs_codigo__isnull=True))

    return [
        {
            "lancamento_id": it.lancamento_id,
            "descricao": it.descricao,
            "ncm": it.ncm,
            "motivo": "item sem código de tributo (CBS) — imposto não apurável",
        }
        for it in qs.select_related("lancamento")
    ]
