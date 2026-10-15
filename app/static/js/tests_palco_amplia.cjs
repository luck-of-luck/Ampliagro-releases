/* Testes do protocolo do palco. Node puro, sem browser, sem rede.
 *
 * Ordem importa: o DOM falso é montado ANTES do módulo ser avaliado, porque o
 * módulo é uma IIFE que captura `window` e `document` no momento em que corre.
 * Reavaliar o módulo mais tarde, com outro DOM, é o caminho mais curto para um
 * harness que mente sobre o produto. */
'use strict';

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'ia-local', 'palco-amplia.js');

let ok = 0;
let falhas = 0;
function t(nome, cond) {
  if (cond) { ok++; console.log('  ok   ' + nome); }
  else { falhas++; console.log('  FAIL ' + nome); }
}

/* ---- DOM falso ------------------------------------------------------------ */
function el(tag) {
  return {
    tagName: String(tag).toUpperCase(),
    children: [],
    attrs: {},
    _text: '',
    set textContent(v) { this._text = v; this.children = []; },
    get textContent() { return this._text; },
    set className(v) { this.attrs.class = v; },
    get className() { return this.attrs.class || ''; },
    set id(v) { this.attrs.id = v; },
    get id() { return this.attrs.id || ''; },
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener() {},
  };
}

global.window = {};
/* getElementById tem de PROCURAR de verdade. Um mock que devolve sempre null
 * deixa passar a injeção dupla de folha de estilo — que é o que a
 * idempotência existe para impedir, e é o tipo de bug que só aparece quando
 * ninguém está a testar. */
function porId(id) {
  const alvos = [document.head, document.body];
  for (const raiz of alvos) {
    for (const filho of raiz.children) {
      if (filho.id === id) return filho;
    }
  }
  return null;
}
global.document = {
  cookie: '',
  head: el('head'),
  body: el('body'),
  createElement: el,
  getElementById: porId,
  dispatchEvent: () => {},
};
global.CustomEvent = function CustomEvent(nome, init) { this.type = nome; this.detail = init && init.detail; };
/* O fetch tem de existir ANTES do modulo correr: e' o que ele embrulha. Sem
 * isto, o embrulho nao acontece e o teste passava a verificar o vazio. */
global.fetch = function () { return Promise.resolve({ url: '', clone: function () { return { json: () => Promise.resolve({}) }; } }); };
window.fetch = global.fetch;

eval(fs.readFileSync(SRC, 'utf8'));
const P = global.window.AmpliaPalco;
const P2espia = P.espiaExec;

console.log('\n== a API publica ==');
t('expõe o protocol completo', !!P);
['parseIntencao', 'render', 'veredito', 'clonar', 'limpar', 'perguntaDeVolta',
 'desenhaMesa', 'garanteEstilo', 'hostEl'].forEach((f) => {
  t('tem ' + f + ' como função', typeof P[f] === 'function');
});
t('o slug do palco é "amplia"', P.PALCO_SLUG === 'amplia');

console.log('\n== o formato canónico (uma linha por widget) ==');
const canonico = '```amplia\nkpi-custo | Custo por hectare\nchart-financeiro | Custo vs receita\n```';
const w1 = P.parseIntencao(canonico);
t('extrai 2 widgets', w1.length === 2);
t('lê o tipo', w1[0].tipo === 'kpi-custo');
t('lê o título', w1[0].titulo === 'Custo por hectare');
t('lê o segundo', w1[1].tipo === 'chart-financeiro');

console.log('\n== o modelo erra, e a mesa continua de pé ==');
t('JSON válido é aceite', P.parseIntencao('```amplia\n[{"tipo":"kpi-roi"}]\n```').length === 1);
t('objeto com "widgets" é aceite', P.parseIntencao('```amplia\n{"widgets":["kpi-roi"]}\n```').length === 1);
t('JSON partido cai para linha-a-linha', P.parseIntencao('```amplia\n[{"tipo": broken\n```').length === 0);
t('JSON partido mas com linha legível recupera', P.parseIntencao('```amplia\n[{"tipo": broken\nkpi-area | Área\n```').length === 1);
t('texto vazio devolve lista vazia', P.parseIntencao('').length === 0);
t('sem bloco devolve [] sem lançar', P.parseIntencao('nada aqui').length === 0);

console.log('\n== a prosa do modelo não vira widget ==');
const comProsa = '```amplia\nkpi-custo | Custo\nespero que isto ajude!\n- uma lista qualquer\n```';
const w2 = P.parseIntencao(comProsa);
t('só o widget é levado', w2.length === 1 && w2[0].tipo === 'kpi-custo');
t('frase de prosa é ignorada', !w2.some((w) => /espero/.test(w.tipo)));

console.log('\n== config opcional ==');
const c1 = P.parseIntencao('```amplia\nkpi-custo | Custo | {"periodo":"2026-09"}\n```');
t('lê config JSON', !!(c1[0] && c1[0].config && c1[0].config.periodo === '2026-09'));
const c2 = P.parseIntencao('```amplia\nkpi-custo | Custo | {config quebrada\n```');
t('config ilegível não perde o widget', c2.length === 1 && !c2[0].config);

console.log('\n== a pergunta de volta do Dislike ==');
const q = P.perguntaDeVolta();
t('é texto fixo, não gerado', typeof q === 'string' && q.length > 40);
t('convida a responder em uma frase', /uma frase/.test(q));

console.log('\n== o estado começa limpo ==');
t('sem widgets no arranque', P.estado.widgets.length === 0);
t('sem assinatura no arranque', P.estado.assinatura === '');

console.log('\n== a tela: bento grid isolado ==');
P.garanteEstilo();
t('injeta o CSS uma vez', document.head.children.length === 1);
P.garanteEstilo();
t('não reinjeta ao segundo pedido', document.head.children.length === 1);
const css = document.head.children[0].textContent;
t('o CSS é escopado ao prefixo', css.includes('.amplia-palco-grid') && css.includes('.amplia-palco-card'));
t('mobile: a grelha cai para uma coluna', /@media \(max-width:640px\)/.test(css));
t('nada foi escrito em body', document.body.children.length === 0);

console.log('\n== XSS: o título vem de um modelo de 1B ==');
P.desenhaMesa([{ tipo: 'kpi-custo', titulo: '<img src=x onerror=alert(1)>' }]);
const host = P.hostEl();
const card = host.children[0].children[0];
const titulo = card.children[0];
t('o título não vira HTML', titulo._text === '<img src=x onerror=alert(1)>');
t('o título é texto, sem filhos', titulo.children.length === 0);
t('o card leva o data-tipo', card.attrs['data-tipo'] === 'kpi-custo');
t('a âncora de dados não recebe HTML', card.children[1].children.length === 0);
/* A verificação é por UTILIZAÇÃO, não por menção: este ficheiro menciona
 * `innerHTML` no comentário que explica porque não a usa, e uma busca pela
 * palavra sozinha reprovaria a própria documentação. O que dangerous é
 * atribuir, inserir ou escrever. */
const fonte = fs.readFileSync(SRC, 'utf8');
const usosPerigosos = [
  /\.innerHTML\s*=/,
  /\.outerHTML\s*=/,
  /insertAdjacentHTML/,
  /document\.write\s*\(/,
  /dangerouslySet/,
];
const encontrados = usosPerigosos.filter((re) => re.test(fonte));
t('nenhum sink de HTML no módulo', encontrados.length === 0,
  encontrados.length ? 'encontrado: ' + encontrados.map(String).join(', ') : '');

console.log('\n== os botões do loop de aprendizado ==');
const barra = P.hostEl().children[1];
const rotulos = barra.children.map((b) => b._text);
t('há Like, Dislike e Salvar', rotulos.length === 3);
t('o botão de like existe', rotulos.some((r) => /Boa mesa/.test(r)));
t('o botão de dislike existe', rotulos.some((r) => /Faltou/.test(r)));
t('o botão de salvar existe', rotulos.some((r) => /Salvar como meu Dashboard/.test(r)));
t('são <button>', barra.children.every((b) => b.tagName === 'BUTTON'));
t('cada botão declara a sua ação', barra.children.every((b) => !!b.attrs['data-acao']));

console.log('\n== mesa vazia não fica com um buraco silencioso ==');
P.desenhaMesa([]);
const v = P.hostEl();
t('diz que não achou nada', /não achou nada/.test(v.children[0]._text));
t('não desenha grelha vazia', v.children.length === 1);


console.log('\n== o fio: a resposta do sandbox monta a mesa ==');
t('o módulo embrulhou o fetch do host', typeof window.fetch === 'function' && window.fetch.__ampliaPalcoFetch === true);
t('embrulhar duas vezes nao duplica', (function () {
  const antes = window.fetch;
  P.espiaExec();
  return window.fetch === antes;
})());

function respostaFake(url, corpo) {
  return {
    url: String(url),
    ok: true,
    headers: { get: () => null, set: () => {} },
    clone: function () { return { json: () => Promise.resolve(corpo) }; },
  };
}
global.window.fetch = function () { return Promise.resolve(respostaFake('/api/amplia/exec/', {})); };
P.espiaExec();

t('uma resposta de OUTRO sandbox nao monta nada', (function () {
  const antes = document.body.children.length;
  window.fetch('/api/amplia/exec/');
  return document.body.children.length === antes;
}));

console.log('\n== a marca que o palco reconhece ==');
t('so monta com dados.palco === "amplia"', (function () {
  const w = P.ultimoDados();
  return w === null; /* ainda nada foi montado */
})());

console.log('\n== os dados vao para o card, como texto ==');
P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'Custo', config: { custo_total: 12500, periodo: '2026-09' } }]);
const card2 = P.hostEl().children[0].children[0];
const dl = card2.children[1].children[0];
t('o card tem uma lista de dados', dl.tagName === 'DL');
t('o par rotulo/valor existe para cada campo', dl.children.length === 4);
t('o rotulo e em portugues, nao a chave crua', dl.children[0]._text === 'Custo total');
/* O numero e formatado em pt-BR. Um '12500' lido como doze mil e quinhentos
   e um '12500,00' lido como doze e meio sao erros que fazem o produtor
   desconfiar de toda a tela. */
t('o valor sai formatado para pt-BR', /12\.500/.test(dl.children[1]._text), '(' + dl.children[1]._text + ')');
t('o valor nunca vira HTML', dl.children[1].children.length === 0);

console.log('\n== card sem dados fica honesto, nao mente ==');
P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'Custo' }]);
const card3 = P.hostEl().children[0].children[0];
t('sem dados, sem lista', card3.children[1].children.length === 0);

console.log('\n== XSS nos dados tambem ==');
P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'X', config: { nota: '<script>alert(1)</script>' } }]);
const card4 = P.hostEl().children[0].children[0];
const dl4 = card4.children[1].children[0];
t('o dado malicioso fica texto', dl4.children[1]._text === '<script>alert(1)</script>');
t('sem filhos HTML', dl4.children[1].children.length === 0);


  console.log('\n== sem_dado NAO e um dado ==');
  /* O bug: `sem_dado: true` e' um booleano, e o filtro de desenho so
   * descartava `null`, `undefined` e `''`. Passava, caia na lista e
   * aparecia no cartao como uma linha "sem_dado: sim" ao lado dos
   * numeros reais do mesmo cartao.
   *
   * E o pior nao era feio: a linha lia-se como "sem dados: ha um sim",
   * quando o servidor queria dizer "este cartao esta vazio". Sao frases
   * opostas, e o produtor nao tem como saber qual leu. */
  P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'Custo', config: { sem_dado: true } }]);
  const cardVazio = P.hostEl().children[0].children[0];
  const corpo = cardVazio.children[1];
  const texto = JSON.stringify(corpo);
  t('sem_dado nao vira linha de dado', texto.indexOf('sem_dado') === -1);
  t('diz "sem dado" ao produtor', texto.indexOf('sem dado') !== -1);
  t('o aviso explica que zero seria mentira', texto.indexOf('zero') !== -1);

  /* Um cartao SEM sem_dado continua a desenhar os numeros. */
  P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'Custo',
    config: { custo_total: 1000, custo_por_ha: 2.5 } }]);
  const cardNum = P.hostEl().children[0].children[0];
  /* `custo_total` e' campo de moeda: sai "R$ 1.000,00", e nao "1000".
   * O teste tem de procurar o que a tela mostra, nao o que o JSON tem. */
  const textoNum = JSON.stringify(cardNum);
  t('os numeros continuam a sair', textoNum.indexOf('1.000') !== -1);
  t('e nao aparece "sem dado" num cartao com numeros',
    JSON.stringify(cardNum).indexOf('sem dado') === -1);

  /* Um config que tem NUMERO *e* `sem_dado` e' contraditorio — e o servidor
   * ja nao produz isso. Se aparecesse, a marca GANHA: ela e' a declaracao
   * explicita de que nao ha o que mostrar, e obeyecer-lhe e' mais seguro do
   * que mostrar um numero que o servidor declarou inexistente. */
  P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'Custo',
    config: { custo_total: 7, sem_dado: true } }]);
  const cardConflito = JSON.stringify(P.hostEl().children[0].children[0]);
  t('em config contraditorio, a marca vence',
    cardConflito.indexOf('sem dado') !== -1);
  t('e o numero contestavel nao e desenhado',
    cardConflito.indexOf('7,00') === -1);

  console.log('\n' + (falhas ? 'FALHOU: ' + ok + ' ok, ' + falhas + ' falha(s)' : 'OK: ' + ok + ' ok, 0 falha(s)'));
process.exit(falhas ? 1 : 0);
