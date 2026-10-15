import pytest

from app.models import (
    EstagioCultura,
    PerfilUsuario,
    Propriedade,
    RegistroProducao,
    TarefaEstagio,
)

pytestmark = pytest.mark.django_db


class TestPropriedade:
    def test_create(self, user_produtor):
        prop = Propriedade.objects.filter(user=user_produtor).first()
        assert prop is not None
        assert prop.nome == "Fazenda Teste"
        assert prop.area_total == 1000

    def test_str(self, user_produtor):
        prop = Propriedade.objects.filter(user=user_produtor).first()
        assert "Fazenda Teste" in str(prop)


class TestTarefaEstagioSync:
    def test_concluida_sets_status(self, user_produtor):
        reg = RegistroProducao.objects.create(
            user=user_produtor, nome="Soja", grupo="vegetal"
        )
        estagio = EstagioCultura.objects.create(registro=reg, nome="Plantio", ordem=1)
        tarefa = TarefaEstagio.objects.create(
            estagio=estagio, descricao="Preparar solo", concluida=True
        )
        assert tarefa.status == "concluido"
        assert tarefa.concluida_em is not None

    def test_status_concluido_sets_concluida(self, user_produtor):
        reg = RegistroProducao.objects.create(
            user=user_produtor, nome="Milho", grupo="vegetal"
        )
        estagio = EstagioCultura.objects.create(registro=reg, nome="Colheita", ordem=2)
        tarefa = TarefaEstagio.objects.create(
            estagio=estagio, descricao="Colher", status="concluido"
        )
        assert tarefa.concluida is True


class TestPerfilUsuario:
    def test_is_produtor(self, user_produtor):
        assert user_produtor.perfil.is_produtor

    def test_is_servidor(self, user_servidor):
        assert user_servidor.perfil.is_servidor

    def test_dashboard_config_mecanica(self, user_servidor):
        cfg = user_servidor.perfil.get_dashboard_config()
        assert "estoque_mecanico" in cfg["paginas"]
        assert cfg["pode_criar"] is True
