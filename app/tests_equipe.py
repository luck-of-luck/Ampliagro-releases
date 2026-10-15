"""Testes da lincagem profissional: cargos, áreas, IA e push instantâneo."""

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia.sandbox import executar
from app.models import (
    CARGO_AREA,
    CARGOS,
    AtividadePlanejada,
    Cultura,
    Funcionario,
    PlanoSafra,
    Propriedade,
    Safra,
    area_do_cargo,
)


def _mkuser(name):
    return User.objects.create_user(username=name, password="x")


class ProfissoesTest(TestCase):
    def test_todo_cargo_tem_area(self):
        chaves = [k for k, _ in CARGOS]
        self.assertGreaterEqual(len(chaves), 100)
        sem = [k for k in chaves if k != "OUTRO" and k not in CARGO_AREA]
        self.assertEqual(sem, [], f"cargos sem área: {sem}")

    def test_area_do_cargo(self):
        self.assertEqual(area_do_cargo("TRATORISTA"), "CAMPO")
        self.assertEqual(area_do_cargo("VAQUEIRO"), "PECUARIA")
        self.assertEqual(area_do_cargo("MECANICO_AGRICOLA"), "MECANICA")
        self.assertEqual(area_do_cargo("ALMOXARIFE"), "ESTOQUE")
        self.assertEqual(area_do_cargo("ENGENHEIRO"), "AGRONOMIA")
        self.assertEqual(area_do_cargo("CONTADOR_RURAL"), "FINANCEIRO")
        self.assertEqual(area_do_cargo("INEXISTENTE_XYZ"), "GERAL")


class TarefaProfissionalTest(TestCase):
    def setUp(self):
        self.dono = _mkuser("dono_eq")
        self.prop = Propriedade.objects.create(
            user=self.dono, nome="Faz Eq", area_total=10, uf="MT", cidade="X"
        )
        self.mec_user = _mkuser("zeca")
        self.mec = Funcionario.objects.create(
            propriedade=self.prop,
            nome="Zé Mecânico",
            cargo="MECANICO_AGRICOLA",
            salario=3000,
            data_admissao="2024-01-01",
            user=self.mec_user,
        )
        cultura = Cultura.objects.create(nome="SojaEq", grupo="graos")
        safra = Safra.objects.create(
            propriedade=self.prop, cultura=cultura, ano=2026, area_plantada=10
        )
        self.plano = PlanoSafra.objects.create(safra=safra)

    def test_ia_associa_por_profissao(self):
        """`associar_tarefa` passou a pedir confirmação.

        Este teste era anterior ao gate. Corria `executar()` sem `confirm` e
        esperava a escrita logo; hoje o `sandbox` devolve `needs_confirm` e
        o plano correcto é confirmar primeiro — que é o que
        `app/ia/tests.py:782` já faz ("`confirm: True` porque
        `associar_tarefa` passou a ter confirmação").

        A chamada directa sem `confirm` **continua a ser a que este teste
        mede**, e continua a ser correcta: não escreve. É isso que se
        verifica primeiro.
        """
        # 1. Sem `confirm`: NÃO escreve, e pergunta.
        out = executar(
            self.dono, "associar_tarefa", {"titulo": "revisar motor pro mecânico"}
        )
        self.assertTrue(out["ok"])
        self.assertTrue(
            out.get("needs_confirm"),
            f"uma escrita tem de pedir confirmacao; resposta: {out}",
        )
        self.assertEqual(
            AtividadePlanejada.objects.filter(
                plano=self.plano, nome__icontains="revisar"
            ).count(),
            0,
            "escreveu sem o produtor confirmar — e e' exactamente o que o "
            "gate de `sandbox.py` existe para impedir",
        )

        # 2. Com `confirm`: escreve, e associa pelo sítio do título.
        out2 = executar(
            self.dono,
            "associar_tarefa",
            {"titulo": "revisar motor pro mecânico", "confirm": True},
        )
        self.assertTrue(out2["ok"], out2)
        self.assertEqual(out2["dados"]["cargo_alvo"], "MECANICO_AGRICOLA")
        self.assertEqual(out2["dados"]["funcionario_id"], self.mec.id)
        self.assertIn("Zé Mecânico", out2["resposta"])

    def test_push_cria_notificacao_na_hora(self):
        from datetime import date

        from app.models import AtividadePlanejada, Notificacao

        AtividadePlanejada.objects.create(
            plano=self.plano,
            nome="Trocar óleo",
            data_prevista=date.today(),
            funcionario=self.mec,
            cargo_alvo="MECANICO_AGRICOLA",
        )
        self.assertTrue(
            Notificacao.objects.filter(
                user=self.mec_user, titulo__contains="Trocar óleo"
            ).exists()
        )

    def test_push_kanban_para_area(self):
        from app.models import (
            EstagioCultura,
            Notificacao,
            RegistroProducao,
            TarefaEstagio,
        )

        cultura = Cultura.objects.create(nome="MilhoEq", grupo="graos")
        reg = RegistroProducao.objects.create(
            user=self.dono, cultura=cultura, nome="Reg Eq"
        )
        est = EstagioCultura.objects.create(registro=reg, nome="Plantio")
        TarefaEstagio.objects.create(
            estagio=est,
            descricao="Apertar parafuso",
            funcionario=self.mec,
            propriedade=self.prop,
        )
        self.assertTrue(Notificacao.objects.filter(user=self.mec_user).exists())

    def test_indices_velocidade(self):
        from app.models import AtividadePlanejada, TarefaEstagio

        def idxs(model):
            return [list(i.fields) for i in model._meta.indexes]

        self.assertIn(["cargo_alvo"], idxs(AtividadePlanejada))
        self.assertIn(["cargo_alvo"], idxs(TarefaEstagio))
        self.assertIn(["propriedade", "cargo"], idxs(Funcionario))
