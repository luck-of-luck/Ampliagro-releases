/* O Chamado Amplia desenhado na widget-bar.
 *
 * ============================================================================
 * O QUE ESTES TESTES PROVAM
 * ============================================================================
 * 1. A PROVENIÊNCIA CHEGA AO ECRÃ. Um bloco `sem_dado` escreve a marca e
 *    NUNCA `0`. Esta é a diferença entre "a despesa foi zero" e "nunca foi
 *    registada nenhuma" — e é a diferença entre uma tela que ajuda e uma tela
 *    de que o produtor decide uma safra em cima de nada.
 * 2. O AVISO SAI EM PORTUGUÊS, com os números concretos. Um aviso que não diz
 *    *quais* números não ajuda ninguém a decidir se acredita ou não.
 * 3. ARQUIVADO SOME COM O BOTÃO DE EDITAR. Um botão que está lá e não faz nada
 *    é pior do que um botão que não existe.
 * 4. **NUNCA `innerHTML`.** Título, texto e célula vêm de um modelo de 1,7B a
 *    responder a um produtor. Injetar isso como HTML é XSS com atraso, e um
 *    teste que o verifique custa três linhas e fecha a porta à recaída.
 * ============================================================================ */
'use strict';

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'ia-local', 'chamado-amplia.js');
const FONTE = fs.readFileSync(SRC, 'utf8');

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

/* ---------------------------------------------------------------------------
   UM DOM PEQUENO, O SUFICIENTE
   ---------------------------------------------------------------------------
   Não é um jsdom. Um DOM de mentira que guarde texto, atributos e filhos chega
   para o que este módulo faz, e um jsdom custaria uma dependência de 3 MB para
   testar cinco funções. */
function el(tag) {
  const no = {
    tagName: String(tag).toUpperCase(),
    children: [],
    attrs: {},
    style: {},
    _text: '',
    _html: null,
    listeners: {},
    /* O `id` REGISTA-SE no documento. Sem isto, `getElementById` devolvia
       sempre null e cada chamada a `hostEl()` criava um contentor novo — e o
       teste lia um contentor vazio enquanto o módulo desenhava noutro. Foi a
       primeira versão deste ficheiro, e falhou 20 verificações de uma vez
       porque o erro não era do módulo. */
    set id(v) {
      this.attrs.id = v;
      if (v) global.document._ids[v] = this;
    },
    get id() {
      return this.attrs.id || '';
    },
    set textContent(v) {
      this._text = v == null ? '' : String(v);
      this.children = [];
    },
    /* O `textContent` de um elemento real devolve o PRÓPRIO texto E o dos
       filhos. A primeira versão devolvia só o dos filhos, e por isso um bloco
       que punha a motivo com `textContent` e depois acrescentava a fonte
       mostrava apenas a fonte — que é o inverso do que o browser faz. */
    get textContent() {
      return this._text + this.children.map((c) => c.textContent).join('');
    },
    set innerHTML(v) {
      this._html = v;
    },
    get innerHTML() {
      return this._html;
    },
    set className(v) {
      this.attrs.class = v;
    },
    get className() {
      return this.attrs.class || '';
    },
    set type(v) {
      this.attrs.type = v;
    },
    get type() {
      return this.attrs.type || '';
    },
    set href(v) {
      this.attrs.href = v;
    },
    set download(v) {
      this.attrs.download = v;
    },
    setAttribute(k, v) {
      this.attrs[k] = String(v);
    },
    getAttribute(k) {
      return this.attrs[k];
    },
    /* `appendChild` tem de POER `parentElement`, e `removeChild` tem de o
     * LIMPAR e apagar o `id` do registo.
     *
     * Sem isto, `hostEl()` montava e `montaSeVisivel()` tentava recortar com
     * `host.parentElement.removeChild(...)` — e `parentElement` era `undefined`
     * porque `appendChild` nao o punha. O recorte nunca acontecia, o aviso
     * saia na mesma (o guarda tinha ja decidido), e o teste via "o host foi
     * recortado" falhava. Nao era o modulo a falhar: era o DOM de mentira a
     * nao fazer a coisa mais basica que faz. */
    appendChild(c) {
      if (c) c.parentElement = this;
      this.children.push(c);
      return c;
    },
    removeChild(c) {
      this.children = this.children.filter((x) => x !== c);
      if (c) {
        c.parentElement = null;
        /* Um no que saiu da arvore nao e encontrado por `getElementById`. O
         * registo `_ids` e um dicionario a parte e nao se limpa sozinho — e
         * um no removido que ainda responde e pior do que um no que nunca
         * existiu. */
        if (c.id) delete global.document._ids[c.id];
      }
    },
    addEventListener(n, f) {
      this.listeners[n] = f;
    },
    dispatchEvent() {
      return true;
    },
    click() {},
    focus() {},
    /* `querySelector` para os DOIS seletores que o modulo usa quando pergunta
     * "a peça está neste contentor?". Sem isto, `slotDesenhado` cairia no
     * `return true` de segurança e o modulo acreditaria num contentor que só
     * tem o texto de fallback por cima — que é exactamente o defeito que o
     * browser mostrou. */
    querySelector(sel) {
      if (typeof sel !== 'string' || sel.charAt(0) !== '.') return null;
      const alvo = sel.slice(1);
      const acha = (no) => {
        if (no.className === alvo) return no;
        for (const c of no.children || []) {
          const r = acha(c);
          if (r) return r;
        }
        return null;
      };
      for (const c of this.children || []) {
        const r = acha(c);
        if (r) return r;
      }
      return null;
    },
    /* Um rect NAO nulo. `estaCoberto` mede o canto superior esquerdo +2px e
     * pede o rect; um rect de zeros faria a funcao dizer "fora da janela" e
     * devolver "nao tapado" sem nunca ter perguntado nada ao DOM. */
    getBoundingClientRect() {
      return { left: 0, top: 0, width: 300, height: 120, right: 300, bottom: 120 };
    },
    /* `contains` e o que separa "e o host" de "e alguma coisa por cima". A
     * versao antiga devolvia sempre `false`, o que obrigava o guarda a dizer
     * "tapado" mesmo quando o elemento ERA o nosso. */
    contains(outro) {
      if (!outro) return false;
      if (outro === this) return true;
      return this.children.some((c) => (c.contains ? c.contains(outro) : c === outro));
    },
  };
  return no;
}

/* Um nó de texto é um nó sem `set`, e o `textContent` tem de devolver o
   PRÓPRIO texto. A primeira versão não tinha isto e o aviso — que é feito de
   um `createTextNode` — lia-se como string vazia. */
function textoNode(valor) {
  return {
    tagName: '#text',
    children: [],
    attrs: {},
    style: {},
    /* `_html: null` e obrigatorio. Sem ele, `undefined !== null` e o verificador
       de "ninguem foi injetado como HTML" conta um nó de texto como se fosse
       uma injeção — e falha por causa do DOM de mentira, não do módulo. */
    _html: null,
    _text: String(valor == null ? '' : valor),
    get textContent() {
      return this._text;
    },
    set textContent(v) {
      this._text = String(v);
    },
    set innerHTML(v) {
      this._html = v;
    },
    appendChild() {},
    addEventListener() {},
  };
}

const PECA = {
  existe: true,
  nome: 'Custo da safra',
  estado: 'publicado',
  versao: 3,
  total: 3,
  blocos: [
    {
      id: 'b1',
      tipo: 'texto',
      titulo: 'Resumo',
      fonte_dado: 'medido',
      config: { texto: 'A safra fechou acima do previsto.' },
    },
    {
      id: 'b2',
      tipo: 'tabela',
      titulo: 'Despesas',
      fonte_dado: 'medido',
      config: {
        colunas: ['categoria', 'valor'],
        linhas: [
          ['Adubo', '1.200,00'],
          ['Semente', '800,00'],
        ],
      },
    },
    {
      id: 'b3',
      tipo: 'kpi',
      titulo: 'Custo por hectare',
      fonte_dado: 'sem_dado',
      config: {},
    },
  ],
  sem_dado: ['b3'],
  numeros_sem_apoio: [],
};

/* Uma cópia profunda, porque `desenha` pode mutar e o próximo teste precisa do
   original — e um teste que depende da ordem dos outros não mede nada. */
function peca(base) {
  return JSON.parse(JSON.stringify(base || PECA));
}

/* `console` e `window.console` sao o MESMO objecto, como num browser.
 *
 * O stub era `{}`, e isso mentia: `window.console` era `undefined`, o guarda
 * `window.console && console.warn(...)` cortava, e o aviso NUNCA saia. O
 * modulo parecia calado quando, num browser, fala. Um stub que e mais pobre que
 * a coisa que finge substituir esconde precisamente o que se quer testar. */
global.window = {
  console: console,
  innerWidth: 1280,
  innerHeight: 800,
  /* O `load` e o `resize` ficam registados em vez de executados. O modulo
   * chama `agendaCorte` no `load` e no `resize`; num stub que os executasse
   * na hora, o corte seria medido antes de existir layout, que e o erro que o
   * browser revelou. Guardados, o teste decide QUANDO o quadro acontece. */
  _listeners: {},
  addEventListener: function (n, f) {
    (this._listeners[n] = this._listeners[n] || []).push(f);
  },
};
global.document = {
  cookie: 'csrftoken=abc',
  readyState: 'complete',
  _ids: {},
  /* `_tapa` e a peça que esta POR CIMA do ponto onde o rato carregaria.
   *
   * Este stub existia sem qualquer noção de oclusão, e e por isso que deu 50
   * verdes com um botao que ninguem conseguia carregar: num DOM de mentira nao
   * ha CSS, e sem `position:absolute` nao ha nada por cima. `_tapa` da ao
   * modulo uma coisa CONTRA que chocar — mas quem diz se o browser esta de
   * acordo com este stub e o `tests/e2e/chamado.spec.ts`, nao este ficheiro. */
  _tapa: null,
  /* `_quadros` e a fila do `requestAnimationFrame`. Vem aqui porque o stub do
   * `document` e o do `window` sao o mesmo objecto deseoito, e o global tem de
   * ver a fila. */
  _quadros: [],
  /* `_slot` e o contentor que a matriz cria para o widget do Chamado:
   * `#widget-chamado-amplia .widget-content`. E o caminho NORMAL a partir de
   * agora — o modulo deixou de se montar sozinho no `#content`, porque la o
   * dashboard tapava-o com a matriz. */
  _slot: null,
  head: el('head'),
  body: el('body'),
  content: el('main'),
  createElement: el,
  createTextNode: textoNode,
  getElementById: (id) =>
    global.document._ids[id] || (id === 'content' ? global.document.content : null),
  /* So o selector que o modulo usa. Um `querySelector` geral seria mentira:
   * diria que o stub sabe CSS, e nao sabe. */
  querySelector: function (sel) {
    if (sel === '#widget-chamado-amplia .widget-content') return global.document._slot;
    return null;
  },
  /* `elementFromPoint` responde o que o RATO alcançaria. `_tapa` e a resposta de
   * um dashboard com a matriz cravada por cima. */
  elementFromPoint: function () {
    return global.document._tapa;
  },
  addEventListener: function () {},
  dispatchEvent: function () {},
};

/* `requestAnimationFrame` ENFILEIRA. Nao executa. E vive no GLOBAL, nao no
 * `document` — o modulo chama-o pelu nome, e num browser isso da para a janela.
 *
 * O modulo mede a oclusão em `requestAnimationFrame` porque no browser a
 * matriz ainda não está pintada no momento do mount. Se o stub executasse o
 * callback na hora, mediria cedo demais — e voltaria a passar pelo motivo
 * errado, que e como este bloco ja falhou uma vez. Estando aqui em vez de
 * `document.requestAnimationFrame`, o modulo caia no `setTimeout` e o corte
 * nunca acontecia: cinco verificações a falhar porque o stub estava no sitio
 * errado, e nao o modulo. */
global.requestAnimationFrame = function (f) {
  global.document._quadros.push(f);
  return global.document._quadros.length;
};

/* "Pinta" um quadro: esvazia a fila e corre o que ficou nela. Como no browser, o
 * que se enfileira DENTRO de um quadro corre no quadro seguinte. */
function pintaQuadro(vezes) {
  for (let i = 0; i < (vezes || 1); i++) {
    const lote = global.document._quadros;
    global.document._quadros = [];
    lote.forEach((f) => f());
  }
}
global.CustomEvent = function (n, i) {
  this.type = n;
  this.detail = i && i.detail;
};
global.Event = function (n, i) {
  this.type = n;
  this.init = i;
};
/* Node 24 tem `global.navigator` como só-getter, e atribuir directamente rebenta com um
   TypeError que não tem nada a ver com o que estamos a testar. `defineProperty`
 * é o caminho que funciona em todas as versões. */
try {
  Object.defineProperty(global, 'navigator', { value: {}, configurable: true, writable: true });
} catch (e) {
  /* ja existe e e' inalteravel: o modulo so o usa no fallback */
}
global.Blob = function () {};
global.URL = { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} };

let fetched = [];
global.fetch = function (url, init) {
  fetched.push({ url: url, init: init || {} });
  return Promise.resolve({
    json: () =>
      Promise.resolve({ ok: true, chamado: peca(), zona_escrita: { preset: 'chamado-amplia' } }),
  });
};
window.fetch = global.fetch;
window.dispatchEvent = function () {};

const PRESETAS_BASE = [{ id: 'visao-geral', name: 'Visao Geral' }];
window.WidgetIntelligence = {
  getPresets: function () {
    return PRESETAS_BASE.slice();
  },
};
window.prompt = function () {
  return null;
};
window.location = { hash: '' };

eval(FONTE);
const C = window.AmpliaChamado;

/* O SLOT DO WIDGET, e uma peca para ele.
 *
 * O modulo deixou de se montar sozinho no `#content` — no dashboard, a matriz
 * bento tapava-o — e passou a desenhar dentro de
 * `#widget-chamado-amplia .widget-content`, o contentor que o proprio
 * `generateWidgetContent` cria para este id. Este e o caminho normal, e e o
 * que o browser vai fazer. O stub tem de ter o mesmo slot, senao todos os
 * testes de desenho medem `desenha` a devolver `null` — que era o que acontecia,
 * e nao era o modulo a falhar. */
function novaSlot() {
  const s = el('div');
  s.className = 'widget-content';
  global.document._slot = s;
  return s;
}
novaSlot();

/* O fonte sem comentarios: o `innerHTML` so aparece no CABECALHO, e o
 * teste do seletor adivinhado tambem. */
const semComentarios = FONTE.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

/* Helper: percorre a arvore collecting texto e atributos. */
function achatar(no, acc) {
  acc = acc || { texto: '', attrs: [], classes: [], innerHTML: [], nos: [] };
  if (!no) return acc;
  acc.texto += (no.textContent || '') + ' ';
  acc.nos.push(no);
  if (no.attrs && no.attrs.class) acc.classes.push(no.attrs.class);
  Object.keys(no.attrs || {}).forEach((k) => acc.attrs.push(k + '=' + no.attrs[k]));
  if (no._html !== null) acc.innerHTML.push(no._html);
  (no.children || []).forEach((c) => achatar(c, acc));
  return acc;
}

console.log('\n== 1. a peca desenha ==');
C.desenha(peca());
let v = achatar(C.hostEl());
t('o titulo da peca aparece', v.texto.indexOf('Custo da safra') >= 0);
t('a versao aparece', v.texto.indexOf('v3') >= 0);
t('o texto do bloco aparece', v.texto.indexOf('A safra fechou acima') >= 0);
t(
  'os valores da tabela aparecem',
  v.texto.indexOf('Adubo') >= 0 && v.texto.indexOf('1.200,00') >= 0
);
t('os tres blocos desenham', v.classes.filter((c) => c.indexOf('amc-') === 0).length >= 3);

console.log('\n== 2. a proveniencia chega ao ecra ==');
C.desenha(peca());
v = achatar(C.hostEl());
t('sem_dado traz a marca "sem dado"', v.texto.indexOf('sem dado') >= 0);
t('sem_dado NAO escreve 0 como valor', v.texto.indexOf('—') >= 0);
t('o bloco sem dado carrega data-fonte', v.attrs.join(' ').indexOf('data-fonte=sem_dado') >= 0);
t('o aviso explica que nao e zero', v.texto.indexOf('Não é zero') >= 0);
t('o aviso nomeia o bloco', v.texto.indexOf('b3') >= 0);

console.log('\n== 3. numeros sem apoio ==');
const P2 = peca();
P2.numeros_sem_apoio = [
  { bloco: 1, numero: '18%' },
  { bloco: 1, numero: '30' },
];
P2.blocos[1].fonte_dado = 'sem_dado';
P2.sem_dado = ['b1', 'b2'];
C.desenha(P2);
v = achatar(C.hostEl());
t('o aviso existe', v.texto.indexOf('Antes de decidir') >= 0);
t('o aviso diz que nenhum bloco sustenta', v.texto.indexOf('nenhum bloco sustenta') >= 0);
t('o aviso nomeia 18%', v.texto.indexOf('18%') >= 0);
t('o aviso nomeia 30', v.texto.indexOf('30') >= 0);

console.log('\n== 4. peca vazia ==');
C.desenha({ existe: false });
v = achatar(C.hostEl());
t('diz que ainda nao ha', v.texto.indexOf('Ainda não há') >= 0);
t(
  'nao desenha grelha',
  v.classes.filter((c) => c.indexOf('amplia-chamado-blocos') >= 0).length === 0
);

console.log('\n== 5. arquivado esconde o botao de editar ==');
const P3 = peca();
P3.estado = 'arquivado';
C.desenha(P3);
v = achatar(C.hostEl());
t('o aviso de arquivado aparece', v.texto.indexOf('a IA só lê') >= 0);
t('NÃO ha botao "Pedir alteracao"', v.texto.indexOf('Pedir alteração') < 0);

console.log('\n== 6. o botao de alterar SÓ existe se houver pipeline ==');
/* O botao chamava `window.iaDockSend`, a API publica do pipeline unico da IA.
 * A versao anterior procurava `#amplia-chat-input`, que NAO EXISTE — e o botao
 * aceitava o clique e nao fazia nada, sem erro nenhum.
 *
 * Aqui cobrem-se os dois estados, porque os dois importam: com pipeline o
 * botao existe e envia; sem pipeline o botao NAO EXISTE e ha uma nota. Um botao
 * que esta la e nao faz nada e pior do que um botao que nao existe. */
let enviados = [];
window.iaDockSend = function () {
  enviados.push('pergunta');
};
window.iaDockToggle = function () {};

C.desenha(peca());
v = achatar(C.hostEl());
t('com pipeline, ha botao "Pedir alteracao"', v.texto.indexOf('Pedir alteracao a IA') >= 0);
t('com pipeline, ha botao de exportar tudo', v.texto.indexOf('Exportar tudo') >= 0);

t(
  'sem pipeline, o botao desaparece',
  (function () {
    delete window.iaDockSend;
    C.desenha(peca());
    const s = achatar(C.hostEl());
    return s.texto.indexOf('Pedir alteracao a IA') < 0;
  })()
);
t(
  'sem pipeline, ha uma nota que explica',
  (function () {
    const s = achatar(C.hostEl());
    return s.texto.indexOf('chat da IA nao esta nesta tela') >= 0;
  })()
);

t(
  'pedirChat diz que nao ha pipeline em vez de falar em silencio',
  (function () {
    const r = window.AmpliaChamado.pedirChat('acrescenta uma tabela');
    return r.ok === false && r.motivo === 'sem_pipeline';
  })()
);

t(
  'NAO ha seletor adivinhado no fonte',
  (function () {
    const codigo = semComentarios;
    return codigo.indexOf('amplia-chat-input') < 0 && codigo.indexOf('amplia-chat-form') < 0;
  })()
);

window.iaDockSend = function () {
  enviados.push('pergunta');
};
t(
  'pedirChat envia com pipeline',
  (function () {
    const r = window.AmpliaChamado.pedirChat('acrescenta uma tabela');
    return r.ok === true;
  })()
);
/* `semComentarios` e definido na seccao 7, que corre DEPOIS. Uma vez por
 * ficheiro chega, e por isso e posto aqui com a sua propria limpeza. */
function _limpa(codigo) {
  return codigo.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
}

console.log('\n== 7. NUNCA innerHTML — o titulo vem do modelo ==');
/* O invariante é literal e verificável: **nenhuma atribuição a `.innerHTML` em
   todo o ficheiro**, ponto. A primeira versão desta verificação era uma
   expressão com `||` que passava por dois caminhos e portanto não provava nada
   — e um teste que não prova é pior do que não ter, porque conta como verde.
   O `innerHTML` aparece no CABEÇALHO em comentário, que é a única razão de a
   contagem ser feita sobre o código e não sobre o ficheiro. */
t('o fonte nao atribui innerHTML em lado nenhum', semComentarios.indexOf('innerHTML') < 0);
t(
  'o fonte nao cria elementos com insertAdjacentHTML',
  semComentarios.indexOf('insertAdjacentHTML') < 0
);
t('o fonte nao usa document.write', semComentarios.indexOf('document.write') < 0);

const P4 = peca();
P4.blocos[0].titulo = '<img src=x onerror=alert(1)>';
P4.blocos[0].config.texto = '<script>alert(2)</' + 'script>';
C.desenha(P4);
v = achatar(C.hostEl());
t('o titulo malicioso aparece como TEXTO', v.texto.indexOf('<img src=x onerror=alert(1)>') >= 0);
t('o script malicioso aparece como TEXTO', v.texto.indexOf('<script>alert(2)</script>') >= 0);
t('nenhum no foi injetado como HTML', v.innerHTML.length === 0);

console.log('\n== 8. a widget-bar conhece o preset ==');
const lista = window.WidgetIntelligence.getPresets();
t(
  'o preset existe na barra',
  lista.some((p) => p && p.id === 'chamado-amplia')
);
t(
  'nao duplica quando chamado outra vez',
  (function () {
    window.WidgetIntelligence.getPresets();
    const d = window.WidgetIntelligence.getPresets();
    return d.filter((p) => p && p.id === 'chamado-amplia').length === 1;
  })()
);
t(
  'os presets de base continuam la',
  lista.some((p) => p && p.id === 'visao-geral')
);

console.log('\n== 9. o CSV leva BOM e ponto-e-virgula ==');
t('o CSV comeca com BOM (Excel pt-BR)', FONTE.indexOf('﻿') >= 0);
t('o CSV usa ; como separador', FONTE.indexOf("join(';')") >= 0);

console.log('\n== 10. limites ==');
t('o teto de blocos vem do servidor', C.MAX_BLOCOS === 24);
t(
  'os tres estados de proveniencia e nenhum mais',
  Object.keys(C.ROTULO_FONTE).sort().join(',') === 'medido,sem_dado,simulado'
);
t('"medido" nao leva marca nenhuma', C.ROTULO_FONTE.medido === '');

console.log('\n== 11. carregar vai a SÓ LEITURA ==');
fetched = [];
C.carrega()
  .then(function () {
    t(
      'le de /palco/chamado/',
      fetched.some((f) => f.url.indexOf('/palco/chamado/') >= 0)
    );
    t(
      'nao faz POST para ler',
      fetched.every((f) => !f.init || f.init.method !== 'POST')
    );

    console.log('\n== 12. a escrita nao e feita por aqui ==');
    const chavesEscrita = ["fetch('PATCH", "fetch('PUT", "fetch('DELETE"];
    t(
      'nao ha PATCH/PUT/DELETE no fonte',
      chavesEscrita.every((k) => FONTE.indexOf(k) < 0)
    );
    t(
      'a unica rota de exec e referenciada, nao chamada directamente',
      FONTE.indexOf("exec: '/api/amplia/exec/'") >= 0
    );

    console.log('\n== 13. um bloco vazio diz PORQUE ==');
    const P5 = peca();
    P5.blocos = [
      {
        id: 'b9',
        tipo: 'tabela',
        titulo: 'Despesas',
        fonte_dado: 'sem_dado',
        config: {
          colunas: ['categoria', 'valor'],
          linhas: [],
          fonte: 'despesas-por-categoria',
          motivo: 'Sem fonte: a IA escreveu os numeros e foram descartados.',
        },
      },
    ];
    C.desenha(P5);
    v = achatar(C.hostEl());
    t('o motivo do servidor aparece', v.texto.indexOf('foram descartados') >= 0);
    t('a fonte aparece no bloco vazio', v.texto.indexOf('despesas-por-categoria') >= 0);
    t('a marca sem dado continua', v.texto.indexOf('sem dado') >= 0);

    const P6 = peca();
    P6.blocos = [
      {
        id: 'b8',
        tipo: 'tabela',
        titulo: 'Despesas',
        fonte_dado: 'sem_dado',
        config: { colunas: ['categoria'], linhas: [] },
      },
    ];
    C.desenha(P6);
    v = achatar(C.hostEl());
    t('sem motivo, ha texto por omissao', v.texto.indexOf('Sem linhas') >= 0);

    console.log('\n== 14. a fonte e visivel nos dados ==');
    const P7 = peca();
    P7.blocos = [
      {
        id: 'b7',
        tipo: 'tabela',
        titulo: 'Despesas',
        fonte_dado: 'medido',
        config: {
          colunas: ['categoria', 'valor'],
          linhas: [['Adubo', '1.234,56']],
          fonte: 'despesas-por-categoria',
        },
      },
    ];
    C.desenha(P7);
    v = achatar(C.hostEl());
    t('a fonte aparece com o numero', v.texto.indexOf('fonte: despesas-por-categoria') >= 0);
    t('o numero aparece', v.texto.indexOf('1.234,56') >= 0);
    t('medido nao leva marca', v.texto.indexOf('sem dado') < 0);

    /* ===========================================================================
   O CONTENTOR TAPADO — o achado que so o browser deu
   ===========================================================================
   O dashboard crava a matriz bento com `position: absolute !important; inset:
   0 0 56px 0` dentro de um `#content` com `overflow: hidden`. O `#content` nao
   tem espaco de flow: o que se ligar la fica por baixo da matriz.

   Aqui o modulo monta. No browser real, montava e ficava invisivel — com o
   botao "Pedir alteracao" no DOM, clicavel por seletor, e impossivel de
   carregar com um rato. Estes testes existem para o ramo "recusar montar" ter
   cobertura no DOM de mentira tambem. Nao provam que a regra esta certa no
   browser — para isso esta o `tests/e2e/chamado.spec.ts`. */
    console.log('\n== 20. ONDE A PECA SE DESENHA ==');

    /* ESTE BLOCO E SINCRONO DE PROPOSITO.
     *
     * A primeira versao re-avaliava o modulo e esperava um tick, porque `carrega()`
     * desenha dentro da promise do `fetch`. Passou "nao monta" — mas porque NADA
     * TINHA DESENHADO ainda, nao porque o guarda fosse verdadeiro. Um teste que
     * passa pela razao errada e pior que nenhum: compra a certeza sem a ter.
     *
     * A via curta e synchronous: o modulo exporta `desenha`, `hostEl` e
     * `aposRenderWidgets`, e o sitio onde desenha esta dentro deles. */
    (function ondeDesenha() {
      const aviso = [];
      const warnOriginal = console.warn;
      console.warn = function (m) {
        aviso.push(String(m));
      };

      /* O dashboard com a matriz cravada: o rato carrega e acerta noutro widget. */
      const comTapadeira = () => {
        document._tapa = el('div');
        document._tapa.id = 'grid-da-matriz';
      };
      const semTapadeira = () => {
        document._tapa = null;
      };
      const limpar = () => {
        delete document._ids['amplia-chamado-ancora'];
        delete document._ids['amplia-chamado-host'];
        document._tapa = null;
        document._slot = null;
      };

      try {
        /* --- 1. O SLOT DO WIDGET: o caminho normal ---
         * Nao ha host, nao ha ancora, e mesmo assim desenha — porque a matriz cria
         * o contentor e o modulo escreve lá dentro. E o que o browser vai fazer. */
        limpar();
        const slot = novaSlot();
        semTapadeira();
        aviso.length = 0;
        const r = C.desenha(peca());
        t('com o slot do widget, desenha', r === slot);
        t('e escreve dentro do slot', achatar(slot).texto.indexOf('Custo da safra') >= 0);
        t('e nao cria um host proprio', !document._ids['amplia-chamado-host']);
        t('e marca o slot como desenhado', slot.getAttribute('data-chamado-pronto') === '1');
        t('e nao se queixa de nada', aviso.length === 0);

        /* --- 2. SEM SLOT E SEM ANCORA: nao desenha e diz porquê ---
         * Este e o ramo que substitui o antigo fallback para `#content`. Um painel
         * que se desenha por baixo da matriz e pior do que um painel que nao se
         * desenha. */
        limpar();
        aviso.length = 0;
        const semSitio = C.desenha(peca());
        t('sem slot e sem ancora, nao desenha nada', semSitio === null);
        t('e explica que nao ha sitio', aviso.length > 0);
        t('e diz que o contentor seria o #content', aviso.join(' ').indexOf('#content') >= 0);
        t('e aponta o widget como a saida', aviso.join(' ').indexOf('chamado-amplia') >= 0);

        /* E UMA VEZ SO. Um aviso por chamada enche a consola de quem nao esta a
         * depurar nada, e um aviso repetido treina quem lê a ignora-lo. */
        aviso.length = 0;
        C.desenha(peca());
        C.desenha(peca());
        t('e o aviso de "sem sitio" nao se repete', aviso.length === 0);

        /* --- 3. A ANCORA DEDICADA, quando existe ---
         * O contentor e do modulo, e so nesse caso vale a pena perguntar se esta
         * tapado: e o modulo que escolheu o sitio. */
        limpar();
        const ancora = el('div');
        ancora.id = 'amplia-chamado-ancora';
        document._ids['amplia-chamado-ancora'] = ancora;
        ancora.getBoundingClientRect = () => ({
          left: 0,
          top: 0,
          width: 300,
          height: 60,
          right: 300,
          bottom: 60,
        });
        comTapadeira();
        aviso.length = 0;
        C.desenha(peca());
        t('com ancora, no instante do mount o host existe', !!document._ids['amplia-chamado-host']);
        pintaQuadro(2);
        t('depois de pintar com algo por cima, e recortado', !document._ids['amplia-chamado-host']);
        t('e diz que a matriz o tapou', aviso.join(' ').toLowerCase().indexOf('matriz') >= 0);

        /* --- 4. A ANCORA VISIVEL: fica ---
         * Sem esta viragem, o teste acima passaria mesmo que o guarda fosse "recusar
         * sempre". */
        limpar();
        delete document._ids['amplia-chamado-ancora'];
        const ancora2 = el('div');
        ancora2.id = 'amplia-chamado-ancora';
        document._ids['amplia-chamado-ancora'] = ancora2;
        ancora2.getBoundingClientRect = () => ({
          left: 0,
          top: 0,
          width: 300,
          height: 60,
          right: 300,
          bottom: 60,
        });
        const originalEFP = document.elementFromPoint;
        document.elementFromPoint = function () {
          return document._ids['amplia-chamado-host'] || document._tapa;
        };
        semTapadeira();
        aviso.length = 0;
        C.desenha(peca());
        pintaQuadro(2);
        t('com a ancora a salvo, o host fica', !!document._ids['amplia-chamado-host']);
        t('e nao se queixa', aviso.length === 0);
        document.elementFromPoint = originalEFP;
      } finally {
        console.warn = warnOriginal;
        limpar();
        /* Deixa o estado como o resto da suite espera encontrar. */
        novaSlot();
        C.desenha(peca());
        pintaQuadro(2);
      }
    })();

    console.log('\n== 21. O QUE ACONTECE QUANDO A MATRIZ SE REDESENHA ==');

    var redesenho = (function redesenho() {
      /* `renderWidgetsOnMatrix` apaga e recria TODOS os `.bento-block` de cada vez
       * que o painel muda. O contentor onde a peça foi desenhada deixa de existir.
       * Sem o ponto de retorno, o painel acabava de desenhar a peça e um clique em
       * qualquer lado a apagava — voltando ao texto generico de widget
       * desconhecido. */
      document._slot = null;
      delete document._ids['amplia-chamado-ancora'];
      delete document._ids['amplia-chamado-host'];

      /* `carrega()` e assincrono (esta dentro da promise do fetch), por isso
       * `aposRenderWidgets` so trabalha depois de `carregado`. */
      C.estado.carregado = false;
      const semSlot = novaSlot();
      t('sem peca carregada, nao inventa nada', C.aposRenderWidgets() === false);

      return fetch('/api/amplia/palco/chamado/')
        .then(function (r) {
          return r.json();
        })
        .then(function () {
          /* Simula o que `carrega()` deixa: uma peca em memoria e `carregado`. */
          C.desenha(peca());
          C.estado.carregado = true;

          /* A matriz recria o contentor: e um no NOVO, sem o marker. */
          const slotNovo = novaSlot();
          t('o redesenho acontece no contentor novo', C.aposRenderWidgets() === true);
          t('e escreve a peca nele', achatar(slotNovo).texto.indexOf('Custo da safra') >= 0);
          t('e marca o novo contentor', slotNovo.getAttribute('data-chamado-pronto') === '1');

          /* E NAO redesenha para cima de si mesmo. Sem esta guarda, o desenho
           * disparava o ponto de retorno, que redesenhava, que disparava: a peça
           * piscava a cada render. */
          t('e nao redesenha duas vezes no mesmo contentor', C.aposRenderWidgets() === false);

          /* E se a matriz NAO desenhou, nao ha o que fazer — e nao e um erro. */
          document._slot = null;
          t('sem slot, nao faz nada', C.aposRenderWidgets() === false);
          document._slot = semSlot;
        });
    })();

    /* O RESUMO ESPERA PELA PROMISE.
     *
     * A primeira versao imprimia o resumo logo a seguir ao IIFE, que devolvia uma
     * promise: `process.exit` matava o processo antes do `.then`, e as seis
     * verificacoes do bloco 21 nunca chegavam a correr. A suite publicava um verde
     * maior sem nunca ter medido uma parte do que dizia medir — e um numero que
     * cresce porque se apagou um bloco parece uma melhoria.
     *
     * Por isso o resumo e a ultima coisa, e a promessa do bloco 21 e devolvida
     * a esta cadeia — a que ja existia. Nao se abre uma segunda cadeia a meio
     * dela: um `.then` dentro de outro `.then` deixa o `.catch` do fim sem
     * apanhar nada, que e pior do que nao ter `.catch` nenhum. */
    return redesenho;
  })

  .then(function () {
    console.log('\n' + '='.repeat(64));
    /* O formato do resumo é o do runner (`scripts/rodar_testes_cjs.mjs`), que lê
     o ÚLTIMO `<número> ok|checks` da saída. Escrever "36 verificações" e
     "36 ok" é a mesma informação, mas só uma delas conta — e a que não conta
     publica uma suite sem número, que é um verde que não diz nada. */
    console.log(
      falhas === 0
        ? ok + ' ok, 0 falhas. TUDO VERIFICADO.'
        : falhas + ' falhas de ' + (ok + falhas) + '.'
    );
    process.exit(falhas === 0 ? 0 : 1);
  })
  .catch(function (e) {
    console.log('  ERRO no carregar(): ' + e);
    process.exit(1);
  });
