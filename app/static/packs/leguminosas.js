/**
 * Pack: Leguminosas (leguminosas)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: leguminosas (10 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-leguminosas-ervilha","title":"Ervilha","icon":"bi-tree","desc":"Ervilha (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Ervilha","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-fava","title":"Fava","icon":"bi-tree","desc":"Fava (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Fava","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-feijao","title":"Feijão","icon":"bi-tree","desc":"Feijão (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Feijão","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-feijao-caupi","title":"Feijão-caupi","icon":"bi-tree","desc":"Feijão-caupi (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Feijão-caupi","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-feijao-guandu","title":"Feijão-guandu","icon":"bi-tree","desc":"Feijão-guandu (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Feijão-guandu","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-grao-de-bico","title":"Grão-de-bico","icon":"bi-tree","desc":"Grão-de-bico (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Grão-de-bico","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-guandu","title":"Guandu","icon":"bi-tree","desc":"Guandu (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Guandu","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-lentilha","title":"Lentilha","icon":"bi-tree","desc":"Lentilha (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Lentilha","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-soja","title":"Soja","icon":"bi-tree","desc":"Soja (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Soja","units":{"default":"kg","available":["kg"]}},{"id":"cult-leguminosas-tremoco","title":"Tremoço","icon":"bi-tree","desc":"Tremoço (Leguminosas)","subgroup":"leguminosas","group":"plantio","django_grupo":"leguminosas","django_nome":"Tremoço","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'leguminosas',
    title: 'Leguminosas',
    icon: 'bi-tree',
    group: 'plantio',
    culture_count: 10,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'leguminosas' } }));
  }

})(typeof window !== 'undefined' ? window : this);