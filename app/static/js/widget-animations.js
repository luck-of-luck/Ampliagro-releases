/**
 * Widget Intelligence System - Animations & Micro-interactions
 * Framer Motion inspired CSS animations
 */
(function () {
  'use strict';

  // ==========================================
  // INJECT STYLES
  // ==========================================
  const styles = document.createElement('style');
  styles.id = 'widget-intelligence-styles';
  styles.textContent = `
/* ============================================
   COMMAND PALETTE ANIMATIONS
   ============================================ */
#command-palette {
    animation: fadeIn 0.15s ease-out;
}
#command-palette-panel {
    animation: slideUp 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}
@keyframes slideUp {
    from { opacity: 0; transform: scale(0.95) translateY(10px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.cp-item {
    transition: background 0.1s ease, transform 0.1s ease;
}
.cp-item:hover {
    background: color-mix(in srgb, var(--theme-accent) 8%, transparent);
    transform: translateX(4px);
}
.cp-item.selected {
    background: color-mix(in srgb, var(--theme-accent) 12%, transparent);
}
.cp-item:focus-visible {
    outline: 2px solid var(--theme-accent);
    outline-offset: -2px;
}
.cp-fav-btn {
    transition: transform 0.15s ease, color 0.15s ease;
}
.cp-fav-btn:hover {
    transform: scale(1.2);
    color: var(--theme-accent);
}
.cp-fav-btn.active {
    color: #f59e0b;
}

.cp-category-label {
    animation: fadeIn 0.2s ease;
}

/* ============================================
   WIDGET BAR ANIMATIONS
   ============================================ */
#widget-bar {
    animation: slideDown 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes slideDown {
    from { opacity: 0; transform: translateY(-100%); }
    to { opacity: 1; transform: translateY(0); }
}

.widgetbar-pill-icon,
.widgetbar-search-btn,
.widgetbar-pill,
.edit-pill {
    transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}
.widgetbar-pill-icon:hover,
.widgetbar-search-btn:hover,
.widgetbar-pill:hover,
.edit-pill:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.widgetbar-pill-icon.active,
.widgetbar-search-btn.active {
    background: color-mix(in srgb, var(--theme-accent) 15%, transparent);
    color: var(--theme-accent);
}

.preset-block {
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.preset-block:hover {
    transform: scale(1.08) translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.preset-block.active {
    animation: pulseRing 2s ease-in-out infinite;
}
@keyframes pulseRing {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--theme-accent) 40%, transparent); }
    50% { box-shadow: 0 0 0 8px transparent; }
}

.search-menu {
    animation: slideDown 0.15s ease-out;
    transform-origin: top center;
}
.search-menu-item {
    transition: background 0.1s ease, padding-left 0.15s ease;
}
.search-menu-item:hover {
    background: color-mix(in srgb, var(--theme-accent) 8%, transparent);
    padding-left: 16px;
}

.edit-pill.primary {
    animation: subtlePulse 3s ease-in-out infinite;
}
@keyframes subtlePulse {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--theme-accent) 40%, transparent); }
    50% { box-shadow: 0 0 0 4px transparent; }
}

.drag-slider-thumb {
    transition: left 0.1s ease, transform 0.1s ease;
}
.drag-slider-thumb:active {
    transform: scale(1.3);
}
.drag-slider-fill {
    transition: width 0.15s ease-out;
}

.edit-dropdown {
    animation: dropdownIn 0.15s ease-out;
    transform-origin: top right;
}
@keyframes dropdownIn {
    from { opacity: 0; transform: scale(0.95) translateY(-4px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.widgetbar-status {
    transition: opacity 0.2s ease;
}

/* ============================================
   WIDGET PALETTE ANIMATIONS
   ============================================ */
#widget-palette-modal {
    animation: fadeIn 0.2s ease;
}
#widget-palette-panel {
    animation: slideInRight 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes slideInRight {
    from { opacity: 0; transform: translateX(100%); }
    to { opacity: 1; transform: translateX(0); }
}

.palette-card {
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.palette-card:hover {
    transform: translateX(4px) scale(1.01);
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
}
.palette-card.selected {
    border-color: var(--theme-accent);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--theme-accent) 20%, transparent);
    background: color-mix(in srgb, var(--theme-accent) 5%, transparent);
}
.palette-card.dragging {
    opacity: 0.5;
    transform: rotate(3deg) scale(1.02);
    box-shadow: 0 12px 32px rgba(0,0,0,0.15);
}

.palette-card-icon {
    transition: transform 0.2s ease;
}
.palette-card:hover .palette-card-icon {
    transform: scale(1.1) rotate(5deg);
}

.palette-fav-btn {
    transition: transform 0.15s ease, color 0.15s ease, background 0.15s ease;
}
.palette-fav-btn:hover {
    transform: scale(1.25);
    background: color-mix(in srgb, var(--theme-accent) 15%, transparent);
}
.palette-fav-btn.active {
    color: #f59e0b;
}

.palette-tab {
    transition: all 0.15s ease;
}
.palette-tab:hover {
    background: color-mix(in srgb, var(--theme-accent) 10%, transparent);
    color: var(--theme-accent);
}

.widget-live-preview {
    animation: previewIn 0.15s ease-out;
    transform-origin: top left;
}
@keyframes previewIn {
    from { opacity: 0; transform: scale(0.9) translateY(-4px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.matrix-drop-overlay {
    animation: fadeIn 0.2s ease;
}
.matrix-drop-overlay .drop-zone-hint {
    animation: bounce 1.5s ease-in-out infinite;
}
@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}

.matrix-container.drop-ready {
    background-image: radial-gradient(circle at center, color-mix(in srgb, var(--theme-accent) 5%, transparent) 0%, transparent 70%);
    animation: pulseBg 2s ease-in-out infinite;
}
@keyframes pulseBg {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}

/* ============================================
   INLINE ADD MENU ANIMATIONS
   ============================================ */
.inline-add-menu {
    animation: popIn 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    transform-origin: top left;
}
@keyframes popIn {
    from { opacity: 0; transform: scale(0.9) translateY(-8px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.inline-add-item {
    transition: all 0.15s ease;
}
.inline-add-item:hover,
.inline-add-item.selected {
    transform: translateX(4px);
    background: color-mix(in srgb, var(--theme-accent) 8%, transparent);
}

.inline-add-icon {
    transition: transform 0.2s ease;
}
.inline-add-item:hover .inline-add-icon {
    transform: scale(1.15) rotate(-5deg);
}

.matrix-drop-hint {
    animation: hintIn 0.3s ease-out;
}
@keyframes hintIn {
    from { opacity: 0; transform: scale(0.8) translateY(8px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}
.matrix-drop-hint.visible {
    animation: hintPulse 2s ease-in-out infinite;
}
@keyframes hintPulse {
    0%, 100% { opacity: 0.8; }
    50% { opacity: 1; }
}

/* ============================================
   PRESET MODAL ANIMATIONS
   ============================================ */
/* Preset modal now uses liquid glass transitions from preset-modal-liquid.css.
   Old animation rules for #preset-modal and #preset-modal-panel removed
   to avoid conflicts with the liquid glass effect. */



.preset-card {
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.preset-card:hover {
    transform: translateY(-4px) scale(1.01);
    box-shadow: 0 16px 40px rgba(0,0,0,0.12);
}
.preset-card.selected {
    border-color: var(--theme-accent);
    box-shadow: 0 0 0 2px var(--theme-accent), 0 16px 40px rgba(0,0,0,0.1);
}
.preset-card.recommended {
    border-color: color-mix(in srgb, var(--theme-accent) 50%, transparent);
}
.preset-card.recommended::before {
    content: '';
    position: absolute;
    top: -2px; left: -2px; right: -2px; bottom: -2px;
    border-radius: inherit;
    background: linear-gradient(135deg, var(--theme-accent), #3ec48f);
    z-index: -1;
    opacity: 0;
    animation: glowPulse 3s ease-in-out infinite;
}
@keyframes glowPulse {
    0%, 100% { opacity: 0; }
    50% { opacity: 0.15; }
}

.mini-widget {
    animation: miniPop 0.3s ease-out backwards;
}
@keyframes miniPop {
    from { opacity: 0; transform: scale(0.5) rotate(-45deg); }
    to { opacity: 1; transform: scale(1) rotate(0); }
}

.preview-widget {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.preview-widget:hover {
    transform: scale(1.02);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
    z-index: 10;
}

.preset-category-tab {
    transition: all 0.2s ease;
}
.preset-category-tab:hover {
    transform: translateY(-2px);
}
.preset-category-tab.active {
    animation: tabSelect 0.3s ease-out;
}
@keyframes tabSelect {
    0% { transform: scale(0.95); }
    50% { transform: scale(1.02); }
    100% { transform: scale(1); }
}

.preset-btn {
    transition: all 0.15s ease;
}
.preset-btn:hover {
    transform: translateY(-1px);
}
.preset-btn:active {
    transform: scale(0.98);
}

/* ============================================
   WIDGET MATRIX ANIMATIONS
   ============================================ */
.bento-block {
    animation: widgetIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) backwards;
}
@keyframes widgetIn {
    from { opacity: 0; transform: scale(0.9) translateY(16px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}

.bento-block.widget-edit-mode {
    animation: editModeIn 0.2s ease-out;
}
@keyframes editModeIn {
    from { box-shadow: 0 0 0 0 color-mix(in srgb, var(--theme-accent) 40%, transparent); }
    to { box-shadow: 0 0 0 2px var(--theme-accent); }
}

.bento-block:not(.widget-edit-mode):hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.resize-handle {
    transition: opacity 0.15s ease, transform 0.15s ease;
}
.widget-edit-mode:hover .resize-handle {
    opacity: 1;
}
.resize-handle:active {
    transform: scale(1.3);
}

/* ============================================
   TOAST NOTIFICATIONS
   ============================================ */
#widget-toast-inner {
    animation: toastIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes toastIn {
    from { opacity: 0; transform: translateY(16px) translateX(-50%); }
    to { opacity: 1; transform: translateY(0) translateX(-50%); }
}
#widget-toast-inner.hiding {
    animation: toastOut 0.2s ease-in forwards;
}
@keyframes toastOut {
    from { opacity: 1; transform: translateY(0) translateX(-50%); }
    to { opacity: 0; transform: translateY(-16px) translateX(-50%); }
}

/* ============================================
   MICRO-INTERACTIONS
   ============================================ */
/* Button press feedback */
button:active,
[role="button"]:active {
    transform: scale(0.97);
    transition: transform 0.05s ease;
}

/* Focus visible for keyboard nav */
:focus-visible {
    outline: 2px solid var(--theme-accent);
    outline-offset: 2px;
}

/* Smooth scrolling for all */
html {
    scroll-behavior: smooth;
}

/* Reduced motion respect */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}

/* ============================================
   STAGGER ANIMATIONS FOR LISTS
   ============================================ */
.stagger-in > * {
    animation: staggerIn 0.3s ease-out backwards;
}
.stagger-in > *:nth-child(1) { animation-delay: 0ms; }
.stagger-in > *:nth-child(2) { animation-delay: 50ms; }
.stagger-in > *:nth-child(3) { animation-delay: 100ms; }
.stagger-in > *:nth-child(4) { animation-delay: 150ms; }
.stagger-in > *:nth-child(5) { animation-delay: 200ms; }
.stagger-in > *:nth-child(6) { animation-delay: 250ms; }
.stagger-in > *:nth-child(7) { animation-delay: 300ms; }
.stagger-in > *:nth-child(8) { animation-delay: 350ms; }
@keyframes staggerIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* ============================================
   LOADING SKELETONS
   ============================================ */
.skeleton {
    background: linear-gradient(90deg,
        color-mix(in srgb, var(--theme-text) 10%, transparent) 25%,
        color-mix(in srgb, var(--theme-text) 20%, transparent) 50%,
        color-mix(in srgb, var(--theme-text) 10%, transparent) 75%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
    border-radius: 4px;
}
@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* ============================================
   SCROLLBAR STYLING
   ============================================ */
.scrollbar-thin::-webkit-scrollbar { width: 6px; height: 6px; }
.scrollbar-thin::-webkit-scrollbar-track { background: transparent; }
.scrollbar-thin::-webkit-scrollbar-thumb {
    background: color-mix(in srgb, var(--theme-text) 30%, transparent);
    border-radius: 3px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
    background: color-mix(in srgb, var(--theme-text) 50%, transparent);
}

/* ============================================
   TOOLTIP ANIMATION
   ============================================ */
[title]:hover::after {
    content: attr(title);
    position: absolute;
    bottom: 100%; left: 50%;
    transform: translateX(-50%);
    padding: 4px 8px;
    background: var(--theme-card);
    color: var(--theme-text);
    font-size: 11px;
    border-radius: 4px;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    border: 1px solid var(--theme-border);
    animation: tooltipIn 0.2s ease-out;
    z-index: 1000;
    pointer-events: none;
    margin-bottom: 4px;
}
@keyframes tooltipIn {
    from { opacity: 0; transform: translateX(-50%) translateY(4px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
`;

  document.head.appendChild(styles);

  // ==========================================
  // TOAST HELPER
  // ==========================================
  window.showWidgetToast = function (message, type = 'success', duration = 3000) {
    const toast = document.getElementById('widget-toast');
    const inner = document.getElementById('widget-toast-inner');
    const msg = document.getElementById('widget-toast-msg');

    if (!toast || !inner || !msg) return;

    const icons = {
      success: 'bi-check-circle',
      error: 'bi-x-circle',
      warning: 'bi-exclamation-triangle',
      info: 'bi-info-circle',
    };
    const colors = {
      success: 'bg-emerald-600',
      error: 'bg-rose-600',
      warning: 'bg-amber-600',
      info: 'bg-blue-600',
    };

    inner.className = `px-4 py-2 rounded-xl ${colors[type]} text-white text-sm font-medium shadow-lg flex items-center gap-2`;
    inner.querySelector('i').className = `bi ${icons[type]} text-base`;
    msg.textContent = message;

    toast.classList.remove('hidden');
    inner.classList.remove('hiding');

    requestAnimationFrame(() => {
      inner.style.transform = 'translateY(0)';
      inner.style.opacity = '1';
    });

    clearTimeout(toast.hideTimeout);
    toast.hideTimeout = setTimeout(() => {
      inner.classList.add('hiding');
      inner.style.transform = 'translateY(-16px)';
      inner.style.opacity = '0';
      setTimeout(() => toast.classList.add('hidden'), 200);
    }, duration);
  };

  // ==========================================
  // INTERSECTION OBSERVER FOR SCROLL ANIMATIONS
  // ==========================================
  function initScrollAnimations() {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: '50px' }
    );

    document
      .querySelectorAll('.palette-card, .preset-card, .bento-block, .widget-card')
      .forEach((el) => {
        observer.observe(el);
      });
  }

  // ==========================================
  // INIT
  // ==========================================
  function init() {
    initScrollAnimations();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
