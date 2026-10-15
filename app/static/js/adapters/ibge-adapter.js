window.IBGEAdapter = (function () {
  var PROXY_URL = '/api/ibge-proxy/';

  var PRODUCT_MAP = {
    // Temporárias
    'cultura-abacaxi': true,
    'cultura-algodao': true,
    'cultura-alho': true,
    'cultura-amendoim': true,
    'cultura-arroz': true,
    'cultura-aveia': true,
    'cultura-batata': true,
    'cultura-batata-doce': true,
    'cultura-cana': true,
    'cultura-cana-de-acucar': true,
    'cultura-cebola': true,
    'cultura-centeio': true,
    'cultura-cevada': true,
    'cultura-ervilha-seca': true,
    'cultura-feijao': true,
    'cultura-fumo': true,
    'cultura-girassol': true,
    'cultura-mamona': true,
    'cultura-mandioca': true,
    'cultura-melancia': true,
    'cultura-melao': true,
    'cultura-milho': true,
    'cultura-soja': true,
    'cultura-sorgo': true,
    'cultura-tomate': true,
    'cultura-trigo': true,
    'cultura-triticale': true,
    // Permanentes
    'cultura-banana': true,
    'cultura-cacau': true,
    'cultura-cafe': true,
    'cultura-coco': true,
    'cultura-erva-mate': true,
    'cultura-juta': true,
    'cultura-laranja': true,
    'cultura-maca': true,
    'cultura-mamao': true,
    'cultura-manga': true,
    'cultura-maracuja': true,
    'cultura-pimenta-do-reino': true,
    'cultura-rami': true,
    'cultura-sisal': true,
    'cultura-uva': true,
    'cultura-abacate': true,
    'cultura-acai': true,
    'cultura-caqui': true,
    'cultura-dende': true,
    'cultura-figo': true,
    'cultura-goiaba': true,
    'cultura-limao': true,
    'cultura-pera': true,
    'cultura-pessego': true,
    'cultura-tangerina': true,
    'cultura-azeitona': true,
    'cultura-palmito': true,
    'cultura-noz': true,
    'cultura-marmelo': true,
    'cultura-linho': true,
    // PEVS (Extração Vegetal / Silvicultura)
    'cultura-buriti': true,
    'cultura-pequi': true,
    'cultura-eucalipto': true,
    'cultura-pinus': true,
    'cultura-acacia': true,
    // PPM (Pecuária Municipal - efetivo dos rebanhos)
    'cultura-bovino': true,
    'cultura-bubalino': true,
    'cultura-equino': true,
    'cultura-ovino': true,
    'cultura-caprino': true,
    'cultura-suino': true,
    'cultura-aves': true,
    'cultura-codorna': true,
    'cultura-bufalo': true,
    // PPM (Aquicultura)
    'cultura-tilapia': true,
    'cultura-tambaqui': true,
    'cultura-tambatinga': true,
    'cultura-pacu': true,
    'cultura-pirarucu': true,
    'cultura-camarao-marinho': true,
    'cultura-camarao': true,
    'cultura-ostra': true,
    'cultura-carpa': true,
    'cultura-lambari': true,
    'cultura-dourado': true,
    'cultura-tucunare': true,
    'cultura-truta': true,
    'cultura-matrinxa': true,
    // Aliases (groups)
    'cultura-citricultura': true,
    'cultura-cafeicultura': true,
    'cultura-rizicultura': true,
    'cultura-olericultura': true,
    'cultura-fruticultura': true,
    'cultura-cerealicultura': true,
  };

  function fetch(cultureId, uf) {
    return proxyCall(cultureId, uf, false);
  }

  function getHistory(cultureId, uf, years) {
    return proxyCall(cultureId, uf, false).then(function (result) {
      return result.history || [];
    });
  }

  function proxyCall(cultureId, uf, forceFallback) {
    return new Promise(function (resolve, reject) {
      var url = PROXY_URL + '?cultura=' + encodeURIComponent(cultureId);
      if (uf) url += '&uf=' + encodeURIComponent(uf);
      if (forceFallback) url += '&fallback=true';

      var xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);
      xhr.timeout = 12000;
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            var data = JSON.parse(xhr.responseText);
            if (data && data.metrics) {
              data._source = data.source || 'fallback';
              resolve(data);
            } else {
              reject('Invalid proxy response');
            }
          } catch (e) {
            reject('Parse error: ' + e.message);
          }
        } else {
          reject('Proxy HTTP ' + xhr.status);
        }
      };
      xhr.onerror = function () {
        reject('Network error');
      };
      xhr.ontimeout = function () {
        reject('Timeout');
      };
      xhr.send();
    });
  }

  return { fetch: fetch, getHistory: getHistory, PRODUCT_MAP: PRODUCT_MAP };
})();
