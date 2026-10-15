"""Passo de ESCRITA da conciliacao: aplica as propostas que o produtor aceitou.

`conciliacao_proposta.py` le e sugere. Este modulo grava. Sao dois ficheiros
porque a divisao e' o que impede o pior erro: um caminho que escreve e' um
caminho que precisa de confirmacao, e nao se pode dar essa responsabilidade a
um modulo que o produtor chama so' para ver.

## O contrato, e por que e' tao defensivo

Uma conciliacao mal feita e' diferente de um bug comum. Nao devolve erro ao
quem a fez - devolve um numero ERRADO. E o produtor, tres semanas depois,
descobre que o lucro da safra estava errado por causa de um casamento que ele
aceitou sem ver a razao.

Por isso, cada escrita passa por quatro portas, todas nesta funcao:

1. **`confirm=True` tem de vir do produtor.** Nao de um default, nao de um
   `params.get("confirm")` que devolve `None` e passa. Verificado como
   `is True`, nao como truthy - porque `confirm="false"` (string) e' truthy
   em Python e escreveria sem perguntar.

2. **A proposta tem de ser RE-COMPUTADA agora.** Nao seAceita o que veio do
   pedido. Se entre a proposta e a confirmacao outro lancamento foi pago, ou
   a data mudou, a proposta ja' nao vale - e usar a versao antiga do cliente
   gravaria um casamento que ja' nao existe. Este e' o ataque mais obvio de
   todos e quase ninguem fecha.

3. **Cada `id` tem de pertencer a conta E a propriedade do utilizador.** Dois
   filtros, nao um. Um `movimentacao_id` de outra fazenda tem de falhar mesmo
   que por algum motivo o filtro da conta passe.

4. **`atomic` + um unico `lancamento` por movimento.** Uma transacao ou
   nada. E cada movimento baixa no maximo um lancamento, porque dois
   movimentos nao podem baixar a mesma conta - isso criaria um pagamento
   que nao aconteceu.

## Por que 'aplicar tudo' e' recusado

`aplicar_todas` levanta `NaoPermitido`. Um 'concilhar tudo' seria
conveniente e seria exactamente o erro que este modulo existe para evitar:
o produtor clica num botao, 40 casamentos sao gravados de uma vez, e um deles
esta' errado. Nao ha forma de o sistema saber qual.

Aceitar e' accepto caso a caso. E' mais cliques. E' o preco.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from app.services.conciliacao_proposta import (
    CONFIANCA_EXATA,
    ResultadoConciliacao,
    sugerir,
)


class NaoPermitido(Exception):
    """Uma escrita foi pedida sem passar pelas portas. Nao e' erro de
    utilizador - e' uma tentativa de escrever pelas costas da confirmacao."""


@dataclass(frozen=True)
class Resultado:
    conciliados: list[dict[str, Any]]
    recusados: list[dict[str, str]]
    nada_foi_escrito: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "conciliados": self.conciliados,
            "recusados": self.recusados,
            "nada_foi_escrito": self.nada_foi_escrito,
            # `total` existe porque um cliente que mostra so' a lista recebe
            # "ok" com zero items e nao sabe se falhou ou se nao havia nada.
            "total": len(self.conciliados) + len(self.recusados),
        }


def aplicar(
    user,
    conta,
    movimentacao_ids: list[int],
    confirm: Any = None,
    *,
    permitir_duvidosa: bool = False,
    agora=None,
) -> Resultado:
    """Grava os casamentos aprovados. `confirm` tem de ser `True` literal.

    `permitir_duvidosa=False` e' o default e NAO e' por Prudencia vaga: um
    casamento `duvidosa` significa que o valor difere em ate 1%. Aceitar isso
    em lote e' como as duas contas de R$ 1.000 se confundem. Quem quiser passa
    `True` - e o registo guarda que foi uma decisao consciente.
    """
    # Porta 1. `is True`, nao truthiness: `confirm="false"` e' truthy e
    # escreveria sem perguntar. Este teste apanha o parametro vindo de
    # texto, de JSON malformado, ou de uma query string.
    if confirm is not True:
        raise NaoPermitido(
            "Escrita sem confirmacao. Nada foi gravado. Para aplicar, "
            "chame de novo com confirm=true - depois de ver a razao de "
            "cada casamento."
        )

    from app.models import LancamentoFinanceiro, MovimentacaoBancaria

    # Porta 3 (metade 1): os dois ids tem de ser da propriedade do utilizador.
    # `conta` ja' foi verificado pelo chamador, mas os ids nao - e sao eles
    # que escolhem o que e' gravado.
    # Porta 3 (metade 1). O filtro de tenancy e' uma RESTRICAO, nao um
    # filtro: o que o filtro apanha tem de ser RECUSADO com nome, nunca
    # ignorado.
    #
    # MEDIDO 2026-10-06. A versao anterior fazia `filter(...)` e seguia em
    # frente. O `movimentacao_id` de outra fazenda simplesmente desaparecia,
    # e a funcao devolvia `nada_foi_escrito=True` com um `ok` limpo. Isso e'
    # um fallo de seguranca disfarçado de sucesso: quem chamou achava que
    # gravou, e nao gravou - ou, pior, achava que o movimento nao existia e
    # nao ia la' ver. Silencio num caminho de escrita e' indistinguivel de
    # sucesso, e e' a unica coisa que este modulo nao pode ser.
    #
    # E `conta` tambem e' verificada aqui. Confiar no chamador funciona ate
    # alguem chamar com a conta errada - e a conta errada e' exatamente o
    # caso que este modulo tem de fechar.
    qs = MovimentacaoBancaria.objects.filter(pk__in=movimentacao_ids)
    if not conta or getattr(conta, "propriedade", None) is None:
        raise NaoPermitido("Conta inválida.")
    if conta.propriedade.user_id != getattr(user, "id", None):
        raise NaoPermitido(
            "Esta conta bancária não é sua. Nenhum movimento foi tocado."
        )

    conhecidos = set(qs.values_list("pk", flat=True))
    for mid in movimentacao_ids:
        if mid not in conhecidos:
            raise NaoPermitido(
                f"Movimento {mid} não existe, ou não pertence a uma conta "
                f"sua. Nada foi gravado."
            )

    movs = list(
        qs.filter(conta=conta, conta__propriedade__user=user).select_related("conta")
    )

    # O movimento pode EXISTIR e ainda assim ser de outra fazenda - e e'
    # esse o caso perigoso, porque o `conhecidos` acima passa. A restricao
    # tem de comparar com o que sobrou, nao com o que existia.
    devolvidos = {m.pk for m in movs}
    for mid in movimentacao_ids:
        if mid not in devolvidos:
            raise NaoPermitido(
                f"Movimento {mid} não pertence a esta conta. Nada foi gravado."
            )

    pendentes = []
    conciliados = []
    recusados = []

    movs_ids_vistos = set()
    for m in movs:
        if m.pk in movs_ids_vistos:
            recusados.append(
                {
                    "movimentacao_id": m.pk,
                    "motivo": "Este movimento foi pedido duas vezes.",
                }
            )
            continue
        movs_ids_vistos.add(m.pk)
        if m.conciliado:
            recusados.append(
                {
                    "movimentacao_id": m.pk,
                    "motivo": (
                        "Já estava conciliado. Se foi outra pessoa, o registo "
                        "diz quando."
                    ),
                }
            )
            continue
        pendentes.append(m)

    # Porta 2: re-computa. Nao seAceita a proposta que veio do pedido - a
    # base pode ter mudado entre a pergunta e a resposta.
    resultado: ResultadoConciliacao = sugerir(user, conta)
    por_mov = {p.movimentacao_id: p for p in resultado.propostas}

    escrita = []
    with transaction.atomic():
        lancamentos = LancamentoFinanceiro.objects.filter(
            pk__in=[p.lancamento_id for p in por_mov.values() if p.lancamento_id],
            propriedade__user=user,
            propriedade=conta.propriedade,
        )
        por_lanc = {l.id: l for l in lancamentos}

        usados_lanc = set()
        for m in pendentes:
            p = por_mov.get(m.pk)
            if p is None or p.lancamento_id is None:
                recusados.append(
                    {
                        "movimentacao_id": m.pk,
                        "motivo": (
                            "Já não há lançamento correspondente. Algo mudou "
                            "desde a consulta - reconsulte antes de aplicar."
                        ),
                    }
                )
                continue
            # MEDIDO 2026-10-06. Este portao comparava com `CONFIANCA_DUVIDOSA`, uma
            # constante que `conciliacao_proposta` **define mas nunca emite**.
            # A unica confianca abaixo de "exata" que o codigo produz e'
            # "provavel" (diferenca ate 1%). Resultado: o portao nunca
            # disparava, o `permitir_duvidosa` era um botao que nao fazia
            # nada, e um casamento com valores diferentes entrava sem
            # confirmacao extra - que era o que este modulo promete.
            #
            # A correccao e' inverter a logica: bloqueia tudo que NAO e'
            # exacto. Assim, se amanha' `sugerir` passar a emitir outra
            # confianca, ela fica bloqueada por omissao. Um portao escrito
            # como "permitir esta confianca exacta" falha aberto; escrito
            # como "recusar tudo menos esta" falha fechado, e e' o que se
            # quer num caminho que escreve dinheiro.
            if p.confianca != CONFIANCA_EXATA and not permitir_duvidosa:
                recusados.append(
                    {
                        "movimentacao_id": m.pk,
                        "motivo": (
                            f"Os valores diferem. {p.porque} Se for o "
                            f"mesmo número, aplique com permitir_duvidosa."
                        ),
                    }
                )
                continue
            if p.lancamento_id in usados_lanc:
                recusados.append(
                    {
                        "movimentacao_id": m.pk,
                        "motivo": (
                            "Esse lançamento já foi usado por outro movimento "
                            "neste pedido. Um lançamento só pode ser uma vez."
                        ),
                    }
                )
                continue
            lanc = por_lanc.get(p.lancamento_id)
            if lanc is None:
                recusados.append(
                    {
                        "movimentacao_id": m.pk,
                        "motivo": "Lançamento não encontrado nesta propriedade.",
                    }
                )
                continue

            usados_lanc.add(lanc.id)
            escrita.append(
                {
                    "movimentacao": m,
                    "lancamento": lanc,
                    "confianca": p.confianca,
                }
            )
            # MEDIDO 2026-10-06. `conciliados` e' a MESMA lista que recebia os
            # movimentos pendentes, e no fim de cada aceitacao se lhe fazia
            # `append({...})`. A lista ficava com objectos E dicionarios: o
            # `len()` contava os dois, e quem lesse o resultado receberia um
            # `MovimentacaoBancaria` dentro de `conciliados`.
            #
            # Duas listas porque e' o que o codigo precisa: `pendentes` sao
            # registos para gravar; `conciliados` sao factos ja' gravados,
            # para mostrar. Misturar as duas e' como um `count()` que conta
            # a mesma coisa duas vezes.

        # Porta 4: gravar so' depois de decidir tudo. `update_fields` e'
        # explicito porque um `.save()` sem lista pode escrever campos que
        # outra sessao mexeu entre a leitura e a gravacao.
        from django.utils import timezone

        data = (agora or timezone.now()).date()
        for item in escrita:
            m = item["movimentacao"]
            l = item["lancamento"]
            m.conciliado = True
            m.data_conciliacao = data
            m.save(update_fields=["conciliado", "data_conciliacao"])
            l.pago = True
            l.data_pagamento = m.data
            l.save(update_fields=["pago", "data_pagamento"])

            conciliados.append(
                {
                    "movimentacao_id": m.pk,
                    "lancamento_id": l.id,
                    "valor": float(abs(Decimal(m.valor))),
                    "confianca": item["confianca"],
                }
            )

    return Resultado(
        conciliados=conciliados,
        recusados=recusados,
        nada_foi_escrito=not escrita,
    )


def aplicar_todas(user, conta, **kwargs) -> None:
    """Recusado de proposito. Ver a razao no topo do modulo."""
    raise NaoPermitido(
        "Não existe 'conciliar tudo'. Cada casamento tem de ser olhado: "
        "dois lançamentos de R$ 1.000 no mesmo mês são idênticos para o "
        "sistema, e só o produtor sabe qual é qual. Peça a lista, veja a "
        "razão de cada uma, e aplique as que estiverem certas."
    )
