/**
 * Ampliagro PWA Service Worker - Cache do shell (híbrido SPA+PWA)
 * Cache strategy: Network-first for API, Cache-first for static assets
 * Sem Background Sync: ver o aviso no sítio onde o listener 'sync' estava.
 */
// ─────────────────────────────────────────────────────────────────────────────
// VERSÃO DO CACHE — subir de número quando um ESTÁTICO muda
// ─────────────────────────────────────────────────────────────────────────────
// Estes três nomes são a única coisa que faz o browser descartar o que já
// tinha. O `fetch` de estáticos é cache-first: devolve o que está em cache e
// só actualiza em segundo plano. Na prática isso significa que uma alteração
// a um `.js` chega ao utilizador no carregamento *seguinte* — e só se o
// utilizador recarregar.
//
// Duas consequências, ambas medidas a 2026-10-01:
//
//  1. Um programador altera o JS, vê o browser em cache, e conclui que a
//     correcção não funciona. Não funciona mesmo — mas não é o código que
//     está a correr.
//  2. Um produtor fica com um ecrã partido e não consegue sair dele: limpar
//     cache à mão é conhecimento que ninguém tem.
//
// Por isso o número abaixo sobe sempre que um estático muda. É um passo
// manual e é chato de esquecer — mas é explícito, aparece no diff, e um
// ficheiro de constantes é exactamente o sítio onde se quer esse registo.
// Números que não mudam quando deviam mudam é o que produziu a confusão
// desta vez.
const CACHE_VERSION = 'v37';
const CACHE_NAME = `ampliagro-os-${CACHE_VERSION}`;
const STATIC_CACHE = `ampliagro-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `ampliagro-dynamic-${CACHE_VERSION}`;
const OFFLINE_DB = 'ampliagro-offline';
// Versão do IndexedDB. NÃO é a CACHE_VERSION: esta é a do ESQUEMA do banco.
// Tem de ser IGUAL à `AMPLIA_DB_VERSION` de app/static/js/pwa/indexeddb.js —
// se um subir e o outro não, os dois `onupgradeneeded` param de concordar sobre
// que stores existem e um deles cria um banco incompleto.
const OFFLINE_DB_VERSION = 2;

// Assets to cache immediately - OS híbrido SPA+PWA (só rotas 200)
//
// ⚠️ O `?v=` AQUI TEM DE SER O MESMO `?v=` DO TEMPLATE. Byte a byte.
//
// Não é cosmético. O Cache API guarda por URL INTEIRA — `/static/js/spa.js?v=20261007m`
// e `/static/js/spa.js?v=20261007m` são duas entradas diferentes. Se aqui levar `?v=A`
// e o `base.html` pedir `?v=B`, o precache guarda uma entrada que ninguém vai
// buscar e o pedido real vai à rede. Offline, isso é o SPA router a não
// arrancar — e o produtor vê um ecrã em branco sem explicação.
//
// Foi o que acontecia com 4 das 6 entradas versionadas. O `spa.js` e o
// `guide.js` já estão com o MESMO `?v=` nos dois lados, e é esse o estado que
// este ficheiro tem de manter: `guide.js?v=20261007n` aqui e
// `?v=20261007k` nos quatro `guia-*.html`. A tabela abaixo é a das entradas
// que estão ERRADAS, para se ver o que já foi corrigido e o que não foi:
//   - `spa.js` — era `v=20261007g` aqui contra `?v=20250912a` no template. CORRIGIDO.
//   - `guide.js` — era `v=20261007f` aqui contra `?v=...` nos templates.
//     CORRIGIDO: é `20261007k` nos dois lados.
//   - `navbar-premium.css` e `soft-ui.css` — continuam a precisar de revisão
//     (há `?v=` no template e entradas com `?v=` diferente aqui).
//
// Nenhuma das quatro foi alguma vez servida do cache. O commentário de baixo,
// sobre subir a CACHE_VERSION, não resolvia isto porque o problema não era a
// versão do cache — era o endereço.
//
// COMO SE CORRIGE UM `?v=` ERRADO: troca-se nos DOIS lados (aqui e no
// `base.html`) e sobe-se a CACHE_VERSION. Se o `?v=` mudar aqui e não no
// template, o cache fica com a entrada velha e o problema volta.
const STATIC_ASSETS = [
  '/',
  '/guias/vegetal/',
  // CSS — os `?v=` copiados de app/templates/base.html
  '/static/css/tailwind-compiled.css', // base.html:16 — sem ?v=
  '/static/css/navbar-premium.css?v=20261006a', // base.html:17
  '/static/css/widgetbar-windows.css?v=20260918a', // base.html:18
  '/static/css/soft-ui.css?v=20261002', // base.html:19
  '/static/css/soft-ui.css?v=20260918a', // index.html:1692 — outro ?v=, é outro URL
  '/static/css/theme.css', // base.html:27 — sem ?v=
  '/static/css/ampliagro-global.css?v=4', // base.html:29
  // JS do shell — `?v=` copiados de app/templates/base.html
  '/static/js/spa.js?v=20261007dbg', // base.html:217
  '/static/js/guide.js?v=20261007n', // guia-vegetal.html:142 e :147
  '/static/js/dashboard_appbar.js', // base.html:219 — sem ?v=
  // A AmplIA. Sem estas cinco, o chat e o feed de alertas não funcionam na
  // PRIMEIRA visita sem sinal: o precache não as tinha, o `cacheFirst` só as
  // guardava depois de uma visita com rede, e a promessa do produto é abrir
  // sem internet. São 324 KB e é o que o produtor abre para working.
  '/static/js/ia-sandbox.js?v=1', // base.html:220
  '/static/js/ia-local/ia-local.js', // base.html:221 — sem ?v=
  '/static/js/ia-local/whisper-audio.js?v=1', // base.html:226
  '/static/js/ia-local/proativo-local.js?v=1', // base.html:232
  '/static/js/ia-local/alerta-feed.css?v=1', // base.html:238
  '/static/js/ia-local/alerta-feed.js?v=1', // base.html:239
  '/static/js/ia-local/palco-amplia.js?v=2', // base.html:247
  '/static/js/ia-local/chamado-amplia.js?v=1', // base.html:260
  // Tema e dados. `theme-system.js` e `theme-presets.js` têm de estar juntos:
  // o commentário em base.html:95-97 avisa que o script inline depende da ordem.
  '/static/js/theme-system.js?v=20261007dbg', // base.html:98
  '/static/js/theme-presets.js?v=20261007dbg', // base.html:106
  '/static/js/cultures-loader.js', // base.html:262 — sem ?v=
  '/static/js/adapters/ibge-adapter.js', // base.html:265 — sem ?v=
  '/static/js/data-provider.js?v=5', // base.html:267
  // PWA
  //
  // `pwa/sync.js` e `pwa/indexeddb.js` NAO entram aqui, e foi uma correcao.
  // Nenhum template os carrega (`data-sync.js` — que e o caminho vivo — nao
  // tem nada a ver com eles), e o `pwa/sync.js` faz POST para
  // `/api/caderno/notas/`, `/api/caderno/fotos/` e `/api/caderno/voice/`,
  // nenhum dos quais existe. Sao 21 KB de precache a guardar codigo morto.
  // O caminho de escrita offline real e o `app/static/js/data-sync.js`, com
  // `localStorage` e endpoints que aceitam escrita.
  // Guard: `tests/test_sync_offline.py`.
  '/static/js/pwa/qr.js',
  '/static/manifest.json',
  'https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
];

// API endpoints that should use network-first - OS híbrido
const API_PATTERNS = [
  '/api/',
  '/operario/api/',
  '/api/tarefas',
  '/api/estagios',
  '/api/funcionarios',
  '/api/propriedades',
  '/api/telemetria',
  '/api/dashboard/',
  '/api/widget-data/',
  '/api/registros-producao/',
  '/api/safras/',
  '/api/culturas/',
  '/api/talhoes/',
];

// Install event - cache static assets (tolerante a 404)
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(async (cache) => {
      console.log('[SW] Caching static assets');
      for (const url of STATIC_ASSETS) {
        try {
          const req = new Request(url, { cache: 'reload' });
          const res = await fetch(req);
          if (res.ok) await cache.put(req, res.clone());
          else console.warn('[SW] skip precache 404', url);
        } catch (e) {
          console.warn('[SW] skip precache fail', url, e.message);
        }
      }
      return self.skipWaiting();
    })
  );
});

// Activate event - clean old caches + notifica para limpar preset cache corrompido + força reinicializacao do mapa
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== STATIC_CACHE && name !== DYNAMIC_CACHE)
            .map((name) => caches.delete(name))
        );
      })
.then(() => self.clients.claim())
      .then(() =>
        self.clients
          .matchAll()
          .then((clients) => {
            // Forca reinicializacao de mapas em todas as paginas abertas
            clients.forEach((c) => {
              c.postMessage({ type: 'CLEAR_PRESET_CACHE' });
              // Envia flag para forcar recarga do mapa do onboarding
              if (c.url.includes('/onboarding/')) {
                c.postMessage({ type: 'RESET_MAP', payload: Date.now() });
              }
            });
          })
      )
  );
});

// Fetch event - híbrido SPA+PWA: stale-while-revalidate para páginas, network-first para API, cache-first para estáticos
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET
  if (request.method !== 'GET') return;

  // Skip esquemas que o Cache API não suporta (chrome-extension://, etc.)
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  // Auth: NUNCA servir do cache — HTML velho traz {% csrf_token %} velho e o
  // POST seguinte falha CSRF (login 403). Login/logout/demo/accounts sempre rede.
  if (
    url.pathname === '/login/' ||
    url.pathname === '/logout/' ||
    url.pathname === '/demo/' ||
    url.pathname.startsWith('/accounts/')
  ) {
    return;
  }

  // Páginas HTML: SEMPRE network-first.
  //
  // MEDIDO 2026-10-06: as guias eram `staleWhileRevalidateHTML`, e o
  // produtor recarregava, via a pagina VELHA (com os KPIs em "—" porque o
  // `render` nao passava `props_stats`), e concluia que a correcao nao
  // funcionava. A correcao funcionava; o que estava a correr era o cache.
  //
  // E o problema nao e' so de actualidade: HTML autenticado tem DADOS DO
  // PRODUTOR (totais, safras, e o `{% csrf_token %}`). Um cache desses
  // servido em stale-while-revalidate mostra a pessoa o numero de ontem como
  // se fosse o de hoje — e, num browser partilhado, mostra o numero de uma
  // conta a outra. E' o mesmo motivo pelo qual `/login/` nunca e' cacheado,
  // dois paragrafos acima.
  //
  // Offline perde-se o HTML, que e' o preco honesto: um painel financeiro
  // guardado ha tres dias e' pior do que nenhum painel. `networkFirst` ainda
  // cai no cache quando a rede falha (abaixo), so que o produtor sem rede
  // ve pagina em vez de "Offline".
  const isHTML =
    request.mode === 'navigate' ||
    request.headers.get('X-Partial') === '1' ||
    (request.headers.get('X-Requested-With') === 'XMLHttpRequest' &&
      url.pathname.startsWith('/guias/'));
  if (isHTML) {
    event.respondWith(networkFirst(request));
    return;
  }

  // API - network-first com fallback e update silencioso
  if (API_PATTERNS.some((pattern) => url.pathname.startsWith(pattern))) {
    event.respondWith(networkFirst(request));
    return;
  }

  // CORREÇÃO PARA ERRO sw.js:373 / CSP:
  // Se for um tile do OpenStreetMap ou estático, usa a lógica corrigida do cacheFirst
  if (url.hostname.includes('tile.openstreetmap.org') || 
      url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Estáticos versionados - cache-first com background refresh
  event.respondWith(cacheFirst(request));
});

// Stale-while-revalidate para HTML: retorna cache 0ms, atualiza em background e notifica diff
async function staleWhileRevalidateHTML(request) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(request);

  // NÃO reconstrói a Response com os headers da rede. Com GZipMiddleware
  // ligado (config/settings/base.py), response.text() já vem decodificado
  // enquanto o header continua dizendo `Content-Encoding: gzip` (+ o
  // content-length antigo): o browser tentava descompactar texto puro e a
  // página quebrava. A resposta de rede vai intacta; o texto serve só para
  // comparar e para o patch no cliente.
  const networkFetch = fetch(request)
    .then(async (response) => {
      if (!response.ok) return response;
      // response.redirected = a navegação terminou em outro lugar (login).
      // Cachear isso guardaria HTML de login sob uma URL privada.
      if (response.redirected) return response;

      const forCache = response.clone(); // corpo intacto para o cache
      const forCompare = response.clone(); // consumido pelo .text()
      const netText = await forCompare.text();
      const cachedText = cached ? await cached.text() : null;

      await cache.put(request, forCache);
      // só notifica se o conteúdo mudou de fato
      if (cached && cachedText !== netText) {
        self.clients
          .matchAll()
          .then((clients) =>
            clients.forEach((c) =>
              c.postMessage({ type: 'HTML_UPDATE', url: request.url, html: netText })
            )
          );
      }
      return response;
    })
    .catch(
      async () => cached || (await caches.match('/')) || new Response('Offline', { status: 503 })
    );

  return cached || networkFetch;
}

// Network-first strategy
async function networkFirst(request) {
  const cache = await caches.open(DYNAMIC_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) {
      return cached;
    }
    // Return offline page for navigation requests - OS híbrido
    if (request.mode === 'navigate') {
      const offline = await caches.match('/');
      return (
        offline ||
        new Response('Offline - Ampliagro OS', {
          status: 503,
          headers: { 'Content-Type': 'text/html' },
        })
      );
    }
    /* Mesma regra do cacheFirst: cache falhado NAO e' excecao.
     * Este `throw` produzia o mesmo `Uncaught (in promise) TypeError` no
     * network-first, e ele aparecia DEPOIS do do cacheFirst corrigido — ou
     * seja, corrigir um só deixa o mesmo erro a entrar pela outra porta.
     * Nenhuma das duas strategias tem o que fazer com um recurso que a CSP
     * bloqueou: 204 e' a resposta honesta. */
    return new Response('', {
      status: 204,
      statusText: 'SW network-fail, sem cache',
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}

// Cache-first strategy with CSP/error handling - OS híbrido
async function cacheFirst(request) {
  const cache = await caches.open(STATIC_CACHE);
  
  // 1. Tenta o cache primeiro
  const cachedResponse = await cache.match(request);
  if (cachedResponse) return cachedResponse;

  try {
    // 2. Tenta a rede
    const networkResponse = await fetch(request);
    
    // Se a resposta for válida, guarda no cache dinâmico
    if (networkResponse && networkResponse.ok) {
      const dynamicCache = await caches.open(DYNAMIC_CACHE);
      dynamicCache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // SOLUÇÃO PARA O ERRO sw.js:373:
    // Retorna uma resposta nula segura para evitar o "TypeError: Failed to construct Response"
    // status 0 ou erros de CSP não permitem corpo (body).
    console.warn('[SW] Fetch falhou ou foi bloqueado pelo CSP:', request.url);
    
    return new Response(null, { 
      status: 408, 
      statusText: 'Network Error or Blocked by CSP' 
    });
  }
}

// Background sync via Service Worker: REMOVIDO (2026-10-04).
//
// Este ficheiro tinha um `addEventListener('sync', ...)` que reagia à etiqueta
// `sync-mutations` e despejava a fila `mutations` para o servidor. O ramo foi
// removido por duas razões, ambas verificadas:
//
//  1. MORTO. Nenhuma linha do projecto registava essa etiqueta — nem
//     `registration.sync.register(...)`, nem `registerSync`, nem um
//     `postMessage` que a registasse. O `onupgradeneeded` deste ficheiro e o
//     `indexeddb.js` criam o banco, mas o `addEventListener('sync')` só
//     dispara quando o browser agenda essa tag. Sem registo, nunca dispara.
//
//  2. ERRADO SE FOSSE LIGADO. O flush apontava para `/api/caderno/notas/`,
//     `/api/caderno/fotos/` e `/api/caderno/voice/`. Nenhum dos três existe no
//     backend (não há "caderno" em nenhum `urls.py`, nem modelo Nota/Foto/
//     Voice). Cada anotação devolveria 404 — o produtor veria "guardado" e a
//     nota nunca chegaria ao servidor.
//
// A sincronização real NÃO corre aqui. Corre em
// `app/static/js/pwa/sync.js`, pelo evento `online` do browser e por um
// temporizador (`startPeriodicSync(5)`), e essa via depende do app aberto.
//
// NOTA: `syncMutations()` abaixo ficou sem chamador e `openOfflineDB()` ficou
// sem chamador dentro deste ficheiro. NÃO os apagar por preguiça: `openOfflineDB()`
// é a CÓPIA do schema que tem de continuar a bater certo com a
// `AMPLIA_DB_VERSION` de `indexeddb.js`. Deixados de propósito, com este aviso.

async function syncMutations() {
  const db = await openOfflineDB();
  const tx = db.transaction('mutations', 'readonly');
  const store = tx.objectStore('mutations');
  const mutations = await store.getAll();

  for (const mutation of mutations) {
    try {
      const response = await fetch(mutation.url, {
        method: mutation.method,
        headers: mutation.headers,
        body: mutation.body,
      });
      if (response.ok) {
        const deleteTx = db.transaction('mutations', 'readwrite');
        await deleteTx.objectStore('mutations').delete(mutation.id);
        // Notify clients
        self.clients.matchAll().then((clients) => {
          clients.forEach((client) =>
            client.postMessage({
              type: 'SYNC_COMPLETE',
              mutationId: mutation.id,
            })
          );
        });
      }
    } catch (error) {
      console.error('[SW] Sync failed for', mutation.id, error);
    }
  }
}

// Helper to open IndexedDB
//
// ── O SCHEMA INTEIRO TEM DE ESTAR AQUI ────────────────────────────────────────
// Este `onupgradeneeded` e o de `indexeddb.js` correm para o MESMO banco. Só
// um deles é executado por versão — o que acordar primeiro cria os stores, e o
// outro encontra-os já prontos e não cria mais nada. Antes desta correcção o
// Service Worker declarava 4 stores ('mutations', 'notes', 'photos',
// 'observations') sem índices, e o JS da página declarava 7 com índices.
// Se o SW ganhasse, `field_notes`, `offline_tasks`, `experiments` e
// `voice_recordings` nunca eram criados e o Caderno de Campo offline partia com
// NotFoundError. O store 'notes' não era usado por ninguém — era código morto.
//
// As DUAS listas precisam mudar juntas. `indexeddb.js` é a fonte de verdade
// dos índices; esta é a cópia. Não apagar object stores existentes: o produtor
// tem dados offline no aparelho dele.
function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(OFFLINE_DB, OFFLINE_DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;

      if (!db.objectStoreNames.contains('mutations')) {
        const store = db.createObjectStore('mutations', { keyPath: 'id', autoIncrement: true });
        store.createIndex('url', 'url', { unique: false });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      }
      if (!db.objectStoreNames.contains('field_notes')) {
        const store = db.createObjectStore('field_notes', { keyPath: 'id', autoIncrement: true });
        store.createIndex('talhao_id', 'talhao_id', { unique: false });
        store.createIndex('cultura_id', 'cultura_id', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
        store.createIndex('synced', 'synced', { unique: false });
      }
      if (!db.objectStoreNames.contains('photos')) {
        const store = db.createObjectStore('photos', { keyPath: 'id', autoIncrement: true });
        store.createIndex('note_id', 'note_id', { unique: false });
        store.createIndex('synced', 'synced', { unique: false });
      }
      if (!db.objectStoreNames.contains('observations')) {
        const store = db.createObjectStore('observations', { keyPath: 'id', autoIncrement: true });
        store.createIndex('talhao_id', 'talhao_id', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
        store.createIndex('synced', 'synced', { unique: false });
      }
      if (!db.objectStoreNames.contains('offline_tasks')) {
        const store = db.createObjectStore('offline_tasks', { keyPath: 'id', autoIncrement: true });
        store.createIndex('talhao_id', 'talhao_id', { unique: false });
        store.createIndex('cargo_alvo', 'cargo_alvo', { unique: false });
        store.createIndex('synced', 'synced', { unique: false });
      }
      if (!db.objectStoreNames.contains('experiments')) {
        const store = db.createObjectStore('experiments', { keyPath: 'id', autoIncrement: true });
        store.createIndex('talhao_a', 'talhao_a', { unique: false });
        store.createIndex('talhao_b', 'talhao_b', { unique: false });
        store.createIndex('status', 'status', { unique: false });
      }
      if (!db.objectStoreNames.contains('voice_recordings')) {
        const store = db.createObjectStore('voice_recordings', {
          keyPath: 'id',
          autoIncrement: true,
        });
        store.createIndex('note_id', 'note_id', { unique: false });
        store.createIndex('synced', 'synced', { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// Listen for messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[SW] Ampliagro Service Worker loaded');
