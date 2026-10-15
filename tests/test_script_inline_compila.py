"""O JavaScript das paginas tem de COMPILAR, nao apenas existir.

MEDIDO 14/10/2026. `app/templates/perfil-config.html` tinha
`_cfgSemAcento()` sem as duas primeiras linhas do corpo — sobrava
`.replace(.).toLowerCase();` a começar a declaração. Um SyntaxError.

E aqui esta o que importa: **um SyntaxError dentro de um `<script>` não falha
só a função. Impede o bloco INTEIRO de compilar.** Toda a página de culturas
ficou morta no navegador — a lista não montava, a busca não existia, o botão
de guardar não respondia — e o produtor via uma página que parecia funcionar
e não fazia nada.

`tests/test_editar_culturas.py` passou na mesma: lê o HTML do servidor e
confirma que os campos existem. É um teste correcto que não chega ao lado
onde o defeito estava. Faltava o passo seguinte — pegar no JavaScript que o
servidor mandou e ver se o motor aceita aquilo.

Este teste é esse passo. Não substitui um teste de e2e e não afirma que a
página funciona: afirma que o script COMPILA, que é o pré-requisico para
qualquer outra coisa acontecer.

Usa `html.parser` e não expressões regulares. Já houve duas voltas por causa
disso: o `{{ dados|json_script:"id" }}` do Django escreve
`<script id="..." type="application/json">`, e um regex que junta esse bloco
ao seguinte produz um erro que parece um SyntaxError real e não é nada disso.
Um parser não erra dessa maneira.

`node` é uma dependência real deste projecto (o workflow faz `node --check` e
o frontend compila com Vite), por isso a sua ausência aqui é um erro e não um
salto silencioso.
"""

import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase

# As páginas com JavaScript inline escrito à mão. Um template com
# `{% static %}` e `json_script` tem de ser RENDERIZADO: copiar o ficheiro do
# disco dá código diferente do que o navegador recebe.
PAGINAS = [
    "/perfil/config/",
    "/pitch/",
]


class _RecolheScripts(HTMLParser):
    """Separa o JavaScript inline do resto, como um navegador faria."""

    #: `application/json` e `text/template` são dados, não código.
    NAO_E_JS = {"application/json", "text/template", "text/html"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocos = []
        self._atual = None
        self._profundidade = 0

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        d = dict(attrs)
        if "src" in d:
            return
        tipo = (d.get("type") or "").strip().lower()
        if tipo and tipo not in ("text/javascript", "application/javascript", "module"):
            return
        self._atual = []
        self._profundidade = 1

    def handle_endtag(self, tag):
        if tag == "script" and self._atual is not None:
            self.blocos.append("".join(self._atual))
            self._atual = None
            self._profundidade = 0

    def handle_data(self, data):
        if self._atual is not None:
            self._atual.append(data)


class ScriptInlineCompilaTest(TestCase):
    def setUp(self):
        User.objects.create_user("dono", password="x")
        self.c = Client()
        self.c.force_login(User.objects.get(username="dono"))

    def test_toda_a_pagina_tem_o_script_compilado(self):
        node = shutil.which("node") or shutil.which("node.exe")
        self.assertIsNotNone(
            node, "node nao esta no PATH; este projecto precisa dele para o build"
        )

        tmp = Path(tempfile.mkdtemp(prefix="js-check-"))
        try:
            for url in PAGINAS:
                html = self.c.get(url).content.decode("utf-8")
                p = _RecolheScripts()
                p.feed(html)

                self.assertTrue(
                    p.blocos, f"{url}: nenhum <script> de JavaScript encontrado"
                )
                for i, js in enumerate(p.blocos):
                    destino = tmp / (url.strip("/").replace("/", "_") + f"_{i}.js")
                    destino.write_text(js, encoding="utf-8")
                    r = subprocess.run(
                        [node, "--check", str(destino)],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    if r.returncode != 0:
                        inicio = " ".join(js.strip()[:120].split())
                        self.fail(
                            f"{url}: o <script> {i} nao compila.\n"
                            f"{r.stderr}\n"
                            f"Comeca por: {inicio}\n"
                            f"Um SyntaxError aqui impede o bloco INTEIRO de correr: "
                            f"a pagina fica morta no navegador, mesmo parecendo correcta."
                        )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
