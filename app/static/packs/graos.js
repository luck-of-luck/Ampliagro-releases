/**
 * Pack: Graos (graos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: graos (12 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-graos-amaranto","title":"Amaranto","icon":"bi-tree","desc":"Amaranto (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Amaranto","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-arroz","title":"Arroz","icon":"bi-tree","desc":"Arroz (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Arroz","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-aveia","title":"Aveia","icon":"bi-tree","desc":"Aveia (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Aveia","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-cacau","title":"Cacau","icon":"bi-tree","desc":"Cacau (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Cacau","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-café","title":"Café","icon":"bi-tree","desc":"Café (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Café","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-centeio","title":"Centeio","icon":"bi-tree","desc":"Centeio (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Centeio","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-cevada","title":"Cevada","icon":"bi-tree","desc":"Cevada (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Cevada","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-milho","title":"Milho","icon":"bi-tree","desc":"Milho (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Milho","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-quinoa","title":"Quinoa","icon":"bi-tree","desc":"Quinoa (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Quinoa","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-sorgo","title":"Sorgo","icon":"bi-tree","desc":"Sorgo (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Sorgo","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-trigo","title":"Trigo","icon":"bi-tree","desc":"Trigo (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Trigo","units":{"default":"sacas","available":["sacas"]}},{"id":"cult-graos-triticale","title":"Triticale","icon":"bi-tree","desc":"Triticale (Graos)","subgroup":"graos","group":"plantio","django_grupo":"graos","django_nome":"Triticale","units":{"default":"sacas","available":["sacas"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'graos',
    title: 'Graos',
    icon: 'bi-circle-fill',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'graos' } }));
  }

})(typeof window !== 'undefined' ? window : this);