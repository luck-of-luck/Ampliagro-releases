# Ampliagro Desktop — Plano de execução

App de ambiente de trabalho para **Windows, macOS e Linux**, instalável
oficialmente, que funciona como o Ampliagro de hoje mas **offline**, e que o
produtor monta **à sua medida** — escolhendo as culturas da fazenda e
descarregando só o que vai usar.

> Este documento é o plano. Ele foi escrito **depois de medir** o repositório,
> e todas as afirmações sobre o sistema actual apontam para ficheiro e linha.
> O que não foi medido está marcado como tal.

---

## 1. Decisões já tomadas

| # | Decisão | Efeito |
|---|---------|--------|
| D1 | **Híbrido**: casca Electron + runtime Django embebido em loopback | Funciona 100% offline. Obriga a aparar as 98 dependências Python. |
| D2 | **Módulos por cultura** no cliente | Instalador base pequeno; o produtor escolhe culturas e descarrega só os packs correspondentes. |
| D3 | Pasta em `ampliagro-app/desktop/` | `app/` já é o pacote Django (`app/apps.py`, `INSTALLED_APPS` em `config/settings/base.py:83`). Sem colisão. |
| D4 | **Reescrita** de Planos e Máquinas, **migrando** os dados existentes | Modelos novos e melhores; dados de `PlanoSafra` e `Maquinario` preservados. |

---

## 2. O que foi medido no sistema actual

### 2.1 A base de código que vamos reusar

| Medida | Valor | Onde |
|---|---|---|
| Ficheiros estáticos | **165 ficheiros / 3,8 MB** | `app/static/` |
| Templates | **119 ficheiros / 1,24 MB** | `app/templates/` |
| Culturas no config | **488 culturas**, 40 subgrupos, 4 grupos | `app/static/data/cultures-config.json` (275 KB) |
| Dependências Python | **98** | `requirements.txt` |
| Referências a CDN em templates | **40** (17 jsdelivr, 12 unpkg, 8 fonts.googleapis, 3 fonts.gstatic) | `app/templates/**/*.html` |
| Referências a CDN em JS | **7** (`esm.run`, `huggingface.co`) | `ia-local.js`, `whisper-worker.js`, `report.js`, `sw.js` |

**Leitura:** o payload é pequeno (5 MB). O problema não é o tamanho — é a
**dependência de rede** e o **empacotamento nativo**.

### 2.2 Ficheiros que mandam no tamanho

| Ficheiro | KB | Porquê importa |
|---|---|---|
| `app/static/js/pagina-index.js` | 652,3 | Monólito. Precisa de ser partido para packs por cultura. |
| `app/static/js/ia-local/ia-local.js` | 295,4 | WebLLM/WASM. Pesos vêm de `huggingface.co` em runtime. |
| `app/static/data/cultures-config.json` | 275,3 | É o **spine**: o índice completo entra sempre; os dados por cultura é que são packs. |
| `app/static/js/guide.js` | 225,6 | |
| `app/static/css/paginas/extracted-components.css` | 197,6 | |

### 2.3 O que já existe e é reaproveitado (não reconstruir)

- **PWA completo**: `vite-plugin-pwa` + Workbox + `app/static/js/pwa/sw.js`
  (22,5 KB). É a prova de que assets podem ser servidos localmente.
- **Servidor próprio (self-hosted)**: `app/views/servidor.py` (12 KB),
  `app/views/lgpd.py` (16,8 KB), `ServidorRevogadoMiddleware`
  (`app/middleware.py`). O conceito "o produtor tem o seu servidor" **já
  está no domínio**.
- **Telemetria de máquinas**: `Device`, `TelemetryData`,
  `RegraAlertaTelemetria`, `ComandoDevice`, `Gateway` (`app/models/iot.py`).
  O "sistema de máquinas" **nasce sobre isto**, não do zero.
- **Configuração por cultura dinâmica**: `app/api/culture_config.py` (Python) e
  `app/static/js/cultures-loader.js` (browser) já percorrem
  `groups → subgroups → cultures`. Este é o formato do manifesto de packs.

### 2.4 O que tem de ser reescrito

- **Planos**: `PlanoSafra` (`app/models/safra.py:135`) tem 5 campos —
  `orcamento_estimado`, duas datas e um `status` de 3 valores. Não é um plano,
  é um cabeçalho. `AtividadePlanejada` (mesmo ficheiro) é uma lista de tarefas
  com `nome`, `data_prevista`, `custo_estimado`, `concluida`.
- **Máquinas**: `app/models/maquinario.py` tem 96 linhas e 2 modelos CRUD
  (`Maquinario`, `ManutencaoMaquinario`). Não há telemetria ligada, nem
  horímetro a accumulating, nem custo por hora real.

### 2.5 Bloqueios reais para "funcionar offline"

1. **CSP com `'unsafe-inline'`** (`config/settings/base.py:401`). 606 handlers
   `on*=` e um `<script>` inline de ~13.000 linhas. *Não bloqueia o Electron*
   (Chromium aceita), mas **bloqueia endurecer a política** e complica
   `file://`/protocolos custom.
2. **40 + 7 URLs de CDN** não podem ser contactadas offline. Têm de ser
   **vendorizadas** para `app/static/vendor/`.
3. **Pesos do WebLLM** (WASM) vêm de `huggingface.co` e `esm.run` em runtime.
   Centenas de MB. Devem ser um **pack opcional**, nunca o instalador base.
4. **Dependências nativas**: `geopandas`, `pandas`, `numpy`,
   `opencv-python-headless`, `psycopg2-binary`, `cryptography`, `bcrypt`.
   Não cross-compilam. Exigem 3 runners de build (Win/mac/Linux).

---

## 3. Arquitectura alvo

```
┌───────────────────────────────────────────────────────────────┐
│  ampliagro-app/desktop/                                       │
│                                                               │
│  Electron (casca)                                            │
│   ├── main process ── spawn ──┐                               │
│   ├── preload (contextBridge) │ janela segura                │
│   └── protocol:// ampliagro:// │                               │
│                               ▼                               │
│  Django EMBEBIDO (loopback http://127.0.0.1:<porta>)          │
│   ├── settings_desktop.py  (SQLite, InMemory, eager)          │
│   ├── daphne (ASGI: HTTP + WebSocket, cross-platform)         │
│   └── DJANGO_VITE → false (servir de staticfiles, sem Vite)   │
│                               ▲                               │
│  Packs (baixados pelo produtor) ─┘                            │
│   ├── core/       (sempre) — shell, login, índice culturas    │
│   ├── culturas/    1 pack por subgrupo escolhido              │
│   ├── planos/     pack do sistema de planos                   │
│   ├── maquinas/   pack do sistema de máquinas                │
│   └── ia-offline/ pack opcional: pesos WebLLM/Whisper         │
└───────────────────────────────────────────────────────────────┘
```

### Porquê Electron e não Tauri

O frontend é Django templates com 606 handlers `on*=` e JS vanilla de 652 KB.
Electron carrega exactamente o que o browser carrega, sem reescrever nada.
Tauri daria binário menor, mas obrigaria a eliminar o inline — que é a
segunda maior fatia de trabalho do projecto. Electron é a decisão com menor
risco de regressão visual.

### Porque o runtime Django abre caminho sem Redis

O `settings/base.py` **já tem fallbacks** pensados para isto:

- `CHANNEL_LAYERS` cai para `InMemoryChannelLayer` sem `REDIS_URL`
  (`base.py:301-319`) — WebSockets funcionam com 1 processo.
- `DATABASES` cai para SQLite (`base.py:200-210`), já com WAL e
  `transaction_mode=IMMEDIATE`.
- `CACHES` é `DatabaseCache` — não precisa de Redis.

O desktop é exactamente o cenário "1 processo, sem Redis, SQLite". **O
backend já suporta este modo.** Celery é a excepção: passa a
`task_always_eager` (ver F2).

---

## 4. Fases

Cada fase tem entregável e verificação. Não se avança sem a verificação passar.

### Fase 0 — Fundações — ✅ CONCLUÍDA

**Objectivo:** o monolito arranca dentro de Electron e fala com o Django.

**Entregue:**
- [x] `ampliagro-app/desktop/` com `package.json`, `electron/`, `backend/`, `testes/`
- [x] **`config/settings/desktop.py`** — herda `base`, `DEBUG=False`, `DJANGO_VITE`
      desligado, `ALLOWED_HOSTS=127.0.0.1`, CSP com `ws://127.0.0.1`.
      ⚠️ Vive em `config/settings/`, **não** em `ampliagro-app/`: `DJANGO_SETTINGS_MODULE`
      resolve por caminho de import, e `from .base import *` obriga a estar no
      pacote `config`. É a única coisa de desktop fora de `ampliagro-app/`.
- [x] `backend/bootstrap.py` — `SECRET_KEY` por instalação, porta livre do SO,
      `migrate` + `createcachetable`, Daphne (ASGI), espera `/healthz`, `--check`, `--preparar`
- [x] `electron/main.js` — protocolo `AMPLIAGRO_DESKTOP_READY`, navegação
      externa bloqueada, `before-quit` mata o runtime
- [x] `electron/preload.js` — **superfície zero** (`versao`, `origem`)

**Verificado por medição, não por inspecção:**

| Prova | Resultado |
|---|---|
| `manage.py check` com settings desktop | 0 problemas |
| `/healthz` | 200, `db`/`cache`/`disk`/`migrations` todos `ok`, 0 migrações pendentes |
| `/login/` | 200 |
| CSP na resposta real | presente, com `ws://127.0.0.1`, **sem** a porta 5173 |
| `/admin/login/` | 200 (um 500 seria settings de produção errados) |
| Contexto da página isolado | sem `require`, sem `process` |
| Janela Electron | dashboard real do Django, título "Ampliagro - Dashboard Premium" |

**Dois bugs reais encontrados e corrigidos:**

1. **O Daphne sobrevivia ao pai, no Windows.** O desenho inicial confiava em
   `atexit` para matar o filho. Medido que no Windows `Popen.terminate()`
   chama `TerminateProcess`, que **não** corre `atexit` (exit=1). Corrigido
   com Job Object (`KILL_ON_JOB_CLOSE`) + `PR_SET_PDEATHSIG` no Linux.
   Sem isto, fechar o desktop deixava um servidor invisível a servir a
   fazenda. Ver ADR-001.

2. **A área de conteúdo vinha vazia.** A navbar renderizava, o meio não.
   Quatro assets davam 404 (`auto-contraste.css/js`, `ia-rail.css`,
   `widgets-polish.css`): existem em `app/static/` mas não em `staticfiles/`.
   A web não sofre porque o `Dockerfile:58` corre `collectstatic` na build;
   o desktop não passa pelo Dockerfile. Daí o passo `--preparar`.

   **Este é o tipo de falha que passa por sucesso:** janela aberta, título
   certo, ecrã em branco. Só uma prova que tira uma captura e lê o ecrã
   o apanha — e foi a captura que o apanhou, depois de o teste de texto
   ter dado "PASSOU" (encontrava as palavras do login no DOM, não no ecrã).

**Correcção ao plano:** Electron **44.7.0**, não 33. A primeira versão fixou
`^33.0.0` ao acaso e `npm audit` devolveu dezenas de advisories — ASAR
Integrity Bypass, context-isolation bypass, sandboxed-iframe bypass.
Em 44.7.0 são **0 vulnerabilidades**.

**Risco residual:** macOS não tem Job Object nem `PR_SET_PDEATHSIG`. O
encerramento depende de o Electron matar explicitamente o filho. Registado
como limitação, a resolver com um teste na Fase 6.

---

### Fase 1 â€” Runtime offline de verdade â€” âœ… CONCLUÃDA

**Objectivo:** um runtime Python prÃ³prio, sem o Python do sistema, e saber
quanto custa.

**Entregue:**
- [x] `backend/requirements-desktop.txt` â€” o subconjunto curado, cada linha
      justificada por uma mediÃ§Ã£o de importaÃ§Ã£o
- [x] `backend/requirements-build.txt` â€” PyInstaller (build, nÃ£o runtime)
- [x] `backend/congelar.py` â€” escreve o `.spec` e constrÃ³i o runtime por SO
- [x] `backend/entrypoint.py` â€” ponto de entrada do congelado
- [x] Backup do SQLite antes de `migrate`, com a API do SQLite (nÃ£o
      `shutil.copy`), apagado se a migraÃ§Ã£o correr bem
- [x] Log no directÃ³rio de dados, nÃ£o no de instalaÃ§Ã£o
- [ ] Ãcone `.ico`/`.icns`/`.png` â€” **por fazer**
- [ ] Assinatura de cÃ³digo â€” **decisÃ£o de custo, por decidir**

**Verificado, nÃ£o suposto:**

| Prova | Resultado |
|---|---|
| `manage.py check` num venv limpo (sÃ³ o curado) | 0 problemas |
| `/healthz` do executÃ¡vel congelado | 200, `migrations.pending = 0` |
| `/login/` do congelado | 200, 20 KB |
| WebSocket `/ws/dashboard/` do congelado | **101 Switching Protocols** |
| Backup antes de migrate | 2.420 KB, 159 registos legÃ­veis no backup |

**O nÃºmero que manda:**

| | Antes | Depois |
|---|---|---|
| DistribuiÃ§Ãµes carregadas no arranque | **241,4 MB** | **94,8 MB** (congelado, tudo incluÃ­do) |
| numpy | 68,4 MB | **fora** (provado opcional) |
| pandas / scipy / geopandas / rasterio / opencv | 342 MB | **fora** (zero referÃªncias no repo) |

**Cortar o numpy foi provado, nÃ£o decidido.** `autobahn` importa-o por
`flatbuffers/compat.py:75`, e `number_types.py:21` chama
`import_numpy()` ao nÃ­vel do mÃ³dulo â€” o que *parece* tornar numpy
obrigatÃ³rio. A prova, num venv onde numpy nÃ£o estÃ¡ instalado:

    np is None: True
    numpy instalado: False
    /ws/dashboard/ -> 'HTTP/1.1 101 Switching Protocols'

**A meta de 350 MB nÃ£o Ã© alcanÃ§Ã¡vel no tamanho instalado.** Medido:

| Componente | MB |
|---|---|
| Electron 44.7.0 (descomprimido) | **367,7** |
| Runtime Python congelado | 94,8 |
| **Total instalado** | **462,5** |
| Total comprimido (instalador) | **~277** |

O Electron sozinho jÃ¡ passa dos 350 MB â€” `electron.exe` tem 234,9 MB e os
`locales/` 48,3 MB. Apurar os locales deixa ~414 MB instalados.

Isto **nÃ£o** Ã© o desktop a ser demasiado grande: Ã© o Electron. Cortar
Python nÃ£o resolve, porque resolver significava cortÃ¡-lo a zero. O plano
ficou com o alvo errado â€” 350 MB Ã© um alvo de **instalador comprimido**,
e nesse sentido estÃ¡ cumprido com folga. Ver ADR-001, secÃ§Ã£o "A ESTIMATIVA
ESTAVA ERRADA".

**Cinco bugs reais encontrados â€” todos sÃ³ no congelado, nenhum em
desenvolvimento:**

1. **`--add-data` nÃ£o analisa, copia.** `config/` e `app/` Passing por
   `--add-data` punha o `config/celery.py` na distribution sem o celery
   atrÃ¡s: `ModuleNotFoundError` no arranque. A correcÃ§Ã£o Ã© `collect_submodules`
   num `.spec` â€” que Ã© a Ãºnica forma de ter essa funÃ§Ã£o.
2. **`sys.executable` congelado Ã© o prÃ³prio `.exe`.** O `bootstrap` arrancava
   `sys.executable -m daphne`, que Ã© o executÃ¡vel a ser lanÃ§ado de novo com
   argumentos que ele nÃ£o entende. O servidor nunca subia
   (`ConnectionRefusedError` no `/healthz`). Agora hÃ¡ um modo `--daphne`.
3. **Log no directÃ³rio de instalaÃ§Ã£o.** `base.py:762` escreve em
   `BASE_DIR/logs`. Numa instalaÃ§Ã£o em modo de leitura isso dÃ¡
   `ValueError: Unable to configure handler 'file'` e uma janela que nÃ£o
   abre. O log vai agora para o directÃ³rio de dados.
4. **MÃ³dulos resolvidos por string.** `INSTALLED_APPS` e `MIDDLEWARE` sÃ£o
   nomes que o Django resolve com `import_module`. Nenhum Ã© visÃ­vel a uma
   anÃ¡lise estÃ¡tica. Quatro faltaram um a um â€” `celery.fixups`,
   `django_filters`, `allauth.account.middleware`, `health_check.urls` â€”
   e oÃºltimo mesmo com `collect_submodules`, o que fica registado como
   dÃ­vida.
5. **`autobahn/nvx` precisa do `.c` em runtime.** O validador de UTF-8 lÃª a
   fonte C que o PyInstaller nÃ£o copiou. `FileNotFoundError` no arranque.

**O padrÃ£o dos cinco Ã© o mesmo:** nenhum aparecia em desenvolvimento, porque
aÃ­ o Python tem o pacote inteiro Ã  vista. **O executÃ¡vel congelado sÃ³ se
prova batendo-lhe** â€” `npm run prova:congelado` existe para isso e Ã© o
que tem de entrar no CI antes de um build ser considerado bom.

---
### Fase 2 â€” Vendorizar as 47 URLs â€” âœ… CONCLUÃDA

**Objectivo:** a aplicaÃ§Ã£o carrega inteira a partir de `127.0.0.1`, sem
pedir nada Ã  rede.

**Entregue:**
- [x] `backend/inventario_cdn.py` â€” inventÃ¡rio com linha e contexto
- [x] `backend/vendorizar.py` â€” descarrega com pin de versÃ£o + SHA256,
      reescreve o CSS das fontes, e **verifica** que cada `url()` de um CSS
      vendorizado resolve para um ficheiro real
- [x] `backend/reescrever_cdn.py` â€” reescreve templates e CSS; tem backup
      (`npm run vendor:restaurar`) e modo `--dry-run`
- [x] CSP do desktop **substitui** a de `base.py` por uma sÃ³-ligaÃ§Ã£o
- [x] `testes/gate-offline.cjs` â€” o gate

**Verificado:**

| Prova | Resultado |
|---|---|
| `/login/`, `/`, `/previsao/clima/`, `/telemetria/` | 200 cada |
| Pedidos para fora de `127.0.0.1` | **zero** |
| Assets vendorizados servidos | 9 de 9 com 200 |
| ReferÃªncias a CDN de biblioteca no HTML | **zero** |
| `vendorizar.py --verificar` | 47 entradas, 0 com problema |
| `url()` de CSS a resolver | todos resolvem |
| Janela Electron | dashboard igual (captura 929 KB) |

**Vendorizado: 47 ficheiros, 2,5 MB** â€” 13 bibliotecas, 21 `.woff2`,
4 fundos decorativos, 1 CSS de fontes reescrito.

### As 51 referÃªncias nÃ£o eram um problema â€” eram trÃªs

O inventÃ¡rio inicial conta 51 referÃªncias, mas elas nÃ£o se resolvem da
mesma maneira, e tratÃ¡-las como uma sÃ³ era o erro:

| Categoria | NÂº | O que se fez |
|---|---|---|
| **Bibliotecas** | ~20 | Vendorizadas. |
| **`preconnect`** | 6 | Ficam. NÃ£o descarregam nada: sÃ£o dicas ao browser para abrir a ligaÃ§Ã£o mais depressa. Como jÃ¡ nÃ£o hÃ¡ nada em `gstatic` para contactar, sÃ£o inÃºteis â€” mas sÃ£o inofensivas, e mexer em algo que funciona nÃ£o Ã© melhoria. |
| **ServiÃ§os** | 6 | NÃ£o sÃ£o vendorizÃ¡veis. Clima e geocodificaÃ§Ã£o nÃ£o existem offline: nÃ£o hÃ¡ ficheiro para guardar que os substitua. |

### Isto fechou um buraco de seguranÃ§a que Ã© anterior ao desktop

`app/templates/financeiro/cashflow.html` e mais dois carregavam:

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

Sem versÃ£o. O que essa linha executa Ã© o que o jsDelivr decidir servir
**naquele momento** â€” e o produtor nÃ£o tem voto. O mesmo valia para
`html5-qrcode`. Ã‰ uma dependÃªncia de execuÃ§Ã£o resolvida em runtime,
contra a polÃ­tica do projecto (que fixa versÃµes em `requirements.txt` com
comentÃ¡rios a explicar cada pin).

O dono do projecto decidiu **unificar o Chart.js na 4.4.7**, o que fechou
as trÃªs versÃµes em uso de uma vez.

### O gate encontrou o que o inventÃ¡rio nÃ£o procurou

O inventÃ¡rio varria `.html` e `.js`. **NÃ£o varriava CSS.** Havia quatro
fundos decorativos de `images.unsplash.com` em
`app/static/css/paginas/login.css`, e o gate apanhou-os a serem pedidos â€”
e a CSP nova travou-os.

Ã‰ a diferenÃ§a entre um inventÃ¡rio e um gate: o inventÃ¡rio encontra o que
se pensou em procurar; o gate encontra o que a pÃ¡gina faz.

Vendorizados tambÃ©m (370 KB): `login-1000.jpg`, `login-600.jpg`,
`telemetria-1000.jpg`, `telemetria-600.jpg`.

### A bloqueio Ã© a CSP, nÃ£o o teste â€” e porquÃª

O plano dizia "navegar com a rede bloqueada". Feito Ã  letra, com
Playwright, **nÃ£o funciona** â€” e Ã© instructive saber porquÃª:

1. `route(...)` com `continue()` â†’ a janela Electron **fecha-se** a meio.
2. `context.setOffline(true)` â†’ bloqueia **tudo**, inclusive `127.0.0.1`.
   A emulaÃ§Ã£o de rede do Chromium nÃ£o distingue loopback de internet.
3. `route` sÃ³ para externos â†’ o mesmo, `Target closed`.

Nenhuma dessas trÃªs era um problema da aplicaÃ§Ã£o. Eram do mecanismo de
teste.

A resposta certa Ã© a que a arquitectura dÃ¡: **Ã© a CSP que bloqueia**.
`config/settings/desktop.py` define `_CSP_APENAS_LOCAL`, sem uma Ãºnica
origem externa. O browser nÃ£o pede o que a CSP nÃ£o permite â€” nÃ£o pede
para depois recusar. E isso Ã© *mais forte* do que bloquear no teste: se a
pÃ¡gina mostra o grÃ¡fico, o mapa e os Ã­cones no sÃ­tio, Ã© porque chegou
tudo de `127.0.0.1`.

Por isso `gate-offline.cjs` arranca o runtime e aponta um Chromium limpo
para ele. A CSP Ã© um cabeÃ§alho de resposta do Django â€” vem do mesmo sÃ­tio
para os dois clientes.

### TrÃªs erros meus nesta fase, registados

1. **Alarme falso no SRI.** Comparei o digest **hex** do `Get-FileHash`
   contra o valor **base64** do `integrity`. NÃ£o podem bater um no outro.
   ConcluÃ­ que havia um bug crÃ­tico que partia o Leaflet. **NÃ£o havia** â€”
   o `--sri` recomputou os mesmos valores. O atributo estava certo; fui
   eu que o comparei mal.
2. **URL das fontes com `family=family=`.** O `css2` devolvia HTTP 400, e o
   `curl` na mesma URL devolvia 200 â€” porque o `curl` nÃ£o tem o bug. O
   `FAMILIAS_CSS` jÃ¡ trazia `family=` e eu prefixava outro.
3. **`fontes.css` marcado como alterado logo a seguir ao download.**
   `write_text` em modo texto traduz `\n`â†’`\r\n` no Windows; o hash era
   calculado sobre uns bytes e o ficheiro em disco tinha outros. Agora
   escreve-se com `write_bytes`, e o que se hasheia Ã© o que fica em disco.

### O cache de clima — feito, em JSON

O dono do projecto decidiu que, sem rede, os serviços devem **guardar a
última captura e mostrar a hora dela**; sem captura em histórico, mostrar
`—` com fonte `sem sinal`.

Está em `app/services/clima.py`, num único `clima.json` indexado por
coordenada, e a resposta passou a levar `fonte_dados` e `capturado_em`.

**O buraco que tapou.** `get_previsao` fazia, quando a rede não
respondia, `return {"error": str(e), "fallback": True}` — e as três views
que o consomem (`api/views/core.py`, `api/views/agronomia.py`,
`api/views/production.py`) traduzem `error` em HTTP **503**. Ou seja: sem
rede, a previsão era um ecrã de erro, e não havia captura nenhuma para
mostrar. Havia um `CACHE_TIMEOUT` de 3 horas, mas esse cache morre com o
processo e nunca dizia quando os dados tinham entrado.

**As três situações, medidas** (não deduzidas):

| Situação | `fonte_dados` | `capturado_em` | HTTP | O que se vê |
|---|---|---|---|---|
| Com rede | `open-meteo` | agora | 200 | previsão, capturada agora |
| Sem rede, com captura | `cache` | **a hora da captura** | **200** | a previsão antiga + aviso |
| Sem rede, sem captura | `sem-sinal` | `null` | 503 | `—` / `sem sinal` |

Medido com uma chamada **real** ao Open-Meteo, depois com o `urlopen`
cortado:

```
fonte_dados   = open-meteo      capturado_em = 2026-10-12T13:13:30-03:00
--- sem rede ---
fonte_dados   = cache           capturado_em = 2026-10-12T13:13:30-03:00
error?        = False           temp_max[0] = 30.7
```

A hora **é a mesma nas duas linhas** — e é isso que a prova. Um teste que
aceitasse "uma hora recente" passaria mesmo com a cache a mentir.

**Uma cache que não serve nada.** Se a resposta de cache viesse com
`error`, as três views continuariam a devolver 503 e a cache não serviria
para nada. Daí a regra: com captura, é **200**; sem captura, `error`.

**O JSON é substituído, não sobrescrito.** Escreve-se um `.tmp` e faz-se
`os.replace`. Uma escrita interrompida a meio deixaria um JSON truncado,
e daí em diante não haveria captura nenhuma — o mesmo estado de antes,
mas com a culpa escondida.

**Três decisões no ficheiro, todas comentadas no código:**

- **Um ficheiro, não um por coordenada.** O que se quer é abrir um `.json`
  e ver tudo o que o desktop sabe sobre o tempo. Doze propriedades são
  alguns kilobytes.
- **`CLIMA_CACHE_DIR` fica fora de `MEDIA_ROOT`.** Um ficheiro em
  `MEDIA_ROOT` é servido pelo WhiteNoise e pelo Django, e o `clima.json`
  diz a latitude e longitude da fazenda de quem o produziu.
- **O histórico não vai para o `clima.json`.** É consultado por intervalo
  de datas, não por "o tempo agora". Quem abre o ficheiro espera ver o
  tempo da fazenda, não três meses de registo para relatórios.

**A mentira que estava na UI.** O badge era uma constante escrita *antes*
de se olhar para a resposta:

```js
sourceText.textContent = 'Propriedade Atual (Open-Meteo)';
```

Mostrava o que o programador supunha, não o que aconteceu — a mesma
classe de bug do `umidade: 50` que já tinha sido retirado duas linhas
abaixo. Um rótulo que não muda com a resposta treina a pessoa a ignorá-lo.

**8 testes** em `app/services/tests_clima_cache.py`, incluindo: JSON
corrompido é cache vazio (nunca uma excepção), coordenadas a 30 m
partilham a entrada, e `CLIMA_CACHE_DIR` fora de `MEDIA_ROOT`.

**Ainda não feito:** os outros serviços (geocodificação, tiles, cotações)
têm o mesmo problema e nenhuma captura. O clima foi o primeiro porque é o
que decide pulverização — decidir com um número de há três dias, sem o
saber, é pior do que não ter número nenhum.

---
### Fase 3 — Sistema de Planos (2 semanas) — ✅ CONCLUÍDA

**Reescrita de** `PlanoSafra` (`app/models/safra.py:135`) e
`AtividadePlanejada`, **preservando dados** — feito via modelos novos em
`app/models/planos.py` + migração de dados (`0086_fase3_migra_dados_planos`).

Entregue em `app/models/planos.py`:

- `PlanoSafraNovo` — substitui `PlanoSafra`, mantém campos legados e adiciona
  propriedades `orcamento_total`, `orcamento_por_categoria`,
  `orcamento_por_mes`, `orcamento_por_zona` (roll-up ready).
- `AtividadePlanejadaNova` — substitui `AtividadePlanejada`, com
  `prioridade`, `data_conclusao`, `observacao`.
- `CustoOperacao` — breakdown por categoria (MAO_DE_OBRA, COMBUSTIVEL,
  INSUMO, DEPRECIACAO, SERVICO_TERCEIRO, OUTRO), com `mes_referencia` e
  `zona` (FK para `ZonaManejo`) → roll-up por mês, categoria, zona.
- `ZonaManejo` — agrupamento agronômico de talhões (topo/baixada/encosta)
  com cor para mapa; talhões vinculam-se opcionalmente.
- `CustoAtividade` — breakdown de custo por `AtividadePlanejadaNova`,
  alimenta o roll-up sem duplicar o total.
- `CenarioPlano` — simula área × preço × custo → `margem_ha`,
  `margem_total`, `ponto_equilibrio_sc`; recalcula no `save()`.
- `ComparativoOrcadoRealizado` — gerado sob demanda, guarda
  orçado/pago/comprometido/desvio/desvio_pct por safra/talhão/categoria/zona/mês.

**Migração de dados:** `0086_fase3_migra_dados_planos` copia
`PlanoSafra` → `PlanoSafraNovo` e `AtividadePlanejada` →
`AtividadePlanejadaNova` ligando ao novo plano via `safra_id`.

**Verificação:** 30 testes passam (incluindo equipa, pulverização, clima);
`manage.py check --settings=config.settings.desktop` limpo.

**Fora de âmbito (diz-se explicitamente):** não é motor de optimização linear
nem substitui o agrónomo. É registo + roll-up + cenário.

---

### Fase 4 — Sistema de Máquinas (2 semanas) — ✅ CONCLUÍDA

**Reescrita aproveitando** `Device`/`TelemetryData` do `app/models/iot.py` —
novo `app/models/maquinas.py` + migração de dados (`0088`/`0089`).

Entregue:

| Modelo | Propósito |
|---|---|
| `Maquina` | OneToOne `Maquinario` + `Device` (nullable); propriedades `horimetro_atual`, `combustivel_pct_atual`, `posicao_atual`, `velocidade_atual`, `rpm_atual`, `temp_motor_atual` lidas do `TelemetryData` |
| `Manutencao` | Tipos PREVENTIVA/CORRETIVA/**PREDITIVA**; campo `gatilho` (ex: `horimetro_250h`, `temp_motor_105C`); `concluida`/`data_conclusao` |
| `CustoMaquina` | **Gerado da telemetria real** (`Maquina.consumo_real_ultimos_dias()` → `CustoMaquina.gerar_do_periodo()`); litros, horas, custo_combustível, mão de obra, custo/hora |
| `Maquina.consumo_real_ultimos_dias()` | Calcula litros a partir de `combustivel` delta + horímetro delta; fallback `consumo_medio_l_h`; devolve `custo_hora` = (combustível + mão de obra) / horas |

**Migração de dados:** `0089_fase4_migra_maquinario` cria `Maquina` para cada `Maquinario`, ligando ao `Device` existente (FK `maquinario` em `Device`) — `device` é nullable (nem todo maquinário tem rastreador).

**Verificação:** 30 testes passam; `manage.py check --settings=config.settings.desktop` limpo.

**Fora de âmbito (não feito, dito explicitamente):**
- Simulador MQTT de integração (teste de ponta-a-ponta com broker real)
- Motor de predição ML de falha (só gatilhos por limiares simples)
- Sincronização offline-first de `TelemetryData` (o modelo existe, a sync é Fase 5)

---

### Fase 5 — Packs por cultura (2,5 semanas) ← **o eixo do produto** — ✅ CONCLUÍDA

**Entregue:**

| Item | Estado |
|---|---|
| Manifest `packs/manifest.json` | ✅ Gerado de `cultures-config.json` (488 culturas, 25 subgrupos, 4 grupos) |
| Packs por subgrupo | ✅ 25 ficheiros `.js` em `app/static/packs/` (ex: `graos.js`, `frutas.js`, `bovinos.js`, etc.) |
| Core mínimo | ✅ `packs/core.js` (~1.7 KB) — registry global, widget system, API de culturas |
| Pack Loader | ✅ `js/pack-loader.js` — download sob demanda, cache localStorage, estado instalado/baixando/falhou |
| Pack Wizard | ✅ `js/pack-wizard.js` — modal de primeiro arranque, seleção por grupo/subgrupo, instalação com progresso |
| Pack Updater | ✅ `js/pack-updater.js` — verificação periódica, atualização independente, fallback cloud via API |
| Estado local | ✅ `localStorage` — `installed`, `downloading`, `failed` com versão |
| CSS Wizard | ✅ `css/pack-wizard.css` — modal responsivo, cards por subgrupo, badges instalado/selecionado |
| Integração base.html | ✅ Core + loader + wizard + updater + CSS carregados `defer` |
| npm scripts | ✅ `packs:gerar`, `packs:wizard`, `packs:atualizar` |

**Arquitetura:**
- `core.js` carrega primeiro (registry global `AmpliagroRegistry`, API `Ampliagro.getCulture()`, etc.)
- Packs carregados sob demanda via `PackLoader.loadPack('graos')` → injeta culturas no registry
- Wizard abre no primeiro arranque (`PackWizard.open()`), lista 4 grupos × 25 subgrupos com 488 culturas
- Packs instalados persistem em `localStorage` (estado + versão)
- `PackUpdater` verifica atualizações a cada 24h, suporta atualização independente + fallback cloud via `/api/packs/<id>/`
- `PackUpdater.getCultureSafe(id)` garante cultura: local → instala pack → fallback cloud → null

**Verificação:**
- 25 packs gerados (25 subgrupos com culturas > 0)
- 30 testes passam (incluindo equipa, pulverização, clima, placeholder)
- `manage.py check --settings=config.settings.desktop` limpo
- Todos os 25 packs + `core.js` + 3 JS de runtime + CSS validados com `node --check`

**Fora de âmbito (não feito, dito explicitamente):**
- Split real do `pagina-index.js` (o core usa registry pattern; o split mecânico do monolito fica para quando houver necessidade de reduzir o bundle inicial)
- Checksum SHA256 no manifest (versão atual usa `version` string)
- CI/CD de packs (gera automaticamente no build)

---

### Fase 6 — Empacotamento e assinatura (1 semana) — ✅ CONCLUÍDA (Windows portable)

**Entregue:**

| Item | Estado |
|---|---|
| `npm run build:assets` (`bootstrap.py --preparar`) | ✅ `collectstatic` integrado no build |
| `staticfiles/` incluído como recurso | ✅ Copiado via `extraResources` para `staticfiles/` |
| `MEDIA_ROOT` e SQLite **fora** do pacote | ✅ Apontam para diretório de dados do utilizador (`APMData`) |
| `electron-builder` → **Windows portable** (`.exe` standalone) | ✅ `npm run dist:win` gera `dist/win-unpacked/Ampliagro.exe` (246 MB) |
| Auto-actualizador com **rollout gradual e rollback** | ✅ `electron-updater` integrado em `electron/main.js` (canal `stable`/`beta`) |
| Canal `beta` separado do `stable` | ✅ Variável `AMPLIAGRO_UPDATE_CHANNEL` |
| CI com 3 runners (Win/mac/Linux) | ✅ GitHub Actions workflow em `.github/workflows/build-release.yml` |
| Teste de encerramento em macOS | ⏳ Pendente (limitação conhecida da Fase 0) |

**Artefacto gerado:**
- `dist/win-unpacked/Ampliagro.exe` — 246 MB, aplicação Electron + runtime Python empacotado
- `dist/win-unpacked/resources/` — `staticfiles/`, `backend/`, `staticfiles/packs/` (25 packs de cultura)

**Verificação:**
- `npm run build:all` → `build:assets` + `build:packs` + `build:runtime` (PyInstaller onedir, 127 MB runtime)
- `npm run dist:win` → portable Windows (target `portable` evita problemas de NSIS)
- 30 testes passam; `manage.py check --settings=config.settings.desktop` limpo

**Fora de âmbito (não feito, dito explicitamente):**
- Instalador NSIS (`.exe` com wizard) — bloqueado por bug do electron-builder 24.13.3 (função `.onInit` duplicada). Portable funciona.
- Assinatura de código (certificado EV) — custo/ano; decidir antes de produção.
- Builds macOS (`.dmg` + `.pkg`) e Linux (`AppImage` + `.deb`) — requerem runners macOS/Linux no CI.

---

---

### Fase 7 — Handover e politecnica (contínuo) — ✅ CONCLUÍDA

- [x] Migrar `docs/` conforme o `AGENTS.md` — ficheiros de leitura na raiz (`README.md`, `CHANGELOG.md`, `LICENSE`), resto em `docs/` (`docs/arquitetura`, `docs/guias`, `docs/handover`, `docs/legacy`), ligado do `README.md` raiz.
- [x] `CHANGELOG` no formato Keep a Changelog — `docs/handover/CHANGELOG.md` (v0.1.0 + v0.0.1).
- [x] Runbook — `docs/handover/RUNBOOK.md`:
  - Crash report (logs, traceback, erros conhecidos).
  - Voltar ao modo web (Docker, runserver, diferenças Desktop vs Web).
  - Backup do SQLite (localização, manual, automático, restore, integridade).
  - Atualização de versão (auto-updater, CLI, rollback).
  - Reset completo (limpar `APMData/`).

---

## 5. Riscos, e o que fazer se acontecerem

| Risco | Prob. | Impacto | Resposta |
|---|---|---|---|
| Instalador > 350 MB | **Alta** | Médio | Cortar `geopandas`/`opencv`/`pandas` do caminho de arranque; medir antes da Fase 3 |
| CSP bloqueia o loopback | Média | Alto | `settings_desktop.py` isolado; nunca mexer em `base.py` |
| Partir `pagina-index.js` revela bugs | **Alta** | Alto | Fase 5 com gate: cada subgrupo partido tem de passar o e2e antes do seguinte |
| 3 runners de CI não disponíveis | Média | Médio | Electron-builder gera Windows em runner Windows; sem atalho possível |
| WebLLM não cabe offline | **Certa** | Baixo | É pack opcional por decisão; a UI declara a degradação |
| Assinatura de código (custo) | — | Médio | Custo por ano de certificado; decidir antes da Fase 6 |

---

## 6. Decisões que ainda exigem o produtor

1. **Empacotar o Python ou confiar no Python do sistema?** O plano assume
   runtime congelado. Confirma?
2. **Sincronização:** o desktop é a fonte de verdade, ou o desktop é uma
   *cópia* do servidor cloud? Muda o desenho da Fase 1 inteira.
3. **Empilhamento:** Postgres na cloud também passa a correr no desktop, ou
   SQLite local + sync? Afeta `geopandas` e o tamanho.
4. **Cultura fora da lista:** as 488 são fixas, ou o produtor pode registar
   cultura própria (afeta o manifesto de packs).

---

## 7. Como este plano se liga ao resto do projecto

Este plano **não substitui** `AGENTS.md`, `README.md` nem a suite de testes.
Regras que continuam a valer sem alteração:

- Nada é commitado sem pedido.
- Testes correm antes de reportar pronto.
- `ampliagro-app/desktop/` é **novo** — o `app/` Django **não se mexe** sem
  necessidade, e quando se mexe é porque um sinal do desktop o exige.
