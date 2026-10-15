import { describe, it, expect, beforeEach } from 'vitest';
import { useWidgetStore } from '../../src/stores/widgetStore';

/**
 * Apagar o preset que está ACTIVO tem de deixar a tela coerente.
 *
 * O bug: `deletePreset` removia o preset e escrevia `activePreset: 'default'`,
 * mas deixava `widgets` apontando para os widgets do preset apagado. O
 * resultado na tela era o pior dos dois: o cabeçalho dizia "Padrão" enquanto o
 * grid desenhava o layout que o produtor acabou de apagar. Sem erro, sem
 * toast — só um dashboard mentindo sobre o que ele acabou de fazer.
 *
 * E um caso pior: apagar 'default' deixava `activePreset: 'default'` apontando
 * para um preset que não existe mais.
 *
 * Estes testes fixam os três invariantes: `activePreset` tem de existir em
 * `presets`, `widgets` tem de ser o conteúdo do preset ativo, e apagar não
 * pode deixar lixo.
 */

const reset = () =>
  useWidgetStore.setState({
    widgets: [],
    presets: { default: { name: 'default', widgets: [] } },
    activePreset: 'default',
    editing: false,
  });

describe('widgetStore — deletePreset', () => {
  beforeEach(() => {
    localStorage.clear();
    reset();
  });

  it('apagar o preset ativo recarrega os widgets do preset de fallback', () => {
    const store = useWidgetStore.getState();

    store.savePreset('meu');
    store.loadPreset('meu');
    store.updateWidget('stat-receitas', { config: { metric: 'custom' } });
    store.reorderWidgets([
      { id: 'so-este', type: 'StatCard', position: { x: 0, y: 0, w: 1, h: 1 } },
    ]);

    expect(useWidgetStore.getState().activePreset).toBe('meu');
    expect(useWidgetStore.getState().widgets).toHaveLength(1);

    useWidgetStore.getState().deletePreset('meu');

    const after = useWidgetStore.getState();
    expect(after.activePreset).toBe('default');
    // O ponto do teste: `widgets` não pode continuar com o layout apagado.
    expect(after.widgets).toEqual(after.presets.default.widgets);
  });

  it('activePreset sempre aponta para um preset que existe', () => {
    const store = useWidgetStore.getState();
    store.savePreset('temporario');
    store.loadPreset('temporario');
    useWidgetStore.getState().deletePreset('temporario');

    const after = useWidgetStore.getState();
    expect(after.activePreset).not.toBe('temporario');
    expect(after.presets[after.activePreset!]).toBeDefined();
  });

  it('apagar o único preset deixa activePreset nulo, não apontando para o vazio', () => {
    // `default` é o único preset: não há para onde cair. O estado honesto é
    // `activePreset: null` (dashboard sem preset) — e não `activePreset:
    // 'default'` apontando para um preset apagado.
    useWidgetStore.getState().deletePreset('default');

    const after = useWidgetStore.getState();
    expect(after.activePreset).toBeNull();
    expect(after.presets.default).toBeUndefined();
    expect(after.widgets).toEqual([]);
  });

  it('apagar um preset que não está ativo não mexe no que está na tela', () => {
    const store = useWidgetStore.getState();
    store.savePreset('a');
    store.loadPreset('a');
    const widgetsBefore = useWidgetStore.getState().widgets;

    useWidgetStore.getState().deletePreset('outro');

    const after = useWidgetStore.getState();
    expect(after.activePreset).toBe('a');
    expect(after.widgets).toEqual(widgetsBefore);
  });
});

describe('widgetStore — loadPreset', () => {
  beforeEach(() => {
    localStorage.clear();
    reset();
  });

  it('carregar um preset inexistente não quebra nem adota um nome falso', () => {
    useWidgetStore.getState().loadPreset('nao-existe');

    const after = useWidgetStore.getState();
    expect(after.activePreset).not.toBe('nao-existe');
    expect(after.widgets).toEqual(after.presets.default.widgets);
  });
});
