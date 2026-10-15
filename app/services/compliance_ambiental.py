"""Conformidade ambiental: Reserva Legal por bioma, e o que se pode dizer.

POR QUE ESTE FICHEIRO EXISTE
===========================
MEDIDO 2026-10-05 (agente 7). `ComplianceAmbientalService` fixava
`percentual_exigido = 0.20` para **todos** os biomas, com um comentario que
admitia o problema:

    percentual_exigido = 0.20  # 20% regra geral
    # Se Amazônia = 0.80, Cerrado = 0.35, etc.

O resultado era um relatorio que **afirmava conformidade falsa**: uma
propriedade na Amazônia Legal com 20% de Reserva Legal era devolvida como
`"status_compliance": "Regular"`, quando a lei exige 80%.

Isto nao e' um detalhe de precisao. Em 2026 a conformidade ambiental deixou de
ser extra e virou **condicao de credito rural**:

- **Ibama Sistema Prisma** (Portaria 151/2026) cruza o CAR autodeclarado com
  bases geoespaciais e emite o "Relatorio de Indicadores de Integridade
  Ambiental", que os **bancos usam antes de liberar o credito**.
- **MapBiomas Monitor do Crédito Rural** cruza Sicor x CAR e marca
  `has_embargoed_areas`, `has_indigenous_lands`, `has_degradacao_alerta`.
- **Meu Imóvel Rural** (gov.br) tem a ferramenta "Tô em Dia?", que faz a
  pré-analise das pendências do **Manual de Crédito Rural**.

Ou seja: um "Regular" falso neste relatório pode custar um financiamento. E
um produtor que recebe "Regular" e descobre o problema na altura do
financiamento perde a confiança no sistema inteiro — que e' a moeda que este
repositório tenta não gastar.

A TABELA E A FONTE
==================
Percentuais de Reserva Legal por bioma, da Lei 12.727/2012 (art. 12-A, que
alterou a Lei 6.938/1981) e da Lei 13.835/2019:

    Amazônia        80%  (35% se a área estiver em Cerrado dentro da Amazônia Legal)
    Cerrado         20%
    Mata Atlântica  20%
    Caatinga        20%
    Pampa           20%
    Pantanal        20%
    (\"Outros\")      20%

IstO e' um **dado legal codificado**, nao uma medicao. Codificar a lei num
ficheiro e' correcto e e' o que evita o bug do 20% unico; o que nao e'
correcto e fingir que um calculo sobre area **declarada** pelo produtor e' uma
certificacao. Da a distincao, em `relatorio_compliance`.

O QUE ESTE MODULO **NAO** FAZ
=============================
- Nao consulta o CAR. Nao ha ligacao ao INCRA nem ao IBAMA
  (`grep sigef|sncr|ibama|mapbiomas` = 0 em `app/`), e um relatorio que
  fingisse cruzar com o CAR seria pior do que nenhum.
- Nao emite certificado. O Manual de Crédito Rural e' um documento do
 diz ao produtor, nao deste sistema.
- Nao assume o bioma. `Propriedade.bioma` e' `blank=True`; se estiver vazio, a
 percentagem exigida e' **desconhecida**, e o relatorio diz isso. Assumir 20%
  era o defeito original, so que com o nome certo.
"""

from decimal import Decimal

from app.models.core import AreaPreservacao, Propriedade

#: Percentual de Reserva Legal exigido, por bioma.
#:
#: Fonte: Lei 12.727/2012, art. 12-A (que alterou o art. 12 da Lei
#: 6.938/1981), acrescido da Lei 13.835/2019. Ver o docstring do modulo.
#:
#: `Decimal` e nao `float`: sao areas que se comparam com um limite legal, e
#: `0.8 - 0.79` em `float` pode dar `-1.1e-16` — um "deficit" de menos que
#: nada, num numero que vai para um relatorio de banco.
PERCENTUAL_RESERVA_LEGAL = {
    "amazonia": Decimal("0.80"),
    "cerrado": Decimal("0.20"),
    "mata_atlantica": Decimal("0.20"),
    "caatinga": Decimal("0.20"),
    "pampa": Decimal("0.20"),
    "pantanal": Decimal("0.20"),
}

#: Biomas da Amazônia Legal onde a RL e' 35% em vez de 80% (a área está
#: dentro da Amazônia Legal mas o bioma dominante é Cerrado).
PERCENTUAL_AMAZONIA_CERRADO = Decimal("0.35")

#: Rotulo humano do bioma, para o relatório. Vem das `choices` do modelo
#: (`app/models/core.py:9`), que e' a fonte, e nao uma copia — uma segunda
#: lista de biomas divergiria da primeira, e a divergencia seria silenciosa.
ROTULOS_BIOMA = dict(Propriedade._meta.get_field("bioma").choices)

#: Base legal dos percentuais da tabela. Constante e nao literal no corpo,
#: porque o corpo tem tres ramos de retorno e um literal repetido tres vezes
#: diverge no terceiro.
BASE_LEGAL = "Lei 12.727/2012 art. 12-A; Lei 13.835/2019"

#: O aviso que o relatorio nunca pode omitir. Constante pelo mesmo motivo: um
#: aviso ausente num dos ramos e' um ramo que mente **por omissao**, que e' a
#: forma de mentira mais difícil de apanhar porque o relatorio continua a
#: devolver 200 e todas as chaves presentes.
AVISO_CAR = (
    "Isto NAO e' uma certificacao do CAR e nao substitui o recibo do CAR, o "
    "CCIR nem a consulta ao Sistema Prisma do Ibama. O banco consulta essas "
    "fontes, nao este numero. Um 'regular' aqui pode nao ser um 'regular' la "
    "— e vice-versa. Para credito rural, consulte 'Tô em Dia?' em Meu Imovel "
    "Rural (gov.br)."
)


def percentual_exigido(bioma: str):
    """O percentual de Reserva Legal exigido, ou `None` se nao se sabe.

    Devolve `None` — e nao 20% — quando o bioma nao esta preenchido. `None` e
    "nao sabemos"; 0,20 seria "seamospapers que a maioria dos casos e' 20%",
    que e' exactamente o defeito que este modulo corrige.
    """
    if not bioma:
        return None
    return PERCENTUAL_RESERVA_LEGAL.get(str(bioma).strip().lower())


class ComplianceAmbientalService:
    """Conformidade ambiental a partir do que o produtor **declarou**.

    Nao e' certificacao. E' uma conta sobre areas declaradas, e diz-lo e' parte
    do resultado — porque o que o produtor declara pode divergir do CAR, e o
    CAR e' o que o banco consulta.
    """

    @classmethod
    def relatorio_compliance(cls, propriedade_id: int) -> dict:
        prop = Propriedade.objects.get(id=propriedade_id)

        bioma = (prop.bioma or "").strip().lower()
        exigido = percentual_exigido(bioma)

        area_total = Decimal(prop.area_total or 0)

        # ── Sem area declarada: nao ha conta para fazer ──────────────────
        if area_total <= 0:
            # ACHADO DO COMITE (agente 7, lente "contrato"): este ramo
            # devolvia 11 chaves e o ramo normal 15. Um consumidor que fizesse
            # `r["aviso"]` rebentava aqui, e nao la. Duas formas de resposta
            # num dicionario e' um contrato que ninguem pode satisfazer:
            # qualquer chave nova obriga a lembrar **deste** ramo.
            #
            # Por isso: as mesmas chaves, com `None` onde nao ha resposta. A
            # forma do contrato e' fixa; o conteudo e' que nao existe.
            return {
                "propriedade_id": prop.id,
                "status_compliance": "indeterminado",
                "motivo": (
                    "A propriedade nao tem area declarada. Sem area total nao "
                    "ha como calcular percentual de Reserva Legal."
                ),
                "bioma": bioma or None,
                "bioma_rotulo": ROTULOS_BIOMA.get(bioma) if bioma else None,
                "percentual_rl_atual": None,
                "percentual_rl_exigido": None,
                "area_total_ha": None,
                "area_reserva_legal_ha": None,
                "area_app_ha": None,
                "deficit_ha": None,
                # `None` e nao `False`: nem medimos APP, nem sabemos se
                # existe. `False` diria "medido, e nao ha" — que e' uma
                # afirmacao que este ramo nao pode fazer.
                "tem_app_declarada": None,
                "app_verificacao": (
                    "Nao verificavel: sem area declarada nao ha sobre o que "
                    "avaliar APP."
                ),
                "fonte": "autodeclarado pelo produtor",
                "certificado": False,
                "aviso": AVISO_CAR,
                "base_legal": BASE_LEGAL,
                "recomendacao": None,
                "percentuais_por_bioma": None,
            }

        # ── Sem bioma declarado: o limite legal e' desconhecido ───────────
        #
        # E' o caso que o codigo antigo tratava como 20%. Dizer "Regular"
        # sem saber o limite legal e' afirmar conformidade a partir de um
        # palpite — e o que o produtor levaria ao banco.
        if exigido is None:
            areas = cls._mede_areas(prop)
            base = {
                "propriedade_id": prop.id,
                "area_total_ha": float(area_total),
                "bioma": None,
                "bioma_rotulo": None,
                "percentual_rl_atual": None,
                "percentual_rl_exigido": None,
                "deficit_ha": None,
                "area_reserva_legal_ha": float(areas["area_reserva_legal_ha"]),
                "area_app_ha": float(areas["area_app_ha"]),
                "tem_app_declarada": areas["area_app_ha"] > 0,
                "app_verificacao": (
                    "APP declarada pelo produtor; a congruencia com a "
                    "geometria nao e' verificada por este relatorio."
                    if areas["area_app_ha"] > 0
                    else "APP nao declarada. Nao medido, e' diferente de medido "
                    "como zero."
                ),
                "fonte": "autodeclarado pelo produtor",
                "certificado": False,
                # Estas tres faltavam neste ramo. Sem elas, `r["aviso"]` — a
                # garantia de que isto nao e' uma certificacao — rebentava
                # aqui, e funcionava nos outros dois ramos. Um consumidor
                # nao pode ter de saber por que caminho chegou a resposta.
                "aviso": AVISO_CAR,
                "base_legal": BASE_LEGAL,
                "recomendacao": (
                    "Preencher o bioma da propriedade e' o unico passo que "
                    "falta para este relatorio passar a devolver um veredicto. "
                    "Sem ele nao ha limite legal com que comparar."
                ),
                "status_compliance": "indeterminado",
                "motivo": (
                    "A propriedade nao tem bioma declarado, e o percentual de "
                    "Reserva Legal exigido depende dele — e' 80% na Amazonia "
                    "e 20% nos restantes biomas. Preencher o bioma em Cadastro "
                    "› Propriedade e' o que torna esta verificacao possivel. "
                    "Sem isso, nenhum veredicto de conformidade e' honesto."
                ),
                "percentuais_por_bioma": {
                    ROTULOS_BIOMA.get(k, k): float(v * 100)
                    for k, v in PERCENTUAL_RESERVA_LEGAL.items()
                },
            }
            return base

        areas = cls._mede_areas(prop)
        # `Decimal` ate ao fim: a divisao e a subtraccao sao o calculo, e
        # `float / Decimal` levanta TypeError. A conversao para `float` e'
        # feita no dicionario de saida, e' para o JSON.
        area_rl = areas["area_reserva_legal_ha"]
        area_app = areas["area_app_ha"]

        atual = (area_rl / area_total) if area_total else Decimal("0")
        deficit_ha = Decimal("0")
        if atual < exigido:
            deficit_ha = (exigido * area_total - area_rl).quantize(Decimal("0.01"))

        # ── APP tambem conta para o veredicto ────────────────────────────
        #
        # ACHADO DO COMITE (agente 7, lentes "dependencias" e "testes",
        # independentemente): `area_app` era calculada, devolvida, e
        # **ignorada no status**. Uma propriedade com 80% de Reserva Legal e
        # zero APP saia "regular" — e APP degradada e' infracao ambiental por
        # si, independente da RL. O relatorio media e nao veredictava.
        #
        # Nao ha um "percentual exigido de APP" legal: a APP e' georregional
        # (margens de rio, topos, encostas), e depende da geometria. Por isso
        # nao se compara com um limiar — verifica-se **se existe**, e o
        # veredicto distingue "tem APP declarada" de "APP nao declarada", que
        # e' falta de medicao e nao uma areas declarada.
        tem_app = area_app > 0

        # Tres estados, nao dois. Colapsar "sem APP declarada" em "regular"
        # seria inventar conformidade a partir de ausencia de dado — que e'
        # exactamente o defeito que este modulo veio corrigir.
        if atual < exigido:
            status = "deficit_de_reserva_legal"
        elif not tem_app:
            status = "app_nao_declarada"
        else:
            status = "regular"

        if status == "regular":
            recomendacao = (
                "Percentual declarado dentro do minimo do bioma, e ha APP declarada."
            )
        elif status == "app_nao_declarada":
            recomendacao = (
                "A Reserva Legal esta' dentro do minimo, mas nao ha APP "
                "declarada. APP degradada e' infracao ambiental por si, "
                "independentemente da Reserva Legal. A area depende da "
                "geometria (margens de curso d'agua, topos de morro, encostas) "
                "e nao se deduce de um percentual — por isso este relatorio "
                "nao a calcula: mede-se, ou nao se sabe."
            )
        else:
            recomendacao = (
                f"Faltam {deficit_ha} ha de Reserva Legal para chegar a "
                f"{exigido * 100:.0f}% de {area_total} ha. A compensacao e' "
                "regulamentada pelo PRA e tem prazo — este numero e' uma "
                "conta sobre area declarada, nao uma pendencia que o banco "
                "vai encontrar."
            )

        # As chaves chamam-se `percentual_*`, logo devolvem **percent** e nao
        # fracao. Uma fracao 0.8 debaixo de um nome que promete "percentual" e'
        # a mesma confusao que o bug original era — o produtor tem de saber
        # ler 80 e nao 0,8, e o valor tem de bater certo com o que a lei diz.
        # A fracao fica interna; a conversao e' na fronteira.
        return {
            "propriedade_id": prop.id,
            "bioma": bioma,
            "bioma_rotulo": ROTULOS_BIOMA.get(bioma, bioma),
            "area_total_ha": float(area_total),
            "area_reserva_legal_ha": float(area_rl),
            "area_app_ha": float(area_app),
            "percentual_rl_atual": float((atual * 100).quantize(Decimal("0.01"))),
            "percentual_rl_exigido": float(exigido * 100),
            "deficit_ha": float(deficit_ha),
            "status_compliance": status,
            "recomendacao": recomendacao,
            # A APP entra no veredicto com dois dados: se existe, e o que
            # existe. Sem eles, `status_compliance` dizia "regular" a uma
            # propriedade que nao tem APP registada.
            "tem_app_declarada": tem_app,
            "app_verificacao": (
                "APP declarada pelo produtor; a congruencia com a geometria "
                "nao e' verificada por este relatorio."
                if tem_app
                else "APP nao declarada. Nao medido, e' diferente de medido como zero."
            ),
            # ── O que este relatorio NAO e' ───────────────────────────────
            #
            # Tres coisas, todas escritas, porque cada uma delas e' o que
            # transforma um relatorio util num documento que o produtor
            # apresenta como se fosse oficial:
            "fonte": "area e Reserva Legal autodeclaradas no Ampliagro",
            "certificado": False,
            "aviso": AVISO_CAR,
            "base_legal": BASE_LEGAL,
        }

    @staticmethod
    def _mede_areas(prop) -> dict:
        """Soma das areas declaradas, em `Decimal` (nunca `float`).

        O `float` so' entra na saida, e' na camada que fala JSON. O calculo
        fica em `Decimal` de ponta a ponta: e' o que impede que
        `exigido * area_total - area_rl` seja uma subtraccao com erro.
        """
        areas = AreaPreservacao.objects.filter(propriedade=prop)
        area_rl = sum(
            (Decimal(a.area_hectare or 0) for a in areas if a.tipo == "RL"),
            Decimal("0"),
        )
        area_app = sum(
            (Decimal(a.area_hectare or 0) for a in areas if a.tipo == "APP"),
            Decimal("0"),
        )
        return {
            "area_reserva_legal_ha": area_rl,
            "area_app_ha": area_app,
        }
