// DataSync — sincroniza DataStore local com Django API

window.DataSync = (function () {
  var SYNCING = false;
  var _uSuffix =
    typeof window.AMPLIAGRO_USER_ID !== 'undefined' && window.AMPLIAGRO_USER_ID != null
      ? '_u' + window.AMPLIAGRO_USER_ID
      : '';
  var _storeKey = 'ampliagro_data' + _uSuffix;

  // Mapeia tipos para endpoints da API
  var API = {
    propriedades: '/api/propriedades/',
    talhoes: '/api/talhoes/',
    safras: '/api/safras/',
    culturas: '/api/culturas/',
    financeiro: '/api/lancamentos/',
    insumos: '/api/insumos/',
    funcionarios: '/api/funcionarios/',
    animais: '/api/animais/',
    maquinarios: '/api/maquinarios/',
    estoque: '/api/estoque/',
    apiario: '/api/apiario/',
  };

  function csrfToken() {
    var el = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (el) return el.value;
    var cookie = document.cookie.split('; ').find(function (c) {
      return c.indexOf('csrftoken=') === 0;
    });
    return cookie ? cookie.split('=')[1] : '';
  }

  // --- Push: envia dados locais pendentes para o servidor ---
  function pushChanges() {
    if (SYNCING) return Promise.reject('Sync ja em andamento');
    SYNCING = true;
    updateSyncButton('Enviando...', true);

    var promises = [];
    var store = (function () {
      var raw = localStorage.getItem(_storeKey);
      return raw ? JSON.parse(raw) : null;
    })();

    if (!store || !store.data) {
      SYNCING = false;
      updateSyncButton('Sincronizar', false);
      return Promise.resolve({ ok: true, msg: 'Nenhum dado local' });
    }

    // Envia todos os itens com _pending = true
    DataStore.TYPES.forEach(function (type) {
      var items = store.data[type] || [];
      var endpoint = API[type];
      if (!endpoint) return;

      items.forEach(function (item) {
        if (!item._pending) return;
        var payload = {};
        Object.keys(item).forEach(function (k) {
          if (k.indexOf('_') !== 0 && k !== 'localId') payload[k] = item[k];
        });

        var method = item.id ? 'PUT' : 'POST';
        var url = item.id ? endpoint + item.id + '/' : endpoint;

        promises.push(
          fetch(url, {
            method: method,
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(payload),
          })
            .then(function (r) {
              if (!r.ok) throw new Error(type + ' HTTP ' + r.status);
              return r.json();
            })
            .then(function (serverItem) {
              // Atualiza o ID local com o ID do servidor
              if (serverItem && serverItem.id) {
                item.id = serverItem.id;
              }
              delete item._pending;
              return { type: type, id: item.id, ok: true };
            })
            .catch(function (err) {
              console.error('[DataSync] Erro ao sync ' + type + ':', err);
              return { type: type, id: item.localId, ok: false, error: err.message };
            })
        );
      });
    });

    return Promise.all(promises)
      .then(function (results) {
        var erros = results.filter(function (r) {
          return !r.ok;
        });
        var store2 = JSON.parse(localStorage.getItem(_storeKey));
        if (store2) {
          store2.pendingChanges = [];
          store2.lastSync = new Date().toISOString();
          localStorage.setItem(_storeKey, JSON.stringify(store2));
        }
        SYNCING = false;
        updateSyncButton('Sincronizar', false);
        DataStore.updateSyncBadge && DataStore.updateSyncBadge();

        if (erros.length) {
          showToast(
            erros.length +
              ' registro(s) NAO foram salvos no servidor — ficam pendentes e serao reenviados. Verifique a conexao.',
            'error'
          );
        } else if (results.length) {
          showToast(results.length + ' registro(s) sincronizado(s)!', 'success');
        } else {
          showToast('Nenhum dado pendente', 'info');
        }

        return { ok: true, total: results.length, erros: erros.length };
      })
      .catch(function (err) {
        SYNCING = false;
        updateSyncButton('Sincronizar', false);
        showToast('Erro de sync: ' + err.message, 'error');
        return { ok: false, error: err.message };
      });
  }

  // --- Pull: busca dados do servidor e mescla no store local ---
  function pullFromServer() {
    if (SYNCING) return Promise.reject('Sync ja em andamento');

    var promises = [];
    Object.keys(API).forEach(function (type) {
      promises.push(
        fetch(API[type])
          .then(function (r) {
            return r.json();
          })
          .then(function (data) {
            var items = Array.isArray(data) ? data : data.results || [];
            items.forEach(function (item) {
              DataStore.save(type, item);
            });
            return { type: type, count: items.length };
          })
          .catch(function (err) {
            console.warn('[DataSync] Erro ao baixar ' + type + ':', err);
            return { type: type, count: 0, error: err.message };
          })
      );
    });

    return Promise.all(promises).then(function (results) {
      DataStore.clearPending();
      var total = results.reduce(function (s, r) {
        return s + r.count;
      }, 0);
      showToast(total + ' registro(s) baixados do servidor', 'success');
      return { ok: true, total: total };
    });
  }

  function updateSyncButton(text, loading) {
    var btn = document.getElementById('sync-button');
    if (!btn) return;
    if (loading) {
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> ' + text;
    } else {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-cloud-arrow-up"></i> ' + text;
    }
  }

  function init() {
    // Auto-pull na carga
    if (navigator.onLine !== false) {
      setTimeout(function () {
        pullFromServer();
      }, 1000);
    }
  }

  return {
    init: init,
    pushChanges: pushChanges,
    pullFromServer: pullFromServer,
  };
})();
