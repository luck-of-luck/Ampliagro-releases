# AmplIA — o servidor MCP

> Como ligar uma IA de fora (Claude Desktop, opencode, Hermes, qualquer
> cliente MCP) à AmplIA, e como ela fala com o resto do sistema.
>
> **Terreno:** `IA-D`. Última verificação: o handshake completo foi corrido e
> passou — ver [Verificado, não suposto](#verificado-não-suposto).

---

## O que isto é

A AmplIA tem uma camada que dá **braços governados** a uma IA que raciocina.

Não é uma IA nova. É o oposto de uma IA nova: é a guarantee de que quando
alguma IA decide agir, ela passa pelo mesmo caminho que um botão do painel —
com a mesma verificação de permissões, o mesmo pedido de confirmação ao
produtor, e a mesma linha na trilha de auditoria.

Três portas, **um caminho de execução só**:

```
                    ┌──────────────────────────────┐
  IA no browser ───▶│  POST /api/amplia/exec/      │
  (WebLLM)          └──────────────┬───────────────┘
                                   │
  Cliente MCP ──────▶  app/amplia_mcp/servidor.py  (stdio)
  (Claude, etc.)                    │
                                   │
                                   ▼
                            executar_para()
                                   │
                                   ▼
                            sandbox.executar()   ← o ÚNICO lugar
                                   │
                        ┌──────────┼──────────┐
                        ▼          ▼          ▼
                  verificação  needs_confirm  IAExecucao
                  de flags                    (auditoria)
```

Um segundo caminho de execução seria exactamente o bug que esta camada existe
para fechar. O teste que o garante está em
`app/amplia_mcp/tests.py::InvarianteDeFonteTest`: percorre o código por AST e
falha se alguém importar do sandbox outra coisa além de
`executar`/`somente_leitura`/`INTENTS`/`catalogo`.

---

## Superfície HTTP

Prefixo: `/api/amplia/`. Tudo exige sessão (`login_required`), excepto o que
diz o contrário.

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/tools/` | As ferramentas no formato de function-calling da OpenAI (é o que o WebLLM consome). Catálogo completo. |
| `POST` | `/exec/` | Executa **uma** ferramenta. `{tool, args, entrada}`. |
| `GET` | `/vocabulario/` | Os nomes verdadeiros, num texto que cabe na janela do modelo local. |
| `GET` | `/contexto/` | O que já existe na fazenda, para a IA não propor duplicata. |
| `GET` | `/diagnostico/` | A aritmética da própria camada e os invariantes do contrato. |
| `GET` | `/skills/` | As especialidades de domínio (campo, finanças, IoT). |
| `POST` | `/ingestao/audio/sinais/` | Sinais determinísticos de uma transcrição. Só leitura. |
| `GET` | `/proativo/pendente/` | Entrega um cenário e toma o lease. Vazio quando não há nada. |
| `POST` | `/proativo/devolver/` | Devolve o cenário sem ter gerado alerta. |
| `GET` | `/alertas/pendentes/` | O que o motor pensou e ainda não foi lido. |
| `POST` | `/alertas/visto/` | O produtor confirmou que leu. |
| `POST` | `/palco/render/` · `/avaliar/` · `/clonar/` | Desenha, avalia e clona uma tela do palco. |
| `GET` | `/palco/info/` | O catálogo do palco. |

### `/tools/` ou `/vocabulario/`?

Depende de quem lê.

| | `/tools/` | `/vocabulario/` |
|---|---|---|
| Tamanho (medido) | ~34 KB, ~8 700 tokens | ~2 500 chars, ~630 tokens |
| Tem `inputSchema` de cada tool | sim | não |
| Cabe na janela do SmolLM2 de 1,7 B | **não** | sim |
| Serve para | modelo de servidor, cliente MCP com prompt grande | o modelo que corre **no browser** |

Um cliente MCP deve usar `/tools/` (ou a lista MCP) e ficar com os schemas.
O browser usa `/vocabulario/`, porque a soma dos schemas não cabia na janela
do modelo — ver [a história do fantasma](#por-que-existe-o-vocabulario).

---

## O servidor MCP (stdio)

### O que é

Um processo local que fala o protocolo MCP por stdio. É a porta para clientes
de fora. Não implementa execução nenhuma — chama `executar_para`, que chama
`sandbox.executar`.

### Pré-requisitos

O SDK `mcp` **não** é dependência do AmplIA. O Django funciona, a IA do painel
funciona e toda a superfície HTTP funciona sem ele — o import é preguiçoso de
propósito. Para o servidor stdio:

```powershell
cd C:\Trabalho\Projetos\Ativos\Ampliagro
.\.venv\Scripts\python.exe -m pip install "mcp>=1.0,<2"
```

### A receita correcta (medida)

```powershell
C:\Trabalho\Projetos\Ativos\Ampliagro\.venv\Scripts\python.exe `
  C:\Trabalho\Projetos\Ativos\Ampliagro\app\amplia_mcp\servidor.py `
  --usuario demo
```

**Use o caminho do ficheiro. Não use `-m app.amplia_mcp.servidor`.**

Isto não é preferência. Medido, com o directório de trabalho fora do
repositório — que é o que um cliente MCP faz:

```
python -m app.amplia_mcp.servidor
  -> ModuleNotFoundError: No module named 'app.amplia_mcp'

python <raiz>\app\amplia_mcp\servidor.py
  -> {"jsonrpc":"2.0","id":1,"result":{...}}   ✅
```

`-m` resolve o nome do módulo no `sys.path` **antes** de correr uma linha do
ficheiro. A correcção que faz o servidor_arrancar sem directório de trabalho
(`RAIZ_REPO`, em `servidor.py`) vive dentro do ficheiro, que nunca chega a ser
lido. `-m` só funciona de dentro da raiz do repositório — e um cliente MCP
nunca está lá.

Se preferires `-m`, funciona com `PYTHONPATH` a apontar para a raiz. Mas o
caminho do ficheiro não depende de nada.

### Opções

| Opção | Efeito |
|---|---|
| `--usuario NOME` | **Obrigatório.** O produtor que esta instância atende. |
| `--permitir-escrita` | Libera as ferramentas que alteram dados. Sem isto, **só leitura**. |
| `--settings MÓDULO` | `DJANGO_SETTINGS_MODULE`. Por omissão `prod` se `AMPLIA_PROD=1`, senão `dev`. |

O modo só-leitura é o default e é uma decisão, não uma omissão. Um agente
externo a correr na máquina do produtor não deve poder, por omissão, acionar
uma válvula de irrigação.

### Configuração para clientes

**Claude Desktop** — `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "amplia": {
      "command": "C:\\Trabalho\\Projetos\\Ativos\\Ampliagro\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Trabalho\\Projetos\\Ativos\\Ampliagro\\app\\amplia_mcp\\servidor.py",
        "--usuario", "demo"
      ]
    }
  }
}
```

**opencode** — `opencode.json`:

```json
{
  "mcp": {
    "amplia": {
      "type": "local",
      "command": [
        "C:\\Trabalho\\Projetos\\Ativos\\Ampliagro\\.venv\\Scripts\\python.exe",
        "C:\\Trabalho\\Projetos\\Ativos\\Ampliagro\\app\\amplia_mcp\\servidor.py",
        "--usuario", "demo"
      ],
      "enabled": true
    }
  }
}
```

**Hermes** — `~/.hermes/config.yaml`, ou o bloco `mcpServers` do teu cliente.

> No Windows, os caminhos JSON usam `\\` porque o JSON também consome `\`.
> E **reinicia o opencode** depois de mexer na configuração — não é recarregada
> a quente.

### Verificar que ficou ligado

```powershell
cd C:\Trabalho\Projetos\Ativos\Ampliagro
.\.venv\Scripts\python.exe scripts\verificar_mcp_amplia.py demo
```

Faz o handshake completo pelo protocolo e diz o que respondeu. Se isto
imprimir seis `OK`, o servidor está de pé e o cliente vai ligar-se.

---

## O que o servidor expõe

### Ferramentas

As **78**: as 76 intenções do catálogo, mais as duas de catálogo
(`amplia_catalogos`, `amplia_desenhar_pagina`).

O nome é sempre `amplia_` + o nome da intenção. O prefixo existe para que o
"criar" de um modelo não colida com a ferramenta de um cliente MCP qualquer na
mesma sessão.

### Recursos

| URI | O quê |
|---|---|
| `amplia://contexto/<usuario>` | O que já existe na fazenda. |
| `amplia://modelos` | As telas que valem a pena montar, com os widgets. |
| `amplia://widgets` | O dicionário: o que cada widget mede e se o número é medido ou gerado. |
| `amplia://skills` | As especialidades de domínio e os intents que cada uma cobre. |
| `amplia://capacidades` | O catálogo derivado do código: o que cada intent faz e que campos pede. |

Um URI desconhecido dá erro explícito. A versão anterior devolvia o contexto
da fazenda para qualquer URI, e um cliente com um typo achava que tinha lido o
que pediu.

### Prompts

| Prompt | Quando |
|---|---|
| `amplia_ferramentas` | Antes da primeira chamada. Traz os 76 nomes verdadeiros e o que fazer quando o nome inventado não existe. |
| `amplia_seguranca` | Antes da primeira escrita. As regras que decidem se a chamada é executada ou perguntada. |
| `amplia_campos` | Quando uma tool devolveu `COLETANDO_DADOS`. Que campos ela quer, e porque a segunda chamada tem de ser a mesma tool. |

Os três textos são **derivados** do catálogo a cada pedido. Um tool novo entra
nos três sem ninguém editar nada — que é o ponto: a lista de nomes escrita à
mão que causou a FILA #27 não pode ser reintroduzida.

---

## Por que existe o `/vocabulario/`

Esta é a parte que vale ler, porque é um defeito real e medido.

O modelo local (`SmolLM2-1.7B-Instruct`) corre **no browser**, e não usava
function-calling nativo: escrevia-se um prompt com uma lista de ferramentas e
esperava-se que o modelo devolvesse `{"tool": "...", "args": {...}}` como
texto.

Essa lista estava escrita à mão no `IA_SYSTEM`
(`app/static/js/ia-local/ia-local.js:4110`). Tinha **treze** nomes: `navegar`,
`consultar`, `criar`, `iniciar_cadastro`, `irrigacao`, `atualizar`,
`excluir`, `relatorio`, `buscar_web`, e mais quatro de compatibilidade.

**Medido: as treze são fantasmas.** Nenhuma existe no catálogo. As 78
verdadeiras não estavam em lado nenhum do prompt.

Consequência medida, ponta a ponta, por HTTP: **toda** a tool call que o
modelo conseguia escrever voltava `tool_fora_do_catalogo`.

```
amplia_irrigacao   HTTP 200  ok=False  -> tool fora do catalogo: 'amplia_irrigacao'
amplia_criar       HTTP 200  ok=False  -> tool fora do catalogo: 'amplia_criar'
amplia_consultar   HTTP 200  ok=False  -> tool fora do catalogo: 'amplia_consultar'
amplia_navegar     HTTP 200  ok=False  -> tool fora do catalogo: 'amplia_navegar'
```

Não era uma ferramenta que às vezes falhava. Era a ponte inteira entre o
modelo e as mãos cortada — e o produtor via um erro de máquina em vez de uma
resposta.

`/api/amplia/tools/` devolvia os schemas correctos. Nenhum código no
repositório os consumia. O servidor tinha razão e a página não ouvia.

A correcção teve **três** camadas, e as duas últimas só apareceram quando a
primeira ficou feita — que é a parte interessante.

1. **`sugestoes` no erro.** Uma tool que não existe volta com os nomes que
   existem, em vez de um "não". Funciona sem tocar no cliente: o modelo tem o
   nome certo no mesmo turno.
2. **`/vocabulario/`.** Os nomes verdadeiros, todos, num texto derivado que
   cabe na janela do modelo. Um intent novo aparece aqui sem ninguém editar
   nada.
3. **O `IA_SYSTEM`, e o que havia por baixo dele.** A persona deixou de
   listar ferramentas: recebe-as de `/api/amplia/vocabulario/`, que é
   derivado. Sem servidor, o prompt diz que não tem ferramentas — e isso é
   o que fecha a porta a uma lista escrita à mão.

E ao corrigir a terceira camada apareceram **dois defeitos que estavam por
baixo dela**, e que os dois primeiros defeitos escondiam:

> **O parser nunca funcionou.** `extrairToolCall` lia `obj.tool`, mas
> `lerObjetoJson` devolve `{ valor, fim }` — o objeto parseado está em
> `valor`. `obj.tool` era sempre `undefined`, o `if` nunca entrava, e a
> extracção devolvia `null` para **toda** a entrada. O mesmo desvio já
> estava corrigido em `proativo-local.js`, com um comentário a avisar.
>
> **A `iaToolCall` escrevia.** Marcada "DESLIGADA" em comentário desde o
> BUILD 0, tinha dois POST vivos a `/api/iot/comandos/`, um POST a criar
> registos, um PATCH, um DELETE e um POST de relatório. E o ramo de
> irrigação mandava `device: lista[0]?.id || 1`.

Os três davam o **mesmo sintoma** do lado de fora — o produtor via a IA não
fazer nada — e um escondia o seguinte. Corrigir só o primeiro teria dado a
impressão de ter resolvido, e o produtor continuaria a ver o mesmo ecrã.

### O que está medido depois

```
nomes no prompt:                     76
nomes testados contra /api/amplia/exec/: 76
nomes recusados por nome:              0
```

O contrato que `tests_contrato_ia.py` trava, escrito numa linha:

> um nome que o AmplIA publica tem de ser um nome que o AmplIA aceita.

### Regra que daqui sai

> Uma lista de capacidades escrita à mão é uma lista para se esquecer de
> acrescentar. Deriva-a do código.

Todos os textos deste servidor — o vocabulário, os três prompts, os recursos —
saem do catálogo a cada chamada. `test_derivado_e_nao_escrito` injecta um
intent falso e falha se ele não aparecer: é o teste que impede a recaída.

---

## Quando uma ferramenta devolve `needs_confirm`

Não é erro. É o servidor a perguntar ao produtor.

```json
{
  "ok": true,
  "needs_confirm": true,
  "resposta": "Você confirma a execução de 'Liga o irrigador'? (Diga 'sim' ou 'não')",
  "state": "AGUARDANDO_CONFIRMACAO"
}
```

Duas formas de confirmar:

- **Com conversa** — manda a frase do produtor. Em HTTP vai no campo `entrada`
  de topo; em stdio é o campo `entrada` dos argumentos.
- **Sem conversa** — a mesma chamada com `{"confirm": true}` nos argumentos.

O produtor é que responde. A IA não se auto-confirma.

---

## Diagnóstico

Quando algo não funciona:

```powershell
# O servidor responde ao protocolo?
.\.venv\Scripts\python.exe scripts\verificar_mcp_amplia.py demo

# As invariantes da camada ainda valem?
.\.venv\Scripts\python.exe manage.py test app.amplia_mcp

# Os 76 nomes chegam ao modelo?
.\.venv\Scripts\python.exe manage.py shell -c "from app.amplia_mcp import vocabulario; v=vocabulario(); print(v['total'], v['chars'], v['cabe'])"
```

| Sintoma | Causa provável |
|---|---|
| `ModuleNotFoundError: No module named 'app.amplia_mcp'` | Usaste `-m`. Usa o caminho do ficheiro. |
| `SDK 'mcp' nao instalado` | `pip install "mcp>=1.0,<2"` no venv do Ampliagro. |
| `usuario 'x' nao existe no banco` | `--usuario` tem de ser um `User` que exista. |
| `usuario obrigatorio` / `sem_usuario` | Falta `--usuario`. |
| `tool fora do catalogo` | Lê `sugestoes` na resposta e chama um dos nomes que vêm lá. |
| `esta tool esta em modo leitura` | Falta `--permitir-escrita`. |
| O modelo inventa nomes | O `IA_SYSTEM` ainda está com a lista manual. Ver a FILA #27. |

---

## Verificado, não suposto

Cada afirmação deste documento tem uma medição atrás. Para repetir:

```powershell
.\.venv\Scripts\python.exe scripts\verificar_mcp_amplia.py demo
```

Saída da última execução, com o directório de trabalho **fora** do
repositório:

```
OK  initialize -> servidor=amplia versao=1.30.0
OK  tools/list  -> 78 ferramentas
    presente: amplia_clima_agora
    presente: amplia_catalogos
    presente: amplia_desenhar_pagina
OK  prompts/list -> 3 prompts: ['amplia_ferramentas', 'amplia_seguranca', 'amplia_campos']
OK  resources/list -> 5 recursos: ['amplia://contexto/demo', 'amplia://modelos',
     'amplia://widgets', 'amplia://skills', 'amplia://capacidades']
OK  prompts/get  -> 1666 chars de orientacao
OK  tools/call   -> 4961 chars de catalogo
```

E a prova de que `-m` não funciona, que é o que justifica a receita:

```
python -m app.amplia_mcp.servidor --usuario demo   (cwd fora do repo)
  -> ModuleNotFoundError: No module named 'app.amplia_mcp'
```

---

## Ficheiros

| Ficheiro | O quê |
|---|---|
| `app/amplia_mcp/__init__.py` | O catálogo, a porta de execução, o vocabulário. |
| `app/amplia_mcp/views.py` | A camada governada por HTTP. |
| `app/amplia_mcp/urls.py` | As rotas, com o prefixo `/api/amplia/`. |
| `app/amplia_mcp/servidor.py` | O servidor MCP por stdio. |
| `app/amplia_mcp/prompts_mcp.py` | Os três prompts, derivados do catálogo. |
| `app/amplia_mcp/contrato.py` | As instruções do servidor e o enriching dos schemas. |
| `app/amplia_mcp/capacidades.py` | O catálogo de capacidades. |
| `app/amplia_mcp/skills.py` | As especialidades de domínio. |
| `app/amplia_mcp/tests.py` | As invariantes da camada. |
| `app/amplia_mcp/tests_comunicacao.py` | A comunicação: vocabulário, sugestões, prompts. |
| `app/amplia_mcp/tests_contrato_ia.py` | O contrato: o que se publica tem de ser o que se aceita. |
| `app/amplia_mcp/receita_mcp.json` | A receita de ligação, pronta a copiar: leitura, escrita e produção. |
| `scripts/verificar_mcp_amplia.py` | O handshake, para repetir tudo isto. |
| `scripts/verificar_mcp_doc.py` | Confere que este ficheiro segue as regras de markdown. |

---

## O contrato, campo a campo

> Secção acrescentada pelo bloco do `contrato.py`. **Não substitui nada acima** —
> o que estava aqui antes foi medido e verificado, e continua a estar. O que
> segue é o que se aprendeu a ler o `inputSchema` como o que o cliente recebe,
> e não como o que o autor da intent escreveu.

## `inputSchema`: o que é derivado e de quê

| Campo | De onde vem | Porquê |
|---|---|---|
| `required` | `required_fields` do intent | É a verdade que o `sandbox` usa para saber o que falta. **Nenhuma** das intents que a pedem a publicava. |
| `confirm` (boolean) | em toda a tool que **não** é só-leitura | O `sandbox` só executa uma escrita com `params["confirm"]`. |
| `additionalProperties: false` | inalterado | O modelo não inventa campo. |
| aviso de capacidade | `flags` + `somente_leitura` | Três casos ditos com precisão: escrita → aviso forte; sem flag → diz que não declarou; leitura → sem aviso. |

`confirm` **não** entra em `required`, por desenho: a confirmação é um
*segundo* passo. Se fosse obrigatória, o modelo teria de confirmar antes de ter
feito o que está a confirmar, e a escrita nunca sairia.

## Três defeitos do contrato, medidos

### 1. O schema não publicava `required`

**MEDIDO, L3.** Nove intents com `required_fields`; **nove** schemas sem
`required`:

```
amplia_cadastrar_funcionario  pede ['nome', 'cargo']
amplia_cadastrar_maquina      pede ['nome', 'tipo']
amplia_cadastrar_talhao       pede ['nome', 'area']
amplia_criar_ordem_compra     pede ['fornecedor', 'valor']
amplia_editar_lancamento      pede ['lancamento', 'campo', 'valor']
amplia_editar_safra           pede ['safra', 'campo', 'valor']
amplia_excluir_safra          pede ['safra']
amplia_registrar_manutencao   pede ['maquina', 'descricao']
amplia_registrar_vacina       pede ['brinco', 'produto']
```

A IA não sabia o que era obrigatório sem tentar — e cada tentativa é uma ida ao
estado `COLETANDO_DADOS`, que devolve "Qual é o nome?" e espera a chamada
seguinte. Num cliente MCP externo isso era um beço sem saída, porque não
havia canal para responder (ver §2).

E há um segundo defeito dentro deste: declarar `required: ["area"]` num schema
que proíbe `area` produz um contrato **impossível de satisfazer** — o modelo é
obrigado a enviar um campo que o schema diz ser inválido. A correção declara o
campo **antes** de o tornar obrigatório.

### 2. O schema proibia `confirm`, que o sistema exige

**MEDIDO, L3.**

```
(a) tools com campos obrigatórios e sem 'required'    9
(b) tools de escrita: 24 · com 'confirm' no schema:   5
(c) tools de escrita com additionalProperties=False: 24
```

Das 24 tools de escrita, 19 não declaravam `confirm` — e as 24 fechavam o
schema. A única forma de confirmar uma escrita era **violar o contrato que o
próprio servidor tinha publicado**.

As 5 que declaravam são as dos intents dinâmicos, que escreveram o
`params_schema` à mão. O caminho existia; só não tinha sido aplicado a todos.

### 3. `views.tools` chamava `catalogo_tools()` duas vezes

**MEDIDO, L1.** Uma para os `tools`, outra para a chave `mcp`. Cada chamada
refazia a dedução de todos os schemas a partir dos exemplos — duas passagens
para a mesma aritmética. Agora há um ponto de chamada só, e um teste de AST que
falha se voltar a haver dois.

## `entrada`: o canal que faltava

**MEDIDO, L2.** `entrada` não aparecia uma única vez em `servidor.py`.

O `sandbox` é uma máquina de estados conversacional: quando uma escrita devolve
`needs_confirm`, o próximo passo é a frase do produtor. Em HTTP, `views.exec`
aceita `entrada`. Em stdio não havia caminho nenhum — e como `entrada` chegava
vazia, o `else` do bloco `AGUARDANDO_CONFIRMACAO` corria e devolvia
"Operação cancelada", **apagando o pedido do produtor**.

`entrada` é um campo de topo nos argumentos, **retirado antes de chegar ao
sandbox** e entregue em `meta`. Fora de `args` por uma razão concreta: deixada
em `args`, o `cadastrar_funcionario` a preencheria com o nome do vaqueiro,
porque "sim" é o primeiro campo vazio da lista.

## `GET /api/amplia/diagnostico/` — o espelho

Responde a uma pergunta que um cliente não consegue responder sozinho: *o
caminho está inteiro?* Devolve a **conta** e os **invariantes**, cada um com
`ok` ou a lista do que o quebra.

O que se garante é a relação:

```
tudo_ok  ==  all(invariantes.values())
```

O resumo nunca mente sobre as partes. É essa a propriedade testada — e é
testável com o código são e com o código partido, ao contrário de
`assertTrue(tudo_ok)`, que só sabe estar verde ou vermelho e não sabe qual das
duas coisas aconteceu.

Cinco invariantes do contrato estão `true` porque foram construídos assim. O
sexto, `skills_sem_handler_fantasma`, depende de ficheiros que não são deste
bloco — e está `false`, porque é assim. Ver a secção seguinte.

## As Skills de domínio: 15 de 15 handlers não existem

**MEDIDO, L2. Reportado, não corrigido** (as SKIs não são território do bloco).

`app/ia/skills/*.md` declarava, em `handlers:`, os intents que cada
especialidade cobre. **Nenhum dos quinze existe no registo:**

| SKI | handlers declarados | existem |
|---|---|---|
| `amplia-campo` | `vra_ndvi_prescricao`, `solo_spd`, `praga_ai_foto`, `guidance_ab`, `as_applied_gap` | **0 / 5** |
| `amplia-finance` | `hedge_b3_real`, `benchmark_fbn`, `lcdpr_sped`, `seguro_chuva_param`, `simular_hedge` | **0 / 5** |
| `amplia-iot` | `can_bus_telemetria`, `avicultura_bigbrother`, `tilapia_mormaco`, `pivo_bme280`, `carbono_mombak` | **0 / 5** |

`praga_ai_foto` e `guidance_ab` aparecem na `COORDENACAO_IA.md` (itens #6 e #7)
como trabalho **feito**. Estão lá como *serviços* de `app/services/`, não como
intents — a SKI apresenta serviços como se fossem capacidades da IA. E a lista
de capacidades é exactamente o que ela diria a quem perguntasse o que sabe
fazer, que é o pior sítio para uma lista de ficção.

O que este bloco faz, sem tocar nos ficheiros: **diz**. `catalogo_skis()`
devolve `cobre` e `cobre_inexistente` separadamente, com um `aviso` que muda de
texto conforme o resultado. Um `except` aqui engole-se o handler fantasma e a
IA fica com um buraco de comportamento sem ninguém notar.

`GET /api/amplia/skills/` e o recurso `amplia://skills` são a mesma informação
em duas linguagens, e saem da **mesma função** — pelo mesmo motivo de
`audio_sinais`: duas implementações do mesmo dicionário discordam, e o produtor
vê um número no ecrã e outro no log.

## Os seis ficheiros SKI têm BOM UTF-8

**MEDIDO, L2. Reportado, não corrigido.**

`app/ia/skills/*.md` e `app/static/ia/skills/*.md` estão gravados com
`ef bb bf` no início. O efeito é silencioso: ler com `encoding="utf-8"` deixa a
BOM em cima da primeira linha, o título markdown deixa de ser reconhecido, o
cabeçalho fecha vazio, e o catálogo devolve três skills **sem nome e sem
handlers**. Sem erro, sem aviso — só a ausência do que devia estar lá.

O leitor já é `utf-8-sig`, que resolve. O que fica para trás é o ficheiro: uma
BOM num markdown é um acidenteo de gravação.

## Porque `contrato.py` é um módulo e não uma linha em `_schema_de_params`

São duas camadas com perguntas diferentes:

- `__init__.py` responde *"o que esta intent faz e que campos aceita"* — e essa
  resposta pertence a quem escreve a intent.
- `contrato.py` responde *"como é que um agente fala com isto"* — e essa
  resposta pertence ao protocolo, que muda por decisão de arquitectura, não por
  feature nova.

A divisão paga-se com testes que comparam as duas camadas
(`ContratoTest`, `ContratoNaoSeRepeteTest`), para que a divergência entre elas
não possa ficar em silêncio. É a mesma doutrina de `DECISÕES TOMADAS` D7: dois
testes de estrutura que leem **código**, nunca texto do ficheiro.

## Invariantes de fonte

Comportamento passa num teste e ainda assim sobra um atalho noutra linha. Por
isso os testes leem a **AST** de `__init__.py`, `views.py`, `servidor.py`,
`contrato.py` e `skills.py`, e falham se aparecer:

- `eval` / `exec` / `compile` / `__import__`;
- SQL montado à mão (tudo passa pelo ORM, que é quem aplica multitenant);
- import do sandbox diferente de `executar` / `somente_leitura` / `INTENTS` / `catalogo`;
- `sandbox.executar` chamado direto na view — tem que passar por
  `executar_para`, que é onde `via="mcp"` está escrito;
- `views.py` a montar o envelope OpenAI no lugar, ou a chamar `catalogo_tools()`
  fora da helper.

E dois `expectedFailure` para os defeitos **reportados e não corrigidos** acima.
`expectedFailure` é a codificação honesta de "isto está partido e eu não o
consertei": o teste passa em vermelho como esperado, e no dia em que alguém
consertar, o `unittest` transforma-o em falha a sério — no sítio exacto onde a
correção tem de ser feita.


## Coerência: a pergunta que nenhuma porta fazia sozinha

> Secção do bloco `coerencia.py`. Junta-se ao que está acima, que mediu o
> comportamento. Esta mede uma coisa diferente: **se o que a camada promete
> bate com o que o código faz.**

## O problema que só aparece quando se junta tudo

Cada porta da camada tinha testes, e todos verdes. O contrato publicava
`required`. O leitor sobrevivia a BOM. O CSRF passava. E a camada teve um
`expectedFailure` a dizer que **15 de 15** handlers declarados nas SKIs não
existiam — enquanto `/tools/` respondia 200 com 78 tools a dizer que sim.

Cada porta estava certa sobre o que dizia. Nenhuma sabia o que a outra dizia.

Um contrato é uma promessa feita a alguém que não está na sala. `/tools/`
promete que `amplia_x` existe; o `exec` tem de a saber executar; o
`amplia://skills` promete que aquele handler existe; o guia promete que
`confirm: true` funciona. **Era a relação entre as promessas que nunca tinha
sido verificada.**

## As dez perguntas

`GET /api/amplia/diagnostico/` traz `coerencia` ao lado de `invariantes`.

| # | Pergunta | O que apanha |
|---|---|---|
| 1 | toda tool de `/tools/` é de catálogo ou de intents? | uma tool com `x-intent` que não existe |
| 2 | **toda tool de `/tools/` tem rota em `/exec/`?** | uma tool nova no `TOOLS_CATALOGO` sem o `NOMES_CATALOGO` junto: o modelo é informado de uma capacidade que não existe |
| 3 | toda escrita declara `confirm` e não o põe em `required`? | o beco de confirmação |
| 4 | todo campo obrigatório é aceitável pelo schema que o declara? | `required: ["area"]` num schema que proíbe `area` |
| 5 | toda intent do registo chega ao cliente como tool? | a falha que a conversa do produtor apanhou |
| 6 | toda SKI aponta para handlers que existem? | os 15 fantasmas do § anterior |
| 7 | todo URI anunciado em `list_resources` é servido? | um recurso anunciado e ilegível |
| 8 | o guia afirma `confirm` e o contrato declara `confirm`? | texto que envelheceu |
| 9 | MCP e OpenAI publicam as mesmas tools? | duas traduções a divergir |
| 10 | `vocabulario()` lista os nomes todos? | um nome cortado do ficheiro de menor janela |

**Resultado hoje: 10 perguntas, 0 falhas.**

`tudo_ok` é a coisa que este bloco demonstra — e não a coisa que torna o
verificador fiável. O que o torna fiável é `tests_coerencia.py`, que **parte
o sistema de propósito** seis vezes, uma promessa de cada vez, e confirma que
a pergunta certa cai. Um verificador que devolve `tudo_ok` sobre um sistema
partido é pior do que não ter verificador: dá confiança a quem não a merece, e
a confiança que se poupa a pensar é a que produz o próximo bug em silêncio.

O verificador também **nunca levanta**. Um traceback não responde à pergunta
que ficou por fazer, e quem não lê o traceback todo conclui que o sistema está
bem. Encontrou-se isto a funcionar:

```
o verificador em si falhou: RuntimeError: import partido
```

## Por que AST e não o servidor a correr

A pergunta 7 precisa de saber que URI estão em `list_resources` e que
`read_resource` os serve. Fazer isso **a correr** exigiria `django.setup()`,
um `User` no banco e o SDK `mcp` instalado — um teste que falha por falta de
dependências e não por culpa do código.

E AST em vez de ler o texto do ficheiro, pela **doutrina D7**: o docstring do
`servidor.py` *nomeia* os recursos que descreve, e um teste que o lesse
passaria por ter encontrado a lista no comentário.

Foi por aqui que se encontrou um bug do próprio verificador, que é a melhor
lição do bloco:

> `async def` produz `AsyncFunctionDef`, não `FunctionDef`. A verificação só
> olhava para o segundo e **disse que `list_resources` não existia num
> ficheiro onde está escrito**. A pior resposta que um verificador pode dar:
> mente com confiança, e o leitor perde o fio em vez de procurar o defeito.

E um achado sobre o registo, que fica escrito porque é o erro que os testes
cometem sempre:

> Para simular "uma intent que não chega ao cliente", tirei a entrada do
> `REGISTO` — e **o teste passou com o sistema partido**. Porque
> `sandbox.INTENTS` foi importado no arranque do processo e continua a ter a
> entrada. É exactamente assim que um registo e um catálogo divergem sem
> ninguém ver. Parte-se o **lado do cliente**, que é o que diverge.

## Um teste que é change-detector, e o que ele custava

Fora do MCP, `CatalogoHigieneTest.test_flags_conhecidas` comparava cada flag
de cada intent contra uma lista de 35 strings escritas à mão. Traduzido:
*«acrescentar uma flag nova parte este teste»* — que é o trabalho normal de
qualquer feature.

É o antipadrão que a doutrina do repo já tinha condemnado noutro sítio. E é
como a coisa entrou na FILA como "flake": um teste que falha quando o sistema
cresce na direcção certa deixa de ser lido, e no dia seguinte em que falharia
por um motivo verdadeiro passa sem ninguém olhar.

O que o substitui mede **relações**, todas verificadas antes de escrever
(35 flags, 35 conformes, 0 mortas):

1. toda flag é `namespace.(read|write|create|comando)`;
2. nenhuma entrada da lista está morta;
3. a lista cobre o que o catálogo usa.

**E o que ele não apanha, dito em voz alta:** um erro de ortografia no
namespace. `irigacao.write` — sem o segundo `r` — passa a forma. O teste
antigo apanhava-o por acaso, porque o nome não estava na lista.

A troca é explícita: **forma é o invariante permanente; vocabulário é o que
se revisa à mão.** O que apanha esse erro hoje não é este teste — é
`sandbox.somente_leitura`, que trata flag nenhuma como escrita. Um typo
degrada para *fail-closed*, que é o lado seguro de errar uma flag.

A limitação está escrita em código, em `test_o_que_este_teste_nao_apanha`, com
`clma.read` e `irigacao.write` declarados como passando **de propósito**: se a
forma apertar e passarem a falhar, a mensagem diz o que fazer.


---

## O Chamado Amplia — a única peça onde a IA escreve

> Secção acrescentada pelo bloco do Chamado. Não substitui nada acima — o que
> estava medido e verificado continua estar.

## O problema que isto fecha

O AmplIA tinha **dois mundos que não falavam**:

| | manual | IA |
|---|---|---|
| widgets | 60 (`catalog.json`, `widget-palette.js`) | 17 (`palco.CATALOGO_IA`) |
| texto livre | não | **não** |
| editar | sim, à mão | **não** |

Os 17 da IA existem todos dentro dos 60 — **verificado um a um**. O problema
nunca foi que os widgets não existissem: foi a IA nunca ser informada dos outros
43, e não haver bloco onde texto, séries escolhidas ou colunas escolhidas
vivessem. Um gráfico era `chart-safras` — UM gráfico fixo. Uma tabela era
`table-financeiro` — UMA tabela fixa.

E o produtor não conseguia editar o que a IA fazia. `palco_clonar` gravava um
preset, e a barra de ações do palco (`palco-amplia.js`) só tinha "Salvar como
meu Dashboard".

## A trava

O produto tem presets que o produtor fixou, apagou, renomeou e organizou. Uma IA
com escrita amposta sobre eles reescreve o trabalho de quem os organiza.

Por isso a escrita tem **uma zona, e só uma**:

```python
pode_escrever(user, "chamado-amplia")  -> True
pode_escrever(user, "custom-custo")    -> False, com o motivo
```

`app/ia/chamado.py::pode_escrever` é a **única** função que decide. É chamada
dentro de cada handler, antes de qualquer coisa ser tocada — não num middleware,
não na view.

### Falha-aberta é a pior forma de uma trava

A primeira versão do handler de edição fazia:

```python
pode_escrever(user, params.get("preset") or ch.SLUG_CHAMADO)   # ERRADO
```

Com o `preset` vazio — ou ausente, ou o que um modelo de 1,7B envia quando não
sabe — a expressão caía no slug da zona e a trava **passava**. O `preset` que
não se consegue ler tem de ser um `preset` onde não se pode escrever.

O teste que fecha esta porta é
`tests_chamado_api.TravaTest::test_preset_ausente_nao_e_uma_passagem`.

### A razão volta escrita

Um `False` sem motivo produz o sintoma exacto que este produto já teve: o
produtor olha para ecrã nenhum e conclui que a IA está avariada. A mesma IA que
devolve *"nos teus presets a IA só lê — diz o que queres mudar e eu faço no
Chamado Amplia"* é uma IA que o produtor percebe.

### A trava também está no schema

Duas camadas, e nenhuma das duas chega sozinha:

1. **`enum` no `inputSchema`** — `preset` aceita um único valor. A restrição é
   legível por máquina, não é uma nota que se pode não ler.
2. **`CheckConstraint` na base** — `chamado_so_na_zona` torna *inválido, no
   próprio banco*, um Chamado com outro slug. Um handler com um bug não grava
   noutro preset: falha na base de dados, que é onde este género de erro tem de
   falhar.

## O que a IA pode construir

Cinco tipos de bloco, todos derivados do código (`app/ia/chamado.py`):

| bloco | o que é | `fonte_dado` |
|---|---|---|
| `texto` | prosa da IA | `medido` se nãonúmero sem apoio |
| `kpi` | um número, com `widget` do catálogo | `medido` com valor |
| `grafico` | séries **escolhidas** pela IA | `medido` com linhas |
| `tabela` | colunas **escolhidas** pela IA | `medido` com linhas |
| `planilha` | a que se exporta e o produtor corrige | `medido` com linhas |

### A norma: um número escrito tem de estar num bloco de dado

> *"um número que a IA escreveu tem de estar em algum bloco de dado da mesma peça"*

Sem esta regra, uma peça com "a margem caiu para 18%" e nenhum bloco que mostre
18% é uma peça que **afirma** — e é de afirmações que um produtor decide uma
safra.

O texto **não é recusado** (recusar é devolver "não posso escrever", o pior
 resultado possível). O texto entra e desce a `sem_dado`, com o aviso escrito em
português no `resposta` — porque o aviso é para o produtor, não para o log.

Datas e anos não contam: `12/03/2026` e "safra 2024" são o próprio dado, não uma
medida.

## Onde o catálogo é publicado

**Não há uma tool nova.** Os blocos vivem dentro de `amplia_catalogos`, e
`amplia://blocos` é um recurso.

A decisão é do produto e já estava escrita em dois testes:

> *"Duas, não cinco. Cada tool extra é uma escolha a mais para errar."*
> *"Uma tool nova apareceu. Cada tool extra é uma escolha a mais para o modelo errar — e o contexto já chega."*

Para um SmolLM2 de 1,7B a correr na aba, cada tool nova é um nome a mais para ser
escolhido mal. O que o modelo precisa é o **dicionário**, não mais um botão onde
o buscar. E um recurso não se escolhe — pede-se pelo nome.

Houve uma `amplia_chamado_blocos` separada, e foi removida de propósito.

## As quatro intents

| intent | escrita? | o que faz |
|---|---|---|
| `amplia_chamado_criar` | sim | monta a peça (substitui se já existe) |
| `amplia_chamado_editar` | sim | muda por **delta**, nunca substituindo tudo |
| `amplia_chamado_ler` | **não** | mostra o corpo, os `id` e o `versao` |
| `amplia_chamado_publicar` | sim | arquiva (a IA passa a só ler) ou reabre |

O **delta** existe porque substituir a peça obriga a IA a reenviar o que já
está feito — e um modelo de 1,7B a reenviar 12 blocos perde dois e muda um sem
querer. O produtor vê uma peça que perdeu conteúdo e conclui que a IA desistiu.

Operações: `adicionar`, `remover`, `substituir`, `reordenar`, `reescrever_texto`.

O `versao` impede que duas edições a partir da mesma leitura se sobreponham: a
segunda escreveria o corpo antigo por cima do novo, e o produtor veria uma
alteração sua desaparecer sem ninguém a ter tocado.

## A escrita continua a passar pelo sandbox

`GET /api/amplia/palco/chamado/` — **só leitura**. A widget-bar precisa de ler
para desenhar; não precisa de escrever. Um `POST` aqui seria um segundo caminho
de execução, que é exactamente o que `app/amplia_mcp/` existe para não ter — e
que o `InvarianteDeFonteTest` traverse o código por AST para apanhar.

## Ficheiros

| Ficheiro | O quê |
|---|---|
| `app/ia/chamado.py` | O catálogo de blocos, a trava, o delta e a rastreabilidade. |
| `app/ia/chamado_intents.py` | As 4 intents. Auto-descobertas por `registro.py`. |
| `app/models/palco.py` | `ChamadoAmplia`, com as duas constraints. |
| `app/api/views/amplia_palco.py` | `GET /palco/chamado/` e a zona em `/palco/info/`. |
| `app/ia/tests_chamado.py` | 43 testes: catálogo, trava, delta, rastreabilidade. |
| `app/ia/tests_chamado_api.py` | 43 testes: ponta a ponta, tenancy, contrato. |


---

## As FONTES — porque é que a IA não escreve números

> Acrescentado depois de a primeira versão estar a correr. É a correcção mais
> importante que esta peça já levou, e a história vale mais do que a regra.

### O buraco

A primeira versão deixava a IA escrever as **linhas** de uma tabela, de um
gráfico ou de uma planilha — e marcava o bloco `medido` por ter linhas. Medido,
em rigor:

```
fonte_dado = medido
linhas     = [['Adubo', '1.234,56'], ['Semente', '900,00']]
```

As duas linhas saíram de um modelo de 1,7B. Não há consulta nenhuma por trás
delas.

Isto não é um detalhe de estilo. É o que `paginas.py` chama, com razão:

> *"Um número gerado não é um número pequeno: é um número que não dá erro. Uma
> balança que não está ligada devolve 50,4 sc/ha com a mesma confiança de uma
> balança ligada, e o produtor multiplica pela área dele."*

Tinha uma agravante que só apareceu quando testei com o modelo a escrever: o
`rastrear_numeros` que eu tinha escrito marcava o "18%" do **texto** como sem
apoio — e tratava a **tabela inventada** como evangelho. O validador era mais
rigoroso com a prosa do que com a malha.

### A regra

> **A IA escolhe a FONTE. O servidor escreve os NÚMEROS.**

Não há linhas no pedido. A IA diz `fonte: "despesas-por-categoria"`, o servidor
consulta o banco, aplica o tenancy e devolve as linhas com a procedência.

| o que a IA manda | o que acontece |
|---|---|
| `fonte` conhecida | o servidor calcula, `fonte_dado: medido` |
| `fonte` desconhecida | linhas descartadas, `sem_dado`, com o motivo |
| sem `fonte` | linhas **descartadas**, `sem_dado`, com o motivo |

### Descartar, e não mostrar com um carimbo

A alternativa era mostrar as linhas da IA marcadas a `sem_dado`. Parece mais
honesta — e é mentira igual: um número inventado à vista do produtor, mesmo
marcado, é um número que ele vai ler, porque está numa coluna com o nome certo
e algarismos com o formato certo.

A diferença é entre *"a despesa foi 1.234,56, e este número não vem de lado
nenhum"* e *"não sei a despesa — escolhe uma fonte"*. A primeira ainda se pode
usar por engano. A segunda obriga a decidir.

### A base guarda a receita

`ChamadoAmplia.corpo` guarda `fonte` e `filtros` — **nunca as linhas**. Os
números são calculados na leitura.

Duas consequências, ambas queridas:

1. **nada que a IA escreveu fica gravado como se fosse medido**;
2. **a peça não envelhece** — pergunta ao banco de cada vez, e o número de
   ontem já não é o número de hoje.

O teste que fecha isto é de ESTRUTURA: lê o AST dos handlers e falha se
aparecer uma gravação a `corpo` sem passar por `_guarda`.

### Um bug que esta regra deu

`f_receitas_despesas` usava `Sum` sem o importar. O `NameError` foi engolido
pelo `except` de `calcular`, que devolvia `ok: False` — e o bloco descia a
`sem_dado`, que o painel lê como "não há registo".

**Um bug de código vestido de ausência de dado.** O produtor vê "não há
lançamentos" e conclui que não lançou nada.

Corrigido o import, e `calcular` passou a distinguir `falhou: True` de "não há
registo". E o teste que apanha a classe inteira — `test_toda_fonte_responde` —
corre **todas** as fontes contra dados reais, porque um import em falta numa
das seis fontes só aparece quando alguém a chama.

### Um contador que media zero

`numeros_descartados` diz quantos números a IA escreveu e foram deitados fora.
É o número que explica ao produtor a diferença entre *"a peça está vazia porque
não há registo"* e *"a peça está vazia porque o que a IA escreveu foi
descartado"*.

Vivia num sítio onde não podia sobreviver. `_guarda` tira `linhas` antes de
gravar — e está certo: a base não guarda números de um modelo. Mas a leitura
contava os descartes por `len(cfg["linhas"])`, e a essa altura `linhas` já não
existe. O contador dava **sempre zero, em qualquer peça, para sempre**.

Zero aqui não era "nada foi descartado": era "ninguém contou". E é o pior dos
dois casos, porque um contador em branco obriga a perguntar e um contador em
zero afirma. O produtor lia "0 descartados" numa peça de onde a IA tinha
mandado quatro.

Duas metades, porque a informação morria em duas sessões:

- `_guarda` passou a contar as linhas **antes** de as tirar, e a gravar a
  contagem no bloco. É metadata sobre a escrita, não um número do produtor
  disfarçado de medição.
- `aplicar_fontes` passou a usar `max(contou_agora, ficou_registado)`. Sem isto,
  a leitura escrevia por cima do registo com o seu próprio zero.

O teste que fecha a classe chama a leitura **duas vezes**: uma peça aberta
agora e outra vez logo a seguir têm de dar a mesma contagem.

### O painel que se desenha por baixo

O painel do Chamado montava-se no `#content` e ficava **por baixo da matriz
bento**. Não por erro de selector: o dashboard crava a matriz com

```css
body:has(.matrix-container.liquid-glass) #content .matrix-container.liquid-glass {
  position: absolute !important; inset: 0 0 56px 0;
}
```

dentro de um `#content` com `overflow: hidden`. Ou seja: o `#content` não tem
espaço de flow para mais nada. O que se ligar lá fica tapado.

Isto só apareceu no browser. Os 50 checks do `tests_chamado_amplia.cjs` passavam
— o DOM de mentira não tem CSS, e sem `position:absolute` não há nada por
cima. O botão estava no DOM, e o Playwright clicava-o por seletor; um rato
acertava no `grid` da matriz. **Um botão que aceita o clique e não faz nada é
pior do que um botão que não existe**, porque o primeiro promete.

A correção mede em vez de adivinhar: `elementFromPoint` no canto superior
esquerdo, que responde o que o rato alcança. Se não for o próprio host, o
painel é **recortado** e a consola diz porquê e o que fazer.

Duas armadilhas que essa medição perdeu, e que ficaram escritas no código:

- **Estrutura não é pintura.** A primeira versão decidia por árvore do DOM
  ("a matriz é filha do mesmo pai que a âncora?") e escreveu a comparação ao
  contrário. O guarda disse "livre" e montou por cima da evidência.
- **Medir cedo demais também é não medir.** O módulo corre com `defer`, antes
  de a matriz estar pintada: `elementFromPoint` devolve o próprio host e o
  guarda passa. A medição foi adiada para depois do primeiro quadro, e
  repetida no `load` e no `resize` — as três alturas em que o sítio pode mudar.

### Onde o Chamado vive: é um widget da matriz

**Decisão: o Chamado é um widget bento do painel.** Não uma âncora fora da
matriz. E a razão não é Preference, é a arquitectura:

- O painel crava a matriz com `position:absolute !important` dentro de um
  `#content` com `overflow:hidden`. **Não há espaço de flow para mais nada** —
  qualquer contentor que se ligue ao `#content` fica por baixo da matriz.
- Brigar com `!important` para o Chamado passar à frente seria uma correcção
  que o próximo `liquid-glass.css` desfaz.
- Widget é o sítio onde o produtor decide a posição, o tamanho e se a quer. Um
  painel que não se pode mover nem tirar não é um widget: é um banner.

A integração toca em **dois sítios**, e não no `index.html`:

| Sítio | O quê |
|---|---|
| `dashboard-desktop.js` → `WIDGET_TYPES` | a ficha: título, ícone, tamanho por omissão |
| `dashboard-desktop.js` → `asseguraChamadoNoLayout()` | acrescenta a peça ao layout de quem já tem painel, numa linha livre abaixo de tudo |
| `chamado-amplia.js` | desenha dentro de `#widget-chamado-amplia .widget-content` |

O `index.html` **não** é tocado: o `generateWidgetContent` dele não conhece este
id e devolve o seu fallback, que já traz um `.widget-content` dentro do
`#widget-chamado-amplia`. O contentor que o frontend precisa já nasce.

**A posição não empurra o painel de ninguém.** Quem já tem widgets vê o Chamado
abaixo de tudo, à direita. Empurrar o painel de alguém para mostrar uma coisa
nova é o tipo de melhoria que se sente como invasão.

### Quem manda no desenho: um embrulho, não um observador

`index.html` redefine `window.renderWidgetsOnMatrix` **duas vezes**, e é a
versão dele que pinta. Um gancho posto no `dashboard-desktop.js` seria um gancho
sobre código morto.

Por isso o `chamado-amplia.js` **embrulha** `window.renderWidgetsOnMatrix`:

```
antes:  asseguraChamadoNoLayout()   -- garante o lugar no layout
        o renderizador do painel     -- pinta, e escreve o texto genérico
depois: o desenho, no PRÓXIMO QUADRO
```

Três coisas que só o browser mostrou, e que estão todas comentadas no código:

1. **No quadro seguinte, não dentro da chamada.** O painel escreve o conteúdo
   dos widgets em mais do que um momento. Desenhar dentro da chamada é desenhar
   antes de o painel acabar — e o contentor ficava marcado como desenhado e
   vazio, com "Chamado da IA" por cima.

2. **O marcador não prova que a peça está lá.** A pergunta que decide é "está a
   peça neste contentor?", e a resposta muda com o que se procura dentro dele.
   Um contentor marcado e vazio é o que produz um painel que parece funcionar.

3. **O gancho instala-se tarde.** O `index.html` substitui a função depois de
   nós a embrulharmos, e uma página que já pintou não gera mutações — logo o
   observador não descobre que houve troca. Daí as tentativas com prazo.

E o observador fica como rede de segurança, porque `renderWidgetsOnMatrix` não é
a única forma de um `.bento-block` ser trocado.

### Uma pergunta pendente não pode sequestrar uma chamada de tool

Este é o mais grave dos quatro, e nenhum teste o apanhava.

`executar()` recupera o estado conversacional — `COLETANDO_DADOS`,
`AGUARDANDO_CONFIRMACAO` — para transformar a resposta do produtor no resto do
que faltava. Fazia isso sempre que `estado_atual` não fosse "NENHUM",
**incluindo numa chamada sem `entrada`**: um tool call programático, que traz
`tool` e `args` completos e não é resposta a nada.

O que acontecia: o `chamado_editar` pedia o `delta`, e o `chamado_criar`
seguinte — completo, explícito — recebia *"O que queres mudar?"* e **`ok:
true`**. Nos testes, uma peça reescrita que nunca aparecia, com o servidor a
dizer que correu bem.

Um `ok: true` que mente é pior do que um erro: o modelo avança, o produtor fica
com a peça antiga, e a causa aparece do lado errado — o teste aponta para o
sintoma, no `toContainText`, e a causa está no sandbox.

A regra que fecha a classe:

> Uma máquina de estados conversacional retoma-se com uma **RESPOSTA**. Sem
> `entrada` não há resposta, e portanto não há nada a retomar.

O estado pendente **não** é apagado por uma chamada programática: deitar fora a
pergunta que o produtor ainda pode responder é pior do que a deixar à espera.
`app/ia/tests_sandbox_estado.py` cobre os dois sentidos — o sequestro, e a
conversa a continuar a funcionar.

### O `@never_cache` que faltava

`palco_chamado` é a leitura da peça, e não tinha `never_cache`. Um `GET` de uma
API pode ser servido do cache do browser, e o efeito era o produtor ver a peça
antiga depois de a IA ter reescrito uma nova — sem erro, sem aviso. Uma peça que
acabou de mudar é o caso em que o cache é exactamente a coisa errada.

### O `npm run test:e2e` não arrancava — e o erro não dizia porquê

Ao fechar o Chamado, a suite e2e do repositório foi um alvo: o `chamado.spec.ts`
vive em `tests/e2e/`, que é o `testDir` do config partilhado. Correu-se
`npm run test:e2e` e deu:

```
Error: Timed out waiting 120000ms from config.webServer.
```

A causa: o config arrancava **dois** servidores, e o primeiro — `npm run dev`, o
vite — **não tem nada para servir**. O `vite.config.ts` tem `root: '.'` e
`base: '/static/dist/'`, mas **não há `index.html` na raiz do projecto**: o
único index é `app/templates/index.html`, que é um template do Django. O vite
responde, e devolve 404 em `/` e em `/static/dist/`.

Aqui o vite é ferramenta de **build** (`npm run build` → `tsc && vite build`,
`outDir: 'staticfiles/dist'`), e o bundle é servido pelo Django por
`{% static %}`. Não há página no vite para abrir.

E o webServer era peso morto: nenhum spec dos `tests/e2e` pede a porta 5173 nem
o bundle — todos navegam para páginas do Django. O servidor que não servia nada
impedia o servidor que serve o Runs de arrancar.

O config ficou com **um** servidor. E com a correcção, a suite passa a executar —
o que timezone reveals de rotação que estava escondida: `critical.spec.ts` (10
falhas), `demo.spec.ts` (3) e `widgetbar-windows.spec.ts` (2) não corriam desde
que alguém os escreveu, e falham por selectores obsoletos (`getByRole('link',
{name: 'ampliagro'})` já não é unívoco). Nenhum é do Chamado.

### Um ficheiro declara o que ele precisa

O `chamado.spec.ts` põe `test.describe.configure({ mode: 'serial' })`, e não é
capricho: há **uma peça por produtor** — é uma `UniqueConstraint` no banco — e
todos os testes do ficheiro escrevem a peça do mesmo `demo`. Com
`fullyParallel: true` e vários workers, dois testes reescrevem o que o outro
acabou de pôr, e a falha aparece no `toContainText` muito abaixo do sítio onde o
problema está, que é a concorrência.

A alternativa era `workers: 1` no config partilhado, que tornaria a suite de
toda mais lenta por causa de um ficheiro.

### O login verifica-se

Com a suite a correr em paralelo, todos os specs escrevem na mesma base SQLite
ao mesmo tempo, e um login pode não completar. A falha aparecia como "o bloco
não tem a marca", mil linhas abaixo e do lado errado do problema.

O helper faz login e **confirma que entrou** (o painel responde e o `#ia-dock`
existe), com uma segunda tentativa. Não esconde um login partido: se o segundo
também falhar, o teste continua a falhar, e com a mensagem certa.

### Ficheiros

| Ficheiro | O quê |
|---|---|
| `app/ia/chamado_fontes.py` | O registo de fontes, com tenancy em todas. |
| `app/ia/tests_chamado_fontes.py` | 20 testes: descarte, cálculo, tenancy, apoio. |
