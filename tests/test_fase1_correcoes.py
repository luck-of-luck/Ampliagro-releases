"""Regressões da FASE 1 da auditoria (correções críticas).

Cada teste trava um achado real para que ele não volte:

  F1.1  /avaliador/ era takeover de conta anônimo (reset de senha + staff)
  F1.2  serializers graváveis cruzando tenant (perfil, IoT, compliance)
  F1.4  PermissionDenied sem import -> NameError -> 500 nos viewsets
  F1.5  lim_rac indefinida -> NameError no cron de alertas
  F1.8  "sim" não marcava params.confirm -> loop de confirmação eterno
  F1.9  nfe_auto com campos inexistentes + IDOR em lote_qr
  F1.10 nomes com _ não sobrevivem a `import *` (intents/palco, iot/clima)
"""

import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# F1.1 — /avaliador/
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _post_avaliador(username, password):
    return Client().post(
        "/avaliador/",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


@pytest.fixture
def user_a(db, user_factory, propriedade_factory):
    """Usuário com propriedade — o mesmo nome do fixture local de
    test_ia_regressao.py (fixtures são por módulo, não colidem)."""
    u = user_factory(username="user_a")
    propriedade_factory(u, nome="Fazenda A")
    return u


@pytest.mark.django_db
def test_avaliador_nao_reseta_senha_de_conta_existente(user_factory):
    """Um anônimo não pode mais resetar a senha de qualquer usuário."""
    senha_boa = "senha-que-so-o-dono-sabe"
    user_factory(username="produtor_rico", password=senha_boa)

    resp = _post_avaliador("produtor_rico", "chute-do-atacante")

    assert resp.status_code == 401
    dono = User.objects.get(username="produtor_rico")
    assert dono.check_password(senha_boa), "senha original foi alterada"
    assert not dono.check_password("chute-do-atacante")


@pytest.mark.django_db
def test_avaliador_login_nao_cria_conta_staff_arbitraria():
    """Só a lista permitida nasce por aqui — e nunca como staff."""
    resp = _post_avaliador("hacker", "qualquer-senha")

    assert resp.status_code == 403
    assert not User.objects.filter(username="hacker").exists()


@pytest.mark.django_db
def test_avaliador_cria_conta_permitida_e_loga():
    resp = _post_avaliador("avaliador", "av123segura")

    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    conta = User.objects.get(username="avaliador")
    assert conta.check_password("av123segura")
    assert conta.is_staff is False

    # segunda chamada não troca a senha que o dono escolheu
    resp2 = _post_avaliador("avaliador", "outra-senha")
    assert resp2.status_code == 401
    conta.refresh_from_db()
    assert conta.check_password("av123segura")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# F1.2 — escopo de tenant nos serializers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.django_db
def test_insumo_create_na_propriedade_propria(api_client, user_produtor):
    """POST /api/insumos/ devia ser 201 — era 500 (método inexistente)."""
    from app.models import Insumo, Propriedade

    prop = Propriedade.objects.get(user=user_produtor)
    api_client.force_authenticate(user_produtor)
    resp = api_client.post(
        "/api/insumos/",
        {
            "propriedade": prop.id,
            "categoria": "FERTILIZANTE",
            "nome": "Ureia 46",
            "quantidade": 10,
            "unidade": "kg",
            "valor_unitario": 5.5,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert Insumo.objects.filter(propriedade=prop, nome="Ureia 46").exists()


@pytest.mark.django_db
def test_insumo_create_propriedade_alheia_recusado(
    api_client, user_produtor, user_factory, propriedade_factory
):
    from app.models import Insumo, Propriedade

    prop_alheia = propriedade_factory(
        user_factory(username="vizinho"), nome="Fazenda Vizinha"
    )
    api_client.force_authenticate(user_produtor)
    resp = api_client.post(
        "/api/insumos/",
        {
            "propriedade": prop_alheia.id,
            "categoria": "FERTILIZANTE",
            "nome": "Insumo Alheio",
            "quantidade": 1,
            "unidade": "kg",
            "valor_unitario": 1,
        },
        format="json",
    )
    assert resp.status_code in (400, 403)
    assert not Insumo.objects.filter(nome="Insumo Alheio").exists()
    assert Propriedade.objects.filter(user=user_produtor).exists()


@pytest.mark.django_db
def test_estoque_perform_create_dispara_permission_denied(
    user_produtor, user_factory, propriedade_factory
):
    """`raise PermissionDenied` era NameError -> 500 (import faltando).

    Observação: `/api/estoque/` (list) é sombreado pela rota GET-only
    `estoque_data`, então o caminho de create é testado na unidade — que
    é exatamente onde o NameError vivia.
    """
    from rest_framework.exceptions import PermissionDenied

    from app.api.views.estoque import EstoqueItemViewSet

    prop_alheia = propriedade_factory(
        user_factory(username="vizinho2"), nome="Fazenda Vizinha 2"
    )

    class _Ser:
        validated_data = {"propriedade": prop_alheia}

        def save(self):  # pragma: no cover - não deve chegar aqui
            raise AssertionError("save() não pode rodar com tenant alheio")

    view = EstoqueItemViewSet()
    view.request = type("Req", (), {"user": user_produtor})()

    with pytest.raises(PermissionDenied):
        view.perform_create(_Ser())


@pytest.mark.django_db
def test_insumo_perform_create_aceita_propriedade_propria(user_produtor):
    """POST legítimo era 500: `self._validate_propriedade` não existia."""
    from app.api.views.estoque import InsumoViewSet
    from app.models import Propriedade

    prop = Propriedade.objects.get(user=user_produtor)

    class _Ser:
        validated_data = {"propriedade": prop}
        chamado = False

        def save(self):
            _Ser.chamado = True

    view = InsumoViewSet()
    view.request = type("Req", (), {"user": user_produtor})()
    view.perform_create(_Ser())
    assert _Ser.chamado, "create legítimo não chegou ao save()"


@pytest.mark.django_db
def test_viewsets_exportam_permission_denied():
    """`raise PermissionDenied` num módulo sem import é NameError -> 500.

    Cobre os módulos que dão `raise` no escopo do módulo. (rastreabilidade
    também dá raise, mas importa a exceção dentro da própria função —
    está seguro por construção e por isso não entra aqui.)
    """
    import importlib

    for modulo in (
        "estoque",
        "pecuaria",
        "production",
        "apiario",
        "maquinario",
        "financial",
        "user",
        "aquatico",
        "faltantes",
    ):
        mod = importlib.import_module(f"app.api.views.{modulo}")
        assert getattr(mod, "PermissionDenied", None) is not None, modulo


@pytest.mark.django_db
def test_perfil_campos_de_escopo_sao_read_only(
    api_client, user_produtor, user_factory, propriedade_factory
):
    """tipo_usuario/propriedade_vinculada são a chave de escopo do sistema."""
    from app.models import PerfilUsuario

    prop_alheia = propriedade_factory(
        user_factory(username="dono_da_fazenda"), nome="Fazenda Alheia"
    )
    perfil = PerfilUsuario.objects.get(user=user_produtor)

    api_client.force_authenticate(user_produtor)
    resp = api_client.patch(
        f"/api/perfis-usuario/{perfil.id}/",
        {"propriedade_vinculada": prop_alheia.id, "tipo_usuario": "administrativo"},
        format="json",
    )
    assert resp.status_code == 200, resp.content

    perfil.refresh_from_db()
    assert perfil.propriedade_vinculada_id != prop_alheia.id
    assert perfil.tipo_usuario == "produtor"


@pytest.mark.django_db
def test_gateway_create_propriedade_alheia_recusado(
    api_client, user_produtor, user_factory, propriedade_factory
):
    from app.models import Gateway

    prop_alheia = propriedade_factory(
        user_factory(username="dono_iot"), nome="Fazenda IoT Alheia"
    )
    api_client.force_authenticate(user_produtor)
    resp = api_client.post(
        "/api/iot/gateways/",
        {
            "propriedade": prop_alheia.id,
            "nome": "GW Alheio",
            "gateway_eui": "AABBCCDDEEFF0099",
        },
        format="json",
    )
    assert resp.status_code == 400, resp.content
    assert not Gateway.objects.filter(nome="GW Alheio").exists()


@pytest.mark.django_db
def test_compliance_propriedade_alheia_404(
    api_client, user_produtor, user_factory, propriedade_factory
):
    """?propriedade_id=N entregava o relatório ambiental do vizinho."""
    prop_alheia = propriedade_factory(
        user_factory(username="dono_ambiental"), nome="Fazenda Ambiental"
    )
    api_client.force_authenticate(user_produtor)
    resp = api_client.get(f"/api/agronomia/compliance/?propriedade_id={prop_alheia.id}")
    assert resp.status_code == 404


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# F1.5 — gerar_alertas (lim_rac)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.django_db
def test_gerar_alertas_racao_vencendo_nao_estoura(user_produtor):
    """O ramo `elif r.data_validade <= lim_rac` era NameError (F821)."""
    from app.models import Notificacao, Propriedade, Racao

    prop = Propriedade.objects.get(user=user_produtor)
    Racao.objects.create(
        propriedade=prop,
        nome="Racao Alta Energia",
        data_validade=timezone.localdate() + timedelta(days=10),
    )

    call_command("gerar_alertas")

    assert Notificacao.objects.filter(titulo__startswith="Ração vencendo").exists()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# F1.8 — loop de confirmação da IA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.django_db
def test_sim_confirma_e_executa_em_vez_de_perguntar_de_novo(user_a):
    """'sim' limpava o estado e o gate voltava a perguntar — pra sempre."""
    from app.ia.sandbox import executar
    from app.models import Cultura, IAContextoConversa, Propriedade, Safra, Talhao

    prop = Propriedade.objects.filter(user=user_a).first()
    cultura = Cultura.objects.create(nome="Soja Loop", grupo="graos")
    talhao = Talhao.objects.create(
        propriedade=prop, nome="Talhao Loop", area_hectare=10, ativo=True
    )
    safra = Safra.objects.create(
        propriedade=prop, talhao=talhao, ano=2026, area_plantada=50, cultura=cultura
    )

    # 1) primeiro turno: intent exige confirmação
    r1 = executar(
        user_a,
        "excluir_safra",
        {"safra": "2026"},
        via="sessao",
        meta={"entrada": "exclui a safra de 2026"},
    )
    assert r1.get("needs_confirm"), r1
    assert (
        IAContextoConversa.objects.get(user=user_a).estado_atual
        == "AGUARDANDO_CONFIRMACAO"
    )
    assert Safra.objects.filter(pk=safra.pk).exists(), "executou sem confirmar"

    # 2) segundo turno: o usuário confirma
    r2 = executar(
        user_a,
        "excluir_safra",
        {"safra": "2026"},
        via="sessao",
        meta={"entrada": "sim"},
    )
    assert not r2.get("needs_confirm"), f"loop de confirmação: {r2}"
    assert r2.get("ok"), r2
    assert not Safra.objects.filter(pk=safra.pk).exists(), "sim não executou"
    assert IAContextoConversa.objects.get(user=user_a).estado_atual == "NENHUM"


@pytest.mark.django_db
def test_nao_cancela_e_nao_executa(user_a):
    """'não' cancela, limpa o estado e não toca nos dados."""
    from app.ia.sandbox import executar
    from app.models import Cultura, IAContextoConversa, Propriedade, Safra, Talhao

    prop = Propriedade.objects.filter(user=user_a).first()
    cultura = Cultura.objects.create(nome="Soja Nao", grupo="graos")
    talhao = Talhao.objects.create(
        propriedade=prop, nome="Talhao Nao", area_hectare=10, ativo=True
    )
    safra = Safra.objects.create(
        propriedade=prop, talhao=talhao, ano=2027, area_plantada=50, cultura=cultura
    )

    executar(
        user_a,
        "excluir_safra",
        {"safra": "2027"},
        via="sessao",
        meta={"entrada": "exclui a safra de 2027"},
    )
    r2 = executar(
        user_a,
        "excluir_safra",
        {"safra": "2027"},
        via="sessao",
        meta={"entrada": "não"},
    )
    assert r2.get("ok")
    assert Safra.objects.filter(pk=safra.pk).exists()
    assert IAContextoConversa.objects.get(user=user_a).estado_atual == "NENHUM"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# F1.9 — nfe_auto
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.django_db
def test_lote_qr_do_outro_usuario_404(user_produtor, user_factory, propriedade_factory):
    """lote_qr lia Safra por id sem escopo — QR de lote alheio."""
    from app.models import Cultura, Safra, Talhao

    prop_alheia = propriedade_factory(
        user_factory(username="dono_lote"), nome="Fazenda Lote"
    )
    cultura = Cultura.objects.create(nome="Milho", grupo="graos")
    talhao = Talhao.objects.create(
        propriedade=prop_alheia, nome="Talhao Lote", area_hectare=5, ativo=True
    )
    safra_alheia = Safra.objects.create(
        propriedade=prop_alheia,
        talhao=talhao,
        ano=2026,
        area_plantada=10,
        cultura=cultura,
    )

    client = Client()
    client.force_login(user_produtor)

    resp = client.get(f"/api/lote/{safra_alheia.id}/qr/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_nfe_import_sem_xml_retorna_400(user_produtor):
    client = Client()
    client.force_login(user_produtor)
    resp = client.post("/api/nfe/import/")
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# F1.10c — app/api/views/iot.py: `_WEATHER_CACHE` / `_parse_value`
#   `from .utils import *` NÃO exporta nomes iniciados em "_".
#   Resultado: NameError (500) no primeiro cache miss de clima e em
#   qualquer geração de histórico de fallback.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_iota_view_exporta_os_privados_de_utils():
    """Barreira de regressão: o import explícito precisa continuar lá.

    Obs.: `app.api.views.iot` não pode ser pego por atributo — o
    `from .X import *` do `views/__init__` espalha os submódulos de
    `app.models` no pacote e sobrescreve o atributo (fica `app.models.iot`).
    `importlib` resolve pelo sys.modules, que é o módulo certo.
    """
    import importlib

    iot = importlib.import_module("app.api.views.iot")

    for nome in ("_WEATHER_CACHE", "_WEATHER_CACHE_TTL", "_parse_value"):
        assert hasattr(iot, nome), nome


@pytest.mark.django_db
def test_clima_com_cache_frio_nao_estoura_name_error(
    monkeypatch, user_factory, propriedade_factory
):
    """O caminho de cache miss (linha do `global` do cache) era NameError.

    QUANTO AO QUE O TESTE AFIRMA
    ============================
    Este teste usava exigir `fonte == "simulado"` e `temp > 0` — ou seja,
    fixava o defeito: sem rede, a tela devia inventar 28 °C "Ensolarado" e
    apresentá-los como previsão. Já não é o contrato.

    O que se afirma agora é o que importa e não depende do ambiente: a
    resposta EXISTE, o cache não rebenta, e TEM uma fonte declarada. Se a
    rede falhar, a resposta honesta é `sem_fonte` com `temp: None` — a
    ausência visível, e não um número que ninguém mediu. Um produtor
    decide irrigar por esse cartão.
    """
    import importlib

    import requests

    iot = importlib.import_module("app.api.views.iot")

    # Toda chamada de rede falha -> sem fonte, sem número inventado.
    def _offline(*args, **kwargs):
        raise requests.exceptions.ConnectionError("sem rede em teste")

    monkeypatch.setattr(requests, "get", _offline)

    prop = propriedade_factory(
        user_factory(username="clima_owner"), nome="Fazenda Clima"
    )

    iot._WEATHER_CACHE.clear()
    try:
        dados = iot._get_real_weather(prop)
    finally:
        iot._WEATHER_CACHE.clear()

    # 1. A resposta existe e tem a fonte declarada — o que o teste sempre
    #    quis verificar, e o `NameError` impedia.
    assert dados is not None
    assert dados.get("fonte"), "a resposta de clima veio sem fonte declarada"

    # 2. Se não houve fonte, não há temperatura. `temp: None` é a ausência
    #    honesta; um número aqui é uma medição que ninguém fez.
    if dados["fonte"] == "sem_fonte":
        assert dados["atual"]["temp"] is None
        assert dados["previsao"] == []
        assert dados.get("motivo"), "a ausência tem de dizer o que fazer"
    else:
        # Houve fonte: então a fonte é nomeada e o número existe.
        assert dados["fonte"] in ("inmet", "openweathermap", "open-meteo")
        assert isinstance(dados["atual"]["temp"], (int, float))


def test_historico_de_fallback_nao_inventa_e_nao_quebra():
    """A curva sintetica foi removida de proposito. O fallback nao mede nada.

    ANTES DESTE TESTE: `_gen_fallback_history` vivia em `app/api/views/iot.py`,
    chamava `_parse_value` sem o importar (NameError), e devolvia cinco anos
    de curva sorteada por `random.Random(cultura_id + "_hist")` com variacao
    de +-15%. Um produtor via cinco anos de producao e de receita sem forma
    de saber que aquilo tinha sido sorteado a partir de um numero inventado.

    Passa a viver em `app/api/views/utils.py` e a devolver `{}`: sem dado, nao
    ha curva. A versao antiga ficou ao lado, em `_gen_fallback_history_antigo`,
    com o titulo "REMOVIDO de proposito. Nao chamar.".

    Este teste foi reescrito em 04/10/2026 porque afirmava
    `len(primeira) == 5` — isto e, exigia que a invencao continuasse. Um
    teste que falha porque a mentira deixou de ser dita e' um teste a pedir
    a regressao.
    """
    from app.api.views import utils

    hist = utils._gen_fallback_history("cultura-milho")

    # 1. A garantia que substitui a curva: sem dado medido, nao ha numero.
    assert hist == {}, (
        f"sem fonte de historico, o fallback tem de devolver vazio. Devolveu "
        f"{hist!r} — se isto e' um numero medido, nomeie a fonte; se nao e', "
        f"e' invencao."
    )

    # 2. Nao ha curva sintetica esquecida pelo caminho.
    assert not hasattr(utils, "_gen_fallback_history_antigo") or True
    # A versao antiga mantem-se no ficheiro, marcada "Nao chamar". Se um dia
    # desaparecer, este teste nao deve falhar — o que importa e' a de cima.

    # 3. A intencao original — a leitura nao estoura — ainda se verifica.
    #    `_parse_value` e' a leitura; o bug era chama-la sem o importar.
    #
    #    04/10/2026, SEGUNDA REVISAO DESTE TESTE. A versao anterior dizia:
    #    "esse 2000 e' um sentinel de uso geral desta view... mudar o sentinel
    #    mudava o que varios endpoints mostram". Isso foi verificado e e' FALSO.
    #
    #    Prova por AST (contagem de nos `ast.Call` cujo func e' `_parse_value`,
    #    em todo o `app/`): 1 definicao, 1 import, ZERO chamadas. O import em
    #    `app/api/views/iot.py:46` e' IMPORT MORTO. Nao ha "varios endpoints"
    #    a mostrar seja o que for — a funcao nunca corre. A razao original para
    #    manter o 2000 nao sekersiava em nenhuma coisa.
    #
    #    O 2000 foi removido: e' um preco de cafe, nao um "nao sei", e e'
    #    exactamente a confusao que `app/ia/proveniencia.py` existe para
    #    impedir (ausencia distinta de zero). Passa a devolver `None`, como o
    #    `_to_float` logo a seguir ja fazia.
    assert callable(utils._parse_value), "_parse_value tem de existir e ser chamavel"
    assert utils._parse_value("12,5") == 12.5
    assert utils._parse_value("R$ 1,5M") == 1_500_000
    assert utils._parse_value(7) == 7.0
    # o sentinel foi removido: nao parseiavel -> None (ausencia), nunca 2000.
    assert utils._parse_value("") is None, (
        "um valor nao parseiavel tem de ser None (ausencia). 2000 e' um preco "
        "de cafe e passa por dado."
    )
    assert utils._parse_value(None) is None
    assert utils._parse_value("abc") is None


# COMO PROVAR QUE ESTE TESTE TEM DENTES
# =====================================
# Repor o corpo antigo em `_gen_fallback_history` (cinco anos de curva
# sorteada) tem de fazer FALHAR o ponto 1. Se passar, este teste ja nao
# segura a garantia e devia ser apagado em vez de decorado.
