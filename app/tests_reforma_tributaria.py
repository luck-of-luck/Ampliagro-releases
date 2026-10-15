"""Reforma Tributária: a estrutura sem os números inventados.

## O teste que define o módulo

`test_sem_tabela_oficial_o_imposto_e_none_e_nao_zero`.

Se alguém preencher a base com um `ibs: 0.00` porque "não carregou a
tabela", o produtor vê R$ 0,00 de imposto e pensa que não deve nada. A
verdade é "não sei". São coisas diferentes, e a diferença é um problema
fiscal.

O mesmo teste verifica o inverso: **carregada a tabela com fonte, o imposto
aparece.** Sem isto, o módulo passaria o teste sendo inútil.

## `fonte` obrigatório

`test_aliquota_sem_fonte_nao_e_apuravel` — AliquotaReforma sem `fonte` não
entra no cálculo. Um índice tributário sem dono é pior do que a ausência do
índice: o produtor confia nele.

## Vigência

`test_aliquota_vencida_nao_e_a_de_hoje` — a alíquota de 2026 não vale em
2027. É o motivo de a tabela estar na base e não no código.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    AliquotaReforma,
    LancamentoFinanceiro,
    Propriedade,
)
from app.services.reforma_tributaria import (
    FONTE_TABELA_OFICIAL,
    aliquota_vigente,
    calcular_ibs_cbs,
    itens_sem_classificacao,
)


class ReformaTributariaTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )

    def _carga(
        self,
        aliquota="0.9000",
        fonte=FONTE_TABELA_OFICIAL,
        inicio=date(2026, 1, 1),
        fim=None,
        reducao=None,
    ):
        return AliquotaReforma.objects.create(
            codigo="CBS",
            aliquota=Decimal(aliquota),
            fonte=fonte,
            vigencia_inicio=inicio,
            vigencia_fim=fim,
            reducao_percentual=reducao,
        )

    # ------------------------------------------------------------------
    # O teste que define o módulo
    # ------------------------------------------------------------------

    def test_sem_tabela_oficial_o_imposto_e_none_e_nao_zero(self):
        """Sem a tabela carregada, o imposto é `None` — nunca 0.00.

        R$ 0,00 de imposto diz ao produtor "não deve nada". "Não sei" é
        outra resposta, e é a verdadeira.
        """
        r = calcular_ibs_cbs(Decimal("10000.00"))

        self.assertIsNone(r["cbs"], "imposto inventado como zero")
        self.assertIsNone(r["ibs"])
        self.assertIsNone(r["total"])
        self.assertFalse(r["apuravel"])
        self.assertIn("gov.br/fazenda", r["motivo"])
        self.assertIn("fonte", r["motivo"], "o motivo tem de dizer o que fazer")

    def test_com_tabela_o_imposto_aparece(self):
        """O contra-teste: carregada a tabela com fonte, o imposto existe.

        Sem isto o módulo passaria o teste de honestidade sendo inútil.
        """
        self._carga(aliquota="0.9000", inicio=date(2026, 1, 1))
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte=FONTE_TABELA_OFICIAL,
            vigencia_inicio=date(2026, 1, 1),
        )

        r = calcular_ibs_cbs(Decimal("10000.00"), quando=date(2026, 6, 1))

        self.assertTrue(r["apuravel"])
        self.assertAlmostEqual(r["cbs"], 90.0, places=2)  # 0,9% de 10.000
        self.assertAlmostEqual(r["ibs"], 10.0, places=2)  # 0,1% de 10.000
        self.assertAlmostEqual(r["total"], 100.0, places=2)

    # ------------------------------------------------------------------
    # A fonte é obrigatória
    # ------------------------------------------------------------------

    def test_aliquota_sem_fonte_nao_e_apuravel(self):
        """`fonte` vazia não entra no cálculo."""
        self._carga(aliquota="0.9000", fonte="   ")
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte="",
            vigencia_inicio=date(2026, 1, 1),
        )

        r = calcular_ibs_cbs(Decimal("10000.00"))
        self.assertFalse(r["apuravel"], "aliquota sem fonte foi usada")
        self.assertIsNone(r["cbs"])

    def test_fonte_e_a_que_justifica_o_numero(self):
        """Quem paga precisa de saber de onde saiu a alíquota."""
        self._carga(fonte="LC 214/2025, tabela publicada em 2026-01-05")
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte="LC 214/2025",
            vigencia_inicio=date(2026, 1, 1),
        )
        r = calcular_ibs_cbs(Decimal("100.00"))
        self.assertIn("LC 214", r["aliquotas"]["cbs"]["fonte"])

    # ------------------------------------------------------------------
    # Vigência
    # ------------------------------------------------------------------

    def test_aliquota_vencida_nao_e_a_de_hoje(self):
        """A tabela muda. A de 2026 não vale em 2027."""
        self._carga(aliquota="0.9000", inicio=date(2026, 1, 1), fim=date(2026, 12, 31))
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte=FONTE_TABELA_OFICIAL,
            vigencia_inicio=date(2026, 1, 1),
            vigencia_fim=date(2026, 12, 31),
        )

        r = calcular_ibs_cbs(Decimal("10000.00"), quando=date(2027, 6, 1))

        self.assertFalse(
            r["apuravel"],
            "usou uma alíquota fora da vigência — o imposto mudaria sem ninguem ver",
        )
        self.assertIsNone(r["cbs"])

    def test_vigencia_aberta_ate_hoje(self):
        self._carga(aliquota="0.9000", inicio=date(2026, 1, 1))
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte=FONTE_TABELA_OFICIAL,
            vigencia_inicio=date(2026, 1, 1),
        )
        r = calcular_ibs_cbs(Decimal("10000.00"), quando=date(2030, 1, 1))
        self.assertTrue(r["apuravel"])

    # ------------------------------------------------------------------
    # A base de cálculo
    # ------------------------------------------------------------------

    def test_base_zero_da_imposto_zero_que_e_uma_medicao(self):
        """Zero sobre base zero **é** uma medição, não uma ausência.

        A mesma distinção do DRE: os grupos vazios são 0 porque a soma de um
        conjunto vazio é zero; aqui a ausência é "não tenho a tabela".
        """
        self._carga()
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte=FONTE_TABELA_OFICIAL,
            vigencia_inicio=date(2026, 1, 1),
        )
        r = calcular_ibs_cbs(Decimal("0.00"))
        self.assertTrue(r["apuravel"])
        self.assertEqual(r["total"], 0.0)

    def test_preco_com_imposto_separa_do_preco(self):
        """O imposto entra no preço, não se soma a ele.

        Quem mostra o preço ao consumidor precisa dos dois números, e
        somá-los no mesmo campo perde a informação de qual é qual.
        """
        self._carga()
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte=FONTE_TABELA_OFICIAL,
            vigencia_inicio=date(2026, 1, 1),
        )
        r = calcular_ibs_cbs(Decimal("1000.00"))
        self.assertEqual(r["base_calculo"], 1000.0)
        self.assertEqual(r["total"], 10.0)
        self.assertEqual(r["preco_com_imposto"], 1010.0)

    def test_reducao_agro_nao_e_aplicada_so(self):
        """A redução depende do item, e não a aplicamos sem o item.

        Aplicar uma redução agro a qualquer base seria inventar um benefício
        fiscal. O serviço diz que existe e não a aplica.
        """
        self._carga(aliquota="0.9000", reducao="50.0000")
        AliquotaReforma.objects.create(
            codigo="IBS",
            aliquota=Decimal("0.1000"),
            fonte=FONTE_TABELA_OFICIAL,
            vigencia_inicio=date(2026, 1, 1),
        )
        r = calcular_ibs_cbs(Decimal("10000.00"))

        self.assertIn("redu", r["reducao_agro"].lower())
        self.assertAlmostEqual(r["cbs"], 90.0, places=2)  # 100% da alíquota

    # ------------------------------------------------------------------
    # Os itens que impedem a apuração
    # ------------------------------------------------------------------

    def test_item_sem_classificacao_impede_o_imposto(self):
        """O que não pode ser apurado é a lista do que o produtor tem de resolver."""
        from app.models import ItemTributario

        l1 = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            valor=Decimal("1000.00"),
            data=date(2026, 3, 10),
        )
        l2 = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            valor=Decimal("500.00"),
            data=date(2026, 3, 11),
        )
        ItemTributario.objects.create(
            lancamento=l1,
            descricao="SOJA",
            ncm="12019000",
            regime="IBS_CBS",
            cbs_codigo="000001",
        )
        ItemTributario.objects.create(
            lancamento=l2,
            descricao="MILHO",
            ncm="10059010",
            cbs_codigo="",
        )

        pendentes = itens_sem_classificacao(self.prop.id)
        self.assertEqual(len(pendentes), 1)
        self.assertEqual(pendentes[0]["lancamento_id"], l2.id)
        self.assertIn("não apurável", pendentes[0]["motivo"])
