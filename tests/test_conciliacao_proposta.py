"""Testes da conciliacao por PROPOSTA.

Cada teste aqui existe porque ha' um erro concreto que ele apanha. Nao ha'
nenhum teste de "funciona".

O teste mais importante do ficheiro e' `test_transferencia_nao_e_proposta`.
Ele fixa uma decisao que, mudada, produz numeros ERRADOS em DUAS direcoes
ao mesmo tempo - e por isso nao aparece em nenhuma coluna.
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
from app.services.conciliacao_proposta import (
    CONFIANCA_DUVIDOSA,
    CONFIANCA_EXATA,
    CONFIANCA_NENHUMA,
    CONFIANCA_PROVAVEL,
    resumo_para_ia,
    sugerir,
)


@pytest.fixture
def cenario(db):
    user = User.objects.create_user(username="banca", password="x")
    prop = Propriedade.objects.create(
        user=user, nome="Fazenda", area_total=100, uf="MT", cidade="Sorriso"
    )
    conta = ContaBancaria.objects.create(
        propriedade=prop, banco="Banco", agencia="1", conta="2", digito="3"
    )
    return {"user": user, "prop": prop, "conta": conta, "hoje": date(2026, 10, 6)}


def _debito(c, data, valor, texto="PAGAMENTO FORNECEDOR"):
    return MovimentacaoBancaria.objects.create(
        conta=c["conta"],
        data=data,
        descricao=texto,
        valor=Decimal(valor),
        tipo="DEBITO",
    )


def _credito(c, data, valor, texto="RECEBIMENTO CLIENTE"):
    return MovimentacaoBancaria.objects.create(
        conta=c["conta"],
        data=data,
        descricao=texto,
        valor=Decimal(valor),
        tipo="CREDITO",
    )


def _despesa(c, data, valor, pago=False, categoria="INSUMO"):
    return LancamentoFinanceiro.objects.create(
        propriedade=c["prop"],
        tipo="DESPESA",
        categoria=categoria,
        valor=Decimal(valor),
        data=data,
        pago=pago,
    )


# ---------------------------------------------------------------- exatas


def test_valor_e_data_iguais_dao_confianca_exata(cenario):
    """O caso que a conciliacao tem de acertar SEMPRE: mesmo numero, mesma
    semana. E' o que os dois sistemas chamam de 'a mesma conta'."""
    d = cenario["hoje"]
    _debito(cenario, d, "45000.00")
    lanc = _despesa(cenario, d - timedelta(days=2), "45000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 1
    p = r.propostas[0]
    assert p.confianca == CONFIANCA_EXATA
    assert p.lancamento_id == lanc.id
    # A razao tem de citar os dois numeros. "Casou porque sim" nao e' razao.
    assert "45" in p.porque


def test_proposta_nao_escreve_nada_no_banco(cenario):
    """A PROPOSTA tem de ser uma proposta.

    Este e' o teste que impede o `conciliar_conta` de ser copiado para aqui.
    Ele escreve - `mov.conciliado = True`, `cand.pago = True`, sem perguntar.
    Se este teste falhar, alguem juntou escrita ao caminho de leitura.
    """
    d = cenario["hoje"]
    mov = _debito(cenario, d, "1000.00")
    lanc = _despesa(cenario, d, "1000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 1
    mov.refresh_from_db()
    lanc.refresh_from_db()
    assert mov.conciliado is False, "a sugestao escreveu no extrato"
    assert lanc.pago is False, "a sugestao baixou a conta a pago sem confirmacao"
    assert r.ja_conciliadas == 0


# -------------------------------------------------------------- tolerancia


def test_diferenca_de_um_centavo_e_arredondamento(cenario):
    """45.000,00 escrito pelo produtor e 45000.00 no extrato sao o mesmo
    numero visto de dois jeitos. Isto NAO e' 'quase igual' - e' a mesma
    conta, e classify-lo como tal evita um falso 'nao conciliado'."""
    d = cenario["hoje"]
    _debito(cenario, d, "45000.01")
    _despesa(cenario, d, "45000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 1
    assert r.propostas[0].confianca == CONFIANCA_EXATA


def test_diferenca_acima_de_um_por_cento_nao_casa(cenario):
    """1% de folga tem um limite, e o limite tem de ser um limite. Sem este
    teste, 'dentro da tolerancia' vira 'qualquer coisa perto'."""
    d = cenario["hoje"]
    _debito(cenario, d, "50000.00")
    _despesa(cenario, d, "40000.00")  # 20% de diferenca

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 0
    assert len(r.nao_casadas) == 1


def test_diferenca_real_e_marcada_como_duvidosa_nao_como_certa(cenario):
    """1% de diferenca NAO e' a mesma conta. Mas tambem nao e' lixo: e' o
    caso que o produtor QUER ver primeiro. Por isso fica, com o aviso
    escrito - e o aviso diz o que acontece se ele aceitar errado."""
    d = cenario["hoje"]
    _debito(cenario, d, "10050.00")  # 0.5% acima
    _despesa(cenario, d, "10000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 1
    assert r.propostas[0].confianca == CONFIANCA_PROVAVEL
    assert r.propostas[0].exige_confirmacao is True
    assert "NAO e' este" in r.propostas[0].porque


# ------------------------------------------------------------ nao casadas


def test_dinheiro_sem_lancamento_e_explicado(cenario):
    """A PERGUNTA que o produtor faz todo o mes e' esta: o que veio do
    extrato que eu nao registrei? Um sistema que so diz quantos casaram
    deixa essa pergunta sem resposta."""
    d = cenario["hoje"]
    _debito(cenario, d, "7777.00", "COMPRA NAO LANÇADA")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.nao_casadas) == 1
    assert len(r.propostas) == 0
    assert "nao foi registado" in r.nao_casadas[0].motivo


def test_data_fora_da_janela_diz_que_e_data(cenario):
    """Nao basta dizer 'nao casou'. A causa importa: um lancamento de marco
    que aparece no extrato de outubro e' outra coisa, e saber isso evita
    procurar em erro durante uma tarde."""
    d = cenario["hoje"]
    _debito(cenario, d, "5000.00")
    _despesa(cenario, d - timedelta(days=60), "5000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.nao_casadas) == 1
    assert "data" in r.nao_casadas[0].motivo.lower()


# ----------------------------------------------------------- transferencia


def test_transferencia_nao_e_proposta(cenario):
    """O teste que mais importa deste ficheiro.

    TRANSFERENCIA ENTRE CONTAS DA PROPRIA FAZENDA nao e' receita nem
    despesa. Um sistema que a conta como uma das duas mente nos DOIS
    lados: a receita esta inflada E a despesa tambem.

    E o pior tipo de bug, porque e' simetrico. Os dois totais fecham, a
    conciliacao parece certa, e a propriedade inteira aparece errada pela
    mesma quantia. Nenhum teste de 'os totais batem" o apanha.
    """
    d = cenario["hoje"]
    mov = _debito(
        cenario,
        d,
        "20000.00",
        "TRANSFERENCIA ENTRE CONTAS PROPRIA FAZENDA",
    )
    # existe ate um lancamento de despesa do mesmo valor, para provar que a
    # regra da transferencia ganha ao valor identico
    _despesa(cenario, d, "20000.00", categoria="TRANSFERENCIA")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 0, "transferencia interna foi casada como despesa"
    assert len(r.nao_casadas) == 1
    n = r.nao_casadas[0]
    assert n.suspeita_transferencia is True
    assert r.transferencias_suspeitas[0].movimentacao_id == mov.pk
    assert "so mudou de conta" in n.motivo


def test_pix_com_folga_e_transferencia_suspeita(cenario):
    """'PIX' sozinho e' fraco - ha' pix de cliente. Mas e' melhor sinalizar
    para o produtor olhar do quecalar automaticamente. O custo de errar
    aqui e' do lado seguro: sobram linhas para ele ver."""
    d = cenario["hoje"]
    _debito(cenario, d, "5000.00", "PIX ENVIADO CONTA INTERNA")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 0
    assert r.nao_casadas[0].suspeita_transferencia is True


# ------------------------------------------------------------- ja' feitos


def test_ja_conciliada_nao_volta_como_proposta(cenario):
    """Uma movimentacao ja' conciliada nao e' uma proposta - e' historico.
    Sem este filtro, a tela mostraria tudo duas vezes e o produtor nao
    saberia o que falta fazer."""
    d = cenario["hoje"]
    mov = _debito(cenario, d, "1000.00")
    mov.conciliado = True
    mov.save(update_fields=["conciliado"])
    _despesa(cenario, d, "1000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    assert len(r.propostas) == 0
    assert r.ja_conciliadas == 1


def test_incluir_conciliadas_quando_pedido(cenario):
    """Quem quer o historico pede. O default e' nao mostrar."""
    d = cenario["hoje"]
    mov = _debito(cenario, d, "1000.00")
    mov.conciliado = True
    mov.save(update_fields=["conciliado"])
    _despesa(cenario, d, "1000.00")

    r = sugerir(cenario["user"], cenario["conta"], incluir_conciliadas=True)

    assert len(r.propostas) == 1


# ----------------------------------------------------- um para um apenas


def test_lancamento_nao_e_usado_por_dois_movimentos(cenario):
    """Duas linhas de extrato do mesmo valor nao podem baixar a MESMA
    conta a pago duas vezes - a segunda criaria um pagamento fantasma."""
    d = cenario["hoje"]
    _debito(cenario, d, "1000.00")
    _debito(cenario, d + timedelta(days=1), "1000.00")
    lanc = _despesa(cenario, d, "1000.00")
    _despesa(cenario, d + timedelta(days=1), "1000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    usados = [p.lancamento_id for p in r.propostas]
    assert len(usados) == len(set(usados)), "um lancamento foi usado duas vezes"
    assert lanc.id in usados


# ------------------------------------------------------------- o resumo IA


def test_resumo_nao_finge_que_acabou(cenario):
    """18 conciliadas e 5 por fazer nao e' 'tudo certo'. O resumo que
    esconde as 5 faz o produtor fechar o mes e descobrir o problema no
    mes seguinte."""
    d = cenario["hoje"]
    _despesa(cenario, d, "1000.00")
    _debito(cenario, d, "1000.00")
    for i in range(5):
        _debito(cenario, d, str(500 * (i + 1)), "SEM LANCAMENTO %d" % i)

    r = sugerir(cenario["user"], cenario["conta"])
    texto = resumo_para_ia(r)

    assert "1 movimento" in texto
    # tem de dizer as duas coisas
    assert "SEM LANCAMENTO" in texto or "Nao ha nenhum lancamento" in texto
    assert "confirmacao" in texto.lower()


def test_resumo_de_conta_vazia_nao_finge_que_casou_nada(cenario):
    """Conta sem movimento nenhum e' diferente de conta com 50 por
    conciliar. `tem_dados` e' a distincao, e sem ela a tela mostrava uma
    tabela vazia como se fosse 'nada para fazer'."""
    r = sugerir(cenario["user"], cenario["conta"])

    assert r.tem_dados is False
    assert r.as_dict()["tem_dados"] is False
    assert "vazio" in resumo_para_ia(r).lower()


def test_as_dict_e_json_serializavel(cenario):
    """A fronteira JSON. `Decimal` e `date` nao passam em json.dumps - se
    este teste falhar, a tela rebenta em runtime em vez de devolver 500
    limpo."""
    import json

    d = cenario["hoje"]
    _debito(cenario, d, "1000.00")
    _despesa(cenario, d, "1000.00")

    r = sugerir(cenario["user"], cenario["conta"])

    json.dumps(r.as_dict())  # nao pode levantar
