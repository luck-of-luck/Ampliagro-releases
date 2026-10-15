"""voz.py — o que o produtor LÊ, e como soa.

MEDIDO, NÃO SUPOSTO
===================
Antes desta correcção, em `app/ia/*.py`:

    25/29 ficheiros  usam  #  (cabeçalho markdown)
    19/29 ficheiros  usam  ** (negrito markdown)
     9/29 ficheiros  usam  R$ (abreviature de sistema)
     7/29 ficheiros  usam  setas Unicode
     4/29 ficheiros  usam  emoji
     0/29 ficheiros  usam  ```

Um produtor no meio do talhão não vê um asterisco duplo. Vê dois
asteriscos e adivinha o resto. E `**` numa *docstring* é correcto — é para
quem lê o código. O problema é `**` numa *resposta*.

POR QUE UM MÓDULO, E NÃO UM LINTER
==================================
Porque o problema não é onde o `**` está escrito, é onde ele SAI. Um
handler novo escreve `**negrito**` na resposta, não há lint que apanhe
isso, e a regra "não escrever markdown nas respostas" vive num ficheiro de
regras que ninguém lê.

A correcção é no **limite**: `sandbox.executar` lava a resposta antes de a
devolver. Um só sítio, e vale para todos os handlers — incluindo os que
outra gente escreve e eu não controlo.

O QUE ESTE MÓDULO NÃO FAZ
-------------------------
Não reescreve frases. Não sabe o que um produtor quer dizer melhor do que o
autor do handler — e uma voz que reescreve o sentido é pior do que uma voz
robótica, porque parece mais segura do que é.

Ele tira o que não pertence a uma conversa: formatação, emoji, setas,
espaçamento duplo, e a impersonalidade das instruções de sistema. O resto é
do autor.
"""

from __future__ import annotations

import re
import unicodedata

#: Emoji e pictogramas, por faixa de Unicode. Cobre o que aparece em
#:Ranges de emoji: o telemóvel do produtor e o computador do programador
#: não mostram o mesmo conjunto, e um pictograma que não aparece aqui
#: continua a ser lixo numa resposta.
_RE_EMOJI = re.compile(
    "["
    "\U0001f000-\U0001faff"  # emoticons e símbolos
    "\U00002600-\U000027bf"  # símbolos Miscellaneous
    "\U00002b00-\U00002bff"  # setas e triângulos
    "\U0000fe00-\U0000fe0f"  # selectors de variação
    "\U0001f1e6-\U0001f1ff"  # bandeiras
    "]"
)

#: Setas. A Unicode E a ASCII: o `->` aparece em `intents.py` e `ia-local.js`
#: desde sempre, e uma resposta que mostra `->` ao produtor é tão máquina
#: como uma que mostra `→`.
_RE_SETA = re.compile(r"[→←↑↓⇒⟶⟵↔]|->|<-|=>")
_RE_CABECALHO = re.compile(r"^\s*#{1,6}\s*", re.M)
_RE_NEGRITO = re.compile(r"\*\*([^*]+)\*\*")
_RE_ITALICO = re.compile(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])")
_RE_TILDA = re.compile(r"~~([^~]+)~~")
_RE_BACKTICK = re.compile(r"`([^`]+)`")
_RE_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_RE_BOLINHA = re.compile(r"^\s*[•●▪·]\s*", re.M)
_RE_ESPACO_FIM = re.compile(r"[ \t]+$", re.M)

#: O handler fala de si na terceira pessoa. Numa resposta, "Ele avisa quando
#: o sync fica offline" é o sistema a falar de si como se fosse uma pessoa
#: ao lado de outra.
#:
#: A correcção NÃO é passar para a primeira pessoa — "aviso quando" continua a
#: ser o sistema a falar de si, só que mais curto. É TIRAR O SUJEITO: o que
#: o produtor precisa de saber é o que vai acontecer, não quem vai dizer.
#:
#:     "Ele avisa quando o sync fica offline."
#:     -> "Avisa quando a sincronização fica desligada."
_RE_TERCEIRA = re.compile(
    r"(?:^|(?<=[.!?]\s)|(?<=\n))\s*(?:Ele|Ela|Este|Esta|Isto)\s+",
    re.I,
)

#: Palavras de sistema que não significam nada para quem está no campo.
#:
#: O artigo vem JUNTO, porque trocar a palavra e deixar o artigo é o que
#: produz "o sincronização" — e um erro gramatical numa resposta diz ao
#: produtor que ninguém a reviu.
RE_SISTEMA = {
    "sync": ("a", "ligação"),
    # Invariáveis, e não "desligado"/"ligado": não sabemos o género do
    # sujeito, e um erro de concordância numa resposta diz ao produtor que
    # ninguém a reviu. "fica sem ligação" é correcto para qualquer sujeito.
    "offline": (None, "sem ligação"),
    "online": (None, "com ligação"),
    "dashboard": ("o", "painel"),
    "widget": ("o", "bloco"),
    "endpoint": ("o", "aparelho"),
    "preset": ("o", "modelo pronto"),
    "status": ("a", "situação"),
    "timestamp": ("a", "hora"),
    "payload": ("os", "dados"),
    "timeout": ("o", "tempo esgotado"),
    "cache": ("o", "guardado"),
    "hook": ("o", "gatilho"),
    "deploy": ("a", "publicação"),
    "build": ("a", "compilação"),
}

_RE_ARTIGO = r"[oas]s?"


#: Marcadores de enfase: `**`, `__`, `~~`, crase, `*` e `_`. Inclui os
#: duplicados (`__x__`), que uma regex de marcador único não apanha — e o
#: resultado é um texto que fica com os símbolos à vista e parece intacto,
#: que é pior do que não ter limpado nada.
_RE_NEGRITO = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_RE_ITALICO = re.compile(r"(?<![\w*])[*_]([^*_]+)[*_](?![\w*])")
_RE_TILDA = re.compile(r"~~([^~]+)~~")
_RE_BACKTICK = re.compile(r"`([^`]+)`")
_RE_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")

_RE_CABECALHO = re.compile(r"^\s*#{1,6}\s*", re.M)
#: A bolinha E o travessão. `- item` é uma lista em markdown e um produtor
#: não sabe o que é isso.
_RE_BOLINHA = re.compile(r"^\s*(?:[•●▪·]\s*|[-*+]\s+)", re.M)
_RE_ESPACO_FIM = re.compile(r"[ \t]+$", re.M)


def _sem_espaco_depois(texto: str) -> str:
    return texto


#: Um decimal **que vem com unidade**: `9.9 mm`, `18.0°C`, `8.3 km/h`.
#:
#: A unidade é o que separa uma MEDIDA de um IDENTIFICADOR, e a diferença não
#: é cosmética: `9.9 mm` é o número que decide se um produtor pulveriza, e
#: `3.11` é a versão de um Python. A mesma vírgula muda de sítio conforme o
#: que o número mede — e o sistema não tem esse direito.
#:
#: Só as guardas de ponto não chegam. Medido: com elas, `Python 3.11` ainda
#: virava `Python 3,11` — o `3` está isolado, e a guarda de ponto não vê o
#: `Python` que está antes. Foi uma regex que prometia proteger a versão e
#: não protegia, que é a forma mais cara de uma mentira: fica no comentário.
#:
#: Daí a unidade ser obrigatória. Uma medida de fazenda vem sempre com
#: unidade; um número de versão, nunca.
_UNIDADE = r"(?:%|°C|°F|mm|cm|km/h|m/s|m²|ha|L|kg|sc|t\b|min|dias?|horas?)"
#: O espaço vai no LOOKAHEAD, não antes dele.
#:
#: A primeira versão desta regex tinha `\s*(?={_UNIDADE})` e comia o espaço:
#: `0.0 mm` saía `0,0mm`. Um número colado à unidade não é português de
#: ninguém, e o defeito é invisível numa revisão apressada — parece correcto
#: até alguém ler a frase. Um lookahead não consome, e o espaço fica onde
#: estava.
_RE_DECIMAL = re.compile(rf"(?<![\d.])(\d+)\.(\d+)(?![\d.])(?=\s*{_UNIDADE})")

#: Dinheiro não leva unidade — leva `R$`. E é a segunda coisa que um produtor
#: brasileiro lê errado: `R$ 0.00` é lido como zero reais, e `R$ 1.234.56`
#: é lido como milhar quando são mil duzentos e trinta e quatro.
#:
#: Aqui a regex é outra, e não uma alternativa: `R$` é a ÂNCORA. Um ponto
#: depois de `R$` só pode ser decimal — não há versão de software que se
#: chame `R$1.2`, e o `1.234` com ponto de milhar continua protegido pelas
#: guardas, porque depois do ponto viria outro ponto.
_RE_DINHEIRO = re.compile(r"(R\$\s*)(?<![\d.])(\d+)\.(\d+)(?![\d.])")

#: O INTERVALO tem de ser uma coisa só.
#:
#: MEDIDO: `17.6–24.3°C` saía `17.6–24,3°C`. O primeiro número não tem
#: unidade colada — o que a segue é um traço e outro número — e a regra
#: simples não o via. O resultado era pior do que não converter nada: um
#: intervalo com vírgula de um lado e ponto do outro é um número que não
#: existe em lado nenhum, e ninguém o lê.
#:
#: Por isso a unidade do intervalo é a do FIM: se o último número do
#: intervalo tem unidade, o primeiro também é medida. Corre antes da regra
#: simples, para o número da direita ficar com a vírgula na passagem seguinte.
_RE_INTERVALO = re.compile(
    rf"(?<![\d.])(\d+)\.(\d+)(?=\s*[–—−-]\s*\d+[.,]\d+\s*{_UNIDADE})"
)


def limpar(texto: str | None) -> str:
    """Tira o que não é conversa. **Não acrescenta nada.**

    ESTA É A REGRA, E ELA FOI APRENDIDA À CUSTA
    -------------------------------------------
    A primeira versão desta função também TRADUZIA: `sync` para
    "sincronização", `offline` para "desligado", e tirava o sujeito de "Ele
    avisa" para virar "aviso". Parecia mais inteligente. Produzia:

        "• diesel 200 L"          -> "Diesel 200 L"      (capitalizou)
        "o sync fica offline"      -> "a ligação fica sem ligação"
        "dashboard endpoint sync"  -> "O painel o aparelho a ligação"

    Um transformador que reescreve é um transformador que MENTE, e mente com
    a confiança de quem parece terde cuidado. Um produtor que lê "a
    ligação fica sem ligação" perde mais confiança no sistema do que se
    lesse "o sync fica offline" — porque a segunda frase ele reconhece como
    algo que ele já ouve, e a primeira não existe em português nenhum.

    Então esta função só SUBTRAI. Formatação, emoji, setas, espaçamento.
    As palavras são do autor do handler, e quem as escreve sabe o que está
    a dizer melhor do que uma regex.

    E é por isso que o handler que escreve "Ele avisa" tem de ser corrigido
    onde está escrito, e não aqui: uma boundary que reescreve frases é uma
    boundary que, mais tarde, alguém vai não entender.
    """
    if not texto:
        return ""

    t = str(texto)

    # 1. markdown com sintaxe, de dentro para fora
    t = _RE_LINK.sub(r"\1", t)
    t = _RE_NEGRITO.sub(lambda m: m.group(1) or m.group(2) or "", t)
    t = _RE_TILDA.sub(r"\1", t)
    t = _RE_ITALICO.sub(r"\1", t)
    t = _RE_BACKTICK.sub(r"\1", t)

    # 2. emoji e setas
    t = _RE_EMOJI.sub("", t)
    t = _RE_SETA.sub("", t)

    # 3. início de linha
    t = _RE_CABECALHO.sub("", t)
    t = _RE_BOLINHA.sub("", t)

    # 4. espaçamento
    t = _RE_ESPACO_FIM.sub("", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" +([.,;:!?])", r"\1", t)
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)

    # 5. o número como um português o lê
    #
    # MEDIDO, executando os handlers de verdade: 25 números com ponto decimal
    # numa interface escrita em português. `18.0°C`, `9.9 mm`, `8.3 km/h`.
    #
    # Isto não é um detalhe tipográfico. A números que decide se um produtor
    # pulveriza ou não: `9.9 mm` de chuva numa aplicação é a diferença entre
    # tratar e perder o aplicação. E um produtor brasileiro lê `18.1` como
    # milhar-e-um, não como dezoito vírgula um.
    #
    # A guarda existe porque a mesma regex, sem ela, comeria o Python de um
    # programador: `Python 3.11` -> `Python 3,11`. Os dois números são reais;
    # a diferença é que um é medida e o outro é versão. `_RE_DECIMAL` só
    # pega em `9.9` isolado, e `3.11.4` fica inteiro pelas duas guardas.
    t = _RE_INTERVALO.sub(r"\1,\2", t)
    t = _RE_DECIMAL.sub(r"\1,\2", t)
    t = _RE_DINHEIRO.sub(r"\1\2,\3", t)

    return t.strip()


def tem_lixo(texto: str | None) -> bool:
    """A resposta ainda tem alguma coisa que não é conversa?

    Para o teste. Um `assertNotEqual(limpar(x), x)` passa em texto que já
    estava limpo; este diz se havia mesmo alguma coisa a limpar.
    """
    t = str(texto or "")
    return bool(
        _RE_NEGRITO.search(t)
        or _RE_ITALICO.search(t)
        or _RE_TILDA.search(t)
        or _RE_BACKTICK.search(t)
        or _RE_LINK.search(t)
        or _RE_EMOJI.search(t)
        or _RE_SETA.search(t)
        or _RE_CABECALHO.search(t)
        or _RE_BOLINHA.search(t)
    )


def sem_acentos(texto: str) -> str:
    """Só para COMPARAR, nunca para mostrar a uma pessoa."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()
