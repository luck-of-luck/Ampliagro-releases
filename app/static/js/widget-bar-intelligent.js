/**
 * Widget Bar Intelligent - Enhances Existing Widgetbar
 * Adds smart suggestions, recents, favorites to search menu
 * Initializes presets carousel, drag sliders, connection status
 */
(function () {
  'use strict';

  // Render do icone de um preset.
  //
  // Os presets sao representados por `<i class="bi ...">`, uma glifo do Bootstrap.
  // O preset-base "IA" traz um SVG em vez disso (as letras IA sobre o verde da
  // Ampliagro), e um SVG nao cabe num `class`. Por isso este helper: se o preset
  // tiver `iconSvg`, devolve o SVG; se nao, cai no `<i class="bi">` de sempre.
  //
  // Fica em `window` porque o OUTRO renderizador — widget-presets.js — precisa
  // do mesmo comportamento, e os dois ficheiros nao se importam.
  window.presetIconHtml = function (preset, color) {
    if (!preset) return '';
    if (preset.iconSvg) {
      // O SVG ja traz as suas proprias cores; `color` nao se aplica a ele.
      return (
        '<span class="preset-svg-icon" style="display:block;width:100%;height:100%">' +
        preset.iconSvg +
        '</span>'
      );
    }
    var style = color ? ' style="color:' + color + '"' : '';
    return '<i class="bi ' + (preset.icon || 'bi-puzzle') + '"' + style + '></i>';
  };

  const state = {
    isCustomMode: false,
    isSearchOpen: false,
  };

  // ==========================================
  // ENHANCE EXISTING WIDGET BAR
  // ==========================================
  function enhanceWidgetBar() {
    // 1. Render presets carousel
    renderPresetsCarousel();

    // 2. Initialize drag sliders
    initDragSliders();

    // 3. Update connection status
    updateConnectionStatus();

    // 4. Enhance search menu with intelligent content (when opened)
    enhanceSearchMenu();

    // 5. Sync custom mode button state
    syncCustomModeButton();
  }

  function enhanceSearchMenu() {
    const searchMenu = document.getElementById('search-menu');
    if (!searchMenu) return;

    // Store original content
    if (!searchMenu.dataset.originalContent) {
      searchMenu.dataset.originalContent = searchMenu.innerHTML;
    }

    // Add event listener to refresh intelligent content when opened
    const searchBtn = document.querySelector('.widgetbar-search-btn');
    if (searchBtn && !searchBtn.dataset.enhanced) {
      searchBtn.dataset.enhanced = 'true';
      const originalOnclick = searchBtn.onclick;
      searchBtn.onclick = function (e) {
        if (originalOnclick) originalOnclick.call(this, e);
        // After menu opens, enhance it
        setTimeout(populateIntelligentSearchMenu, 50);
      };
    }
  }

  function populateIntelligentSearchMenu() {
    const searchMenu = document.getElementById('search-menu');
    if (!searchMenu || !searchMenu.classList.contains('open')) return;

    const recents = window.WidgetIntelligence?.getRecents?.() || [];
    const favorites = window.WidgetIntelligence?.getFavorites?.() || [];
    const suggestions = window.WidgetIntelligence?.getSuggestions?.({ limit: 6 }) || [];

    // Windows Start — IDs dedicados (compatível com nova grade 2 colunas)
    const recentSection =
      document.getElementById('search-section-recents') ||
      searchMenu.querySelector('.search-menu-section:nth-of-type(2)');
    const favSection =
      document.getElementById('search-section-favs') ||
      searchMenu.querySelector('.search-menu-section:nth-of-type(3)');
    const suggestSection =
      document.getElementById('search-section-suggested') ||
      searchMenu.querySelector('.search-menu-section:nth-of-type(4)');

    if (recentSection) {
      recentSection.innerHTML =
        '<div class="search-menu-header"><i class="bi bi-clock-history me-1"></i> Recentes</div>' +
        renderRecentItems(recents);
    }
    if (favSection) {
      favSection.innerHTML =
        '<div class="search-menu-header"><i class="bi bi-star me-1"></i> Favoritos</div>' +
        renderFavoriteItems(favorites);
    }
    if (suggestSection) {
      suggestSection.innerHTML =
        '<div class="search-menu-header"><i class="bi bi-magic me-1"></i> Sugerido para você</div>' +
        renderSuggestionItems(suggestions);
    }
  }

  function renderRecentItems(recents) {
    if (!recents.length)
      return '<div class="search-menu-item muted"><i class="bi bi-clock-history"></i><span>Nenhum widget recente</span></div>';
    return recents
      .slice(0, 5)
      .map((r) => {
        const type = window.WIDGET_TYPES?.[r.id];
        return `<div class="search-menu-item" onclick="addWidgetFromSearch('${
          r.id
        }')" data-widget="${r.id}">
                <i class="bi ${type?.icon || 'bi-puzzle'}"></i><span>${type?.title || r.id}</span>
                <span class="search-menu-time">${formatTimeAgo(r.timestamp)}</span>
            </div>`;
      })
      .join('');
  }

  function renderFavoriteItems(favorites) {
    if (!favorites.length)
      return '<div class="search-menu-item muted"><i class="bi bi-star"></i><span>Nenhum favorito - clique na estrela para adicionar</span></div>';
    return favorites
      .slice(0, 6)
      .map((id) => {
        const type = window.WIDGET_TYPES?.[id];
        return `<div class="search-menu-item" onclick="addWidgetFromSearch('${id}')" data-widget="${id}">
                <i class="bi ${type?.icon || 'bi-puzzle'}"></i><span>${type?.title || id}</span>
                <i class="bi bi-star-fill text-warning"></i>
            </div>`;
      })
      .join('');
  }

  function renderSuggestionItems(suggestions) {
    if (!suggestions.length)
      return '<div class="search-menu-item muted"><i class="bi bi-magic"></i><span>Nenhuma sugestão no momento</span></div>';
    return suggestions
      .slice(0, 6)
      .map((id) => {
        const type = window.WIDGET_TYPES?.[id];
        return `<div class="search-menu-item" onclick="addWidgetFromSearch('${id}')" data-widget="${id}">
                <i class="bi ${type?.icon || 'bi-puzzle'}"></i><span>${type?.title || id}</span>
                <span class="badge bg-emerald-100 text-emerald-700 text-xs">IA</span>
            </div>`;
      })
      .join('');
  }

  /**
   * DELEGADO. Este ficheiro já NÃO escreve em `#presets-carousel`.
   *
   * MEDIDO 2026-10-04 (agente 4). Havia DOIS renderizadores para o mesmo
   * sítio, e ambos faziam `innerHTML =` — quem escrevia por último vencia.
   *
   * Este perdia em três coisas, todas medidas em jsdom por
   * `tests/unit/presets_renderizador.test.js`:
   *
   *   1. **A ordem.** Este itera `Object.entries(window.PRESETS)` — a ordem de
   *      inserção do objecto. O dono itera `getPresetOrder()`, que é a ordem
   *      que o produtor ARRASTOU e que foi persistida. O arrastar existia e
   *      este renderizador desfazia-o.
   *   2. **O preset activo.** Este marca o primeiro da lista como activo; o
   *      dono marca o que está em `matrix-active-preset`. Com a lista
   *      reordenada, os dois discordam sobre qual é o preset activo.
   *   3. **As capacidades.** Este faz clique e preview. O dono faz também
   *      arrastar, editar, apagar e respeita `_presetImutavel`.
   *
   * E, pelo lado da segurança, este escrevia `onclick=` INLINE — que é dívida
   * de CSP. Escolher este renderizador não eliminava a dívida: mudava-a de
   * sítio. `'unsafe-inline'` em `script-src` é o que permite o `onclick`, e
   * o objectivo é tirá-lo (ver `docs/sistema/4.md` §2: 606 handlers medidos).
   *
   * O dono é `renderWidgetbarPresets()`, em `app/static/js/pagina-index.js`
   * (linha ~16455), que é registada em `window.renderWidgetbarPresets` pelo
   * mesmo ficheiro. `app/templates/index.html` carrega esse ficheiro e só o
   * chama — a função não vive no template.
   *
   * POR QUE ISTO NÃO QUEBRA AS OUTRAS PÁGINAS
   * ------------------------------------------
   * Este ficheiro é carregado em `base.html`, ou seja, em TODAS as páginas.
   * `#presets-carousel` só existe no dashboard. Se o dono não estiver
   * registado — outra página, ou o script do dashboard ainda não correu — esta
   * função **não escreve nada** e avisa uma vez. Antes escrevia um botão sem
   * as capacidades; agora não escreve. A degradação é visível, não silenciosa.
   */
  let _delegouSemDono = false;
  function renderPresetsCarousel() {
    const dono = window.renderWidgetbarPresets;
    if (typeof dono !== 'function') {
      if (!_delegouSemDono && document.getElementById('presets-carousel')) {
        _delegouSemDono = true;
        console.warn(
          '[WidgetBar] #presets-carousel existe mas o dono ' +
            '(window.renderWidgetbarPresets) ainda não foi registado. ' +
            'Nada foi escrito, de propósito — havia dois renderizadores ' +
            'para o mesmo sítio e o último a escrever vencia.'
        );
      }
      return;
    }
    dono();
  }

  function formatTimeAgo(ts) {
    const diff = Date.now() - ts;
    const mins = Math.floor(diff / 6e4);
    const hours = Math.floor(diff / 36e5);
    const days = Math.floor(diff / 864e5);
    if (mins < 1) return 'agora';
    if (mins < 60) return `${mins}min`;
    if (hours < 24) return `${hours}h`;
    return `${days}d`;
  }

  // ==========================================
  // PRESET PREVIEW CARD
  // ==========================================
  let presetPreviewTimeout = null;
  let currentPresetPreview = null;

  window.showPresetPreview = function (event, presetKey) {
    clearTimeout(presetPreviewTimeout);

    const btn = event.currentTarget;
    if (!btn) return;

    const presets = window.PRESETS || {};
    const preset = presets[presetKey];
    if (!preset) return;

    const card = document.getElementById('preset-preview-card');
    if (!card) return;

    // Generate preview content
    card.innerHTML = generatePresetPreviewContent(presetKey, preset);
    card.setAttribute('aria-hidden', 'false');

    // Position the card
    positionPresetPreviewCard(card, btn);

    // Show with animation
    presetPreviewTimeout = setTimeout(() => {
      card.classList.add('visible');
      currentPresetPreview = presetKey;
    }, 150);
  };

  window.hidePresetPreview = function () {
    clearTimeout(presetPreviewTimeout);

    const card = document.getElementById('preset-preview-card');
    if (!card) return;

    card.classList.remove('visible');
    card.setAttribute('aria-hidden', 'true');
    currentPresetPreview = null;

    // Clear content after animation
    setTimeout(() => {
      if (!card.classList.contains('visible')) {
        card.innerHTML = '';
      }
    }, 200);
  };

  function generatePresetPreviewContent(presetKey, preset) {
    // preset.widgets is an object with widget IDs as keys
    const widgetIds = preset.widgets ? Object.keys(preset.widgets) : [];
    const widgetCount = widgetIds.length;

    // Generate a mini grid preview based on the preset's widgets
    const previewWidgets = widgetIds
      .slice(0, 8)
      .map((w, i) => {
        const color = i % 2 === 0 ? 'rgba(15,157,110,0.2)' : 'rgba(59,130,246,0.15)';
        return `<span style="background:${color}; border-radius:3px;"></span>`;
      })
      .join('');

    const emptySlots = 8 - widgetCount;
    const emptyHtml =
      emptySlots > 0
        ? '<span style="background:rgba(0,0,0,0.03); border-radius:3px;"></span>'.repeat(emptySlots)
        : '';

    return `
            <div class="preview-header">
                <div class="preview-icon">
                    ${presetIconHtml(preset)}
                </div>
                <div>
                    <div class="preview-title">${preset.label}</div>
                    <div class="preview-subtitle">${
                      preset.description || `${widgetCount} widgets`
                    }</div>
                </div>
            </div>
            <div class="preview-image">
                <div class="preset-block-tooltip-preview-grid" style="width:100%;height:100%;padding:12px;">
                    ${previewWidgets}${emptyHtml}
                </div>
            </div>
            <div class="preview-meta">
                <span><i class="bi bi-grid-3x3-gap"></i> ${widgetCount} widgets</span>
                <span><i class="bi bi-layout-sidebar"></i> ${preset.category || 'Custom'}</span>
            </div>
            <div class="preview-actions">
                <button class="preview-btn primary" onclick="applyPreset('${presetKey}'); hidePresetPreview();">
                    <i class="bi bi-check"></i> Aplicar
                </button>
                <button class="preview-btn" onclick="openPresetModal(); hidePresetPreview();">
                    <i class="bi bi-pencil"></i> Editar
                </button>
            </div>
        `;
  }

  function positionPresetPreviewCard(card, btn) {
    const rect = btn.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Default: above the button
    let left = rect.left + rect.width / 2 - cardRect.width / 2;
    let top = rect.top - cardRect.height - 12;

    // Adjust horizontal
    if (left < 8) left = 8;
    if (left + cardRect.width > viewportWidth - 8) {
      left = viewportWidth - cardRect.width - 8;
    }

    // Adjust vertical - if not enough space above, show below
    if (top < 8) {
      top = rect.bottom + 12;
      // Update arrow direction
      card.classList.add('arrow-top');
      card.classList.remove('arrow-bottom');
    } else {
      card.classList.add('arrow-bottom');
      card.classList.remove('arrow-top');
    }

    card.style.left = left + 'px';
    card.style.top = top + 'px';
  }

  // ==========================================
  // CUSTOM MODE (enhance existing function)
  // ==========================================
  const originalToggleCustomMode = window.toggleCustomMode;
  window.toggleCustomMode = function () {
    const willExit = state.isCustomMode;
    const willEnter = !state.isCustomMode;
    // Ao ENTRAR em edição: guarda JSON snapshot para o Restaurar + setas undo/redo
    if (willEnter && typeof window.pushLayoutHistory === 'function') {
      try {
        window.pushLayoutHistory();
      } catch (e) {}
    }
    // Botão vira "Salvar" no modo edição: salva o layout ao sair e empilha histórico
    if (willExit && typeof window.saveCurrentPreset === 'function') {
      try {
        window.saveCurrentPreset();
      } catch (e) {}
      if (typeof window.pushLayoutHistory === 'function') {
        try {
          window.pushLayoutHistory();
        } catch (e) {}
      }
    }
    state.isCustomMode = !state.isCustomMode;
    const btn = document.getElementById('custom-mode-btn');
    const section = document.getElementById('edit-mode-section');
    const appbar = document.getElementById('dashboard-appbar');

    /*
     * No celular a barra de edicao flutua ACIMA da widget bar, e para isso ela
     * precisa de position:fixed de verdade. So que dentro do #widgetbar-right-section
     * (que tem `contain: layout`) e do #dashboard-appbar (que tem backdrop-filter)
     * o fixed NAO e relativo a viewport: e relativo ao ancestral. Medido antes
     * desta correcao: a barra saia com 62px de largura em vez de 377, porque o
     * left:8px/right:8px resolvia contra um pai de 62px.
     *
     * A correcao e estrutural, e nao um hack de CSS: enquanto for para sair de
     * dentro da widget bar, o elemento vai para o <body>. No desktop volta para
     * o lugar original. Nao ha CSS dependente do aninhamento (verificado), e
     * assim o contain/backdrop-filter ficam intactos.
     */
    const CELULAR = window.matchMedia('(max-width: 900px)').matches;
    if (section) {
      if (state.isCustomMode && CELULAR) {
        if (section.parentElement !== document.body) {
          section.dataset.paiOriginal = '';
          document.body.appendChild(section);
        }
      } else if (!state.isCustomMode && section.parentElement === document.body) {
        const alvo = document.getElementById('widgetbar-right-section');
        if (alvo) alvo.appendChild(section);
      }
    }

    // Sincroniza flags globais (index.html é fonte da verdade para drag/resize)
    if (typeof window.__setEditFlags === 'function') {
      window.__setEditFlags(state.isCustomMode);
    } else {
      if (window.widgetbarState) window.widgetbarState.isCustomMode = state.isCustomMode;
      window.widgetEditMode = state.isCustomMode;
      window.customMode = state.isCustomMode;
    }
    if (window.widgetbarState) window.widgetbarState.isCustomMode = state.isCustomMode;

    // Gear → Check (Salvar) no modo edição
    if (btn) {
      btn.classList.toggle('active', state.isCustomMode);
      if (btn.querySelector('i')) {
        btn.querySelector('i').className = `bi bi-${state.isCustomMode ? 'check2' : 'gear'}`;
      }
      btn.title = state.isCustomMode ? 'Salvar Layout' : 'Modo Edição';
      btn.setAttribute('aria-pressed', state.isCustomMode);
      btn.setAttribute('aria-label', state.isCustomMode ? 'Salvar Layout' : 'Modo Edição');
    }
    if (section) section.classList.toggle('hidden', !state.isCustomMode);
    if (appbar) appbar.classList.toggle('editing', state.isCustomMode);

    // Sincroniza matriz via helper exposto (sem double-toggle)
    if (typeof window.syncWidgetEditDOM === 'function') {
      window.syncWidgetEditDOM(state.isCustomMode);
    } else {
      document.querySelectorAll('.bento-block').forEach(function (el) {
        el.classList.toggle('widget-edit-mode', state.isCustomMode);
      });
      if (state.isCustomMode && typeof window.initWidgetDragging === 'function') {
        setTimeout(function () {
          window.initWidgetDragging();
        }, 0);
      }
    }

    closeSearchMenu();
    // atualiza estado das setas undo/redo
    if (typeof window.updateHistoryButtons === 'function') {
      try {
        setTimeout(window.updateHistoryButtons, 80);
      } catch (e) {}
    }
  };

  function syncCustomModeButton() {
    const btn = document.getElementById('custom-mode-btn');
    const appbar = document.getElementById('dashboard-appbar');
    var shouldBeEdit = !!(
      window.widgetbarState?.isCustomMode ||
      (typeof window.__getEditFlags === 'function' && window.__getEditFlags()) ||
      window.widgetEditMode ||
      window.customMode
    );
    if (btn && shouldBeEdit) {
      state.isCustomMode = true;
      if (window.widgetbarState) window.widgetbarState.isCustomMode = true;
      btn.classList.add('active');
      if (btn.querySelector('i')) btn.querySelector('i').className = 'bi bi-check2';
      btn.title = 'Salvar Layout';
      btn.setAttribute('aria-pressed', 'true');
      btn.setAttribute('aria-label', 'Salvar Layout');
      const section = document.getElementById('edit-mode-section');
      if (section) section.classList.remove('hidden');
      if (appbar) appbar.classList.add('editing');
      // Garante que a matriz também entre em edição se veio de outro caminho
      if (typeof window.syncWidgetEditDOM === 'function') window.syncWidgetEditDOM(true);
    }
  }

  // ==========================================
  // SEARCH MENU
  // ==========================================
  window.toggleSearchMenu = function () {
    state.isSearchOpen = !state.isSearchOpen;
    const menu = document.getElementById('search-menu');
    const btn = document.querySelector('.widgetbar-search-btn');
    if (menu) {
      menu.classList.toggle('open', state.isSearchOpen);
      menu.setAttribute('aria-hidden', state.isSearchOpen ? 'false' : 'true');
    }
    if (btn) {
      btn.classList.toggle('active', state.isSearchOpen);
      btn.setAttribute('aria-expanded', state.isSearchOpen ? 'true' : 'false');
    }
    // Fecha Quick Settings se abrir Start (Windows: Start fecha System Tray)
    if (state.isSearchOpen && typeof window.closeQuickSettings === 'function')
      window.closeQuickSettings();
    if (state.isSearchOpen) {
      setTimeout(() => {
        document.getElementById('search-menu-input')?.focus();
        populateIntelligentSearchMenu();
      }, 50);
    }
  };

  window.closeSearchMenu = function () {
    state.isSearchOpen = false;
    const menu = document.getElementById('search-menu');
    const btn = document.querySelector('.widgetbar-search-btn');
    if (menu) {
      menu.classList.remove('open');
      menu.setAttribute('aria-hidden', 'true');
    }
    if (btn) {
      btn.classList.remove('active');
      btn.setAttribute('aria-expanded', 'false');
    }
  };

  window.handleSearchMenuKey = function (e) {
    if (e.key === 'Escape') {
      closeSearchMenu();
    } else if (e.key === 'Enter') {
      const firstItem = document.querySelector('.search-menu-item[data-widget]');
      if (firstItem) firstItem.click();
    }
  };

  window.addWidgetFromSearch = function (widgetId) {
    window.addWidget?.(widgetId);
    closeSearchMenu();
    window.WidgetIntelligence?.addRecent?.(widgetId, { source: 'search-menu' });
    window.WidgetIntelligence?.trackUsage?.(widgetId, 'add-from-search');
  };

  // ==========================================
  // DRAG SLIDERS - FLUIDOS
  // ==========================================
  function initDragSliders() {
    document.querySelectorAll('.drag-slider').forEach((slider) => {
      if (slider.dataset.initialized) return;
      slider.dataset.initialized = 'true';

      const values = slider.dataset.values.split(',');
      const index = parseInt(slider.dataset.index) || 0;
      let currentIndex = index;
      let isDragging = false;
      let dragStartPct = 0;

      const thumb = slider.querySelector('.drag-slider-thumb');
      const fill = slider.querySelector('.drag-slider-fill');
      const label = slider.querySelector('.drag-slider-thumb span');

      function updateUI(idx, animate = true) {
        currentIndex = Math.max(0, Math.min(values.length - 1, idx));
        const pct = values.length > 1 ? (currentIndex / (values.length - 1)) * 100 : 0;
        if (thumb) {
          thumb.style.transition = animate ? 'left 0.1s ease-out' : 'none';
          thumb.style.left = `${pct}%`;
          thumb.dataset.value = values[currentIndex];
          thumb.setAttribute('data-value', values[currentIndex]);
        }
        if (fill) {
          fill.style.transition = animate ? 'width 0.1s ease-out' : 'none';
          fill.style.width = `${pct}%`;
        }
        if (label) label.textContent = values[currentIndex];
        slider.setAttribute('aria-valuenow', String(currentIndex));
        slider.setAttribute('aria-valuetext', values[currentIndex]);

        if (slider.id === 'period-slider') {
          window.widgetbarState = window.widgetbarState || {};
          window.widgetbarState.chartPeriod = values[currentIndex];
          window.updateChartsForPeriod?.(values[currentIndex]);
        } else if (slider.id === 'financial-slider') {
          window.widgetbarState = window.widgetbarState || {};
          window.widgetbarState.financialFilter = values[currentIndex];
          window.updateFinancialFilter?.(values[currentIndex]);
        }
      }

      // Click on track - smooth animate to position
      slider.addEventListener('click', (e) => {
        if (e.target === thumb || e.target.closest('.drag-slider-thumb')) return;
        const rect = slider.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const idx = Math.round(pct * (values.length - 1));
        updateUI(idx, true);
      });

      // Fluid drag on thumb — atualiza badge (data-value) em tempo real
      thumb?.addEventListener('mousedown', (e) => {
        isDragging = true;
        dragStartPct =
          (e.clientX - slider.getBoundingClientRect().left) / slider.getBoundingClientRect().width;
        e.preventDefault();
        document.body.style.userSelect = 'none';
        if (thumb) thumb.style.transition = 'none';
        if (fill) fill.style.transition = 'none';
      });

      document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        const rect = slider.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));

        // FLUID: atualiza posição contínua sem snap durante o arrasto
        const fluidPct = pct * 100;
        if (thumb) thumb.style.left = `${fluidPct}%`;
        if (fill) fill.style.width = `${fluidPct}%`;

        // Atualiza NOME do badge em tempo real (igual ao salto final) — antes só mudava span oculto
        const fluidIdx = pct * (values.length - 1);
        const liveIdx = Math.round(fluidIdx);
        const clampedLive = Math.max(0, Math.min(values.length - 1, liveIdx));
        const liveVal = values[clampedLive];
        if (thumb) {
          thumb.dataset.value = liveVal;
          thumb.setAttribute('data-value', liveVal);
        }
        if (label) label.textContent = liveVal;
        slider.setAttribute('aria-valuetext', liveVal);
      });

      document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        isDragging = false;
        document.body.style.userSelect = '';
        // SNAP para valor mais próximo com base na posição atual do thumb
        const thumbLeft = parseFloat(thumb.style.left) || 0;
        const finalPct = Math.max(0, Math.min(1, thumbLeft / 100));
        const idx = Math.round(finalPct * (values.length - 1));
        updateUI(idx, true);
      });

      slider.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowRight') {
          e.preventDefault();
          updateUI(currentIndex + 1, true);
        }
        if (e.key === 'ArrowLeft') {
          e.preventDefault();
          updateUI(currentIndex - 1, true);
        }
      });

      slider.setAttribute('tabindex', '0');
      slider.setAttribute('role', 'slider');
      slider.setAttribute(
        'aria-label',
        slider.id === 'period-slider' ? 'Período do gráfico' : 'Filtro financeiro'
      );
      slider.setAttribute('aria-valuemin', '0');
      slider.setAttribute('aria-valuemax', String(values.length - 1));
      // inicializa badge (data-value) e posição — antes ficava vazio até primeiro clique
      updateUI(currentIndex, false);
    });
  }

  // ==========================================
  // DROPDOWNS — delegado para index.html (versão rica com _captureBgOriginal/_captureFontOriginal + centralização)
  // Se index.html já definiu toggleEditDropdown rico, NÃO sobrescreve (era o bug que quebrava cor/tamanho)
  // ==========================================
  if (
    typeof window.toggleEditDropdown === 'function' &&
    window.toggleEditDropdown.toString().indexOf('_captureBgOriginal') !== -1
  ) {
    // index.html versão rica já existe — preserva, não sobrescreve
  } else {
    window.toggleEditDropdown = function (id) {
      document.querySelectorAll('.edit-dropdown').forEach((d) => {
        if (d.id !== id) d.classList.add('hidden');
      });
      const el = document.getElementById(id);
      if (el) el.classList.toggle('hidden');
    };
    window.toggleEditDropdown._isSimple = true;
  }

  window.toggleExportDropdown = function () {
    const el = document.getElementById('export-dropdown');
    if (el) el.classList.toggle('hidden');
  };

  // Document click para fechar edit-dropdowns: só se index.html ainda não instalou o seu (que já trata centralização bg)
  if (!window._editDropdownClickInstalled) {
    document.addEventListener('click', (e) => {
      if (
        !e.target.closest('.edit-dropdown') &&
        !e.target.closest('[onclick*="toggleEditDropdown"]') &&
        !e.target.closest('#export-btn')
      ) {
        document.querySelectorAll('.edit-dropdown').forEach((d) => d.classList.add('hidden'));
      }
    });
    window._editDropdownClickInstalled = true;
  }

  // ==========================================
  // PRESETS — com debounce para evitar multiplos reloads no mesmo clique
  // ==========================================
  window.applyPreset = (function () {
    var _lastApply = { id: null, time: 0 };
    return function (presetId, evt) {
      if (evt && evt.stopPropagation)
        try {
          evt.stopPropagation();
        } catch (e) {}
      var now = Date.now();
      if (_lastApply.id === presetId && now - _lastApply.time < 800) return;
      _lastApply = { id: presetId, time: now };
      const presets = window.PRESETS || {};
      const preset = presets[presetId];
      if (!preset) return;

      document.querySelectorAll('.preset-block').forEach((b) => {
        b.classList.remove('active');
        b.classList.remove('active-preset');
      });
      const btn = document.querySelector(`[data-preset="${presetId}"]`);
      if (btn) {
        btn.classList.add('active');
        btn.classList.add('active-preset');
      }

      if (window.loadPreset) {
        window.loadPreset(presetId);
      }

      window.WidgetIntelligence?.trackUsage?.(`preset-${presetId}`, 'apply');
    };
  })();

  // ==========================================
  // EXPORT OPTIONS
  // ==========================================
  window.toggleExportOption = function (key) {
    window.widgetbarState = window.widgetbarState || {};
    window.widgetbarState.exportOptions = window.widgetbarState.exportOptions || {
      widgets: true,
      period: true,
      filters: true,
    };
    window.widgetbarState.exportOptions[key] = !window.widgetbarState.exportOptions[key];
  };

  // ==========================================
  // SELECTION STATE
  // ==========================================
  window.setActiveWidget = function (widgetId) {
    state.activeWidget = widgetId;
    const editBtn = document.getElementById('edit-selected-btn');
    const delBtn = document.getElementById('delete-selected-btn');
    const hasSelection = !!widgetId;
    if (editBtn) editBtn.disabled = !hasSelection;
    if (delBtn) delBtn.disabled = !hasSelection;
  };

  // ==========================================
  // CONNECTION STATUS
  // ==========================================
  function updateConnectionStatus() {
    const statusEl = document.getElementById('connection-status');
    if (!statusEl) return;
    statusEl.className = navigator.onLine
      ? 'bi bi-wifi text-xs connection-status text-emerald-500'
      : 'bi bi-wifi-off text-xs connection-status text-rose-500';
  }

  window.addEventListener('online', updateConnectionStatus);
  window.addEventListener('offline', updateConnectionStatus);

  // ==========================================
  // PUBLIC API
  // ==========================================
  window.WidgetBarIntelligent = {
    enhance: enhanceWidgetBar,
    populateIntelligentSearchMenu,
    setActiveWidget,
    getActiveWidget: () => state.activeWidget,
    refresh: () => {
      renderPresetsCarousel();
      if (state.isSearchOpen) {
        populateIntelligentSearchMenu();
      }
    },
  };

  // Expose preset preview functions globally for inline event handlers
  window.showPresetPreview = showPresetPreview;
  window.hidePresetPreview = hidePresetPreview;

  // ==========================================
  // INIT
  // ==========================================
  function init() {
    const checkReady = setInterval(() => {
      if (window.widgetbarState !== undefined) {
        clearInterval(checkReady);
        enhanceWidgetBar();
      }
    }, 50);

    setTimeout(() => {
      clearInterval(checkReady);
      enhanceWidgetBar();
    }, 2000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
