"""A REGRA DE CONTAS, ligada ao motor proactivo.

MEDIDO 2026-10-05 (agente 9). Este modulo tem DUAS metades com papeis
diferentes, e a distincao e' o que permite a regra entrar no motor sem
atalho:

  `contas_para_cenario`  LE do banco. Chamada por `proativo.montar_cenario`,
                        que e' quem tem a propriedade. Devolve DADOS.
  `regra_contas`         ja' nao e' usada pelo motor — deixou de ser o ponto de
                        entrada quando a regra passou a entrar por
                        `regras_deterministicas`, que e' pura. Mantem-se porque
                        e' a leitura directa, a que se chama de um script ou de
                        um teste, e e' o que documenta a regra sem o motor no
                        meio.

POR QUE NAO UM ATALHO PROPRIO
=============================
A regra da chuva entra por `regras_deterministicas` e dai para `emitir_alerta`,
que e' onde estao o `nivel_minimo` do produtor, o teto diario e o fingerprint
que evita repetir. Uma segunda entrada para as contas — a que fizesse a
consulta e emitisse directamente — passaria ao lado de tudo isso. E a falha
seria invisivel: o alerta saia, so que sem teto e sem deduplicacao, e o
produtor passava a receber a mesma cobranca cinco vezes.

Por isso a regra de contas entra pelo MESMO caminho da chuva. Um caminho com
atalho proprio e' o dia em que a governanca e' contornada.

O QUE A REGLA NAO FAZ
======================
- Nao sugere como pagar, nem negocia, nem paga.
- Nao escreve em `LancamentoFinanceiro`.
- Nao usa `LancamentoFinanceiro.data` como vencimento: essa data e' quando o
  facto ACONTECEU. Uma despesa sem `ContaAPagar` nao entra na lista de
  vencimentos, porque nao se sabe quando vence — e a `listar_contas` diz
  exatamente isso ao produtor.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

#: Antecedencia. Tres dias da ao produtor para ligar ao fornecedor ou repor no
#: banco. Avisar no dia ja e' tarde — e' quando ele nao tem como reagir.
DIAS_DE_ANTECEDENCIA = 3


def _dinheiro(v) -> str:
    """`1.234,56` — como o produtor le, nao como a maquina guarda."""
    try:
        d = Decimal(str(v or 0))
    except (InvalidOperation, ValueError):
        d = Decimal("0")
    inteiro, _, frac = f"{d:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{frac}"


def contas_para_cenario(user, propriedade, *, hoje=None) -> dict:
    """Le as contas em aberto que pedem atencao. DADOS, nao achados.

    Devolve a forma que `proativo._regra_contas_do_cenario` consome:

        {"tem_algo": bool, "vencidas": int, "lista": [
            {"titulo", "mensagem", "nivel", "marca", "quem", "valor",
             "carimbo", "evidencia", "conta_id"}, ... ]}

    A consulta e' aqui — `montar_cenario` tem a propriedade — e a formatacao e'
    em `regras_deterministicas`, que fica pura. Cada metade faz uma coisa.
    """
    from django.utils import timezone

    from app.models.contas import ContaAPagar

    hoje = hoje or timezone.localdate()
    horizonte = hoje + timedelta(days=DIAS_DE_ANTECEDENCIA)

    qs = (
        ContaAPagar.objects.filter(
            propriedade=propriedade,
            estado="ABERTA",
            vencimento__lte=horizonte,
        )
        .order_by("vencimento")
        .select_related("conta_bancaria")[:20]
    )

    lista: list[dict] = []
    for conta in qs:
        # Uma conta sem origem da data entra no aviso, mas marcada. O produtor
        # ve que nao sabemos de onde veio o vencimento — e e' isso que o faz
        # confirmar antes de pagar.
        carimbo = "" if conta.confiavel else " (data sem origem — confirme a data)"
        quem = conta.fornecedor or conta.descricao

        if conta.vencida:
            marca = f"VENCIDA ha {conta.dias_atraso} dias"
            titulo = (
                f"Conta vencida ha {conta.dias_atraso} dias: {_dinheiro(conta.valor)}"
            )
            mensagem = (
                f"{conta.descricao}"
                + (f" ({conta.fornecedor})" if conta.fornecedor else "")
                + f" venceu em {conta.vencimento:%d/%m/%Y} e continua em "
                f"aberto. Sao {_dinheiro(conta.valor)}.{carimbo} "
                f"Se ja pagou e nao lancou, diga — o LCDPR fecha com o pagamento."
            )
            nivel = "critico"
        elif conta.vencimento == hoje:
            dias = 0
            marca = "vence hoje"
            titulo = f"Conta vence hoje: {_dinheiro(conta.valor)}"
            mensagem = (
                f"{conta.descricao}"
                + (f" ({conta.fornecedor})" if conta.fornecedor else "")
                + f" vence hoje, {hoje:%d/%m/%Y}. {_dinheiro(conta.valor)}."
                + carimbo
            )
            nivel = "atencao"
        else:
            dias = (conta.vencimento - hoje).days
            marca = f"vence em {dias} dias"
            titulo = f"Conta vence em {dias} dias: {_dinheiro(conta.valor)}"
            mensagem = (
                f"{conta.descricao}"
                + (f" ({conta.fornecedor})" if conta.fornecedor else "")
                + f" vence a {conta.vencimento:%d/%m/%Y}, daqui a {dias} dias. "
                f"{_dinheiro(conta.valor)}.{carimbo}"
            )
            nivel = "info"

        lista.append(
            {
                "titulo": titulo,
                "mensagem": mensagem,
                "nivel": nivel,
                "marca": marca,
                "quem": quem,
                "valor": _dinheiro(conta.valor),
                "carimbo": carimbo,
                "conta_id": conta.pk,
                # o fingerprint que impede o mesmo aviso duas vezes
                "evidencia": (
                    f"conta:{conta.pk}:{conta.vencimento.isoformat()}:{conta.estado}"
                ),
            }
        )

    return {
        "tem_algo": bool(lista),
        "vencidas": sum(1 for c in lista if c["nivel"] == "critico"),
        "lista": lista,
    }


def regra_contas(user, propriedade, *, hoje=None) -> list[dict]:
    """A regra em forma de achado, para leitura directa.

    O motor NAO usa esta — usa `contas_para_cenario` + a formatacao em
    `proativo`. Fica porque e' a leitura sem o motor no meio, que e' o que se
    quer quando se esta a ver o que o produtor ia receber.
    """
    return contas_para_cenario(user, propriedade, hoje=hoje)["lista"]


def resumo_saude_financeira(user, propriedade, *, hoje=None) -> dict:
    """O retrato que o painel mostra: quanto sai, quanto entra, quanto atrapa.

    Devolve tambem `incompletos` — as contas sem origem da data. Um ERP que
    mostra "tudo em dia" sem dizer que ha um vencimento nao verificado esta a
    dizer que sabe quando nao sabe.
    """
    from django.utils import timezone

    from app.models.contas import ContaAPagar, ContaAReceber

    hoje = hoje or timezone.localdate()

    pagar = ContaAPagar.objects.filter(propriedade=propriedade, estado="ABERTA")
    receber = ContaAReceber.objects.filter(propriedade=propriedade, estado="ABERTA")

    total_pagar = sum((c.valor for c in pagar), Decimal("0"))
    total_receber = sum((c.valor for c in receber), Decimal("0"))
    vencidas = [c for c in pagar if c.vencida]
    total_vencido = sum((c.valor for c in vencidas), Decimal("0"))
    sem_origem = [c for c in pagar if not c.confiavel]

    return {
        "total_pagar": total_pagar,
        "total_receber": total_receber,
        "saldo_previsto": total_receber - total_pagar,
        "qtd_pagar": pagar.count(),
        "qtd_receber": receber.count(),
        "qtd_vencidas": len(vencidas),
        "total_vencido": total_vencido,
        "qtd_sem_origem": len(sem_origem),
        "proximo_vencimento": pagar.order_by("vencimento").first(),
        "hoje": hoje,
    }
