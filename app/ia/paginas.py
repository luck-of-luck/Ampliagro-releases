"""paginas.py — os MODELOS e as REFERÊNCIAS com que uma IA constrói uma tela.

O PROBLEMA
==========
O AmplIA tem 79 intents expostas pelo MCP, e nenhuma delas diz à IA que
existe um catálogo de 17 widgets, que 8 são medidos e 9 são simulados, nem o que
um widget devolve. Peça a um agente externo — Claude Desktop, Hermes, o
qualquer — "monta um painel para uma fazenda de café", e ele tem três saídas,
e as três são inventar:

  1. Chamar intents a esmo e não montar página nenhuma.
  2. Chamar `amplia_<coisa-que-não-existe>` e receber 404.
  3. Descrever uma página em prosa, que ninguém executa.

As três são a mesma coisa: falta o vocabulário. Um modelo não inventa melhor
quando lhe dão regras; inventa melhor quando lhes dão um **catálogo**.

O QUE ISTO MÓDULO É
===================
Um catálogo de páginas. Não um construtor de páginas: ele NÃO escreve HTML, NÃO
desenha tela, e NÃO executa nada. Ele diz três coisas e nada mais:

  * **MODELOS** (`MODELOS`) — as telas que valem a pena montar, já com os
    widgets escolhidos, a unidade de cada um, e o dado de que depende.
  * **REFERÊNCIAS** (`referencia_widgets`) — o dicionário: o que existe, o que
    cada widget mede, e — o mais importante — se o número é medido ou gerado.
  * **PROVÊNCIA** — `montar()` carimba cada valor com a sua origem.

A REGRA ÚNICA
=============
Um número gerado não é um número pequeno: é um número que não dá erro. Uma
balança que não está ligada devolve 50,4 sc/ha com a mesma confiança de uma
balança ligada, e o produtor multiplica pela área dele. Por isso:

  * os MODELOS só usam widgets MEDIDOS — não há interruptor para ligar os
    simulados, porque um interruptor que não faz nada é pior do que nenhum:
    o modelo marca-o, gasta uma chamada, e a tela não muda;
  * um widget cujo dado não existe não vira `0` — vira `sem_dado: True` com
    `fonte_dado: "sem_dado"`;
    Zero é um número, e um número que não veio de lugar nenhum mente com
    com a confiança de um bom.

O QUE NÃO É
===========
Não é um `eval`, não é um gerador de `.py`, não é um schema livre. Uma página
que cite um widget fora do catálogo é REJEITADA, com o nome do widget no erro —
para que a IA leia o erro e corrija, em vez de insistir. Um LLM pequeno insiste
quando não tem resposta; dar-lhe o motivo do erro é o que o faz parar.
"""

from __future__ import annotations

from typing import Any

from app.ia.palco import CATALOGO_IA, WIDGETS_SERVIDOR, WIDGETS_TOP_GLOBAIS
from app.ia.palco_dados import CAMPOS_POR_WIDGET
from app.ia.proveniencia import Estado

#: Medidas pelas quais um modelo pode ser perguntado. A IA escolhe, não inventa.
#: O que cada widget precisa para mostrar um número. Um `depende` escrito à
#: mão na entrada do modelo é uma lista que divergir: hoje `cafe` citava
#: `kpi-custo` e não pedia lançamento nenhum, e o contrato prometia "completa"
#: com um quarto do ecrã em branco. Derivar daqui é o que impede a repetição —
#: acrescentar um widget a um modelo passa a trazer o requisito consigo.
REQUISITOS_POR_WIDGET: dict[str, tuple[str, ...]] = {
    "kpi-custo": ("lancamento", "area_medida"),
    "kpi-caixa": ("lancamento",),
    "kpi-roi": ("lancamento",),
    "kpi-produtividade": ("safra",),
    "kpi-area": ("safra",),
    "chart-safras": ("safra",),
    "table-financeiro": ("lancamento",),
    "kpi-alertas": (),
}

CULTURAS = {
    "cafe": "Café",
    "gado": "Gado de corte",
    "mista": "Café e gado de corte",
    "graos": "Grãos",
    "hortalicas": "Hortaliças",
    "geral": "Exploração geral",
}


# --------------------------------------------------------------------------
# 1. OS MODELOS
# --------------------------------------------------------------------------
# Cada modelo é uma tela que alguém realmente usa. Não são variações de
# layout: são perguntas diferentes, e por isso dados diferentes.
#
# `depende` lista o que tem de EXISTIR para a tela merecer a pena. Serve para
# a IA dizer "falta isto" em vez de mostrar uma mesa de zeros — que é o que
# transforma um painel vazio num painel que engana.
MODELOS: dict[str, dict[str, Any]] = {
    "panorama": {
        "titulo": "Panorama da propriedade",
        "para_quem": "Produtor que quer saber, num olhar, se a safra está a dar.",
        "widgets": [
            "kpi-area",
            "kpi-custo",
            "kpi-caixa",
            "kpi-roi",
            "kpi-produtividade",
            "kpi-alertas",
        ],
        # Tudo aqui vem do banco. Nenhum widget simulado entra num panorama.
        "depende": ["propriedade"],
        "culturas": ["geral"],
    },
    "cafe": {
        "titulo": "Safra de café",
        "para_quem": "Quem vive da colheita e precisa de t/ha e custo por hectare.",
        "widgets": [
            "kpi-produtividade",
            "kpi-area",
            "kpi-custo",
            "chart-safras",
        ],
        "depende": ["safra"],
        "culturas": ["cafe", "mista"],
    },
    "gado": {
        "titulo": "Gado de corte",
        "para_quem": "Quem precisa do resultado financeiro e da área ocupada.",
        "widgets": [
            "kpi-area",
            "kpi-custo",
            "kpi-caixa",
            "table-financeiro",
        ],
        "depende": ["propriedade"],
        "culturas": ["gado", "mista"],
    },
    "financeiro": {
        "titulo": "Dinheiro",
        "para_quem": "Quem pergunta quanto entrou, quanto saiu, e o que sobrou.",
        "widgets": [
            "kpi-caixa",
            "kpi-custo",
            "kpi-roi",
            "table-financeiro",
        ],
        "depende": ["lancamento"],
        "culturas": ["geral", "cafe", "gado", "mista"],
    },
    "alertas": {
        "titulo": "O que exige atenção",
        "para_quem": "Quem abre a tela porque alguma coisa o preocupou.",
        "widgets": ["kpi-alertas"],
        "depende": [],
        "culturas": ["geral"],
    },
}


def nome_modelo(valor: str) -> str | None:
    """Aceita o que a IA escreveu e devolve o id canonico, ou None.

    Aceitar a variacao e' bondade; devolver o canonico e' o que garante que dois
    agentes que pediram "cafe" e "café" construam a mesma tela. Sem isso, a
    mesma pergunta produz duas paginas, e o produtor acredita que a app muda de
    forma conforme a palavra.

    Os acentos saem de proposito. "CAFÉ" e' o que uma pessoa escreve; "cafe" e'
    o que esta no catalogo. Comparados literalmente, o pedido mais natural do
    mundo devolve "modelo desconhecido" com a lista de opcoes ao lado - e o
    produtor conclui que a IA nao sabe cafe.
    """
    if not valor:
        return None
    alvo = _sem_acento(str(valor)).strip().lower()
    for chave in MODELOS:
        if _sem_acento(chave) == alvo:
            return chave
    return None


def _sem_acento(texto: str) -> str:
    """NFD decompõe o 'é' em 'e' mais o acento; o acento e' deitado fora.

    `unicodedata.normalize` faz o trabalho todo. Uma tabela de substituicoes
    escrita a mao e' o caminho para esquecer o 'ã' - e um 'ã' esquecido e'
    exactamente o erro que o produtor nao perdoa numa palavra que ele escreveu.
    """
    import unicodedata

    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def referencia_widgets(
    somente_medidos: bool = False,
    user=None,
    filtrar_culturas: bool = True,
) -> list[dict[str, Any]]:
    """O dicionário que a IA precisa para não inventar widget.

    `fonte_dado` é a coluna que importa. Um LLM que lê a lista toda sem ela vai
    montar uma tela com `kpi-praga-ai` ao lado de `kpi-produtividade` e
    apresentar os dois com a mesma cara — que é exactamente o que estraga a
    confiança num painel. Ver qual é medido e qual é gerado é o que permite
    dizer ao produtor "este número aqui é de exemplo".

    `user` e `filtrar_culturas` cortam o que não serve ao produtor: quem escolheu
    Soja nao precisa de ver `kpi-weigh-scale` (peso na balanca e' rebanho), e
    oferecer e' pior do que nao ter: o modelo deduz que aquilo se aplica e monta
    a tela.

    O corte é do LADO DA LISTA, não do lado dos dados. Um widget escondido aqui
    continua a ter aggregator e endpoint em `palco_dados.py` — e é isso que se
    quer: quando o produtor escolher a cultura, o widget volta sem ninguém ter
    de ir reescrever a camada de dados. O inverso (esconder no aggregator)
    obriga a desfazer a alteração em dois sítios e deixa o endpoint a devolver
    404 sem explicação.

    `filtrar_culturas=False` devolve o catálogo inteiro. Usado pelos testes do
    catálogo e pelo comando `amplia_mcp`, que documenta o que EXISTE e não o que
    este produtor vê.
    """
    from app.cultures.filtro import grupos_da_marca, grupos_escolhidos, widget_aplicavel

    grupos_usuario = grupos_escolhidos(user) if filtrar_culturas else None

    saida: list[dict[str, Any]] = []
    for tipo in sorted(CATALOGO_IA):
        spec = CATALOGO_IA[tipo] or {}
        simulado = bool(spec.get("simulado"))
        if somente_medidos and simulado:
            continue
        if not widget_aplicavel(grupos_usuario, grupos_da_marca(spec.get("aplica_a"))):
            continue
        saida.append(
            {
                "id": tipo,
                "descricao": spec.get("descricao", ""),
                "fonte": spec.get("fonte", "servidor"),
                # `True` = o número não saiu de um sensor nem de um
                # lançamento. Existe, é bem formatado, e não serve para decidir.
                "simulado": simulado,
                "fonte_dado": "simulado" if simulado else "medido",
                # Os campos que o widget devolve. Sai de `CAMPOS_POR_WIDGET`,
                # nao do catalogo: nenhuma entrada do catalogo tinha `campos`,
                # e o dicionario prometia uma lista vazia para os 17 widgets.
                "campos": list(CAMPOS_POR_WIDGET.get(tipo, ())),
                # `servidor` = o Django preenche com agregados do banco.
                # `top_globais` = o CLIENTE busca sozinho, num endpoint
                # determinístico sem ligação à propriedade de quem pergunta.
                "como_preencher": (
                    "cliente" if tipo in WIDGETS_TOP_GLOBAIS else "servidor"
                ),
            }
        )
    return saida


def summarise_catalogo() -> str:
    """Uma frase para o modelo ler no system prompt.

    O texto tem de caber no orçamento de contexto e diz o que importa: quantos
    widgets existem, quantos são medidos, e que os simulados existem. Esconder
    os simulados não os elimina — só faz a IA descobri-los no resultado, já com
    o número na tela.
    """
    total = len(CATALOGO_IA)
    medidos = len(WIDGETS_SERVIDOR)
    simulados = total - medidos
    return (
        f"Widgets disponíveis: {total}. "
        f"Medidos (saem do banco e são fiáveis): {medidos}. "
        f"Simulados (número gerado, sem ligação a esta fazenda): {simulados}. "
        "Use os medidos por omissão. Só use um simulado se o produtor o pedir "
        "explicitamente, e diga que é simulado."
    )


# --------------------------------------------------------------------------
# 3. O QUE EXISTE — para a tela não nascer de um vazio
# --------------------------------------------------------------------------


def o_que_existe(user) -> dict[str, Any]:
    """O inventário real da conta, para a tela saber se tem o que mostrar.

    Cada chave responde a uma dependência dos MODELOS. Uma dependência que não
    está satisfeita não é motivo para inventar o dado — é motivo para a IA dizer
    "ainda não há safras registadas" e desenhar a parte que dá.

    O ESCOPO É `propriedades_visiveis(user)`, E NÃO `filter(user=user)`
    ==============================================================
    Um servidor não é DONO da propriedade a que está ligado: é ACESSOR. Com
    `filter(user=user)`, um técnico ligado a uma fazenda via um inventário
    inteiramente vazio — `safra: False`, `lancamento: False` — e a tela
    desenhava-se contra a conclusão "não há safras", que é uma afirmação
    falsa sobre uma fazenda que ele tem permissão para ver. O painel da IA
    ficava vazio sem uma única palavra de aviso, enquanto o resto do sistema
    mostrava-lhe os mesmos números.
    """
    from app.ia.palco_dados import _propriedades_do_usuario
    from app.models import LancamentoFinanceiro, Safra

    props = _propriedades_do_usuario(user)
    return {
        "propriedade": props.exists(),
        "propriedades": list(props.values_list("nome", flat=True)[:10]),
        "safra": Safra.objects.filter(propriedade__in=props).exists(),
        "lancamento": LancamentoFinanceiro.objects.filter(
            propriedade__in=props
        ).exists(),
        # A área é 0 quando ninguém a mediu. `True` aqui quer dizer
        # "existe e é utilizável", e não "o campo tem algum valor" — senão
        # uma propriedade de 0 ha contaria como pronta para dividir.
        "area_utilizavel": any(
            float(p.area_total or 0) > 0 for p in props.only("id", "area_total")[:20]
        ),
    }


# --------------------------------------------------------------------------
# 4. MONTAR — a página, com a origem de cada número
# --------------------------------------------------------------------------


def montar(user, modelo: str, *, prop=None) -> dict:
    """Transforma um modelo numa página, com a procedência de cada valor.

    Devolve SEMPRE um dicionário com `ok`. Um `raise` aqui chegaria ao produtor
    como traceback, e quem chama isto é um modelo de 1B que vai errar o nome do
    modelo uma vez em três. O erro vem no `erros`, com o nome das opções — para
    a IA corrigir sozinha, em vez de o produtor receber uma página em branco.
    """
    from app.ia.palco import validar_estrutura
    from app.ia.palco_dados import enriquece

    alvo = nome_modelo(modelo)
    if alvo is None:
        return {
            "ok": False,
            "erros": [f"modelo desconhecido: {modelo!r}"],
            "modelos_disponiveis": sorted(MODELOS),
        }
    m = MODELOS[alvo]

    # 1. O que falta. Isto vem ANTES de desenhar: uma tela de zeros é pior do
    #    que uma tela que admite estar vazia.
    inventario = o_que_existe(user)
    # O que falta sai dos WIDGETS, e nao da lista `depende` do modelo. Sao as
    # duas a mesma pergunta — "de que precisa esta tela" — e quando foram
    # escritas a mao em dois sitios, divergiram: `cafe` prometia estar
    # completo sem um unico lancamento registado, com `kpi-custo` em branco no
    # meio do ecra e nenhum aviso.
    pedidos: list[str] = list(m["depende"])
    for w in m["widgets"]:
        for req in REQUISITOS_POR_WIDGET.get(w, ()):
            if req not in pedidos:
                pedidos.append(req)
    faltando = []
    for d in pedidos:
        if d == "area_medida":
            # area 0 nao e' "area conhecida": e' area por medir, e dividir
            # por ela produz um custo por hectare inventado.
            if not inventario.get("area_utilizavel"):
                faltando.append(d)
        elif not inventario.get(d):
            faltando.append(d)

    # 2. Só entram widgets declarados. Esta linha é a que impede a invenção:
    #    um id que não exista no catálogo nunca chega ao renderizador.
    #
    #    E só entram os que servem AO PRODUTOR: `referencia_widgets` esconde-os
    #    da lista, mas uma MODELO é escrita à mão e pode citar um widget que o
    #    catálogo já não oferece a este produtor. Sem este segundo corte, um
    #    `kpi-weigh-scale` numa tela de quem só planta soja aparecia na tela
    #    com um zero e a explicação do nada.
    #
    #    MEDIDO 13/10/2026: hoje este segundo corte não tira nada — nenhuma das
    #    5 MODELOS cita um widget com `aplica_a`, todas usam widgets de
    #    fazenda. Está aqui para o próximo `MODELOS` que citar um, e para que
    #    ninguém descubra por ecrã que a regra é só do catálogo.
    _oferecidos = {w["id"] for w in referencia_widgets(user=user)}
    escolhidos = [w for w in m["widgets"] if w in CATALOGO_IA and w in _oferecidos]
    widgets = validar_estrutura([{"tipo": w} for w in escolhidos])[0]

    # 3. Os números reais, com tenancy.
    widgets = enriquece(user, widgets, prop=prop)

    # 4. A origem JÁ FOI DECIDIDA por `enriquece`, que a pôs no config.
    #
    #    Esta função já fazia isto por sua conta — deduzia `medido` do
    #    CATÁLOGO e marcava `sem_dado` lendo uma chave `valor` que nenhum
    #    cálculo produz. Foi corrigido uma vez, e reintroduzido agora pela
    #    via mais subtil: a segunda versão lê o config, o que PAREECE mais
    #    rigoroso, e mesmo assim volta a decidir por cima da decisão que o
    #    módulo de dados já tomou.
    #
    #    Duas fontes de verdade para o mesmo campo é o que o Plano A veio
    #    eliminar. Agora há UMA: quem embrulha decide, e quem compõe lê. Um
    #    carimbo que se reescreve a caminho da tela é um carimbo que alguém
    #    pode reescrever por engano — e foi exactamente o que aconteceu.
    for w in widgets:
        cfg = w.get("config") or {}
        mediu = bool(cfg) and not cfg.get("sem_dado") and not cfg.get("_indisponivel")
        # A DECISÃO É DE `enriquece`. Aqui só se ESPELHA no widget, porque o
        # frontend lê o widget e não vai ao config atrás da origem.
        #
        # Espelhar não é decidir de novo: o valor vem do config. E se o config
        # não o tiver — um widget escrito à mão, que não passou pelo módulo —
        # o estado é o SEGURO, `sem_dado`. Um número cuja origem ninguém
        # conhece é pior do que a sua ausência.
        #
        # A versão anterior só escrevia quando o config NÃO tinha, e desde que
        # `enriquece` passou a pôr sempre, o widget ficava sem `fonte_dado` e o
        # frontend recebia um `undefined` no lugar de uma resposta. Um
        # carimbo que só se escreve quando falta é um carimbo que desaparece
        # justamente quando está lá.
        if cfg.get("fonte_dado") is not None:
            w["fonte_dado"] = cfg["fonte_dado"]
            if cfg["fonte_dado"] != Estado.MEDIDO:
                w["config"] = {**cfg, "sem_dado": True}
        else:
            w["fonte_dado"] = Estado.MEDIDO if mediu else Estado.SEM_DADO
            if not mediu:
                w["config"] = {**cfg, "sem_dado": True, "fonte_dado": w["fonte_dado"]}

    # 5. Um widget que a tela não tem como mostrar não entra no caminho das
    #    dependências. Sem isto, `cafe` prometia estar completo com safra
    #    registada e sem um único lançamento — e `kpi-custo` ficava em branco
    #    sem ninguém dizer porquê.

    return {
        "ok": True,
        "modelo": alvo,
        "titulo": m["titulo"],
        "para_quem": m["para_quem"],
        "widgets": widgets,
        "faltando": faltando,
        # A tela que não tem o que mostrar diz que não tem. Uma lista de
        # dependências por resolver é mais útil ao produtor do que seis zeros.
        "completa": not faltando,
        "aviso": (
            None
            if not faltando
            else "Ainda falta: " + ", ".join(faltando) + ". A tela mostra o que da."
        ),
    }
