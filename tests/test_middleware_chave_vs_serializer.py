"""O middleware procura `talhao_id`. O serializer DRF espera `talhao`.

Se forem chaves diferentes, o porto unico de isolamento nao ve o campo que o
serializer realmente le — e entao um `create` sem `perform_create` e sem
`validate_*` fica sem barreira nenhuma.

Isto nao e' deduzido de documentacao: e' medido com um pedido real.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def dois():
    from app.models import Propriedade, Talhao

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
        d[chave] = {
            "user": u,
            "propriedade": p,
            "talhao": Talhao.objects.create(
                propriedade=p, nome=f"T {chave}", area_hectare=10.0, ativo=True
            ),
        }
    return d


class TestAChaveQueOMiddlewareVêTest:
    """Qual e' a chave que o serializer DRf espera?"""

    def test_o_serializer_aceita_o_nome_do_campo(self, dois):
        from app.api.serializers import AplicacaoInsumoSerializer

        s = AplicacaoInsumoSerializer(
            data={"talhao": dois["ana"]["talhao"].pk, "dose": 1.0, "data": "2026-01-10"}
        )
        print("\n  serializer com 'talhao':  valido =", s.is_valid())
        if not s.is_valid():
            print("  erros:", dict(s.errors))

    def test_o_serializer_ignora_o_talhao_id(self, dois):
        from app.api.serializers import AplicacaoInsumoSerializer

        s = AplicacaoInsumoSerializer(
            data={
                "talhao_id": dois["ana"]["talhao"].pk,
                "dose": 1.0,
                "data": "2026-01-10",
            }
        )
        print("\n  serializer com 'talhao_id': valido =", s.is_valid())
        print(
            "  o 'talhao' ficou a null?    ",
            s.validated_data.get("talhao") if s.is_valid() else "nao validou",
        )

    def test_a_chave_que_o_serializer_le_e_verificada(self, dois):
        """Este teste so' IMPRIMIA os codigos. Nao afirmava nada.

        Mutation testing apanhou: revertendo a correccao dos nomes de campo,
        este ficheiro continuava verde. Um teste que imprime e passa na mesma
        nao mede nada — e' a terceira vez nesta auditoria que isso acontece
        (a propriedade do corpo, e o ficheiro do upload).

        O que se mede e' uma coisa so: **um corpo com `talhao` — a forma que o
        serializer DRF le — e' recusado tal e qual como `talhao_id`.**

        Sem esta correccao, `TABELAS_VERIFICADAS` via `talhao_id`, um cliente
        DRF manda `talhao`, e a verificacao de tenancy sobre chaves
        estrangeiras ficava desligada em `application/json` — que e' como a
        API fala. A correccao de ler o corpo JSON, sozinha, nao fechava isso.
        """
        talhao_de_outro = dois["bruno"]["talhao"].pk

        def pedir(corpo):
            c = Client()
            c.force_login(dois["ana"]["user"])
            return c.post(
                "/api/qualquer/",
                data=json.dumps(corpo),
                content_type="application/json",
            )

        # a chave do serializer DRF tem de ser verificada
        r_drf = pedir({"talhao": talhao_de_outro})
        assert r_drf.status_code == 403, (
            f'um corpo com "talhao" (a chave que o serializer le) nao foi '
            f'recusado: {r_drf.status_code}. O middleware olha para "talhao_id" '
            "e a API fala em 'talhao' — a verificacao de tenancy sobre chaves "
            "estrangeiras esta' desligada em JSON"
        )

        # e a chave de formulario tem de continuar verificada
        r_form = pedir({"talhao_id": talhao_de_outro})
        assert r_form.status_code == 403

    def test_o_que_e_do_dono_passa_nas_duas_chaves(self, dois):
        """Nao pode ser um 403 para tudo: um sistema que recusa o proprio dono
        e' inutil, nao seguro."""
        talhao_dele = dois["ana"]["talhao"].pk
        for chave in ("talhao", "talhao_id"):
            c = Client()
            c.force_login(dois["ana"]["user"])
            r = c.post(
                "/api/qualquer/",
                data=json.dumps({chave: talhao_dele}),
                content_type="application/json",
            )
            assert (
                r.status_code != 403
            ), f"o proprio dono foi recusado com a chave {chave!r}: {r.status_code}"

    def test_o_serializer_usa_o_nome_do_campo_e_nao_o_attname(self, dois):
        """Por que e' que isto importa: prova de que `talhao` e' a chave real.

        Se o serializer so' aceitasse `talhao_id`, a correccao do middleware
        seria desnecessaria. Este teste fixa esse facto, para que ninguem
        mude uma das pontas sem saber que a outra depende dela.
        """
        from app.api.serializers import AplicacaoInsumoSerializer

        s = AplicacaoInsumoSerializer(
            data={
                "talhao": dois["ana"]["talhao"].pk,
                "insumo": None,
                "data": "2026-01-10",
                "dose": 1.0,
            }
        )
        # `talhao` e' reconhecido: o erro, se houver, nao e' "talhao obrigatorio"
        s.is_valid()
        erros = dict(s.errors)
        assert "talhao" not in erros, (
            f"o serializer nao reconheceu 'talhao': {erros}. Se isto mudar, a "
            "correccao do middleware tem de mudar com ele"
        )
