/**
 * Prova de comportamento do `data-sync.js` — antes de mexer.
 *
 * Carrega o ficheiro real num `vm` com `fetch` e `localStorage` falsos e
 * reproduz o ciclo: apagar offline -> sincronizar -> o servidor volta a
 * devolver o registo.
 *
 * Nao se testa texto. Testa-se o que acontece.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const RAIZ = path.resolve(__dirname, '..', '..');
const DATA_SYNC = fs.readFileSync(
  path.join(RAIZ, 'app', 'static', 'js', 'data-sync.js'),
  'utf8'
);
const DATA_STORE = fs.readFileSync(
  path.join(RAIZ, 'app', 'static', 'js', 'data-store.js'),
  'utf8'
);

// ── Mundo falso ─────────────────────────────────────────────────────────────
const localStorage = {};
const server = new Map(); // "talhoes/3" -> {id: 3, nome: 'T1'}
const requests = [];

function resposta(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status: status,
    json: function () {
      return Promise.resolve(body);
    },
  };
}

const fetchCalls = [];
const toasts = [];
function fakeFetch(url, opts) {
  opts = opts || {};
  fetchCalls.push({ url: url, method: opts.method || 'GET' });

  const m = /^([\w-]+)\/(\d+)\/$/.exec(url.replace('/api/', ''));
  const item = m ? server.get(m[1] + '/' + m[2]) : null;

  if (opts.method === 'DELETE') {
    if (item) {
      server.delete(m[1] + '/' + m[2]);
      return Promise.resolve(resposta(204, null));
    }
    return Promise.resolve(resposta(404, null));
  }
  if (opts.method === 'POST' || opts.method === 'PUT') {
    const novo = JSON.parse(opts.body);
    const id = m ? Number(m[2]) : 7;
    if (opts.method === 'POST') novo.id = id;
    server.set(opts.method === 'POST' ? 'talhoes/' + id : m[1] + '/' + m[2], novo);
    return Promise.resolve(resposta(opts.method === 'POST' ? 201 : 200, novo));
  }
  // GET
  if (url.endsWith('/talhoes/')) {
    return Promise.resolve(resposta(200, Array.from(server.values())));
  }
  return Promise.resolve(resposta(200, []));
}

const contexto = {
  // `data-store.js` chama `DataStore.init()` no fim do ficheiro, e
  // `window.DataStore = ...` — sem esta auto-referencia, o `DataStore`
  // global nao existe e o script rebenta na linha 362.
  localStorage: {
    getItem: function (k) {
      return Object.prototype.hasOwnProperty.call(localStorage, k) ? localStorage[k] : null;
    },
    setItem: function (k, v) {
      localStorage[k] = String(v);
    },
  },
  document: {
    querySelector: function () {
      return { value: 'csrf' };
    },
    cookie: 'csrftoken=csrf',
    getElementById: function () {
      return null;
    },
  },
  navigator: { onLine: true },
  fetch: fakeFetch,
  console: console,
  setTimeout: function () {},
  // `data-store.js:329` arranca um `setInterval` no init. Nao queremos um
  // timer vivo num script de teste.
  setInterval: function () {},
  clearInterval: function () {},
  addEventListener: function () {},
  // `showToast` e' global da app (definido noutro script). Registamos o que
  // diz, porque a honestidade do toast e' parte do que estamos a medir.
  showToast: function (msg, kind) {
    toasts.push({ msg: msg, kind: kind || 'info' });
  },
  Promise: Promise,
  Date: Date,
  Math: Math,
  JSON: JSON,
};
contexto.globalThis = contexto;
contexto.window = contexto;
vm.createContext(contexto);
vm.runInContext(DATA_STORE, contexto, { filename: 'data-store.js' });
vm.runInContext(DATA_SYNC, contexto, { filename: 'data-sync.js' });

// ── Cenario ─────────────────────────────────────────────────────────────────
// O servidor tem um talhao. A app local tem o mesmo talhao.
server.set('talhoes/3', { id: 3, nome: 'T1', area_hectare: 1 });

const DataStore = contexto.window.DataStore;
const DataSync = contexto.window.DataSync;

function estado() {
  const raw = localStorage['ampliagro_data'];
  return raw ? JSON.parse(raw) : null;
}

// O produtor apaga o talhao (offline ou nao — o codigo e' o mesmo).
DataStore.save('talhoes', { id: 3, nome: 'T1', area_hectare: 1 });
console.log('1. guardado local:', JSON.stringify(estado().data.talhoes));
console.log('   pendingChanges:', estado().pendingChanges.length);

// A API publica chama-lhe `delete` (data-store.js:344), nao `remove`.
DataStore['delete']('talhoes', 3);
console.log('2. apos remove() -> data:', JSON.stringify(estado().data.talhoes));
console.log('   deletedIds:', JSON.stringify(estado().deletedIds.talhoes));
console.log('   pendingChanges:', estado().pendingChanges.length);

// Sincroniza.
DataSync.pushChanges().then(function () {
  console.log('3. pedidos enviados:', JSON.stringify(fetchCalls));
  console.log('   servidor ainda tem o talhao?', server.has('talhoes/3'));
  console.log('   deletedIds depois:', JSON.stringify(estado().deletedIds.talhoes));
  console.log('   pendingChanges depois:', estado().pendingChanges.length);

  // O pull automatico do init().
  fetchCalls.length = 0;
  return DataSync.pullFromServer();
}).then(function () {
  console.log('4. depois do pull -> data local:', JSON.stringify(estado().data.talhoes));
  const local = estado().data.talhoes || [];
  console.log('');
  if (local.some(function (x) { return x.id === 3; })) {
    console.log('>>> REPRODUZIDO: o talhao apagado voltou. O DELETE nunca saiu.');
  } else {
    console.log('>>> OK: o talhao apagado ficou apagado.');
  }
}).catch(function (e) {
  console.error('ERRO', e);
  process.exitCode = 1;
});