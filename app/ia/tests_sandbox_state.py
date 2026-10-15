"""A state-machine da AmplIA nao pode "colar" a proxima mensagem.

O `sandbox.executar` guarda o estado da conversa em `IAContextoConversa`
(`NENHUM` / `COLETANDO_DADOS` / `AGUARDANDO_CONFIRMACAO`). O ramo
`COLETANDO_DADOS` (sandbox.py) assume que a entrada do produtor responde ao
primeiro campo ainda vazio e depois segue o fluxo.

O invariant que este ficheiro existe para travar: quando a COLECAO TERMINA --
todos os `required_fields` preenchidos -- o estado tem de voltar a `NENHUM`.
Se nao voltar, a proxima pergunta do produtor ("e o estoque?") e engolida como
resposta de um campo que ja nao existe, e o produtor fica sem resposta sem
saber porque.

Hoje o bug esta encoberto: todo intent com `required_fields` tambem tem
`requires_confirmation`, entao o ramo `AGUARDANDO_CONFIRMACAO` vem logo a
seguir e sobrescreve o estado. O primeiro teste abaixo fixa essa premissa
(invariant de catalogo); o segundo reproduz o bug de verdade, com um intent
de leitura que coleta mas nao confirma -- a forma como um intent novo entra em
producao sem ninguem notar.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase

from app.ia import sandbox
from app.ia.sandbox import INTENTS
from app.models import IAContextoConversa


class ColetaDeDadosTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("produtor", password="x")

    def _contexto(self):
        return IAContextoConversa.objects.get(user=self.user)

    # ------------------------------------------------------------------
    # 1. Invariant de catalogo: nenhuma colecaao sem confirmacao
    # ------------------------------------------------------------------

    def test_intent_com_coleta_exige_confirmacao(self):
        """Premissa que hoje engole o bug do estado.

        Se isto quebrar, o ramo COLETANDO_DADOS passa a executar intent sem
        nunca passar por AGUARDANDO_CONFIRMACAO -- e o estado fica preso.
        """
        sem_confirmacao = [
            nome
            for nome, spec in INTENTS.items()
            if spec.get("required_fields") and not spec.get("requires_confirmation")
        ]
        self.assertEqual(
            sem_confirmacao,
            [],
            f"intents que coletam dados sem exigir confirmacao: {sem_confirmacao}",
        )

    # ------------------------------------------------------------------
    # 2. O bug: estado preso em COLETANDO_DADOS
    # ------------------------------------------------------------------

    def test_estado_nao_fica_preso_depois_da_coleta(self):
        """Reproduz: intent de leitura que coleta e nao confirma.

        Cria um intent temporario no catalogo -- e o que acontece quando
        alguem adiciona um intent de leitura com `required_fields` e esquece
        `requires_confirmation`.
        """
        executado = []

        def handler(user, params, ctx):
            executado.append(dict(params))
            return {"ok": True, "resposta": "relatorio pronto"}

        INTENTS["teste_leitura_com_coleta"] = {
            "descricao": "intent de teste que coleta e nao confirma",
            "exemplos": [{"nome": "x"}],
            "flags": ["relatorio.read"],
            "required_fields": ["nome"],
            "handler": handler,
        }
        try:
            # 1a chamada: falta o campo -> COLETANDO_DADOS
            r1 = sandbox.executar(
                self.user, "teste_leitura_com_coleta", {}, via="teste"
            )
            self.assertEqual(r1.get("state"), "COLETANDO_DADOS")
            self.assertEqual(self._contexto().estado_atual, "COLETANDO_DADOS")

            # 2a chamada: o produtor responde o campo -> deve executar
            r2 = sandbox.executar(
                self.user,
                "teste_leitura_com_coleta",
                {},
                via="teste",
                meta={"entrada": "Fazenda Boa"},
            )
            self.assertTrue(r2.get("ok"), r2)
            self.assertEqual(len(executado), 1, "o handler devia ter executado")

            # HERE ESTA O BUG: com a colecao terminada e sem confirmacao
            # no meio, o estado tem de estar limpo.
            self.assertEqual(
                self._contexto().estado_atual,
                "NENHUM",
                "o estado ficou preso em COLETANDO_DADOS depois da coleta",
            )

            # 3a chamada: uma pergunta NOVA nao pode ser engolida
            r3 = sandbox.executar(
                self.user, "ajuda", {}, via="teste", meta={"entrada": "e o estoque?"}
            )
            self.assertTrue(r3.get("ok"), r3)
            self.assertTrue(
                len(executado) == 1,
                "a pergunta nova foi tratada como resposta de campo: "
                f"o handler rodou {len(executado)} vezes",
            )
        finally:
            INTENTS.pop("teste_leitura_com_coleta", None)

    # ------------------------------------------------------------------
    # 3. O caminho feliz: coleta + confirmacao limpa o estado
    # ------------------------------------------------------------------

    def test_coleta_com_confirmacao_devolve_para_nenhum(self):
        """Fluxo real: coleta -> confirma -> executa. O estado fecha."""
        executado = []

        def handler(user, params, ctx):
            executado.append(dict(params))
            return {"ok": True, "resposta": "talhao cadastrado"}

        INTENTS["teste_escrita_com_coleta"] = {
            "descricao": "intent de teste com confirmacao",
            "exemplos": [{"nome": "x", "area": "1"}],
            "flags": ["talhao.write"],
            "required_fields": ["nome", "area"],
            "requires_confirmation": True,
            "handler": handler,
        }
        try:
            r1 = sandbox.executar(self.user, "teste_escrita_com_coleta", {})
            self.assertEqual(r1.get("state"), "COLETANDO_DADOS")

            r2 = sandbox.executar(
                self.user, "teste_escrita_com_coleta", {}, meta={"entrada": "Sitio"}
            )
            self.assertEqual(r2.get("state"), "COLETANDO_DADOS")  # falta `area`

            # responde `area` -> agora a colecao fecha e o portao de
            # confirmacao fecha o ciclo
            r3 = sandbox.executar(
                self.user, "teste_escrita_com_coleta", {}, meta={"entrada": "12"}
            )
            self.assertTrue(r3.get("needs_confirm"), r3)
            self.assertEqual(self._contexto().estado_atual, "AGUARDANDO_CONFIRMACAO")

            r4 = sandbox.executar(
                self.user, "teste_escrita_com_coleta", {}, meta={"entrada": "sim"}
            )
            self.assertTrue(r4.get("ok"), r4)
            self.assertEqual(len(executado), 1)
            self.assertEqual(self._contexto().estado_atual, "NENHUM")
        finally:
            INTENTS.pop("teste_escrita_com_coleta", None)
