"""
views.py — a camada governada exposta por HTTP.

É este endpoint que o WebLLM do navegador passa a chamar, no lugar do
`iaToolCall` em JavaScript que fazia POST direto em `/api/iot/comandos/`.

Por que um endpoint e nao o servidor MCP direto: o LLM roda na aba, o Django
roda no servidor. Eles se encontram em HTTP, com a sessão do Django — o que
significa que a tool herda a autenticação e o multitenant sem código extra. O
servidor MCP stdio (`servidor.py`) existe para clientes externos (Claude
Desktop, Hermes) e usa a MESMA função `executar_para`. Um caminho só de
execução, duas portas.

Contrato
--------
GET  /api/amplia/tools/    -> catalogo no formato OpenAI function-calling,
                              que é o que o WebLLM consome nativamente
POST /api/amplia/exec/     -> { "tool": "amplia_...", "args": {...} }
GET  /api/amplia/contexto/ -> texto de contexto (o "Resource" do roadmap)
POST /api/amplia/ingestao/audio/sinais/
                             -> sinais deterministicos de uma transcricao.
                                Nao e "execucao": nao age em nada, so devolve
                                o que o extrator reconheceu no texto. Exposto
                                para que o cliente e o servidor usem a MESMA
                                funcao — duas implementacoes de "talhao 4"
                                discordando entre si e o produtor vendo um
                                numero na tela e outro no log.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST

from app.amplia_mcp import (
    NOMES_CATALOGO,
    TOOLS_CATALOGO,
    catalogo_tools,
    contexto,
    executar_catalogo,
    executar_para,
    nome_tool,
    vocabulario,
)
from app.amplia_mcp.contrato import GUIA, para_openai, resumo_contrato


def _todas_as_tools():
    """O catálogo inteiro, montado UMA vez.

    Antes, `views.tools` chamava `catalogo_tools()` duas vezes — uma para os
    `tools` e outra para a chave `mcp` — e cada chamada refazia a dedução de
    todos os schemas a partir dos exemplos. Duas passagens para a mesma
    aritmética. `ContratoNaoSeRepeteTest` trava que este é o único ponto de
    chamada.
    """
    return catalogo_tools() + list(TOOLS_CATALOGO)


@login_required
@require_http_methods(["GET"])
def tools(request):
    """Catalogo no formato que o WebLLM entende nativamente.

    O WebLLM usa a mesma convencao de tools da OpenAI (`type: function`), e nao
    o envelope de Resource do protocolo MCP. Traduzir aqui e melhor que fazer
    o JS da aba traduzir: uma traducao so, testada, e o contrato do MCP
    preservado para o outro lado.

    O catálogo de páginas entra aqui ao lado das intents, e não noutro
    endpoint. Um modelo que recebeu as tools de ação mas não sabe que há tela
    a desenhar nunca vai perguntar por ela — a lista de tools é o que ele lê
    para saber o que pode fazer, e o que não está nela não existe para ele.

    A traducao vive em `contrato.py`, e nao aqui, porque o servidor MCP (stdio)
    precisa da MESMA. Duas traducoes — uma em Python, outra em JSON — divergem
    no primeiro dia em que um schema muda, e divergem em silencio: o cliente
    HTTP passa a ver `required` e o cliente MCP nao.
    """
    bruto = _todas_as_tools()
    return JsonResponse(
        {
            "tools": para_openai(bruto),
            "mcp": [t["name"] for t in bruto if t.get("x-intent")],
            "guia": GUIA,
        }
    )


@login_required
@require_http_methods(["GET"])
def skills_view(request):
    """As especialidades de dominio, e que intents cada uma cobre.

    `amplia://skills` no MCP e este endpoint sao a mesma informacao em duas
    linguagens — e sao a mesma funcao que produz os dois, pelo mesmo motivo de
    `audio_sinais`: duas implementacoes do mesmo dicionario discordam, e o
    produtor ve um numero na tela e outro no log.
    """
    from app.amplia_mcp.skills import catalogo_skis

    return JsonResponse(catalogo_skis())


def _skills_saos():
    from app.amplia_mcp.skills import catalogo_skis

    return catalogo_skis()["handlers_fantasmas"] == 0


def _por_origem():
    from app.ia.registro import por_origem

    return {k: len(v) for k, v in sorted(por_origem().items())}


@login_required
@require_http_methods(["GET"])
def diagnostico(request):
    """A aritmetica desta camada. Para nao precisar de abrir ficheiros.

    Responde a uma pergunta que um cliente nao consegue responder sozinho:
    *o caminho esta inteiro?*. Devolve a conta — quantas tools, quantas de
    escrita, quantas com confirmacao declarada — e os invariantes que o
    contrato garante, cada um com o seu valor.

    E' leitura de codigo, nao accao: nao entra na trilha de auditoria, pela
    mesma razao que `amplia_catalogos` nao entra. Uma trilha com 400 leituras
    de catalogo e 3 accoes esconde as 3.

    O que se garante e' a RELACAO `tudo_ok == all(invariantes.values())` — o
    resumo nunca mente sobre as partes. E' testavel com o codigo sao e com o
    codigo partido, ao contrario de `assertTrue(tudo_ok)`, que so sabe estar
    verde ou vermelho sem saber qual das duas coisas aconteceu.

    Hoje `skills_sem_handler_fantasma` e' `False`: as SKIs declaram 15 handlers
    e nenhum existe (FILA #43). O endpoint reporta isso em vez de o esconder.
    """
    from app.ia.registro import COLISOES, REGISTO

    bruto = _todas_as_tools()
    conta = resumo_contrato(bruto)

    # Colisoes de nome entre catalogos: `registro.nomes_duplicados()` devolve
    # `_mesmo_objecto` quando e' o agregador a repetir o que outro catalogo ja
    # tinha — o que nao e' defeito. So o resto e'.
    colisoes_reais = {k: v for k, v in COLISOES.items() if k != "_mesmo_objecto"}

    invariantes = {
        # Toda intent chega como tool. Se isto falha, a IA nao sabe que a
        # capacidade existe — que foi exactamente a falha que o `registro.py`
        # veio fechar.
        "toda_intent_e_uma_tool": len([t for t in bruto if t.get("x-intent")])
        == len(REGISTO),
        # Nenhuma escrita sem confirmacao declarada. Sem isto, uma escrita e'
        # pedida e nao pode ser confirmada por quem a pediu.
        "toda_escrita_declara_confirmacao": not conta["escrita_sem_confirm_declarado"],
        # Nenhum schema fecha sem declarar o que exige: campo obrigatorio que
        # o schema proibe e' um contrato impossivel de satisfazer.
        "obrigatorio_e_satisfazivel": all(
            set(t["inputSchema"].get("required") or [])
            <= set(t["inputSchema"].get("properties") or {})
            for t in bruto
        ),
        # A allowlist e' o catalogo: toda tool corresponde a uma intent real.
        "tool_corresponde_a_intent": all(
            t.get("x-intent") in REGISTO for t in bruto if t.get("x-intent")
        ),
        # Os SKIs de dominio nao apontam para handlers que nao existem.
        "skills_sem_handler_fantasma": _skills_saos(),
        # Nenhuma colisao real de nome entre catalogos.
        "sem_colisao_entre_catalogos": not colisoes_reais,
    }

    from app.amplia_mcp.coerencia import verificar

    coerencia = verificar()

    return JsonResponse(
        {
            "conta": conta,
            "intents_no_registo": len(REGISTO),
            "por_origem": _por_origem(),
            "colisoes": colisoes_reais,
            "invariantes": invariantes,
            "tudo_ok": all(invariantes.values()),
            # `invariantes` responde "as reacções dao o que promete?". `coerencia`
            # responde "as PROMESSAS batem com o que o codigo faz?".
            #
            # Sao perguntas diferentes e uma nao substitui a outra. Uma tool
            # sem rota em `/exec/` e' coerente com o contrato (esta declarada,
            # tem schema) e incoerente com o servidor (ninguem a executa). Foi
            # assim que 15 handlers inexistentes sobreviveram meses: cada porta
            # estava certa sobre o que dizia, e nenhuma sabia o que a outra
            # dizia.
            "coerencia": {
                "perguntas": coerencia["perguntas"],
                "falhou": coerencia["falhou"],
                "tudo_ok": coerencia["tudo_ok"],
                # As falhas FIRST: quem abre isto num terminal tem segundos, e
                # a pergunta que falhou e' a unica coisa que precisa de ler.
                "falhas": coerencia["falhas"],
            },
        }
    )


@login_required
@require_POST
def exec(request):  # noqa: A001 - nome da ROTA em /api/amplia/exec/; renomear quebra o JS e o MCP
    """Executa UMA tool. Nunca duas: uma chamada por request.

    Um endpoint que aceita lote seria mais barato no numero de requests, mas
    criaria um caminho onde um unico pedido do modelo executa acoes multiplas
    sem intervencao — que e o que o `needs_confirm` do sandbox existe para
    impedir. Uma chamada, um pedido de confirmacao, umudio do produtor.
    """
    import json

    try:
        corpo = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return JsonResponse(
            {"ok": False, "erro": "corpo nao e JSON", "codigo": "json_invalido"},
            status=400,
        )

    nome = corpo.get("tool") or corpo.get("name") or ""
    args = corpo.get("args") or corpo.get("arguments") or {}
    if not isinstance(args, dict):
        return JsonResponse(
            {"ok": False, "erro": "args deve ser objeto", "codigo": "args_invalido"},
            status=400,
        )

    # a frase do usuario entra como metadado, para a trilha de auditorio
    meta = {}
    if corpo.get("entrada"):
        meta["entrada"] = str(corpo["entrada"])[:2000]

    # As tools de CATÁLOGO não são intents, e não vão ao sandbox: ler um
    # catálogo não é uma acção, e registá-lo como tal encheria a trilha de
    # nauditoria de ruído até não se ver mais nada. vão pela porta delas.
    if nome in NOMES_CATALOGO:
        return JsonResponse(executar_catalogo(request.user, nome, args))

    resultado = executar_para(request.user, nome, args, **meta)

    # 200 mesmo quando a tool falhou: um erro de tool e um resultado, nao um
    # erro de HTTP. O 4xx faria o cliente tratar como falha de rede e tentar de
    # novo, executando a acao duas vezes.
    return JsonResponse(resultado)


@login_required
@require_http_methods(["GET"])
def ctx(request):
    """Contexto do usuario, para a IA nao propor o que ja existe."""
    return JsonResponse({"contexto": contexto(request.user)})


@login_required
@require_http_methods(["GET"])
def vocabulario_view(request):
    """O texto que o modelo local recebe no system prompt.

    O nome e' `vocabulario_view` e nao `vocabulario` por um motivo que ja
    mordeu neste ficheiro: o modulo tambem importa uma funcao chamada
    `vocabulario`, e uma view com o mesmo nome passa a ser a resolucao do
    nome dentro do proprio modulo. O corpo chamava a si proprio com um
    `User` onde esperava um `HttpRequest` — `AttributeError: 'User' object
    has no attribute 'user'`, em todas as chamadas, para sempre.

    Porque este endpoint e' separado do `/tools/`
    -------------------------------------------
    `/tools/` devolve os schemas completos — 34 KB, ~8 700 tokens medidos.
    Serve para um cliente que os meta no prompt com folga, e e' a resposta
    correcta para um modelo de servidor. Para o modelo que roda NO NAVEGADOR
    e' impossivel: SmolLM2 de 1,7 B tem janela de 4 096, e o catalogo sozinho
    estoura isso antes da conversa comecar.

    O defeito medido (FILA #27) foi o meio-termo entre as duas: `/tools/` era
    buscado pelo painel e nenhum schema chegava ao prompt. O modelo ficava a
    funcionar com uma lista de nomes escrita a mao — treze nomes, e nenhum
    deles existia.

    Este endpoint fecha o meio-termo: os nomes verdadeiros, todos, num texto
    que cabe, e derivados do catalogo a cada chamada.

    `limite` e' da leitura, nao da escrita. Quem tem um modelo maior pede
    mais; quem tem um menor pede menos. O padrao e' o do modelo de 1,7 B.
    """
    try:
        limite = int(request.GET.get("limite", 3200))
    except (TypeError, ValueError):
        limite = 3200
    # Piso e teto: abaixo de 400 o texto perde a lista de nomes, que e' a
    # razao de ele existir; acima de 12000 ja nao e' um system prompt e quem
    # quer isso quer o `/tools/`, que devolve o catalogo inteiro e sem cortar.
    limite = max(400, min(limite, 12000))

    return JsonResponse(vocabulario(request.user, limite=limite))


# =============================================================================
# SINAIS DE AUDIO — o unico endpoint de ingestao neste modulo, e ele nao age
# =============================================================================
# Nao esta aqui por "comodidade de API". Esta aqui porque ha uma duplicacao
# concreta a evitar.
#
# A extracao de sinais (talhao, quantidade, classe de insumo) tem que existir
# no servidor, em Python. Se o cliente tambem tivesse uma versao em JavaScript,
# existiriam duas respostas para a mesma frase — e o produtor veria "talhao 4"
# na tela e "talhao 3" no log, sem nenhuma forma de saber qual era o certo.
#
# O sinal vai ao LLM como PISTA, nao como veredito. O LLM pode discordar, e
# quando discorda o sandbox ainda exige confirmacao. A seguranca nao depende
# do modelo acertar — e por isso este endpoint pode ser "so leitura" sem
# necessidade de confirmacao: ele nao tem mao nenhuma.
# =============================================================================
@login_required
@require_POST
def audio_sinais(request):
    from app.ia.ingestao import audio as _audio

    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)

    texto = str(payload.get("texto") or "").strip()
    if not texto:
        return JsonResponse({"erro": "texto vazio"}, status=400)
    if len(texto) > 2000:
        # limite generoso e ainda suficiente: um relato de 2 min cabe folgado,
        # e acima disso o que chegou nao e um relato, e um arquivo
        return JsonResponse({"erro": "texto longo demais (max 2000)"}, status=400)

    sinais = _audio.extrair_sinais(texto)
    return JsonResponse({"sinais": sinais})


# =============================================================================
# A FILA DO CENARIO — onde a nuvem encontra o modelo que esta no celular
# =============================================================================
# estes dois endpoints sao de LEITURA e ESCRITA minima, e existem por um
# motivo que e o mesmo do `audio_sinais`: a logica esta em Python, no servidor,
# e o que o JS faz e entregar o texto e trazer a resposta. Se a aba montasse o
# cenario, cada aba decidiria o que e relevante e a mesma previsao viraria
# dois cenarios diferentes.
#
# `GET /api/amplia/proativo/pendente/`
#     entrega UM cenario e toma o lease. Vazio quando nao ha nada.
#     A entrega e' uma entrega: quem recebe primeiro fica com ele, e uma
#     segunda aba pegando o mesmo cenario receberia um alerta duplicado.
#
# `POST /api/amplia/proativo/devolver/`
#     devolve o cenario SEM ter emitido alerta, para ele voltar a fila.
#     E' o caminho do "o modelo nao achou nada" e do "a aba fechou no meio" —
#     sem ele, um cenario consumido sem resposta seria perdido em silencio.
# =============================================================================
@login_required
@require_http_methods(["GET"])
def proativo_pendente(request):
    """Um cenario para o modelo local raciocinar. Ou nada."""
    from app.ia.proativo import cenario_para_ia, proximo_cenario

    c = proximo_cenario(request.user)
    if c is None:
        return JsonResponse({"cenario": None})
    return JsonResponse(
        {
            "cenario": {
                "id": c.pk,
                "contexto": c.contexto,
                # `cenario_para_ia`, e nao `c.cenario`: sem a conversao, todo
                # float da previsao chega ao celular como "40.0" (string), e
                # e' assim que o SmolLM2 le a temperatura e a chuva.
                "dados": cenario_para_ia(c.cenario),
                "expira_em": c.expira_em.isoformat(),
                "tentativa": c.tentativas,
            }
        }
    )


@login_required
@require_POST
def proativo_devolver(request):
    """A aba devolve o cenario sem ter gerado alerta."""
    import json

    from app.ia.proativo import cenario_do_usuario, devolver_cenario

    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)

    cid = payload.get("cenario_id")
    if not cid:
        return JsonResponse({"erro": "informe cenario_id"}, status=400)

    # Busca com o dono na consulta. Um id de cenario que nao seja seu devolve
    # "nao encontrado" — e nao "proibido", porque um "proibido" confirmaria que
    # aquele cenario existe.
    cenario = cenario_do_usuario(request.user, cid)
    if cenario is None:
        return JsonResponse({"erro": "cenario nao encontrado"}, status=404)

    # `devolver_cenario`, nao `encerrar_cenario`. A aba devolve porque a
    # analise nao achou nada — ou porque o modelo nao estava carregado. Nos dois
    # casos o cenario esta SAUDAVEL e o unico motivo de nao ter virado alerta e
    # temporario. Descartar aqui jogava fora a fila e queimava uma das tres
    # tentativas: uma falha de infraestrutura (WebLLM nao carregou) custava
    # um cenario, nao um retry. Quem decide o descarte final e o contador de
    # tentativas, dentro de `devolver_cenario` — nao esta view.
    return JsonResponse(
        devolver_cenario(cenario, erro=str(payload.get("erro") or "")[:500])
    )


@login_required
@require_http_methods(["GET"])
def proativo_alertas(request):
    """O que o motor pensou e ainda nao foi lido. O feed do produtor.

    Endpoint proprio, e nao uma leitura de `Notificacao`, por um motivo so: o
    `evidencia` — de onde veio o numero, contra qual limiar, sobre qual tarefa —
    so existe em `IAAlertaProativo`. A notificacao espelhada carrega titulo e
    texto, que e' o suficiente para um sino e insuficiente para decidir.

    `@require_http_methods(["GET"])` explicito, e nao herdado do dispatcher: e'
    um *feed*, e um feed que aceita POST e devolve 200 e' um 405 que ninguem
    nota e um browser que deixa de avisar quando o metodo e' errado.
    """
    from app.ia.proativo import contar_alertas_novos, listar_alertas

    try:
        limite = int(request.GET.get("limite", 20))
    except (TypeError, ValueError):
        limite = 20

    try:
        estado = str(request.GET.get("estado", "novo")).strip() or "novo"
    except Exception:  # pragma: no cover - getattr defensivo
        estado = "novo"

    return JsonResponse(
        {
            "alertas": listar_alertas(request.user, estado=estado, limite=limite),
            "novos": contar_alertas_novos(request.user),
        }
    )


@login_required
@require_POST
def proativo_alerta_visto(request):
    """O produtor confirmou que leu. Some da fila, e da central."""
    from app.ia.proativo import marcar_alerta_visto

    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return JsonResponse({"erro": "JSON invalido"}, status=400)

    aid = payload.get("alerta_id")
    if not aid:
        return JsonResponse({"erro": "informe alerta_id"}, status=400)

    r = marcar_alerta_visto(request.user, aid)
    return JsonResponse(r, status=200 if r.get("ok") else 404)
