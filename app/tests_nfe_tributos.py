"""Os tributos da NF-e, com o ficheiro de teste do próprio projecto.

## Porque este teste usa o fixture e não um XML inventado

Escrevi primeiro um XML sintético para testar a extracção. Depois de o ter
 funcionalmente correcto, parei — porque um XML que eu escrevo verifica o meu
parser contra as minhas suposições, e as suposições podem estar erradas sem
que nada as conteste.

`tests/fixtures/nfe_sample.xml` é uma nota real de venda (CFOP **5101**) com
ICMS, IPI, PIS e COFINS. É o activo mais valioso que havia para isto.

## Os três defeitos que o fixture prova

**1. O sinal invertido, com o fixture do projecto.** CFOP 5101 é venda. Antes
do §23F, isto entrava como `DESPESA`/`INSUMO` e aumentava o estoque.

**2. Os tributos eram deitados fora.** Uma venda de R$ 13.750 com R$ 1.650 de
ICMS entrava no ledger **sem o imposto** — e o produtor comparava o preço de
venda com um custo incompleto sem nunca saber.

**3. O grupo 9906 não existe neste repositório.** Grep Confirmado: o fixture
não tem `IBSCBS`, nem `9906`, nem `CST` de CBS. Por isso os campos da reforma
ficam vazios **e não são preenchidos por inferência** — inventar as tags de um
layout que não tenho é a coisa que fiz quando tentei embuti as alíquotas.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from app.models import (
    EstoqueItem,
    ItemTributario,
    LancamentoFinanceiro,
    Propriedade,
)

FIXTURE = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "nfe_sample.xml"
)


class NfeTributosFixtureTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        Propriedade.objects.create(
            user=self.u,
            nome="Fazenda",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        self.client.force_login(self.u)
        self.xml = FIXTURE.read_bytes()

    def _importa(self):
        return self.client.post(
            "/api/nfe/import/", {"xml": SimpleUploadedFile("nfe.xml", self.xml)}
        )

    def test_o_fixture_é_o_que_digo_que_e(self):
        """Antes de testar o código, confirmo o que o fixture tem.

        Se o fixture mudar — outro CFOP, sem `ICMS00` — este teste falha e diz
        que a Expectations mudou. Testar código contra uma fixture que não é
        a que se pensa é a forma de testar o ficheiro errado.
        """
        texto = FIXTURE.read_text(encoding="utf-8")
        self.assertIn("<CFOP>5101</CFOP>", texto, "o fixture deixou de ser uma venda")
        self.assertIn("<ICMS00>", texto, "o fixture deixou de ter ICMS00")
        self.assertIn("<vICMS>1650.00</vICMS>", texto)

    def test_venda_do_fixture_entra_como_receita(self):
        """CFOP 5101 é venda: receita, e sem mexer no estoque de insumo."""
        r = self._importa()
        self.assertEqual(r.status_code, 200, r.content[:200])

        lanc = LancamentoFinanceiro.objects.filter(descricao__icontains="SOJA").first()
        self.assertIsNotNone(lanc, "o fixture não gerou lançamento")
        self.assertEqual(lanc.tipo, "RECEITA")
        self.assertEqual(lanc.categoria, "VENDA_PROD")
        self.assertEqual(lanc.cfop, "5101")
        self.assertFalse(
            EstoqueItem.objects.filter(nome__icontains="SOJA").exists(),
            "uma venda aumentou o estoque de insumo",
        )

    def test_quantidade_e_unidade_do_fixture(self):
        self._importa()
        lanc = LancamentoFinanceiro.objects.filter(descricao__icontains="SOJA").first()
        self.assertEqual(lanc.quantidade, Decimal("100.0000"))
        self.assertEqual(lanc.unidade, "SC")

    def test_icms_do_fixture_e_importado(self):
        """R$ 1.650 de ICMS deixavam de ser deitados fora."""
        self._importa()

        item = ItemTributario.objects.first()
        self.assertIsNotNone(item, "nenhum item tributário criado")

        self.assertEqual(item.regime, "ICMS_IPI")
        self.assertEqual(item.ncm, "12010010")
        self.assertEqual(item.base_calculo, Decimal("13750.00"))
        self.assertEqual(item.icms_cst, "00")
        self.assertEqual(item.icms_origem, "0")
        self.assertEqual(item.icms_aliquota, Decimal("12.0000"))
        self.assertEqual(item.valor_icms, Decimal("1650.00"))
        self.assertEqual(item.pis_cst, "08")
        self.assertEqual(item.motivo, "")

    def test_os_tributos_somam(self):
        self._importa()
        item = ItemTributario.objects.first()
        # Só o ICMS tem valor no fixture; IPI NT e PIS NT são isentos.
        self.assertEqual(item.total_tributos, Decimal("1650.00"))

    def test_o_grupo_9906_nao_e_inventado(self):
        """A reforma fica vazia — e **diz porquê**.

        O fixture não tem `IBSCBS`. Se alguém preencher `cbs_codigo` por
        inferência, a proxima nota com o grupo real vem e o código mente.
        """
        self._importa()
        item = ItemTributario.objects.first()

        self.assertEqual(item.cbs_codigo, "")
        self.assertEqual(item.ibs_codigo, "")
        self.assertNotEqual(item.regime, "IBS_CBS")

    def test_nota_sem_imposto_e_desconhecido_nao_zero(self):
        """Sem grupo `<imposto>`, o imposto é desconhecido — não zero.

        É a distinção que atravessou toda esta auditoria, agora no último
        sítio onde faltava.
        """
        xml = b"""<?xml version="1.0"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe>
  <ide><dhEmi>2026-03-10T10:00:00-03:00</dhEmi></ide>
  <det><prod><xProd>MILHO</xProd><NCM>10059010</NCM><CFOP>1102</CFOP>
    <uCom>KG</uCom><qCom>1000</qCom><vUnCom>1.50</vUnCom><vProd>1500.00</vProd>
  </prod></det>
</infNFe></NFe></nfeProc>"""

        self.client.post(
            "/api/nfe/import/", {"xml": SimpleUploadedFile("nfe.xml", xml)}
        )

        item = ItemTributario.objects.first()
        self.assertEqual(item.regime, "DESCONHECIDO")
        self.assertIsNone(item.total_tributos, "tributo desconhecido virou zero")
        self.assertIn("desconhecido", item.motivo)
