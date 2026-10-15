/**
 * Pack: Ovos (ovos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: ovos (2 culturas)
 * Grupo: animal
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-ovos-codorna-poedeira","title":"Codorna-Poedeira","icon":"bi-piggy-bank","desc":"Codorna-Poedeira (Ovos)","subgroup":"ovos","group":"animal","django_grupo":"ovos","django_nome":"Codorna-Poedeira","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-ovos-galinha-poedeira","title":"Galinha-Poedeira","icon":"bi-piggy-bank","desc":"Galinha-Poedeira (Ovos)","subgroup":"ovos","group":"animal","django_grupo":"ovos","django_nome":"Galinha-Poedeira","units":{"default":"cabeca","available":["cabeca"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'ovos',
    title: 'Ovos',
    icon: 'bi-hospital',
    group: 'animal',
    culture_count: 2,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'ovos' } }));
  }

})(typeof window !== 'undefined' ? window : this);