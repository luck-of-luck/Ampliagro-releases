"""A revogacao de servidor tem de chegar a toda a escrita, nao so as leituras.

Este ficheiro e a CAMADA DE INTEGRACAO. Nao duplica
`tests/test_revogacao_api.py`, que testa o `ServidorRevogadoMiddleware`
isolado, com `RequestFactory` e um `perfil` de `SimpleNamespace`, so com GET.

O que so se mede aqui:

  1. **METODOS DE ESCRITA.** O middleware unit test usa `RequestFactory().get()`.
     O relatorio afirma que "7 rotas POST mantinham escrita". Isso so aparece
     com um POST a passar pela pilha real.
  2. **A PILHA COMPLETA.** `RequestFactory` nao corre settings, nem
     `SessionMiddleware`, nem `AuthenticationMiddleware`, nem o DRF. Um
     middleware registado mas mal ligado passa o teste unit e falha aqui
     (`test_revogacao_api.py::test_a_middleware_esta_ligada_em_settings`
     cobre esse outro lado).

`app/services/revogacao.py` cobre quem nao passa por HTTP — Celery e
management commands — e essa cobertura e testada a parte.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()

# (metodo, caminho). Inclui leitura, escrita, e `agenda-analises` que dava 500.
ROTAS_API = [
    ("get", "/api/talhoes/"),
    ("get", "/api/safras/"),
    ("get", "/api/financeiro/"),
    ("get", "/api/animais/"),
    ("get", "/api/propriedades/"),
    ("get", "/api/agenda-analises/"),
    ("post", "/api/tarefas-estagio/mover"),
    ("post", "/api/tarefas-estagio/criar"),
]


@pytest.fixture
def revogado(db):
    u = User.objects.create_user("revogado", password="x")
    perfil = u.perfil
    perfil.ativo_servidor = False
    perfil.save()
    return u


@pytest.fixture
def cliente(revogado):
    c = Client()
    assert c.login(username="revogado", password="x")
    return c


@pytest.mark.django_db
@pytest.mark.parametrize("metodo,caminho", ROTAS_API)
def test_rota_api_recusa_servidor_revogado(cliente, metodo, caminho):
    """O coracao do achado: 403, e nao 200 com dados de outro tenant."""
    r = getattr(cliente, metodo)(caminho, content_type="application/json", data={})
    assert r.status_code in (401, 403), (
        f"{metodo.upper()} {caminho} respondeu {r.status_code} para um servidor "
        f"revogado. O corpo foi: {r.content[:200]!r}"
    )


@pytest.mark.django_db
def test_escrita_e_recusada_e_nao_so_leitura(cliente):
    """O relatorio diz que 7 POST mantinham escrita. Esta e a separatizacao.

    Um middleware que so protege o GET deixa o POST passar e o dano e
    escrita — que e o que o produtor nao ve.
    """
    r = cliente.post("/api/tarefas-estagio/mover", content_type="application/json")
    assert r.status_code in (401, 403), (
        f"POST /api/tarefas-estagio/mover respondeu {r.status_code}. "
        "Escrita passa com o servidor revogado."
    )


@pytest.fixture
def cliente_nao_revogado(db):
    u = User.objects.create_user("ativo", password="x")
    u.perfil.ativo_servidor = True
    u.perfil.save()
    c = Client()
    assert c.login(username="ativo", password="x")
    return c


@pytest.mark.django_db
def test_leitura_normal_sigue_a_passar(cliente_nao_revogado):
    """A outra metade: o middleware nao pode estar a bloquear toda a gente."""
    r = cliente_nao_revogado.get("/api/propriedades/")
    assert r.status_code == 200, (
        f"/api/propriedades/ devolveu {r.status_code} para um servidor ACTIVO. "
        "O middleware esta a recusar quem nao devia."
    )


@pytest.mark.django_db
def test_perfil_ausente_nao_e_revogacao():
    """O inverso: quem nao tem perfil nao esta revogado.

    O middleware tem este cuidado (`app/middleware.py:107-109`) e o teste
    fixa-o. Sem ele, um registo orfao ficava bloqueado sem razao — e o
    suporte ligava para dizer "o servidor esta desativado", o que era mentira.
    """
    User.objects.create_user("sem_perfil_user", password="x")
    c = Client()
    assert c.login(username="sem_perfil_user", password="x")
    r = c.get("/api/propriedades/")
    corpo = r.content.decode("utf-8", "ignore")
    assert "desativado" not in corpo, (
        "perfil ausente foi tratado como revogacao — o produtor perdia o "
        "acesso sem o servidor estar desativado"
    )
