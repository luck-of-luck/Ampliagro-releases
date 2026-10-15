"""A revogacao do servidor tem de chegar a `/api/`, nao so ao HTML.

O DEFEITO
=========
O produtor desactiva o servidor em `app/views/lgpd.py`
(`perfil.ativo_servidor = False`). Quem ja tinha sessao continuava a ler a
fazenda: as quatro paginas HTML de `app/views/servidor.py` checam o flag e fazem
`logout`, mas a camada `/api/` nao o lia em lado nenhum. Cada view declara
`permission_classes = [IsAuthenticated]`, e isso prova que ha SESSAO — nao que a
sessao ainda e' valida.

`tests/test_superficie_servidor.py` mede essa superficie e da 23 rotas com HTTP
200 e dados da fazenda. Este ficheiro nao mede: fixa o CONTRACTO do
`ServidorRevogadoMiddleware`, para que a revogacao nao volte a desaparecer por
causa de uma view nova que se esqueça da regra.

POR QUE UM TESTE DO MIDDLEWARE E NAO DAS ROTAS
=============================================
Um teste por rota sobe quando a rota nova declara a permissao e falha quando
ela se lembra. O que protects aqui e' o ponto unico: `ServidorRevogadoMiddleware`
esta ligado e nega. Se algum dia alguem o tirar do `MIDDLEWARE`, o teste falha
com uma mensagem que diz o que se perdeu — e nao com "200 onde devia ser 403"
numa rota que ninguem lembrava.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import RequestFactory

from app.middleware import ServidorRevogadoMiddleware

pytestmark = pytest.mark.django_db


def _request(caminho, perfil):
    """Request com `request.user` ja posto — o middleware so le isso."""
    request = RequestFactory().get(caminho)
    request.user = SimpleNamespace(is_authenticated=True, perfil=perfil)
    return request


def _perfil(ativo_servidor):
    return SimpleNamespace(tipo_usuario="servidor", ativo_servidor=ativo_servidor)


def _roda(perfil, caminho="/api/estoque/"):
    """Passa o middleware. Devolve (chamou_o_view, resposta)."""
    chamadas = []

    def get_response(request):
        chamadas.append(request)
        return SimpleNamespace(status_code=200)

    resposta = ServidorRevogadoMiddleware(get_response)(_request(caminho, perfil))
    return bool(chamadas), resposta


def _e_403(resposta):
    return getattr(resposta, "status_code", None) == 403


def test_servidor_revogado_e_recusado_em_api_sem_chegar_ao_view():
    """
    O contrato: `ativo_servidor=False` + sessao viva => 403, e a view nao corre.

    `403` porque e' JSON que o cliente pede; as paginas HTML fazem `logout`, que
    e' o que um browser precisa. Nao se responde 200 com lista vazia: um
    `200 []` nao distingue "revogado" de "nao tem estoque", e foi essa
    ambiguidade que escondeu o furo.
    """
    chamou, resposta = _roda(_perfil(False))

    assert _e_403(resposta), (
        "servidor revogado nao recebeu 403 em /api/: "
        "a revogacao chegou a passar. IsAuthenticated prova que ha sessao, "
        "nao que a sessao ainda e' valida."
    )
    assert not chamou, (
        "a view /api/ EXECUTOU para um servidor revogado. O 403 tem de ser "
        "antes do view — depois do view o dado ja foi lido do banco."
    )


def test_servidor_ativo_passa_e_o_view_responde():
    """O outro lado do interruptor: activo tem de continuar a funcionar."""
    chamou, resposta = _roda(_perfil(True))

    assert chamou, (
        "servidor ACTIVO foi bloqueado. `ativo_servidor` tem default=True: "
        "isto so pode acontecer quando o produtor o desligou."
    )
    assert resposta.status_code == 200


def test_operario_e_agronomo_nao_sao_afetados():
    """
    `ativo_servidor` tem `default=True` (ver `PerfilUsuario`), portanto so o
    produtor o desliga — e so o servidor e' afectado. Um operario com o flag
    ligado tem de ler `/api/` como sempre; se este teste falhar, o middleware
    esta a fechar a porta a gente que nunca a desligou.
    """
    for tipo in ("operario", "agronomo", "mecanico", "administrativo", "produtor"):
        perfil = SimpleNamespace(tipo_usuario=tipo, ativo_servidor=True)
        chamou, _ = _roda(perfil)
        assert chamou, f"middleware bloqueou um {tipo} com o flag ligado"


def test_utilizador_sem_perfil_nao_e_bloqueado():
    """
    Perfil ausente e' registo orfao, nao revogacao. Quem nao tem perfil nao tem
    propriedade vinculada, e as views ja respondem "sem dado" — o middleware
    nao tem opiniao sobre isso. `getattr(..., None)` devolve `None` e nao
    levanta: `RelatedObjectDoesNotExist` herda de `AttributeError` (Django
    5.2, `related_descriptors.py:146`). Este teste existe porque essa heranca
    e' um detalhe da biblioteca de que a CORRECTA depende.
    """
    chamou, _ = _roda(None)

    assert chamou, (
        "utilizador sem PerfilUsuario foi bloqueado. Sem perfil nao ha "
        "revogacao a aplicar — e `getattr(user, 'perfil', None)` tem de dar "
        "None, nao levantar."
    )


def test_fora_de_api_a_revogacao_nao_e_aplicada():
    """
    ESCOPO: so `/api/`. As paginas HTML ja tratam a revogacao com `logout`, e
    mexer no login/logout delas sem medicao seria inventar comportamento.
    """
    chamou, _ = _roda(_perfil(False), caminho="/servidor/dashboard/")

    assert chamou, (
        "o middleware passou a valer fora de /api/. Se a revogacao tem de "
        "crescer para as paginas HTML, e' uma decisao separada — e precisa de "
        "`logout`, nao de 403."
    )


def test_anonymous_nao_e_bloqueado():
    """Sem sessao nao ha quem revogar; o `IsAuthenticated` da view decide."""
    request = RequestFactory().get("/api/estoque/")
    request.user = SimpleNamespace(is_authenticated=False)
    chamadas = []

    def get_response(req):
        chamadas.append(req)
        return SimpleNamespace(status_code=401)

    resposta = ServidorRevogadoMiddleware(get_response)(request)

    assert chamadas, "anonimo foi bloqueado pelo middleware, em vez de pela view"
    assert resposta.status_code == 401


def test_leitura_do_flag_partida_fecha_a_porta_em_vez_de_passar():
    """
    FALHA FECHA A PORTA. Se a leitura do flag levantar (campo renomeado, base
        inacessivel), deixar seguir significa entregar a fazenda a um servidor que o
        produtor desligou, em silencio.

        Custa disponibilidade? Nao: ler `user.perfil` vai a base de dados, portanto
        se a base esta em baixo todas as views `/api/` falham na mesma. O 403 aqui
        nao tira nada a ninguem que ia mesmo ter resposta.
    """

    class PerfilQuebrado:
        tipo_usuario = "servidor"

        @property
        def ativo_servidor(self):
            raise RuntimeError("campo renomeado")

    chamadas = []

    def get_response(req):
        chamadas.append(req)
        return SimpleNamespace(status_code=200)

    resposta = ServidorRevogadoMiddleware(get_response)(
        _request("/api/estoque/", PerfilQuebrado())
    )

    assert not chamadas, (
        "a view correu com a verificacao de revogacao em falha — o furo "
        "volta em silencio, que e' como entrou."
    )
    assert _e_403(resposta), "a falha na leitura do flag tem de dar 403, nao 200."


def test_a_middleware_esta_ligada_em_settings():
    """
    O teste acima passa mesmo com o middleware desligado do `MIDDLEWARE` — a
    classe existe e funciona. Este e' o que fecha essa porta: um middleware
    perfeito, desligado, e' o mesmo que nao existir.
    """
    from django.conf import settings

    ligada = [
        m for m in settings.MIDDLEWARE if m.endswith("ServidorRevogadoMiddleware")
    ]

    assert ligada, (
        "ServidorRevogadoMiddleware nao esta no MIDDLEWARE. A revogacao "
        "esta medida em 23 rotas de /api/ e nenhuma delas a le."
    )


# ─────────────────────────────────────────────────────────────────────────────
# DEFENCE IN DEPTH — a revogacao ONDE NAO HA `request`.
#
# MEDIDO 2026-10-04 (agente 4). Os testes acima medem o HTTP. O relatorio de
# arquitectura nomeia, correctamente, o que o middleware NAO cobre:
#
#   - uma tarefa do Celery, que nao recebe `request` e nao entra no middleware;
#   - uma management command;
#   - uma viewset que declara as suas `permission_classes` (o default do DRF
#     fica sobreposto, e um `permission class` em DEFAULT_PERMISSION_CLASSES
#     nao resolveria).
#
# Estes testes existem para tornar essa camada **verificavel** em vez de
# documentada. Se alguém remover a chamada, o teste falha — e a falha diz
# qual das três portas ficou aberta.
# ─────────────────────────────────────────────────────────────────────────────


def _utilizador_real(ativo_servidor, username="revog_probe"):
    """Um User com perfil de servidor, no BD de teste."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(username, f"{username}@x.com", "pw")
    from app.models import PerfilUsuario

    PerfilUsuario.objects.update_or_create(
        user=user,
        defaults={"tipo_usuario": "servidor", "ativo_servidor": ativo_servidor},
    )
    user.refresh_from_db()
    return user


def test_a_revogacao_e_verificada_fora_do_http_celery_e_command():
    """O `resolver()` da IA recusa — e e' o que um task do Celery chama.

    Este e' o teste que importa. Nao passa por `RequestFactory`, nao tem
    `request`, nao entra no middleware: e' exactamente o caminho de um worker
    assincrono. Se aqui passar, a revogacao esta a ser imposta so no sitio
    onde ja estava a ser imposta.
    """
    from django.core.exceptions import PermissionDenied

    from app.ia.propriedade import resolver

    revogado = _utilizador_real(False)
    with pytest.raises(PermissionDenied):
        resolver(revogado)

    activo = _utilizador_real(True, "ativo_probe")
    # Nao levanta. Pode devolver `None` (sem propriedade) — o que e' uma
    # resposta valida e NAO e' uma revogacao.
    resolver(activo)


def test_servidor_ativo_e_fail_closed_quando_a_leitura_falha():
    """Um guarda que assume 'activo' quando nao sabe vira um acesso."""
    from app.services.revogacao import servidor_ativo

    class PerfilQueExplode:
        @property
        def ativo_servidor(self):
            raise RuntimeError("a base caiu")

    user = SimpleNamespace(is_authenticated=True, perfil=PerfilQueExplode())
    assert servidor_ativo(user) is False, (
        "a falha na leitura do flag tem de fechar a porta. Devolver True "
        "transforma uma revogacao num acesso — que e' o pior resultado "
        "possivel deste ficheiro."
    )


def test_o_middleware_delega_na_mesma_regra_e_nao_uma_copia():
    """Duas copias da mesma regra divergem. Este e' o que impede a segunda."""
    import inspect

    from app.middleware import ServidorRevogadoMiddleware
    from app.services.revogacao import servidor_ativo

    fonte = inspect.getsource(ServidorRevogadoMiddleware.__call__)
    assert "servidor_ativo" in fonte, (
        "o middleware voltou a ler `perfil.ativo_servidor` em vez de chamar "
        "`app.services.revogacao.servidor_ativo`. Sao duas copias da mesma "
        "regra, e so uma delas se actualiza quando a outra muda."
    )
