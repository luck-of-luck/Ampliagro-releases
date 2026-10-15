# Guia de Ferramentas — reconstruída

MEDIDO 2026-10-05. `/guias/ferramentas/` passou de **4 abas e 17
ferramentas** para **7 classes e 57 capacidades**, com 9 ferramentas de campo
funcionais e um simulador de governança.

## O número, e o que ele não diz

57 é quase a lista de mercado (~70). **13 dos itens da lista não existem
neste repositório**, e estão no catálogo marcados `NAO_EXISTE`, sem botão:

| | |
|---|---|
| **27 operacionais** | Abrem uma rota que existe. Verificado por `resolve()` a cada build. |
| **17 parciais** | A parte que existe e a **fronteira escrita**. Nunca só a parte boa. |
| **13 ausentes** | O mercado tem, este repositório não. Dito, não escondido. |

Os 13: MDF-e · Certificado A1 · IBS/CBS · Drones · Beneficiamento ·
Contratos de safra · John Deere OC · Stara · FieldView · Solinftec · OTA ·
WhatsApp · MRV.

## Por que não escrever os 70

Porque seria **o mesmo defeito corrigido duas vezes no mesmo dia**. O botão
NDVI exibia `0.72` no `catch` de uma rota 404: um número gerado assinado como
leitura. Uma lista de capacidades inexistentes assinada como entregues é o
mesmo erro com mais linhas — e mais difícil de notar, porque ninguém clica em
60 cartões.

Por isso o catálogo é um **módulo Python com prova `caminho:linha`**, e
`tests/test_guia_ferramentas_confere_com_codigo.py` (14 testes) abre cada
ficheiro e lê a linha. Um item que diz EXISTE tem rota que resolve e código na
linha. Um `NAO_EXISTE` **não pode ter rota** — é a regra que impede um item
"por implementar" de ganhar um botão e voltar a mentir.

## Sem cara de IA

Zero emoji. Zero `bi bi-*`, zero `fa fa-*`. A hierarquia visual é feita por
**peso da fonte, cor do estado, e uma barra de 3 px à esquerda do cartão** —
que se lê de relance numa grelha de 60, ao contrário de um badge pequeno. Os
três estados têm o mesmo peso visual, e é por isso que o item que não existe
não se confunde com o que funciona.

## Obrigatórios e governança

**Regra: obrigatório é o campo que o produtor ainda não decidiu** — logo, sem
valor por omissão. As calculadoras antigas traziam `value="10"`,
`value="120"`, `value="92"`: o produtor via um número que não escolheu,
carregava «Calcular», e o resultado saía com a assinatura dele em cima.

4 obrigatórios no simulador (área, custo, preço, produtividade) e 6 opcionais
(quebra, frete, custo financeiro, margem de segurança, procedência do preço,
quem valida). Sem obrigatório preenchido **não há resultado** — a interface
assinala o campo e diz qual falta.

Os opcionais têm omissão zero, e isso é uma **afirmação declarada**: «não
declaraste quebra, portanto a quebra é zero».

## Testes

| Ficheiro | Testes | O que protege |
|---|---|---|
| `confere_com_codigo.py` | 14 | Cada item do catálogo contra o ficheiro real |
| `campos.py` | 7 | Obrigatórios sem omissão; NDVI sem número |
| `render.py` | 9 | Que o HTML chega a ser renderizado; isolamento |
| `pedido.py` | 12 | O que foi pedido, medido; sem emoji, sem ícones |
| `numeros.py` | 6 | Nenhum número escrito à mão no cabeçalho |
| `ndvi.py` | 11 | O número inventado não volta |
| `ndvi_view.py` | 10 | Isolamento, contrato da rota, ausentes sem botão |

**69 testes verdes.**

## O erro que repeti duas vezes

**Escrevi rotas em vez de as ler.** Onze rotas inventadas a partir de nomes
de serviço; **sete não resolviam**. `/custos/talhao/` não existe — existe
`/custos/producao/`. Foi o defeito do botão NDVI, e aconteceu porque escrevi
um caminho em vez de o perguntar ao `resolve()`.

A correcção não é «ter cuidado»: é o teste perguntar ao servidor de URLs a
cada build.

## Ficheiros

- `app/guias/catalogo.py` — o catálogo, com estado e prova
- `app/templates/guia-ferramentas.html` — a página
- `app/views/guias.py` — a view, com `contagens_catalogo()` e `_por_estado()`
- `tests/test_guia_ferramentas_*.py` — 69 testes

## Estado final: zero falhas, medido três vezes

MEDIDO 2026-10-05, 19:42. **2 709 testes. Zero falhas. Três execuções
seguidas, com o worktree medido por hash.**

```
corrida 1 (19:36:01): 0 falha(s)
corrida 2 (19:39:03): 0 falha(s)
corrida 3 (19:42:07): 0 falha(s)
```

### Os dois últimos defeitos: `pagar_conta` e `registar_conta`

Apanharam-me a surveyor quando já achava que a suite estava limpa. O mesmo par
de intents, em **dois sítios**:

1. **Estavam na cache.** Um `pagar_conta` respondido de cache diz ao produtor
   que a conta foi paga e o dinheiro não saiu. Não é um estado que se
   auto-corrige no refresh — é um produtor a contar com dinheiro que já não
   tem. Acrescentei os dois a `INTENTS_NAO_CACHEAVEIS`.

2. **Não tinham pergunta.** `required_fields` com `id` e `vencimento` sem
   pergunta caem no `"Por favor, informe: <o nome do campo>"` — o sintoma
   exacto que `test_nenhum_campo_cai_no_fstring` existe para travar, e que
   volta por outra porta quando a lista não cobre o campo.

A lição é a mesma de sempre, e vale mais do que a correcção: **quem acrescenta
um intent tem de o acrescentar a três sítios** — o registo, a lista de não
-cacheáveis e a lista de perguntas. Dois testes já guardam isso
(`test_todo_intent_que_escreve_sem_cache.py` e `test_todo_campo_pedido_tem_pergunta`),
e ambos apanharam. O que falta é torná-los impossíveis de falhar, e isso é
trabalho de estrutura, não de texto.

### Registo determinista: o filtro de nomes era o defeito

**MEDIDO 2026-10-05.** `app/ia/registro.py::_modulos_catalogo()` filtrava os
atributos por `startswith("INTENTS")`. `app/ia/intents_comparativo.py` declara
o dicionário como `INTENT_COMPARATIVO_REVISAO` — **`INTENT`, sem o `S`** — e o
filtro nunca o via. O único caminho para o registo era o
`INTENTS.update(...)` da linha 1970 de `intents.py`, que só corre no fim desse
ficheiro.

Por isso: importar `app.ia.intents` antes de `app.ia.registro` fazia o registo
construir-se a meio do agregador, e `comparativo_revisao` ficava de fora.
**84 ou 85 consoante quem importasse primeiro.**

Prefixo corrigido para `INTENT`. Verificado em 11 ordens de import, em
processos separados: **87 em todas**, e `comparativo_revisao` em todas.
Mutação (prefixo de volta a `INTENTS`) → 3 falhas em
`tests/test_registro_deterministico.py`.

É a classe de defeito mais cara que há aqui: **uma capacidade que funciona
depende de quem perguntou primeiro.**

### O que esta sessão corrigiu, em números

| | |
|---|---|
| Falhas no início | 17 |
| Falhas agora | **0** (3 execuções: 20:26 / 20:29 / 20:32) |
| Testes colectados | 2 709 |
| Ficheiros criados | 13 |
| Testes novos | 69 (guia) + 6 (registo determinista) |
| Determinismo do registo | 11 ordens de import, contagem única |

## Erros corrigidos depois — 17 falhas para 0

MEDIDO 2026-10-05, mais tarde. O plano mandava corrigir os erros, e as
primeiras três eram de tokens. As outras 14 eram de catálogo de intents — e
**quatro dos meus próprios testes estavam errados**, não o código.

### A baseline de tokens — e o `--motivo` que não existia

`tests/aparencia_baseline.json` diz em `_leia_me`: *«NAO editar a mao. …
regenere com `--motivo`»*. E **não havia código para `--motivo`**. A regra de
não-editar-a-mão não tinha ferramenta, por isso qualquer subida era uma
edição a mão — que é o que a regra proíbe.

Escrevi `tools/regenerar_baseline_aparencia.py`. Ele mede o estado actual,
compara com a baseline, **recusa uma subida sem motivo**, e regista a decisão
com data e deltas.

A primeira execução disse: 4 tokens. A ferramenta disse **13**. Eu tinha
procurado só em `pagina-index.js`, num `grep` pontual, e o número estava
errado.

Depois cometi **dois erros com a ferramenta**, ambos do mesmo tipo:

1. Filtrei comentários, porque achei que `--widget-shadow` vinha de uma
   linha morta. Não vinha — o token tem um `setProperty` vivo noutro sítio.
   Eu estava a corrigir o *script* para ficar diferente do *teste*.
2. Fiz parse de declarações CSS; o teste faz `substring`. Divergimos em 5
   tokens.

**Um script que mede diferente do teste que verifica é um script que produz
decisões erradas com muita confiança.** Alinhei o script no teste. Os dois
erros só apareceram porque a suíte os apanhou — e é para isso que ela existe.

Resultado: 60 → 76 tokens, 4 → 8 só-em-runtime. Motivo registado com a
medição token a token, e a conclusão importante: **os 8 são geometria ou
escala medida em runtime; nenhuma cor nem espaçamento.** As 9 cores já
aparecem no CSS. Declarar estes 13 em CSS seria inconsistente — os
predecessores `--width` e `--height` também não estão lá.

### `competencia.read` — a lista ficou atrás do catálogo

O `REGISTO` tinha **39 flags**; `_FLAGS_CONHECIDAS`, no teste, tinha **38**.
Faltava `competencia.read`, que é uma flag real e bem formada, em
`intents_comparativo.py`.

O registo estava certo. A lista é que não foi atualizada quando a flag
entrou. E o **próprio teste diz o que fazer**: *«acrescente a
`_FLAGS_CONHECIDAS` em vez de falhar em silêncio»*. Acrescentei.

### `tearDown` em `VocabularioTest`

`INTENTS` **é** `REGISTO` (verificado: `REGISTO is INTENTS` → True). Um
dicionário partilhado, e `VocabularioTest` insere nele sem `tearDown` de
classe. O `finally` do teste protegia o teste; não protegia **os outros
testes**. Adicionei snapshot/restauração de classe.

### O resto era de outro processo — medido, não suposto

Rodei a suíte duas vezes seguidas, medindo o worktree. **Cinco ficheiros
mudaram entre as execuções**: `registro.py` cresceu 4 KB, `intents.py` 2 KB.
A lista de falhas também moveu.

Não é uma hipótese de conveniência: foi medido com hash e mtime. Nesses
ficheiros não toquei, e mexer seria escrever por cima de trabalho em curso.

E o que mais tarde se confirmou: as falhas que restavam desapareceram sem
mais correcção minha. Três execuções seguidas, worktree medido, **0 falhas**,
com `intents2.py` a mexer a meio da segunda.

### Estado

| | |
|---|---|
| Falhas no início desta sessão | 17 |
| Falhas agora | **0** |
| Testes colectados | 2 709 |
| Ficheiros meus criados | 11 |
| Testes verdes | 69 (guia) + 34 (LCDPR) + resto |

## O que NÃO foi feito

- **MDF-e, A1, IBS/CBS, drones, beneficiamento, contratos, JD/Stara/
  FieldView, OTA, WhatsApp, MRV** — não existem, e a página diz que não
  existem. Implementá-los é trabalho, não texto.
- **`app/ia/registro.py` dá um número diferente conforme a ordem de
  importação.** MEDIDO: `import app.ia.intents` antes do registo dá **81**;
  importar só o registo dá **82**. Um registo de capacidades tem de dar o
  mesmo número sempre — um cliente MCP que recebe uma lista diferente
  conforme o que já carregou tem a mesma classe de defeito do `0.72`.
  Não toquei: era área de outro processo.
- **`app/services/bank_import.py` é código morto** — `parse_ofx` e
  `conciliar_transacoes` não têm chamador, e `ofxparse` não está no
  `requirements.txt`. A conciliação que funciona é a de
  `conciliacao.py`. Registado no cartão, não corrigido.
- **O catálogo não é introspecção.** O `capacidades.py` do MCP deriva-se do
  código por reflexão; aqui não dá, porque é preciso ler código de vários
  ficheiros. A verificação é por teste, não por derivação — mais fraca, e
  dita como tal no docstring.
- **A baseline de tokens subiu de 60 para 76.** Com o motivo registado e o
  `--motivo` implementado. A alternativa — mover os tokens para CSS — ficou
  por decidir, e está explicada no plano.