r"""
coerencia.py — a pergunta que ninguem estava a fazer: o que a camada
publica e' verdade?

POR QUE ISTO E' UM FICHEIRO E NAO MAIS UM TESTE
-----------------------------------------------

A camada tem testes para cada comportamento isolado: o contrato publica
`required` (`ContratoTest`), o leitor sobrevive a BOM (`SkillsTest`), o CSRF
passa (`CsrfRealTest`). Todos verdes. E, durante meses, a camada teve um
`expectedFailure` a dizer que 15 de 15 handlers declarados nas SKIs nao
existiam — enquanto o `/tools/` respondia 200 com 78 tools a dizer que sim.

E' o padrao que a EXPERIENCIA DE HOJE exIU:
cada porta estava certa sobre o que dizia, e nenhuma sabia o que a outra
dizia.

Um contrato e' uma promessa feita a alguem que nao esta na sala. O
`/tools/` promete que `amplia_x` existe; o `exec` e' que tem de a saber
executar; o `amplia://skills` promete que aquele handler existe; o guia
promete que `confirm: true` funciona. **Cada promessa e' verdade isoladamente.
O que falha e' a relacao entre elas.**

Por isso o ficheiro expoe UMA funcao, `verificar()`, que responde a uma lista
fechada de perguntas, e devolve o que falhou — nao um booleano. Um booleano
que da `False` nao diz aonde olhar; uma lista diz.

O QUE ELE NAO E'
----------------

Nao e' um duplicar dos testes de comportamento. Nao volta a testar se
`confirm` abre a confirmation gate — isso e' `ContratoTest`. Ele testa se as
**afirmacoes que a camada faz sobre si mesma** batem com o codigo. E' a
diferenca entre testar uma funcao e testar uma documentacao, e a segunda e'
que estava por testar.

O QUE DA' PARA FAZER COM ISTO
------------------------------

Corrido a partir de `/api/amplia/diagnostico/` (`coerencia` na resposta) e de
`scripts/verificar_mcp_amplia.py`. Uma falha aqui e' uma promessa que o
servidor fez e nao cumpriu — que e' a unica classe de bug que um cliente nao
consegue diagnosticar sozinho, porque ele acredita no servidor.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import re
from typing import Any

#: A mesma fonte única que o `sandbox.py` usa para limpar o prompt de
#: confirmação. Duas cópias do mesmo padrão é ter uma delas errada — e a
#: anterior tinha `startswith`, que não apanha "INSTRUÇÃO IA (ML):".
from app.ia.texto import RE_INSTRUCAO

#: O que o servidor promete, escrito a mao DE PROPOSITO.
#:
#: A lista de perguntas e' deste ficheiro e nao do `contrato.py` de proposito:
#: se as duas vivessem juntas, uma pergunta apagada em conjunto com a
#: capacidade que a motivava desapareceria sem ninguem notar. Aqui a pergunta
#: esta escrita, e o que se apaga e' a resposta — que e' a coisa que se quer
#: ver falhar.
#:
#: A 11a pergunta e' A PRIMEIRA A CORRER, e nao por estetica: as outras
#: dez sao todas RELATIVAS — comparam o MCP com o REGISTO, as tools com as
#: rotas, o guia com o contrato. Se um catalogo de `app/ia/registro.py`
#: falhar a importar, o REGISTO encolhe E o MCP encolhe com ele, e cada
#: comparação relativa continua a dar "certo". Foi o que aconteceu, medido:
#: 76 intents caíram para 44 sem uma única pergunta vermelha.
PREGUNTAS = (
    "todo catalogo de intents carregou (nenhum foi omitido em silencio)",
    "toda tool de `tools` existe no catalogo de intents ou e' de catalogo",
    "toda tool de `tools` tem rota: `exec` sabe executar o nome",
    "toda tool de escrita declara `confirm` e nao o poe em `required`",
    "todo campo obrigatorio e' aceitavel pelo schema que o declara",
    "toda intent do registo chega ao cliente como tool",
    "toda SKI declarada aponta para handlers que existem",
    "todo URI de recurso anunciado pelo servidor MCP e' legivel",
    "o guia afirma `confirm` e o contrato declara `confirm`",
    "as duas linguagens (MCP e OpenAI) publicam as mesmas tools",
    "`vocabulario()` lista exatamente os nomes de `TOOLS_CATALOGO` + intents",
    # As duas ultimas sao as unicas que NAO sao relativas: comparam o que a
    # descricao PROMETE com o que o handler FAZ. As onze de cima dizem que
    # o catalogo esta coerente consigo mesmo — e um catalogo pode ser
    # perfeitamente coerente e descrever uma capacidade que nao existe.
    "a descricao que promete accao e' a accao que o handler faz",
    "nenhuma tool marcada so'-leitura promete accao na descricao",
)

#: Índice da pergunta que tem de correr primeiro. Um número, e não a
#: posição, para que acrescentar uma pergunta no fim não a desloque.
P_INTEGRIDADE = 0


def _todas_as_tools() -> list[dict[str, Any]]:
    from app.amplia_mcp import TOOLS_CATALOGO, catalogo_tools

    return catalogo_tools() + list(TOOLS_CATALOGO)


def verificar() -> dict[str, Any]:
    """Corre as perguntas todas. Devolve as que falharam, com o motivo.

    Nunca levanta. Um verificador que rebenta nao e' um verificador: quando o
    que falha e' uma importacao circular ou um import partido, quem o corre
    precisa de ler a resposta — e um traceback nao responde a pergunta que
    ficou por fazer.
    """
    resultados: list[dict[str, Any]] = []
    for pergunta in PREGUNTAS:
        try:
            ok, detalhe = _responder(pergunta)
        except Exception as e:  # noqa: BLE001 — o verificador nao pode rebentar
            ok, detalhe = False, f"o verificador em si falhou: {type(e).__name__}: {e}"
        resultados.append({"pergunta": pergunta, "ok": ok, "detalhe": detalhe})

    falhadas = [r for r in resultados if not r["ok"]]
    return {
        "perguntas": len(resultados),
        "falhou": len(falhadas),
        "tudo_ok": not falhadas,
        # As falhas FIRST: quem abre isto num terminal tem dez segundos antes
        # de perder a paciencia, e a pergunta que falhou e' a unica coisa que
        # precisa de ler.
        "falhas": [
            {"pergunta": r["pergunta"], "detalhe": r["detalhe"]} for r in falhadas
        ],
        "respostas": resultados,
    }


def _responder(pergunta: str) -> tuple[bool, str]:
    """Uma pergunta, uma resposta. A tabela e' um dicionario de funcoes.

    Dicionario e nao `if` encadeado porque a pergunta e' a chave: e' o que
    permite ao `LOG` e a um humano citar a pergunta pelo nome, e nao por uma
    posicao numa cadeia de ifs que muda quando alguem acrescenta um caso.
    """
    from app.amplia_mcp import NOMES_CATALOGO, TOOLS_CATALOGO, nome_tool
    from app.amplia_mcp.contrato import (
        GUIA,
        PARAM_CONFIRMACAO,
        enriquecer,
        para_mcp,
        para_openai,
    )
    from app.ia.registro import REGISTO

    bruto = _todas_as_tools()
    completo = enriquecer(bruto)

    tabela = {
        PREGUNTAS[0]: _todo_catalogo_carregou,
        PREGUNTAS[1]: _toda_tool_e_do_catalogo,
        PREGUNTAS[2]: _toda_tool_tem_rota,
        PREGUNTAS[3]: _escrita_declara_confirm,
        PREGUNTAS[4]: _obrigatorio_e_satisfazivel,
        PREGUNTAS[5]: _toda_intent_chega,
        PREGUNTAS[6]: _skis_apontam_para_o_que_existe,
        PREGUNTAS[7]: _todo_uri_e_legivel,
        PREGUNTAS[8]: _guia_bate_com_o_contrato,
        PREGUNTAS[9]: _as_duas_linguagens_concordam,
        PREGUNTAS[10]: _vocabulario_bate_com_o_catalogo,
        PREGUNTAS[11]: _capacidade_e_honesta,
        PREGUNTAS[12]: _read_only_nao_promete_accoa,
    }
    fn = tabela.get(pergunta)
    if fn is None:
        return (
            False,
            "pergunta sem resposta implementada — o verificador mente por omissao",
        )
    return fn(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO)


# --------------------------------------------------------------------------
# As perguntas
# --------------------------------------------------------------------------


#: Verbo que promete ACÇÃO. Não é classification de intenção — é o oposto:
#: a lista do que a descrição FAZ, e o que a check confronta com o que o
#: handler FAZ. Sem acentos, porque as descrições são escritas sem.
_VERBO_ACCAO = re.compile(
    r"\b(automatiz\w*|trava\w*|aciona\w*|dispara\w*|executa\w*|liga\w*|"
    r"desliga\w*|programa\w*|aplica\w*|move\w*|cobra\w*|manda\w*|imp\w*|"
    r"abre\w*|fecha\w*|semeia\w*|configura\w*)\b",
    re.I,
)

#: Descrições que dizem claramente que a capacidade é de CONSULTA. Uma
#: tool que lista pode ser alias de outra que lista — não há dishonesty nisso.
_E_CONSULTA = re.compile(
    r"\b(lista\w*|consult\w*|mostra\w*|resumo\w*|quais|quantos)\b", re.I
)


#: Um EXEMPLO de como se pergunta, entre aspas, não é uma promessa.
#:
#: `alertas_telemetria` tem a descrição:
#:     INSTRUÇÃO IA: use para 'alertas dos sensores', 'alarmes disparados'.
#:     Só leitura.
#: "disparados" é um particípio dentro de um EXEMPLO: descreve o alarme que já
#: disparou, não uma acção que a tool vá executar. A primeira versão destas
#: checks acusou-a — e com razão, do ponto de vista dela, e sem razão nenhuma.
#: A descrição tem duas partes comromiseiros diferentes: o que a tool FAZ, e
#: como se PERGUNTA por ela. Só a primeira promete.
_EXEMPLO_ENTRE_ASPAS = re.compile(r"'[^']*'|\"[^\"]*\"")

#: Um handler para onde este delega que é de CONSULTA. Delegar para aqui e
#: chamar-lhe "automatizar" é a mentira que estas checks caçam.
#:
#: `_semear_regra` NÃO entra: semear É a acção que a descrição promete, e
#: partilhar um helper entre oito handlers legítimos não é dishonesto.
_ALVO_DE_CONSULTA = re.compile(r"(listar|lista|regras_auto|resumo|consulta)", re.I)


def _sem_exemplos(descricao: str) -> str:
    """A descrição sem os exemplos entre aspas: só o que a tool FAZ."""
    return _EXEMPLO_ENTRE_ASPAS.sub(" ", str(descricao or ""))


def _primeira_palavra(descricao: str) -> str:
    """A primeira palavra significativa da descrição, já sem o prefixo de
    instrução e sem os exemplos entre aspas.

    Porque a PRIMEIRA palavra e não a primeira ocorrência: a diferença entre
    uma promessa e uma enumeração.

        "Configura a regra que liga o aerador"   -> primeira = "Configura"
        -> promete acção. É assim que se escreve uma capacidade.

        "…+ últimas safras + aplicações"          -> a acção não é a primeira
        -> "aplicações" é um SUBSTANTIVO: as aplicações que o histórico
        mostra. `aplica\\w*` casava e acusava uma tool de leitura de mentir.

    Uma descrição que promete uma acção começa por nomear a acção. Uma que
    enumera o que mostra, não.
    """
    texto = _sem_exemplos(descricao)
    # tira o prefixo "INSTRUÇÃO IA: ..." se sobrar
    m = RE_INSTRUCAO.match(texto.strip())
    if m:
        texto = texto.strip()[m.end() :]
    palavras = re.findall(r"[A-Za-zÀ-ÿ]+", texto)
    return palavras[0].lower() if palavras else ""


def _promete_accoa(descricao: str) -> str:
    """A acção que a descrição promete ser o QUE ELA FAZ, ou vazio."""
    primeira = _primeira_palavra(descricao)
    if not primeira or _E_CONSULTA.search(primeira):
        # "Lista", "Consulta", "Mostra", "Resumo": promete consultar, não agir.
        return ""
    if _VERBO_ACCAO.match(primeira):
        return primeira
    return ""


def _handler_delega_a_outro(handler) -> str:
    """Nome do handler para o qual este delega, se apenas delega.

    Só quando o corpo É o `return`: um handler que faz trabalho E depois
    chama outro não é um alias, e tratá-lo como alias daria um falso
    positivo. É a forma que o defeito tinha — uma linha só.
    """
    try:
        src = inspect.getsource(handler)
    except (OSError, TypeError):
        return ""
    linhas = [
        l.strip()
        for l in src.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    # descarta o `def` e o docstring
    corpo = [l for l in linhas if not l.startswith(("def ", '"""', "'''"))]
    corpo = [l for l in corpo if not (l.startswith('"') or l.startswith("'"))]
    if len(corpo) != 1:
        return ""
    m = re.match(r"^return (_\w+)\(", corpo[0])
    return m.group(1) if m else ""


def _capacidade_e_honesta(bruto, completo, REGISTO, *_):
    """A descrição promete acção e o handler só reencaminha?

    O defeito que esta check caça: um handler que é uma linha e delega para
    outro handler de OUTRO nome, enquanto a descrição promete automating
    ("Automatizar Moba ... +R$660k"). A IA respondia "feito" e nada acontecia.

    Medido antes da correcção: 8 dos 9 `automatizar_*` eram exactamente isto.
    Nenhum mudava uma linha na base — `RegraAlertaTelimetria` 0→0,
    `IotEndpoint` 0→0, `ComandoDevice` 0→0.

    A regra do "e' mesmo uma alias" tem uma excepção deliberada: um alias
    CUJA descrição diz que consulta não é mentira. `automatizar_regras` é
    `_automatizar_regras_auto` e diz "Lista automações" — é honesto, e a
    check tem de o deixar em paz.
    """
    mentiras = []
    for nome, spec in sorted(REGISTO.items()):
        descricao = (spec or {}).get("descricao") or ""
        verbo = _promete_accoa(descricao)
        if not verbo:
            continue
        handler = (spec or {}).get("handler")
        if handler is None:
            continue
        delegado = _handler_delega_a_outro(handler)
        # Só é mentira se reencaminha para uma CONSULTA. Delegar para um
        # helper partilhado que faz o que a descrição promete ("_semear_regra")
        # e oito handlers honestos a partilhar código, não uma mentira.
        if delegado and _ALVO_DE_CONSULTA.search(delegado):
            mentiras.append(
                f"{nome}: descrição promete '{verbo}' mas o handler só "
                f"reencaminha para `{delegado}`, que é de consulta"
            )
    if mentiras:
        return False, "; ".join(mentiras)
    return True, f"nenhuma capacidade promete acção e não a faz ({len(REGISTO)} vistas)"


def _read_only_nao_promete_accoa(bruto, completo, REGISTO, *_):
    """O contrato diz "seguro, pode chamar" e a descrição diz outra coisa?

    `x-read-only` vem das flags. As flags são o que o `sandbox.somente_leitura`
    e o `contrato.enriquecer` usam, e é a única coisa que um cliente MCP lê
    antes de decidir se chama. Uma tool com `x-read-only: true` e uma
    descrição a prometer acção dá ao modelo DOIS sinais opostos — e o que
    ganha para a decisão de segurança é o `x-read-only`.

    O resultado não é a tool fazer mal: é o produtor acreditar que
    automatizou e não agir. O prejuízo é a OMISSÃO, que é silenciosa.
    """
    ferramentas = {t.get("x-intent"): t for t in completo if t.get("x-intent")}
    contradictions = []
    for nome, spec in sorted(REGISTO.items()):
        t = ferramentas.get(nome)
        if t is None or not t.get("x-read-only"):
            continue
        verbo = _promete_accoa((spec or {}).get("descricao") or "")
        if verbo:
            contradictions.append(
                f"{nome}: x-read-only=true mas a descrição promete '{verbo}'"
            )
    if contradictions:
        return False, "; ".join(contradictions)
    return True, (
        f"nenhuma tool marcada só-leitura promete acção ({len(ferramentas)} vistas)"
    )


def _todo_catalogo_carregou(bruto, completo, REGISTO, *_):
    """Nenhum catálogo de intents foi omitido em silêncio.

    POR QUE ESTA PERGUNTA E' A PRIMEIRA, E POR QUE EXISTE
    ---------------------------------------------------
    As outras dez perguntam coisas RELATIVAS: o MCP bate com o REGISTO? as
    tools batem com as rotas? o guia bate com o contrato? Uma comparação
    relativa dá "certo" quando as duas pontas caem juntas.

    Foi assim que 76 intents passaram a 44 sem ninguém ver: três catálogos
    (`intents.py`, `iot_intents.py`, `dinamico_intents.py` — este último é
    todo o Criador Livre) falharam a importar, o `registro.py` engole o erro
    num `except: continue` sem log, e o MCP encolheu com o registo. Todas as
    dez perguntas acima continuaram verdes.

    A PERGUNTA NÃO É "QUANTAS INTENTS HÁ"
    -----------------------------------
    A primeira versão desta check usava um número fixo (`ESPERADO = 76`).
    Durou vinte minutos: outra sessão adicionou quatro intents e o número
    ficou errado — o health check passou a acusar um bug que não existia.

    Um total escrito à mão é um contador de CPD: muda com cada feature nova,
    e um alarme que dispara em cada feature é um alarme que ninguém lê.

    A pergunta que não envelhece é **qual catálogo devia ter carregado e não
    carregou?** — derivada por introspecção em `registro._catalogos_esperados`,
    sem nenhum número escrito à mão. Resposta: `registro.saude()["integro"]`.
    """
    from app.ia import registro as reg
    from app.ia.texto import RE_INSTRUCAO

    s = reg.saude()
    if s["integro"]:
        return (
            True,
            f"{s['catalogos_carregados']}/{s['catalogos_esperados']} catálogos, "
            f"{s['intents']} intents",
        )

    return (
        False,
        f"{len(s['falhou'])} catálogo(s) NÃO carregou(am): {', '.join(s['falhou'])}. "
        f"O REGISTO tem {s['intents']} intents e a IA está cega para tudo o que "
        f"esses catálogos deviam dar. Motivo: "
        f"{'; '.join(f'{k}: {v}' for k, v in s['falhas'].items()) or '(sem motivo registado)'}",
    )


def _toda_tool_e_do_catalogo(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO):
    from app.amplia_mcp import nome_tool

    de_intent = {t["name"] for t in bruto if t.get("x-intent")}
    for_tools = {t["name"] for t in TOOLS_CATALOGO}
    orfas = de_intent - {nome_tool(n) for n in REGISTO}
    return (
        not orfas,
        f"{len(orfas)} tools com x-intent que nao existe no registo: {sorted(orfas)}"
        if orfas
        else f"{len(de_intent)} de intents + {len(for_tools)} de catalogo",
    )


def _toda_tool_tem_rota(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO):
    """A promessa mais importante, e a que ninguém verificava.

    `/tools/` diz ao modelo "estas são as tuas mãos". Se `exec` não souber
    executar um nome que veio nessa lista, o modelo foi informado de uma
    capacidade que não existe — e recebe `tool_fora_do_catalogo` a tentar
    usá-la. Não há erro visível: há um 200 com `ok: false`, que um cliente
    trata como resultado.

    A allowlist de `exec` é `NOMES_CATALOGO` ∪ (o que `executar_para`
    aceita). Um nome que chegue a `/tools/` e não esteja em nenhum dos dois é
    uma mão que o catálogo promete e o router não conhece.
    """
    from app.amplia_mcp import nome_tool

    nomes = {t["name"] for t in bruto}
    conhecidos = set(NOMES_CATALOGO) | {nome_tool(n) for n in REGISTO}
    sem_rota = sorted(nomes - conhecidos)
    return (
        not sem_rota,
        f"{len(sem_rota)} tools sem rota em /exec/: {sem_rota}"
        if sem_rota
        else f"{len(nomes)} tools, todas com rota",
    )


def _escrita_declara_confirm(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO):
    from app.amplia_mcp.contrato import PARAM_CONFIRMACAO

    sem_confirm, confirm_obrigatorio = [], []
    for t in completo:
        if t.get("x-read-only"):
            continue
        props = t["inputSchema"].get("properties") or {}
        if PARAM_CONFIRMACAO not in props:
            sem_confirm.append(t["name"])
        if PARAM_CONFIRMACAO in (t["inputSchema"].get("required") or []):
            confirm_obrigatorio.append(t["name"])
    problemas = []
    if sem_confirm:
        problemas.append(f"sem 'confirm' declarado: {sem_confirm}")
    if confirm_obrigatorio:
        # Confirmar antes de ter feito tornaria a escrita impossível: e' o que
        # transforma um segundo passo num passo que nunca chega.
        problemas.append(f"'confirm' em 'required': {confirm_obrigatorio}")
    return (
        not problemas,
        "; ".join(problemas) or "todas as escritas declaram confirm, e nenhuma o exige",
    )


def _obrigatorio_e_satisfazivel(
    bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO
):
    maus = []
    for t in completo:
        props = t["inputSchema"].get("properties") or {}
        for campo in t["inputSchema"].get("required") or []:
            if campo not in props:
                maus.append(f"{t['name']}.{campo}")
    return (
        not maus,
        f"obrigatorios que o schema proibe: {maus}"
        if maus
        else f"{sum(1 for t in completo if t['inputSchema'].get('required'))} tools com obrigatorios, todos aceitaveis",
    )


def _toda_intent_chega(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO):
    publicadas = {t.get("x-intent") for t in bruto if t.get("x-intent")}
    faltam = sorted(set(REGISTO) - publicadas)
    return (
        not faltam,
        f"{len(faltam)} intents que nao chegam ao cliente: {faltam}"
        if faltam
        else f"as {len(REGISTO)} intents chegam como tool",
    )


def _skis_apontam_para_o_que_existe(
    bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO
):
    from app.amplia_mcp.skills import catalogo_skis

    cat = catalogo_skis()
    if cat["handlers_fantasmas"]:
        return (
            False,
            f"{cat['handlers_fantasmas']} handlers de SKI que nao existem: "
            + ", ".join(f"{s['nome']}={s['cobre_inexistente']}" for s in cat["skills"]),
        )
    # E o inverso tambem: uma promessa que ja tem botao e' um alias a mais,
    # e uma lista que so cresce e' uma lista que apodrece.
    ja_existe = [
        f"{s['nome']}.{k}"
        for s in cat["skills"]
        for k in (s.get("prometido_sem_botao") or {})
        if k in REGISTO
    ]
    return (
        not ja_existe,
        f"promessas que ja tem intent: {ja_existe}"
        if ja_existe
        else f"{cat['total']} SKIs, todos os handlers existem; "
        f"{cat['promessas_sem_botao']} nomeadas sem botao, todas com morada",
    )


def _todo_uri_e_legivel(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO):
    """O que o servidor ANUNCIA tem de ser legível.

    Um recurso anunciado e ilegível é um erro que o cliente só descobre quando
    o precisa — e um cliente MCP não tem como listar o que não está em
    `list_resources`. Anunciar é uma promessa como qualquer outra.

    Feito por **AST**, e nao por correr o servidor: `list_resources` é uma
    corrotina dentro de uma função que precisa de `django.setup()`, de um
    `User` no banco e do SDK `mcp` instalado. Arrancar o servidor para
    confirmar uma lista de strings seria um teste que falha por falta de
    dependencias e não por culpa do código.

    E AST em vez de ler o texto pela doutrina D7: o docstring do `servidor.py`
    *nomeia* os recursos que descreve, e um teste que o lesse passaria por ter
    encontrado a lista no comentário.
    """
    # Caminho ABSOLUTO, resolvido a partir deste ficheiro. Com um caminho
    # relativo, a pergunta dava "nao existe" sempre que o teste corresse fora
    # da raiz do projecto — um alarme falso que trains o olho a ignorar a
    # pergunta, que e' o pior sitio para um teste de integridade ficar.
    fonte = pathlib.Path(__file__).resolve().parents[2] / "app" / "amplia_mcp" / "servidor.py"
    if not fonte.exists():
        return (
            False,
            "app/amplia_mcp/servidor.py nao existe — a camada perdeu o servidor",
        )

    arvore = ast.parse(fonte.read_text(encoding="utf-8"))

    def _uris_da_funcao(nome_da_funcao: str) -> set[str] | None:
        """Os `uri=` literais de todos os `mt.Resource(...)` dentro da função.

        `None` quando a função não existe — que é diferente de existir sem
        recursos, e a diferença é o que separa "não sei" de "não há".
        """
        for no in ast.walk(arvore):
            if not _e_funcao(no) or no.name != nome_da_funcao:
                continue
            uris = set()
            for sub in ast.walk(no):
                if not (isinstance(sub, ast.Call) and _nome(sub.func) == "Resource"):
                    continue
                for kw in sub.keywords:
                    if kw.arg == "uri" and isinstance(kw.value, ast.Constant):
                        if isinstance(kw.value.value, str):
                            uris.add(kw.value.value)
            return uris
        return None

    def _tratados_por_read_resource() -> set[str] | None:
        """Os prefixos que `read_resource` sabe responder.

        Uma string comparada com `startswith` e' um prefixo, e a string toda
        e' um prefixo de si propria. As duas entram: um `== "amplia://skills"`
        e' um `startswith("amplia://skills")` disfarçado.
        """
        for no in ast.walk(arvore):
            if not _e_funcao(no) or no.name != "read_resource":
                continue
            achados = set()
            for sub in ast.walk(no):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if sub.value.startswith("amplia://"):
                        achados.add(sub.value)
                elif (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "startswith"
                    and sub.args
                    and isinstance(sub.args[0], ast.Constant)
                    and isinstance(sub.args[0].value, str)
                ):
                    achados.add(sub.args[0].value)
            return achados
        return None

    anunciado = _uris_da_funcao("list_resources")
    if anunciado is None:
        return False, "servidor.py nao tem `list_resources` — MCP moderno exige-o"

    tratados = _tratados_por_read_resource()
    if tratados is None:
        return False, "servidor.py nao tem `read_resource` — anuncia e nao entrega"

    # `amplia://contexto/<usuario>` e' anunciado com f-string, e por isso nao
    # aparece como literal. Entra a mao, e a mao e' verificada: tem de haver um
    # `startswith` que a cubra.
    contexto = "amplia://contexto/"
    if contexto not in tratados:
        return False, f"'{contexto}' e' anunciado mas `read_resource` nao o reconhece"

    ilegiveis = sorted(
        u
        for u in anunciado
        if u != contexto and not any(u.startswith(p) for p in tratados)
    )
    return (
        not ilegiveis,
        f"anunciados e nao servidos: {ilegiveis}"
        if ilegiveis
        else f"{len(anunciado)} recursos anunciados, todos servidos",
    )


def _e_funcao(no) -> bool:
    """`async def` produz `AsyncFunctionDef`, nao `FunctionDef`.

    Todos os handlers do servidor MCP sao `async`. Uma verificacao que so
    olhe para `FunctionDef` diz que `list_resources` nao existe num ficheiro
    onde esta escrito — que e' a pior resposta que um verificador pode dar:
    mente com confianca, e o leitor perde o fio em vez de procurar o defeito.
    """
    return isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))


def _nome(node) -> str:
    """`mt.Resource` -> `Resource`. O `ast.Attribute` tem o nome em `.attr`."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _guia_bate_com_o_contrato(bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO):
    """O guia é texto, e texto envelhece. Isto diz se ainda é verdade."""
    from app.amplia_mcp.contrato import GUIA, PARAM_CONFIRMACAO

    if PARAM_CONFIRMACAO not in GUIA:
        return False, "o guia nao menciona 'confirm', e o contrato obriga a confirmar"
    escritas = [t for t in completo if not t.get("x-read-only")]
    return True, f"o guia menciona '{PARAM_CONFIRMACAO}' e ha {len(escritas)} escritas"


def _as_duas_linguagens_concordam(
    bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO
):
    from app.amplia_mcp.contrato import para_mcp, para_openai

    por_mcp = [t["name"] for t in para_mcp(bruto)]
    por_openai = [t["function"]["name"] for t in para_openai(bruto)]
    if por_mcp != por_openai:
        so_mcp = sorted(set(por_mcp) - set(por_openai))
        so_openai = sorted(set(por_openai) - set(por_mcp))
        return False, f"divergem. so MCP={so_mcp[:5]} so OpenAI={so_openai[:5]}"
    return True, f"as duas linguagens publicam as mesmas {len(por_mcp)} tools"


def _vocabulario_bate_com_o_catalogo(
    bruto, completo, REGISTO, NOMES_CATALOGO, TOOLS_CATALOGO
):
    """O `/vocabulario/` é o que o modelo de 1,7 B realmente lê.

    E' o ficheiro de menorjanela do sistema, e por isso o mais provavel de
    divergir: cabe em ~2 500 chars porque foi cortado, e o que foi cortado
    pode ter sido um nome. Um nome de intent fora do vocabulário é um nome que
    a IA não sabe que existe — que é a falha que a conversa do produtor
    apanhou.
    """
    from app.amplia_mcp import vocabulario

    v = vocabulario()
    texto = v.get("texto", "")
    faltam = sorted(n for n in REGISTO if n not in texto)
    return (
        not faltam,
        f"{len(faltam)} intents fora do vocabulario: {faltam}"
        if faltam
        else f"os {len(REGISTO)} nomes chegam ao modelo em {v.get('chars')} chars",
    )
