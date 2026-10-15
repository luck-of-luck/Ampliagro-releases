/**
 * Verifica o ramo `clima` de `formatarDadosNatural` contra o payload REAL do
 * servidor — não contra uma transcrição em Python.
 *
 * POR QUE EXECUTAR O JS E NÃO REESCREVER A LÓGICA
 * -------------------------------------------------
 * A primeira sonda desta defect traduziu o ramo do JavaScript para Python e
 * executou a tradução. Isso prova que a tradução estava certa, o que não é o
 * que interessa. O que interessa é o que o PRODUCTOR lê, e o produtor lê o
 * que este ficheiro devolve.
 *
 * Este harness extrai o ramo tal como está escrito no ficheiro em produção, e
 * corre-o. Se alguém o reescrever, é este código que fica a ler a versão nova
 * — sem ninguém se lembrar de actualizar uma cópia.
 *
 * USO
 * ---
 *   python scripts/clima_payload.py > /tmp/clima.json     # payload real
 *   node scripts/verifica_clima_chat.mjs /tmp/clima.json
 */

import { readFileSync } from 'node:fs';

const caminhoJS = 'app/static/js/ia-local/ia-local.js';
const payloadPath = process.argv[2];

if (!payloadPath) {
  console.error('uso: node verifica_clima_chat.mjs <payload.json>');
  process.exit(2);
}

const fonte = readFileSync(caminhoJS, 'utf8');
const bruto = readFileSync(payloadPath, 'utf8');
// O BOM do PowerShell 5.1 (`Out-File -Encoding utf8`) chega aqui como U+FEFF e
// faz o JSON.parse rebentar com um erro que não aponta para a BOM. Tira-se o
// primeiro caractere se for BOM, e só ele — não um `trim()` às cegas, que
// comia conteúdo.
const semBOM = bruto.charCodeAt(0) === 0xfeff ? bruto.slice(1) : bruto;
let payload;
try {
  payload = JSON.parse(semBOM);
} catch (e) {
  console.error(`payload ilegível em ${payloadPath}: ${e.message}`);
  process.exit(2);
}

// Extrair o ramo do clima. Começa no `if (recurso === 'clima'` e termina no
// primeiro `}` que fecha o `if` a dois níveis — o ramo não tem `if` aninhado
// que confunda, porque as guardas internas são ternários.
const inicio = fonte.indexOf("if (recurso === 'clima'");
if (inicio === -1) {
  console.error('ramo do clima não encontrado em', caminhoJS);
  process.exit(2);
}

let nivel = 0;
let i = inicio;
let fim = -1;
for (; i < fonte.length; i++) {
  const c = fonte[i];
  if (c === '{') nivel++;
  else if (c === '}') {
    nivel--;
    if (nivel === 0) {
      fim = i + 1;
      break;
    }
  }
}
if (fim === -1) {
  console.error('não consegui fechar o ramo do clima');
  process.exit(2);
}

const ramo = fonte.slice(inicio, fim);

// O ramo usa `return`, portanto tem de viver dentro de uma função. Envolve-se
// no corpo de `formatarDadosNatural` para que o `return` signifique o mesmo
// que significa lá dentro.
const corpo = `
function formatarDadosNatural(recurso, data) {
  const fmtNum = (v, d = 0) => (v === null || v === undefined ? '—' : Number(v).toFixed(d));
  ${ramo}
  return '(o ramo nao devolveu nada)';
}
`;

const fn = new Function(`${corpo}; return formatarDadosNatural;`)();

console.log('='.repeat(72));
console.log('O QUE O PRODUCTOR LÊ NO CHAT DA AMPLIA');
console.log('='.repeat(72));
console.log();
console.log('fonte (servidor) :', JSON.stringify(payload.fonte));
console.log('payload          :', JSON.stringify(payload).slice(0, 160));
console.log();

const texto = fn('clima', payload);
console.log('resposta do chat :');
console.log('  >>>', texto);
console.log();

const fonteReal = String(payload.fonte || '').toLowerCase();
const eSimulado = fonteReal === 'simulado' || fonteReal === 'fallback';
const falaNaFonte =
  /simulad/i.test(texto) || /fonte:/i.test(texto) || /não tenho previsão/i.test(texto);
const despejoJSON = /\{|\["dia"|icone:/.test(texto);

console.log('verificações');
console.log('  o servidor diz que é simulado :', eSimulado);
console.log('  o chat fala nisso           :', falaNaFonte);
console.log('  devolveu JSON cru            :', despejoJSON);
console.log();

let mau = false;
if (despejoJSON) {
  console.log('>>> FALHA: despejo de JSON cru. O produtor lê uma lista, não uma frase.');
  mau = true;
}
if (eSimulado && !falaNaFonte) {
  console.log('>>> FALHA: número simulado apresentado como previsão, sem qualquer marca.');
  mau = true;
}
if (!eSimulado && !despejoJSON && !falaNaFonte) {
  console.log('>>> FALHA: fonte real, mas o texto não diz de onde veio.');
  mau = true;
}

console.log(mau ? 'RESULTADO: FALHOU' : 'RESULTADO: o produtor lê texto honesto');
process.exit(mau ? 1 : 0);
