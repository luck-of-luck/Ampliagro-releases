"""O saldo de rastreabilidade tem de ser uma subtracção, não um zero.

MEDIDO 2026-10-05. O defeito
----------------------------
`RastroItemViewSet.alertas_ruptura` somava, num único
`.values("insumo_id").annotate(...)`:

    Sum("quantidade_recebida")
  - Sum("movimentos__quantidade", filter=Q(movimentos__tipo="SAIDA"))
  + Sum("movimentos__quantidade", filter=Q(movimentos__tipo="AJUSTE"))

Dois defeitos ao mesmo tempo, e o segundo escondia o primeiro.

**1. `quantidade_recebida` sai multiplicada.** A soma dos movimentos obriga a
JUNTAR a tabela de movimentos, e cada linha de movimento duplica a linha do
RastroItem. O erro cresce com o numero de movimentos — que e' o que cresce
quando o produtor usa o rastreio, que e' a razao de o rastreio existir.

**2. O `Coalesce` tapava tudo com `0`.** E' o que fazia o preco de (1) ser
invisivel. `Sum(..., filter=Q(movimentos__tipo="AJUSTE"))` devolve `NULL`
quando nao ha ajustes — e ajustes sao raros. Em SQL, `100 - 30 + NULL` e'
`NULL`, e `Coalesce(..., 0)` transforma isso em **ZERO**.

MEDIDO por execucao (nao por leitura): com 100 recebidas e 3 saidas de 10,

    formula antiga:  saldo_total = 0        <- NAO era 270, era 0
    formula nova:    saldo_total = 70

Consequencia: `0 < estoque_minimo` e' verdade quase sempre, portanto
`/api/rastros/alertas_ruptura/` reportava **todos** os insumos como ruptura,
com o deficit inteiro. O alerta que existe para avisar antes da compra
disparava sempre, e por isso deixou de ser lido — o que e' pior do que
nunca ter existido.

Porquê este número
-----------------
100 recebidas, 3 saidas de 10. O `saldo_total` e' o discriminador: a formula
antiga devolve 0 e a nova devolve 70. Afirmar o numero e' mais forte do que
afirmar que o alerta aparece — um alerta que aparece por acidente nao prova
nada sobre o saldo.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import Insumo, MovimentoEstoque, Propriedade, RastroItem


class SaldoSemFanOutTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("rastro", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Faz Rastro", area_total=10, uf="MT", cidade="X"
        )
        self.insumo = Insumo.objects.create(
            propriedade=self.prop,
            nome="Ureia",
            categoria="INSUMO",
            unidade="kg",
            quantidade=Decimal("0"),
            valor_unitario=Decimal("0"),
            # O minimo e' alto de proposito: o endpoint so devolve insumos
            # ABAIXO do minimo, entao com um minimo baixo um saldo correcto
            # desaparecia da resposta e o teste deixava de poder medir o
            # numero. Assim o alerta dispara sempre e o que se afirma e'
            # sempre o `saldo_total` — o discriminador, nao a existencia.
            estoque_minimo=Decimal("1000"),
        )
        self.client.force_login(self.u)

    def _lote(self, recebida):
        return RastroItem.objects.create(
            propriedade=self.prop,
            insumo=self.insumo,
            numero_lote="L1",
            numero_serie="S1",
            nf_entrada="NF1",
            quantidade_recebida=Decimal(recebida),
            unidade="kg",
            data_recebimento=date(2026, 1, 1),
        )

    def _saidas(self, lote, quantas, cada):
        for _ in range(quantas):
            MovimentoEstoque.objects.create(
                rastro_item=lote,
                tipo="SAIDA",
                quantidade=Decimal(cada),
            )

    def _saldo(self):
        r = self.client.get("/api/rastros/alertas_ruptura/")
        self.assertEqual(r.status_code, 200)
        alertas = r.json()["alertas"]
        self.assertEqual(len(alertas), 1, f"esperava 1 alerta: {r.json()}")
        return alertas[0]

    def test_tres_saidas_nao_multiplicam_o_recebido(self):
        lote = self._lote("100")
        self._saidas(lote, 3, "10")
        # 100 - 3x10 = 70. Com fan-out daria 300 - 30 = 270, e o alerta de
        # ruptura NUNCA dispararia: era isso que se perdia — nao um algarismo
        # feio, mas o aviso que devia ter chegado antes da compra.
        self.assertEqual(self._saldo()["saldo_total"], 70.0)

    def test_um_lote_sem_movimentos_da_o_recebido(self):
        self._lote("100")
        a = self._saldo()
        self.assertEqual(a["saldo_total"], 100.0)
        self.assertEqual(a["deficit"], 900.0)

    def test_ajuste_soma(self):
        # A semântica de negócio fica a mesma: subtrai SAIDA, soma AJUSTE.
        lote = self._lote("100")
        self._saidas(lote, 2, "10")
        MovimentoEstoque.objects.create(
            rastro_item=lote, tipo="AJUSTE", quantidade=Decimal("5")
        )
        a = self._saldo()
        self.assertEqual(a["saldo_total"], 85.0)

    def test_o_erro_crescia_com_o_numero_de_movimentos(self):
        """O que torna o defeito grave: o erro era proporcional ao uso.

        Com 1 movimento o saldobate certo — e por isso passava despercebido.
        Este teste fixa essa growth: 6 saidas tem de dar 100-60=40, nao 600-60.
        """
        lote = self._lote("100")
        self._saidas(lote, 6, "10")
        a = self._saldo()
        self.assertEqual(a["saldo_total"], 40.0)

    def test_entrada_nao_e_subtraida(self):
        # ENTRADA e TRANSF ficaram fora antes e continuam fora. Isto fixa a
        # semântica para que ninguem a mude sem querer ao mexer na aritmética.
        lote = self._lote("100")
        MovimentoEstoque.objects.create(
            rastro_item=lote, tipo="ENTRADA", quantidade=Decimal("999")
        )
        a = self._saldo()
        self.assertEqual(a["saldo_total"], 100.0)
