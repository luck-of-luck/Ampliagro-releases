/* O fio inteiro, do fetch do host ate a mesa na tela.
 *
 * E o teste que teria apanhado o defeito que quase passou: o protocolo antigo
 * dependia de um bloco ``` que o ia-local.js apaga em sanitizarResposta. Nao
 * havia forma de esse protocolo funcionar, e nenhum teste unitario o diria —
 * porque o parsing, sozinho, estava certo. So integrando se descobre que a
 * coisa que chega e diferente da coisa que se esperava. */
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

function el(tag) {
  return {
    tagName: String(tag).toUpperCase(), children: [], attrs: {}, _text: '',
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

/* getElementById tem de PROCURAR. Um mock que devolve sempre null faz o
 * hostEl() criar um contentor novo a cada chamada, e a mesa desenhada num
 * contentor desaparece do ponto de vista de quem a mandou montar — que é
 * exatamente o tipo de falha que só aparece no teste de integração. */
function porId(id) {
  for (const raiz of [document.head, document.body]) {
    for (const filho of raiz.children) {
      if (filho.id === id) return filho;
    }
  }
  return null;
}

global.window = {};
global.document = {
  cookie: '',
  head: el('head'),
  body: el('body'),
  createElement: el,
  getElementById: porId,
  dispatchEvent: () => {},
};
global.CustomEvent = function CustomEvent(nome, init) { this.type = nome; this.detail = init && init.detail; };

/* O fetch do HOST, como o ia-local.js o usaria. */
const chamadas = [];
global.fetch = function (url) {
  chamadas.push(url);
  return Promise.resolve({
    url: String(url),
    ok: true,
    headers: { get: () => null, set: () => {} },
    clone() { return { json: () => Promise.resolve(ultimoCorpo) }; },
  });
};
window.fetch = global.fetch;

let ultimoCorpo = {};
eval(fs.readFileSync(SRC, 'utf8'));
const P = window.AmpliaPalco;

function responder(corpo) {
  ultimoCorpo = corpo;
  return window.fetch('/api/amplia/exec/', { method: 'POST', body: '{}' });
}

const MESA = {
  ok: true,
  resposta: 'Mesa montada no preset Amplia: kpi-custo.',
  dados: {
    palco: 'amplia',
    widgets: [{ tipo: 'kpi-custo', titulo: 'Custo por hectare', config: { custo_total: 12500 } }],
    layout: 'grid-mixed',
    assinatura: 'custodotalhao2',
    intent: 'custo do talhao 2',
    descartados: ['desconhecido:nao-existe'],
  },
};

(async function principal() {
  console.log('\n== o embrulho esta no sitio ==');
  t('o fetch do host foi embrulhado', window.fetch.__ampliaPalcoFetch === true);
  const antes = window.fetch;
  P.espiaExec();
  t('re-embrulhar nao cria outro embrulho', window.fetch === antes);

  console.log('\n== o sandbox responde, e a mesa aparece ==');
  await responder(MESA);
  await new Promise((r) => setTimeout(r, 0));
  const d = P.ultimoDados();
  t('o palco reconheceu a propria execucao', !!d && d.palco === 'amplia');
  const host = P.hostEl();
  t('a mesa foi desenhada', host.children.length >= 2);
  const card = host.children[0].children[0];
  t('o card e do widget pedido', card.attrs['data-tipo'] === 'kpi-custo');
  t('o titulo veio do servidor', card.children[0]._text === 'Custo por hectare');
  t('os dados foram pintados', card.children[1].children.length === 1);
  t('a assinatura ficou no estado', P.estado.assinatura === 'custodotalhao2');
  t('os descartados chegaram ao cliente', P.ultimoDados().descartados.length === 1);

  console.log('\n== uma resposta que NAO e do palco passa intacta ==');
  document.body.children = [];
  await responder({ ok: true, resposta: 'ok', dados: { intents: ['clima_agora'] } });
  await new Promise((r) => setTimeout(r, 0));
  t('nao desenhou nada', document.body.children.length === 0);
  t('e o ultimo dado continua o do palco', P.ultimoDados().palco === 'amplia');

  console.log('\n== uma falha do sandbox nao monta nada ==');
  document.body.children = [];
  await responder({ ok: false, erro: 'nenhum widget reconhecido' });
  await new Promise((r) => setTimeout(r, 0));
  t('falha nao desenha mesa', document.body.children.length === 0);

  console.log('\n== a promessa do host nunca e estragada pelo espiao ==');
  t('o embrulho devolve uma promessa', typeof window.fetch('/api/amplia/tools/').then === 'function');
  const antes2 = chamadas.length;
  await window.fetch('/api/amplia/tools/');
  t('o spy so observa, nao bloqueia', chamadas.length === antes2 + 1);

  console.log('\n== as duas vias podem disparar no mesmo turno ==');
  /* O ia-local.js intercepta o bloco markdown como fallback, e este módulo
   * espia o sandbox. Numa ronda em que o modelo faz as DUAS coisas — ou em
   * que o fallback e a tool disparam juntos — a mesa pode ser montada duas
   * vezes.
   *
   * Duplicar a mesa é pior do que não montar: o produtor passa a ler o mesmo
   * número duas vezes e conclui que a IA alucina. Num produto que promete
   * confiança nos números, é o pior defeito possível. */
  await responder(MESA);
  await new Promise((r) => setTimeout(r, 0));
  const grelha1 = P.hostEl().children[0].children.length;

  P.montarDoServidor(MESA.dados);
  const grelha2 = P.hostEl().children[0].children.length;
  t('montar duas vezes NAO duplica widgets', grelha1 === grelha2 && grelha2 === 1,
    '(1a: ' + grelha1 + ', 2a: ' + grelha2 + ')');
  t('o contentor nao acumula filhos', P.hostEl().children.length === 2,
    '(' + P.hostEl().children.length + ' filhos)');

  /* O Like sobrevive ao remount porque vive no ESTADO, não no DOM. Se
   * dependesse do ecrã, o botão de avaliar deixaria de funcionar à segunda
   * montagem — e o produtor perderia a forma de ensinar a IA. */
  t('a assinatura continua depois do remount', P.estado.assinatura === 'custodotalhao2');

  await responder({
    ok: true,
    dados: {
      palco: 'amplia',
      widgets: [{ tipo: 'kpi-clima', titulo: 'Chuva' }],
      layout: 'grid-mixed',
      assinatura: 'x',
      intent: 'y',
    },
  });
  await new Promise((r) => setTimeout(r, 0));
  t('uma mesa nova substitui a antiga, nao acumula',
    P.hostEl().children[0].children.length === 1
    && P.hostEl().children[0].children[0].attrs['data-tipo'] === 'kpi-clima');

  console.log('\n' + (falhas ? 'FALHOU: ' + ok + ' ok, ' + falhas + ' falha(s)' : 'OK: ' + ok + ' ok, 0 falha(s)'));
  process.exit(falhas ? 1 : 0);
})();
