"""Um `path()` depois de um `router.register()` NAO ignora o router — ganha-lhe.

Este ficheiro existe por causa de um bug real e silencioso.

O QUE ACONTECEU
===============
Em `app/api/urls.py`:

    router.register(r"estoque", EstoqueItemViewSet, basename="estoque")        # L148
    router.register(r"maquinarios", MaquinarioViewSet, basename="maquinario")  # L141
    ...
    path("estoque/", estoque_data, name="api-estoque")                          # L262
    path("maquinarios/", maquinarios_data, name="api-maquinarios")             # L299

Em Django o URL resolver percorre as patrons por ordem e devolve a PRIMEIRA
que faz match. Estas `path()` vinham DEPOIS do registo do router e ocupavam o
mesmo prefixo — logo resolviam, e o ViewSet ficava inalcancavel.

`estoque_data` e `maquinarios_data` sao `@api_view(["GET"])`. O resultado:

  * `cadastro-estoque.html:191`     POST   `/api/estoque/`        -> 405
  * `cadastro-estoque.html:200`     DELETE `/api/estoque/{id}/`  -> 405
  * `cadastro-maquinario.html:257`  POST   `/api/maquinarios/`    -> 405
  * `estoque-geral.html:115`        faz `itens.forEach` sobre um objecto
                                    `{itens, ...}`, nao um array -> TypeError

Ou seja: o cadastro de estoque e de maquinas estava partido, e nada na suite
falhava. Django nao avisa. O router nao avisa. So a medicao apanha.

A CORRECAO
==========
Os agregados mudaram para `estoque-resumo/` e `maquinarios-resumo/`, a
convencao que a casa ja usava em `funcionarios-resumo/`. O router ficou com
`/api/estoque/` e `/api/maquinarios/`.

DUAS ARMADILHAS JA PERCORRIDAS NESTE FICHEIRO
=============================================
1. Indexar pelo NOME DO VIEWSET e comparar com uma lista de BASENAMES.
   `endswith("estoque")` contra `"EstoqueItemViewSet"` da `False`, e os 9
   testes de sombreamento passaram a `skip` sem dar erro.

2. `collections.Counter(REGISTOS)` para detectar prefixos duplicados, onde
   `REGISTOS` ja e' um dict indexado pelo prefixo — o Counter dava sempre 1
   e o teste era um tautologismo.

Um teste que salta em silencio, ou que nao pode falhar, e' pior do que nao ter
teste: parece cobertura. `test_ha_registos_no_router` existe para travar a
primeira armadilha.
"""

import ast
import pathlib

import pytest
from django.urls import get_resolver

URLS = pathlib.Path(__file__).resolve().parents[1] / "app" / "api" / "urls.py"
TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "app" / "templates"

# Parametrizado pelo PREFIXO, nao pelo basename: o prefixo e' o que determina
# a URL, e nem todos os registos tem `basename` explicito (o de `culturas`
# nao tem, e caia no nome da classe).
PREFIXOS_CRUDS = (
    "estoque",
    "maquinarios",
    "talhoes",
    "safras",
    "culturas",
    "insumos",
    "funcionarios",
    "animais",
    "propriedades",
)

# O par (template, rota) que o produtor usa ao clicar "guardar".
CADASTROS = (
    ("cadastro-estoque.html", "/api/estoque/"),
    ("cadastro-maquinario.html", "/api/maquinarios/"),
)


def _router_registrations():
    """`{prefixo: {"viewset": ..., "basename": ...}}` lido do fonte.

    Ler o fonte e o que torna isto util sem base de dados: e' um aviso de
    estrutura, nao um teste de comportamento.
    """
    arvore = ast.parse(URLS.read_text(encoding="utf-8"))
    achados = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        func = no.func
        if not (isinstance(func, ast.Attribute) and func.attr == "register"):
            continue
        # `router.register(r"x", XViewSet, basename="x")` — o basename e'
        # KEYWORD, so se contam os dois posicionais.
        if len(no.args) < 2:
            continue
        prefix, viewset = no.args[0], no.args[1]
        if not (isinstance(prefix, ast.Constant) and isinstance(viewset, ast.Name)):
            continue
        basename = None
        for kw in no.keywords:
            if kw.arg == "basename" and isinstance(kw.value, ast.Constant):
                basename = kw.value.value
        achados[prefix.value] = {
            "viewset": viewset.id,
            "basename": basename or viewset.id,
        }
    return achados


REGISTOS = _router_registrations()


def test_ha_registos_no_router():
    """Trava de sanidade, e existe por causa da armadilha 1 do cabecalhao."""
    assert len(REGISTOS) > 5, (
        f"so encontrei {len(REGISTOS)} `router.register()` em {URLS.name} — o "
        "parser deixou de bater certo e os testes abaixo passariam por vazio"
    )
    assert all(
        v["basename"] for v in REGISTOS.values()
    ), "algum registo ficou sem basename legivel"


@pytest.mark.parametrize("prefixo", PREFIXOS_CRUDS)
def test_rota_do_router_nao_esta_sombreada(prefixo):
    """O ViewSet tem de ser ALCANCAVEL no caminho que o router lhe deu."""
    if prefixo not in REGISTOS:
        pytest.skip(f"`{prefixo}` nao esta registado no router")
    caminho = "/api/" + prefixo.strip("^$") + "/"

    alcancado = getattr(get_resolver().resolve(caminho).func, "cls", None)
    nome = alcancado.__name__ if alcancado else "?"
    esperado = REGISTOS[prefixo]["viewset"]

    assert esperado in nome, (
        f"`{caminho}` foi registado no router como `{esperado}` mas resolve "
        f"para `{nome}`. Alguma `path()` posterior ocupou o mesmo caminho e "
        "sombreou o ViewSet — os consumidores CRUD recebem 405. (Aconteceu "
        "com estoque e maquinarios; ver o cabecalhao.)"
    )


@pytest.mark.parametrize("ficheiro,caminho", CADASTROS)
def test_o_cadastro_que_o_produtor_usa_precisa_de_post(ficheiro, caminho):
    """A consequencia pratica, sem passar pelo router: o "guardar" do cadastro.

    Estes sao os pedidos que o produtor faz a clicar guardar. Se algum levar
    405, o cadastro esta partido — e nenhum teste de modelo falha, porque o
    problema nao esta no modelo, esta na rota.
    """
    txt = (TEMPLATES / ficheiro).read_text(encoding="utf-8")
    assert caminho in txt, (
        f"{ficheiro} deixou de usar {caminho} — actualiza CADASTROS neste "
        "ficheiro, senao o teste mede uma coisa que ja nao existe"
    )

    alcancado = getattr(get_resolver().resolve(caminho).func, "cls", None)
    verbos = getattr(alcancado, "http_method_names", None)
    assert verbos is None or "post" in verbos, (
        f"{caminho} e' chamada com POST por {ficheiro}, mas resolve para "
        f"`{alcancado.__name__ if alcancado else '?'}` com verbos {verbos} "
        "— o cadastro devolve 405"
    )
