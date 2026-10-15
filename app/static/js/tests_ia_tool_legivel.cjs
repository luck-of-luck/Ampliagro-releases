/* O NOME DA FERRAMENTA NAO E LINGUAGEM DE PRODUTOR.
 *
 * Uma auditoria de interface acusou "a resposta expoe a logica interna do
 * sistema (a chamada da funcao) directamente no frontend". A substancia estava
 * certa; a letra, nao: `amplia_criar_preset` nao existe em lado nenhum do
 * repositorio. A tool real e `amplia_render_preset` (intents.py).
 *
 * Mas o defeito EXISTIA, noutro sitio, e era real: quatro fallbacks de erro em
 * `ia-local.js` devolviam ao produtor o identificador da tool e, num deles, ate
 * 400 caracteres de erro cru do browser:
 *
 *   `Ferramenta ${call.tool} executada.`   <- o nome da maquina como resposta
 *   `Erro ao executar ${tool}: ${msg...}`  <- + endpoint/SQL/stack na tela
 *   `Nao consegui executar ${call.tool}.`
 *   `Erro ao executar ${call.tool}: ${...}`
 *
 * Nenhum teste os cobria. Porquê? Porque o resto do caminho esta CORRETO: o
 * sandbox devolve `r.resposta` em portugues ja pronta para o produtor, e o
 * comentario ao lado diz isso mesmo ("nao reescrevemos nada"). Os fallbacks so
 * apareciam quando a resposta vinha VAZIA — e uma resposta vazia e, por
 * definicao, o caminho que nao tem teste. O defeito morava exactamente no
 * buraco da cobertura.
 *
 * Este teste e a rede debaixo desse buraco. Tal como `tests_fallback_sem_
 * invencao.py` faz com `inspect.getsource`, ele le o FICHEIRO: `ia-local.js`
 * tem 5755 linhas e vive dentro de um IIFE, nao exporta `toolCallGovernada`, e
 * importa-lo custaria o proprio `ia-local.js` inteiro por causa dos efeitos
 * de topo. Ler a fonte e o honesto, nao o preguiçoso.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'ia-local', 'ia-local.js');
/* `ia-local.js` esta em CRLF (5755 de 5755), e um `\n}` puro nao existe num
 * ficheiro CRLF. Sem esta normalizacao o teste corria verde sobre assertions de
 * substring e vermelho sobre as de linha — o pior dos dois: parece que cobre
 * quando cobre metade. A mesma atencao a encoding que `tests_proativo.cjs`
 * ja exige ("nao ha lixo de encoding"). */
const fonte = fs.readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n');

let ok = 0;
let falhas = 0;
function t(nome, cond) {
  if (cond) {
    ok++;
    console.log('  ok   ' + nome);
  } else {
    falhas++;
    console.log('  FAIL ' + nome);
  }
}

/* Corta a funcao `toolCallGovernada`: do `async function` ate a linha `}` que
 * fecha a coluna zero. */
function corpoDa(nome) {
  const i = fonte.indexOf(nome);
  if (i < 0) return '';
  const j = fonte.indexOf('\n}\n', i);
  return j < 0 ? '' : fonte.slice(i, j);
}

const governada = corpoDa('async function toolCallGovernada');

/* As expressoes que o produtor recebia. `nome` e o identificador normalizado
 * da tool (`amplia_render_preset`); `call.tool` e o que o modelo escreveu. */
const VAZAM = ['${call.tool}', '${tool}', '${nome}'];

/* Todo o retorno da funcao, um por linha. Um `return` que carregue uma
 * expressao de tool e um texto de maquina a caminho da tela. */
function retornos(corpo) {
  return corpo
    .split('\n')
    .filter((l) => /^\s*return\b/.test(l))
    .join('\n');
}

console.log('== a funcao existe ==');
t('toolCallGovernada esta no ficheiro', governada.length > 0);

console.log('\n== nenhum return entrega o nome da tool ==');
const retornosGovernada = retornos(governada);
for (const expr of VAZAM) {
  t('sem ' + expr + ' no que o produtor le', !retornosGovernada.includes(expr));
}

console.log('\n== as quatro frases que vazavam foram removidas ==');
const VAZADAS = [
  'Ferramenta ${call.tool} executada.',
  'Erro ao executar ${tool}: ${msg.slice(0, 400)}',
  'Nao consegui executar ${call.tool}.',
  'Erro ao executar ${call.tool}:',
];
for (const frase of VAZADAS) {
  t('saiu: ' + frase, !fonte.includes(frase));
}

console.log('\n== o produtor recebe Portuguese, nao sintaxe ==');
t(
  'a tool que correu e calou-se devolve confirmacao semantica',
  governada.includes("return 'Pronto.';")
);
t(
  'ha um caminho que explica que o servidor nao respondeu',
  /nao consegui falar com o servidor|N[aã]o consegui falar com o servidor/i.test(governada)
);

console.log('\n== "Pronto" nunca e mentira ==');
/* O ponto que vale mais que todos: quando o sandbox devolve ok=false SEM
 * texto, o pedido NAO foi atendido. Dizer "Pronto." ali seria afirmar ao
 * produtor que a acao foi feita quando nao foi — e num ERP ele decide
 * confiar no que le. A guarda tem de vir ANTES do "Pronto.". */
const iOk = governada.indexOf('r.ok === false');
const iPronto = governada.lastIndexOf("return 'Pronto.';");
t('a guarda ok=false existe', iOk > -1);
t('"Pronto." ainda existe', iPronto > -1);
t('a guarda vem ANTES do "Pronto."', iOk > -1 && iPronto > -1 && iOk < iPronto);
t(
  'quando ok=false o produtor nao lede "Pronto."',
  /if \(r\.ok === false\) return '[^']*'/.test(governada)
);

console.log('\n== o detalhe tecnico NAO se perdeu: foi para o console ==');
/* Apagar a mensagem da tela nao pode ser deitar a informacao fora. O
 * sintoma tem de continuar diagnosticavel por quem opera. */
t(
  'o detalhe da tool governada vai para o console',
  /console\.warn\(\[?['"]\[IA\] tool governada falhou/.test(governada)
);
t(
  'o erro cru do executor antigo vai para o console',
  fonte.includes("console.warn('tool exec falhou:'")
);
t('e o identificador continua registado no log', /console\.warn\([^)]*\bnome\b/.test(governada));

console.log('\n== o caminho feliz nao foi estragado ==');
/* Uma correcao que estraga o caminho feliz e pior que o defeito. A resposta
 * do sandbox tem de continuar a passar, intacta e em portugues. */
t(
  'a resposta do sandbox continua a ser preferida',
  /sanitizarResposta\(textoResposta\)/.test(governada)
);
t('e so quando ela e vazia e que ha fallback', /if \(texto\) return texto;/.test(governada));
t(
  'o comentario do sandbox — "nao reescrevemos nada" — ainda vale',
  fonte.includes('nao reescrevemos nada')
);

console.log('\n' + (falhas ? 'FALHOU' : 'OK') + ': ' + ok + ' ok, ' + falhas + ' falha(s)');
process.exit(falhas ? 1 : 0);
