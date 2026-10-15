"""A regra `contas_vencidas` tem de parar de MENTIR.

MEDIDO 2026-10-05 (agente 9). O `gerar_alertas.py` contava como "conta
vencida" qualquer `LancamentoFinanceiro` com `data < hoje`.

`data` e' quando a despesa ACONTECEU. Nao e' quando o dinheiro e' para sair.

O cenario que este ficheiro torna impossivel:

    Janeiro de 2024: compro adubo por R$ 5 000, registo a despesa.
    Nao pago. Nao tenho data de vencimento — nunca a registei.
    Outubro de 2026: o produtor recebe "1 conta vencida, R$ 5 000.00".

Isto nao e' um erro de arredondamento. E' um alerta `critical` que afirma um
atraso que nao existe, e que se repete todos os meses com o mesmo numero —
porque a despesa continua la para sempre.

Um alarme que mente sobre a mesma coisa durante anos e' o que faz um produtor
desligar as notificacoes. E' o pior modo de um alerta falhar.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from app.models import ContaAPagar, LancamentoFinanceiro, Propriedade


class ContasVencidasHonestasTest(TestCase):
    """O comando diz o que sabe, e pergunta o que nao sabe."""

    def setUp(self):
        self.u = User.objects.create_user(username="alertas_cmd", password="x")
        self.prop = Propriedade.objects.create(
            user=self.u,
            nome="Fazenda dos Alertas",
            area_total=100.0,
            uf="GO",
            cidade="Pirenópolis",
        )

    def _alertas(self):
        """Corre a logica REAL do comando e devolve os alertas de contas.

        O metodo e' `Command._verificar_propriedade(user, prop, hoje,
        trinta_dias)`. A primeira versao deste teste adivinhava o nome por
        tentativa-e-erro e fazia `skipTest` quando nao encontrava — o que e'
        um teste que passa sem provar nada, que e' pior do que nao ter teste.
        """
        from app.management.commands.gerar_alertas import Command

        cmd = Command()
        r = cmd._verificar_propriedade(
            self.u, self.prop, date(2026, 10, 5), 30
        )
        if isinstance(r, dict):
            lista = r.get("alertas") or []
        else:
            lista = list(r or [])
        return [a for a in lista if "conta" in str(a.get("regra", ""))]


    # ---------------------------------------------------------------- 1
    def test_uma_despesa_VELHA_sem_vencimento_nao_e_conta_vencida(self):
        """O cenario do titulo deste ficheiro.

        Janeiro de 2024, sem data de vencimento registada. Em October de 2026
        NAO e' uma conta vencida — e' uma despesa em aberto sem data.
        """
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMO",
            valor=Decimal("5000.00"),
            data=date(2024, 1, 15),
            pago=False,
            descricao="Adubo NP 20-05-20",
        )
        alertas = self._alertas()
        vencidas = [a for a in alertas if a.get("regra") == "contas_vencidas"]

        self.assertEqual(
            vencidas,
            [],
            "uma despesa de 2024 sem data de vencimento foi marcada como "
            "conta vencida. `data` e' quando ACONTECEU, nao quando vence",
        )

    # ---------------------------------------------------------------- 2
    def test_uma_despesa_VELHA_aparece_como_sem_data(self):
        """E o que ela e': um registo incompleto.

        Nao se esconde. Um produtor com tres despesas em aberto sem data nao tem
        um atraso — tem uma lacuna, e a mensagem que o ajuda diz isso.
        """
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMO",
            valor=Decimal("5000.00"),
            data=date(2024, 1, 15),
            pago=False,
        )
        alertas = self._alertas()
        sem_data = [a for a in alertas if a.get("regra") == "contas_sem_vencimento"]

        self.assertEqual(len(sem_data), 1, f"a despesa sumiu: {alertas}")
        self.assertIn(
            "não têm data de vencimento",
            sem_data[0]["mensagem"],
            "a mensagem tem de dizer que nao sabemos quando vence",
        )
        self.assertEqual(
            sem_data[0]["nivel"],
            "warning",
            "sem data nao e' `critical`: nao e' dinheiro que nao saiu quando devia",
        )

    # ---------------------------------------------------------------- 3
    def test_uma_conta_com_vencimento_real_ainda_e_critica(self):
        """A correccao nao pode perder o atraso verdadeiro.

        Uma `ContaAPagar` com vencimento passado e' dinheiro que nao saiu
        quando devia. Isso e' `critical`, e tem de continuar a ser.
        """
        ContaAPagar.objects.create(
            propriedade=self.prop,
            descricao="Fertilizante",
            valor=Decimal("1200.00"),
            vencimento=date(2026, 9, 20),
            fornecedor="Cenario X",
        )
        alertas = self._alertas()
        vencidas = [a for a in alertas if a.get("regra") == "contas_vencidas"]

        self.assertEqual(len(vencidas), 1, f"o atraso real desapareceu: {alertas}")
        self.assertEqual(vencidas[0]["nivel"], "critical")
        self.assertIn("20/09/2026", vencidas[0]["mensagem"])

    # ---------------------------------------------------------------- 4
    def test_o_valor_do_atraso_e_o_da_conta_nao_o_da_despesa(self):
        """O total tem de bater certo.

        A versao anterior somava `LancamentoFinanceiro.valor` de coisas que
        nao tinham vencimento. O total que vai para o produtor tem de ser o
        das contas que estao mesmo atrasadas.
        """
        ContaAPagar.objects.create(
            propriedade=self.prop,
            descricao="Conta atrasada",
            valor=Decimal("1200.00"),
            vencimento=date(2026, 9, 20),
        )
        # uma despesa grande e velha, que NAO e' atraso
        LancamentoFinanceiro.objects.create(
            propriedade=self.prop,
            tipo="DESPESA",
            categoria="INSUMO",
            valor=Decimal("5000.00"),
            data=date(2024, 1, 15),
            pago=False,
        )
        alertas = self._alertas()
        vencidas = [a for a in alertas if a.get("regra") == "contas_vencidas"]

        # `f"{float(x):,.2f}"` escreve no formato AMERICANO: "1,200.00". Nao e'
        # o que o produtor le no resto do sistema ("1.234,56") — ver a nota de
        # formato no `gerar_alertas.py`. O teste mede o valor, nao a pontuacao.
        msg = vencidas[0]["mensagem"]
        self.assertIn("1200", msg.replace(".", "").replace(",", ""))
        self.assertNotIn("5000", msg.replace(".", "").replace(",", ""))
