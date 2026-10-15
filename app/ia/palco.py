"""O que a IA pode mandar aparecer na tela — e o que ela NÃO pode.

O CATÁLOGO É A FRONTEIRA
========================
A IA não desenha widgets. Ela **compõe** widgets que já existem no registo
`WIDGET_TYPES` do dashboard, e escolhe com que dados cada um é alimentado.

Isso não é limitação, é a razão de o Prompter chamar-se "mesa de operação" e o
resultado ser um painel em vez de um texto. Um SmolLM2 de 1B gerando HTML livre
produz: Broken HTML, ids duplicados, CSS vazando no resto da tela, e nenhum
histórico utilizável. Compôr o registo existente dá: renderizadores testados,
layout responsivo, e uma assinatura (intent → estrutura) que é a mesma coisa em
toda linha do dataset de aprendizado.

Por isso `render_preset` valida contra este catálogo e **descarta** o que não
conhece. Um widget inventado não é erro fatal — é ruído, e a IA ainda compõe
uma mesa útil com o resto.

O QUE ESTE MÓDULO NÃO É
=======================
Não é o registo de renderização. Os renderizadores vivem em JavaScript
(`extra-widgets.js`, `widget-intelligence.js`, `dashboard-desktop.js`). Isto é o
catálogo do *servidor*, e existe por um motivo que o JS não cobre: **o treino**.
Quando o produtor dá Like, gravamos a assinatura com a estrutura validada. O
servidor precisa saber o que era válido na altura em que o Like foi dado para
que o modelo aprenda com exemplos reais, e não com alucinações.
"""

from __future__ import annotations

import unicodedata
from typing import Any

#: Tipo de widget: o que a IA pode compor. As chaves são os IDs de `WIDGET_TYPES`.
#:
#: CADA ENTRADA DECLARA DE ONDE VEM O SEU DADO (`fonte`). Isto não é metadado
#: para enfeite: é a diferença entre um número e uma mentira.
#:
#: A primeira versão desta lista não declarava nada, e foi montada a partir dos
#: TÍTULOS e ÍCONES do `WIDGET_TYPES` em JavaScript. Aí está o erro que quase
#: Repetimos: `kpi-custo` e `chart-financeiro` são entradas de LAYOUT, não
#: widgets com dados. `/api/top-globais/kpi-custo/` responde 404 "widget
#: desconhecido", e o catálogo real de widgets com dados é outro, todo `kpi-*`
#: de agronomia e IoT.
#:
#: Ou seja: eu oferecera ao modelo ids que a camada de dados nunca conheceu. A
#: mesa ia montar com títulos e zero números — que é o sintoma exato que o
#: produtor reportou.
#:
#: Duas fontes, e são as duas que existem de facto:
#:   `servidor`     — o backend agrega o banco (ver `app/ia/palco_dados.py`);
#:   `top_globais`  — cada um tem o seu endpoint `/api/top-globais/<id>/`.
#:
#: Um widget sem fonte não entra na lista. Se um dia houver um terceiro
#: caminho de dados, ganha uma fonte nova — e um widget que ninguém consegue
#: preencher nunca chega a ser oferecido ao modelo.
#:
#: `aplica_a`: a que grupos de cultura o widget diz respeito.
#:   ausente  → widget de fazenda. Serve a qualquer cultura, aparece sempre.
#:   "vegetal" → só para quem escolheu cultura de grupo vegetal.
#:   "animal"  → só para quem escolheu animal ou aquicultura.
#:
#: QUATRO widgets é que têm `aplica_a`. Os outros 13 são de fazenda — custo,
#: caixa, ROI, área, chuva, carbono — e serve a toda a gente; marcá-los como
#: vegetais esconderia o custo de quem produz peixe, que é uma das coisas que
#: o produto existe para mostrar.
#:
#: A ATRIBUIÇÃO NÃO É INVENTADA: sai da `descricao` que já está em cima de
#: cada widget deste catálogo. `kpi-vra-ndvi` diz "vigor da vegetação";
#: `kpi-guidance-ab` diz "aplicação de defensivos"; `kpi-weigh-scale` diz "peso
#: na balança" — as três coisas são de lavoura ou de rebanho, não as duas.
#: Ainda assim é uma decisão de negócio, não uma dedução: se `kpi-weigh-scale`
#: também pesar fruta colhida, o certo é tirá-lo de `animal`. Por isso a lista
#: é curta e explícita, e não um `if` espalhado pelo código.
#:
#: Quem aplica isto é `app.cultures.filtro.widget_aplicavel`, chamado de
#: `app/ia/paginas.py::referencia_widgets`. O filtro é do LADO DO CATÁLOGO
#: (o que se oferece), não do lado dos dados (o que se preenche): esconder um
#: widget da lista sem mexer em `palco_dados.py` é o que garante que nenhum
#: aggregator continua a calcular um número que já ninguém vê.
CATALOGO_IA: dict[str, dict[str, Any]] = {
    # --- agregados do servidor: números que o produtor reconhece ---
    "kpi-custo": {
        "descricao": "Custo total e custo por hectare",
        "fonte": "servidor",
    },
    "kpi-caixa": {
        "descricao": "Fluxo de caixa: entradas, saidas e saldo",
        "fonte": "servidor",
    },
    "kpi-roi": {
        "descricao": "Retorno sobre investimento da receita frente a despesa",
        "fonte": "servidor",
    },
    "kpi-produtividade": {
        "descricao": "Producao por hectare, sobre as safras lancadas",
        "fonte": "servidor",
    },
    "kpi-area": {
        "descricao": "Area plantada, area colhida e a diferenca entre elas",
        "fonte": "servidor",
    },
    "chart-safras": {
        "descricao": "Producao e produtividade por ano",
        "fonte": "servidor",
    },
    "table-financeiro": {
        "descricao": "Lancamentos financeiros por categoria",
        "fonte": "servidor",
    },
    "kpi-alertas": {
        "descricao": "Alertas abertos, por severidade",
        "fonte": "servidor",
    },
    # --- widgets que tem o seu proprio endpoint de dados ---
    "kpi-chuva-1km": {
        "descricao": "Chuva acumulada num raio de 1 km",
        "fonte": "top_globais",
        "simulado": True,
    },
    "kpi-praga-ai": {
        "descricao": "Risco de praga detectado por imagem",
        "fonte": "top_globais",
        "simulado": True,
        "aplica_a": "vegetal",
    },
    "kpi-vra-ndvi": {
        "descricao": "Vigor da vegetacao por NDVI",
        "fonte": "top_globais",
        "simulado": True,
        "aplica_a": "vegetal",
    },
    "kpi-weigh-scale": {
        # VEGETAL, e não "animal" — que foi a primeira leitura, feita pelo nome
        # do widget. A implementação desmente o nome: `weigh_scale_tempo_real`
        # (app/services/top_globais.py:363) recebe um `talhao_id` e devolve
        # `sc_ha` — sacas POR HECTARE. Talhão e saca/ha são lavoura; um talhão
        # não existe para quem tem gado, e gado não se pesa em sacas por
        # hectare.
        #
        # Onde está então o peso do animal? Não está: `automatizar_bigbrother`
        # (as 12 balanças) é uma REGRA de IoT para avicultura, não um widget.
        # Ou seja, antes desta correcção o catálogo prometia um widget de peso
        # a quem produz gado — e o que vinha era um `sc_ha` sobre um talhão
        # inexistente, com a confiança de quem pediu.
        "descricao": "Peso na balanca",
        "fonte": "top_globais",
        "simulado": True,
        "aplica_a": "vegetal",
    },
    "kpi-carbono": {
        # MEDIDO 2026-10-05. A descricao dizia "Carbono capturado na area",
        # o que promete uma quantidade. `top_globais.carbono_mombak` devolve
        # `tco2e: None` DE PROPONITO e explica porquê: a conta antiga era
        # `area * 12.5` hardcoded, e a Mombak e' uma norma com registo — um
        # carimbo sem inventario de carbono e' uma certificacao falsa com o
        # nome de uma norma verdadeira.
        #
        # O que o descriptor tem de fazer e' o que a doutrina manda: se a
        # COISA NAO EXISTE, dizer que nao existe. Prometer "capturado" num
        # widget que nunca calcula e' o que faz o produtor perguntar onde esta
        # o numero.
        "descricao": "Carbono: sem medicao de solo registada. O widget nao calcula tCO2e.",
        "fonte": "top_globais",
        "simulado": True,
    },
    "kpi-benchmark-fbn": {
        "descricao": "Comparacao de produtividade com a regiao",
        "fonte": "top_globais",
        "simulado": True,
    },
    "kpi-hedge-b3": {
        # MEDIDO 2026-10-05: a descricao era "Cobertura de mata nativa na
        # propriedade". O widget chama `hedge_b3_real(sacas, strike)` — e'
        # uma cobertura de opcoes sobre Chicago, nao floresta. A descricao
        # estava errada, e errada para o lado que mais engana: um produtor
        # que pede protecao de preco recebe mata nativa, e um produtor que
        # recebe mata nativa nao sabe que pediu protecao de preco.
        # O `id` fica: mudar o id parte as referencias que ja existem, e o
        # nome `hedge-b3` e' o certo.
        "descricao": "Protecao de preco: cobertura de opcoes sobre Chicago (B3)",
        "fonte": "top_globais",
        "simulado": True,
    },
    "kpi-guidance-ab": {
        "descricao": "Rastreabilidade da aplicacao de defensivos",
        "fonte": "top_globais",
        "simulado": True,
        "aplica_a": "vegetal",
    },
    "kpi-seguro-chuva": {
        "descricao": "Indice de risco de chuva para o seguro",
        "fonte": "top_globais",
        "simulado": True,
    },
}

#: Os TRÊS estados possíveis de um valor, e só três.
#:
#: Este vocabulário é partilhado porque o mesmo nome de campo com dois valores
#: diferentes é o antecedente exacto do tipo de bug que este ficheiro existe
#: para travar: um consumidor a comparar com "medido" e outro com "real", cada
#: um a achar que o outro está errado, e nenhum a dizer.
#:
#: ALIAS, não literals. Estas eram três strings independentes que coincidiam ter
#: o mesmo valor das de `proveniencia.Estado` — duas fontes de verdade para o
#: mesmo conceito, que divergem no primeiro dia em que alguém acrescenta um
#: estado a um lado e não ao outro. `Estado` é a fonte; aqui só se aponta para
#: ela, para não obrigar a reescrever os consumidores que já comparam com
#: `FONTE_*`.
#:
#: `proveniencia` não importa nada de `app`, portanto este alias não fecha ciclo.
from app.ia.proveniencia import Estado

FONTE_MEDIDO = Estado.MEDIDO
FONTE_SEM_DADO = Estado.SEM_DADO
FONTE_SIMULADO = Estado.SIMULADO


#: Os widgets que o CLIENTE vai buscar sozinho, porque tem endpoint proprio.
WIDGETS_TOP_GLOBAIS = frozenset(
    k for k, v in CATALOGO_IA.items() if v.get("fonte") == "top_globais"
)

#: Os que o SERVIDOR preenche com agregados do banco.
WIDGETS_SERVIDOR = frozenset(
    k for k, v in CATALOGO_IA.items() if v.get("fonte") == "servidor"
)

#: O palco. Um preset, sem dono, que a IA redesenha a cada pergunta.
SLUG_PALCO = "amplia"

#: Layouts que o painel sabe desenhar.
LAYOUTS_VALIDOS = frozenset({"grid-2x3", "grid-mixed", "grid-1x1", "grid-auto"})

#: Limite de widgets por mesa. Acima disto a tela fica ilegível e o produtor
#: desiste — a "mesa de operação" tem de caber num olhar, não num relatório.
MAX_WIDGETS = 8


def widget_permitido(tipo: str) -> bool:
    return tipo in CATALOGO_IA


def campos_conhecidos(tipo: str) -> set[str]:
    return set(CATALOGO_IA.get(tipo, {}).get("campos", ()))


def validar_estrutura(bruto: Any) -> tuple[list[dict], list[str]]:
    """Normaliza o que a IA mandou e devolve (widgets, descartados).

    Nunca levanta. A IA é um modelo de 1B: ela vai errar o formato, o id e o
    layout. Um erro fatal aqui significaria que o produtor fez uma pergunta
    analítica e recebeu um traceback — e a pergunta mais importante do produto
    é justamente a que a IA tem mais vontade de estragar. Então cada problema é
    registrado como *descartado* e a composição segue com o que presta.
    """
    if isinstance(bruto, dict):
        if "widgets" not in bruto:
            # Objeto sem a chave esperada. Devolve-se o sinal de fora: uma mesa
            # vazia sem motivo registado parece "a IA não achou nada", e é
            # "a IA mandou mal" — dois defeitos que se corrigem de jeitos
            # completamente diferentes.
            return [], ["sem_chave_widgets"]
        bruto = bruto.get("widgets")
    if not isinstance(bruto, list):
        return [], ["estrutura_nao_lista"]

    widgets: list[dict] = []
    descartados: list[str] = []

    for item in bruto:
        if isinstance(item, str):
            item = {"tipo": item}
        if not isinstance(item, dict):
            descartados.append("item_nao_objeto")
            continue
        tipo = str(item.get("tipo") or item.get("type") or "").strip()
        if not widget_permitido(tipo):
            # Widget inventado. Cai fora em silencio: a IA ainda compõe a mesa
            # com o resto, e o produtor vê algo útil em vez de um erro.
            descartados.append(f"desconhecido:{tipo or '?'}")
            continue
        config = item.get("config")
        config = config if isinstance(config, dict) else {}
        # A geometria mora no config porque é onde o dashboard já a espera
        # (index.html lê config.gridX / config.gridW para escrever
        # gridColumn / gridRow). Passar por ali, e não num campo novo, é o que
        # faz o renderizador existente entender sem tocar nele.
        geo = normalizar_geometria(item.get("geom") or item.get("geometry") or config)
        if geo:
            config = {**config, **geo}
        widgets.append(
            {
                "tipo": tipo,
                "titulo": str(item.get("titulo") or CATALOGO_IA[tipo]["descricao"])[
                    :120
                ],
                "config": config,
            }
        )

    # Remove repetidos mantendo a primeira ocorrência: um KPI dobrado na tela
    # parece defeito, e o produtor não sabe se é o motor ou a tela.
    vistos: set[str] = set()
    unicos: list[dict] = []
    for w in widgets:
        if w["tipo"] in vistos:
            descartados.append(f"repetido:{w['tipo']}")
            continue
        vistos.add(w["tipo"])
        unicos.append(w)

    if len(unicos) > MAX_WIDGETS:
        descartados.append(f"acima_do_teto:{len(unicos)}")
        unicos = unicos[:MAX_WIDGETS]

    return unicos, descartados


def normalizar_layout(bruto: Any) -> str:
    layout = str(bruto or "").strip()
    if layout in LAYOUTS_VALIDOS:
        return layout
    # "grid-mixed" é o padrão de propósito: uma mesa de operação quase nunca é
    # uma grade perfeita — são KPIs pequenos e um gráfico grande ao lado.
    return "grid-mixed"


# ---------------------------------------------------------------------------
# GEOMETRIA POR WIDGET
#
# O layout era, até aqui, uma escolha de 4 strings (LAYOUTS_VALIDOS). A IA
# escolhia `grid-mixed` e o frontend calculava a geometria. Ela não conseguia
# dizer "este widget é 20 de largura na linha 20" porque não havia ONDE dizer:
# grep de gridX|gridW no pipeline do palco (palco.py, palco_dados.py,
# api/views/amplia_palco.py) não retorna nada.
#
# A grade do dashboard é de 64 colunas (ver os gridW:20 dos widgets em
# index.html). Sem isso, a IA não tem como mover nem redimensionar widget, e o
# "editar o preset" que o produtor pediu não tem por onde acontecer.
#
# A dúvida: um 1B vai mandar gridW:900 e gridX:-40. A resposta NÃO é erro 500 —
# é descartar a geometria daquele widget e manter o layout automático, porque
# um widget com geometria má é pior que um widget sem geometria. Ver
# app/ia/intents.py:1024-1026: "a validação é o que torna isto seguro para um
# modelo de 1B".
# ---------------------------------------------------------------------------
GRADE_COLUNAS = 64
GRADE_LINHAS_MAX = 200
COLUNAS_MIN = 2
COLUNAS_MAX = 64
LINHAS_MIN = 1


def _int_dentro(valor: Any, minimo: int, maximo: int, padrao: int) -> int:
    """Converte para int dentro de um intervalo, ou devolve o padrão.

    `bool` é subclasse de `int` em Python: True viraria 1 e passaria na
    validação. Um modelo que mandou `true` onde queria um número não está
    descrevendo geometria, e a resposta é o padrão, não um widget deslocado.
    """
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        return padrao
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        return padrao
    if n < minimo or n > maximo:
        return padrao
    return n


def normalizar_geometria(bruto: Any) -> dict | None:
    """A geometria que o widget pediu, ou None se não pediu ou pediu loucura.

    Devolve None — e o widget continua com layout automático — quando:
      - não veio nada (o caso normal hoje, e continua válido);
      - veio incompleto (só gridW, sem gridX): adivinhar a posição seria
        inventar onde o produtor quer o gráfico;
      - algum valor está fora dos limites.

    A distinção entre "não pediu" e "pediu errado" é o que impede que a
    validação vire mais uma fonte de bug: o primeiro é o caso comum e não pode
    levantar erro; o segundo é raro e cai no automático.
    """
    if not isinstance(bruto, dict):
        return None
    # qualquer uma das quatro chaves provoca o caminho da geometria
    if not ({"gridX", "gridY", "gridW", "gridH"} & set(bruto)):
        return None

    x = _int_dentro(bruto.get("gridX"), 0, GRADE_COLUNAS - 1, -1)
    y = _int_dentro(bruto.get("gridY"), 0, GRADE_LINHAS_MAX, -1)
    w = _int_dentro(bruto.get("gridW"), COLUNAS_MIN, COLUNAS_MAX, -1)
    h = _int_dentro(bruto.get("gridH"), LINHAS_MIN, GRADE_LINHAS_MAX, -1)

    if -1 in (x, y, w, h):
        return None
    if x + w > GRADE_COLUNAS:
        # transbordaria a grade. Cortar a largura caber, mas inventar a largura
        # que o produtor pediu é mudar a mesa dele; melhor o layout automático.
        return None
    return {"gridX": x, "gridY": y, "gridW": w, "gridH": h}


def assinatura_do_intent(intent: str) -> str:
    """A impressão digital de uma pergunta, para o aprendizado casar perguntas
    parecidas.

    Acento é TRANSCRITO, não apagado. Numa app em português, "Histórico",
    "Área" e "Talhão" são literalmente as palavras que o produtor escreve — e um
    smartphone sem acento é o mesmo produtor no mesmo dia. Descartar o
    acento separava "histórico" de "historico" em duas assinaturas, e o Like de
    uma deixava de ensinar a outra: exatamente o que o aprendizado existe para
    evitar.

    Depois, só ficam letras e números, em minúsculas. Assim "Qual o histórico
    do talhão 2?", "qual o historico do talhao 2" e "Histórico: talhão 2" caem
    na MESMA assinatura.
    """
    decomposto = unicodedata.normalize("NFKD", str(intent or "").lower())
    sem_marcas = "".join(c for c in decomposto if not unicodedata.combining(c))
    limpo = "".join(c for c in sem_marcas if c.isalnum())
    return limpo[:160]


# ---------------------------------------------------------------------------
# PATCH PARCIAL — o que o palco.edit aplica
#
# render_preset SUBSTITUI a mesa inteira: o modelo manda a lista completa e a
# antiga é descartada (tests_palco_fio: "uma mesa nova substitui a antiga, não
# acumula"). Isso é o que torna a edição impossível — não há como dizer "só
# mexe neste".
#
# aplicar_operacoes() é a peça que falta: recebe a lista atual e uma lista de
# operações, e devolve a lista nova. É função PURA — não toca em banco, não
# chama LLM, não levanta exceção. Operação inválida é DESCARTADA e as válidas
# aplicam, porque o modelo é 1B e vai errar o formato (ver intents.py:1024).
#
# Operações:
#   {"op": "add",    "widget": {...}}                  adiciona (validado)
#   {"op": "remove", "tipo": "kpi-custo"}              remove por tipo
#   {"op": "move",   "tipo": "kpi-custo", "geom": {...}}  define posição
#   {"op": "resize", "tipo": "kpi-custo", "geom": {...}}  define tamanho
#
# move e resize são a mesma operação por dentro (ambos gravam geometria), mas
# ficam separados no nome porque é assim que o produtor pensa: "move este" e
# "aumenta este" são pedidos diferentes, mesmo que o efeito seja o mesmo campo.
# ---------------------------------------------------------------------------


def aplicar_operacoes(
    widgets: list[dict], operacoes: Any
) -> tuple[list[dict], list[str]]:
    """Aplica um patch parcial à mesa. Devolve (widgets_novos, descartados).

    Nunca levanta. Cada operação inválida vira um motivo em `descartados` e a
    mesa segue com o resto — a mesma regra do validar_estrutura, aplicada ao
    patch em vez da mesa inteira.
    """
    if not isinstance(operacoes, list):
        return list(widgets), ["operacoes_nao_lista"]

    # cópia rasa: não mutar a lista que o chamador passou
    novos = [dict(w) for w in widgets]
    descartados: list[str] = []

    for op in operacoes:
        if not isinstance(op, dict):
            descartados.append("op_nao_objeto")
            continue
        tipo_op = str(op.get("op") or "").strip().lower()

        if tipo_op == "add":
            bruto = op.get("widget")
            if not isinstance(bruto, dict):
                descartados.append("add_sem_widget")
                continue
            # reusa a validação da mesa: um widget inventado não entra
            validos, desc = validar_estrutura([bruto])
            if not validos:
                descartados.extend(f"add:{d}" for d in desc)
                continue
            # não duplica tipo: um KPI dobrado na tela parece defeito
            if any(w["tipo"] == validos[0]["tipo"] for w in novos):
                descartados.append(f"add:repetido:{validos[0]['tipo']}")
                continue
            if len(novos) >= MAX_WIDGETS:
                descartados.append(f"add:acima_do_teto:{MAX_WIDGETS}")
                continue
            novos.append(validos[0])

        elif tipo_op == "remove":
            alvo = str(op.get("tipo") or "").strip()
            antes = len(novos)
            novos = [w for w in novos if w["tipo"] != alvo]
            if len(novos) == antes:
                descartados.append(f"remove:nao_encontrado:{alvo or '?'}")

        elif tipo_op in ("move", "resize"):
            alvo = str(op.get("tipo") or "").strip()
            geo = normalizar_geometria(op.get("geom") or op.get("geometry"))
            if geo is None:
                descartados.append(f"{tipo_op}:geometria_invalida:{alvo or '?'}")
                continue
            achou = False
            for w in novos:
                if w["tipo"] == alvo:
                    w["config"] = {**(w.get("config") or {}), **geo}
                    achou = True
                    break
            if not achou:
                descartados.append(f"{tipo_op}:nao_encontrado:{alvo or '?'}")

        else:
            descartados.append(f"op_desconhecida:{tipo_op or '?'}")

    return novos, descartados
