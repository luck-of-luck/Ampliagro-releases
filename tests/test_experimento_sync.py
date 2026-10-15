"""A2b — o servidor tem de aceitar a medicao do produtor **uma vez so**.

O QUE ESTE FICHEIRO PROVA, E O QUE NAO PROVA
---------------------------------------------
O JS (`tests_experimento_sync.cjs`) prova que o cliente manda o `uid` e que
reenvia quando a resposta se perde. Este prova que o **servidor** reconhece o
`uid` e nao duplica.

A razao de serem dois ficheiros: o mesmo bug — um duplicado — pode ser
introduzido em qualquer um dos lados, e testar so um deles deixa o outro livre
de reintroduzir o problema. E' a mesma razao que fez o A0 ter um `.cjs` e um
`.py`.

O BUG DE REFERENCIA
-------------------
`app/static/js/data-sync.js` faz `item.id ? PUT : POST`. O POST chega ao
servidor, a resposta nao chega ao cliente, `item.id` continua vazio, e a
proxima sincronizacao faz POST outra vez: **duplicado**, sem forma de o
servidor saber que e' o mesmo registo.

Estes testes sao a contraprovva. Se alguem trocar o upsert por um `create`, ou
tirar o `unique=True` do `uid`, o `test_reenvio_nao_duplica` falha.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from app.api.serializers import (
    Experimento_Serializer,
    MedicaoExperimental_Serializer,
)
from app.models import (
    Cultura,
    Experimento,
    MedicaoExperimental,
    Propriedade,
    Safra,
    Talhao,
)

# ------------------------------------------------------------------ fixtures


@pytest.fixture
def user(db):
    return User.objects.create_user("produtor", password="x")


@pytest.fixture
def vizinho(db):
    return User.objects.create_user("vizinho", password="x")


@pytest.fixture
def propriedade(user):
    return Propriedade.objects.create(user=user, nome="Fazenda A", area_total=100)


@pytest.fixture
def talhao(propriedade):
    return Talhao.objects.create(
        propriedade=propriedade, nome="T1", area_hectare=10, ativo=True
    )


@pytest.fixture
def cultura():
    return Cultura.objects.create(nome="Soja", grupo="graos")


@pytest.fixture
def safra(propriedade, talhao, cultura):
    return Safra.objects.create(
        propriedade=propriedade,
        talhao=talhao,
        cultura=cultura,
        ano=2026,
        area_plantada=10,
    )


def criar_experimento(user, **extra) -> Experimento:
    return Experimento.objects.create(
        user=user,
        nome="NPK",
        hypothesis="nitrogenio extra melhora a produtividade",
        metricas=["produtividade"],
        **extra,
    )


# ================================================================== o uid


class TestUid:
    def test_uid_e_gerado_e_unico(self, db):
        a = Experimento.objects.create(user=_u(), nome="A")
        b = Experimento.objects.create(user=_u(), nome="B")
        assert a.uid and b.uid
        assert a.uid != b.uid

    def test_uid_e_unico_no_banco(self, user, django_user_model):
        """O `unique=True` e' o que torna o upsert possivel.

        Sem isto, dois pedidos com o mesmo uid criavam dois registos e o
        servidor nao tinha como saber que era o mesmo.
        """
        exp = criar_experimento(user)
        with pytest.raises(IntegrityError):
            Experimento.objects.create(user=user, nome="B", uid=exp.uid)

    def test_registro_em_he_obrigatorio(self, user):
        """Sem `registado_em` nao se sabe a condicao em que mediram.

        E' o relogio do produtor, no talhao — e a unica coisa que o servidor
        nao pode preencher sozinho.
        """
        exp = criar_experimento(user)
        m = MedicaoExperimental(
            experimento=exp,
            tratamento="A",
            dados={"produtividade": 50},
            fonte_dado="medido",
        )
        with pytest.raises(IntegrityError):
            m.save()

    def test_sincronizado_em_e_do_servidor(self, user):
        exp = criar_experimento(user)
        m = MedicaoExperimental.objects.create(
            experimento=exp,
            tratamento="A",
            dados={"produtividade": 50},
            fonte_dado="medido",
            registado_em=timezone.now(),
        )
        assert m.sincronizado_em is not None


def _u():
    return User.objects.create_user(
        f"u{Experimento.objects.count()}{id(object())}"[:150]
    )


# ======================================================= idempotencia no push


class TestReenvioNaoDuplica:
    """O teste que o `data-sync.js` nao passa."""

    def test_o_mesmo_uid_duas_vezes_da_o_mesimo_registo(self, user, client):
        client.force_login(user)
        corpo = {
            "nome": "NPK",
            "hypothesis": "melhora",
            "metricas": ["produtividade"],
            "significance_level": 0.05,
        }
        r1 = client.post("/api/experimentos/", corpo, content_type="application/json")
        assert r1.status_code == 201, r1.content[:300]
        uid = r1.json()["uid"]

        # A segunda tentativa leva o MESMO uid: e' a resposta que se perdeu.
        corpo2 = dict(corpo, uid=uid)
        r2 = client.post("/api/experimentos/", corpo2, content_type="application/json")
        assert r2.status_code == 200, r2.content[:300]

        assert Experimento.objects.count() == 1
        assert r2.json()["id"] == r1.json()["id"]

    def test_lote_reenviado_nao_duplica_nenhuma_medicao(self, user, client):
        client.force_login(user)

        def uma(n):
            return {
                "uid": f"m-{n}",
                "experimento_uid": uid,
                "tratamento": "A" if n % 2 == 0 else "B",
                "talhao": None,
                "dados": {"produtividade": 50 + n},
                "contexto": {"fonte_dado": "medido"},
                "fonte_dado": "medido",
                "registado_em": timezone.now().isoformat(),
            }

        exp_r = client.post(
            "/api/experimentos/",
            {"nome": "X", "metricas": ["produtividade"]},
            content_type="application/json",
        )
        uid = exp_r.json()["uid"]

        lote = [uma(1), uma(2), uma(3)]
        r1 = client.post(
            "/api/medicoes-experimentais/lote/",
            {"medicoes": lote},
            content_type="application/json",
        )
        assert r1.status_code == 200, r1.content[:400]
        assert r1.json()["criados"] == 3, r1.json()
        assert MedicaoExperimental.objects.count() == 3

        # O reenvio: o cliente nao sabe que a primeira vez chegou.
        r2 = client.post(
            "/api/medicoes-experimentais/lote/",
            {"medicoes": lote},
            content_type="application/json",
        )
        assert r2.json()["criados"] == 0, r2.json()
        assert r2.json()["ja_existiam"] == 3, r2.json()
        eq = MedicaoExperimental.objects.count()
        assert eq == 3, f"o lote reenviado duplicou: {eq} medicoes em vez de 3"

    def test_lote_misto_cria_novas_e_conta_as_que_ja_existem(self, user, client):
        client.force_login(user)
        uid = client.post(
            "/api/experimentos/",
            {"nome": "Y", "metricas": ["produtividade"]},
            content_type="application/json",
        ).json()["uid"]

        def uma(n, sufixo=""):
            return {
                "uid": f"m{n}{sufixo}",
                "experimento_uid": uid,
                "tratamento": "A",
                "dados": {"produtividade": 50},
                "fonte_dado": "medido",
                "registado_em": timezone.now().isoformat(),
            }

        client.post(
            "/api/medicoes-experimentais/lote/",
            {"medicoes": [uma(1), uma(2)]},
            content_type="application/json",
        )
        # O produtor mediu mais duas enquanto offline, e reenvia as duas antigas.
        r = client.post(
            "/api/medicoes-experimentais/lote/",
            {"medicoes": [uma(1), uma(2), uma(3), uma(4)]},
            content_type="application/json",
        )
        j = r.json()
        assert j["criados"] == 2, j
        assert j["ja_existiam"] == 2, j
        assert MedicaoExperimental.objects.count() == 4


# ============================================== o que o servidor nao pode aceitar


class TestRejeicoes:
    def test_registado_em_no_futuro_e_recusado(self, user, client):
        """O relogio do aparelho pode estar errado. A data de chegada nunca e' futura."""
        client.force_login(user)
        uid = client.post(
            "/api/experimentos/",
            {"nome": "Z", "metricas": ["produtividade"]},
            content_type="application/json",
        ).json()["uid"]

        futuro = timezone.now() + timezone.timedelta(days=2)
        r = client.post(
            "/api/medicoes-experimentais/lote/",
            {
                "medicoes": [
                    {
                        "uid": "futuro",
                        "experimento_uid": uid,
                        "tratamento": "A",
                        "dados": {},
                        "fonte_dado": "medido",
                        "registado_em": futuro.isoformat(),
                    }
                ]
            },
            content_type="application/json",
        )
        j = r.json()
        assert j["rejeitados"] == 1, j
        assert MedicaoExperimental.objects.count() == 0
        # O erro diz QUAL e porque — o produtor tem de poder corrigir no campo.
        assert j["erros"] and "registado_em" in j["erros"][0]["erro"], j

    def test_uma_prescricao_alheia_e_recusada(
        self, user, vizinho, propriedade, talhao, cultura, safra, client
    ):
        """O A2b nao pode ser o vector que fura o multi-tenant.

        `MedicaoExperimental.prescricao` liga a medicao a proveniencia de outro.
        Sem esta validacao, um produtor envia o `prescricao_id` do vizinho e a
        medicao entra na base alheia.
        """
        from app.models import PrescricaoVRA

        p = PrescricaoVRA.objects.create(
            safra=safra,
            talhao=talhao,
            cultura=cultura,
            tipo_insumo="FERTILIZANTE",
            dose_ha=100,
            unidade="kg/ha",
        )

        client.force_login(vizinho)
        uid = client.post(
            "/api/experimentos/",
            {"nome": "Alheio", "metricas": ["produtividade"]},
            content_type="application/json",
        ).json()["uid"]

        r = client.post(
            "/api/medicoes-experimentais/lote/",
            {
                "medicoes": [
                    {
                        "uid": "alheia",
                        "experimento_uid": uid,
                        "prescricao": p.pk,
                        "tratamento": "A",
                        "dados": {},
                        "fonte_dado": "medido",
                        "registado_em": timezone.now().isoformat(),
                    }
                ]
            },
            content_type="application/json",
        )
        j = r.json()
        assert j["rejeitados"] == 1, j
        assert MedicaoExperimental.objects.count() == 0

    def test_uma_prescricao_ruim_nao_derruba_o_lote(
        self, user, propriedade, talhao, cultura, safra, client
    ):
        """O produtor mandou 40 medicoes e uma tem a prescricao errada.

        Perder as 39 boas porque uma falhou a validacao seria pior do que
        aceitar uma errada.
        """
        from app.models import PrescricaoVRA

        PrescricaoVRA.objects.create(
            safra=safra,
            talhao=talhao,
            cultura=cultura,
            tipo_insumo="FERTILIZANTE",
            dose_ha=100,
            unidade="kg/ha",
        )
        client.force_login(user)
        uid = client.post(
            "/api/experimentos/",
            {"nome": "Misto", "metricas": ["produtividade"]},
            content_type="application/json",
        ).json()["uid"]

        def uma(n):
            return {
                "uid": f"ok-{n}",
                "experimento_uid": uid,
                "tratamento": "A",
                "dados": {"produtividade": n},
                "fonte_dado": "medido",
                "registado_em": timezone.now().isoformat(),
            }

        lote = [uma(1), uma(2)]
        lote.append(dict(uma(3), uid="mau", prescricao=999999))
        r = client.post(
            "/api/medicoes-experimentais/lote/",
            {"medicoes": lote},
            content_type="application/json",
        )
        j = r.json()
        assert j["criados"] == 2, j
        assert j["rejeitados"] == 1, j
        assert MedicaoExperimental.objects.count() == 2

    def test_lote_vazio_e_um_erro_explicito(self, user, client):
        client.force_login(user)
        r = client.post(
            "/api/medicoes-experimentais/lote/", {}, content_type="application/json"
        )
        assert r.status_code == 400
        assert "medicoes" in r.json()["erro"]

    def test_significance_level_fora_de_0_a_1_e_recusado(self, user, client):
        """A barra de significancia decide-se ANTES de ver os dados."""
        client.force_login(user)
        r = client.post(
            "/api/experimentos/",
            {"nome": "Barra", "metricas": [], "significance_level": 5},
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "significance_level" in r.json()


# ================================================================= tenancy


class TestTenancy:
    def test_vizinho_nao_ve_a_medicao(self, user, vizinho, client):
        client.force_login(user)
        uid = client.post(
            "/api/experimentos/",
            {"nome": "Privado", "metricas": []},
            content_type="application/json",
        ).json()["uid"]
        client.post(
            "/api/medicoes-experimentais/lote/",
            {
                "medicoes": [
                    {
                        "uid": "p1",
                        "experimento_uid": uid,
                        "tratamento": "A",
                        "dados": {"custo": 1200},
                        "fonte_dado": "medido",
                        "registado_em": timezone.now().isoformat(),
                    }
                ]
            },
            content_type="application/json",
        )

        client.force_login(vizinho)
        assert client.get("/api/experimentos/").json()["results"] == []
        assert client.get("/api/medicoes-experimentais/").json()["results"] == []
