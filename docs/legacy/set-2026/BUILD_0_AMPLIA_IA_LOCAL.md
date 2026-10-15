# BUILD 0 — a IA raciocina, e suas mãos são governadas

> Data: 2026-09-26 · Predecessor: `FUNDACAO_AMPLIA_D1_D2_D3.md`
> Estado: implementado, 26 testes, 337 na suíte, 0 regressão.

---

## O erro que eu cometi na D1

Na auditoria anterior eu afirmei: *"não existe NENHUMA chamada de LLM no
projeto — a AmplIA é 100% determinística"*.

**Estava errado.** Eu tinha greppado só Python. Em JavaScript existe:

```js
// app/static/js/ia-local/ia-local.js
let iaModel = 'SmolLM2-1.7B-Instruct-q4f16_1-MLC';   // com Qwen2-0.5B de reserva
const webllm = await import('https://esm.run/@mlc-ai/web-llm@0.2.79');
```

A pista estava no meu próprio histórico de sessão: ao limpar o cache do
browser apareceram `webllm/config`, `webllm/wasm`, `webllm/model`. Eu li aquilo
e passei direto.

O modelo já era o certo para o requisito: **SmolLM2-1.7B em q4f16 roda em WebGPU
e responde curto dentro da janela de 2–4 s num celular moderno.** Não faltava
modelo. Faltava o resto.

---

## O problema real: a IA raciocinava em último lugar

A cadeia era:

```
wizards → sandboxBridge (19 intents) → smartResponse (regex)
        → fallbackIntent (regex) → WebLLM  ← só aqui
```

O produtor perguntava *"vai chover?"* e recebia regex em 50 ms, com um modelo
de 1.7B carregado na aba. **A IA que raciocina nunca raciocinava** — só era
consultada quando o regex já tinha desistido, ou seja, quando a pergunta era
tão estranha que o regex não tinha nada a dizer.

E o que pior: as "mãos" do modelo eram `iaToolCall`, uma função em JavaScript
que fazia isto:

```js
if (tool === 'irrigacao') {
  await apiFetch('/api/iot/comandos/', { method: 'POST', ... });
}
```

**POST direto na API de comandos.** Um modelo de 1.7B podia acionar uma **válvula
de irrigação** sem passar por `sandbox.executar`, sem `needs_confirm`, sem linha
em `IAExecucao` e sem checagem de flag de capacidade. E o parsing era
`text.match(/\{[^]*"tool"[^]*\}/)`, que casa o primeiro `{` com o último `}` da
resposta.

---

## O que a BUILD 0 faz

### 1. A cadeia foi invertida

```
wizards → WebLLM RACIOCINA → tools governadas
        → (se não houver LLM pronto) sandboxBridge → regex → regex
```

Os **wizards continuam primeiros**, e essa é a única concessão: são máquinas
de estado persistentes (uma etapa de cadastro em curso). Enta-los com um modelo
de 1.7B quebraria o formulário no meio do preenchimento.

O bloco do LLM saiu do fim da cadeia e virou a função `raciocinarLlm()`, para
que a inversão fosse uma **movimentação**, não uma cópia. Cópia é como a
cadeia divergiria de novo em seis meses.

### 2. As mãos passaram a ser as mesmas dos intents

`app/amplia_mcp/` expõe as **65 intents** como tools tipadas e executa **só**
por `sandbox.executar(via="mcp")`. Uma tool não é uma função que este módulo
implementa: é um intent do catálogo existente. Então toda tool herda, sem
código novo:

- verificação de flag de capacidade;
- `needs_confirm` — escrita vira pedido, não fato;
- `parece_injecao` — sequestro de prompt vira estado neutro;
- linha em `IAExecucao` com entrada, flags, fontes e duração;
- escopo de usuário nas queries.

`iaToolCall` foi desligada, com o corpo mantido no arquivo como referência de
migration (as tools dela foram promovidas a intents).

### 3. Três portas, um caminho só de execução

| Porta | Serve a | Caminho |
|---|---|---|
| `POST /api/amplia/exec/` | o LLM na aba do navegador | → `executar_para` |
| `python -m app.amplia_mcp.servidor --usuario X` | Claude Desktop, Hermes, qualquer agente MCP | → `executar_para` |
| `import app.amplia_mcp` | código Python | → `executar_para` |

O SDK `mcp` é import **preguiçoso**: o AmplIA, a IA do painel e o endpoint HTTP
funcionam sem ele. O servidor stdio é só a porta para clientes de fora.

O stdio tem um portão que a web não precisa: `--permitir-escrita`. Um agente
rodando na máquina do produtor não aciona irrigação por padrão.

---

## Medido no navegador, não presumido

Com sessão de produtor real em `127.0.0.1:8001`:

| Chamada | Resultado |
|---|---|
| `GET /api/amplia/tools/` | **200**, 65 tools no formato OpenAI — 48 leitura, 17 com aviso de escrita |
| `amplia_ligar_irrigador` | **200** — *"confirme para ligar o irrigador … (envie confirm=true)"*, `IAExecucao` **#68** |
| `amplia_deleta_banco` (fora do catálogo) | **200** `tool_fora_do_catalogo` |
| `amplia_ajuda` (leitura) | **200**, resposta útil |
| `GET /api/iot/comandos/` depois | **0 comandos na fila** |

A última linha é a que importa. **A válvula não foi acionada.** Com o caminho
antigo, aquele mesmo POST teria criado o comando.

---

## A allowlist é o catálogo, não o formato

O `tool_fora_do_catalogo` acima não é decoração. Na primeira versão eu checava
só o prefixo, e `amplia_deleta_tudo` passava. Um modelo pequeno inventa nome de
tool com convicção; o servidor tem de recusar **pelo catálogo**, não pelo
formato do nome. O teste cobre os dois casos (sem prefixo → `tool_desconhecida`;
prefixo ok mas intent inexistente → `tool_fora_do_catalogo`).

E a descrição da tool não pode mentir sobre capacidade. `sandbox.somente_leitura`
é fail-closed de propósito: intent que não declara flag é tratado como escrita.
Isso é certo para segurança, mas faz `ajuda` — que só lista capacidades —
ser rotulada como "ALTERA dados". Se o modelo recebesse um aviso falso toda vez
que o produtor perguntasse *"o que você sabe fazer"*, ele **aprenderia a ignorar
avisos de capacidade** — que é justamente o que tornaria o aviso inútil nas
tools que importam. São três casos, ditos com precisão: flag de escrita →
aviso forte; sem flag → *"não declarou flag"*; leitura → sem aviso.

---

## Inventário

| Arquivo | Papel |
|---|---|
| `app/amplia_mcp/__init__.py` | catálogo derivado dos intents, `executar_para` (porta única), `contexto` |
| `app/amplia_mcp/views.py` | 3 endpoints; `exec` aceita **uma** tool por request |
| `app/amplia_mcp/servidor.py` | servidor MCP stdio, import preguiçoso, portão `--permitir-escrita` |
| `app/amplia_mcp/urls.py` | `app_name` e rotas |
| `app/amplia_mcp/tests.py` | 26 testes, incluindo invariante de **fonte** |
| `config/urls.py` | `path("api/amplia/", …)` |
| `ia-local.js` | cadeia invertida + `raciocinarLlm()` + `toolCallGovernada()` |

### Invariantes de fonte (o que impede a regressão)

Comportamento passa num teste e ainda assim sobra um atalho em outra linha.
Então há testes que leem a AST dos módulos e falham se aparecer:

- `eval` / `exec` / `compile` / `__import__`;
- SQL montado à mão (tudo passa pelo ORM, que é quem aplica multitenant);
- import do sandbox diferente de `executar` / `somente_leitura` / `INTENTS` / `catalogo`;
- `sandbox.executar` chamado direto na view — tem que passar por
  `executar_para`, que é onde `via="mcp"` está escrito.

### Sobre o parser de tool call

Substituí a regex gulenta por leitura de objeto JSON balanceado, respeitando
strings e escapes. A regex antiga casava o primeiro `{` com o último `}` da
resposta: num modelo pequeno, que costuma envolver a resposta em prosa com
exemplos, ela pegava o objeto errado. O novo percorre candidatos e devolve o
primeiro que tenha `tool` como chave.

---

## Estado

`manage.py check` 0 issues · `makemigrations --check` sem mudanças ·
`node --check` OK · **337 testes OK** (311 anteriores + 26 novos).

---

## O que não foi feito

- **Não instalei o SDK `mcp`.** Ele é opcional e o download fica para quando
  houver cliente externo concreto. O servidor stdio avisa como instalá-lo.
- **Não mexi nos 65 intents.** A BUILD 0 expõe o que já existia; ela não
  amplia o catálogo. Ampliar é trabalho de produto, com intenção definida por
  uso real, não por inferência.
- **Não prometo 2–4 s ainda.** O modelo é o certo para a janela, mas **medir em
  celular real é trabalho de campo** — o primeiro acesso baixa hundreds of MB de
  pesos. Falta medir: tempo até o primeiro token, tokens/s e o custo de RAM.
  Enquanto isso não for medido, "2–4 s" é expectativa, não medição.
- **Não toquei no `saldo_total` pendente** de Lote 2 (retorna 0, esperado 900).
- **Não toquei em `app/templates/index.html`**, sob edição de outra sessão.

## Próximo: BUILD 1 (OCR + áudio)

O Pack 0 do plano é o que vende sem hardware: foto de caderno sujo e áudio de
tractorista. A base já está pronta — `sandbox` dá a porta governada, e o LLM
local raciocina. Falta o ingestion: upload de imagem, OCR, e a extração
estruturada que alimenta os models nativos.
