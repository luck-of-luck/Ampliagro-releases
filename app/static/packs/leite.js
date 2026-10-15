/**
 * Pack: Leite (leite)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: leite (3 culturas)
 * Grupo: animal
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-leite-búfala-leiteira","title":"Búfala-Leiteira","icon":"bi-piggy-bank","desc":"Búfala-Leiteira (Leite)","subgroup":"leite","group":"animal","django_grupo":"leite","django_nome":"Búfala-Leiteira","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-leite-cabra-leiteira","title":"Cabra-Leiteira","icon":"bi-piggy-bank","desc":"Cabra-Leiteira (Leite)","subgroup":"leite","group":"animal","django_grupo":"leite","django_nome":"Cabra-Leiteira","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-leite-vaca-leiteira","title":"Vaca-Leiteira","icon":"bi-piggy-bank","desc":"Vaca-Leiteira (Leite)","subgroup":"leite","group":"animal","django_grupo":"leite","django_nome":"Vaca-Leiteira","units":{"default":"cabeca","available":["cabeca"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'leite',
    title: 'Leite',
    icon: 'bi-hospital',
    group: 'animal',
    culture_count: 3,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'leite' } }));
  }

})(typeof window !== 'undefined' ? window : this);