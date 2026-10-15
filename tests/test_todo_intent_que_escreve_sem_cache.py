"""Todo o intent que escreve tem de estar em `INTENTS_NAO_CACHEAVEIS`.

O PROBLEMA
==========
MEDIDO 2026-10-05: `INTENTS_NAO_CACHEAVEIS` (`app/ia/sandbox.py:102`) era uma lista escrita
a mao, enquanto a REGRA ja vivia em `somente_leitura()` — uma flag `write`,
`create` ou `comando`. Duas formas de dizer a mesma coisa, e a lista esqueceu
**20 dos 32** intents que escrevem.

O QUE ACONTECE
==============
O `sandbox` tem uma cache de respostas com TTL. Um intent em `INTENTS_NAO_CACHEAVEIS` e'
servido da cache e o handler **nao corre**. Um intent que escreve e fica de
fora responde com o resultado em cache e o produtor ouve "feito" sem ter sido
feito.

`remarcar_tarefa` e' o pior caso: adia uma data e confirma.
`criar_entidade` e `inserir_registro` sao o "criador livre" — escrevem o que a
pessoa pedir, sem tipo nem forma conhecida. Com TTL, "cria uma tabela de
forgets" pode dizer que ja existe.

POR QUE UM TESTE E NAO SO UMA CORRECCAO
=======================================
Corrigi a lista. A lista volta a desatualizar-se no proximo intent de escrita,
porque ninguem lembra de ir ver. Este teste e' o que faz a lista deixar de ser
uma opcao: nasce um intent com `flags: ["x.write"]` e a suite avisa antes de
alcancar o e-CAC de um produtor.
"""

import re

from django.test import SimpleTestCase

from app.ia.registro import REGISTO
from app.ia.sandbox import INTENTS_NAO_CACHEAVEIS

RX = re.compile(r"write|create|comando")


class TodoIntentQueEscreveEstaSemCache(SimpleTestCase):
    def _escreve(self, spec) -> bool:
        return any(RX.search(str(f)) for f in (spec.get("flags") or []))

    def test_nenhum_intent_que_escreve_fica_de_fora(self):
        """A regra. Um intent que escreve fora daqui repete a escrita."""
        fora = sorted(
            nome
            for nome, spec in REGISTO.items()
            if self._escreve(spec) and nome not in INTENTS_NAO_CACHEAVEIS
        )
        self.assertEqual(
            fora,
            [],
            f"intents que escrevem e nao estao em INTENTS_NAO_CACHEAVEIS: {fora}.\n\n"
            "OU ESTES ESCREVEM MESMO E TEM DE SAIR DA CACHE, ou a flag esta errada. "
            "Um intent com `write`/`create`/`comando` nas flags responde da cache "
            "sem correr o handler — o produtor ouve 'feito' sem ter sido feito.",
        )

    def test_a_lista_tem_intents_que_escrevem(self):
        """Trava de sanidade: se o registo esvaziar, este ficheiro passa a
        verde sem estar a medir nada."""
        escreve = [n for n, s in REGISTO.items() if self._escreve(s)]
        self.assertGreater(
            len(escreve), 20, "o registo tem menos intents de escrita do que o medido"
        )
        self.assertTrue(
            INTENTS_NAO_CACHEAVEIS & set(escreve),
            "INTENTS_NAO_CACHEAVEIS nao interseta nenhum intent de escrita — a lista "
            "desligou-se do registo",
        )

    def test_o_criterio_e_o_mesmo_da_regra(self):
        """`INTENTS_NAO_CACHEAVEIS` e `somente_leitura` tem de concordar no criterio.

        Se um usar `write` e o outro `write|create|comando`, voltam a ser duas
        coisas diferentes. Este teste fixa o mesmo padrao dos dois lados.
        """
        from app.ia.sandbox import somente_leitura

        for nome, spec in REGISTO.items():
            if nome in INTENTS_NAO_CACHEAVEIS:
                with self.subTest(intent=nome):
                    self.assertFalse(
                        somente_leitura(spec),
                        f"{nome} esta em INTENTS_NAO_CACHEAVEIS mas `somente_leitura` "
                        "diz que e' de leitura — os dois criterios discordam",
                    )

    def test_nao_ha_intent_de_leitura_em_sem_cache(self):
        """O inverso. Pôr uma leitura na lista custa uma query de menos e
        nenhuma mais — nao e' um perigo, mas e' ruido que esconde uma
        entrada errada."""
        leituras = sorted(
            nome
            for nome, spec in REGISTO.items()
            if not self._escreve(spec) and nome in INTENTS_NAO_CACHEAVEIS
        )
        self.assertEqual(
            leituras,
            [],
            f"intents de leitura em INTENTS_NAO_CACHEAVEIS: {leituras} — nao e' perigoso, "
            "mas enche a lista de entradas que nao Devem estar la",
        )
