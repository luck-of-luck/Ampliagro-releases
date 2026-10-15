"""O que o PRODUTOR VE. Nao a funcao — o caminho inteiro.

MEDIDO 2026-10-05 (agente 11). Mutation testing na correccao da confirmacao
apanhou 6 de 7. A que escapou foi a mais importante: **a ligacao**.

Os testes de `prompt_de_confirmacao` chamam a funcao directamente, com os
parametros na mao. Passam `{"safra": "2025/26"}` e provam que a funcao sabe
mostrar um valor. Nao provam que **alguem lha passe os valores** — e se o
sandbox voltar a chamar `prompt_de_confirmacao(intent)` sem o segundo
argumento, todos eles continuam verdes.

Este ficheiro fecha esse buraco: chama `sandbox.executar()`, que e' o caminho
que o produtor percorre, e mede a STRING que ele recebe.

O objectivo e' concreto. Se `params`={safra: 2025/26} e o texto de confirmacao
continuar a dizer "esta safra", o produtor responde "sim" a uma pergunta que
nao identifica o objecto. Este teste tem de falhar nesse caso.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.ia import sandbox
from app.models.ia import IAContextoConversa

User = get_user_model()


class ConfirmacaoPontaAPontaTest(TestCase):
    """Do `executar()` a string que sai na tela."""

    def setUp(self):
        self.user = User.objects.create_user(username="vitor", password="x")
        ctx, _ = IAContextoConversa.objects.update_or_create(
            user=self.user,
            defaults={
                "estado_atual": "NENHUM",
                "intent_pendente": "",
                "dados_coletados": {},
            },
        )
        self.ctx = ctx

    # ------------------------------------------------------------------
    def test_a_confirmacao_mostra_o_valor_que_chegou(self):
        """A ligacao. `executar` passa `params` ao texto de confirmacao."""
        r = sandbox.executar(
            self.user,
            "excluir_safra",
            {"safra": "2025/26", "confirm": False},
        )
        resposta = str(r.get("resposta") or "")

        self.assertTrue(
            r.get("needs_confirm"),
            f"a escrita destrutiva nao pediu confirmacao: {resposta!r}",
        )
        self.assertIn(
            "2025/26",
            resposta,
            "o valor NAO chegou a confirmacao. O produtor le uma pergunta que "
            f"nao identifica o objecto e responde 'sim' as cegas: {resposta!r}",
        )

    def test_o_ano_da_safra_muda_a_pergunta(self):
        """Duas safras, duas perguntas. Este e' o teste que mata o defeito
        original — a pergunta era identica para qualquer safra."""
        perguntas = []
        for safra in ("2025/26", "2027/28"):
            IAContextoConversa.objects.update_or_create(
                user=self.user,
                defaults={
                    "estado_atual": "NENHUM",
                    "intent_pendente": "",
                    "dados_coletados": {},
                },
            )
            r = sandbox.executar(
                self.user, "excluir_safra", {"safra": safra, "confirm": False}
            )
            perguntas.append(str(r.get("resposta") or ""))

        self.assertNotEqual(
            perguntas[0],
            perguntas[1],
            f"a confirmacao e' identica para safras diferentes: {perguntas[0]!r}",
        )
        self.assertIn("2025/26", perguntas[0])
        self.assertIn("2027/28", perguntas[1])

    def test_o_que_sera_apagado_esta_no_texto(self):
        """Nao basta mostrar a safra: tem de dizer QUE e' que desaparece."""
        IAContextoConversa.objects.update_or_create(
            user=self.user,
            defaults={
                "estado_atual": "NENHUM",
                "intent_pendente": "",
                "dados_coletados": {},
            },
        )
        r = sandbox.executar(
            self.user,
            "excluir_safra",
            {"safra": "2025/26", "tarefas": 14, "confirm": False},
        )
        resposta = str(r.get("resposta") or "")
        self.assertIn("14", resposta, f"o numero de tarefas sumiu: {resposta!r}")

    def test_nada_e_apagado_antes_do_sim(self):
        """O gate continua a valer. Esta correccao e' sobre O QUE se mostra,
        nao sobre SE se mostra."""
        from app.models import Safra

        r = sandbox.executar(
            self.user, "excluir_safra", {"safra": "2025/26", "confirm": False}
        )
        self.assertTrue(r.get("needs_confirm"))
        self.assertEqual(Safra.objects.count(), 0, "a safra foi apagada sem 'sim'")

    def test_a_instrucao_para_o_modelo_nao_vaza_na_tela(self):
        """`descricao` e' escrita PARA O MODELO. Echoa-la ao produtor punha a
        unica barreira antes de apagar uma safra coberta de engenharia."""
        IAContextoConversa.objects.update_or_create(
            user=self.user,
            defaults={
                "estado_atual": "NENHUM",
                "intent_pendente": "",
                "dados_coletados": {},
            },
        )
        r = sandbox.executar(
            self.user, "excluir_safra", {"safra": "2025/26", "confirm": False}
        )
        resposta = str(r.get("resposta") or "")
        for marca in ("INSTRUÇÃO", "INSTRUCAO", "use para", "obrigatório por"):
            self.assertNotIn(
                marca.lower(),
                resposta.lower(),
                f"a instrucao interna vazou para o produtor: {resposta!r}",
            )

    def test_um_campo_obrigatorio_em_falta_pergunta_nao_confirma(self):
        """Este caso mudou de significado durante o teste, e vale a pena dizer
        porque.

        A primeira versao afirmava que um campo vazio aparecia como "nao
        informado" na confirmacao. O sistema respondeu "De que safra?" — e
        estava certo: `safra` esta' em `required_fields`, e confirmar antes de
        saber QUE safra e' apagar a confirmar as cegas, que e' exactamente o
        defeito que se esta a corrigir.

        Exigir aqui a confirmacao seria exigir o comportamento errado. O que
        este caso afirma e' o que o sistema faz: perguntar, e nao confirmar.

        A cobertura de "nao informado" fica no nivel unitario
        (`tests/test_confirmacao_mostra_o_alvo.py`), onde se aplica aos campos
        OPCIONAIS que chegam vazios ate a confirmacao.
        """
        IAContextoConversa.objects.update_or_create(
            user=self.user,
            defaults={
                "estado_atual": "NENHUM",
                "intent_pendente": "",
                "dados_coletados": {},
            },
        )
        r = sandbox.executar(
            self.user, "excluir_safra", {"safra": "", "confirm": False}
        )
        resposta = str(r.get("resposta") or "")

        self.assertFalse(
            r.get("needs_confirm"),
            "confirmou sem saber que safra — o proprio defeito que se corrige",
        )
        self.assertIn(
            "safra",
            resposta.lower(),
            f"devia ter perguntado qual a safra: {resposta!r}",
        )
