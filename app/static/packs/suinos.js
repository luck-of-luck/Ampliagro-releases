/**
 * Pack: Suinos (suinos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: suinos (20 culturas)
 * Grupo: animal
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-suinos-berkshire","title":"Berkshire","icon":"bi-piggy-bank","desc":"Berkshire (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Berkshire","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-bisaro","title":"Bisaro","icon":"bi-piggy-bank","desc":"Bisaro (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Bisaro","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-caruncho","title":"Caruncho","icon":"bi-piggy-bank","desc":"Caruncho (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Caruncho","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-chester-white","title":"Chester-White","icon":"bi-piggy-bank","desc":"Chester-White (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Chester-White","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-duroc","title":"Duroc","icon":"bi-piggy-bank","desc":"Duroc (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Duroc","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-hampshire","title":"Hampshire","icon":"bi-piggy-bank","desc":"Hampshire (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Hampshire","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-ibérico","title":"Ibérico","icon":"bi-piggy-bank","desc":"Ibérico (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Ibérico","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-landrace","title":"Landrace","icon":"bi-piggy-bank","desc":"Landrace (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Landrace","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-large-white","title":"Large-White","icon":"bi-piggy-bank","desc":"Large-White (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Large-White","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-meishan","title":"Meishan","icon":"bi-piggy-bank","desc":"Meishan (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Meishan","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-monteiro","title":"Monteiro","icon":"bi-piggy-bank","desc":"Monteiro (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Monteiro","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-moura","title":"Moura","icon":"bi-piggy-bank","desc":"Moura (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Moura","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-mulefoot","title":"Mulefoot","icon":"bi-piggy-bank","desc":"Mulefoot (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Mulefoot","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-nilo","title":"Nilo","icon":"bi-piggy-bank","desc":"Nilo (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Nilo","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-piau","title":"Piau","icon":"bi-piggy-bank","desc":"Piau (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Piau","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-pietrain","title":"Pietrain","icon":"bi-piggy-bank","desc":"Pietrain (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Pietrain","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-poland-china","title":"Poland-China","icon":"bi-piggy-bank","desc":"Poland-China (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Poland-China","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-spotted","title":"Spotted","icon":"bi-piggy-bank","desc":"Spotted (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Spotted","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-tamworth","title":"Tamworth","icon":"bi-piggy-bank","desc":"Tamworth (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Tamworth","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-suinos-yorkshire","title":"Yorkshire","icon":"bi-piggy-bank","desc":"Yorkshire (Suinos)","subgroup":"suinos","group":"animal","django_grupo":"suinos","django_nome":"Yorkshire","units":{"default":"cabeca","available":["cabeca"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'suinos',
    title: 'Suinos',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'suinos' } }));
  }

})(typeof window !== 'undefined' ? window : this);