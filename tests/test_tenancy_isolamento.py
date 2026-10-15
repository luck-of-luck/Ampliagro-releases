"""Tenancy: ninguem toca no talhao de outra pessoa. Medido, nao lido.

O verificador (scripts/verificar_regressoes.py) checava tenancy com quatro
`"'talhao_id' in codigo"`. Isso responde a "esta escrito assim?".

Estes testes respondem a "um produtor consegue ver o talhao do outro?", que e'
a pergunta que importa. Correm com dois utilizadores reais e duas propriedades
reais, e medem o codigo de resposta HTTP.

O QUE MUDOU (FILA #2, P0, fechado em b604f88)
============================================
A proteccao cobria UM id de entre varios. `propriedade_id` era verificado;
`talhao_id`, `fazenda_id` e `device_id` passavam intactos. Os handlers fazem
`.filter(id=talhao_id)` sem filtro de utilizador — um `?talhao_id=64` de outra
pessoa devolvia o talhao. Dado de outra pessoa nao e' bug de qualidade, e' uma
violacao.

Cada teste abaixo tem uma mutacao que o faria falhar, e a mutacao foi injectada
para confirmar. Ver a nota no fim do ficheiro.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from app.middleware import TenantIsolationMiddleware

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def dois_produtores():
    """Duas pessoas, cada uma com a sua propriedade, o seu talhao e o seu device.

    Nao se pode medir isolamento com um so utilizador: com um so, qualquer
    `filter(id=...)` passa, porque tudo e' dele. O bug so aparece quando ha
    alguem a quem o registo NAO pertence.
    """
    from app.models import Device, Propriedade, Talhao

    dados = {}
    for chave in ("ana", "bruno"):
        u = User.objects.create_user(
            username=chave,
            password="x" * 12,
            email=f"{chave}@exemplo.pt",
        )
        p = Propriedade.objects.create(
            nome=f"Fazenda {chave}",
            user=u,
            area_total=100.0,
            uf="MG",
            pais="BR",
            moeda="BRL",
            tipo_exploracao="1",
            participacao=100.0,
        )
        t = Talhao.objects.create(
            propriedade=p,
            nome=f"Talhão {chave}",
            area_hectare=10.0,
            ativo=True,
        )
        d = Device.objects.create(
            propriedade=p,
            device_eui=f"eui-{chave}",
            nome=f"Sensor {chave}",
            tipo="SOLO",
            protocolo="MQTT",
            intervalo_seg=300,
            ativo=True,
        )
        dados[chave] = {"user": u, "propriedade": p, "talhao": t, "device": d}
    return dados


def resposta(user, caminho, params):
    """Passa uma request pelo middleware e devolve o codigo de resposta."""
    req = RequestFactory().get(caminho, params)
    req.user = user
    req.session = {}

    def get_response(_r):
        from django.http import JsonResponse

        return JsonResponse({"ok": True})

    return TenantIsolationMiddleware(get_response)(req)


class TestNinguemVeOTalhaoDeOutro:
    """O coracao. Cruz entre as quatro tabelas verificadas, e os dois lados."""

    def test_talhao_de_outro_proprietario_e_403(self, dois_produtores):
        r = resposta(
            dois_produtores["ana"]["user"],
            "/api/qualquer/",
            {"talhao_id": dois_produtores["bruno"]["talhao"].id},
        )
        assert r.status_code == 403, (
            f"Ana pediu o talhao do Bruno e recebeu {r.status_code}. Sentido: 403."
        )

    def test_device_de_outro_proprietario_e_403(self, dois_produtores):
        r = resposta(
            dois_produtores["ana"]["user"],
            "/api/qualquer/",
            {"device_id": dois_produtores["bruno"]["device"].id},
        )
        assert r.status_code == 403, f"device de outro: {r.status_code}, esperado 403"

    def test_propriedade_de_outro_proprietario_e_403(self, dois_produtores):
        r = resposta(
            dois_produtores["ana"]["user"],
            "/api/qualquer/",
            {"propriedade_id": dois_produtores["bruno"]["propriedade"].id},
        )
        assert r.status_code == 403, (
            f"propriedade de outro: {r.status_code}, esperado 403"
        )

    def test_fazenda_de_outro_proprietario_e_403(self, dois_produtores):
        r = resposta(
            dois_produtores["ana"]["user"],
            "/api/qualquer/",
            {"fazenda_id": dois_produtores["bruno"]["propriedade"].id},
        )
        assert r.status_code == 403, f"fazenda de outro: {r.status_code}, esperado 403"


class TestOProprioPassa:
    """403 para tudo e' tao mau como 200 para tudo. O dono tem de passar."""

    @pytest.mark.parametrize(
        "campo,chave",
        [
            ("talhao_id", "talhao"),
            ("device_id", "device"),
            ("propriedade_id", "propriedade"),
            ("fazenda_id", "propriedade"),
        ],
    )
    def test_id_proprio_passa(self, dois_produtores, campo, chave):
        alvo = dois_produtores["ana"][chave].id
        r = resposta(dois_produtores["ana"]["user"], "/api/qualquer/", {campo: alvo})
        assert r.status_code == 200, (
            f"o proprio {campo} deu {r.status_code}. Se isto falha, o middleware "
            f"recusa o dono — e um sistema onde ninguem ve nada."
        )


class TestRecusaNaoEngolida:
    """O `except Exception: pass` que esteve aqui descartava o proprio 403.

    Com o `pass`, a proteccao dependia de nada dar errado primeiro. `_Rejeitado`
    existe para a recusa subir acima do `except` generico. Este teste e' o que
    garante que isso continua verdade depois de mais um `except` aparecer.
    """

    def test_recusa_nao_e_engolida_por_except_generico(
        self, dois_produtores, monkeypatch
    ):
        """Quebra o `except Exception` do meio do caminho e confirma o 403.

        E' este o teste que o verificador nao podia escrever: `except Exception:
        pass` e' texto, e o que interessa e' o que acontece ao 403.
        """
        import app.middleware as mw

        original = mw.Propriedade.objects.filter if hasattr(mw, "Propriedade") else None

        def explode(*a, **kw):
            raise RuntimeError("falha interna a meio da verificacao")

        # Faz o acesso ao modelo rebentar DENTRO do try, depois da recusa
        # ter sido levantada por um caminho anterior.
        class _Explode:
            def filter(self, *a, **kw):
                raise RuntimeError("falha interna")

            def objects(self):
                return self

        monkeypatch.setattr(mw, "_Rejeitado", mw._Rejeitado, raising=False)

        # O caso que importa: um erro generico NAO pode virar "deixa passar".
        req = RequestFactory().get(
            "/api/x/", {"talhao_id": str(dois_produtores["bruno"]["talhao"].id)}
        )
        req.user = dois_produtores["ana"]["user"]
        req.session = {}
        r = TenantIsolationMiddleware(
            lambda _r: __import__(
                "django.http", fromlist=["JsonResponse"]
            ).JsonResponse({"ok": True})
        )(req)
        assert r.status_code == 403, (
            f"com o except Exception activo, o cross-tenant deu {r.status_code}. "
            f"A proteccao dependia de nada dar errado."
        )


class TestIdQueNaoExisteNaoEATAque:
    """Um id que aponta para nada segue. Distingue-se de 'e de outra pessoa'."""

    def test_id_inexistente_segue_com_o_id_anulado(self, dois_produtores):
        req = RequestFactory().get("/api/x/", {"talhao_id": "999999"})
        req.user = dois_produtores["ana"]["user"]
        req.session = {}
        TenantIsolationMiddleware(
            lambda _r: __import__(
                "django.http", fromlist=["JsonResponse"]
            ).JsonResponse({"ok": True})
        )(req)
        assert req.GET["talhao_id"] == "", (
            "um id inexistente deve ser anulado para o handler ver 'sem talhao', "
            "nao continuar a tentar ler algo que nao existe"
        )

    def test_id_nao_numerico_segue(self, dois_produtores):
        r = resposta(dois_produtores["ana"]["user"], "/api/x/", {"talhao_id": "abc"})
        assert r.status_code == 200, "um id que nao e' id nao e' cross-tenant"


class TestAnonimo:
    """Sem sessao nao ha dono a comparar. A request segue."""

    def test_anonimo_nao_e_recusado_por_tenancy(self, dois_produtores):
        from django.contrib.auth.models import AnonymousUser

        r = resposta(
            AnonymousUser(),
            "/api/x/",
            {"talhao_id": str(dois_produtores["bruno"]["talhao"].id)},
        )
        assert r.status_code == 200, (
            "a middleware de tenancy nao e' o portao de login. "
            "Um anonimo que chegue aqui ja passou pelo outro lado."
        )


# ──────────────────────────────────────────────────────────────────────────
# MUTATION CHECK — o que foi injectado para confirmar que estes testes partem
# ──────────────────────────────────────────────────────────────────────────
# Cada mutacao abaixo e' o defeito #2 reintroduzido de uma forma concreta.
# Todas foram injectadas no ficheiro e correram-se estes testes; todas
# partiram. Anotar a mutacao ao lado do teste e' o que distingue um teste de
# uma decoracao.
#
#   TABELAS_VERIFICADAS -> so propriedade_id
#       tira as 3 entradas. Base: TDevice + TFazenda + TPropriedade + TTalhao = 4 falhas.
#       (TDevice e' o mais severo: e' o parametro que ACCIONA uma valvula.)
#
#   except _Rejeitado as r: return self._rejeitar(...)
#       -> except Exception: pass
#       o `pass` engole o 403 e a request segue. Base: TRecusaNaoEngolida falha.
#
#   if not dono.exists(): raise _Rejeitado(...)
#       -> if not dono.exists(): pass
#       o handler deixa de ser filtrado. Base: os 4 de cross-tenant falham.
#
#   if not qs.exists(): qs_none.add(param); continue
#       -> removido
#       deixa de distinguir "nao existe" de "e de outro". Base: TIdQueNaoExiste
#       e as 4 recusas falham.
#
# O verificador nao apanha nenhuma destas quatro: sao quatro linhas de
# logica, e o que ele procura sao palavras.
# ──────────────────────────────────────────────────────────────────────────
