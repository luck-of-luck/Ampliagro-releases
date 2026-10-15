/**
 * Pack: Cítricos (citricos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: citricos (15 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-citricos-cidra","title":"Cidra","icon":"bi-tree","desc":"Cidra (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Cidra","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-kumquat","title":"Kumquat","icon":"bi-tree","desc":"Kumquat (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Kumquat","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-laranja","title":"Laranja","icon":"bi-tree","desc":"Laranja (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Laranja","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-lima","title":"Lima","icon":"bi-tree","desc":"Lima (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Lima","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-limao","title":"Limão","icon":"bi-tree","desc":"Limão (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Limão","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-limao-cravo","title":"Limão-cravo","icon":"bi-tree","desc":"Limão-cravo (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Limão-cravo","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-limao-galego","title":"Limão-galego","icon":"bi-tree","desc":"Limão-galego (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Limão-galego","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-limao-siciliano","title":"Limão-siciliano","icon":"bi-tree","desc":"Limão-siciliano (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Limão-siciliano","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-limao-taiti","title":"Limão-taiti","icon":"bi-tree","desc":"Limão-taiti (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Limão-taiti","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-mexerica","title":"Mexerica","icon":"bi-tree","desc":"Mexerica (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Mexerica","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-mexerica-cravo","title":"Mexerica-cravo","icon":"bi-tree","desc":"Mexerica-cravo (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Mexerica-cravo","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-pomelo","title":"Pomelo","icon":"bi-tree","desc":"Pomelo (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Pomelo","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-ponkan","title":"Ponkan","icon":"bi-tree","desc":"Ponkan (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Ponkan","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-tangerina","title":"Tangerina","icon":"bi-tree","desc":"Tangerina (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Tangerina","units":{"default":"kg","available":["kg"]}},{"id":"cult-citricos-toranja","title":"Toranja","icon":"bi-tree","desc":"Toranja (Citricos)","subgroup":"citricos","group":"plantio","django_grupo":"citricos","django_nome":"Toranja","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'citricos',
    title: 'Cítricos',
    icon: 'bi-tree',
    group: 'plantio',
    culture_count: 15,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'citricos' } }));
  }

})(typeof window !== 'undefined' ? window : this);