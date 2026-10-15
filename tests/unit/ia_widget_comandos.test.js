import { describe, it, expect, vi } from 'vitest';

describe('comandos locais de widgets', () => {
  it('encaminha recursos e proatividade sem capturar comandos antigos', async () => {
    const { interpretarComandoRecurso: parse } = await import('../../app/static/js/ia-local/ia-local.js');
    expect(parse('liste recursos')).toEqual({ intent: 'recursos_catalogo', params: {} });
    expect(parse('campos de talhoes').params.recurso).toBe('talhoes');
    expect(parse('edite recurso talhoes 12 campos {"area_hectare":4.25}')).toEqual({ intent: 'recurso_alterar', params: { recurso: 'talhoes', id: 12, operacao: 'editar', campos: { area_hectare: 4.25 } } });
    expect(parse('ative copiloto propriedade 4')).toEqual({ intent: 'ligar_proatividade', params: { propriedade_id: 4, ativo: true } });
    expect(parse('desative copiloto propriedade 4').params.ativo).toBe(false);
    expect(parse('liste sensores')).toBeNull();
    expect(parse('edite recurso talhoes 12 campos {invalido}')).toBeNull();
  });
  it('extrai nomes com espaços, destino e posição sem inferência remota', async () => {
    vi.stubGlobal('fetch', vi.fn());
    const { interpretarComandoWidget: parse } =
      await import('../../app/static/js/ia-local/ia-local.js');
    expect(
      parse('mova widget kpi-caixa do preset "Meu caixa" para preset "Custos" posição 2')
    ).toEqual({
      intent: 'widget_alterar',
      params: {
        preset: 'Meu caixa',
        widget: 'kpi-caixa',
        operacao: 'mover',
        destino: 'Custos',
        posicao: 2,
      },
    });
    expect(parse('liste widgets do preset "Custos"')).toEqual({
      intent: 'widget_ler',
      params: { preset: 'Custos' },
    });
    expect(parse('edite widget kpi-caixa do preset "Custos" título "Saldo disponível"')).toEqual({
      intent: 'widget_alterar',
      params: {
        preset: 'Custos',
        widget: 'kpi-caixa',
        operacao: 'editar',
        titulo: 'Saldo disponível',
      },
    });
    expect(parse('exclua widget kpi-caixa do preset "Custos"').params.operacao).toBe('excluir');
    expect(parse('mova widget kpi-caixa')).toBeNull();
    vi.unstubAllGlobals();
  });
});
