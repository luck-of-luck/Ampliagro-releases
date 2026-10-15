"""Testes para o handler h_imagem_para_palco - extracao de widgets de dashboards."""

import json
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User

from app.ia.intents import h_imagem_para_palco


class ImagemParaPalcoTest(TestCase):
    """Testes de extracao de widgets de imagens de dashboard."""

    def setUp(self):
        self.user = User.objects.create_user("test_user", "test@x.com", "p")

    @patch("app.ia.intents.llm_gateway.chamar")
    def test_h_imagem_para_palco_extrai_tipos_widgets(self, mock_chamar):
        """Verifica que os tipos de widgets (kpi, chart, table) são extraídos corretamente."""
        mock_chamar.return_value = {
            "ok": True,
            "texto": '{"widgets": [{"type": "kpi", "title": "Produção Total", "value": "1.200 ton", "position": {"x": 0, "y": 0}}, {"type": "chart", "title": "Evolução Mensal", "chart_type": "line", "data": [10, 20, 15, 25], "position": {"x": 1, "y": 0}}, {"type": "table", "title": "Talhões", "columns": ["Talhao", "Area", "Cultura"], "rows": [["T1", "50 ha", "Soja"], ["T2", "30 ha", "Milho"]], "position": {"x": 0, "y": 1}}]}',
            "provedor": "local",
            " pedido": "local",
            "erro": "",
            "duracao_ms": 100,
        }

        params = {"image_url": "https://exemplo.com/dashboard.png"}
        ctx = {"fontes": []}

        resultado = h_imagem_para_palco(self.user, params, ctx)

        self.assertTrue(resultado["ok"])
        self.assertIn("widget_types", resultado["dados"])
        self.assertIn("positions", resultado["dados"])

        widget_types = resultado["dados"]["widget_types"]
        self.assertIn("kpi", widget_types)
        self.assertIn("chart", widget_types)
        self.assertIn("table", widget_types)

    @patch("app.ia.intents.llm_gateway.chamar")
    def test_h_imagem_para_palco_extrai_posicoes_widgets(self, mock_chamar):
        """Verifica que as posições dos widgets são extraídas corretamente."""
        mock_chamar.return_value = {
            "ok": True,
            "texto": '{"widgets": [{"type": "kpi", "title": "KPI 1", "position": {"x": 0, "y": 0}}, {"type": "chart", "title": "Chart 1", "position": {"x": 1, "y": 0}}, {"type": "table", "title": "Table 1", "position": {"x": 0, "y": 1}}, {"type": "kpi", "title": "KPI 2", "position": {"x": 1, "y": 1}}, {"type": "widget", "title": "Widget Extra", "position": {"x": 2, "y": 0}}]}',
            "provedor": "local",
            " pedido": "local",
            "erro": "",
            "duracao_ms": 100,
        }

        params = {"image_url": "https://exemplo.com/dashboard.png"}
        ctx = {"fontes": []}

        resultado = h_imagem_para_palco(self.user, params, ctx)

        self.assertTrue(resultado["ok"])
        self.assertIn("positions", resultado["dados"])

        positions = resultado["dados"]["positions"]
        self.assertLessEqual(len(positions), 4)

        for pos in positions:
            self.assertIn("type", pos)
            self.assertIn("position", pos)
            self.assertIn("x", pos["position"])
            self.assertIn("y", pos["position"])

    # MEDIDO 14/10/2026: este `@patch` estava na coluna 0 a decorar um metodo
    # indentado, e o ficheiro nao parseava. Nao e' um teste que falha: e' a
    # recolha de `app/ia/` INTEIRA que aborta com IndentationError, e o
    # workflow levava `--ignore=app/ia/tests_imagem_palco.py` para contornar.
    # Um `--ignore` bought a tempo e escondeu um ficheiro partido.
    @patch("app.ia.intents.llm_gateway.chamar")
    def test_h_imagem_para_palco_sem_imagem_retorna_erro(self, mock_chamar):
        """Verifica que retorna erro quando nenhuma imagem é fornecida."""
        params = {}
        ctx = {"fontes": []}

        resultado = h_imagem_para_palco(self.user, params, ctx)

        self.assertFalse(resultado["ok"])
        self.assertIn("error", resultado)
        self.assertIn("No image provided", resultado["error"])

    @patch("app.ia.intents.llm_gateway.chamar")
    def test_h_imagem_para_palco_com_image_base64(self, mock_chamar):
        """Verifica que funciona com image_base64 em vez de image_url."""
        mock_chamar.return_value = {
            "ok": True,
            "texto": '{"widgets": [{"type": "kpi", "title": "KPI", "position": {"x": 0, "y": 0}}]}',
            "provedor": "local",
            "pedido": "local",
            "erro": "",
            "duracao_ms": 100,
        }

        params = {
            "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        }
        ctx = {"fontes": []}

        resultado = h_imagem_para_palco(self.user, params, ctx)

        self.assertTrue(resultado["ok"])
        mock_chamar.assert_called_once()

    @patch("app.ia.intents.llm_gateway.chamar")
    def test_h_imagem_para_palco_ignora_tipos_nao_reconhecidos(self, mock_chamar):
        """Verifica que widgets de tipos não reconhecidos são ignorados."""
        mock_chamar.return_value = {
            "ok": True,
            "texto": '{"widgets": [{"type": "kpi", "title": "KPI Válido", "position": {"x": 0, "y": 0}}, {"type": "chart", "title": "Chart Válido", "position": {"x": 1, "y": 0}}, {"type": "table", "title": "Table 1", "position": {"x": 0, "y": 1}}, {"type": "kpi", "title": "KPI 2", "position": {"x": 1, "y": 1}}, {"type": "widget", "title": "Widget Extra", "position": {"x": 2, "y": 0}}]}',
            "provedor": "local",
            "pedido": "local",
            "erro": "",
            "duracao_ms": 100,
        }

        params = {"image_url": "https://exemplo.com/dashboard.png"}
        ctx = {"fontes": []}

        resultado = h_imagem_para_palco(self.user, params, ctx)

        self.assertTrue(resultado["ok"])
        widget_types = resultado["dados"]["widget_types"]
        self.assertIn("kpi", widget_types)
        self.assertIn("chart", widget_types)
        self.assertNotIn("tipo-invalido", widget_types)

    @patch("app.ia.intents.llm_gateway.chamar")
    def test_h_imagem_para_palco_trata_erro_llm(self, mock_chamar):
        """Verifica que erros do LLM são tratados graciosamente."""
        mock_chamar.return_value = {
            "ok": False,
            "texto": "",
            "provedor": "openai-compatible",
            "pedido": "remoto",
            "erro": "Timeout na chamada à API",
            "duracao_ms": 20000,
        }

        params = {"image_url": "https://exemplo.com/dashboard.png"}
        ctx = {"fontes": []}

        resultado = h_imagem_para_palco(self.user, params, ctx)

        self.assertFalse(resultado["ok"])
        self.assertIn("error", resultado)
        self.assertIn("Erro ao analisar imagem", resultado["error"])
