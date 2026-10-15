window.StageRegistry = (function () {
  var STORAGE_KEY = 'ampliagro_estagios';
  var SYNC_KEY = 'ampliagro_estagios_sync_queue';

  function getAll() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function getByRegistro(registroId) {
    return getAll().filter(function (e) {
      return e.registro === registroId;
    });
  }

  function save(estagio) {
    var all = getAll();
    var now = new Date().toISOString();
    estagio._synced = false;
    estagio._localTs = now;
    if (estagio.id && typeof estagio.id === 'number') {
      estagio._synced = true;
    }
    if (estagio.id) {
      var idx = all.findIndex(function (e) {
        return e.id === estagio.id;
      });
      if (idx >= 0) {
        estagio._createdAt = all[idx]._createdAt || now;
        estagio._updatedAt = now;
        all[idx] = estagio;
      } else {
        estagio._createdAt = now;
        estagio._updatedAt = now;
        all.push(estagio);
      }
    } else {
      estagio.id = 'local-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
      estagio._createdAt = now;
      estagio._updatedAt = now;
      all.push(estagio);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
    addToSyncQueue(estagio);
    return estagio;
  }

  function remove(id) {
    var all = getAll().filter(function (e) {
      return e.id !== id;
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
    addToSyncQueue({ id: id, _deleted: true });
  }

  function saveTarefa(tarefa) {
    var all = getAll();
    var now = new Date().toISOString();
    tarefa._synced = false;
    tarefa._localTs = now;
    if (tarefa.id && typeof tarefa.id === 'number') {
      tarefa._synced = true;
    }
    var est = all.find(function (e) {
      return e.id === tarefa.estagio;
    });
    if (est) {
      est.tarefas = est.tarefas || [];
      if (tarefa.id) {
        var idx = est.tarefas.findIndex(function (t) {
          return t.id === tarefa.id;
        });
        if (idx >= 0) {
          tarefa._updatedAt = now;
          est.tarefas[idx] = tarefa;
        } else {
          tarefa._createdAt = now;
          tarefa._updatedAt = now;
          est.tarefas.push(tarefa);
        }
      } else {
        tarefa.id = 'local-t-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
        tarefa._createdAt = now;
        tarefa._updatedAt = now;
        est.tarefas.push(tarefa);
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
      addToSyncQueue(tarefa);
    }
    return tarefa;
  }

  function toggleTarefa(tarefaId) {
    var all = getAll();
    for (var i = 0; i < all.length; i++) {
      if (all[i].tarefas) {
        var t = all[i].tarefas.find(function (t2) {
          return t2.id === tarefaId;
        });
        if (t) {
          t.concluida = !t.concluida;
          t.concluida_em = t.concluida ? new Date().toISOString() : null;
          t._localTs = new Date().toISOString();
          t._synced = false;
          localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
          addToSyncQueue(t);
          return t;
        }
      }
    }
    return null;
  }

  function addToSyncQueue(item) {
    try {
      var queue = JSON.parse(localStorage.getItem(SYNC_KEY)) || [];
      item._queueTs = new Date().toISOString();
      queue.push(item);
      localStorage.setItem(SYNC_KEY, JSON.stringify(queue));
    } catch (e) {}
  }

  function getSyncQueue() {
    try {
      return JSON.parse(localStorage.getItem(SYNC_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function clearSyncQueue() {
    localStorage.setItem(SYNC_KEY, '[]');
  }

  function exportJSON() {
    return JSON.stringify(getAll(), null, 2);
  }

  function importJSON(jsonStr) {
    var data = JSON.parse(jsonStr);
    if (!Array.isArray(data)) throw new Error('Formato invalido');
    localStorage.setItem(STORAGE_KEY, jsonStr);
    return data;
  }

  return {
    getAll: getAll,
    getByRegistro: getByRegistro,
    save: save,
    remove: remove,
    saveTarefa: saveTarefa,
    toggleTarefa: toggleTarefa,
    getSyncQueue: getSyncQueue,
    clearSyncQueue: clearSyncQueue,
    exportJSON: exportJSON,
    importJSON: importJSON,
  };
})();
