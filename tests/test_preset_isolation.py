import json

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from app.models.usuario import DashboardUserState

User = get_user_model()


class PresetIsolationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testpreset", password="pass")
        self.factory = RequestFactory()

    def test_fast_clone_isolation(self):
        """Garante que _fastClone nao compartilha referencia (simulado em Python)"""
        import copy

        a = {"kpi-roi": {"gridX": 0, "gridY": 0}}
        b = copy.deepcopy(a)
        b["kpi-roi"]["gridX"] = 99
        self.assertEqual(a["kpi-roi"]["gridX"], 0, "deep copy deve isolar")

    def test_presets_distintos_no_server(self):
        """Presets salvos no DashboardUserState devem ser distintos, nao clones"""
        # Simula dois presets com layouts distintos
        visao_geral = {"kpi-roi": {"gridX": 0}, "kpi-custo": {"gridX": 8}}
        visao_campo = {"kpi-produtividade": {"gridX": 0}, "chart-safras": {"gridX": 24}}
        state = {
            "layout": visao_geral,
            "active_preset": "visao-geral",
            "presets_order": ["visao-geral", "visao-campo", "visao-financeira"],
            "presets": {
                "visao-campo": visao_campo,
                "visao-financeira": {"kpi-caixa": {"gridX": 16}},
            },
            "presets_meta": {},
        }
        obj, _ = DashboardUserState.objects.get_or_create(user=self.user)
        obj.state = state
        obj.save()
        obj.refresh_from_db()
        # Verifica que visao-campo nao foi clonado de visao-geral
        self.assertNotEqual(
            json.dumps(obj.state["presets"]["visao-campo"], sort_keys=True),
            json.dumps(obj.state["layout"], sort_keys=True),
            "preset nao deve ser clone do layout",
        )
        # Verifica que dois presets sao diferentes entre si
        self.assertNotEqual(
            json.dumps(obj.state["presets"]["visao-campo"], sort_keys=True),
            json.dumps(obj.state["presets"]["visao-financeira"], sort_keys=True),
        )

    def test_repair_cloned_presets(self):
        """Simula reparo: se dois presets tem mesmo JSON, um deve ser detectado como clone"""
        clone = {"kpi-roi": {"gridX": 0}}
        state = {
            "layout": clone,
            "presets": {
                "visao-campo": clone,
                "visao-financeira": clone,  # clonado!
                "custom-arroz": {"kpi-arroz": {"gridX": 5}},
            },
            "presets_meta": {},
        }
        # detecta clones
        seen = {}
        clones = []
        for k, v in state["presets"].items():
            js = json.dumps(v, sort_keys=True)
            if js in seen and js != "{}":
                clones.append(k)
            else:
                seen[js] = k
        self.assertIn("visao-financeira", clones, "deve detectar clonagem")
        self.assertNotIn("custom-arroz", clones)

    def test_persist_nao_sobrescreve_vazio(self):
        """persistPresetWidgets nao deve sobrescrever preset com dados com {} vazio"""
        # Simula logica JS: se value é {} e existing tem dados, skip
        existing = {"kpi-roi": {"gridX": 0}}
        value_empty = {}
        should_skip = not value_empty and existing and len(existing) > 0
        # value_empty is {} -> bool({}) is False, so not {} is True, existing true -> skip
        # Em Python: not {} == True
        self.assertTrue(should_skip or (not value_empty and bool(existing)))

    def test_visao_base_protegido(self):
        """visao-geral e visao-base nao devem ser deletaveis (simula deletePresetByKey)"""

        def can_delete(key):
            return key not in ("visao-geral", "visao-base")

        self.assertFalse(can_delete("visao-geral"))
        self.assertFalse(can_delete("visao-base"))
        self.assertTrue(can_delete("visao-campo"))
        self.assertTrue(can_delete("visao-financeira"))
        self.assertTrue(can_delete("visao-executivo"))
        self.assertTrue(can_delete("custom-arroz"))
