"""Testes das mecânicas de backend: estoque, throttle, conciliação, depreciação."""

import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from app.models import (
    AplicacaoInsumo,
    ContaBancaria,
    Insumo,
    LancamentoFinanceiro,
    Maquinario,
    MovimentacaoBancaria,
    Propriedade,
    Talhao,
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


class EstoqueAutomaticoTest(TestCase):
    def setUp(self):
        self.u = _mkuser("mec")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Faz Mec", area_total=10, uf="MT", cidade="X"
        )
        self.talhao = Talhao.objects.create(
            propriedade=self.prop, nome="T1", area_hectare=10, ativo=True
        )
        self.ins = Insumo.objects.create(
            propriedade=self.prop,
            categoria="DEFENSIVO",
            nome="Glif",
            quantidade=100,
            unidade="L",
            valor_unitario=10,
        )

    def test_aplicacao_baixa_estoque(self):
        AplicacaoInsumo.objects.create(
            insumo=self.ins, talhao=self.talhao, data=date.today(), dose=10
        )
        self.ins.refresh_from_db()
        self.assertEqual(float(self.ins.quantidade), 90)

    def test_sem_saldo_bloqueia(self):
        with self.assertRaises(ValidationError):
            AplicacaoInsumo.objects.create(
                insumo=self.ins, talhao=self.talhao, data=date.today(), dose=500
            )
        self.ins.refresh_from_db()
        self.assertEqual(float(self.ins.quantidade), 100)

    def test_excluir_devolve_estoque(self):
        ap = AplicacaoInsumo.objects.create(
            insumo=self.ins, talhao=self.talhao, data=date.today(), dose=10
        )
        ap.delete()
        self.ins.refresh_from_db()
        self.assertEqual(float(self.ins.quantidade), 100)


class ThrottleIATest(TestCase):
    @override_settings(IA_THROTTLE_PER_MINUTE=3)
    def test_limite_429(self):
        u = _mkuser("throttle")
        c = Client()
        c.force_login(u)
        payload = {"intent": "ajuda", "params": {}}
        for _ in range(3):
            r = c.post(
                "/api/ia/executar/",
                data=json.dumps(payload),
                content_type="application/json",
            )
            self.assertEqual(r.status_code, 200)
        r = c.post(
            "/api/ia/executar/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 429)
        self.assertFalse(r.json()["ok"])


class ConciliacaoTest(TestCase):
    def setUp(self):
        self.u = _mkuser("conc")
        self.prop = Propriedade.objects.create(
            user=self.u, nome="Faz Conc", area_total=10, uf="MT", cidade="X"
        )
        self.conta = ContaBancaria.objects.create(
            propriedade=self.prop,
            banco="Banco C",
            agencia="1",
            conta="2",
            tipo="CORRENTE",
        )

    def test_casa_valor_exato(self):
        from app.services.conciliacao import conciliar_conta

        hoje = timezone.now().date()
        mov = MovimentacaoBancaria.objects.create(
            conta=self.conta, data=hoje, valor=250, tipo="DEBITO"
        )
        lac = LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=250,
            data=hoje,
        )
        pares = conciliar_conta(self.conta)
        self.assertEqual(len(pares), 1)
        mov.refresh_from_db()
        lac.refresh_from_db()
        self.assertTrue(mov.conciliado)
        self.assertTrue(lac.pago)
        self.assertEqual(lac.data_pagamento, hoje)

    def test_valor_diferente_nao_casa(self):
        from app.services.conciliacao import conciliar_conta

        hoje = timezone.now().date()
        mov = MovimentacaoBancaria.objects.create(
            conta=self.conta, data=hoje, valor=251, tipo="DEBITO"
        )
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMOS",
            valor=250,
            data=hoje,
        )
        self.assertEqual(conciliar_conta(self.conta), [])
        mov.refresh_from_db()
        self.assertFalse(mov.conciliado)


class DepreciacaoTest(TestCase):
    def test_linear_5_de_10_anos(self):
        from app.models import Maquinario

        u = _mkuser("depr")
        prop = Propriedade.objects.create(
            user=u, nome="Faz D", area_total=10, uf="MT", cidade="X"
        )
        m = Maquinario.objects.create(
            propriedade=prop,
            tipo="TRATOR",
            nome="Trator D",
            valor_aquisicao=100000,
            valor_residual=10000,
            vida_util_anos=10,
            data_aquisicao=date.today() - timedelta(days=int(5 * 365.25)),
        )
        self.assertTrue(54000 < m.valor_atual < 56000)

    def test_sem_base_none(self):
        from app.models import Maquinario

        u = _mkuser("depr2")
        prop = Propriedade.objects.create(
            user=u, nome="Faz D2", area_total=10, uf="MT", cidade="X"
        )
        m = Maquinario.objects.create(propriedade=prop, tipo="TRATOR", nome="T")
        self.assertIsNone(m.valor_atual)
