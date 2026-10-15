/**
 * Widget Palette - Side Panel for Drag & Drop Widget Addition
 * Live preview, categories, search, keyboard navigation
 */
(function () {
  'use strict';

  // ── Estilo dos cards "sem dado" ─────────────────────────────────────────
  // A paleta não tem folha de estilos própria, por isso os estilos vivem aqui.
  // Injectados uma vez, no primeiro carregamento.
  if (!document.getElementById('widget-palette-req-css')) {
    const st = document.createElement('style');
    st.id = 'widget-palette-req-css';
    st.textContent = `
      .palette-card.sem-dado .palette-card-icon { filter: saturate(.35); }
      .palette-card.sem-dado .palette-card-title { color: var(--text-secondary, #64748b); }
      .palette-badge.falta {
        display:inline-flex; align-items:center; justify-content:center;
        width:14px; height:14px; border-radius:50%;
        background:rgba(148,163,184,.22); color:#94a3b8; font-size:9px;
      }
      .palette-card-requer {
        margin-top:3px; font-size:10px; line-height:1.35;
        color:#94a3b8; font-style:italic;
        display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
        overflow:hidden;
      }
      .palette-card.sem-dado:hover .palette-card-requer { -webkit-line-clamp:4; }
    `;
    document.head.appendChild(st);
  }

  const state = {
    isOpen: false,
    activeTab: 'all',
    searchQuery: '',
    selectedIndex: 0,
    draggedItem: null,
    previewWidget: null,
    categories: [
      { id: 'all', label: 'Todos', icon: 'bi-grid-3x3-gap' },
      { id: 'kpi', label: 'KPIs', icon: 'bi-speedometer2' },
      { id: 'chart', label: 'Gráficos', icon: 'bi-graph-up' },
      { id: 'table', label: 'Tabelas', icon: 'bi-table' },
      { id: 'list', label: 'Listas', icon: 'bi-list-task' },
      { id: 'composite', label: 'Compostos', icon: 'bi-layers' },
      { id: 'culture', label: 'Por Cultura', icon: 'bi-flower1' },
    ],
  };

  // ==========================================
  // WIDGET CATEGORIZATION
  // ==========================================
  function categorizeWidget(id, type) {
    if (id.startsWith('kpi-')) return 'kpi';
    if (id.startsWith('chart-')) return 'chart';
    if (id.startsWith('table-')) return 'table';
    if (id.startsWith('list-') || id === 'calendar-widget' || id === 'alerts-widget') return 'list';
    if (id.startsWith('widget-') || id === 'weather-widget') return 'composite';
    return 'kpi';
  }

  function getFilteredWidgets() {
    const types = window.WIDGET_TYPES || {};
    let widgets = Object.entries(types).map(([id, type]) => ({
      id,
      ...type,
      category: categorizeWidget(id, type),
    }));

    // Add culture widgets
    if (window.CULTURE_GROUPS) {
      window.CULTURE_GROUPS.forEach((g) => {
        g.cultures.forEach((c) => {
          if (!types[c.id]) {
            widgets.push({
              id: c.id,
              title: c.title,
              icon: c.icon || 'bi-flower1',
              defaultSize: { w: 6, h: 4 },
              desc: c.desc || '',
              category: 'culture',
              cultureGroup: g.id,
              subgroup: c.subgroup,
            });
          }
        });
      });
    }

    // Filter by tab
    if (state.activeTab !== 'all') {
      widgets = widgets.filter((w) => w.category === state.activeTab);
    }

    // Filter by search
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      widgets = widgets.filter(
        (w) =>
          w.title.toLowerCase().includes(q) ||
          w.id.toLowerCase().includes(q) ||
          w.desc?.toLowerCase().includes(q) ||
          w.category.toLowerCase().includes(q)
      );
    }

    // Sort: favorites first, then recents, then alphabetical
    const favorites = window.WidgetIntelligence?.getFavorites?.() || [];
    const recents = window.WidgetIntelligence?.getRecents?.().map((r) => r.id) || [];

    widgets.sort((a, b) => {
      const aFav = favorites.includes(a.id);
      const bFav = favorites.includes(b.id);
      if (aFav !== bFav) return bFav - aFav;

      const aRec = recents.indexOf(a.id);
      const bRec = recents.indexOf(b.id);
      if (aRec >= 0 && bRec >= 0) return aRec - bRec;
      if (aRec >= 0) return -1;
      if (bRec >= 0) return 1;

      return a.title.localeCompare(b.title);
    });

    return widgets;
  }

  // ==========================================
  // RENDER
  // ==========================================
  function render() {
    const panel = document.getElementById('widget-palette-panel');
    if (!panel) return;

    const widgets = getFilteredWidgets();
    const favorites = window.WidgetIntelligence?.getFavorites?.() || [];
    const recents = window.WidgetIntelligence?.getRecents?.() || [];

    let html = `
            <!-- Header -->
            <div class="palette-header">
                <div class="palette-title">
                    <i class="bi bi-puzzle"></i>
                    <span>Paleta de Widgets</span>
                    <span class="palette-count">${widgets.length} disponíveis</span>
                </div>
                <button onclick="closeWidgetPalette()" class="palette-close" aria-label="Fechar"><i class="bi bi-x-lg"></i></button>
            </div>

            <!-- Search -->
            <div class="palette-search">
                <i class="bi bi-search"></i>
                <input type="text" id="palette-search" placeholder="Buscar widgets..." value="${
                  state.searchQuery
                }"
                    oninput="handlePaletteSearch(this.value)" onkeydown="handlePaletteKeydown(event)">
                <kbd class="palette-shortcut">Esc</kbd>
            </div>

            <!-- Tabs -->
            <div class="palette-tabs" role="tablist">
                ${state.categories
                  .map(
                    (c) => `
                    <button role="tab" class="palette-tab ${
                      state.activeTab === c.id ? 'active' : ''
                    }"
                        onclick="setPaletteTab('${c.id}')" aria-selected="${
                          state.activeTab === c.id
                        }">
                        <i class="bi ${c.icon}"></i><span>${c.label}</span>
                    </button>
                `
                  )
                  .join('')}
            </div>

            <!-- Content -->
            <div class="palette-content" id="palette-content" role="tabpanel">
                ${widgets.length === 0 ? renderEmptyState() : renderWidgetGrid(widgets)}
            </div>

            <!-- Footer -->
            <div class="palette-footer">
                <div class="palette-hints">
                    <span><kbd>←→↑↓</kbd> Navegar</span>
                    <span><kbd>Enter</kbd> Adicionar</span>
                    <span><kbd>Espaço</kbd> Favoritar</span>
                    <span><kbd>Arrastar</kbd> Para matriz</span>
                </div>
                <button onclick="openAddWidgetModal()" class="palette-btn-full">Modal Completo (Ctrl+Shift+W)</button>
            </div>
        `;

    panel.innerHTML = html;

    // Update selection
    updateSelection();
  }

  function renderWidgetGrid(widgets) {
    return `
            <div class="palette-grid" role="listbox" aria-multiselectable="false">
                ${widgets.map((w, i) => renderWidgetCard(w, i)).join('')}
            </div>
        `;
  }

  function renderWidgetCard(widget, index) {
    const isFavorite = (window.WidgetIntelligence?.getFavorites?.() || []).includes(widget.id);
    const isRecent = (window.WidgetIntelligence?.getRecents?.().map((r) => r.id) || []).includes(
      widget.id
    );
    const isSelected = index === state.selectedIndex;

    // ── O que falta a este widget, para esta conta ───────────────────────────
    // Um widget sem dados não é escondido: é mostrado e explica o que precisa.
    // Um menu que desaparece sem explicação é um menu que o produtor contorna
    // pelo outro lado (e o "contorno" dele costuma ser inventar números).
    const req = window.avaliarWidgetRequisito
      ? window.avaliarWidgetRequisito(widget.id, window.widgetDataCache || {})
      : { estado: 'pronto', msg: '' };
    const falta = req.estado !== 'pronto';
    const dica = escapePalette(req.msg || '');

    return `
            <div class="palette-card ${isSelected ? 'selected' : ''} ${
              isFavorite ? 'favorite' : ''
            } ${isRecent ? 'recent' : ''} ${falta ? 'sem-dado' : ''}"
                 data-id="${widget.id}" data-index="${index}"
                 role="option" aria-selected="${isSelected}"
                 draggable="true"
                 aria-describedby="${falta ? 'req-' + widget.id : ''}"
                 ondragstart="handlePaletteDragStart(event, '${widget.id}')"
                 ondragend="handlePaletteDragEnd(event)"
                 onclick="handlePaletteCardClick('${widget.id}', ${index})"
                 onmouseenter="handlePaletteCardHover(${index})"
                 title="${widget.title}${
                   falta ? ' — ' + dica : widget.desc ? ': ' + widget.desc : ''
                 }">
                <div class="palette-card-icon" style="background: ${
                  falta ? 'rgba(148,163,184,0.35)' : getCategoryColor(widget.category)
                }">
                    <i class="bi ${widget.icon}"></i>
                </div>
                <div class="palette-card-info">
                    <div class="palette-card-title">${widget.title}</div>
                    <div class="palette-card-meta">
                        <span class="palette-card-size">${widget.defaultSize?.w || 4}×${
                          widget.defaultSize?.h || 3
                        }</span>
                        ${
                          isFavorite
                            ? '<span class="palette-badge favorite"><i class="bi bi-star-fill"></i></span>'
                            : ''
                        }
                        ${
                          isRecent
                            ? '<span class="palette-badge recent"><i class="bi bi-clock-history"></i></span>'
                            : ''
                        }
                        ${
                          widget.category === 'culture'
                            ? '<span class="palette-badge culture"><i class="bi bi-flower1"></i></span>'
                            : ''
                        }
                        ${
                          falta
                            ? '<span class="palette-badge falta" title="' +
                              dica +
                              '"><i class="bi bi-info-circle"></i></span>'
                            : ''
                        }
                    </div>
                    ${
                      falta
                        ? '<div class="palette-card-requer" id="req-' +
                          widget.id +
                          '">' +
                          dica +
                          '</div>'
                        : ''
                    }
                </div>
                <button class="palette-fav-btn ${
                  isFavorite ? 'active' : ''
                }" onclick="event.stopPropagation(); togglePaletteFavorite('${
                  widget.id
                }')" aria-label="${
                  isFavorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos'
                }">
                    <i class="bi ${isFavorite ? 'bi-star-fill' : 'bi-star'}"></i>
                </button>
            </div>
        `;
  }

  /** Escapa o texto do registo antes de o meter no HTML. */
  function escapePalette(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderEmptyState() {
    return `
            <div class="palette-empty">
                <i class="bi bi-search"></i>
                <h4>Nenhum widget encontrado</h4>
                <p>Tente outro termo ou mude a aba</p>
            </div>
        `;
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

  function updateSelection() {
    const cards = document.querySelectorAll('.palette-card');
    cards.forEach((card, i) => {
      card.classList.toggle('selected', i === state.selectedIndex);
      card.setAttribute('aria-selected', i === state.selectedIndex);
    });

    // Scroll into view
    const selected = cards[state.selectedIndex];
    if (selected) {
      selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  // ==========================================
  // DRAG & DROP
  // ==========================================
  window.handlePaletteDragStart = function (e, widgetId) {
    state.draggedItem = widgetId;
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', widgetId);

    // Create preview
    createLivePreview(widgetId);

    // Visual feedback
    const card = e.target.closest('.palette-card');
    if (card) card.classList.add('dragging');

    // Show drop zones on matrix
    showMatrixDropZones();
  };

  window.handlePaletteDragEnd = function (e) {
    state.draggedItem = null;
    removeLivePreview();
    hideMatrixDropZones();

    document
      .querySelectorAll('.palette-card.dragging')
      .forEach((c) => c.classList.remove('dragging'));
  };

  function createLivePreview(widgetId) {
    const type = window.WIDGET_TYPES?.[widgetId];
    if (!type) return;

    const preview = document.createElement('div');
    preview.id = 'widget-live-preview';
    preview.className = 'widget-live-preview';
    preview.style.pointerEvents = 'none';
    preview.style.zIndex = '2147483647';
    preview.innerHTML = `
            <div class="preview-header">
                <i class="bi ${type.icon}"></i>
                <span>${type.title}</span>
            </div>
            <div class="preview-content">
                ${getPreviewContent(widgetId)}
            </div>
            <div class="preview-size">${type.defaultSize?.w || 4}×${
              type.defaultSize?.h || 3
            } células</div>
        `;

    document.body.appendChild(preview);
    state.previewWidget = preview;

    // Position at cursor
    positionPreview(preview);
  }

  function positionPreview(preview) {
    document.addEventListener('mousemove', movePreview);
    function movePreview(e) {
      preview.style.left = `${e.clientX + 20}px`;
      preview.style.top = `${e.clientY - 10}px`;
    }
  }

  function removeLivePreview() {
    if (state.previewWidget) {
      state.previewWidget.remove();
      state.previewWidget = null;
    }
  }

  function getPreviewContent(widgetId) {
    const previews = {
      'kpi-roi':
        '<div class="preview-kpi"><span class="label">ROI Operacional</span><span class="value">+12,5%</span></div>',
      'kpi-custo':
        '<div class="preview-kpi"><span class="label">Custo/Ha</span><span class="value">R$ 450</span></div>',
      'kpi-clima':
        '<div class="preview-kpi"><i class="bi bi-sun"></i><span class="value">28°C</span></div>',
      'chart-line': '<canvas class="preview-chart" width="200" height="80"></canvas>',
      'chart-bar': '<canvas class="preview-chart" width="200" height="80"></canvas>',
      'table-data':
        '<table class="preview-table"><tr><th>Item</th><th>Valor</th></tr><tr><td>Soja</td><td>R$ 85</td></tr><tr><td>Milho</td><td>R$ 42</td></tr></table>',
      'list-tarefas':
        '<ul class="preview-list"><li>Plantar soja</li><li>Revisar manutenção</li><li>Aplicar fertilizante</li></ul>',
    };
    return previews[widgetId] || `<div class="preview-placeholder">${widgetId}</div>`;
  }

  function showMatrixDropZones() {
    const container = document.querySelector('.matrix-container');
    if (!container) return;

    // Add drop zone overlay
    const overlay = document.createElement('div');
    overlay.id = 'matrix-drop-overlay';
    overlay.className = 'matrix-drop-overlay';
    overlay.innerHTML =
      '<div class="drop-zone-hint"><i class="bi bi-plus-circle"></i> Solte para adicionar aqui</div>';
    container.appendChild(overlay);

    // Highlight empty cells
    highlightEmptyCells();
  }

  function hideMatrixDropZones() {
    const overlay = document.getElementById('matrix-drop-overlay');
    if (overlay) overlay.remove();

    document
      .querySelectorAll('.matrix-cell.drop-target')
      .forEach((c) => c.classList.remove('drop-target'));
  }

  function highlightEmptyCells() {
    // This would integrate with the matrix system to show valid drop positions
    const container = document.querySelector('.matrix-container');
    if (!container) return;

    // For now, just add a general drop zone
    container.classList.add('drop-ready');
  }

  // Handle drop on matrix
  document.addEventListener('dragover', (e) => {
    if (state.draggedItem && e.target.closest('.matrix-container')) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    }
  });

  document.addEventListener('drop', (e) => {
    if (state.draggedItem && e.target.closest('.matrix-container')) {
      e.preventDefault();
      const widgetId = state.draggedItem;
      // Find position in matrix (simplified)
      const container = e.target.closest('.matrix-container');
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Add widget at approximate position
      addWidgetAtPosition(widgetId, x, y);

      hideMatrixDropZones();
    }
  });

  function addWidgetAtPosition(widgetId, x, y) {
    // Delegate to matrix system
    if (window.addWidget) {
      window.addWidget(widgetId);
    }
  }

  // ==========================================
  // INTERACTIONS
  // ==========================================
  window.handlePaletteCardClick = function (widgetId, index) {
    state.selectedIndex = index;
    updateSelection();
    addWidget(widgetId);
  };

  window.handlePaletteCardHover = function (index) {
    state.selectedIndex = index;
    updateSelection();
  };

  function addWidget(widgetId) {
    if (window.addWidget) {
      window.addWidget(widgetId);
      window.WidgetIntelligence?.addRecent?.(widgetId, { source: 'palette' });
      window.WidgetIntelligence?.trackUsage?.(widgetId, 'add-from-palette');
    }
    // Don't close - allow adding multiple
  }

  window.togglePaletteFavorite = function (widgetId) {
    const isFav = window.WidgetIntelligence?.toggleFavorite?.(widgetId);
    render(); // Re-render to update UI
  };

  window.setPaletteTab = function (tabId) {
    state.activeTab = tabId;
    state.selectedIndex = 0;
    render();
  };

  window.handlePaletteSearch = function (query) {
    state.searchQuery = query;
    state.selectedIndex = 0;
    render();
  };

  window.handlePaletteKeydown = function (e) {
    const widgets = getFilteredWidgets();
    const maxIndex = widgets.length - 1;

    switch (e.key) {
      case 'Escape':
        closeWidgetPalette();
        break;
      case 'ArrowDown':
        e.preventDefault();
        state.selectedIndex = Math.min(state.selectedIndex + 5, maxIndex);
        updateSelection();
        break;
      case 'ArrowUp':
        e.preventDefault();
        state.selectedIndex = Math.max(state.selectedIndex - 5, 0);
        updateSelection();
        break;
      case 'ArrowRight':
        e.preventDefault();
        state.selectedIndex = Math.min(state.selectedIndex + 1, maxIndex);
        updateSelection();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        state.selectedIndex = Math.max(state.selectedIndex - 1, 0);
        updateSelection();
        break;
      case 'Enter':
        e.preventDefault();
        if (widgets[state.selectedIndex]) {
          addWidget(widgets[state.selectedIndex].id);
        }
        break;
      case ' ':
        e.preventDefault();
        if (widgets[state.selectedIndex]) {
          togglePaletteFavorite(widgets[state.selectedIndex].id);
        }
        break;
      case 'Tab':
        e.preventDefault();
        // Cycle tabs
        const tabs = state.categories.map((c) => c.id);
        const currentIdx = tabs.indexOf(state.activeTab);
        const nextIdx = (currentIdx + 1) % tabs.length;
        setPaletteTab(tabs[nextIdx]);
        break;
    }
  };

  // ==========================================
  // OPEN/CLOSE
  // ==========================================
  window.openWidgetPalette = function () {
    const modal = document.getElementById('widget-palette-modal');
    const panel = document.getElementById('widget-palette-panel');

    if (!modal || !panel) return;

    state.isOpen = true;
    state.searchQuery = '';
    state.activeTab = 'all';
    state.selectedIndex = 0;
    render();

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    requestAnimationFrame(() => {
      panel.classList.remove('translate-x-full', 'opacity-0');
      panel.classList.add('translate-x-0', 'opacity-100');
    });

    document.body.style.overflow = 'hidden';

    // Focus search
    setTimeout(() => document.getElementById('palette-search')?.focus(), 100);

    window.WidgetIntelligence?.trackUsage?.('widget-palette', 'open');
  };

  window.closeWidgetPalette = function () {
    const modal = document.getElementById('widget-palette-modal');
    const panel = document.getElementById('widget-palette-panel');

    if (!modal || !panel) return;

    panel.classList.remove('translate-x-0', 'opacity-100');
    panel.classList.add('translate-x-full', 'opacity-0');

    setTimeout(() => {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      document.body.style.overflow = '';
    }, 300);

    state.isOpen = false;
  };

  window.toggleWidgetPalette = function () {
    if (state.isOpen) closeWidgetPalette();
    else openWidgetPalette();
  };

  // ==========================================
  // INIT - Inject modal HTML
  // ==========================================
  function injectModal() {
    if (document.getElementById('widget-palette-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'widget-palette-modal';
    modal.className =
      'fixed inset-0 z-[1000] hidden items-center justify-end p-0 bg-black/30 backdrop-blur-sm';
    modal.onclick = (e) => {
      if (e.target === modal) closeWidgetPalette();
    };
    modal.innerHTML = `
            <div id="widget-palette-panel" class="transform transition-all duration-300 ease-out translate-x-full opacity-0 bg-white dark:bg-slate-900 shadow-2xl flex flex-col h-full max-w-sm w-full border-l border-slate-200 dark:border-slate-700" onclick="event.stopPropagation()"></div>
        `;
    document.body.appendChild(modal);
  }

  function init() {
    injectModal();

    // Keyboard shortcut: Ctrl+Shift+W
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'W') {
        e.preventDefault();
        toggleWidgetPalette();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
