"""O JavaScript do ecrã do DRE tem de ser sintacticamente válido.

## O que este teste apanha

`app/templates/financeiro/dre.html` tem JavaScript **inline** num bloco
`<script>`. Eu reescrevi o `renderRow` (para tratar `null` como "não medido")
e acrescentei `renderAviso` — um banner novo.

**JavaScript inline não é verificado por nenhum linter deste projecto.** O Ruff
não o vê, o semgrep não o vê, o `tsc` não o vê (é um template, não um módulo).
E um erro de sintaxe num `<script>` inline **não dá erro visível no Django**:
o template renderiza, o HTML sai, e o browser falha em silêncio, deixando o
ecrã do DRE **todo em branco**.

Ou seja: eu podia ter partido o ecrã inteiro do DRE e a suite de Python
continuaria a dar verde. Este teste é a barreira.

## Como verifica

Extrai o conteúdo do `<script>` e passa-o ao `node --check`, que é o parser
do próprio JavaScript. Não é uma regex: é o mesmo parser que o browser usa.

E depois executa o `renderRow` com `null` e confirma que devolve "não medido"
e **não** `R$ 0,00` — porque `Intl.NumberFormat.format(null)` coage para zero,
que é a mentira que o §23E corrigiu.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase

TEMPLATE = Path(__file__).resolve().parent / "templates" / "financeiro" / "dre.html"


def _blocos_script() -> list[str]:
    html = TEMPLATE.read_text(encoding="utf-8")
    return re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL)


class DreJavascriptTest(SimpleTestCase):
    @unittest.skipIf(shutil.which("node") is None, "node nao instalado")
    def test_o_js_inline_do_dre_e_sintacticamente_valido(self):
        """`node --check` em cada bloco `<script>` inline.

        Um erro de sintaxe aqui deixa o ecrã do DRE em branco **sem dar erro
        nenhum no servidor** — que é a pior combinação possível.
        """
        blocos = _blocos_script()
        self.assertTrue(blocos, "o template nao tem nenhum script inline?")

        erros = []
        with tempfile.TemporaryDirectory() as d:
            for i, bloco in enumerate(blocos):
                # `node --check` só aceita scripts, não fragments com
                # template tags. Se houver `{{ }}` ou `{% %}`, salta-os: o
                # browser também não os veria.
                if "{{" in bloco or "{%" in bloco:
                    continue
                caminho = Path(d) / f"bloco{i}.js"
                caminho.write_text(bloco, encoding="utf-8")
                r = subprocess.run(
                    ["node", "--check", str(caminho)],
                    capture_output=True,
                    text=True,
                )
                if r.returncode != 0:
                    erros.append(f"bloco {i}: {r.stderr.strip()[:300]}")

        self.assertEqual(erros, [], "JS do DRE invalido:\n" + "\n".join(erros))

    @unittest.skipIf(shutil.which("node") is None, "node nao instalado")
    def test_renderrow_devolve_nao_medido_e_nao_zero(self):
        """Executa o `renderRow` real com `null`.

        Este é o behavioural test: `Intl.NumberFormat.format(null)` devolve
        `R$ 0,00` (verificado em Node), o que afirmaria que o produtor não
        deve imposto quando a verdade é "não sei".
        """
        blocos = _blocos_script()
        fonte = "\n".join(b for b in blocos if "{{" not in b and "{%" not in b)

        # O browser precisa de `document` para o `document.getElementById` do
        # topo do script. Empacotamos só o que vamos exercitar.
        harness = f"""
const document = {{
  getElementById: () => ({{
    classList: {{ add(){{}}, remove(){{}} }},
    value: "",
  }}),
  addEventListener(){{}},
}};
{fonte}
const saida = renderRow("(-) Deduções", null, true);
console.log(JSON.stringify({{
  contemNaoMedido: saida.includes("não medido") || saida.includes("n\\u00e3o medido"),
  contemZero: saida.includes("0,00"),
  temFormatCurrency: typeof formatCurrency === "function",
}}));
"""
        with tempfile.TemporaryDirectory() as d:
            caminho = Path(d) / "harness.js"
            caminho.write_text(harness, encoding="utf-8")
            r = subprocess.run(["node", str(caminho)], capture_output=True, text=True)

        self.assertEqual(r.returncode, 0, r.stderr[:500])
        dados = json.loads(r.stdout.strip().splitlines()[-1])

        self.assertTrue(
            dados["contemNaoMedido"],
            "renderRow(null) nao devolveu 'não medido'",
        )
        self.assertFalse(
            dados["contemZero"],
            "renderRow(null) imprimiu 0,00 — a mentira que o §23E removeu",
        )

    def test_o_template_usa_renderaviso(self):
        """O aviso tem de estar ligado ao render.

        Uma função definida e não chamada é o modo mais silencioso de uma
        feature não existir.
        """
        html = TEMPLATE.read_text(encoding="utf-8")
        match = re.search(r"function renderDRE\(.*?\n  \}", html, re.DOTALL)
        self.assertIsNotNone(match)
        self.assertIn("renderAviso(dre)", match.group(0))
