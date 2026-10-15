"""O teste que faltava: a view tem de RECEBER o ficheiro, nao o middleware
nao dar 500.

MEDIDO 2026-10-05 (agente 11). Fiz mutation testing nos testes do middleware JSON
e uma mutacao nao foi apanhada: `if "json" not in ct: return None` podia ser
removido e os testes continuavam verdes.

Porque. O teste antigo afirmava `assertNotEqual(status, 500)` e
`assertNotEqual(status, 403)`. Se o middleware lesse o corpo de um multipart, o
stream consumia-se, a view ficava sem `FILES`, e nao havia nem 500 nem 403 —
o teste passava **pelo motivo errado**. E' a forma mais comum de um teste
verde nao provar nada: verifica que o dia correu bem, em vez de verificar que
a coisa que importa aconteceu.

Este teste manda a view olhar para o que recebeu e devolver isso na resposta.
Assim, perder o ficheiro passa a ser visivel.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from app.middleware import TenantIsolationMiddleware

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def dono():
    from app.models import Propriedade

    u = User.objects.create_user("ana_foto", password="x" * 12)
    Propriedade.objects.create(
        user=u,
        nome="Fazenda ana",
        area_total=100.0,
        uf="MG",
        pais="BR",
        moeda="BRL",
        tipo_exploracao="1",
        participacao=100.0,
    )
    return u


def passar_e_ver(user, req):
    """Passa pelo middleware e devolve o que a VIEW recebeu.

    A view devolve o que viu. Se o middleware comeu o corpo, `files` vem vazio
    e o teste falla — que e' o ponto.
    """
    req.user = user
    req.session = {}

    def get_response(r):
        from django.http import JsonResponse

        return JsonResponse(
            {
                "ficheiros": sorted(getattr(r, "FILES", {}).keys()),
                "campos": sorted(getattr(r, "POST", {}).keys()),
                "corpo_json": getattr(r, "corpo_json", "AUSENTE"),
            }
        )

    return TenantIsolationMiddleware(get_response)(req)


class TestOMultipartChegaIntactoTest:
    def test_o_ficheiro_sobrevive_ao_middleware(self, dono):
        req = RequestFactory().post(
            "/api/x/",
            data={
                "talhao_id": "1",
                "nome": "com foto",
                "ficheiro": SimpleUploadedFile("a.jpg", b"\xff\xd8\xff", "image/jpeg"),
            },
        )
        r = passar_e_ver(dono, req)
        d = json.loads(r.content)
        assert "ficheiro" in d["ficheiros"], (
            f"o middleware COMEU o ficheiro: a view recebeu {d['ficheiros']}. "
            "O teste antigo passava porque nao havia nem 500 nem 403 — e' "
            "exatamente o teste que nao provava nada."
        )

    def test_o_middleware_nao_le_o_corpo_de_um_multipart(self, dono):
        """A guarda que a mutation test Removeu. Tem de estar aqui."""
        req = RequestFactory().post(
            "/api/x/",
            data={
                "talhao_id": "1",
                "ficheiro": SimpleUploadedFile("a.jpg", b"\xff\xd8\xff", "image/jpeg"),
            },
        )
        assert TenantIsolationMiddleware._corpo_json(req) is None

    def test_um_formulario_simples_tambem_nao_e_lido(self, dono):
        req = RequestFactory().post("/api/x/", data={"talhao_id": "1"})
        assert TenantIsolationMiddleware._corpo_json(req) is None

    def test_um_corpo_misto_nao_e_adivinhado_como_json(self, dono):
        """`multipart/mixed` tem uma parte JSON e uma parte ficheiro.

        E' este o caso que faz a guarda ser `"json" in ct` e nao
        `ct.startswith("json")`. E o risco real e' o oposto do que testei antes:
        tentar parsear o corpo todo como JSON, perder o ficheiro e inventar um
        `corpo_json` que nunca existiu.

        Este teste afirma exactamente isso: o middleware devolve `None`. Nao
        afirma nada sobre o parser de multipart do Django — isso nao e' deste
        codigo, e fingir que e' seria medir outra coisa.
        """
        fronteira = "----X"
        corpo = json.dumps({"talhao_id": "1"})
        body = (
            f"--{fronteira}\r\n"
            f'Content-Disposition: form-data; name="meta"\r\n\r\n{corpo}\r\n'
            f"--{fronteira}--\r\n"
        ).encode()

        req = RequestFactory().generic(
            "POST",
            "/api/x/",
            data=body,
            content_type=f"multipart/mixed; boundary={fronteira}",
        )
        assert (
            TenantIsolationMiddleware._corpo_json(req) is None
        ), "o middleware adivinhou que um corpo misto era JSON — e' inventar"

    def test_o_guard_content_type_usa_contains_e_nao_startswith(self, dono):
        """`multipart/mixed` contem 'json' no fim, nao no inicio.

        Se a guarda fosse `ct.startswith("json")`, um `application/vnd.api+json`
        — que e' JSON com sufixo — deixaria de ser reconhecido. E' um formato
        real: GraphQL-over-HTTP e JSON:API usam variantes.
        """
        req = RequestFactory().post(
            "/api/x/",
            data=json.dumps({"a": 1}),
            content_type="application/vnd.api+json",
        )
        assert TenantIsolationMiddleware._corpo_json(req) == {
            "a": 1
        }, "um content-type JSON com sufixo tem de ser reconhecido"
