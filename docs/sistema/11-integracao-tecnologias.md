# 10 — Mapa de Tecnologias para Integracao

**Base:** `docs/sistema/9.md` (agente 9)
**Data:** 2026-10-04
**Projecto:** `C:\Trabalho\Projetos\Ativos\Ampliagro`
**Pedido:** *"se baseie no agente 9.md para fazer isso, construa um arquivo gigante rastreado o que temos de melhor de tecnologia para ajudar na integracao"*

---

## 0. O que este documento e, e o que ele nao e

**E:** um mapa de lacuna-medida -> tecnologia. Cada linha tem a medicao que
justifica a recomendacao. Se a medicao desaparecer, a recomendacao cai.

**NAO e:** uma wishlist. Uma tecnologia so entra se (a) resolver uma lacuna que
**medi** nesta arvore, e (b) responder a "e se nao integrarmos isto?".

### 0.1 O unico metodo que copiei do 9.md

O `9.md` §A.0 conta que o medidor v1 do agente 9 procurava um termo e contava
ocorrencias, e deu **21 "OK" em coisas que nao existem**. `CBAM` apareceu num
teste. `e-CAC` casou com `from django.core.cache import cache` — o "C" de
"cache" lido como sigla.

A regra que ele tira disso e' a unica coisa que aqui importa:

> *nenhum "OK" entra sem que alguem tenha lido a linha.*

E a regra que eu acrescento, a partir de um erro **meu** desta sessao:

> *nenhum "OK" entra sem que se confirme que o `grep` encontrou o ficheiro
> certo.*

Desconto abaixo. Reado primeiro, confirmei o caminho, e o "OK" evaporou.

---

## 1. TABELA DE ESTADO DE VERIFICACAO

Leia isto antes de citar o documento. O que **nao** esta na secção 1 como
MEDIDO, e' conhecimento meu, e conhecimento meu envelhece.

| Etiqueta | Significado | Como pode ser usada |
|---|---|---|
| **M** | **MEDIDO** nesta sessao, com `ficheiro:linha` | Decisao |
| **V** | **VERIFICADO** hoje por fonte externa | Decisao, com data |
| **C** | **CONHECIMENTO** meu, nao verificado nesta sessao | Hipotese |
| **N** | **NAO VERIFICADO** | Nao decidir |

| Achado | Etiqueta | Evidencia |
|---|---|---|
| BD e' SQLite, nao PostgreSQL | **M** | `config/settings/base.py:173` |
| 560 handlers `on*=` inline | **M** | 54 templates; `index.html` 131 |
| 94 `<script>` sem `src` | **M** | contagem nos templates |
| 1117 `style=` inline | **M** | contagem nos templates |
| `paho-mqtt` ausente | **M** | `requirements*.txt` |
| Broker ausente do compose principal | **M** | `docker-compose.yml`: 0 hits |
| `AMPLIAGRO_DATA_KEY` so em test settings | **M** | `config/settings/test.py:49` |
| **`django-csp` NAO esta em nenhum manifesto** | **M** | ver §2.1 |
| Proveniencia: 5 vs 6 estados | **M** | `validators.py` vs `proveniencia.py:88-95` |
| Nao existe lib mantida de LCDPR | **V** | `python-sped` arquivado |
| PyNFe: NF-e 4.00 + MDF-e, LGPL-3.0 | **V** | github.com/TadaSoftware/PyNFe |
| Django `MIDDLEWARE` resolve no boot | **C** | conhecimento mio |
| Precos dos concorrentes | **N** | 4.md §21 |
| Taxa de classificacao NCM do Ampliagro | **N** | 4.md §21 |

---

## 2. ACHADOS QUE INVERTEM O 9.md

Antes do mapa, tres coisas que o `9.md` disse e que **hoje nao sao verdade**.
O `9.md` §0 ja avisava: *"toda medicao vale no instante em que foi tirada e
deve ser re-verificada antes de virar decisao"*. Isto e' essa re-verificacao.

### 2.1 `django-csp` e' a unica dependencia NAO declarada — e e' a defesa principal contra XSS

**Este e' o achado mais grave do documento.**

| Fato | Evidencia | Estado |
|---|---|---|
| O middleware esta no `MIDDLEWARE` | `config/settings/base.py:120` → `"csp.middleware.CSPMiddleware"` | **M** |
| O pacote esta instalado na maquina | `csp` versao **4.0** | **M** |
| `django-csp` nao esta em `requirements.txt` | 163 linhas, 0 hits | **M** |
| Nem em `requirements-mcp.txt`, nem em `setup.py` | 0 hits nos tres | **M** |

O `MIDDLEWARE` do Django e' resolvido **no arranque**. `csp.middleware` que nao
existe e' `ImportError`, e o ImportError no `MIDDLEWARE` **impede o boot**.

> **Consequencia:** a CSP — a defesa que o `4.md` §1 chama de *"o achado que
> decide tudo"* — **existe nesta maquina porque alguem a instalou a mao.** Numa
> maquina limpa, `pip install -r requirements.txt` seguido de `manage.py runserver`
> **nao arranca**.

Isto e' exactamente a classe de bug que o `9.md` §A.0 promete apanhar e que
nenhum teste apanha: **`tests/test_csp.py` tem 13 testes e todos passam — nesta
maquina.** Passam porque o pacote esta aqui. Nao porque o projecto o pediu.

**Correccao de uma linha:**

```
django-csp>=4.0,<5.0
```

**Nao afirmo** que o CI esteja a falhar. **Nao o medi.** Afirmo o que meci: o
manifesto e o codigo discordam, e o codigo perde.

### 2.2 A promessa criptografica da telemetria esta SUPERADA — o `9.md` §3 esta wrong

O `9.md` §3 classificou como **CONFIRMADO-contraditorio** e escreveu que
`AMPLIAGRO_DATA_KEY` tinha *"zero ocorrencias"* e que *"Fernet/AES para
telemetria nao existe"*.

**Re-medido hoje:**

| Afirmacao do 9.md §3 | Medido agora |
|---|---|
| `AMPLIAGRO_DATA_KEY` tem zero ocorrencias | **So em `config/settings/test.py:49`** — fixture de teste, comentada *"nunca producao"*. **A assertao esta certa.** |
| "Fernet/AES para telemetria nao existe" | **Existe, com outro nome.** `app/iot/views.py:38` documenta: `Gateway.api_key_hash` com hash cego, `app/seguranca.py:hash_cego` |
| "o mecanismo real e' `Gateway.api_key` com Fernet — nome e ambito diferentes" | **Correto no nome, e o ambito e' MELHOR:** a chave esta **cifrada em repouso** (Fernet randomizado) e indexada por hash — um **indice cego** |

O `app/iot/views.py:24-46` e' um caso raro: **o modulo documenta o proprio erro
passado.**

> *"Este texto dizia antes 'sem api_key, valida por config'. **Estava errado**, e
> a frase e' perigosa porque descreve um bypass que nao existe."* (L27-28)

E L85: *"Fallback por device_eui REMOVIDO: qualquer um que conheça o EUI…"* — o
ataque de impersonacao por EUI conhecido foi **fechado**.

E ha um guarda: `tests/test_webhook_ttn_sem_auth.py`, que **falha de proposito**
se o bypass sem `api_key` reaparecer (L43-46).

**Veredicto:** o `9.md` §3 mediu uma arvore anterior. O mecanismo existe, e e' mais
forte do que o manifesto descreve. **O que falta e' o nome**: o manifesto §VI
promete *"Fernet/AES-256 via AMPLIAGRO_DATA_KEY"*; a realidade e' *"indice cego
+ Fernet em repouso"*. **Isto e' um defeito de documento, nao de seguranca.**

> **E por isso que o `9.md` §0 manda rever.** Se eu tivesse citad[o] o §3 sem
> re-medir, publicava um "achado" que ja tinha sido resolvido.

### 2.3 A divergencia de proveniencia mudou de forma — nao desapareceu

O `9.md` §2 publicava "3 estados, `declarado` nao existe" e **foi corrigido**:
`declarado` existe. **Hoje:**

| Sítio | Estados | Numero |
|---|---|---|
| `app/validators.py` `ESTADOS_FONTE` | `medido`, `medido_com_ressalva`, `suspect`, `sem_dado`, `declarado` | **5** |
| `app/ia/proveniencia.py:88-95` `TODOS` | `MEDIDO`, `MEDIDO_COM_RESSALVA`, `SUSPECT`, `SEM_DADO`, **`SIMULADO`**, `DECLARADO` | **6** |

**A divergencia persiste, mas rodou:** agora e' `SIMULADO` que so existe num
lado. E ha uma segunda divergencia que o `9.md` nao mediu: **o tipo**. Um lado
sao `str`, o outro sao membros de `Enum`.

Isto **e' um bug com consequencia**, e nao cosmetico: um payload gravado com
`proveniencia` pode nao passar a validacao de `validators`. Ver §4.5.

---

## 3. O MEU ERRO DA SESSAO — registado, porque e' o que torna o resto honesto

O meu comando de recherche devolveu:

```
test.py:49: AMPLIAGRO_DATA_KEY = "P9BO46kX9OJ46V3LRADIHqiGN_lP_ElHOT9u9nZdWdM="
```

**Meu primeiro impulso foi reportar como segredo hardcoded.** E um `grep` das
minhas settings **nao** encontrava a chave — logo, "acabei de achar uma chave
Fernet em texto claro fora de settings". So porque a variavel se chama
`DATA_KEY` e o ficheiro `test.py` e' curto, o instinto disse "segredo".

**Fui confirmar o caminho antes de publicar.** `Split-Path -Leaf` tinha-me
escondido o directorio. O ficheiro real era:

```
config/settings/test.py
```

que e' um **modulo de settings de teste** (L51: *"Test database - SQLite in
memory for speed"*), com o comentario **na propria linha**:
*"Chave Fernet fixa p/ testes de criptografia (nunca producao)"*.

**Erro desfazido por confirmacao, nao por sorte.** O `9.md` §A.0 e' exactamente
isto: a linha que parece um achado e' muitas vezes uma linha de teste.

> **Regra que acrescento ao `9.md`:** *antes de reportar um segredo, confirmar
> que o caminho esta dentro da arvore de execucao.* Um segredo em `test.py` e'
> um teste. Um segredo em `base.py` e' um segredo.

---

## 4. O MAPA: lacuna medida -> melhor tecnologia

Ordenado por **produtor exposto**, nao por novidade. Criterio: uma tecnologia
que exija mais manutencao do que a lacuna que fecha, **nao entra**.

### 4.1 CSP: 560 handlers bloqueiam o nonce

**Medido (M):**

| Medida | Valor |
|---|---|
| Handlers `on*=` | **560** em 54 templates |
| Concentrados | `index.html` **131**, `dashboard_appbar.html` 46, `guia-ferramentas.html` 22, `navbar.html` 17 |
| `<script>` sem `src` | **94** |
| `style=` inline | **1117** |

O proprio `base.py:359` ja sabe a resposta:

> `nonce="{{ CSP_NONCE }}"` + `csp.constants.NONCE` em vez…

**Tecnologia:**

| Camada | Ferramenta | Porque |
|---|---|---|
| Politica | **`django-csp` 4.0** | **Ja esta no MIDDLEWARE.** Nao e' adoptar — e' declarar. Ver §2.1 |
| Nonce no template | `csp.constants.NONCE` + tag `{{ CSP_NONCE }}` | `base.py:359` ja aponta para aqui |
| Migracao dos 560 | **`jscodeshift`** | Transforma **AST**, nao regex. Um `onclick="a();b()"` vira um `addEventListener` nomeado. **Nao ha alternativa robusta**: `sed` sobre 560 handlers inline, em 4 linguagens de evento, e' a forma de criar 560 bugs novos |
| Eventos declarativos | **`htmx`** | `hx-on:click` resolve handlers **sem JS inline**, porque o valor vive num atributo. Reduz o numero a migrar em vez de os migrar todos |

**Ordem que recomendo (e o porquê):**

1. **`django-csp` no `requirements.txt` — hoje.** Uma linha. Sem isto, nada
   abaixo importa porque o boot falha.
2. `htmx` nos templates de maior densidade (`index.html`, 131 handlers) — resolve
   por eliminacao, nao por migracao.
3. `jscodeshift` no resto, com `--dry-run` e revisao por template.
4. So entao `script-src 'nonce-...'` estricto, removendo `'unsafe-inline'`.

**Risco de nao fazer:** `'unsafe-inline'` em `script-src` e' a **ausencia** de
CSP. Um `injectou` de `<script>` passa. O `base.py:347` ja o diz:
*"a CSP e' a unica defesa contra XSS injectado, e isto desliga essa…"*.

**Verificacao:** `tests/test_csp.py` ja existe (13 verdes). Falta o **teste que
falha quando reaparece um `on*=`** — o mesmo formato do
`tests/test_webhook_ttn_sem_auth.py`. Um guarda que **nao falha nunca** nao e'
um guarda.

### 4.2 Tenancy: a resposta certa esta bloqueada pela base de dados

**Este e' o ponto onde a medicao muda a resposta.**

O `9.md` §5 mediu que o `TenantIsolationMiddleware` **nao cobre** tarefas
Celery, management commands, e WebSockets — porque sao middleware, e middleware
so corre em HTTP. E pediu (P1-6) *"revogacao dentro da view, nao so no
middleware"*.

**A resposta tecnicamente correcta existe e e' uma so:** **Row Level Security do
PostgreSQL.** Uma politica RLS filtra por `current_setting('app.tenant_id')` e
**nao importa por onde a query entrou** — Celery, `manage.py`, `psql`. E o
middleware deixa de ser a defesa: passa a ser a *performance*.

**Medido (M):** `config/settings/base.py:173`

```python
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")}
```

**A base de dados e' SQLite.** E L176-182 sao `PRAGMA` de SQLite
(`journal_mode=WAL`, `mmap_size=3GB`) — **SQLite nao tem RLS.**

> **Logo: a garantia mais forte que a arquitectura poderia ter, e' hoje
> impossivel, por escolha de base de dados.** Enquanto for SQLite, o
> "isolamento absoluto" que o manifesto §VI vende **nao tem como ser verdadeiro
> fora do caminho HTTP** — e nao por falta de cuidado no codigo.

**Opcoes, com o custo de cada uma:**

| Opcao | Garanteia | Custo |
|---|---|---|
| **A. Migrar para PostgreSQL + RLS** | **Unica que fecha fora de HTTP.** Alem disso, `SELECT ... FOR UPDATE`, `JSONB`, e o `search_path` que ja se ve no L180 | **Alto.** Migra **todas** as migrations. `transaction_mode=IMMEDIATE` e um default de SQLite e tem de ir |
| **B. Um unico chokepoint no ORM** | Fecha Celery e commands **se** tudo passar por ele | **Medio.** Exige um `manager` ou um `QuerySet` base que **exija** `tenant_id`. Nao e' uma opcao, e' um **convenio** que ninguem cumpre sem guarda |
| **C. `active_server` na view, alem do middleware** | Fecha HTTP+Celery que passe pela view | **Baixo.** E' o P1-6 do `9.md`. **Nao fecha `manage.py`** |

**A minha leitura:** **C agora, A como decisao de arquitectura com data.**
`psycopg` **nao esta** instalado (verificado: ausente), e a migracao de um
projecto com 445 ficheiros Python e dados de producao nao e' uma tarefa de
sprint.

> **E o que se escreve no manifesto, seja qual for a opcao:** *"isolamento forte
> e medido, para requests HTTP"* (P1-8 do `9.md`) — **ou** assumes-se
> PostgreSQL e afirma-se RLS **com** `FORCE ROW LEVEL SECURITY`, porque table
> owner **ignora** RLS por omissao. Sem `FORCE`, a politica nao protege o
> proprio owner, e isso e' o tipo de defeito que so se descobre no incidente.

**Ja instalado e subutilizado:** `django-auditlog>=3.0` **esta no
`requirements.txt`.** Ninguem o mencionou em nenhum dos 9 documentos. E' a
ferramenta certa para responder a *"como sabes que este valor nao foi mudado?"* —
que e' a pergunta que o §5 do `9.md` termina sem resposta.

### 4.3 MQTT: a configuracao existe, o cliente nao

**Medido (M):** confirmado o `9.md` §4, sem mudanca.

| Fato | Estado |
|---|---|
| `paho-mqtt` em `requirements*.txt` | **AUSENTE** |
| `mosquitto` / `1883` em `docker-compose.yml` | **ZERO** |
| `docker-compose.telemetry.yml` | tem broker (**overlay** opt-in) |
| `mqtt_listener.py` | `D` (apagado) |
| `mosquitto/` | so `mosquitto.conf` |

**Tecnologia:**

| Necessidade | Ferramenta | Nota |
|---|---|---|
| Broker | **Eclipse Mosquitto** | A config **ja existe**. Falta o broker no compose principal e a politica de password |
| Broker gerido | **EMQX** | Se precise de **cluster** e metricas. Mais pesado, mais caro |
| Cliente Python | **`paho-mqtt`** | A biblioteca canonica. **`pip install paho-mqtt`** |
| Broker na nuvem | **AWS IoT Core** / HiveMQ | Se quiser tirar a operacao das maos. Custo por mensagem |

**O `docker-compose.yml` e' a decisao, nao o broker.** Um broker num overlay
opt-in significa que `docker-compose up` — o comando que qualquer pessoa
corre — **nao levanta telemetria nenhuma**. Ou o broker sobe no compose
principal, ou o §II do manifesto deixa de listar MQTT como runtime.

**Escolha:** Mosquitto no compose principal + `paho-mqtt`, e um `depends_on` com
`condition: service_healthy`. **Nao adoptar EMQX** — e' operacao que o projecto
nao precisa aos 500 utilizadores.

### 4.4 Celery: o motor esta instalado, a task visivel e' um placeholder

**Medido (M):** `celery`, `django-celery-beat`, `django-celery-results`,
`redis`, `channels`, `channels-redis` — **todos instalados**. E o `9.md` §7
mediu `app/tasks.py`: **12 linhas**, `return True`, comentado *"Placeholder for
actual report generation logic"*.

**O `9.md` §7 tem um ponto que merece ser repetido:** *"o README do sistema e'
enganador sobre o que corre onde"*. O motor proativo existe
(`proativo.py:580 avaliar_usuario`). O ficheiro que um leitor abrir para saber
o que o worker faz **nao faz nada**.

**Tecnologia:**

| Lacuna | Ferramenta | Porque |
|---|---|---|
| Saber o que corre | **Celery canvas** (`chain`, `group`, `chord`) | Dependencias entre tarefas ficam **visiveis no codigo**, nao em `if`s. `chord` e' a resposta correcta para "avalia N periodos e consolida" |
| Visibilidade | **`django-celery-results`** — **ja instalado** | Os resultados vao para a BD. `Task.objects.filter(...)` responde a *"esta task correu?"* sem instrumentacao nova |
| Varrer alertas | Manter `amplia.proativo.varrer`, **com revogacao dentro** | O `9.md` §5 mostra que o middleware nao chega ao worker. **A revogacao tem de estar no corpo da task** |
| Nada mais | — | **Nao adoptar Taskiq / Dramatiq / Huey.** O Celery esta instalado e integrado. Trocar de broker e' custo sem ganho |

**Adopcao real:** implementar a primeira task de verdade e escrever o teste que
falha se ela devolver `True` sem fazer nada. `test_placeholder_zero.py` ja
existe para outro ficheiro — **o precedente esta criado.**

### 4.5 Proveniencia: uma fonte da verdade, gerada

**Medido (M):** §2.3 — 5 estados num sitio, 6 no outro, e `str` vs `Enum`.

Isto **nao e' estetica.** Um payload gravado por `proveniencia` com
`simulado` nao valida em `validators`. E `SIMULADO` e' o estado que o
`9.md` §12 aponto como *"o que o documento esquece"*.

**Tecnologia:**

| Opcao | Custo | Nota |
|---|---|---|
| **A. `jsonschema` como fonte, codegen** | Medio | `jsonschema` esta **AUSENTE**. Um `proveniencia.schema.json`, `datamodel-code-generator` gera os dois lados. **Um ficheiro, dois consumidores** |
| **B. Um enum unico partilhado** | Baixo | `proveniencia.Estado` passa a ser a unica definicao; `validators.ESTADOS_FONTE` deriva dele. **Menos elegante, resolve hoje** |
| **C. Um guarda no CI** | Baixo | `test_manifesto_confere_com_o_codigo.py` — o P0-2 do `9.md` §11 |

**Escolha: B agora, C sempre.** A opcao A e' a correcta a prazo e introduz
codegen num projecto que ainda nao tem. **C e' o que impede que isto volte a
divergrir** — e e' o mesmo formato do `test_csp.py`, que o `9.md` §1 classificou
como *"raro e nao obvio"*.

### 4.6 LCDPR: **nao existe biblioteca. E isso e' a descoberta.**

**Verificado hoje (V).** Fui procurar a biblioteca que resolveria o P0 critico e
**nao a encontrei**. O que existe:

| Projecto | Estado | Tem LCDPR? |
|---|---|---|
| **`sped-br/python-sped`** | **ARQUIVADO.** O autor escreveu: *"nao consigo mais mante-lo e portanto estou arquivando este repositorio"* | **NAO.** Modulos: ECD, ECF, EFD-PIS/COFINS, EFD-ICMS/IPI, FCI |
| `PySPED` (PyPI, v1.0.2) | LGPL-v2.1, *"Production/Stable"* | Nao — `nfe`, `nfse`, `cte`, `ecd` |
| `spedpy` (v1.2.3) | MIT, fork | Nao |

> **Isto inverte a recomendacao intuitiva.** Nao ha `sped.rural` para adoptar.
> O `python-sped` principal esta **morto**.

**Logo: o LCDPR do Ampliagro escrito a mao nao e' preguiça - e' ausencia de
alternativa.** E o que o `4.md` §20 mediu ja ganha adimensionamento correcto:
havia **tres** geradores, porque nao ha biblioteca a importar.

**Actualizacao 2026-10-04:** os tres foram **reduzidos a um** por delegacao
(`lcdpr_export.py` chama `_formatar_valor`), e ha teste de regressao. A
duplicacao de implementacao **esta resolvida**. O que continua aberto e' o
**validador real da Receita**, que nunca foi executado.
**O que fazer, entao:**

| Lacuna | Ferramenta | Estado |
|---|---|---|
| **Conformidade** | **Validador oficial da Receita** | **[N]** Nao instalado, nunca executado. **E' a unica prova que importa** |
| **Deriva do leiaute** | **Schema-driven**: `jsonschema` + um `lcdpr.schema.json` versionado por versao do Leiaute | `jsonschema` AUSENTE |
| **Regressao** | **`hypothesis`** | **AUSENTE.** Property-based testing sobre um ficheiro `|`-delimited: *qualquer* valor monetario tem de sair com ponto e 2 casas |
| **Um gerador so** | **JA RESOLVIDO** (2026-10-04) | Havia **tres**; `lcdpr_export.py` passou a **delegar** em `_formatar_valor`. Regressao travada por `tests/test_lcdpr_leiaute.py:62` |
| `0045`, Bloco Z | **Especificacao RFB**, nao biblioteca | [N] nao verificados contra a versao oficial |

**Assinatura:** o LCDPR e' **texto plano `|`-delimited**, nao XML. Portanto
`pyhanko`/`signxml` (XML/DSig, para NF-e) **nao se aplicam** — e' a resposta
errada a uma pergunta que ninguem fez. O que serve: uma assinatura **detached**
de um digest, sobre o conteudo, com `cryptography` **ja instalada**.

**Por que `hypothesis` e' o item de maior valor aqui:** o bug do
`.replace(".", ",")` **ja tem teste de regressao**
(`tests/test_lcdpr_leiaute.py:62`, com `Decimal("1234.56")`). **Esse bug
concreto esta coberto.** O que `hypothesis` traria e' a **classe**: um teste de
exemplo fixo prova que `1234.56` sai bem; `hypothesis` gera `0.005`, `-0.01`,
`1e6`, `999999999.99`, `Decimal("1E+2")` e encontra o resto dos mesmos erros de
arredondamento e separador — **incluindo os que ninguem pensou ainda**.

Ou seja: o teste de regressao e' a **rede**; `hypothesis` e' o **sensor que
ve a rede toda**. Nao substitui o primeiro — ve-se que ja existe. Complementa-o.

> **E aqui esta o meu erro de §3, outra vez.** Escrevi que o bug medido no
> `4.md` §20 era `.replace(".", ",")` num float. Era — mas **eu tinha-o lido
> numa docstring**, e o bug ja estava corrigido. Se tivesse aberto a linha como
> abri ao verificar o `test.py`, teria escrito *"ja covered"*. **Tres passages
> no mesmo documento, o mesmo padrao:** o `grep` devolve uma linha, e eu assumo
> que a linha e' o que o `grep` casa.

### 4.7 NF-e / MDF-e: aqui a biblioteca existe, e e' boa

**Medido (M):** 0 hits para `SEFAZ` e `MDFe`. Nenhuma integracao.

**Verificado hoje (V):** **PyNFe** — LGPL-3.0, activo, cobre **NF-e 4.00**,
NFC-e, NFS-e e **MDF-e**, com contingencia, consulta de status, protocolo,
cancelamento, carta de correccao e **manifestacao do destinatario**. E' a
biblioteca brasileira de referencia parawebservices da SEFAZ.

**Escolha: PyNFe.** Alternativas (`nodrime`, `python-nfe`) sao so o mesmo
protocolo com maintainers a menos.

**Custo, e e' o que ninguem escreve:** PyNFe fala **SOAP/XML**, e isto obriga a
**certificado digital ICP-Brasil** por produtor. O `4.md` §16 mediu
`ICP_Brasil` = **0 ficheiros**. **Nao e' um bug — e' o que torna o offline
necessario:** o Ampliagro tem de ser o que **faz a reconciliacao** (lê a
nota), **nao** o que **emite** a nota. Emissao e' do Aegro, com o certificado
dele. **Esta e' a fronteira que mantem o secao 4 nao implementavel e o
produto viavel ao mesmo tempo.**

**Prioridade: BAIXA.** Nao inverte o eixo do produto. So fechar depois do LCDPR.

### 4.8 Offline / Caderno: Dexie sobre IndexedDB cru

**Contexto:** o `4.md` mediu que o offline esta relacionado ao swipe, e ha
`workbox-window` e `vite-plugin-pwa` **instalados**.

| Opcao | Quando |
|---|---|
| **`Dexie.js`** | **Escolha.** 30 KB, tipada, IndexedDB semIndexes documentados. O Caderno sao objectos simples com consultas por `[propriedade+tipo]` |
| `RxDB` | Quando precisar de **replicacao** embutida. Pesa mais, e o sync do Caderno tem regras de conflito que dependem do dominio |
| `idb` | A lib minima. Suficiente, mas reescrever indices a mao |

**Nao adoptar agora:** o ganho do Dexie e' real mas o blocker **nao e' a lib** —
e' `test_sync_offline.py` a falhar por um dump ausente. **Fixar o dump primeiro.**

### 4.9 Lint: ESLint + Prettier + plugin, tres ferramentas que se brigam

**Medido (M):** `package.json` tem `eslint@9`, `prettier@3`,
`eslint-plugin-prettier@5`, `eslint-config-prettier@9`, **juntos**. E
`eslint-config-prettier` existe **exatamente para desligar as regras de
formatação do ESLint** — que e' o que `eslint-plugin-prettier` volta a ligar.

**Opcoes:**

| Ferramenta | Nota |
|---|---|
| **Manter as tres** | Funciona. E' o que ha. Nao mexer sem ganho |
| **`Biome`** | Rust, **10-100x** mais rapido, linter+formatter num binario, **e tem suporte de HTML**. **Acelera a migracao dos 560 handlers** porque formata HTML e JS no mesmo passo |
| `oxlint` | Rust, linter so. Corre em fase com o ESLint — bom como `eslint --fix` |

**Escolha: `Biome`**, se e' que se toca. **Com uma condicao:** so depois da
CSP estar estrita (§4.1), porque **o formatter vai mexer nos 560 handlers** e
a ordem importa. Migrar handlers e formatar ao mesmo tempo torna o
`jscodeshift` impossivel de rever.

### 4.10 Segredos: o padrao certo ja esta no sitio certo

**Medido (M):** `config/settings/test.py:49` — chave Fernet fixa em settings de
teste, comentada *"nunca producao"*. **Isto e' o padrao correcto:** um valor
fixo em `test.py`, o valor real em `env`.

**Falta:**

| Onde | Falta | Ferramenta |
|---|---|---|
| `AMPLIAGRO_DATA_KEY` | **nao existe em producao** (`base.py`, `dev.py`, `prod.py` nao o tem) | **`age`** ou **SOPS**: chave de encriptacao num ficheiro versionado, valor em variavel de ambiente |
| Segredos de deploy | nenhuma revisao de "esta chave e' de teste?" | `detect-secrets` / `gitleaks` em pre-commit |

**Precedente do projecto:** `config/settings/base.py:184-187` tem
`IA_LOCAL_KEY = env.str(...)` com o comentario *"a chave so pode agir pelos
user IDs listados aqui"*. **O padrao existe. Falta e' `AMPLIAGRO_DATA_KEY`.**

### 4.11 Documentacao que diverge do codigo: um teste, nao um plano

O `9.md` §12 da a recomendacao que eu aceito sem reserva:

> *"a proxima versao deste manifesto nao precisa de mais capacidade. Precisa de
> `grep` de cada afirmacao contra o codigo, e de um teste que corra essa
> verificacao no CI."*

**Tecnologia:** um teste que afirme que o documento e o codigo concordam. **Este
projecto ja tem esse padrao** — `test_csp.py` (a politica nos settings tem de
coincidir com o que o HTML pede), `test_placeholder_zero.py` (trava o zero
inventado), `test_manifesto_confere_com_o_codigo.py` (ja citado no `9.md`).

**Regra nova:** *"nenhum 'OK' sem a linha lida"* + *"nenhum segredo sem o
caminho confirmado"*. **A segunda regra foi aprendida nesta sessao, custa uma
confirmacao, e teria evitado um achado falso.**

---

## 5. OS TRES QUE VALEM A PRIMEIRA SEMANA

Ordenados por produtor exposto, nao por esforco.

### P0-1 — `django-csp` no `requirements.txt`
**1 linha.** Sem isto o boot falha numa maquina limpa. (§2.1)

### P0-2 — `paho-mqtt` + Mosquitto no compose principal
**2 ficheiros.** Ou o broker sobe, ou o §II do manifesto deixa de dizer MQTT. (§4.3)

### P0-3 — `hypothesis` e a validador da RFB
**E' o unico item desta lista que pode ser declarado "feito" com prova.** Sem o
validador, o P0 do `4.md` §20 continua sendo um palpite sobre o ficheiro. (§4.6)

---

## 6. O QUE EU **NAO** VERIFIQUEI

- **Nao executei o validador da Receita.** Todo o §4.6 e' raciocinio sobre
  formato, **nao** prova de aceitacao.
- **Nao medi** `psycopg` na base alem da ausencia. **Nao** testei migracao para
  PostgreSQL. A opcao A do §4.2 e' um plano, nao uma estimativa.
- **Nao medi** a latencia de `jscodeshift` nos 560 handlers. **Nao** o corri em
  modo `--dry-run`.
- **Nao abri conta em nenhum sistema.** Nenhum preco neste documento. [N]
- **Nao medi** a taxa de classificacao NCM. O `4.md` §21 ja tinha marcado.
- **Nao compilei nem testei** nenhuma das recomendacoes deste documento. **Este
  e' um mapa, nao um patch.**
- **Nao medi** se o CI esta presently broken por causa do §2.1. Verifiquei que o
  manifesto **nao declara** a dependencia; se o CI passa, e' porque instala de
  outra forma.
- **Ja medi errado uma vez** (§3). Por isso: **re-verificar antes de decidir,
  como o `9.md` §0 manda.**

---

## 7. Fontes

| Fonte | Uso |
|---|---|
| `docs/sistema/9.md` | Metodo (§A.0), §2, §3, §4, §5, §7, §8, §11 |
| `docs/sistema/4.md` | §16 medidos, §18 checklist, §20 LCDPR (corrigido) |
| `github.com/sped-br/python-sped` | **ARQUIVADO** — sem modulo rural |
| `github.com/TadaSoftware/PyNFe` | LGPL-3.0, NF-e 4.00, MDF-e, contingencia |
| pypi.org/project/PySPED | v1.0.2, LGPL-v2.1 — sem LCDPR |
| Receita Federal, Leiaute LCDPR 1.3 | [N] **nao lida na fonte primaria nesta sessao** |

---

## 8. A TESE DESTE DOCUMENTO

O `9.md` §12 escreveu:

> *"o documento descreve o sistema que este projecto **quer** ser, com a
> confianca de quem descreveu o que **e**."*

**A leitura pelo lado da tecnologia inverte metade disso.** Numa passagem pelo
`requirements.txt`:

| O que a arquitectura precisa | Estado |
|---|---|
| `django-csp` — a defesa principal contra XSS | **instalada, nao declarada** |
| `paho-mqtt` — a telemetria | **ausente** |
| `psycopg` — o isolamento forte | **ausente** |
| `hypothesis` — a prova do ficheiro do fisco | **ausente** |
| `jsonschema` — a fonte unica | **ausente** |
| `cryptography` — a telemetria cifrada | **instalada, usada por outro caminho** |

**Cinco ausencias, um padrao:** as dependencias **de-development** nao estao
declaradas. O que corre em producao esta instalado; o que **provaria** as
afirmacoes, nao esta.

> **E esta e' a razao pela qual o `9.md` §0 e' o achado mais importante dos
> dois documentos.** A `python-sped` arquivada e' o exemplo perfeito: **a
> biblioteca que resolvia o P0 critico do `4.md` §20 morreu, e o `requirements.txt`
> nao a.chama porque nunca a teve.** A integracao com tecnologia *"boa"* nao e'
> aqui: e' a que **esta escrita no manifesto e esta declarada no ficheiro de
> dependencias.**

**Tres accoes, por ordem:**

1. `django-csp` no `requirements.txt`. **Uma linha. Hoje.**
2. `paho-mqtt` + broker no compose principal, **ou** §II deixa de dizer MQTT.
3. Correr **uma vez** o validador da Receita sobre o LCDPR, e escrever o
   resultado no `4.md` §20. **E o unico item desta lista que fecha uma pergunta
   em vez de a mover.**

---

> **Nota para a mesclagem:** este documento **nao substitui** o `9.md`. O
> `9.md` mede o registo — o que esta prometido e o que o registo nao cobre. Este
> mede a **corrente** — o que esta declarado e o que corre. Um mede a promessa, o
> outro mede a dependencia. **Os dois assinam a mesma frase:** *a parte que se
> apresenta como fundacao e' a que nao foi verificada.*
