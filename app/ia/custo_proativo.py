"""Orcamento x realizado, lido pelo motor proativo.

`contas_proativo.py` faz isto para as contas a pagar. Este faz para a conta
por talhao. A forma de saida e' a MESMA - de proposito: o motor consome uma
unica estrutura, e um segundo formato significa uma segunda coisa para o
motor aprender a ler.

**A regra que este modulo impõe a si mesmo: so avisa desvio que DÓ para agir.**

Um motor proativo que manda um alerta por cada talhao com desvio produz, numa
fazenda de 20 talhoes, 20 alertas, e o produtor deixa de ler ao terceiro. E o
que acontece quando o sistema e' competente mas barulhento é pior do que
quando o sistema não existe: o produtor desliga as notificações.

Por isso o limiar nao e' "qualquer desvio". E':
  - desvio de **15% ou mais** do orcado, E
  - pelo menos **R$ 500** de diferenca absoluta.

As duas condicoes juntas. Uma propriedade pequena com 8% de desvio não ouve
nada - R$ 120 não muda uma decisão. E uma propriedade grande com 2% ouve
nada - R$ 4.000 num orçamento de R$ 200.000 não é o que dói. O que dói é
quando o número que o produtor planeou e o número que gastou deixam de
conversar, e isso tem um minimo em reais.

**O que este modulo NAO avisa**, e a lista é deliberada:

- **Sem orçamento registado.** Não é um desvio; é falta de cadastro. O aviso
  de "faltam orçar 3 talhões" é do painel (`pendencias`), não do motor. O
  motor não transformaria falta de dados em ruído diário.
- **Talhão sem lançamento.** O mesmo: quem não lançou não gastou, e dizer
  "gastou 0" seria mentira.
- **Despesa sem talhão.** Aparece como `nao_alocado` mas não tem talhão a que
  atribuir o excesso. Ratear seria inventar o destino do dinheiro.
- **Orçamento zero.** `orcamento = 0` com `desvio = 25.000` dá divisão por
  zero; o serviço já devolve `desvio_pct = None` nesse caso, e aqui também não
  se divide.

E o mais importante: **este modulo não escreve nada**. Lê, compara, e devolve
o que o produtor tem de saber. A acção — reduzir a próxima semente, adiar uma
aplicação — é do produtor.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.services.custo_talhao import custo_por_talhao

# Abaixo disto, o desvio nao muda decisao nenhuma.
LIMIAR_PCT = Decimal("15")
LIMIAR_REAIS = Decimal("500")

# Quantos talhoes num so alerta. O motor proativo tem um limite de tamanho
# porque o contexto vai para um LLM que roda no telefone do produtor; 20
# linhas de custo sao 20 linhas de contexto para um aviso que se resolve em
# uma frase. Os piores entram; o resto fica no painel.
MAX_TALHOES = 3


def _dinheiro(v: Decimal | None) -> str:
    """`None` devolve `--`, nunca `R$ 0,00`.

    Mesma regra do resto do sistema: "não registado" e "registou zero" são
    coisas diferentes, e num aviso proativo a diferença é entre o produtor
    agir e o produtor não fazer nada.
    """
    if v is None:
        return "--"
    return f"R$ {v:,.2f}"


def _pct(v: Decimal | None) -> str:
    if v is None:
        return "--"
    return f"{v:,.1f}%"


def desvio_para_cenario(
    user, propriedade, *, hoje: date | None = None
) -> dict[str, Any]:
    """Talhoes que gastaram mais do que orcado, para o motor proativo.

    Devolve a forma que `proativo.py` consome — a mesma de
    `contas_para_cenario`:

        {"tem_algo": bool, "desvios": int, "lista": [
            {"titulo", "mensagem", "nivel", "marca", "cartao"}, ... ]}
    """
    if propriedade is None:
        return {"tem_algo": False, "desvios": 0, "lista": []}

    # O ANO CORRETO. MEDIDO 2026-10-05: eu nao passava `ano`, e o servico
    # devolve `None`, que significa "agrega tudo". Um gasto de 2019 contava
    # contra o orcado da safra de 2026 e produzia um desvio de 300% sobre
    # um orcado que ja foi cumprido ha sete anos.
    #
    # Nao ha ano "certa" sem perguntar: um produtor em safrinha em October
    # esta' a comparar contra 2026, e um produtor de.beans em marco esta' a
    # comparar contra 2025. `hoje` e' o parametro que o motor ja' passa
    # para `contas_para_cenario`, e o ano do orcado segue a safra corrente.
    ano_ref = (hoje or date.today()).year
    resultado = custo_por_talhao(user, propriedade=propriedade, ano=ano_ref)

    candidatos = []
    for linha in resultado.linhas:
        # Sem orcado ou sem area: nao e' um desvio, e' falta de cadastro.
        if linha.orcado is None or linha.desvio is None:
            continue
        # Dentro do orcado nao se avisa - e' isso que o produtor QUER.
        if linha.desvio <= 0:
            continue
        # As duas condicoes, juntas.
        if linha.desvio < LIMIAR_REAIS:
            continue
        if linha.desvio_pct is None or linha.desvio_pct < LIMIAR_PCT:
            continue
        candidatos.append(linha)

    candidatos.sort(key=lambda l: l.desvio, reverse=True)

    lista = []
    for linha in candidatos[:MAX_TALHOES]:
        pct_txt = _pct(linha.desvio_pct)
        por_ha = ""
        if linha.custo_por_ha is not None:
            por_ha = f" ({_dinheiro(linha.custo_por_ha)}/ha)"

        lista.append(
            {
                "titulo": (
                    f"{linha.talhao}: gastou {_pct(linha.desvio_pct)} acima do orcado"
                ),
                "mensagem": (
                    f"O orcado era {_dinheiro(linha.orcado)} e ja' foram "
                    f"{_dinheiro(linha.realizado_despesa)} - "
                    f"{_dinheiro(linha.desvio)} a mais{pct_txt}{por_ha}. "
                    f"O que ainda esta' comprometido e' "
                    f"{_dinheiro(linha.comprometido_despesa)}, e isso ainda "
                    f"pode aumentar a conta."
                ),
                # O NIVEL, em portugues. MEDIDO 2026-10-05: escrevi
                # "critical"/"warning" e o motor nunca os emitia.
                #
                # A casa fala "critico"/"atencao" - e' o que `emitir_alerta`
                # mapeia para 0/1/2 e o que o filtro de preferencia de
                # `varrer_proativo` compara (`nivel_minimo`). Uma string que
                # nao existe nessa escala cai em `mapa_nivel.get(..., 1)`,
                # vira atencao, e nunca corresponde ao `=="atencao"` do
                # filtro: o alerta passava a WRITE mas nunca chegava a sair.
                #
                # E' o mesmo erro do limiar 0.6 vs 0.06 - um valor certo na
                # escala errada. Um detector que compara texto apanha; um
                # teste que so verifica `nivel` tem de verificar o VALOR
                # exacto, nao a presenca da chave.
                "nivel": "critico" if (linha.desvio_pct or 0) >= 40 else "atencao",
                "marca": f"+{pct_txt} do orcado",
                "cartao": "custo",
                "talhao": linha.talhao,
                "talhao_id": linha.talhao_id,
                "desvio": linha.desvio,
                "desvio_pct": linha.desvio_pct,
            }
        )

    return {
        "tem_algo": bool(lista),
        # O total e' o numero que NAO cabe no alerta. "Varios talhoes" obriga
        # o produtor a abrir a tela; o total obriga-o a decidir.
        "desvios": len(candidatos),
        "total_desvio": float(sum((l.desvio for l in candidatos), Decimal("0"))),
        "total_desvio_por_talhao": (
            float(resultado.nao_alocado_despesa)
            if resultado.nao_alocado_registros
            else 0.0
        ),
        "lista": lista,
    }


def resumo_desvio(user, propriedade) -> dict[str, Any]:
    """O retrato curto, para a tela e para o contexto do LLM.

    Nao e' isto que o produtor ve no alerta - o alerta tem de ser curto. E'
    isto que vai no cenario, para o LLM poder responder a pergunta seguinte
    sem ir buscar nada.
    """
    resultado = custo_por_talhao(user, propriedade=propriedade)
    com_orcado = [l for l in resultado.linhas if l.orcado is not None]
    fora = [l for l in com_orcado if l.desvio and l.desvio > 0]
    fora.sort(key=lambda l: l.desvio, reverse=True)

    return {
        "orcado_total": float(sum((l.orcado for l in com_orcado), Decimal("0"))),
        "realizado_total": float(resultado.total_despesa),
        "desvio_total": float(sum((l.desvio for l in fora), Decimal("0"))),
        "talhoes_com_orcado": len(com_orcado),
        "talhoes_acima": [l.talhao for l in fora],
        "pior": fora[0].talhao if fora else None,
        "pior_desvio_pct": float(fora[0].desvio_pct)
        if fora and fora[0].desvio_pct
        else None,
        "nao_alocado": float(resultado.nao_alocado_despesa),
        "nao_alocado_registros": resultado.nao_alocado_registros,
    }
