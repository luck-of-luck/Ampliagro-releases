import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface WidgetConfig {
  id: string;
  type: string;
  position: { x: number; y: number; w: number; h: number };
  config?: Record<string, any>;
}

interface WidgetPreset {
  name: string;
  widgets: WidgetConfig[];
}

interface WidgetState {
  widgets: WidgetConfig[];
  presets: Record<string, WidgetPreset>;
  activePreset: string | null;
  editing: boolean;
  addWidget: (widget: Omit<WidgetConfig, 'id'>) => void;
  removeWidget: (id: string) => void;
  updateWidget: (id: string, updates: Partial<WidgetConfig>) => void;
  reorderWidgets: (widgets: WidgetConfig[]) => void;
  savePreset: (name: string) => void;
  loadPreset: (name: string) => void;
  deletePreset: (name: string) => void;
  setEditing: (editing: boolean) => void;
  setActivePreset: (name: string | null) => void;
}

const defaultPresets: Record<string, WidgetPreset> = {
  default: {
    name: 'Padrão',
    widgets: [
      { id: 'stat-receitas', type: 'StatCard', position: { x: 0, y: 0, w: 3, h: 2 }, config: { metric: 'receitas' } },
      { id: 'stat-despesas', type: 'StatCard', position: { x: 3, y: 0, w: 3, h: 2 }, config: { metric: 'despesas' } },
      { id: 'stat-lucro', type: 'StatCard', position: { x: 6, y: 0, w: 3, h: 2 }, config: { metric: 'lucro' } },
      { id: 'stat-margem', type: 'StatCard', position: { x: 9, y: 0, w: 3, h: 2 }, config: { metric: 'margem' } },
    ],
  },
  rastreabilidade: {
    name: 'Rastreabilidade',
    widgets: [
      { id: 'alertas-validade', type: 'AlertBanner', position: { x: 0, y: 0, w: 6, h: 3 }, config: { type: 'validade' } },
      { id: 'alertas-ruptura', type: 'AlertBanner', position: { x: 6, y: 0, w: 6, h: 3 }, config: { type: 'ruptura' } },
      { id: 'lotes-recentes', type: 'RastroTable', position: { x: 0, y: 3, w: 12, h: 6 }, config: {} },
    ],
  },
  custos: {
    name: 'Custos',
    widgets: [
      { id: 'custo-chart', type: 'CustoChart', position: { x: 0, y: 0, w: 6, h: 4 }, config: { type: 'doughnut' } },
      { id: 'dre-chart', type: 'CustoChart', position: { x: 6, y: 0, w: 6, h: 4 }, config: { type: 'bar' } },
      { id: 'centros-custo', type: 'CustosTable', position: { x: 0, y: 4, w: 12, h: 5 }, config: {} },
    ],
  },
};

export const useWidgetStore = create<WidgetState>()(
  persist(
    (set) => ({
      widgets: defaultPresets.default.widgets,
      presets: defaultPresets,
      activePreset: 'default',
      editing: false,

      addWidget: (widget) =>
        set((state) => ({
          widgets: [...state.widgets, { ...widget, id: crypto.randomUUID() }],
        })),

      removeWidget: (id) =>
        set((state) => ({
          widgets: state.widgets.filter((w) => w.id !== id),
        })),

      updateWidget: (id, updates) =>
        set((state) => ({
          widgets: state.widgets.map((w) => (w.id === id ? { ...w, ...updates } : w)),
        })),

      reorderWidgets: (widgets) => set({ widgets }),

      savePreset: (name) =>
        set((state) => ({
          presets: {
            ...state.presets,
            [name]: { name, widgets: state.widgets },
          },
        })),

      loadPreset: (name) =>
        set((state) => {
          // Preset inexistente: fica no preset atual em vez de adotar um nome
          // que não existe e esvaziar a tela. Antes, `loadPreset('typo')`
          // deixava `activePreset: 'typo'` com `widgets: []` — o dashboard
          // ficava em branco e o produtor não tinha como saber por quê.
          const preset = state.presets[name];
          if (!preset) return state;
          return { widgets: preset.widgets, activePreset: name };
        }),

      deletePreset: (name) =>
        set((state) => {
          if (!state.presets[name]) return state;
          const { [name]: _removido, ...rest } = state.presets;

          // `activePreset` tem de continuar apontando para um preset que
          // EXISTE. Antes caía sempre em 'default' — que (a) não recebia os
          // widgets do preset padrão, deixando o grid mostrar o layout apagado
          // sob o título "Padrão", e (b) não existia quando o próprio 'default'
          // era o preset apagado, deixando `activePreset` apontando para o
          // vazio.
          const candidatos = Object.keys(rest);
          const fallback = candidatos.includes('default')
            ? 'default'
            : candidatos[0] ?? null;

          const apagouAtivo = state.activePreset === name;
          return {
            presets: rest,
            activePreset: apagouAtivo ? fallback : state.activePreset,
            // Só recarrega quando o preset apagado era o que estava na tela.
            widgets: apagouAtivo
              ? (rest[fallback ?? '']?.widgets ?? [])
              : state.widgets,
          };
        }),

      setEditing: (editing) => set({ editing }),

      setActivePreset: (name) => set({ activePreset: name }),
    }),
    {
      name: 'ampliagro-widgets',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
