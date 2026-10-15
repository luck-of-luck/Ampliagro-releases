"""O ecrã do DRE não pode voltar a dizer "R$ 0,00" para o que não foi medido.

## O bug que este ficheiro existe para apanhar

`app/services/dre.py` passou a devolver `deducoes`, `receita_liquida`,
`lucro_bruto`, `resultado_operacional` e `lucro_liquido` como `None`, porque
dependem de uma linha que o sistema não mede.

O template, em `renderRow`, fazia:

```js
${formatCurrency(value)}
```

e `Intl.NumberFormat.prototype.format(null)` **coage `null` para `0`**. O
ecrã passava a mostrar "R$ 0,00" em cinco linhas — exactamente a mentira que
o serviço tinha acabado de remover. O bug ficava invisível: o serviço estava
certo e o ecrã mentia na mesma.

Isto não é um teste de JavaScript. É um teste sobre **o que o ecrã diz**, lido
do template, porque o template é onde a mentira voltava.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

TEMPLATE = Path(__file__).resolve().parent / "templates" / "financeiro" / "dre.html"


class DRETelaHonestaTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = TEMPLATE.read_text(encoding="utf-8")

    def test_renderrow_trata_null_como_nao_medido(self):
        """`renderRow` tem de distinguir `null` de `0` antes de formatar."""
        match = re.search(r"function renderRow\(.*?\n  \}", self.html, re.DOTALL)
        self.assertIsNotNone(match, "renderRow nao encontrado no template")
        corpo = match.group(0)

        self.assertIn(
            "naoMedido",
            corpo,
            "renderRow nao trata null — o formatCurrency(null) volta a "
            "imprimir R$ 0,00",
        )
        # E o `formatCurrency(value)` nu só pode ficar no ramo medido.
        self.assertIn("formatCurrency(value)", corpo)
        self.assertRegex(
            corpo,
            r"naoMedido[\s\S]{0,400}formatCurrency\(value\)",
            "o formatCurrency ficou fora do ramo que exclui null",
        )

    def test_formatcurrency_nao_e_chamado_diretamente_com_null(self):
        """Nenhum `formatCurrency(dre.<linha>)` directo.

        Uma chamada directa assim não passa por `naoMedido` e volta a
        coagir `null` a zero.
        """
        directos = re.findall(r"formatCurrency\(dre\.\w+\)", self.html)
        self.assertEqual(
            directos,
            [],
            f"formatCurrency chamado directamente sobre a linha do DRE: {directos}",
        )

    def test_ecra_avisa_quando_o_dre_e_incompleto(self):
        """Um DRE com `aviso` tem de o mostrar.

        Sem isto, o produtor vê "não medido" em cinco linhas e não sabe
        porque é que o número não está lá.
        """
        self.assertIn("renderAviso", self.html)
        self.assertIn("dre.aviso", self.html)
        match = re.search(r"function renderAviso\(.*?\n  \}", self.html, re.DOTALL)
        self.assertIsNotNone(match, "renderAviso nao encontrado")
        self.assertIn("dre.incompleto", match.group(0))

    def test_renderdre_chama_renderaviso(self):
        """O aviso tem de entrar no HTML, não estar definido e por usar."""
        match = re.search(r"function renderDRE\(.*?\n  \}", self.html, re.DOTALL)
        self.assertIsNotNone(match, "renderDRE nao encontrado")
        self.assertIn(
            "renderAviso(dre)",
            match.group(0),
            "renderDRE nao chama renderAviso — o aviso nunca aparece",
        )
