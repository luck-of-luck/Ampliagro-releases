/**
 * Core Ampliagro - núcleo mínimo (~50 KB gzipped)
 * Registry de culturas, widget system, pack loader
 * Carrega ANTES de qualquer pack
 */

(function (global) {
  'use strict';

  // Registry global de culturas (preenchido pelos packs)
  var AmpliagroRegistry = {
    cultures: {},      // id -> culture object
    widgets: {},       // widgetId -> widget module
    groups: {},        // groupId -> group meta
    subgroups: {},     // subgroupId -> subgroup meta
    packs: {},         // packId -> { installed, version, ... }
  };

  global.AmpliagroRegistry = AmpliagroRegistry;

  // Helper: obtém cultura por ID (fallback para metadata do manifest)
  function getCulture(id) {
    return AmpliagroRegistry.cultures[id] || null;
  }

  // Helper: lista culturas por subgrupo
  function getCulturesBySubgroup(subgroupId) {
    return Object.values(AmpliagroRegistry.cultures)
      .filter(function (c) { return c.subgroup === subgroupId; });
  }

  // Helper: lista culturas por grupo
  function getCulturesByGroup(groupId) {
    return Object.values(AmpliagroRegistry.cultures)
      .filter(function (c) { return c.group === groupId; });
  }

  // Helper: obtém metadados de subgrupo
  function getSubgroupMeta(subgroupId) {
    return AmpliagroRegistry.subgroups[subgroupId] || null;
  }

  // Expõe API
  global.Ampliagro = {
    registry: AmpliagroRegistry,
    getCulture: getCulture,
    getCulturesBySubgroup: getCulturesBySubgroup,
    getCulturesByGroup: getCulturesByGroup,
    getSubgroupMeta: getSubgroupMeta,
  };

  // Sinaliza core pronto
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('coreloaded'));
  }

})(typeof window !== 'undefined' ? window : this);