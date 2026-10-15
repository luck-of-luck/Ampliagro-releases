"""A automação prometida chega aos serviços que construí?

## A pergunta

Depois de construir `capacidade_pagamento`, `rede_precos`, `zarc`, `cfop`,
`reforma_tributaria` e `custo_producao`, **a IA consegue alcançá-los?**

Sem isto, os serviços existem, passam nos testes, e nenhum produtor — nem por
pergunta, nem por automação — lhes chega. Seriam código morto, que é a forma
mais cara de dizer "implementámos uma feature".

## Como o teste responde

Não por nome de módulo: os intents chamam-se `preco_referencia`, não
`rede_precos`. A verificação **inspeciona o código de cada handler** e vê qual
serviço ele chama. É o que interessa — não o nome, mas o que a automação de
facto executa.

A primeira versão deste ficheiro procurava `rede_precos` no texto dos
intents, e falhava mesmo depois de os seis estarem ligados: o nome do intent é
`preco_referencia`. **O teste estava errado, não o código** — a mesma lição
da §23I, outra vez.
"""

from __future__ import annotations

import inspect

from django.test import SimpleTestCase

from app.ia.intents import INTENTS

# serviço -> (o que o handler chama, o nome do intent que o executa)
#
# As duas colunas são diferentes e confundi-las foi o que fez a primeira
# versão deste teste falhar com os seis intents já ligados: `verificar_
# propriedade` é a FUNÇÃO, `zarc_safra` é o INTENT. Um teste que escreve a
# função num sítio e o nome no outro mede a nada.
SERVICOS = {
    "capacidade_pagamento": ("capacidade_pagamento", "capacidade_pagamento"),
    "rede_precos": ("preco_referencia", "preco_referencia"),
    "zarc": ("verificar_propriedade", "zarc_safra"),
    "cfop": ("classificar", "classificar_cfop"),
    "reforma_tributaria": ("calcular_ibs_cbs", "ibs_cbs"),
    "custo_producao": ("calcular_custo_producao", "custo_producao"),
}

NOMES_INTENTS = {v[1] for v in SERVICOS.values()}


def _servicos_alcancaveis():
    """Serviço -> nome do intent que o executa, lido do código do handler."""
    alcancaveis = {}
    for nome, spec in INTENTS.items():
        handler = spec.get("handler")
        if handler is None:
            continue
        try:
            fonte = inspect.getsource(handler)
        except (OSError, TypeError):
            continue
        for servico, (chamada, _intent) in SERVICOS.items():
            if f"{chamada}(" in fonte:
                alcancaveis.setdefault(servico, nome)
    return alcancaveis


class AutomacaoAlcancaServicosTest(SimpleTestCase):
    def test_cada_servico_construido_e_alcancaavel(self):
        """O número que interessa: 6 de 6."""
        alcancaveis = _servicos_alcancaveis()
        orfaos = sorted(set(SERVICOS) - set(alcancaveis))

        self.assertEqual(
            orfaos,
            [],
            f"servicos construidos que a automacao nao alcanca: {orfaos}. "
            "Enquanto esta lista nao estiver vazia, a feature existe mas o "
            "produtor nunca lhe chega.",
        )

    def test_o_alcance_e_por_intent_nomeado(self):
        """Cada serviço tem um intent com nome, não um serviço órfão.

        Um serviço alcançável por nome é descobrível: a IA lê a descrição e
        sabe que existe. Um serviço alcançável só por coincidência não é.
        """
        alcancaveis = _servicos_alcancaveis()
        self.assertEqual(
            len(alcancaveis),
            len(SERVICOS),
            f"alcance parcial: {alcancaveis}",
        )
        for servico, intent in alcancaveis.items():
            self.assertIn(
                intent,
                INTENTS,
                f"{servico} mapeia para um intent que nao existe: {intent}",
            )

    def test_todos_os_intents_do_ledger_sao_so_leitura(self):
        """Nenhum destes intents escreve.

        Um factor de crédito que a IA altera é um factor que alguém deixou de
        auditar. E a §VI do `8.md` fixa que a IA não mexe no que é do produtor
        sem ele pedir.
        """
        do_ledger = NOMES_INTENTS
        escritas = []
        for nome in do_ledger:
            spec = INTENTS.get(nome, {})
            flags = spec.get("flags", [])
            if not any("read" in f for f in flags):
                escritas.append(nome)

        self.assertEqual(
            escritas,
            [],
            f"intents do ledger sem flag de leitura: {escritas}",
        )

    def test_cada_intent_do_ledger_diz_quando_nao_usar(self):
        """A descrição diz quando NÃO usar.

        Sem isso a IA chama a ferramenta errada com frequência, e o produtor vê
        a resposta a uma pergunta que não fez. Os intents existentes no
        projecto já faziam isto (`clima_agora`: "NÃO use para perguntas de
        SIM/NÃO") — é a convenção, e um intent sem ela é um buraco.
        """
        faltam = []
        for intent in NOMES_INTENTS:
            desc = INTENTS.get(intent, {}).get("descricao", "")
            if "NÃO use" not in desc:
                faltam.append(intent)

        self.assertEqual(
            faltam,
            [],
            f"intents sem 'NÃO use' na descricao: {faltam}",
        )
