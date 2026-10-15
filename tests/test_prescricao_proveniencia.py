"""A2 — a procedencia do `PrescricaoVRA` tem de responder "porque mandou isto?".

ESTE FICHEIRO TESTA O §4.3 DA CARTA
------------------------------------
O §4.3 é a aposta que sobreviveu à revisão adversarial: **procedencia auditavel
por talhao e por decisao**. Cada recomendacao guardada com a evidencia que a
produziu, a versao da analise, e o **erro medido contra o desfecho**.

Porque e' o diferençador defensavel: um competidor com 9 anos de dados nao
versionados nao consegue retrofitar isto. Lock-in real nasce do que e' caro de
recriar, nao do volume bruto.

O QUE ESTE FICHEIRO TRAVA
-------------------------
A regra `fonte_dado` no sitio onde ela mas doi. O projecto ja tem, espalhado por
varios ficheiros, a disciplina de distinguir "nao medido" de "medido e zero" — o
`tests_placeholder_zero.py`, o `test_clima_sem_invencao.py`, o
`erro_efetivo_medido` de outra sessao. Aqui o risco e' concreto e historico:

    uma previsao de 65 sc/ha que deu 65 sc/ha  ->  erro 0%    (medido)
    uma previsao que ninguem registou         ->  erro ???   (sem dado)

`0` e `None` nao se confundem em Python, mas confundem-se num JSON, num
serializador, e numa tela. `erro_percentual` devolve `None`, e `fonte_dado_erro`
diz qual dos dois e'.
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth.models import User

from app.models import Cultura, PrescricaoVRA, Propriedade, Safra, Talhao

# ------------------------------------------------------------------ fixtures


@pytest.fixture
def user(db):
    return User.objects.create_user("produtor", password="x")


@pytest.fixture
def propriedade(user):
    # `area_total` e' NOT NULL no schema. MEDIDO: o default do model nao chega
    # porque o `migrate` de teste cria a coluna sem default — e um teste que
    # inventa um default diferente do schema passa em dev e falha em prod.
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


def prescribe(safra, talhao, cultura, **extra) -> PrescricaoVRA:
    return PrescricaoVRA.objects.create(
        safra=safra,
        talhao=talhao,
        cultura=cultura,
        tipo_insumo="FERTILIZANTE",
        dose_ha=120,
        unidade="kg/ha",
        **extra,
    )


# ------------------------------------------------- o elo com o desfecho existe


class TestEloComDesfecho:
    """`PrescricaoVRA.safra` -> `Safra.produtividade`. O elo ja existia."""

    def test_realizada_vem_da_safra(self, safra, talhao, cultura):
        safra.produtividade = 65
        safra.save(update_fields=["produtividade"])
        p = prescribe(safra, talhao, cultura, produtividade_esperada=70)

        assert float(p.produtividade_realizada) == 65.0

    def test_safra_sem_produtividade_da_none_e_nao_zero(self, safra, talhao, cultura):
        """Safra registada mas nao colhida. `None`, nunca 0."""
        p = prescribe(safra, talhao, cultura, produtividade_esperada=70)

        assert p.produtividade_realizada is None
        assert p.erro_percentual is None
        assert p.desfecho_medido is False
        assert p.fonte_dado_erro == "sem_dado"


# --------------------------------------------------------------- o erro medido


class TestErroMedido:
    def test_erro_percentual_aritmetica(self, safra, talhao, cultura):
        """Previu 70, colheu 65 -> a previsao foi 7.69% otimista."""
        safra.produtividade = 65
        safra.save(update_fields=["produtividade"])
        p = prescribe(safra, talhao, cultura, produtividade_esperada=70)

        assert p.erro_percentual == pytest.approx(7.69, abs=0.01)
        assert p.desfecho_medido is True
        assert p.fonte_dado_erro == "medido"

    def test_erro_negativo_quando_a_previsao_foi_pessimista(
        self, safra, talhao, cultura
    ):
        """Previu 60, colheu 70 -> a previsao foi demasiado baixa."""
        safra.produtividade = 70
        safra.save(update_fields=["produtividade"])
        p = prescribe(safra, talhao, cultura, produtividade_esperada=60)

        assert p.erro_percentual == pytest.approx(-14.29, abs=0.01)

    def test_erro_zero_e_uma_coisa_diferente_de_sem_dado(self, safra, talhao, cultura):
        """O teste que dá o nome a esta classe.

        Acertou em cheio: erro 0.0, `medido`.
        Ninguem registou previsao: erro None, `sem_dado`.

        Sao valores diferentes **e de tipos diferentes**. Se este teste falhar,
        alguem trocou `None` por `0` para "simplificar" — e foi exactamente o que
        o `experiment.js` fazia com o clima, devolvendo 25 graus constantes.
        """
        safra.produtividade = 65
        safra.save(update_fields=["produtividade"])

        acertou = prescribe(safra, talhao, cultura, produtividade_esperada=65)
        sem_previsao = prescribe(safra, talhao, cultura)

        assert acertou.erro_percentual == 0.0
        assert acertou.fonte_dado_erro == "medido"

        assert sem_previsao.erro_percentual is None
        assert sem_previsao.fonte_dado_erro == "sem_dado"

        assert acertou.erro_percentual != sem_previsao.erro_percentual

    def test_realizada_zero_da_erro_indefinivel_e_nao_infinito(
        self, safra, talhao, cultura
    ):
        """Erro relativo a zero nao tem resposta. `inf` e `0` seriam inventar.

        Mas o **desfecho continua medido**: produtividade 0 e' uma medicao real
        (a lavoura falhou, ou o registo e' mesmo zero). Por isso o terceiro
        estado, `medido_sem_erro` — que e' o mesmo vocabulario de
        `medido_com_ressalva` que o `experiment.js` passou a usar.

        Este teste encontrou um bug real: `fonte_dado_erro` devolvia "medido"
        (porque as duas pontas existiam) enquanto `erro_percentual` devolvia
        `None`. As duas propriedades discordavam entre si.
        """
        safra.produtividade = 0
        safra.save(update_fields=["produtividade"])
        p = prescribe(safra, talhao, cultura, produtividade_esperada=70)

        assert p.erro_percentual is None
        assert p.desfecho_medido is True
        assert p.fonte_dado_erro == "medido_sem_erro"

    def test_fonte_dado_erro_concorda_sempre_com_erro_percentual(
        self, safra, talhao, cultura
    ):
        """A invariante: nunca ha `erro_percentual is None` com fonte `medido`.

        Se aparecer um quarto estado mal desenhado, esta falha. E' o teste que
        impede que as duas propriedades voltem a discordar.
        """
        for realizada, esperada in [
            (None, 70),  # sem colheita
            (65, None),  # sem previsao
            (65, 70),  # o caso normal
            (65, 65),  # acertou em cheio
            (0, 70),  # colheita zero
            (None, None),  # nada
        ]:
            safra.produtividade = realizada
            safra.save(update_fields=["produtividade"])
            p = prescribe(safra, talhao, cultura, produtividade_esperada=esperada)

            fonte = p.fonte_dado_erro
            if p.erro_percentual is None:
                assert fonte in {"sem_dado", "medido_sem_erro"}, (
                    f"realizada={realizada} esperada={esperada}: erro None mas "
                    f"fonte={fonte} — as duas discordam"
                )
            else:
                assert fonte == "medido", (
                    f"realizada={realizada} esperada={esperada}: erro "
                    f"{p.erro_percentual} mas fonte={fonte}"
                )

    def test_erro_muda_quando_a_safra_e_actualizada(self, safra, talhao, cultura):
        """`erro_percentual` e' uma property: tem de reflectir o estado actual.

        Se alguma vez for guardado como campo, esta e' a prova de que foi
        gravado no sitio errado — passaria a mentir depois da colheita.
        """
        p = prescribe(safra, talhao, cultura, produtividade_esperada=70)
        assert p.erro_percentual is None

        safra.produtividade = 35
        safra.save(update_fields=["produtividade"])

        assert p.erro_percentual == pytest.approx(100.0, abs=0.01)


# ------------------------------------------------------------- a procedencia


class TestProcedencia:
    def test_o_pacote_tem_o_que_um_comprador_pergunta(self, safra, talhao, cultura):
        safra.produtividade = 65
        safra.save(update_fields=["produtividade"])
        p = prescribe(
            safra,
            talhao,
            cultura,
            produtividade_esperada=70,
            versao_analise="solo-pt-2026.1",
            contexto_recomendacao={
                "fonte_dado": "medido",
                "clima": {"temp": {"valor": 24.0, "fonte_dado": "medido"}},
            },
        )

        prov = p.proveniencia

        assert prov["dose_ha"] == 120.0
        assert prov["produtividade_esperada"] == 70.0
        assert prov["produtividade_realizada"] == 65.0
        assert prov["erro_percentual"] == pytest.approx(7.69, abs=0.01)
        assert prov["fonte_dado_erro"] == "medido"
        assert prov["versao_analise"] == "solo-pt-2026.1"
        assert prov["contexto_recomendacao"]["fonte_dado"] == "medido"
        assert prov["talhao_id"] == talhao.pk
        assert prov["criado_em"] is not None

    def test_ausentes_viram_none_e_nao_zero_nem_string_vazia(
        self, talhao, cultura, safra
    ):
        """`versao_analise` e' `CharField(blank=True)`: vazio no Python, `None` no JSON.

        E' a mesma razao do `erro_percentual`: um `"--"` ou um `""` na frente de
        um comprador le-se como "foi medido e deu zero", e nao como "nao foi
        medido".
        """
        p = prescribe(safra, talhao, cultura)

        assert p.proveniencia["versao_analise"] is None
        assert p.proveniencia["contexto_recomendacao"] == {}
        assert p.proveniencia["produtividade_esperada"] is None
        assert p.proveniencia["produtividade_realizada"] is None
        assert p.proveniencia["fonte_dado_erro"] == "sem_dado"

    def test_prescricao_sem_previsao_continua_valida(self, talhao, cultura, safra):
        """O produtor nao e' obrigado a adivinhar o futuro para poder semear.

        Se tornar a previsao obrigatoria, obriga a inventar um numero — e voltamos
        ao `experiment.js`.
        """
        p = prescribe(safra, talhao, cultura)
        assert p.pk is not None
        assert p.versao_analise == ""
        assert p.contexto_recomendacao == {}

    def test_o_contexto_guarda_o_carimbo_de_fonte(self, talhao, cultura, safra):
        """A evidencia tem de travelling com o seu proprio `fonte_dado`.

        Nao basta guardar `{"temp": 24}`: sem o carimbo, um sensor `suspect`
        e um `good` ficam indistinguiveis, e e' o `suspect` que nao pode
        sustentar uma decisao.
        """
        p = prescribe(
            safra,
            talhao,
            cultura,
            contexto_recomendacao={
                "fonte_dado": "medido_com_ressalva",
                "clima": {
                    "temp": {"valor": 24.0, "fonte_dado": "medido"},
                    "ph": {"valor": 6.8, "fonte_dado": "suspect"},
                },
                "solo": {"ph": {"fonte_dado": "sem_dado"}},
            },
        )
        ctx = p.contexto_recomendacao

        assert ctx["fonte_dado"] == "medido_com_ressalva"
        assert ctx["clima"]["temp"]["fonte_dado"] == "medido"
        assert ctx["clima"]["ph"]["fonte_dado"] == "suspect"
        assert ctx["solo"]["ph"]["fonte_dado"] == "sem_dado"

        # E o round-trip nao perde nada.
        p.refresh_from_db()
        assert p.contexto_recomendacao == ctx


# ------------------------------------------------------------------ o indice


class TestConsultaDeA2:
    def test_indice_safra_talhao_existe(self):
        """A consulta do A2 e' 'as prescricoes desta safra ja avaliadas'.

        Sem indice, varrer a tabela toda assim que a base cresce e' o que faz
        um painel lento.
        """
        nomes = {i.name for i in PrescricaoVRA._meta.indexes}
        assert "app_prescri_safra_i_2d6bb9_idx" in nomes
        campos = next(
            i
            for i in PrescricaoVRA._meta.indexes
            if i.name == "app_prescri_safra_i_2d6bb9_idx"
        )
        assert list(campos.fields) == ["safra", "talhao"]


# ------------------------------------------------------------- chega ao cliente


class TestProvenienciaNaAPI:
    """De nada serve uma property que ninguem consegue ler.

    O A2 so tem valor quando o produtor, o comprador ou a cooperativa conseguem
    pedir "esta recomendacao foi avaliada?" e receber a resposta.
    """

    def test_endpoint_devolve_o_erro_e_a_sua_fonte(
        self, client, user, safra, talhao, cultura
    ):
        client.force_login(user)
        safra.produtividade = 65
        safra.save(update_fields=["produtividade"])
        p = prescribe(
            safra,
            talhao,
            cultura,
            produtividade_esperada=70,
            versao_analise="solo-pt-2026.1",
            contexto_recomendacao={"fonte_dado": "medido", "clima": {}},
        )

        r = client.get("/api/prescricoes-vra/")
        assert r.status_code == 200, r.content[:400]

        item = next(x for x in r.json()["results"] if x["id"] == p.pk)
        assert float(item["produtividade_realizada"]) == 65.0
        assert float(item["produtividade_esperada"]) == 70.0
        assert item["erro_percentual"] == pytest.approx(7.69, abs=0.01)
        assert item["fonte_dado_erro"] == "medido"
        assert item["versao_analise"] == "solo-pt-2026.1"

    def test_null_sobrevive_como_null_no_json(
        self, client, user, safra, talhao, cultura
    ):
        """`null`, nunca `0`.

        E' aqui que a dishonesty fica visivel: um serializador que transforma
        `None` em `0` entrega ao cliente "o erro foi zero", e o cliente desenha
        um "0%" que significa "acertou em cheio". O `fonte_dado_erro` ao lado e'
        o que salva o cliente de cair nessa.
        """
        client.force_login(user)
        p = prescribe(safra, talhao, cultura)

        r = client.get("/api/prescricoes-vra/")
        assert r.status_code == 200

        item = next(x for x in r.json()["results"] if x["id"] == p.pk)
        assert item["erro_percentual"] is None
        assert item["produtividade_realizada"] is None
        assert item["produtividade_esperada"] is None
        assert item["fonte_dado_erro"] == "sem_dado"

        corpo = r.content.decode()
        # Sem depender do espacamento: o DRF serializa compacto, e um teste que
        # assume `": null"` falha quando alguem liga o `indent`.
        assert re.search(r'"erro_percentual"\s*:\s*null', corpo), corpo[:300]
        assert re.search(r'"produtividade_realizada"\s*:\s*null', corpo)
        # E, critically, nao pode ter virado 0 em lado nenhum destes tres.
        assert re.search(r'"erro_percentual"\s*:\s*0', corpo) is None

    def test_outro_produtor_nao_ve_a_prescricao(
        self, client, user, safra, talhao, cultura
    ):
        """A procedencia nao pode ser o vector que fura o multi-tenant.

        O A2 junta dados de dois lados (a prescricao e a produtividade da safra).
        Um endpoint que devolvesse a produtividade sem filtrar a prescricao
        entregava a um produtor o resultado da lavoura do vizinho.
        """
        client.force_login(user)
        prescribe(safra, talhao, cultura, produtividade_esperada=70)

        r = client.get("/api/prescricoes-vra/")
        assert len(r.json()["results"]) == 1

        vizinho = User.objects.create_user("vizinho", password="x")
        client.force_login(vizinho)
        r2 = client.get("/api/prescricoes-vra/")
        assert r2.status_code == 200
        assert r2.json()["results"] == []
