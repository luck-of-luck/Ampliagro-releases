"""O simulador de lucro não pode inventar custo por hectare.

## O defeito, e porque sobreviveu à §23B

Na §23B tirei `custo_ha = 380` hardcoded de `views/financeiro.py`. **O `380`
continuava no template**, em `simulador-lucro.html`:

```js
custo_ha: parseFloat(t.custo_ha ?? t.custo ?? 380) || 380
```

Isto é pior do que o que tirei da view, por uma razão específica: a
invenção acontecia **na normalização**. O `null` era destruído ali, antes de
`calcLucro` o ver — por isso nenhuma função a jusante podia recuperar a
ausência. Um default que oculta a ausência no primeiro passo torna todos os
passos seguintes incapazes de a ver.

E `|| 10` na área: um talhão de 0 ha virava 10 ha — uma superfície inventada
duas vezes, uma no número e outra no produto.

**Impacto:** o simulador mostrava um lucro calculado sobre um custo que
ninguém mediu, e o produtor decide plantar com esse número.

## O que o teste fixa

1. Não existe `380` como default de custo no template.
2. Não existe `|| 10` como default de área.
3. `formatBRL(null)` devolve "não informado" e **não** "R$ 0,00" — porque
   `Number(null)` é 0.
4. O JS é sintacticamente válido (o `node --check` de `tests_dre_javascript.py`
  cobre o DRE; este cobre o simulador).

Os exemplos `380` que restam no ficheiro **estão correctos**: são o array de
exemplo, rotulado `(exemplo 25ha)`, que existe precisamente para quando não há
talhão cadastrado. Distinguir "exemplo declarado" de "default silencioso" é
parte do que este teste preserva.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from django.test import SimpleTestCase

TPL = Path(__file__).resolve().parent / "templates" / "simulador-lucro.html"


class SimuladorNaoInventaTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = TPL.read_text(encoding="utf-8")

    def _js(self) -> str:
        blocos = re.findall(
            r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", self.html, re.DOTALL
        )
        return "\n".join(b for b in blocos if "{{" not in b and "{%" not in b)

    def _so_codigo(self) -> str:
        """O JS sem comentarios.

        Escrevi a razao das correccoes em comentarios, e um `380` numa
        explicacao nao e o `380` que o browser executa — mas o teste precisa
        de distinguir os dois.
        """
        js = self._js()
        js = re.sub(r"/\*.*?\*/", "", js, flags=re.DOTALL)
        return re.sub(r"//[^\n]*", "", js)

    def test_nao_ha_default_de_380_no_custo(self):
        """`|| 380` e `?? 380` no custo era a mentira."""
        custo = re.search(r"custo_ha\s*:.*", self._so_codigo())
        self.assertIsNotNone(custo, "o mapa custo_ha desapareceu")
        linha = custo.group(0)
        self.assertNotIn("380", linha, f"custo ainda tem 380 como default: {linha}")

    def test_nao_ha_default_de_10_na_area(self):
        area = re.search(r"area_hectare\s*:.*", self._so_codigo())
        self.assertIsNotNone(area)
        linha = area.group(0)
        self.assertNotIn("|| 10", linha, f"area ainda tem 10 ha como default: {linha}")

    def test_formatbrl_diz_nao_informado_em_null(self):
        """`Number(null)` e 0 — sem este guarda, "R$ 0,00" num lucro."""
        m = re.search(r"function formatBRL\(.*?\n  \}", self._so_codigo(), re.DOTALL)
        self.assertIsNotNone(m, "formatBRL nao encontrada")
        corpo = m.group(0)
        self.assertIn("não informado", corpo)
        self.assertIn("null", corpo)

    def test_o_backend_nunca_recebe_um_custo_inventado(self):
        """O pior dos três sítios: `simulacao.py` **calcula** com o número.

        O `base` que vai para `/api/simulacao/` levava
        `parseFloat(t.custo_ha)||380`. O backend recebia 380 e devolvia ponto
        de equilíbrio, Monte Carlo e cenário pessimista calculados sobre um
        custo que ninguém mediu — e o produtor decide plantar com eles.

        A guarda tem de estar **antes** do `simPost`.
        """
        # `_so_codigo()` e nao `_js()`: escrevi a razao da correccao num
        # comentario logo acima da guarda, e um `380` numa explicacao nao e o
        # `380` que o browser executa — mas o teste tem de distinguir os dois.
        m = re.search(
            r"async function calcCenarios\(.*?simPost\(",
            self._so_codigo(),
            re.DOTALL,
        )
        self.assertIsNotNone(m, "calcCenarios nao encontrada")
        corpo = m.group(0)

        self.assertNotIn("380", corpo, "calcCenarios ainda envia 380 ao backend")
        self.assertNotIn(
            "||10",
            corpo.replace(" ", ""),
            "calcCenarios ainda envia 10 ha ao backend",
        )
        self.assertIn(
            "return;",
            corpo,
            "calcCenarios nao aborta quando falta area ou custo",
        )
        self.assertIn(
            "t.custo_ha === null",
            corpo,
            "calcCenarios nao verifica a ausencia de custo por hectare",
        )
        """`calcLucro` tem de devolver `null`, não um número de nada."""
        m = re.search(r"function calcLucro\(.*?\n  \}", self._so_codigo(), re.DOTALL)
        self.assertIsNotNone(m, "calcLucro nao encontrada")
        corpo = m.group(0)
        self.assertNotIn("|| 380", corpo)
        self.assertNotIn("|| 0", corpo, "calcLucro ainda transforma ausencia em zero")

    @unittest.skipUnless(__import__("shutil").which("node"), "node nao instalado")
    def test_o_js_do_simulador_e_valido(self):
        """Sintaxe verificada pelo parser do browser, não por regex."""
        import shutil
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            caminho = Path(d) / "sim.js"
            caminho.write_text(
                "const document={getElementById:()=>({style:{},classList:{add(){},"
                "remove(){}},value:'',textContent:'',innerHTML:''}),"
                "addEventListener(){},querySelectorAll:()=>[]};\n" + self._js(),
                encoding="utf-8",
            )
            r = subprocess.run(
                ["node", "--check", str(caminho)], capture_output=True, text=True
            )
        self.assertEqual(r.returncode, 0, r.stderr[:400])
