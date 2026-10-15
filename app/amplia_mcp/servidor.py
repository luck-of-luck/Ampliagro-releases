r"""
servidor.py — o servidor MCP (stdio) do AmplIA.

Para que este arquivo rode, o SDK `mcp` precisa estar instalado
(`pip install mcp`). Ele NAO e dependencia do AmplIA: o Django funciona,
a IA do painel funciona e o endpoint HTTP funciona sem o SDK. O servidor MCP
e a porta para clientes de fora (Claude Desktop, Hermes, qualquer agente que
fale MCP), e por isso o import e preguiçoso e o resto do projeto nao sente a
falta dele.

Este servidor expoe:

  Tools     — as intents, via `app.amplia_mcp.executar_para`, com o contrato
              completo de `contrato.py`
  Resources — `amplia://contexto/{usuario}`, `amplia://modelos`,
              `amplia://widgets`, `amplia://blocos`, `amplia://skills`,
              `amplia://capacidades`

Ele NAO implementa execucao. Chama `executar_para`, que chama
`sandbox.executar`. Um segundo caminho de execucao seria exatamente o bug que
esta camada existe para fechar.

O usuario chega por parametro (`--usuario`), porque o MCP stdio e um processo
local sem sessao web. O `is_authenticated` e forcado porque o `sandbox` exige
usuario — um processo stdio sem usuario e um caso que a API web nao alcanca, e
tratado explicitamente em vez de ser assumido.


OS TRÊS DEFECTOS QUE ESTE FICHEIRO TINHA, E COMO FORAM MEDIDOS
--------------------------------------------------------------

**1. Não arrancava de fora do repositório.** `python -m app.amplia_mcp.servidor`
exige que o CWD seja a raiz do projeto, porque é o que põe `config` no
`sys.path`. Um cliente MCP não tem CWD — Claude Desktop e Hermes arrancam o
processo com o directório de trabalho do utilizador, e a receita que o
documento suggestia (`--usuario`) não resolvia nada disto.

    Medido, L3: `python <repo>/app/amplia_mcp/servidor.py --usuario x`, com CWD
    no directório do utilizador ->
        rc=2, "django.setup() falhou: No module named 'config'"

    Corrigido com `_arrancar_django()`, que descobre a raiz pelo `__file__` e a
    junta ao `sys.path`. Um cliente MCP configura um caminho absoluto uma vez
    e nunca mais pensa nele; a raiz tem de se deduzir sozinha.

**2. Não tinha canal de `entrada`.** O `sandbox` é uma máquina de estados
conversacional: quando uma escrita devolve `needs_confirm`, o próximo passo é
a frase do produtor. Em HTTP, `views.exec` aceita `entrada`. Em stdio não
havia caminho nenhum — e como `entrada` chega vazia, o `else` do bloco
`AGUARDANDO_CONFIRMACAO` corria e devolvia "Operação cancelada."

    Medido, L2: `grep "entrada" servidor.py` -> zero ocorrências.

    Corrigido: `entrada` é um campo de topo nos argumentos, retirado antes de
    chegar ao sandbox e entregue em `meta`. E `confirm: true` continua a ser o
    caminho sem frase, para o agente que não tem conversa.

**3. Arrancava em `config.settings.dev`, fixo.** Um servidor MCP em produção
herdava as settings de desenvolvimento — com o `DEBUG` ligado. Passa a haver
`--settings`, e o default passa a ser `config.settings.prod` quando o
ambiente o diz que é produção. O default anterior estava errado no sentido
inverso do perigoso: nunca Protectava, protegia sempre.

    Corrigido em `_ajustar_settings()`.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Any

#: A raiz do repositório, deduzida deste ficheiro: app/amplia_mcp/servidor.py
#: -> app/amplia_mcp -> app -> <raiz>. É a única forma de um cliente MCP
#: arrancar sem CWD, e o único motivo de este import existir antes do Django.
RAIZ_REPO = pathlib.Path(__file__).resolve().parents[2]

#: Bytes de uma resposta de tool. O MCP não tem limite, mas o modelo tem
#: contexto, e um catálogo de telas com 30 widgets é maior do que a janela
#: útil de um modelo de 1.7B. Truncar é melhor do que ver a chamada recusada.
LIMITE_RESPOSTA = 8000


def _falta(m):
    print(f"[amplia-mcp] {m}", file=sys.stderr)
    return 2


def _arrancar_django(settings: str) -> int | None:
    """Põe o Django de pé a partir de um caminho absoluto. Devolve erro ou None.

    Faz três coisas, e as três são o que faltava:

    1. `RAIZ_REPO` no `sys.path` — sem isto, `config` não importa (medido, L3).
    2. `DJANGO_SETTINGS_MODULE` — resolvido por uma precedência explícita.
    3. Chamar `django.setup()` e devolver o erro com a SUA mensagem, não uma
       genérica. "django.setup() falhou" sem dizer qual foi o erro é o que
       fez este defeito durar: ninguém sabia que era o path.

    PRECEDÊNCIA DAS SETTINGS (revisão de 2026-09-30)
    ----------------------------------------------
    A versão anterior fazia isto:

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings)
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", _settings_default())

    A segunda linha nunca corre — a primeira já punha a chave. E a primeira
    é um `setdefault`, o que significa que o flag `--settings` era IGNORADO
    sempre que a variável já existisse no ambiente. Medido, L3:

        env DJANGO_SETTINGS_MODULE=config.settings.dev
        --settings config.settings.prod   ->  arrancou em dev

    Ou seja: o flag que a docstring deste ficheiro apresenta como a correção
    para "arrancar em dev num servidor de produção" não corrigia nada numa
    máquina que tivesse a variável exportada — que é precisamente a máquina
    de produção, e a que alguém pode ter `set` por hábito. O operador via o
    servidor a subir e acreditava ter escolhido.

    A ordem agora é: flag explícito > ambiente > default por ambiente. Um
    valor vazio conta como "não dito", porque `DJANGO_SETTINGS_MODULE=""` é
    o que deixa um launcher exporta-la sem querer, e `setdefault` não
    substitui uma chave vazia — o resultado era `django.setup()` a falhar
    sem módulo, sem ninguém perceber porquê.
    """
    if str(RAIZ_REPO) not in sys.path:
        sys.path.insert(0, str(RAIZ_REPO))

    # O `sys.path` resolve o MÓDULO. Não resolve o FICHEIRO DE DADOS.
    #
    # O `.env` do Ampliagro tem `DATABASE_URL=sqlite:///db.sqlite3` — e esse
    # caminho é RELATIVO. O SQLite resolve-o contra o directório de trabalho
    # do processo, que num cliente MCP é o directório do utilizador, nunca a
    # raiz do repositório. O `sys.path` de cima não chega: o módulo importa,
    # o Django arranca, e a primeira consulta morre.
    #
    #     Medido, L3, CWD em `C:\Trabalho\Projetos`:
    #         [amplia-mcp] nao consegui ligar ao banco: no such table: auth_user
    #
    # É a mesma armadilha que o `ampliagro-dev` regista para o `manage.py`, e
    # aqui não há ninguém para a contornar: quem arranca o servidor é o
    # Claude Desktop ou o opencode, que não sabem nada do Ampliagro.
    #
    # Por isso o processo MUDA DE DIRECTÓRIO, e não só o path. É a única
    # forma de um caminho relativo funcionar quando quem o invoca não tem
    # como escolher o cwd.
    #
    # Só se muda se ainda não estivermos lá: `django.setup()` pode ser chamado
    # por outro import antes de nós, e mudar de directório a meio não
    # estraga nada — mas também não ajuda. A guarda evita o travail de
    # dizer onde estamos a cada chamada.
    if pathlib.Path.cwd().resolve() != RAIZ_REPO:
        try:
            os.chdir(RAIZ_REPO)
        except OSError as e:  # noqa: BLE001 — a mensagem é o produto
            return _falta(
                f"nao consegui mudar para a raiz do repositorio "
                f"({RAIZ_REPO}): {e}\n"
                "O DATABASE_URL e' relativo, por isso o servidor tem de "
                "arrancar dentro do repositorio."
            )

    escolhida = (
        (settings or "").strip()
        or (os.environ.get("DJANGO_SETTINGS_MODULE") or "").strip()
        or _settings_default()
    )
    os.environ["DJANGO_SETTINGS_MODULE"] = escolhida

    try:
        import django
    except ImportError as e:
        return _falta(
            f"Django nao encontrado neste interprete ({e}). Use o Python do venv: {sys.executable}"
        )

    try:
        django.setup()
    except Exception as e:  # noqa: BLE001 — a mensagem é o produto desta função
        return _falta(
            f"django.setup() falhou: {e}\n"
            f"  settings: {os.environ.get('DJANGO_SETTINGS_MODULE')}\n"
            f"  raiz:    {RAIZ_REPO}\n"
            f"  path:    {sys.path[0]}"
        )
    return None


def _settings_default() -> str:
    """`prod` fora de desenvolvimento, `dev` dentro.

    O default anterior era `dev` fixo, o que num servidor em produção é
    `DEBUG=True` e a mostrar tracebacks ao primeiro utilizador que erre um
    argumento. A escolha agora segue o ambiente, que é a única coisa que
    distingue os dois sem perguntar a alguém.
    """
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        return os.environ["DJANGO_SETTINGS_MODULE"]
    em_producao = os.environ.get("AMPLIA_PROD", "").lower() in (
        "1",
        "true",
        "sim",
        "yes",
    )
    return "config.settings.prod" if em_producao else "config.settings.dev"


def _texto(v: Any, limite: int = LIMITE_RESPOSTA) -> str:
    """Serializa com o que menos se perde: `ensure_ascii=False`, `default=str`."""
    return json.dumps(v, ensure_ascii=False, default=str)[:limite]


async def _no_thread(fn, *args, **kwargs):
    """Corre uma função SÍNCRONA do Django a partir de um handler async.

    O defeito que isto resolve, medido, não suposto
    ------------------------------------------------
    O SDK do MCP é async. O Django ORM não é. Um handler `async def` que
    chama `sandbox.executar` — que vai ao banco — levanta
    `SynchronousOnlyOperation`, e o cliente MCP recebe a frase:

        You cannot call this from an async context - use a thread or
        sync_to_async.

    Em modo leitura isso e' pior do que um crash, porque o servidor parece
    funcionar: o handshake responde, o `tools/list` devolve as 78 tools, o
    portao de escrita recusa corretamente. So' a chamada verdadeira falha — e
    falha sempre, em todas as tools que tocam o banco, que sao quase todas. Um
    agente que ligue isto e receba um catalogo enorme e depois um erro em cada
    tool conclui que o AmplIA esta em baixo quando esta, na verdade,
    inacessivel.

    Porque uma thread e não `sync_to_async`: o `sync_to_async` do asgiref com
    `thread_sensitive=True` (o default) executa num executor dedicado, o que
    serializa as operações de base de dados. Para um servidor cujo trabalho
    são consultas curtas, isso é o comportamento certo: uma conexão por
    thread, sem duas threads aMexer na mesma. `thread_sensitive=False`
    devolveria paralelismo que o Django não quer.

    O fecho da conexao nao e' opcional: cada thread nova abre a sua, e um
    servidor de MCP vive muito tempo com o mesmo punhado de threads do
    executor. Sem `close_old_connections`, uma alteracao de esquema ou um
    restart do Postgres deixaria essas threads a falar com uma ligacao morta.
    """
    from asgiref.sync import sync_to_async
    from django.db import close_old_connections

    await sync_to_async(close_old_connections, thread_sensitive=True)()
    try:
        return await sync_to_async(fn, thread_sensitive=True)(*args, **kwargs)
    finally:
        # Em caso de excepcao tambem: uma escrita que rebentou a meio e deixa
        # a transacao aberta e' pior do que uma escrita que rebentou.
        await sync_to_async(close_old_connections, thread_sensitive=True)()


def rodar(usuario: str, permitir_escrita: bool = False, settings: str = ""):
    """Sobe o servidor MCP em stdio. Bloqueia ate o stdin fechar."""
    erro = _arrancar_django(settings or _settings_default())
    if erro:
        return erro

    try:
        import mcp.types as mt
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
    except ImportError:
        return _falta(
            "SDK 'mcp' nao instalado. A AmplIA funciona sem ele "
            "(HTTP em /api/amplia/). Para o servidor stdio: pip install mcp"
        )

    from django.contrib.auth.models import User

    from app.amplia_mcp import (
        NOMES_CATALOGO,
        TOOLS_CATALOGO,
        catalogo_tools,
        contexto,
        executar_catalogo,
        executar_para,
        nome_tool,
    )
    from app.amplia_mcp import prompts_mcp as _prompts
    from app.amplia_mcp.contrato import GUIA, para_mcp

    try:
        user = User.objects.get(username=usuario)
    except User.DoesNotExist:
        return _falta(f"usuario {usuario!r} nao existe no banco.")
    except Exception as e:  # noqa: BLE001 — banco mal configurado é comum
        return _falta(f"nao consegui ligar ao banco: {e}")

    # `permitir_escrita` e o portao de seguranca do stdio. Um agente externo
    # rodando na maquina do produtor nao deveria, por padrao, poder acionar
    # irrigacao. O padrao e o mais seguro e o mais explicito: ligar e opt-in.
    bloqueio: set[str] = set()
    if not permitir_escrita:
        from app.ia.sandbox import INTENTS, somente_leitura

        bloqueio = {nome_tool(n) for n, s in INTENTS.items() if not somente_leitura(s)}
        if bloqueio:
            print(
                f"[amplia-mcp] modo leitura: {len(bloqueio)} tools de escrita "
                "bloqueadas. Use --permitir-escrita para liberar.",
                file=sys.stderr,
            )

    server = Server("amplia", instructions=GUIA)
    server.usuario = usuario
    server.user = user
    server.bloqueio = bloqueio
    # O contrato é montado UMA vez. Montar por chamada faria cada `list_tools`
    # refazer a dedução de todos os schemas — e, pior, daria um resultado
    # diferente se alguém acrescentasse um intent entre duas listas.
    server.catalogo = para_mcp(catalogo_tools() + list(TOOLS_CATALOGO))

    @server.list_tools()
    async def list_tools():
        return [
            mt.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in server.catalogo
        ]

    @server.call_tool()
    async def call_tool(nome: str, argumentos: dict | None):
        argumentos = dict(argumentos or {})

        # `entrada` e a FRASE DO PRODUTOR, e e' o canal que faltava.
        #
        # Porque e' de topo e nao dentro de `args`: o `sandbox` le-a de
        # `meta`, nunca de `params`. Deixá-la em `args` faria com que um
        # handler a tratasse como um campo do domínio — e `cadastrar_funcionario`
        # a preencheria com o nome do vaqueiro, porque "sim" e' o primeiro
        # campo vazio.
        entrada = str(argumentos.pop("entrada", "") or "").strip()
        meta = {"entrada": entrada} if entrada else {}

        # O catalogo e' leitura de codigo: nao toca em nada, e por isso nao
        # passa pelo sandbox nem entra na trilha de auditoria. Uma trilha com
        # 400 leituras de catalogo e 3 accoes esconde as 3.
        if nome in NOMES_CATALOGO:
            return [
                mt.TextContent(
                    type="text",
                    text=_texto(
                        await _no_thread(executar_catalogo, user, nome, argumentos)
                    ),
                )
            ]

        if nome in server.bloqueio:
            return [
                mt.TextContent(
                    type="text",
                    text=(
                        f"A tool {nome} altera dados e este servidor esta em "
                        "modo leitura. Suba com --permitir-escrita para liberar."
                    ),
                )
            ]

        return [
            mt.TextContent(
                type="text",
                text=_texto(
                    await _no_thread(executar_para, user, nome, argumentos, **meta)
                ),
            )
        ]

    @server.list_resources()
    async def list_resources():
        return [
            mt.Resource(
                uri=f"amplia://contexto/{usuario}",
                name="Contexto do produtor",
                description="O que já existe na fazenda — para a IA não propor duplicata.",
                mimeType="text/plain",
            ),
            mt.Resource(
                uri="amplia://modelos",
                name="Modelos de tela",
                description=(
                    "As telas que valem a pena montar, com os widgets de cada uma. "
                    "Leia ANTES de desenhar: inventar um nome de modelo ou de "
                    "widget é a forma mais rápida de a tela nascer errada."
                ),
                mimeType="application/json",
            ),
            mt.Resource(
                uri="amplia://widgets",
                name="Dicionário de widgets",
                description=(
                    "O que cada widget mede e se o número é medido ou gerado. "
                    "`fonte_dado: simulado` significa que o valor é inventado e "
                    "não serve para decidir."
                ),
                mimeType="application/json",
            ),
            mt.Resource(
                uri="amplia://fontes",
                name="Fontes medidas",
                description=(
                    "De onde vem cada número — e o que NÃO tem número.\n\n"
                    "Leia antes de responder com uma contagem. As "
                    "culturas existem em duas fontes (a tabela e o "
                    "config) e dão números diferentes; este recurso "
                    "diz as duas e diz qual é a que a tela mostra.\n\n"
                    "`campos_que_faltam` lista o que está VAZIO — janela "
                    "de plantio, ciclo, chave de mercado. Vazio não é "
                    "zero: é 'ninguém escreveu'. Um agente que derive "
                    "esses números está a inventar a data de plantio "
                    "de um produtor.\n\n"
                    "Todo número traz `fonte` e `quando`."
                ),
                mimeType="application/json",
            ),
            # NOVO. As SKIs de domínio (`app/ia/skills/amplia-*.md`) estavam
            # escritas desde o BUILD e nenhuma superfície as lia — nem MCP,
            # nem HTTP. Um agente que não as lê conhece `praga_ai_foto` pelo
            # nome e erra o que ela mede. Domainar um recurso que já existe no
            # repositório é a melhoria mais barata de toda esta lista.
            mt.Resource(
                uri="amplia://skills",
                name="SKIs de domínio",
                description=(
                    "As três especialidades declaradas do AmplIA (campo, "
                    "finanças, IoT), com os intents que cada uma cobre. Leia "
                    "antes de escolher uma tool de agronomia."
                ),
                mimeType="application/json",
            ),
            mt.Resource(
                uri="amplia://capacidades",
                name="O que a AmplIA sabe fazer",
                description=(
                    "O catálogo de capacidades derivado do código: o que cada "
                    "intent faz, que campos pede, e se altera dados."
                ),
                mimeType="application/json",
            ),
            mt.Resource(
                uri="amplia://blocos",
                name="Blocos do Chamado Amplia",
                description=(
                    "Os tipos de bloco que a IA pode CONSTRUIR (texto, kpi, "
                    "grafico, tabela, planilha), os campos de cada um, e ONDE "
                    "ela pode escrever. Leia antes de `amplia_chamado_criar`."
                ),
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri):
        from app.amplia_mcp import skills as _skills
        from app.ia.paginas import MODELOS, referencia_widgets, summarise_catalogo

        u = str(uri)

        # O mesmo motivo de `call_tool`: os resources que tocam a base de
        # dados precisam da thread. `contexto` e `capacidades` consultam o
        # usuario; sem isto, um `amplia://capacidades` devolvia a mesma
        # excepção que uma tool, e o agente ficava sem o catálogo.
        if u == "amplia://modelos":
            return json.dumps(
                {
                    "modelos": [
                        {
                            "id": k,
                            "titulo": m["titulo"],
                            "para_quem": m["para_quem"],
                            "widgets": m["widgets"],
                            "depende": m["depende"],
                        }
                        for k, m in MODELOS.items()
                    ],
                    "resumo": summarise_catalogo(),
                },
                ensure_ascii=False,
            )

        if u == "amplia://widgets":
            return json.dumps(referencia_widgets(), ensure_ascii=False)

        if u == "amplia://blocos":
            from app.amplia_mcp import catalogo_blocos

            return json.dumps(catalogo_blocos(), ensure_ascii=False)

        if u == "amplia://skills":
            return json.dumps(_skills.catalogo_skis(), ensure_ascii=False)

        if u == "amplia://fontes":
            # As fontes MEDIDAS: de onde vem cada numero, e o que esta
            # VAZIO. Um agente que responde 'sao 709 culturas' tem de poder
            # dizer de onde as leu — e um agente que diz 'a janela de
            # plantio e' de outubro a marco' tem de ver, aqui, que esse campo
            # nao tem um unico registo preenchido.
            from app.amplia_mcp.fontes import catalogo_de_fontes

            return json.dumps(catalogo_de_fontes(), ensure_ascii=False)

        if u == "amplia://capacidades":
            from app.amplia_mcp.capacidades import catalogo_de_capacidades
            from functools import partial

            # `user=`: o servidor atende UM produtor (`--usuario`, linha 599).
            # Passá-lo é o que faz a lista de capacidades respeitar as culturas
            # que esse produtor escolheu no cadastro. Sem isto, o agente ligado
            # a esta máquina via "liga o aerador quando o mormaço da tilápia
            # passar de 30 °C" a um produtor que só planta soja.
            return json.dumps(
                await _no_thread(partial(catalogo_de_capacidades, user=user)),
                ensure_ascii=False,
            )

        # `amplia://contexto/{usuario}` e o unico URI com parametro. Uma
        # comparacao por igualdade resolveria so o nome do usuario que este
        # servidor atende — que e' sempre o mesmo. Comparar o PREFIXO e o que
        # faz o recurso funcionar para qualquer `amplia://contexto/*`.
        if u.startswith("amplia://contexto/"):
            return await _no_thread(contexto, user)

        # A anterior devolvia `contexto(user)` para QUALQUER URI desconhecido.
        # Um cliente que pede `amplia://contexto` com um typo levava o
        # contexto da fazenda e achava que tinha lido o que pediu. Um recurso
        # que não existe tem de dizer que não existe.
        raise ValueError(
            f"recurso MCP desconhecido: {u!r}. Disponiveis: "
            "amplia://contexto/<usuario>, amplia://modelos, amplia://widgets, "
            "amplia://blocos, amplia://skills, amplia://capacidades, "
            "amplia://fontes"
        )

    # ============================ PROMPTS =============================
    # A terceira superficie do MCP, e a que faltava. `tools` diz o que se
    # pode chamar, `resources` o que se pode ler; `prompts` diz o que se
    # PEDE. Sem ela, um agente chega as 79 tools sem saber duas coisas que o
    # codigo ja sabe: que escrita pede confirmacao, e que um nome inventado
    # volta com `sugestoes` em vez de falhar em silencio.
    #
    # `Server(instructions=GUIA)` (acima) e' o texto fixo que o host le no
    # Initialize. Um prompt e' melhor que isso num caso especifico: e'
    # pedido, e a resposta pode mudar com o codigo. O `amplia_ferramentas`
    # lista os nomes verdadeiros a cada pedido — e' o mesmo texto que
    # `vocabulario()` devolve, pelo mesmo motivo.
    # =====================================================================
    @server.list_prompts()
    async def list_prompts():
        from mcp.types import Prompt

        return [
            Prompt(name=p["name"], description=p["description"])
            for p in _prompts.catalogo_prompts()
        ]

    @server.get_prompt()
    async def get_prompt(nome: str, argumentos: dict | None = None):
        from mcp.types import GetPromptResult, PromptMessage, TextContent

        texto = _prompts.montar(nome)
        if texto is None:
            # Prompt inexistente tem de ser erro explicito. Uma string vazia
            # seria lida pelo cliente como "existe mas nao diz nada", que e
            # pior do que nao existir.
            disponiveis = ", ".join(p["name"] for p in _prompts.catalogo_prompts())
            raise ValueError(
                f"prompt MCP desconhecido: {nome!r}. Disponiveis: {disponiveis}"
            )
        return GetPromptResult(
            description=f"AmplIA: {nome}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=texto),
                )
            ],
        )

    import anyio

    async def main():
        async with stdio_server() as (leitura, escrita):
            await server.run(leitura, escrita, server.create_initialization_options())

    anyio.run(main)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="amplia-mcp",
        description="Servidor MCP do AmplIA (stdio). Tools = intents do AmplIA, "
        "executadas pelo sandbox.",
    )
    p.add_argument(
        "--usuario", required=True, help="username do produtor que a IA vai atender"
    )
    p.add_argument(
        "--permitir-escrita",
        action="store_true",
        help="libera as tools que alteram dados (padrao: somente leitura)",
    )
    p.add_argument(
        "--settings",
        default="",
        help="DJANGO_SETTINGS_MODULE (padrao: prod se AMPLIA_PROD=1, senao dev)",
    )
    a = p.parse_args(argv)
    return rodar(a.usuario, a.permitir_escrita, a.settings)


if __name__ == "__main__":
    raise SystemExit(main())
