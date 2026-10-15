"""O Chamado Amplia — a peça que a IA escreve, e a única onde ela pode.

O QUE MUDOU COM ESTE MÓDULO
===========================
Antes, a IA compunha widgets de um catálogo de 17 (`app/ia/palco.py::CATALOGO_IA`)
e não tinha texto nenhum: o vocabulário possível era `tipo` + `titulo` + `config`.
Um gráfico era `chart-safras`, UM gráfico fixo. Uma tabela era `table-financeiro`,
UMA tabela fixa. Não havia como a IA escrever uma frase, escolher as séries de um
gráfico, ou escolher as colunas de uma tabela — porque não havia bloco onde isso
vivesse.

O dashboard, esse, tinha 60 widgets em `catalog.json` e uma paleta de
drag-and-drop (`app/static/js/widget-palette.js`). Ou seja: **os widgets sempre
existiram; o que não existia era a IA ser informada deles, e não haver lugar para
texto.** Este módulo fecha as duas metades.

A TRAVA: POR QUE ELA EXISTE
===========================
O produto tem dois mundos que não falavam: o manual (60 widgets, editáveis à mão)
e o da IA (17 widgets, efémeros). Junta-se a isto o facto de o produtor poder
fixar dashboards que pagou, apagou, renomeou e organizou — e uma IA com permissão
de escritaamposta sobre eles reescreve o trabalho de quem os organiza.

Por isso a escrita tem **uma zona por omissão, e só uma**: o Chamado Amplia. Não é uma
restrição que se pode desligar porque um dia é útil desligar — é a razão de o
produtor poder confiar que o resto dos presets dele é dele.

    pode_escrever(user, "chamado-amplia")                    -> True
    pode_escrever(user, "custom-custo")                      -> False, com o motivo
    pode_escrever(user, "custom-custo", pedido_explicito=True) -> True

A terceira linha é a Fase 2, e é uma excepção **autorizada, não silenciosa**. O
`pedido_explicito` não vem dos `params` — vem da resposta do produtor ao
`confirm`, que é o mecanismo do `sandbox`. Um `custom-*` continua fechado a
escrita espontânea; o que muda é que o produtor passou a poder dizer "guarda
esta tela" e ter a tela guardada, em vez de a tela se perder quando a conversa
acabou. A promessa que continua a valer é a que importa: **a IA não reescreve o
que construíste sem pedires.**

O motivo importa tanto quanto o `False`. Uma IA que devolve só "não" faz o produtor
achar que a IA está avariada; a mesma IA que devolve "não, mas posso fazer isso no
Chamado Amplia" é uma IA que o produtor percebe. É a regra de
`amplia_desenhar_pagina` aplicada à escrita.

O QUE ESTE MÓDULO NÃO É
=======================
Não é HTML, não é `eval`, não é um schema livre, e não é uma segunda porta de
execução. A escrita continua a passar por `sandbox.executar` — como tudo o resto
que a IA toca. O que este módulo decide é *se pode* e *como fica depois*, nunca
*executa por fora*.

Como na docela do resto do AmplIA: `validar_blocos()` NUNCA levanta. Um LLM de 1,7B
vai mandar o formato errado, e uma traceback na pergunta analítica mais importante
do produto é pior do que uma mesa a menos.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.ia.proveniencia import Estado

# --------------------------------------------------------------------------
# A ZONA DE ESCRITA
# --------------------------------------------------------------------------

#: O preset onde a IA pode escrever. UM, por instalação, e de sistema — por isso
#: o mesmo slug em todas as contas: é uma ferramenta do produto, não conteúdo do
#: produtor. Cada produtor tem o SEU,isolado pelo `user` como toda a tabela.
SLUG_CHAMADO = "chamado-amplia"

NOME_CHAMADO = "Chamado Amplia"

#: O slug faz parte de `app.presets.PRESETS_SISTEMA`. Sem isso,
#: `preset_permitido("chamado-amplia")` devolvia False e a validação que existe
#: para apanhar presets fantasma APAGAVA a peça principal — o mesmo modo de
#: falha que a docstring de `amplia_palco.py` já descreve: "a mesa é criada e
#: nunca mais aparece no menu — um botão que parece funcionar e não faz nada".

#: Limite de blocos por chamado. Acima disto a tela deixa de ser "visão rápida" e
#: passa a ser o relatório que o produtor estava a tentar não ler. O teto é uma
#: restrição de produto, e é por isso que é uma constante com nome.
MAX_BLOCOS = 24

#: Limite do corpo de um bloco de texto. 4000 caracteres é ~1 página; um bloco de
#: prosa maior é um documento, e documentos têm outro caminho.
MAX_TEXTO = 4000

#: Limite de linhas de uma tabela/planilha. Uma tabela que não cabe num ecrã
#: de telemóvel tem de ser uma exportação, não um bloco.
MAX_LINHAS = 200

MAX_TITULO = 120


# --------------------------------------------------------------------------
# O CATÁLOGO DE BLOCOS
# --------------------------------------------------------------------------
#: Cada entrada declara os campos que o bloco PEDE. O catálogo é a fronteira:
#: um bloco de tipo desconhecido é descartado e a peça monta-se com o resto — a
#: mesma doutrina de `palco.validar_estrutura`, pela mesma razão: um LLM pequeno
#: insiste quando recebe "não", e monta-se com o que presta quando recebe o
#: motivo.
#:
#: `campos` é o que o MCP publica. Sem isto, um agente externo teria de adivinhar
#: o nome dos campos — e a adivinhacao com nome errado é um bloco vazio na tela.
CATALOGO_BLOCOS: dict[str, dict[str, Any]] = {
    # --- prosa -------------------------------------------------------------
    "texto": {
        "descricao": "Um parágrafo de análise escrita pela IA.",
        "campos": ["texto"],
        "obrigatorios": ["texto"],
        # A prosa não sai de uma consulta. É o único bloco que não carrega dado
        # medido, e é por isso que leva o separador abaixo.
        "origem": "prosa",
    },
    # --- número ------------------------------------------------------------
    "kpi": {
        "descricao": (
            "Um número grande com o valor e uma frase que diga o que é. "
            "Use um id de `amplia_catalogos.widgets`."
        ),
        "campos": ["widget"],
        "obrigatorios": ["widget"],
        "origem": "dado",
    },
    # --- séries ------------------------------------------------------------
    "grafico": {
        "descricao": (
            "Um gráfico de barras, linha ou pizza com as séries que o produtor "
            "pedir. As séries saem do banco; a escolha das séries é sua."
        ),
        "campos": ["tipo_dado", "titulo", "rotulo", "colunas", "fonte_widget"],
        "obrigatorios": ["rotulo", "colunas"],
        "origem": "dado",
    },
    # --- malhas ------------------------------------------------------------
    "tabela": {
        "descricao": (
            "Uma tabela de leitura. Escolhe as COLUNAS, não um widget inteiro. "
            "Para exportar, use planilha."
        ),
        "campos": ["titulo", "colunas", "linhas"],
        "obrigatorios": ["colunas"],
        "origem": "dado",
    },
    "planilha": {
        "descricao": (
            "Uma tabela que o produtor pode EXPORTAR (xlsx/csv) e em que pode "
            "corrigir valores. É o bloco para 'me dá isso para levar para a "
            "contabilidade'."
        ),
        "campos": ["titulo", "colunas", "linhas", "editavel"],
        "obrigatorios": ["colunas"],
        "origem": "dado",
    },
}

#: Os que carregam número. Um bloco de prosa com número não rastreado é o
#: defeito que este catálogo existe para travar — ver `rastrear_numeros`.
BLOCOS_DADO = frozenset(k for k, v in CATALOGO_BLOCOS.items() if v["origem"] == "dado")

TIPOS_GRAFICO = frozenset({"barras", "linha", "pizza", "area"})


def bloco_permitido(tipo: str) -> bool:
    return tipo in CATALOGO_BLOCOS


def campos_conhecidos(tipo: str) -> tuple[str, ...]:
    """Os campos que o bloco aceita.

    DIFFERENTE de `palco.campos_conhecidos`, que lia `CATALOGO_IA[tipo]["campos"]`
    — chave que NENHUMA entrada do catálogo declarava, e portanto devolvia
    `set()` para os 17 widgets, sempre. Esta lê a chave que o catálogo deste
    módulo escreve, e há teste a falhar se algum dia deixar de estar escrito.
    """
    return tuple(CATALOGO_BLOCOS.get(tipo, {}).get("campos", ()))


# --------------------------------------------------------------------------
# A TRAVA DE ESCRITA
# --------------------------------------------------------------------------


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar_slug(valor: str) -> str:
    """O slug canónico, para a comparação da trava não depender da escrita.

    "Chamado Amplia", "chamado-amplia" e "CHAMADO  AMPLIA" são a mesma zona. Sem
    isto, a trava falhava por causa de uma maiúscula — e uma trava que falha por
    um acento não é uma trava, é uma fonte de erro sem aviso: o produtor vê
    "não posso" numa peça que a IA depois escreve no mesmo sítio.
    """
    limpo = "".join(c for c in _sem_acento(valor).lower() if c.isalnum() or c in "-_ ")
    return "-".join(limpo.split()).strip("-")


def e_zona_de_escrita(slug: str) -> bool:
    return normalizar_slug(slug) == normalizar_slug(SLUG_CHAMADO)


def _PRESETS_DO_PRODUTO() -> frozenset:
    """Os painéis que são DO PRODUTO. Espelho de `app.presets.PRESETS_SISTEMA`.

    É uma função e não uma constante no topo do módulo porque `app.presets` não
    pode ser importado na importação deste módulo: `presets.py` não importa nada
    daqui, mas um `import` no topo tornaria a ordem de importação parte do
    comportamento. A leitura é adiada para dentro da função.
    """
    from app import presets

    return presets.PRESETS_SISTEMA


def e_preset_do_produtor(slug: str | None) -> bool:
    """Este preset é DO PRODUTOR, e por isso a IA pode escreve-lo — a pedido.

    "Do produtor" tem uma definição, e não é `not <e uma zona de escrita>`:
    é `preset_permitido()` MENOS `PRESETS_SISTEMA`. A diferença importa —
    `amplia`, `chamado-amplia` e `base-ia` estão em `PRESETS_SISTEMA`, e
    `preset_permitido()` diz que eles *podem existir no dashboard*. São do
    produto, não do produtor, e a IA não os reescreve nem a pedido.

    Reutiliza `app/presets.py` em vez de repetir o prefixo `custom-`: esse
    ficheiro é a fonte única, e a sua própria nota de topo diz que alterar lá
    muda os dois lados de uma vez. Uma segunda lista do prefixo aqui seria a
    lista que seesquece de ser actualizada.
    """
    from app import presets

    if not slug:
        return False
    slug = str(slug).strip()
    if slug in _PRESETS_DO_PRODUTO():
        return False
    return presets.preset_permitido(slug)


def pode_escrever(
    user, preset_slug: str | None, pedido_explicito: bool = False
) -> tuple[bool, str]:
    """A única função que decide se a IA pode mexer. Devolve (pode, motivo).

    O motivo volta SEMPRE com o `False`, e é o que a IA diz ao produtor. Um "não"
    sem explicação produz o sintoma exato que este produto já teve: o produtor
    olha para ecrã nenhum e conclui que a IA está avariada.

    `pedido_explicito` é a autorização do PRODUTOR, e é o que separa as duas
    garantias. Sem ele, a regra é a de sempre e continua a ser verdade: a IA
    só escreve no Chamado. Com ele, pode escrever num preset `custom-*` — o que
    o produtor construiu — mas **só porque ele pediu**.

    E' PORQUÊ ISTO NÃO É UM `if` NO HANDLER
    =========================================
    `pedido_explicito` não pode ser um campo dos `params`. Se o chamador o
    ligasse a um campo que o modelo preenche, a guarda seria decorativa: o
    modelo marcava o próprio.check e escrevia no preset do produtor, e o texto
    da promessa continuaria a dizer que nao o faz. A autoria do sinal tem de
    estar onde o modelo nao chega — na RESPOSTA do produtor, que é o `confirm`
    que o `sandbox` aplica depois da maquina de estados. E' por isso que o
    parametro aqui e' um booleano recebido de fora, e nao um nome de preset: o
    `slug` e' do produtor escolher, e o que o autoriza e' ter dito "sim".
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False, "sem produtor identificado: o Chamado Amplia é por produtor."

    if preset_slug is None or not str(preset_slug).strip():
        # O palco efémero não é a zona. Criar a primeira peça é criação, não
        # edição, e é o que `chamado_criar` faz — mas apontar para um preset em
        # branco é sempre um pedido malformado, e dizer que sim seria escrever
        # num sítio que não existe.
        return False, (
            "Falta indicar o preset. O único preset que a IA pode escrever é o "
            f"'{NOME_CHAMADO}'."
        )

    if e_zona_de_escrita(preset_slug):
        return True, ""

    if pedido_explicito and e_preset_do_produtor(preset_slug):
        return True, ""

    # O motivo distingue os três "não", porque são três coisas diferentes e o
    # produtor não pode ficar com o mesmo texto para três casos. Dizer "é seu e
    # a IA não escreve" a quem acabara de pedir o contrário é o produto a
    # responder como se não tivesse ouvido.
    if e_zona_de_escrita(preset_slug):
        # Inalcançável na prática: o slug da zona passou no teste de cima.
        return True, ""

    if str(preset_slug).strip() in _PRESETS_DO_PRODUTO():
        return False, (
            f"'{preset_slug}' é um painel do Amplia, não teu — não se guarda lá "
            "uma tela. Posso guardar no Chamado Amplia ou num dashboard teu."
        )

    if pedido_explicito:
        # Pediu, mas o slug não é de ninguém. `visao-geral` cai aqui porque é
        # um preset BLOQUEADO (`app/presets.py::PRESET_BLOCK`), não porque
        # exista: a limpeza de fantasmas apagaria-o a seguir, e guardar uma tela
        # num preset que vai desaparecer é prometer uma tela que não fica.
        return False, (
            f"Não encontro um painel chamado '{preset_slug}'. Os teus dashboards "
            f"começam por 'custom-'. Posso criar esse nome, ou guardar no {NOME_CHAMADO}."
        )

    return False, (
        f"O preset '{preset_slug}' é teu e a IA não escreve nele por conta "
        f"própria — só lê. Se queres guardar esta tela aí, diz 'guarda esta tela' "
        f"e eu pergunto antes; para mudar outra coisa, diga o que mudar e faço "
        f"no {NOME_CHAMADO}."
    )


# --------------------------------------------------------------------------
# NÚMEROS RASTREÁVEIS — a norma que o texto tem de cumprir
# --------------------------------------------------------------------------

#: Um número escrito em prosa. O padrão é deliberadamente largo: quer o `1.234,56`
#: e o `42%`, e não quer o `2024` de "safra 2024" — que é um ANO, não uma
#: medida. Sem essa exclusão, quase toda a frase innocuousa vira "número não
#: rastreado" e o alerta deixa de valer alguma coisa.
#: Um número escrito em prosa, com a ordem das alternativas a IMPORTA.
#:
#: O formato brasileiro (`1.234,56`) tem de vir ANTES do que só agrupa
#: milhares (`1.234`): o `re` tenta as alternativas pela ordem e para na
#: primeira que casa. Com o inverso, "1.234,56" produzia DOIS números — "1.234"
#: e "56" — e o produtor via dois avisos de "número não rastreado" para o mesmo
#: valor, o que treina o PRODUTOR a ignorar o aviso.
#:
#: E a unidade não pode ser `\s*`: com zero espaços, "89total" casava `89` e
#: depois `t` de "total" como se fosse a unidade "t" (tonelada). Passava-me
#: isto a dizer que o número era "89t", num texto onde não há 89 toneladas.
#: Por isso `%` e `R$` ligam sem espaço (são símbolos, não palavras) e as
#: unidades com letra exigem espaço antes e fim de palavra depois.
_RE_NUMERO = re.compile(
    r"(?<![\w-])("
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)+"  # 1.234,56 e 1.234.567,89
    r"|\d{1,3}(?:\.\d{3})+"  # 420.000
    r"|\d+,\d+"  # 45,5
    r"|\d+(?:\.\d+)?"  # 30
    r")"
    r"(\s*(?:%|R\$)|\s+(?:ha|kg|t|sc)\b(?![\w]))?",
    re.I,
)

#: Separadores de data EM TORTO do número. A data de um lançamento financeiro é
#: real e não precisa de rastreio — é o próprio dado, e rastreá-la faria o alerta
#: disparar em "12/03/2026" e perder o que interessa.
#:
#: O teste olha para os caracteres VIZINHOS do NÚMERO, e é `m.end(1)` — o fim
#: do grupo 1, não o fim da match. A diferença não é um detalhe: em "45,5 ha." o
#: fim da match é o ponto final da frase, e perguntar "isto é uma data?" ao ponto
#: final respondia sempre que sim. O número é que precisa de saber se é data.
#:
#: E NÃO HÁ PONTO NESTA LISTA. Estava, e medido:
#:
#:     'A semente custou 77,77.'  ->  []      <- devia ser ['77,77']
#:     'O adubo custou 1.234,56.' ->  []      <- devia ser ['1.234,56']
#:
#: O ponto final da frase entrava na lista de separadores de data, e portanto
#: TODO o número no fim de uma frase era descartado. A rastreabilidade — a norma
#: do produto — devolveva `medido` quase sempre, que é o carimbo de "isto está
#: certo". Um validador que passa sempre é pior do que nenhum, porque dá a
#: confiança de que o número foi conferido.
#:
#: O ponto final de "1.234" nunca precisou de estar aqui: o padrão do número já
#: lê "1.234.567" como um só número, e o `-` de "03-2025" é apanhado pelo `-`.
#: Um teste de regressão em `tests_chamado.py::test_ignora_ponto_final` fecha a
#: porta.
_SEPARADOR_DATA = "/-"

#: Um número isolado, sem casa decimal e sem unidade, dentro da faixa de anos, é
#: um ANO — e um ano não é uma medida. "a safra 2024 fechou a 30 sc/ha" só tem de
#: rastrear o 30.
#:
#: A faixa é estreita de propósito (1970-2099). Um `20` solto não é um ano, é um
#: número, e apanhá-lo como ano seria a forma de um valor real passar sem
#: rastreio. A regra é "só duvidoso quando a dúvida é plausível", e 2024 é.
_E_ANO = re.compile(r"^\s*(19|20)\d{2}\s*$")


def numeros_no_texto(texto: str) -> list[str]:
    """Os números de um texto, sem anos, sem datas e sem a numeração da lista.

    Devolve o NÚMERO, sem a unidade. A unidade não interessa para a pergunta que
    esta função faz — "este número está em algum bloco de dado?" — e juntá-la
    fazia "30 sc/ha" não casar com um `30` que o banco Declara. O que se compara
    é a medida, não a sua unidade.
    """
    achados: list[str] = []
    for m in _RE_NUMERO.finditer(texto or ""):
        numero = m.group(1).strip()
        unidade = (m.group(2) or "").strip()
        if not numero:
            continue
        antes = texto[m.start(1) - 1] if m.start(1) > 0 else ""
        depois = texto[m.end(1)] if m.end(1) < len(texto) else ""
        # `and` ANTES do `in`, e não depois. `"" in "/-."` é True em Python: a
        # string vazia éoka em qualquer string. Sem esta guarda, o primeiro
        # número de um texto que começa com ele — "1.234,56 no total" — era
        # tomado por uma data e descartado, e a peça passava a ter um número
        # por rastrear que ninguém via. É o tipo de bug que só aparece com o
        # número na PRIMEIRA posição, que é onde os números grandes estão.
        if antes and antes in _SEPARADOR_DATA:
            continue
        if depois and depois in _SEPARADOR_DATA:
            continue
        if not unidade and _E_ANO.match(numero):
            continue
        achados.append(numero)
    return achados


def _numeros_conhecidos(corpo: list[dict]) -> set[str]:
    """Todos os valores que os blocos de DADO declararam."""
    conhecidos: set[str] = set()
    for b in corpo:
        if b.get("tipo") not in BLOCOS_DADO:
            continue
        for linha in _linhas_de(b):
            for valor in linha:
                if valor is None or isinstance(valor, bool):
                    continue
                txt = str(valor).strip()
                if not txt:
                    continue
                conhecidos.add(txt.replace(",", "."))
                try:
                    conhecidos.add(f"{float(txt):g}")
                except (TypeError, ValueError):
                    pass
                # A MESMA leitura que se faz ao texto. Uma tabela que declara
                # "18%" tem de sustentar um texto que diz "18%" — e sem isto a
                # comparação era entre "18" (do texto, sem unidade) e "18%"
                # (da célula, com unidade), que nunca casam, e toda a
                # rastreabilidade de percentagens era silenciosamente perdida.
                conhecidos.update(numeros_no_texto(txt))
    return conhecidos


def _linhas_de(b: dict) -> list[list[Any]]:
    """As linhas de um bloco de malha, seja ele `tabela`, `planilha` ou série.

    LÊ DE `config`, e não da raiz do bloco. `validar_blocos` põe tudo o que a IA
    mandou dentro de `config` — e uma versão anterior desta função lia
    `b.get("linhas")` na raiz, que dá sempre `None`. O efeito era silencioso e
    terrível: nenhuma tabela tinha linhas, todos os blocos de dado desciam a
    `sem_dado`, e nenhum teste de integração falhava porque cada teste construía
    o bloco à mão com `linhas` na raiz. Um teste que escreve o objeto de uma
    maneira e o código o lê de outra não testa nada — passa a testar a forma
    errada.
    """
    cfg = b.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
    linhas = cfg.get("linhas")
    if isinstance(linhas, list):
        return [x if isinstance(x, list) else [x] for x in linhas]
    return []


def rastrear_numeros(corpo: list[dict]) -> list[dict]:
    """Os números que um texto afirma e nenhum bloco de dado sustenta.

    É a norma do produto em forma executável: **um número que a IA escreveu tem de
    estar em algum bloco de dado da mesma peça.** Uma peça com "a margem caiu para
    18%" e nenhum bloco que mostre 18% é uma peça que afirma; e uma peça que
    afirma números é uma peça de que o produtor vai decidir a safra.

    Não é motivo para recusar o texto — seria devolver ao produtor "não posso
    escrever", que é o pior resultado possível. O texto entra, e a sua
    `fonte_dado` desce para `sem_dado`, que é o estado que o painel e o produtor
    já sabem ler.
    """
    conhecidos = _numeros_conhecidos(corpo)
    achados: list[dict] = []
    for i, b in enumerate(corpo):
        if b.get("tipo") != "texto":
            continue
        texto = str(b.get("config", {}).get("texto") or "")
        for numero in numeros_no_texto(texto):
            chave = numero.replace(",", ".")
            if chave in conhecidos or numero in conhecidos:
                continue
            try:
                if f"{float(chave):g}" in conhecidos:
                    continue
            except (TypeError, ValueError):
                pass
            achados.append({"bloco": i, "numero": numero})
    return achados


# --------------------------------------------------------------------------
# VALIDAR — nunca levanta
# --------------------------------------------------------------------------


def _linhas_normalizadas(bruto: Any) -> list[list[Any]]:
    if not isinstance(bruto, list):
        return []
    saida: list[list[Any]] = []
    for linha in bruto[:MAX_LINHAS]:
        if isinstance(linha, list):
            saida.append(list(linha[:MAX_BLOCOS]))
        elif isinstance(linha, dict):
            saida.append([linha.get(k) for k in linha])
        elif isinstance(linha, (str, int, float)) or linha is None:
            saida.append([linha])
        else:
            saida.append([str(linha)])
    return saida


def _colunas_normalizadas(bruto: Any, linhas: list[list[Any]]) -> list[str]:
    if isinstance(bruto, list):
        return [str(c)[:60] for c in bruto[:MAX_BLOCOS] if str(c).strip()][:MAX_BLOCOS]
    # Sem colunas declaradas, infere-se da largura da linha mais longa. Uma
    # planilha com 4 campos e nenhuma coluna nomeada é inutilizável, e o modelo
    # esquece-se sempre das colunas — o campo é declarado "obrigatório" no
    # catálogo e mesmo assim chega vazio.
    largura = max((len(x) for x in linhas), default=0)
    return [f"coluna_{i + 1}" for i in range(largura)]


def validar_blocos(
    bruto: Any, corpo_atual: list[dict] | None = None
) -> tuple[list[dict], list[str]]:
    """Normaliza o que a IA mandou. Devolve (blocos, descartados).

    `corpo_atual` é a peça que já existe: os ids continuam. Sem ele, um
    `remover {id: "b3"}` depois de um `adicionar` não encontra o alvo — e uma
    edição que depende de ids que mudam a cada chamada é uma edição que não
    funciona duas vezes seguidas.
    """
    if isinstance(bruto, dict):
        if "blocos" not in bruto:
            return [], ["sem_chave_blocos"]
        bruto = bruto.get("blocos")
    if not isinstance(bruto, list):
        return [], ["estrutura_nao_lista"]

    proximo = 1
    for b in corpo_atual or []:
        m = re.match(r"^b(\d+)$", str(b.get("id") or ""))
        if m:
            proximo = max(proximo, int(m.group(1)) + 1)

    blocos: list[dict] = []
    descartados: list[str] = []

    for item in bruto:
        if isinstance(item, str):
            item = {"tipo": item}
        if not isinstance(item, dict):
            descartados.append("item_nao_objeto")
            continue
        tipo = str(item.get("tipo") or item.get("type") or "").strip()
        if not bloco_permitido(tipo):
            descartados.append(f"desconhecido:{tipo or '?'}")
            continue

        cfg_bruta = item.get("config")
        cfg: dict[str, Any] = dict(cfg_bruta) if isinstance(cfg_bruta, dict) else {}
        # Um bloco escrito sem `config` mas com as chaves no próprio item é o
        # formato mais natural que um LLM produz. Rejeitá-lo por isso seria
        # estar a castigar a forma, não o conteúdo.
        for k, v in item.items():
            if k not in ("tipo", "type", "id", "config"):
                cfg.setdefault(k, v)

        linhas = _linhas_normalizadas(cfg.get("linhas"))
        if "linhas" in CATALOGO_BLOCOS[tipo]["campos"]:
            cfg["linhas"] = linhas
        if "colunas" in CATALOGO_BLOCOS[tipo]["campos"]:
            cfg["colunas"] = _colunas_normalizadas(cfg.get("colunas"), linhas)
        if tipo == "texto":
            cfg["texto"] = str(cfg.get("texto") or "")[:MAX_TEXTO]
        if tipo == "grafico":
            g = str(cfg.get("tipo_dado") or "barras").strip().lower()
            cfg["tipo_dado"] = g if g in TIPOS_GRAFICO else "barras"
        if tipo == "planilha":
            cfg["editavel"] = bool(cfg.get("editavel", True))

        titulo = str(cfg.get("titulo") or CATALOGO_BLOCOS[tipo]["descricao"])[
            :MAX_TITULO
        ]
        cfg["titulo"] = titulo

        blocos.append(
            {
                "id": f"b{proximo}",
                "tipo": tipo,
                "titulo": titulo,
                "config": cfg,
                # O carimbo viaja no bloco, não é decidido à chegada: um bloco
                # escrito à mão e um enriquecido pelo servidor têm de chegar ao
                # ecrã com o mesmo formato, ou o frontend tem de saber de onde
                # cada um veio. Ver `paginas.py::montar`, que é o mesmo raciocínio.
                "fonte_dado": Estado.SEM_DADO,
            }
        )
        proximo += 1

    # Ids repetidos nunca: um `remover` tem de ter um alvo único.
    vistos: set[str] = set()
    unicos: list[dict] = []
    for b in blocos:
        if b["id"] in vistos:
            b["id"] = f"b{proximo}"
            proximo += 1
        vistos.add(b["id"])
        unicos.append(b)

    if len(unicos) > MAX_BLOCOS:
        descartados.append(f"acima_do_teto:{len(unicos)}")
        unicos = unicos[:MAX_BLOCOS]

    return unicos, descartados


# --------------------------------------------------------------------------
# DELTA — editar sem substituir tudo
# --------------------------------------------------------------------------
#: Substituir a peça inteira a cada pedido obriga a IA a reenviar o que já
#: está feito — e um LLM de 1,7B que reenvia 12 blocos vai perder dois e mudar
#: um sem querer. O produtor vê uma peça que perdeu conteúdo e conclui que a IA
#: "desistiu a meio". O delta corrige isso: cada operação toca no que disse.
OPERACOES = ("adicionar", "remover", "substituir", "reordenar", "reescrever_texto")


def aplicar_delta(corpo: list[dict], delta: Any) -> tuple[list[dict], list[str]]:
    """Aplica um delta. Devolve (corpo_novo, avisos).

    `corpo` NÃO é mutado: o handler grava o resultado, e mutar o objeto que o
    chamador ainda pode estar a ler para um `try/except` é a forma mais barata
    de perder um pedido.
    """
    avisos: list[str] = []
    if isinstance(delta, dict):
        ops = [delta]
    elif isinstance(delta, list):
        ops = [d for d in delta if isinstance(d, dict)]
    else:
        return list(corpo or []), ["delta_invalido"]
    if not ops:
        return list(corpo or []), ["delta_vazio"]

    corpo_novo: list[dict] = [dict(b) for b in (corpo or [])]

    for op in ops:
        acao = str(op.get("op") or op.get("acao") or "").strip().lower()
        if acao not in OPERACOES:
            avisos.append(f"operacao_desconhecida:{acao or '?'}")
            continue

        if acao == "adicionar":
            novos, descartados = validar_blocos(op.get("blocos"), corpo_novo)
            corpo_novo.extend(novos)
            avisos.extend(descartados)
            continue

        alvo_id = str(op.get("id") or "").strip()
        alvo = next((b for b in corpo_novo if b.get("id") == alvo_id), None)

        if acao == "remover":
            if alvo is None:
                avisos.append(f"id_inexistente:{alvo_id or '?'}")
                continue
            corpo_novo = [b for b in corpo_novo if b.get("id") != alvo_id]
            continue

        # `reordenar` ANTES do guard de `alvo`. É a única operação que não tem
        # `id` — opera sobre a lista inteira — e estava depois dele, onde o
        # `alvo is None` a descartava com "id_inexistente". A operação nunca
        # fazia nada, e devolvia um aviso que apontava para o campo errado: quem
        # lesse o aviso achava que tinha de inventar um id, e não que a
        # reordenação estava a ser ignorada.
        if acao == "reordenar":
            ordem = op.get("ordem")
            if not isinstance(ordem, list) or not all(
                isinstance(x, str) for x in ordem
            ):
                avisos.append("ordem_invalida")
                continue
            por_id = {b.get("id"): b for b in corpo_novo}
            nova = [por_id[i] for i in ordem if i in por_id]
            # O que a ordem não mencionou fica no fim, por ordem antiga. Perder
            # um bloco por o produtor não listar um id é perda de trabalho.
            for b in corpo_novo:
                if b.get("id") not in ordem:
                    nova.append(b)
            corpo_novo = nova
            continue

        if alvo is None:
            avisos.append(f"id_inexistente:{alvo_id or '?'}")
            continue

        if acao == "substituir":
            trocado, descartados = validar_blocos([op.get("bloco")], [])
            avisos.extend(descartados)
            if trocado:
                novo = trocado[0]
                novo["id"] = alvo_id
                corpo_novo = [novo if b.get("id") == alvo_id else b for b in corpo_novo]
            continue

        if acao == "reescrever_texto":
            if alvo.get("tipo") != "texto":
                avisos.append(f"nao_e_texto:{alvo_id}")
                continue
            texto = str(op.get("texto") or "")
            if not texto.strip():
                avisos.append(f"texto_vazio:{alvo_id}")
                continue
            alvo["config"] = {**alvo.get("config", {}), "texto": texto[:MAX_TEXTO]}
            alvo["titulo"] = str(alvo["config"].get("titulo") or alvo.get("titulo"))[
                :MAX_TITULO
            ]
            continue

        if acao == "reordenar":
            ordem = op.get("ordem")
            if not isinstance(ordem, list) or not all(
                isinstance(x, str) for x in ordem
            ):
                avisos.append("ordem_invalida")
                continue
            por_id = {b.get("id"): b for b in corpo_novo}
            nova = [por_id[i] for i in ordem if i in por_id]
            # O que a ordem não mencionou fica no fim, por ordem antiga. Perder
            # um bloco por o produtor não listar um id é perda de trabalho.
            for b in corpo_novo:
                if b.get("id") not in ordem:
                    nova.append(b)
            corpo_novo = nova
            continue

    if len(corpo_novo) > MAX_BLOCOS:
        avisos.append(f"acima_do_teto:{len(corpo_novo)}")
        corpo_novo = corpo_novo[:MAX_BLOCOS]

    return corpo_novo, avisos


def aplicar_fonte_dado(corpo: list[dict]) -> list[dict]:
    """Marca cada bloco com `fonte_dado`, decidindo ANTES do ecrã.

    **Um bloco de dado só é `medido` se o SERVIDOR o preencheu.**

    Esta é a regra que a primeira versão não tinha, e é a que importa mais. A
    versão anterior marcava `medido` a qualquer bloco que tivesse linhas — e as
    linhas vinham do que um modelo de 1,7B escreveu. Um número inventado com o
    carimbo `medido` é a pior coisa que este sistema pode mostrar: não dá erro,
    e o produtor multiplica-o pela área dele.

    Por isso o `fonte_dado` de um bloco de dado já vem decidido em
    `aplicar_fontes`, e aqui só se lê. Um bloco sem fonte do servidor desce a
    `sem_dado` com o motivo — que é o que permite ao produtor perceber que
    aquilo é um desenho, e não uma medição.

    Um bloco de prosa apoia-se nos números que os blocos de DADO realmente têm —
    e `aplicar_fontes` é quem põe esse carimbo, depois de descartar as linhas
    que a IA escreveu. Apoiá-lo nas linhas inventadas seria o mesmo erro uma
    segunda vez, com a agravante de parecer verificável.
    """
    # O apoio do texto é calculado AQUI, e não lido de um carimbo que outra
    # função pôs. Ler `b["texto_apoio"]` obrigava a que `aplicar_fontes` tivesse
    # corrido primeiro, e essa era a MESMA classe de defeito que já Twice
    # apanhei: um carimbador que depende de estado que outro maintainer
    # escreve. Chamada isolada, dava `sem_dado` a todos os textos.
    sem_apoio = {a["bloco"] for a in rastrear_numeros(corpo)}

    for i, b in enumerate(corpo):
        cfg = b.get("config") or {}
        if b.get("tipo") in BLOCOS_DADO:
            if b.get("fonte_dado") == Estado.MEDIDO:
                continue
            b["fonte_dado"] = Estado.SEM_DADO
            if not cfg.get("motivo"):
                cfg["motivo"] = (
                    "A IA escreveu os números e não há fonte no servidor. "
                    "Escolha uma fonte para isto ser uma medição."
                )
                b["config"] = cfg
        elif b.get("tipo") == "texto":
            b["texto_apoio"] = i not in sem_apoio
            b["fonte_dado"] = Estado.MEDIDO if b["texto_apoio"] else Estado.SEM_DADO
        else:
            b["fonte_dado"] = Estado.SEM_DADO
    return corpo


def aplicar_fontes(
    user, corpo: list[dict], *, prop=None, talhao: str = ""
) -> list[dict]:
    """Troca as linhas que a IA escreveu pelas linhas que o servidor leu.

    Para cada bloco de DADO:
      - com `fonte` conhecida  -> calcula, põe as linhas, marca `medido`;
      - com `fonte` desconhecida -> descarta as linhas da IA, `sem_dado`;
      - sem `fonte`            -> descarta as linhas da IA, `sem_dado`, com motivo.

    DESCARTAR, E NÃO MOSTRAR COM UM CARIMBO
    =========================================
    A alternativa era mostrar as linhas da IA marcadas a `sem_dado`. Parece mais
    honesta — e é mentira igual: um número inventado à vista do produtor,
    mesmo marcado, é um número que ele vai ler, porque está numa coluna com o
    nome certo e algarismos com o formato certo.

    A diferença é entre "a despesa foi 1.234,56, e este número não vem de lado
    nenhum" e "não sei a despesa — escolhe uma fonte". A primeira ainda se pode
    usar por engano. A segunda obriga a decidir. É esta que serve o produtor.
    """
    from app.ia import chamado_fontes

    def _conta_descartados(b: dict, cfg: dict) -> int:
        """Quantos números foram descartados NESTE bloco, sem perder a história.

        `cfg["linhas"]` só existe enquanto a peça é um rascunho. Assim que a IA
        confirma, `_guarda` tira-as antes de gravar — que é o ponto: a base não
        guarda números que um modelo escreveu. Mas isso significa que, na
        LEITURA, `linhas` já não está lá e `len(...)` dá zero.

        Por isso a primeira versão passava a dar `numeros_descartados = 0` em
        todas as peças, para sempre — porque a linha de baixo estava vazia, não
        porque nada tivesse sido descartado. O produtor lia "0 números
        descartados" numa peça de onde a IA tinha mandado quatro, e a leitura
        affirmava o contrário da verdade.

        Por isso o maior dos dois: o que se conta agora (se alguma coisa ainda
        tem linhas por caminho) e o que ficou registado quando se descartou.
        """
        agora = len(cfg.get("linhas") or [])
        try:
            registado = int(b.get("numeros_descartados") or 0)
        except (TypeError, ValueError):
            registado = 0
        return max(agora, registado)

    for b in corpo:
        if b.get("tipo") not in BLOCOS_DADO:
            continue
        cfg = dict(b.get("config") or {})
        nome_fonte = str(cfg.get("fonte") or "").strip()
        descartadas = _conta_descartados(b, cfg)

        if not nome_fonte:
            b["config"] = _config_sem_linhas(cfg, nome_fonte, "")
            b["config"]["motivo"] = (
                "Sem fonte: a IA escreveu os números e foram descartados. Cite "
                "uma fonte (ver `amplia_catalogos.fontes`) para isto ser uma "
                "medição do seu banco."
            )
            b["fonte_dado"] = Estado.SEM_DADO
            if descartadas:
                b["numeros_descartados"] = descartadas
            continue

        calculado = chamado_fontes.calcular(
            user, nome_fonte, prop=prop, talhao=talhao, filtros=cfg.get("filtros")
        )
        if not calculado.get("ok"):
            b["config"] = _config_sem_linhas(cfg, nome_fonte, calculado.get("erro", ""))
            b["fonte_dado"] = Estado.SEM_DADO
            if descartadas:
                b["numeros_descartados"] = descartadas
            continue

        novo = dict(cfg)
        novo["fonte"] = nome_fonte
        novo["colunas"] = calculado["colunas"]
        novo["linhas"] = calculado["linhas"]
        novo["unidade"] = calculado.get("unidade", "")
        novo.pop("motivo", None)
        b["config"] = novo
        # `medido` SÓ quando o servidor respondeu COM LINHAS. Uma consulta que
        # volta vazia é "não há registo" — e é exactamente isso que um `0`
        # esconde.
        b["fonte_dado"] = Estado.MEDIDO if calculado["linhas"] else Estado.SEM_DADO
        if not calculado["linhas"]:
            b["config"] = {
                **novo,
                "motivo": f"A fonte '{nome_fonte}' foi consultada e não há registo.",
            }
        b["numeros_descartados"] = 0

    # O carimbo do texto é posto APOSTE, e a partir dos números que ficaram.
    sem_apoio = {a["bloco"] for a in rastrear_numeros(corpo)}
    for i, b in enumerate(corpo):
        if b.get("tipo") == "texto":
            b["texto_apoio"] = i not in sem_apoio
    return corpo


def _config_sem_linhas(cfg: dict, fonte: str, motivo: str) -> dict:
    """A config de um bloco de dado que não tem números para mostrar.

    Fica com as colunas e o título — o produtor vê QUE quer ver — e sem linhas.
    Uma moldura com o nome certo é um pedido de dados; uma moldura com números
    dentro é uma mentira com nome de dado.
    """
    novo = {
        "titulo": cfg.get("titulo", ""),
        "colunas": cfg.get("colunas", []),
        "linhas": [],
        "editavel": cfg.get("editavel", True),
        "tipo_dado": cfg.get("tipo_dado", "barras"),
    }
    if fonte:
        novo["fonte"] = fonte
    if motivo:
        novo["motivo"] = motivo
    return novo


def referencia_blocos() -> list[dict[str, Any]]:
    """O dicionário que o MCP publica: o que existe e que campos cada um pede."""
    saida: list[dict[str, Any]] = []
    for tipo in sorted(CATALOGO_BLOCOS):
        spec = CATALOGO_BLOCOS[tipo]
        saida.append(
            {
                "id": tipo,
                "descricao": spec["descricao"],
                "campos": list(spec.get("campos", ())),
                "obrigatorios": list(spec.get("obrigatorios", ())),
                "origem": spec.get("origem", "dado"),
            }
        )
    return saida


def summarise_blocos() -> str:
    """A frase que cabe no prompt do modelo local.

    Diz o número de blocos e a regra que impede a invenção. Esconder a regra
    não a elimina — só faz o modelo descobri-la quando a tela já está errada.
    """
    return (
        f"Tipos de bloco: {len(CATALOGO_BLOCOS)} "
        f"({', '.join(sorted(CATALOGO_BLOCOS))}). "
        "Blocos de dado (kpi, grafico, tabela, planilha) só são 'medido' se "
        "tiverem linhas: sem linhas ficam 'sem_dado'. "
        "Um número que você escrever no texto tem de estar numa linha de algum "
        "bloco de dado; se não estiver, o bloco desce a 'sem_dado'."
    )


#: Teto de linhas de uma série para virar peça. Acima disto o gráfico vira
#: ruído e a tabela não cabe no telemóvel — e uma peça que ninguém lê é uma
#: peça que finge informar.
MAX_LINHAS_SERIE = 31


def serie_valida(serie: Any) -> tuple[bool, str]:
    """O contrato que todo produtor de série assina, verificado num lugar só.

    Uma série é {titulo, rotulo, colunas, linhas, fonte[, filtros]} onde
    colunas é [rotulo_x, rotulo_y] e linhas é [[rotulo, numero], ...].
    Sem `fonte`, a peça não monta: sem fonte o `aplicar_fontes` não tem de
    onde recalcular, e linhas que ninguém recalcula são linhas que ninguém
    carimbou.
    """
    if not isinstance(serie, dict):
        return False, "série não é um objeto"
    titulo = serie.get("titulo")
    if not isinstance(titulo, str) or not titulo.strip():
        return False, "série sem titulo"
    rotulo = serie.get("rotulo")
    if not isinstance(rotulo, str) or not rotulo.strip() or len(rotulo) > 20:
        return False, "série sem rotulo (unidade curta, ex: 'mm')"
    colunas = serie.get("colunas")
    if (
        not isinstance(colunas, list)
        or len(colunas) != 2
        or not all(isinstance(c, str) and c.strip() for c in colunas)
    ):
        return False, "série precisa de colunas [rotulo_x, rotulo_y]"
    linhas = serie.get("linhas")
    if not isinstance(linhas, list) or not linhas:
        return False, "série sem linhas"
    if len(linhas) > MAX_LINHAS_SERIE:
        return False, f"série com linhas demais (teto {MAX_LINHAS_SERIE})"
    for i, linha in enumerate(linhas):
        if not isinstance(linha, list) or len(linha) != 2:
            return False, f"linha {i} não é [rotulo, numero]"
        rot, num = linha
        if not isinstance(rot, str) or not rot.strip():
            return False, f"linha {i} sem rotulo"
        if isinstance(num, bool) or not isinstance(num, (int, float)):
            return False, f"linha {i} sem numero"
        if num != num or num in (float("inf"), float("-inf")):
            return False, f"linha {i} com numero inválido"
    fonte = serie.get("fonte")
    if not isinstance(fonte, str) or not fonte.strip():
        return False, "série sem fonte (quem recalcula?)"
    return True, ""


def peca_de_serie(serie: dict[str, Any], resposta: str) -> dict[str, Any]:
    """Monta a peça rica (texto+grafico+tabela) de uma série medida.

    Os blocos saem SEM linhas e COM `fonte`: quem preenche é o
    `aplicar_fontes`, recalculando — nunca o que viajou na série. Uma série
    que chegasse com linhas prontas para a peça seria um cavalo de Troia
    para número inventado: o carimbo `medido` tem de vir de consulta, não
    de transporte.
    """
    valida, motivo = serie_valida(serie)
    if not valida:
        return {"ok": False, "erro": f"série inválida: {motivo}"}
    titulo = str(serie["titulo"]).strip()[:MAX_TITULO]
    rotulo = str(serie["rotulo"]).strip()
    colunas = [str(c).strip() for c in serie["colunas"]]
    fonte = str(serie["fonte"]).strip()
    filtros = serie.get("filtros") if isinstance(serie.get("filtros"), dict) else {}
    base_fonte: dict[str, Any] = {"fonte": fonte}
    if filtros:
        base_fonte["filtros"] = filtros
    blocos, descartados = validar_blocos(
        [
            {"tipo": "texto", "config": {"texto": str(resposta or "")}},
            {
                "tipo": "grafico",
                "config": {
                    "tipo_dado": "barras",
                    "titulo": titulo,
                    "rotulo": rotulo,
                    "colunas": colunas,
                    **base_fonte,
                },
            },
            {
                "tipo": "tabela",
                "config": {
                    "titulo": titulo,
                    "colunas": colunas,
                    **base_fonte,
                },
            },
        ]
    )
    if not blocos:
        return {"ok": False, "erro": "nenhum bloco sobreviveu à validação"}
    return {
        "ok": True,
        "peca": {
            "nome": titulo,
            "existe": True,
            "estado": "",
            "versao": 1,
            "blocos": blocos,
            "descartados": descartados,
        },
    }
