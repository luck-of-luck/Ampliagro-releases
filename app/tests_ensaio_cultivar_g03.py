"""G-03 EnsaioCultivar — o criterio de saida do plano-correcao.

1. Ensaio sem faixas passa (cria e responde; ranking e' lista vazia, nao erro).
2. Ranking sem testemunha -> delta None (sem_dado honesto; sem inventar vencedor);
   com testemunha -> delta 0 na base e positivo na melhor.
3. `uid` repetido nao duplica (POST idempotente, mesmo contrato offline do
   ExperimentoViewSet).
4. Escopo: ensaio/faixa de outro produtor e' invisivel (404, nao 403 com dado).
+ Funcao pura `ranking_ensaio` sem BD: media ignora None, None vai por ultimo.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from app.models import Cultura, Cultivar, EnsaioCultivar, FaixaEnsaio, Propriedade
from app.services.ensaio import ranking_ensaio


class RankingPuroG03Test(SimpleTestCase):
    """Sem BD de proposito: a aritmetica do ranking nao precisa de banco."""

    def test_media_ignora_none_e_none_vai_por_ultimo(self):
        linhas = ranking_ensaio(
            [
                {"cultivar_id": 1, "produtividade_sc_ha": 50.0},
                {"cultivar_id": 1, "produtividade_sc_ha": None},
                {"cultivar_id": 2, "produtividade_sc_ha": None},
                {"cultivar_id": 3, "produtividade_sc_ha": 70.0},
            ]
        )
        self.assertEqual([l["cultivar_id"] for l in linhas], [3, 1, 2])
        self.assertEqual(linhas[1]["media_sc_ha"], 50.0)
        self.assertIsNone(linhas[2]["media_sc_ha"])

    def test_sem_testemunha_delta_none(self):
        linhas = ranking_ensaio(
            [{"cultivar_id": 1, "produtividade_sc_ha": 50.0}],
            testemunha_id=None,
        )
        self.assertIsNone(linhas[0]["delta_pct"])

    def test_testemunha_zero_na_base(self):
        linhas = ranking_ensaio(
            [
                {"cultivar_id": 7, "produtividade_sc_ha": 40.0},
                {"cultivar_id": 8, "produtividade_sc_ha": 50.0},
            ],
            testemunha_id=7,
        )
        por_id = {l["cultivar_id"]: l for l in linhas}
        self.assertEqual(por_id[7]["delta_pct"], 0.0)
        self.assertEqual(por_id[8]["delta_pct"], 25.0)

    def test_testemunha_sem_dado_delta_none(self):
        """Base sem medicao -> nenhum delta e' calculado (nao inventa 0)."""
        linhas = ranking_ensaio(
            [
                {"cultivar_id": 7, "produtividade_sc_ha": None},
                {"cultivar_id": 8, "produtividade_sc_ha": 50.0},
            ],
            testemunha_id=7,
        )
        for linha in linhas:
            self.assertIsNone(linha["delta_pct"])


class EnsaioCultivarG03Test(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor_g03", "g03@x.com", "x")
        self.outro = User.objects.create_user("outro_g03", "outro_g03@x.com", "x")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda G03", area_total=100
        )
        self.prop_outro = Propriedade.objects.create(
            user=self.outro, nome="Alheia G03", area_total=10
        )
        self.cultura = Cultura.objects.create(nome="Milho G03", grupo="graos")
        self.testemunha = Cultivar.objects.create(
            cultura=self.cultura, nome_comercial="Testemunha G03"
        )
        self.cultivar = Cultivar.objects.create(
            cultura=self.cultura, nome_comercial="BRS G03"
        )

    def _cli(self, user=None):
        cli = APIClient()
        cli.force_authenticate(user=user or self.user)
        return cli


    def test_ensaio_sem_faixas_passa(self):
        resp = self._cli().post(
            "/api/ensaios-cultivar/",
            {"uid": "ensaio-g03-vazio", "nome": "Sem faixas ainda"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        rank = self._cli().get(f"/api/ensaios-cultivar/{resp.data['id']}/ranking/")
        self.assertEqual(rank.status_code, 200)
        self.assertEqual(rank.data["ranking"], [])
        # Regra de escrita: fonte_dado declarado por omissao.
        self.assertEqual(resp.data["fonte_dado"], "declarado")

    def test_ranking_sem_testemunha_delta_none(self):
        ensaio = EnsaioCultivar.objects.create(
            user=self.user, propriedade=self.prop, nome="Sem testemunha"
        )
        FaixaEnsaio.objects.create(
            ensaio=ensaio, cultivar=self.cultivar, produtividade_sc_ha=Decimal("55")
        )
        resp = self._cli().get(f"/api/ensaios-cultivar/{ensaio.pk}/ranking/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["ranking"]), 1)
        self.assertEqual(resp.data["ranking"][0]["media_sc_ha"], 55.0)
        self.assertIsNone(resp.data["ranking"][0]["delta_pct"])
        self.assertEqual(resp.data["fonte_dado"], "declarado")

    def test_ranking_com_testemunha_calcula_delta(self):
        ensaio = EnsaioCultivar.objects.create(
            user=self.user, propriedade=self.prop, testemunha=self.testemunha
        )
        FaixaEnsaio.objects.create(
            ensaio=ensaio, cultivar=self.testemunha, produtividade_sc_ha=Decimal("40")
        )
        FaixaEnsaio.objects.create(
            ensaio=ensaio, cultivar=self.cultivar, produtividade_sc_ha=Decimal("50")
        )
        resp = self._cli().get(f"/api/ensaios-cultivar/{ensaio.pk}/ranking/")
        por_id = {l["cultivar_id"]: l for l in resp.data["ranking"]}
        self.assertEqual(por_id[self.testemunha.pk]["delta_pct"], 0.0)
        self.assertEqual(por_id[self.cultivar.pk]["delta_pct"], 25.0)
        # Ordem: melhor media primeiro.
        self.assertEqual(resp.data["ranking"][0]["cultivar_id"], self.cultivar.pk)

    def test_uid_repetido_nao_duplica(self):
        cli = self._cli()
        payload = {"uid": "ensaio-g03-offline", "nome": "Reenvio do aparelho"}
        r1 = cli.post("/api/ensaios-cultivar/", payload, format="json")
        self.assertEqual(r1.status_code, 201)
        r2 = cli.post("/api/ensaios-cultivar/", payload, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(
            EnsaioCultivar.objects.filter(uid="ensaio-g03-offline").count(), 1
        )

    def test_ensaio_alheio_invisivel(self):
        alheio = EnsaioCultivar.objects.create(
            user=self.outro, propriedade=self.prop_outro, nome="Alheio G03"
        )
        cli = self._cli()
        self.assertEqual(cli.get(f"/api/ensaios-cultivar/{alheio.pk}/").status_code, 404)
        self.assertEqual(
            cli.get(f"/api/ensaios-cultivar/{alheio.pk}/ranking/").status_code, 404
        )

    def test_faixa_alheia_invisivel(self):
        ensaio_alheio = EnsaioCultivar.objects.create(
            user=self.outro, propriedade=self.prop_outro
        )
        faixa = FaixaEnsaio.objects.create(ensaio=ensaio_alheio, cultivar=self.cultivar)
        self.assertEqual(
            self._cli().get(f"/api/faixas-ensaio/{faixa.pk}/").status_code, 404
        )

    def test_faixa_em_ensaio_alheio_recusada(self):
        ensaio_alheio = EnsaioCultivar.objects.create(
            user=self.outro, propriedade=self.prop_outro
        )
        resp = self._cli().post(
            "/api/faixas-ensaio/",
            {"ensaio": ensaio_alheio.pk, "cultivar": self.cultivar.pk},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ensaio", resp.data)

    def test_faixa_duplicada_na_mesma_repeticao_recusada(self):
        from django.db import IntegrityError, transaction

        ensaio = EnsaioCultivar.objects.create(user=self.user, propriedade=self.prop)
        FaixaEnsaio.objects.create(ensaio=ensaio, cultivar=self.cultivar, repeticao=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FaixaEnsaio.objects.create(
                    ensaio=ensaio, cultivar=self.cultivar, repeticao=1
                )

    def test_delete_ensaio_leva_faixas(self):
        ensaio = EnsaioCultivar.objects.create(user=self.user, propriedade=self.prop)
        f = FaixaEnsaio.objects.create(ensaio=ensaio, cultivar=self.cultivar)
        ensaio.delete()
        self.assertFalse(FaixaEnsaio.objects.filter(pk=f.pk).exists())
