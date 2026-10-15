# Compreensão do Sistema Ampliagro

> **VERSÃO 2 — reescrita.** A v1 caracterizou o sistema como monolítico e a IA
> como não-probabilística. **As duas estavam erradas.** O que me levou a errar foi um
> erro de método meu, não do código: li docstrings do lado *servidor* e
> generalizei para o sistema todo, e nunca procurei outras cópias do repositório
> no disco. O código está correcto e coerente; a minha leitura é que estava
> incompleta.
>
> Documento escrito a partir de **leitura do código**. Não li a documentação
> `.md` do projecto excepto `console.md` (autorizado), que é código de
> governação, não documentação.
>
> Código: `C:\Trabalho\Projetos\Ativos\Ampliagro`
> Branch: `chore/snapshot-sistema-atual-20261004` (69 ficheiros por commitar)
> Remote: `github.com/luck-of-luck/Ampliagro`
> Graph: 6 943 nós / 27 213 arestas

---

## 1. Os dois erros da v1, e como os cometi

### Erro 1 — não procurei o repositório

Encontrei **um** caminho de código (via o SQLite `.coverage`) e assumi que era
o canónico. Há **8+ cópias do Ampliagro** nesta máquina. Encontrei a certa,
mas não *saber* que tinha encontradolevou-me a tratar uma cópia como *o*
sistema.

| Caminho | O que é |
|---|---|
| `C:\Trabalho\Projetos\Ativos\Ampliagro` | **o sistema**, 499 `.py`, snapshot 2026-10-04 |
| `C:\Trabalho\Projetos\Ativos\Ampliagro-bekup_JULHO` | backup |
| `C:\Trabalho\Projetos\Ativos\Ampliagro-meioSPA` | backup (fase "meio SPA") |
| `C:\Trabalho\Projetos\Ativos\Ampliagro.worktrees\*` (4) | worktrees de agentes |
| `C:\Trabalho\Projetos_Ativos\Ampliagro` | só `.md` de coordenação — **parece** o sistema, não é |
| `C:\Users\lucas\Documents\Projetos_geral\Ampliagro` | **aqui foi aberta a sessão**: só `.ruff_cache`, `htmlcov`, `.coverage`, `db.sqlite3` |
| `C:\Users\lucas\Documents\Projetos_geral\Ampliagro.worktrees\{contratos-teste,tenant-seguranca}` | worktrees do repo |
| `C:\Pessoal\Downloads_Organizados\Projetos\Ampliagro-main` | download do GitHub (52 `.py`, esmagado) |
| `C:\Users\lucas\OneDrive\Documentos\GitHub\Ampliagro` | 51 `.py`, esmagado |
| `C:\Users\lucas\AppData\Local\hermes\Ampliagro` | 199 `.py`, cópia do Hermes |

⚠️ **O risco disto é concreto, não teórico:** o directório onde esta sessão foi
aberta está praticamente vazio. Quem abrir o projecto pelo path errado conclui
que o código se perdeu.

### Erro 2 — li o servidor e generalizei

`app/ia/llm_gateway/__init__.py:19` diz, literal:

> *"Não existe nenhuma chamada de LLM no projeto."*

Isto é verdade **do processo Django**. Eu escrevi-o como afirmação sobre **o
sistema**. O LLM corre **no navegador** — e é o ficheiro maior do projecto
inteiro. Numa frase: *"Não há LLM no servidor"* não é *"não há LLM"*.

---

## 2. O sistema NÃO é monolítico

### 2.1 Topologia: 7 runtimes, 3 linguagens

| # | Runtime | Linguagem | Entra por | Papel |
|---|---|---|---|---|
| 1 | **Django web** (daphne/ASGI) | Python | `docker compose` | HTTP + WebSocket |
| 2 | **MCP stdio** (`amplia-mcp`) | Python | Claude Desktop, Hermes, opencode | 3 superfícies MCP para agentes LLM externos |
| 3 | **Celery worker + beat** | Python | `celery -A Ampliagro worker` | motor proativo |
| 4 | **MQTT listener** | Python | `manage.py mqtt_listener` | ingestão IoT contínua |
| 5 | **Navegador / WebLLM** | JavaScript | `@mlc-ai/web-llm@0.2.79` | **o cérebro** — 6 320 linhas |
| 6 | **Node `.cjs`** | JavaScript | `npm test` | harnesses de teste do palco/chamado |
| 7 | **ia-coord** | Python + Markdown | `ia-coord/guard/verificar.py` | coordenação multi-agente |

Complementado por: PostgreSQL 16, Redis 7, Mosquitto (MQTT), Caddy (TLS),
Open-Meteo / IBGE / INMET / NASA POWER / Sentinel (dados externos).

### 2.2 O MCP é mesmo um processo separado

`app/amplia_mcp/servidor.py` (587 linhas) arranca **sozinho**:

```python
RAIZ_REPO = pathlib.Path(__file__).resolve().parents[2]   # deduz a raiz do __file__
os.chdir(RAIZ_REPO)          # sem isto, o SQLite relativo morre
os.environ["DJANGO_SETTINGS_MODULE"] = escolhida
django.setup()                # bootstrappa o Django fora do manage.py

server = Server("amplia", instructions=GUIA)
anyio.run(main)               # stdio_server()

p.add_argument("--usuario", required=True)        # o stdio não tem sessão web
p.add_argument("--permitir-escrita", ...)         # opt-in, default leitura
p.add_argument("--settings", default="")          # prod se AMPLIA_PROD=1
```

E o docstring diz quem o arranca: *"Claude Desktop e Hermes arrancam o processo
com o directório de trabalho do utilizador"*. Por isso três defeitos
documentados e medidos: não arrancava fora do repo (`sys.path`), não tinha
canal de `entrada` para a máquina de estados conversacional, e arrancava
sempre em `dev`.

### 2.3 E o desenho é deliberadamente "modular", não acidental

`amplia_mcp/views.py:12` dá a fórmula:

> **"Um caminho só de execução, duas portas."**

A blocklist de compliance, o embrulho de proveniência e o gate de confiança
são verificações **in-process** — e são incontornáveis porque há **um
processo de escrita**. Os "cérebros" é que são múltiplos e probabilísticos.

⚠️ **Custo real do monolito de Django** (a parte que é genuinamente um
problema): `app/templates/index.html` tem **848 KB** com ~13 000 linhas de JS
inline. Isso força `'unsafe-inline'` na CSP — medido no próprio código: 606
handlers `on*=` e 1 268 atributos `style=`. **Não há protecção CSP contra XSS
em script.** É a dívida do monolito de frontend a ser cobrada.

---

## 3. A IA É probabilística — e é essa a arquitectura

### 3.1 Dois cérebros, e a separação é o ponto todo

`app/amplia_mcp/__init__.py:6-26` declara:

> *"Até agora a AmplIA tinha **dois cérebros separados** e nenhuma mão segura:*
> 1. *`app/ia/intents*.py` — 65 intents determinísticos, com sandbox e
>    auditoria. **Rigorosos. Mas não raciocinam: casam regex.***
> 2. *`app/static/js/ia-local/ia-local.js` — WebLLM rodando **no navegador**
>    (SmolLM2-1.7B, com Qwen2-0.5B de reserva). **Raciocina de verdade.**"*

E o problema que existia antes de o MCP existir:

> *"as 'mãos' eram `iaToolCall`, uma function em JavaScript que fazia isso:
> `if (tool === 'irrigacao') await apiFetch('/api/iot/comandos/', {method:'POST'})`.
> Ou seja: **uma IA capaz de acionar uma válvula de irrigação fazia isso por
> HTTP directo, sem passar por `sandbox.executar()`**. Sem `needs_confirm`,
> sem linha em `IAExecucao`, sem verificação de flag de capacidade."*

> **"A separação entre 'quem pensa' e 'quem age' é o que permite uma IA
> poderosa sem uma porta dos fundos."**

Isto é **governança de acção**, não remoção do raciocínio. Eu escrevi na v1
"o LLM está em quarentena na borda" — **errado**. O LLM raciocina; o que está
governado é o que ele *faz*.

### 3.2 O motor no navegador, com degradação em 3 níveis

```js
// ia-local.js:4525
async function iaInit(onProgress) {
  const webllm = await import('https://esm.run/@mlc-ai/web-llm@0.2.79');
  const engine = new webllm.MLCEngine();
  await engine.reload(iaModel);                    // SmolLM2-1.7B
} catch {
  iaModel = 'Qwen2-0.5B-Instruct-q4f16_1-MLC';    // :4544
} catch {
  iaReady = 'server';                              // :4552  sem WebGPU
}
```

É um componente de runtime com fallback, com `setInitProgressCallback` a
reportar progresso ao utilizador. `obterIaEngine()` devolve `null` quando
`iaReady === 'server'`. **Isto não é uma ideia; é código com alarme.**

### 3.3 O modelo tem limites que moldaram a arquitectura

- **Janela de 4 096 tokens.** O catálogo completo são ~8 700 tokens medidos.
  Daí `vocabulario/` existir: *"não cabe na janela do SmolLM2 de 1.7 B que
  roda na aba. Este é o texto derivado que cabe."*
- **`max_tokens: 200`, `temperature: 0.2`.**
- **O modelo erra nomes.** Daí `sugerir_tools()` com `difflib` — e a nota
  mais dura do projecto: *"o system prompt do `ia-local.js`, com **13 nomes
  dos quais 0 existem** — que custou um turno inteiro de tool calls inúteis."*

E o bug mais instructive que li (`:6122-6136`): `extrairToolCall` lia
`obj.tool` sobre o **texto** em vez do **objecto parseado**, e a docstring de
`lerObjetoJson` dizia "devolvendo o texto". **Duas coisas erradas que se
cancelavam**: a extracção devolvia `null` sempre. O comentário explica o
que é isto:

> *"Não era um bug de nomes (FILA #27) — era um bug uma camada mais abaixo, e
> era invisível enquanto a lista do prompt fosse de nomes errados: os dois
> defeitos davam o mesmo sintoma e escondiam um atrás do outro."*

E o mesmo desvio estava em `proativo-local.js`: *"Duas cópias da mesma
função, uma certa e outra não — e a que não estava certa é a do chat."*

### 3.4 O motor proativo: dois caminhos convergentes

`app/ia/proativo.py` — a decisão mais importante do projecto, textual:

> *"**Para o risco mais provável, o alerta não precisa do LLM.** 'Chuva forte
> na sexta + aplicação de fertilizante na quinta = produto lavado' é uma
> regra. Um regex e uma comparação de data resolvem isso, e resolvem
> **melhor** que um modelo de 1,7B."*

```
caminho A (regra)  servidor, determinístico, SEM LLM  ← cobre o risco comum
caminho B (LLM)    navegador, semântico, sobre o mesmo contexto estrito
```

E `proativo_tasks.py` é ainda mais explícito:

> *"O worker **NÃO FAZ: chamar o LLM.** [...] o worker deixa o cenário
> **persistido na fila** (`IACenarioPendente`), e o navegador o recolhe quando
> estiver ocioso. O resultado vem por `amplia_emitir_alerta_proativo`, que é a
> MESMA porta governada."*

> *"Se o alerta dependesse do LLM, ele só chegaria quando a aba do produtor
> estivesse aberta — ou seja, **os alertas mais urgentes seriam exactamente os
> que não chegariam**."*

⚠️ **Deriva documento/código:** `proativo_tasks.py:26-28` afirma *"'config/celery.py' está, hoje, um comentário: 'Celery is temporarily disabled'"*. **Não é verdade no código actual** — `config/celery.py` tem `app = Celery("ampliagro")` activo e `app.conf.beat_schedule = BEAT_SCHEDULE`. Ou o docstring envelheceu, ou o Celery foi reabilitado depois. O núcleo como função pura (`varrer()`) é a decisão correcta e continua válida.

### 3.5 O que o LLM tem de distinguir é a fronteira do contexto

O contexto do proativo é montado por código, com o texto do produtor dentro de
um **rótulo fixo**, e o motivo está escrito (`proativo.py:170-173`):

> *"O texto do produtor entra NUM RÓTULO FIXO. Não é vaidade: é a fronteira
> entre 'dado do sistema' e 'texto que alguém escreveu', e o LLM precisa saber
> qual é qual para não seguir instrução encontrada no meio."*

---

## 4. O que garante que a IA não inventa

### 4.1 Proveniência — a regra que é um tipo, não uma convenção

`app/ia/proveniencia.py`. Três dataclasses `frozen`, e `__post_init__` **levanta**:

```python
Medido(valor, fonte)      # sem fonte  -> ValueError
SemDado(motivo)           # sem motivo -> ValueError
Simulado(valor, gerador)  # sem gerador-> ValueError
```

> *"Não é uma convenção que se cumpre. É uma consequência da construção: o
> serializador recebe sempre valores embrulhados, e o que ele escreve é a forma
> que essa embrulha obriga."*

E o diagnóstico que justifica o módulo existir:

> *"Esta sessão encontrou números inventados em **seis camadas, seis mecanismos
> diferentes, seis ficheiros que não se conhecem** [...] e a prova de que é
> estrutural é que **eu introduzi a sétima enquanto a curava**."*

Três estados e nenhum outro. O quarto estado tentador — "estimado" — foi
recusado: *"um número estimado que não diz que é estimado é um número medido
que mente."*

### 4.2 Compliance — regra é regra, não Redmição

`app/ia/compliance.py:6-11`:

> *"Uma lista de termos é uma REGRA, e regra implementada com modelo de
> linguagem é regra que pode falhar no dia em que mais importa. Se o sistema
> precisa dizer 'não, isso aqui não entra', essa resposta não pode depender de
> como o modelo 'sentiu' a frase."*

E a lista é cirúrgica: **"queimada" não entra** (queimada de pasto é manejo
legalizado); **"desmatamento" entra mas "desmatada" não** (porque "área
desmatada" é o nome da ferramenta de *compliance* que o produtor precisa).

### 4.3 Confiança — o score é do servidor

`sandbox.py:297-322`: se o cliente não mandou scores, o servidor **calcula-os**.
A versão anterior confiava no cliente, e o gate M3 era decorativo: *"um
cliente que mandasse `meta: {}` passava a pedir à granularidade que quisesse."*

### 4.4 Os testes de honestidade são o activo mais valioso do projecto

Nomes que dizem a invariante defendida: `test_clima_sem_invencao.py`,
`test_ndvi_sem_medicao_inventada.py`, `test_sem_dado_inventado.py`,
`test_fallback_sem_invencao.py`, `test_pulverizacao_sem_invencao.py`,
`test_evidencia_carimbada.py`, `test_cotacoes_preco_honesto.py`,
`test_doses_sem_invencao.py`, `test_tenancy_isolamento.py`, `test_csp.py`.

**1 689 funções de teste em 123 ficheiros.**

⚠️ E, de `proativo.py:238-251`, um aviso que vale mais do que many bugs:

> *"Os 532 testes passavam porque todos mockavam `obter_previsao` inteira: a
> função nunca rodou com uma propriedade de verdade, e nenhum teste exercitou
> o contrato das chaves. **Um teste que cobre a função errada é pior do que
> nenhum, porque parece cobertura.**"*

---

## 5. O desenvolvimento é multi-agente — e auditado

Isto não está no código de produto; está em `console.md` (2 220 linhas) e
`ia-coord/`. É parte do sistema.

### 5.1 O protocolo

`ia-coord/guard/verificar.py` (602 linhas) corre 5 verificações:

| V | O que verifica |
|---|---|
| V1 | corrupção CJK/mojibake por **varrimento de bytes** |
| V2 | manifesto do plenário — alguém reescreveu um registo antigo? (SHA-256) |
| V3 | numeração dos slots |
| V4 | cada slot tem o que a LEIA-ME promete |
| V5 | ficheiros a meio escrever (UTF-8 inválido) |

Regra R5, o coração disto:

> *"Um comando que não corre tem de **DIZER QUE NÃO CORREU**. Este script não
> tem caminho de reserva que imprima 'OK'."*

E tem uma distinção que vale mais que o resto:

> *"**NAO VARRI NADA — isto é 'não verifiquei', não 'limpo'**"* (linha 232)

Slots: `ia-1` … `ia-11`, com 3 **git worktrees** para agentes em paralelo
(`contratos-teste`, `tenant-seguranca`, `cultura-dados-design-abas-navegador`).

### 5.2 O achado que só aparece quando se lê tudo junto

`console.md:1345-1347`:

> *"As quatro sessões, Working em paralelo, sem se falarem, bateram nos MESMOS
> TRÊS BUGS DE FERRAMENTA. Nenhum o descobriu porque o outro o descobriu."*

| # | Bug | Sessões |
|---|---|---|
| 1.1 | Corrupção CJK em comentários | **4 de 4** — *"Isto é uma ferramenta que corrompe texto em silêncio e precisa de uma catraca, não de mais cuidado"* |
| 1.2 | Índice git partilhado | **4 de 4** — *"Nenhum agente pode confiar em `git add -A` neste repositorio"* |
| 1.3 | A ferramenta `edit` em ficheiros grandes | 2 — uma reescreveu 2,1 MB e inseriu **uma linha em branco depois de cada uma** (26.606 → 47.633 linhas) |
| 1.4 | **Ninguém correu um scanner determinístico** | **4 de 4** |

O ponto 1.4, textual:

> *"IA-6: 'scanners que rodaram: NENHUM' [...] 'IDOR, CSRF, XSS, injecao:
> NAO OLHADOS. Não estou dizendo que estão bem — estou dizendo que não olhei.'
> IA-2: 'Não houve revisão por comité de 46 lentes: cluster_consultar não
> estava utilizável'. IA-6: 'O COMITÉ DE 46 LENTES ESTAVA OFFLINE (404)'."*

> *"**QUATRO SESSÕES, ZERO scanners, ZERO comité.** Quatro revisões por leitura
> e raciocínio. Nenhum dado determinista."*

**É exactamente o buraco que eu reencontrei.** O meu `cluster_consultar` desta
sessão devolveu 8 de 10 lentes a recusar por falta de acesso a ficheiros.

---

## 6. Verificação dos achados do ledger (por mim, não por confiança)

`console.md` documenta 8 achados. **Verifiquei cada um no código actual.**

| # | Achado | Estado **verificado** |
|---|---|---|
| **GRAVE 1** | `ativo_servidor` não se propaga a 4 rotas `/servidor/` | ✅ **CORRIGIDO** |
| **GRAVE 2** | `operario.py` grava 6 tarefas + `RegistroProducao "Demo"` ao renderizar | ✅ **CORRIGIDO** (com gate) |
| **MÉDIO 3** | `except Exception: is_servidor = True` — falha **aberta** | ✅ **CORRIGIDO** (falha fechada) |
| **BAIXO 4** | `cadastro-funcionario.html` renderiza `[]` | ✅ **CORRIGIDO** |
| **BAIXO 5** | Árvore de backup recursiva, 250+ níveis | ❌ **AINDA VIVO** |
| **BLOQ 6** | `catalog.json` bloqueia todos os commits | ✅ **RESOLVIDO** (ficheiro apagado, fora do índice) |
| **SIST 7** | Catraca de corrupção CJK | ✅ `ia-coord/guard/verificar.py` V1 |
| **SIST 8** | Catraca de acesso a rotas | ❌ não encontrado |

### GRAVE 1 — propagação da revogação (verificado, corrigido)

O helper é agora a fonte única (`servidor.py:24-53`):

```python
def _perfil_e_propriedade(request, tipos_bloqueados=("produtor",)):
    ...
    if not perfil.ativo_servidor:
        return None, None
```

Confirmei as 5 rotas:

| Rota | Linha | Verificação |
|---|---|---|
| `servidor_dashboard_view` | 73 | check próprio em **87** + `logout(request)` |
| `servidor_estoque_view` | 222 | helper em **224** |
| `servidor_agenda_view` | 265 | helper em **267** |
| `servidor_alertas_view` | 301 | helper em **303** |
| `operario_kanban_view` | 25 | decorator `kanban_required` → `utils.py:89` |

⚠️ **Uma excepção deliberada, e está documentada** (`app/api/views/api.py:18`):

> *"NOTA DE REVOGAÇÃO — `get_talhoes_api` **NÃO** verifica `ativo_servidor`, de
> propósito."*

⚠️ `lgpd.py:345` é onde o produtor desactiva; `auth.py:128` é o portão de login;
`operario.py:310` escreve `"ativo_servidor": True` num payload — **verificar
se isso é resposta de API ou se pode divergir do perfil.**

### GRAVE 2 / MÉDIO 3 — o gate e a falha fechada (verificados)

```python
# operario.py:42-67  — antes era `is_servidor = True; pode_criar = True`
except Exception:
    logger.warning("kanban_perfil_ilegivel", ...)
    is_servidor = False
    area = ""
    pode_criar = False

# operario.py:101-104 — o gate
demo_habilitado = settings.DEBUG or getattr(settings, "AMPLIAGRO_DEMO_ENABLED", False)
if not is_servidor and propriedade and not base_qs.exists() and demo_habilitado:
```

E a formulação do problema é exacta:

> *"**É O INVERSO DO `sem_dado`. Aqui o vazio é preenchido com mentira.**"*

### BAIXO 5 — ❌ ainda vivo, e é maior do que o ledger diz

O ledger diz "250+ níveis, dormente desde 26/07". **Medido agora:**

```
_backups/  ->  12 151 subpastas
backups/   ->  02/10/2026     (ontem)
cofre-bekups/  ->  25/07/2026
```

O ledger diz que a árvore estava *dormente*. **`backups/` foi modificado
ontem.** Ou a árvore continua a crescer, ou há um segundo processo. O dano
documentado (barra `grep`, CI, antivírus, e *"foi a CAUSA SECUNDÁRIA de dois
enchakes de ferramentas nesta sessão — Get-ChildItem estourou 120 s"*) continua
plausível, e eu próprio ive um `Get-ChildItem` a estourar o timeout durante
esta sessão.

---

## 7. Domínio e dados (condensado; a v1 tem o detalhe)

Cadeia que sustenta quase tudo:

```
User ──1:1── PerfilUsuario
  └── Propriedade (FK user)   ← o TENANT é o user, não django-tenants
        ├── Talhao ── TalhaoGeometria (GeoJSON)
        ├── Safra ── EstagioCultura ── RegistroProducao
        ├── LancamentoFinanceiro, EstoqueItem, Animal, Maquinario, Funcionario
        └── Device/Gateway/TelemetryData (IoT)
```

⚠️ **Multi-propriedade é real, não acidental:** `Propriedade.user` não tem
`unique=True`. Daí `.first()` espalhado pelo código e o módulo
`painel_agregado.py`, que existe porque *"`dashboard_data` recebia **uma**
propriedade [...] Um produtor com duas fazendas via o painel inteiro
calculado sobre uma delas, **sem qualquer aviso**: números reais, errados."*

⚠️ **`app/models/__init__.py` não exporta `AreaPreservacao`** (definida em
`core.py:258`) — provável omissão.

---

## 8. Achados meus desta sessão (verificados)

### Leitura profunda: Criador Livre e LGPD

**`app/ia/dinamicos.py` (721 linhas)** — Onde a "lógica" criada pela IA é aplicada por código genérico. O ponto que define a segurança:

> *"O que a IA **não** consegue fazer, por construção: escrever uma função, exigir `import`, disparar um shell, ler um arquivo do servidor, ou sair do escopo do usuário. **Não é uma política configurável que alguém pode desligar; é a ausência de um caminho de código que faça essas coisas.**"*

E a fronteira de campo:
```python
RE_CHAVE = re.compile(r"^[a-z_][a-z0-9_]{0,58}[a-z0-9]$|^[a-z_]$")
```
> *"Nomes de campo são identificadores, não texto livre. Esta regex é a fronteira que impede `dados__` virar um lookup malicioso."*

**`app/views/lgpd.py` (400 linhas)** — Direito de acesso e de esquecimento. Defeito real documentado:

- **Exportação devolvia 130 bytes e 5 campos.** *"Para a fazenda que existe no banco: 18 talhões, 12 safras, 4 lançamentos, 18 animais, 2 maquinários, 8 dispositivos, 3 funcionários, 115 execuções de IA, 113 eventos, 17 artefatos, 68 widgets, 8 notificações — e o endereço rural completo. Nada disso saía."*
- **Anonimização não anonimizava.** *"`PerfilUsuario` não tem campo `nome` [...] A tela dizia 'Dados anonimizados' e o perfil continuava intacto."*

Regra que fica: **"Nenhum `except: pass` numa operação que o titular usa para exercer um direito."** E `_registros` devolve **a contagem com os dados** — *"sem ela, quem pede os dados não tem como conferir se veio tudo."*

**`app/ia/palco.py` (270 linhas) — O palco: o que a IA pode mandar aparecer**

A fronteira entre "compor widgets existentes" e "desenhar HTML livre". A regra:

> *"A IA **não desenha** widgets. Ela **compõe** widgets que já existem no registo `WIDGET_TYPES` [...] Por isso `render_preset` valida contra este catálogo e **descarta** o que não conhece."*

Cada widget declara a sua `fonte` (`servidor` ou `top_globais`), e alguns marcam `simulado: True`. Houve um defeito real: a primeira versão do catálogo foi montada a partir dos TÍTULOS do `WIDGET_TYPES` em JavaScript, oferecendo ao modelo ids como `kpi-custo` que a camada de dados nunca conheceu — *"mesa ia montar com títulos e zero números."*

**`app/ia/palco_dados.py` (682 linhas) — Onde a proveniência encontra o produto**

Regra única:

> **"Um número que não sai do banco não entra na mesa. Nem zero, nem um placeholder, nem um '-'. Uma mesa com um card a menos é uma mesa menor; uma mesa com um número inventado é uma mentira, e o produtor age em cima dela."*

O `_n` devolve `None` (não `0`) — *"'sem dado' e 'zero' são coisas diferentes."* E importa `Medido`, `Estado`, `serializar_tudo` directamente da `proveniencia.py` — **a doutrina está centralizada e reutilizada, não reimplementada por módulo.**

**`app/ia/paginas.py` (407 linhas) — Os MODELOS de tela com que uma IA constrói um painel**

O problema que resolve: *"Peça a um agente externo 'monta um painel para uma fazenda de café', e ele tem três saídas, e as três são inventar."* E a formulação:

> *"Um modelo não inventa melhor quando lhe dão regras; inventa melhor quando lhes dão um **catálogo**."*

Regra única — e é contra o LLM pequeno:

> *"os MODELOS só usam widgets MEDIDOS — **não há interruptor para ligar os simulados, porque um interruptor que não faz nada é pior do que nenhum**: o modelo marca-o, gasta uma chamada, e a tela não muda."*

E o `REQUISITOS_POR_WIDGET` é **derivado, não escrito à mão**: *"hoje `cafe` citava `kpi-custo` e não pedia lançamento nenhum, e o contrato prometia 'completa' com um quarto do ecrã em branco. Derivar daqui é o que impede a repetição — acrescentar um widget a um modelo passa a trazer o requisito consigo."*

**`app/services/top_globais.py` (554 linhas) — O handler mais perigoso, já corrigido**

O docstring de `vra_ndvi_prescricao` documenta o ataque mais grave que encontrei no projecto:

> *"Este handler fazia três coisas que não podia fazer:*
> 1. *Marcava `fonte_real` só porque `COPERNICUS_USER` existia no ambiente. **Ter a chave no `.env` não descarrega um pixel** — e essa linha sozinha transformava um `None` em 'medido', sem aviso."*
> 2. *Prescrevia `dose: 180` kg de NPK 20-10-10 a partir de um NDVI que era um **sha256 do id do talhão**."*
> 3. *Emitia um XML ISO11783 — o formato que uma máquina de aplicação lê para espalhar produto no campo — com essa dose."*

> *" junto: uma aplicação de fertilizante com o formato que um tractor consome, a partir de um número que ninguém mediu."*

A correcção: sem NDVI medido, `prescricao: None`, `dose: None`, **e diz porquê**. E a nota de desenho: *"A lógica de dose, quando houver NDVI real, pertence a um agrónomo e a uma tabela de recomendação — não a um `if` num widget."*

E a mesma doutrina no `can_bus_telemetria`: *"`latest` vive aqui fora do `if` de propósito [...] A view devolvia 500, e **um 500 não diz 'não há telemetria': diz 'a aplicação está caída'**."*

**`app/services/ndvi.py` (119 linhas) — O defecto mais completamente documentado**

A história inteira cabe no docstring:

> *"`ndvi_medio` era `max(0.4, min(0.88, 0.55 + sha256(talhao_id-semana) % 300 / 1000))`. Ou seja: **um hash**. Não havia uma única chamada à Copernicus em lado nenhum do repositório — o nome 'Sentinel-2' estava no `return`, e mais nenhum."*

E o pior não era o valor — era a etiqueta:

> *"O payload devolvia `"satelite": "Sentinel-2 L2A (determinístico)"`, e o heatmap desenha esse mesmo número a cheio, por cima da cor, com o veredicto agronómico ('Excelente' / 'Atenção') ao lado e a frase `Sentinel-2 L2A • nuvens 12%` impressa por baixo. **Um produtor a decidir irrigar pela cor de um talhão estava a olhar para uma imagem de satélite falsificada, com o carimbo do satélite verdadeiro por cima.**"*

> *"A docstring chegou a dizer 'NDVI real por talhão'. Não usava."*

Agora `_buscar_sentinel2` devolve **sempre** `None` (a implementação real ficou por fazer) e o payload diz `fonte_dado: "indisponivel"` com o motivo. Detalhe bonito: sem valor, `data_captura` também é `None` — *"a data de um dado que não existe é outra mentira pequena que se pode evitar."*

**`app/services/simulacao.py` (198 linhas) — Onde o probabilístico é correcto**

`monte_carlo` usa `random.Random(seed)` com `seed=42` por omissão. Puro, sem banco, sem HTTP, reprodutível. **O contraste deliberado:** onde o número é uma *medição* tem de vir do banco (`ndvi.py` foi reescrito por isso); onde é uma *simulação* tem `seed`, é pura, e é rotulada como simulação.

**`app/services/cotacoes.py` (190 linhas) — O defeito mais insidioso, e a origem de `proveniencia.py`**

> *"O carimbo de proveniência comparava o resultado com um SEGUNDO sorteio (`b3_data != cls._fetch_b3_mock()`). Dois sorteios independentes de `random.uniform` **nunca coincidem — medi 0 coincidências em 500 tentativas** — portanto `"fonte": "real"` era o que saía praticamente sempre, por cima de dados 100% aleatórios."*

Isto é a **mesma arquitectura de `proveniencia.py`, por defeito**. E mostra exactamente porquê: o mecanismo era *funcionalmente correcto* (a comparação nunca dava `real` por acidente) — era apenas **inútil**, porque interrogava o mock errado, e `_fetch_b3_real()` devolvia `None` em **todos** os caminhos.

Isto é o `proativo.py:238-251` noutro ficheiro: *"um teste que cobre a função errada é pior do que nenhum, porque parece cobertura."*

**`app/views/nfe_auto.py` (204 linhas) — Segurança de upload bem feita (o inverso do IoT)**

- **`defusedxml`**, não `xml.etree`: *"a biblioteca nativa não resolve entidades externas, mas expande as internas — e um 'billion laughs' cabe em 2 KB. Este ficheiro chega por UPLOAD: **o input é de um autenticado, e por isso é exactamente o input que não se pode confiar.**"*
- Teto de 5 MB verificado **antes** de ler uma byte.
- `ParseError` → 400, `DefusedXmlException` → 400, `Exception` → 500 **sem `str(e)`** — *"vaza caminho/integrity detail pro cliente"*.
- Tenancy correcto: `Propriedade.objects.filter(user=request.user)`.

**`app/services/custo_producao.py` (107 linhas) — Três bugs do mesmo padrão num ficheiro**

O inimigo sistemático é o `or Decimal("1.0")`. **Três vezes no mesmo ficheiro**, e cada uma produz "um número plausível e errado":

| # | Onde | O que fazia |
|---|---|---|
| 1 | área | `Safra.talhoes` é uma M2M **vazia (0 linhas)**; a soma dava 0 e caía no `or 1.0` — *"custo por hectare dividido por **um hectare que ele nunca declarou**"* |
| 2 | produção | `producao_estimada` **nunca existiu** no modelo; AttributeError em **toda** safra, mascarado por um FieldError anterior |
| 3 | custo/saca | produção zero não divide; o fallback devolvia o custo **inteiro como se fosse por saca** |

A cascata corrigida: `area_plantada` → talhões → **`None` com `erro: "safra_sem_area"`**.

**`app/ia/propriedade.py` (65 linhas) — O melhor exemplo de "regra de segurança não pode viver em N sítios"**

Existiam três cópias byte-a-byte de `_prop` (`_prop`, `_prop2`, `_prop3` em `intents.py`/`intents2.py`/`intents3.py`). O porque de consolidar:

> *"Os nomes diferentes diziam 'três coisas diferentes', e é exactamente esse o defeito: **são a MESMA regra, e a regra é de segurança**. O filtro `user=user` é o que impede um produtor de ler a fazenda de outro. **Um handler corrigido e dois por corrigir é isolamento de tenant por sorte** — e o teste que passa no handler corrigido dá confiança falsa sobre os outros dois."*

E as cópias **já divergiam**: `_prop` rebentava com `AttributeError` se `params` era `None`; `_prop2`/`_prop3` usavam `(params or {})`. Um `None` é um `params` legítimo — o sandbox chama handlers sem argumentos opcionais.

A regra (inalterada): `propriedade_id` wins, **mas o `user=user` fica sempre no filtro** — um id de outra conta simplesmente não casa.

**`app/ia/intents3.py` (1331 linhas)** — Escritas guiadas: `h_editar_safra` valida `campo not in _CAMPOS_SAFRA` — uma **allowlist** de campos editáveis. Nunca `campo = params.get(...)` directo ao `.save()`.

**`app/api/perms.py` (91 linhas) — Permissões para tabelas sem dono**

`Cultura` é a tabela de referência **partilhada** (~700 linhas semeadas, sem dono). Qualquer produtor podia `PATCH` e mudar a janela de plantio de "Soja" — o que altera a recomendação agronómica de todos. A correcção: `GET/POST` livres, `PUT/PATCH/DELETE` **só `is_staff`**. E o `has_object_permission` existe para fechar um caminho que ainda não existe — *"o DRF chama os dois, e um `return True` aqui seria uma porta aberta caso alguém acrescente um `get_object`."*

> *"Isto não substitui um `Cultura` com dono [...] Até lá, é **o buraco mais pequeno que não parte o produto**."*

Junta-se a `IsOwnerPropriedade` (em `iot/viewsets.py`) para formar a dupla camada do tenancy na API: models com `propriedade` → `IsOwner`; tabela partilhada sem dono → `LeituraGlobalEscritaStaff`.

**`app/api/views/faltantes.py` (136 linhas) — A regra de tenancy como fábrica, não como 15 copies**

Este ficheiro não escreve 15 viewsets — escreve **uma fábrica** e instancia 15:

```python
def make_scoped_viewset(model, scope_lookup, filters=(), search=()):
    ...
    def perform_create(self, serializer):
        obj = serializer.save()
        ok = model.objects.filter(pk=obj.pk).filter(**{scope_lookup: self.request.user}).exists()
        if not ok:
            obj.delete()
            raise PermissionDenied("Fora do escopo do seu usuário")
```

É `propriedade.py` aplicado à camada REST: **a regra de tenancy não pode viver em 15 sítios, então vive em 1 sítio que gera os 15.** Cada um dos 15 modelos declara o seu `scope_lookup` — o caminho de reverso até `user`, **o mesmo formato** do `TenantIsolationMiddleware.TABELAS_VERIFICADAS`.

E o `perform_create` valida **depois** do save e **apaga se fugir do escopo** — mais robusto que validar o `validated_data` antes, porque cobre qualquer caminho de escrita.

Isto é o contraponto exacto ao que o `console.md` regista (`intents.py` com 3 cópias de `_prop`, o `edit` a corromper ficheiros): alguém aprendeu a lição e a aplicou por ⚙️ fábrica.

**`app/services/recomendacao_solo.py` (143 linhas) — `None` como mais-valoroso que `0`, na agronomia**

`analisar_solo` está documentada como **bomba-relógio sem rota** (a auditoria de 2026-09-29 confirmou que não é chamada). Três defeitos que seriam enganadores se alguém a ligasse: `estado_ph` era "Bom" por omissão; `recomendacao_npk` era "300 kg/ha de 04-14-08" com "Placeholder"; `ctc or 0` transformava campo ausente em zero **que alimentava a fórmula de calagem**.

A correcção: `recomendacao_npk: None`, `estado_ph: None` sem pH, e uma lista `faltando_na_analise` **nomeada**. E a distinção crítica:

> *"Um `or 0` esconde a diferença entre 'o solo não tem alumínio' e 'não medimos o alumínio' — e **a segunda é a que impede a calagem de ser recomendada**."*

A calagem e gessagem **continuam a ser calculadas** a partir de análise real — o módulo não foi desactivado, foi corrigido para onde não sabe responder.

**`app/services/hedge.py` (73 linhas) — Matemática correcta, texto com literal (inconsistência interna)**

`hedge_recomendado` é puro e determinístico, mas embute um valor no texto:
```python
"recomendacao": "TRAVAR 50% a R$145" if ganho > 0 else "NÃO travar..."
```
`R$145` vem do caso de referência (1000 ha, soja 85→80), não do input. Para um produtor com 10 ha ou 5000 ha, o texto diz "R$145" igual — e parece ao produtor que R$145 é calculado. **É a mesma classe de literal que `paginas.py` proíbe** — num ficheiro de matemática que, de resto, está certo. Inconsistência interna, não bug grave.

### CONFIRMADO — li a linha

**`app/bot.py` (423 linhas) — O detector que põe a excepção onde se pode errar**

> *"A pontuação é a soma. Só passa do limiar quem junta **vários sinais fracos**, que é a diferença entre **'isto é um humano' — afirmação que não se sustenta — e 'isto não parece humano' — que se sustenta**."*

E o sinal contra-intuitivo — **um User-Agent que se diz browser é sinal negativo**:
> *"Um bot que se apresenta como Chrome está a fazer o que os bots fazem, mas um produtor com proxy também, e não é o nosso alvo. **Por isso desconta.**"*

Com a ressalva que torna isto honesto: `curl`, `python-requests` e `httpx` estão na lista — mas *"não são 'bots' no sentido maligno: são integrações legítimas — a IA local, por exemplo. Por isso contam como sinal, e não como veredicto."*

**O safeguard final:**

> **"QUEM TEM SESSÃO PASSA SEMPRE."**
> *"Um produtor com login recebe 403 porque a IA o skepeou e fecha-lhe o painel? **Não** — e é o único garante real contra falso positivo, porque um raspador nunca tem sessão."*
> *"O preço é abrir a sessão antes de recusar. É um custo medido e aceite: **pagamos uma linha em `django_session` para conseguir dizer com certeza que não estamos a fechar o sistema a quem trabalha nele.**"*

E a cadência é deliberadamente fraca (+4, ou +2 perto do limite), nunca bloqueio directo:
> *"Um cliente acima do limite pode ser um produtor com uma tela parada a recarregar, e fechar esse é o erro que este módulo existe para não cometer. **A pontuação tem de somar com o resto para o portão fechar.**"*

E a assimetria cache/registo é **declarada, não escondida**:
> *"com 4 workers, cada um só viu um quarto das rotas que o cliente visitou. **A dispersão é um sinal fracionário e por isso nunca chega sozinho ao limiar.**"*

**O padrão, e é o mesmo par de `chamado_intents.py` invertido:**

| Módulo | Onde põe a barreira | Razão |
|---|---|---|
| `chamado_intents.py` | **no handler**, primeira linha | *"uma restrição que está na primeira linha do handler é lida por quem abre o ficheiro"* — para não falhar por **esquecimento** |
| `bot.py` | **na excepção**, quem tem sessão passa | *"o único garante real contra falso positivo"* — para não falhar por **erro** |

Um põe a regra onde se pode esquecer; o outro põe a excepção onde se pode errar.

**`app/validators.py` (194 linhas) — O vocabulário de proveniência, e o estado que faltava**

`ESTADOS_FONTE` tem **cinco** estados, e o quarto (`declarado`) foi acrescentado em **2026-10-03** — o commit mais recente:

```
medido               um sensor disse isto
medido_com_ressalva  um sensor disse, mas algum campo é suspect
suspect              o sensor disse, e não é de confiança
sem_dado             ninguém mediu. Ausência, nunca zero.
declarado            alguém afirmou. Não é medição.
```

E o raciocínio, que é o mais afiado do projecto:

> *"Tudo o que um sensor mede tem carimbo. Tudo o que um produtor **escreve** — uma produtividade de que se lembra, o nome de um talhão — não tem sensor nenhum. E o vocabulário só tinha quatro estados, nenhum dos quais era esse caso."*

As duas saídas ruins, **ambas mentira**:

| Marcar como | Falha |
|---|---|
| `medido` | *"um comprador que pague mais por um lote rastreado está a pagar por uma declaração tratada como medição"* |
| `sem_dado` | *"Errado pelo outro lado: **há** dado [...] o produtor desconfia do sistema inteiro ao ver o que ele próprio afirmou marcado como desconhecido"* |

A regra que fecha:
> **"O sistema nunca promove uma afirmação a medição. Quem mediu foi o sensor; quem afirmou foi a pessoa."**

E aplica-se à **importação de planilha**: *"Uma planilha de 2019 continua `declarado` em 2026, e marcar isso como medido seria apagar de onde o número veio."*

**E a decisão mais contra-intuitiva do projecto — `validate_evidencia`:**

`{}` → **ACEITE.** *"Ausência declarada é honestidade, não erro. O produtor não é obrigado a ter sensor para semear."*

> *"Obrigar `fonte_dado` em tudo transformaria 'não tenho sensor' num erro de validação, e o resultado seria **o produtor a escrever `sem_dado` apressado em tudo para o formulário passar**. **Um campo obrigatório não produz dados honestos; produz dados conformes.**"*

Isto é **fail-open deliberado** onde a regra padrão seria fail-closed — e está certo. Se o campo é obrigatório, o sistema obtém campo preenchido com valor falso. Se é vazio, obtém ausência declarada.

E a mensagem de erro, que é o mais fino da camada:
> *"A mensagem tem de dizer **o que escrever**, não só o que está mal. **Um erro que não diz o caminho é um beco** — [...] e este é o sítio onde **o produtor aprende a mentir em vez de admitir a ausência**."*

Isto é `dinamico_intents.py` ("erro utilizável, não booleano") aplicado ao **produtor humano** em vez do modelo. E "o produtor aprende a mentir" é o reconhecimento de que **um sistema que ensina o utilizador a mentir é um design failure**.

**`app/ia/chamado.py` (864 linhas) — A zona de escrita, e o porquê de ser uma**

> *"O produto tem dois mundos que não falavam: o manual (60 widgets, editáveis à mão) e o da IA (17 widgets, efémeros). Junta-se a isto o facto de o produtor poder **fixar dashboards que pagou, apagou, renomeou e organizou** — e uma IA com permissão de escrita sobre eles reescreve o trabalho de quem os organiza."*

> *"Por isso a escrita tem **uma zona, e só uma**: o Chamado Amplia. Não é uma restrição que se pode desligar porque um dia é útil desligar — **é a razão de o produtor poder confiar que o resto dos presets dele é dele**."*

E o detalhe de **UX de segurança** que é raríssimo:

> *"O motivo importa tanto quanto o `False`. Uma IA que devolve só 'não' faz o produtor achar que a IA está avariada; a mesma IA que devolve **'não, mas posso fazer isso no Chamado Amplia'** é uma IA que o produtor percebe."*

Os tetos são **de produto, não técnicos**, e cada um tem a razão escrita:
- `MAX_BLOCOS = 24` — *"acima disto a tela deixa de ser 'visão rápida' e passa a ser o relatório que o produtor estava a tentar não ler"*
- `MAX_LINHAS = 200` — *"uma tabela que não cabe num ecrã de telemóvel tem de ser uma exportação, não um bloco"*
- `MAX_TEXTO = 4000` — *"um bloco de prosa maior é um documento, e documentos têm outro caminho"*

**`app/ia/chamado_intents.py` (596 linhas) — Onde a restrição deve viver**

> *"A TRAVA VIVE AQUI, NÃO NUM `if` DISCRETO."*

E o porquê é a linha mais dura sobre segurança de IA que li neste projecto:

> *"Houve um handler 'desligado' em comentário com **dois POSTs vivos** a `/api/iot/comandos/`. **Uma restrição que depende de alguém se lembrar de a aplicar é uma restrição que uma sessão cansada burla.** Uma restrição que está na primeira linha do handler é lida por quem abre o ficheiro."*

E a eliminação da superfície em vez da validação:
> *"Nenhuma delas aceita um `user`: o produtor é o `user` que vem do sandbox, e um campo de produtor no corpo do pedido é **a forma mais curta de um vazamento entre contas**."*
> *"`do_produtore` e não `filter(pk=...)`: aceitar um id do corpo e depois comparar a pertença é mais um passo em que alguém se engana. Aqui **não há id para enganar**."*

Isto é `propriedade.py` e `faltantes.py` aplicados a **autorização**: eliminar a superfície em vez de a validar.

E `_prescrever` previne a *"mesa invisível"* — *"existe na base, a IA consegue lê-la, e o produtor nunca a vê"*. É o que `amplia_mcp/urls.py` chama de *"um botão que parece funcionar e não faz nada"*.

**`app/ia/copiloto.py` (229 linhas) — A regra não se duplica; importa-se**

O problema: a regra que acha a aplicação que a chuva estraga **já existe** em `proativo.py::regras_deterministicas`, mas vive num *worker* — e o `sandbox` nunca a chama (*"medido: a palavra 'proativo' não aparece em `sandbox.py`"*). Resultado: *"o produtor pergunta do tempo, recebe a temperatura, e a aplicação de glifosato de quinta fica a lavar-se sem ninguém lhe dizer."*

E a decisão de não duplicar:
> *"`regras_deterministicas` tem a janela de dias, os limiares, o filtro de tarefas concluídas, e o cuidado de não alertar sobre trabalho já feito — porque **'alertar sobre tarefa concluída é o alarme que faz o produtor desligar a notificação'**. Duplicar isso aqui seria ter duas respostas à mesma chuva."*

E o fecho técnico:
```python
from app.ia.proativo import LIMIAR_CHUVA_MM, LIMIAR_CHUVA_PROB
```
> *"Se alguém mudar um limiar, muda nos dois lados **no mesmo commit, porque é o mesmo objecto**."*
> *"a regra vê chuva suficiente, o copiloto oferece o dia errado, e o produtor descobre a divergência **no campo, com o agrotóxico já comprado**."*

E o limite do que faz: *"Não decide o que fazer. Não remarca nada. **Pergunta** — [...] um copiloto que age sem perguntar não é um copiloto: é um sistema a decidir por alguém que paga as consequências."*

**`app/ia/dinamico_intents.py` (671 linhas) — O problema central do Criador Livre**

> *"Um SmolLM2 de 1.7B é capaz de produzir `{"alimento": "X", "idade_da_vaca": 10}` para um schema que tem `alimento`/`quantidade_kg`. **Isso não é hipotético: é o comportamento esperado** de um modelo treinado para continuar texto plausível, não para obedecer contrato."*

E as duas respostas, com a armadilha nomeada:

| | O que se faz | Veredicto |
|---|---|---|
| (a) | aceitar e descartar a chave | **Proibido** — *"o registro foi gravado sem a idade que o MODELO inventou ter visto, e ninguém foi avisado [...] um sistema que perde dado em silêncio é pior que um que não tem o dado"* |
| (b) | recusar dizendo a chave inválida e as válidas | **O que fazem** — *"a recusa precisa voltar para o modelo como um erro **utilizável**, não como um booleano. Sem o nome do campo válido, o modelo não tem como se corrigir."* |

`MAX_CAMPOS = 20` por **duas** razões: a janela de 4096 tokens do SmolLM2, **e** *"um modelo pequeno não planeia 60 campos. Ele vai tentar, falhar, e devolver um schema pela metade."*

⚠️ `TIPOS_ACEITOS` duplica `TIPOS_CAMPO` de propósito (o schema vai para o prompt), e o comentário **admite a divergência**: *"divergência entre as duas é impossível de corrigir em tempo de execução."* É uma dívida **nomeada**, não escondida.

E a defesa em três camadas: *"Quem garante a integridade é o schema no banco, não o bom comportamento do modelo. Mesmo que o modelo se comporte, a tool é estrita; e mesmo que a tool fosse contornada, `registrar()` valida de novo antes do `save`, dentro de `transaction.atomic`. São três camadas, e a última não depende do modelo."*

**`app/ia/texto.py` (116 linhas) — O módulo mais revelador: a cola entre dois destinatários**

Cada intent tem **uma** descrição, escrita **para o modelo** (`"INSTRUÇÃO IA: use para..."`). O `sandbox` ecoava-a no pedido de confirmação, e o produtor lia literalmente:

> *"Você confirma a execução de **'INSTRUÇÃO IA: use para 'gera pedido de compra / faz pedido de diesel/adubo'. Cria como RASCUNHO e confirma.'**?"*

> *"**A única barreira antes de apagar uma safra estava embebida em texto de engenharia.**"*

E o diagnóstico vai mais fundo que o bug:

> *"O pior não é o texto: é que **ninguém leu e ninguém decidiu**. A descrição servia para o modelo; o sandbox reutilizou-a para a pessoa; e a escolha passou despercebida porque **nenhuma das duas metades estava errada sozinha.**"*

> *"Não é um bug do `sandbox` nem dos autores. É a **COLA**: um texto escrito para um destinatário a ser mostrado a outro."*

A correcção **não** é "limpar a descrição" — a descrição está certa para o modelo. É ter **dois textos**: `prompt_confirmacao` (escrito pelo autor para a pessoa) com fallback à descrição limpa. E nunca um prompt inventado: *"um prompt de confirmação inventado é pior que um feio: pode prometer o que o código não faz."*

O `RE_INSTRUCAO` é regex e não `startswith`, por um motivo medido: a descrição de `feedback` começa com `"INSTRUÇÃO IA (ML):"` — parênteses **antes** dos dois pontos. `startswith` não casa. *"Foi o único de 80 a vazar, e continuaria a vazar com `startswith` corrigido à pressa."*

**Isto é `coerencia.py` outra vez:** corrigir o sintoma (`startswith` → regex) sem tratar a classe (`\b[^:]*:` para não partir no `:` errado).

**`app/ia/voz.py` (285 linhas) — O módulo mais humano, e a decisão mais difícil**

Medido antes de mexer: em `app/ia/*.py`, 25 de 29 ficheiros usavam markdown, 19 negrito, 7 setas, 4 emoji.

> *"Um produtor no meio do talhão não vê um asterisco duplo. Vê dois asteriscos e adivinha o resto. E `**` numa **docstring** é correcto — é para quem lê o código. O problema é `**` numa **resposta**."*

A correcção é no **limite** (`sandbox.executar` lava antes de devolver), não na origem — porque *"um handler novo escreve `**negrito**`, não há lint que apanhe isso, e a regra vive num ficheiro de regras que ninguém lê."*

E a decisão de design mais difícil de escrever — **não** passar para a primeira pessoa:
> *"Passar para a primeira pessoa continua a ser o sistema a falar de si, só que mais curto. **É TIRAR O SUJEITO**."*
> `"Ele avisa quando o sync fica offline."` → `"Avisa quando a sincronização fica desligada."*

E o detalhe linguístico mais fino: o artigo vem **junto** na substituição, *"porque trocar a palavra e deixar o artigo é o que produz 'o sincronização' — e um erro gramatical numa resposta diz ao produtor que ninguém a reviu."*

E o limite que o módulo impõe a si próprio:
> *"Não reescreve frases. **Uma voz que reescreve o sentido é pior do que uma voz robótica, porque parece mais segura do que é.**"*

**0. `app/services/custos.py` — o `or 0` legítimo (e a distinção que torna a doutrina aplicável)**

`custos.py` usa `or 0` no cálculo de custo. **É correcto**, e é o contraponto exacto de `custo_producao.py`: aqui `Sum()` devolve `None` porque **não há lançamentos** — `0` é o valor medido. Em `custo_producao.py`, `or 1.0` escondia **área nunca declarada**.

> **O mesmo operador, significados opostos — e a diferença é se existe um facto medido por trás.**

Esta é a regra que torna a doutrina aplicável sem ser absurda: `None → 0` é honesto quando o vazio *é* o zero; `None → 1.0` é mentira quando o vazio *significa falta de medição*. `custos.py` tem o comentário *"Para MVP: insumos vêm de RastreabilidadeSafra; demais ficam 0 até rateio detalhado"* — assume a dívida em voz alta. E `custo.save()` deixa o cálculo derivado no modelo, não no serviço.

`app/services/vra.py` gera ISO 11783-10 (o XML que um tractor consome). Usa `xml.etree` sem `defusedxml` — correcto, porque é **saída**, não entrada: não há XML não-confiável a parsear. O `defusedxml` do `nfe_auto.py` protege o *upload*; aqui não há nada a proteger.

**1. `app/services/lcdpr.py:33-36` — CPF fixo num ficheiro fiscal**

```python
# Dados fake do produtor na base
cpf_produtor = "12345678901"
```

O gerador do **LCDPR** (declaração à Receita Federal) escreve sempre
`12345678901` no registo `0000`, mesmo com `Propriedade.cpf_cnpj` preenchido
(`core.py:86`). Usado por `api/exportar-lcdpr/` e pelo intent
`gerar_lcdpr`. É um placeholder em produção. **Correção: uma linha.**

**2. `app/services/lcdpr.py:69-79` — 12 queries num `for` de 12 meses**

`self.lancamentos.filter(data__month=mes)` dentro de `for mes in range(1,13)`.
Um `values("data__month","tipo").annotate(Sum("valor"))` faz o mesmo em 1.

**3. `app/ia/views.py:356` — gravação sem escolha em multi-propriedade**

`confirmar_estoque` faz `Propriedade.objects.filter(user=user).first()`.
Num sistema que suporta várias fazendas, o item vai para a errada e não há como
o produtor escolher. Falta `propriedade_id` no pedido, validado por
`propriedades_visiveis`.

**4. `config/settings/base.py:256` — `InMemoryChannelLayer`**

`ASGI_APPLICATION` + `daphne` activos, `DashboardConsumer` existente, e o
channel layer **em memória**. Com mais de um worker, `group_send` não chega
aos outros processos. Redis já está no `docker-compose.yml`.

**5. `app/api/views/utils.py:46-66` — uma mina com `return 2000` (rebaixada)**

```python
def _parse_value(v):
    ...
    return 2000          # em QUALQUER falha: não numérico, string vazia, lista
```

Ao lado, `_to_float` (linha 69) faz o mesmo trabalho e **devolve `None`** em
vez de um número — que é o comportamento correcto, e o que a `proveniencia.py`
exige.

⚠️ **Rebaixada depois de verificar chamadas.** Li a definição e classifiquei
como risco; o grep mostra que **`_parse_value` é importada em
`app/api/views/iot.py:50` e não é chamada em lado nenhum.** Hoje é inerte.

Fica registado como **mina**, não como bug: o dia em que alguém a usar, cada
valor não parseável vira `2000` em silêncio — `proveniencia.py:12` documenta
exactamente esta classe de bug (`getWidgetDataFromAPI()` com `|| 'R$ 450'`).
A correcção é borrar a função, ou fazê-la devolver `None` como `_to_float`.

**Lição de método, registada porque é o que me fez reportar errado:** a
minha primeira busca usou `app\**\*.py`, que em PowerShell são **dois
níveis**, e por isso não viu `app/api/views/`. Um grep que não encontra nada
não é prova de que não existe — pode ser o glob.

### RUIDO — scanner rodou, falso positivo

- `middleware.py:85` — semgrep `direct-use-of-httpresponse` (WARNING, LOW
  confidence). A string vem de uma chave de dict, não do utilizador.
- 11 × "Hardcoded Password" (ast-grep) — todos `password="x1234567"` em
  fixtures de teste.

**6. `app/iot/views.py:130-158` — injecção de telemetria sem autenticação (GRAVE)**

A hipótese que levantei na v2 **está confirmada, e é pior do que supunha.**

Primeiro, a parte que está certa: **existe autenticação.** `_resolve_auth`
(linhas 32-61) aceita `X-API-Key`, `?api_key=` ou `Authorization: Bearer`, e
procura o gateway por `api_key_hash=hash_cego(api_key)` — Fernet, *"índice
cego"*, e o comentário explica bem porquê: *"Fernet é randomizado e nunca casa
em `filter(campo=valor)`"*. `app/seguranca.py` tem `EncryptedCharField` e
`get_fernet()` que **explode em produção sem `AMPLIAGRO_DATA_KEY`**. Isto é
trabalho a sério.

O problema é o fallback do webhook TTN:

```python
# iot/views.py:130 — o atacante decide se é um webhook TTN
is_ttn_webhook = isinstance(payload, dict) and (
    "uplink_message" in payload or "end_device_ids" in payload
)
...
# iot/views.py:147-158
device, err = _get_device_from_request(request, device_eui)
if err:                                              # err é 401 "autenticação necessária"
    if is_ttn_webhook and device is None and device_eui:
        device = Device.objects.select_related(...).get(device_eui=device_eui)
        # ^^^ o 401 é DESCARTADO e o device é resolvido SEM auth nenhuma
```

`is_ttn_webhook` é determinado **pela forma do corpo do pedido** — é o
atacarante que decide entrar por esta porta. E o `device_eui` vem do próprio
payload (`end_device_ids.dev_eui`).

**O comentário da linha 129 promete uma verificação que não existe:**

> `# Se for webhook TTN sem auth mas com app_id conhecido, permite (valida via FonteDadosExterna)`

E a linha 149:

> `# permite webhook TTN sem api_key se device for encontrado e **fonte externa TTN ativa**`

**Não há verificação de `FonteDadosExterna`.** Varri o código inteiro: as
únicas utilizações de `FonteDadosExterna` são `ia/fontes.py` (a allowlist da
IA), `services/cotacoes.py` (CONAB) e os serializers/viewsets de CRUD. **Nenhuma
no caminho do webhook.** E também não há validação por IP nem token: procurei
`REMOTE_ADDR`, `X-Forwarded-For`, `ttn_token`, `webhook_secret` — nada no path
de autenticação.

E a docstring da view afirma o contrário do que o código faz:

```python
# iot/views.py:114
# TTN/ChirpStack webhook pode vir sem api_key - valida por IP/config se necessário;
# por ora exige key          <-- NÃO exige key. O bloco abaixo dispensa-o.
```

**Impacto, com `device_eui` conhecido** (que é um identificador de hardware,
frequentemente impresso na etiqueta do sensor — não é segredo):

| Efeito | Onde |
|---|---|
| Escrita em `TelemetryData` | `bulk_create` em `:194` |
| Escrita em `LeituraSensor` (tabela legacy) | `:227`, se `device.estacao` |
| **`gateway.status = "online"` falsificado** | `:243` |
| `device.bateria_pct`, `device.rssi` falsificados | `:236-237` |
| **Dispara `evaluate_batch` + `evaluate_culture_alerts`** | `:248`, `:255` |

O último efeito é grave por si, mas o motor de regras **agrava-o**. De
`app/iot/regras_auto.py:13-27`:

```python
{
  "id": "grao_bme280_pivo_40mm",
  "metric": "umidade_solo",
  "tipo": "threshold_min",
  "valor_ref": 60,
  "acao_fisica": "abrir_valvula",     # ← ABRE UMA VÁLVULA
  "severidade": "critical",
}
```

**A cadeia completa, ponta a ponta:**

1. Atacante faz `POST /api/iot/mqtt/webhook/` com `{"uplink_message": …, "end_device_ids": {"dev_eui": "<alvo>"}}` — **sem auth**, porque o fallback TTN descarta o 401
2. `normalize_payload` extrai `umidade_solo: 50` do payload
3. `TelemetryData.objects.bulk_create` grava
4. `evaluate_batch` vê `50 < 60` → **`acao_fisica: "abrir_valvula"`**
5. **Irrigação activa numa fazenda que não pediu** — acionada por um caminho que não passa pelo `sandbox.executar` onde `ligar_irrigador` vive governado (`irrigacao.write`, `needs_confirm`, `SEM_CACHE`)

**Não é exfiltração de dados. É acção física não autorizada num sistema agrícola.**

E o motor de regras está *correctamente escrito* — debounce, guardas de dados insuficientes (`len(vals) >= 20`, `avg is not None`), z-score com média e desvio reais. **O que falta é a garantia de autenticidade da origem, não a de integridade do processamento.**

Isto é o achado mais grave do documento.

**Correcção:** o `FonteDadosExterna` activo **tem de ser consultado** antes do
fallback, e `is_ttn_webhook` **não pode** ser decidido pelo corpo do pedido.
Ou o webhook valida por IP allowlist, ou exige `api_key`, ou morre.

**7. SEGUNDO VECTORE, INDEPENDENTE — `NaN`/`Inf` na telemetria (GRAVE)**

Confirmado por leitura de `app/iot/parsers.py` e `app/iot/views.py`.

`parsers._coerce_value` (linha 185) é só `float(v)` com `None` em falha:

```python
def _coerce_value(v):
    try:
        return float(v)
    except Exception:
        return None
```

**Não há `math.isfinite`.** E `float("nan")` / `float("inf")` passam — `val is None` é `False` para ambos (linha 355), e `_dict_to_readings` (linha 374) não tem guarda de plausibilidade nenhuma. Não existe `RANGE`, `MIN_`, `MAX_`, `clip`, `sanitiz` em todo o ficheiro.

E o `push_telemetry` grava com `qualidade="good"` **hardcoded** (linha 187), apesar do comentário na linha 175 dizer *"ignora métricas fora do range absurdo (ex: -9999)"* — **não há nada que ignore**. O `try/except` só apanha excepções de construção, não valores absurdos.

**Porque isto é grave e não cosmético:**

1. `alert_engine.py:67` faz `Avg("value")` sobre a propriedade. **Um `NaN` contamina a média inteira** — e o `delta` e o `anomalia` (z-score) comparam contra essa média. O motor de regras fica cego para a métrica, ou pior, fica com `mean = nan` e `stdev = nan`, e as comparações `>= thr` ficam `False` para sempre.
2. `NaN` gravado em `TelemetryData` **propaga-se a todas as leituras futuras** que façam agregação sobre a mesma propriedade+métrica.
3. `NaN` em `LeituraSensor` (o mirror legacy) também.

**Correcção:** `_coerce_value` deve devolver `None` para `nan`/`inf`:
```python
v = float(x)
return v if math.isfinite(v) else None
```
E `qualidade` deve reflectir a validação, não ser constante.

⚠️ **Agravante independente** (`iot/views.py:54-59`): `device_eui` **funciona
como `api_key`**:

```python
# tenta device_eui como key (legado)
dev = Device.objects.select_related(...).get(device_eui=api_key)
return dev.gateway, dev
```

Isto torna o identificador de hardware **uma credencial**, em qualquer rota.
O comentário diz "legado" — mas continua vivo.

### NÃO VERIFICADO
- **`app/api/views/user.py`** — 57 KB, o maior ficheiro da API. Só li
  `dashboard_data` por graph.
- **`app/views/*.py`** — 33 ficheiros; li `servidor.py`, `operario.py`,
  `utils.py` (parcial). `auth.py` (27 KB), `guias.py` (20 KB), `cadastro.py`
  (22 KB) por ler.
- **`app/ia/proativo.py`** — li 1-309 de 1029.
- **`app/amplia_mcp/`** — li `__init__.py` 1-130 de 978, `servidor.py` completo,
  `views.py` 1-120 de 474, `contrato.py` por ler.
- **Migrações** — 64 arquivos, `0001_initial` → `0064_chamadoamplia`. Não as li.

### Scanners: cobertura real

| Scanner | Correu? | Resultado |
|---|---|---|
| semgrep | sim, 7 ficheiros | 1 WARNING, falso positivo |
| ast-grep | sim, **`files_scanned: 4`** | 11 falsos positivos (fixtures) |
| bandit | **não** | não instalado neste host |
| gitleaks | **não** | não instalado |
| osv-scanner / grype / trivy | **não** | não instalados |
| codeql | **não** | não instalado |
| ZAP (DAST) | **não** | não instalado, e sem Docker |

⚠️ O `ast-grep` reportou `files_scanned: 4` quando lhe passei a pasta `app/`
com 362 ficheiros Python. **Não considero o secrets-scan do projecto feito.**

**Logo: CVEs de dependência, segredos no histórico git, IaC e DAST não foram
verificados.** Dizer "seguro" nesses eixos seria mentira — e é exactamente o
que o `console.md:1386` regista como falha de quatro sessões.

---

## 9. Síntese

O Ampliagro é um **sistema multi-processo** (web, MCP stdio, Celery, MQTT,
navegador, Node, coord multi-agente) com **um único caminho de escrita**,
governado por `sandbox.executar()`.

A IA é **probabilística por cima, determinística por baixo**: um LLM de 1,7 B
que raciocina na aba do produtor (com fallback em cascata) chama ferramentas
determinísticas que herdam `needs_confirm`, flags de capacidade, `IAExecucao`,
proveniência e blocklist de compliance — sem nunca poder escrever um `.py`, sem
`eval`/`exec`, e sem poder pedir uma tool que não exista no catálogo.

O que garante a honestidade não são prompts: são **tipos** (`Medido` sem
`fonte` não constrói), **sinais** (a invalidação de cache), e **middleware**
(isolamento por tabela).

A parte mais rara do projecto é o **registo de coordenadas**: `console.md` documenta
falhas, quem as corrigiu, e *o que ficou por verificar* — incluindo que quatro
sessões nunca correram um scanner. É a razão por que este documento distingue
`CONFIRMADO` de `NÃO VERIFICADO`.

### O que eu mudaria, por ordem

1. **`app/iot/views.py:130-158` — webhook TTN sem auth.** Injeção de telemetria e de alertas sem credenciais. Exige a verificação de `FonteDadosExterna` que o comentário já promete, e `is_ttn_webhook` não pode vir do corpo do pedido. **É o único item desta lista com impacto de segurança em produção.**
2. **`lcdpr.py:34`** — CPF fixo (`"12345678901"`) num ficheiro fiscal. Uma linha.
3. **`InMemoryChannelLayer`** — o websocket parte em multi-worker. Uma linha de config.
4. **`device_eui` como `api_key`** (`iot/views.py:56`) — um identificador de hardware não deve autenticar nada.
5. **`_parse_value`** (`api/views/utils.py:46`) — importada em `iot.py:50`, **nunca chamada**. Devolve `2000` em qualquer falha. Borrar, ou devolver `None` como `_to_float`.
6. **`_backups/` com 12 151 pastas** — apagar ou mover para fora do repositório.
7. **`views/__init__.py::_SUBMODULOS_LOCAIS`** — tupla manual; um `from .Y import *` novo sem a actualizar reproduz o bug dos 38 módulos apontados para o módulo errado.
8. **`index.html` com 848 KB** — enquanto durar, não há CSP contra XSS em script.
