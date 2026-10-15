import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

/**
 * A composicao de widgets que o handler anexa a resposta. Fase 1, lado do
 * browser.
 *
 * O que se prova aqui e' o que o Python nao pode provar: que o que o servidor
 * manda e' lido, filtrado e dado a desenhar. Sem este ficheiro, o servidor pode
 * produzir `widget_composicao` a horas e nenhuma mesa aparece — que e' o mesmo
 * vazio da `out["copiloto"]`, o campo que ninguem lia.
 */
describe('normalizaComposicao', () => {
  beforeAll(() => {
    global.window = {
      fetch: () => Promise.resolve(),
      document: { cookie: '' },
    };
    global.document = { cookie: '' };

    const codePath = path.resolve(__dirname, '../../app/static/js/ia-local/palco-amplia.js');
    eval(fs.readFileSync(codePath, 'utf-8'));
  });

  const N = () => window.AmpliaPalco.normalizaComposicao;

  it('esta exportada', () => {
    expect(N()).toBeTypeOf('function');
  });

  it('aceita a lista que o servidor manda', () => {
    const saida = N()([{ tipo: 'kpi-custo', titulo: 'Custo' }]);
    expect(saida).toEqual([{ tipo: 'kpi-custo', titulo: 'Custo' }]);
  });

  it('aceita o envelope {"widgets": [...]}', () => {
    const saida = N()({ widgets: [{ tipo: 'chart-safras' }] });
    expect(saida).toEqual([{ tipo: 'chart-safras' }]);
  });

  it('o que nao e lista da lista vazia, nunca lanca', () => {
    for (const ruim of [undefined, null, 42, 'kpi-custo', {}, { nada: 1 }, true]) {
      expect(N()(ruim)).toEqual([]);
    }
  });

  it('descarta o que nao tem tipo', () => {
    expect(N()([{ titulo: 'sem tipo' }, { tipo: '' }, 'texto', 42, null])).toEqual([]);
  });

  it('descarta um id que nao pode ser widget', () => {
    /* Um id com espaco ou ponto nao vira classe nem endpoint. O servidor tambem
     * recusa (palco.widget_permitido), mas um `tipo` malformado que passe a
     * chegar ao DOM e' o tipo de coisa que o `textContent` sozinho nao segura. */
    const saida = N()([
      { tipo: 'kpi custo' },
      { tipo: '<script>' },
      { tipo: 'kpi.ok' },
      { tipo: 'chart-safras' },
    ]);
    expect(saida).toEqual([{ tipo: 'chart-safras' }]);
  });

  it('corta o titulo em 120 caracteres', () => {
    const saida = N()([{ tipo: 'kpi-custo', titulo: 'x'.repeat(400) }]);
    expect(saida[0].titulo.length).toBe(120);
  });

  it('descarta config que nao e objecto', () => {
    const saida = N()([{ tipo: 'kpi-custo', config: ['a'] }, { tipo: 'kpi-caixa' }]);
    expect(saida).toEqual([{ tipo: 'kpi-custo' }, { tipo: 'kpi-caixa' }]);
  });

  it('deduplica por tipo', () => {
    const saida = N()([
      { tipo: 'kpi-custo', titulo: 'primeiro' },
      { tipo: 'kpi-custo', titulo: 'segundo' },
    ]);
    expect(saida).toHaveLength(1);
    expect(saida[0].titulo).toBe('primeiro');
  });

  it('corta no mesmo teto do servidor (8)', () => {
    const muitos = Array.from({ length: 30 }, (_, i) => ({ tipo: `t${i}` }));
    expect(N()(muitos)).toHaveLength(8);
  });

  it('nao deixa passar nenhuma chave extra', () => {
    const saida = N()([{ tipo: 'kpi-custo', valor: 12345, handler: 'x', dados: {} }]);
    expect(saida).toEqual([{ tipo: 'kpi-custo' }]);
    expect(saida[0]).not.toHaveProperty('valor');
  });
});
