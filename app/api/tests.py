from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from app.models import Cultura, Propriedade, Safra, Talhao

from .views import (
    CulturaViewSet,
    PerfilUsuarioViewSet,
    PropriedadeViewSet,
    WidgetUsuarioViewSet,
    widgets_layout_sync,
)


class CulturaAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test-cultura", password="test")

    def test_culturas_list(self):
        factory = APIRequestFactory()
        view = CulturaViewSet.as_view({"get": "list"})
        request = factory.get("/api/culturas/")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)


class PropriedadeAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test-propriedade", password="test"
        )

    def test_propriedades_list(self):
        factory = APIRequestFactory()
        view = PropriedadeViewSet.as_view({"get": "list"})
        request = factory.get("/api/propriedades/")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_propriedade_counts_annotated(self):
        prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Teste", area_total=100
        )
        cultura = Cultura.objects.create(nome="Soja")
        Talhao.objects.create(
            propriedade=prop, nome="Talhão 1", area_hectare=50, cultura_atual=cultura
        )
        Talhao.objects.create(propriedade=prop, nome="Talhão 2", area_hectare=30)
        Safra.objects.create(
            propriedade=prop,
            safra_nome="Safra 23/24",
            ano=2024,
            area_plantada=80,
            cultura=cultura,
        )
        factory = APIRequestFactory()
        view = PropriedadeViewSet.as_view({"get": "list"})
        request = factory.get("/api/propriedades/")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(hasattr(response, "data"))

    def test_safra_related_fields(self):
        from app.models import Talhao as T

        from .views import SafraViewSet

        prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Teste", area_total=100
        )
        cultura = Cultura.objects.create(nome="Milho")
        talhao = T.objects.create(propriedade=prop, nome="Talhão 1", area_hectare=50)
        Safra.objects.create(
            propriedade=prop,
            safra_nome="Safra 24",
            ano=2024,
            area_plantada=80,
            cultura=cultura,
            talhao=talhao,
        )
        factory = APIRequestFactory()
        view = SafraViewSet.as_view({"get": "list"})
        request = factory.get("/api/safras/")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        # Apenas verifica status, dados são paginados e podem variar
        self.assertTrue(hasattr(response, "data"))


class WidgetUsuarioAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", password="test")

    def test_widgets_usuario_list(self):
        factory = APIRequestFactory()
        view = WidgetUsuarioViewSet.as_view({"get": "list"})
        request = factory.get("/api/widgets-usuario/")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_widgets_layout_sync(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/widgets-layout-sync/",
            {
                "widgets": {
                    "kpi-roi": {
                        "gridX": 1,
                        "gridY": 2,
                        "gridW": 3,
                        "gridH": 4,
                        "visible": True,
                    }
                }
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = widgets_layout_sync(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["saved"], 1)


class PerfilUsuarioAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test-perfil", password="test")

    def test_perfis_usuario_list(self):
        factory = APIRequestFactory()
        view = PerfilUsuarioViewSet.as_view({"get": "list"})
        request = factory.get("/api/perfis_usuario/")
        force_authenticate(request, user=self.user)
        response = view(request)
        self.assertEqual(response.status_code, 200)


class DashboardDataRealTest(APITestCase):
    """Regressões do painel: só dados reais e cálculos consistentes."""

    def setUp(self):
        from django.core.cache import cache

        self.user = User.objects.create_user(
            username="test-dashboard-real", password="test"
        )
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda Dashboard",
            area_total=100,
            uf="SP",
            cidade="Ribeirão Preto",
        )
        cache.clear()

    def _request_dashboard(self):
        factory = APIRequestFactory()
        request = factory.get("/api/dashboard/")
        force_authenticate(request, user=self.user)
        from .views import dashboard_data

        response = dashboard_data(request)
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_saldo_e_os_pendentes_nao_inventam_nem_inflacionam(self):
        from datetime import date, timedelta

        from app.models import LancamentoFinanceiro, Maquinario

        hoje = date.today()
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="Vendas",
            valor=1000,
            data=hoje,
            descricao="Venda de soja",
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="Insumos",
            valor=250,
            data=hoje,
            descricao="Ureia",
        )
        Maquinario.objects.create(
            propriedade=self.prop,
            tipo="TRATOR",
            nome="Trator atrasado",
            proxima_manutencao=hoje - timedelta(days=3),
        )
        Maquinario.objects.create(
            propriedade=self.prop,
            tipo="COLHEDORA",
            nome="Colhedora em dia",
            proxima_manutencao=hoje + timedelta(days=90),
        )

        data = self._request_dashboard()

        self.assertEqual(data["financeiro"]["total_receitas"], 1000.0)
        self.assertEqual(data["financeiro"]["total_despesas"], 250.0)
        self.assertEqual(data["financeiro"]["saldo"], 750.0)
        # Só a manutenção vencida conta: o maquinário futuro não infla o KPI.
        self.assertEqual(data["os_pendentes"], 1)
        self.assertEqual(data["resumo"]["total_maquinarios"], 2)
        # "Hoje" é o saldo real do dia; não há series horárias inventadas.
        self.assertEqual(data["chart_data"]["today"]["data"], [750.0])
        self.assertNotIn("06h", data["chart_data"]["today"]["labels"])
        self.assertEqual(data["chart_data"]["week"]["data"][hoje.weekday()], 750.0)
        self.assertEqual(len(data["chart_data"]["week"]["labels"]), 7)

    def test_dashboard_sem_lancamentos_nao_falha(self):
        data = self._request_dashboard()
        self.assertEqual(data["os_pendentes"], 0)
        self.assertEqual(data["financeiro"]["saldo"], 0.0)
        self.assertEqual(data["chart_data"], {})
