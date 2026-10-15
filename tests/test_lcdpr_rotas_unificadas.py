import pytest
from django.contrib.auth import get_user_model

from app.models import PerfilUsuario, Propriedade

ROTAS = ["/api/exportar-lcdpr/", "/api/financeiro/lcdpr/download/",
         "/api/lancamentos-detalhados/export_lcdpr/"]


@pytest.fixture
def propriedade(db, client):
    user = get_user_model().objects.create_user(username="fiscal-rotas")
    PerfilUsuario.objects.update_or_create(user=user, defaults={"tipo_usuario": "produtor"})
    client.force_login(user)
    return Propriedade.objects.create(user=user, nome='Nome " seguro', area_total="10.00",
        cpf_cnpj="12345678901", caepf="12345678901234", cad_itr="12345678",
        endereco="Estrada rural", bairro="Zona rural", uf="MT", cod_municipio="5103403", cep="78000000",
        cadastro_fiscal={"contribuinte": {"nome": "Titular", "endereco": "Rua Um", "numero": "10",
            "bairro": "Centro", "uf": "MT", "cod_municipio": "5103403", "cep": "78000000", "email": "titular@example.com"}})


@pytest.mark.django_db
def test_tres_portas_entregam_mesmos_bytes_e_nome_seguro(client, propriedade):
    respostas = [client.get(rota, {"propriedade": propriedade.pk, "ano": 2026}) for rota in ROTAS]
    assert [r.status_code for r in respostas] == [200, 200, 200]
    assert len({r.content for r in respostas}) == 1
    for resposta in respostas:
        assert resposta.content.startswith(b"0000|LCDPR|0013|")
        assert resposta["Content-Disposition"] == f'attachment; filename="LCDPR_{propriedade.pk}_2026.txt"'
        assert "text/plain" in resposta["Content-Type"]
        assert "no-store" in resposta["Cache-Control"]
        assert resposta.content.endswith(b"\r\n")


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
@pytest.mark.parametrize("params", [{"ano": "abc"}, {"ano": "0"}, {"propriedade": "abc"}, {"propriedade": "1", "propriedade_id": "2"}])
def test_parametro_invalido_nao_vira_500(client, propriedade, rota, params):
    assert client.get(rota, params).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
def test_escopo_alheio_nao_e_exportado(client, propriedade, rota):
    outro = get_user_model().objects.create_user(username="outro-fiscal")
    prop = Propriedade.objects.create(user=outro, nome="Sigilo", area_total="1.00")
    resposta = client.get(rota, {"propriedade": prop.pk, "ano": 2026})
    assert resposta.status_code == 404
    assert b"Sigilo" not in resposta.content
    # O alias legado é verificado antes pelo middleware de isolamento.
    legado = client.get(rota, {"propriedade_id": prop.pk, "ano": 2026})
    assert legado.status_code == 403
    assert b"Sigilo" not in legado.content


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
def test_varias_propriedades_exigem_selecao(client, propriedade, rota):
    Propriedade.objects.create(user=propriedade.user, nome="Segunda", area_total="1.00")
    assert client.get(rota, {"ano": 2026}).status_code == 400


@pytest.mark.django_db
def test_diagnostico_e_download_concordam_sobre_pendencias(client, propriedade):
    propriedade.cadastro_fiscal = {}
    propriedade.save()
    params = {"propriedade": propriedade.pk, "ano": 2026}
    diagnostico = client.get("/api/lancamentos-detalhados/diagnostico_lcdpr/", params)
    assert diagnostico.status_code == 200
    assert diagnostico.json()["pode_exportar"] is False
    for rota in ROTAS:
        resposta = client.get(rota, params)
        assert resposta.status_code == 400
        assert resposta.json()["diagnostico"]["pendencias"] == diagnostico.json()["pendencias"]
