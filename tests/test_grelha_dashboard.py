"""A grelha do dashboard: os presets nao podem voltar a pressupor 24 colunas.

O QUE PARTIU, MEDIDO NO DOM
============================
    .matrix-container    --grid-cols: 64    64 colunas de 7,95 px
    kpi-area             gridColumn: 25 / span 8
    largura do widget    120 px        area util 64 px
    rotulo "Área Total"  precisa de 65 px

Cortava por 1 px. E o `gridW: 8` nao era um numero "pequeno demais" — era
um numero escrito para OUTRA grelha.

TRES GRELHAS EM COEXISTENCIA
============================
MEDIDO nos presets (antes da limpa de 2026-10-14, que deixou UM):

    base-ia       gridX+gridW max = 24     grelha de 24 colunas
    (custom-agua, o preset de demo, vivia com max = 40; foi removido)
    GRID_COLS               = 64            grelha de 64 colunas

E a propria fonte diz que ja foi outra vez antes: "(revert 256→64 para
estabilidade)". Ou seja: mudar `GRID_COLS` JA aconteceu, e cada vez levou
a revistar a presenca de cada numero. Nenhum numero revistou.

A CORRECCAO: FRACCOES, NAO COLUNAS
==================================
`col(33.3)` em vez de `gridW: 8`. O preset passa a dizer o que quer dizer
e acompanha qualquer `GRID_COLS` futuro.

O QUE ESTE TESTE TRAVA
======================
1. `GRID_COLS` tem de existir e `col()` tem de o usar — para o proximo
   preset novo nao nascer com um numero absoluto outra vez.
2. Nenhum preset pode ter `gridX + gridW > GRID_COLS` (transborda a linha).
3. Nenhum widget de KPI pode ser mais estreito que o MINIMO LEGIVEL. Um
   KPI com menos de 120 px de area util nao mostra o rotulo E o valor: e'
   a razao de o `kpi-area` cortar por 1 px.
4. A migracao v2 tem de cobrir as DUAS pilhas (undo E redo). Corrigir so
   `undo` deixa o bug a um Ctrl+Shift+Z — a correccao que falha a meio e'
   pior do que nao haver, porque parece arrumada e volta.
5. A migracao v2 tem de ser IDEMPOTENTE: verificado no browser, 3 arranques
   seguidos nao podem duplicar. Por isso a flag e' sua.
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
JS = RAIZ / "app" / "static" / "js" / "pagina-index.js"

# o minimo para o rotulo + o valor caberem. MEDIDO: o rotulo "Área Total"
# precisa de 65 px; com `break-words` o rotulo quebra, mas o numero nao
# deve. Abaixo disto o cartao e' um bloco sem informacao.
MIN_UTIL_PX = 120
# 1037 px era a largura medida da contentora com 64 colunas de 7,95
LARGURA_MEDIDA = 1037


class GrelhaTest(unittest.TestCase):
    def setUp(self):
        self.t = JS.read_text(encoding="utf-8")

    def grid_cols(self):
        m = re.search(r"const GRID_COLS = (\d+);", self.t)
        self.assertIsNotNone(m, "nao encontrei `const GRID_COLS`")
        return int(m.group(1))

    # ------------------------------------------------------------------
    # 1) A FUNCAO col() EXISTE E USA O GRID_COLS
    # ------------------------------------------------------------------
    def test_afuncao_col_usa_o_grid_cols(self):
        self.assertRegex(
            self.t,
            r"function col\(percent\)\s*\{\s*return Math\.round\(\(GRID_COLS \* percent\) / 100\);",
            "a funcao `col(percent)` nao deriva de `GRID_COLS`. Sem isso, "
            "volta a ser um numero solto — que e' como o problema nasceu.",
        )

    def test_o_preset_base_ia_usa_fraccoes(self):
        """O preset que renderiza por omissao nao pode ter numeros soltos."""
        i = self.t.find("'base-ia':")
        self.assertNotEqual(i, -1, "nao encontrei o preset base-ia")
        bloco = self.t[i : self.t.find("},", i) + 2]
        # todo gridW tem de ser col(...)
        gws = re.findall(r"gridW:\s*([^,}]+)", bloco)
        for g in gws:
            self.assertRegex(
                g.strip(),
                r"^col\(",
                "`base-ia` tem gridW: %s — um numero absoluto. Era o "
                "`gridW: 8` que dava 120 px numa grelha de 64." % g.strip(),
            )
        gxs = re.findall(r"gridX:\s*([^,}]+)", bloco)
        for g in gxs:
            self.assertRegex(
                g.strip(),
                r"^col\(",
                "`base-ia` tem gridX: %s — um numero absoluto." % g.strip(),
            )

    # ------------------------------------------------------------------
    # 2) NADA TRANSBORDA A LINHA
    # ------------------------------------------------------------------
    def _fraccoes_do_base_ia(self):
        cols = self.grid_cols()
        i = self.t.find("'base-ia':")
        bloco = self.t[i : self.t.find("},", i) + 2]
        out = []
        for m in re.finditer(
            r"'([\w-]+)':\s*\{\s*gridX:\s*col\(([\d.]+)\),\s*gridY:\s*(\d+),\s*"
            r"gridW:\s*col\(([\d.]+)\),\s*gridH:\s*(\d+)",
            bloco,
        ):
            out.append(
                {
                    "id": m.group(1),
                    "x": round(cols * float(m.group(2)) / 100),
                    "w": round(cols * float(m.group(4)) / 100),
                    "y": int(m.group(3)),
                    "h": int(m.group(5)),
                }
            )
        return cols, out

    def test_nenhum_widget_transborda_a_linha(self):
        cols, widgets = self._fraccoes_do_base_ia()
        self.assertTrue(widgets, "nao extrai nenhum widget de base-ia")
        for w in widgets:
            self.assertLessEqual(
                w["x"] + w["w"],
                cols,
                "`%s` acaba em %d colunas e GRID_COLS e' %d — transborda a "
                "linha da grelha." % (w["id"], w["x"] + w["w"], cols),
            )

    def test_nenhum_widget_abaixo_do_minimo_legivel(self):
        """Um KPI com menos de 120 px nao mostra rotulo nem valor.

        MEDIDO: `kpi-area` tinha 118 px uteis e o rotulo "Área Total" precisa
        de 65 px — so na horizontal. A 120 px o cartao tem sitio para as
        duas linhas; abaixo disso o numero, que e' o que se le, e' o que
        desaparece.
        """
        cols, widgets = self._fraccoes_do_base_ia()
        px_por_col = (LARGURA_MEDIDA - 24) / cols  # padding medido de 12+12
        for w in widgets:
            if not w["id"].startswith("kpi-"):
                continue
            util = w["w"] * px_por_col
            self.assertGreaterEqual(
                util,
                MIN_UTIL_PX,
                "`%s` ficaria com %.0f px uteis (minimo %d). O `kpi-area` "
                "ficou com 118 e o rotulo cortava." % (w["id"], util, MIN_UTIL_PX),
            )

    # ------------------------------------------------------------------
    # 3) A MIGRACAO V2
    # ------------------------------------------------------------------
    def test_a_migracao_v2_cobre_as_duas_pilhas(self):
        i = self.t.find("ampliagro-grid-scaled-v2-historico")
        self.assertNotEqual(
            i,
            -1,
            "nao encontrei a migracao v2 — o historico volta a repor a "
            "geometria antiga a cada Ctrl+Z",
        )
        bloco = self.t[i : i + 1600]
        self.assertIn(
            "matrix-layout-history-undo",
            bloco,
            "a migracao v2 nao toca na pilha de `undo`",
        )
        self.assertIn(
            "matrix-layout-history-redo",
            bloco,
            "a migracao v2 nao toca na pilha de `redo`. Corrigir so `undo` "
            "deixa o bug a um Ctrl+Shift+Z — a correccao que falha a meio e' "
            "pior do que nao haver: parece arrumada e volta.",
        )

    def test_a_migracao_v2_tem_a_sua_propria_flag(self):
        """Reusar a flag v1 obrigaria a duplicar o layout de quem ja migrou.

        O dobro de 32 da 64 — a largura toda, para todos os widgets. Cada
        versao de migracao fica com a sua flag, e verificado no browser:
        3 arranques seguidos nao mudam nada.
        """
        self.assertIn(
            "ampliagro-grid-scaled-v2-historico",
            self.t,
            "a migracao v2 precisa de uma flag propria",
        )
        i = self.t.find("ampliagro-grid-scaled-v2-historico")
        bloco = self.t[max(0, i - 120) : i + 1600]
        # o bloco v2 nao deve escrever a flag v1
        self.assertNotIn(
            "setItem('ampliagro-grid-scaled-v1'",
            bloco,
            "o bloco v2 esta a escrever a flag da v1. Quem ja tinha migrado "
            "voltaria a correr o v2 E a v1 no mesmo arranque.",
        )


if __name__ == "__main__":
    unittest.main()
