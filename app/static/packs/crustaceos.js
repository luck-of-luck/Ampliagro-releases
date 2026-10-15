/**
 * Pack: Crustaceos (crustaceos)
 * Gerado automaticamente - NÃO EDITAR MANUALMENTE
 * Versão do manifest: 2.0.0
 * Subgrupo: crustaceos (20 culturas)
 * Grupo: aquatica
 */

(function (global) {
  'use strict';

  // Dados das culturas deste pack
  var CULTURES = [{"id":"cult-crustaceos-camarao","title":"Camarão","icon":"bi-water","desc":"Camarão (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Camarão","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-camarao-pitu","title":"Camarão-pitu","icon":"bi-water","desc":"Camarão-pitu (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Camarão-pitu","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-caramujo","title":"Caramujo","icon":"bi-water","desc":"Caramujo (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Caramujo","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-caranguejo","title":"Caranguejo","icon":"bi-water","desc":"Caranguejo (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Caranguejo","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-centolla","title":"Centolla","icon":"bi-water","desc":"Centolla (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Centolla","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-choco","title":"Choco","icon":"bi-water","desc":"Choco (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Choco","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-craca","title":"Craca","icon":"bi-water","desc":"Craca (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Craca","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-escargot","title":"Escargot","icon":"bi-water","desc":"Escargot (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Escargot","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-guaiamum","title":"Guaiamum","icon":"bi-water","desc":"Guaiamum (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Guaiamum","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-lagosta","title":"Lagosta","icon":"bi-water","desc":"Lagosta (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Lagosta","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-lagostim","title":"Lagostim","icon":"bi-water","desc":"Lagostim (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Lagostim","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-lula","title":"Lula","icon":"bi-water","desc":"Lula (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Lula","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-lula-gigante","title":"Lula-gigante","icon":"bi-water","desc":"Lula-gigante (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Lula-gigante","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-mexilhao","title":"Mexilhão","icon":"bi-water","desc":"Mexilhão (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Mexilhão","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-ostra","title":"Ostra","icon":"bi-water","desc":"Ostra (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Ostra","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-polvo","title":"Polvo","icon":"bi-water","desc":"Polvo (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Polvo","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-santola","title":"Santola","icon":"bi-water","desc":"Santola (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Santola","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-siba","title":"Siba","icon":"bi-water","desc":"Siba (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Siba","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-siri","title":"Siri","icon":"bi-water","desc":"Siri (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Siri","units":{"default":"kg","available":["kg"]}},{"id":"cult-crustaceos-vieira","title":"Vieira","icon":"bi-water","desc":"Vieira (Crustaceos)","subgroup":"crustaceos","group":"aquatica","django_grupo":"crustaceos","django_nome":"Vieira","units":{"default":"kg","available":["kg"]}}];

  // Metadados do pack
  var PACK_META = {
    id: 'crustaceos',
    title: 'Crustaceos',
    icon: 'bi-droplet',
    group: 'aquatica',
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
    window.dispatchEvent(new CustomEvent('packloaded', { detail: { pack: 'crustaceos' } }));
  }

})(typeof window !== 'undefined' ? window : this);