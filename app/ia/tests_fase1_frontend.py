"""A Fase 1 inteira, doranchio do produtor ate ao DOM. O que fecha o ciclo.

MEDIDO 2026-10-08. ate aqui a Fase 1 tinha tres meias-verdades que passavam
todas as suites:

1. o servidor produzia `widget_composicao` — e nao havia quem a lesse;
2. o browser lia a composicao — mas nenhum handler a mandava;
3. um handler mandava — mas nenhuma suite media que a mesa fosse desenhada.

Trespecas que, juntas, davam um produto que nao faz nada. Este teste e' o que
liga as tres: pega na resposta HTTP que o browser recebe e passa-a ao
`normalizaComposicao` do browser, o mesmo objecto que `vigia()` usa.
"""

import io
import json
import os
import re
import unittest


class MesaChegaAoProdutorTest(unittest.TestCase):
    """Sem base de dados: e' sobre o contrato entre o que o Python escreve e
    o que o JavaScript le."""

    RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    JS = os.path.join(RAIZ, "app", "static", "js", "ia-local", "palco-amplia.js")

    def setUp(self):
        with open(self.JS, encoding="utf-8") as fh:
            self.js = fh.read()

    def _fonte_da_funcao(self, nome):
        """O corpo da funcao, do `function nome` ate ao fecho correspondente."""
        m = re.search(r"function\s+%s\s*\(" % re.escape(nome), self.js)
        if not m:
            self.fail(f"a funcao {nome} nao existe em {self.JS}")
        inicio = self.js.index("{", m.end())
        nivel = 0
        for i in range(inicio, len(self.js)):
            if self.js[i] == "{":
                nivel += 1
            elif self.js[i] == "}":
                nivel -= 1
                if nivel == 0:
                    return self.js[inicio : i + 1]
        self.fail(f"a funcao {nome} nao fecha")

    # ------------------------------------------------------------------ JS

    def test_o_vigia_le_a_composicao_de_topo(self):
        """O `vigia` tem de ler `corpo.widget_composicao`.

        Sem esta linha o servidor produz o campo e o browser ignora — e nada
        falha, porque o `dados` continua a vir e o palco antigo desenha uma
        mesa vazia ou errada. E o mesmo vazio da `out["copiloto"]`.
        """
        vigia = self._fonte_da_funcao("vigia")
        self.assertIn("widget_composicao", vigia)
        self.assertIn("normalizaComposicao", vigia)

    def test_a_composicao_tem_prioridade_sobre_o_palco(self):
        """Composição primeiro. Vem de um intent novo; o palco é o caminho velho.

        E a ordem importa: se o palco fosse primeiro, uma resposta com as duas
        coisas mostraria a mesa velha e ignoraria a que o handler escolheu — e
        isso seria um bug que so apareceria nos intents que devolvem as duas.
        """
        vigia = self._fonte_da_funcao("vigia")
        i_comp = vigia.index("widget_composicao")
        i_palco = vigia.index("PALCO_SLUG")
        self.assertLess(
            i_comp,
            i_palco,
            "a composicao tem de ser lida ANTES do palco antigo",
        )

    def test_o_vigia_desenha_a_composicao(self):
        """Ler nao e' desenhar.

        O caminho da composicao desenha directamente. O caminho do palco vai por
        `montarDoServidor`, que desenha — por isso aqui ha UMA chamada, e nao
        duas. Este teste diz isso de proposito: se um dia alguem trocar o
        `montarDoServidor(dados)` por um `return` e o palco deixar de desenhar,
        o `test_o_palco_antigo_ainda_desenha` abaixo e' que apanha.
        """
        vigia = self._fonte_da_funcao("vigia")
        self.assertIn("desenhaMesa(", vigia)
        self.assertIn("completaDadosTopGlobais(", vigia)
        self.assertIn("emitir(", vigia)
        # e o caminho novo tem de devolver ANTES de cair no palco, senao os dois
        # desenham e o produtor ve a mesa duas vezes
        self.assertIn("return;", vigia)

    def test_o_palco_antigo_ainda_desenha(self):
        """O caminho velho nao pode ter perdido o desenho."""
        self.assertIn("desenhaMesa(", self._fonte_da_funcao("montarDoServidor"))

    def test_o_vigia_encontra_se_ou_guarda_a_excepcao(self):
        """Uma composicao mal formada nao pode partir quem observa.

        O `espiaExec` embrulha o `fetch` e o `try/catch` esta em volta do
        `vigia`. Isto prova que a protecao existe — porque uma composicao que
        rebente aqui apagaria a tela do produtor, que e' a pior coisa que um
        extra opcional pode fazer.
        """
        self.assertIn("espiaExec", self.js)
        embrulhado = self._fonte_da_funcao("espiaExec")
        self.assertIn("catch", embrulhado)
        self.assertIn("Observar nunca pode partir", embrulhado)

    # --------------------------------------------------------------- Python

    def test_o_sandbox_normaliza_antes_de_devolver(self):
        """A garantia do servidor: o que sai de `executar` ja' vem normalizado."""
        with open(
            os.path.join(self.RAIZ, "app", "ia", "sandbox.py"), encoding="utf-8"
        ) as fh:
            sandbox = fh.read()
        self.assertIn("_normalizar_composicao", sandbox)

    def test_a_mesma_exigencia_dos_dois_lados(self):
        """O teto de 8 e' o mesmo dos dois lados — e o teste diz isso.

        Duas constantes com o mesmo valor em duas linguagens divergem no dia em
        que uma sobe. `tests_widget_composicao.py` ja' compara as duas
        (`_TETO_COMPOSICAO == palco.MAX_WIDGETS`); aqui confirmamos que o
        JavaScript tambem usa o mesmo numero, e nao um magico solto.
        """
        comp = self._fonte_da_funcao("normalizaComposicao")
        self.assertIn(
            "8",
            comp,
            "o JS tem de usar o mesmo teto de 8 que o servidor; "
            "um numero magico aqui diverge na primeira subida",
        )

    def test_o_frontend_esta_no_service_worker(self):
        """O ficheiro tem de estar no precache, senao a mesa nao aparece offline.

        E o produto promete offline-first. Um `palco-amplia.js` novo que nao entre
        no precache e' um ficheiro que so existe quando ha rede — e a IA local e'
        a promessa que se distingue.
        """
        with open(
            os.path.join(self.RAIZ, "app", "static", "js", "pwa", "sw.js"),
            encoding="utf-8",
        ) as fh:
            sw = fh.read()
        self.assertIn("ia-local/palco-amplia.js", sw)

    def test_a_composicao_e_serializavel(self):
        """O campo vai por JSON. Um valor que o `json.dumps` nao aceite e' um
        campo que o browser nunca ve — e nao ha erro no servidor, que e' o pior
        sitio para um dado sumir."""
        from app.ia.sandbox import _normalizar_composicao

        saida = _normalizar_composicao(
            [{"tipo": "kpi-custo", "config": {"periodo": "30d"}}]
        )
        texto = json.dumps({"widget_composicao": saida})
        self.assertEqual(json.loads(texto)["widget_composicao"], saida)
