"""INTENTS DE CONTAS A PAGAR E A RECEBER — a lacuna F10, utilizavel pela IA.

Duas vezes, como pedido:

  1. POR PEDIDO — os intents deste ficheiro. O produtor pergunta e a IA
     responde.
  2. DE ROTINA — `regra_contas` em `app/ia/contas_proativo.py`, que dispara
     sem ninguem pedir. Um boleto que vence quinta e o produtor soube na
     quinta e' dinheiro a mais na rua.

O QUE A IA **NAO** FAZ AQUI, e porquê
=====================================
- Nao adivinha vencimento. Sem data do produtor, nao ha conta. Um "10/03"
  inventado e' um boleto que o produtor vai pagar.
- Nao diz "esta tudo em dia" quando o que houve foi falha de rede. O
  `fonte_dado` distingue MEDIDO de DECLARADO, e o que nao se sabe diz-se.
- Nao paga nada sem confirmacao. `pagar_conta` escreve; a confirmacao e' o
  que separa "o produtor pediu" de "a IA decidiu".

DAS DESPESAS SEM VENCIMENTO
===========================
`h_contas_a_pagar` (o intent antigo, `intents2.py:260`) era um SOMATORIO:
pegava em `LancamentoFinanceiro` com `pago=False` e devolvia o total. O
`test_80_contas_a_pagar` (app/ia/tests.py:1152) depende desse comportamento.

Duas saidas seriam más: romper o teste (um produtor com despesas registadas
deixava de as ver) ou manter duas fontes de verdade (cada uma com a sua
contagem; escolher entre as duas passa a ser um bug esperando).

A via que fica: `ContaAPagar` e' a fonte de verdade — porque tem
`vencimento` — e as despesas sem data entram marcadas como tal. Uma
`LancamentoFinanceiro` com `pago=False` e' mesmo uma obrigacao; o que nao
sabemos e' QUANDO vence, e isso diz-se em vez de inventar ou esconder.

O alerta de rotina NUNCA usa a data destas: `regra_contas` so le
`ContaAPagar`, que tem vencimento verdadeiro.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation


def _hoje():
    from django.utils import timezone

    return timezone.localdate()


def _dinheiro(v) -> str:
    """`1.234,56` — como o produtor le, nao como a maquina guarda.

    O LCDPR ja corrigiu este ponto e o mesmo erro custa aqui dinheiro:
    `1.234,56` lido com ponto decimal e' 1.23456, e um boleto fica 1000x
    errado.
    """
    try:
        d = Decimal(str(v or 0))
    except (InvalidOperation, ValueError):
        d = Decimal("0")
    inteiro, _, frac = f"{d:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{frac}"


def _prop2(user, params):
    from app.models import Propriedade

    pid = params.get("propriedade") or params.get("propriedade_id")
    qs = Propriedade.objects.filter(user=user)
    if pid:
        return qs.filter(id=pid).first() or qs.first()
    return qs.first()


def _data(bruto):
    """Aceita `2026-03-15`, `15/03/2026` e `15/03`. Devolve `None` se nao der."""
    import datetime as _dt

    if not bruto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m"):
        try:
            return _dt.datetime.strptime(str(bruto), formato).date()
        except (ValueError, TypeError):
            continue
    return None


def _despesas_sem_vencimento(prop):
    """Despesas registadas que ainda nao viraram `ContaAPagar`.

    Sao obrigacoes de que **nao sabemos o vencimento**.

    `conta_origem__isnull=True` impede a mesma despesa de aparecer duas vezes:
    depois de `liquidar`, a conta tem `lancamento` apontado para ela e some
    daqui. Sem esta clausula, pagar uma conta faria o total do "a pagar"
    subir — o mesmo defeito que a NF-e duplicada ja teve no Ampliagro.
    """
    from app.models import LancamentoFinanceiro

    return list(
        LancamentoFinanceiro.objects.filter(
            propriedade=prop,
            tipo="DESPESA",
            pago=False,
            conta_origem__isnull=True,
        ).order_by("data")[:20]
    )


def listar_contas(user, params, ctx):
    """Le contas a pagar e a receber, com as despesas sem data marcadas."""
    from app.models.contas import ContaAPagar, ContaAReceber

    prop = _prop2(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada", "dados": {}}

    hoje = _hoje()
    so_vencidas = bool(params.get("vencidas"))
    limite = int(params.get("limite") or 12)

    def _abertas(modelo, campo):
        qs = modelo.objects.filter(propriedade=prop, estado="ABERTA")
        if so_vencidas:
            qs = qs.filter(**{f"{campo}__lt": hoje})
        return qs.order_by(campo)

    pagar = _abertas(ContaAPagar, "vencimento")
    receber = _abertas(ContaAReceber, "vencimento")

    total_pagar = sum((c.valor for c in pagar), Decimal("0"))
    total_receber = sum((c.valor for c in receber), Decimal("0"))

    vencidas = [c for c in pagar if c.vencida]
    a_vencer = [c for c in pagar if c.vencimento <= hoje + timedelta(days=3)]
    sem_data = _despesas_sem_vencimento(prop)
    total_sem_data = sum((d.valor for d in sem_data), Decimal("0"))

    ctx["fontes"].append("interna:contas")

    if not pagar.count() and not receber.count() and not sem_data:
        # Zero linhas nao e' um total de zero. E' a ideia de que nao ha contas
        # registadas, e a frase tem de dizer isso — `test_81_contas_a_pagar_vazio`
        # (app/ia/tests.py:1171) exige-a.
        #
        # NOTA: aqui NAO e' caso de `sem_dado`. A consulta correu e devolveu
        # zero linhas. "Nenhuma conta" e' a leitura correta; "sem dado" seria
        # mentira.
        return {
            "ok": True,
            "resposta": "Nenhuma conta a pagar ou a receber em aberto.",
            "dados": {
                "total_pagar": 0.0,
                "total_receber": 0.0,
                "qtd_pagar": 0,
                "qtd_receber": 0,
                "vencidas": 0,
                "qtd_sem_data": 0,
                "total_sem_data": 0.0,
                "linhas": [],
                "ids": [],
            },
            "artefato": ("financeiro/contas", "financeiro"),
        }

    linhas = [
        (
            f"lanc-{d.pk}",
            f"sem data de vencimento: {d.descricao or d.categoria} "
            f"{_dinheiro(d.valor)} — confirme a data",
        )
        for d in sem_data
    ]
    vistos = set()

    for c in list(vencidas) + list(a_vencer) + list(pagar)[:limite]:
        if c.pk in vistos:
            continue
        vistos.add(c.pk)
        marca = (
            f"VENCIDA ha {c.dias_atraso} dias"
            if c.vencida
            else f"vence {c.vencimento:%d/%m}"
        )
        quem = c.fornecedor or c.descricao
        carimbo = "" if c.confiavel else "  [data sem origem — confirme]"
        linhas.append((c.pk, f"{marca}: {quem} {_dinheiro(c.valor)}{carimbo}"))

    resposta = (
        f"A pagar: {_dinheiro(total_pagar)} em {pagar.count()} contas. "
        f"A receber: {_dinheiro(total_receber)} em {receber.count()}. "
        f"{len(vencidas)} vencida(s)."
        + (
            f" {len(sem_data)} despesa(s) sem data de vencimento: "
            f"{_dinheiro(total_sem_data)} — confirme a data."
            if sem_data
            else ""
        )
    )
    return {
        "ok": True,
        "resposta": resposta
        + ("\n" + "\n".join(f"- {t}" for _, t in linhas[:limite]) if linhas else ""),
        "dados": {
            "total_pagar": float(total_pagar),
            "total_receber": float(total_receber),
            "qtd_pagar": pagar.count(),
            "qtd_receber": receber.count(),
            "vencidas": len(vencidas),
            "qtd_sem_data": len(sem_data),
            "total_sem_data": float(total_sem_data),
            "linhas": [t for _, t in linhas[:limite]],
            "ids": [pk for pk, _ in linhas[:limite]],
        },
        "artefato": ("financeiro/contas", "financeiro"),
    }


def registar_conta(user, params, ctx):
    """Cria uma conta a pagar ou a receber.

    `vencimento` e' obrigatorio e NAO e' inventado: sem ele, o handler diz
    isso. Um vencimento estimado e' uma data que o produtor vai pagar.
    """
    from app.models.contas import ContaAPagar, ContaAReceber

    prop = _prop2(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada", "dados": {}}

    descricao = (params.get("descricao") or "").strip()
    if len(descricao) < 2:
        return {"ok": False, "erro": "diga o que e' a conta", "dados": {}}

    valor = params.get("valor")
    if valor in (None, "", 0):
        return {"ok": False, "erro": "diga o valor", "dados": {}}

    dia = _data(params.get("vencimento") or params.get("data"))
    if dia is None:
        return {
            "ok": False,
            "erro": (
                "diga a data de vencimento (dd/mm). Nao vou inventar a data: "
                "e' ela que diz quando o dinheiro sai."
            ),
            "dados": {},
        }

    receber = str(params.get("tipo") or "").lower() in (
        "receber",
        "a_receber",
        "cliente",
    )
    ref = params.get("documento") or params.get("documento_ref") or ""
    fonte = (
        "INVENTADO"
        if params.get("sem_data_fiavel")
        else ("MEDIDO" if ref else "DECLARADO")
    )
    contraparte = (params.get("fornecedor") or params.get("cliente") or "").strip()

    comum = dict(
        propriedade=prop,
        descricao=descricao[:200],
        valor=valor,
        vencimento=dia,
        categoria=(params.get("categoria") or "").strip()[:20]
        or ("VENDA_PROD" if receber else "INSUMO"),
        fonte_dado=fonte,
        documento_ref=ref[:60],
    )

    if receber:
        conta = ContaAReceber.objects.create(cliente=contraparte[:200], **comum)
        tipo_txt = "a receber"
    else:
        conta = ContaAPagar.objects.create(fornecedor=contraparte[:200], **comum)
        tipo_txt = "a pagar"

    ctx["fontes"].append("interna:contas")
    aviso = (
        " Confirme a data com a fonte antes de fechar o pagamento."
        if fonte != "MEDIDO"
        else ""
    )
    return {
        "ok": True,
        "resposta": (
            f"Conta {tipo_txt} registada: {descricao}, "
            f"{_dinheiro(valor)}, vencimento {dia:%d/%m/%Y}.{aviso}"
        ),
        "dados": {
            "id": conta.pk,
            "tipo": tipo_txt,
            "vencimento": dia.isoformat(),
            "valor": float(valor),
            "fonte_dado": fonte,
        },
        "artefato": ("financeiro/contas", "financeiro"),
    }


def pagar_conta(user, params, ctx):
    """Baixa uma conta e escreve o `LancamentoFinanceiro` que o LCDPR le.

    `liquidar` vive no modelo, nao aqui: a regra e' a mesma venha pela IA, pelo
    produtor ou pela fila offline. Tres copias da regra e' tres sitios onde um
    deles esquece o lancamento e o LCDPR deixa de fechar.
    """
    from app.models.contas import ContaAPagar

    prop = _prop2(user, params)
    if not prop:
        return {"ok": False, "erro": "nenhuma propriedade encontrada", "dados": {}}

    cid = params.get("id") or params.get("conta_id")
    qs = ContaAPagar.objects.filter(propriedade=prop)
    conta = (
        qs.filter(pk=cid).first()
        if cid
        else qs.filter(estado="ABERTA").order_by("vencimento").first()
    )
    if not conta:
        return {"ok": False, "erro": "nenhuma conta em aberto", "dados": {}}

    dia = _data(params.get("data") or params.get("data_pagamento")) or _hoje()

    conta_bancaria = None
    cb = params.get("conta_bancaria") or params.get("conta")
    if cb:
        from app.models import ContaBancaria

        conta_bancaria = ContaBancaria.objects.filter(propriedade=prop, id=cb).first()

    lanc = conta.liquidar(
        data_pagamento=dia,
        conta_bancaria=conta_bancaria,
        user=user,
    )
    ctx["fontes"].append("interna:contas")
    return {
        "ok": True,
        "resposta": (
            f"Pago: {conta.descricao}, {_dinheiro(conta.valor)}, "
            f"em {dia:%d/%m/%Y}. Lancamento {lanc.pk} escrito para o LCDPR."
        ),
        "dados": {
            "conta_id": conta.pk,
            "lancamento_id": lanc.pk,
            "valor": float(conta.valor),
            "data": dia.isoformat(),
        },
        "artefato": ("financeiro/contas", "financeiro"),
    }


#: Onde os intents sao registados
#: ==============================
#: Nao ha `INTENTS_CONTAS` aqui, e a ausencia e' deliberada.
#:
#: A definicao UNICA vive em `app/ia/intents2.py::INTENTS2`, ao lado dos
#: outros intents, porque e' ai que `app/ia/intents.py` vai buscar com
#: `INTENTS.update(INTENTS2)`.
#:
#: Tive aqui uma segunda definicao e `test_nao_ha_duplicados_reais` apanhou:
#: o mesmo nome com conteudos diferentes e' uma colisao real, porque o que
#: executa passa a depender da ordem de import. Este ficheiro fica com os
#: HANDLERS; a tabela fica no sitio onde todas as outras estao.
