// SPA Router - versao modular com suporte a paginas parciais (HTML)
// Rotas servidas como HTML parcial (fetch com header X-Partial) em vez de JSON
const __htmlRoutes = {
  'simulador-financeiro': '/simulador/financeiro/',
  'simulador-colheita': '/simulador/colheita/',
  'agenda-agricola': '/agenda/agricola/',
  'agenda-pecuaria': '/agenda/pecuaria/',
  'setor-campo': '/setor/campo/',
  'setor-estoque': '/setor/estoque/',
  'alertas-criticos': '/alertas/criticos/',
  'alertas-info': '/alertas/info/',
  'animais-gado': '/animais/gado/',
  'racoes-nutricao': '/animais/racoes/',
  'dashboard-os': '/dashboard/os/',
  'resumo-gerencial': '/dashboard/resumo/',
  'previsao-clima': '/previsao/clima/',
  'previsao-safra': '/previsao/safra/',
  sensores: '/iot/sensores/',
  dispositivos: '/iot/dispositivos/',
  'equipe-agenda': '/equipe/agenda/',
  'equipe-empregados': '/equipe/empregados/',
  'estoque-geral': '/estoque/geral/',
  'estoque-insumos': '/estoque/insumos/',
  'logistica-caminhao': '/logistica/caminhoes/',
  'logistica-rotas': '/logistica/rotas/',
  'perfil-config': '/perfil/config/',
  'config-dia': '/config/dia/',
  'config-noturno': '/config/noturno/',
  'config-sistema': '/config/sistema/',
  'config-page': '/config/page/',
  'erro-report': '/erro/',
  'guia-vegetal': '/guias/vegetal/',
  'guia-animal': '/guias/animal/',
  'guia-aquatica': '/guias/aquatica/',
  'guia-sistemas': '/guias/sistemas/',
  'registro-cafe': '/guias/vegetal/cafe/',
  'registro-cafe-alias': '/registro/cafe/',
  mapa: '/mapa/',
  'adicionar-funcionario': '/funcionario/adicionar/',
  'cadastro-safra': '/cadastro/safra/',
  'cadastro-talhao': '/cadastro/talhao/',
  'cadastro-animal': '/cadastro/animal/',
  'cadastro-apiario': '/cadastro/apiario/',
  'cadastro-insumo': '/cadastro/insumo/',
  'cadastro-maquinario': '/cadastro/maquinario/',
  'cadastro-funcionario': '/cadastro/funcionario/',
  'cadastro-propriedade': '/cadastro/propriedade/',
  'cadastro-financeiro': '/cadastro/financeiro/',
  'cadastro-estoque': '/cadastro/estoque/',
};

const __tabTitles = {
  dashboard: 'Dashboard Premium',
  visao_geral: 'Visão Geral',
  empregados: 'Empregados',
  agenda: 'Agenda',
  agenda_analises: 'Agenda de Análises',
  agenda_producao: 'Agenda de Produção',
  estoque: 'Estoque',
  vendas: 'Vendas',
  apiario: 'Apiário',
  armazem: 'Armazém',
  pecuaria: 'Pecuária',
  financeiro: 'Financeiro',
  compras: 'Compras',
  maquinarios: 'Maquinários',
  novidades: 'Novidades',
  gestao: 'Gestão',
  perfil: 'Perfil',
  'simulador-financeiro': 'Simulador Financeiro',
  'simulador-colheita': 'Simulador de Colheita',
  'agenda-agricola': 'Agenda Agrícola',
  'agenda-pecuaria': 'Agenda Pecuária',
  'setor-campo': 'Setor Campo',
  'setor-estoque': 'Setor Estoque',
  'alertas-criticos': 'Alertas Críticos',
  'alertas-info': 'Alertas Info',
  'racoes-nutricao': 'Rações/Nutrição',
  'previsao-clima': 'Previsão Clima',
  'previsao-safra': 'Previsão Safra',
  sensores: 'Sensores',
  dispositivos: 'Dispositivos',
  'equipe-agenda': 'Agenda Geral',
  'equipe-empregados': 'Empregados',
  'estoque-insumos': 'Insumos',
  'logistica-rotas': 'Rotas',
  'logistica-caminhao': 'Logística',
  'perfil-config': 'Configurações',
  'perfil-sair': 'Sair',
  'config-dia': 'Modo Dia',
  'config-noturno': 'Modo Noturno',
  'config-sistema': 'Modo Sistema',
  config_page: 'Modo Livre',
  'animais-gado': 'Animais Gado',
  'erro-report': 'Reportar Erro',
  'guia-vegetal': 'Guia Vegetal',
  'guia-animal': 'Guia Animal',
  'guia-aquatica': 'Guia Aquática',
  'guia-sistemas': 'Guia Sistemas',
  'registro-cafe': 'Café — Registro de Produção',
  'registro-cafe-alias': 'Café — Registro de Produção',
  mapa: 'Mapa',
  'adicionar-funcionario': 'Adicionar Funcionário',
  'cadastro-safra': 'Cadastro de Safras',
  'cadastro-talhao': 'Cadastro de Talhões',
  'cadastro-animal': 'Cadastro de Animais',
  'cadastro-apiario': 'Cadastro de Apiários',
  'cadastro-insumo': 'Cadastro de Insumos',
  'cadastro-maquinario': 'Cadastro de Maquinários',
  'cadastro-funcionario': 'Cadastro de Funcionários',
  'cadastro-propriedade': 'Cadastro de Propriedades',
  'cadastro-financeiro': 'Cadastro Financeiro',
  'cadastro-estoque': 'Cadastro de Estoque',
  'dashboard-os': 'Dashboard OS',
  'resumo-gerencial': 'Resumo Gerencial',
};

// Mapa URL -> tab (para popstate e interceptacao de links)
const __pathToTab = {
  '/': 'dashboard',
  '/dashboard/': 'dashboard',
  '/empregados/': 'empregados',
  '/agenda/': 'agenda',
  '/agenda/analises/': 'agenda_analises',
  '/agenda/producao/': 'agenda_producao',
  '/estoque/': 'estoque',
  '/vendas/': 'vendas',
  '/apiario/': 'apiario',
  '/armazem/': 'armazem',
  '/pecuaria/': 'pecuaria',
  '/financeiro/': 'financeiro',
  '/compras/': 'compras',
  '/maquinarios/': 'maquinarios',
  '/novidades/': 'novidades',
  '/visao-geral/': 'visao_geral',
  '/gestao/': 'gestao',
  '/perfil/': 'perfil',
};
Object.keys(__htmlRoutes).forEach(function (tab) {
  __pathToTab[__htmlRoutes[tab]] = tab;
});

window.addEventListener('load', function () {
  // Delega para o sistema central de temas (theme-system.js) para evitar flick/duplicação
  if (typeof window.restaurarTemaDoUsuario === 'function') {
    try {
      window.restaurarTemaDoUsuario();
    } catch (e) {}
    try {
      if (window.applyThemeVars) window.applyThemeVars();
    } catch (e) {}
    try {
      var _pm =
        (typeof window.getPreferences === 'function' ? window.getPreferences().theme.mode : null) ||
        localStorage.getItem('theme');
      if (_pm) localStorage.setItem('theme', _pm);
    } catch (e) {}
  } else {
    var preferences = {};
    try {
      var _prefKey = 'ampliagro-preferences';
      if (window.AMPLIAGRO_USER_ID != null)
        _prefKey = 'ampliagro-preferences_u' + window.AMPLIAGRO_USER_ID;
      preferences = JSON.parse(localStorage.getItem(_prefKey) || '{}');
      if (!preferences.theme && _prefKey !== 'ampliagro-preferences') {
        preferences = JSON.parse(localStorage.getItem('ampliagro-preferences') || '{}');
      }
    } catch (e) {
      preferences = {};
    }
    var savedThemeMode =
      typeof window.normalizarModoTema === 'function'
        ? window.normalizarModoTema(
            preferences.theme && preferences.theme.mode ? preferences.theme.mode : null
          )
        : preferences.theme && preferences.theme.mode
          ? preferences.theme.mode
          : null;
    if (!savedThemeMode) {
      var _t = localStorage.getItem('theme');
      savedThemeMode =
        typeof window.normalizarModoTema === 'function' ? window.normalizarModoTema(_t) : _t;
    }
    if (!savedThemeMode || savedThemeMode === 'system') savedThemeMode = 'claro';
    var isDark = false;
    if (savedThemeMode === 'escuro' || savedThemeMode === 'dark') {
      isDark = true;
      document.documentElement.classList.add('dark');
    } else if (savedThemeMode === 'custom') {
      var _customDark =
        preferences.theme && preferences.theme.custom && preferences.theme.custom.dark;
      if (_customDark) {
        isDark = true;
        document.documentElement.classList.add('dark');
      }
    } else if (savedThemeMode === 'claro' || savedThemeMode === 'light') {
      isDark = false;
      document.documentElement.classList.remove('dark');
    }
    if (typeof window.applyThemeVars === 'function') {
      window.applyThemeVars();
    }
    if (savedThemeMode) localStorage.setItem('theme', savedThemeMode);
  }

  // Mapeamento de tabs da navbar Matrix para os tabs existentes
  const tabAliasMap = {
    'simulador-financeiro': 'simulador-financeiro',
    'simulador-colheita': 'simulador-colheita',
    simulador_fin: 'simulador-financeiro',
    simulador_col: 'simulador-colheita',
    'agenda-agricola': 'agenda-agricola',
    'agenda-pecuaria': 'agenda-pecuaria',
    agenda_agri: 'agenda-agricola',
    agenda_pecu: 'agenda-pecuaria',
    'setor-campo': 'setor-campo',
    'setor-estoque': 'setor-estoque',
    setor_campo: 'setor-campo',
    setor_estoque: 'setor-estoque',
    'alertas-criticos': 'alertas-criticos',
    'alertas-info': 'alertas-info',
    alertas_criticos: 'alertas-criticos',
    alertas_info: 'alertas-info',
    'animais-gado': 'animais-gado',
    'racoes-nutricao': 'racoes-nutricao',
    racoes: 'racoes-nutricao',
    'previsao-clima': 'previsao-clima',
    'previsao-safra': 'previsao-safra',
    previsoes: 'previsao-clima',
    'iot-sensores': 'sensores',
    'iot-dispositivos': 'dispositivos',
    sensores: 'sensores',
    dispositivos: 'dispositivos',
    'equipe-agenda': 'equipe-agenda',
    'equipe-empregados': 'equipe-empregados',
    'estoque-geral': 'estoque-geral',
    'estoque-insumos': 'estoque-insumos',
    'logistica-caminhao': 'logistica-caminhao',
    'logistica-rotas': 'logistica-rotas',
    logistica: 'logistica-caminhao',
    'perfil-config': 'perfil-config',
    'perfil-sair': 'perfil-sair',
    'config-dia': 'custom-config',
    'config-noturno': 'custom-config',
    'config-sistema': 'config-sistema',
    config_page: 'perfil-config',
    'erro-report': 'erro-report',
    'guia-vegetal': 'guia-vegetal',
    'guia-animal': 'guia-animal',
    'guia-aquatica': 'guia-aquatica',
    'guia-sistemas': 'guia-sistemas',
    'cadastro-safra': 'cadastro-safra',
    'cadastro-talhao': 'cadastro-talhao',
    'cadastro-animal': 'cadastro-animal',
    'cadastro-apiario': 'cadastro-apiario',
    'cadastro-insumo': 'cadastro-insumo',
    'cadastro-maquinario': 'cadastro-maquinario',
    'cadastro-funcionario': 'cadastro-funcionario',
    'cadastro-propriedade': 'cadastro-propriedade',
    'cadastro-financeiro': 'cadastro-financeiro',
    'cadastro-estoque': 'cadastro-estoque',
    'dashboard-os': 'dashboard-os',
    'resumo-gerencial': 'resumo-gerencial',
  };

  document.querySelectorAll('[data-tab]').forEach((link) => {
    if (link.classList && link.classList.contains('sub-tab')) return;
    link.addEventListener('click', (e) => {
      e.preventDefault();
      let tabName = link.getAttribute('data-tab');
      tabName = tabAliasMap[tabName] || tabName;
      switchTab(tabName, true);
    });
  });

  // Interceptador global de links internos (navegacao SPA sem recarregar)
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
      return;
    var a = e.target.closest ? e.target.closest('a') : null;
    if (!a) return;
    if (
      a.hasAttribute('data-tab') ||
      a.hasAttribute('data-bs-toggle') ||
      a.getAttribute('target') === '_blank'
    )
      return;
    if (a.hasAttribute('download')) return;
    var href = a.getAttribute('href');
    if (!href) return;
    if (
      href.startsWith('#') ||
      href.startsWith('mailto:') ||
      href.startsWith('tel:') ||
      href.startsWith('javascript:')
    )
      return;
    var url;
    try {
      url = new URL(href, window.location.origin);
    } catch (err) {
      return;
    }
    if (url.origin !== window.location.origin) return;
    if (url.pathname.startsWith('/api/')) return;
    var tab =
      __pathToTab[url.pathname] ||
      __pathToTab[url.pathname + '/'] ||
      __pathToTab[url.pathname.replace(/\/$/, '')];
    if (!tab) {
      // Fallback SPA para rotas dinamicas de guias/culturas/cadastros que nao estao no mapa estatico
      // Ex: /guias/vegetal/soja/, /registro/soja/, /cadastro/safra/ ja esta no mapa, mas slug dinamico nao
      var p = url.pathname;
      var isGenericHtmlRoute =
        (p.startsWith('/guias/') &&
          !/^\/guias\/vegetal\/\d+\/?$/.test(p) &&
          !/^\/registro\/[^\/]+\/?$/.test(p)) ||
        p.startsWith('/cadastro/') ||
        p.startsWith('/apiario/') ||
        p.startsWith('/caderno/') ||
        p.startsWith('/mapa/');
      // Se painel cultura estiver aberto, não navega - apenas atualiza URL via pushState (SPA panel)
      if (p.match(/^\/guias\/vegetal\/\d+/) || p.match(/^\/registro\//)) {
        if (document.getElementById('culturaDetail')?.classList.contains('active')) {
          e.preventDefault();
          window.history.pushState({ cultura: p }, '', p);
          console.log('[SPA] URL cultura atualizado sem reload', p);
          return;
        }
        // Se não tem painel, deixa o redirect do servidor (que agora manda para /guias/vegetal/)
      }
      if (isGenericHtmlRoute) {
        e.preventDefault();
        // Trata como partial generico: fetch com X-Partial e injeta no #content, esconde appbar
        (function () {
          var appbar = document.getElementById('dashboard-appbar');
          if (appbar) appbar.style.setProperty('display', 'none', 'important');
          var widgetBar = document.getElementById('widget-bar');
          if (widgetBar) widgetBar.style.setProperty('display', 'none', 'important');
          var content = document.getElementById('content');
          if (content)
            content.innerHTML =
              '<div class="skeleton-loader p-4"><div class="skeleton-line mb-3" style="height:24px;width:40%;background:linear-gradient(90deg,#e5edf3 25%,#f0f5fa 50%,#e5edf3 75%);border-radius:8px;"></div></div>';
          fetch(p, {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-Partial': '1' },
            cache: 'default',
          })
            .then(function (res) {
              if (!res.ok) throw new Error('Partial not available');
              return res.text();
            })
            .then(function (html) {
              if (content) renderPartialHtml(html, content);
              window.history.pushState({ tab: p }, '', p);
              if (typeof window.updateNavActive === 'function') window.updateNavActive();
            })
            .catch(function (err) {
              console.error('SPA generic partial error', err);
              window.location.href = p;
            });
        })();
        return;
      }
      return;
    }
    e.preventDefault();
    switchTab(tab, true);
  });

  // Intercepta cliques em cards de cultura (div.cultura-card com onclick window.location.href)
  // que nao sao <a> e causavam full reload removendo a dashboard_appbar
  document.addEventListener(
    'click',
    function (e) {
      var card = e.target.closest('.cultura-card');
      var quickBtn = e.target.closest('.cultura-quick-add');
      var target = card || quickBtn;
      if (!target) return;
      // O card pode ter sido clicado via quickBtn dentro dele
      var actualCard = target.closest('.cultura-card') || target;
      if (!actualCard) return;
      var hrefMatch = (actualCard.getAttribute('onclick') || '').match(/'([^']+)'/);
      var href = hrefMatch ? hrefMatch[1] : null;
      if (!href) {
        var cid = actualCard.getAttribute('data-cultura-id') || actualCard.dataset.culturaId;
        if (cid) href = '/guias/vegetal/' + cid + '/';
      }
      if (!href) return;
      // So intercepta guias/registro
      if (!(href.startsWith('/guias/') || href.startsWith('/registro/'))) return;
      try {
        if (window.dashboardLog)
          window.dashboardLog('spa:cultura-card', {
            href: href,
            caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 80),
          });
      } catch (e) {}
      // Evita o inline onclick fazer full reload
      e.preventDefault();
      e.stopPropagation();
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      // SPA fetch generico
      var appbar2 = document.getElementById('dashboard-appbar');
      if (appbar2) appbar2.style.setProperty('display', 'none', 'important');
      var widgetBar2 = document.getElementById('widget-bar');
      if (widgetBar2) widgetBar2.style.setProperty('display', 'none', 'important');
      var content2 = document.getElementById('content');
      if (content2)
        content2.innerHTML =
          '<div class="skeleton-loader p-4"><div class="skeleton-line mb-3" style="height:24px;width:40%;background:linear-gradient(90deg,#e5edf3 25%,#f0f5fa 50%,#e5edf3 75%);border-radius:8px;"></div></div>';
      fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-Partial': '1' } })
        .then(function (res) {
          if (!res.ok) throw new Error('Partial not available');
          return res.text();
        })
        .then(function (html) {
          if (content2) renderPartialHtml(html, content2);
          window.history.pushState({ tab: href }, '', href);
          if (typeof window.updateNavActive === 'function') window.updateNavActive();
        })
        .catch(function (err) {
          console.error('SPA cultura card error', err);
          window.location.href = href;
        });
    },
    true
  );

  const pathname = window.location.pathname;

  // Handle QR code tracking route
  var trackMatch = pathname.match(/\/rastrear\/([^\/]+)\/([^\/]+)/);
  if (trackMatch) {
    var tipo = trackMatch[1];
    var id = trackMatch[2];
    setTimeout(function () {
      if (typeof window.handleTrackingRoute === 'function') {
        window.handleTrackingRoute(tipo, id);
      }
    }, 1000);
  }

  // Rotas dinamicas (ex: /guias/vegetal/<id>/) nao estao em __pathToTab:
  // sao paginas renderizadas pelo servidor e nao devem ser sobrescritas.
  const initialTab = __pathToTab[pathname];
  // No load inicial, rotas HTML (secoes) ja vieram renderizadas pelo servidor;
  // apenas rotas JSON precisam buscar dados via API.
  // Dashboard é renderizado pelo index.html (initWidgetsMatrix) — não via SPA para evitar duplo render 0->9 visto no console com F12
  if (initialTab && !__htmlRoutes[initialTab] && initialTab !== 'dashboard') {
    switchTab(initialTab, false);
  } else {
    // Fix: base.html agora sempre inclui dashboard_appbar no DOM; esconde se nao for dashboard
    var isDash =
      pathname === '/' ||
      pathname === '' ||
      pathname === '/dashboard/' ||
      pathname.indexOf('index') > -1 ||
      initialTab === 'dashboard';
    if (!isDash) {
      var _ab0 = document.getElementById('dashboard-appbar');
      if (_ab0) _ab0.style.setProperty('display', 'none', 'important');
      var _wb0 = document.getElementById('widget-bar');
      if (_wb0) _wb0.style.setProperty('display', 'none', 'important');
    } else {
      // No dashboard, garante visivel (caso tenha vindo de cache escondido)
      var _ab1 = document.getElementById('dashboard-appbar');
      if (_ab1) _ab1.style.setProperty('display', '', 'important');
      var _wb1 = document.getElementById('widget-bar');
      if (_wb1) _wb1.style.setProperty('display', '', 'important');
    }
  }
});

// Recalcula o pill ativo da navbar conforme o pathname atual (SPA usa pushState,
// entao o highlight precisa ser atualizado apos cada navegacao, nao so no load).
window.updateNavActive = function () {
  var path = window.location.pathname;
  var pills = document.querySelectorAll('.nav-pill[data-pill]');
  pills.forEach(function (p) {
    p.classList.remove('is-active');
  });
  pills.forEach(function (p) {
    var pill = p.getAttribute('data-pill');
    if (
      (pill === 'dashboard' && (path === '/' || path === '' || path.indexOf('index') > -1)) ||
      path.indexOf(pill) > -1
    ) {
      p.classList.add('is-active');
    }
  });
  var dd = document.getElementById('user-dropdown');
  if (dd) {
    dd.classList.remove('is-open');
  }
};

var __tabAnimTimer = null;
function suTabEnter(content) {
  if (!content) return;
  content.classList.add('tab-switching');
  if (__tabAnimTimer) clearTimeout(__tabAnimTimer);
  __tabAnimTimer = setTimeout(function () {
    content.classList.remove('tab-switching');
  }, 500);
}

async function switchTab(tabName, pushToHistory = true) {
  try {
    if (window.dashboardLog)
      window.dashboardLog('spa:switchTab', {
        tab: tabName,
        push: pushToHistory,
        from: location.pathname,
        caller: ((new Error().stack || '').split('\n')[2] || '').trim().substring(0, 100),
      });
    else console.log('[Dashboard] spa:switchTab', tabName);
  } catch (e) {}
  // SPA: ao trocar de pagina o .matrix-container eh destruido; limpa cache do drag (evita teleport)
  try {
    if (typeof window._resetMatrixContainerCache === 'function')
      window._resetMatrixContainerCache();
  } catch (e) {}
  // Aborta qualquer drag/resize pendente (evita ghost preso ao voltar)
  try {
    var _ds = window._dragState || null;
    // _dragState eh privado no index.html; tenta limpar via variavel global exposta
    if (document.querySelectorAll('.drag-ghost').length) {
      document.querySelectorAll('.drag-ghost').forEach(function (g) {
        g.remove();
      });
    }
    document
      .querySelectorAll(
        '.bento-block.drag-origin, .bento-block.drop-target, .bento-block.drop-target-invalid'
      )
      .forEach(function (el) {
        el.classList.remove('drag-origin', 'drop-target', 'drop-target-invalid');
        el.style.transition = '';
      });
    document.querySelectorAll('.grid-drop-hint').forEach(function (el) {
      el.remove();
    });
  } catch (e) {}
  document.querySelectorAll('.dropdown-menu a[data-tab]').forEach((a) => {
    a.classList.remove('active');
  });

  document.querySelectorAll('[data-tab="' + tabName + '"]').forEach((a) => {
    a.classList.add('active');
  });

  document.title = 'Ampliagro - ' + (__tabTitles[tabName] || tabName);

  const appbar = document.getElementById('dashboard-appbar');
  if (appbar)
    appbar.style.setProperty('display', tabName === 'dashboard' ? '' : 'none', 'important');

  const widgetBar = document.getElementById('widget-bar');
  if (widgetBar)
    widgetBar.style.setProperty('display', tabName === 'dashboard' ? '' : 'none', 'important');

  const content = document.getElementById('content');
  if (!content) return;
  const isDark = document.documentElement.classList.contains('dark');
  const skeletonBg = isDark
    ? 'linear-gradient(90deg, #334155 25%, #475569 50%, #334155 75%)'
    : 'linear-gradient(90deg, #e5edf3 25%, #f0f5fa 50%, #e5edf3 75%)';
  if (tabName !== 'dashboard') {
    content.innerHTML =
      '<div class="skeleton-loader p-4">' +
      '<div class="skeleton-line mb-3" style="height: 24px; width: 40%; background: ' +
      skeletonBg +
      '; border-radius: 8px;"></div>' +
      '<div class="skeleton-line mb-3" style="height: 16px; width: 60%; background: ' +
      skeletonBg +
      '; border-radius: 6px;"></div>' +
      '<div class="skeleton-card" style="height: 180px; background: ' +
      skeletonBg +
      '; border-radius: 12px; margin-top: 20px;"></div>' +
      '</div>';
  }

  // Rota HTML parcial (pagina standalone carregada sem recarregar)
  const htmlRoute = __htmlRoutes[tabName];
  if (htmlRoute) {
    try {
      const res = await fetch(htmlRoute, {
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-Partial': '1' },
      });
      if (res.status === 401 || res.status === 403) {
        content.innerHTML = '';
        window.location.href = '/login/';
        return;
      }
      if (!res.ok) throw new Error('Partial not available');
      const html = await res.text();
      renderPartialHtml(html, content);
      suTabEnter(content);
      if (pushToHistory) {
        window.history.pushState({ tab: tabName }, '', htmlRoute);
      }
      if (typeof window.updateNavActive === 'function') window.updateNavActive();
    } catch (err) {
      console.error('SPA partial load error:', err);
      content.innerHTML =
        '<div class="container-fluid mb-5 px-2">' +
        '<div class="page-hero card border-0 shadow-sm p-4 mb-4 bg-ncs-50 dark:bg-ncs-900 card-override border-ncs-900/20 dark:border-ncs-50/20 rounded-md">' +
        '<div class="d-flex justify-content-between align-items-start flex-wrap gap-3">' +
        '<div>' +
        '<div class="d-flex align-items-center mb-2">' +
        '<span class="badge badge-success badge-pill px-3 py-2 mr-2 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-sparkles"></i> Centro de comando ativo</span>' +
        '<span class="small text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold">Erro ao carregar página</span>' +
        '</div>' +
        '<h3 class="font-weight-bold text-ncs-900 dark:text-ncs-50 mb-1">' +
        (__tabTitles[tabName] || tabName) +
        '</h3>' +
        '<small class="text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold">Clique no link novamente para tentar.</small>' +
        '</div>' +
        '</div>' +
        '</div>';
    }
    suTabEnter(content);
    return;
  }

  const endpoints = {
    dashboard: '/api/dashboard/',
    visao_geral: '/api/visao-geral/',
    empregados: '/api/funcionarios/',
    agenda: '/api/agenda/',
    agenda_analises: '/api/agenda-analises/',
    agenda_producao: '/api/agenda-producao/',
    estoque: '/api/estoque/',
    vendas: '/api/vendas/',
    apiario: '/api/apiario/',
    armazem: '/api/armazem/',
    pecuaria: '/api/pecuaria/',
    financeiro: '/api/financeiro/',
    compras: '/api/compras/',
    maquinarios: '/api/maquinarios/',
    novidades: '/api/novidades/',
    gestao: '/api/gestao/',
    perfil: '/api/perfil/',
    previsao_clima: '/api/previsao-clima/',
    previsao_safra: '/api/previsao-safra/',
    sensores: '/api/sensores/',
    dispositivos: '/api/dispositivos/',
    estoque_insumos: '/api/insumos/',
    logistica_rotas: '/api/rotas/',
  };

  // Guia Vegetal sub-tabs sao internos da pagina, nao SPA tabs — ignora para evitar 404 /api/graos/
  var guiaSubTabs = [
    'graos',
    'frutas',
    'citricos',
    'hortalicas',
    'tuberculos',
    'ervas',
    'leguminosas',
    'oleaginosas',
    'frutas_bosque',
    'especiarias',
    'medicinais',
    'panc',
    'trepadeiras',
    'cana',
    'fibras',
    'nativas',
    'outras',
  ];
  if (guiaSubTabs.indexOf(tabName) !== -1) {
    console.warn('[SPA] sub-tab guia ignorado:', tabName);
    return;
  }
  if (!endpoints[tabName] && !__htmlRoutes[tabName]) {
    console.warn('[SPA] tab desconhecido ignorado:', tabName);
    return;
  }

  const endpoint = endpoints[tabName] || '/api/' + tabName + '/';

  let data = null;

  try {
    if (tabName !== 'dashboard') {
      const res = await fetch(endpoint, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });

      if (res.status === 401 || res.status === 403) {
        content.innerHTML = '';
        window.location.href = '/login/';
        return;
      }

      if (!res.ok) throw new Error('API not available');
      data = await res.json();
    }

    const renderMap = {
      dashboard:
        typeof renderDashboardDesktop === 'function'
          ? renderDashboardDesktop
          : typeof renderDashboardTab === 'function'
            ? renderDashboardTab
            : null,
      visao_geral: typeof renderVisaoGeralTab === 'function' ? renderVisaoGeralTab : null,
      empregados: typeof renderEmpregadosTab === 'function' ? renderEmpregadosTab : null,
      agenda: typeof renderAgendaTab === 'function' ? renderAgendaTab : null,
      agenda_analises:
        typeof renderAgendaAnalisesTab === 'function' ? renderAgendaAnalisesTab : null,
      agenda_producao:
        typeof renderAgendaProducaoTab === 'function' ? renderAgendaProducaoTab : null,
      estoque: typeof renderEstoqueTab === 'function' ? renderEstoqueTab : null,
      vendas: typeof renderVendasTab === 'function' ? renderVendasTab : null,
      apiario: typeof renderApiarioTab === 'function' ? renderApiarioTab : null,
      armazem: typeof renderArmazemTab === 'function' ? renderArmazemTab : null,
      pecuaria: typeof renderPecuariaTab === 'function' ? renderPecuariaTab : null,
      financeiro: typeof renderFinanceiroTab === 'function' ? renderFinanceiroTab : null,
      compras: typeof renderComprasTab === 'function' ? renderComprasTab : null,
      maquinarios: typeof renderMaquinariosTab === 'function' ? renderMaquinariosTab : null,
      novidades: typeof renderNovidadesTab === 'function' ? renderNovidadesTab : null,
      gestao: typeof renderGestaoTab === 'function' ? renderGestaoTab : null,
      perfil: typeof renderPerfilTab === 'function' ? renderPerfilTab : null,
      'estoque-insumos':
        typeof renderEstoqueInsumosTab === 'function' ? renderEstoqueInsumosTab : null,
    };

    // Para dashboard, preferir sistema principal (index.html) quando disponível - evita conflito de grid 9 vs 64
    if (tabName === 'dashboard') {
      // #region agent log
      if (window.__dbgNav)
        window.__dbgNav('B', 'spa.js:switchTab', 'enter dashboard', {
          theme: window.__dbgThemeSnap ? window.__dbgThemeSnap() : null,
          widgetCount: Object.keys(window.widgets || {}).length,
          matrixInit: !!window._widgetsMatrixInitialized,
          hasMatrix: !!(content && content.querySelector && content.querySelector('.matrix-container')),
        });
      // #endregion
      // Se o sistema principal (index.html) está carregado, reutiliza-o (unifica storage e grid 64)
      if (
        typeof window.renderWidgetsOnMatrix === 'function' &&
        typeof window.GRID_COLS !== 'undefined'
      ) {
        // Garante container no content (caso conteúdo tenha sido trocado por partial)
        var hasMatrix = content.querySelector('.matrix-container');
        if (!hasMatrix) {
          // SPA voltou ao dashboard após estar em guia — limpa charts antigos presos a canvas removido
          try {
            if (window.chartInstances) {
              Object.values(window.chartInstances).forEach(function (c) {
                try {
                  c.destroy();
                } catch (e) {}
              });
            }
          } catch (e) {}
          try {
            if (window.widgetbarState && window.widgetbarState.chartInstances) {
              Object.values(window.widgetbarState.chartInstances).forEach(function (c) {
                try {
                  c.destroy();
                } catch (e) {}
              });
              window.widgetbarState.chartInstances = {};
            }
          } catch (e) {}
          try {
            if (typeof window._resetMatrixContainerCache === 'function')
              window._resetMatrixContainerCache();
          } catch (e) {}
          content.innerHTML =
            '<div class="matrix-container" style="--grid-cols: ' +
            window.GRID_COLS +
            '; --grid-rows: ' +
            window.GRID_ROWS +
            ';"></div>';
        }
        try {
          if (typeof window.initWidgetsMatrix === 'function') {
            if (!window._widgetsMatrixInitialized) {
              // Aguarda init absoluto terminar (evita render com 0 widgets visto no console: spa:switchTab 0 -> render 0 antes do CulturesLoader)
              if (window._widgetsMatrixPromise) await window._widgetsMatrixPromise;
              else await window.initWidgetsMatrix();
            } else if (typeof window.renderWidgetsOnMatrix === 'function') {
              // Só renderiza se já tem widgets (evita flick 0 -> 9)
              var _w = window.widgets || {};
              if (Object.keys(_w).length) {
                window.renderWidgetsOnMatrix();
                if (typeof window.adjustMatrixHeight === 'function') window.adjustMatrixHeight();
              }
            }
          }
        } catch (e) {
          console.warn('initWidgetsMatrix/renderWidgetsOnMatrix falhou no spa.js', e);
        }
        try {
          if (typeof window.initChartsForWidgets === 'function')
            setTimeout(function () {
              window.initChartsForWidgets();
            }, 80);
        } catch (e) {}
        // Reidrata tema sem flick
        try {
          if (window.applyThemeVars) window.applyThemeVars();
        } catch (e) {}
        // Sincroniza widgetbar editing se necessário
        try {
          if (
            typeof window.syncWidgetEditDOM === 'function' &&
            (window.widgetEditMode || window.customMode)
          )
            window.syncWidgetEditDOM(true);
        } catch (e) {}
        // Garante que a WIDGET-BAR (dashboard_appbar) fique visivel e sincronizada ao voltar ao dashboard
        // (fix para bug onde cultura/guia via full reload removia o elemento e SPA só fazia display toggle)
        try {
          var _abFix = document.getElementById('dashboard-appbar');
          if (_abFix) {
            _abFix.style.setProperty('display', '', 'important');
            // Se estava em edicao, garante classe editing e botoes
            var _isEditFix = !!(
              window.widgetEditMode ||
              window.customMode ||
              window.widgetbarState?.isCustomMode
            );
            if (_isEditFix) {
              _abFix.classList.add('editing');
              var _secFix = document.getElementById('edit-mode-section');
              if (_secFix) _secFix.classList.remove('hidden');
              var _btnFix = document.getElementById('custom-mode-btn');
              if (_btnFix) {
                _btnFix.classList.add('active');
                var _ic = _btnFix.querySelector('i');
                if (_ic) _ic.className = 'bi bi-check2';
                _btnFix.title = 'Salvar Layout';
              }
              if (
                typeof window.WidgetBarIntelligent !== 'undefined' &&
                window.WidgetBarIntelligent.refresh
              ) {
                try {
                  window.WidgetBarIntelligent.refresh();
                } catch (e2) {}
              }
              // Força re-ataque do drag no novo container (fix teleport)
              if (typeof window.initWidgetDragging === 'function') {
                try {
                  setTimeout(function () {
                    window.initWidgetDragging();
                  }, 30);
                } catch (e2) {}
              }
            } else {
              // Fora de edicao: garante que nao ficou em estado editing preso
              var _secFix2 = document.getElementById('edit-mode-section');
              if (_secFix2) _secFix2.classList.add('hidden');
            }
          } else {
            // Elemento nao existe (caso raro de template antigo sem fix base.html) — recarrega dashboard
            console.warn('dashboard-appbar missing on dashboard return, reloading');
            window.location.href = '/';
            return;
          }
        } catch (e) {}
        // ABSOLUTO: nao forca segundo reload apos navegacao — dashboard ja esta correto com 1 render
      } else {
        // Sistema principal não carregado (entrou direto em /guias/* ou outra página e veio via SPA)
        // — o renderDashboardDesktop fallback é um grid 6-widget simples e buga; força reload real para pegar o dashboard absoluto com 128 cols, bg, meta etc.
        try {
          console.warn(
            'Main matrix not loaded (no GRID_COLS), reloading dashboard for real render'
          );
        } catch (e) {}
        window.location.href = '/';
        return;
      }
    } else if (renderMap[tabName]) {
      content.innerHTML = renderMap[tabName](data);
    } else {
      content.innerHTML =
        '<div class="container-fluid mb-5 px-2">' +
        '<div class="page-hero card border-0 shadow-sm p-4 mb-4 bg-ncs-50 dark:bg-ncs-900 card-override border-ncs-900/20 dark:border-ncs-50/20 rounded-md">' +
        '<div class="d-flex justify-content-between align-items-start flex-wrap gap-3">' +
        '<div>' +
        '<div class="d-flex align-items-center mb-2">' +
        '<span class="badge badge-success badge-pill px-3 py-2 mr-2 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-sparkles"></i> Centro de comando ativo</span>' +
        '<span class="small text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold"> Sem dados da API</span>' +
        '</div>' +
        '<h3 class="font-weight-bold text-ncs-900 dark:text-ncs-50 mb-1">' +
        (__tabTitles[tabName] || tabName) +
        '</h3>' +
        '<small class="text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold">Nenhum registro localizado no momento.</small>' +
        '</div>' +
        '</div>' +
        '</div>';
    }

    suTabEnter(content);
    if (typeof renderCharts === 'function') {
      renderCharts();
    }
    if (typeof initChartsForWidgets === 'function') {
      setTimeout(initChartsForWidgets, 100);
    }
    if (typeof initSpecificCharts === 'function') {
      setTimeout(initSpecificCharts, 150);
    }

    if (pushToHistory) {
      let url;
      if (tabName === 'agenda_analises') {
        url = '/agenda/analises/';
      } else if (tabName === 'agenda_producao') {
        url = '/agenda/producao/';
      } else if (tabName === 'dashboard') {
        url = '/';
      } else {
        url = '/' + tabName + '/';
      }
      window.history.pushState({ tab: tabName }, '', url);
    }
    if (typeof window.updateNavActive === 'function') window.updateNavActive();
  } catch (err) {
    console.error('SPA switchTab error:', err);
    content.innerHTML =
      '<div class="container-fluid mb-5 px-2">' +
      '<div class="page-hero card border-0 shadow-sm p-4 mb-4 bg-ncs-50 dark:bg-ncs-900 card-override border-ncs-900/20 dark:border-ncs-50/20 rounded-md">' +
      '<div class="d-flex justify-content-between align-items-start flex-wrap gap-3">' +
      '<div>' +
      '<div class="d-flex align-items-center mb-2">' +
      '<span class="badge badge-success badge-pill px-3 py-2 mr-2 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200"><i class="bi bi-sparkles"></i> Centro de comando ativo</span>' +
      '<span class="small text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold">Erro de conexão</span>' +
      '</div>' +
      '<h3 class="font-weight-bold text-ncs-900 dark:text-ncs-50 mb-1">' +
      (__tabTitles[tabName] || tabName) +
      '</h3>' +
      '<small class="text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold">Tentando reconectar...</small>' +
      '</div>' +
      '</div>' +
      '</div>';
    suTabEnter(content);
  }
}

// Renderiza um fragmento HTML parcial (marcado por comentarios PARTIAL)
function renderPartialHtml(html, content) {
  const extract = (start, end) => {
    const i = html.indexOf(start);
    if (i < 0) return '';
    const j = html.indexOf(end, i + start.length);
    if (j < 0) return '';
    return html.substring(i + start.length, j);
  };

  const cssHtml = extract('<!--PARTIAL:CSS-->', '<!--/PARTIAL:CSS-->');
  let contentHtml = extract('<!--PARTIAL:CONTENT-->', '<!--/PARTIAL:CONTENT-->');
  const scriptsHtml = extract('<!--PARTIAL:SCRIPTS-->', '<!--/PARTIAL:SCRIPTS-->');

  if (!contentHtml && html.indexOf('<html') >= 0) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const newContent = doc.getElementById('content');
    if (newContent) {
      contentHtml = newContent.innerHTML;
    } else {
      window.location.reload();
      return;
    }
  } else if (!contentHtml) {
    contentHtml = html;
  }
  const title = extract('<title data-partial-title>', '</title>').trim();
  if (title) document.title = title;

  // Injeta CSS (links e estilos) uma unica vez no head
  const cssDoc = new DOMParser().parseFromString(cssHtml, 'text/html');
  cssDoc.querySelectorAll('link[rel="stylesheet"]').forEach((link) => {
    const href = link.getAttribute('href');
    if (!href) return;
    const exists = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).some(
      (l) => l.getAttribute('href') === href
    );
    if (!exists) {
      const el = document.createElement('link');
      el.rel = 'stylesheet';
      el.href = href;
      document.head.appendChild(el);
      // #region agent log
      if (window.__dbgNav)
        window.__dbgNav('B', 'spa.js:renderPartialHtml', 'injected stylesheet', {
          href: String(href).slice(0, 180),
          sheetCount: document.querySelectorAll('link[rel="stylesheet"]').length,
        });
      // #endregion
    }
  });
  cssDoc.querySelectorAll('style').forEach((style) => {
    const text = style.textContent;
    const dup = Array.from(document.head.querySelectorAll('style')).some(
      (s) => s.textContent === text
    );
    if (!dup) document.head.appendChild(style.cloneNode(true));
  });

  content.innerHTML = contentHtml;
  window.scrollTo(0, 0);
  // Reidrata tema após injeção de partial (custom precisa re-aplicar --theme-* vars)
  try {
    if (typeof window.restaurarTemaDoUsuario === 'function') {
      // Re-aplica modo salvo sem trigger extra de storage (restaura custom se necessário)
      window.restaurarTemaDoUsuario();
    }
    if (window.applyThemeVars) window.applyThemeVars();
  } catch (e) {}
  try {
    var m = window.modoAtualDom ? window.modoAtualDom() : null;
    if (window.syncModeDropdown) window.syncModeDropdown(m);
  } catch (e) {}

  // Hibrido PWA: escuta HTML_UPDATE do SW e aplica diff minimo sem reload
  if ('serviceWorker' in navigator && !window._spaHybridBound) {
    window._spaHybridBound = true;
    navigator.serviceWorker.addEventListener('message', function (e) {
      if (e.data && e.data.type === 'HTML_UPDATE' && e.data.html) {
        try {
          var url = e.data.url || '';
          console.log(
            '[SPA Hibrido] received HTML_UPDATE',
            url,
            'panelActive',
            document.getElementById('culturaDetail')?.classList.contains('active')
          );
          // não sobrescreve se painel cultura estiver aberto (evita fechar painel) - qualquer URL
          if (document.getElementById('culturaDetail')?.classList.contains('active')) {
            console.log('[SPA Hibrido] skip HTML_UPDATE - painel aberto', url);
            return;
          }
          if (url && location.href.indexOf(new URL(url).pathname) >= 0) {
            // diff simples: se html contem #content, atualiza só #content
            var doc = new DOMParser().parseFromString(e.data.html, 'text/html');
            var newContent = doc.querySelector('#content');
            var cur = document.querySelector('#content');
            if (newContent && cur && newContent.innerHTML !== cur.innerHTML) {
              // preserva scroll e foco
              var scroll = window.scrollY;
              cur.innerHTML = newContent.innerHTML;
              window.scrollTo(0, scroll);
              console.log('[SPA Hibrido] HTML atualizado em background', url);
            }
          }
        } catch (err) {
          console.warn('HTML_UPDATE fail', err);
        }
      }
    });
  }
  // Executa scripts (src em ordem + inline), em escopo global
  const scriptDoc = new DOMParser().parseFromString(scriptsHtml, 'text/html');
  const scripts = Array.from(scriptDoc.querySelectorAll('script'));
  let chain = Promise.resolve();
  // Um `<script src>` criado para executar um partial JA CORREU quando o
  // `onload` dispara. Deixa-lo no `<body>` era crescimento sem limite:
  // MEDIDO 2026-10-06, 16 `<script>` de `guide.js` empilhados no body ao
  // fim de meia hora de navegacao. Nao era memoria util — era lixo que
  // impedia o garbage collector de recolher o elemento.
  const carregarEdisparar = (resolve, src) => {
    const el = document.createElement('script');
    el.src = src;
    el.async = false;
    const limpar = () => {
      if (el.parentNode) el.parentNode.removeChild(el);
      resolve();
    };
    el.onload = limpar;
    el.onerror = limpar;
    document.body.appendChild(el);
  };
  scripts.forEach((script) => {
    if (script.src) {
      chain = chain.then(() => new Promise((resolve) => carregarEdisparar(resolve, script.src)));
    } else if (script.textContent.trim()) {
      const t = (script.getAttribute('type') || '').toLowerCase();
      if (t && t !== 'text/javascript' && t !== 'application/javascript') return;
      chain = chain.then(() => execPartialInlineScript(script.textContent));
    }
  });
  // Scripts que vieram dentro do content via includes (ex: _edit_modal.html) não executam via innerHTML — executa manualmente
  const contentScripts = Array.from(content.querySelectorAll('script')).filter((s) => {
    const t = (s.getAttribute('type') || '').toLowerCase();
    return !t || t === 'text/javascript' || t === 'application/javascript';
  });
  contentScripts.forEach((s) => {
    if (s.src) {
      const src = s.src || s.getAttribute('src');
      if (src) {
        chain = chain.then(
          () => new Promise((resolve) => carregarEdisparar(resolve, src))
        );
      }
    } else if (s.textContent.trim()) {
      const code = s.textContent;
      s.remove();
      chain = chain.then(() => execPartialInlineScript(code));
    }
  });
}

// Executa um script inline do partial, ISOLADO.
//
// POR QUE NAO E' `new Function(...)`
// =============================
// A versao anterior montava o codigo numa string e chamava `new Function`.
// A CSP do projeto NAO tem `'unsafe-eval'` em `script-src` — tem
// `'wasm-unsafe-eval'`, que e' outra coisa. Resultado medido: o browser
// recusava TODOS os scripts inline das paginas, uma vez por navegacao:
//
//     EvalError: Evaluating a string as JavaScript violates the following
//     Content Security Policy directive because 'unsafe-eval' is not an
//     allowed source of script
//
// O que o produtor via: os KPIs da guia vegetal em "—", os badges das
// culturas em 0, e o `window._guideStats` nunca publicado. A correcao do
// backend estava certa e mesmo assim a pagina ficava sem dados, porque
// o codigo que publicava os dados nunca chegou a correr.
//
// A via sem `eval`
// =================
// Um `<script>` de VERDADE, inserido no documento, executa sem `eval` — e
// por isso que `script-src 'self' 'unsafe-inline'` o permite. E o browser
// trata-o exatamente como trata o script de uma pagina normal.
//
// O isolamento que a versao anterior buscava (`const`/`let` nao colidem
// entre visitas) mantem-se: cada execucao cria um `<script>` NOVO, logo
// tem o seu proprio escopo de bloco. As `function` declarations viram
// globais porque o codigo corre em escopo global — que e' o que o
// `onclick=` inline do template precisa.
//
// `DOMContentLoaded` ja passou (a SPA carrega depois do load), por isso
// quem o espera tem de ser disparado a mao — e e' o que se faz aqui.
function execPartialInlineScript(code) {
  if (!code || !code.trim()) return;

  var script = document.createElement('script');
  script.textContent = code;
  // Fica marcado para quem precisar saber que este script correu.
  script.setAttribute('data-spa-partial', '1');
  // `DOMContentLoaded` ja passou quando a SPA navega. O `addEventListener`
  // de um script recem-criado ouve o evento para sempre, e quem registou
  // `DOMContentLoaded` ficaria a espera de algo que nao volta a acontecer.
  // E' aqui que nascia o "a pagina fica em loading para sempre".
  var origAdd = document.addEventListener;
  document.addEventListener = function (type, fn) {
    if (type === 'DOMContentLoaded') {
      setTimeout(fn, 0);
      return;
    }
    return origAdd.call(this, type, fn);
  };
  try {
    (document.head || document.body).appendChild(script);
  } catch (e) {
    console.error('SPA partial inline script falhou:', e);
  } finally {
    document.addEventListener = origAdd;
    // O `<script>` ja correu; tira-lo do DOM liberta a memoria e nao
    // altera o que ja foi feito.
    if (script.parentNode) script.parentNode.removeChild(script);
  }
}

window.addEventListener('popstate', (e) => {
  // MEDIDO 2026-10-06: isto so redesenhava quando `e.state.tab` existia, e
  // por isso o botao VOLTAR do browser mostrava a pagina antiga com o URL
  // novo. Duas razoes, ambas medidas:
  //
  //  1. Chegado ao `/` por um carregamento normal, `history.state` e' `null`.
  //     Fiz BACK de `/guias/sistemas/` para `/` e o `location.pathname` passou
  //     a `/` enquanto o ecrã continuava a ser a Guia Sistemas.
  //
  //  2. O `pushState` do fallback generico (linha ~354) grava
  //     `{tab: '/guias/sistemas/'}` — um CAMINHO onde este codigo espera um
  //     NOME de tab. `switchTab('/guias/sistemas/')` nao encontra
  //     `__htmlRoutes[...]` e cai no ramo da API.
  //
  // A correccao e' resolver pelo URL, que e' a unica fonte que sobrevive a um
  // `popstate` sem estado. `e.state` fica so como pista.
  var caminho = window.location.pathname;
  var tab = __pathToTab[caminho] || __pathToTab[caminho + '/'] || __pathToTab[caminho.replace(/\/$/, '')];

  if (!tab && e.state && e.state.tab && !String(e.state.tab).startsWith('/')) {
    tab = e.state.tab;
  }

  if (tab && __htmlRoutes[tab]) {
    switchTab(tab, false);
    if (typeof window.updateNavActive === 'function') window.updateNavActive();
    return;
  }

  if (caminho === '/' || caminho === '/dashboard/') {
    switchTab('dashboard', false);
    if (typeof window.updateNavActive === 'function') window.updateNavActive();
    return;
  }

  // Rotas dinamicas (`/guias/vegetal/<id>/`) e o resto: delega no router, que
  // sabe tratar o caso generico. Sem isto, voltar de um registo para a guia
  // deixava o registo no ecrã.
  var conteudo = document.getElementById('content');
  if (!conteudo) return;
  fetch(caminho, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-Partial': '1' } })
    .then(function (res) {
      if (res.status === 401 || res.status === 403) {
        window.location.href = '/login/';
        return null;
      }
      if (!res.ok) throw new Error('Partial not available');
      return res.text();
    })
    .then(function (html) {
      if (html == null) return;
      renderPartialHtml(html, conteudo);
      if (typeof window.updateNavActive === 'function') window.updateNavActive();
    })
    .catch(function () {
      // Sem rede o cache do SW nao ajuda num `popstate`; melhor recarregar do
      // que deixar o URL a dizer uma coisa e o ecrã outra.
      window.location.reload();
    });
});

// Export para acesso global
window.switchTab = switchTab;
window.__htmlRoutes = __htmlRoutes;
