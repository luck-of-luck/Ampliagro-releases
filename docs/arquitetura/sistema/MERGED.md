# MESCLAGEM — Consolidação das análises

**Autores:** agente 1 (síntese original) · **agente 4** (secções 7 a 9, acrescentadas depois)
**Data:** 2026-10-04
**Material:** `1.md` · `2.md` · `3.md` · `4.md` · `5.md` · `6.md` · `7.md` · `9.md` · `10.md`
**`8.md` não existe e não vai existir** — o número foi atribuído a um ficheiro que nunca foi escrito. A amostra é **8 documentos**, não 9.
**Como esta secção foi acrescentada:** o `MERGED.md` foi escrito sem a `4.md`. As secções 7 a 9 foram mais tarde pelo agente 4, e estão marcadas como tal. **Não substituem as secções 1 a 6** — acrescentam-se.

---

## 7. CONTRIBUTOS DO AGENTE 4 (acrescentado depois da síntese original)

Esta secção cobre uma área que **nenhum dos outros sete agentes reclamou**: a política de segurança do navegador, a integridade do JavaScript do dashboard, a integração Vite e o pipeline de testes JavaScript. As secções 2 a 5 acima não tocam nela — `rg` por `eslint`, `prettier`, `5173`, `sourcemap` e `presets-carousel` nos outros sete documentos devolve zero.

### 7.1 CONFIRMADO — Um `{% tag %}` dentro de um comentário `{# #}` continua a ser código

Achado meu, do meu próprio erro, e é o mais facilmente reutilizável desta secção.

O primeiro `base.html` que escrevi documentava a correcção do Vite **citando as tags dentro do comentário**. Resultado: `TemplateSyntaxError: Unclosed tag on line 114: 'if'`. A página `/` deixou de compilar e o `tests/test_csp.py` foi de 9/9 para 8/9.

Reproduzido isoladamente:

```
comentario com {% if %} dentro          →  ERRO: Unclosed tag on line 2: 'if'
comentario com {% vite_asset %} dentro  →  COMPILA (mas é analisado como tag)
```

Ou seja: **o interior de um `{# ... #}` é lido como código.** Agrava porque o parágrafo que *explica* o problema não pode escrever o problema com a forma dele — ao escrevê-lo, fecha o próprio comentário. Tive de escrever "uma chave" em vez de mostrar a chave.

> **Regra:** nunca escrever uma tag Django dentro de um comentário de chave. O bloco `{% comment %}...{% endcomment %}` é que trata o interior como texto.

### 7.2 CONFIRMADO — `npm run lint` nunca pode ser aplicado como está

| | Antes | Depois |
|---|---|---|
| Tempo | **>240 s** (cortado por mim) | **9,7 s** |
| Erros reportados | 0 (não terminava) | 10, todos reais |
| Ficheiros percorridos | 465 | só `app/`, `src/`, `tests/` |

Duas causas, ambas minhas:

1. **Sem escopo.** O `eslint .` ignorava só `node_modules/` e um ficheiro. Percorria `.venv/Lib/site-packages/**` (o admin do Django: jQuery com 8.654 linhas), `staticfiles/` (output de build), `scratch/` (rascunhos com 10.892 linhas) e `ia-local.js` (6.926).
2. **Prettier como regra de lint.** Com `eslint-plugin-prettier`, `prettier/prettier` é **error**, e `--max-warnings 0` faz o lint falhar em dívida de formatação **pré-existente**. Instalar o plugin **piorou** o lint. O ficheiro mais pequeno que testei dava 6 erros.

**O que o lint passou a dizer, e que ninguém sabia:**

```
ia-local.js:240  no-dupe-keys  Duplicate key 'animais-individuais'
ia-local.js:241  no-dupe-keys  Duplicate key 'pesagens'
ia-local.js:244  no-dupe-keys  Duplicate key 'eventos-sanitarios'
ia-local.js:247  no-dupe-keys  Duplicate key 'leituras'
ia-local.js:250  no-dupe-keys  Duplicate key 'gateways'
```

**CONFIRMADO, e sem exagerar:** as 5 chaves duplicadas têm **valor idêntico** nos dois sítios. **Não há bug de comportamento hoje.** O que há é uma armadilha: num object literal o último vence, e o primeiro é descartado **em silêncio** — editar a linha de cima não faria nada, e nada diria que não fez. Corrigidas, com o raciocínio escrito no sítio.

### 7.3 CONFIRMADO — `tsc` tem inputs e está a falhar

`Dockerfile.prod:70` diz que `tsc` falha com TS18003 "No inputs were found". **Isso é verdade dentro da imagem** (que copia `src/`, não `tests/`) e **falso localmente**: o `tsconfig.json` tem `"include": ["src", "tests"]`.

Logo, localmente `tsc --noEmit` **dá erros reais**:

```
tests/e2e/chamado.spec.ts:70    TS7006  Parameter 'blocos' implicitly has an 'any' type
tests/e2e/modelo-local.spec.ts:29  TS2339  Property 'goto' does not exist on type 'URL'
```

O do `modelo-local` é um bug real: `page` está tipado como `URL` em vez de `Page`, o que torna `page.goto()` um erro de tipos.

**Consequência:** `npm run build` (`tsc && vite build`) e `npm run typecheck` estão **ambos a falhar**. Fora do meu âmbito, e digo-o em vez de o esconder atrás de um `--quiet`.

### 7.4 O padrão que atravessa os três documentos: correcção documentada como feita, e não feita

Este é o achado estrutural, e é o mesmo nos três sítios:

| Onde | Afirma | Realidade |
|---|---|---|
| `Dockerfile.prod:58` | *"Retirar esse `if` (já feito no template)"* | O `{% if VITE_ATIVO %}` **continuava lá**. O bundle de 51 KB era construído pelo stage `frontend` e **nunca referenciado** |
| `base.html` (HEAD) | *"O bundle carrega SEMPRE"* | Não carregava nunca em produção |
| `base.py` (HEAD) | Política completa de CSP | `django-csp` 4.0 lia outra sintaxe; `build_policy()` devolvia `''` e **o header nunca era emitido** |

Nenhum é um erro de raciocínio — são os três **a mesma coisa**: alguém escreve no comentário o que a correcção faz, e a correcção não chega a ser aplicada. Nenhum teste apanha um comentário. Por isso o CSP levou a ser adormecida, e o bundle a ser construido para nada.

> **A regra que sai disto, e que se aplica a tudo neste repositório:** um guarda tem de ler o **estado**, nunca o **comentário**. Foi o que fiz com `test_csp.py::test_a_politica_esta_no_formato_que_a_middleware_le` e com `test_hmr_continua_condicional_e_o_bundle_nao` — ambos passam hoje e ambos falhariam se alguém voltasse a escrever a mentira.

### 7.5 CONFIRMADO — Uma guarda pode passar por vazio, e a minha passou

Escrevi `test_o_dev_server_so_entra_em_debug` para afirmar que a origem do dev-server só entra em DEBUG. **Passava — sem nunca exercitar o caminho que importava.** Duas razões, ambas minhas:

1. Sob `pytest`, `settings.DEBUG` é `False` (o `pytest-django` põe-no a False **em runtime**, depois do import). O teste comparava `False == False`.
2. **O receptor do sinal tinha um bug**: retornava antes de se ligar, porque `kwargs.get("setting")` era `None` num `adding=True`. A origem nunca era adicionada — e o teste confirmava que não era adicionada. Passava por estar certo.

Corrigi com `override_settings`, que é a via que dispara `setting_changed`, e escrevi um segundo teste que força os dois estados:

```python
with override_settings(DEBUG=True):   # tem de estar
with override_settings(DEBUG=False):  # tem de NÃO estar
```

E um terceiro detalhe: `directivas()` devolve **cópias**. Chamar uma vez e usar o resultado fora dos blocos media o snapshot, não a política.

### 7.6 O que o agente 4 implementou (medido, não prometido)

| # | Acção | Verificação |
|---|---|---|
| 1 | `base.html`: `vite_asset` **fora** do guard, `vite_hmr_client` dentro | `test_hmr_continua_condicional_e_o_bundle_nao` |
| 2 | `base.py`: dev-server na CSP **só em DEBUG**, ligado a `setting_changed` | `test_o_sinal_segue_o_debug_nos_dois_sentidos` — 4 transições verificadas |
| 3 | `tests/gerar_clima_render.py`: senha fora do repositório, `AMPLIAGRO_DEMO_SENHA` do ambiente, fixture portátil | `rg` do segredo → 0 ocorrências no código |
| 4 | `eslint.config.mjs`: prettier fora do lint, `ignores` com 9 entradas | 240 s → **9,7 s** |
| 5 | `ia-local.js`: 5 chaves duplicadas removidas | `no-dupe-keys` → 0 |
| 6 | `ci.yml`: passos de Python, conta demo, geração do dump, lint | YAML parse OK; `sed` testado em git-bash contra o stdout real |
| 7 | `vite.config.ts`: `sourcemap: 'hidden'` em vez de `false` | ver 7.7 |
| 8 | `.prettierignore` novo | protege 107 templates / 34.170 linhas |
| 9 | `index.html`: 2 linhas desindentadas restauradas | CRLF preservado (14.656), handlers 132 → 132 |

`tests/test_csp.py`: **13 passed** (era 9; os 4 novos são os guards acima).

### 7.7 O `sourcemap: false` que estava no `vite.config.ts`

A intenção era boa (um `.map` expõe o fonte inteiro; 144.683 bytes medidos em `staticfiles/`). O remédio estava errado por duas razões, ambas verificadas:

1. **Não teve efeito.** `staticfiles/dist/js/legacy.C6Z7LlIz.js:4` **ainda tem** `//# sourceMappingURL=...` enquanto o `.map` não é recriado. Só um rebuild + `collectstatic` limpa.
2. **Estragou o Sentry.** `base.py:703` liga o Sentry com `SENTRY_DSN`, e `browser.sentry-cdn.com` está na CSP. Sem mapas, um stack trace de produção chega ao painel como `legacy.C6Z7LlIz.js:1:482913`.

`'hidden'` genera o `.map` e **não** acrescenta o `sourceMappingURL` ao bundle. **O que falta para fechar:** rebuild + collectstatic, e um `sentry-cli sourcemaps upload` — este último não foi feito porque precisa de `SENTRY_AUTH_TOKEN` e não me foi pedido. Está escrito no ficheiro.

### 7.8 O que o agente 4 NÃO fez, e porquê

- **A migração da CSP estrita** (os 606 handlers `on*=`). É um plano de **dois passos** e o passo 2 é caro. Fazer só o nonce hoje **mata** os handlers — pela spec, `'unsafe-inline'` é ignorado quando há nonce. Deixado por fazer de propósito: meio nonce é pior que `'unsafe-inline'`.
- **O renderizador duplo de `#presets-carousel`.** `index.html:13200` (div, com drag/editar/apagar) e `widget-bar-intelligent.js:212` (button, com `onclick` inline) escrevem no mesmo sítio; 14 linhas do `index.html` chamam o primeiro. **Não escolhi ao acaso** — a decisão tem de vir de um teste de comportamento que compare o DOM dos dois, e esse teste não existe. Escolher o externo "porque é mais limpo" perde funcionalidades; escolher o inline mantém a dívida.
- **Os 9 `eslint-disable` mortos** que sobram. `npm run lint -- --fix` resolve-os. **Não os corrigi** porque estão em ficheiros de outros agentes que estavam a ser escritos — `--fix` reescreve o ficheiro inteiro, e com escrita concorrente isso pode comer trabalho alheio. Commando exacto, decisão de quando, não minha.
- **`sentry-cli sourcemaps upload`**, por razão acima.
- **A validação da cadeia do clima ponta a ponta.** `config.settings.test` usa SQLite `:memory:`, e cada `manage.py` é um processo novo — as tabelas desaparecem entre comandos. Só se valida com uma base persistente, e **não escrevi na `db.sqlite3` de dev** para o fazer. O que **foi** verificado: o `sed` de extracção da senha, em git-bash, contra o stdout verbatim do comando; e o caminho de erro do gerador (exit 2 com mensagem que diz o que fazer).

### 7.9 Correcção a `MERGED.md`

A secção 5 (§"O QUE NENHUM DOS 7 VERIFICOU") diz *"`4.md` e `8.md` não existem. A amostra é 7 de 9."* Está errado nos dois sentidos: o `4.md` existe (379 linhas) e o `8.md` **não vai existir**. Amostra: **8 documentos**.

Acrescentar a esta lista do que ninguém verificou: **`gitleaks`, `codeql`, `trivy`, `grype`, `osv-scanner`, `zap`, `bearer` continuam indisponíveis.** O agente 4 também não os executou. E o facto de haver uma senha real em texto claro no repositório — agora removida do código, mas presente em `ia-coord/ia-2/RELATO-VARREDURA.md`, que é um relatório de outro agente — torna a ausência de `gitleaks` mais uncomfortable, não menos.

---

## 1. VALIDAÇÃO — integridade das referências

Verifiquei mecanicamente: extraí cada `ficheiro:linha` dos 7 documentos, indexei os **3.537 ficheiros** do projecto e confirmei que cada referência resolve e que a linha existe.

| Ficheiro | refs OK | só basename | inexistentes | linha fora |
|---|---|---|---|---|
| 1.md | 67 | 3 | 0 | 0 |
| 2.md | 117 | 2 | 2 | 0 |
| 3.md | 48 | 2 | 1 | 0 |
| 5.md | 31 | 2 | 0 | 0 |
| 6.md | 114 | 0 | 0 | 0 |
| 7.md | 80 | 1 | 0 | 2 |
| 9.md | 64 | 3 | 0 | 0 |
| **TOTAL** | **521** | 13 | **3** | **2** |

**Veredicto: integridade alta.** **Zero números de linha inventados** em 7 documentos. Isto é raro e é o sinal de que o material é trustworthy.

### As 5 excepções, todas resolvidas

| Ref | Quem | Resolução |
|---|---|---|
| `app/iot/management/commands/mqtt_listener.py` | **2, 5, 6, 7, 9** | **Explicada e CONFIRMADA — o ficheiro foi APAGADO.** Ver §3.2 |
| `tests/aparencia_baseline.js` | 3 | Defeito real. Existe `tests/test_aparencia_invariante.py` e um `*_baseline.json` |
| `app/verificar_doutrina.py` | 2 | Defeito real — não existe em lado nenhum |
| `iot.py:334` / `iot.py:353` | 7 | **Falso positivo do meu validador.** `7.md` cita `app/ia/iot.py` por basename; o resolver escolheu um `iot.py` mais curto. As linhas são válidas |
| `app/static/manifest.js` | 1 | **Falso positivo do meu regex** — casou `manifest.json` como `manifest.js` + `on`. `1.md` está limpo |

---

## 2. ONDE OS 7 CONCORDAM — e isso vale mais que qualquer ficheiro

Convergência independente é o sinal mais forte que existe. Estes pontos foram medidos por ≥3 agentes, por caminhos diferentes:

### 2.1 A doutrina de proveniência está partido em DOIS vocabulários

Todos os 7 tocaram na proveniência. **A divergência foi real e está resolvida — e o erro era meu.**

```
app/validators.py:11-17   ESTADOS_FONTE = {medido, medido_com_ressalva, suspect,
                                           sem_dado, declarado}      ← 5 estados
app/ia/proveniencia.py:68 TODOS = (MEDIDO, SEM_DADO, SIMULADO)      ← 3 estados
app/models/producao.py:605  choices inclui ("declarado", ...)        ← 3.º sítio
```

| Quem | Disse | Veredicto |
|---|---|---|
| **agente 2** | `validators.py`, 5 estados + `declarado` | ✅ **ACERTOU** |
| **agente 1 (eu)** | "3 estados, não cinco; `Declarado` não existe" | ❌ **ERREI** — li só `proveniencia.py` |
| **agente 9** | "CONFIRMADO — os três, não cinco"; `DECLARADO` não existe | ❌ **ERROR INVERSO** —transformou a minha leitura parcial em "CONFIRMADO" |
| agente 7 | citou `proveniencia.py:122-149` | ⚠️ mesmo ângulo parcial |

**O manifesto Agro 5.0 está CORRECTO na doutrina central.** Os cinco estados dele são exactamente os de `validators.py:11-17`, e a "regra pétrea" está em `validators.py:40-41`:

> *"o sistema nunca promove uma afirmação a medição. Quem mediu foi o sensor; quem afirmou foi a pessoa."*

**O que está realmente mal não é falsificação — é coerência interna:**
1. `ia/proveniencia.py:68` **omite `declarado`**. O painel pode marcar um dado que o produtor afirmou como se fosse medido — exactamente o que `validators.py:26-37` diz ser mentira.
2. `validators.py:9` diz *"o mais importante dos **seis**"* mas o conjunto tem **cinco** (`:24` diz que "só tinha quatro"). Comentário a contar mal.

> **Lição metodológica:** o agente 9 convergiu comigo e transformou o meu erro em "CONFIRMADO". **Convergência entre agentes não valida um erro — amplifica-o.** O que valida é o código.

### 2.2 `AMPLIAGRO_DATA_KEY` não existe

Agentes 1, 3 e 9, por caminhos diferentes. A única Fernet em `base.py` é `BACKUP_ENCRYPTION_KEY` (protege backups, não ingestão). O mecanismo real é `Gateway.api_key` com Fernet (`iot/views.py:55`) — **nome e âmbito diferentes do que o manifesto promete.**

Agente 9 acrescenta o ângulo mais duro, e é o certo: a §IV do manifesto diz que a **monetização de carbono** depende da pureza criptográfica. Se a telemetria não tem a criptografia declarada, **a cadeia de custódia do carbono assenta numa promessa.**

### 2.3 O Caderno de Campo offline é feature fantasma

Agentes 1 e 6, independentemente. O 6 diz explicitamente (`:37`): *"Corroborei o agente 1 por via independente — `caderno` não aparece em nenhum `urls.py`, e não existe modelo `Nota`/`Foto`/`Voice`. Corroborado, não citado."*

### 2.5 A CSP estava ligada e não fazia nada (agente 4) — CONFIRMADO por execução

**O achado de segurança mais subtil dos 9 documentos, porque nada nele parece errado.**

| Facto | Estado |
|---|---|
| `django-csp` instalado | **4.0** |
| O 4.x lê | `getattr(settings, "CONTENT_SECURITY_POLICY", {})` |
| O que o `base.py` tinha | sintaxe **3.x**: `CSP_DEFAULT_SRC`, `CSP_SCRIPT_SRC`, `CSP_FRAME_ANCESTORS` |
| `CSPMiddleware` | ligado (`base.py:120`) — e a carregar sem erro |

A cadeia, isolada pelo agente 4:
```python
cfg = getattr(settings, 'CONTENT_SECURITY_POLICY', {})   # -> {}   porque a chave 3.x nao existe
default_config(...) if cfg else None                     # -> None
# e o middleware so escreve se for truthy:
if csp:  response[HEADER] = csp                          # -> nada
```

**O middleware estava ligado, a política era `{}`, o cabeçalho nunca saía.** A defesa XSS estava **desligada a parecer ligada** — que é a forma mais perigosa de falha, porque passa a code review e a todos os testes que não verifiquem o cabeçalho.

> **Isto generaliza os dois primeiros achados desta mesclagem.** Nenhum dos três — revogação, Proveniência, CSP — falhou por código errado. Falharam por **configuração ou convenção que ninguém verificou contra a coisa que a consome**. `IsAuthenticated` não distingue revogado de activo; `{}` não se distingue de uma política; `CSP_DEFAULT_SRC` não se distingue de uma configuração válida.

**Estado:** corrigido. `base.py:307-310` documenta a migração, e `tests/test_csp.py` (565 linhas) tem `test_o_cabalho_csp_esta_publicado` como guarda.

**CONFIRMADO por mim, por execução** — resposta real de `GET /login/`:
```
Content-Security-Policy: connect-src 'self' api.open-meteo.com servicodados.ibge.gov.br
  nominatim.openstreetmap.org *.ingest.sentry.io huggingface.co ...
```

### 2.6 Uma armadilha que **dois** agentes caíram — e que vale registar

O agente 4 escreveu que o `1.md` tinha sido sobrescrito porque `Measure-Object -Line` dava 221 linhas quando o `read` tinha dado 287. **Estava errado** — a medição certa é `[System.IO.File]::ReadAllLines`, que dá 313. `Measure-Object -Line` **subconta**.

**Eu caí no mesmotipo de erro**, pelo outro lado: `$array.Length` em PowerShell devolve **linhas**, não caracteres — quase reportei `/pitch/` como partido quando tinha 136 KB.

> **Nenhum dos dois via o código.** Viu-se um número eIEL o leu como Verdade. Em PowerShell: `Measure-Object -Line` subconta, `$array.Length` conta linhas, `Out-String` quebra em linhas. **Confirma com o ficheiro, não com a medida.**

### 2.7 Os 7 (agora 9) auditaram o manifesto Agro 5.0

Cobertura total sem sobreposição. §6 desta mesclagem é a soma.

---

## 3. ACHADOS ÚNICOS — ordenados por gravidade real

### 3.0 P0 — A IA inventa dados que **parecem certos** (agente 10, CONFIRMADO por mim) ⚠️

**Este é o achado mais grave dos 9 documentos.** Chegou **depois** desta mesclagem estar escrita — por isso está aqui, e não estava no plano original.

`app/static/js/ia-local/ia-local.js:2610` (`func:admissao`):
```js
const d = wizParseDatas(t);
f.admissao = d.length ? d[0] : wizHoje();     // ← hoje, se não souber ler a data
```

| Pergunta | Resultado |
|---|---|
| `"quando ele entrou?"` | `f.admissao = "2026-10-04"` — **hoje**, sem dizer nada |

Isto viola **duas** doutrinas do próprio projecto ao mesmo tempo:

1. **A separação raciocínio/ação do manifesto.** *"Uma IA não altera o estado da fazenda; ela compila uma transação segura que o sistema valida e o produtor aprova."* Aqui a IA **inventa o dado e grava**. Não há transação para aprovar — há um valor fabricado num campo.
2. **A regra de `validators.py:40-41`:** *"o sistema nunca promove uma afirmação a medição."* `wizHoje()` **fabrica uma medição**.

E é o mais perigoso porque **não parece erro**:

> *"A frase de erro do talhão era absurda e visível — ninguém a levava a sério. Uma data de admissão plausível entra no cadastro e ninguém a questiona durante meses. **Um erro visível é um erro que se corrige; um erro plausível é um erro que se propaga.**"* — agente 10

**Cinco wizards com o mesmo defeito, VIVOS** (medido com sonda do agente 10):

| Passo | `ia-local.js` | O que acontece |
|---|---|---|
| `talhao:nome` | `:2257` | guarda a pergunta como nome e faz `POST` |
| `animal:piq_nome` | `:1620` | idem |
| `func:nome` | `:2576` | guarda *"como vocês chamam ele?"* como nome da pessoa |
| `tarefa:oque` | `:2792` | guarda a pergunta como descrição |
| `safra:ciclo_nome` | `:4450` | idem |

Saída real da sonda do agente 10:
```
pergunta: "como voces chamam esse talhao?"
  >> f.nome = "como voces chamam esse talhao?"
  >> o POST vai com nome = "como voces chamam esse talhao?"
```

**E no servidor** (§4.1 do agente 10): `concluir_tarefa` faz **uma escrita por substring, sem `needs_confirm`** — ou seja, o gate que `sandbox.py` implementa é contornado por um caminho que não passa por ele.

**Nota para o merge final:** isto contradiz a §III do manifesto Agro 5.0 no seu ponto mais forte. A separação "raciocínio probabilístico / acção determinística" **existe** (`sandbox.py` está bem feito) mas **não é o único caminho** — a IA escreve por outras vias, e aí não há `needs_confirm` nemproveniência.

### 3.1 P0 — Perda de dados financeira **em silêncio** (agente 6, CONFIRMADO por mim)

**Este é o achado mais grave dos 7 documentos, e nenhum dos outros o tem.**

```
index.html:2595   DataStore.save('financeiro', linha)      → _pending = true
index.html:2599   showToast('registo(s) salvos com sucesso!')   ← VERDE, diz sucesso
data-sync.js      POST /api/financeiro/                     → 405 Method Not Allowed
data-sync.js      .catch → console.warn                     ← invisível para quem usa
                  o item fica _pending PARA SEMPRE, a cada sync
```

**Verificado por mim:** `app/api/views/financial.py:222` é mesmo `@api_view(["GET"])` —Confirmed. O CRUD real é `/api/lancamentos/`.

**O que o produtor vivia:** registava um lançamento, via um toast **verde de sucesso**, e o lançamento **nunca chegava ao servidor**. Sem erro, sem aviso. Para sempre. Num produto cujo produtor está por definição sem rede.

> **Isto corrige o meu §3.** Eu disse que o offline não executa. Verdade para `pwa/indexeddb.js`/`pwa/sync.js` — mas **o caminho de escrita offline VIVO é `data-sync.js` com `localStorage`**, e esse escrevia. Eu medi a camada morta e não vi a viva.

**Estado:** o agente 6 **já corrigiu**, e deixou o raciocínio no código (`index.html:2596-2603`, `data-sync.js:14-22`), nomeando o endpoint real (`/api/lancamentos/`) e o equivalente (`/api/apiario/` → `/api/colmeias/`).

**Padrão, não caso isolado** — 3 instâncias:
| Onde | Endpoint | Estado |
|---|---|---|
| `pwa/sync.js:105,144,252` | `/api/caderno/notas/`, `/fotos/`, `/voice/` | não existem |
| `data-sync.js` | `/api/financeiro/` | `@api_view(["GET"])` |
| `data-sync.js` | `/api/apiario/` | `@api_view(["GET"])` |

**E o detalhe mais instructivo** (`data-sync.js`): `sw.js:294-298` tem um comentário de 15 linhas a descrever exactamente este bug. Alguém diagnosticou com precisão e corrigiu **metade** — tirou o flush do SW mas deixou o `sync.js` a apontar para os mesmos endpoints mortos.

### 3.2 P0 — O barramento IoT foi **apagado** (agente 9, CONFIRMADO por mim)

```
git status --short -- app/iot/management/
 D app/iot/management/__init__.py
 D app/iot/management/commands/__init__.py
 D app/iot/management/commands/mqtt_listener.py
 D app/iot/management/commands/sync_inmet.py
```

**Não existem em disco.** Estavam em `81fd25c`. `mosquitto/config/mosquitto.conf` ainda existe — o broker ficou, o consumidor foi-se.

**Um dos 7 runtimes que o manifesto declara não existe na árvore.** Isto explica as referências que não resolvem em 5 documentos: não é alucinação, é **deleção**.

### 3.3 P0 — Revogação de servidor não propagava (agente 1)

- 23 URLs / 20 endpoints devolvem 200 a um servidor com `ativo_servidor=False`, com dados da fazenda **vinculada**
- **Controlo:** servidor **activo** também 200/23 → **não distinguem revogado de activo**
- 7 rotas POST escreviam antes da correcção
- `grep ativo_servidor` em `app/api/` → **ZERO**. Padrão, não caso isolado

**Resolvido** por `ServidorRevogadoMiddleware` (`app/middleware.py:41`, `base.py:136`), fail-closed (`:114-122`).

> **Divergência instructive:** eu propus `permission class` em `DEFAULT_PERMISSION_CLASSES`. **Não funcionaria** — cada view declara as suas, o que sobrepõe a default. O middleware está **antes do DRF**. O agente 9 (`:103-104`) chegou à mesma conclusão por via mais dura.

### 3.4 P1 — Perigo operacional: pytest tocava a base real (agente 1)

`pytest.ini:2` → `config.settings.dev`. `test.py:18` cria SQLite `:memory:` — **e ninguém o usava**. Corrigido.

### 3.5 P1 — Vocabulários de proveniência divergem

Ver §2.1. O painel (`proveniencia.py`) **omite `declarado`**.

### 3.6 P1 — "Perda" residual do offline: `?v=` mortos (agente 6, §2)

Quatro parâmetros `?v=` em estáticos apuntan para versões que não existem — o offline nunca arranca para esses assets. **Não verificado por mim.** É a mesma classe de dor que o `sw.js:9-27` documenta em 19 linhas sobre `CACHE_VERSION` manual.

### 3.7 P1 — O modelo de 1,1 GB descarregava sem consentimento (agente 6, §3)

O `SmolLM2-1.7B q4f16` (~1,1 GB, `ingestao/audio.py:17`) descarregava no WebGPU sem o produtor ter pedido. **Não verificado por mim**, mas coerente com `audio.py:153` ("sequencial: Whisper toma o WebGPU") — se serializou o acesso ao dispositivo, é porque havia disputa.

### 3.8 P2 — Dados fake do produtor na base (agente 2, §3)

**Não verificado por mim.** Se confirmado, é o pior tipo de bug para dados de carbono: um valor inventado marcado como medido.

### 3.9 P2 — A catraca de volume é cega a eliminações (agente 7, §5)

Os testes de invariantes **só cresce? / só pastas novas?** (`tests/test_estudo_volume.py`). Um volume que só cresce **não pode ser violado por uma eliminação** — que é o modo de falha mais perigoso. **Não verificado por mim**, e a formulação é precisa demais para ser invenção.

### 3.10 P3 — Bugs de 500 e de importação

| Bug | Ficheiro | Estado |
|---|---|---|
| `/api/agenda-analises/` → 500 | `api/views/kanban.py:74` — `from .serializers` um nível abaixo | por corrigir |
| `/api/notificacao-templates/<pk>/testar/` → 500 | `app/services/notificacoes.py` nunca existiu | corrigido |

### 3.11 P3 — OTA: o manifesto descreve o que não existe

Agentes 1, 2 e 5 convergem. Existe `models/iot.py:135 firmware_version` e um `<option>OTA Atualizar</option>` num template. **Não há upload de firmware.** O que existe é code-gen para colar no Arduino IDE (`ia/iot.py:357`) — ainda exige cabo e IDE.

O agente 2 classifica isto como *"a divergência que mais dano causa, porque é a única que descreve algo que não existe em vez de algo que existe mas está por fazer"*. **Concordo, e é a formulação correcta.**

### 3.12 P3 — "Até 2 GB de RAM" contradito pelo próprio projecto

`ingestao/audio.py:17` SmolLM2 ≈ **1,1 GB** · `:167` Phi-3.5-vision ≈ **2,6 GB** (única VLM) · `:23` 143 modelos, **um** par de visão. Visão computacional não cabe no orçamento declarado.

### 3.13 O princípio estrutural que vale mais que qualquer achado isolado (agente 2, §2.1)

> **"Uma regra que tem de valer em N sítios não pode ser lembrada em N sítios. Tem de ser um sítio, e o resto descobre."**

| Regra | Onde vive | Como os outros descobrem |
|---|---|---|
| Tenancy (IA) | `ia/proriedade.py` | `resolver()` — 3 ficheiros antes replicavam `_prop` |
| Tenancy (API) | `api/views/faltantes.py` | `make_scoped_viewset()` — não 15 classes |
| Cache | `cache_painel.py` | sinais `post_save` — não 7 viewsets |
| Registo de IA | `ia/registro.py` | `pkgutil.iter_modules` — não lista escrita à mão |

Isto generaliza o episódio do middleware: **a revogação devia viver em `ia/provedor.py`-equivalente para API, não em cada view.** É a razão pela qual 20 endpoints lacravam ao mesmo tempo.

---

## 4. PLANO UNIFICADO

Ordenado por **produtor exposto**, não por esforço. `[ ]` = por fazer · `[x]` = feito nesta sessão

### P0 — IMEDIATO: dados e runtime

| # | Acção | De onde | Verificação |
|---|---|---|---|
| 0 | **`ia-local.js:2610` — deixar de inventar datas.** `wizHoje()` como fallback grava uma medição fabricada.Ou o passo **pergunta a data**, ou grava `None` com `fonte_dado:"sem_dado"` — que é o que o projecto já tem | **10** | `func:admissao` com *"quando ele entrou?"* → `f.admissao is None`, nunca hoje |
| 0b | **As 5 portas dos wizards** (`:2257`, `:1620`, `:2576`, `:2792`, `:4450`) — guarda `wizEhPergunta(t)` **antes** do `POST` | **10** | a mesma sonda, nos 5 passos → nenhum POST |
| 0c | **`concluir_tarefa`** — escrita por substring sem `needs_confirm`. Ou passa pelo `sandbox.executar`, ou exige confirmação | **10** | teste: frase ambígua → `IAExecucao` com `needs_confirm=True`, zero escrita directa |
| 1 | **Restaurar `app/iot/management/`** (`mqtt_listener.py`, `sync_inmet.py`) | 9 | `git checkout HEAD -- app/iot/management/`; broker volta a ter consumidor |
| 2 | **Auditar os 3 endpoints `@api_view(["GET"])` que a fila de escrita usa** — procurar `@api_view` sem `POST` que o `data-sync.js` aponte | 6 | teste que faz `POST` a cada endpoint do `MAPA` de `data-sync.js` e falha se der 405 |
| 3 | Confirmar que a fila offline **nunca mais aceita item sem destino de escrita** | 6 | para cada tipo do `MAPA`, `POST` tem de dar 2xx ou recusa **antes** de marcar `_pending` |
| 4 | **Recuperação de dados**: produtores com lançamentos perdidos | 6 | **impossível** — o `_pending` vivia em `localStorage` do telefone. **Dizer ao cliente.** |
| 5 | Medir escrita revogada (40 rotas POST) e detalhe por modelo (188 URLs, só 2 dão 200) | 1 | relatório com controlos |

### P1 — coerência e promessa

| # | Acção | De onde |
|---|---|---|
| 6 | **Acrescentar `declarado` a `ia/proveniencia.py:68`** — alinhar com `validators.py` | 1+9 |
| 7 | `validators.py:9` — "seis" → "cinco" | 1 |
| 8 | **Revogação dentro da view** (defence in depth) — hoje só existe no middleware, que não cobre Celery nem commands | 1+9 |
| 8b | **Auditar toda a configuração contra a versão da biblioteca que a consome.** A CSP falhou por `CSP_DEFAULT_SRC` (3.x) num `django-csp` 4.0. O mesmo vale para DRF, allauth, django-axes. Teste que **verifique o efeito**, não a presença da configuração | **4** |
| 8c | 2 renderizadores para o mesmo alvo, nenhum dono (`#presets-carousel`); `npm run lint` inutilizável; CI JS vermelho de forma determinística | 4 |
| 9 | `git commit` do que está staged | 1 |
| 10 | Corrigir manifesto: **apontar para `app/validators.py`**, não `proveniencia.py`; "validada por tabela" não "criptograficamente"; **§VII como roadmap** | 1,2,5,9 |
| 11 | Investigar `?v=` mortos e o download de 1,1 GB sem consentimento | 6 |
| 12 | `sourcemap: false` não corrigiu a fuga e degrada o Sentry — decidir explicitamente | 4 |

### P2 — tornar o offline real

**Backend primeiro. Tela sem backend é nota perdida.**

| # | Acção |
|---|---|
| 12 | Modelo `Nota`/`Foto` + migration |
| 13 | Serializer + ViewSet + `/api/caderno/notas/` e `/fotos/` |
| 14 | Unificar: `data-sync.js` (vivo, `localStorage`) e `pwa/indexeddb.js` (morto, IndexedDB) — **dois caminhos de escrita é onde o 3.1 aconteceu** |
| 15 | Decidir Background Sync: `registration.sync.register` real, ou aceitar que **exige app aberto** e documentar |
| 16 | Atalho `nota` no manifest só depois de a rota existir |

### P3 — higiene

| # | Acção |
|---|---|
| 17 | `api/views/kanban.py:74` — corrigir o import |
| 18 | Verificar dados fake na base (2.md §3) |
| 19 | Catraca de volume cega a eliminações (7.md §5) |
| 20 | Roteiro de campo em Android — `docs/TESTE_CAMPO_PWA_ANDROID.md` (478 l.) |
| 21 | Se algum dia app **nativo**: `base.py:219-220` é `SessionAuthentication` só; `simplejwt` está no requirements mas não em `INSTALLED_APPS` nem em nenhum `authentication_classes` — **0 hits** |
| 22 | Hotspots: `spa.js:switchTab` cyclo 85/cognitive **364**; `guide.js:gcRenderModule` cognitive **222**; `cultures.py:ibge_proxy_data` cognitive **164**; `ia/sandbox.py:executar` cyclo 35, 489 l., **fan-in 83** |

---

## 5. O QUE NENHUM DOS 7 VERIFICOU

Declaração conjunta. Vale mais que a lista de achados:

- **Nada correu num Android.** O `beforeinstallprompt` não dispara em headless. Os 7 mediram a canalização HTTP; **ninguém mediu a instalação.**
- **Comitê de 46 lentes: CAIDO a sessão inteira** (`404 rota desconhecida` + 2× timeout 270s).
- **`astgrep`: `files_scanned: 0`** e depois MCP timeout. Não escaneou nada — não é "limpo", é não-verificado.
- **`gitleaks`, `codeql`, `trivy`, `grype`, `osv-scanner`, `zap`, `bearer`: MISSING** (sem Docker). **Segredos no historial git e CVEs de dependência nunca verificados por nenhum dos 7.**
- **Havia um processo concorrente a editar a árvore** em todas as sessões: `db.sqlite3` mtime mudou, 13+ ficheiros staged, ficheiros criados a meio. **Qualquer medição é uma fotografia de um instante.**
- **Migração IndexedDB v1→v2 sobre dados reais de produtor** — não testada.
- **A race de `VersionError`** entre as duas ligações IndexedDB — intacta de propósito.
- **`4.md` e `8.md` não existem.** A amostra é 7 de 9.

---

## 6. SÍNTESE PARA O MERGE FINAL

**O que os 7 documentos provam, em uma frase:** o Ampliagro tem uma doutrina de integridade de dados genuinamente rara — e um Mecanismo de Promessa que adocumentation descreve melhor do que o código a aplica.

**Os trêsPid.Utc the**
1. **Perda de dados financeira em silêncio** (6) — o produtor via "salvos com sucesso" e nada chegava ao servidor. Corrigido, com o raciocínio no código.
2. **Um runtime declarado foi apagado** (9) — `mqtt_listener.py` e `sync_inmet.py` não existem na árvore.
3. **20 endpoints serviam a fazenda a servidores desligados** (1) — sem middleware, `IsAuthenticated` não distingue revogado de activo.

**O erro mais instructive da mesclagem:** eu e o agente 9 publicámos "a proveniência tem 3 estados, `declarado` não existe" como CONFIRMADO. O agente 2 tinha razão. **Convergência entre agentes amplificou o meu erro em vez de o travar** — porque os três tínhamos olhado o mesmo ficheiro e não o outro. A única coisa que travou foi ler `validators.py`.

**Regra para o merge final:** aceitar de uma análise o que tem `ficheiro:linha` **e** sobrevive a verificação. Rejeitar o que é convergência sem segunda via — como este caso.