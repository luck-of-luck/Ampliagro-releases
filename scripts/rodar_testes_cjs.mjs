/**
 * Corre as suites `.cjs` que estavam órfãs.
 *
 * O problema que isto resolve, medido
 * ----------------------------------
 * O AmplIA tem duas famílias de teste JavaScript e só uma era automaticamente
 * executada.
 *
 *   tests/unit/*.test.js   — vitest, `npm test`, 6 ficheiros, 62 testes
 *   app/static/js/tests_*.cjs — scripts de node, 7 ficheiros, ~280 checks
 *
 * O `vitest.config.ts` tem `include: ['tests/unit/...test.{js,ts,tsx}']`, e
 * o `.cjs` está em `app/static/js/`. Nenhum `npm` script os corria. O CI
 * também não: o job de testes corre `pytest app/api/tests.py` e nunca chama
 * `npm test`.
 *
 * MEDIDO antes desta correcção: os sete `.cjs` passam todos, à mão, um a um.
 * MEDIDO o que isso significa: 280 checks que não podem falhar, porque nada
 * os executa. Um teste que nunca corre é uma opinião sobre o código, com a
 * forma de teste.
 *
 * Porque um script e não `vitest include`
 * --------------------------------------
 * Porque não são testes de vitest. Correm em `node`, escrevem no `console` e
 * saem com código de processo. Metê-los no `include` do vitest não os correria
 * — e seria pior do que não correr nada, porque pareceria que estavam
 * cobertos.
 *
 * Porque este script continua a correr se um falhar
 * -----------------------------------------------
 * Porque o objectivo é ver TUDO numa execução. Parar no primeiro ficheiro
 * esconde a segunda falha, e a segunda falha é a que ninguém vai ver.
 * O resumo final é que decide o código de saída.
 */
import { spawnSync } from 'node:child_process';
import { readdirSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PASTA = path.join(RAIZ, 'app', 'static', 'js');

function suites() {
  if (!existsSync(PASTA)) return [];
  return readdirSync(PASTA)
    .filter((n) => /^tests_.*\.cjs$/.test(n))
    .sort();
}

const lista = suites();
if (!lista.length) {
  console.log('Nenhuma suite .cjs em app/static/js/. Nada a fazer.');
  process.exit(0);
}

let falhados = [];
console.log(`A correr ${lista.length} suites .cjs de app/static/js/:\n`);

for (const nome of lista) {
  process.stdout.write(`  ${nome} ... `);
  const r = spawnSync(process.execPath, [path.join(PASTA, nome)], {
    cwd: RAIZ,
    encoding: 'utf-8',
  });
  const saida = `${r.stdout || ''}${r.stderr || ''}`;

  if (r.status === 0) {
    // O número de checks é o que torna o verde informativo. "OK" a seco não
    // diz se foram 3 ou 300, e a diferença interessa.
    //
    // O ÚLTIMO número, não o primeiro: estas suites imprimem "ok" por caso, e
    // o resumo "57 ok" vem no fim. Ler o primeiro contava um subgrupo e
    // publicava um número que não é o total — que é o defeito que o teste
    // `test_total_conta_nomes_e_nao_assuntos` jáTrata no servidor.
    const todos = [...saida.matchAll(/(\d+)\s+(?:ok|checks?|CHECKS?)\b/gi)].map((m) =>
      Number(m[1])
    );
    const total = todos.length ? Math.max(...todos) : null;
    console.log(`ok${total ? ` (${total} checks)` : ''}`);
  } else {
    console.log('FALHOU');
    falhados.push(nome);
    // A saída do que falhou é a parte útil; imprimi-la aqui evita ter de
    // ir correr o ficheiro à mão para perceber porquê.
    const linhas = saida.trim().split(/\r?\n/);
    console.log(
      linhas
        .slice(-14)
        .map((l) => `      ${l}`)
        .join('\n')
    );
    console.log('');
  }
}

console.log('');
if (falhados.length) {
  console.log(`FALHOU: ${falhados.length} de ${lista.length} suites .cjs`);
  console.log(`  ${falhados.join('\n  ')}`);
  process.exit(1);
}
console.log(`OK: ${lista.length} suites .cjs`);
