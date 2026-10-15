/**
 * Widget Inline Add - Click Empty Matrix Cell to Add Widget
 * Contextual suggestions based on position, neighbors, and data
 * DISABLED per user request - use widget bar instead
 */
(function () {
  'use strict';

  const state = {
    isEnabled: false, // DISABLED - use widget bar (+ button) instead
    lastHoveredCell: null,
    addButton: null,
  };

  // ==========================================
  // INIT - Observe Matrix
  // ==========================================
  function init() {
    // DISABLED - no longer setting up click/hover handlers on matrix
    // Widgets are added via the widget bar (+ button) or command palette
    console.log('[WidgetInlineAdd] Disabled - use widget bar to add widgets');
  }

  function setupMatrixClickHandler(container) {
    if (container.dataset.inlineAddInitialized) return;
    container.dataset.inlineAddInitialized = 'true';

    // Click on empty space in matrix
    container.addEventListener('click', (e) => {
      if (!state.isEnabled) return;
      if (e.target !== container) return; // Only empty space
      if (state.isCustomMode()) return; // Not in edit mode

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      showInlineAddMenu(x, y, container);
    });

    // Hover to show drop hint
    container.addEventListener('mousemove', (e) => {
      if (!state.isEnabled || state.isCustomMode()) return;
      if (e.target !== container) return;

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      showDropHint(x, y, container);
    });

    container.addEventListener('mouseleave', () => {
      hideDropHint();
    });
  }

  // ==========================================
  // INLINE ADD MENU
  // ==========================================
  function showInlineAddMenu(x, y, container) {
    // Remove existing
    hideInlineAddMenu();

    const suggestions = getContextualSuggestions(x, y, container);
    if (!suggestions.length) return;

    const menu = document.createElement('div');
    menu.id = 'inline-add-menu';
    menu.className = 'inline-add-menu';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.innerHTML = `
            <div class="inline-add-header">
                <i class="bi bi-plus-circle"></i>
                <span>Adicionar Widget</span>
                <button class="inline-add-close" onclick="hideInlineAddMenu()"><i class="bi bi-x"></i></button>
            </div>
            <div class="inline-add-suggestions">
                ${suggestions
                  .map(
                    (w, i) => `
                    <button class="inline-add-item ${i === 0 ? 'selected' : ''}" data-id="${w.id}" data-index="${i}"
                        onclick="addWidgetFromInline('${w.id}')" onmouseenter="selectInlineItem(${i})">
                        <div class="inline-add-icon" style="background: ${getCategoryColor(w.category)}">
                            <i class="bi ${w.icon}"></i>
                        </div>
                        <div class="inline-add-info">
                            <span class="inline-add-title">${w.title}</span>
                            <span class="inline-add-size">${w.defaultSize?.w || 4}×${w.defaultSize?.h || 3}</span>
                        </div>
                        ${w.isFavorite ? '<i class="bi bi-star-fill inline-fav"></i>' : ''}
                        ${w.isRecent ? '<i class="bi bi-clock-history inline-recent"></i>' : ''}
                        ${w.isSuggested ? '<span class="inline-ai">IA</span>' : ''}
                    </button>
                `
                  )
                  .join('')}
            </div>
            <div class="inline-add-footer">
                <button onclick="openWidgetPalette(); hideInlineAddMenu()" class="inline-add-more">
                    <i class="bi bi-grid-3x3-gap"></i> Ver todos (Ctrl+Shift+W)
                </button>
                <button onclick="openAddWidgetModal(); hideInlineAddMenu()" class="inline-add-more">
                    <i class="bi bi-plus-lg"></i> Modal Completo
                </button>
            </div>
        `;

    container.appendChild(menu);

    // Animate in
    requestAnimationFrame(() => menu.classList.add('open'));

    // Position adjustment (keep in viewport)
    adjustMenuPosition(menu);

    // Keyboard navigation
    menu.focus();
    menu.addEventListener('keydown', handleInlineKeydown);
  }

  function hideInlineAddMenu() {
    const menu = document.getElementById('inline-add-menu');
    if (menu) {
      menu.classList.remove('open');
      setTimeout(() => menu.remove(), 200);
    }
  }

  function getContextualSuggestions(x, y, container) {
    const allWidgets = Object.entries(window.WIDGET_TYPES || {}).map(([id, type]) => ({
      id,
      ...type,
      category: categorizeWidget(id),
    }));

    // Add culture widgets
    if (window.CULTURE_GROUPS) {
      window.CULTURE_GROUPS.forEach((g) => {
        g.cultures.forEach((c) => {
          if (!window.WIDGET_TYPES?.[c.id]) {
            allWidgets.push({
              id: c.id,
              title: c.title,
              icon: c.icon || 'bi-flower1',
              defaultSize: { w: 6, h: 4 },
              category: 'culture',
            });
          }
        });
      });
    }

    // Score based on context
    const scored = allWidgets.map((w) => {
      let score = 0;
      const favorites = window.WidgetIntelligence?.getFavorites?.() || [];
      const recents = window.WidgetIntelligence?.getRecents?.().map((r) => r.id) || [];
      const suggestions = window.WidgetIntelligence?.getSuggestions?.({ limit: 20 }) || [];

      if (favorites.includes(w.id)) score += 100;
      if (recents.includes(w.id)) score += 50 - recents.indexOf(w.id) * 5;
      if (suggestions.includes(w.id)) score += 30 - suggestions.indexOf(w.id) * 2;

      // Position-based: top area -> KPIs, middle -> charts, bottom -> tables/lists
      const relativeY = y / container.clientHeight;
      if (relativeY < 0.3 && w.category === 'kpi') score += 20;
      if (relativeY > 0.3 && relativeY < 0.7 && w.category === 'chart') score += 20;
      if (relativeY > 0.7 && (w.category === 'table' || w.category === 'list')) score += 20;

      // Neighbor-aware: if there are charts nearby, suggest tables
      const neighbors = getNeighborWidgets(x, y);
      if (neighbors.hasChart && w.category === 'table') score += 15;
      if (neighbors.hasTable && w.category === 'chart') score += 15;
      if (neighbors.hasKPI && w.category === 'chart') score += 10;

      return {
        ...w,
        score,
        isFavorite: favorites.includes(w.id),
        isRecent: recents.includes(w.id),
        isSuggested: suggestions.includes(w.id),
      };
    });

    return scored.sort((a, b) => b.score - a.score).slice(0, 8);
  }

  function getNeighborWidgets(x, y) {
    // Simplified - check existing widgets in matrix
    const hasChart = document.querySelector('.bento-block [id^="chart-"]') !== null;
    const hasTable = document.querySelector('.bento-block [id^="table-"]') !== null;
    const hasKPI = document.querySelector('.bento-block [id^="kpi-"]') !== null;
    return { hasChart, hasTable, hasKPI };
  }

  function categorizeWidget(id) {
    if (id.startsWith('kpi-')) return 'kpi';
    if (id.startsWith('chart-')) return 'chart';
    if (id.startsWith('table-')) return 'table';
    if (id.startsWith('list-') || id === 'calendar-widget' || id === 'alerts-widget') return 'list';
    if (id.startsWith('widget-') || id === 'weather-widget') return 'composite';
    return 'kpi';
  }

  function getCategoryColor(category) {
    const colors = {
      kpi: 'linear-gradient(135deg, #0f9d6e, #3ec48f)',
      chart: 'linear-gradient(135deg, #3b82f6, #60a5fa)',
      table: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
      list: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
      composite: 'linear-gradient(135deg, #ec4899, #f472b6)',
      culture: 'linear-gradient(135deg, #14b8a6, #2dd4bf)',
    };
    return colors[category] || colors.kpi;
  }

  function adjustMenuPosition(menu) {
    const rect = menu.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    if (rect.right > vw - 16) {
      menu.style.left = `${vw - rect.width - 16}px`;
    }
    if (rect.bottom > vh - 16) {
      menu.style.top = `${vh - rect.height - 16}px`;
    }
  }

  function handleInlineKeydown(e) {
    const items = document.querySelectorAll('.inline-add-item');
    const selected = document.querySelector('.inline-add-item.selected');
    const currentIndex = selected ? parseInt(selected.dataset.index) : -1;

    switch (e.key) {
      case 'Escape':
        hideInlineAddMenu();
        break;
      case 'ArrowDown':
        e.preventDefault();
        selectInlineItem(Math.min(currentIndex + 1, items.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        selectInlineItem(Math.max(currentIndex - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (selected) selected.click();
        break;
    }
  }

  window.selectInlineItem = function (index) {
    document.querySelectorAll('.inline-add-item').forEach((item, i) => {
      item.classList.toggle('selected', i === index);
    });
  };

  window.addWidgetFromInline = function (widgetId) {
    if (window.addWidget) {
      window.addWidget(widgetId);
      window.WidgetIntelligence?.addRecent?.(widgetId, { source: 'inline' });
      window.WidgetIntelligence?.trackUsage?.(widgetId, 'add-from-inline');
    }
    hideInlineAddMenu();
  };

  // ==========================================
  // DROP HINT
  // ==========================================
  function showDropHint(x, y, container) {
    // Remove ALL existing hints immediately (not with timeout)
    document.querySelectorAll('#matrix-drop-hint').forEach((el) => el.remove());

    const hint = document.createElement('div');
    hint.id = 'matrix-drop-hint';
    hint.className = 'matrix-drop-hint';
    hint.style.left = `${x}px`;
    hint.style.top = `${y}px`;
    hint.innerHTML = '<i class="bi bi-plus-circle"></i><span>Clique para adicionar widget</span>';

    container.appendChild(hint);
    requestAnimationFrame(() => hint.classList.add('visible'));
  }

  function hideDropHint() {
    document.querySelectorAll('#matrix-drop-hint').forEach((el) => el.remove());
  }

  // ==========================================
  // PUBLIC API
  // ==========================================
  window.WidgetInlineAdd = {
    enable: () => {
      state.isEnabled = true;
    },
    disable: () => {
      state.isEnabled = false;
      hideInlineAddMenu();
      hideDropHint();
    },
    isEnabled: () => state.isEnabled,
  };

  // Helper for custom mode check
  state.isCustomMode = () => window.widgetbarState?.isCustomMode === true;

  // Global access for inline menu
  window.hideInlineAddMenu = hideInlineAddMenu;
  window.addWidgetFromInline = window.addWidgetFromInline;
  window.selectInlineItem = window.selectInlineItem;

  // Init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
