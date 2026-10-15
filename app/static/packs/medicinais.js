/**
 * Pack: Medicinais & Aromaticas (medicinais)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: medicinais (6 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-medicinais-arnica","title":"Arnica","icon":"bi-tree","desc":"Arnica (Medicinais)","subgroup":"medicinais","group":"plantio","django_grupo":"medicinais","django_nome":"Arnica","units":{"default":"kg","available":["kg"]}},{"id":"cult-medicinais-babosa","title":"Babosa","icon":"bi-tree","desc":"Babosa (Medicinais)","subgroup":"medicinais","group":"plantio","django_grupo":"medicinais","django_nome":"Babosa","units":{"default":"kg","available":["kg"]}},{"id":"cult-medicinais-bardana","title":"Bardana","icon":"bi-tree","desc":"Bardana (Medicinais)","subgroup":"medicinais","group":"plantio","django_grupo":"medicinais","django_nome":"Bardana","units":{"default":"kg","available":["kg"]}},{"id":"cult-medicinais-escorcionera","title":"Escorcionera","icon":"bi-tree","desc":"Escorcionera (Medicinais)","subgroup":"medicinais","group":"plantio","django_grupo":"medicinais","django_nome":"Escorcionera","units":{"default":"kg","available":["kg"]}},{"id":"cult-medicinais-ginseng","title":"Ginseng","icon":"bi-tree","desc":"Ginseng (Medicinais)","subgroup":"medicinais","group":"plantio","django_grupo":"medicinais","django_nome":"Ginseng","units":{"default":"kg","available":["kg"]}},{"id":"cult-medicinais-quina","title":"Quina","icon":"bi-tree","desc":"Quina (Medicinais)","subgroup":"medicinais","group":"plantio","django_grupo":"medicinais","django_nome":"Quina","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'medicinais',
    title: 'Medicinais & Aromaticas',
    icon: 'bi-flower3',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'medicinais' } }));
  }

})(typeof window !== 'undefined' ? window : this);