"""Persistência, atomicidade e isolamento das operações de widgets."""

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.intents_preset_crud import h_preset_editar
from app.ia.intents_widget import h_widget_alterar, h_widget_ler
from app.models.palco import PresetPalco


class WidgetOperacoesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("widget-owner")
        self.outro = User.objects.create_user("widget-other")
        self.widget = {
            "tipo": "kpi-caixa",
            "titulo": "Meu caixa",
            "config": {"ano": 2026},
        }
        self.origem = PresetPalco.objects.create(
            user=self.user,
            slug="custom-origem",
            nome="Origem",
            fixado=True,
            estrutura={
                "widgets": [self.widget, {"tipo": "kpi-custo", "titulo": "Custo"}],
                "layout": "grid-2x3",
            },
        )
        self.destino = PresetPalco.objects.create(
            user=self.user,
            slug="custom-destino",
            nome="Destino",
            estrutura={"widgets": []},
        )

    def alterar(self, **extra):
        return h_widget_alterar(
            self.user,
            {
                "preset": "Origem",
                "widget": "kpi-caixa",
                "operacao": "mover",
                "confirm": True,
                **extra,
            },
            {},
        )

    def test_move_preserva_configuracao_e_remove_da_origem(self):
        self.assertTrue(self.alterar(destino="Destino")["ok"])
        self.origem.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(self.destino.estrutura["widgets"], [self.widget])
        self.assertEqual(len(self.origem.estrutura["widgets"]), 1)

    def test_reordena_sem_perder_pecas(self):
        self.assertTrue(self.alterar(posicao=2)["ok"])
        self.origem.refresh_from_db()
        self.assertEqual(self.origem.estrutura["widgets"][1], self.widget)

    def test_nao_move_sem_confirmacao(self):
        self.assertTrue(self.alterar(destino="Destino", confirm=False)["needs_confirm"])
        self.origem.refresh_from_db()
        self.assertEqual(len(self.origem.estrutura["widgets"]), 2)

    def test_destino_alheio_nao_remove_origem(self):
        self.destino.user = self.outro
        self.destino.save()
        self.assertFalse(self.alterar(destino="Destino")["ok"])
        self.origem.refresh_from_db()
        self.assertEqual(len(self.origem.estrutura["widgets"]), 2)
        self.assertFalse(h_widget_ler(self.outro, {"preset": "Origem"}, {})["ok"])

    def test_edita_apenas_campos_solicitados(self):
        self.assertTrue(
            self.alterar(operacao="editar", titulo="Saldo", config={"mes": 10})["ok"]
        )
        self.origem.refresh_from_db()
        self.assertEqual(
            self.origem.estrutura["widgets"][0],
            {**self.widget, "titulo": "Saldo", "config": {"ano": 2026, "mes": 10}},
        )

    def test_exclui_um_widget(self):
        self.assertTrue(self.alterar(operacao="excluir")["ok"])
        self.origem.refresh_from_db()
        self.assertEqual(
            [w["tipo"] for w in self.origem.estrutura["widgets"]], ["kpi-custo"]
        )

    def test_posicao_invalida_nao_escreve(self):
        for posicao in (0, 4, True, "2"):
            self.assertFalse(self.alterar(posicao=posicao)["ok"])
        self.origem.refresh_from_db()
        self.assertEqual(self.origem.estrutura["widgets"][0], self.widget)

    def test_adicionar_preserva_titulo_config_layout_e_fixacao(self):
        resultado = h_preset_editar(
            self.user,
            {"nome": "Origem", "adicionar": ["kpi-alertas"], "confirm": True},
            {},
        )
        self.assertTrue(resultado["ok"], resultado)
        self.origem.refresh_from_db()
        self.assertEqual(self.origem.estrutura["widgets"][0], self.widget)
        self.assertEqual(self.origem.estrutura["layout"], "grid-2x3")
        self.assertTrue(self.origem.fixado)

    def test_mcp_publica_schema_e_sandbox_confirma(self):
        from app.amplia_mcp import catalogo_tools
        from app.ia.sandbox import executar

        tool = next(t for t in catalogo_tools() if t["name"] == "amplia_widget_alterar")
        self.assertIn("posicao", tool["inputSchema"]["properties"])
        resultado = executar(
            self.user,
            "widget_alterar",
            {"preset": "Origem", "widget": "kpi-caixa", "operacao": "excluir"},
        )
        self.assertTrue(resultado["needs_confirm"], resultado)
        self.origem.refresh_from_db()
        self.assertEqual(len(self.origem.estrutura["widgets"]), 2)
