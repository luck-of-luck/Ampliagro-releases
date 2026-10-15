"""Guardas de template: impede vazamento de sintaxe Django para a tela.

Por que este arquivo existe
---------------------------
O lexer de template do Django (``django.template.base.tag_re``) compila os
delimitadores com ``re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})")`` **sem**
``re.DOTALL``. Logo, um comentario ``{# ... #}`` que se estende por mais de
uma linha **nao e reconhecido como comentario**: o lexer nao casa o token e o
texto inteiro cai na saida como conteudo literal.

Isso ja vazou varias vezes para o usuario, no rodape das paginas:

* ``{# PERF: theme-system.js ... #}`` (commit 70fbbee)
* ``{# Build stamp: ... #}`` (commit bccaa1c)
* ``{# Sem opacity aqui: ... #}`` (reintroduzido durante o trabalho de contraste)

E o problema e mais largo do que ``{# #}``: **qualquer** tag partida em linha
vaza — ``{% ... %}`` e ``{{ ... }}`` tambem. Confirmado em producao: um
``{% include "partials/_empty_state_cta.html" with ... %}`` escrito em 6 linhas
saiu no HTML das paginas de cadastro de apiario e aquatico como texto literal.

Comentario e tag de linha unica funcionam; multi-linha nao. Estas guardas
existem para o motivo ficar escrito perto de onde a regra e aplicada, e para o
bug nao voltar em silencio.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.exceptions import TemplateSyntaxError
from django.test import SimpleTestCase

# Tags de template que contenham quebra de linha.
COMENTARIO_MULTILINHA = re.compile(r"\{#[\s\S]*?#\}")
TAG_BLOCO_MULTILINHA = re.compile(r"\{%[\s\S]*?%\}")
TAG_VARIAVEL_MULTILINHA = re.compile(r"\{\{[\s\S]*?\}\}")

# Trechos onde uma tag multi-linha e INofENSIVA porque o proprio Django ignora
# o conteudo: o corpo de {% comment %} e {% verbatim %} nunca e emitido.
CONTEUDO_IGNORADO = re.compile(
    r"\{%(?:\s*)comment(?:\s*)%\}[\s\S]*?\{%\s*endcomment\s*%\}"
    r"|\{%\s*verbatim\s*%\}[\s\S]*?\{%\s*endverbatim\s*%\}"
)


def _templates():
    base = Path(settings.BASE_DIR) / "app" / "templates"
    return sorted(base.rglob("*.html"))


def _tags_multilinha(texto):
    """Devolve as tags multi-linha de `texto` que o Django NAO iriam reconhecer.

    Mascara antes o corpo de {% comment %}/{% verbatim %}: ali a tag abre e
    fecha na mesma linha por construcao, e o resto do conteudo nunca sai.
    """
    mascarado = CONTEUDO_IGNORADO.sub(lambda m: re.sub(r"[^\n]", "", m.group(0)), texto)
    achados = []
    for regex, nome in (
        (COMENTARIO_MULTILINHA, "{# #}"),
        (TAG_BLOCO_MULTILINHA, "{% %}"),
        (TAG_VARIAVEL_MULTILINHA, "{{ }}"),
    ):
        for match in regex.finditer(mascarado):
            if "\n" in match.group(0):
                achados.append((nome, mascarado[: match.start()].count("\n") + 1))
    return achados


class ComentarioDjangoNaoVazaTest(SimpleTestCase):
    """Nenhum template pode conter {# ... #} multi-linha (vaza como texto)."""

    def test_nenhum_comentario_multilinha_em_templates(self):
        offenders = []
        for path in _templates():
            texto = path.read_text(encoding="utf-8", errors="replace")
            for match in COMENTARIO_MULTILINHA.finditer(texto):
                if "\n" in match.group(0):
                    linha = texto[: match.start()].count("\n") + 1
                    offenders.append(f"{path.relative_to(settings.BASE_DIR)}:{linha}")
        self.assertEqual(
            offenders,
            [],
            "Comentario {# #} multi-linha vaza como texto na pagina (Django nao "
            "aplica DOTALL no lexer de template). Use comentario de linha unica, "
            "<!-- --> ou mova a explicacao para o codigo Python/commit: "
            + ", ".join(offenders),
        )

    def test_comentario_multilinha_realmente_vaza(self):
        """Characterization test do Django 5.x.

        O lexer de template nao compila DOTALL, entao ``{# ... #}`` multi-linha
        NAO e removido. Este teste trava esse comportamento: se o Django mudar
        e passar a remover, o teste falha e avisa que a guarda do scanner pode
        ser simplificada.
        """
        saida = Template("A\n{# l1\nl2 #}\nB").render(Context({}))
        self.assertIn(
            "{#",
            saida,
            "Django passou a remover comentarios {# #} multi-linha. A regra do "
            "scanner pode ser relaxada e este teste removido.",
        )

    def test_comentario_de_linha_unica_e_removido(self):
        """O oposto: linha unica funciona e nao pode quebrar."""
        saida = Template("A {# single #} B").render(Context({}))
        self.assertNotIn("{#", saida)
        self.assertNotIn("#}", saida)


class TagDeBlocoNaoVazaTest(SimpleTestCase):
    """{% ... %} e {{ ... }} multi-linha tambem vazam — nao so {# #}."""

    def test_nenhuma_tag_multilinha_em_templates(self):
        offenders = []
        for path in _templates():
            texto = path.read_text(encoding="utf-8", errors="replace")
            for nome, linha in _tags_multilinha(texto):
                offenders.append(
                    f"{path.relative_to(settings.BASE_DIR)}:{linha} ({nome})"
                )
        self.assertEqual(
            offenders,
            [],
            "Tag de template multi-linha vaza como texto na pagina (Django nao "
            "aplica DOTALL no lexer). Reescreva em linha unica: "
            + ", ".join(offenders),
        )

    def test_tag_de_bloco_multilinha_realmente_vaza(self):
        """Prova de que o problema vale para uma tag {% %} unica partida em linha.

        Cuidado com o teste obvio e enganoso: ``{% if %}`` / corpo / ``{% endif %}``
        renderiza bem, porque CADA tag esta numa linha so. O que quebra e UMA tag
        unica partida em varias linhas — que e o caso do ``include ... with``.
        """
        saida = Template("x\n{% if y %}\n1\n{% endif %}\nz").render(
            Context({"y": True})
        )
        self.assertNotIn("{%", saida, "sanity: varias tags, uma por linha, funcionam")
        self.assertEqual(saida.strip(), "x\n\n1\n\nz".strip())

    def test_tag_de_bloco_partida_quebra_o_parser(self):
        """Uma tag {% %} partida em linha orfa o resto do template.

        E o mesmo defeito do lexer, visto pelo outro lado: alem de vazar texto
        cru, a tag quebrada faz o parser tratar o token seguinte como tag
        orfa. Se um dia isso deixar de estourar, a guarda do scanner pode ser
        revista.
        """
        with self.assertRaises(TemplateSyntaxError):
            Template("x\n{% if y\n%}1{% endif %}z")

    def test_include_multilinha_realmente_vaza(self):
        """O caso que chegou em producao: include ... with em varias linhas."""
        fonte = 'a\n{% include "x.html" with\n  k="v" %}\nb'
        saida = Template(fonte).render(Context({}))
        self.assertIn("{% include", saida)

    def test_corpo_de_comment_e_verbatim_e_ignorado(self):
        """Nao dar falso positivo: o corpo de {% comment %} nunca e emitido."""
        texto = '{# a\nb #}\n{% comment %}\n{% include "x" with\nk="v" %}\n{% endcomment %}\n'
        achados = _tags_multilinha(texto)
        # so o comentario {# #} e违规; a tag dentro de {% comment %} nao conta
        self.assertEqual([n for n, _ in achados], ["{# #}"])


class RenderNaoExpoeSintaxeTest(SimpleTestCase):
    """Construcoes validas nao podem devolver marcadores crus."""

    def test_render_nao_expoe_marcadores_validos(self):
        for fonte, esperado in (
            ("A {# single #} B", "A  B"),
            ("{% if x %}nao{% endif %}", ""),
            ("{{ nao_existe }}", ""),
            ("{% comment %}z{% endcomment %}", ""),
        ):
            with self.subTest(fonte=fonte):
                saida = Template(fonte).render(Context({"x": False}))
                self.assertNotIn("{#", saida)
                self.assertNotIn("%}", saida)
                self.assertNotIn("{{", saida)
                self.assertEqual(saida, esperado)
