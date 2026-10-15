/**
 * Pack: Tubérculos e Raízes (tuberculos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: tuberculos (13 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-tuberculos-batata","title":"Batata","icon":"bi-tree","desc":"Batata (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Batata","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-batata-doce","title":"Batata-doce","icon":"bi-tree","desc":"Batata-doce (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Batata-doce","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-beterraba","title":"Beterraba","icon":"bi-tree","desc":"Beterraba (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Beterraba","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-cará","title":"Cará","icon":"bi-tree","desc":"Cará (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Cará","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-inhame","title":"Inhame","icon":"bi-tree","desc":"Inhame (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Inhame","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-maca","title":"Maca","icon":"bi-tree","desc":"Maca (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Maca","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-mandioca","title":"Mandioca","icon":"bi-tree","desc":"Mandioca (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Mandioca","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-mandioquinha","title":"Mandioquinha","icon":"bi-tree","desc":"Mandioquinha (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Mandioquinha","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-nabo","title":"Nabo","icon":"bi-tree","desc":"Nabo (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Nabo","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-rabanete","title":"Rabanete","icon":"bi-tree","desc":"Rabanete (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Rabanete","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-raiz-forte","title":"Raiz-forte","icon":"bi-tree","desc":"Raiz-forte (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Raiz-forte","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-rábano","title":"Rábano","icon":"bi-tree","desc":"Rábano (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Rábano","units":{"default":"kg","available":["kg"]}},{"id":"cult-tuberculos-taro","title":"Taro","icon":"bi-tree","desc":"Taro (Tuberculos)","subgroup":"tuberculos","group":"plantio","django_grupo":"tuberculos","django_nome":"Taro","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'tuberculos',
    title: 'Tubérculos e Raízes',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'tuberculos' } }));
  }

})(typeof window !== 'undefined' ? window : this);