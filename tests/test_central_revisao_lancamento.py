from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from app.models import ContaBancaria, LancamentoFinanceiro, Propriedade
from tests.test_lcdpr_rotas_unificadas import propriedade  # noqa: F401
from tests.test_central_gestao import nota_upload


def criar_movimento(prop):
    return LancamentoFinanceiro.objects.create(
        propriedade=prop, tipo="DESPESA", categoria="OUTROS", valor=Decimal("40"),
        data=date(2026, 1, 3), descricao="Compra", tipo_lancamento_lcdpr="",
    )


def url(prop, lanc):
    return f"/gestao/central/?propriedade={prop.pk}&ano=2026&escopo=contribuinte&lancamento={lanc.pk}"


def dados(**extra):
    valores = {"secao": "lancamento", "movimento-tipo": "DESPESA",
               "movimento-descricao": "Compra revisada", "movimento-participante": "Fornecedor",
               "movimento-participante_doc": "98765432100", "movimento-tipo_documento_lcdpr": "1",
               "movimento-numero_documento": "123", "movimento-tipo_lancamento_lcdpr": "2",
               "movimento-conta_bancaria": "", "movimento-pago": "on",
               "movimento-data_pagamento": "2026-02-10"}
    valores.update(extra)
    return valores


@pytest.mark.django_db
def test_nfe_revisada_na_central_entra_no_lcdpr(client, propriedade):
    resposta = client.post("/api/nfe/import/", {"xml": nota_upload(), "propriedade": propriedade.pk})
    assert resposta.status_code == 201, resposta.content
    lanc = LancamentoFinanceiro.objects.get(propriedade=propriedade)
    original = (lanc.valor, lanc.data, lanc.safra_id, lanc.talhao_id, lanc.comprovante)
    assert not lanc.pago and not lanc.tipo_lancamento_lcdpr
    pagina = client.get(url(propriedade, lanc))
    assert pagina.status_code == 200
    assert 'Salvar revisão do lançamento' in pagina.content.decode()
    resposta = client.post(url(propriedade, lanc), dados(**{"movimento-valor": "1.00", "valor": "1.00"}))
    assert resposta.status_code == 302
    assert "escopo=contribuinte" in resposta.url
    lanc.refresh_from_db()
    assert (lanc.valor, lanc.data, lanc.safra_id, lanc.talhao_id, lanc.comprovante) == original
    assert lanc.pago and lanc.data_pagamento == date(2026, 2, 10)
    exportado = client.get("/api/exportar-lcdpr/", {"propriedade": propriedade.pk, "ano": 2026})
    assert exportado.status_code == 200, exportado.content
    movimentos = [ln.split("|") for ln in exportado.content.decode().splitlines() if ln.startswith("Q100|")]
    assert len(movimentos) == 1
    assert movimentos[0][1] == "10022026"
    assert movimentos[0][7:9] == ["98765432100", "2"]
    assert int(movimentos[0][10]) == int(lanc.valor * 100)


@pytest.mark.django_db
@pytest.mark.parametrize("alteracao,campo", [
    ({"movimento-data_pagamento": ""}, "data_pagamento"),
    ({"movimento-pago": ""}, "data_pagamento"),
    ({"movimento-tipo_lancamento_lcdpr": "1"}, "tipo_lancamento_lcdpr"),
    ({"movimento-tipo_lancamento_lcdpr": "3"}, "tipo_lancamento_lcdpr"),
    ({"movimento-participante_doc": "123"}, "participante_doc"),
    ({"movimento-participante_doc": ""}, "participante_doc"),
    ({"movimento-descricao": "Linha|extra"}, "descricao"),
])
def test_revisao_invalida_preserva_movimento(client, propriedade, alteracao, campo):
    lanc = criar_movimento(propriedade)
    resposta = client.post(url(propriedade, lanc), dados(**alteracao))
    assert resposta.status_code == 400
    assert campo in resposta.context["formulario_lancamento"].errors
    lanc.refresh_from_db()
    assert not lanc.pago and not lanc.tipo_lancamento_lcdpr
    assert lanc.descricao == "Compra"


@pytest.mark.django_db
def test_conta_e_lancamento_de_outra_propriedade_sao_recusados(client, propriedade):
    outro = get_user_model().objects.create_user(username="revisao-outro")
    prop = Propriedade.objects.create(user=outro, nome="Sigilo", area_total=1)
    alheio = criar_movimento(prop)
    for metodo in (client.get, client.post):
        resposta = metodo(url(propriedade, alheio), dados() if metodo == client.post else {})
        assert resposta.status_code == 404
        assert b"Sigilo" not in resposta.content
    conta = ContaBancaria.objects.create(propriedade=prop, banco="001 Banco", agencia="1234", conta="123", digito="1")
    proprio = criar_movimento(propriedade)
    resposta = client.post(url(propriedade, proprio), dados(**{"movimento-conta_bancaria": conta.pk}))
    assert resposta.status_code == 400
    assert "conta_bancaria" in resposta.context["formulario_lancamento"].errors
    proprio.refresh_from_db()
    assert proprio.conta_bancaria_id is None and not proprio.pago


@pytest.mark.django_db
def test_revisao_pendente_pode_ser_salva_sem_inventar_pagamento(client, propriedade):
    lanc = criar_movimento(propriedade)
    resposta = client.post(url(propriedade, lanc), dados(**{
        "movimento-pago": "", "movimento-data_pagamento": "",
        "movimento-tipo_lancamento_lcdpr": "", "movimento-participante_doc": "",
    }))
    assert resposta.status_code == 302
    lanc.refresh_from_db()
    assert lanc.descricao == "Compra revisada"
    assert not lanc.pago and lanc.data_pagamento is None
    assert not lanc.tipo_lancamento_lcdpr


@pytest.mark.django_db
def test_pendencia_abre_revisao_do_lancamento_correspondente(client, propriedade):
    lanc = criar_movimento(propriedade)
    lanc.pago, lanc.tipo_lancamento_lcdpr = True, "2"
    lanc.save()
    resposta = client.get("/gestao/central/", {"propriedade": propriedade.pk, "ano": 2026})
    assert resposta.status_code == 200
    assert f"lancamento={lanc.pk}#revisar-lancamento" in resposta.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("consulta", ["lancamento=x", "lancamento=0", "lancamento=-1", ""])
def test_post_sem_identificacao_valida_nao_altera_cadastro(client, propriedade, consulta):
    resposta = client.post(f"/gestao/central/?propriedade={propriedade.pk}&{consulta}", dados())
    assert resposta.status_code == 400
