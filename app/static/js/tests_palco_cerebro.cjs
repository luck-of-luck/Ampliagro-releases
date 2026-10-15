/* O que o modelo precisa de saber, e o que ele NAO precisa.
 *
 * Este ficheiro cobre o defeito que o produtor reportou: "a IA não desenvolve
 * os widgets". A causa não era o modelo ser burro — era ninguém lhe dizer
 * que isto existia. O prompt do sistema lista as tools à mão, e o palco não
 * estava na lista; e nenhuma chamada ao modelo passa `tools:` ao motor, porque
 * o catálogo é cacheado e nunca usado numa inferência.
 *
 * Se esta triagem quebrar, o sintoma volta a ser exactamente o mesmo: o chat
 * funciona, a IA responde bem, e nenhum widget aparece. */
'use strict';

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'ia-local', 'palco-amplia.js');

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

function el(tag) {
  return {
    tagName: String(tag).toUpperCase(),
    children: [],
    attrs: {},
    _text: '',
    set textContent(v) {
      this._text = v;
      this.children = [];
    },
    get textContent() {
      return this._text;
    },
    set className(v) {
      this.attrs.class = v;
    },
    get className() {
      return this.attrs.class || '';
    },
    set id(v) {
      this.attrs.id = v;
    },
    get id() {
      return this.attrs.id || '';
    },
    setAttribute(k, v) {
      this.attrs[k] = v;
    },
    getAttribute(k) {
      return this.attrs[k];
    },
    appendChild(c) {
      this.children.push(c);
      return c;
    },
    addEventListener() {},
  };
}

global.window = {};
global.document = {
  cookie: '',
  head: el('head'),
  body: el('body'),
  createElement: el,
  getElementById: () => null,
  dispatchEvent: () => {},
};
global.CustomEvent = function CustomEvent(n, i) {
  this.type = n;
  this.detail = i && i.detail;
};
global.fetch = function () {
  return Promise.resolve({
    url: '',
    clone: function () {
      return { json: () => Promise.resolve({}) };
    },
  });
};
window.fetch = global.fetch;

/* O motor, como o ia-local.js o expoe: `window.__ampliaIa.engine()`. */
let pedidos = [];
const completions = {
  create: function (p) {
    pedidos.push(p);
    return Promise.resolve({ choices: [{ message: { content: '' } }] });
  },
};
const MOTOR = { chat: { completions: completions } };
window.__ampliaIa = {
  engine: function () {
    return MOTOR;
  },
};

/* O registo de presets, como o dashboard o expoe. */
const PRESETAS_BASE = [{ id: 'visao-geral', name: 'Visão Geral' }];
window.WidgetIntelligence = {
  getPresets: function () {
    return PRESETAS_BASE.slice();
  },
};

eval(fs.readFileSync(SRC, 'utf8'));
const P = window.AmpliaPalco;

console.log('\n== a triagem: quando a pergunta pede uma ISTA ==');
[
  ['custo do talhao 2 neste mes', true],
  ['como evoluiu a producao', true],
  ['compare as safras 2024 e 2025', true],
  ['historico do talhao 2', true],
  ['faz um resumo financeiro consolidado', true],
  ['quanto rende a soja este ano', true],
  ['mostra o grafico de custos', true],
].forEach(([q, esperado]) => {
  t('"' + q + '" -> ' + (esperado ? 'mesa' : 'sem mesa'), P.querMesa(q) === esperado);
});

console.log('\n== a triagem: quando NAO se monta mesa ==');
[
  ['vai chover amanha', false],
  ['chove hoje', false],
  ['temperatura agora', false],
  ['clima agora', false],
  ['quem e o dono do talhao 3', false],
  ['', false],
].forEach(([q, esperado]) => {
  t('"' + q + '" -> ' + (esperado ? 'mesa' : 'sem mesa'), P.querMesa(q) === esperado);
});

console.log('\n== o proprio prompt lembra: previsao JAMAIS e mesa ==');
t(
  '"vai chover, faz um grafico" NAO monta mesa',
  P.querMesa('vai chover, faz um grafico') === false,
  'a previsao e' + ' o pior sitio para desperdic' + 'ar confianca'
);

console.log('\n== a instrucao que o modelo vai ler ==');
const bloco = P.blocoInstrucao();
t('ensina o formato do bloco', bloco.indexOf('```amplia') !== -1);
t('ensina a escrever tipo | titulo', /tipo-do-widget \| Titulo/.test(bloco));
t(
  'diz para NAO montar mesa em sim/nao',
  /NAO use\s*\n?.*sim\/n/i.test(bloco) || /NAO monte mesa/.test(bloco)
);
t('leva a lista de widgets', bloco.indexOf('kpi-custo') !== -1);
t(
  'e curta de proposito (o motor tem 4096 tokens)',
  bloco.length < 1200,
  '(' + bloco.length + ' chars)'
);

console.log('\n== o motor recebe a instrucao ==');
async function responde(pergunta) {
  pedidos = [];
  await MOTOR.chat.completions.create({
    messages: [
      { role: 'system', content: 'Voce e a AmplIA.' },
      { role: 'user', content: pergunta },
    ],
    max_tokens: 256,
    stream: true,
  });
  return pedidos[pedidos.length - 1];
}

(async function () {
  const analitica = await responde('custo do talhao 2 neste mes');
  const sys = analitica.messages[0].content;
  t('o prompt do sistema foi acrescido, nao substituido', sys.indexOf('Voce e a AmplIA.') === 0);
  t('e a instrucao da mesa esta la', sys.indexOf('MESA DE OPERACAO') !== -1);
  t('e a tool vai anexada', Array.isArray(analitica.tools) && analitica.tools.length === 1);
  t('a tool e a do palco', analitica.tools[0].function.name === 'amplia_render_preset');
  t(
    'os outros parametros ficam intactos',
    analitica.max_tokens === 256 && analitica.stream === true
  );

  const factual = await responde('vai chover amanha');
  t(
    'numa pergunta factual NAO ha instrucao',
    factual.messages[0].content.indexOf('MESA DE OPERACAO') === -1
  );
  t('nem tool anexada', factual.tools === undefined);

  console.log('\n== o motor so e embrulhado uma vez ==');
  const antes = MOTOR.chat.completions.create;
  P.ligaMotor();
  t('re-embrulhar nao cria outro embrulho', MOTOR.chat.completions.create === antes);

  console.log('\n== o preset Amplia aparece no menu ==');
  const lista = window.WidgetIntelligence.getPresets();
  t(
    'esta na lista',
    lista.some((p) => p.id === 'amplia')
  );
  t('e o primeiro, antes dos outros', lista[0].id === 'amplia');
  t(
    'os outros presets continuam la',
    lista.some((p) => p.id === 'visao-geral')
  );
  t('e marcado como fluido', lista[0].fluida === true);
  t(
    'nao duplica se registar outra vez',
    window.WidgetIntelligence.getPresets().length === lista.length
  );

  console.log('\n== a mesa vai para o painel, nao para o body solto ==');
  const painel = el('section');
  painel.setAttribute('id', 'content');
  global.document.getElementById = (id) => (id === 'content' ? painel : null);
  P.desenhaMesa([{ tipo: 'kpi-custo', titulo: 'Custo' }]);
  t('o palco foi montado dentro de #content', painel.children.length === 1);

  console.log('\n== o botão Editar: desligado por padrão ==');
  t(
    'a edição começa desligada',
    P.edicaoLigada() === false,
    'com a tool anexada, a IA poderia mexer em preset sem o produtor pedir'
  );
  t(
    'com edição desligada, nenhum comando de edição abre caminho',
    P.querEdicao('tira o gráfico de chuva') === false
  );
  t(
    'nem "move", nem "aumenta", nem "apaga"',
    P.querEdicao('move o gráfico') === false &&
      P.querEdicao('aumenta o KPI de custo') === false &&
      P.querEdicao('apaga a tabela') === false
  );

  console.log('\n== com o produtor ligando o botão ==');
  P.edicaoLigada(true);
  t('agora a edição está ligada', P.edicaoLigada() === true);
  [
    'tira o gráfico de chuva',
    'remove a tabela',
    'apaga o KPI',
    'aumenta o KPI de custo',
    'move o gráfico de safras',
    'redimensiona o card',
    'adiciona o KPI de ROI',
  ].forEach((q) => {
    t('"' + q + '" vira edição', P.querEdicao(q) === true);
  });

  console.log('\n== pergunta de número NUNCA vira edição ==');
  /* render_preset e' o caminho da pergunta analitica. Um verbo de edicao nao
   * pode capturar uma pergunta que so quer saber um numero. */
  t(
    '"mostra a evolucao da producao" nao e' + ' edicao',
    P.querEdicao('mostra a evolucao da producao') === false
  );
  t(
    '"custo do talhao 2 neste mes" nao e' + ' edicao',
    P.querEdicao('custo do talhao 2 neste mes') === false
  );
  t(
    '"como evoluiu a producao" nao e' + ' edicao',
    P.querEdicao('como evoluiu a producao') === false
  );

  console.log('\n== verbo de edição VENCE o gatilho de render ==');
  /* Este ponto ja falhou. "tira o grafico de chuva" contem "grafico", que e'
   * gatilho de render — e a versao que checava querMesa primeiro devolvia
   * false, entao a IA MONTAVA UMA MESA NOVA quando o produtor tinha pedido
   * para TIRAR um widget. Ligar o botao e' o produtor dizendo o que quer;
   * o render nao tem o direito de vetar. */
  t(
    '"tira o grafico de chuva" e' + ' edicao, mesmo com "grafico" no texto',
    P.querEdicao('tira o grafico de chuva') === true
  );
  t(
    '"adiciona um grafico de custo" e' + ' edicao com o botao ligado',
    P.querEdicao('adiciona um grafico de custo') === true
  );

  console.log('\n== a edicao nao come o orcamento do render ==');
  /* O motor roda com 4096 de contexto e o bloco do render tem teto. Se a
   * edicao fosse anexada sempre, a instrucao que o produtor ja tinha seria
   * espremida. Por isso o bloco de edicao e' separado. */
  const blocoEd = P.blocoInstrucaoEdicao();
  t(
    'o bloco de edicao existe e explica as 4 operacoes',
    /add/.test(blocoEd) && /remove/.test(blocoEd) && /move/.test(blocoEd) && /resize/.test(blocoEd)
  );
  t(
    'o bloco de edicao nao e' + ' o bloco de render',
    blocoEd.indexOf('EDITAR UMA MESA') !== -1 && blocoEd.indexOf('MESA DE OPERACAO') === -1
  );
  t(
    'a tool de edicao se chama amplia_editar_preset',
    P.schemaDaToolEdicao().function.name === 'amplia_editar_preset'
  );
  t(
    'a tool de edicao e' + ' distinta da de render',
    P.schemaDaToolEdicao().function.name !== P.schemaDaTool().function.name
  );

  console.log(
    '\n' +
      (falhas ? 'FALHOU: ' + ok + ' ok, ' + falhas + ' falha(s)' : 'OK: ' + ok + ' ok, 0 falha(s)')
  );
  process.exit(falhas ? 1 : 0);
})();
