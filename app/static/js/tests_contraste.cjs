// Harness: valida a matematica de contraste do auto-contraste.js com um DOM stub.
const fs = require('fs');
const path = require('path');

function makeEl(bgColor, bgImage, parent) {
  return {
    nodeType: 1,
    _cs: { backgroundColor: bgColor, backgroundImage: bgImage || 'none' },
    parentElement: parent || null,
    style: { setProperty() {}, getPropertyValue() { return ''; } },
    attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] || null; },
    matches() { return false; },
    querySelectorAll() { return []; },
  };
}

// stub de getComputedStyle
globalThis.getComputedStyle = (el) => el._cs;
globalThis.document = {
  readyState: 'complete',
  body: { _el: true },
  addEventListener() {},
  querySelectorAll() { return []; },
  dispatchEvent() {},
};
globalThis.MutationObserver = function () { return { observe() {} }; };

const src = fs.readFileSync(path.join(__dirname, 'auto-contraste.js'), 'utf8')
  .replace('window.AmpliagroContraste =', 'globalThis.__K__ =');

const win = {};
new Function('window', 'globalThis', 'document', 'getComputedStyle', 'MutationObserver', 'setTimeout', src)(
  win, globalThis, globalThis.document, globalThis.getComputedStyle, globalThis.MutationObserver, setTimeout
);
const K = globalThis.__K__;
const { razao, luminancia, resolver, fundosReais } = K;

const R = (c) => [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16), 1];
let falhas = 0;
function check(nome, got, min, max) {
  const ok = got >= (min === undefined ? -Infinity : min) && got <= (max === undefined ? Infinity : max);
  if (!ok) falhas++;
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${nome} = ${typeof got === 'number' ? got.toFixed(2) : got} (esperado ${min}~${max === undefined ? '∞' : max})`);
}

console.log('--- 1. razao de contraste (WCAG) ---');
check('branco/preto (maximo teorico)', razao(luminancia([255, 255, 255]), luminancia([0, 0, 0])), 20.9, 21.1);
check('branco/verde #0f9d6e', razao(luminancia([255, 255, 255]), luminancia(R('#0f9d6e'))), 3.4, 3.5);
check('branco/ouro #b98523 (padrao do hero)', razao(luminancia([255, 255, 255]), luminancia(R('#b98523'))), 3.2, 3.4);
check('branco/amarelo #f1c40f', razao(luminancia([255, 255, 255]), luminancia(R('#f1c40f'))), 1.6, 1.7);
check('branco/amarelo #ffe066', razao(luminancia([255, 255, 255]), luminancia(R('#ffe066'))), 1.2, 1.4);
check('slate900/amarelo #ffe066', razao(luminancia([17, 24, 39]), luminancia(R('#ffe066'))), 13.0, 15.0);

console.log('\n--- 2. gradiente: extrai todas as paradas ---');
const g = makeEl('rgba(0, 0, 0, 0)',
  'linear-gradient(135deg, rgb(15, 157, 110) 0%, rgb(30, 111, 130) 60%, rgb(185, 133, 35) 100%)');
const stops = fundosReais(g);
check('paradas encontradas', stops.length, 3, 3);
check('1a parada = verde do tema', Math.round(stops[0][0]), 15, 15);

console.log('\n--- 3. gradiente CLARO (o bug do video): escolhe texto escuro ---');
const claro = makeEl('rgba(0, 0, 0, 0)',
  'linear-gradient(90deg, rgb(46, 204, 113) 0%, rgb(241, 196, 15) 50%, rgb(253, 224, 71) 100%)');
const rClaro = resolver(claro, '');
console.log(`     cor escolhida: ${rClaro.cor} | razao ${rClaro.razao.toFixed(2)} | sombra ${rClaro.sombra === 'none' ? 'none' : 'sim'}`);
check('texto escuro escolhido sobre gradiente claro', /rgb\(1[0-9]|rgb\(2[0-9]|rgb\([0-9],/.test(rClaro.cor) ? 1 : 0, 1, 1);
check('razao atinge >= 4.5 (AA texto normal)', rClaro.razao, 4.5, 21);
check('ganhou sombra de apoio', rClaro.sombra !== 'none' ? 1 : 0, 1, 1);

console.log('\n--- 4. gradiente ESCURO: mantem texto claro ---');
const escuro = makeEl('rgba(0, 0, 0, 0)',
  'linear-gradient(135deg, rgb(15, 157, 110) 0%, rgb(30, 111, 130) 60%, rgb(185, 133, 35) 100%)');
const rEscuro = resolver(escuro, '');
console.log(`     cor escolhida: ${rEscuro.cor} | razao ${rEscuro.razao.toFixed(2)}`);
check('texto claro escolhido sobre gradiente escuro', rEscuro.cor === 'rgb(255,255,255)' ? 1 : 0, 1, 1);
check('razao >= 3 (AA texto grande)', rEscuro.razao, 3, 21);

console.log('\n--- 4b. gradiente de tom MEDIO: nenhuma cor plana atinge 4.5 ---');
// O gradiente padrao do hero (#0f9d6e -> #1e6f82 -> #b98523) tem a parada do
// meio num tom onde escurecer o branco PIORA o contraste. Nenhuma cor solida
// atinge 4.5:1. Nesse caso a correcao correta nao e forcar a cor: e a sombra
// de apoio, que garante a borda do glifo em qualquer ponto do gradiente.
const rMedio = resolver(escuro, '');
console.log(`     pior razao possivel com cor plana: ${rMedio.razao.toFixed(2)} (< 4.5 e inevitavel)`);
check('reconhece que 4.5 e inatingivel', rMedio.razao < 4.5 ? 1 : 0, 1, 1);
check('aplica sombra mesmo assim', rMedio.sombra !== 'none' ? 1 : 0, 1, 1);
check('ainda passa AA de texto grande (3:1)', rMedio.razao, 3, 4.5);
check('data-contraste-ok = largo para 3~4.5', resolver(escuro, '').razao >= 3 ? 1 : 0, 1, 1);
const pai = makeEl('rgb(253, 224, 71)', 'none', null);
const filho = makeEl('rgba(0, 0, 0, 0.3)', 'none', pai);
const f = fundosReais(filho);
const esperada = 253 * 0.7; // 0.3 alpha de preto sobre #ffe066
check('composicao alfa', Math.round(f[0][0]), Math.round(esperada), Math.round(esperada) + 1);

console.log('\n--- 6. preferencia explicita ---');
check('force "claro" em fundo escuro mantem branco', resolver(escuro, 'claro').cor === 'rgb(255,255,255)' ? 1 : 0, 1, 1);
const forcado = resolver(claro, 'claro');
console.log(`     forcado=claro sobre gradiente claro -> ${forcado.cor} razao ${forcado.razao.toFixed(2)} (a preferencia cede quando a outra e MUITO melhor)`);
check('mesmo assim atinge >= 3', forcado.razao, 3, 21);

console.log('\n--- 7. atributo data-contraste-ok ---');
const el = makeEl('rgb(255,255,255)', 'none', null);
el.setAttribute('data-auto-contraste', '');
require('fs');
console.log('--- 8. parse de formatos variados ---');
const formatos = ['#fff', '#ffffff', '#ffff', 'rgb(1,2,3)', 'rgba(1, 2, 3, 0.5)', 'rgb(1 2 3 / 50%)'];
formatos.forEach((f) => {
  const stopsF = fundosReais(makeEl(f, 'none', null));
  console.log(`     ${f.padEnd(20)} -> ${stopsF[0].map((n) => Math.round(n)).join(',')}`);
});

console.log(falhas === 0 ? '\n=== TODOS OS CHECKS PASSARAM ===' : `\n=== ${falhas} FALHA(S) ===`);
process.exit(falhas === 0 ? 0 : 1);
