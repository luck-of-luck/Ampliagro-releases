"""Os handlers do ledger, executados de verdade.

`test_automacao_completude.py` prova que os intents estão registados. Este
prova que **funcionam** quando a IA os chama — e que a honestidade sobrevive
à passagem pelo handler, que é onde um `None` se transforma facilmente em
palavra bonita.

## O caminho mais perigoso

Um serviço devolve `None` com `motivo`, e o handler escreve-o no texto. Se o
handler escrever "R$ 0,00" em vez do motivo, **o defeito que corrigi no serviço
reaparece na conversa** — que é onde o produtor lê.

`test_capacidade_nao_diz_zero_quando_falta` e
`test_preco_nao_inventa_mediana_sem_transacoes` existem para isso.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.intents import INTENTS
from app.models import (
    Cultura,
    LancamentoFinanceiro,
    Propriedade,
    Safra,
)


class HandlersLedgerTest(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("prod", password="x")
        self.p = PerfilUsuarioFactory(self.u)
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda Boa",
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        self.cultura = Cultura.objects.create(nome="Soja")
        self.safra = Safra.objects.create(
            propriedade=self.prop,
            cultura=self.cultura,
            ano=2026,
            area_plantada=Decimal("50.00"),
            producao_total=Decimal("30000.00"),
            data_plantio=date(2026, 10, 5),
        )

    def _chama(self, nome, **params):
        spec = INTENTS[nome]
        ctx = {"fontes": []}
        return spec["handler"](self.u, params, ctx)

    def _venda(self, qtd, preco, nome="SOJA"):
        return LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            descricao=f"NF-e {nome}",
            valor=Decimal(str(preco * qtd)).quantize(Decimal("0.01")),
            data=date(2026, 3, 10),
            quantidade=Decimal(str(qtd)),
            unidade="SC",
            cfop="5102",
        )

    # ------------------------------------------------------------------

    def test_capacidade_responde_e_carimba_a_fonte(self):
        for _ in range(3):
            self._venda(100, 150.0)
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMO",
            valor=Decimal("500.00"),
            data=date(2026, 3, 10),
            quantidade=Decimal("10"),
            unidade="KG",
            cfop="1102",
        )

        r = self._chama("capacidade_pagamento")

        self.assertTrue(r["ok"])
        self.assertEqual(r["fonte_dado"], "medido")
        self.assertIn("Fazenda Boa", r["resposta"])
        # E a recusa de decidir tem de estar no texto, não só no payload.
        self.assertIn("banco", r["resposta"].lower())
        self.assertIsNone(r["dados"]["decisao_de_credito"])

    def test_capacidade_nao_diz_zero_quando_falta(self):
        """Sem despesas registadas, o texto diz que não apurou."""
        for _ in range(3):
            self._venda(100, 150.0)

        r = self._chama("capacidade_pagamento")

        self.assertIn("não apurado", r["resposta"])
        self.assertNotIn("despesas: R$ 0.00", r["resposta"])

    def test_preco_nao_inventa_mediana_sem_transacoes(self):
        """Sem venda, o handler diz que não há — e diz onde buscar."""
        r = self._chama("preco_referencia", produto="soja")

        self.assertTrue(r["ok"])
        self.assertEqual(r["fonte_dado"], "sem_dado")
        self.assertIn("Sem quantidade", r["resposta"])
        self.assertNotIn("mediana", r["resposta"].lower())

    def test_preco_avisa_amostra_pequena(self):
        """3 transações: a mediana é dada, o aviso acompanha."""
        for _ in range(3):
            self._venda(100, 150.0)

        r = self._chama("preco_referencia", produto="soja")

        self.assertEqual(r["fonte_dado"], "medido_com_aviso")
        self.assertIn("amostra", r["resposta"])
        self.assertIn("concentração", r["resposta"].lower())

    def test_preco_sem_produto_pede_o_produto(self):
        r = self._chama("preco_referencia")
        self.assertFalse(r["ok"])
        self.assertIn("produto", r["erro"])

    def test_cfop_diz_o_efeito_no_estoque(self):
        r = self._chama("classificar_cfop", cfop="5102")

        self.assertTrue(r["ok"])
        self.assertIn("receita", r["resposta"].lower())
        self.assertIn("não como insumo", r["resposta"].lower())

    def test_cfop_desconhecido_e_honesto(self):
        r = self._chama("classificar_cfop", cfop="9999")

        self.assertEqual(r["fonte_dado"], "sem_dado")
        self.assertIn("lucro", r["resposta"].lower())

    def test_ibs_sem_tabela_diz_que_nao_sei(self):
        """A alíquota não está carregada, e o handler não a inventa."""
        r = self._chama("ibs_cbs", valor="10000")

        self.assertEqual(r["fonte_dado"], "sem_dado")
        self.assertIsNone(r["dados"]["cbs"])
        self.assertIn("gov.br/fazenda", r["resposta"])

    def test_ibs_com_valor_nao_numerico_nao_parte(self):
        r = self._chama("ibs_cbs", valor="muito")
        self.assertFalse(r["ok"])
        self.assertIn("número", r["erro"])

    def test_custo_sem_safra_pergunta(self):
        """Sem safra não há custo por hectare — e não há escolha automática."""
        r = self._chama("custo_producao")

        self.assertFalse(r["ok"])
        self.assertIn("safra", r["erro"])

    def test_zarc_distingue_fora_de_desconhecido(self):
        r = self._chama("zarc_safra")

        self.assertTrue(r["ok"])
        # A safra existe, o ZARC não está carregado -> desconhecido, não 'fora'.
        vereditos = r["dados"]["rastros"]
        self.assertEqual(len(vereditos), 1)
        self.assertIsNone(vereditos[0]["dentro_da_janela"])
        self.assertNotIn("fora da janela", r["resposta"])

    def test_o_tecnico_alcanca_a_fazenda_que_serve(self):
        """Um perfil `agronomo` que não é dono tem de alcançar a fazenda.

        Este é o caso da cooperativa (§23D): o técnico pergunta pelos campos
        das fazendas que serve. Com a versão estrita do resolutor
        (`Propriedade.objects.filter(user=user)`) o handler dizia "nenhuma
        propriedade encontrada" — **um bug de funcionalidade que se lê como
        bug de segurança**, porque a falha aparece como "sem dados" e não como
        "sem permissão".
        """
        from app.models import Funcionario, PerfilUsuario

        perfil = PerfilUsuario.objects.get(user=self.u)
        perfil.tipo_usuario = "agronomo"
        perfil.propriedade_vinculada = self.prop
        perfil.save()
        self.u.refresh_from_db()

        # Uma propriedade de OUTRO dono, vinculada ao perfil do técnico.
        outro = User.objects.create_user("dono_outro", password="x")
        servida = Propriedade.objects.create(
            user=outro,
            nome="Fazenda servida",
            area_total=Decimal("80.00"),
            uf="MT",
            cidade="Sorriso",
        )
        func = Funcionario.objects.create(
            propriedade=servida,
            nome="Vínculo",
            cargo="Tecnico",
            salario=Decimal("3000.00"),
            data_admissao=date(2026, 1, 1),
        )
        # **Uma** instancia, set **e** save na mesma. Duas chamadas a
        # `.get()` sao duas linhas diferentes do banco: a segunda carrega
        # o valor antigo e o `save()` sobrescreve o vinculo. Foi o que
        # aconteceu aqui, e e o mesmo erro que cometi em
        # `tests_cooperativa.py`.
        _perfil = PerfilUsuario.objects.get(user=self.u)
        _perfil.funcionario = func
        _perfil.save()
        self.u.refresh_from_db()

        # Uma venda na fazenda servida, para o preço ter o que agregar.
        LancamentoFinanceiro.objects.create(
            propriedade=servida,
            tipo="RECEITA",
            categoria="VENDA_PROD",
            descricao="NF-e SOJA",
            valor=Decimal("15000.00"),
            data=date(2026, 3, 10),
            quantidade=Decimal("100"),
            unidade="SC",
            cfop="5102",
        )

        r = self._chama("preco_referencia", produto="soja")

        self.assertTrue(r["ok"], r.get("erro"))
        self.assertEqual(
            r["dados"]["n_transacoes"],
            1,
            "o tecnico nao alcancou a fazenda que serve",
        )


def PerfilUsuarioFactory(user):
    from app.models import PerfilUsuario

    perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
    perfil.propriedade_vinculada = None
    perfil.save()
    user.refresh_from_db()
    return perfil
