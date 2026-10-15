"""A ponte do copiloto respeita o contrato e o escopo das APIs reais."""

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.intents_recursos import (
    h_recurso_alterar,
    h_recurso_ler,
    h_recursos_catalogo,
)
from app.models import Propriedade, Talhao


class RecursosCopilotoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("recursos-owner")
        self.outro = User.objects.create_user("recursos-other")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Sítio", area_total=20, cidade="Sorriso", uf="MT"
        )
        self.alheia = Propriedade.objects.create(
            user=self.outro, nome="Outra", area_total=10, cidade="Sorriso", uf="MT"
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="Norte", area_hectare=3
        )

    def editar(self, **params):
        return h_recurso_alterar(
            self.user,
            {
                "recurso": "talhoes",
                "id": self.talhao.pk,
                "operacao": "editar",
                "confirm": True,
                **params,
            },
            {},
        )

    def test_catalogo_descobre_campos_reais(self):
        out = h_recursos_catalogo(self.user, {"recurso": "talhoes"}, {})
        self.assertTrue(out["ok"], out)
        self.assertIn("area_hectare", out["dados"]["campos"])

    def test_ler_lista_e_registro_da_conta(self):
        for params in (
            {"recurso": "propriedades"},
            {"recurso": "propriedades", "id": self.prop.pk},
        ):
            out = h_recurso_ler(self.user, params, {})
            self.assertTrue(out["ok"], out)
            self.assertNotIn("Outra", str(out["dados"]))
        out = h_recurso_ler(
            self.user, {"recurso": "propriedades", "id": self.alheia.pk}, {}
        )
        self.assertFalse(out["ok"], out)

    def test_edita_valor_pelo_serializer_do_modulo(self):
        out = self.editar(campos={"area_hectare": "4.25"})
        self.assertTrue(out["ok"], out)
        self.talhao.refresh_from_db()
        self.assertEqual(str(self.talhao.area_hectare), "4.25")

    def test_nao_altera_sem_confirmacao(self):
        self.assertTrue(
            self.editar(campos={"nome": "Novo"}, confirm=False)["needs_confirm"]
        )
        self.talhao.refresh_from_db()
        self.assertEqual(self.talhao.nome, "Norte")

    def test_rejeita_area_invalida_e_chaves_desconhecidas(self):
        for campos in (
            {"area_hectare": -1},
            {"campo_inventado": 2},
            {"id": 300},
            {"user": self.outro.pk},
        ):
            out = self.editar(campos=campos)
            self.assertFalse(out["ok"], out)
        self.talhao.refresh_from_db()
        self.assertEqual(self.talhao.area_hectare, 3)

    def test_mover_nao_pode_apontar_para_propriedade_alheia(self):
        out = self.editar(campos={"propriedade": self.alheia.pk})
        self.assertFalse(out["ok"], out)
        self.talhao.refresh_from_db()
        self.assertEqual(self.talhao.propriedade_id, self.prop.pk)

    def test_excluir_usa_rota_existente(self):
        out = self.editar(operacao="excluir")
        self.assertTrue(out["ok"], out)
        self.assertFalse(Talhao.objects.filter(pk=self.talhao.pk).exists())
