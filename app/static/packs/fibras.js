/**
 * Pack: Fibras (fibras)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: fibras (9 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-fibras-algodao","title":"Algodão","icon":"bi-tree","desc":"Algodão (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Algodão","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-cânhamo","title":"Cânhamo","icon":"bi-tree","desc":"Cânhamo (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Cânhamo","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-juta","title":"Juta","icon":"bi-tree","desc":"Juta (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Juta","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-linho","title":"Linho","icon":"bi-tree","desc":"Linho (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Linho","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-la","title":"Lã","icon":"bi-tree","desc":"Lã (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Lã","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-piacava","title":"Piaçava","icon":"bi-tree","desc":"Piaçava (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Piaçava","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-rami","title":"Rami","icon":"bi-tree","desc":"Rami (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Rami","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-seda","title":"Seda","icon":"bi-tree","desc":"Seda (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Seda","units":{"default":"kg","available":["kg"]}},{"id":"cult-fibras-sisal","title":"Sisal","icon":"bi-tree","desc":"Sisal (Fibras)","subgroup":"fibras","group":"plantio","django_grupo":"fibras","django_nome":"Sisal","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'fibras',
    title: 'Fibras',
    icon: 'bi-cloud',
    group: 'plantio',
    culture_count: 9,
  };

  // Regista as culturas no registry global
  function registerCultures() {
    if (!global.AmpliagroRegistry) return;
    CULTURES.forEach(function (c) {
      if (!global.AmpliagroRegistry.cultures) {
        global.AmpliagroRegistry.cultures = {};
      }
      global.AmpliagroRegistry.cultures[c.id] = c;
    });
  }

  // Auto-regista quando carregado
  if (typeof window !== 'undefined' && window.AmpliagroRegistry) {
    registerCultures();
  } else if (typeof window !== 'undefined') {
    // Aguarda registry estar pronto
    var checkRegistry = setInterval(function () {
      if (window.AmpliagroRegistry) {
        clearInterval(checkRegistry);
        registerCultures();
      }
    }, 100);
  }

  // Exporta para PackLoader
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PACK_META: PACK_META, CULTURES: CULTURES };
  }

  // Sinaliza pack carregado
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'fibras' } }));
  }

})(typeof window !== 'undefined' ? window : this);