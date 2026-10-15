"""`GET /api/contexto-ia/` — comportamento e custo de queries.

O endpoint diz "tudo que a IA precisa saber em 1 chamada". A primeira parte
cumpre isso; a segunda, a do banco, e' que a media mediu.

MEDIDO (antes desta mudanca): o corpo do `for p in props` fazia 8 queries POR
PROPRIEDADE — `talhoes.count()`, `safras.count()`, `animais.all()` (todas as
linhas, so para somar uma coluna), `lotes_aquaticos.count()`,
`funcionarios.count()`, `devices.count()`, e as DUAS listas do payload
(`talhoes[:20]`, `safras[:10]`) que repetem as contagens acima. Com N
propriedades: `8N + 1`. Um produtor com 12 fazendas pagava 97 queries para
devolver um JSON.

Estes testes existem para travar as DUAS coisas: o numero que volta (compara-se
com o modelo, nao com um literal) e o custo (que nao cresce com N).
"""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from app.models import Animal, Funcionario, Propriedade, Safra, Talhao

pytestmark = pytest.mark.django_db


def _contagens_esperadas(prop, ano):
    """O que o corpo antigo devolveria — calculado em Python, sem N+1."""
    talhoes = list(prop.talhoes.filter(ativo=True))
    safras = list(prop.safras.filter(ano=ano))
    return {
        "talhoes": len(talhoes),
        "safras_ano": len(safras),
        "animais": sum(a.quantidade or 0 for a in prop.animais.all()),
        "lotes_aquaticos": prop.lotes_aquaticos.count(),
        "funcionarios": prop.funcionarios.filter(ativo=True).count(),
        "devices": prop.devices.count(),
    }


class TestComportamento:
    def test_devolve_as_contagens_de_cada_propriedade(self, auth_client, user_produtor):
        from django.utils import timezone

        ano = timezone.now().year
        prop = Propriedade.objects.filter(user=user_produtor).first()

        Talhao.objects.create(propriedade=prop, nome="T1", area_hectare=10)
        Talhao.objects.create(propriedade=prop, nome="T2", area_hectare=5)
        Funcionario.objects.create(
            propriedade=prop,
            nome="Joao",
            cargo="GERENTE",
            salario=1000,
            data_admissao=date(2020, 1, 1),
        )
        Animal.objects.create(propriedade=prop, especie="BOVINO", quantidade=12)

        r = auth_client.get("/api/contexto-ia/")
        assert r.status_code == 200
        dados = r.json()

        achada = next(p for p in dados["propriedades"] if p["id"] == prop.id)
        assert achada["contagens"]["talhoes"] == 2
        assert achada["contagens"]["funcionarios"] == 1
        # `quantidade` e' somada, nao contada: 12 animais = 12 cabecas.
        assert achada["contagens"]["animais"] == 12
        assert achada["contagens"] == _contagens_esperadas(prop, ano)

    def test_totais_somam_as_propriedades(self, auth_client, user_produtor):
        props = list(Propriedade.objects.filter(user=user_produtor))
        for i, prop in enumerate(props[:3]):
            Talhao.objects.create(propriedade=prop, nome=f"T{i}", area_hectare=1)

        r = auth_client.get("/api/contexto-ia/")
        dados = r.json()

        esperado = sum(p["contagens"]["talhoes"] for p in dados["propriedades"])
        assert dados["totais"]["talhoes"] == esperado

    def test_lista_de_talhoes_respeita_o_limite_de_20(self, auth_client, user_produtor):
        prop = Propriedade.objects.filter(user=user_produtor).first()
        for i in range(25):
            Talhao.objects.create(propriedade=prop, nome=f"T{i:02d}", area_hectare=1)

        r = auth_client.get("/api/contexto-ia/")
        achada = next(
            p for p in r.json()["propriedades"] if p["id"] == prop.id
        )
        # A contagem diz 25; a lista traz 20. Sao coisas diferentes e as duas
        # tem de continuar a dizer isso.
        assert achada["contagens"]["talhoes"] == 25
        assert len(achada["talhoes"]) == 20

    def test_isolamento_por_usuario(self, auth_client, user_produtor, user_factory):
        outro = user_factory(username="outro_produtor")
        Propriedade.objects.create(user=outro, nome="Fazenda Alheia", area_total=1)
        Animal.objects.create(
            propriedade=Propriedade.objects.filter(user=outro).first(),
            especie="BOVINO",
            quantidade=999,
        )

        dados = auth_client.get("/api/contexto-ia/").json()
        assert all(p["nome"] != "Fazenda Alheia" for p in dados["propriedades"])
        # 999 e' a soma de um animal que NAO e' do usuario logado.
        assert dados["totais"]["animais"] < 999


class TestCustoDeQueries:
    """O numero de queries nao pode crescer com o numero de propriedades."""

    def _queries(self, client):
        with CaptureQueriesContext(connection) as ctx:
            r = client.get("/api/contexto-ia/")
        assert r.status_code == 200
        return len(ctx.captured_queries)

    def test_nao_cresce_com_o_numero_de_propriedades(
        self, auth_client, user_produtor
    ):
        uma = self._queries(auth_client)  # o usuario ja tem >=1 propriedade

        for i in range(6):
            prop = Propriedade.objects.create(
                user=user_produtor, nome=f"Fazenda Nova {i}", area_total=1
            )
            Talhao.objects.create(propriedade=prop, nome="T", area_hectare=1)

        sete = self._queries(auth_client)

        # Sete propriedades custam o mesmo que uma. Antes: 8N+1, ou seja, esta
        # afirmacao dava 9 vs 57.
        assert sete == uma, f"{uma} queries com 1 propriedade, {sete} com 7"

    def test_custo_total_e_uma_constante_pequena(self, auth_client, user_produtor):
        # Teto generoso de propósito: o que prende e' a INDEPENDENCIA de N
        # (teste anterior). Este só apanha um regresso que multiplica o
        # trabalho por dentro de uma unica propriedade.
        assert self._queries(auth_client) <= 20
