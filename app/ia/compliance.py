"""
compliance.py — a Blocklist de Compliance Ético/Ambiental (BUILD 3).

POR QUE ISSO É DETERMINÍSTICO E NÃO UM LLM
--------------------------------------------
Uma lista de termos é uma REGRA, e regra implementada com modelo de linguagem é
regra que pode falhar no dia em que mais importa. Se o sistema precisa dizer
"não, isso aqui não entra", essa resposta não pode depender de como o modelo
"sentiu" a frase. Logo: regex, sem chamada de inferência, sem exceção, sem
fallback que "deixa passar se o modelo não souber".

O requisito da BUILD 3 é este: se o pedido de criação de ferramenta contiver
termos sensíveis, a tool NEGA e registra auditoria.

O QUE ENTRA NA LISTA, E O QUE NÃO ENTRA — que é a parte séria
--------------------------------------------------------------
O erro óbvio aqui é bloquear "queimada". No Brasil, queimada de pasto é manejo
conservacionista e legalizado, sob autorização do órgão ambiental; é
técnica ordinary de produtor, não crime. E "app" é o nome do produto: bloquear
"app" bloquearia toda ferramenta do AmplIA.

Por isso a lista busca **marcadores de ato ilegal sem ambiguidade**, não
palavras do agro:

    entra:       "queimada_oculta", "queimada clandestina", "desmatamento"
    NÃO entra:   "queimada de pasto", "manejo de solo", "app", "App Geladeira"

Duas fronteiras, ambas deliberadas, ambas por risco de erro INDIRETO:

**1. "queimada" não entra.** Queimada de pasto é manejo conservacionista e
legalizado, sob autorização do órgão ambiental. Bloquear a palavra bloquearia
uma técnica legítima de produtor.

**2. "desmatamento" entra, mas "desmatada" (particípio) NÃO.**

    "Desmatamento"  -> bloqueado: nomeia o ato
    "Área desmatada" -> PERMITIDO: é como se chama a ferramenta de
                       COMPROMISSO AMBIENTAL que verifica APP e CAR

A segunda é uma decisão de produto, e ela é reversível num instante: basta
acrescentar o particípio à lista de termos. O que a motivou: o particípio é a
forma natural de nomear um campo que *registra* área já mapeada, e bloquear isso
impediria justamente a ferramenta de controle que o produtor precisa para
trabalhar dentro da lei. Quem decide é o produtor e o jurídico, não este
arquivo — por
isso o termo recusado volta SEMPRE nomeado, e nunca em silêncio.

A consequência geral: uma blocklist por termo não é um classificador de
intenção. Quem precisa dessa distinção é o humano, e por isso a recusa vai
para a IA E para o produtor, com o termo e o lugar onde ele apareceu, e vira
evento de auditoria. A blocklist é a primeira barreira, não a decisão final.

DONDE SE PROCURA
----------------
No **nome** da ferramenta E nos **rótulos e chaves** de cada campo. Verificar
só o nome seria trivial de contornar:

    criar_entidade("Controle de Área", campos=[{"rotulo": "Área desmatada"}])

O nome é inocente; o campo não. A ameaça real mora no campo que vai registrar a
infração.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

#: (termo, motivo, base legal de referência)
#:
#: Só entram marcadores que nomeiam o ato ilegal em si. Ver o docstring para
#: por que "queimada" e "app" ficaram de fora.
TERMOS_BLOQUEADOS: list[tuple[str, str, str]] = [
    (
        "desmatamento",
        "desmatamento sem autorizacao do orgao ambiental",
        "Lei 9.605/1998 (Lei de Crimes Ambientais), art. 55",
    ),
    (
        "desmatar",
        "acao de desmatar sem autorizacao",
        "Lei 9.605/1998, art. 55",
    ),
    (
        "madeira ilegal",
        "exploracao de madeira de origem ilegal",
        "Lei 9.605/1998, arts. 27 e 55",
    ),
    (
        "madeira nativa",
        "extracao de madeira de especie nativa protegida",
        "Lei 9.605/1998, art. 27",
    ),
    (
        "queimada oculta",
        "queimada ilegal registrada como manejo",
        "Lei 9.605/1998, art. 55",
    ),
    (
        "queimada clandestina",
        "queima clandestina de area",
        "Lei 9.605/1998, art. 55",
    ),
    (
        "queima clandestina",
        "queima clandestina de area",
        "Lei 9.605/1998, art. 55",
    ),
    (
        "caca ilegal",
        "caca de fauna nativa protegida",
        "Lei 9.605/1998, art. 32",
    ),
    (
        "transgressao ambiental",
        "transgressao ambiental",
        "Lei 9.605/1998, art. 55",
    ),
]


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento, com `_`, `-` e `.` virando espaço.

    Sem acento e sem underscore, "madeira_ilegal", "madeira ilegal" e
    "Madeira_Ilegal" são o mesmo termo. Se a comparação não normalizasse, o
    blocklist seria contornável por uma troca de digitação.
    """
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[_\-.]+", " ", t)
    # Colapsa espacos REPETIDOS. Sem esta linha, "madeira  ilegal" (dois
    # espacos) passa e "madeira ilegal" nao — e um furo de um caracter, num
    # tokenizer que tem token de espaco duplo. Blocklist com furo de um
    # espaco nao e blocklist.
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


#: (padrão compilado, termo legível, motivo, base). O termo legível viaja
#: junto porque `padrao.pattern` é o regex ESCAPADO — relatar
#: "madeira\\ ilegal" na recusa mostraria ao produtor um artefato de
#: implementação em vez do termo que ele escreveu.
_PADROES: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(re.escape(normalizar(termo))), normalizar(termo), motivo, base)
    for termo, motivo, base in TERMOS_BLOQUEADOS
]


def _alvos(nome: str, campos: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    """(descrição legível, texto) de cada lugar onde o termo pode estar.

    A descrição é legível de propósito: a recusa precisa dizer QUAL campo
    disparou, senão o produtor renomeia o nome da ferramenta e esbarra no mesmo
    muro.
    """
    alvos: list[tuple[str, str]] = [("nome da ferramenta", str(nome or ""))]
    for c in campos or []:
        if not isinstance(c, dict):
            continue
        rotulo = c.get("rotulo") or c.get("label") or ""
        chave = c.get("chave") or c.get("key") or ""
        if rotulo:
            alvos.append((f"rotulo do campo {rotulo!r}", str(rotulo)))
        if chave:
            alvos.append((f"chave do campo {chave!r}", str(chave)))
    return alvos


def analisar(nome: str, campos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Avalia o pedido de criação. Devolve SEMPRE um dicionário.

    Nunca levanta e nunca adia: quem chama precisa de uma resposta síncrona
    para decidir se pede confirmação ao produtor.

    Devolve `{"bloqueado": bool, "termo", "motivo", "base_legal", "onde",
    "texto"}` — todos os campos presentes nos dois caminhos, para quem chama
    não precisar de `.get()`.
    """
    for onde, texto in _alvos(nome, campos):
        normalizado = normalizar(texto)
        for padrao, termo, motivo, base in _PADROES:
            if padrao.search(normalizado):
                return {
                    "bloqueado": True,
                    "termo": termo,
                    "motivo": motivo,
                    "base_legal": base,
                    "onde": onde,
                    "texto": texto[:120],
                }

    return {
        "bloqueado": False,
        "termo": "",
        "motivo": "",
        "base_legal": "",
        "onde": "",
        "texto": "",
    }


def termos_catalogo() -> list[dict[str, str]]:
    """A lista como a IA e o produtor leem. Para a UI de configuração."""
    return [
        {"termo": normalizar(t), "motivo": m, "base_legal": b}
        for t, m, b in TERMOS_BLOQUEADOS
    ]
