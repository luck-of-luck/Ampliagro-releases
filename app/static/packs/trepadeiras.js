/**
 * Pack: Trepadeiras (trepadeiras)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: trepadeiras (6 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-trepadeiras-baunilha","title":"Baunilha","icon":"bi-tree","desc":"Baunilha (Trepadeiras)","subgroup":"trepadeiras","group":"plantio","django_grupo":"trepadeiras","django_nome":"Baunilha","units":{"default":"kg","available":["kg"]}},{"id":"cult-trepadeiras-chuchu","title":"Chuchu","icon":"bi-tree","desc":"Chuchu (Trepadeiras)","subgroup":"trepadeiras","group":"plantio","django_grupo":"trepadeiras","django_nome":"Chuchu","units":{"default":"kg","available":["kg"]}},{"id":"cult-trepadeiras-lúpulo","title":"Lúpulo","icon":"bi-tree","desc":"Lúpulo (Trepadeiras)","subgroup":"trepadeiras","group":"plantio","django_grupo":"trepadeiras","django_nome":"Lúpulo","units":{"default":"kg","available":["kg"]}},{"id":"cult-trepadeiras-maracujá","title":"Maracujá","icon":"bi-tree","desc":"Maracujá (Trepadeiras)","subgroup":"trepadeiras","group":"plantio","django_grupo":"trepadeiras","django_nome":"Maracujá","units":{"default":"kg","available":["kg"]}},{"id":"cult-trepadeiras-pimenta-do-reino","title":"Pimenta-do-reino","icon":"bi-tree","desc":"Pimenta-do-reino (Trepadeiras)","subgroup":"trepadeiras","group":"plantio","django_grupo":"trepadeiras","django_nome":"Pimenta-do-reino","units":{"default":"kg","available":["kg"]}},{"id":"cult-trepadeiras-videira","title":"Videira","icon":"bi-tree","desc":"Videira (Trepadeiras)","subgroup":"trepadeiras","group":"plantio","django_grupo":"trepadeiras","django_nome":"Videira","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'trepadeiras',
    title: 'Trepadeiras',
    icon: 'bi-tree',
    group: 'plantio',
    culture_count: 6,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'trepadeiras' } }));
  }

})(typeof window !== 'undefined' ? window : this);