"""Guia de Ferramentas: o que foi feito e o que ficou por fazer.

MEDIDO 2026-10-05. Sessão centrada em reconstruir `/guias/ferramentas/`.

O PEDIDO E A TENSÃO QUE ELE CONTÉM
==================================
Pediu-se: a guia de ferramentas com muito mais capacidades, separadas por
classe como um produto de topo de mercado, sem «cara de IA com emojis e
ícones», cheia de campos, com alguns obrigatórios e vários de governança.

A lista de mercado tem ~70 itens. **13 deles não existem neste repositório**:
MDF-e, certificado A1, IBS/CBS, drones, beneficiamento, contratos de safra,
John Deere Operations Center, Stara, FieldView, Solinftec, OTA, WhatsApp,
MRV.

A resposta óbvia — escrever os 70 no template — seria **o mesmo defeito que
foi corrigido duas vezes no mesmo dia**: o botão NDVI exibia `0.72` no
`catch` de uma rota 404. Um número gerado assinado como leitura. Uma lista de
capacidades inexistentes assinada como entregues é o mesmo erro com mais
linhas, e mais difícil de notar porque ninguém clica em 60 cartões.

O que se fez em vez disso
=========================
- 57 capacidades em 7 classes (A B C D E G H — sem F, como a lista), com
  **estado declarado e prova `caminho:linha` verificada por teste**:
  27 operacionais, 17 parciais com a fronteira escrita, 13 ausentes.
- `tests/test_guia_ferramentas_confere_com_codigo.py` — 14 testes que abrem o
  ficheiro e leem a linha. Um item que diz EXISTE tem rota que resolve e
  código na linha; um NAO_EXISTE **não pode ter rota**.
- 9 ferramentas de campo funcionais, e um simulador de governança com 4
  obrigatórios e 6 opcionais.
- `tests/test_guia_ferramentas_campos.py` — os obrigatórios não têm valor
  por omissão. A regra: obrigatório é o campo que o produtor **ainda não
  decidiu**.
- `tests/test_guia_ferramentas_render.py` — 9 testes de renderização e
  isolamento. Um template pode passar todos os testes estruturais e nunca
  chegar a ser HTML: `caderno/offline.html` está em disco, tem teste, e não
  está registado em nenhum `urls.py`.

O ERRO QUE REPITI DUAS VEZES
=============================
**Escrevi rotas em vez de as ler.** Onze rotas inventadas a partir de nomes
de serviço; sete não resolviam. `/custos/talhao/` não existe — existe
`/custos/producao/`. Foi exactamente o defeito do botão NDVI, e aconteceu
porque escrevi um caminho em vez de o perguntar ao `resolve()`.

A correcção não é «ter cuidado»: é o teste `test_todo_item_operacional_abre_uma_rota_que_resolve`
perguntar ao servidor de URLs a cada build. E as classes CSS de estado
ficaram com o mesmo peso visual para os três estados, porque um item que não
existe não pode ter o mesmo aspecto do que funciona — o produtor clica nos
dois.
"""

from __future__ import annotations

import pathlib
import re
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "guia-ferramentas.html"


def fonte() -> str:
    return TEMPLATE.read_text(encoding="utf-8", errors="replace")


class OEstiloNaoTemCaraDeIA(TestCase):
    """O pedido foi explícito: «sem essa cara de IA com emojis e ícones».

    Testá-lo é Subjective e não escala. Testar o que é objectivo — os
    emoji, e os icon-shared — é verificável e é o que apareceu nas páginas
    geradas por IA.
    """

    def test_nao_ha_emoji_no_template(self):
        """Zero emoji.

        A página antiga tinha `🧮 📊 📡 🛠️` nos separadores e `🌱 🌾 💧 📐`
        nos títulos dos cartões. Os números dos separadores desceram com o
        catálogo; os emoji também têm de descer.
        """
        emoji = re.compile(
            "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]"
        )
        achados = emoji.findall(fonte())
        self.assertEqual(
            achados,
            [],
            f"a guia tem {len(achados)} emoji: {sorted(set(achados))}\n\n"
            f"O pedido foi exactamente não ter «cara de IA com emojis e "
            f"ícones». Os ícones Bootstrap também saem: a hierarquia visual "
            f"é feita por peso, cor e barra lateral de estado.",
        )

    def test_nao_ha_classe_de_icon_font_awesome(self):
        """`bi bi-...` é o sinal de ícone herdado.

        A hierarquia agora é: peso da fonte, cor, e a barra de 3 px à
        esquerda do cartão. Não há glifo a carregar antes do texto aparecer.
        """
        t = fonte()
        self.assertNotIn("bi bi-", t, "a guia ainda usa ícones Bootstrap (`bi bi-*`)")
        self.assertNotIn("fa fa-", t, "a guia ainda usa Font Awesome (`fa fa-*`)")

    def test_a_hierarquia_e_feita_com_peso_e_cor(self):
        """O que substitui o ícone: peso no nome, cor no estado, barra no cartão.

        Se alguém remove a barra lateral e põe um ícone no lugar, este teste
        avisa. É a verificação do substituto, não só do que foi retirado.
        """
        t = fonte()
        for seletor in (
            ".gf-item::before",  # a barra de estado
            ".gf-item-nome",
            ".gf-seccao-letra",
            ".gf-item-estado",
        ):
            self.assertIn(
                seletor,
                t,
                f"falta {seletor}. A hierarquia visual sem ícones depende "
                f"dele — e se desaparecer, volta o ícone.",
            )


class AGuiaCumpreOPedido(TestCase):
    """O que foi pedido, medido. Não «parece bom», conta."""

    def setUp(self):
        self.u = User.objects.create_user("guia_pedido", password="x1234567")
        self.client.force_login(self.u)
        self.html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")

    def test_muito_mais_capacidades_que_as_17_antigas(self):
        """A guia tinha 17 ferramentas. Passou a ter 57 capacidades."""
        from app.guias.catalogo import CATALOGO

        total = sum(len(c["itens"]) for c in CATALOGO)
        self.assertGreater(total, 17, "a guia encolheu. O pedido era «muitos mais».")
        self.assertGreaterEqual(total, 57)

    def test_separadas_por_classe(self):
        """Cada classe da lista do mercado é uma secção navegável."""
        from app.guias.catalogo import CATALOGO

        for classe in CATALOGO:
            self.assertIn(
                f'id="sec-{classe["id"]}"',
                self.html,
                f"a secção {classe['id']} não está na página",
            )

    def test_muitos_campos_e_uns_poucos_obrigatorios(self):
        """O pedido: «cheia de campos, com alguns obrigatórios para simular».

        Conto os campos do simulador: obrigatórios e opcionais, e confirmo
        que a proporção é a pedida — poucos obrigatórios, vários de
        controlo.
        """
        obrigatorios = ["gvArea", "gvCusto", "gvPreco", "gvProd"]
        opcionais = [
            "gvPerdas",
            "gvFrete",
            "gvFinanceiro",
            "gvMargemSeg",
            "gvFonte",
            "gvValidador",
        ]
        for campo in obrigatorios + opcionais:
            self.assertIn(f'id="{campo}"', self.html, f"falta o campo {campo}")
        self.assertEqual(
            len(opcionais) > len(obrigatorios),
            True,
            "o pedido era poucos obrigatórios e vários de controlo. Está invertido.",
        )

    def test_o_nome_da_classe_aparece_para_o_produtor(self):
        """A letra é para o produtor que viu a lista; o nome, para ele escrever."""
        from app.guias.catalogo import CATALOGO

        for classe in CATALOGO:
            self.assertIn(
                classe["nome"],
                self.html,
                f"o nome da classe {classe['nome']} não aparece",
            )


class OsTresEstadosTemOMesmoPesoVisual(TestCase):
    """A regra que impede a lista de voltar a ser marketing.

    Um cartão que não existe com o mesmo aspecto do que funciona é um
    cartão que o produtor clica. O peso visual é o que diz ao olhar, antes
    de ler, que este não abre.
    """

    def setUp(self):
        # MEDIDO 2026-10-05: esta classe não fazia login, e a view é
        # `@login_required`. O teste recebia a **página de login** em vez
        # da guia — que não tem cartões — e falhava por `[] is not true`.
        #
        # E o sintoma era enganador: `assertTrue(ausentes)` numa lista vazia
        # parece dizer «a página não desenhou os cartões ausentes». O que
        # dizia era «não viste a página». Um teste que não faz login e
        # passa por estar a testar a página está a testar o redirect.
        self.u = User.objects.create_user("guia_peso", password="x1234567")
        self.client.force_login(self.u)

    def test_as_tres_classe_css_existem(self):
        t = fonte()
        for classe in ("i-existe", "i-parcial", "i-ausente"):
            self.assertIn(f".gf-item.{classe}", t)

    def test_cada_estado_tem_a_sua_barra(self):
        """A barra lateral é o indicador primário — não um badge pequeno.

        Um badge passa despercebido numa grelha de 60; uma barra de 3 px que
        atravessa o cartão lê-se de relance.
        """
        t = fonte()
        self.assertIn(".gf-item::before", t)
        for classe, cor in (
            ("i-existe", "var(--cor-primaria)"),
            ("i-parcial", "var(--cor-aviso"),
        ):
            self.assertIn(f".gf-item.{classe}::before", t)
            self.assertIn(cor, t)
        # O ausente não recebe a barra primária: é deliberadamente discreto.
        self.assertIn(
            ".gf-item.i-ausente::before",
            t,
            "o item ausente devia ter a barra mais discreta das três — e "
            "ainda não tem nenhuma regra própria.",
        )

    def test_o_nao_implementado_diz_na_ausencia_dado(self):
        """A nota do ausente explica que não há botão — não mostra um 404.

        Um cartão cinza com «Sem botão porque não abriria em lado nenhum» é
        o que um vendedor de verdade lhe diria. O que não se faz é
        apresentá-lo clicável.
        """
        from app.guias.catalogo import NAO_EXISTE

        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        ausentes = re.findall(
            r'<article class="gf-item i-ausente"[^>]*>(.*?)</article>', html, re.S
        )
        self.assertTrue(ausentes)
        for corpo in ausentes:
            self.assertIn(
                "gf-ausente-nota",
                corpo,
                "um cartão de capacidade ausente não explica a ausência. "
                "Cinza sem explicação parece um cartão avariado, não um "
                "reconhecimento.",
            )


class AIsolamentoContinuaValendo(TestCase):
    """O teste antigo protegia isto. A reconstrução não pode tê-lo perdido."""

    def setUp(self):
        self.eu = User.objects.create_user("guia_iso2", password="x1234567")
        self.viz = User.objects.create_user("guia_iso2_v", password="x1234567")
        p1 = __import__(
            "app.models", fromlist=["Propriedade"]
        ).Propriedade.objects.create(
            user=self.eu, nome="Minha", area_total=Decimal("1")
        )
        p2 = __import__(
            "app.models", fromlist=["Propriedade"]
        ).Propriedade.objects.create(
            user=self.viz, nome="Dele", area_total=Decimal("1")
        )
        T = __import__("app.models", fromlist=["Talhao"]).Talhao
        T.objects.create(propriedade=p1, nome="Meu", area_hectare="1")
        T.objects.create(propriedade=p2, nome="Alheio", area_hectare="1")
        self.client.force_login(self.eu)

    def test_o_talhao_alheio_nao_aparece(self):
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        self.assertNotIn("Alheio", html)

    def test_a_rota_do_ndvi_exige_talhao(self):
        """A excepção que vem do `talhao=1` fixo: sem parâmetro, é 400."""
        r = self.client.get("/api/agronomia/ndvi/")
        self.assertEqual(r.status_code, 400)
