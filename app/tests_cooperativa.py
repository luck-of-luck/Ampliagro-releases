"""Cooperativa: a agregação tem de ser mais honesta que a soma.

## O teste que mais importa

`test_agregado_nao_soma_propriedade_sem_dado`.

Uma cooperativa com 3 Cooperados, um deles sem lançamentos, tem duas
respostas possíveis e só uma é honesta:

- `{"receitas": 900000}` — e o agregado diz "R$ 900 mil" sem dizer de quantas
  propriedades. Um técnico de crédito lê "R$ 900 mil" e não sabe que é de 2
  em 3. **Isto é o `or Decimal("1.0")` do `custo_producao.py`, com uma
  falha maior.**
- `{"receitas": 900000, "incompleta": true, "incompletos": [...]}` — o número
  é dos valores apurados, e diz isso.

## E o inverso

`test_propriedade_alheia_e_recusada_e_nao_soma`: uma propriedade que o perfil
não pode ver **não entra na soma**. Sem isto, um perfil de cooperativa com uma
propriedade alheia na lista receberia o total dela — que é o vazamento que o
`TenantIsolationMiddleware` existe para impedir.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import (
    LancamentoFinanceiro,
    PerfilUsuario,
    Propriedade,
)
from app.services.cooperativa import (
    agregado,
    pode_agregar,
    propriedades_agregaveis,
)


class CooperativaAgregadoTest(TestCase):
    def setUp(self):
        self.tec = User.objects.create_user("tecnico", password="x")
        perfil = PerfilUsuario.objects.get(user=self.tec)
        perfil.tipo_usuario = "agronomo"
        perfil.save()

        self.dona = User.objects.create_user("dona", password="x")
        perfil_dona = PerfilUsuario.objects.get(user=self.dona)
        perfil_dona.tipo_usuario = "produtor"
        perfil_dona.save()

        self.p1 = self._prop("Fazenda 1", self.dona, receita="100000.00")
        self.p2 = self._prop("Fazenda 2", self.dona, receita="800000.00")
        self.p3 = self._prop("Fazenda 3", self.dona, receita=None)
        self.alheia = self._prop("Fazenda alheia", self.dona, receita="500000.00")

        # p1 e p2 com despesa: sem ela `despesas_periodo` é `None`
        # (capacidade_pagamento.py:62) e a soma nunca seria "completa". Uma
        # propriedade com receita e sem despesa tem um fator por apurar, e o
        # agregado tem de dizer isso.
        for prop, desp in ((self.p1, "40000.00"), (self.p2, "300000.00")):
            LancamentoFinanceiro.objects.create(
                propriedade=prop,
                descricao="Custo",
                valor=Decimal(desp),
                tipo="DESPESA",
                categoria="MECANIZACAO",
                data=date(2026, 4, 2),
            )

    def _prop(self, nome, user, receita):
        prop = Propriedade.objects.create(
            user=user,
            nome=nome,
            area_total=Decimal("100.00"),
            uf="MT",
            cidade="Sorriso",
        )
        if receita is not None:
            LancamentoFinanceiro.objects.create(
                propriedade=prop,
                descricao="Venda",
                valor=Decimal(receita),
                tipo="RECEITA",
                categoria="VENDA_PROD",
                data=date(2026, 3, 10),
            )
        return prop

    def _vincula_tecnico(self, principal, *restas):
        """O técnico passa a ver `principal` e `restas`.

        `PerfilUsuario.propriedade_vinculada` é **uma** propriedade
        (`models/usuario.py:34`), e `funcionario` é OneToOne — ou seja, o
        perfil dá acesso a **duas** propriedades, não a N. Uma cooperativa de
        verdade precisaria de um vínculo 1:N que não existe.

        Isto não é um defeito do meu módulo: é um limite do modelo atual, e
        registo-o em vez de fingir que o limite não existe. O que os testes
        fixam é que, com as propriedades que o perfil **tem**, a agregação é
        verificada e a soma é honesta.
        """
        from app.models import Funcionario

        perfil = PerfilUsuario.objects.get(user=self.tec)
        perfil.propriedade_vinculada = principal
        perfil.funcionario = None
        if restas:
            func = Funcionario.objects.create(
                propriedade=restas[0],
                nome="Vinculo tecnico",
                cargo="Tecnico",
                salario=Decimal("3000.00"),
                data_admissao=date(2026, 1, 1),
            )
            perfil.funcionario = func
        perfil.save()

        # O sinal `post_save` da criação do User já tinha populado o cache de
        # `u.perfil`. `propriedades_visiveis` lê esse cache, não o banco
        # (hierarquia.py:213), por isso sem isto o vínculo não existe — o
        # perfil tem a propriedade e o código acha que não tem.
        self.tec.refresh_from_db()
        return self.tec

    # ------------------------------------------------------------------
    # A soma honesta
    # ------------------------------------------------------------------

    def test_agregado_nao_soma_propriedade_sem_dado(self):
        """A soma é dos valores apurados, e diz de quantos.

        Uma com receita (100k) e uma sem. A soma é 100k **e** marcada como
        incompleta — não "R$ 100k da cooperativa".
        """
        self._vincula_tecnico(self.p1, self.p3)

        r = agregado(self.tec, [self.p1.id, self.p3.id])

        self.assertEqual(r["totais"]["receitas"], 100000.0)
        self.assertTrue(r["incompleta"], "soma parcial declarada como completa")
        self.assertEqual(
            r["totais"]["propriedades_no_total"]["receitas"],
            1,
            "a soma nao diz de quantas propriedades veio",
        )
        incompletos = {i["propriedade_id"] for i in r["incompletos"]}
        self.assertIn(self.p3.id, incompletos)
        self.assertIsNotNone(r["aviso"])

    def test_soma_completa_nao_e_marcada_incompleta(self):
        self._vincula_tecnico(self.p1, self.p2)
        r = agregado(self.tec, [self.p1.id, self.p2.id])
        self.assertEqual(
            r["propriedades_agregadas"],
            [self.p1.id, self.p2.id],
            "o tecnico tem de ver as duas: "
            f"agregadas={r['propriedades_agregadas']} "
            f"recusadas={r['propriedades_recusadas']}",
        )
        self.assertEqual(r["totais"]["receitas"], 900000.0)
        self.assertEqual(r["totais"]["despesas"], 340000.0)
        self.assertEqual(r["totais"]["saldo"], 560000.0)
        self.assertFalse(r["incompleta"])
        self.assertIsNone(r["aviso"])

    def test_area_nao_medida_nao_entra_na_soma(self):
        """Área não medida não entra como 0 ha — é o mesmo princípio."""
        sem_area = Propriedade.objects.create(
            user=self.dona, nome="Sem área", area_total=Decimal("0.00")
        )
        self._vincula_tecnico(sem_area)
        r = agregado(self.tec, [sem_area.id])
        self.assertIsNone(r["totais"]["area_ha"])
        self.assertTrue(r["incompleta"])

    def test_nenhuma_propriedade_com_dado_soma_e_none(self):
        """Sem nenhum valor apurado, a soma é `None` — não 0."""
        self._vincula_tecnico(self.p3)
        r = agregado(self.tec, [self.p3.id])
        self.assertIsNone(r["totais"]["receitas"])
        self.assertIsNone(r["totais"]["saldo"])

    # ------------------------------------------------------------------
    # Segurança — a agregação sem verificação é um vazamento
    # ------------------------------------------------------------------

    def test_propriedade_alheia_e_recusada_e_nao_soma(self):
        """A propriedade que o perfil não pode ver não entra na soma.

        Sem isto, um perfil de cooperativa com uma propriedade alheia na
        lista receberia o total dela.
        """
        self._vincula_tecnico(self.p1)
        r = agregado(self.tec, [self.p1.id, self.alheia.id])

        self.assertIn(self.p1.id, r["propriedades_agregadas"])
        self.assertIn(self.alheia.id, r["propriedades_recusadas"])
        self.assertNotIn(self.alheia.id, r["por_propriedade"])
        # E a soma não inclui o valor alheio.
        self.assertEqual(r["totais"]["receitas"], 100000.0)
        self.assertTrue(r["incompleta"], "havia recusa e nao foi declarada")

    def test_pode_agregar_e_por_propriedade(self):
        self._vincula_tecnico(self.p1)
        self.assertTrue(pode_agregar(self.tec, self.p1.id))
        self.assertFalse(pode_agregar(self.tec, self.alheia.id))

    def test_separacao_permite_explicar_ao_produtor(self):
        """A separação nomeia o que ficou de fora — uma lista menor seria
        lida como "a cooperativa não tem isso"."""
        self._vincula_tecnico(self.p1)
        permitidas, recusadas = propriedades_agregaveis(
            self.tec, [self.p1.id, self.alheia.id]
        )
        self.assertEqual(permitidas, [self.p1.id])
        self.assertEqual(recusadas, [self.alheia.id])

    def test_agregado_nao_decide_credito(self):
        self._vincula_tecnico(self.p1)
        r = agregado(self.tec, [self.p1.id])
        self.assertIsNone(r["decisao_de_credito"])

    # ------------------------------------------------------------------
    # O bloqueio: um perfil chega a DUAS propriedades, não a N
    # ------------------------------------------------------------------

    def test_perfil_agrega_no_maximo_duas_propriedades(self):
        """Regista o limite que trava a cooperativa de verdade.

        `PerfilUsuario` dá acesso a **duas** propriedades: uma por
        `propriedade_vinculada` e uma por `funcionario` (ambos singulares). Uma
        cooperativa de 30 cooperados **não é expressável** no modelo atual.

        Este teste não falha por acaso — ele fixa o limite para que, quando o
        vínculo 1:N entrar, ele quebre e obrige a rever `cooperativa.py`. Um
        limite silencioso é pior do que um limite declarado.
        """
        from app.hierarquia import propriedades_visiveis

        self._vincula_tecnico(self.p1, self.p2)
        visiveis = propriedades_visiveis(self.tec)
        self.assertEqual(
            visiveis.count(),
            2,
            "o perfil chegou a mais de 2: o limite mudou, reve "
            "cooperativa.py e este teste",
        )

        # Uma terceira propriedade existe e é visível a outro perfil, mas não
        # a este — por isso uma cooperativa real não cabe aqui.
        self.assertEqual(
            propriedades_visiveis(self.dona)
            .filter(pk__in=[self.p1.id, self.p2.id, self.p3.id])
            .count(),
            3,
            "a dona ve as tres; o perfil do tecnico, duas",
        )
