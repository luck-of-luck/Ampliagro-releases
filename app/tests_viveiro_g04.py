"""G-04 Viveiro + LoteMuda — o criterio de saida do plano-correcao.

1. Lote sem datas passa (nenhuma data e' gerada pelo sistema; etapa nula
   ate acontecer — §0.3).
2. Expedicao sem talhao passa (muda expedida antes de plantar e' legítimo;
   talhao_destino e' SET_NULL).
3. DELETE viveiro leva lotes (CASCADE, dado operacional).
4. DELETE cultura com muda vinculada da ProtectedError (7º PROTECT).
+ Cadeia matriz(texto) -> lote -> talhao rastreavel via API.
+ Escopo: viveiro/lote alheio invisivel (404); escrita em propriedade alheia
  recusada (403 no perform_create, padrao rastreabilidade).
"""

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from app.models import Cultura, LoteMuda, Propriedade, Talhao, Viveiro


class ViveiroG04Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor_g04", "g04@x.com", "x")
        self.outro = User.objects.create_user("outro_g04", "outro_g04@x.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda G04", area_total=100
        )
        self.prop_outro = Propriedade.objects.create(
            user=self.outro, nome="Alheia G04", area_total=10
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T-G04", area_hectare=5
        )
        self.talhao_alheio = Talhao.objects.create(
            propriedade=self.prop_outro, nome="T-alheio", area_hectare=2
        )
        self.cultura = Cultura.objects.create(nome="Cafe G04", grupo="perenes")
        self.viveiro = Viveiro.objects.create(
            propriedade=self.prop, nome="Viveiro G04", tipo="estaquia"
        )

    def _cli(self, user=None):
        cli = APIClient()
        cli.force_authenticate(user=user or self.user)
        return cli

    # --- criterios de saida do plano ---------------------------------------

    def test_lote_sem_datas_passa(self):
        lote = LoteMuda.objects.create(
            viveiro=self.viveiro, cultura=self.cultura, origem_matriz="Matriz 7"
        )
        self.assertIsNone(lote.data_repique)
        self.assertIsNone(lote.data_aclimatacao)
        self.assertIsNone(lote.data_expedicao)
        # qtd_expedida comeca em 0 (soma pode ser 0); produzida null = ausencia.
        self.assertEqual(lote.qtd_expedida, 0)
        self.assertIsNone(lote.qtd_produzida)

    def test_expedicao_sem_talhao_passa(self):
        lote = LoteMuda.objects.create(
            viveiro=self.viveiro, qtd_expedida=500, data_expedicao="2026-09-01"
        )
        self.assertIsNone(lote.talhao_destino_id)
        self.assertEqual(lote.qtd_expedida, 500)

    def test_delete_viveiro_leva_lotes(self):
        lote = LoteMuda.objects.create(viveiro=self.viveiro)
        self.viveiro.delete()
        self.assertFalse(LoteMuda.objects.filter(pk=lote.pk).exists())

    def test_delete_cultura_com_muda_da_protectederror(self):
        LoteMuda.objects.create(viveiro=self.viveiro, cultura=self.cultura)
        with self.assertRaises(ProtectedError):
            self.cultura.delete()

    def test_cadeia_matriz_lote_talhao_via_api(self):
        """O critério de saída inteiro: matriz (texto) -> lote -> talhão,
        legível pela API sem nenhuma data inventada."""
        lote = LoteMuda.objects.create(
            viveiro=self.viveiro,
            cultura=self.cultura,
            origem_matriz="Muda-mae 12 (compra Fornecedor X)",
            talhao_destino=self.talhao,
            qtd_produzida=1200,
        )
        resp = self._cli().get(f"/api/lotes-muda/{lote.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["origem_matriz"], "Muda-mae 12 (compra Fornecedor X)")
        self.assertEqual(resp.data["talhao_destino"], self.talhao.pk)
        self.assertEqual(resp.data["viveiro_nome"], "Viveiro G04")
        # Nenhuma data gerada pelo sistema.
        self.assertIsNone(resp.data["data_repique"])
        self.assertIsNone(resp.data["data_aclimatacao"])
        self.assertIsNone(resp.data["data_expedicao"])

    def test_fonte_dado_declarado_por_omissao(self):
        resp = self._cli().post(
            "/api/viveiros/",
            {"propriedade": self.prop.pk, "nome": "Novo Viveiro", "tipo": "in_vitro"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["fonte_dado"], "declarado")

    # --- escopo -------------------------------------------------------------

    def test_viveiro_alheio_invisivel(self):
        alheio = Viveiro.objects.create(
            propriedade=self.prop_outro, nome="Alheio", tipo="in_vitro"
        )
        resp = self._cli().get(f"/api/viveiros/{alheio.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_lote_alheio_invisivel(self):
        alheio = Viveiro.objects.create(
            propriedade=self.prop_outro, nome="Alheio", tipo="in_vitro"
        )
        lote = LoteMuda.objects.create(viveiro=alheio)
        resp = self._cli().get(f"/api/lotes-muda/{lote.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_post_viveiro_em_propriedade_alheia_recusado(self):
        """perform_create (padrão rastreabilidade): 403, sem escrever."""
        resp = self._cli().post(
            "/api/viveiros/",
            {"propriedade": self.prop_outro.pk, "nome": "Invasao", "tipo": "in_vitro"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_lote_em_viveiro_alheio_recusado(self):
        alheio = Viveiro.objects.create(
            propriedade=self.prop_outro, nome="Alheio", tipo="in_vitro"
        )
        resp = self._cli().post(
            "/api/lotes-muda/",
            {"viveiro": alheio.pk, "origem_matriz": "roubada"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_talhao_destino_alheio_recusado(self):
        """Mesmo vector do prescricao alheio: a muda nao liga talhao alheio."""
        resp = self._cli().post(
            "/api/lotes-muda/",
            {"viveiro": self.viveiro.pk, "talhao_destino": self.talhao_alheio.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("talhao_destino", resp.data)

    def test_lote_no_talhao_de_destino_visivel_na_lista(self):
        """Escopo de leitura via viveiro -> propriedade -> user."""
        LoteMuda.objects.create(viveiro=self.viveiro, talhao_destino=self.talhao)
        resp = self._cli().get("/api/lotes-muda/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        resp_outro = self._cli(user=self.outro).get("/api/lotes-muda/")
        self.assertEqual(resp_outro.data["count"], 0)
