/**
 * Pack: Ervas (ervas)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: ervas (13 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-ervas-alecrim","title":"Alecrim","icon":"bi-tree","desc":"Alecrim (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Alecrim","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-alfavaca","title":"Alfavaca","icon":"bi-tree","desc":"Alfavaca (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Alfavaca","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-camomila","title":"Camomila","icon":"bi-tree","desc":"Camomila (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Camomila","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-erva-doce","title":"Erva-doce","icon":"bi-tree","desc":"Erva-doce (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Erva-doce","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-estragao","title":"Estragão","icon":"bi-tree","desc":"Estragão (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Estragão","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-funcho","title":"Funcho","icon":"bi-tree","desc":"Funcho (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Funcho","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-hortela","title":"Hortelã","icon":"bi-tree","desc":"Hortelã (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Hortelã","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-hortela-pimenta","title":"Hortelã-pimenta","icon":"bi-tree","desc":"Hortelã-pimenta (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Hortelã-pimenta","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-mangerona","title":"Mangerona","icon":"bi-tree","desc":"Mangerona (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Mangerona","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-manjericao","title":"Manjericão","icon":"bi-tree","desc":"Manjericão (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Manjericão","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-orégano","title":"Orégano","icon":"bi-tree","desc":"Orégano (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Orégano","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-sálvia","title":"Sálvia","icon":"bi-tree","desc":"Sálvia (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Sálvia","units":{"default":"kg","available":["kg"]}},{"id":"cult-ervas-tomilho","title":"Tomilho","icon":"bi-tree","desc":"Tomilho (Ervas)","subgroup":"ervas","group":"plantio","django_grupo":"ervas","django_nome":"Tomilho","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'ervas',
    title: 'Ervas',
    icon: 'bi-tree',
    group: 'plantio',
    culture_count: 13,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'ervas' } }));
  }

})(typeof window !== 'undefined' ? window : this);