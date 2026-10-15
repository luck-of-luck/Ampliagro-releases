# AmplIA SKI - Comparativo (o que temos, medido em codigo)
# NOTA DE FORMATO, e' importante: `description:` tem de ser UMA LINHA. O parser
# desta pasta e' artesanal e nao le YAML de bloco (`>-`). As outras tres skills
# tambem estao assim. Se encolher a descricao num `>-`, a skill volta a ser
# lida como VAZIA — e foi exactamente o que aconteceu a versao anterior deste
# ficheiro, que vivia com `---` e chaves portuguesas.
name: amplia-comparativo
description: O que o Ampliagro tem, medido em codigo, das 50 capacidades do comparativo de mercado. Usar quando pedirem o que ja temos, em que dimensao estamos em falta, ou para decidir se vale construir uma capacidade nova. A TOOL e amplia_comparativo.
version: 1.2.0
triggers: ["o que voces tem", "o que ja existe", "comparativo", "concorrentes", "em que estamos", "lacuna", "gap", "prioridade", "ja temos isso", "falta o que"]
# handlers: intents REAIS do registo (85 entradas). Um nome aqui que nao exista e'
# uma tool inventada — `catalogo_skis()` conta-as. `amplia_comparativo` NAO entra
# aqui: e' uma tool de catalogo, nao um intent. Fica referido no corpo.
handlers: ["comparativo_revisao"]
# sem_intent: existe no codigo mas nao ha botao. Uma promessa nao cumprida, dita
# como promessa — e nao como capacidade.
sem_intent:
  medir_ampliagro: "existe em app/amplia_mcp/comparativo.py. O caminho publico e' a tool amplia_comparativo."
  divergencias: "existe em app/amplia_mcp/comparativo.py. Nao ha intent; le-se no retorno de amplia_comparativo, campo `divergencias`."
performance: {cache: 300, flags: ["comparativo.read"]}

A TOOL: `amplia_comparativo(grupo=...)`. Filtra por grupo (`'A. Fiscal'`,
`'B. Financeiro'`, `'C. Campo'`, `'D. Pecuaria'`, `'E. Logistica'`, `'G. Maq/IA'`,
`'H. Dados'`). Sem argumento devolve as 50.

## O que a tool devolve, e qual campo responde a pergunta

Cada capacidade vem com DOIS campos de estado. Confundi-los e' o erro mais caro
desta skill:

| campo | o que e' | quem manda |
|---|---|---|
| `veredicto` | C / E / N, com `evidencia_ficheiro` | **ESTE.** E' a resposta. |
| `estado` | cobertura da sonda automatica | so diagnostico |

`veredicto`:
- **C** — confirmado em codigo. `evidencia_ficheiro` traz `app/x.py:12`.
- **E** — existe, mas a prova e' fraca: um campo, uma constante, um decorator.
- **N** — medido, nao existe.

`natureza` separa duas coisas que a planilha misturava:
- **LACUNA COMPETITIVA** — existe lider com evidencia de fonte. Aqui ha alguem a
  frente e vale a pena olhar.
- **SEM BENCHMARK** — nenhum dos 100 tem evidencia de fonte. Falhar aqui NAO e'
  ficar atras de ninguem; e' escolha de produto, nao buraco de mercado.

## AS TRES REGRAS

1. **Responde por `veredicto`, nunca por `estado`.**
   `estado: nao_verificada` significa que a busca automatica nao cobre esta
   capacidade — NAO que esteja por medir. As 50 tem veredicto adjudicado. Se
   responderes por `estado`, vais dizer que um buraco confirmado e' desconhecido,
   ou o contrario.

2. **NUNCA afirmes que somos primeiros, melhores ou lideres.**
   A matriz esta 98,6% por medir: 4 928 das 5 000 celulas sao `?`. Nao ha medicao
   que sustente. Se te perguntarem "como estamos frente a concorrencia", diz que
   a comparacao nao esta medida, e diz o que ESTA medido — o nosso lado. A
   `natureza` diz se existe lider com evidencia; so nesse caso podes dizer que ha
   alguem a frente.

3. **Nao transformes `SEM BENCHMARK` em prioridade.**
   E' a escolha mais tentadora e a mais errada. Ha 3 dimensoes assim.

## Porque nao ha ranking

A matriz de origem (`docs/sistema/comparativo/comparativo-100x50.xlsx`) tem
100 aplicacoes x 50 capacidades. **Medido: 4 928 das 5 000 celulas (98,6%) sao
`?`** — ninguem mediu se aquele produto tem aquela capacidade. So 68 estao
confirmadas.

Um ranking construido sobre isto seria uma lista de 100 produtos com 98,6% de
dados inventados. Nao e' uma aproximacao: e' uma affirmacao sem medicao, e e'
exactamente o defeito que este sistema nao pode ter.

A metade do comparativo que E' legivel e' o nosso lado — mede-se no codigo. O
veredicto vem de `docs/sistema/comparativo/vereditos.py`, com `ficheiro:linha`.

## O numero de hoje

25 confirmadas, 7 enfraquecidas, 18 ausentes. Das 18 ausencias, **15 sao lacunas
competitivas** e **3 nao sao gap** — O08 drones, L04 beneficiamento e M05 OTA de
firmware, onde nenhum dos 100 tem evidencia de fonte.

Por grupo: Campo e o mais forte (8 C de 9). Fiscal e o mais fraco (2 C, 2 E, 4 N).

## Quando NAO usar

- Para saber o que a AmplIA **faz** (intents, acoes) -> `amplia_catalogos`.
- Para montar uma tela -> `amplia_catalogos` primeiro, depois
  `amplia_desenhar_pagina`.
- Para um numero de uma fazenda -> o widget medido. O comparativo e' sobre
  produto, nao sobre dados de ninguem.

Esta skill e' para o **produto**, nao para a **fazenda**. Confundir as duas da o
erro mais caro que ha: mostrar a um produtor o score de um produto como se fosse
o resultado dele.

## Uma nota de disciplina

O veredicto ja foi corrigido duas vezes por auditoria de ancoras, nos dois
sentidos. Uma capacidade estava marcada `N` quando o codigo existia (ISOBUS em
`services/vra.py:13`). E cinco estavam marcadas `C` ancoradas num nome de campo
ou num decorator — que, pela propria definicao de `vereditos.py`, e' `E`. Um
veredicto que ninguem olhou para a linha onde aponta e' uma opiniao com formato
de medicao.
