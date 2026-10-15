/**
 * Pack Updater - atualização independente de packs + fallback cloud
 * Fase 5: packs podem ser atualizados independentemente da app
 */

(function (global) {
  'use strict';

  var UPDATER = (function () {
    var CHECK_INTERVAL = 24 * 60 * 60 * 1000; // 24h
    var MANIFEST_URL = '/static/packs/manifest.json';
    var PACKS_BASE = '/static/packs/';
    var VERSION_KEY = 'ampliagro-pack-versions';

    function getStoredVersions() {
      try {
        return JSON.parse(localStorage.getItem(VERSION_KEY) || '{}');
      } catch (e) {
        return {};
      }
    }

    function setStoredVersion(packId, version) {
      var v = getStoredVersions();
      v[packId] = version;
      localStorage.setItem(VERSION_KEY, JSON.stringify(v));
    }

    // Verifica se há atualização para um pack
    async function checkPackUpdate(packId) {
      try {
        var resp = await fetch(MANIFEST_URL + '?v=' + Date.now());
        if (!resp.ok) return null;
        var manifest = await resp.json();
        var packMeta = manifest.subgroups[packId];
        if (!packMeta) return null;

        var currentVersion = getStoredVersions()[packId];
        var remoteVersion = packMeta.version || '1.0.0';

        if (currentVersion !== remoteVersion) {
          return { packId: packId, current: currentVersion, remote: remoteVersion };
        }
        return null;
      } catch (e) {
        console.warn('[PackUpdater] Falha ao verificar ' + packId + ':', e);
        return null;
      }
    }

    // Verifica todos os packs instalados
    async function checkAllUpdates() {
      var state = global.PackLoader.getState();
      var installed = Object.keys(state.installed);
      var updates = [];

      for (var i = 0; i < installed.length; i++) {
        var update = await checkPackUpdate(installed[i]);
        if (update) updates.push(update);
      }
      return updates;
    }

    // Atualiza um pack específico
    async function updatePack(packId) {
      var state = global.PackLoader.getState();

      // Remove versão antiga para forçar re-download
      delete state.installed[packId];
      global.PackLoader.saveState(state);
      localStorage.removeItem('ampliagro-pack-versions'); // força re-check

      try {
        await global.PackLoader.loadPack(packId);
        var manifest = await global.PackLoader.loadManifest();
        var meta = manifest.subgroups[packId];
        if (meta && meta.version) {
          setStoredVersion(packId, meta.version);
        }
        return { success: true, packId: packId };
      } catch (e) {
        console.error('[PackUpdater] Falha ao atualizar ' + packId + ':', e);
        return { success: false, packId: packId, error: String(e) };
      }
    }

    // Fallback cloud: se pack não instalado, tenta buscar da API
    async function cloudFallback(packId) {
      // Tenta buscar dados da API remota
      var apiUrl = '/api/packs/' + packId + '/';
      try {
        var resp = await fetch(apiUrl, { credentials: 'same-origin' });
        if (!resp.ok) throw new Error('API ' + resp.status);
        var data = await resp.json();

        // Injeta no registry como se fosse pack local
        if (data.cultures && Array.isArray(data.cultures)) {
          if (!global.AmpliagroRegistry) global.AmpliagroRegistry = { cultures: {} };
          data.cultures.forEach(function (c) {
            global.AmpliagroRegistry.cultures[c.id] = c;
          });
        }
        return { success: true, source: 'cloud' };
      } catch (e) {
        console.warn('[PackUpdater] Fallback cloud falhou para ' + packId + ':', e);
        return { success: false, error: String(e) };
      }
    }

    // Getter seguro de cultura: tenta local, depois cloud
    async function getCultureSafe(cultureId) {
      if (global.AmpliagroRegistry && global.AmpliagroRegistry.cultures[cultureId]) {
        return global.AmpliagroRegistry.cultures[cultureId];
      }

      // Tenta inferir pack do cultureId
      var packId = inferPackFromCulture(cultureId);
      if (packId) {
        // Tenta instalar pack
        try {
          await global.PackLoader.loadPack(packId);
          if (global.AmpliagroRegistry && global.AmpliagroRegistry.cultures[cultureId]) {
            return global.AmpliagroRegistry.cultures[cultureId];
          }
        } catch (e) {
          console.warn('[PackUpdater] Pack ' + packId + ' não disponível:', e);
        }

        // Fallback cloud
        try {
          await cloudFallback(packId);
          if (global.AmpliagroRegistry && global.AmpliagroRegistry.cultures[cultureId]) {
            return global.AmpliagroRegistry.cultures[cultureId];
          }
        } catch (e) {}
      }

      return null;
    }

    function inferPackFromCulture(cultureId) {
      // cultureId format: cult-graos-soja, cult-frutas-abacate, etc.
      // subgrupo é a parte após cult-<grupo>-
      var parts = cultureId.split('-');
      if (parts.length >= 3) {
        // cult-graos-soja -> graos
        // cult-frutas-abacate -> frutas
        return parts[1];
      }
      return null;
    }

    // Inicia verificação periódica
    function startPeriodicCheck() {
      setInterval(async function () {
        var updates = await checkAllUpdates();
        if (updates.length > 0 && typeof global.showToast === 'function') {
          global.showToast(
            'Atualizações',
            updates.length + ' pack(s) com atualização disponível',
            'info'
          );
        }
      }, CHECK_INTERVAL);
    }

    // API pública
    return {
      checkPackUpdate: checkPackUpdate,
      checkAllUpdates: checkAllUpdates,
      updatePack: updatePack,
      cloudFallback: cloudFallback,
      getCultureSafe: getCultureSafe,
      startPeriodicCheck: startPeriodicCheck,
    };
  })();

  global.PackUpdater = UPDATER;

  // Auto-inicia verificação periódica
  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function () {
      global.PackUpdater.startPeriodicCheck();
    });
  }
})(typeof window !== 'undefined' ? window : this);
