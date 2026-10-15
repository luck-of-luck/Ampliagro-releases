// Pack Loader Runtime - carrega packs de cultura sob demanda
// Faz parte da Fase 5: Packs por cultura

(function (global) {
  'use strict';

  var PACKS_BASE = '/static/packs/';
  var MANIFEST_URL = PACKS_BASE + 'manifest.json';

  // Estado dos packs em localStorage
  var STORAGE_KEY = 'ampliagro-packs-state';
  var STATE_VERSION = 1;

  function getState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return initialState();
      var parsed = JSON.parse(raw);
      if (parsed.version !== STATE_VERSION) return initialState();
      return parsed;
    } catch (e) {
      return initialState();
    }
  }

  function initialState() {
    return {
      version: STATE_VERSION,
      installed: {}, // packId -> { installedAt, version, size }
      downloading: {}, // packId -> promise
      failed: {}, // packId -> { error, at }
    };
  }

  function saveState(state) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.warn('[PackLoader] Falha ao salvar estado:', e);
    }
  }

  // Cache de manifest
  var manifestPromise = null;

  function loadManifest() {
    if (manifestPromise) return manifestPromise;
    manifestPromise = fetch(MANIFEST_URL)
      .then(function (r) {
        if (!r.ok) throw new Error('Manifest ' + r.status);
        return r.json();
      })
      .catch(function (err) {
        console.error('[PackLoader] Falha ao carregar manifest:', err);
        manifestPromise = null; // permite retry
        throw err;
      });
    return manifestPromise;
  }

  // Carrega um pack (subgrupo) - retorna Promise que resolve com o módulo
  function loadPack(packId) {
    var state = getState();

    // Já instalado?
    if (state.installed[packId]) {
      return loadPackModule(packId);
    }

    // Já baixando?
    if (state.downloading[packId]) {
      return state.downloading[packId];
    }

    // Inicia download
    var promise = downloadAndInstall(packId).then(
      function (mod) {
        state.installed[packId] = {
          installedAt: Date.now(),
          version: '1.0.0',
        };
        delete state.downloading[packId];
        delete state.failed[packId];
        saveState(state);
        return mod;
      },
      function (err) {
        state.failed[packId] = { error: String(err), at: Date.now() };
        delete state.downloading[packId];
        saveState(state);
        throw err;
      }
    );

    state.downloading[packId] = promise;
    saveState(state);
    return promise;
  }

  function downloadAndInstall(packId) {
    var url = PACKS_BASE + packId + '.js';
    return fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error('Pack ' + packId + ' ' + r.status);
        return r.text();
      })
      .then(function (code) {
        // Avalia o módulo pack (espera exports globais)
        var mod = evalPack(code, packId);
        return mod;
      });
  }

  function evalPack(code, packId) {
    // Cria escopo isolado para o pack
    var exports = {};
    var module = { exports: exports };
    // eslint-disable-next-line no-eval
    var fn = new Function('module, exports', code);
    fn(module, exports);
    // Marca como pack carregado
    if (typeof window !== 'undefined') {
      window.AmpliagroPacks = window.AmpliagroPacks || {};
      window.AmpliagroPacks[packId] = exports;
    }
    return exports;
  }

  function loadPackModule(packId) {
    // Pack já instalado - carrega do cache se possível, senão re-baixa
    var url = PACKS_BASE + packId + '.js';
    return fetch(url)
      .then(function (r) {
        return r.text();
      })
      .then(function (code) {
        return evalPack(code, packId);
      })
      .catch(function () {
        // Fallback: re-instala
        var state = getState();
        delete state.installed[packId];
        saveState(state);
        return loadPack(packId);
      });
  }

  // API pública
  global.PackLoader = {
    loadManifest: loadManifest,
    loadPack: loadPack,
    isInstalled: function (packId) {
      return !!getState().installed[packId];
    },
    getState: getState,
    uninstallPack: function (packId) {
      var state = getState();
      delete state.installed[packId];
      delete state.downloading[packId];
      delete state.failed[packId];
      saveState(state);
    },
    // Para o wizard: lista todos os packs disponíveis com metadados
    listPacks: function () {
      return loadManifest().then(function (m) {
        var state = getState();
        return m.groups.map(function (g) {
          return {
            group: g,
            subgroups: g.subgroups.map(function (sg) {
              var meta = m.subgroups[sg.id];
              return {
                id: meta.id,
                title: meta.title,
                icon: meta.icon,
                culture_count: meta.culture_count,
                installed: !!state.installed[meta.id],
                failed: !!state.failed[meta.id],
              };
            }),
          };
        });
      });
    },
  };

  // Auto-inicializa manifest ao carregar
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function () {
      loadManifest().catch(function () {});
    });
  }
})(typeof window !== 'undefined' ? window : global);
