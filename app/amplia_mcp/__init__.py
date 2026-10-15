r"""
amplia_mcp — BUILD 0: a camada que dá BRAÇOS governados à IA que raciocina.

O PROBLEMA QUE ISTO RESOLVE
---------------------------
Até agora a AmplIA tinha dois cérebros separados e nenhuma mão segura:

1. `app/ia/intents*.py` — 65 intents da primeira versão, com sandbox e auditoria.
   Rigorosos. Mas não raciocinam: casam regex.
2. `app/static/js/ia-local/ia-local.js` — WebLLM rodando **no navegador**
   (SmolLM2-1.7B, com Qwen2-0.5B de reserva). Raciocina de verdade. Mas as
   "mãos" eram `iaToolCall`, uma function em JavaScript que fazia isso:

       if (tool === 'irrigacao') {
         await apiFetch('/api/iot/comandos/', { method: 'POST', ... });
       }

   Ou seja: uma IA capaz de acionar uma **válvula de irrigação** fazia isso
   por HTTP direto, sem passar por `sandbox.executar()`. Sem `needs_confirm`,
   sem linha em `IAExecucao`, sem verificação de flag de capacidade. E o
   parsing da chamada era `text.match(/\{[^]*"tool"[^]*\}/)`, que casa o
   primeiro `{` com o último `}` do texto.

A separação entre "quem pensa" e "quem age" é o que allows uma IA powerful sem
uma porta dos fundos. Este módulo é a porta: as mãos passam a ser as mesmas
tools que os intents da primeira versão já usam, com o mesmo caminho de execução.

O QUE ESTE MÓDULO FAZ — E O QUE ELE PROMETE NÃO FAZER
-----------------------------------------------------
Expõe as 65 intents como tools tipadas, e não inventa um segundo catálogo.
Uma tool daqui NÃO é uma função que este módulo implementa: é um `intent` do
catálogo existente, executado por `sandbox.executar(via="mcp")`. Isso significa
que toda tool herda, sem código novo:

  * verificação de flag de capacidade (`clima.read`, `irrigacao.write`);
  * `needs_confirm` — ação de escrita vira pedido de confirmação, não fato;
  * `parece_injecao` — tentativa de sequestrar o prompt vira estado neutro;
  * trilha de auditoria — cada chamada vira `IAExecucao` com entrada, flags,
    fontes e duração;
  * escopo de usuário — as queries do intent já são filtradas porwhichever
    `user` é passado.

E o que continua PROIBIDO, por construção (diretriz 2 do mapa):

  * nenhum `eval`/`exec` — uma tool é um intent do catálogo, não código;
  * nenhum `.py` gerado — nada aqui escreve arquivo;
  * nenhuma tool inventada por request — o nome precisa existir no catálogo,
    senão 404. Um LLM não consegue pedir uma ferramenta que não está no catálogo,
    mesmo que peça com convicção.

Este módulo é a implementação da Etapa 1 do roadmap de
`docs/mcp-Ampliagro_amplIA.md`: a ponte entre a IA e o contexto Django. A
Etapa 2 (motor dinâmico) já está pronta em `app/ia/dinamicos.py` + os models
`Dynamic*`, e este catálogo a inclui como tools — o que significa que a IA já
consegue "criar ferramenta" e "registrar" pelas mesmas mãos governadas.
"""

from __future__ import annotations

import difflib
from typing import Any

#: Prefixo das tools. Sem prefixo, "criar" do LLM colidiria com uma tool de um
#: cliente MCP qualquer hospedado na mesma sessão.
PREFIXO = "amplia_"

#: Teto de caracteres por descrição de tool. Existe porque um catálogo sem teto
#: cresce até partir a janela de contexto de quem o lê — e quem o lê aqui é um
#: SmolLM2 de 1,7 B. Ver `vocabulario` para o orçamento do prompt, que é o
#: número que decide se a IA consegue agir.
LIMITE_DESCRICAO = 900


def nome_tool(nome_intent: str) -> str:
    return f"{PREFIXO}{nome_intent}"


def intent_de_tool(nome: str) -> str | None:
    """Inverte `nome_tool`. Devolve None se não for uma tool nossa."""
    if not nome or not nome.startswith(PREFIXO):
        return None
    interno = nome[len(PREFIXO) :]
    # "amplia_" sozinho nao e uma tool: sem nome, o nome de intent seria "" e
    # o catalogo-iframe la embaixo receberia um intent inexistente.
    return interno or None


def _com_aviso(descricao: str, aviso: str, limite: int = LIMITE_DESCRICAO) -> str:
    """Junta o aviso de capacidade ao texto sem que o teto o possa cortar.

    O defeito que isto fecha (FILA #28)
    ----------------------------------
    A primeira versão fazia `(descricao + aviso)[:900]`. O aviso fica no FIM
    — era a última coisa a ser cortada. Uma descrição com mais de 900
    caracteres publicava a tool de escrita como se fosse de leitura, e o
    modelo aprendia que "ALTERA dados" é uma decoração que às vezes não
    está lá.

    Quando o limite apertar, o que se sacrifica é a descrição, que é
    redundante com o nome. Nunca o aviso, que é o aviso.
    """
    if not aviso:
        return descricao[:limite]
    if len(descricao) + len(aviso) <= limite:
        return descricao + aviso
    sobra = max(limite - len(aviso), 0)
    return descricao[:sobra].rstrip() + aviso


def sugerir_tools(nome: str, limite: int = 5) -> list[str]:
    """Os nomes REAIS de tool mais parecidos com o que foi pedido.

    Porque isto existe (FILA #27)
    ------------------------------
    Um LLM pequeno não erra o nome por acaso: repete o que lhe disseram que
    era uma tool. A resposta "tool fora do catalogo: 'amplia_irrigacao'" não
    lhe diz o que escrever a seguir, e o produtor fica a ver um erro de
    máquina em vez de uma resposta.

    Com as sugestões, a mesma falha vira uma segunda tentativa correcta — sem
    rede, sem servidor novo e sem tocar no cliente.

    Devolve o NOME COMPLETO com prefixo, porque é isso que o modelo tem de
    escrever. E usa `difflib`, não um mapa escrito à mão: um mapa escrito à
    mão é uma lista para se esquecer de acrescentar, e foi exactamente uma
    lista escrita à mão — o system prompt do `ia-local.js`, com 13 nomes
    dos quais 0 existem — que custou um turno inteiro de tool calls inúteis.
    """
    from app.ia.sandbox import INTENTS

    if not nome:
        return []
    interno = nome[len(PREFIXO) :] if nome.startswith(PREFIXO) else nome
    if not interno:
        return [nome_tool(n) for n in sorted(INTENTS)[:limite]]
    parecidos = difflib.get_close_matches(interno, list(INTENTS), n=limite, cutoff=0.5)
    return [nome_tool(n) for n in parecidos]


# --------------------------------------------------------------------------
# Schema das tools
# --------------------------------------------------------------------------


def _schema_de_params(intent: str) -> dict[str, Any]:
    """Deduz o schema JSON dos parâmetros a partir dos exemplos do intent.

    Não há introspecção de assinatura no catálogo: `INTENTS` guarda
    `exemplos` e um `handler`, não os parâmetros. Deduzir dos exemplos é uma
    aproximação — e é declarada como tal, porque um schema errado faz o modelo
    errar a chamada, e um schema ausente faz ele passar tudo como string.

    Onde o exemplo traz `{"talhao": 3}` o campo é inteiro; onde traz
    `{"talhao": "3A"}` é string. Um parametro que só aparece como string mas
    o nome sugere número (id, qtd, _id) ainda é declarado string: errar para
    string é recuperável pelo handler, errar para int descarta informação.
    """
    from app.ia.sandbox import INTENTS

    spec = INTENTS.get(intent) or {}

    # BUILD 2: schema declarado tem precedencia sobre o deduzido. Quando a
    # intent escreve `params_schema`, ele e' a fonte da verdade: foi escrito
    # para ser o contrato da tool, e nao um subproduto de exemplos.
    declarado = spec.get("params_schema")
    if declarado:
        return {
            "type": "object",
            "properties": dict(declarado),
            "additionalProperties": False,
        }

    props: dict[str, Any] = {}
    for exemplo in spec.get("exemplos", []) or []:
        if not isinstance(exemplo, dict):
            continue
        # a chave "_entrada" é a frase do usuário, não um parâmetro
        for chave, valor in exemplo.items():
            if chave.startswith("_"):
                continue
            if chave not in props:
                if isinstance(valor, bool):
                    tipo = "boolean"
                elif isinstance(valor, int):
                    tipo = "integer"
                elif isinstance(valor, float):
                    tipo = "number"
                else:
                    tipo = "string"
                props[chave] = {"type": tipo}

    return {
        "type": "object",
        "properties": props,
        # additionalProperties False: o LLM não inventa campo, e um campo
        # a mais é descartado e listado em `descartadas` pelo validador.
        "additionalProperties": False,
    }


def _aviso_de_capacidade(flags, leitura: bool) -> str:
    """Texto de capacidade que o modelo lê. Não pode mentir.

    `sandbox.somente_leitura` é fail-closed de propósito: intent que não
    declara flag nenhuma é tratado como potencialmente escrito. Isso está
    certo para segurança, mas a consequência é que `ajuda` — que só lista o que
    o sistema sabe fazer — chega a ser classificada como escrita.

    Se a descrição daqui dissesse "ALTERA dados" para uma tool de consulta, o
    modelo receberia um aviso falso toda vez que o produtor pedisse "o que
    você sabe fazer", e aprenderia a ignorar avisos de capacidade — que é
    exatamente o que tornaria o aviso inútil quando IMPORTASSE.

    Três casos, ditos com precisão:
      * flag de escrita presente  -> aviso forte
      * sem flag nenhuma          -> diz que nao declarou, sem afirmar que escreve
      * só leitura                -> sem aviso
    """
    if leitura:
        return ""
    tem_flag = bool(flags)
    if tem_flag:
        return " ATENCAO: esta tool ALTERA dados e pode pedir confirmacao."
    return (
        " ATENCAO: esta tool nao declarou flag de capacidade, entao o sistema a "
        "trata como escrita e pode pedir confirmacao."
    )


def catalogo_tools() -> list[dict[str, Any]]:
    """As tools que a AmplIA pode chamar, no formato MCP (`inputSchema`).

    Só leitura e escrita andam juntos na lista; o que as separa é a flag, e é
    a flag que o sandbox consulta. Ocultar as de escrita do modelo não impede
    a chamada — tornaria a tool invisível em vez de protegida, e a proteção
    precisa ser real, não cosmética.
    """
    from app.ia.sandbox import INTENTS, somente_leitura

    saida: list[dict[str, Any]] = []
    for nome in sorted(INTENTS):
        spec = INTENTS[nome] or {}
        flags = list(spec.get("flags", []) or [])
        leitura = somente_leitura(spec)
        descricao = (spec.get("descricao") or spec.get("desc") or "").strip()
        if not descricao:
            descricao = f"Intent `{nome}` do AmplIA."
        aviso = _aviso_de_capacidade(flags, leitura)
        saida.append(
            {
                "name": nome_tool(nome),
                "description": _com_aviso(descricao, aviso),
                "inputSchema": _schema_de_params(nome),
                # metadados proprios: o MCP ignora chaves extras, mas um
                # cliente nosso sabe ler antes de tentar chamar.
                "x-intent": nome,
                "x-flags": flags,
                "x-read-only": leitura,
            }
        )
    return saida


def catalogo_legivel() -> list[dict[str, Any]]:
    """Mesmo catálogo, sem as chaves `x-` (para o LLM ler como texto)."""
    saida = []
    for t in catalogo_tools():
        saida.append(
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
        )
    return saida


# --------------------------------------------------------------------------
# A unica porta de execucao
# --------------------------------------------------------------------------


def executar_para(user, nome: str, args: dict[str, Any] | None = None, **meta):
    """Executa uma tool. É a ÚNICA porta de saída deste módulo.

    Não há caminho que execute um intent sem passar por aqui, e `aqui` é
    `sandbox.executar`. Se alguém precisar contornar, o código de revisão tem
    um único lugar onde olhar.

    `via` fica fixo em "mcp" para a trilha de auditorio saber de onde veio a
    chamada — é o que permite responder "o que essa IA fez às 14h?" sem
    adivinhar.
    """
    from app.ia.sandbox import executar

    intent = intent_de_tool(nome)
    if intent is None:
        return {
            "ok": False,
            "erro": f"tool desconhecida: {nome!r}",
            "codigo": "tool_desconhecida",
            # Sem prefixo e' o caso mais comum: o modelo esqueceu o
            # `amplia_`. Dizer "tool desconhecida" e calar-se deixava-o
            # repetir o mesmo nome no escuro; a sugestao da-lhe a forma
            # correcta logo a seguir.
            "sugestoes": sugerir_tools(nome),
        }

    # A allowlist e' o CATALOGO, nao o prefixo. Sem esta checagem,
    # "amplia_deleta_tudo" passava no teste de prefixo e chegava ao sandbox
    # com um intent que nao existe. Um modelo pequeno inventa nome de tool com
    # conviccao; o servidor tem de recusar pelo catalogo, nao pelo formato.
    from app.ia.sandbox import INTENTS

    if intent not in INTENTS:
        return _recusa_de_tool(nome, len(INTENTS))
    if user is None or not getattr(user, "is_authenticated", False):
        # nem chega a checar o catalogo: sem usuario nao ha a quem responder
        return {"ok": False, "erro": "usuario obrigatorio", "codigo": "sem_usuario"}

    # SEGUNDA LINHA DE DEFESA (A3). O `ia-local.js` ja nao fabrica `dados`
    # (a correcao do lado do cliente), mas o cliente NAO e fronteira: e um
    # ficheiro que o produtor pode ter em cache, um modulo que pode estar
    # desactualizado no tablet dele, ou outra coisa a chamar este endpoint. Se
    # chegar um valor marcadamente automatico, nao e o produtor que o pediu —
    # e nao se grava.
    #
    # Fica aqui, e nao la dentro do `sandbox`, porque este e' o unico ponto de
    # saida do modulo: e aqui que a recusa fica registada com `origem: cliente`
    # antes de chegar a qualquer logica de escrita.
    fabricado = _dado_fabricado(args or {}, intent)
    if fabricado:
        return fabricado

    return executar(user, intent, args or {}, via="mcp", meta=meta or None)


def _sem_acento(t: str) -> str:
    """Minúsculas, sem acento, espaços normalizados.

    Escrito com `unicodedata` e sem literais acentuados de propósito: o valor
    fabricarado vinha do cliente em português, e comparar texto acentuado
    literal é uma fonte de bugs difícil de ver.
    """
    import unicodedata as _ud

    decomposed = _ud.normalize("NFKD", t or "")
    base = "".join(c for c in decomposed if not _ud.combining(c))
    return " ".join(base.lower().split())


# Marcadores de "valor que ninguém escreveu". Comparados SEM acento.
_MARCADORES_FABRICADOS = ("novo", "nova")

# Os valores EXACTOS que o `ia-local.js` produzia, para os recursos que ele
# conhecia. Enumerados em vez de tentados por regra.
#
# Podia parecer mais esperto casar o valor com o nome do recurso em vez de ter
# uma lista. Não pode: o português não pluraliza por acrescentar um `s`
# (`operacao` -> `operacoes`), e qualquer regra de pluralização aqui erra para
# um dos lados — ou deixa passar lixo, ou recusa o nome que um produtor deu
# legalmente a uma coisa sua. Uma lista explícita é auditável e não tem falsos
# positivos: nenhum produtor chama uma safra de "Novo safras".
_FABRICADOS_CONHECIDOS = frozenset(
    f"{m} {r}"
    for r in (
        # plural: o `map3` do cliente usava a chave, ja no plural
        "safras",
        "talhoes",
        "operacoes",
        "funcionarios",
        "insumos",
        "maquinerios",
        "animais",
        "culturas",
        "propriedades",
        "estoque",
        # singular: o ramo `criar` + `opera` emitia "Nova operacao"
        "safra",
        "talhao",
        "operacao",
        "funcionario",
        "insumo",
        "maquinario",
        "animal",
        "cultura",
        "propriedade",
    )
    for m in _MARCADORES_FABRICADOS
)


def _dado_fabricado(args: dict[str, Any] | None, intent: str) -> dict[str, Any] | None:
    """Recusa um valor que o CLIENTE fabricou em vez de o ter perguntado.

    Porque isto existe. O `fallbackIntent` do `ia-local.js` emitia, para
    qualquer frase que combinasse "criar" com um nome de recurso, uma
    tool de ESCRITA assim:

        {"tool": "criar", "args": {"recurso": "safras",
                                   "dados": {"nome": "Novo safras"}}}

    Na altura o servidor recusava por outro motivo — `amplia_criar` não estava no
    catalogo. Ou seja: a protecao estava la por ACIDENTE, nao por desenho. Bastava
    alguém adicionar a tool ao catálogo e o cliente passava a gravar registos
    chamados "Novo safras", sem os campos obrigatórios, sem o produtor pedir, e
    sem ele os ver aparecer. O cliente já foi corrigido; esta é a segunda linha.

    Porque o padrão é apertado e não uma lista de palavras proibidas: só recusa
    valores de EXATAMENTE duas palavras, cujo primeiro termo é "novo"/"nova" e
    cujo segundo é o próprio nome do recurso que se vai gravar. Um produtor que
    escreva "Nova Vida" não é recusado. Um "Novo talhoes" é — porque ninguém
    escreve o slug plural do recurso como nome de uma coisa sua.

    Nota de desenho: isto NÃO substitui o `needs_confirm`. Uma escrita legítima
    continua a passar por confirmação do produtor; esta regra só barra o que
    nenhum produtor pediu.
    """
    dados = (args or {}).get("dados")
    if not isinstance(dados, dict):
        return None

    alvo = _sem_acento(intent).replace("_", " ")
    if not alvo:
        return None

    for chave, valor in dados.items():
        if not isinstance(valor, str):
            continue
        partes = _sem_acento(valor).split()
        if len(partes) != 2:
            continue
        if partes[0] not in _MARCADORES_FABRICADOS:
            continue
        # `valor_norm` e' a frase toda normalizada ("nova operacao"), que e' o
        # que o conjunto conhece. Comparar so a segunda palavra nao casava com
        # nada — o conjunto tem as frases, nao os segundos termos.
        valor_norm = " ".join(partes)
        segundo = partes[1]
        # O valor tem de ser um marcador CONHECIDO, ou casar com o slug do
        # intent que se vai gravar (para um recurso novo que o cliente nao
        # conhecia). `alvo` pode ter varias palavras, por isso compara-se termo
        # a termo.
        if valor_norm not in _FABRICADOS_CONHECIDOS and segundo not in alvo.split():
            continue
        return {
            "ok": False,
            "codigo": "dado_fabricado",
            "erro": (
                f"'{chave}' chegou como \"{valor}\", que e' um marcador de "
                f"valor automatico e nao um dado do produtor. Nada foi gravado. "
                f"Pergunte o valor ao produtor."
            ),
            # Para a trilha: isto e' o cliente a fabricar, nao o produtor a
            # pedir algo estranho. A distincao importa se um dia isto vira
            # bug de produto em vez de bug de agente.
            "origem": "cliente",
            "intent": intent,
            "chave": chave,
        }
    return None


def _recusa_de_tool(nome: str, total: int) -> dict[str, Any]:
    """A recusa de um nome que não existe, com o caminho de recuperação.

    O caso `sugestoes: []` é o que esta função trata com mais cuidado.
    Nomes como `navegar` — que é o que a persona antiga ensinava — não têm
    nada parecido no catálogo, porque **não existe**: navegar não é uma
    acção do agente, é mexer num endereço. Uma lista vazia deixava o modelo
    a tentar outra vez, porque "não sei" e "não há nada parecido" são coisas
    diferentes e só uma delas está escrita.

    Por isso, lista vazia vem com a frase que fecha o ciclo: não há nada
    parecido, não repitas o nome, diz ao produtor o que não consegues fazer.
    Sem isso, o defeito medido (FILA #27) regressava pela porta do fundo —
    não por chamar uma tool errada, mas por a chamar até o produtor desistir.
    """
    sugestoes = sugerir_tools(nome)
    erro = f"tool fora do catalogo: {nome!r}"
    if not sugestoes:
        erro += (
            ". Nao ha nenhuma ferramenta parecida com este nome — nao repitas o "
            "nome: diz ao produtor o que nao consegues fazer."
        )
    return {
        "ok": False,
        "erro": erro,
        "codigo": "tool_fora_do_catalogo",
        "sugestoes": sugestoes,
        "total_tools": total,
        # A chave que o cliente lee para nao tratar "vazio" como "ainda nao
        # carregou". Sem isto, uma lista vazia e uma resposta em silencio
        # são indistinguiveis do ponto de vista do modelo.
        "parece_erro_de_nome": True,
    }


# --------------------------------------------------------------------------
# O vocabulario — o que o modelo local consegue mesmo saber
# --------------------------------------------------------------------------
# O defeito que isto fecha (FILA #27)
# ----------------------------------
# O `IA_SYSTEM` em `static/js/ia-local/ia-local.js` ensinava ao modelo local
# uma lista escrita à mao: `navegar`, `consultar`, `criar`, `irrigacao`,
# `excluir`... Treze nomes. MEDIDO: as treze sao fantasmas — nenhuma existe
# no catalogo. E as verdadeiras nao estavam em lado nenhum do prompt.
#
# Consequencia medida, ponta a ponta, por HTTP: toda a tool call que o modelo
# local conseguia escrever voltava `tool_fora_do_catalogo`. Nao era uma tool
# que as vezes falhava — era a ponte inteira entre o modelo e as maos cortada.
#
# `/api/amplia/tools/` devolvia os schemas correctos (34 KB) e nenhum codigo
# no repositorio os consumia. O servidor tinha razao e a pagina nao ouvia.
#
# POR QUE ISTO E' DERIVADO E NAO ESCRITO
# --------------------------------------
# Um mapa escrito à mao e' uma lista para se esquecer de acrescentar, e a
# forgoreira desta classe de defeito foi exactamente uma lista escrita à mao.
# Aqui a lista nao existe: sai do `INTENTS` a cada chamada. Um intent novo
# aparece no vocabulario sem ninguem editar este ficheiro.
#
# POR QUE E' COMPACTO
# ------------------
# O catalogo completo sao ~8 700 tokens. O modelo que o ia ler e' um SmolLM2
# de 1,7 B, com janela de 4 096. Nao cabia — e mesmo que coubesse, 78 schemas
# atravessam um modelo que ja levava 1 200 tokens de contexto do sistema e
# seis mensagens de historico. Um modelo pequeno nao escolhe bem entre 78
# opcoes; escolhe mal entre 78 e depois inventa uma.
#
# O que fica de fora e' deliberado: os `args` de cada tool. Estao no catalogo
# completo, que existe para quem o aguente. Aqui o modelo precisa de uma
# coisa so — o nome certo — e errar no nome e' o que produz o fantasma.


def _namespace(spec: dict[str, Any]) -> str:
    """O primeiro `FLAG.NAMESPACE`, que e' o assunto da tool.

    `clima.read` -> `clima`. Serve para por `ligar_irrigador` ao lado de
    `desligar_irrigador` sem que ninguem mantenha a ordem numa lista.

    Um intent sem flag nenhuma vai para `_`. E' o caso que `somente_leitura`
    trata como escrita — e por isso nunca aparece sob "LEITURA" aqui.
    """
    flags = spec.get("flags") or []
    if not flags:
        return "_"
    return str(flags[0]).split(".")[0] or "_"


def _grupos() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """`(leitura, escrita)` agrupadas por namespace de flag.

    A separacao e' a de `somente_leitura`, a mesma que o sandbox consulta — a
    que decide quem paga confirmacao. Uma tool na coluna errada aqui esta na
    coluna errada la, e o produtor perde o aviso.
    """
    from app.ia.sandbox import INTENTS, somente_leitura

    leitura: dict[str, list[str]] = {}
    escrita: dict[str, list[str]] = {}
    for nome in sorted(INTENTS):
        spec = INTENTS[nome] or {}
        alvo = leitura if somente_leitura(spec) else escrita
        alvo.setdefault(_namespace(spec), []).append(nome)
    return leitura, escrita


def _linha_grupo(rotulo: str, nomes: list[str], limite: int = 300) -> str:
    """Uma linha `assunto: a, b, c`, ou o que couber mais um aviso do resto.

    Nao cortamos a lista a meio sem dizer. Um nome truncado e um nome que nao
    existe sao indistinguiveis para quem tenta usa-lo — e e' o modelo pequeno
    que vai tentar.

    Os nomes sao JA COM O PREFIXO. Parece redundante — o texto repete
    `amplia_` trenta vezes — e e' essa a razao de estar. O nome que o modelo
    escreve tem de ser o nome exacto, e um texto que ensina o nome sem
    prefixo de um lado e pede o prefixo do outro produz metade das chamadas
    erradas. No browser o normalizador aceita os dois
    (`if (!nome.startsWith('amplia_')) nome = 'amplia_' + nome`), por isso o
    nome completo nao custa nada la e e' o unico que funciona num cliente
    MCP, que nao normaliza nada.
    """
    completos = [nome_tool(n) for n in nomes]
    lista = ", ".join(completos)
    if len(lista) <= limite:
        return f"{rotulo}: {lista}"

    usados: list[str] = []
    # `+2` e' o ", " que cada nome acrescentado traz consigo.
    usado = len(rotulo) + 2
    for nome in completos:
        if usado + len(nome) + 2 > limite:
            break
        usados.append(nome)
        usado += len(nome) + 2

    restantes = len(completos) - len(usados)
    if not usados:
        # Namespace com nomes giganticamente longos: o rotulo sozinho ja
        # comeu o orcamento. Devolve o rotulo, que ainda diz o assunto.
        return f"{rotulo}: (nomes omitidos — leia /api/amplia/tools/)"
    return (
        f"{rotulo}: {', '.join(usados)}"
        f" (+{restantes} — leia /api/amplia/tools/ para o resto)"
    )


def vocabulario(user=None, limite: int = 3200) -> dict[str, Any]:
    """O texto que o modelo local recebe no system prompt.

    Cabe em `limite` caracteres de proposito: o orcamento e' do modelo que
    le, nao do servidor que escreve. Passar um numero deixa quem chama
    decidir conforme o modelo que tem — um SmolLM2 de 1,7 B e um modelo de
    servidor nao tem a mesma janela, e o texto serve os dois.
    """
    leitura, escrita = _grupos()

    blocos: list[str] = [
        "FERRAMENTAS DA AMPLIA — escreva o nome EXATAMENTE como esta aqui.",
        "",
        "LEITURA (respondem sem perguntar nada):",
    ]
    for rotulo, nomes in leitura.items():
        blocos.append(_linha_grupo(f"  {rotulo}", nomes))
    blocos += [
        "",
        "ESCRITA (mudam dados; o servidor vai pedir confirmacao ao produtor — "
        "so chame quando o produtor pedir):",
    ]
    for rotulo, nomes in escrita.items():
        blocos.append(_linha_grupo(f"  {rotulo}", nomes))
    blocos += [
        "",
        'COMO CHAMAR: {"tool": "amplia_<nome_acima>", "args": {...}}',
        "Um nome que nao esta nesta lista NAO EXISTE. Escolha o mais proximo "
        "e chame com esse nome.",
    ]

    texto = "\n".join(blocos)
    cortado = len(texto) > limite
    if cortado:
        # O corte so pode comer o fim — as regras de "como chamar" sao as
        # ultimas, e sem elas o modelo sabe os nomes e nao sabe o formato.
        #
        # E o corte DIZ que cortou. Um vocabulario truncado que parece completo
        # e' uma mentira por omissao com a forma de um facto: o modelo le a
        # lista, conclui que e' tudo o que existe, e fica com as ferramentas
        # que faltaram como se nunca tivessem existido. E' a mesma razao pela
        # qual um widget sem dado mostra "sem dado" (D2) e um numero sem
        # fonte vale `None` (D1).
        marca = (
            "\n[LISTA INCOMPLETA: falta(m) ferramenta(s). Peça "
            "/api/amplia/tools/ ou /api/amplia/vocabulario/ com mais limite]"
        )
        orcamento = limite - len(marca)
        texto = texto[: max(orcamento, 0)].rsplit("\n", 1)[0] + marca

    return {
        "texto": texto,
        "cabe": not cortado,
        "chars": len(texto),
        "limite": limite,
        # A soma dos NOMES, nao o numero de namespaces. `len(leitura)` e' o
        # numero de assuntos — que e' o que a lista mostra, nao o que a IA
        # pode chamar. Um total que nao bate com o catalogo e' um numero em
        # que ninguem pode confiar, e e' pior do que nenhum.
        "total": sum(len(v) for v in leitura.values())
        + sum(len(v) for v in escrita.values()),
        "namespaces": len(leitura) + len(escrita),
        # A estrutura, para um cliente que montar o prompt sozinho em vez de
        # colar o texto. Mesmo dado, nunca uma segunda lista.
        "leitura": leitura,
        "escrita": escrita,
    }


# --------------------------------------------------------------------------
# Contexto (a "visao" da IA)
# --------------------------------------------------------------------------


def contexto(user, limite: int = 1200) -> str:
    """O que a IA precisa de saber ANTES de responder.

    Duas coisas, e a segunda faltava.

    1. **O que existe no sistema do produtor** — as propriedades, as
       ferramentas que ele já criou. É o `Resource` do roadmap MCP: antes
       de a IA propor uma ferramenta nova, lê o que já existe.

    2. **O que a AmplIA sabe fazer** — as capacidades, o que cada uma
       pede, e a distinção entre registar uma PESSOA e registar uma COISA.

    A segunda é a que faltava, e a ausência dela é a origem de uma
    conversa real. Um produtor perguntou "como se cadastrar" e recebeu o
    cadastro de MÁQUINAS. A capacidade de registar uma pessoa existia, com
    handler e com exemplos — mas este `contexto()` devolvia 31 caracteres a
    dizer "Propriedades: Sitio Santa Clara", e a IA não tinha onde
    descobrir o resto. Adivinhava, e adivinhava máquina.

    Nenhum dos dois cabeçalhos é decorativo: a IA precisa dos DOIS. Sem o
    segundo não sabe o que pode fazer; sem o primeiro não sabe o que já
    está feito.
    """
    from app.hierarquia import propriedades_visiveis

    partes: list[str] = []

    # MEDIDO 2026-10-05. Estes tres `except Exception: pass` eram o pior
    # caso da lista toda, e nao por causa do silencio — por causa do que
    # FAZEM a seguir.
    #
    # No fim da funcao ha `if not partes: return "Sem dados de contexto"`.
    # E um `except: pass` nao engole nada: ele CONSTRUI esse estado. A IA
    # recebe a string "Sem dados de contexto para este usuario" e conclui
    # que este produtor nao tem propriedade nenhuma. O que aconteceu foi um
    # `OperationalError` — uma coluna em falta a meio de uma migracao.
    #
    # E o pior de todos, porque este texto vai para o MODELO. O painel
    # mente a um produtor; aqui a mentira entra na cabeca de uma IA que vai
    # responder a esse produtor como se fosse verdade. Um produtor que pede
    # "quais sao as minhas propriedades" recebe "nao tem nenhuma" — e
    # desiste. Nao ha forma de ele desconfiar, porque a resposta parece
    # uma leitura de base, e nao e'.
    #
    # Este era o bug do painel que dizia "sem dado" sem ter feito fetch,
    # a versao que se alimenta a si mesma.
    #
    # A correccao: o contexto nao pode ser silenciosamente incompleto.
    # Registado o que falhou e DITO no contexto.
    def _falhou(rotulo, exc):
        import logging

        logging.getLogger(__name__).error(
            "contexto_para_ia: nao foi possivel ler %s (%s). O contexto "
            "vai sair incompleto, e a IA vai receber isso como se fosse "
            "uma leitura de base.",
            rotulo,
            type(exc).__name__,
            exc_info=True,
        )
        partes.append(
            f"[INDISPONIVEL: {rotulo} nao pode ser lido neste momento — "
            f"isto NAO e' 'nao tens isto', e' 'nao consegui verificar']"
        )

    try:
        props = list(propriedades_visiveis(user).values_list("nome", flat=True)[:10])
        if props:
            partes.append("Propriedades: " + ", ".join(props))
    except Exception as exc:
        _falhou("as propriedades", exc)

    try:
        from app.models import DynamicApp

        apps = list(
            DynamicApp.objects.filter(user=user)
            .exclude(estado="ARQUIVADO")
            .values_list("nome", flat=True)[:20]
        )
        if apps:
            partes.append("Ferramentas que voce já criou: " + ", ".join(apps))
    except Exception as exc:
        _falhou("as ferramentas que ja criaste", exc)

    # O QUE SABE FAZER. Vem antes de qualquer outra coisa, porque é o que
    # impede a adivinhação — e a adivinhação é o defeito.
    try:
        from app.amplia_mcp.capacidades import (
            catalogo_de_capacidades,
            indice_pessoa_maquina,
        )

        cat = catalogo_de_capacidades()
        partes.append(f"O QUE SABE FAZER: {cat['total']} capacidades")
        pm = indice_pessoa_maquina()
        nomes_p = [x["capacidade"] for x in pm["pessoas"]]
        nomes_c = [x["capacidade"] for x in pm["coisas"]]
        if nomes_p:
            partes.append("PESSOAS: " + ", ".join(nomes_p))
        if nomes_c:
            partes.append("COISAS: " + ", ".join(nomes_c))
        if nomes_p or nomes_c:
            partes.append(
                "PESSOA pede `cargo` (vaqueiro, tratorista); "
                "COISA pede `tipo` (trator, colheitadeira). `nome` é comum "
                "às duas — perguntar `tipo` a quem disse 'vaqueiro' leva ao "
                "cadastro de um camião."
            )
    except Exception as exc:
        # Ver a nota em `_falhou`: este era o pior dos tres. Perdia
        # exatamente a parte do contexto que diz a IA o que PODE fazer,
        # que e' o que impede a adivinhanca.
        _falhou("o catalogo de capacidades", exc)

    if not partes:
        return "Sem dados de contexto para este usuario."

    texto = " | ".join(partes)
    return texto[:limite]


# ==========================================================================
# ETAPA 2 — o "Construtor de UI" do roadmap, exposto como ferramenta
# ==========================================================================
# As 79 intents acima são mãos: a IA age sobre a fazenda. Estas são olhos e
# catálogo: a IA vê o que existe e decide o que mostrar.
#
# A ETAPA 2 do roadmap pedia, textualmente, "o interpretador que lê esses
# modelos e desenha a tela (Construtor de UI)". Metade disso estava por fazer —
# o interpretador existe (`app/ia/palco.py`), mas não era legível de fora. Um
# agente externo via 79 mãos e nenhuma pista de que havia tela a desenhar.
#
# São DUAS tools, e não cinco, por uma razão: cada tool extra é uma coisa que
# um LLM de 1.7B tem de escolher certo. `amplia_desenhar_pagina` aceita o nome
# de um modelo; quem quiser saber quais existem, ou o que cada widget mede,
# pergunta — e a resposta vem do mesmo catálogo. Duas portas para um dicionário
# éAlready o bastante; cinco seria cinco ways de errar o mesmo caminho.
# --------------------------------------------------------------------------

#: As tools de catálogo. Não entram em `catalogo_tools()` porque não são
#: intents: são leituras de um catálogo, e não devem aparecer como "ações que a
#: AmplIA sabe fazer" na lista de capacidades — seria fundir o que o sistema
#: CONSEGUE com o que o sistema SABE QUE CONSEGUE.
TOOLS_CATALOGO = (
    {
        "name": "amplia_catalogos",
        "description": (
            "O CATÁLOGO com que uma tela é montada. Chame isto ANTES de tentar "
            "desenhar qualquer página.\n\n"
            "Devolve: `modelos` (as telas que valem a pena montar, com os "
            "widgets de cada uma e o dado de que dependem), `widgets` (o "
            "dicionário: o que existe, o que mede, e se o número é medido ou "
            "gerado), `blocos` (os tipos de peça que pode CONSTRUIR — texto, "
            "kpi, grafico, tabela, planilha — com os campos de cada um), "
            "`zona_escrita` (ONDE pode escrever) e `resumo` (uma frase).\n\n"
            "REGRA DO CATÁLOGO: use widgets com `fonte_dado: medido` por "
            "omissão. Os com `fonte_dado: simulado` devolvem um número GERADO, "
            "sem ligação a esta fazenda — devolvem 200 e parecem bons, e é por "
            "isso que são perigosos. Se usar um, diga que é simulado.\n\n"
            "A ZONA DE ESCRITA tem um preset só, o Chamado Amplia. Nos outros "
            "presets a AmplIA SÓ LÊ. Se o produtor pedir para mudar outro "
            "preset, não o faças: diz que naquele preset a IA só lê e oferece "
            "fazer a mudança no Chamado Amplia.\n\n"
            "Se escrever um número no bloco de texto, esse número tem de estar "
            "numa linha de algum bloco de dado. Se não estiver, o bloco desce a "
            "'sem_dado' e o produtor vê o aviso.\n\n"
            "Chame sem argumentos. Não invente nome de modelo, de widget nem de "
            "bloco: os que não existem nesta lista não existem, e pedir um é a "
            "forma mais rápida de a tela nascer errada."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "apenas_medidos": {
                    "type": "boolean",
                    "description": "Se verdadeiro, devolve só os widgets medidos.",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "amplia_desenhar_pagina",
        "description": (
            "Monta uma tela a partir de um MODELO do catálogo. Os números saem "
            "do banco, com o dono da fazenda no filtro.\n\n"
            "Use `modelo` com um id de `amplia_catalogos.modelos` (ex.: 'cafe', "
            "'panorama', 'financeiro'). Se duvidar do nome, chame o catálogo "
            "primeiro em vez de tentar um nome novo: um modelo inexistente é "
            "devolvido com a lista dos que existem, e a tentativa não passa "
            "despercebida.\n\n"
            "Cada widget volta com `fonte_dado`, que tem TRÊS valores possíveis:\n"
            "  - 'medido'   — o número saiu do banco e serve para decidir.\n"
            "  - 'sem_dado' — não há o que mostrar. O config traz só "
            "`sem_dado: true`.\n"
            "  - 'simulado' — número gerado, sem ligação a esta fazenda.\n\n"
            "Mostre esse carimbo ao produtor. Um 'sem_dado' mostrado como 0 "
            "afirma que a despesa foi zero, e a verdade é que nunca foi "
            "registada nenhuma.\n\n"
            "Não existe parâmetro para pedir um widget simulado: nenhum modelo "
            "os usa. Se o produtor pedir um dado que não existe, diga que não "
            "existe e o que mediria — não aproxime."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "modelo": {
                    "type": "string",
                    "description": "Id do modelo. Vem de `amplia_catalogos`.",
                },
            },
            "required": ["modelo"],
            "additionalProperties": False,
        },
    },
    {
        "name": "amplia_inventario_carbono",
        "description": (
            "Inventário de emissões da propriedade (MRV: Medição, Relatório).\n\n"
            "O QUE ISTO FAZ E O QUE NÃO FAZ — leia antes de responder ao produtor\n"
            "========================\n"
            "Isto MEDE e RELATA. NÃO VERIFICA, e NÃO EMITE CRÉDITO.\n\n"
            "Medição e Relatório é o que dá: um número com a fonte de cada fator "
            "escrita linha a linha (IPCC 2006/2019, MapBiomas/PRODES). Verificação "
            "é o que um corpo acreditado faz — e isso não está aqui, nem pode "
            "estar: verificar é externo por definição.\n\n"
            "Consequência prática: o produtor NÃO PODE vender carbono com este "
            "número, nem usá-lo para compensar obrigação, nem transacioná-lo. "
            "Todo o retorno traz `pode_ser_verificado: false` e um aviso. Se o "
            "produtor pedir crédito de carbono, diga que falta a verificação "
            "externa — não anuncie o número como crédito.\n\n"
            "O QUE É MEDIDO\n"
            "--------------\n"
            "  • Escopo 1 de combustível — diesel em litros, com o fator do IPCC.\n"
            "  • Uso de solo por bioma — desmatamento, com o fator do MapBiomas.\n"
            "  (São só estas duas. Não há mais.)\n\n"
            "O QUE NÃO É MEDIDO — e o que o retorno diz\n"
            "------------------------------------------\n"
            "  • Fertilizante — o fator de N₂O é por kg de N, e o Ampliagro "
            "registra a dose em kg de produto (ou L, ou sc). Falta a composição "
            "do N no schema, e sem ela qualquer número seria um chute com "
            "aparência de medição.\n"
            "  • Escopo 2 (energia comprada) — não há registo de consumo.\n"
            "  • Escopo 3 (cadeia de valor: fabricação, transporte, "
            "distribuição) — não há fator por kg de insumo que sirva a todas as "
            "formulações.\n\n"
            "Escopos 2 e 3 voltam `null`, nunca 0. Zero é um número; `null` é "
            "'não temos este dado'. E o inventário SUBESTIMA — o aviso diz.\n\n"
            "CARBONO NEGATIVO\n"
            "---------------\n"
            "`carbono_negativo` volta SEMPRE `null`. Isto mede emissões, não mede "
            "carbono armazenado no solo, na mata ou em práticas de manejo. Sem "
            "essa medição, dizer que a propriedade é 'neutra' ou 'negativa' é "
            "afirmação sem prova — e é a maior fonte de promessa verde sem "
            "prova que existe.\n\n"
            "COMO CHAMAR\n"
            "----------\n"
            "Chame com `ano`. A propriedade vem do contexto (a do produtor "
            "autenticado). Sem `ano`, use o ano corrente.\n\n"
            "Se o produtor perguntar 'quanto vou ganhar com carbono', a resposta "
            "honesta é que não se ganha nada sem verificação — e que o primeiro "
            "passo é medir, que é o que esta tool faz. Não prometa receita."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ano": {
                    "type": "integer",
                    "description": (
                        "Ano do inventário. Sem este campo, o ano corrente. "
                        "Só há registo de aplicação de insumo a partir da data "
                        "em que foi criado — anos anteriores podem vir vazios."
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "amplia_estado_sistema",
        "description": (
            "O estado MEDIDO do sistema — o que está a funcionar e o que "
            "está partido.\n\n"
            "O QUE ISTO FAZ, E PORQUÊ EXISTE\n"
            "===================================\n"
            "Um agente que perguntasse 'os widgets estão a mostrar os dados?' "
            "não tinha onde olhar: o catálogo diz o que a IA sabe FAZER, não "
            "o que o sistema está A DAR. Esta tool é essa segunda leitura.\n\n"
            "MEDIDO 2026-10-05: o painel dizia 'sem dado' em todos os widgets "
            "e NÃO dava erro nenhum. A causa era uma guarda que lia o cookie "
            "`sessionid` — que é HTTP-only e invisível a `document.cookie`. "
            "A guarda era `false` para TODOS os utilizadores autenticados, "
            "sempre, e por isso os dados nunca eram buscados. Um 'sem dado' "
            "que não é ausência de dado: é ausência de fetch.\n\n"
            "O QUE É MEDIDO\n"
            "--------------\n"
            "Cinco invariantes, que são exactamente os que já partiram:\n\n"
            "  1. `mojibake_js`     — texto com codificação partida nos .js.\n"
            "     MEDIDO: 1658 controlos C1 e 892 pares `Ãƒ` em "
            "pagina-index.js; o rótulo do KPI chegou a tela como "
            "`ÃƒÂrea Total`.\n\n"
            "  2. `guarda_sessao`   — se a guarda de sessão consegue ver a "
            "autenticação.\n"
            "     Se `SESSION_COOKIE_HTTPONLY` é True e a guarda Depends do "
            "cookie, ela é `false` para toda a gente.\n\n"
            "  3. `backends`       — se todo o backend em "
            "`AUTHENTICATION_BACKENDS` tem `get_user`.\n"
            "     MEDIDO: `AxesStandaloneBackend` não tem. Se uma sessão "
            "apontar para ele, dá 500 em todas as páginas.\n\n"
            "  4. `skills`         — handlers declarados que não existem no "
            "registo.\n"
            "     Um handler fantasma é uma tool que o modelo chama e leva "
            "`tool_fora_do_catalogo`.\n\n"
            "  5. `migracoes`     — migrations por aplicar.\n"
            "     MEDIDO: 5 por fazer fizeram o código pedir "
            "`cod_municipio` a uma base sem a coluna, e o "
            "`TenantIsolationMiddleware` desativou-se a si próprio.\n\n"
            "O QUE ESTA TOOL NÃO É\n"
            "-----------------------\n"
            "Não é um painel, e não adivinha. Cada item é lido do ficheiro ou "
            "da base no momento da chamada e traz `ok`, `valor` e `onde`.\n\n"
            "Um item que NÃO FOI MEDIDO vem com `ok: null` e o motivo. "
            "Nunca `true` por omissão — um verificador que dissesse 'tudo "
            "bem' sem ter lido nada seria o mesmo bug do painel que dizia "
            "'IoT: 4' com 8 dispositivos, ao contrário.\n\n"
            "COMO USAR A RESPOSTA\n"
            "----------------------\n"
            "Se `falhas` tiver nomes, o sistema está partido nesses pontos: "
            "diga o que está partido, não tente adivinhar o número. Se "
            "`nao_medidos` tiver nomes, isso NÃO é 'tudo bem' — é "
            "'nãoVERIFYFOU': diga que não mediu.\n\n"
            "`promessas_sem_botao` (neste mesmo ponto, dentro de `skills`) "
            "nomeia lógica que existe mas não tem intent — é honesto, não é "
            "falha. Não chame uma dessas coisas por nome."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "so_falhas": {
                    "type": "boolean",
                    "description": (
                        "Devolve só o que está a falhar e o que não "
                        "mediu. É o que um agente quer primeiro — o que "
                        "passa não precisa de ser lido."
                    ),
                }
            },
            "additionalProperties": False,
        },
    },
)

#: Nomes das tools de catálogo, para as views saberem o que é o quê.
NOMES_CATALOGO = frozenset(t["name"] for t in TOOLS_CATALOGO)


def catalogo_completo(so_medidos: bool = False) -> dict[str, Any]:
    """O dicionário inteiro: modelos + widgets + blocos + zona de escrita.

    Uma tool só, com tudo dentro. A alternativa — uma tool por lista — obriga o
    modelo a fazer três chamadas para montar a mesma tela, e um LLM pequeno
    Called a meio caminho é um LLM pequeno sem catálogo.

    OS BLOCOS FICAM AQUI, E NÃO NUMA TOOL PRÓPRIA
    ===============================================
    Houve uma `amplia_chamado_blocos` separada, e foi removida. O motivo está
    escrito em dois testes que já existiam e que este bloco respeita:

        "Duas, não cinco. Cada tool extra é uma escolha a mais para errar."
        "Uma tool nova apareceu. Cada tool extra é uma escolha a mais para o
         modelo errar — e o contexto já chega."

    A escolha é do produto, e é uma escolha boa: para um SmolLM2 de 1,7B a correr
    na aba, cada tool nova é um nome a mais para ser escolhido mal. O que o
    modelo precisa de saber é o DICIONÁRIO, não mais um botão onde o buscar.

    O bloco continua alcançável sem inchar a tool: `amplia://blocos` é um
    RECURSO, e um recurso não se escolhe — pede-se pelo nome. Quem quer só os
    blocos (um agente que já sabe os modelos) lê o recurso e não paga a janela
    inteira.
    """
    from app.ia import chamado as _chamado
    from app.ia.paginas import MODELOS, referencia_widgets, summarise_catalogo

    return {
        "modelos": [
            {
                "id": chave,
                "titulo": m["titulo"],
                "para_quem": m["para_quem"],
                "widgets": list(m["widgets"]),
                "depende": list(m["depende"]),
                "culturas": list(m["culturas"]),
            }
            for chave, m in MODELOS.items()
        ],
        "widgets": referencia_widgets(somente_medidos=so_medidos),
        "blocos": _chamado.referencia_blocos(),
        "fontes": _referencia_fontes(),
        "zona_escrita": _zona_de_escrita(),
        "resumo": summarise_catalogo() + " " + _chamado.summarise_blocos(),
    }


def _referencia_fontes() -> list[dict[str, Any]]:
    """As fontes de dado dos blocos, derivadas do registo.

    Vem do código e não de uma lista escrita à mão: uma fonte que a IA não
    conhece é uma fonte que a IA inventa, e o resultado é uma tabela com
    números plausíveis e nenhuma consulta por trás.
    """
    from app.ia import chamado_fontes

    return chamado_fontes.referencia_fontes()


def _zona_de_escrita() -> dict[str, Any]:
    """Onde a IA pode escrever. Sai do módulo, nunca de uma lista daqui."""
    from app.ia import chamado

    return {
        "preset": chamado.SLUG_CHAMADO,
        "nome": chamado.NOME_CHAMADO,
        "regra": (
            "A IA escreve SÓ neste preset. Nos restantes, só lê — e a recusa "
            "vem com o motivo e o caminho alternativo, para o produtor saber o "
            "que fazer em vez de ver um 'não'."
        ),
        "operacoes": list(chamado.OPERACOES),
        "max_blocos": chamado.MAX_BLOCOS,
    }


def catalogo_blocos() -> dict[str, Any]:
    """Só os blocos, para o recurso `amplia://blocos`.

    Um recurso não é uma tool: pede-se pelo nome, não se escolhe de um menu. Por
    isso o dicionário dos blocos vive nos DOIS lados — dentro de
    `amplia_catalogos` para quem vai montar uma peça, e aqui para quem já sabe
    os modelos e só quer os blocos, sem pagar a janela inteira.
    """
    from app.ia import chamado

    return {
        "blocos": chamado.referencia_blocos(),
        "zona_escrita": _zona_de_escrita(),
        "resumo": chamado.summarise_blocos(),
    }


def executar_catalogo(user, nome: str, args: dict[str, Any] | None = None) -> dict:
    """A porta das tools de catálogo. Separada de `executar_para` de propósito.

    `executar_para` vai ao `sandbox.executar`, que é o caminho que AUDITA uma
    acção. Um catálogo é uma LEITURA de código — não toca em nada. Metê-lo no
    sandbox faria cada catálogo deixar uma linha de `IAExecucao` por ser lido,
    e o registo de "o que a IA fez" deixaria de ser informação e passava a
    ser ruído. Quando a trilha tem 400 leituras de catálogo e 3 acções, são as
    3 que interessam.
    """
    args = args or {}
    if nome == "amplia_catalogos":
        return {
            "ok": True,
            **catalogo_completo(so_medidos=bool(args.get("apenas_medidos"))),
        }
    if nome == "amplia_desenhar_pagina":
        from app.ia.paginas import montar

        return montar(user, args.get("modelo") or "")
    if nome == "amplia_estado_sistema":
        # Leitura pura: ficheiros e base. Nao toca em nada, por isso vai na
        # porta de catalogo e NAO pelo sandbox — uma trilha com uma leitura
        # de estado a mais esconde a accao que interessa.
        from app.amplia_mcp.estado import estado_do_sistema

        return estado_do_sistema(so_falhas=bool(args.get("so_falhas")))
    if nome == "amplia_inventario_carbono":
        # O ANO E' O UNICO ARGUMENTO, e nao ha `propriedade_id` de proposito:
        # a propriedade vem do `user`, como em todas as outras leituras. Uma
        # tool que aceite `propriedade_id` do modelo e' uma porta aberta — o
        # produtor A pede o inventario da fazenda do produtor B.
        from datetime import datetime

        from app.ia.propriedade import resolver as _resolver_propriedade
        from app.services.mrv import RelatorioMRV

        ano = args.get("ano") or datetime.now().year
        try:
            ano = int(ano)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "erro": f"'ano' tem de ser um inteiro. Recebi {ano!r}.",
            }

        prop = _resolver_propriedade(user)
        if prop is None:
            return {
                "ok": False,
                "erro": (
                    "Este produtor ainda nao tem propriedade cadastrada. O "
                    "inventario de emissoes e' por propriedade — sem ela nao "
                    "ha o que inventariar."
                ),
            }

        return {"ok": True, **RelatorioMRV.calcular(propriedade_id=prop.id, ano=ano)}
    return {"ok": False, "erro": f"tool de catalogo desconhecida: {nome!r}"}
