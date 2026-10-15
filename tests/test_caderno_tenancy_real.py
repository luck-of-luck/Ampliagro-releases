"""Prova directa da defesa do talhao alheio, SEM o servidor revogado.

MEDIDO 2026-10-06. `tests/test_caderno_campo.py::test_um_talhao_alheio_e_recusado`
existe e esta' certo no espirito, mas **nunca exerceu a defesa que diz medir**.

A razao: `exigir_sessao_json` devolve 403 `servidorRevogado` ANTES do
serializer correr, neste ambiente. O pedido morre no decorator, o
`PrimaryKeyRelatedField` nunca e' chamado, e o `assertEqual(count(), 0)` que
logo a seguir diria "nada foi gravado" nunca chega a ser avaliado.

Ou seja: o teste passava ou falhava por uma razao que nao tem nada a ver com
talhao alheio. Um dia o servidor deixa de estar revogado, o 403 vira 400, e o
teste comeca a dar verde - sem nada ter sido verificado. O pior desfecho de
um teste de seguranca: dar confianca sem medir.

Este ficheiro chama o serializer directamente, com o contexto de request real.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory

from app.api.views.caderno import NotaCampoSerializer
from app.models import NotaCampo, Propriedade, Talhao

# O tipo tem de ser uma escolha REAL do modelo. MEDIDO: as escolhas sao em
# minusculas (`observacao`, `praga`, ...) e `OBSERVACAO` da' invalid_choice -
# um teste que passa por escrever mal o campo mede o campo, nao a defesa.
TIPO_OK = "observacao"


@pytest.fixture
def cenario(db):
    eu = User.objects.create_user(username="dono", password="x")
    outro = User.objects.create_user(username="outro", password="x")

    minha = Propriedade.objects.create(
        user=eu, nome="Minha", area_total=10, uf="MT", cidade="Sorriso"
    )
    deles = Propriedade.objects.create(
        user=outro, nome="Deles", area_total=10, uf="GO", cidade="Goias"
    )

    return {
        "eu": eu,
        "deles": deles,
        "meu_talhao": Talhao.objects.create(
            propriedade=minha, nome="A-1", area_hectare=5
        ),
        "talhao_alheio": Talhao.objects.create(
            propriedade=deles, nome="B-1", area_hectare=5
        ),
        "request": APIRequestFactory().post("/api/caderno/notas/"),
    }


def _ser(cenario, data):
    """Cria o serializer com `data=` - o DRF recusa `is_valid()` sem isso,
    e um teste que salta essa validacao nao mede nada."""
    request = cenario["request"]
    request.user = cenario["eu"]
    return NotaCampoSerializer(data=data, context={"request": request})


def test_talhao_alheio_e_rejeitado(cenario):
    """A defesa real: o `queryset` do campo so' contem talhoes do dono."""
    s = _ser(
        cenario,
        {"talhao_id": cenario["talhao_alheio"].pk, "conteudo": "x", "tipo": TIPO_OK},
    )

    assert s.is_valid() is False, "o serializer ACEITOU um talhao de outra fazenda"
    assert "talhao_id" in s.errors


def test_talhao_alheio_nao_e_gravado(cenario):
    """Nada escrito. `is_valid()` sem `save()` e' o que prova isto."""
    s = _ser(
        cenario,
        {"talhao_id": cenario["talhao_alheio"].pk, "conteudo": "x", "tipo": TIPO_OK},
    )
    s.is_valid()

    assert NotaCampo.objects.count() == 0, "algo foi gravado noutra fazenda"


def test_meu_proprio_talhao_e_aceito(cenario):
    """O teste INVERSO, e sem ele o de cima nao diz nada.

    Um `queryset=Talhao.objects.none()` - que rejeitaria tudo, ate o dono -
    passaria em `test_talhao_alheio_e_rejeitado`. Um teste de recusa sem
    teste de aceitacao mede 'ha' uma falha algures', nao 'a defesa funciona'.
    """
    s = _ser(
        cenario,
        {"talhao_id": cenario["meu_talhao"].pk, "conteudo": "palha", "tipo": TIPO_OK},
    )

    assert s.is_valid() is True, f"o dono nao escreve no proprio talhao: {s.errors}"


def test_meu_proprio_talhao_grava_e_preserva_o_dono(cenario):
    """E' a prova completa: o caminho feliz grava E o talhao e' o meu."""
    s = _ser(
        cenario,
        {"talhao_id": cenario["meu_talhao"].pk, "conteudo": "palha", "tipo": TIPO_OK},
    )

    assert s.is_valid() is True
    nota = s.save(user=cenario["eu"])

    assert NotaCampo.objects.count() == 1
    assert nota.talhao_id == cenario["meu_talhao"].pk
    assert nota.user_id == cenario["eu"].pk


def test_propriedade_alheia_e_rejeitada(cenario):
    s = _ser(
        cenario,
        {
            "propriedade_id": cenario["deles"].pk,
            "conteudo": "x",
            "tipo": TIPO_OK,
        },
    )

    assert s.is_valid() is False, "propriedade de outra fazenda foi aceite"
    assert "propriedade_id" in s.errors


def test_erro_do_talhao_nao_e_silenciado_por_outro(cenario):
    """Um erro por vez. Se `conteudo` faltar E o talhao for alheio, os dois
    tem de aparecer. Um serializer que so' diz 'erro' sem dizer qual deixa
    o produtor a corrigir a coisa errada."""
    s = _ser(cenario, {"talhao_id": cenario["talhao_alheio"].pk})

    assert s.is_valid() is False
    assert "talhao_id" in s.errors


def test_conteudo_vazio_e_rejeitado(cenario):
    """Uma nota sem texto nao e' uma nota. E' ruido no caderno de campo, e
    ruido que depois ninguem consegue filtrar."""
    s = _ser(
        cenario,
        {"talhao_id": cenario["meu_talhao"].pk, "conteudo": "", "tipo": TIPO_OK},
    )

    assert s.is_valid() is False
