/**
 * Pack: PANC (panc)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: panc (15 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-panc-araruta","title":"Araruta","icon":"bi-tree","desc":"Araruta (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Araruta","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-azedinha","title":"Azedinha","icon":"bi-tree","desc":"Azedinha (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Azedinha","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-beldroega","title":"Beldroega","icon":"bi-tree","desc":"Beldroega (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Beldroega","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-bertalha","title":"Bertalha","icon":"bi-tree","desc":"Bertalha (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Bertalha","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-capuchinha","title":"Capuchinha","icon":"bi-tree","desc":"Capuchinha (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Capuchinha","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-caruru","title":"Caruru","icon":"bi-tree","desc":"Caruru (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Caruru","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-clitoria","title":"Clitoria","icon":"bi-tree","desc":"Clitoria (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Clitoria","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-dente-de-leao","title":"Dente-de-leão","icon":"bi-tree","desc":"Dente-de-leão (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Dente-de-leão","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-hibisco","title":"Hibisco","icon":"bi-tree","desc":"Hibisco (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Hibisco","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-jambu","title":"Jambu","icon":"bi-tree","desc":"Jambu (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Jambu","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-ora-pro-nóbis","title":"Ora-pro-nóbis","icon":"bi-tree","desc":"Ora-pro-nóbis (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Ora-pro-nóbis","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-peixinho-da-horta","title":"Peixinho-da-horta","icon":"bi-tree","desc":"Peixinho-da-horta (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Peixinho-da-horta","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-picao-preto","title":"Picão-preto","icon":"bi-tree","desc":"Picão-preto (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Picão-preto","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-serralha","title":"Serralha","icon":"bi-tree","desc":"Serralha (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Serralha","units":{"default":"kg","available":["kg"]}},{"id":"cult-panc-taioba","title":"Taioba","icon":"bi-tree","desc":"Taioba (Panc)","subgroup":"panc","group":"plantio","django_grupo":"panc","django_nome":"Taioba","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'panc',
    title: 'PANC',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'panc' } }));
  }

})(typeof window !== 'undefined' ? window : this);