/* As formas verbais do português nao sao todas "prefixo+mesma vogal".
 *
 *   sugerir  -> eu SUGIRO, tu SUGURES, ele SUGERE,  subj. SUGIRA
 *   preferir -> eu PREFIRO, tu PREFERES, ele PREFERE, subj. PREFIRA
 *
 * O "e" do infinitivo vira "i" na 1a pessoa: sugerir -> sugiro, tal como
 * preferir -> prefiro. Uma alternativa escrita `prefer(?:o|e)` produz
 * "prefere" e NUNCA "prefiro" — e e' por ai que o defeito passa.
 *
 * Este ficheiro diz que forma esta coberta e que nome nao e' apanhado.
 */
'use strict';

const RE =
  /^(escolh(?:a|e|o|er|es)|suger(?:ir|es|e|a)|sugir(?:o|a)|pref[ei]r(?:o|es|e|a|ir)|inventa|surpreende)\b/;

const FORMAS = [
  // escolher
  'escolhe',
  'escolha',
  'escolho',
  'escolhes',
  'escolher',
  'escolha os dois',
  // sugerir
  // sugerir — as formas são sugere/sugiro/sugires? NÃO: "sugeres".
  // A 2ª pessoa de "sugerir" é "sugeres" (do infinitivo), como em
  // "queres". "sugures" e "sugura" não são formas deste verbo e
  // apareceram aqui numa primeira versão deste ficheiro.
  'sugere',
  'sugiro',
  'sugira',
  'sugeres',
  'sugerir',
  'sugere um nome',
  // preferir
  'prefere',
  'prefiro',
  'prefira',
  'preferes',
  'preferir',
  'prefiro outro',
  // núcleo
  'inventa',
  'inventa um nome',
  'surpreende',
  'surpreende-me',
];

/* Nomes e valores do Ampliagro. Qualquer um destes a ser apanhado e' um
 * bug: um funcionario que se chame "Manda" deixa de poder ser registado. */
const NOMES = [
  'Escolhido',
  'Escola',
  'Escolta',
  'Sugestão',
  'Sugerido',
  'Manda',
  'Deixa',
  'Começa',
  'Repete',
  'Acaba',
  'Arranca',
  'Preferido',
  'Vaieta',
  'Invalido',
  'Surpreendente',
  'Ana',
  'Joao Silva',
  'Maria',
  'Ze Carlos',
  'Jose da Silva',
  'Comum',
  'Qualquer',
  'Manuel',
  'Aluminio',
  'Vale',
  'Reparte',
];

/* Nomes que PARECEM verbo e não são. Este é o teste que justifica a
 * âncora no início: `Prefere` é o imperativo de "preferir" e tem de ser
 * apanhado; `Preferido` começa igual e é um particípio, e é um nome
 * plausível. A diferença entre eles é a letra a seguir. */
const FORMA_IGUAL_NOME = [
  ['Prefere', true], // imperativo de "preferir"
  ['Sugere', true], // imperativo de "sugerir"
  ['Escolhe', true], // imperativo de "escolher"
  ['Preferido', false],
  ['Sugerido', false],
  ['Escolhido', false],
];

let f = 0;
console.log('=== formas verbais (tem de apanhar) ===');
for (const v of FORMAS) {
  if (!RE.test(v.toLowerCase())) {
    console.log('  PERDEU  ' + JSON.stringify(v));
    f++;
  }
}
console.log('=== nomes e valores (tem de NAO apanhar) ===');
for (const n of NOMES) {
  if (RE.test(n.toLowerCase())) {
    console.log('  APANHOU  ' + n);
    f++;
  }
}
console.log('=== a mesma raiz, verbo ou particípio? ===');
for (const [palavra, esperada] of FORMA_IGUAL_NOME) {
  const real = RE.test(palavra.toLowerCase());
  if (real !== esperada) {
    console.log(
      '  ' +
        palavra +
        ': esperado ' +
        (esperada ? 'imperativo' : 'NÃO imperativo') +
        ', obtido ' +
        (real ? 'imperativo' : 'não') +
        f +
        ''
    );
    f++;
  }
}

console.log(
  '\n' +
    (f
      ? f + ' problema(s)'
      : 'ok: ' +
        FORMAS.length +
        ' formas, ' +
        NOMES.length +
        ' nomes limpos, ' +
        FORMA_IGUAL_NOME.length +
        ' pares_verbo_nome')
);
process.exit(f ? 1 : 0);
