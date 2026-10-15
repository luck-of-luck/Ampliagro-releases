"""Caderno de Campo: a nota de campo tem de chegar ao servidor.

O QUE ESTES TESTES PROVAM
=========================
Cada teste abaixo existe porque o `MERGED.md` registou que o
`pwa/sync.js` gravava notas no IndexedDB e perdia-as todas: `POST
/api/caderno/notas/` devolvia 404, o `catch` fazia `console.error`, e o
produtor ficava com um caderno no telemóvel que não existia em lado nenhum.

Nenhum destes testes toca em `sync.js` — teste-se o servidor, porque o
servidor é a parte que estava em falta. O comportamento do browser
(idempotência via `offline_id`, `markNoteSynced` só depois de 2xx) é
coberto pelo contrato que estes testes fixam: `offline_id` é devolvido e a
segunda tentativa devolve `duplicado: True` com o mesmo `id`.
"""

import json

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.models import Cultura, NotaCampo, Propriedade, Talhao


@pytest.fixture
def cliente():
    return APIClient()


def login(cliente, user):
    """Sessão real por cookie, não `force_authenticate`.

    O `sync.js` faz `fetch` com a sessão do produtor — é o browser que
    manda o cookie. O `force_authenticate` do DRF injecta um objecto
    `user` por *request*, o que não satisfaz o `@login_required` do Django
    numa view que não é do DRF: o resultado é um 401 falso que não
    acontece em produção. Testar com a sessão real é o que garante que o
    caminho exercitado é o caminho usado.
    """
    cliente.force_login(user)
    return cliente


@pytest.fixture(autouse=True)
def _db(django_db_setup, django_db_blocker):
    """Todos os testes deste ficheiro tocam na base de dados.

    Aplicado por `autouse` em vez de repetir `@pytest.mark.django_db` em
    cada decorador: um teste novo escrito sem o marker falha alto, em vez de
    passar a falhar por uma razao que nao tem nada a ver com o que testa.
    """
    with django_db_blocker.unblock():
        yield


@pytest.fixture
def talhao_do_user(django_user_model):
    user = django_user_model.objects.create_user(
        username="produtor", password="x", is_staff=False
    )
    prop = Propriedade.objects.create(
        user=user, nome="Fazenda Boa", cidade="Goias", uf="GO", area_total=100
    )
    tal = Talhao.objects.create(propriedade=prop, nome="T1", area_hectare=1.0)
    return user, prop, tal


# --------------------------------------------------------------------------
# 1. O que estava partido: a nota escrevia-se e nao chegava ao servidor
# --------------------------------------------------------------------------


def test_nota_campo_grava_e_persiste(cliente, talhao_do_user, django_user_model):
    """O que o `sync.js:105` envia tem de virar uma linha na base de dados."""
    user, prop, tal = talhao_do_user
    login(cliente, user)

    r = cliente.post(
        reverse("api-caderno-notas"),
        {
            "talhao_id": tal.pk,
            "conteudo": "Pulgão no canto norte, uns 20 por planta.",
            "tipo": "praga",
            "offline_id": 7,
        },
        format="json",
    )

    assert r.status_code == 201, r.content
    assert NotaCampo.objects.filter(user=user).count() == 1

    nota = NotaCampo.objects.get(user=user)
    assert nota.talhao_id == tal.pk
    # A propriedade foi derivada do talhao — o `sync.js` nao a manda.
    assert nota.propriedade_id == prop.pk
    # Regra de proveniencia: uma nota escrita e' `declarado`. Nunca `medido`.
    assert nota.fonte_dado == "declarado"
    assert r.json()["offline_id"] == 7


# --------------------------------------------------------------------------
# 2. Idempotencia: o browser reenvia em cada sync
# --------------------------------------------------------------------------


def test_reenvio_offline_id_nao_duplica(cliente, talhao_do_user):
    """O `sync.js` so marca a nota como sincronizada depois de um 2xx.

    Uma nota escrita offline repete em cada sync enquanto o servidor
    estiver em baixo. Sem `offline_id`, um produtor offline uma tarde
    acabava com a mesma nota vinte vezes.
    """
    user, prop, tal = talhao_do_user
    login(cliente, user)
    payload = {
        "talhao_id": tal.pk,
        "conteudo": "Choveu de madrugada.",
        "offline_id": 99,
    }

    r1 = cliente.post(reverse("api-caderno-notas"), payload, format="json")
    r2 = cliente.post(reverse("api-caderno-notas"), payload, format="json")

    assert r1.status_code == 201
    # O segundo e' 200, nao 201: nao e' uma nota nova.
    assert r2.status_code == 200
    assert r2.json()["duplicado"] is True
    assert r2.json()["id"] == r1.json()["id"]
    assert NotaCampo.objects.filter(user=user).count() == 1


# --------------------------------------------------------------------------
# 3. Tenancy: o caminho do sync nao passa pelo middleware
# --------------------------------------------------------------------------


def test_talhao_alheio_e_rejeitado(cliente, talhao_do_user, django_user_model):
    """Um `talhao_id` de outra fazenda nao pode ser gravado.

    Este POST vem do `fetch` do browser com a sessao do produtor, e nao
    passa pelo `TenantIsolationMiddleware`. A unica defesa deste caminho e'
    a validacao no serializer — sem ela, isto e' uma fuga cross-tenant.
    """
    user, prop, tal = talhao_do_user
    outro = django_user_model.objects.create_user(username="vizinho", password="x")
    prop2 = Propriedade.objects.create(
        user=outro,
        nome="Fazenda do Vizinho",
        cidade="Goias",
        uf="GO",
        area_total=100,
    )
    tal2 = Talhao.objects.create(propriedade=prop2, nome="T9", area_hectare=2.0)

    login(cliente, user)
    r = cliente.post(
        reverse("api-caderno-notas"),
        {"talhao_id": tal2.pk, "conteudo": "invadindo", "offline_id": 1},
        format="json",
    )

    # A middleware agora verifica ids no corpo JSON e devolve 403
    # (recurso de outra pessoa): 400 foi para o serializer.
    assert r.status_code == 403
    assert NotaCampo.objects.count() == 0


def test_anonymous_nao_escreve(cliente):
    """Sem sessao, o sync nao grava nada."""
    r = cliente.post(
        reverse("api-caderno-notas"),
        {"conteudo": "sem dono", "offline_id": 1},
        format="json",
    )
    assert r.status_code in (401, 403)
    assert NotaCampo.objects.count() == 0


# --------------------------------------------------------------------------
# 4. Honestidade do payload
# --------------------------------------------------------------------------


def test_nota_sem_texto_e_rejeitada(cliente, talhao_do_user):
    """Uma nota sem texto nao e' uma nota. Falhar alto e' melhor do que
    gravar uma linha vazia que ninguem consegue ler."""
    user, prop, tal = talhao_do_user
    login(cliente, user)
    r = cliente.post(
        reverse("api-caderno-notas"),
        {"talhao_id": tal.pk, "conteudo": "   ", "offline_id": 2},
        format="json",
    )
    assert r.status_code == 400
    assert NotaCampo.objects.count() == 0


def test_tipo_desconhecido_e_rejeitado(cliente, talhao_do_user):
    """A lista de tipos e' fechada; um texto livre vira, em tres meses, um
    campo que ninguem consegue filtrar."""
    user, prop, tal = talhao_do_user
    login(cliente, user)
    r = cliente.post(
        reverse("api-caderno-notas"),
        {
            "talhao_id": tal.pk,
            "conteudo": "x",
            "tipo": "campo_inventado",
            "offline_id": 3,
        },
        format="json",
    )
    assert r.status_code == 400
    assert NotaCampo.objects.count() == 0


# --------------------------------------------------------------------------
# 5. As rotas que ainda nao existem dizem isso
# --------------------------------------------------------------------------


def test_fotos_responde_e_nao_404(cliente, talhao_do_user):
    """`fotos/` foi implementada; `voice/` continua por decidir.

    MEDIDO 2026-10-05 (actualizacao do agente 7). Este teste afirmava que
    `fotos/` devolvia **501**, e deixou de ser verdade: `nota_fotos` existe e
    grava `FotoNota` ligado pelo `offline_id` da nota, precisamente para a foto
    poder chegar **antes** da nota na fila offline. A implementacao e' melhor
    do que a especificacao que este teste guardava, e o que estava a travar
    (o 404) continua travado.

    O que a rota faz agora, sem ficheiro, e' 400 com o motivo: existe e valida
    a entrada. Um 501 aqui voltaria a dizer "ainda nao existe" sobre uma rota
    que existe.

    A distincao de fundo mantém-se intacta, e e' a que interessa: **404 e' um
    bug** (o `sync.js:144` e' um `fetch` com `catch` e perderia a foto sem ver
    erro); **501 e' uma decisao** (a rota existe e diz o que falta);
    **400 e' validacao** (a rota existe, o pedido e' que esta errado).
    """
    user, prop, tal = talhao_do_user
    login(cliente, user)
    r = cliente.post(reverse("api-caderno-fotos"), {})
    assert r.status_code != 404, "a rota voltou a desaparecer"
    assert r.status_code == 400, (
        f"sem ficheiro, `fotos/` devolve 400 com o motivo; veio {r.status_code}: "
        f"{r.content[:200]}"
    )
    corpo = r.json()
    assert corpo["ok"] is False
    assert corpo["erro"], "tem de dizer o que falta, nao apenas que falta"


def test_voice_diz_501(cliente, talhao_do_user):
    user, prop, tal = talhao_do_user
    login(cliente, user)
    r = cliente.post(reverse("api-caderno-voice"), {})
    assert r.status_code == 501
    assert r.json()["ok"] is False


# --------------------------------------------------------------------------
# 6. As rotas que o `sync.js` espera resolvem
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rota",
    ["api-caderno-notas", "api-caderno-fotos", "api-caderno-voice"],
)
def test_rota_resolve(rota):
    """O sintoma original era `Resolver404`. Estas tres rotas tem de
    resolver, mesmo as que devolvem 501."""
    assert reverse(rota)
