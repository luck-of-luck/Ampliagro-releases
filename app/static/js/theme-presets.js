/* ═══════════════════════════════════════════════════════════
   AMPLIAGRO — Painel de Aparência (presets de tema)
   Carregado no base.html; usado pelo dropdown de modos da navbar.
   Modos: Claro / Escuro / Personalizado.
   ═══════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  window.AMPLIAGRO_THEMES = {
    escuro: {
      nome: 'Escuro',
      tituloCurto: 'Escuro',
      icone: 'bi-moon-stars',
      dark: true,
      descricao: 'Preto/carbono sóbrio com esmeralda premium',
      sistema: {
        planoDeFundoDoSistema: '#0b0f0e',
        planoDeFundoDaNavbar: '#131917',
        planoDeFundoDoCard: '#151b19',
        planoDeFundoDoCardAninhado: '#1a211f',
        planoDeFundoDaToolbar: '#131917',
      },
      bordas: {
        bordaPadrao: '#3ec48f',
        bordaSuave: 'rgba(62,196,143,0.22)',
      },
      texto: {
        textoPrimario: '#e9eeec',
        textoSecundario: '#8b9792',
        textoFraco: '#5f6b66',
      },
      destaque: {
        corPrimaria: '#3ec48f',
        corClara: '#57d7a0',
        corEscura: '#0b8259',
        corDoBrilho: 'rgba(62,196,143,0.4)',
        corDoTextoSobreDestaque: '#0a1410',
      },
      grafico: {
        corDaLinha: '#3ec48f',
        corDoPreenchimento: 'rgba(62,196,143,0.2)',
        corDaGrade: 'rgba(233,238,236,0.08)',
      },
      estados: {
        alerta: '#e0a84e',
        erro: '#ef6a6a',
        sucesso: '#3ec48f',
      },
    },

    claro: {
      nome: 'Claro',
      tituloCurto: 'Claro',
      icone: 'bi-sun',
      dark: false,
      descricao: 'Branco suave com esmeralda da marca',
      sistema: {
        planoDeFundoDoSistema: '#f6f8f7',
        planoDeFundoDaNavbar: '#fdfefe',
        planoDeFundoDoCard: '#fdfefe',
        planoDeFundoDoCardAninhado: '#f3f7f5',
        planoDeFundoDaToolbar: '#f6f8f7',
      },
      bordas: {
        bordaPadrao: '#0f9d6e',
        bordaSuave: 'rgba(15,157,110,0.25)',
      },
      texto: {
        textoPrimario: '#1d2421',
        textoSecundario: '#5f6b66',
        textoFraco: '#8b9792',
      },
      destaque: {
        corPrimaria: '#0f9d6e',
        corClara: '#4cc396',
        corEscura: '#0b8259',
        corDoBrilho: 'rgba(15,157,110,0.35)',
        corDoTextoSobreDestaque: '#ffffff',
      },
      grafico: {
        corDaLinha: '#0f9d6e',
        corDoPreenchimento: 'rgba(15,157,110,0.18)',
        corDaGrade: 'rgba(29,36,33,0.10)',
      },
      estados: {
        alerta: '#c98a24',
        erro: '#d93a3a',
        sucesso: '#0f9d6e',
      },
    },

    cafe: {
      nome: 'Café',
      tituloCurto: 'Café',
      icone: 'bi-cup-hot',
      dark: true,
      descricao: 'Marrom torrado aconchegante com caramelo',
      sistema: {
        planoDeFundoDoSistema: '#14100c',
        planoDeFundoDaNavbar: '#1d1712',
        planoDeFundoDoCard: '#201913',
        planoDeFundoDoCardAninhado: '#262019',
        planoDeFundoDaToolbar: '#1d1712',
      },
      bordas: {
        bordaPadrao: '#c08a4e',
        bordaSuave: 'rgba(192,138,78,0.25)',
      },
      texto: {
        textoPrimario: '#f0e8dc',
        textoSecundario: '#a89a86',
        textoFraco: '#6f6355',
      },
      destaque: {
        corPrimaria: '#c08a4e',
        corClara: '#d9a866',
        corEscura: '#8a5f2e',
        corDoBrilho: 'rgba(192,138,78,0.4)',
        corDoTextoSobreDestaque: '#1a120a',
      },
      grafico: {
        corDaLinha: '#c08a4e',
        corDoPreenchimento: 'rgba(192,138,78,0.2)',
        corDaGrade: 'rgba(240,232,220,0.08)',
      },
      estados: {
        alerta: '#e0a84e',
        erro: '#ef6a6a',
        sucesso: '#7fb069',
      },
    },

    oceano: {
      nome: 'Oceano',
      tituloCurto: 'Oceano',
      icone: 'bi-water',
      dark: true,
      descricao: 'Azul profundo com ciano vibrante',
      sistema: {
        planoDeFundoDoSistema: '#0a1218',
        planoDeFundoDaNavbar: '#0e1a23',
        planoDeFundoDoCard: '#101f2a',
        planoDeFundoDoCardAninhado: '#142634',
        planoDeFundoDaToolbar: '#0e1a23',
      },
      bordas: {
        bordaPadrao: '#38bdf8',
        bordaSuave: 'rgba(56,189,248,0.22)',
      },
      texto: {
        textoPrimario: '#e8f1f6',
        textoSecundario: '#8ba3b2',
        textoFraco: '#5d7280',
      },
      destaque: {
        corPrimaria: '#38bdf8',
        corClara: '#7dd3fc',
        corEscura: '#0369a1',
        corDoBrilho: 'rgba(56,189,248,0.4)',
        corDoTextoSobreDestaque: '#08131a',
      },
      grafico: {
        corDaLinha: '#38bdf8',
        corDoPreenchimento: 'rgba(56,189,248,0.2)',
        corDaGrade: 'rgba(232,241,246,0.08)',
      },
      estados: {
        alerta: '#f0b429',
        erro: '#f26d6d',
        sucesso: '#34d399',
      },
    },

    pordosol: {
      nome: 'Pôr-do-sol',
      tituloCurto: 'Pôr-do-sol',
      icone: 'bi-sunset',
      dark: true,
      descricao: 'Laranja quente de fim de tarde no campo',
      sistema: {
        planoDeFundoDoSistema: '#160f0a',
        planoDeFundoDaNavbar: '#201410',
        planoDeFundoDoCard: '#241811',
        planoDeFundoDoCardAninhado: '#2b1f15',
        planoDeFundoDaToolbar: '#201410',
      },
      bordas: {
        bordaPadrao: '#f97316',
        bordaSuave: 'rgba(249,115,22,0.25)',
      },
      texto: {
        textoPrimario: '#f7ece2',
        textoSecundario: '#b09a87',
        textoFraco: '#77655a',
      },
      destaque: {
        corPrimaria: '#f97316',
        corClara: '#fb923c',
        corEscura: '#c2410c',
        corDoBrilho: 'rgba(249,115,22,0.4)',
        corDoTextoSobreDestaque: '#1c0e04',
      },
      grafico: {
        corDaLinha: '#f97316',
        corDoPreenchimento: 'rgba(249,115,22,0.2)',
        corDaGrade: 'rgba(247,236,226,0.08)',
      },
      estados: {
        alerta: '#fbbf24',
        erro: '#ef4444',
        sucesso: '#4ade80',
      },
    },

    floresta: {
      nome: 'Floresta',
      tituloCurto: 'Floresta',
      icone: 'bi-tree',
      dark: false,
      descricao: 'Verde mata claro e fresco',
      sistema: {
        planoDeFundoDoSistema: '#eef4ee',
        planoDeFundoDaNavbar: '#f7faf7',
        planoDeFundoDoCard: '#fbfdfb',
        planoDeFundoDoCardAninhado: '#e6efe6',
        planoDeFundoDaToolbar: '#eef4ee',
      },
      bordas: {
        bordaPadrao: '#2f7d4f',
        bordaSuave: 'rgba(47,125,79,0.25)',
      },
      texto: {
        textoPrimario: '#1c2b22',
        textoSecundario: '#55685c',
        textoFraco: '#7d8f84',
      },
      destaque: {
        corPrimaria: '#2f7d4f',
        corClara: '#57a773',
        corEscura: '#1d5c37',
        corDoBrilho: 'rgba(47,125,79,0.35)',
        corDoTextoSobreDestaque: '#ffffff',
      },
      grafico: {
        corDaLinha: '#2f7d4f',
        corDoPreenchimento: 'rgba(47,125,79,0.18)',
        corDaGrade: 'rgba(28,43,34,0.10)',
      },
      estados: {
        alerta: '#b97f1f',
        erro: '#cf3d3d',
        sucesso: '#2f7d4f',
      },
    },

    uva: {
      nome: 'Uva',
      tituloCurto: 'Uva',
      icone: 'bi-gem',
      dark: true,
      descricao: 'Roxo vinhedo elegante',
      sistema: {
        planoDeFundoDoSistema: '#120e18',
        planoDeFundoDaNavbar: '#191223',
        planoDeFundoDoCard: '#1d1529',
        planoDeFundoDoCardAninhado: '#241b33',
        planoDeFundoDaToolbar: '#191223',
      },
      bordas: {
        bordaPadrao: '#a78bfa',
        bordaSuave: 'rgba(167,139,250,0.25)',
      },
      texto: {
        textoPrimario: '#ece7f5',
        textoSecundario: '#9d92b5',
        textoFraco: '#6b6084',
      },
      destaque: {
        corPrimaria: '#a78bfa',
        corClara: '#c4b5fd',
        corEscura: '#7c3aed',
        corDoBrilho: 'rgba(167,139,250,0.4)',
        corDoTextoSobreDestaque: '#150f22',
      },
      grafico: {
        corDaLinha: '#a78bfa',
        corDoPreenchimento: 'rgba(167,139,250,0.2)',
        corDaGrade: 'rgba(236,231,245,0.08)',
      },
      estados: {
        alerta: '#f0b429',
        erro: '#f26d6d',
        sucesso: '#34d399',
      },
    },
  };

  function preset(id) {
    return (window.AMPLIAGRO_THEMES || {})[id] || null;
  }

  /* ═══════════════════════════════════════════════════════════
     PALETTA ÚNICA — todas as telas (gráficos, KPIs, estados)
     leem as variáveis --pal-* aplicadas no <html>.
     ═══════════════════════════════════════════════════════════ */

  var NATIVE_PALETTES = {
    light: {
      accent: '#0f9d6e',
      metrica: '#0f9d6e',
      accentBar: 'rgba(15,157,110,0.50)',
      accentFill: 'rgba(15,157,110,0.10)',
      grid: 'rgba(29,36,33,0.08)',
      gridSoft: 'rgba(29,36,33,0.04)',
      tick: '#5f6b66',
      pointBorder: '#fdfefe',
      chartBg: '#fdfefe',
      ok: '#0f9d6e',
      alert: '#c98a24',
      error: '#d93a3a',
      warn: '#c98a24',
      series: [
        '#0f9d6e',
        '#c19a3c',
        '#2f8f7e',
        '#3b82f6',
        '#8b5cf6',
        '#14b8a6',
        '#84cc16',
        '#e08f3c',
      ],
    },
    dark: {
      accent: '#3ec48f',
      metrica: '#3ec48f',
      accentBar: 'rgba(62,196,143,0.50)',
      accentFill: 'rgba(62,196,143,0.12)',
      grid: 'rgba(233,238,236,0.07)',
      gridSoft: 'rgba(233,238,236,0.035)',
      tick: '#8b9792',
      pointBorder: '#151b19',
      chartBg: '#151b19',
      ok: '#3ec48f',
      alert: '#e0a84e',
      error: '#ef6a6a',
      warn: '#e0a84e',
      series: [
        '#3ec48f',
        '#d9b45c',
        '#4fb5a3',
        '#60a5fa',
        '#a78bfa',
        '#22d3ee',
        '#a3e635',
        '#f0a84e',
      ],
    },
  };

  /* Deriva a paleta a partir do schema de um preset (destaque + grafico + estados) */
  function presetPalette(p) {
    var g = p.grafico,
      e = p.estados,
      t = p.texto,
      sys = p.sistema;
    var series = p.dark
      ? [g.corDaLinha, '#d9b45c', '#60a5fa', '#f472b6', '#a78bfa', '#22d3ee', '#a3e635', '#f0a84e']
      : [g.corDaLinha, '#c19a3c', '#3b82f6', '#ef4444', '#8b5cf6', '#14b8a6', '#84cc16', '#e08f3c'];
    return {
      accent: g.corDaLinha,
      metrica: (p.destaque || {}).corPrimaria || g.corDaLinha,
      accentBar: g.corDoPreenchimento,
      accentFill: g.corDoPreenchimento,
      grid: g.corDaGrade,
      gridSoft: g.corDaGrade,
      tick: t.textoSecundario,
      pointBorder: sys.planoDeFundoDoCard,
      chartBg: sys.planoDeFundoDoCard,
      ok: e.sucesso,
      alert: e.alerta,
      error: e.erro,
      warn: e.alerta,
      series: series,
    };
  }

  function activePalette() {
    if (typeof window.AMPLIAGRO_THEMES === 'object') {
      var ap = activePresetId();
      if (ap) {
        var pp = preset(ap);
        if (pp) return presetPalette(pp);
      }
    }
    var dark = document.documentElement.classList.contains('dark');
    return NATIVE_PALETTES[dark ? 'dark' : 'light'];
  }

  var PAL_VARS = {
    accent: '--pal-accent',
    metrica: '--pal-metrica',
    accentBar: '--pal-accent-bar',
    accentFill: '--pal-accent-fill',
    grid: '--pal-grid',
    gridSoft: '--pal-grid-soft',
    tick: '--pal-tick',
    pointBorder: '--pal-point-border',
    chartBg: '--pal-bg',
    ok: '--pal-ok',
    alert: '--pal-alert',
    error: '--pal-error',
    warn: '--pal-warn',
    series: '--pal-series',
  };

  /* Aplica --pal-* no <html> e avisa as telas para repintarem */
  window.applyThemeVars = function () {
    var pal = activePalette();
    var sch = activeSchema();
    // #region agent log
    if (window.__dbgNav)
      window.__dbgNav('B', 'theme-presets.js:applyThemeVars', 'applyThemeVars', {
        palAccent: pal && pal.accent,
        schemaId: sch && sch.id,
        htmlCustom: document.documentElement.classList.contains('custom-theme'),
        htmlDark: document.documentElement.classList.contains('dark'),
      });
    // #endregion
    var root = document.documentElement.style;
    Object.keys(PAL_VARS).forEach(function (k) {
      root.setProperty(PAL_VARS[k], k === 'series' ? JSON.stringify(pal.series) : pal[k]);
    });
    /* Marca preset nomeado p/ o CSS liberar a neutralização legada */
    if (sch && sch.id) document.documentElement.setAttribute('data-preset', sch.id);
    else document.documentElement.removeAttribute('data-preset');
    /* Sincroniza --cor-nav-* (navbar/widgetbar) e --cor-* (soft-ui) */
    syncNavAndSoftUI(pal, sch ? sch.schema : null);
    try {
      document.dispatchEvent(new CustomEvent('ampliagro:palette', { bubbles: true }));
    } catch (e) {}
  };

  function syncNavAndSoftUI(pal, schema) {
    var root = document.documentElement.style;
    var s = schema && schema.sistema ? schema.sistema : null;
    var t = schema && schema.texto ? schema.texto : null;
    var b = schema && schema.bordas ? schema.bordas : null;
    var isDark =
      schema && typeof schema.dark === 'boolean'
        ? !!schema.dark
        : document.documentElement.classList.contains('dark');
    /* --cor-nav-* vars for navbar */
    root.setProperty('--cor-nav-primaria', pal.accent);
    root.setProperty('--cor-nav-ouro', pal.alert || '#c98a24');
    root.setProperty(
      '--cor-nav-ouro-brilho',
      pal.alert ? pal.alert.replace(')', ',0.22)').replace('rgb', 'rgba') : 'rgba(193,154,60,0.22)'
    );
    root.setProperty('--cor-nav-pilula-ativa', pal.accent);
    root.setProperty('--cor-nav-avatar', pal.accent);
    root.setProperty('--cor-nav-etiqueta-fundo', pal.accentFill || 'rgba(15,157,110,0.07)');
    root.setProperty('--cor-nav-etiqueta-hover', pal.accentBar || 'rgba(15,157,110,0.14)');
    root.setProperty('--cor-nav-busca-fundo', pal.gridSoft || 'rgba(29,36,33,0.045)');
    root.setProperty('--cor-nav-busca-foco', pal.accentFill || 'rgba(15,157,110,0.08)');
    root.setProperty('--cor-nav-separador', pal.grid || 'rgba(29,36,33,0.07)');
    root.setProperty('--cor-nav-texto', pal.tick || (isDark ? '#e9eeec' : '#1b2220'));
    root.setProperty('--cor-nav-texto-medio', pal.tick || (isDark ? '#8b9792' : '#5f6b66'));
    if (isDark) {
      root.setProperty('--cor-nav-fundo', 'rgba(21,27,25,0.88)');
      root.setProperty('--cor-nav-fundo-rolagem', 'rgba(21,27,25,0.97)');
      root.setProperty('--cor-nav-borda', 'rgba(233,238,236,0.09)');
      root.setProperty('--cor-nav-pilula-hover', 'rgba(62,196,143,0.12)');
      root.setProperty('--cor-nav-pilula-texto', '#3ec48f');
      root.setProperty('--cor-nav-vidro-borda', 'rgba(255,255,255,0.06)');
      root.setProperty('--cor-nav-sombra', '0 1px 3px rgba(0,0,0,0.2)');
      root.setProperty('--cor-nav-dropdown-fundo', 'rgba(21,27,25,0.96)');
      root.setProperty('--cor-nav-dropdown-borda', 'rgba(233,238,236,0.09)');
      root.setProperty('--cor-nav-dropdown-sombra', '0 12px 48px rgba(0,0,0,0.5)');
    } else {
      root.setProperty('--cor-nav-fundo', 'rgba(253,254,254,0.82)');
      root.setProperty('--cor-nav-fundo-rolagem', 'rgba(253,254,254,0.96)');
      root.setProperty('--cor-nav-borda', 'rgba(29,36,33,0.10)');
      root.setProperty('--cor-nav-pilula-hover', 'rgba(29,36,33,0.055)');
      root.setProperty('--cor-nav-pilula-texto', '#ffffff');
      root.setProperty('--cor-nav-vidro-borda', 'rgba(255,255,255,0.6)');
      root.setProperty(
        '--cor-nav-sombra',
        '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)'
      );
      root.setProperty('--cor-nav-dropdown-fundo', 'rgba(253,254,254,0.96)');
      root.setProperty('--cor-nav-dropdown-borda', 'rgba(29,36,33,0.10)');
      root.setProperty('--cor-nav-dropdown-sombra', '0 12px 48px rgba(13,22,18,0.12)');
    }
    /* --cor-* vars for soft-ui */
    root.setProperty('--cor-primaria', pal.accent);
    root.setProperty('--cor-primaria-forte', pal.accent);
    root.setProperty('--cor-primaria-suave', pal.accentFill || 'rgba(15,157,110,0.12)');
    root.setProperty('--cor-ouro', pal.alert || '#c19a3c');
    root.setProperty(
      '--cor-ouro-suave',
      (pal.alert || '#c19a3c').replace(')', ',0.16)').replace('rgb', 'rgba')
    );
    root.setProperty('--cor-sucesso', pal.ok || pal.accent);
    root.setProperty('--cor-alerta', pal.alert || '#c98a24');
    root.setProperty('--cor-erro', pal.error || '#d93a3a');
    root.setProperty(
      '--cor-erro-suave',
      (pal.error || '#d93a3a').replace(')', ',0.12)').replace('rgb', 'rgba')
    );
    if (isDark) {
      root.setProperty('--cor-fundo', (s && s.planoDeFundoDoSistema) || '#0b0f0e');
      root.setProperty('--cor-fundo-escuro', (s && s.planoDeFundoDaNavbar) || '#131917');
      root.setProperty('--cor-fundo-card', (s && s.planoDeFundoDoCard) || '#151b19');
      root.setProperty(
        '--cor-fundo-card-aninhado',
        (s && s.planoDeFundoDoCardAninhado) || '#1a211f'
      );
      root.setProperty(
        '--cor-fundo-card-profundo',
        (s && s.planoDeFundoDoCardAninhado) || '#202826'
      );
      root.setProperty('--cor-texto', (t && t.textoPrimario) || '#e9eeec');
      root.setProperty('--cor-texto-medio', (t && t.textoSecundario) || '#8b9792');
      root.setProperty('--cor-texto-fraco', (t && t.textoFraco) || '#5f6b66');
      root.setProperty('--cor-borda', (b && b.bordaSuave) || 'rgba(233,238,236,0.09)');
      root.setProperty('--cor-borda-forte', (b && b.bordaPadrao) || 'rgba(233,238,236,0.16)');
      root.setProperty('--cor-sombra', 'rgba(0,0,0,0.5)');
      root.setProperty('--cor-sombra-clara', 'rgba(255,255,255,0.05)');
      root.setProperty('--cor-sombra-interna', 'rgba(0,0,0,0.4)');
    } else {
      root.setProperty('--cor-fundo', (s && s.planoDeFundoDoSistema) || '#f6f8f7');
      root.setProperty('--cor-fundo-escuro', (s && s.planoDeFundoDaNavbar) || '#e9eeec');
      root.setProperty('--cor-fundo-card', (s && s.planoDeFundoDoCard) || '#fdfefe');
      root.setProperty(
        '--cor-fundo-card-aninhado',
        (s && s.planoDeFundoDoCardAninhado) || '#f3f7f5'
      );
      root.setProperty(
        '--cor-fundo-card-profundo',
        (s && s.planoDeFundoDoCardAninhado) || '#e9efec'
      );
      root.setProperty('--cor-texto', (t && t.textoPrimario) || '#1d2421');
      root.setProperty('--cor-texto-medio', (t && t.textoSecundario) || '#5f6b66');
      root.setProperty('--cor-texto-fraco', (t && t.textoFraco) || '#8b9792');
      root.setProperty('--cor-borda', (b && b.bordaSuave) || 'rgba(29,36,33,0.09)');
      root.setProperty('--cor-borda-forte', (b && b.bordaPadrao) || 'rgba(29,36,33,0.16)');
      root.setProperty('--cor-sombra', 'rgba(29,36,33,0.12)');
      root.setProperty('--cor-sombra-clara', 'rgba(255,255,255,0.92)');
      root.setProperty('--cor-sombra-interna', 'rgba(29,36,33,0.06)');
    }
  }

  /* Leitor único para telas com Canvas (Chart.js): retorna a paleta ativa */
  window.ampliChartPalette = function () {
    var cs = getComputedStyle(document.documentElement);
    var read = function (name) {
      return cs.getPropertyValue(name).trim();
    };
    var seriesRaw = read('--pal-series');
    var series = null;
    if (seriesRaw) {
      try {
        series = JSON.parse(seriesRaw);
      } catch (e) {}
    }
    if (!series && typeof window.AMPLIAGRO_THEMES === 'object') {
      var pal = activePalette();
      series = pal.series;
    }
    if (!series) series = NATIVE_PALETTES.light.series.slice();
    return {
      isDark: document.documentElement.classList.contains('dark'),
      accent: read('--pal-accent') || '#0f9d6e',
      metrica: read('--pal-metrica') || read('--pal-accent') || '#0f9d6e',
      accentBar: read('--pal-accent-bar') || 'rgba(15,157,110,0.50)',
      accentFill: read('--pal-accent-fill') || 'rgba(15,157,110,0.10)',
      grid: read('--pal-grid') || 'rgba(29,36,33,0.08)',
      gridSoft: read('--pal-grid-soft') || 'rgba(29,36,33,0.04)',
      tick: read('--pal-tick') || '#5f6b66',
      pointBorder: read('--pal-point-border') || '#fdfefe',
      chartBg: read('--pal-bg') || '#fdfefe',
      ok: read('--pal-ok') || '#0f9d6e',
      alert: read('--pal-alert') || '#c98a24',
      error: read('--pal-error') || '#d93a3a',
      warn: read('--pal-warn') || '#c98a24',
      series: series,
      pie: series,
    };
  };

  /* Sincroniza automaticamente quando <html> troca de classe (dark/custom).
     Guarda a última classe p/ não repintar à toa (cada repaint rebuilda charts). */
  if (typeof MutationObserver !== 'undefined') {
    var _palTimer = null;
    var _lastCls = document.documentElement.className;
    new MutationObserver(function () {
      var cur = document.documentElement.className;
      if (cur === _lastCls) return;
      _lastCls = cur;
      clearTimeout(_palTimer);
      _palTimer = setTimeout(function () {
        window.applyThemeVars();
      }, 120);
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  }
  window.applyThemeVars();

  /* ═══════════════════════════════════════════════════════════
     NEON — plugin global do Chart.js: linhas, barras e pontos
     ganham brilho (glow) na cor do acento quando tema custom.
     Bordas/grade permanecem sem brilho (apenas o dado brilha).
     ═══════════════════════════════════════════════════════════ */

  var NEON_BLUR = 16;
  var _neonCtx = null;

  /* Guarda o ctx de cada chart para restaurar após o desenho */
  var neonGlowPlugin = {
    id: 'ampliagroNeon',
    beforeDatasetsDraw: function (chart) {
      var html = document.documentElement;
      if (!html.classList.contains('custom-theme')) return;
      var cs = getComputedStyle(html);
      var accent = cs.getPropertyValue('--pal-accent').trim() || '#3ec48f';
      _neonCtx = chart.ctx;
      _neonCtx.save();
      _neonCtx.shadowColor = accent;
      _neonCtx.shadowBlur = NEON_BLUR;
    },
    afterDatasetsDraw: function () {
      if (_neonCtx) {
        try {
          _neonCtx.restore();
        } catch (e) {}
        _neonCtx = null;
      }
    },
  };

  window.ampliRegisterChartGlow = function () {
    if (typeof window.Chart !== 'function') return false;
    if (window._ampliNeonRegistered) return true;
    try {
      // Chart.js 4.x uses Chart.register() instead of Chart.plugins.register()
      if (typeof window.Chart.register === 'function') {
        window.Chart.register(neonGlowPlugin);
      } else if (typeof window.Chart.plugins?.register === 'function') {
        // Fallback for Chart.js 3.x
        window.Chart.plugins.register(neonGlowPlugin);
      }
      window._ampliNeonRegistered = true;
      return true;
    } catch (e) {
      return false;
    }
  };

  /* Registra assim que o Chart.js estiver disponível (base.html carrega depois) */
  var _glowTries = 0;
  (function pollChart() {
    if (window.ampliRegisterChartGlow()) return;
    if (_glowTries++ < 100) setTimeout(pollChart, 100);
  })();

  /* Converte o schema do preset para o formato de tema custom do sistema */
  window.mapPresetToCustom = function (id) {
    var p = preset(id);
    if (!p) return null;
    return {
      mode: 'custom',
      source: 'preset',
      presetId: id,
      dark: !!p.dark,
      applyNavbar: true,
      applyWorkspace: true,
      applyWidgetbar: true,
      accent: p.destaque.corPrimaria,
      text: p.texto.textoPrimario,
      navbar: p.sistema.planoDeFundoDaNavbar,
      workspace: p.sistema.planoDeFundoDoSistema,
      card: p.sistema.planoDeFundoDoCard,
      widgetbar: p.sistema.planoDeFundoDaToolbar,
      schema: p,
    };
  };

  /* Aplica as classes/vars do tema custom (fallback para páginas
     sem window.applyCustomTheme, ex.: dashboard) */
  function applyCustomFallback(custom) {
    var html = document.documentElement;
    ['custom-theme-navbar', 'custom-theme-workspace', 'custom-theme-widgetbar'].forEach(
      function (c) {
        html.classList.remove(c);
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
    /* Marca preset p/ liberar a neutralização legada no CSS */
    var sch = custom.schema || null;
    if (!sch && custom.source === 'preset' && custom.presetId) sch = preset(custom.presetId);
    if (sch && custom.presetId) html.setAttribute('data-preset', custom.presetId);
  }

  /* Restaura preset/custom em páginas SEM o motor do dashboard.
     O theme-system.js já tentou; sem window.applyCustomTheme ele caiu
     no base claro/escuro (mistura). Aqui completamos com o fallback. */
  function restaurarCustomSeNecessario() {
    try {
      var prefs = typeof window.getPreferences === 'function' ? window.getPreferences() : {};
      var t = prefs.theme || {};
      if (t.mode !== 'custom' || !t.custom) return;
      var html = document.documentElement;
      if (html.classList.contains('custom-theme')) return; // dashboard já aplicou
      if (typeof window.applyCustomTheme === 'function') {
        window.applyCustomTheme(t.custom, false);
      } else {
        applyCustomFallback(t.custom);
      }
      if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
      if (typeof window.syncModeDropdown === 'function') window.syncModeDropdown('custom');
    } catch (e) {}
  }

  /* Seleção de preset a partir do painel — renomeado para evitar conflito com widget-presets.js */
  window.selectThemePreset = function (id, e) {
    if (e && e.stopPropagation) e.stopPropagation();

    /* Card "Personalizado": abre a sub-lista de temas prontos.
       O modal de cores abre pelo card "Criar do zero" ou pelo botão Personalizar. */
    if (id === 'personalizado') {
      window.toggleSubPresets();
      return true;
    }

    /* Card "Criar do zero": abre o modal de personalização de cores */
    if (id === '__novo') {
      if (typeof window.openPersonalizarMode === 'function') {
        window.openPersonalizarMode(e);
        return true;
      }
      if (typeof window.openCustomThemeModal === 'function')
        window.openCustomThemeModal();
      if (typeof window.closeModeDropdown === 'function') window.closeModeDropdown();
      return true;
    }

    /* Modos nativos claro / escuro: usa o motor do theme-system.js */
    if ((id === 'claro' || id === 'escuro') && typeof window.aplicarTema === 'function') {
      window.aplicarTema(id);
      if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
      if (typeof window.syncModeDropdown === 'function') window.syncModeDropdown(id);
      if (typeof window.closeModeDropdown === 'function') window.closeModeDropdown();
      window.refreshModePanel();
      return true;
    }

    var custom = window.mapPresetToCustom(id);
    if (!custom) return false;

    var prefs = typeof window.getPreferences === 'function' ? window.getPreferences() : {};
    prefs.theme = prefs.theme || {};
    prefs.theme.mode = 'custom';
    prefs.theme.custom = custom;
    if (typeof window.savePreferences === 'function')
      window.savePreferences({ theme: prefs.theme });

    if (typeof window.applyCustomTheme === 'function') {
      window.applyCustomTheme(custom, false);
    } else {
      applyCustomFallback(custom);
    }
    if (typeof window.applyThemeVars === 'function') window.applyThemeVars();
    if (typeof window.syncModeDropdown === 'function') window.syncModeDropdown('custom');
    if (typeof window.closeModeDropdown === 'function') window.closeModeDropdown();
    window.refreshModePanel();
    return true;
  };

  // Alias for backward compatibility (used by theme panel cards onclick)
  window.selectPreset = window.selectThemePreset;

  /* ═══════════════════════════════════════════════════════════
     PAINEL: só Claro / Escuro / Personalizado.
     Os presets nomeados (Café, Oceano, Pôr-do-sol, Floresta, Uva)
     moram DENTRO do Personalizado, numa sub-lista expansível.
     ═══════════════════════════════════════════════════════════ */
  var SUB_PRESETS = ['cafe', 'oceano', 'pordosol', 'floresta', 'uva'];

  function ensureSubStyles() {
    if (document.getElementById('mode-subpresets-css')) return;
    var st = document.createElement('style');
    st.id = 'mode-subpresets-css';
    st.textContent = [
      '.nav-mode-subpresets{flex-basis:100%;max-width:100%;grid-column:1/-1;margin-top:2px;border-top:1px dashed var(--cor-nav-dropdown-borda);padding-top:8px;display:none;}',
      '.nav-mode-subpresets.open{display:block;}',
      '.nav-mode-subpresets-title{font-size:10px;font-weight:700;letter-spacing:.04em;opacity:.75;margin:0 2px 6px;}',
      '.nav-mode-subpresets-grid{display:flex;flex-wrap:wrap;gap:8px;}',
      '.nav-mode-subpresets-grid .nav-mode-card{flex:1 1 140px;max-width:170px;}',
      '.nav-mode-card.is-open{border-color:var(--cor-nav-primaria);box-shadow:0 0 0 1px var(--cor-nav-primaria);}',
      '.nav-mode-subpreset-new{display:flex;align-items:center;justify-content:center;gap:6px;min-height:64px;font-size:12px;font-weight:600;}',
    ].join('\n');
    document.head.appendChild(st);
  }

  window.toggleSubPresets = function (force) {
    var sub = document.getElementById('mode-subpresets');
    if (!sub) return false;
    var open =
      typeof force === 'boolean' ? force : !sub.classList.contains('open');
    sub.classList.toggle('open', open);
    var cust = document.querySelector('.nav-mode-card[data-preset="personalizado"]');
    if (cust) cust.classList.toggle('is-open', open);
    return open;
  };

  function subPresetsHTML() {
    var cards = SUB_PRESETS.filter(function (id) {
      return preset(id);
    })
      .map(function (id) {
        return cardHTML(id);
      })
      .join('\n');
    cards +=
      '\n<div class="nav-mode-card" data-preset="__novo" role="button" tabindex="0" aria-pressed="false" onclick="selectPreset(\'__novo\',event)">' +
      '<div class="nav-mode-subpreset-new">✏️ Criar do zero</div>' +
      '<div class="nav-mode-card-name">Personalizar cores</div></div>';
    return (
      '<div class="nav-mode-subpresets" id="mode-subpresets">' +
      '<p class="nav-mode-subpresets-title">Temas prontos</p>' +
      '<div class="nav-mode-subpresets-grid">' +
      cards +
      '</div></div>'
    );
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function cardHTML(id) {
    var p = preset(id);
    if (!p) return '';
    var s = p.sistema,
      b = p.bordas,
      t = p.texto,
      d = p.destaque,
      g = p.grafico;
    return [
      '<div class="nav-mode-card" data-preset="' +
        esc(id) +
        '" role="button" tabindex="0" aria-pressed="false" onclick="selectPreset(\'' +
        esc(id) +
        '\',event)">',
      '  <div class="nav-mode-card-head">',
      '    <span class="nav-mode-card-title"><i class="bi ' +
        esc(p.icone || 'bi-palette') +
        '"></i><span>' +
        esc(p.nome) +
        '</span></span>',
      '    <span class="nav-mode-card-badge">Ativo</span>',
      '  </div>',
      '  <div class="nav-mode-card-preview">',
      '    <div class="nmc-pv" style="background:' +
        s.planoDeFundoDoSistema +
        ';border-color:' +
        b.bordaPadrao +
        '">',
      '      <div class="nmc-pv-nav" style="background:' +
        s.planoDeFundoDaNavbar +
        ';border-color:' +
        b.bordaPadrao +
        '">',
      '        <i class="nmc-pv-acc" style="background:' + d.corPrimaria + '"></i>',
      '        <i class="nmc-pv-line" style="background:' + t.textoSecundario + '"></i>',
      '        <i class="nmc-pv-line nmc-pv-line-sm" style="background:' + t.textoFraco + '"></i>',
      '      </div>',
      '      <div class="nmc-pv-row">',
      '        <div class="nmc-pv-card" style="background:' +
        s.planoDeFundoDoCard +
        ';border-color:' +
        b.bordaSuave +
        '">',
      '          <span class="nmc-pv-vbar" style="background:' +
        g.corDaLinha +
        ';height:55%"></span>',
      '          <span class="nmc-pv-vbar" style="background:' +
        g.corDaLinha +
        ';height:85%"></span>',
      '          <span class="nmc-pv-vbar" style="background:' +
        g.corDaLinha +
        ';height:40%"></span>',
      '        </div>',
      '        <div class="nmc-pv-card nmc-pv-card-nest" style="background:' +
        s.planoDeFundoDoCardAninhado +
        ';border-color:' +
        b.bordaSuave +
        '">',
      '          <i class="nmc-pv-acc" style="background:' + d.corClara + '"></i>',
      '          <i class="nmc-pv-line" style="background:' + t.textoSecundario + '"></i>',
      '        </div>',
      '      </div>',
      '    </div>',
      '  </div>',
      '  <div class="nav-mode-card-name">' + esc(p.nome) + '</div>',
      '</div>',
    ].join('\n');
  }

  function activePresetId() {
    /* Prefs primeiro: com preset ativo o <html> tem classe custom-theme,
       mas a paleta deve continuar sendo a do preset (não a nativa). */
    try {
      var prefs = typeof window.getPreferences === 'function' ? window.getPreferences() : {};
      var t = prefs.theme || {};
      if (t.mode === 'custom' && t.custom && t.custom.source === 'preset' && t.custom.presetId) {
        if (preset(t.custom.presetId)) return t.custom.presetId;
      }
    } catch (e) {}
    var html = document.documentElement;
    if (html.classList.contains('custom-theme')) return 'personalizado';
    var tema = html.getAttribute('data-tema');
    if (tema === 'claro' || tema === 'escuro') return tema;
    return null;
  }

  /* Schema (cores) do preset/custom ativo, ou null se modo nativo */
  function activeSchema() {
    try {
      var prefs = typeof window.getPreferences === 'function' ? window.getPreferences() : {};
      var t = prefs.theme || {};
      var c = t.custom;
      if (t.mode === 'custom' && c) {
        if (c.source === 'preset' && c.presetId && preset(c.presetId)) {
          var p = preset(c.presetId);
          return { schema: p, id: c.presetId };
        }
        if (c.schema) return { schema: c.schema, id: c.presetId || null };
      }
    } catch (e) {}
    return null;
  }

  /* Card "Personalizado": preview gerado com as cores ATUAIS do sistema */
  function customCardHTML() {
    var cs = getComputedStyle(document.documentElement);
    var read = function (n) {
      return cs.getPropertyValue(n).trim();
    };
    var sFundo = read('--cor-fundo') || '#f6f8f7';
    var sNav = read('--cor-fundo-navbar') || '#fdfefe';
    var sCard = read('--cor-fundo-card') || '#fdfefe';
    var sCardNest = read('--cor-fundo-card-aninhado') || '#f3f7f5';
    var borda = read('--cor-borda') || 'rgba(29,36,33,0.12)';
    var acc = read('--theme-accent') || read('--cor-primaria') || '#0f9d6e';
    var accClara = read('--cor-acento') || acc;
    var t2 = read('--cor-texto-suave') || '#5f6b66';
    var t3 = read('--cor-texto-fraco') || '#8b9792';
    return [
      '<div class="nav-mode-card" data-preset="personalizado" role="button" tabindex="0" aria-pressed="false" onclick="selectPreset(\'personalizado\',event)">',
      '  <div class="nav-mode-card-head">',
      '    <span class="nav-mode-card-title"><span>Personalizado</span></span>',
      '    <span class="nav-mode-card-badge">Ativo</span>',
      '  </div>',
      '  <div class="nav-mode-card-preview">',
      '    <div class="nmc-pv" style="background:' + sFundo + ';border-color:' + borda + '">',
      '      <div class="nmc-pv-nav" style="background:' + sNav + ';border-color:' + borda + '">',
      '        <i class="nmc-pv-acc" style="background:' + acc + '"></i>',
      '        <i class="nmc-pv-line" style="background:' + t2 + '"></i>',
      '        <i class="nmc-pv-line nmc-pv-line-sm" style="background:' + t3 + '"></i>',
      '      </div>',
      '      <div class="nmc-pv-row">',
      '        <div class="nmc-pv-card" style="background:' +
        sCard +
        ';border-color:' +
        borda +
        '">',
      '          <span class="nmc-pv-vbar" style="background:' + acc + ';height:55%"></span>',
      '          <span class="nmc-pv-vbar" style="background:' + acc + ';height:85%"></span>',
      '          <span class="nmc-pv-vbar" style="background:' + acc + ';height:40%"></span>',
      '        </div>',
      '        <div class="nmc-pv-card nmc-pv-card-nest" style="background:' +
        sCardNest +
        ';border-color:' +
        borda +
        '">',
      '          <i class="nmc-pv-acc" style="background:' + accClara + '"></i>',
      '          <i class="nmc-pv-line" style="background:' + t2 + '"></i>',
      '        </div>',
      '      </div>',
      '    </div>',
      '  </div>',
      '  <div class="nav-mode-card-name">Personalizado</div>',
      '</div>',
    ].join('\n');
  }

  window.renderModePanel = function () {
    var grid = document.getElementById('mode-panel-grid');
    if (!grid) return;
    if (grid.dataset.rendered) {
      window.refreshModePanel();
      return;
    }
    grid.dataset.rendered = '1';
    ensureSubStyles();
    /* O template já traz cards estáticos (no-JS); remove para não duplicar */
    grid.querySelectorAll('.nav-mode-card').forEach(function (c) {
      c.remove();
    });
    var oldCustom = document.getElementById('mode-card-custom');
    if (oldCustom) oldCustom.remove();
    var oldSub = document.getElementById('mode-subpresets');
    if (oldSub) oldSub.remove();
    /* Painel principal: SÓ Claro / Escuro. Personalizado entra depois. */
    ['claro', 'escuro'].forEach(function (id) {
      var wrap = document.createElement('div');
      wrap.innerHTML = cardHTML(id);
      var card = wrap.firstChild;
      if (card) grid.appendChild(card);
    });
    /* Card "Personalizado" entra por último */
    var custWrap = document.createElement('div');
    custWrap.id = 'mode-card-custom';
    grid.appendChild(custWrap);
    /* Sub-lista de temas prontos (Café, Oceano, Pôr-do-sol, ...) + Criar do zero */
    var subWrap = document.createElement('div');
    subWrap.innerHTML = subPresetsHTML();
    if (subWrap.firstChild) grid.appendChild(subWrap.firstChild);
    window.refreshModePanel();
  };

  window.refreshModePanel = function () {
    var grid = document.getElementById('mode-panel-grid');
    if (!grid) return;
    /* Regenera o preview do Personalizado com as cores atuais */
    var custWrap = document.getElementById('mode-card-custom');
    if (custWrap) custWrap.innerHTML = customCardHTML();
    var active = activePresetId();
    grid.querySelectorAll('.nav-mode-card').forEach(function (card) {
      var on = card.getAttribute('data-preset') === active;
      card.classList.toggle('is-active', on);
      card.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    /* Se o ativo é um tema pronto, o Personalizado fica ativo e a sub-lista abre */
    if (SUB_PRESETS.indexOf(active) !== -1) {
      var cust = grid.querySelector('.nav-mode-card[data-preset="personalizado"]');
      if (cust) {
        cust.classList.add('is-active');
        cust.setAttribute('aria-pressed', 'true');
      }
      window.toggleSubPresets(true);
    }
  };

  /* ── Personalizar: começar do vazio (padrão) ou clonar preset existente ── */
  var EMPTY_BASE = {
    accent: '#0f9d6e',
    text: '#e9eeec',
    navbar: '#131917',
    workspace: '#0b0f0e',
    card: '#151b19',
    widgetbar: '#131917',
    chart: '#0f9d6e',
    border: '#33413f',
    dark: true,
  };

  /* Preenche o select "Começar de" do modal com os presets (Clonar: X) */
  window.populatePresetBase = function () {
    var sel = document.getElementById('custom-theme-base');
    if (!sel || sel.dataset.done) return;
    Object.keys(window.AMPLIAGRO_THEMES || {}).forEach(function (id) {
      var p = window.AMPLIAGRO_THEMES[id];
      var o = document.createElement('option');
      o.value = id;
      o.textContent = 'Clonar: ' + p.nome;
      sel.appendChild(o);
    });
    sel.dataset.done = '1';
  };

  /* Aplica a base escolhida (vazio ou clone) nos inputs de cor do modal */
  window.presetBaseChange = function () {
    var sel = document.getElementById('custom-theme-base');
    var id = sel ? sel.value : '';
    var base = EMPTY_BASE;
    if (id && (window.AMPLIAGRO_THEMES || {})[id]) {
      var p = window.AMPLIAGRO_THEMES[id];
      base = {
        accent: p.destaque.corPrimaria,
        text: p.texto.textoPrimario,
        navbar: p.sistema.planoDeFundoDaNavbar,
        workspace: p.sistema.planoDeFundoDoSistema,
        card: p.sistema.planoDeFundoDoCard,
        widgetbar: p.sistema.planoDeFundoDaToolbar,
        chart: p.grafico.corDaLinha,
        border: p.bordas.bordaPadrao,
        dark: !!p.dark,
      };
    }
    var set = function (inputId, v) {
      var el = document.getElementById(inputId);
      if (el && typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v)) el.value = v;
    };
    set('custom-theme-accent', base.accent);
    set('custom-theme-text', base.text);
    set('custom-theme-navbar', base.navbar);
    set('custom-theme-workspace', base.workspace);
    set('custom-theme-card', base.card);
    set('custom-theme-widgetbar', base.widgetbar);
    set('custom-theme-chart', base.chart);
    set('custom-theme-border', base.border);
    var dk = document.getElementById('custom-theme-option-dark');
    if (dk) dk.checked = !!base.dark;
    if (typeof window.applyCustomTheme === 'function') window.applyCustomTheme();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      window.renderModePanel();
      window.populatePresetBase();
      restaurarCustomSeNecessario();
    });
  } else {
    window.renderModePanel();
    window.populatePresetBase();
    restaurarCustomSeNecessario();
  }
})();
