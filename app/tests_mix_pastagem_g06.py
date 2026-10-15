"""G-06 MixPastagem — o criterio de saida do plano-correcao.

1. Soma 60+30 passa com `pct_nao_atribuido` = 10 visivel no GET (area nao
   semeada e' informacao, nao erro).
2. Soma 60+50 recusa (impossivel fisico); pct unitario > 100 e negativo
   recusam (Min/Max 0-100).
3. DELETE piquete leva mixes (CASCADE — sem piquete nao ha mix).
4. DELETE cultura com mix da ProtectedError (8o PROTECT, espelhado aqui e
   na cascata).
+ Nenhuma taxa de semeadura gerada pelo sistema (null ate' declarar).
+ Escopo `piquete__propriedade__user`: mix alheio invisivel (404), POST em
  piquete alheio recusado.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from app.models import Cultura, MixPastagem, Piquete, Propriedade


class MixPastagemG06Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor_g06", "g06@x.com", "x")
        self.outro = User.objects.create_user("outro_g06", "outro_g06@x.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda G06", area_total=100
        )
        self.prop_outro = Propriedade.objects.create(
            user=self.outro, nome="Alheia G06", area_total=10
        )
        self.piquete = Piquete.objects.create(
            propriedade=self.prop,
            nome="P-G06",
            area_hectare=12,
            capacidade_ua_ha=3,
        )
        self.piquete_alheio = Piquete.objects.create(
            propriedade=self.prop_outro,
            nome="P-alheio",
            area_hectare=5,
            capacidade_ua_ha=2,
        )
        self.brasiliao = Cultura.objects.create(nome="Braquiaria G06", grupo="pastagens")
        self.estrela = Cultura.objects.create(nome="Estrela G06", grupo="pastagens")
        self.milheto = Cultura.objects.create(nome="Milheto G06", grupo="pastagens")

    def _cli(self, user=None):
        cli = APIClient()
        cli.force_authenticate(user=user or self.user)
        return cli

    def _post(self, piquete, cultura, pct, cli=None):
        return (cli or self._cli()).post(
            "/api/mixes-pastagem/",
            {"piquete": piquete.pk, "cultura": cultura.pk, "pct": pct},
            format="json",
        )

    # --- criterios de saida -------------------------------------------------

    def test_soma_60_30_passa_com_nao_atribuido_10(self):
        r1 = self._post(self.piquete, self.brasiliao, "60.00")
        self.assertEqual(r1.status_code, 201)
        r2 = self._post(self.piquete, self.estrela, "30.00")
        self.assertEqual(r2.status_code, 201)
        # `pct_nao_atribuido` visivel no GET (critério de saida).
        resp = self._cli().get(f"/api/mixes-pastagem/{r2.data['id']}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["pct_nao_atribuido"], "10.00")

    def test_soma_60_50_recusa(self):
        self.assertEqual(self._post(self.piquete, self.brasiliao, "60").status_code, 201)
        resp = self._post(self.piquete, self.estrela, "50")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("pct", resp.data)
        self.assertEqual(
            MixPastagem.objects.filter(piquete=self.piquete).count(), 1
        )

    def test_soma_exato_100_passa_com_zero_nao_atribuido(self):
        self._post(self.piquete, self.brasiliao, "60")
        r2 = self._post(self.piquete, self.estrela, "40")
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.data["pct_nao_atribuido"], "0.00")

    def test_pct_unitario_acima_de_100_e_negativo_recusam(self):
        resp = self._post(self.piquete, self.brasiliao, "100.01")
        self.assertEqual(resp.status_code, 400)
        resp = self._post(self.piquete, self.brasiliao, "-1")
        self.assertEqual(resp.status_code, 400)

    def test_delete_piquete_leva_mixes(self):
        mix = MixPastagem.objects.create(
            piquete=self.piquete, cultura=self.brasiliao, pct=Decimal("60")
        )
        self.piquete.delete()
        self.assertFalse(MixPastagem.objects.filter(pk=mix.pk).exists())

    def test_delete_cultura_com_mix_da_protectederror(self):
        MixPastagem.objects.create(
            piquete=self.piquete, cultura=self.brasiliao, pct=Decimal("60")
        )
        with self.assertRaises(ProtectedError):
            self.brasiliao.delete()

    def test_taxa_e_data_null_ate_declarar(self):
        """Nenhuma taxa gerada pelo sistema: null ate' o produtor dizer."""
        mix = MixPastagem.objects.create(
            piquete=self.piquete, cultura=self.brasiliao, pct=Decimal("60")
        )
        self.assertIsNone(mix.taxa_semeadura_kg_ha)
        self.assertIsNone(mix.data_semeadura)
        self.assertEqual(mix.fonte_dado, "declarado")

    # --- escopo -------------------------------------------------------------

    def test_mix_alheio_invisivel(self):
        mix = MixPastagem.objects.create(
            piquete=self.piquete_alheio, cultura=self.brasiliao, pct=Decimal("60")
        )
        resp = self._cli().get(f"/api/mixes-pastagem/{mix.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_post_em_piquete_alheio_recusado(self):
        resp = self._post(self.piquete_alheio, self.brasiliao, "60")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("piquete", resp.data)

    def test_lista_so_mostra_os_proprios(self):
        MixPastagem.objects.create(
            piquete=self.piquete, cultura=self.brasiliao, pct=Decimal("60")
        )
        MixPastagem.objects.create(
            piquete=self.piquete_alheio, cultura=self.brasiliao, pct=Decimal("60")
        )
        resp = self._cli().get("/api/mixes-pastagem/")
        self.assertEqual(resp.data["count"], 1)
        resp_outro = self._cli(user=self.outro).get("/api/mixes-pastagem/")
        self.assertEqual(resp_outro.data["count"], 1)
