"""A pergunta invertida: "estou aqui, o que posso plantar?" — em vez de "esta
cultura, quando?".

O QUE ESTE FICHEIRO PROVA
-------------------------
MEDIDO em 2026-10-03: a tabela `ZARC` tem **0 registos** e o catalogo tem **709
culturas**. O endpoint antigo (`consultar_zarc`) exige `cultura_id` + `uf` — para
perguntar *quando semear soja*, o produtor tinha de **ja ter escolhido soja**.

O primeiro minuto de um produtor era, portanto:
    abrir -> 709 culturas num selector -> nenhuma sabia onde ele esta
          -> nenhuma janela de plantio no sistema -> fechar

O `para_minha_regiao` inverte a pergunta. E, being the honest thing it has to
be, **nao inventa a resposta**.

A REGRA DESTE TESTE, e a do PRODUCTO
------------------------------------
Um producer so recebe uma janela de plantio se ela **existir na ZARC**. Nem um
dia gerado, nem uma media nacional, nem "tipicamente em setembro". Uma data de
plantio inventada aqui nao e' um bug: e' uma recomendacao de risco climatico
errada, e quem decide quando semear com base num numero falso perde dinheiro ou a
lavoura.

Por isso este ficheiro tem **três grupos de testes**:

  1. COM a ZARC vazia (o estado real de hoje)  -> `sem_dado`, e diz o que falta
  2. COM a ZARC semeada num municipio          -> a janela aparece, sem mudanca
                                                  de codigo
  3. O que nunca pode acontecer               -> uma data que nao veio da ZARC

O grupo 2 e' o importante: prova que o codigo do caminho feliz esta certo, sem
que isso obrigue a semear nada em producao. **Um caminho feliz so se prova com
dado real no teste; senao so se prova que o codigo faz o que nao foi testado.**
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from app.models import ZARC, Cultura


@pytest.fixture
def user(db):
    return User.objects.create_user("prod", password="x")


@pytest.fixture
def client_logado(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def soja():
    return Cultura.objects.create(nome="Soja", grupo="graos")


@pytest.fixture
def milho():
    return Cultura.objects.create(nome="Milho", grupo="graos")


# ============================================================ 1. o estado real


class TestZarcVazia:
    """O estado de hoje: 0 registos. E o que o produtor ve."""

    def test_sem_uf_e_erro_explicito(self, client_logado):
        r = client_logado.get("/api/zarc/para_minha_regiao/")
        assert r.status_code == 400
        assert r.json()["fonte_dado"] == "sem_dado"

    def test_uf_incompleta_e_erro(self, client_logado):
        r = client_logado.get("/api/zarc/para_minha_regiao/?uf=R")
        assert r.status_code == 400

    def test_regiao_sem_dado_diz_sem_dado(self, client_logado, soja):
        """**0 janelas, e nao uma janela inventada.**"""
        r = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Passo Fundo"
        )
        assert r.status_code == 200
        j = r.json()

        assert j["total_janelas"] == 0
        assert j["janelas"] == []
        assert j["fonte_dado"] == "sem_dado"

    def test_o_aviso_diz_o_que_falta_e_onde_vem(self, client_logado):
        """Um `sem_dado` sem caminho e' um beco — e no onboarding e' onde o
        produtor desiste.

        A resposta tem de dizer o que falta **e** de onde vem, para que
        acrescentar o dado seja um acto e nao uma investigacao.
        """
        r = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Passo Fundo"
        )
        aviso = r.json()["aviso"]

        assert aviso, "sem dado, tem de haver aviso"
        baixo = aviso.lower()
        assert "0 registos" in baixo, aviso
        assert "zarc" in baixo, aviso
        assert "embrapa" in baixo, aviso

    def test_o_catalogo_vem_na_mesma_resposta(self, client_logado, soja, milho):
        """O produtor tem 709 culturas **mesmo sem janela regional**.

        Dizer `sem_dado` a lista inteira seria esconder o que ele ja tem. O que
        nao se sabe e' a janela, nao o catalogo — e a resposta separa os dois.
        """
        r = client_logado.get("/api/zarc/para_minha_regiao/?uf=RS")
        cat = r.json()["catalogo"]

        assert cat["fonte_dado"] == "medido"
        assert cat["total_culturas"] >= 2
        grupos = {g["grupo"] for g in cat["grupos"]}
        assert "graos" in grupos, grupos

    def test_o_catalogo_vem_agrupado_nao_em_709_linhas(self, client_logado, soja):
        """709 opcoes num selector e' o problema. Grupos sao a resposta."""
        r = client_logado.get("/api/zarc/para_minha_regiao/?uf=RS")
        grupos = r.json()["catalogo"]["grupos"]

        assert grupos, "tem de vir agrupado"
        assert all("grupo" in g and "culturas" in g for g in grupos)
        assert all(g["culturas"] >= 1 for g in grupos)


# ==================================================== 2. o caminho feliz, provado


class TestComZarcSemeada:
    """O codigo do caminho feliz, provado com dado real — mas so no teste.

    MEDIDO: 0 registos em producao. Este teste **nao** semeia nada em producao;
    cria registos dentro do teste, prova o caminho, e o django apaga no fim. E'
    assim que se prova um caminho sem inventar dado: o registo e' real, o local
    e' descartavel.
    """

    def _semeia(self, cultura, uf="RS", municipio="Passo Fundo"):
        hoje = timezone.localdate()
        return ZARC.objects.create(
            cultura=cultura,
            uf=uf,
            municipio=municipio,
            data_inicio_plantio=hoje - timedelta(days=10),
            data_fim_plantio=hoje + timedelta(days=20),
            ciclo_dias=140,
            risco_climatico=0.2,
        )

    def test_a_janela_aparece_sem_mudar_uma_linha_de_codigo(self, client_logado, soja):
        """O mesmo endpoint que devolve `sem_dado` com a tabela vazia devolve a
        janela com ela semeada. **E o teste que prova que o A1 do item 2
        (Semear a ZARC) nao exige codigo.**
        """
        self._semeia(soja)

        r = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Passo Fundo"
        )
        j = r.json()

        assert j["total_janelas"] == 1
        # `declarado`, nao `medido`: a ZARC e' a declaracao da Embrapa sobre a
        # regiao. Nenhum sensor desta propriedade mediu a janela de plantio, e
        # o produtor usa esta data para decidir quando semear.
        assert j["fonte_dado"] == "declarado"
        assert j["aviso"] is None

        janela = j["janelas"][0]
        assert janela["cultura_nome"] == "Soja"
        assert janela["janela_aberta"] is True
        assert janela["fonte_dado"] == "declarado"
        assert janela["fonte"] == "Embrapa — ZARC"

    def test_dias_para_fechar(self, client_logado, soja):
        self._semeia(soja)  # fecha dentro de 20 dias
        j = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Passo Fundo"
        ).json()
        assert j["janelas"][0]["dias_para_fechar"] == 20

    def test_janela_fechada_dias_e_none_e_nao_zero(self, client_logado, soja):
        """`0 dias` parece uma contagem e nao e'. `None` e' ausencia — e a
        mesma disciplina do `erro_percentual` do A2."""
        hoje = timezone.localdate()
        ZARC.objects.create(
            cultura=soja,
            uf="RS",
            municipio="Passo Fundo",
            data_inicio_plantio=hoje - timedelta(days=200),
            data_fim_plantio=hoje - timedelta(days=30),
            ciclo_dias=140,
            risco_climatico=0.2,
        )
        j = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Passo Fundo"
        ).json()
        janela = j["janelas"][0]

        assert janela["janela_aberta"] is False
        assert janela["dias_para_fechar"] is None

    def test_outro_municipio_nao_ve_a_janela(self, client_logado, soja):
        self._semeia(soja, municipio="Passo Fundo")
        j = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Caxias do Sul"
        ).json()
        assert j["total_janelas"] == 0
        assert j["fonte_dado"] == "sem_dado"

    def test_outra_uf_nao_ve_a_janela(self, client_logado, soja):
        self._semeia(soja, uf="RS")
        j = client_logado.get("/api/zarc/para_minha_regiao/?uf=MT").json()
        assert j["total_janelas"] == 0

    def test_so_a_uf_ja_devolve(self, client_logado, soja):
        """O produtor nem sempre sabe o municipio em que vive. A UF e' o piso."""
        self._semeia(soja)
        j = client_logado.get("/api/zarc/para_minha_regiao/?uf=RS").json()
        assert j["total_janelas"] == 1


# ================================== 3. o que nunca pode acontecer


class TestNuncaInventaData:
    """As garantias. Se alguma destas falhar, o produto passou a mentir."""

    def test_nenhuma_data_que_nao_venha_da_zarc(self, client_logado, soja, milho):
        """Com a tabela vazia, **nenhuma** data no payload.

        Este teste varre o JSON inteiro a procura de algo que pareca uma data de
        plantio. E' o inverso do teste que verifica um valor: aqui verifica-se
        a **ausencia** dele, que e' o que nao se ve num `assertEqual` normal.
        """
        r = client_logado.get(
            "/api/zarc/para_minha_regiao/?uf=RS&municipio=Passo Fundo"
        )
        corpo = r.content.decode()
        j = r.json()

        for _chave in ("janela_inicio", "janela_fim"):
            assert j["janelas"] == [], "nao pode haver janelas sem ZARC"

        # Nenhum ISO date pode aparecer. `consultado_em` e' a data de hoje e nao
        # e' janela de plantio — por isso se exclui, com razao.
        import re

        sem_consultado = corpo.replace(f'"{j["consultado_em"]}"', "")
        assert not re.search(r"\d{4}-\d{2}-\d{2}", sem_consultado), sem_consultado[:300]

    def test_a_semear_e_o_mesmo_endpoint(self, client_logado, soja):
        """A garantia pratica: semear a ZARC **nao muda codigo**.

        O mesmo endpoint, o mesmo payload, so com o dado. E' isto que torna o
        item 2 da ordem um trabalho de dados e nao de engenharia.
        """
        vazio = client_logado.get("/api/zarc/para_minha_regiao/?uf=RS").json()
        ZARC.objects.create(
            cultura=soja,
            uf="RS",
            municipio="Passo Fundo",
            data_inicio_plantio=timezone.localdate(),
            data_fim_plantio=timezone.localdate() + timedelta(days=10),
            ciclo_dias=140,
            risco_climatico=0.2,
        )
        semeado = client_logado.get("/api/zarc/para_minha_regiao/?uf=RS").json()

        assert vazio["total_janelas"] == 0
        assert semeado["total_janelas"] == 1
        # O catalogo nao mudou — semear a ZARC nao mexe no que ja existia.
        assert (
            vazio["catalogo"]["total_culturas"] == semeado["catalogo"]["total_culturas"]
        )


# ================================================== 4. multi-tenancy


class TestTenancy:
    def test_exige_autenticacao(self, client):
        r = client.get("/api/zarc/para_minha_regiao/?uf=RS")
        assert r.status_code in (401, 403)
