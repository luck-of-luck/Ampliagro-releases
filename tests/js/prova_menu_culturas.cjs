/**
 * Executa o `cultures-loader.js` REAL contra o `cultures-config.json` REAL e
 * mede o que chega ao menu (`window.CULTURE_GROUPS`).
 *
 * POR QUE EXECUTAR E NAO CONTAR O JSON
 * =====================================
 * `tests/test_promessas_numericas.py` diz, no seu proprio metodo, que conta
 * "pelo MESMO caminho que o runtime". Nao conta: le o JSON com `json.loads` e
 * conta os grupos. Sao coisas diferentes, e a diferenca e' o achado.
 *
 * O `extrativismo` tem zero culturas no ficheiro — e o loader, em
 * `cultures-loader.js:141`, faz `return` antes do `push`, por isso nunca
 * chega ao menu. O defeito que o teste descreve ("uma entrada de menu que
 * nao faz nada") ja nao existe no runtime.
 *
 * O mesmo se passa com os subgrupos vazios: sao aplanados nas culturas do
 * grupo (`cultures-loader.js:112-121`), e um subgrupo vazio simply nao
 * produz nada. Nao ha secao vazia no ecra.
 *
 * Este script mede o runtime. Se um dia o loader deixar de filtrar, o menu
 * volta a ter entradas vazias — e este script ve isso.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const RAIZ = path.resolve(__dirname, '..', '..');
const CFG = path.join(RAIZ, 'app', 'static', 'data', 'cultures-config.json');
const LOADER = path.join(RAIZ, 'app', 'static', 'js', 'cultures-loader.js');

const config = fs.readFileSync(CFG, 'utf8');
const loader = fs.readFileSync(LOADER, 'utf8');

// Endpoint que o browser pede, servido do disco.
const contexto = {
  window: {},
  document: { getElementById: function () { return null; } },
  localStorage: {
    _d: {},
    getItem: function (k) {
      return Object.prototype.hasOwnProperty.call(this._d, k) ? this._d[k] : null;
    },
    setItem: function (k, v) { this._d[k] = String(v); },
  },
  fetch: function (url) {
    if (String(url).indexOf('cultures-config.json') !== -1) {
      return Promise.resolve({
        ok: true,
        json: function () { return Promise.resolve(JSON.parse(config)); },
      });
    }
    return Promise.resolve({ ok: false, json: function () { return Promise.resolve({}); } });
  },
  console: { warn: function () {}, log: function () {}, error: function () {} },
  setTimeout: function (fn) { fn(); },
  clearTimeout: function () {},
  Promise: Promise,
};
contexto.globalThis = contexto;
contexto.window = contexto;
contexto.self = contexto;
vm.createContext(contexto);
vm.runInContext(loader, contexto, { filename: 'cultures-loader.js' });

// O loader assincrono. Damos-lhe tempo.
setTimeout(() => {
  const grupos = contexto.window.CULTURE_GROUPS || [];
  let ok = true;

  console.log('Grupos que chegam ao menu: ' + grupos.length);
  console.log('');

  for (const g of grupos) {
    const n = (g.cultures || []).length;
    console.log(`  ${String(g.id).padEnd(14)} ${String(g.title).padEnd(26)} ${n} culturas`);
    if (n === 0) {
      console.log('    >>> VAZIO no menu');
      ok = false;
    }

    // Subgrupos efectivamente representados no menu.
    const subs = {};
    for (const c of g.cultures || []) {
      const t = c.subgroup_title || '(sem subgrupo)';
      subs[t] = (subs[t] || 0) + 1;
    }
    for (const [t, k] of Object.entries(subs)) {
      if (k === 0) {
        console.log(`    >>> subgrupo vazio no menu: ${t}`);
        ok = false;
      }
    }
  }

  // Os grupos do ficheiro que NAO chegam ao menu.
  const noMenu = new Set(grupos.map((g) => g.id));
  const doFicheiro = JSON.parse(config).groups || [];
  const escondidos = doFicheiro.filter((g) => !noMenu.has(g.id)).map((g) => g.id);

  console.log('');
  console.log('Grupos no ficheiro mas NAO no menu: ' +
    (escondidos.length ? escondidos.join(', ') : '(nenhum)'));
  console.log('');
  console.log(ok
    ? '>>> OK: nenhum grupo nem subgrupo vazio chega ao menu.'
    : '>>> FALHA: ha entradas vazias no menu.');

  if (!ok) process.exitCode = 1;
}, 400);