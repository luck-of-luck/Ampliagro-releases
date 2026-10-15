/**
 * Pack: Aves (aves)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: aves (15 culturas)
 * Grupo: animal
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-aves-avestruz","title":"Avestruz","icon":"bi-piggy-bank","desc":"Avestruz (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Avestruz","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-cisne","title":"Cisne","icon":"bi-piggy-bank","desc":"Cisne (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Cisne","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-codorna","title":"Codorna","icon":"bi-piggy-bank","desc":"Codorna (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Codorna","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-ema","title":"Ema","icon":"bi-piggy-bank","desc":"Ema (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Ema","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-faisao","title":"Faisão","icon":"bi-piggy-bank","desc":"Faisão (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Faisão","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-galinha","title":"Galinha","icon":"bi-piggy-bank","desc":"Galinha (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Galinha","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-galinha-d'angola","title":"Galinha-d'Angola","icon":"bi-piggy-bank","desc":"Galinha-d'Angola (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Galinha-d'Angola","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-ganso","title":"Ganso","icon":"bi-piggy-bank","desc":"Ganso (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Ganso","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-mandarim","title":"Mandarim","icon":"bi-piggy-bank","desc":"Mandarim (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Mandarim","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-marreco","title":"Marreco","icon":"bi-piggy-bank","desc":"Marreco (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Marreco","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-pato","title":"Pato","icon":"bi-piggy-bank","desc":"Pato (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Pato","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-pavao","title":"Pavão","icon":"bi-piggy-bank","desc":"Pavão (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Pavão","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-perdiz","title":"Perdiz","icon":"bi-piggy-bank","desc":"Perdiz (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Perdiz","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-peru","title":"Peru","icon":"bi-piggy-bank","desc":"Peru (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Peru","units":{"default":"cabeca","available":["cabeca"]}},{"id":"cult-aves-pomba","title":"Pomba","icon":"bi-piggy-bank","desc":"Pomba (Aves)","subgroup":"aves","group":"animal","django_grupo":"aves","django_nome":"Pomba","units":{"default":"cabeca","available":["cabeca"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'aves',
    title: 'Aves',
    icon: 'bi-hospital',
    group: 'animal',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'aves' } }));
  }

})(typeof window !== 'undefined' ? window : this);