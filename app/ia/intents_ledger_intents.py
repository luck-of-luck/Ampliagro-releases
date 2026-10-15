"""INTENTS do ledger — os seis serviços de dados, ligados à automação.

O registo. Os handlers estão em `intents_ledger.py`; aqui ficam as descrições
e os exemplos, que é o que a IA lê para decidir quando chamar.

## A regra das descrições

Cada descrição diz **quando NÃO usar**, como os outros intents já faziam
(`clima_agora`: "NÃO use para perguntas de SIM/NÃO"). Sem isso a IA chama a
ferramenta errada com frequência, e o produtor vê a resposta de uma pergunta
que não fez.

E cada uma carrega o carimbo `fonte_dado` na resposta — `medido`,
`sem_dado` ou `medido_com_aviso`. Um `None` mostrado como 0 é o defeito que
corrigi no DRE; aqui o risco é o mesmo e o lugar é a conversa.

## Todos só-leitura

`flags: ["*.read"]`. Nenhum destes escreve. A §VI do `8.md` fixa que a IA
não toca no layout do produtor sem ele pedir, e um factor de crédito que a IA
altera é um factor que alguém deixou de auditar.
"""

from __future__ import annotations

from app.ia.intents_ledger import (
    h_capacidade_pagamento,
    h_classificar_cfop,
    h_custo_producao,
    h_ibs_cbs,
    h_preco_referencia,
    h_zarc_safra,
)

INTENTS_LEDGER = {
    "capacidade_pagamento": {
        "descricao": (
            "INSTRUÇÃO IA: use para FACTORES de crédito — 'qual a minha "
            "capacidade de pagamento', 'quanto recebi e quanto gastei este ano', "
            "'qual o meu custo por hectare médio'.\n\n"
            "Devolve cada factor com `valor`, `fonte` e — quando falta — "
            "`motivo`. Um factor sem apuração vem como `null` com a frase do que "
            "falta; NUNCA como 0.\n\n"
            "NÃO use para decidir crédito: o campo `decisao_de_credito` é sempre "
            "null e o sistema não decide. Se o produtor pedir 'vou conseguir "
            "empréstimo', diga que estes são os FACTORES e que a decisão é do "
            "banco.\n\n"
            "NÃO use para custo por hectare de UMA safra — use `custo_producao`, "
            "que tem área e produção específicas."
        ),
        "exemplos": [
            "qual a minha capacidade de pagamento",
            "quanto recebi e quanto gastei neste ano",
            "qual o meu custo por hectare médio",
            "tenho margem para pedir um empréstimo?",
            "como está o meu endividamento",
        ],
        "flags": ["fin.read"],
        "handler": h_capacidade_pagamento,
    },
    "preco_referencia": {
        "descricao": (
            "INSTRUÇÃO IA: use para o PREÇO das vendas registadas na própria "
            "fazenda — 'a quanto vendi a soja', 'qual o preço da soja aqui', "
            "'quanto rendeu a última safra'.\n\n"
            "Devolve mediana, P25, P75 **e a estrutura do mercado**: quantas "
            "transações, em quantas fazendas, e que percentagem vai para a "
            "maior. A concentração costuma valer mais que a mediana — é poder "
            "de negociação.\n\n"
            "NÃO use para o preço de mercado externo (B3, Ceasa, CONAB): isso "
            "precisa de fonte externa configurada e não vem aqui.\n\n"
            "Se houver menos de 5 transações, o serviço diz que é amostra e não "
            "preço de mercado. **Repita esse aviso ao produtor** — publicar a "
            "mediana sem o `n` é o que ele viria a ler sem perceber."
        ),
        "exemplos": [
            "a quanto vendi a soja",
            "qual o preço da soja aqui",
            "quanto rendeu a última safra",
            "qual foi o preço médio da venda",
            "qual o preço de mercado da soja",
            "quanto eu venda por saca",
        ],
        "flags": ["fin.read"],
        "handler": h_preco_referencia,
    },
    "zarc_safra": {
        "descricao": (
            "INSTRUÇÃO IA: use para a JANELA ZARC de plantio — 'posso plantar "
            "agora', 'a soja está dentro da janela', 'qual a última data para "
            "plantar'.\n\n"
            "O veredito é por safra e tem TRÊS valores: `true` (dentro da "
            "janela), `false` (fora, com os dias) e `null` (não há ZARC "
            "carregado).\n\n"
            "NÃO transforme `null` em 'fora'. Uma safra sem ZARC carregado não "
            "está errada — está em desconhecido, e dizer que está fora é acusar "
            "o produtor de uma coisa que o sistema não sabe.\n\n"
            "NÃO use para outras janelas (ZARC de é outro país, e a de "
            "milho é outra cultura): a verificação é do UF e da cultura que a "
            "safra tem, e a propriedade tem de estar no estado certo. Se o "
            "produtor plantou onde não pode, diga qual é a janela **dele**."
        ),
        "exemplos": [
            "posso plantar soja agora",
            "a safra está dentro da janela de plantio",
            "qual a última data para plantar",
            "o talhão está na janela ZARC",
            "quando começa a janela de plantio do milho",
        ],
        "flags": ["safra.read"],
        "handler": h_zarc_safra,
    },
    "classificar_cfop": {
        "descricao": (
            "INSTRUÇÃO IA: use para saber o que um CFOP FAZ — 'o que é o CFOP "
            "5102', 'esse CFOP é entrada ou saída', 'compra ou venda'.\n\n"
            "Devolve o efeito no estoque, o tipo de lançamento e a categoria. Um "
            "CFOP que sai começa por 1/2/3 e é ENTRADA (despesa); começa por 5 "
            "e é SAÍDA (receita); 6/7 é apuração e não gera lançamento.\n\n"
            "NÃO use para importar uma NF-e — para isso o produtor carrega o "
            "ficheiro XML.\n\n"
            "NÃO use para o imposto de uma venda concreta: isso é `ibs_cbs`.\n\n"
            "Um CFOP fora da tabela do sistema é recusado com motivo. **Não "
            "adivinhe o sinal**: 1201 (retorno) e 1202 (devolução) começam "
            "igual e significam coisas diferentes."
        ),
        "exemplos": [
            "o que é o CFOP 5102",
            "esse CFOP é entrada ou saída",
            "o CFOP 1102 é compra ou venda",
            "classifica o CFOP 5901",
        ],
        "flags": ["fin.read"],
        "handler": h_classificar_cfop,
    },
    "ibs_cbs": {
        "descricao": (
            "INSTRUÇÃO IA: use para o IMPOSTO da reforma — 'quanto de IBS/CBS "
            "sobre esta venda', 'qual a alíquota', 'quanto fica o preço com "
            "imposto'.\n\n"
            "Devolve `apuravel`. Se for `false`, a tabela oficial não está "
            "carregada e o imposto é `null` com o motivo e **onde buscar a "
            "tabela**.\n\n"
            "NÃO invente a alíquota, mesmo que pareça óbvia. Dizer '0,9%' sem a "
            "tabela oficial verificada é inventar um índice fiscal, e o produtor "
            "paga errado e só descobre na fiscalização. Sem tabela, diga que "
            "não está carregado.\n\n"
            "NÃO use para o imposto JÁ Pago ou para a obligation de apurar: "
            "isto é a alíquota sobre uma base que o produtor informa, não a "
            "obrigação do exercicio. Para o que falta apurar na safra, o produtor "
            "precisa de um registo com o código do tributo da NF-e."
        ),
        "exemplos": [
            "quanto de IBS/CBS sobre 10 mil reais",
            "qual a alíquota de IBS agora",
            "quanto fica o preço com imposto",
            "a reforma tributária já está a valer",
        ],
        "flags": ["fin.read"],
        "handler": h_ibs_cbs,
    },
    "custo_producao": {
        "descricao": (
            "INSTRUÇÃO IA: use para o CUSTO de UMA safra — 'quanto me custou a "
            "soja deste ano', 'qual o custo por hectare da safra 2026', 'quanto "
            "custou por saca'.\n\n"
            "Precisa do `safra_id`. Se faltar, pergunte — não escolha a safra "
            "mais recente sozinho.\n\n"
            "NÃO use para a média entre safras ou para a capacidade de "
            "pagamento — são outros intents.\n\n"
            "Devolve `null` com motivo para o que não é apurável (sem área plantada "
            "não há custo por hectare). Diga isso ao produtor; **não arredonde "
            "para 0**."
        ),
        "exemplos": [
            "quanto me custou a soja deste ano",
            "qual o custo por hectare da safra",
            "quanto custou por saca",
            "custo de produção do talhão",
        ],
        "flags": ["safra.read", "fin.read"],
        "handler": h_custo_producao,
    },
}
