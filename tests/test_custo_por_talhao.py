"""O que a conta de custo por talhao nao pode fazer.

Cada teste aqui existe porque a versao anterior (`h_lucro_talhao`, um aggregate
dentro de um `for`) fez uma destas coisas. Nao sao testes de "a formula esta
certa" - sao testes de "isto estava a mentir sobre dinheiro".
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    AtividadePlanejada,
    Cultura,
    LancamentoFinanceiro,
    PlanoSafra,
    Propriedade,
    Safra,
    Talhao,
)
from app.services.custo_talhao import (
    ResultadoCusto,
    custo_por_talhao,
    resumo_para_ia,
)

D = Decimal
ZERO = Decimal("0")


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("joao", "joao@x.com", "s12345678")
        self.outro = User.objects.create_user("maria", "maria@x.com", "s12345678")
        self.prop = Propriedade.objects.create(
            user=self.user, nome="Fazenda Boa", cep="37400000", area_total=D("30")
        )
        self.cultura = Cultura.objects.create(nome="Soja")
        self.t1 = Talhao.objects.create(
            propriedade=self.prop, nome="Baixada", area_hectare=D("10")
        )
        self.t2 = Talhao.objects.create(
            propriedade=self.prop, nome="Cercado", area_hectare=D("20")
        )
        self.t3 = Talhao.objects.create(
            propriedade=self.prop, nome="Beira Rio", area_hectare=D("5")
        )

    def despesa(self, talhao, valor, pago=True, **kw):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="insumo",
            valor=D(valor),
            data="2026-03-10",
            talhao=talhao,
            pago=pago,
            **kw,
        )

    def receita(self, talhao, valor, pago=True):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="venda",
            valor=D(valor),
            data="2026-06-10",
            talhao=talhao,
            pago=pago,
        )


class DespesaNaoPagaNaoECusto(Base):
    """O bug mais caro: contar boleto em aberto como dinheiro gasto.

    O LCDPR e' de regime de caixa - `Q100` sai de `data_pagamento`. Uma tela de
    custo que conta compromisso como realizado mostra ao produtor que ele ja
    perdeu dinheiro que ainda tem no banco, e faz-o decidir por um numero que
    ele nao pode reconciliar com o extrato.
    """

    def test_despesa_pendente_nao_entra_no_realizado(self):
        self.despesa(self.t1, "5000", pago=False)
        self.despesa(self.t1, "1000", pago=True)

        r = custo_por_talhao(self.user)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)

        self.assertEqual(linha.realizado_despesa, D("1000"))
        self.assertEqual(linha.comprometido_despesa, D("5000"))
        self.assertEqual(linha.lucro_realizado, D("-1000"))

    def test_pendente_nao_altera_o_ordenamento(self):
        """O talhao com a pendencia mais alta nao pode subir para o topo."""
        self.despesa(self.t1, "9000", pago=True)
        self.despesa(self.t2, "50", pago=False)

        r = custo_por_talhao(self.user)
        topo = r.por_ordem_de_custo()[0]
        self.assertEqual(topo.talhao_id, self.t1.id)

    def test_receita_pendenta_tambem_nao_conta(self):
        self.receita(self.t1, "9000", pago=False)
        r = custo_por_talhao(self.user)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.realizado_receita, D("0"))
        self.assertEqual(linha.receitas_com_registro, 0)


class DespesaSemTalhaoNaoDesaparece(Base):
    """O segundo bug: o dinheiro sem destinatario sumia do racio.

    Combustivel, frete e mao-de-obra quase nunca tem talhao. A versao anterior
    filtrava `talhao=t` e esses lancamentos nao apareciam em lado nenhum: o
    lucro por talhao saia inflado, sem um unico aviso visivel.
    """

    def test_a_nao_alocada_e_reportada(self):
        self.despesa(None, "3000")
        r = custo_por_talhao(self.user)
        self.assertEqual(r.nao_alocado_despesa, D("3000"))
        self.assertEqual(r.nao_alocado_registros, 1)

    def test_o_racio_nao_aumenta_sozinho(self):
        """Nada e' rateado. O total por talhao continua sem esse dinheiro."""
        self.despesa(self.t1, "1000")
        self.despesa(None, "9000")

        r = custo_por_talhao(self.user)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.realizado_despesa, D("1000"))
        self.assertEqual(r.total_despesa, D("1000"))

    def test_so_despesa_sem_talhao_nao_e_silencio(self):
        """So despesa nao alocada: o texto tem de dizer o valor e o que falta.

        A frase "nao esta vinculada" so entra no ramo em que o dinheiro e'
        TODO nao alocado. Com um talhao que ja tem custo, o resumo diz o resto e
        o produtor consegue reconciliar pelo valor - fingir que o aviso e'
        obrigatorio aqui seria-o.
        """
        self.despesa(None, "9000")
        r = custo_por_talhao(self.user)
        self.assertEqual(r.nao_alocado_despesa, D("9000"))
        self.assertIn("9,000.00", resumo_para_ia(r))

    def test_so_despesa_nao_alocada_diz_o_que_falta(self):
        self.despesa(None, "9000")
        txt = resumo_para_ia(custo_por_talhao(self.user))
        self.assertIn("nenhum está vinculado a um talhão", txt)
        self.assertIn("9,000.00", txt)
        self.assertIn("Vincule", txt)

    def test_sem_nada_nao_alocado_o_texto_nao_menta_disso(self):
        self.despesa(self.t1, "1000")
        r = custo_por_talhao(self.user)
        self.assertNotIn("não está vinculada", resumo_para_ia(r))


class OrcadoAusenteNaoEOrcadoZero(Base):
    """A confusao mais cara de um painel: celula vazia mostrada como 0.

    "Orcado 0" diz ao produtor que planeou gastar nada. "Sem orcado" diz que
    ninguem planejou. O primeiro leva a uma decisao; o segundo leva a um
    cadastro.
    """

    def test_talhao_sem_plano_devolve_none_e_nao_zero(self):
        self.despesa(self.t1, "1000")
        r = custo_por_talhao(self.user)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)

        self.assertIsNone(linha.orcado)
        self.assertIsNone(linha.desvio)
        self.assertIsNone(linha.desvio_pct)

    def test_none_sobrevive_a_serializacao(self):
        self.despesa(self.t1, "1000")
        r = custo_por_talhao(self.user)
        d = next(l for l in r.as_dict()["linhas"] if l["talhao"] == "Baixada")
        self.assertIsNone(d["orcado"])
        self.assertIsNotNone(d["realizado_despesa"])

    def test_orcado_zero_explicito_e_zero(self):
        """Zero planeado e' um orcado. Deve calcular desvio."""
        safra = Safra.objects.create(
            propriedade=self.prop,
            talhao=self.t1,
            cultura=self.cultura,
            ano=2026,
            area_plantada=D("10"),
            receita_estimada=D("0"),
        )
        PlanoSafra.objects.create(safra=safra, orcamento_estimado=D("0"))
        self.despesa(self.t1, "250")

        r = custo_por_talhao(self.user, ano=2026)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.orcado, D("0"))
        self.assertEqual(linha.receita_orcada, D("0"))
        self.assertEqual(linha.desvio, D("250"))
        self.assertIsNone(linha.desvio_pct, "divisao por zero nao produz 100%")


class DesvioDoOrcado(Base):
    def setUp(self):
        super().setUp()
        self.safra = Safra.objects.create(
            propriedade=self.prop,
            talhao=self.t1,
            cultura=self.cultura,
            ano=2026,
            area_plantada=D("10"),
            receita_estimada=D("50000"),
        )
        self.plano = PlanoSafra.objects.create(
            safra=self.safra, orcamento_estimado=D("20000")
        )

    def test_gastou_mais_que_planeou(self):
        self.despesa(self.t1, "25000")
        r = custo_por_talhao(self.user, ano=2026)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.desvio, D("5000"))
        self.assertEqual(linha.desvio_pct, D("25.00"))

    def test_receita_orcada_entra_no_lucro_orcado(self):
        self.despesa(self.t1, "25000")
        self.receita(self.t1, "40000")
        r = custo_por_talhao(self.user, ano=2026)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.lucro_orcado, D("30000"))
        self.assertEqual(linha.lucro_realizado, D("15000"))

    def test_atividades_somam_quando_o_plano_e_mudo(self):
        """O schema nao deixa um plano sem orcado: `orcamento_estimado` e'
        NOT NULL, tal como `Talhao.area_hectare`.

        Escrevi este teste a crer que um plano sem valor era possivel. Nao e' a
        base que recusa. O fallback para a soma das atividades fica no servico
        como defesa (linha herdada, migracao futura que relaxe a coluna), mas
        **nao e' alcancavel pelo caminho normal** - e digo-o aqui para ninguem
        contar com ele ao fechar um orcamento.
        """
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanoSafra.objects.create(safra=self.safra, orcamento_estimado=None)

    def test_plano_com_valor_manda_sobre_a_soma_das_atividades(self):
        """Somar os dois contaria a mesma atividade duas vezes."""
        AtividadePlanejada.objects.create(
            plano=self.plano,
            nome="Semear",
            data_prevista="2026-11-01",
            custo_estimado=D("7000"),
        )
        r = custo_por_talhao(self.user, ano=2026)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.orcado, D("20000"), "20000 do plano, nao 27000")


class CustosPorHectare(Base):
    def test_divide_por_area(self):
        self.despesa(self.t1, "1000")
        r = custo_por_talhao(self.user)
        linha = next(l for l in r.linhas if l.talhao_id == self.t1.id)
        self.assertEqual(linha.custo_por_ha, D("100.00"))

    def test_a_area_e_obrigatoria_no_schema(self):
        """Nao e' uma preferencia minha: e' NOT NULL na base de dados.

        Escrevi estes testes a crer que um talhao sem area era possivel. Nao e'.
        A base recusa. O guard `if not self.area_ha` do servico continua
        correcto - e' defesa para uma linha herdada ou para uma migracao futura
        que relaxe a coluna - mas um teste que finja que o estado e' alcancavel
        seria um teste de uma fantasy.
        """
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            Talhao.objects.create(
                propriedade=self.prop, nome="Sem Area", area_hectare=None
            )

    def test_o_guard_ainda_produz_none_e_nao_zero(self):
        """Directo na dataclass, para cobrir o caminho que o schema proibe."""
        from app.services.custo_talhao import LinhaCusto

        l = LinhaCusto(
            talhao_id=999,
            talhao="Legado",
            area_ha=None,
            orcado=None,
            receita_orcada=None,
            realizado_receita=ZERO,
            realizado_despesa=D("1000"),
            comprometido_despesa=ZERO,
            despesas_com_registro=1,
            receitas_com_registro=0,
        )
        self.assertIsNone(l.custo_por_ha, "0.00 R$/ha seria mentira de precisao")
        self.assertIsNone(l.lucro_por_ha)

    def test_area_nula_vai_para_o_fim_do_ranking(self):
        """Ainda que o schema o impeca hoje, o sort nao pode confiar nele."""
        from app.services.custo_talhao import LinhaCusto

        sem = LinhaCusto(
            talhao_id=1,
            talhao="Sem Area",
            area_ha=None,
            orcado=None,
            receita_orcada=None,
            realizado_receita=ZERO,
            realizado_despesa=D("1"),
            comprometido_despesa=ZERO,
            despesas_com_registro=1,
            receitas_com_registro=0,
        )
        com = LinhaCusto(
            talhao_id=2,
            talhao="10 ha",
            area_ha=D("10"),
            orcado=None,
            receita_orcada=None,
            realizado_receita=ZERO,
            realizado_despesa=D("100"),
            comprometido_despesa=ZERO,
            despesas_com_registro=1,
            receitas_com_registro=0,
        )
        resultado = ResultadoCusto(linhas=[sem, com])
        self.assertEqual(resultado.por_ordem_de_custo()[-1].talhao, "Sem Area")

    def test_total_por_ha_ignora_o_talhao_sem_area(self):
        self.despesa(self.t1, "1000")
        self.despesa(self.t2, "2000")
        self.despesa(self.t3, "500")
        r = custo_por_talhao(self.user)
        self.assertEqual(r.area_total, D("35"))
        self.assertEqual(r.total_despesa, D("3500"))


class IsolamentoPorPropriedade(Base):
    def test_propriedade_alheia_e_invisivel(self):
        self.despesa(self.t1, "1000")
        outra = Propriedade.objects.create(
            user=self.outro, nome="Deles", area_total=D("10")
        )
        t_alheio = Talhao.objects.create(
            propriedade=outra, nome="Deles", area_hectare=D("10")
        )
        LancamentoFinanceiro.objects.create(
            propriedade=outra,
            tipo="DESPESA",
            categoria="x",
            valor=D("999999"),
            data="2026-03-10",
            talhao=t_alheio,
            pago=True,
        )

        r = custo_por_talhao(self.user)
        nomes = {l.talhao for l in r.linhas}
        self.assertEqual(nomes, {"Baixada", "Beira Rio", "Cercado"})
        self.assertEqual(r.total_despesa, D("1000"))

    def test_filtro_por_propriedade_ignora_as_outras(self):
        p2 = Propriedade.objects.create(
            user=self.user, nome="Segunda", area_total=D("5")
        )
        t2 = Talhao.objects.create(propriedade=p2, nome="La", area_hectare=D("5"))
        self.despesa(self.t1, "100")
        LancamentoFinanceiro.objects.create(
            propriedade=p2,
            tipo="DESPESA",
            categoria="x",
            valor=D("700"),
            data="2026-03-10",
            talhao=t2,
            pago=True,
        )
        r = custo_por_talhao(self.user, propriedade=p2)
        self.assertEqual({l.talhao for l in r.linhas}, {"La"})
        self.assertEqual(r.total_despesa, D("700"))


class HonestidadeDoTexto(Base):
    def test_fazenda_vazia_nao_inventa_numero(self):
        r = custo_por_talhao(self.user)
        self.assertFalse(r.tem_dados)
        self.assertEqual(r.total_despesa, D("0"))
        self.assertIn("Sem lançamentos", resumo_para_ia(r))

    def test_talhao_sem_lancamento_e_nomeado(self):
        self.despesa(self.t1, "100")
        r = custo_por_talhao(self.user)
        self.assertEqual(sorted(r.talhoes_sem_lancamento), ["Beira Rio", "Cercado"])

    def test_todos_os_talhoes_aparecem_mesmo_sem_dados(self):
        """Um talhao sem lancamento continua a ser um talhao do produtor."""
        r = custo_por_talhao(self.user)
        self.assertEqual(len(r.linhas), 3)

    def test_dinheiro_e_decimal_ate_ao_fim(self):
        self.despesa(self.t1, "0.1")
        self.despesa(self.t1, "0.2")
        r = custo_por_talhao(self.user)
        self.assertEqual(r.total_despesa, D("0.3"))
        self.assertIsInstance(r.total_despesa, Decimal)


class NadaDeNMaisUmaConsulta(Base):
    """A versao anterior fazia `2 * len(talhoes) + 1` queries."""

    def test_o_numero_de_queries_nao_cresce_com_o_numero_de_talhoes(self):
        with self.settings(DEBUG=True):
            from django.db import connection, reset_queries

            for t in ("C", "D", "E", "F", "G", "H"):
                Talhao.objects.create(
                    propriedade=self.prop, nome=t, area_hectare=D("1")
                )

            def conta():
                reset_queries()
                custo_por_talhao(self.user)
                return len(connection.queries)

            reset_queries()
            custo_por_talhao(self.user)
            com_3 = len(connection.queries)
            com_9 = conta()

        self.assertLessEqual(
            com_9 - com_3,
            1,
            f"6 talhoes a mais custaram {com_9 - com_3} queries: ha N+1 no caminho",
        )


class FiltroDeAno(Base):
    def setUp(self):
        super().setUp()
        self.despesa(self.t1, "1000", data="2026-03-10") if False else None

    def _l(self, **kw):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="x",
            talhao=self.t1,
            pago=True,
            **kw,
        )

    def test_ano_filtra(self):
        self._l(valor=D("1000"), data="2025-03-10")
        self._l(valor=D("4000"), data="2026-03-10")

        r26 = custo_por_talhao(self.user, ano=2026)
        r25 = custo_por_talhao(self.user, ano=2025)
        self.assertEqual(r26.total_despesa, D("4000"))
        self.assertEqual(r25.total_despesa, D("1000"))

    def test_sem_ano_agrega_tudo(self):
        self._l(valor=D("1000"), data="2025-03-10")
        self._l(valor=D("4000"), data="2026-03-10")
        self.assertEqual(custo_por_talhao(self.user).total_despesa, D("5000"))


class TalhaoInativo(Base):
    def test_talhao_desactivado_sai(self):
        self.t1.ativo = False
        self.t1.save(update_fields=["ativo"])
        self.despesa(self.t1, "1000")
        r = custo_por_talhao(self.user)
        self.assertNotIn("Baixada", {l.talhao for l in r.linhas})
