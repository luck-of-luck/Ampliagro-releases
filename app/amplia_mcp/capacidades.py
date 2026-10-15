"""A capacidade que faltava: a IA saber o que sabe.

Este módulo responde a uma pergunta que nenhuma tool respondia: "o que é
que eu consigo fazer?". E responde a partir do CÓDIGO, não de uma lista
escrita à mão.

POR QUE A LISTA À MÃO SERIA O MESMO BUG DE SEMPRE

Um catálogo escrito a mão diverge do código no primeiro dia em que alguém
mexe numa feature. A versão anterior desta camada dizia "as 65 intents" no
docstring do servidor MCP, e há 76. Não é descuido de ninguém: é o
comportamento natural de uma lista que ninguém actualiza quando a verdade
muda.

Por isso tudo o que está aqui é derivado:
  - os intents, de `app.ia.registro` (que os descobre por introspecção)
  - os campos pedidos, do `required_fields` de cada intent — a verdade
    declarada, não os exemplos em prosa
  - a distinção entre pessoa e máquina, de quem pede `cargo` e quem pede
    `tipo`

O que NÃO é derivado é o texto de ajuda por capacidade — as descrições dos
intents são escritas por uma pessoa e são a intenção, e isso não se
automatiza. A diferença é que o texto é *indexado pelo código*: se um
intent novo aparece, ele aparece aqui, com a descrição que o autor lhe
deu, sem ninguém lembrar de o acrescentar.

O QUE A CONVERSA DO UTILIZADOR PROVOU

Ele perguntou "como se cadastrar" e recebeu o wizard de máquinas. Não
porque faltasse a capacidade — `cadastrar_funcionario` estava escrito, com
descrição e exemplos, e o handler funcionava. Faltava a IA poder VER o que
existia. Esta tool é essa capacidade.

A segunda coisa que a conversa provou: a distinção pessoa/máquina é o
ponto onde a IA erra, porque `nome` é campo das duas e `cargo`/`tipo` não
se confundem sozinhos. Por isso há um índice dedicado a essa distinção.
"""

from __future__ import annotations

import re
from typing import Any

from app.ia import registro as _reg
from app.ia.texto import RE_INSTRUCAO as RE_INSTRUCAO_CENTRAL

#: Palavras que dizem "isto é sobre PESSOAS" e "isto é sobre COISAS".
#: Não é clasificación de linguagem — é a diferença que o registo tem de
#: tornar explícita, porque `nome` é campo das duas e é onde a IA se
#: engana. "Vaqueiro" ao pedido de "tipo" é a prova.
_PESSOAS = {
    "cargo",
    "funcionario",
    "salario",
    "data_admissao",
}
_COISAS = {
    "tipo",
    "maquina",
    "placa",
    "chassi",
    "ano_fabricacao",
}

#: O DOMÍNIO de cada intent, lido do prefixo das flags (a parte antes do ponto).
#:
#: POR QUE ISTO EXISTE, E POR QUE NÃO É SÓ MAIS UMA LISTA
#: ------------------------------------------------------
#: A primeira versão desta função classificava por `required_fields` e por
#: menções no texto. Resultado medido: **3 de 80 intents classificados**, com
#: `neutro: 77`. O índice pessoa/maquina — que este módulo foi construído
#: para tornar fiável, por causa do incidente do "vaqueiro" — estava
#: tecnicamente presente e praticamente inútil. Um índice com uma entrada é
#: pior do que nenhum: dá a impressão de estar resolvido.
#:
#: A causa não era o texto: era que `required_fields` só existe em 9 intents
#: de 80. A informação que existe em **todos** já estava escrita — nas flags.
#: `registro.por_flag()` devolve o vocabulário do domínio inteiro, e ele foi
#: escrito por pessoas, não deduzido. Usá-lo é ler dado, não adivinhar.
#:
#: `neutro` é uma CATEGORIA, não uma falha. Uma consulta de clima, de contas
#: ou do Kanban não é sobre uma pessoa nem sobre uma coisa — é sobre a
#: fazenda. Forçá-la a um dos dois lados só baralharia o índice.
_PESSOAS_DOMINIO = {
    "funcionario",
}
#: Deliberadamente estreito, e é uma correcção.
#:
#: A primeira versão desta lista punha aqui `sanidade`, `pecuaria`, `apiario`
#: e `mip` — tudo o que é sobre gente viva. Com isso, `alerta_pragas` passou a
#: "pessoa", e `app/ia/tests_capacidades_ia.py` foi ao vermelho:
#:
#:     test_nada_de_neutro_e_classificado_como_pessoa
#:     → toda a gente em `pessoas` tem de ter "funcion" no nome
#:
#: E o teste está certo. "pessoa" neste índice não significa "ser vivo" nem
#: "quem a fazenda mantém": significa **registo de pessoal**, e existe para
#: responder a uma pergunta estreita — `cadastrar_funcionario` pede `cargo`,
#: `cadastrar_maquina` pede `tipo`, e `nome` serve para as duas. Animais, MIP
#: e sanidade são de outro índice, e metê-los aqui ENSINA O ERRO: quando o
#: modelo vê `alertar_pragas` ao lado de `cadastrar_funcionario` na mesma
#: lista de "pessoa", aprende que pessoa é um categoria larga, e volta a
#: errar no cadastro.
#:
#: A lição está escrita no invariant do teste. O lado "coisa" pode ser largo
#: porque "coisa" não carrega essa ambiguidade.
_COISAS_DOMINIO = {
    "maquinario",
    "campo",
    "estoque",
    "insumo",
    "safra",
    "iot",
    "aquatico",
    "logistica",
    "criador_livre",
}

#: O prefixo de "INSTRUÇÃO IA:" que os autores escrevem para o MODELO.
#:
#: Este é o MESMO regex que `app/ia/sandbox.py` usa para limpar o prompt de
#: confirmação. A primeira versão tinha uma CÓPIA daqui, com `startswith` em
#: vez de regex — e por isso `feedback` ("INSTRUÇÃO IA (ML):") vazava. Ter o
#: padrão em dois sítios é ter duas fontes: corrige-se uma e a outra fica
#: errada. A fonte única é `app/ia/texto.py`.
_RE_INSTRUCAO = RE_INSTRUCAO_CENTRAL


def _dominio(spec: dict[str, Any]) -> set[str]:
    """Os domínios que as flags deste intent declaram.

    `registro.por_flag()` é a fonte: as flags foram escritas para dizer o
    domínio, e escrevê-las foi mais barato e mais fiável do que as inferir do
    texto. Um intent com flags de dois domínios (ex.: `['fin.read',
    'campo.read']`) devolve os dois — e `_classifica` resolve.
    """
    dominios = set()
    for flag in spec.get("flags") or []:
        nome = str(flag).split(".", 1)[0].strip().lower()
        if nome:
            dominios.add(nome)
    return dominios


def _classifica(nome: str, spec: dict[str, Any]) -> str:
    """`pessoa`, `coisa`, `ambos` ou `neutro` — pelo que o intent PEDE.

    A primeira versão dava falsos positivos, e eram do pior tipo: `ajuda`,
    `listar_tarefas` e `gerar_lcdpr` saíam como "de pessoa" só porque os
    respetivos exemplos diziam "equipa" ou "você". Uma lista onde
    `cadastrar_funcionario` aparece ao lado de `gerar_lcdpr`, ambos marcados
    "pessoa", ensina a IA exactamente o erro que se quer evitar.

    Por isso são DUAS condições, e ambas têm de ser verdadeiras: o intent
    tem de pedir campos de pessoa ou de coisa — ou chamar-se um cadastro —
    E a conversa tem de ser sobre a pessoa ou sobre a coisa. Uma menção
    avulsa não classifica nada.

    HÁ DUAS FONTES, e nenhuma basta sozinha:

      1. CAMPOS PEDIDOS (`required_fields`) — o sinal mais forte, porque um
         campo `cargo` é um campo de pessoa e `tipo` é um campo de coisa.
         Só 9 de 80 intents o têm, portanto nunca chega para cobrir.

      2. DOMÍNIO DAS FLAGS — o sinal que cobre os outros 71. Um intent com
         `funcionario.*` ou `sanidade.*` é sobre gente; com `maquinario.*` ou
         `campo.*`, sobre coisas. Flags sem domínio conhecido
         (`clima`, `fin`, `tarefa`, `proativo`, `palco`, `ml`, `simulacao`,
         `chamado`) ficam NEUTRAS — é o que mantém `listar_tarefas` e
         `gerar_lcdpr` fora de "pessoa", que foi o erro que o docstring
         documenta.

    `campo` e `pecuaria` são de leitura e de escrita com a mesma forma: o que
    decide é o nome, não o verbo. Por isso `cadastrar_talhao` (campo) é coisa
    e `concluir_tarefa` (tarefa) é neutro, apesar de ambos escreverem.
    """
    campos = set(spec.get("required_fields", []) or [])
    texto = " ".join(
        [spec.get("descricao") or ""] + [str(e) for e in (spec.get("exemplos") or [])]
    ).lower()

    exige_pessoa = bool(campos & _PESSOAS)
    exige_coisa = bool(campos & _COISAS)

    # Fonte 2: o domínio, das flags.
    dominios = _dominio(spec)
    dominio_pessoa = bool(dominios & _PESSOAS_DOMINIO)
    dominio_coisa = bool(dominios & _COISAS_DOMINIO)

    # Fonte 3: o NOME, para "pessoa" continuar a significar exactamente o que
    # o teste `test_nada_de_neutro_e_classificado_como_pessoa` exige — todo o
    # que entra em `pessoas` tem "funcion" no nome. `listar_funcionarios` usa
    # a flag `equipe.read` e não `funcionario.*`, portanto sem este sinal
    # saía de "pessoa" só por o nome, e o índice perdia o par leer/registar
    # que é o seu uso principal.
    nome_pessoa = "funcion" in nome.lower()

    fala_pessoa = any(
        p in texto
        for p in (
            "funcion",
            "pessoa",
            "equipa",
            "equipe",
            "vaqueir",
            "tratorista",
            "diarista",
            "mecânico",
            "mecanico",
        )
    )
    fala_coisa = any(
        c in texto
        for c in (
            "máquina",
            "maquina",
            "trator",
            "colheitadeira",
            "caminhão",
            "caminhao",
            "equipamento",
            "frota",
        )
    )

    # Um cadastro que não tem campo próprio é ambíguo por natureza: o campo
    # vem na conversa. Classifica pelo nome e pela fala, e só por essa.
    eh_cadastro = "cadastrar" in nome or "criar" in nome

    tem_pessoa = (
        exige_pessoa
        or dominio_pessoa
        or nome_pessoa
        or (eh_cadastro and fala_pessoa and not fala_coisa)
    )
    tem_coisa = (
        exige_coisa or dominio_coisa or (eh_cadastro and fala_coisa and not fala_pessoa)
    )

    if tem_pessoa and tem_coisa:
        return "ambos"
    if tem_pessoa:
        return "pessoa"
    if tem_coisa:
        return "coisa"
    return "neutro"


def catalogo_de_capacidades(
    *,
    categoria: str | None = None,
    consulta: str | None = None,
    apenas_leitura: bool = False,
    user=None,
    filtrar_culturas: bool = True,
) -> dict[str, Any]:
    """O que a AmplIA sabe fazer, com o que pede e o que arrisca.

    Três filtros, todos opcionais, e os três combináveis — porque a
    pergunta real é "como é que eu pesco um trator?" e isso é consulta +
    só-leitura, não uma categoria.

    O `por_que` de cada capacidade é a `descricao` do intent, cortada no
    primeiro `INSTRUÇÃO IA:` porque essa é a parte que o autor escreveu
    para o modelo, e o resto é a parte útil.

    `user` e `filtrar_culturas` cortam o que não serve a este produtor: quem
    escolheu Soja não deve ver "liga o aerador quando o mormaço da tilápia
    passar de 30 °C". Não é uma pergunta a mais — é a IA a sugerir um
    aerador a uma fazenda sem tanque.

    É o MESMO filtro dos widgets (`app/ia/paginas.py::referencia_widgets`) e
    a mesma tabela de marcas (`app.cultures.filtro._MARCAS`). Duas respostas
    diferentes para "o que serve a este produtor" é o caminho para a IA
    oferecer uma coisa e o painel mostrar outra.

    `filtrar_culturas=False` devolve o registo inteiro: é o que o comando
    `amplia_mcp` usa para DOCUMENTAR o que existe, e o que os testes do
    catálogo usam para contar capacidades sem producer nenhum.
    """
    from app.cultures.filtro import grupos_da_marca, grupos_escolhidos, widget_aplicavel
    from app.ia.sandbox import somente_leitura

    consulta = (consulta or "").strip().lower()
    grupos_usuario = grupos_escolhidos(user) if filtrar_culturas else None
    saida: list[dict[str, Any]] = []

    for nome in sorted(_reg.REGISTO):
        spec = _reg.REGISTO[nome] or {}
        leitura = somente_leitura(spec)
        if apenas_leitura and not leitura:
            continue

        # `aplica_a` ausente = capacidade de fazenda (registar funcionário,
        # gerar LCDPR, consultar contas). Presente = só para quem produz
        # aquele. Ver a nota sobre marcas em `app/ia/intents4.py`.
        if not widget_aplicavel(grupos_usuario, grupos_da_marca(spec.get("aplica_a"))):
            continue

        categoria_intent = _classifica(nome, spec)
        if categoria and categoria_intent != categoria:
            continue

        descricao = (spec.get("descricao") or "").strip()
        # A descrição do autor vem como "INSTRUÇÃO IA: use para ...". O que
        # o modelo precisa é do que vem a seguir — o resto é instrução de
        # uso, não descrição.
        #
        # O regex e não `startswith`, porque `feedback` começa com
        # "INSTRUÇÃO IA (ML):" — parênteses antes dos dois-pontes. Ver
        # `_RE_INSTRUCAO`.
        m = _RE_INSTRUCAO.match(descricao)
        if m:
            descricao = descricao[m.end() :].strip()
        descricao = descricao.split("\n\n")[0].strip()

        entrada = {
            "capacidade": nome,
            "o_que_faz": descricao or f"Intent `{nome}`.",
            "pede": list(spec.get("required_fields", []) or []),
            "so_leitura": leitura,
            "categoria": categoria_intent,
            "confirma": bool(spec.get("requires_confirmation")),
        }

        if consulta:
            alvo = " ".join(
                [nome, entrada["o_que_faz"], " ".join(entrada["pede"])]
                + [str(e) for e in (spec.get("exemplos") or [])]
            ).lower()
            if consulta not in alvo:
                continue

        exemplos = [str(e) for e in (spec.get("exemplos") or [])][:4]
        if exemplos:
            entrada["como_perguntar"] = exemplos
        saida.append(entrada)

    por_cat: dict[str, int] = {}
    for e in saida:
        por_cat[e["categoria"]] = por_cat.get(e["categoria"], 0) + 1

    return {
        "total": len(saida),
        "todas_as_capacidades": len(_reg.REGISTO),
        "filtro": {
            "categoria": categoria,
            "consulta": consulta or None,
            "apenas_leitura": apenas_leitura,
            "culturas": sorted(grupos_usuario) if grupos_usuario is not None else None,
        },
        "por_categoria": por_cat,
        "categorias": {
            "pessoa": "regista e consulta PESSOAS — funcionário, vaqueiro, tratorista",
            "coisa": "regista e consulta COISAS — trator, colheitadeira, talhão",
            "ambos": "lida ou escreve as duas coisas",
            "neutro": "consulta, cálculo ou ação sobre a fazenda",
        },
        "capacidades": saida,
    }


def indice_pessoa_maquina() -> dict[str, Any]:
    """A distinção que a IA erra, isolada e nomeada.

    "Vaqueiro" ao pedido de "tipo" foi o que aconteceu. `nome` é campo das
    duas coisas, e o campo a seguir é que diz o que se está a registar.
    """
    pessoas, coisas, ambos = [], [], []
    for nome in sorted(_reg.REGISTO):
        spec = _reg.REGISTO[nome] or {}
        c = _classifica(nome, spec)
        if c == "pessoa":
            pessoas.append(
                {"capacidade": nome, "pede": spec.get("required_fields") or []}
            )
        elif c == "coisa":
            coisas.append(
                {"capacidade": nome, "pede": spec.get("required_fields") or []}
            )
        elif c == "ambos":
            ambos.append(
                {"capacidade": nome, "pede": spec.get("required_fields") or []}
            )
    return {
        "regra": (
            "Se a pessoa quer registar UMA PESSOA, o campo é `cargo` "
            "(vaqueiro, tratorista, diarista). Se quer registar UMA COISA, "
            "o campo é `tipo` (trator, colheitadeira, caminhão). `nome` é "
            "comum aos dois — por isso não serve para distinguir, e é a "
            "origem do erro: perguntar `tipo` a alguém que disse 'vaqueiro' "
            "leva ao wizard de registar um camião."
        ),
        "pessoas": pessoas,
        "coisas": coisas,
        "ambos": ambos,
    }


def indice_por_campo() -> dict[str, list[str]]:
    """`{campo: [capacidades que o pedem]}` — para a IA saber o que falta.

    Quando ela está a meio de um cadastro e não sabe o que falta, olha
    para o campo que já tem e descobre o resto. Isto é o inverso da
    pergunta, e é a que resolve a conversa presa.
    """
    saida: dict[str, list[str]] = {}
    for nome, spec in _reg.REGISTO.items():
        for campo in spec.get("required_fields", []) or []:
            saida.setdefault(campo, []).append(nome)
    for nomes in saida.values():
        nomes.sort()
    return dict(sorted(saida.items()))


def resumo_categorias() -> str:
    """Uma frase por categoria, para a IA poder responder 'o que você faz?'."""
    cat = catalogo_de_capacidades()
    linhas = [
        f"A AmplIA tem {cat['total']} capacidades em {len(cat['por_categoria'])} categorias."
    ]
    legendas = cat["categorias"]
    for chave, n in sorted(cat["por_categoria"].items(), key=lambda kv: -kv[1]):
        linhas.append(f"- {chave} ({n}): {legendas.get(chave, '')}")
    return "\n".join(linhas)
