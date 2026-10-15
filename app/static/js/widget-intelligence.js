/**
 * Widget Intelligence System - Core Brain
 * Tracking, suggestions, recents, favorites, AI-powered recommendations
 */
(function () {
  'use strict';

  const STORAGE_KEYS = {
    RECENTS: 'widget-intelligence-recents',
    FAVORITES: 'widget-intelligence-favorites',
    USAGE_STATS: 'widget-intelligence-usage',
    CONTEXT: 'widget-intelligence-context',
  };

  const MAX_RECENTS = 10;
  const MAX_FAVORITES = 20;

  // ==========================================
  // CORE STATE
  // ==========================================
  let state = {
    recents: [],
    favorites: [],
    usageStats: {},
    context: {
      currentCulture: null,
      currentRole: 'produtor',
      timeOfDay: 'morning',
      dashboardType: 'overview',
      hasTelemetry: false,
      hasFinance: false,
      hasAnimals: false,
      hasApiario: false,
    },
  };

  // ==========================================
  // STORAGE
  // ==========================================
  function loadState() {
    try {
      state.recents = JSON.parse(localStorage.getItem(STORAGE_KEYS.RECENTS) || '[]');
      state.favorites = JSON.parse(localStorage.getItem(STORAGE_KEYS.FAVORITES) || '[]');
      state.usageStats = JSON.parse(localStorage.getItem(STORAGE_KEYS.USAGE_STATS) || '{}');
      state.context = JSON.parse(
        localStorage.getItem(STORAGE_KEYS.CONTEXT) || JSON.stringify(state.context)
      );
    } catch (e) {
      console.warn('[WidgetIntelligence] Failed to load state:', e);
    }
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEYS.RECENTS, JSON.stringify(state.recents));
      localStorage.setItem(STORAGE_KEYS.FAVORITES, JSON.stringify(state.favorites));
      localStorage.setItem(STORAGE_KEYS.USAGE_STATS, JSON.stringify(state.usageStats));
      localStorage.setItem(STORAGE_KEYS.CONTEXT, JSON.stringify(state.context));
    } catch (e) {
      console.warn('[WidgetIntelligence] Failed to save state:', e);
    }
  }

  // ==========================================
  // PUBLIC API
  // ==========================================
  window.WidgetIntelligence = {
    // --- Context ---
    setContext(ctx) {
      state.context = { ...state.context, ...ctx };
      saveState();
      this.notifyContextChange();
    },

    getContext() {
      return { ...state.context };
    },

    // --- Recents ---
    addRecent(widgetId, metadata = {}) {
      const existingIndex = state.recents.findIndex((r) => r.id === widgetId);
      const entry = {
        id: widgetId,
        timestamp: Date.now(),
        ...metadata,
      };

      if (existingIndex >= 0) {
        state.recents.splice(existingIndex, 1);
      }
      state.recents.unshift(entry);
      if (state.recents.length > MAX_RECENTS) state.recents = state.recents.slice(0, MAX_RECENTS);
      saveState();
      this.notifyChange('recents');
    },

    getRecents() {
      return [...state.recents];
    },

    // --- Favorites ---
    toggleFavorite(widgetId) {
      const index = state.favorites.indexOf(widgetId);
      if (index >= 0) {
        state.favorites.splice(index, 1);
      } else {
        if (state.favorites.length >= MAX_FAVORITES) {
          state.favorites.pop();
        }
        state.favorites.unshift(widgetId);
      }
      saveState();
      this.notifyChange('favorites');
      return state.favorites.includes(widgetId);
    },

    isFavorite(widgetId) {
      return state.favorites.includes(widgetId);
    },

    getFavorites() {
      return [...state.favorites];
    },

    // --- Usage Tracking ---
    trackUsage(widgetId, action = 'add') {
      if (!state.usageStats[widgetId]) {
        state.usageStats[widgetId] = { count: 0, lastUsed: 0, actions: {} };
      }
      state.usageStats[widgetId].count++;
      state.usageStats[widgetId].lastUsed = Date.now();
      state.usageStats[widgetId].actions[action] =
        (state.usageStats[widgetId].actions[action] || 0) + 1;
      saveState();
    },

    getUsageStats(widgetId) {
      return state.usageStats[widgetId] || { count: 0, lastUsed: 0, actions: {} };
    },

    getMostUsed(limit = 10) {
      return Object.entries(state.usageStats)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, limit)
        .map(([id]) => id);
    },

    // --- Smart Suggestions ---
    getSuggestions(options = {}) {
      const { limit = 8, exclude = [], context = state.context } = options;
      const scores = new Map();

      // 1. Favorites (highest base score)
      state.favorites.forEach((id, idx) => {
        if (!exclude.includes(id)) scores.set(id, (scores.get(id) || 0) + 100 - idx);
      });

      // 2. Recents (time decay)
      const now = Date.now();
      state.recents.forEach((entry, idx) => {
        if (!exclude.includes(entry.id)) {
          const hoursAgo = (now - entry.timestamp) / 36e5;
          const decay = Math.max(0, 50 - hoursAgo * 2);
          scores.set(entry.id, (scores.get(entry.id) || 0) + decay - idx);
        }
      });

      // 3. Most used
      this.getMostUsed(20).forEach((id, idx) => {
        if (!exclude.includes(id)) scores.set(id, (scores.get(id) || 0) + 30 - idx);
      });

      // 4. Context-aware suggestions
      const contextBoosts = this.getContextBoosts(context);
      contextBoosts.forEach((boost, id) => {
        if (!exclude.includes(id)) scores.set(id, (scores.get(id) || 0) + boost);
      });

      // 5. Role-based defaults
      const roleDefaults = this.getRoleWidgets(context.currentRole);
      roleDefaults.forEach((id, idx) => {
        if (!exclude.includes(id)) scores.set(id, (scores.get(id) || 0) + 10 - idx);
      });

      // Sort and return
      return Array.from(scores.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit)
        .map(([id]) => id);
    },

    getContextBoosts(context) {
      const boosts = new Map();
      const culture = context.currentCulture;
      const role = context.currentRole;
      const hasTelemetry = context.hasTelemetry;
      const hasFinance = context.hasFinance;
      const hasAnimals = context.hasAnimals;
      const hasApiario = context.hasApiario;

      // Culture-specific
      if (culture) {
        const cultureWidgets = this.getCultureWidgets(culture);
        cultureWidgets.forEach((id) => boosts.set(id, (boosts.get(id) || 0) + 40));
      }

      // Role-specific
      const roleWidgets = this.getRoleWidgets(role);
      roleWidgets.forEach((id, idx) => boosts.set(id, (boosts.get(id) || 0) + 25 - idx));

      // Data availability
      if (hasTelemetry)
        ['kpi-sensores', 'kpi-clima', 'chart-line', 'alerts-widget'].forEach((id) =>
          boosts.set(id, (boosts.get(id) || 0) + 30)
        );
      if (hasFinance)
        ['kpi-roi', 'kpi-caixa', 'kpi-custo', 'chart-financeiro', 'table-financeiro'].forEach(
          (id) => boosts.set(id, (boosts.get(id) || 0) + 30)
        );
      if (hasAnimals)
        ['kpi-animais', 'list-colheita', 'chart-producao-animal'].forEach((id) =>
          boosts.set(id, (boosts.get(id) || 0) + 25)
        );
      if (hasApiario)
        ['list-colmeias', 'kpi-alertas'].forEach((id) =>
          boosts.set(id, (boosts.get(id) || 0) + 25)
        );

      // Time of day
      if (context.timeOfDay === 'morning')
        ['kpi-clima', 'calendar-widget', 'list-tarefas'].forEach((id) =>
          boosts.set(id, (boosts.get(id) || 0) + 15)
        );
      if (context.timeOfDay === 'evening')
        ['kpi-caixa', 'kpi-alertas', 'widget-resumo'].forEach((id) =>
          boosts.set(id, (boosts.get(id) || 0) + 15)
        );

      return boosts;
    },

    getCultureWidgets(cultureId) {
      if (!window.CULTURE_GROUPS) return [];
      const widgets = [];
      window.CULTURE_GROUPS.forEach((g) => {
        g.cultures.forEach((c) => {
          if (c.id === cultureId || c.id.includes(cultureId)) {
            // Map culture to relevant widget types
            const mapping = {
              cafe: ['kpi-produtividade', 'kpi-area', 'chart-safras', 'chart-area'],
              soja: ['kpi-produtividade', 'kpi-area', 'chart-safras', 'table-safras'],
              milho: ['kpi-produtividade', 'kpi-area', 'chart-safras', 'chart-bar'],
              boi: ['kpi-animais', 'chart-producao-animal', 'list-colheita'],
              leite: ['kpi-animais', 'chart-producao-animal', 'list-colheita'],
            };
            const mapped = mapping[cultureId.replace('cultura-', '')] || [];
            mapped.forEach((id) => widgets.push(id));
          }
        });
      });
      return [...new Set(widgets)];
    },

    getRoleWidgets(role) {
      const roleMap = {
        produtor: ['kpi-roi', 'kpi-custo', 'kpi-caixa', 'widget-executivo', 'chart-financeiro'],
        gerente: [
          'kpi-alertas',
          'kpi-manutencoes',
          'kpi-funcionarios',
          'widget-executivo',
          'list-tarefas',
        ],
        operario: ['list-tarefas', 'list-agenda', 'calendar-widget', 'kpi-clima', 'weather-widget'],
        agronomo: ['kpi-produtividade', 'kpi-area', 'chart-line', 'chart-safras', 'kpi-clima'],
        veterinario: ['kpi-animais', 'list-colheita', 'chart-producao-animal', 'alerts-widget'],
        mecanico: ['kpi-manutencoes', 'list-manutencao', 'alerts-widget'],
        apicultor: ['list-colmeias', 'kpi-alertas', 'kpi-clima', 'weather-widget'],
        servidor: ['widget-executivo', 'kpi-alertas', 'kpi-funcionarios', 'chart-financeiro'],
      };
      return roleMap[role] || roleMap['produtor'];
    },

    // --- Presets ---
    getPresets() {
      return [
        {
          id: 'visao-geral',
          name: 'Visão Geral',
          icon: 'bi-speedometer2',
          description: 'KPIs essenciais para acompanhar a fazenda',
          category: 'Essenciais',
          widgets: [
            'kpi-roi',
            'kpi-custo',
            'kpi-alertas',
            'kpi-sensores',
            'kpi-clima',
            'kpi-caixa',
          ],
          layout: 'grid-2x3',
          tags: ['iniciante', 'executivo', 'dia-a-dia'],
        },
        {
          id: 'financeiro-completo',
          name: 'Financeiro Completo',
          icon: 'bi-graph-up-arrow',
          description: 'Controle total de receitas, custas e fluxo de caixa',
          category: 'Financeiro',
          widgets: [
            'kpi-roi',
            'kpi-custo',
            'kpi-caixa',
            'chart-financeiro',
            'table-financeiro',
            'widget-financeiro',
          ],
          layout: 'grid-mixed',
          tags: ['contabilidade', 'gestao', 'mensal'],
        },
        {
          id: 'campo-producao',
          name: 'Campo & Produção',
          icon: 'bi-geo-alt',
          description: 'Produtividade, área, safras e clima',
          category: 'Agronômico',
          widgets: [
            'kpi-produtividade',
            'kpi-area',
            'kpi-clima',
            'chart-safras',
            'chart-line',
            'widget-campo',
          ],
          layout: 'grid-mixed',
          tags: ['agronomo', 'safra', 'produtividade'],
        },
        {
          id: 'pecuaria',
          name: 'Pecuária',
          icon: 'bi-heart-pulse',
          description: 'Rebanho, produção animal e sanidade',
          category: 'Pecuária',
          widgets: [
            'kpi-animais',
            'chart-producao-animal',
            'list-colheita',
            'kpi-alertas',
            'weather-widget',
          ],
          layout: 'grid-2x3',
          tags: ['veterinario', 'gado', 'leite'],
        },
        {
          id: 'apicultura',
          name: 'Apicultura',
          icon: 'bi-flower1',
          description: 'Colmeias, mel e clima para abelhas',
          category: 'Apicultura',
          widgets: ['list-colmeias', 'kpi-clima', 'kpi-alertas', 'weather-widget', 'chart-line'],
          layout: 'grid-2x3',
          tags: ['apicultor', 'mel', 'abelhas'],
        },
        {
          id: 'manutencao',
          name: 'Manutenção & Frota',
          icon: 'bi-tools',
          description: 'OS, equipamentos e preventivas',
          category: 'Operacional',
          widgets: ['kpi-manutencoes', 'list-manutencao', 'kpi-alertas', 'calendar-widget'],
          layout: 'grid-2x2',
          tags: ['mecanico', 'frota', 'preventiva'],
        },
        {
          id: 'equipe-rh',
          name: 'Equipe & RH',
          icon: 'bi-people',
          description: 'Funcionários, tarefas e agenda',
          category: 'Gestão',
          widgets: [
            'kpi-funcionarios',
            'list-tarefas',
            'list-agenda',
            'calendar-widget',
            'widget-executivo',
          ],
          layout: 'grid-mixed',
          tags: ['gerente', 'rh', 'equipe'],
        },
        {
          id: 'executivo',
          name: 'Visão Executiva',
          icon: 'bi-briefcase',
          description: 'Resumo estratégico para tomada de decisão',
          category: 'Executivo',
          widgets: ['widget-resumo', 'widget-executivo', 'kpi-roi', 'chart-mixed', 'kpi-alertas'],
          layout: 'hero-mixed',
          tags: ['diretor', 'estrategico', 'board'],
        },
      ];
    },

    // --- Events ---
    _listeners: new Set(),
    onChange(listener) {
      this._listeners.add(listener);
    },
    offChange(listener) {
      this._listeners.delete(listener);
    },
    notifyChange(type) {
      this._listeners.forEach((l) => l({ type, state: this.getPublicState() }));
    },
    notifyContextChange() {
      this._listeners.forEach((l) => l({ type: 'context', context: state.context }));
    },

    getPublicState() {
      return {
        recents: this.getRecents(),
        favorites: this.getFavorites(),
        mostUsed: this.getMostUsed(),
        suggestions: this.getSuggestions(),
      };
    },

    // --- Init ---
    init() {
      loadState();
      this.detectContext();
      return this;
    },

    detectContext() {
      // Detect time of day
      const hour = new Date().getHours();
      let timeOfDay = 'morning';
      if (hour >= 12 && hour < 18) timeOfDay = 'afternoon';
      else if (hour >= 18) timeOfDay = 'evening';

      // Detect role from user data
      let currentRole = 'produtor';
      try {
        const userData = JSON.parse(localStorage.getItem('userData') || '{}');
        if (userData.tipo_usuario) currentRole = userData.tipo_usuario;
        if (userData.cargo) currentRole = userData.cargo.toLowerCase();
      } catch (e) {}

      // Detect current culture from URL or localStorage
      let currentCulture = null;
      try {
        const urlParams = new URLSearchParams(window.location.search);
        currentCulture = urlParams.get('cultura') || localStorage.getItem('currentCulture');
      } catch (e) {}

      // Detect data availability
      const hasTelemetry = !!localStorage.getItem('hasTelemetry');
      const hasFinance = !!localStorage.getItem('hasFinance');
      const hasAnimals = !!localStorage.getItem('hasAnimals');
      const hasApiario = !!localStorage.getItem('hasApiario');

      this.setContext({
        currentCulture,
        currentRole,
        timeOfDay,
        hasTelemetry,
        hasFinance,
        hasAnimals,
        hasApiario,
      });
    },
  };

  // Auto-init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.WidgetIntelligence.init());
  } else {
    window.WidgetIntelligence.init();
  }
})();
