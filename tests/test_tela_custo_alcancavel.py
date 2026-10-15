"""O produtor tem de conseguir CHEGAR a tela.

MEDIDO 2026-10-05. Construi `/custos/orcado-realizado/`, liguei o endpoint,
escrevi 38 testes - e a tela nao estava ligada a lado nenhum. `grep` nao
devolveu nenhuma referencia nos templates, so a propria tela a apontar para
`custos-producao`. O produtor tinha uma feature completa e invisivel.

E' a mesma classe de bug de um motor sem porta, um caso acima: coisa feita e
inalcancavel. O servico existia sem endpoint; o endpoint existia sem ecra; a
ecra existia sem ligacao. Tres camadas de "feito" que nao chegam a ninguem.

Estes testes existem porque a proxima vez o sintoma vai ser o mesmo e a causa
nao vai ser obvia: nao ha erro, nao ha 404, a pagina simplesmente nao esta no
caminho.
"""

import re
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import PerfilUsuario, Propriedade

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]


class ALigacaoNoMenu(TestCase):
    """A tela tem de estar a partir de onde o produtor ja' esta."""

    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@x.com", "s12345678")
        PerfilUsuario.objects.filter(user=self.user).update(
            tipo_usuario="produtor", area_servidor="AGRONOMIA"
        )
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda", cep="37400000", area_total=D("30")
        )
        self.client.force_login(self.user)

    def _templates(self):
        return list((RAIZ / "app" / "templates").glob("*.html"))

    def test_a_tela_e_alcancavel_de_outra_pagina_de_custo(self):
        """Custos, Centros de custo e DRE sao a familia onde o produtor
        procura isto. Se a tela nao sai de la, ele nao a encontra."""
        alvos = ["custos-producao.html", "centros-custo.html", "dre.html"]
        for nome in alvos:
            caminho = RAIZ / "app" / "templates" / nome
            self.assertTrue(caminho.exists(), f"{nome} nao existe")
            texto = caminho.read_text(encoding="utf-8")
            self.assertIn(
                "orcamento-realizado",
                texto,
                f"{nome} nao tem ligacao para a tela do orcado x realizado. "
                "A feature esta feita e inacessivel.",
            )

    def test_a_ligacao_aponta_para_a_url_certa(self):
        """Um `href` para um nome de url inexistente rebenta a pagina toda,
        e o sintoma e' um 500 numa tela que estava a funcionar - o produtor
        nao sabe que o erro foi um link novo."""
        from django.template import Context, Template

        for nome in ("centros-custo.html", "dre.html"):
            caminho = RAIZ / "app" / "templates" / nome
            texto = caminho.read_text(encoding="utf-8")
            for _m in re.finditer(r"\{%\s*url\s+'orcamento-realizado'\s*%\}", texto):
                renderizado = Template("{% url 'orcamento-realizado' %}").render(
                    Context({})
                )
                self.assertEqual(
                    renderizado,
                    reverse("orcamento-realizado"),
                    "o nome de url nao resolve para a rota registada",
                )

    def test_o_mercado_de_appbar_e_spa(self):
        """A tela nao usa `{% url %}` no body, so nos headers - e as rotas
        `/custos/...` podem nao estar na SPA. Se nao estiverem, o produtor
        que navega pela appbar leva a um 404."""
        r = self.client.get(reverse("orcamento-realizado"))
        self.assertEqual(r.status_code, 200)


class OQueOProdutorEncontra(TestCase):
    """A tela responde com dados, nao so com 200."""

    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@x.com", "s12345678")
        PerfilUsuario.objects.filter(user=self.user).update(
            tipo_usuario="produtor", area_servidor="AGRONOMIA"
        )
        Propriedade.objects.create(
            user=self.user, nome="Fazenda", cep="37400000", area_total=D("30")
        )
        self.client.force_login(self.user)

    def test_o_ciclo_completo_responde(self):
        """Tela -> API -> tabela. Se a API mudar de nome, a tela fica com
        'Nao foi possivel carregar' e o produtor ve uma fazenda vazia que
        nao esta vazia."""
        from app.models import LancamentoFinanceiro, Talhao

        prop = (
            self.prop
            if hasattr(self, "prop")
            else Propriedade.objects.filter(user=self.user).first()
        )
        t = Talhao.objects.create(
            propriedade=prop, nome="Baixada", area_hectare=D("10")
        )
        LancamentoFinanceiro.objects.create(
            propriedade=prop,
            tipo="DESPESA",
            categoria="insumo",
            valor=D("1000"),
            data="2026-03-10",
            talhao=t,
            pago=True,
        )

        tela = self.client.get(reverse("orcamento-realizado"))
        self.assertEqual(tela.status_code, 200)

        api = self.client.get(reverse("api_custo_por_talhao"))
        self.assertEqual(api.status_code, 200)
        d = api.json()
        self.assertTrue(d["tem_dados"])
        self.assertEqual(d["total_despesa"], 1000.0)

    def test_a_url_da_api_no_template_existe(self):
        """Ja coberto em `test_tela_orcamento_realizado.py`, mas aqui fica
        porque este e' o ficheiro que explica a ligacao."""
        caminho = RAIZ / "app" / "templates" / "orcamento-realizado.html"
        texto = caminho.read_text(encoding="utf-8")
        m = re.search(r"(/api/financeiro/[a-z\-/]+)", texto)
        self.assertIsNotNone(m)
        from django.urls import resolve

        resolve(m.group(1))
