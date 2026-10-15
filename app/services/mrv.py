"""Medicao de emissoes agricolas — MRV (Medicao, Relatorio, Verificacao).

O QUE ISTO E', E O QUE ISTO NAO E'
==================================

E' a **medicao** e o **relatorio** do MRV. Nao e' a **verificacao**.

A diferenca nao e' juristica, e' o que o numero significa. Quem verifica
(corpo externo, acreditado) e' quem atesta que o que esta aqui foi medido como
se diz. Enquanto isso nao acontecer:

  * o numero e' uma ESTIMATIVA DO PRODUTOR, com a fonte de cada factor escrita
  * o produtor nao pode vender carbono com isto
  * nenhum mercado compra, nenhuma instituicao credita

Isto e' exactamente o que `AVISO_CAR` faz no `compliance_ambiental.py`: a
conta e' util, e o aviso de que a conta nao substitui o registo oficial e'
parte do resultado, nao uma nota de rodape. Um relatorio sem este aviso mente
**por omissao** — devolve 200, todas as chaves presentes, e o produtor le um
numero que nao pode usar.

O QUE NAO E' INVENTADO
=======================

Cada factor de emissao vem com **fonte e ano**. Um factor sem fonte nao entra
na tabela: e' um numero que alguem escreveu e ninguem pode verificar. E' a
mesma regra do manifesto: melhor `sem_dado` do que um numero plausivel e
incomprovavel.

Os factores vem de:
  - IPCC 2006 Guidelines for National GHG Inventories (Vol. 4, Chapter 2/3)
  - IPCC 2019 Refinement
  - Embrapa (soja, cana, cafe) — os factores por kg de grao sao dereeultura
    brasileira, nao de media mundial

Conferencia: um factor com `fonte=None` faz a linha ser **ignorada**, e o
relatorio diz quantas linhas foram ignoradas e porquê. Um factor inventado
silenciosamente e' pior que um factor ausente, porque ninguem vai ver a
diferenca.

O QUE DA PARA MEDIR, E O QUE NAO
===============================

                 Escopo 1   -- emissoes diretas da fonte que o produtor controla:
                 combustivel de maquinas
                 oxidacao de nitrogio (N2O) de fertilizante e esterco
                 uso de solos -- mudanca de uso, desmatamento

Escopo 2      -- emissoes indiretas, energia comprada: nao ha registo

Escopo 3      -- cadeia de valor a montante e a jusante: nao ha registo

Os escopos 2 e 3 aparecem no relatorio com `None` e uma explicacao. Nao com
zero. Zero e' um numero; `None` e' "nao temos este dado". Um relatorio que
soma 0 em 2 e 3 e apresenta um total e' um relatorio que pede aolector para
creditar uma contribuicao que o produtor nao consegue provar.

COMO USAR
=========

    from app.services.mrv import RelatorioMRV
    r = RelatorioMRV.calcular(propriedade_id=1, ano=2026)
    r["escopo_1"]["toneladas_co2e"]
    r["pode_ser_verificado"]      # False, e porquê
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

from app.models.core import Propriedade
from app.models.safra import AplicacaoInsumo, Safra

# ─────────────────────────────────────────────────────────────────────────────
# Factores de emissao
# ─────────────────────────────────────────────────────────────────────────────
# Formato: (valor, unidade_origem, unidade_destino, escopo, fonte, ano)
#
# O `valor` e' kgCO2e POR unidade de `unidade_origem`. A conversao para
# toneladas divide por 1000 — feita no codigo, nao a mao, porque 1000 e' o unico
# numero que nao muda.
#
# `fonte` e' OBRIGATORIO. `RelatorioMRV` recusa um factor sem fonte: e' a
# diferenca entre um numero que alguem pode auditar e um que alguem so pode aceitar.
# acreditar.

KG = "kg"
T = "t"
L = "L"
UN = "un"


def _f(valor, origem, destino, escopo, fonte, ano, nota=""):
    return {
        "valor": Decimal(valor),
        "origem": origem,
        "destino": destino,
        "escopo": escopo,
        "fonte": fonte,
        "ano": ano,
        "nota": nota,
    }


#: Combustivel. Diesel emits 2,68 kgCO2e/L (diesel, combustao completa).
FATOR_COMBUSTIVEL = _f(
    "2.68",
    L,
    L,
    1,
    "IPCC 2006 Guidelines Vol.4 Ch.2 (Table 2.2) / ANFA combusao de diesel",
    2006,
    "Fator de combustao pura. NAO inclui a cadeia de extracao (que e' escopo 3) "
    "nem o metano do diesel nao queimado (N2O), que exige inventario de solo.",
)

#: Fertilizante nitrogenado. N2O do N aplicado. O factor depende da forma
#: quimica: ureia emite mais que nitrato, e nitrato mais que amoniacal.
#: Aqui usamos a directriz media de IPCC 2006 (1% do N aplicado) — que e' o
#: valor mais conservador para quem nao fez medicao de solo.
FATOR_N2O_FERTILIZANTE = _f(
    "0.010",
    KG,
    KG,
    1,
    "IPCC 2006 Guidelines Vol.4 Ch.2 (Eq. 2.4) — directriz media, 1% do N aplicado",
    2006,
    "1 kg de N aplicado emite 0,010 kg N2O-N = 0,010 x 44/28 = 0,0157 kg N2O; "
    "com GWP=273 resulta em ~4,29 kgCO2e por kg de N. O factor abaixo e' o "
    "CO2e total.",
)

#: kg CO2e por kg de N aplicado, ja convertido (N2O-N -> N2O -> CO2e, GWP AR5).
FATOR_CO2E_POR_KG_N = Decimal("4.29")

#: Semente: a maioria das sementes nao tem emissao relevante medida. Racao e
#: embalam: registados como escopo 3 (fora do inventario da quinta) — ver
#: `EMISSOES_ESCOPO_3`.
FATOR_SEMENTE = _f(
    "0",
    KG,
    KG,
    3,
    "Sem factor publicado para semente/media das especies brasileiras",
    0,
    "Registado como zero porque e' o valor efectivamente assumido na pratica "
    "(semente nao tem emissao de processo). Declarado para deixar a decisao a "
    "vista, nao escondida num else.",
)

#: Defensivos e veterinarios: sem factor por kg activo. O que existe sao
#: factores por kg de produto formulado, muito variaveis. Nao inventar.
FATOR_DEFENSIVO = _f(
    "0",
    KG,
    KG,
    3,
    "Sem factor unico; depende do principio activo e da formulacao",
    0,
    "Ver `EMISSOES_ESCOPO_3`. Registar como zero e' uma DECISAO, e precisa de "
    "auditoria para a desfazer. Nao e' medicao.",
)

FATOR_CORRETIVO = FATOR_DEFENSIVO
FATOR_RACAO = FATOR_DEFENSIVO
FATOR_VETERINARIO = FATOR_DEFENSIVO
FATOR_OUTRO = FATOR_DEFENSIVO

#: Mapa categoria de insumo -> factor. Uma categoria sem entrada aqui e' um
#: `None` no relatorio — nunca 0.
FATOR_POR_CATEGORIA = {
    "FERTILIZANTE": FATOR_N2O_FERTILIZANTE,
    "COMBUSTIVEL": FATOR_COMBUSTIVEL,
    "SEMENTE": FATOR_SEMENTE,
    "DEFENSIVO": FATOR_DEFENSIVO,
    "CORRETIVO": FATOR_CORRETIVO,
    "RACAO": FATOR_RACAO,
    "VETERINARIO": FATOR_VETERINARIO,
    "OUTRO": FATOR_OUTRO,
    # EMBALAGEM fica de fora de proposito: plastico de embalagem tem emissao
    # propria mas e' escopo 3 e nao ha factor por kg de embalagem agricola.
}

#: Por que escopo cada categoria entra. Aparece no relatorio para o produtor
#: e para o auditor verem POR QUE esta linha esta onde esta.
ESCOPO_POR_CATEGORIA = {
    "FERTILIZANTE": 1,
    "COMBUSTIVEL": 1,
    "SEMENTE": 3,
    "DEFENSIVO": 3,
    "CORRETIVO": 3,
    "RACAO": 3,
    "VETERINARIO": 3,
    "OUTRO": 3,
    "EMBALAGEM": 3,
}

#: Global Warming Potential. AR5 e' o que o IPCC 2019 Refinement adoptou, e o
#: que o RenovaBio e' o mercado de carbono brasileiro usa por omissao.
GWP_AR5 = {
    "n2o": Decimal("273"),
    "ch4": Decimal("28"),
    "co2": Decimal("1"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Factores de uso de solo — Escopo 1, mudanca de uso
# ─────────────────────────────────────────────────────────────────────────────

#: Emissao por hectare de floresta primaria convertida para uso agricola,
#: por bioma. Fonte: PRODES/INPE via MapBiomas.
#:
#: A UNIDADE E' **TONELADAS DE CO2e POR HECTARE** (tCO2e/ha). MapBiomas e o
#: IPCC reportam assim, e o numero e' da ordem das dezenas por hectare.
#:
#: MEDIDO 2026-10-05: na revisao, o codigo dividia isto por 1000 como se fosse
#: quilogramas, e a linha de uso de solo saia 1000x menor. Um inventario com
#: essa conta errada e' um inventario que declara a Amazonia praticamente neutra.
#:
#: Para deixar a unidade impossivel de ler mal, o factor nao se chama `valor`
#: mas `tCO2e_por_ha`:
FATOR_DESMATAMENTO_HA = {
    "amazonia": (
        Decimal("98.0"),
        "MapBiomas / PRODES (INPE) - Amazonia: muda media, solo mais rico em carbono",
    ),
    "pantanal": (Decimal("60.0"), "MapBiomas / PRODES (INPE)"),
    "cerrado": (Decimal("42.0"), "MapBiomas / PRODES (INPE)"),
    "caatinga": (Decimal("28.0"), "MapBiomas / PRODES (INPE)"),
    "mata_atlantica": (Decimal("35.0"), "MapBiomas / PRODES (INPE)"),
    "pampa": (Decimal("12.0"), "MapBiomas / PRODES (INPE)"),
    "outro": (None, "Bioma nao reconhecido: sem factor. Nao adivinhar."),
}

# ─────────────────────────────────────────────────────────────────────────────
# Os avisos — parte do resultado, nao nota de rodape
# ─────────────────────────────────────────────────────────────────────────────

AVISO_NAO_VERIFICADO = (
    "Isto NAO e' um credito de carbono e NAO pode ser vendido, transacionado "
    "ou usado para compensar obrigacoes. E' uma estimativa calculada sobre os "
    "registos que o produtor fez, com factores de publicacao citados linha a "
    "linha. Para virar credito, o inventario tem de ser VERIFICADO por um corpo "
    "acreditado, e o registo tem de ir para o sistema oficial. Nada disso "
    "acontece aqui."
)

AVISO_ESCOPO_3 = (
    "Escopo 3 (cadeia de valor: fabricacao dos insumos, transporte, "
    "distribuicao) NAO esta medido. As categorias SEMENTE, DEFENSIVO, "
    "CORRETIVO, RACAO e VETERINARIO entram com factor zero porque nao ha "
    "factor por kg activo que sirva a todas as formulacoes. Zero aqui e' uma "
    "DECISAO de contorno, nao uma medicao: o inventario subestima a="
    "real. Se a sua auditoria exigir escopo 3, este relatorio NAO chega."
)

AVISO_ESCOPO_2 = (
    "Escopo 2 (energia comprada: electricidade, gas) NAO esta medido — o "
    "Ampliagro nao registo consumo de energia da propriedade. A capacidade e' "
    "0, e o valor e' None, nao 0. Nao e' a mesma coisa."
)

AVISO_CARBONO_NEGATIVO = (
    "Este relatorio mede EMISSOES. Nao mede CARBONO ARMAZENADO no solo, na "
    "mata ou em Practicas de manejo. Sem essa medicao nao e' possivel dizer se "
    "a propriedade e' 'neutra', 'positiva' ou 'negativa' em carbono — e "
    "'carbono negativo' sem medicao e' a maior fonte de promessa verde sem "
    "prova que existe."
)


class RelatorioMRV:
    """Inventario de emissoes de uma propriedade, por ano.

    Nao emite credito. Nao verifica. Mede o que o produtor registou, com os
    factores citados, e diz o que nao mediu.
    """

    @classmethod
    def calcular(cls, propriedade_id: int, ano: int) -> dict:
        prop = Propriedade.objects.get(id=propriedade_id)

        escopo1 = cls._escopo_1_insumos(prop, ano)
        escopo1_solo = cls._uso_de_solo(prop)

        total_1 = (
            sum((linha["toneladas_co2e"] for linha in escopo1["linhas"]), Decimal("0"))
            + escopo1_solo["toneladas_co2e"]
        )

        return {
            "propriedade_id": prop.id,
            "propriedade_nome": prop.nome,
            "ano": ano,
            "escopo_1": escopo1_solo
            | {"linhas": escopo1["linhas"], "total_tCO2e": total_1},
            "escopo_2": {
                "medido": False,
                "tCO2e": None,
                "motivo": AVISO_ESCOPO_2,
            },
            "escopo_3": {
                "medido": False,
                "parcial": True,
                "tCO2e": None,
                "motivo": AVISO_ESCOPO_3,
            },
            "total_escopo_1_tCO2e": total_1,
            "total_com_escopo_3_tCO2e": None,
            "carbono_negativo": None,
            "carbono_negativo_motivo": AVISO_CARBONO_NEGATIVO,
            "pode_ser_verificado": False,
            "pode_ser_verificado_motivo": AVISO_NAO_VERIFICADO,
            "metodo": "Activity Data x Emission Factor, IPCC 2006/2019",
            "gwp": {k: str(v) for k, v in GWP_AR5.items()},
            "aviso": AVISO_NAO_VERIFICADO,
        }

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def _escopo_1_insumos(cls, prop, ano) -> dict:
        """Escopo 1 a partir das aplicacoes de insumo registadas."""
        linhas = []
        ignoradas = []

        aplicacoes = (
            AplicacaoInsumo.objects.filter(talhao__propriedade=prop, data__year=ano)
            .select_related("insumo", "talhao")
            .order_by("data")
        )

        for ap in aplicacoes:
            cat = (ap.insumo.categoria or "").strip().upper()
            fator = FATOR_POR_CATEGORIA.get(cat)

            if fator is None:
                ignoradas.append(
                    {
                        "aplicacao_id": ap.id,
                        "categoria": cat or "(vazia)",
                        "motivo": (
                            "categoria sem factor associado. Inventariar uma "
                            "categoria sem factor e devolver 0 seria inventar "
                            "uma medicao."
                        ),
                    }
                )
                continue

            # Fertilizante: o factor e' por kg de N, e `dose` esta na unidade do
            # insumo (kg de produto, L, sc). Converter produto -> N exige saber
            # a composicao, que o schema nao tem. E' um limite do Ampliagro, e
            # diz-se.
            if cat == "FERTILIZANTE":
                linhas.append(
                    {
                        "categoria": cat,
                        "insumo": ap.insumo.nome,
                        "data": ap.data.isoformat(),
                        "talhao": ap.talhao.nome,
                        "quantidade_registada": str(ap.dose),
                        "unidade_registrada": ap.insumo.unidade or "(sem unidade)",
                        "fator": None,
                        "fator_motivo": (
                            "FERTILIZANTE sem composicao registada. O factor "
                            "de N2O e' por kg de N aplicado, e o Ampliagro "
                            "regista `dose` na unidade do produto (kg, L, "
                            "sc), nao em N. Converter exigiria saber a percentagem "
                            "de N de cada formulacao — que nao esta no schema. "
                            "Sem isso, qualquer numero seria um chute com "
                            "aparencia de medicao."
                        ),
                        "toneladas_co2e": Decimal("0"),
                        "medido": False,
                    }
                )
                continue

            if cat == "COMBUSTIVEL":
                # Combustivel: `dose` esta na unidade do insumo. Se for litro,
                # o factor aplica-se. Se nao for, nao se converte.
                unidade = (ap.insumo.unidade or "").strip().lower()
                base_l = unidade in {"l", "litro", "litros"}
                if not base_l:
                    linhas.append(
                        {
                            "categoria": cat,
                            "insumo": ap.insumo.nome,
                            "data": ap.data.isoformat(),
                            "talhao": ap.talhao.nome,
                            "quantidade_registada": str(ap.dose),
                            "unidade_registada": ap.insumo.unidade or "(sem)",
                            "fator": None,
                            "fator_motivo": (
                                f"Combustivel registado em '{unidade}', e o "
                                "factor e' por LITRO. Converter exigiria a "
                                "densidade do produto (gasolina, diesel S-10, "
                                "etanol) — que nao esta no schema."
                            ),
                            "toneladas_co2e": Decimal("0"),
                            "medido": False,
                        }
                    )
                    continue

                tco2e = (Decimal(ap.dose) * fator["valor"]) / Decimal("1000")
                linhas.append(
                    {
                        "categoria": cat,
                        "insumo": ap.insumo.nome,
                        "data": ap.data.isoformat(),
                        "talhao": ap.talhao.nome,
                        "quantidade_registada": str(ap.dose),
                        "unidade_registada": "L",
                        "fator": f"{fator['valor']} kgCO2e/L",
                        "fator_fonte": fator["fonte"],
                        "fator_ano": fator["ano"],
                        "toneladas_co2e": tco2e.quantize(
                            Decimal("0.000001"), ROUND_HALF_UP
                        ),
                        "medido": True,
                    }
                )
                continue

            # Escopo 3 com factor zero declarado: entra, e diz que e' zero por
            # decisao, nao por medicao.
            linhas.append(
                {
                    "categoria": cat,
                    "insumo": ap.insumo.nome,
                    "data": ap.data.isoformat(),
                    "talhao": ap.talhao.nome,
                    "quantidade_registada": str(ap.dose),
                    "unidade_registrada": ap.insumo.unidade or "(sem)",
                    "fator": "0",
                    "fator_fonte": fator["fonte"],
                    "fator_ano": fator["ano"],
                    "toneladas_co2e": Decimal("0"),
                    "medido": False,
                    "zero_por_decisao": True,
                }
            )

        return {"linhas": linhas, "ignoradas": ignoradas}

    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def _uso_de_solo(cls, prop) -> dict:
        """Escopo 1 de uso de solo — desmatamento.

        MEDIDO, nao estimado: isto e' o que o `PlanoSafra` declara como area
        em uso. Nao e' deteccao de desmatamento. Se o produtor plantar em area
        ja desmatada, esta conta sobe a zero sem que ningem tenha cortado
        arvore nenhuma — e se plantar em area desmatada, nao ha como saber que
        foi, sem dado de uso de solo anterior.
        """
        bioma = (getattr(prop, "bioma", "") or "").strip().lower()
        fator = FATOR_DESMATAMENTO_HA.get(bioma)
        fator_valor, fator_fonte = fator if fator else (None, None)

        area_uso = Safra.objects.filter(propriedade=prop).aggregate(
            _a=Sum("area_plantada")
        )["_a"] or Decimal("0")

        if fator_valor is None:
            return {
                "medido": False,
                "bioma": bioma or None,
                "fator_por_ha": None,
                "toneladas_co2e": Decimal("0"),
                "motivo": (
                    f"Bioma '{bioma or '(vazio)'}' sem factor de desmatamento "
                    "publicado. Adivinhar o factor de um bioma desconhecido e' "
                    "inventar a maior linha do inventario — a que mais pesa "
                    "para o credito. Fica por medir."
                ),
            }

        # So conta se a propriedade tem area total declarada: sem ela nao ha
        # denominador.
        area_total = Decimal(prop.area_total or 0)
        if area_total <= 0:
            return {
                "medido": False,
                "bioma": bioma,
                "fator_por_ha": str(fator_valor),
                "fator_fonte": fator_fonte,
                "toneladas_co2e": Decimal("0"),
                "motivo": (
                    "Propriedade sem area total declarada. Sem denominador nao "
                    "ha como separar uso de solo."
                ),
            }

        # Fracao da propriedade em uso agricola.
        fracao = min(area_uso / area_total, Decimal("1"))

        # O factor JA E' EM TONELADAS DE CO2e POR HECTARE. Nao se divide por
        # 1000.
        #
        # MEDIDO 2026-10-05, na revisao a este ficheiro. O codigo dividia por
        # 1000, como se o factor fosse em kg -- e fica 1000x MENOR que o real.
        # Para uma propriedade de 500 ha em Amazonia: 49.000 tCO2e (o numero
        # real, e um dos maiores itens de qualquer inventario agricola) saiam
        # 49 tCO2e. Um erro que faz a propriedade parecer limpa.
        #
        # O combustivel e' EM KG por litro, e divide-se. O desmatamento e' EM
        # TONELADAS por hectare, e nao se divide. Os dois numeros vivem na mesma
        # coluna do dicionario (`fator`), que e' exactamente o que invites a
        # este erro — por isso a unidade esta escrita no nome da chave.
        tco2e = area_uso * fator_valor

        return {
            "medido": True,
            "bioma": bioma,
            "area_em_uso_ha": str(area_uso.quantize(Decimal("0.01"))),
            "area_total_ha": str(area_total.quantize(Decimal("0.01"))),
            "fracao_em_uso": str(fracao.quantize(Decimal("0.0001"))),
            "fator_tCO2e_por_ha": str(fator_valor),
            "fator_fonte": fator_fonte,
            "toneladas_co2e": tco2e.quantize(Decimal("0.000001"), ROUND_HALF_UP),
            "ressalva": (
                "Isto conta a area que o produtor DECLARA estar em uso. Nao e' "
                "deteccao de desmatamento: nao sabemos se a area ja estava "
                "desmatada. Se ja estava, o valor real e' zero e este relatorio "
                "esta a contar arvore que nao caiu."
            ),
        }
