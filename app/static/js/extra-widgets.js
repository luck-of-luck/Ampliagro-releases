/* ═══════════════════════════════════════════════════════════
   AMPLIAGRO — Widgets extras (IoT + IA + informações)
   Registra 19 widgets no painel sem tocar no index.html:
     • merge em WIDGET_TYPES (tamanho/título/ícone)
     • merge em WIDGET_CATALOG (grupos iot/ia + listas/tabelas/charts)
     • envolve window.getWidgetSpecificContent (só assume quando o
       conteúdo original volta placeholder)
   Dados: busca lazy com cache de 60s nas APIs existentes.
   ═══════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ── util ── */
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function fmtN(v, d) {
    if (v == null || v === '') return '—';
    return Number(v).toLocaleString('pt-BR', { maximumFractionDigits: d == null ? 1 : d });
  }
  function fmtMoney(v) {
    if (v == null || v === '') return '—';
    return Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
  }
  function fmtDT(v) {
    if (!v) return '—';
    try {
      var dt = new Date(v);
      return dt.toLocaleDateString('pt-BR') + ' ' + dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return String(v).slice(0, 16).replace('T', ' ');
    }
  }
  function rows(j) {
    if (!j) return [];
    if (Array.isArray(j)) return j;
    if (Array.isArray(j.results)) return j.results;
    if (Array.isArray(j.data)) return j.data;
    if (Array.isArray(j.artefatos)) return j.artefatos;
    return [];
  }

  var _cache = {};
  function jget(url, ttl) {
    var now = Date.now();
    var hit = _cache[url];
    if (hit && now - hit.t < (ttl || 60000)) return Promise.resolve(hit.d);
    var f = window.fetchWithTimeout || window.fetch;
    return f(url, { credentials: 'same-origin' }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (d) {
      _cache[url] = { t: now, d: d };
      return d;
    });
  }

  function shell(id, titulo) {
    return '<div class="p-2 h-full flex flex-col min-h-0"><div class="text-xs font-medium text-slate-500 mb-1">' +
      esc(titulo) + '</div><div id="xw-' + id + '" class="flex-1 min-h-0 overflow-auto">' +
      '<p class="text-xs text-slate-400 p-2">Carregando…</p></div></div>';
  }
  var _loading = {};
  function fill(id, promiseFn) {
    if (_loading[id]) return;
    _loading[id] = true;
    setTimeout(function () {
      var el = document.getElementById('xw-' + id);
      if (!el) {
        _loading[id] = false;
        return;
      }
      promiseFn().then(function (html) {
        var el2 = document.getElementById('xw-' + id);
        if (el2) el2.innerHTML = html;
        _loading[id] = false;
      }).catch(function () {
        var el3 = document.getElementById('xw-' + id);
        if (el3) el3.innerHTML = '<p class="text-xs text-slate-400 p-2">Sem dados.</p>';
        _loading[id] = false;
      });
    }, 30);
  }

  function dot(cor) {
    return '<span class="inline-block w-1.5 h-1.5 rounded-full ' + cor + '"></span>';
  }
  function statusDot(s) {
    s = String(s || '').toLowerCase();
    if (s === 'ack' || s === 'enviado' || s === 'ativo' || s === 'ativa' || s === 'concluido') return dot('bg-theme-ok');
    if (s === 'erro' || s === 'vencida' || s === 'inativo') return dot('bg-theme-error');
    return dot('bg-theme-alert');
  }

  /* Tabela genérica a partir de JSON */
  function genTable(list, cols, emptyMsg) {
    if (!list.length) return '<p class="text-xs text-slate-400 p-2">' + esc(emptyMsg || 'Nenhum dado') + '</p>';
    var h = '<div class="overflow-auto h-full text-xs"><table class="w-full"><thead><tr class="border-b text-[10px]">';
    cols.forEach(function (c) {
      h += '<th class="py-1 px-1 text-slate-400 font-medium ' + (c.num ? 'text-right' : 'text-left') + '">' + esc(c.label) + '</th>';
    });
    h += '</tr></thead><tbody>';
    list.slice(0, 20).forEach(function (r) {
      h += '<tr class="border-b border-slate-100 dark:border-slate-800">';
      cols.forEach(function (c) {
        var v = typeof c.get === 'function' ? c.get(r) : r[c.key];
        h += '<td class="py-0.5 px-1 ' + (c.num ? 'text-right' : '') + '">' + v + '</td>';
      });
      h += '</tr>';
    });
    return h + '</tbody></table></div>';
  }

  /* ── builders IoT ── */
  function bKpiDevices() {
    fill('kpi-iot-devices', function () {
      return Promise.all([
        jget('/api/iot/devices/').catch(function () { return []; }),
        jget('/api/iot/gateways/').catch(function () { return []; }),
      ]).then(function (r) {
        var devs = rows(r[0]);
        var at = devs.filter(function (x) { return x.ativo; }).length;
        var bat = devs.filter(function (x) { return x.bateria_pct != null; });
        var batMin = bat.length ? Math.min.apply(null, bat.map(function (x) { return x.bateria_pct; })) : null;
        return '<div class="space-y-2 p-2 text-center"><i class="bi bi-cpu text-2xl text-theme-accent"></i>' +
          '<p class="text-xl font-bold">' + devs.length + ' devices</p>' +
          '<div class="text-xs text-slate-400">' + at + ' ativos • ' + rows(r[1]).length + ' gateways' +
          (batMin != null ? ' • bat min ' + batMin + '%' : '') + '</div></div>';
      });
    });
    return shell('kpi-iot-devices', 'Dispositivos IoT');
  }
  function bKpiAlertas() {
    fill('kpi-iot-alertas', function () {
      return jget('/api/iot/alertas/').then(function (j) {
        var all = rows(j);
        var open = all.filter(function (a) { return !a.resolvido; });
        return '<div class="space-y-2 p-2 text-center"><i class="bi bi-broadcast text-2xl ' +
          (open.length ? 'text-theme-error' : 'text-theme-ok') + '"></i>' +
          '<p class="text-xl font-bold">' + open.length + ' abertos</p>' +
          '<div class="text-xs text-slate-400">de ' + all.length + ' alertas de telemetria</div></div>';
      });
    });
    return shell('kpi-iot-alertas', 'Alertas IoT');
  }
  function bKpiFontes() {
    fill('kpi-iot-fontes', function () {
      return jget('/api/iot/fontes-externas/').then(function (j) {
        var all = rows(j);
        var at = all.filter(function (f) { return f.ativa; });
        var tipos = at.map(function (f) { return esc(f.tipo || f.nome); }).slice(0, 3).join(' • ');
        return '<div class="space-y-2 p-2 text-center"><i class="bi bi-cloud-arrow-down text-2xl text-theme-accent"></i>' +
          '<p class="text-xl font-bold">' + at.length + ' ativas</p>' +
          '<div class="text-xs text-slate-400">' + (tipos || 'INMET • NASA • Open-Meteo') + '</div></div>';
      });
    });
    return shell('kpi-iot-fontes', 'Fontes Externas');
  }
  function bTableLeituras() {
    fill('table-iot-leituras', function () {
      return jget('/api/iot/telemetry/?limit=12').then(function (j) {
        var list = j.data || rows(j);
        return genTable(list, [
          { label: 'Hora', get: function (r) { return fmtDT(r.timestamp); } },
          { label: 'Device', get: function (r) { return esc(r.device_nome || r.device || '—'); } },
          { label: 'Métrica', get: function (r) { return esc(r.metric); } },
          { label: 'Valor', num: true, get: function (r) { return '<span class="font-semibold">' + fmtN(r.value, 2) + ' ' + esc(r.unit || '') + '</span>'; } },
        ], 'Sem leituras — conecte um device ou aguarde o push.');
      });
    });
    return shell('table-iot-leituras', 'Últimas Leituras');
  }
  function bListComandos() {
    fill('list-iot-comandos', function () {
      return jget('/api/iot/comandos/').then(function (j) {
        var list = rows(j);
        if (!list.length) return '<p class="text-slate-400 py-2 text-center text-xs">Nenhum comando</p>';
        return '<div class="text-xs p-1 overflow-auto h-full">' + list.slice(0, 10).map(function (c) {
          return '<div class="flex items-center gap-2 py-1 border-b border-slate-100 dark:border-slate-800 last:border-0">' +
            statusDot(c.status) +
            '<div class="flex-1 min-w-0"><div class="font-medium truncate">' + esc(c.comando) + '</div>' +
            '<div class="text-slate-400 truncate">' + fmtDT(c.criado_em) + (c.ultimo_erro ? ' • ' + esc(c.ultimo_erro) : '') + '</div></div>' +
            '<span class="text-[10px] text-slate-400">' + esc(c.status) + '</span></div>';
        }).join('') + '</div>';
      });
    });
    return shell('list-iot-comandos', 'Comandos p/ Devices');
  }
  function bTableRegras() {
    fill('table-iot-regras', function () {
      return jget('/api/iot/regras-alerta/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Regra', get: function (r) { return esc(r.nome); } },
          { label: 'Métrica', get: function (r) { return esc(r.metric); } },
          { label: 'Tipo', get: function (r) { return esc((r.tipo || '').replace('threshold_', 'limite ')); } },
          { label: 'Ativa', get: function (r) { return r.ativa ? dot('bg-theme-ok') : dot('bg-slate-300'); } },
        ], 'Nenhuma regra — crie em Telemetria.');
      });
    });
    return shell('table-iot-regras', 'Regras de Alerta');
  }
  function bChartTelemetria(id) {
    fill('chart-iot-telemetria', function () {
      return jget('/api/iot/telemetry/?metric=temperatura&agg=hour&limit=168').then(function (j) {
        var data = (j.data || []).filter(function (r) { return r.avg != null; });
        if (!data.length) return '<p class="text-xs text-slate-400 p-2">Sem série de temperatura (7d).</p>';
        setTimeout(function () { drawTempChart(id, data); }, 40);
        return '<canvas id="xwc-' + id + '" class="w-full h-full"></canvas>';
      });
    });
    return shell('chart-iot-telemetria', 'Temperatura 7 dias');
  }
  function drawTempChart(id, data) {
    var cv = document.getElementById('xwc-' + id);
    if (!cv || typeof window.Chart !== 'function') return;
    var pal = window.ampliChartPalette ? window.ampliChartPalette() : { accent: '#0f9d6e', accentFill: 'rgba(15,157,110,.15)', grid: 'rgba(128,128,128,.1)', tick: '#888' };
    try {
      var old = window.Chart.getChart ? window.Chart.getChart(cv) : null;
      if (old) old.destroy();
    } catch (e) {}
    new window.Chart(cv, {
      type: 'line',
      data: {
        labels: data.map(function (r) { return String(r.bucket || '').slice(5, 16).replace('T', ' '); }),
        datasets: [{
          data: data.map(function (r) { return r.avg; }),
          borderColor: pal.accent, backgroundColor: pal.accentFill, fill: 'origin',
          borderWidth: 2, pointRadius: 0, tension: 0.35,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: pal.grid }, ticks: { color: pal.tick, font: { size: 8 }, maxTicksLimit: 6 } },
          y: { grid: { color: pal.grid }, ticks: { color: pal.tick, font: { size: 8 } } },
        },
      },
    });
  }

  /* ── builders IA ── */
  function bKpiIntents() {
    fill('kpi-ia-intents', function () {
      return Promise.all([
        jget('/api/ia/intents/').catch(function () { return { intents: {} }; }),
        jget('/api/ia/sessao/').catch(function () { return {}; }),
      ]).then(function (r) {
        var n = Object.keys(r[0].intents || {}).length;
        var armed = r[1].sandbox_armado;
        if (typeof window.buildModernKpiHtml === 'function') {
          return window.buildModernKpiHtml('Intenções Mapeadas', n, armed ? 'Sandbox Armado' : 'Sandbox Desarmado', '', armed);
        }
        return '<div class="space-y-2 p-2 text-center"><i class="bi bi-robot text-2xl text-theme-accent"></i>' +
          '<p class="text-xl font-bold">' + n + ' intents</p>' +
          '<div class="text-xs ' + (armed ? 'text-theme-ok' : 'text-theme-alert') + '">' +
          (armed ? 'sandbox armado' : 'sandbox desarmado') + '</div></div>';
      });
    });
    return '<div id="xw-kpi-ia-intents" class="w-full h-full"><div class="flex items-center justify-center h-full text-xs text-slate-400">Carregando...</div></div>';
  }
  function bKpiArtefatos() {
    fill('kpi-ia-artefatos', function () {
      return jget('/api/ia/artefatos/').then(function (j) {
        var all = j.artefatos || rows(j);
        var tipos = {};
        all.forEach(function (a) { tipos[a.tipo] = (tipos[a.tipo] || 0) + 1; });
        var top = Object.keys(tipos).slice(0, 2).map(function (t) { return t + ':' + tipos[t]; }).join(' • ');
        if (typeof window.buildModernKpiHtml === 'function') {
          return window.buildModernKpiHtml('Memória da IA', all.length, esc(top || 'Em contexto'), '', true);
        }
        return '<div class="space-y-2 p-2 text-center"><i class="bi bi-box-seam text-2xl text-theme-accent"></i>' +
          '<p class="text-xl font-bold">' + all.length + ' artefatos</p>' +
          '<div class="text-xs text-slate-400">' + esc(top || 'memória da IA') + '</div></div>';
      });
    });
    return '<div id="xw-kpi-ia-artefatos" class="w-full h-full"><div class="flex items-center justify-center h-full text-xs text-slate-400">Carregando...</div></div>';
  }
  function bListArtefatos() {
    fill('list-ia-artefatos', function () {
      return jget('/api/ia/artefatos/').then(function (j) {
        var all = j.artefatos || rows(j);
        if (!all.length) return '<p class="text-slate-400 py-2 text-center text-xs">Nenhum artefato ainda</p>';
        return '<div class="text-xs p-1.5 overflow-auto h-full space-y-1">' + all.slice(0, 10).map(function (a) {
          return '<div class="flex items-center gap-3 p-2 rounded-lg bg-white/40 dark:bg-black/20 backdrop-blur-sm border border-slate-200 dark:border-slate-700/60 hover:border-theme-accent/50 hover:shadow-sm transition-all">' +
            '<div class="w-7 h-7 rounded-full bg-theme-accent/10 flex items-center justify-center shrink-0"><i class="bi bi-memory text-theme-accent text-[10px]"></i></div>' +
            '<div class="flex-1 min-w-0"><div class="font-semibold text-slate-700 dark:text-slate-200 truncate">' + esc(a.chave) + '</div>' +
            '<div class="text-[9px] text-slate-500 uppercase tracking-wider truncate mt-0.5">' + esc(a.tipo) + ' • ' + esc(a.origem || '') + '</div></div></div>';
        }).join('') + '</div>';
      });
    });
    return shell('list-ia-artefatos', 'Artefatos Recentes');
  }

  /* ── builders info (APIs faltantes) ── */
  function bTableInventario() {
    fill('table-inventario', function () {
      return jget('/api/inventario-itens/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Qtd. Sistema', num: true, get: function (r) { return fmtN(r.quantidade_sistema, 2); } },
          { label: 'Qtd. Contada', num: true, get: function (r) { return fmtN(r.quantidade_contada, 2); } },
          { label: 'Dif.', num: true, get: function (r) {
            var d = (parseFloat(r.quantidade_contada) || 0) - (parseFloat(r.quantidade_sistema) || 0);
            return '<span class="font-semibold ' + (d === 0 ? 'text-theme-ok' : 'text-theme-error') + '">' + fmtN(d, 2) + '</span>';
          } },
        ], 'Nenhum item inventariado.');
      });
    });
    return shell('table-inventario', 'Inventário (divergências)');
  }
  function bTableOrdens() {
    fill('table-ordens-compra', function () {
      return jget('/api/ordens-compra/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Fornecedor', get: function (r) { return esc(r.fornecedor); } },
          { label: 'Emissão', get: function (r) { return esc(r.data_emissao || '—'); } },
          { label: 'Status', get: function (r) { return statusDot(r.status) + ' ' + esc(r.status); } },
          { label: 'Total', num: true, get: function (r) { return '<span class="font-semibold">' + fmtMoney(r.valor_total) + '</span>'; } },
        ], 'Nenhuma ordem de compra.');
      });
    });
    return shell('table-ordens-compra', 'Ordens de Compra');
  }
  function bTablePesagens() {
    fill('table-pesagens', function () {
      return jget('/api/pesagens/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Data', get: function (r) { return esc(r.data || '—'); } },
          { label: 'Tipo', get: function (r) { return esc(r.tipo || '—'); } },
          { label: 'Peso', num: true, get: function (r) { return '<span class="font-semibold">' + fmtN(r.peso, 1) + ' kg</span>'; } },
        ], 'Nenhuma pesagem.');
      });
    });
    return shell('table-pesagens', 'Pesagens');
  }
  function bTablePiquetes() {
    fill('table-piquetes', function () {
      return jget('/api/piquetes/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Piquete', get: function (r) { return esc(r.nome); } },
          { label: 'Área', num: true, get: function (r) { return fmtN(r.area_hectare, 2) + ' ha'; } },
          { label: 'Cap. UA/ha', num: true, get: function (r) { return fmtN(r.capacidade_ua_ha, 2); } },
          { label: 'Status', get: function (r) { return statusDot(r.status) + ' ' + esc(r.status || '—'); } },
        ], 'Nenhum piquete.');
      });
    });
    return shell('table-piquetes', 'Piquetes');
  }
  function bListEventos() {
    fill('list-eventos-sanitarios', function () {
      return jget('/api/eventos-sanitarios/').then(function (j) {
        var list = rows(j);
        if (!list.length) return '<p class="text-slate-400 py-2 text-center text-xs">Nenhum evento sanitário</p>';
        return '<div class="text-xs p-1 overflow-auto h-full">' + list.slice(0, 10).map(function (e) {
          return '<div class="flex items-center gap-2 py-1 border-b border-slate-100 dark:border-slate-800 last:border-0">' +
            '<i class="bi bi-heart-pulse text-theme-error"></i>' +
            '<div class="flex-1 min-w-0"><div class="font-medium truncate">' + esc(e.tipo) + ' — ' + esc(e.produto || '') + '</div>' +
            '<div class="text-slate-400 truncate">' + esc(e.data || '') + (e.proxima_dose ? ' • próx: ' + esc(e.proxima_dose) : '') + '</div></div></div>';
        }).join('') + '</div>';
      });
    });
    return shell('list-eventos-sanitarios', 'Eventos Sanitários');
  }
  function bTableProtocolos() {
    fill('table-protocolos', function () {
      return jget('/api/protocolos-sanitarios/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Protocolo', get: function (r) { return esc(r.nome); } },
          { label: 'Espécie', get: function (r) { return esc(r.especie || '—'); } },
          { label: 'Repetir (dias)', num: true, get: function (r) { return fmtN(r.dias_para_repeticao, 0); } },
        ], 'Nenhum protocolo.');
      });
    });
    return shell('table-protocolos', 'Protocolos Sanitários');
  }
  function bTablePlanos() {
    fill('table-planos-safra', function () {
      return jget('/api/planos-safra/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Orçamento', num: true, get: function (r) { return '<span class="font-semibold">' + fmtMoney(r.orcamento_estimado) + '</span>'; } },
          { label: 'Início', get: function (r) { return esc(r.data_inicio_prevista || '—'); } },
          { label: 'Status', get: function (r) { return statusDot(r.status) + ' ' + esc(r.status); } },
        ], 'Nenhum plano de safra.');
      });
    });
    return shell('table-planos-safra', 'Planos de Safra');
  }
  function bTableReceituarios() {
    fill('table-receituarios', function () {
      return jget('/api/receituarios/').then(function (j) {
        return genTable(rows(j), [
          { label: 'ART', get: function (r) { return esc(r.art || '—'); } },
          { label: 'Praga', get: function (r) { return esc(r.praga || r.diagnostico || '—'); } },
          { label: 'Emitido', get: function (r) { return fmtDT(r.criado_em); } },
        ], 'Nenhum receituário.');
      });
    });
    return shell('table-receituarios', 'Receituários');
  }
  function bTableRastreio() {
    fill('table-rastreio', function () {
      return jget('/api/rastreabilidade/').then(function (j) {
        return genTable(rows(j), [
          { label: 'Aplicação', get: function (r) { return fmtDT(r.data_aplicacao); } },
          { label: 'Qtd.', num: true, get: function (r) { return fmtN(r.quantidade_aplicada, 2); } },
          { label: 'Custo total', num: true, get: function (r) { return '<span class="font-semibold">' + fmtMoney(r.custo_total) + '</span>'; } },
        ], 'Nenhum registro de rastreio.');
      });
    });
    return shell('table-rastreio', 'Rastreabilidade');
  }

  var BUILDERS = {
    'kpi-iot-devices': bKpiDevices,
    'kpi-iot-alertas': bKpiAlertas,
    'kpi-iot-fontes': bKpiFontes,
    'table-iot-leituras': bTableLeituras,
    'chart-iot-telemetria': bChartTelemetria,
    'list-iot-comandos': bListComandos,
    'table-iot-regras': bTableRegras,
    'kpi-ia-intents': bKpiIntents,
    'kpi-ia-artefatos': bKpiArtefatos,
    'list-ia-artefatos': bListArtefatos,
    'table-inventario': bTableInventario,
    'table-ordens-compra': bTableOrdens,
    'table-pesagens': bTablePesagens,
    'table-piquetes': bTablePiquetes,
    'list-eventos-sanitarios': bListEventos,
    'table-protocolos': bTableProtocolos,
    'table-planos-safra': bTablePlanos,
    'table-receituarios': bTableReceituarios,
    'table-rastreio': bTableRastreio,
  };

  var TYPES = {
    'kpi-iot-devices': { title: 'Dispositivos IoT', icon: 'bi-cpu', defaultSize: { w: 6, h: 6 } },
    'kpi-iot-alertas': { title: 'Alertas IoT', icon: 'bi-broadcast', defaultSize: { w: 6, h: 6 } },
    'kpi-iot-fontes': { title: 'Fontes Externas', icon: 'bi-cloud-arrow-down', defaultSize: { w: 6, h: 6 } },
    'table-iot-leituras': { title: 'Últimas Leituras', icon: 'bi-activity', defaultSize: { w: 12, h: 10 } },
    'chart-iot-telemetria': { title: 'Temperatura 7 dias', icon: 'bi-thermometer-half', defaultSize: { w: 12, h: 8 } },
    'list-iot-comandos': { title: 'Comandos Devices', icon: 'bi-send', defaultSize: { w: 6, h: 10 } },
    'table-iot-regras': { title: 'Regras de Alerta', icon: 'bi-bell', defaultSize: { w: 8, h: 8 } },
    'kpi-ia-intents': { title: 'IA Local', icon: 'bi-robot', defaultSize: { w: 6, h: 6 } },
    'kpi-ia-artefatos': { title: 'Memória da IA', icon: 'bi-box-seam', defaultSize: { w: 6, h: 6 } },
    'list-ia-artefatos': { title: 'Artefatos Recentes', icon: 'bi-memory', defaultSize: { w: 6, h: 10 } },
    'table-inventario': { title: 'Inventário', icon: 'bi-clipboard-check', defaultSize: { w: 8, h: 8 } },
    'table-ordens-compra': { title: 'Ordens de Compra', icon: 'bi-cart', defaultSize: { w: 12, h: 10 } },
    'table-pesagens': { title: 'Pesagens', icon: 'bi-speedometer', defaultSize: { w: 8, h: 8 } },
    'table-piquetes': { title: 'Piquetes', icon: 'bi-grid-1x2', defaultSize: { w: 8, h: 8 } },
    'list-eventos-sanitarios': { title: 'Eventos Sanitários', icon: 'bi-heart-pulse', defaultSize: { w: 6, h: 10 } },
    'table-protocolos': { title: 'Protocolos Sanitários', icon: 'bi-journal-medical', defaultSize: { w: 8, h: 8 } },
    'table-planos-safra': { title: 'Planos de Safra', icon: 'bi-kanban', defaultSize: { w: 8, h: 8 } },
    'table-receituarios': { title: 'Receituários', icon: 'bi-file-earmark-medical', defaultSize: { w: 8, h: 8 } },
    'table-rastreio': { title: 'Rastreabilidade', icon: 'bi-qr-code', defaultSize: { w: 12, h: 10 } },
  };

  function extraContent(id) {
    var b = BUILDERS[id];
    if (!b) return null;
    try {
      return b(id);
    } catch (e) {
      return null;
    }
  }

  function merge() {
    /* 1. WIDGET_TYPES (const do dashboard-desktop.js ou window) */
    try {
      var WT = null;
      if (typeof WIDGET_TYPES !== 'undefined' && WIDGET_TYPES) WT = WIDGET_TYPES;
      else if (window.WIDGET_TYPES) WT = window.WIDGET_TYPES;
      else WT = window.WIDGET_TYPES = {};
      Object.keys(TYPES).forEach(function (k) {
        if (!WT[k]) WT[k] = TYPES[k];
      });
    } catch (e) {}

    /* 2. WIDGET_CATALOG (só existe no dashboard) */
    try {
      var cat = window.WIDGET_CATALOG;
      if (cat) {
        if (cat.kpi && !cat.kpi.iot) {
          cat.kpi.iot = {
            title: 'IoT e Sensores', icon: 'bi-cpu',
            items: [
              { id: 'kpi-iot-devices', label: 'Dispositivos', icon: 'bi-cpu', color: 'cyan' },
              { id: 'kpi-iot-alertas', label: 'Alertas IoT', icon: 'bi-broadcast', color: 'rose' },
              { id: 'kpi-iot-fontes', label: 'Fontes Externas', icon: 'bi-cloud-arrow-down', color: 'sky' },
            ],
          };
        }
        if (cat.kpi && !cat.kpi.ia) {
          cat.kpi.ia = {
            title: 'IA Local', icon: 'bi-robot',
            items: [
              { id: 'kpi-ia-intents', label: 'IA Local', icon: 'bi-robot', color: 'violet' },
              { id: 'kpi-ia-artefatos', label: 'Memória IA', icon: 'bi-box-seam', color: 'violet' },
              { id: 'list-ia-artefatos', label: 'Artefatos', icon: 'bi-memory', color: 'slate' },
            ],
          };
        }
        ['table-iot-leituras', 'table-iot-regras', 'table-inventario', 'table-ordens-compra',
          'table-pesagens', 'table-piquetes', 'table-protocolos', 'table-planos-safra',
          'table-receituarios', 'table-rastreio'].forEach(function (id) {
          if (cat.tabelas && !cat.tabelas.some(function (x) { return x.id === id; })) {
            cat.tabelas.push({ id: id, label: TYPES[id].title, icon: TYPES[id].icon, color: 'teal' });
          }
        });
        ['list-iot-comandos', 'list-eventos-sanitarios'].forEach(function (id) {
          if (cat.listas && !cat.listas.some(function (x) { return x.id === id; })) {
            cat.listas.push({ id: id, label: TYPES[id].title, icon: TYPES[id].icon, color: 'amber' });
          }
        });
        if (cat.graficos && !cat.graficos.some(function (x) { return x.id === 'chart-iot-telemetria'; })) {
          cat.graficos.push({ id: 'chart-iot-telemetria', label: 'Temperatura 7d', icon: 'bi-thermometer-half', color: 'cyan' });
        }
      }
    } catch (e) {}

    /* 3. envolve o resolvedor de conteúdo (só assume no placeholder) */
    try {
      if (typeof window.getWidgetSpecificContent === 'function' && !window.getWidgetSpecificContent._xw) {
        var orig = window.getWidgetSpecificContent;
        var wrapped = function (id) {
          var h = null;
          try {
            h = orig(id);
          } catch (e) {}
          if (h && h.indexOf('bi-grid-3x3-gap') === -1) return h;
          return extraContent(id) || h;
        };
        wrapped._xw = true;
        window.getWidgetSpecificContent = wrapped;
      }
    } catch (e) {}
  }

  /* Repinta o chart de telemetria quando o modo troca */
  document.addEventListener('ampliagro:palette', function () {
    try {
      var cvs = document.querySelectorAll('canvas[id^="xwc-"]');
      if (!cvs.length || typeof window.Chart !== 'function') return;
      Array.prototype.forEach.call(cvs, function (cv) {
        try {
          var old = window.Chart.getChart ? window.Chart.getChart(cv) : null;
          if (old) old.destroy();
        } catch (e) {}
      });
      var wid = cvs[0].id.replace(/^xwc-/, '');
      _loading[wid] = false;
      fill(wid, function () {
        return jget('/api/iot/telemetry/?metric=temperatura&agg=hour&limit=168').then(function (j) {
          var data = (j.data || []).filter(function (r) { return r.avg != null; });
          if (!data.length) return '<p class="text-xs text-slate-400 p-2">Sem série de temperatura (7d).</p>';
          setTimeout(function () { drawTempChart(wid, data); }, 40);
          return '<canvas id="xwc-' + wid + '" class="w-full h-full"></canvas>';
        });
      });
    } catch (e) {}
  });

  /* MEDIDO 2026-10-05: este `merge()` corria uma vez, no
   * `DOMContentLoaded` — e os widgets sao desenhados DEPOIS.
   *
   * O dashboard sobe em duas ondas: primeiro carrega culturas e dados
   * (`Promise.all` de `CulturesLoader.ready()` e `/api/dashboard/`), e so
   * entao chama `renderWidgetsOnMatrix()`. O `DOMContentLoaded` dispara
   * muito antes de o primeiro widget existir. Resultado medido:
   *
   *     /api/ia/artefatos/   NUNCA chamada   (e ha 3 artefactos)
   *     /api/iot/alertas/    NUNCA chamada
   *     xw-kpi-ia-artefatos  AUSENTE no DOM
   *
   * O `fill()` procurava `xw-<id>`, nao o encontrava, e saia sem fazer o
   * fetch — sem erro. `pagina-index.js` nao tem builder para estes dois
   * ids (caem no default), e o widget fica com `—`.
   *
   * Duas renderizadores para os mesmos ids, e o que sabia fazer era o que
   * nunca chegou a correr.
   *
   * A correccao e' tornar `merge()` RE-DISPARAVEL, e nao reescrever os
   * builders. `pagina-index.js` chama `window.XW_merge()` logo depois de
   * `renderWidgetsOnMatrix()`. E' idempotente: `WIDGET_TYPES` so recebe
   * entradas em falta (`if (!WT[k])`), o catalogo so quando o grupo nao
   * existe, e o `fill()` tem o guard `_loading`. Chamar duas vezes nao
   * duplica nada.
   */
  window.XW_merge = merge;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      merge();
      // O DOM ja estava pronto quando o script carregou tarde; o merge
      // acima corre logo, e este segundo encontro apanha o caso em que o
      // dashboard desenhou widgets entre os dois.
      if (window.AMPLIAGRO_WIDGETS_PENDENTES) merge();
    });
  } else {
    merge();
  }
})();
