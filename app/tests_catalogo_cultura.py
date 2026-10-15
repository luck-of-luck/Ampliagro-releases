"""O catálogo de culturas é partilhado: alterar é assunto de staff.

Este teste existe porque a falha que fecha é INVISÍVEL. Um produtor que
muda a `janela_plantio` de "Soja" não recebe erro nenhum — o outro produtor
é que recebe, dias ou semanas depois, uma recomendação de plantio errada, e
sem nenhum rasto de quem mudou.

Por isso o teste mede o efeito, não a configuração: chama a API como um
produtor comum e tenta as operações que corrompem o catálogo de toda a
gente.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class CatalogoCulturaPartilhadoTest(TestCase):
    def setUp(self):
        self.url = reverse("cultura-list") if self._tem_nome() else "/api/culturas/"
        self.api = APIClient()

        self.produtor = User.objects.create_user(
            "produtor_catalogo", "p@c.com", "senhaforte123"
        )
        self.staff = User.objects.create_user(
            "staff_catalogo", "s@c.com", "senhaforte123", is_staff=True
        )

        from app.models import Cultura

        self.cultura = Cultura.objects.create(
            nome="Soja", grupo="graos", janela_plantio_inicio=10, janela_plantio_fim=20
        )

    @staticmethod
    def _tem_nome():
        from django.urls import reverse as _r

        try:
            _r("cultura-list")
            return True
        except Exception:
            return False

    # --- o que qualquer produtor pode fazer ------------------------------

    def test_leitura_do_catalogo_aberta(self):
        """O frontend precisa de ler o catálogo para montar os ecrãs."""
        self.api.force_authenticate(self.produtor)
        r = self.api.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            any(i.get("id") == self.cultura.id for i in r.json()["results"])
            if isinstance(r.json(), dict) and "results" in r.json()
            else any(i.get("id") == self.cultura.id for i in r.json()),
            "o produtor tem de ver a cultura no catálogo",
        )

    def test_criar_cultura_continua_permitido(self):
        """A página de cadastro faz POST. Tirar isto parte o produto."""
        self.api.force_authenticate(self.produtor)
        r = self.api.post(self.url, {"nome": "Canola", "grupo": "oleaginosas"})
        self.assertEqual(
            r.status_code,
            201,
            f"criar cultura tem de continuar a funcionar para o produtor: {r.content[:200]}",
        )

    # --- o que tem de estar fechado --------------------------------------

    def test_produtor_nao_altera_janela_de_plantio_alheia(self):
        """O dano real: mudar a janela de todos, sem erro e sem rasto."""
        self.api.force_authenticate(self.produtor)
        r = self.api.patch(
            f"{self.url}{self.cultura.id}/",
            {"janela_plantio_inicio": 1, "janela_plantio_fim": 2},
        )
        self.assertIn(
            r.status_code,
            (403, 405),
            f"um produtor nao pode reescrever a janela de plantio (veio {r.status_code})",
        )
        self.cultura.refresh_from_db()
        self.assertEqual(
            self.cultura.janela_plantio_inicio,
            10,
            "a janela de plantio mudou na base de dados apesar do 403",
        )

    def test_produtor_nao_desactiva_uma_cultura_partilhada(self):
        """`ativo=False` esconde a cultura dos ecrãs de toda a gente."""
        self.api.force_authenticate(self.produtor)
        r = self.api.patch(f"{self.url}{self.cultura.id}/", {"ativo": False})
        self.assertIn(r.status_code, (403, 405))
        self.cultura.refresh_from_db()
        self.assertTrue(self.cultura.ativo)

    def test_produtor_nao_apaga_cultura(self):
        self.api.force_authenticate(self.produtor)
        r = self.api.delete(f"{self.url}{self.cultura.id}/")
        self.assertIn(r.status_code, (403, 405))
        self.assertTrue(
            type(self.cultura).objects.filter(pk=self.cultura.pk).exists(),
            "a cultura foi apagada apesar do 403",
        )

    def test_anonimo_nao_le_o_catalogo(self):
        r = self.api.get(self.url)
        self.assertIn(r.status_code, (401, 403))

    # --- o que a administração precisa de continuar a poder fazer ----------

    def test_staff_altera_o_catalogo(self):
        """Staff tem de conseguir corrigir o catálogo — é para isso que existe."""
        self.api.force_authenticate(self.staff)
        r = self.api.patch(
            f"{self.url}{self.cultura.id}/", {"janela_plantio_inicio": 11}
        )
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.cultura.refresh_from_db()
        self.assertEqual(self.cultura.janela_plantio_inicio, 11)
