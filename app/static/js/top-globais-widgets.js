/**
 * Top Globais — Wire frontend dos 16 widgets FieldView/JD/Trimble/Solinftec
 * Quando bento-block com id kpi-vra-ndvi etc é criado, busca /api/top-globais/<id> e renderiza.
 */
(function () {
  'use strict';

  /**
   * Um valor que pode não existir, para mostrar.
   *
   * `${ndvi.ndvi_medio} — ${ndvi.sanidade}` escrevia literalmente
   * "null — null" no ecrã quando não havia medição. E
   * `${ndvi.cobertura_nuvens || 0}` escrezia "0%" — que não é "sem
   * medição", é a afirmação de que o céu estava limpo.
   *
   * A diferença importa: "Sem NDVI" pede uma acção. "0% de nuvens" faz a
   * pessoa irrigar com base num zero que ninguém mediu.
   *
   * Devolve o texto do valor, e `true` quando não há nada que mostrar.
   */
  function valorOuAusente(v, quandoAusente) {
    if (v === null || v === undefined || v === '') return quandoAusente;
    return String(v);
  }

  var HANDLERS = {
    'kpi-vra-ndvi': function (data) {
      var ndvi = data.ndvi || data;
      var temNdvi = ndvi.ndvi_medio !== null && ndvi.ndvi_medio !== undefined;

      // O heatmap só existe quando há medição. Sem ela, o `onerror`
      // escondia a imagem e o cartão ficava com um buraco — e sem dizer
      // porque. Agora diz.
      var heatmap =
        ndvi.heatmap_url ||
        (temNdvi ? '/api/talhao/' + (ndvi.talhao_id || 1) + '/ndvi-heatmap/' : null);
      var imagem = data._loading
        ? '<div class="animate-pulse bg-slate-200 h-[100px] rounded"></div>'
        : heatmap
          ? '<img src="' +
            heatmap +
            '" alt="NDVI heatmap" class="w-full h-[100px] object-cover rounded-lg border border-black/5" loading="lazy"/>'
          : '<div class="h-[100px] rounded-lg border border-dashed border-slate-300 dark:border-slate-700 flex items-center justify-center text-[10px] opacity-60 text-center px-2">Sem imagem de satélite</div>';

      // O valor grande. Com NDVI: o número e o veredicto agronómico, que
      // é o que decide a irrigação. Sem: a ausência, e o motivo.
      var grande = temNdvi
        ? ndvi.sanidade
          ? ndvi.ndvi_medio + ' — ' + ndvi.sanidade
          : String(ndvi.ndvi_medio)
        : 'Sem NDVI';

      // `cobertura_nuvens` só aparece se foi medida. O `|| 0` antigo
      // transformava "não medido" em "céu limpo", que é uma afirmação
      // meteorológica feita a partir de nada.
      var meta = [];
      if (ndvi.satelite) meta.push(ndvi.satelite);
      if (ndvi.cobertura_nuvens !== null && ndvi.cobertura_nuvens !== undefined) {
        meta.push('nuvens ' + ndvi.cobertura_nuvens + '%');
      }
      meta.push('Talhao ' + (ndvi.talhao_id || 1));
      if (ndvi.data_captura) meta.push(String(ndvi.data_captura).slice(0, 10));

      var motivo = temNdvi ? data.acao || '' : ndvi.motivo || 'Sem fonte de satélite configurada';

      var presc = data.prescricao
        ? '<div class="text-[10px] mt-1 bg-emerald-50 text-emerald-700 rounded px-2 py-1">VRA ' +
          data.prescricao.produto +
          ' ' +
          data.prescricao.dose +
          'kg/ha</div>'
        : '';

      return (
        '<div class="p-2 flex flex-col gap-2">' +
        '<div class="flex justify-between items-start">' +
        '<div class="min-w-0"><div class="text-[10px] opacity-60">VRA NDVI 10m Sentinel-2</div>' +
        '<div class="text-lg font-bold">' +
        grande +
        '</div>' +
        '<div class="text-[10px] opacity-60">' +
        motivo +
        '</div></div>' +
        '<div class="text-[9px] opacity-50 text-right shrink-0">' +
        meta.join('<br/>') +
        '</div>' +
        '</div>' +
        imagem +
        presc +
        '</div>'
      );
    },
    'kpi-can-bus': function (data) {
      var chartId = 'canbus-chart-' + (data.device_id || 1) + '-' + Date.now();
      var dtcBadge = data.dtc
        ? '<span class="bg-red-500 text-white text-[9px] px-2 py-0.5 rounded-full">DTC ' +
          data.dtc +
          '</span>'
        : '<span class="bg-emerald-500 text-white text-[9px] px-2 py-0.5 rounded-full">OK</span>';
      var hist = data.chart || {
        labels: ['00:00', '01:00', '02:00', '03:00', '04:00', '05:00'],
        rpm: [1800, 1900, 2100, 2000, 1850, 1920],
        consumo: [12, 13, 14, 12.5, 13, 12],
      };
      // Store for post-render chart init
      window._canBusChartData = window._canBusChartData || {};
      window._canBusChartData[chartId] = hist;
      return `<div class="p-2 flex flex-col gap-2"><div class="flex justify-between items-start"><div><div class="text-[10px] opacity-60">CAN Bus J1939</div><div class="text-lg font-bold">${
        data.rpm
      } RPM</div><div class="text-xs">${
        data.consumo_lh
      } L/h ${dtcBadge}</div></div><div class="text-[9px] opacity-50">${data.estado}<br/>Dev ${
        data.device_id || 1
      }</div></div><canvas id="${chartId}" height="70" class="w-full rounded bg-slate-50"></canvas><div class="text-[8px] opacity-40">RPM×hora 6h — DTC P0420 = falha catalisador</div></div>`;
    },
    'kpi-guidance-ab': function (data) {
      // `precisao_cm` é null quando não há guia ligada. `${null}cm` escrevia
      // "nullcm" — e o `cm` sem número parece uma medida truncada, que é
      // pior: parece que o sistema leu o sensor e não percebeu.
      var precisao =
        data.precisao_cm === null || data.precisao_cm === undefined
          ? null
          : data.precisao_cm + 'cm';
      var auto =
        data.auto_section === null || data.auto_section === undefined
          ? '—'
          : data.auto_section
            ? 'ON'
            : 'OFF';
      var linha = data.linha || data.talhao_nome || '—';
      return (
        '<div class="p-3"><div class="text-xs">' +
        linha +
        '</div>' +
        '<div class="text-[10px] opacity-60">Precisão ' +
        (precisao === null ? 'não medida' : precisao) +
        ' • Auto-section ' +
        auto +
        '</div></div>'
      );
    },
    'kpi-ai-cultura': function (data) {
      // `cultura: null` com `confianca: null`. O `${(confianca*100)}`
      // dava "NaN%" e `${cultura}` dava "null" — dois bugs num template.
      if (!data.cultura) {
        return (
          '<div class="p-3"><div class="text-sm font-bold">Sem detecção</div>' +
          '<div class="text-[10px] opacity-60">' +
          (data.motivo || 'Sem fonte de imagem') +
          '</div></div>'
        );
      }
      var conf =
        data.confianca === null || data.confianca === undefined
          ? null
          : Math.round(data.confianca * 100) + '%';
      return (
        '<div class="p-3"><div class="text-sm font-bold">' +
        data.cultura +
        '</div>' +
        '<div class="text-xs">Conf ' +
        (conf === null ? 'não medida' : conf) +
        ' ' +
        (data.fonte || '') +
        '</div></div>'
      );
    },
    'kpi-chuva-1km': function (data) {
      // `mm_15min: 0.0` sem fonte nenhuma, com `_evidencia: ""`. Mostrar
      // "0.0mm/15min" afirma que não chove — e "0mm" num sistema que não
      // consultou nada é a forma mais barata de estar errado.
      var temFonte =
        data._evidencia !== '' && data._evidencia !== null && data._evidencia !== undefined;
      if (!temFonte) {
        return (
          '<div class="p-3"><div class="text-lg font-bold">Sem leitura</div>' +
          '<div class="text-xs opacity-60">Sem radar de chuva ligado</div></div>'
        );
      }
      return (
        '<div class="p-3"><div class="text-lg font-bold">' +
        data.mm_15min +
        'mm/15min</div>' +
        '<div class="text-xs">' +
        data.mm_1h +
        'mm/1h ' +
        (data.alerta ? '⚠️' : 'OK') +
        '</div></div>'
      );
    },
    'kpi-as-applied': function (data) {
      if (data.gap_pct === null || data.gap_pct === undefined) {
        return (
          '<div class="p-3"><div class="text-sm">Sem comparação</div>' +
          '<div class="text-[10px] opacity-60">Sem layers de aplicação</div></div>'
        );
      }
      var ndvi = data.ndvi === null || data.ndvi === undefined ? 'sem NDVI' : 'NDVI ' + data.ndvi;
      return (
        '<div class="p-3"><div class="text-sm">Gap ' +
        data.gap_pct +
        '%</div>' +
        '<div class="text-xs">' +
        (data.acao || '') +
        ' ' +
        ndvi +
        '</div></div>'
      );
    },
    'kpi-praga-ai': function (data) {
      // `praga: null` sem diagnóstico. `${null}` escrevia "null", e
      // `(null*100).toFixed(0)%` escrevia "0%" — que parece uma
      // percentagem medida a zero.
      if (!data.praga) {
        return (
          '<div class="p-3"><div class="text-sm font-bold">Sem diagnóstico</div>' +
          '<div class="text-[10px] opacity-60">' +
          (data.motivo || 'Sem foto submetida') +
          '</div></div>'
        );
      }
      var conf =
        data.confianca === null || data.confianca === undefined
          ? ''
          : 'Conf ' + Math.round(data.confianca * 100) + '% ';
      return (
        '<div class="p-3"><div class="text-sm font-bold">' +
        data.praga +
        '</div>' +
        '<div class="text-xs">' +
        conf +
        (data.acao || '') +
        '</div></div>'
      );
    },
    'kpi-rota-otimizada': function (data) {
      if (data.km_total === null || data.km_total === undefined) {
        return (
          '<div class="p-3"><div class="text-sm">Sem rota</div>' +
          '<div class="text-[10px] opacity-60">' +
          (data.motivo || 'Sem optimiseizador ligado') +
          '</div></div>'
        );
      }
      var eco =
        data.economia_pct === null || data.economia_pct === undefined
          ? ''
          : 'Economia ' + data.economia_pct + '%';
      return (
        '<div class="p-3"><div class="text-sm">' +
        data.km_total +
        'km em ' +
        data.tempo_h +
        'h</div>' +
        '<div class="text-xs">' +
        eco +
        ' 70 colheitadeiras</div></div>'
      );
    },
    'kpi-weigh-scale': function (data) {
      // `sc_ha: null` sem balança ligada. `${null} sc/ha` escrevia
      // "null sc/ha" — que parece uma pesagem que deu zero.
      if (data.sc_ha === null || data.sc_ha === undefined) {
        return (
          '<div class="p-3"><div class="text-lg font-bold">Sem pesagem</div>' +
          '<div class="text-xs opacity-60">' +
          (data.motivo || 'Nenhuma balança ligada') +
          '</div></div>'
        );
      }
      var ndvi = data.ndvi === null || data.ndvi === undefined ? '' : 'NDVI ' + data.ndvi;
      return (
        '<div class="p-3"><div class="text-lg font-bold">' +
        data.sc_ha +
        ' sc/ha</div>' +
        '<div class="text-xs">' +
        ndvi +
        ' ' +
        (data.tempo_real ? 'tempo real' : 'última pesagem') +
        '</div></div>'
      );
    },
    'kpi-hedge-b3': function (data) {
      return `<div class="p-3"><div class="text-sm">Hedge ${data.recomendado} (${data.sacas} sc @ ${data.strike})</div><div class="text-[9px] opacity-50">B3 Chicago</div></div>`;
    },
    'kpi-benchmark-fbn': function (data) {
      return `<div class="p-3"><div class="text-sm">Seu ${data.seu_custo_ha} vs ${
        data.media_2k
      } média</div><div class="text-xs ${
        data.vs_media_pct > 0 ? 'text-red-500' : 'text-green-600'
      }">${data.vs_media_pct > 0 ? '+' : ''}${data.vs_media_pct}%</div></div>`;
    },
    'kpi-seguro-chuva': function (data) {
      // `motivo` primeiro: quando o backend nao mediu, mostrar `nullmm` e
      // "OK (limite 200mm)" affirmava que nao houve perda a indenizar.
      if (data.motivo) {
        return `<div class="p-3"><div class="text-xs opacity-60">Sem dado</div>` +
          `<div class="text-[9px] opacity-50">${data.motivo}</div></div>`;
      }
      return `<div class="p-3"><div class="text-sm">${
        data.chuva_60d
      }mm/60d</div><div class="text-xs">${
        data.paga ? 'Paga R$' + data.valor : 'OK'
      } (limite ${data.limite}mm)</div></div>`;
    },
    'kpi-lcdpr-sped': function (data) {
      return `<div class="p-3"><div class="text-sm">${data.arquivo}</div><div class="text-xs">${
        data.sped ? 'SPED OK' : '-'
      } ${data.auditavel ? 'Auditável' : ''}</div></div>`;
    },
    'kpi-carbono': function (data) {
      return `<div class="p-3"><div class="text-sm">${data.tco2e} tCO2e</div><div class="text-xs">${data.area_ha}ha × ${data.tco2e_ha} Mombak</div></div>`;
    },
    'kpi-voz': function (data) {
      // O texto fixo "TTS/STT pt-BR" afirmava uma capacidade. Agora vem do
      // backend, que mediu `tts: False`.
      var voz = data.tts || data.stt ? (data.voz || 'pt-BR') : 'sem motor de voz';
      return `<div class="p-3"><div class="text-xs">${data.texto}</div>` +
        `<div class="text-[9px] opacity-50">${voz}</div></div>`;
    },
    'kpi-copilot-hedge': function (data) {
      if (data.motivo) {
        return `<div class="p-3"><div class="text-xs opacity-60">Sem dado</div>` +
          `<div class="text-[9px] opacity-50">${data.motivo}</div></div>`;
      }
      return `<div class="p-3"><div class="text-xs">${data.copilot ? 'Copilot' : ''} ${
        data.resposta || JSON.stringify(data).slice(0, 60)
      }</div></div>`;
    },
  };

  function wire(block) {
    var id = block.id ? block.id.replace('widget-', '') : '';
    if (!HANDLERS[id]) return;
    var content = block.querySelector('.widget-content') || block;
    if (!content || content.dataset.topGlobaisWired) return;
    content.dataset.topGlobaisWired = '1';
    // params: tenta pegar talhao_id do primeiro talhao, senão 1
    var params = new URLSearchParams();
    if (
      id.indexOf('vra') >= 0 ||
      id.indexOf('guidance') >= 0 ||
      id.indexOf('applied') >= 0 ||
      id.indexOf('weigh') >= 0
    ) {
      var tid = 1;
      try {
        var t = document.querySelector('[data-talhao-id]');
        if (t) tid = t.getAttribute('data-talhao-id');
      } catch (e) {}
      params.set('talhao_id', tid);
    }
    if (id.indexOf('can-bus') >= 0) params.set('device_id', '1');
    if (id.indexOf('chuva') >= 0 || id.indexOf('seguro') >= 0 || id.indexOf('ai-cultura') >= 0) {
      params.set('lat', '-15');
      params.set('lon', '-47');
    }
    if (id.indexOf('benchmark') >= 0) params.set('propriedade_id', '1');
    if (id.indexOf('hedge') >= 0) {
      params.set('sacas', '1000');
      params.set('strike', '85');
    }
    if (id.indexOf('voz') >= 0 || id.indexOf('copilot') >= 0)
      params.set('texto', 'quanto choveu no talhao 3?');

    // skeleton enquanto busca
    var header = content.querySelector('.widget-header');
    var headerHtml = header ? header.outerHTML : '';
    content.innerHTML =
      headerHtml +
      '<div class="p-3 animate-pulse"><div class="h-4 bg-slate-200 rounded w-1/2 mb-2"></div><div class="h-[70px] bg-slate-200 rounded mb-2"></div><div class="h-3 bg-slate-200 rounded w-1/3"></div></div>';
    fetch('/api/top-globais/' + id + '/?' + params.toString(), { credentials: 'same-origin' })
      .then(function (r) {
        return r.json();
      })
      .then(function (j) {
        var d = j.data || j;
        var html = '';
        try {
          html = HANDLERS[id](d);
        } catch (e) {
          html = '<div class="p-2 text-xs">Erro: ' + e.message + '</div>';
        }
        // preserva header do widget se existir
        var h2 = content.querySelector('.widget-header');
        var hHtml2 = h2 ? h2.outerHTML : headerHtml;
        content.innerHTML = hHtml2 + html;
        // Se for CAN Bus, inicializa Chart.js RPM×hora
        if (id === 'kpi-can-bus' && window.Chart && d.chart) {
          try {
            var canvas = content.querySelector('canvas[id^="canbus-chart"]');
            if (canvas) {
              var ctx = canvas.getContext('2d');
              var hist = window._canBusChartData[canvas.id] || d.chart;
              new Chart(ctx, {
                type: 'line',
                data: {
                  labels: hist.labels,
                  datasets: [
                    {
                      label: 'RPM',
                      data: hist.rpm,
                      borderColor: '#f59e0b',
                      backgroundColor: 'rgba(245,158,11,0.1)',
                      tension: 0.4,
                      pointRadius: 0,
                      borderWidth: 1.5,
                      yAxisID: 'y',
                    },
                    {
                      label: 'L/h',
                      data: hist.consumo,
                      borderColor: '#0f9d6e',
                      backgroundColor: 'rgba(15,157,110,0.1)',
                      tension: 0.4,
                      pointRadius: 0,
                      borderWidth: 1.5,
                      yAxisID: 'y1',
                    },
                  ],
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { display: false }, tooltip: { enabled: true } },
                  scales: { x: { display: false }, y: { display: false }, y1: { display: false } },
                  interaction: { mode: 'index', intersect: false },
                },
              });
            }
          } catch (e) {
            console.warn('CAN Bus chart', e);
          }
        }
      })
      .catch(function (e) {
        content.innerHTML =
          '<div class="p-2 text-xs text-red-500">Falha API top-globais: ' + e.message + '</div>';
      });
  }

  // Scan com debounce real: renderWidgetsOnMatrix dispara por FRAME durante drag.
  // Antes, cada render agendava um setTimeout(300) sem clear → um drag de 2s enfileirava
  // ~60 querySelectorAll('.bento-block') globais + 60 passagens de wire.
  var _scanTimer = null;
  function scanSoon() {
    if (_scanTimer) clearTimeout(_scanTimer);
    _scanTimer = setTimeout(function () {
      _scanTimer = null;
      scan();
    }, 300);
  }

  function scan() {
    document.querySelectorAll('.bento-block').forEach(wire);
  }

  // Observa matrix-container para novos widgets (drag drop)
  var _watchedContainer = null;
  function watch() {
    var cont = document.querySelector('.matrix-container');
    if (!cont || cont === _watchedContainer) return;
    _watchedContainer = cont;
    new MutationObserver(function (muts) {
      var needsFullScan = false;
      muts.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType !== 1) return;
          if (n.classList.contains('bento-block')) {
            wire(n);
            return;
          }
          if (n.querySelectorAll) {
            var found = n.querySelectorAll('.bento-block');
            if (found.length) {
              found.forEach(wire);
              return;
            }
          }
          needsFullScan = true;
        });
      });
      if (needsFullScan) scanSoon();
    }).observe(cont, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', function () {
      scan();
      watch();
    });
  else {
    scan();
    watch();
  }

  // Re-scan após renderWidgetsOnMatrix (estilo index.html) — DEBOUNCED
  var _orig = window.renderWidgetsOnMatrix;
  if (typeof _orig === 'function' && !_orig._topGlobaisWrapped) {
    window.renderWidgetsOnMatrix = function () {
      var r = _orig.apply(this, arguments);
      scanSoon();
      return r;
    };
    window.renderWidgetsOnMatrix._topGlobaisWrapped = true;
  }

  window.TopGlobaisWidgets = { scan: scan, scanSoon: scanSoon, rewire: watch, handlers: HANDLERS };
})();
