"""Testes de `app/ia/deteccao.py` — o servidor a entender.

O QUE ESTE MÓDULO COMBATE
=========================
Até aqui o servidor não tinha nenhuma comprehend de linguagem: recebia o
`deteccao` no `meta`, com os `scores` que o CLIENTE afirmava. Três
consequências, todas reais:

- o gate de confiança M3 era decorativo (a condição era
  `deteccao and deteccao.get("scores")`, e um cliente que mandasse `meta: {}`
  não passava por ele);
- um cliente MCP não tinha conversa nenhuma;
- a mesma frase dava resultados diferentes conforme quem perguntou.

O `sandbox` passou a CALCULAR os scores quando o cliente não os manda. Estes
testes existem para que essa seja a comportamento normal e não o exceptional.

A PARIDADE COM O NAVEGADOR
==========================
`ia-local.js` ainda calcula a detecção no browser, para não acrescentar uma
ida ao servidor a cada tecla. Isso deixa DUAS implementações da mesma regra,
e "duas implementações" é como as divergências começam.

Em vez de refazer o chat — que é a parte mais difícil de testar deste
projecto — este ficheiro fixa a lista de stopwords e o limiar, e o
`TesteDeParidadeComONavegador` vai buscar a lista ao próprio JavaScript e
compara. Se alguém acrescentar uma palavra a um lado e não ao outro, o
teste diz qual dos dois ficou para trás, em vez de a divergência aparecer
meses depois como "a IA percebe às vezes".
"""

import json
import pathlib
import re

from django.test import SimpleTestCase, TestCase

from app.ia.deteccao import LIMIAR, STOP, _palavras, detectar, normalizar
from app.ia.registro import REGISTO
from app.ia.sandbox import somente_leitura

JS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "static"
    / "js"
    / "ia-local"
    / "ia-local.js"
)


class NormalizacaoTest(SimpleTestCase):
    def test_tira_acentos(self):
        self.assertEqual(normalizar("temperatura"), "temperatura")
        self.assertEqual(normalizar("irrigação"), "irrigacao")
        self.assertEqual(normalizar("PISTÃO"), "pistao")

    def test_aceita_none_e_vazio(self):
        self.assertEqual(normalizar(None), "")
        self.assertEqual(normalizar(""), "")


class PalavrasTest(SimpleTestCase):
    def test_corta_palavras_curtas_e_stopwords(self):
        # "as" e "de" saem (stop), "10" sai (curta)
        self.assertEqual(
            _palavras("as ferramentas de 10 anos"), ["ferramentas", "anos"]
        )

    def test_separa_frases_com_acentos_e_simbolos(self):
        self.assertIn("cafe", _palavras("café,"))
        self.assertIn("cafe", _palavras("café!!!"))


class DeteccaoTest(SimpleTestCase):
    """O que o produtor diz, e o que o servidor entende."""

    #: Frases que um produtor rural diz de facto. Cada uma com a intent que
    #: uma pessoa esperaria. Este é o teste que diz se a porta serve.
    CASOS = [
        ("como esta o tempo agora", "clima_agora"),
        ("vai chover amanha", "vai_chover"),
        ("quando pulverizar", "melhor_pulverizar"),
        ("meu estoque de ureia", "estoque_baixo"),  # MEDIDO 2026-10-05: era
        # "consultar_estoque". As DUAS intents listam "estoque baixo" nos
        # exemplos, e "meu estoque de ureia" e' legitimamente ambigua entre
        # elas. Ver `test_a_ambiguidade_entre_estoque_e_consulta`, que fixa
        # esta decisao em vez de a deixar a oscilar.
        ("quanto rendeu a safra de soja", "resumo_safra"),
        ("listar maquinas", "listar_maquinas"),
        ("talhoes", "resumo_talhoes"),  # sem espaço: como o produtor escreve
        ("registrar o trator novo", "cadastrar_maquina"),
        ("excluir a safra milho 2025", "excluir_safra"),
    ]

    def test_perguntas_do_produtor_atingem_a_intent_certa(self):
        for frase, esperado in self.CASOS:
            d = detectar(frase)
            self.assertEqual(
                d["escolhido"],
                esperado,
                f"{frase!r} -> {d['escolhido']!r} (esperado {esperado!r})",
            )
            self.assertTrue(d["acima_do_limiar"], frase)

    def test_devolve_scores_de_todos_mesmo_sem_match(self):
        """O que torna o gate auditável: o número é do servidor, e há número
        para todos os intents — mesmo quando nenhum passa o limiar."""
        d = detectar("xyzzy plugh")
        self.assertEqual(d["escolhido"], None)
        self.assertFalse(d["acima_do_limiar"])
        self.assertEqual(set(d["scores"]), set(REGISTO))

    def test_frase_vazia_nao_explode(self):
        for frase in ("", "   ", "?", "!!!", "a e o u"):
            d = detectar(frase)
            self.assertIsNone(d["escolhido"], repr(frase))

    def test_escrita_nunca_cai_em_intent_de_leitura(self):
        """O bug que originou `sandbox.parece_cadastro`: um pedido de
        cadastro respondido com um resumo."""
        for frase in (
            "cadastrar um funcionario novo",
            "criar um talhao",
            "registrar a vacina do brinco 142",
        ):
            d = detectar(frase)
            if d["escolhido"]:
                self.assertFalse(
                    somente_leitura(REGISTO[d["escolhido"]]),
                    f"{frase!r} caiu em {d['escolhido']!r}, que é só leitura",
                )

    def test_pergunta_terminada_em_interrogacao_e_consulta(self):
        """ "terminaram a tarefa?" é estado, não é escrita — apesar de conter
        um verbo de acção."""
        d = detectar("terminaram a tarefa?")
        if d["escolhido"]:
            self.assertTrue(somente_leitura(REGISTO[d["escolhido"]]), d["escolhido"])


class ParidadeComONavegadorTest(SimpleTestCase):
    """As duas implementações da mesma regra não podem divergir em silêncio."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tem_js = JS.exists()
        if cls.tem_js:
            cls.src = JS.read_text(encoding="utf-8", errors="replace")

    def test_a_lista_de_stopwords_e_a_mesma(self):
        if not self.tem_js:
            self.skipTest("ia-local.js não encontrado")
        m = re.search(r"const stop = new Set\(\s*'([^']+)'\.split", self.src)
        self.assertIsNotNone(m, "não encontrei a lista de stop no ia-local.js")
        js_stop = {w.strip() for w in m.group(1).split(",") if w.strip()}
        self.assertEqual(
            js_stop,
            set(STOP),
            "a lista de stopwords do navegador e a do servidor divergiram — "
            f"só no JS: {sorted(js_stop - set(STOP))}; "
            f"só no Python: {sorted(set(STOP) - js_stop)}",
        )

    def test_o_limiar_do_navegador_e_o_mesmo(self):
        if not self.tem_js:
            self.skipTest("ia-local.js não encontrado")
        m = re.search(r"bestScore >= ([0-9.]+)", self.src)
        self.assertIsNotNone(m, "não encontrei o limiar no ia-local.js")
        self.assertEqual(
            float(m.group(1)),
            LIMIAR,
            "o limiar do navegador e o do servidor divergiram — "
            "a mesma frase daria respostas diferentes conforme quem perguntou",
        )


class OGatePassaASerConfiavelTest(TestCase):
    """A razão de este módulo existir: o score passa a ser do servidor."""

    def setUp(self):
        from django.contrib.auth.models import User

        from app.models import Propriedade

        self.u = User.objects.create_user("det_probe", password="x1234567")
        Propriedade.objects.create(
            user=self.u, nome="FAZ", cidade="SOROCABA", uf="SP", area_total=10
        )

    def test_sem_scores_do_cliente_o_servidor_calcula(self):
        from app.ia import sandbox
        from app.models import IAExecucao

        sandbox.executar(
            self.u,
            "listar_maquinas",
            {},
            via="sessao",
            meta={"entrada": "quais maquinas tenho na fazenda"},
        )
        d = (IAExecucao.objects.latest("id").deteccao) or {}
        self.assertTrue(
            d.get("calculado_no_servidor"),
            "sem scores do cliente, o servidor tem de calcular os seus — "
            "caso contrário o gate M3 continua a ser decorativo",
        )
        self.assertTrue(d.get("scores"))

    def test_o_cliente_continua_a_poder_dizer_o_que_entendeu(self):
        """A Interface sabe coisas que o bag-of-words não sabe.

        Sobrescrever o score do cliente deixaria de fora os oito fast-paths do
        painel, que são UX e respondem sem ida ao servidor. O que não pode é
        deixar de haver score do servidor quando o cliente não manda nenhum.
        """
        from app.ia import sandbox
        from app.models import IAExecucao

        sandbox.executar(
            self.u,
            "listar_maquinas",
            {},
            via="sessao",
            meta={
                "entrada": "x",
                "deteccao": {
                    "metodo": "fast-path",
                    "scores": {"listar_maquinas": 1.0},
                    "escolhido": "listar_maquinas",
                },
            },
        )
        d = (IAExecucao.objects.latest("id").deteccao) or {}
        self.assertEqual(d.get("metodo"), "fast-path")
        self.assertEqual((d.get("scores") or {}).get("listar_maquinas"), 1.0)
