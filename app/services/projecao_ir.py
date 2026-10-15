"""Projecao de IR ao longo do ano: quando o produtor vai pagar, mes a mes.

POR QUE ISTO E' A DIMENSAO QUE NINGUEM NICHADO RESPONDE
======================================================
MEDIDO 2026-10-05 (agente 3). A folha 100x50 diz, na coluna "porque conta
numa decisao de compra" de F17, uma frase que e' a especificacao inteira:

    "A Lucro Rural vende isto nomeadamente: 'vale comprar o trator agora?'"

E' essa a pergunta. **Nenhum** dos nichados a responde:

    Aegro / JetBov / iAgroSat    gesto animal, semano a semana
    TOTVS Agro / eCont Agro      resultado do EXERCICIO, fechado
    Lucro Rural                  risco de credito, nao calendario
    Sol Aguia / Agrosat          indice de vegetacao, nao caixa

Todos dizem "voce fechou o ano com lucro de R$ 240 mil". Nenhum diz "esse
lucro entra em marco, e em marco o IR desta Competencia e' R$ 18 mil". Um
ERP anual e' verdade e inutil para a decisao — a decisao e' sobre **quando**,
e o "quando" e' o que separates "comprar o trator" de "esperar por marco".

O QUE ESTE SERVICO **NAO** FAZ
==============================
- Nao e' umaECD. Nao assina, nao envia, nao substitui contador.
- Nao presume custo dedutivel. Um trator pode ser dedutivel em 35% ou em
  100%, conforme a ACTIVIDADE (Lei 8.587/95, art. 313, II, 'b'), e essa
  escolha e' do contador e da escritura. Este modulo **recebe** a percentagem
  como parametro e **exige-a**: nao a inventa, e nao assume 100%.
- Nao conhece inflacao, cambio, nem a receita trinitaria — que a reforma de
  2026 comeca a valer em 2027. A projecao e' do IR **vigente**, e diz.

A REGRA DE HONESTIDADE QUE DOMINA TUDO
======================================
    projecao com dado medido      -> o numero
    projecao sem dado suficiente -> `indeterminado`, e **diz o que falta**

Um "R$ 0 de imposto" quando nao ha lançamentos de despesa nao e' uma
projecao: e' a ausencia de medicaoVestida de numero. E o produtor que le
"zero" e compra o trator em novembro.

Isto nao e'， uma excentricidade. E' a mesma razao pela qual
`compliance_ambiental` devolve `indeterminado` em vez de assumir 20% de
Reserva Legal, e pela qual o `NotificacaoTemplate.canais` deixou de queimar
canais: **um numero que o sistema inventou custa dinheiro ao produtor**.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.models.financeiro import LancamentoFinanceiro

#: Faixas do IR de Pessoa Física para pessoa natural no Brasil, em vigor na
#: data desta medicao. Fonte: Lei 11.482/2007 (tabelaDp/Tabela A), com as
#: parcelas ate R$ 28.775,56 deduzidas do IRRF (Lei 9.430/1996, art. 3o, II).
#:
#: `(limite_supereior_ou_None, parcela_a_deduzir, aliquota)`
#:
#: `limite_supereior=None` marca a ultima faixa, que nao tem teto.
#:
#: Isto e' **dado legal codificado**, nao medicao. Codificar a lei num
#: ficheiro e' correcto e e' o que evita o bug da tabela unica; o que nao e'
#: correcto e fingir que o `IR` de 2026 e' o de 2027. `VIGENCIA` diz ate que
#: data este valor vale, e `projecao_ir` recusa-se a responder depois dela sem
#: que o produtor diga que actualizou.
#: Tabela de incidencia ANUAL de pessoas fisicas.
#:
#: Fonte oficial lida em 2026-10-05:
#: https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2026
#: ("Incidencia Anual - A partir do exercicio 2027").
#:
#: MEDIDO. Estes numeros estavam errados, todos. A primeira versao foi escrita
#: de memoria: as cinco deducoes estavam erradas e dois dos tetos nao eram os
#: da lei. Um teste com numero de referencia acusou a diferenca, e a leitura
#: da fonte oficial mostrou que NENHUM dos cinco valores estava certo.
#:
#: Um dado legal nao se escreve de memoria. Ou se le da fonte, ou o modulo
#: nao existe. E o mesmo principio de PERCENTUAL_RESERVA_LEGAL, que tambem
#: e dado legal codificado, e que pelo mesmo motivo tem a fonte escrita ao
#: lado.
#:
#: (teto_ou_None, deducao_ou_None, aliquota_ou_None); None na deducao marca
#: a faixa isenta.
FAIXAS_IR = (
    (Decimal("29145.60"), None, None),
    (Decimal("33919.80"), Decimal("2185.92"), Decimal("0.075")),
    (Decimal("45012.60"), Decimal("4729.91"), Decimal("0.150")),
    (Decimal("55976.16"), Decimal("8105.85"), Decimal("0.225")),
    (Decimal("59526.16"), Decimal("10904.66"), Decimal("0.275")),
    (None, Decimal("12424.28"), Decimal("0.275")),
)

#: Deducao por dependente. Lei 15.191/2025: R$ 189,59 por mes.
DEDUCAO_DEPENDENTE_MENSAL = Decimal("189.59")

#: Limite mensal do desconto simplificado, mesma lei.
DEDUCAO_SIMPLIFICADA_MENSAL = Decimal("607.20")

#: Tabela de REDUCAO da Lei 15.270/2025, que e o que decide o produtor
#: pequeno. Abaixo de R$ 5.000 por mes nao se paga nada; entre 5.000 e
#: 7.350 a reducao e linear; acima disso nao ha reducao.
#:
#: Sem esta lei, a projecao de um produtor que fatura R$ 40 mil por ano
#: diria que paga imposto quando nao paga nada. Nao e erro de centavos:
#: e erro de 100%.
REDUCAO_ATE_ISENCAO = Decimal("5000.00")
REDUCAO_ATE_ZERO = Decimal("7350.00")
REDUCAO_COEFICIENTE = Decimal("0.133145")
REDUCAO_CONSTANTE = Decimal("978.62")

#: Ate que data a tabela acima e' a vigente. A reforma tributaria (IBS/CBS,
#: Lei Complementar 214/2025) comeca em 2026 com a **transicao** do imposto
#: sobre a renda, e o IR passa a ser permanentemente reduzido a zero ate
#: 2033. Ou seja: **esta tabela envelhece**, e e' melhor que envelheça com uma
#: data escrita do que sem ela.
VIGENCIA = "2026-12-31"

MESES = (
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)

CENTIMO = Decimal("0.01")


def _c(x) -> Decimal:
    """Arredonda a centimos, `ROUND_HALF_UP`, para nao perder meio centimo
    em direccao errada. `Decimal` e' obrigatorio: `0.075 * 100` em `float` da
    `7.499999999999999`, e um imposto com esse erro paga-se com o produtor."""
    return Decimal(x).quantize(CENTIMO, rounding=ROUND_HALF_UP)


@dataclass
class Mes:
    """Um mes da projecao. Campos `None` significam **nao medido**.

    `lancamentos` sao os `(id, valor)` das DESPESAS do mes. A deduibilidade e'
    por lancamento e nao por total — um onus a 35% e uma despesa a 100% nao se
    cancelam — entao o par precisa de sobreviver a agrupamento.

    MEDIDO: este campo foi acrescentado depois de o ruff acusar
    `B009`/`B010` num `setattr`/`getattr` com nome constante. O remendo
    funcionava, mas escondia um campo que existe em runtime e nao existe na
    classe. Quem tipear contra `Mes` via-o agora.
    """

    mes: str
    receita: Decimal = Decimal("0")
    despesa: Decimal = Decimal("0")
    #: Receitas do mes que o produtor **declara** que nao foram facturadas.
    conjectural: Decimal = Decimal("0")
    #: `(id, valor)` das despesas do mes.
    lancamentos: list[tuple[int, Decimal]] = field(default_factory=list)

    @property
    def resultado(self) -> Decimal:
        return self.receita - self.despesa

    def para_dict(self) -> dict:
        return {
            "mes": self.mes,
            "receita_ha": float(_c(self.receita)),
            "despesa_ha": float(_c(self.despesa)),
            "resultado_ha": float(_c(self.resultado)),
            "receita_conjectural_ha": float(_c(self.conjectural)),
        }


@dataclass
class Projecao:
    """O resultado. `bloqueios` e' a parte que impede o produtor de ler um
    numero que nao pode ler."""

    meses: list[Mes] = field(default_factory=list)
    #: Percentagens dedutiveis que o contador deu, por lancamento. Vazio
    #: significa **nao dado** — nunca "tudo dedutivel".
    dedutiveis: dict[int, Decimal] = field(default_factory=dict)
    #: Contrato de deduibilidade assumed pelo produtor (ex.: trator 35%).
    #: `None` = nao informado, e o modulo NAO projeta nesse caso.
    percentual_dedutivel_padrao: Decimal | None = None
    ano: int = 0
    bloqueios: list[str] = field(default_factory=list)
    #: Rendimento tributavel **mensal** medio, para a reducao da Lei
    #: 15.270/2025. `None` = desconhecido, e entao a reducao nao se aplica.
    rendimento_mensal_medio: Decimal | None = None

    # ── o que o produtor precisa ───────────────────────────────────────────
    @property
    def receita_total(self) -> Decimal:
        return sum((m.receita for m in self.meses), Decimal("0"))

    @property
    def despesa_total(self) -> Decimal:
        return sum((m.despesa for m in self.meses), Decimal("0"))

    @property
    def despesa_dedutivel(self) -> Decimal | None:
        """`None` se nao ha contrato de deduibilidade. Nao `0`."""
        if self.percentual_dedutivel_padrao is None and not self.dedutiveis:
            return None
        total = Decimal("0")
        for m in self.meses:
            for lanc_id, valor in self._lancamentos_do_mes(m):
                pct = self.dedutiveis.get(lanc_id, self.percentual_dedutivel_padrao)
                if pct is None:
                    return None
                total += valor * pct
        return total

    def _lancamentos_do_mes(self, mes: Mes) -> Iterable[tuple[int, Decimal]]:
        yield from mes.lancamentos

    # ── o IR ──────────────────────────────────────────────────────────────
    def ir_do_mes(self, mes: Mes) -> Decimal | None:
        """Imposto de um mes isolado, ou `None` se nao se sabe.

        O IR incide sobre o resultado **acumulado do ano ate esse mes**, com a
        tabela progressiva aplicada a esse acumulado e as parcelas do proprio
        mes. E' este o calculo que responde a "vale comprar agora?": o trator
        de hoje abate a base *deste* mes, nao do ano que vem.

        Se o produtor fez uma perda, o imposto e' zero — e isso e' um
        **numero**, nao uma ausencia, porque a perda esta' medida.
        """
        dedutivel = self.despesa_dedutivel
        if dedutivel is None:
            return None
        # Confirma que o mes pedido existe antes de percorrer.
        if not any(m.mes == mes.mes for m in self.meses):  # pragma: no cover
            return None

        # A deducao e' por lancamento, nao sobre o total: um onus de 35%
        # e uma despesa de 100% nao se cancelam.
        base = Decimal("0")
        for m in self.meses:
            base += m.receita - m.conjectural
            for lanc_id, valor in self._lancamentos_do_mes(m):
                pct = self.dedutiveis.get(lanc_id, self.percentual_dedutivel_padrao)
                base -= valor * pct
            if m.mes == mes.mes:
                break
        if base <= 0:
            return Decimal("0.00")
        return calcular_ir(base, rendimento_mensal=self.rendimento_mensal_medio)

    def para_dict(self) -> dict:
        dedutivel = self.despesa_dedutivel
        linhas = []
        acumulado_receita = Decimal("0")
        acumulado_dedutivel = Decimal("0")
        for m in self.meses:
            acumulado_receita += m.receita
            if dedutivel is not None:
                acumulado_dedutivel += self._dedutivel_do_mes(m)
            ir_mes = self.ir_do_mes(m)
            d = m.para_dict()
            d["ir_do_mes"] = float(ir_mes) if ir_mes is not None else None
            d["ir_acumulado"] = (
                float(_c(acumulado_receita - acumulado_dedutivel))
                if dedutivel is not None
                else None
            )
            linhas.append(d)

        determinavel = dedutivel is not None and not self.bloqueios
        return {
            "ok": determinavel,
            "ano": self.ano,
            "base_do_ano": (
                float(_c(self.receita_total - dedutivel)) if determinavel else None
            ),
            "imposto_total_estimado": (
                float(
                    calcular_ir(
                        self.receita_total - dedutivel,
                        rendimento_mensal=self.rendimento_mensal_medio,
                    )
                )
                if determinavel
                else None
            ),
            "meses": linhas,
            "bloqueios": list(self.bloqueios),
            "fonte": "lancamentos registados na competencia, dedutibilidade "
            "declarada pelo contador",
            "aviso": (
                "Projecao, nao ECD. Nao substitui contador, e nao conhece "
                "definitivo,-checkbox nem plano decao. As faixas sao as "
                f"vigentes em {VIGENCIA}; a reforma comeca a mudar o "
                "imposto em 2027."
            ),
            "dedutibilidade": (
                "percentuais fornecidos" if dedutivel is not None else "NAO INFORMADA"
            ),
        }

    def _dedutivel_do_mes(self, mes: Mes) -> Decimal:
        total = Decimal("0")
        for lanc_id, valor in self._lancamentos_do_mes(mes):
            pct = self.dedutiveis.get(lanc_id, self.percentual_dedutivel_padrao)
            if pct is not None:
                total += valor * pct
        return total


def reducao_ir(rendimento_mensal: Decimal) -> Decimal:
    """Reducao do imposto, Lei 15.270/2025 (tabela de reducao mensal).

    Ate R$ 5.000 por mes o imposto e' **zero**. Entre 5.000 e 7.350 a reducao
    e' linear, e tem um **teto**: zera o imposto que ali incidiria. Acima de
    7.350 nao ha reducao nenhuma — o imposto e' o integral.

    Devolve quanto se desconta por mes, e **nunca negativo**.
    """
    if rendimento_mensal <= REDUCAO_ATE_ISENCAO:
        return Decimal("0.00")

    if rendimento_mensal <= REDUCAO_ATE_ZERO:
        bruto = REDUCAO_CONSTANTE - (REDUCAO_COEFICIENTE * rendimento_mensal)
        return max(Decimal("0.00"), _c(bruto))

    return Decimal("0.00")


def is_isento_por_reducao(rendimento_mensal: Decimal | None) -> bool | None:
    """O produtor esta na faixa de **isencao** da Lei 15.270/2025?

    MEDIDO 2026-10-05 (agente 3). Este `if` nao existia, e a sua falta dava o
    pior erro de todo o modulo: `reducao_ir()` devolve `0.00` em **dois**
    casos que significam o oposto,

        1. abaixo de R$ 5.000 por mes -> a lei ISENTA;
        2. acima de R$ 7.350 por mes -> a lei nao da REDUCAO.

    Eu tratava os dois com um `else: return 0.00`, e o caso 2 devolvia zero.
    Um produtor que fatura R$ 250 mil por ano a R$ 20.833 por mes recebia
    `imposto_com_reducao: 0.0` — **isento quem nao tem direito a isencao**.
    O sistema inventava um beneficio fiscal que a lei nao da, que e' o
    inverso do honesto.

    A distincao e' a **posicao na tabela**, nao o valor do redutor. E' a
    mesma classe do `compliance_ambiental` a trocar "20%" de um valor unico
    pela relacao entre biomas.

    Devolve `None` quando nao se sabe o rendimento: e' `None` e nao `False`,
    porque "nao sei" nao e' "nao tem".
    """
    if rendimento_mensal is None:
        return None
    return rendimento_mensal <= REDUCAO_ATE_ISENCAO


def calcular_ir(base: Decimal, *, rendimento_mensal: Decimal | None = None) -> Decimal:
    """Imposto sobre uma base anual, pela tabela progressiva oficial.

    Aplica a faixa da base, multiplica pela aliquota e subtrai a deducao da
    faixa. Sao as deducoes da Lei 9.430/1996, art. 3o, II, que tornam a
    progressao continua entre patamares.

    `rendimento_mensal` activa a tabela de reducao da Lei 15.270/2025, que e'
    **mensal**. Sem ele, a reducao nao pode ser aplicada — e o resultado
    devolvido e' a tabela anual sem a reducao, que e' o que este modulo
    devolve.

    Tres casos, e **nao** e' o mesmo quando o redutor da' 0.00:

        - abaixo de R$ 5.000 por mes: a lei ISENTA, o imposto e' zero;
        - entre 5.000 e 7.350: a reducao zera o imposto da faixa, com teto;
        - acima de 7.350: **nao ha reducao**, o imposto e' o integral.

    Ver `is_isento_por_reducao` para o porque de isto estar separado.
    """
    if base <= 0:
        return Decimal("0.00")

    isento = is_isento_por_reducao(rendimento_mensal)
    if isento is True:
        return Decimal("0.00")

    ano_redutor: Decimal | None = None
    if rendimento_mensal is not None and isento is False:
        redutor_mensal = reducao_ir(rendimento_mensal)
        if redutor_mensal > 0:
            ano_redutor = redutor_mensal * 12
        # `redutor == 0.00` **acima** de 7.350 significa "sem reducao", e
        # nao "isento": o imposto segue integral.

    for teto, deducao, aliquota in FAIXAS_IR:
        if aliquota is None:  # faixa isenta
            continue
        if teto is None or base <= teto:
            bruto = base * aliquota - (deducao or Decimal("0"))
            resultado = max(Decimal("0.00"), _c(bruto))
            if ano_redutor is not None:
                # teto: a reducao nunca produz imposto negativo
                resultado = max(Decimal("0.00"), _c(resultado - ano_redutor))
            return resultado

    raise AssertionError("FAIXAS_IR sem faixa aberta")  # pragma: no cover


def projetar_ir(
    *,
    propriedade_id: int,
    ano: int,
    percentual_dedutivel_padrao: Decimal | None = None,
    dedutiveis: dict[int, Decimal] | None = None,
    receita_conjectural: dict[str, Decimal] | None = None,
) -> Projecao:
    """Monta a projecao a partir dos lancamentos registados.

    Parametros
    ----------
    percentual_dedutivel_padrao:
        Percentagem dedutivel **declarada**, em `0..1`. `None` (o default) e'
        o caso honesto: sem este numero nao existe projecao, e o servico
        devolve `bloqueios` em vez de assumir 100%.

        Este default e' o ponto mais importante do modulo. `1.0` seria
        mais "util" e seria uma mentira: em staying a atividade principal o
        onus e' dedutivel em 35% (Lei 8.587/95, art. 313, II, b), e uma
       ulsao baseada em 100% subestima o imposto — o produtor compra o
        trator a pensar que vai pagar menos do que vai.

    dedutiveis:
        Por `id` de lancamento, para o caso de o onus nao seguir a regra
        geral. Tem precedencia sobre o padrao.

    receita_conjectural:
        Receita por nome de mes que o produtor **declara** que vai facturar
        e ainda nao lancou. Entra separada de `receita`, e nunca se junta a
        ela — porque e' receita que nao foi medida, so' prevista, e o
        produtor tem de ver essa diferenca antes de comprar o trator.
    """
    dedutiveis = dedutiveis or {}
    receita_conjectural = receita_conjectural or {}

    lancamentos = list(
        LancamentoFinanceiro.objects.filter(
            propriedade_id=propriedade_id,
            data__year=ano,
        )
        .only("id", "tipo", "valor", "data", "pago")
        .order_by("data", "id")
    )

    proj = Projecao(
        dedutiveis={int(k): Decimal(v) for k, v in dedutiveis.items()},
        percentual_dedutivel_padrao=(
            None
            if percentual_dedutivel_padrao is None
            else Decimal(percentual_dedutivel_padrao)
        ),
        ano=ano,
    )

    # ── agrupar por mes ────────────────────────────────────────────────────
    meses: dict[str, Mes] = {m: Mes(m) for m in MESES}
    por_mes_lanc: dict[str, list[tuple[int, Decimal]]] = {m: [] for m in MESES}

    for lanc in lancamentos:
        # `lanc.data` pode ser `date` ou `datetime`; `month` existe nos dois.
        chave = MESES[lanc.data.month - 1]
        mes = meses[chave]
        valor = Decimal(lanc.valor)
        if lanc.tipo == "RECEITA":
            mes.receita += valor
        else:
            mes.despesa += valor
            por_mes_lanc[chave].append((lanc.id, valor))
        # a conta dedutivel e' por lancamento: guarda o par
        if lanc.tipo != "RECEITA":
            mes.lancamentos.append((lanc.id, valor))

    for nome, valor in receita_conjectural.items():
        if nome in meses:
            meses[nome].conjectural += Decimal(valor)

    # `por_mes_lanc` e' o mesmo conteudo de `mes.lancamentos`, construido a
    # parte para nao ter de voltar a iterar os lancamentos.
    proj.meses = [meses[m] for m in MESES]

    # ── o que falta ───────────────────────────────────────────────────────
    if proj.percentual_dedutivel_padrao is None and not proj.dedutiveis:
        proj.bloqueios.append(
            "Nao foi informado o percentual dedutivel das despesas. Sem esse "
            "numero qualquer projecao seria inventada: o onus e' dedutivel "
            "em 35% (Lei 8.587/95, art. 313, II, 'b') e nao em 100%, e "
            "assumir 100% subestima o imposto. Pergunte ao contador."
        )
    if not lancamentos and not receita_conjectural:
        proj.bloqueios.append(
            "Nao ha lancamentos neste ano nem receita prevista declarada. "
            "Nao medido nao e' zero."
        )

    return proj
