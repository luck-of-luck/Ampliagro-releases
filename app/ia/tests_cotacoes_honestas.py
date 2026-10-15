"""Cotações: um preço sem fonte é um defeito, não uma escolha.

Este módulo foi reescrito depois de se descobrir que servia preços
sorteados com `random.uniform` — soja 130-160, café 900-1100 — carimbados
`fonte: "real"`. O carimbo comparava o resultado com um SEGUNDO sorteio, e
dois sorteios nunca coincidem: em 500 tentativas, zero. Ou seja, "real" era
quase sempre o que saía, por cima de ruído.

Um produtor que decide venda por aquele número não tinha como saber que era
ruído. É a mesma classe do bug do arroz/milho no dashboard, e pior: ali via-se
a curva, aqui o número isolado com uma casa decimal parece um preço.
"""

import ast
import pathlib
import unittest

from django.test import TestCase

from app.services.cotacoes import CotacoesService

FICHEIRO = pathlib.Path(__file__).resolve().parent.parent / "services" / "cotacoes.py"


def codigo_sem_comentarios() -> str:
    """Só o código, sem docstrings nem comentários.

    O docstring deste serviço nomeia precisamente os defeitos que apagou
    (`random.uniform`, `_fetch_b3_mock`, a comparação). Um teste que lesse o
    ficheiro inteiro apanharia o próprio aviso a dizer "falha" — e um
    teste que falha por causa da explicação é um teste que não serve para
    nada.
    """
    arvore = ast.parse(FICHEIRO.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(
            no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if (
                ast.get_docstring(no) is not None
                and no.body
                and isinstance(no.body[0], ast.Expr)
                and isinstance(no.body[0].value, ast.Constant)
            ):
                no.body.pop(0)
    return ast.unparse(arvore)


class CotacoesNaoInventamPreco(unittest.TestCase):
    def test_modulo_nao_sorteia_preco(self):
        """`random` saiu do ficheiro. Um `random.uniform` aqui volta a
        fabricar cotação, e o carimbo de proveniência passa a mentir com a
        mesma Ease de antes."""
        arvore = ast.parse(FICHEIRO.read_text(encoding="utf-8"))
        imports = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                imports.update(a.name for a in no.names)
            elif isinstance(no, ast.ImportFrom):
                imports.add(no.module or "")
        self.assertNotIn(
            "random",
            imports,
            "cotacoes voltou a importar random: volta a fabricar preço",
        )

    def test_nao_existe_mock_que_devolva_numeros(self):
        """Os `_fetch_*_mock` desapareceram. Se alguém os reintroduzir a
        devolver números, o teste apanha."""
        codigo = codigo_sem_comentarios()
        self.assertNotIn("_fetch_b3_mock", codigo)
        self.assertNotIn("_fetch_conab_mock", codigo)

    def test_proveniencia_e_calculada_nao_comparada(self):
        """A comparação com um segundo sorteio foi a causa do carimbo
        partido. `fonte` tem de ser derivada de haver preço, não de
        comparar com outra chamada."""
        codigo = codigo_sem_comentarios()
        self.assertNotIn(
            "_fetch_b3_mock",
            codigo,
            "A proveniencia voltou a ser comparada com um segundo sorteio",
        )
        self.assertIn(
            "tem_preco",
            codigo,
            "A fonte tem de ser derivada de haver preco, nao de comparar chamadas",
        )


class CotacoesSemFonteDevolveNone(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.addCleanup(cache.clear)

    def test_sem_fonte_nao_ha_preco_numerico(self):
        dados = CotacoesService.get_cotacoes()

        precos = [
            v.get("preco") for bloco in ("b3", "conab") for v in dados[bloco].values()
        ]
        numericos = [p for p in precos if isinstance(p, (int, float)) and p is not None]
        self.assertEqual(numericos, [], f"Preco numerico sem fonte: {numericos}")

    def test_fonte_diz_indisponivel(self):
        dados = CotacoesService.get_cotacoes()
        self.assertEqual(dados["fonte"], "indisponivel")
        self.assertTrue(dados["aviso"], "fonte indisponivel sem aviso ao produtor")

    def test_preco_none_vem_com_motivo(self):
        """`None` sozinho é um bugreport. `None` com motivo é uma resposta."""
        dados = CotacoesService.get_cotacoes()
        for bloco in ("b3", "conab"):
            for commodity, v in dados[bloco].items():
                self.assertIsNone(
                    v.get("preco"), f"{bloco}.{commodity} tem preco sem fonte"
                )
                self.assertTrue(
                    v.get("motivo"),
                    f"{bloco}.{commodity} sem preco e sem motivo",
                )

    def test_as_chaves_mantem_se_para_o_frontend(self):
        """As chaves existem para o frontend não rebentar com `undefined`,
        mas o VALOR é None — nunca 0, porque 0 é um preço, e um preço
        impossível."""
        dados = CotacoesService.get_cotacoes()
        for commodity in ("soja", "milho", "cafe", "boi_gordo"):
            self.assertIn(commodity, dados["b3"])

    def test_duas_chamadas_dao_o_mesmo(self):
        """Um preço que muda a cada chamada é ruído. Sem fonte, o resultado
        tem de ser estável — não por caching, mas por não ter nada de
        aleatório dentro."""
        a = CotacoesService.get_cotacoes()
        from django.core.cache import cache

        cache.clear()
        b = CotacoesService.get_cotacoes()
        self.assertEqual(
            a["b3"],
            b["b3"],
            "Duas chamadas deram b3 diferente: ha aleatoriedade a servir de preco",
        )
