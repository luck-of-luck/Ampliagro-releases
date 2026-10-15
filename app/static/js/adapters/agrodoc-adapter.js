// AgroDoc API Adapter - CEPEA/ESALQ real-time prices
// Docs: https://agrodocai.com.br/api-docs

window.AgroDocAdapter = (function () {
  var BASE_URL = 'https://agrodocai.com.br/api/v1/cotacao';

  var PRODUCT_MAP = {
    'boi-gordo': {
      produto: 'boi_gordo',
      key: 'boi_gordo_cepea_sp',
      unidade: '@',
      labelPreco: 'Preço por Arroba',
    },
    'bovino-corte': {
      produto: 'vaca_gorda',
      key: 'vaca_gorda',
      unidade: '@',
      labelPreco: 'Preço por Arroba',
    },
    'cultura-bovino': {
      produto: 'boi_gordo',
      key: 'boi_gordo_cepea_sp',
      unidade: '@',
      labelPreco: 'Preço por Arroba',
    },
    soja: { produto: 'soja', key: 'soja', unidade: 'sc 60kg', labelPreco: 'Valor da Saca' },
    'cultura-soja': {
      produto: 'soja',
      key: 'soja',
      unidade: 'sc 60kg',
      labelPreco: 'Valor da Saca',
    },
    milho: { produto: 'milho', key: 'milho', unidade: 'sc 60kg', labelPreco: 'Valor da Saca' },
    'cultura-milho': {
      produto: 'milho',
      key: 'milho',
      unidade: 'sc 60kg',
      labelPreco: 'Valor da Saca',
    },
    bezerro: {
      produto: 'bezerro',
      key: 'bezerro_ms',
      unidade: 'cabeça',
      labelPreco: 'Preço por Cabeça',
    },
    'cultura-bezerro': {
      produto: 'bezerro',
      key: 'bezerro_ms',
      unidade: 'cabeça',
      labelPreco: 'Preço por Cabeça',
    },
  };

  function normalizeCultureId(cultureId) {
    return String(cultureId || '')
      .trim()
      .toLowerCase();
  }

  function resolveMapping(cultureId) {
    var key = normalizeCultureId(cultureId);
    if (PRODUCT_MAP[key]) return PRODUCT_MAP[key];

    if (key.indexOf('cultura-') === 0) {
      var noPrefix = key.slice(8);
      if (PRODUCT_MAP[noPrefix]) return PRODUCT_MAP[noPrefix];
    }

    if (key === 'cultura-boi-gordo') return PRODUCT_MAP['boi-gordo'];
    return null;
  }

  function toNumber(v) {
    if (typeof v === 'number' && isFinite(v)) return v;
    if (typeof v !== 'string') return null;
    var s = v.trim();
    if (!s || s === '-') return null;
    s = s.replace(/R\$/g, '').replace(/\s/g, '');
    if (s.indexOf(',') >= 0 && s.indexOf('.') >= 0) {
      s = s.replace(/\./g, '').replace(',', '.');
    } else if (s.indexOf(',') >= 0) {
      s = s.replace(',', '.');
    }
    var n = parseFloat(s);
    return isFinite(n) ? n : null;
  }

  function formatMoney(value) {
    if (value === null || value === undefined || !isFinite(value)) return '—';
    return (
      'R$ ' + value.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    );
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
      var d = new Date(dateStr);
      if (isNaN(d.getTime())) return String(dateStr);
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch (e) {
      return String(dateStr);
    }
  }

  function axisLabelFromDate(dateStr) {
    if (!dateStr) return 'Atual';
    try {
      var d = new Date(dateStr);
      if (isNaN(d.getTime())) return 'Atual';
      return String(d.getFullYear());
    } catch (e) {
      return 'Atual';
    }
  }

  function parseResponse(data, mapping, uf) {
    var ufPrice = uf && data && data.boi_gordo_uf ? toNumber(data.boi_gordo_uf.preco) : null;
    var preco = ufPrice;
    if (preco === null) preco = toNumber(data && data.valor);
    if (preco === null && data) preco = toNumber(data[mapping.key]);

    var dataAtualizacao =
      (data && (data.atualizado || data.atualizado_em || data.data_cotacao || data.data)) || '';
    var dataFonte = (data && data.fonte) || 'CEPEA/ESALQ';

    var hist = [];
    if (preco !== null) {
      hist = [{ ano: axisLabelFromDate(dataAtualizacao), valor: preco }];
    }

    return {
      metrics: [
        {
          key: 'valor_saca',
          label: mapping.labelPreco,
          value: formatMoney(preco),
          unit: mapping.unidade,
        },
        {
          key: 'atualizacao',
          label: 'Atualizado em',
          value: formatDate(dataAtualizacao),
          unit: '',
        },
        { key: 'fonte', label: 'Fonte', value: dataFonte, unit: '' },
        {
          key: 'uf',
          label: 'Praça de Referência',
          value: uf ? uf.toUpperCase() : 'SP (CEPEA)',
          unit: '',
        },
      ],
      history: hist,
      history_by_metric: { valor_saca: hist },
      source: 'agrodoc',
      _source: 'agrodoc',
      _raw: data,
    };
  }

  function fetch(cultureId, uf) {
    return new Promise(function (resolve, reject) {
      var mapping = resolveMapping(cultureId);
      if (!mapping) return reject('Produto não mapeado para AgroDoc: ' + cultureId);

      var url = BASE_URL + '?produto=' + encodeURIComponent(mapping.produto);
      if (uf && uf.length === 2) url += '&uf=' + encodeURIComponent(uf.toUpperCase());

      var xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);
      xhr.timeout = 8000;
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            var data = JSON.parse(xhr.responseText);
            resolve(parseResponse(data, mapping, uf));
          } catch (e) {
            reject('Erro ao parsear resposta AgroDoc: ' + e.message);
          }
        } else {
          reject('AgroDoc HTTP ' + xhr.status);
        }
      };
      xhr.onerror = function () {
        reject('Erro de rede AgroDoc');
      };
      xhr.ontimeout = function () {
        reject('Timeout AgroDoc');
      };
      xhr.send();
    });
  }

  function getProduct(cultureId) {
    var m = resolveMapping(cultureId);
    return m ? m.produto : null;
  }

  function supports(cultureId) {
    return !!resolveMapping(cultureId);
  }

  return {
    fetch: fetch,
    supports: supports,
    getProduct: getProduct,
    PRODUCT_MAP: PRODUCT_MAP,
  };
})();
