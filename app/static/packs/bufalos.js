/**
 * Pack: Búfalos (bufalos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: bufalos (4 culturas)
 * Grupo: animal
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-bufalos-búfalo-carabao","title":"Búfalo-Carabao","icon":"bi-piggy-bank","desc":"Búfalo-Carabao (Bufalos)","subgroup":"bufalos","group":"animal","django_grupo":"bufalos","django_nome":"Búfalo-Carabao","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-bufalos-búfalo-jafarabadi","title":"Búfalo-Jafarabadi","icon":"bi-piggy-bank","desc":"Búfalo-Jafarabadi (Bufalos)","subgroup":"bufalos","group":"animal","django_grupo":"bufalos","django_nome":"Búfalo-Jafarabadi","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-bufalos-búfalo-mediterrâneo","title":"Búfalo-Mediterrâneo","icon":"bi-piggy-bank","desc":"Búfalo-Mediterrâneo (Bufalos)","subgroup":"bufalos","group":"animal","django_grupo":"bufalos","django_nome":"Búfalo-Mediterrâneo","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-bufalos-búfalo-murrah","title":"Búfalo-Murrah","icon":"bi-piggy-bank","desc":"Búfalo-Murrah (Bufalos)","subgroup":"bufalos","group":"animal","django_grupo":"bufalos","django_nome":"Búfalo-Murrah","units":{"default":"cabeca","available":["cabeca"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'bufalos',
    title: 'Búfalos',
    icon: 'bi-hospital',
    group: 'animal',
    culture_count: 4,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'bufalos' } }));
  }

})(typeof window !== 'undefined' ? window : this);