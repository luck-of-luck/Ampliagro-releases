"""A REGRA DE CONTAS TEM DE DISPARAR PELO MOTOR.

MEDIDO 2026-10-05 (agente 9). Escrevi `contas_proativo.py` com 25 testes e
`regra_contas` produzia achados correctos — e **nada a chamava**. Todos os
testes passavam porque testavam a funcao, nao a autonomia.

Este ficheiro fecha essa porta. Testa o CAMINHO INTEIRO:

    montar_cenario -> regras_deterministicas -> avaliar_usuario -> alerta

O que um teste da funcao nao apanha:
  - um cenario sem tarefas nao chega a existir (um boleto vencido nao e' uma
    tarefa, e antes disto nao havia cenario sem tarefas)
  - a chave `regra` em falta: `emitir_alerta` exige-a, e sem ela o alerta nao
    sai — nao sai mal, **nao sai**, e o teste da funcao nao nota
  - a governanca: nivel_minimo, teto diario, fingerprint. Um caminho com atalho
    proprio passaria por cima disto e o teste da funcao nao veria
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.ia import proativo
from app.models import ContaAPagar, Propriedade


class AutonomiaDasContasTest(TestCase):
    """A regra entra pelo mesmo caminho que a chuva."""

    def setUp(self):
        self.u = User.objects.create_user(username="auto_contas", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda Autonoma",
            area_total=80.0,
            uf="GO",
            cidade="Pirenópolis",
        )

    def conta(self, **kw):
        padrao = dict(
            propriedade=self.prop,
            descricao="Fertilizante",
            valor=Decimal("900.00"),
            vencimento=timezone.localdate(),
        )
        padrao.update(kw)
        return ContaAPagar.objects.create(**padrao)

    # ---------------------------------------------------------------- 1
    def test_um_boleto_vencido_cria_cenario_mesmo_sem_tarefas(self):
        """O caso que estava partido.

        `montar_cenario` devolvia `tem_cenario: False` sem tarefas. Um boleto
        vencido nao e' uma tarefa, e portanto o produtor nunca via o aviso —
        mesmo com dinheiro a sair.
        """
        self.conta(vencimento=timezone.localdate() - timedelta(days=4))

        cenario = proativo.montar_cenario(self.u, self.prop)

        self.assertTrue(
            cenario["tem_cenario"],
            "conta vencida tem de produzir cenario, mesmo sem tarefas: "
            "um boleto para nao ser uma tarefa",
        )
        self.assertTrue(cenario["contas"]["tem_algo"])

    # ---------------------------------------------------------------- 2
    def test_a_regra_devolve_o_formato_que_o_motor_exige(self):
        """`regra` e' obrigatoria. Sem ela o alerta NAO SAI — e nao sai mal."""
        self.conta(vencimento=timezone.localdate() - timedelta(days=2))

        achados = proativo.regras_deterministicas(
            proativo.montar_cenario(self.u, self.prop)
        )
        contas = [a for a in achados if a.get("regra") == "contas"]

        self.assertTrue(contas, "a regra de contas nao devolveu achados")
        for a in contas:
            for chave in ("titulo", "mensagem", "nivel", "regra", "evidencia"):
                self.assertIn(chave, a, f"achado sem `{chave}`")
            self.assertEqual(a["nivel"], "critico")

    # ---------------------------------------------------------------- 3
    def test_a_conta_vence_longe_nao_cria_cenario(self):
        """Um aviso sobre tudo e' o mesmo que nao avisar."""
        cenario = proativo.montar_cenario(self.u, self.prop)
        self.assertFalse(cenario["tem_cenario"])

        self.conta(vencimento=timezone.localdate() + timedelta(days=40))
        cenario = proativo.montar_cenario(self.u, self.prop)
        self.assertFalse(
            cenario["tem_cenario"],
            "conta a 40 dias nao justifica um cenario",
        )

    # ---------------------------------------------------------------- 4
    def test_o_alerta_sai_pelo_motor(self):
        """Ponta a ponta: o produtor recebe."""
        from app.models import ProativoPreferencia
        # Proatividade comeca DESLIGADA por desenho: o opt-in do produtor
        # e' o que liga. Um teste que liguasse por fora estaria a medir
        # outra coisa.

        ProativoPreferencia.objects.get_or_create(
            user=self.u,
            propriedade=self.prop,
            defaults={"ativo": True, "nivel_minimo": 0},
        )
        self.conta(
            vencimento=timezone.localdate() - timedelta(days=3),
            descricao="Custo de armazenagem",
            fornecedor="Cenario X",
        )

        r = proativo.avaliar_usuario(self.u)

        self.assertEqual(r["ok"], True, r)
        self.assertGreaterEqual(r["alertas"], 1, f"nenhum alerta saiu: {r}")
        self.assertEqual(r["suprimidos"], 0, f"a governanca suprimiu: {r}")

    # ---------------------------------------------------------------- 5
    def test_nao_repete_o_mesmo_aviso(self):
        """O fingerprint e' o que impede cinco copias da mesma cobranca."""
        from app.models import ProativoPreferencia

        ProativoPreferencia.objects.get_or_create(
            user=self.u,
            propriedade=self.prop,
            defaults={"ativo": True, "nivel_minimo": 0},
        )
        self.conta(vencimento=timezone.localdate() - timedelta(days=3))

        primeira = proativo.avaliar_usuario(self.u)
        segunda = proativo.avaliar_usuario(self.u)

        self.assertGreaterEqual(primeira["alertas"], 1)
        self.assertEqual(
            segunda["alertas"],
            0,
            "o mesmo aviso saiu duas vezes — o fingerprint nao esta a "
            "impedir, e o produtor vai receber a mesma cobranca em loop",
        )

    # ---------------------------------------------------------------- 6
    def test_a_conta_sem_origem_da_data_vem_marcada(self):
        """A regra nao mostra um numero sem dizer de onde veio."""
        self.conta(
            vencimento=timezone.localdate() + timedelta(days=2),
            fonte_dado="INVENTADO",
        )
        cenario = proativo.montar_cenario(self.u, self.prop)
        achados = [
            a
            for a in proativo.regras_deterministicas(cenario)
            if a.get("regra") == "contas"
        ]
        self.assertTrue(achados)
        self.assertIn("confirme", achados[0]["mensagem"].lower())

    # ---------------------------------------------------------------- 7
    def test_a_regra_da_chuva_continua_a_funcionar(self):
        """Ligar uma regra nova nao pode partir a que ja existia."""
        from app.ia import proativo as P

        cenario = {
            "tem_cenario": True,
            "tarefas": [
                {
                    "tarefa_id": 1,
                    "dia": timezone.localdate().isoformat(),
                    "descricao": "aplicar herbicida",
                    "status": "pendente",
                    "prioridade": 1,
                    "parece_aplicacao": True,
                }
            ],
            "previsao": {
                "ok": True,
                "dias": [
                    {
                        "dia": timezone.localdate().isoformat(),
                        "prob": 90,
                        "mm": 30.0,
                        "tmin": 20,
                        "tmax": 28,
                    }
                ],
            },
            "contas": {},
        }
        achados = P.regras_deterministicas(cenario)
        self.assertTrue(
            achados,
            "a regra da chuva deixou de disparar depois de a de contas entrar",
        )
