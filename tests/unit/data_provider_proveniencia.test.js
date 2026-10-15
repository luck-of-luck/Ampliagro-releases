import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

/**
 * `hasIBGEMapping` — o guarda de proveniencia, e o ponto mais caro do
 * `data-provider.js`.
 *
 * O que faz
 * ---------
 * Decide se uma cultura tem dados REAIS do IBGE SIDRA. E' a funcao que separa
 * "numero de uma fonte" de "numero inventado": se ela disser `true` a uma
 * cultura que o IBGE nao cobre, o produto passa a apresentar um dado sintetico
 * como se fosse medido. Por isso o comportamento aqui nao e' um detalhe — e' a
 * garantia de que nada e' inventado.
 *
 * O custo, medido
 * ---------------
 * O corpo original, quando o id nao casa directamente, fazia DUAS varreduras
 * completas do `PRODUCT_MAP`, e em CADA comparacao voltava a chamar
 * `normalizeNoAccent()` — que faz `toLowerCase()` + `normalize('NFD')` +
 * um `replace` com regex. `PRODUCT_MAP` tem ~300 chaves e o `index.html` chama
 * isto por cultura (ate 488), varias vezes por cultura. O trabalho repetido
 * e' quadratico no tamanho do mapa.
 *
 * Estes testes travam as DUAS coisas:
 *   1. equivalencia — o mesmo id devolve o mesmo booleano que a versao
 *      original, que esta reimplementada abaixo como referencia;
 *   2. custo — o numero de normalizacoes nao cresce com o numero de chamadas
 *      repetidas sobre o mesmo id.
 *
 * O segundo teste e' o que impede a otimizacao de voltar a ser desfeita por
 * alguem que leia "duas varreduras num mapa de 300 chaves" e ache razoavel.
 */

const RAIZ = resolve(__dirname, '../..');
const FONTE = readFileSync(resolve(RAIZ, 'app/static/js/data-provider.js'), 'utf-8');

/** O PRODUCT_MAP real do adapter, para que o teste nao use um mapa inventado. */
const ADAPTER = readFileSync(
  resolve(RAIZ, 'app/static/js/adapters/ibge-adapter.js'),
  'utf-8',
);

/**
 * `BREED_TO_SPECIES` e' interno ao IIFE e nao e' exportado. Extrai-se do
 * proprio fonte em vez de reescrito: uma copia desatualizada aqui compararia o
 * codigo com uma verdade que ja nao e' a dele, e o teste passaria a proteger a
 * coisa errada — que e' pior do que nao ter teste.
 */
const BREEDS = vm.runInNewContext(
  '(' + FONTE.match(/var BREED_TO_SPECIES = (\{[\s\S]*?\});/)[1] + ')',
);

/**
 * A versao ORIGINAL de `hasIBGEMapping`, copiada da linha 34 antes da
 * mudanca. E' a referencia de equivalencia: a otimizacao pode mudar o custo,
 * nunca a resposta.
 */
function referenciaOriginal(id, PRODUCT_MAP, BREED_TO_SPECIES, normalizeNoAccent) {
  if (!PRODUCT_MAP) return false;
  if (PRODUCT_MAP[id]) return true;
  const norm = normalizeNoAccent(id);
  const short = norm.split('-').pop();
  if (BREED_TO_SPECIES[short] && PRODUCT_MAP['cultura-' + BREED_TO_SPECIES[short]])
    return true;
  if (PRODUCT_MAP['cultura-' + short]) return true;
  const stripped = norm
    .replace('cult-', '')
    .replace('graos-', '')
    .replace('frutas-', '')
    .replace('hortalicas-', '')
    .replace('leguminosas-', '')
    .replace('bovinos-', '')
    .replace('suinos-', '')
    .replace('aves-', '')
    .replace('peixes-', '')
    .replace('crustaceos-', '');
  if (PRODUCT_MAP['cultura-' + stripped]) return true;
  if (PRODUCT_MAP[stripped]) return true;
  const keys = Object.keys(PRODUCT_MAP);
  for (let i = 0; i < keys.length; i++)
    if (normalizeNoAccent(keys[i]).indexOf(short) >= 0) return true;
  if (BREED_TO_SPECIES[short]) {
    const esp = BREED_TO_SPECIES[short];
    for (let j = 0; j < keys.length; j++)
      if (normalizeNoAccent(keys[j]).indexOf(esp) >= 0) return true;
  }
  return false;
}

function normalizeNoAccent(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .trim();
}

/**
 * Um `window` minimo e' autorreferencial (`w.window === w`), como num
 * browser.
 *
 * Os scripts sao avaliados no global do jsdom (`runInThisContext`) e nao num
 * `vm` separado por duas razoes:
 *
 *  1. o contador de custo conta `String.prototype.normalize`. Num contexto `vm`
 *     o `String` e' outro, e a instrumentacao nao contaria nada — o teste
 *     passaria a medir zero, que e' sempre "verde" e nunca quer dizer nada;
 *  2. `index.html` carrega estes scripts no mesmo global, e e' esse o ambiente
 *     cujo custo interessa.
 *
 * Os singletons sao apagados entre testes: `IBGEAdapter` preso de um teste
 * para o seguinte faria o caso "sem adapter" mentir.
 */
function carregar({ comAdapter = true } = {}) {
  vm.runInThisContext(
    'globalThis.IBGEAdapter = undefined; globalThis.CultureData = undefined;'
  );
  if (comAdapter) vm.runInThisContext(ADAPTER);
  vm.runInThisContext(FONTE);
  return globalThis;
}

afterEach(() => {
  vm.runInThisContext(
    'globalThis.IBGEAdapter = undefined; globalThis.CultureData = undefined;'
  );
});

/** Todos os ids do mapa + alguns que so' batem por sufixo/raca. */
function idsDeTeste(PRODUCT_MAP) {
  const ids = Object.keys(PRODUCT_MAP);
  ids.push('cult-graos-soja', 'cultura-frutas-banana', 'soja', 'nelore');
  ids.push('angus', 'nao-existe-mesmo', '', 'cult-peixes-tilapia');
  return ids;
}

describe('hasIBGEMapping — proveniencia', () => {
  it('nao aceita adaptacao: o mapa e' + ' o do IBGEAdapter real', () => {
    const w = carregar();
    expect(w.IBGEAdapter).toBeTruthy();
    expect(Object.keys(w.IBGEAdapter.PRODUCT_MAP).length).toBeGreaterThan(50);
  });

  it('devolve exatamente o que a versao original devolvia', () => {
    const w = carregar();
    const mapa = w.IBGEAdapter.PRODUCT_MAP;

    for (const id of idsDeTeste(mapa)) {
      const obtido = w.CultureData.hasIBGEMapping(id);
      const esperado = referenciaOriginal(id, mapa, BREEDS, normalizeNoAccent);
      expect({ id, obtido }).toEqual({ id, obtido: esperado });
    }
  });

  it('sem adapter, nao ha mapeamento (e nao ha excecao)', () => {
    const w = carregar({ comAdapter: false });
    expect(w.IBGEAdapter).toBeUndefined();
    expect(w.CultureData.hasIBGEMapping('soja')).toBe(false);
  });

  it('um id directo do mapa e' + ' aceito', () => {
    const w = carregar();
    const primeiro = Object.keys(w.IBGEAdapter.PRODUCT_MAP)[0];
    expect(w.CultureData.hasIBGEMapping(primeiro)).toBe(true);
  });
});

describe('hasIBGEMapping — custo', () => {
  let normalizacoes;
  let original;

  beforeEach(() => {
    // `normalizeNoAccent` chama `String.prototype.normalize('NFD')`. Contar
    // essas chamadas e' contar o trabalho que a funcao refaz a cada
    // invocacao — e' a metrica que a otimizacao tem de mexer.
    normalizacoes = 0;
    original = String.prototype.normalize;
    String.prototype.normalize = function (form) {
      normalizacoes += 1;
      return original.call(this, form);
    };
  });

  afterEach(() => {
    String.prototype.normalize = original;
  });

  it('repetir o MESMO id nao repete o trabalho', () => {
    const w = carregar();
    const mapa = w.IBGEAdapter.PRODUCT_MAP;
    // Um id que NAO casa directamente: e' o caminho que faz as varreduras.
    const id = 'cult-graos-soja-inexistente';

    w.CultureData.hasIBGEMapping(id);
    const primeira = normalizacoes;

    for (let i = 0; i < 50; i++) w.CultureData.hasIBGEMapping(id);

    // 50 repeticoes nao podem custar trabalho novo.
    expect(normalizacoes).toBe(primeira);
  });

  it('o custo nao cresce com o numero de ids repetidos', () => {
    const w = carregar();
    const ids = idsDeTeste(w.IBGEAdapter.PRODUCT_MAP);

    // 1 passada
    for (const id of ids) w.CultureData.hasIBGEMapping(id);
    const umaPassada = normalizacoes;

    // 5 passadas
    for (let p = 0; p < 5; p++) for (const id of ids) w.CultureData.hasIBGEMapping(id);
    const cincoPassadas = normalizacoes;

    // Se nao houver memoizacao, 6 passadas custam ~6x uma. Com memoizacao, as
    // 5 passadas a mais nao custam praticamente nada.
    expect(cincoPassadas).toBeLessThan(umaPassada * 1.5);
  });
});