/**
 * Pack: Frutas de Bosque (frutas_bosque)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: frutas_bosque (16 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-frutas_bosque-acerola","title":"Acerola","icon":"bi-tree","desc":"Acerola (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Acerola","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-amora","title":"Amora","icon":"bi-tree","desc":"Amora (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Amora","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-amora-preta","title":"Amora-preta","icon":"bi-tree","desc":"Amora-preta (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Amora-preta","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-camu-camu","title":"Camu-camu","icon":"bi-tree","desc":"Camu-camu (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Camu-camu","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-cereja-do-rio-grande","title":"Cereja-do-rio-grande","icon":"bi-tree","desc":"Cereja-do-rio-grande (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Cereja-do-rio-grande","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-cranberry","title":"Cranberry","icon":"bi-tree","desc":"Cranberry (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Cranberry","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-framboesa","title":"Framboesa","icon":"bi-tree","desc":"Framboesa (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Framboesa","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-groselha","title":"Groselha","icon":"bi-tree","desc":"Groselha (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Groselha","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-jabuticaba","title":"Jabuticaba","icon":"bi-tree","desc":"Jabuticaba (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Jabuticaba","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-mirtilo","title":"Mirtilo","icon":"bi-tree","desc":"Mirtilo (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Mirtilo","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-mirtilo-vermelho","title":"Mirtilo-vermelho","icon":"bi-tree","desc":"Mirtilo-vermelho (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Mirtilo-vermelho","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-morango","title":"Morango","icon":"bi-tree","desc":"Morango (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Morango","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-morango-silvestre","title":"Morango-silvestre","icon":"bi-tree","desc":"Morango-silvestre (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Morango-silvestre","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-physalis","title":"Physalis","icon":"bi-tree","desc":"Physalis (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Physalis","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-pitanga","title":"Pitanga","icon":"bi-tree","desc":"Pitanga (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Pitanga","units":{"default":"kg","available":["kg"]}},{"id":"cult-frutas_bosque-uvaia","title":"Uvaia","icon":"bi-tree","desc":"Uvaia (Frutas_Bosque)","subgroup":"frutas_bosque","group":"plantio","django_grupo":"frutas_bosque","django_nome":"Uvaia","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'frutas_bosque',
    title: 'Frutas de Bosque',
    icon: 'bi-tree',
    group: 'plantio',
    culture_count: 16,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'frutas_bosque' } }));
  }

})(typeof window !== 'undefined' ? window : this);