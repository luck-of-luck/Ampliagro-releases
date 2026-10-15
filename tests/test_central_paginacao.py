from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest
from app.models import LancamentoFinanceiro
from tests.test_lcdpr_rotas_unificadas import propriedade  # noqa: F401
from tests.test_central_revisao_lancamento import dados


@pytest.fixture
def movimentos(propriedade):
    return LancamentoFinanceiro.objects.bulk_create([
        LancamentoFinanceiro(propriedade=propriedade, tipo="DESPESA", categoria="OUTROS",
            valor="1.00", data=date(2026, 1, 1), data_pagamento=date(2026, 2, 1),
            pago=True, tipo_lancamento_lcdpr="2", tipo_documento_lcdpr="3",
            participante_doc="12345678901", descricao=f"Movimento {i:03d}")
        for i in range(101)
    ])


@pytest.mark.django_db
def test_todas_as_linhas_sao_acessiveis_sem_duplicacao_e_totais_nao_sao_paginados(client, propriedade, movimentos):
    params = {"propriedade": propriedade.pk, "ano": 2026, "escopo": "contribuinte"}
    primeira = client.get("/gestao/central/", params)
    segunda = client.get("/gestao/central/", {**params, "pagina": 2})
    assert primeira.status_code == segunda.status_code == 200
    ids1 = [l.pk for l in primeira.context["lancamentos"]]
    ids2 = [l.pk for l in segunda.context["lancamentos"]]
    assert len(ids1) == 100 and len(ids2) == 1
    assert not set(ids1) & set(ids2)
    assert ids1 + ids2 == [l.pk for l in reversed(movimentos)]
    for resposta in (primeira, segunda):
        assert resposta.context["diagnostico"]["resumo"]["saidas"] == "101.00"
        assert resposta.context["total_lancamentos"] == 101
    html = segunda.content.decode()
    assert "Mostrando 101–101 de 101 registros" in html
    assert f"escopo=contribuinte&amp;pagina=2&amp;lancamento={ids2[0]}" in html
    assert "escopo=contribuinte&amp;pagina=1#movimentos" in html


@pytest.mark.django_db
def test_revisao_na_segunda_pagina_preserva_retorno(client, propriedade, movimentos):
    alvo = movimentos[0]
    caminho = f"/gestao/central/?propriedade={propriedade.pk}&ano=2026&escopo=contribuinte&pagina=2&lancamento={alvo.pk}"
    pagina = client.get(caminho)
    assert pagina.status_code == 200
    assert pagina.context["lancamento_revisao"].pk == alvo.pk
    resposta = client.post(caminho, dados())
    assert resposta.status_code == 302
    params = parse_qs(urlsplit(resposta.url).query)
    assert params == {"propriedade": [str(propriedade.pk)], "ano": ["2026"], "escopo": ["contribuinte"], "pagina": ["2"]}
    assert client.get(resposta.url).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("numero", ["abc", "0", "-1", "2.5"])
def test_pagina_invalida_retorna_400(client, propriedade, numero):
    assert client.get("/gestao/central/", {"propriedade": propriedade.pk, "pagina": numero}).status_code == 400


@pytest.mark.django_db
def test_pagina_alem_do_fim_usa_ultima_e_vazio_nao_quebra(client, propriedade):
    resposta = client.get("/gestao/central/", {"propriedade": propriedade.pk, "pagina": 999})
    assert resposta.status_code == 200
    assert resposta.context["pagina"] == 1
    assert "Mostrando 0–0 de 0 registros" in resposta.content.decode()
