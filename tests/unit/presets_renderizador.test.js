/**
 * `#presets-carousel` TEM UM ESCRITOR — e este ficheiro é o guarda
 *
 * A HISTÓRIA, porque é ela que justifica o contrato
 * -------------------------------------------------
 * Havia DOIS renderizadores para o mesmo sítio:
 *
 *   `renderWidgetbarPresets()`   pagina-index.js:16455   -> <div>
 *   `renderPresetsCarousel()`    widget-bar-intelligent.js:198 -> <button>
 *
 * Ambos faziam `getElementById('presets-carousel')` + `innerHTML =`.
 * **Quem escrevia por último vencia** — e a ordem de execução entre um
 * ficheiro em `base.html` e o script inline do `{% block content %}` depende
 * do browser, não do código.
 *
 * A PRIMEIRA VERSÃO deste ficheiro provava a divergência. Corria verde e
 * estava certo. O diagnóstico, em jsdom:
 *
 *   index.html        -> DIV.preset-block, DIV.preset-block active-preset, ...
 *   widget-bar-int    -> BUTTON.preset-block active-preset, BUTTON...
 *
 * Três diferenças, e as três importavam:
 *
 *   1. **A ordem.** O externo iterava `Object.entries(window.PRESETS)` — a
 *      ordem de inserção do objecto. O dono itera `getPresetOrder()`, que é a
 *      ordem que o produtor ARRASTOU e que foi persistida. O arrastar existia
 *      e o externo desfazia-o.
 *   2. **O preset activo.** O externo marcava o primeiro da lista; o dono
 *      marca o que está em `matrix-active-preset`.
 *   3. **As capacidades.** Só o dono tem arrastar, editar, apagar e
 *      `_presetImutavel`. E só o dono não usa handlers inline — os 4
 *      `onclick=` do externo eram dívida de CSP.
 *
 * A CAUSA FOI CORRIGIDA: `renderPresetsCarousel()` passou a DELEGAR em
 * `window.renderWidgetbarPresets` e deixou de escrever. O `not.toBe` que
 * provava a divergência passou a falhar — que é a forma correcta deste
 * ficheiro avisar que o defeito deixou de existir.
 *
 * O QUE ESTE FICHEIRO É AGORA
 * ---------------------------
 * O mesmo facto pelo outro lado: "são iguais, e têm de continuar a ser". Um
 * `not.toBe` que deixasse de ser verdade ficava ali à espera de alguém o
 * inverter para fazer passar.
 *
 * POR QUE O MÉTODO É JUSTO
 * -----------------------
 * Os dois lados são extraídos e avaliados **pela mesma via**: cortar a função
 * do ficheiro e correr em jsdom. A primeira tentativa correu o IIFE externo
 * inteiro e disparou um `load` sintético, e deu `[]` — o IIFE regista o
 * listener no parse e em jsdom o `load` já tinha acontecido. Um teste que
 * depende da ordem de eventos do browser mede o browser, não o renderizador.
 *
 * O QUE ESTE GUARDA NÃO COBRE
 * ---------------------------
 * As dependências dos dois renderizadores são *stubs*. O que está medido é o
 * DOM que cada função ESCREVE, não o que os previews e os modais fazem a
 * seguir. É o limite honesto deste teste, e está escrito aqui para ninguém o
 * confundir com cobertura de interacção.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
/* O DONO vive em `app/static/js/pagina-index.js`, e é registado em
   `window.renderWidgetbarPresets` pelo mesmo ficheiro (linha ~16888).
   `app/templates/index.html` carrega esse ficheiro e só o chama — não tem a
   função. O caminho errado aqui mostrava "renderWidgetbarPresets() nao existe"
   e 4 vermelhos que não mediam o sistema: mediam o teste a olhar para o sítio
   errado. */
const INDEX = join(RAIZ, 'app', 'static', 'js', 'pagina-index.js');
const EXTERNO = join(RAIZ, 'app', 'static', 'js', 'widget-bar-intelligent.js');

/** Os MESMOS presets para os dois lados. Sem isto, estaríamos a medir outra coisa. */
const PRESETS_DADOS = {
  'base-ia': { label: 'Assistente IA', color: '#0f9d6e', icon: 'bi-stars', widgets: {} },
  'custom-pdemo1': { label: 'Minha Chuva', color: '#3b82f6', icon: 'bi-droplet', widgets: {} },
  'visao-geral': { label: 'Visao Geral', color: '', icon: 'bi-grid', widgets: {} },
};

/** Container limpo e as dependencias minimas dos dois renderizadores. */
function preparar() {
  document.body.innerHTML = '<div id="presets-carousel"></div>';
  const alvo = document.getElementById('presets-carousel');

  localStorage.clear();
  window.PRESETS = JSON.parse(JSON.stringify(PRESETS_DADOS));
  window.presetIconHtml = (p, cor) =>
    `<i class="bi ${p.icon || 'bi-puzzle'}"${cor ? ` style="color:${cor}"` : ''}></i>`;

  // Dependencias do dono (`index.html`). Stubs de proposito: o que se mede e'
  // o DOM que a funcao ESCREVE, nao o que os previews fazem depois.
  const ordem = Object.keys(PRESETS_DADOS);
  window.getPresetOrder = () => ordem.slice();
  window.savePresetOrder = () => {};
  window.sget = (k) => (k === 'matrix-active-preset' ? 'custom-pdemo1' : null);
  window.sset = () => {};
  window._presetImutavel = (k) => k === 'base-ia';
  window.initPresetPreviews = () => {};
  window.showPresetPreview = () => {};
  window.hidePresetPreview = () => {};
  window.applyPreset = () => {};
  window.showToast = () => {};
  window.dashboardLog = () => {};
  window.persistDashboardStateToServer = () => {};
  window.AmpliagroPrefs = { purgePreset: () => {} };
  window.loadPreset = () => {};

  return alvo;
}

/**
 * Corta uma funcao `function nome() {...}` INTEIRA, por contagem de chaves.
 *
 * POR QUE NAO POR REGEX: a versao anterior procurava o proximo
 * `\n\s{0,10}function \w+\s*\(` — e `renderWidgetbarPresets()` tem ONZE
 * funcoes aninhadas (`finish`, `onHoldMove`, `onHoldUp`, `cleanupHold`,
 * `beginFluidDrag`, `onFluidMove`, `rectsOnce`, `findNewIdx`,
 * `movePlaceholderTo`, `onFluidEnd`) com indentacao de 4 a 6 espacos, ou seja
 * DENTRO do `\s{0,10}`. O corte acontecia em `finish(save)` e a funcao
 * extraida parava a meio do dblclick — medir isso nao media o sistema.
 *
 * Chaves dentro de strings ou de comentarios nao contam: `ignore` salta
 * '...' "..." `...` e /*...*\/ para um corpo com regex de cor e cssText.
 */
function extrair(texto, nome) {
  const marca = `function ${nome}(`;
  const inicio = texto.indexOf(marca);
  if (inicio < 0) throw new Error(`${nome}() nao existe`);

  // primeiro `{` depois da assinatura
  let i = texto.indexOf('{', inicio);
  if (i < 0) throw new Error(`${nome}() sem corpo`);

  let profundidade = 0;
  let ignore = null; // ', ", `
  for (; i < texto.length; i++) {
    const c = texto[i];
    const anterior = texto[i - 1];

    if (ignore) {
      if (c === ignore && anterior !== '\\') ignore = null;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') {
      ignore = c;
      continue;
    }
    if (c === '/' && texto[i + 1] === '/') {
      const fim = texto.indexOf('\n', i);
      i = fim < 0 ? texto.length : fim;
      continue;
    }
    if (c === '/' && texto[i + 1] === '*') {
      const fim = texto.indexOf('*/', i);
      i = fim < 0 ? texto.length : fim + 1;
      continue;
    }
    if (c === '{') profundidade++;
    else if (c === '}') {
      profundidade--;
      if (profundidade === 0) return texto.slice(inicio, i + 1);
    }
  }
  throw new Error(`${nome}() nao fecha — chaves desequilibradas`);
}

function correrDoIndex() {
  const html = readFileSync(INDEX, 'utf8');
  const corpo = extrair(html, 'renderWidgetbarPresets');
  const alvo = preparar();
  // `new Function` em vez de `eval` para o corpo nao vazar para o scope.
  new Function(`${corpo}; return renderWidgetbarPresets;`)().call(window);
  return alvo.innerHTML;
}

function correrDoExterno() {
  const src = readFileSync(EXTERNO, 'utf8');
  const alvo = preparar();
  const corpo = extrair(src, 'renderPresetsCarousel');
  // O "avisar uma vez" do externo é um `let` que vive AO LADO da função, no
  // mesmo IIFE. O extrator devolve só a função, portanto sem esta linha o
  // `_delegouSemDono` não existe e o teste mede um ReferenceError em vez do
  // comportamento. Declarar aqui é detalhe do arnês, não do sistema.
  new Function(`let _delegouSemDono = false;\n${corpo}; return renderPresetsCarousel;`)().call(
    window
  );
  return alvo.innerHTML;
}

describe('#presets-carousel tem UM escritor', () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = '';
    delete window.renderWidgetbarPresets;
  });

  it('o externo delega e produz EXACTAMENTE o mesmo DOM que o dono', () => {
    // O dono tem de estar registado em `window` — é isso que o IIFE externo
    // chama. Registamo-lo com a função real do index.html.
    const html = readFileSync(INDEX, 'utf8');
    window.renderWidgetbarPresets = new Function(
      `${extrair(html, 'renderWidgetbarPresets')}; return renderWidgetbarPresets;`
    )();

    const doDono = correrDoIndex();
    const doExterno = correrDoExterno();

    expect(doExterno, 'o renderizador externo voltou a escrever por si').toBe(doDono);
  });

  it('o externo nao escreve nada quando o dono nao esta registado', () => {
    // A degradacao tem de ser VISIVEL, nao silenciosa.
    // `widget-bar-intelligent.js` e' carregado em `base.html`, ou seja em todas
    // as paginas, e `#presets-carousel` so existe no dashboard. Noutra pagina
    // nao ha o que escrever. E no dashboard, se o dono ainda nao tiver
    // registado, tambem nao — porque antes escrevia-se um botao sem arrastar,
    // sem editar e sem apagar, e o produtor achava que era o mesmo.
    const alvo = preparar();
    correrDoExterno();
    expect(alvo.innerHTML).toBe('');
  });

  it('o dono nao usa handlers inline', () => {
    // O que decide a questao da CSP: um `div` com `addEventListener` nao e'
    // divida CSP; um `onclick=` e'. O dono ficou com zero.
    // (Restam 4 `onclick=` no menu de pesquisa deste mesmo ficheiro, e outros
    // nos outros templates: e' a fase 2 da CSP, e `docs/sistema/4.md` mede-os.)
    expect(correrDoIndex()).not.toMatch(/<[^>]+\son[a-z]+\s*=/i);
  });

  it('o dono respeita a ordem persistida', () => {
    // A diferenca funcional que fez o arrastar existir num lado e nao no
    // outro: o dono itera `getPresetOrder()` — a ordem que o produtor arrastou
    // e que foi persistida. O externo iterava `Object.entries(window.PRESETS)`.
    const html = correrDoIndex();
    expect(html).toMatch(/data-preset="base-ia"/);
    expect(html.indexOf('data-preset="base-ia"')).toBeLessThan(
      html.indexOf('data-preset="custom-pdemo1"')
    );
  });

  it('diagnostico: o que o dono escreve', () => {
    const html = correrDoIndex();
    const alvo = preparar();
    alvo.innerHTML = html;
    const filhos = [...alvo.children].map((c) => c.tagName + '.' + c.className);
    console.log('\n  #presets-carousel ->', filhos, '\n');
    expect(filhos.length).toBe(3);
    expect(filhos.every((f) => f.startsWith('DIV'))).toBe(true);
  });
});
