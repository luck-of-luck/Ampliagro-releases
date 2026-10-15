import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * O registo de requisitos diz ao produtor o que falta antes de ele escolher.
 *
 * Porque isto precisa de teste
 * ----------------------------
 * A lista cresce quando alguém acrescenta um widget novo, e ninguém se lembra
 * de acrescentar a fonte de dados. Sem teste, o widget volta a ser a caixa
 * vazia que o `generateWidgetContent` desenha — e o produtor lá fica com um
 * buraco no painel sem saber porquê.
 *
 * O que este teste prende
 * -----------------------
 *  1. A avaliação nunca inventa: um requisito em falta é `falta`, não `pronto`.
 *  2. Zero é um valor, não uma ausência: `lancamentos: []` é falta, mas
 *     `total_receitas: 0` também — porque ainda não há lançamentos.
 *  3. Um widget sem registo não é bloqueado (passa a `pronto`).
 *  4. As frases dizem o que fazer, não só o que falta.
 */

const RAIZ = resolve(__dirname, '../..');
const SRC = readFileSync(resolve(RAIZ, 'app/static/js/widget-requisitos.js'), 'utf8');

// Avaliador isolado: corre o ficheiro num `window` mínimo, sem DOM.
function carregar() {
  const win = {};
  new Function('window', SRC)(win);
  return win;
}

describe('registo de requisitos dos widgets', () => {
  it('exporta o registo e o avaliador', () => {
    const w = carregar();
    expect(w.WIDGET_REQUISITOS).toBeTruthy();
    expect(typeof w.avaliarWidgetRequisito).toBe('function');
  });

  it('conta nova: a área está pronta, o financeiro falta', () => {
    const w = carregar();
    const dados = {
      propriedade: { area_total: 209.48 },
      financeiro: { lancamentos: [], receitas: 0, despesas: 0 },
      safras: { items: [] },
    };
    expect(w.avaliarWidgetRequisito('kpi-area', dados).estado).toBe('pronto');
    expect(w.avaliarWidgetRequisito('kpi-caixa', dados).estado).toBe('falta');
    expect(w.avaliarWidgetRequisito('kpi-custo', dados).estado).toBe('falta');
  });

  it('com lançamentos e despesas, o custo por hectare fica pronto', () => {
    const w = carregar();
    const dados = {
      propriedade: { area_total: 100 },
      financeiro: { lancamentos: [{ id: 1 }], despesas: 5000 },
    };
    const r = w.avaliarWidgetRequisito('kpi-custo', dados);
    expect(r.estado).toBe('pronto');
    expect(r.msg).toBe('');
  });

  it('a frase de falta diz o que fazer, e não devolve vazio', () => {
    const w = carregar();
    const todos = Object.entries(w.WIDGET_REQUISITOS);
    for (const [id, reg] of todos) {
      if (!reg.falta) continue;
      const msg = String(reg.falta);
      expect(msg.length, `${id} tem frase`).toBeGreaterThan(10);
      // Frases úteis são imperativas: começam por um verbo de acção.
      expect(
        /^(Cadastre|Registe|Desenhe|Não foi|Ainda não)/i.test(msg),
        `${id}: "${msg}" não diz o que fazer`
      ).toBe(true);
    }
  });

  it('um widget sem registo nunca fica sem dado (passa a pronto)', () => {
    const w = carregar();
    expect(w.avaliarWidgetRequisito('chart-pie', {}).estado).toBe('pronto');
    expect(w.avaliarWidgetRequisito('inexistente-xyz', {}).estado).toBe('pronto');
  });

  it('sensores dependem de uma leitura real, não da existência da lista', () => {
    const w = carregar();
    expect(w.avaliarWidgetRequisito('kpi-sensores', { sensores: [] }).estado).toBe('falta');
    expect(w.avaliarWidgetRequisito('kpi-sensores', { sensores: [{ valor: 65 }] }).estado).toBe(
      'pronto'
    );
  });

  it('um avaliador que rebenta não trava o menu', () => {
    const w = carregar();
    // `financeiro` como número faz `Object.keys` devolver [] — não deve lançar.
    let r;
    expect(() => {
      r = w.avaliarWidgetRequisito('kpi-caixa', { financeiro: 42 });
    }).not.toThrow();
    expect(r.estado).toBe('falta');
  });

  it('todos os ids do registo têm ficha em WIDGET_TYPES', () => {
    const desktop = readFileSync(resolve(RAIZ, 'app/static/js/tabs/dashboard-desktop.js'), 'utf8');
    const i = desktop.indexOf('const WIDGET_TYPES = {');
    const bloco = desktop.slice(i, desktop.indexOf('\n};', i));
    const fichas = new Set([...bloco.matchAll(/'([\w\-]+)':\s*\{/g)].map((m) => m[1]));
    const w = carregar();
    // Se um id do registo não tiver ficha, a paleta nunca o mostra — e a
    // frase de "falta" nunca é lida. É o mesmo erro do registo de 22 widgets.
    const orfaos = Object.keys(w.WIDGET_REQUISITOS).filter((id) => !fichas.has(id));
    expect(orfaos, `ids sem ficha: ${orfaos.join(', ')}`).toEqual([]);
  });
});
