"""A porta de entrada estava aberta em JSON. Este ficheiro e' o portao.

MEDIDO 2026-10-05 (agente 11). `TenantIsolationMiddleware` escolhia a fonte dos
ids assim:

    fonte = request.GET if request.method == "GET" else request.POST

O `request.POST` do Django so' e' povoado para `application/x-www-form-urlencoded`
e `multipart/form-data`. Numa API DRF quase todo o POST/PUT vai como
`application/json` — e entao `fonte` chegava VAZIO ao loop, o `continue` saltava
cada chave, e a verificacao de tenancy **nao corria**.

Nao ha excepcao. Nao ha log. Nao ha 500. A proteccao simplesmente nao acontecia,
e quem dependesse do middleware ficava sem nada — sem sinal. E' o pior modo de
falha que existe numa fronteira de seguranca: da a sensacao de que ha
filtragem.

Estes testes medem o middleware pelo `RequestFactory`, como `test_tenancy_
isolamento.py` faz. Nao dependem do nome de uma rota nem de um campo de
serializer que ninguem verficou: medem a coisa.

Cada teste tem uma mutacao que o faria falhar — e as mutacoes foram injectadas
para confirmar. Ver a nota no fim.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from app.middleware import TenantIsolationMiddleware

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def dois():
    """Duas pessoas, cada uma com o que e' seu.

    Nao se mede isolamento com um so utilizador: com um so, qualquer
    `filter(id=...)` passa, porque tudo e' dele. O bug so aparece quando existe
    alguem a quem o registo NAO pertence.
    """
    from app.models import Cultura, Propriedade, Safra, Talhao

    d = {}
    for chave in ("ana", "bruno"):
        u = User.objects.create_user(chave, password="x" * 12)
        p = Propriedade.objects.create(
            user=u,
            nome=f"Fazenda {chave}",
            area_total=100.0,
            uf="MG",
            pais="BR",
            moeda="BRL",
            tipo_exploracao="1",
            participacao=100.0,
        )
        t = Talhao.objects.create(
            propriedade=p, nome=f"Talhao {chave}", area_hectare=10.0, ativo=True
        )
        d[chave] = {"user": u, "propriedade": p, "talhao": t}
    # uma safra que e' do bruno — o parametro `safra_id` do middleware
    soja = Cultura.objects.create(nome="Soja", grupo="graos")
    # `Safra` tem `propriedade` NOT NULL alem do `talhao` — a quinta coisa que
    # este ficheiro errou por adivinhar. Ate aqui eu escrevi os campos de
    # memoria; a partir daqui leio-os do modelo, que e' o unico jeito.
    d["bruno"]["safra"] = Safra.objects.create(
        propriedade=d["bruno"]["propriedade"],
        talhao=d["bruno"]["talhao"],
        ano=2026,
        cultura=soja,
        area_plantada=10.0,
    )
    return d


def passar(user, req):
    """Passa um request pelo middleware e devolve a resposta."""
    req.user = user
    req.session = {}

    def get_response(_r):
        from django.http import JsonResponse

        return JsonResponse({"ok": True})

    return TenantIsolationMiddleware(get_response)(req)


def req_json(user, corpo, metodo="post"):
    return passar(
        user,
        getattr(RequestFactory(), metodo)(
            "/api/qualquer/",
            data=json.dumps(corpo),
            content_type="application/json",
        ),
    )


def req_form(user, corpo):
    return passar(user, RequestFactory().post("/api/qualquer/", data=corpo))


# =====================================================================
# 1. O TESTE QUE PROVA A CORRECCAO
# =====================================================================
class TestOCorpoJsonPassaAVerificacao:
    def test_json_com_talhao_de_outro_e_403(self, dois):
        """Isto passava sem tocar no middleware: com `request.POST` vazio o
        loop nao via o id e o pedido seguia."""
        r = req_json(dois["ana"]["user"], {"talhao_id": dois["bruno"]["talhao"].pk})
        assert r.status_code == 403

    def test_json_com_safra_de_outro_e_403(self, dois):
        """`safra_id` esta' em `TABELAS_VERIFICADAS` e e' lido de `request` em
        varias views. Era um dos nomes que nunca chegava a ser verificado."""
        r = req_json(dois["ana"]["user"], {"safra_id": dois["bruno"]["safra"].pk})
        assert r.status_code == 403

    def test_json_com_propriedade_de_outra_e_403(self, dois):
        r = req_json(
            dois["ana"]["user"], {"propriedade_id": dois["bruno"]["propriedade"].pk}
        )
        assert r.status_code == 403

    def test_o_dono_dos_seus_ids_passa(self, dois):
        """Um 403 aqui seria um sistema inutil, nao um sistema seguro."""
        r = req_json(dois["ana"]["user"], {"talhao_id": dois["ana"]["talhao"].pk})
        assert r.status_code == 200

    def test_json_sem_ids_nao_e_recusado(self, dois):
        """Nao ha o que verificar: nao pode fabricar uma recusa."""
        r = req_json(dois["ana"]["user"], {"nome": "qualquer"})
        assert r.status_code == 200

    def test_json_malformado_nao_e_500(self, dois):
        """Um corpo que nao se parseia ja nao passa a validacao do DRF. O
        middleware nao pode trocar um 400 honesto por um 500."""
        req = RequestFactory().post(
            "/api/qualquer/", data="{isto nao e' json", content_type="application/json"
        )
        r = passar(dois["ana"]["user"], req)
        assert r.status_code != 500

    def test_json_que_nao_e_objeto_e_ignorado(self, dois):
        req = RequestFactory().post(
            "/api/qualquer/", data=json.dumps([1, 2]), content_type="application/json"
        )
        r = passar(dois["ana"]["user"], req)
        assert r.status_code != 500


# =====================================================================
# 2. O QUE NAO SE PODE QUEBRAR
# =====================================================================
class TestOQueJaFuncionava:
    def test_formulario_continua_verificado(self, dois):
        """A correccao nao pode ter partido o caminho que ja funcionava."""
        r = req_form(dois["ana"]["user"], {"talhao_id": dois["bruno"]["talhao"].pk})
        assert r.status_code == 403

    def test_query_string_continua_verificada(self, dois):
        r = passar(
            dois["ana"]["user"],
            RequestFactory().get("/api/x/", {"talhao_id": dois["bruno"]["talhao"].pk}),
        )
        assert r.status_code == 403

    def test_multipart_nao_perde_o_ficheiro(self, dois):
        """Por isto que o content-type e' testado ANTES de ler o corpo: num
        multipart, ler o corpo consome o stream e a view fica sem ficheiro."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        req = RequestFactory().post(
            "/api/x/",
            data={
                "talhao_id": dois["ana"]["talhao"].pk,
                "ficheiro": SimpleUploadedFile("a.jpg", b"\xff\xd8\xff", "image/jpeg"),
            },
        )
        r = passar(dois["ana"]["user"], req)
        assert r.status_code != 500
        assert r.status_code != 403


# =====================================================================
# 3. O LEITOR, MEDIDO DIRETAMENTE
# =====================================================================
class TestOLeitor:
    def test_le_o_corpo_json(self):
        req = RequestFactory().post(
            "/x/",
            data=json.dumps({"propriedade_id": 7}),
            content_type="application/json",
        )
        assert TenantIsolationMiddleware._corpo_json(req) == {"propriedade_id": 7}

    def test_formulario_devolve_none(self):
        """Ler o corpo de um multipart consome o stream."""
        req = RequestFactory().post("/x/", data={"propriedade_id": 7})
        assert TenantIsolationMiddleware._corpo_json(req) is None

    def test_json_que_nao_e_objeto_devolve_none(self):
        req = RequestFactory().post(
            "/x/", data=json.dumps([1]), content_type="application/json"
        )
        assert TenantIsolationMiddleware._corpo_json(req) is None

    def test_lixo_devolve_none(self):
        req = RequestFactory().post(
            "/x/", data="{nao presta", content_type="application/json"
        )
        assert TenantIsolationMiddleware._corpo_json(req) is None

    def test_get_nao_le_corpo(self):
        req = RequestFactory().get("/x/")
        assert TenantIsolationMiddleware._corpo_json(req) is None


"""
NOTA DE MUTACOES
================

Estas mutacoes foram injectadas uma de cada vez, para confirmar que os testes
acima falham quando o codigo volta ao estado anterior. Sem isso, um teste que
passa nao prova nada — pode passar porque esta' a medir a coisa errada.

  1. `fonte = request.GET if method == "GET" else request.POST`
     -> falha `test_json_com_talhao_de_outro_e_403`,
        `..._safra_de_outro...`, `..._propriedade_de_outra...`

  2. `if "json" not in ct: return None` invertido para sempre
     -> falha `test_formulario_devolve_none` e
        `test_multipart_nao_perde_o_ficheiro`

  3. `return dados` sem o `isinstance(dados, dict)`
     -> falha `test_json_que_nao_e_objeto_e_ignorado`

  4. remover o `try/except` do `json.loads`
     -> falha `test_json_malformado_nao_e_500` e `test_lixo_devolve_none`
"""
