window.ProductionRegistry = (function () {
  var STORAGE_KEY = 'ampliagro_productions';

  function getAll() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function getByCulture(cultureId) {
    return getAll().filter(function (r) {
      return r.cultureId === cultureId;
    });
  }

  function getByCultureSorted(cultureId) {
    return getByCulture(cultureId).sort(function (a, b) {
      return (b.createdAt || '').localeCompare(a.createdAt || '');
    });
  }

  function getById(id) {
    return (
      getAll().find(function (r) {
        return r.id === id;
      }) || null
    );
  }

  function save(record) {
    var records = getAll();
    var now = new Date().toISOString();
    if (!record.name) record.name = '';
    if (record.id) {
      var idx = -1;
      for (var i = 0; i < records.length; i++) {
        if (records[i].id === record.id) {
          idx = i;
          break;
        }
      }
      if (idx >= 0) {
        record.updatedAt = now;
        record.createdAt = records[idx].createdAt || now;
        records[idx] = record;
      } else {
        record.id = 'prod-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
        record.createdAt = now;
        record.updatedAt = now;
        records.push(record);
      }
    } else {
      record.id = 'prod-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
      record.createdAt = now;
      record.updatedAt = now;
      records.push(record);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    if (typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(
        new CustomEvent('productionchanged', { detail: { action: 'save', record: record } })
      );
    }
    return record;
  }

  function remove(id) {
    var records = getAll().filter(function (r) {
      return r.id !== id;
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    if (typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(
        new CustomEvent('productionchanged', { detail: { action: 'delete', id: id } })
      );
    }
  }

  function exportJSON() {
    return JSON.stringify(getAll(), null, 2);
  }

  function importJSON(jsonStr) {
    var data = JSON.parse(jsonStr);
    if (!Array.isArray(data)) throw new Error('Formato invalido: esperado array');
    localStorage.setItem(STORAGE_KEY, jsonStr);
    if (typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(
        new CustomEvent('productionchanged', { detail: { action: 'import', count: data.length } })
      );
    }
    return data;
  }

  function getStats() {
    var records = getAll();
    var total = records.length;
    var byCulture = {};
    records.forEach(function (r) {
      byCulture[r.cultureId] = (byCulture[r.cultureId] || 0) + 1;
    });
    return { total: total, byCulture: byCulture };
  }

  return {
    getAll: getAll,
    getByCulture: getByCulture,
    getByCultureSorted: getByCultureSorted,
    getById: getById,
    save: save,
    remove: remove,
    exportJSON: exportJSON,
    importJSON: importJSON,
    getStats: getStats,
  };
})();
