"""Testes do intent de conciliacao bancaria.

O que se testa aqui NAO e' se a funcao devolve um dicionario. E':
- o produtor nao tem de pedir o nome da conta;
- ele recebe a resposta que faz a pergunta dele, e nao um 'ok';
- e o mais importante: **nao escreve nada**.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from app.models import (
    ContaBancaria,
    LancamentoFinanceiro,
    MovimentacaoBancaria,
    Propriedade,
)


@pytest.fixture
def cenario(db):
    u = User.objects.create_user(username="lucas", password="x")
    p = Propriedade.objects.create(
        user=u, nome="Faz", area_total=50, uf="MT", cidade="Sorriso"
    )
    c = ContaBancaria.objects.create(
        propriedade=p, banco="BB", agencia="1", conta="9", digito="0"
    )
    return {"u": u, "p": p, "c": c, "hoje": date(2026, 10, 6)}


def _mov(c, data, valor, tipo="DEBITO", texto="COMPRA"):
    return MovimentacaoBancaria.objects.create(
        conta=c["c"], data=data, descricao=texto, valor=Decimal(valor), tipo=tipo
    )


def _lanc(c, data, valor, tipo="DESPESA", pago=False):
    return LancamentoFinanceiro.objects.create(
        propriedade=c["p"],
        tipo=tipo,
        categoria="INSUMO",
        valor=Decimal(valor),
        data=data,
        pago=pago,
    )


def test_intent_responde_a_pergunta_e_nao_diz_ok(cenario, tmp_path):
    from app.ia.intents2 import h_conciliar_banco

    c = cenario
    d = c["hoje"]
    _mov(c, d, "1500.00", "DEBITO", "COMPRA NAO REGISTADA")
    _mov(c, d, "45000.00", "DEBITO", "PAGAMENTO FERTILIZANTE")
    _lanc(c, d, "45000.00")

    ctx = {"fontes": []}
    out = h_conciliar_banco(c["u"], {}, ctx)

    assert out["ok"] is True
    r = out["resposta"]
    # o que o produtor QUER saber: tem algo sem registo?
    assert "Nao ha nenhum lancamento" in r or "sem correspondencia" in r.lower()
    # e nao pode ser so' um numero de 'tudo bem'
    assert "1" in r
    # tem de dizer que nada foi escrito
    assert "confirmacao" in r.lower()


def test_intent_diz_o_que_falta_e_nao_apenas_o_que_ficou(cenario):
    from app.ia.intents2 import h_conciliar_banco

    c = cenario
    d = c["hoje"]
    # 2 casam
    _lanc(c, d, "1000.00")
    _lanc(c, d, "2000.00")
    _mov(c, d, "1000.00", "DEBITO", "PAGAMENTO A")
    _mov(c, d, "2000.00", "DEBITO", "PAGAMENTO B")
    # 3 nao casam
    for i in range(3):
        _mov(c, d + timedelta(days=i), str(700 * (i + 1)), "DEBITO", "EXTRA %d" % i)

    ctx = {"fontes": []}
    out = h_conciliar_banco(c["u"], {}, ctx)

    dados = out["dados"]
    assert dados["total_propostas"] == 2
    assert dados["total_nao_casadas"] == 3


def test_intent_nao_escreve_nada(cenario):
    """O INTENT e' de leitura. Este teste e' o que garante que um dia
    alguem nao acrescenta `conciliar_conta()` dentro do handler e o produtor
    acorda com contas baixadas a pago que nao pagou."""
    from app.ia.intents2 import h_conciliar_banco

    c = cenario
    d = c["hoje"]
    mov = _mov(c, d, "5000.00", "DEBITO", "PAGAMENTO")
    lanc = _lanc(c, d, "5000.00")

    before_mov = MovimentacaoBancaria.objects.count()
    h_conciliar_banco(c["u"], {}, {"fontes": []})

    mov.refresh_from_db()
    lanc.refresh_from_db()
    assert mov.conciliado is False, "o handler escreveu no extrato"
    assert lanc.pago is False, "o handler baixou a conta a pago"
    assert MovimentacaoBancaria.objects.count() == before_mov


def test_transferencia_aparece_na_resposta(cenario):
    """O produtor tem de ver que ha' uma transferencia na lista, porque
    'nao casou' sem 'porque' deixa-o a pensar que o sistema falhou."""
    from app.ia.intents2 import h_conciliar_banco

    c = cenario
    d = c["hoje"]
    _mov(c, d, "20000.00", "DEBITO", "TRANSFERENCIA ENTRE CONTAS")

    out = h_conciliar_banco(c["u"], {}, {"fontes": []})

    assert out["dados"]["transferencias_suspeitas"] == 1


def test_conta_sem_extrato_nao_diz_que_falta_algo(cenario):
    """Conta vazia != conta com pendencia. A tela precisa de distinguir,
    e o texto tambem."""
    from app.ia.intents2 import h_conciliar_banco

    out = h_conciliar_banco(cenario["u"], {}, {"fontes": []})

    assert "vazio" in out["resposta"].lower()


def test_isolamento_por_produtor(cenario):
    """A conta do vizinho nao aparece na minha resposta. Este e' o teste
    que garante que a conciliacao nao vaza dinheiro de outra fazenda."""
    from app.ia.intents2 import h_conciliar_banco

    c = cenario
    vizinho = User.objects.create_user(username="v", password="x")
    pv = Propriedade.objects.create(
        user=vizinho, nome="Deles", area_total=10, uf="GO", cidade="Goias"
    )
    cv = ContaBancaria.objects.create(
        propriedade=pv, banco="Outro", agencia="1", conta="1", digito="1"
    )
    MovimentacaoBancaria.objects.create(
        conta=cv,
        data=c["hoje"],
        descricao="SEGREDO",
        valor=Decimal("999999.00"),
        tipo="DEBITO",
    )

    out = h_conciliar_banco(c["u"], {}, {"fontes": []})

    assert "SEGREDO" not in out["resposta"]
    assert all(x["conta_id"] != cv.pk for x in out["dados"]["por_conta"])
