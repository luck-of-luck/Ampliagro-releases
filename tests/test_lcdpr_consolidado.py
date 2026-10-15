from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from app.models import ContaBancaria, LancamentoFinanceiro
from app.services.lcdpr_export import LCDPRExporter, LCDPRDadosIncompletos, diagnosticar_consolidado
from tests.test_lcdpr_rotas_unificadas import propriedade  # noqa: F401 fixture


def outra_propriedade(original, nome, **alteracoes):
    nova = deepcopy(original)
    nova.pk = None
    nova.nome = nome
    nova.cad_itr = "87654321"
    for campo, valor in alteracoes.items():
        setattr(nova, campo, valor)
    nova.save()
    return nova


def movimento(prop, tipo, valor, dia, conta=None):
    return LancamentoFinanceiro.objects.create(propriedade=prop, tipo=tipo,
        categoria="OUTROS", descricao=f"Movimento {prop.nome}", valor=Decimal(valor),
        data=date(2025, 12, 1), data_pagamento=date(2026, 1, dia), pago=True,
        participante_doc="12345678901", tipo_documento_lcdpr="3",
        tipo_lancamento_lcdpr="1" if tipo == "RECEITA" else "2", conta_bancaria=conta)


@pytest.mark.django_db
def test_consolidado_ordena_caixa_e_referencia_imoveis_contas_e_saldos(client, propriedade):
    segunda = outra_propriedade(propriedade, "Fazenda Dois", cpf_cnpj="123.456.789-01")
    contas = [ContaBancaria.objects.create(propriedade=p, banco="001 Banco", agencia="1234", conta=str(12345+i), digito="1") for i, p in enumerate([propriedade, segunda])]
    movimento(propriedade, "RECEITA", "100", 10, contas[0])
    movimento(segunda, "DESPESA", "30", 5, contas[1])
    params = {"propriedade": propriedade.pk, "ano": 2026, "escopo": "contribuinte"}
    response = client.get("/api/exportar-lcdpr/", params)
    assert response.status_code == 200, response.content
    registros = [linha.split("|") for linha in response.content.decode().splitlines()]
    imoveis = [r for r in registros if r[0] == "0040"]
    assert [r[1] for r in imoveis] == ["001", "002"]
    q100 = [r for r in registros if r[0] == "Q100"]
    assert len(q100) == 2
    assert [r[1:4] for r in q100] == [["05012026", "002", "002"], ["10012026", "001", "001"]]
    assert [r[-2:] for r in q100] == [["3000", "N"], ["7000", "P"]]
    janeiro = next(r for r in registros if r[:2] == ["Q200", "012026"])
    assert janeiro == ["Q200", "012026", "10000", "3000", "7000", "P"]
    assert registros[-1][-1] == str(len(registros))
    diagnostico = client.get("/api/lancamentos-detalhados/diagnostico_lcdpr/", params).json()
    assert [p["id"] for p in diagnostico["propriedades_incluidas"]] == [propriedade.pk, segunda.pk]
    assert diagnostico["resumo"]["saldo"] == "70.00"
    assert diagnostico["resumo"]["lancamentos_incluidos"] == 2
    assert "_consolidado.txt" in response["Content-Disposition"]
    html = client.get("/gestao/central/", params)
    assert html.status_code == 200
    assert "Imóveis incluídos no consolidado" in html.content.decode()
    assert "escopo=contribuinte" in html.content.decode()


@pytest.mark.django_db
def test_consolidacao_nao_inclui_outro_cpf_ou_propriedade_sem_acesso(client, propriedade):
    movimento(propriedade, "RECEITA", "10", 1)
    outro_cpf = outra_propriedade(propriedade, "Outro CPF", cpf_cnpj="98765432100")
    outro_user = get_user_model().objects.create_user(username="cpf-igual-sem-acesso")
    alheia = outra_propriedade(propriedade, "Sigilo", user=outro_user)
    for prop in (outro_cpf, alheia):
        movimento(prop, "RECEITA", "999", 2)
    params = {"propriedade": propriedade.pk, "ano": 2026, "escopo": "contribuinte"}
    response = client.get("/api/lancamentos-detalhados/diagnostico_lcdpr/", params)
    assert response.status_code == 200
    assert response.json()["resumo"]["entradas"] == "10.00"
    assert [p["id"] for p in response.json()["propriedades_incluidas"]] == [propriedade.pk]
    assert b"Sigilo" not in response.content


@pytest.mark.django_db
def test_cadastro_divergente_bloqueia_consolidacao_sem_bloquear_revisao_individual(client, propriedade):
    segunda = outra_propriedade(propriedade, "Outra")
    segunda.cadastro_fiscal["contribuinte"]["nome"] = "Titular divergente"
    segunda.save()
    params = {"propriedade": propriedade.pk, "ano": 2026, "escopo": "contribuinte"}
    response = client.get("/api/exportar-lcdpr/", params)
    assert response.status_code == 400
    assert any(p["codigo"] == "cadastro_divergente" and p["propriedade_id"] == segunda.pk for p in response.json()["diagnostico"]["pendencias"])
    params["escopo"] = "propriedade"
    assert client.get("/api/exportar-lcdpr/", params).status_code == 200


@pytest.mark.django_db
def test_gerador_recusa_cpfs_diferentes_e_deduplica_conjunto(propriedade):
    segunda = outra_propriedade(propriedade, "Outra")
    movimento(propriedade, "RECEITA", "10", 1)
    conteudo = LCDPRExporter(propriedade, 2026, propriedades=[propriedade, segunda, propriedade]).gerar_arquivo()
    assert sum(linha.startswith("0040|") for linha in conteudo.splitlines()) == 2
    assert sum(linha.startswith("Q100|") for linha in conteudo.splitlines()) == 1
    segunda.cpf_cnpj = "98765432100"
    with pytest.raises(LCDPRDadosIncompletos):
        LCDPRExporter(propriedade, 2026, propriedades=[propriedade, segunda]).gerar_arquivo()


@pytest.mark.django_db
@pytest.mark.parametrize("ano", [None, "2026", True, 2018, 10000])
def test_diagnostico_consolidado_ano_invalido_retorna_pendencia(propriedade, ano):
    resultado = diagnosticar_consolidado(propriedade, [propriedade], ano)
    assert not resultado["pode_exportar"]
    assert any(p["codigo"] == "ano_invalido" for p in resultado["pendencias"])
