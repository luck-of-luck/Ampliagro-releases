/**
 * Smart Presets Modal - One-click Dashboard Layouts
 * Animated preview, categories, customization, AI recommendations
 */
(function () {
  'use strict';

  // Este ficheiro e o widget-bar-intelligent.js partilham o render do icone de
  // preset, porque o preset-base "IA" usa SVG e nao um glifo do Bootstrap. O
  // helper vive em `window` e e definido no widget-bar-intelligent.js; a ordem
  // de carregamento dos dois nao e garantida, por isso ha aqui uma copia de
  // recurso que so entra se o outro ainda nao tiver corrido.
  var presetIconHtml =
    window.presetIconHtml ||
    function (preset, color) {
      if (!preset) return '';
      if (preset.iconSvg)
        return (
          '<span class="preset-svg-icon" style="display:block;width:100%;height:100%">' +
          preset.iconSvg +
          '</span>'
        );
      var style = color ? ' style="color:' + color + '"' : '';
      return '<i class="bi ' + (preset.icon || 'bi-puzzle') + '"' + style + '></i>';
    };
  window.presetIconHtml = presetIconHtml;

  const state = {
    isOpen: false,
    activeCategory: 'all',
    selectedPreset: null,
    previewMode: 'desktop', // desktop, tablet, mobile
    animationFrame: null,
  };

  // ==========================================
  // PRESET DEFINITIONS (enhanced from WidgetIntelligence)
  // ==========================================
  const PRESET_CATEGORIES = [
    { id: 'all', label: 'Todos', icon: 'bi-grid-3x3-gap' },
    { id: 'essenciais', label: 'Essenciais', icon: 'bi-star', color: '#f59e0b' },
    { id: 'financeiro', label: 'Financeiro', icon: 'bi-cash-stack', color: '#0f9d6e' },
    { id: 'agronomico', label: 'Agronômico', icon: 'bi-flower1', color: '#14b8a6' },
    { id: 'pecuaria', label: 'Pecuária', icon: 'bi-heart-pulse', color: '#ec4899' },
    { id: 'apicultura', label: 'Apicultura', icon: 'bi-bug', color: '#f97316' },
    { id: 'operacional', label: 'Operacional', icon: 'bi-tools', color: '#6366f1' },
    { id: 'gestao', label: 'Gestão', icon: 'bi-people', color: '#8b5cf6' },
    { id: 'executivo', label: 'Executivo', icon: 'bi-briefcase', color: '#1e293b' },
  ];

  function getPresets() {
    const basePresets = window.WidgetIntelligence?.getPresets?.() || [];

    // Enhance with category, preview data, tags
    return basePresets.map((p) => ({
      ...p,
      category: categorizePreset(p.id),
      previewWidgets: generatePreviewWidgets(p.widgets),
      tags: p.tags || [],
      isRecommended: isPresetRecommended(p.id),
      difficulty: getPresetDifficulty(p.widgets.length),
      estimatedTime: `${Math.ceil(p.widgets.length * 1.5)} min`,
    }));
  }

  function categorizePreset(id) {
    const map = {
      'visao-geral': 'essenciais',
      'financeiro-completo': 'financeiro',
      'campo-producao': 'agronomico',
      pecuaria: 'pecuaria',
      apicultura: 'apicultura',
      manutencao: 'operacional',
      'equipe-rh': 'gestao',
      executivo: 'executivo',
    };
    return map[id] || 'essenciais';
  }

  function isPresetRecommended(presetId) {
    const context = window.WidgetIntelligence?.getContext?.() || {};
    const role = context.currentRole;
    const culture = context.currentCulture;

    const recommendations = {
      produtor: ['visao-geral', 'financeiro-completo', 'campo-producao'],
      gerente: ['visao-geral', 'financeiro-completo', 'equipe-rh', 'executivo'],
      operario: ['campo-producao', 'manutencao'],
      agronomo: ['campo-producao', 'visao-geral'],
      veterinario: ['pecuaria', 'visao-geral'],
      mecanico: ['manutencao', 'visao-geral'],
      apicultor: ['apicultura', 'visao-geral'],
      servidor: ['executivo', 'financeiro-completo', 'gestao'],
    };
    return (recommendations[role] || []).includes(presetId);
  }

  function getPresetDifficulty(widgetCount) {
    if (widgetCount <= 4) return { label: 'Iniciante', color: '#0f9d6e', icon: 'bi-trophy' };
    if (widgetCount <= 7) return { label: 'Intermediário', color: '#f59e0b', icon: 'bi-award' };
    return { label: 'Avançado', color: '#ec4899', icon: 'bi-gem' };
  }

  function generatePreviewWidgets(widgetIds) {
    return widgetIds
      .map((id) => {
        const type = window.WIDGET_TYPES?.[id];
        if (!type) return null;
        return {
          id,
          title: type.title,
          icon: type.icon,
          size: type.defaultSize || { w: 4, h: 3 },
          category: categorizeWidget(id),
        };
      })
      .filter(Boolean);
  }

  function categorizeWidget(id) {
    if (id.startsWith('kpi-')) return 'kpi';
    if (id.startsWith('chart-')) return 'chart';
    if (id.startsWith('table-')) return 'table';
    if (id.startsWith('list-') || id === 'calendar-widget' || id === 'alerts-widget') return 'list';
    return 'composite';
  }

  // ==========================================
  // RENDER
  // ==========================================
  function render() {
    const panel = document.getElementById('preset-modal-panel');
    if (!panel) return;

    const presets = getPresets();
    const filtered =
      state.activeCategory === 'all'
        ? presets
        : presets.filter((p) => p.category === state.activeCategory);

    let html = `
            <!-- Header -->
            <div class="preset-modal-header">
                <div class="preset-modal-title">
                    <i class="bi bi-layout-three-columns"></i>
                    <span>Presets Inteligentes</span>
                    <span class="preset-count">${filtered.length} layouts</span>
                </div>
                <div class="preset-modal-actions">
                    <select id="preset-device-preview" onchange="setPresetPreviewMode(this.value)" class="preset-device-select">
                        <option value="desktop">Desktop</option>
                        <option value="tablet">Tablet</option>
                        <option value="mobile">Mobile</option>
                    </select>
                    <button onclick="closePresetModal()" class="preset-modal-close"><i class="bi bi-x-lg"></i></button>
                </div>
            </div>

            <!-- Category Tabs -->
            <div class="preset-categories" role="tablist">
                ${PRESET_CATEGORIES.map(
                  (c) => `
                    <button role="tab" class="preset-category-tab ${
                      state.activeCategory === c.id ? 'active' : ''
                    }"
                        onclick="setPresetCategory('${c.id}')" aria-selected="${
                          state.activeCategory === c.id
                        }"
                        style="${c.color ? `--cat-color: ${c.color}` : ''}">
                        <i class="bi ${c.icon}"></i><span>${c.label}</span>
                        ${
                          getCategoryCount(c.id, presets) > 0
                            ? `<span class="preset-cat-count">${getCategoryCount(
                                c.id,
                                presets
                              )}</span>`
                            : ''
                        }
                    </button>
                `
                ).join('')}
            </div>

            <!-- Presets Grid -->
            <div class="presets-grid" id="presets-grid" role="tabpanel">
                ${
                  filtered.length === 0
                    ? renderEmptyCategory()
                    : filtered.map((p) => renderPresetCard(p)).join('')
                }
            </div>

            <!-- Preview Panel (when preset selected) -->
            <div class="preset-preview-panel ${
              state.selectedPreset ? 'visible' : ''
            }" id="preset-preview-panel">
                ${state.selectedPreset ? renderPresetPreview(state.selectedPreset) : ''}
            </div>

            <!-- Footer -->
            <div class="preset-modal-footer">
                <div class="preset-hints">
                    <span><kbd>←→</kbd> Categorias</span>
                    <span><kbd>↑↓</kbd> Navegar</span>
                    <span><kbd>Enter</kbd> Aplicar</span>
                    <span><kbd>Espaço</kbd> Preview</span>
                </div>
            </div>
        `;

    panel.innerHTML = html;
  }

  function getCategoryCount(catId, presets) {
    if (catId === 'all') return presets.length;
    return presets.filter((p) => p.category === catId).length;
  }

  function hexToRgba(hex, a) {
    try {
      var h = hex.replace('#', '');
      if (h.length === 3)
        h = h
          .split('')
          .map(function (ch) {
            return ch + ch;
          })
          .join('');
      if (h.length === 6)
        return (
          'rgba(' +
          parseInt(h.slice(0, 2), 16) +
          ',' +
          parseInt(h.slice(2, 4), 16) +
          ',' +
          parseInt(h.slice(4, 6), 16) +
          ',' +
          a +
          ')'
        );
      return hex;
    } catch (e) {
      return hex;
    }
  }
  function renderPresetCard(preset) {
    const difficulty = preset.difficulty;
    const isRec = preset.isRecommended;
    const isSelected = state.selectedPreset?.id === preset.id;
    var catColor = getCategoryColor(preset.category);
    var sh = /^#([0-9a-fA-F]{3,8})$/.test(catColor)
      ? 'box-shadow:0 6px 18px ' +
        hexToRgba(catColor, 0.18) +
        ', 0 2px 6px ' +
        hexToRgba(catColor, 0.12) +
        ';'
      : '';
    // fundo sutil por categoria quando selecionado
    var bg =
      isSelected && /^#([0-9a-fA-F]{3,8})$/.test(catColor)
        ? 'background:' + hexToRgba(catColor, 0.06) + ';'
        : '';

    return `
            <div class="preset-card ${isSelected ? 'selected' : ''} ${isRec ? 'recommended' : ''}"
                 data-id="${preset.id}" onclick="selectPreset('${preset.id}')"
                 onmouseenter="hoverPreset('${preset.id}')"
                 role="option" aria-selected="${isSelected}" style="${bg}${sh}">
                <div class="preset-card-header">
                    <div class="preset-card-icon" style="background: ${catColor}">
                        ${presetIconHtml(preset)}
                    </div>
                    ${isRec ? '<span class="preset-badge rec">Recomendado</span>' : ''}
                </div>
                <div class="preset-card-body">
                    <h4 class="preset-card-title">${preset.name}</h4>
                    <p class="preset-card-desc">${preset.description}</p>
                    <div class="preset-card-meta">
                        <span class="preset-meta-item">
                            <i class="bi bi-puzzle"></i> ${preset.widgets.length} widgets
                        </span>
                        <span class="preset-meta-item">
                            <i class="bi bi-clock"></i> ${preset.estimatedTime}
                        </span>
                    </div>
                    <div class="preset-card-tags">
                        ${preset.tags
                          .slice(0, 3)
                          .map((t) => `<span class="preset-tag">${t}</span>`)
                          .join('')}
                        ${
                          preset.tags.length > 3
                            ? `<span class="preset-tag more">+${preset.tags.length - 3}</span>`
                            : ''
                        }
                    </div>
                </div>
                <div class="preset-card-footer">
                    <span class="preset-difficulty" style="background: ${difficulty.color}">
                        <i class="bi ${difficulty.icon}"></i> ${difficulty.label}
                    </span>
                    <div class="preset-mini-preview" id="mini-preview-${preset.id}"></div>
                </div>
            </div>
        `;
  }

  function getCategoryColor(category) {
    const cat = PRESET_CATEGORIES.find((c) => c.id === category);
    return cat?.color || '#0f9d6e';
  }

  function renderPresetPreview(preset) {
    const previewWidgets = preset.previewWidgets;
    const deviceClass = `preview-${state.previewMode}`;

    return `
            <div class="preset-preview-header">
                <h3><span style="display:inline-block;width:1.15em;height:1.15em;vertical-align:-0.2em">${presetIconHtml(
                  preset
                )}</span> ${preset.name}</h3>
                <p>${preset.description}</p>
                <div class="preview-device-toggle">
                    <button class="${
                      state.previewMode === 'desktop' ? 'active' : ''
                    }" onclick="setPresetPreviewMode('desktop')" title="Desktop"><i class="bi bi-monitor"></i></button>
                    <button class="${
                      state.previewMode === 'tablet' ? 'active' : ''
                    }" onclick="setPresetPreviewMode('tablet')" title="Tablet"><i class="bi bi-tablet"></i></button>
                    <button class="${
                      state.previewMode === 'mobile' ? 'active' : ''
                    }" onclick="setPresetPreviewMode('mobile')" title="Mobile"><i class="bi bi-phone"></i></button>
                </div>
            </div>
            <div class="preset-preview-canvas ${deviceClass}" id="preset-preview-canvas">
                ${renderPreviewGrid(previewWidgets)}
            </div>
            <div class="preset-preview-actions">
                <button onclick="customizePreset('${preset.id}')" class="preset-btn secondary">
                    <i class="bi bi-sliders"></i> Personalizar
                </button>
                <button onclick="applyPreset('${
                  preset.id
                }'); closePresetModal()" class="preset-btn primary">
                    <i class="bi bi-check-lg"></i> Aplicar Layout
                </button>
            </div>
        `;
  }

  function renderPreviewGrid(widgets) {
    // Generate a visual grid representation
    const cols = state.previewMode === 'mobile' ? 4 : state.previewMode === 'tablet' ? 8 : 12;

    return widgets
      .map((w, i) => {
        const x = (i * 3) % cols;
        const y = Math.floor((i * 3) / cols) * 2;
        const w_ = Math.min(w.size.w, cols - x);
        const h_ = w.size.h;

        return `
                <div class="preview-widget" style="
                    grid-column: ${x + 1} / span ${w_};
                    grid-row: ${y + 1} / span ${h_};
                    background: ${getCategoryColor(w.category)};
                ">
                    <div class="preview-widget-content">
                        <i class="bi ${w.icon}"></i>
                        <span>${w.title}</span>
                    </div>
                </div>
            `;
      })
      .join('');
  }

  function renderEmptyCategory() {
    return `
            <div class="preset-empty">
                <i class="bi bi-funnel"></i>
                <h4>Nenhum preset nesta categoria</h4>
                <p>Tente outra categoria ou crie seu próprio layout</p>
            </div>
        `;
  }

  // ==========================================
  // ANIMATIONS
  // ==========================================
  function animatePreviewEntrance() {
    const canvas = document.getElementById('preset-preview-canvas');
    if (!canvas) return;

    const widgets = canvas.querySelectorAll('.preview-widget');
    widgets.forEach((w, i) => {
      w.style.opacity = '0';
      w.style.transform = 'scale(0.9) translateY(10px)';
      w.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      w.style.transitionDelay = `${i * 50}ms`;

      requestAnimationFrame(() => {
        w.style.opacity = '1';
        w.style.transform = 'scale(1) translateY(0)';
      });
    });
  }

  // ==========================================
  // INTERACTIONS
  // ==========================================
  window.selectPreset = function (presetId) {
    const presets = getPresets();
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;

    state.selectedPreset = preset;
    render();

    // Animate preview
    setTimeout(animatePreviewEntrance, 50);

    // Track
    window.WidgetIntelligence?.trackUsage?.(`preset-${presetId}`, 'preview');
  };

  window.hoverPreset = function (presetId) {
    // Render mini preview
    const presets = getPresets();
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;

    const container = document.getElementById(`mini-preview-${presetId}`);
    if (!container) return;

    container.innerHTML = preset.previewWidgets
      .map(
        (w) => `
            <div class="mini-widget" style="background: ${getCategoryColor(w.category)}">
                <i class="bi ${w.icon}"></i>
            </div>
        `
      )
      .join('');
  };

  window.setPresetCategory = function (catId) {
    state.activeCategory = catId;
    state.selectedPreset = null;
    render();
  };

  window.setPresetPreviewMode = function (mode) {
    state.previewMode = mode;
    if (state.selectedPreset) {
      const panel = document.getElementById('preset-preview-panel');
      panel.innerHTML = renderPresetPreview(state.selectedPreset);
      animatePreviewEntrance();
    }
    // Update select
    document.getElementById('preset-device-preview').value = mode;
  };

  window.customizePreset = function (presetId) {
    // Open widget palette with preset widgets pre-selected
    const presets = getPresets();
    const preset = presets.find((p) => p.id === presetId);
    if (!preset) return;

    closePresetModal();
    setTimeout(() => {
      window.openWidgetPalette?.();
      // Pre-select preset widgets
      preset.widgets.forEach((id) => {
        window.WidgetIntelligence?.addRecent?.(id, { source: 'preset-customize' });
      });
    }, 300);
  };

  // ==========================================
  // OPEN/CLOSE — Works with the Liquid Glass template modal
  // Template IDs: #preset-modal-overlay, #preset-modal, #preset-modal-box
  // ==========================================
  window.openPresetModal = function () {
    const overlay = document.getElementById('preset-modal-overlay');
    const modal = document.getElementById('preset-modal');
    const box = document.getElementById('preset-modal-box');

    if (!modal || !box) return;

    state.isOpen = true;
    state.activeCategory = 'all';
    state.selectedPreset = null;
    state.previewMode = 'desktop';

    // Show overlay and modal
    if (overlay) {
      overlay.classList.remove('hidden');
      overlay.classList.add('flex');
    }
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Animate in
    box.style.opacity = '0';
    box.style.transform = 'scale(0.95) translateY(10px)';
    requestAnimationFrame(() => {
      box.style.transition = 'all 0.35s cubic-bezier(0.16, 1, 0.3, 1)';
      box.style.opacity = '1';
      box.style.transform = 'scale(1) translateY(0)';
    });

    document.body.style.overflow = 'hidden';
    window.WidgetIntelligence?.trackUsage?.('preset-modal', 'open');
  };

  window.closePresetModal = function () {
    const overlay = document.getElementById('preset-modal-overlay');
    const modal = document.getElementById('preset-modal');
    const box = document.getElementById('preset-modal-box');

    if (!modal) return;

    // Animate out
    if (box) {
      box.style.transition = 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)';
      box.style.opacity = '0';
      box.style.transform = 'scale(0.95) translateY(10px)';
    }

    setTimeout(() => {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      if (overlay) {
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
      }
      document.body.style.overflow = '';
    }, 250);

    state.isOpen = false;
  };

  // ==========================================
  // KEYBOARD
  // ==========================================
  document.addEventListener('keydown', (e) => {
    if (!state.isOpen) return;

    const presets = getPresets();
    const filtered =
      state.activeCategory === 'all'
        ? presets
        : presets.filter((p) => p.category === state.activeCategory);

    const cards = document.querySelectorAll('.preset-card');
    const currentIdx = state.selectedPreset
      ? filtered.findIndex((p) => p.id === state.selectedPreset.id)
      : -1;

    switch (e.key) {
      case 'Escape':
        closePresetModal();
        break;
      case 'ArrowRight':
        if (e.ctrlKey) {
          // Next category
          const cats = PRESET_CATEGORIES.map((c) => c.id);
          const idx = cats.indexOf(state.activeCategory);
          setPresetCategory(cats[(idx + 1) % cats.length]);
        } else if (currentIdx >= 0) {
          // Next preset
          const next = Math.min(currentIdx + 1, filtered.length - 1);
          selectPreset(filtered[next].id);
        }
        break;
      case 'ArrowLeft':
        if (e.ctrlKey) {
          const cats = PRESET_CATEGORIES.map((c) => c.id);
          const idx = cats.indexOf(state.activeCategory);
          setPresetCategory(cats[(idx - 1 + cats.length) % cats.length]);
        } else if (currentIdx > 0) {
          selectPreset(filtered[currentIdx - 1].id);
        }
        break;
      case 'ArrowDown':
        if (currentIdx >= 0 && currentIdx < filtered.length - 1) {
          e.preventDefault();
          selectPreset(filtered[currentIdx + 1].id);
        }
        break;
      case 'ArrowUp':
        if (currentIdx > 0) {
          e.preventDefault();
          selectPreset(filtered[currentIdx - 1].id);
        }
        break;
      case 'Enter':
        if (state.selectedPreset) {
          e.preventDefault();
          applyPreset(state.selectedPreset.id);
          closePresetModal();
        }
        break;
      case ' ':
        if (state.selectedPreset) {
          e.preventDefault();
          // Toggle preview panel
        }
        break;
      case 'Tab':
        if (e.shiftKey) {
          // Focus category tabs
        }
        break;
    }
  });

  // ==========================================
  // INIT — Modal HTML is provided by the Django template (preset_modal.html)
  // No injection needed; the template already has the Liquid Glass modal.
  // ==========================================
  function init() {
    // No-op: modal is rendered server-side via {% include 'partials/preset_modal.html' %}
    console.log('[WidgetPresets] Using template-based Liquid Glass modal');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
