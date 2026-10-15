# ADR-001 — Casca Electron + runtime Django embebido

- **Estado:** aceita
- **Data:** 2026-10-12

## Contexto

O Ampliagro hoje é Django 5.2 + DRF + Channels + Celery, com 98 dependências
Python (das quais várias nativas: `geopandas`, `pandas`, `numpy`,
`opencv-python-headless`, `psycopg2-binary`, `cryptography`, `bcrypt`).
O frontend são 119 templates Django + 165 ficheiros estáticos (3,8 MB),
com Vite, Tailwind e JS vanilla.

Queremos um app de ambiente de trabalho para Windows, macOS e Linux que
funcione offline e rode o mesmo sistema.

## Decisão

**Electron** como casca, com o **runtime Django embebido** em
`http://127.0.0.1:<porta>` servido por **Daphne** (ASGI, não WSGI — ver
"Daphne e não waitress" abaixo).

## Porquê

### O runtime Django já suporta este modo

`config/settings/base.py` já tem exactamente os fallbacks que o desktop
precisa, e não foi preciso inventar nada:

- `DATABASES` cai para SQLite (`base.py:200-210`), já com WAL e
  `transaction_mode="IMMEDIATE"`.
- `CHANNEL_LAYERS` cai para `InMemoryChannelLayer` quando não há `REDIS_URL`
  (`base.py:301-319`).
- `CACHES` é `DatabaseCache` (`base.py:644`) — não precisa de Redis.

O desktop é o cenário "1 processo, sem Redis, SQLite". O backend já lived.

### Electron e não Tauri

O frontend tem **606 handlers `on*=`** e um `<script>` inline de ~13.000
linhas (registado em `config/settings/base.py:379-401`). Electron carrega
exactamente o que o browser carrega — **zero regressão visual**. Tauri daria
binário menor, mas obrigaria a eliminar todo o inline, que é a segunda maior
fatia de trabalho do projecto.

### Daphne e não waitress (correção)

A primeira versão deste ADR dizia **waitress**. **Estava errado**, e o erro
seria fatal: waitress é **WSGI**, e este projecto é **ASGI**.

- `config/asgi.py` monta um `ProtocolTypeRouter` com `"http"` e `"websocket"`.
- O WebSocket é `ws/dashboard/` → `DashboardConsumer` (`app/consumers.py`).
- Por detrás estão `TelemetryData`, `AlertaTelemetria` e `ComandoDevice`
  (`app/models/iot.py`) — alertas em tempo real.

Servir com waitress significava `SyncConsumer` a responder a HTTP e nada
nunca a servir o WebSocket. O painel funcionava; os alertas em tempo real
não. Como o sintoma é *ausência de tempo real* e não erro, isto passaria
despercebido até alguém esperar um alarme de sensor que não chegava.

**A correcção é `daphne`**, que é o servidor documentado do Channels, é
Python puro (compila em qualquer SO sem cross-compile), e **já é uma
dependência declarada** (`requirements.txt`, e `"daphne"` está em
`INSTALLED_APPS` — `config/settings/base.py:70`). Estado medido na máquina:
`daphne 4.2.3`.

Nota sobre `uvicorn` (também declarado, 0.54.0): para WebSockets precisa de
`websockets` ou `wsproto`. A medição diz **`websockets` NÃO está instalado**
e `wsproto` 1.3.2 está. Uvicorn com `--ws wsproto` funcionaria, mas Daphne
não precisa da flag e é o servidor que o Channels documenta. Escolhido Daphne.

### Bootstrap e o `setdefault` do ASGI

`config/asgi.py:6` tem:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
```

`setdefault` **só aplica se a variável não existir**. Como o desktop quer
`config.settings.desktop`, o `bootstrap.py` tem de atribuir a variável
**antes** de qualquer import que carregue o ASGI. Se importar primeiro, o
desktop arrancaria silenciosamente com os **settings de produção** — sem
`DJANGO_VITE` desligado, sem CSP de loopback, com a configuração de logging
e cache errada. É uma falha silenciosa, do tipo que só aparece em produção.

### Electron e não um webview do sistema

Não garante a mesma versão de Chromium em Windows/mac/Linux. Numa aplicação
que depende de `SharedArrayBuffer`/WASM (WebLLM) e de comportamento de CSP
consistente, fixar o Chromium é uma decisão de compatibilidade, não um
detalhe.

## Consequências

**Boas**
- Funciona 100% offline depois da Fase 1.
- A UI é a mesma que a web — sem segunda implementação, sem drift.
- O runtime embebido também serve ao `docker-compose` existente.

**Maus**
- Instalador grande. **A medição de 2026-10-12 deu 462,5 MB instalados**,
  não os ~150 MB que esta ADR estimava para o Electron (ver a secção
  "A ESTIMATIVA ESTAVA ERRADA"). O alvo de 350 MB **não é alcançável com
  Electron** no tamanho instalado; é alcançável no instalador comprimido.
- 3 runners de build. PyInstaller e as wheels nativas não fazem cross-compile.
- Electron ocupa 367,7 MB, não 150 MB. Aceito porque a alternativa
  (Tauri) obrigaria a reescrever 606 handlers `on*=` e um `<script>` inline
  de ~13.000 linhas.

**Neutras**
- Celery tem de passar a `task_always_eager` + worker em thread. É a única
  peça que precisa de trabalho real.
- O CSP de `base.py` precisa de uma entrada para `127.0.0.1` — feita em
  `settings_desktop.py`, **nunca** em `base.py`, para não abrir uma porta em
  produção.

## Alternativas descartadas

| Alternativa | Porquê não |
|---|---|
| Shell fino, backend na cloud | Não é offline. Fica só com o cache do PWA. |
| Runtime Django completo, sem cortes | Instalador de 600 MB–1 GB. Cortar antes de cortar uma feature. |
| Tauri | Ganho de ~320 MB contra a reescrita de 606 handlers + 13k linhas. |
| Reimplementar o frontend em React/Electron | Duplicaria a aplicação inteira. Rejeitado. |

## A ESTIMATIVA ESTAVA ERRADA — e o número importa

Esta ADR dizia, na primeira versão, que o Electron ocupava "~150 MB" e que
o alvo de 350 MB para o instalador era atingível cortando `geopandas`,
`opencv` e `pandas`.

**Medido em 2026-10-12, com Electron 44.7.0:**

| Componente | Tamanho |
|---|---|
| `electron.exe` (sozinho) | 234,9 MB |
| `dxcompiler.dll` | 24,6 MB |
| `resources.pak` | 11,9 MB |
| `locales/` (55 ficheiros) | 48,3 MB |
| resto do `dist/` | ~48 MB |
| **Electron total** | **367,7 MB** |
| Runtime Python congelado (Fase 1) | 94,8 MB |
| **TOTAL instalado** | **462,5 MB** |

A conta que a ADR fazia (150 + runtime) estava errada por 2,5 vezes no
Electron. E o que o planoomitiu é que **cortar Python não resolve**:
mesmo com o runtime Python a zero, o Electron sozinho já passa dos 350 MB.

O que a medição corrige, e é o que fica:

- **350 MB é um alvo para o INSTALADOR COMPRIMIDO, não para o instalado.**
  Com compressão, 462,5 MB dão ~277 MB. É esse o número que o produtor
  vê a descarregar, e é esse que interessa.
- **Apurar Electron dá pouco.** Tirar os 48,3 MB de locales (e o
  `electron-builder` fá-lo por omissão, mantendo só `pt-BR` e `en-US`)
  deixa ~414 MB instalados. O `electron.exe` de 234,9 MB não se apura.
- **Portanto a escolha Electron/Tauri tem de ser revistada por quem decide
  o negócio**, à luz destes números e não dos que estavam aqui. A
  recomendação desta ADR mantém-se porque o custo do Tauri (reescrever
  606 handlers inline e um script de 13.000 linhas) não diminuiu — mas o
  argumento do tamanho, esse, caiu.