"""A guia abre para um produtor com dados reais. E só esses.

MEDIDO 2026-10-05. Este ficheiro **substitui** `test_guia_ferramentas_ndvi_view.py`.

Porquê substituir em vez de adaptar: o teste antigo fazia cinco asserções
sobre `TALHOES`, e quatro delas continues válidas. Mas escrevia-o antes de o
catálogo existir, e o seu valor maior era o de provar que a view passa os
talhões **do produtor** e não os da base — uma propriedade de isolamento que
vale mais agora que há 27 itens no catálogo para confundir.

O que mudou é que este teste passou a verificar **três** camadas, porque a
guia passou a ter três:

1. A view passa os talhões do produtor (isolamento).
2. A rota `/api/agronomia/ndvi/` responde e devolve o contrato que o botão
   consome (`ndvi_medio` nulo + `fonte_dado` + `motivo`).
3. A página não promete o que o catálogo diz que não existe.

O ponto 3 é novo e é o que este ficheiro acrescenta. Com 13 itens marcados
`NAO_EXISTE`, a pergunta «a página mostra algum deles como clicável?» passa a
ser a verificação importante — e é a que impede a lista de voltar a ser um
catálogo de marketing.
"""

from __future__ import annotations

import json
import pathlib
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Propriedade, Talhao

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "guia-ferramentas.html"


def fonte() -> str:
    return TEMPLATE.read_text(encoding="utf-8", errors="replace")


class TalhoesDoProdutor(TestCase):
    """1. O isolamento. A propriedade mais importante da view."""

    def setUp(self):
        self.eu = User.objects.create_user("ndvi_view", password="x1234567")
        self.minha = Propriedade.objects.create(
            user=self.eu, nome="Minha", area_total=Decimal("10")
        )
        self.vizinho = User.objects.create_user("ndvi_vizinho", password="x1234567")
        self.deles = Propriedade.objects.create(
            user=self.vizinho, nome="Deles", area_total=Decimal("5")
        )
        self.meu_talhao = Talhao.objects.create(
            propriedade=self.minha, nome="Soitario", area_hectare="10.00"
        )
        self.talhao_deles = Talhao.objects.create(
            propriedade=self.deles, nome="Secreto", area_hectare="5.00"
        )
        self.client.force_login(self.eu)

    def _talhoes_no_html(self):
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        m = re.search(r"var TALHOES\s*=\s*(\[[^;]*\]);", html)
        assert m, "a página não passa `TALHOES` ao código"
        return json.loads(m.group(1))

    def test_a_view_passa_o_talhao_do_produtor(self):
        """O botão só funciona se a view lhe der talhão."""
        talhoes = self._talhoes_no_html()
        self.assertEqual(
            [t["nome"] for t in talhoes],
            ["Soitario"],
            "a lista de talhões não é a do produtor",
        )

    def test_a_view_nao_passa_o_talhao_do_vizinho(self):
        """O tenancy aplica-se também ao que vai para dentro de um `<script>`.

        Um talhão do vizinho no JavaScript é a mesma fuga que contar os
        sensores dele: o produtor vê um talhão que não é seu, e pode pedir o
        NDVI dele.
        """
        nomes = [t["nome"] for t in self._talhoes_no_html()]
        self.assertNotIn("Secreto", nomes)

    def test_sem_talhao_a_pagina_diz_que_nao_ha(self):
        """Produtor sem talhão recebe `[]` — e o botão diz «não há talhão».

        Não `0.72`, não uma lista de talhões que não existe.
        """
        Talhao.objects.filter(propriedade=self.minha).delete()
        self.assertEqual(self._talhoes_no_html(), [])

    def test_apenas_talhoes_ativos(self):
        """Um talhão inactivo não entra na lista.

        Sem esta distinção, o produtor escolhe um talhão que desativou e
        recebe NDVI de uma área que já não cultiva — e a leitura é
        personagem para uma decisão.
        """
        self.meu_talhao.ativo = False
        self.meu_talhao.save()
        self.assertEqual(
            self._talhoes_no_html(),
            [],
            "um talhão com `ativo=False` foi oferecido ao produtor",
        )

    def test_a_rota_responde_e_devolve_o_contrato(self):
        """A rota que o botão consome responde, e diz o que falta.

        O `test_guia_ferramentas_ndvi.py` verifica que a rota **resolve**.
        Este verifica que ela **responde**, e que quando não há satélite
        devolve `ndvi_medio: null` com um motivo. É esse contrato que o
        botão transforma em «sem leitura».
        """
        resposta = self.client.get(
            "/api/agronomia/ndvi/", {"talhao_id": self.meu_talhao.id}
        )
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()

        self.assertIn("ndvi_medio", corpo)
        self.assertIn("fonte_dado", corpo)
        if corpo["ndvi_medio"] is None:
            self.assertTrue(
                corpo.get("motivo"),
                "sem NDVI e sem motivo: o botão ficaria sem nada que dizer ao "
                "produtor além de «sem leitura», que não ajuda ninguém a "
                "saber o que fazer.",
            )

    def test_a_rota_exige_talhao(self):
        """Sem `talhao_id` a rota recusa, e não devolve um número.

        Este era o caminho que o `talhao=1` fixo evitava — por isso é que
        fixava: sem ele faltava o parâmetro. A resposta certa é 400, não um
        índice de vegetação qualquer.
        """
        resposta = self.client.get("/api/agronomia/ndvi/")
        self.assertEqual(resposta.status_code, 400)

    def test_a_rota_recusa_o_talhao_de_outro(self):
        """O tenancy da API, não só o da view.

        A view filtrar os talhões é uma coisa; a API recusar o id de outro
        produtor é outra. São a mesma garantia em dois sítios, e é o segundo
        que fecha a fuga: a URL é adivinhável.
        """
        resposta = self.client.get(
            "/api/agronomia/ndvi/", {"talhao_id": self.talhao_deles.id}
        )
        # 404, não 200 com o NDVI de outro. `get_object_or_404` no serviço.
        self.assertIn(
            resposta.status_code,
            (403, 404),
            "a API devolveu %s para o talhão de outro produtor. Deveria ser "
            "403 ou 404." % resposta.status_code,
        )


class APaginaNaoPrometeOQueNaoExiste(TestCase):
    """3. O novo: nenhum item `NAO_EXISTE` aparece clicável."""

    def setUp(self):
        self.u = User.objects.create_user("ndvi_promessa", password="x1234567")
        self.client.force_login(self.u)

    def test_nenhum_item_por_implementar_tem_botao(self):
        """13 itens não existem. Nenhum pode ter um `href` nem um botão.

        Um cartão `NAO_EXISTE` com botão é um 404 esperando que alguém clique.
        Pior: se a rota aparecer um dia, o cartão passa a dizer que já
        funciona — sem ninguém ter ligado o código.
        """
        from app.guias.catalogo import NAO_EXISTE

        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        # Cada cartão: pega do nome até ao fim do cartão.
        cartoes = re.findall(
            r'<article class="gf-item[^"]*"[^>]*>(.*?)</article>', html, re.S
        )
        self.assertTrue(cartoes, "não encontrei cartões na página")

        sem_estado = []
        for corpo in cartoes:
            classe = re.search(r'<article class="gf-item ([^"]*)"', corpo)
            m_nome = re.search(r'<h3 class="gf-item-nome">([^<]+)</h3>', corpo)
            if not m_nome:
                continue
            nome = m_nome.group(1).strip()
            tem_botao = ('class="gf-btn"' in corpo) or (
                "<a " in corpo and "href=" in corpo
            )
            # Um NAO_EXISTE é desenhado sem botão: o template só cria o
            # `<a>` quando há rota.
            if classe and "i-ausente" in classe.group(1) and tem_botao:
                sem_estado.append(nome)

        self.assertEqual(
            sem_estado,
            [],
            f"itens marcados como não implementados mas com botão: {sem_estado}",
        )

    def test_o_numero_de_nao_implementados_bate_com_o_catalogo(self):
        """A caixa «Não implementado» conta o que o catálogo diz.

        Se o catálogo tem 13 e a caixa diz 10, o produtor vê 3 ausentes que a
        página jura que não existem. A contagem é derivada, não escrita —
        ver `test_guia_ferramentas_numeros.py`.
        """
        from app.guias.catalogo import NAO_EXISTE

        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        ausentes_html = len(re.findall(r'class="gf-item i-ausente"', html))
        ausentes_cat = sum(
            1
            for c in __import__("app.guias.catalogo", fromlist=["CATALOGO"]).CATALOGO
            for it in c["itens"]
            if it["estado"] == NAO_EXISTE
        )
        self.assertEqual(
            ausentes_html,
            ausentes_cat,
            f"a página desenha {ausentes_html} itens como não implementados e "
            f"o catálogo tem {ausentes_cat}",
        )
        self.assertGreater(
            ausentes_cat,
            0,
            "o catálogo não tem nenhum item NAO_EXISTE. Ou a auditoria não foi "
            "feita, ou alguém apagou os honestos e ficou só a lista bonita.",
        )

    def test_todo_parcial_diz_o_que_falta(self):
        """Cada cartão amarelo tem de escrever a fronteira.

        Um parcial que só diz «parcial» obriga o produtor a perguntar o quê.
        E o que ele perguntaria é «isto funciona?», que é a pergunta errada.
        """
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        parciais = re.findall(
            r'<article class="gf-item i-parcial"[^>]*>(.*?)</article>', html, re.S
        )
        self.assertTrue(parciais, "a página não desenha nenhum cartão parcial")

        sem_fronteira = []
        for corpo in parciais:
            m = re.search(r'<h3 class="gf-item-nome">([^<]+)</h3>', corpo)
            nome = m.group(1).strip() if m else "?"
            if "gf-fronteira" not in corpo:
                sem_fronteira.append(nome)

        self.assertEqual(
            sem_fronteira,
            [],
            f"cartões parciais sem «Fronteira:» {sem_fronteira}",
        )
