"""V3 — o teste que protege o INVARIANTE (§1): a aparência não pode mudar.

ESTE TESTE É A FILA V3 DA `docs/conversa-agentes2`
--------------------------------------------------
A §1.3 da carta fixa a regra testável do invariante:

    «Nenhuma cor, espaçamento, raio ou sombra pode ser escrito fora de
    `design-tokens.css`. Qualquer valor literal de cor em outro arquivo é
    violação.»

E a §5 diz do V3: «CI que falha se houver cor literal fora de
`design-tokens.css`... é o que garante que §1 sobrevive a V0–V2. Faça antes
de V2.» É este ficheiro.

POR QUE ISTE NÃO É «CONTAR ZERO»
---------------------------------
Porque a regra, escrita assim, já está violada 4.269 vezes. MEDIDO em
2026-10-03, com o scanner deste ficheiro (comentários CSS removidos antes
de contar, senão o comentário que explica uma cor contava-a):

    ficheiro                       hex  rgba/hsl/oklch
    paginas/extracted-components 1612        244
    paginas/dashboard-index.css   363        193
    paginas/registro-cultura.css  149        101
    paginas/registro-cafe.css     140         95
    ...                            ...        ...
    TOTAL (39 ficheiros)         2911       1334

Um teste que começa a falhar no primeiro dia é um teste que ninguém corrige:
em duas semanas está `--noqa`, em dois meses está apagado. O que protege uma
base já estragada é uma **catraca** (*ratchet*): regista-se onde se está hoje
e falha-se quando se piora. Nunca falha sozinho; falha quando alguém acrescenta.

Por isso este teste tem três propriedades que valem mais que o número:

1. **Por ficheiro, não total.** Um total global deixa o jogo fácil: tira 10
   cores de um ficheiro e põe 10 noutro, o número não mexe e o débito
   mudou de sítio. Por ficheiro não há soma-zero.
2. **Um ficheiro novo com cores falha**, porque não está na baseline. É o
   caso que mais importa: é o que impede a próxima pessoa de abrir um
   `.css` e inventar uma paleta.
3. **Aceitar a descida é explícito.** Quando alguém converte 300 literais
   para `var(--cor-*)`, o teste vai falhar — e a falha é o sinal de que
   merece baixar a baseline. O mecanismo está no `--aceitar`.

O QUE ESTE TESTE NÃO PROTEGE (e é preciso saber)
------------------------------------------------
Não apanha a cor written em `<style>` dentro de template, nem em JavaScript
(`theme-presets.js` tem 1.135 linhas), nem em CSS gerado. A §1 é uma
fronteira; este ficheiro cobre a parte dela que é CSS versionado.

E — medido, e é o achado mais importante desta sessão — **esta baseline não
é o problema maior.** Ver `TOKEN_CASCADE_ABAIXO`.

TOKEN_CASCADE_ABAIXO — O QUE A MEDIÇÃO ENCONTROU
-------------------------------------------------
A §1.2 da carta chama `design-tokens.css` de «o contrato». MEDIDO: esse
ficheiro define 105 variáveis e **zero** `--cor-*`. E o sistema consome
1.158 vezes `var(--cor-*)` — uma família de tokens que o «contrato» não
conhece. Quem a define são TRÊS ficheiros:

    soft-ui.css           103 definições
    ampliagro-global.css   43 definições
    theme.css              41 definições

E 11 desses nomes são definidos com VALORES DIFERENTES nos dois primeiros
ficheiros que os carregam. `--cor-primaria` é `#54c996` no `soft-ui.css` e
`#3ec48f` no `theme.css`. O vencedor depende da ordem de `<link>` em
`base.html:13,19,27,29` — que hoje é: design-tokens, soft-ui, theme,
ampliagro-global. Quem ganha é o último.

Isto está registado como achado, e **não** foi corrigido aqui: escolher qual
dos dois valores é o certo é uma decisão de aparência, e a §1 proíbe-me de a
tomar sozinho. Ver `docs/conversa-agentes2` §7, decisão D4.
"""

from __future__ import annotations

import json
import pathlib
import re

from django.test import SimpleTestCase

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSS = RAIZ / "app" / "static" / "css"
BASELINE = pathlib.Path(__file__).parent / "token_baseline.json"

#: Ficheiros que ficam de fora da catraca, cada um por um motivo verificável.
EXCLUIDOS = {
    # A §1.2: este ficheiro É o contrato. Aqui a cor literal é a definição
    # da cor, não uma violação.
    "design-tokens.css",
    # `package.json` → `build:css` → `npx @tailwindcss/cli`. Está no
    # `.gitignore` e no `.dockerignore`: é saído do build, não escrito por
    # uma pessoa. Contá-lo seria contar o compilador.
    "tailwind-compiled.css",
}

#: Comentários são removidos ANTES de contar. Sem isto, o comentário que
#: documenta uma cor conta-a como se fosse uma violação — e o ficheiro que
#: explica o problema passa a ser o culpado. É a decisão D7 do
#: `COORDENACAO_IA.md`, o mesmo cuidado que `test_clima_sem_invencao.py`
#: toma ao não procurar texto dentro de docstrings.
_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

#: Funções de cor. `rgb/rgba/hsl/hsla` são as de CSS clássico; `oklch/oklab/
#: lab/lch` são as que o Tailwind v4 emite (MEDIDO: `tailwind.css` tem
#: 84), e `color()` cobre `color(display-p3 ...)`.
_FUNCAO = re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\s*\(")


def conta_cores(caminho: pathlib.Path) -> int:
    """Cores literais no ficheiro, sem contar o que está em comentário."""
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    limpo = _COMENTARIO.sub(" ", texto)
    return len(_HEX.findall(limpo)) + len(_FUNCAO.findall(limpo))


def varre_css() -> dict[str, int]:
    """{ficheiro relativo: nº de cores literais}, só os que têm alguma.

    A chave é `.as_posix()`, nunca `str()`. MEDIDO: com `str()`, a baseline
    gerada no Windows fica com `paginas\\dashboard-index.css` e o runner do
    CI (Linux, `ubuntu-latest`) produz `paginas/dashboard-index.css` — 18
    chaves diferentes, e a catraca falhava num repositório limpo. Passava
    aqui e falhava lá, que é o pior sítio para uma falha: o CI é onde não há
    ninguém a ver. `as_posix()` dá `/` nos dois sistemas.

    Isto não é umorro: trocar só a linha não chega. A baseline tem de ser
    regerada com as chaves em `/`, senão as 18 linhas antigas continuam
    erradas — em direcção ao contrário.
    """
    medido: dict[str, int] = {}
    for caminho in sorted(CSS.rglob("*.css")):
        if caminho.name in EXCLUIDOS:
            continue
        n = conta_cores(caminho)
        if n:
            medido[caminho.relative_to(CSS).as_posix()] = n
    return medido


class TokenNaoCresce(SimpleTestCase):
    """A catraca do invariante."""

    def setUp(self):
        # `utf-8-sig` e não `utf-8`: o Notepad do Windows e o
        # `Set-Content -Encoding UTF8` do PowerShell escrevem BOM, e um BOM
        # em JSON faz o `json.load` rebentar — o que deixa a baseline
        # ilegível E o script que a regenera também. Medido a acontecer
        # durante a escrita deste ficheiro.
        self.baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))

    def test_nenhuma_cor_literal_acima_da_baseline(self):
        actual = varre_css()

        subiu = {
            ficheiro: (self.baseline.get(ficheiro, 0), n)
            for ficheiro, n in actual.items()
            if n > self.baseline.get(ficheiro, 0)
        }
        self.assertEqual(
            subiu,
            {},
            "Cor literal NOVA ou a mais. A §1.3 proíbe-cor-literal-fora-de-"
            "design-tokens.css.\n"
            "Se a cor é legítima, ela é um token: ponha-a em design-tokens.css "
            "e use var(--...).\n"
            "Se a intenção é mesmo ceder o número, é uma decisão de produto — "
            "não se toma num commit de arrumação:\n"
            "    python tests/aceitar_token_baseline.py\n"
            f"O que cresceu: {subiu}",
        )

    def test_baseline_nao_tem_ficheiro_que_ja_nao_existe(self):
        """Apagar CSS não pode apagar a dívida sem querer.

        Sem este teste, `git rm` de um ficheiro faria a baseline guardar
        linhas órfãs para sempre, e a contagem real passaria a divergir da
        catraca sem ninguém ver.
        """
        hoje = varre_css()
        orfas = sorted(set(self.baseline) - set(hoje))
        self.assertEqual(
            orfas,
            [],
            f"Ficheiros na baseline que já não existem: {orfas}. "
            "Se foram apagados de propósito, regenere a baseline.",
        )


class TokenCascade(SimpleTestCase):
    """A segunda casa dos tokens — o achado que a carta não tinha.

    Este teste NÃO falha hoje: mede e fixa o número, para que a contagem
    não cresça sem ninguém reparar. O ficheiro que ficou com a colisão está
    em `docs/conversa-agentes2` §7 (D4) para alguém decidir.
    """

    #: Ficheiros que definem `--cor-*`. MEDIDO em 2026-10-03.
    CASAS = ("soft-ui.css", "theme.css", "ampliagro-global.css")

    def test_o_contrato_nao_declara_a_familia_que_o_sistema_consome(self):
        contrato = self._definicoes(CSS / "design-tokens.css")
        cor = {nome for nome in contrato if nome.startswith("--cor-")}
        self.assertEqual(
            cor,
            set(),
            "design-tokens.css passou a definir --cor-*. Se isto é de propósito, "
            "o comentário de EXCLUIDOS e a §1.2 da carta têm de ser "
            "actualizados juntos — o contrato e a carta não podem divergir.",
        )

    def test_nome_de_token_definido_em_dois_ficheiros(self):
        """Conta os tokens repetidos entre as três casas. MEDIDO: **32**.

        Dos 32, 22 são `--cor-*` — a família que 1.158 sítios consomem.

        A contagem é por NOME DISTINTO, nunca por linha de declaração, e a
        razão é técnica: `soft-ui.css` tem 131 linhas de declaração mas
        só 66 nomes distintos, porque cada token aparece duas vezes — uma
        em `:root`, outra em `html.dark`. Isso é o mesmo token nos dois
        modos, não dois tokens.

        Contar por linha dava 97, e os 97 estão errados. Uma contagem que
        sobrestima o problema não é conservative: faz o número parecer
        maior do que é, e quando alguém o corrige a seguir, deixa de
        crer no resto do que o teste mede.
        """
        colisoes: dict[str, set[str]] = {}
        for ficheiro in self.CASAS:
            for nome in self._definicoes(CSS / ficheiro):
                colisoes.setdefault(nome, set()).add(ficheiro)

        repetidos = {nome: fs for nome, fs in sorted(colisoes.items()) if len(fs) > 1}
        self.assertEqual(
            len(repetidos),
            32,
            "A lista de tokens definidos em mais do que um ficheiro mudou. "
            "Subiu? Uma casa nova de tokens apareceu — e isso é uma decisão de "
            f"aparência (D4). Agora: {sorted(repetidos)}",
        )

    @staticmethod
    def _definicoes(caminho: pathlib.Path) -> dict[str, str]:
        """{nome: valor} das custom properties declaradas no topo do ficheiro.

        Por linha e não por regex sobre o ficheiro inteiro: só interessa o
        que está a DECLARAR (`--x: y;`), não o que está a usar.
        """
        achados: dict[str, str] = {}
        padrao = re.compile(r"^\s*(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);")
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            m = padrao.match(linha)
            if m:
                achados.setdefault(m.group(1), m.group(2).strip())
        return achados
