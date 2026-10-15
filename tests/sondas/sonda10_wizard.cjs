/* Sonda dos BURACOS que ficaram em `ia-local.js` depois da correcção da
 * pergunta-por-valor. Mede, nao testa: e' a origem dos numeros de
 * `docs/sistema/10.md`.
 *
 *   node docs/sistema/_sonda10_wizard.cjs
 */
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..');
const SRC = path.join(RAIZ, 'app', 'static', 'js', 'ia-local', 'ia-local.js');

const TALHOES = [
  { id: 1, nome: 'Pastagem - Braquiaria', area_hectare: 5, propriedade: 7 },
  { id: 3, nome: 'Talhao 1 - Catuai Vermelho', area_hectare: 3.5, propriedade: 7 },
];
const CULTURAS = [
  { id: 1, nome: 'Abobrinha', ciclo_dias: 120, grupo: 'vegetal' },
  { id: 2, nome: 'Cafe', ciclo_dias: 900, grupo: 'perene' },
];
const FUNCIONARIOS = [{ id: 1, nome: 'Joao da Silva', cargo: 'GERENTE' }];

const r = (d) => ({ ok: true, status: 200, text: async () => JSON.stringify(d) });
function casa(alvo, arr) {
  const q = String(alvo).toLowerCase();
  return arr.filter((x) => x.nome.toLowerCase().includes(q));
}
function fetchFalso(url) {
  const u = String(url);
  const s = u.split('?')[0];
  // O `?search=` tem de ser honrado. Uma sonda que ignora o filtro mede
  // outra coisa: na primeira versao desta, `?search=cultura abobrinha`
  // devolvia as culturas todas, o fluxo parava no passo `cultura` e as
  // secoes C e D mediram um caminho que ninguem percorre.
  const q = u.includes('search=') ? decodeURIComponent(u.split('search=')[1].split('&')[0]) : '';
  if (s === '/api/talhoes/') return Promise.resolve(r(TALHOES));
  if (s === '/api/culturas/') return Promise.resolve(r(q ? casa(q, CULTURAS) : CULTURAS));
  if (s === '/api/funcionarios/') return Promise.resolve(r(q ? casa(q, FUNCIONARIOS) : FUNCIONARIOS));
  if (s === '/api/piquetes/') return Promise.resolve(r([]));
  if (s === '/api/propriedades/') return Promise.resolve(r([{ id: 7, nome: 'Fazenda' }]));
  return Promise.resolve(r({ results: [] }));
}
function el() {
  const n = {
    tagName: 'DIV',
    children: [],
    attrs: {},
    style: {},
    dataset: {},
    value: '',
    textContent: '',
    innerHTML: '',
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild() {},
    setAttribute() {},
    getAttribute: () => null,
    removeAttribute() {},
    addEventListener() {},
    removeEventListener() {},
    querySelector: () => null,
    querySelectorAll: () => [],
    getBoundingClientRect: () => ({ width: 0, height: 0, top: 0, left: 0 }),
    focus() {},
    click() {},
    remove() {},
    closest: () => null,
    insertBefore() {},
    cloneNode: () => el(),
    scrollIntoView() {},
  };
  for (const p of ['firstChild', 'lastChild', 'parentNode', 'parentElement']) {
    Object.defineProperty(n, p, { get: () => null });
  }
  return n;
}
let src = fs.readFileSync(SRC, 'utf8');
src = src
  .replace(/^export\s+default\s+[^;]+;?[ \t]*$/gm, '')
  .replace(/^export\s*\{[^}]*\};?[ \t]*$/gm, '')
  .replace(/^export\s+/gm, '');
const ctx = {
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Promise,
  URL,
  URLSearchParams,
  TextEncoder,
  TextDecoder,
  AbortController,
  fetch: fetchFalso,
  FormData: class {},
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  navigator: { language: 'pt-BR', clipboard: { writeText: async () => {} } },
  location: { href: '', pathname: '/', search: '', reload() {}, assign() {} },
  history: { pushState() {} },
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  requestAnimationFrame: (f) => setTimeout(f, 0),
  alert() {},
};
ctx.window = ctx;
ctx.self = ctx;
ctx.globalThis = ctx;
ctx.document = {
  body: el(),
  head: el(),
  documentElement: el(),
  cookie: 'csrftoken=x',
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => el(),
  createTextNode: () => ({}),
  addEventListener() {},
  removeEventListener() {},
  readyState: 'complete',
};
ctx.iaLocal = null;
vm.createContext(ctx);
vm.runInContext(
  src +
    '\n;globalThis.__ia={wizTalhaoStart,wizTalhaoStep,get wizTalhaoF(){return wizTalhaoF},' +
    'wizFuncStart,wizFuncStep,get wizFunc(){return wizFunc},' +
    'wizSafraStart,wizSafraStep,get wizSafra(){return wizSafra},' +
    'wizAnimalStart,wizAnimalStep,get wizAnimal(){return wizAnimal},' +
    'wizEhPergunta,wizEscolher,wizDispensavel,WIZ_PASSOS_LISTA};',
  ctx,
  { filename: 'ia-local.js' }
);
const ia = ctx.__ia;

function linha(rot, txt) {
  const s = String(txt || '');
  console.log('  ' + rot + ' "' + s.slice(0, 150) + '"');
}

(async () => {
  console.log('='.repeat(78));
  console.log('A. WIZARD TALHAO — o passo do NOME nao tem guarda de pergunta');
  console.log('='.repeat(78));
  ia.wizTalhaoStart('cadastrar talhao');
  linha('pergunta:', 'como voces chamam esse talhao?');
  await ia.wizTalhaoStep('como voces chamam esse talhao?');
  console.log('    >> f.nome = ' + JSON.stringify(ia.wizTalhaoF.nome));
  console.log('    >> f.step = ' + ia.wizTalhaoF.step);
  await ia.wizTalhaoStep('12');
  console.log('    (depois da área) passo = ' + ia.wizTalhaoF.step + '  nome = ' + JSON.stringify(ia.wizTalhaoF.nome));
  console.log('    >> o POST vai com nome = ' + JSON.stringify(ia.wizTalhaoF.nome));

  console.log();
  console.log('='.repeat(78));
  console.log('B. WIZARD FUNCIONARIO — o NOME e a ADMISSAO');
  console.log('='.repeat(78));
  ia.wizFuncStart('cadastrar funcionario');
  await ia.wizFuncStep('como voces chamam ele?');
  console.log('    >> f.nome = ' + JSON.stringify(ia.wizFunc.nome));
  await ia.wizFuncStep('tratorista');
  await ia.wizFuncStep('a combinar');
  console.log('    passo antes da admissão = ' + ia.wizFunc.step);
  linha('pergunta:', 'quando ele entrou?');
  await ia.wizFuncStep('quando ele entrou?');
  console.log('    >> f.admissao = ' + JSON.stringify(ia.wizFunc.admissao) + '   <-- HOJE, sem avisar');
  console.log('    >> passo = ' + ia.wizFunc.step);

  console.log();
  console.log('='.repeat(78));
  console.log('C. SAFRA — passos NUMERICOS com uma pergunta');
  console.log('='.repeat(78));
  await ia.wizSafraStart('cadastrar safra');
  await ia.wizSafraStep('cultura abobrinha');
  await ia.wizSafraStep('Safra Abobrinha 2026');
  await ia.wizSafraStep('Talhao 1 - Catuai Vermelho');
  console.log('    passo = ' + ia.wizSafra.step);
  linha('pergunta:', 'que ano voces usam por ai?');
  await ia.wizSafraStep('que ano voces usam por ai?');
  console.log('    >> w.ano = ' + JSON.stringify(ia.wizSafra.ano) + '  passo = ' + ia.wizSafra.step);
  linha('pergunta:', 'quanto custa a semente?');
  await ia.wizSafraStep('quanto custa a semente?');
  console.log('    >> w.area = ' + JSON.stringify(ia.wizSafra.area) + '  passo = ' + ia.wizSafra.step);

  console.log();
  console.log('='.repeat(78));
  console.log('D. SAFRA — o ANO com uma pergunta que tem um numero dentro');
  console.log('='.repeat(78));
  await ia.wizSafraStart('cadastrar safra');
  await ia.wizSafraStep('cultura abobrinha');
  await ia.wizSafraStep('Safra Abobrinha 2026');
  await ia.wizSafraStep('pular');
  console.log('    passo = ' + ia.wizSafra.step);
  await ia.wizSafraStep('a safra de 2019 foi a melhor, qual o ano?');
  console.log('    >> w.ano = ' + JSON.stringify(ia.wizSafra.ano) + '  passo = ' + ia.wizSafra.step);

  console.log();
  console.log('='.repeat(78));
  console.log('E. ANIMAL — o piquete pergunta o talhao (passo NAO declarado)');
  console.log('='.repeat(78));
  console.log('    WIZ_PASSOS_LISTA tem "animal:piq_talhao"? ' + !!ia.WIZ_PASSOS_LISTA['animal:piq_talhao']);
  ia.wizAnimalStart('cadastrar lote');
  await ia.wizAnimalStep('boi');
  await ia.wizAnimalStep('corte');
  await ia.wizAnimalStep('nelore');
  await ia.wizAnimalStep('20');
  await ia.wizAnimalStep('450');
  console.log('    passo = ' + ia.wizAnimal.step);
  await ia.wizAnimalStep('20/01/2026');
  console.log('    passo = ' + ia.wizAnimal.step);
  await ia.wizAnimalStep('piquete norte');
  await ia.wizAnimalStep('5');
  await ia.wizAnimalStep('1.5');
  console.log('    passo = ' + ia.wizAnimal.step);
  linha('pergunta:', 'qual talhao temos disponivel?');
  const rr = await ia.wizAnimalStep('qual talhao temos disponivel?');
  linha('resposta:', rr);
  console.log('    passo = ' + ia.wizAnimal.step);

  console.log();
  console.log('='.repeat(78));
  console.log('F. COBERTURA DE WIZ_PASSOS_LISTA vs os passos que leem uma lista');
  console.log('='.repeat(78));
  console.log('    declarados: ' + Object.keys(ia.WIZ_PASSOS_LISTA).join(', '));
})();