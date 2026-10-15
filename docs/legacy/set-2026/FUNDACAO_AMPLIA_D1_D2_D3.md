# Fundação do AmplIA — D1, D2 e D3

> Este documento registra as três decisões de arquitetura tomadas antes da
> BUILD 0 do `MAPA_DE_IMPLEMENTACAO_AMPLIA.md`. Ele existe porque cada uma
> delas é irreversível depois que entra em migration: nome de model, formato de
> dado e contrato de chamada mudam sem quebrar nada em silêncio.
>
> Data: 2026-09-26 · Estado: implementado e coberto por 47 testes.

---

## Por que essas três primeiro

Os documentos da fase pedem uma coisa só: **"valide a arquitetura do projeto
atual antes de inserir pastas MCP"**. A auditoria encontrou quatro fatos que
mudaram o desenho:

| Achado | Consequência |
|---|---|
| Não há **nenhuma** chamada de LLM no projeto (zero imports de `openai`/`anthropic`/`ollama`) | Na primeira versão a AmplIA era determinística: ~114 KB de intents em `app/ia/intents*.py` com sandbox e auditoria próprios |
| O banco é **SQLite**, não PostgreSQL | `JSONField.__contains` — a forma natural de consultar JSONB — **não funciona**: `NotSupportedError` |
| `DynamicApp/DynamicField/DynamicRecord` **não existem** | BUILD 2 é campo aberto; e os dois docs discordam nos nomes |
| `app/ia/sandbox.py` já tem anti-injeção, allowlist de fontes e trilha de auditoria | BUILD 3 está ~40% pronto, de um jeito **melhor** que o previsto (primeira versão, não LLM) |

---

## D1 — Local-first, LLM como opt-in

**Decisão.** O `llm_gateway` nasce com o provedor `local` como **padrão**. LLM
entra como opt-in explícito, na mesma linha do conceito de allowlist que
`app/ia/fontes.py` já usa.

**Por que, e não "AmplIA é LLM".** O plano assume LLM. Na primeira versão o código era determinístico
e auditado. Se o LLM fosse o padrão:

- a diretriz 4 (offline-first) passaria a depender de rede e de chave;
- a "soberania sobre os dados" — o diferencial que o `PLANO_CRIADOR_LIVRE`
  vende textualmente — seria contradicted no primeiro dia;
- o produtor no meio do talhão, sem sinal, perderia o formulário.

**Contrato.** `chamar()` **nunca levanta**. Devolve sempre as mesmas chaves:

```python
{"ok": bool, "texto": str, "provedor": str,
 "pedido": "local" | "remoto", "erro": str, "duracao_ms": int}
```

Um provedor remoto que estoura é registrado e o local assume. Resposta offline
é uma **resposta honesta** — diz o que está desligado e o que o sistema sabe
fazer de verdade com os dados da fazenda. Não é um placeholder: inventar texto
parecido com IA custaria ao produtor a garantia de que o que a AmplIA afirma
veio do banco dele.

**Isolamento.** Ninguém importa `openai` ou `anthropic` fora de
`app/ia/llm_gateway/`. A allowlist é fechada: um nome de provedor desconhecido
**não** vira `importlib` dinâmico — é recusado e o local assume.

**Configuração** (settings tem precedência sobre ambiente):

```python
LLM_GATEWAY = {
    "provedor": "local",        # padrão
    "chave": "",                # ou AMPLIA_LLM_CHAVE
    "modelo": "",
    "base_url": "",
    "timeout_s": 20.0,
}
```

`disponivel()` devolve diagnóstico para a UI **sem devolver a chave**.

---

## D2 — Camada agnóstica, sem portar agora

**Decisão.** Não portar para PostgreSQL nesta fase. Em vez disso, a camada de
metadados usa **só o subconjunto que os dois backends aceitam**, e trata
JSONB como melhoria de deploy.

**A armadilha medida, não suposta.** Neste projeto, em SQLite:

| Verbo | SQLite | Postgres |
|---|---|---|
| `JSONField` roundtrip | OK | OK |
| chave = valor (`dados__status='ativo'`) | OK | OK |
| chave aninhada (`dados__a__b=1`) | OK | OK |
| chave existe (`dados__has_key=`) | OK | OK |
| **contém par (`dados__contains=`)** | **`NotSupportedError`** | OK |

Código escrito no Postgres e portado para dev em SQLite quebraria **em
runtime**, no meio de uma listagem, longe do commit que causou.

**O que a camada garante.** `contem()` devolve o mesmo conjunto nos dois
backends: usa `__contains` (`@>`, indexável por GIN) onde existe e degrada
para uma sequência de key transforms onde não. A degradação **não** usa
`__icontains` no texto do JSON — `{"codigo": 1}` casaria com `{"codigo": 12}`.
A comparação é por chave, valor a valor. Esse caso tem teste.

**Onde o Postgres rende mais.** `json_portatil.diagnostico()` diz se o
`__contains` está disponível e qual estratégia está em uso. O índice GIN fica
fora do model de propósito: `GinIndex` vive em `django.contrib.postgres` e
não existe no SQLite, então declará-lo quebraria o `check` de todo ambiente
SQLite — inclusive o que roda os testes. Fica como DDL de deploy, e só faz
sentido acima de 10 mil linhas (`vale_a_pena_gin`).

**`JSONFieldPortatil`.** O `JSONField` do Django usa `json.dumps` puro, que não
sabe serializar `Decimal` nem `date`. Num formulário dinâmico esses tipos são o
pão com manteiga — "Quantidade (kg)" é DECIMAL, "Quando" é DATA. Sem o encoder
do Django, `registrar()` quebrava **depois** da validação: o produtor veria
"criado com sucesso" e o registro sumiria. O preço é honesto: **DECIMAL volta
como string**, o que é preferível a guardar `float` e perder precisão em
dinheiro.

---

## D3 — Um vocabulário só

**Decisão.** Adotado o vocabulário do `mcp-Ampliagro_amplIA.md`:

| Adotado | Nome antigo (MAPA) | Por quê |
|---|---|---|
| `DynamicApp` | `DynamicEntity` | "App" é a palavra do produto: o usuário vê um app no painel, nunca "entity" |
| `DynamicField` | `DynamicSchema` | **Uma linha por campo** é o único desenho que evolui: renomear um campo não pode exigir reescrever o schema inteiro, e cada campo carrega suas próprias regras |
| `DynamicRecord` | `DynamicRecord` | mesmo nome, sem conflito |

Nomes diferentes entre os dois docs significariam migrations diferentes e tools
MCP diferentes. Renomear depois custa migration.

**Metadados, nunca código.** A diretriz 2 do mapa é explícita: nunca `eval()` ou
`exec()` de código gerado pela IA. A "programação" de uma ferramenta tem duas
camadas:

- **metadados** (o que a IA escreve) → `DynamicApp` + `DynamicField`
- **comportamento** (código nosso) → `app/ia/dinamicos.py`

O que a IA **não** consegue fazer, por construção — não por configuração que
alguém possa desligar: escrever função, exigir `import`, disparar shell, ler
arquivo do servidor, ou sair do escopo do usuário. `app/ia/tests_dinamicos.py`
verifica isso lendo o AST dos quatro módulos e falha se aparecer `eval`, `exec`,
`compile`, `__import__` ou `getattr(x, "__alguma_coisa")`.

---

## Inventário

| Arquivo | Papel |
|---|---|
| `app/ia/llm_gateway/__init__.py` | D1 — isolamento do LLM, provider local como padrão |
| `app/ia/json_portatil.py` | D2 — probe de capacidade + filtros portáveis + DDL de GIN |
| `app/models/campos.py` | `JSONFieldPortatil` — JSONField que aceita `Decimal`/`date`/`UUID` |
| `app/models/dinamico.py` | D3 — os 3 models, com `DynamicRecordQuerySet.para(user)` escopado |
| `app/ia/dinamicos.py` | camada de serviço: validação, coerção de tipo, CRUD, `descrever()` |
| `app/ia/tests_dinamicos.py` | 47 testes de invariante |
| `app/migrations/0049_dinamicos_criador_livre.py` | 3 tabelas, 5 índices, 2 constraints |

### Invariantes cobertos por teste

- o gateway nunca levanta, e sem chave não chama nada externo;
- o probe de capacidade **não mente** (regressão: o cache indexado só pelo
  vendor contaminava as features entre si, e o SQLite se anunciava com JSONB);
- `contem()` devolve o mesmo conjunto em qualquer backend, e não confunde
  `{"codigo": 1}` com `{"codigo": 12}`;
- `DynamicRecord.objects.para(None)` devolve **vazio**, nunca tudo;
- `registrar()` em ferramenta alheia é recusado; campo `REFERENCIA` para
  registro de outro usuário também;
- `descrever()` levanta em vez de devolver schema vazio — schema vazio seria o
  modo sutil de a IA desenhar a tela errada sem sinal de erro;
- configuração incoerente (OPCOES sem lista, REFERENCIA sem alvo) falha no
  `save`, não na leitura;
- nenhuma chamada de execução de código nos 4 módulos.

### Estado

`manage.py check` 0 issues · `makemigrations --check` sem mudanças ·
**311 testes OK** (264 preexistentes + 47 novos, zero regressão).

---

## O que NÃO foi feito, e por quê

- **Não porta para PostgreSQL.** 84 models e 48 migrations já existem sobre
  SQLite. É trabalho de infraestrutura, não de fundação de IA.
- **Não cria o app `amplia_mcp`.** BUILD 0 é a próxima fase. O desenho aqui já
  evita o erro óbvio: o MCP não será um processo paralelo com caminho de
  segurança próprio — será mais um `via=` do `sandbox.executar()`, herdando
  allowlist, anti-injeção e auditoria de graça.
- **Não expõe view nem endpoint.** Nenhum `urls.py` foi tocado. A camada de
  serviço é testável sem HTTP, e o BUILD 1 já traz o pack de valor.
- **Não toca `app/templates/index.html`**, que está sob edição de outra sessão.
- **Não mexe no `saldo_total` pendente de Lote 2** (retorna 0, esperado 900):
  é separado deste trabalho.
