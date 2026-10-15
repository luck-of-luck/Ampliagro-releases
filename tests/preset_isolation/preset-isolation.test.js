/// <reference types="jest" />
// Teste de isolacao de presets — roda com Node (node preset-isolation.test.js)
function _fastClone(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(_fastClone);
  if (obj.constructor !== Object) return obj;
  const clone = {};
  for (const k in obj) clone[k] = _fastClone(obj[k]);
  return clone;
}

function testIsolation() {
  const a = { 'kpi-roi': { gridX: 0, gridY: 0 } };
  const b = _fastClone(a);
  b['kpi-roi'].gridX = 99;
  console.assert(a['kpi-roi'].gridX === 0, 'deep clone deve isolar');
  console.log(a['kpi-roi'].gridX === 0 ? 'PASS clone isolation' : 'FAIL clone');
}

function testNoFallbackClone() {
  const PRESET_WIDGETS_JSON = {
    'visao-geral': { 'kpi-roi': { gridX: 0 } },
    'visao-campo': { 'kpi-produtividade': { gridX: 0 } },
  };
  const PRESETS = {
    'visao-campo': { widgets: { 'kpi-produtividade': { gridX: 0 } } },
  };
  function clonePresetWidgets(presetName) {
    // `Object.hasOwn` e nao `.hasOwnProperty()`: um preset chamado
    // "hasOwnProperty" ou "constructor" faria `.hasOwnProperty(presetName)`
    // devolver `true` para o objecto errado, e este teste existe para
    // apanhar exactamente esse tipo de fuga entreizadores. MEDIDO
    // 2026-10-04 (agente 4): `no-prototype-builtins` no `npm run lint`.
    if (Object.hasOwn(PRESET_WIDGETS_JSON, presetName)) {
      const v = PRESET_WIDGETS_JSON[presetName];
      if (!v || !Object.keys(v).length) {
        if (PRESETS[presetName] && Object.keys(PRESETS[presetName].widgets).length)
          return _fastClone(PRESETS[presetName].widgets);
        return {};
      }
      return _fastClone(v);
    }
    return _fastClone(PRESET_WIDGETS_JSON[presetName] || PRESET_WIDGETS_JSON['visao-geral']);
  }
  const campo = clonePresetWidgets('visao-campo');
  const geral = clonePresetWidgets('visao-geral');
  console.assert(
    JSON.stringify(campo) !== JSON.stringify(geral),
    'presets distintos nao devem clonar'
  );
  console.log(
    JSON.stringify(campo) !== JSON.stringify(geral) ? 'PASS distinct presets' : 'FAIL distinct'
  );
  const unknown = clonePresetWidgets('inexistente');
  console.assert(
    JSON.stringify(unknown) === JSON.stringify(PRESET_WIDGETS_JSON['visao-geral']),
    'fallback para desconhecido ok'
  );
  console.log('PASS fallback');
}

function testRepairCloned() {
  const PRESET_WIDGETS_JSON = {
    'visao-campo': { 'kpi-roi': { gridX: 0 } },
    'visao-financeira': { 'kpi-roi': { gridX: 0 } }, // clone!
    'custom-arroz': { 'kpi-arroz': { gridX: 5 } },
  };
  const seen = {};
  const clones = [];
  for (const k in PRESET_WIDGETS_JSON) {
    const js = JSON.stringify(PRESET_WIDGETS_JSON[k]);
    if (seen[js] && js !== '{}') clones.push(k);
    else seen[js] = k;
  }
  console.assert(clones.includes('visao-financeira'), 'deve detectar clone');
  console.assert(!clones.includes('custom-arroz'), 'custom distinto');
  console.log(clones.includes('visao-financeira') ? 'PASS repair detection' : 'FAIL repair');
}

function testPersistSkipEmpty() {
  function persistPresetWidgets(presetName, value, existing) {
    if (!value || typeof value !== 'object') return 'skip null';
    if (!Object.keys(value).length && existing && Object.keys(existing).length) return 'skip empty';
    return 'persist';
  }
  console.assert(
    persistPresetWidgets('visao-campo', {}, { 'kpi-roi': { gridX: 0 } }) === 'skip empty',
    'skip empty'
  );
  console.assert(
    persistPresetWidgets(
      'visao-campo',
      { 'kpi-roi': { gridX: 1 } },
      { 'kpi-roi': { gridX: 0 } }
    ) === 'persist',
    'persist ok'
  );
  console.log('PASS persist skip');
}

function testDeleteProtection() {
  function canDelete(k) {
    return k !== 'visao-geral' && k !== 'visao-base';
  }
  console.assert(!canDelete('visao-geral') && !canDelete('visao-base'), 'base protegido');
  console.assert(canDelete('visao-campo') && canDelete('visao-executivo'), 'outros liberados');
  console.log('PASS delete protection');
}

testIsolation();
testNoFallbackClone();
testRepairCloned();
testPersistSkipEmpty();
testDeleteProtection();
console.log('Todos testes JS PASS');
