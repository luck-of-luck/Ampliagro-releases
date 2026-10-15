/**
 * O painel de um produtor que ainda não registou propriedade tem de dizer
 * que não tem propriedade.
 *
 * O QUE ESTE TESTE TRAVA
 * ----------------------
 * `/api/dashboard/` devolve `{"sem_propriedade": true}` quando o produtor
 * ainda não registou propriedade. Esse sinal é lido, guardado em
 * `dashboardData` — e nunca era usado para nada. O que o produtor via era:
 *
 *     ┌────────────────┐  ┌────────────────┐
 *     │ FLUXO DE CAIXA │  │ ALERTAS        │
 *     │ sem dado       │  │ 0              │
 *     │ Sem lançamentos│  │ Nenhum alerta  │
 *     └────────────────┘  └────────────────┘
 *
 * Não é um painel vazio — é um painel *com widgets*, que é pior. Um vazio
 * puro diz "não há nada". Um painel com widgets a dizer "sem dado" diz "o
 * sistema funciona e a sua fazenda está vazia", e não é verdade nenhuma das
 * duas: não há propriedade registada, e sem propriedade não há nada para
 * medir. O produtor não tem como saber que o passo seguinte é registar a
 * propriedade, porque ninguém mo disse.
 *
 * A regra do projecto é a dos números: **ausência que não é anunciada é uma
 * mentira**. Aqui a ausência é a propriedade.
 *
 * POR QUE EXTRAIR A FUNÇÃO EM VEZ DE IMPORTAR O FICHEIRO
 * ------------------------------------------------------
 * `dashboard-desktop.js` é um script de browser que depende de `widgets`,
 * `WIDGET_TYPES`, `GRID_COLS` e de um DOM montado. Extrair só a função do
 * render e correr com stubs testa o código que está em produção — não uma
 * cópia, e não uma reimplementação.
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const caminhoJS = path.resolve(__dirname, '../../app/static/js/tabs/dashboard-desktop.js');
const fonte = fs.readFileSync(caminhoJS, 'utf-8');

/** Extrai `window.renderWidgetsOnMatrix = function () { … };` por contagem de chavetas. */
function extrairRender() {
  const marca = 'window.renderWidgetsOnMatrix = function ()';
  const inicio = fonte.indexOf(marca);
  if (inicio === -1) throw new Error('renderWidgetsOnMatrix não encontrado');

  let i = fonte.indexOf('{', inicio);
  let nivel = 0;
  for (; i < fonte.length; i++) {
    if (fonte[i] === '{') nivel++;
    else if (fonte[i] === '}') {
      nivel--;
      if (nivel === 0) return fonte.slice(inicio, i + 1);
    }
  }
  throw new Error('não consegui fechar renderWidgetsOnMatrix');
}

/** Elemento de DOM mínimo: só o que a função usa. */
function elemento(tag) {
  return {
    tagName: tag,
    className: '',
    id: '',
    innerHTML: '',
    style: {},
    _attrs: {},
    _filhos: [],
    setAttribute(nome, valor) {
      this._attrs[nome] = String(valor);
    },
    getAttribute(nome) {
      return Object.prototype.hasOwnProperty.call(this._attrs, nome) ? this._attrs[nome] : null;
    },
    hasAttribute(nome) {
      return Object.prototype.hasOwnProperty.call(this._attrs, nome);
    },
    appendChild(el) {
      this._filhos.push(el);
      return el;
    },
    insertBefore(el) {
      this._filhos.unshift(el);
      return el;
    },
    querySelectorAll(seletor) {
      const classe = seletor.replace(/^\./, '');
      const out = [];
      const visitar = (no) => {
        for (const f of no._filhos) {
          if (f.className && f.className.split(/\s+/).includes(classe)) out.push(f);
          visitar(f);
        }
      };
      visitar(this);
      return out;
    },
    closest() {
      return null;
    },
    /** Todos os descendentes, para o teste poder procurar o aviso. */
    todos() {
      const out = [this];
      for (const f of this._filhos) out.push(...f.todos());
      return out;
    },
  };
}

/** `document` mínimo: `querySelector('.matrix-container')` e `createElement`. */
function domFalso() {
  const matriz = elemento('div');
  return {
    matriz,
    querySelector(sel) {
      return sel === '.matrix-container' ? matriz : null;
    },
    querySelectorAll() {
      return [];
    },
    getElementById() {
      return null;
    },
    createElement(tag) {
      return elemento(tag);
    },
  };
}

/** Corre o render com o estado dado. Devolve o contentor da matriz. */
function correr(dashboardData, { escondido = false } = {}) {
  const corpo = extrairRender();
  const dom = domFalso();

  // A função real usa `document`, `widgets` e `window.dashboardData`. Injetá-los
  // como parâmetros de `new Function` corre o código de produção sem browser.
  const factory = new Function(
    'document',
    'widgets',
    'generateWidgetContent',
    'initWidgetDragHandlers',
    'window',
    'primeiroArranqueEscondido',
    `${corpo.replace(
      'window.renderWidgetsOnMatrix = function ()',
      'function renderWidgetsOnMatrix()'
    )}
     return renderWidgetsOnMatrix;`
  );

  const widgets = { 'kpi-caixa': { visible: true, gridX: 0, gridY: 0, gridW: 4, gridH: 3 } };
  const render = factory(
    dom,
    widgets,
    () => '<div>conteudo</div>',
    () => {},
    { widgetbarState: null, dashboardData },
    () => escondido
  );

  render();
  return dom.matriz;
}

/** Procura, em qualquer ponto da árvore, o elemento com um atributo a "true". */
function comAtributo(raiz, atributo) {
  return raiz.todos().find((el) => el.getAttribute && el.getAttribute(atributo) === 'true');
}

describe('primeiro arranque — produtor sem propriedade', () => {
  it('o ficheiro tem o aviso, e não só a intenção', () => {
    // Falha cedo e com mensagem clara se alguém apagar a parte que desenho.
    expect(fonte).toContain('data-primeiro-arranque');
    expect(fonte).toContain('sem_propriedade');
  });

  it('mostra o aviso quando o backend diz sem_propriedade', () => {
    const matriz = correr({ sem_propriedade: true });
    const aviso = comAtributo(matriz, 'data-primeiro-arranque');
    expect(aviso, 'o aviso de primeiro arranque não foi inserido').toBeTruthy();
    expect(aviso.innerHTML).toContain('Comece por registar a sua propriedade');
  });

  it('o aviso diz que "sem dado" é falta de registo, não uma falha', () => {
    const matriz = correr({ sem_propriedade: true });
    const aviso = comAtributo(matriz, 'data-primeiro-arranque');
    expect(aviso.innerHTML).toMatch(/sem dado/i);
    expect(aviso.innerHTML).toMatch(/não é uma falha|Não é uma falha/i);
  });

  it('o aviso dá um caminho: link para o cadastro e para o passo a passo', () => {
    const matriz = correr({ sem_propriedade: true });
    const aviso = comAtributo(matriz, 'data-primeiro-arranque');
    expect(aviso.innerHTML).toContain('/cadastro/propriedade/');
    expect(aviso.innerHTML).toContain('/onboarding/');
  });

  it('mantém os widgets — o aviso explica, não substitui', () => {
    // O produtor vê o que vai passar a funcionar. Um aviso que escondesse os
    // widgets seria trocar um painel enganador por um painel vazio.
    const matriz = correr({ sem_propriedade: true });
    const widgets = matriz._filhos.filter(
      (f) => f.className && f.className.includes('bento-block')
    );
    expect(widgets.length).toBeGreaterThan(0);
  });

  it('NÃO mostra o aviso quando o produtor já tem propriedade', () => {
    // O aviso errado é pior do que a ausência do aviso: dizer "comece por
    // registar a propriedade" a quem já a registou é inventar um problema.
    const matriz = correr({ sem_propriedade: false, safras: [] });
    expect(comAtributo(matriz, 'data-primeiro-arranque')).toBeFalsy();
  });

  it('NÃO mostra o aviso quando o backend ainda não respondeu', () => {
    // `dashboardData` a null é "não sabemos ainda", e "não sabemos" não é
    // "não tem". Mostrar o aviso aqui seria afirmar uma coisa que ninguém mediu.
    const matriz = correr(null);
    expect(comAtributo(matriz, 'data-primeiro-arranque')).toBeFalsy();
  });

  it('respeita o "esconder" do produtor', () => {
    // Um botão que não faz nada é pior do que não ter botão.
    const matriz = correr({ sem_propriedade: true }, { escondido: true });
    expect(comAtributo(matriz, 'data-primeiro-arranque')).toBeFalsy();
  });

  it('o botão de esconder não é um botão morto', () => {
    expect(fonte).toContain('window.hideFirstRunBanner');
    expect(fonte).toMatch(/function primeiroArranqueEscondido/);
  });
});
