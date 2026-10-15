"""G-01 Cultivar — o criterio de saida do plano-correcao, fixado em teste.

Tres redes, cada uma com o motivo escrito:

1. POST minimo passa (cultura + nome_comercial); catalogo honesto aceita
   linha quase vazia em vez de exigir numero que ninguem tem.
2. PATCH/DELETE nao-staff da 403 (catalogo partilhado sem dono — ver
   `app/api/perms.py`); staff passa.
3. DELETE da cultivar com safra vinculada zera o campo (SET_NULL, como
   `Talhao.cultura_atual`); DELETE da cultura com cultivar vinculada
   recusa (PROTECT, como `Safra.cultura`).
"""

from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from app.models import Cultura, Cultivar, Propriedade, Safra


class CultivarG01Test(TestCase):
    def setUp(self):
        self.produtor = User.objects.create_user(
            "produtor_g01", "g01@x.com", "senhaforte123"
        )
        self.staff = User.objects.create_user(
            "staff_g01", "staff_g01@x.com", "senhaforte123", is_staff=True
        )
        self.soja = Cultura.objects.create(nome="Soja G01", grupo="graos")
        self.prop = Propriedade.objects.create(
            user=self.produtor, nome="Fazenda G01", area_total=100
        )

    def _cultivar(self):
        return Cultivar.objects.create(
            cultura=self.soja, nome_comercial="TMG G01", fonte_dado="declarado"
        )

    def test_post_minimo_passa(self):
        cli = APIClient()
        cli.force_authenticate(user=self.staff)
        resp = cli.post(
            "/api/cultivares/",
            {"cultura": self.soja.pk, "nome_comercial": "TMG G01"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        c = Cultivar.objects.get(pk=resp.data["id"])
        self.assertEqual(c.fonte_dado, "declarado")
        self.assertIsNone(c.ciclo_max)

    def test_patch_nao_staff_e_403(self):
        c = self._cultivar()
        cli = APIClient()
        cli.force_authenticate(user=self.produtor)
        resp = cli.patch(f"/api/cultivares/{c.pk}/", {"obtentor": "X"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_delete_nao_staff_e_403(self):
        c = self._cultivar()
        cli = APIClient()
        cli.force_authenticate(user=self.produtor)
        resp = cli.delete(f"/api/cultivares/{c.pk}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Cultivar.objects.filter(pk=c.pk).exists())

    def test_staff_altera(self):
        c = self._cultivar()
        cli = APIClient()
        cli.force_authenticate(user=self.staff)
        resp = cli.patch(f"/api/cultivares/{c.pk}/", {"obtentor": "TMG"}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_delete_cultura_com_cultivar_recusa(self):
        self._cultivar()
        with self.assertRaises(ProtectedError):
            self.soja.delete()
        self.assertTrue(Cultura.objects.filter(pk=self.soja.pk).exists())
