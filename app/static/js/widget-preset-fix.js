/* Fix for preset isolation and F12 compression - v2 */
(function () {
  console.log('[PresetFix v2] Initializing');
  var MIN_WIDTH = 900;
  var origPersist = window.persistPresetWidgets;
  if (origPersist) {
    window.persistPresetWidgets = function (presetName, value) {
      if (window.innerWidth < MIN_WIDTH) {
        console.warn('[PresetFix] Skip persist when compressed', window.innerWidth);
        return;
      }
      var cloned = JSON.parse(JSON.stringify(value));
      return origPersist.call(this, presetName, cloned);
    };
  }
  window.addEventListener('load', function () {
    setTimeout(function () {
      var src = window.PRESETS || window.PRESET_WIDGETS_JSON;
      if (src) {
        var presets = Object.keys(src);
        var order = [];
        try {
          order = JSON.parse(localStorage.getItem('matrix-preset-order') || '[]');
        } catch (e) {}
        console.log(
          '[PresetFix v2] Presets:',
          presets.join(', ') || '(vazio)',
          '| order:',
          (order || []).join(', ') || '(vazio)',
          '| active:',
          localStorage.getItem('matrix-active-preset') || '-'
        );
        if (!presets.length)
          console.warn(
            '[PresetFix] nenhum preset — hard-coded Agua/Lua não carregou, verifique v8 + allowlist'
          );
      }
    }, 2500);
  });
  var wasCompressed = window.innerWidth < MIN_WIDTH;
  window.addEventListener('resize', function () {
    var isCompressed = window.innerWidth < MIN_WIDTH;
    if (isCompressed && !wasCompressed) {
      console.log('[PresetFix] Entered compressed mode');
      wasCompressed = true;
    } else if (!isCompressed && wasCompressed) {
      console.log('[PresetFix] Exited compressed mode');
      wasCompressed = false;
      if (typeof window.renderWidgetsOnMatrix === 'function') {
        setTimeout(function () {
          window.renderWidgetsOnMatrix();
        }, 100);
      }
    }
  });
  console.log('[PresetFix v2] Ready');
})();
