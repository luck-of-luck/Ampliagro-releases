/**
 * Pack: Especiarias (especiarias)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: especiarias (12 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-especiarias-alcaparra","title":"Alcaparra","icon":"bi-tree","desc":"Alcaparra (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Alcaparra","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-acafrao","title":"Açafrão","icon":"bi-tree","desc":"Açafrão (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Açafrão","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-baunilha","title":"Baunilha","icon":"bi-tree","desc":"Baunilha (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Baunilha","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-cardamomo","title":"Cardamomo","icon":"bi-tree","desc":"Cardamomo (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Cardamomo","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-cúrcuma","title":"Cúrcuma","icon":"bi-tree","desc":"Cúrcuma (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Cúrcuma","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-gengibre","title":"Gengibre","icon":"bi-tree","desc":"Gengibre (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Gengibre","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-malagueta","title":"Malagueta","icon":"bi-tree","desc":"Malagueta (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Malagueta","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-noz-moscada","title":"Noz-moscada","icon":"bi-tree","desc":"Noz-moscada (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Noz-moscada","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-pimenta-biquinho","title":"Pimenta-biquinho","icon":"bi-tree","desc":"Pimenta-biquinho (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Pimenta-biquinho","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-pimenta-cumari","title":"Pimenta-cumari","icon":"bi-tree","desc":"Pimenta-cumari (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Pimenta-cumari","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-pimenta-dedo-de-moca","title":"Pimenta-dedo-de-moça","icon":"bi-tree","desc":"Pimenta-dedo-de-moça (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Pimenta-dedo-de-moça","units":{"default":"kg","available":["kg"]}},{"id":"cult-especiarias-pimenta-do-reino","title":"Pimenta-do-reino","icon":"bi-tree","desc":"Pimenta-do-reino (Especiarias)","subgroup":"especiarias","group":"plantio","django_grupo":"especiarias","django_nome":"Pimenta-do-reino","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'especiarias',
    title: 'Especiarias',
    icon: 'bi-stars',
    group: 'plantio',
    culture_count: 12,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'especiarias' } }));
  }

})(typeof window !== 'undefined' ? window : this);