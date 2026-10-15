// ── Global showToast (fallback, sobrescrito por paginas que definem o proprio) ──
(function () {
  var _toastQueue = [];
  var _toastReady = false;

  function ensureToastContainer() {
    if (document.getElementById('toast')) return true;
    var el = document.createElement('div');
    el.id = 'toast';
    el.style.cssText =
      'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:9999;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;color:#fff;opacity:0;transition:opacity 0.3s;pointer-events:none;max-width:90vw;text-align:center';
    document.body.appendChild(el);
    return true;
  }

  window.showToast = function (msg, type) {
    type = type || 'info';
    if (!ensureToastContainer()) return;
    var t = document.getElementById('toast');
    if (!t) return;
    var colors = { success: '#0f9d6e', error: '#d93a3a', warning: '#c98a24', info: '#1d2421' };
    t.style.background = colors[type] || colors.info;
    t.textContent = msg;
    t.style.opacity = '1';
    if (window._toastTimer) clearTimeout(window._toastTimer);
    window._toastTimer = setTimeout(function () {
      t.style.opacity = '0';
    }, 3000);
  };

  // ── Stubs para modals da navbar (avaliacao amigavel fora do dashboard; ──
  // ── implementacoes reais sao definidas pelo index.html no dashboard)   ──
  function isDashboard() {
    var p = window.location.pathname;
    return p === '/' || p.indexOf('index') > -1 || p === '';
  }

  var MODAL_FUNCS = [
    'openCalculatorModal',
    'closeCalculatorModal',
    'switchCalcTab',
    'calcPulverizacao',
    'calcPearson',
    'calcNPK',
    'calcBiometria',
    'selectNPKProduct',
    'selectPVProduct',
    'openQuickSpreadsheet',
    'closeQuickSpreadsheet',
    'rebuildQuickSheet',
    'saveQuickSheet',
    'openFieldNotebook',
    'closeFieldNotebook',
    'renderFieldNotebook',
    'printFieldNotebook',
    'openProductRegistry',
    'closeProductRegistry',
    'showProductTab',
    'renderProductList',
    'renderProductForm',
    'saveProductForm',
    'editProduct',
    'deleteProduct',
    'renderProductPriceTable',
    'getProductSelectOptions',
    'getProductPrice',
    'getProductsByCategoryValue',
    'openCommandPalette',
    'closeCommandPalette',
    'buildCommandCatalog',
    'filterCommandPalette',
    'exportSystemSnapshot',
    'importSystemSnapshot',
    'gerarQRCode',
    'closeQRModal',
    'printQRCode',
  ];

  MODAL_FUNCS.forEach(function (fnName) {
    window[fnName] = function () {
      if (!isDashboard()) {
        showToast('Este recurso está disponível apenas no Dashboard.', 'warning');
        return undefined;
      }
    };
  });
})();
