"""Regressões: escrever um lançamento tem de aparecer no painel.

Este ficheiro existe por causa de um defeito concreto: `dashboard_data`
guardava o payload em `cache["dash:<user_id>"]` durante 30 s e **nada** apagava
essa chave — não havia um único `cache.delete` no repositório. O produtor
lançava uma despesa, voltava ao painel, e via os números de antes (ou zeros,
se o payload ainda fosse o primeiro). O painel é um ecrã que parece
autoritário; 30 segundos de um número velho é uma mentira com formato de
fatura.

Não testamos o tempo (30 s) — testamos a CAUSA: que escrever apaga a chave.
Se alguém voltar a desligar estes sinais, o teste cai.

Ver `app/cache_painel.py` para a implementação e o raciocínio.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from app.api.views import dashboard_data
from app.models import LancamentoFinanceiro, Propriedade


class CacheDoPainelInvalidadoTest(APITestCase):
    """O painel tem de refletir uma escrita imediatamente a seguir."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test-cache-painel", password="test"
        )
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Cache", area_total=100, uf="SP"
        )
        cache.clear()
        self.factory = APIRequestFactory()

    def _painel(self):
        request = self.factory.get("/api/dashboard/")
        force_authenticate(request, user=self.user)
        response = dashboard_data(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_lancamento_novo_aparece_no_painel_sem_esperar_o_cache(self):
        """O teste que descreve a queixa: escreve, lê, o número já é o novo."""
        # Primeira leitura: sem lançamentos, o saldo é zero.
        self.assertEqual(self._painel()["fluxo_caixa"], 0)

        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Vendas",
            valor=5000,
            data=date.today(),
            descricao="Venda de milho",
        )

        # Sem invalidação, esta leitura devolveria 0 (o payload em cache).
        self.assertEqual(
            self._painel()["fluxo_caixa"],
            5000,
            "o lançamento gravado não apareceu no painel — cache não invalidado",
        )

    def test_area_da_fazenda_nova_aparece_no_painel(self):
        """A área é a base do custo/ha: mudar a área tem de mudar o painel."""
        self._painel()  # aquece o cache com area_total=100

        self.prop.area_total = 250
        self.prop.save()

        self.assertEqual(
            self._painel()["area_total"],
            250,
            "a área alterada não apareceu no painel — cache não invalidado",
        )

    def test_escrever_para_o_dono_nao_limpa_o_painel_de_outro(self):
        """Dois produtores são dois painéis:写的 de um não apaga o do outro.

        Sem isto, um único `cache.clear()` global resolveria o bug original —
        e trocava-o por um painel que pisca o do vizinho a cada importação.
        """
        outro = User.objects.create_user(username="test-cache-outro", password="test")
        Propriedade.objects.create(
            user=outro, nome="Fazenda Vizinha", area_total=10, uf="MG"
        )

        req = self.factory.get("/api/dashboard/")
        force_authenticate(req, user=outro)
        vizinho = dashboard_data(req).data
        self.assertEqual(vizinho["area_total"], 10)

        # O dono vizinho grava. O painel do primeiro produtor não pode mudar.
        prop_vizinha = Propriedade.objects.get(user=outro)
        prop_vizinha.area_total = 999
        prop_vizinha.save()

        req2 = self.factory.get("/api/dashboard/")
        force_authenticate(req2, user=self.user)
        meu = dashboard_data(req2).data
        self.assertEqual(
            meu["area_total"],
            100,
            "a escrita de um produtor limpou o cache de outro",
        )

    def test_calculo_apos_invalidar_continua_coerente(self):
        """Invalidação não pode alterar o que é calculado — só QUANDO.

        Protege contra uma correção "apague sempre o cache" que introduz um
        erro de cálculo ao caminho.
        """
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="Insumos",
            valor=2000,
            data=date.today(),
            descricao="Fertilizante",
        )
        payload = self._painel()

        # 2000 de despesa em 100 ha medidos.
        self.assertEqual(payload["custo_ha"], 20.0)
        self.assertTrue(payload["area_medida"])
        # Despesa registada E calculada: o ROI existe e é -100% (receita 0).
        self.assertEqual(payload["roi"], -100.0)

    def test_roi_sem_despesa_registada_nao_e_zero(self):
        """Só com receita, o ROI é "não há ROI para calcular" — não 0,0%.

        Com R$ 1000 de receita e zero despesas, `(1000-0)/0` não se divide.
        O painel que mostrava "0,0%" afirma que o produtor empatou.
        """
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Vendas",
            valor=1000,
            data=date.today(),
            descricao="Venda",
        )
        payload = self._painel()

        self.assertIsNone(
            payload["roi"],
            "um ROI sem despesa registada foi apresentado como 0%",
        )


class CacheNaoFabricaZeroTest(APITestCase):
    """O painel que devolve `{}` é pior do que o que devolve erro.

    `dashboard_data` respondia `{}` (HTTP 200) quando o utilizador não tem
    propriedade. O front-end tratava esse objecto vazio como "todos os campos
    a null" e cada KPI caía no seu `|| 0` — que é exactamente o
    "dados zerados" que o produtorihara. A resposta honesta é um estado
    vazio nomeado, não um dicionário sem chaves.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="test-sem-prop", password="test")
        cache.clear()

    def test_sem_propriedade_devolve_um_estado_explicito(self):
        request = APIRequestFactory().get("/api/dashboard/")
        force_authenticate(request, user=self.user)
        data = dashboard_data(request).data

        self.assertIsInstance(data, dict)
        # A resposta tem de dizer PORQUÊ está vazia, para o front-end poder
        # mostrar "sem propriedade" em vez de zeros.
        self.assertIn("sem_propriedade", data)
        self.assertTrue(data["sem_propriedade"])
        # E nenhum número inventado para preencher o vazio.
        for chave in ("roi", "custo_ha", "area_total", "fluxo_caixa"):
            self.assertIsNone(data.get(chave), f"{chave} foi inventado")


class DivisaoPorZeroTest(APITestCase):
    """Uma fazenda sem área medida é uma fazenda sem área medida."""

    def setUp(self):
        self.user = User.objects.create_user(username="test-sem-area", password="test")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Sem Area", area_total=0, uf="SP"
        )
        cache.clear()

    def test_despesa_sem_area_nao_vira_custo_por_hectare(self):
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="Insumos",
            valor=15000,
            data=date.today(),
            descricao="Adubo",
        )
        request = APIRequestFactory().get("/api/dashboard/")
        force_authenticate(request, user=self.user)
        data = dashboard_data(request).data

        # R$ 15.000 num dividendo de 1 ha dava R$ 15.000,00/ha. A fazenda não
        # foi medida, e portanto não há custo por hectare que se possa afirmar.
        self.assertIsNone(
            data["custo_ha"],
            "custo/ha inventado numa fazenda sem área medida",
        )
        self.assertFalse(data["area_medida"])
        # A despesa continua visível — é a área que falta, não o lançamento.
        self.assertEqual(data["financeiro"]["total_despesas"], 15000)
