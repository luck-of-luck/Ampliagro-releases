/**
 * O DASHBOARD ESTA INTEIRO? — nenhuma funcao chamada sem definicao
 *
 * O QUE ESTE GUARD APANHA
 * ----------------------
 * Em 2026-10-04, `app/templates/index.html` perdeu um bloco contiguo de 4.135
 * linhas na arvore de trabalho (2 insercoes, 4.137 eliminacoes). As CHAMADAS
 * sobreviveram; as DEFINICOES nao. `getPresetOrder()` era chamada em 10+ sitios
 * e nao existia em lado nenhum do repositorio.
 *
 * O symptom nao foi uma excecao. O dashboard e' um `<script>` inline so, e um
 * unico ReferenceError aborta o ficheiro INTEIRO — de modo que tudo abaixo da
 * linha da queda deixava de correr sem um unico erro visivel. O produtor via
 * uma barra de presets vazia e o sintoma era "isto nao aparece".
 *
 * Nenhum teste viu. O ficheiro compilava, `manage.py check` passava, e o
 * servidor servia 594 KB de HTML perfeitamente valido.
 *
 * PORQUE UM PARSER E' PRECISO
 * ---------------------------
 * A primeira versao deste guard usou regex e deu 221 falsos positivos:
 * "Milho", "Brasil" e "Racao" estao dentro de strings e comentarios em
 * portugues. Um parser separa codigo de texto, e o ruido cai para zero.
 *
 * PORQUE ISTO E' EXECUTADO (e nao e' mais um teste morto)
 * --------------------------------------------------------
 * O `vitest.config.ts` inclui todos os `.test.{js,ts,tsx}` em `tests/unit/` e o
 * CI corre `npm test` (.github/workflows/ci.yml). Um include que nao casa com
 * nenhum ficheiro e' um teste que nao existe com a forma de teste — ja
 * aconteceu neste repositorio, e o comentario do `vitest.config.ts` regista-o.
 *
 * O LIMITE DESTE GUARD, DITO DE ANTEM
 * ------------------------------------
 * Ele sabe que um nome e' CHAMADO e que nao ha nenhuma declaracao com esse
 * nome em lado nenhum. Nao sabe se essa chamada esta dentro do scope certo.
 * Portanto so davera falhar quando o nome nao existe mesmo — que e' a
 * assinatura do ficheiro truncado. Nao substitui um teste de comportamento.
 */

import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from '@babel/parser';

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const INDEX = join(RAIZ, 'app', 'templates', 'index.html');
const JS_DIR = join(RAIZ, 'app', 'static', 'js');

/** Tira a sintaxe Django, que nao e' JavaScript e faria o parser falhar. */
function semDjango(src) {
  return src
    .replace(/\{\{[\s\S]*?\}\}/g, 'null')
    .replace(/\{%[\s\S]*?%\}/g, ';')
    .replace(/\{#[\s]*?#\}/g, '');
}

/** Os corpos dos <script> sem `src` — o dashboard e' inline. */
function corposInline(html) {
  const out = [];
  const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (/\bsrc\s*=/.test(m[1])) continue;
    out.push(m[2]);
  }
  return out;
}

function parseJS(src, etiqueta) {
  try {
    return parse(semDjango(src), {
      sourceType: 'script',
      allowReturnOutsideFunction: true,
      errorRecovery: true,
      plugins: [
        'optionalChaining',
        'nullishCoalescingOperator',
        'classProperties',
        'dynamicImport',
        'objectRestSpread',
        'classPrivateProperties',
      ],
    });
  } catch (e) {
    throw new Error(`${etiqueta}: nao parseou — ${e.message.slice(0, 160)}`);
  }
}

/**
 * Nomes declarados, em QUALQUER scope.
 *
 * A aproximacao e' deliberada e vao no sentido seguro: junta tudo o que esta
 * declarado em qualquer sitio. Um nome declarado num scope interior conta como
 * declarado. Isto produz falsos NEGATIVOS (pode deixar passar um erro de scope)
 * e nunca falsos positivos — que e o que interessa num guard destravado.
 */
function declarados(ast, acc = new Set()) {
  const add = (n) => {
    if (n && n.type === 'Identifier') acc.add(n.name);
  };
  const visitar = (no) => {
    if (!no || typeof no !== 'object') return;
    if (Array.isArray(no)) {
      no.forEach(visitar);
      return;
    }
    if (typeof no.type !== 'string') return;

    switch (no.type) {
      case 'FunctionDeclaration':
      case 'ClassDeclaration':
        // Os PARAMETROS contam. Sem esta linha, `fn` em
        // `function debouncedSave(key, fn, delay)` aparecia como chamado sem
        // definicao — o primeiro rascunho deste guard tinha esse bug.
        add(no.id);
        (no.params || []).forEach(add);
        break;
      case 'VariableDeclarator':
        add(no.id);
        if (no.init) visitar(no.init);
        break;
      case 'FunctionExpression':
      case 'ArrowFunctionExpression':
        (no.params || []).forEach(add);
        add(no.id);
        break;
      case 'AssignmentExpression': {
        const l = no.left;
        // `window.X = ...` e' como o dashboard expoe a maioria das funcoes.
        if (
          l &&
          l.type === 'MemberExpression' &&
          l.object &&
          l.object.type === 'Identifier' &&
          l.object.name === 'window' &&
          l.property &&
          l.property.type === 'Identifier'
        ) {
          acc.add(l.property.name);
        }
        add(l);
        break;
      }
      case 'ObjectProperty':
      case 'ObjectMethod':
        add(no.key);
        break;
      case 'CatchClause':
        add(no.param);
        break;
      case 'ImportSpecifier':
      case 'ExportSpecifier':
        add(no.local || no.exported);
        break;
      default:
        break;
    }
    for (const k of Object.keys(no)) {
      if (k === 'loc' || k === 'leadingComments' || k === 'trailingComments') continue;
      visitar(no[k]);
    }
  };
  visitar(ast);
  return acc;
}

/** Identificadores usados como CALLEE: `nome(`. */
function chamadas(ast, acc = []) {
  const visitar = (no) => {
    if (!no || typeof no !== 'object') return;
    if (Array.isArray(no)) {
      no.forEach(visitar);
      return;
    }
    if (typeof no.type !== 'string') return;
    if (no.type === 'CallExpression' && no.callee && no.callee.type === 'Identifier') {
      acc.push({ nome: no.callee.name, linha: no.callee.loc ? no.callee.loc.start.line : 0 });
    }
    for (const k of Object.keys(no)) {
      if (k === 'loc' || k === 'leadingComments' || k === 'trailingComments') continue;
      visitar(no[k]);
    }
  };
  visitar(ast);
  return acc;
}

/** Globais do JS e do DOM — `index.html` nao os declara. */
const GLOBAIS = new Set(
  `require isNaN isFinite parseInt parseFloat eval encodeURI
decodeURI encodeURIComponent decodeURIComponent escape unescape String Number Boolean
Array Object JSON Math Date RegExp Promise Symbol Map Set WeakMap WeakSet Error TypeError
RangeError SyntaxError setTimeout clearTimeout setInterval clearInterval
requestAnimationFrame cancelAnimationFrame fetch alert confirm prompt console
document window navigator location history localStorage sessionStorage indexedDB
caches performance crypto atob btoa structuredClone queueMicrotask Intl URL
URLSearchParams Headers Request Response FormData Blob FileReader AbortController Event
CustomEvent MutationObserver IntersectionObserver ResizeObserver DOMParser
XMLHttpRequest WebSocket Worker Chart jQuery $ getComputedStyle matchMedia
addEventListener removeEventListener dispatchEvent`.split(/\s+/)
);

function ficheirosJS(dir) {
  const out = [];
  let entradas;
  try {
    entradas = readdirSync(dir);
  } catch {
    return out;
  }
  for (const nome of entradas) {
    if (!nome.endsWith('.js')) continue;
    const p = join(dir, nome);
    try {
      if (statSync(p).isFile()) out.push(p);
    } catch {
      /* ignora */
    }
  }
  return out;
}

describe('integridade do JavaScript do dashboard', () => {
  const html = readFileSync(INDEX, 'utf8');
  const inline = corposInline(html);
  const externos = ficheirosJS(JS_DIR);

  it('o template tem scripts inline (sanidade do proprio guard)', () => {
    expect(
      inline.length,
      'nenhum <script> inline encontrado em index.html. Ou o ficheiro foi ' +
        'truncado, ou o dashboard passou a externo — neste caso este guard ' +
        'ja nao serve para nada e tem de ser reescrito.'
    ).toBeGreaterThan(0);
  });

  it('todo o script inline parseia como JavaScript', () => {
    inline.forEach((corpo, i) => {
      expect(() => parseJS(corpo, `index.html bloco ${i + 1}`)).not.toThrow();
    });
  });

  it('nenhuma funcao e chamada sem existir definicao em lado nenhum', () => {
    const declaradosTotal = new Set();

    inline.forEach((corpo, i) => {
      declarados(parseJS(corpo, `index.html bloco ${i + 1}`), declaradosTotal);
    });
    // Os ficheiros em app/static/js tambem contam: o dashboard chama
    // `switchTab` (spa.js), `showToast` (toast.js), `searchAction`
    // (dashboard_appbar.js) e `toggleIAPanel` (ia_panel.js).
    externos.forEach((p) => {
      try {
        declarados(parseJS(readFileSync(p, 'utf8'), p), declaradosTotal);
      } catch {
        /* um ficheiro partido nao apaga o resto da analise */
      }
    });

    const todas = chamadas([]);
    inline.forEach((corpo, i) => {
      chamadas(parseJS(corpo, `index.html bloco ${i + 1}`), todas);
    });

    const primeiras = new Map();
    for (const c of todas) if (!primeiras.has(c.nome)) primeiras.set(c.nome, c.linha);

    const faltam = [...primeiras.entries()]
      .filter(([nome]) => !declaradosTotal.has(nome) && !GLOBAIS.has(nome))
      .sort((a, b) => a[1] - b[1]);

    expect(
      faltam.map(([nome, linha]) => `${nome} (linha ${linha})`),
      'CHAMADAS SEM DEFINICAO. Ou o ficheiro foi truncado — o caso de ' +
        '2026-10-04, em que getPresetOrder/renderWidgetbarPresets ' +
        'desapareceram e a barra de presets ficou vazia sem erro nenhum — ou ' +
        'uma funcao foi renomeada e as chamadas nao acompanharam. O dashboard ' +
        'UM <script> inline: um so ReferenceError aborta o ficheiro ' +
        'inteiro e nada abaixo da linha da queda corre.'
    ).toEqual([]);
  });
});
