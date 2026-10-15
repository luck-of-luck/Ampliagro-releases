/**
 * Pack: Oleaginosas (oleaginosas)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: oleaginosas (16 culturas)
 * Grupo: plantio
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-oleaginosas-amendoim","title":"Amendoim","icon":"bi-tree","desc":"Amendoim (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Amendoim","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-amêndoa","title":"Amêndoa","icon":"bi-tree","desc":"Amêndoa (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Amêndoa","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-avela","title":"Avelã","icon":"bi-tree","desc":"Avelã (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Avelã","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-canola","title":"Canola","icon":"bi-tree","desc":"Canola (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Canola","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-castanha-de-caju","title":"Castanha-de-Caju","icon":"bi-tree","desc":"Castanha-de-Caju (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Castanha-de-Caju","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-castanha-do-pará","title":"Castanha-do-Pará","icon":"bi-tree","desc":"Castanha-do-Pará (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Castanha-do-Pará","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-chia","title":"Chia","icon":"bi-tree","desc":"Chia (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Chia","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-cártamo","title":"Cártamo","icon":"bi-tree","desc":"Cártamo (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Cártamo","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-gergelim","title":"Gergelim","icon":"bi-tree","desc":"Gergelim (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Gergelim","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-girassol","title":"Girassol","icon":"bi-tree","desc":"Girassol (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Girassol","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-linhaca","title":"Linhaça","icon":"bi-tree","desc":"Linhaça (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Linhaça","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-macadâmia","title":"Macadâmia","icon":"bi-tree","desc":"Macadâmia (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Macadâmia","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-mamona","title":"Mamona","icon":"bi-tree","desc":"Mamona (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Mamona","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-noz","title":"Noz","icon":"bi-tree","desc":"Noz (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Noz","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-noz-peca","title":"Noz-pecã","icon":"bi-tree","desc":"Noz-pecã (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Noz-pecã","units":{"default":"kg","available":["kg"]}},{"id":"cult-oleaginosas-pistache","title":"Pistache","icon":"bi-tree","desc":"Pistache (Oleaginosas)","subgroup":"oleaginosas","group":"plantio","django_grupo":"oleaginosas","django_nome":"Pistache","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'oleaginosas',
    title: 'Oleaginosas',
    icon: 'bi-droplet-half',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'oleaginosas' } }));
  }

})(typeof window !== 'undefined' ? window : this);