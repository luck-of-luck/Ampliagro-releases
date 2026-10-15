"""Impede que o dashboard volte a semear dado inventado.

Este nao e' um teste de "o codigo tem esta forma". E' um teste sobre O
DADO: o template nao pode conter uma serie de oito anos de produtividade
que nenhum produtor-produziu. O numero e' o contrato, nao a sintaxe.

A origem do defeito foi um preset (`custom-agua`, hoje removido) que trazia
historico de arroz e milho de 2017 a 2024 -- valores que nenhuma base de
dados continha. Um produtor de cafe via esses numeros no ecra com a mesma
authority que veria os seus. A semeadura passou a ter um preset so'
(`base-ia`), do produto; o resto nasce da mao do produtor ou da IA.
"""

import pathlib
import re
import unittest

TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "templates" / "index.html"

# Onde a logica do preset vive AGORA.
#
# MEDIDO 2026-10-05. Estas tres assercoes liam `TEMPLATE` e pediam
# `_filtrarParaProdutor` e `clonePresetWidgets`. O refactor que extraiu a
# logica da folha para `app/static/js/pagina-index.js` (carregado por
# `index.html:1714`) levou-as com ele: no template sao **zero** ocorrencias,
# no JS sao 4 e 6.
#
# Verificado antes de mexer: a proteccao sobreviveu ao refactor.
# `_filtrarParaProdutor` esta dentro dos 700 chars de `clonePresetWidgets`
# (L1987), e a string que o `demo-clean v11` usava para repor o preset cru
# nao esta no JS. O que falhava era o teste, nao o codigo.
#
# Esta constante e' separada da `TEMPLATE` de proposito: a classe de cima faz
# um teste de AUSENCIA de numeros, e juntar 12 000 linhas de JS ao texto
# poderia introduzir um numero que a fizesse falhar por razao errada.
JS_PAGINA = (
    pathlib.Path(__file__).resolve().parent.parent / "static" / "js" / "pagina-index.js"
)


class DashboardNaoSemeiaDadoInventado(unittest.TestCase):
    """Nenhum preset embutido pode trazer historico ou metrica de exemplo."""

    @classmethod
    def setUpClass(cls):
        cls.texto = TEMPLATE.read_text(encoding="utf-8")

    def test_preset_nao_declara_series_de_exemplo(self):
        """`var _sample*` pode existir, mas nunca com dados dentro."""
        decls = re.findall(r"var _sample(?:Prod|Bar)\d*\s*=\s*(\{.*?\});", self.texto)
        for d in decls:
            self.assertEqual(
                d.strip(),
                "{}",
                f"Um _sample* voltou a levar dados: {d[:120]}",
            )

    def test_preset_nao_injecta_serie_em_widget_sem_metrica(self):
        """O injector que fabricava a curva tem de ser um no-op."""
        injecoes = [
            l.strip() for l in self.texto.splitlines() if "for(var k in _sample" in l
        ]
        for l in injecoes:
            self.assertNotIn(
                "w[k]=",
                l,
                f"A atribuicao que fabricava o dado voltou: {l[:120]}",
            )

    def test_historico_de_oito_anos_nao_esta_hardcoded(self):
        """A serie 3200..4100 kg/ha foi a primeira coisa vista no ecra."""
        for valor in ("3200", "3400", "3350", "4100"):
            with self.subTest(valor=valor):
                # so interessa se for uma serie de dados, nao um qualquer
                # uso do numero no layout
                series = re.findall(rf"{valor}\s*,\s*\d+\s*,\s*\d+", self.texto)
                self.assertEqual(
                    series, [], f"Serie com {valor} ainda hardcoded: {series[:2]}"
                )

    def test_widgets_sem_dado_ficam_sem_dado(self):
        """O injector tem de continuar a existir mas a nao fazer nada.

        Se alguem apagar o bloco inteiro, este teste ainda passa -- e isso
        esta bem. O que nao pode e' o bloco voltar a escrever.
        """
        for l in self.texto.splitlines():
            if "repairedPk" in l:
                self.assertNotIn("w[k]=", l, f"repairedPk voltou a escrever: {l[:120]}")


class RótuloNaoDesmenteSobreOLavour(unittest.TestCase):
    """O titulo tambem e' dado.

    Um produtor de cafe acordou com "PRODUTIVIDADE DE ARROZ" e "AREA MILHO
    (FAZENDA)" no ecra. Tirar o numero inventado nao resolvia: o titulo
    continuava a descrever uma lavoura que a pessoa nao tem, e o rasto e'
    pior que o numero -- fica a suggestir que o sistema so sabe falar de
    arroz.
    """

    @classmethod
    def setUpClass(cls):
        # Template **e** JS. A guarda tem de estar num dos dois: se um dia o
        # refactor a puser noutro ficheiro, o teste continua a perguntar
        # "existe?" em vez de acahar num caminho que ja morreu.
        cls.texto = (
            TEMPLATE.read_text(encoding="utf-8")
            + "\n"
            + JS_PAGINA.read_text(encoding="utf-8")
        )

    def test_preset_nao_declara_culturas_fixas(self):
        """O filtro tem de existir E ser aplicado onde o preset e' lido."""
        self.assertIn("_filtrarParaProdutor", self.texto)

    def test_filtro_cobre_o_ponto_de_leitura(self):
        """Filtrar so na semeadura nao chega: um preset guardado antes da
        mudanca volta a trazer o arroz. O filtro tem de estar no
        `clonePresetWidgets`, por onde tudo e' lido."""
        i = self.texto.find("function clonePresetWidgets")
        self.assertNotEqual(i, -1, "clonePresetWidgets desapareceu")
        corpo = self.texto[i : i + 700]
        self.assertIn(
            "_filtrarParaProdutor",
            corpo,
            "clonePresetWidgets nao filtra: um preset antigo traz o arroz de volta",
        )

    def test_reparacao_nao_restaura_a_versao_crua(self):
        """O bloco 'demo-clean v11' existia para repor o hardcoded cru — e
        era ele que desfazia o filtro. Tem de comparar com a versao ja
        filtrada."""
        self.assertNotIn(
            "JSON.stringify(_allHardcoded['custom-agua'])",
            self.texto,
            "A reparacao voltou a comparar com o preset cru, o que repõe arroz e milho",
        )


if __name__ == "__main__":
    unittest.main()
