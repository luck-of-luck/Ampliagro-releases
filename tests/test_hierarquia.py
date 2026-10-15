import pytest

from app.hierarquia import PERMISSAO_POR_VIEW, pode_acessar

pytestmark = pytest.mark.django_db


class TestHierarquia:
    def test_produtor_ve_tudo(self, user_produtor):
        # O produtor tem acesso a praticamente todas as views que ele é dono.
        for view_name in PERMISSAO_POR_VIEW:
            assert pode_acessar(user_produtor, view_name)

    def test_servidor_mecanica_ve_estoque(self, user_servidor):
        assert pode_acessar(user_servidor, "servidor-estoque")

    def test_403_sem_permissao(self, client, user_servidor):
        client.force_login(user_servidor)
        response = client.get("/cadastro/financeiro/")
        assert response.status_code == 403
