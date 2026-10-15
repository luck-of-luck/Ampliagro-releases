/* ═══════════════════════════════════════════════════════════
   AMPLIAGRO — Sistema de Temas
   ───────────────────────────────────────────────────────────
   Só existem TRÊS modos válidos:
     • claro  (dia)
     • escuro (noite)
     • custom (personalizado)
   A FONTE DA VERDADE é o JSON de preferências do usuário
   ("ampliagro-preferences_u<id>" ou "ampliagro-preferences").
   Valores legados (light/dark/system/dia/noite/personalizado)
   são normalizados; qualquer valor inválido vira 'claro'.
   O rótulo do botão na navbar NUNCA mostra "Aparência".
   As cores são controladas por variáveis CSS globais (--cor-*).
   ═══════════════════════════════════════════════════════════ */

/* ── Modos canônicos e normalização ── */
window.TEMA_MODOS_VALIDOS = ['claro', 'escuro', 'custom'];
// #region agent log
// MEDIDO 2026-10-07: este funcao enviava telemetria de depuracao para um
// servidor de ingest local, num porto dev que nao existe. A CSP bloqueava
// todo o pedido e o console ficava inundado. A funcao passa a ser um NO-OP:
// os chamadores ja protegem com `if (window.__dbgNav)`, e este corpo tira o
// envio de rede.
window.__dbgNav = function () {};
window.__dbgThemeSnap = function () {
  var html = document.documentElement;
  var classes = [];
  try {
    html.classList.forEach(function (c) {
      if (c === 'dark' || c.indexOf('custom') === 0) classes.push(c);
    });
  } catch (e) {}
  return {
    classes: classes,
    dataTema: html.getAttribute('data-tema'),
    dataPreset: html.getAttribute('data-preset'),
    corFundo: html.style.getPropertyValue('--cor-fundo') || '',
    themeAccent: html.style.getPropertyValue('--theme-accent') || '',
    lsTheme: (function () {
      try {
        return localStorage.getItem('theme');
      } catch (e) {
        return null;
      }
    })(),
    lsModo: (function () {
      try {
        return localStorage.getItem('ampliagro_tema');
      } catch (e) {
        return null;
      }
    })(),
    sheetCount: document.querySelectorAll('link[rel="stylesheet"]').length,
    styleCount: document.querySelectorAll('head style').length,
  };
};
// #endregion

window.normalizarModoTema = function (modo) {
  var mapa = {
    claro: 'claro',
    dia: 'claro',
    light: 'claro',
    escuro: 'escuro',
    noite: 'escuro',
    dark: 'escuro',
    custom: 'custom',
    personalizado: 'custom',
  };
  return mapa[String(modo || '').toLowerCase()] || null;
};

/* Nome amigável exibido na navbar — nunca retorna "Aparência" */
window.nomeModoTema = function (modo) {
  var m = window.normalizarModoTema(modo);
  if (m === 'escuro') return 'Escuro';
  if (m === 'custom') return 'Personalizado';
  return 'Claro';
};

/* Chave do JSON de preferências do usuário logado (com escopo) */
window.chavePreferenciasUsuario = function () {
  var base = 'ampliagro-preferences';
  var uid = window.AMPLIAGRO_USER_ID;
  if (uid === null || uid === undefined || uid === '') return { scoped: base, plain: base };
  var scoped = base + '_u' + uid;
  return { scoped: scoped, plain: base };
};

/* Lê o JSON de preferências do usuário — prioriza scoped mas mescla com plain para conservar tema */
function lerPreferenciasUsuario() {
  var prefs = {};
  try {
    var chaves = window.chavePreferenciasUsuario();
    var rawScoped = localStorage.getItem(chaves.scoped);
    var rawPlain = chaves.plain !== chaves.scoped ? localStorage.getItem(chaves.plain) : null;
    var prefsScoped = rawScoped ? JSON.parse(rawScoped) : null;
    var prefsPlain = rawPlain ? JSON.parse(rawPlain) : null;
    // prioriza scoped se tiver theme.mode válido, senão usa plain, senão merge
    if (prefsScoped && prefsScoped.theme && prefsScoped.theme.mode) {
      prefs = prefsScoped;
    } else if (prefsPlain && prefsPlain.theme && prefsPlain.theme.mode) {
      prefs = prefsPlain;
      // migra para scoped se usuário logado para conservar
      if (chaves.scoped !== chaves.plain && !rawScoped) {
        try {
          localStorage.setItem(chaves.scoped, JSON.stringify(prefsPlain));
        } catch (e) {}
      }
    } else {
      prefs = prefsScoped || prefsPlain || {};
    }
    if (!prefs || typeof prefs !== 'object') prefs = {};
  } catch (e) {
    prefs = {};
  }
  prefs.theme = prefs.theme || {};
  return prefs;
}

/* Grava o modo no JSON de preferências — sempre em scoped+plain+espelhos para conservar */
function salvarModoNoJsonUsuario(modo) {
  try {
    var prefs = lerPreferenciasUsuario();
    prefs.theme.mode = modo;
    var chaves = window.chavePreferenciasUsuario();
    var json = JSON.stringify(prefs);
    // sempre grava nos 3 lugares para garantir que qualquer página leia
    try {
      localStorage.setItem(chaves.scoped, json);
    } catch (e) {}
    try {
      if (chaves.plain !== chaves.scoped) localStorage.setItem(chaves.plain, json);
    } catch (e) {}
    try {
      localStorage.setItem('ampliagro_tema', modo);
    } catch (e) {}
    try {
      localStorage.setItem('theme', modo);
    } catch (e) {}
  } catch (e) {}
}

window.Tema = {
  claro: {
    nome: 'Claro',
    escuro: false,
    corFundo: '#fdfefe',
    corTexto: '#1d2421',
    corPrimaria: '#0f9d6e',
    corSecundaria: '#1d2421',
    corAcento: '#3ec48f',
    corBorda: '#e5e7eb',
    corHover: 'rgba(15, 157, 110, 0.1)',
  },
  escuro: {
    nome: 'Escuro',
    escuro: true,
    corFundo: '#0b0f0e',
    corTexto: '#e9eeec',
    corPrimaria: '#3ec48f',
    corSecundaria: '#0b0f0e',
    corAcento: '#57d7a0',
    corBorda: '#33413f',
    corHover: 'rgba(62, 196, 143, 0.1)',
  },
};

function modoAtualDom() {
  var html = document.documentElement;
  if (html.classList.contains('custom-theme')) return 'custom';
  return html.getAttribute('data-tema') === 'escuro' ? 'escuro' : 'claro';
}

function aplicarTema(nomeTema, salvar) {
  var modo = window.normalizarModoTema(nomeTema);
  /* Só aceita os dois modos nativos aqui; custom é tratado à parte */
  // #region agent log
  if (window.__dbgNav)
    window.__dbgNav('A', 'theme-system.js:aplicarTema', 'aplicarTema enter', {
      nomeTema: nomeTema,
      modo: modo,
      salvar: salvar !== false,
      before: window.__dbgThemeSnap ? window.__dbgThemeSnap() : null,
      stack: (new Error().stack || '').split('\n').slice(1, 5).join(' | '),
    });
  // #endregion
  if (!modo || modo === 'custom') return false;
  var tema = window.Tema[modo];
  if (!tema) return false;

  // Aplica a classe 'dark' no <html> e limpa custom-theme pegajoso
  var html = document.documentElement;
  Array.from(html.classList).forEach(function (c) {
    if (c.indexOf('custom-theme') === 0) html.classList.remove(c);
  });
  html.classList.toggle('dark', tema.escuro);
  html.setAttribute('data-tema', modo);
  /* Modo nativo: derruba marca de preset (a neutralização legada volta ao gate) */
  try {
    html.removeAttribute('data-preset');
  } catch (e) {}

  // Limpa variáveis injetadas por temas custom/presets (evita "mistura" de temas)
  var propsToRemove = [];
  for (var i = 0; i < html.style.length; i++) {
    var p = html.style[i];
    if (p.indexOf('--cor-nav-') === 0 || p.indexOf('--pal-') === 0 || p.indexOf('--theme-') === 0) {
      propsToRemove.push(p);
    }
  }
  propsToRemove.forEach(function (p) {
    html.style.removeProperty(p);
  });

  // Aplica variáveis CSS globais
  var raiz = html.style;
  raiz.setProperty('--cor-fundo', tema.corFundo);
  raiz.setProperty('--cor-texto', tema.corTexto);
  raiz.setProperty('--cor-primaria', tema.corPrimaria);
  raiz.setProperty('--cor-secundaria', tema.corSecundaria);
  raiz.setProperty('--cor-acento', tema.corAcento);
  raiz.setProperty('--cor-borda', tema.corBorda);
  raiz.setProperty('--cor-hover', tema.corHover);

  if (salvar !== false) {
    try {
      localStorage.setItem('ampliagro_tema', modo);
    } catch (e) {}
    try {
      localStorage.setItem('theme', modo);
    } catch (e) {}
    salvarModoNoJsonUsuario(modo);
    try {
      if (typeof window.__setThemeExpected === 'function')
        window.__setThemeExpected(modo, tema.escuro);
    } catch (e) {}
  }

  // Sincroniza o botão da navbar (se existir)
  if (typeof window.syncModeDropdown === 'function') {
    window.syncModeDropdown(modo);
  }

  return true;
}

/* Aplica o modo PERSONALIZADO salvo no JSON do usuário */
function aplicarCustomSalvo(prefs) {
  prefs = prefs || lerPreferenciasUsuario();
  var custom = prefs.theme.custom;
  if (typeof window.applyCustomTheme === 'function' && custom) {
    window.applyCustomTheme(custom, false);
    return true;
  }
  /* Sem motor custom nesta página: mantém base dia/noite conforme custom.dark */
  var baseEscuro = !!(custom && custom.dark);
  aplicarTema(baseEscuro ? 'escuro' : 'claro', false);
  return false;
}

function alternarTema() {
  /* Se está no personalizado, alterna entre dia/noite pelo estado atual */
  var atual = modoAtualDom();
  var novo = atual === 'escuro' ? 'claro' : 'escuro';
  return aplicarTema(novo);
}

/*
 * RESTAURAÇÃO CENTRAL — sempre lê o JSON do usuário primeiro.
 * Ordem: JSON do usuário → espelhos legados → preferência do SO.
 * O resultado é SEMPRE um dos modos válidos (claro/escuro/custom).
 */
function restaurarTemaDoUsuario() {
  var prefs = lerPreferenciasUsuario();
  // #region agent log
  if (window.__dbgNav)
    window.__dbgNav('A', 'theme-system.js:restaurarTemaDoUsuario', 'restore enter', {
      prefMode: prefs && prefs.theme ? prefs.theme.mode : null,
      hasCustom: !!(prefs && prefs.theme && prefs.theme.custom),
      customDark: !!(prefs && prefs.theme && prefs.theme.custom && prefs.theme.custom.dark),
      before: window.__dbgThemeSnap ? window.__dbgThemeSnap() : null,
      stack: (new Error().stack || '').split('\n').slice(1, 5).join(' | '),
    });
  // #endregion

  var modo = window.normalizarModoTema(prefs.theme.mode);
  if (!modo) {
    try {
      modo = window.normalizarModoTema(localStorage.getItem('theme'));
    } catch (e) {}
  }
  if (!modo) {
    try {
      modo = window.normalizarModoTema(localStorage.getItem('ampliagro_tema'));
    } catch (e) {}
  }
  /* Último recurso: preferência do sistema operacional (dia/noite) */
  if (!modo) {
    var prefereEscuro =
      window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    modo = prefereEscuro ? 'escuro' : 'claro';
  }

  if (modo === 'custom') {
    /* Garante que o JSON fique canônico mesmo se veio de valor legado */
    if (prefs.theme.mode !== 'custom') salvarModoNoJsonUsuario('custom');
    aplicarCustomSalvo(prefs);
    try {
      localStorage.setItem('theme', 'custom');
    } catch (e) {}
    if (typeof window.syncModeDropdown === 'function') window.syncModeDropdown('custom');
    // #region agent log
    if (window.__dbgNav)
      window.__dbgNav('A', 'theme-system.js:restaurarTemaDoUsuario', 'restore exit custom', {
        after: window.__dbgThemeSnap ? window.__dbgThemeSnap() : null,
      });
    // #endregion
    return 'custom';
  }

  aplicarTema(modo);
  // #region agent log
  if (window.__dbgNav)
    window.__dbgNav('A', 'theme-system.js:restaurarTemaDoUsuario', 'restore exit native', {
      modo: modo,
      after: window.__dbgThemeSnap ? window.__dbgThemeSnap() : null,
    });
  // #endregion
  return modo;
}

function carregarTemaSalvo() {
  return restaurarTemaDoUsuario();
}

// ── Watchdog: garante que tema manual não seja sobrescrito por race (3s revert) ──
window.__themeExpected = null;
window.__themeWatchdogTimer = null;
window.__setThemeExpected = function (modo, isDarkCustom) {
  var m = window.normalizarModoTema(modo);
  if (!m) return;
  var isDark = m === 'escuro' || (m === 'custom' && !!isDarkCustom);
  // Para custom, dark vem de prefs.theme.custom.dark
  if (m === 'custom') {
    try {
      var p = lerPreferenciasUsuario();
      if (p.theme && p.theme.custom) isDark = !!p.theme.custom.dark;
      else if (typeof isDarkCustom === 'boolean') isDark = isDarkCustom;
    } catch (e) {}
  }
  window.__themeExpected = { modo: m, isDark: isDark, until: Date.now() + 10000 };
  if (window.__themeWatchdogTimer) clearInterval(window.__themeWatchdogTimer);
  window.__themeWatchdogTimer = setInterval(function () {
    if (!window.__themeExpected) {
      clearInterval(window.__themeWatchdogTimer);
      window.__themeWatchdogTimer = null;
      return;
    }
    if (Date.now() > window.__themeExpected.until) {
      clearInterval(window.__themeWatchdogTimer);
      window.__themeWatchdogTimer = null;
      window.__themeExpected = null;
      return;
    }
    try {
      var html = document.documentElement;
      var curDark = html.classList.contains('dark');
      var curCustom = html.classList.contains('custom-theme');
      var curModo = curCustom
        ? 'custom'
        : html.getAttribute('data-tema') === 'escuro'
          ? 'escuro'
          : 'claro';
      var exp = window.__themeExpected;
      // Se divergir, reaplica
      if (exp.modo === 'custom') {
        if (!curCustom || curDark !== exp.isDark) {
          console.warn('[ThemeWatchdog] Reaplicando custom esperado', exp, 'cur', {
            curCustom,
            curDark,
            curModo,
          });
          restaurarTemaDoUsuario();
        }
      } else {
        if (curModo !== exp.modo || curDark !== exp.isDark) {
          console.warn('[ThemeWatchdog] Reaplicando', exp.modo, 'cur', curModo, curDark);
          aplicarTema(exp.modo, false);
          try {
            if (window.applyThemeVars) window.applyThemeVars();
          } catch (e) {}
          try {
            if (window.syncModeDropdown) window.syncModeDropdown(exp.modo);
          } catch (e) {}
        }
      }
    } catch (e) {}
  }, 500);
};

// Inicialização e eventos globais
(function init() {
  // Aplica imediatamente (o <html> já existe; evita flash de cor errada).
  // Lê SEMPRE o JSON do usuário como fonte da verdade.
  carregarTemaSalvo();
  // Inicializa expected com o modo atual para watchdog também proteger o estado inicial
  try {
    var initModo = modoAtualDom();
    var initDark = document.documentElement.classList.contains('dark');
    window.__setThemeExpected(initModo, initDark);
    // Mas não precisa watchdog longo no init, só 2s
    if (window.__themeWatchdogTimer) {
      clearInterval(window.__themeWatchdogTimer);
      window.__themeWatchdogTimer = null;
    }
    window.__themeExpected = null;
  } catch (e) {}

  // Sincroniza ao trocar o tema em outra aba
  window.addEventListener('storage', function (e) {
    if (!e.key) return;
    var chaves = window.chavePreferenciasUsuario();
    if (
      e.key === chaves.scoped ||
      e.key === chaves.plain ||
      e.key === 'ampliagro_tema' ||
      e.key === 'theme'
    ) {
      // Se watchdog está ativo, ignora storage externo que iria reverter manual
      if (window.__themeExpected && Date.now() < window.__themeExpected.until) {
        console.warn('[Theme] storage event ignorado por watchdog', e.key);
        return;
      }
      restaurarTemaDoUsuario();
    }
  });

  // Se nada foi salvo, acompanha a preferência do SO
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (window.__themeExpected && Date.now() < window.__themeExpected.until) return;
      var prefs = lerPreferenciasUsuario();
      var temModoSalvo = !!window.normalizarModoTema(prefs.theme.mode);
      if (!temModoSalvo) carregarTemaSalvo();
    });
  }
})();

// API pública
window.aplicarTema = aplicarTema;
window.alternarTema = alternarTema;
window.carregarTemaSalvo = carregarTemaSalvo;
window.restaurarTemaDoUsuario = restaurarTemaDoUsuario;
window.modoAtualDom = modoAtualDom;

/* API de tema compartilhada — usada pelos botões/selectMode da navbar.
   Só existia no index.html (SPA); estava ausente nas demais páginas
   (base.html), o que fazia `selectMode` chamar window.setTheme inexistente
   e o tema não mudar fora do dashboard. */
window.setTheme = function (theme, e) {
  if (e && e.stopPropagation) e.stopPropagation();
  var modo = window.normalizarModoTema(theme);

  if (modo === 'custom') {
    var prefs = typeof lerPreferenciasUsuario === 'function' ? lerPreferenciasUsuario() : {};
    if (typeof window.applyCustomTheme === 'function') {
      window.applyCustomTheme(prefs.theme.custom || {}, false);
    } else {
      aplicarTema(prefs.theme.custom && prefs.theme.custom.dark ? 'escuro' : 'claro', false);
    }
    salvarModoNoJsonUsuario('custom');
    try {
      localStorage.setItem('theme', 'custom');
    } catch (err) {}
    try {
      if (typeof window.__setThemeExpected === 'function')
        window.__setThemeExpected(
          'custom',
          !!(prefs.theme && prefs.theme.custom && prefs.theme.custom.dark)
        );
    } catch (e) {}
    if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
    if (typeof window.syncModeDropdown === 'function') window.syncModeDropdown('custom');
    if (typeof window.closeModeDropdown === 'function') window.closeModeDropdown();
    return true;
  }

  var alvo = modo || 'claro';
  aplicarTema(alvo);
  if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
  if (typeof window.syncModeDropdown === 'function') window.syncModeDropdown(alvo);
  if (typeof window.closeModeDropdown === 'function') window.closeModeDropdown();
  return true;
};

/* Fallback global de sincronização do botão da navbar.
   O index.html sobrescreve com uma versão mais rica; esta garante
   que TODAS as páginas mostrem o modo ativo corretamente.
   O rótulo é SEMPRE um modo válido — nunca "Aparência". */
window.syncModeDropdown =
  window.syncModeDropdown ||
  function (modo) {
    var label = document.querySelector('#nav-mode-btn .nav-mode-label');
    if (!label) return;
    if (!window.normalizarModoTema(modo)) modo = modoAtualDom();
    label.textContent = window.nomeModoTema(modo);
  };

/* Abre o modal "Personalizar" a partir do dropdown (todas as páginas) */
window.openPersonalizarMode = function (e) {
  if (e && e.stopPropagation) e.stopPropagation();
  var dd = document.getElementById('mode-dropdown');
  if (dd) dd.classList.remove('is-open');
  if (typeof window.openCustomThemeModal === 'function') {
    window.openCustomThemeModal();
  } else {
    /* Sem modal do dashboard nesta pagina: usa a pagina dedicada */
    window.location.href = '/config/page/';
  }
};
