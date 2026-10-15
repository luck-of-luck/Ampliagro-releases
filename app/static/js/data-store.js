// DataStore — armazenamento local JSON com export/import e sync
// Tudo salvo em localStorage e exportavel como arquivo .json

window.DataStore = (function () {
  var _uSuffix =
    typeof window.AMPLIAGRO_USER_ID !== 'undefined' && window.AMPLIAGRO_USER_ID != null
      ? '_u' + window.AMPLIAGRO_USER_ID
      : '';
  var KEY = 'ampliagro_data' + _uSuffix;
  // Só entram aqui tipos com um endpoint que ACEITA ESCRITA. Um tipo que não
  // temwriting endpoint não pode ficar nesta lista: o `data-sync.js` itera
  // `TYPES` para descarregar, e um tipo aqui sem escrita-sync nunca sai do
  // aparelho — sem erro, sem aviso.
  //
  // `financeiro` e `apiario` saíram por isso. `/api/financeiro/` e
  // `/api/apiario/` são `@api_view(["GET"])` — o painel. O CRUD está em
  // `/api/lancamentos/` e `/api/colmeias/`, mas a linha da folha de cálculo
  // não tem a forma desses serializers. Voltar a pôr aqui só quando o
  // `save()` em index.html souber que o registo foi gravado no servidor.
  //
  // Guard: `tests/test_sync_offline.py`.
  var TYPES = [
    'propriedades',
    'talhoes',
    'safras',
    'culturas',
    'insumos',
    'funcionarios',
    'animais',
    'maquinarios',
    'estoque',
  ];

  function getStore() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return createStore();
  }

  function createStore() {
    var store = {
      version: '1.0',
      lastSync: null,
      lastModified: new Date().toISOString(),
      data: {},
      pendingChanges: [],
      deletedIds: {},
    };
    TYPES.forEach(function (t) {
      store.data[t] = [];
    });
    TYPES.forEach(function (t) {
      store.deletedIds[t] = [];
    });
    return store;
  }

  function saveStore(store) {
    store.lastModified = new Date().toISOString();
    try {
      localStorage.setItem(KEY, JSON.stringify(store));
    } catch (e) {
      console.warn('[DataStore] Erro ao salvar localStorage', e);
    }
  }

  // --- Public API ---

  function getAll(type) {
    var store = getStore();
    return store.data[type] || [];
  }

  function getById(type, id) {
    var items = getAll(type);
    for (var i = 0; i < items.length; i++) {
      if (items[i].id == id || items[i].localId == id) return items[i];
    }
    return null;
  }

  function save(type, data) {
    var store = getStore();
    if (!store.data[type]) store.data[type] = [];

    var idx = -1;
    if (data.id) {
      for (var i = 0; i < store.data[type].length; i++) {
        if (store.data[type][i].id == data.id || store.data[type][i].localId == data.id) {
          idx = i;
          break;
        }
      }
    }

    if (!data.localId && !data.id) {
      data.localId = 'local_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
      data._pending = true;
    }

    if (idx >= 0) {
      // Merge com dados antigos
      var old = store.data[type][idx];
      store.data[type][idx] = mergeData(old, data);
      store.data[type][idx]._updatedAt = new Date().toISOString();
      store.data[type][idx]._pending = true;
    } else {
      data._createdAt = new Date().toISOString();
      data._pending = true;
      store.data[type].push(data);
    }

    store.pendingChanges.push({
      type: type,
      action: data.id ? 'update' : 'create',
      id: data.id || data.localId,
      timestamp: new Date().toISOString(),
    });

    saveStore(store);
    updateSyncBadge();
    return data.localId || data.id;
  }

  function remove(type, id) {
    var store = getStore();
    if (!store.data[type]) return;
    store.data[type] = store.data[type].filter(function (d) {
      return d.id != id && d.localId != id;
    });
    store.pendingChanges.push({
      type: type,
      action: 'delete',
      id: id,
      timestamp: new Date().toISOString(),
    });
    if (!store.deletedIds[type].includes(id)) {
      store.deletedIds[type].push(id);
    }
    saveStore(store);
    updateSyncBadge();
  }

  function mergeData(old, nu) {
    var result = {};
    Object.keys(old).forEach(function (k) {
      result[k] = old[k];
    });
    Object.keys(nu).forEach(function (k) {
      result[k] = nu[k];
    });
    return result;
  }

  // --- Export ---
  function exportJSON() {
    var store = getStore();
    var output = {
      version: store.version,
      exportedAt: new Date().toISOString(),
      data: {},
    };
    TYPES.forEach(function (t) {
      output.data[t] = (store.data[t] || []).map(function (item) {
        // Remove campos internos do sync
        var clean = {};
        Object.keys(item).forEach(function (k) {
          if (k.indexOf('_') !== 0) clean[k] = item[k];
        });
        return clean;
      });
    });
    return output;
  }

  function downloadJSON() {
    var json = exportJSON();
    var blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = 'ampliagro-dados-' + new Date().toISOString().slice(0, 10) + '.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  // --- Import ---
  function importJSON(json, merge) {
    if (!json || !json.data) {
      showToast('Arquivo JSON invalido', 'error');
      return false;
    }
    var store = getStore();
    if (merge) {
      TYPES.forEach(function (t) {
        if (json.data[t] && Array.isArray(json.data[t])) {
          json.data[t].forEach(function (item) {
            if (item.id) {
              var existing = false;
              for (var i = 0; i < store.data[t].length; i++) {
                if (store.data[t][i].id == item.id) {
                  store.data[t][i] = mergeData(store.data[t][i], item);
                  existing = true;
                  break;
                }
              }
              if (!existing) store.data[t].push(item);
            } else {
              store.data[t].push(item);
            }
          });
        }
      });
    } else {
      store.data = {};
      TYPES.forEach(function (t) {
        store.data[t] = json.data[t] && Array.isArray(json.data[t]) ? json.data[t].slice() : [];
      });
    }
    store.lastModified = new Date().toISOString();
    saveStore(store);
    updateSyncBadge();
    return true;
  }

  function uploadJSON(callback) {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = function (e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function (ev) {
        try {
          var json = JSON.parse(ev.target.result);
          var ok = importJSON(json, true);
          if (callback) callback(ok, json);
        } catch (err) {
          showToast('Erro ao ler arquivo: ' + err.message, 'error');
          if (callback) callback(false, null);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }

  // --- Sync Status ---
  function getSyncStatus() {
    var store = getStore();
    var pendentes = store.pendingChanges ? store.pendingChanges.length : 0;
    var online = navigator.onLine !== false;
    return {
      lastSync: store.lastSync,
      pendingCount: pendentes,
      online: online,
      totalRegistros: TYPES.reduce(function (sum, t) {
        return sum + (store.data[t] || []).length;
      }, 0),
    };
  }

  function updateSyncBadge() {
    var badge = document.getElementById('sync-status-badge');
    if (!badge) return;
    var status = getSyncStatus();
    if (!status.online) {
      badge.innerHTML = '<i class="bi bi-wifi-off"></i> Offline';
      badge.className = 'sync-badge offline';
    } else if (status.pendingCount > 0) {
      badge.innerHTML =
        '<i class="bi bi-cloud-upload"></i> ' +
        status.pendingCount +
        ' pendente' +
        (status.pendingCount > 1 ? 's' : '');
      badge.className = 'sync-badge pending';
    } else if (status.lastSync) {
      var diff = Math.floor((Date.now() - new Date(status.lastSync).getTime()) / 60000);
      badge.innerHTML = '<i class="bi bi-cloud-check"></i> ' + (diff < 1 ? 'agora' : diff + 'min');
      badge.className = 'sync-badge synced';
    } else {
      badge.innerHTML = '<i class="bi bi-cloud"></i> Iniciar';
      badge.className = 'sync-badge';
    }
  }

  function clearPending(tipos) {
    var store = getStore();
    store.pendingChanges = [];
    store.lastSync = new Date().toISOString();
    store.data = markSynced(store.data, tipos);
    saveStore(store);
    updateSyncBadge();
  }

  function markSynced(data, tipos) {
    // MEDIDO, 2026-10-04: antes `markSynced` limpava `_pending` de TODOS os
    // tipos, e `clearPending` era chamado incondicionalmente depois do pull —
    // mesmo quando um tipo falhou. O item que nunca chegou ao servidor ficava
    // marcado como sincronizado. Perda silenciosa, a mesma classe que o
    // `financeiro` no `data-sync.js`.
    //
    // Agora `tipos` limita a limpeza aos tipos que foram de facto puxados.
    // Sem argumento, limpa tudo (compatibilidade com chamadas antigas).
    var lista = tipos || TYPES;
    lista.forEach(function (t) {
      (data[t] || []).forEach(function (item) {
        delete item._pending;
      });
    });
    return data;
  }

  // --- Init ---
  function init() {
    var store = getStore();
    TYPES.forEach(function (t) {
      if (!store.data[t]) store.data[t] = [];
      if (!store.deletedIds[t]) store.deletedIds[t] = [];
    });
    saveStore(store);
    updateSyncBadge();
    // Atualizar periodicamente
    setInterval(updateSyncBadge, 30000);
    window.addEventListener('online', updateSyncBadge);
    window.addEventListener('offline', updateSyncBadge);
  }

  // --- Contagem por tipo ---
  function countByType(type) {
    return getAll(type).length;
  }

  return {
    init: init,
    getAll: getAll,
    getById: getById,
    save: save,
    delete: remove,
    exportJSON: exportJSON,
    downloadJSON: downloadJSON,
    importJSON: importJSON,
    uploadJSON: uploadJSON,
    getSyncStatus: getSyncStatus,
    clearPending: clearPending,
    countByType: countByType,
    TYPES: TYPES,
  };
})();

// Auto-init
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () {
    DataStore.init();
  });
} else {
  DataStore.init();
}
