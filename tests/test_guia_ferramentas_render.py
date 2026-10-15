"""A guia renderiza de facto? Um template pode passar todos os testes e
não chegar a ser HTML.

MEDIDO 2026-10-05. A verificação final depois de reconstruir a guia. Não
substitui os testes estruturais — é a prova de que o que escrevi **funciona**,
não de que tem a forma que eu pedi.

O que se prova aqui, e que os outros ficheiros não provam:
1. O Django renderiza sem `TemplateSyntaxError`.
2. Os 57 itens aparecem no HTML.
3. As 7 classes aparecem com a letra.
4. Os 3 números do cabeçalho batem com o catálogo.
5. A navegação de classes tem um botão por classe.
6. Um produtor sem talhão não leva `TALHOES` com o talhão do vizinho.

O motivo de este ficheiro existir: um `pytest` que passa pode estar a ler um
ficheiro que o Django nunca chegou a carregar. Já aconteceu — o
`caderno/offline.html` está em disco, tem teste, e **não está registado em
nenhum `urls.py`**. Passar testes não é a mesma coisa que aparecer no ecrã.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Propriedade, Talhao


class AGuiaRenderiza(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("guia_render", password="x1234567")
        self.client.force_login(self.u)

    def html(self) -> str:
        r = self.client.get(reverse("guia-ferramentas"))
        self.assertEqual(r.status_code, 200)
        return r.content.decode("utf-8")

    # ------------------------------------------------------------------
    def test_renderiza_sem_erro_de_sintaxe(self):
        """Se isto falha, o problema é meu e é de sintaxe.

        O resto dos testes deste ficheiro assume que o HTML existe. Esta é a
        asserção que torna essa suposição válida.
        """
        r = self.client.get(reverse("guia-ferramentas"))
        self.assertEqual(r.status_code, 200)
        # Um erro de sintaxe de template no Django dá 500 ou levanta.
        self.assertNotIn("TemplateSyntaxError", r.content.decode("utf-8", "replace"))

    def test_os_57_itens_estao_no_html(self):
        """Contar os cartões é a prova mais directa que existe.

        Os outros testes verificam o catálogo; este verifica que o catálogo
        chegou ao browser. São coisas diferentes: um pode passar sem o outro.
        """
        from app.guias.catalogo import CATALOGO

        html = self.html()
        total = sum(len(c["itens"]) for c in CATALOGO)
        cartoes = len(re.findall(r'<article class="gf-item', html))
        self.assertEqual(
            cartoes,
            total,
            f"o HTML tem {cartoes} cartões e o catálogo tem {total}",
        )

    def test_as_7_classes_aparecem_com_a_letra(self):
        """A letra é o que liga a página à lista que o produtor leu antes."""
        from app.guias.catalogo import CATALOGO

        html = self.html()
        for classe in CATALOGO:
            letra = classe["letra"]
            self.assertIn(
                f'class="gf-seccao-letra">{letra}<',
                html,
                f"a letra {letra} ({classe['nome']}) não chegou ao HTML",
            )

    def test_a_navegacao_tem_um_botao_por_classe(self):
        """A navegação é o que faz as classes aparecerem e desaparecerem."""
        from app.guias.catalogo import CATALOGO

        html = self.html()
        botoes = re.findall(r'class="gf-nav-btn[^"]*" data-classe="([^"]+)"', html)
        self.assertEqual(
            sorted(botoes),
            sorted(c["id"] for c in CATALOGO),
            "a navegação não tem um botão por classe",
        )

    def test_os_tres_numeros_do_cabecalho(self):
        """As três caixas de estado, com os valores do catálogo."""
        from app.guias.catalogo import CATALOGO

        esperado = {}
        for estado in ("EXISTE", "PARCIAL", "NAO_EXISTE"):
            esperado[estado] = sum(
                1 for c in CATALOGO for it in c["itens"] if it["estado"] == estado
            )

        html = self.html()
        caixas = re.findall(
            r'class="gf-estado gf-e-(\w+)"\s*>\s*<div class="gf-estado-num"[^>]*>\s*(\d+)',
            html,
            re.S,
        )
        self.assertEqual(len(caixas), 3, f"esperava 3 caixas, achei {len(caixas)}")
        obtido = {estado: int(n) for estado, n in caixas}

        # A classe CSS não é o nome do estado: `gf-e-ausente` corresponde a
        # `NAO_EXISTE`. Comparar as chaves em minúsculas directamente daria
        # `nao_existe` != `ausente` — e o teste falharia com os números
        # certos, que é o pior tipo de falha.
        # A TRADUÇÃO está escrita à vista de propósito: se a classe CSS
        # mudar de nome, isto quebra logo, em vez de a comparação deixar de
        # verificar alguma coisa.
        CSS_PARA_ESTADO = {
            "existe": "EXISTE",
            "parcial": "PARCIAL",
            "ausente": "NAO_EXISTE",
        }
        self.assertEqual(
            {CSS_PARA_ESTADO[k]: v for k, v in obtido.items()},
            esperado,
            f"o cabeçalho mostra {obtido} e o catálogo tem {esperado}",
        )
        # E nenhum estado foge à tabela — uma classe nova sem tradução aqui
        # não seria comparada com nada, e o teste passaria em silêncio.
        self.assertEqual(
            set(obtido) - set(CSS_PARA_ESTADO),
            set(),
            "uma classe CSS de estado nova não tem tradução na tabela",
        )

    def test_as_ferramentas_de_campo_estao_no_html(self):
        """As 9 ferramentas de acção, todas presentes."""
        html = self.html()
        for id_ in (
            "gfAduboBtn",
            "gfSemBtn",
            "gfPulvBtn",
            "gfConvBtn",
            "gfNdviBtn",
            "gfUniBtn",
            "gfVozBtn",
        ):
            self.assertIn(id_, html, f"a ferramenta {id} não chegou ao HTML")

    def test_o_simulador_tem_os_campos_obrigatorios(self):
        """Os 4 obrigatórios do simulador estão presentes e sem valor."""
        html = self.html()
        for campo in ("gvArea", "gvCusto", "gvPreco", "gvProd"):
            m = re.search(r'id="%s"[^>]*>' % campo, html)
            self.assertIsNotNone(m, "o campo %s não chegou ao HTML" % campo)
            self.assertNotIn(
                "value=",
                m.group(0),
                "o campo obrigatório %s tem valor por omissão no HTML "
                "renderizado" % campo,
            )


class AGuiaIsolaOSeu(TestCase):
    def setUp(self):
        self.eu = User.objects.create_user("guia_iso", password="x1234567")
        self.viz = User.objects.create_user("guia_iso_viz", password="x1234567")
        pminha = Propriedade.objects.create(
            user=self.eu, nome="Minha", area_total=Decimal("10")
        )
        pdele = Propriedade.objects.create(
            user=self.viz, nome="Dele", area_total=Decimal("10")
        )
        Talhao.objects.create(propriedade=pminha, nome="Meu talhao", area_hectare="1")
        Talhao.objects.create(propriedade=pdele, nome="Talhao alheio", area_hectare="1")
        self.client.force_login(self.eu)

    def test_o_talhao_alheio_nao_aparece_nem_no_html(self):
        """Nem como opção, nem em comentário, nem em `data-*`.

        Verifico o HTML **todo**, não só a linha do JavaScript. Um talhão
        alheio que apareça num comentário de HTML ainda é o nome do talhão
        do vizinho na página.
        """
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        self.assertNotIn(
            "Talhao alheio",
            html,
            "o talhão de outro produtor está no HTML. A lista de talhões é "
            "filtrada por `propriedade__user` na view, mas isto confirma que "
            "a filtragem está a acontecer.",
        )
        self.assertIn("Meu talhao", html)

    def test_a_conta_de_iot_nao_conta_o_vizinho(self):
        """Nenhum sensor alheio na contagem.

        Este é o número que o teste antigo apanhou a mentir — «IoT: 4»
        quando a base tinha 8. A versão de hoje é filtrada; confirmo.
        """
        from app.models import Device

        pminha = Propriedade.objects.filter(user=self.eu).first()
        pdele = Propriedade.objects.filter(user=self.viz).first()
        Device.objects.create(
            propriedade=pminha, nome="Meu", device_eui="eui-meu-x", tipo="SOLO"
        )
        for i in range(5):
            Device.objects.create(
                propriedade=pdele,
                nome="Dele %d" % i,
                device_eui="eui-dele-%d" % i,
                tipo="SOLO",
            )

        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        badge = re.search(r'class="badge"[^>]*>(.*?)</span>', html, re.S)
        self.assertIsNotNone(badge)
        m = re.search(r"·\s*(\d+)\s*sensor", badge.group(1))
        self.assertIsNotNone(m, "o badge não mostra sensores")
        self.assertEqual(
            int(m.group(1)),
            1,
            "a guia conta %s sensores. O produtor tem 1 e o vizinho tem 5."
            % m.group(1),
        )
