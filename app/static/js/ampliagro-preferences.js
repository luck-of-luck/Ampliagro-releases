/* ==========================================================================
   AMPLIAGRO PREFERENCES — Gerenciador Centralizado
   ─────────────────────────────────────────────────────────────────────────
   Separa claro/escuro/custom e cores de gráficos por preset.
   Toda adição/remoção passa por aqui, garantindo que não deixe
   dados fantasma ou rastros (limpeza completa).
   Baseado no dashboard, usado por TODA página via API SPA.
   ========================================================================== */
window.AmpliagroPrefs = (function() {
  const BASE_KEY = 'ampliagro-preferences';
  function scopedKey() {
    const uid = window.AMPLIAGRO_USER_ID;
    return uid != null ? BASE_KEY + '_u' + uid : BASE_KEY;
  }
  function plainKey() { return BASE_KEY; }

  function load() {
    try {
      const s = localStorage.getItem(scopedKey());
      if (s) return JSON.parse(s);
      const p = localStorage.getItem(plainKey());
      if (p) return JSON.parse(p);
    } catch(e) {}
    return { version: 1, theme: { mode: 'claro' }, presets: {}, charts: {} };
  }
  function save(prefs) {
    const json = JSON.stringify(prefs);
    try { localStorage.setItem(scopedKey(), json); } catch(e) {}
    try { localStorage.setItem(plainKey(), json); } catch(e) {}
    // espelhos legados
    try { localStorage.setItem('ampliagro_tema', prefs.theme?.mode || 'claro'); } catch(e) {}
    try { localStorage.setItem('theme', prefs.theme?.mode || 'claro'); } catch(e) {}
    // notifica API SPA
    try { window.dispatchEvent(new CustomEvent('prefs:changed', { detail: prefs })); } catch(e) {}
  }

  /* --- TEMA: claro / escuro / custom separados --- */
  function setThemeMode(mode) {
    mode = window.normalizarModoTema ? window.normalizarModoTema(mode) : mode;
    if (!['claro','escuro','custom'].includes(mode)) mode = 'claro';
    const prefs = load();
    prefs.theme = prefs.theme || {};
    // limpa rastro do modo anterior
    if (mode !== 'custom' && prefs.theme.custom) {
      // mantém custom salvo mas não ativo (não apaga, só desativa)
      // se quiser apagar rastros, descomente: delete prefs.theme.custom;
    }
    prefs.theme.mode = mode;
    save(prefs);
    // aplica
    if (mode === 'custom' && typeof window.applyCustomTheme === 'function') {
      window.applyCustomTheme(prefs.theme.custom || {}, false);
    } else if (typeof window.aplicarTema === 'function') {
      window.aplicarTema(mode, false);
    }
    return prefs;
  }

  function setCustomTheme(customData) {
    const prefs = load();
    prefs.theme = prefs.theme || {};
    prefs.theme.mode = 'custom';
    prefs.theme.custom = customData || {};
    save(prefs);
    if (typeof window.applyCustomTheme === 'function') window.applyCustomTheme(customData, false);
    return prefs;
  }

  function clearCustomTheme() {
    const prefs = load();
    if (prefs.theme) {
      delete prefs.theme.custom;
      if (prefs.theme.mode === 'custom') prefs.theme.mode = 'claro';
    }
    save(prefs);
    // limpa CSS vars custom
    const html = document.documentElement;
    Array.from(html.style).forEach(prop => {
      if (prop.startsWith('--cor-') || prop.startsWith('--theme-')) html.style.removeProperty(prop);
    });
    html.classList.remove('custom-theme');
    html.removeAttribute('data-tema-custom');
    if (typeof window.aplicarTema === 'function') window.aplicarTema('claro', false);
    return prefs;
  }

  /* --- PRESETS e CORES DE GRÁFICOS — por preset, sem fantasma --- */
  function setPreset(presetKey, data) {
    const prefs = load();
    prefs.presets = prefs.presets || {};
    prefs.presets[presetKey] = data;
    save(prefs);
    return prefs;
  }
  function removePreset(presetKey) {
    const prefs = load();
    let changed = false;
    if (prefs.presets && prefs.presets[presetKey]) {
      delete prefs.presets[presetKey];
      changed = true;
    }
    // limpa cores de gráficos desse preset
    if (prefs.charts && prefs.charts[presetKey]) {
      delete prefs.charts[presetKey];
      changed = true;
    }
    // limpa ordem se tiver
    if (prefs.presetsOrder) {
      const idx = prefs.presetsOrder.indexOf(presetKey);
      if (idx >= 0) { prefs.presetsOrder.splice(idx, 1); changed = true; }
    }
    // limpa widgets do preset no storage
    try {
      const k1 = 'matrix-preset-json-' + presetKey;
      const k2 = 'matrix-widgets-preset-' + presetKey;
      localStorage.removeItem(k1);
      localStorage.removeItem(k2);
      // scoped também
      const uid = window.AMPLIAGRO_USER_ID;
      if (uid != null) {
        localStorage.removeItem(k1 + '_u' + uid);
        localStorage.removeItem(k2 + '_u' + uid);
      }
    } catch(e) {}
    if (changed) save(prefs);
    return prefs;
  }

  function setChartColors(presetKey, colors) {
    const prefs = load();
    prefs.charts = prefs.charts || {};
    // colors = { datasets: { borderColor, backgroundColor }, palette: [...] }
    prefs.charts[presetKey] = colors;
    save(prefs);
    return prefs;
  }
  function removeChartColors(presetKey) {
    const prefs = load();
    if (prefs.charts && prefs.charts[presetKey]) {
      delete prefs.charts[presetKey];
      save(prefs);
    }
    return prefs;
  }
  function clearAllChartColors() {
    const prefs = load();
    if (prefs.charts) {
      prefs.charts = {};
      save(prefs);
    }
    // limpa todos os storages de chart
    try {
      Object.keys(localStorage).forEach(k => {
        if (k.includes('chart') || k.includes('preset')) {
          // só limpa se for chart color, não apaga presets
          if (k.includes('chart')) localStorage.removeItem(k);
        }
      });
    } catch(e) {}
    return prefs;
  }

  // As chaves que um preset DETEM. A lista e' fechada e cada entrada e' o
  // nome INTEIRO da chave, nunca um pedaco.
  //
  // Antes, a purga media por `k.includes(presetKey)`. A limpeza v13 do
  // dashboard tratava cada chave de `prefs.presets` como um nome de preset e
  // chamava purgePreset com 'order' e 'active' — e 'order' esta em
  // `matrix-preset-order` e 'active' esta em `matrix-active-preset`. Purgar
  // UM preset apagava, uma vez por visita, o preset ACTIVO e a ORDEM dos
  // presets. Era o motivo de o painel abrir noutro preset ao reentrar.
  function chavesDoPreset(presetKey) {
    const uid = window.AMPLIAGRO_USER_ID;
    const base = [
      'matrix-preset-json-' + presetKey,
      'matrix-widgets-preset-' + presetKey,
      'matrix-preset-' + presetKey,
    ];
    if (uid == null) return base;
    return base.concat(base.map((k) => k + '_u' + uid));
  }

  // Limpeza total de rastros de um preset (chamado ao deletar)
  function purgePreset(presetKey) {
    removePreset(presetKey);
    removeChartColors(presetKey);
    try {
      chavesDoPreset(presetKey).forEach((k) => {
        try { localStorage.removeItem(k); } catch (e) {}
      });
    } catch (e) {}
    return load();
  }

  // API pública
  var api = {
    load, save,
    setThemeMode, setCustomTheme, clearCustomTheme,
    setPreset, removePreset,
    setChartColors, removeChartColors, clearAllChartColors,
    purgePreset
  };

  /* Globais canônicas — o dashboard (index.html) já define as dele e
     sobrescreve estas; aqui garantimos que TODAS as páginas tenham
     get/savePreferences (antes só existia no dashboard e os presets
     viravam mistura fora dele). */
  if (typeof window.getPreferences !== 'function') {
    window.getPreferences = function () {
      var prefs = load();
      prefs.theme = prefs.theme || {};
      if (window.normalizarModoTema) {
        prefs.theme.mode = window.normalizarModoTema(prefs.theme.mode) || 'claro';
      } else if (!prefs.theme.mode) {
        prefs.theme.mode = 'claro';
      }
      prefs.theme.custom = prefs.theme.custom || { dark: true, source: 'ui' };
      return prefs;
    };
  }
  if (typeof window.savePreferences !== 'function') {
    window.savePreferences = function (next) {
      var prefs = load();
      next = next || {};
      var merged = Object.assign({}, prefs, next, {
        theme: Object.assign({}, prefs.theme, next.theme || {}),
      });
      if (merged.theme && merged.theme.mode === 'custom' && !merged.theme.custom) {
        merged.theme.custom = { dark: true, source: 'ui' };
      }
      save(merged);
      return merged;
    };
  }

  return api;
})();
