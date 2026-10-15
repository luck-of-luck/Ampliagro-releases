r"""
skills.py — as especialidades do AmplIA, expostas a quem fala MCP.

O QUE ESTA RESOLVE
------------------

`app/ia/skills/amplia-campo.md`, `amplia-finance.md` e `amplia-iot.md` estão
escritos desde o BUILD 16. Cada um declara, em `handlers:`, os intents que
cobre — e cada handler e' um intent real, do registo.

O problema e' que **ninguem os lia**. A unica superficie que os consumia era
`loadAmpliaSKI(t)` em `app/static/js/ia-local.js`, que e' o WebLLM na aba. Um
agente externo — Claude Desktop, Hermes, qualquer cliente MCP — recebe a lista
de tools e **nada mais**: conhece `amplia_praga_ai_foto` pelo nome, sem saber
que ela e' VRA/NDVI de 10 m sobre Sentinel-2, e sem saber que `amplia_solo_spd`
exige MO de 2% para virar 3,4%.

O resultado e' o erro que o nome do intent sugere e a especialidade nao diz:
uma tool de agronomia chamada com parametros de outra coisa, respondendo com um
erro que nao parece relacionado com o que se perguntou.

Esta e', de todas as melhorias desta camada, a mais barata: o conhecimento ja
esta escrito, em YAML simples, dentro do repositorio. O que faltava era a
porta.

ONDE ESTE MODULO LE
--------------------

De `app/ia/skills/` — e nao de `app/static/ia/skills/`. Os dois directorios
tem hoje conteudo **identico** (verificado byte a byte por
`SkillsTest::test_as_duas_pastas_estao_iguais`), e o de `static/` e' servido
por HTTP a aba. Manter os dois e' uma duplicacao a espera de divergir; o de
`app/ia/` e' a fonte, porque e' o que esta ao lado do codigo que executa os
handlers. A verificacao de igualdade e' um teste, nao uma suposicao — e se
alguem divergir, o teste manda dizer qual dos dois errou.

O QUE NAO E' DERIVADO
---------------------

O texto de cada SKI e' escrito por uma pessoa: e' a intencao, e nao se
automatiza. O que esta faz e' *indexa-lo pelo codigo* — se um handler
declarado nao existir no registo, isso e' um achado, e a funcao diz qual.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

#: Onde estao as SKIs. Relativo a este ficheiro, e nao ao CWD — um servidor MCP
#: nao tem CWD, e a licao do `servidor.py` aplica-se a toda a leitura de
#: ficheiros num processo stdio.
PASTA_SKIS = pathlib.Path(__file__).resolve().parents[1] / "ia" / "skills"

#: A pasta espelho servida por HTTP a aba. So para o teste de paridade.
PASTA_SKIS_ESTATICA = (
    pathlib.Path(__file__).resolve().parents[1] / "static" / "ia" / "skills"
)

#: O cabecalho YAML das SKIs e' deliberadamente minimalista (name, description,
#: version, triggers, handlers, performance) e nao usa `---`. Um parser de YAML
#: seria a dependencia certa e a dependencia errada para o que isto faz: ler
#: seis campos de um ficheiro que o proprio repositorio escreve. Um
#: `import yaml` aqui passava a ser uma dependencia do caminho de IA para
#: interpretar cinco linhas.
_LINHA = re.compile(r"^(?P<chave>[a-z_]+):\s*(?P<valor>.*)$")


def _desenrolar(txt: str) -> str:
    return txt.strip().strip("\"'")


def _dividir_respeitando(texto: str) -> list[str]:
    """Separa por virgula, mas so as que estao ao nivel de fora.

    Uma SKI real tem `performance: {cache: 60, flags: ["campo.read",
    "iot.read"]}`. Um `split(",")` cego parte a lista interna em duas metades e
    devolve `['[', '"', 'c', 'a', 'm', 'p', 'o'...]` — quinze letras soltas,
    cada uma tratada como um elemento. Foi o que aconteceu, e foi apanhado por
    um teste que esperava `["campo.read", "iot.read"]`.

    A contabilidade de nivel (`[`/`{` sobem, `]`/`}` descem) e' o que resolve.
    Nao ha aspas a considerar porque nenhum valor das SKIs contem virgula
    dentro de aspas — e se um dia vier, um `yaml.safe_load` resolve, e o teste
    de paridade continua a dizer a verdade.
    """
    partes: list[str] = []
    atual: list[str] = []
    nivel = 0

    for char in texto:
        if char in "[{":
            nivel += 1
        elif char in "]}":
            nivel -= 1
        if char == "," and nivel == 0:
            partes.append("".join(atual))
            atual = []
            continue
        atual.append(char)

    resto = "".join(atual)
    if resto.strip():
        partes.append(resto)
    return [p for p in (p.strip() for p in partes) if p]


def _valor(bruto: str) -> Any:
    """`["a", "b"]` -> lista · `{a: 1}` -> mapa · resto -> texto.

    O `performance` de uma SKI e' um mapa flow-style (`{cache: 60, flags: [...]}`)
    e os `triggers`/`handlers` sao listas flow-style. Um YAML a serio resolve
    isto em duas linhas; a versao honesta e' o `_dividir_respeitando` acima mais
    seis, e vale mais do que a dependencia — porque nao acrescenta um modulo
    que falha a carregar a um caminho de IA que hoje nao tem nenhum.
    """
    if bruto.startswith("[") and bruto.endswith("]"):
        return [_desenrolar(p) for p in _dividir_respeitando(bruto[1:-1])]
    if bruto.startswith("{") and bruto.endswith("}"):
        saida: dict[str, Any] = {}
        for par in _dividir_respeitando(bruto[1:-1]):
            if ":" not in par:
                continue
            chave, _, valor = par.partition(":")
            # Recursao, e nao `_desenrolar`: o valor de uma chave pode ser uma
            # lista (`flags: ["a.b", "c.d"]`) e tem de sair lista. Sem isto,
            # `performance.flags` chegava ao cliente como a STRING
            # `["a.b", "c.d"]` — legivel, e por isso perigoso: uma busca por
            # flag casa com a string e passa, e ninguem repara que e' texto.
            saida[chave.strip()] = _valor(valor.strip())
        return saida
    return _desenrolar(bruto)


def _parse(texto: str) -> dict[str, Any]:
    """Le o cabecalho de uma SKI. So os campos de topo, so antes do corpo.

    O formato real e' este, e e' mais simples do que parece:

        # AmplIA SKI - Campo (VRA NDVI, SPD, praga AI, guidance)
        name: amplia-campo
        description: Skill campo para AmplIA - VRA NDVI 10m Sentinel-2...
        version: 1.0.0
        triggers: ["VRA", "NDVI", "SPD", "praga", "guidance", "as-applied"]
        handlers: ["vra_ndvi_prescricao", "solo_spd", ...]
        performance: {cache: 60, flags: ["campo.read", "iot.read"]}
        sem_intent:
          vra_ndvi_prescricao: "VRA/NDVI de 10 m em app/services/ndvi.py..."
          praga_ai_foto: "app/services/top_globals.py..."

    Repare-se no titulo markdown na PRIMEIRA linha: e' um `#`, nao um
    `campo: valor`. Uma versao anterior deste parser fechava o cabecalho
    nesse ponto - o `name:` seguinte ficava no corpo e `nome` saia `None`.
    Foi apanhado pelo `SkillsTest`, e e' o motivo de o titulo ter tratamento
    explicito em vez de cair no `else` generico.

    `sem_intent` e' o unico campo com sub-mapas indentadas, e e' lido como tal.
    Sem tratamento, as linhas `  nome: "nota"` caem no corpo e o campo vira a
    string vazia — que e' pior do que nao existir, porque parece um campo
    declarado e nao diz nada.
    """
    cabecalho: dict[str, Any] = {}
    corpo: list[str] = []
    no_cabecalho = True
    sub_campo: str | None = None

    # `utf-8-sig` resolve quem abre o ficheiro por este modulo. Isto resolve
    # quem lhe entrega o texto ja lido. Os dois sao precisos: uma BOM que
    # sobre a primeira linha transforma o titulo markdown em texto alheio e o
    # cabecalho fecha vazio — o modo de falha silencioso que o `ler_ski`
    # documenta.
    texto = texto.lstrip("")

    for linha in texto.splitlines():
        if no_cabecalho:
            # Sub-mapa indentado: `  chave: "valor"` dentro do campo aberto.
            if sub_campo is not None:
                if linha.startswith((" ", "\t")) and linha.strip():
                    part = linha.strip()
                    if ":" in part:
                        chave, _, valor = part.partition(":")
                        cabecalho[sub_campo][chave.strip()] = _valor(valor.strip())
                    continue
                # Saiu da indentacao: o sub-mapa acabou.
                sub_campo = None

            if linha.startswith("#"):
                # Titulo markdown. Guarda-se como `_titulo`: e' informacao, e
                # o `name` de dentro e' a chave de verdade.
                cabecalho.setdefault("_titulo", linha.lstrip("# ").strip())
                continue

            m = _LINHA.match(linha)
            if m:
                chave = m.group("chave")
                valor = _valor(m.group("valor").strip())
                cabecalho[chave] = valor
                # `sem_intent:` sem valor abre um mapa; qualquer outro campo
                # fica com o valor escalar que teve.
                if chave == "sem_intent" and not valor:
                    cabecalho[chave] = {}
                    sub_campo = chave
                continue

            # Linha em branco ou texto livre: o cabecalho acabou aqui.
            no_cabecalho = False
            if linha.strip():
                corpo.append(linha)
            continue
        corpo.append(linha)

    cabecalho["_corpo"] = "\n".join(corpo).strip()
    return cabecalho


def ler_ski(caminho: pathlib.Path) -> dict[str, Any]:
    """Uma SKI, com o cabecalho lido e o corpo intacto.

    `utf-8-sig` e' nao um detalhe. Os tres ficheiros em `app/ia/skills/` tem
    BOM UTF-8, e medir isso custa o primeiro `name: None` e um catalogo vazio
    — sem erro, sem aviso, so um dicionario que devolveu nada. `utf-8-sig`
    consome a BOM se existir e nao faz mal se nao existir, que e' exactamente
    o que se quer de um leitor de um ficheiro cujo autor nao sabe que a gravou
    com BOM.
    """
    dados = _parse(caminho.read_text(encoding="utf-8-sig"))
    dados["_ficheiro"] = caminho.name
    return dados


def listar_skis() -> list[dict[str, Any]]:
    """Todas as SKIs, ordenadas por nome — a ordem e' deterministica de proposito."""
    if not PASTA_SKIS.is_dir():
        return []
    return [ler_ski(p) for p in sorted(PASTA_SKIS.glob("*.md"))]


def _int_se_numero(valor: Any) -> Any:
    """`"60"` -> `60`; `"1.0.0"` -> `"1.0.0"`; `None` -> `None`.

    O parser nao converte, porque nao sabe a que se destina cada campo: um
    `version` que vira `float` perde o `.0` e um `cache` que fica em texto
    nao pode ser comparado. Quem sabe o que o campo e' converte-o, e e' este
    `cache_s` — um TTL em segundos e' um numero, e um cliente que o receba
    como texto descobre isso quando tenta comparar.
    """
    if isinstance(valor, int):
        return valor
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return valor


def catalogo_skis() -> dict[str, Any]:
    """O indice, para `amplia://skills` e para `GET /api/amplia/skills/`.

    Devolve **quais intents cada especialidade cobre, e verifica se existem**.
    Um `handlers:` que aponta para um intent inexistente e' a forma mais barata
    de a IA aprender uma ficcao, e e' a mesma classe de defeito do
    `tool_fora_do_catalogo`: um nome que parece certo e nao existe.

    E devolve tambem `prometido_sem_botao`: a logica que a SKI nomeia e que
    **nao tem intent**. Esta e' a parte que a v1.0 escondia. Uma especialidade
    que promete seis coisas e entrega cinco e' melhor que uma que promete seis
    e nao entrega nenhuma — mas so quando diz qual das duas e'. Um agente que
    le `sem_intent` sabe o que procurar no codigo; um agente a quem se esconde
    a informacao inventa o resto.
    """
    from app.ia.registro import REGISTO

    saida: list[dict[str, Any]] = []
    total_fantasmas = 0
    total_promessas = 0

    for ski in listar_skis():
        handlers = [str(h) for h in (ski.get("handlers") or [])]
        # Um handler declarado que nao existe. Vai para o relatorio, nao para
        # `except`: engole-se um handler fantasma e a IA fica com um buraco
        # de comportamento que ninguem notou.
        fantasmas = [h for h in handlers if h not in REGISTO]
        total_fantasmas += len(fantasmas)

        sem_intent = dict(ski.get("sem_intent") or {})
        # Uma promessa que JÁ tem botao deixa de ser promessa: e' um alias, e
        # vai para `handlers` em vez de ficar numa lista que so cresce.
        ja_existe = [k for k in sem_intent if k in REGISTO]
        for k in ja_existe:
            sem_intent.pop(k, None)
        total_promessas += len(sem_intent)

        saida.append(
            {
                "nome": ski.get("name"),
                "descricao": ski.get("description"),
                "versao": ski.get("version"),
                "dispara_com": list(ski.get("triggers") or []),
                "cobre": [h for h in handlers if h in REGISTO],
                "cobre_inexistente": fantasmas,
                # Logica do dominio que a SKI nomeia e que ainda nao e'
                # chamavel. Cada entrada diz ONDE esta, para quem quiser
                # promote-la a intent saber o que falta escrever.
                "prometido_sem_botao": sem_intent,
                "cache_s": _int_se_numero((ski.get("performance") or {}).get("cache")),
                "flags": list((ski.get("performance") or {}).get("flags") or []),
                "notas": ski.get("_corpo", ""),
            }
        )

    return {
        "skills": saida,
        "total": len(saida),
        "handlers_fantasmas": total_fantasmas,
        "promessas_sem_botao": total_promessas,
        "aviso": (
            "Os handlers listados sao intents REAIS do registo. Um handler em "
            "`cobre_inexistente` nao existe e nao pode ser chamado."
            if total_fantasmas
            else "Todos os handlers declarados existem no registo."
        ),
        "aviso_promessas": (
            "`prometido_sem_botao` nomeia logica do dominio que a SKI conhece e "
            "que ainda NAO tem intent — nao e' chamavel. Cada nota diz onde "
            "esta, para quem a promote-la saber o que falta."
            if total_promessas
            else "Toda a logica nomeada pelas SKIs e' chamavel."
        ),
    }
