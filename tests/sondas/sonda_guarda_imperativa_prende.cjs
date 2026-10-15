/* Os testes novos PRENDEM, ou passam a vazio?
 *
 * Um teste que passa e' barato. Este ficheiro tira a protecção ao
 * `ia-local.js` de facto — reescreve o `WIZ_IMPERATIVO` para uma regex que
 * nao apanha nada — e ve se os testes ficam vermelhos.
 *
 * Nao escreve nada em disco: a alteracao e' in-memory, neste processo.
 */

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..');
const ALVO = path.join(RAIZ, 'app', 'static', 'js', 'ia-local', 'ia-local.js');
const SUITE = path.join(RAIZ, 'app', 'static', 'js', 'tests_pergunta_nao_e_valor.cjs');

const original = fs.readFileSync(ALVO, 'utf8');

/* Troca a regex por uma que não apanha nada, sem usar regex para a
   encontrar: um `\/` mal escapado fecha o literal e o ficheiro nem chega a
   correr — que foi exactamente o que aconteceu na primeira versão. */
function semImperativo(txt) {
  const marcador = 'const WIZ_IMPERATIVO =';
  const i = txt.indexOf(marcador);
  if (i === -1) return txt;
  const fim = txt.indexOf(';', i);
  if (fim === -1) return txt;
  return txt.slice(0, i) + 'const WIZ_IMPERATIVO = /^(zzzznaoexiste)\\b/;' + txt.slice(fim + 1);
}

/* Uma regex que parece certa e não apanha nada — o erro que eu COMETI
   ("prefer(?:o|e)" nunca casa "prefiro"). */
const QUEBRADA = semImperativo(original);

if (QUEBRADA === original) {
  console.error('a substituicao nao pegou: o formato de WIZ_IMPERATIVO mudou.');
  console.error('actualiza este ficheiro — e' + ' NORMAL que se quebre quando o codigo muda.');
  process.exit(2);
}

/* Escreve a versao quebrada, corre a suite, e restaura tudo. */
fs.writeFileSync(ALVO, QUEBRADA, 'utf8');
let rc;
try {
  rc = require('child_process').spawnSync(process.execPath, [SUITE], {
    encoding: 'utf8',
    cwd: RAIZ,
  });
} finally {
  fs.writeFileSync(ALVO, original, 'utf8');
}

const saida = rc.stdout + rc.stderr;
const vermelhos = (saida.match(/^\s*FAIL\s/gm) || []).length;
const ultimas = saida
  .split('\n')
  .filter((l) => /^\s*-\s/.test(l))
  .slice(0, 6);

console.log('=== a suite corre COM a proteccao partida ===');
console.log('  exit code : ' + rc.status + '  (tem de ser != 0)');
console.log('  FAIL      : ' + vermelhos + '  (tem de ser > 0)');
if (ultimas.length) {
  console.log('  primeiras falhas:');
  ultimas.forEach((l) => console.log('    ' + l.trim()));
}

console.log('\n=== o ficheiro foi restaurado? ===');
const depois = fs.readFileSync(ALVO, 'utf8');
console.log('  identico ao original: ' + (depois === original));
if (depois !== original) {
  console.error('  RESTAURACAO FALHOU — o repositorio ficou com a versao quebrada.');
  process.exit(2);
}

const bom = rc.status !== 0 && vermelhos > 0 && depois === original;
console.log('\n' + (bom ? 'RESULTADO: os testes PRENDEM a regressao' : 'RESULTADO: NAO prendem'));
process.exit(bom ? 0 : 1);
