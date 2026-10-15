// ────────────────────────────────────────────────────────────────────────
// AMPLIAGRO STORAGE OPTIMIZED — batch reads, debounced writes, memory cache
// ────────────────────────────────────────────────────────────────────────

// ── STUB SEGURO: addFilterTagSafe (deve existir ANTES de initDragSliders) ──
// setPeriodFilter (L5058) chama addFilterTag, mas so definido em L5257.
// Sem isto o ReferenceError ABORTA o bloco inteiro e startResize/
// initWidgetDragging/openAddWidgetModal/openEditSelectedWidget/
// deleteSelectedWidget ficam indefinidos. Fila drenada na definicao real.
window.__addFilterTagQueue = window.__addFilterTagQueue || [];
window.addFilterTagSafe =
  window.addFilterTagSafe ||
  function (label) {
    if (typeof window.addFilterTag === 'function') {
      try {
        return window.addFilterTag(label);
      } catch (e) {}
    }
    window.__addFilterTagQueue.push(label);
  };

var AMPLIAGRO_UID =
  typeof window.AMPLIAGRO_USER_ID === 'number' || typeof window.AMPLIAGRO_USER_ID === 'string'
    ? window.AMPLIAGRO_USER_ID
    : null;

// Keys that should be scoped per user
var SCOPED_PREFIXES = [
  'matrix-',
  'ampliagro-preferences',
  'ampliagro_data',
  'ampliagro-culture-uf',
  'ampliagro-onboard-cultures',
];

function _isScopedKey(key) {
  if (!key) return false;
  for (var i = 0; i < SCOPED_PREFIXES.length; i++) {
    if (key.indexOf(SCOPED_PREFIXES[i]) === 0) return true;
  }
  return false;
}

function scopedKey(key) {
  if (AMPLIAGRO_UID == null || key == null || !_isScopedKey(key)) return key;
  return key + '_u' + AMPLIAGRO_UID;
}

// ────────────────────────────────────────────────────────────────────────
// Memory cache + batched writes
// ────────────────────────────────────────────────────────────────────────
var _lsCache = Object.create(null);
var _lsWriteQueue = Object.create(null);
var _lsWriteTimer = null;
var _lsInitialized = false;

function _flushWrites() {
  _lsWriteTimer = null;
  var keys = Object.keys(_lsWriteQueue);
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    var v = _lsWriteQueue[k];
    try {
      if (v === undefined) localStorage.removeItem(k);
      else localStorage.setItem(k, v);
      _lsCache[k] = v;
    } catch (e) {
      console.warn('[storage] write failed', k, e);
    }
  }
  _lsWriteQueue = Object.create(null);
}

function _queueWrite(key, value) {
  _lsWriteQueue[key] = value;
  if (_lsWriteTimer === null) {
    _lsWriteTimer = setTimeout(_flushWrites, 0); // microtask flush
  }
}

function _primeCache(keys) {
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    if (!Object.prototype.hasOwnProperty.call(_lsCache, k)) {
      try {
        _lsCache[k] = localStorage.getItem(k);
      } catch (e) {
        _lsCache[k] = null;
      }
    }
  }
}

// One-time init: prime cache with all scoped keys (single pass)
function _initStorage() {
  if (_lsInitialized) return;
  _lsInitialized = true;
  var toPrime = [];
  try {
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && _isScopedKey(k)) toPrime.push(k);
    }
  } catch (e) {}
  _primeCache(toPrime);
}

// LEITURA SEMPRE DO ARMAZENAMENTO. O cache em memoria escrevia por tras
// (`sset` -> fila -> `sflush`) mas nao via as escritas feitas por
// `localStorage.setItem` directamente noutros pontos do ficheiro. Resultado:
// `sget` devolvia um valor que ja nao existia no disco, e era esse valor
// velado que voltava a ser desenhado no painel.
//
// Ha mais de vinte escrita direta em `matrix-*` neste ficheiro. Trocar todas
// por `sset` e' a correcao fragile -- a proxima escrita direta e o bug volta. A
// leitura atravessa e nenhum deles consegue mentir. O cache fica como espelho
// de escrita (util para depuracao) e a ESCRITA continua agrupada, que era o
// ganho do cache.
function sget(key) {
  var sk = scopedKey(key);
  try {
    var v = localStorage.getItem(sk);
    _lsCache[sk] = v;
    return v;
  } catch (e) {
    return null;
  }
}

function sset(key, value) {
  var sk = scopedKey(key);
  _queueWrite(sk, value);
}

function sremove(key) {
  var sk = scopedKey(key);
  _queueWrite(sk, undefined);
}

// Synchronous flush for critical saves (persistPresetWidgets, saveCurrentPreset)
function sflush() {
  if (_lsWriteTimer) {
    clearTimeout(_lsWriteTimer);
    _flushWrites();
  }
}

// Migration runs once, uses cache
function migrateScopedStorage() {
  if (AMPLIAGRO_UID == null) return;
  try {
    var keys = [];
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && _isScopedKey(k) && k.indexOf('_u') === -1) keys.push(k);
    }
    // O ESTADO DE PRESET NAO ATRAVESSA FRONTEIRA DE CONTA.
    //
    // Medido 2026-10-14: esta migracao copiava as chaves `matrix-preset-*`
    // sem escopo para a conta que entrou — e uma conta nova herdava os
    // presets ("Tempo", "Logistica") de quem tinha usado o browser antes.
    // O servidor e' a fonte da verdade de cada conta (e o estado de uma
    // conta nova ja' la' esta', com o `base-ia`), por isso o que nao tem
    // escopo nao e' adoptado: fica onde esta' e cada conta le' o que e'
    // seu.
    //
    // Custo conhecido e aceite: o preset criado em sessao anonima nao
    // passa a existir para a conta que faz login a seguir. Perder o
    // proprio preset e' melhor do que receber o de outra pessoa.
    var aMigrar = keys.filter(function (k) {
      return k.indexOf('matrix-preset-') !== 0;
    });
    var hadMatrixState = false;
    for (var i = 0; i < aMigrar.length; i++) {
      var k = aMigrar[i];
      var scoped = scopedKey(k);
      if (!localStorage.getItem(scoped)) {
        localStorage.setItem(scoped, localStorage.getItem(k));
      }
      if (k.indexOf('matrix-') === 0) hadMatrixState = true;
    }
    if (hadMatrixState || sget('matrix-widgets-layout') || sget('matrix-active-preset')) {
      sset('matrix-layout-initialized', '1');
    }
    if (AMPLIAGRO_UID != null && localStorage.getItem('ampliagro-preferences')) {
      localStorage.removeItem('ampliagro-preferences');
    }
  } catch (e) {}
}

// Expose for debugging
window.__storage = {
  getCache: function () {
    return _lsCache;
  },
  flush: sflush,
  prime: _primeCache,
};

// Expose for debugging
window.__storage = {
  getCache: function () {
    return _lsCache;
  },
  flush: sflush,
  prime: _primeCache,
};

// Initialize cache immediately
_initStorage();
migrateScopedStorage();

// ────────────────────────────────────────────────────────────────────────
// Fast deep clone — avoids JSON round-trip for plain objects/arrays
// ────────────────────────────────────────────────────────────────────────
function _fastClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj.getTime());
  if (Array.isArray(obj)) {
    var arr = new Array(obj.length);
    for (var i = 0; i < obj.length; i++) arr[i] = _fastClone(obj[i]);
    return arr;
  }
  // Avoid circular refs and non-plain objects
  if (obj.constructor !== Object && obj.constructor !== Array) return obj;
  var clone = Object.create(Object.getPrototypeOf(obj));
  var keys = Object.keys(obj);
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    clone[k] = _fastClone(obj[k]);
  }
  return clone;
}

// ────────────────────────────────────────────────────────────────────────
// Debounced save queue — batch multiple rapid saves
// ────────────────────────────────────────────────────────────────────────
var _saveTimers = Object.create(null);
function debouncedSave(key, fn, delay) {
  delay = delay || 150;
  if (_saveTimers[key]) clearTimeout(_saveTimers[key]);
  _saveTimers[key] = setTimeout(function () {
    try {
      fn();
    } catch (e) {
      console.warn('[debouncedSave]', key, e);
    }
    delete _saveTimers[key];
  }, delay);
}
function flushDebouncedSaves() {
  for (var k in _saveTimers) {
    if (_saveTimers[k]) {
      clearTimeout(_saveTimers[k]);
    }
    try {
      _saveTimers[k] = null;
    } catch (e) {}
  }
}
window.__debounced = { flush: flushDebouncedSaves };

// Preferences init

(function () {
  // Delega para sistema central se disponível (evita flick/duplicação)
  if (typeof window.restaurarTemaDoUsuario === 'function') {
    try {
      window.restaurarTemaDoUsuario();
    } catch (e) {}
    return;
  }
  try {
    var savedPreferences = JSON.parse(sget('ampliagro-preferences') || '{}');
    var savedThemeMode =
      savedPreferences.theme && savedPreferences.theme.mode
        ? window.normalizarModoTema(savedPreferences.theme.mode)
        : null;
    if (!savedThemeMode) savedThemeMode = window.normalizarModoTema(localStorage.getItem('theme'));
    if (savedThemeMode === 'escuro') {
      document.documentElement.classList.add('dark');
    } else if (savedThemeMode === 'custom') {
      var _customDark =
        savedPreferences.theme &&
        savedPreferences.theme.custom &&
        savedPreferences.theme.custom.dark;
      if (_customDark) document.documentElement.classList.add('dark');
    } else {
      savedThemeMode = savedThemeMode || 'claro';
      document.documentElement.classList.remove('dark');
    }
    if (savedThemeMode) localStorage.setItem('theme', savedThemeMode);
  } catch (e) {
    console.warn('localStorage indisponível para leitura das preferências:', e);
  }
})();

window.getPreferences = function () {
  var raw = sget('ampliagro-preferences');

  var preferences = {};

  try {
    preferences = raw ? JSON.parse(raw) : {};
  } catch (e) {
    preferences = {};
  }

  preferences.theme = preferences.theme || {};

  /* O modo é SEMPRE um dos válidos: claro | escuro | custom */
  preferences.theme.mode = window.normalizarModoTema(preferences.theme.mode) || 'claro';
  preferences.theme.custom = preferences.theme.custom || { dark: true, source: 'ui' };

  return preferences;
};

window.savePreferences = function (nextPreferences) {
  var preferences = window.getPreferences();

  var mergedPreferences = Object.assign({}, preferences, nextPreferences, {
    theme: Object.assign(
      {},
      preferences.theme,
      nextPreferences && nextPreferences.theme ? nextPreferences.theme : {}
    ),
  });

  if (
    mergedPreferences.theme &&
    mergedPreferences.theme.mode === 'custom' &&
    !mergedPreferences.theme.custom
  ) {
    mergedPreferences.theme.custom = { dark: true, source: 'ui' };
  }

  /* Persiste somente modos canônicos (claro | escuro | custom) */
  if (mergedPreferences.theme) {
    var modoCanonico = window.normalizarModoTema(mergedPreferences.theme.mode);
    if (!modoCanonico) {
      if (document.documentElement.classList.contains('custom-theme')) {
        modoCanonico = 'custom';
      } else if (document.documentElement.classList.contains('dark')) {
        modoCanonico = 'escuro';
      } else {
        modoCanonico = 'claro';
      }
    }
    mergedPreferences.theme.mode = modoCanonico;
  }

  sset('ampliagro-preferences', JSON.stringify(mergedPreferences));
  if (mergedPreferences.theme && mergedPreferences.theme.mode)
    localStorage.setItem('theme', mergedPreferences.theme.mode);

  return mergedPreferences;
};

// Função para mudar tema (dark/light/system/custom)

window.normalizeCustomTheme = function (custom) {
  custom = custom || {};
  var normalized = Object.assign(
    {
      dark: true,
      source: 'ui',
      mode: 'custom',
      applyNavbar: true,
      applyWorkspace: true,
      applyWidgetbar: true,
      accent: '#0f9d6e',
      text: '#e9eeec',
      navbar: '#131917',
      workspace: '#0b0f0e',
      card: '#151b19',
      widgetbar: '#131917',
    },
    custom
  );
  if (custom.surface && !custom.navbar) normalized.navbar = custom.surface;
  if (custom.surface && !custom.workspace) normalized.workspace = custom.surface;
  if (custom.surface && !custom.card) normalized.card = custom.surface;
  return normalized;
};

window.openCustomThemeModal = function () {
  var modal = document.getElementById('custom-theme-modal');
  if (!modal) return;
  /* Foto do tema atual p/ o Reverter desfazer os ajustes do modal */
  try {
    var prefs = window.getPreferences ? window.getPreferences() : {};
    window._customThemeSnapshot = JSON.stringify(prefs.theme || {});
  } catch (e) {
    window._customThemeSnapshot = null;
  }
  var active = document.activeElement;
  modal._returnFocus = active && active !== document.body ? active : null;
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('overflow-hidden');
  setTimeout(function () {
    var close = document.getElementById('custom-theme-close');
    if (close) close.focus();
  }, 0);
};

window.closeCustomThemeModal = function (returnFocus) {
  var modal = document.getElementById('custom-theme-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('overflow-hidden');
  if (returnFocus !== false && modal._returnFocus && typeof modal._returnFocus.focus === 'function')
    modal._returnFocus.focus();
};

window.saveCustomTheme = function () {
  /* O modal já aplica e salva a cada ajuste (applyCustomTheme);
                 Salvar só fecha. */
  window.closeCustomThemeModal();
};

window.revertCustomTheme = function () {
  /* Volta para a foto tirada ao abrir o modal */
  try {
    if (window._customThemeSnapshot) {
      var snap = JSON.parse(window._customThemeSnapshot);
      if (window.savePreferences) window.savePreferences({ theme: snap });
      if (snap.mode === 'custom' && typeof window.applyCustomTheme === 'function') {
        window.applyCustomTheme(snap.custom, false);
      } else if (typeof window.aplicarTema === 'function') {
        window.aplicarTema(snap.mode || 'claro');
      }
      if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
      if (typeof window.refreshModePanel === 'function') window.refreshModePanel();
    }
  } catch (e) {}
  window.closeCustomThemeModal();
};

window.setTheme = function (theme) {
  /* Delega para o sistema de temas.
                 Modos válidos: claro(dia) | escuro(noite) | custom(personalizado).
                 Legados (light/dark/system/dia/noite) são normalizados. */
  var modo = window.normalizarModoTema(theme);

  /* Personalizado: aplica as cores salvas no JSON do usuário */
  if (modo === 'custom') {
    var prefs = window.getPreferences();
    prefs.theme.mode = 'custom';
    window.savePreferences({ theme: prefs.theme });
    try {
      localStorage.setItem('theme', 'custom');
    } catch (e) {}
    if (typeof window.applyCustomTheme === 'function') {
      window.applyCustomTheme(prefs.theme.custom, false);
    }
    if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
    window.syncModeDropdown('custom');
    return;
  }

  var alvo = modo || 'claro';
  if (typeof window.aplicarTema === 'function') {
    window.aplicarTema(alvo);
  } else {
    document.documentElement.classList.toggle('dark', alvo === 'escuro');
    document.documentElement.removeAttribute('data-tema');
    try {
      localStorage.setItem('ampliagro_tema', alvo);
    } catch (e) {}
    try {
      localStorage.setItem('theme', alvo);
    } catch (e) {}
  }
  if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
  window.syncModeDropdown(alvo);
  window.savePreferences({ theme: { mode: alvo } });
  try {
    if (typeof window.__setThemeExpected === 'function')
      window.__setThemeExpected(alvo, alvo === 'escuro');
  } catch (e) {}
};

window.syncModeDropdown = function (mode) {
  var btn = document.getElementById('nav-mode-btn');
  if (!btn) return;
  var label = btn.querySelector('.nav-mode-label');
  if (!label) return;
  /* Rótulo sempre é um modo válido — nunca "Aparência" */
  if (!window.normalizarModoTema(mode)) {
    mode = document.documentElement.classList.contains('custom-theme')
      ? 'custom'
      : window.modoAtualDom
        ? window.modoAtualDom()
        : 'claro';
  }
  label.textContent = window.nomeModoTema(mode);
};

// Inicializar estado ativo dos botões de tema

window.applyCustomTheme = function (custom) {
  var readInputs = arguments.length < 2 || arguments[1] !== false;
  // #region agent log
  if (window.__dbgNav)
    window.__dbgNav('E', 'pagina-index.js:applyCustomTheme', 'applyCustomTheme', {
      readInputs: readInputs,
      inDark: !!(custom && custom.dark),
      inAccent: custom && custom.accent,
      willSaveCustom: true,
      before: window.__dbgThemeSnap ? window.__dbgThemeSnap() : null,
    });
  // #endregion
  custom = window.normalizeCustomTheme(custom || window.getPreferences().theme.custom);
  var html = document.documentElement;
  var inputs = {
    accent: 'custom-theme-accent',
    text: 'custom-theme-text',
    navbar: 'custom-theme-navbar',
    workspace: 'custom-theme-workspace',
    card: 'custom-theme-card',
    widgetbar: 'custom-theme-widgetbar',
  };
  Object.keys(inputs).forEach(function (key) {
    var input = document.getElementById(inputs[key]);
    if (!input) return;
    if (readInputs && input.value) custom[key] = input.value;
    if (!readInputs) input.value = custom[key];
  });
  var options = {
    applyNavbar: 'custom-theme-option-navbar',
    applyWorkspace: 'custom-theme-option-workspace',
    applyWidgetbar: 'custom-theme-option-widgetbar',
    dark: 'custom-theme-option-dark',
  };
  Object.keys(options).forEach(function (key) {
    var input = document.getElementById(options[key]);
    if (!input) return;
    if (readInputs) custom[key] = input.checked;
    else input.checked = !!custom[key];
  });

  ['custom-theme-navbar', 'custom-theme-workspace', 'custom-theme-widgetbar'].forEach(
    function (className) {
      html.classList.remove(className);
    }
  );
  html.classList.add('custom-theme');
  if (custom.applyNavbar) html.classList.add('custom-theme-navbar');
  if (custom.applyWorkspace) html.classList.add('custom-theme-workspace');
  if (custom.applyWidgetbar) html.classList.add('custom-theme-widgetbar');
  html.classList.toggle('dark', !!custom.dark);

  var root = html.style;
  root.setProperty('--theme-accent', custom.accent);
  root.setProperty('--theme-text', custom.text);
  root.setProperty('--theme-navbar', custom.navbar);
  root.setProperty('--theme-workspace', custom.workspace);
  root.setProperty('--theme-card', custom.card);
  root.setProperty('--theme-widgetbar', custom.widgetbar);
  root.setProperty('--color-ncs-orange-amber', custom.accent);
  root.setProperty('--ncs-orange-amber', custom.accent);
  root.setProperty('--ncs-blue-dark', custom.navbar);
  root.setProperty('--color-ncs-blue-dark', custom.navbar);
  root.setProperty('--ncs-blue-light', custom.text);
  root.setProperty('--color-ncs-blue-light', custom.text);

  var options = {
    applyNavbar: 'custom-theme-option-navbar',
    applyWorkspace: 'custom-theme-option-workspace',
    applyWidgetbar: 'custom-theme-option-widgetbar',
    dark: 'custom-theme-option-dark',
  };
  Object.keys(options).forEach(function (key) {
    var input = document.getElementById(options[key]);
    if (input) input.checked = !!custom[key];
  });
  var preferences = window.getPreferences();
  preferences.theme.custom = custom;
  preferences.theme.mode = 'custom'; // Ensure mode is set to custom
  window.savePreferences({ theme: preferences.theme });
  try {
    if (typeof window.__setThemeExpected === 'function')
      window.__setThemeExpected('custom', !!custom.dark);
  } catch (e) {}
  if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
};

window.toggleCustomThemeMode = function () {
  var preferences = window.getPreferences();
  var custom = window.normalizeCustomTheme(preferences.theme.custom);
  custom.dark = !custom.dark;
  window.applyCustomTheme(custom, false);
};

// ── Command Palette ──
var COMMAND_CATALOG = [];

function buildCommandCatalog() {
  var cmds = [
    {
      id: 'goto-dashboard',
      label: 'Ir para Dashboard',
      icon: 'bi-speedometer2',
      category: 'Navegacao',
      action: function () {
        switchTab('dashboard');
        closeCommandPalette();
      },
    },
    {
      id: 'goto-financeiro',
      label: 'Ir para Financeiro',
      icon: 'bi-currency-dollar',
      category: 'Navegacao',
      action: function () {
        switchTab('financeiro');
        closeCommandPalette();
      },
    },
    {
      id: 'goto-estoque',
      label: 'Ir para Estoque',
      icon: 'bi-box-seam',
      category: 'Navegacao',
      action: function () {
        switchTab('estoque');
        closeCommandPalette();
      },
    },
    {
      id: 'goto-campo',
      label: 'Ir para Campo',
      icon: 'bi-tree',
      category: 'Navegacao',
      action: function () {
        switchTab('campo');
        closeCommandPalette();
      },
    },
    {
      id: 'goto-pecuaria',
      label: 'Ir para Pecuaria',
      icon: 'bi-hospital',
      category: 'Navegacao',
      action: function () {
        switchTab('pecuaria');
        closeCommandPalette();
      },
    },
    {
      id: 'toggle-dark',
      label: 'Alternar Modo Noturno',
      icon: 'bi-moon-stars',
      category: 'Acoes',
      action: function () {
        toggleCustomThemeMode();
        closeCommandPalette();
      },
    },
    {
      id: 'toggle-edit',
      label: 'Alternar Modo Edicao',
      icon: 'bi-pencil-square',
      category: 'Acoes',
      action: function () {
        toggleWidgetEditMode();
        closeCommandPalette();
      },
    },
    {
      id: 'export-data',
      label: 'Exportar Dados (.agro)',
      icon: 'bi-download',
      category: 'Acoes',
      action: function () {
        exportSystemSnapshot();
        closeCommandPalette();
      },
    },
    {
      id: 'open-calc',
      label: 'Abrir Calculadoras',
      icon: 'bi-calculator',
      category: 'Ferramentas',
      action: function () {
        closeCommandPalette();
        openCalculatorModal();
      },
    },
    {
      id: 'open-notebook',
      label: 'Abrir Caderno de Campo',
      icon: 'bi-journal-text',
      category: 'Ferramentas',
      action: function () {
        closeCommandPalette();
        openFieldNotebook();
      },
    },
    {
      id: 'open-spreadsheet',
      label: 'Abrir Entrada Rapida',
      icon: 'bi-table',
      category: 'Ferramentas',
      action: function () {
        closeCommandPalette();
        openQuickSpreadsheet();
      },
    },
    {
      id: 'open-products',
      label: 'Abrir Produtos e Precificacao',
      icon: 'bi-box-seam',
      category: 'Ferramentas',
      action: function () {
        closeCommandPalette();
        openProductRegistry();
      },
    },
  ];
  if (window.CulturesLoader && CulturesLoader.getConfig) {
    var cfg = CulturesLoader.getConfig();
    if (cfg && cfg.groups) {
      cfg.groups.forEach(function (g) {
        if (g.subgroups) {
          g.subgroups.forEach(function (sg) {
            if (sg.cultures) {
              sg.cultures.forEach(function (c) {
                cmds.push({
                  id: 'culture-' + c.id,
                  label: 'Ir para ' + (c.title || c.id),
                  icon: c.icon || 'bi-flower1',
                  category: g.title || g.id,
                  action: function () {
                    showCultureMiniPanel(c.id, g.id);
                    closeCommandPalette();
                  },
                });
              });
            }
          });
        }
      });
    }
  }
  COMMAND_CATALOG = cmds;
}

window.openCommandPalette = function () {
  if (!COMMAND_CATALOG.length) buildCommandCatalog();
  var modal = document.getElementById('command-palette');
  var panel = document.getElementById('command-palette-panel');
  var input = document.getElementById('command-palette-input');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
    if (input) {
      input.value = '';
      input.focus();
    }
  });
  filterCommandPalette('');
};

window.closeCommandPalette = function () {
  var modal = document.getElementById('command-palette');
  var panel = document.getElementById('command-palette-panel');
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }, 150);
};

var cpSelectedIndex = -1;

window.filterCommandPalette = function (query) {
  var results = document.getElementById('command-palette-results');
  if (!results) return;
  var q = (query || '').toLowerCase().trim();
  var filtered = [];
  if (!q) {
    filtered = COMMAND_CATALOG.slice(0, 20);
  } else {
    COMMAND_CATALOG.forEach(function (cmd) {
      if (
        cmd.label.toLowerCase().indexOf(q) >= 0 ||
        (cmd.category || '').toLowerCase().indexOf(q) >= 0
      ) {
        filtered.push(cmd);
      }
    });
  }
  cpSelectedIndex = -1;
  if (filtered.length === 0) {
    results.innerHTML =
      '<div class="text-[9px] text-slate-400 text-center py-4">Nenhum comando encontrado</div>';
    return;
  }
  var html = '';
  var currentCat = '';
  filtered.slice(0, 30).forEach(function (cmd, idx) {
    if (cmd.category !== currentCat) {
      currentCat = cmd.category;
      html +=
        '<div class="text-[7px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-2 pb-0.5">' +
        currentCat +
        '</div>';
    }
    html +=
      '<div class="cp-item flex items-center gap-2 px-3 py-1.5 cursor-pointer text-[10px] text-slate-700 dark:text-slate-200 rounded-lg mx-1 transition-colors" data-cp-index="' +
      idx +
      '" onclick="executeCommand(' +
      idx +
      ')"><i class="bi ' +
      cmd.icon +
      ' text-emerald-500 text-[10px] w-4 text-center"></i><span>' +
      cmd.label +
      '</span></div>';
  });
  results.innerHTML = html;
};

window.executeCommand = function (idx) {
  var filtered = getFilteredCommands();
  if (idx >= 0 && idx < filtered.length) {
    filtered[idx].action();
  }
};

function getFilteredCommands() {
  var input = document.getElementById('command-palette-input');
  var q = (input ? input.value : '').toLowerCase().trim();
  if (!q) return COMMAND_CATALOG.slice(0, 20);
  var result = [];
  COMMAND_CATALOG.forEach(function (cmd) {
    if (
      cmd.label.toLowerCase().indexOf(q) >= 0 ||
      (cmd.category || '').toLowerCase().indexOf(q) >= 0
    ) {
      result.push(cmd);
    }
  });
  return result.slice(0, 30);
}

document.addEventListener('keydown', function (event) {
  var cp = document.getElementById('command-palette');
  if (cp && !cp.classList.contains('hidden')) {
    if (event.key === 'Escape') {
      closeCommandPalette();
      event.preventDefault();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      cpSelectedIndex = Math.min(cpSelectedIndex + 1, getFilteredCommands().length - 1);
      updateCpSelection();
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      cpSelectedIndex = Math.max(cpSelectedIndex - 1, 0);
      updateCpSelection();
      return;
    }
    if (event.key === 'Enter' && cpSelectedIndex >= 0) {
      event.preventDefault();
      executeCommand(cpSelectedIndex);
      return;
    }
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
    event.preventDefault();
    openCommandPalette();
    return;
  }
  var modal = document.getElementById('custom-theme-modal');
  if (!modal || modal.classList.contains('hidden')) return;
  if (event.key === 'Escape') {
    event.preventDefault();
    window.closeCustomThemeModal();
    return;
  }
  if (event.key !== 'Tab') return;
  var focusable = modal.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])');
  if (!focusable.length) return;
  var first = focusable[0];
  var last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

function updateCpSelection() {
  document.querySelectorAll('#command-palette-results .cp-item').forEach(function (el, i) {
    el.classList.toggle('selected', i === cpSelectedIndex);
    if (i === cpSelectedIndex) el.scrollIntoView({ block: 'nearest' });
  });
}

// ── Calculadoras Agronomicas ──
window.openCalculatorModal = function () {
  var modal = document.getElementById('calculator-modal');
  var panel = document.getElementById('calculator-modal-panel');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
  });
  switchCalcTab('pulverizacao');
};

window.closeCalculatorModal = function () {
  var modal = document.getElementById('calculator-modal');
  var panel = document.getElementById('calculator-modal-panel');
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }, 150);
};

window.switchCalcTab = function (tab) {
  document.querySelectorAll('.calc-tab').forEach(function (t) {
    t.classList.remove('active-calc-tab');
  });
  var btn = document.querySelector('.calc-tab[data-calc-tab="' + tab + '"]');
  if (btn) btn.classList.add('active-calc-tab');
  var content = document.getElementById('calc-content');
  if (!content) return;
  var html = '';
  if (tab === 'pulverizacao') {
    html =
      '<div class="space-y-2"><p class="text-[9px] text-slate-500 mb-2">Calcule o volume de calda por hectare para calibrar seu pulverizador.</p>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Produto (Defensivo)</label><select id="calc-pv-prod" onchange="selectPVProduct()" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">' +
      window.getProductSelectOptions('defensivo') +
      '</select></div>' +
      '<div class="grid grid-cols-3 gap-2"><div><label class="text-[8px] font-medium text-slate-500">Velocidade (km/h)</label><input type="number" id="calc-pv-vel" value="5" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Vazao do Bico (L/min)</label><input type="number" id="calc-pv-vaz" value="0.8" step="0.1" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Espacamento (m)</label><input type="number" id="calc-pv-esp" value="0.5" step="0.05" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div></div>' +
      '<div class="flex gap-2"><button onclick="calcPulverizacao()" class="px-3 py-1 text-[9px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white transition-all">Calcular</button>' +
      '<button onclick="document.getElementById(\'calc-pv-result\').textContent=\'\';" class="px-2 py-1 text-[8px] font-semibold rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-slate-200 transition-all">Limpar</button></div>' +
      '<div id="calc-pv-result" class="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 pt-1"></div></div>';
  } else if (tab === 'pearson') {
    html =
      '<div class="space-y-2"><p class="text-[9px] text-slate-500 mb-2">Quadrado de Pearson: calcule a proporcao ideal de ingredientes para atingir a proteina bruta desejada.</p>' +
      '<div class="grid grid-cols-3 gap-2"><div><label class="text-[8px] font-medium text-slate-500">PB Ingrediente A (%)</label><input type="number" id="calc-pear-a" value="8" step="0.1" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">PB Ingrediente B (%)</label><input type="number" id="calc-pear-b" value="45" step="0.1" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">PB Meta (%)</label><input type="number" id="calc-pear-meta" value="18" step="0.1" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div></div>' +
      '<button onclick="calcPearson()" class="px-3 py-1 text-[9px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white transition-all">Calcular</button>' +
      '<div id="calc-pear-result" class="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 pt-1"></div></div>';
  } else if (tab === 'npk') {
    html =
      '<div class="space-y-2"><p class="text-[9px] text-slate-500 mb-2">Calcule a quantidade de fertilizante com base na expectativa de colheita e analise de solo.</p>' +
      '<div class="grid grid-cols-2 gap-2"><div><label class="text-[8px] font-medium text-slate-500">Produto Cadastrado</label><select id="calc-npk-prod" onchange="selectNPKProduct()" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">' +
      window.getProductSelectOptions('fertilizante') +
      '</select></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Cultura</label><select id="calc-npk-cultura" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200"><option value="milho">Milho</option><option value="soja">Soja</option><option value="trigo">Trigo</option><option value="cafe">Cafe</option><option value="cana">Cana-de-acucar</option></select></div></div>' +
      '<div class="grid grid-cols-2 gap-2"><div><label class="text-[8px] font-medium text-slate-500">Expectativa (sc/ha)</label><input type="number" id="calc-npk-exp" value="60" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Fonte NPK (N-P-K)</label><input type="text" id="calc-npk-fonte" value="08-30-10" placeholder="Ex: 08-30-10" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div></div>' +
      '<div class="flex gap-2"><button onclick="calcNPK()" class="px-3 py-1 text-[9px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white transition-all">Calcular</button>' +
      "<button onclick=\"document.getElementById('calc-npk-prod').value='';document.getElementById('calc-npk-fonte').value='';document.getElementById('calc-npk-result').textContent='';\" class=\"px-2 py-1 text-[8px] font-semibold rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-slate-200 transition-all\">Limpar</button></div>" +
      '<div id="calc-npk-result" class="text-[11px] text-emerald-700 dark:text-emerald-400 pt-1"></div></div>';
  } else if (tab === 'biometria') {
    html =
      '<div class="space-y-2"><p class="text-[9px] text-slate-500 mb-2">Estime a produtividade antes da colheita com base na contagem de campo.</p>' +
      '<div class="grid grid-cols-4 gap-2"><div><label class="text-[8px] font-medium text-slate-500">Plantas/m<sup>2</sup></label><input type="number" id="calc-bio-plantas" value="12" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Estruturas/planta</label><input type="number" id="calc-bio-estrut" value="1.5" step="0.1" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Graos/estrutura</label><input type="number" id="calc-bio-graos" value="36" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div>' +
      '<div><label class="text-[8px] font-medium text-slate-500">Peso 1000 graos (g)</label><input type="number" id="calc-bio-peso" value="280" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800"></div></div>' +
      '<button onclick="calcBiometria()" class="px-3 py-1 text-[9px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white transition-all">Calcular</button>' +
      '<div id="calc-bio-result" class="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 pt-1"></div></div>';
  }
  content.innerHTML = html;
};

window.selectPVProduct = function () {
  var sel = document.getElementById('calc-pv-prod');
  if (!sel || !sel.value) return;
  if (!window.ProductRegistry) return;
  var p = ProductRegistry.getById(sel.value);
  if (p) {
    sel.options[sel.selectedIndex].setAttribute('data-preco', p.preco || 0);
  }
};

window.calcPulverizacao = function () {
  var vel = parseFloat(document.getElementById('calc-pv-vel').value);
  var vaz = parseFloat(document.getElementById('calc-pv-vaz').value);
  var esp = parseFloat(document.getElementById('calc-pv-esp').value);
  if (!vel || !vaz || !esp) {
    document.getElementById('calc-pv-result').textContent = 'Preencha todos os campos';
    return;
  }
  var lha = (600 * vaz) / (vel * esp);
  var html =
    '<span class="text-[10px] font-normal text-slate-500">Volume de calda:</span> ' +
    lha.toFixed(1) +
    ' L/ha';
  var prodSel = document.getElementById('calc-pv-prod');
  if (prodSel && prodSel.value) {
    var opt = prodSel.options[prodSel.selectedIndex];
    var preco = parseFloat(opt.getAttribute('data-preco')) || 0;
    if (preco > 0) {
      var dose = 1;
      var custoHa = preco * dose;
      html +=
        '<br><span class="text-[10px] font-normal text-slate-500">Custo estimado:</span> <span class="text-emerald-600 font-semibold">R$ ' +
        custoHa.toFixed(2) +
        '/ha</span>';
    }
  }
  document.getElementById('calc-pv-result').innerHTML = html;
};

window.calcPearson = function () {
  var a = parseFloat(document.getElementById('calc-pear-a').value);
  var b = parseFloat(document.getElementById('calc-pear-b').value);
  var meta = parseFloat(document.getElementById('calc-pear-meta').value);
  if (!a || !b || !meta) {
    document.getElementById('calc-pear-result').textContent = 'Preencha todos os campos';
    return;
  }
  if (meta <= b || meta >= a) {
    document.getElementById('calc-pear-result').textContent =
      'A meta deve estar entre ' + b + '% e ' + a + '%';
    return;
  }
  var parteA = (((meta - b) / (a - b)) * 100).toFixed(1);
  var parteB = (100 - parseFloat(parteA)).toFixed(1);
  document.getElementById('calc-pear-result').innerHTML =
    'Proporcao: <span class="text-emerald-600">' +
    parteA +
    '%</span> do Ingrediente A + <span class="text-emerald-600">' +
    parteB +
    '%</span> do Ingrediente B';
};

window.selectNPKProduct = function () {
  var sel = document.getElementById('calc-npk-prod');
  if (!sel || !sel.value) return;
  if (!window.ProductRegistry) return;
  var p = ProductRegistry.getById(sel.value);
  if (p && p.nome) {
    var match = p.nome.match(/(\d{1,3})\s*[-\.]?\s*(\d{1,3})\s*[-\.]?\s*(\d{1,3})/);
    if (match) {
      document.getElementById('calc-npk-fonte').value = match[1] + '-' + match[2] + '-' + match[3];
    }
  }
};

window.calcNPK = function () {
  var exp = parseFloat(document.getElementById('calc-npk-exp').value);
  var fonte = (document.getElementById('calc-npk-fonte').value || '').trim();
  var cultura = document.getElementById('calc-npk-cultura').value || 'milho';
  var prodSel = document.getElementById('calc-npk-prod');
  var precoProduto = 0;
  if (prodSel && prodSel.value && window.ProductRegistry) {
    var p = ProductRegistry.getById(prodSel.value);
    if (p) precoProduto = parseFloat(p.preco) || 0;
  }
  if (!exp || !fonte) {
    document.getElementById('calc-npk-result').textContent = 'Preencha todos os campos';
    return;
  }
  var partes = fonte.split('-');
  if (partes.length !== 3) {
    document.getElementById('calc-npk-result').textContent =
      'Formato invalido. Use N-P-K (ex: 08-30-10)';
    return;
  }
  var n = parseFloat(partes[0]) / 100,
    p = parseFloat(partes[1]) / 100,
    k = parseFloat(partes[2]) / 100;
  var necessidades = {
    milho: { n: 1.2, p: 0.5, k: 0.8 },
    soja: { n: 0.05, p: 0.8, k: 1.2 },
    trigo: { n: 1.0, p: 0.4, k: 0.6 },
    cafe: { n: 0.6, p: 0.4, k: 0.5 },
    cana: { n: 1.0, p: 0.3, k: 1.0 },
  };
  var cult = cultura;
  var need = necessidades[cult] || necessidades.milho;
  var qtn = (exp * need.n) / n;
  var qtp = (exp * need.p) / p;
  var qtk = (exp * need.k) / k;
  var htmlResult =
    'Para <strong>' +
    exp +
    ' sc/ha</strong> de <strong>' +
    cult +
    '</strong> com ' +
    fonte +
    ':<br>' +
    '&bull; Nitrogenio: <span class="font-semibold">' +
    (isFinite(qtn) ? qtn.toFixed(1) : 'N/A') +
    ' kg/ha</span><br>' +
    '&bull; Fosforo: <span class="font-semibold">' +
    (isFinite(qtp) ? qtp.toFixed(1) : 'N/A') +
    ' kg/ha</span><br>' +
    '&bull; Potassio: <span class="font-semibold">' +
    (isFinite(qtk) ? qtk.toFixed(1) : 'N/A') +
    ' kg/ha</span><br>';
  if (precoProduto > 0) {
    var qtdTotalKg =
      (isFinite(qtn) ? qtn : 0) + (isFinite(qtp) ? qtp : 0) + (isFinite(qtk) ? qtk : 0);
    var custoHa = (qtdTotalKg / 1000) * precoProduto;
    htmlResult +=
      '&bull; Custo fertilizante: <span class="font-semibold text-emerald-600">R$ ' +
      custoHa.toFixed(2) +
      '/ha</span><br>';
  }
  htmlResult +=
    '<span class="text-[8px] text-slate-400">*Valores estimados. Consulte um engenheiro agronomo.</span>';
  document.getElementById('calc-npk-result').innerHTML = htmlResult;
};

window.calcBiometria = function () {
  var pl = parseFloat(document.getElementById('calc-bio-plantas').value);
  var es = parseFloat(document.getElementById('calc-bio-estrut').value);
  var gr = parseFloat(document.getElementById('calc-bio-graos').value);
  var pe = parseFloat(document.getElementById('calc-bio-peso').value);
  if (!pl || !es || !gr || !pe) {
    document.getElementById('calc-bio-result').textContent = 'Preencha todos os campos';
    return;
  }
  var prod = (pl * es * gr * pe) / 60000;
  document.getElementById('calc-bio-result').innerHTML =
    '<span class="text-[10px] font-normal text-slate-500">Produtividade estimada:</span> ' +
    prod.toFixed(1) +
    ' sc/ha';
};

// ── Planilha Rapida ──
window.openQuickSpreadsheet = function () {
  var modal = document.getElementById('quick-spreadsheet-modal');
  var panel = document.getElementById('quick-spreadsheet-panel');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
  });
  rebuildQuickSheet();
};

window.closeQuickSpreadsheet = function () {
  var modal = document.getElementById('quick-spreadsheet-modal');
  var panel = document.getElementById('quick-spreadsheet-panel');
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }, 150);
};

window.rebuildQuickSheet = function () {
  var type = document.getElementById('qs-type').value;
  var rows = parseInt(document.getElementById('qs-rows').value, 10) || 10;
  var container = document.getElementById('qs-grid-container');
  if (!container) return;
  var headers = [],
    fields = [];
  if (type === 'producao') {
    headers = ['Cultura', 'Talhao', 'Area (ha)', 'Producao (sc)', 'Data'];
    fields = ['cultura', 'talhao', 'area', 'producao', 'data'];
  } else if (type === 'pesagem') {
    headers = ['Animal/Lote', 'Peso (kg)', 'Data', 'Observacao'];
    fields = ['animal', 'peso', 'data', 'obs'];
  } else if (type === 'insumo') {
    headers = ['Insumo', 'Quantidade', 'Unidade', 'Talhao', 'Data'];
    fields = ['insumo', 'qtd', 'unid', 'talhao', 'data'];
  } else if (type === 'financeiro') {
    headers = ['Descricao', 'Valor (R$)', 'Tipo', 'Categoria', 'Data'];
    fields = ['desc', 'valor', 'tipo', 'categoria', 'data'];
  } else if (type === 'produto') {
    headers = ['Nome', 'Categoria', 'Marca', 'Preco (R$)', 'Unidade', 'Estoque'];
    fields = ['nome', 'categoria', 'marca', 'preco', 'unidade', 'estoque'];
  }
  var html =
    '<table class="w-full text-[9px] border-collapse"><thead><tr class="bg-slate-50 dark:bg-slate-800/50">';
  headers.forEach(function (h) {
    html +=
      '<th class="text-left py-1 px-1 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">' +
      h +
      '</th>';
  });
  html += '</thead><tbody>';
  for (var i = 0; i < rows; i++) {
    html += '<tr class="qs-row">';
    fields.forEach(function (f) {
      var ph =
        type === 'financeiro' && f === 'tipo'
          ? 'Receita/Despesa'
          : f.charAt(0).toUpperCase() + f.slice(1);
      html +=
        '<td class="border-b border-slate-100 dark:border-slate-800 p-0"><input class="qs-input w-full bg-transparent text-slate-700 dark:text-slate-200 px-1 py-0.5 focus:outline-none focus:bg-emerald-50 dark:focus:bg-emerald-900/20 text-[9px]" placeholder="' +
        ph +
        '" data-field="' +
        f +
        '"></td>';
    });
    html += '</tr>';
  }
  html += '</tbody></table>';
  container.innerHTML = html;
  setTimeout(function () {
    var first = container.querySelector('.qs-input');
    if (first) first.focus();
  }, 100);
  container.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      var inputs = container.querySelectorAll('.qs-input');
      var current = document.activeElement;
      var idx = Array.from(inputs).indexOf(current);
      if (idx >= 0 && idx + 1 < inputs.length) {
        var nextIdx = idx + 1;
        var nextRow = Math.floor(nextIdx / fields.length);
        if (nextRow >= rows) return;
        inputs[nextIdx].focus();
      }
    }
    if (e.key === 'Tab') {
      e.preventDefault();
      var inputs = container.querySelectorAll('.qs-input');
      var current = document.activeElement;
      var idx = Array.from(inputs).indexOf(current);
      var dir = e.shiftKey ? -1 : 1;
      var next = idx + dir;
      if (next >= 0 && next < inputs.length) inputs[next].focus();
    }
  });
};

window.saveQuickSheet = function () {
  var type = document.getElementById('qs-type').value;
  var rows = [];
  document.querySelectorAll('.qs-row').forEach(function (row) {
    var data = {};
    row.querySelectorAll('.qs-input').forEach(function (inp) {
      data[inp.getAttribute('data-field')] = inp.value.trim();
    });
    var hasData = Object.values(data).some(function (v) {
      return v !== '';
    });
    if (hasData) rows.push(data);
  });
  if (rows.length === 0) {
    showToast('Nenhum dado preenchido', 'warning');
    return;
  }
  if (type === 'produto' && window.ProductRegistry) {
    rows.forEach(function (r) {
      if (r.nome) {
        ProductRegistry.save({
          nome: r.nome,
          categoria: r.categoria || 'insumo_geral',
          marca: r.marca || '',
          preco: parseFloat(r.preco) || 0,
          unidade: r.unidade || 'un',
          quantidade: parseFloat(r.estoque) || 0,
        });
      }
    });
  }
  if (type === 'producao' && window.ProductionRegistry) {
    rows.forEach(function (r) {
      if (r.cultura && r.producao) {
        ProductionRegistry.save({
          cultureId:
            'cultura-' +
            r.cultura
              .toLowerCase()
              .normalize('NFD')
              .replace(/[^a-z0-9]/g, ''),
          quantity: parseFloat(r.producao) || 0,
          area: parseFloat(r.area) || 0,
          plantingDate: r.data || new Date().toISOString().slice(0, 10),
        });
      }
    });
  }
  // Só entra na fila offline o que tem endpoint de ESCRITA.
  //
  // `financeiro` saiu de propósito: `/api/financeiro/` é
  // `@api_view(["GET"])` — é o agregador do painel, não um CRUD.
  // A fila aceitava o registo, marcava `_pending`, e o POST
  // levava 405 em CADA tentativa, para sempre. O produtor via
  // "salvos com sucesso" e o lançamento não chegava ao servidor.
  // O CRUD real é `/api/lancamentos/`; até a folha de cálculo
  // falar a forma desse serializer, este tipo avisa que precisa
  // de rede em vez de fingir que guardou.
  if (window.DataStore && type !== 'produto') {
    var storeType = { producao: 'safras', pesagem: 'animais', insumo: 'insumos' }[type] || null;
    if (storeType) {
      rows.forEach(function (r) {
        DataStore.save(storeType, r);
      });
    }
  }
  closeQuickSpreadsheet();
  var _naFila =
    window.DataStore &&
    type !== 'produto' &&
    ({ producao: 1, pesagem: 1, insumo: 1 }[type] ? 1 : 0);
  if (_naFila && !navigator.onLine) {
    // A fila é real e o sync existe — mas só quando houver rede.
    showToast(
      rows.length + ' registro(s) guardados neste aparelho. Sincronizam quando houver internet.',
      'info'
    );
  } else if (!_naFila && type === 'financeiro') {
    showToast(
      rows.length +
        ' lançamento(s) precisam de ligação. Sem internet, o lançamento não pode ser gravado — leve-o para o registo financeiro.',
      'warning'
    );
  } else {
    showToast(rows.length + ' registro(s) salvos com sucesso!', 'success');
  }
};

// ── Caderno de Campo ──
window.openFieldNotebook = function (cultureId) {
  var modal = document.getElementById('field-notebook-modal');
  var panel = document.getElementById('field-notebook-panel');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
  });
  renderFieldNotebook(cultureId || '');
};

window.closeFieldNotebook = function () {
  var modal = document.getElementById('field-notebook-modal');
  var panel = document.getElementById('field-notebook-panel');
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }, 150);
};

window.printFieldNotebook = function () {
  window.print();
};

window.renderFieldNotebook = function (cultureId) {
  var content = document.getElementById('field-notebook-content');
  if (!content) return;
  var now = new Date();
  var dateStr = now.toLocaleDateString('pt-BR');
  var propNome = 'Minha Propriedade';
  if (window.widgetDataCache && window.widgetDataCache.propriedade) {
    propNome = window.widgetDataCache.propriedade.nome || propNome;
  }
  var records = [];
  if (window.ProductionRegistry) {
    var all = ProductionRegistry.getAll() || [];
    if (cultureId)
      all = all.filter(function (r) {
        return r.cultureId === cultureId;
      });
    records = all;
  }
  var cultureName = cultureId
    ? cultureId.replace('cultura-', '').replace(/-/g, ' ')
    : 'Todas as Culturas';
  cultureName = cultureName.charAt(0).toUpperCase() + cultureName.slice(1);
  var html = '<div class="max-w-[700px] mx-auto py-4">';
  html +=
    '<h1 class="text-base font-bold text-slate-800 dark:text-slate-100 mb-1">Caderno de Campo</h1>';
  html +=
    '<div class="text-[8px] text-slate-400 mb-4">' +
    propNome +
    ' | Gerado em ' +
    dateStr +
    ' | Cultura: ' +
    cultureName +
    '</div>';
  if (records.length === 0) {
    html +=
      '<div class="text-[10px] text-slate-400 py-8 text-center">Nenhum registro de producao encontrado para esta cultura.</div></div>';
    content.innerHTML = html;
    return;
  }
  html +=
    '<table class="w-full text-[9px] border-collapse mb-4"><thead><tr class="bg-slate-100 dark:bg-slate-800"><th class="text-left py-1 px-2 border border-slate-300 dark:border-slate-600">Data</th><th class="text-left py-1 px-2 border border-slate-300 dark:border-slate-600">Cultura</th><th class="text-right py-1 px-2 border border-slate-300 dark:border-slate-600">Area (ha)</th><th class="text-right py-1 px-2 border border-slate-300 dark:border-slate-600">Producao</th><th class="text-left py-1 px-2 border border-slate-300 dark:border-slate-600">Obs</th></tr></thead><tbody>';
  records.forEach(function (r) {
    var cname = (r.cultureId || '').replace('cultura-', '').replace(/-/g, ' ');
    html +=
      '<tr><td class="py-0.5 px-2 border border-slate-200 dark:border-slate-700">' +
      (r.plantingDate || r.date || '—') +
      '</td>' +
      '<td class="py-0.5 px-2 border border-slate-200 dark:border-slate-700">' +
      cname +
      '</td>' +
      '<td class="py-0.5 px-2 border border-slate-200 dark:border-slate-700 text-right">' +
      (r.area || '—') +
      '</td>' +
      '<td class="py-0.5 px-2 border border-slate-200 dark:border-slate-700 text-right font-semibold">' +
      (r.quantity || '—') +
      '</td>' +
      '<td class="py-0.5 px-2 border border-slate-200 dark:border-slate-700">' +
      (r.notes || '') +
      '</td></tr>';
  });
  html += '</tbody></table>';
  html +=
    '<div class="text-[7px] text-slate-400 text-center mt-6 border-t border-slate-200 dark:border-slate-700 pt-2">Documento gerado pelo Ampliagro OS | Valido como registro de boas praticas agricolas</div>';
  html += '</div>';
  content.innerHTML = html;
};

// ── Snapshot / Backup .agro ──
window.exportSystemSnapshot = function () {
  var snapshot = {
    meta: {
      version: '1.0',
      exportedAt: new Date().toISOString(),
      appName: 'Ampliagro OS',
      description: 'Snapshot completo do sistema',
    },
    widgets: {},
    userConfig: {
      uf: sget('ampliagro-culture-uf') || '',
      theme: localStorage.getItem('theme') || 'light',
      preset: sget('matrix-active-preset') || '',
    },
    dataStore: { data: {} },
    productionRecords: [],
  };
  if (typeof widgets !== 'undefined') {
    Object.keys(widgets).forEach(function (id) {
      var w = widgets[id];
      snapshot.widgets[id] = {
        gridX: w.gridX,
        gridY: w.gridY,
        gridW: w.gridW,
        gridH: w.gridH,
        visible: w.visible,
        title: w.title,
        metricKey: w.metricKey,
        source: w.source,
        widgetType: w.widgetType,
      };
    });
  }
  if (window.DataStore) {
    var dsTypes = [
      'propriedades',
      'talhoes',
      'safras',
      'culturas',
      'financeiro',
      'insumos',
      'funcionarios',
      'animais',
      'maquinarios',
      'estoque',
      'apiario',
    ];
    dsTypes.forEach(function (t) {
      if (typeof DataStore.getAll === 'function') snapshot.dataStore.data[t] = DataStore.getAll(t);
    });
  }
  if (window.ProductionRegistry) {
    snapshot.productionRecords = ProductionRegistry.getAll() || [];
  }
  if (window.ProductRegistry) {
    snapshot.products = ProductRegistry.getAll() || [];
  }
  try {
    var layout = sget('matrix-widgets-layout');
    if (layout) snapshot.widgetLayout = JSON.parse(layout);
  } catch (e) {}
  var blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' });
  var url = URL.createObjectURL(blob);
  var link = document.createElement('a');
  link.href = url;
  link.download = 'ampliagro-backup-' + new Date().toISOString().slice(0, 10) + '.agro';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  showToast('Snapshot exportado com sucesso!', 'success');
};

window.importSystemSnapshot = function () {
  var input = document.createElement('input');
  input.type = 'file';
  input.accept = '.agro,.json';
  input.onchange = function (e) {
    var file = e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (ev) {
      try {
        var snap = JSON.parse(ev.target.result);
        if (!snap || !snap.meta) {
          showToast('Arquivo .agro invalido', 'error');
          return;
        }
        if (snap.widgets && typeof widgets !== 'undefined') {
          Object.keys(snap.widgets).forEach(function (id) {
            widgets[id] = snap.widgets[id];
          });
          saveWidgetsLayout();
        }
        if (snap.dataStore && snap.dataStore.data && window.DataStore) {
          var dsTypes = [
            'propriedades',
            'talhoes',
            'safras',
            'culturas',
            'financeiro',
            'insumos',
            'funcionarios',
            'animais',
            'maquinarios',
            'estoque',
            'apiario',
          ];
          dsTypes.forEach(function (t) {
            if (snap.dataStore.data[t] && typeof DataStore.save === 'function') {
              snap.dataStore.data[t].forEach(function (item) {
                DataStore.save(t, item);
              });
            }
          });
        }
        if (snap.productionRecords && window.ProductionRegistry) {
          snap.productionRecords.forEach(function (r) {
            ProductionRegistry.save(r);
          });
        }
        if (snap.products && window.ProductRegistry) {
          snap.products.forEach(function (p) {
            ProductRegistry.save(p);
          });
        }
        if (snap.userConfig) {
          if (snap.userConfig.uf) sset('ampliagro-culture-uf', snap.userConfig.uf);
          if (snap.userConfig.theme) localStorage.setItem('theme', snap.userConfig.theme);
        }
        renderWidgetsOnMatrix();
        showToast('Snapshot restaurado com sucesso!', 'success');
      } catch (err) {
        showToast('Erro ao ler arquivo: ' + err.message, 'error');
      }
    };
    reader.readAsText(file);
  };
  input.click();
};

// ── Product Registry ──
var currentProductId = null;

window.openProductRegistry = function () {
  var modal = document.getElementById('product-registry-modal');
  var panel = document.getElementById('product-registry-panel');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
  });
  showProductTab('lista');
};

window.closeProductRegistry = function () {
  var modal = document.getElementById('product-registry-modal');
  var panel = document.getElementById('product-registry-panel');
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }, 150);
};

window.showProductTab = function (tab) {
  var container = document.getElementById('product-registry-content');
  if (!container) return;
  document.querySelectorAll('#product-registry-tabs button').forEach(function (b) {
    b.classList.remove('bg-emerald-600', 'text-white');
    b.classList.add('bg-slate-100', 'dark:bg-slate-800', 'text-slate-600', 'dark:text-slate-300');
  });
  var tabBtn = document.getElementById('prod-tab-' + tab);
  if (tabBtn) {
    tabBtn.classList.remove(
      'bg-slate-100',
      'dark:bg-slate-800',
      'text-slate-600',
      'dark:text-slate-300'
    );
    tabBtn.classList.add('bg-emerald-600', 'text-white');
  }
  if (tab === 'lista') renderProductList();
  else if (tab === 'cadastrar') renderProductForm();
  else if (tab === 'precos') renderProductPriceTable();
};

window.renderProductList = function () {
  var container = document.getElementById('product-registry-content');
  var products = window.ProductRegistry ? ProductRegistry.getAll() : [];
  var cats = window.ProductRegistry ? ProductRegistry.getCategories() : [];
  var html = '<div class="space-y-1">';
  if (products.length === 0) {
    html +=
      '<div class="text-center py-8 text-slate-400"><i class="bi bi-box-seam text-2xl block mb-2"></i>Nenhum produto cadastrado.<br><button onclick="showProductTab(\'cadastrar\')" class="mt-2 px-3 py-1 text-[9px] font-semibold rounded-full bg-emerald-600 text-white hover:bg-emerald-700 transition-all">+ Cadastrar Produto</button></div>';
    container.innerHTML = html;
    return;
  }
  html += '<div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5">';
  products.forEach(function (p) {
    var catLabel = p.categoria || '—';
    var found = cats.find(function (c) {
      return c.id === p.categoria;
    });
    if (found) catLabel = found.label;
    var icon = 'bi-box';
    if (p.categoria === 'fertilizante') icon = 'bi-droplet';
    else if (p.categoria === 'defensivo') icon = 'bi-shield-check';
    else if (p.categoria === 'semente') icon = 'bi-flower1';
    else if (p.categoria === 'racao') icon = 'bi-cup-hot';
    html +=
      '<div class="flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-700/60 hover:border-emerald-300 dark:hover:border-emerald-700 transition-all bg-white dark:bg-slate-800/30 cursor-pointer" onclick="editProduct(\'' +
      p.id +
      '\')">' +
      '<div class="w-7 h-7 flex items-center justify-center rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"><i class="bi ' +
      icon +
      ' text-[10px]"></i></div>' +
      '<div class="flex-1 min-w-0"><div class="text-[10px] font-semibold text-slate-800 dark:text-slate-100 truncate">' +
      (p.nome || 'Sem nome') +
      '</div>' +
      '<div class="text-[7px] text-slate-400">' +
      catLabel +
      (p.marca ? ' &middot; ' + p.marca : '') +
      '</div></div>' +
      '<div class="text-right"><div class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">R$ ' +
      (parseFloat(p.preco) || 0).toFixed(2) +
      '</div>' +
      '<div class="text-[7px] text-slate-400">' +
      (p.unidade || 'un') +
      '</div></div>' +
      '<button onclick="event.stopPropagation();deleteProduct(\'' +
      p.id +
      '\')" class="w-5 h-5 flex items-center justify-center rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-300 hover:text-red-500"><i class="bi bi-trash3 text-[8px]"></i></button>' +
      '</div>';
  });
  html += '</div></div>';
  container.innerHTML = html;
};

window.renderProductForm = function (editId) {
  var container = document.getElementById('product-registry-content');
  var p = editId && window.ProductRegistry ? ProductRegistry.getById(editId) : null;
  currentProductId = editId || null;
  var cats = window.ProductRegistry ? ProductRegistry.getCategories() : [];
  var unidades = window.ProductRegistry ? ProductRegistry.getUnidades() : ['kg', 'L', 'sc', 'un'];
  var nome = p ? p.nome : '';
  var cat = p ? p.categoria : 'fertilizante';
  var marca = p ? p.marca : '';
  var preco = p ? p.preco : '';
  var unidade = p ? p.unidade : 'kg';
  var qtd = p ? p.quantidade : '';
  var html =
    '<div class="max-w-md mx-auto py-2">' +
    '<div class="text-[11px] font-bold text-slate-800 dark:text-slate-100 mb-3">' +
    (editId ? 'Editar Produto' : 'Novo Produto') +
    '</div>' +
    '<div class="space-y-2">' +
    '<div><label class="text-[8px] font-medium text-slate-500 block mb-0.5">Nome do Produto</label>' +
    '<input id="prod-form-nome" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-emerald-400" value="' +
    nome +
    '" placeholder="Ex: Super Simples 08-30-10"></div>' +
    '<div class="grid grid-cols-2 gap-2">' +
    '<div><label class="text-[8px] font-medium text-slate-500 block mb-0.5">Categoria</label>' +
    '<select id="prod-form-categoria" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">';
  cats.forEach(function (c) {
    html +=
      '<option value="' +
      c.id +
      '"' +
      (cat === c.id ? ' selected' : '') +
      '>' +
      c.label +
      '</option>';
  });
  html +=
    '</select></div>' +
    '<div><label class="text-[8px] font-medium text-slate-500 block mb-0.5">Marca / Fornecedor</label>' +
    '<input id="prod-form-marca" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-emerald-400" value="' +
    marca +
    '" placeholder="Ex: Mosaic, Syngenta"></div>' +
    '</div>' +
    '<div class="grid grid-cols-3 gap-2">' +
    '<div><label class="text-[8px] font-medium text-slate-500 block mb-0.5">Preco Unitario (R$)</label>' +
    '<input id="prod-form-preco" type="number" step="0.01" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-emerald-400" value="' +
    preco +
    '" placeholder="0,00"></div>' +
    '<div><label class="text-[8px] font-medium text-slate-500 block mb-0.5">Unidade</label>' +
    '<select id="prod-form-unidade" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200">';
  unidades.forEach(function (u) {
    html +=
      '<option value="' + u + '"' + (unidade === u ? ' selected' : '') + '>' + u + '</option>';
  });
  html +=
    '</select></div>' +
    '<div><label class="text-[8px] font-medium text-slate-500 block mb-0.5">Qtd. Estoque</label>' +
    '<input id="prod-form-qtd" type="number" step="0.1" class="w-full text-[10px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-emerald-400" value="' +
    qtd +
    '" placeholder="0"></div>' +
    '</div>' +
    '<div class="flex gap-2 pt-1">' +
    '<button onclick="saveProductForm()" class="flex-1 px-3 py-1.5 text-[9px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"><i class="bi bi-check-lg mr-1"></i>Salvar Produto</button>' +
    '<button onclick="showProductTab(\'lista\')" class="px-3 py-1.5 text-[9px] font-semibold rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 transition-all">Cancelar</button>' +
    '</div>' +
    '</div></div>';
  container.innerHTML = html;
};

window.saveProductForm = function () {
  if (!window.ProductRegistry) {
    showToast('ProductRegistry nao disponivel', 'error');
    return;
  }
  var nome = document.getElementById('prod-form-nome').value.trim();
  if (!nome) {
    showToast('Informe o nome do produto', 'warning');
    return;
  }
  var data = {
    nome: nome,
    categoria: document.getElementById('prod-form-categoria').value,
    marca: document.getElementById('prod-form-marca').value.trim(),
    preco: parseFloat(document.getElementById('prod-form-preco').value) || 0,
    unidade: document.getElementById('prod-form-unidade').value,
    quantidade: parseFloat(document.getElementById('prod-form-qtd').value) || 0,
  };
  if (currentProductId) data.id = currentProductId;
  ProductRegistry.save(data);
  showToast('Produto salvo com sucesso!', 'success');
  currentProductId = null;
  showProductTab('lista');
};

window.editProduct = function (id) {
  renderProductForm(id);
};

window.deleteProduct = function (id) {
  if (!window.ProductRegistry) return;
  if (!confirm('Remover este produto?')) return;
  ProductRegistry.remove(id);
  showProductTab('lista');
};

window.renderProductPriceTable = function () {
  var container = document.getElementById('product-registry-content');
  var products = window.ProductRegistry ? ProductRegistry.getAll() : [];
  var html = '<div class="py-1">';
  html +=
    '<div class="text-[8px] text-slate-400 mb-2">Tabela consolidada de precos dos produtos cadastrados.</div>';
  if (products.length === 0) {
    html += '<div class="text-center py-8 text-slate-400">Nenhum produto cadastrado.</div></div>';
    container.innerHTML = html;
    return;
  }
  html +=
    '<table class="w-full text-[9px] border-collapse"><thead><tr class="bg-slate-50 dark:bg-slate-800/50">' +
    '<th class="text-left py-1 px-1.5 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">Produto</th>' +
    '<th class="text-left py-1 px-1.5 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">Categoria</th>' +
    '<th class="text-left py-1 px-1.5 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">Marca</th>' +
    '<th class="text-right py-1 px-1.5 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">Preco</th>' +
    '<th class="text-right py-1 px-1.5 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">Unid.</th>' +
    '<th class="text-right py-1 px-1.5 font-semibold text-slate-500 border-b border-slate-200 dark:border-slate-700">Estoque</th>' +
    '</tr></thead><tbody>';
  var cats = window.ProductRegistry ? ProductRegistry.getCategories() : [];
  products.forEach(function (p) {
    var catLabel = p.categoria || '—';
    var found = cats.find(function (c) {
      return c.id === p.categoria;
    });
    if (found) catLabel = found.label;
    html +=
      '<tr class="hover:bg-slate-50 dark:hover:bg-slate-800/20"><td class="py-0.5 px-1.5 border-b border-slate-100 dark:border-slate-800 font-medium">' +
      (p.nome || '—') +
      '</td>' +
      '<td class="py-0.5 px-1.5 border-b border-slate-100 dark:border-slate-800">' +
      catLabel +
      '</td>' +
      '<td class="py-0.5 px-1.5 border-b border-slate-100 dark:border-slate-800">' +
      (p.marca || '—') +
      '</td>' +
      '<td class="py-0.5 px-1.5 border-b border-slate-100 dark:border-slate-800 text-right font-semibold text-emerald-600">R$ ' +
      (parseFloat(p.preco) || 0).toFixed(2) +
      '</td>' +
      '<td class="py-0.5 px-1.5 border-b border-slate-100 dark:border-slate-800 text-right">' +
      (p.unidade || 'un') +
      '</td>' +
      '<td class="py-0.5 px-1.5 border-b border-slate-100 dark:border-slate-800 text-right">' +
      (parseFloat(p.quantidade) || 0).toFixed(1) +
      '</td></tr>';
  });
  html += '</tbody></table></div>';
  container.innerHTML = html;
};

window.getProductPrice = function (productId) {
  if (!window.ProductRegistry) return 0;
  var p = ProductRegistry.getById(productId);
  return p ? parseFloat(p.preco) || 0 : 0;
};

window.getProductsByCategoryValue = function (categoryId) {
  if (!window.ProductRegistry) return [];
  return ProductRegistry.getByCategory(categoryId);
};

window.getProductSelectOptions = function (categoryFilter) {
  if (!window.ProductRegistry) return '';
  var products = categoryFilter
    ? ProductRegistry.getByCategory(categoryFilter)
    : ProductRegistry.getAll();
  var html = '<option value="">-- Selecione um produto --</option>';
  products.forEach(function (p) {
    html +=
      '<option value="' +
      p.id +
      '" data-preco="' +
      (parseFloat(p.preco) || 0) +
      '" data-unidade="' +
      (p.unidade || '') +
      '">' +
      p.nome +
      (p.marca ? ' (' + p.marca + ')' : '') +
      '</option>';
  });
  return html;
};

// ── QR Code ──
window.gerarQRCode = function (tipo, id, nome) {
  var modal = document.getElementById('qr-modal');
  if (!modal) {
    var html =
      '<div id="qr-modal" onclick="closeQRModal()" class="fixed inset-0 z-[1002] hidden items-center justify-center bg-black/40 backdrop-blur-sm">' +
      '<div onclick="event.stopPropagation()" class="bg-white dark:bg-[#131917] rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700/60 p-4 transition-all duration-200 scale-95 opacity-0" style="width:280px" id="qr-modal-panel">' +
      '<div class="text-center"><div id="qr-code-container" class="flex justify-center mb-2"></div>' +
      '<p id="qr-label" class="text-[9px] font-medium text-slate-600 dark:text-slate-300 mb-2"></p>' +
      '<button onclick="printQRCode()" class="px-2 py-1 text-[8px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white mr-1"><i class="bi bi-printer"></i> Imprimir</button>' +
      '<button onclick="closeQRModal()" class="px-2 py-1 text-[8px] font-semibold rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300">Fechar</button></div></div></div>';
    var div = document.createElement('div');
    div.innerHTML = html;
    document.body.appendChild(div);
    modal = document.getElementById('qr-modal');
  }
  var panel = document.getElementById('qr-modal-panel');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
  });
  document.getElementById('qr-label').textContent = nome || tipo + ': ' + id;
  var container = document.getElementById('qr-code-container');
  container.innerHTML = '';
  var baseUrl = window.location.origin + '/app/#/rastrear/' + tipo + '/' + id;
  if (typeof QRCode !== 'undefined') {
    new QRCode(container, {
      text: baseUrl,
      width: 180,
      height: 180,
      colorDark: '#0a7d56',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.H,
    });
  } else {
    container.innerHTML =
      '<div class="w-[180px] h-[180px] flex items-center justify-center bg-slate-100 dark:bg-slate-800 rounded-lg text-[8px] text-slate-400">QR Code: ' +
      baseUrl +
      '</div>';
  }
};

window.closeQRModal = function () {
  var modal = document.getElementById('qr-modal');
  var panel = document.getElementById('qr-modal-panel');
  if (!modal || !panel) return;
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }, 150);
};

window.printQRCode = function () {
  var container = document.getElementById('qr-code-container');
  if (!container) return;
  var qrImg = container.querySelector('img');
  var win = window.open('', '_blank');
  if (win) {
    win.document.write(
      '<html><head><title>QR Code</title><style>body{display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;font-family:sans-serif;}img{width:200px;height:200px;}p{font-size:12px;color:#666;margin-top:8px;}</style></head><body>'
    );
    if (qrImg) win.document.write(qrImg.outerHTML);
    win.document.write('<p>' + (document.getElementById('qr-label').textContent || '') + '</p>');
    win.document.write('</body></html>');
    win.document.close();
    setTimeout(function () {
      win.print();
    }, 500);
  }
};

// ── Rastreamento via URL (SPA route) ──
window.handleTrackingRoute = function (tipo, id) {
  var target = null;
  if (tipo === 'insumo' && window.DataStore) target = DataStore.getById('insumos', id);
  else if (tipo === 'animal' && window.DataStore) target = DataStore.getById('animais', id);
  else if (tipo === 'producao' && window.ProductionRegistry) {
    var all = ProductionRegistry.getAll() || [];
    for (var i = 0; i < all.length; i++) {
      if (all[i].id === id) {
        target = all[i];
        break;
      }
    }
  }
  if (target) {
    showToast('Item encontrado: ' + (target.nome || target.cultureId || id), 'success');
  } else {
    showToast('Item nao encontrado: ' + id, 'warning');
  }
};

window.initThemeButtons = function () {
  var html = document.documentElement;

  var themeButtons = document.querySelectorAll('.theme-phase-btn, .nav-theme-btn');

  var preferences = window.getPreferences();

  var savedTheme =
    preferences.theme && preferences.theme.mode
      ? preferences.theme.mode
      : localStorage.getItem('theme');
  if (savedTheme === 'config_page') savedTheme = 'custom';

  if (savedTheme === 'custom' && preferences.theme.custom)
    window.applyCustomTheme(preferences.theme.custom, false);

  var isDark = html.classList.contains('dark');
  if (!savedTheme && isDark) savedTheme = 'dark';
  if (!savedTheme && !isDark) savedTheme = 'light';

  var activeIndex =
    savedTheme === 'light' ? 0 : savedTheme === 'dark' ? 1 : savedTheme === 'system' ? 2 : 3;

  if (!savedTheme) activeIndex = isDark ? 1 : 0;

  themeButtons.forEach(function (btn, index) {
    btn.classList.toggle('active', index === activeIndex);
  });
};

document.addEventListener('DOMContentLoaded', function () {
  initThemeButtons();

  try {
    updateConnectionStatus();
  } catch (e) {
    console.warn('Falha ao atualizar status de conexão:', e);
  }
});

// Dropdown handlers

var dropdownTimeout = null;

window.toggleDropdown = function (dropdownId) {
  var navbar = document.getElementById('nav-premium');
  if (navbar) {
    document.querySelectorAll("#nav-premium [id$='-dropdown']").forEach(function (d) {
      d.classList.remove('open');
      d.classList.add('hidden');
    });
  }
  if (dropdownTimeout) {
    clearTimeout(dropdownTimeout);
    dropdownTimeout = null;
  }
  var dropdown = document.getElementById(dropdownId + '-dropdown');
  if (dropdown) {
    if (dropdown.classList.contains('hidden') || !dropdown.classList.contains('open')) {
      dropdown.classList.remove('hidden');
      dropdown.classList.add('open');
      dropdownTimeout = setTimeout(function () {
        dropdown.classList.remove('open');
        dropdown.classList.add('hidden');
        dropdownTimeout = null;
      }, 5000);
    } else {
      dropdown.classList.remove('open');
      dropdown.classList.add('hidden');
    }
  }
};

document.addEventListener('click', function (event) {
  var navbar = document.getElementById('nav-premium');

  var dashboardAppbar = document.getElementById('dashboard-appbar');

  var widgetBar = document.getElementById('widget-bar');

  if (navbar && !navbar.contains(event.target)) {
    document.querySelectorAll("#nav-premium [id$='-dropdown']").forEach(function (d) {
      d.classList.add('hidden');
    });
    if (dropdownTimeout) {
      clearTimeout(dropdownTimeout);
      dropdownTimeout = null;
    }
  }

  if (widgetBar && !widgetBar.contains(event.target)) {
    document.querySelectorAll("#widget-bar [id$='-dropdown']").forEach(function (d) {
      d.classList.add('hidden');
    });
  }

  if (dashboardAppbar && !dashboardAppbar.contains(event.target)) {
    document.querySelectorAll("#dashboard-appbar [id$='-dropdown']").forEach(function (d) {
      d.classList.add('hidden');
    });
  }
});

function updateConnectionStatus() {
  var statusEl = document.getElementById('connection-status');
  if (!statusEl) return;
  var circle = statusEl.querySelector('svg circle');
  if (!circle) return;
  var isOnline = navigator.onLine;
  circle.setAttribute('fill', isOnline ? '#0f9d6e' : '#ef4444');
}

window.addEventListener('online', updateConnectionStatus);

window.addEventListener('offline', updateConnectionStatus);

try {
  updateConnectionStatus();
} catch (e) {
  console.warn('Falha ao atualizar status de conexão:', e);
}

// ============================================

// Widget Matrix System - Unificado

// ============================================

let widgetEditMode = false;
// widgets is declared globally in dashboard-desktop.js and exposed as window.widgets
let chartInstances = {};
var widgetDataCache = null;
let customMode = false;
// Expor flags para sincronizar com widget-bar-intelligent.js / dashboard-desktop.js
window.widgetEditMode = widgetEditMode;
window.customMode = customMode;
window.__setEditFlags = function (isEdit) {
  widgetEditMode = !!isEdit;
  customMode = !!isEdit;
  window.widgetEditMode = widgetEditMode;
  window.customMode = customMode;
  window._widgetsMatrixInitialized = window._widgetsMatrixInitialized; // no-op
  if (window.widgetbarState) window.widgetbarState.isCustomMode = !!isEdit;
  if (!isEdit) {
    document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
      el.classList.remove('widget-selected');
    });
    try {
      _selectedWidgetId = null;
    } catch (e) {}
    try {
      window._selectedWidgetId = null;
    } catch (e) {}
    try {
      if (typeof updateValuesList === 'function') updateValuesList(null);
    } catch (e) {}
  }
  try {
    if (typeof window.updateWidgetBarSelectionIndicator === 'function')
      window.updateWidgetBarSelectionIndicator();
  } catch (e) {}
};
window.__getEditFlags = function () {
  return !!(
    widgetEditMode ||
    customMode ||
    (window.widgetbarState && window.widgetbarState.isCustomMode)
  );
};

let currentPeriod = 'month';

let activeFilters = [];

let financialMode = 'ambos';

let searchTimeout = null;

// Grid responsivo — células responsivas via CSS 1fr (revert 256→64 para estabilidade)
const GRID_COLS = 64;
let GRID_ROWS = 40;
const GRID_PAD = 12;
const GRID_GAP = 6;

/* `col(25)` — 25% da largura, em colunas.
 *
 * MEDIDO 2026-10-05: os presets estavam escritos em NUMEROS ABSOLUTOS de
 * coluna, e nao em fraccoes — e cada um assumia uma grelha diferente:
 *
 *     base-ia       gridX+gridW max = 24   (grelha de 24)
 *     (o preset de demo que vivia aqui foi removido: nascia em toda a
 *      conta e trazia series de culturas que ninguem registou)
 *     GRID_COLS               = 64          (grelha de 64)
 *
 * Tres grelhas em coexistencia. Com `GRID_COLS = 64`, o `gridW: 8` do
 * `base-ia` dava 8/64 = 12,5% — o widget media 120 px e a sua area util
 * 64 px. O rotulo "Área Total" precisa de 65 px. Cortava por 1 px.
 *
 * E a grelha ja foi 256 antes ("revert 256→64"), o que prova que mudar o
 * numero global ja aconteceu antes e leva sempre a revistar a presenca de
 * cada numero.
 *
 * Com `col(25)` o preset passa a dizer o que quer dizer — "metade", "quarto",
 * "75%" — e acompanha qualquer `GRID_COLS` futuro. Um numero absoluto
 * numa grelha e' um numero que fica errado em silencio.
 *
 * `gridH` mantem-se absoluto: as linhas nao sao uma fraccao da largura, e
 * `GRID_ROWS` e' a altura total, nao uma escala a preservar.
 */
function col(percent) {
  return Math.round((GRID_COLS * percent) / 100);
}

// Logger absoluto — escreve no console toda vez que o dashboard for atualizado
window.dashboardLog = function (acao, detalhes) {
  var ts =
    new Date().toLocaleTimeString('pt-BR') + '.' + String(Date.now() % 1000).padStart(3, '0');
  var caller = '';
  try {
    caller = (new Error().stack || '').split('\n')[3] || '';
    caller = caller
      .replace(/^\s*at\s+/, '')
      .trim()
      .substring(0, 80);
  } catch (e) {}
  var wCount = 0;
  try {
    wCount = Object.keys(window.widgets || window._absoluteWidgets || {}).length;
  } catch (e) {}
  var preset = '';
  try {
    preset = (typeof sget === 'function' ? sget('matrix-active-preset') : '') || '—';
  } catch (e) {}
  var payload = {
    ts: ts,
    caller: caller,
    widgets: wCount,
    preset: preset,
    url: location.pathname + location.search,
  };
  if (detalhes && typeof detalhes === 'object')
    Object.keys(detalhes).forEach(function (k) {
      payload[k] = detalhes[k];
    });
  else if (detalhes) payload.info = detalhes;
  console.log(
    '%c[Dashboard] ' + acao,
    'background:#0f9d6e;color:#fff;padding:2px 6px;border-radius:4px;font-weight:700;',
    payload
  );
  try {
    if (window._dashboardLogBuffer)
      window._dashboardLogBuffer.push({ acao: acao, payload: payload });
  } catch (e) {}
};
window._dashboardLogBuffer = window._dashboardLogBuffer || [];
// Atalho puro para forçar e logar
window.dashboardForceOnce = function () {
  console.warn('[Dashboard] forceDashboardCorrect() solicitado manualmente');
  if (window.forceDashboardCorrect) window.forceDashboardCorrect();
};
window.GRID_COLS = GRID_COLS;
Object.defineProperty(window, 'GRID_ROWS', {
  get: function () {
    return GRID_ROWS;
  },
  set: function (v) {
    GRID_ROWS = v;
  },
  configurable: true,
});
window.GRID_PAD = GRID_PAD;
window.GRID_GAP = GRID_GAP;

// ============================================
// CULTURE GROUPS - Carregado de cultures-config.json pelo CulturesLoader
// Fallback basico enquanto o JSON nao carrega
// ============================================
var CULTURE_GROUPS = [];
var dashboardData = null;
// A AmplIA nao inventa metricas de uma fazenda.
//
// Este bloco servia, para TODAS as culturas e TODOS os produtores, um
// "Valor da Saca: R$ 1.450,00", "Producao Total: 12.750 sacas" e
// "Receita Estimada: R$ 18,5 M". Nao era um valor por omissao silencioso:
// era o ultimo recurso de `getFallbackMetrics`, e o `catch` do caminho de
// dados reais chegava aqui sempre que a API falhava. Uma queda de rede
// mostrava a um produtor a receita de ninguem.
//
// Fica `CULTURE_METRICS` declarado e vazio porque `cultures-loader.js` e
// `data-provider.js` o consultam por condicao. Um objeto vazio e' a forma
// de dizer "nenhuma metrica inventada" sem partir quem o le.
var CULTURE_METRICS = {};

// UM SO PRESET NASCE COM A CONTA — e' o `base-ia`.
//
// Aqui havia quatro presets de DEMOSTRACAO (plantio/sol/internet/agua),
// cada um com config especifica distinta, e todos eram semeados em TODA
// a conta. Medido 2026-10-14: uma conta nova acordava com `custom-agua`
// na barra de widgets, com series de arroz e milho que ninguem registou
// — e o `custom-agua` era tambem o fallback de `clonePresetWidgets`, o
// que punha os widgets dele dentro do preset de qualquer produtor.
//
// A semeadura agora tem UM preset: o de entrada, que e' do produto.
// Todo o resto nasce da mao do produtor ou da IA.
var _deletedPresets = [];
try {
  _deletedPresets = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
  if (!Array.isArray(_deletedPresets)) _deletedPresets = [];
} catch (e) {
  _deletedPresets = [];
}
var _allHardcoded = {
  // PRESET-BASE DE ENTRADA. Fica PRIMEIRO de proposito: `PRESETS` e
  // construido a partir da ordem deste object, e varios sítios do
  // codigo caem em `Object.keys(PRESETS)[0]` quando nao ha preset
  // activo. Sendo o primeiro, esses fallbacks passam a devolver o
  // preset-base.
  //
  // Conteudo: contexto (o que e a fazenda, quanto area, que tempo)
  // e orientacao (o que precisa de atencao, o que fazer hoje).
  // O chat da IA e' global (`#ia-dock`), por isso nao entra aqui.
  //
  // Em fraccoes, nao em colunas. As fraccoes vem do preset ORIGINAL, que
  // estava escrito para uma grelha de 24 colunas: `gridW: 24` era a
  // largura toda, `gridW: 8` um terco. Sobre `GRID_COLS = 64` esses
  // numeros davam 12,5% — o widget media 120 px com 64 px uteis, e o
  // rotulo "Área Total" precisa de 65 px. Cortava por 1 px. Ver `col()`.
  'base-ia': {
    'widget-resumo': { gridX: col(0), gridY: 0, gridW: col(100), gridH: 10, visible: true },
    'kpi-alertas': { gridX: col(0), gridY: 10, gridW: col(33.3), gridH: 8, visible: true },
    'list-tarefas': { gridX: col(33.3), gridY: 10, gridW: col(66.7), gridH: 8, visible: true },
    'kpi-area': { gridX: col(0), gridY: 18, gridW: col(33.3), gridH: 8, visible: true },
    'kpi-clima': { gridX: col(33.3), gridY: 18, gridW: col(66.7), gridH: 8, visible: true },
  },
};
window.PRESET_WIDGETS_JSON = {};

// UM PRODUTOR NAO PLANTA TUDO.
//
// O preset de entrada foi escrito para um produtor de arroz e milho,
// e era entregue a toda a gente. Quem cultiva cafe acordava com
// "PRODUTIVIDADE DE ARROZ" e "AREA MILHO" no ecra: rotulos que
// descrevem uma lavoura que a pessoa nao tem, para a mesma pessoa que
// fica com a impressao de que o sistema so sabe falar de arroz.
//
// Tirar o numero inventado nao chega, porque o numero foi so a
// metadade do problema. O TITULO tambem mente. Aqui remove-se o
// widget de uma cultura que o produtor nao tem — e nao se o troca
// por outro, porque isso seria inventar tambem.
//
// Quem nao tem nenhuma cultura cadastrada fica com os widgets
// genericos (kpi-caixa, kpi-alertas). E' um preset mais pequeno,
// que e' o preset certo para quem ainda nao planta nada.
var _culturasProdutor = window._BOOTSTRAP.culturas;
function _pertenceAoProdutor(wid) {
  if (String(wid).indexOf('cultura-') !== 0) return true; // generico
  if (!_culturasProdutor.length) return false; // nao tem lavoura
  var slug = String(wid).slice('cultura-'.length).split('_')[0];
  return _culturasProdutor.indexOf(slug) !== -1;
}
// A MESMA regra tem de valer em todo o lado onde o preset e'
// copiado de `_allHardcoded`. Ha um bloco "demo-clean v11" mais
// abaixo cuja unica funcao e' repor o hardcoded quando o preset
// dele difere — e foi ele que desfazia o filtro, repondo o arroz
// e o milho. Um filtro que so corre na semeadura e' um filtro que
// o primeiro Script que mexer no preset apaga.
function _filtrarParaProdutor(widgets) {
  var out = {};
  Object.keys(widgets || {}).forEach(function (wid) {
    if (_pertenceAoProdutor(wid)) out[wid] = widgets[wid];
  });
  return out;
}
var _filtroJaAplicado = false;
Object.keys(_allHardcoded).forEach(function (k) {
  if (_deletedPresets.indexOf(k) !== -1) return;
  var w = _filtrarParaProdutor(_fastClone(_allHardcoded[k]));
  var antes = Object.keys(_allHardcoded[k]).length,
    depois = Object.keys(w).length;
  if (depois !== antes)
    console.log(
      '[preset]',
      k,
      '—',
      antes - depois,
      'widget(s) de cultura que este produtor nao tem, removidos'
    );
  window.PRESET_WIDGETS_JSON[k] = w;
});
// SVG do preset-base: as letras "IA" sobre o verde da Ampliagro.
// Vive aqui (e nao como <img src>) porque o preset pinta o icone com a
// cor do preset e porque um data-URI nao acrescenta um pedido HTTP.
var _IA_SVG =
  '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false" style="width:100%;height:100%;display:block">' +
  '<rect x="2" y="2" width="60" height="60" rx="16" fill="#0f9d6e"/>' +
  '<text x="32" y="42" font-family="Segoe UI,Roboto,Helvetica Neue,Arial,sans-serif" font-size="27" font-weight="700" letter-spacing="-1" fill="#ffffff" text-anchor="middle">IA</text>' +
  '</svg>';
// UMA entrada so'. Este objecto ja foi declarado duas vezes no mesmo
// ficheiro — a primeira com os metadados do `custom-agua` — e a segunda
// declaracao ganhava, deixando a primeira como codigo morto que mentia
// sobre o que existia. Os metadados de preset do produtor nao nascem
// aqui: vem do que ele criou (`persistPresetWidgets`, `restorePresetsFromPreferences`).
var _presetMeta = {
  'base-ia': {
    icon: 'bi-stars',
    label: 'Assistente IA',
    color: '#0f9d6e',
    iconSvg: _IA_SVG,
    imutavel: true,
  },
};
const PRESETS = {};
// `iconSvg` e `imutavel` passam para o PRESETS: sem isso o SVG nunca
// chegava ao render, e a guarda de exclusao nao via o preset.
Object.keys(window.PRESET_WIDGETS_JSON).forEach(function (k) {
  var m = _presetMeta[k] || {};
  PRESETS[k] = {
    icon: m.icon,
    label: m.label,
    color: m.color,
    iconSvg: m.iconSvg,
    imutavel: !!m.imutavel,
    widgets: _fastClone(window.PRESET_WIDGETS_JSON[k]),
  };
});
// O preset-base nao pode ser marcado como deletado, nem por engano.
// `_markPresetDeleted` e' chamada pela exclusao e por outras UI's;
// e o unico sitio onde o nome entra na lista de deletados.
window._presetImutavel = function (k) {
  if (!k) return false;
  if (window.PRESETS && PRESETS[k] && PRESETS[k].imutavel) return true;
  return k === 'base-ia';
};
window._markPresetDeleted = function (k) {
  if (window._presetImutavel && window._presetImutavel(k)) return;
  try {
    var arr = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
    if (!Array.isArray(arr)) arr = [];
    if (arr.indexOf(k) === -1) {
      arr.push(k);
      localStorage.setItem('ampliagro-deleted-presets', JSON.stringify(arr));
    }
  } catch (e) {}
};
window._unmarkPresetDeleted = function (k) {
  try {
    var arr = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
    if (!Array.isArray(arr)) arr = [];
    var idx = arr.indexOf(k);
    if (idx !== -1) {
      arr.splice(idx, 1);
      localStorage.setItem('ampliagro-deleted-presets', JSON.stringify(arr));
    }
  } catch (e) {}
};
// Allowlist de presets (fonte da verdade: app/presets.py, injetada pelo backend).
// Usada pela limpeza v13, pelo getPresetOrder e pela re-injeção do servidor, para
// que um preset bloqueado nunca volte por /api/dashboard-state/.
window._PRESET_BLOCK = window._BOOTSTRAP.presetBlock;
window._PRESET_SISTEMA = window._BOOTSTRAP.presetSistema;
// Um preset de SISTEMA passa, mesmo sem o prefixo `custom-`. Sem esta
// porta, `base-ia` era classificado como intruso pela limpeza v13 no
// primeiro save — o preset-base seria apagado pelo proprio sistema
// que o acabou de criar.
window._presetIsSystem = function (k) {
  return !!k && window._PRESET_SISTEMA.indexOf(k) !== -1;
};
window._presetIsAllowed = function (k) {
  if (!k) return false;
  if (window._presetIsSystem(k)) return true;
  return k.indexOf('custom-') === 0 && window._PRESET_BLOCK.indexOf(k) === -1;
};
// MIGRACAO DA FORMA LEGADA DE `prefs`.
//
// `syncPresetsToPreferences` gravava a ordem, o preset activo e os metadados
// DENTRO de `prefs.presets`, ao lado do espaco onde `AmpliagroPrefs.setPreset`
// poria um preset por chave. Duas verdades no mesmo campo. A limpeza v13 lia
// cada chave de `presets` como um nome de preset, e as chaves `order`, `active`
// e `list` nao comecam por `custom-`: entravam na limpeza, e a limpeza chamava
// `purgePreset` -- que media por substring e levava `matrix-preset-order` e
// `matrix-active-preset` consigo. Da' o painel abrir noutro preset ao reentrar.
//
// A migracao absorve a forma legada em `presetIndex` e NAO apaga nada que o
// utilizador tenha criado: e' uma mudanca de nome de campo.
window._migrarPrefsPresets = function () {
  if (typeof window.getPreferences !== 'function') return false;
  var prefs = window.getPreferences();
  if (!prefs || typeof prefs !== 'object') return false;
  var legado = prefs.presets;
  var temLegado =
    legado &&
    typeof legado === 'object' &&
    (Array.isArray(legado.order) ||
      typeof legado.active === 'string' ||
      (legado.list && typeof legado.list === 'object'));
  if (!temLegado) return false;
  var idx = prefs.presetIndex && typeof prefs.presetIndex === 'object' ? prefs.presetIndex : {};
  if (Array.isArray(legado.order)) idx.order = legado.order;
  if (typeof legado.active === 'string') idx.active = legado.active;
  if (legado.list && typeof legado.list === 'object') idx.list = legado.list;
  prefs.presetIndex = idx;
  delete prefs.presets;
  window.savePreferences({ presetIndex: idx });
  try {
    if (typeof sflush === 'function') sflush();
  } catch (e) {}
  return true;
};

// Enforce blocklist v13 — bloqueia só fantasmas conhecidos, permite custom do usuário e respeita deleted
window._enforceAllowlist = function () {
  var isAllowed = window._presetIsAllowed;
  var deleted = [];
  try {
    deleted = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
  } catch (e) {
    deleted = [];
  }
  var changed = false;
  Object.keys(PRESETS || {}).forEach(function (k) {
    if (!isAllowed(k) || deleted.indexOf(k) !== -1) {
      delete PRESETS[k];
      delete PRESET_WIDGETS_JSON[k];
      try {
        localStorage.removeItem('matrix-preset-json-' + k);
        localStorage.removeItem('matrix-preset-json-' + k + '_u' + (window.AMPLIAGRO_UID || ''));
      } catch (e) {}
      changed = true;
    }
  });
  Object.keys(PRESET_WIDGETS_JSON || {}).forEach(function (k) {
    if (!isAllowed(k) || deleted.indexOf(k) !== -1) {
      delete PRESET_WIDGETS_JSON[k];
      try {
        localStorage.removeItem('matrix-preset-json-' + k);
        localStorage.removeItem('matrix-preset-json-' + k + '_u' + (window.AMPLIAGRO_UID || ''));
      } catch (e) {}
      changed = true;
    }
  });
  try {
    var toDel = [];
    for (var i = 0; i < localStorage.length; i++) {
      var kk = localStorage.key(i);
      if (kk && kk.indexOf('matrix-preset-json-') === 0) {
        var kn = kk
          .replace('matrix-preset-json-', '')
          .replace('_u' + (window.AMPLIAGRO_UID || ''), '');
        if (!isAllowed(kn) || deleted.indexOf(kn) !== -1) toDel.push(kk);
      }
    }
    toDel.forEach(function (kk) {
      try {
        localStorage.removeItem(kk);
        changed = true;
      } catch (e) {}
    });
  } catch (e) {}
  return changed;
};
// A forma legada de `prefs` e' absorvida ANTES de qualquer leitura de preset:
// `restorePresetsFromPreferences` le `presetIndex`, e sem migrar antes ele
// nao encontraria a ordem de quem ja tinha.
try {
  window._migrarPrefsPresets();
} catch (e) {}
try {
  window._enforceAllowlist();
} catch (e) {}
// Restore custom presets from preferences BEFORE any rendering
if (typeof restorePresetsFromPreferences === 'function') restorePresetsFromPreferences();
try {
  window._enforceAllowlist();
} catch (e) {}

// Migrate layouts to 2x scale instead of wiping them!
if (localStorage.getItem('ampliagro-grid-scaled-v1') !== 'true') {
  try {
    function scaleLayout(jsonStr) {
      if (!jsonStr) return null;
      try {
        var parsed = JSON.parse(jsonStr);
        if (parsed && typeof parsed === 'object') {
          Object.keys(parsed).forEach(function (k) {
            var w = parsed[k];
            if (w.gridX !== undefined) w.gridX = w.gridX * 2;
            if (w.gridY !== undefined) w.gridY = w.gridY * 2;
            if (w.gridW !== undefined) w.gridW = w.gridW * 2;
            if (w.gridH !== undefined) w.gridH = w.gridH * 2;
          });
        }
        return JSON.stringify(parsed);
      } catch (e) {
        return null;
      }
    }

    // Scale matrix-widgets-layout
    var mwl = localStorage.getItem('matrix-widgets-layout');
    if (mwl) {
      var s_mwl = scaleLayout(mwl);
      if (s_mwl) localStorage.setItem('matrix-widgets-layout', s_mwl);
    }

    // Scale matrix-preset-json-*
    Object.keys(localStorage).forEach(function (k) {
      if (k.startsWith('matrix-preset-json-')) {
        var mpj = localStorage.getItem(k);
        if (mpj) {
          var s_mpj = scaleLayout(mpj);
          if (s_mpj) localStorage.setItem(k, s_mpj);
        }
      }
    });

    // As PILHAS DE HISTORICO ficaram de fora de proposito nesta v1 — ver a
    // migracao v2, logo abaixo. Corrigi-las aqui E na v2 faria um
    // utilizador novo passar pelas duas e ficar com o layout ao dobro.
    localStorage.setItem('ampliagro-grid-scaled-v1', 'true');
    console.log('Layouts scaled to 2x grid.');
  } catch (e) {
    console.error('Migration failed', e);
  }
}

// A migracao acima corre SO UMA VEZ (flag `ampliagro-grid-scaled-v1`), e
// antes de cobrir as pilhas de historico. Quem ja a correu tem a flag a
// 'true' e nunca mais passa por aqui — o que e' exactamente o caso do
// dashboard partido que motivou esta correccao.
//
// Por isso a segunda passagem, com a SUA flag. Nao se volta a usar a v1:
// reescrever a flag antiga obrigaria a duplicar duas vezes o layout de
// quem ja tinha migrado, e o dobro de 32 daria 64 — a largura toda, para
// tudo. Cada versao de migracao fica com a sua.
if (localStorage.getItem('ampliagro-grid-scaled-v2-historico') !== 'true') {
  try {
    /* As DUAS pilhas. `redo` guarda a mesma geometria antiga que `undo`, e
     * corrigir so `undo` deixa o bug a um Ctrl+Shift+Z de distanca — a
     * correccao que falha a meio e' pior do que nao haver: parece arrumada
     * e volta. */
    ['matrix-layout-history-undo', 'matrix-layout-history-redo'].forEach(function (chave) {
      var raw = localStorage.getItem(chave);
      if (!raw) return;
      var pilha;
      try {
        pilha = JSON.parse(raw);
      } catch (e) {
        return; /* pilha corrompida nao trava a migracao */
      }
      if (!Array.isArray(pilha)) return;
      var mudou = false;
      pilha.forEach(function (snapshot) {
        if (!snapshot || typeof snapshot !== 'object') return;
        Object.keys(snapshot).forEach(function (id) {
          var w = snapshot[id];
          if (!w || typeof w !== 'object') return;
          ['gridX', 'gridY', 'gridW', 'gridH'].forEach(function (p) {
            if (typeof w[p] === 'number') {
              w[p] = w[p] * 2;
              mudou = true;
            }
          });
        });
      });
      if (mudou) localStorage.setItem(chave, JSON.stringify(pilha));
    });
    localStorage.setItem('ampliagro-grid-scaled-v2-historico', 'true');
  } catch (e) {
    /* idem */
  }
}

// Fallback: only reset buggy presets if not done before, but DON'T wipe layout or custom presets if they exist!
if (localStorage.getItem('ampliagro-presets-reset-v2') !== 'true') {
  localStorage.setItem('ampliagro-presets-reset-v2', 'true');
}

// Expose PRESETS globally for widget-bar-intelligent.js
window.PRESETS = PRESETS;

function clonePresetWidgets(presetName) {
  // Ponto unico de leitura de widgets de preset. Filtrar aqui e'
  // o que garante a regra: um preset guardado antes desta mudanca
  // (ou re-semeado por um bloco legado) ainda traz `cultura-arroz`
  // para quem nao planta arroz, e o filtro so na semeadura nao o
  // apanha. Aqui nao ha caminho de leitura que escape.
  if (!_filtroJaAplicado) {
    _filtroJaAplicado = true;
    Object.keys(PRESET_WIDGETS_JSON).forEach(function (pk) {
      PRESET_WIDGETS_JSON[pk] = _filtrarParaProdutor(PRESET_WIDGETS_JSON[pk]);
    });
  }
  // ─────────────────────────────────────────────────────────────────────────
  // UM PRESET MOSTRA O QUE ESTA NO SEU JSON. NADA MAIS.
  //
  // Antes, um preset vazio ou ausente devolvia `custom-agua`, e o
  // `saveCurrentPreset` a seguir gravava esse emprestimo por cima do preset
  // pedido. O resultado era o sintoma do dono: o preset de soja, reentrado,
  // com os widgets do cafe — e ja gravado, portanto ja definitivo.
  //
  // Nao ha fallback. Nao ha segunda fonte. Um preset sem widgets e' um preset
  // SEM widgets, e o painel diz isso. Um preset nunca mostra o conteudo de
  // outro: e' a unica forma de "o preset e' o que o JSON diz" ser verdade.
  // ─────────────────────────────────────────────────────────────────────────
  if (!PRESET_WIDGETS_JSON.hasOwnProperty(presetName)) return {};
  var v = PRESET_WIDGETS_JSON[presetName];
  if (!v || typeof v !== 'object' || !Object.keys(v).length) return {};
  return _fastClone(v);
}
// PRESETS CLONADOS: DETECTA E REGISTA. NAO REESCREVE.
//
// Dois presets com o JSON byte-a-byte igual sao um clone. Podem ter nascido
// assim, ou terem ficado assim quando um preset vazio herdou os widgets de um
// outro (esse caminho foi removido: ver `clonePresetWidgets`).
//
// A resposta honesta e' mostrar o conflito, nao fabricar uma diferenca que o
// utilizador nao pediu. Um "reparo" que inventa conteudo produz um preset que
// parece correcto e nao corresponde a nada que ele tenha feito -- e um preset
// inventado e' pior que um preset em falta.
//
// O que fica: o primeiro de cada grupo intacto, os restantes registados em
// `ampliagro-preset-conflitos-v1` com o nome e o numero de widgets. O utilizador
// decide. `resolverClonesPresets()` esvazia os repetidos, que e' a unica
// accao honesta que nao exige adivinhar o conteudo.

// Chave de comparacao independente da ordem das chaves: dois JSON com as
// mesmas widgets em ordens diferentes sao o mesmo preset, nao dois.
function _assinaturaPreset(w) {
  try {
    return Object.keys(w || {})
      .sort()
      .map(function (k) {
        return k + '=' + JSON.stringify(w[k]);
      })
      .join('|');
  } catch (e) {
    return '';
  }
}

window._detectarClonesPresets = function () {
  var grupos = {};
  Object.keys(PRESET_WIDGETS_JSON || {}).forEach(function (k) {
    var w = PRESET_WIDGETS_JSON[k] || {};
    if (!Object.keys(w).length) return;
    var sig = _assinaturaPreset(w);
    if (!sig) return;
    if (!grupos[sig]) grupos[sig] = [];
    grupos[sig].push(k);
  });
  var conflitos = [];
  Object.keys(grupos).forEach(function (sig) {
    var membros = grupos[sig];
    if (membros.length < 2) return;
    conflitos.push({
      original: membros[0],
      repetidos: membros.slice(1),
      widgets: Object.keys(PRESET_WIDGETS_JSON[membros[0]] || {}).length,
      rotulos: membros.map(function (k) {
        return (PRESETS[k] && PRESETS[k].label) || k;
      }),
    });
  });
  if (conflitos.length) {
    // Registo, nao reparo. O original de cada grupo nao e' tocado.
    try {
      sset('ampliagro-preset-conflitos-v1', JSON.stringify(conflitos));
      if (typeof sflush === 'function') sflush();
    } catch (e) {}
    console.warn(
      '[preset-clone] ' +
        conflitos.length +
        ' preset(s) repetem outro byte a byte. Nada foi alterado; o conflito ' +
        'esta em `ampliagro-preset-conflitos-v1`.',
      conflitos
    );
  }
  return conflitos;
};

// Esvazia os PRESETS REPETIDOS de cada grupo. O original fica. Inventar
// widgets para "diferenciar" seria fabricar o dado que falta e chamar-lhe
// reparacao -- o mesmo que um widget sem dado mostra "SEM DADO".
window.resolverClonesPresets = function () {
  var conflitos = window._detectarClonesPresets();
  var esvaziados = [];
  conflitos.forEach(function (c) {
    c.repetidos.forEach(function (k) {
      PRESET_WIDGETS_JSON[k] = {};
      if (PRESETS[k]) PRESETS[k].widgets = {};
      try {
        sset('matrix-preset-json-' + k, '{}');
      } catch (e) {}
      esvaziados.push(k);
    });
  });
  if (esvaziados.length) {
    try {
      if (typeof sflush === 'function') sflush();
    } catch (e) {}
    try {
      if (typeof persistDashboardStateToServer === 'function') persistDashboardStateToServer();
    } catch (e) {}
    console.warn('[preset-clone] repetidos esvaziados (o original ficou):', esvaziados);
  }
  return esvaziados;
};

// O nome antigo fica, para o ponto de chamada em `hydratePresetWidgets` nao
// quebrar. Agora DETECTA; ja nao reescreve.
window._repairClonedPresets = function () {
  return window._detectarClonesPresets().reduce(function (acc, c) {
    return acc.concat(c.repetidos);
  }, []);
};

function persistPresetWidgets(presetName, value) {
  if (!value || typeof value !== 'object') return;
  // Nunca persiste {} vazio por cima de preset que já tem dados — evita apagar com race
  if (!Object.keys(value).length) {
    var existing = PRESET_WIDGETS_JSON[presetName];
    if (existing && Object.keys(existing).length) {
      console.warn('[persistPresetWidgets] skip empty overwrite for', presetName);
      return;
    }
  }
  var cloned = _fastClone(value);
  PRESET_WIDGETS_JSON[presetName] = cloned;
  if (PRESETS[presetName]) {
    PRESETS[presetName].widgets = _fastClone(cloned);
  } else {
    // cria shell se não existe (custom)
    PRESETS[presetName] = {
      icon: 'bi-speedometer2',
      label: presetName,
      color: '#64748b',
      cultures: [],
      widgets: _fastClone(cloned),
    };
  }
  try {
    sset('matrix-preset-json-' + presetName, JSON.stringify(cloned));
  } catch (e) {}
  // Todos presets (inclui visao-* custom) agora sincronizam — só base não
  if (presetName !== 'visao-geral' && presetName !== 'visao-base') scheduleDashboardStateSync();
  sflush();
}

var _stateSyncTimer = null;
function scheduleDashboardStateSync() {
  if (AMPLIAGRO_UID == null) return;
  if (_stateSyncTimer) clearTimeout(_stateSyncTimer);
  _stateSyncTimer = setTimeout(function () {
    _stateSyncTimer = null;
    persistDashboardStateToServer();
  }, 1500);
}

function hydratePresetWidgets() {
  var _deletedHydrate = [];
  try {
    _deletedHydrate = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
  } catch (e) {}
  // SO AS CHAVES DESTA CONTA.
  //
  // Medido 2026-10-14: uma conta nova acordava com os presets de outra
  // ("Tempo", "Logistica") na barra de widgets. A origem nao era o
  // servidor — o estado da conta nova no servidor tinha so' `base-ia` —
  // era este varredura: ela lia no localStorage QUALQUER chave
  // `matrix-preset-json-*`, inclusive as que uma sessao anterior tinha
  // deixado sem escopo de utilizador.
  //
  // Com utilizador identificado, so' a chave desta conta
  // (`matrix-preset-json-X_u<id>`) e' lida. A chave sem escopo e'
  // ignorada — e apagada quando ja' tiver copia com escopo, que e'
  // duplicacao sem dado novo. A chave de OUTRA conta (`_u<outro>`)
  // tambem e' ignorada, mas NAO e' apagada: o browser pode ser partilhado
  // e o que la' esta' nao e' nosso.
  //
  // Sem utilizador identificado (anonimo) o comportamento e' o de
  // sempre: ha' uma so' pessoa neste storage.
  var _uid = window.AMPLIAGRO_UID;
  var _sufixo = _uid != null ? '_u' + _uid : null;
  for (var i = 0; i < localStorage.length; i++) {
    try {
      var key = localStorage.key(i);
      if (!key || key.indexOf('matrix-preset-json-') !== 0) continue;
      var bruto = key.slice('matrix-preset-json-'.length);
      if (_sufixo) {
        var _meu = bruto.length > _sufixo.length && bruto.slice(-_sufixo.length) === _sufixo;
        if (!_meu) {
          // sem escopo, e ja' copiada para esta conta: duplicacao, lixo.
          if (!/_u\d+$/.test(bruto) && sget('matrix-preset-json-' + bruto)) {
            localStorage.removeItem(key);
          }
          continue;
        }
      }
      var presetName = bruto.replace(/_u\d+$/, '');
      if (_deletedHydrate.indexOf(presetName) !== -1) continue;
      if (!PRESET_WIDGETS_JSON[presetName]) {
        PRESET_WIDGETS_JSON[presetName] = {};
      }
    } catch (e) {}
  }
  Object.keys(PRESET_WIDGETS_JSON).forEach(function (presetName) {
    try {
      var saved = sget('matrix-preset-json-' + presetName);
      if (saved) {
        var parsed = JSON.parse(saved);
        if (!parsed || typeof parsed !== 'object') return;
        // Se saved é identico ao visao-geral mas presetName não é visao-geral e default é diferente,
        // é clonagem antiga (bug visao-geral fallback) — ignora e mantém default distinto
        try {
          var _vgStr = JSON.stringify(window.PRESET_WIDGETS_JSON['visao-geral'] || {});
          var _parsedStr = JSON.stringify(parsed);
          var _defStr = PRESETS[presetName]
            ? JSON.stringify(PRESETS[presetName].widgets || {})
            : '';
          if (
            presetName !== 'visao-geral' &&
            _parsedStr === _vgStr &&
            _defStr &&
            _defStr !== _vgStr
          ) {
            console.warn(
              '[hydrate] clonagem detectada em',
              presetName,
              '— mantendo default distinto'
            );
            // corrige localStorage imediatamente
            try {
              sset('matrix-preset-json-' + presetName, JSON.stringify(PRESETS[presetName].widgets));
            } catch (e) {}
            return;
          }
        } catch (e) {}
        PRESET_WIDGETS_JSON[presetName] = _fastClone(parsed);
        if (PRESETS[presetName]) {
          PRESETS[presetName].widgets = _fastClone(parsed);
        }
      }
    } catch (e) {}
  });
  // Após hidratar, repara clones residuais (dois presets com mesmo JSON)
  try {
    if (typeof window._repairClonedPresets === 'function') window._repairClonedPresets();
  } catch (e) {}
}

// Helper: persist current widgets to the active preset immediately
function saveCurrentPreset() {
  var activePreset = sget('matrix-active-preset') || 'base-ia';
  if (widgets && Object.keys(widgets).length > 0) {
    persistPresetWidgets(activePreset, widgets);
  }
}

window.getWidgetData = function () {
  return widgetDataCache;
};
// P1: Web Worker para cálculos pesados fora da main thread
window.__widgetWorker = null;
window.__workerSeq = 0;
try {
  window.__widgetWorker = new Worker('/static/js/widget-worker.js');
} catch (e) {}
window.execWidgetWorker = function (type, payload) {
  return new Promise(function (resolve, reject) {
    if (!window.__widgetWorker) return resolve(null); // fallback sync
    var id = ++window.__workerSeq;
    var handler = function (ev) {
      if (ev.data && ev.data.id === id) {
        window.__widgetWorker.removeEventListener('message', handler);
        if (ev.data.success) resolve(ev.data.result);
        else reject(ev.data.error);
      }
    };
    window.__widgetWorker.addEventListener('message', handler);
    window.__widgetWorker.postMessage({ id: id, type: type, payload: payload });
    // timeout fallback 400ms
    setTimeout(function () {
      try {
        window.__widgetWorker.removeEventListener('message', handler);
      } catch (e) {}
      resolve(null);
    }, 400);
  });
};

// fetchWithTimeout já injetado em base.html <head> (15s). Evita redefinição com recursão.
if (!window.fetchWithTimeout) {
  window.fetchWithTimeout = async function (url, opts, timeoutMs, retries) {
    timeoutMs = timeoutMs || 15000;
    retries = retries == null ? 2 : retries;
    opts = opts || {};
    opts.credentials = opts.credentials || 'same-origin';
    var _origFetch = window.fetch.bind(window);
    for (var attempt = 0; attempt <= retries; attempt++) {
      var ctrl = new AbortController();
      var timer = setTimeout(function () {
        ctrl.abort();
      }, timeoutMs);
      try {
        var res = await _origFetch(url, Object.assign({}, opts, { signal: ctrl.signal }));
        clearTimeout(timer);
        if (!res.ok && res.status >= 500 && attempt < retries) {
          await new Promise(function (r) {
            setTimeout(r, 600 * (attempt + 1));
          });
          continue;
        }
        return res;
      } catch (e) {
        clearTimeout(timer);
        if (e.name === 'AbortError' && attempt < retries) {
          await new Promise(function (r) {
            setTimeout(r, 600 * (attempt + 1));
          });
          continue;
        }
        if (attempt === retries) throw e;
      }
    }
  };
}
window.refreshWidgetData = async function () {
  try {
    if (hasWidgetSession()) {
      var wres = await window.fetchWithTimeout(
        '/api/widget-data/',
        { credentials: 'same-origin' },
        15000,
        2
      );
      if (wres && wres.ok) widgetDataCache = await wres.json();
    }
  } catch (e) {
    console.warn('widget-data timeout (15s), usando cache stale', e);
  }
  return widgetDataCache;
};
// (removido wrapper duplicado — base.html já faz global patch idempotente)

function adjustMatrixHeight() {
  var navBar = document.querySelector('#nav-premium .nav-main');
  var navHeight = navBar ? navBar.offsetHeight : 64;
  // #dashboard-appbar e position:fixed — nao afeta o layout
  // pb-14 (56px) no #content ja protege o espaco inferior
  var content = document.getElementById('content');
  var contentPadBot = content ? parseFloat(getComputedStyle(content).paddingBottom) : 56;
  var available = window.innerHeight - navHeight - contentPadBot;

  var maxRows = Math.floor((available + GRID_GAP - 2 * GRID_PAD) / (20 + GRID_GAP));
  maxRows = Math.max(4, Math.min(40, maxRows));

  if (maxRows !== GRID_ROWS) {
    GRID_ROWS = maxRows;
    var container = document.querySelector('.matrix-container');
    if (container) {
      container.style.setProperty('--grid-rows', GRID_ROWS);
    }
    Object.keys(widgets).forEach(function (id) {
      var w = widgets[id];
      if (w.gridY + w.gridH > GRID_ROWS) {
        w.gridY = Math.max(0, GRID_ROWS - w.gridH);
      }
    });
  }
}

// Helper: preserva estilizacao local (bgColor, chartStyle, meta, etc) ao mesclar layout do servidor
// Garante que o exato widget do painel de inserir apareca sem perder formatacao
function mergePreserveStyling(serverWidgets, localWidgets) {
  if (!serverWidgets || typeof serverWidgets !== 'object') return serverWidgets;
  if (!localWidgets || typeof localWidgets !== 'object') return serverWidgets;
  var merged = JSON.parse(JSON.stringify(serverWidgets));
  Object.keys(localWidgets).forEach(function (id) {
    var local = localWidgets[id];
    var srv = merged[id];
    if (!local || !local.visible) return;
    if (!srv) {
      // Widget existe localmente mas nao no servidor (ex: recem inserido) — preserva integralmente
      merged[id] = JSON.parse(JSON.stringify(local));
      return;
    }
    // Preserva campos de estilo/meta se o servidor nao tiver ou tiver vazio
    var styleKeys = [
      'bgColor',
      'chartStyleCategory',
      'chartStyleVariant',
      'mainColor',
      '_mainColor',
      'chartSubtype',
      'widgetType',
      'title',
      'showTitle',
      'metricKey',
      'source',
      '_metaEnabled',
      '_metaValue',
      '_starred',
      '_compareSeries',
      '_chartData',
      '_cardHistory',
      '_cardMyHistory',
      '_lastMetric',
      'selectedRecords',
      '_comparative',
    ];
    styleKeys.forEach(function (k) {
      if (
        local[k] !== undefined &&
        local[k] !== null &&
        local[k] !== '' &&
        (srv[k] === undefined || srv[k] === null || srv[k] === '')
      ) {
        srv[k] = JSON.parse(JSON.stringify(local[k]));
      }
      // Se local tem bgColor/meta mas srv tem diferente (ex: srv tem bgColor vazio), preserva local
      if (k === 'bgColor' && local[k] && !srv[k]) srv[k] = local[k];
      if (
        (k === '_metaEnabled' || k === '_metaValue') &&
        local[k] !== undefined &&
        srv[k] === undefined
      )
        srv[k] = local[k];
    });
    // Preserva grid se local for mais recente? Mantem srv grid (posicao pode ter sido atualizada no servidor), mas preserva estilo
  });
  return merged;
}

window._widgetsMatrixInitialized = false;
window._widgetsMatrixPromise = null;
// ESQUEMA ABSOLUTO: so atualiza UMA vez, carrega e entende tudo, so widgets que o usuario realmente inseriu
window.initWidgetsMatrix = async function () {
  if (window._widgetsMatrixPromise) {
    try {
      dashboardLog('initWidgetsMatrix:skip', { reason: 'ja em progresso/promessa' });
    } catch (e) {}
    return window._widgetsMatrixPromise;
  }
  if (window._widgetsMatrixInitialized) {
    try {
      dashboardLog('initWidgetsMatrix:skip', { reason: 'ja inicializado' });
    } catch (e) {}
    return;
  }
  window._widgetsMatrixPromise = (async function () {
    // flag só no final, evita que spa renderize com 0 enquanto cultures ainda carrega (causa do flick no console com F12)
    try {
      dashboardLog('initWidgetsMatrix:enter', {
        caller: (new Error().stack || '').split('\n')[2] || '',
      });
    } catch (e) {}
    // #region agent log
    if (window.__dbgNav)
      window.__dbgNav('C', 'pagina-index.js:initWidgetsMatrix', 'init enter', {
        hasLayout: !!sget('matrix-widgets-layout'),
        layoutKeys: (function () {
          try {
            return Object.keys(JSON.parse(sget('matrix-widgets-layout') || '{}')).length;
          } catch (e) {
            return -1;
          }
        })(),
        activePreset: sget('matrix-active-preset'),
        memCount: Object.keys(widgets || {}).length,
      });
    // #endregion
    adjustMatrixHeight();

    // ABSOLUTO: le EXATAMENTE o que o usuario inseriu, com formatacao exata do painel
    var localLayout = null;
    try {
      localLayout = JSON.parse(sget('matrix-widgets-layout') || 'null');
    } catch (e) {
      localLayout = null;
    }
    if (localLayout && typeof localLayout === 'object' && Object.keys(localLayout).length) {
      // Clone profundo para nao compartilhar referencia com localStorage
      widgets = JSON.parse(JSON.stringify(localLayout));
      // MIGRACAO: corrige _mercado_ bar com bg faint 0.08/0.12 que deveria ser 0.6 (exceto tracejada/pontilhada que eh 0.15 faint proposital)
      try {
        Object.keys(widgets).forEach(function (mid) {
          var c = widgets[mid];
          if (
            !c ||
            c.chartSubtype !== 'bar' ||
            !c._chartData ||
            !c._chartData.datasets ||
            !c._chartData.datasets[0]
          )
            return;
          if (mid.indexOf('_mercado_') < 0) return;
          var ds = c._chartData.datasets[0];
          var bg = String(ds.backgroundColor || '');
          var variant = c.chartStyleVariant || '';
          // Se eh barra solida (nao tracejada/pontilhada) mas bg ta faint 0.08/0.12, corrige para 0.6
          if (
            variant !== 'tracejada' &&
            variant !== 'pontilhada' &&
            (bg.indexOf('0.08') >= 0 || bg.indexOf('0.12') >= 0)
          ) {
            var bc = ds.borderColor || '#0f9d6e';
            var m = String(bc).match(/^#([0-9a-fA-F]{6})$/);
            if (m) {
              var hex = m[1];
              var r = parseInt(hex.slice(0, 2), 16),
                g = parseInt(hex.slice(2, 4), 16),
                b = parseInt(hex.slice(4, 6), 16);
              ds.backgroundColor = 'rgba(' + r + ',' + g + ',' + b + ',0.6)';
            } else if (bg.indexOf('rgba') === 0) {
              var nums = bg.match(/\d+/g);
              if (nums && nums.length >= 3)
                ds.backgroundColor = 'rgba(' + nums[0] + ',' + nums[1] + ',' + nums[2] + ',0.6)';
            }
          }
          // Caso especifico demo cacau: tracejada faint 0.15 mas usuario queria solido agrupada — corrige uma vez
          if (
            mid === 'cult-graos-cacau_mercado_receita_estimada_grafico_bar' &&
            variant === 'tracejada' &&
            bg.indexOf('0.15') >= 0
          ) {
            c.chartStyleVariant = 'agrupada';
            var bc2 = ds.borderColor || '#0f9d6e';
            var m2 = String(bc2).match(/^#([0-9a-fA-F]{6})$/);
            if (m2) {
              var hx = m2[1];
              var rr = parseInt(hx.slice(0, 2), 16),
                gg = parseInt(hx.slice(2, 4), 16),
                bb = parseInt(hx.slice(4, 6), 16);
              ds.backgroundColor = 'rgba(' + rr + ',' + gg + ',' + bb + ',0.6)';
            } else ds.backgroundColor = 'rgba(15,157,110,0.6)';
            delete ds.borderDash;
            try {
              dashboardLog('migrate:cacau_bar', { from: 'tracejada 0.15', to: 'agrupada 0.6' });
            } catch (e) {}
          }
        });
        // Persiste migracao imediatamente para nao piscar na proxima recarga
        try {
          sset('matrix-widgets-layout', JSON.stringify(widgets));
        } catch (e) {}
      } catch (e) {}
    } else if (sget('ampliagro-onboard-cultures')) {
      await autoBuildOnboardingPreset();
    } else {
      var presetName = sget('matrix-active-preset') || 'base-ia';
      hydratePresetWidgets();
      var presetWidgets = clonePresetWidgets(presetName);
      if (Object.keys(presetWidgets).length) {
        widgets = JSON.parse(JSON.stringify(presetWidgets));
      }
      // SEM fallback. O preset pedido nao tinha widgets: fica sem widgets.
      // Aqui devolvia `custom-agua`, e o `saveCurrentPreset` a seguir
      // gravava esses widgets por cima do preset pedido -- o preset do
      // produtor passava a ter, e a conservar, o conteudo de outro.
    }
    // Guarda copia absoluta para nunca perder contexto
    try {
      window._initialWidgets = JSON.parse(JSON.stringify(widgets));
      window._absoluteWidgets = JSON.parse(JSON.stringify(widgets));
    } catch (e) {
      window._initialWidgets = null;
      window._absoluteWidgets = null;
    }

    // Entende tudo ANTES de renderizar: espera culturas e dados
    try {
      await Promise.all([
        window.CulturesLoader ? window.CulturesLoader.ready() : Promise.resolve(),
        hasWidgetSession()
          ? window
              .fetchWithTimeout('/api/dashboard/', { credentials: 'same-origin' }, 8000, 1)
              .then(function (r) {
                return r && r.ok ? r.json() : null;
              })
              .then(function (d) {
                if (d) dashboardData = d;
              })
              .catch(function () {})
          : Promise.resolve(),
        hasWidgetSession() ? window.refreshWidgetData().catch(function () {}) : Promise.resolve(),
      ]);
    } catch (e) {}

    // Renderiza UMA vez, absoluto, com contexto completo — sem segundo reload
    normalizeWidgetPositions();
    window.widgets = widgets;
    renderWidgetsOnMatrix();

    /* MEDIDO 2026-10-05: `extra-widgets.js` sabia construir
     * `kpi-ia-artefatos`, `kpi-iot-alertas` e mais uma dezena de widgets que
     * `pagina-index.js` nao conhece — mas so o fazia no `DOMContentLoaded`,
     * e este render acontece DEPOIS. Resultado: os contentores `xw-<id>` que o
     * `fill()` procura nunca existiam, os fetches nao saiam, e os widgets
     * ficavam em `—` (que e' o default do `generateWidgetContent` para um id
     * desconhecido).
     *
     * `/api/ia/artefatos/` devolvia 3 artefactos e nunca era chamado.
     *
     * Chamar aqui, logo apos o render: e' o primeiro momento em que os
     * widgets estao no DOM. E' idempotente — ver o comentario no fim de
     * `extra-widgets.js`.
     */
    try {
      if (typeof window.XW_merge === 'function') window.XW_merge();
    } catch (e) {
      /* um widget que falha nao pode levar o dashboard inteiro */
    }
    var _mcInit = document.querySelector('.matrix-container');
    if (_mcInit) {
      _mcInit.classList.add('su-stagger');
      setTimeout(
        function () {
          _mcInit.classList.remove('su-stagger');
        },
        420 + Object.keys(widgets).length * 26
      );
    }
    renderWidgetbarPresets();

    // ABSOLUTO: 1 render sem background refresh — mantem formatacao exata do painel (sem piscar)
    // Removido refreshMarketWidgetsData que recriava _chartData com 0.12 e perdia borda tracejada/meta
    // Se precisar atualizar dados, faca via botao Atualizar, nao automatico no reload

    // Sincroniza menu e widget-bar com server (garante que presets criados em outro navegador aparecam nos dois lugares)
    try {
      if (typeof tryRestoreDashboardFromServer === 'function' && window.AMPLIAGRO_UID) {
        tryRestoreDashboardFromServer().then(function (applied) {
          if (applied) {
            try {
              renderPresetCarousel();
              renderWidgetbarPresets();
            } catch (e) {}
            console.log('[sync] presets do servidor sincronizados para menu e barra');
          }
        });
      }
    } catch (e) {}
    // ABSOLUTO: elimina segundo reload — dashboard ja esta correto com o exato widget do painel
    // Nao faz segundo render nem performBackgroundSync/forceDashboardCorrect automatico
    // Apenas garante clima se houver
    document.querySelectorAll('[id^="clima-"]').forEach(function (el) {
      var wid = el.id.replace('clima-', '');
      if (window._climaInitialized) delete window._climaInitialized[wid];
      if (typeof initClimaWidget === 'function')
        try {
          initClimaWidget(wid, el);
        } catch (e) {}
    });

    // 4. Last resort for a brand-new account: the base-ia preset
    if (!Object.keys(widgets).length) {
      widgets = clonePresetWidgets('base-ia');
      normalizeWidgetPositions();
      window.widgets = widgets;
      renderWidgetsOnMatrix();
      renderWidgetbarPresets();
    }
    window._widgetsMatrixInitialized = true;
  })();
  return window._widgetsMatrixPromise;
};

// Forca dashboard correto — repete ate widgets nao ficarem vazios/sem formatacao (puro JS, sem Bootstrap)
// Corrigido: nao recarrega loucamente, verifica formato real e evita loop infinito por meta
window.forceDashboardCorrect = async function (maxAttempts) {
  if (window._forceRunning) return;
  window._forceRunning = true;
  maxAttempts = maxAttempts || 3;
  try {
    for (var attempt = 0; attempt < maxAttempts; attempt++) {
      var hasEmpty = false;
      var hasWrongFormat = false;
      document.querySelectorAll('.bento-block').forEach(function (el) {
        var id = el.id.replace('widget-', '');
        var cfg = window.widgets && window.widgets[id];
        if (!cfg || !cfg.visible) return;
        var content = el.querySelector('.widget-content');
        if (!content || content.innerHTML.trim() === '') hasEmpty = true;
        if (content && content.innerHTML.indexOf('Sem dados') >= 0) {
          if (cfg.selectedRecords || cfg.metricKey || (cfg._cardHistory && cfg._cardHistory.length))
            hasEmpty = true;
        }
        if (cfg && cfg.bgColor) {
          var bg = el.style.background || el.style.backgroundColor || '';
          if (!bg || bg === '' || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') {
            el.style.background = cfg.bgColor;
            // Nao marca hasWrongFormat aqui — apenas corrige inline, nao precisa re-render louco
          }
        }
        if (cfg && cfg._metaEnabled && cfg._metaValue) {
          var inst = window.chartInstances && window.chartInstances['chart-' + id];
          var hasMetaChart =
            inst &&
            inst.config &&
            inst.config.options &&
            inst.config.options.plugins &&
            inst.config.options.plugins.ampliReference &&
            inst.config.options.plugins.ampliReference.metaLines;
          var hasMetaDom = content && content.innerHTML.indexOf('Meta') >= 0;
          if (!hasMetaChart && !hasMetaDom) {
            // So considera formato errado se meta realmente nao estiver renderizada
            // Nao forca reload louco — apenas marca para tentar mais uma vez se houver dados
            if (cfg._cardHistory || cfg._lastMetric) hasWrongFormat = true;
          }
        }
        if (cfg && cfg.chartSubtype === 'bar' && el.querySelector('canvas')) {
          var inst2 = window.chartInstances && window.chartInstances['chart-' + id];
          if (inst2 && inst2.config && inst2.config.type !== 'bar') hasWrongFormat = true;
        }
      });
      if (window.CULTURE_GROUPS && window.CULTURE_GROUPS.length === 0) {
        // So considera empty se realmente nao tiver grupos e houver widgets de cultura
        var hasCulturaWidget = false;
        try {
          Object.keys(window.widgets || {}).forEach(function (k) {
            if (k.indexOf('cultura-') === 0) hasCulturaWidget = true;
          });
        } catch (e) {}
        if (hasCulturaWidget) hasEmpty = true;
      }
      if (!hasEmpty && !hasWrongFormat) break;
      try {
        if (window.CulturesLoader && window.CulturesLoader.ready)
          await window.CulturesLoader.ready();
        if (window.refreshWidgetData) await window.refreshWidgetData();
        renderWidgetsOnMatrix();
        if (window.refreshMarketWidgetsData) refreshMarketWidgetsData();
      } catch (e) {}
      await new Promise(function (r) {
        setTimeout(r, 600 * (attempt + 1));
      });
    }
    try {
      renderWidgetsOnMatrix();
    } catch (e) {}
  } finally {
    window._forceRunning = false;
  }
};

// T19.01 - Sincronizacao de dados em background
window.performBackgroundSync = function () {
  if (document.hidden || widgetEditMode || customMode) return;
  if (!hasWidgetSession()) return;
  try {
    Promise.all([
      window
        .fetchWithTimeout('/api/dashboard/', { credentials: 'same-origin' }, 15000, 1)
        .then(function (r) {
          return r && r.ok ? r.json() : null;
        }),
      window.refreshWidgetData(),
    ])
      .then(function (results) {
        if (results[0] && typeof results[0] === 'object') dashboardData = results[0];
        renderWidgetsOnMatrix();
        refreshMarketWidgetsData();
        // Re-popular containers de clima com dados frescos
        document.querySelectorAll('[id^="clima-"]').forEach(function (el) {
          var wid = el.id.replace('clima-', '');
          if (window._climaInitialized) delete window._climaInitialized[wid];
          initClimaWidget(wid, el);
        });
      })
      .catch(function () {});
  } catch (e) {}
};

// ABSOLUTO: auto-refresh desabilitado — dashboard so atualiza UMA vez com o exato widget do painel
// Se precisar atualizar manualmente, chame window.forceDashboardCorrect() — nao faz interval
// setInterval(window.performBackgroundSync, 5 * 60 * 1000);
// window.addEventListener('ampliagro:refresh', window.performBackgroundSync);

function tryRestoreDashboardFromServer() {
  return fetch('/api/dashboard-state/', { credentials: 'same-origin' })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .then(function (data) {
      if (!data || !data.ok || !data.state) return false;
      var st = data.state;
      // Preset bloqueado (fantasma) ou deletado pelo usuário não volta do servidor.
      // Sem este filtro o /api/dashboard-state/ reintroduz os presets removidos
      // logo depois da limpeza v13 e o dashboard os exibe de novo.
      var _isAllowed = function (k) {
        if (typeof window._presetIsAllowed === 'function') return window._presetIsAllowed(k);
        return k && k.indexOf('custom-') === 0;
      };
      var _deleted = [];
      try {
        _deleted = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
      } catch (e) {
        _deleted = [];
      }
      if (!Array.isArray(_deleted)) _deleted = [];
      var _aceita = function (k) {
        return _isAllowed(k) && _deleted.indexOf(k) === -1;
      };
      if (st.presets_order && Array.isArray(st.presets_order) && st.presets_order.length) {
        // local wins: só restaura do server se não houver ordem local
        // (evita restore tardio sobrescrever drag fluido acabado de salvar)
        var _localPresetOrder = null;
        try {
          _localPresetOrder = JSON.parse(sget('matrix-preset-order'));
        } catch (e) {}
        if (!Array.isArray(_localPresetOrder) || !_localPresetOrder.length) {
          var _srvOrder = st.presets_order.filter(function (k) {
            return _aceita(k);
          });
          if (_srvOrder.length) {
            // `sset` escreve na chave COM escopo (`..._u<id>`), que e' a que
            // `getPresetOrder` vai ler. A linha de baixo escrevia na chave SEM
            // escopo: num utilizador autenticado a ordem do servidor nao era
            // nunca lida, e a ordem do servidor nao se aplicava. Agora escreve
            // nas duas, e o sflush garante a persistencia imediata.
            try {
              sset('matrix-preset-order', JSON.stringify(_srvOrder));
              if (typeof sflush === 'function') sflush();
            } catch (e) {}
            try {
              if (scopedKey('matrix-preset-order') === 'matrix-preset-order')
                localStorage.setItem('matrix-preset-order', JSON.stringify(_srvOrder));
            } catch (e) {}
          }
        }
      }
      var applied = false;
      if (st.presets && typeof st.presets === 'object') {
        Object.keys(st.presets).forEach(function (name) {
          if (!_aceita(name)) return;
          var w = st.presets[name];
          if (!w || typeof w !== 'object') return;
          PRESET_WIDGETS_JSON[name] = JSON.parse(JSON.stringify(w));
          try {
            sset('matrix-preset-json-' + name, JSON.stringify(w));
          } catch (e) {}
          if (PRESETS[name]) PRESETS[name].widgets = JSON.parse(JSON.stringify(w));
          else {
            var meta = (st.presets_meta && st.presets_meta[name]) || {};
            PRESETS[name] = {
              icon: meta.icon || 'bi-speedometer2',
              label: meta.label || name,
              cultures: meta.cultures || [],
              widgets: JSON.parse(JSON.stringify(w)),
            };
          }
          applied = true;
        });
      }
      if (st.active_preset && _aceita(st.active_preset)) {
        try {
          sset('matrix-active-preset', st.active_preset);
        } catch (e) {}
        applied = true;
      }
      // `st.layout` e' o layout do preset ACTIVO. Aplicado sem condicao,
      // ele desenha os widgets de um preset por baixo de outro -- o preset de
      // soja a abrir com a grelha do cafe. So entra se trouxer o preset
      // activo que o justifica; sem esse par, NAO se aplica nada.
      var _layoutDoAtivo =
        st.active_preset &&
        _aceita(st.active_preset) &&
        st.layout &&
        typeof st.layout === 'object' &&
        Object.keys(st.layout).length;
      if (_layoutDoAtivo) {
        // Merge com layout local para nao perder estilizacao exata do painel de inserir
        var baseLocal = window._initialWidgets || null;
        try {
          if (!baseLocal) baseLocal = JSON.parse(sget('matrix-widgets-layout') || 'null');
        } catch (e) {
          baseLocal = null;
        }
        var merged =
          typeof mergePreserveStyling === 'function' && baseLocal
            ? mergePreserveStyling(st.layout, baseLocal)
            : st.layout;
        widgets = JSON.parse(JSON.stringify(merged));
        // #region agent log
        if (window.__dbgNav)
          window.__dbgNav(
            'C',
            'pagina-index.js:tryRestoreDashboardFromServer',
            'server layout applied',
            {
              srvCount: Object.keys(st.layout || {}).length,
              localCount: baseLocal ? Object.keys(baseLocal).length : 0,
              mergedCount: Object.keys(widgets).length,
              active: st.active_preset,
            }
          );
        // #endregion
        try {
          sset('matrix-widgets-layout', JSON.stringify(widgets));
          if (typeof sflush === 'function') sflush();
        } catch (e) {}
        applied = true;
      }
      return applied;
    })
    .catch(function () {
      return false;
    });
}

function persistDashboardStateToServer() {
  if (AMPLIAGRO_UID == null || typeof widgets === 'undefined') return;
  var state = {
    layout: typeof widgets === 'object' && widgets ? widgets : {},
    active_preset: sget('matrix-active-preset') || 'base-ia',
    presets_order: getPresetOrder(),
    presets: {},
    presets_meta: {},
    presets_fonte_dado: {},
  };
  // A origem e' declarada na MESMA passagem da escrita (VISÃO §5.1.5: "Toda a
  // escrita na base de dados declara `fonte_dado`. Sem isso, a escrita nao
  // entra."). Um preset montado pelo utilizador e' `declarado`: foi ele que o
  // disse, nao um sensor e nao uma medicao. Nao ha `medido` neste caminho, e
  // escrever `medido` aqui seria a mentira que o VISÃO §0.1 acusa.
  state.layout_fonte_dado = 'declarado';
  Object.keys(PRESETS).forEach(function (key) {
    if (key === 'visao-geral' || key === 'visao-base') return;
    var w = PRESET_WIDGETS_JSON[key] || PRESETS[key].widgets || {};
    state.presets[key] = JSON.parse(JSON.stringify(w));
    state.presets_meta[key] = {
      icon: PRESETS[key].icon,
      label: PRESETS[key].label,
      cultures: PRESETS[key].cultures || [],
    };
    state.presets_fonte_dado[key] = 'declarado';
  });
  try {
    fetch('/api/dashboard-state/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': window._BOOTSTRAP.csrf,
      },
      body: JSON.stringify({ state: state }),
    }).catch(function () {});
  } catch (e) {}
}

// Prevent overlapping widgets on page refresh
function normalizeWidgetPositions() {
  if (!widgets || typeof widgets !== 'object') return;
  var occupied = [];
  Object.keys(widgets).forEach(function (id) {
    var w = widgets[id];
    if (!w || !w.visible) return;
    // Validate grid bounds
    if (typeof w.gridX !== 'number' || w.gridX < 0) w.gridX = 0;
    if (typeof w.gridY !== 'number' || w.gridY < 0) w.gridY = 0;
    if (typeof w.gridW !== 'number' || w.gridW < 1) w.gridW = 1;
    if (typeof w.gridH !== 'number' || w.gridH < 1) w.gridH = 1;
    if (w.gridX + w.gridW > GRID_COLS) w.gridX = Math.max(0, GRID_COLS - w.gridW);
    if (w.gridY + w.gridH > GRID_ROWS) w.gridY = Math.max(0, GRID_ROWS - w.gridH);
    // Check for overlap with previously placed widgets
    var overlaps = false;
    for (var i = 0; i < occupied.length; i++) {
      var o = occupied[i];
      if (
        w.gridX < o.x + o.w &&
        w.gridX + w.gridW > o.x &&
        w.gridY < o.y + o.h &&
        w.gridY + w.gridH > o.y
      ) {
        overlaps = true;
        break;
      }
    }
    if (overlaps) {
      // Find a free position
      var placed = false;
      for (var y = 0; y < GRID_ROWS && !placed; y++) {
        for (var x = 0; x < GRID_COLS && !placed; x++) {
          var canPlace = true;
          for (var j = 0; j < occupied.length; j++) {
            var p = occupied[j];
            if (x < p.x + p.w && x + w.gridW > p.x && y < p.y + p.h && y + w.gridH > p.y) {
              canPlace = false;
              break;
            }
          }
          if (canPlace) {
            w.gridX = x;
            w.gridY = y;
            placed = true;
          }
        }
      }
      if (!placed) {
        // Couldn't find a free position, stack at bottom
        w.gridX = 0;
        w.gridY = GRID_ROWS - w.gridH;
      }
    }
    occupied.push({ x: w.gridX, y: w.gridY, w: w.gridW, h: w.gridH });
  });
}

window.refreshMarketWidgetsData = function () {
  Object.keys(widgets).forEach(function (id) {
    var cfg = widgets[id];
    if (!cfg || !cfg.visible) return;
    if (id.indexOf('_mercado_') < 0) return;
    var source = cfg.source || '';
    if (source !== 'ibge' && source !== 'agrodoc') return;
    var cultureId = id.split('_mercado_')[0];
    var uf = cfg.selectedUf || '';
    if (!window.CultureData || typeof CultureData.init !== 'function') return;

    CultureData.init()
      .then(function () {
        return CultureData.getMetricsBySource(cultureId, source, uf, { realOnly: true });
      })
      .then(function (result) {
        if (!result || result._source === 'no_data') return;
        var metrics = result.metrics || [];
        var matchedMetric = null;
        metrics.forEach(function (m) {
          if (m.key === cfg.metricKey) matchedMetric = m;
        });

        var newChartData = null;
        if (result.history_by_metric && Array.isArray(result.history_by_metric[cfg.metricKey])) {
          var hist = result.history_by_metric[cfg.metricKey];
          var labels = hist.map(function (h) {
            return String(h.ano);
          });
          var data = hist.map(function (h) {
            return typeof h.valor === 'number' ? h.valor : null;
          });
          var dPal = chartPalette();

          // ── Estilo do widget: cor principal + variante ──
          var rStyleMeta =
            cfg.chartStyleCategory &&
            cfg.chartStyleVariant &&
            window.AmpliChartStyles &&
            AmpliChartStyles.variant
              ? AmpliChartStyles.variant(cfg.chartStyleCategory, cfg.chartStyleVariant)
              : null;
          var chartDatasets = [
            {
              label: matchedMetric ? matchedMetric.label : cfg.metricKey,
              data: data,
              borderColor: cfg._mainColor || dPal.accent,
              backgroundColor: dPal.accentFill,
              borderWidth: 4,
            },
          ];

          // Reinsere séries comparadas preservadas no widget
          (cfg._compareSeries || []).forEach(function (c) {
            if (!c || !c.data) return;
            chartDatasets.push({
              label: c.label || 'Comparada',
              data: labels.map(function (y) {
                return Object.prototype.hasOwnProperty.call(c.data, y) ? c.data[y] : null;
              }),
              borderColor: c.color || '#f59e0b',
              borderWidth: 4,
            });
          });

          if (window.AmpliChartStyles && rStyleMeta) {
            chartDatasets.forEach(function (ds) {
              AmpliChartStyles.applyDataset(ds, cfg.chartStyleCategory, cfg.chartStyleVariant, {
                nopoints: rStyleMeta.type === 'line' && cfg.chartStyleVariant !== 'comPontos',
              });
            });
          }
          newChartData = { labels: labels, datasets: chartDatasets };
          cfg._mainColor =
            cfg._chartData && cfg._chartData.datasets && cfg._chartData.datasets[0]
              ? cfg._chartData.datasets[0].borderColor || dPal.accent
              : dPal.accent;
        }

        var changed = false;
        if (newChartData && JSON.stringify(newChartData) !== JSON.stringify(cfg._chartData)) {
          cfg._chartData = newChartData;
          cfg._cardHistory = result.history_by_metric
            ? result.history_by_metric[cfg.metricKey] || []
            : [];
          changed = true;
        }
        if (matchedMetric && JSON.stringify(matchedMetric) !== JSON.stringify(cfg._lastMetric)) {
          cfg._lastMetric = matchedMetric;
          changed = true;
        }
        if (changed) {
          saveWidgetsLayout();
          var el = document.getElementById('widget-' + id);
          if (el) {
            var canvas = el.querySelector('canvas');
            if (canvas && newChartData) {
              if (chartInstances[canvas.id]) {
                chartInstances[canvas.id].destroy();
                delete chartInstances[canvas.id];
              }
              var chartCfg = buildMarketChartConfig(id, canvas);
              if (chartCfg) {
                chartInstances[canvas.id] = new Chart(canvas, chartCfg);
                watchChartResize(canvas);
                canvas.classList.add('reveal-chart');
              }
            }
          }
        }
      })
      .catch(function () {});
  });
};
// Helper: sombra = mesma cor do fundo do widget (fix #sombra-widget — background e sombra mesma cor)
function _widgetShadowForBg(bg, isHover) {
  if (!bg || bg === 'transparent' || bg === 'rgba(0, 0, 0, 0)') return '';
  try {
    var d = document.createElement('div');
    d.style.background = bg;
    d.style.display = 'none';
    document.body.appendChild(d);
    var cs = getComputedStyle(d).backgroundColor;
    document.body.removeChild(d);
    var m = cs.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (m) {
      var r = m[1],
        g = m[2],
        b = m[3];
      if (isHover)
        return (
          '0 4px 14px rgba(' +
          r +
          ',' +
          g +
          ',' +
          b +
          ',0.18), 0 8px 24px rgba(' +
          r +
          ',' +
          g +
          ',' +
          b +
          ',0.12)'
        );
      return (
        '0 2px 8px rgba(' +
        r +
        ',' +
        g +
        ',' +
        b +
        ',0.12), 0 4px 14px rgba(' +
        r +
        ',' +
        g +
        ',' +
        b +
        ',0.08)'
      );
    }
  } catch (e) {}
  return '';
}
window._widgetShadowForBg = _widgetShadowForBg;
window.renderWidgetsOnMatrix = function () {
  try {
    var _logDetails = {
      caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 120),
      count: (function () {
        try {
          return Object.keys(widgets || {}).length;
        } catch (e) {
          return 0;
        }
      })(),
      visible: (function () {
        try {
          return Object.values(widgets || {}).filter(function (w) {
            return w.visible;
          }).length;
        } catch (e) {
          return 0;
        }
      })(),
      isEdit: !!(
        widgetEditMode ||
        customMode ||
        (window.widgetbarState && window.widgetbarState.isCustomMode)
      ),
    };
    // Log detalhado de cada widget com formatacao para detectar perda no final
    try {
      var _fmt = {};
      Object.keys(widgets || {}).forEach(function (k) {
        var c = widgets[k];
        if (!c || !c.visible) return;
        _fmt[k] = {
          bg: c.bgColor || 'none',
          chart:
            (c.chartSubtype || c.chartType || 'none') +
            '/' +
            (c.chartStyleCategory || '') +
            ':' +
            (c.chartStyleVariant || ''),
          meta: c._metaEnabled ? c._metaValue : 'off',
        };
      });
      _logDetails.fmt = _fmt;
    } catch (e) {}
    dashboardLog('renderWidgetsOnMatrix', _logDetails);
  } catch (e) {}
  var container = document.querySelector('.matrix-container');
  if (!container) {
    try {
      dashboardLog('renderWidgetsOnMatrix:abort', { reason: 'no container' });
    } catch (e) {}
    return;
  }
  // SPA recria container -> garante que drag use o novo elemento
  if (typeof _matrixContainer !== 'undefined') _matrixContainer = container;

  container.style.setProperty('--grid-cols', GRID_COLS);
  container.style.setProperty('--grid-rows', GRID_ROWS);

  var isEdit = widgetEditMode || customMode;
  var count = 0;

  // 1. Mapear elementos DOM existentes
  var existingEls = {};
  container.querySelectorAll('.bento-block').forEach(function (el) {
    var wId = el.id.replace('widget-', '');
    existingEls[wId] = el;
  });

  // 2. Sincronizar modelo → DOM
  Object.entries(widgets).forEach(function ([id, config]) {
    if (!config.visible) return;
    count++;
    var el = existingEls[id];
    var newHtml = generateWidgetContent(id, config);

    if (el) {
      // Widget existe → atualizar posicao
      var newCol = config.gridX + 1 + ' / span ' + config.gridW;
      var newRow = config.gridY + 1 + ' / span ' + config.gridH;
      if (el.style.gridColumn !== newCol) el.style.gridColumn = newCol;
      if (el.style.gridRow !== newRow) el.style.gridRow = newRow;
      el.style.setProperty('--widget-index', count);
      el.classList.toggle('widget-edit-mode', !!isEdit);

      // Reatividade granular: só atualiza o HTML se mudou
      if (el.innerHTML !== newHtml) {
        // Destroi os gráficos APENAS desse widget desatualizado
        el.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
          if (chartInstances[c.id]) {
            try {
              chartInstances[c.id].destroy();
            } catch (e) {}
            delete chartInstances[c.id];
          }
        });
        el.innerHTML = newHtml;
        if (isEdit) addEditModeElements(el, id);
      }

      delete existingEls[id];
    } else {
      // Widget novo → criar elemento (batch via fragment para evitar reflow por widget)
      el = document.createElement('div');
      el.id = 'widget-' + id;
      el.className = 'bento-block lc-panel' + (isEdit ? ' widget-edit-mode' : '');
      el.style.gridColumn = config.gridX + 1 + ' / span ' + config.gridW;
      el.style.gridRow = config.gridY + 1 + ' / span ' + config.gridH;
      el.style.setProperty('--widget-index', count);
      el.innerHTML = newHtml;
      // if (config.bgColor) { el.style.setProperty('background', config.bgColor, 'important'); el.style.setProperty('background-image', 'none', 'important'); }
      // Sombra = mesma cor do fundo (widget) — por widget
      try {
        // var effBgNew = config.bgColor || (document.documentElement.classList.contains('dark') ? 'rgba(0,0,0,0.95)' : 'rgba(255,255,255,0.95)');
        // var shNew = _widgetShadowForBg(effBgNew, false);
        // var shHoverNew = _widgetShadowForBg(effBgNew, true);
        // if (shNew) { el.style.setProperty('--widget-shadow', shNew, 'important'); el.style.setProperty('box-shadow', shNew, 'important'); }
        // if (shHoverNew) el.style.setProperty('--widget-shadow-hover', shHoverNew, 'important');
      } catch (e) {}
      if (isEdit) addEditModeElements(el, id);
      // batch: cola no fragment, append único após loop
      if (!window._newWidgetsFragment)
        window._newWidgetsFragment = document.createDocumentFragment();
      window._newWidgetsFragment.appendChild(el);
    }

    // Aplicar bgColor e sombra (mesma cor) — com !important para sobrepor o gradiente do tema
    /*
                  if (config.bgColor) {
                      if (el.style.getPropertyValue('background') !== config.bgColor) { el.style.setProperty('background', config.bgColor, 'important'); el.style.setProperty('background-image', 'none', 'important'); }
                      try{
                          var shUpd = _widgetShadowForBg(config.bgColor, false);
                          var shHoverUpd = _widgetShadowForBg(config.bgColor, true);
                          if (shUpd) { el.style.setProperty('--widget-shadow', shUpd, 'important'); el.style.setProperty('box-shadow', shUpd, 'important'); }
                          if (shHoverUpd) el.style.setProperty('--widget-shadow-hover', shHoverUpd, 'important');
                      }catch(e){}
                  } else {
                      if (el.style.getPropertyValue('background')) { el.style.removeProperty('background'); el.style.removeProperty('background-image'); }
                      try{
                          var defBgUpd = document.documentElement.classList.contains('dark') ? 'rgba(0,0,0,0.95)' : 'rgba(255,255,255,0.95)';
                          var shDefUpd = _widgetShadowForBg(defBgUpd, false);
                          var shHoverDefUpd = _widgetShadowForBg(defBgUpd, true);
                          if (shDefUpd) { el.style.setProperty('--widget-shadow', shDefUpd, 'important'); el.style.setProperty('box-shadow', shDefUpd, 'important'); }
                          if (shHoverDefUpd) el.style.setProperty('--widget-shadow-hover', shHoverDefUpd, 'important');
                      }catch(e){}
                  }
                  */
  });
  // batch append novos widgets de uma vez (1 reflow vs N)
  if (window._newWidgetsFragment && window._newWidgetsFragment.childNodes.length) {
    container.appendChild(window._newWidgetsFragment);
    window._newWidgetsFragment = null;
  }

  // 3. Remover widgets que nao existem mais no modelo
  Object.keys(existingEls).forEach(function (id) {
    var el = existingEls[id];
    el.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
      if (chartInstances[c.id]) {
        chartInstances[c.id].destroy();
        delete chartInstances[c.id];
      }
    });
    el.remove();
  });

  // 4. Status
  var statusEl = document.getElementById('widget-status');
  if (statusEl) statusEl.textContent = count + ' ativos';

  // 5. Re-atar listeners de drag nos elementos em edit mode
  if (isEdit) initWidgetDragging();

  // 6. Restaurar selecao
  if (_selectedWidgetId) {
    var selEl = document.getElementById('widget-' + _selectedWidgetId);
    if (selEl) selEl.classList.add('widget-selected');
  }

  // 7. Iniciar charts apenas para widgets novos
  initChartsForWidgets();

  // 8. Ajustar conteudo de cada widget ao tamanho da caixa
  scaleWidgetContentSize();
};

// ============================================
// CONTENT FITTER (responsivo) - gera/renderiza o conteudo
// conforme a largura e altura reais de cada widget, sem cortes.
// ResizeObserver no bento-block -> buckets de tamanho, re-render
// ao cruzar niveis, --wsz/--hsz expostos e charts re-dimensionados.
// ============================================
window.scaleWidgetContentSize = function () {
  document.querySelectorAll('.matrix-container .bento-block').forEach(function (block) {
    if (block._fitObs) return;
    var box = block.querySelector(':scope > .widget-content');
    if (!box) {
      block._fitObs = true;
      return;
    }
    var hasMap = box.querySelector('[id^="map-"]');
    if (hasMap) {
      block._fitObs = true;
      return;
    }

    var widgetId = block.id ? block.id.replace('widget-', '') : '';
    var lastBucket = null;
    var rbTimer = null;

    function bucketOf(w, h) {
      if (w < 260 || h < 150) return 'xs';
      if (w < 420 || h < 240) return 'sm';
      if (w < 700 || h < 400) return 'md';
      if (w < 1000 || h < 620) return 'lg';
      return 'xl';
    }

    function resizeCharts() {
      box.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
        var inst = chartInstances[c.id];
        if (inst && typeof inst.resize === 'function') inst.resize();
      });
    }

    function rerenderContent() {
      var cfg = window.widgets && widgets[widgetId];
      var cur = block.querySelector(':scope > .widget-content');
      if (!cur || !cfg) return;
      cur.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
        if (chartInstances[c.id]) {
          try {
            chartInstances[c.id].destroy();
          } catch (e) {}
          delete chartInstances[c.id];
        }
      });
      cur.innerHTML = getWidgetSpecificContent(widgetId);
      if (typeof initChartsForWidgets === 'function') initChartsForWidgets();
    }

    function applySize() {
      var w = block.clientWidth,
        h = block.clientHeight;
      if (!w || !h) return;
      block.style.setProperty('--wsz', w + 'px');
      block.style.setProperty('--hsz', h + 'px');

      var bucket = bucketOf(w, h);
      resizeCharts();

      if (bucket !== lastBucket) {
        lastBucket = bucket;
        block.setAttribute('data-size', bucket);
        if (rbTimer) clearTimeout(rbTimer);
        // Re-render ao cruzar níveis: o conteudo se adapta
        // (largo/compacto, numero de itens, layout) sem cortes
        rbTimer = setTimeout(rerenderContent, 90);
      }
    }

    applySize();
    try {
      block._fitObs = new ResizeObserver(applySize);
      block._fitObs.observe(block);
    } catch (e) {
      block._fitObs = true;
    }
  });
};

function addEditModeElements(el, id) {
  var badge = document.createElement('div');
  badge.className = 'edit-mode-badge';
  badge.innerHTML = '<i class="bi bi-arrows-move text-[8px]"></i>';
  el.appendChild(badge);

  var dirs = ['se', 'sw', 'ne', 'nw', 'e', 'w', 's', 'n'];
  for (var d = 0; d < dirs.length; d++) {
    (function (dir) {
      var rh = document.createElement('div');
      rh.className = 'resize-handle edge-' + dir;
      rh.dataset.widget = id;
      rh.dataset.dir = dir;
      rh.title = 'Redimensionar';
      el.appendChild(rh);
      rh.addEventListener('mousedown', function (ev) {
        ev.preventDefault();
        ev.stopImmediatePropagation();
        startResize(ev, this.dataset.widget, this.dataset.dir);
      });
    })(dirs[d]);
  }
}

function removeEditModeElements(el) {
  el.querySelectorAll('.edit-mode-badge, .resize-handle').forEach(function (e) {
    e.remove();
  });
}
window.addEditModeElements = addEditModeElements;
window.removeEditModeElements = removeEditModeElements;
// Sincroniza DOM de edição sem toggle (útil para widgetbar)
window.syncWidgetEditDOM = function (isEdit) {
  var container = document.querySelector('.matrix-container');
  if (!container) return;
  container.classList.toggle('editing', !!isEdit);
  container.querySelectorAll('.bento-block').forEach(function (el) {
    var wId = el.id.replace('widget-', '');
    el.classList.toggle('widget-edit-mode', !!isEdit);
    if (isEdit) {
      if (wId && !el.querySelector('.edit-mode-badge')) addEditModeElements(el, wId);
    } else {
      el.classList.remove('widget-selected');
      removeEditModeElements(el);
    }
  });
  if (isEdit && typeof window.initWidgetDragging === 'function') {
    try {
      window.initWidgetDragging();
    } catch (e) {}
  }
};

window.generateWidgetContent = function (id, config) {
  var type = WIDGET_TYPES[id] || { icon: 'bi-app-indicator', title: 'Cultura' };
  /* Este `return ''` é o que fazia um widget recém-criado aparecer como
   * um buraco na matriz: o `addWidget` criava o contentor, o
   * `generateWidgetContent` devolvia string vazia, e o bloco ficava lá
   * sem nada dentro. `getWidgetSpecificContent` (abaixo) já tem um
   * fallback seguro para ids que não conhece, portanto deixar o
   * contentor nascer é melhor do que nascer vazio — o texto
   * "sem dado" é um estado legível; um retângulo em branco não é.
   * A guarda que sobrou trata apenas `cultura-*` sem configuração. */
  if (
    id.indexOf('cultura-') === 0 &&
    (!config || (!config.selectedRecords && !config.metricKey && id.indexOf('_mercado_') < 0))
  ) {
    return '<div class="flex items-center justify-center h-full text-xs text-slate-400 p-4"><i class="bi bi-grid-3x3-gap text-lg mr-2"></i>Selecione os registros no painel de edição</div>';
  }

  var contentHtml =
    '<div class="widget-content p-2 overflow-auto absolute inset-0 flex flex-col">' +
    getWidgetSpecificContent(id) +
    '</div>';
  return contentHtml;
};

window.getWidgetSpecificContent = function (id) {
  var d = dashboardData;
  var w = widgetDataCache || {};
  var safras = w.safras || {};
  var fin = w.financeiro || {};
  var est = w.estoque || {};
  var anim = w.animais || {};
  var maq = w.maquinarios || {};
  var talhoes = w.talhoes || {};
  var insumos = w.insumos || {};
  var funcs = w.funcionarios || {};
  var apiario = w.apiario || {};
  var prop = w.propriedade || {};

  function fmt(n, decimals) {
    return n != null && !isNaN(n)
      ? Number(n).toLocaleString('pt-BR', {
          minimumFractionDigits: decimals || 0,
          maximumFractionDigits: decimals || 0,
        })
      : '---';
  }
  function fmtMoney(n) {
    return n != null && !isNaN(n)
      ? 'R$ ' +
          Number(n).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : '---';
  }

  // ── Dados de clima/alertas/novidades (dashboardData real, com fallback) ──
  var climaData = (d && d.clima) || w.weather || null;
  var climaAtual = (climaData && climaData.atual) || null;
  var climaPrev = (climaData && climaData.previsao) || [];
  var climaFonte = (climaData && climaData.fonte) || (d && d.clima_fonte) || '';
  var climaCidade = (climaData && climaData.cidade) || '';
  var fonteLabel =
    {
      inmet: 'INMET',
      openweathermap: 'OpenWeatherMap',
      'open-meteo': 'Open-Meteo',
      sem_fonte: 'Sem fonte',
      simulado: 'Simulado',
    }[climaFonte] ||
    climaFonte ||
    '';
  var alertaItems = (d && d.alertas_list) || [];
  var novidadeItems = (d && d.novidades) || [];
  var wCfgSize = window.widgets && window.widgets[id];
  var widgetLargo = !wCfgSize || wCfgSize.gridW >= 8;

  /* O icone do alerta: so o simbolo, sem circulo preenchido.
   * O fundo era `bg-rose-100` / `bg-amber-100` / `bg-sky-100` — uma
   * bolha de cor atras de cada linha que repetia o que o proprio
   * simbolo ja diz. Em tres linhas de alerta empilhadas o que se
   * lia nao era o alerta, era a fila de circulos.
   * A cor continua a estar no simbolo: e' ela que distingue
   * critico de atencao de informativo. */
  function itemIconHtml(item) {
    var nivel = item.nivel || 'info';
    var cor =
      nivel === 'critical'
        ? 'text-rose-400'
        : nivel === 'warning'
          ? 'text-amber-400'
          : 'text-sky-400';
    return (
      '<i class="bi ' +
      (item.icone || 'bi-exclamation-circle') +
      ' text-[13px] ' +
      cor +
      ' shrink-0 leading-none"></i>'
    );
  }

  window.switchWidgetInnerTab = function (widgetId, tabId) {
    var container = document.getElementById('widget-tabs-' + widgetId);
    if (!container) return;
    var btns = container.querySelectorAll('.widget-tab-btn');
    btns.forEach(function (btn) {
      if (btn.getAttribute('data-tab') === tabId) {
        btn.classList.add(
          'bg-white',
          'dark:bg-slate-700',
          'text-slate-800',
          'dark:text-white',
          'shadow-sm',
          'font-semibold'
        );
        btn.classList.remove('text-slate-500', 'hover:text-slate-700');
      } else {
        btn.classList.remove(
          'bg-white',
          'dark:bg-slate-700',
          'text-slate-800',
          'dark:text-white',
          'shadow-sm',
          'font-semibold'
        );
        btn.classList.add('text-slate-500', 'hover:text-slate-700');
      }
    });
    var contents = container.querySelectorAll('.widget-tab-content');
    contents.forEach(function (content) {
      if (content.getAttribute('data-tab') === tabId) {
        content.classList.remove('hidden');
      } else {
        content.classList.add('hidden');
      }
    });
  };

  /* A marca de "não há medição" no painel.
   *
   * O backend devolve `null` para o que não mediu (roi, custo_ha) e
   * expõe `area_medida` para o que não dá para dividir. Antes disto
   * esses `null` viravam 0 — e "R$ 0,00/ha" ou "+0,0% de ROI" são
   * afirmações. Um rótulo curto e cinzento é uma resposta honesta.
   * HTML em vez de texto simples porque o KPI já é HTML montado. */
  window.SEM_DADO =
    '<span class="text-theme-tick" style="font-size:0.55em;font-weight:600;letter-spacing:0.02em">sem dado</span>';

  /* O cartao do KPI. Antes disto era um SEGUNDO cartao dentro do
   * widget — `background:var(--cor-fundo-card)` e uma borda propria
   * — que e' o que se via como "borda interna" a meio do painel.
   * A moldura pertence ao `.bento-block` (o widget inteiro), em
   * verde esmeralda; aqui dentro nao ha fundo nem borda.
   *
   * `min-w-0` e' obrigatorio: `.widget-content` e' um contentor
   * flex, e sem ele o KPI fica na largura do texto e transborda
   * do widget em vez de encolher. `h-full` tambem nao: mediria o
   * contentor em vez do espaco que sobra, e empurraria a legenda
   * (que tem `margin-top:auto`) para fora do widget. */
  window.buildModernKpiHtml = function (title, value, subtitle, subtitleVal, trendIsPositive) {
    var html = '<div class="amp-kpi flex flex-col justify-center gap-1 min-w-0">';

    /* O rotulo usa `--pal-tick` (o cinza de ticks do sistema, em vez do
     * `text-slate-500` de antes) e `title` para o texto completo ao
     * passar o rato.
     *
     * MEDIDO 2026-10-05: `truncate` aqui dava 0 px de altura ao rotulo
     * e cortava o texto em duas linhas. No widget `kpi-area` a caixa
     * interna tem 64 px e o rotulo "Área Total" precisa de 65 px — 1 px
     * de sobra, e o `truncate` cortava o "a".
     *
     * `truncate` e' `white-space:nowrap` + `overflow:hidden`, e num
     * flex-column com `overflow:hidden` no contentor o elemento chega a
     * ter ALTURA ZERO. Nao e' que o texto era pequeno: o rotulo nao
     * tinha onde estar.
     *
     * Agora o rotulo QUEBRA (`break-words` + `leading-tight`), que e' o
     * que se pede: um rotulo que diz o que e' o dado e' melhor do que um
     * rotulo cortado que obriga a passar o rato para adivinhar. */
    html +=
      '<span class="amp-kpi__label text-[11px] font-bold uppercase tracking-wider leading-tight break-words hyphens-auto" title="' +
      title +
      '">' +
      title +
      '</span>';

    /* O numero e' o que se le primeiro. A cor vem do token de texto
     * do sistema (`--text-primary`), nao de `text-slate-800`, para
     * acompanhar a troca de tema sem uma classe de cada vez. */
    html +=
      '<p class="amp-kpi__value text-3xl font-extrabold leading-tight break-words">' +
      value +
      '</p>';

    if (subtitle || subtitleVal) {
      var trendColor =
        trendIsPositive === true
          ? 'text-emerald-500'
          : trendIsPositive === false
            ? 'text-rose-500'
            : 'text-slate-400';
      var trendBg =
        trendIsPositive === true
          ? 'bg-emerald-500/10'
          : trendIsPositive === false
            ? 'bg-rose-500/10'
            : 'bg-slate-500/10';
      var trendIcon = trendIsPositive === true ? '↗' : trendIsPositive === false ? '↘' : '—';

      /* `amp-kpi__foot` e' o contentor da legenda. O `flex-wrap` e' o que
       * resolve o caso apertado COM badge: sem ele o badge (`shrink-0`)
       * e a legenda disputam a mesma linha, e num widget estreito a
       * legenda perde e desaparece. Com wrap, desce de linha. */
      html +=
        '<div class="amp-kpi__foot text-[10px] font-medium mt-auto pt-1 flex items-center gap-1.5 min-w-0">';
      if (subtitleVal) {
        html +=
          '<span class="' +
          trendColor +
          ' ' +
          trendBg +
          ' px-1.5 py-0.5 rounded-md flex items-center gap-0.5 font-bold">' +
          subtitleVal +
          ' <span class="text-[9px]">' +
          trendIcon +
          '</span></span>';
      }
      /* `truncate` cortava a legenda em "Manutenções pend..." e em
       * "(Receitas − Despesas) / Receitas" — o texto que o produtor
       * tem de ler desaparecia. `amp-clamp-2` da ate duas linhas. */
      if (subtitle) {
        html += '<span class="amp-clamp-2">' + subtitle + '</span>';
      }
      html += '</div>';
    }
    html += '</div>';
    return html;
  };

  function buildClimaKpiHtml() {
    var html = '<div class="flex flex-col h-full p-2 gap-1.5 min-w-0">';
    /* Cabecalho: cidade a esquerda, fonte a direita, no topo. O badge da fonte
     * deixa de ser uma pílula com fundo: e' um rotulo, e o fundo
     * era mais uma superficie dentro do widget. */
    html += '<div class="flex items-center justify-between gap-2 shrink-0">';
    html +=
      '<span class="text-[10px] font-semibold text-slate-500 dark:text-slate-300 truncate">' +
      (climaCidade || '') +
      '</span>';
    if (fonteLabel)
      html +=
        '<span class="text-[8px] uppercase font-semibold tracking-wide text-sky-500 dark:text-sky-400 shrink-0">' +
        fonteLabel +
        '</span>';
    html += '</div>';

    /* Leitura actual em TRES COLUNAS:
     *
     *   esquerda  — temperatura
     *   centro    — icone do tempo + a descricao dele
     *   direita   — humidade
     *
     * O que estava a sobrepor era uma pilha em `flex-col` com o
     * icone a `text-4xl` e a descricao e a humidade numa linha
     * `flex-wrap gap-3`: quando o widget encolhia, essa linha nao
     * tinha espaco para as duas pecas e o `flex-wrap` deixava a
     * segunda por cima da primeira. Um `grid` de tres colunas nao
     * tem esse problema por construcao — cada texto vive na sua
     * pista e nunca pode cair na do vizinho. Por isso aqui e'
     * grid e nao flex.
     *
     * `min-w-0` em cada celula e' o que permite o `truncate`
     * funcionar: sem ele a celula fica na largura do texto e
     * transborda da pista. O rotulo vai por cima do valor, que e'
     * a ordem que se le sem depender da cor. */
    if (climaAtual) {
      html += '<div class="flex-1 min-h-0 flex items-center">';
      html += '<div class="w-full grid grid-cols-3 items-center gap-2 text-center">';

      html += '<div class="min-w-0">';
      html += '<div class="text-[9px] uppercase tracking-wide text-slate-400">Temp.</div>';
      html +=
        '<div class="text-2xl font-bold leading-tight">' +
        (climaAtual.temp != null ? climaAtual.temp + '°C' : '---') +
        '</div>';
      html += '</div>';

      html += '<div class="min-w-0">';
      html +=
        '<i class="bi ' +
        (climaAtual.icone || 'bi-sun') +
        ' text-3xl text-amber-400 leading-none"></i>';
      html +=
        '<div class="text-[11px] text-slate-500 truncate mt-0.5">' +
        (climaAtual.descricao || '') +
        '</div>';
      html += '</div>';

      html += '<div class="min-w-0">';
      html += '<div class="text-[9px] uppercase tracking-wide text-slate-400">Umidade</div>';
      html +=
        '<div class="text-2xl font-bold leading-tight">' +
        (climaAtual.umidade != null ? climaAtual.umidade + '%' : '---') +
        '</div>';
      html += '</div>';

      html += '</div>';
      html += '</div>';
    }

    /* Previsao. As tres caixas tinham larguras iguais mas alturas
     * diferentes: a "Hoje" levava uma linha extra de humidade
     * (so quando `widgetLargo`) e por isso nascia mais alta que as
     * outras duas. `items-stretch` + uma estrutura igual para as
     * tres resolve: nenhuma depende do que tem dentro.
     *
     * E mais largas: `gap-1` com `px-0.5` deixava-as coladas e
     * estreitas no meio do widget, num bloco que ocupava so uma
     * fraccao da largura. */
    if (climaPrev.length) {
      var dias = climaPrev.slice(0, 3);
      html += '<div class="flex gap-2 shrink-0 items-stretch">';
      dias.forEach(function (dia) {
        html += '<div class="flex-1 min-w-0 text-center px-2 py-1.5 amp-dia-card">';
        html += '<div class="text-[9px] text-slate-500 truncate">' + (dia.dia || '') + '</div>';
        html +=
          '<i class="bi ' +
          (dia.icone || 'bi-cloud') +
          ' text-sm text-amber-500 block mt-0.5"></i>';
        html +=
          '<div class="text-[11px] font-semibold mt-0.5">' +
          (dia.temp != null ? dia.temp + '°' : '---') +
          '</div>';
        /* A humidade fica sempre, nas tres: e' o que iguala as
         * alturas, e sem ela as caixas so se pareciam quando o
         * widget e' largo. Vem '--' quando nao ha medicao, que
         * e' diferente de zero. */
        html +=
          '<div class="text-[8px] text-slate-400">' +
          (dia.umidade != null ? dia.umidade + '%' : '--') +
          '</div>';
        html += '</div>';
      });
      html += '</div>';
    }
    html += '</div>';
    return html;
  }

  function buildAlertasKpiHtml() {
    var total = alertaItems.length || (d && d.alertas != null ? d.alertas : 0);
    var maxItens = widgetLargo ? 8 : 3;
    var html = '<div class="flex flex-col h-full p-2 gap-1.5 min-w-0">';
    /* Cabecalho: simbolo, numero e rotulo NA MESMA LINHA, alinhados pela
     * base. Antes o numero e "Alertas" estavam empilhados num
     * bloco a parte do circulo — tres niveis de leitura para
     * dizer "ha 3 alertas". O circulo preenchido tambem foi
     * para: o simbolo ja diz que e' um aviso, e o fundo vermelho
     * repetia isso do tamanho do widget. */
    /* `items-center`, nao `items-baseline`. As baselines nao podem coincidir
     * quando as tres pecas tem corpos diferentes: o "3" a 20px
     * empurrava a sua baseline para baixo do "ALERTAS" a 10px, e
     * o resultado era o numero a parecer caido. Alinhar pelo
     * CENTRO das caixas da que resolve: o glifo, o digito e o
     * rotulo ficam a mesma altura, que e' o que se le.
     *
     * `leading-none` so no icone — a fonte de icones nao tem
     * altura de linha propria, e sem isso a caixa do `<i>` fica
     * maior que o glifo e o empurra para baixo. Nos `<span>` de
     * texto fica a altura natural. */
    html += '<div class="flex items-center gap-1.5 shrink-0">';
    html +=
      '<i class="bi bi-exclamation-triangle text-theme-error text-[15px] leading-none shrink-0"></i>';
    html += '<span class="text-xl font-bold">' + total + '</span>';
    html +=
      '<span class="text-[10px] uppercase tracking-wide text-slate-400">' +
      (total === 1 ? 'Alerta' : 'Alertas') +
      '</span>';
    html += '</div>';
    if (alertaItems.length) {
      html += '<div class="flex-1 min-h-0 overflow-hidden space-y-1">';
      alertaItems.slice(0, maxItens).forEach(function (a) {
        /* Cada linha e' uma LINHA, nao uma caixa: sem fundo e sem `rounded-md`.
         * O `bg-slate-50 dark:bg-slate-800/40` desenhava tres
         * cartoes empilhados dentro do widget — a segunda camada
         * de fundo que o widget nao deve ter. O que separa as
         * linhas agora e' espaco mais o filete do contentor
         * (`.amp-alerta-linha + .amp-alerta-linha`, em
         * dashboard-index.css).
         *
         * `amp-clamp-2` em vez de `truncate`: "Manutenção:
         * Derrickadeira Jacto DM-5 em 30/10" nao cabia numa linha e
         * era cortada a meio da palavra, sem dizer que havia
         * mais. Duas linhas mostram o alerta inteiro. */
        html += '<div class="amp-alerta-linha flex items-start gap-1.5 text-[10px] py-1 min-w-0">';
        html += itemIconHtml(a);
        html += '<span class="amp-clamp-2">' + (a.msg || '') + '</span>';
        html += '</div>';
      });
      if (alertaItems.length > maxItens)
        html +=
          '<div class="text-[9px] text-slate-400 text-center">+' +
          (alertaItems.length - maxItens) +
          ' mais</div>';
      html += '</div>';
    } else {
      html +=
        '<div class="flex-1 flex items-center justify-center text-[11px] text-slate-400"><i class="bi bi-check-circle text-theme-ok mr-1.5"></i>Nenhum alerta ativo</div>';
    }
    html += '</div>';
    return html;
  }

  function buildNovidadesKpiHtml() {
    var maxItens = widgetLargo ? 8 : 4;
    var html = '<div class="flex flex-col h-full p-2 gap-1.5 min-w-0">';
    /* Mesmo desenho dos Alertas: simbolo, numero e rotulo na mesma linha, sem
     * circulo preenchido. As duas listas vivem lado a lado no painel
     * e partilham o `itemIconHtml`; com cabecalhos diferentes, o
     * olho tinha de ler duas vezes como o widget se orientava. */
    html += '<div class="flex items-center gap-1.5 shrink-0">';
    html += '<i class="bi bi-megaphone text-theme-alert text-[15px] leading-none shrink-0"></i>';
    html += '<span class="text-xl font-bold">' + novidadeItems.length + '</span>';
    html +=
      '<span class="text-[10px] uppercase tracking-wide text-slate-400">' +
      (novidadeItems.length === 1 ? 'Novidade' : 'Novidades') +
      '</span>';
    html += '</div>';
    if (novidadeItems.length) {
      html += '<div class="flex-1 min-h-0 overflow-hidden space-y-1">';
      novidadeItems.slice(0, maxItens).forEach(function (n) {
        /* Linha, nao caixa — igual aos Alertas, e pela mesma razao: o
         * `bg-slate-50 dark:bg-slate-800/40` era uma segunda
         * camada de fundo dentro do widget. O `amp-alerta-linha`
         * e' a classe que o CSS ja' conhece para dar o filete
         * de separacao. */
        html += '<div class="amp-alerta-linha flex items-start gap-1.5 text-[10px] py-1 min-w-0">';
        html += itemIconHtml(n);
        html += '<span class="amp-clamp-2">' + (n.msg || '') + '</span>';
        html += '</div>';
      });
      if (novidadeItems.length > maxItens)
        html +=
          '<div class="text-[9px] text-slate-400 text-center">+' +
          (novidadeItems.length - maxItens) +
          ' mais</div>';
      html += '</div>';
    } else {
      html +=
        '<div class="flex-1 flex items-center justify-center text-[11px] text-slate-400"><i class="bi bi-inbox mr-1.5"></i>Sem novidades por enquanto</div>';
    }
    html += '</div>';
    return html;
  }

  function semDados(label, hint) {
    return (
      '<span class="text-theme-tick" style="font-size:0.62em" title="' +
      (hint || 'Sem dados para ' + label + '. Cadastre registros e eles aparecerão aqui.') +
      '"><i class="bi bi-inbox mr-1"></i>Sem dados</span>'
    );
  }

  var content = {
    // ── KPIs de lançamentos (dados reais; nunca valores fixos) ──
    'kpi-vendas-totais': (function () {
      var v =
        fin && fin.receitas != null
          ? fin.receitas
          : d && d.financeiro && d.financeiro.total_receitas != null
            ? d.financeiro.total_receitas
            : 0;
      return window.buildModernKpiHtml(
        'Receitas',
        fmtMoney(v),
        'Soma das receitas lançadas',
        '',
        true
      );
    })(),
    'kpi-margem-bruta': (function () {
      var rec =
        fin && fin.receitas != null
          ? fin.receitas
          : d && d.financeiro && d.financeiro.total_receitas != null
            ? d.financeiro.total_receitas
            : 0;
      var desp =
        fin && fin.despesas != null
          ? fin.despesas
          : d && d.financeiro && d.financeiro.total_despesas != null
            ? d.financeiro.total_despesas
            : 0;
      /* Sem receita, `(rec - desp) / rec` nao se divide. O `? 0` que
       * estava aqui mostrava "0,0%" - que e' uma margem medida, e nao
       * e': e' a ausencia do denominador. */
      if (!(rec > 0)) {
        return window.buildModernKpiHtml(
          'Margem',
          window.SEM_DADO,
          'Sem receitas lancadas',
          '',
          null
        );
      }

      var margem = ((rec - desp) / rec) * 100;
      return window.buildModernKpiHtml(
        'Margem',
        fmt(margem, 1) + '%',
        '(Receitas − Despesas) / Receitas',
        '',
        margem >= 0
      );
    })(),
    'kpi-pedidos': (function () {
      /* `fin.lancamentos.length != null` e' sempre verdadeiro (um
       * length nunca e' null), logo o ramo `: 0` nunca corria. E' um
       * resto de um ternario antigo, inofensivo: sem lancamentos o
       * zero e' a resposta certa. */
      var n =
        fin && fin.lancamentos
          ? d && d.financeiro && d.financeiro.total_lancamentos != null
            ? d.financeiro.total_lancamentos
            : fin.lancamentos.length
          : 0;
      return window.buildModernKpiHtml(
        'Lançamentos',
        fmt(n, 0),
        'Receitas e despesas lançadas',
        '',
        true
      );
    })(),
    'kpi-melhor-cliente': (function () {
      var cat =
        fin && fin.por_categoria && fin.por_categoria.length
          ? fin.por_categoria.slice().sort(function (a, b) {
              return (b.total || 0) - (a.total || 0);
            })[0]
          : null;
      if (!cat || !cat.categoria)
        return window.buildModernKpiHtml(
          'Maior Categoria',
          fmtMoney(0),
          'Nenhuma categoria',
          '',
          true
        );
      return window.buildModernKpiHtml(
        'Maior Categoria',
        fmtMoney(cat.total || 0),
        cat.categoria,
        '',
        true
      );
    })(),

    // ── Existing KPIs (use dashboardData for backward compat) ──
    /* ─────────────────────────────────────────────────────────────
     * KPI SEM DADO ≠ KPI COM VALOR ZERO
     *
     * O `dashboard_data` (app/api/views/user.py) devolve `roi: null`
     * e `custo_ha: null` quando o denominador não existe — "não há
     * despesa registada" e "a área não está medida" são coisas que
     * se dizem, não 0,0% e R$ 0,00/ha.
     *
     * Estes três widgets deitavam fora esse contrato:
     *   - `kpi-roi`   null → 0, e ainda com o sinal `+` (0 >= 0), o
     *                que fazia "não sei" aparecer como "empatei".
     *   - `kpi-custo` null → RECALCULAVA com `|| 1` no divisor, e
     *                dividia a despesa real por 1 ha inventado —
     *                o mesmo defeito que o backend já tinha
     *                removido, reintroduzido em JS.
     *   - `kpi-area`  ignorava `area_medida`, que existe
     *                precisamente para esta pergunta.
     *
     * A regra daqui: se a fonte diz "não sei", o painel diz
     * "sem dado". Nunca preencher o vazio com um número plausível.
     * ───────────────────────────────────────────────────────────── */
    'kpi-roi': (function () {
      var roiVal = d && d.roi != null ? d.roi : null;
      if (roiVal === null && fin.receitas != null) {
        var despesasR = fin.despesas != null ? fin.despesas : 0;
        // Sem despesa não há ROI para calcular: não é 0, é indefinido.
        roiVal =
          despesasR > 0 ? Math.round(((fin.receitas - despesasR) / despesasR) * 1000) / 10 : null;
      }
      if (roiVal == null) {
        return window.buildModernKpiHtml(
          'ROI Operacional',
          window.SEM_DADO,
          'Sem despesas registadas',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'ROI Operacional',
        fmt(roiVal, 1) + '%',
        'Rentabilidade estimada',
        roiVal >= 0 ? '+' + fmt(roiVal, 1) + '%' : fmt(roiVal, 1) + '%',
        roiVal >= 0
      );
    })(),
    'kpi-custo': (function () {
      var custoVal = d && d.custo_ha != null ? d.custo_ha : null;
      /* O divisor `|| 1` produzia R$ 12.000,00/ha numa fazenda que
       * ninguém mediu. Só se divide por uma área REAL. */
      if (custoVal === null && fin.despesas != null && fin.despesas > 0) {
        var areaBruta =
          prop.area_total != null && parseFloat(prop.area_total) > 0
            ? parseFloat(prop.area_total)
            : talhoes.area_total != null && parseFloat(talhoes.area_total) > 0
              ? parseFloat(talhoes.area_total)
              : null;
        custoVal = areaBruta ? Math.round((fin.despesas / areaBruta) * 100) / 100 : null;
      }
      if (custoVal == null) {
        return window.buildModernKpiHtml(
          'Custo/Ha',
          window.SEM_DADO,
          'Cadastre a área da fazenda',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Custo/Ha',
        fmtMoney(custoVal),
        'Baseado em despesas/área',
        '',
        null
      );
    })(),
    'kpi-alertas': buildAlertasKpiHtml(),
    'kpi-manutencoes': (function () {
      /* `num === 0` com legenda "OK" dizia ao produtor que o
       * maquinário dele está tudo bem quando o que existia era
       * "não há campo". Ausência de dado não é sinal de saúde. */
      var num =
        d && d.os_pendentes != null
          ? d.os_pendentes
          : maq && maq.manutencao_pendente != null
            ? maq.manutencao_pendente
            : null;
      if (num == null) {
        return window.buildModernKpiHtml(
          'OS Pendentes',
          window.SEM_DADO,
          'Sem registro de manutenção',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'OS Pendentes',
        num,
        'Manutenções pendentes',
        num > 0 ? num + ' alertas' : 'OK',
        num === 0
      );
    })(),
    /* Umidade e temperatura seguem a MESMA regra dentro do mesmo
     * widget: sem leitura, mostra "--" e não inventa. Antes a
     * temperatura caía em "--°C" e a umidade em "0%" — o mesmo
     * widget, duas respostas diferentes para a mesma pergunta, e a
     * de umidade a dizer que o sensor mediu 0% de humidade. */
    'kpi-sensores': (function () {
      var um =
        d && d.umidade != null
          ? d.umidade
          : w.weather && w.weather.atual && w.weather.atual.umidade != null
            ? w.weather.atual.umidade
            : null;
      var tp =
        d && d.temperatura != null
          ? d.temperatura
          : w.weather && w.weather.atual && w.weather.atual.temp != null
            ? w.weather.atual.temp
            : null;
      // Allowlist, NÃO "fonte !== 'simulado'".
      //
      // A negação diz que tudo o que não seja 'simulado' é real.
      // Isso é falso por omissão: um `fonte` novo, mal escrito ou
      // inventado, passa como fonte verdadeira sem ninguém
      // reparar — e foi exactamente o que aconteceu quando o
      // fallback de clima passou a dizer "google clima". O painel
      // mostrou "Ativa" a verde sobre 28 °C escritos à mão.
      //
      // Uma lista do que é realmente real falha para o lado
      // seguro: o valor novo é tratado como não-real até alguém o
      // declarar aqui. O custo é uma linha; o custo da negação
      // foi um produtor a decidir irrigar por um número inventado.
      // `open-meteo` entrou na lista porque passou a ser a fonte
      // REAL do sistema: é a que `FonteDadosExterno` tem ativa, e a
      // que a IA já usava pelo serviço de coordenadas. Sem esta
      // linha, o painel marcaria a estação como "Simulada" por
      // baixo de uma medição verdadeira — o inverso do defeito
      // anterior, e igualmente enganador.
      var FONTES_CLIMA_REAIS = ['inmet', 'openweathermap', 'open-meteo'];
      var fonteReal = FONTES_CLIMA_REAIS.indexOf(climaFonte) !== -1;
      // "Sem fonte" e "Simulado" não são o mesmo aviso. A primeira
      // diz que não houve resposta; a segunda, que o número é
      // gerado. Confundir as duas faz o produtor procurar o
      // defeito onde não está.
      var rotuloEstacao = fonteReal
        ? 'Ativa'
        : climaFonte === 'sem_fonte'
          ? 'Sem fonte'
          : 'Simulada';
      var classeEstacao = fonteReal ? 'text-theme-ok' : 'text-theme-alert';
      /* Duas leituras lado a lado: o TIPO por cima e o VALOR por baixo, e o
       * estado da estacao numa linha propria no rodape.
       *
       * Antes era uma lista de linhas "rotulo ... valor" com a
       * humidade a ocupar a largura toda e a temperatura a
       * repetir o mesmo padrao por baixo, com a barra entre as
       * duas. Duas medidas que se leem em conjunto (ar e agua,
       * as duas entradas da estacao) ficam lado a lado: e' a
       * leitura de rezar, nao de tabela.
       *
       * A barra de humidade saiu. Com o valor ja em numero grande
       * ao lado da temperatura, so acrescentava um medidor sem
       * escala — "99%" e uma barra quase cheia dizem o mesmo, e
       * uma delas e' mais facil de ler. */
      return (
        '<div class="text-xs h-full flex flex-col justify-center gap-1.5">' +
        '<div class="grid grid-cols-2 gap-2">' +
        '<div class="text-center min-w-0">' +
        '<div class="text-[9px] uppercase tracking-wide text-slate-400">Temp.</div>' +
        '<div class="text-xl font-bold leading-tight">' +
        (tp != null ? tp + '°C' : '--') +
        '</div>' +
        '</div>' +
        '<div class="text-center min-w-0">' +
        '<div class="text-[9px] uppercase tracking-wide text-slate-400">Umidade</div>' +
        '<div class="text-xl font-bold leading-tight">' +
        (um != null ? um + '%' : '--') +
        '</div>' +
        '</div>' +
        '</div>' +
        '<div class="flex items-center justify-center gap-1.5 pt-1 border-t text-[10px] text-slate-400">' +
        '<span>Estação</span>' +
        '<span class="font-semibold ' +
        classeEstacao +
        '">' +
        rotuloEstacao +
        '</span>' +
        '</div>' +
        '</div>'
      );
    })(),
    'kpi-clima': buildClimaKpiHtml(),
    'kpi-novidades': buildNovidadesKpiHtml(),
    'kpi-caixa': (function () {
      /* Saldo 0 é um saldo legítimo (nada entrou, nada saiu) — mas
       * só se o campo existir. Sem campo nenhum, mostrá-lo como
       * R$ 0,00 afirma que o produtor não movimentou dinheiro,
       * e a verdade pode ser "não perguntámos". */
      var saldo = fin.saldo != null ? fin.saldo : d && d.fluxo_caixa != null ? d.fluxo_caixa : null;
      var mesFin =
        d && d.financeiro_mensal && d.financeiro_mensal.length
          ? d.financeiro_mensal[d.financeiro_mensal.length - 1]
          : null;
      var sub = mesFin && mesFin.receita != null ? '+ ' + fmtMoney(mesFin.receita) : '';
      if (saldo == null) {
        return window.buildModernKpiHtml(
          'Fluxo de Caixa',
          window.SEM_DADO,
          'Sem lançamentos financeiros',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Fluxo de Caixa',
        fmtMoney(saldo),
        'Neste mês',
        sub,
        saldo >= 0
      );
    })(),
    'kpi-calendario':
      '<div class="grid grid-cols-7 gap-0.5 text-xs p-1">' +
      (d && d.dias && d.dias.length
        ? d.dias
            .map(function (di) {
              return (
                '<div class="' +
                (di.destaque ? 'bg-theme-accent text-white rounded' : '') +
                ' p-1 text-center">' +
                di.num +
                '</div>'
              );
            })
            .join('')
        : '<p class="text-slate-400 col-span-7 text-center py-4">Sem calendário</p>') +
      '</div>',

    // ── New KPIs from real data ──
    'kpi-produtividade': (function () {
      /* `? … : 0` transformava "sem safras com produtividade" em
       * "0,0 sc/ha" — que é uma produtividade medida, e nula. */ var prod =
        safras.por_ano && safras.por_ano.length ? safras.por_ano[0].media_produtividade : null;
      if (prod == null) {
        return window.buildModernKpiHtml(
          'Produtividade Média',
          window.SEM_DADO,
          'Sem safras com produção',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Produtividade Média',
        fmt(prod, 1) + ' sc/ha',
        'Nas safras ativas',
        '',
        true
      );
    })(),
    'kpi-area': (function () {
      /* `area_medida` foi criado no backend exatamente para esta
       * pergunta e nunca foi lido aqui. Sem ele, "0,0 ha" é
       * indistinguível de "a fazenda foi medida e tem 0 ha". */
      var areaVal = null;
      if (prop.area_total != null && parseFloat(prop.area_total) > 0)
        areaVal = parseFloat(prop.area_total);
      if (areaVal == null && talhoes.area_total != null && parseFloat(talhoes.area_total) > 0)
        areaVal = parseFloat(talhoes.area_total);
      if (areaVal == null && safras.items && safras.items.length) {
        var sumA = safras.items.reduce(function (a, s) {
          return a + (parseFloat(s.area) || 0);
        }, 0);
        if (sumA > 0) areaVal = sumA;
      }
      if (areaVal == null) {
        return window.buildModernKpiHtml(
          'Área Total',
          window.SEM_DADO,
          'Cadastre a área da fazenda',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Área Total',
        fmt(areaVal, 1) + ' ha',
        'Total cadastrado',
        '',
        true
      );
    })(),
    'kpi-funcionarios': (function () {
      /* `num != null ? num : 0` dizia "0 ativos" quando o campo não
       * veio. Um produtor sem uma única pessoa registada é uma
       * afirmação; um payload sem o campo é ausência de resposta. */
      var num = funcs.ativos != null ? funcs.ativos : null;
      if (num == null) {
        return window.buildModernKpiHtml(
          'Equipe',
          window.SEM_DADO,
          'Sem registo de equipa',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Equipe',
        num + ' ativos',
        'De ' + (funcs.total || 0) + ' no total',
        '',
        true
      );
    })(),
    'kpi-animais': (function () {
      var num = anim.total_cabecas != null ? anim.total_cabecas : null;
      if (num == null) {
        return window.buildModernKpiHtml(
          'Rebanho',
          window.SEM_DADO,
          'Sem registo de rebanho',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Rebanho',
        fmt(num, 0) + ' cabeças',
        'Total atual',
        '',
        true
      );
    })(),
    'kpi-safras': (function () {
      var num = safras.total_safras != null ? safras.total_safras : null;
      var proxPlantio = d && d.tarefas && d.tarefas.length ? d.tarefas[0].nome : '';
      if (num == null) {
        return window.buildModernKpiHtml(
          'Safras Ativas',
          window.SEM_DADO,
          'Sem safras registadas',
          '',
          null
        );
      }
      return window.buildModernKpiHtml(
        'Safras Ativas',
        num,
        proxPlantio ? 'Próximo: ' + proxPlantio : 'Em andamento',
        '',
        true
      );
    })(),
    'kpi-insumos': (function () {
      /* Sem itens de insumo, o valor é 0 — e isso é verdade: não há
       * insumo em estoque, o valor é zero. A soma de uma lista
       * vazia é legitimamente 0, ao contrário de "não sei". */
      var val =
        insumos.items && insumos.items.length
          ? insumos.items.reduce(function (a, i) {
              return a + (i.valor_unitario || 0) * (i.quantidade || 0);
            }, 0)
          : 0;
      return window.buildModernKpiHtml(
        'Custo Insumos',
        fmtMoney(val),
        'Estimativa em estoque',
        '',
        false
      );
    })(),

    // ── Charts (canvas placeholders — initChartsForWidgets fills them) ──
    'chart-line': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-bar': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-pie': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-radar': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-doughnut': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-polar': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-scatter': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-mixed': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-stacked-bar': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-horizontal-bar': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-area': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-bubble': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-safras': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-financeiro': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-estoque': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',
    'chart-producao-animal': '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>',

    // ── Tables ──
    'table-data':
      '<div class="t-full flex flex-col"><div class="flex items-center justify-between px-2 py-1 border-b border-slate-200 dark:border-slate-700 shrink-0"><span class="text-xs font-medium text-slate-500">Safras</span><div class="flex gap-1"><button onclick="exportTableCSV(\'safras\')" class="px-2 py-0.5 text-[9px] bg-slate-100 dark:bg-slate-800 rounded hover:bg-slate-200 dark:hover:bg-slate-700" title="Exportar CSV"><i class="bi bi-file-earmark-spreadsheet mr-1"></i>CSV</button><button onclick="exportTableExcel(\'safras\')" class="px-2 py-0.5 text-[9px] bg-emerald-100 dark:bg-emerald-900/30 rounded hover:bg-emerald-200 dark:hover:bg-emerald-800/30" title="Exportar Excel"><i class="bi bi-file-earmark-excel mr-1"></i>Excel</button></div></div><div class="overflow-auto flex-1 text-xs">' +
      (safras.items && safras.items.length
        ? '<table class="w-full"><thead><tr class="border-b border-slate-200 dark:border-slate-700"><th class="text-left py-1 text-slate-400 font-medium px-2">Cultura</th><th class="text-right py-1 text-slate-400 font-medium">Área</th><th class="text-right py-1 text-slate-400 font-medium">Produção</th><th class="text-right py-1 text-slate-400 font-medium">Prod.</th></tr></thead><tbody>' +
          safras.items
            .slice(0, 15)
            .map(function (s) {
              return (
                '<tr><td class="py-0.5 px-2">' +
                (s.cultura || '') +
                '</td><td class="text-right py-0.5">' +
                fmt(s.area, 1) +
                ' ha</td><td class="text-right py-0.5">' +
                fmt(s.producao, 1) +
                '</td><td class="text-right py-0.5 font-semibold">' +
                fmt(s.produtividade, 1) +
                '</td></tr>'
              );
            })
            .join('') +
          '</tbody></table>'
        : '<p class="text-xs text-slate-400 p-2">Nenhum dado</p>') +
      '</div></div>',
    'list-tasks':
      '<ul class="text-xs space-y-1 p-2"><li class="text-slate-400">Use o módulo de tarefas</li></ul>',
    'table-planilha':
      '<div class="p-1 text-xs overflow-auto h-full">' +
      (fin.mensal && fin.mensal.length
        ? '<table class="w-full"><thead><tr class="border-b text-[9px]"><th class="text-left py-1">Mês</th><th class="text-right py-1">Receita</th><th class="text-right py-1">Despesa</th></tr></thead><tbody>' +
          fin.mensal
            .map(function (f) {
              var m = String(f.data__month || '');
              return (
                '<tr><td class="py-0.5">' +
                (m || '—') +
                '</td><td class="text-right py-0.5 text-theme-ok">' +
                fmtMoney(f.receitas) +
                '</td><td class="text-right py-0.5 text-theme-error">' +
                fmtMoney(f.despesas) +
                '</td></tr>'
              );
            })
            .join('') +
          '</tbody></table></div>'
        : '<p class="text-xs text-slate-400">Nenhum dado financeiro</p></div>'),
    'list-agenda':
      '<ul class="text-xs space-y-1.5 p-2">' +
      (safras.items && safras.items.length
        ? safras.items
            .slice(0, 10)
            .map(function (s) {
              return (
                '<li class="flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-theme-accent"></span><span class="text-slate-700 dark:text-slate-300">' +
                s.cultura +
                ' — ' +
                s.ano +
                '</span></li>'
              );
            })
            .join('')
        : '<li class="text-slate-400">Nenhum evento</li>') +
      '</ul>',
    'calendar-widget':
      '<div class="grid grid-cols-7 gap-0.5 text-xs p-1">' +
      (d && d.dias && d.dias.length
        ? d.dias
            .map(function (di) {
              return (
                '<div class="' +
                (di.destaque ? 'bg-theme-accent text-white rounded' : '') +
                ' p-1 text-center">' +
                di.num +
                '</div>'
              );
            })
            .join('')
        : Array.from({ length: 31 }, function (_, i) {
            return '<div class="p-1 text-center">' + (i + 1) + '</div>';
          }).join('')) +
      '</div>',
    /* `maq.manutencao_pendente || 0` afirmava '0 manutencoes
     * pendentes' quando o campo nao existe. Este widget ja sabia
     * mostrar 'sem dado' na linha de baixo - a de cima e que
     * mentia. Agora as duas seguem a mesma regra. */
    'alerts-widget': (function () {
      var pend = maq && maq.manutencao_pendente != null ? maq.manutencao_pendente : null;
      /* Mesmo principio dos Alertas: o simbolo diz que e' um aviso, o circulo
       * vermelho de 32px repetia-o do tamanho do widget. O
       * `items-center` fica no contentor para o icone ficar a
       * meio do bloco de texto, agora que nao ha mais uma caixa
       * a centrar. */
      return (
        '<div class="flex items-center gap-2 text-xs p-3"><i class="bi bi-exclamation-circle text-theme-error text-[15px] leading-none shrink-0"></i><div class="min-w-0"><div class="font-medium">' +
        (pend != null
          ? pend + ' manutenções pendentes'
          : semDados('Manutenções', 'Registe maquinários com data de manutenção.')) +
        '</div><div class="text-slate-400">' +
        (d && d.alertas != null ? d.alertas + ' alertas' : '-') +
        '</div></div></div>'
      );
    })(),
    'sensor-mini':
      '<div class="text-xs p-2"><div class="flex justify-between"><span>Umidade</span><span class="font-bold">' +
      (d && d.umidade != null
        ? d.umidade + '%'
        : semDados('Umidade', 'Conecte sensores IoT ou aguarde leituras da estação.')) +
      '</span></div><div class="w-full bg-slate-200 rounded h-1 mt-1"><div class="bg-theme-accent h-1 rounded" style="width: ' +
      (d && d.umidade != null ? d.umidade : 50) +
      '%"></div></div></div>',

    // ── New Tables ──
    'table-financeiro':
      '<div class="overflow-auto h-full text-xs">' +
      (fin.lancamentos && fin.lancamentos.length
        ? '<table class="w-full"><thead><tr class="border-b text-[10px]"><th class="text-left py-1 px-1 text-slate-400 font-medium">Data</th><th class="text-left py-1 text-slate-400 font-medium">Descrição</th><th class="text-right py-1 text-slate-400 font-medium">Valor</th><th class="text-center py-1 text-slate-400 font-medium">Status</th></tr></thead><tbody>' +
          fin.lancamentos
            .slice(0, 20)
            .map(function (l) {
              return (
                '<tr class="border-b border-slate-100 dark:border-slate-800"><td class="py-0.5 px-1 whitespace-nowrap">' +
                (l.data || '') +
                '</td><td class="py-0.5 max-w-[120px] truncate">' +
                (l.descricao || l.categoria) +
                '</td><td class="py-0.5 text-right font-medium ' +
                (l.tipo === 'RECEITA' ? 'text-theme-ok' : 'text-theme-error') +
                '">' +
                fmtMoney(l.valor) +
                '</td><td class="py-0.5 text-center"><span class="inline-block w-1.5 h-1.5 rounded-full ' +
                (l.pago ? 'bg-theme-ok' : 'bg-theme-alert') +
                '"></span></td></tr>'
              );
            })
            .join('') +
          '</tbody></table></div>'
        : '<p class="text-xs text-slate-400 p-2">Nenhum lançamento</p>'),

    'table-estoque':
      '<div class="overflow-auto h-full text-xs">' +
      (est.items && est.items.length
        ? '<table class="w-full"><thead><tr class="border-b text-[10px]"><th class="text-left py-1 px-1 text-slate-400 font-medium">Item</th><th class="text-left py-1 text-slate-400 font-medium">Cat.</th><th class="text-right py-1 text-slate-400 font-medium">Qtd</th><th class="text-right py-1 text-slate-400 font-medium">Validade</th></tr></thead><tbody>' +
          est.items
            .slice(0, 20)
            .map(function (e) {
              return (
                '<tr><td class="py-0.5 px-1">' +
                e.nome +
                '</td><td class="py-0.5 text-slate-500">' +
                e.categoria +
                '</td><td class="py-0.5 text-right">' +
                fmt(e.quantidade, 1) +
                ' ' +
                e.unidade +
                '</td><td class="py-0.5 text-right text-slate-400">' +
                (e.validade || '—') +
                '</td></tr>'
              );
            })
            .join('') +
          '</tbody></table></div>'
        : '<p class="text-xs text-slate-400 p-2">Estoque vazio</p>'),

    // ── Tabela por categoria financeira (substitui a demo Power BI) ──
    'table-vendas-regiao': (function () {
      var categorias = (fin && fin.por_categoria ? fin.por_categoria : [])
        .filter(function (c) {
          return c && c.categoria && Number(c.total) > 0;
        })
        .sort(function (a, b) {
          return Number(b.total) - Number(a.total);
        });
      if (!categorias.length) {
        return (
          '<div class="h-full flex items-center justify-center p-4 text-center text-xs text-slate-400">' +
          semDados('Categorias', 'Cadastre lançamentos financeiros com categoria.') +
          '</div>'
        );
      }
      var maior = Number(categorias[0].total) || 1;
      var html =
        '<div class="p-4 h-full flex flex-col min-h-0">' +
        '<div class="flex items-center gap-4 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-3 pb-2 border-b border-slate-200 dark:border-[#1e2a26]">' +
        '<div class="w-2/5">Categoria</div>' +
        '<div class="w-1/3 text-right">Valor</div>' +
        '<div class="w-1/4"></div></div>' +
        '<div class="flex-1 overflow-y-auto scrollbar-none space-y-3 min-h-0">';
      categorias.forEach(function (c) {
        var pct = Math.max(0, Math.min(100, (Number(c.total) / maior) * 100));
        html +=
          '<div class="flex items-center gap-4 text-xs">' +
          '<div class="w-2/5 font-medium text-slate-700 dark:text-slate-300 truncate" title="' +
          String(c.categoria).replace(/"/g, '&quot;') +
          '">' +
          c.categoria +
          '</div>' +
          '<div class="w-1/3 text-slate-500 text-right truncate">' +
          fmtMoney(c.total) +
          '</div>' +
          '<div class="w-1/4 flex items-center shrink-0"><div class="h-1.5 w-full bg-slate-100 dark:bg-slate-800/50 rounded-full overflow-hidden">' +
          '<div class="h-full bg-theme-accent rounded-full" style="width:' +
          pct.toFixed(1) +
          '%"></div></div></div></div>';
      });
      return html + '</div></div>';
    })(),

    'table-safras':
      '<div class="overflow-auto h-full text-xs">' +
      (safras.items && safras.items.length
        ? '<table class="w-full"><thead><tr class="border-b text-[10px]"><th class="text-left py-1 px-1 text-slate-400 font-medium">Cultura</th><th class="text-left py-1 text-slate-400 font-medium">Talhão</th><th class="text-center py-1 text-slate-400 font-medium">Ano</th><th class="text-right py-1 text-slate-400 font-medium">Área</th><th class="text-right py-1 text-slate-400 font-medium">Prod.</th><th class="text-right py-1 text-slate-400 font-medium">Receita</th></tr></thead><tbody>' +
          safras.items
            .slice(0, 20)
            .map(function (s) {
              return (
                '<tr><td class="py-0.5 px-1">' +
                s.cultura +
                '</td><td class="py-0.5 text-slate-500">' +
                s.talhao +
                '</td><td class="py-0.5 text-center">' +
                s.ano +
                '</td><td class="py-0.5 text-right">' +
                fmt(s.area, 1) +
                ' ha</td><td class="py-0.5 text-right font-medium">' +
                fmt(s.produtividade, 1) +
                '</td><td class="py-0.5 text-right text-theme-ok">' +
                fmtMoney(s.receita) +
                '</td></tr>'
              );
            })
            .join('') +
          '</tbody></table></div>'
        : '<p class="text-xs text-slate-400 p-2">Nenhuma safra</p>'),

    // ── New Lists ──
    'list-manutencao':
      '<div class="text-xs p-1 overflow-auto h-full">' +
      (maq.items && maq.items.length
        ? maq.items
            .filter(function (m) {
              return m.proxima_manutencao || !m.ativo;
            })
            .slice(0, 15)
            .map(function (m) {
              return (
                '<div class="flex items-center gap-2 py-1 border-b border-slate-100 dark:border-slate-800 last:border-0"><div class="w-6 h-6 rounded-full ' +
                (m.ativo ? 'bg-amber-100 dark:bg-amber-900/30' : 'bg-slate-100 dark:bg-slate-800') +
                ' flex items-center justify-center"><i class="bi bi-tools ' +
                (m.ativo ? 'text-amber-500' : 'text-slate-400') +
                ' text-[10px]"></i></div><div class="flex-1 min-w-0"><div class="font-medium truncate">' +
                m.nome +
                '</div><div class="text-slate-400 truncate">' +
                (m.proxima_manutencao ? 'Próx: ' + m.proxima_manutencao : 'Inativo') +
                '</div></div></div>'
              );
            })
            .join('')
        : '<p class="text-slate-400 py-2 text-center">Nenhum maquinário</p>') +
      '</div>',

    'list-colmeias':
      '<div class="text-xs p-1 overflow-auto h-full">' +
      (apiario.colmeias && apiario.colmeias.length
        ? apiario.colmeias
            .map(function (c) {
              return (
                '<div class="flex items-center gap-2 py-1 border-b border-slate-100 dark:border-slate-800 last:border-0"><div class="w-6 h-6 rounded-full ' +
                (c.ativa
                  ? 'bg-emerald-100 dark:bg-emerald-900/30'
                  : 'bg-slate-100 dark:bg-slate-800') +
                ' flex items-center justify-center"><i class="bi bi-flower1 ' +
                (c.ativa ? 'text-emerald-500' : 'text-slate-400') +
                ' text-[10px]"></i></div><div class="flex-1"><div class="font-medium">' +
                c.identificacao +
                '</div><div class="text-slate-400">' +
                (c.tipo_abelha || '—') +
                '</div></div><span class="w-1.5 h-1.5 rounded-full ' +
                (c.ativa ? 'bg-emerald-500' : 'bg-slate-300') +
                '"></span></div>'
              );
            })
            .join('')
        : '<p class="text-slate-400 py-2 text-center">Nenhuma colmeia</p>') +
      '</div>',

    // ── Summary card ──
    /* O resumo repetia `|| 0` em cinco celulas. '0 safras' e
     * verdade quando nao ha safras; 'safras: 0' quando o campo
     * nao veio tambem parece verdade, e nao e'. Aqui cada
     * celula diz 'sem dado' quando nao sabe, e mostra o zero
     * quando zero e mesmo a resposta. */
    'widget-resumo': (function () {
      function cel(titulo, valor, sufixo) {
        return (
          '<div class="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-2 text-center">' +
          '<div class="text-lg font-bold text-theme-accent">' +
          (valor == null ? semDados(titulo) : valor + (sufixo || '')) +
          '</div><div class="text-slate-400">' +
          titulo +
          '</div></div>'
        );
      }
      var area =
        talhoes.area_total != null
          ? parseFloat(talhoes.area_total)
          : prop.area_total != null
            ? parseFloat(prop.area_total)
            : null;
      if (area != null && !area && prop.area_total == null) area = null;
      var saldo = fin.saldo != null ? fin.saldo : d && d.fluxo_caixa != null ? d.fluxo_caixa : null;
      return (
        '<div class="grid grid-cols-2 gap-2 p-2 text-xs h-full">' +
        cel('Safras', safras.total_safras != null ? safras.total_safras : null) +
        cel('Ha', area != null ? fmt(area, 1) : null) +
        cel('Animais', anim.total_cabecas != null ? fmt(anim.total_cabecas, 0) : null) +
        cel('Equipe', funcs.ativos != null ? funcs.ativos : null) +
        '<div class="col-span-2 bg-slate-50 dark:bg-slate-800/50 rounded-lg p-2 text-center">' +
        '<div class="text-sm font-bold ' +
        (saldo == null ? 'text-slate-400' : saldo >= 0 ? 'text-theme-ok' : 'text-theme-error') +
        '">' +
        (saldo == null ? semDados('Saldo') : fmtMoney(saldo)) +
        '</div><div class="text-slate-400">Saldo Financeiro</div></div></div>'
      );
    })(),

    // ── Map widget ──
    'widget-mapa': '<div id="map-' + id + '" class="w-full h-full rounded-lg"></div>',

    // ── Gantt/Timeline widget ──
    'widget-gantt':
      '<div class="p-2 overflow-auto h-full"><div class="text-xs font-medium text-slate-500 mb-2">Cronograma Plantio/Colheita</div><div id="gantt-' +
      id +
      '" class="w-full h-full"></div></div>',

    // ── Clima Real widget ──
    'widget-clima':
      '<div class="p-3 text-center h-full"><div id="clima-' +
      id +
      '"><div class="text-sm text-slate-500">Carregando clima...</div></div></div>',

    // ── IoT Sensors widget ──
    'widget-iot':
      '<div class="p-2 overflow-auto h-full"><div class="text-xs font-medium text-slate-500 mb-2">Leituras Recentes</div><div id="iot-' +
      id +
      '"></div></div>',

    // ── Comparativo Culturas ──
    'widget-comparativo':
      '<div class="p-2 h-full"><div class="flex gap-2 mb-2"><select id="cmp-cultura1-' +
      id +
      '" class="flex-1 text-xs p-1 border rounded bg-white dark:bg-slate-800"></select><select id="cmp-cultura2-' +
      id +
      '" class="flex-1 text-xs p-1 border rounded bg-white dark:bg-slate-800"></select></div><canvas id="chart-' +
      id +
      '" class="w-full h-full"></canvas></div>',
  };

  // Culture widgets (skip market widgets, e.g. cultura-arroz_mercado_...)
  if (id.indexOf('cultura-') === 0 && id.indexOf('_mercado_') < 0) {
    var ctype = WIDGET_TYPES[id];
    var cname = id.replace('cultura-', '');
    var cdata = safras.items
      ? safras.items.find(function (s) {
          return s.cultura && s.cultura.toLowerCase().indexOf(cname) >= 0;
        })
      : null;
    var val = cdata
      ? fmt(cdata.producao, 1) + ' sc'
      : semDados('Produção', 'Cadastre safras desta cultura para exibir a produção total.');
    var icon = ctype ? ctype.icon : 'bi-flower1';
    var title = ctype
      ? ctype.title
      : cname.charAt(0).toUpperCase() + cname.slice(1).replace(/-/g, ' ');
    var desc = ctype ? ctype.desc || 'Em monitoramento' : 'Em monitoramento';
    return (
      '<div class="flex flex-col h-full overflow-hidden" style="background-image:linear-gradient(to bottom, transparent, var(--pal-accent-fill, rgba(15,157,110,0.06)))"><div class="flex items-center gap-2 px-2.5 py-2 border-b border-slate-100 dark:border-slate-700/60 bg-white/40 dark:bg-black/10 shrink-0"><div class="w-6 h-6 flex items-center justify-center rounded-md bg-theme-accent-soft text-theme-accent shadow-sm shrink-0"><i class="bi ' +
      icon +
      ' text-[10px]"></i></div><div class="flex-1 min-w-0"><div class="text-[11px] font-semibold text-slate-800 dark:text-slate-100 leading-tight truncate">' +
      title +
      '</div><div class="text-[8px] text-slate-400 dark:text-slate-500 truncate">' +
      desc +
      '</div></div><span class="text-[9px] font-mono font-bold text-theme-accent bg-theme-accent-soft px-1.5 py-0.5 rounded-md shrink-0">' +
      val +
      '</span></div><div class="flex-1 min-h-0 p-0.5"><canvas id="chart-' +
      id +
      '" class="w-full h-full"></canvas></div></div>'
    );
  }

  // Market widget (saved from addWidgetFromMiniCard)
  var wCfg = window.widgets && window.widgets[id];
  if (wCfg && (wCfg.metricKey || id.indexOf('_mercado_') >= 0)) {
    return getMarketWidgetContent(id, wCfg);
  }

  // Multi-series production widget
  if (wCfg && wCfg.selectedRecords && wCfg.selectedRecords.length > 0) {
    return getProductionWidgetContent(id, wCfg);
  }

  // Fallback para QUALQUER KPI não mapeado explicitamente.
  // Só entra aqui se o id realmente não existir no mapa `content`.
  // Antes, qualquer id começando com 'kpi-' caía neste bloco e devolvia
  // sempre "Sem dados", tornando o mapa `content` inacessível para todos
  // os KPIs (ROI, Custo/Ha, Caixa, Área, Manutenções, Equipe, Safras...).
  if (id && id.startsWith('kpi-') && !content[id]) {
    var wTitle = 'KPI';
    if (typeof WIDGET_TYPES !== 'undefined' && WIDGET_TYPES[id]) wTitle = WIDGET_TYPES[id].title;
    else wTitle = id.replace('kpi-', '').replace(/-/g, ' ').toUpperCase();
    // NÃO É '0'.
    //
    // `'0'` com o subtítulo "Sem registros" diz duas coisas que
    // se contradizem: que se mediu zero, e que não se mediu
    // nada. A segunda é a verdade. E é a que importa — "0
    // alertas" convence a pessoa de que está tudo bem;
    // "sem registos" obriga-a a perguntar porque é que o
    // sensor não falou.
    //
    // É a mesma classe do `umidade: 50`: um número inventado
    // com aspecto de medição. Um KPI sem dado mostra a
    // ausência, e diz que não tem dado.
    return window.buildModernKpiHtml(wTitle, '—', 'Sem dado', '', null);
  }

  return (
    content[id] ||
    '<div class="flex items-center justify-center h-full text-xs text-slate-400 p-4"><i class="bi bi-grid-3x3-gap text-lg mr-2"></i>' +
      (typeof WIDGET_TYPES !== 'undefined' && WIDGET_TYPES[id]
        ? WIDGET_TYPES[id].title
        : 'Widget') +
      '</div>'
  );
};

function getProductionWidgetContent(id, cfg) {
  var selectedIds = cfg.selectedRecords || [];
  var metricKey = cfg.metricKey || '';
  var records = [];
  if (window.ProductionRegistry) {
    selectedIds.forEach(function (rid) {
      var r = ProductionRegistry.getById(rid);
      if (r) records.push(r);
    });
  }
  var widgetType = cfg.widgetType || 'grafico';
  var chartSubtype = cfg.chartSubtype || 'line';

  if (records.length === 0)
    return '<div class="flex items-center justify-center h-full text-[8px] text-slate-400">Sem dados</div>';

  // ── Compute aggregation ──
  var labels = [],
    data = [];

  if (metricKey === 'detalhamento') {
    // Table view — show all records
    var rows =
      '<tr><td class="text-[7px] text-slate-500 px-1.5 py-0.5 font-semibold border border-slate-200 dark:border-slate-700">Registro</td><td class="text-[7px] text-slate-500 px-1.5 py-0.5 font-semibold border border-slate-200 dark:border-slate-700">Local</td><td class="text-[7px] text-slate-500 px-1.5 py-0.5 font-semibold border border-slate-200 dark:border-slate-700">Data</td><td class="text-[7px] text-slate-500 px-1.5 py-0.5 font-semibold border border-slate-200 dark:border-slate-700 text-right">Qtd</td></tr>';
    records.forEach(function (r) {
      rows +=
        '<tr><td class="text-[7px] text-slate-700 px-1.5 py-0.5 border border-slate-200 dark:border-slate-700">' +
        (r.name || '—') +
        '</td><td class="text-[7px] text-slate-500 px-1.5 py-0.5 border border-slate-200 dark:border-slate-700">' +
        (r.location || '—') +
        '</td><td class="text-[7px] text-slate-500 px-1.5 py-0.5 border border-slate-200 dark:border-slate-700">' +
        (r.plantingDate || '—') +
        '</td><td class="text-[7px] font-semibold text-slate-700 dark:text-slate-200 px-1.5 py-0.5 border border-slate-200 dark:border-slate-700 text-right">' +
        (r.quantity || 0) +
        '</td></tr>';
    });
    return (
      '<div class="overflow-auto h-full"><table class="w-full border-collapse rounded-lg overflow-hidden"><tbody>' +
      rows +
      '</tbody></table></div>'
    );
  }

  if (metricKey === 'distribuicao') {
    var total = records.reduce(function (a, r) {
      return a + (r.quantity || 0);
    }, 0);
    records.forEach(function (r) {
      labels.push(r.name || r.location || '—');
      data.push(total > 0 ? Math.round(((r.quantity || 0) / total) * 10000) / 100 : 0);
    });
  } else if (
    metricKey === 'taxa_lotacao' ||
    metricKey === 'conversao_alimentar' ||
    metricKey === 'rendimento'
  ) {
    var locs = {},
      totalQty = 0;
    records.forEach(function (r) {
      if (r.location) locs[r.location] = (locs[r.location] || 0) + 1;
      totalQty += r.quantity || 0;
    });
    var num = Object.keys(locs).length || 1;
    labels = [
      metricKey === 'taxa_lotacao'
        ? 'Taxa'
        : metricKey === 'conversao_alimentar'
          ? 'Conversão'
          : 'Rendimento',
    ];
    data = [Math.round((totalQty / num) * 100) / 100];
  } else if (metricKey.indexOf('media_') === 0) {
    var groups = {};
    records.forEach(function (r) {
      var loc = r.location || 'Sem local';
      if (!groups[loc]) groups[loc] = { sum: 0, count: 0 };
      groups[loc].sum += r.quantity || 0;
      groups[loc].count++;
    });
    Object.keys(groups).forEach(function (loc) {
      labels.push(loc);
      data.push(Math.round((groups[loc].sum / groups[loc].count) * 100) / 100);
    });
  } else if (metricKey === 'serie_temporal') {
    var byDate = {};
    records.forEach(function (r) {
      var d = r.plantingDate || '—';
      if (!byDate[d]) byDate[d] = 0;
      byDate[d] += r.quantity || 0;
    });
    Object.keys(byDate)
      .sort()
      .forEach(function (d) {
        labels.push(d);
        data.push(Math.round(byDate[d] * 100) / 100);
      });
  } else if (metricKey === 'comparativo') {
    records.forEach(function (r) {
      labels.push(r.name || r.location || '—');
      data.push(r.quantity || 0);
    });
  } else {
    // *_total types — sum
    var sum = records.reduce(function (a, r) {
      return a + (r.quantity || 0);
    }, 0);
    labels = ['Total'];
    data = [Math.round(sum * 100) / 100];
  }

  if (widgetType === 'tabela') {
    if (chartSubtype === 'anos' || chartSubtype === 'fatores') {
      // Extract multidimensional data
      var metricsList = ['Produção', 'Área', 'Produtividade', 'Fertilizantes'];
      var allYears = [];
      var allFactors = [];
      var db = {}; // db[year][factor][metric]

      records.forEach(function (r) {
        var y = r.plantingDate ? r.plantingDate.slice(0, 4) : 'N/A';
        var f = r.location || r.name || 'Geral';
        if (allYears.indexOf(y) < 0) allYears.push(y);
        if (allFactors.indexOf(f) < 0) allFactors.push(f);

        if (!db[y]) db[y] = {};
        if (!db[y][f]) db[y][f] = {};

        db[y][f]['Produção'] = (db[y][f]['Produção'] || 0) + (r.quantity || 0);
        if (r.fields) {
          if (r.fields.area)
            db[y][f]['Área'] = (db[y][f]['Área'] || 0) + (parseFloat(r.fields.area) || 0);
          if (r.fields.produtividade)
            db[y][f]['Produtividade'] =
              (db[y][f]['Produtividade'] || 0) + (parseFloat(r.fields.produtividade) || 0);
          if (r.fields.fertilizante)
            db[y][f]['Fertilizantes'] =
              (db[y][f]['Fertilizantes'] || 0) + (parseFloat(r.fields.fertilizante) || 0);
        }
      });

      allYears.sort();
      allFactors.sort();

      var isAnos = chartSubtype === 'anos';
      var tabs = isAnos ? allYears : allFactors;
      var rows = isAnos ? allFactors : allYears;
      var rowLabel = isAnos ? 'Fator / Talhão' : 'Ano / Período';

      if (tabs.length === 0)
        return '<div class="flex items-center justify-center h-full text-[8px] text-slate-400">Sem dados p/ abas</div>';

      var html = '<div id="widget-tabs-' + id + '" class="flex flex-col h-full overflow-hidden">';

      // Header tabs
      html +=
        '<div class="flex gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-t-lg overflow-x-auto scrollbar-none shrink-0">';
      tabs.forEach(function (t, i) {
        var active = i === 0;
        var btnCls = active
          ? 'bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm font-semibold'
          : 'text-slate-500 hover:text-slate-700';
        html +=
          '<button class="widget-tab-btn px-3 py-1 rounded text-[8px] whitespace-nowrap transition-colors ' +
          btnCls +
          '" data-tab="tab-' +
          i +
          '" onclick="if(window.switchWidgetInnerTab) window.switchWidgetInnerTab(\'' +
          id +
          "', 'tab-" +
          i +
          '\')">' +
          t +
          '</button>';
      });
      html += '</div>';

      // Content
      html += '<div class="relative flex-1 bg-white dark:bg-transparent overflow-hidden">';
      tabs.forEach(function (t, i) {
        html +=
          '<div class="widget-tab-content absolute inset-0 overflow-auto ' +
          (i === 0 ? '' : 'hidden') +
          '" data-tab="tab-' +
          i +
          '">';
        html += '<table class="w-full text-[7px] text-left">';
        html +=
          '<thead><tr class="border-b border-slate-200 dark:border-slate-700/50 text-slate-400"><th class="px-2 py-1.5 font-medium">' +
          rowLabel +
          '</th>';
        metricsList.forEach(function (m) {
          html += '<th class="px-2 py-1.5 font-medium text-right">' + m + '</th>';
        });
        html += '</tr></thead><tbody>';

        rows.forEach(function (row) {
          var y = isAnos ? t : row;
          var f = isAnos ? row : t;
          var rowData = db[y] && db[y][f] ? db[y][f] : null;

          html +=
            '<tr class="border-b border-slate-100 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">';
          html +=
            '<td class="px-2 py-1.5 font-medium text-slate-600 dark:text-slate-300">' +
            row +
            '</td>';
          metricsList.forEach(function (m) {
            var val = rowData && rowData[m] ? rowData[m] : 0;
            html +=
              '<td class="px-2 py-1.5 text-right font-mono text-emerald-600 dark:text-emerald-400">' +
              (val ? val.toLocaleString('pt-BR') : '-') +
              '</td>';
          });
          html += '</tr>';
        });

        html += '</tbody></table></div>';
      });
      html += '</div></div>';
      return html;
    }

    // Variantes normais (lista)
    var rows2 = '';
    labels.forEach(function (l, i) {
      rows2 +=
        '<tr><td class="text-[7px] text-slate-500 px-1.5 py-0.5 border border-slate-200 dark:border-slate-700">' +
        l +
        '</td><td class="text-[7px] font-semibold text-slate-700 dark:text-slate-200 px-1.5 py-0.5 border border-slate-200 dark:border-slate-700 text-right">' +
        (typeof data[i] === 'number' ? data[i].toLocaleString('pt-BR') : data[i]) +
        '</td></tr>';
    });
    return (
      '<div class="overflow-auto h-full"><table class="w-full border-collapse rounded-lg overflow-hidden"><tbody>' +
      rows2 +
      '</tbody></table></div>'
    );
  }

  if (widgetType === 'kpi') {
    var kpiVal =
      data.length > 0
        ? typeof data[data.length - 1] === 'number'
          ? data[data.length - 1].toLocaleString('pt-BR')
          : data[data.length - 1]
        : '0';
    var kpiTitle = metricKey.replace(/_/g, ' ');
    kpiTitle = kpiTitle.charAt(0).toUpperCase() + kpiTitle.slice(1);
    if (window.buildModernKpiHtml) {
      return window.buildModernKpiHtml(kpiTitle, kpiVal, 'Dados de produção', '', true);
    }
    return (
      '<div class="flex flex-col justify-center h-full p-4"><span class="text-xs text-slate-500 uppercase">' +
      kpiTitle +
      '</span><div class="text-2xl font-bold text-slate-800 dark:text-white">' +
      kpiVal +
      '</div></div>'
    );
  }

  if (widgetType === 'lista') {
    var items = '';
    labels.forEach(function (l, i) {
      items +=
        '<div class="flex justify-between text-[7px] px-2 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/30"><span class="text-slate-500">' +
        l +
        '</span><span class="font-semibold text-slate-700 dark:text-slate-200">' +
        (typeof data[i] === 'number' ? data[i].toLocaleString('pt-BR') : data[i]) +
        '</span></div>';
    });
    return '<div class="overflow-y-auto h-full scrollbar-none space-y-1">' + items + '</div>';
  }

  return '<canvas id="chart-' + id + '" class="w-full h-full"></canvas>';
}

function getMarketWidgetContent(id, cfg) {
  var widgetType = cfg.widgetType || 'grafico';
  var metricKey = cfg.metricKey || '';
  var title = cfg.title || metricKey;
  var source = cfg.source || 'agrodoc';

  var hist = cfg._cardHistory || [];
  var myHist = cfg._cardMyHistory || [];
  var lastMetric = cfg._lastMetric || null;

  var lastVal = '';
  if (lastMetric && lastMetric.value) {
    lastVal = lastMetric.value + (lastMetric.unit ? ' ' + lastMetric.unit : '');
  } else if (hist.length > 0) {
    var last = hist[hist.length - 1];
    lastVal =
      (typeof last.valor === 'number' ? last.valor.toLocaleString('pt-BR') : last.valor) +
      ' (' +
      last.ano +
      ')';
  }

  var w = window.widgetDataCache || {};
  var safras = w.safras || {};
  var cultureRecords = [];

  // Culture name from widget id (e.g. cultura-arroz_mercado_... -> arroz)
  var cultureKey = '';
  var idBase = String(id).split('_mercado_')[0] || String(id).split('_')[0] || '';
  if (idBase.indexOf('cultura-') === 0) {
    cultureKey = idBase.replace('cultura-', '').replace(/-/g, ' ').toLowerCase().trim();
  }

  // Prettier culture display name (título do config, ex.: "Café")
  var cultureTitle = '';
  if (idBase) {
    var flatC = typeof getFlatCultureList === 'function' ? getFlatCultureList() : [];
    for (var fi = 0; fi < flatC.length; fi++) {
      if (flatC[fi].id === idBase) {
        cultureTitle = flatC[fi].title;
        break;
      }
    }
    if (!cultureTitle && cultureKey) {
      cultureTitle = cultureKey.charAt(0).toUpperCase() + cultureKey.slice(1);
    }
  }

  // Widget title: "Produção Total" -> "Produção Total de Café"
  if (cultureTitle && title && title.toLowerCase().indexOf(cultureTitle.toLowerCase()) < 0) {
    title = title + ' de ' + cultureTitle;
  }
  var titlePlain = title;

  function safrasByCulture(items) {
    var all = items || [];
    if (!cultureKey) return all;
    var filtered = all.filter(function (s) {
      return s && s.cultura && String(s.cultura).toLowerCase().indexOf(cultureKey) >= 0;
    });
    return filtered.length > 0 ? filtered : all;
  }

  function metricFromSafra(s) {
    if (metricKey === 'area_plantada') return s.area || 0;
    if (metricKey === 'producao_total') return s.producao || 0;
    if (metricKey === 'valor_saca' || metricKey === 'sacas_talhao') return s.produtividade || 0;
    if (metricKey === 'receita_estimada') return s.receita || 0;
    return s.produtividade || s.producao || 0;
  }

  if (window.ProductionRegistry) {
    var cid = id.split('_')[0];
    cultureRecords = ProductionRegistry.getByCulture(cid);
  }

  var safrasFallback = safrasByCulture(safras.items);
  if (!lastVal && safrasFallback.length > 0) {
    var lastS = safrasFallback[safrasFallback.length - 1];
    lastVal =
      metricFromSafra(lastS).toLocaleString('pt-BR') +
      ' (' +
      (lastS.ano || lastS.cultura || '—') +
      ')';
  }

  if (widgetType === 'tabela') {
    var rows = '';
    if (hist.length > 0 || myHist.length > 0) {
      hist.forEach(function (h) {
        rows +=
          '<tr><td class="text-[7px] text-slate-500 px-1">' +
          h.ano +
          '</td><td class="text-[7px] font-semibold text-slate-700 px-1 text-right">' +
          (typeof h.valor === 'number' ? h.valor.toLocaleString('pt-BR') : h.valor) +
          '</td></tr>';
      });
      myHist.forEach(function (h) {
        rows +=
          '<tr class="bg-blue-50 dark:bg-blue-900/20"><td class="text-[7px] text-slate-500 px-1">' +
          h.ano +
          ' (propriedade)</td><td class="text-[7px] font-semibold text-blue-700 dark:text-blue-300 px-1 text-right">' +
          (typeof h.valor === 'number' ? h.valor.toLocaleString('pt-BR') : h.valor) +
          '</td></tr>';
      });
    } else if (source === 'cultura' && cultureRecords.length > 0) {
      cultureRecords.slice(-10).forEach(function (r) {
        rows +=
          '<tr><td class="text-[7px] text-slate-500 px-1">' +
          (r.date || r.plantingDate || '—') +
          '</td><td class="text-[7px] font-semibold text-slate-700 px-1 text-right">' +
          (r.quantity || 0) +
          '</td></tr>';
      });
    } else if (safrasFallback.length > 0) {
      safrasFallback.slice(-10).forEach(function (s) {
        var val = metricFromSafra(s);
        rows +=
          '<tr><td class="text-[7px] text-slate-500 px-1">' +
          (s.ano || s.cultura || '—') +
          '</td><td class="text-[7px] font-semibold text-slate-700 px-1 text-right">' +
          val.toLocaleString('pt-BR') +
          '</td></tr>';
      });
    }
    return (
      '<div class="flex flex-col h-full"><div class="flex items-center justify-between px-1.5 py-0.5 border-b border-slate-200 dark:border-slate-700 shrink-0"><span class="text-[7px] font-medium text-slate-500 truncate">' +
      title +
      '</span><span class="text-[7px] font-semibold text-emerald-600">' +
      lastVal +
      '</span></div><div class="overflow-auto flex-1"><table class="w-full border-collapse"><tbody>' +
      (rows || '<tr><td class="text-[7px] text-slate-400 px-1">Sem dados</td></tr>') +
      '</tbody></table></div></div>'
    );
  }

  if (widgetType === 'kpi') {
    if (window.buildModernKpiHtml) {
      return window.buildModernKpiHtml(
        titlePlain,
        lastVal,
        source === 'ibge' ? 'Dados do IBGE' : 'Dados do Mercado',
        '',
        true
      );
    }
    return (
      '<div class="flex flex-col justify-center h-full p-4"><span class="text-xs text-slate-500 uppercase">' +
      titlePlain +
      '</span><div class="text-2xl font-bold text-slate-800 dark:text-white">' +
      lastVal +
      '</div></div>'
    );
  }

  if (widgetType === 'lista') {
    var items = '';
    if (hist.length > 0 || myHist.length > 0) {
      hist.forEach(function (h) {
        items +=
          '<div class="flex justify-between text-[7px] px-1"><span class="text-slate-500">' +
          h.ano +
          '</span><span class="font-semibold text-slate-700">' +
          (typeof h.valor === 'number' ? h.valor.toLocaleString('pt-BR') : h.valor) +
          '</span></div>';
      });
      myHist.forEach(function (h) {
        items +=
          '<div class="flex justify-between text-[7px] px-1 text-blue-700 dark:text-blue-300"><span class="text-slate-500">' +
          h.ano +
          ' (propriedade)</span><span class="font-semibold">' +
          (typeof h.valor === 'number' ? h.valor.toLocaleString('pt-BR') : h.valor) +
          '</span></div>';
      });
    } else if (source === 'cultura' && cultureRecords.length > 0) {
      cultureRecords.slice(-10).forEach(function (r) {
        items +=
          '<div class="flex justify-between text-[7px] px-1"><span class="text-slate-500">' +
          (r.date || r.plantingDate || '—') +
          '</span><span class="font-semibold text-slate-700">' +
          (r.quantity || 0) +
          '</span></div>';
      });
    } else if (safrasFallback.length > 0) {
      safrasFallback.slice(-10).forEach(function (s) {
        var val = metricFromSafra(s);
        items +=
          '<div class="flex justify-between text-[7px] px-1"><span class="text-slate-500">' +
          (s.ano || s.cultura || '—') +
          '</span><span class="font-semibold text-slate-700">' +
          val.toLocaleString('pt-BR') +
          '</span></div>';
      });
    }
    return (
      '<div class="flex flex-col h-full"><div class="flex items-center justify-between px-1.5 py-0.5 border-b border-slate-200 dark:border-slate-700 shrink-0"><span class="text-[7px] font-medium text-slate-500 truncate">' +
      title +
      '</span><span class="text-[7px] font-semibold text-emerald-600">' +
      lastVal +
      '</span></div><div class="overflow-y-auto flex-1 scrollbar-none">' +
      (items || '<div class="text-[7px] text-slate-400 px-1">Sem dados</div>') +
      '</div></div>'
    );
  }

  var titleBar =
    '<div class="flex items-center justify-between px-3 py-2 shrink-0 z-10"><span class="text-[10px] uppercase tracking-wider font-bold text-slate-600 dark:text-slate-300 truncate">' +
    title +
    '</span><span class="text-xs font-bold text-emerald-600 shrink-0 ml-2">' +
    lastVal +
    '</span></div>';
  return (
    '<div class="flex flex-col h-full overflow-hidden relative">' +
    titleBar +
    '<div class="flex-1 min-h-0"><canvas id="chart-' +
    id +
    '" class="w-full h-full"></canvas></div></div>'
  );
}

window.toggleWidgetEditMode = function () {
  widgetEditMode = !widgetEditMode;
  customMode = widgetEditMode;
  window.widgetEditMode = widgetEditMode;
  window.customMode = customMode;
  if (window.widgetbarState) window.widgetbarState.isCustomMode = widgetEditMode;
  document.querySelector('.matrix-container')?.classList.toggle('editing', widgetEditMode);
  var container = document.querySelector('.matrix-container');
  if (container) {
    container.querySelectorAll('.bento-block').forEach(function (el) {
      var wId = el.id.replace('widget-', '');
      if (widgetEditMode) {
        el.classList.add('widget-edit-mode');
        if (wId && !el.querySelector('.edit-mode-badge')) {
          addEditModeElements(el, wId);
        }
      } else {
        el.classList.remove('widget-edit-mode');
        removeEditModeElements(el);
      }
    });
    if (widgetEditMode) initWidgetDragging();
  }
  // Sincroniza widgetbar (gear→check + edit-mode-section + appbar)
  try {
    var wbBtn = document.getElementById('custom-mode-btn');
    var wbSection = document.getElementById('edit-mode-section');
    var wbAppbar = document.getElementById('dashboard-appbar');
    if (wbBtn) {
      wbBtn.classList.toggle('active', widgetEditMode);
      wbBtn.setAttribute('aria-pressed', widgetEditMode);
      if (wbBtn.querySelector('i'))
        wbBtn.querySelector('i').className = widgetEditMode ? 'bi bi-check2' : 'bi bi-gear';
      wbBtn.title = widgetEditMode ? 'Salvar Layout' : 'Modo Edição';
      wbBtn.setAttribute('aria-label', wbBtn.title);
    }
    if (wbSection) wbSection.classList.toggle('hidden', !widgetEditMode);
    if (wbAppbar) wbAppbar.classList.toggle('editing', widgetEditMode);
    document.querySelectorAll('.bento-block').forEach(function (el) {
      el.classList.toggle('widget-edit-mode', widgetEditMode);
    });
  } catch (e) {}
  if (!widgetEditMode) {
    document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
      el.classList.remove('widget-selected');
    });
    try {
      _selectedWidgetId = null;
    } catch (e) {}
    try {
      window._selectedWidgetId = null;
    } catch (e) {}
    try {
      if (typeof updateValuesList === 'function') updateValuesList(null);
    } catch (e) {}
  }
  // Atualiza indicador central
  try {
    if (typeof window.updateWidgetBarSelectionIndicator === 'function')
      window.updateWidgetBarSelectionIndicator();
  } catch (e) {}
};

window.editAddWidget = function (widgetId) {
  addWidget(widgetId);
};

window.abrirMarketplaceWidgets = function () {
  document.getElementById('marketplace-modal').classList.remove('hidden');
};

// Dashboard WidgetBar Functions

window.openSearchMenu = function () {
  var menu = document.getElementById('search-menu');
  if (menu) {
    menu.classList.add('open');
    setTimeout(function () {
      var innerInput = document.getElementById('search-menu-input');
      if (innerInput) innerInput.focus();
    }, 60);
  }
};

window.closeSearchMenuNow = function () {
  var menu = document.getElementById('search-menu');
  if (menu) menu.classList.remove('open');
};

window.toggleSearchMenu = function () {
  var menu = document.getElementById('search-menu');
  var wrap = document.querySelector('.widgetbar-search-wrap');
  if (menu) {
    var isOpening = !menu.classList.contains('open');
    menu.classList.toggle('open');
    document.body.classList.toggle('search-menu-open', isOpening);
    if (isOpening) {
      // Move para body para escapar de backdrop-filter/transform do parent que quebra fixed
      if (menu.parentElement !== document.body) {
        menu._originalParent = menu.parentElement;
        menu._originalNext = menu.nextSibling;
        document.body.appendChild(menu);
      }
      menu.style.setProperty('position', 'fixed', 'important');
      menu.style.setProperty('top', '50%', 'important');
      menu.style.setProperty('left', '50%', 'important');
      menu.style.setProperty('bottom', 'auto', 'important');
      menu.style.setProperty('right', 'auto', 'important');
      menu.style.setProperty('transform', 'translate(-50%, -50%) scale(0.97)', 'important');
      menu.style.setProperty('margin', '0', 'important');
      menu.style.setProperty('z-index', '1000', 'important');
      setTimeout(function () {
        menu.style.setProperty('transform', 'translate(-50%, -50%) scale(1)', 'important');
        var inp = document.getElementById('search-menu-input');
        if (inp) inp.focus();
      }, 10);
    } else {
      document.body.classList.remove('search-menu-open');
      menu.style.removeProperty('position');
      menu.style.removeProperty('top');
      menu.style.removeProperty('left');
      menu.style.removeProperty('bottom');
      menu.style.removeProperty('right');
      menu.style.removeProperty('transform');
      menu.style.removeProperty('margin');
      menu.style.removeProperty('z-index');
      // Devolve para o wrap original
      if (menu._originalParent) {
        try {
          if (menu._originalNext && menu._originalNext.parentElement === menu._originalParent) {
            menu._originalParent.insertBefore(menu, menu._originalNext);
          } else {
            menu._originalParent.appendChild(menu);
          }
        } catch (e) {}
        menu._originalParent = null;
        menu._originalNext = null;
      }
    }
  }
};
// Close search menu on outside click (centralizado)
document.addEventListener('click', function (e) {
  var menu = document.getElementById('search-menu');
  if (menu && menu.classList.contains('open')) {
    if (!menu.contains(e.target) && !e.target.closest('.widgetbar-search-btn')) {
      menu.classList.remove('open');
      document.body.classList.remove('search-menu-open');
      menu.style.removeProperty('position');
      menu.style.removeProperty('top');
      menu.style.removeProperty('left');
      menu.style.removeProperty('bottom');
      menu.style.removeProperty('right');
      menu.style.removeProperty('transform');
      menu.style.removeProperty('margin');
      menu.style.removeProperty('z-index');
      if (menu._originalParent) {
        try {
          if (menu._originalNext && menu._originalNext.parentElement === menu._originalParent) {
            menu._originalParent.insertBefore(menu, menu._originalNext);
          } else {
            menu._originalParent.appendChild(menu);
          }
        } catch (err) {}
        menu._originalParent = null;
        menu._originalNext = null;
      }
    }
  }
});
// Esc fecha ambos os menus centralizados
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    var sm = document.getElementById('search-menu');
    if (sm && sm.classList.contains('open')) {
      sm.classList.remove('open');
      document.body.classList.remove('search-menu-open');
      sm.style.removeProperty('position');
      sm.style.removeProperty('top');
      sm.style.removeProperty('left');
      sm.style.removeProperty('bottom');
      sm.style.removeProperty('right');
      sm.style.removeProperty('transform');
      sm.style.removeProperty('margin');
      sm.style.removeProperty('z-index');
      if (sm._originalParent) {
        try {
          if (sm._originalNext && sm._originalNext.parentElement === sm._originalParent) {
            sm._originalParent.insertBefore(sm, sm._originalNext);
          } else {
            sm._originalParent.appendChild(sm);
          }
        } catch (err) {}
        sm._originalParent = null;
        sm._originalNext = null;
      }
    }
    var bgDd = document.getElementById('bg-color-dropdown');
    if (bgDd && bgDd.classList.contains('open')) {
      bgDd.classList.remove('open');
      bgDd.classList.add('hidden');
      document.body.classList.remove('bg-dropdown-open');
      bgDd.style.removeProperty('position');
      bgDd.style.removeProperty('top');
      bgDd.style.removeProperty('left');
      bgDd.style.removeProperty('bottom');
      bgDd.style.removeProperty('right');
      bgDd.style.removeProperty('transform');
      bgDd.style.removeProperty('margin');
      bgDd.style.removeProperty('z-index');
      if (bgDd._originalParent) {
        try {
          if (bgDd._originalNext && bgDd._originalNext.parentElement === bgDd._originalParent) {
            bgDd._originalParent.insertBefore(bgDd, bgDd._originalNext);
          } else {
            bgDd._originalParent.appendChild(bgDd);
          }
        } catch (err) {}
        bgDd._originalParent = null;
        bgDd._originalNext = null;
      }
    }
  }
});

window.handleSearchKey = function (event) {
  if (event.key === 'Enter') {
    searchInCanvas(event.target.value);
  }
};

window.handleSearchMenuKey = function (event) {
  if (event.key === 'Enter') {
    var val = event.target.value.trim().toLowerCase();
    var items = { dashboard: 0, financeiro: 1, campo: 2, estoque: 3 };
    var targets = ['dashboard', 'financeiro', 'campo', 'estoque'];
    var match = targets.find(function (t) {
      return t.indexOf(val) >= 0 || val.indexOf(t) >= 0;
    });
    if (match) {
      searchAction(match);
    } else if (val) {
      searchAction(val);
    }
    event.target.value = '';
  }
  if (event.key === 'Escape') {
    closeSearchMenuNow();
  }
};

window.toggleExportDropdown = function () {
  var dropdown = document.getElementById('export-dropdown');

  if (dropdown) {
    dropdown.classList.toggle('hidden');
  }
};

window.exportDashboardData = function () {
  exportReport('csv');

  document.getElementById('export-dropdown').classList.add('hidden');
};

window.exportOptions = { widgets: true, period: true, filters: true };

window.toggleExportOption = function (option) {
  window.exportOptions[option] = !window.exportOptions[option];

  var optionIndex = { widgets: 0, period: 1, filters: 2 };

  var labels = document.querySelectorAll('#export-dropdown label');

  if (labels[optionIndex[option]]) {
    var cb = labels[optionIndex[option]].querySelector('input[type="checkbox"]');

    if (cb) cb.checked = window.exportOptions[option];
  }
};

window.openAmplIAPanel = function () {
  toggleIAPanel();
};

window.fecharMarketplaceWidgets = function () {
  document.getElementById('marketplace-modal').classList.add('hidden');
};

window.addWidget = function (widgetId, chartType) {
  var type = WIDGET_TYPES[widgetId];

  /* ── Auto-registo: o modal oferecia e o clique morria em silêncio ──
   *
   * Este `return 'desconhecido'` silencioso foi a causa de 22 widgets
   * do catálogo que, quando clicados, não acrescentavam nada: a ficha
   * faltava em WIDGET_TYPES e o clique acabava num toast de erro.
   *
   * Registar os 22 corrige o sintoma. A linha abaixo corrige a CAUSA:
   * um widget anunciado no catálogo passa a ser instalável mesmo que
   * a ficha se perca, em vez de devolver 'desconhecido'. O título vem
   * do próprio catálogo, para a matriz não mostrar "Widget".
   *
   * Isto não é adivinhação: o utilizador escolheu explicitamente um
   * widget que o sistema lhe ofereceu. O que não fazemos é inventar
   * conteúdo — só garantimos que o contentor nasce, e o renderizador
   * decide se tem dados para mostrar ou se escreve "sem dado".
   */
  if (!type) {
    var _rot = null;
    try {
      if (window.WIDGET_CATALOG) {
        var _cats = window.WIDGET_CATALOG;
        for (var _ck2 in _cats) {
          var _arr = _cats[_ck2];
          if (!Array.isArray(_arr)) continue;
          for (var _i2 = 0; _i2 < _arr.length; _i2++) {
            if (_arr[_i2] && _arr[_i2].id === widgetId) {
              _rot = _arr[_i2];
              break;
            }
          }
          if (_rot) break;
        }
      }
    } catch (e) {}
    type = {
      title: (_rot && _rot.label) || widgetId,
      icon: (_rot && _rot.icon) || 'bi-grid-3x3-gap',
      defaultSize: { w: 6, h: 6 },
    };
    WIDGET_TYPES[widgetId] = type;
    if (window.console) console.warn('[widgets] ficha auto-registada para "' + widgetId + '"');
  }

  if (!type) return 'desconhecido';
  if (widgets[widgetId] && widgets[widgetId].visible) {
    if (window._editingWidgetIdForGeneric === widgetId) {
      // Editando genérico já existente — apenas fecha e mantém (bg/cor já via preview)
      window._editingWidgetIdForGeneric = null;
      if (typeof closeAddWidgetModal === 'function')
        try {
          closeAddWidgetModal();
        } catch (e) {}
      return 'existente';
    }
    /* Já está no dashboard: destaca onde ele está em vez de nada */
    try {
      var el = document.getElementById('widget-' + widgetId);
      if (el) {
        if (el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        el.style.transition = 'box-shadow .3s';
        el.style.boxShadow = '0 0 0 3px var(--pal-accent, #0f9d6e)';
        setTimeout(function () {
          el.style.boxShadow = '';
        }, 1200);
      }
    } catch (e) {}
    return 'existente';
  }

  var pos = findFreePosition(type.defaultSize.w, type.defaultSize.h);

  if (!pos) {
    if (typeof showToast === 'function') showToast('warning', 'Espaço insuficiente na matriz!');
    return 'sem-espaco';
  }

  widgets[widgetId] = {
    gridX: pos.x,
    gridY: pos.y,
    gridW: type.defaultSize.w,
    gridH: type.defaultSize.h,
    visible: true,
  };
  // #region agent log
  if (window.__dbgNav)
    window.__dbgNav('C', 'pagina-index.js:addWidget', 'widget added', {
      widgetId: widgetId,
      total: Object.keys(widgets).length,
      stack: (new Error().stack || '').split('\n').slice(1, 6).join(' | '),
    });
  // #endregion
  if (chartType) widgets[widgetId].chartType = chartType;

  saveWidgetsLayout();
  renderWidgetsOnMatrix();
  return 'adicionado';
};

var _ampConfirmCb = null;

window.showCenterConfirmDialog = function (opts) {
  var ov = document.getElementById('amp-confirm-overlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'amp-confirm-overlay';
    ov.style.cssText =
      'position:fixed;top:0;left:0;right:0;bottom:0;z-index:2147483000;display:none;align-items:center;justify-content:center;background:rgba(2,6,23,0.55);backdrop-filter:blur(3px);padding:16px';
    ov.innerHTML =
      '' +
      '<div id="amp-confirm-card" style="background:#ffffff;color:#1d2421;border-radius:16px;box-shadow:0 25px 60px -12px rgba(0,0,0,0.45);width:100%;max-width:360px;padding:20px;transform:translateY(6px);opacity:0;transition:transform .18s ease,opacity .18s ease">' +
      '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">' +
      '<div id="amp-confirm-icon" style="width:34px;height:34px;min-width:34px;border-radius:10px;background:#fef2f2;color:#ef4444;display:flex;align-items:center;justify-content:center;font-size:15px"><i class="bi bi-exclamation-triangle"></i></div>' +
      '<div id="amp-confirm-title" style="font-weight:700;font-size:14px"></div>' +
      '</div>' +
      '<div id="amp-confirm-msg" style="font-size:12px;color:#5f6b66;line-height:1.5;margin-bottom:16px;word-break:break-word"></div>' +
      '<div style="display:flex;justify-content:flex-end;gap:8px">' +
      '<button id="amp-confirm-cancel" style="padding:7px 14px;font-size:12px;font-weight:600;border-radius:9px;border:1px solid #e9eeec;background:var(--cor-fundo-card);color:var(--cor-texto-medio);cursor:pointer">Cancelar</button>' +
      '<button id="amp-confirm-ok" style="padding:7px 16px;font-size:12px;font-weight:600;border-radius:9px;border:none;background:#ef4444;color:#fff;cursor:pointer">Confirmar</button>' +
      '</div>' +
      '</div>';
    document.body.appendChild(ov);
    ov.addEventListener('mousedown', function (e) {
      if (e.target === ov) window.closeCenterConfirmDialog();
    });
  }
  opts = opts || {};
  var ok = document.getElementById('amp-confirm-ok');
  var cancel = document.getElementById('amp-confirm-cancel');
  if (!ok || !cancel) return;
  var titleEl = document.getElementById('amp-confirm-title');
  var msgEl = document.getElementById('amp-confirm-msg');
  if (titleEl) titleEl.textContent = opts.title || 'Atenção';
  if (msgEl) msgEl.textContent = opts.message || '';
  ok.textContent = opts.confirmLabel || 'Confirmar';
  if (opts.danger) {
    ok.style.background = '#ef4444';
  } else {
    ok.style.background = '#0f9d6e';
  }
  _ampConfirmCb = typeof opts.onConfirm === 'function' ? opts.onConfirm : null;
  cancel.onclick = function () {
    window.closeCenterConfirmDialog();
  };
  ok.onclick = function () {
    var cb = _ampConfirmCb;
    _ampConfirmCb = null;
    window.closeCenterConfirmDialog();
    if (cb) cb();
  };
  ov.style.display = 'flex';
  requestAnimationFrame(function () {
    var card = document.getElementById('amp-confirm-card');
    if (card) {
      card.style.transform = 'translateY(0)';
      card.style.opacity = '1';
    }
  });
};

window.closeCenterConfirmDialog = function () {
  var ov = document.getElementById('amp-confirm-overlay');
  if (!ov || ov.style.display === 'none') return;
  var card = document.getElementById('amp-confirm-card');
  if (card) {
    card.style.transform = 'translateY(6px)';
    card.style.opacity = '0';
  }
  var ok = document.getElementById('amp-confirm-ok');
  var cancel = document.getElementById('amp-confirm-cancel');
  if (ok) ok.onclick = null;
  if (cancel) cancel.onclick = null;
  ov.style.display = 'none';
};

document.addEventListener('keydown', function (e) {
  var k = e.key;
  if (k !== 'Delete' && k !== 'Backspace') return;
  if (!widgetEditMode && !customMode) return;
  if (!_selectedWidgetId || !widgets[_selectedWidgetId]) return;
  var t = e.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  var ov = document.getElementById('amp-confirm-overlay');
  if (ov && ov.style.display !== 'none') return;
  e.preventDefault();
  e.stopPropagation();
  if (typeof window.deleteSelectedWidget === 'function') window.deleteSelectedWidget();
});

window.removeWidget = function (widgetId, skipConfirm) {
  if (!widgets[widgetId]) return;
  function performRemove() {
    var cfg = widgets[widgetId];
    if (!cfg) return;
    cfg.visible = false;
    if (_selectedWidgetId === widgetId) {
      _selectedWidgetId = null;
      document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
        el.classList.remove('widget-selected');
      });
    }
    document.querySelectorAll('.edit-dropdown').forEach(function (d) {
      d.classList.remove('open');
      d.classList.add('hidden');
    });
    saveWidgetsLayout();
    renderWidgetsOnMatrix();
  }
  if (skipConfirm) {
    performRemove();
    return;
  }
  showCenterConfirmDialog({
    title: 'Remover widget',
    message: 'Tem certeza que deseja remover este widget do dashboard?',
    confirmLabel: 'Remover',
    danger: true,
    onConfirm: performRemove,
  });
};

window.clearAllWidgets = function () {
  showCenterConfirmDialog({
    title: 'Limpar dashboard',
    message: 'Tem certeza que deseja remover todos os widgets do dashboard?',
    confirmLabel: 'Limpar tudo',
    danger: true,
    onConfirm: function () {
      Object.keys(widgets).forEach(function (id) {
        widgets[id].visible = false;
      });
      widgets = {};
      _selectedWidgetId = null;
      document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
        el.classList.remove('widget-selected');
      });
      document.querySelectorAll('.edit-dropdown').forEach(function (d) {
        d.classList.remove('open');
        d.classList.add('hidden');
      });
      saveWidgetsLayout();
      renderWidgetsOnMatrix();
    },
  });
};

function getCookie(name) {
  var cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

window.hasWidgetSession = function () {
  /* MEDIDO 2026-10-05: isto devolvia `false` para TODOS os utilizadores
   * autenticados, sempre. E' a razão de o dashboard inteiro mostrar
   * "sem dado".
   *
   * A cadeia, medida no browser com uma sessao valida (uid 60):
   *
   *     document.cookie ................ "csrftoken"     (so este)
   *     getCookie('sessionid') ......... null
   *     hasWidgetSession() ............. false
   *     /api/dashboard/ ................ NUNCA chamada
   *     window.dashboardData ........... null
   *     window.widgetDataCache ........ null
   *
   * A causa: `config/settings/base.py` tem `SESSION_COOKIE_HTTPONLY = True`
   * (que e' o certo e o default do Django), e um cookie HTTP-only nao e'
   * legivel por `document.cookie`. Nao ha excepcao — um cookie
   * HTTP-only e' invisible para o JS por desenho. Logo
   * `getCookie('sessionid')` nunca pode devolver nada, e a funcao era
   * sempre `false`.
   *
   * E o efeito era silencioso: os guardas `if (!hasWidgetSession()) return`
   * faziam o fetch do payload nao correr, o `dashboardData` ficava `null`,
   * e cada widget caia no ramo "sem dado". Nenhum erro, nenhum 403 — so a
   * ausencia de dados, que e' indistinguivel de "o produtor nao tem nada".
   *
   * A correccao anterior (2026-10-04) trocou `sessionid || csrftoken` por
   * so `sessionid`, para evitar que um visitante anonimo contasse como
   * sessao. O `csrftoken` e' mesmo emitido antes de qualquer login, e
   * aquele `||` estava certo em esconder o anonimo — mas a correccao
   * introduziu um problema maior: `sessionid` nao e' visivel, entao a
   * guarda passou a proteger ninguem do outro lado.
   *
   * Agora o sinal vem de onde e' verdade: o SERVIDOR. O `<body>` leva
   * `data-authenticated`, que o template preenche com `user.is_authenticated`
   * — o mesmo valor que ja desvia o nome do utilizador no menu.
   *
   * A ordem das fontes e' deliberada:
   *   1. `data-authenticated` no <body> — o servidor, sem ambiguidade
   *   2. `AMPLIAGRO_UID`               — ausente em anonimo, presente em logado
   *   3. `getCookie('sessionid')`      — so se algum dia SESSION_COOKIE_HTTPONLY
   *                                       for posto a False; hoje nunca
   */
  var corpo = document.body;
  if (corpo && corpo.getAttribute) {
    var flag = corpo.getAttribute('data-authenticated');
    if (flag === '1' || flag === '0') return flag === '1';
  }
  // O UID e' posto pelo servidor so para utilizadores com sessao.
  if (window.AMPLIAGRO_UID != null && window.AMPLIAGRO_UID !== '') return true;
  // Ultimo recurso, e so porque um dia o cookie pode deixar de ser
  // http-only. Nao e' de confianza: hoje devolve sempre null.
  return !!getCookie('sessionid');
};

window.saveWidgetsLayout = function () {
  // Nunca salva layout vazio (evita sobrescrever preset correto com 0 visto no console F12)
  try {
    if (!widgets || !Object.keys(widgets || {}).length) {
      dashboardLog('saveWidgetsLayout:skip', { reason: '0 widgets' });
      return;
    }
  } catch (e) {}
  try {
    dashboardLog('saveWidgetsLayout:queue', {
      caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 120),
      widgets: (function () {
        try {
          return Object.keys(widgets || {}).length;
        } catch (e) {
          return 0;
        }
      })(),
    });
  } catch (e) {}
  debouncedSave(
    'widgets-layout',
    function () {
      try {
        window.widgets = widgets;
        sset('matrix-widgets-layout', JSON.stringify(widgets));
        if (typeof sflush === 'function')
          try {
            sflush();
          } catch (e) {}
        try {
          dashboardLog('saveWidgetsLayout:flushed', { count: Object.keys(widgets || {}).length });
        } catch (e) {}
        // Persiste tambem no preset ativo para nao perder ao trocar de preset
        try {
          if (typeof saveCurrentPreset === 'function') saveCurrentPreset();
        } catch (e) {}
        scheduleDashboardStateSync();
        if (!hasWidgetSession()) return;
        fetch('/api/widgets-layout-sync/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken'),
          },
          credentials: 'same-origin',
          body: JSON.stringify({ widgets: widgets }),
        })
          // NAO engolir em silencio. MEDIDO, 2026-10-04: o
          // `.catch(function(){})` sem nada antes fazia este POST
          // falhar 403 a CADA re-render da matriz, e o unico
          // sintoma visivel eram linhas de log do Django. Um 401
          // ou 403 aqui significa "a sessao morreu" — o que o
          // utilizador PRECISA de ver, porque o proximo ecrã
          // dele esta a mostrar numeros que nao sao dele.
          .then(function (r) {
            if (r.status === 401 || r.status === 403) {
              dashboardLog('widgets-layout-sync:sem-sessao', {
                status: r.status,
              });
              location.href =
                '/login/?next=' + encodeURIComponent(location.pathname + location.search);
            }
          })
          .catch(function () {});
      } catch (e) {
        console.warn('Erro ao salvar layout:', e);
      }
    },
    150
  );
};
// Flush imediato para garantir que reload rapido nao perca estilo/meta
window.saveWidgetsLayoutImmediate = function () {
  try {
    dashboardLog('saveWidgetsLayoutImmediate', {
      caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 120),
      count: (function () {
        try {
          return Object.keys(widgets || {}).length;
        } catch (e) {
          return 0;
        }
      })(),
    });
  } catch (e) {}
  try {
    window.widgets = widgets;
    sset('matrix-widgets-layout', JSON.stringify(widgets));
    if (typeof sflush === 'function')
      try {
        sflush();
      } catch (e) {}
    try {
      if (typeof saveCurrentPreset === 'function') saveCurrentPreset();
    } catch (e) {}
    scheduleDashboardStateSync();
    if (!hasWidgetSession()) return;
    fetch('/api/widgets-layout-sync/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      credentials: 'same-origin',
      body: JSON.stringify({ widgets: widgets }),
    })
      // mesmo tratamento do `saveWidgetsLayout`: um 401/403
      // aqui e' sessao perdida, e nao um erro de rede para
      // engolir. Ver o comentario completo em `saveWidgetsLayout`.
      .then(function (r) {
        if (r.status === 401 || r.status === 403) {
          location.href = '/login/?next=' + encodeURIComponent(location.pathname + location.search);
        }
      })
      .catch(function () {});
  } catch (e) {
    console.warn('saveImmediate', e);
  }
};

// — histórico debounced: cada save em edição vira um passo de undo após 500ms —
(function () {
  var _origSave = window.saveWidgetsLayout;
  var histTimer = null;
  window.saveWidgetsLayout = function () {
    var res = _origSave.apply(this, arguments);
    try {
      var isEditing = document.getElementById('dashboard-appbar')?.classList.contains('editing');
      if (isEditing && typeof window.pushLayoutHistory === 'function') {
        clearTimeout(histTimer);
        histTimer = setTimeout(function () {
          try {
            window.pushLayoutHistory();
          } catch (e) {}
        }, 550);
      }
    } catch (e) {}
    return res;
  };
})();

window.saveCurrentAsPreset = function (name) {
  try {
    sset('matrix-widgets-preset-' + name, JSON.stringify(widgets));
    window.addFilterTagSafe('Preset "' + name + '" salvo');
  } catch (e) {
    console.warn('Erro ao salvar preset:', e);
  }
};

window.restoreWidgetsLayout = function () {
  try {
    var backup = sget('matrix-widgets-backup');
    if (!backup) return;
    // guarda estado atual no histórico antes de restaurar para permitir refazer
    if (typeof window.pushLayoutHistory === 'function') {
      try {
        window.pushLayoutHistory();
      } catch (e) {}
    }
    widgets = JSON.parse(backup);
    saveWidgetsLayout();
    renderWidgetsOnMatrix();
    window.addFilterTagSafe('Layout personalizado restaurado');
    document.querySelectorAll('.preset-card').forEach(function (c) {
      c.classList.remove('active');
    });
    if (typeof window.pushLayoutHistory === 'function') {
      try {
        window.pushLayoutHistory();
      } catch (e) {}
    }
    if (typeof window.updateHistoryButtons === 'function')
      try {
        window.updateHistoryButtons();
      } catch (e) {}
  } catch (e) {
    console.warn('[restore] erro:', e);
  }
};

// ── Histórico de layouts — snapshot ao entrar em edição + undo/redo com setas ──
(function () {
  var MAX = 20;
  var undoStack = [];
  var redoStack = [];
  function deepClone(o) {
    try {
      return JSON.parse(JSON.stringify(o));
    } catch (e) {
      return {};
    }
  }
  function loadHistory() {
    try {
      var u = sget('matrix-layout-history-undo');
      var r = sget('matrix-layout-history-redo');
      if (u) undoStack = JSON.parse(u);
      if (r) redoStack = JSON.parse(r);
    } catch (e) {}
    if (!Array.isArray(undoStack)) undoStack = [];
    if (!Array.isArray(redoStack)) redoStack = [];
  }
  function persist() {
    try {
      sset('matrix-layout-history-undo', JSON.stringify(undoStack));
      sset('matrix-layout-history-redo', JSON.stringify(redoStack));
    } catch (e) {}
  }
  loadHistory();
  window.updateHistoryButtons = function () {
    var undoBtn = document.getElementById('layout-undo-btn');
    var redoBtn = document.getElementById('layout-redo-btn');
    var undoCount = Math.max(0, undoStack.length - 1);
    var redoCount = redoStack.length;
    if (undoBtn) {
      undoBtn.disabled = undoCount === 0;
      undoBtn.setAttribute('aria-disabled', undoBtn.disabled ? 'true' : 'false');
      undoBtn.dataset.count = String(undoCount);
      undoBtn.title = undoCount
        ? 'Desfazer (' + undoCount + ' passos) — Ctrl+Z'
        : 'Desfazer (Ctrl+Z)';
    }
    if (redoBtn) {
      redoBtn.disabled = redoCount === 0;
      redoBtn.setAttribute('aria-disabled', redoBtn.disabled ? 'true' : 'false');
      redoBtn.dataset.count = String(redoCount);
      redoBtn.title = redoCount
        ? 'Refazer (' + redoCount + ' passos) — Ctrl+Y'
        : 'Refazer (Ctrl+Y)';
    }
  };
  window.pushLayoutHistory = function () {
    try {
      var snap = deepClone(widgets);
      // evita duplicado idêntico ao topo
      if (undoStack.length > 0) {
        try {
          if (JSON.stringify(undoStack[undoStack.length - 1]) === JSON.stringify(snap)) return;
        } catch (e) {}
      }
      undoStack.push(snap);
      if (undoStack.length > MAX) undoStack.shift();
      redoStack = [];
      persist();
      window.updateHistoryButtons();
    } catch (e) {
      console.warn('[history push] erro', e);
    }
  };
  window.undoLayoutHistory = function () {
    try {
      if (undoStack.length <= 1) return;
      var current = undoStack.pop();
      redoStack.push(current);
      var prev = deepClone(undoStack[undoStack.length - 1]);
      widgets = prev;
      // persiste também no preset ativo para manter coerência
      try {
        var activePreset = sget('matrix-active-preset') || 'base-ia';
        if (typeof persistPresetWidgets === 'function') persistPresetWidgets(activePreset, widgets);
      } catch (e) {}
      saveWidgetsLayout();
      renderWidgetsOnMatrix();
      persist();
      window.updateHistoryButtons();
      window.addFilterTagSafe('Desfeito');
    } catch (e) {
      console.warn('[undo] erro', e);
    }
  };
  window.redoLayoutHistory = function () {
    try {
      if (redoStack.length === 0) return;
      var next = redoStack.pop();
      undoStack.push(deepClone(next));
      if (undoStack.length > MAX) undoStack.shift();
      widgets = deepClone(next);
      try {
        var activePreset2 = sget('matrix-active-preset') || 'base-ia';
        if (typeof persistPresetWidgets === 'function')
          persistPresetWidgets(activePreset2, widgets);
      } catch (e) {}
      saveWidgetsLayout();
      renderWidgetsOnMatrix();
      persist();
      window.updateHistoryButtons();
      window.addFilterTagSafe('Refeito');
    } catch (e) {
      console.warn('[redo] erro', e);
    }
  };
  // alias compatíveis com dashboard_appbar.html
  window.undoLayout = window.undoLayoutHistory;
  window.redoLayout = window.redoLayoutHistory;
  // expõe para debug
  window._layoutHistory = {
    get undo() {
      return undoStack;
    },
    get redo() {
      return redoStack;
    },
  };
  // inicializa botões
  setTimeout(window.updateHistoryButtons, 300);
  // garante que existe ao menos 1 entrada
  setTimeout(function () {
    if (undoStack.length === 0) {
      try {
        window.pushLayoutHistory();
      } catch (e) {}
    } else {
      window.updateHistoryButtons();
    }
  }, 600);
  // atalhos Ctrl+Z / Ctrl+Y ou Ctrl+Shift+Z
  document.addEventListener('keydown', function (e) {
    var isEdit = document.getElementById('dashboard-appbar')?.classList.contains('editing');
    if (!isEdit) return;
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      window.undoLayoutHistory();
    } else if (
      (e.ctrlKey || e.metaKey) &&
      (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))
    ) {
      e.preventDefault();
      window.redoLayoutHistory();
    }
  });
})();

// Guard: evita multiplos cliques rapidos no mesmo preset (debounce 800ms)
window._loadPresetLock = window._loadPresetLock || { name: null, time: 0 };
window.loadPreset = function (presetName) {
  var now = Date.now();
  if (window._loadPresetLock.name === presetName && now - window._loadPresetLock.time < 800) {
    try {
      dashboardLog('loadPreset:debounced', {
        to: presetName,
        delta: now - window._loadPresetLock.time,
      });
    } catch (e) {}
    return;
  }
  window._loadPresetLock = { name: presetName, time: now };
  try {
    dashboardLog('loadPreset', {
      from: sget('matrix-active-preset') || 'visao-geral',
      to: presetName,
      caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 120),
    });
  } catch (e) {}
  // 1. Persist current preset synchronously before switching so edits are preserved
  var currentPreset = sget('matrix-active-preset') || 'base-ia';
  if (currentPreset !== presetName && widgets && Object.keys(widgets).length > 0) {
    persistPresetWidgets(currentPreset, widgets);
  }
  try {
    sset('matrix-widgets-backup', JSON.stringify(widgets));
  } catch (e) {}
  hydratePresetWidgets();
  // 2. Synchronously load the new preset's widgets (no setTimeout race condition) — UMA UNICA RENDERIZACAO
  widgets = clonePresetWidgets(presetName);
  try {
    sset('matrix-active-preset', presetName);
    sset('matrix-widgets-layout', JSON.stringify(widgets));
  } catch (e) {}
  syncPresetsToPreferences();
  // Atualiza active e sombra/fundo por preset (sombra = mesma cor do fundo de cada preset)
  document
    .querySelectorAll('.preset-block, .preset-card, .modal-preset-card')
    .forEach(function (card) {
      var key =
        (card.dataset && (card.dataset.preset || card.dataset.presetKey)) ||
        card.getAttribute('data-preset') ||
        '';
      var isActive = key === presetName;
      card.classList.toggle('active-preset', isActive);
      try {
        var p = PRESETS[key] || PRESETS[presetName];
        var c = p && p.color ? p.color : '';
        var valid =
          c &&
          (/^#([0-9a-fA-F]{3,8})$/.test(c) ||
            c.indexOf('rgb') === 0 ||
            c.indexOf('hsl') === 0 ||
            c.indexOf('var(') === 0);
        if (!valid && key) {
          var map = { 'visao-geral': '#0f9d6e', 'visao Geral': '#0f9d6e', default: '#64748b' };
          if (map[key]) {
            c = map[key];
            valid = true;
          } else if (key.indexOf('visao') === 0) {
            c = '#0f9d6e';
            valid = true;
          }
        }
        if (valid && card.classList.contains('preset-block')) {
          var hexToRgba = function (hex, a) {
            try {
              var h = hex.replace('#', '');
              if (h.length === 3)
                h = h
                  .split('')
                  .map(function (ch) {
                    return ch + ch;
                  })
                  .join('');
              if (h.length === 6)
                return (
                  'rgba(' +
                  parseInt(h.slice(0, 2), 16) +
                  ',' +
                  parseInt(h.slice(2, 4), 16) +
                  ',' +
                  parseInt(h.slice(4, 6), 16) +
                  ',' +
                  a +
                  ')'
                );
              return hex;
            } catch (e) {
              return hex;
            }
          };
          var bgA = isActive ? 0.14 : 0.09;
          var shA = isActive ? 0.28 : 0.18;
          card.style.background = hexToRgba(c, bgA);
          card.style.boxShadow =
            '0 4px 14px ' + hexToRgba(c, shA) + ', 0 1px 4px ' + hexToRgba(c, shA * 0.6);
        } else if (valid) {
          // preset-card / modal: sombra colorida leve
          var shA2 = isActive ? 0.22 : 0.14;
          var hexToRgba2 = function (hex, a) {
            try {
              var h = hex.replace('#', '');
              if (h.length === 3)
                h = h
                  .split('')
                  .map(function (ch) {
                    return ch + ch;
                  })
                  .join('');
              if (h.length === 6)
                return (
                  'rgba(' +
                  parseInt(h.slice(0, 2), 16) +
                  ',' +
                  parseInt(h.slice(2, 4), 16) +
                  ',' +
                  parseInt(h.slice(4, 6), 16) +
                  ',' +
                  a +
                  ')'
                );
              return hex;
            } catch (e) {
              return hex;
            }
          };
          card.style.boxShadow =
            '0 6px 18px ' + hexToRgba2(c, shA2) + ', 0 2px 6px ' + hexToRgba2(c, shA2 * 0.6);
        }
      } catch (e) {}
    });
  activeFilters = activeFilters.filter(function (filter) {
    return filter.indexOf('Preset: ') !== 0;
  });
  normalizeWidgetPositions();
  renderWidgetsOnMatrix();
  saveWidgetsLayout();
  if (typeof sflush === 'function')
    try {
      sflush();
    } catch (e) {}
  window.addFilterTagSafe('Preset: ' + presetName.charAt(0).toUpperCase() + presetName.slice(1));
  // NOTA: refreshMarketWidgetsData e forceDashboardCorrect removidos daqui para evitar 2º/3º reload.
  // O renderWidgetsOnMatrix já usa o _chartData absoluto do preset com bg 0.6 / tracejada 0.15 correto.
  // Se precisar atualizar dados de mercado, o usuário clica em Atualizar, não automático no switch.
  // NOTE: DB widgets from /api/widgets-usuario/ are intentionally NOT merged here.
};
window.setPeriodMode = function (mode) {
  currentPeriod = mode;

  var buttons = document.querySelectorAll('#period-toggle div');

  buttons.forEach(function (btn) {
    btn.classList.remove('active-period');
  });

  var activeBtn = Array.from(buttons).find(function (btn) {
    return btn.textContent.toLowerCase() === mode.toLowerCase();
  });

  if (activeBtn) {
    activeBtn.classList.add('active-period');
  }

  window.addFilterTagSafe(mode.charAt(0).toUpperCase() + mode.slice(1));
};

window.setFinancialMode = function (mode) {
  financialMode = mode;

  var buttons = document.querySelectorAll('#financial-toggle button');

  buttons.forEach(function (btn) {
    btn.classList.remove('active', 'lucros', 'gastos');
  });

  var activeBtn = Array.from(buttons).find(function (btn) {
    return btn.textContent.toLowerCase().includes(mode);
  });

  if (activeBtn) {
    activeBtn.classList.add('active');
    if (mode === 'lucros') activeBtn.classList.add('lucros');
    if (mode === 'gastos') activeBtn.classList.add('gastos');
  }

  // Filtrar widgets por categoria financeira (funciona em modo de edicao tambem)
  document.querySelectorAll('.bento-block').forEach(function (el) {
    var wId = el.id.replace('widget-', '');
    if (mode === 'ambos') {
      el.style.display = '';
    } else if (mode === 'lucros') {
      el.style.display =
        wId.indexOf('roi') >= 0 ||
        wId.indexOf('caixa') >= 0 ||
        wId.indexOf('line') >= 0 ||
        wId.indexOf('pie') >= 0
          ? ''
          : 'none';
    } else if (mode === 'gastos') {
      el.style.display =
        wId.indexOf('custo') >= 0 ||
        wId.indexOf('manuten') >= 0 ||
        wId.indexOf('alerta') >= 0 ||
        wId.indexOf('bar') >= 0
          ? ''
          : 'none';
    }
  });

  window.addFilterTagSafe(mode.charAt(0).toUpperCase() + mode.slice(1));
};

window.setPeriodFilter = function (period) {
  currentPeriod = period;

  var buttons = document.querySelectorAll('#period-toggle div');

  buttons.forEach(function (btn) {
    btn.classList.remove('active-period');
  });

  var activeBtn = Array.from(buttons).find(function (btn) {
    return btn.textContent.toLowerCase() === period.toLowerCase();
  });

  if (activeBtn) {
    activeBtn.classList.add('active-period');
  }

  // Update ALL chart widgets with the new period (destroy + rebuild so
  // every widget type — generic, safras/cultura, producao-animal — re-renders)
  if (typeof chartInstances !== 'undefined') {
    Object.keys(chartInstances).forEach(function (cId) {
      try {
        chartInstances[cId].destroy();
      } catch (e) {}
      delete chartInstances[cId];
    });
  }
  if (typeof initChartsForWidgets === 'function') {
    initChartsForWidgets();
  }

  window.addFilterTagSafe(period.charAt(0).toUpperCase() + period.slice(1));
};

// Drag Slider functionality — Windows 11 pill + drag em qualquer lugar + scroll + global move
function initDragSliders() {
  document.querySelectorAll('.drag-slider').forEach(function (slider) {
    var thumb = slider.querySelector('.drag-slider-thumb');
    var fill = slider.querySelector('.drag-slider-fill');
    if (!thumb) return;
    var values = (slider.dataset.values || '').split(',').filter(Boolean);
    if (!values.length) return;
    var currentIndex = parseInt(slider.dataset.index) || 0;
    currentIndex = Math.max(0, Math.min(values.length - 1, currentIndex));
    var isDragging = false;
    var hasDragged = false;

    function updateThumbPosition(percent, force) {
      var clampedPercent = Math.max(0, Math.min(100, percent));
      thumb.style.left = clampedPercent + '%';
      if (fill) fill.style.width = clampedPercent + '%';
      thumb.setAttribute(
        'data-value',
        values[Math.round((clampedPercent / 100) * (values.length - 1))] || ''
      );
      var valueIndex = Math.round((clampedPercent / 100) * (values.length - 1));
      valueIndex = Math.max(0, Math.min(values.length - 1, valueIndex));
      if (force || valueIndex !== currentIndex) {
        currentIndex = valueIndex;
        slider.dataset.index = String(currentIndex);
        var span = thumb.querySelector('span');
        if (span) span.textContent = values[currentIndex];
        thumb.setAttribute('data-value', values[currentIndex]);
        if (slider.id === 'period-slider') {
          setPeriodFilter(values[currentIndex].toLowerCase());
        } else if (slider.id === 'financial-slider') {
          setFinancialMode(values[currentIndex].toLowerCase());
        }
      }
    }

    // Set initial position
    var initialPercent = values.length > 1 ? (currentIndex / (values.length - 1)) * 100 : 0;
    updateThumbPosition(initialPercent, true);
    slider.style.cursor = 'grab';
    slider.style.userSelect = 'none';

    function getPercentFromClientX(clientX) {
      var rect = slider.getBoundingClientRect();
      var x = clientX - rect.left;
      return (x / rect.width) * 100;
    }

    function onPointerDown(e) {
      // permite drag em qualquer lugar do slider (track, fill, thumb)
      isDragging = true;
      hasDragged = false;
      slider.style.cursor = 'grabbing';
      thumb.style.cursor = 'grabbing';
      // evita seleção de texto
      e.preventDefault();
      var percent = getPercentFromClientX(e.clientX);
      updateThumbPosition(percent);
      // captura global para continuar arrastando mesmo fora da barra
      document.addEventListener('mousemove', onPointerMove);
      document.addEventListener('mouseup', onPointerUp);
      document.addEventListener('touchmove', onTouchMove, { passive: false });
      document.addEventListener('touchend', onPointerUp);
    }

    function onPointerMove(e) {
      if (!isDragging) return;
      hasDragged = true;
      var percent = getPercentFromClientX(e.clientX);
      updateThumbPosition(percent);
    }

    function onTouchMove(e) {
      if (!isDragging) return;
      if (e.touches && e.touches[0]) {
        hasDragged = true;
        var percent = getPercentFromClientX(e.touches[0].clientX);
        updateThumbPosition(percent);
        e.preventDefault();
      }
    }

    function onPointerUp() {
      if (!isDragging) return;
      isDragging = false;
      slider.style.cursor = 'grab';
      thumb.style.cursor = 'grab';
      document.removeEventListener('mousemove', onPointerMove);
      document.removeEventListener('mouseup', onPointerUp);
      document.removeEventListener('touchmove', onTouchMove);
      document.removeEventListener('touchend', onPointerUp);
      // evita click fantasma após drag
      setTimeout(function () {
        hasDragged = false;
      }, 50);
    }

    // inicia drag em qualquer parte do slider
    slider.addEventListener('mousedown', onPointerDown);
    slider.addEventListener(
      'touchstart',
      function (e) {
        if (e.touches && e.touches[0]) {
          isDragging = true;
          hasDragged = false;
          var percent = getPercentFromClientX(e.touches[0].clientX);
          updateThumbPosition(percent);
          document.addEventListener('touchmove', onTouchMove, { passive: false });
          document.addEventListener('touchend', onPointerUp);
        }
      },
      { passive: true }
    );

    // scroll/wheel para trocar de estado (dia→semana... / lucros→ambos→gastos)
    slider.addEventListener(
      'wheel',
      function (e) {
        e.preventDefault();
        var delta = e.deltaY > 0 ? 1 : -1;
        // inverte se for shift? não, mantém natural (scroll down = próximo)
        var newIdx = Math.max(0, Math.min(values.length - 1, currentIndex + delta));
        if (newIdx !== currentIndex) {
          var percent = (newIdx / (values.length - 1)) * 100;
          updateThumbPosition(percent, true);
        }
      },
      { passive: false }
    );

    // click no track (sem arrastar) — ignora se foi drag
    slider.addEventListener('click', function (e) {
      if (hasDragged) {
        e.preventDefault();
        return;
      }
      // se clicou no thumb, já foi tratado no mousedown (evita duplo)
      if (e.target === thumb || thumb.contains(e.target)) return;
      var percent = getPercentFromClientX(e.clientX);
      updateThumbPosition(percent);
    });
  });
}

// Tooltip de presets agora é o unificado (caixa com nome acima, widgetbar-windows.css)
// initPresetPreviews desativado para não duplicar tooltip
function initPresetPreviews() {
  return;
}

// Initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () {
    initDragSliders();
    initPresetPreviews();
  });
} else {
  initDragSliders();
  initPresetPreviews();
}

window.getChartDataForPeriod = function (period) {
  var d = dashboardData;
  var labelsMap = {
    today: [''],
    week: ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
    month: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
    semester: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
    year: [],
    fiveyears: [],
  };
  var labels = labelsMap[period] || labelsMap['month'];
  if (d && d.chart_data && d.chart_data[period]) {
    var cd = d.chart_data[period];
    var cdLabels = Array.isArray(cd.labels) ? cd.labels : labels;
    var cdData = Array.isArray(cd.data) ? cd.data : [];
    return {
      labels: cdLabels,
      datasets: [
        {
          label: cd.label || 'Valores',
          data: cdData,
          borderColor: cd.borderColor || chartPalette().accent,
          backgroundColor: cd.backgroundColor || hexToRgba(chartPalette().accent, 0.1),
          fill: cd.fill !== undefined ? cd.fill : false,
          tension: cd.tension !== undefined ? cd.tension : 0.3,
        },
      ],
    };
  }
  // Sem dado real para o período: gráfico vazio, nunca números fictícios.
  return {
    labels: labels,
    datasets: [
      {
        label: 'Sem lançamentos no período',
        data: labels.map(function () {
          return 0;
        }),
        borderColor: chartPalette().accent,
        backgroundColor: hexToRgba(chartPalette().accent, 0.1),
        fill: false,
        tension: 0.3,
      },
    ],
  };
};

window.applyPeriodFilter = function (period) {
  setPeriodFilter(period);
};

window.addFilterTag = function (label) {
  if (activeFilters.includes(label)) return;

  activeFilters.push(label);

  updateFilterTagsDisplay();
};
// Drena o que o stub acumulou durante a init (setPeriodFilter pode ter disparado
// addFilterTagSafe antes desta definicao existir).
// updateFilterTagsDisplay so e definida DEPOIS, por isso a drenagem espera o proximo frame.
function _drainAddFilterTagQueue() {
  try {
    if (typeof window.updateFilterTagsDisplay !== 'function') return false;
    if (!window.__addFilterTagQueue || !window.__addFilterTagQueue.length) return true;
    var _qft = window.__addFilterTagQueue.slice();
    window.__addFilterTagQueue.length = 0;
    _qft.forEach(function (lbl) {
      try {
        window.addFilterTag(lbl);
      } catch (e) {}
    });
    return true;
  } catch (e) {
    return true;
  }
}
if (typeof requestAnimationFrame === 'function') {
  requestAnimationFrame(function () {
    _drainAddFilterTagQueue();
  });
} else {
  setTimeout(function () {
    _drainAddFilterTagQueue();
  }, 0);
}

window.updateFilterTagsDisplay = function () {
  var container = document.getElementById('active-tags-container');

  var list = document.getElementById('active-tags-list');

  if (!container || !list) return;

  if (activeFilters.length > 0) {
    container.classList.remove('hidden');

    list.innerHTML = activeFilters
      .map(function (filter) {
        var safeFilter = JSON.stringify(filter);

        return (
          '<span class="filter-tag">' +
          filter +
          ' <button onclick="removeFilterTag(' +
          safeFilter +
          ')"><i class="bi bi-x"></i></button></span>'
        );
      })
      .join('');
  } else {
    container.classList.add('hidden');
  }
};

window.removeFilterTag = function (filter) {
  activeFilters = activeFilters.filter(function (f) {
    return f !== filter;
  });

  updateFilterTagsDisplay();
};

window.clearAllFilters = function () {
  activeFilters = [];

  updateFilterTagsDisplay();
};

window.debounceSearch = function (event) {
  if (searchTimeout) clearTimeout(searchTimeout);

  searchTimeout = setTimeout(function () {
    searchInCanvas(event.target.value);
  }, 300);
};

window.searchInCanvas = function (query) {
  document.querySelectorAll('.bento-block').forEach(function (el) {
    el.classList.remove('widget-highlighted');
  });

  if (!query) return;

  document.querySelectorAll('.bento-block').forEach(function (el) {
    if (el.textContent.toLowerCase().includes(query.toLowerCase())) {
      el.classList.add('widget-highlighted');
    }
  });
};

window.exportReport = function (format) {
  if (format === 'csv') {
    var csv = 'data:text/csv;charset=utf-8,Widget,Posição\n';

    Object.entries(widgets).forEach(function ([id, config]) {
      csv += id + ',' + config.gridX + ',' + config.gridY + '\\n';
    });

    var link = document.createElement('a');

    link.setAttribute('href', encodeURI(csv));

    link.setAttribute('download', 'dashboard_widgets.csv');

    link.click();
  } else {
    alert('Exportando como ' + format.toUpperCase() + '...');
  }
};

window.openAmpliaPortal = function () {
  document.getElementById('amplia-portal-modal').classList.remove('hidden');
};

window.closeAmpliaPortal = function () {
  document.getElementById('amplia-portal-modal').classList.add('hidden');
};

window.sendAmpliaMessage = function () {
  // O chat ativo é o ia-dock (window.iaDockSend). Este modal legado
  // apenas encaminha o texto para lá — nada de resposta mockada.
  var input = document.getElementById('amplia-input');
  if (!input || !input.value.trim()) return;
  var txt = input.value;
  input.value = '';
  document.getElementById('amplia-portal-modal').classList.add('hidden');
  var dock = document.getElementById('ia-dock-input');
  if (dock) {
    dock.value = txt;
    if (typeof window.iaDockSend === 'function') {
      window.iaDockSend();
      return;
    }
  }
  if (typeof window.iaDockToggle === 'function') window.iaDockToggle();
};

function getWidgetChartData(id) {
  var w = widgetDataCache || {};
  var safras = w.safras || {};
  var fin = w.financeiro || {};
  var est = w.estoque || {};
  var anim = w.animais || {};
  var now = new Date();

  // Culture name from widget id (e.g. cultura-arroz_mercado_... -> arroz)
  var chartCultKey = '';
  var chartCultBase = String(id).split('_mercado_')[0] || String(id).split('_')[0] || '';
  if (chartCultBase.indexOf('cultura-') === 0) {
    chartCultKey = chartCultBase.replace('cultura-', '').replace(/-/g, ' ').toLowerCase().trim();
  }
  function chartSafrasOfCulture(items) {
    var all = items || [];
    if (!chartCultKey) return all;
    var filtered = all.filter(function (s) {
      return s && s.cultura && String(s.cultura).toLowerCase().indexOf(chartCultKey) >= 0;
    });
    return filtered.length > 0 ? filtered : all;
  }

  function filterByPeriod(labels, values, period) {
    if (!labels.length || !values.length) return { labels: labels, values: values };
    var n = labels.length;
    var take = n;
    if (period === 'today') take = Math.min(1, n);
    else if (period === 'week') take = Math.min(7, n);
    else if (period === 'month') take = Math.min(6, n);
    else if (period === 'semester') take = Math.min(12, n);
    else if (period === 'year' || period === 'fiveyears') take = n;
    var start = Math.max(0, n - take);
    return { labels: labels.slice(start), values: values.slice(start) };
  }

  // Market widget from mini-panel: use stored chart data, filtered by period
  var wCfg = window.widgets && window.widgets[id];
  if (wCfg && wCfg._chartData && wCfg._chartData.labels && wCfg._chartData.labels.length > 0) {
    var cd = wCfg._chartData;
    if (cd.datasets && cd.datasets.length > 0) {
      var filtered = filterByPeriod(cd.labels, cd.datasets[0].data, currentPeriod);
      return {
        labels: filtered.labels,
        datasets: cd.datasets.map(function (ds, i) {
          var f = i === 0 ? filtered : filterByPeriod(cd.labels, ds.data, currentPeriod);
          return {
            label: ds.label || 'Serie ' + (i + 1),
            data: f.values,
            borderColor: ds.borderColor,
            backgroundColor: ds.backgroundColor,
            fill: ds.fill,
            tension: ds.tension,
          };
        }),
      };
    }
    return cd;
  }

  // Build chart data based on widget ID prefix/content
  // chart-safras: harvests by year (or by month when fine period selected)
  if (id === 'chart-safras' || id.indexOf('cultura-') >= 0) {
    var finePeriod =
      currentPeriod === 'today' || currentPeriod === 'week' || currentPeriod === 'month';
    var rawItems = chartSafrasOfCulture(
      typeof w.safras !== 'undefined' && w.safras.items ? w.safras.items : []
    );
    if (finePeriod && rawItems.length > 0) {
      // Aggregate by month using data_plantio (fallback: data_colheita, then ano)
      var byMonth = {};
      rawItems.forEach(function (s) {
        var dateStr = s.data_plantio || s.data_colheita || null;
        var ym = dateStr ? dateStr.substring(0, 7) : s.ano ? String(s.ano) + '-01' : null;
        if (!ym) return;
        byMonth[ym] = byMonth[ym] || { producao: 0, area: 0 };
        byMonth[ym].producao += parseFloat(s.producao || s.producao_total || 0) || 0;
        byMonth[ym].area += parseFloat(s.area || s.area_plantada || 0) || 0;
      });
      var monthKeys = Object.keys(byMonth).sort().slice(-12);
      var monthNames = [
        'Jan',
        'Fev',
        'Mar',
        'Abr',
        'Mai',
        'Jun',
        'Jul',
        'Ago',
        'Set',
        'Out',
        'Nov',
        'Dez',
      ];
      return {
        labels: monthKeys.map(function (k) {
          var parts = k.split('-');
          var mIdx = parseInt(parts[1], 10) - 1;
          return (
            (parts[0] === String(now.getFullYear()) ? '' : parts[0] + ' ') + (monthNames[mIdx] || k)
          );
        }),
        datasets: [
          {
            label: 'Produção Total',
            data: monthKeys.map(function (k) {
              return byMonth[k].producao;
            }),
            borderColor: chartPalette().accent,
            backgroundColor: hexToRgba(chartPalette().accent, 0.6),
          },
          {
            label: 'Área (ha)',
            data: monthKeys.map(function (k) {
              return byMonth[k].area;
            }),
            borderColor: chartPalette().pie[1],
            backgroundColor: hexToRgba(chartPalette().pie[1], 0.4),
          },
        ],
      };
    }
    if (chartCultKey) {
      // Culture-specific: aggregate safras of this culture by year
      var cultByYear = {};
      chartSafrasOfCulture(rawItems).forEach(function (s) {
        var y = s.ano != null ? String(s.ano) : '';
        if (!y) return;
        if (!cultByYear[y]) cultByYear[y] = { total_producao: 0, total_area: 0 };
        cultByYear[y].total_producao += parseFloat(s.producao || s.producao_total || 0) || 0;
        cultByYear[y].total_area += parseFloat(s.area || s.area_plantada || 0) || 0;
      });
      var cyItems = Object.keys(cultByYear)
        .sort()
        .map(function (k) {
          return {
            ano: k,
            total_producao: Math.round(cultByYear[k].total_producao * 100) / 100,
            total_area: Math.round(cultByYear[k].total_area * 100) / 100,
          };
        });
      var cyfItems = filterByPeriod(
        cyItems.map(function (i) {
          return String(i.ano);
        }),
        cyItems.map(function (i) {
          return parseFloat(i.total_producao) || 0;
        }),
        currentPeriod
      );
      var cyfArea = filterByPeriod(
        cyItems.map(function (i) {
          return String(i.ano);
        }),
        cyItems.map(function (i) {
          return parseFloat(i.total_area) || 0;
        }),
        currentPeriod
      );
      return {
        labels: cyfItems.labels,
        datasets: [
          {
            label: 'Produção Total',
            data: cyfItems.values,
            borderColor: chartPalette().accent,
            backgroundColor: hexToRgba(chartPalette().accent, 0.6),
          },
          {
            label: 'Área (ha)',
            data: cyfArea.values,
            borderColor: chartPalette().pie[1],
            backgroundColor: hexToRgba(chartPalette().pie[1], 0.4),
          },
        ],
      };
    }
    var items = safras.por_ano || [];
    var fItems = filterByPeriod(
      items.map(function (i) {
        return String(i.ano);
      }),
      items.map(function (i) {
        return parseFloat(i.total_producao) || 0;
      }),
      currentPeriod
    );
    var fArea = filterByPeriod(
      items.map(function (i) {
        return String(i.ano);
      }),
      items.map(function (i) {
        return parseFloat(i.total_area) || 0;
      }),
      currentPeriod
    );
    return {
      labels: fItems.labels,
      datasets: [
        {
          label: 'Produção Total',
          data: fItems.values,
          borderColor: chartPalette().accent,
          backgroundColor: hexToRgba(chartPalette().accent, 0.6),
        },
        {
          label: 'Área (ha)',
          data: fArea.values,
          borderColor: chartPalette().pie[1],
          backgroundColor: hexToRgba(chartPalette().pie[1], 0.4),
        },
      ],
    };
  }
  // chart-financeiro: financial by category
  if (id === 'chart-financeiro') {
    var cats = fin.por_categoria || [];
    var receitas = cats.filter(function (c) {
      return c.tipo === 'RECEITA';
    });
    var despesas = cats.filter(function (c) {
      return c.tipo === 'DESPESA';
    });
    return {
      labels: receitas.map(function (c) {
        return c.categoria;
      }),
      datasets: [
        {
          label: 'Receitas',
          data: receitas.map(function (c) {
            return parseFloat(c.total) || 0;
          }),
          backgroundColor: (function () {
            var p = chartPalette().pie;
            return [
              hexToRgba(p[0], 0.7),
              hexToRgba(p[1], 0.6),
              hexToRgba(p[2], 0.5),
              hexToRgba(p[3], 0.4),
            ];
          })(),
        },
      ],
    };
  }
  // chart-estoque: inventory by category
  if (id === 'chart-estoque') {
    var cats = est.por_categoria || [];
    return {
      labels: cats.map(function (c) {
        return c.categoria;
      }),
      datasets: [
        {
          label: 'Quantidade',
          data: cats.map(function (c) {
            return parseFloat(c.total) || 0;
          }),
          backgroundColor: hexToRgba(chartPalette().pie[2], 0.6),
        },
      ],
    };
  }
  // chart-producao-animal: animal production filtered by period
  if (id === 'chart-producao-animal') {
    var prods = w.producao_animal || [];
    var byMonth = {};
    prods.forEach(function (p) {
      if (!p.data) return;
      var m = p.data.substring(0, 7);
      byMonth[m] = (byMonth[m] || 0) + parseFloat(p.quantidade || 0);
    });
    var mKeys = Object.keys(byMonth).sort();
    var monthNames = [
      'Jan',
      'Fev',
      'Mar',
      'Abr',
      'Mai',
      'Jun',
      'Jul',
      'Ago',
      'Set',
      'Out',
      'Nov',
      'Dez',
    ];
    var filtered = filterByPeriod(
      mKeys.map(function (k) {
        var p = k.split('-');
        return monthNames[parseInt(p[1], 10) - 1] + ' ' + p[0];
      }),
      mKeys.map(function (k) {
        return byMonth[k];
      }),
      currentPeriod
    );
    return {
      labels: filtered.labels,
      datasets: [
        {
          label: 'Produção',
          data: filtered.values,
          borderColor: chartPalette().accent,
          backgroundColor: hexToRgba(chartPalette().accent, 0.2),
          fill: true,
          tension: 0.3,
        },
      ],
    };
  }

  // Fallback: use period-based generic data
  return getChartDataForPeriod(currentPeriod);
}

function chartPalette() {
  if (typeof window.ampliChartPalette === 'function') {
    var p = window.ampliChartPalette();
    return {
      isDark: p.isDark,
      accent: p.accent,
      accentBar: p.accentBar,
      accentFill: p.accentFill,
      grid: p.grid,
      gridSoft: p.gridSoft,
      tick: p.tick,
      pointBorder: p.pointBorder,
      chartBg: p.chartBg,
      ok: p.ok,
      alert: p.alert,
      error: p.error,
      warn: p.warn,
      pie: p.series,
    };
  }
  var isDark = document.documentElement.classList.contains('dark');
  return isDark
    ? {
        isDark: true,
        accent: '#3b82f6',
        accentBar: 'rgba(59,130,246,0.55)',
        accentFill: 'rgba(59,130,246,0.12)',
        grid: 'rgba(255,255,255,0.08)',
        gridSoft: 'rgba(255,255,255,0.05)',
        tick: '#cbd5e1',
        pointBorder: '#151b19',
        pie: [
          '#3b82f6',
          '#60a5fa',
          '#2563eb',
          '#38bdf8',
          '#6366f1',
          '#818cf8',
          '#0ea5e9',
          '#93c5fd',
        ],
      }
    : {
        isDark: false,
        accent: '#0f9d6e',
        accentBar: 'rgba(15,157,110,0.6)',
        accentFill: 'rgba(15,157,110,0.06)',
        grid: 'rgba(0,0,0,0.06)',
        gridSoft: 'rgba(0,0,0,0.04)',
        tick: '#5f6b66',
        pointBorder: '#fff',
        pie: [
          '#0f9d6e',
          '#c19a3c',
          '#2f8f7e',
          '#3b82f6',
          '#8b5cf6',
          '#14b8a6',
          '#84cc16',
          '#e08f3c',
        ],
      };
}

function hexToRgba(c, a) {
  if (!c || c.charAt(0) !== '#') return c;
  var r = parseInt(c.slice(1, 3), 16),
    g = parseInt(c.slice(3, 5), 16),
    b = parseInt(c.slice(5, 7), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + a + ')';
}

function darkenDatasetColors(ds) {
  if (!ds || typeof ds !== 'object') return ds;
  var out = {};
  Object.keys(ds).forEach(function (k) {
    out[k] = ds[k];
  });
  var map = {
    '#0f9d6e': '#3b82f6',
    'rgba(15,157,110,0.6)': 'rgba(59,130,246,0.55)',
    'rgba(15,157,110,0.7)': 'rgba(59,130,246,0.65)',
    'rgba(15,157,110,0.08)': 'rgba(59,130,246,0.12)',
    'rgba(15,157,110,0.06)': 'rgba(59,130,246,0.12)',
    '#0f9d6e': '#3b82f6',
    'rgba(0,107,104,0.6)': 'rgba(59,130,246,0.55)',
    'rgba(0,107,104,0.2)': 'rgba(59,130,246,0.2)',
    'rgba(0,107,104,0.1)': 'rgba(59,130,246,0.12)',
    'rgba(0, 107, 104, 0.1)': 'rgba(59,130,246,0.12)',
  };
  [
    'borderColor',
    'backgroundColor',
    'pointBackgroundColor',
    'pointBorderColor',
    'hoverBackgroundColor',
    'hoverBorderColor',
  ].forEach(function (key) {
    if (typeof out[key] === 'string' && map[out[key]]) out[key] = map[out[key]];
    if (Array.isArray(out[key]))
      out[key] = out[key].map(function (c) {
        return map[c] || c;
      });
  });
  return out;
}

function chartDataHasPoints(cfg) {
  if (!cfg || !cfg.data || !cfg.data.datasets || !cfg.data.datasets.length) return false;
  return cfg.data.datasets.some(function (ds) {
    if (!ds || !ds.data || !ds.data.length) return false;
    return ds.data.some(function (v) {
      return v !== null && v !== undefined && v !== '';
    });
  });
}

function showChartEmpty(canvas) {
  if (!canvas || canvas.getAttribute('data-empty')) return;
  canvas.setAttribute('data-empty', '1');
  canvas.style.display = 'none';
  var wrap = canvas.parentElement;
  if (wrap && !wrap.querySelector('.chart-empty-msg')) {
    var d = document.createElement('div');
    d.className = 'chart-empty-msg';
    d.setAttribute(
      'title',
      'Nenhum lançamento cadastrado para este indicador ainda. Cadastre registros para visualizar o gráfico.'
    );
    d.innerHTML = '<i class="bi bi-inbox"></i> Sem registros';
    wrap.appendChild(d);
  }
}

/* Repinta todos os gráficos quando a paleta do tema muda */
document.addEventListener('ampliagro:palette', function () {
  if (typeof window.initChartsForWidgets !== 'function') return;
  Object.keys(chartInstances || {}).forEach(function (cId) {
    try {
      chartInstances[cId].destroy();
    } catch (e) {}
    delete chartInstances[cId];
  });
  window.initChartsForWidgets();
});

function watchChartResize(canvasEl) {
  if (!canvasEl || canvasEl._chartResizeObs || typeof ResizeObserver === 'undefined') return;
  try {
    canvasEl._chartResizeObs = new ResizeObserver(function () {
      var inst = chartInstances[canvasEl.id];
      if (inst && typeof inst.resize === 'function') inst.resize();
    });
    canvasEl._chartResizeObs.observe(canvasEl.parentElement || canvasEl);
  } catch (e) {}
}

function buildChartConfig(id, ctx) {
  var wid = ctx.id.replace('chart-', '');
  var wCfg = widgets[wid] || {};
  // Delega para market config apenas se tem metricKey (evita loop infinito quando _mercado_ sem metricKey)
  if (wCfg.metricKey && typeof buildMarketChartConfig === 'function') {
    // Evita recursão: buildMarketChartConfig pode voltar para cá se sem metricKey
    if (window._buildChartRecursion) return null;
    window._buildChartRecursion = true;
    var mCfg = buildMarketChartConfig(wid, ctx);
    window._buildChartRecursion = false;
    if (mCfg) return mCfg;
  }
  // Preserva exatamente o formato do painel de inserir: chartSubtype, chartType, chartStyle
  var chartType = wCfg.chartType || wCfg.chartSubtype || getDefaultChartType(id);
  // Se tem chartStyleCategory/Variant (do editor), usa o tipo da variante (ex: barra vs linha)
  try {
    if (wCfg.chartStyleCategory && wCfg.chartStyleVariant && window.AmpliChartStyles) {
      var v = AmpliChartStyles.variant(wCfg.chartStyleCategory, wCfg.chartStyleVariant);
      if (
        v &&
        v.type &&
        ['bar', 'line', 'pie', 'doughnut', 'radar', 'polarArea', 'scatter', 'bubble'].indexOf(
          v.type
        ) >= 0
      ) {
        chartType = v.type;
      }
    }
  } catch (e) {}
  var chartData = getWidgetChartData(wid);
  var pal = chartPalette();

  function rgba(c, a) {
    return 'rgba(' + (c.match(/\d+/g) || [0, 0, 0]).join(',') + ',' + a + ')';
  }

  var config = {
    type: chartType,
    data: {
      labels: chartData.labels || [],
      datasets: (chartData.datasets || []).map(function (ds) {
        return pal.isDark && !document.documentElement.classList.contains('custom-theme')
          ? darkenDatasetColors(ds)
          : ds;
      }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false, axis: 'x' },
      plugins: {
        legend: {
          display: chartType !== 'line' && chartType !== 'area' && chartType !== 'scatter',
          labels: {
            boxWidth: 12,
            usePointStyle: true,
            padding: 16,
            font: { size: 11, family: "'Space Grotesk', 'Inter', sans-serif" },
            pointStyle: 'circle',
            color: pal.tick,
          },
        },
        tooltip: {
          enabled: true,
          backgroundColor: pal.isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.95)',
          titleColor: pal.isDark ? '#e2e8f0' : '#1e293b',
          bodyColor: pal.isDark ? '#cbd5e1' : '#334155',
          borderColor: pal.isDark ? 'rgba(51, 65, 85, 0.5)' : 'rgba(226, 232, 240, 0.8)',
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          titleFont: { size: 13, family: "'Space Grotesk', 'Inter', sans-serif", weight: '600' },
          bodyFont: { size: 12, family: "'Inter', sans-serif" },
          displayColors: true,
          boxPadding: 4,
          usePointStyle: true,
          callbacks: {
            label: function (context) {
              var label = context.dataset.label || '';
              if (label) label += ': ';
              if (context.parsed.y !== null) {
                var val = context.parsed.y;
                if (val >= 1000) label += (val / 1000).toFixed(1).replace('.0', '') + 'k';
                else label += val;
              }
              return label;
            },
          },
        },
      },
      scales: {},
    },
  };

  // Configure scales per chart type
  if (chartType === 'radar') {
    config.options.scales = {
      r: { grid: { color: pal.grid }, ticks: { font: { size: 8 }, color: pal.tick } },
    };
    config.options.plugins.tooltip.enabled = true;
  } else if (chartType === 'polarArea') {
    config.options.scales = { r: { grid: { color: pal.grid } } };
    config.options.plugins.tooltip.enabled = true;
  } else if (chartType === 'scatter' || chartType === 'bubble') {
    // Convert to scatter format: {x, y} objects
    if (
      config.data.datasets &&
      config.data.datasets[0] &&
      Array.isArray(config.data.datasets[0].data)
    ) {
      var vals = config.data.datasets[0].data;
      var lbls = config.data.labels || [];
      config.data.datasets[0].data = vals.map(function (v, i) {
        return { x: i, y: v };
      });
    }
    config.options.scales = {
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: { font: { size: 9 }, padding: 4, color: pal.tick },
      },
      y: {
        display: true,
        grid: { display: false },
        border: { display: false },
        ticks: { font: { size: 9 }, padding: 4, color: pal.tick },
      },
    };
  } else {
    var formatYLabel = function (value) {
      if (value >= 1000000) return (value / 1000000).toFixed(1).replace('.0', '') + 'M';
      if (value >= 1000) return (value / 1000).toFixed(0) + 'k';
      return value;
    };
    config.options.scales = {
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: { font: { size: 9 }, maxRotation: 0, autoSkip: true, padding: 8, color: pal.tick },
      },
      y: {
        display: true,
        position: 'right',
        grid: { display: false, drawBorder: false },
        border: { display: false },
        ticks: {
          font: { size: 8 },
          color: pal.isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.3)',
          padding: 2,
          callback: formatYLabel,
          maxTicksLimit: 6,
        },
      },
    };
    config.options.layout = { padding: { top: 4, bottom: 2, left: 0, right: 0 } };

    // Animação fluida e contínua (delegando o deslize LTR para o CSS reveal-chart)
    config.options.animation = {
      duration: 1000,
      easing: 'easeOutQuart',
    };
  }

  // Ensure backgroundColor arrays for pie/doughnut/polar
  if (['pie', 'doughnut', 'polarArea'].indexOf(chartType) >= 0) {
    if (
      !config.data.datasets[0].backgroundColor ||
      typeof config.data.datasets[0].backgroundColor === 'string'
    ) {
      config.data.datasets[0].backgroundColor = pal.pie.slice();
    }
  }

  // Style datasets (Chart Lab Premium)
  var ctx2d = ctx.getContext('2d');

  function createDynamicGradient(baseColor, alphaStart, alphaEnd) {
    var grad = ctx2d.createLinearGradient(0, 0, 0, 300);
    var r = 15,
      g = 157,
      b = 110;
    if (baseColor) {
      if (baseColor.indexOf('#') === 0) {
        var hex = baseColor.replace('#', '');
        if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
        r = parseInt(hex.substring(0, 2), 16) || r;
        g = parseInt(hex.substring(2, 4), 16) || g;
        b = parseInt(hex.substring(4, 6), 16) || b;
      } else if (baseColor.indexOf('rgb') === 0) {
        var match = baseColor.match(/\d+/g);
        if (match && match.length >= 3) {
          r = match[0];
          g = match[1];
          b = match[2];
        }
      }
    }
    grad.addColorStop(0, 'rgba(' + r + ',' + g + ',' + b + ',' + alphaStart + ')');
    grad.addColorStop(1, 'rgba(' + r + ',' + g + ',' + b + ',' + alphaEnd + ')');
    return grad;
  }

  config.data.datasets.forEach(function (ds, idx) {
    if (!ds.borderColor)
      ds.borderColor = idx === 0 ? pal.accent : pal.pie[idx % pal.pie.length] || '#f59e0b';

    if (['line', 'area', 'radar'].indexOf(chartType) >= 0) {
      ds.fill = ds.fill !== undefined ? ds.fill : 'origin';
      ds.tension = ds.tension !== undefined ? ds.tension : 0.4; // smooth curve Chart Lab style

      if (
        !ds.backgroundColor ||
        ds.backgroundColor === 'rgba(245,158,11,0.1)' ||
        String(ds.backgroundColor).indexOf('LinearGradient') > -1
      ) {
        ds.backgroundColor = createDynamicGradient(ds.borderColor, pal.isDark ? 0.35 : 0.25, 0.0);
      }

      ds.borderWidth = 3; // thicker modern lines

      if (ds.pointRadius === undefined || ds.pointRadius === 0) {
        ds.pointRadius = 0; // clean SVG look, no dots
        ds.pointHoverRadius = 6;
        ds.pointHoverBackgroundColor = ds.borderColor;
        ds.pointHoverBorderColor = pal.isDark ? '#0f172a' : '#ffffff';
        ds.pointHoverBorderWidth = 2;
        ds.hitRadius = 10;
      }
    } else if (chartType === 'bar') {
      ds.borderWidth = 0;
      ds.borderRadius = 4; // rounded bars
      if (!ds.backgroundColor) ds.backgroundColor = ds.borderColor;
    }
  });

  return config;
}

function getDefaultChartType(id) {
  if (id === 'chart-pie' || id === 'chart-financeiro') return 'pie';
  if (id === 'chart-doughnut') return 'doughnut';
  if (id === 'chart-polar') return 'polarArea';
  if (id === 'chart-radar') return 'radar';
  if (id === 'chart-scatter') return 'scatter';
  if (id === 'chart-bubble') return 'bubble';
  if (id === 'chart-mixed') return 'bar'; // bar with line overlay added below
  if (id === 'chart-stacked-bar') return 'bar';
  if (id === 'chart-horizontal-bar') return 'bar';
  if (id === 'chart-area') return 'line';
  if (id === 'chart-safras') return 'bar';
  if (id === 'chart-estoque' || id === 'chart-producao-animal') return 'line';
  return 'line';
}

window.initChartsForWidgets = function () {
  document.querySelectorAll('canvas[id^="chart-"]').forEach(function (ctx) {
    if (typeof Chart !== 'undefined') {
      if (chartInstances[ctx.id] && chartInstances[ctx.id].canvas !== ctx) {
        try {
          chartInstances[ctx.id].destroy();
        } catch (e) {}
        delete chartInstances[ctx.id];
      }
      if (!chartInstances[ctx.id]) {
        var wid = ctx.id.replace('chart-', '');
        var cfg = buildChartConfig(wid, ctx);

        if (!chartDataHasPoints(cfg)) {
          showChartEmpty(ctx);
          return;
        }

        // Special: mixed chart = bar + line overlay
        if (wid === 'chart-mixed') {
          cfg.type = 'bar';
          if (cfg.data.datasets.length > 1) {
            cfg.data.datasets[1].type = 'line';
            cfg.data.datasets[1].borderColor = '#f59e0b';
            cfg.data.datasets[1].backgroundColor = 'transparent';
            cfg.data.datasets[1].fill = false;
            cfg.data.datasets[1].tension = 0.3;
          }
        }

        // Stacked bar
        if (wid === 'chart-stacked-bar') {
          cfg.options.scales = cfg.options.scales || {};
          cfg.options.scales.x = cfg.options.scales.x || {};
          cfg.options.scales.y = cfg.options.scales.y || {};
          cfg.options.scales.x.stacked = true;
          cfg.options.scales.y.stacked = true;
        }

        // Horizontal bar
        if (wid === 'chart-horizontal-bar') {
          cfg.options.indexAxis = 'y';
        }

        chartInstances[ctx.id] = new Chart(ctx, cfg);
        watchChartResize(ctx);
        // Trigger left-to-right reveal
        ctx.classList.add('reveal-chart');
      }
    }
  });

  // Initialize Map widgets
  document.querySelectorAll('[id^="map-"]').forEach(function (el) {
    if (!window._mapInstances) window._mapInstances = {};
    var wid = el.id.replace('map-', '');
    if (!window._mapInstances[wid] && typeof L !== 'undefined') {
      initMapWidget(wid, el);
    }
  });

  // Initialize Gantt widgets
  document.querySelectorAll('[id^="gantt-"]').forEach(function (el) {
    var wid = el.id.replace('gantt-', '');
    if (!window._ganttInitialized) window._ganttInitialized = {};
    if (!window._ganttInitialized[wid]) {
      initGanttWidget(wid, el);
    }
  });

  // Initialize Clima widgets
  document.querySelectorAll('[id^="clima-"]').forEach(function (el) {
    var wid = el.id.replace('clima-', '');
    if (!window._climaInitialized) window._climaInitialized = {};
    if (!window._climaInitialized[wid]) {
      initClimaWidget(wid, el);
    }
  });

  // Initialize IoT widgets
  document.querySelectorAll('[id^="iot-"]').forEach(function (el) {
    var wid = el.id.replace('iot-', '');
    if (!window._iotInitialized) window._iotInitialized = {};
    if (!window._iotInitialized[wid]) {
      initIotWidget(wid, el);
    }
  });

  // Initialize Comparativo widget charts
  document.querySelectorAll('[id^="chart-widget-comparativo"]').forEach(function (ctx) {
    if (typeof Chart !== 'undefined' && !chartInstances[ctx.id]) {
      var wid = ctx.id.replace('chart-', '');
      if (wid === 'widget-comparativo') {
        initComparativoWidget(wid, ctx);
      }
    }
  });

  // Initialize production multi-series chart widgets
  document.querySelectorAll('canvas[id^="chart-"]').forEach(function (ctx) {
    if (typeof Chart !== 'undefined' && !chartInstances[ctx.id]) {
      var wid = ctx.id.replace('chart-', '');
      var wCfg = window.widgets && window.widgets[wid];
      if (wCfg && wCfg.selectedRecords && wCfg.selectedRecords.length > 0) {
        var cfg = buildProductionChartConfig(wid, ctx);
        if (cfg) {
          chartInstances[ctx.id] = new Chart(ctx, cfg);
          watchChartResize(ctx);
          ctx.classList.add('reveal-chart');
        }
      }
    }
  });

  // Initialize market chart widgets
  document.querySelectorAll('canvas[id^="chart-"]').forEach(function (ctx) {
    if (typeof Chart !== 'undefined' && !chartInstances[ctx.id]) {
      var wid = ctx.id.replace('chart-', '');
      var wCfg = window.widgets && window.widgets[wid];
      if (wCfg && (wCfg.metricKey || wid.indexOf('_mercado_') >= 0)) {
        var cfg = buildMarketChartConfig(wid, ctx);
        if (cfg) {
          chartInstances[ctx.id] = new Chart(ctx, cfg);
          watchChartResize(ctx);
          ctx.classList.add('reveal-chart');
        }
      }
    }
  });

  // Qualquer canvas de gráfico que ficou sem instância = dados vazios
  document.querySelectorAll('canvas[id^="chart-"]').forEach(function (cv) {
    if (!chartInstances[cv.id]) showChartEmpty(cv);
  });
};

// ============================================
// PERIOD & FINANCIAL FILTER HANDLERS (called by widget bar sliders)
// ============================================
window.updateChartsForPeriod = function (period) {
  try {
    dashboardLog('updateChartsForPeriod', {
      period: period,
      caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 100),
    });
  } catch (e) {}
  currentPeriod = period;
  window.widgetbarState = window.widgetbarState || {};
  window.widgetbarState.chartPeriod = period;

  // Re-initialize all chart widgets with new period - preserva bgColor e formato exato
  document.querySelectorAll('canvas[id^="chart-"]').forEach(function (cv) {
    if (chartInstances[cv.id]) {
      try {
        chartInstances[cv.id].destroy();
      } catch (e) {}
      delete chartInstances[cv.id];
    }
  });

  // Refresh widgets que dependem de periodo - inclui cultura/market/production para periodo, preserva bgColor
  document.querySelectorAll('.bento-block').forEach(function (el) {
    var wid = el.id.replace('widget-', '');
    var cfg = widgets[wid];
    if (!cfg || !cfg.visible) return;
    // So atualiza widgets que dependem de periodo (chart, table, cultura com historico)
    var isPeriodWidget =
      wid.indexOf('widget-chart-') === 0 ||
      wid.indexOf('widget-table-') === 0 ||
      wid.indexOf('cultura-') === 0 ||
      wid.indexOf('_mercado_') >= 0 ||
      cfg.selectedRecords ||
      cfg.metricKey;
    if (!isPeriodWidget) return;
    var contentEl = el.querySelector('.widget-content');
    if (contentEl) {
      contentEl.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
        if (chartInstances[c.id]) {
          try {
            chartInstances[c.id].destroy();
          } catch (e) {}
          delete chartInstances[c.id];
        }
      });
      var prevBg = cfg.bgColor || el.style.getPropertyValue('background') || '';
      contentEl.innerHTML = getWidgetSpecificContent(wid);
      // Restaura bgColor exato do painel (nao perde no slider) — com !important
      if (cfg.bgColor) {
        el.style.setProperty('background', cfg.bgColor, 'important');
        el.style.setProperty('background-image', 'none', 'important');
      } else if (prevBg) {
        el.style.setProperty('background', prevBg, 'important');
        el.style.setProperty('background-image', 'none', 'important');
      }
    }
  });

  // Re-initialize charts with new period
  setTimeout(function () {
    window.initChartsForWidgets();
  }, 50);
};

window.updateFinancialFilter = function (filter) {
  financialMode = filter;
  window.widgetbarState = window.widgetbarState || {};
  window.widgetbarState.financialFilter = filter;

  // Refresh financial widgets
  document
    .querySelectorAll(
      '.bento-block[id^="widget-kpi-roi"], .bento-block[id^="widget-kpi-custo"], .bento-block[id^="widget-kpi-caixa"], .bento-block[id^="widget-chart-financeiro"], .bento-block[id^="widget-table-financeiro"], .bento-block[id^="widget-widget-financeiro"]'
    )
    .forEach(function (el) {
      var wid = el.id.replace('widget-', '');
      if (widgets[wid]) {
        var contentEl = el.querySelector('.widget-content');
        if (contentEl) {
          contentEl.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
            if (chartInstances[c.id]) {
              try {
                chartInstances[c.id].destroy();
              } catch (e) {}
              delete chartInstances[c.id];
            }
          });
          contentEl.innerHTML = getWidgetSpecificContent(wid);
        }
      }
    });

  // Re-initialize charts
  setTimeout(function () {
    window.initChartsForWidgets();
  }, 50);
};

function getMetricLabels(metricKey) {
  var labels = { x: '', y: 'Valor' };
  if (metricKey === 'valor_saca') {
    labels.x = 'Ano';
    labels.y = 'Preço (R$)';
  } else if (metricKey === 'producao_total') {
    labels.x = 'Ano';
    labels.y = 'Produção';
  } else if (metricKey === 'area_plantada') {
    labels.x = 'Ano';
    labels.y = 'Área (ha)';
  } else if (metricKey === 'produtividade' || metricKey === 'minha_produt') {
    labels.x = 'Ano';
    labels.y = 'Produtividade';
  } else if (metricKey === 'receita_estimada') {
    labels.x = 'Ano';
    labels.y = 'Receita (R$)';
  } else if (metricKey === 'sacas_total' || metricKey === 'sacas_talhao') {
    labels.y = 'Sacas';
  } else if (metricKey === 'cabecas_total') {
    labels.y = 'Cabeças';
  } else if (metricKey === 'biomassa_total') {
    labels.y = 'Biomassa (kg)';
  } else if (metricKey === 'volume_total') {
    labels.y = 'Volume (m³)';
  } else if (metricKey === 'media_talhao') {
    labels.x = 'Talhão';
    labels.y = 'Sacas/Talhão';
  } else if (metricKey === 'media_lote') {
    labels.x = 'Lote';
    labels.y = 'Cabeças/Lote';
  } else if (metricKey === 'media_tanque') {
    labels.x = 'Tanque';
    labels.y = 'kg/Tanque';
  } else if (metricKey === 'media_area') {
    labels.x = 'Área';
    labels.y = 'm³/Área';
  } else if (metricKey === 'serie_temporal' || metricKey === 'serie_temporal2') {
    labels.x = 'Data';
    labels.y = 'Quantidade';
  } else if (metricKey === 'comparativo') {
    labels.x = 'Data';
    labels.y = 'Quantidade';
  } else if (metricKey === 'distribuicao') {
    labels.x = 'Registro';
    labels.y = 'Participação (%)';
  } else if (metricKey === 'taxa_lotacao') {
    labels.y = 'Taxa (cab./ha)';
  } else if (metricKey === 'conversao_alimentar') {
    labels.y = 'Ração/Biomassa';
  } else if (metricKey === 'rendimento') {
    labels.y = 'por hectare';
  }
  return labels;
}

function buildProductionChartConfig(wid, ctx) {
  var wCfg = window.widgets && window.widgets[wid];
  if (!wCfg || !wCfg.selectedRecords) return null;
  var selectedIds = wCfg.selectedRecords;
  var metricKey = wCfg.metricKey || '';
  var records = [];
  if (window.ProductionRegistry) {
    selectedIds.forEach(function (rid) {
      var r = ProductionRegistry.getById(rid);
      if (r) records.push(r);
    });
  }
  if (records.length === 0) return null;
  var chartSubtype = wCfg.chartSubtype || 'line';
  var isCircular = ['pie', 'doughnut', 'radar', 'polarArea'].indexOf(chartSubtype) >= 0;

  // ── Compute aggregated labels & data by metricKey ──
  var labels = [],
    data = [];
  var pal = chartPalette();
  var colors = pal.isDark
    ? ['#3ec48f', '#d9b45c', '#4fb5a3', '#60a5fa', '#a78bfa', '#22d3ee', '#a3e635', '#f0a84e']
    : ['#0f9d6e', '#c19a3c', '#2f8f7e', '#3b82f6', '#8b5cf6', '#14b8a6', '#84cc16', '#e08f3c'];

  if (metricKey === 'distribuicao') {
    var total = records.reduce(function (a, r) {
      return a + (r.quantity || 0);
    }, 0);
    records.forEach(function (r) {
      labels.push(r.name || r.location || '—');
      data.push(total > 0 ? Math.round(((r.quantity || 0) / total) * 10000) / 100 : 0);
    });
    if (!isCircular) chartSubtype = 'doughnut';
    isCircular = true;
  } else if (
    metricKey === 'taxa_lotacao' ||
    metricKey === 'conversao_alimentar' ||
    metricKey === 'rendimento'
  ) {
    var locs = {},
      totalQty = 0;
    records.forEach(function (r) {
      if (r.location) locs[r.location] = (locs[r.location] || 0) + 1;
      totalQty += r.quantity || 0;
    });
    var num = Object.keys(locs).length || 1;
    labels = [
      metricKey === 'taxa_lotacao'
        ? 'Taxa'
        : metricKey === 'conversao_alimentar'
          ? 'Conversão'
          : 'Rendimento',
    ];
    data = [Math.round((totalQty / num) * 100) / 100];
  } else if (metricKey.indexOf('media_') === 0) {
    var groups = {};
    records.forEach(function (r) {
      var loc = r.location || 'Sem local';
      if (!groups[loc]) groups[loc] = { sum: 0, count: 0 };
      groups[loc].sum += r.quantity || 0;
      groups[loc].count++;
    });
    Object.keys(groups).forEach(function (loc) {
      labels.push(loc);
      data.push(Math.round((groups[loc].sum / groups[loc].count) * 100) / 100);
    });
  } else if (metricKey === 'serie_temporal') {
    var byDate = {};
    records.forEach(function (r) {
      var d = r.plantingDate || '—';
      if (!byDate[d]) byDate[d] = 0;
      byDate[d] += r.quantity || 0;
    });
    Object.keys(byDate)
      .sort()
      .forEach(function (d) {
        labels.push(d);
        data.push(Math.round(byDate[d] * 100) / 100);
      });
  } else if ((metricKey === 'comparativo' || wCfg._comparative) && records.length > 0) {
    // Comparativo: cada registro = barra/coluna distinta (nome x quantidade) — evita todos com mesmo valor por data esparsa
    var compLabels = records.map(function (r, idx) {
      return r.name || r.location || r.cultura || 'Registro ' + (idx + 1);
    });
    var compData = records.map(function (r) {
      return r.quantity != null ? r.quantity : r.producao != null ? r.producao : 0;
    });
    var datasets = [
      {
        label: 'Quantidade',
        data: compData,
        backgroundColor: records.map(function (_, idx) {
          return colors[idx % colors.length];
        }),
        borderColor: records.map(function (_, idx) {
          return colors[idx % colors.length];
        }),
        borderWidth: 2,
        pointRadius: 2,
      },
    ];
    var allDates = compLabels;
    var mLabelsC = getMetricLabels(metricKey);
    var compOpts = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false, axis: 'x' },
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: {
            boxWidth: 20,
            padding: 10,
            font: { size: 11 },
            usePointStyle: true,
            pointStyle: 'line',
            color: pal.tick,
          },
        },
        tooltip: { enabled: false },
      },
      scales: {
        x: {
          display: true,
          grid: { display: false },
          border: { display: false },
          ticks: {
            font: { size: 6 },
            maxRotation: 0,
            autoSkip: true,
            padding: 1,
            color: pal.tick,
            maxTicksLimit: 4,
          },
        },
        y: {
          display: true,
          grid: { display: false },
          border: { display: false },
          ticks: { font: { size: 6 }, padding: 1, color: pal.tick, maxTicksLimit: 4 },
        },
      },
      layout: { padding: { top: 2, bottom: 1, left: 0, right: 0 } },
    };
    var pmvC = wCfg._metaValue;
    if (
      wCfg._metaEnabled &&
      pmvC !== '' &&
      pmvC !== null &&
      pmvC !== undefined &&
      !isNaN(parseFloat(pmvC))
    ) {
      compOpts.plugins.ampliReference = {
        metaLines: [{ value: parseFloat(pmvC), color: '#d93a3a', label: 'Meta' }],
      };
    }
    return {
      type:
        ['bar', 'line', 'pie', 'doughnut', 'radar', 'polarArea', 'scatter', 'bubble'].indexOf(
          chartSubtype
        ) >= 0
          ? chartSubtype
          : 'line',
      data: { labels: allDates, datasets: datasets },
      options: compOpts,
    };
  } else {
    // *_total types — sum
    var sum = records.reduce(function (a, r) {
      return a + (r.quantity || 0);
    }, 0);
    labels = ['Total'];
    data = [Math.round(sum * 100) / 100];
  }

  if (data.length === 1 && !isCircular) {
    data.unshift(data[0]);
    labels.unshift('');
  }

  var dataset;
  if (isCircular) {
    dataset = {
      data: data,
      backgroundColor: colors.slice(0, data.length),
      borderColor: pal.isDark ? '#151b19' : '#fdfefe',
      borderWidth: 2,
    };
  } else {
    dataset = {
      data: data,
      borderColor: pal.accent,
      backgroundColor: chartSubtype === 'bar' ? pal.accentBar : pal.accentFill,
      borderWidth: 2,
      pointRadius: data.length === 2 ? [0, 5] : 2,
      pointBackgroundColor: pal.accent,
      pointBorderColor: pal.pointBorder,
      pointBorderWidth: 1,
      fill: false,
      tension: 0.35,
    };
  }

  var mLabels = getMetricLabels(metricKey);
  var hasSingleVal =
    data.length <= 2 &&
    labels.filter(function (l) {
      return l !== '';
    }).length <= 1;

  // ── Estilo escolhido no editor (categoria + variante) ──
  var pStyleCat = wCfg.chartStyleCategory || null;
  var pStyleVar = wCfg.chartStyleVariant || null;
  var pStyleMeta =
    pStyleCat && pStyleVar && window.AmpliChartStyles && AmpliChartStyles.variant
      ? AmpliChartStyles.variant(pStyleCat, pStyleVar)
      : null;
  var pConfig = {
    type: isCircular
      ? chartSubtype
      : ['bar', 'scatter', 'bubble'].indexOf(chartSubtype) >= 0
        ? chartSubtype
        : 'line',
    data: { labels: labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false, axis: 'x' },
      plugins: {
        legend: {
          display: !hasSingleVal,
          position: 'bottom',
          labels: {
            boxWidth: 20,
            padding: 10,
            font: { size: 11 },
            usePointStyle: true,
            pointStyle: 'line',
            color: pal.tick,
          },
        },
        tooltip: { enabled: false },
      },
      scales: isCircular
        ? {}
        : {
            x: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: {
                font: { size: 9 },
                maxRotation: 0,
                autoSkip: true,
                padding: 4,
                color: pal.tick,
              },
            },
            y: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: { font: { size: 9 }, padding: 4, color: pal.tick },
            },
          },
      layout: { padding: { top: 24, bottom: 4, left: 2, right: 2 } },
    },
  };
  if (pStyleMeta) {
    if (pStyleMeta.type && !isCircular) {
      pConfig.type =
        ['bar', 'line', 'scatter', 'bubble', 'pie', 'doughnut', 'radar', 'polarArea'].indexOf(
          pStyleMeta.type
        ) >= 0
          ? pStyleMeta.type
          : ['pie', 'doughnut', 'radar', 'polarArea'].indexOf(pStyleMeta.type) >= 0
            ? chartSubtype
            : 'line';
    }
    if (window.AmpliChartStyles) {
      AmpliChartStyles.applyDataset(dataset, pStyleCat, pStyleVar, {
        nopoints: pStyleMeta.type === 'line',
      });
      if (pStyleMeta.horizontal && !isCircular) {
        pConfig.options.indexAxis = 'y';
      }
      if (pStyleMeta.stacked && !isCircular) {
        pConfig.options.scales.x = pConfig.options.scales.x || {};
        pConfig.options.scales.y = pConfig.options.scales.y || {};
        pConfig.options.scales.x.stacked = true;
        pConfig.options.scales.y.stacked = true;
      }
      var pCut = AmpliChartStyles.cutout
        ? AmpliChartStyles.cutout(pStyleCat, pStyleVar)
        : undefined;
      if (pCut) pConfig.options.cutout = pCut;
      var pRot = AmpliChartStyles.rotation
        ? AmpliChartStyles.rotation(pStyleCat, pStyleVar)
        : undefined;
      if (pRot != null) pConfig.options.rotation = pRot;
      var pCirc = AmpliChartStyles.circumference
        ? AmpliChartStyles.circumference(pStyleCat, pStyleVar)
        : undefined;
      if (pCirc != null) pConfig.options.circumference = pCirc;
    }
  }

  // Cor principal escolhida no editor (série principal)
  var pmc = wCfg.mainColor || wCfg._mainColor || null;
  if (pmc) {
    var prgb = hexToRgbList(pmc);
    dataset.borderColor = pmc;
    if (isCircular) {
      dataset.backgroundColor =
        dataset.backgroundColor || (prgb ? 'rgba(' + prgb.join(',') + ',0.6)' : pmc);
    } else {
      dataset.backgroundColor =
        chartSubtype === 'bar'
          ? prgb
            ? 'rgba(' + prgb.join(',') + ',0.6)'
            : pmc
          : prgb
            ? 'rgba(' + prgb.join(',') + ',0.08)'
            : pmc;
      dataset.pointBackgroundColor = dataset.pointBackgroundColor || pmc;
      dataset.pointBorderColor = dataset.pointBorderColor || pmc;
    }
  }

  // Linha de meta escolhida no editor
  var pmv = wCfg._metaValue;
  if (
    wCfg._metaEnabled &&
    pmv !== '' &&
    pmv !== null &&
    pmv !== undefined &&
    !isNaN(parseFloat(pmv)) &&
    !isCircular
  ) {
    if (!pConfig.options.plugins) pConfig.options.plugins = {};
    pConfig.options.plugins.ampliReference = {
      metaLines: [{ value: parseFloat(pmv), color: '#d93a3a', label: 'Meta' }],
    };
  }

  return pConfig;
}

function buildMarketChartConfig(wid, ctx) {
  var wCfg = window.widgets && window.widgets[wid];
  if (!wCfg || !wCfg.metricKey) {
    if (window._buildChartRecursion) return null;
    window._buildChartRecursion = true;
    var _c = buildChartConfig(wid, ctx);
    window._buildChartRecursion = false;
    return _c;
  }

  var chartSubtype = wCfg.chartSubtype || 'line';
  var metricKey = wCfg.metricKey;
  var source = wCfg.source || 'agrodoc';
  var isCircular = ['pie', 'doughnut', 'radar', 'polarArea'].indexOf(chartSubtype) >= 0;

  if (
    wCfg._chartData &&
    Array.isArray(wCfg._chartData.labels) &&
    wCfg._chartData.labels.length > 0
  ) {
    var pal = chartPalette();
    var stored = wCfg._chartData;
    var storedDatasets = Array.isArray(stored.datasets)
      ? stored.datasets.map(function (ds) {
          return pal.isDark ? darkenDatasetColors(ds) : ds;
        })
      : [];
    var useCircular = isCircular;
    var mLabelsStored = getMetricLabels(metricKey);
    if (!mLabelsStored.x) mLabelsStored.x = 'Período';

    // ── Estilo escolhido no editor (categoria + variante) ──
    var styleCat = wCfg.chartStyleCategory || null;
    var styleVar = wCfg.chartStyleVariant || null;
    var styleMeta =
      styleCat && styleVar && window.AmpliChartStyles && AmpliChartStyles.variant
        ? AmpliChartStyles.variant(styleCat, styleVar)
        : null;
    if (styleMeta) {
      chartSubtype = styleMeta.type;
      useCircular = ['pie', 'doughnut', 'radar', 'polarArea'].indexOf(chartSubtype) >= 0;
    }
    if (styleMeta && styleMeta.stacked) {
      chartSubtype = styleMeta.type === 'line' ? 'line' : 'bar';
      if (chartSubtype === 'bar') {
        (storedDatasets || []).forEach(function (ds) {
          if (ds.stack === undefined) ds.stack = 'main';
        });
      }
    }
    storedDatasets = (storedDatasets || []).map(function (ds, idx) {
      if (window.AmpliChartStyles && styleMeta) {
        AmpliChartStyles.applyDataset(ds, styleCat, styleVar, {
          nopoints: styleMeta.type === 'line' && styleVar !== 'comPontos',
        });
      }
      return ds;
    });

    // Cor principal escolhida no editor (série principal do widget)
    var trgCol = wCfg.mainColor || wCfg._mainColor || null;
    if (trgCol && storedDatasets.length) {
      var trgRgb = hexToRgbList(trgCol);
      var dsMain0 = storedDatasets[0];
      dsMain0.borderColor = trgCol;
      if (useCircular) {
        dsMain0.backgroundColor =
          dsMain0.backgroundColor || (trgRgb ? 'rgba(' + trgRgb.join(',') + ',0.6)' : trgCol);
      } else {
        dsMain0.backgroundColor =
          chartSubtype === 'bar'
            ? trgRgb
              ? 'rgba(' + trgRgb.join(',') + ',0.6)'
              : trgCol
            : trgRgb
              ? 'rgba(' + trgRgb.join(',') + ',0.08)'
              : trgCol;
        dsMain0.pointBackgroundColor = dsMain0.pointBackgroundColor || trgCol;
        dsMain0.pointBorderColor = dsMain0.pointBorderColor || trgCol;
      }
    }

    var cfgStored = {
      type: useCircular ? chartSubtype : chartSubtype === 'bar' ? 'bar' : 'line',
      data: { labels: stored.labels, datasets: storedDatasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false, axis: 'x' },
        plugins: {
          legend: {
            display: storedDatasets.length > 1,
            position: 'bottom',
            labels: {
              boxWidth: 20,
              padding: 10,
              font: { size: 11 },
              usePointStyle: true,
              pointStyle: 'line',
              color: pal.tick,
            },
          },
          tooltip: { enabled: false },
        },
        scales: useCircular
          ? {}
          : {
              x: {
                display: true,
                grid: { display: false },
                border: { display: false },
                ticks: {
                  font: { size: 9 },
                  maxRotation: 0,
                  autoSkip: true,
                  padding: 4,
                  color: pal.tick,
                },
              },
              y: {
                display: true,
                grid: { display: false },
                border: { display: false },
                ticks: { font: { size: 9 }, padding: 4, color: pal.tick },
              },
            },
        layout: { padding: { top: 24, bottom: 4, left: 2, right: 2 } },
        animation: {
          duration: 1200,
          easing: 'easeOutQuart',
        },
      },
    };

    // ── Aplicar opções da variante (horizontal/stacked/donut) ──
    if (styleMeta) {
      if (styleMeta.horizontal && !useCircular) {
        cfgStored.options.indexAxis = 'y';
      }
      if (styleMeta.stacked && !useCircular) {
        cfgStored.options.scales = cfgStored.options.scales || {};
        cfgStored.options.scales.x = cfgStored.options.scales.x || {};
        cfgStored.options.scales.y = cfgStored.options.scales.y || {};
        cfgStored.options.scales.x.stacked = true;
        cfgStored.options.scales.y.stacked = true;
      }
      var cut = AmpliChartStyles.cutout ? AmpliChartStyles.cutout(styleCat, styleVar) : undefined;
      if (cut) cfgStored.options.cutout = cut;
      var rot = AmpliChartStyles.rotation
        ? AmpliChartStyles.rotation(styleCat, styleVar)
        : undefined;
      if (rot != null) cfgStored.options.rotation = rot;
      var circ = AmpliChartStyles.circumference
        ? AmpliChartStyles.circumference(styleCat, styleVar)
        : undefined;
      if (circ != null) cfgStored.options.circumference = circ;
      if (styleMeta.metaLine && wCfg._lastMetric && wCfg._lastMetric.meta) {
        var metaVal0 = parseFloat(wCfg._lastMetric.meta);
        cfgStored.options.plugins.ampliReference = {
          metaLines: [
            {
              value: metaVal0,
              label: 'Meta ' + metaVal0.toLocaleString('pt-BR'),
              color: '#d93a3a',
            },
          ],
        };
        // Garante Y visivel para meta do IBGE
        var dMax0 =
          Math.max.apply(
            null,
            (stored.datasets[0].data || []).filter(function (v) {
              return typeof v === 'number' && isFinite(v);
            })
          ) || 0;
        if (metaVal0 > dMax0) {
          cfgStored.options.scales = cfgStored.options.scales || {};
          cfgStored.options.scales.y = cfgStored.options.scales.y || {};
          cfgStored.options.scales.y.suggestedMax = Math.ceil(metaVal0 * 1.08);
        }
      }
    }
    var mv = wCfg._metaValue;
    if (
      wCfg._metaEnabled &&
      mv !== '' &&
      mv !== null &&
      mv !== undefined &&
      !isNaN(parseFloat(mv)) &&
      !useCircular
    ) {
      if (!cfgStored.options.plugins) cfgStored.options.plugins = {};
      var metaV = parseFloat(mv);
      cfgStored.options.plugins.ampliReference = {
        metaLines: [
          { value: metaV, color: '#d93a3a', label: 'Meta ' + metaV.toLocaleString('pt-BR') },
        ],
      };
      // Garante que a meta fique visivel mesmo acima do maximo dos dados (ex: 16M com dados ate 15M)
      var dMax =
        Math.max.apply(
          null,
          (stored.datasets[0].data || []).filter(function (v) {
            return typeof v === 'number' && isFinite(v);
          })
        ) || 0;
      if (metaV > dMax) {
        cfgStored.options.scales = cfgStored.options.scales || {};
        cfgStored.options.scales.y = cfgStored.options.scales.y || {};
        cfgStored.options.scales.y.suggestedMax = Math.ceil(metaV * 1.08);
      }
    }

    return cfgStored;
  }

  // Try to extract history from widgetDataCache
  var w = window.widgetDataCache || {};
  var safras = w.safras || {};

  // Culture name from widget id (e.g. cultura-arroz_mercado_... -> arroz)
  var cultKey = '';
  var widBase = String(wid).split('_mercado_')[0] || String(wid).split('_')[0] || '';
  if (widBase.indexOf('cultura-') === 0) {
    cultKey = widBase.replace('cultura-', '').replace(/-/g, ' ').toLowerCase().trim();
  }
  function safrasOfCulture(items) {
    var all = items || [];
    if (!cultKey) return all;
    var filtered = all.filter(function (s) {
      return s && s.cultura && String(s.cultura).toLowerCase().indexOf(cultKey) >= 0;
    });
    return filtered.length > 0 ? filtered : all;
  }

  // Build history from available data
  var labels = [];
  var data = [];

  if (source === 'cultura') {
    var cid = wid.split('_')[0];
    if (window.ProductionRegistry) {
      var records = ProductionRegistry.getByCultureSorted(cid);
      var byYear = {};
      records.forEach(function (r) {
        var year = r.plantingDate ? r.plantingDate.split('-')[0] : '';
        if (year) {
          if (!byYear[year]) byYear[year] = [];
          byYear[year].push(r);
        }
      });
      var years = Object.keys(byYear).sort().slice(-5);
      labels = years;
      data = years.map(function (y) {
        var sum = byYear[y].reduce(function (a, r) {
          return a + (r.quantity || 0);
        }, 0);
        return Math.round((sum / byYear[y].length) * 100) / 100;
      });
    }
  } else if (source === 'composite') {
    var cid2 = wid.split('_')[0];
    var myAvg = 0,
      stateVal = 0;
    if (window.ProductionRegistry) {
      var recs = ProductionRegistry.getByCultureSorted(cid2);
      var sum = 0;
      recs.forEach(function (r) {
        sum += r.quantity || 0;
      });
      myAvg = recs.length > 0 ? sum / recs.length : 0;
    }
    var stateItems = safrasOfCulture(safras.items);
    if (stateItems.length > 0) {
      stateVal = stateItems[0].produtividade || stateItems[0].producao || 0;
    }
    labels = ['Meu', 'Estado'];
    data = [myAvg, stateVal];
  } else {
    // agrodoc / ibge — use safras data from widgetDataCache (filtered by culture)
    var cultureItems = safrasOfCulture(safras.items);
    if (cultureItems.length > 0) {
      cultureItems.slice(-5).forEach(function (s) {
        labels.push(s.ano || '');
        if (metricKey === 'area_plantada') data.push(s.area || 0);
        else if (metricKey === 'producao_total') data.push(s.producao || 0);
        else if (metricKey === 'valor_saca') data.push(s.produtividade || 0);
        else if (metricKey === 'produtividade') data.push(s.produtividade || 0);
        else if (metricKey === 'sacas_talhao') data.push(s.produtividade || 0);
        else if (metricKey === 'receita_estimada')
          data.push(s.receita || (s.producao || 0) * (s.produtividade || 1) || 0);
        else data.push(s.produtividade || s.producao || 0);
      });
    }
  }

  if (labels.length === 0) {
    labels = ['Sem dados'];
    data = [0];
  }
  if (data.length === 1 && !isCircular) {
    data.unshift(data[0]);
    if (labels[0] !== 'Sem dados') labels.unshift('');
  }

  var pal = chartPalette();
  var dataset;
  if (isCircular) {
    dataset = {
      data: data,
      backgroundColor: pal.pie.slice(0, data.length),
      borderColor: pal.isDark ? '#151b19' : '#fdfefe',
      borderWidth: 2,
    };
  } else {
    dataset = {
      data: data,
      borderColor: pal.accent,
      backgroundColor: chartSubtype === 'bar' ? pal.accentBar : pal.accentFill,
      borderWidth: 2,
      pointRadius: data.length === 2 ? [0, 5] : 2,
      pointBackgroundColor: pal.accent,
      pointBorderColor: pal.pointBorder,
      pointBorderWidth: 1,
      fill: false,
      tension: 0.35,
    };
  }

  var mLabels = getMetricLabels(metricKey);
  var hasSingleVal =
    data.length <= 2 &&
    labels.filter(function (l) {
      return l !== '';
    }).length <= 1;

  return {
    type: isCircular
      ? chartSubtype
      : ['bar', 'scatter', 'bubble'].indexOf(chartSubtype) >= 0
        ? chartSubtype
        : 'line',
    data: { labels: labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false, axis: 'x' },
      plugins: {
        legend: {
          display: !hasSingleVal,
          position: 'bottom',
          labels: {
            boxWidth: 20,
            padding: 10,
            font: { size: 11 },
            usePointStyle: true,
            pointStyle: 'line',
            color: pal.tick,
          },
        },
        tooltip: { enabled: false },
      },
      scales: isCircular
        ? {}
        : {
            x: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: {
                font: { size: 9 },
                maxRotation: 0,
                autoSkip: true,
                padding: 4,
                color: pal.tick,
              },
            },
            y: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: { font: { size: 9 }, padding: 4, color: pal.tick },
            },
          },
      layout: { padding: { top: 24, bottom: 4, left: 2, right: 2 } },
    },
  };
} // ============================================
// MAP WIDGET (Leaflet)
// ============================================
window._mapInstances = {};

function initMapWidget(widgetId, container) {
  if (typeof L === 'undefined') return;
  var w = widgetDataCache;
  var prop = w && w.propriedade;
  var talhoes = w && w.talhoes && w.talhoes.items ? w.talhoes.items : [];
  var map = L.map('map-' + widgetId, { zoomControl: true, attributionControl: true });
  window._mapInstances[widgetId] = map;
  // Keep tiles in sync when the widget is resized
  var mapEl = document.getElementById('map-' + widgetId);
  if (mapEl && typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(function () {
      map.invalidateSize();
    }).observe(mapEl);
  }
  // Default center: property city or Brazil
  var center = prop && prop.uf ? [-15.7942, -47.8825] : [-15.7942, -47.8825];
  map.setView(center, 10);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap',
  }).addTo(map);
  // Add talhão polygons if geometries exist
  talhoes.forEach(function (t) {
    if (t.geometria && t.geometria.type === 'Feature') {
      L.geoJSON(t.geometria, {
        style: {
          color: chartPalette().accent,
          weight: 2,
          fillColor: chartPalette().accent,
          fillOpacity: 0.2,
        },
      })
        .addTo(map)
        .bindPopup(
          '<b>' +
            t.nome +
            '</b><br>Área: ' +
            (t.area || '—') +
            ' ha<br>Cultura: ' +
            (t.cultura || '—')
        );
    }
  });
  if (talhoes.length) {
    var group = L.featureGroup();
    talhoes.forEach(function (t) {
      if (t.geometria) group.addLayer(L.geoJSON(t.geometria));
    });
    map.fitBounds(group.getBounds().pad(0.1));
  }
}

// ============================================
// GANTT WIDGET (Timeline)
// ============================================
window._ganttInitialized = {};

function initGanttWidget(widgetId, container) {
  var w = widgetDataCache;
  var safras = w && w.safras && w.safras.items ? w.safras.items : [];
  var html = '<div class="gantt-container" style="font-size:10px;">';
  var months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
  // Header
  html += '<div class="gantt-header flex gap-1 px-2">';
  html += '<div class="w-24 font-medium text-slate-500">Cultura</div>';
  months.forEach(function (m) {
    html +=
      '<div class="flex-1 text-center text-xs text-slate-400 border-l border-slate-200 dark:border-slate-700">' +
      m +
      '</div>';
  });
  html += '</div>';
  // Rows
  safras.slice(0, 15).forEach(function (s) {
    var plantio = s.data_plantio ? new Date(s.data_plantio) : null;
    var colheita = s.data_colheita ? new Date(s.data_colheita) : null;
    var startMonth = plantio ? plantio.getMonth() : 0;
    var endMonth = colheita ? colheita.getMonth() : 11;
    if (endMonth < startMonth) endMonth = startMonth + 12;
    var widthPct = ((endMonth - startMonth + 1) / 12) * 100;
    var leftPct = (startMonth / 12) * 100;
    html +=
      '<div class="gantt-row flex gap-1 px-2 py-1 border-t border-slate-100 dark:border-slate-800 items-center">';
    html +=
      '<div class="w-24 truncate text-slate-700 dark:text-slate-300">' +
      (s.cultura || '—') +
      ' ' +
      (s.ano || '') +
      '</div>';
    html += '<div class="flex-1 relative h-5">';
    html +=
      '<div class="absolute h-full rounded bg-emerald-500/60" style="left:' +
      leftPct +
      '%;width:' +
      widthPct +
      '%;"></div>';
    if (plantio)
      html +=
        '<div class="absolute top-0 w-1 h-1 bg-emerald-700" style="left:' +
        (startMonth / 12) * 100 +
        '%;" title="Plantio: ' +
        plantio.toLocaleDateString() +
        '"></div>';
    if (colheita)
      html +=
        '<div class="absolute top-0 w-1 h-1 bg-amber-600" style="left:' +
        (endMonth / 12) * 100 +
        '%;" title="Colheita: ' +
        colheita.toLocaleDateString() +
        '"></div>';
    html += '</div></div>';
  });
  if (!safras.length)
    html += '<div class="text-slate-400 text-center py-4 text-xs">Nenhuma safra cadastrada</div>';
  html += '</div>';
  container.innerHTML = html;
  window._ganttInitialized[widgetId] = true;
}

// ============================================
// CLIMA REAL WIDGET
// ============================================
window._climaInitialized = {};

function initClimaWidget(widgetId, container) {
  function renderClimaData(data) {
    var atual = (data && data.atual) || {};
    var prev = (data && data.previsao) || [];
    var fonte = (data && data.fonte) || '';
    var fonteLabel =
      {
        inmet: 'INMET',
        openweathermap: 'OpenWeatherMap',
        'open-meteo': 'Open-Meteo',
        sem_fonte: 'Sem fonte',
        simulado: 'Simulado',
      }[fonte] ||
      fonte ||
      '';
    var html = '<div class="flex flex-col h-full min-w-0">';
    html += '<div class="flex items-center justify-between gap-1 mb-1 shrink-0">';
    html +=
      '<span class="text-[10px] text-slate-400 truncate">' +
      ((data && data.cidade) || '') +
      '</span>';
    if (fonteLabel)
      html +=
        '<span class="text-[8px] uppercase font-semibold tracking-wide text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-900/40 rounded px-1.5 py-0.5 shrink-0">' +
        fonteLabel +
        '</span>';
    html += '</div>';
    if (atual && atual.temp != null) {
      html += '<div class="flex items-center gap-3 shrink-0">';
      html += '<i class="bi ' + (atual.icone || 'bi-sun') + ' text-4xl text-amber-400"></i>';
      html +=
        '<div class="leading-tight min-w-0"><div class="text-3xl font-bold">' +
        atual.temp +
        '°C</div><div class="text-[11px] text-slate-500 truncate">' +
        (atual.descricao || '') +
        '</div></div>';
      html +=
        '<div class="ml-auto text-right shrink-0"><div class="text-[10px] text-slate-400">Umidade</div><div class="text-sm font-semibold">' +
        (atual.umidade != null ? atual.umidade + '%' : '---') +
        '</div></div>';
      html += '</div>';
    }
    if (prev.length) {
      html += '<div class="flex-1 min-h-0 overflow-auto mt-1">';
      prev.forEach(function (p, i) {
        var isHoje = i === 0 || (p.dia || '').toLowerCase() === 'hoje';
        html +=
          '<div class="py-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2">';
        html += '<span class="font-medium text-[11px] truncate">' + (p.dia || '') + '</span>';
        html +=
          '<span class="flex items-center gap-1 text-[11px] shrink-0"><i class="bi ' +
          (p.icone || 'bi-cloud') +
          ' text-amber-500"></i>' +
          (p.temp != null ? p.temp + '°C' : '---') +
          '</span>';
        html +=
          '<span class="text-[10px] text-slate-400 shrink-0">' +
          (p.umidade != null ? p.umidade + '%' : '') +
          '</span>';
        html +=
          '<span class="text-[10px] text-slate-500 hidden sm:inline truncate max-w-[120px]">' +
          (p.descricao || '') +
          '</span>';
        html += '</div>';
      });
      html += '</div>';
    } else if (!atual || atual.temp == null) {
      // O servidor diz PORQUÊ não há temperatura (`motivo`), e
      // dizer "indisponíveis" deixava o produtor a concluir que o
      // sensor avariou. São coisas diferentes: uma fonte que não
      // respondeu pede-lhe uma ação, um sensor morto pede-lhe
      // outra.
      //
      // O `motivo` vem do próprio servidor (nome da propriedade
      // e da fonte), mas é texto e entra em `innerHTML` — então
      // é escapado aqui. `esc` serve, mas está definido mais
      // abaixo no ficheiro e o seu valor ainda é `undefined`
      // quando este bloco corre; daí o escape local.
      var _motivo = (data && data.motivo) || 'Dados de clima indisponíveis';
      html +=
        '<div class="text-slate-400 text-xs py-4 text-center">' +
        String(_motivo)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;') +
        '</div>';
    }
    html += '</div>';
    container.innerHTML = html;
  }

  var weather = (widgetDataCache || {}).weather;
  if (weather) {
    renderClimaData(weather);
    window._climaInitialized[widgetId] = true;
    return;
  }
  // Fallback: busca direta no endpoint
  fetch('/api/weather/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      renderClimaData(data);
    })
    .catch(function () {
      container.innerHTML =
        '<div class="text-slate-400 text-xs text-center py-4">Erro ao carregar clima</div>';
    });
  window._climaInitialized[widgetId] = true;
}

// ============================================
// IOT SENSORS WIDGET
// ============================================
window._iotInitialized = {};

function initIotWidget(widgetId, container) {
  var w = widgetDataCache;
  var estacoes = w && w.estacoes ? w.estacoes : [];
  var leituras = w && w.leituras ? w.leituras : [];
  // Mock: fetch from API
  fetch('/api/leituras-sensor/')
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      var html = '<div class="space-y-2 text-xs">';
      if (data && data.length) {
        data.slice(0, 10).forEach(function (l) {
          html +=
            '<div class="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">';
          html += '<span class="text-slate-600 dark:text-slate-300">' + l.tipo + '</span>';
          html += '<span class="font-mono font-medium">' + l.valor + ' ' + l.unidade + '</span>';
          html += '</div>';
        });
      } else {
        html += '<div class="text-slate-400 text-center py-2">Nenhum sensor configurado</div>';
      }
      html += '</div>';
      container.innerHTML = html;
    })
    .catch(function () {
      container.innerHTML =
        '<div class="text-slate-400 text-xs text-center py-4">Erro ao carregar sensores</div>';
    });
  window._iotInitialized[widgetId] = true;
}

// ============================================
// COMPARATIVO CULTURAS WIDGET
// ============================================
function initComparativoWidget(widgetId, ctx) {
  var w = widgetDataCache;
  var safras = w && w.safras && w.safras.items ? w.safras.items : [];
  var culturas = [
    ...new Set(
      safras
        .map(function (s) {
          return s.cultura;
        })
        .filter(Boolean)
    ),
  ];
  var select1 = document.getElementById('cmp-cultura1-' + widgetId);
  var select2 = document.getElementById('cmp-cultura2-' + widgetId);
  if (select1) {
    select1.innerHTML =
      '<option value="">Selecione</option>' +
      culturas
        .map(function (c) {
          return '<option value="' + c + '">' + c + '</option>';
        })
        .join('');
  }
  if (select2) {
    select2.innerHTML =
      '<option value="">Selecione</option>' +
      culturas
        .map(function (c) {
          return '<option value="' + c + '">' + c + '</option>';
        })
        .join('');
  }
  function updateChart() {
    var c1 = select1 ? select1.value : '';
    var c2 = select2 ? select2.value : '';
    var d1 = safras.filter(function (s) {
      return s.cultura === c1;
    });
    var d2 = safras.filter(function (s) {
      return s.cultura === c2;
    });
    var labels = [
      ...new Set(
        [...d1, ...d2].map(function (s) {
          return s.ano;
        })
      ),
    ].sort();
    var data1 = labels.map(function (y) {
      var s = d1.find(function (x) {
        return x.ano === y;
      });
      return s ? s.producao : 0;
    });
    var data2 = labels.map(function (y) {
      var s = d2.find(function (x) {
        return x.ano === y;
      });
      return s ? s.producao : 0;
    });
    if (chartInstances[ctx.id]) chartInstances[ctx.id].destroy();
    var cmpPal = chartPalette();
    chartInstances[ctx.id] = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: c1, data: data1, backgroundColor: cmpPal.accentBar },
          { label: c2, data: data2, backgroundColor: 'rgba(245,158,11,0.7)' },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false, axis: 'x' },
        plugins: {
          legend: {
            display: true,
            position: 'bottom',
            labels: {
              boxWidth: 20,
              padding: 10,
              font: { size: 11 },
              usePointStyle: true,
              pointStyle: 'line',
              color: cmpPal.tick,
            },
          },
          tooltip: { enabled: false },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: {
              font: { size: 9 },
              maxRotation: 0,
              autoSkip: true,
              padding: 4,
              color: cmpPal.tick,
            },
          },
          y: {
            grid: { display: false },
            border: { display: false },
            ticks: { font: { size: 9 }, padding: 4, color: cmpPal.tick },
          },
        },
        layout: { padding: { top: 24, bottom: 4, left: 2, right: 2 } },
      },
    });
    watchChartResize(ctx);
    ctx.classList.add('reveal-chart');
  }
  if (select1) select1.addEventListener('change', updateChart);
  if (select2) select2.addEventListener('change', updateChart);
  updateChart();
}

// ============================================
// COLLISION DETECTION - Grid position helpers
// ============================================
// COLLISION DETECTION - Grid position helpers
// ============================================
window.findFreePosition = function (w, h) {
  for (var y = 0; y < GRID_ROWS; y++) {
    for (var x = 0; x < GRID_COLS; x++) {
      if (!checkCollision(x, y, w, h)) {
        return { x: x, y: y };
      }
    }
  }
  return null;
};

window.checkCollision = function (x, y, w, h, skipId) {
  if (x < 0 || y < 0 || x + w > GRID_COLS || y + h > GRID_ROWS) return true;
  for (var id in widgets) {
    if (!widgets.hasOwnProperty(id)) continue;
    if (id === skipId || !widgets[id].visible) continue;
    var cfg = widgets[id];
    if (!(
      x + w <= cfg.gridX ||
      x >= cfg.gridX + cfg.gridW ||
      y + h <= cfg.gridY ||
      y >= cfg.gridY + cfg.gridH
    )) {
      return true;
    }
  }
  return false;
};

// ============================================
// DRAG AND DROP - Custom mouse-based smooth drag (NO HTML5 native drag)
// ============================================
// HTML5 native drag (draggable=true) is DISABLED because it conflicts with
// our custom mousedown/mousemove/mouseup system, causing:
//   1. Widget ghost cloning by the browser
//   2. Drag freezing when both systems fight for control
// Only custom mouse/touch events are used below.
// ============================================
var _dragState = {
  active: false,
  widgetId: null,
  startX: 0,
  startY: 0,
  origX: 0,
  origY: 0,
  ghost: null,
};

window.initWidgetDragging = function () {
  // SPA navegacao recria .matrix-container -> invalida cache do container antigo (detached causa teleport)
  _matrixContainer = null;
  // Remove old listeners from all previously-attached elements
  document.querySelectorAll('[data-drag-init]').forEach(function (el) {
    el.removeEventListener('mousedown', el._onMouseDown);
    el.removeEventListener('touchstart', el._onTouchStart);
    el.removeAttribute('data-drag-init');
  });

  // Remove old document-level listeners
  document.removeEventListener('mousemove', _onMouseMove);
  document.removeEventListener('mouseup', _onMouseUp);
  document.removeEventListener('touchmove', _onTouchMove);
  document.removeEventListener('touchend', _onTouchEnd);

  // Mouse-based smooth drag for all widgets in edit mode
  document.querySelectorAll('.bento-block.widget-edit-mode').forEach(function (el) {
    el._onMouseDown = function (e) {
      _startMouseDrag(e, el);
    };
    el._onTouchStart = function (e) {
      _startTouchDrag(e, el);
    };
    el.addEventListener('mousedown', el._onMouseDown);
    el.addEventListener('touchstart', el._onTouchStart, { passive: false });
    el.setAttribute('data-drag-init', '1');
  });
};

function _startMouseDrag(e, el) {
  if (!widgetEditMode && !customMode) return;
  if (e.button !== 0) return;
  if (
    e.target.closest('.remove-widget-btn') ||
    e.target.closest('.resize-handle') ||
    e.target.closest('.edit-mode-badge')
  )
    return;
  var wId = el.id.replace('widget-', '');
  if (!widgets[wId]) return;
  e.preventDefault();

  // Seleciona o widget ao clicar
  document.querySelectorAll('.bento-block.widget-selected').forEach(function (b) {
    b.classList.remove('widget-selected');
  });
  el.classList.add('widget-selected');
  _selectedWidgetId = wId;
  updateValuesList(wId);

  // Guardar offset do clique dentro do widget para drag suave
  var elRect = el.getBoundingClientRect();
  _dragState.active = true;
  _dragState.widgetId = wId;
  _dragState.startX = e.clientX;
  _dragState.startY = e.clientY;
  _dragState.origX = widgets[wId].gridX;
  _dragState.origY = widgets[wId].gridY;
  _dragState.clickOffsetX = e.clientX - elRect.left;
  _dragState.clickOffsetY = e.clientY - elRect.top;
  _dragState._pendingX = e.clientX;
  _dragState._pendingY = e.clientY;
  _dragState._rafPending = false;

  el.classList.add('drag-origin');
  el.style.transition = 'none';

  // Create ghost element
  var ghost = el.cloneNode(true);
  ghost.className = 'bento-block drag-ghost';
  ghost.style.width = el.offsetWidth + 'px';
  ghost.style.height = el.offsetHeight + 'px';
  ghost.style.left = e.clientX - _dragState.clickOffsetX + 'px';
  ghost.style.top = e.clientY - _dragState.clickOffsetY + 'px';
  ghost.style.pointerEvents = 'none';
  ghost.style.zIndex = '2147483647';
  document.body.appendChild(ghost);
  _dragState.ghost = ghost;

  document.addEventListener('mousemove', _onMouseMove);
  document.addEventListener('mouseup', _onMouseUp);
}

function _startTouchDrag(e, el) {
  if (!widgetEditMode && !customMode) return;
  e.preventDefault();
  var touch = e.touches[0];
  var wId = el.id.replace('widget-', '');
  if (!widgets[wId]) return;

  document.querySelectorAll('.bento-block.widget-selected').forEach(function (b) {
    b.classList.remove('widget-selected');
  });
  el.classList.add('widget-selected');
  _selectedWidgetId = wId;
  updateValuesList(wId);

  // Guardar offset do toque dentro do widget para drag suave
  var elRect = el.getBoundingClientRect();
  _dragState.active = true;
  _dragState.widgetId = wId;
  _dragState.startX = touch.clientX;
  _dragState.startY = touch.clientY;
  _dragState.origX = widgets[wId].gridX;
  _dragState.origY = widgets[wId].gridY;
  _dragState.clickOffsetX = touch.clientX - elRect.left;
  _dragState.clickOffsetY = touch.clientY - elRect.top;
  _dragState._pendingX = touch.clientX;
  _dragState._pendingY = touch.clientY;
  _dragState._rafPending = false;

  el.classList.add('drag-origin');
  el.style.transition = 'none';

  var ghost = el.cloneNode(true);
  ghost.className = 'bento-block drag-ghost';
  ghost.style.width = el.offsetWidth + 'px';
  ghost.style.height = el.offsetHeight + 'px';
  ghost.style.left = touch.clientX - _dragState.clickOffsetX + 'px';
  ghost.style.top = touch.clientY - _dragState.clickOffsetY + 'px';
  ghost.style.pointerEvents = 'none';
  ghost.style.zIndex = '2147483647';
  document.body.appendChild(ghost);
  _dragState.ghost = ghost;

  document.addEventListener('touchmove', _onTouchMove, { passive: false });
  document.addEventListener('touchend', _onTouchEnd);
}

function _onMouseMove(e) {
  if (!_dragState.active) return;
  e.preventDefault();
  _updateDrag(e.clientX, e.clientY);
}

function _onTouchMove(e) {
  if (!_dragState.active) return;
  e.preventDefault();
  var touch = e.touches[0];
  _updateDrag(touch.clientX, touch.clientY);
}

var _matrixContainer = null;
// Invalida cache quando SPA troca de pagina (matrix-container antigo fica detached)
window._resetMatrixContainerCache = function () {
  _matrixContainer = null;
};
function _updateDrag(clientX, clientY) {
  if (!_dragState.active) return;
  // Synchronous update for correctness (rAF throttling broke hint in headless)
  _doUpdateDrag(clientX, clientY);
}

function _doUpdateDrag(clientX, clientY) {
  if (_dragState.ghost) {
    _dragState.ghost.style.left = clientX - _dragState.clickOffsetX + 'px';
    _dragState.ghost.style.top = clientY - _dragState.clickOffsetY + 'px';
  }

  var container =
    _matrixContainer && _matrixContainer.isConnected
      ? _matrixContainer
      : document.querySelector('.matrix-container');
  if (!container) return;
  _matrixContainer = container;
  var rect = container.getBoundingClientRect();
  var style = window.getComputedStyle(container);
  var actPad = parseFloat(style.paddingLeft) || GRID_PAD;
  var actGap = parseFloat(style.columnGap) || parseFloat(style.gap) || GRID_GAP;
  var cellW = (rect.width - 2 * actPad - (GRID_COLS - 1) * actGap) / GRID_COLS;
  var cellH = (rect.height - 2 * actPad - (GRID_ROWS - 1) * actGap) / GRID_ROWS;
  var cfg = widgets[_dragState.widgetId];
  if (!cfg) return;
  var relX = clientX - rect.left - actPad - _dragState.clickOffsetX;
  var relY = clientY - rect.top - actPad - _dragState.clickOffsetY;
  var col = Math.round(relX / (cellW + actGap));
  var row = Math.round(relY / (cellH + actGap));
  col = Math.max(0, Math.min(GRID_COLS - 1, col));
  row = Math.max(0, Math.min(GRID_ROWS - 1, row));

  col = Math.max(0, Math.min(GRID_COLS - cfg.gridW, col));
  row = Math.max(0, Math.min(GRID_ROWS - cfg.gridH, row));

  var isValid = !checkCollision(col, row, cfg.gridW, cfg.gridH, _dragState.widgetId);
  var el = document.getElementById('widget-' + _dragState.widgetId);
  if (el) {
    el.classList.toggle('drop-target', isValid);
    el.classList.toggle('drop-target-invalid', !isValid);
    // Sempre move visualmente durante o drag (passa por cima de outros widgets)
    // A validacao de colisao ocorre apenas no _finalizeDrag
    el.style.gridColumn = col + 1 + ' / span ' + cfg.gridW;
    el.style.gridRow = row + 1 + ' / span ' + cfg.gridH;
  }

  var hint = container.querySelector('.grid-drop-hint');
  if (!hint) {
    hint = document.createElement('div');
    hint.className = 'grid-drop-hint';
    hint.style.pointerEvents = 'none';
    container.appendChild(hint);
  }
  hint.textContent = 'Pos: ' + (col + 1) + ', ' + (row + 1);
  hint.classList.toggle('invalid', !isValid);
  hint.style.left = actPad + col * (cellW + actGap) + 'px';
  hint.style.top = actPad + row * (cellH + actGap) + 'px';
  hint.style.pointerEvents = 'none';

  _dragState.pendingCol = col;
  _dragState.pendingRow = row;
  _dragState.isValid = isValid;
} // end _doUpdateDrag

function _onMouseUp(e) {
  if (!_dragState.active) return;
  document.removeEventListener('mousemove', _onMouseMove);
  document.removeEventListener('mouseup', _onMouseUp);
  // Also remove resize listeners to prevent stuck behavior
  document.removeEventListener('mousemove', _onResizeMove);
  document.removeEventListener('mouseup', _onResizeEnd);
  _resizeState.active = false;
  _finalizeDrag();
}

function _onTouchEnd(e) {
  if (!_dragState.active) return;
  document.removeEventListener('touchmove', _onTouchMove);
  document.removeEventListener('touchend', _onTouchEnd);
  // Also remove resize listeners to prevent stuck behavior
  document.removeEventListener('mousemove', _onResizeMove);
  document.removeEventListener('mouseup', _onResizeEnd);
  _resizeState.active = false;
  _finalizeDrag();
}

function _finalizeDrag() {
  var wId = _dragState.widgetId;
  if (!wId || !widgets[wId]) {
    _cleanupDrag();
    return;
  }

  var col = _dragState.pendingCol;
  var row = _dragState.pendingRow;
  var origX = _dragState.origX,
    origY = _dragState.origY;

  var moved = col !== undefined && row !== undefined && _dragState.isValid;
  if (moved) {
    widgets[wId].gridX = col;
    widgets[wId].gridY = row;
    saveWidgetsLayout();
    _cleanupDrag();
  } else {
    _cleanupDrag();
    if (col !== undefined && row !== undefined) {
      // Drop invalido (colisao) — snap de volta com animacao
      var el = document.getElementById('widget-' + wId);
      if (el) {
        el.style.transition = 'grid-column 0.2s, grid-row 0.2s';
        el.style.gridColumn = origX + 1 + ' / span ' + widgets[wId].gridW;
        el.style.gridRow = origY + 1 + ' / span ' + widgets[wId].gridH;
        setTimeout(function () {
          if (el) el.style.transition = '';
        }, 250);
      }
    }
  }
}

function _cleanupDrag() {
  if (_dragState.ghost) {
    _dragState.ghost.remove();
    _dragState.ghost = null;
  }
  var dragEl = document.getElementById('widget-' + _dragState.widgetId);
  if (dragEl) {
    dragEl.style.transition = '';
    dragEl.classList.remove('drag-origin', 'drop-target', 'drop-target-invalid');
  }
  document.querySelectorAll('.grid-drop-hint').forEach(function (el) {
    el.remove();
  });
  _dragState.active = false;
  _dragState.widgetId = null;
  _dragState.pendingCol = undefined;
  _dragState.pendingRow = undefined;
  _dragState.isValid = false;
}

// ============================================
// RESIZE HANDLER - Drag-to-resize widgets
// ============================================
var _resizeState = {
  active: false,
  widgetId: null,
  dir: null,
  startX: 0,
  startY: 0,
  origW: 0,
  origH: 0,
  origX: 0,
  origY: 0,
};

window.startResize = function (e, widgetId, dir) {
  if (!widgetEditMode && !customMode) return;
  e.preventDefault();
  var cfg = widgets[widgetId];
  if (!cfg) return;

  // Select the widget on resize handle click
  var el = document.getElementById('widget-' + widgetId);
  if (el) {
    document.querySelectorAll('.bento-block.widget-selected').forEach(function (b) {
      b.classList.remove('widget-selected');
    });
    el.classList.add('widget-selected');
    _selectedWidgetId = widgetId;
    updateValuesList(widgetId);
  }

  _resizeState.active = true;
  _resizeState.widgetId = widgetId;
  _resizeState.dir = dir;
  _resizeState.startX = e.clientX;
  _resizeState.startY = e.clientY;
  _resizeState.origW = cfg.gridW;
  _resizeState.origH = cfg.gridH;
  _resizeState.origX = cfg.gridX;
  _resizeState.origY = cfg.gridY;

  document.addEventListener('mousemove', _onResizeMove);
  document.addEventListener('mouseup', _onResizeEnd);
};

function _onResizeMove(e) {
  if (!_resizeState.active) return;

  // Throttle with rAF
  if (_resizeState._rafPending) return;
  _resizeState._rafPending = true;

  requestAnimationFrame(function () {
    _resizeState._rafPending = false;
    _doResizeMove(e);
  });
}

function _doResizeMove(e) {
  if (!_resizeState.active) return;
  e.preventDefault();
  var container = document.querySelector('.matrix-container');
  if (!container) return;
  var rect = container.getBoundingClientRect();
  var style = window.getComputedStyle(container);
  var actPad = parseFloat(style.paddingLeft) || GRID_PAD;
  var actGap = parseFloat(style.columnGap) || parseFloat(style.gap) || GRID_GAP;
  var cellW = (rect.width - 2 * actPad - (GRID_COLS - 1) * actGap) / GRID_COLS;
  var cellH = (rect.height - 2 * actPad - (GRID_ROWS - 1) * actGap) / GRID_ROWS;

  var dCols = Math.round((e.clientX - _resizeState.startX) / (cellW + actGap));
  var dRows = Math.round((e.clientY - _resizeState.startY) / (cellH + actGap));
  var dir = _resizeState.dir;
  var cfg = widgets[_resizeState.widgetId];
  if (!cfg) return;

  var newX = _resizeState.origX;
  var newY = _resizeState.origY;
  var newW = _resizeState.origW;
  var newH = _resizeState.origH;

  // Face/borda direita: a largura acompanha o cursor
  if (dir.indexOf('e') >= 0) {
    newW = _resizeState.origW + dCols;
  }
  // Face/borda esquerda: a borda acompanha o cursor, movendo a origem
  if (dir.indexOf('w') >= 0) {
    newW = _resizeState.origW - dCols;
    newX = _resizeState.origX + dCols;
  }
  // Base: a altura acompanha o cursor
  if (dir.indexOf('s') >= 0) {
    newH = _resizeState.origH + dRows;
  }
  // Topo: a borda acompanha o cursor, movendo a origem
  if (dir.indexOf('n') >= 0) {
    newH = _resizeState.origH - dRows;
    newY = _resizeState.origY + dRows;
  }

  // Tamanho minimo
  if (newW < 2) newW = 2;
  if (newH < 2) newH = 2;

  // Naozar entradas fora dos limites do grid
  if (newX < 0) {
    newW -= -newX;
    newX = 0;
  }
  if (newY < 0) {
    newH -= -newY;
    newY = 0;
  }
  if (newX + newW > GRID_COLS) newW = GRID_COLS - newX;
  if (newY + newH > GRID_ROWS) newH = GRID_ROWS - newY;
  if (newW < 2 || newH < 2) return;

  // Verificar colisao com outros widgets
  var resizeOk =
    newX + newW <= GRID_COLS &&
    newY + newH <= GRID_ROWS &&
    !checkCollision(newX, newY, newW, newH, _resizeState.widgetId);
  var el = document.getElementById('widget-' + _resizeState.widgetId);
  if (el) el.classList.toggle('resize-blocked', !resizeOk);
  if (resizeOk) {
    cfg.gridX = newX;
    cfg.gridY = newY;
    cfg.gridW = newW;
    cfg.gridH = newH;
    if (el) {
      el.style.gridColumn = newX + 1 + ' / span ' + newW;
      el.style.gridRow = newY + 1 + ' / span ' + newH;
    }
  }
}

function _onResizeEnd(e) {
  if (!_resizeState.active) return;
  document.removeEventListener('mousemove', _onResizeMove);
  document.removeEventListener('mouseup', _onResizeEnd);
  var resizedId = _resizeState.widgetId;
  var rEl = document.getElementById('widget-' + resizedId);
  if (rEl) {
    rEl.classList.remove('resize-blocked');
    rEl.querySelectorAll('canvas[id^="chart-"]').forEach(function (c) {
      var inst = chartInstances[c.id];
      if (inst && typeof inst.resize === 'function') inst.resize();
    });
  }
  _resizeState.active = false;
  saveWidgetsLayout();
}

// ============================================
// EDIT MODE FUNCTIONS - Novos botoes de edicao
// ============================================
var _selectedWidgetId = null;

// Selecionar widget ao clicar ou segurar no modo edicao — cor de fundo e edicao funcionam no selecionado
function _isEditModeActive() {
  return !!(
    window.widgetEditMode ||
    window.customMode ||
    (window.widgetbarState && window.widgetbarState.isCustomMode) ||
    (typeof widgetEditMode !== 'undefined' && widgetEditMode) ||
    (typeof customMode !== 'undefined' && customMode) ||
    document.querySelector('.matrix-container.editing') ||
    document.getElementById('dashboard-appbar')?.classList.contains('editing')
  );
}
function _selectWidgetBlock(block) {
  if (!block) return;
  var wId = block.id.replace('widget-', '');
  document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
    el.classList.remove('widget-selected');
  });
  block.classList.add('widget-selected');
  try {
    _selectedWidgetId = wId;
  } catch (e) {}
  try {
    window._selectedWidgetId = wId;
  } catch (e) {}
  if (typeof updateValuesList === 'function') updateValuesList(wId);
  if (typeof window.updateWidgetBarSelectionIndicator === 'function')
    window.updateWidgetBarSelectionIndicator();
  if (typeof window._captureBgOriginal === 'function')
    try {
      window._captureBgOriginal();
    } catch (e) {}
  var editBtn = document.getElementById('edit-selected-btn');
  if (editBtn) editBtn.classList.toggle('opacity-50', !wId);
}
document.addEventListener('click', function (e) {
  if (!_isEditModeActive()) return;
  if (e.target.closest('.resize-handle') || e.target.closest('.edit-mode-badge')) return;
  var block = e.target.closest('.bento-block');
  if (block) {
    _selectWidgetBlock(block);
  }
  // Clique fora NÃO desseleciona — fica selecionado até sair do modo edição ou selecionar outro widget (via _selectWidgetBlock) ou clicar no X do centro
});
// pointerdown/mousedown garante selecao mesmo quando o drag faz preventDefault e o click nao dispara
document.addEventListener('pointerdown', function (e) {
  if (!_isEditModeActive()) return;
  if (e.target.closest('.resize-handle') || e.target.closest('.edit-mode-badge')) return;
  var block = e.target.closest('.bento-block');
  if (block) {
    // Seleciona imediatamente ao pressionar/segurar
    _selectWidgetBlock(block);
  }
});
document.addEventListener('mousedown', function (e) {
  if (!_isEditModeActive()) return;
  if (e.target.closest('.resize-handle') || e.target.closest('.edit-mode-badge')) return;
  var block = e.target.closest('.bento-block');
  if (block) {
    // Fallback para browsers sem pointerdown — seleciona mesmo se já houver outro selecionado
    _selectWidgetBlock(block);
  }
});
// Duplo clique em widget no modo edicao abre direto o painel de edicao com todas as variaveis/metas/cores
document.addEventListener('dblclick', function (e) {
  if (!widgetEditMode && !customMode) return;
  var block = e.target.closest('.bento-block');
  if (!block) return;
  e.preventDefault();
  var wId = block.id.replace('widget-', '');
  document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
    el.classList.remove('widget-selected');
  });
  block.classList.add('widget-selected');
  _selectedWidgetId = wId;
  updateValuesList(wId);
  if (typeof window.updateWidgetBarSelectionIndicator === 'function')
    window.updateWidgetBarSelectionIndicator();
  if (typeof window.openEditSelectedWidget === 'function') window.openEditSelectedWidget();
});
// Patch: garante persistência mesmo com dashboard-desktop.js cacheado antigo que remove widget-selected ao clicar fora
document.addEventListener('click', function (e) {
  setTimeout(function () {
    if (!_isEditModeActive()) return;
    var wId = null;
    try {
      wId = eval('_selectedWidgetId');
    } catch (err) {}
    if (!wId) return;
    var block = document.getElementById('widget-' + wId);
    if (block && !block.classList.contains('widget-selected')) {
      document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
        el.classList.remove('widget-selected');
      });
      block.classList.add('widget-selected');
      if (typeof window.updateWidgetBarSelectionIndicator === 'function')
        try {
          window.updateWidgetBarSelectionIndicator();
        } catch (err) {}
    }
  }, 0);
});

// Indicador central da widget-bar: mostra qual widget esta selecionado (só em modo edição)
window.updateWidgetBarSelectionIndicator = function () {
  var ind = document.getElementById('widgetbar-selection-indicator');
  var txt = document.getElementById('widgetbar-selection-text');
  if (!ind || !txt) return;
  var isEdit = !!(
    window.widgetEditMode ||
    window.customMode ||
    (window.widgetbarState && window.widgetbarState.isCustomMode)
  );
  if (!isEdit) {
    ind.classList.add('hidden');
    return;
  }
  ind.classList.remove('hidden');
  var wId =
    typeof _selectedWidgetId !== 'undefined' && _selectedWidgetId ? _selectedWidgetId : null;
  if (!wId || !window.widgets || !window.widgets[wId]) {
    txt.textContent = 'Nenhum selecionado';
    txt.removeAttribute('title');
    ind.style.opacity = '0.6';
    try {
      if (typeof window.syncWidgetFontField === 'function') window.syncWidgetFontField();
    } catch (e) {}
    return;
  }
  var cfg = window.widgets[wId];
  var title = cfg && (cfg.title || cfg.label) ? cfg.title || cfg.label : wId;
  // Para _mercado/_producao, usa título já formatado com cultura
  if (wId.indexOf('_mercado_') >= 0 || wId.indexOf('_producao_') >= 0) {
    // Título já vem como "Valor da Produção" etc, tenta pegar do DOM também
    var el = document.getElementById('widget-' + wId);
    var domTitle = el
      ? (el.querySelector('.widget-content .text-\\[10px\\]')?.textContent || '').trim()
      : '';
    if (domTitle) title = domTitle;
  } else if (wId.indexOf('cultura-') === 0 || wId.indexOf('cult-') === 0) {
    var cEl = document.getElementById('widget-' + wId);
    var cDom = cEl ? (cEl.querySelector('.text-\\[11px\\]')?.textContent || '').trim() : '';
    if (cDom) title = cDom;
  }
  txt.textContent = title;
  txt.title = wId;
  ind.style.opacity = '1';
  ind.classList.remove('hidden');
  try {
    if (typeof window.syncWidgetFontField === 'function') window.syncWidgetFontField();
  } catch (e) {}
};
window.clearWidgetSelection = function () {
  document.querySelectorAll('.bento-block.widget-selected').forEach(function (el) {
    el.classList.remove('widget-selected');
  });
  try {
    _selectedWidgetId = null;
  } catch (e) {}
  try {
    window._selectedWidgetId = null;
  } catch (e) {}
  if (typeof updateValuesList === 'function') updateValuesList(null);
  if (typeof window.updateWidgetBarSelectionIndicator === 'function')
    window.updateWidgetBarSelectionIndicator();
};
// Atualiza indicador quando a seleção muda
var _origUpdateValuesList = window.updateValuesList;
// Hook para manter indicador sincronizado com qualquer updateValuesList
var _prevUpdateValuesList = window.updateValuesList;
window.updateValuesList = function (wId) {
  if (typeof _prevUpdateValuesList === 'function')
    try {
      _prevUpdateValuesList.apply(this, arguments);
    } catch (e) {}
  if (typeof window.updateWidgetBarSelectionIndicator === 'function')
    window.updateWidgetBarSelectionIndicator();
};

window.toggleEditDropdown = function (id) {
  var dropdown = document.getElementById(id);
  if (!dropdown) return;
  var isOpen = dropdown.classList.contains('open');
  document.querySelectorAll('.edit-dropdown').forEach(function (d) {
    d.classList.remove('open');
    d.classList.add('hidden');
    // Limpa centralização de qualquer bg anterior
    if (d.id === 'bg-color-dropdown') {
      d.style.removeProperty('position');
      d.style.removeProperty('top');
      d.style.removeProperty('left');
      d.style.removeProperty('bottom');
      d.style.removeProperty('right');
      d.style.removeProperty('transform');
      d.style.removeProperty('margin');
      d.style.removeProperty('z-index');
      if (d._originalParent && d.id === 'font-size-dropdown') {
        try {
          if (d._originalNext && d._originalNext.parentElement === d._originalParent) {
            d._originalParent.insertBefore(d, d._originalNext);
          } else {
            d._originalParent.appendChild(d);
          }
        } catch (e) {}
        d._originalParent = null;
        d._originalNext = null;
      }
      if (d._originalParent) {
        try {
          if (d._originalNext && d._originalNext.parentElement === d._originalParent) {
            d._originalParent.insertBefore(d, d._originalNext);
          } else {
            d._originalParent.appendChild(d);
          }
        } catch (e) {}
        d._originalParent = null;
        d._originalNext = null;
      }
    }
  });
  document.body.classList.remove('bg-dropdown-open');
  if (!isOpen) {
    dropdown.classList.remove('hidden');
    dropdown.classList.add('open');
    if (id === 'font-size-dropdown') {
      if (!dropdown._originalParent) {
        dropdown._originalParent = dropdown.parentElement;
        dropdown._originalNext = dropdown.nextSibling;
      }
      document.body.appendChild(dropdown);
    }
    if (id === 'bg-color-dropdown') {
      document.body.classList.add('bg-dropdown-open');
      // Captura cor original do widget selecionado para preview/reverter
      if (typeof window._captureBgOriginal === 'function')
        try {
          window._captureBgOriginal();
        } catch (e) {}
      // Auto-seleciona primeiro widget se nenhum selecionado (fix botão cor não funcionar)
      if (!window._selectedWidgetId && !window._selectedWidgetId) {
        var firstBlock = document.querySelector('.bento-block');
        if (firstBlock && typeof _selectWidgetBlock === 'function')
          try {
            _selectWidgetBlock(firstBlock);
          } catch (e) {}
      }
      // Move para body para centralizar perfeitamente (escapa do relative parent)
      if (dropdown.parentElement !== document.body) {
        dropdown._originalParent = dropdown.parentElement;
        dropdown._originalNext = dropdown.nextSibling;
        document.body.appendChild(dropdown);
      }
      dropdown.style.setProperty('position', 'fixed', 'important');
      dropdown.style.setProperty('top', '50%', 'important');
      dropdown.style.setProperty('left', '50%', 'important');
      dropdown.style.setProperty('bottom', 'auto', 'important');
      dropdown.style.setProperty('right', 'auto', 'important');
      dropdown.style.setProperty('transform', 'translate(-50%, -50%) scale(0.96)', 'important');
      dropdown.style.setProperty('margin', '0', 'important');
      dropdown.style.setProperty('z-index', '1000', 'important');
      setTimeout(function () {
        dropdown.style.setProperty('transform', 'translate(-50%, -50%) scale(1)', 'important');
      }, 10);
    } else if (id === 'font-size-dropdown') {
      // Captura tamanho original e sincroniza inputs (fix botão texto não funcionar)
      if (typeof window._captureFontOriginal === 'function')
        try {
          window._captureFontOriginal();
        } catch (e) {}
      else if (typeof window.syncWidgetFontField === 'function')
        try {
          window.syncWidgetFontField();
        } catch (e) {}
      // Auto-seleciona primeiro widget se nenhum selecionado
      if (!window._selectedWidgetId) {
        var fb = document.querySelector('.bento-block');
        if (fb && typeof _selectWidgetBlock === 'function')
          try {
            _selectWidgetBlock(fb);
            setTimeout(function () {
              if (typeof window._captureFontOriginal === 'function') window._captureFontOriginal();
            }, 0);
          } catch (e) {}
      }
    }
  }
  if (id === 'add-widget-dropdown' && !isOpen) {
    openAddWidgetModal();
    return;
  }
};

// Fechar dropdowns ao clicar fora (centralizado)
document.addEventListener('click', function (e) {
  if (!e.target.closest('.edit-dropdown') && !e.target.closest('[onclick*="toggleEditDropdown"]')) {
    var hadBgOpen = document.getElementById('bg-color-dropdown')?.classList.contains('open');
    document.querySelectorAll('.edit-dropdown').forEach(function (d) {
      d.classList.remove('open');
      d.classList.add('hidden');
    });
    if (hadBgOpen) {
      document.body.classList.remove('bg-dropdown-open');
      var bgDd = document.getElementById('bg-color-dropdown');
      if (bgDd) {
        bgDd.style.removeProperty('position');
        bgDd.style.removeProperty('top');
        bgDd.style.removeProperty('left');
        bgDd.style.removeProperty('bottom');
        bgDd.style.removeProperty('right');
        bgDd.style.removeProperty('transform');
        bgDd.style.removeProperty('margin');
        bgDd.style.removeProperty('z-index');
        if (bgDd._originalParent) {
          try {
            if (bgDd._originalNext && bgDd._originalNext.parentElement === bgDd._originalParent) {
              bgDd._originalParent.insertBefore(bgDd, bgDd._originalNext);
            } else {
              bgDd._originalParent.appendChild(bgDd);
            }
          } catch (err) {}
          bgDd._originalParent = null;
          bgDd._originalNext = null;
        }
      }
    }
  }
});
// Fechar pesquisar ao clicar fora já trata search-menu-open, mas também limpa inline se necessário
document.addEventListener('click', function (e) {
  var menu = document.getElementById('search-menu');
  if (
    menu &&
    !menu.classList.contains('open') &&
    menu.style.getPropertyValue('position') === 'fixed'
  ) {
    // Menu fechado mas ainda com override fixed — limpa
    if (!menu.contains(e.target) && !e.target.closest('.widgetbar-search-btn')) {
      menu.style.removeProperty('position');
      menu.style.removeProperty('top');
      menu.style.removeProperty('left');
      menu.style.removeProperty('bottom');
      menu.style.removeProperty('right');
      menu.style.removeProperty('transform');
      menu.style.removeProperty('margin');
    }
  }
});

// ═══════════════════════════════════════════════════════════════════
// MODAL ADICIONAR WIDGET — Sistema Unificado
// ═══════════════════════════════════════════════════════════════════

// Definição centralizada de todos os widgets disponíveis no modal
window.WIDGET_CATALOG = {
  kpi: {
    comercial: {
      title: 'Comercial e Produção (Safra 24/25)',
      icon: 'bi-shop',
      items: [
        {
          id: 'kpi-vendas-totais',
          label: 'Produção Total (ton) — Safra',
          icon: 'bi-box-seam',
          color: 'emerald',
        },
        {
          id: 'kpi-margem-bruta',
          label: 'Margem por Hectare (R$/ha)',
          icon: 'bi-graph-up',
          color: 'green',
        },
        {
          id: 'kpi-pedidos',
          label: 'Pedidos de Venda (sc)',
          icon: 'bi-currency-dollar',
          color: 'blue',
        },
        {
          id: 'kpi-melhor-cliente',
          label: 'Melhor Talhão (produtividade)',
          icon: 'bi-star',
          color: 'amber',
        },
      ],
    },
    financeiro: {
      title: 'Financeiro e Rentabilidade',
      icon: 'bi-currency-dollar',
      items: [
        { id: 'kpi-roi', label: 'ROI', icon: 'bi-currency-dollar', color: 'green' },
        { id: 'kpi-custo', label: 'Custo/Ha', icon: 'bi-calculator', color: 'teal' },
        { id: 'kpi-caixa', label: 'Caixa', icon: 'bi-wallet2', color: 'emerald' },
      ],
    },
    produtividade: {
      title: 'Produtividade e Agronômico',
      icon: 'bi-graph-up-arrow',
      items: [
        {
          id: 'kpi-produtividade',
          label: 'Produtividade',
          icon: 'bi-graph-up-arrow',
          color: 'lime',
        },
        { id: 'kpi-area', label: 'Área Plantada', icon: 'bi-bounding-box', color: 'blue' },
      ],
    },
    operacional: {
      title: 'Operacional, Frota e Insumos',
      icon: 'bi-gear',
      items: [
        { id: 'kpi-manutencoes', label: 'Manutenção', icon: 'bi-tools', color: 'orange' },
        { id: 'kpi-sensores', label: 'Sensores', icon: 'bi-cpu', color: 'cyan' },
        { id: 'kpi-alertas', label: 'Alertas', icon: 'bi-exclamation-triangle', color: 'amber' },
        { id: 'kpi-funcionarios', label: 'Equipe', icon: 'bi-people', color: 'sky' },
      ],
    },
    sustentabilidade: {
      title: 'Sustentabilidade e Riscos',
      icon: 'bi-shield-check',
      items: [
        { id: 'kpi-clima', label: 'Clima', icon: 'bi-cloud-sun', color: 'sky' },
        { id: 'kpi-novidades', label: 'Novidades', icon: 'bi-megaphone', color: 'amber' },
        { id: 'widget-resumo', label: 'Resumo', icon: 'bi-info-circle', color: 'violet' },
      ],
    },
    top_globais: {
      title: 'TOP Globais — Clone FieldView / JD / Trimble / Solinftec (120 funcionalidades)',
      icon: 'bi-globe2',
      items: [
        {
          id: 'kpi-vra-ndvi',
          label: 'VRA NDVI 10m Sentinel-2 → Prescrição',
          icon: 'bi-satellite',
          color: 'emerald',
        },
        { id: 'kpi-can-bus', label: 'CAN Bus RPM/Consumo DTC', icon: 'bi-cpu', color: 'orange' },
        {
          id: 'kpi-guidance-ab',
          label: 'Guidance A-B Auto-section',
          icon: 'bi-signpost-split',
          color: 'blue',
        },
        {
          id: 'kpi-ai-cultura',
          label: 'AI Detecta Cultura Satélite',
          icon: 'bi-robot',
          color: 'violet',
        },
        {
          id: 'kpi-chuva-1km',
          label: 'Chuva Hiperlocal 1km 15min',
          icon: 'bi-cloud-rain-heavy',
          color: 'sky',
        },
        {
          id: 'kpi-as-applied',
          label: 'As-Applied vs As-Planned Gap',
          icon: 'bi-bullseye',
          color: 'amber',
        },
        { id: 'kpi-praga-ai', label: 'Alerta Praga AI Foto', icon: 'bi-bug', color: 'red' },
        {
          id: 'kpi-rota-otimizada',
          label: 'Rota Otimizada 70 Colheitadeiras',
          icon: 'bi-geo-alt',
          color: 'teal',
        },
        {
          id: 'kpi-weigh-scale',
          label: 'Weigh Scale sc/ha Tempo Real',
          icon: 'bi-speedometer2',
          color: 'lime',
        },
        {
          id: 'kpi-hedge-b3',
          label: 'Hedge B3 Chicago Real',
          icon: 'bi-graph-up-arrow',
          color: 'green',
        },
        {
          id: 'kpi-benchmark-fbn',
          label: 'Benchmark 2k Fazendas',
          icon: 'bi-bar-chart-line',
          color: 'cyan',
        },
        {
          id: 'kpi-seguro-chuva',
          label: 'Seguro Paramétrico Chuva',
          icon: 'bi-shield-fill-check',
          color: 'sky',
        },
        {
          id: 'kpi-lcdpr-sped',
          label: 'LCDPR SPED Auditável',
          icon: 'bi-file-earmark-check',
          color: 'emerald',
        },
        { id: 'kpi-carbono', label: 'Carbono tCO2e/ha Mombak', icon: 'bi-tree', color: 'green' },
        { id: 'kpi-voz', label: 'Assistente Voz', icon: 'bi-mic', color: 'violet' },
        {
          id: 'kpi-copilot-hedge',
          label: 'Copilot Hedge 65sc',
          icon: 'bi-chat-dots',
          color: 'amber',
        },
      ],
    },
  },
  graficos: [
    { id: 'chart-line', label: 'Linha', icon: 'bi-graph-up', color: 'emerald' },
    { id: 'chart-bar', label: 'Barras', icon: 'bi-bar-chart', color: 'teal' },
    { id: 'chart-pie', label: 'Pizza', icon: 'bi-pie-chart', color: 'violet' },
    { id: 'chart-area', label: 'Área', icon: 'bi-activity', color: 'cyan' },
    { id: 'chart-doughnut', label: 'Rosca', icon: 'bi-circle-half', color: 'pink' },
    { id: 'chart-radar', label: 'Radar', icon: 'bi-diagram-3', color: 'sky' },
    { id: 'chart-polar', label: 'Polar', icon: 'bi-bullseye', color: 'orange' },
    { id: 'chart-scatter', label: 'Dispersão', icon: 'bi-dot', color: 'lime' },
    { id: 'chart-stacked-bar', label: 'Empilhadas', icon: 'bi-bar-chart-fill', color: 'amber' },
    { id: 'chart-horizontal-bar', label: 'Horizontal', icon: 'bi-bar-chart-steps', color: 'blue' },
    { id: 'chart-mixed', label: 'Misto', icon: 'bi-layers', color: 'violet' },
    { id: 'chart-bubble', label: 'Bolhas', icon: 'bi-circle', color: 'pink' },
    { id: 'chart-safras', label: 'Safras', icon: 'bi-calendar3', color: 'green' },
    { id: 'chart-financeiro', label: 'Financeiro', icon: 'bi-pie-chart-fill', color: 'emerald' },
    { id: 'chart-estoque', label: 'Estoque', icon: 'bi-box', color: 'orange' },
    { id: 'chart-producao-animal', label: 'Prod. Animal', icon: 'bi-graph-up', color: 'amber' },
  ],
  tabelas: [
    { id: 'table-vendas-regiao', label: 'Vendas Região', icon: 'bi-map', color: 'violet' },
    { id: 'table-data', label: 'Safras', icon: 'bi-table', color: 'green' },
    { id: 'table-planilha', label: 'Planilha', icon: 'bi-file-spreadsheet', color: 'blue' },
    { id: 'table-financeiro', label: 'Financeiro', icon: 'bi-cash-stack', color: 'emerald' },
    { id: 'table-estoque', label: 'Estoque', icon: 'bi-boxes', color: 'orange' },
    { id: 'table-safras', label: 'Safras Detalhe', icon: 'bi-table', color: 'teal' },
  ],
  listas: [
    { id: 'list-tasks', label: 'Tarefas', icon: 'bi-list-task', color: 'emerald' },
    { id: 'list-agenda', label: 'Agenda', icon: 'bi-calendar-check', color: 'sky' },
    { id: 'list-manutencao', label: 'Manutenção', icon: 'bi-tools', color: 'orange' },
    { id: 'list-colmeias', label: 'Colmeias', icon: 'bi-flower1', color: 'amber' },
    { id: 'alerts-widget', label: 'Alertas', icon: 'bi-exclamation-triangle', color: 'rose' },
    { id: 'calendar-widget', label: 'Calendário', icon: 'bi-calendar-week', color: 'violet' },
  ],
};

var COLOR_MAP = {
  emerald: {
    bg: 'bg-emerald-100 dark:bg-emerald-500/15',
    text: 'text-emerald-600 dark:text-emerald-400',
  },
  green: { bg: 'bg-green-100 dark:bg-green-500/15', text: 'text-green-600 dark:text-green-400' },
  teal: { bg: 'bg-teal-100 dark:bg-teal-500/15', text: 'text-teal-600 dark:text-teal-400' },
  cyan: { bg: 'bg-cyan-100 dark:bg-cyan-500/15', text: 'text-cyan-600 dark:text-cyan-400' },
  sky: { bg: 'bg-sky-100 dark:bg-sky-500/15', text: 'text-sky-600 dark:text-sky-400' },
  blue: { bg: 'bg-blue-100 dark:bg-blue-500/15', text: 'text-blue-600 dark:text-blue-400' },
  violet: {
    bg: 'bg-violet-100 dark:bg-violet-500/15',
    text: 'text-violet-600 dark:text-violet-400',
  },
  amber: { bg: 'bg-amber-100 dark:bg-amber-500/15', text: 'text-amber-500 dark:text-amber-400' },
  orange: {
    bg: 'bg-orange-100 dark:bg-orange-500/15',
    text: 'text-orange-500 dark:text-orange-400',
  },
  rose: { bg: 'bg-rose-100 dark:bg-rose-500/15', text: 'text-rose-500 dark:text-rose-400' },
  pink: { bg: 'bg-pink-100 dark:bg-pink-500/15', text: 'text-pink-500 dark:text-pink-400' },
  lime: { bg: 'bg-lime-100 dark:bg-lime-500/15', text: 'text-lime-600 dark:text-lime-400' },
  slate: { bg: 'bg-slate-100 dark:bg-slate-500/15', text: 'text-slate-600 dark:text-slate-400' },
};

function renderWidgetGrid(containerId, items) {
  var grid = document.getElementById(containerId);
  if (!grid) return;
  grid.innerHTML = '';
  items.forEach(function (item) {
    var isActive = isWidgetActive(item.id);
    var colors = COLOR_MAP[item.color] || COLOR_MAP.emerald;
    var card = document.createElement('div');
    card.className = 'widget-card relative group/card' + (isActive ? ' widget-added' : '');
    card.setAttribute('data-widget-id', item.id);
    card.setAttribute('data-widget-label', item.label.toLowerCase());
    card.onclick = function () {
      addWidgetFromModal(item.id);
    };

    var editBtn =
      "<button onclick=\"event.stopPropagation(); if(typeof openWidgetSettings==='function') openWidgetSettings('" +
      item.id +
      '\');" class="absolute top-1.5 right-1.5 p-1.5 rounded-lg bg-white/5 dark:bg-black/20 text-slate-400 dark:text-white/50 hover:text-emerald-500 dark:hover:text-white hover:bg-white/10 dark:hover:bg-black/40 opacity-0 group-hover/card:opacity-100 transition-all z-10 flex items-center justify-center" title="Modificar Widget"><i class="bi bi-gear-fill text-[11px]"></i></button>';

    card.innerHTML =
      editBtn +
      '<div class="widget-card-icon ' +
      colors.bg +
      ' ' +
      colors.text +
      '"><i class="bi ' +
      item.icon +
      ' text-sm"></i></div><span class="widget-card-label">' +
      item.label +
      '</span>';
    grid.appendChild(card);
  });
}

function isWidgetActive(widgetId) {
  if (typeof widgets !== 'undefined' && widgets[widgetId])
    return widgets[widgetId].visible === true;
  return false;
}

function updateWidgetCounter() {
  var counter = document.getElementById('widget-modal-counter');
  if (!counter) return;
  var count = 0;
  if (typeof widgets !== 'undefined') {
    Object.values(widgets).forEach(function (w) {
      if (w.visible) count++;
    });
  }
  counter.textContent = count + ' widget' + (count !== 1 ? 's' : '') + ' no dashboard';
}

function renderAllWidgetGrids() {
  renderKpiAccordion();
  updateWidgetCounter();
}

function renderKpiAccordion() {
  var container = document.getElementById('kpi-accordion-container');
  if (!container) return;

  if (!window.WIDGET_CATALOG || !window.WIDGET_CATALOG.kpi) {
    container.innerHTML =
      '<div style="color:white;padding:20px;">ERRO: WIDGET_CATALOG.kpi VAZIO OU NÃO EXISTE!</div>';
    return;
  }

  container.innerHTML = '';
  var categories = window.WIDGET_CATALOG.kpi;
  var catKeys = Object.keys(categories);
  if (catKeys.length === 0) {
    container.innerHTML += '<div style="color:white;padding:20px;">ERRO: CATEGORIAS VAZIAS!</div>';
  }
  // Linha superior com pills lado a lado (igual vegetal/animal)
  var btnRow = document.createElement('div');
  btnRow.className = 'flex flex-wrap gap-2 mb-4';
  btnRow.id = 'kpi-pills-row';
  container.appendChild(btnRow);
  catKeys.forEach(function (catKey, idx) {
    var cat = categories[catKey];
    var pill = document.createElement('button');
    pill.className = 'subgroup-pill' + (idx === 0 ? ' active' : '');
    pill.setAttribute('data-kpi-pill', catKey);
    pill.innerHTML =
      '<i class="bi ' +
      (cat.icon || 'bi-folder') +
      '"></i> ' +
      cat.title +
      ' <span class="ml-1 text-[10px] bg-black/5 dark:bg-white/10 px-1.5 py-0.5 rounded-full">' +
      cat.items.length +
      '</span>';
    pill.onclick = (function (k) {
      return function () {
        toggleKpiCategory(k);
      };
    })(catKey);
    btnRow.appendChild(pill);
    // Painel da categoria
    var panel = document.createElement('div');
    panel.className = 'kpi-category-panel';
    panel.setAttribute('data-kpi-panel', catKey);
    panel.style.display = idx === 0 ? '' : 'none';
    panel.innerHTML = '<div class="grid grid-cols-4 gap-2" id="kpi-grid-' + catKey + '"></div>';
    container.appendChild(panel);
    renderWidgetGrid('kpi-grid-' + catKey, cat.items);
  });
}

window.toggleKpiCategory = function (catKey) {
  var pill = document.querySelector('[data-kpi-pill="' + catKey + '"]');
  var panel = document.querySelector('[data-kpi-panel="' + catKey + '"]');
  if (!pill || !panel) return;
  var isActive = pill.classList.contains('active');
  // Alterna: adiciona/esconde (como vegetal)
  if (isActive) {
    // Nao deixa esconder o ultimo visivel
    var visiblePanels = document.querySelectorAll(
      '.kpi-category-panel:not([style*="display: none"])'
    );
    if (visiblePanels.length <= 1) return;
    pill.classList.remove('active');
    panel.style.display = 'none';
  } else {
    pill.classList.add('active');
    panel.style.display = '';
  }
};

// Fechar modal com Escape
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape' && document.body.classList.contains('widget-modal-open')) {
    closeAddWidgetModal();
    e.preventDefault();
    e.stopPropagation();
  }
});

window.openAddWidgetModal = function () {
  var modal = document.getElementById('add-widget-modal');
  var panel = document.getElementById('add-widget-modal-panel');
  var emptyState = document.getElementById('widget-modal-empty-state');
  var content = document.getElementById('widget-modal-content');
  var searchInput = document.getElementById('widget-modal-search');
  var showAllChk = document.getElementById('widget-modal-show-all');

  if (!modal || !panel) return;

  // Fix permanente console 23/09: conflitos z-index (appbar 2147483647), opacity 0 scale-95, backdrop
  // Garante que modal fique acima de dashboard-appbar/quick-settings/ia-panel (todos 214748364x)
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  document.body.classList.add('widget-modal-open');
  // Abaixa temporariamente blockers que tinham 2Bi z-index
  var _blockers = [
    'dashboard-appbar',
    'quick-settings-flyout',
    'widget-context-menu',
    'ia-panel-overlay',
    'ia-dock',
  ];
  window._modalBlockersBackup = [];
  _blockers.forEach(function (id) {
    var el = document.getElementById(id);
    if (el && parseInt(window.getComputedStyle(el).zIndex, 10) > 1001) {
      window._modalBlockersBackup.push({ el: el, z: el.style.zIndex });
      el.style.setProperty('z-index', '1000', 'important');
    }
  });
  // Fundo escuro + blur (console fix)
  modal.style.setProperty('background-color', 'rgba(0,0,0,0.5)', 'important');
  modal.style.setProperty('backdrop-filter', 'blur(4px)', 'important');
  modal.style.setProperty('z-index', '2147483647', 'important');
  // Painel: força visível (era opacity 0 visibility hidden scale-95)
  panel.style.setProperty('opacity', '1', 'important');
  panel.style.setProperty('visibility', 'visible', 'important');
  panel.style.setProperty('pointer-events', 'auto', 'important');
  panel.style.setProperty('display', 'flex', 'important');
  panel.style.setProperty('flex-direction', 'column', 'important');
  requestAnimationFrame(function () {
    panel.style.transform = 'scale(1)';
    panel.style.opacity = '1';
    panel.style.visibility = 'visible';
  });

  renderAllWidgetGrids();
  if (typeof CulturesLoader !== 'undefined') {
    CulturesLoader.renderAll();
  }

  switchWidgetTab('kpi');

  if (searchInput) searchInput.value = '';
  if (showAllChk) showAllChk.checked = false;
  filterWidgetModal();
};

window.closeAddWidgetModal = function () {
  var modal = document.getElementById('add-widget-modal');
  var panel = document.getElementById('add-widget-modal-panel');
  if (!modal || !panel) return;
  restoreMiniChrome();
  var miniPanel = document.getElementById('culture-mini-panel');
  var tabsRow = document.querySelector('#add-widget-modal-panel > div:nth-child(2)');
  var content = document.getElementById('widget-modal-content');
  if (miniPanel) miniPanel.classList.add('hidden');
  if (tabsRow) tabsRow.classList.remove('hidden');
  if (content) content.classList.remove('hidden');
  cultureMiniPanelState.cultureId = null;
  destroyMiniPanelCharts();
  panel.style.transform = 'scale(0.95)';
  panel.style.opacity = '0';
  panel.style.visibility = 'hidden';
  // Restaura z-index dos blockers
  if (window._modalBlockersBackup) {
    window._modalBlockersBackup.forEach(function (b) {
      if (b.z) b.el.style.zIndex = b.z;
      else b.el.style.removeProperty('z-index');
    });
    window._modalBlockersBackup = [];
  }
  modal.style.removeProperty('background-color');
  modal.style.removeProperty('backdrop-filter');
  setTimeout(function () {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.body.classList.remove('widget-modal-open');
    panel.style.removeProperty('opacity');
    panel.style.removeProperty('visibility');
    panel.style.removeProperty('pointer-events');
    panel.style.removeProperty('display');
    panel.style.removeProperty('flex-direction');
  }, 150);
};

window.filterWidgetModal = function () {
  var q = (document.getElementById('widget-modal-search').value || '').toLowerCase().trim();
  var showAllChk = document.getElementById('widget-modal-show-all');
  var showAll = showAllChk ? showAllChk.checked : false;
  var emptyState = document.getElementById('widget-modal-empty-state');
  var content = document.getElementById('widget-modal-content');
  var miniPanel = document.getElementById('culture-mini-panel');
  var totalVisible = 0;
  var firstVisibleTab = null;

  // Don't filter if mini panel is open
  if (miniPanel && !miniPanel.classList.contains('hidden')) return;

  // Build set of cultures with production data
  var filledCultures = {};
  if (window.ProductionRegistry) {
    ProductionRegistry.getAll().forEach(function (r) {
      filledCultures[r.cultureId] = true;
    });
  }

  // Step 1: Show/hide individual cards
  var allCards = document.querySelectorAll(
    '#widget-modal-content .widget-card, #widget-modal-content [data-culture-card]'
  );
  allCards.forEach(function (card) {
    var label = (
      card.getAttribute('data-widget-label') ||
      card.getAttribute('data-culture-title') ||
      ''
    ).toLowerCase();
    var cultureId = card.getAttribute('data-culture-id') || '';
    var matchSearch = !q || label.indexOf(q) >= 0;
    // When unchecked: only show culture cards that have production data; KPI cards always show
    var hasData = showAll || !cultureId || filledCultures[cultureId];
    card.style.display = matchSearch && hasData ? '' : 'none';
    if (matchSearch && hasData) {
      totalVisible++;
      if (!firstVisibleTab) {
        var parentTab = card.closest('.tab-content');
        if (parentTab) firstVisibleTab = parentTab.getAttribute('data-modal-tab');
      }
      // Open accordion body when search finds items
      if (q) {
        var accBody = card.closest('.accordion-body');
        if (accBody) accBody.classList.add('open');
        var accHeader = accBody ? accBody.previousElementSibling : null;
        if (accHeader) accHeader.classList.add('open');
      }
    }
  });

  // Step 2: Show/hide subgroup containers (mb-2 e kpi-category-panel) baseado nos cards visiveis
  var allMb2 = document.querySelectorAll(
    '#widget-modal-content .mb-2, #widget-modal-content .kpi-category-panel'
  );
  allMb2.forEach(function (el) {
    var isKpiPanel = el.classList.contains('kpi-category-panel');
    if (!isKpiPanel && !el.querySelector('.accordion-header')) return;
    var cards = el.querySelectorAll('.widget-card, [data-culture-card]');
    var anyVisible = false;
    cards.forEach(function (c) {
      if (c.style.display !== 'none') anyVisible = true;
    });
    if (q) {
      // Durante busca: mostra painel que tiver resultado, ignora filtro do dropdown
      el.style.display = anyVisible ? '' : 'none';
    } else {
      // Sem busca: respeita filtro do dropdown KPI (se __all mostra tudo, senao so o selecionado ja esta visivel)
      // Para kpi-category-panel, deixa como esta (controlado por filterKpiCategory), senao aplica logica de showAll
      if (isKpiPanel) {
        // Nao altera display de kpi panels quando nao ha busca — deixa dropdown controlar
        // Mas se nenhum painel visivel e showAll desmarcado, esconde vazios
        if (!showAll && !anyVisible) el.style.display = 'none';
      } else {
        if (!showAll && !q) {
          el.style.display = anyVisible ? '' : 'none';
        } else {
          el.style.display = '';
        }
      }
    }
  });

  // Mostrar/ocultar empty state
  if (q && totalVisible === 0) {
    emptyState.classList.remove('hidden');
    content.classList.add('hidden');
  } else {
    emptyState.classList.add('hidden');
    content.classList.remove('hidden');
  }

  // Trocar para a aba onde encontrou resultados
  if (q && firstVisibleTab) {
    switchWidgetTab(firstVisibleTab);
  }
};

// ── Detail view (legacy — kept for compatibility) ──
window.showCultureDetail = function (cultureId, groupId) {
  // Redirect to new mini panel
  showCultureMiniPanel(cultureId, groupId);
};

window.switchWidgetTab = function (tab) {
  // Suporta preset-tab-btn (KPIs/Recentes), nav-link (legado) e cultura
  document
    .querySelectorAll(
      '#widget-modal-tabs .preset-tab-btn, #widget-modal-tabs .nav-link, #widget-modal-tabs .widget-modal-tab, #widget-modal-tabs-cultura .nav-link, #widget-modal-tabs-cultura button'
    )
    .forEach(function (btn) {
      btn.classList.remove('active', 'active-tab');
      btn.setAttribute('aria-selected', 'false');
    });
  var activeBtn = document.querySelector(
    '#widget-modal-tabs .preset-tab-btn[data-modal-tab="' +
      tab +
      '"], #widget-modal-tabs .nav-link[data-modal-tab="' +
      tab +
      '"], #widget-modal-tabs .widget-modal-tab[data-modal-tab="' +
      tab +
      '"], #widget-modal-tabs-cultura .nav-link[data-modal-tab="' +
      tab +
      '"], #widget-modal-tabs-cultura button[data-modal-tab="' +
      tab +
      '"]'
  );
  if (activeBtn) {
    activeBtn.classList.add('active');
    // Compat: mantem active-tab para legado
    activeBtn.classList.add('active-tab');
    activeBtn.setAttribute('aria-selected', 'true');
  }
  document.querySelectorAll('#widget-modal-content .tab-content').forEach(function (c) {
    c.classList.add('hidden');
    c.classList.remove('active');
  });
  var content = document.querySelector(
    '#widget-modal-content .tab-content[data-modal-tab="' + tab + '"]'
  );
  if (content) {
    content.classList.remove('hidden');
    content.classList.add('active');
  } else {
    // Ausência anunciada, não ausência silenciosa.
    //
    // A versão anterior fazia `if (content) {...}` e mais nada: um
    // separador sem painel deixava o modal completamente em branco,
    // sem widgets e sem uma palavra. Foi o que aconteceu com o
    // separador "Extrativismo", cujo grupo tinha zero culturas — o
    // produtor via um rectângulo vazio e não tinha como saber se
    // era um erro, uma falha de rede, ou um separador que não era
    // para ele.
    //
    // `cultures-loader.js` já não cria separadores sem conteúdo.
    // Esta guarda fica para o caso genérico — um separador
    // escrito à mão, um painel que não carregou, um nome de grupo
    // trocado — porque o custo de a ter é uma linha, e o custo de
    // não a ter é um ecrã vazio sem explicação.
    if (tab) {
      var aviso = document.createElement('div');
      aviso.className = 'tab-content active';
      aviso.setAttribute('data-modal-tab', tab);
      aviso.setAttribute('data-empty-tab', 'true');
      aviso.innerHTML =
        '<div style="padding:28px 20px;text-align:center;opacity:.75">' +
        '<i class="bi bi-inbox" style="font-size:1.6rem;display:block;margin-bottom:.5rem"></i>' +
        'Ainda não há widgets nesta secção.' +
        '<div style="font-size:.8em;margin-top:.35rem;opacity:.8">' +
        'Assim que houver culturas registadas, aparecem aqui.' +
        '</div></div>';
      var host = document.getElementById('widget-modal-content');
      if (host) host.appendChild(aviso);
    }
  }
  // Fecha dropdown KPI se nao for KPI
  if (tab !== 'kpi') {
    var kpiDrop = document.getElementById('kpi-nav-item');
    if (kpiDrop) {
      kpiDrop.classList.remove('show');
      var t = kpiDrop.querySelector('.dropdown-toggle');
      if (t) t.setAttribute('aria-expanded', 'false');
    }
  }
  // Hide mini panel when switching tabs
  if (typeof hideCultureMiniPanel === 'function') hideCultureMiniPanel();
};

// ── Accordion toggle ──
window.toggleAccordion = function (accordionId) {
  var body = document.getElementById(accordionId);
  if (!body) return;
  var header = body.previousElementSibling;
  var isOpen = body.classList.contains('open');
  if (isOpen) {
    body.classList.remove('open');
    if (header) header.classList.remove('open');
  } else {
    body.classList.add('open');
    if (header) header.classList.add('open');
  }
};

// ── Culture mini panel state ──
var cultureMiniPanelState = {
  cultureId: null,
  groupId: null,
  tab: 'mercado',
  selectedType: null,
  marketCards: [],
  availableUFs: [],
};
var miniSavedHeaderHTML = '';
var miniSavedFooterHTML = '';

function getMarketCardDefinitions(groupId) {
  var defs = {
    vegetal: {
      agrodoc: [{ key: 'valor_saca', title: 'Preço de Mercado', sub: '(AgroDoc / CEPEA)' }],
      ibge: [
        { key: 'producao_total', title: 'Produção Total', sub: '(IBGE / SIDRA)' },
        { key: 'area_plantada', title: 'Área Plantada', sub: '(IBGE / SIDRA)' },
        { key: 'produtividade', title: 'Produtividade', sub: '(IBGE / SIDRA)' },
        { key: 'receita_estimada', title: 'Valor da Produção', sub: '(IBGE / SIDRA)' },
      ],
      fallback: {
        key: 'no_data',
        title: 'Dados de Mercado',
        sub: '(sem fonte real disponível)',
      },
    },
    animal: {
      agrodoc: [{ key: 'valor_saca', title: 'Preço por Arroba', sub: '(AgroDoc / CEPEA)' }],
      ibge: [
        { key: 'cabecas_total', title: 'Efetivo do Rebanho', sub: '(IBGE / PPM)' },
        { key: 'receita_estimada', title: 'Valor da Produção', sub: '(IBGE / PPM)' },
      ],
      fallback: {
        key: 'no_data',
        title: 'Dados de Mercado',
        sub: '(sem fonte real disponível)',
      },
    },
    aquatica: {
      agrodoc: [{ key: 'valor_saca', title: 'Preço por kg', sub: '(AgroDoc / CEPEA)' }],
      ibge: [
        { key: 'producao_total', title: 'Produção Total', sub: '(IBGE / PPM)' },
        { key: 'receita_estimada', title: 'Valor da Produção', sub: '(IBGE / PPM)' },
      ],
      fallback: {
        key: 'no_data',
        title: 'Dados de Mercado',
        sub: '(sem fonte real disponível)',
      },
    },
    extrativismo: {
      agrodoc: [{ key: 'valor_kg', title: 'Preço por kg', sub: '(AgroDoc / CEPEA)' }],
      ibge: [
        { key: 'producao_total', title: 'Volume Extraído', sub: '(IBGE / SIDRA)' },
        { key: 'area_plantada', title: 'Área de Manejo', sub: '(IBGE / SIDRA)' },
        { key: 'rendimento', title: 'Rendimento', sub: '(IBGE / SIDRA)' },
        {
          key: 'receita_estimada',
          title: 'Valor da Produção Extrativa',
          sub: '(IBGE / SIDRA)',
        },
      ],
      fallback: {
        key: 'no_data',
        title: 'Dados de Mercado',
        sub: '(sem fonte real disponível)',
      },
    },
  };
  return defs[groupId] || defs.vegetal;
}

function buildMarketCards(cultureId, groupId) {
  var uf = sget('ampliagro-culture-uf') || '';
  function card(metricKey, title, subtitle, source) {
    return {
      metricKey: metricKey,
      title: title,
      subtitle: subtitle,
      source: source,
      selectedUf: uf,
      widgetType: 'grafico',
      data: null,
      history: [],
      chartInstance: null,
    };
  }

  var cards = [];
  var hasAgroDoc = !!(
    window.CultureData &&
    CultureData.hasAgroDocSupport &&
    CultureData.hasAgroDocSupport(cultureId)
  );
  var hasIBGE = !!(
    window.CultureData &&
    CultureData.hasIBGEMapping &&
    CultureData.hasIBGEMapping(cultureId)
  );
  var defs = getMarketCardDefinitions(groupId);

  if (hasAgroDoc && defs.agrodoc) {
    defs.agrodoc.forEach(function (d) {
      cards.push(card(d.key, d.title, d.sub, 'agrodoc'));
    });
  }

  if (hasIBGE && defs.ibge) {
    defs.ibge.forEach(function (d) {
      cards.push(card(d.key, d.title, d.sub, 'ibge'));
    });
  }

  // Fallback só se for dado real; se não tem fonte real, não insere nada
  if (!hasAgroDoc && !hasIBGE && defs.fallback) {
    // não empurra no_data — será filtrado adiante
  }

  // Só insere Minha Produtividade se houver registros reais
  var hasProdRecords = !!(
    window.ProductionRegistry &&
    ProductionRegistry.getByCultureSorted &&
    ProductionRegistry.getByCultureSorted(cultureId).length
  );
  if (hasProdRecords) {
    cards.push(card('minha_produt', 'Minha Produtividade', '(meus registros)', 'cultura'));
  }
  // Só comparativo se houver mercado real + produção real
  if (hasProdRecords && (hasAgroDoc || hasIBGE)) {
    cards.push(card('comparativo', 'Comparativo Estado', '(eu vs. mercado real)', 'composite'));
  }
  // Filtra: só mantem cards com fonte real; remove no_data vazios
  cards = cards.filter(function (c) {
    return c.source !== 'no_data';
  });
  // Se ficou vazio (cultura sem fonte real como Amaranto), mantém 1 card genérico para permitir inserir Linha/Barra/Card/Planilha sem erro
  if (cards.length === 0) {
    cards.push(
      card('producao_total', 'Produção Total', '(sem dados reais — cadastre produção)', 'cultura')
    );
  }
  return cards;
}

function buildProductionRecords(cultureId) {
  if (!window.ProductionRegistry) return [];
  var serverId = cultureMiniPanelState && cultureMiniPanelState.serverCultureId;
  return ProductionRegistry.getByCultureSorted(cultureId).concat(
    getToolbarRecordsForCulture(cultureId, serverId)
  );
}

// ── Registros de produção salvos no servidor (Guias / cadastros) ──
var _serverCulturaMapCache = null;

function _normName(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function getServerCulturaMap() {
  if (_serverCulturaMapCache) return Promise.resolve(_serverCulturaMapCache);
  return fetch('/api/culturas/', { credentials: 'same-origin' })
    .then(function (r) {
      return r.ok ? r.json() : [];
    })
    .then(function (items) {
      var map = { bySlug: {}, byNome: {} };
      (items || []).forEach(function (c) {
        if (c && c.id != null) {
          map.bySlug[String(c.id)] = c;
          map.bySlug['cultura-' + c.id] = c;
          if (c.nome) map.byNome[_normName(c.nome)] = c;
          if (c.chave_mercado) map.bySlug[c.chave_mercado] = c;
        }
      });
      _serverCulturaMapCache = map;
      return map;
    })
    .catch(function () {
      _serverCulturaMapCache = { bySlug: {}, byNome: {} };
      return _serverCulturaMapCache;
    });
}

function resolveServerCultura(cultureId) {
  var culture =
    window.CulturesLoader && CulturesLoader.getCulture
      ? CulturesLoader.getCulture(cultureId)
      : null;
  var nomeNorm = culture ? _normName(culture.django_nome || culture.title) : _normName(cultureId);
  return getServerCulturaMap().then(function (map) {
    var c = map.bySlug[cultureId] || map.bySlug['cultura-' + cultureId] || map.byNome[nomeNorm];
    return c || null;
  });
}

function getToolbarRecordsForCulture(cultureId, serverId) {
  if (!serverId) return [];
  return ProductionRegistry.getByCulture(String(serverId));
}

function mergeServerProductionRecords(records, into) {
  var byId = {};
  (into || []).forEach(function (r) {
    if (r.id != null) byId[String(r.id)] = r;
  });
  var added = false;
  (records || []).forEach(function (r) {
    if (r == null) return;
    var key =
      r.id != null ? String(r.id) : r.name + '|' + (r.location || '') + '|' + (r.date || '');
    if (byId[key]) return;
    var rec = {
      id: r.id,
      cultureId: cultureMiniPanelState.cultureId,
      groupId: r.groupId || (cultureMiniPanelState && cultureMiniPanelState.groupId),
      status: r.status || 'ativo',
      name: r.name || '',
      location: r.location || '',
      date: r.date || r.plantingDate || '',
      plantingDate: r.plantingDate || r.date || '',
      quantity: r.quantity,
      unit: r.unit || '',
      observations: r.observations || '',
      fields: r.fields || {},
      treatments: r.treatments || [],
      harvests: (r.fields && r.fields.harvests) || [],
      createdAt: r.createdAt || '',
      updatedAt: r.updatedAt || '',
    };
    byId[key] = rec;
    into.push(rec);
    added = true;
  });
  return added;
}

function loadServerProductionRecords(cultureId, groupId) {
  if (!window.ProductionRegistry) return;
  var st = cultureMiniPanelState;
  if (!st || st.cultureId !== cultureId) return;
  resolveServerCultura(cultureId)
    .then(function (c) {
      if (!st || st.cultureId !== cultureId) return;
      if (c && c.id != null) st.serverCultureId = String(c.id);
      var q =
        c && c.id != null
          ? '?cultura=' + c.id
          : cultureId
            ? '?cultura=' + encodeURIComponent(cultureId)
            : '';
      return fetch('/api/registros-producao/' + q, { credentials: 'same-origin' })
        .then(function (r) {
          return r.ok ? r.json() : [];
        })
        .then(function (records) {
          var list = Array.isArray(records) ? records : (records && records.results) || [];
          var added = mergeServerProductionRecords(list, st.productionRecords);
          if (added) {
            var ed = st.editor;
            if (
              st.tab === 'minha-producao' &&
              st.selectedRecordIds.length === 0 &&
              st.productionRecords.length === 1
            ) {
              st.selectedRecordIds = [st.productionRecords[0].id];
            }
            renderCultureMiniPanel();
            if (
              st.tab === 'minha-producao' &&
              st.productionCards &&
              st.productionCards[ed.activeCard]
            ) {
              fetchProductionCardData(ed.activeCard);
            }
          }
        })
        .catch(function () {});
    })
    .catch(function () {});
}

function getProductionCardDefinitions(groupId) {
  var defs = {
    vegetal: [
      { metricKey: 'sacas_total', title: 'Sacas Obtidas', subtitle: '(total dos registros)' },
      {
        metricKey: 'media_talhao',
        title: 'Média por Talhão',
        subtitle: '(agrupado por local)',
      },
      {
        metricKey: 'serie_temporal',
        title: 'Série Temporal',
        subtitle: '(evolução por data)',
      },
      { metricKey: 'comparativo', title: 'Comparativo', subtitle: '(registros lado a lado)' },
      { metricKey: 'detalhamento', title: 'Detalhamento', subtitle: '(tabela completa)' },
      {
        metricKey: 'distribuicao',
        title: 'Distribuição',
        subtitle: '(participação percentual)',
      },
    ],
    animal: [
      { metricKey: 'cabecas_total', title: 'Cabeças Totais', subtitle: '(total dos registros)' },
      { metricKey: 'media_lote', title: 'Média por Lote', subtitle: '(agrupado por local)' },
      {
        metricKey: 'serie_temporal',
        title: 'Ciclo Produtivo',
        subtitle: '(evolução temporal)',
      },
      { metricKey: 'comparativo', title: 'Comparativo Lotes', subtitle: '(lotes lado a lado)' },
      { metricKey: 'detalhamento', title: 'Detalhamento', subtitle: '(tabela completa)' },
      { metricKey: 'taxa_lotacao', title: 'Taxa de Lotação', subtitle: '(cab./hectare)' },
    ],
    aquatica: [
      { metricKey: 'biomassa_total', title: 'Biomassa Total', subtitle: '(total dos registros)' },
      {
        metricKey: 'media_tanque',
        title: 'Média por Tanque',
        subtitle: '(agrupado por local)',
      },
      {
        metricKey: 'serie_temporal',
        title: 'Ciclo de Cultivo',
        subtitle: '(evolução temporal)',
      },
      { metricKey: 'comparativo', title: 'Comparativo Tanques', subtitle: '(tanques lado a lado)' },
      { metricKey: 'detalhamento', title: 'Detalhamento', subtitle: '(tabela completa)' },
      {
        metricKey: 'conversao_alimentar',
        title: 'Conversão Alimentar',
        subtitle: '(ração/biomassa)',
      },
    ],
    extrativismo: [
      { metricKey: 'volume_total', title: 'Volume Extraído', subtitle: '(total dos registros)' },
      { metricKey: 'media_area', title: 'Média por Área', subtitle: '(agrupado por local)' },
      { metricKey: 'serie_temporal', title: 'Sazonalidade', subtitle: '(evolução por data)' },
      {
        metricKey: 'comparativo',
        title: 'Comparativo Áreas',
        subtitle: '(áreas lado a lado)',
      },
      { metricKey: 'detalhamento', title: 'Detalhamento', subtitle: '(tabela completa)' },
      { metricKey: 'rendimento', title: 'Rendimento', subtitle: '(por hectare)' },
    ],
  };
  return defs[groupId] || defs.vegetal;
}

function buildProductionCardConfigs(groupId) {
  var defs = getProductionCardDefinitions(groupId);
  return defs.map(function (d) {
    return {
      metricKey: d.metricKey,
      title: d.title,
      subtitle: d.subtitle,
      source: 'producao',
      widgetType: 'grafico',
      chartSubtype: 'line',
      data: null,
      history: [],
      chartInstance: null,
    };
  });
}

window.showCultureMiniPanel = function (cultureId, groupId) {
  var content = document.getElementById('widget-modal-content');
  var miniPanel = document.getElementById('culture-mini-panel');
  var tabsRow = document.querySelector('#add-widget-modal-panel > div:nth-child(2)');
  if (!content || !miniPanel) return;
  var ufOptions =
    window.CultureData && Array.isArray(CultureData.UF_LIST)
      ? CultureData.UF_LIST.slice()
      : [{ sigla: '', nome: 'Brasil (todos)' }];
  cultureMiniPanelState = {
    cultureId: cultureId,
    groupId: groupId,
    tab: 'mercado',
    selectedType: null,
    marketCards: buildMarketCards(cultureId, groupId),
    productionRecords: buildProductionRecords(cultureId),
    productionCards: buildProductionCardConfigs(groupId),
    selectedRecordIds: [],
    checkboxExpanded: false,
    availableUFs: ufOptions,
    editor: {
      category: 'linha',
      variant: 'suave',
      activeCard: 0,
      compare: [],
      mainColor: null,
      previewChart: null,
      _editingWidgetId: null,
    },
  };
  content.classList.add('hidden');
  content.style.setProperty('display', 'none', 'important');
  if (tabsRow) {
    tabsRow.classList.add('hidden');
    tabsRow.style.setProperty('display', 'none', 'important');
  }
  miniPanel.classList.remove('hidden');
  miniPanel.style.setProperty('display', 'flex', 'important');
  miniPanel.style.setProperty('flex', '1 1 0%', 'important');
  miniPanel.style.setProperty('min-height', '0', 'important');
  miniPanel.style.setProperty('flex-direction', 'column', 'important');
  miniPanel.style.setProperty('overflow-y', 'auto', 'important');
  miniPanel.style.setProperty('height', '100%', 'important');
  var _hdrShow = document.getElementById('widget-modal-header');
  if (_hdrShow) {
    _hdrShow.classList.remove('hidden');
    _hdrShow.classList.add('flex');
  }
  saveMiniChrome();
  renderCultureMiniPanel();
  fetchAvailableUFs(cultureId);
  loadServerProductionRecords(cultureId, groupId);
};

window.hideCultureMiniPanel = function () {
  var content = document.getElementById('widget-modal-content');
  var miniPanel = document.getElementById('culture-mini-panel');
  var tabsRow = document.querySelector('#add-widget-modal-panel > div:nth-child(2)');
  if (!content || !miniPanel) return;
  content.classList.remove('hidden');
  content.style.removeProperty('display');
  if (tabsRow) {
    tabsRow.classList.remove('hidden');
    tabsRow.style.removeProperty('display');
  }
  miniPanel.classList.add('hidden');
  miniPanel.style.setProperty('display', 'none', 'important');
  var _hdrHide = document.getElementById('widget-modal-header');
  if (_hdrHide) {
    _hdrHide.classList.add('hidden');
    _hdrHide.classList.remove('flex');
    _hdrHide.innerHTML = '';
  }
  cultureMiniPanelState.cultureId = null;
  if (cultureMiniPanelState.editor) cultureMiniPanelState.editor._editingWidgetId = null;
  destroyMiniPanelCharts();
  restoreMiniChrome();
};

// ── Estrelas (favoritos) — ativam meta/comparação por card ──
function cardStarKey(kind, cardIdx) {
  var st = cultureMiniPanelState;
  var c =
    kind === 'market'
      ? st.marketCards && st.marketCards[cardIdx]
      : st.productionCards && st.productionCards[cardIdx];
  if (!c) return '';
  return kind + ':' + (st.cultureId || '') + ':' + (c.metricKey || '');
}

function loadStarredCards() {
  try {
    return JSON.parse(localStorage.getItem('amp-starred-cards') || '{}');
  } catch (e) {
    return {};
  }
}

function isCardStarred(kind, cardIdx) {
  var key = cardStarKey(kind, cardIdx);
  return !!key && !!loadStarredCards()[key];
}

window.toggleCardStar = function (kind, cardIdx) {
  var key = cardStarKey(kind, cardIdx);
  if (!key) return;
  var map = loadStarredCards();
  if (map[key]) {
    delete map[key];
  } else {
    map[key] = 1;
  }
  try {
    localStorage.setItem('amp-starred-cards', JSON.stringify(map));
  } catch (e) {}
  renderCultureMiniPanel();
};

// ── Meta (linha de referência) ──
window.toggleEditorMeta = function (checked) {
  var ed = cultureMiniPanelState.editor;
  ed.metaEnabled = !!checked;
  if (!ed.metaEnabled) ed.metaValue = '';
  renderCultureMiniPanel();
};

window.setEditorMetaValue = function (v) {
  cultureMiniPanelState.editor.metaValue = v;
  renderEditorPreview();
};

function metaLineOptions(opts, enabled, value, label) {
  if (!opts || typeof opts !== 'object') return opts;
  if (!opts.plugins) opts.plugins = {};
  if (
    enabled &&
    value !== '' &&
    value !== null &&
    value !== undefined &&
    !isNaN(parseFloat(value))
  ) {
    opts.plugins.ampliReference = {
      metaLines: [{ value: parseFloat(value), color: '#d93a3a', label: label || 'Meta' }],
    };
  }
  return opts;
}

function productionRecordChartValue(record, metricKey) {
  if (!record) return 0;
  if (metricKey === 'produtividade') {
    var a = miniExtractArea(record);
    return a && a > 0 ? (record.quantity || 0) / a : record.quantity || 0;
  }
  if (
    metricKey === 'receita_estimada' ||
    metricKey === 'receita' ||
    metricKey === 'receita_total'
  ) {
    var rev = miniExtractRevenue(record);
    return rev !== null ? rev : record.quantity || 0;
  }
  if (metricKey === 'valor_saca' || metricKey === 'preco') {
    var vp = miniExtractUnitPrice(record);
    return vp !== null ? vp : record.quantity || 0;
  }
  return record.quantity || 0;
}

window.setMiniPanelTab = function (tab) {
  cultureMiniPanelState.tab = tab;
  renderCultureMiniPanel();
};

window.setMiniPanelCultureType = function (type) {
  cultureMiniPanelState.selectedType = type;
};

window.selectMiniCardWidgetType = function (cardIdx, type) {
  var card = cultureMiniPanelState.marketCards[cardIdx];
  card.widgetType = type;
  if (type === 'grafico' && !card.chartSubtype) card.chartSubtype = 'line';
  renderCultureMiniPanel();
};

window.selectChartSubtype = function (idx, subtype) {
  cultureMiniPanelState.marketCards[idx].chartSubtype = subtype;
  renderMiniCardChart(idx);
};

window.changeMiniCardUf = function (cardIdx, uf) {
  var card = cultureMiniPanelState.marketCards[cardIdx];
  if (!card) return;
  if (card.source === 'cultura') return;

  sset('ampliagro-culture-uf', uf);
  if (window.CultureData && typeof CultureData.setUf === 'function') {
    CultureData.setUf(uf);
  }

  cultureMiniPanelState.marketCards.forEach(function (c) {
    if (c.source !== 'cultura') {
      c.selectedUf = uf;
    }
  });

  renderCultureMiniPanel();
};

window.changeGlobalUF = function (uf) {
  sset('ampliagro-culture-uf', uf);
  if (window.CultureData && typeof CultureData.setUf === 'function') {
    CultureData.setUf(uf);
  }

  cultureMiniPanelState.marketCards.forEach(function (c) {
    c.selectedUf = uf;
  });

  renderCultureMiniPanel();
};

window.fetchAvailableUFs = function (cultureId) {
  var fallbackUFs =
    window.CultureData && Array.isArray(CultureData.UF_LIST)
      ? CultureData.UF_LIST.slice()
      : [{ sigla: '', nome: 'Brasil (todos)' }];

  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/api/ibge-ufs/?cultura=' + encodeURIComponent(cultureId), true);
  xhr.timeout = 15000;

  function applyUFs(options) {
    cultureMiniPanelState.availableUFs = options;
    if (cultureMiniPanelState.tab === 'mercado') {
      renderCultureMiniPanel();
    }
  }

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var data = JSON.parse(xhr.responseText);
        var options = [{ sigla: '', nome: 'Brasil (todos)' }];

        if (Array.isArray(data.uf_options) && data.uf_options.length > 0) {
          data.uf_options.forEach(function (u) {
            if (!u || !u.sigla) return;
            options.push({ sigla: u.sigla, nome: u.nome || u.sigla });
          });
        } else if (Array.isArray(data.ufs) && data.ufs.length > 0) {
          data.ufs.forEach(function (sigla) {
            if (!sigla) return;
            options.push({ sigla: sigla, nome: sigla });
          });
        }

        if (options.length > 1) {
          applyUFs(options);
          return;
        }
      } catch (e) {}
    }

    applyUFs(fallbackUFs);
  };

  xhr.onerror = function () {
    applyUFs(fallbackUFs);
  };
  xhr.ontimeout = function () {
    applyUFs(fallbackUFs);
  };
  xhr.send();
};

function destroyMiniPanelCharts() {
  cultureMiniPanelState.marketCards.forEach(function (c) {
    if (c.chartInstance) {
      try {
        c.chartInstance.destroy();
      } catch (e) {}
      c.chartInstance = null;
    }
  });
  (cultureMiniPanelState.productionCards || []).forEach(function (c) {
    if (c.chartInstance) {
      try {
        c.chartInstance.destroy();
      } catch (e) {}
      c.chartInstance = null;
    }
  });
}

function saveMiniChrome() {
  var h = document.getElementById('widget-modal-header');
  var f = document.getElementById('widget-modal-footer');
  if (h && !miniSavedHeaderHTML) miniSavedHeaderHTML = h.innerHTML;
  if (f && !miniSavedFooterHTML) miniSavedFooterHTML = f.innerHTML;
}

function restoreMiniChrome() {
  var h = document.getElementById('widget-modal-header');
  var f = document.getElementById('widget-modal-footer');
  if (h && miniSavedHeaderHTML) h.innerHTML = miniSavedHeaderHTML;
  if (f && miniSavedFooterHTML) f.innerHTML = miniSavedFooterHTML;
  miniSavedHeaderHTML = '';
  miniSavedFooterHTML = '';
}

function renderMiniPanelChrome(culture) {
  var headerEl = document.getElementById('widget-modal-header');
  var footerEl = document.getElementById('widget-modal-footer');
  if (!headerEl || !footerEl || !culture) return;
  var activeTab = cultureMiniPanelState.tab;
  var cultureId = cultureMiniPanelState.cultureId;
  var groupId = cultureMiniPanelState.groupId;

  // ── Header: título + Estado + abas ──
  var tabs = [
    { id: 'mercado', label: 'Mercado' },
    { id: 'minha-producao', label: 'Minha produção' },
  ];
  var tabsHtml = '';
  tabs.forEach(function (t) {
    var cls = t.id === activeTab ? 'mini-pill-tab active' : 'mini-pill-tab';
    tabsHtml +=
      '<button onclick="setMiniPanelTab(\'' +
      t.id +
      '\')" class="' +
      cls +
      '">' +
      t.label +
      '</button>';
  });
  var cadastroUrl = '/guias/vegetal/';
  if (culture && culture.id) {
    var grupo = (culture.django_grupo || 'vegetal').toLowerCase();
    if (grupo === 'animal') cadastroUrl = '/guias/animal/';
    else if (grupo === 'aquatico' || grupo === 'aquática') cadastroUrl = '/guias/aquatica/';
    else cadastroUrl = '/guias/vegetal/';
    cadastroUrl += culture.id + '/';
  }
  tabsHtml +=
    '<a href="' +
    cadastroUrl +
    '" class="mini-pill-tab mini-pill-link" title="Ir para cadastro de cultura"><i class="bi bi-plus-circle"></i> Cadastrar produção</a>';

  var currentUF = sget('ampliagro-culture-uf') || '';
  var ufHtml =
    '<span class="text-[7px] text-slate-500 font-semibold uppercase tracking-wider">Estado</span>';
  ufHtml +=
    '<select class="mini-card-select text-[7px] py-0.5 px-1" onchange="changeGlobalUF(this.value)">';
  var ufOptions =
    cultureMiniPanelState.availableUFs && cultureMiniPanelState.availableUFs.length
      ? cultureMiniPanelState.availableUFs
      : window.CultureData && Array.isArray(CultureData.UF_LIST)
        ? CultureData.UF_LIST
        : [{ sigla: '', nome: 'Brasil (todos)' }];
  ufOptions.forEach(function (u) {
    if (!u) return;
    var sigla = u.sigla || '';
    var nome = u.nome || sigla || 'Brasil (todos)';
    var sel = sigla === currentUF ? ' selected' : '';
    var label = sigla ? sigla + (nome && nome !== sigla ? ' - ' + nome : '') : 'Brasil (todos)';
    ufHtml += '<option value="' + sigla + '"' + sel + '>' + label + '</option>';
  });
  ufHtml += '</select>';

  var h2 = '<div class="flex flex-col gap-1.5 w-full">';
  h2 += '<div class="flex items-center justify-between">';
  h2 += '<div class="flex items-center gap-2 min-w-0">';
  h2 +=
    '<div class="w-6 h-6 flex items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"><i class="bi bi-flower1 text-[11px]"></i></div>';
  h2 +=
    '<div class="min-w-0"><h2 class="text-[12px] font-bold text-slate-800 dark:text-slate-100 truncate">' +
    (culture.title || 'Cultura') +
    '</h2><p class="text-[8px] text-slate-400 dark:text-slate-500">Adicionar widget</p></div>';
  h2 += '</div>';
  h2 +=
    '<button onclick="closeAddWidgetModal()" class="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-all text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"><i class="bi bi-x-lg text-[10px]"></i></button>';
  h2 += '</div>';
  h2 += '<div class="flex items-center justify-between gap-2">';
  h2 += '<div class="flex items-center gap-1.5">' + ufHtml + '</div>';
  h2 += '<div class="flex gap-1.5 overflow-x-auto scrollbar-none">' + tabsHtml + '</div>';
  h2 += '</div>';
  h2 += '</div>';
  headerEl.innerHTML = h2;

  // ── Footer: Voltar + status + ação ──
  var editingW = cultureMiniPanelState.editor && cultureMiniPanelState.editor._editingWidgetId;
  var f2 = '<div class="flex items-center justify-between gap-2 w-full">';
  f2 +=
    '<button onclick="hideCultureMiniPanel()" class="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-200/50 dark:hover:bg-slate-700/50 transition-all text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 relative z-10"><i class="bi bi-arrow-left text-[12px]"></i></button>';
  f2 += '<div class="flex-1 flex justify-center">';
  if (editingW) {
    f2 +=
      '<span class="inline-flex items-center gap-1 px-2.5 py-1 text-[9px] font-semibold rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700/50"><i class="bi bi-patch-check"></i> Já inserido — atualizando este widget</span>';
  } else {
    f2 +=
      '<span class="inline-flex items-center gap-1 px-2.5 py-1 text-[9px] font-medium rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700"><i class="bi bi-plus-circle"></i> Novo widget</span>';
  }
  f2 += '</div>';
  if (activeTab === 'cadastrar') {
    f2 += '<div class="flex items-center gap-2">';
    f2 +=
      '<button onclick="limparFormProducao()" class="px-3 py-1.5 text-[10px] font-medium rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 transition-all"><i class="bi bi-x-circle"></i> Cancelar</button>';
    f2 +=
      '<button onclick="submitMiniPanelRecord(\'' +
      cultureId +
      "','" +
      groupId +
      '\')" class="flex items-center gap-1 px-4 py-1.5 text-[10px] font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition-all"><i class="bi bi-check2"></i> Salvar</button>';
    f2 += '</div>';
  } else {
    if (editingW) {
      f2 +=
        '<button onclick="insertEditorWidget()" class="mini-inserir-btn" style="width:auto;padding:6px 22px"><i class="bi bi-pencil-square"></i> Salvar</button>';
    } else {
      f2 +=
        '<button onclick="insertEditorWidget()" class="mini-inserir-btn" style="width:auto;padding:6px 22px"><i class="bi bi-plus-lg"></i> Inserir widget</button>';
    }
  }
  f2 += '</div>';
  footerEl.innerHTML = f2;
}

function renderCultureMiniPanel() {
  var miniPanel = document.getElementById('culture-mini-panel');
  if (!miniPanel || !cultureMiniPanelState.cultureId) return;
  var cultureId = cultureMiniPanelState.cultureId;
  var groupId = cultureMiniPanelState.groupId;
  var activeTab = cultureMiniPanelState.tab;
  var culture = null;
  if (window.CulturesLoader) culture = CulturesLoader.getCulture(cultureId);
  if (!culture) {
    miniPanel.innerHTML =
      '<p class="text-xs text-slate-400 py-4 text-center">Cultura não encontrada</p>';
    return;
  }

  destroyMiniPanelCharts();
  renderMiniPanelChrome(culture);

  // Ghost live preview — espelha presets: mostra widget como ficará no dashboard
  var ghostCard = editorActiveCard();
  var ghostTitle = ghostCard ? ghostCard.title : culture.title;
  var ghostIcon = culture.icon || 'bi-flower1';
  var ghostColor =
    cultureMiniPanelState.editor.mainColor ||
    (window.chartPalette ? chartPalette().accent : '#0b5e3f');
  var isEditingWidget = !!cultureMiniPanelState.editor._editingWidgetId;
  var ghostLabel = isEditingWidget ? 'Editando: ' + ghostTitle : 'Novo widget: ' + ghostTitle;
  var html =
    '<div class="live-widget-ghost" style="display:flex;align-items:center;gap:10px;padding:10px 12px;margin-bottom:12px;border:1.5px dashed ' +
    ghostColor +
    ';border-radius:10px;background:linear-gradient(135deg, rgba(11,94,63,0.06), transparent);">';
  html +=
    '<div style="width:36px;height:36px;border-radius:8px;background:' +
    ghostColor +
    ';color:#fff;display:grid;place-items:center;flex-shrink:0"><i class="bi ' +
    ghostIcon +
    '"></i></div>';
  html +=
    '<div style="flex:1;min-width:0"><div style="font-size:11px;font-weight:700;color:' +
    ghostColor +
    ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' +
    ghostLabel +
    '</div><div style="font-size:9px;color:var(--cor-texto-medio)">ao vivo — altera ícone/cor/tipo e veja aqui</div></div>';
  html +=
    '<span style="font-size:8px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:' +
    ghostColor +
    ';border:1px solid ' +
    ghostColor +
    ';padding:3px 8px;border-radius:9999px;background:rgba(255,255,255,.7)">' +
    (cultureMiniPanelState.editor.category || 'linha') +
    ' · ' +
    (cultureMiniPanelState.editor.variant || 'suave') +
    '</span>';
  html += '</div>';

  if (activeTab === 'cadastrar') {
    // Cadastrar produção — formulário especialista por grupo (largura total)
    html += '<div class="mini-panel-box">';
    html += renderProductionFormGrouped(cultureId, groupId, culture);
    html += '</div>';

    miniPanel.innerHTML = html;
    return;
  }

  // ── Editor 3 colunas (config | preview | fonte) ──
  html += '<div class="mini-editor">';
  html += renderEditorColConfig();
  html += renderEditorColPreview();
  html += renderEditorColSources(cultureId, groupId);
  html += '</div>';

  miniPanel.innerHTML = html;

  // Carregar dados do card ativo + séries comparadas
  var ed = cultureMiniPanelState.editor;
  if (activeTab === 'mercado') {
    if (cultureMiniPanelState.marketCards[ed.activeCard]) fetchMiniCardData(ed.activeCard);
    ed.compare.forEach(function (c) {
      if (c.kind === 'market' && cultureMiniPanelState.marketCards[c.idx]) fetchMiniCardData(c.idx);
    });
    renderMiniPanelDataReady();
  } else {
    if (cultureMiniPanelState.selectedRecordIds.length > 0) {
      if (cultureMiniPanelState.productionCards[ed.activeCard])
        fetchProductionCardData(ed.activeCard);
      ed.compare.forEach(function (c) {
        if (c.kind === 'production' && cultureMiniPanelState.productionCards[c.idx])
          fetchProductionCardData(c.idx);
      });
    }
    renderMiniPanelDataReady();
  }
}

// Renderiza o preview do editor automaticamente quando os dados chegam
function autoRenderEditorPreview() {
  if (!cultureMiniPanelState || !cultureMiniPanelState.cultureId) return;
  if (typeof renderEditorPreview !== 'function') return;
  if (!document.getElementById('mini-editor-preview')) return;
  try {
    renderEditorPreview();
  } catch (e) {}
}

function renderMiniPanelDataReady() {
  setTimeout(function () {
    autoRenderEditorPreview();
  }, 120);
}

// ══════════════════════════════════════════════════
// EDITOR 3 COLUNAS — helpers
// ══════════════════════════════════════════════════

function editorActiveCard() {
  var ed = cultureMiniPanelState.editor;
  if (cultureMiniPanelState.tab === 'mercado') {
    return cultureMiniPanelState.marketCards[ed.activeCard] || null;
  }
  return cultureMiniPanelState.productionCards[ed.activeCard] || null;
}

function editorSourceCards() {
  var tab = cultureMiniPanelState.tab;
  if (tab === 'mercado') return cultureMiniPanelState.marketCards;
  return cultureMiniPanelState.productionCards;
}

function editorSourceDesc(card) {
  if (!card) return '';
  if (card.desc) return card.desc;
  if (card.source === 'ibge') return 'Dados reais do IBGE / SIDRA para o indicador';
  if (card.source === 'agrodoc') return 'Dados reais do AgroDoc / CEPEA';
  if (card.source === 'cultura') return 'Calculado a partir dos meus registros de produção';
  if (card.source === 'composite') return 'Comparativo entre minha produção e o mercado';
  if (card.source === 'producao') return 'A partir dos registros selecionados da minha produção';
  return card.subtitle || '';
}

function renderEditorColConfig() {
  var ed = cultureMiniPanelState.editor;
  var html = '';
  html += '<div class="mini-editor-col">';

  // Categoria (tipo) — só Linha, Barra, Card e Planilha (e suas variações)
  html +=
    '<div class="mini-editor-col-title"><i class="bi bi-bar-chart"></i> Tipo de gráfico</div>';
  html += '<div class="mini-style-pills">';
  var ALLOWED_CATEGORIES = ['linha', 'barras', 'cartao', 'planilha'];
  var cats =
    window.AmpliChartStyles && AmpliChartStyles.categoriesList
      ? AmpliChartStyles.categoriesList().filter(function (c) {
          return ALLOWED_CATEGORIES.indexOf(c.id) >= 0;
        })
      : [{ id: 'linha', label: 'Linha', icon: 'bi-graph-up' }];
  if (cats.length === 0) cats = [{ id: 'linha', label: 'Linha', icon: 'bi-graph-up' }];
  cats.forEach(function (cat) {
    var active = cat.id === ed.category ? ' active' : '';
    html +=
      '<button class="mini-style-pill' +
      active +
      '" onclick="setEditorCategory(\'' +
      cat.id +
      '\')"><i class="bi ' +
      cat.icon +
      '"></i>' +
      cat.label +
      '</button>';
  });
  html += '</div>';

  // Variantes (radio — seleção única por categoria)
  html += '<div class="mini-editor-section">';
  html +=
    '<div class="mini-editor-col-title"><i class="bi bi-check2-square"></i> Estilo do Gráfico <span class="mini-variant-hint">(selecione um)</span></div>';
  html += '<div class="mini-variant-grid">';
  var catId = ed.category;
  var variants =
    window.AmpliChartStyles && AmpliChartStyles.variantsList
      ? AmpliChartStyles.variantsList(ed.category)
      : [{ id: 'suave', label: 'Suave', desc: 'Curva suave' }];
  if (!variants.length) variants = [{ id: 'suave', label: 'Suave', desc: 'Curva suave' }];
  variants.forEach(function (v) {
    if (v.id === 'comMeta') return; // Será tratado como toggle separado
    var checked = v.id === ed.variant ? ' checked' : '';
    var radioId = 'mv-' + (catId || 'c') + '-' + v.id;
    html +=
      '<input type="radio" name="mini-variant" id="' +
      radioId +
      '" class="mini-variant-radio" ' +
      checked +
      ' onchange="setEditorVariant(\'' +
      v.id +
      '\')">';
    html += '<label for="' + radioId + '" class="mini-variant-chip">';
    html += '<span class="mini-variant-chip-check"><i class="bi bi-check2"></i></span>';
    html += '<span class="mini-variant-chip-text">';
    html += '<span class="mini-variant-check-name">' + v.label + '</span>';
    html += '<span class="mini-variant-check-desc">' + v.desc + '</span>';
    html += '</span>';
    html += '</label>';
  });
  html += '</div>';
  html += '</div>';

  // Cor da série principal e Meta
  html += '<div class="mini-editor-section">';
  html +=
    '<div class="mini-editor-col-title"><i class="bi bi-palette"></i> Configuração da Série</div>';
  var mainColorHex = ed.mainColor || (ed.compare.length ? ed.compare[0].color : '');
  if (!mainColorHex && window.chartPalette) mainColorHex = chartPalette().accent;
  html += '<div class="mini-compare-row mb-1" style="align-items:center">';
  html +=
    '<input type="color" value="' +
    mainColorHex +
    '" class="mini-compare-color" onchange="setMainColor(this.value)">';
  html += '<span class="mini-compare-label">Cor principal</span>';
  html += '</div>';

  // Toggle de Meta
  var metaChecked = ed.hasMeta ? ' checked' : '';
  html += '<label class="mini-compare-row cursor-pointer" style="align-items:center">';
  html +=
    '<input type="checkbox" ' +
    metaChecked +
    ' onchange="setEditorMeta(this.checked)" class="w-3 h-3 rounded border-slate-300 text-emerald-600 focus:ring-emerald-400/20 bg-white">';
  html += '<span class="mini-compare-label">Adicionar linha de meta</span>';
  html += '</label>';
  if (ed.hasMeta) {
    html +=
      '<input type="number" id="mini-meta-input" step="any" value="' +
      (ed.metaValue !== '' && ed.metaValue != null ? ed.metaValue : '') +
      '" oninput="setEditorMetaValue(this.value)" placeholder="Valor da meta (vazio = último ponto)" class="w-full mt-1.5 text-[9px] px-2 py-1.5 rounded-lg border border-slate-200 dark:border-[#1e2a26] bg-slate-50 dark:bg-[#0d1412] text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:border-emerald-400">';
  }
  html += '</div>';

  // Comparar séries
  html += '<div class="mini-editor-section">';
  html += '<div class="mini-editor-col-title"><i class="bi bi-plus-circle"></i> Comparar</div>';
  html += '<div class="mini-compare">';
  ed.compare.forEach(function (c, ci) {
    var label = c.label || 'Série ' + (ci + 1);
    html += '<div class="mini-compare-row">';
    html +=
      '<input type="color" value="' +
      c.color +
      '" class="mini-compare-color" onchange="setCompareColor(' +
      ci +
      ', this.value)">';
    html += '<span class="mini-compare-label" title="' + label + '">' + label + '</span>';
    html +=
      '<button class="mini-compare-remove" onclick="removeCompareSeries(' +
      ci +
      ')"><i class="bi bi-x"></i></button>';
    html += '</div>';
  });
  html += '<div class="mini-compare-add">';
  html += '<select id="mini-compare-select">';
  var cards = editorSourceCards();
  var activeCard = editorActiveCard();
  cards.forEach(function (card, idx) {
    if (card === activeCard) return;
    var label = card.title + (card.subtitle ? ' ' + card.subtitle : '');
    html += '<option value="' + idx + '">' + label + '</option>';
  });
  html += '</select>';
  html +=
    '<button class="mini-add-ok" onclick="addCompareSeries()"><i class="bi bi-plus"></i></button>';
  html += '</div>';
  html += '</div>';
  html += '</div>';

  html += '</div>';
  return html;
}

function renderEditorColPreview() {
  var ed = cultureMiniPanelState.editor;
  var card = editorActiveCard();
  var html = '';
  html += '<div class="mini-editor-col mini-editor-col-fixed">';
  html += '<div class="mini-editor-col-title"><i class="bi bi-eye"></i> Preview</div>';
  if (card) {
    var srcLabel =
      card.source === 'ibge'
        ? 'IBGE'
        : card.source === 'agrodoc'
          ? 'AgroDoc'
          : card.source === 'cultura'
            ? 'Meus dados'
            : card.source === 'composite'
              ? 'Comparativo'
              : '';
    html += '<div class="mini-editor-prevrow">';
    html += '<div style="min-width:0">';
    html +=
      '<div class="lbl">' +
      card.title +
      (card.subtitle ? ' <span style="opacity:0.6">' + card.subtitle + '</span>' : '') +
      '</div>';
    html += '<div class="text-[7px] text-slate-400">' + editorSourceDesc(card) + '</div>';
    html += '</div>';
    html += '<div style="margin-left:auto;text-align:right">';
    html += '<div class="text-[7px] text-slate-400">Prev</div>';
    html += '<span class="val" id="mini-editor-prev-val">—</span>';
    html += '</div>';
    html += '</div>';
  }
  html += '<div class="mini-editor-preview">';
  html += '<canvas id="mini-editor-preview"></canvas>';
  html += '<div id="mini-editor-preview-empty" class="mini-editor-preview-empty">Sem dados</div>';
  html += '</div>';
  html += '</div>';
  return html;
}

function renderEditorColSources(cultureId, groupId) {
  var ed = cultureMiniPanelState.editor;
  var html = '';
  html += '<div class="mini-editor-col">';
  html += '<div class="mini-editor-col-title"><i class="bi bi-database"></i> Fonte de dados</div>';

  if (cultureMiniPanelState.tab === 'minha-producao') {
    // Seleção de registros (checkboxes)
    html += renderProductionCheckboxView(cultureId);
    if (cultureMiniPanelState.selectedRecordIds.length === 0) {
      html +=
        '<div class="text-[8px] text-slate-400 text-center py-3">Selecione registros acima para liberar os cards</div>';
      html += '</div>';
      return html;
    }
    // Registrar colheita (ações sobre os registros selecionados)
    html += '<div class="border-t border-slate-200 dark:border-slate-700 pt-2 mt-2">';
    html +=
      '<button onclick="toggleHarvestForm()" class="text-[9px] text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1"><i class="bi bi-flower2"></i> Registrar Colheita</button>';
    html +=
      '<div id="mini-harvest-form" class="hidden mt-2 p-2 rounded-lg bg-slate-50 dark:bg-emerald-900/20 border border-slate-200 dark:border-slate-700 space-y-1.5">';
    html += '<div class="grid grid-cols-2 gap-2">';
    html +=
      '<div><label class="text-[8px] text-slate-500 font-semibold block mb-0.5">Data da Colheita</label><input type="date" id="mini-harvest-date" class="w-full text-[9px] px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200"></div>';
    html +=
      '<div><label class="text-[8px] text-slate-500 font-semibold block mb-0.5">Quantidade</label><input type="number" step="0.01" id="mini-harvest-qty" placeholder="0,00" class="w-full text-[9px] px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 placeholder:text-slate-400"></div>';
    html += '</div>';
    html +=
      '<div><label class="text-[8px] text-slate-500 font-semibold block mb-0.5">Unidade</label><select id="mini-harvest-unit" class="w-full text-[9px] px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200"><option value="">Selecione...</option><option value="kg">kg</option><option value="sacas">Sacas</option><option value="tonelada">Tonelada</option><option value="litro">Litro</option><option value="unidade">Unidade</option><option value="cabeca">Cabeça</option><option value="arroba">@</option></select></div>';
    html +=
      '<button onclick="submitHarvest(\'' +
      cultureId +
      '\')" class="w-full flex items-center justify-center gap-1 px-2 py-1.5 text-[9px] font-bold rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-all"><i class="bi bi-check2"></i> Confirmar Colheita</button>';
    html += '</div>';
    html += '</div>';
  }

  html += '<div class="mini-source-list">';
  var cards = editorSourceCards();
  cards.forEach(function (card, idx) {
    var active = idx === ed.activeCard ? ' active' : '';
    var color =
      card.source === 'ibge'
        ? '#0f9d6e'
        : card.source === 'agrodoc'
          ? '#3b82f6'
          : card.source === 'cultura'
            ? '#f59e0b'
            : '#8b5cf6';
    var prevId =
      cultureMiniPanelState.tab === 'mercado' ? 'mp-card-prev-' + idx : 'mp-prod-prev-' + idx;
    html +=
      '<button class="mini-source-item' + active + '" onclick="setEditorActiveCard(' + idx + ')">';
    html += '<span class="mini-source-dot" style="background:' + color + '"></span>';
    html += '<div style="min-width:0;flex:1">';
    html += '<div class="mini-source-title">' + card.title + '</div>';
    html += '<div class="mini-source-sub">' + (card.subtitle || '') + '</div>';
    html += '<div class="mini-source-desc">' + editorSourceDesc(card) + '</div>';
    html += '</div>';
    html += '<div style="text-align:right;flex-shrink:0">';
    html += '<div class="text-[6px] text-slate-400">Prev</div>';
    html += '<span id="' + prevId + '" class="mini-source-prev">—</span>';
    html += '</div>';
    html += '</button>';
  });
  html += '</div>';

  // Lógica antiga de meta removida - agora fica na primeira coluna junto com a cor

  html += '</div>';
  return html;
}

// ══════════════════════════════════════════════════
// EDITOR — ações
// ══════════════════════════════════════════════════

window.setEditorCategory = function (cat) {
  var ed = cultureMiniPanelState.editor;
  ed.category = cat;
  var variants =
    window.AmpliChartStyles && AmpliChartStyles.variantsList
      ? AmpliChartStyles.variantsList(cat)
      : [];
  ed.variant = variants.length ? variants[0].id : 'suave';
  renderCultureMiniPanel();
};

window.setEditorVariant = function (variant) {
  cultureMiniPanelState.editor.variant = variant;
  renderEditorPreview();
};

window.setEditorActiveCard = function (idx) {
  cultureMiniPanelState.editor.activeCard = idx;
  renderCultureMiniPanel();
};

window.addCompareSeries = function () {
  var select = document.getElementById('mini-compare-select');
  if (!select) return;
  var idx = parseInt(select.value, 10);
  var cards = editorSourceCards();
  if (!cards[idx] || cards[idx] === editorActiveCard()) return;
  var pal = chartPalette();
  var usedColors = cultureMiniPanelState.editor.compare.map(function (c) {
    return c.color;
  });
  var mainHex = cultureMiniPanelState.editor.mainColor || pal.accent || '';
  if (usedColors.indexOf(mainHex) < 0) usedColors.push(mainHex);
  var color = pal.pie[0];
  for (var i = 0; i < pal.pie.length; i++) {
    if (usedColors.indexOf(pal.pie[i]) < 0) {
      color = pal.pie[i];
      break;
    }
  }
  if (usedColors.indexOf(color) >= 0) {
    color = pal.pie[1] || color;
  }
  cultureMiniPanelState.editor.compare.push({
    kind: cultureMiniPanelState.tab === 'mercado' ? 'market' : 'production',
    idx: idx,
    label: cards[idx].title + (cards[idx].subtitle ? ' ' + cards[idx].subtitle : ''),
    color: color,
  });
  renderCultureMiniPanel();
};

window.removeCompareSeries = function (ci) {
  cultureMiniPanelState.editor.compare.splice(ci, 1);
  renderCultureMiniPanel();
};

window.setMainColor = function (color) {
  cultureMiniPanelState.editor.mainColor = color;
  renderEditorPreview();
};

window.setCompareColor = function (ci, color) {
  var c = cultureMiniPanelState.editor.compare[ci];
  if (!c) return;
  c.color = color;
  renderEditorPreview();
};

window.setEditorMeta = function (checked) {
  cultureMiniPanelState.editor.hasMeta = checked;
  renderCultureMiniPanel();
};

window.setEditorMetaValue = function (val) {
  cultureMiniPanelState.editor.metaValue = val;
  renderEditorPreview();
};

window.insertEditorWidget = function () {
  var ed = cultureMiniPanelState.editor;
  var editId = ed && ed._editingWidgetId ? ed._editingWidgetId : null;
  if (cultureMiniPanelState.tab === 'mercado') {
    addWidgetFromMiniCard(ed.activeCard, cultureMiniPanelState.cultureId, editId);
  } else {
    addWidgetFromProductionCard(ed.activeCard, cultureMiniPanelState.cultureId, editId);
  }
};

// ══════════════════════════════════════════════════
// EDITOR — preview (desenha no canvas único)
// ══════════════════════════════════════════════════

window.renderEditorPreview = function () {
  var ed = cultureMiniPanelState.editor;
  var canvas = document.getElementById('mini-editor-preview');
  if (!canvas) return;

  if (ed.previewChart) {
    try {
      ed.previewChart.destroy();
    } catch (e) {}
    ed.previewChart = null;
  }

  var card = editorActiveCard();
  var emptyEl = document.getElementById('mini-editor-preview-empty');
  if (!card) {
    if (emptyEl) emptyEl.style.display = 'flex';
    return;
  }

  var variant =
    window.AmpliChartStyles && AmpliChartStyles.variant
      ? AmpliChartStyles.variant(ed.category, ed.variant)
      : null;
  var baseType = variant ? variant.type : 'line';
  var isCircular = ['pie', 'doughnut', 'polarArea'].indexOf(baseType) >= 0;
  var isScatter = baseType === 'scatter' || baseType === 'bubble';

  var hist = card.history || [];
  var hasUser = !!card.myHistory && card.myHistory.length > 0;
  var cardComp =
    cultureMiniPanelState.tab === 'minha-producao' &&
    card &&
    (card._comparative || card.metricKey === 'comparativo') &&
    card._records &&
    card._records.length > 0
      ? card._records
      : null;
  var hasData =
    (hist.length > 0 && (hist[0].valor || hist[0].valor === 0)) ||
    hasUser ||
    (!!cardComp && cardComp.length > 0);
  if (!hasData) {
    if (emptyEl) emptyEl.style.display = 'flex';
    var prevVal = document.getElementById('mini-editor-prev-val');
    if (prevVal) prevVal.textContent = '—';
    return;
  }
  if (emptyEl) emptyEl.style.display = 'none';

  var htmlContainer = document.getElementById('mini-editor-preview-html');
  if (!htmlContainer) {
    htmlContainer = document.createElement('div');
    htmlContainer.id = 'mini-editor-preview-html';
    htmlContainer.style.width = '100%';
    htmlContainer.style.height = '100%';
    canvas.parentNode.insertBefore(htmlContainer, canvas);
  }

  if (baseType === 'html') {
    canvas.style.display = 'none';
    htmlContainer.style.display = 'block';

    var lastVal = hist.length > 0 ? hist[hist.length - 1].valor : 0;
    var lastValStr =
      typeof lastVal === 'number'
        ? lastVal.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
        : lastVal != null
          ? String(lastVal)
          : '—';
    var metricLabel = card.metricLabel || card.title || '';
    var subtitle = card.subtitle || '';

    if (ed.category === 'cartao') {
      if (window.buildModernKpiHtml) {
        htmlContainer.innerHTML = window.buildModernKpiHtml(
          metricLabel,
          lastValStr,
          subtitle,
          '',
          true
        );
      } else {
        htmlContainer.innerHTML =
          '<div class="flex flex-col justify-center h-full p-4"><span class="text-xs text-slate-500">' +
          metricLabel +
          '</span><div class="text-2xl font-bold">' +
          lastValStr +
          '</div></div>';
      }
    } else if (ed.category === 'planilha') {
      if (ed.variant === 'anos' || ed.variant === 'fatores') {
        var vLabel = ed.variant === 'anos' ? 'Anos' : 'Fatores';
        htmlContainer.innerHTML =
          '<div class="flex items-center justify-center h-full p-4 text-xs text-slate-500 text-center flex-col gap-2"><i class="bi bi-layout-text-window text-2xl"></i>Planilha com Abas (' +
          vLabel +
          ')<br><span class="text-[9px]">A prévia completa da matriz será renderizada no Dashboard após a inserção.</span></div>';
      } else {
        var tb =
          '<div class="overflow-auto h-full w-full text-xs p-2"><table class="w-full"><thead><tr class="border-b text-slate-500 text-left"><th class="py-1">Ano</th><th class="py-1 text-right">Valor</th></tr></thead><tbody>';
        hist
          .slice()
          .reverse()
          .forEach(function (h) {
            var v =
              typeof h.valor === 'number'
                ? h.valor.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
                : h.valor != null
                  ? String(h.valor)
                  : '—';
            tb +=
              '<tr><td class="py-1 text-slate-700 dark:text-slate-300">' +
              (h.ano || '-') +
              '</td><td class="py-1 text-right font-medium text-emerald-600">' +
              v +
              '</td></tr>';
          });
        tb += '</tbody></table></div>';
        htmlContainer.innerHTML = tb;
      }
    }

    var prevVal2 = document.getElementById('mini-editor-prev-val');
    if (prevVal2) prevVal2.textContent = lastValStr;
    return;
  } else {
    canvas.style.display = 'block';
    htmlContainer.style.display = 'none';
  }

  var pal = chartPalette();
  var labels = hist.map(function (h) {
    return h.ano;
  });
  var data = hist.map(function (h) {
    return h.valor;
  });

  // Alinhar labels com histórico do usuário quando existir
  var datasets = [];
  var mainColor = ed.mainColor || (ed.compare.length ? ed.compare[0].color : pal.accent);
  var usedColors = [mainColor];

  function editorPickColor(fallback) {
    var cand = fallback || pal.pie[0];
    for (var i = 0; i < pal.pie.length; i++) {
      if (usedColors.indexOf(pal.pie[i]) < 0) {
        cand = pal.pie[i];
        break;
      }
    }
    usedColors.push(cand);
    return cand;
  }

  function editorApplyGrad(ds, color) {
    if (!ds._gradientLine || isCircular) return ds;
    var g =
      window.AmpliChartStyles && AmpliChartStyles.makeGradient
        ? AmpliChartStyles.makeGradient(canvas, color || ds.borderColor, 0.35, 0.02)
        : null;
    if (g) {
      ds.backgroundColor = g;
      ds.fill = 'origin';
    }
    return ds;
  }

  // Comparação talhão x talhão (card de produção favoritado com 2+ registros)
  if (cardComp && !isCircular && !isScatter && ['line', 'bar'].indexOf(baseType) >= 0) {
    var compLabels =
      card._dates ||
      Array.prototype.concat.apply(
        [],
        cardComp.map(function (r) {
          return r.plantingDate || '—';
        })
      );
    compLabels.forEach(function (d) {
      if (labels.indexOf(d) < 0) labels.push(d);
    });
    cardComp.forEach(function (r) {
      var c = editorPickColor();
      var d = labels.map(function (dd) {
        return (r.plantingDate || '—') === dd ? r.quantity || 0 : null;
      });
      var cd = {
        label: r.name || r.location || 'Talhão',
        data: d,
        borderColor: c,
        fill: false,
        pointRadius: 2,
        pointBackgroundColor: c,
        borderWidth: 1.5,
      };
      if (baseType === 'bar') {
        cd.backgroundColor = hexToRgba(c, 0.6);
      }
      if (baseType === 'line') {
        cd.tension = 0.35;
        if (window.AmpliChartStyles)
          AmpliChartStyles.applyDataset(cd, ed.category, ed.variant, { color: c });
      }
      cd.fill = false;
      editorApplyGrad(cd, c);
      datasets.push(cd);
    });
  } else if (isCircular) {
    var bg = pal.pie.slice(0, data.length);
    datasets.push({
      label: card.title,
      data: data,
      backgroundColor: bg,
      borderColor: pal.isDark ? '#000' : '#fdfefe',
      borderWidth: 2,
    });
  } else if (isScatter) {
    datasets.push({
      label: card.title,
      data: data.map(function (v, i) {
        return { x: labels[i], y: v };
      }),
    });
  } else {
    var dsMain = { label: card.title, data: data.slice() };
    if (window.AmpliChartStyles)
      AmpliChartStyles.applyDataset(dsMain, ed.category, ed.variant, {
        color: mainColor,
        highlight: true,
      });
    if (baseType === 'bar' && !dsMain.backgroundColor) dsMain.backgroundColor = mainColor;
    if (baseType === 'line' && !dsMain.borderColor) dsMain.borderColor = mainColor;
    editorApplyGrad(dsMain, mainColor);
    if (hasUser) {
      var ud = card.myHistory.map(function (h) {
        return h.valor;
      });
      var ul = card.myHistory.map(function (h) {
        return h.ano;
      });
      var aligned = labels.map(function (l) {
        var i = ul.indexOf(l);
        return i >= 0 ? ud[i] : null;
      });
      var userCol = editorPickColor(pal.pie[1] || '#3b82f6');
      var dsUser = { label: 'Propriedade', data: aligned };
      if (window.AmpliChartStyles)
        AmpliChartStyles.applyDataset(dsUser, ed.category, ed.variant, {
          color: userCol,
          highlight: true,
        });
      editorApplyGrad(dsUser, userCol);
      datasets.push(dsUser);
    }
    datasets.push(dsMain);
  }

  // Séries comparadas
  var edTab = cultureMiniPanelState.tab;
  ed.compare.forEach(function (c) {
    var srcCard =
      c.kind === 'market'
        ? cultureMiniPanelState.marketCards[c.idx] || null
        : cultureMiniPanelState.productionCards[c.idx] || null;
    if (!srcCard || !srcCard.history) return;
    var ch = srcCard.history;
    if (isCircular) {
      datasets.push({
        label: c.label,
        data: ch.map(function (h) {
          return h.valor;
        }),
        backgroundColor: pal.pie,
        borderColor: pal.isDark ? '#000' : '#fdfefe',
        borderWidth: 2,
      });
    } else if (isScatter) {
      datasets.push({
        label: c.label,
        data: ch.map(function (h) {
          return { x: h.ano, y: h.valor };
        }),
      });
    } else {
      var cc = editorPickColor(c.color || '');
      var cd = {
        label: c.label,
        data: ch.map(function (h) {
          return h.valor;
        }),
      };
      if (window.AmpliChartStyles)
        AmpliChartStyles.applyDataset(cd, ed.category, ed.variant, { color: cc });
      cd.fill = false;
      editorApplyGrad(cd, cc);
      datasets.push(cd);
    }
    ch.forEach(function (h) {
      if (labels.indexOf(h.ano) < 0) labels.push(h.ano);
    });
  });

  if (datasets.length === 1 && datasets[0].data.length === 1) {
    datasets[0].data.unshift(datasets[0].data[0]);
    labels.unshift('');
  }

  var opts = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false, axis: 'x' },
    plugins: { tooltip: { enabled: false } },
    scales: {},
  };

  if (window.AmpliChartStyles && AmpliChartStyles.options) {
    var styleOpts = AmpliChartStyles.options(ed.category, ed.variant, pal, {
      legend: datasets.length > 1 || (variant && variant.legend),
    });
    if (styleOpts && styleOpts.plugins) opts.plugins = styleOpts.plugins;
    if (styleOpts && styleOpts.indexAxis) opts.indexAxis = styleOpts.indexAxis;
  }
  if (!opts.plugins.legend)
    opts.plugins.legend = {
      display: datasets.length > 1,
      position: 'bottom',
      labels: {
        boxWidth: 20,
        padding: 10,
        font: { size: 11 },
        usePointStyle: true,
        pointStyle: 'line',
        color: pal.tick,
      },
    };
  else if (datasets.length > 1 && opts.plugins.legend.display === false) {
    opts.plugins.legend.display = true;
  }

  if (!isCircular) {
    opts.scales.x = {
      display: true,
      grid: { display: false },
      border: { display: false },
      ticks: { font: { size: 9 }, color: pal.tick, maxRotation: 0, autoSkip: true, padding: 4 },
    };
    opts.scales.y = {
      display: true,
      grid: { display: false },
      border: { display: false },
      ticks: { font: { size: 9 }, color: pal.tick, padding: 4 },
    };
    var mLabel = getMetricLabels(card.metricKey || '');
  }
  opts.layout = { padding: { top: 24, bottom: 4, left: 2, right: 2 } };

  var cfg = { type: baseType, data: { labels: labels, datasets: datasets }, options: opts };
  if (!isCircular && baseType === 'doughnut') {
    cfg.type = 'line';
  }
  var hasEditorMeta =
    ed.hasMeta &&
    ed.metaValue !== '' &&
    ed.metaValue !== null &&
    ed.metaValue !== undefined &&
    !isNaN(parseFloat(ed.metaValue));
  if (hasEditorMeta && !isCircular) {
    opts.plugins.ampliReference = {
      metaLines: [{ value: parseFloat(ed.metaValue), color: '#d93a3a', label: 'Meta' }],
    };
  } else if (ed.hasMeta && !isCircular) {
    var lastVal = data[data.length - 1];
    opts.plugins.ampliReference = {
      metaLines: [{ value: lastVal, color: pal.alert, label: 'Meta' }],
    };
  }
  var cutout = window.AmpliChartStyles
    ? AmpliChartStyles.cutout(ed.category, ed.variant)
    : undefined;
  if (cutout) opts.cutout = cutout;
  var rotation = window.AmpliChartStyles
    ? AmpliChartStyles.rotation(ed.category, ed.variant)
    : undefined;
  if (rotation != null) opts.rotation = rotation;
  var circumference = window.AmpliChartStyles
    ? AmpliChartStyles.circumference(ed.category, ed.variant)
    : undefined;
  if (circumference != null) opts.circumference = circumference;

  try {
    var ctx = canvas.getContext('2d');
    ed.previewChart = new Chart(ctx, cfg);
    var prevVal = document.getElementById('mini-editor-prev-val');
    if (prevVal) {
      var pv = data[data.length - 1];
      prevVal.textContent =
        typeof pv === 'number'
          ? pv.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
          : pv != null
            ? String(pv)
            : '—';
    }
  } catch (e) {
    if (emptyEl) {
      emptyEl.style.display = 'flex';
      emptyEl.innerHTML =
        '<span class="text-[8px] text-slate-400">Erro ao renderizar preview</span>';
    }
  }
};

function renderMarketCard(card, idx, cultureId) {
  var html = '';
  html += '<div class="mini-card">';
  // LEFT: controles
  html += '<div class="mini-card-left">';
  html +=
    '<div><span class="font-bold text-slate-800" style="font-size:11px">' + card.title + '</span>';
  if (card.subtitle)
    html +=
      ' <span class="text-slate-500 ml-0.5" style="font-size:7px">' + card.subtitle + '</span>';
  var starredMarket = isCardStarred('market', idx);
  html +=
    ' <button class="mini-star-btn' +
    (starredMarket ? ' active' : '') +
    '" onclick="toggleCardStar(\'market\', ' +
    idx +
    ')" title="Favoritar (habilita meta/comparação)"><i class="bi ' +
    (starredMarket ? 'bi-star-fill' : 'bi-star') +
    '"></i></button>';
  html += ' <span class="text-[8px] text-slate-500 ml-1">Prev:</span>';
  html +=
    ' <span id="mp-card-prev-' +
    idx +
    '" class="text-[9px] font-bold text-slate-800">—</span></div>';
  // Source indicator ( always visible )
  var src = card.source || '';
  if (src === 'ibge') {
    html +=
      '<div class="text-[6px] font-bold text-emerald-700 bg-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-300 rounded px-1 py-0.5 mt-0.5 inline-block">IBGE</div>';
  } else if (src === 'agrodoc') {
    html +=
      '<div class="text-[6px] font-bold text-blue-700 bg-blue-100 dark:bg-blue-900/30 dark:text-blue-300 rounded px-1 py-0.5 mt-0.5 inline-block">AgroDoc</div>';
  } else if (src === 'no_data') {
    html +=
      '<div class="text-[6px] font-bold text-slate-600 bg-slate-100 dark:bg-slate-800 dark:text-slate-300 rounded px-1 py-0.5 mt-0.5 inline-block">Sem dados reais</div>';
  }
  // Toggle 3 posicoes
  html += '<div class="mini-toggle">';
  ['grafico', 'lista', 'tabela'].forEach(function (t) {
    var label = t === 'grafico' ? 'gráfico' : t === 'tabela' ? 'tabela' : 'lista';
    var cls = card.widgetType === t ? ' active' : '';
    html +=
      '<button class="' +
      cls +
      '" onclick="selectMiniCardWidgetType(' +
      idx +
      ", '" +
      t +
      '\')">' +
      label +
      '</button>';
  });
  html += '</div>';
  // Dropdown subtipo de grafico
  if (card.widgetType === 'grafico') {
    var chartTypes = [
      { id: 'line', label: 'Linha' },
      { id: 'bar', label: 'Barra' },
      { id: 'doughnut', label: 'Rosca' },
      { id: 'pie', label: 'Pizza' },
      { id: 'radar', label: 'Radar' },
      { id: 'polarArea', label: 'Polar' },
    ];
    html +=
      '<select class="mini-card-select" onchange="selectChartSubtype(' +
      idx +
      ", this.value, 'market')\">";
    chartTypes.forEach(function (ct) {
      var sel = (card.chartSubtype || 'line') === ct.id ? ' selected' : '';
      html += '<option value="' + ct.id + '"' + sel + '>' + ct.label + '</option>';
    });
    html += '</select>';
  }
  // Select UF (mercado)
  var sourceLabel =
    card.source === 'cultura'
      ? 'Meus dados'
      : card.source === 'composite'
        ? 'Comparativo'
        : (card.source || 'mercado').toUpperCase();
  if (card.source === 'ibge' || card.source === 'agrodoc') {
    html +=
      '<select class="mini-card-select" onchange="changeMiniCardUf(' + idx + ', this.value)">';
    html += '<option value="">' + sourceLabel + '</option>';
    var ufOptions =
      cultureMiniPanelState.availableUFs && cultureMiniPanelState.availableUFs.length
        ? cultureMiniPanelState.availableUFs
        : window.CultureData && Array.isArray(CultureData.UF_LIST)
          ? CultureData.UF_LIST
          : [];
    ufOptions.forEach(function (u) {
      if (!u) return;
      var sigla = u.sigla || '';
      if (!sigla) return;
      var nome = u.nome || sigla;
      var sel = sigla === card.selectedUf ? ' selected' : '';
      html += '<option value="' + sigla + '"' + sel + '>' + sigla + ' - ' + nome + '</option>';
    });
    html += '</select>';
  }
  // Inserir / Salvar edição (quando já existe no preset)
  if (card.source === 'no_data') {
    html +=
      '<button class="mini-inserir-btn opacity-50 cursor-not-allowed" disabled title="Sem dados reais disponíveis">Inserir</button>';
  } else {
    var widBtn = marketWidgetIdFor(idx, cultureId);
    var normWidBtn = String(widBtn)
      .replace(/^cult_/, 'cult-')
      .replace(/gafico/g, 'grafico');
    var existsBtn =
      !!(widBtn && window.widgets && widgets[widBtn] && widgets[widBtn].visible) ||
      !!(normWidBtn && window.widgets && widgets[normWidBtn] && widgets[normWidBtn].visible) ||
      !!(
        widBtn &&
        window.widgets &&
        Object.keys(window.widgets).some(function (k) {
          return (
            String(k)
              .replace(/^cult_/, 'cult-')
              .replace(/gafico/g, 'grafico') === normWidBtn
          );
        })
      );
    var ed2 = cultureMiniPanelState.editor;
    var normEditId =
      ed2 && ed2._editingWidgetId
        ? String(ed2._editingWidgetId)
            .replace(/^cult_/, 'cult-')
            .replace(/gafico/g, 'grafico')
        : null;
    var isEditingThis = !!(ed2 && ed2._editingWidgetId && normWidBtn === normEditId);
    var btnLabelM = isEditingThis ? 'Salvar' : existsBtn ? 'Salvar' : 'Inserir';
    var editArgM = isEditingThis ? ", '" + ed2._editingWidgetId + "'" : '';
    html +=
      '<button class="mini-inserir-btn" onclick="addWidgetFromMiniCard(' +
      idx +
      ", '" +
      cultureId +
      "'" +
      editArgM +
      ')">' +
      btnLabelM +
      '</button>';
  }
  html += '</div>';
  // RIGHT: preview
  html += '<div class="mini-card-right">';
  html += '<canvas id="mp-card-chart-' + idx + '"></canvas>';
  html +=
    '<div id="mp-card-placeholder-' +
    idx +
    '" class="mini-chart-placeholder"><span class="text-[8px] text-slate-400">Sem dados</span></div>';
  html += '</div>';
  html += '</div>';
  return html;
}

function miniNumber(value) {
  if (typeof value === 'number') return isFinite(value) ? value : null;
  if (value === null || value === undefined) return null;

  var s = String(value).trim();
  if (!s || s === '—' || s === '-') return null;
  s = s.replace(/R\$/g, '').replace(/\s/g, '');

  if (s.indexOf(',') >= 0 && s.indexOf('.') >= 0) {
    s = s.replace(/\./g, '').replace(',', '.');
  } else if (s.indexOf(',') >= 0) {
    s = s.replace(',', '.');
  }

  s = s.replace(/[^0-9.-]/g, '');
  if (!s || s === '-' || s === '.' || s === '-.') return null;

  var n = parseFloat(s);
  return isFinite(n) ? n : null;
}

function miniYear(value) {
  if (!value) return '';
  var m = String(value).match(/(19|20)\d{2}/);
  return m ? m[0] : '';
}

function miniRecordYear(record) {
  if (!record) return '';
  return miniYear(record.date || record.plantingDate || record.createdAt || record.updatedAt);
}

function miniPickNumber(obj, keys) {
  if (!obj || !Array.isArray(keys)) return null;
  for (var i = 0; i < keys.length; i++) {
    var k = keys[i];
    if (obj[k] !== undefined && obj[k] !== null) {
      var n = miniNumber(obj[k]);
      if (n !== null) return n;
    }
    if (obj.fields && obj.fields[k] !== undefined && obj.fields[k] !== null) {
      var nf = miniNumber(obj.fields[k]);
      if (nf !== null) return nf;
    }
  }
  return null;
}

function miniExtractArea(record) {
  return miniPickNumber(record, ['areaHa', 'exploredArea', 'area', 'hectares']);
}

function miniExtractUnitPrice(record) {
  var val = miniPickNumber(record, [
    'unitPrice',
    'price',
    'preco',
    'valorUnitario',
    'valor_unitario',
    'valorSaca',
    'precoSaca',
  ]);
  if (val !== null && val > 0) return val;
  if (window.ProductRegistry && record && record.cultureId) {
    var cultureName = record.cultureId.replace('cultura-', '').replace(/-/g, ' ').toLowerCase();
    var products = ProductRegistry.getAll();
    for (var i = 0; i < products.length; i++) {
      if (products[i].nome && products[i].nome.toLowerCase().indexOf(cultureName) >= 0) {
        var pv = parseFloat(products[i].preco);
        if (pv > 0) return pv;
      }
    }
  }
  return val;
}

function miniExtractRevenue(record) {
  var direct = miniPickNumber(record, ['revenue', 'receita', 'valorTotal', 'totalValue', 'valor']);
  if (direct !== null) return direct;

  var qty = miniPickNumber(record, ['quantity', 'qty']);
  var price = miniExtractUnitPrice(record);
  if (qty !== null && price !== null) return qty * price;

  return null;
}

function buildPropertyHistoryByMetric(cultureId, metricKey) {
  if (!window.ProductionRegistry) return [];

  var records = ProductionRegistry.getByCultureSorted(cultureId);
  if (!records || records.length === 0) return [];

  var byYear = {};
  function ensureYear(year) {
    if (!year) return null;
    if (!byYear[year]) {
      byYear[year] = {
        sumQty: 0,
        qtyCount: 0,
        sumArea: 0,
        areaCount: 0,
        sumRevenue: 0,
        revenueCount: 0,
        sumUnitPrice: 0,
        unitPriceCount: 0,
      };
    }
    return byYear[year];
  }

  records.forEach(function (record) {
    var recordYear = miniRecordYear(record);
    if (!recordYear && Array.isArray(record.harvests) && record.harvests.length > 0) {
      recordYear = miniYear(record.harvests[0].date);
    }

    var bucket = ensureYear(recordYear);
    if (bucket) {
      var area = miniExtractArea(record);
      if (area !== null) {
        bucket.sumArea += area;
        bucket.areaCount += 1;
      }

      var revenue = miniExtractRevenue(record);
      if (revenue !== null) {
        bucket.sumRevenue += revenue;
        bucket.revenueCount += 1;
      }

      var price = miniExtractUnitPrice(record);
      if (price !== null) {
        bucket.sumUnitPrice += price;
        bucket.unitPriceCount += 1;
      }
    }

    var hasHarvestQty = false;
    if (Array.isArray(record.harvests) && record.harvests.length > 0) {
      record.harvests.forEach(function (h) {
        var harvestYear = miniYear(h.date) || recordYear;
        var hb = ensureYear(harvestYear);
        if (!hb) return;

        var hq = miniPickNumber(h, ['quantity', 'qty']);
        if (hq !== null) {
          hb.sumQty += hq;
          hb.qtyCount += 1;
          hasHarvestQty = true;
        }

        var hp = miniPickNumber(h, [
          'unitPrice',
          'price',
          'preco',
          'valorUnitario',
          'valor_unitario',
        ]);
        if (hp !== null) {
          hb.sumUnitPrice += hp;
          hb.unitPriceCount += 1;
        }

        var hr = miniPickNumber(h, ['revenue', 'receita', 'total', 'valor']);
        if (hr !== null) {
          hb.sumRevenue += hr;
          hb.revenueCount += 1;
        }
      });
    }

    if (!hasHarvestQty && bucket) {
      var qty = miniPickNumber(record, ['quantity', 'qty']);
      if (qty !== null) {
        bucket.sumQty += qty;
        bucket.qtyCount += 1;
      }
    }
  });

  var years = Object.keys(byYear)
    .sort(function (a, b) {
      var na = parseInt(a, 10);
      var nb = parseInt(b, 10);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return String(a).localeCompare(String(b), 'pt-BR', { numeric: true });
    })
    .slice(-8);

  var out = [];
  years.forEach(function (year) {
    var y = byYear[year];
    var val = null;

    if (
      metricKey === 'producao_total' ||
      metricKey === 'minha_produt' ||
      metricKey === 'comparativo'
    ) {
      val = y.qtyCount > 0 ? y.sumQty : null;
    } else if (metricKey === 'area_plantada') {
      val = y.areaCount > 0 ? y.sumArea : null;
    } else if (metricKey === 'produtividade') {
      val = y.qtyCount > 0 && y.areaCount > 0 && y.sumArea > 0 ? y.sumQty / y.sumArea : null;
    } else if (metricKey === 'receita_estimada') {
      if (y.revenueCount > 0) {
        val = y.sumRevenue;
      } else if (y.qtyCount > 0 && y.unitPriceCount > 0) {
        val = y.sumQty * (y.sumUnitPrice / y.unitPriceCount);
      }
    } else if (metricKey === 'valor_saca') {
      val = y.unitPriceCount > 0 ? y.sumUnitPrice / y.unitPriceCount : null;
    } else {
      val = y.qtyCount > 0 ? y.sumQty : null;
    }

    if (val !== null && isFinite(val)) {
      out.push({ ano: String(year), valor: Math.round(val * 100) / 100 });
    }
  });

  return out;
}

function fetchMiniCardData(cardIdx) {
  var card = cultureMiniPanelState.marketCards[cardIdx];
  var cultureId = cultureMiniPanelState.cultureId;
  var prevEl = document.getElementById('mp-card-prev-' + cardIdx);
  var canvas = document.getElementById('mp-card-chart-' + cardIdx);
  var placeholder = document.getElementById('mp-card-placeholder-' + cardIdx);

  function showNoData(message) {
    if (prevEl) prevEl.textContent = '—';
    if (placeholder) {
      placeholder.style.display = 'flex';
      placeholder.innerHTML =
        '<span class="text-[8px] text-slate-400">' + (message || 'Sem dados reais') + '</span>';
    }
    if (canvas) canvas.style.display = 'none';
    card.history = [];
    card.myHistory = [];
    autoRenderEditorPreview();
  }

  function parseNumeric(value) {
    var n = miniNumber(value);
    return n === null ? NaN : n;
  }

  if (card.source === 'cultura') {
    var ownHist = buildPropertyHistoryByMetric(cultureId, 'produtividade');
    if (!ownHist.length) ownHist = buildPropertyHistoryByMetric(cultureId, 'producao_total');
    if (ownHist.length === 0) {
      showNoData();
      return;
    }

    card.history = ownHist;
    card.myHistory = [];

    if (prevEl) {
      var ownLast = ownHist[ownHist.length - 1];
      prevEl.textContent =
        ownLast && typeof ownLast.valor === 'number' ? ownLast.valor.toLocaleString('pt-BR') : '—';
    }

    renderMiniCardChart(cardIdx);
    return;
  }

  if (card.source === 'composite') {
    if (
      !window.CultureData ||
      !window.ProductionRegistry ||
      typeof CultureData.getMetricsBySource !== 'function'
    ) {
      showNoData('Sem dados reais para comparação');
      return;
    }

    var ufComp = card.selectedUf || '';
    var sourceForCompare =
      window.CultureData && CultureData.hasIBGEMapping && CultureData.hasIBGEMapping(cultureId)
        ? 'ibge'
        : 'auto';
    CultureData.init()
      .then(function () {
        return CultureData.getMetricsBySource(cultureId, sourceForCompare, ufComp, {
          realOnly: true,
        });
      })
      .then(function (result) {
        var metrics = result.metrics || [];
        if (result._source === 'no_data' || result.source === 'no_data' || metrics.length === 0) {
          showNoData('Sem dados reais para comparação');
          return;
        }

        var stateMetric = null;
        for (var i = 0; i < metrics.length; i++) {
          if (
            metrics[i].key === 'produtividade' ||
            metrics[i].key === 'producao_total' ||
            metrics[i].key === 'valor_saca'
          ) {
            stateMetric = metrics[i];
            break;
          }
        }
        if (!stateMetric && metrics.length > 0) stateMetric = metrics[0];
        if (!stateMetric) {
          showNoData('Sem indicador comparável');
          return;
        }

        var stateHistory = [];
        if (
          result.history_by_metric &&
          Array.isArray(result.history_by_metric.produtividade) &&
          result.history_by_metric.produtividade.length > 0
        ) {
          stateHistory = result.history_by_metric.produtividade;
        } else if (
          result.history_by_metric &&
          Array.isArray(result.history_by_metric.producao_total) &&
          result.history_by_metric.producao_total.length > 0
        ) {
          stateHistory = result.history_by_metric.producao_total;
        } else if (Array.isArray(result.history) && result.history.length > 0) {
          stateHistory = result.history;
        }

        var myHistory = buildPropertyHistoryByMetric(cultureId, 'produtividade');
        if (!myHistory.length)
          myHistory = buildPropertyHistoryByMetric(cultureId, 'producao_total');

        if (stateHistory.length > 0) {
          card.data = result;
          card.history = stateHistory;
          card.myHistory = myHistory;

          var sLast = stateHistory[stateHistory.length - 1];
          var sVal = sLast ? parseNumeric(sLast.valor) : NaN;
          var mVal =
            myHistory.length > 0 ? parseNumeric(myHistory[myHistory.length - 1].valor) : NaN;
          if (prevEl && isFinite(mVal) && isFinite(sVal) && sVal !== 0) {
            var d = (((mVal - sVal) / sVal) * 100).toFixed(1);
            prevEl.textContent = (d > 0 ? '+' + d : d) + '%';
          } else if (prevEl) {
            prevEl.textContent = '—';
          }

          renderMiniCardChart(cardIdx);
          return;
        }

        var records = ProductionRegistry.getByCultureSorted(cultureId);
        var myProd = 0;
        var myCount = 0;
        records.forEach(function (r) {
          if (r.quantity) {
            myProd += r.quantity;
            myCount++;
          }
        });

        var myAvg = myCount > 0 ? myProd / myCount : 0;
        var stateVal = parseNumeric(stateMetric.value);
        if (!isFinite(stateVal)) stateVal = 0;

        card.data = result;
        var diff =
          myAvg > 0 && stateVal > 0 ? (((myAvg - stateVal) / stateVal) * 100).toFixed(1) : '—';
        if (prevEl) prevEl.textContent = diff !== '—' ? (diff > 0 ? '+' + diff : diff) + '%' : '—';

        card.myHistory = [];
        card.history = [
          { ano: 'Meu', valor: myAvg },
          { ano: stateMetric.label || 'Estado', valor: stateVal },
        ];
        renderMiniCardChart(cardIdx);
      })
      .catch(function () {
        showNoData('Sem dados reais para comparação');
      });
    return;
  }

  if (!window.CultureData || typeof CultureData.getMetricsBySource !== 'function') {
    showNoData('Sem dados reais para este indicador');
    return;
  }

  var uf = card.selectedUf || '';

  CultureData.init()
    .then(function () {
      return CultureData.getMetricsBySource(cultureId, card.source || 'auto', uf, {
        realOnly: true,
      });
    })
    .then(function (result) {
      card.data = result;
      var metrics = result.metrics || [];
      card.myHistory = buildPropertyHistoryByMetric(cultureId, card.metricKey);

      if (result._source === 'no_data' || result.source === 'no_data' || metrics.length === 0) {
        showNoData('Sem dados reais para este indicador');
        return;
      }

      var m = null;
      for (var i = 0; i < metrics.length; i++) {
        if (metrics[i].key === card.metricKey) {
          m = metrics[i];
          break;
        }
      }

      if (!m) {
        showNoData('Indicador indisponível na fonte real');
        return;
      }

      if (prevEl) {
        prevEl.textContent = m.value + (m.unit ? ' ' + m.unit : '');
      }

      card._singleMetric = m;
      card._lastMetric = m;

      if (
        result.history_by_metric &&
        Array.isArray(result.history_by_metric[card.metricKey]) &&
        result.history_by_metric[card.metricKey].length > 0
      ) {
        card.history = result.history_by_metric[card.metricKey];
        delete card._singleMetric;
        renderMiniCardChart(cardIdx);
        return;
      }

      if (
        card.metricKey === 'producao_total' &&
        Array.isArray(result.history) &&
        result.history.length > 0
      ) {
        card.history = result.history;
        delete card._singleMetric;
        renderMiniCardChart(cardIdx);
        return;
      }

      var singleVal = parseNumeric(m.value);
      if (isFinite(singleVal)) {
        card.history = [{ ano: String(new Date().getFullYear()), valor: singleVal }];
        renderMiniCardChart(cardIdx);
        return;
      }

      showNoData('Sem histórico real para este indicador');
    })
    .catch(function () {
      showNoData('Sem dados reais para este indicador');
    });
}

function renderMiniCardChart(cardIdx) {
  var card = cultureMiniPanelState.marketCards[cardIdx];
  if (!card) return;
  var canvasEl = document.getElementById('mp-card-chart-' + cardIdx);
  if (!canvasEl) {
    autoRenderEditorPreview();
    return;
  }
  var chartBox = canvasEl.parentElement;
  var placeholder = document.getElementById('mp-card-placeholder-' + cardIdx);
  if (!chartBox) return;

  if (card.chartInstance) {
    try {
      card.chartInstance.destroy();
    } catch (e) {}
    card.chartInstance = null;
  }

  var hist = card.history || [];
  var hasUserHistory = !!card.myHistory && card.myHistory.length > 0;
  var hasData = (hist.length > 0 && (hist[0].valor || hist[0].valor === 0)) || hasUserHistory;

  if (!hasData) {
    chartBox.innerHTML =
      '<div id="mp-card-placeholder-' +
      cardIdx +
      '" class="mini-chart-placeholder" style="display:flex"><span class="text-[8px] text-slate-400">Sem dados</span></div>';
    return;
  }

  if (card.widgetType === 'tabela') {
    var rows = '';
    hist.forEach(function (h) {
      rows +=
        '<tr><td class="text-[7px] text-slate-500 px-1">' +
        h.ano +
        '</td><td class="text-[7px] font-semibold text-slate-700 px-1 text-right">' +
        h.valor.toLocaleString('pt-BR') +
        '</td></tr>';
    });
    if (hasUserHistory) {
      card.myHistory.forEach(function (h) {
        rows +=
          '<tr class="bg-blue-50 dark:bg-blue-900/20"><td class="text-[7px] text-slate-500 px-1">' +
          h.ano +
          ' (propriedade)</td><td class="text-[7px] font-semibold text-blue-700 dark:text-blue-300 px-1 text-right">' +
          h.valor.toLocaleString('pt-BR') +
          '</td></tr>';
      });
    }
    chartBox.innerHTML =
      '<table class="w-full border-collapse"><tbody>' + rows + '</tbody></table>';
    return;
  }

  if (card.widgetType === 'lista') {
    var items = '';
    hist.forEach(function (h) {
      items +=
        '<div class="flex justify-between text-[7px] px-1"><span class="text-slate-500">' +
        h.ano +
        '</span><span class="font-semibold text-slate-700">' +
        h.valor.toLocaleString('pt-BR') +
        '</span></div>';
    });
    if (hasUserHistory) {
      card.myHistory.forEach(function (h) {
        items +=
          '<div class="flex justify-between text-[7px] px-1 text-blue-700 dark:text-blue-300"><span class="text-slate-500">' +
          h.ano +
          ' (propriedade)</span><span class="font-semibold">' +
          h.valor.toLocaleString('pt-BR') +
          '</span></div>';
      });
    }
    chartBox.innerHTML = '<div class="overflow-y-auto h-full scrollbar-none">' + items + '</div>';
    return;
  }

  chartBox.innerHTML = '<canvas id="mp-card-chart-' + cardIdx + '"></canvas>';
  var canvas = document.getElementById('mp-card-chart-' + cardIdx);

  var labels = hist.map(function (h) {
    return h.ano;
  });
  var data = hist.map(function (h) {
    return h.valor;
  });
  if (hasUserHistory) {
    card.myHistory.forEach(function (h) {
      var y = h.ano;
      if (labels.indexOf(y) < 0) {
        labels.push(y);
        data.push(null);
      }
    });
  }
  if (data.length === 1) {
    data.unshift(data[0]);
    labels.unshift('');
  }

  var chartType = card.chartSubtype || 'line';
  var isCircular = ['pie', 'doughnut', 'radar', 'polarArea'].indexOf(chartType) >= 0;
  if (isCircular && hasUserHistory) {
    chartType = 'line';
    isCircular = false;
  }

  var mpPal = chartPalette();
  var colors = mpPal.pie.slice();
  var bgColors = colors.map(function (c) {
    return hexToRgba(c, 0.7);
  });

  var datasets = [];
  var marketSeriesLabel = card.source === 'ibge' ? 'IBGE' : 'Mercado';

  // Market data dataset (green/blue by theme)
  var marketDataset = {
    data: data,
    borderColor: mpPal.accent,
    backgroundColor: chartType === 'bar' ? mpPal.accentBar : mpPal.accentFill,
    borderWidth: 2,
    pointRadius: data.length === 2 ? [0, 5] : 2,
    pointBackgroundColor: mpPal.accent,
    pointBorderColor: mpPal.pointBorder,
    pointBorderWidth: 1,
    fill: chartType === 'line' || chartType === 'area',
    tension: 0.35,
    showLine: true,
    label: marketSeriesLabel,
  };

  if (isCircular) {
    marketDataset = {
      data: data,
      backgroundColor: bgColors.slice(0, data.length),
      borderColor: mpPal.isDark ? '#151b19' : '#fdfefe',
      borderWidth: 1,
      label: marketSeriesLabel,
    };
  }

  datasets.push(marketDataset);

  // User data dataset (blue) - for cross-data mode
  if (hasUserHistory) {
    var userLabels = card.myHistory.map(function (h) {
      return h.ano;
    });
    var userData = card.myHistory.map(function (h) {
      return h.valor;
    });

    // Align user data with market labels
    var alignedUserData = labels.map(function (label) {
      var idx = userLabels.indexOf(label);
      return idx >= 0 ? userData[idx] : null;
    });

    var userDataset = {
      data: alignedUserData,
      borderColor: mpPal.pie[1] || '#3b82f6',
      backgroundColor:
        chartType === 'bar'
          ? hexToRgba(mpPal.pie[1] || '#3b82f6', 0.6)
          : hexToRgba(mpPal.pie[1] || '#3b82f6', 0.06),
      borderWidth: 2,
      pointRadius: data.length === 2 ? [0, 5] : 2,
      pointBackgroundColor: mpPal.pie[1] || '#3b82f6',
      pointBorderColor: mpPal.pointBorder,
      pointBorderWidth: 1,
      fill: chartType === 'line' || chartType === 'area',
      tension: 0.35,
      showLine: true,
      label: 'Propriedade',
    };

    if (isCircular) {
      userDataset = {
        data: userData,
        backgroundColor: [hexToRgba(mpPal.pie[1] || '#3b82f6', 0.7)],
        borderColor: mpPal.pointBorder,
        borderWidth: 1,
        label: 'Propriedade',
      };
    }

    datasets.push(userDataset);
  }

  var mLabels = getMetricLabels(card.metricKey || '');
  if (!mLabels.x) mLabels.x = 'Período';

  var ctx = canvas.getContext('2d');
  card.chartInstance = new Chart(ctx, {
    type: chartType,
    data: {
      labels: labels,
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false, axis: 'x' },
      plugins: {
        legend: {
          display: hasUserHistory,
          position: 'bottom',
          labels: {
            boxWidth: 20,
            padding: 10,
            font: { size: 11 },
            usePointStyle: true,
            pointStyle: 'line',
            color: mpPal.tick,
          },
        },
        tooltip: { enabled: false },
      },
      scales: isCircular
        ? {}
        : {
            x: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: {
                font: { size: 9 },
                maxRotation: 0,
                minRotation: 0,
                autoSkip: true,
                padding: 4,
                color: mpPal.tick,
              },
            },
            y: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: {
                font: { size: 9 },
                padding: 4,
                color: mpPal.tick,
                callback: function (value) {
                  var n = Number(value);
                  return isFinite(n) ? n.toLocaleString('pt-BR') : value;
                },
              },
            },
          },
      layout: { padding: { top: 24, bottom: 4, left: 2, right: 2 } },
    },
  });
  canvas.classList.add('reveal-chart');

  autoRenderEditorPreview();
}

var PRODUCTION_COLORS = chartPalette().pie.slice();

// Toggle cross-data mode for market cards
window.toggleCrossData = function (cardIdx) {
  var card = cultureMiniPanelState.marketCards[cardIdx];
  if (!card) return;

  var checkbox = document.getElementById('mp-xd-' + cardIdx);
  if (!checkbox) return;

  card.crossData = checkbox.checked;

  // Re-fetch data to get user history if enabled
  fetchMiniCardData(cardIdx);
};

function toggleProductionRecords() {
  cultureMiniPanelState.checkboxExpanded = !cultureMiniPanelState.checkboxExpanded;
  renderCultureMiniPanel();
}

window.onProductionCheckboxChange = function (recordId) {
  var idx = cultureMiniPanelState.selectedRecordIds.indexOf(recordId);
  if (idx >= 0) {
    cultureMiniPanelState.selectedRecordIds.splice(idx, 1);
  } else {
    cultureMiniPanelState.selectedRecordIds.push(recordId);
  }
  renderCultureMiniPanel();
};

// ── Production Cards ──

window.selectProductionCardWidgetType = function (cardIdx, type) {
  var card = cultureMiniPanelState.productionCards[cardIdx];
  card.widgetType = type;
  if (type === 'grafico' && !card.chartSubtype) card.chartSubtype = 'line';
  renderCultureMiniPanel();
};

window.selectProductionCardSubtype = function (cardIdx, subtype) {
  cultureMiniPanelState.productionCards[cardIdx].chartSubtype = subtype;
  renderCultureMiniPanel();
};

function renderProductionCard(card, idx, cultureId) {
  var html = '';
  html += '<div class="mini-card">';
  html += '<div class="mini-card-left">';
  html +=
    '<div><span class="font-bold text-slate-800" style="font-size:11px">' + card.title + '</span>';
  if (card.subtitle)
    html +=
      ' <span class="text-slate-500 ml-0.5" style="font-size:7px">' + card.subtitle + '</span>';
  var starredProd = isCardStarred('prod', idx);
  html +=
    ' <button class="mini-star-btn' +
    (starredProd ? ' active' : '') +
    '" onclick="toggleCardStar(\'prod\', ' +
    idx +
    ')" title="Favoritar (habilita meta/comparação)"><i class="bi ' +
    (starredProd ? 'bi-star-fill' : 'bi-star') +
    '"></i></button>';
  html += ' <span class="text-[8px] text-slate-500 ml-1">Prev:</span>';
  html +=
    ' <span id="mp-prod-prev-' +
    idx +
    '" class="text-[9px] font-bold text-slate-800">—</span></div>';
  html += '<div class="mini-toggle">';
  ['grafico', 'lista', 'tabela'].forEach(function (t) {
    var label = t === 'grafico' ? 'gráfico' : t === 'tabela' ? 'tabela' : 'lista';
    var cls = card.widgetType === t ? ' active' : '';
    html +=
      '<button class="' +
      cls +
      '" onclick="selectProductionCardWidgetType(' +
      idx +
      ", '" +
      t +
      '\')">' +
      label +
      '</button>';
  });
  html += '</div>';
  if (card.widgetType === 'grafico') {
    var chartTypes = [
      { id: 'line', label: 'Linha' },
      { id: 'bar', label: 'Barra' },
      { id: 'doughnut', label: 'Rosca' },
      { id: 'pie', label: 'Pizza' },
      { id: 'radar', label: 'Radar' },
      { id: 'polarArea', label: 'Polar' },
    ];
    html +=
      '<select class="mini-card-select" onchange="selectProductionCardSubtype(' +
      idx +
      ', this.value)">';
    chartTypes.forEach(function (ct) {
      var sel = (card.chartSubtype || 'line') === ct.id ? ' selected' : '';
      html += '<option value="' + ct.id + '"' + sel + '>' + ct.label + '</option>';
    });
    html += '</select>';
  }
  var widProd = productionWidgetIdFor(idx, cultureId);
  var normWidProd = String(widProd)
    .replace(/^cult_/, 'cult-')
    .replace(/gafico/g, 'grafico');
  var existsProd =
    !!(widProd && window.widgets && widgets[widProd] && widgets[widProd].visible) ||
    !!(normWidProd && window.widgets && widgets[normWidProd] && widgets[normWidProd].visible) ||
    !!(
      widProd &&
      window.widgets &&
      Object.keys(window.widgets).some(function (k) {
        return (
          String(k)
            .replace(/^cult_/, 'cult-')
            .replace(/gafico/g, 'grafico') === normWidProd
        );
      })
    );
  var ed3 = cultureMiniPanelState.editor;
  var normEditProd =
    ed3 && ed3._editingWidgetId
      ? String(ed3._editingWidgetId)
          .replace(/^cult_/, 'cult-')
          .replace(/gafico/g, 'grafico')
      : null;
  var isEditingProd = !!(ed3 && ed3._editingWidgetId && normWidProd === normEditProd);
  var btnLabelP = isEditingProd ? 'Salvar' : existsProd ? 'Salvar' : 'Inserir';
  var editArgP = isEditingProd ? ", '" + ed3._editingWidgetId + "'" : '';
  html +=
    '<button class="mini-inserir-btn" onclick="addWidgetFromProductionCard(' +
    idx +
    ", '" +
    cultureId +
    "'" +
    editArgP +
    ')">' +
    btnLabelP +
    '</button>';
  html += '</div>';
  html += '<div class="mini-card-right">';
  html += '<canvas id="mp-prod-card-chart-' + idx + '"></canvas>';
  html +=
    '<div id="mp-prod-card-placeholder-' +
    idx +
    '" class="mini-chart-placeholder"><span class="text-[8px] text-slate-400">Sem dados</span></div>';
  html += '</div>';
  html += '</div>';
  return html;
}

function fetchProductionCardData(cardIdx) {
  var card = cultureMiniPanelState.productionCards[cardIdx];
  var selectedIds = cultureMiniPanelState.selectedRecordIds;
  var prevEl = document.getElementById('mp-prod-prev-' + cardIdx);
  var canvas = document.getElementById('mp-prod-card-chart-' + cardIdx);
  var placeholder = document.getElementById('mp-prod-card-placeholder-' + cardIdx);

  function showNoData() {
    if (prevEl) prevEl.textContent = '—';
    if (placeholder) placeholder.style.display = 'flex';
    if (canvas) canvas.style.display = 'none';
    autoRenderEditorPreview();
  }

  if (!window.ProductionRegistry || selectedIds.length === 0) {
    showNoData();
    return;
  }

  var records = [];
  selectedIds.forEach(function (id) {
    var r = ProductionRegistry.getById(id);
    if (r) records.push(r);
  });
  if (records.length === 0) {
    showNoData();
    return;
  }

  var metricKey = card.metricKey;
  var history = [];

  // ── Compute aggregation based on metricKey ──
  if (metricKey === 'detalhamento') {
    // Table view — history will be rendered directly in renderProductionCardChart
    card._records = records;
    card.history = [];
    if (prevEl) prevEl.textContent = records.length + ' registros';
    renderProductionCardChart(cardIdx);
    autoRenderEditorPreview();
    return;
  }

  if (
    metricKey === 'distribuicao' ||
    metricKey === 'taxa_lotacao' ||
    metricKey === 'conversao_alimentar' ||
    metricKey === 'rendimento'
  ) {
    // Percentage / ratio distributions
    if (metricKey === 'distribuicao') {
      var total = records.reduce(function (a, r) {
        return a + (r.quantity || 0);
      }, 0);
      history = records.map(function (r) {
        return {
          ano: r.name || r.location || '—',
          valor: total > 0 ? Math.round(((r.quantity || 0) / total) * 10000) / 100 : 0,
        };
      });
    } else if (metricKey === 'taxa_lotacao') {
      var locs = {},
        totalQty = 0;
      records.forEach(function (r) {
        if (r.location) locs[r.location] = (locs[r.location] || 0) + 1;
        totalQty += r.quantity || 0;
      });
      var numLocs = Object.keys(locs).length || 1;
      history = [{ ano: 'Taxa', valor: Math.round((totalQty / numLocs) * 100) / 100 }];
    } else if (metricKey === 'conversao_alimentar') {
      var sum = records.reduce(function (a, r) {
        return a + (r.quantity || 0);
      }, 0);
      var count = records.length || 1;
      history = [{ ano: 'Conversão', valor: Math.round((sum / count) * 100) / 100 }];
    } else {
      // rendimento
      var locs2 = {},
        totalQty2 = 0;
      records.forEach(function (r) {
        if (r.location) locs2[r.location] = (locs2[r.location] || 0) + 1;
        totalQty2 += r.quantity || 0;
      });
      var numLocs2 = Object.keys(locs2).length || 1;
      history = [{ ano: 'Rendimento', valor: Math.round((totalQty2 / numLocs2) * 100) / 100 }];
    }
  } else if (metricKey.indexOf('media_') === 0) {
    // Group by location, average
    var groups = {};
    records.forEach(function (r) {
      var loc = r.location || 'Sem local';
      if (!groups[loc]) groups[loc] = { sum: 0, count: 0 };
      groups[loc].sum += r.quantity || 0;
      groups[loc].count++;
    });
    history = Object.keys(groups).map(function (loc) {
      return { ano: loc, valor: Math.round((groups[loc].sum / groups[loc].count) * 100) / 100 };
    });
  } else if (metricKey === 'serie_temporal') {
    // Group by plantingDate
    var byDate = {};
    records.forEach(function (r) {
      var d = r.plantingDate || '—';
      if (!byDate[d]) byDate[d] = 0;
      byDate[d] += r.quantity || 0;
    });
    history = Object.keys(byDate)
      .sort()
      .map(function (d) {
        return { ano: d, valor: Math.round(byDate[d] * 100) / 100 };
      });
  } else if (
    metricKey === 'comparativo' ||
    (isCardStarred('prod', cardIdx) &&
      records.length > 1 &&
      ['line', 'bar'].indexOf(card.chartSubtype || 'line') >= 0 &&
      card.widgetType !== 'tabela')
  ) {
    // Comparação talhão x talhão: cada registro selecionado vira uma série.
    var allDates = [],
      dateMap = {};
    records.forEach(function (r) {
      var d = r.plantingDate || '—';
      if (!dateMap[d]) {
        dateMap[d] = true;
        allDates.push(d);
      }
    });
    allDates.sort();
    card._records = records;
    card._dates = allDates;
    card._comparative = true;
    history = []; // not used for chart — renderProductionCardChart handles directly
    if (prevEl) prevEl.textContent = records.length + ' registros';
    renderProductionCardChart(cardIdx);
    autoRenderEditorPreview();
    return;
  } else {
    // Total / sum (sacas_total, cabecas_total, biomassa_total, volume_total)
    var sum = records.reduce(function (a, r) {
      return a + (r.quantity || 0);
    }, 0);
    history = [{ ano: 'Total', valor: Math.round(sum * 100) / 100 }];
  }

  card.history = history;
  card._records = null;
  card._comparative = false;

  if (history.length > 0 && prevEl) {
    var lastVal = history[history.length - 1].valor;
    if (typeof lastVal === 'number') prevEl.textContent = lastVal.toLocaleString('pt-BR');
    else prevEl.textContent = String(lastVal);
  }

  renderProductionCardChart(cardIdx);
  autoRenderEditorPreview();
}

function renderProductionCardChart(cardIdx) {
  var card = cultureMiniPanelState.productionCards[cardIdx];
  var chartBox = document.getElementById('mp-prod-card-chart-' + cardIdx);
  var placeholder = document.getElementById('mp-prod-card-placeholder-' + cardIdx);
  if (!chartBox) return;

  var parent = chartBox.parentElement;

  // Handle detalhamento (table view) specially
  if (card.metricKey === 'detalhamento') {
    var records = card._records || [];
    if (records.length === 0) {
      if (placeholder) placeholder.style.display = 'flex';
      return;
    }
    var statusColors = {
      ativo: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30',
      colhido: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
      vendido: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
      encerrado: 'text-slate-500 bg-slate-100 dark:bg-slate-800',
    };
    var unitLabels = {
      cabeca: 'cab',
      mudas: 'mudas',
      kg: 'kg',
      m3: 'm³',
      tonelada: 't',
      litro: 'L',
      unidade: 'un',
      arroba: '@',
    };
    var fieldLabels = {
      variety: 'Variedade',
      species: 'Espécie',
      breed: 'Raça',
      category: 'Categoria',
      areaHa: 'Área (ha)',
      mudasQty: 'Mudas',
      spacing: 'Espaçamento',
      system: 'Sistema',
      irrigation: 'Irrigação',
      avgWeight: 'Peso Médio',
      avgAge: 'Idade',
      feeding: 'Alimentação',
      initialBiomass: 'Biomassa Inicial',
      dailyFeed: 'Ração/dia',
      feedConv: 'Conv. Alimentar',
      prodType: 'Tipo',
      exploredArea: 'Área Expl.(ha)',
      method: 'Método',
    };
    var rows = '';
    rows +=
      '<tr><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700 font-semibold">Registro</td><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700 font-semibold">Local</td><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700 font-semibold">Início</td><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700 font-semibold">Qtd</td><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700 font-semibold">Status</td></tr>';
    records.forEach(function (r) {
      var st = r.status || 'ativo';
      var sc = statusColors[st] || statusColors.ativo;
      var fieldsHtml = '';
      if (r.fields) {
        var fKeys = Object.keys(r.fields);
        fKeys.forEach(function (fk) {
          if (r.fields[fk]) {
            var fl = fieldLabels[fk] || fk;
            fieldsHtml +=
              ' <span class="text-[6px] text-slate-400">• ' + fl + ': ' + r.fields[fk] + '</span>';
          }
        });
      }
      var tCount = (r.treatments && r.treatments.length) || 0;
      var hCount = (r.harvests && r.harvests.length) || 0;
      rows +=
        '<tr><td class="text-[7px] text-slate-700 px-1 border border-slate-200 dark:border-slate-700">' +
        (r.name || '—') +
        fieldsHtml +
        '</td><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700">' +
        (r.location || '—') +
        '</td><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700">' +
        (r.date || '—') +
        '</td><td class="text-[7px] font-semibold text-slate-700 px-1 border border-slate-200 dark:border-slate-700 text-right">' +
        (r.quantity || 0) +
        ' ' +
        (unitLabels[r.unit] || r.unit || '') +
        '</td><td class="text-[7px] px-1 border border-slate-200 dark:border-slate-700"><span class="inline-block px-1.5 rounded-full font-semibold ' +
        sc +
        '">' +
        st +
        '</span>' +
        (tCount ? ' <span class="text-[6px] text-slate-400">T:' + tCount + '</span>' : '') +
        (hCount ? ' <span class="text-[6px] text-slate-400">C:' + hCount + '</span>' : '') +
        '</td></tr>';
    });
    parent.innerHTML =
      '<div class="overflow-auto h-full"><table class="w-full border-collapse"><tbody>' +
      rows +
      '</tbody></table></div>';
    return;
  }

  var widgetType = card.widgetType || 'grafico';
  var hist = card.history || [];

  if (widgetType === 'tabela') {
    var rows2 = '';
    hist.forEach(function (h) {
      rows2 +=
        '<tr><td class="text-[7px] text-slate-500 px-1 border border-slate-200 dark:border-slate-700">' +
        h.ano +
        '</td><td class="text-[7px] font-semibold text-slate-700 dark:text-slate-200 px-1 border border-slate-200 dark:border-slate-700 text-right">' +
        (typeof h.valor === 'number' ? h.valor.toLocaleString('pt-BR') : h.valor) +
        '</td></tr>';
    });
    parent.innerHTML =
      '<div class="overflow-auto h-full"><table class="w-full border-collapse"><tbody>' +
      rows2 +
      '</tbody></table></div>';
    return;
  }

  if (widgetType === 'lista') {
    var items = '';
    hist.forEach(function (h) {
      items +=
        '<div class="flex justify-between text-[7px] px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700"><span class="text-slate-500">' +
        h.ano +
        '</span><span class="font-semibold text-slate-700 dark:text-slate-200">' +
        (typeof h.valor === 'number' ? h.valor.toLocaleString('pt-BR') : h.valor) +
        '</span></div>';
    });
    parent.innerHTML =
      '<div class="overflow-y-auto h-full scrollbar-none space-y-1">' + items + '</div>';
    return;
  }

  var palP = chartPalette();

  // ── Chart ──
  parent.innerHTML =
    '<canvas id="mp-prod-card-chart-' +
    cardIdx +
    '" style="background:' +
    palP.chartBg +
    ';border-radius:4px;"></canvas>';
  var canvas = document.getElementById('mp-prod-card-chart-' + cardIdx);
  if (!canvas) return;

  var chartType = card.chartSubtype || 'line';
  if (chartType === 'line' && card.metricKey === 'distribuicao') chartType = 'doughnut';
  var isCircular = ['pie', 'doughnut', 'radar', 'polarArea'].indexOf(chartType) >= 0;

  var colors = palP.pie.slice();

  // ── Comparativo: cada registro = barra distinta (evita todos com mesmo valor)
  if (
    (card.metricKey === 'comparativo' || card._comparative) &&
    card._records &&
    card._records.length > 0
  ) {
    var records = card._records;
    var labels = records.map(function (r, idx) {
      return r.name || r.location || r.cultura || 'Registro ' + (idx + 1);
    });
    var compVals = records.map(function (r) {
      return r.quantity != null ? r.quantity : r.producao != null ? r.producao : 0;
    });
    var datasets = [
      {
        label: 'Quantidade',
        data: compVals,
        backgroundColor: records.map(function (_, idx) {
          return hexToRgba(colors[idx % colors.length], 0.85);
        }),
        borderColor: records.map(function (_, idx) {
          return colors[idx % colors.length];
        }),
        borderWidth: 2,
      },
    ];
    var mLabelsC = getMetricLabels(card.metricKey);
    try {
      if (card.chartInstance) card.chartInstance.destroy();
    } catch (e) {}
    var ctx = canvas.getContext('2d');
    card.chartInstance = new Chart(ctx, {
      type: isCircular
        ? chartType
        : ['bar', 'scatter', 'bubble'].indexOf(chartType) >= 0
          ? chartType
          : 'line',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        backgroundColor: palP.chartBg,
        interaction: { mode: 'index', intersect: false, axis: 'x' },
        plugins: {
          legend: {
            display: datasets.length > 1,
            position: 'bottom',
            labels: {
              boxWidth: 14,
              padding: 6,
              font: { size: 9 },
              color: palP.tick,
              usePointStyle: true,
              pointStyle: 'line',
            },
          },
          tooltip: { enabled: false },
        },
        scales: isCircular
          ? {}
          : {
              x: {
                display: true,
                grid: { display: false },
                border: { display: false },
                ticks: {
                  font: { size: 7 },
                  color: palP.tick,
                  maxRotation: 0,
                  autoSkip: true,
                  padding: 3,
                },
              },
              y: {
                display: true,
                grid: { display: false },
                border: { display: false },
                ticks: { font: { size: 7 }, padding: 3, color: palP.tick },
              },
            },
        layout: { padding: { top: 20, bottom: 4, left: 0, right: 0 } },
      },
    });
    canvas.classList.add('reveal-chart');
    return;
  }

  var labels = hist.map(function (h) {
    return h.ano;
  });
  var data = hist.map(function (h) {
    return h.valor;
  });
  if (data.length === 1) {
    data.unshift(data[0]);
    labels.unshift('');
  }

  var bgColors = colors.map(function (c) {
    return c + 'b3';
  });

  var dataset;
  if (isCircular) {
    dataset = {
      data: data,
      backgroundColor: colors.slice(0, data.length),
      borderColor: palP.pointBorder,
      borderWidth: 2,
    };
  } else {
    dataset = {
      data: data,
      borderColor: palP.accent,
      backgroundColor:
        chartType === 'bar' ? hexToRgba(palP.accent, 0.6) : hexToRgba(palP.accent, 0.06),
      borderWidth: 2,
      pointRadius: data.length === 2 ? [0, 5] : 2,
      pointBackgroundColor: palP.accent,
      pointBorderColor: palP.pointBorder,
      pointBorderWidth: 1,
      fill: false,
      tension: 0.35,
    };
  }

  var mLabels = getMetricLabels(card.metricKey);
  var hasSingleVal =
    data.length <= 2 &&
    labels.filter(function (l) {
      return l !== '';
    }).length <= 1;

  try {
    if (card.chartInstance) {
      card.chartInstance.destroy();
    }
  } catch (e) {}
  var ctx = canvas.getContext('2d');
  card.chartInstance = new Chart(ctx, {
    type: isCircular
      ? chartType
      : ['bar', 'scatter', 'bubble'].indexOf(chartType) >= 0
        ? chartType
        : 'line',
    data: { labels: labels, datasets: [dataset] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      backgroundColor: palP.chartBg,
      plugins: {
        legend: {
          display: !hasSingleVal,
          position: 'bottom',
          labels: {
            color: palP.tick,
            font: { size: 9 },
            boxWidth: 14,
            padding: 6,
            usePointStyle: true,
            pointStyle: 'line',
          },
        },
        tooltip: { enabled: false },
      },
      scales: isCircular
        ? {}
        : {
            x: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: {
                font: { size: 8 },
                color: palP.tick,
                maxRotation: 0,
                autoSkip: true,
                padding: 3,
              },
            },
            y: {
              display: true,
              grid: { display: false },
              border: { display: false },
              ticks: { font: { size: 8 }, padding: 3, color: palP.tick },
            },
          },
      layout: { padding: { top: 20, bottom: 4, left: 0, right: 0 } },
    },
  });
  canvas.classList.add('reveal-chart');
}

window.addWidgetFromProductionCard = function (cardIdx, cultureId, updateId) {
  var card = cultureMiniPanelState.productionCards[cardIdx];
  if (!card) return;
  var selectedIds = cultureMiniPanelState.selectedRecordIds;
  if (!Array.isArray(selectedIds) || selectedIds.length === 0) {
    if (typeof showToast === 'function') showToast('warning', 'Selecione ao menos um registro');
    return;
  }

  var ed = cultureMiniPanelState.editor || {
    category: 'linha',
    variant: 'suave',
    compare: [],
    mainColor: null,
  };
  var widgetType =
    ed.category === 'planilha' ? 'tabela' : ed.category === 'cartao' ? 'kpi' : 'grafico';
  var wType = widgetType;
  var chartSubtype = editorChartSubtype(ed, card);
  card.chartSubtype = chartSubtype;

  var widgetId = productionWidgetIdFor(cardIdx, cultureId);
  if (!widgetId) return;

  var existingOld = updateId ? widgets[updateId] : null;
  var isUpdate = !!updateId;
  var existing = widgets[widgetId];

  if (existing && existing.visible && !(isUpdate && existingOld && existingOld === existing)) {
    if (typeof showToast === 'function') showToast('warning', 'Widget já inserido para este card');
    return;
  }
  if (isUpdate && updateId !== widgetId && existingOld) existingOld.visible = false;

  var defaultSize = { w: 20, h: 28 };
  var pos;
  if (isUpdate && (existing || existingOld)) {
    var anchor = existing || existingOld;
    pos = { x: anchor.gridX, y: anchor.gridY };
  } else {
    pos = window.findFreePosition ? findFreePosition(defaultSize.w, defaultSize.h) : { x: 0, y: 0 };
  }
  if (!pos) {
    if (typeof showToast === 'function') showToast('warning', 'Espaço insuficiente na matriz');
    return;
  }

  var keepSize = isUpdate && (existing || existingOld);

  widgets[widgetId] = {
    gridX: pos.x,
    gridY: pos.y,
    gridW: keepSize ? (existing || existingOld).gridW : defaultSize.w,
    gridH: keepSize ? (existing || existingOld).gridH : defaultSize.h,
    visible: true,
    title: card.title || card.metricKey,
    showTitle: true,
    selectedRecords: selectedIds.slice(),
    metricKey: card.metricKey,
    widgetType: widgetType,
    chartSubtype: chartSubtype,
    chartStyleCategory: ed.category,
    chartStyleVariant: ed.variant,
    mainColor: ed.mainColor || null,
    _mainColor: ed.mainColor || null,
    _compareSeries: (ed.compare || []).slice(),
    _metaEnabled: !!ed.hasMeta,
    _metaValue:
      ed.metaValue === '' || ed.metaValue === null || ed.metaValue === undefined
        ? ''
        : ed.metaValue,
    _starred: isCardStarred('prod', cardIdx),
    _comparative: !!card._comparative,
  };
  if (typeof window.saveWidgetsLayoutImmediate === 'function') window.saveWidgetsLayoutImmediate();
  else saveWidgetsLayout();
  renderWidgetsOnMatrix();
  showWidgetToast(isUpdate ? 'Widget atualizado!' : undefined);
  hideCultureMiniPanel();
  if (cultureMiniPanelState.editor) cultureMiniPanelState.editor._editingWidgetId = null;
};

function renderProductionCheckboxView(cultureId) {
  var state = cultureMiniPanelState;
  var records = state.productionRecords;
  var selected = state.selectedRecordIds;

  if (records.length === 0) {
    var emptyUrl = '/guias/vegetal/';
    var c = (window.CulturesLoader && CulturesLoader.getCulture(cultureId)) || null;
    if (c) {
      var g = (c.django_grupo || 'vegetal').toLowerCase();
      if (g === 'animal') emptyUrl = '/guias/animal/';
      else if (g === 'aquatico' || g === 'aquática') emptyUrl = '/guias/aquatica/';
      else emptyUrl = '/guias/vegetal/';
      emptyUrl += c.id + '/';
    }
    return (
      '<div class="py-6 text-center"><i class="bi bi-inbox text-2xl text-slate-400 mb-2 block"></i><p class="text-xs text-slate-500 mb-2">Nenhum registro</p><a href="' +
      emptyUrl +
      '" class="inline-flex items-center gap-1 px-3 py-1.5 text-[11px] font-semibold rounded-full bg-emerald-600 hover:bg-emerald-700 text-white transition-all"><i class="bi bi-plus-circle"></i> Cadastrar produção</a></div>'
    );
  }

  var allSelected = selected.length === records.length && records.length > 0;
  var html = '';

  html +=
    '<div class="text-[9px] font-semibold text-slate-600 dark:text-slate-400 mb-1.5">Registros Disponíveis</div>';
  html += '<div class="mini-record-carousel mb-2">';
  var statusColors = {
    ativo: 'text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30',
    colhido: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
    vendido: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
    encerrado: 'text-slate-500 bg-slate-100 dark:bg-slate-800',
  };
  records.forEach(function (r) {
    var isChecked = selected.indexOf(r.id) >= 0;
    var name = r.name || r.location || 'Sem nome';
    var st = r.status || 'ativo';
    var sc = statusColors[st] || statusColors.ativo;
    var detail =
      (r.date || r.plantingDate ? 'Data: ' + (r.date || r.plantingDate) : '') +
      (r.location ? ' • ' + r.location : '');
    var tCount = (r.treatments && r.treatments.length) || 0;
    var hCount = (r.harvests && r.harvests.length) || 0;
    var extra = (tCount ? ' T:' + tCount : '') + (hCount ? ' C:' + hCount : '');
    html +=
      '<button class="mini-record-card' +
      (isChecked ? ' selected' : '') +
      '" onclick="onProductionCheckboxChange(\'' +
      r.id +
      '\')">';
    html +=
      '<div class="flex items-center gap-1"><span class="mini-record-card-badge ' +
      sc +
      '">' +
      st +
      '</span>' +
      (isChecked ? '<i class="bi bi-check2 text-emerald-600 text-[8px] ml-auto"></i>' : '') +
      '</div>';
    html += '<div class="mini-record-card-name">' + name + extra + '</div>';
    html += '<div class="mini-record-card-detail">' + detail + '</div>';
    html += '</button>';
  });
  html += '</div>';

  // Selecionar todos
  html += '<div class="flex items-center gap-2">';
  html +=
    '<button onclick="' +
    (allSelected ? 'toggleSelectAllRecords()' : 'toggleSelectAllRecords()') +
    '" class="flex items-center gap-1 px-2 py-1 text-[8px] font-semibold rounded-md border ' +
    (allSelected
      ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300'
      : 'border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-400 hover:border-emerald-400 hover:text-emerald-600') +
    ' transition-all"><i class="bi ' +
    (allSelected ? 'bi-check2-all' : 'bi-check2-square') +
    '"></i>' +
    (allSelected ? 'Desmarcar todos' : 'Selecionar todos') +
    '</button>';
  html += '<span class="text-[7px] text-slate-400">(' + selected.length + ' selecionados)</span>';
  html += '</div>';

  return html;
}

window.onProductionCheckboxChange = function (recordId) {
  var idx = cultureMiniPanelState.selectedRecordIds.indexOf(recordId);
  if (idx >= 0) {
    cultureMiniPanelState.selectedRecordIds.splice(idx, 1);
  } else {
    cultureMiniPanelState.selectedRecordIds.push(recordId);
  }
  onProductionSelectionChange();
};

window.onProductionSelectionChange = function () {
  renderCultureMiniPanel();
};

window.toggleSelectAllRecords = function () {
  var records = cultureMiniPanelState.productionRecords || [];
  var selected = cultureMiniPanelState.selectedRecordIds;
  var allSelected = selected.length === records.length && records.length > 0;
  if (allSelected) {
    cultureMiniPanelState.selectedRecordIds = [];
  } else {
    cultureMiniPanelState.selectedRecordIds = records.map(function (r) {
      return r.id;
    });
  }
  renderCultureMiniPanel();
};

// ── Formulário Especialista por Grupo ──
function getProductionFormFields(groupId, culture) {
  var types = (culture && culture.types) || {};
  var typeKeys = Object.keys(types);
  var typeOptions = typeKeys.map(function (k) {
    return { value: k, label: types[k].label };
  });
  var getLocations = function (cid) {
    var locs = [];
    if (window.ProductionRegistry) {
      ProductionRegistry.getByCulture(cid).forEach(function (r) {
        if (r.location && locs.indexOf(r.location) < 0) locs.push(r.location);
      });
    }
    return locs;
  };
  var form = {
    vegetal: [
      {
        key: 'name',
        label: 'Nome do Cultivo',
        type: 'text',
        placeholder: 'ex: Café Arábica Talhão Norte',
        required: true,
        colSpan: 2,
      },
      {
        key: 'variety',
        label: 'Tipo / Variedade',
        type: 'select',
        options: typeOptions,
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      { key: 'location', label: 'Talhão / Área', type: 'location', colSpan: 1 },
      { key: 'plantingDate', label: 'Data de Plantio', type: 'date', colSpan: 1 },
      {
        key: 'areaHa',
        label: 'Área Plantada (ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        unit: 'ha',
        colSpan: 1,
      },
      {
        key: 'mudasQty',
        label: 'Mudas / Unidades',
        type: 'number',
        step: 1,
        placeholder: '0',
        unit: 'mudas',
        colSpan: 1,
      },
      {
        key: 'spacing',
        label: 'Espaçamento (m)',
        type: 'text',
        placeholder: 'ex: 0.5 x 0.8',
        colSpan: 1,
      },
      {
        key: 'system',
        label: 'Sistema de Cultivo',
        type: 'select',
        options: [
          { value: 'convencional', label: 'Convencional' },
          { value: 'organico', label: 'Orgânico' },
          { value: 'integrado', label: 'Integrado' },
          { value: 'agrofloresta', label: 'Agrofloresta' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      {
        key: 'irrigation',
        label: 'Irrigação',
        type: 'select',
        options: [
          { value: 'seca', label: 'Seca' },
          { value: 'aspersao', label: 'Aspersão' },
          { value: 'gotejo', label: 'Gotejo' },
          { value: 'pivo', label: 'Pivô Central' },
          { value: 'sulco', label: 'Sulco' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'ex: Plantado em terreno baixo, pode ser afetado por geadas',
        colSpan: 2,
      },
    ],
    animal: [
      {
        key: 'name',
        label: 'Nome do Lote',
        type: 'text',
        placeholder: 'ex: Lote Nelore 2024',
        required: true,
        colSpan: 2,
      },
      {
        key: 'species',
        label: 'Espécie',
        type: 'select',
        options: [
          { value: 'bovino', label: 'Bovino' },
          { value: 'suino', label: 'Suíno' },
          { value: 'ovino', label: 'Ovino' },
          { value: 'caprino', label: 'Caprino' },
          { value: 'equino', label: 'Equino' },
          { value: 'bufalo', label: 'Búfalo' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      {
        key: 'breed',
        label: 'Raça',
        type: 'text',
        placeholder: 'ex: Nelore, Holandesa',
        colSpan: 1,
      },
      {
        key: 'category',
        label: 'Categoria',
        type: 'select',
        options: [
          { value: 'cria', label: 'Cria' },
          { value: 'recria', label: 'Recria' },
          { value: 'engorda', label: 'Engorda' },
          { value: 'leite', label: 'Leite' },
          { value: 'reproducao', label: 'Reprodução' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      { key: 'location', label: 'Piquete / Local', type: 'location', colSpan: 1 },
      { key: 'date', label: 'Data de Entrada', type: 'date', colSpan: 1 },
      {
        key: 'qty',
        label: 'Cabeças',
        type: 'number',
        step: 1,
        placeholder: '0',
        unit: 'cab',
        colSpan: 1,
      },
      {
        key: 'avgWeight',
        label: 'Peso Médio (kg)',
        type: 'number',
        step: 0.1,
        placeholder: '0,0',
        unit: 'kg',
        colSpan: 1,
      },
      {
        key: 'avgAge',
        label: 'Idade Média (meses)',
        type: 'number',
        step: 0.5,
        placeholder: '0',
        unit: 'meses',
        colSpan: 1,
      },
      {
        key: 'feeding',
        label: 'Alimentação',
        type: 'select',
        options: [
          { value: 'pastagem', label: 'Pastagem' },
          { value: 'confinamento', label: 'Confinamento' },
          { value: 'semiconfinamento', label: 'Semiconfinamento' },
          { value: 'silagem', label: 'Silagem' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Vacinas, histórico, etc',
        colSpan: 2,
      },
    ],
    aquatica: [
      {
        key: 'name',
        label: 'Nome do Tanque',
        type: 'text',
        placeholder: 'ex: Tanque 03 - Tilápias',
        required: true,
        colSpan: 2,
      },
      {
        key: 'species',
        label: 'Espécie',
        type: 'select',
        options: [
          { value: 'tilapia', label: 'Tilápia' },
          { value: 'tambaqui', label: 'Tambaqui' },
          { value: 'camarao', label: 'Camarão' },
          { value: 'carpa', label: 'Carpa' },
          { value: 'truta', label: 'Truta' },
          { value: 'outro', label: 'Outro' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      { key: 'location', label: 'Tanque / Viveiro', type: 'location', colSpan: 1 },
      { key: 'date', label: 'Data de Povoamento', type: 'date', colSpan: 1 },
      {
        key: 'qty',
        label: 'Alevinos / Peixes',
        type: 'number',
        step: 1,
        placeholder: '0',
        unit: 'unidades',
        colSpan: 1,
      },
      {
        key: 'initialBiomass',
        label: 'Biomassa Inicial (kg)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        unit: 'kg',
        colSpan: 1,
      },
      {
        key: 'dailyFeed',
        label: 'Ração (kg/dia)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        unit: 'kg/dia',
        colSpan: 1,
      },
      {
        key: 'feedConv',
        label: 'Conversão Alimentar',
        type: 'number',
        step: 0.01,
        placeholder: '1.5',
        unit: 'CA',
        colSpan: 1,
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Qualidade da água, temperatura, etc',
        colSpan: 2,
      },
    ],
    extrativismo: [
      {
        key: 'name',
        label: 'Produto Extraído',
        type: 'text',
        placeholder: 'ex: Castanha-do-Pará',
        required: true,
        colSpan: 2,
      },
      {
        key: 'prodType',
        label: 'Tipo',
        type: 'select',
        options: [
          { value: 'madeira', label: 'Madeira' },
          { value: 'borracha', label: 'Borracha' },
          { value: 'castanha', label: 'Castanha' },
          { value: 'acai', label: 'Açaí' },
          { value: 'palmito', label: 'Palmito' },
          { value: 'oleo', label: 'Óleo' },
          { value: 'cipó', label: 'Cipó' },
          { value: 'resina', label: 'Resina' },
          { value: 'carvao', label: 'Carvão' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      { key: 'location', label: 'Área de Extração', type: 'location', colSpan: 1 },
      { key: 'date', label: 'Data da Extração', type: 'date', colSpan: 1 },
      {
        key: 'qty',
        label: 'Volume Extraído',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
      },
      {
        key: 'unit',
        label: 'Unidade',
        type: 'select',
        options: [
          { value: 'm3', label: 'm³' },
          { value: 'kg', label: 'kg' },
          { value: 'tonelada', label: 'Tonelada' },
          { value: 'litro', label: 'Litro' },
          { value: 'unidade', label: 'Unidade' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
      },
      {
        key: 'exploredArea',
        label: 'Área Explorada (ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        unit: 'ha',
        colSpan: 1,
      },
      {
        key: 'method',
        label: 'Método',
        type: 'select',
        options: [
          { value: 'manual', label: 'Manual' },
          { value: 'mecanizado', label: 'Mecanizado' },
          { value: 'semi-mecanizado', label: 'Semi-mecanizado' },
        ],
        placeholder: 'Selecione...',
        colSpan: 2,
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Condições da área, etc',
        colSpan: 2,
      },
    ],
  };
  return form[groupId] || form.vegetal;
}

function renderField(field, cultureId) {
  var id = 'mpf-' + field.key + '-' + cultureId;
  var requiredAttr = field.required ? ' required' : '';
  var cls =
    'w-full text-[9px] px-2 py-1.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400/20 transition-all';
  var colSpan = field.colSpan > 1 ? ' col-span-2' : '';
  var unitHtml = field.unit
    ? ' <span class="text-[7px] text-slate-400 font-medium ml-0.5">' + field.unit + '</span>'
    : '';
  var html = '<div class="' + colSpan + '">';
  html +=
    '<label class="text-[9px] text-slate-600 dark:text-slate-400 font-semibold block mb-0.5" for="' +
    id +
    '">' +
    field.label +
    unitHtml +
    '</label>';
  if (field.type === 'select') {
    var opts = field.options || [];
    html += '<select id="' + id + '" class="' + cls + '">';
    if (field.placeholder) html += '<option value="">' + field.placeholder + '</option>';
    opts.forEach(function (o) {
      var val = o.value || o;
      var lbl = o.label || o;
      html += '<option value="' + val + '">' + lbl + '</option>';
    });
    html += '</select>';
  } else if (field.type === 'location') {
    var existingLocations = [];
    if (window.ProductionRegistry) {
      ProductionRegistry.getByCulture(cultureId).forEach(function (r) {
        if (r.location && existingLocations.indexOf(r.location) < 0)
          existingLocations.push(r.location);
      });
    }
    html +=
      '<select id="' +
      id +
      '" onchange="var n=document.getElementById(\'' +
      id +
      "-new');if(this.value==='__new__'){n.classList.remove('hidden');n.focus();}else{n.classList.add('hidden');n.value='';}\" class=\"" +
      cls +
      '"><option value="">Selecionar...</option>';
    existingLocations.forEach(function (l) {
      html += '<option value="' + l.replace(/'/g, "\\'") + '">' + l + '</option>';
    });
    html += '<option value="__new__">+ Novo...</option></select>';
    html +=
      '<input id="' +
      id +
      '-new" type="text" placeholder="Novo local..." class="' +
      cls +
      ' mt-1 hidden">';
  } else if (field.type === 'textarea') {
    html +=
      '<textarea id="' +
      id +
      '" rows="2" placeholder="' +
      (field.placeholder || '') +
      '" class="' +
      cls +
      ' resize-none"' +
      requiredAttr +
      '></textarea>';
  } else if (field.type === 'date') {
    html += '<input id="' + id + '" type="date" class="' + cls + '"' + requiredAttr + '>';
  } else {
    html +=
      '<input id="' +
      id +
      '" type="' +
      (field.type || 'text') +
      '" step="' +
      (field.step || 'any') +
      '" placeholder="' +
      (field.placeholder || '') +
      '" class="' +
      cls +
      '"' +
      requiredAttr +
      '>';
  }
  html += '</div>';
  return html;
}

function getFieldValue(field, cultureId) {
  var id = 'mpf-' + field.key + '-' + cultureId;
  var el = document.getElementById(id);
  if (!el) return '';
  if (field.type === 'location') {
    var val = el.value;
    if (val === '__new__') {
      var newEl = document.getElementById(id + '-new');
      return newEl ? newEl.value.trim() : '';
    }
    return val;
  }
  if (field.type === 'number') return parseFloat(el.value) || 0;
  return el.value.trim();
}

function renderTreatmentRow(idx, cultureId) {
  var html =
    '<div class="flex items-center gap-1.5 text-[9px]" id="mpt-row-' + idx + '-' + cultureId + '">';
  html +=
    '<input type="date" id="mpt-date-' +
    idx +
    '-' +
    cultureId +
    '" class="w-[90px] px-1.5 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 text-[9px] focus:outline-none focus:border-emerald-400">';
  html +=
    '<select id="mpt-type-' +
    idx +
    '-' +
    cultureId +
    '" class="px-1.5 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 text-[9px] focus:outline-none focus:border-emerald-400"><option value="">Tipo...</option><option value="fertilizante">Fertilizante</option><option value="pesticida">Pesticida</option><option value="corretivo">Corretivo</option><option value="inoculante">Inoculante</option><option value="outro">Outro</option></select>';
  html +=
    '<input type="text" id="mpt-product-' +
    idx +
    '-' +
    cultureId +
    '" placeholder="Produto" class="w-[90px] px-1.5 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 text-[9px] placeholder:text-slate-400 focus:outline-none focus:border-emerald-400">';
  html +=
    '<input type="text" id="mpt-dose-' +
    idx +
    '-' +
    cultureId +
    '" placeholder="Dose" class="w-[70px] px-1.5 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 text-[9px] placeholder:text-slate-400 focus:outline-none focus:border-emerald-400">';
  html +=
    '<select id="mpt-method-' +
    idx +
    '-' +
    cultureId +
    '" class="px-1.5 py-1 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 text-[9px] focus:outline-none focus:border-emerald-400"><option value="">Método...</option><option value="pulverizacao">Pulverização</option><option value="incorporacao">Incorporação</option><option value="fertirrigacao">Fertirrigação</option><option value="manual">Manual</option><option value="mecanizado">Mecanizado</option></select>';
  html +=
    '<button onclick="removeTreatmentRow(' +
    idx +
    ", '" +
    cultureId +
    '\')" class="text-red-500 hover:text-red-700 px-1 text-[9px]">✕</button>';
  html += '</div>';
  return html;
}

window.addTreatmentRow = function (cultureId) {
  var container = document.getElementById('mpt-rows-' + cultureId);
  if (!container) return;
  var idx = container.children.length;
  container.insertAdjacentHTML('beforeend', renderTreatmentRow(idx, cultureId));
};

window.removeTreatmentRow = function (idx, cultureId) {
  var row = document.getElementById('mpt-row-' + idx + '-' + cultureId);
  if (row) row.remove();
};

function getTreatmentRows(cultureId) {
  var container = document.getElementById('mpt-rows-' + cultureId);
  if (!container) return [];
  var treatments = [];
  for (var i = 0; i < container.children.length; i++) {
    var dateEl = document.getElementById('mpt-date-' + i + '-' + cultureId);
    var typeEl = document.getElementById('mpt-type-' + i + '-' + cultureId);
    var prodEl = document.getElementById('mpt-product-' + i + '-' + cultureId);
    var doseEl = document.getElementById('mpt-dose-' + i + '-' + cultureId);
    var methodEl = document.getElementById('mpt-method-' + i + '-' + cultureId);
    if (dateEl && typeEl && typeEl.value) {
      treatments.push({
        date: dateEl.value,
        type: typeEl.value,
        product: prodEl ? prodEl.value.trim() : '',
        dose: doseEl ? doseEl.value.trim() : '',
        method: methodEl ? methodEl.value : '',
      });
    }
  }
  return treatments;
}

function renderProductionFormGrouped(cultureId, groupId, culture) {
  var fields = getProductionFormFields(groupId, culture);
  var html = '<div class="space-y-2">';
  html += '<div class="grid grid-cols-2 gap-x-3 gap-y-2">';
  fields.forEach(function (f) {
    html += renderField(f, cultureId);
  });
  html += '</div>';

  // ── Tratamentos inline ──
  html += '<div class="border-t border-slate-200 dark:border-slate-700 pt-2 mt-2">';
  html += '<div class="flex items-center justify-between mb-1">';
  html +=
    '<span class="text-[9px] font-semibold text-slate-600 dark:text-slate-400">Tratamentos / Insumos</span>';
  html +=
    '<button onclick="addTreatmentRow(\'' +
    cultureId +
    '\')" class="text-[9px] text-emerald-600 hover:text-emerald-700 font-semibold flex items-center gap-1"><i class="bi bi-plus-circle"></i> Adicionar</button>';
  html += '</div>';
  html += '<div id="mpt-rows-' + cultureId + '" class="space-y-1"></div>';
  html += '</div>';

  html += '</div>';
  return html;
}

window.limparFormProducao = function () {
  var cultureId = cultureMiniPanelState.cultureId;
  if (!cultureId) return;
  var fields = getProductionFormFields(cultureMiniPanelState.groupId, null);
  fields.forEach(function (f) {
    var id = 'mpf-' + f.key + '-' + cultureId;
    var el = document.getElementById(id);
    if (!el) return;
    if (f.type === 'location') {
      el.value = '';
      var newEl = document.getElementById(id + '-new');
      if (newEl) {
        newEl.value = '';
        newEl.classList.add('hidden');
      }
    } else if (f.type === 'number') el.value = '';
    else el.value = '';
  });
  var tContainer = document.getElementById('mpt-rows-' + cultureId);
  if (tContainer) tContainer.innerHTML = '';
  if (typeof showToast === 'function') showToast('info', 'Formulário limpo');
};

window.toggleHarvestForm = function () {
  var form = document.getElementById('mini-harvest-form');
  if (form) form.classList.toggle('hidden');
};

window.submitHarvest = function (cultureId) {
  var dateEl = document.getElementById('mini-harvest-date');
  var qtyEl = document.getElementById('mini-harvest-qty');
  var unitEl = document.getElementById('mini-harvest-unit');
  if (!dateEl || !qtyEl || !unitEl) return;
  var date = dateEl.value;
  var qty = parseFloat(qtyEl.value) || 0;
  var unit = unitEl.value;
  if (!date || !qty) {
    if (typeof showToast === 'function') showToast('warning', 'Preencha data e quantidade');
    return;
  }
  var ids = cultureMiniPanelState.selectedRecordIds;
  if (!window.ProductionRegistry || ids.length === 0) return;
  ids.forEach(function (rid) {
    var r = ProductionRegistry.getById(rid);
    if (!r) return;
    if (!r.harvests) r.harvests = [];
    r.harvests.push({ date: date, quantity: qty, unit: unit, createdAt: new Date().toISOString() });
    r.status = 'colhido';
    r.updatedAt = new Date().toISOString();
    ProductionRegistry.save(r);
  });
  cultureMiniPanelState.productionRecords = buildProductionRecords(cultureId);
  if (typeof showToast === 'function')
    showToast('success', ids.length + ' registro(s) colhido(s)!');
  // Reset form
  dateEl.value = '';
  qtyEl.value = '';
  unitEl.value = '';
  var form = document.getElementById('mini-harvest-form');
  if (form) form.classList.add('hidden');
  renderCultureMiniPanel();
};

window.submitMiniPanelRecord = function (cultureId, groupId) {
  var fields = getProductionFormFields(groupId, null);
  var record = {
    cultureId: cultureId,
    groupId: groupId,
    status: 'ativo',
    fields: {},
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  var hasName = false;
  fields.forEach(function (f) {
    var val = getFieldValue(f, cultureId);
    if (f.key === 'name') {
      record.name = val;
      if (val) hasName = true;
    } else if (f.key === 'location') {
      record.location = val;
    } else if (f.key === 'plantingDate' || f.key === 'date') {
      record.date = val;
      record.plantingDate = val;
    } else if (f.key === 'qty' || f.key === 'mudasQty') {
      record.quantity = val;
    } else if (f.key === 'unit') {
      record.unit = val;
    } else if (f.key === 'observations') {
      record.observations = val;
    } else {
      record.fields[f.key] = val;
    }
  });
  if (!hasName) {
    if (typeof showToast === 'function') showToast('warning', 'Preencha o nome do registro');
    return;
  }
  record.treatments = getTreatmentRows(cultureId);
  if (window.ProductionRegistry) {
    ProductionRegistry.save(record);
    cultureMiniPanelState.productionRecords = buildProductionRecords(cultureId);
    if (typeof showToast === 'function') showToast('success', 'Registro salvo!');
    renderCultureMiniPanel();
  }
};

function editorChartSubtype(ed, card) {
  var styleMeta =
    window.AmpliChartStyles && typeof AmpliChartStyles.variant === 'function'
      ? AmpliChartStyles.variant(ed.category, ed.variant)
      : null;
  var chartSubtype = styleMeta ? styleMeta.type : card.chartSubtype || 'line';
  if (styleMeta && (styleMeta.horizontal || ed.variant === 'horizontal')) chartSubtype = 'bar';
  return chartSubtype;
}

function marketWidgetIdFor(cardIdx, cultureId) {
  var cards = cultureMiniPanelState.marketCards;
  if (!cards || !cards[cardIdx]) return '';
  var card = cards[cardIdx];
  var ed = cultureMiniPanelState.editor || { category: 'linha', variant: 'suave' };
  var widgetType =
    ed.category === 'planilha' ? 'tabela' : ed.category === 'cartao' ? 'kpi' : 'grafico';
  var wType = widgetType;
  var chartSubtype = editorChartSubtype(ed, card);
  return (
    cultureId +
    '_mercado_' +
    card.metricKey +
    '_' +
    wType +
    (wType === 'grafico' ? '_' + chartSubtype : '')
  );
}

function productionWidgetIdFor(cardIdx, cultureId) {
  var cards = cultureMiniPanelState.productionCards;
  if (!cards || !cards[cardIdx]) return '';
  var card = cards[cardIdx];
  var ed = cultureMiniPanelState.editor || { category: 'linha', variant: 'suave' };
  var widgetType =
    ed.category === 'planilha' ? 'tabela' : ed.category === 'cartao' ? 'kpi' : 'grafico';
  var wType = widgetType;
  var chartSubtype = editorChartSubtype(ed, card);
  return (
    cultureId +
    '_producao_' +
    card.metricKey +
    '_' +
    wType +
    (wType === 'grafico' && chartSubtype && chartSubtype !== 'line' ? '_' + chartSubtype : '')
  );
}

function hexToRgbList(hex) {
  if (!hex) return null;
  var h = String(hex).trim();
  if (h.charAt(0) === '#') h = h.slice(1);
  if (h.length === 3)
    h = h
      .split('')
      .map(function (c) {
        return c + c;
      })
      .join('');
  if (h.length === 6 && /^[0-9a-fA-F]{6}$/.test(h)) {
    var n = parseInt(h, 16);
    if (!isNaN(n)) return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  var mm = String(hex).match(/\d+(\.\d+)?/g);
  if (mm && mm.length >= 3) {
    var r = parseFloat(mm[0]),
      g = parseFloat(mm[1]),
      b = parseFloat(mm[2]);
    if (!isNaN(r) && !isNaN(g) && !isNaN(b) && r >= 0 && g >= 0 && b >= 0)
      return [Math.round(r), Math.round(g), Math.round(b)];
  }
  return null;
}

window.openEditSelectedWidget = function () {
  var wId = _selectedWidgetId;
  var cfg = wId ? window.widgets && widgets[wId] : null;
  if (!wId || !cfg) {
    openAddWidgetModal();
    return;
  }
  // Normaliza id com underscore/typo para abrir no lugar certo (ex: cult_graos-arroz_mercado_area_plantada_gafico_line -> cult-graos-arroz_mercado_area_plantada_grafico_line)
  var normWId = String(wId)
    .replace(/^cult_/, 'cult-')
    .replace(/_gafico/g, '_grafico')
    .replace(/gafico/g, 'grafico');
  // Se normalizou, usa o normalizado para buscar cultura/metric, mas mantém o wId original para edição
  var parts = normWId.split(/_(mercado|producao)_/);
  if (parts.length !== 3) {
    // Widget genérico (kpi, chart, cult- sem métrica, cultura-)
    // Abre o painel de inserir e destaca o widget para edição
    openAddWidgetModal();
    // Tenta mapear cultura- / cult- / cult_ para abrir o mini painel da cultura correspondente
    var maybeCulture = null;
    if (wId.indexOf('cultura-') === 0)
      maybeCulture = wId.replace('cultura-', '').split('_')[0].split('-')[0];
    else if (wId.indexOf('cult-') === 0 || wId.indexOf('cult_') === 0)
      maybeCulture = String(wId).replace(/^cult_/, 'cult-');
    // Se for cultura (ex: cult-graos-milho, cultura-arroz), abre o mini painel dessa cultura
    if (maybeCulture) {
      var normCult = String(maybeCulture)
        .replace(/^cultura-/, '')
        .replace(/^cult-[^-]+-/, '');
      var foundId = null,
        foundGroup = '';
      if (typeof CULTURE_GROUPS !== 'undefined' && CULTURE_GROUPS) {
        for (var gi2 = 0; gi2 < CULTURE_GROUPS.length && !foundId; gi2++) {
          var gg2 = CULTURE_GROUPS[gi2];
          for (var cj2 = 0; gg2.cultures && cj2 < gg2.cultures.length && !foundId; cj2++) {
            var cand2 = String(gg2.cultures[cj2].id).replace(/^cult-[^-]+-/, '');
            if (cand2 === normCult || gg2.cultures[cj2].id === maybeCulture) {
              foundId = gg2.cultures[cj2].id;
              foundGroup = gg2.id;
            }
          }
        }
      }
      if (foundId) {
        setTimeout(function () {
          try {
            hideCultureMiniPanel();
            showCultureMiniPanel(foundId, foundGroup);
          } catch (e) {}
          // Guarda edição para que o próximo inserir vire Salvar edição
          try {
            cultureMiniPanelState.editor._editingWidgetId = wId;
          } catch (e) {}
          try {
            if (typeof window._captureBgOriginal === 'function') window._captureBgOriginal();
          } catch (e) {}
        }, 350);
        return;
      }
    }
    // Genérico kpi/chart: destaca no catalogo e guarda para Salvar edição
    setTimeout(function () {
      try {
        window._editingWidgetIdForGeneric = wId;
        var card =
          document.querySelector('[data-widget-id="' + wId + '"]') ||
          document.querySelector('[onclick*="\'' + wId + '\'"]');
        if (card) {
          card.scrollIntoView({ behavior: 'smooth', block: 'center' });
          card.classList.add('ring-2', 'ring-emerald-500');
          setTimeout(function () {
            try {
              card.classList.remove('ring-2', 'ring-emerald-500');
            } catch (e) {}
          }, 2000);
        }
        if (typeof window._captureBgOriginal === 'function')
          try {
            window._captureBgOriginal();
          } catch (e) {}
      } catch (e) {}
    }, 400);
    return;
  }
  var cultureId = String(parts[0]).replace(/^cult_/, 'cult-');
  var kind = parts[1];
  var rest = String(parts[2] || '').replace(/gafico/g, 'grafico');
  var tokens = (rest || '').split('_');
  var wType = 'grafico',
    subtype = null,
    metricKey = rest;
  if (
    tokens.length >= 2 &&
    ['grafico', 'tabela', 'lista', 'gafico'].indexOf(tokens[tokens.length - 2]) >= 0
  ) {
    wType = tokens[tokens.length - 2] === 'gafico' ? 'grafico' : tokens[tokens.length - 2];
    var lastTok = tokens[tokens.length - 1];
    if (
      wType === 'grafico' &&
      ['line', 'bar', 'pie', 'doughnut', 'radar', 'polarArea', 'area', 'scatter'].indexOf(
        lastTok
      ) >= 0
    ) {
      subtype = lastTok;
    }
    metricKey = tokens.slice(0, tokens.length - 2).join('_');
  } else if (
    tokens.length === 1 &&
    ['grafico', 'tabela', 'lista', 'gafico'].indexOf(tokens[0]) >= 0
  ) {
    wType = tokens[0];
    metricKey = rest.replace(new RegExp(tokens[0] + '$'), '');
    if (metricKey.charAt(metricKey.length - 1) === '_') metricKey = metricKey.slice(0, -1);
  }

  var groupId = '';
  if (typeof CULTURE_GROUPS !== 'undefined' && CULTURE_GROUPS) {
    for (var gi = 0; gi < CULTURE_GROUPS.length && !groupId; gi++) {
      var g = CULTURE_GROUPS[gi];
      for (var ci = 0; g.cultures && ci < g.cultures.length && !groupId; ci++) {
        if (g.cultures[ci].id === cultureId) groupId = g.id;
      }
    }
    // Fallback para widgets antigos com prefixo cultura- (ex: cultura-arroz -> cult-graos-arroz)
    if (!groupId) {
      var norm = String(cultureId)
        .replace(/^cultura-/, '')
        .replace(/^cult-[^-]+-/, '');
      for (var gj = 0; gj < CULTURE_GROUPS.length && !groupId; gj++) {
        var gg = CULTURE_GROUPS[gj];
        for (var cj = 0; gg.cultures && cj < gg.cultures.length && !groupId; cj++) {
          var cand = String(gg.cultures[cj].id).replace(/^cult-[^-]+-/, '');
          if (cand === norm) {
            groupId = gg.id;
            cultureId = gg.cultures[cj].id;
          }
        }
      }
    }
  }
  if (!groupId) {
    openAddWidgetModal();
    return;
  }

  var modal = document.getElementById('add-widget-modal');
  if (modal && modal.classList.contains('hidden')) openAddWidgetModal();
  hideCultureMiniPanel();
  showCultureMiniPanel(cultureId, groupId);
  cultureMiniPanelState.tab = kind === 'producao' ? 'minha-producao' : 'mercado';
  var ed = cultureMiniPanelState.editor;
  ed._editingWidgetId = wId;
  if (cfg.chartStyleCategory) ed.category = cfg.chartStyleCategory;
  if (cfg.chartStyleVariant) ed.variant = cfg.chartStyleVariant;
  ed.mainColor = cfg.mainColor || cfg._mainColor || null;
  ed.metaEnabled = !!cfg._metaEnabled;
  ed.metaValue =
    cfg._metaValue === '' || cfg._metaValue === null || cfg._metaValue === undefined
      ? ''
      : cfg._metaValue;

  var cards =
    kind === 'mercado' ? cultureMiniPanelState.marketCards : cultureMiniPanelState.productionCards;
  for (var cix = 0; cix < (cards || []).length; cix++) {
    if (cards[cix].metricKey === metricKey) {
      ed.activeCard = cix;
      break;
    }
  }
  var activeCard = cards && cards[ed.activeCard];
  if (activeCard) {
    if (cfg.widgetType) activeCard.widgetType = cfg.widgetType;
    if (subtype) activeCard.chartSubtype = subtype;
  }

  ed.compare = [];
  var mCards = cultureMiniPanelState.marketCards || [];
  var pCards = cultureMiniPanelState.productionCards || [];
  (cfg._compareSeries || []).forEach(function (c) {
    var ckind = null;
    if (c.kind) ckind = c.kind;
    else if (c.idx !== undefined && c.idx !== null) ckind = mCards[c.idx] ? 'market' : 'production';
    if (!ckind) return;
    var src = ckind === 'market' ? mCards[c.idx] : pCards[c.idx];
    if (!src) return;
    ed.compare.push({
      idx: c.idx,
      label: c.label || src.title || src.metricKey || 'Série',
      color: c.color || null,
      kind: ckind,
    });
  });

  if (kind === 'producao') {
    cultureMiniPanelState.selectedRecordIds = (cfg.selectedRecords || []).slice();
  }

  renderCultureMiniPanel();
};

window.addWidgetFromMiniCard = function (cardIdx, cultureId, updateId) {
  var card = cultureMiniPanelState.marketCards[cardIdx];
  if (!card) {
    if (typeof showToast === 'function') showToast('warning', 'Selecione um card válido');
    return;
  }
  var ed = cultureMiniPanelState.editor || {
    category: 'linha',
    variant: 'suave',
    compare: [],
    mainColor: null,
  };
  var widgetType =
    ed.category === 'planilha' ? 'tabela' : ed.category === 'cartao' ? 'kpi' : 'grafico';
  var wType = widgetType;

  var chartSubtype = editorChartSubtype(ed, card);
  card.chartSubtype = chartSubtype;

  var widgetId = marketWidgetIdFor(cardIdx, cultureId);
  if (!widgetId) return;

  var existingOld = updateId ? widgets[updateId] : null;
  var isUpdate = !!updateId;
  var existing = widgets[widgetId];

  if (existing && existing.visible && !(isUpdate && existingOld && existingOld === existing)) {
    if (typeof showToast === 'function') showToast('warning', 'Widget já inserido para este card');
    return;
  }
  if (isUpdate && updateId !== widgetId && existingOld) existingOld.visible = false;

  var defaultSize = { w: 10, h: 5 };
  var pos;
  if (isUpdate && (existing || existingOld)) {
    var anchor = existing || existingOld;
    pos = { x: anchor.gridX, y: anchor.gridY };
  } else {
    pos = window.findFreePosition ? findFreePosition(defaultSize.w, defaultSize.h) : { x: 0, y: 0 };
  }
  if (!pos) {
    if (typeof showToast === 'function') showToast('warning', 'Espaço insuficiente na matriz');
    return;
  }

  var keepSize = isUpdate && (existing || existingOld);
  var mainCol = ed.mainColor || null;
  var mainRgb = mainCol ? hexToRgbList(mainCol) : null;

  // Copy chart data from card so dashboard widget can render
  var chartData = null;
  var cmpSeries = [];
  if ((card.history && card.history.length > 0) || (card.myHistory && card.myHistory.length > 0)) {
    var lbl = [];
    var mMap = {};
    var pMap = {};

    function pushYear(map, year, val) {
      if (!year || val === null || val === undefined) return;
      if (Object.prototype.hasOwnProperty.call(map, year)) return;
      map[year] = val;
      if (lbl.indexOf(year) < 0) lbl.push(year);
    }

    (card.history || []).forEach(function (h) {
      pushYear(mMap, String(h.ano || ''), miniNumber(h.valor));
    });
    (card.myHistory || []).forEach(function (h) {
      pushYear(pMap, String(h.ano || ''), miniNumber(h.valor));
    });

    (ed.compare || []).forEach(function (c, ci) {
      var srcCard =
        c.kind === 'market'
          ? cultureMiniPanelState.marketCards[c.idx] || null
          : cultureMiniPanelState.productionCards[c.idx] || null;
      if (!srcCard || !srcCard.history) return;
      var cMap = {};
      srcCard.history.forEach(function (h) {
        pushYear(cMap, String(h.ano || ''), miniNumber(h.valor));
      });
      if (Object.keys(cMap).length === 0) return;
      cmpSeries.push({
        idx: c.idx,
        label: c.label || 'Série ' + (ci + 1),
        color:
          c.color ||
          (function () {
            var pp = chartPalette().pie || [];
            return pp[ci % pp.length] || '#0f9d6e';
          })(),
        map: cMap,
      });
    });

    lbl.sort(function (a, b) {
      var na = parseInt(a, 10),
        nb = parseInt(b, 10);
      if (!isNaN(na) && !isNaN(nb)) return na - nb;
      return String(a).localeCompare(String(b), 'pt-BR', { numeric: true });
    });

    if (lbl.length > 0) {
      var datasets = [
        {
          label: card.source === 'ibge' ? 'IBGE' : card.title || card.metricKey,
          data: lbl.map(function (y) {
            return Object.prototype.hasOwnProperty.call(mMap, y) ? mMap[y] : null;
          }),
          borderColor: mainCol || '#0f9d6e',
          backgroundColor:
            wType === 'grafico' && chartSubtype === 'bar'
              ? mainRgb
                ? 'rgba(' + mainRgb.join(',') + ',0.6)'
                : 'rgba(15,157,110,0.6)'
              : mainRgb
                ? 'rgba(' + mainRgb.join(',') + ',0.08)'
                : 'rgba(15,157,110,0.08)',
          borderWidth: 4,
        },
      ];
      if (card.myHistory && card.myHistory.length > 0) {
        datasets.push({
          label: 'Propriedade',
          data: lbl.map(function (y) {
            return Object.prototype.hasOwnProperty.call(pMap, y) ? pMap[y] : null;
          }),
          borderColor: '#3b82f6',
          backgroundColor:
            wType === 'grafico' && chartSubtype === 'bar'
              ? 'rgba(59,130,246,0.6)'
              : 'rgba(59,130,246,0.08)',
          borderWidth: 4,
        });
      }
      // Séries comparadas escolhidas no editor
      cmpSeries.forEach(function (c) {
        datasets.push({
          label: c.label,
          data: lbl.map(function (y) {
            return Object.prototype.hasOwnProperty.call(c.map, y) ? c.map[y] : null;
          }),
          borderColor: c.color,
          backgroundColor:
            wType === 'grafico' && chartSubtype === 'bar'
              ? 'rgba(59,130,246,0.5)'
              : 'rgba(59,130,246,0.05)',
          borderWidth: 4,
        });
      });
      chartData = { labels: lbl, datasets: datasets };
    }
  }

  widgets[widgetId] = {
    gridX: pos.x,
    gridY: pos.y,
    gridW: keepSize ? (existing || existingOld).gridW : defaultSize.w,
    gridH: keepSize ? (existing || existingOld).gridH : defaultSize.h,
    visible: true,
    title: card.title || card.metricKey,
    showTitle: true,
    metricKey: card.metricKey,
    source: card.source || 'agrodoc',
    widgetType: widgetType,
    chartSubtype: chartSubtype,
    chartStyleCategory: ed.category,
    chartStyleVariant: ed.variant,
    mainColor: mainCol,
    _mainColor: mainCol,
    _compareSeries: cmpSeries.map(function (c) {
      return { idx: c.idx, label: c.label, color: c.color, data: c.map || {} };
    }),
    _chartData: chartData,
    _cardHistory: card.history || [],
    _cardMyHistory: card.myHistory || [],
    _lastMetric: card._lastMetric || null,
    _metaEnabled: !!ed.hasMeta,
    _metaValue:
      ed.metaValue === '' || ed.metaValue === null || ed.metaValue === undefined
        ? ''
        : ed.metaValue,
    _starred: isCardStarred('market', cardIdx),
  };
  // Salva imediato para garantir que o exato widget do painel apareca apos reload (sem perder formatacao)
  if (typeof window.saveWidgetsLayoutImmediate === 'function') window.saveWidgetsLayoutImmediate();
  else saveWidgetsLayout();
  renderWidgetsOnMatrix();

  // ABSOLUTO: nao faz refresh async que sobrescrevia _chartData e causava piscar tiny->grande
  // O widget salvo ja tem _chartData/_cardHistory exatos do painel; manter sem overwrite ate usuario clicar Atualizar

  showWidgetToast(isUpdate ? 'Widget atualizado!' : undefined);
  hideCultureMiniPanel();
  if (cultureMiniPanelState.editor) cultureMiniPanelState.editor._editingWidgetId = null;
};

window.addWidgetFromModal = function (widgetId, widgetType) {
  var st = typeof addWidget === 'function' ? addWidget(widgetId) : 'desconhecido';
  if (typeof renderAllWidgetGrids === 'function') {
    renderAllWidgetGrids();
  }
  if (st === 'existente') showWidgetToast('Widget já está no dashboard (destacado).');
  else if (st === 'sem-espaco') showWidgetToast('Sem espaço na matriz para este widget.');
  else if (st === 'desconhecido') showWidgetToast('Widget desconhecido.');
  else showWidgetToast();
};

function showWidgetToast(msg) {
  var toast = document.getElementById('widget-toast');
  var inner = document.getElementById('widget-toast-inner');
  var msgEl = document.getElementById('widget-toast-msg');
  if (!toast || !inner) return;
  msgEl.textContent = msg || 'Widget adicionado ao dashboard!';
  toast.classList.remove('hidden');
  requestAnimationFrame(function () {
    inner.style.transform = 'translateY(0)';
    inner.style.opacity = '1';
  });
  setTimeout(function () {
    inner.style.transform = 'translateY(8px)';
    inner.style.opacity = '0';
    setTimeout(function () {
      toast.classList.add('hidden');
    }, 300);
  }, 1800);
}
/* ═══ Preset System ═══ */
var _presetSuppressClickUntil = 0; // escopo compartilhado: sobrevive a re-renders (supressão pós-drag)
var PRESET_ICONS_CATEGORIZED = {
  vegetal: ['bi-tree', 'bi-flower1', 'bi-flower2', 'bi-sun', 'bi-cloud-sun', 'bi-droplet'],
  animal: ['bi-bug', 'bi-heart', 'bi-shield', 'bi-star', 'bi-award'],
  aquatico: [
    'bi-cloud-rain',
    'bi-snow',
    'bi-wind',
    'bi-umbrella',
    'bi-moon',
    'bi-sunrise',
    'bi-globe',
  ],
  logistico: [
    'bi-truck',
    'bi-box-seam',
    'bi-boxes',
    'bi-map',
    'bi-pin-map',
    'bi-geo-alt',
    'bi-shop',
    'bi-building',
    'bi-briefcase',
    'bi-speedometer2',
    'bi-cash-stack',
    'bi-bank',
    'bi-grid-3x3-gap',
    'bi-bar-chart',
    'bi-pie-chart',
    'bi-graph-up',
    'bi-graph-down',
    'bi-eyedropper',
    'bi-people',
    'bi-person-badge',
    'bi-calendar3',
    'bi-calendar-week',
    'bi-clipboard-data',
    'bi-file-earmark-bar-graph',
    'bi-graph-up-arrow',
    'bi-activity',
    'bi-layers',
    'bi-lightning',
    'bi-fire',
    'bi-key',
    'bi-gear',
    'bi-tools',
    'bi-cpu',
    'bi-phone',
    'bi-laptop',
    'bi-display',
  ],
};
var PRESET_ICONS = [
  'bi-speedometer2',
  'bi-cash-stack',
  'bi-bank',
  'bi-geo-alt',
  'bi-briefcase',
  'bi-grid-3x3-gap',
  'bi-bar-chart',
  'bi-pie-chart',
  'bi-graph-up',
  'bi-graph-down',
  'bi-box-seam',
  'bi-truck',
  'bi-droplet',
  'bi-sun',
  'bi-cloud-sun',
  'bi-tree',
  'bi-flower1',
  'bi-flower2',
  'bi-bug',
  'bi-eyedropper',
  'bi-people',
  'bi-person-badge',
  'bi-building',
  'bi-shop',
  'bi-house-door',
  'bi-calendar3',
  'bi-calendar-week',
  'bi-clipboard-data',
  'bi-file-earmark-bar-graph',
  'bi-graph-up-arrow',
  'bi-activity',
  'bi-layers',
  'bi-boxes',
  'bi-globe',
  'bi-map',
  'bi-pin-map',
  'bi-award',
  'bi-star',
  'bi-heart',
  'bi-lightning',
  'bi-fire',
  'bi-shield',
  'bi-key',
  'bi-gear',
  'bi-tools',
  'bi-cpu',
  'bi-phone',
  'bi-laptop',
  'bi-display',
  'bi-cloud-rain',
  'bi-snow',
  'bi-wind',
  'bi-umbrella',
  'bi-moon',
  'bi-sunrise',
];
var PRESET_COLORS = [
  '#0f9d6e',
  '#3b82f6',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#14b8a6',
  '#64748b',
  '#f97316',
  '#06b6d4',
  '#84cc16',
];

function getPresetOrder() {
  var order;
  try {
    order = JSON.parse(sget('matrix-preset-order'));
  } catch (e) {}
  var isAllowed = window._presetIsAllowed;
  var deleted = [];
  try {
    deleted = JSON.parse(localStorage.getItem('ampliagro-deleted-presets') || '[]');
  } catch (e) {
    deleted = [];
  }
  if (Array.isArray(order)) {
    var filtered = order.filter(function (k) {
      return isAllowed(k) && deleted.indexOf(k) === -1;
    });
    // adiciona presets novos que estão em PRESETS mas não na ordem (ex: criados em outro aba e sincronizados via server)
    try {
      var missing = Object.keys(PRESETS).filter(function (k) {
        return isAllowed(k) && deleted.indexOf(k) === -1 && filtered.indexOf(k) === -1;
      });
      if (missing.length) {
        filtered = filtered.concat(missing);
        try {
          savePresetOrder(filtered);
        } catch (e) {}
      }
    } catch (e) {}
    if (filtered.length !== order.length) {
      try {
        savePresetOrder(filtered);
      } catch (e) {}
      return filtered;
    }
    if (!filtered.length) return filtered;
    return filtered;
  }
  var keys = Object.keys(PRESETS).filter(function (k) {
    return isAllowed(k) && deleted.indexOf(k) === -1;
  });
  if (!keys.length) return [];
  return keys;
}

function savePresetOrder(order) {
  try {
    var json = JSON.stringify(order);
    // escrita síncrona direta para garantir persistência imediata (reload rápido)
    try {
      var sk = scopedKey('matrix-preset-order');
      localStorage.setItem(sk, json);
      if (typeof _lsCache !== 'undefined') _lsCache[sk] = json;
      // também garante chave sem escopo para compatibilidade
      if (sk !== 'matrix-preset-order') {
        try {
          localStorage.setItem('matrix-preset-order', json);
        } catch (e2) {}
      }
    } catch (e2) {}
    sset('matrix-preset-order', json);
    if (typeof sflush === 'function')
      try {
        sflush();
      } catch (e2) {}
  } catch (e) {}
  syncPresetsToPreferences();
  scheduleDashboardStateSync();
  if (typeof sflush === 'function')
    try {
      sflush();
    } catch (e) {}
}

function syncPresetsToPreferences() {
  if (typeof window.savePreferences !== 'function') return;
  var order = getPresetOrder();
  var active = sget('matrix-active-preset') || 'base-ia';
  var list = {};
  Object.keys(PRESETS).forEach(function (key) {
    // Store metadata only (omit widgets to keep preferences lean)
    list[key] = {
      icon: PRESETS[key].icon,
      color: PRESETS[key].color || '',
      label: PRESETS[key].label,
      cultures: PRESETS[key].cultures || [],
    };
  });
  // `presets` e' o mapa de PRESETS. A ordem e o preset activo nao sao
  // presets: moram em `presetIndex`. Antes viviam em `presets.{order,active,
  // list}` e a limpeza v13 lia cada chave de `presets` como um nome de preset
  // -- o que punha 'active' e 'order' na fila de limpeza. (portao C11)
  window.savePreferences({ presetIndex: { order: order, active: active, list: list } });
}

// A IDENTIDADE de um preset e' gerada aqui, no acto de salvar.
//
// Antes vinha do nome: `'custom-' + nome.toLowerCase().replace(...)`. O nome
// e' o que o utilizador escreve e o que ele muda; a identidade de um preset
// nao pode sair dai. Duas consequencias medidas:
//   - dois presets que o utilizador quer chamar igual colidiam na chave;
//   - apagar um preset e recria-lo com o MESMO nome reanimava os widgets do
//     antigo, porque a chave voltava a ser a mesma e o JSON antigo continuava
//     no armazenamento.
//
// A chave mantem o prefixo `custom-` porque e' o que `preset_permitido()`
// (app/presets.py) aceita; o corpo ja nao significa nada. O nome passa a ser
// so um ROTULO dentro do indice.
window._gerarIdPreset = function () {
  var t = Date.now().toString(36);
  var r = '';
  try {
    if (window.crypto && window.crypto.getRandomValues) {
      var a = new Uint32Array(2);
      window.crypto.getRandomValues(a);
      r = a[0].toString(36) + a[1].toString(36);
    }
  } catch (e) {}
  if (!r) r = Math.random().toString(36).slice(2, 10);
  return 'custom-p' + t + r.slice(0, 6);
};

// Onde a ordem, o preset activo e os metadados vivem. `presets` NAO entra:
// ver `syncPresetsToPreferences` e o portao C11.
function _presetIndex(prefs) {
  if (prefs && prefs.presetIndex && typeof prefs.presetIndex === 'object') {
    return prefs.presetIndex;
  }
  // FORMA LEGADA: { order, active, list } dentro de `presets`. Aceite na
  // leitura para nao perder a ordem de quem ja tinha, mas a proxima
  // sincronizacao escreve em `presetIndex` e a migracao de arranque limpa o
  // resto. `list` guarda os METADADOS por preset, nunca os widgets.
  if (prefs && prefs.presets && typeof prefs.presets === 'object') {
    var legado = prefs.presets;
    if (
      Array.isArray(legado.order) ||
      typeof legado.active === 'string' ||
      (legado.list && typeof legado.list === 'object')
    ) {
      return legado;
    }
  }
  return null;
}

function restorePresetsFromPreferences() {
  if (typeof window.getPreferences !== 'function') return;
  var prefs = window.getPreferences();
  var p = _presetIndex(prefs);
  if (!p) return;
  // Restore order — só se não houver ordem local (local wins: o drag fluido
  // salva no localStorage; o server só hidrata no primeiro uso/novo dispositivo)
  if (Array.isArray(p.order)) {
    var localOrder = null;
    try {
      localOrder = JSON.parse(sget('matrix-preset-order'));
    } catch (e) {}
    if (!Array.isArray(localOrder) || !localOrder.length) {
      try {
        sset('matrix-preset-order', JSON.stringify(p.order));
      } catch (e) {}
      try {
        localStorage.setItem('matrix-preset-order', JSON.stringify(p.order));
      } catch (e) {}
    }
  }
  // Restore active
  if (p.active) {
    try {
      sset('matrix-active-preset', p.active);
    } catch (e) {}
  }
  // Merge PRESETS metadata (cultures, icon, color, label) from preferences
  if (p.list && typeof p.list === 'object') {
    Object.keys(p.list).forEach(function (key) {
      var meta = p.list[key];
      if (PRESETS[key]) {
        PRESETS[key].cultures = meta.cultures || PRESETS[key].cultures || [];
        if (meta.icon) PRESETS[key].icon = meta.icon;
        if (meta.color !== undefined) PRESETS[key].color = meta.color;
        if (meta.label) PRESETS[key].label = meta.label;
      } else {
        // Custom preset that only exists in preferences — recreate shell
        // Seed PRESET_WIDGETS_JSON as well so hydratePresetWidgets can fill from localStorage
        if (!PRESET_WIDGETS_JSON[key]) PRESET_WIDGETS_JSON[key] = {};
        // IMPORTANT: Deep clone to prevent PRESETS[key].widgets from sharing the same
        // object reference as PRESET_WIDGETS_JSON[key]. Without this, mutating one
        // would affect the other, causing cross-preset pollution.
        PRESETS[key] = {
          icon: meta.icon || 'bi-speedometer2',
          color: meta.color || '',
          label: meta.label || key,
          cultures: meta.cultures || [],
          widgets: JSON.parse(JSON.stringify(PRESET_WIDGETS_JSON[key] || {})),
        };
      }
    });
  }
  // Hydrate widget data for all presets (including custom ones now seeded above)
  hydratePresetWidgets();
}

function renderPresetCarousel() {
  var container = document.getElementById('modal-preset-carousel');
  if (!container) return;
  // Attach trash zone events
  var trashZone = document.getElementById('preset-trash-zone');
  if (trashZone) {
    trashZone.onclick = null;
    trashZone.ondragover = function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      trashZone.classList.add('preset-trash-hover');
    };
    trashZone.ondragleave = function () {
      trashZone.classList.remove('preset-trash-hover');
    };
    trashZone.ondrop = function (e) {
      e.preventDefault();
      trashZone.classList.remove('preset-trash-hover', 'preset-trash-active');
      var key = e.dataTransfer.getData('text/plain');
      if (key && key !== 'visao-geral' && key !== 'visao-base' && PRESETS[key]) {
        if (confirm('Excluir preset "' + PRESETS[key].label + '"?')) deletePresetByKey(key);
      }
    };
  }
  var order = getPresetOrder();
  var activeKey = sget('matrix-active-preset') || 'base-ia';
  container.innerHTML = '';
  // Drop no vazio da barra (extremos): esquerda = inicio, direita = fim
  container.ondragover = function (e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };
  container.ondrop = function (e) {
    var fromKey = e.dataTransfer.getData('text/plain');
    if (!fromKey || e.target.closest('.modal-preset-card')) return;
    e.preventDefault();
    var rect = container.getBoundingClientRect();
    var isLeft = e.clientX < rect.left + 60;
    var o = getPresetOrder();
    var idx = o.indexOf(fromKey);
    if (idx < 0) return;
    o.splice(idx, 1);
    if (isLeft) o.unshift(fromKey);
    else o.push(fromKey);
    savePresetOrder(o);
    renderPresetCarousel();
    renderWidgetbarPresets();
  };
  order.forEach(function (key) {
    var p = PRESETS[key];
    if (!p) return;
    var isDefault = getPresetOrder().length <= 1;
    var card = document.createElement('div');
    card.className = 'modal-preset-card' + (key === activeKey ? ' active-preset' : '');
    card.draggable = true;
    card.dataset.presetKey = key;
    // Sombra = mesma cor do fundo do preset — por preset
    (function () {
      var c = p.color || '';
      var isValid =
        c && (/^#([0-9a-fA-F]{3,8})$/.test(c) || c.indexOf('rgb') === 0 || c.indexOf('hsl') === 0);
      if (!isValid) {
        if (key === 'visao-geral' || key.indexOf('visao') === 0) c = '#0f9d6e';
        else if (key.indexOf('financeiro') === 0) c = '#0f9d6e';
        else if (key.indexOf('campo') === 0) c = '#14b8a6';
        else c = '#64748b';
        isValid = true;
      }
      var isActive = key === activeKey;
      var hexToRgba = function (hex, a) {
        try {
          var h = hex.replace('#', '');
          if (h.length === 3)
            h = h
              .split('')
              .map(function (ch) {
                return ch + ch;
              })
              .join('');
          if (h.length === 6)
            return (
              'rgba(' +
              parseInt(h.slice(0, 2), 16) +
              ',' +
              parseInt(h.slice(2, 4), 16) +
              ',' +
              parseInt(h.slice(4, 6), 16) +
              ',' +
              a +
              ')'
            );
          return hex;
        } catch (e) {
          return hex;
        }
      };
      var bgA = isActive ? 0.1 : 0.06;
      var shA = isActive ? 0.22 : 0.14;
      card.style.background = hexToRgba(c, bgA);
      card.style.boxShadow =
        '0 4px 12px ' + hexToRgba(c, shA) + ', 0 1px 3px ' + hexToRgba(c, shA * 0.6);
      card.style.borderColor = hexToRgba(c, 0.18);
    })();
    var iconColor = p.color ? ' style="color:' + p.color + '"' : '';
    // se p.color era classe tailwind, iconColor já está como classe, mas card já tem bg/shadow por preset acima
    if (p.color && (/^#([0-9a-fA-F]{3,8})$/.test(p.color) || p.color.indexOf('rgb') === 0)) {
      iconColor = ' style="color:' + p.color + '"';
    }
    card.innerHTML =
      '<i class="bi ' +
      p.icon +
      '"' +
      iconColor +
      '></i><span class="preset-tooltip">' +
      p.label +
      '</span>';
    card.addEventListener('click', function (e) {
      if (e.target.closest('.preset-card-delete')) return;
      // Click selects the preset for editing
      document.querySelectorAll('.modal-preset-card').forEach(function (c) {
        c.classList.remove('selected-for-edit');
      });
      card.classList.add('selected-for-edit');
      editPresetForm(key);
    });
    // Double click loads the preset
    card.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      loadPreset(key);
      closePresetModal();
    });

    // Delete button
    var delBtn = card.querySelector('.preset-card-delete');
    if (delBtn) {
      delBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (!confirm('Excluir preset "' + p.label + '"?')) return;
        deletePresetByKey(key);
      });
    }
    // Drag reorder
    card.addEventListener('dragstart', function (e) {
      e.dataTransfer.setData('text/plain', key);
      e.dataTransfer.effectAllowed = 'move';
      card.classList.add('dragging');
      document.getElementById('preset-trash-zone').classList.add('preset-trash-active');
    });
    card.addEventListener('dragend', function () {
      card.classList.remove('dragging');
      document.getElementById('preset-trash-zone').classList.remove('preset-trash-active');
    });
    card.addEventListener('dragover', function (e) {
      e.preventDefault();
    });
    card.addEventListener('dragenter', function () {
      card.classList.add('drag-over');
    });
    card.addEventListener('dragleave', function () {
      card.classList.remove('drag-over');
    });
    card.addEventListener('drop', function (e) {
      e.preventDefault();
      card.classList.remove('drag-over');
      var fromKey = e.dataTransfer.getData('text/plain');
      if (fromKey === key) return;
      var order = getPresetOrder();
      var fromIdx = order.indexOf(fromKey);
      var toIdx = order.indexOf(key);
      if (fromIdx < 0 || toIdx < 0) return;
      // Se soltar na metade direita do card, insere depois (permite ir pro final)
      var rect = card.getBoundingClientRect();
      var isRightHalf = e.clientX > rect.left + rect.width / 2;
      order.splice(fromIdx, 1);
      toIdx = order.indexOf(key);
      if (isRightHalf) toIdx++;
      order.splice(toIdx, 0, fromKey);
      savePresetOrder(order);
      renderPresetCarousel();
      renderWidgetbarPresets();
    });
    container.appendChild(card);
  });
}

function deletePresetByKey(key) {
  // O preset-base e' imutavel: e' o ponto de partida do produtor e
  // some com ele o painel volta a ficar vazio. Recusa aqui, ANTES de
  // qualquer `delete`, e nao depois.
  if (window._presetImutavel && window._presetImutavel(key)) {
    if (window.showToast) window.showToast('O preset Assistente IA não pode ser excluído', 'error');
    return;
  }
  var _order = getPresetOrder();
  if (_order.length <= 1) {
    if (window.showToast) window.showToast('Não é possível excluir o último preset', 'error');
    return;
  }
  delete PRESETS[key];
  delete PRESET_WIDGETS_JSON[key];
  try {
    sremove('matrix-preset-json-' + key);
  } catch (e) {}
  try {
    localStorage.removeItem('matrix-preset-json-' + key);
  } catch (e) {}
  try {
    localStorage.removeItem('matrix-preset-json-' + key + '_u' + (window.AMPLIAGRO_UID || ''));
  } catch (e) {}
  try {
    sflush();
  } catch (e) {}
  try {
    if (window._markPresetDeleted) window._markPresetDeleted(key);
  } catch (e) {}
  try {
    if (window.AmpliagroPrefs) window.AmpliagroPrefs.purgePreset(key);
  } catch (e) {}
  // Havia aqui `removeItem('matrix-preset-json-' + key + '_u15')`: um id de
  // utilizador fixescrito no codigo. Num browser partilhado, apagar um preset
  // apagava o preset do utilizador 15. A varredura abaixo apanha todas as
  // variantes com escopo, incluindo a dele.
  // garante que nenhum JSON fantasma reste (varre tudo)
  try {
    var _toDel = [];
    for (var _i = 0; _i < localStorage.length; _i++) {
      var _kk = localStorage.key(_i);
      if (_kk && _kk.indexOf('matrix-preset-json-' + key) === 0) _toDel.push(_kk);
    }
    _toDel.forEach(function (_kk) {
      try {
        localStorage.removeItem(_kk);
      } catch (e) {}
    });
  } catch (e) {}
  var wasActive = (sget('matrix-active-preset') || 'base-ia') === key;
  var order = getPresetOrder().filter(function (k) {
    return k !== key;
  });
  savePresetOrder(order);
  if (wasActive) {
    var _next = order[0] || 'visao-geral';
    try {
      sset('matrix-active-preset', _next);
    } catch (e) {}
    try {
      if (typeof loadPreset === 'function') loadPreset(_next);
    } catch (e) {}
  } else {
    // SPA: só atualiza barra, não recarrega widgets se continuamos no mesmo preset
    try {
      dashboardLog('deletePreset:spa', { deleted: key, active: sget('matrix-active-preset') });
    } catch (e) {}
  }
  try {
    if (window.showToast) window.showToast('Preset excluído', 'success');
  } catch (e) {}
  // SPA: atualiza só carrossel/barra, sem tocar no .matrix-container
  renderPresetCarousel();
  renderWidgetbarPresets();
  // Força sync pro servidor já que key pode ser visao-* custom
  try {
    if (typeof persistDashboardStateToServer === 'function') persistDashboardStateToServer();
  } catch (e) {}
}

function renderWidgetbarPresets() {
  var container = document.getElementById('presets-carousel');
  if (!container) return;
  var order = getPresetOrder();
  var activeKey = sget('matrix-active-preset') || 'base-ia';
  container.innerHTML = '';
  order.forEach(function (key) {
    var p = PRESETS[key];
    if (!p) return;
    var el = document.createElement('div');
    el.className = 'preset-block' + (key === activeKey ? ' active-preset' : '');
    el.dataset.preset = key;
    el.dataset.name = p.label;
    el.title = p.label;
    // Sombra = mesma cor do fundo do preset (fix #sombra-preset) — por preset
    (function () {
      var c = p.color || '';
      var isValid =
        c && (/^#([0-9a-fA-F]{3,8})$/.test(c) || c.indexOf('rgb') === 0 || c.indexOf('hsl') === 0);
      if (!isValid) {
        // mapeia visao-geral e outros com classe tailwind para cor hex real
        if (key === 'visao-geral' || key.indexOf('visao') === 0) c = '#0f9d6e';
        else if (key.indexOf('financeiro') === 0) c = '#0f9d6e';
        else if (key.indexOf('campo') === 0) c = '#14b8a6';
        else c = '#64748b';
        isValid = true;
      }
      var isActive = key === activeKey;
      var hexToRgba = function (hex, a) {
        try {
          var h = hex.replace('#', '');
          if (h.length === 3)
            h = h
              .split('')
              .map(function (ch) {
                return ch + ch;
              })
              .join('');
          if (h.length === 6)
            return (
              'rgba(' +
              parseInt(h.slice(0, 2), 16) +
              ',' +
              parseInt(h.slice(2, 4), 16) +
              ',' +
              parseInt(h.slice(4, 6), 16) +
              ',' +
              a +
              ')'
            );
          return hex;
        } catch (e) {
          return hex;
        }
      };
      var bgA = isActive ? 0.14 : 0.09;
      var shA = isActive ? 0.28 : 0.18;
      el.style.background = hexToRgba(c, bgA);
      el.style.boxShadow =
        '0 4px 14px ' + hexToRgba(c, shA) + ', 0 1px 4px ' + hexToRgba(c, shA * 0.6);
      // O preset-base "IA" traz SVG: o helper devolve o SVG quando o
      // preset o tem, e o `<i class="bi">` (com a cor do preset)
      // quando nao — que e' o comportamento de sempre.
      var _corIcon = /^#([0-9a-fA-F]{3,8})$/.test(c) || c.indexOf('rgb') === 0 ? c : '';
      el.innerHTML = (
        window.presetIconHtml ||
        function (pp, cc) {
          return (
            '<i class="bi ' +
            (pp.icon || 'bi-puzzle') +
            '"' +
            (cc ? ' style="color:' + cc + '"' : '') +
            '></i>'
          );
        }
      )(p, _corIcon);
      return;
    })();
    if (!el.innerHTML)
      el.innerHTML = (
        window.presetIconHtml ||
        function (pp) {
          return '<i class="bi ' + (pp.icon || 'bi-puzzle') + '"></i>';
        }
      )(p);
    // click com supressão pós-drag (holding não dispara load)
    // em modo edição, click abre edição de cor/ícone (não troca preset)
    el.addEventListener('click', function (e) {
      if (Date.now() < (_presetSuppressClickUntil || 0)) {
        e.stopImmediatePropagation();
        e.preventDefault();
        return;
      }
      if (dragState) {
        e.stopImmediatePropagation();
        e.preventDefault();
        return;
      }
      var isEditing = false;
      try {
        var appbar = document.getElementById('dashboard-appbar');
        isEditing = !!(appbar && appbar.classList.contains('editing'));
        if (!isEditing && window.widgetbarState) isEditing = !!window.widgetbarState.isCustomMode;
        if (!isEditing && typeof window.__getEditFlags === 'function') {
          try {
            isEditing = !!window.__getEditFlags();
          } catch (err2) {}
        }
      } catch (err) {}
      if (isEditing) {
        e.preventDefault();
        e.stopPropagation();
        if (typeof window.editPresetForm === 'function') {
          window.editPresetForm(key);
          if (typeof window.openPresetModal === 'function') window.openPresetModal();
        }
        return;
      }
      loadPreset(key);
    });
    // duplo clique edita nome inline (igual modal)
    el.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      var oldLabel = p.label;
      var input = document.createElement('input');
      input.type = 'text';
      input.value = oldLabel;
      input.maxLength = 20;
      input.style.cssText =
        'position:absolute;left:50%;top:calc(100% + 10px);transform:translateX(-50%);width:140px;padding:6px 8px;border-radius:8px;border:1px solid var(--cor-nav-separador);background:var(--cor-nav-dropdown-fundo);font-size:0.75rem;color:var(--cor-nav-texto);z-index:2147483645;box-shadow:0 8px 24px rgba(0,0,0,0.15)';
      el.style.position = 'relative';
      el.appendChild(input);
      input.focus();
      input.select();
      var done = false;
      function finish(save) {
        if (done) return;
        done = true;
        var newName = input.value.trim();
        if (input.parentNode) input.parentNode.removeChild(input);
        if (save && newName && newName !== oldLabel) {
          p.label = newName;
          el.title = newName;
          el.dataset.name = newName;
          try {
            persistPresetWidgets(key, p.widgets);
          } catch (err) {}
          syncPresetsToPreferences();
          renderPresetCarousel();
          el.title = newName;
        }
      }
      input.addEventListener('blur', function () {
        finish(true);
      });
      input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') finish(true);
        else if (ev.key === 'Escape') finish(false);
      });
    });
    // === Drag fluido: segura 1s → arrasta livre no eixo X, troca ao passar por cima ===
    var dragState = null;
    var HOLD_MS = 1000;
    var MOVE_THR = 8;
    var _holdTimer = null,
      _holdStartX = 0,
      _holdStartY = 0,
      _holdRect = null,
      _holdContRect = null;
    var _holdCleanup = null;

    el.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      if (Date.now() < _presetSuppressClickUntil) return;
      // Permite drag mesmo em modo edi��o (bypassa click que abre editPresetForm)
      var appbar = document.getElementById('dashboard-appbar');
      var isEditing = !!(appbar && appbar.classList.contains('editing'));
      if (!isEditing && window.widgetbarState) isEditing = !!window.widgetbarState.isCustomMode;
      if (!isEditing && typeof window.__getEditFlags === 'function') {
        try {
          isEditing = !!window.__getEditFlags();
        } catch (err2) {}
      }
      // Se est� em modo edi��o, permite arrastar sem abrir formul�rio de edi��o
      // (drag fluido funciona independentemente do estado de edi��o)

      _holdStartX = e.clientX;
      _holdStartY = e.clientY;
      _holdRect = el.getBoundingClientRect();
      _holdContRect = container.getBoundingClientRect();
      clearTimeout(_holdTimer);
      el.classList.add('holding');
      _holdTimer = setTimeout(function () {
        if (!dragState) beginFluidDrag(_holdRect, _holdContRect, _holdStartX, _holdStartY);
      }, HOLD_MS);

      function onHoldMove(ev) {
        if (
          Math.abs(ev.clientX - _holdStartX) > MOVE_THR ||
          Math.abs(ev.clientY - _holdStartY) > MOVE_THR
        ) {
          clearTimeout(_holdTimer);
          _holdTimer = null;
          el.classList.remove('holding');
          cleanupHold();
        }
      }
      function onHoldUp() {
        clearTimeout(_holdTimer);
        _holdTimer = null;
        el.classList.remove('holding');
        cleanupHold();
      }
      function cleanupHold() {
        document.removeEventListener('mousemove', onHoldMove);
        document.removeEventListener('mouseup', onHoldUp);
        _holdCleanup = null;
      }
      _holdCleanup = cleanupHold;
      document.addEventListener('mousemove', onHoldMove);
      document.addEventListener('mouseup', onHoldUp);
    });

    function beginFluidDrag(rect, contRect, startX, startY) {
      if (_holdCleanup) _holdCleanup();
      clearTimeout(_holdTimer);
      _holdTimer = null;
      el.classList.remove('holding');
      // ghost preso no eixo X (igual slider) - usa fixed com transform
      var ghost = el.cloneNode(true);
      ghost.className = 'preset-block preset-ghost';
      ghost.style.cssText =
        'width:32px;height:32px;z-index:2147483647;pointer-events:none;opacity:0.75;box-shadow:0 8px 24px rgba(0,0,0,0.22);will-change:transform;';
      ghost.style.setProperty('position', 'fixed', 'important');
      ghost.style.setProperty('left', '0', 'important');
      ghost.style.setProperty('top', '0', 'important');
      ghost.style.setProperty(
        'transform',
        'translate3d(' + rect.left + 'px,' + rect.top + 'px,0) scale(1.05)',
        'important'
      );
      ghost.dataset.preset = key;
      ghost.dataset.origLeft = rect.left;
      ghost.dataset.origTop = rect.top;
      document.body.appendChild(ghost);
      // placeholder animado que ocupa o espaço
      var ph = document.createElement('div');
      ph.className = 'preset-block placeholder';
      ph.dataset.placeholderFor = key;
      el.parentNode.insertBefore(ph, el);
      el.style.setProperty('display', 'none', 'important');

      var others = Array.from(container.children).filter(function (c) {
        return c.dataset.preset && c !== el;
      });
      // guarda ordem atual (lógica, sem duplicar placeholder)
      var curOrder = order.slice();

      dragState = {
        el: el,
        ghost: ghost,
        ph: ph,
        key: key,
        rect: rect,
        contRect: contRect,
        startX: startX,
        startY: startY,
        others: others,
        order: order.slice(),
        curOrder: curOrder,
        raf: 0,
        _lastX: startX,
      };
      container.classList.add('drag-active');
      // habilita transição suave nos outros presets (vão deslizar)
      others.forEach(function (o) {
        o.style.transition = 'transform 180ms cubic-bezier(0.2,0,0,1)';
        o.style.willChange = 'transform';
      });
      document.addEventListener('mousemove', onFluidMove);
      document.addEventListener('mouseup', onFluidEnd);
      // feedback visual que entrou em modo drag
      el.style.opacity = ''; // já escondido
    }

    function onFluidMove(e) {
      if (!dragState) return;
      e.preventDefault();
      dragState._lastX = e.clientX;
      if (dragState.raf) return;
      dragState.raf = requestAnimationFrame(function () {
        dragState.raf = 0;
        var curX = dragState._lastX != null ? dragState._lastX : e.clientX;
        var dx = curX - dragState.startX;
        // clamp ao container (trava X como slider)
        var minDx = dragState.contRect.left - dragState.rect.left - 8;
        var maxDx = dragState.contRect.right - dragState.rect.right + 8;
        dx = Math.max(minDx, Math.min(maxDx, dx));
        dragState.ghost.style.setProperty(
          'transform',
          'translate3d(' +
            (dragState.rect.left + dx) +
            'px,' +
            dragState.rect.top +
            'px,0) scale(1.05)',
          'important'
        );
        var ghostCenter = dragState.rect.left + 16 + dx;
        // PERF (layout thrashing): antes isto fazia ~2 recalculos de
        // estilo POR WIDGET a cada frame de drag (getBoundingClientRect
        // lido, depois `void o.offsetWidth` forcando de novo). Com 46
        // widgets viram dezenas por frame, e o Chrome reporta
        // "[Violation] Forced reflow while executing JavaScript".
        // Agora sao 3 no total: ler antes, ler depois do move, e um
        // unico reflow para "virar" as transicoes.
        // LEITURA 1 (1 reflow): retangulos antes de mover o placeholder.
        var antes = rectsOnce(dragState.others);
        var newIdx = findNewIdx(ghostCenter, antes);
        var oldIdx = dragState.order.indexOf(dragState.key);
        if (newIdx !== oldIdx && newIdx !== -1) {
          movePlaceholderTo(newIdx);
          dragState.order.splice(oldIdx, 1);
          dragState.order.splice(newIdx, 0, dragState.key);
          dragState.curOrder = dragState.order.slice();
          // LEITURA 2 (1 reflow): posicao depois do movimento.
          var depois = rectsOnce(dragState.others);
          var byEl = new Map();
          for (var i = 0; i < depois.length; i++) byEl.set(depois[i].el, depois[i].left);
          // ESCRITA 1: calcula e aplica todos os deltas, sem ler nada
          var moves = [];
          for (var j = 0; j < antes.length; j++) {
            var d = antes[j].left - byEl.get(antes[j].el);
            if (d !== 0) moves.push({ el: antes[j].el, d: d });
          }
          for (var m = 0; m < moves.length; m++) {
            moves[m].el.style.transition = 'none';
            moves[m].el.style.transform = 'translateX(' + moves[m].d + 'px)';
          }
          // 1 unico reflow para o browser enxergar o estado sem transition
          if (moves.length) void dragState.others[0].offsetWidth;
          for (var q = 0; q < moves.length; q++) {
            moves[q].el.style.transition = 'transform 180ms cubic-bezier(0.2,0,0,1)';
            moves[q].el.style.transform = 'translateX(0)';
          }
        }
      });
    }

    // Le o geometry de N elementos em UM unico layout. Ler dentro de um
    // forEach que depois escreve forca um recalculo sincrono por elemento.
    function rectsOnce(els) {
      var out = new Array(els.length);
      for (var i = 0; i < els.length; i++) {
        var r = els[i].getBoundingClientRect();
        out[i] = { el: els[i], left: r.left, width: r.width, mid: r.left + r.width / 2 };
      }
      return out;
    }

    // `cached` evita reler o layout: findNewIdx era chamado todo frame e
    // lia getBoundingClientRect() DENTRO do comparator do sort (O(n log n)
    // leituras) e mais 2x por elemento no laco seguinte.
    function findNewIdx(ghostCenter, cached) {
      // Extremos: se arrastar até a borda do container, aloca direto no início/fim
      var contL = dragState.contRect.left,
        contR = dragState.contRect.right;
      var base = cached || rectsOnce(dragState.others);
      if (ghostCenter <= contL + 24) return 0;
      if (ghostCenter >= contR - 24) return base.length;
      var sorted = base.slice().sort(function (a, b) {
        return a.left - b.left;
      });
      var cnt = 0;
      for (var i = 0; i < sorted.length; i++) {
        if (ghostCenter > sorted[i].mid) cnt++;
        else break;
      }
      return cnt; // 0..others.length
    }

    function movePlaceholderTo(newIdx) {
      if (dragState.ph.parentNode) dragState.ph.parentNode.removeChild(dragState.ph);
      var remaining = Array.from(container.children).filter(function (c) {
        return c !== dragState.el && c !== dragState.ph;
      });
      if (newIdx >= remaining.length) container.appendChild(dragState.ph);
      else container.insertBefore(dragState.ph, remaining[newIdx]);
    }

    function onFluidEnd(e) {
      if (!dragState) return;
      if (dragState.raf) {
        cancelAnimationFrame(dragState.raf);
        dragState.raf = 0;
      }
      document.removeEventListener('mousemove', onFluidMove);
      document.removeEventListener('mouseup', onFluidEnd);
      container.classList.remove('drag-active');
      dragState.others.forEach(function (o) {
        o.style.transition = '';
        o.style.transform = '';
        o.style.willChange = '';
      });
      var newOrder = dragState.curOrder.slice();
      var oldOrder = getPresetOrder();
      var changed = JSON.stringify(newOrder) !== JSON.stringify(oldOrder);
      if (dragState.ghost.parentNode) dragState.ghost.parentNode.removeChild(dragState.ghost);
      if (dragState.ph.parentNode) dragState.ph.parentNode.removeChild(dragState.ph);
      dragState.el.style.removeProperty('display');
      dragState.el.style.opacity = '';
      dragState.el.classList.remove('holding');
      _presetSuppressClickUntil = Date.now() + 650;
      var saved = dragState;
      dragState = null;
      clearTimeout(_holdTimer);
      _holdTimer = null;
      if (changed) {
        savePresetOrder(newOrder);
        if (typeof sflush === 'function')
          try {
            sflush();
          } catch (e) {}
        renderPresetCarousel();
        renderWidgetbarPresets();
      }
    }

    container.appendChild(el);
  });
  initPresetPreviews();
}
// Expõe o renderizador oficial para o widget-bar-intelligent.js delegar
// (preserva drag fluido hold 1s + FLIP + persistência)
window.renderWidgetbarPresets = renderWidgetbarPresets;

function populateCloneDropdown() {
  var sel = document.getElementById('preset-clone-select');
  if (!sel) return;
  sel.innerHTML = '<option value="">Sem widgets iniciais (Painel vazio)</option>';
  var order = getPresetOrder();
  order.forEach(function (k) {
    if (!PRESETS[k]) return;
    var opt = document.createElement('option');
    opt.value = k;
    opt.textContent = PRESETS[k].label;
    sel.appendChild(opt);
  });
}
function addNewPresetForm() {
  var form = document.getElementById('preset-edit-form');
  var nameInput = document.getElementById('preset-name-input');
  // Live preview typing
  if (!nameInput._liveBound) {
    nameInput.addEventListener('input', liveUpdatePresetCarouselPreview);
    nameInput._liveBound = true;
  }
  var isVisible = form.style.display === 'block';
  form.style.display = isVisible ? 'none' : 'block';
  if (isVisible) {
    // remove live preview card
    var live = document.querySelector('.modal-preset-card[data-preset-key="__live_new_preset__"]');
    if (live) live.remove();
    return;
  }
  document.querySelectorAll('.modal-preset-card').forEach(function (c) {
    c.classList.remove('selected-for-edit');
  });
  nameInput.value = '';
  nameInput.dataset.editKey = '';
  document.getElementById('preset-delete-btn').style.display = 'none';
  var cloneGroup = document.getElementById('preset-clone-group');
  if (cloneGroup) cloneGroup.style.display = 'block';
  populateCloneDropdown();
  var saveBtn = document.getElementById('preset-save-btn');
  if (saveBtn) saveBtn.textContent = 'Finalizar e adicionar presets';
  renderColorGrid('');
  renderIconGrid('bi-tree'); // default icon
  liveUpdatePresetCarouselPreview();
}

window.editPresetForm = function (key) {
  var p = PRESETS[key];
  if (!p) return;
  document.getElementById('preset-edit-form').style.display = 'block';
  var nameInput = document.getElementById('preset-name-input');
  nameInput.value = p.label;
  nameInput.dataset.editKey = key;
  if (!nameInput._liveBound) {
    nameInput.addEventListener('input', liveUpdatePresetCarouselPreview);
    nameInput._liveBound = true;
  }
  // remove live new card if exists
  var live = document.querySelector('.modal-preset-card[data-preset-key="__live_new_preset__"]');
  if (live) live.remove();
  document.getElementById('preset-delete-btn').style.display =
    getPresetOrder().length <= 1 ? 'none' : 'inline-flex';
  var cloneGroup = document.getElementById('preset-clone-group');
  if (cloneGroup) cloneGroup.style.display = 'none';
  var saveBtn = document.getElementById('preset-save-btn');
  if (saveBtn) saveBtn.textContent = 'Salvar';
  renderColorGrid(p.color || '');
  renderIconGrid(p.icon);
};
window.duplicatePresetForm = function () {
  var nameInput = document.getElementById('preset-name-input');
  var editKey = nameInput.dataset.editKey;
  var p = PRESETS[editKey];
  if (!p) return;
  var baseName = p.label + ' cópia';
  var newName = baseName;
  var n = 1;
  while (
    Object.values(PRESETS).some(function (v) {
      return v.label === newName;
    })
  ) {
    n++;
    newName = baseName + ' ' + n;
  }
  var newKey =
    'custom-' + newName.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Date.now().toString(36);
  var clonedWidgets = JSON.parse(JSON.stringify(p.widgets || {}));
  PRESETS[newKey] = {
    icon: p.icon,
    label: newName,
    color: p.color || '',
    cultures: (p.cultures || []).slice(),
    widgets: clonedWidgets,
  };
  PRESET_WIDGETS_JSON[newKey] = JSON.parse(JSON.stringify(clonedWidgets));
  try {
    persistPresetWidgets(newKey, clonedWidgets);
  } catch (e) {}
  var order = getPresetOrder();
  order.push(newKey);
  savePresetOrder(order);
  renderPresetCarousel();
  renderWidgetbarPresets();
  // abre edição do duplicado
  editPresetForm(newKey);
  window.addFilterTagSafe('Preset duplicado: ' + newName);
};

function getFlatCultureList() {
  var out = [];
  if (typeof CULTURE_GROUPS === 'undefined') return out;
  CULTURE_GROUPS.forEach(function (g) {
    g.cultures.forEach(function (c) {
      out.push({ id: c.id, title: c.title, icon: c.icon, group: g.title });
    });
  });
  return out;
}

function renderPresetCultureList(selectedIds) {
  var list = document.getElementById('preset-culture-list');
  var searchInput = document.getElementById('preset-culture-search');
  if (!list) return;
  if (searchInput) searchInput.value = '';
  selectedIds = selectedIds || [];
  var all = getFlatCultureList();
  list.innerHTML = '';
  all.forEach(function (c) {
    var el = document.createElement('div');
    el.className = 'preset-culture-item' + (selectedIds.indexOf(c.id) >= 0 ? ' selected' : '');
    el.dataset.cultureId = c.id;
    el.innerHTML =
      '<div class="culture-check"><i class="bi bi-check"></i></div><i class="bi ' +
      c.icon +
      '"></i><span>' +
      c.title +
      '</span><span class="culture-group">' +
      c.group +
      '</span>';
    el.addEventListener('click', function () {
      el.classList.toggle('selected');
    });
    list.appendChild(el);
  });
}

window.filterPresetCultures = function (query) {
  var items = document.querySelectorAll('#preset-culture-list .preset-culture-item');
  var q = query.toLowerCase().trim();
  items.forEach(function (item) {
    var text = item.textContent.toLowerCase();
    item.style.display = !q || text.indexOf(q) >= 0 ? 'flex' : 'none';
  });
};

function getSelectedCultures() {
  var items = document.querySelectorAll('#preset-culture-list .preset-culture-item.selected');
  return Array.from(items).map(function (el) {
    return el.dataset.cultureId;
  });
}

window.openPresetModal = function () {
  var overlay = document.getElementById('preset-modal-overlay');
  var modal = document.getElementById('preset-modal');
  if (!overlay || !modal) return;
  renderPresetCarousel();
  // Ensure form starts hidden
  document.getElementById('preset-edit-form').style.display = 'none';
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
};

window.closePresetModal = function () {
  var overlay = document.getElementById('preset-modal-overlay');
  var modal = document.getElementById('preset-modal');
  if (!overlay || !modal) return;
  overlay.classList.add('hidden');
  overlay.classList.remove('flex');
  modal.classList.add('hidden');
  modal.classList.remove('flex');
};

function liveUpdatePresetCarouselPreview() {
  var nameInput = document.getElementById('preset-name-input');
  var editKey = nameInput ? nameInput.dataset.editKey : '';
  var pendingKey = '__live_new_preset__';
  var isNew = !editKey;
  var targetKey = isNew ? pendingKey : editKey;
  var iconEl = document.querySelector('.preset-icon-option.selected i');
  var icon = iconEl
    ? iconEl.className.split(' ').find(function (c) {
        return c.indexOf('bi-') === 0;
      }) || 'bi-tree'
    : 'bi-tree';
  var colorEl = document.querySelector('#preset-color-grid .selected');
  var color = '';
  if (colorEl) {
    var idx = Array.from(
      document.querySelectorAll('#preset-color-grid .preset-color-option')
    ).indexOf(colorEl);
    if (idx >= 0 && idx < PRESET_COLORS.length) color = PRESET_COLORS[idx];
  }
  var label = nameInput ? nameInput.value.trim() : '';
  if (!label) label = isNew ? 'Novo preset' : PRESETS[editKey] ? PRESETS[editKey].label : 'Preset';
  var container = document.getElementById('modal-preset-carousel');
  if (!container) return;
  var card = container.querySelector('.modal-preset-card[data-preset-key="' + targetKey + '"]');
  if (isNew && !card) {
    card = document.createElement('div');
    card.className = 'modal-preset-card live-preview';
    card.dataset.presetKey = pendingKey;
    card.style.opacity = '0.9';
    card.style.borderStyle = 'dashed';
    card.style.borderColor = color || '#0b5e3f';
    card.style.background = 'linear-gradient(180deg, #fff, #f4f8fb)';
    container.appendChild(card);
  }
  if (!card) return;
  var iconColor = color ? ' style="color:' + color + '"' : '';
  card.innerHTML = '<i class="bi ' + icon + '"' + iconColor + '></i><span>' + label + '</span>';
  card.title = label;
  if (color) card.style.borderColor = color;
  // Garante visível: rola até o fim
  try {
    container.scrollLeft = container.scrollWidth;
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'end' });
  } catch (e) {}
  // Também atualiza editando existente direto no carousel
  if (!isNew) {
    var existing = container.querySelector('.modal-preset-card[data-preset-key="' + editKey + '"]');
    if (existing && existing !== card) {
      existing.querySelector('i').className = 'bi ' + icon;
      if (color) existing.querySelector('i').style.color = color;
      else existing.querySelector('i').style.color = '';
      existing.querySelector('span').textContent = label;
    }
  }
}
function renderIconGrid(selected) {
  ['vegetal', 'animal', 'aquatico', 'logistico'].forEach(function (category) {
    var grid = document.getElementById('preset-icon-carousel-' + category);
    if (!grid) return;
    grid.innerHTML = '';
    PRESET_ICONS_CATEGORIZED[category].forEach(function (icon) {
      var el = document.createElement('div');
      el.className = 'preset-icon-option' + (icon === selected ? ' selected' : '');
      el.innerHTML = '<i class="bi ' + icon + ' text-base"></i>';
      el.title = icon;
      el.dataset.icon = icon;
      el.addEventListener('click', function () {
        document.querySelectorAll('.preset-icon-option').forEach(function (o) {
          o.classList.remove('selected');
        });
        el.classList.add('selected');
        liveUpdatePresetCarouselPreview();
      });

      el.addEventListener('mousemove', function (e) {
        var rect = el.getBoundingClientRect();
        var x = e.clientX - rect.left;
        var y = e.clientY - rect.top;
        el.style.setProperty('--card-glow-x', x + 'px');
        el.style.setProperty('--card-glow-y', y + 'px');
      });

      grid.appendChild(el);
    });
  });
}
function renderColorGrid(selected) {
  var grid = document.getElementById('preset-color-grid');
  if (!grid) return;
  grid.innerHTML = '';
  PRESET_COLORS.forEach(function (color) {
    var el = document.createElement('div');
    el.className = 'preset-color-option' + (color === selected ? ' selected' : '');
    el.style.background = color;
    el.title = color;
    el.addEventListener('click', function () {
      grid.querySelectorAll('.preset-color-option').forEach(function (o) {
        o.classList.remove('selected');
      });
      el.classList.add('selected');
      liveUpdatePresetCarouselPreview();
    });
    grid.appendChild(el);
  });
  var none = document.createElement('div');
  none.className = 'preset-color-option' + (!selected ? ' selected' : '');
  none.style.cssText =
    'background: repeating-linear-gradient(45deg, rgba(200,200,200,0.4) 0px, rgba(200,200,200,0.4) 3px, transparent 3px, transparent 6px); display: flex; align-items: center; justify-content: center; font-size: 11px;';
  none.innerHTML = '<i class="bi bi-x"></i>';
  none.title = 'Cor padrão';
  none.addEventListener('click', function () {
    grid.querySelectorAll('.preset-color-option').forEach(function (o) {
      o.classList.remove('selected');
    });
    none.classList.add('selected');
    liveUpdatePresetCarouselPreview();
  });
  grid.appendChild(none);
}
window.autoBuildOnboardingPreset = function () {
  return new Promise(function (resolve) {
    var keys = [];
    try {
      keys = JSON.parse(sget('ampliagro-onboard-cultures') || '[]');
    } catch (e) {
      keys = [];
    }
    sremove('ampliagro-onboard-cultures');
    if (!Array.isArray(keys) || !keys.length) {
      resolve();
      return;
    }
    if (!window.CulturesLoader || typeof window.CulturesLoader.ready !== 'function') {
      resolve();
      return;
    }
    CulturesLoader.ready(function () {
      try {
        if (!window.CULTURE_GROUPS || !window.CULTURE_GROUPS.length) {
          resolve();
          return;
        }
        var pairs = [];
        keys.forEach(function (k) {
          for (
            var gi = 0;
            gi < window.CULTURE_GROUPS.length &&
            !pairs.some(function (p) {
              return p.cultureId === k;
            });
            gi++
          ) {
            var g = window.CULTURE_GROUPS[gi];
            for (var ci = 0; ci < g.cultures.length; ci++) {
              if (g.cultures[ci].id === k) {
                pairs.push({ cultureId: k, groupId: g.id });
                break;
              }
            }
          }
        });
        if (!pairs.length) {
          resolve();
          return;
        }
        // Brand-new dashboard: start from the base-ia preset, then add culture widgets
        if (!Object.keys(widgets).length) {
          widgets = clonePresetWidgets('base-ia');
        }
        pairs.forEach(function (pair) {
          cultureMiniPanelState = {
            cultureId: pair.cultureId,
            groupId: pair.groupId,
            tab: 'mercado',
            selectedType: null,
            marketCards: buildMarketCards(pair.cultureId, pair.groupId),
            availableUFs: [],
          };
          cultureMiniPanelState.marketCards.forEach(function (card, idx) {
            if (card.source === 'no_data') return;
            addWidgetFromMiniCard(idx, pair.cultureId);
          });
        });
        if (Object.keys(widgets).length) {
          var presetKey = 'custom-minhas-culturas';
          var culturesList = pairs.map(function (p) {
            return p.cultureId;
          });
          if (!PRESETS[presetKey]) {
            // Só cria se não existe — não clona por cima de preset existente com widgets diferentes
            PRESETS[presetKey] = {
              icon: 'bi-flower1',
              label: 'Minhas Culturas',
              cultures: culturesList,
              widgets: JSON.parse(JSON.stringify(widgets)),
            };
            PRESET_WIDGETS_JSON[presetKey] = JSON.parse(JSON.stringify(widgets));
            var order = getPresetOrder();
            if (order.indexOf(presetKey) === -1) order.push(presetKey);
            savePresetOrder(order);
            persistPresetWidgets(presetKey, widgets);
          } else {
            // Preset já existe — não sobrescreve widgets, só garante culturas
            if (!PRESETS[presetKey].cultures || !PRESETS[presetKey].cultures.length) {
              PRESETS[presetKey].cultures = culturesList;
              PRESET_WIDGETS_JSON[presetKey] =
                PRESET_WIDGETS_JSON[presetKey] || _fastClone(PRESETS[presetKey].widgets || {});
            }
          }
          sset('matrix-active-preset', presetKey);
          syncPresetsToPreferences();
        }
      } catch (e) {
        console.warn('[onboarding] autoBuild error:', e);
      }
      resolve();
    });
  });
};

window.savePresetForm = function () {
  var nameInput = document.getElementById('preset-name-input');
  var editKey = nameInput.dataset.editKey || '';
  var name = nameInput.value.trim();
  if (!name) {
    nameInput.focus();
    return;
  }
  var iconEl = document.querySelector('.preset-icon-option.selected i');
  var icon = iconEl
    ? iconEl.className.replace('bi ', '').replace(' text-lg', '')
    : 'bi-speedometer2';
  var colorEl = document.querySelector('#preset-color-grid .selected');
  var color = '';
  if (colorEl) {
    var bg = colorEl.style.background || '';
    if (bg && bg.indexOf('repeating') === -1) {
      var idx = Array.from(
        document.querySelectorAll('#preset-color-grid .preset-color-option')
      ).indexOf(colorEl);
      if (idx >= 0 && idx < PRESET_COLORS.length) color = PRESET_COLORS[idx];
      else color = bg;
    }
  }
  var order = getPresetOrder();
  var isNew = false;
  var localWidgets = {};

  if (!editKey) {
    // New preset - check cloning
    isNew = true;
    var cloneSel = document.getElementById('preset-clone-select');
    if (cloneSel && cloneSel.value && PRESETS[cloneSel.value]) {
      localWidgets = JSON.parse(JSON.stringify(PRESETS[cloneSel.value].widgets || {}));
    }
  } else if (PRESETS[editKey]) {
    localWidgets = JSON.parse(JSON.stringify(PRESETS[editKey].widgets || {}));
  }

  var clonedForPRESETS = JSON.parse(JSON.stringify(localWidgets));
  var clonedForJSON = JSON.parse(JSON.stringify(localWidgets));

  if (!isNew && PRESETS[editKey]) {
    PRESETS[editKey].icon = icon;
    PRESETS[editKey].color = color;
    PRESETS[editKey].label = name;
    // PRESETS[editKey].widgets = clonedForPRESETS; // Dont overwrite widgets on simple edit
    // PRESET_WIDGETS_JSON[editKey] = clonedForJSON;
  } else {
    // A identidade NAO sai do nome. Sai do gerador. Dois presets com o mesmo
    // rotulo coexistem; apagar e recriar com o mesmo rotulo nasce vazio.
    var key = window._gerarIdPreset();
    var tentativas = 0;
    while (PRESETS[key] && tentativas < 8) {
      key = window._gerarIdPreset();
      tentativas++;
    }
    PRESETS[key] = {
      icon: icon,
      color: color,
      label: name,
      cultures: [],
      widgets: clonedForPRESETS,
    };
    PRESET_WIDGETS_JSON[key] = clonedForJSON;
    try {
      if (window._unmarkPresetDeleted) window._unmarkPresetDeleted(key);
    } catch (e) {}
    try {
      persistPresetWidgets(key, localWidgets);
    } catch (err) {}
    order.push(key);
    editKey = key;
  }
  savePresetOrder(order);
  if (typeof sflush === 'function')
    try {
      sflush();
    } catch (e) {}
  renderPresetCarousel();
  renderWidgetbarPresets();
  closePresetModal();

  if (isNew) {
    // Load the newly created preset
    loadPreset(editKey);
    // Open widget panel to allow user to add widgets to the blank/cloned preset
    if (typeof window.openWidgetPanel === 'function') {
      window.openWidgetPanel();
    }
  }
};

window.deletePresetForm = function () {
  var nameInput = document.getElementById('preset-name-input');
  var editKey = nameInput.dataset.editKey;
  if (!editKey || !PRESETS[editKey]) return;
  var _order = getPresetOrder();
  if (_order.length <= 1) {
    if (window.showToast) window.showToast('Não é possível excluir o último preset', 'error');
    return;
  }
  if (!confirm('Excluir preset "' + (PRESETS[editKey].label || editKey) + '"?')) return;
  delete PRESETS[editKey];
  delete PRESET_WIDGETS_JSON[editKey];
  try {
    sremove('matrix-preset-json-' + editKey);
  } catch (e) {}
  try {
    if (window._markPresetDeleted) window._markPresetDeleted(editKey);
  } catch (e) {}
  try {
    if (window.AmpliagroPrefs) window.AmpliagroPrefs.purgePreset(editKey);
  } catch (e) {}
  var wasActive = (sget('matrix-active-preset') || 'base-ia') === editKey;
  var order = getPresetOrder().filter(function (k) {
    return k !== editKey;
  });
  savePresetOrder(order);
  if (wasActive) {
    var _next = order[0] || 'visao-geral';
    try {
      sset('matrix-active-preset', _next);
    } catch (e) {}
    try {
      if (typeof loadPreset === 'function') loadPreset(_next);
    } catch (e) {}
  } else {
    try {
      dashboardLog('deletePresetForm:spa', { deleted: editKey });
    } catch (e) {}
  }
  try {
    if (window.showToast) window.showToast('Preset excluído', 'success');
  } catch (e) {}
  renderPresetCarousel();
  renderWidgetbarPresets();
  try {
    if (typeof persistDashboardStateToServer === 'function') persistDashboardStateToServer();
  } catch (e) {}
  closePresetModal();
};

// Captura infos do widget selecionado e preview em tempo real para Cor de Fundo
window._bgOriginalColor = null;
window._bgPreviewColor = null;
window._captureBgOriginal = function () {
  var wId =
    typeof _selectedWidgetId !== 'undefined' && _selectedWidgetId ? _selectedWidgetId : null;
  if (!wId || !window.widgets || !window.widgets[wId]) {
    window._bgOriginalColor = null;
    return null;
  }
  var cfg = window.widgets[wId];
  var el = document.getElementById('widget-' + wId);
  var cur = cfg && cfg.bgColor ? cfg.bgColor : el ? el.style.background || '' : '';
  window._bgOriginalColor = cur || '';
  window._bgPreviewColor = cur || '';
  var status = document.getElementById('bg-preview-status');
  var input = document.getElementById('bg-custom-color-input');
  if (status) {
    if (!wId) status.textContent = 'Selecione um widget';
    else if (!cur) status.textContent = 'Original: padrão (transparente)';
    else status.textContent = 'Original: ' + cur;
  }
  if (input) {
    try {
      var hex = cur || '';
      // Converte rgba para hex aproximado para o input color (fallback #0f9d6e)
      if (hex.indexOf('rgba') === 0 || hex.indexOf('rgb') === 0) {
        var m = hex.match(/\d+/g);
        if (m && m.length >= 3) {
          var r = parseInt(m[0]).toString(16).padStart(2, '0');
          var g = parseInt(m[1]).toString(16).padStart(2, '0');
          var b = parseInt(m[2]).toString(16).padStart(2, '0');
          hex = '#' + r + g + b;
        } else hex = '#0f9d6e';
      } else if (!hex || hex === '') hex = '#0f9d6e';
      if (/^#[0-9a-fA-F]{3,6}$/.test(hex))
        input.value =
          hex.length === 4 ? '#' + hex[1] + hex[1] + hex[2] + hex[2] + hex[3] + hex[3] : hex;
    } catch (e) {}
  }
  return window._bgOriginalColor;
};
window.previewWidgetBg = function (color) {
  var wId =
    typeof _selectedWidgetId !== 'undefined' && _selectedWidgetId ? _selectedWidgetId : null;
  if (!wId) {
    var st = document.getElementById('bg-preview-status');
    if (st) st.textContent = 'Selecione um widget primeiro';
    return;
  }
  var el = document.getElementById('widget-' + wId);
  if (color) {
    if (el) {
      el.style.setProperty('background', color, 'important');
      el.style.setProperty('background-image', 'none', 'important');
      try {
        var shP = _widgetShadowForBg(color, false);
        var shHoverP = _widgetShadowForBg(color, true);
        if (shP) {
          el.style.setProperty('--widget-shadow', shP, 'important');
          el.style.setProperty('box-shadow', shP, 'important');
        }
        if (shHoverP) el.style.setProperty('--widget-shadow-hover', shHoverP, 'important');
      } catch (e) {}
    }
    if (window.widgets && window.widgets[wId]) window.widgets[wId].bgColor = color;
    window._bgPreviewColor = color;
  } else {
    if (el) {
      el.style.removeProperty('background');
      el.style.removeProperty('background-image');
      try {
        var defBgP = document.documentElement.classList.contains('dark')
          ? 'rgba(0,0,0,0.95)'
          : 'rgba(255,255,255,0.95)';
        var shDefP = _widgetShadowForBg(defBgP, false);
        var shHoverDefP = _widgetShadowForBg(defBgP, true);
        if (shDefP) {
          el.style.setProperty('--widget-shadow', shDefP, 'important');
          el.style.setProperty('box-shadow', shDefP, 'important');
        }
        if (shHoverDefP) el.style.setProperty('--widget-shadow-hover', shHoverDefP, 'important');
      } catch (e) {}
    }
    if (window.widgets && window.widgets[wId]) delete window.widgets[wId].bgColor;
    window._bgPreviewColor = '';
  }
  var status = document.getElementById('bg-preview-status');
  if (status) {
    if (!color) status.textContent = 'Preview: padrão (segue claro/escuro)';
    else status.textContent = 'Preview: ' + color;
  }
  try {
    if (typeof window.updateWidgetBarSelectionIndicator === 'function')
      window.updateWidgetBarSelectionIndicator();
  } catch (e) {}
};
window.clearWidgetBgTheme = function () {
  var wId =
    typeof _selectedWidgetId !== 'undefined' && _selectedWidgetId ? _selectedWidgetId : null;
  if (!wId) {
    var st = document.getElementById('bg-preview-status');
    if (st) st.textContent = 'Selecione um widget primeiro';
    return;
  }
  var el = document.getElementById('widget-' + wId);
  if (el) {
    el.style.removeProperty('background');
    el.style.removeProperty('background-image');
    try {
      var defBgC = document.documentElement.classList.contains('dark')
        ? 'rgba(0,0,0,0.95)'
        : 'rgba(255,255,255,0.95)';
      var shDefC = _widgetShadowForBg(defBgC, false);
      var shHoverDefC = _widgetShadowForBg(defBgC, true);
      if (shDefC) {
        el.style.setProperty('--widget-shadow', shDefC, 'important');
        el.style.setProperty('box-shadow', shDefC, 'important');
      }
      if (shHoverDefC) el.style.setProperty('--widget-shadow-hover', shHoverDefC, 'important');
    } catch (e) {}
  }
  if (window.widgets && window.widgets[wId]) delete window.widgets[wId].bgColor;
  window._bgPreviewColor = '';
  var status = document.getElementById('bg-preview-status');
  if (status) status.textContent = 'Preview: claro/escuro (segue tema)';
};
window.revertWidgetBg = function () {
  var wId =
    typeof _selectedWidgetId !== 'undefined' && _selectedWidgetId ? _selectedWidgetId : null;
  if (!wId) return;
  var orig =
    typeof window._bgOriginalColor !== 'undefined' && window._bgOriginalColor !== null
      ? window._bgOriginalColor
      : '';
  var el = document.getElementById('widget-' + wId);
  if (orig) {
    if (el) {
      el.style.setProperty('background', orig, 'important');
      el.style.setProperty('background-image', 'none', 'important');
      try {
        var shR = _widgetShadowForBg(orig, false);
        var shHoverR = _widgetShadowForBg(orig, true);
        if (shR) {
          el.style.setProperty('--widget-shadow', shR, 'important');
          el.style.setProperty('box-shadow', shR, 'important');
        }
        if (shHoverR) el.style.setProperty('--widget-shadow-hover', shHoverR, 'important');
      } catch (e) {}
    }
    if (window.widgets && window.widgets[wId]) window.widgets[wId].bgColor = orig;
  } else {
    if (el) {
      el.style.removeProperty('background');
      el.style.removeProperty('background-image');
      try {
        var defBgR = document.documentElement.classList.contains('dark')
          ? 'rgba(0,0,0,0.95)'
          : 'rgba(255,255,255,0.95)';
        var shDefR = _widgetShadowForBg(defBgR, false);
        var shHoverDefR = _widgetShadowForBg(defBgR, true);
        if (shDefR) {
          el.style.setProperty('--widget-shadow', shDefR, 'important');
          el.style.setProperty('box-shadow', shDefR, 'important');
        }
        if (shHoverDefR) el.style.setProperty('--widget-shadow-hover', shHoverDefR, 'important');
      } catch (e) {}
    }
    if (window.widgets && window.widgets[wId]) delete window.widgets[wId].bgColor;
  }
  window._bgPreviewColor = orig;
  var status = document.getElementById('bg-preview-status');
  if (status) status.textContent = orig ? 'Revertido: ' + orig : 'Revertido: padrão (claro/escuro)';
};
window.saveWidgetBg = function () {
  var wId =
    typeof _selectedWidgetId !== 'undefined' && _selectedWidgetId ? _selectedWidgetId : null;
  if (!wId || !window.widgets || !window.widgets[wId]) {
    var st2 = document.getElementById('bg-preview-status');
    if (st2) st2.textContent = 'Selecione um widget';
    return;
  }
  // O preview já está em widgets[wId].bgColor e el.style.background — agora persiste
  if (typeof window.saveWidgetsLayoutImmediate === 'function') window.saveWidgetsLayoutImmediate();
  else if (typeof saveWidgetsLayout === 'function') saveWidgetsLayout();
  try {
    if (typeof saveCurrentPreset === 'function') saveCurrentPreset();
  } catch (e) {}
  window._bgOriginalColor = window._bgPreviewColor;
  var status = document.getElementById('bg-preview-status');
  if (status)
    status.textContent = window._bgPreviewColor
      ? 'Salvo: ' + window._bgPreviewColor
      : 'Salvo: padrão';
  // Fecha dropdown
  var dd = document.getElementById('bg-color-dropdown');
  if (dd) {
    dd.classList.remove('open');
    dd.classList.add('hidden');
  }
  document.body.classList.remove('bg-dropdown-open');
  var bgDd = document.getElementById('bg-color-dropdown');
  if (bgDd) {
    bgDd.style.removeProperty('position');
    bgDd.style.removeProperty('top');
    bgDd.style.removeProperty('left');
    bgDd.style.removeProperty('bottom');
    bgDd.style.removeProperty('right');
    bgDd.style.removeProperty('transform');
    bgDd.style.removeProperty('margin');
    bgDd.style.removeProperty('z-index');
    if (bgDd._originalParent) {
      try {
        if (bgDd._originalNext && bgDd._originalNext.parentElement === bgDd._originalParent) {
          bgDd._originalParent.insertBefore(bgDd, bgDd._originalNext);
        } else {
          bgDd._originalParent.appendChild(bgDd);
        }
      } catch (err) {}
      bgDd._originalParent = null;
      bgDd._originalNext = null;
    }
  }
};
window.setWidgetBg = function (color) {
  // Compat: agora salva direto (usado em outros lugares), mas o menu usa preview+save
  if (!_selectedWidgetId || !widgets[_selectedWidgetId]) return;
  widgets[_selectedWidgetId].bgColor = color || undefined;
  var el = document.getElementById('widget-' + _selectedWidgetId);
  if (el) el.style.background = color || '';
  if (!color) delete widgets[_selectedWidgetId].bgColor;
  window._bgOriginalColor = color || '';
  window._bgPreviewColor = color || '';
  if (typeof window.saveWidgetsLayoutImmediate === 'function') window.saveWidgetsLayoutImmediate();
  else saveWidgetsLayout();
  try {
    if (typeof saveCurrentPreset === 'function') saveCurrentPreset();
  } catch (e) {}
  document.querySelectorAll('.edit-dropdown').forEach(function (d) {
    d.classList.remove('open');
    d.classList.add('hidden');
  });
  document.body.classList.remove('bg-dropdown-open');
};

// ══════════════════════════════════════════════════════════════
// TAMANHO DO TEXTO DOS WIDGETS — auto-escala + fixo por widget
// Auto: texto escala com o tamanho do widget (gridW/gridH → --wfs).
// Fixo: fontSizePx no config do widget (16 = tamanho atual).
// ══════════════════════════════════════════════════════════════
function widgetTextAutoScale(cfg) {
  var w = (cfg && +cfg.gridW) || 6,
    h = (cfg && +cfg.gridH) || 6;
  var s = Math.min(w, h) / 6;
  if (s < 0.7) s = 0.7;
  if (s > 1.8) s = 1.8;
  return Math.round(s * 100) / 100;
}
function _isChartWidgetId(id) {
  return id.indexOf('chart-') === 0 || id.indexOf('_grafico') >= 0;
}
function widgetTextScaleFor(id) {
  var cfg = (window.widgets || {})[id];
  if (!cfg) return null;
  if (cfg.fontSizePx) return { scale: cfg.fontSizePx / 16, fixed: true };
  if (_isChartWidgetId(id)) return null; // gráficos: canvas se ajusta sozinho
  var el = document.getElementById('widget-' + id);
  if (el && el.querySelector && el.querySelector('canvas')) return null; // canvas já presente
  return { scale: widgetTextAutoScale(cfg), fixed: false };
}
function applyWidgetTextScaling() {
  if (!window.widgets) return;
  var blocks = document.querySelectorAll('.matrix-container .bento-block');
  blocks.forEach(function (el) {
    var id = (el.id || '').replace('widget-', '');
    if (!id) return;
    var r = widgetTextScaleFor(id);
    if (!r) {
      el.style.removeProperty('--wfs');
      el.removeAttribute('data-font-fixed');
      return;
    }
    el.style.setProperty('--wfs', r.scale);
    if (r.fixed) el.setAttribute('data-font-fixed', '1');
    else el.removeAttribute('data-font-fixed');
  });
}
// Reaplica após cada render (resize, drag, preset, sync) sem tocar no render original
function _wrapRenderTextScale() {
  if (
    typeof window.renderWidgetsOnMatrix !== 'function' ||
    window.renderWidgetsOnMatrix._textScaleWrapped
  )
    return false;
  var _origRenderTS = window.renderWidgetsOnMatrix;
  window.renderWidgetsOnMatrix = function () {
    var r = _origRenderTS.apply(this, arguments);
    try {
      applyWidgetTextScaling();
    } catch (e) {}
    return r;
  };
  window.renderWidgetsOnMatrix._textScaleWrapped = true;
  return true;
}
if (!_wrapRenderTextScale()) {
  document.addEventListener('DOMContentLoaded', function () {
    if (_wrapRenderTextScale()) {
      try {
        applyWidgetTextScaling();
      } catch (e) {}
    }
    try {
      _watchWidgetCanvas();
    } catch (e) {}
  });
} else {
  try {
    applyWidgetTextScaling();
  } catch (e) {}
}
// Gráficos (canvas) criados DEPOIS do render: remove a auto-escala do bloco
// (exceto tamanho fixo — escolha explícita do usuário). Cobre cultura-/_mercado_.
var _canvasWatchInstalled = false;
function _widgetHasFixedFont(id) {
  var cfg = (window.widgets || {})[id];
  return !!(cfg && cfg.fontSizePx);
}
function _watchWidgetCanvas() {
  if (_canvasWatchInstalled) return;
  var cont = document.querySelector('.matrix-container');
  if (!cont || typeof MutationObserver === 'undefined') return;
  _canvasWatchInstalled = true;
  new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      m.addedNodes.forEach(function (n) {
        if (!n || !n.querySelectorAll) return;
        var canvases = n.nodeName === 'CANVAS' ? [n] : n.querySelectorAll('canvas');
        if (!canvases.length) return;
        var block = n.closest ? n.closest('.bento-block') : null;
        if (!block && n.nodeName === 'CANVAS' && n.parentElement)
          block = n.parentElement.closest ? n.parentElement.closest('.bento-block') : null;
        if (!block || !block.id) return;
        var id = block.id.replace('widget-', '');
        if (_isChartWidgetId(id) || _widgetHasFixedFont(id)) return;
        block.style.removeProperty('--wfs');
        block.removeAttribute('data-font-fixed');
      });
    });
  }).observe(cont, { childList: true, subtree: true });
}
try {
  _watchWidgetCanvas();
} catch (e) {}
document.addEventListener('DOMContentLoaded', function () {
  try {
    _watchWidgetCanvas();
  } catch (e) {}
});
function _fontSelectedId() {
  var wId =
    typeof window._selectedWidgetId !== 'undefined' && window._selectedWidgetId
      ? window._selectedWidgetId
      : null;
  if (!wId && typeof _selectedWidgetId !== 'undefined') {
    try {
      wId = _selectedWidgetId || null;
    } catch (e) {}
  }
  return wId;
}
function _syncFontInputs(px) {
  var num = document.getElementById('font-size-input');
  var rng = document.getElementById('font-size-range');
  var pct = document.getElementById('font-size-pct');
  var v = Math.max(8, Math.min(64, parseInt(px, 10) || 16));
  if (num && document.activeElement !== num) num.value = v;
  if (rng && document.activeElement !== rng) rng.value = v;
  if (pct) pct.textContent = Math.round((v / 16) * 100) + '%';
}
window._captureFontOriginal = function () {
  var wId = _fontSelectedId();
  // #region agent log
  if (window.__dbgNav) {
    var _el = wId ? document.getElementById('widget-' + wId) : null;
    var _cfg = wId && window.widgets ? window.widgets[wId] : null;
    window.__dbgNav('D', 'pagina-index.js:_captureFontOriginal', 'font capture', {
      wId: wId,
      storedPx: _cfg ? _cfg.fontSizePx || null : null,
      grid: _cfg ? { w: _cfg.gridW, h: _cfg.gridH } : null,
      autoScale: _cfg ? widgetTextAutoScale(_cfg) : null,
      cssWfs: _el ? _el.style.getPropertyValue('--wfs') : null,
      zoom: _el
        ? (function () {
            var c = _el.querySelector('.widget-content');
            return c ? getComputedStyle(c).zoom : null;
          })()
        : null,
      inputVal: (document.getElementById('font-size-input') || {}).value || null,
    });
  }
  // #endregion
  var status = document.getElementById('font-size-status');
  if (!wId || !window.widgets || !window.widgets[wId]) {
    window._fontOriginalPx = null;
    if (status) status.textContent = 'Selecione um widget';
    _syncFontInputs(16);
    return null;
  }
  var cur = window.widgets[wId].fontSizePx || null;
  window._fontOriginalPx = cur;
  _syncFontInputs(cur || 16);
  if (status)
    status.textContent = cur
      ? 'Original: ' + cur + 'px (fixo)'
      : 'Original: automático (escala pelo tamanho)';
  return window._fontOriginalPx;
};
window.syncWidgetFontField = function () {
  try {
    if (typeof window._captureFontOriginal === 'function') window._captureFontOriginal();
  } catch (e) {}
};
window.previewWidgetFontSize = function (px) {
  var wId = _fontSelectedId();
  var status = document.getElementById('font-size-status');
  if (!wId || !window.widgets || !window.widgets[wId]) {
    if (status) status.textContent = 'Selecione um widget primeiro';
    return;
  }
  var v = Math.max(8, Math.min(64, parseInt(px, 10) || 16));
  _syncFontInputs(v);
  var scale = Math.round((v / 16) * 100) / 100;
  var el = document.getElementById('widget-' + wId);
  if (el) {
    el.style.setProperty('--wfs', scale);
    el.setAttribute('data-font-fixed', '1');
  }
  window.widgets[wId].fontSizePx = v;
  if (status) status.textContent = 'Preview: ' + v + 'px (≈' + Math.round(scale * 100) + '%)';
};
window.revertWidgetFontSize = function () {
  var wId = _fontSelectedId();
  if (!wId) return;
  var orig =
    typeof window._fontOriginalPx !== 'undefined' && window._fontOriginalPx
      ? window._fontOriginalPx
      : null;
  if (orig) {
    window.previewWidgetFontSize(orig);
    var status = document.getElementById('font-size-status');
    if (status) status.textContent = 'Revertido: ' + orig + 'px';
  } else {
    window.clearWidgetFontSize();
    var status2 = document.getElementById('font-size-status');
    if (status2) status2.textContent = 'Revertido: automático';
  }
};
window.clearWidgetFontSize = function () {
  var wId = _fontSelectedId();
  var status = document.getElementById('font-size-status');
  if (!wId || !window.widgets || !window.widgets[wId]) {
    if (status) status.textContent = 'Selecione um widget primeiro';
    return;
  }
  delete window.widgets[wId].fontSizePx;
  window._fontOriginalPx = null;
  var el = document.getElementById('widget-' + wId);
  var s = widgetTextAutoScale(window.widgets[wId]);
  if (el) {
    if (_isChartWidgetId(wId) || (el.querySelector && el.querySelector('canvas'))) {
      el.style.removeProperty('--wfs');
    } else el.style.setProperty('--wfs', s);
    el.removeAttribute('data-font-fixed');
  }
  _syncFontInputs(16);
  if (status) status.textContent = 'Preview: automático (≈' + Math.round(s * 100) + '%)';
};
window.saveWidgetFontSize = function () {
  var wId = _fontSelectedId();
  var status = document.getElementById('font-size-status');
  if (!wId || !window.widgets || !window.widgets[wId]) {
    if (status) status.textContent = 'Selecione um widget';
    return;
  }
  // O preview já está em widgets[wId].fontSizePx — agora persiste
  if (typeof window.saveWidgetsLayoutImmediate === 'function') window.saveWidgetsLayoutImmediate();
  else if (typeof saveWidgetsLayout === 'function') saveWidgetsLayout();
  try {
    if (typeof saveCurrentPreset === 'function') saveCurrentPreset();
  } catch (e) {}
  window._fontOriginalPx = window.widgets[wId].fontSizePx || null;
  if (status)
    status.textContent = window._fontOriginalPx
      ? 'Salvo: ' + window._fontOriginalPx + 'px'
      : 'Salvo: automático';
  var dd = document.getElementById('font-size-dropdown');
  if (dd) {
    dd.classList.remove('open');
    dd.classList.add('hidden');
  }
  document.body.classList.remove('bg-dropdown-open');
};

window.setChartType = function (type) {
  if (!_selectedWidgetId) return;
  var el = document.getElementById('widget-' + _selectedWidgetId);
  if (!el) return;
  var canvas = el.querySelector('canvas');
  if (canvas && chartInstances[canvas.id]) {
    chartInstances[canvas.id].destroy();
    delete chartInstances[canvas.id];
  }
  if (canvas) {
    var scPal = chartPalette();
    var scData = getChartDataForPeriod(currentPeriod);
    if (scPal.isDark && scData.datasets)
      scData.datasets = scData.datasets.map(function (ds) {
        return darkenDatasetColors(ds);
      });
    var newChart = new Chart(canvas, {
      type: type,
      data: scData,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false, axis: 'x' },
        plugins: {
          legend: {
            display: type !== 'line',
            position: 'bottom',
            labels: {
              boxWidth: 20,
              padding: 10,
              font: { size: 11 },
              usePointStyle: true,
              pointStyle: 'line',
              color: scPal.tick,
            },
          },
          tooltip: { enabled: false },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: { color: scPal.tick, font: { size: 9 }, padding: 4 },
          },
          y: {
            grid: { display: false },
            border: { display: false },
            ticks: { color: scPal.tick, font: { size: 9 }, padding: 4 },
          },
        },
        layout: { padding: { top: 24, bottom: 4, left: 2, right: 2 } },
      },
    });
    chartInstances[canvas.id] = newChart;
    watchChartResize(canvas);
    canvas.classList.add('reveal-chart');
  }
  if (!widgets[_selectedWidgetId].chartType) widgets[_selectedWidgetId].chartType = {};
  widgets[_selectedWidgetId].chartType = type;
  saveWidgetsLayout();
  document.querySelectorAll('.edit-dropdown').forEach(function (d) {
    d.classList.remove('open');
    d.classList.add('hidden');
  });
};

window.updateValuesList = function (wId) {
  var list = document.getElementById('values-list');
  if (!list || !wId || !widgets[wId]) {
    if (list)
      list.innerHTML =
        '<div class="text-slate-400 italic text-xs">Selecione um widget para ver seus valores</div>';
    return;
  }
  var cfg = widgets[wId];
  var d = dashboardData;
  var vars = [];
  if (wId.indexOf('roi') >= 0) vars = ['ROI: ' + (d && d.roi != null ? d.roi + '%' : '--')];
  else if (wId.indexOf('custo') >= 0)
    vars = [
      'Custo/Ha: R$ ' +
        (d && d.custo_ha != null ? Number(d.custo_ha).toLocaleString('pt-BR') : '--'),
    ];
  else if (wId.indexOf('chart') >= 0) vars = ['Período: Atual'];
  else vars = ['Valor: --'];

  list.innerHTML = vars
    .map(function (v) {
      return (
        '<div class="flex items-center justify-between py-1 px-2 rounded bg-slate-50 dark:bg-slate-800 text-xs"><span>' +
        v +
        '</span><button onclick="removeSystemVar(\'' +
        v +
        '\')" class="text-rose-400 hover:text-rose-600"><i class="bi bi-x"></i></button></div>'
      );
    })
    .join('');
};

window.addSystemVar = function (varName) {
  if (!_selectedWidgetId) return;
  // Store the var reference in widget config
  if (!widgets[_selectedWidgetId].systemVars) widgets[_selectedWidgetId].systemVars = [];
  widgets[_selectedWidgetId].systemVars.push(varName);
  saveWidgetsLayout();
  updateValuesList(_selectedWidgetId);
};

window.removeSystemVar = function (varName) {
  if (!_selectedWidgetId || !widgets[_selectedWidgetId].systemVars) return;
  var idx = widgets[_selectedWidgetId].systemVars.indexOf(varName);
  if (idx >= 0) widgets[_selectedWidgetId].systemVars.splice(idx, 1);
  saveWidgetsLayout();
  updateValuesList(_selectedWidgetId);
};

window.deleteSelectedWidget = function () {
  if (!_selectedWidgetId || !widgets[_selectedWidgetId]) return;
  var wId = _selectedWidgetId;
  var cfg = widgets[wId];
  var label = cfg && cfg.title ? cfg.title : wId;
  showCenterConfirmDialog({
    title: 'Excluir widget',
    message: 'Tem certeza que deseja excluir "' + label + '" do dashboard?',
    confirmLabel: 'Excluir',
    danger: true,
    onConfirm: function () {
      removeWidget(wId, true);
    },
  });
};

window.exportChartToXLSX = function () {
  if (!_selectedWidgetId) return;
  var csv = 'Período,Valor\n';
  var chartData = getChartDataForPeriod(currentPeriod);
  for (var i = 0; i < chartData.labels.length; i++) {
    csv += chartData.labels[i] + ',' + chartData.datasets[0].data[i] + '\n';
  }
  var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  var url = URL.createObjectURL(blob);
  var link = document.createElement('a');
  link.href = url;
  link.download = 'gráfico-' + _selectedWidgetId + '-' + Date.now() + '.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  document.querySelectorAll('.edit-dropdown').forEach(function (d) {
    d.classList.remove('open');
    d.classList.add('hidden');
  });
};

// Export table data to CSV
window.exportTableCSV = function (type) {
  var w = widgetDataCache || {};
  var data = [];
  if (type === 'safras' && w.safras && w.safras.items) data = w.safras.items;
  else if (type === 'financeiro' && w.financeiro && w.financeiro.lancamentos)
    data = w.financeiro.lancamentos;
  else if (type === 'financeiro_mensal' && w.financeiro && w.financeiro.mensal)
    data = w.financeiro.mensal;
  else if (type === 'estoque' && w.estoque && w.estoque.items) data = w.estoque.items;

  if (!data.length) return alert('Nenhum dado para exportar');

  var headers = Object.keys(data[0]);
  var csv =
    headers.join(',') +
    '\n' +
    data
      .map(function (r) {
        return headers
          .map(function (h) {
            return JSON.stringify(r[h] || '');
          })
          .join(',');
      })
      .join('\n');
  var blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = type + '.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
};

// Export table data to Excel (.xls que o Excel abre direto)
window.exportTableExcel = function (type) {
  var w = widgetDataCache || {};
  var data = [];
  if (type === 'safras' && w.safras && w.safras.items) data = w.safras.items;
  else if (type === 'financeiro' && w.financeiro && w.financeiro.lancamentos)
    data = w.financeiro.lancamentos;
  else if (type === 'financeiro_mensal' && w.financeiro && w.financeiro.mensal)
    data = w.financeiro.mensal;
  else if (type === 'estoque' && w.estoque && w.estoque.items) data = w.estoque.items;

  if (!data.length) return alert('Nenhum dado para exportar');

  var headers = Object.keys(data[0]);
  var esc = function (v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  };
  var html =
    '<table><thead><tr>' +
    headers
      .map(function (h) {
        return '<th>' + esc(h) + '</th>';
      })
      .join('') +
    '</tr></thead><tbody>' +
    data
      .map(function (r) {
        return (
          '<tr>' +
          headers
            .map(function (h) {
              return '<td>' + esc(r[h]) + '</td>';
            })
            .join('') +
          '</tr>'
        );
      })
      .join('') +
    '</tbody></table>';
  var blob = new Blob(['\ufeff' + html], { type: 'application/vnd.ms-excel;charset=utf-8;' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = type + '.xls';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
};

// Recalcular altura da matriz ao redimensionar janela
var _resizeTimer;
window.addEventListener('resize', function () {
  try {
    dashboardLog('window:resize', { w: window.innerWidth, h: window.innerHeight });
  } catch (e) {}
  clearTimeout(_resizeTimer);
  _resizeTimer = setTimeout(function () {
    try {
      dashboardLog('resize:adjustMatrixHeight:start', { GRID_ROWS: GRID_ROWS });
    } catch (e) {}
    adjustMatrixHeight();
    // Re-posicionar widgets existentes se necessario
    Object.keys(widgets).forEach(function (id) {
      if (!widgets[id].visible) return;
      var w = widgets[id];
      if (w.gridY + w.gridH > GRID_ROWS) {
        w.gridY = Math.max(0, GRID_ROWS - w.gridH);
      }
      if (w.gridX + w.gridW > GRID_COLS) {
        w.gridX = Math.max(0, GRID_COLS - w.gridW);
      }
    });
    renderWidgetsOnMatrix();
  }, 250);
});

// ============================================
// WIDGET INTELLIGENCE - Enhanced Add Widget Modal
// ============================================

// Populate Recent Widgets tab
function populateRecentWidgets() {
  var container = document.getElementById('recent-widgets-grid');
  if (!container || !window.WidgetIntelligence) return;

  var recents = window.WidgetIntelligence.getRecents ? window.WidgetIntelligence.getRecents() : [];
  if (!recents.length) {
    container.innerHTML =
      '<div class="text-center py-4 text-slate-400 text-xs">Nenhum widget recente</div>';
    return;
  }

  container.innerHTML = recents
    .slice(0, 10)
    .map(function (r) {
      var type = window.WIDGET_TYPES ? window.WIDGET_TYPES[r.id] : null;
      return (
        '<button class="widget-card" onclick="addWidgetFromIntelligence(\'' +
        r.id +
        '\')">' +
        '<div class="widget-card-icon bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">' +
        '<i class="bi ' +
        (type?.icon || 'bi-puzzle') +
        ' text-[13px]"></i></div>' +
        '<span class="widget-card-label">' +
        (type?.title || r.id) +
        '</span>' +
        '<span class="text-[8px] text-slate-400 ml-auto">' +
        formatTimeAgo(r.timestamp) +
        '</span>' +
        '</button>'
      );
    })
    .join('');
}

// Populate Favorite Widgets tab
function populateFavoriteWidgets() {
  var container = document.getElementById('favorite-widgets-grid');
  if (!container || !window.WidgetIntelligence) return;

  var favorites = window.WidgetIntelligence.getFavorites
    ? window.WidgetIntelligence.getFavorites()
    : [];
  if (!favorites.length) {
    container.innerHTML =
      '<div class="text-center py-4 text-slate-400 text-xs">Nenhum favorito - clique na estrela para adicionar</div>';
    return;
  }

  container.innerHTML = favorites
    .slice(0, 12)
    .map(function (id) {
      var type = window.WIDGET_TYPES ? window.WIDGET_TYPES[id] : null;
      return (
        '<button class="widget-card" onclick="addWidgetFromIntelligence(\'' +
        id +
        '\')">' +
        '<div class="widget-card-icon bg-amber-100 dark:bg-amber-500/15 text-amber-600 dark:text-amber-400">' +
        '<i class="bi ' +
        (type?.icon || 'bi-puzzle') +
        ' text-[13px]"></i></div>' +
        '<span class="widget-card-label">' +
        (type?.title || id) +
        '</span>' +
        '<i class="bi bi-star-fill text-amber-500 ml-auto text-[10px]"></i>' +
        '</button>'
      );
    })
    .join('');
}

// Populate AI Suggested Widgets tab
function populateSuggestedWidgets() {
  var container = document.getElementById('suggested-widgets-grid');
  if (!container || !window.WidgetIntelligence) return;

  var suggestions = window.WidgetIntelligence.getSuggestions
    ? window.WidgetIntelligence.getSuggestions({ limit: 12 })
    : [];
  if (!suggestions.length) {
    container.innerHTML =
      '<div class="text-center py-4 text-slate-400 text-xs">Nenhuma sugestão no momento</div>';
    return;
  }

  container.innerHTML = suggestions
    .map(function (id) {
      var type = window.WIDGET_TYPES ? window.WIDGET_TYPES[id] : null;
      return (
        '<button class="widget-card" onclick="addWidgetFromIntelligence(\'' +
        id +
        '\')">' +
        '<div class="widget-card-icon bg-purple-100 dark:bg-purple-500/15 text-purple-600 dark:text-purple-400">' +
        '<i class="bi ' +
        (type?.icon || 'bi-puzzle') +
        ' text-[13px]"></i></div>' +
        '<span class="widget-card-label">' +
        (type?.title || id) +
        '</span>' +
        '<span class="badge bg-purple-100 text-purple-700 text-[9px] ml-auto px-1.5 py-0.5 rounded">IA</span>' +
        '</button>'
      );
    })
    .join('');
}

// Add widget from intelligence tabs
function addWidgetFromIntelligence(widgetId) {
  if (window.addWidget) {
    window.addWidget(widgetId);
  }
  if (window.WidgetIntelligence) {
    window.WidgetIntelligence.addRecent?.(widgetId, { source: 'intelligence-modal' });
    window.WidgetIntelligence.trackUsage?.(widgetId, 'add-from-intelligence');
  }
  updateWidgetModalCounter();
}

// Format time ago
function formatTimeAgo(ts) {
  var diff = Date.now() - ts;
  var mins = Math.floor(diff / 6e4);
  var hours = Math.floor(diff / 36e5);
  var days = Math.floor(diff / 864e5);
  if (mins < 1) return 'agora';
  if (mins < 60) return mins + 'min';
  if (hours < 24) return hours + 'h';
  return days + 'd';
}

// Update widget modal counter
function updateWidgetModalCounter() {
  var counter = document.getElementById('widget-modal-counter');
  if (counter && window.widgets) {
    var count = Object.values(window.widgets).filter(function (w) {
      return w.visible;
    }).length;
    counter.textContent = count + ' widgets no dashboard';
  }
}

// Override switchWidgetTab to populate intelligence tabs
var originalSwitchWidgetTab = window.switchWidgetTab;
window.switchWidgetTab = function (tab) {
  if (originalSwitchWidgetTab) originalSwitchWidgetTab(tab);

  // Populate intelligence tabs when selected
  setTimeout(function () {
    if (tab === 'recent') populateRecentWidgets();
    else if (tab === 'favorite') populateFavoriteWidgets();
    else if (tab === 'suggested') populateSuggestedWidgets();
  }, 50);
};

// Initialize intelligence tabs when modal opens
var originalOpenAddWidgetModal = window.openAddWidgetModal;
window.openAddWidgetModal = function () {
  if (originalOpenAddWidgetModal) originalOpenAddWidgetModal();
  updateWidgetModalCounter();
  // Populate default tab (kpi)
  if (window.WidgetIntelligence && window.WidgetIntelligence.ready) {
    window.WidgetIntelligence.ready(function () {
      populateRecentWidgets();
      populateFavoriteWidgets();
      populateSuggestedWidgets();
    });
  }
};

// Keyboard navigation for intelligence tabs
document.addEventListener('keydown', function (e) {
  var modal = document.getElementById('add-widget-modal');
  if (!modal || modal.classList.contains('hidden')) return;

  var activeTab = document.querySelector('.widget-modal-tab.active-tab');
  if (!activeTab) return;

  var tabs = Array.from(document.querySelectorAll('.widget-modal-tab'));
  var currentIndex = tabs.indexOf(activeTab);

  if (e.key === 'ArrowRight' && currentIndex < tabs.length - 1) {
    e.preventDefault();
    tabs[currentIndex + 1].click();
  } else if (e.key === 'ArrowLeft' && currentIndex > 0) {
    e.preventDefault();
    tabs[currentIndex - 1].click();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    var selectedCard = document.querySelector('.widget-card.selected, .widget-card:hover');
    if (selectedCard && selectedCard.onclick) {
      selectedCard.click();
    }
  }
});
