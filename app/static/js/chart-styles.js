/* ═══════════════════════════════════════════════════════════
   AMPLIAGRO — Registro de estilos de gráfico (Chart Lab / 200)
   ─────────────────────────────────────────────────────────────
   Cada categoria (Linha, Área, Barras, Pizza/Donut, Radial,
   Radar, Dispersão, Composto, Hierarquia, Especial, Progresso,
   Matriz) tem um conjunto de variantes. Cada variante gera um
   "config de estilo" que é aplicado sobres  datasets Chart.js,
   lendo sempre os tokens --pal-* via ampliChartPalette().
   ──
   Uso:
     var meta = AmpliChartStyles.variant('linha','suave');
     meta.applyDataset(ds, pal, params);   // decora um dataset
     meta.options(pal, extra);             // escalas/legenda/plugins
   ═══════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';

  function rgbaOf(hex, a) {
    if (!hex) return 'rgba(16,185,129,' + (a == null ? 0.2 : a) + ')';
    var s = String(hex).trim();
    var m = s.match(/^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/);
    var r, g, b;
    if (m) {
      var h = m[1];
      if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      r = parseInt(h.slice(0, 2), 16);
      g = parseInt(h.slice(2, 4), 16);
      b = parseInt(h.slice(4, 6), 16);
    } else {
      var m2 = s.match(/rgba?\(([^)]+)\)/);
      if (m2) {
        var parts = m2[1].split(',');
        r = parseInt(parts[0], 10);
        g = parseInt(parts[1], 10);
        b = parseInt(parts[2], 10);
      }
    }
    if (r === undefined || g === undefined || b === undefined || isNaN(r) || isNaN(g) || isNaN(b)) {
      return 'rgba(16,185,129,' + (a == null ? 0.2 : a) + ')';
    }
    return 'rgba(' + r + ',' + g + ',' + b + ',' + (a == null ? 0.2 : a) + ')';
  }

  function chartPal() {
    if (typeof global.ampliChartPalette === 'function') {
      try {
        return global.ampliChartPalette();
      } catch (e) {}
    }
    var dark = document.documentElement.classList.contains('dark');
    return {
      isDark: dark,
      accent: dark ? '#3ec48f' : '#0f9d6e',
      accentBar: dark ? 'rgba(62,196,143,0.5)' : 'rgba(15,157,110,0.50)',
      accentFill: dark ? 'rgba(62,196,143,0.12)' : 'rgba(15,157,110,0.10)',
      grid: dark ? 'rgba(233,238,236,0.07)' : 'rgba(29,36,33,0.08)',
      gridSoft: dark ? 'rgba(233,238,236,0.035)' : 'rgba(29,36,33,0.04)',
      tick: dark ? '#8b9792' : '#5f6b66',
      pointBorder: dark ? '#151b19' : '#fdfefe',
      chartBg: dark ? '#151b19' : '#fdfefe',
      pie: dark
        ? ['#3ec48f', '#d9b45c', '#4fb5a3', '#60a5fa', '#a78bfa', '#22d3ee', '#a3e635', '#f0a84e']
        : ['#0f9d6e', '#c19a3c', '#2f8f7e', '#3b82f6', '#8b5cf6', '#14b8a6', '#84cc16', '#e08f3c'],
    };
  }

  function seriesColor(pal, idx, fallback) {
    var arr = pal && pal.pie ? pal.pie : [];
    var c = arr[idx % (arr.length || 1)];
    return c || fallback || '#0f9d6e';
  }

  /* ─────────────────────────────────────────────
     VARIANTES — estrutura
     id, label, desc, type (chart.js base),
     applyDataset(ds, pal, params), options(pal, extra)
     ───────────────────────────────────────────── */

  var LINE_CURVES = {
    monotone: { tension: 0.35, stepped: false },
    linear: { tension: 0, stepped: false },
    step: { tension: 0, stepped: true },
    stepBefore: { tension: 0, stepped: 'before' },
    stepAfter: { tension: 0, stepped: 'after' },
    basis: { tension: 0.4, stepped: false },
    natural: { tension: 0.45, stepped: false },
  };

  function lineBase(ds, pal, curve, fill, dashed, radius) {
    if (!pal) pal = chartPal();
    var c = curve || LINE_CURVES.monotone;
    if (ds.tension === undefined) ds.tension = c.tension;
    if (ds.stepped === undefined) ds.stepped = c.stepped;
    if (fill !== undefined && ds.fill === undefined) ds.fill = fill;
    if (ds.borderWidth === undefined) ds.borderWidth = 2;
    if (dashed && ds.borderDash === undefined)
      ds.borderDash = Array.isArray(dashed) ? dashed : [5, 5];
    if (radius !== undefined && ds.pointRadius === undefined) ds.pointRadius = radius;
    if (ds.pointBackgroundColor === undefined)
      ds.pointBackgroundColor = ds.borderColor || pal.accent;
    if (ds.pointBorderColor === undefined) ds.pointBorderColor = pal.pointBorder;
    ds.showLine = true;
    return ds;
  }

  function barBase(ds, pal, stacked, horizontal, radius) {
    if (!pal) pal = chartPal();
    if (ds.borderRadius === undefined) ds.borderRadius = radius || 3;
    if (ds.borderWidth === undefined) ds.borderWidth = 1;
    if (ds.borderColor === undefined) ds.borderColor = ds.backgroundColor;
    if (stacked && ds.stack === undefined) ds.stack = 'main';
    return ds;
  }

  var STYLES = {
    /* ── LINHA ─────────────────────────────── */
    linha: {
      label: 'Linha',
      icon: 'bi-graph-up',
      variants: {
        suave: {
          label: 'Suave',
          desc: 'Curva suave, sem pontos',
          type: 'line',
          curveType: 'monotone',
          metaLine: false,
        },
        reta: {
          label: 'Reta',
          desc: 'Segmentos retos entre pontos',
          type: 'line',
          curveType: 'linear',
        },
        passos: { label: 'Em passos', desc: 'Degraus (step)', type: 'line', stepped: true },
        passoAntes: {
          label: 'Passo antes',
          desc: 'Degraus antes do próximo',
          type: 'line',
          stepped: 'before',
        },
        pontilhada: { label: 'Pontilhada', desc: 'Traço pontilhado', type: 'line' },
        tracejada: { label: 'Tracejada', desc: 'Traço tracejado', type: 'line' },
        comPontos: { label: 'Com pontos', desc: 'Pontos aplicados', type: 'line' },
        comparativa: {
          label: 'Comparativa',
          desc: 'Multi-série com legenda',
          type: 'line',
          legend: true,
        },
        gradiente: {
          label: 'Com gradiente',
          desc: 'Preenchimento com gradiente',
          type: 'line',
          gradient: true,
          fill: 'origin',
        },
      },
    },

    /* ── ÁREA ──────────────────────────────── */
    area: {
      label: 'Área',
      icon: 'bi-activity',
      variants: {
        basica: { label: 'Básica', desc: 'Área sólida translúcida', type: 'line', fill: 'origin' },
        empilhada: {
          label: 'Empilhada',
          desc: 'Séries empilhadas',
          type: 'line',
          fill: 'origin',
          stacked: true,
        },
        comPontos: { label: 'Com pontos', desc: 'Área com pontos', type: 'line', fill: 'origin' },
        comGrad: {
          label: 'Com gradiente',
          desc: 'Área com gradiente',
          type: 'line',
          fill: 'origin',
          gradient: true,
        },
        comparativa: {
          label: 'Comparativa',
          desc: 'Áreas sobrepostas',
          type: 'line',
          fill: 'origin',
          legend: true,
        },
      },
    },

    /* ── BARRAS ────────────────────────────── */
    barras: {
      label: 'Barras',
      icon: 'bi-bar-chart',
      variants: {
        vertical: { label: 'Vertical', desc: 'Colunas', type: 'bar' },
        horizontal: {
          label: 'Horizontal',
          desc: 'Barras horizontais',
          type: 'bar',
          horizontal: true,
        },
        empilhada: { label: 'Empilhada', desc: 'Colunas empilhadas', type: 'bar', stacked: true },
        agrupada: { label: 'Agrupada', desc: 'Multi-série lado a lado', type: 'bar', legend: true },
        arredondada: { label: 'Arredondada', desc: 'Barras com cantos redondos', type: 'bar' },
        pontilhada: {
          label: 'Borda pontilhada',
          desc: 'Colunas com borda pontilhada',
          type: 'bar',
        },
        tracejada: { label: 'Borda tracejada', desc: 'Colunas com borda tracejada', type: 'bar' },
        comMeta: {
          label: 'Com Meta',
          desc: 'Colunas com linha de meta',
          type: 'bar',
          metaLine: true,
        },
      },
    },

    /* ── PIZZA / DONUT ─────────────────────── */
    pizza: {
      label: 'Pizza',
      icon: 'bi-pie-chart',
      variants: {
        pizza: { label: 'Pizza', desc: 'Torta clássica', type: 'pie' },
        donut: { label: 'Donut', desc: 'Rosca com furo', type: 'doughnut', cutout: '62%' },
        semiDonut: {
          label: 'Semi-donut',
          desc: 'Meia rosca',
          type: 'doughnut',
          cutout: '62%',
          rotation: -90,
          circumference: 180,
        },
        comCentro: {
          label: 'Com total no centro',
          desc: 'Rosca com valor central',
          type: 'doughnut',
          cutout: '70%',
          centerText: true,
        },
        pontilhada: { label: 'Borda pontilhada', desc: 'Fatias pontilhadas', type: 'pie' },
        tracejada: { label: 'Borda tracejada', desc: 'Fatias tracejadas', type: 'pie' },
      },
    },

    /* ── RADIAL ────────────────────────────── */
    radial: {
      label: 'Radial',
      icon: 'bi-bullseye',
      variants: {
        polar: { label: 'Polar', desc: 'Barras radiais', type: 'polarArea' },
        gauge: {
          label: 'Gauge',
          desc: 'Medidor de 0-100%',
          type: 'doughnut',
          gauge: true,
          cutout: '75%',
          rotation: -90,
          circumference: 180,
        },
        anelProg: {
          label: 'Anel de progresso',
          desc: 'Rosca percentual',
          type: 'doughnut',
          gauge: true,
          cutout: '72%',
        },
      },
    },

    /* ── RADAR ─────────────────────────────── */
    radar: {
      label: 'Radar',
      icon: 'bi-diagram-3',
      variants: {
        basico: { label: 'Básico', desc: 'Rede simples', type: 'radar', fill: false },
        preenchido: { label: 'Preenchido', desc: 'Área preenchida', type: 'radar', fill: true },
        comPontos: { label: 'Com pontos', desc: 'Marcadores visíveis', type: 'radar', fill: true },
        comparativo: {
          label: 'Comparativo',
          desc: 'Multi-série',
          type: 'radar',
          fill: true,
          legend: true,
        },
      },
    },

    /* ── DISPERSÃO ─────────────────────────── */
    dispersao: {
      label: 'Dispersão',
      icon: 'bi-dot',
      variants: {
        scatter: { label: 'Pontos', desc: 'Pontos (x, y)', type: 'scatter' },
        bolhas: { label: 'Bolhas', desc: 'Tamanho variável', type: 'bubble' },
        tendencia: {
          label: 'Com tendência',
          desc: 'Pontos + linha de regressão',
          type: 'scatter',
          trendLine: true,
        },
      },
    },

    /* ── COMPOSTO ──────────────────────────── */
    composto: {
      label: 'Composto',
      icon: 'bi-layers',
      variants: {
        barraLinha: {
          label: 'Barras + linha',
          desc: 'Colunas com overlay em linha',
          type: 'bar',
          mixed: true,
          legend: true,
        },
        areaBarra: {
          label: 'Área + barras',
          desc: 'Área com barras',
          type: 'bar',
          mixed: true,
          legend: true,
        },
        duasEscalas: {
          label: 'Duas escalas',
          desc: 'Eixo Y duplo (R$ vs unid.)',
          type: 'line',
          twoAxes: true,
          legend: true,
        },
      },
    },

    /* ── HIERARQUIA ────────────────────────── */
    hierarquia: {
      label: 'Hierarquia',
      icon: 'bi-flow',
      variants: {
        donutNested: {
          label: 'Donut aninhado',
          desc: 'Níveis concêntricos',
          type: 'doughnut',
          nested: true,
        },
        treemap: { label: 'Treemap', desc: 'Retângulos por peso', type: 'bar', treeMap: true },
      },
    },

    /* ── ESPECIAL ──────────────────────────── */
    especial: {
      label: 'Especial',
      icon: 'bi-stars',
      variants: {
        funnel: { label: 'Funil', desc: 'Progressão decrescente', type: 'bar', funnel: true },
        pareto: {
          label: 'Pareto',
          desc: 'Barras + acumulado',
          type: 'bar',
          pareto: true,
          legend: true,
        },
        waterfall: {
          label: 'Cascata',
          desc: 'Acumulado encadeado',
          type: 'bar',
          waterfall: true,
          legend: true,
        },
      },
    },

    /* ── PROGRESSO ─────────────────────────── */
    progresso: {
      label: 'Progresso',
      icon: 'bi-hourglass-split',
      variants: {
        barraProgr: {
          label: 'Barra de progresso',
          desc: 'Percentual horizontal',
          type: 'bar',
          progress: true,
        },
        roscaProgr: {
          label: 'Rosca de progresso',
          desc: 'Percentual circular',
          type: 'doughnut',
          gauge: true,
          cutout: '78%',
        },
        etapas: { label: 'Etapas', desc: 'Passos marcados', type: 'bar', steps: true },
      },
    },

    /* ── MATRIZ ────────────────────────────── */
    matriz: {
      label: 'Matriz',
      icon: 'bi-grid',
      variants: {
        heatmap: { label: 'Heatmap', desc: 'Cores por célula', type: 'bar', heatmap: true },
        comparada: { label: 'Comparada', desc: 'Métricas em grade', type: 'radar', legend: true },
      },
    },

    /* ── CARTÃO KPI ────────────────────────── */
    cartao: {
      label: 'Cartão',
      icon: 'bi-card-text',
      variants: {
        basico: { label: 'Básico', desc: 'Resumo com meta', type: 'html' },
      },
    },

    /* ── PLANILHA ──────────────────────────── */
    planilha: {
      label: 'Planilha',
      icon: 'bi-table',
      variants: {
        anos: { label: 'Por Anos', desc: 'Guias de Anos, Linhas de Fatores', type: 'html' },
        fatores: { label: 'Por Fatores', desc: 'Guias de Fatores, Linhas de Anos', type: 'html' },
        lista: { label: 'Lista', desc: 'Dados simples em tabela', type: 'html' },
      },
    },
  };

  /* ─────────────────────────────────────────────
     HELPERS DE APLICAÇÃO (decoram datasets/options)
     ───────────────────────────────────────────── */

  function applyLineVariant(ds, pal, v, params) {
    var curve = v.stepped
      ? { tension: 0, stepped: v.stepped }
      : v.curveType
        ? LINE_CURVES[v.curveType]
        : LINE_CURVES.monotone;
    var dashed = null;
    if (v.borderDash) dashed = v.borderDash;
    else if (v.id === 'pontilhada') dashed = [2, 4];
    else if (v.id === 'tracejada') dashed = [6, 4];
    var fill = v.fill;
    if (v.id === 'gradiente' && ds._noGradientFill) fill = false;
    lineBase(
      ds,
      pal,
      curve,
      fill,
      dashed,
      v.id === 'comPontos' ? 3 : params && params.nopoints ? 0 : 1.5
    );
    if (v.gradient) ds._gradientLine = true;
    if (params && params.color) {
      if (ds.borderColor === undefined) ds.borderColor = params.color;
      if (ds.pointBackgroundColor === undefined) ds.pointBackgroundColor = params.color;
      // Destaque borda + preenchimento no preview: linha ganha área translúcida
      if (params.highlight && ds.fill !== false) {
        ds.fill = 'origin';
        if (ds.backgroundColor === undefined) ds.backgroundColor = rgbaOf(params.color, 0.14);
      }
    }
    if (v.id === 'comparativa') ds._asSeparateSeries = true;
    return ds;
  }

  function applyBarVariant(ds, pal, v, params) {
    barBase(ds, pal, v.stacked, v.horizontal, v.id === 'arredondada' ? 6 : 3);
    if (v.horizontal && ds.indexAxis === undefined) {
      ds.$horizontal = true;
    }
    if (params && params.color) {
      if (ds.backgroundColor === undefined || ds.backgroundColor === pal.accentBar)
        ds.backgroundColor = rgbaOf(params.color, pal.isDark ? 0.75 : 0.7);
      if (ds.borderColor === undefined) ds.borderColor = params.color;
      if (params.highlight && ds.borderWidth === 1) ds.borderWidth = 1.5;
    }
    if (v.id === 'pontilhada' || v.id === 'tracejada') {
      ds.borderWidth = 2;
      ds.borderDash = v.id === 'pontilhada' ? [2, 4] : [6, 4];
      ds.backgroundColor = rgbaOf(ds.borderColor || pal.accent, 0.15); // Lighter fill to highlight border
    }
    if (v.funnel) ds._funnel = true;
    if (v.pareto) ds._pareto = true;
    if (v.waterfall) ds._waterfall = true;
    return ds;
  }

  function applyPieVariant(ds, pal, v, params) {
    if (ds.borderColor === undefined) ds.borderColor = pal.isDark ? '#000000' : '#fbfffe';
    if (ds.borderWidth === undefined) ds.borderWidth = 1;
    if (params && params.highlight && params.color) ds.borderColor = params.color;
    if (v.id === 'semiDonut' || v.id === 'gauge') ds._circumference = v.circumference;
    if (v.id === 'pontilhada' || v.id === 'tracejada') {
      ds.borderWidth = 2;
      ds.borderDash = v.id === 'pontilhada' ? [2, 4] : [6, 4];
      ds.borderColor = pal.accent;
    }
    return ds;
  }

  function applyRadarVariant(ds, pal, v, params) {
    if (ds.fill === undefined) ds.fill = !!v.fill;
    if (ds.borderWidth === undefined) ds.borderWidth = 2;
    if (ds.pointRadius === undefined) ds.pointRadius = v.id === 'comPontos' ? 3 : 1.5;
    if (v.id === 'basico') ds.backgroundColor = 'transparent';
    return ds;
  }

  function applyScatterVariant(ds, pal, v, params) {
    if (ds.pointRadius === undefined) ds.pointRadius = 4;
    if (ds.pointHoverRadius === undefined) ds.pointHoverRadius = 6;
    if (v.id === 'bolhas') ds.pointRadius = 6;
    if (v.trendLine && ds.tension === undefined) ds.tension = 0;
    return ds;
  }

  /* Converte hex -> gradiente vertical no contexto do canvas */
  function buildVerticalGradient(canvas, color, from, to) {
    var ctx = canvas && canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx || !ctx.createLinearGradient) return rgbaOf(color, from);
    var w = canvas.width || 300,
      h = canvas.height || 150;
    var grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, rgbaOf(color, from == null ? 0.35 : from));
    grad.addColorStop(1, rgbaOf(color, to == null ? 0.02 : to));
    return grad;
  }

  /* ─────────────────────────────────────────────
     API PÚBLICA
     ───────────────────────────────────────────── */

  var AmpliChartStyles = {
    categories: STYLES,

    category: function (catId) {
      return STYLES[catId] || null;
    },

    categoriesList: function () {
      var out = [];
      Object.keys(STYLES).forEach(function (k) {
        out.push({ id: k, label: STYLES[k].label, icon: STYLES[k].icon });
      });
      return out;
    },

    variantsList: function (catId) {
      var cat = STYLES[catId];
      if (!cat) return [];
      var out = [];
      Object.keys(cat.variants).forEach(function (k) {
        out.push({
          id: k,
          label: cat.variants[k].label,
          desc: cat.variants[k].desc,
          type: cat.variants[k].type,
        });
      });
      return out;
    },

    variant: function (catId, variantId) {
      var cat = STYLES[catId];
      if (!cat || !cat.variants[variantId]) return null;
      return {
        category: catId,
        label: cat.variants[variantId].label,
        desc: cat.variants[variantId].desc,
        type: cat.variants[variantId].type,
        fill: cat.variants[variantId].fill,
        stacked: cat.variants[variantId].stacked,
        horizontal: cat.variants[variantId].horizontal,
        metaLine: cat.variants[variantId].metaLine,
        legend: cat.variants[variantId].legend,
        gradient: cat.variants[variantId].gradient,
        mixed: cat.variants[variantId].mixed,
        twoAxes: cat.variants[variantId].twoAxes,
        gauge: cat.variants[variantId].gauge,
        cutout: cat.variants[variantId].cutout,
        centerText: cat.variants[variantId].centerText,
        circumference: cat.variants[variantId].circumference,
      };
    },

    /* Decora um dataset individual com a variante escolhida */
    applyDataset: function (ds, catId, variantId, params) {
      if (!ds) return ds;
      var pal = chartPal();
      var vRaw = STYLES[catId] && STYLES[catId].variants[variantId];
      if (!vRaw) {
        if (params && params.color && ds.borderColor === undefined) ds.borderColor = params.color;
        return ds;
      }
      var v = Object.assign({ id: variantId }, vRaw);
      var baseType = v.type;
      if (baseType === 'line') applyLineVariant(ds, pal, v, params);
      else if (baseType === 'bar') applyBarVariant(ds, pal, v, params);
      else if (baseType === 'pie' || baseType === 'doughnut' || baseType === 'polarArea')
        applyPieVariant(ds, pal, v, params);
      else if (baseType === 'radar') applyRadarVariant(ds, pal, v, params);
      else if (baseType === 'scatter' || baseType === 'bubble')
        applyScatterVariant(ds, pal, v, params);
      if (params && params.color) {
        if (
          ds.backgroundColor === undefined ||
          ds.backgroundColor === pal.accentFill ||
          ds.backgroundColor === pal.accentBar
        ) {
          ds.backgroundColor = rgbaOf(params.color, 0.25);
        }
      }
      return ds;
    },

    /* Recolore um dataset (usado pelo comparativo para trocar a cor da série) */
    recolor: function (ds, color, isBar) {
      if (!ds || !color) return ds;
      ds.borderColor = color;
      if (ds.pointBackgroundColor) ds.pointBackgroundColor = color;
      if (isBar || ds._barStyle) ds.backgroundColor = rgbaOf(color, 0.7);
      else if (ds.fill) ds.backgroundColor = rgbaOf(color, 0.18);
      return ds;
    },

    /* Monta escalas/legenda conforme categoria+variante (parciais, p/ merge) */
    options: function (catId, variantId, pal, extra) {
      pal = pal || chartPal();
      var v = STYLES[catId] && STYLES[catId].variants[variantId];
      var o = { plugins: {}, scales: {} };
      var showLegend = (v && v.legend) || (extra && extra.legend) || false;
      if (showLegend) {
        o.plugins.legend = {
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
      } else {
        o.plugins.legend = { display: false };
      }
      if (v && v.horizontal) {
        o.indexAxis = 'y';
      }
      if (v && v.stacked) {
        o.scales.x = {
          stacked: true,
          grid: { display: false },
          border: { display: false },
          ticks: { color: pal.tick, font: { size: 7 }, padding: 1 },
        };
        o.scales.y = {
          stacked: true,
          grid: { display: false },
          border: { display: false },
          ticks: { color: pal.tick, font: { size: 7 }, padding: 1 },
        };
      }
      if (v && v.twoAxes) {
        o.scales.y = {
          grid: { display: false },
          border: { display: false },
          ticks: { color: pal.tick, font: { size: 7 }, padding: 1 },
          position: 'left',
        };
        o.scales.y1 = {
          grid: { display: false },
          border: { display: false },
          position: 'right',
          ticks: { color: pal.tick, font: { size: 7 }, padding: 1 },
        };
      }
      /* Left-to-right animation for line, area, bar charts */
      var animTypes = ['line', 'bar', 'scatter', 'bubble'];
      var chartType = v ? v.type : null;
      if (animTypes.indexOf(chartType) >= 0) {
        o.animation = {
          duration: 1200,
          easing: 'easeOutQuart',
        };
      }
      return o;
    },

    /* Cutout / rotação para donut/gauge */
    cutout: function (catId, variantId) {
      var v = STYLES[catId] && STYLES[catId].variants[variantId];
      if (!v) return undefined;
      if (v.cutout) return v.cutout;
      if (v.type === 'doughnut') return v.id === 'donut' || v.id === 'comCentro' ? '62%' : '68%';
      return undefined;
    },

    /* Rotação (radial) */
    rotation: function (catId, variantId) {
      var v = STYLES[catId] && STYLES[catId].variants[variantId];
      if (v && v.rotation != null) return v.rotation;
      if (v && v.id === 'gauge') return -90;
      return undefined;
    },

    circumference: function (catId, variantId) {
      var v = STYLES[catId] && STYLES[catId].variants[variantId];
      if (v && v.circumference != null) return v.circumference;
      return undefined;
    },

    /* Gradiente vertical aplicado como backgroundColor scriptable */
    makeGradient: function (canvas, color, from, to) {
      return buildVerticalGradient(canvas, color, from, to);
    },
  };

  // Atribui o id automaticamente para cada variante com base na sua chave
  Object.keys(STYLES).forEach(function (catKey) {
    Object.keys(STYLES[catKey].variants).forEach(function (varKey) {
      STYLES[catKey].variants[varKey].id = varKey;
    });
  });

  global.AmpliChartStyles = AmpliChartStyles;
})(window);

/* ═══════════════════════════════════════════════════════════
   Plugin desabilitado — linhas sempre visíveis
   ═══════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';
  if (typeof global.Chart !== 'function') return;
  global.Chart.register({
    id: 'ampliagroLeftToRight',
    beforeDatasetsDraw: function () {},
    afterDatasetsDraw: function () {},
  });
})(window);

/* ═══════════════════════════════════════════════════════════
   Plano de fundo — plugin minimalista p/ "linha de meta" e
   faixa de referência, equivalente ao ReferenceLine/ReferenceArea
   do catálogo (Chart.js não traz nativo).
   ═══════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';
  if (typeof global.Chart !== 'function') return;

  var metaLines = [];

  var referencePlugin = {
    id: 'ampliagroReference',
    beforeDatasetsDraw: function (chart) {
      metaLines =
        (chart.options.plugins &&
          chart.options.plugins.ampliReference &&
          chart.options.plugins.ampliReference.metaLines) ||
        [];
    },
    afterDatasetsDraw: function (chart) {
      if (!metaLines.length) return;
      var ctx = chart.ctx,
        area = chart.chartArea;
      var yScale = chart.scales && chart.scales.y;
      if (!yScale) return;
      metaLines.forEach(function (m) {
        var y = yScale.getPixelForValue(m.value);
        if (isNaN(y) || y < area.top || y > area.bottom) return;
        ctx.save();
        ctx.strokeStyle = m.color || '#d93a3a';
        ctx.setLineDash([6, 4]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(area.left, y);
        ctx.lineTo(area.right, y);
        ctx.stroke();
        ctx.restore();
        if (m.label) {
          ctx.save();
          ctx.font = '8px system-ui, sans-serif';
          ctx.fillStyle = m.color || '#d93a3a';
          ctx.fillText(m.label, area.left + 3, y - 3);
          ctx.restore();
        }
      });
      metaLines = [];
    },
  };

  try {
    // Chart.js 4.x uses Chart.register() instead of Chart.plugins.register()
    if (typeof global.Chart.register === 'function') {
      global.Chart.register(referencePlugin);
    } else if (typeof global.Chart.plugins?.register === 'function') {
      // Fallback for Chart.js 3.x
      global.Chart.plugins.register(referencePlugin);
    }
  } catch (e) {}
})(window);

/* ═══════════════════════════════════════════════════════════
   Plugin Crosshair — linha vertical + badges de valor
   no hover, estilo Recharts.
   ═══════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';
  if (typeof global.Chart !== 'function') return;

  /* Polyfill roundRect para browsers antigos */
  if (
    typeof CanvasRenderingContext2D !== 'undefined' &&
    !CanvasRenderingContext2D.prototype.roundRect
  ) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
      if (typeof r === 'number') r = [r, r, r, r];
      this.moveTo(x + r[0], y);
      this.lineTo(x + w - r[1], y);
      this.quadraticCurveTo(x + w, y, x + w, y + r[1]);
      this.lineTo(x + w, y + h - r[2]);
      this.quadraticCurveTo(x + w, y + h, x + w - r[2], y + h);
      this.lineTo(x + r[3], y + h);
      this.quadraticCurveTo(x, y + h, x, y + h - r[3]);
      this.lineTo(x, y + r[0]);
      this.quadraticCurveTo(x, y, x + r[0], y);
      this.closePath();
    };
  }

  function getCrosshairMeta(chart) {
    if (!chart._crosshair) chart._crosshair = { active: false, x: 0, index: -1 };
    return chart._crosshair;
  }

  var crosshairPlugin = {
    id: 'ampliagroCrosshair',

    afterEvent: function (chart, args) {
      var evt = args.event;
      var meta = getCrosshairMeta(chart);
      var area = chart.chartArea;
      if (!area) return;

      if (
        evt.type === 'mouseout' ||
        evt.x < area.left ||
        evt.x > area.right ||
        evt.y < area.top ||
        evt.y > area.bottom
      ) {
        meta.active = false;
        meta.index = -1;
        chart.draw();
        return;
      }

      var points = chart.getElementsAtEventForMode(
        { x: evt.x, y: evt.y, native: true },
        'index',
        { intersect: false },
        false
      );
      if (points && points.length) {
        meta.active = true;
        meta.index = points[0].index;
        meta.x = chart.scales.x.getPixelForValue(points[0].index);
        chart.draw();
      }
    },

    afterDatasetsDraw: function (chart) {
      var meta = getCrosshairMeta(chart);
      if (!meta.active || meta.index < 0) return;
      var ctx = chart.ctx;
      var area = chart.chartArea;
      var x = meta.x;

      ctx.save();

      /* Linha vertical tracejada */
      ctx.strokeStyle = 'rgba(128,128,128,0.35)';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(x, area.top);
      ctx.lineTo(x, area.bottom);
      ctx.stroke();
      ctx.setLineDash([]);

      /* Pontos de interseção nas linhas */
      chart.data.datasets.forEach(function (ds, dsIdx) {
        var point = chart.getDatasetMeta(dsIdx).data[meta.index];
        if (!point) return;
        var py = point.y;
        var color = ds.borderColor || '#888';

        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, py, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.arc(x, py, 1.5, 0, Math.PI * 2);
        ctx.fill();
      });

      /* Badges de valor no topo */
      var badgeY = area.top - 2;
      var badges = [];
      chart.data.datasets.forEach(function (ds, dsIdx) {
        if (ds.hidden) return;
        var pointMeta = chart.getDatasetMeta(dsIdx).data[meta.index];
        if (!pointMeta) return;
        var val = ds.data[meta.index];
        if (val == null) return;
        var color = ds.borderColor || '#888';
        var formatted =
          typeof val === 'number' ? val.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) : val;
        badges.push({ text: formatted, color: color });
      });

      if (badges.length) {
        ctx.font = 'bold 8px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        var gap = 4;
        var totalW = 0;
        var measured = badges.map(function (b) {
          var tw = ctx.measureText(b.text).width + 8;
          totalW += tw;
          return { w: tw, text: b.text, color: b.color };
        });
        totalW += gap * (measured.length - 1);
        var startX = Math.max(area.left + 2, x - totalW / 2);
        if (startX + totalW > area.right - 2) startX = area.right - 2 - totalW;

        measured.forEach(function (b) {
          ctx.fillStyle = b.color;
          ctx.globalAlpha = 0.92;
          var rx = startX;
          var ry = badgeY - 14;
          ctx.beginPath();
          ctx.roundRect(rx, ry, b.w, 14, 3);
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.fillStyle = '#fff';
          ctx.fillText(b.text, rx + b.w / 2, ry + 11);
          startX += b.w + gap;
        });
      }

      /* Label do mês abaixo */
      var label = chart.data.labels[meta.index];
      if (label) {
        ctx.font = '9px system-ui, -apple-system, sans-serif';
        ctx.fillStyle = 'rgba(128,128,128,0.85)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(label, x, area.bottom + 3);
      }

      ctx.restore();
    },
  };

  try {
    if (typeof global.Chart.register === 'function') {
      global.Chart.register(crosshairPlugin);
    }
  } catch (e) {}
})(window);
