import os
import sys

# Add app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "app"))

# Add THIS directory to Python path, so tests can import their siblings.
#
# MEDIDO 2026-10-05. Dois ficheiros em `tests/` importam um irmao pelo caminho
# CURTO, sem o prefixo de pacote:
#
#     tests/test_nfe_import_view.py:28   from test_importar_nfe import CHAVE, NF_E
#     tests/aceitar_token_baseline.py:31 from test_token_violacao import ...
#
# O modulo destino esta ao lado, com o nome certo. O que falta e' o `tests/` no
# `sys.path` — e sem isso o pytest falha na COLECAO com
# `ModuleNotFoundError: No module named 'test_importar_nfe'`, que le como
# "falta o ficheiro" quando o ficheiro esta la.
#
# Isto e' o complemento do `tests/__init__.py`: aquele resolve o import com
# prefixo (`from tests.lcpr_fixtures import ...`) e este resolve o import sem
# prefixo. Os dois estilos ja coexistem no repositorio; sem os dois arranjos,
# metade das suites nao chega a correr.
#
# `conftest.py` e' o sitio certo porque o pytest le-o ANTES da coleccao, em
# qualquer ficheiro de `tests/`, mesmo quando a suite e' corrida por caminho
# absoluto. Corrigir os dois imports nos ficheiros que os usam resolveria
# estes dois — e deixaria o mesmo buraco para o proximo teste escrito apressado.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

# Pytest fixtures
import pytest

# ---------------------------------------------------------------------------
# O banco de teste é REAL — e isto não é opcional
# ---------------------------------------------------------------------------
# Este override removido. Antes:
#
#     @pytest.fixture(scope="session")
#     def django_db_setup():
#         pass
#
# Um `pass` aqui não é "não fazer nada": é **substituir** a fixture que o
# pytest-django usa para criar e destruir a base de teste. Com ela fora, todo
# `pytest` corre CONTRA O `db.sqlite3` DE DESENVOLVIMENTO, sem rollback, sem
# isolamento — e foi assim que este repositório ficou com `ctx`, `ctx2`,
# `ctx3`, `test_agenda`, `probe`, `p4`, `palco_vivo`… como utilizadores reais,
# e com talhões e funcionários "Teste" nas propriedades de gente a desenvolver.
#
# Não é um problema teórico. Os sintomas reais medidos nesta base:
#
#   * `User.objects.create_user("ctx")` na 2.ª vez levanta
#     `UNIQUE constraint failed: auth_user.username` — que parece "o teste
#     está mal escrito" e não "o teste está a sujar a base";
#   * `Propriedade`/`Talhao` de teste aparecem em listas de fazendas de
#     produtores a desenvolver a aplicação;
#   * um `pytest --lf` que apaga o que um teste criou apaga dados reais.
#
# A fixture do pytest-django é a que sabe criar a base de teste isolada e
# destruí-la no fim. Simplesmente não a substituir: os fixtures `db` daqui
# dependem dela, e sem ela `db` deixa de significar o que diz.


@pytest.fixture
def user_factory():
    """Factory para criar usuários de teste."""
    from django.contrib.auth.models import User

    def _create_user(username="testuser", password="testpass123", **kwargs):
        user = User.objects.create_user(username=username, password=password, **kwargs)
        return user

    return _create_user


@pytest.fixture
def propriedade_factory():
    """Factory para criar propriedades de teste."""
    from app.models import Propriedade

    def _create_propriedade(user, **kwargs):
        defaults = {
            "nome": "Fazenda Teste",
            "area_total": 100.0,
            "uf": "MT",
            "cidade": "Primavera do Leste",
        }
        defaults.update(kwargs)
        return Propriedade.objects.create(user=user, **defaults)

    return _create_propriedade


@pytest.fixture
def cultura_factory():
    """Factory para criar culturas de teste."""
    from app.models import Cultura

    def _create_cultura(**kwargs):
        defaults = {
            "nome": "Soja",
            "grupo": "graos",
            "unidade_comercial": "sacas",
            "ativo": True,
        }
        defaults.update(kwargs)
        return Cultura.objects.create(**defaults)

    return _create_cultura


@pytest.fixture
def talhao_factory():
    """Factory para criar talhões de teste."""
    from app.models import Cultura, Talhao

    def _create_talhao(propriedade, cultura=None, **kwargs):
        if cultura is None:
            cultura = Cultura.objects.first()
            if not cultura:
                cultura = Cultura.objects.create(nome="Soja", grupo="graos")

        defaults = {
            "propriedade": propriedade,
            "nome": "Talhao Teste",
            "area_hectare": 100.0,
            "cultura_atual": cultura,
            "ativo": True,
        }
        defaults.update(kwargs)
        return Talhao.objects.create(**defaults)

    return _create_talhao


@pytest.fixture
def funcionario_factory():
    """Factory para criar funcionários de teste."""
    from app.models import Funcionario

    def _create_funcionario(propriedade, **kwargs):
        defaults = {
            "nome": "Funcionário Teste",
            "cargo": "TRATORISTA",
            "salario": 3000.00,
            "data_admissao": "2024-01-01",
            "ativo": True,
        }
        defaults.update(kwargs)
        return Funcionario.objects.create(propriedade=propriedade, **defaults)

    return _create_funcionario


@pytest.fixture
def seed_mvp_demo():
    """Executa seed_mvp_demo para popular dados de teste."""
    from django.core.management import call_command

    def _run():
        call_command("seed_mvp_demo", "--reset", "--with-telemetry", verbosity=0)

    return _run


@pytest.fixture
def user_produtor(db, user_factory, propriedade_factory):
    user = user_factory(username="produtor_test")
    from app.models import PerfilUsuario, Propriedade

    # `get_or_create`, não `create`.
    #
    # `app/signals.py::garantir_perfil_usuario` já cria o PerfilUsuario no
    # `post_save` de `auth.User` — foi lá para apanhar os utilizadores que
    # nascem fora de `app/views/auth.py` (SSO Google, admin do Django). Este
    # fixture, com `create`, tentava inserir um segundo perfil para o mesmo
    # `user_id` e rebentava em `UNIQUE constraint failed:
    # app_perfilusuario.user_id`.
    #
    # Confirmado: com o sinal activo, `User.objects.create_user()` já deixa 1
    # perfil. O `create` a seguir era sempre o que falhava — e como o sinal
    # tem de continuar a correr, a correção é no fixture, não no sinal.
    PerfilUsuario.objects.get_or_create(
        user=user, defaults={"tipo_usuario": "produtor"}
    )
    propriedade_factory(user=user, nome="Fazenda Teste", area_total=1000, uf="MT")
    return user


@pytest.fixture
def user_servidor(db, user_produtor, user_factory):
    user = user_factory(username="servidor_test")
    from app.models import PerfilUsuario, Propriedade

    prop = Propriedade.objects.filter(user=user_produtor).first()
    # `update_or_create`, não `get_or_create`.
    #
    # O `post_save` de `auth.User` já criou um PerfilUsuario com o default
    # `tipo_usuario="produtor"`. Com `get_or_create(defaults=...)` esse
    # registo já existe, os defaults nunca eram aplicados, e o "servidor"
    # ficava na verdade com um perfil de produtor — daí
    # `test_is_servidor` e `test_dashboard_config_mecanica` falharem com
    # `['tarefas', 'agenda']` em vez da config de MECANICA.
    #
    # O fixture declara o que quer que o utilizador SEJA; a tabela está a
    # dizer outra coisa e o `update` é o que reconcilia.
    PerfilUsuario.objects.update_or_create(
        user=user,
        defaults={
            "tipo_usuario": "servidor",
            "area_servidor": "MECANICA",
            "propriedade_vinculada": prop,
            "vinculado_por": user_produtor,
        },
    )
    # `user.perfil` estava em cache no objecto Django; invalidar para que o
    # teste leia o perfil acabado de escrever e não o de produtor.
    if hasattr(user, "_state"):
        user._state.fields_cache.pop("perfil", None)
    return user


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(api_client, user_produtor):
    api_client.force_authenticate(user=user_produtor)
    return api_client
