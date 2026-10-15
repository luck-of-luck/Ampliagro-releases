window.ProductRegistry = (function () {
  var STORAGE_KEY = 'ampliagro_produtos';

  var CATEGORIES = [
    { id: 'fertilizante', label: 'Fertilizante', npk: true },
    { id: 'defensivo', label: 'Defensivo', npk: false },
    { id: 'semente', label: 'Semente', npk: false },
    { id: 'racao', label: 'Racao', npk: false },
    { id: 'combustivel', label: 'Combustivel', npk: false },
    { id: 'embalagem', label: 'Embalagem', npk: false },
    { id: 'implemento', label: 'Implemento', npk: false },
    { id: 'insumo_geral', label: 'Insumo Geral', npk: false },
  ];

  var UNIDADES = ['kg', 'L', 'sc', 'un', 't', 'g', 'mL', 'saco'];

  function getAll() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function getByCategory(catId) {
    return getAll().filter(function (p) {
      return p.categoria === catId;
    });
  }

  function getByNPK() {
    return getAll().filter(function (p) {
      var cat = CATEGORIES.find(function (c) {
        return c.id === p.categoria;
      });
      return cat && cat.npk;
    });
  }

  function getById(id) {
    return (
      getAll().find(function (p) {
        return p.id === id;
      }) || null
    );
  }

  function save(product) {
    var products = getAll();
    var now = new Date().toISOString();
    if (product.id) {
      var idx = -1;
      for (var i = 0; i < products.length; i++) {
        if (products[i].id === product.id) {
          idx = i;
          break;
        }
      }
      if (idx >= 0) {
        product.updatedAt = now;
        product.createdAt = products[idx].createdAt || now;
        products[idx] = product;
      } else {
        product.id = 'prod-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
        product.createdAt = now;
        products.push(product);
      }
    } else {
      product.id = 'prod-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
      product.createdAt = now;
      products.push(product);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(products));
    if (typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(
        new CustomEvent('productchanged', { detail: { action: 'save', product: product } })
      );
    }
    return product;
  }

  function remove(id) {
    var products = getAll().filter(function (p) {
      return p.id !== id;
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(products));
    if (typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(
        new CustomEvent('productchanged', { detail: { action: 'delete', id: id } })
      );
    }
  }

  function getCategories() {
    return CATEGORIES;
  }
  function getUnidades() {
    return UNIDADES;
  }

  function getStats() {
    var products = getAll();
    var byCat = {};
    products.forEach(function (p) {
      byCat[p.categoria] = (byCat[p.categoria] || 0) + 1;
    });
    return { total: products.length, byCategory: byCat };
  }

  return {
    getAll: getAll,
    getByCategory: getByCategory,
    getByNPK: getByNPK,
    getById: getById,
    save: save,
    remove: remove,
    getCategories: getCategories,
    getUnidades: getUnidades,
    getStats: getStats,
  };
})();
