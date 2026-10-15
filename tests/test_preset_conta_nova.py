"""Conta nova nasce com UM preset, e cada preset so' mostra o que e' seu.

O QUE PARTIU, MEDIDO
====================
2026-10-14. O dono criou uma conta nova, entrou, e a barra de widgets
mostrou tres botoes: "IA", "Água" e "Tempo". Nenhum dos dois ultimos tinha
sido pedido por ele.

A causa nao era uma so'. Medido nas tres paragens:

    1. SEMEADURA. `_allHardcoded`, em `pagina-index.js`, trazia quatro
       presets de DEMOSTRACAO (plantio/sol/internet/agua) e semeava-os em
       TODA a conta. O `custom-agua` tinha series de arroz e milho de
       2017-2024 — numeros que nenhuma base continha.

    2. FUGIRA DE ESTADO ENTRE CONTAS. `palco-amplia.js` gravava
       `localStorage.setItem('matrix-preset-json-' + slug)` SEM escopo de
       utilizador, e `hydratePresetWidgets()` varria o localStorage a ler
       QUALQUER chave `matrix-preset-json-*`. A conta nova, no mesmo
       browser, acordou com os presets ("Tempo", "Logistica") de quem
       tinha usado a maquina antes. O servidor da conta nova tinha so'
       `base-ia` — a fuga era do lado do cliente.
       (`migrateScopedStorage()` tambem adoptava as chaves sem escopo.)

    3. EMPRESTIMO DE WIDGETS. `clonePresetWidgets(preset)` devolvia
       `custom-agua` quando o preset pedido estava vazio, e o
       `saveCurrentPreset()` a seguir gravava esse emprestimo por cima do
       preset do produtor. O preset passava a ter — e a conservar — os
       widgets de outro.

O QUE ESTE FICHEIRO TRAVA
=========================
1. A semeadura tem UM preset: `base-ia`.
2. Nenhum preset pede widgets a outro (sem fallback para outro nome).
3. Os metadados de preset sao declarados UMA vez.
4. A leitura do localStorage so' ve' as chaves da conta identificada, e a
   escrita passou a usar a chave com escopo.
5. A migracao de storage nao adopta estado de preset sem escopo.
6. O backend conhece os nomes fantasma e limpa-os do estado gravado.
"""

import json
import pathlib
import re
import unittest

from app.presets import (
    PRESET_BASE_IA,
    PRESETS_SISTEMA,
    limpar_presets_bloqueados,
    preset_imutavel,
    preset_permitido,
)

RAIZ = pathlib.Path(__file__).resolve().parents[1]
JS = RAIZ / "app" / "static" / "js" / "pagina-index.js"
PALCO = RAIZ / "app" / "static" / "js" / "ia-local" / "palco-amplia.js"
PRESETS = RAIZ / "app" / "presets.py"

FANTASMAS = ("custom-agua", "custom-tempo", "custom-logistica")


class ContaNovaNasceLimpa(unittest.TestCase):
    """A barra de widgets de quem acabou de criar a conta."""

    @classmethod
    def setUpClass(cls):
        cls.t = JS.read_text(encoding="utf-8")

    def _bloco(self, marcador):
        i = self.t.find(marcador)
        self.assertNotEqual(i, marcador and -1, f"nao encontrei {marcador!r}")
        return self.t[i : i + 400]

    def test_sementeira_tem_um_preset_so(self):
        """`_allHardcoded` declapa UM preset — e' o do produto.

        Qualquer segunda chave aqui e' um preset que nasce em toda a conta,
        que foi o defeito: a conta nova nao pediu "Agua" e acordou com ela.
        """
        i = self.t.find("var _allHardcoded = {")
        self.assertNotEqual(i, -1, "`_allHardcoded` desapareceu")
        fim = self.t.find("\n};", i)
        bloco = self.t[i:fim]
        chaves = re.findall(r"^\s{2}'([\w-]+)':\s*\{", bloco, re.M)
        self.assertEqual(
            chaves,
            ["base-ia"],
            "a sementeira deixou de ter um preset so'. Achados: %s" % chaves,
        )

    def test_nenhum_preset_pede_widgets_a_outro(self):
        """Sem fallback: um preset vazio fica vazio."""
        ajudas = [
            m.group(0)
            for m in re.finditer(r"clonePresetWidgets\('([\w-]+)'\)", self.t)
            if m.group(1) != "base-ia"
        ]
        self.assertEqual(
            ajudas,
            [],
            "ha' preset a pedir widgets a outro preset: %s. E' o emprestimo "
            "que depois fica gravado por cima do preset do produtor." % ajudas,
        )

    def test_metadados_de_preset_declarados_uma_vez(self):
        """`var _presetMeta` existia duas vezes; a segunda ganhava."""
        self.assertEqual(
            self.t.count("var _presetMeta = {"),
            1,
            "`_presetMeta` voltou a ser declarado mais de uma vez — a primeira "
            "declaracao fica morta e mente sobre o que existe.",
        )

    def test_hidratacao_so_le_chaves_da_conta(self):
        """A varredura do localStorage nao pode adoptar preset de outra conta."""
        i = self.t.find("function hydratePresetWidgets")
        corpo = self.t[i : i + 2600]
        self.assertIn("_sufixo", corpo, "a hidratacao nao filtra por conta")
        self.assertIn(
            "bruto.slice(-_sufixo.length) === _sufixo",
            corpo,
            "a hidratacao aceita qualquer chave `matrix-preset-json-*`, "
            'inclusive a de outra conta — foi assim que o "Tempo" apareceu.',
        )

    def test_migracao_nao_adota_preset_sem_escopo(self):
        i = self.t.find("function migrateScopedStorage")
        corpo = self.t[i : i + 1900]
        self.assertIn(
            "matrix-preset-",
            corpo,
            "a migracao deixou de excluir o estado de preset — volta a "
            "adoptar, para a conta que entra, o que estava sem escopo.",
        )

    def test_palco_escreve_com_escopo(self):
        """A IA grava o preset do produtor — na chave da conta dele."""
        t = PALCO.read_text(encoding="utf-8")
        brutos = [
            l.strip() for l in t.splitlines() if "localStorage.setItem('matrix-" in l
        ]
        self.assertEqual(
            brutos,
            [],
            "volta a haver escrita directa em `matrix-*` sem escopo: %s. "
            "Essa chave sem dono e' lida por qualquer conta no browser." % brutos,
        )
        self.assertIn(
            "scopedKey('matrix-preset-json-'",
            t,
            "o preset do palco nao passa pela chave com escopo.",
        )


class BackendConheceOsFantasmas(unittest.TestCase):
    """O estado gravado no servidor tem de ser limpo na leitura e na escrita."""

    def test_fantasmas_nao_sao_permitidos(self):
        for nome in FANTASMAS:
            self.assertFalse(
                preset_permitido(nome),
                "%s passou a ser um preset valido — volta a aparecer na conta "
                "que nunca o pediu." % nome,
            )

    def test_preset_do_produtor_continua_permitido(self):
        self.assertTrue(preset_permitido("custom-pmv8dewtp1svk7b"))
        self.assertTrue(preset_permitido("custom-custo-e-caixa"))

    def test_preset_de_sistema_continua_permitido(self):
        for nome in PRESETS_SISTEMA:
            self.assertTrue(preset_permitido(nome))
        self.assertTrue(preset_imutavel(PRESET_BASE_IA))

    def test_limpeza_tira_os_fantasmas_do_estado(self):
        """O estado medido nas contas de teste do dono."""
        agua = {"cultura-arroz_mercado_produtividade_grafico": {"gridX": 0}}
        state = {
            "layout": agua,
            "active_preset": "custom-tempo",
            "presets_order": [
                "base-ia",
                "custom-tempo",
                "custom-agua",
                "custom-logistica",
            ],
            "presets": {
                "base-ia": {"widget-resumo": {"gridX": 0}},
                "custom-agua": agua,
                "custom-tempo": dict(agua),
                "custom-logistica": dict(agua),
            },
            "presets_meta": {"custom-tempo": {"label": "tempo"}},
        }
        estado, removidos = limpar_presets_bloqueados(state)
        self.assertEqual(
            sorted(estado["presets"]),
            ["base-ia"],
            "a limpeza deixou fantasma no estado: %s" % sorted(estado["presets"]),
        )
        self.assertEqual(estado["presets_order"], ["base-ia"])
        self.assertEqual(
            estado["active_preset"],
            "base-ia",
            "o preset activo apontava para um fantasma e nao caiu num valido",
        )
        self.assertTrue(set(FANTASMAS) <= set(removidos), "faltou declarar remocao")
        self.assertIsNone(estado["presets_meta"].get("custom-tempo"))

    def test_limpeza_preserva_o_que_o_produtor_criou(self):
        state = {
            "presets_order": ["base-ia", "custom-pmv8dewtp1svk7b"],
            "presets": {
                "base-ia": {"widget-resumo": {}},
                "custom-pmv8dewtp1svk7b": {"kpi-caixa": {}},
            },
        }
        estado, removidos = limpar_presets_bloqueados(state)
        self.assertEqual(removidos, [])
        self.assertEqual(
            sorted(estado["presets"]), ["base-ia", "custom-pmv8dewtp1svk7b"]
        )


class FugaEntreContasEstaFechada(unittest.TestCase):
    """O servidor de cada conta so' devolve o que e' dela."""

    def test_estado_de_conta_nova_nao_traz_preset_emprestado(self):
        """Simula o que a view faz com o estado de uma conta nova."""
        state = json.loads('{"presets_order": ["base-ia"], "presets": {"base-ia": {}}}')
        estado, removidos = limpar_presets_bloqueados(state)
        self.assertEqual(list(estado["presets"]), ["base-ia"])
        self.assertEqual(removidos, [])


if __name__ == "__main__":
    unittest.main()
