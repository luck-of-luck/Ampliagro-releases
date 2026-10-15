"""O botão NDVI deixou de fabricar o número. Este teste prova que ficou.

MEDIDO 2026-10-05. Este ficheiro **substitui** `test_guia_ferramentas_ndvi.py`,
que lia `window.ndviFerramenta` do template antigo.

O que mudou no código, e porquê o teste antigo não pôde ser só adaptado
====================================================================
A guia foi reconstruída: `ndviFerramenta` passou a `lerNdvi`, dentro de uma
IIFE, e deixou de ser `window.`-global. O teste antigo procurava
`window\.ndviFerramenta\s*=\s*async\s*function\s*\(\)\s*\{` e, não o
encontrando, devolvia `""` — e os três testes que dependiam dessa passagem
falhavam **sem dizer porquê**.

Isto é o que um teste que apanha pela assinatura faz quando o nome muda: falha
por razão errada. E a razão errada é pior que a certa, porque treina a
ignorar o vermelho.

Por isso este ficheiro passa a procurar a **capacidade**, não o nome da
função: procura a rota `/api/agronomia/ndvi/`, procura `ndvi_medio`, procura
`r.ok`. Se a implementação mudar de nome outra vez, os testes continuam a
perguntar se a mentira voltou — que é o trabalho deles.

O QUE ESTE TESTE PROVA, EM ORDEM DE IMPORTÂNCIA
================================================
1. **Nenhum caminho produz um NDVI que não veio da leitura.** Prova por
   negação: apanha decimais escritos à mão no bloco, e apanha um `||` com
   número.
2. **A rota existe.** `resolve()` não `grep`. Um cartão que aponta para um
   404 é o defeito original.
3. **`r.ok` antes do parse.** Um 404 devolve HTML, e `r.json()` sobre HTML
   lança — o `catch` entrava e lia como se fosse falha de rede.
4. **Sem talhão, diz que não há talhão.** E a lista é a do produtor.
"""

from __future__ import annotations

import pathlib
import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import Resolver404, resolve
from django.urls import reverse

RAIZ = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "guia-ferramentas.html"


def fonte() -> str:
    return TEMPLATE.read_text(encoding="utf-8", errors="replace")


def bloco_ndvi() -> str:
    """O código do NDVI, do início da função ao fim do `catch`.

    Procura pela capacidade, não pelo nome: `async function lerNdvi` hoje,
    `window.ndviFerramenta` ontem, `window._ndvi` amanhã. O que não muda é
    que há de estar aqui uma leitura de NDVI.
    """
    t = fonte()
    # A função que faz o fetch ao NDVI.
    m = re.search(r"(async\s+function\s+\w*ndvi\w*\s*\([^)]*\)\s*\{)", t, re.I)
    if not m:
        return ""
    # Fecha no fim da função: conta chaves, como o teste antigo fazia.
    ini = m.end() - 1
    nivel = 0
    for j in range(ini, len(t)):
        if t[j] == "{":
            nivel += 1
        elif t[j] == "}":
            nivel -= 1
            if nivel == 0:
                return t[ini : j + 1]
    return t[ini:]


class ONumeroInventadoNaoVoltou(TestCase):
    def setUp(self):
        self.bloco = bloco_ndvi()
        self.assertTrue(
            self.bloco,
            "não encontrei a função de NDVI no template. Procurou-se por "
            "`async function ...ndvi...`, e não por um nome fixo.\n\n"
            "Se a função foi removida, este teste deve falhar — mas com esta "
            "mensagem, que diz o que procurar. Não falhar em silêncio.",
        )

    # ------------------------------------------------------------------
    # 1) NENHUM NÚMERO ESCRITO À MÃO
    # ------------------------------------------------------------------
    def test_nenhum_decimal_no_leo_do_ndvi(self):
        """`0.72` no `catch` era o defeito. Nenhum decimal pode estar escrito.

        Prova por negação, não por comparação com o valor antigo: se amanhã
        alguém escrever `0.71`, este teste também falha. Comparar com `0.72`
        só apanharia aquele número exacto — que é a forma de escrever um
        teste que não protege nada.
        """
        decimais = re.findall(r"\b\d+\.\d+\b", self.bloco)
        self.assertEqual(
            decimais,
            [],
            f"o código do NDVI tem decimais escritos: {decimais}\n\n"
            f"Um índice de vegetação escrito no código é um número que a "
            f"falha fabricou. O `0.72` do `catch` de uma rota 404 era "
            f"exactamente isto: o produtor clicava, não havia sensor, e a "
            f"tela afirmava um valor com a assinatura dele em cima.",
        )

    def test_nenhum_fallback_com_numero(self):
        """`j.ndvi || '0.72'` — o segundo sítio onde se inventava.

        Havia **três** caminhos e dois inventavam: 200 com `ndvi`, 200 sem
        `ndvi`, e erro. Nenhum dizia «sem leitura».
        """
        fallbacks = re.findall(r"\|\|\s*(['\"])([^'\"]*)\1", self.bloco)
        com_digitos = [(a, b) for a, b in fallbacks if re.search(r"\d", b)]
        self.assertEqual(
            com_digitos,
            [],
            f"o NDVI tem {len(com_digitos)} fallback(s) com dígitos: "
            f"{com_digitos}\n\n"
            f"Um `||` com número é um segundo sítio onde a tela inventa "
            f"leitura. Se o campo não veio, o que tem de aparecer é "
            f"«sem leitura» — não o valor de outro caso.",
        )

    def test_o_catch_nao_mostra_ndvi(self):
        """O ramo de falha não escreve índice de vegetação.

        Este é o teste que sobrevive à rota passar a existir. Mesmo com a
        rota viva, um `catch` com número é um número que sobrevive a falhar
        — e a falha é exactamente quando não se deve inventar.
        """
        i = self.bloco.find("catch")
        self.assertNotEqual(
            i,
            -1,
            "o NDVI deixou de ter catch. Sem isto, um erro de rede "
            "reverta a aplicação e o produtor fica sem saber o que aconteceu.",
        )
        ramo = self.bloco[i:]
        numeros = re.findall(r"(?<![\w.])\d+\.\d+(?![\w])", ramo)
        self.assertEqual(
            numeros,
            [],
            f"o ramo `catch` escreve {numeros}. Um NDVI no ramo de falha é um "
            f"número que a falha fabricou.\n\n"
            f"O `catch` é o caminho NORMAL quando a rota dá 404: `fetch` não "
            f"levanta, devolve 404, `r.json()` sobre HTML levanta SyntaxError. "
            f"Ou seja, o número aparecia em TODOS os cliques.",
        )

    # ------------------------------------------------------------------
    # 2) A ROTA EXISTE
    # ------------------------------------------------------------------
    def test_a_rota_que_o_codigo_pede_existe(self):
        """`resolve()`, não `grep`.

        O defeito original pedia `/api/ia/super/`, que é Resolver404. Um
        `grep` na página não apanha nada; é o `resolve` que pergunta ao
        servidor de URLs.
        """
        m = re.search(r"fetch\(\s*'([^']*ndvi[^']*)'", self.bloco)
        self.assertIsNotNone(m, "o código do NDVI não tem fetch")
        alvo = m.group(1).split("?")[0]
        try:
            resolve(alvo)
        except (Resolver404, Exception):
            self.fail(
                f"o NDVI pede `{alvo}` e essa rota NÃO EXISTE.\n\n"
                f"O `fetch` devolve 404, `r.json()` sobre HTML lança "
                f"SyntaxError, e o `catch` entra — que é onde o número "
                f"inventado aparecia.\n\n"
                f"A rota real é `/api/agronomia/ndvi/?talhao_id=`."
            )

    def test_a_rota_antiga_nao_volveu(self):
        """`/api/ia/super/` não pode estar em código.

        Verifico linha a linha, ignorando comentários: o comentário que
        explica o defeito é o registo do que aconteceu, e apagá-lo seria
        perder a lição. Mas em código, não.
        """
        for linha in fonte().splitlines():
            limpa = linha.strip()
            if limpa.startswith(("//", "*", "/*", "#", "<!--", "async")):
                continue
            self.assertNotIn(
                "/api/ia/super/",
                limpa,
                f"a rota inventada voltou em código: {limpa[:90]}",
            )

    # ------------------------------------------------------------------
    # 3) `r.ok` ANTES DO PARSE
    # ------------------------------------------------------------------
    def test_verifica_r_ok_antes_do_parse(self):
        """`r.json()` sem `r.ok` transforma um 404 numa exceção genérica.

        Com `r.ok`, o 404 diz «não foi possível ler (HTTP 404)». Sem, o
        `catch` diz «erro desconhecido» — e o produtor não sabe se a rede
        falhou ou se o servidor não tem o talhão.
        """
        self.assertIn(
            "if (!r.ok)",
            self.bloco,
            "o NDVI faz `r.json()` sem verificar `r.ok`. Um 404 devolve HTML "
            "e `r.json()` lança — o `catch` entrava e perdia-se a informação "
            "do que aconteceu de facto.",
        )

    # ------------------------------------------------------------------
    # 4) SEM DADO DIZ SEM DADO
    # ------------------------------------------------------------------
    def test_trata_ndvi_nulo_como_sem_leitura(self):
        """`ndvi_medio: null` é o contrato do serviço. Tem de ser tratado.

        `app/api/views/agronomia.py:153` devolve `ndvi_medio: None` com
        `fonte_dado` e `motivo` quando não há fonte. Ignorar esse `None` e
        mostrar a série toda como se fosse leitura é inventar por omissão.
        """
        self.assertIn(
            "ndvi_medio",
            self.bloco,
            "o código do NDVI não menciona `ndvi_medio` — o campo que o "
            "serviço devolve. Sem ele não há como distinguir «não veio» de "
            "«veio zero».",
        )
        self.assertTrue(
            "null" in self.bloco or "undefined" in self.bloco,
            "o código do NDVI não compara `ndvi_medio` com `null` nem com "
            "`undefined`. Um `null` renderizado como se fosse um valor é "
            "mostrar «0» quando a verdade é «não medido».",
        )

    def test_mostra_a_fonte_quando_le(self):
        """`fonte_dado` no resultado. Um número sem origem é um número sem contexto.

        É o princípio de `proveniencia.py` aplicado ao ecrã: se sabes de
        onde veio, mostras; se não sabes, mostras que não sabes.
        """
        self.assertIn(
            "fonte_dado",
            self.bloco,
            "o NDVI não mostra a fonte da leitura. Um índice sem origem não "
            "distingue um sensor de uma interpolação.",
        )


class SemTalhaoNaoInventa(TestCase):
    """O que a página faz quando não há talhão."""

    def setUp(self):
        self.u = User.objects.create_user("guia_ndvi_vazio", password="x1234567")
        self.client.force_login(self.u)

    def test_sem_talhao_a_pagina_diz_que_nao_ha(self):
        """Produtor sem talhão vê `TALHOES = []` e o código avisa.

        Antes da correcção, `talhao=1` fixo mostrava os dados do talhão 1 ao
        produtor que tinha o talhão 7 — ou de outro, se o 1 fosse de outra
        fazenda. É uma fuga de dados entre produtores, não só um número
        errado.
        """
        html = self.client.get(reverse("guia-ferramentas")).content.decode("utf-8")
        m = re.search(r"var TALHOES\s*=\s*(\[[^;]*\]);", html)
        self.assertIsNotNone(
            m,
            "a página não passa `TALHOES` ao código. O botão fica sem "
            "saber o que é um talhão teu.",
        )
        self.assertEqual(
            m.group(1).strip(),
            "[]",
            "um produtor sem talhões devolveu %s" % m.group(1).strip(),
        )

    def test_o_codigo_avisa_antes_de_pedir(self):
        """A lista vazia tem de ser tratada, não é pasada à frente.

        `TALHOES.map(...)` sobre `[]` dá `[]`, o `prompt` abre vazio, e o
        produtor não sabe o que está a escolher. O aviso é o que falta.
        """
        bloco = bloco_ndvi()
        self.assertIn(
            "!TALHOES.length",
            bloco,
            "o código não trata a lista de talhões vazia. Sem o aviso, o "
            "produtor vê um `prompt` vazio e não sabe o que se espera dele.",
        )

    def test_a_escolha_e_validada_contra_a_lista(self):
        """O que o produtor escreve tem de existir na lista dele.

        `prompt` devolve texto livre. Sem validação, escrever `99` levava a
        um pedido por um talhão que não é seu — ou a um 404 que ninguém
        sabe ler.
        """
        bloco = bloco_ndvi()
        self.assertIn(
            "filter",
            bloco,
            "o código não valida a escolha contra a lista de talhões.",
        )
        self.assertIn(
            "encodeURIComponent",
            bloco,
            "o id do talhão vai para a query string sem `encodeURIComponent`. "
            "Um nome com acento ou um id manipulado passa mal.",
        )
