// Culture Data Provider - unified interface for culture metrics
// Routes: AgroDoc (real-time prices) → IBGE SIDRA (PAM) → Fallback (offline JSON)
// Cache: in-memory + sessionStorage with TTL

window.CultureData = (function () {
  // ---------- Source Registry ----------
  // Which cultures use which primary source
  var AGRODOC_CULTURES = {
    soja: 'soja',
    'cultura-soja': 'soja',
    milho: 'milho',
    'cultura-milho': 'milho',
    'boi-gordo': 'boi_gordo',
    'cultura-bovino': 'boi_gordo',
    'bovino-corte': 'vaca_gorda',
    bezerro: 'bezerro',
    'cultura-bezerro': 'bezerro',
  };

  function normalizeCultureId(id) {
    return String(id || '')
      .trim()
      .toLowerCase();
  }

  // Culture IDs that have IBGE SIDRA mapping — suporta cult-graos-soja, cult-frutas-banana, acentos
  function normalizeNoAccent(s){ return String(s||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim(); }
  var BREED_TO_SPECIES = {
    'nelore':'bovino','angus':'bovino','brahman':'bovino','guzera':'bovino','holandes':'bovino','boi gordo':'bovino','bezerro':'bovino',
    'landrace':'suino','large-white':'suino','duroc':'suino','suino':'suino',
    'galinha':'aves','frango':'aves','peru':'aves','codorna':'aves',
    'ovelha':'ovino','cabra':'caprino','quarto-de-milha':'equino','bufalo':'bubalino','tilapia':'tilapia','tambaqui':'tambaqui','pacu':'pacu','pintado':'pintado','carpa':'carpa','truta':'truta','camarao':'camarao','ostra':'ostra'
  };
  // ── Proveniencia: o guarda de "este numero e' real" ──────────────────────────
  //
  // `hasIBGEMapping` decide se a cultura tem dado do IBGE SIDRA. E' a funcao
  // que separa "medido" de "inventado": se errar para `true`, o produto passa a
  // mostrar um numero sintetico como se fosse da fazenda. Por isso a mudanca
  // aqui e' so' de CUSTO — a resposta tem de ser bit a bit a mesma, e
  // `tests/unit/data_provider_proveniencia.test.js` compara com a versao
  // original para o provar.
  //
  // MEDIDO antes: para um id que nao casa directamente, o corpo fazia DUAS
  // varreduras do `PRODUCT_MAP` (~300 chaves) e, em CADA comparacao, voltava a
  // chamar `normalizeNoAccent()` — `toLowerCase()` + `normalize('NFD')` + um
  // `replace` com regex. Medido no teste: 1 chamada = 92 normalizacoes, e
  // repetir o MESMO id 50 vezes = 4692. Como o `index.html` interroga isto por
  // cultura (o catalogo tem 488) e mais do que uma vez por cultura, o
  // `resolveSource` de cada uma pagava o mapa inteiro varias vezes.
  //
  // As duas correccoes:
  //   1. `_chavesNormalizadas` normaliza as chaves UMA vez por `PRODUCT_MAP`,
  //      em vez de duas vezes por chave e por chamada;
  //   2. o resultado e' memorizado por id.
  //
  // Ambas se invalidam quando muda a REFERENCIA do `PRODUCT_MAP`, nao quando
  // muda o seu conteudo: o `PRODUCT_MAP` do `ibge-adapter.js` e' um literal de
  // modulo e nunca e' reatribuido, mas nada impede que um dia um adapter
  // diferente o substitua — e nesse dia um memo velho responderia pelo mapa
  // antigo. Trocar a referencia e' a unica forma de invalidar com seguranca.
  var _normRef = null;
  var _normKeys = null;
  var _memoRef = null;
  var _memo = Object.create(null);

  function _chavesNormalizadas(mapa) {
    if (_normRef !== mapa) {
      _normRef = mapa;
      _normKeys = Object.keys(mapa).map(function (k) {
        return normalizeNoAccent(k);
      });
    }
    return _normKeys;
  }

  function hasIBGEMapping(id) {
    if (!window.IBGEAdapter || !window.IBGEAdapter.PRODUCT_MAP) return false;
    var mapa = window.IBGEAdapter.PRODUCT_MAP;

    // `typeof` na chave porque a colisao importa mesmo aqui: sem ele,
    // `undefined` e a string `'undefined'` caem no mesmo memo e passariam a
    // devolver a resposta uma da outra. Os valores sao booleanos, nunca
    // `undefined`, por isso o teste de cache abaixo e' fiado.
    var chave = typeof id + ':' + id;
    if (_memoRef === mapa && _memo[chave] !== undefined) return _memo[chave];

    var r = _hasIBGEMapping(id, mapa);

    if (_memoRef !== mapa) {
      _memoRef = mapa;
      _memo = Object.create(null);
    }
    _memo[chave] = r;
    return r;
  }

  function _hasIBGEMapping(id, mapa) {
    if (mapa[id]) return true;
    var norm = normalizeNoAccent(id);
    var short = norm.split('-').pop();
    if (BREED_TO_SPECIES[short] && mapa['cultura-' + BREED_TO_SPECIES[short]]) return true;
    if (mapa['cultura-' + short]) return true;
    var stripped = norm.replace('cult-','').replace('graos-','').replace('frutas-','').replace('hortalicas-','').replace('leguminosas-','').replace('bovinos-','').replace('suinos-','').replace('aves-','').replace('peixes-','').replace('crustaceos-','');
    if (mapa['cultura-' + stripped]) return true;
    if (mapa[stripped]) return true;
    var normKeys = _chavesNormalizadas(mapa);
    for (var i=0;i<normKeys.length;i++) if (normKeys[i].indexOf(short) >=0) return true;
    if (BREED_TO_SPECIES[short]) {
      var esp = BREED_TO_SPECIES[short];
      for (var j=0;j<normKeys.length;j++) if (normKeys[j].indexOf(esp) >=0) return true;
    }
    return false;
  }

  function getAgroDocProduct(cultureId) {
    var id = normalizeNoAccent(cultureId);
    if (AGRODOC_CULTURES[id]) return AGRODOC_CULTURES[id];
    if (id.indexOf('cultura-') === 0) {
      var noPrefix = id.slice(8);
      if (AGRODOC_CULTURES[noPrefix]) return AGRODOC_CULTURES[noPrefix];
    }
    var short = id.split('-').pop();
    if (AGRODOC_CULTURES[short]) return AGRODOC_CULTURES[short];
    if (AGRODOC_CULTURES['cultura-' + short]) return AGRODOC_CULTURES['cultura-' + short];

    if (window.AgroDocAdapter && typeof window.AgroDocAdapter.getProduct === 'function') {
      var viaAdapter = window.AgroDocAdapter.getProduct(cultureId);
      if (viaAdapter) return viaAdapter;
      if (short) {
        var viaShort = window.AgroDocAdapter.getProduct(short);
        if (viaShort) return viaShort;
        viaShort = window.AgroDocAdapter.getProduct('cultura-' + short);
        if (viaShort) return viaShort;
      }
    }
    return null;
  }

  function hasAgroDocSupport(cultureId) {
    return !!getAgroDocProduct(cultureId);
  }

  function resolveSource(cultureId) {
    if (hasAgroDocSupport(cultureId) && window.AgroDocAdapter) return 'agrodoc';
    if (hasIBGEMapping(cultureId)) return 'ibge';
    return 'no_data';
  }

  // ---------- Cache Layer ----------
  var memoryCache = {};
  var CACHE_TTL = {
    agrodoc: 5 * 60 * 1000, // 5 min for real-time prices
    ibge: 60 * 60 * 1000, // 1h for annual IBGE data
    fallback: 24 * 60 * 60 * 1000, // 24h for static fallback
    no_data: 2 * 60 * 1000,
  };

  function cacheGet(key) {
    var cached = memoryCache[key];
    if (cached && Date.now() < cached.expires) return cached.data;
    // Try sessionStorage
    try {
      var stored = sessionStorage.getItem('cdp_' + key);
      if (stored) {
        var parsed = JSON.parse(stored);
        if (Date.now() < parsed.expires) {
          memoryCache[key] = parsed; // restore to memory
          return parsed.data;
        }
        sessionStorage.removeItem('cdp_' + key);
      }
    } catch (e) {}
    return null;
  }

  function cacheSet(key, data, source) {
    var ttl = CACHE_TTL[source] || CACHE_TTL.fallback;
    var entry = { data: data, expires: Date.now() + ttl };
    memoryCache[key] = entry;
    try {
      sessionStorage.setItem('cdp_' + key, JSON.stringify(entry));
    } catch (e) {}
  }

  // ---------- Fallback Data ----------
  function getFallbackMetrics(cultureId) {
    return null;
  }

  // ---------- Public API ----------
  var _ufSuffix =
    typeof window.AMPLIAGRO_USER_ID !== 'undefined' && window.AMPLIAGRO_USER_ID != null
      ? '_u' + window.AMPLIAGRO_USER_ID
      : '';
  var _ufKey = 'ampliagro-culture-uf' + _ufSuffix;
  var selectedUf = localStorage.getItem(_ufKey) || '';

  function init() {
  /* Ja nao carrega o ficheiro de metricas de exemplo: ele servia 468
   * numeros inventados e, no caminho de erro, apresentava-os como os do
   * produtor.
   *
   * O `Promise.resolve()` mantem a assinatura para quem chama: mudar uma
   * inicializacao assincrona para sincronia parte chamadores que fazem
   * `.then()`. */
    return Promise.resolve();
  }

  /**
   * NAO CONSEGUI LER. Deliberadamente diferente de "sem dados".
   *
   * "Sem dados" diz ao produtor que vao ao cadastro, e e' accionavel.
   * "Nao consegui ler" diz que o problema e' da ligacao, e mostrar "sem dados"
   * seria MENTIR-LHE que o trabalho dele desapareceu. Um homem quepassou a percorrer a a e' informado de que ela nao existe, quando o que
   * se perdeu foi um pedido de rede.
   *
   * E o mais importante: NAO devolve numeros. O `catch` que chamava esta
   * funcao devolvia antes 468 metricas fixas de `culture-metrics-fallback` —
   * "Receita Estimada: R$ 18,5 milhoes" era o que aparecia quando a API
   * falhava. Esse era o numero em que alguem toma um credito, e vinha de um
   * `catch`.
   *
   * `metrics: []` e' deliberado. Um payload com metricas cheias e um campo
   * `_indisponivel: true` seria pior do que um vazio: qualquer interface que
   * nao leia esse campo mostraria os numeros.
   */
  function buildUnavailableResult(cultureId, uf, message) {
    return {
      metrics: [],
      history: [],
      history_by_metric: {},
      _source: 'indisponivel',
      source: 'indisponivel',
      _indisponivel: true,
      _cached: false,
      cultura: cultureId,
      uf: uf || 'BR',
      _error: message || 'Nao foi possivel ler os dados.',
    };
  }

  function buildNoDataResult(cultureId, uf, message) {
    return {
      metrics: [],
      history: [],
      history_by_metric: {},
      _source: 'no_data',
      source: 'no_data',
      cultura: cultureId,
      uf: uf || 'BR',
      _error: message || 'Sem dados reais',
    };
  }

  function fetchBySource(cultureId, source, uf) {
    if (source === 'agrodoc') {
      if (!hasAgroDocSupport(cultureId) || !window.AgroDocAdapter) {
        return Promise.reject(new Error('AgroDoc não suporta esta cultura'));
      }
      return window.AgroDocAdapter.fetch(cultureId, uf);
    }

    if (source === 'ibge') {
      if (!hasIBGEMapping(cultureId) || !window.IBGEAdapter) {
        return Promise.reject(new Error('IBGE não suporta esta cultura'));
      }
      return window.IBGEAdapter.fetch(cultureId, uf);
    }

    if (source === 'fallback') {
      // `fallback` deixou de significar "números de exemplo" e passou a
      // significar "aceito que não há dados". O nome fica para não partir
      // quem chama; o comportamento muda, e diz porque.
      //
      // Antes isto servia as 468 métricas fixas de `culture-metrics-fallback`
      // como se fossem da fazenda de quem está a ver.
      return Promise.resolve(
        buildUnavailableResult(
          cultureId,
          uf,
          'Esta fonte não tem dados. Números de exemplo não são apresentados ' +
            'como se fossem seus.'
        )
      );
    }

    if (source === 'no_data') {
      return Promise.resolve(buildNoDataResult(cultureId, uf));
    }

    return Promise.reject(new Error('Fonte inválida: ' + source));
  }

  function getMetricsBySource(cultureId, source, ufOverride, options) {
    options = options || {};
    var realOnly = !!options.realOnly;
    var uf = typeof ufOverride === 'string' ? ufOverride : selectedUf;
    var requested = source || 'auto';
    var resolved = requested === 'auto' ? resolveSource(cultureId) : requested;
    if (!resolved) resolved = 'no_data';

    var cacheKey = ['metrics', resolved, cultureId, uf || 'BR', realOnly ? 'real' : 'all'].join(
      '|'
    );
    var cached = cacheGet(cacheKey);
    if (cached) return Promise.resolve(cached);

    return fetchBySource(cultureId, resolved, uf)
      .then(function (result) {
        var out = result || {};
        out.metrics = Array.isArray(out.metrics) ? out.metrics : [];
        out.history = Array.isArray(out.history) ? out.history : [];
        out.history_by_metric =
          out.history_by_metric && typeof out.history_by_metric === 'object'
            ? out.history_by_metric
            : {};
        out._source = out._source || out.source || resolved;
        out.source = out.source || out._source;
        out._cached = false;

        if (realOnly && (out._source === 'fallback' || out._source === 'no_data')) {
          throw new Error('Sem dados reais para esta fonte');
        }

        cacheSet(cacheKey, out, resolved);
        return out;
      })
      .catch(function (err) {
        var msg = err && err.message ? err.message : String(err || 'Erro desconhecido');

        if (realOnly) {
          return buildNoDataResult(cultureId, uf, msg);
        }

        // NENHUM número de exemplo. O que se passou é que não conseguimos
        // ler, e a resposta honesta a isso é dizer que não conseguimos ler.
        //
        // Este `catch` era o caminho perigoso: era aqui que uma falha de
        // rede, um timeout ou um 500 se transformavam num painel de números
        // inventados com a mesma aparência dos verdadeiros. "Receita
        // Estimada: R$ 18,5 milhões" é o número em que alguém toma um
        // crédito, e ele vinha de um `catch`.
        return buildUnavailableResult(
          cultureId,
          ufOverride,
          'API indisponível: ' + msg
        );
      });
  }

  function getMetrics(cultureId, ufOverride) {
    return getMetricsBySource(cultureId, 'auto', ufOverride, { realOnly: false });
  }

  function getHistory(cultureId, years) {
    years = years || 5;
    var cacheKey = 'hist_' + cultureId + '|' + years;

    var cached = cacheGet(cacheKey);
    if (cached) return Promise.resolve(cached);

    return fetch('/api/commodities/')
      .then(function (r) {
        return r.json();
      })
      .then(function (json) {
        var culturas = json.culturas || [];
        var filtradas = culturas.filter(function (c) {
          if (!c.cultura || !cultureId) return false;
          var norm = function (s) {
            return s
              .toLowerCase()
              .normalize('NFD')
              .replace(/[\u0300-\u036f]/g, '')
              .replace(/^cultura-/, '');
          };
          var culturaNorm = norm(c.cultura);
          var idNorm = norm(cultureId);
          return culturaNorm.indexOf(idNorm) >= 0 || idNorm.indexOf(culturaNorm) >= 0;
        });
        var data = filtradas.slice(0, years + 1).map(function (c) {
          return { ano: String(c.ano || ''), valor: c.producao || 0 };
        });
        if (data.length) {
          cacheSet(cacheKey, data, 'api');
          return data;
        }
        // Try IBGE adapter as fallback
        if (
          window.IBGEAdapter &&
          window.IBGEAdapter.PRODUCT_MAP &&
          window.IBGEAdapter.PRODUCT_MAP[cultureId]
        ) {
          return window.IBGEAdapter.getHistory(cultureId, '', years)
            .then(function (ibgeData) {
              if (ibgeData && ibgeData.length) {
                cacheSet(cacheKey, ibgeData, 'ibge');
                return ibgeData;
              }
              cacheSet(cacheKey, [], 'empty');
              return [];
            })
            .catch(function () {
              cacheSet(cacheKey, [], 'error');
              return [];
            });
        }
        cacheSet(cacheKey, [], 'empty');
        return [];
      })
      .catch(function () {
        // Try IBGE adapter on network error too
        if (
          window.IBGEAdapter &&
          window.IBGEAdapter.PRODUCT_MAP &&
          window.IBGEAdapter.PRODUCT_MAP[cultureId]
        ) {
          return window.IBGEAdapter.getHistory(cultureId, '', years)
            .then(function (ibgeData) {
              if (ibgeData && ibgeData.length) {
                cacheSet(cacheKey, ibgeData, 'ibge');
                return ibgeData;
              }
              cacheSet(cacheKey, [], 'empty');
              return [];
            })
            .catch(function () {
              cacheSet(cacheKey, [], 'error');
              return [];
            });
        }
        cacheSet(cacheKey, [], 'error');
        return [];
      });
  }

  function getSourceLabel(cultureId) {
    var s = resolveSource(cultureId);
    switch (s) {
      case 'agrodoc':
        return 'CEPEA/ESALQ (tempo real)';
      case 'ibge':
        return 'IBGE PAM (anual)';
      case 'no_data':
        return 'Sem dados reais';
      case 'fallback':
        return 'Dados offline';
      default:
        return '—';
    }
  }

  function setUf(uf) {
    selectedUf = uf;
    try {
      localStorage.setItem(_ufKey, uf);
    } catch (e) {}
  }

  function getUf() {
    return selectedUf;
  }

  // Avaliable UFs for dropdown
  var UF_LIST = [
    { sigla: '', nome: 'Brasil (todos)' },
    { sigla: 'AC', nome: 'Acre' },
    { sigla: 'AL', nome: 'Alagoas' },
    { sigla: 'AP', nome: 'Amapá' },
    { sigla: 'AM', nome: 'Amazonas' },
    { sigla: 'BA', nome: 'Bahia' },
    { sigla: 'CE', nome: 'Ceará' },
    { sigla: 'DF', nome: 'Distrito Federal' },
    { sigla: 'ES', nome: 'Espírito Santo' },
    { sigla: 'GO', nome: 'Goiás' },
    { sigla: 'MA', nome: 'Maranhão' },
    { sigla: 'MT', nome: 'Mato Grosso' },
    { sigla: 'MS', nome: 'Mato Grosso do Sul' },
    { sigla: 'MG', nome: 'Minas Gerais' },
    { sigla: 'PA', nome: 'Pará' },
    { sigla: 'PB', nome: 'Paraíba' },
    { sigla: 'PR', nome: 'Paraná' },
    { sigla: 'PE', nome: 'Pernambuco' },
    { sigla: 'PI', nome: 'Piauí' },
    { sigla: 'RJ', nome: 'Rio de Janeiro' },
    { sigla: 'RN', nome: 'Rio Grande do Norte' },
    { sigla: 'RS', nome: 'Rio Grande do Sul' },
    { sigla: 'RO', nome: 'Rondônia' },
    { sigla: 'RR', nome: 'Roraima' },
    { sigla: 'SC', nome: 'Santa Catarina' },
    { sigla: 'SP', nome: 'São Paulo' },
    { sigla: 'SE', nome: 'Sergipe' },
    { sigla: 'TO', nome: 'Tocantins' },
  ];

  return {
    init: init,
    getMetrics: getMetrics,
    getMetricsBySource: getMetricsBySource,
    getHistory: getHistory,
    getSource: resolveSource,
    getSourceLabel: getSourceLabel,
    setUf: setUf,
    getUf: getUf,
    UF_LIST: UF_LIST,
    hasIBGEMapping: hasIBGEMapping,
    hasAgroDocSupport: hasAgroDocSupport,
    getAgroDocProduct: getAgroDocProduct,
  };
})();
