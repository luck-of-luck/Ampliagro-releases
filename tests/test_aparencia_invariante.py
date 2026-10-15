"""A1 — a segunda metade do INVARIANTE (§1): o que a catraca de CSS não apanha.

ESTE FICHEIRO COMPLEMENTA `tests/test_token_violacao.py`. Não o substitui.

POR QUE EXISTE UM SEGUNDO FICHEIRO
----------------------------------
O `test_token_violacao.py` é uma catraca bem feita — por ficheiro, sem soma-zero,
com aceitação explícita — e diz no seu próprio docstring o que NÃO cobre:

    «Não apanha a cor escrita em `<style>` dentro de template, nem em
     JavaScript (`theme-presets.js` tem 1.135 linhas), nem em CSS gerado.
     A §1 é uma fronteira; este ficheiro cobre a parte dela que é CSS
     versionado.»

Fica registado que a §1.4 da carta apanha mais: os **tokens de runtime** (a
identidade visual é injectada por JS, não só declarada em CSS) e a **estrutura**
(grid, ordem, densidade, z-index). A §1.3 original tratava só de cor.

Porque isto é o que protege o A2 e o A3
----------------------------------------
`guide.js` tem 5.515 linhas e `ia-local.js` 6.066. Partir esses ficheiros vai
mexer em grid, ordem e densidade. Com a rede de segurança actual, essa refatoração
pode mudar a cara do produto e **nenhum teste falha**. Este ficheiro é essa rede.

O QUE ESTE FICHEIRO NÃO TENTA
-----------------------------
Não tenta levar aAppearance a zero. MEDIDO: `var(--cor-*)` aparece **1.033 vezes**
em CSS e o `design-tokens.css` — que a carta §1.2 chama de «o contrato» — declara
**zero** `--cor-*`. A família que o produto usa é definida por `soft-ui.css`,
`theme.css` e `ampliagro-global.css`, e há 32 nomes definidos em mais do que um
ficheiro (isso já está noutra catraca, `TokenCascade`). Zerar isto não é trabalho
de uma tarde: é mudar a aparência, que a §1 proíbe.

Por isso: **catraca, não zeragem.** Regista-se onde se está e falha-se quando se
piora. Um teste que começa a falhar no primeiro dia é um teste que ninguém
corrige — em duas semanas está `--noqa`, em dois meses está apagado.
"""

from __future__ import annotations

import json
import pathlib
import re

from django.test import SimpleTestCase

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSS = RAIZ / "app" / "static" / "css"
JS = RAIZ / "app" / "static" / "js"
BASELINE = pathlib.Path(__file__).parent / "aparencia_baseline.json"


#: `utf-8-sig` e não `utf-8`: o mesmo motivo do `test_token_violacao.py` — BOM
#: em JSON rebenta o `json.load` e deixa a baseline ilegível.
def _carrega() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8-sig"))


_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
_SET_PROPERTY = re.compile(r"""setProperty\(\s*['"`](--[\w-]+)['"`]""")


# ---------------------------------------------------------------- tokens runtime


class TokensRuntime(SimpleTestCase):
    """Os tokens que a identidade visual injecta por JavaScript.

    MEDIDO em 2026-10-03: **60 tokens distintos** em 4 ficheiros — 50 deles em
    `theme-presets.js`, que é o motor dos 27 presets e do modo escuro.

    Por que isto é invariante e não detalhe interno: o `design-tokens.css`
    declara **zero** `--cor-*`, e o sistema consome `var(--cor-*)` 1.033 vezes.
    A identidade visual do Ampliagro **não está no contrato** — está em JS e em
    três folhas de estilo. Mudar um `setProperty` é mudar a aparência do produto
    exactamente tanto quanto mudar uma cor no CSS.
    """

    def varre_tokens(self) -> dict[str, int]:
        achados: dict[str, int] = {}
        for f in sorted(JS.rglob("*.js")):
            nomes = set(
                _SET_PROPERTY.findall(f.read_text(encoding="utf-8", errors="replace"))
            )
            if nomes:
                achados[f.relative_to(JS).as_posix()] = len(nomes)
        return achados

    def test_nenhum_ficheiro_js_injecta_mais_tokens(self):
        actual = self.varre_tokens()
        baseline = _carrega()["tokens_runtime_por_ficheiro"]
        subiu = {
            ficheiro: (baseline.get(ficheiro, 0), n)
            for ficheiro, n in actual.items()
            if n > baseline.get(ficheiro, 0)
        }
        self.assertEqual(
            subiu,
            {},
            "Novo token injectado por JavaScript. A identidade visual é injectada "
            "por JS, não só declarada em CSS — por isso isto é §1 e não detalhe.\n"
            f"O que cresceu: {subiu}",
        )

    def test_total_de_tokens_runtime_nao_cresce(self):
        # DISTINTOS, nunca a soma por ficheiro. MEDIDO: 4 nomes aparecem em mais
        # do que um ficheiro, e a soma por ficheiro dava 64 contra 60 distintos.
        # A baseline guarda o número distinto, portanto somar aqui comparava
        # duas coisas diferentes — e era a soma que estava errada.
        #
        # Isto é a mesma armadilha que o `test_token_violacao.py` descreve para
        # o total global de cores, aplicada ao eixo errado: aqui a contagem por
        # ficheiro é a boa e o total é que não pode ser somado.
        nomes: set[str] = set()
        for f in sorted(JS.rglob("*.js")):
            nomes.update(
                _SET_PROPERTY.findall(f.read_text(encoding="utf-8", errors="replace"))
            )
        self.assertLessEqual(
            len(nomes),
            _carrega()["tokens_runtime_total"],
            f"Tokens runtime distintos: {len(nomes)}, baseline "
            f"{_carrega()['tokens_runtime_total']}. "
            "Um token novo precisa de ser declarado em CSS para ser auditável.",
        )


class TokensSoEmRuntime(SimpleTestCase):
    """Tokens que existem **só** em JavaScript, sem nada declarado em CSS.

    MEDIDO: 4 — `--height`, `--width`, `--lg-filter`, `--lg-tick`, todos de
    `liquid-glass.js`.

    Não é um defeito: `--width`/`--height` são geometria de um componente, não
    parte da paleta. Mas é uma fronteira que precisa de estar **escrita**, porque
    a próxima pessoa não tem como saber se pode inventar o `--cor-anything` do
    mesmo jeito. O que este teste faz é fixar a lista, para que a lista nova
    seja uma decisão e não um acaso.
    """

    def test_lista_de_tokens_sem_declaracao_css(self):
        css = "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(CSS.rglob("*.css"))
        )
        nomes: set[str] = set()
        for f in sorted(JS.rglob("*.js")):
            nomes.update(
                _SET_PROPERTY.findall(f.read_text(encoding="utf-8", errors="replace"))
            )
        so_runtime = sorted(n for n in nomes if n not in css)
        self.assertEqual(
            so_runtime,
            _carrega()["tokens_so_em_runtime"],
            "A lista de tokens que existem só em JS mudou.\n"
            "Se o token novo é geometria de componente, é legítimo — acrescente à "
            "baseline.\nSe é cor ou espaçamento, ele tem de ser declarado em CSS, "
            "porque CSS é onde aAppearance é auditável.",
        )


# ------------------------------------------------------- estrutura e densidade


#: {propriedade: o que controla}. Os comentários são removidos ANTES de contar —
#: sem isso o comentário que documenta um `z-index` conta-o como se fosse uso.
PADROES: dict[str, str] = {
    "z_index": r"(?<!-)z-index\s*:",
    "grid_template": r"grid-template-(?:columns|areas)\s*:",
    "grid_column": r"(?<!-)grid-column\s*:",
    "order": r"(?<!-)order\s*:\s*-?\d",
    "font_size_px": r"font-size\s*:\s*\d+(?:\.\d+)?px",
    "font_weight": r"font-weight\s*:\s*\d{3}",
    "line_height": r"line-height\s*:\s*\d",
    "height_px": r"(?<!-)height\s*:\s*\d+px",
    "gap_px": r"(?<!-)(?:gap|row-gap|column-gap)\s*:\s*\d+px",
    "espacamento_px": r"(?<!-)(?:padding|margin)(?:-[a-z]+)?\s*:\s*\d+px",
    "radius_px": r"border-radius\s*:\s*\d+px",
}

_QUE_E_ESTRUTURA = (
    "Mudar isto muda a cara do produto sem mudar nenhuma cor: a §1.3 (que só "
    "fala de cor) não apanha nada disto. A §1.4 da carta lista layout, ordem de "
    "colunas, densidade e z-index como o buraco que faltava — este é esse buraco."
)

#: Ficheiros GERADOS, fora da catraca — cada um por um motivo verificável.
#:
#: MEDIDO, e foi uma falha minha: a primeira versão desta catraca contava
#: `tailwind-compiled.css`. O `test_token_violacao.py` já o exclui, com o
#: motivo certo — é saída do `npx @tailwindcss/cli`, não escrita por uma pessoa.
#: Eu não repliquei a exclusão, e quando outra sessão correu `npm run build:css`
#: o contador mudou sozinho:
#:
#:     font-size +1   height +2   padding -1   z-index -2
#:
#: — todas as quatro **num ficheiro gerado**, zero em CSS escrito à mão. A
#: catraca acusou o produtor de mudar a aparência quando o que mudou foi o
#: compilador. E o pior efeito: um alarme falso treina a ignorar o alarme, e o
#: alarme verdadeiro (uma cor nova num `.css` escrito à mão) deixa de ser visto.
#:
#: `design-tokens.css` NÃO é excluído aqui, ao contrário do que acontece na
#: catraca de cor: lá ele está de fora porque é a *definição* da cor. Aqui é CSS
#: escrito à mão e faz parte do design — a contá-lo.
GERADOS = {
    # `package.json` -> `build:css` -> `npx @tailwindcss/cli`. Está no
    # `.gitignore` e no `.dockerignore`: é saído do build.
    "tailwind-compiled.css",
}


def _css_de_mao() -> list[pathlib.Path]:
    return [p for p in sorted(CSS.rglob("*.css")) if p.name not in GERADOS]


class EstruturaNaoCresce(SimpleTestCase):
    """Grid, ordem, densidade, tipografia e z-index, por ficheiro."""

    def varre(self) -> dict[str, dict[str, int]]:
        medido: dict[str, dict[str, int]] = {}
        for f in _css_de_mao():
            texto = f.read_text(encoding="utf-8", errors="replace")
            limpo = _COMENTARIO.sub(" ", texto)
            contagens = {
                chave: len(re.findall(pat, limpo)) for chave, pat in PADROES.items()
            }
            contagens = {k: v for k, v in contagens.items() if v}
            if contagens:
                medido[f.relative_to(CSS).as_posix()] = contagens
        return medido

    def test_nenhuma_estrutura_acima_da_baseline(self):
        actual = self.varre()
        baseline = _carrega()["layout_por_ficheiro"]
        subiu: dict[str, dict] = {}
        for ficheiro, contagens in actual.items():
            base = baseline.get(ficheiro, {})
            diff = {
                chave: (base.get(chave, 0), n)
                for chave, n in contagens.items()
                if n > base.get(chave, 0)
            }
            if diff:
                subiu[ficheiro] = diff

        self.assertEqual(
            subiu,
            {},
            f"Estrutura/aparência cresceu. {_QUE_E_ESTRUTURA}\n"
            "Por ficheiro, não por total: um total deixa o jogo fácil (tirar 10 de "
            "um ficheiro e pôr 10 noutro não mexe no número e muda o débito de "
            "sítio).\n"
            f"O que cresceu: {subiu}",
        )

    def test_baseline_nao_tem_ficheiro_que_ja_nao_existe(self):
        """Apagar CSS não pode apagar a dívida sem querer."""
        hoje = self.varre()
        orfas = sorted(set(_carrega()["layout_por_ficheiro"]) - set(hoje))
        self.assertEqual(
            orfas,
            [],
            f"Ficheiros na baseline que já não existem: {orfas}. "
            "Se foram apagados de propósito, regenere a baseline.",
        )

    def test_totais_globais_nao_crescem(self):
        actual = self.varre()
        base = _carrega()["layout_total"]
        subiu = {
            chave: (base.get(chave, 0), sum(v.get(chave, 0) for v in actual.values()))
            for chave in PADROES
            if sum(v.get(chave, 0) for v in actual.values()) > base.get(chave, 0)
        }
        self.assertEqual(subiu, {}, f"Totais de estrutura subiram: {subiu}")
