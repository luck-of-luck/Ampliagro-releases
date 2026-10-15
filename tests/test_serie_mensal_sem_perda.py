"""O gráfico financeiro não pode perder dinheiro.

O DEFEITO
=========
`financeiro_mensal_agregado` montava o mapa por `r["mes"].month` — o
NÚMERO do mês, sem o ano. Dois Outubros de anos diferentes caíam na mesma
chave de dicionário, e o segundo que a base de dados devolvesse apagava o
primeiro. Não havia aviso, não havia soma: uma linha desaparecia.

Verificado na Fazenda Modelo (Primavera do Leste/MT) com os lançamentos
reais do banco:

    2024-10-05  DESPESA  420.000,00   ← insumo,safra 2024/25
    2026-10-15  RECEITA  850.000,00   ← venda de produção

Ambos caem em "Out". O gráfico devolvia ``Out: receita 850.000, despesa
0,00`` — e a despesa de R$ 420.000 nunca tinha sido paga fora do gráfico.
O produtor via um mês de despesas vazio.

O QUE ESTE TESTE TRAVA
======================
1. Nenhum lançamento desaparece: a soma da série é a soma do banco.
2. A chave inclui o ano, e meses de anos diferentes SOMAM em vez de colidir.
3. A ordem dos rótulos continua Jan..Dez (o contrato do gráfico não mudou).
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.test import TestCase

from app.models import LancamentoFinanceiro, Propriedade
from app.painel_agregado import MESES_PT, financeiro_mensal_agregado

User = get_user_model()


class SerieMensalNaoPerdeDinheiro(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("fin_t", "fin_t@t.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user,
            nome="Fazenda",
            cidade="Primavera do Leste",
            uf="MT",
            area_total=Decimal("1200"),
        )

    def _lancar(self, dia, tipo, valor):
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            data=date.fromisoformat(dia),
            tipo=tipo,
            valor=Decimal(valor),
        )

    def _soma_do_banco(self):
        return LancamentoFinanceiro.objects.filter(propriedade=self.prop).aggregate(
            r=Sum("valor", filter=Q(tipo="RECEITA")),
            d=Sum("valor", filter=Q(tipo="DESPESA")),
        )

    # ───────────────────────────────────────────────────────────────────
    def test_outubro_de_dois_anos_nao_se_apaga(self):
        """O caso real: R$ 420.000 de despesa apagados por R$ 850.000 de receita.

        Este é o teste que impede a regressão. A colisão é invisível numa
        fazenda com um ano só de dados — e foi por isso que passou verde.
        """
        self._lancar("2024-10-05", "DESPESA", "420000.00")
        self._lancar("2025-03-10", "RECEITA", "1850000.00")
        self._lancar("2026-09-12", "RECEITA", "100.00")
        self._lancar("2026-10-15", "RECEITA", "850000.00")

        serie = financeiro_mensal_agregado(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        )
        outubro = [m for m in serie if m["mes"] == "Out"]

        self.assertEqual(
            len(outubro),
            1,
            "os dois Outubros têm de virar UMA linha somada, não duas nem zero",
        )
        self.assertEqual(outubro[0]["receita"], 850000.00)
        self.assertEqual(
            outubro[0]["despesa"],
            420000.00,
            "a despesa de 2024 desapareceu do gráfico. O gráfico dizia "
            "'despesa 0,00' e o produtor via um mês sem despesa.",
        )

    def test_a_serie_soma_exatamente_o_que_o_banco_tem(self):
        """A série mensal não pode divergir do total, em nenhum mês.

        Este é o teste mais largo e o que mais apanha: qualquer colisão, em
        qualquer mês, de qualquer ano, quebra a igualdade. Um teste que
        verifica só Outubro passa se Janeiro colidir e o valor for menor.
        """
        self._lancar("2024-01-10", "DESPESA", "111.11")
        self._lancar("2024-01-20", "RECEITA", "222.22")
        self._lancar("2025-01-05", "DESPESA", "333.33")
        self._lancar("2025-01-15", "RECEITA", "444.44")
        self._lancar("2026-01-01", "DESPESA", "555.55")
        self._lancar("2026-01-31", "RECEITA", "666.66")
        self._lancar("2026-06-15", "DESPESA", "777.77")
        self._lancar("2026-06-20", "RECEITA", "888.88")

        serie = financeiro_mensal_agregado(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        )
        banco = self._soma_do_banco()

        self.assertEqual(
            round(sum(m["receita"] for m in serie), 2),
            float(banco["r"] or 0),
            "a soma das receitas da série não bate com o banco: alguma linha "
            "se perdeu.",
        )
        self.assertEqual(
            round(sum(m["despesa"] for m in serie), 2),
            float(banco["d"] or 0),
            "a soma das despesas da série não bate com o banco: alguma linha "
            "se perdeu.",
        )

    def test_janeiro_acumula_os_tres_anos(self):
        """Três Janeiros viram umsó mês com a soma dos três.

        A soma por mês do CALENDÁRIO é a leitura que o gráfico promete: os
        rótulos são fixos (Jan..Dez) e um mês do calendário é tudo o que
        aconteceu nele, em qualquer ano.
        """
        self._lancar("2024-01-10", "DESPESA", "111.11")
        self._lancar("2025-01-05", "DESPESA", "333.33")
        self._lancar("2026-01-01", "DESPESA", "555.55")

        serie = financeiro_mensal_agregado(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        )
        janeiro = [m for m in serie if m["mes"] == "Jan"]

        self.assertEqual(len(janeiro), 1)
        self.assertEqual(janeiro[0]["despesa"], 1000.0 - 0.01)

    def test_nenhuma_linha_perde_a_despesa_ou_a_receita(self):
        """Nenhum mês pode ter uma de metades a zero quando houve algo.

        A assinatura do defeito era exactamente esta: `despesa: 0.00` num mês
        que tinha despesas. Um mês com uma das metades a zero é legítimo
        (só receita, ou só despesa); um mês com AMBAS a zero nunca entra na
        série.
        """
        self._lancar("2026-02-10", "DESPESA", "1000.00")
        self._lancar("2026-03-10", "RECEITA", "2000.00")

        serie = financeiro_mensal_agregado(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        )
        for m in serie:
            self.assertTrue(
                m["receita"] or m["despesa"],
                f"{m['mes']} entrou na série com receita E despesa a zero — "
                "um mês vazio não entra.",
            )

    def test_a_ordem_dos_meses_continua_sendo_o_calendario(self):
        """O contrato do gráfico não mudou: Jan vem antes de Dez.

        Um mês trocado de lugar é um gráfico que mente calmo — e nada mais
        denuncia. Este teste existe para que a correção da chave não
        reordene a série como efeito colateral.
        """
        self._lancar("2026-01-10", "DESPESA", "1.00")
        self._lancar("2026-06-10", "DESPESA", "1.00")
        self._lancar("2026-12-10", "DESPESA", "1.00")
        self._lancar("2026-03-10", "DESPESA", "1.00")

        serie = financeiro_mensal_agregado(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        )
        self.assertEqual([m["mes"] for m in serie], ["Jan", "Mar", "Jun", "Dez"])

    def test_lancamento_sem_data_nao_entra(self):
        """A série filtra `data` nula, em vez de a somar como um mês.

        `LancamentoFinanceiro.data` é NOT NULL, então o caso não nasce por
        INSERT — mas a proteção existe para quando nasce por importação, por
        `bulk_create` sem validação, ou por uma migração. E o custo de a
        perder é alto: um dia NULL somado ao mês de janeiro é dinheiro que
        aparece onde não foi gasto.
        """
        import inspect

        from app.painel_agregado import financeiro_mensal_agregado as f

        self.assertIn(
            "data__isnull=False",
            inspect.getsource(f),
            "a série deixou de filtrar `data` nula: um dia sem data passaria "
            "a ser contado como um mês do gráfico.",
        )

        self._lancar("2026-05-10", "DESPESA", "50.00")
        serie = financeiro_mensal_agregado(
            LancamentoFinanceiro.objects.filter(propriedade=self.prop)
        )
        self.assertEqual(sum(m["despesa"] for m in serie), 50.0)
