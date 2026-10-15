"""Uma NF-e de venda não pode entrar como despesa. E o preço não pode vir de `float`.

## O que encontrei

`app/views/nfe_auto.py` importa itens de NF-e para estoque + financeiro. Faz
`tipo="DESPESA"`, `categoria="INSUMO"`, `valor=preco * qtd` — e **não olha
para o CFOP uma única vez** (`nfe_auto.py:60-117`).

O CFOP diz o que o documento é. Os que começam por `5` são **saída**: venda de
mercadoria. Os que começam por `1`, `2` ou `3` são **entrada**: compra,
transferência, retorno.

`nfe_auto.py` não distingue. Uma nota de venda de soja a R$ 78.000 entra como
**despesa de insumo** de R$ 78.000. O sinal está invertido, e o erro aparece
no DRE, no lucro e no crédito — como se o produtor tivesse *gasto* 78 mil
vendendo.

Isto não é teórico: o XML de teste que o próprio repo usa
(`app/ia/ingestao/tests.py:37`) traz `<CFOP>5102</CFOP>`, que é venda.

## E o dinheiro em `float`

`qtd` e `preco` são `float(...)` (`nfe_auto.py:80,84`), e `valor=preco * qtd`
vai para um `DecimalField`. `DecimalField` guardaria o valor arredondado, mas
a **soma** de vários items em `float` acumula erro antes de chegar lá. Um
lançamento financeiro é um valor legal: não pode passar por binário.

`estoque.py` e `rastreabilidade.py` já usam `DecimalField`. Aqui o `float` é
um vestígio do parser, que não desculpa.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from app.models import LancamentoFinanceiro, Propriedade


def _xml_nfe(cfop: str, xprod: str, qcom: str, vuncom: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe>
      <ide><nNF>1</nNF><dhEmi>2026-03-10T10:00:00-03:00</dhEmi></ide>
      <det>
        <prod>
          <xProd>{xprod}</xProd>
          <CFOP>{cfop}</CFOP>
          <qCom>{qcom}</qCom>
          <uCom>SC</uCom>
          <vUnCom>{vuncom}</vUnCom>
          <vProd>20000.00</vProd>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>""".encode()


class NfeAutoCfopTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        self.url = "/api/nfe/import/"
        # `nfe_import` é `@login_required` (nfe_auto.py:129) — sem login a
        # resposta é um 302 para o ecrã de entrada, não um 200 de JSON.
        self.client.force_login(self.u)

    def _importa(self, cfop, xprod="SOJA", qcom="100", vuncom="200"):
        return self._post_xml(_xml_nfe(cfop, xprod, qcom, vuncom))

    def _post_xml(self, xml: bytes):
        """A view lê `request.FILES['xml']` (`nfe_auto.py:39,43`), não JSON.

        Um POST com `data=json.dumps(...)` e `content_type="application/json"`
        devolve 400 — e esse 400 é do transporte, não do CFOP.
        """
        return self.client.post(self.url, {"xml": SimpleUploadedFile("nfe.xml", xml)})

    # ------------------------------------------------------------------
    # O sinal
    # ------------------------------------------------------------------

    def test_nfe_de_venda_nao_entra_como_despesa(self):
        """CFOP 5102 é venda. Não pode virar despesa de insumo."""
        r = self._importa("5102", qcom="400", vuncom="150")
        self.assertEqual(r.status_code, 200)

        lanc = LancamentoFinanceiro.objects.filter(propriedade=self.prop).first()
        self.assertIsNotNone(lanc, "nenhum lancamento criado")

        self.assertEqual(
            lanc.tipo,
            "RECEITA",
            f"CFOP 5102 (venda) lancado como {lanc.tipo} — sinal invertido",
        )

    def test_nfe_de_compra_continua_despesa(self):
        """CFOP 1102 (compra) é despesa. A correcção não pode inverter isto."""
        r = self._importa("1102", xprod="FERTILIZANTE", qcom="50", vuncom="1000")
        self.assertEqual(r.status_code, 200)

        lanc = LancamentoFinanceiro.objects.filter(propriedade=self.prop).first()
        self.assertIsNotNone(lanc)
        self.assertEqual(lanc.tipo, "DESPESA")
        self.assertEqual(lanc.categoria, "INSUMO")

    def test_cfop_nao_reconhecido_nao_e_lancado(self):
        """Um CFOP que não sabemos classificar **não entra**.

        Descartar é perdoável — o produtor tem o XML. Inventar o sinal de uma
        venda é irreversível: o lançamento entra no DRE e no lucro.
        """
        r = self._importa("9999", xprod="DESCONHECIDO")
        # A resposta tem de dizer que não importou.
        self.assertEqual(r.status_code, 200)
        corpo = json.loads(r.content)
        self.assertFalse(
            corpo.get("criados"),
            f"CFOP 9999 foi importado: {corpo}",
        )
        self.assertFalse(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop).exists(),
            "CFOP desconhecido gerou lancamento",
        )

    # ------------------------------------------------------------------
    # O dinheiro
    # ------------------------------------------------------------------

    def test_valor_e_decimal_e_nao_float(self):
        """A soma de items não pode passar por binário.

        Com `float`, dois itens de R$ 0,10 somam 0.19999999999999998 em vez
        de 0,20. Numa NF-e com 40 items isso já é um cêntimo errado num
        documento fiscal.
        """
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe>
    <ide><dhEmi>2026-03-10T10:00:00-03:00</dhEmi></ide>
    <det><prod><xProd>A</xProd><CFOP>1102</CFOP><qCom>3</qCom><uCom>UN</uCom>
      <vUnCom>0.10</vUnCom><vProd>0.30</vProd></prod></det>
    <det><prod><xProd>B</xProd><CFOP>1102</CFOP><qCom>3</qCom><uCom>UN</uCom>
      <vUnCom>0.10</vUnCom><vProd>0.30</vProd></prod></det>
  </infNFe></NFe>
</nfeProc>"""

        self._post_xml(xml)

        total = sum(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop).values_list(
                "valor", flat=True
            ),
            Decimal("0"),
        )
        self.assertEqual(
            total,
            Decimal("0.60"),
            f"soma em binario: {total!r} (esperado 0.60 exacto)",
        )

    def test_entrada_nao_cria_estoque_de_venda(self):
        """Uma venda não pode entrar como estoque de insumo.

        Uma NF-e de venda aumenta em 100 sc de soja ao estoque de insumo do
        produtor. A quantidade de soja que ele tem passa a ser falsa.
        """
        from app.models import EstoqueItem

        self._importa("5102", xprod="SOJA", qcom="400", vuncom="150")
        self.assertFalse(
            EstoqueItem.objects.filter(propriedade=self.prop).exists(),
            "venda entrou como insumo em estoque",
        )

    # ------------------------------------------------------------------
    # Integridade do valor — nenhum item entra a R$ 0,00
    # ------------------------------------------------------------------

    def test_item_com_valor_ilegivel_e_recusado(self):
        """Uma quantidade que não se lê não pode virar `0`.

        `_decimo("abc")` devolve `None`, e `None or Decimal("0")` punha
        `qtd = 0`. O lançamento ficava com `valor = preço × 0 = R$ 0,00`, a
        `quantidade` ia `None` por ser falsy, e o item aparecia em
        `criados` como importado.

        **Uma linha de R$ 0,00 numa ledger fiscal é pior que uma linha em
        falta**: a linha em falta avisa o produtor, e a de zero afirma que o
        item vale nada.
        """
        r = self._importa("1102", xprod="FERTILIZANTE", qcom="abc", vuncom="100.00")

        self.assertFalse(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop).exists(),
            "item com quantidade ilegivel foi lancado a 0.00",
        )
        corpo = json.loads(r.content)
        self.assertFalse(corpo.get("criados"), f"item recusado mas criado: {corpo}")
        self.assertTrue(corpo.get("recusados"), "recusa nao foi comunicada")
        self.assertIn("quantidade", corpo["recusados"][0]["motivo"].lower())

    def test_item_com_preco_ilegivel_e_recusado(self):
        r = self._importa("1102", qcom="100", vuncom="--")
        self.assertFalse(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop).exists()
        )
        corpo = json.loads(r.content)
        self.assertTrue(corpo.get("recusados"))

    def test_item_com_quantidade_zero_nao_e_recusado(self):
        """Quantidade zero **legível** é uma medição, não uma ilegibilidade.

        O mesmo `_decimo` devolve `Decimal("0")` num caso e `None` no outro, e
        `or` tratava os dois igual. Distinguir é o ponto: uma nota com 0 sc é
        uma nota com 0 sc, não uma nota que não li.
        """
        self._importa("1102", qcom="0", vuncom="100.00")

        lanc = LancamentoFinanceiro.objects.filter(propriedade=self.prop).first()
        self.assertIsNotNone(lanc, "quantidade zero recusada indevidamente")
        self.assertEqual(lanc.valor, Decimal("0.00"))
        self.assertEqual(lanc.quantidade, Decimal("0"))
