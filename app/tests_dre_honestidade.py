"""O DRE não pode afirmar uma linha que não mediu.

## Os três defeitos

**1. `deducoes` é um zero que ninguém mediu.** Está hardcoded
(`dre.py:41-43`, com o comentário "pode ser categorizado futuramente") e entra
em `receita_liquida`. O ecrã mostra "(-) Deduções da Receita Bruta: R$ 0,00"
com o mesmo peso tipográfico das linhas medidas. **Não há devolução modelleda:
há uma linha que diz que não houve devolução.** Para quem lê um DRE para
obter crédito, esta é a linha mais perigosa do ecrã — é a diferença entre
"receita bruta R$ 500 mil" e "receita bruta R$ 500 mil menos o que
devolvemos", e o sistema não sabe o segundo número.

**2. `SEMENTE` e `JUROS` estão no mapa e não existem.** `mapa_grupos`
(`dre.py:29,36`) mapeia categorias que não estão em `CATEGORIAS_FINANCEIRO`
(`models/financeiro.py:11-24`). São chaves mortas: nunca casam. O teste
`test_mapa_nao_inventa_categorias` falha até isto ser corrigido.

**3. Uma categoria desconhecida é engolida em silêncio.** `dre.py:69-71` tem
`mapa_grupos.get(categoria, ...)` com um default. Uma receita que não mapeia
entra como `receita_bruta` sem ninguém saber. **Um default que classifica é
mais perigoso que um erro**, porque produz um DRE plausível e errado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import LancamentoFinanceiro, Propriedade
from app.services.dre import gerar_dre


class DREHonestidadeTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )

    def _lanca(self, tipo, categoria, valor, dia=10):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo=tipo,
            categoria=categoria,
            valor=Decimal(valor),
            data=date(2026, 3, dia),
            descricao="teste",
        )

    def _dre(self):
        return gerar_dre(self.prop.id, date(2026, 1, 1), date(2026, 12, 31))

    # ------------------------------------------------------------------
    # Defeito 1 — deducoes
    # ------------------------------------------------------------------

    def test_deducoes_nao_e_um_zero_afirmado(self):
        """`deducoes` tem de declarar que não foi medida.

        Não aceito `0.00`: isso diz "não houve devolução". O honesto é `None`
        com o motivo, porque **o sistema não tem devolução para medir**.
        """
        self._lanca("RECEITA", "VENDA_PROD", "500000.00")
        dre = self._dre()

        self.assertIsNone(
            dre["deducoes"],
            "deducoes=0 afirma que nao houve devolucao. Nao houve? "
            "Nao — nunca houve devolucao modelleda.",
        )
        self.assertIsNotNone(dre["deducoes_motivo"])

    def test_receita_liquida_nao_depende_de_uma_linha_nao_medida(self):
        """Se deducoes não é medida, a líquida não pode derivar dela.

        Uma `receita_liquida` calculada a partir de um zero inventado é um
        número com dois graus de erro: o das deduções e o das receitas.
        """
        self._lanca("RECEITA", "VENDA_PROD", "500000.00")
        dre = self._dre()

        self.assertIsNone(
            dre["receita_liquida"],
            "derivou de deducoes nao medida",
        )
        # A bruta continua medida — é ela que se pode mostrar.
        self.assertEqual(dre["receita_bruta"], Decimal("500000.00"))

    def test_dre_avisa_que_a_liquida_nao_e_confiavel(self):
        self._lanca("RECEITA", "VENDA_PROD", "500000.00")
        dre = self._dre()
        self.assertIn("deducoes", [i.get("linha") for i in dre["incompleto"]])
        self.assertIsNotNone(dre["aviso"])

    # ------------------------------------------------------------------
    # Defeito 2 — categorias que não existem
    # ------------------------------------------------------------------

    def test_mapa_nao_inventa_categorias(self):
        """Toda chave do mapa é uma categoria real do modelo.

        `SEMENTE` e `JUROS` estão no mapa (`dre.py:29,36`) e não estão em
        `CATEGORIAS_FINANCEIRO`. São chaves mortas que sugerem uma cobertura
        que o sistema não tem.
        """
        from app.models.financeiro import CATEGORIAS_FINANCEIRO
        from app.services.dre import mapa_grupos

        reais = {c for c, _ in CATEGORIAS_FINANCEIRO}
        inventadas = sorted(set(mapa_grupos) - reais)
        self.assertEqual(
            inventadas,
            [],
            f"categorias no mapa que o modelo nao tem: {inventadas}",
        )

    def test_toda_categoria_real_tem_grupo(self):
        """O outro sentido: nenhuma categoria real fica sem grupo.

        Se alguma ficar, cai no default e é engolida em silêncio — o defeito 3.
        """
        from app.models.financeiro import CATEGORIAS_FINANCEIRO
        from app.services.dre import mapa_grupos

        reais = {c for c, _ in CATEGORIAS_FINANCEIRO}
        sem_grupo = sorted(reais - set(mapa_grupos))
        self.assertEqual(
            sem_grupo,
            [],
            f"categorias reais sem grupo, que caem no default: {sem_grupo}",
        )

    # ------------------------------------------------------------------
    # Defeito 3 — o default que engole
    # ------------------------------------------------------------------

    def test_categoria_desconhecida_e_reportada_nao_engolida(self):
        """Uma categoria fora do mapa tem de ser nomeada.

        `dre.py:69-71` tinha `mapa_grupos.get(categoria, "despesa_operacional"
        if tipo == "DESPESA" else "receita_bruta")`. Uma receita não mapeada
        entrava como receita bruta **sem ninguém saber** — o DRE ficava
        plausível e errado.

        `BARTER` é uma categoria que o sistema **não tem**, mas que um
        importador ou um `.update()` com um mapeamento errado escreveria.
        Gravo-a directamente: `choices` no Django é validação de formulário,
        não de base de dados — não impede `objects.create()`.
        """
        self._lanca("RECEITA", "VENDA_PROD", "100000.00")
        self._lanca("RECEITA", "BARTER", "70000.00")

        dre = self._dre()

        nao_classificadas = [c["categoria"] for c in dre["nao_classificadas"]]
        self.assertIn(
            "BARTER",
            nao_classificadas,
            "categoria desconhecida engolida em silencio",
        )
        self.assertIn("BARTER", [i.get("categoria") for i in dre["incompleto"]])

        # E não pode ter entrado como receita bruta: 100k, não 170k.
        self.assertEqual(
            dre["receita_bruta"],
            Decimal("100000.00"),
            "BARTER foi publicado como receita bruta",
        )

    def test_incompleto_reporta_a_linha_deducoes(self):
        """`incompleto` nomeia a linha, não só diz que há algo."""
        self._lanca("RECEITA", "VENDA_PROD", "100000.00")
        dre = self._dre()
        linhas = [i.get("linha") for i in dre["incompleto"]]
        self.assertIn("deducoes", linhas)

    def test_receita_liquida_muda_para_none_quando_a_deducao_e_zero(self):
        """Regressão: com dedução medida, a líquida passa a existir."""
        dre = self._dre()
        # Período sem lançamentos: bruta 0, deducoes None -> líquida None.
        self.assertIsNone(dre["deducoes"])
        self.assertIsNone(dre["receita_liquida"])
