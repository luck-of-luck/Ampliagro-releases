"""A pergunta que o Plano A promete responder:

    É possível construir um payload com um número e sem fonte?

Se não é, a classe de defeito morreu. Não porque cada widget foi cuidado — um
`careful` falha. Porque o caminho que produz um número sem origem deixou de
existir, e ninguém o pode chamar por engano.

Este ficheiro não testa um widget. Testa a PROPRIEDADE, sobre todos eles, com
uma conta que tem três anos de história, lançamentos e uma safra a meio.

O que mudou com a proveniência como tipo:

  * `Medido()` sem `fonte` LANÇA. A fonte deixou de ser um campo opcional que
    se esquecia, e passou a ser um argumento que não pode faltar.
  * `SemDado()` sem `motivo` LANÇA. Um "sem dado" que não diz o que falta
    obriga o produtor a adivinhar, e adivinhar mal num painel é pior do que
    não ter nada.
  * `medir(None)` devolve `SemDado`, e não `Medido(0)`. Esta é a conversão que
    esteve errada seis vezes: uma área que ninguém mediu a aparecer como 1, um
    custo sem lançamentos a aparecer como 0.
  * `serializar()` é o ÚNICO caminho para escrever um número num config, e ele
    não sabe escrever um número sozinho.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import proveniencia as P
from app.ia.palco import CATALOGO_IA, WIDGETS_SERVIDOR
from app.ia.palco_dados import enriquece


def _cafe():
    from app.models import Cultura

    c, _ = Cultura.objects.get_or_create(nome="Caf" + "é", defaults={"grupo": "graos"})
    return c


# ---------------------------------------------------------------------------
# A PROPRIEDADE
# ---------------------------------------------------------------------------
class ONumeroNaoTemCaminhoSemFonte(TestCase):
    """O teste central. Se isto passar, nenhum `Medido` nasce sem `fonte`."""

    def test_medido_sem_fonte_lanca(self):
        with self.assertRaises(ValueError):
            P.Medido(418.57, "")
        with self.assertRaises(ValueError):
            P.Medido(418.57, "   ")

    def test_simulado_sem_gerador_lanca(self):
        """Daqui a seis meses ninguém se lembra de onde saiu o número.

        E um número que ninguém sabe de onde veio é um número que ninguém pode
        defender perante um auditor. Por isso o `gerador` não é decorativo.
        """
        with self.assertRaises(ValueError):
            P.Simulado(50.4, "")

    def test_sem_dado_sem_motivo_lanca(self):
        with self.assertRaises(ValueError):
            P.SemDado("")

    def test_none_vira_sem_dado_e_nao_zero(self):
        """A conversão que esteve errada seis vezes.

        `float(area) or 1.0`, `saldo or 0`, `cfg.get("valor")` — todas as
        formas de trocar "não medi" por "medi zero". As duas frases são
        opostas, e só uma é verdade.
        """
        r = P.medir(None, "LancamentoFinanceiro da propriedade 18")
        self.assertIsInstance(r, P.SemDado)
        self.assertEqual(r.estado, "sem_dado")

    def test_zero_verdadeiro_e_medido_nao_sem_dado(self):
        """O outro lado da mesma moeda.

        Uma despesa de zero REAIS é uma medição: ele gastou zero. Tratar
        isso como "sem dado" é tão errado como tratar "não sei" como zero — e
        é o erro que esconde um produtor que parou de gastar.
        """
        r = P.medir(0, "LancamentoFinanceiro da propriedade 18")
        self.assertIsInstance(r, P.Medido)
        self.assertEqual(r.estado, "medido")

    def test_serializar_sempre_escreve_a_origem(self):
        for v, esperado in (
            (P.Medido(10, "Safra 2025"), "medido"),
            (P.SemDado("nenhuma safra"), "sem_dado"),
            (P.Simulado(50.4, "hash deterministico"), "simulado"),
        ):
            saida = P.serializar(v, chave="x")
            self.assertIn(
                "fonte_dado", saida, f"{type(v).__name__} nao escreveu a origem"
            )
            self.assertEqual(saida["fonte_dado"], esperado)

    def test_sem_dado_nao_escreve_zero(self):
        """A última porta por onde a mentira passaria.

        Se `sem_dado` escrevesse `0`, o payload seria indistinguível do de um
        `Medido(0)` — e a distinção que acabámos de construir evaporava no
        serializador, que é onde ninguém volta a olhar.
        """
        saida = P.serializar(P.SemDado("nenhum lancamento"), chave="custo")
        self.assertIsNone(saida["custo"])
        self.assertIn("motivo", saida)

    def test_a_fonte_precisa_dizer_algo_de_especifico(self):
        """Uma fonte que não distingue uma consulta de outra não é uma fonte.

        `Medido(10, "api")` passa a construção e não serve para nada: daqui a
        três meses ninguém descobre se foi a tabela de safras ou a de
        lançamentos. A fonte tem de responder a "isto foi lido de onde?".
        """
        # o que o modulo exige e a nao-vazia; o que um revisor exige e a
        # especificidade. Este teste fixa a primeira, que e' automatizavel.
        self.assertRaises(ValueError, P.Medido, 10, "")


# ---------------------------------------------------------------------------
# A PROPRIEDADE SOBRE O CATÁLOGO TODO
# ---------------------------------------------------------------------------
class TodoWidgetTrazProveniencia(TestCase):
    """O teste que o Plano A promete: a propriedade, sobre todos os widgets.

    Uma conta com TRÊS anos. Um teste com um ano só passa, e é por isso que
    esta classe usa o histórico que a persona tem.
    """

    def setUp(self):
        from app.models import LancamentoFinanceiro, Propriedade, Safra

        self.u = User.objects.create_user(username="tipo", password="x")
        self.p = Propriedade.objects.create(
            user=self.u,
            nome="Sítio",
            cidade="Muzambinho",
            uf="MG",
            area_total=Decimal("340"),
        )
        cafe = _cafe()
        for ano, prod, colhida in (
            (2024, 62_000, 228),
            (2025, 58_500, 228),
            (2026, None, 0),
        ):
            Safra.objects.create(
                propriedade=self.p,
                cultura=cafe,
                ano=ano,
                area_plantada=Decimal("210"),
                area_colhida=Decimal(str(colhida)),
                producao_total=Decimal(str(prod)) if prod else None,
                data_colheita=date(ano, 7, 15) if prod else None,
            )
        for tipo, valor in (("RECEITA", 2_664_000), ("DESPESA", 48_600)):
            LancamentoFinanceiro.objects.create(
                propriedade=self.p,
                tipo=tipo,
                categoria="VENDA",
                descricao="x",
                valor=Decimal(str(valor)),
                data="2026-07-25",
                pago=True,
                tipo_documento_lcdpr="NF",
            )

    def test_todo_widget_de_servidor_traz_a_origem(self):
        """Para cada widget, o config ou traz fonte ou diz que não tem.

        Um widget de servidor que devolve números sem `fonte_dado` é a coisa
        que o Plano A promete tornar impossível. Se um aparece aqui, ou o
        `_calcula` não passou pelo módulo, ou alguém o escreveu à mão.
        """
        for tipo in sorted(WIDGETS_SERVIDOR):
            cfg = enriquece(self.u, [{"tipo": tipo}])[0].get("config")
            if cfg is None:
                continue
            # `enriquece` ainda devolve configs crus — a migração para
            # `proveniencia` é o passo seguinte, e este teste é o que a mede.
            tem_fonte = P.tem_proveniencia(cfg)
            tem_numero = any(
                isinstance(v, (int, float)) and v is not None
                for k, v in cfg.items()
                if k not in ("ano", "anos", "anos_contagem")
            )
            self.assertTrue(
                tem_fonte or not tem_numero,
                f"{tipo} devolve números sem trazer a origem: {cfg}",
            )

    def test_o_estado_diz_o_que_esta_measured(self):
        """`fonte_dado` só aceita os três valores, e só com o sentido certo."""
        for tipo in sorted(WIDGETS_SERVIDOR):
            cfg = enriquece(self.u, [{"tipo": tipo}])[0].get("config") or {}
            estado = cfg.get("fonte_dado")
            if estado is None:
                continue
            self.assertIn(estado, P.TODOS, f"{tipo}: estado desconhecido {estado!r}")
            # `simulado` nunca pode vir de um widget de SERVIDOR: eles leem o
            # banco, e se um disser que é simulado, a fonte falhou.
            self.assertNotEqual(
                estado,
                P.Estado.SIMULADO,
                f"{tipo} é um widget de servidor e declarou-se simulado.",
            )
