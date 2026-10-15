"""Sem dado do IBGE, não há lavoura inventada.

`/api/ibge-proxy/` tinha um caminho de fallback que servia
`FALLBACK_METRICS`: 210 culturas com produção, área, produtividade e receita
escritas à mão, mais um `DEFAULT_METRICS` que dava 1 200 t / 30 ha / R$ 900K
a qualquer cultura não mapeada. E ainda por cima `_gen_fallback_history`,
que sorteava cinco anos de curva (`random.Random(cultura_id + "_hist")`,
±15%) em cima desses números.

A agravante de onde isto estava: o fallback dispara quando o IBGE falha. Ou
seja, no pior momento possível — quando a fonte real está em baixo, e é
exatamente quando o produtor mais precisa de saber que o número não é real.

É a mesma classe do bug do arroz/milho no dashboard, que já foi corrigido.
Ficou este.
"""

from unittest import TestCase

from app.api.views.utils import (
    _gen_fallback_history,
    _gen_fallback_history_antigo,
    _gen_fallback_metrics,
)


class FallbackNaoFabricaLavoura(TestCase):
    def test_metricas_de_fallback_vazias(self):
        """Qualquer cultura, mapeada ou não, dá lista vazia."""
        for cultura in (
            "cultura-soja",
            "cultura-milho",
            "cultura-arroz",
            "cultura-uma-cultura-que-nao-existe",
        ):
            with self.subTest(cultura=cultura):
                self.assertEqual(
                    _gen_fallback_metrics(cultura),
                    [],
                    "Fallback voltou a servir métrica",
                )

    def test_historico_de_fallback_vazio(self):
        """Cinco anos de curva sorteada é o que se está a remover."""
        for cultura in ("cultura-soja", "cultura-milho"):
            with self.subTest(cultura=cultura):
                self.assertEqual(
                    _gen_fallback_history(cultura), {}, "Histórico voltou a ser gerado"
                )

    def test_a_view_nao_serve_fallback(self):
        """A função vazia não chega: a view tem de dizer `indisponivel` e
        dar o motivo, para o frontend mostrar "sem dado" em vez de uma
        lista vazia sem explicação."""
        import inspect

        from app.api.views import cultures

        fonte = inspect.getsource(cultures)
        # remove os comentários: a explicação nomeia o defeito removido
        codigo = "\n".join(
            l for l in fonte.splitlines() if not l.strip().startswith("#")
        )
        self.assertNotIn(
            "_gen_fallback_metrics(cultura_id)",
            codigo,
            "A view voltou a chamar o gerador de métricas inventadas",
        )
        self.assertNotIn(
            "_gen_fallback_history(cultura_id)",
            codigo,
            "A view voltou a chamar o gerador de curva sintética",
        )
        self.assertIn(
            'result["source"] = "indisponivel"',
            fonte,
            "A resposta sem dado tem de se identificar como indisponível",
        )

    def test_funcao_antiga_levanta_em_vez_de_servir(self):
        """A versão antiga ficou no ficheiro como aviso, mas tem de estar
        desligada. Uma função que levanta é melhor do que uma que funciona:
        quem a chamar descobre logo, em vez de servir ruído."""
        with self.assertRaises(RuntimeError):
            _gen_fallback_history_antigo("cultura-soja")


class DadosDeExemploNaoSaoServidos(TestCase):
    def test_o_ficheiro_de_210_culturas_existe_mas_nao_e_servido(self):
        """`fallback_data.py` continua no repositório com 210 lavouras
        fictícias. Apagá-lo seria correto, mas deixá-lo com um aviso é o que
        impede que alguém o religue sem se aperceber — e o teste garante
        que, mesmo que alguém o importe, a view não o serve."""
        import pathlib

        from app.api import fallback_data

        caminho = pathlib.Path(fallback_data.__file__)
        texto = caminho.read_text(encoding="utf-8")

        # As 210 lavouras lá estão (é isso que o ficheiro é).
        self.assertIn("FALLBACK_METRICS", texto)
        # Mas a view não o chama: coberto por
        # `test_a_view_nao_serve_fallback` acima.
        self.assertIn("DEFAULT_METRICS", texto)
