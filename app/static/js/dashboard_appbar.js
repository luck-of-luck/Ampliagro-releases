/* AMPLIAGRO — Ações da barra de widgets (widgetbar).
   Carregado em TODAS as páginas via base.html; por isso só usa
   APIs globais com guardas (a widgetbar fica oculta fora do dashboard). */
(function () {
  'use strict';
  window.DashboardAppbar = window.DashboardAppbar || {};
  DashboardAppbar.init = function () {};

  /* Menu Iniciar da widgetbar + Enter da busca (estava indefinido) */
  window.searchAction = function (alvo) {
    try {
      if (typeof window.closeSearchMenuNow === 'function') window.closeSearchMenuNow();
    } catch (e) {}
    var tabs = {
      dashboard: 'dashboard',
      financeiro: 'financeiro',
      campo: 'campo',
      estoque: 'estoque',
    };
    if (alvo && tabs[alvo] && typeof window.switchTab === 'function') {
      window.switchTab(tabs[alvo]);
      return;
    }
    if (alvo && typeof window.searchInCanvas === 'function') {
      window.searchInCanvas(alvo);
      return;
    }
    if (typeof window.switchTab === 'function') window.switchTab('dashboard');
  };
})();
