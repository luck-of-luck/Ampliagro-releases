"""Chuva da semana em peça + CRUD de presets pela IA.

O QUE ESTE FICHEIRO PROVA
=========================
1. `chuva_semana` responde Sim/Não com os dias e entrega `dados.serie`
   (dias×mm) de dados REAIS — nunca inventados, nunca zeros no lugar de
   medição ausente.
2. Toda série que entra vira peça validada e carimbada MEDIDO pela fonte
   `chuva-semana` (o caminho que o dashboard usa).
3. O sandbox só compõe a peça com o modo painel ligado; com chat ou sem
   modo, vão prosa (+série para o gráfico do chat).
4. Presets: listar (lê), editar por peça e apagar — com confirmação, com
   guarda e sem vazar entre produtores.

Tudo sem rede: `obter_previsao` é mockada na fronteira do fetch; a
formatação (rótulos, prosa, blocos) roda de verdade, que é o que estes
testes medem.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.intents_chuva import INTENTS_CHUVA, rotulo_dia, serie_de
from app.ia.sandbox import executar

DIAS = [
    {"dia": "2026-10-12", "tmax": 28, "tmin": 18, "prob": 80, "mm": 12.5},
    {"dia": "2026-10-13", "tmax": 27, "tmin": 17, "prob": 20, "mm": 0.0},
    {"dia": "2026-10-14", "tmax": 29, "tmin": 19, "prob": 60, "mm": 4.0},
    {"dia": "2026-10-15", "tmax": 30, "tmin": 20, "prob": 10, "mm": 0.0},
    {"dia": "2026-10-16", "tmax": 26, "tmin": 18, "prob": None, "mm": None},
    {"dia": "2026-10-17", "tmax": 25, "tmin": 17, "prob": 90, "mm": 22.0},
    {"dia": "2026-10-18", "tmax": 27, "tmin": 18, "prob": 30, "mm": 0.4},
]

PREV = {"ok": True, "dias": DIAS}


def _prop(nome="Fazenda Chuva", user=None):
    from app.models import Propriedade

    return Propriedade.objects.create(
        user=user, nome=nome, area_total=10, cidade="Alterosa", uf="MG"
    )


class RotuloESerieTest(TestCase):
    def test_rotulo_dia_sem_locale(self):
        self.assertEqual(rotulo_dia("2026-10-14"), "qua 14/10")
        self.assertEqual(rotulo_dia("2026-10-12"), "seg 12/10")

    def test_rotulo_dia_lixo_nao_levanta(self):
        # Lixo nunca atravessa como exceção: cai na fatia honesta.
        self.assertEqual(rotulo_dia(None), "")
        self.assertIsInstance(rotulo_dia("nao-data"), str)

    def test_serie_pula_ausente_sem_mentir_zero(self):
        linhas, ausentes = serie_de(DIAS)
        self.assertEqual(len(linhas), 6)
        self.assertEqual(ausentes, 1)
        self.assertEqual(linhas[0], ["seg 12/10", 12.5])
        for _, mm in linhas:
            self.assertIsInstance(mm, float)

    def test_serie_vazia_sem_dias(self):
        linhas, _ = serie_de([])
        self.assertEqual(linhas, [])


class ChuvaSemanaTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("chuva_ana", password="x")
        self.prop = _prop(user=self.ana)

    def _ok(self, dias=None):
        with mock.patch(
            "app.ia.proativo.obter_previsao",
            return_value={"ok": True, "dias": DIAS if dias is None else dias},
        ):
            from app.ia.intents_chuva import h_chuva_semana

            return h_chuva_semana(self.ana, {}, {"fontes": []})

    def test_sim_com_dias_e_serie(self):
        out = self._ok()
        self.assertTrue(out["ok"])
        self.assertIn("Sim", out["resposta"])
        self.assertIn("3 de 6", out["resposta"])
        self.assertIn("22", out["resposta"])
        self.assertIn("b 17/10", out["resposta"])
        serie = out["dados"]["serie"]
        self.assertEqual(serie["colunas"], ["dia", "mm"])
        self.assertEqual(len(serie["linhas"]), 6)
        self.assertEqual(serie["fonte"], "chuva-semana")
        self.assertEqual(serie["filtros"], {"dias": 7})

    def test_nao_ha_chuva(self):
        secos = [dict(d, mm=0.0, prob=5) for d in DIAS if d["mm"] is not None]
        out = self._ok(secos)
        self.assertTrue(out["ok"])
        self.assertIn("Não há chuva", out["resposta"])

    def test_sem_propriedade(self):
        vazio = User.objects.create_user("chuva_vazio", password="x")
        from app.ia.intents_chuva import h_chuva_semana

        out = h_chuva_semana(vazio, {}, {"fontes": []})
        self.assertFalse(out["ok"])

    def test_sem_fonte_diz_o_motivo(self):
        with mock.patch(
            "app.ia.proativo.obter_previsao",
            return_value={"ok": False, "motivo": "sem coordenada"},
        ):
            from app.ia.intents_chuva import h_chuva_semana

            out = h_chuva_semana(self.ana, {}, {"fontes": []})
        self.assertFalse(out["ok"])
        self.assertIn("sem coordenada", out["erro"])

    def test_intent_no_registo(self):
        from app.ia.registro import REGISTO

        self.assertIn("chuva_semana", REGISTO)
        self.assertIn("chuva_semana", INTENTS_CHUVA)
        spec = INTENTS_CHUVA["chuva_semana"]
        self.assertTrue(spec["descricao"].strip())
        self.assertTrue(spec["exemplos"])
        self.assertIn("clima.read", spec["flags"])


class FonteChuvaSemanaTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("chuva_fonte", password="x")
        self.prop = _prop(user=self.ana)

    def test_calcular_medidos(self):
        from app.ia.chamado_fontes import calcular

        with mock.patch("app.ia.proativo.obter_previsao", return_value=dict(PREV)):
            out = calcular(self.ana, "chuva-semana", filtros={"dias": 7})
        self.assertTrue(out["ok"])
        self.assertEqual(out["colunas"], ["dia", "mm"])
        self.assertEqual(len(out["linhas"]), 6)
        self.assertEqual(out["unidade"], "mm")

    def test_sem_coordenada_linhas_vazias(self):
        from app.ia.chamado_fontes import calcular

        with mock.patch(
            "app.ia.proativo.obter_previsao",
            return_value={"ok": False, "motivo": "sem coordenada"},
        ):
            out = calcular(self.ana, "chuva-semana")
        self.assertTrue(out["ok"])
        self.assertEqual(out["linhas"], [])


class PecaDeSerieTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("chuva_peca", password="x")
        self.prop = _prop(user=self.ana)

    def _serie(self):
        linhas, _ = serie_de(DIAS)
        return {
            "titulo": "Chuva (mm)",
            "rotulo": "mm",
            "colunas": ["dia", "mm"],
            "linhas": linhas,
            "fonte": "chuva-semana",
            "filtros": {"dias": 7},
        }

    def test_serie_valida(self):
        from app.ia.chamado import serie_valida

        ok, motivo = serie_valida(self._serie())
        self.assertTrue(ok, motivo)
        for ruim in [
            None,
            {},
            dict(self._serie(), fonte=""),
            dict(self._serie(), linhas=[]),
            dict(self._serie(), linhas=[["x", float("nan")]]),
            dict(self._serie(), linhas=[[f"d{i}", 1.0] for i in range(40)]),
        ]:
            ok, _ = serie_valida(ruim)
            self.assertFalse(ok)

    def test_peca_tem_texto_grafico_tabela(self):
        from app.ia.chamado import peca_de_serie

        out = peca_de_serie(self._serie(), "Chove.")
        self.assertTrue(out["ok"])
        # Sem `existe`, o `desenha()` do Chamado mostra o estado vazio em vez
        # dos blocos — envelope idêntico ao do compositor da casa.
        self.assertTrue(out["peca"]["existe"])
        tipos = [b["tipo"] for b in out["peca"]["blocos"]]
        self.assertEqual(tipos, ["texto", "grafico", "tabela"])
        grafico = out["peca"]["blocos"][1]
        self.assertEqual(grafico["config"]["tipo_dado"], "barras")
        self.assertEqual(grafico["config"]["fonte"], "chuva-semana")

    def test_aplicar_fontes_mede_de_verdade(self):
        from app.ia import chamado as ch

        with mock.patch("app.ia.proativo.obter_previsao", return_value=dict(PREV)):
            out = ch.peca_de_serie(self._serie(), "Chove.")
            blocos = ch.aplicar_fontes(self.ana, out["peca"]["blocos"])
        grafico = [b for b in blocos if b["tipo"] == "grafico"][0]
        tabela = [b for b in blocos if b["tipo"] == "tabela"][0]
        self.assertEqual(grafico["fonte_dado"], "medido")
        self.assertEqual(len(grafico["config"]["linhas"]), 6)
        self.assertEqual(tabela["fonte_dado"], "medido")

    def test_peca_so_com_painel_ligado(self):
        with mock.patch("app.ia.proativo.obter_previsao", return_value=dict(PREV)):
            sem = executar(self.ana, "chuva_semana", {}, via="sessao", meta={})
            com = executar(
                self.ana,
                "chuva_semana",
                {},
                via="sessao",
                meta={"modos": ["painel"], "entrada": "vai chover essa semana"},
            )
        self.assertTrue(sem["ok"])
        self.assertIn("serie", sem["dados"])
        self.assertNotIn("peca", sem.get("dados", {}))
        self.assertTrue(com["ok"])
        peca = com["dados"]["peca"]
        tipos = [b["tipo"] for b in peca["blocos"]]
        self.assertEqual(tipos, ["texto", "grafico", "tabela"])
        grafico = peca["blocos"][1]
        self.assertEqual(grafico["fonte_dado"], "medido")
        self.assertEqual(len(grafico["config"]["linhas"]), 6)

    def test_modo_chat_nao_poe_peca(self):
        with mock.patch("app.ia.proativo.obter_previsao", return_value=dict(PREV)):
            out = executar(
                self.ana,
                "chuva_semana",
                {},
                via="sessao",
                meta={"modos": ["chat"], "entrada": "vai chover essa semana"},
            )
        self.assertTrue(out["ok"])
        self.assertIn("serie", out["dados"])
        self.assertNotIn("peca", out.get("dados", {}))


class PresetCrudTest(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("crud_ana", password="x")
        self.bob = User.objects.create_user("crud_bob", password="x")
        _prop(user=self.ana)

    def _cria(self, nome="Custo", tipos=("kpi-custo",)):
        from app.ia import palco_presets

        plano = palco_presets.planear(
            self.ana, nome, [{"tipo": t, "titulo": t} for t in tipos]
        )
        self.assertTrue(plano["ok"])
        gravado = palco_presets.gravar(self.ana, plano)
        self.assertTrue(gravado["ok"])
        return gravado

    def test_listar_vazio_e_cheio(self):
        vazio = executar(self.ana, "preset_listar", {}, via="sessao")
        self.assertTrue(vazio["ok"])
        self.assertEqual(vazio["dados"]["presets"], [])
        self._cria("Custo")
        self._cria("Caixa", ("kpi-caixa",))
        cheio = executar(self.ana, "preset_listar", {}, via="sessao")
        nomes = [p["nome"] for p in cheio["dados"]["presets"]]
        self.assertEqual(sorted(nomes), ["Caixa", "Custo"])

    def test_listar_nao_vaza_para_vizinho(self):
        self._cria("Secreto")
        alheio = executar(self.bob, "preset_listar", {}, via="sessao")
        self.assertTrue(alheio["ok"])
        self.assertEqual(alheio["dados"]["presets"], [])

    def test_editar_pede_e_executa(self):
        self._cria("Custo", ("kpi-custo",))
        plano = executar(
            self.ana,
            "preset_editar",
            {"nome": "Custo", "adicionar": ["kpi-caixa"], "remover": []},
            via="sessao",
        )
        self.assertTrue(plano.get("needs_confirm"))
        # Primeira chamada: o gate do sandbox segura com o `prompt_confirmacao`
        # do spec (genérico de propósito — o nome não se interpola ali).
        self.assertIn("mudar", plano["resposta"])
        feito = executar(
            self.ana,
            "preset_editar",
            {
                "nome": "Custo",
                "adicionar": ["kpi-caixa"],
                "remover": [],
                "confirm": True,
            },
            via="sessao",
        )
        self.assertTrue(feito["ok"])
        from app.ia import palco_presets

        atual = palco_presets.listar(self.ana)[0]
        tipos = [w.get("tipo") for w in (atual.estrutura or {}).get("widgets", [])]
        self.assertEqual(sorted(tipos), ["kpi-caixa", "kpi-custo"])

    def test_editar_widget_desconhecido_avisa_e_ignora(self):
        self._cria("Custo", ("kpi-custo",))
        # O aviso do handler só aparece quando ele roda: na chamada confirmada.
        # Desconhecido + válido juntos: avisa o ruim, propõe o bom.
        from app.ia.intents_preset_crud import h_preset_editar

        plano = h_preset_editar(
            self.ana,
            {
                "nome": "Custo",
                "adicionar": ["kpi-caixa", "kpi-inexistente"],
                "remover": [],
            },
            {},
        )
        self.assertTrue(plano.get("needs_confirm"))
        self.assertIn("kpi-inexistente", plano["resposta"])
        self.assertIn("kpi-caixa", plano["resposta"])
        feito = executar(
            self.ana,
            "preset_editar",
            {
                "nome": "Custo",
                "adicionar": ["kpi-caixa", "kpi-inexistente"],
                "remover": [],
                "confirm": True,
            },
            via="sessao",
        )
        # Segunda confirmação: executa só com o válido — o ruim ficou para trás.
        self.assertTrue(feito["ok"])
        from app.ia import palco_presets

        atual = palco_presets.listar(self.ana)[0]
        tipos = [w.get("tipo") for w in (atual.estrutura or {}).get("widgets", [])]
        self.assertEqual(sorted(tipos), ["kpi-caixa", "kpi-custo"])

    def test_editar_preset_alheio_nao_acha(self):
        self._cria("Secreto")
        out = executar(
            self.bob,
            "preset_editar",
            {"nome": "Secreto", "adicionar": ["kpi-caixa"], "confirm": True},
            via="sessao",
        )
        self.assertFalse(out["ok"])

    def test_apagar_pede_e_some(self):
        self._cria("Velho", ("kpi-custo", "kpi-caixa"))
        plano = executar(self.ana, "preset_apagar", {"nome": "Velho"}, via="sessao")
        self.assertTrue(plano.get("needs_confirm"))
        self.assertIn("apagar", plano["resposta"])
        feito = executar(
            self.ana, "preset_apagar", {"nome": "Velho", "confirm": True}, via="sessao"
        )
        self.assertTrue(feito["ok"])
        from app.ia import palco_presets

        self.assertEqual([p.nome for p in palco_presets.listar(self.ana)], [])

    def test_apagar_inexistente_e_honesto(self):
        out = executar(
            self.ana,
            "preset_apagar",
            {"nome": "Fantasma", "confirm": True},
            via="sessao",
        )
        self.assertFalse(out["ok"])
        self.assertIn("achei", out["erro"])

    def test_remover_servico(self):
        from app.ia import palco_presets

        self._cria("Temp", ("kpi-custo",))
        fora = palco_presets.remover(self.ana, "Fantasma")
        self.assertFalse(fora["ok"])
        dentro = palco_presets.remover(self.ana, "Temp")
        self.assertTrue(dentro["ok"])
        self.assertEqual(dentro["widgets"], 1)

    def test_intents_no_registo(self):
        from app.ia.registro import REGISTO

        for nome in ("preset_listar", "preset_editar", "preset_apagar"):
            self.assertIn(nome, REGISTO)
            self.assertTrue(REGISTO[nome]["descricao"].strip())
            self.assertTrue(REGISTO[nome]["handler"])
