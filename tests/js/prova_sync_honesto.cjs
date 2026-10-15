/**
 * Prova 2 — o caminho da falha.
 *
 * O sync tem de continuar a DIZER a verdade quando o servidor recusa:
 *   * o DELETE que falhou fica em `deletedIds` para a proxima tentativa;
 *   * o `pendingChanges` do tipo com erro nao e' limpo;
 *   * o toast e' de erro, e nao de sucesso.
 *
 * E o caminho inverso: um tipo que corre bem pode perder as suas pendencias,
 * mesmo quando outro tipo falhou.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const RAIZ = path.resolve(__dirname, '..', '..');

function carregar(modoFalha) {
  const server = new Map();
  const fetchCalls = [];
  const toasts = [];
  const localStorage = {};

  function resposta(status, body) {
    return {
      ok: status >= 200 && status < 300,
      status: status,
      json: function () {
        return Promise.resolve(body);
      },
    };
  }

  function fakeFetch(url, opts) {
    opts = opts || {};
    fetchCalls.push({ url: url, method: opts.method || 'GET' });
    const m = /^([\w-]+)\/(\d+)\/$/.exec(url.replace('/api/', ''));
    const chave = m ? m[1] + '/' + m[2] : null;

    if (opts.method === 'DELETE') {
      // Modo de falha: o servidor recusa o DELETE com 500.
      if (modoFalha && chave === 'talhoes/3') {
        return Promise.resolve(resposta(500, { detail: 'boom' }));
      }
      server.delete(chave);
      return Promise.resolve(resposta(204, null));
    }
    if (opts.method === 'POST' || opts.method === 'PUT') {
      const novo = JSON.parse(opts.body);
      if (opts.method === 'POST') novo.id = 7;
      server.set(opts.method === 'POST' ? 'talhoes/7' : chave, novo);
      return Promise.resolve(resposta(opts.method === 'POST' ? 201 : 200, novo));
    }
    if (url.endsWith('/talhoes/')) {
      return Promise.resolve(resposta(200, Array.from(server.values())));
    }
    if (url.endsWith('/insumos/')) {
      return Promise.resolve(resposta(200, [{ id: 9, nome: 'Ureia' }]));
    }
    return Promise.resolve(resposta(200, []));
  }

  const contexto = {
    localStorage: {
      getItem: function (k) {
        return Object.prototype.hasOwnProperty.call(localStorage, k)
          ? localStorage[k]
          : null;
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
    console: { warn: function () {}, error: function () {}, log: function () {} },
    setTimeout: function () {},
    setInterval: function () {},
    clearInterval: function () {},
    addEventListener: function () {},
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

  // O servidor tem o talhao. Sem semear isto, "o talhao continua no
  // servidor" passaria a vazio — o registo nunca chegou a existir e o
  // teste nao provaria nada.
  server.set('talhoes/3', { id: 3, nome: 'T1', area_hectare: 1 });

  vm.createContext(contexto);
  vm.runInContext(
    fs.readFileSync(path.join(RAIZ, 'app', 'static', 'js', 'data-store.js'), 'utf8'),
    contexto,
    { filename: 'data-store.js' }
  );
  vm.runInContext(
    fs.readFileSync(path.join(RAIZ, 'app', 'static', 'js', 'data-sync.js'), 'utf8'),
    contexto,
    { filename: 'data-sync.js' }
  );

  return {
    DataStore: contexto.window.DataStore,
    DataSync: contexto.window.DataSync,
    server: server,
    toasts: toasts,
    fetchCalls: fetchCalls,
    estado: function () {
      const raw = localStorage['ampliagro_data'];
      return raw ? JSON.parse(raw) : null;
    },
  };
}

function check(nome, cond, detalhe) {
  console.log((cond ? '  OK   ' : '  FALHA') + ' | ' + nome + (detalhe ? ' — ' + detalhe : ''));
  if (!cond) process.exitCode = 1;
}

// ── Cenario A: o DELETE e' recusado ────────────────────────────────────────
console.log('A) servidor recusa o DELETE (500)');
const a = carregar(true);
a.DataStore['delete']('talhoes', 3);
a.DataStore.save('insumos', { nome: 'Ureia', quantidade: 5 });

a.DataSync.pushChanges().then(function () {
  const st = a.estado();

  check(
    'o DELETE falhado continua em deletedIds',
    (st.deletedIds.talhoes || []).indexOf(3) !== -1,
    JSON.stringify(st.deletedIds.talhoes)
  );
  check(
    'o talhao continua no servidor',
    a.server.has('talhoes/3'),
    'nao devia ter sido apagado'
  );
  check(
    'pendingChanges do tipo com falha nao foi limpo',
    (st.pendingChanges || []).some(function (c) {
      return c.type === 'talhoes';
    }),
    JSON.stringify(st.pendingChanges)
  );
  check(
    'pendingChanges do tipo que correu bem foi limpo',
    !(st.pendingChanges || []).some(function (c) {
      return c.type === 'insumos';
    }),
    'insumos sincronizou'
  );
  const ultimo = a.toasts[a.toasts.length - 1];
  check('o toast e\' de erro', ultimo && ultimo.kind === 'error', ultimo && ultimo.msg);

  // ── Cenario B: segunda tentativa, agora sem falha ────────────────────────
  console.log('');
  console.log('B) segunda tentativa, o servidor aceita');
  const b = carregar(false);
  b.DataStore['delete']('talhoes', 3);
  return b.DataSync.pushChanges().then(function () {
    const st = b.estado();
    check(
      'o DELETE foi tentado de novo',
      b.fetchCalls.some(function (c) {
        return c.method === 'DELETE';
      }),
      JSON.stringify(b.fetchCalls)
    );
    check('deletedIds ficou vazio', (st.deletedIds.talhoes || []).length === 0);
    check('o talhao saiu do servidor', !b.server.has('talhoes/3'));
    const ultimo = b.toasts[b.toasts.length - 1];
    check('o toast e\' de sucesso', ultimo && ultimo.kind === 'success', ultimo && ultimo.msg);
  });
}).catch(function (e) {
  console.error('ERRO', e);
  process.exitCode = 1;
});