"""Recomendação com consequência tem de vir de uma medição.

Duas correções, e os testes que as trancam.

1. `h_recomendacao_adubacao` assumia **4 t/ha** quando o produtor não dizia a
   produtividade, e multiplicava pela tabela de extração. Medido: a mesma
   lavoura, sem e com o número, dava 280 kg N/ha e 70 kg N/ha — 4x de
   diferença causada só por o produtor não ter dito. E o carimbo dizia
   `interna:solo`, fazendo a análise de solo parecer responsável por um número
   que ela não mediu.

2. `as_applied_gap` usava `abs(ndvi - 0.65)`: um talhão com NDVI 0,90 — o
   melhor da lavoura — ficava "25 pontos longe do alvo" e recebia a ordem
   "Reaplicar". Não era invenção (o NDVI é medido), era a medida lida ao
   contrário: só a faixa 0,55–0,75 dava "OK".

Regra que estes testes defendem (D1): número sem fonte é `None` + motivo.
Nunca um valor assumido, nunca uma estimativa disfarçada de conta fechada.
"""

from unittest.mock import patch

from django.test import TestCase


class RecomendacaoAdubacaoTest(TestCase):
    """A dose de NPK não pode sair de uma produtividade que ninguém mediu."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        from app.models import AnaliseSolo, Propriedade, Talhao

        self.user = get_user_model().objects.create_user("prod_adub", password="x")
        self.prop = Propriedade.objects.create(user=self.user, nome="FA", area_total=10)
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T1", area_hectare=10
        )
        AnaliseSolo.objects.create(
            talhao=self.talhao,
            data_coleta=timezone.now(),
            ph=5.2,
            ctc=8.0,
            saturacao_bases_v=40.0,
        )

    def _chama(self, params):
        from app.ia.intents3 import h_recomendacao_adubacao

        return h_recomendacao_adubacao(self.user, params, {"fontes": []})

    def test_sem_produtividade_nao_da_dose(self):
        """O defeito: assumia 4 t/ha e dizia o número como se fosse medido."""
        r = self._chama({"cultura": "soja"})
        resposta = r["resposta"]
        self.assertNotIn("kg N", resposta, f"deu dose sem produtividade: {resposta}")

    def test_pergunta_a_produtividade_em_vez_de_adivinhar(self):
        r = self._chama({"cultura": "soja"})
        self.assertIn("pergunta", r, "devia perguntar a produtividade")
        self.assertIn("t/ha", r["pergunta"])

    def test_diz_que_a_dose_muda_com_a_produtividade(self):
        """O produtor tem de perceber PORQUÊ não recebeu número."""
        r = self._chama({"cultura": "soja"})
        self.assertIn("4x", r["resposta"])

    def test_com_produtividade_da_dose(self):
        r = self._chama({"cultura": "soja", "produtividade_t_ha": 3.0})
        # 70 kg N/t x 3.0 = 210
        self.assertIn("210 kg N", r["resposta"])
        self.assertTrue(r["ok"])

    def test_a_dose_escala_com_a_produtividade(self):
        """1 t/ha tem de dar 1/4 da dose de 4 t/ha. Era o que não acontecia."""
        baixo = self._chama({"cultura": "soja", "produtividade_t_ha": 1.0})["resposta"]
        alto = self._chama({"cultura": "soja", "produtividade_t_ha": 4.0})["resposta"]
        self.assertIn("70 kg N", baixo)
        self.assertIn("280 kg N", alto)

    def test_produtividade_zero_ou_negativa_nao_vira_dose(self):
        for valor in (0, -5):
            with self.subTest(valor=valor):
                r = self._chama({"cultura": "soja", "produtividade_t_ha": valor})
                self.assertNotIn("kg N", r["resposta"])

    def test_produtividade_aceita_varios_nomes(self):
        """O produtor diz do jeito dele; o campo não pode ser um só."""
        for chave in ("produtividade_t_ha", "produtividade", "prod_t_ha"):
            with self.subTest(chave=chave):
                r = self._chama({"cultura": "soja", chave: 2.0})
                self.assertIn("140 kg N", r["resposta"])

    def test_a_calagem_continua_a_ser_dada(self):
        """A calagem vem mesmo da análise de solo — não se pode perder isso."""
        r = self._chama({"cultura": "soja"})
        self.assertIn("Calagem", r["resposta"])
        self.assertIn("calcário", r["resposta"])

    def test_a_proveniencia_distingue_solo_de_referencia(self):
        """`interna:solo` sozinho dizia que a análise mediu a dose de NPK."""
        ctx = {"fontes": []}
        from app.ia.intents3 import h_recomendacao_adubacao

        h_recomendacao_adubacao(
            self.user, {"cultura": "soja", "produtividade_t_ha": 3.0}, ctx
        )
        self.assertIn("interna:solo", ctx["fontes"])
        self.assertIn("referencia:extracao_npk", ctx["fontes"])

    def test_a_calagem_dispensada_diz_dispensada(self):
        """V% alta = não precisa de calar. Este caminho já estava certo."""
        from app.models import AnaliseSolo

        AnaliseSolo.objects.filter(talhao=self.talhao).update(saturacao_bases_v=75)
        r = self._chama({"cultura": "soja"})
        self.assertIn("dispensada", r["resposta"])


class GapAplicadoTest(TestCase):
    """`abs()` punia a lavoura mais vigorousa."""

    def _as_applied(self, ndvi_medio):
        from app.services.top_globais import as_applied_gap

        falso = {"ndvi_medio": ndvi_medio, "motivo": None}
        with patch(
            "app.services.ndvi.NDVIService.process_talhao_ndvi", return_value=falso
        ):
            return as_applied_gap(1)

    def test_lavoura_vigorosa_nao_recebe_reaplicar(self):
        """NDVI 0,90 é o melhor estado possível. Dizer "Reaplicar" aqui
        manda o produtor gastar dinheiro em cima de uma lavoura que já está
        no alvo."""
        r = self._as_applied(0.90)
        self.assertEqual(r["acao"], "OK", f"NDVI 0.90 deu {r['acao']}")
        self.assertEqual(r["gap_pct"], 0.0)

    def test_acima_do_alvo_gap_e_zero(self):
        for valor in (0.70, 0.80, 0.90, 0.99):
            with self.subTest(ndvi=valor):
                self.assertEqual(self._as_applied(valor)["gap_pct"], 0.0)

    def test_abaixo_do_alvo_da_reaplicar(self):
        """O caminho que tem de funcionar: falta mesmo, repõe-se."""
        r = self._as_applied(0.50)
        self.assertEqual(r["acao"], "Reaplicar")
        self.assertGreater(r["gap_pct"], 10)

    def test_dentro_da_faixa_da_ok(self):
        for valor in (0.60, 0.65, 0.70):
            with self.subTest(ndvi=valor):
                self.assertEqual(self._as_applied(valor)["acao"], "OK")

    def test_sem_medicao_nao_da_acao(self):
        """O caminho do `None` já estava certo e tem de continuar."""
        from app.services.top_globais import as_applied_gap

        with patch(
            "app.services.ndvi.NDVIService.process_talhao_ndvi",
            return_value={"ndvi_medio": None, "motivo": "sem dado"},
        ):
            r = as_applied_gap(1)
        self.assertIsNone(r["acao"])
        self.assertIsNone(r["gap_pct"])
