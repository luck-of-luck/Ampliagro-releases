# Entrega: orçado × realizado por talhão, e o resto desta sessão

**Para quem vem a seguir.** Isto não é um relatório do que fiz. É o que precisa
de saber para **complementar** esta trabalho sem a substituir.

Cada secção diz o que foi feito, **porquê**, e o que **não** deve fazer.

---

## 1. O headline: uma conta que não existia

O Ampliagro tinha as quatro entradas que a conta exige e não tinha a conta:

| entrada | onde |
|---|---|
| orçamento | `PlanoSafra.orcamento_estimado` |
| custo previsto por actividade | `AtividadePlanejada.custo_estimado` |
| dinheiro que mexeu | `LancamentoFinanceiro` ligado a `talhao`/`safra` |
| área | `Talhao.area_hectare` |

O que existia era `h_lucro_talhao` em `app/ia/intents3.py`: um `aggregate()`
dentro de um `for`. Três defeitos, todos sobre dinheiro.

### 1.1 Contava despesa não paga como custo

Filtrava só por `tipo`, ignorando `pago`. Um boleto em aberto aparecia como
dinheiro já gasto.

Isto é mais do que um erro de soma. **O LCDPR, no mesmo código, é de regime de
caixa** — `Q100` sai de `data_pagamento`. O produtor via um número de caixa na
conversa e podia comparar com um número de competência noutro ecrã, sem forma
de saber qual dos dois estava errado.

Agora só entra `pago=True`. O que ficou por pagar vai para uma coluna à parte,
`comprometido_despesa`.

**Não volte a ignorar o `pago`.** Se achar que "despesa registada" é
"despesa paga", olhe primeiro para `app/services/lcdpr.py`.

### 1.2 Descartava a despesa sem talhão

`filter(talhao=t)` salta combustível, frete, mão-de-obra — que quase nunca têm
talhão. O lucro por talhão saía inflado, sem nenhum aviso visível.

Agora o que não está alocado é reportado com valor e contagem.

**Não rateie nada.** Distribuir uma despesa comum por área é inventar o destino
do dinheiro, e custo atribuído ao talhão errado produz uma decisão agronómica
errada — não só um número errado. O que existe é `nao_alocado`, visível e
honesto.

### 1.3 Fazia N+1

`2 × len(talhoes) + 1` consultas → **3**, independentes do tamanho da fazenda.

Há teste que mede isto (`NadaDeNMaisUmaConsulta`) e **falha** se voltar a
crescer. Se acrescentar um `aggregate()` dentro de um ciclo, ele apanha.

---

## 2. Decisões deliberadas. Não são bugs.

### `None` sobrevive até ao fim. Orçamento ausente não vira `0`.

"Orçado 0" diz ao produtor que planeou gastar nada. "Sem orçamento" diz que
ninguém planejou. O primeiro leva a uma decisão; o segundo leva a um cadastro.
A celula vazia é `--`, nunca `0`.

Isto atravessa a dataclass inteira, e `as_dict()` serializa `None` como `None`.

### `Decimal` até ao fim, convertido **uma vez**, na fronteira

`(0.1 + 0.2)` em dinheiro é a razão clássica de um relatório não bater com o
extrato. A conta inteira corre em `Decimal`. O payload é JSON e
`json.dumps` não conhece `Decimal` — daí o `_json()`, **no limite**, depois da
soma. O texto que o produtor lê é formatado a partir do `Decimal`, não do
float.

Ordem errada (converter antes de somar) reintroduz `0.30000000000000004`.
Há teste para isso.

### `area_hectare` e `orcamento_estimado` são `NOT NULL`

Escrevi testes para "talhão sem área" e "plano sem orçamento". **A base de dados
recusa os dois.** Os testes ficaram a medir a restrição, não a fingir que o
estado existe.

Os guards `if not self.area_ha` e o fallback para soma de actividades **não são
alcançáveis pelo caminho normal**. São defesa (linha herdada, migração futura
que relaxe a coluna). Não conte com eles ao fechar um orçamento, e não escreva
um teste que finja o contrário.

### Duas ordenações, porque são duas perguntas

`qual talhão deu mais lucro` e `onde o dinheiro foi gasto` **não dão a mesma
resposta**. Um talhão pequeno com muita receita ganha; um grande com pouca
receita perde.

- `ResultadoCusto.por_ordem_de_custo()` — método da dataclass
- `ordenar_por_lucro(resultado)` — função de módulo

Nomes diferentes **de propósito**: uma função de topo com o mesmo nome do
método é o caminho para alguém escrever `resultado.ordenar_por_lucro()` e levar
`AttributeError` em produção. Já aconteceu uma vez nesta sessão.

O **texto** da IA responde ao intent (`lucro_talhao`) e por isso mostra lucro.
Cheguei a escrevê-lo ordenado por custo — o produtor perguntava por ganho e
recebia por gasto. Se alterar `resumo_para_ia`, mantenha-o a responder à
pergunta do intent.

---

## 3. Os testes que falham se alguém desfizer isto

Cada teste existe porque a versão anterior fez aquela coisa.

```bash
python -m pytest tests/test_custo_por_talhao.py \
                 tests/test_intento_custo_por_talhao.py
```

| ficheiro | guarda |
|---|---|
| `DespesaNaoPagaNaoECusto` | pendente não entra no realizado, nem conta como custo |
| `DespesaSemTalhaoNaoDesaparece` | não alocado é visível; o rácio não cresce sozinho |
| `OrcadoAusenteNaoEOrcadoZero` | `None` ≠ `0`; zero explícito calcula desvio |
| `NadaDeNMaisUmaConsulta` | o número de queries não cresce com o número de talhões |
| `CustosPorHectare` | `area_hectare` é `NOT NULL`; o guard produz `None` e não `0.00` |
| `IsolamentoPorPropriedade` | propriedade alheia é invisível |
| `test_o_payload_sobrevive_a_json_dumps` | o contrato é JSON; um `Decimal` a mais é um 500 |

`test_intento_custo_por_talhao.py` **ata o handler ao painel**: se o handler
recalcular a conta à maneira antiga, o produtor vê um número na conversa e outro
no ecrã, e não há forma de saber qual é o certo.

---

## 4. Os outros defeitos que apanhei nesta sessão

Registo-os porque cada um já custou uma falha de produção, e porque todos
foram **medidos**, não deduzidos.

### 4.1 O limiar do navegador divergia do servidor em 10×

`ia-local.js` usava `bestScore >= 0.6`; `app/ia/deteccao.py` usa
`LIMIAR = 0.06`. O navegador é uma **porta do mesmo algoritmo** — mesma lista
de `stop`, mesmo fallback por sobreposição. A mesma frase dava intents
diferentes conforme se perguntasse ao dock ou à API. Corrigido para `0.06`.

Nada disto abre uma escrita: `requires_confirmation` e o gate M3
(`_LIMIAR_ESCRITA`, 0.6) estão **antes** da execução. Um match fraco de
*leitura* é inofensivo.

### 4.2 O registo 0030 do LCDPR tinha perdido o marcador

Outra sessão transcreveu o enunciado oficial e passou a usar o `linha()` de
`app/services/lcdpr_layout.py`, mas a chamada ficou `linha(endereco, ...)` sem o
`"0030"`. O ficheiro saía com `|Sem Endereco|...` em vez de
`|0030|Sem Endereco|...` — um registo que a Receita não reconhece.

Uma linha, uma vírgula. `Q100CoerenciaTest` apanhou.

### 4.3 Colisão de URLs escondia o CRUD

`path("estoque/", ...)` declarado **depois** de `router.register()` sombreava o
router: a leitura funcionava e a escrita não. Os agregados foram para
`/api/estoque-resumo/` e `/api/maquinarios-resumo/`; o CRUD ficou em
`/api/estoque/` e `/api/maquinarios/`.

`tests/test_router_nao_sombreado.py` foi verificado **reintroduzindo o bug** e
vendo o teste falhar. Um teste que nunca falhou não se sabe se funciona.

### 4.4 Fixtures que passavam pelo motivo errado

`app/ia/tests.py::test_109_lucro_talhao` criava lançamentos **sem `pago`**. O
default do model é `False`. O teste "passava" só porque o handler antigo não
filtrava por isso — contava conta-a-pagar como despesa.

Ao corrigir o handler, o teste passou a falhar — e estava certo em falhar.
Ficou explícito, com o porquê em comentário.

Vale a pena desconfiar de qualquer teste que dependia do defeito que se
acabou de corrigir.

---

## 5. O que NÃO está feito

Não anuncie nada disto como entregue.

- **Não há ecrã.** O serviço e a resposta da IA existem; falta o painel onde o
  produtor compara orçamento e realizado lado a lado. `as_dict()` já entrega
  tudo o que a tela precisa.
- **NF-e/SEFAZ com NCM** continua inteiro.
- **Metodologia de carbono / chain-of-custody** — não implementada.
- **A suite não é verde-num-snapshot.** Duas falhas dependentes de ordem, de
  outros trabalhos. Ver §6.
- **Proveniência tem dois vocabulários**: `app/validators.py` (cinco estados)
  e `app/ia/proveniencia.py` (seis, com `simulado`). Não reconciliei.

### Duas premissas minhas que o código desmentiu

Vale a pena registar porque eu as assumi e errei, e o schema corrigiu-me:

1. `Talhao.area_hectare` é `NOT NULL` — não existe talhão sem área.
2. `PlanoSafra.orcamento_estimado` é `NOT NULL` — não existe plano sem
   orçamento, o que torna o fallback para soma de actividades inalcançável
   pelo caminho normal.

---

## 6. Estado medido no momento da entrega

```
2341 testes    2 falhas    13 suites .cjs OK
```

As duas falhas são de outro trabalho e não tocam esta entrega:

- `ComentarioDjangoNaoVazaTest::test_nenhum_comentario_multilinha_em_templates`
- `TagDeBlocoNaoVazaTest::test_nenhuma_tag_multilinha_em_templates`

**A suite não é verde-num-snapshot.** Isto é dívida estrutural: há fixtures e
sondas cujo resultado depende da ordem de execução. Passa isolado, falha no
conjunto. Isolar isto é trabalho de fundo e precisa de ser feito com calma —
é o que tornaria a suite verde de verdade.

O E2E tem WebGPU indisponível neste host
(`navigator.gpu.requestAdapter()` devolve `null`): a inferência real com
SmolLM2 **não foi validada aqui**.

---

## 7. Ao continuar

1. **Rode a suíte completa, não só os seus ficheiros.** `python -m pytest`.
   Fixture compartilhada é a fonte número um de "funciona aqui e falha lá".
2. **Se um teste falha depois de mexer em algo que outra sessão toca, confirme
   de que lado está o bug** antes de corrigir. Boa parte das falhas que vi
   nesta sessão era o outro lado a meio de escrever.
3. **Não escreva migração para modelos que outra sessão criou.** Já aconteceu:
   `app/models/caderno.py` apareceu sem migração e o teste de migração mandava
   explicitamente não a escrever.
4. **Medir antes de afirmar.** Scanner verde não é ausência de bug — é ausência
   de detecção. E o bandit/semgrep só reconhecem nomes em inglês: `SENHA` e
   `API_KEY` passam limpos num ficheiro em português. Se o alvo está em
   português, a varredura de segredos tem de ser feita por conta.

---

## Ficheiros desta entrega

**Novo**
- `app/services/custo_talhao.py` — a conta
- `app/services/lcdpr_layout.py` — layouts canónicos do LCDPR
- `tests/test_custo_por_talhao.py` — 30 testes, um por defeito
- `tests/test_intento_custo_por_talhao.py` — 12 testes, atam handler ao painel
- `tests/test_lcdpr_conformidade.py`
- `tests/test_router_nao_sombreado.py`
- `tests/test_revocacao_escrita_integracao.py`
- `tests/test_webhook_ttn_sem_auth.py`
- `tests/test_todo_intent_que_escreve_sem_cache.py`
- `tests/test_conftest_nao_apaga_dado_imutavel.py`
- `tests/test_fila_offline_aceita_escrita.py`
- `tests/test_sync_offline.py`
- `tests/test_precache_pwa.py`
- `docs/sistema/6.md` — estudo competitivo

**Alterado**
- `app/ia/intents3.py` — `h_lucro_talhao` passou a formatar a conta
- `app/services/lcdpr_export.py` — marcador `0030`
- `app/ia/deteccao.py` + `app/static/js/ia-local/ia-local.js` — paridade de limiar
- `app/api/urls.py` — colisão de URLs
- `app/ia/sandbox.py`, `app/ia/intents.py` — lista de caches imutável
- `app/tests_nfe_xxe.py` — fixture NF-e
