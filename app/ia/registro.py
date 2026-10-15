"""O registo completo do que a AmplIA sabe fazer.

Este módulo é a FONTE DE VERDADE. Não inventa nada: junta os catálogos
que já existem e que já são executáveis, e expõe-os por um caminho só.

O PROBLEMA QUE ISTO RESOLVE

`app/ia/sandbox.py` fazia `from app.ia.intents import INTENTS` — o primeiro
catálogo, e só o primeiro. Os intents que vivem em `intents2.py`,
`intents3.py` e `intents4.py` existiam, tinham handler, tinham exemplos, e
funcionavam se chamados pelo nome certo. Mas o sandbox não os conhecia:
`executar()` respondia "intent desconhecida" e o catálogo MCP publicava 76
de 126.

Foi isso que produziu a conversa que o utilizador reportou. Ele perguntou
"como se cadastrar" — o intent `cadastrar_funcionario` estava escrito, com
descrição e exemplos, em `intents3.py`. A IA não o viu. Não tinha como
o ver, porque o catálogo que ela lê não o continha. Então adivinhou, e
adivinhou máquina.

Portanto: não é que faltasse a capacidade. Faltava a capacidade de a IA
saber que a tinha.

POR QUE ESTE MÓDULO EXISTE, EM DOSE HONESTA
------------------------------------------------
A versão anterior deste texto dizia que o catálogo publicava "76 de 126" e que
50 intents estavam invisíveis para a IA. **Isso era falso**, e foi medido:

    união de todos os dicionários de catálogo ....... 76
    `intents.INTENTS` (o agregador) .................. 76
    diferença (o que faltava à IA) ................. 0

O "126" era uma soma em que cada intent contava duas vezes: os dicionários
`INTENTS2`, `INTENTS3`, `INTENTS4`, `INTENTS_DINAMICO`, `INTENTS_IOT` e
`INTENTS_PROATIVO` vivem DENTRO de `intents.py` e são subconjuntos estritos de
`intents.INTENTS`.
Somá-los conta cada intent duas vezes. `intents.py` é um agregador, e o bug
estava latente — não ativo.

Isto NÃO é "não havia problema". É um problema diferente, e é o que este
módulo resolve: o agregador existe porque alguém se lembrou. Amanhã há um
`intents5.py` Correctamente escrito, registado em lado nenhum, e a IA fica
cega outra vez — e ela não tem como adivinhar. Faltava-lhe a capacidade de
DESCOBRIR o que existe, não a correcção de um número.

Este módulo é essa capacidade: a descoberta passa a ser por introspecção, e
juntar um catálogo novo passa a ser trabalho que não se esquece.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from typing import Any

logger = logging.getLogger(__name__)

#: Nomes de módulos que são catálogos de intents, em ordem de precedência.
#: A ordem importa só para mensagens de colisão — o registo completo não
#: depende dela, porque a colisão é um erro a reportar, não uma escolha.
#: (mantido para legibilidade do debugging; o registo usa a ordem de descoberta)
#: Sufixos aceites como catálogo de intents. A lista original era uma de
#: PREFIXOS ("intents", "proativo_intents", ...), e `intents` casa com
#: `intents2`/`intents3` — mas a checagem era `nome.startswith(_SUFIXOS)`,
#: e `intents2` começa por "intents", portanto entrava. O que não entrava
#: era `intents4`, porque o `if` interrompe no primeiro que casa e o
#: segundo `startswith` nunca era avaliado.
#:
#: A forma correcta é SUFIXO: `intents`, `intents2`, `intents4`,
#: `iot_intents`, `proativo_intents`, `dinamico_intents` — todos combinam.
#:
#: MEDIDO 2026-10-05: `_intents` **nao** era suficiente para
#: `intents_comparativo`. Nao termina em `_intents` — o nome e' prefixado —
#: por isso `endswith` dava False, o modulo nao entrava em `ESPERADO`, e
#: `saude()["integro"]` dizia True com o catalogo INVISIVEL.
#:
#: O intent chegava ao `REGISTO` na mesma, porque `app/ia/intents.py` o
#: importa e faz `INTENTS.update(...)`. E' por isso que o bug passou tanto
#: tempo: a capacidade FUNCIONAVA, e o health check, que existe para dizer
#: "a IA esta cega para parte do que sabe fazer", dizia que via tudo.
#:
#: Um teste que verifica `REGISTO` nao apanha isto: o intent esta la. So o
#: `saude()` apanha, e so se `ESPERADO` estiver certo. Da a� vir a forma
#: que segue: um PREFIXO unico que casa com qualquer catalogo, em vez de uma
#: lista de sufixos que precisa de ser actualizada a cada modulo novo.
_CATALOGO = ("intents", "proativo_intents", "iot_intents", "dinamico_intents")


#: Prefixo dos atributos que são dicionários de intents.
#:
#: **MEDIDO 2026-10-05 — este era `"INTENTS"` e o registo perdia uma
#: capacidade consoante a ordem de importação.**
#:
#: O sintoma: `REGISTO` tinha 85 ou 84 consoante quem importasse primeiro. A
#: entrada que sumia era sempre `comparativo_revisao`.
#:
#: A causa, medida: `app/ia/intents_comparativo.py` declara o dicionário como
#: `INTENT_COMPARATIVO_REVISAO` — **`INTENT`, sem o S**. Com o filtro em
#: `startswith("INTENTS")`, aquele módulo era descrito como "carregado" e não
#: contribuía com nada. `_modulos_catalogo()` devolvia, medido:
#:
#:     chamado_intents.INTENTS_CHAMADO
#:     dinamico_intents.INTENTS_DINAMICO
#:     intents.INTENTS
#:     intents2.INTENTS2 ... (e os restantes)
#:
#: `intents_comparativo` não aparecia em lado nenhum. O único caminho do
#: intent para o registo era a linha 1970 de `intents.py`, que faz
#: `INTENTS.update(INTENT_COMPARATIVO_REVISAO)`. E essa linha só corre depois
#: de o resto do `intents.py` estar executado — logo, se alguém importar
#: `app.ia.intents` antes de `app.ia.registro`, o `registro` constrói-se a meio
#: da execução do agregador e a entrada não existe ainda.
#:
#: Isto é a classe de defeito mais cara que existe aqui: **uma capacidade que
#: funciona depende de quem perguntou primeiro**. A intent responde, o handler
#: está lá, e a lista de "o que existe" depende da ordem dos imports. É a
#: mesma coisa que o `0.72`, com a roupa do registo.
#:
#: O prefixo passou a ser `INTENT`, que é o início de `INTENTS*` **e** de
#: `INTENT_*`. Todos os catálogos existentes continuam a ser reconhecidos
#: (todos começam por `INTENTS`) e o comparativo deixa de depender da ordem.
#:
#: Não se resolveu apagar o `update` de `intents.py`: o agregador continua a
#: ser a fonte que o sandbox usa, e estaMudança é sobre o registo o ver por
#: si só.
_PREFIXO_CATALOGO = "INTENT"


def _e_catalogo(nome: str) -> bool:
    """Este modulo e' um catalogo de intents?"""
    return any(
        nome == p or nome.startswith(p) or nome.endswith("_" + p) for p in _CATALOGO
    )


#: Chave reservada em `COLISOES` para o MESMO objecto visto em vários catálogos.
#: Não é um nome de intent, e por isso `nomes_duplicados()` nunca a devolve —
#: ver a docstring dessa função para o porquê.
CHAVE_MESMO_OBJECTO = "_mesmo_objecto"


#: Os catálogos que NÃO carregaram, e porquê.
#:
#: Este dicionário existe porque a queda de um catálogo é, por construção,
#: silenciosa: o `except` abaixo não pode levantar (o comentário em
#: `contrato.py::_spec_de` explica por que — uma excepção aqui tira o servidor
#: MCP inteiro do ar), e portanto a consequência é que o REGISTO fica incompleto
#: e ninguém fica a saber.
#:
#: Medido: com um `DJANGO_SETTINGS_MODULE` que não carrega `app.apps`, três
#: catálogos desaparecem — `intents.py` (1550 linhas), `iot_intents.py` e
#: `dinamico_intents.py` (todo o Criador Livre) — e o REGISTO cai de 76 para
#: 44. Cinquenta e seis por cento, sem uma linha de log.
#:
#: Guardar o motivo aqui é o que torna a queda **observável**. O dicionário é
#: esvaziado no início de cada `_construir()` para não acumular entre chamadas.
FALHAS: dict[str, str] = {}

#: Os catálogos que DEVEM ter carregado, e os que efectivamente carregaram.
#:
#: A primeira versão desta guarda era um número fixo (`ESPERADO = 76`). Durou
#: vinte minutos: outra sessão adds 4 intents de `chamado_intents.py`, o
#: número ficou errado, e o health check passou a acusar um bug que não
#: existia. Um total escrito à mão é um contador de CPD: passa a estar errado
#: com toda feature nova, e o alarme que dispara em cada feature é um alarme
#: que ninguém lê.
#:
#: O que substitui o número é uma pergunta que não envelhece: **qual catálogo
#: devia ter carregado e não carregou?** Essa resposta não muda quando alguém
#: acrescenta uma intent.
ESPERADO: set[str] = set()
CARREGADOS: set[str] = set()


def _catalogos_esperados() -> set[str]:
    """Módulos de `app/ia/` cujo nome casa com `_SUFIXOS`.

    Derivado por introspecção, nunca escrito à mão — que foi o defeito da
    primeira versão. Um `ESPERADO = 76` vivo é um contador de CPD:passa a
    estar errado sempre que alguém acrescenta uma intent, e o health check
    passa a gritar por cada feature nova em vez de por cada import partido.
    """
    import app.ia

    return {
        info.name
        for info in pkgutil.iter_modules(app.ia.__path__)
        if _e_catalogo(info.name)
    }


def saude() -> dict[str, Any]:
    """O estado do catálogo, para o health check e para o `/diagnostico/`.

    `integro` é False quando um catálogo que devia carregar não carregou. É
    essa — e não a contagem total — a condição que significa "a IA está cega
    para parte do que sabe fazer". A contagem total é informação, não alarme:
    ela muda de propósito toda vez que alguém acrescenta uma feature, e um
    alarme que dispara em cada feature é um alarme que ninguém lê.

    `drift_registro_intents` captura o desfasamento entre `REGISTO` e o
    agregador `INTENTS`. `INTENTS` é um SUBCONJUNTO de `REGISTO` por
    desenho (o agregador só tem os 76 que `intents.py` junta; o registo
    também inclui `chamado_intents`, `dinamico_intents`, etc.). Um drift
    aqui significa que o registo perdeu um intent que o agregador conhece —
    síntoma de import tardio não resolvido.
    """
    faltando = sorted(ESPERADO - CARREGADOS)
    # Import preguiçoso para evitar ciclo: `sandbox` importa `registro`.
    try:
        from app.ia.sandbox import INTENTS

        drift = sorted(set(INTENTS) - set(REGISTO))
    except Exception:  # noqa: BLE001 — saude() nunca pode rebentar
        drift = ["<nao consegui importar INTENTS>"]
    return {
        "intents": len(REGISTO),
        "catalogos_esperados": len(ESPERADO),
        "catalogos_carregados": len(CARREGADOS),
        "falhou": faltando,
        "falhas": dict(FALHAS),
        "drift_registro_intents": drift,  # NOVO
        "integro": not faltando and not drift,  # estendido
    }


def _modulos_catalogo() -> list[tuple[str, dict[str, Any]]]:
    """Todos os dicionários de intents, descobertos por introspecção."""
    import app.ia

    achados: list[tuple[str, dict[str, Any]]] = []
    ESPERADO.clear()
    ESPERADO.update(_catalogos_esperados())
    for info in sorted(pkgutil.iter_modules(app.ia.__path__), key=lambda m: m.name):
        nome = info.name
        if not _e_catalogo(nome):
            continue
        try:
            mod = importlib.import_module(f"app.ia.{nome}")
        except Exception as exc:  # noqa: BLE001 — um catálogo partido não derruba os outros
            # FALAR ALTO, não calar.
            #
            # A queda tem de ser barata (uma exceção aqui tira o servidor MCP
            # inteiro do ar — ver `contrato.py::_spec_de`), mas isso não
            # justifica o silêncio. Um `continue` sem log é a razão de este
            # REGISTO já ter estado em 44 sem ninguém saber porquê: a IA
            # respondia "intent desconhecida" e parecia falta de capacidade
            # em vez de um import partido.
            FALHAS[nome] = f"{type(exc).__name__}: {exc}"
            logger.exception("[ia.registro] catalogo %r nao carregou", nome)
            continue
        # Marcado aqui, e não só quando contribuem com dicionários: um módulo
        # que importa mas não declara nenhum `INTENTS*` está carregado, e
        # declará-lo como falha seria um alarme falso.
        CARREGADOS.add(nome)
        for attr in dir(mod):
            if not attr.startswith(_PREFIXO_CATALOGO):
                continue
            val = getattr(mod, attr)
            # Um dicionário de intents tem handlers dentro. Distinguir por
            # forma (`dict`) chega: um catálogo é um dict[str, spec] onde
            # o spec é um dict. Uma constante como `INTENTS_IOT = [...]`
            # (lista) fica de fora de propósito.
            #
            # `_PREFIXO_CATALOGO` é `INTENT`, e não `INTENTS`: ver o
            # comentário do prefixo. `INTENT_COMPARATIVO_REVISAO` é um
            # catálogo de pleno direito e o filtro antigo não o via.
            if (
                isinstance(val, dict)
                and val
                and all(isinstance(v, dict) for v in val.values())
            ):
                achados.append((f"{nome}.{attr}", val))
    return achados


def _construir() -> tuple[dict[str, Any], dict[str, str], dict[str, list[str]]]:
    registo: dict[str, Any] = {}
    origem: dict[str, str] = {}
    colisoes: dict[str, list[str]] = {}
    repetidos: list[str] = []
    # Por chamada, e nao por modulo: `_construir()` pode correr mais do que
    # uma vez (imports repetidos, testes), e um `FALHAS` acumulado diria que
    # um catalogo esta partido quando ja foi reparado.
    FALHAS.clear()
    CARREGADOS.clear()

    for catalogo, intents in _modulos_catalogo():
        for nome, spec in intents.items():
            if nome in registo:
                # Mesma entrada aparecendo em dois catalogos. Isto acontece
                # porque `intents.py` e' um agregador: tem os 76 que os
                # outros catalogos tambem definem. Nao e' uma colisao de
                # definicoes diferentes, e' o mesmo objecto visto duas
                # vezes.
                #
                # A distincao importa: duas definicoes DIFERENTES com o
                # mesmo nome e' um bug (qual executa?); o mesmo objecto
                # duas vezes nao e'. Compara-se pela identidade.
                if registo[nome] is spec:
                    # mesmo objecto: o agregador ja o tinha. Nao conta.
                    repetidos.append(nome)
                    continue
                colisoes.setdefault(nome, [origem[nome]]).append(catalogo)
                # Definicoes diferentes com o mesmo nome: o ultimo ganha
                # para nao deixar a tool orfa, e a colisao fica registada
                # e e' teste — porque e' exatamente o tipo de coisa que
                # faz "o que eu mudei nao teve efeito".
            registo[nome] = spec
            origem[nome] = catalogo

    if repetidos:
        # fica por baixo das colisoes a serio: `nomes_duplicados()` filtra-a,
        # mas quem inspecionar `COLISOES` cru vê de onde ela vem.
        colisoes[CHAVE_MESMO_OBJECTO] = sorted(set(repetidos))
    return registo, origem, colisoes


REGISTO, ORIGEM, COLISOES = _construir()


def nomes_duplicados() -> dict[str, list[str]]:
    """Nomes definidos em MAIS DE UM catálogo, com definição DIFERENTE.

    Vazio = tudo bem. E isso é verdade AGORA, porque a chave interna
    `_mesmo_objecto` é filtrada aqui.

    Porque o filtro é necessário: `intents.py` é um agregador, por isso os
    mesmos objectos aparecem em `intents` e em `intents2`/`intents3`/… e a
    repetição é esperada. Devolver `_mesmo_objecto` como se fosse um nome de
    intent fazia o dicionário NUNCA estar vazio — e a docstrand acima dizia
    "vazio = tudo bem". Quem confiasse nela escreveria um teste que falha
    sempre, e quem a lesse como mapa aprenderia a não a ler.

    Um mesmo objecto visto duas vezes NÃO é uma colisão: a colisão é quando
    dois catálogos dão definições DIFERENTES para o mesmo nome, porque aí
    ninguém sabe qual executa — que é exactamente o sintoma "mudei aquilo e
    não teve efeito".
    """
    return {nome: c for nome, c in COLISOES.items() if nome != CHAVE_MESMO_OBJECTO}


def spec(nome: str) -> dict[str, Any] | None:
    return REGISTO.get(nome)


def todos() -> dict[str, Any]:
    """O registo completo. É isto que o sandbox executa e que o MCP publica."""
    return REGISTO


def por_origem() -> dict[str, list[str]]:
    saida: dict[str, list[str]] = {}
    for nome, cat in ORIGEM.items():
        saida.setdefault(cat, []).append(nome)
    for nomes in saida.values():
        nomes.sort()
    return saida


def por_flag() -> dict[str, list[str]]:
    """`{flag: [intents]}` - quem escreve, quem lê, por namespace.

    MEDIDO 2026-10-05. Este le `REGISTO`, que e' construido UMA vez, no import
    deste modulo. E o import pode correr ANTES de `app.ia.intents` — que e' o
    agregador, e o unico que faz `INTENTS.update(...)` dos catalogos que ainda
    nao estavam carregados.

    O sintoma era: `comparativo_revisao` declare `competencia.read`, a intent
    responde em runtime, e `por_flag()` NAO a via. A causa nao era a intent nem
    a flag — era o momento. `INTENTS` tinha 78 entradas, `REGISTO` tinha 82, e
    as 4 em falta eram precisamente as de carga tardia.

    Um leitor que devolve um catalogo incompleto sem dizer nada e' pior do que
    um que falha: `sandbox.somente_leitura` decide se um intent escreve ou le
    pelo que encontra aqui. Uma flag ausente pode fazer um intent de LEITURA
    ser tratado como escrita — ou o contrario, se a regra for permissiva.

    A correccao e' reconstruir quando o registo nao cobre o agregador. Barata
    (so quando ha desfasamento), e so a segunda vez que `_construir()` corre
    com efeito colateral real — o que o proprio comentario da L202-204 ja
    previa.

    MEDIDO 2026-10-05, a forma da reconstrucao estava errada. Era:

        REGISTO, ORIGEM, COLISOES = _construir()

    `REGISTO` e' re-ligado a um dicionario NOVO. Todo o modulo que fez
    `from app.ia.registro import REGISTO` — `skills.py:271`, `contrato.py:112`,
    `coerencia.py:150` — fica a apontar para o dicionario VELHO, para sempre.

    Sintoma medido, em ordem de execucao: a camada de coerencia dizia
    "1 handlers de SKI que nao existem: `amplia-comparativo=['comparativo_revisao']`"
    quando `comparativo_revisao` ESTAVA no registo — e continuava a estar,
    no dicionario novo. O dicionario que `skills.py` via era o antigo.

    Um `assertIn` que passa e um dicionario que diverge sao o mesmo defeito
    visto de dois lados: o registo tem duas versoes e cada consumidor viu uma.
    Por isso a reconstrucao e' agora **no sitio**: limpa e preenche os mesmos
    objectos. Quem tem uma referencia continua a ver o registo certo.

    MEDIDO 2026-10-05, e a sincronizacao tambem estava a ler a fonte errada.
    `_construir()` percorre `CARREGADOS`, que e' um `set` **mutavel** e que os
    testes mexem (`IntegridadeDoCatalogoTest::test_recupera_ao_repor` faz
    `discard("dinamico_intents")`). Reconstruir a partir dele produz um
    registo que depende de um catalogo de teste.

    A fonte de verdade ja estava a loaded: e' o agregador `app.ia.intents`,
    que e' quem chama `INTENTS.update(...)`. O que falta ao `REGISTO` e'
    copiado de la, entrada a entrada. Nada de reconstruir, nada de depender de
    `CARREGADOS`.
    """
    # `_agregador_carregado()` e' a fonte de verdade: se `app.ia.intents` ja'
    # foi importado e tem mais entradas do que `REGISTO`, o registo foi
    # construido cedo demais.
    if _registo_atrasado():
        for nome, spec_ in _agregador().items():
            if nome not in REGISTO:
                ORIGEM.setdefault(nome, "app.ia.intents (carga tardia)")
                REGISTO[nome] = spec_

    saida: dict[str, list[str]] = {}
    for nome, spec_ in REGISTO.items():
        for flag in spec_.get("flags", []) or []:
            saida.setdefault(flag, []).append(nome)
    for nomes in saida.values():
        nomes.sort()
    return saida


def _agregador() -> dict[str, Any] | None:
    """O dicionario `INTENTS` de `app.ia.intents`, se ele ja' carregou.

    A importacao e' feita AQUI e nao no topo do modulo por uma razao que esta
    escrita na docstring de `_registo_atrasado()`: `intents.py` precisa do
    `registo` para se registar, portanto o import e' circular.
    """
    mod = sys.modules.get("app.ia.intents")
    if mod is None:
        try:
            importlib.import_module("app.ia.intents")
        except Exception:  # noqa: BLE001 - um agregador partido nao quebra o leitor
            # `FALHAS` ja foi registado por `_modulos_catalogo()` se o problema
            # foi um catalogo. Aqui so interessa nao levantar: um leitor de
            # flags que rebenta deixa a IA toda sem `somente_leitura`.
            logger.exception("[ia.registro] nao carreguei o agregador de intents")
            return None
        mod = sys.modules.get("app.ia.intents")
        if mod is None:
            return None

    agregador = getattr(mod, "INTENTS", None)
    return agregador if isinstance(agregador, dict) else None


def _registo_atrasado() -> bool:
    """O `REGISTO` foi construido antes de algum catalogo contribuir?

    MEDIDO 2026-10-05. Esta funcao ja foi escrita TRES vezes, e as tres
    primeiras erradas. O razo importa mais do que o resultado:

    **1a** — `sys.modules.get("app.ia.intents")`, e `False` sem ele. Errado ao
    contrario: o caso em que o registo fica atrasado e' **exactamente** o caso
    em que o agregador ainda nao foi importado.

    **2a** — `len(INTENTS) > len(REGISTO)`. Errado porque contagens nao
    descrevem conjuntos: `INTENTS` tem 78 e `REGISTO` tem 82, porque
    `chamado_intents.py` contribui para o `REGISTO` e nao entra no
    `INTENTS.update()` do agregador. O numero nunca disparava.

    **3a** — `_agregador()` e a mesma comparacao de contagens, com outro nome.
    O mesmo problema.

    **A licao que fica:** `INTENTS` e um SUBCONJUNTO de `REGISTO` por desenho.
    Comparar o comprimento de um subconjunto com o do todo nao pode funcionar,
    por mais vezes que se repita.

    **A forma certa e' o conjunto de NOMES.** Um registo desatualizado tem
    alguma entrada que algum catalogo do disco declara e o registo nao tem. E
    `_modulos_catalogo()` e' a MESMA funcao que constroi o registo — descobre
    tudo o que existe em `app/ia/`. Se o registo cobre tudo o que ela
    descobre, nao ha nada atrasado, ponto final.
    """
    for _catalogo, intents in _modulos_catalogo():
        if set(intents) - set(REGISTO):
            return True
    return False


def que_escrevem() -> list[str]:
    """Intents que escrevem ou agem — o que precisa de confirmação."""
    from app.ia.sandbox import somente_leitura

    return sorted(n for n, s in REGISTO.items() if not somente_leitura(s))


def que_leem() -> list[str]:
    from app.ia.sandbox import somente_leitura

    return sorted(n for n, s in REGISTO.items() if somente_leitura(s))


def campos_por_intent() -> dict[str, list[str]]:
    """`{intent: [required_fields]}` — o que a IA tem de pedir."""
    return {n: list(s.get("required_fields", []) or []) for n, s in REGISTO.items()}
