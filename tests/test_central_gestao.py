from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from app.models import LancamentoFinanceiro, PerfilUsuario, Propriedade
from tests.test_importar_nfe import NF_E, CHAVE
from app.api.fiscal_serializers import CadastroFiscalSerializer
from app.api.serializers import PropriedadeSerializer


@pytest.fixture
def produtor(db, client):
    user = get_user_model().objects.create_user(username="central-produtor")
    PerfilUsuario.objects.update_or_create(user=user, defaults={"tipo_usuario": "produtor"})
    client.force_login(user)
    return user


def fazenda(user, nome):
    return Propriedade.objects.create(user=user, nome=nome, area_total=Decimal("10"))


@pytest.mark.django_db
def test_central_sem_propriedade_orienta_cadastro(client, produtor):
    response = client.get(reverse("central-gestao"))
    assert response.status_code == 200
    assert "Cadastre sua primeira propriedade" in response.content.decode()
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.django_db
def test_central_isola_propriedade_e_mostra_pendencias(client, produtor):
    prop = fazenda(produtor, "Minha Fazenda")
    outro = get_user_model().objects.create_user(username="central-outro")
    alheia = fazenda(outro, "Sigilo de outro produtor")
    response = client.get(reverse("central-gestao"), {"propriedade": prop.pk, "ano": 2026})
    assert response.status_code == 200
    html = response.content.decode()
    assert "Minha Fazenda" in html
    assert "Sigilo de outro produtor" not in html
    assert "pendência(s) para revisar" in html
    assert "Baixar LCDPR para conferência" not in html
    assert client.get(reverse("central-gestao"), {"propriedade": alheia.pk}).status_code == 404


@pytest.mark.django_db
def test_central_usa_ano_do_pagamento_e_nao_apenas_emissao(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    for descricao, emissao, pagamento in [
        ("Pago neste ano", date(2025, 12, 1), date(2026, 1, 2)),
        ("Pago em outro ano", date(2026, 12, 1), date(2027, 1, 2)),
    ]:
        LancamentoFinanceiro.objects.create(propriedade=prop, tipo="DESPESA", categoria="INSUMO",
            valor=Decimal("10"), descricao=descricao, data=emissao, pago=True,
            data_pagamento=pagamento, tipo_lancamento_lcdpr="")
    response = client.get(reverse("central-gestao"), {"ano": 2026})
    assert response.status_code == 200
    assert "Pago neste ano" in response.content.decode()
    assert "Pago em outro ano" not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("params", [{"ano": "x"}, {"ano": 10000}, {"propriedade": "x"}])
def test_central_recusa_parametros_invalidos(client, produtor, params):
    assert client.get(reverse("central-gestao"), params).status_code == 400


@pytest.mark.django_db
def test_central_exige_login(client):
    assert client.get(reverse("central-gestao")).status_code == 302


def nota_upload():
    return SimpleUploadedFile("nota.xml", NF_E.format(chave=CHAVE).encode(), content_type="application/xml")


@pytest.mark.django_db
def test_importacao_exige_destino_quando_ha_varias_propriedades(client, produtor):
    fazenda(produtor, "Primeira")
    fazenda(produtor, "Segunda")
    response = client.post(reverse("nfe-import"), {"xml": nota_upload()})
    assert response.status_code == 400
    assert LancamentoFinanceiro.objects.count() == 0


@pytest.mark.django_db
def test_nota_alimenta_financeiro_da_propriedade_selecionada_uma_vez(client, produtor):
    primeira = fazenda(produtor, "Primeira")
    segunda = fazenda(produtor, "Segunda")
    response = client.post(reverse("nfe-import"), {"xml": nota_upload(), "propriedade": segunda.pk})
    assert response.status_code == 201
    lancamento = LancamentoFinanceiro.objects.get(pk=response.json()["lancamento_id"])
    assert lancamento.propriedade_id == segunda.pk
    assert lancamento.tipo_documento_lcdpr == "1"
    assert lancamento.participante_doc == "12345678000199"
    assert not lancamento.pago
    assert lancamento.tipo_lancamento_lcdpr == ""
    assert not primeira.lancamentos.exists()
    repetida = client.post(reverse("nfe-import"), {"xml": nota_upload(), "propriedade": segunda.pk})
    assert repetida.status_code == 200
    assert repetida.json()["duplicado"] is True
    assert segunda.lancamentos.count() == 1


@pytest.mark.django_db
def test_importacao_nao_escreve_em_propriedade_alheia(client, produtor):
    outro = get_user_model().objects.create_user(username="dono-destino")
    alheia = fazenda(outro, "Alheia")
    response = client.post(reverse("nfe-import"), {"xml": nota_upload(), "propriedade": alheia.pk})
    assert response.status_code == 404
    assert not LancamentoFinanceiro.objects.exists()


@pytest.mark.django_db
def test_formulario_salva_rascunho_sem_apagar_contador(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    prop.cadastro_fiscal = {"contador": {"nome": "Contador"}}
    prop.save()
    url = reverse("central-gestao") + f"?propriedade={prop.pk}&ano=2026"
    response = client.post(url, {"nome": "Pessoa Física", "cep": "37890000", "numero": "123"})
    assert response.status_code == 302
    prop.refresh_from_db()
    assert prop.cadastro_fiscal["contribuinte"]["nome"] == "Pessoa Física"
    assert prop.cadastro_fiscal["contador"]["nome"] == "Contador"
    html = client.get(url).content.decode()
    assert 'value="Pessoa Física"' in html
    assert "Contribuinte: nome" not in html
    assert "Contribuinte: endereco" in html


@pytest.mark.django_db
def test_formulario_invalido_nao_grava_e_exibe_erro(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    response = client.post(reverse("central-gestao") + f"?propriedade={prop.pk}", {"cep": "123", "nome": "Teste"})
    assert response.status_code == 400
    prop.refresh_from_db()
    assert prop.cadastro_fiscal == {}
    assert "errorlist" in response.content.decode()


@pytest.mark.django_db
def test_serializer_persiste_cadastro_estruturado(produtor):
    prop = fazenda(produtor, "Fazenda")
    serializer = PropriedadeSerializer(prop, data={"cadastro_fiscal": {
        "contribuinte": {"nome": "Titular", "numero": "S/N"},
        "contrapartes": [{"tipo": "1", "documento": "12345678901", "nome": "Parceiro", "participacao": "50.00"}],
    }}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    prop.refresh_from_db()
    assert prop.cadastro_fiscal["contrapartes"][0]["participacao"] == "50.00"
    assert PropriedadeSerializer(prop).data["cadastro_fiscal"]["contribuinte"]["numero"] == "S/N"


@pytest.mark.parametrize("dados", [
    {"contribuinte": {"campo_inventado": "x"}},
    {"contribuinte": {"nome": "Pessoa|outra"}},
    {"contribuinte": {"nome": "Pessoa\nOutra"}},
    {"contribuinte": {"uf": "XX"}},
    {"contribuinte": {"email": "invalido"}},
    {"contribuinte": {"cep": "12"}},
    {"contribuinte": []},
    {"contrapartes": [{"tipo": "1", "documento": "12345678901", "nome": "Pessoa", "participacao": "101"}]},
])
def test_cadastro_fiscal_recusa_formatos_invalidos(dados):
    assert not CadastroFiscalSerializer(data=dados).is_valid()


@pytest.mark.django_db
def test_salvar_cadastro_exige_propriedade_explicita(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    assert client.post(reverse("central-gestao"), {"nome": "Pessoa"}).status_code == 400
    prop.refresh_from_db()
    assert prop.cadastro_fiscal == {}


@pytest.mark.django_db
def test_salvar_cadastro_recusa_propriedade_alheia(client, produtor):
    outro = get_user_model().objects.create_user(username="cadastro-alheio")
    prop = fazenda(outro, "Fazenda alheia")
    assert client.post(reverse("central-gestao") + f"?propriedade={prop.pk}", {"nome": "Pessoa"}).status_code == 404
    prop.refresh_from_db()
    assert prop.cadastro_fiscal == {}


@pytest.mark.django_db
def test_contador_salvo_chega_ao_arquivo_sem_apagar_contribuinte(client, produtor):
    from app.services.lcdpr_export import LCDPRExporter
    prop = fazenda(produtor, "Fazenda")
    prop.cpf_cnpj = "12345678901"
    prop.caepf = "12345678901234"
    prop.cad_itr = "12345678"
    prop.endereco = "Estrada rural"
    prop.bairro = "Zona rural"
    prop.cod_municipio = "5103403"
    prop.cep = "78000000"
    prop.cadastro_fiscal = {"contribuinte": {"nome": "Titular", "endereco": "Rua Um", "numero": "10", "bairro": "Centro", "uf": "MT", "cod_municipio": "5103403", "cep": "78000000", "email": "titular@example.com"}}
    prop.save()
    response = client.post(reverse("central-gestao") + f"?propriedade={prop.pk}", {
        "secao": "contador", "contador-nome": "Contador Teste",
        "contador-documento": "12345678901", "contador-crc": "MT123456",
        "contador-email": "contador@example.com", "contador-telefone": "65999999999",
    })
    assert response.status_code == 302
    prop.refresh_from_db()
    assert prop.cadastro_fiscal["contribuinte"]["nome"] == "Titular"
    linhas = LCDPRExporter(prop, 2026).gerar_arquivo().splitlines()
    assert linhas[-1].split("|") == ["9999", "Contador Teste", "12345678901", "MT123456", "contador@example.com", "65999999999", str(len(linhas))]


def dados_terceiros(**extra):
    return {"secao": "contrapartes", "contrapartes-TOTAL_FORMS": "1", "contrapartes-INITIAL_FORMS": "0",
        "contrapartes-0-tipo": "3", "contrapartes-0-documento": "12345678901",
        "contrapartes-0-nome": "Parceiro", "contrapartes-0-participacao": "50.00", **extra}


@pytest.mark.django_db
def test_terceiros_podem_ser_incluidos_e_excluidos(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    url = reverse("central-gestao") + f"?propriedade={prop.pk}"
    assert client.post(url, dados_terceiros()).status_code == 302
    prop.refresh_from_db()
    assert prop.cadastro_fiscal["contrapartes"][0]["participacao"] == "50.00"
    assert "Parceiro" in client.get(url).content.decode()
    assert client.post(url, dados_terceiros(**{"contrapartes-INITIAL_FORMS": "1", "contrapartes-0-DELETE": "on"})).status_code == 302
    prop.refresh_from_db()
    assert prop.cadastro_fiscal["contrapartes"] == []


@pytest.mark.django_db
def test_formset_sem_management_ou_invalido_nao_apaga_dados(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    url = reverse("central-gestao") + f"?propriedade={prop.pk}"
    client.post(url, dados_terceiros())
    for dados in ({"secao": "contrapartes"}, dados_terceiros(**{"contrapartes-0-participacao": "101"})):
        assert client.post(url, dados).status_code == 400
        prop.refresh_from_db()
        assert len(prop.cadastro_fiscal["contrapartes"]) == 1


@pytest.mark.django_db
def test_linha_extra_vazia_nao_cria_terceiro(client, produtor):
    prop = fazenda(produtor, "Fazenda")
    response = client.post(reverse("central-gestao") + f"?propriedade={prop.pk}", {
        "secao": "contrapartes", "contrapartes-TOTAL_FORMS": "1", "contrapartes-INITIAL_FORMS": "0", "contrapartes-0-tipo": "1",
    })
    assert response.status_code == 302
    prop.refresh_from_db()
    assert prop.cadastro_fiscal["contrapartes"] == []
