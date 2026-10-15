/**
 * Widget Command Palette - Universal Ctrl+K Interface
 * Fuzzy search, actions, navigation, widget adding - all in one
 */
(function () {
  'use strict';

  const _highlightCache = new Map();

  const state = {
    isOpen: false,
    query: '',
    selectedIndex: 0,
    results: [],
    categories: [],
    recentActions: [],
    keyboardNavigation: true,
  };

  const MAX_RESULTS = 12;

  // ==========================================
  // COMMAND REGISTRY
  // ==========================================
  const COMMANDS = [
    // Navigation
    {
      id: 'nav-dashboard',
      title: 'Ir para Dashboard',
      subtitle: 'Visão geral da fazenda',
      icon: 'bi-speedometer2',
      shortcut: 'Ctrl+1',
      category: 'Navegação',
      action: () => navigate('/'),
    },
    {
      id: 'nav-financeiro',
      title: 'Ir para Financeiro',
      subtitle: 'Contas, fluxo de caixa, relatórios',
      icon: 'bi-cash-stack',
      shortcut: 'Ctrl+2',
      category: 'Navegação',
      action: () => navigate('/financeiro/'),
    },
    {
      id: 'nav-campo',
      title: 'Ir para Campo',
      subtitle: 'Talhões, culturas, operações',
      icon: 'bi-geo-alt',
      shortcut: 'Ctrl+3',
      category: 'Navegação',
      action: () => navigate('/campo/'),
    },
    {
      id: 'nav-estoque',
      title: 'Ir para Estoque',
      subtitle: 'Insumos, produtos, inventário',
      icon: 'bi-box-seam',
      shortcut: 'Ctrl+4',
      category: 'Navegação',
      action: () => navigate('/estoque/'),
    },
    {
      id: 'nav-animais',
      title: 'Ir para Animais',
      subtitle: 'Rebanho, sanidade, produção',
      icon: 'bi-heart-pulse',
      shortcut: 'Ctrl+5',
      category: 'Navegação',
      action: () => navigate('/animais/'),
    },
    {
      id: 'nav-apiario',
      title: 'Ir para Apiário',
      subtitle: 'Colmeias, mel, manejos',
      icon: 'bi-flower1',
      shortcut: 'Ctrl+6',
      category: 'Navegação',
      action: () => navigate('/apiario/'),
    },
    {
      id: 'nav-maquinarios',
      title: 'Ir para Máquinas',
      subtitle: 'Frota, manutenção, OS',
      icon: 'bi-truck',
      shortcut: 'Ctrl+7',
      category: 'Navegação',
      action: () => navigate('/maquinarios/'),
    },
    {
      id: 'nav-funcionarios',
      title: 'Ir para Equipe',
      subtitle: 'Funcionários, tarefas, agenda',
      icon: 'bi-people',
      shortcut: 'Ctrl+8',
      category: 'Navegação',
      action: () => navigate('/funcionarios/'),
    },

    // Widget Actions
    {
      id: 'widget-add',
      title: 'Adicionar Widget',
      subtitle: 'Abrir paleta de widgets',
      icon: 'bi-plus-lg',
      shortcut: 'Ctrl+Shift+W',
      category: 'Widgets',
      action: () => window.openAddWidgetModal?.(),
    },
    {
      id: 'widget-preset',
      title: 'Aplicar Preset',
      subtitle: 'Escolher layout pré-definido',
      icon: 'bi-layout-three-columns',
      shortcut: 'Ctrl+Shift+P',
      category: 'Widgets',
      action: () => window.openPresetModal?.(),
    },
    {
      id: 'widget-restore',
      title: 'Restaurar Meu Layout',
      subtitle: 'Voltar ao layout salvo',
      icon: 'bi-arrow-counterclockwise',
      shortcut: 'Ctrl+Shift+R',
      category: 'Widgets',
      action: () => window.restoreWidgetsLayout?.(),
    },
    {
      id: 'widget-clear',
      title: 'Limpar Todos Widgets',
      subtitle: 'Remover tudo do dashboard',
      icon: 'bi-trash3',
      shortcut: '',
      category: 'Widgets',
      action: () => {
        if (confirm('Remover todos os widgets?')) window.clearAllWidgets?.();
      },
    },
    {
      id: 'widget-edit',
      title: 'Editar Widget Selecionado',
      subtitle: 'Configurar widget ativo',
      icon: 'bi-pencil-square',
      shortcut: 'Enter',
      category: 'Widgets',
      action: () => window.openEditSelectedWidget?.(),
    },

    // Data Actions
    {
      id: 'data-export',
      title: 'Exportar Dashboard',
      subtitle: 'Baixar CSV com dados atuais',
      icon: 'bi-download',
      shortcut: 'Ctrl+E',
      category: 'Dados',
      action: () => window.exportDashboardData?.(),
    },
    {
      id: 'data-sync',
      title: 'Sincronizar Agora',
      subtitle: 'Forçar sync com servidor',
      icon: 'bi-arrow-repeat',
      shortcut: 'Ctrl+S',
      category: 'Dados',
      action: () => window.forceSync?.(),
    },
    {
      id: 'data-backup',
      title: 'Backup Completo (.agro)',
      subtitle: 'Exportar snapshot do sistema',
      icon: 'bi-file-earmark-zip',
      shortcut: '',
      category: 'Dados',
      action: () => window.exportSystemSnapshot?.(),
    },
    {
      id: 'data-restore',
      title: 'Restaurar Backup',
      subtitle: 'Importar snapshot .agro',
      icon: 'bi-file-earmark-arrow-up',
      shortcut: '',
      category: 'Dados',
      action: () => window.importSystemSnapshot?.(),
    },

    // Tools
    {
      id: 'tool-calc',
      title: 'Calculadoras Agronômicas',
      subtitle: 'Pulverização, Pearson, NPK, Biometria',
      icon: 'bi-calculator',
      shortcut: 'Ctrl+Shift+C',
      category: 'Ferramentas',
      action: () => window.openCalculatorModal?.(),
    },
    {
      id: 'tool-spreadsheet',
      title: 'Entrada Rápida (Planilha)',
      subtitle: 'Registros em lote via tab/enter',
      icon: 'bi-table',
      shortcut: 'Ctrl+Shift+E',
      category: 'Ferramentas',
      action: () => window.openQuickSpreadsheet?.(),
    },
    {
      id: 'tool-products',
      title: 'Produtos & Preços',
      subtitle: 'Cadastro e tabela de preços',
      icon: 'bi-box-seam',
      shortcut: '',
      category: 'Ferramentas',
      action: () => window.openProductRegistry?.(),
    },
    {
      id: 'tool-notebook',
      title: 'Caderno de Campo',
      subtitle: 'Registros, impressão, PDF',
      icon: 'bi-journal-text',
      shortcut: 'Ctrl+Shift+N',
      category: 'Ferramentas',
      action: () => window.openFieldNotebook?.(),
    },
    {
      id: 'tool-simulator',
      title: 'Simulador de Lucro',
      subtitle: 'Cenários, break-even, sensibilidade',
      icon: 'bi-graph-up-arrow',
      shortcut: '',
      category: 'Ferramentas',
      action: () => navigate('/simulador/lucro/'),
    },
    {
      id: 'tool-experiment',
      title: 'Experimento A/B',
      subtitle: 'Testes estatísticos NDVI/produtividade',
      icon: 'bi-diagram-3',
      shortcut: '',
      category: 'Ferramentas',
      action: () => navigate('/experimento/'),
    },

    // AI & Smart
    {
      id: 'ai-suggest',
      title: 'Sugestões Inteligentes',
      subtitle: 'Widgets recomendados para seu contexto',
      icon: 'bi-magic',
      shortcut: 'Ctrl+Shift+A',
      category: 'IA',
      action: () => window.showAISuggestions?.(),
    },
    {
      id: 'ai-report',
      title: 'Gerar Relatório PDF',
      subtitle: 'Relatório 1-clique com gráficos e QR',
      icon: 'bi-file-earmark-pdf',
      shortcut: 'Ctrl+Shift+R',
      category: 'IA',
      action: () => window.generatePDFReport?.(),
    },
    {
      id: 'ai-voice',
      title: 'AmplIA - Voz no Campo',
      subtitle: 'Comandos de voz offline-first',
      icon: 'bi-mic',
      shortcut: 'Ctrl+Shift+V',
      category: 'IA',
      action: () => window.toggleAmplia?.(),
    },

    // Settings
    {
      id: 'settings-theme',
      title: 'Personalizar Tema',
      subtitle: 'Cores, modo escuro, widgetbar',
      icon: 'bi-palette',
      shortcut: 'Ctrl+,',
      category: 'Configurações',
      action: () => window.openCustomThemeModal?.(),
    },
    {
      id: 'settings-profile',
      title: 'Meu Perfil',
      subtitle: 'Conta, preferências, notificações',
      icon: 'bi-person-circle',
      shortcut: '',
      category: 'Configurações',
      action: () => navigate('/perfil/'),
    },
    {
      id: 'settings-help',
      title: 'Ajuda & Atalhos',
      subtitle: 'Documentação e teclas de atalho',
      icon: 'bi-question-circle',
      shortcut: 'F1',
      category: 'Configurações',
      action: () => window.showHelp?.(),
    },
    {
      id: 'settings-keyboard',
      title: 'Mapa de Atalhos',
      subtitle: 'Todos os atalhos do sistema',
      icon: 'bi-keyboard',
      shortcut: 'Ctrl+/',
      category: 'Configurações',
      action: () => window.showKeyboardMap?.(),
    },

    // System
    {
      id: 'sys-fullscreen',
      title: 'Alternar Tela Cheia',
      subtitle: 'Modo imersivo',
      icon: 'bi-fullscreen',
      shortcut: 'F11',
      category: 'Sistema',
      action: () => toggleFullscreen(),
    },
    {
      id: 'sys-compact',
      title: 'Modo Compacto',
      subtitle: 'Widgetbar reduzida',
      icon: 'bi-arrows-angle-contract',
      shortcut: 'Ctrl+Shift+M',
      category: 'Sistema',
      action: () => window.toggleCompactMode?.(),
    },
    {
      id: 'sys-devtools',
      title: 'Ferramentas de Dev',
      subtitle: 'Debug, logs, performance',
      icon: 'bi-bug',
      shortcut: 'F12',
      category: 'Sistema',
      action: () => window.openDevTools?.(),
    },
  ];

  // ==========================================
  // FUZZY SEARCH
  // ==========================================
  function fuzzyScore(query, text) {
    if (!query) return 1;
    query = query.toLowerCase();
    text = text.toLowerCase();

    let score = 0;
    let queryIdx = 0;
    let lastMatchIdx = -1;

    for (let i = 0; i < text.length && queryIdx < query.length; i++) {
      if (text[i] === query[queryIdx]) {
        const bonus = i === 0 || text[i - 1] === ' ' || text[i - 1] === '-' ? 10 : 1;
        const proximity = lastMatchIdx >= 0 ? Math.max(0, 5 - (i - lastMatchIdx)) : 0;
        score += bonus + proximity;
        lastMatchIdx = i;
        queryIdx++;
      }
    }

    if (queryIdx < query.length) return 0; // Not all chars matched

    // Bonus for exact prefix match
    if (text.startsWith(query)) score += 50;

    return score / text.length;
  }

  function searchCommands(query) {
    if (!query.trim()) {
      // Return recents + favorites + top commands
      const recents = getRecentCommands();
      const favorites = getFavoriteCommands();
      const top = COMMANDS.filter(
        (c) => !recents.some((r) => r.id === c.id) && !favorites.some((f) => f.id === c.id)
      ).slice(0, 8);
      return [...recents, ...favorites, ...top].slice(0, MAX_RESULTS);
    }

    const scored = COMMANDS.map((cmd) => {
      const titleScore = fuzzyScore(query, cmd.title) * 3;
      const subtitleScore = fuzzyScore(query, cmd.subtitle || '') * 1.5;
      const categoryScore = fuzzyScore(query, cmd.category || '') * 1;
      const shortcutScore = (cmd.shortcut && fuzzyScore(query, cmd.shortcut) * 2) || 0;
      const idScore = fuzzyScore(query, cmd.id) * 0.5;

      // Usage boost
      const usage = window.WidgetIntelligence?.getUsageStats?.(cmd.id) || { count: 0 };
      const usageBoost = Math.min(usage.count * 0.5, 10);

      return {
        ...cmd,
        score: titleScore + subtitleScore + categoryScore + shortcutScore + idScore + usageBoost,
        matchedTitle: highlightMatch(cmd.title, query),
        matchedSubtitle: cmd.subtitle ? highlightMatch(cmd.subtitle, query) : '',
      };
    });

    return scored
      .filter((r) => r.score > 0.01)
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_RESULTS);
  }

  function highlightMatch(text, query) {
    if (!query) return text;
    let re = _highlightCache.get(query);
    if (!re) {
      if (_highlightCache.size > 200) _highlightCache.clear();
      re = new RegExp(`(${query.split('').join('.*?')})`, 'i');
      _highlightCache.set(query, re);
    }
    const parts = text.split(re);
    return parts.map((part, i) => (i % 2 === 1 ? `<mark>${part}</mark>` : part)).join('');
  }

  // ==========================================
  // RECENTS & FAVORITES (Command-specific)
  // ==========================================
  function getRecentCommands() {
    try {
      return JSON.parse(localStorage.getItem('command-palette-recents') || '[]')
        .map((id) => COMMANDS.find((c) => c.id === id))
        .filter(Boolean)
        .slice(0, 4);
    } catch (e) {
      return [];
    }
  }

  function getFavoriteCommands() {
    try {
      return JSON.parse(localStorage.getItem('command-palette-favorites') || '[]')
        .map((id) => COMMANDS.find((c) => c.id === id))
        .filter(Boolean);
    } catch (e) {
      return [];
    }
  }

  function addRecentCommand(id) {
    try {
      let recents = JSON.parse(localStorage.getItem('command-palette-recents') || '[]');
      recents = [id, ...recents.filter((x) => x !== id)].slice(0, 10);
      localStorage.setItem('command-palette-recents', JSON.stringify(recents));
    } catch (e) {}
  }

  function toggleFavoriteCommand(id) {
    try {
      let favs = JSON.parse(localStorage.getItem('command-palette-favorites') || '[]');
      const idx = favs.indexOf(id);
      if (idx >= 0) favs.splice(idx, 1);
      else favs.unshift(id);
      localStorage.setItem('command-palette-favorites', JSON.stringify(favs.slice(0, 10)));
      render();
    } catch (e) {}
  }

  function isFavoriteCommand(id) {
    try {
      return JSON.parse(localStorage.getItem('command-palette-favorites') || '[]').includes(id);
    } catch (e) {
      return false;
    }
  }

  // ==========================================
  // RENDER
  // ==========================================
  function render() {
    const resultsEl = document.getElementById('command-palette-results');
    if (!resultsEl) return;

    const grouped = groupByCategory(state.results);
    let html = '';

    for (const [category, commands] of Object.entries(grouped)) {
      html += `<div class="cp-category"><span class="cp-category-label">${category}</span>`;
      commands.forEach((cmd, idx) => {
        const globalIdx = state.results.indexOf(cmd);
        const isSelected = globalIdx === state.selectedIndex;
        const fav = isFavoriteCommand(cmd.id);
        html += `
                    <div class="cp-item ${isSelected ? 'selected' : ''}" data-index="${globalIdx}" data-id="${cmd.id}" role="option" aria-selected="${isSelected}">
                        <div class="cp-item-main">
                            <span class="cp-item-icon"><i class="bi ${cmd.icon}"></i></span>
                            <div class="cp-item-text">
                                <span class="cp-item-title">${cmd.matchedTitle || cmd.title}</span>
                                ${cmd.matchedSubtitle ? `<span class="cp-item-subtitle">${cmd.matchedSubtitle}</span>` : ''}
                            </div>
                        </div>
                        <div class="cp-item-meta">
                            ${cmd.shortcut ? `<kbd class="cp-shortcut">${cmd.shortcut}</kbd>` : ''}
                            <button class="cp-fav-btn ${fav ? 'active' : ''}" data-id="${cmd.id}" title="${fav ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}">
                                <i class="bi ${fav ? 'bi-star-fill' : 'bi-star'}"></i>
                            </button>
                        </div>
                    </div>
                `;
      });
      html += '</div>';
    }

    if (state.results.length === 0) {
      html = `<div class="cp-empty"><i class="bi bi-search"></i><p>Nenhum comando encontrado</p><small>Tente termos como "widget", "financeiro", "exportar"</small></div>`;
    }

    resultsEl.innerHTML = html;

    // Scroll selected into view
    const selectedEl = resultsEl.querySelector('.cp-item.selected');
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function groupByCategory(commands) {
    const grouped = {};
    commands.forEach((cmd) => {
      if (!grouped[cmd.category]) grouped[cmd.category] = [];
      grouped[cmd.category].push(cmd);
    });
    // Sort categories: Navegação, Widgets, Dados, Ferramentas, IA, Configurações, Sistema
    const order = [
      'Navegação',
      'Widgets',
      'Dados',
      'Ferramentas',
      'IA',
      'Configurações',
      'Sistema',
    ];
    const sorted = {};
    order.forEach((cat) => {
      if (grouped[cat]) sorted[cat] = grouped[cat];
    });
    Object.keys(grouped)
      .filter((c) => !order.includes(c))
      .forEach((cat) => {
        sorted[cat] = grouped[cat];
      });
    return sorted;
  }

  // ==========================================
  // UI STATE
  // ==========================================
  function open() {
    const modal = document.getElementById('command-palette');
    const panel = document.getElementById('command-palette-panel');
    const input = document.getElementById('command-palette-input');

    if (!modal || !panel) return;

    state.isOpen = true;
    state.query = '';
    state.selectedIndex = 0;
    state.results = searchCommands('');
    render();

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    requestAnimationFrame(() => {
      modal.querySelector('div[onclick]').classList.remove('scale-95', 'opacity-0');
      modal.querySelector('div[onclick]').classList.add('scale-100', 'opacity-100');
    });

    setTimeout(() => input?.focus(), 50);
    document.body.style.overflow = 'hidden';

    // Track
    window.WidgetIntelligence?.trackUsage?.('command-palette', 'open');
  }

  function close() {
    const modal = document.getElementById('command-palette');
    const panel = document.getElementById('command-palette-panel');
    if (!modal || !panel) return;

    panel.classList.remove('scale-100', 'opacity-100');
    panel.classList.add('scale-95', 'opacity-0');
    setTimeout(() => {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      document.body.style.overflow = '';
    }, 200);

    state.isOpen = false;
    state.query = '';
    document.getElementById('command-palette-input').value = '';
  }

  function executeSelected() {
    const cmd = state.results[state.selectedIndex];
    if (!cmd) return;

    addRecentCommand(cmd.id);
    window.WidgetIntelligence?.trackUsage?.(cmd.id, 'execute');
    close();
    setTimeout(() => cmd.action?.(), 50);
  }

  // ==========================================
  // KEYBOARD HANDLING
  // ==========================================
  function handleKeydown(e) {
    if (!state.isOpen) return;

    switch (e.key) {
      case 'Escape':
        e.preventDefault();
        close();
        break;
      case 'ArrowDown':
        e.preventDefault();
        state.selectedIndex = Math.min(state.selectedIndex + 1, state.results.length - 1);
        render();
        break;
      case 'ArrowUp':
        e.preventDefault();
        state.selectedIndex = Math.max(state.selectedIndex - 1, 0);
        render();
        break;
      case 'Enter':
        e.preventDefault();
        executeSelected();
        break;
      case 'Tab':
        e.preventDefault();
        // Cycle through categories
        break;
    }
  }

  function handleInput(e) {
    state.query = e.target.value;
    state.selectedIndex = 0;
    state.results = searchCommands(state.query);
    render();
  }

  function handleClick(e) {
    const item = e.target.closest('.cp-item');
    if (item) {
      state.selectedIndex = parseInt(item.dataset.index);
      executeSelected();
    }

    const favBtn = e.target.closest('.cp-fav-btn');
    if (favBtn) {
      e.stopPropagation();
      toggleFavoriteCommand(favBtn.dataset.id);
    }
  }

  // ==========================================
  // HELPERS
  // ==========================================
  function navigate(url) {
    if (window.navigateSPA) window.navigateSPA(url);
    else window.location.href = url;
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen();
    }
  }

  // ==========================================
  // PUBLIC API
  // ==========================================
  window.CommandPalette = {
    open,
    close,
    toggle: () => (state.isOpen ? close() : open()),
    isOpen: () => state.isOpen,
    execute: executeSelected,
    registerCommand: (cmd) => {
      COMMANDS.push(cmd);
    },
    unregisterCommand: (id) => {
      const idx = COMMANDS.findIndex((c) => c.id === id);
      if (idx >= 0) COMMANDS.splice(idx, 1);
    },
  };

  // ==========================================
  // INIT
  // ==========================================
  function init() {
    const modal = document.getElementById('command-palette');
    const input = document.getElementById('command-palette-input');
    const results = document.getElementById('command-palette-results');

    if (!modal || !input || !results) return;

    // Global shortcut
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        window.CommandPalette.toggle();
      }
    });

    // Modal events
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close();
    });

    input.addEventListener('input', handleInput);
    input.addEventListener('keydown', handleKeydown);
    results.addEventListener('click', handleClick);
    results.addEventListener('keydown', handleKeydown);

    // Prevent input from closing on Escape
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') e.stopPropagation();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
