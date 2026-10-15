"""G-02 LoteSemente — o criterio de saida do plano-correcao.

1. Laudo nulo passa (sem_dado honesto); germinacao 0.00 passa (afirmacao
   valida, semente morta); sem `rastro` recusa.
2. DELETE do Rastro leva o LoteSemente; saldo/QR do Rastro inalterados.
3. Escopo: lote de outro produtor e' invisivel (404, nao 403 com dado).
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from app.models import Cultura, Cultivar, Insumo, LoteSemente, Propriedade, RastroItem


class LoteSementeG02Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor_g02", "g02@x.com", "x")
        self.outro = User.objects.create_user("outro_g02", "outro_g02@x.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda G02", area_total=100
        )
        self.prop_outro = Propriedade.objects.create(
            user=self.outro, nome="Alheia G02", area_total=10
        )
        self.cultura = Cultura.objects.create(nome="Soja G02", grupo="graos")
        self.cultivar = Cultivar.objects.create(
            cultura=self.cultura, nome_comercial="TMG G02"
        )
        self.insumo = Insumo.objects.create(
            propriedade=self.prop,
            categoria="SEMENTE",
            nome="Semente G02",
            quantidade=100,
            unidade="sc",
            valor_unitario=100,
        )

    def _rastro(self, prop=None):
        return RastroItem.objects.create(
            propriedade=prop or self.prop,
            insumo=self.insumo,
            numero_lote="L-G02",
            quantidade_recebida=Decimal("100"),
            unidade="sc",
            data_recebimento=date(2026, 1, 10),
        )

    def test_laudo_nulo_passa(self):
        ls = LoteSemente.objects.create(rastro=self._rastro())
        self.assertIsNone(ls.germinacao_pct)
        self.assertEqual(ls.fonte_dado, "declarado")

    def test_germinacao_zero_passa(self):
        ls = LoteSemente.objects.create(
            rastro=self._rastro(), germinacao_pct=Decimal("0.00")
        )
        self.assertEqual(ls.germinacao_pct, Decimal("0.00"))

    def test_sem_rastro_recusa(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            LoteSemente.objects.create(germinacao_pct=Decimal("90"))

    def test_delete_rastro_leva_lote(self):
        r = self._rastro()
        ls = LoteSemente.objects.create(rastro=r, germinacao_pct=Decimal("90"))
        saldo_antes = r.saldo
        r.delete()
        self.assertFalse(LoteSemente.objects.filter(pk=ls.pk).exists())
        self.assertEqual(saldo_antes, Decimal("100"))

    def test_lote_alheio_invisivel(self):
        r_alheio = RastroItem.objects.create(
            propriedade=self.prop_outro,
            insumo=self.insumo,
            numero_lote="L-ALHEIO",
            quantidade_recebida=Decimal("10"),
            unidade="sc",
            data_recebimento=date(2026, 1, 10),
        )
        ls = LoteSemente.objects.create(rastro=r_alheio)
        cli = APIClient()
        cli.force_authenticate(user=self.user)
        resp = cli.get(f"/api/lotes-semente/{ls.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_rastro_traz_lote_aninhado(self):
        r = self._rastro()
        LoteSemente.objects.create(
            rastro=r, cultivar=self.cultivar, germinacao_pct=Decimal("92")
        )
        cli = APIClient()
        cli.force_authenticate(user=self.user)
        resp = cli.get(f"/api/rastros/{r.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["lote_semente"]["germinacao_pct"], "92.00")
        self.assertEqual(
            resp.data["lote_semente"]["cultivar_nome"], "TMG G02"
        )
