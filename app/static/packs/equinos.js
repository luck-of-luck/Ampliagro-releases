/**
 * Pack: Equinos (equinos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: equinos (20 culturas)
 * Grupo: animal
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-equinos-andaluz","title":"Andaluz","icon":"bi-piggy-bank","desc":"Andaluz (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Andaluz","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-appaloosa","title":"Appaloosa","icon":"bi-piggy-bank","desc":"Appaloosa (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Appaloosa","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-bretao","title":"Bretão","icon":"bi-piggy-bank","desc":"Bretão (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Bretão","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-burro","title":"Burro","icon":"bi-piggy-bank","desc":"Burro (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Burro","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-campolina","title":"Campolina","icon":"bi-piggy-bank","desc":"Campolina (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Campolina","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-clydesdale","title":"Clydesdale","icon":"bi-piggy-bank","desc":"Clydesdale (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Clydesdale","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-crioulo","title":"Crioulo","icon":"bi-piggy-bank","desc":"Crioulo (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Crioulo","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-friesian","title":"Friesian","icon":"bi-piggy-bank","desc":"Friesian (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Friesian","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-jumento","title":"Jumento","icon":"bi-piggy-bank","desc":"Jumento (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Jumento","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-lusitano","title":"Lusitano","icon":"bi-piggy-bank","desc":"Lusitano (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Lusitano","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-mangalarga-marchador","title":"Mangalarga-Marchador","icon":"bi-piggy-bank","desc":"Mangalarga-Marchador (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Mangalarga-Marchador","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-mula","title":"Mula","icon":"bi-piggy-bank","desc":"Mula (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Mula","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-mustang","title":"Mustang","icon":"bi-piggy-bank","desc":"Mustang (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Mustang","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-paint-horse","title":"Paint-Horse","icon":"bi-piggy-bank","desc":"Paint-Horse (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Paint-Horse","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-percheron","title":"Percheron","icon":"bi-piggy-bank","desc":"Percheron (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Percheron","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-puro-sangue-inglês","title":"Puro-Sangue-Inglês","icon":"bi-piggy-bank","desc":"Puro-Sangue-Inglês (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Puro-Sangue-Inglês","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-pônei","title":"Pônei","icon":"bi-piggy-bank","desc":"Pônei (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Pônei","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-quarto-de-milha","title":"Quarto-de-Milha","icon":"bi-piggy-bank","desc":"Quarto-de-Milha (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Quarto-de-Milha","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-shire","title":"Shire","icon":"bi-piggy-bank","desc":"Shire (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Shire","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-equinos-árabe","title":"Árabe","icon":"bi-piggy-bank","desc":"Árabe (Equinos)","subgroup":"equinos","group":"animal","django_grupo":"equinos","django_nome":"Árabe","units":{"default":"cabeca","available":["cabeca"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'equinos',
    title: 'Equinos',
    icon: 'bi-hospital',
    group: 'animal',
    culture_count: 20,
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'equinos' } }));
  }

})(typeof window !== 'undefined' ? window : this);