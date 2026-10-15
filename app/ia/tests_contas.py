"""Testes de contas a pagar e a receber.

O que se prova aqui, e porquê:

  - o `vencimento` sobrevive a ida e volta (e' a razao de o modelo existir)
  - `vencida` e' DERIVADO, nunca guardado — sem isso ha um segundo sitio onde
    a verdade pode estar errada
  - `liquidar` escreve o `LancamentoFinanceiro` — sem o qual o LCDPR nao fecha
  - a provenance impede que um numero sem origem entre num fluxo
  - a regra proativa dispara sozinha e NAO inventa
  - a IA nao adivinha a data de vencimento

MEDIDO 2026-10-05 (agente 9). Data: 2026-10-05
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from django.contrib.auth.models import User

from app.models import (
    ContaAPagar,
    ContaAReceber,
    LancamentoFinanceiro,
    Propriedade,
)


class BaseContas(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username="contas_teste", password="x")
        # `area_total` e' NOT NULL. A factory do `tests/conftest.py` poe 100.0;
        # aqui vai o mesmo, para o erro aparecer uma vez e nao em cada teste.
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda das Contas",
            area_total=100.0,
            cidade="Pirenópolis",
            uf="GO",
        )

    def conta(self, **kw):
        padrao = dict(
            propriedade=self.prop,
            descricao="Fertilizante 20-05-20",
            valor=Decimal("1250.00"),
            vencimento=timezone.localdate() + timedelta(days=10),
        )
        padrao.update(kw)
        return ContaAPagar.objects.create(**padrao)


class VencimentoTest(BaseContas):
    def test_vencimento_guarda_e_preserva(self):
        """O campo que `LancamentoFinanceiro` nao tinha."""
        dia = timezone.localdate() + timedelta(days=7)
        c = self.conta(vencimento=dia)
        c.refresh_from_db()
        self.assertEqual(c.vencimento, dia)

    def test_vencida_e_derivado_do_vencimento(self):
        hoje = timezone.localdate()
        vencida = self.conta(vencimento=hoje - timedelta(days=3))
        em_dia = self.conta(vencimento=hoje + timedelta(days=3))

        self.assertTrue(vencida.vencida)
        self.assertFalse(em_dia.vencida)
        # o campo `estado` continua ABERTA: `vencida` e' pergunta, nao estado
        self.assertEqual(vencida.estado, "ABERTA")

    def test_dias_atraso_conta(self):
        c = self.conta(vencimento=timezone.localdate() - timedelta(days=5))
        self.assertEqual(c.dias_atraso, 5)

    def test_conta_paga_nao_esta_vencida(self):
        c = self.conta(vencimento=timezone.localdate() - timedelta(days=10))
        c.estado = "PAGA"
        c.data_pagamento = timezone.localdate()
        self.assertFalse(
            c.vencida,
            "uma conta paga nao pode dizer que esta vencida — o alerta "
            "errado e' o que faz o produtor desligar as notificacoes",
        )

    def test_valor_zero_e_rejeitado(self):
        c = self.conta()
        c.valor = Decimal("0")
        with self.assertRaises(ValidationError):
            c.clean()

    def test_paga_sem_data_e_rejeitada(self):
        c = self.conta()
        c.estado = "PAGA"
        with self.assertRaises(ValidationError):
            c.clean()


class LiquidarTest(BaseContas):
    def test_liquidar_escreve_o_lancamento_que_o_lcdpr_le(self):
        """Sem isto, a conta sai do mundo e o LCDPR nao fecha."""
        c = self.conta(fornecedor="Forte Agro", categoria="INSUMO")
        antes = LancamentoFinanceiro.objects.count()

        lanc = c.liquidar(data_pagamento=timezone.localdate())
        c.refresh_from_db()

        self.assertEqual(LancamentoFinanceiro.objects.count(), antes + 1)
        self.assertEqual(c.estado, "PAGA")
        self.assertEqual(c.lancamento_id, lanc.pk)
        # o que o Q100 do LCDPR le
        self.assertEqual(lanc.tipo, "DESPESA")
        self.assertEqual(lanc.valor, Decimal("1250.00"))
        self.assertEqual(lanc.tipo_lancamento_lcdpr, "2")
        self.assertEqual(lanc.participante, "Forte Agro")
        self.assertTrue(lanc.pago)

    def test_liquidar_duas_vezes_e_rejeitado(self):
        """Pagar duas vezes e' o defeito que duplica despesa."""
        c = self.conta()
        c.liquidar(data_pagamento=timezone.localdate())
        with self.assertRaises(ValidationError):
            c.liquidar(data_pagamento=timezone.localdate())
        self.assertEqual(LancamentoFinanceiro.objects.filter(tipo="DESPESA").count(), 1)

    def test_receber_escreve_receita(self):
        r = ContaAReceber.objects.create(
            propriedade=self.prop,
            descricao="Venda de gado",
            valor=Decimal("9000.00"),
            vencimento=timezone.localdate(),
            cliente="Frigorifico X",
        )
        lanc = r.receber(data_recebimento=timezone.localdate())
        r.refresh_from_db()
        self.assertEqual(lanc.tipo, "RECEITA")
        self.assertEqual(lanc.tipo_lancamento_lcdpr, "1")
        self.assertEqual(r.estado, "PAGA")


class ProvenienciaTest(BaseContas):
    """A regra que distingue o Ampliagro de um ERP comum."""

    def test_vencimento_medido_e_confiavel(self):
        c = self.conta(fonte_dado="MEDIDO", documento_ref="NF-e 3526...")
        self.assertTrue(c.confiavel)

    def test_vencimento_declarado_e_confiavel(self):
        """O produtor disse. Honesto, e usa-se."""
        c = self.conta(fonte_dado="DECLARADO")
        self.assertTrue(c.confiavel)

    def test_vencimento_inventado_nao_e_confiavel(self):
        """Sem origem, o numero aparece mas nao governa decisao."""
        c = self.conta(fonte_dado="INVENTADO")
        self.assertFalse(c.confiavel)


class RegraProativaTest(BaseContas):
    """A capacidade de rotina: dispara sem ninguem pedir."""

    def test_conta_vencida_dispara_alerta_critico(self):
        from app.ia.contas_proativo import regra_contas

        self.conta(
            vencimento=timezone.localdate() - timedelta(days=2),
            descricao="Custo de armazenagem",
        )
        achados = regra_contas(self.u, self.prop)
        criticos = [a for a in achados if a["nivel"] == "critico"]
        self.assertEqual(len(criticos), 1)
        self.assertIn("vencida", criticos[0]["titulo"].lower())

    def test_conta_longe_nao_dispara(self):
        """Um aviso sobre tudo e' o mesmo que nao avisar."""
        from app.ia.contas_proativo import regra_contas

        self.conta(vencimento=timezone.localdate() + timedelta(days=30))
        self.assertEqual(regra_contas(self.u, self.prop), [])

    def test_conta_no_limite_de_3_dias_dispara(self):
        from app.ia.contas_proativo import regra_contas

        self.conta(vencimento=timezone.localdate() + timedelta(days=3))
        achados = regra_contas(self.u, self.prop)
        self.assertEqual(len(achados), 1)

    def test_conta_sem_origem_de_data_vem_marcada(self):
        from app.ia.contas_proativo import regra_contas

        self.conta(
            vencimento=timezone.localdate() + timedelta(days=1),
            fonte_dado="INVENTADO",
        )
        achados = regra_contas(self.u, self.prop)
        self.assertTrue(achados)
        self.assertIn("confirme", achados[0]["mensagem"].lower())

    def test_resumo_diz_quando_nao_sabe(self):
        from app.ia.contas_proativo import resumo_saude_financeira

        self.conta(vencimento=timezone.localdate(), fonte_dado="INVENTADO")
        r = resumo_saude_financeira(self.u, self.prop)
        self.assertEqual(r["qtd_sem_origem"], 1)
        self.assertGreater(r["total_pagar"], 0)


class IntencoesIA(BaseContas):
    def test_listar_devolve_totais_e_vencidas(self):
        from app.ia.contas_intents import listar_contas

        self.conta(valor=Decimal("1000.00"))
        self.conta(
            vencimento=timezone.localdate() - timedelta(days=5), valor=Decimal("500.00")
        )
        ctx = {"fontes": []}

        out = listar_contas(self.u, {}, ctx)

        self.assertTrue(out["ok"])
        self.assertEqual(out["dados"]["qtd_pagar"], 2)
        self.assertEqual(out["dados"]["vencidas"], 1)
        self.assertAlmostEqual(out["dados"]["total_pagar"], 1500.00, places=2)

    def test_registar_sem_vencimento_e_recusado(self):
        """O ponto do design: a IA pergunta, nao inventa."""
        from app.ia.contas_intents import registar_conta

        out = registar_conta(
            self.u, {"descricao": "Custo de armazenagem", "valor": 1200}, {"fontes": []}
        )
        self.assertFalse(out["ok"])
        self.assertIn("vencimento", out["erro"].lower())
        self.assertEqual(ContaAPagar.objects.count(), 0)

    def test_registar_com_vencimento_cria_conta(self):
        from app.ia.contas_intents import registar_conta

        out = registar_conta(
            self.u,
            {
                "descricao": "Custo de armazenagem",
                "valor": 1200,
                "vencimento": "15/03",
                "fornecedor": "Cenario X",
            },
            {"fontes": []},
        )
        self.assertTrue(out["ok"])
        self.assertEqual(ContaAPagar.objects.count(), 1)
        c = ContaAPagar.objects.first()
        self.assertEqual(c.fornecedor, "Cenario X")
        # sem documento, a origem e' DECLARADO — e a resposta diz isso
        self.assertEqual(c.fonte_dado, "DECLARADO")
        self.assertIn("confirme", out["resposta"].lower())

    def test_registar_com_documento_marca_medido(self):
        from app.ia.contas_intents import registar_conta

        registar_conta(
            self.u,
            {
                "descricao": "Compra de semente",
                "valor": 900,
                "vencimento": "2026-03-15",
                "documento": "NF-e 3526",
            },
            {"fontes": []},
        )
        self.assertEqual(ContaAPagar.objects.first().fonte_dado, "MEDIDO")

    def test_pagar_conta_baixa_e_escreve_lancamento(self):
        from app.ia.contas_intents import pagar_conta

        self.conta(descricao="Fertilizante")
        out = pagar_conta(self.u, {}, {"fontes": []})

        self.assertTrue(out["ok"])
        self.assertEqual(ContaAPagar.objects.first().estado, "PAGA")
        self.assertEqual(LancamentoFinanceiro.objects.filter(tipo="DESPESA").count(), 1)
        self.assertIn("lcdpr", out["resposta"].lower())

    def test_pagar_sem_contas_nao_inventa(self):
        from app.ia.contas_intents import pagar_conta

        out = pagar_conta(self.u, {}, {"fontes": []})
        self.assertFalse(out["ok"])


class IsolarPorPropriedadeTest(BaseContas):
    """Multi-empresa: o que e' de uma fazenda nao aparece na outra.

    E' a dimensao G03 da matriz, e a razao de `ContaAPagar` levar
    `propriedade` em vez de `user` directamente.
    """

    def setUp(self):
        super().setUp()
        self.outro = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda II",
            area_total=50.0,
            cidade="Rio Verde",
            uf="GO",
        )

    def test_conta_de_uma_fazenda_nao_aparece_na_outra(self):
        from app.ia.contas_intents import listar_contas

        ContaAPagar.objects.create(
            propriedade=self.outro,
            descricao="Conta da fazenda II",
            valor=Decimal("3000.00"),
            vencimento=timezone.localdate(),
        )
        out = listar_contas(self.u, {"propriedade": self.prop.id}, {"fontes": []})
        self.assertEqual(out["dados"]["qtd_pagar"], 0)

    def test_regra_proativa_respeita_a_fazenda(self):
        from app.ia.contas_proativo import regra_contas

        ContaAPagar.objects.create(
            propriedade=self.outro,
            descricao="Conta vencida da II",
            valor=Decimal("3000.00"),
            vencimento=timezone.localdate() - timedelta(days=9),
        )
        self.assertEqual(regra_contas(self.u, self.prop), [])
        self.assertEqual(len(regra_contas(self.u, self.outro)), 1)
