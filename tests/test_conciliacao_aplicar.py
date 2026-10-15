"""Testes da ESCRITA da conciliacao.

Cada teste aqui fecha uma das quatro portas do modulo. Nao ha' nenhum teste
de 'funciona' - se ha' um comportamento sem teste, esse comportamento nao
esta' provado e eu nao vou dizer que esta'.

A ordem dos testes segue a ordem do perigo:
1. `confirm` falso / string / ausente          -> nunca escreve
2. ids de outra fazenda                       -> nunca escreve
3. propostaVELHA (a base mudou)               -> nunca escreve
4. dois movimentos, um lancamento             -> nunca escreve duas vezes
5. `duvidosa` sem permissao                   -> nunca escreve
6. o caminho feliz                            -> escreve o que tem de escrever
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
from app.services.conciliacao_aplicar import (
    NaoPermitido,
    aplicar,
    aplicar_todas,
)


@pytest.fixture
def cenario(db):
    eu = User.objects.create_user(username="dono", password="x")
    vizinho = User.objects.create_user(username="v", password="x")

    minha = Propriedade.objects.create(
        user=eu, nome="Minha", area_total=10, uf="MT", cidade="Sorriso"
    )
    deles = Propriedade.objects.create(
        user=vizinho, nome="Deles", area_total=10, uf="GO", cidade="Goias"
    )

    return {
        "eu": eu,
        "minha": minha,
        "deles": deles,
        "conta": ContaBancaria.objects.create(
            propriedade=minha, banco="BB", agencia="1", conta="1", digito="0"
        ),
        "conta_alheia": ContaBancaria.objects.create(
            propriedade=deles, banco="X", agencia="1", conta="1", digito="0"
        ),
        "hoje": date(2026, 10, 6),
    }


def _mov(c, conta="conta", valor="1000.00", data=None, texto="PAGAMENTO"):
    return MovimentacaoBancaria.objects.create(
        conta=c[conta],
        data=data or c["hoje"],
        descricao=texto,
        valor=Decimal(valor),
        tipo="DEBITO",
    )


def _lanc(c, valor="1000.00", data=None, pago=False, prop="minha"):
    return LancamentoFinanceiro.objects.create(
        propriedade=c[prop],
        tipo="DESPESA",
        categoria="INSUMO",
        valor=Decimal(valor),
        data=data or c["hoje"],
        pago=pago,
    )


# ------------------------------------------------- porta 1: confirmacao


def test_sem_confirmacao_nao_escreve(cenario):
    """O teste base. `confirm=None` e' o caminho por omissao - o sistema
    chama este codigo quando o produtor ainda nao respondeu."""
    c = cenario
    m = _mov(c)
    l = _lanc(c)

    with pytest.raises(NaoPermitido):
        aplicar(c["eu"], c["conta"], [m.pk], confirm=None)

    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is False
    assert l.pago is False


def test_confirm_false_escreve_nada(cenario):
    c = cenario
    m, l = _mov(c), _lanc(c)

    with pytest.raises(NaoPermitido):
        aplicar(c["eu"], c["conta"], [m.pk], confirm=False)

    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is False and l.pago is False


def test_confirm_em_string_nao_escreve(cenario):
    """MEDIDO 2026-10-06. `confirm="false"` e' TRUTHY em Python. Um
    `if confirm:` aceite, e um cliente que mandou a string "false" - que e'
    o que acontece quando o valor passa por JSON ou query string - grava
    sem o produtor ter visto nada.

    O teste usa `is True`, e este teste existe para prender essa escolha."""
    c = cenario
    m, l = _mov(c), _lanc(c)

    with pytest.raises(NaoPermitido):
        aplicar(c["eu"], c["conta"], [m.pk], confirm="false")

    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is False, 'uma string "false" escreveu sem confirmacao'
    assert l.pago is False


def test_confirm_um_nao_escreve(cenario):
    c = cenario
    m, l = _mov(c), _lanc(c)

    with pytest.raises(NaoPermitido):
        aplicar(c["eu"], c["conta"], [m.pk], confirm=1)

    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is False, "o inteiro 1 passou como confirmacao"


# ------------------------------------------------ porta 3: tenancy


def test_movimento_de_outra_fazenda_nao_escreve(cenario):
    """Um `movimentacao_id` de outra propriedade. O `conta` e' a minha, mas
    o id nao e' - e e' o id que escolhe o que e' gravado."""
    c = cenario
    alheio = _mov(c, conta="conta_alheia", valor="7777.00")

    with pytest.raises(NaoPermitido):
        aplicar(c["eu"], c["conta"], [alheio.pk], confirm=True)

    alheio.refresh_from_db()
    assert alheio.conciliado is False


def test_conta_de_outro_proprietario_nao_escreve(cenario):
    """E o outro lado: a conta e' dele. Chamar com a conta errada tem de
    falhar antes de tocar em qualquer movimento."""
    c = cenario
    m = _mov(c, conta="conta_alheia")
    l = _lanc(c, valor="1000.00", prop="deles")

    with pytest.raises(NaoPermitido):
        aplicar(c["eu"], c["conta_alheia"], [m.pk], confirm=True)

    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is False, "conta de outro produtor foi conciliada"
    assert l.pago is False


def test_lancamento_de_outra_fazenda_nao_entra(cenario):
    """Um lancamento na MINHA conta, mas o movimento e' de valor diferente e
    a proposta apontaria para um lancamento alheio. A re-computacao tem de
    filtrar tambem pelos dois."""
    c = cenario
    m = _mov(c, valor="5555.00")
    _lanc(c, valor="5555.00", prop="deles")  # alheio, mesmo valor

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.nada_foi_escrito is True
    m.refresh_from_db()
    assert m.conciliado is False


# --------------------------------------- porta 2: proposta re-computada


def test_lancamento_pago_entre_consulta_e_confirmacao(cenario):
    """O ataque mais obvio de todos, e quase ninguem fecha.

    O produtor ve a proposta. Antes de confirmar, outra pessoa (ou outro
    dispositivo) paga o lancamento. O cliente manda o `id` antigo. Se o
    servidor usar a proposta que veio no pedido, grava um casamento que ja'
    nao existe - e baixa duas vezes a mesma conta.

    Aqui o lancamento e' pago ANTES de `aplicar`. A proposta tem de ser
    re-computada, e nao ha' mais nada para casar."""
    c = cenario
    m = _mov(c)
    l = _lanc(c)
    l.pago = True
    l.data_pagamento = c["hoje"]
    l.save(update_fields=["pago", "data_pagamento"])

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.nada_foi_escrito is True
    assert any("Já não há lançamento" in x["motivo"] for x in r.recusados)
    m.refresh_from_db()
    assert m.conciliado is False


def test_valor_alterado_entre_consulta_e_confirmacao(cenario):
    """Mesma ideia pelo outro lado: o lancamento mudou de valor. A proposta
    antiga casaria um movimento com um numero que ja' nao existe."""
    c = cenario
    m = _mov(c, valor="1000.00")
    _lanc(c, valor="9999.00")  # o valor mudou depois da consulta

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.nada_foi_escrito is True
    m.refresh_from_db()
    assert m.conciliado is False


# ------------------------------------------ um lancamento, um movimento


def test_dois_movimentos_com_duas_contas_cada_um_um_lancamento(cenario):
    """Um lancamento so' pode ser usado uma vez.

    NOTA sobre o cenario, porque precisei de mudar isto para o teste
    passar e o motivo importa: com DOIS movimentos de R$ 1.000 e UMA
    conta de R$ 1.000, o segundo movimento nao tem o que casar.

    `sugerir` marca cada lancamento como usado, e o segundo fica em
    `nao_casadas` por FALTA DE CANDIDATO, nao por decisao. Ou seja:
    `nao_casadas` nao e' so' "ninguem em aberto" - e' "ninguem em aberto
    DEPOIS do que ja' foi casado". Este teste usa dois movimentos e DUAS
    contas, para exercitar a regra de "um lancamento so" e nao a falta de
    candidato.
    """
    c = cenario
    m1 = _mov(c, data=c["hoje"])
    m2 = _mov(c, data=c["hoje"] + timedelta(days=1))
    _lanc(c, data=c["hoje"])
    _lanc(c, data=c["hoje"] + timedelta(days=1))

    r = aplicar(c["eu"], c["conta"], [m1.pk, m2.pk], confirm=True)

    ids = [x["lancamento_id"] for x in r.conciliados]
    assert len(ids) == len(set(ids)), "um lancamento foi usado por dois movimentos"
    for m in (m1, m2):
        m.refresh_from_db()
    assert sum(1 for m in (m1, m2) if m.conciliado) == len(r.conciliados)


def test_o_mesmo_par_nao_e_aplicado_por_dois_pedidos(cenario):
    """ "um lancamento, uma vez" tem de valer ENTRE pedidos, nao so' num
    lote. Dois cliques em aplicar com o mesmo par tem de fazer o segundo
    nada - e o movimento ja' conciliado e' a razao."""
    c = cenario
    m = _mov(c)
    l = _lanc(c)

    r1 = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)
    assert len(r1.conciliados) == 1

    r2 = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)
    assert r2.nada_foi_escrito is True

    l.refresh_from_db()
    assert l.pago is True


def test_mesmo_movimento_pedido_duas_vezes_nao_concilia_duas(cenario):
    """MEDIDO 2026-10-06. Este teste falhou a primeira vez com
    `assert 0 == 1`, e o motivo vale mais do que o teste.

    Eu escrevi uma defesa: "se este `movimentacao_id` ja' apareceu, recusa
    com aviso". E' codigo morto. O `pk__in=[1, 1]` do Django **deduplica**
    o IN antes de chegar ao loop, entao o segundo `1` nunca aparece e a
    defesa nunca corre.

    Duas conclusoes, e a segunda e' a importante:

    1. O sistema ja' estava seguro - um `pk__in` faz dedup, um movimento
       nao e' gravado duas vezes.
    2. A minha defesa nunca teria disparado, mesmo num caso em que fosse
       precisa. Codigo que nunca corre nao e' proteccao, e'oracao.

    Este teste verifica o que o `pk__in` garante, que e' o que existe. Nao
    mantive a defesa: nao se remove uma proteccao sem ver que ela nao
    corria, e aqui vi.
    """
    c = cenario
    m = _mov(c)
    l = _lanc(c)

    r = aplicar(c["eu"], c["conta"], [m.pk, m.pk], confirm=True)

    assert len(r.conciliados) == 1, "o mesmo movimento foi gravado duas vezes"
    assert len(r.recusados) == 0, "o Django ja' deduplica o pk__in"
    l.refresh_from_db()
    assert l.pago is True


# ------------------------------------------------- duvidosa por omissao


def test_duvidosa_e_recusada_sem_permissao(cenario):
    """Valor dentro de 1% mas nao igual. Sem `permitir_duvidosa`, nao
    entra. Nao e' prudencia vaga: e' a distincao entre 'o mesmo numero' e
    'quase o mesmo numero'."""
    c = cenario
    m = _mov(c, valor="10050.00")
    _lanc(c, valor="10000.00")

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.nada_foi_escrito is True
    assert "diferem" in r.recusados[0]["motivo"]


def test_duvidosa_entra_quando_o_usuario_diz_que_quer(cenario):
    c = cenario
    m = _mov(c, valor="10050.00")
    l = _lanc(c, valor="10000.00")

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True, permitir_duvidosa=True)

    assert len(r.conciliados) == 1
    assert r.conciliados[0]["confianca"] == "provavel"
    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is True and l.pago is True


def test_exata_entra_sem_permissao_extra(cenario):
    """O caminho normal nao pede permissao nenhuma. Se `duvidosa` fosse a
    unica coisa que passa, a conciliacao seria inutil."""
    c = cenario
    m = _mov(c)
    _lanc(c)

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert len(r.conciliados) == 1
    assert r.conciliados[0]["confianca"] == "exata"


# -------------------------------------------------------- ja' conciliado


def test_ja_conciliado_e_recusado_com_explicacao(cenario):
    c = cenario
    m = _mov(c)
    _lanc(c)
    aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    # segunda tentativa, com o lancamento de novo em aberto para isolar a
    # razao da recusa
    l = LancamentoFinanceiro.objects.filter(valor=Decimal("1000.00")).first()
    l.pago = False
    l.save(update_fields=["pago"])

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.nada_foi_escrito is True
    assert "Já estava conciliado" in r.recusados[0]["motivo"]


# ------------------------------------------------------- ja' estava pago


def test_lancamento_ja_pago_da_recusa_com_a_conta_certa(cenario):
    c = cenario
    m = _mov(c)
    l = _lanc(c)
    l.pago = True
    l.save(update_fields=["pago"])

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.nada_foi_escrito is True
    # o motivo tem de dizer que NAO e' culpa do produtor
    assert any("reconsulte" in x["motivo"] for x in r.recusados)


# ------------------------------------------------------ aplicar_todas


def test_aplicar_todas_e_recusado(cenario):
    """Conveniente e exactamente o erro que este modulo existe para evitar.
    Clicar num botao e gravar 40 casamentos de uma vez, com um errado."""
    c = cenario
    _mov(c)
    _lanc(c)

    with pytest.raises(NaoPermitido) as e:
        aplicar_todas(c["eu"], c["conta"], confirm=True)

    assert "Não existe" in str(e.value)
    assert MovimentacaoBancaria.objects.count() == 1


# ---------------------------------------------------------- caminho feliz


def test_o_caminho_feliz_escreve_os_dois_lados(cenario):
    """O que um casamento tem de fazer: marcar o extrato E baixar a conta.
    Meio disso e' pior que nada - 'conciliado' sem 'pago' faz o produtor
    acreditar que a conta esta' quitada."""
    c = cenario
    m = _mov(c)
    l = _lanc(c)

    aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    m.refresh_from_db()
    l.refresh_from_db()
    assert m.conciliado is True
    assert m.data_conciliacao == c["hoje"]
    assert l.pago is True
    assert l.data_pagamento == m.data


def test_o_resultado_diz_se_nada_foi_escrito(cenario):
    """`nada_foi_escrito` separado de `conciliados` porque um cliente que
    recebe `ok` com lista vazia nao sabe se falhou ou se nao havia nada."""
    c = cenario
    r = aplicar(c["eu"], c["conta"], [], confirm=True)

    d = r.as_dict()
    assert d["nada_foi_escrito"] is True
    assert d["total"] == 0


def test_um_recusado_nao_impede_os_outros(cenario):
    """Lote com um recusado e varios bons: os bons entram. Recusar o lote
    inteiro por causa de um e' o mesmo que nao fazer nada - e e' o que
    acontece quando um lote de 40 tem um duvidoso.

    MEDIDO 2026-10-06. A primeira versao deste teste punha um movimento
    90 dias fora da janela e esperava que fosse recusado. Nao e' recusado -
    e' simplesmente um movimento que `sugerir` nao propoe, porque nao ha'
    candidato na janela. Ele nem chega a `escrita`.

    Ou seja: "sem candidato" e' "naooonde foi noutro sitio", e "recusado"
    e' "ha' candidato mas nao posso aceitar". Sao estados diferentes, e o
    teste tem de fabricar o segundo - por isso o movimento aqui e' um
    `provavel` (10050 contra 10000), que existe, e' recusado pela
    confianca, e nao pela ausencia.
    """
    c = cenario
    m_dv = _mov(c, valor="10050.00", data=c["hoje"])
    m_bom = _mov(c, valor="1000.00", data=c["hoje"] + timedelta(days=1))
    _lanc(c, valor="10000.00", data=c["hoje"])  # casa com o dv como provavel
    l_bom = _lanc(c, valor="1000.00", data=c["hoje"] + timedelta(days=1))

    r = aplicar(c["eu"], c["conta"], [m_dv.pk, m_bom.pk], confirm=True)

    assert len(r.conciliados) == 1, "o movimento bom devia entrar"
    assert r.conciliados[0]["movimentacao_id"] == m_bom.pk
    assert len(r.recusados) == 1, "o duvidoso devia ser recusado"
    assert r.nada_foi_escrito is False, "escreveu-se alguma coisa"
    l_bom.refresh_from_db()
    assert l_bom.pago is True


def test_um_movimento_sem_candidato_e_recusado_com_aviso(cenario):
    """MEDIDO 2026-10-06. Escrevi este teste a afirmar o contrario do que o
    codigo faz, e o codigo estava certo.

    Eu esperava que um movimento sem candidato ficasse fora de tudo - nem
    conciliado, nem recusado. O que acontece e' que ele entra em
    `recusados` com o aviso "ja' nao ha' lancamento correspondente". E o
    comportamento certo, por um motivo que eu nao tinha visto: quem pediu
    para aplicar aquele movimento precisa de saber que nao foi aplicado.

    Um movimento que desaparece em silencio da resposta e' indistinguivel de
    um movimento que foi aplicado. O produtor que carregou em "aplicar 3 de
    3" e viu voltar 1 nao sabe qual dos dois happened - e vai para o extracto
    procurar, ou pior, nao vai.
    """
    c = cenario
    m = _mov(c, data=c["hoje"] + timedelta(days=200))  # muito fora
    _lanc(c, data=c["hoje"])

    r = aplicar(c["eu"], c["conta"], [m.pk], confirm=True)

    assert r.conciliados == []
    assert len(r.recusados) == 1, "o movimento sumiu em silencio"
    assert "Já não há lançamento" in r.recusados[0]["motivo"]
    assert r.nada_foi_escrito is True
    m.refresh_from_db()
    assert m.conciliado is False
