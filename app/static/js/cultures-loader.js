window.CulturesLoader = (function () {
  var loaded = false;
  var callbacks = [];
  var configData = null;

  function load() {
    try {
      if (window.dashboardLog)
        window.dashboardLog('CulturesLoader:load:start', {
          url: '/static/data/cultures-config.json',
        });
    } catch (e) {}
    // Cache localStorage para F12 com Disable cache (evita 1.7s de atraso visto no console)
    try {
      var cached = localStorage.getItem('ampliagro-cultures-config');
      var cachedAt = parseInt(localStorage.getItem('ampliagro-cultures-config-at') || '0', 10);
      if (cached && Date.now() - cachedAt < 24 * 60 * 60 * 1000) {
        var cfg = JSON.parse(cached);
        configData = cfg;
        applyConfig(cfg);
        loaded = true;
        try {
          if (window.dashboardLog)
            window.dashboardLog('CulturesLoader:load:done', {
              groups: (cfg.groups || []).length,
              cached: true,
            });
        } catch (e) {}
        notifyCallbacks();
        if (typeof window.dispatchEvent === 'function')
          window.dispatchEvent(new CustomEvent('culturesloaded', { detail: cfg }));
        // atualiza em background sem bloquear
        fetch('/static/data/cultures-config.json')
          .then(function (r) {
            return r.json();
          })
          .then(function (fresh) {
            try {
              localStorage.setItem('ampliagro-cultures-config', JSON.stringify(fresh));
              localStorage.setItem('ampliagro-cultures-config-at', String(Date.now()));
            } catch (e) {}
            if (JSON.stringify(fresh) !== cached) {
              configData = fresh;
              applyConfig(fresh);
            }
          })
          .catch(function () {});
        return Promise.resolve(cfg);
      }
    } catch (e) {}
    return fetch('/static/data/cultures-config.json')
      .then(function (r) {
        try {
          if (window.dashboardLog)
            window.dashboardLog('CulturesLoader:load:fetch', { ok: r.ok, status: r.status });
        } catch (e) {}
        return r.json();
      })
      .then(function (config) {
        try {
          if (window.dashboardLog)
            window.dashboardLog('CulturesLoader:load:done', {
              groups: (config.groups || []).length,
            });
        } catch (e) {}
        try {
          localStorage.setItem('ampliagro-cultures-config', JSON.stringify(config));
          localStorage.setItem('ampliagro-cultures-config-at', String(Date.now()));
        } catch (e) {}
        configData = config;
        applyConfig(config);
        loaded = true;
        notifyCallbacks();
        if (typeof window.dispatchEvent === 'function') {
          window.dispatchEvent(new CustomEvent('culturesloaded', { detail: config }));
        }
        return config;
      })
      .catch(function (err) {
        console.warn('[CulturesLoader] cultures-config.json nao carregado, usando fallback', err);
        // tenta usar cache mesmo expirado
        try {
          var fallback = localStorage.getItem('ampliagro-cultures-config');
          if (fallback) {
            var fb = JSON.parse(fallback);
            configData = fb;
            applyConfig(fb);
          }
        } catch (e) {}
        loaded = true;
        notifyCallbacks();
      });
  }

  function applyConfig(config) {
    var groups = [];
    (config.groups || []).forEach(function (g) {
      var group = {
        id: g.id,
        title: g.title,
        icon: g.icon,
        cultures: [],
      };

      if (g.cultures) {
        g.cultures.forEach(function (c) {
          group.cultures.push(normalizeCulture(c, g.id));
        });
      }

      if (g.subgroups) {
        g.subgroups.forEach(function (sg) {
          (sg.cultures || []).forEach(function (c) {
            var nc = normalizeCulture(c, g.id);
            nc.subgroup = sg.id;
            nc.subgroup_title = sg.title;
            nc.subgroup_icon = sg.icon || g.icon;
            group.cultures.push(nc);
          });
        });
      }

      // UM GRUPO VAZIO NAO ENTRA NO MENU. MEDIDO 2026-10-04.
      //
      // `cultures-config.json` tem um grupo `extrativismo` com zero culturas —
      // o subgrupo chama-se "Conceitos" e a lista esta vazia. Com o `push`
      // incondicional, esse grupo chegava a `window.CULTURE_GROUPS` e
      // portanto ao menu, e o produtor via um separador "Extrativismo" que
      // nao tinha nada dentro.
      //
      // Isto e' diferente de "faltam culturas". Uma cultura em falta e' uma
      // lacuna; um grupo declarado e vazio e' uma entrada de menu que nao faz
      // nada. E o `index.html:9794-9808` trata o painel vazio com uma
      // mensagem honesta — mas essa guarda e' o ultimo recurso, e o
      // separador nunca devia ter chegado a existir.
      //
      // E o que torna isto mais do que estetica: `extrativismo` conta como
      // uma das cadeias do produto. Contar uma cadeia que nao tem nada e'
      //exactly o tipo de numero que o `tests/test_promessas_numericas.py`
      // mede e nao aceita.
      if (!group.cultures.length) {
        if (window.console && console.warn) {
          console.warn(
            '[culturas-loader] grupo "' + group.id +
            '" declarado no config sem nenhuma cultura; nao entra no menu.'
          );
        }
        return;
      }

      groups.push(group);
    });

    window.CULTURE_GROUPS = groups;

    if (!window.CULTURE_METRICS) window.CULTURE_METRICS = {};
    window.CULTURE_METRICS.default = metricsArrayFromObj(config.default_metrics);
    groups.forEach(function (g) {
      g.cultures.forEach(function (c) {
        var m = {};
        if (c.metrics_override) {
          Object.keys(config.default_metrics).forEach(function (k) {
            var base = JSON.parse(JSON.stringify(config.default_metrics[k]));
            var override = c.metrics_override[k];
            if (override) {
              if (override.value !== undefined) base.value = override.value;
              if (override.label !== undefined) base.label = override.label;
              if (override.unit !== undefined) base.unit = override.unit;
            }
            m[k] = base;
          });
        }
        window.CULTURE_METRICS[c.id] = Object.keys(m).length ? m : null;
      });
    });

    window.CULTURE_UNITS = config.units || {};
    window.CULTURE_CONFIG = config;

    // Popula WIDGET_TYPES automaticamente
    if (typeof window.WIDGET_TYPES !== 'undefined' && window.WIDGET_TYPES) {
      groups.forEach(function (g) {
        g.cultures.forEach(function (c) {
          if (!window.WIDGET_TYPES[c.id]) {
            window.WIDGET_TYPES[c.id] = {
              title: c.title,
              icon: c.icon,
              defaultSize: { w: 10, h: 5 },
              desc: c.desc || '',
              group: g.id,
              subgroup: c.subgroup || '',
            };
          }
        });
      });
    }
  }

  function normalizeCulture(c, groupId) {
    return {
      id: c.id,
      title: c.title,
      icon: c.icon,
      desc: c.desc || '',
      types: c.types || {},
      units: c.units || { default: 'sacas', available: [] },
      conversions: c.conversions || [],
      ibge: c.ibge || null,
      agrodoc: c.agrodoc || null,
      django_grupo: c.django_grupo || groupId || 'outro',
      django_nome: c.django_nome || c.title,
      metrics_override: c.metrics_override || null,
      subgroup: c.subgroup || '',
      subgroup_title: c.subgroup_title || '',
    };
  }

  function metricsArrayFromObj(obj) {
    if (!obj) return [];
    return Object.keys(obj).map(function (k) {
      return obj[k];
    });
  }

  function notifyCallbacks() {
    callbacks.forEach(function (cb) {
      try {
        cb(configData);
      } catch (e) {}
    });
    callbacks = [];
  }

  function ready(cb) {
    if (loaded) {
      if (cb)
        setTimeout(function () {
          cb(configData);
        }, 0);
      return Promise.resolve(configData);
    }
    if (cb) callbacks.push(cb);
    return new Promise(function (resolve) {
      callbacks.push(function (cfg) {
        resolve(cfg);
      });
    });
  }

  function getCulture(id) {
    if (!window.CULTURE_GROUPS) return null;
    for (var gi = 0; gi < window.CULTURE_GROUPS.length; gi++) {
      var g = window.CULTURE_GROUPS[gi];
      for (var ci = 0; ci < g.cultures.length; ci++) {
        if (g.cultures[ci].id === id) return g.cultures[ci];
      }
    }
    var lower = id.toLowerCase();
    for (var gi2 = 0; gi2 < window.CULTURE_GROUPS.length; gi2++) {
      var g2 = window.CULTURE_GROUPS[gi2];
      for (var ci2 = 0; ci2 < g2.cultures.length; ci2++) {
        if (g2.cultures[ci2].id.indexOf(lower) >= 0) return g2.cultures[ci2];
      }
    }
    return null;
  }

  function findByTitle(title) {
    if (!window.CULTURE_GROUPS) return null;
    var lower = title.toLowerCase();
    for (var gi = 0; gi < window.CULTURE_GROUPS.length; gi++) {
      var g = window.CULTURE_GROUPS[gi];
      for (var ci = 0; ci < g.cultures.length; ci++) {
        if (g.cultures[ci].title.toLowerCase() === lower) return g.cultures[ci];
      }
    }
    return null;
  }

  function convert(value, fromUnit, toUnit, cultureId, type) {
    var cfg = configData;
    if (!cfg) return null;
    if (fromUnit === toUnit) return value;

    var fromDef = cfg.units[fromUnit];
    var toDef = cfg.units[toUnit];
    if (fromDef && fromDef.base_si && toDef && toDef.base_si && fromDef.base_si === toDef.base_si) {
      return (value * (fromDef.to_si || 1)) / (toDef.to_si || 1);
    }

    var culture = getCulture(cultureId);
    if (culture && culture.conversions) {
      for (var i = 0; i < culture.conversions.length; i++) {
        var cv = culture.conversions[i];
        if (cv.from === fromUnit && cv.to === toUnit) {
          if (!cv.type || !type || cv.type === type) {
            return value * cv.factor;
          }
        }
      }
    }
    return null;
  }

  // ==========================================
  // RENDER ENGINE — accordion de subcategorias
  // ==========================================

  /**
   * Um grupo sem culturas não é um grupo: é um buraco com um separador em cima.
   *
   * O caso real é o `extrativismo`, cujo subgrupo ("Conceitos") tem
   * `cultures: []`. O separador aparecia, o painel era criado, e o
   * `renderCultureAccordion` não tinha nada para desenhar — Resultado: abrir
   * "Adicionar Widget" e clicar em "Extrativismo" dava um modal inteiro em
   * branco, sem widgets e sem uma única palavra de explicação. O produtor não
   * tinha como saber se era um erro, uma falha de rede, ou se aquele separador
   * era para ele.
   *
   * A regra é a mesma que vale para os números: **ausência que não é
   * anunciada é uma mentira**. Dizer "não há nada aqui" é honesto; mostrar um
   * rectângulo vazio faz o utilizador tentar corrigir o que não está
   * estragado. Por isso o separador não é desenhado, em vez de ser desenhado
   * e vir acompanhado de um aviso que ninguém lê.
   *
   * Se um dia o extrativismo tiver culturas, o separador volta sozinho — não
   * há lista de separadores para manter em sintonia, que é o que faz este
   * tipo de coisa divergir.
   *
   * @returns {Array} os grupos que realmente têm conteúdo.
   */
  function gruposComConteudo() {
    var todos = window.CULTURE_GROUPS || [];
    return todos.filter(function (g) {
      return g && Array.isArray(g.cultures) && g.cultures.length > 0;
    });
  }

  function renderCultureTabs() {
    try {
      var container = document.getElementById('widget-modal-tabs-cultura');
      if (!container || !window.CULTURE_GROUPS) return;
      container.querySelectorAll('[data-dynamic-tab]').forEach(function (el) {
        el.remove();
      });
      gruposComConteudo().forEach(function (group) {
        var li = document.createElement('li');
        li.className = 'nav-item';
        li.setAttribute('data-dynamic-tab', 'true');
        var btn = document.createElement('button');
        btn.setAttribute('onclick', "switchWidgetTab('" + group.id + "')");
        btn.setAttribute('data-modal-tab', group.id);
        btn.setAttribute('data-dynamic-tab', 'true');
        btn.setAttribute('role', 'tab');
        btn.className = 'nav-link';
        btn.innerHTML = '<i class="bi ' + (group.icon || 'bi-flower1') + '"></i> ' + group.title;
        li.appendChild(btn);
        container.appendChild(li);
      });
    } catch (e) {
      console.warn('[CulturesLoader] renderCultureTabs error:', e);
    }
  }

  function renderPersistentCultureFilter() {
    // Removido: campo "filtrar cultura por qualquer area" excluído a pedido do usuário
    try {
      var oldBar = document.getElementById('culture-filter-bar');
      if (oldBar) oldBar.remove();
    } catch (e) {}
  }

  function renderCultureContent() {
    try {
      var container = document.getElementById('widget-modal-content');
      if (!container || !window.CULTURE_GROUPS) return;
      container.querySelectorAll('[data-dynamic-content]').forEach(function (el) {
        el.remove();
      });
      // Mesmos grupos que os separadores. Se esta lista e a de
      // `renderCultureTabs` divergirem, aparece um separador sem painel (ou
      // um painel sem separador) — e o painel vazio é exactamente o defeito
      // que o filtro veio resolver. Por isso as duas chamam a MESMA função.
      gruposComConteudo().forEach(function (group) {
        var div = document.createElement('div');
        div.className = 'tab-content hidden';
        div.setAttribute('data-modal-tab', group.id);
        div.setAttribute('data-dynamic-content', 'true');
        div.id = 'culture-tab-' + group.id;
        container.appendChild(div);
        renderCultureAccordion(group, div);
      });
    } catch (e) {
      console.warn('[CulturesLoader] renderCultureContent error:', e);
    }
  }

  function renderCultureAccordion(group, container) {
    try {
      container.innerHTML = '';
      var subgroups = {};
      group.cultures.forEach(function (c) {
        var sg = c.subgroup || '_default';
        if (!subgroups[sg])
          subgroups[sg] = {
            title: c.subgroup_title || group.title,
            icon: c.subgroup_icon || group.icon,
            cultures: [],
          };
        subgroups[sg].cultures.push(c);
      });
      var sgKeys = Object.keys(subgroups);
      // Subgroup buttons row
      var btnRow = document.createElement('div');
      btnRow.className = 'flex flex-wrap gap-1 mb-2';
      container.appendChild(btnRow);

      sgKeys.forEach(function (sgk, idx) {
        var sg = subgroups[sgk];
        var accId = 'sg-' + group.id + '-' + sgk;
        // Pill button
        var btn = document.createElement('button');
        btn.className = 'subgroup-pill' + (idx === 0 ? ' active' : '');
        btn.setAttribute('data-subgroup-btn', accId);
        btn.innerHTML =
          sg.title + ' <i class="bi bi-chevron-down text-[7px] transition-transform"></i>';
        btn.onclick = (function (id, el) {
          return function () {
            var body = document.getElementById(id);
            if (!body) return;
            var isOpen = body.style.display !== 'none';
            if (isOpen) {
              body.style.display = 'none';
              el.classList.remove('active');
              el.querySelector('i').style.transform = '';
            } else {
              body.style.display = '';
              el.classList.add('active');
              el.querySelector('i').style.transform = 'rotate(180deg)';
            }
          };
        })(accId, btn);
        btnRow.appendChild(btn);
        // Container for this subgroup's cards
        var body = document.createElement('div');
        body.id = accId;
        body.className = 'subgroup-cards-grid';
        body.style.display = idx === 0 ? '' : 'none';
        container.appendChild(body);
        sg.cultures.forEach(function (c) {
          renderSingleCultureCard(body, c, group);
        });
      });
    } catch (e) {
      console.warn('[CulturesLoader] renderCultureAccordion error:', e);
    }
  }

  function renderCultureButtons() {
    // Legacy — now handled by renderCultureAccordion
  }

  function renderCultureCardGroup(grid, cultures, group) {
    try {
      cultures.forEach(function (c) {
        var btn = document.createElement('div');
        btn.className = 'widget-card relative group/card';
        btn.setAttribute('onclick', "showCultureMiniPanel('" + c.id + "', '" + group.id + "')");
        btn.setAttribute('data-culture-card', 'true');
        btn.setAttribute('data-culture-id', c.id);
        btn.setAttribute('data-culture-title', c.title);
        btn.setAttribute('data-subgroup', c.subgroup || '_default');
        var typeBadge = '';
        var typeKeys = Object.keys(c.types || {});
        if (typeKeys.length > 0) {
          typeBadge =
            '<span class="text-[6px] text-emerald-500 dark:text-emerald-400 mt-0.5 opacity-0 group-hover/card:opacity-100 transition-opacity">' +
            typeKeys.slice(0, 2).join(', ') +
            (typeKeys.length > 2 ? '...' : '') +
            '</span>';
        }
        var editBtn =
          "<button onclick=\"event.stopPropagation(); if(typeof openWidgetSettings==='function') openWidgetSettings('" +
          c.id +
          '\');" class="absolute top-1.5 right-1.5 p-1.5 rounded-lg bg-white/5 dark:bg-black/20 text-slate-400 dark:text-white/50 hover:text-emerald-500 dark:hover:text-white hover:bg-white/10 dark:hover:bg-black/40 opacity-0 group-hover/card:opacity-100 transition-all z-10 flex items-center justify-center" title="Modificar Widget"><i class="bi bi-gear-fill text-[11px]"></i></button>';

        btn.innerHTML =
          editBtn +
          '<div class="widget-card-icon bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"><i class="bi ' +
          c.icon +
          ' text-xs"></i></div><span class="widget-card-label">' +
          c.title +
          '</span>' +
          typeBadge;
        grid.appendChild(btn);
      });
    } catch (e) {
      console.warn('[CulturesLoader] renderCultureCardGroup error:', e);
    }
  }

  function renderSingleCultureCard(container, c, group) {
    try {
      var btn = document.createElement('div');
      btn.className = 'widget-card relative group/card';
      btn.setAttribute('onclick', "showCultureMiniPanel('" + c.id + "', '" + group.id + "')");
      btn.setAttribute('data-culture-card', 'true');
      btn.setAttribute('data-culture-id', c.id);
      btn.setAttribute('data-culture-title', c.title);
      btn.setAttribute('data-subgroup', c.subgroup || '_default');
      var editBtn =
        "<button onclick=\"event.stopPropagation(); if(typeof openWidgetSettings==='function') openWidgetSettings('" +
        c.id +
        '\');" class="absolute top-1.5 right-1.5 p-1.5 rounded-lg bg-white/5 dark:bg-black/20 text-slate-400 dark:text-white/50 hover:text-emerald-500 dark:hover:text-white hover:bg-white/10 dark:hover:bg-black/40 opacity-0 group-hover/card:opacity-100 transition-all z-10 flex items-center justify-center" title="Modificar Widget"><i class="bi bi-gear-fill text-[11px]"></i></button>';

      btn.innerHTML =
        editBtn +
        '<div class="widget-card-icon bg-emerald-100 dark:bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"><i class="bi ' +
        (c.icon || 'bi-flower1') +
        ' text-[11px]"></i></div><span class="widget-card-label">' +
        c.title +
        '</span>';
      container.appendChild(btn);
    } catch (e) {
      console.warn('[CulturesLoader] renderSingleCultureCard error:', e);
    }
  }

  function renderAll() {
    var doRender = function () {
      renderCultureTabs();
      renderCultureContent();
      renderCultureButtons();
      renderPersistentCultureFilter();
      var modal = document.getElementById('add-widget-modal');
      if (modal && !modal.classList.contains('hidden')) {
        if (typeof window.switchWidgetTab === 'function') {
          try {
            window.switchWidgetTab('kpi');
          } catch (e) {}
        }
      }
    };
    ready(function () {
      doRender();
    });
  }

  function reRender() {
    load().then(function () {
      renderAll();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      load();
    });
  } else {
    load();
  }

  return {
    ready: ready,
    getCulture: getCulture,
    findByTitle: findByTitle,
    convert: convert,
    renderAll: renderAll,
    reRender: reRender,
    getConfig: function () {
      return configData;
    },
  };
})();
