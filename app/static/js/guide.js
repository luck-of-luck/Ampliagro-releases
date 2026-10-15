function guideCsrf() {
  if (typeof getCSRFToken === 'function') return getCSRFToken();
  var m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : '';
}

// ── Categorias nativas Ampliagro (select com busca via datalist) ──
window.GUIDE_CATEGORIAS = [
  'Gr\u00e3os',
  'Hortali\u00e7as',
  'Fruticultura',
  'Citros',
  'Oleaginosas',
  'Fibras',
  'Forrageiras',
  'Pastagem',
  'Caf\u00e9',
  'Cana-de-a\u00e7\u00facar',
  'Florestal',
  'Outro',
];

// ── Meses para janela de plantio (3 primeiras letras) ──
window.GUIDE_MESES = [
  'Jan',
  'Fev',
  'Mar',
  'Abr',
  'Maio',
  'Jun',
  'Jul',
  'Ago',
  'Set',
  'Out',
  'Nov',
  'Dez',
];

// ── CSS injetado uma vez para o novo layout de m\u00f3dulos / inputs h\u00edbridos ──
var GUIDE_PANEL_CSS =
  '' +
  '/* ===== DESIGN SYSTEM: Premium Guide Panel — esmeralda / branco / preto (alinhado a soft-ui --cor-*) ===== */' +
  ':root{--gc-teal-900:var(--cor-primaria);--gc-teal-700:var(--cor-primaria);--gc-teal-600:var(--cor-primaria);--gc-teal-500:var(--cor-primaria);--gc-teal-400:color-mix(in srgb,var(--cor-primaria) 18%, transparent);--gc-teal-100:var(--cor-hover);--gc-teal-50:color-mix(in srgb,var(--cor-hover) 60%, #fff);' +
  '--gc-coffee-800:var(--cor-texto);--gc-coffee-700:var(--cor-texto-suave);--gc-coffee-500:var(--cor-texto-fraco);--gc-coffee-300:var(--cor-borda);--gc-coffee-100:var(--cor-fundo-card-aninhado);' +
  '--gc-green:var(--cor-primaria);--gc-amber:var(--cor-alerta);--gc-red:var(--cor-erro);--gc-blue:var(--cor-primaria);' +
  '--gc-ink-900:var(--cor-texto);--gc-ink-800:var(--cor-texto);--gc-ink-700:var(--cor-texto-suave);--gc-ink-600:var(--cor-texto-suave);--gc-ink-500:var(--cor-texto-fraco);--gc-ink-400:var(--cor-texto-fraco);--gc-ink-200:var(--cor-borda);--gc-ink-100:var(--cor-fundo-card-aninhado);--gc-ink-50:var(--cor-fundo);' +
  '--gc-r-sm:8px;--gc-r-md:12px;--gc-r-lg:12px;--gc-r-xl:16px;' +
  '--gc-shadow-sm:0 1px 2px var(--cor-sombra);--gc-shadow-md:0 6px 20px var(--cor-sombra),0 1px 3px var(--cor-sombra);--gc-shadow-lg:0 20px 48px var(--cor-sombra),0 8px 24px rgba(0,0,0,.12);' +
  '--gc-ring:0 0 0 3px var(--cor-hover);}' +
  '/* ===== Panel Card — centralizado premium (esmeralda/branco/preto) ===== */' +
  '#culturaDetail.gc-editor-panel{max-width:1180px;width:min(1180px,95vw);max-height:min(90vh,920px);border-radius:var(--gc-r-xl);box-shadow:var(--gc-shadow-lg);background:var(--cor-fundo-card);border:1px solid var(--cor-borda);overflow:hidden;display:flex;flex-direction:column;}' +
  'html.dark, html.custom-theme #culturaDetail.gc-editor-panel{background:var(--cor-fundo-card);border-color:var(--cor-borda);}' +
  '#culturaDetail.gc-editor-panel .detail-body{padding:0;overflow:auto;overscroll-behavior:contain;flex:1;min-height:0;}' +
  '/* ===== Context Bar ===== */' +
  '.gc-context-bar{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid var(--gc-ink-100);}' +
  'html.dark, html.custom-theme .gc-context-bar, html.custom-theme .gc-context-bar{border-color:var(--cor-borda);}' +
  '.gc-context-left{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--gc-ink-600);}' +
  '.gc-brand-mark{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--gc-teal-500),var(--gc-teal-700));display:flex;align-items:center;justify-content:center;color:#fff;font-family:Sora,sans-serif;font-weight:800;font-size:13px;box-shadow:var(--gc-shadow-sm);}' +
  '.gc-brand-name{font-family:Sora,sans-serif;font-weight:700;color:var(--gc-ink-900);font-size:14px;}' +
  'html.dark, html.custom-theme .gc-brand-name{color:#fff;}' +
  '.gc-crumb-sep{color:var(--gc-ink-400);}' +
  '.gc-crumb{color:var(--gc-ink-600);}' +
  '.gc-crumb-current{color:var(--gc-teal-700);font-weight:600;}' +
  '/* ===== Hero Section — esmeralda minimal ===== */' +
  '.gc-hero{position:relative;padding:22px 24px 18px;background:linear-gradient(135deg, var(--cor-primaria) 0%, color-mix(in srgb, var(--cor-primaria) 85%, var(--cor-fundo-card)) 45%, var(--cor-fundo-card) 100%);border-bottom:1px solid var(--cor-borda);}' +
  'html.dark, html.custom-theme .gc-hero{background:linear-gradient(135deg, var(--cor-primaria) 0%, color-mix(in srgb, var(--cor-primaria) 70%, var(--cor-fundo-card)) 50%, var(--cor-fundo-card) 100%);border-color:var(--cor-borda);}' +
  '.gc-hero-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;}' +
  '.gc-hero-id{display:flex;align-items:center;gap:14px;}' +
  '.gc-hero-ava{width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg, var(--cor-primaria), color-mix(in srgb, var(--cor-primaria) 80%, black));display:flex;align-items:center;justify-content:center;box-shadow:0 6px 16px var(--cor-hover);flex-shrink:0;font-size:20px;color:#fff;border:1px solid color-mix(in srgb,var(--cor-primaria) 18%, transparent);}' +
  '.gc-hero-name{font-family:Sora,sans-serif;font-weight:800;font-size:22px;letter-spacing:-.02em;margin:0;color:var(--cor-texto); line-height:1.15;}' +
  'html.dark, html.custom-theme .gc-hero-name{color:var(--cor-texto,#edf3ef);}' +
  '.gc-hero-sub{margin:3px 0 0;color:var(--cor-texto-suave);font-size:12.5px; line-height:1.4;}' +
  'html.dark, html.custom-theme .gc-hero-sub{color:var(--cor-texto-fraco);}' +
  '.gc-hero-editing{display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:11px;font-weight:700;letter-spacing:-.01em;color:var(--cor-primaria);background:var(--cor-hover);border:1px solid color-mix(in srgb,var(--cor-primaria) 14%, transparent);padding:4px 10px 4px 8px;border-radius:100px;}' +
  'html.dark, html.custom-theme .gc-hero-editing{background:color-mix(in srgb,var(--cor-primaria,#54c996) 14%, transparent);color:var(--cor-primaria);border-color:color-mix(in srgb,var(--cor-primaria,#54c996) 18%, transparent);}' +
  '.gc-hero-editing i{font-size:10px;}' +
  '.gc-hero-close{width:36px;height:36px;border-radius:10px;border:1px solid var(--cor-borda);background:var(--cor-fundo-card-aninhado);color:var(--cor-texto-suave);display:flex;align-items:center;justify-content:center;transition:all var(--transicao-rapida);cursor:pointer;flex-shrink:0;}' +
  '.gc-hero-close:hover{background:var(--cor-erro-suave,rgba(189,63,57,.13));color:var(--cor-erro);border-color:color-mix(in srgb,var(--cor-erro) 22%, transparent);}' +
  'html.dark, html.custom-theme .gc-hero-close{background:var(--cor-fundo-card-aninhado);border-color:var(--cor-borda);color:var(--cor-texto-fraco);}' +
  '.gc-hero-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px;}' +
  '.gc-chip{display:inline-flex;align-items:center;gap:6px;background:var(--cor-fundo-card);border:1px solid var(--cor-borda);padding:6px 12px;border-radius:100px;font-size:12px;font-weight:700;letter-spacing:-.01em;color:var(--cor-texto);box-shadow:0 1px 2px var(--cor-sombra);}' +
  'html.dark, html.custom-theme .gc-chip{background:var(--cor-fundo-card-aninhado);border-color:var(--cor-borda);color:var(--cor-texto);}' +
  '.gc-chip i{color:var(--cor-primaria);font-size:12px;}' +
  '.gc-chip.warm i{color:var(--cor-texto-fraco);}' +
  '/* ===== Carousel — esmeralda minimal (sem scroll, wrap responsivo) ===== */' +
  '.gc-carousel-wrap{padding:16px 24px 8px;position:relative;display:flex;flex-direction:column;gap:8px;}' +
  '.gc-carousel-row{display:flex;align-items:center;gap:8px;width:100%;}' +
  '.gc-section-label{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;}' +
  '.gc-section-label h3{font-family:Sora,sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--cor-texto-suave);margin:0;font-weight:800;}' +
  'html.dark, html.custom-theme .gc-section-label h3{color:var(--cor-texto-fraco);}' +
  '.gc-carousel{display:flex;gap:12px;flex-wrap:nowrap;overflow:hidden;padding:4px 4px 12px;flex:1;justify-content:flex-start;}' +
  '.gc-carousel-slider{height:6px;background:var(--cor-fundo-card-aninhado);border-radius:999px;margin:8px 48px 0;position:relative;cursor:pointer;user-select:none;}' +
  '.gc-carousel-thumb{position:absolute;top:0;left:0;height:100%;background:var(--cor-primaria);border-radius:999px;cursor:grab;transition:background .15s, height .15s;min-width:40px;}' +
  '.gc-carousel-thumb:active{cursor:grabbing;height:8px;top:-1px;background:var(--cor-primaria-forte);}' +
  '.gc-carousel-thumb:hover{background:var(--cor-primaria-forte);}' +
  '.gc-carousel-btn{width:36px;height:36px;min-width:36px;border-radius:50%;border:1px solid var(--cor-borda);background:var(--cor-fundo-card);box-shadow:0 4px 12px var(--cor-sombra);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:2;color:var(--cor-primaria);flex-shrink:0;transition:all .15s;}' +
  '.gc-carousel-btn:hover{background:var(--cor-primaria);color:#fff;border-color:var(--cor-primaria);transform:scale(1.05);}' +
  '.gc-carousel-btn:disabled{opacity:.3;cursor:not-allowed;transform:none;}' +
  '.gc-carousel-btn i{font-size:14px;}' +
  '@media(max-width:860px){.gc-carousel{gap:10px;}.gc-car-card{width:160px;min-width:160px;}}' +
  '@media(max-width:480px){.gc-car-card{width:140px;min-width:140px;}}' +
  '.gc-car-card{scroll-snap-align:start;flex:0 0 auto;width:196px;border:1px solid var(--cor-borda);border-radius:12px;padding:14px;background:var(--cor-fundo-card);cursor:pointer;transition:all .16s var(--transicao-rapida);position:relative;box-shadow:0 1px 0 rgba(255,255,255,.6),0 4px 12px var(--cor-sombra);}' +
  'html.dark, html.custom-theme .gc-car-card{background:var(--cor-fundo-card);border-color:var(--cor-borda);}' +
  '.gc-car-card:hover{border-color:color-mix(in srgb,var(--cor-primaria) 28%, var(--cor-borda));transform:translateY(-1px);box-shadow:0 8px 18px var(--cor-sombra);}' +
  '.gc-car-card.active{border-color:var(--cor-primaria);box-shadow:0 0 0 3px var(--cor-primaria-suave),var(--gc-shadow-md);}' +
  '.gc-car-head{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px;}' +
  '.gc-car-zone{display:flex;align-items:center;gap:5px;font-size:12px;font-weight:700;color:var(--cor-texto);}' +
  'html.dark, html.custom-theme .gc-car-zone{color:var(--cor-texto);}' +
  '.gc-car-zone i{color:var(--cor-primaria);font-size:11px;}' +
  '.gc-car-sub{font-size:11px;color:var(--cor-texto-fraco);margin-top:1px;}' +
  '.gc-car-dots{display:flex;gap:4px;margin-left:auto;}' +
  '.gc-car-dots .dot{width:6px;height:6px;border-radius:50%;}' +
  '.gc-car-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px 6px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--cor-borda);}' +
  'html.dark, html.custom-theme .gc-car-metrics{border-color:var(--cor-borda);}' +
  '.gc-car-metric-label{font-size:9px;color:var(--cor-texto-fraco);text-transform:uppercase;letter-spacing:.04em; font-weight:700;}' +
  '.gc-car-metric-val{font-family:JetBrains Mono,monospace;font-size:11.5px;font-weight:700;color:var(--cor-texto);margin-top:1px;}' +
  'html.dark, html.custom-theme .gc-car-metric-val{color:var(--cor-texto);}' +
  '.gc-car-stage{margin-top:10px;height:5px;border-radius:6px;background:var(--cor-fundo-card-aninhado);overflow:hidden;position:relative;}' +
  '.gc-car-stage-fill{transition:width .6s var(--transicao-fluida);}' +
  '.gc-cycle-info{position:relative;}' +
  '.gc-cycle-tooltip{position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:var(--cor-texto);color:#fff;padding:6px 10px;border-radius:8px;font-size:11px;white-space:nowrap;opacity:0;pointer-events:none;transition:.15s;}' +
  '.gc-cycle-info:hover .gc-cycle-tooltip{opacity:1;}' +
  'html.dark, html.custom-theme .gc-car-stage{background:var(--cor-fundo-card-profundo);}' +
  '.gc-car-stage-fill{height:100%;border-radius:6px;background:var(--cor-primaria);}' +
  '.gc-car-stage-label{margin-top:5px;font-size:10px;font-weight:700;color:var(--cor-texto-fraco);}' +
  '.gc-car-card.gc-car-new{border-style:dashed;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:var(--cor-primaria);min-height:150px;background:color-mix(in srgb,var(--cor-primaria-suave) 22%, transparent);border-color:color-mix(in srgb,var(--cor-primaria) 24%, var(--cor-borda));border-width:1.5px;}' +
  'html.dark, html.custom-theme .gc-car-card.gc-car-new{color:var(--cor-primaria); background:color-mix(in srgb,var(--cor-primaria) 8%, transparent);}' +
  '.gc-car-card.gc-car-new i{font-size:20px;}' +
  '.gc-car-card.gc-car-new span{font-size:12px;font-weight:800;letter-spacing:-.01em;}' +
  '/* ===== Workspace — rail esmeralda ===== */' +
  '.gc-workspace{display:grid;grid-template-columns:78px 1fr;gap:0;padding:18px 24px 8px;}' +
  '.gc-rail{display:flex;flex-direction:column;gap:6px;padding-right:14px;border-right:1px solid var(--cor-borda);}' +
  'html.dark, html.custom-theme .gc-rail{border-color:var(--cor-borda);}' +
  '.gc-rail-btn{display:flex;flex-direction:column;align-items:center;gap:5px;background:transparent;border:1px solid transparent;border-radius:10px;padding:12px 6px;min-height:64px;justify-content:center;color:var(--cor-texto-fraco);transition:all var(--transicao-rapida);cursor:pointer;position:relative;}' +
  '.gc-rail-btn:hover::after{content:attr(data-tooltip);position:absolute;left:78px;top:50%;transform:translateY(-50%);background:var(--cor-texto);color:#fff;padding:6px 10px;border-radius:8px;font-size:11px;white-space:nowrap;z-index:10;pointer-events:none;opacity:1;}' +
  '.gc-rail-btn i{font-size:18px;}' +
  '.gc-rail-btn i{font-size:16px;}' +
  '.gc-rail-btn span{font-size:9.5px;font-weight:700;line-height:1.15;text-align:center;letter-spacing:-.01em;}' +
  '.gc-rail-btn:hover{background:var(--cor-fundo-card-aninhado);color:var(--cor-texto-medio);border-color:var(--cor-borda);}' +
  'html.dark, html.custom-theme .gc-rail-btn:hover{background:var(--cor-fundo-card-aninhado);color:var(--cor-texto);}' +
  '.gc-rail-btn.active{background:var(--cor-primaria);color:#fff;box-shadow:0 6px 14px var(--cor-primaria-suave);border-color:var(--cor-primaria);}' +
  '.gc-content-pane{padding-left:22px;min-height:340px;}' +
  '.gc-module{display:none;}' +
  '.gc-module.active{display:block;animation:gcFadeUp .32s var(--transicao-fluida) both;}' +
  '@keyframes gcFadeUp{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:translateY(0);}}' +
  '/* ===== Form Fields — esmeralda ===== */' +
  '.gc-field-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px 16px;}' +
  '.gc-field{display:flex;flex-direction:column;gap:6px;}' +
  '.gc-field.span2{grid-column:span 2;}' +
  '.gc-field label{font-size:11px;font-weight:800;letter-spacing:.02em;text-transform:uppercase;color:var(--cor-texto-suave);display:flex;align-items:center;gap:6px;}' +
  'html.dark, html.custom-theme .gc-field label{color:var(--cor-texto-medio);}' +
  '.gc-field label i{color:var(--cor-primaria);font-size:11px;}' +
  '.gc-field input,.gc-field select,.gc-field textarea{border:1px solid var(--cor-borda);border-radius:8px;padding:10px 12px;font-size:13px;line-height:1.4;color:var(--cor-texto);background:color-mix(in srgb,var(--cor-fundo-card) 84%, #fff);transition:all .16s var(--transicao-rapida);font-family:inherit;box-shadow:inset 0 1px 2px rgba(0,0,0,.03);}' +
  'html.dark, html.custom-theme .gc-field input,html.dark, html.custom-theme .gc-field select,html.dark, html.custom-theme .gc-field textarea{background:var(--cor-fundo-card-profundo);border-color:var(--cor-borda);color:var(--cor-texto);}' +
  '.gc-field input:focus,.gc-field select:focus,.gc-field textarea:focus{outline:none;border-color:var(--cor-primaria);box-shadow:0 0 0 3px var(--cor-primaria-suave);background:var(--cor-fundo-card);}' +
  '.gc-field input::placeholder,.gc-field textarea::placeholder{color:var(--cor-texto-fraco);}' +
  '.gc-field .hint{font-size:11px;color:var(--cor-primaria);font-weight:600;margin-top:1px;}' +
  '.gc-field .hint.muted{color:var(--cor-texto-fraco);font-weight:500;}' +
  '/* ===== Badges ===== */' +
  '.gc-badge-row{display:flex;gap:8px;margin-top:2px;flex-wrap:wrap;}' +
  '.gc-badge{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;padding:5px 11px;border-radius:100px;}' +
  '.gc-badge.teal{background:var(--cor-primaria-suave);color:var(--cor-primaria);border:1px solid color-mix(in srgb,var(--cor-primaria) 14%, transparent);}' +
  'html.dark, html.custom-theme .gc-badge.teal{background:color-mix(in srgb,var(--cor-primaria) 14%, transparent);color:var(--cor-primaria);border-color:color-mix(in srgb,var(--cor-primaria) 18%, transparent);}' +
  '.gc-badge.coffee{background:var(--cor-fundo-card-aninhado);color:var(--cor-texto-medio);border:1px solid var(--cor-borda);}' +
  '.gc-badge.green{background:color-mix(in srgb,var(--cor-primaria) 8%, #f0fdf4);color:var(--cor-primaria);border:1px solid color-mix(in srgb,var(--cor-primaria) 14%, transparent);}' +
  '.gc-badge.amber{background:var(--cor-ouro-suave);color:var(--cor-ouro);border:1px solid color-mix(in srgb,var(--cor-ouro) 22%, transparent);}' +
  '.gc-badge.red{background:var(--cor-erro-suave);color:var(--cor-erro);border:1px solid color-mix(in srgb,var(--cor-erro) 18%, transparent);}' +
  '/* ===== Cycle Ring ===== */' +
  '.gc-cycle-layout{display:grid;grid-template-columns:270px 1fr;gap:28px;align-items:start;}' +
  '.gc-cycle-info h4{font-family:Sora,sans-serif;font-size:15px;margin:0 0 6px;color:var(--cor-texto);letter-spacing:-.01em;}' +
  'html.dark, html.custom-theme .gc-cycle-info h4{color:var(--cor-texto);}' +
  '.gc-cycle-info p{font-size:12.5px;color:var(--cor-texto-medio);line-height:1.5;margin:0 0 12px;}' +
  '.gc-stat-line{display:flex;align-items:center;gap:8px;margin-bottom:8px;}' +
  '.gc-stat-line .k{font-size:11.5px;color:var(--cor-texto-fraco);font-weight:700;min-width:140px;}' +
  '.gc-stat-line .v{font-family:JetBrains Mono,monospace;font-weight:700;font-size:13px;color:var(--cor-texto);}' +
  'html.dark, html.custom-theme .gc-stat-line .v{color:var(--cor-texto);}' +
  '/* ===== Callouts ===== */' +
  '.gc-callout{border-radius:10px;padding:12px 14px;font-size:12.5px;line-height:1.5;display:flex;gap:10px;margin-top:8px;}' +
  '.gc-callout i{font-size:14px;flex-shrink:0;margin-top:1px;}' +
  '.gc-callout.info{background:var(--cor-primaria-suave);color:var(--cor-primaria-forte);border:1px solid color-mix(in srgb,var(--cor-primaria) 14%, transparent);}' +
  'html.dark, html.custom-theme .gc-callout.info{background:color-mix(in srgb,var(--cor-primaria) 10%, transparent);color:var(--cor-primaria);border-color:color-mix(in srgb,var(--cor-primaria) 16%, transparent);}' +
  '.gc-callout.tip{background:color-mix(in srgb,var(--cor-ouro-suave) 55%, #fff);color:var(--cor-texto);border:1px solid color-mix(in srgb,var(--cor-ouro) 18%, transparent);}' +
  '.gc-callout.alert{background:rgba(189,63,57,0.12);color:#bd3f39;border:1px solid rgba(189,63,57,0.2);}' +
  'html.dark, html.custom-theme .gc-callout.alert{background:rgba(241,119,114,0.15);color:#f17772;border-color:rgba(241,119,114,0.3);}' +
  '/* ===== Stats Grid ===== */' +
  '.gc-stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;}' +
  '.gc-stat-card{border:1px solid var(--cor-borda);border-radius:12px;padding:14px 14px;background:linear-gradient(180deg,var(--cor-fundo-card),var(--cor-fundo-card-aninhado));box-shadow:0 1px 0 rgba(255,255,255,.6),0 4px 12px var(--cor-sombra);}' +
  'html.dark, html.custom-theme .gc-stat-card{background:linear-gradient(180deg,var(--cor-fundo-card),var(--cor-fundo-card-aninhado));border-color:var(--cor-borda);}' +
  '.gc-stat-card .lbl{font-size:10px;color:var(--cor-texto-fraco);font-weight:700;letter-spacing:.04em;text-transform:uppercase;display:flex;align-items:center;gap:6px;margin-bottom:6px;}' +
  '.gc-stat-card .lbl i{color:var(--cor-primaria);}' +
  '.gc-stat-card .num{font-family:JetBrains Mono,monospace;font-weight:800;font-size:18px;color:var(--cor-texto);letter-spacing:-.02em;}' +
  'html.dark, html.custom-theme .gc-stat-card .num{color:var(--cor-texto);}' +
  '.gc-stat-card .num span{font-size:11px;color:var(--cor-texto-fraco);font-weight:600;margin-left:3px;}' +
  '.gc-stat-card.accent{background:linear-gradient(135deg,var(--cor-primaria),var(--cor-primaria-forte));border-color:var(--cor-primaria);box-shadow:0 8px 20px var(--cor-primaria-suave);}' +
  '.gc-stat-card.accent .lbl,.gc-stat-card.accent .num{color:#fff;}' +
  '.gc-stat-card.accent .lbl i{color:rgba(255,255,255,.85);}' +
  '.gc-stat-card.accent .num span{color:rgba(255,255,255,.7);}' +
  '/* ===== Bar Compare ===== */' +
  '.gc-bar-compare{border:1px solid var(--cor-borda);border-radius:12px;padding:16px;background:var(--cor-fundo-card);}' +
  'html.dark, html.custom-theme .gc-bar-compare{border-color:var(--cor-borda);}' +
  '.gc-bar-row{display:flex;justify-content:space-between;font-size:12px;font-weight:700;color:var(--cor-texto-medio);margin-bottom:8px;}' +
  '.gc-bar-track{height:12px;border-radius:8px;background:var(--cor-fundo-card-aninhado);overflow:hidden;display:flex;}' +
  'html.dark, html.custom-theme .gc-bar-track{background:var(--cor-fundo-card-profundo);}' +
  '.gc-bar-cost{background:var(--cor-texto-fraco);height:100%;}' +
  '.gc-bar-margin{background:var(--cor-primaria);height:100%;}' +
  '.gc-bar-foot{display:flex;gap:14px;margin-top:10px;font-size:11px;color:var(--cor-texto-medio);}' +
  '.gc-bar-foot span{display:flex;align-items:center;gap:6px;font-weight:600;}' +
  '.gc-bar-foot .sw{width:9px;height:9px;border-radius:3px;}' +
  '/* ===== Treatment List — esmeralda ===== */' +
  '.gc-treat-list{display:flex;flex-direction:column;gap:10px;}' +
  '.gc-treat-row{display:grid;grid-template-columns:130px 140px 1fr 110px 140px 32px;gap:8px;align-items:center;padding:10px;border:1px solid var(--cor-borda);border-radius:10px;background:var(--cor-fundo-card-aninhado);margin-top:8px;position:relative;}' +
  '.gc-treat-row:hover{border-color:color-mix(in srgb,var(--cor-primaria) 14%, var(--cor-borda));}' +
  '.gc-treat-row .gc-drag-handle{cursor:grab;color:var(--cor-texto-fraco);padding:4px;display:flex;align-items:center;}' +
  '.gc-treat-row .gc-drag-handle:active{cursor:grabbing;}' +
  '.gc-treat-row input,.gc-treat-row select{border:1px solid var(--cor-borda-forte);border-radius:7px;padding:8px 10px;font-size:12.5px;background:var(--cor-fundo-card);color:var(--cor-texto);font-family:inherit;transition:all .15s;}' +
  '.gc-treat-row input:focus,.gc-treat-row select:focus{outline:none;border-color:var(--cor-primaria);box-shadow:0 0 0 3px var(--cor-primaria-suave);}' +
  '.gc-treat-del{width:28px;height:28px;border-radius:7px;border:1px solid var(--cor-borda);background:var(--cor-fundo-card);color:var(--cor-texto-fraco);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.15s;font-size:12px;}' +
  '.gc-treat-del:hover{background:var(--cor-erro-suave);color:var(--cor-erro);border-color:color-mix(in srgb,var(--cor-erro) 20%, transparent);}' +
  '@media(max-width:860px){.gc-treat-row{grid-template-columns:1fr 1fr;gap:10px;}}' +
  '@media(max-width:560px){.gc-treat-row{grid-template-columns:1fr;gap:10px;padding:12px;}.gc-treat-row input,.gc-treat-row select{font-size:14px;padding:10px;}.gc-treat-del{width:32px;height:32px;}}' +
  '.gc-treat-item{display:flex;align-items:center;gap:14px;border:1px solid var(--cor-borda);border-radius:12px;padding:12px 14px;background:var(--cor-fundo-card);transition:border-color .16s;}' +
  'html.dark, html.custom-theme .gc-treat-item{border-color:var(--cor-borda);background:var(--cor-fundo-card);}' +
  '.gc-treat-item:hover{border-color:color-mix(in srgb,var(--cor-primaria) 14%, var(--cor-borda));}' +
  '.gc-treat-ico{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:15px;}' +
  '.gc-treat-ico.fert{background:var(--cor-primaria-suave);color:var(--cor-primaria);}' +
  '.gc-treat-ico.fung{background:color-mix(in srgb,var(--cor-agua) 12%, #eff6ff);color:var(--cor-agua);}' +
  '.gc-treat-ico.pest{background:var(--cor-ouro-suave);color:var(--cor-ouro);}' +
  '.gc-treat-body{flex:1;min-width:0;}' +
  '.gc-treat-title{font-size:13px;font-weight:700;color:var(--cor-texto);}' +
  'html.dark, html.custom-theme .gc-treat-title{color:var(--cor-texto);}' +
  '.gc-treat-meta{font-size:11.5px;color:var(--cor-texto-medio);margin-top:2px;}' +
  '.gc-treat-status{font-size:11px;font-weight:700;padding:5px 11px;border-radius:100px;white-space:nowrap;}' +
  '.gc-add-row{display:flex;align-items:center;gap:8px;justify-content:center;border:1.5px dashed var(--cor-borda-forte);border-radius:12px;padding:11px;color:var(--cor-primaria);font-size:12.5px;font-weight:800;letter-spacing:-.01em;transition:all .16s;background:color-mix(in srgb,var(--cor-primaria-suave) 26%, transparent);width:100%;margin-top:4px;cursor:pointer;}' +
  '.gc-add-row:hover{background:var(--cor-primaria-suave);border-color:var(--cor-primaria);color:var(--cor-primaria-forte);}' +
  '/* ===== Monitoramento ===== */' +
  '.gc-mon-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;}' +
  '.gc-mon-card{border:1px solid var(--cor-borda);border-radius:12px;padding:16px;background:var(--cor-fundo-card);box-shadow:0 1px 0 rgba(255,255,255,.6),0 4px 12px var(--cor-sombra);}' +
  'html.dark, html.custom-theme .gc-mon-card{border-color:var(--cor-borda);background:var(--cor-fundo-card);}' +
  '.gc-mon-card h5{font-family:Sora,sans-serif;font-size:12px;margin:0 0 12px;display:flex;align-items:center;gap:7px;color:var(--cor-texto);font-weight:800;letter-spacing:-.01em;}' +
  'html.dark, html.custom-theme .gc-mon-card h5{color:var(--cor-texto);}' +
  '.gc-mon-card h5 i{color:var(--cor-primaria);}' +
  '.gc-soil-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px;}' +
  '.gc-soil-item .k{font-size:10px;color:var(--cor-texto-fraco);text-transform:uppercase;letter-spacing:.04em;font-weight:700;}' +
  '.gc-soil-item .v{font-family:JetBrains Mono,monospace;font-weight:800;font-size:14px;color:var(--cor-texto);margin-top:2px;}' +
  'html.dark, html.custom-theme .gc-soil-item .v{color:var(--cor-texto);}' +
  '/* ===== Action Bar — sticky esmeralda ===== */' +
  '.gc-action-bar{position:sticky;bottom:0;z-index:5;display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:14px 24px;border-top:1px solid var(--cor-borda);background:color-mix(in srgb,var(--cor-fundo) 92%, var(--cor-fundo-card));backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}' +
  'html.dark, html.custom-theme .gc-action-bar{background:color-mix(in srgb,var(--cor-fundo-card) 96%, transparent);border-color:var(--cor-borda);}' +
  '.gc-action-bar .gc-btn{display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:10px;font-size:13px;font-weight:800;letter-spacing:-.01em;border:1px solid transparent;transition:all .16s var(--transicao-rapida);cursor:pointer;}' +
  '.gc-btn-ghost{background:var(--cor-fundo-card-aninhado);border-color:var(--cor-borda);color:var(--cor-texto);}' +
  'html.dark, html.custom-theme .gc-btn-ghost{background:var(--cor-fundo-card-aninhado);border-color:var(--cor-borda);color:var(--cor-texto);}' +
  '.gc-btn-ghost:hover{background:var(--cor-fundo-card);border-color:var(--cor-borda-forte);transform:translateY(-1px);}' +
  '.gc-btn-add{background:var(--cor-fundo-card);border-color:var(--cor-primaria);color:var(--cor-primaria);}' +
  'html.dark, html.custom-theme .gc-btn-add{background:var(--cor-fundo-card);border-color:var(--cor-primaria);color:var(--cor-primaria);}' +
  '.gc-btn-add:hover{background:var(--cor-primaria-suave);transform:translateY(-1px);}' +
  '.gc-btn-primary{background:linear-gradient(135deg,var(--cor-primaria),var(--cor-primaria-forte));color:#fff;box-shadow:0 6px 16px var(--cor-primaria-suave);border-color:var(--cor-primaria);}' +
  '.gc-btn-primary:hover{box-shadow:0 8px 20px var(--cor-primaria-suave);transform:translateY(-1px);}' +
  '/* ===== Legacy compat ===== */' +
  '.gc-editor{display:none;}' +
  '.gc-side{display:none;}' +
  '.gc-modules{display:grid;grid-template-columns:1fr 1fr;gap:16px;}' +
  '.gc-module{border:1.5px solid var(--cor-borda);border-radius:var(--gc-r-md);padding:16px;background:var(--cor-fundo-card);}' +
  'html.dark, html.custom-theme .gc-module{background:var(--cor-fundo-card);border-color:var(--cor-borda);}' +
  '.gc-module-head{display:flex;align-items:center;gap:7px;margin-bottom:12px;font-family:Sora,sans-serif;font-size:12.5px;font-weight:700;color:var(--cor-texto);}' +
  'html.dark, html.custom-theme .gc-module-head{color:var(--cor-texto);}' +
  '.gc-module-head i{color:var(--cor-primaria);}' +
  '/* ===== Responsive ===== */' +
  '@media(max-width:860px){' +
  '.gc-workspace{grid-template-columns:1fr;}' +
  '.gc-rail{flex-direction:row;border-right:none;border-bottom:1px solid var(--gc-ink-100);padding-right:0;padding-bottom:10px;overflow-x:auto;margin-bottom:16px;}' +
  'html.dark, html.custom-theme .gc-rail{border-color:var(--gc-ink-700);}' +
  '.gc-rail-btn{flex:0 0 auto;width:76px;}' +
  '.gc-content-pane{padding-left:0;}' +
  '.gc-field-grid{grid-template-columns:1fr;}' +
  '.gc-field.span2{grid-column:span 1;}' +
  '.gc-cycle-layout{grid-template-columns:1fr;justify-items:center;text-align:center;}' +
  '.gc-stat-grid{grid-template-columns:1fr 1fr;}' +
  '.gc-mon-grid{grid-template-columns:1fr;}' +
  '.gc-modules{grid-template-columns:1fr;}' +
  '}' +
  '/* ===== Scrollbar ===== */' +
  '.gc-content-pane::-webkit-scrollbar{width:5px;height:5px;}' +
  '.gc-content-pane::-webkit-scrollbar-thumb{background:var(--gc-ink-200);border-radius:10px;}' +
  'html.dark, html.custom-theme .gc-content-pane::-webkit-scrollbar-thumb{background:var(--gc-ink-600);}' +
  '/* ===== Body lock: impede scroll do fundo ===== */' +
  'body.gc-panel-open{overflow:hidden !important;height:100vh !important;}' +
  'body.gc-panel-open #content{overflow:hidden !important;}' +
  /* ===== Estágios Dinâmicos ===== */ +'.gc-phase-bar{display:flex;flex-direction:column;gap:14px;margin:12px 0;}' +
  '.gc-stage-tabs-shell{display:flex;align-items:flex-end;gap:8px;min-width:0;}' +
  '.gc-stage-tabs-track{display:flex;align-items:flex-end;gap:6px;overflow-x:auto;overflow-y:hidden;scrollbar-width:thin;padding:0 2px 0 0;flex:1;min-width:0;}' +
  '.gc-stage-tabs-track::-webkit-scrollbar{height:4px;}' +
  '.gc-stage-tabs-track::-webkit-scrollbar-thumb{background:var(--gc-ink-200);border-radius:999px;}' +
  'html.dark, html.custom-theme .gc-stage-tabs-track::-webkit-scrollbar-thumb{background:var(--gc-ink-600);}' +
  '.gc-stage-tab{display:inline-flex;align-items:center;gap:7px;padding:10px 16px 11px;border:1.5px solid var(--gc-ink-200);border-bottom:none;border-radius:12px 12px 0 0;background:linear-gradient(180deg,#f8fafc,#eef2f7);color:var(--gc-ink-700);font-size:12px;font-weight:700;white-space:nowrap;cursor:pointer;position:relative;transition:all var(--transicao-rapida) ease;box-shadow:inset 0 -1px 0 rgba(148,163,184,.18);}' +
  'html.dark, html.custom-theme .gc-stage-tab{border-color:var(--gc-ink-600);background:linear-gradient(180deg,var(--gc-ink-700),var(--gc-ink-800));color:var(--gc-ink-200);}' +
  '.gc-stage-tab.active{background:#fff;color:var(--gc-ink-900);border-color:var(--gc-teal-400);box-shadow:0 -2px 10px rgba(13,148,136,.08);z-index:2;}' +
  'html.dark, html.custom-theme .gc-stage-tab.active{background:var(--gc-ink-800);color:#fff;border-color:var(--gc-teal-400);box-shadow:0 -2px 10px rgba(45,212,191,.12);}' +
  '.gc-stage-tab.active::after{content:"";position:absolute;left:12px;right:12px;bottom:-1px;height:2px;background:var(--gc-teal-500);border-radius:999px;}' +
  '.gc-stage-tab-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}' +
  '.gc-stage-tab-name{display:inline-flex;align-items:center;gap:5px;}' +
  '.gc-stage-tab-badge{font-size:10px;font-weight:700;padding:2px 7px;border-radius:999px;background:var(--gc-ink-100);color:var(--gc-ink-500);}' +
  'html.dark, html.custom-theme .gc-stage-tab-badge{background:var(--gc-ink-600);color:var(--gc-ink-300);}' +
  '.gc-stage-tab-badge.done{background:#dcfce7;color:#15803d;}' +
  '.gc-stage-tab-add{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:0 12px;height:42px;border:1.5px dashed var(--gc-ink-300);border-bottom:none;border-radius:12px 12px 0 0;background:transparent;color:var(--gc-teal-600);font-size:12px;font-weight:700;cursor:pointer;transition:.15s;}' +
  '.gc-stage-tab-add:hover{background:var(--gc-teal-50);border-color:var(--gc-teal-400);}' +
  '.gc-stage-panel{position:relative;border:1.5px solid var(--gc-ink-200);border-radius:0 14px 14px 14px;padding:14px 14px 12px;background:#fff;overflow:hidden;}' +
  'html.dark, html.custom-theme .gc-stage-panel{border-color:var(--gc-ink-600);background:var(--gc-ink-800);}' +
  '.gc-stage-panel::before{content:"";position:absolute;left:18px;top:-12px;width:2px;height:12px;background:linear-gradient(180deg,var(--gc-teal-400),transparent);border-radius:999px;}' +
  '.gc-stage-panel-head{display:flex;align-items:center;gap:10px;margin-bottom:8px;}' +
  '.gc-stage-panel-title{font-size:13px;font-weight:800;color:var(--gc-ink-900);display:flex;align-items:center;gap:8px;flex:1;}' +
  'html.dark, html.custom-theme .gc-stage-panel-title{color:#fff;}' +
  '.gc-stage-panel-hint{font-size:10px;font-weight:700;color:var(--gc-ink-400);text-transform:uppercase;letter-spacing:.6px;}' +
  '.gc-stage-add-inline-wrap{margin-top:8px;}' +
  '.gc-phase-actions{display:flex;gap:4px;margin-left:4px;}' +
  '.gc-phase-actions button{width:24px;height:24px;border:none;border-radius:6px;background:transparent;color:var(--gc-ink-400);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:12px;transition:.12s;}' +
  '.gc-phase-actions button:hover{background:var(--gc-ink-100);color:var(--gc-ink-700);}' +
  '.gc-phase-actions button.danger:hover{background:#fef2f2;color:var(--gc-red);}' +
  '.gc-sub-item{display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:8px;margin-bottom:4px;transition:.12s;}' +
  '.gc-sub-item:hover{background:var(--gc-ink-50);}' +
  'html.dark, html.custom-theme .gc-sub-item:hover{background:var(--gc-ink-700);}' +
  '.gc-sub-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}' +
  '.gc-sub-name{font-size:12px;font-weight:600;color:var(--gc-ink-700);flex:1;}' +
  'html.dark, html.custom-theme .gc-sub-name{color:var(--gc-ink-200);}' +
  '.gc-sub-actions{display:flex;gap:3px;}' +
  '.gc-sub-actions button{width:22px;height:22px;border:none;border-radius:5px;background:transparent;color:var(--gc-ink-400);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:11px;transition:.12s;}' +
  '.gc-sub-actions button:hover{background:var(--gc-ink-100);color:var(--gc-ink-700);}' +
  '.gc-sub-actions button.danger:hover{background:#fef2f2;color:var(--gc-red);}' +
  '.gc-task-list{margin-top:4px;padding-left:0;}' +
  '.gc-task-item{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:6px;font-size:12px;color:var(--gc-ink-600);transition:.12s;}' +
  '.gc-task-item:hover{background:var(--gc-ink-50);}' +
  'html.dark, html.custom-theme .gc-task-item:hover{background:var(--gc-ink-700);}' +
  '.gc-task-check{width:18px;height:18px;border-radius:5px;border:2px solid var(--gc-ink-300);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.15s;flex-shrink:0;background:#fff;}' +
  'html.dark, html.custom-theme .gc-task-check{background:var(--gc-ink-800);border-color:var(--gc-ink-500);}' +
  '.gc-task-check.checked{background:var(--gc-teal-600);border-color:var(--gc-teal-600);color:#fff;}' +
  '.gc-task-check i{font-size:10px;opacity:0;transition:.15s;}' +
  '.gc-task-check.checked i{opacity:1;}' +
  '.gc-task-desc{flex:1;}' +
  '.gc-task-desc.done{text-decoration:line-through;color:var(--gc-ink-400);}' +
  '.gc-task-attr{font-size:10px;color:var(--gc-ink-400);font-weight:500;background:var(--gc-ink-100);padding:2px 7px;border-radius:100px;white-space:nowrap;}' +
  'html.dark, html.custom-theme .gc-task-attr{background:var(--gc-ink-700);color:var(--gc-ink-400);}' +
  '.gc-task-add-btn{display:flex;align-items:center;gap:5px;padding:4px 10px;border:1px dashed var(--gc-ink-200);border-radius:6px;font-size:11px;font-weight:600;color:var(--gc-teal-600);background:transparent;cursor:pointer;transition:.12s;margin-top:4px;margin-left:0;}' +
  '.gc-task-add-btn:hover{background:var(--gc-teal-50);border-color:var(--gc-teal-400);}' +
  '.gc-task-inline{display:none;margin-top:6px;margin-left:0;padding:10px 12px;border:1.5px solid var(--gc-teal-400);border-radius:var(--gc-r-sm);background:var(--gc-teal-50);}' +
  'html.dark, html.custom-theme .gc-task-inline{background:rgba(13,148,136,.08);border-color:rgba(13,148,136,.3);}' +
  '.gc-task-inline.open{display:block;animation:gcFadeUp .2s ease both;}' +
  '.gc-task-inline textarea{width:100%;border:1.5px solid var(--gc-ink-200);border-radius:8px;padding:8px 10px;font-size:12px;resize:none;font-family:inherit;background:#fff;color:var(--gc-ink-900);}' +
  'html.dark, html.custom-theme .gc-task-inline textarea{background:var(--gc-ink-800);border-color:var(--gc-ink-600);color:var(--gc-ink-100);}' +
  '.gc-task-inline textarea:focus{outline:none;border-color:var(--gc-teal-500);box-shadow:var(--gc-ring);}' +
  '.gc-task-inline-attrs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:6px;}' +
  '.gc-task-inline-attrs select,.gc-task-inline-attrs input{border:1.5px solid var(--gc-ink-200);border-radius:6px;padding:5px 8px;font-size:11px;background:#fff;color:var(--gc-ink-900);font-family:inherit;}' +
  'html.dark, html.custom-theme .gc-task-inline-attrs select,html.dark, html.custom-theme .gc-task-inline-attrs input{background:var(--gc-ink-800);border-color:var(--gc-ink-600);color:var(--gc-ink-100);}' +
  '.gc-task-inline-btns{display:flex;gap:6px;margin-top:8px;justify-content:flex-end;}' +
  '.gc-task-inline-btns button{padding:5px 12px;border-radius:7px;font-size:11px;font-weight:700;border:1.5px solid transparent;cursor:pointer;transition:.12s;}' +
  '.gc-ti-cancel{background:#fff;border-color:var(--gc-ink-200);color:var(--gc-ink-600);}' +
  'html.dark, html.custom-theme .gc-ti-cancel{background:var(--gc-ink-700);border-color:var(--gc-ink-600);color:var(--gc-ink-300);}' +
  '.gc-ti-save{background:var(--gc-teal-600);color:#fff;border-color:var(--gc-teal-600);}' +
  '.gc-ti-save:hover{background:var(--gc-teal-700);}' +
  /* ===== Drag & Drop ===== */ +'.gc-drag-handle{opacity:0;cursor:grab;color:var(--gc-ink-400);font-size:13px;padding:2px;transition:opacity .15s;flex-shrink:0;touch-action:none;}' +
  '.gc-stage-tab:hover .gc-drag-handle,.gc-task-item:hover .gc-drag-handle{opacity:1;}' +
  '.gc-drag-handle:active{cursor:grabbing;}' +
  '.gc-stage-tab[data-draggable="true"],.gc-task-item[data-draggable="true"]{cursor:grab;}' +
  '.gc-dragging{opacity:.35 !important;border-style:dashed !important;}' +
  '.gc-drop-above{box-shadow:inset 0 3px 0 var(--gc-teal-500) !important;}' +
  '.gc-drop-below{box-shadow:inset 0 -3px 0 var(--gc-teal-500) !important;}' +
  '.gc-drop-before{box-shadow:inset 3px 0 0 var(--gc-teal-500) !important;}' +
  '.gc-drop-after{box-shadow:inset -3px 0 0 var(--gc-teal-500) !important;}' +
  'body.gc-grabbing,body.gc-grabbing *{cursor:grabbing !important;user-select:none !important;}' +
  /* ===== Form inline de Estágio ===== */ +'.gc-stage-inline{display:none;margin-top:6px;padding:12px 14px;border:1.5px solid var(--gc-teal-400);border-radius:var(--gc-r-sm);background:var(--gc-teal-50);}' +
  'html.dark, html.custom-theme .gc-stage-inline{background:rgba(13,148,136,.08);border-color:rgba(13,148,136,.3);}' +
  '.gc-stage-inline.open{display:block;animation:gcFadeUp .2s ease both;}' +
  '.gc-stage-inline input[type="text"]{width:100%;border:1.5px solid var(--gc-ink-200);border-radius:8px;padding:8px 10px;font-size:12.5px;font-family:inherit;background:#fff;color:var(--gc-ink-900);}' +
  'html.dark, html.custom-theme .gc-stage-inline input[type="text"]{background:var(--gc-ink-800);border-color:var(--gc-ink-600);color:var(--gc-ink-100);}' +
  '.gc-stage-inline input[type="text"]:focus{outline:none;border-color:var(--gc-teal-500);box-shadow:var(--gc-ring);}' +
  '.gc-stage-inline .gc-color-row{margin-top:10px;}' +
  '.gc-color-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px;}' +
  '.gc-color-opt{width:24px;height:24px;border-radius:50%;cursor:pointer;border:2.5px solid transparent;transition:.15s;}' +
  '.gc-color-opt:hover{transform:scale(1.15);}' +
  '.gc-color-opt.active{border-color:var(--gc-ink-900);box-shadow:0 0 0 2px #fff,0 0 0 4px var(--gc-teal-400);}' +
  'html.dark, html.custom-theme .gc-color-opt.active{border-color:#fff;box-shadow:0 0 0 2px var(--gc-ink-800),0 0 0 4px var(--gc-teal-400);}' +
  '.gc-stage-inline-btns{display:flex;gap:6px;margin-top:10px;justify-content:flex-end;}' +
  '.gc-stage-inline-btns button{padding:5px 12px;border-radius:7px;font-size:11px;font-weight:700;border:1.5px solid transparent;cursor:pointer;transition:.12s;}' +
  '.gc-si-cancel{background:#fff;border-color:var(--gc-ink-200);color:var(--gc-ink-600);}' +
  'html.dark, html.custom-theme .gc-si-cancel{background:var(--gc-ink-700);border-color:var(--gc-ink-600);color:var(--gc-ink-300);}' +
  '.gc-si-save{background:var(--gc-teal-600);color:#fff;border-color:var(--gc-teal-600);}' +
  '.gc-si-save:hover{background:var(--gc-teal-700);}';

var HERO_ICONS = {
  vegetal: 'bi-tree',
  animal: 'bi-bug',
  aquatica: 'bi-water',
  extrativismo: 'bi-basket2',
};

var GUIDE_DEFAULTS = {
  'Boi Gordo': { species: 'bovino', category: 'engorda', feeding: 'pastagem' },
  'Vaca Gorda': { species: 'bovino', category: 'engorda', feeding: 'pastagem' },
  Bezerro: { species: 'bovino', category: 'cria', feeding: 'pastagem' },
  Suíno: { species: 'suino', category: 'engorda', feeding: 'racao' },
  'Matriz Suína': { species: 'suino', category: 'reproducao', feeding: 'racao' },
  Ovino: { species: 'ovino', category: 'engorda', feeding: 'pastagem' },
  Caprino: { species: 'caprino', category: 'engorda', feeding: 'pastagem' },
  Equino: { species: 'equino', feeding: 'pastagem' },
  Búfalo: { species: 'bufalo', feeding: 'pastagem' },
  Frango: { species: 'ave', category: 'engorda', feeding: 'racao' },
  Peru: { species: 'ave', category: 'engorda', feeding: 'racao' },
  Codorna: { species: 'ave', category: 'leite', feeding: 'racao' },
  Marreco: { species: 'ave', category: 'engorda', feeding: 'racao' },
  Galinha: { species: 'ave', category: 'leite', feeding: 'racao' },
  Leite: { species: 'bovino', category: 'leite', feeding: 'pastagem' },
  'Vaca Leiteira': { species: 'bovino', category: 'leite', feeding: 'pastagem' },
  'Cabra Leiteira': { species: 'caprino', category: 'leite', feeding: 'pastagem' },
  Ovos: { species: 'ave', category: 'leite', feeding: 'racao' },
  'Peixe (Tilápia)': { species: 'tilapia' },
  'Peixe (Tambaqui)': { species: 'tambaqui' },
  'Peixe (Pacu)': { species: 'pacu' },
  'Peixe (Carpa)': { species: 'carpa' },
  'Peixe (Truta)': { species: 'truta' },
  'Peixe (Jundiá)': { species: 'jundia' },
  'Peixe (Curimatã)': { species: 'curimata' },
  'Peixe (Pirarucu)': { species: 'pirarucu' },
  Camarão: { species: 'camarao' },
};

function gcFieldDefaults(culturaNome) {
  var d = GUIDE_DEFAULTS[String(culturaNome || '').trim()] || null;
  return d ? Object.assign({}, d) : {};
}

var RAIL_DEFS = {
  vegetal: [
    { key: 'id', icon: 'bi-fingerprint', title: 'Identidade' },
    { key: 'tempo', icon: 'bi-clock-history', title: 'Ciclo & Tempo' },
    { key: 'fin', icon: 'bi-cash-stack', title: 'Financeiro' },
    { key: 'trat', icon: 'bi-eyedropper', title: 'Tratamentos' },
    { key: 'mon', icon: 'bi-cloud-sun-fill', title: 'Monitoramento' },
  ],
  animal: [
    { key: 'id', icon: 'bi-fingerprint', title: 'Identidade' },
    { key: 'manejo', icon: 'bi-clipboard2-pulse', title: 'Manejo e Reprodu\u00e7\u00e3o' },
    { key: 'sanidade', icon: 'bi-heart-pulse', title: 'Sanidade' },
    { key: 'trat', icon: 'bi-eyedropper', title: 'Tratamentos' },
    { key: 'mon', icon: 'bi-cloud-sun-fill', title: 'Monitoramento' },
  ],
  aquatica: [
    { key: 'id', icon: 'bi-fingerprint', title: 'Identidade' },
    { key: 'agua', icon: 'bi-droplet-half', title: 'Qualidade da \u00c1gua' },
    { key: 'alimentacao', icon: 'bi-basket2', title: 'Alimenta\u00e7\u00e3o' },
    { key: 'trat', icon: 'bi-eyedropper', title: 'Tratamentos' },
    { key: 'mon', icon: 'bi-cloud-sun-fill', title: 'Monitoramento' },
  ],
  extrativismo: [
    { key: 'id', icon: 'bi-fingerprint', title: 'Identidade' },
    { key: 'tempo', icon: 'bi-clock-history', title: 'M\u00e9tricas de Tempo' },
    { key: 'fin', icon: 'bi-cash-stack', title: 'Expectativa Financeira' },
    { key: 'trat', icon: 'bi-eyedropper', title: 'Tratamentos' },
    { key: 'mon', icon: 'bi-cloud-sun-fill', title: 'Monitoramento' },
  ],
};

function railDefs(groupId) {
  return RAIL_DEFS[groupId] || RAIL_DEFS.vegetal;
}

function ensureGuideStyles() {
  if (document.getElementById('gc-module-styles')) return;
  var s = document.createElement('style');
  s.id = 'gc-module-styles';
  s.textContent = GUIDE_PANEL_CSS;
  (document.head || document.documentElement).appendChild(s);
  if (!document.getElementById('gcRailFloat')) {
    var tip = document.createElement('div');
    tip.id = 'gcRailFloat';
    tip.style.display = 'none';
    document.body.appendChild(tip);
  }
  if (!document.getElementById('gcCarMenu')) {
    var menu = document.createElement('div');
    menu.id = 'gcCarMenu';
    document.body.appendChild(menu);
  }
  gcMenuOutsideClickOnce();
}

window.saveGuideSettings = function (culturaId, groupId, mode) {
  saveGuideProduction(culturaId, groupId, mode);
};

function guideLocalRecords(cid) {
  if (!window.ProductionRegistry) return [];
  return ProductionRegistry.getByCulture(cid);
}

function guideApiRecords(cid) {
  return fetch('/api/registros-producao/?cultura=' + encodeURIComponent(cid))
    .then(function (r) { return r.json(); })
    .then(function(data){
      if(Array.isArray(data)) return data;
      if(data && Array.isArray(data.results)) return data.results;
      return [];
    })
    .catch(function () { return []; });
}

function mergeGuideRecords(apiRecords, localRecords) {
  var merged = [];
  var seen = {};
  (apiRecords || []).forEach(function (r) {
    merged.push(r);
    seen[r.id] = true;
  });
  localRecords.forEach(function (r) {
    if (!r.id || !seen[r.id]) merged.push(r);
  });
  return merged;
}

function initSubTabs() {
  document.querySelectorAll('.sub-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      document.querySelectorAll('.sub-tab').forEach(function (t) {
        t.classList.remove('active');
      });
      document.querySelectorAll('.tab-content').forEach(function (t) {
        t.classList.remove('active');
      });
      this.classList.add('active');
      var el = document.getElementById('tab-' + this.dataset.tab);
      if (el) el.classList.add('active');
    });
  });
}

function getProductionFormFields(groupId, culture) {
  var types = (culture && culture.types) || {};
  var typeKeys = Object.keys(types);
  var typeOptions = typeKeys.map(function (k) {
    return { value: k, label: types[k].label || types[k] };
  });
  var getLocations = function (cid) {
    var locs = [];
    var cached = (window._guideCache && window._guideCache[cid]) || [];
    cached.forEach(function (r) {
      if (r.location && locs.indexOf(r.location) < 0) locs.push(r.location);
    });
    guideLocalRecords(cid).forEach(function (r) {
      if (r.location && locs.indexOf(r.location) < 0) locs.push(r.location);
    });
    return locs;
  };
  var form = {
    vegetal: [
      {
        key: 'name',
        label: 'Nome do Cultivo',
        type: 'text',
        placeholder: 'ex: Café Arábica Talhão Norte',
        required: true,
        colSpan: 2,
        module: 'id',
      },
      { key: 'location', label: 'Talhão / Zona', type: 'location', colSpan: 1, module: 'id' },
      {
        key: 'areaHa',
        label: '\u00c1rea do Talhão (ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'system',
        label: 'Sistema de Cultivo',
        type: 'select',
        options: [
          { value: 'convencional', label: 'Convencional' },
          { value: 'organico', label: 'Orgânico' },
          { value: 'integrado', label: 'Integrado (IFP)' },
          { value: 'agrofloresta', label: 'Agrofloresta (SAF)' },
          { value: 'permacultura', label: 'Permacultura' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'irrigation',
        label: 'Irrigação',
        type: 'select',
        options: [
          { value: 'seca', label: 'Seca (natural)' },
          { value: 'aspersao', label: 'Aspersão' },
          { value: 'gotejo', label: 'Gotejamento' },
          { value: 'pivo', label: 'Pivô Central' },
          { value: 'sulco', label: 'Sulco' },
          { value: 'microaspersao', label: 'Microaspersão' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'spacing',
        label: 'Espaçamento',
        type: 'text',
        placeholder: 'ex: 3,5 × 0,7 m',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'altitude',
        label: 'Altitude (m)',
        type: 'number',
        step: 1,
        placeholder: '950',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'soilType',
        label: 'Tipo de Solo',
        type: 'select',
        options: [
          { value: 'argiloso', label: 'Argiloso' },
          { value: 'franco', label: 'Franco' },
          { value: 'arenoso', label: 'Arenoso' },
          { value: 'franco-argiloso', label: 'Franco-Argiloso' },
          { value: 'franco-arenoso', label: 'Franco-Arenoso' },
          { value: 'lateritico', label: 'Latossolo' },
          { value: 'neossolo', label: 'Neossolo' },
          { value: 'argissolo', label: 'Argissolo' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'topografia',
        label: 'Topografia',
        type: 'select',
        options: [
          { value: 'plana', label: 'Plana' },
          { value: 'ondulada', label: 'Ondulada' },
          { value: 'montanhosa', label: 'Montanhosa' },
          { value: 'encosta', label: 'Encosta' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'processamento',
        label: 'Processamento pós-colheita',
        type: 'select',
        options: [
          { value: 'cereja', label: 'Cereja Descascado' },
          { value: 'natural', label: 'Natural (via seca)' },
          { value: 'lavado', label: 'Lavado (via úmida)' },
          { value: 'fermentacao', label: 'Fermentação controlada' },
          { value: 'outro', label: 'Outro' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'certificacoes',
        label: 'Certificações',
        type: 'text',
        placeholder: 'ex: Rainforest, UTZ, Orgânico',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Condições do terreno, histórico, observações gerais...',
        colSpan: 2,
        module: 'id',
      },
      { key: 'plantingDate', label: 'Data de Plantio', type: 'date', colSpan: 1, module: 'tempo' },
      {
        key: 'colheitaDate',
        label: 'Data de Colheita Prevista',
        type: 'date',
        colSpan: 1,
        module: 'tempo',
      },
      {
        key: 'cicloDias',
        label: 'Ciclo Estimado (dias)',
        type: 'number',
        step: 1,
        placeholder: '120',
        module: 'tempo',
      },
      { key: 'janelaInicio', label: 'Janela Início', type: 'month', colSpan: 1, module: 'tempo' },
      { key: 'janelaFim', label: 'Janela Fim', type: 'month', colSpan: 1, module: 'tempo' },
      { key: 'podaData', label: 'Última Poda', type: 'date', colSpan: 1, module: 'tempo' },
      {
        key: 'podaTipo',
        label: 'Tipo de Poda',
        type: 'select',
        options: [
          { value: 'esqueletamento', label: 'Esqueletamento' },
          { value: 'formacao', label: 'Formação' },
          { value: 'manutencao', label: 'Manutenção' },
          { value: 'colheita', label: 'Poda de colheita' },
          { value: 'renovacao', label: 'Renovação' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'tempo',
      },
      {
        key: 'mudasQty',
        label: 'Mudas / Sementes (unid)',
        type: 'number',
        step: 1,
        placeholder: '0',
        module: 'fin',
      },
      {
        key: 'custoEstimado',
        label: 'Custo Total Estimado (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'custoSemente',
        label: 'Custo Semente/Muda (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'custoMaoDeObra',
        label: 'Custo Mão-de-Obra (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'custoInsumos',
        label: 'Custo Insumos (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'produtividade',
        label: 'Produtividade (sc/ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'precoUnitario',
        label: 'Preço de Referência (R$/sc)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
    ],
    animal: [
      {
        key: 'name',
        label: 'Nome do Lote / Rebanho',
        type: 'text',
        placeholder: 'ex: Lote Nelore 2024',
        required: true,
        colSpan: 2,
        module: 'id',
      },
      {
        key: 'breed',
        label: 'Raça',
        type: 'text',
        placeholder: 'ex: Nelore, Holandesa, Cambuí',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'location',
        label: 'Piquete / Pasto / Curral',
        type: 'location',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'qty',
        label: 'Cabeças (cab)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'finalidade',
        label: 'Finalidade',
        type: 'select',
        options: [
          { value: 'corte', label: 'Corte' },
          { value: 'leite', label: 'Leite' },
          { value: 'reproducao', label: 'Reprodução' },
          { value: 'misto', label: 'Misto' },
          { value: 'competition', label: 'Competição/Feira' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'source',
        label: 'Origem',
        type: 'select',
        options: [
          { value: 'nascido', label: 'Nascido na propriedade' },
          { value: 'comprado', label: 'Comprado' },
          { value: 'arrendamento', label: 'Arrendado' },
          { value: 'troca', label: 'Troca' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Histórico, reprodução, genealogia...',
        colSpan: 2,
        module: 'id',
      },
      { key: 'date', label: 'Data de Entrada', type: 'date', colSpan: 1, module: 'manejo' },
      {
        key: 'pesoInicial',
        label: 'Peso Inicial (kg)',
        type: 'number',
        step: 0.1,
        placeholder: '0,0',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'pesoAtual',
        label: 'Peso Atual (kg)',
        type: 'number',
        step: 0.1,
        placeholder: '0,0',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'pesoMeta',
        label: 'Peso Meta abate (kg)',
        type: 'number',
        step: 0.1,
        placeholder: '0,0',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'avgAge',
        label: 'Idade Atual (meses)',
        type: 'number',
        step: 0.5,
        placeholder: '0',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'ganhoPeso',
        label: 'Ganho Peso Dia (kg/dia)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'loteCapacidade',
        label: 'Capacidade do Piquete (cab)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'areaPiquete',
        label: 'Área do Piquete (ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'lottacao',
        label: 'Lotação (cab/ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'feeding',
        label: 'Regime Alimentar',
        type: 'select',
        options: [
          { value: 'pastagem', label: 'Pastagem' },
          { value: 'confinamento', label: 'Confinamento' },
          { value: 'semiconfinamento', label: 'Semiconfinamento' },
          { value: 'silagem', label: 'Silagem' },
          { value: 'racao', label: 'Ração balanceada' },
          { value: 'salteado', label: 'Salteado (pasto + suplemento)' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'pastagemTipo',
        label: 'Tipo de Pastagem',
        type: 'select',
        options: [
          { value: 'braquaria', label: 'Braquiária' },
          { value: 'panicuma', label: 'Panicum' },
          { value: 'capim-limao', label: 'Capim-limão' },
          { value: 'alezania', label: 'Alezzandro' },
          { value: 'multiple', label: 'Mista' },
          { value: 'outro', label: 'Outro' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'reproducao',
        label: 'Reprodução',
        type: 'select',
        options: [
          { value: 'natural', label: 'Natural' },
          { value: 'inseminacao', label: 'Inseminação Artificial' },
          { value: 'transferencia', label: 'Transferência de Embrião' },
          { value: 'monta', label: 'Monta controlada' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'manejo',
      },
      {
        key: 'custoEstimado',
        label: 'Custo de Manejo (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'manejo',
      },
      {
        key: 'vacinas',
        label: 'Vacinas Aplicadas',
        type: 'text',
        placeholder: 'ex: Febre Aftosa, Brucelose, Clostridioses',
        colSpan: 2,
        module: 'sanidade',
      },
      {
        key: 'proximaDose',
        label: 'Próxima Vacina/Dose',
        type: 'date',
        colSpan: 1,
        module: 'sanidade',
      },
      { key: 'vermifugo', label: 'Último Vermífugo', type: 'date', colSpan: 1, module: 'sanidade' },
      {
        key: 'vermifugoProduto',
        label: 'Produto Vermífugo',
        type: 'text',
        placeholder: 'ex: Ivermectina, Albendazol',
        colSpan: 1,
        module: 'sanidade',
      },
      {
        key: 'ectoparasitas',
        label: 'Ectoparasitas',
        type: 'text',
        placeholder: 'ex: Carrapato, Mosca dos chifres',
        colSpan: 1,
        module: 'sanidade',
      },
      {
        key: 'exames',
        label: 'Exames / Laudos Veterinários',
        type: 'textarea',
        placeholder: 'ex: Brucelose negativa em 05/2026, tuberculose OK',
        colSpan: 2,
        module: 'sanidade',
      },
      {
        key: 'dataPesagem',
        label: 'Data da Última Pesagem',
        type: 'date',
        colSpan: 1,
        module: 'mon',
      },
      {
        key: 'conversaoAlimentar',
        label: 'Conversão Alimentar (kg ração/kg ganho)',
        type: 'number',
        step: 0.01,
        placeholder: '7,0',
        colSpan: 1,
        module: 'mon',
      },
    ],
    aquatica: [
      {
        key: 'name',
        label: 'Nome do Tanque / Viveiro',
        type: 'text',
        placeholder: 'ex: Tanque 03 - Tilápias',
        required: true,
        colSpan: 2,
        module: 'id',
      },
      {
        key: 'location',
        label: 'Tanque / Viveiro / Lago',
        type: 'location',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'qty',
        label: 'Alevinos / Peixes (unid)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'sistema',
        label: 'Sistema de Cultivo',
        type: 'select',
        options: [
          { value: 'extensivo', label: 'Extensivo' },
          { value: 'semi-intensivo', label: 'Semi-intensivo' },
          { value: 'intensivo', label: 'Intensivo' },
          { value: 'superintensivo', label: 'Superintensivo (Biofloc)' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'areaTanque',
        label: 'Área do Tanque (m²)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'profundidade',
        label: 'Profundidade Média (m)',
        type: 'number',
        step: 0.1,
        placeholder: '1,5',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'volume',
        label: 'Volume da Água (m³)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'tipoFisico',
        label: 'Tipo Físico',
        type: 'select',
        options: [
          { value: 'barro', label: 'Tanque de Barro' },
          { value: 'concreto', label: 'Tanque de Concreto' },
          { value: 'geotextil', label: 'Tanque Geotêxtil' },
          { value: 'lona', label: 'Tanque de Lona' },
          { value: 'natural', label: 'Lago Natural' },
          { value: 'raceway', label: 'Raceway' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'maternidade',
        label: 'Maternidade / Viveiro',
        type: 'select',
        options: [
          { value: 'sim', label: 'Sim' },
          { value: 'nao', label: 'Não' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Infraestrutura, cercas, proteção, histórico...',
        colSpan: 2,
        module: 'id',
      },
      { key: 'date', label: 'Data de Povoamento', type: 'date', colSpan: 1, module: 'agua' },
      {
        key: 'initialBiomass',
        label: 'Biomassa Inicial (kg)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'agua',
      },
      {
        key: 'tempAgua',
        label: 'Temperatura da Água (°C)',
        type: 'number',
        step: 0.1,
        placeholder: '26,0',
        module: 'agua',
      },
      {
        key: 'ph',
        label: 'pH da Água',
        type: 'number',
        step: 0.1,
        placeholder: '7,0',
        module: 'agua',
      },
      {
        key: 'oxigenio',
        label: 'Oxigênio Dissolvido (mg/L)',
        type: 'number',
        step: 0.1,
        placeholder: '6,0',
        module: 'agua',
      },
      {
        key: 'amonia',
        label: 'Amônia NH₃ (mg/L)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'agua',
      },
      {
        key: 'nitrito',
        label: 'Nitrito NO₂ (mg/L)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'agua',
      },
      {
        key: 'turbidez',
        label: 'Turbidez (NTU)',
        type: 'number',
        step: 1,
        placeholder: '0',
        module: 'agua',
      },
      {
        key: 'alcalinidade',
        label: 'Alcalinidade (mg/L CaCO₃)',
        type: 'number',
        step: 1,
        placeholder: '0',
        module: 'agua',
      },
      {
        key: 'dureza',
        label: 'Dureza Total (mg/L)',
        type: 'number',
        step: 1,
        placeholder: '0',
        module: 'agua',
      },
      {
        key: 'dailyFeed',
        label: 'Ração Diária (kg/dia)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'alimentacao',
      },
      {
        key: 'feedType',
        label: 'Tipo de Ração',
        type: 'select',
        options: [
          { value: 'proteica', label: 'Proteica (35-45%)' },
          { value: 'crescimento', label: 'Crescimento (25-35%)' },
          { value: 'engorda', label: 'Engorda (20-25%)' },
          { value: 'manutencao', label: 'Manutenção (15-20%)' },
          { value: 'premio', label: 'Prêmio natural' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'alimentacao',
      },
      {
        key: 'feedFreq',
        label: 'Frequência',
        type: 'select',
        options: [
          { value: '1x', label: '1x ao dia' },
          { value: '2x', label: '2x ao dia' },
          { value: '3x', label: '3x ao dia' },
          { value: '4x', label: '4x ao dia' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'alimentacao',
      },
      {
        key: 'feedConv',
        label: 'Conversão Alimentar (CA)',
        type: 'number',
        step: 0.01,
        placeholder: '1,5',
        colSpan: 1,
        module: 'alimentacao',
      },
      {
        key: 'custoEstimado',
        label: 'Custo Ração (R$/kg)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'alimentacao',
      },
      {
        key: 'mortalidade',
        label: 'Mortalidade (%)',
        type: 'number',
        step: 0.1,
        placeholder: '0,0',
        colSpan: 1,
        module: 'mon',
      },
      {
        key: 'crescimentoDia',
        label: 'Crescimento Diário (g/dia)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'mon',
      },
      {
        key: 'biomassaAtual',
        label: 'Biomassa Atual (kg)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'mon',
      },
      {
        key: 'densidade',
        label: 'Densidade (peixes/m³)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'mon',
      },
    ],
    extrativismo: [
      {
        key: 'name',
        label: 'Produto / Extraído',
        type: 'text',
        placeholder: 'ex: Castanha-do-Pará, Açaí, Palmito',
        required: true,
        colSpan: 2,
        module: 'id',
      },
      {
        key: 'prodType',
        label: 'Tipo de Produto',
        type: 'select',
        options: [
          { value: 'madeira', label: 'Madeira' },
          { value: 'borracha', label: 'Borracha' },
          { value: 'castanha', label: 'Castanha' },
          { value: 'acai', label: 'Açaí' },
          { value: 'palmito', label: 'Palmito' },
          { value: 'oleo', label: 'Óleo essencial' },
          { value: 'cipo', label: 'Cipó' },
          { value: 'resina', label: 'Resina/Bálsamo' },
          { value: 'carvao', label: 'Carvão' },
          { value: 'fruta', label: 'Fruta nativa' },
          { value: 'ervas', label: 'Ervas/Plantas medicinais' },
          { value: 'outro', label: 'Outro' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      { key: 'location', label: 'Área de Extração', type: 'location', colSpan: 1, module: 'id' },
      {
        key: 'areaExplorada',
        label: 'Área Explorada (ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'areaTotal',
        label: 'Área Total Concessão (ha)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'metodo',
        label: 'Método de Extração',
        type: 'select',
        options: [
          { value: 'manual', label: 'Manual' },
          { value: 'mecanizado', label: 'Mecanizado' },
          { value: 'semi-mecanizado', label: 'Semi-mecanizado' },
          { value: 'misto', label: 'Misto' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'finalidade',
        label: 'Finalidade',
        type: 'select',
        options: [
          { value: 'comercial', label: 'Comercial' },
          { value: 'subsistencia', label: 'Subsistência' },
          { value: 'artesanal', label: 'Artesanal' },
          { value: 'industrial', label: 'Industrial' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'sustentavel',
        label: 'Manejo Sustentável',
        type: 'select',
        options: [
          { value: 'sim', label: 'Sim (certificado)' },
          { value: 'parcial', label: 'Parcialmente' },
          { value: 'nao', label: 'Não' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'especiePrincipal',
        label: 'Espécie Principal',
        type: 'text',
        placeholder: 'ex: Bertholletia excelsa (Castanheira)',
        colSpan: 1,
        module: 'id',
      },
      {
        key: 'observations',
        label: 'Observações',
        type: 'textarea',
        placeholder: 'Condições da área, espécies associadas, acesso...',
        colSpan: 2,
        module: 'id',
      },
      { key: 'date', label: 'Data da Extração', type: 'date', colSpan: 1, module: 'tempo' },
      { key: 'safraInicio', label: 'Início da Safra', type: 'date', colSpan: 1, module: 'tempo' },
      { key: 'safraFim', label: 'Fim da Safra', type: 'date', colSpan: 1, module: 'tempo' },
      {
        key: 'cicloExtracao',
        label: 'Ciclo de Recorrência',
        type: 'select',
        options: [
          { value: 'anual', label: 'Anual' },
          { value: 'semestral', label: 'Semestral' },
          { value: 'bienal', label: 'Bienal' },
          { value: 'pluriual', label: 'Plurianual' },
          { value: 'continuo', label: 'Contínuo' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'tempo',
      },
      {
        key: 'turnoCorte',
        label: 'Turno de Corte (anos)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'tempo',
      },
      {
        key: 'qty',
        label: 'Volume Extraído',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'fin',
      },
      {
        key: 'unit',
        label: 'Unidade',
        type: 'select',
        options: [
          { value: 'm3', label: 'm³' },
          { value: 'kg', label: 'kg' },
          { value: 'tonelada', label: 'Tonelada' },
          { value: 'litro', label: 'Litro' },
          { value: 'unidade', label: 'Unidade' },
          { value: 'caixa', label: 'Caixa (15kg)' },
          { value: 'saca', label: 'Saca (60kg)' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'fin',
      },
      {
        key: 'precoUnitario',
        label: 'Preço Unitário (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'custoOperacional',
        label: 'Custo Operacional (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'custoTransporte',
        label: 'Custo Transporte (R$)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        module: 'fin',
      },
      {
        key: 'volumeEstimado',
        label: 'Volume Estimado Safra (kg)',
        type: 'number',
        step: 0.01,
        placeholder: '0,00',
        colSpan: 1,
        module: 'mon',
      },
      {
        key: 'colonias',
        label: 'Nº Colônias / Indivíduos (unid)',
        type: 'number',
        step: 1,
        placeholder: '0',
        colSpan: 1,
        module: 'mon',
      },
      {
        key: 'regeneracao',
        label: 'Regeneração Natural',
        type: 'select',
        options: [
          { value: 'boa', label: 'Boa' },
          { value: 'regular', label: 'Regular' },
          { value: 'ruim', label: 'Ruim' },
          { value: 'ausente', label: 'Ausente' },
        ],
        placeholder: 'Selecione...',
        colSpan: 1,
        module: 'mon',
      },
    ],
  };
  return form[groupId] || form.vegetal;
}

function renderField(field, culturaId, prefix, savedValue) {
  prefix = prefix || 'g-';
  var id = prefix + 'prod-' + field.key + '-' + culturaId;
  var requiredAttr = field.required ? ' required' : '';
  var cls =
    'w-full text-[13px] px-3 py-2.5 rounded-[8px] border border-[var(--cor-borda)] bg-[var(--cor-fundo-card)] dark:bg-[var(--cor-fundo-card-profundo)] text-[var(--cor-texto)] dark:text-[var(--cor-texto)] placeholder:text-[var(--cor-texto-fraco)] focus:outline-none focus:border-[var(--cor-primaria)] focus:ring-2 focus:ring-[var(--cor-primaria-suave)] transition-all shadow-sm';
  var colSpan = field.colSpan > 1 ? ';grid-column:span 2' : '';
  var sv = savedValue === undefined || savedValue === null ? '' : String(savedValue);
  var esc = function (s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  };
  var html = '<div style="' + colSpan + '">';
  html +=
    '<label style="font-size:11px; color:var(--cor-texto-suave); font-weight:800; letter-spacing:.02em; text-transform:uppercase; display:block; margin-bottom:6px;" for="' +
    id +
    '">' +
    field.label +
    (field.required ? ' <span style="color:var(--cor-erro);">*</span>' : '') +
    '</label>';
  if (field.type === 'select') {
    var opts = field.options || [];
    html += '<select id="' + id + '" class="' + cls + '">';
    if (field.placeholder)
      html += '<option value="' + (sv === '' ? '' : '') + '">' + field.placeholder + '</option>';
    opts.forEach(function (o) {
      var val = String(o.value || o);
      var lbl = o.label || o;
      html +=
        '<option value="' +
        esc(val) +
        '"' +
        (sv === val ? ' selected' : '') +
        '>' +
        lbl +
        '</option>';
    });
    html += '</select>';
  } else if (field.type === 'location') {
    var existingLocations = [];
    var cached = (window._guideCache && window._guideCache[culturaId]) || [];
    cached.forEach(function (r) {
      if (r.location && existingLocations.indexOf(r.location) < 0)
        existingLocations.push(r.location);
    });
    guideLocalRecords(culturaId).forEach(function (r) {
      if (r.location && existingLocations.indexOf(r.location) < 0)
        existingLocations.push(r.location);
    });
    html +=
      '<select id="' +
      id +
      '" onchange="var n=document.getElementById(\'' +
      id +
      "-new');if(this.value==='__new__'){n.style.display='block';n.focus();}else{n.style.display='none';n.value='';}\" class=\"" +
      cls +
      '"><option value="' +
      esc(sv) +
      '">' +
      (sv ? esc(sv) : 'Selecionar...') +
      '</option>';
    existingLocations.forEach(function (l) {
      html +=
        '<option value="' +
        esc(l) +
        '"' +
        (sv === l ? ' selected' : '') +
        '>' +
        esc(l) +
        '</option>';
    });
    html += '<option value="__new__">+ Novo...</option></select>';
    html +=
      '<input id="' +
      id +
      '-new" type="text" placeholder="Novo local..." class="' +
      cls +
      '" style="margin-top:4px;display:none;">';
  } else if (field.type === 'textarea') {
    html +=
      '<textarea id="' +
      id +
      '" rows="2" placeholder="' +
      (field.placeholder || '') +
      '" class="' +
      cls +
      '" style="resize:none;"' +
      requiredAttr +
      '>' +
      esc(sv) +
      '</textarea>';
  } else if (field.type === 'date') {
    html +=
      '<input id="' +
      id +
      '" type="date" class="' +
      cls +
      '"' +
      requiredAttr +
      ' value="' +
      esc(sv) +
      '">';
  } else if (field.type === 'datalist') {
    var listId = id + '-list';
    html +=
      '<input id="' +
      id +
      '" list="' +
      listId +
      '" placeholder="' +
      (field.placeholder || '') +
      '" class="' +
      cls +
      '" autocomplete="off" value="' +
      esc(sv) +
      '">';
    html += '<datalist id="' + listId + '">';
    (field.options || []).forEach(function (o) {
      var val = o.value || o;
      var lbl = o.label || o;
      html += '<option value="' + esc(val) + '">' + (lbl === val ? '' : lbl) + '</option>';
    });
    html += '</datalist>';
  } else if (field.type === 'month') {
    html += '<select id="' + id + '" class="' + cls + '">';
    html += '<option value="">M\u00eas...</option>';
    window.GUIDE_MESES.forEach(function (m, i) {
      var val = String(i + 1);
      html +=
        '<option value="' + val + '"' + (sv === val ? ' selected' : '') + '>' + m + '</option>';
    });
    html += '</select>';
  } else if (field.prefix && (field.type === 'number' || field.type === 'text')) {
    html += '<div class="gc-affix">';
    html += '<span class="gc-affix-pre">' + field.prefix + '</span>';
    html +=
      '<input id="' +
      id +
      '" type="' +
      (field.type || 'text') +
      '" step="' +
      (field.step || 'any') +
      '" placeholder="' +
      (field.placeholder || '') +
      '" class="gc-affix-input"' +
      requiredAttr +
      ' value="' +
      esc(sv) +
      '">';
    html += '</div>';
  } else {
    html +=
      '<input id="' +
      id +
      '" type="' +
      (field.type || 'text') +
      '" step="' +
      (field.step || 'any') +
      '" placeholder="' +
      (field.placeholder || '') +
      '" class="' +
      cls +
      '"' +
      requiredAttr +
      ' value="' +
      esc(sv) +
      '">';
  }
  html += '</div>';
  return html;
}

function renderTreatmentRow(idx, culturaId, prefix) {
  prefix = prefix || 'g-';
  var aid = function (suffixName) {
    return prefix + 't-' + suffixName + '-' + idx + '-' + culturaId;
  };
  var html = '<div class="gc-treat-row" id="' + prefix + 't-row-' + idx + '-' + culturaId + '">';
  html += '<input type="date" id="' + aid('date') + '">';
  html +=
    '<select id="' +
    aid('type') +
    '"><option value="">Tipo...</option><option value="fertilizante">Fertilizante</option><option value="pesticida">Pesticida</option><option value="corretivo">Corretivo</option><option value="inoculante">Inoculante</option><option value="outro">Outro</option></select>';
  html += '<input type="text" id="' + aid('product') + '" placeholder="Produto">';
  html += '<input type="text" id="' + aid('dose') + '" placeholder="Dose">';
  html +=
    '<select id="' +
    aid('method') +
    '"><option value="">M\u00e9todo...</option><option value="pulverizacao">Pulveriza\u00e7\u00e3o</option><option value="incorporacao">Incorpora\u00e7\u00e3o</option><option value="fertirrigacao">Fertirriga\u00e7\u00e3o</option><option value="manual">Manual</option><option value="mecanizado">Mecanizado</option></select>';
  html +=
    '<button type="button" class="gc-treat-del" onclick="removeGuideTreatmentRow(' +
    idx +
    ", '" +
    culturaId +
    "', '" +
    prefix +
    '\')" title="Remover">\u2715</button>';
  html += '</div>';
  return html;
}

window.addGuideTreatmentRow = function (culturaId, prefix) {
  prefix = prefix || 'g-';
  var container = document.getElementById(prefix + 't-rows-' + culturaId);
  if (!container) return;
  var idx = container.children.length;
  container.insertAdjacentHTML('beforeend', renderTreatmentRow(idx, culturaId, prefix));
};

window.removeGuideTreatmentRow = function (idx, culturaId, prefix) {
  prefix = prefix || 'g-';
  var row = document.getElementById(prefix + 't-row-' + idx + '-' + culturaId);
  if (row) row.remove();
};

function getTreatmentRows(culturaId, prefix) {
  prefix = prefix || 'g-';
  var container = document.getElementById(prefix + 't-rows-' + culturaId);
  if (!container) return [];
  var treatments = [];
  for (var i = 0; i < container.children.length; i++) {
    var dateEl = document.getElementById(prefix + 't-date-' + i + '-' + culturaId);
    var typeEl = document.getElementById(prefix + 't-type-' + i + '-' + culturaId);
    var prodEl = document.getElementById(prefix + 't-product-' + i + '-' + culturaId);
    var doseEl = document.getElementById(prefix + 't-dose-' + i + '-' + culturaId);
    var methodEl = document.getElementById(prefix + 't-method-' + i + '-' + culturaId);
    if (dateEl && typeEl && typeEl.value) {
      treatments.push({
        date: dateEl.value,
        type: typeEl.value,
        product: prodEl ? prodEl.value.trim() : '',
        dose: doseEl ? doseEl.value.trim() : '',
        method: methodEl ? methodEl.value : '',
      });
    }
  }
  return treatments;
}

function gcFormState(culturaId) {
  if (!window._guideFormState) window._guideFormState = {};
  if (!window._guideFormState[culturaId])
    window._guideFormState[culturaId] = { fields: {}, treatments: [] };
  return window._guideFormState[culturaId];
}

function gcNum(v) {
  var n = parseFloat(String(v == null ? '' : v).replace(',', '.'));
  return isNaN(n) ? 0 : n;
}

function gcFmt(v, casas) {
  var n = gcNum(v);
  if (casas === undefined) casas = n % 1 === 0 ? 0 : 2;
  return n.toLocaleString('pt-BR', {
    minimumFractionDigits: n % 1 === 0 ? 0 : casas,
    maximumFractionDigits: casas,
  });
}

function gcEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function gcFieldKeyFromId(el, culturaId) {
  if (!el || !el.id) return null;
  var p = 'g-prod-';
  var s = '-' + culturaId;
  if (el.id.indexOf(p) !== 0) return null;
  var key = el.id.slice(p.length);
  if (key.slice(-4) === '-new') key = key.slice(0, -4);
  if (key.slice(-s.length) === s) key = key.slice(0, -s.length);
  return key;
}

function gcCaptureField(el, culturaId) {
  var key = gcFieldKeyFromId(el, culturaId);
  if (!key) return;
  var st = gcFormState(culturaId);
  var val = el.value;
  if (key === 'location' && val === '__new__') {
    var newEl = document.getElementById(el.id + '-new');
    val = newEl ? newEl.value.trim() : '';
  }
  st.fields[key] = val;
  gcUpdatePreview(culturaId);
}

function gcUpdatePreview(culturaId) {
  var st = gcFormState(culturaId);
  var hero = document.getElementById('gc-hero-name-' + culturaId);
  if (hero && st.fields.name) hero.textContent = st.fields.name;
}

/* ═══════════════════════════════════════════════════════════
   MONITORAMENTO — renderizadores por grupo (coerência de domínio)
   Vegetal   → clima no talhão + análise de solo + fitossanitário
   Animal    → clima/conforto térmico + sanidade + reprodução + piquetes
   Aquática  → temperatura/oxigênio/pH/amoníaco da água
   Extrativismo → clima + sustentação + sanidade de coleta
   ═══════════════════════════════════════════════════════════ */

function gcApiGet(url) {
  return fetch(url, { credentials: 'same-origin' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .catch(function () { return null; });
}

function gcUnwrap(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function gcMonCard(title, icon, bodyHtml, span) {
  var style = span === 2 ? ' style="grid-column:span 2;"' : '';
  return (
    '<div class="gc-mon-card"' + style + '>' +
    '<h5><i class="bi ' + icon + '"></i> ' + title + '</h5>' +
    bodyHtml +
    '</div>'
  );
}

function gcMonStat(k, v) {
  return '<div class="gc-soil-item"><div class="k">' + k + '</div><div class="v">' + v + '</div></div>';
}

/* ── VEGETAL (mantido: clima no talhão + solo + fitossanitário) ── */
function gcRenderMonVegetal(culturaId) {
  var html = '<div class="gc-mon-grid">';
  html += gcMonCard(
    'Clima no talhão',
    'bi-cloud-sun-fill',
    '<div style="display:flex;align-items:center;gap:14px;">' +
      '<div style="font-family:JetBrains Mono,monospace;font-size:30px;font-weight:700;color:#0f172a;">--°C</div>' +
      '<div style="font-size:12px;color:#475569;">Dados indisponíveis<br>' +
      '<span style="font-size:11px;color:#94a3b8;">Configure esta estação meteorológica</span></div>' +
    '</div>' +
    '<div style="margin-top:12px;font-size:11.5px;color:#475569;display:flex;align-items:center;gap:6px;">' +
    '<i class="bi bi-umbrella-fill" style="color:#3b82f6;"></i> Configure dados climáticos para previsão</div>'
  );
  html += gcMonCard(
    'Análise de solo',
    'bi-layers-fill',
    '<div class="gc-soil-grid">' +
      gcMonStat('pH', '—') + gcMonStat('Mat. Orgânica', '—') +
      gcMonStat('Fósforo (P)', '—') + gcMonStat('Potássio (K)', '—') +
    '</div>' +
    '<div class="gc-callout info" style="margin-top:10px;"><i class="bi bi-info-circle"></i> Registre análises de solo para monitoramento.</div>'
  );
  html += gcMonCard(
    'Alerta fitossanitário',
    'bi-exclamation-diamond-fill',
    '<div class="gc-callout alert"><i class="bi bi-bug-fill"></i> Nenhum alerta ativo. Configure monitoramento para receber alertas automáticos.</div>',
    2
  );
  html += gcMonCard(
    'Dica para esta fase',
    'bi-lightbulb-fill',
    '<div class="gc-callout tip"><i class="bi bi-cup-hot-fill"></i> Mantenha registros atualizados para decisões precisas na gestão da cultura.</div>',
    2
  );
  html += '</div>';
  return html;
}

/* ── ANIMAL (mata os campos de vegetal) ── */
function gcRenderMonAnimal(culturaId, culture, f) {
  var fase = (f && f.fase) || (f && f.category) || '';
  var especie = (culture && (culture.species || culture.especie)) || '';
  var html = '<div class="gc-mon-grid">';

  /* 1) Conforto térmico — clima traduzido para impacto no animal */
  html += gcMonCard(
    'Conforto térmico',
    'bi-thermometer-half',
    '<div style="display:flex;align-items:center;gap:14px;">' +
      '<div style="font-family:JetBrains Mono,monospace;font-size:30px;font-weight:700;color:#0f172a;">--°C</div>' +
      '<div style="font-size:12px;color:#475569;">Sem estação vinculada<br>' +
      '<span style="font-size:11px;color:#94a3b8;">Conforto térmico e ITH ficam indisponíveis</span></div>' +
    '</div>' +
    '<div style="margin-top:12px;font-size:11.5px;color:#475569;display:flex;align-items:center;gap:6px;">' +
    '<i class="bi bi-exclamation-triangle-fill" style="color:#f59e0b;"></i> Abaixo de 20°C ou acima de 30°C há queda de produção' +
    '</div>' +
    '<div class="gc-soil-grid" style="margin-top:10px;">' +
      gcMonStat('Umidade relativa', '—') +
      gcMonStat('ITH (índice)', '—') +
    '</div>',
    2
  );

  /* 2) Sanidade — dados reais de EventoSanitario */
  html += '<div class="gc-mon-card" data-gc-mon="sanidade"><h5><i class="bi bi-heart-pulse"></i> Sanidade do rebanho</h5>' +
    '<div style="font-size:12px;color:#64748b;">Carregando eventos…</div></div>';

  /* 3) Reprodução / mortalidade */
  html += '<div class="gc-mon-card" data-gc-mon="repro"><h5><i class="bi bi-arrow-repeat"></i> Reprodução e mortalidade</h5>' +
    '<div style="font-size:12px;color:#64748b;">Carregando…</div></div>';

  /* 4) Piquetes — lotação e descanso */
  html += '<div class="gc-mon-card" data-gc-mon="piquete"><h5><i class="bi bi-geo-alt-fill"></i> Piquetes e pastejo</h5>' +
    '<div style="font-size:12px;color:#64748b;">Carregando…</div></div>';

  /* 5) Produção do lote (leite, corte, ovos, mel) */
  html += '<div class="gc-mon-card" data-gc-mon="producao"><h5><i class="bi bi-droplet-half"></i> Produção do lote</h5>' +
    '<div style="font-size:12px;color:#64748b;">Carregando…</div></div>';

  /* 6) Nutrição — ração e consumo */
  html += gcMonCard(
    'Nutrição e ração',
    'bi-basket2-fill',
    '<div class="gc-soil-grid">' +
      gcMonStat('Ração diaria/cab', '—') +
      gcMonStat('Consumo real', '—') +
    '</div>' +
    '<div class="gc-callout info" style="margin-top:10px;"><i class="bi bi-info-circle"></i> Registre racoes e consumo no módulo Nutrição.',
    2
  );

  html += gcMonCard(
    'Indicadores deste lote',
    'bi-lightbulb-fill',
    '<div class="gc-soil-grid">' +
      gcMonStat('Fase', fase || '—') +
      gcMonStat('Espécie', especie || '—') +
      gcMonStat('Cabeças', (f && f.qty) ? gcNum(f.qty) : '—') +
      gcMonStat('Peso médio', (f && f.pesoMedio) ? gcNum(f.pesoMedio) + ' kg' : '—') +
    '</div>' +
    '<div class="gc-callout tip" style="margin-top:10px;"><i class="bi bi-cup-hot-fill"></i> Conforto térmico, sanidade e lotação são os três determinantes diretos de ganho de peso e produção leiteira.</div>',
    2
  );
  html += '</div>';

  gcLoadAnimalMon(culturaId, f);
  return html;
}

/* Busca dados reais de sanidade/reprodução/piquetes/produção */
function gcLoadAnimalMon(culturaId, f) {
  var nome = (window._guideCfg && window._guideCfg[culturaId] && window._guideCfg[culturaId].name) || '';
  var slug = String(nome).trim().toLowerCase();
  var rotulos = {
    bovino: ['BOVINO', 'Bovino'], suino: ['SUINO', 'Suíno'],
    ovino: ['OVINO', 'Ovino'], caprino: ['CAPRINO', 'Caprino'],
    equino: ['EQUINO', 'Equino'], bufalo: ['BUFALO', 'Búfalo'],
    ave: ['AVES', 'Aves']
  };
  var sp = (window._guideCfg && window._guideCfg[culturaId] && window._guideCfg[culturaId].species) || '';
  var alvo = rotulos[sp] ? rotulos[sp][0] : null;

  var setBox = function (key, inner) {
    var el = document.querySelector('.gc-mon-card[data-gc-mon="' + key + '"] .gc-mon-body, .gc-mon-card[data-gc-mon="' + key + '"]');
    if (!el) return;
    var head = el.querySelector('h5');
    var tmp = document.createElement('div');
    tmp.innerHTML = inner;
    el.innerHTML = (head ? head.outerHTML : '') + tmp.innerHTML;
  };

  /* Sanidade: próximas doses de EventoSanitario */
  gcApiGet('/api/eventos-sanitarios/').then(function (data) {
    var ev = gcUnwrap(data);
    var hoje = new Date().toISOString().slice(0, 10);
    var prox = ev.filter(function (e) { return e.proxima_dose && e.proxima_dose <= hoje; });
    var agenda = ev
      .filter(function (e) { return e.proxima_dose; })
      .sort(function (a, b) { return String(a.proxima_dose).localeCompare(String(b.proxima_dose)); })
      .slice(0, 6);
    var inner = '<div class="gc-soil-grid">' +
      gcMonStat('Eventos registrados', ev.length) +
      gcMonStat('Doses vencidas', prox.length) +
      '</div>';
    if (agenda.length) {
      inner += '<div style="margin-top:10px;font-size:11.5px;color:#475569;"><strong>Próximas doses</strong></div>' +
        '<div style="margin-top:6px;">' + agenda.map(function (e) {
          return '<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:11.5px;border-bottom:1px solid #f1f5f9;">' +
            '<span>' + (e.produto || e.tipo || '—') + '</span>' +
            '<span style="color:' + (e.proxima_dose <= hoje ? '#dc2626' : '#64748b') + ';font-weight:600;">' + gcFmtDate(e.proxima_dose) + '</span></div>';
        }).join('') + '</div>';
    } else {
      inner += '<div class="gc-callout info" style="margin-top:10px;"><i class="bi bi-info-circle"></i> Sem agenda sanitária registrada. Use o módulo Sanidade.</div>';
    }
    setBox('sanidade', inner);
  });

  /* Reprodução: indivíduos por sexo + status */
  gcApiGet('/api/animais-individuais/').then(function (data) {
    var ind = gcUnwrap(data);
    var fmeas = ind.filter(function (a) { return a.sexo === 'F'; }).length;
    var machos = ind.filter(function (a) { return a.sexo === 'M'; }).length;
    var mortos = ind.filter(function (a) { return a.status === 'morto'; }).length;
    var vendidos = ind.filter(function (a) { return a.status === 'vendido'; }).length;
    var inner = '<div class="gc-soil-grid">' +
      gcMonStat('Fêmeas', fmeas) + gcMonStat('Machos', machos) +
      gcMonStat('Mortos', mortos) + gcMonStat('Vendidos', vendidos) +
      '</div>';
    var taxa = ind.length ? ((mortos / ind.length) * 100).toFixed(1) : '0.0';
    inner += '<div class="gc-callout ' + (parseFloat(taxa) > 5 ? 'alert' : 'info') + '" style="margin-top:10px;">' +
      '<i class="bi bi-' + (parseFloat(taxa) > 5 ? 'exclamation-diamond-fill' : 'info-circle') + '"></i> ' +
      'Taxa de mortalidade: <strong>' + taxa + '%</strong> (' + mortos + ' de ' + ind.length + ')</div>';
    setBox('repro', inner);
  });

  /* Piquetes: lotação e descanso */
  gcApiGet('/api/piquetes/').then(function (data) {
    var pq = gcUnwrap(data);
    var pastejo = pq.filter(function (p) { return p.status === 'pastejo'; }).length;
    var descanso = pq.filter(function (p) { return p.status === 'descanso'; }).length;
    var areaTotal = pq.reduce(function (a, p) { return a + (parseFloat(p.area_hectare) || 0); }, 0);
    var inner = '<div class="gc-soil-grid">' +
      gcMonStat('Piquetes', pq.length) + gcMonStat('Área total', areaTotal ? areaTotal.toFixed(1) + ' ha' : '—') +
      gcMonStat('Em pastejo', pastejo) + gcMonStat('Em descanso', descanso) +
    '</div>';
    if (!pq.length) {
      inner = '<div class="gc-callout info"><i class="bi bi-info-circle"></i> Nenhum piquete cadastrado. Cadastre piquetes para calcular lotação e descanso.</div>';
    } else if (descanso === 0) {
      inner += '<div class="gc-callout alert" style="margin-top:10px;"><i class="bi bi-exclamation-diamond-fill"></i> Nenhum piquete em descanso — risco de compactação e perda de pastagem.</div>';
    }
    setBox('piquete', inner);
  });

  /* Produção: ProducaoAnimal */
  gcApiGet('/api/producao-animal/').then(function (data) {
    var pr = gcUnwrap(data);
    if (alvo) pr = pr.filter(function (p) { return p.animal_especie === alvo || !p.animal_especie; });
    var total = pr.reduce(function (a, p) { return a + (parseFloat(p.quantidade_produzida) || 0); }, 0);
    var receita = pr.reduce(function (a, p) { return a + (parseFloat(p.valor_estimado) || 0); }, 0);
    var un = (pr[0] && pr[0].unidade) || 'un';
    var inner = '<div class="gc-soil-grid">' +
      gcMonStat('Produção acumulada', total ? total.toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' ' + un : '—') +
      gcMonStat('Receita estimada', receita ? 'R$ ' + receita.toLocaleString('pt-BR', { minimumFractionDigits: 2 }) : '—') +
      gcMonStat('Registros', pr.length) +
    '</div>';
    if (!pr.length) {
      inner = '<div class="gc-callout info"><i class="bi bi-info-circle"></i> Sem produção registrada para esta espécie.</div>';
    }
    setBox('producao', inner);
  });
}

/* ── AQUÁTICA ── */
function gcRenderMonAquatica(culturaId, culture, f) {
  var html = '<div class="gc-mon-grid">';
  html += gcMonCard(
    'Qualidade da água',
    'bi-droplet-fill',
    '<div class="gc-soil-grid">' +
      gcMonStat('Temperatura', '—') + gcMonStat('pH', '—') +
      gcMonStat('Oxigênio dissolvido', '—') + gcMonStat('Amoníaco (NH₃)', '—') +
    '</div>' +
    '<div class="gc-callout info" style="margin-top:10px;"><i class="bi bi-info-circle"></i> Registre os parâmetros no módulo Qualidade da Água.</div>',
    2
  );
  html += gcMonCard(
    'Alerta deMortandade',
    'bi-exclamation-diamond-fill',
    '<div class="gc-callout alert"><i class="bi bi-water"></i> Nenhum alerta ativo. Configure monitoramento para alertas automáticos de mortandada e baixa oxigenação.</div>',
    2
  );
  html += gcMonCard(
    'Consumo de ração',
    'bi-basket2-fill',
    '<div class="gc-soil-grid">' +
      gcMonStat('Biomassa estimada', '—') + gcMonStat('Conversão alimentar', '—') +
    '</div>',
    2
  );
  html += gcMonCard(
    'Dica para esta fase',
    'bi-lightbulb-fill',
    '<div class="gc-callout tip"><i class="bi bi-cup-hot-fill"></i> Oxigênio dissolvido abaixo de 4 mg/L é o principal fator de mortalidade em viveiros.</div>',
    2
  );
  html += '</div>';
  return html;
}

/* ── EXTRATIVISMO ── */
function gcRenderMonExtrativismo(culturaId, culture, f) {
  var html = '<div class="gc-mon-grid">';
  html += gcMonCard(
    'Clima da área de coleta',
    'bi-cloud-sun-fill',
    '<div style="display:flex;align-items:center;gap:14px;">' +
      '<div style="font-family:JetBrains Mono,monospace;font-size:30px;font-weight:700;color:#0f172a;">--°C</div>' +
      '<div style="font-size:12px;color:#475569;">Sem estação vinculada</div>' +
    '</div>',
    2
  );
  html += gcMonCard(
    'Sustentação da coleta',
    'bi-tree-fill',
    '<div class="gc-soil-grid">' +
      gcMonStat('Área de manejo', '—') + gcMonStat('Produção /área', '—') +
    '</div>' +
    '<div class="gc-callout info" style="margin-top:10px;"><i class="bi bi-info-circle"></i> Registre área de manejo para calcular pressão de coleta.</div>',
    2
  );
  html += gcMonCard(
    'Sanidade de coleta',
    'bi-heart-pulse',
    '<div class="gc-callout info"><i class="bi bi-info-circle"></i> Sem registros sanitários.</div>',
    2
  );
  html += gcMonCard(
    'Dica para esta fase',
    'bi-lightbulb-fill',
    '<div class="gc-callout tip"><i class="bi bi-cup-hot-fill"></i> Respeite o período de regeneração entre coletas para preservar a fonte.</div>',
    2
  );
  html += '</div>';
  return html;
}

function gcRenderModule(culturaId, moduleKey) {
  moduleKey = moduleKey || 'id';
  if (!window._gcModule) window._gcModule = {};
  window._gcModule[culturaId] = moduleKey;
  try{ var _car = gcCarState(culturaId); _car.moduleId = moduleKey; }catch(e){}
  var groupId = (window._guideGroup && window._guideGroup[culturaId]) || 'vegetal';
  var culture = (window._guideCfg && window._guideCfg[culturaId]) || null;

  document.querySelectorAll('.gc-rail-btn[data-cultura="' + culturaId + '"]').forEach(function (b) {
    var on = b.getAttribute('data-module') === moduleKey;
    b.classList.toggle('active', on);
  });

  var contentPane = document.querySelector('#culturaDetail .gc-content-pane');
  if (!contentPane) return;

  var allFields = getProductionFormFields(groupId, culture);
  var defs = railDefs(groupId);
  var def = null;
  for (var i = 0; i < defs.length; i++) if (defs[i].key === moduleKey) def = defs[i];
  if (!def) {
    def = defs[0];
    moduleKey = def.key;
  }

  var st = gcFormState(culturaId);
  var f = st.fields || {};
  var base = (window._gcBase && window._gcBase[culturaId]) || {};
  var area = f.areaHa ? gcNum(f.areaHa) : f.qty ? gcNum(f.qty) : gcNum(base.area);
  /* Custo: estimado direto ou soma dos componentes (semente + mão-de-obra + insumos) */
  var custoComp =
    gcNum(f.custoSemente) + gcNum(f.custoMaoDeObra) + gcNum(f.custoInsumos);
  var custo = f.custoEstimado ? gcNum(f.custoEstimado) : custoComp;
  var custoOrigem = f.custoEstimado ? 'estimado' : custoComp ? 'componentes' : '';
  var prod = f.produtividade ? gcNum(f.produtividade) : 0;
  /* FIX: receita = produção total × preço (mudasQty é quantidade, nunca R$) */
  var preco = f.precoUnitario ? gcNum(f.precoUnitario) : 0;
  var custoHa = area ? custo / area : 0;
  var prodTotal = prod && area ? prod * area : 0;
  var receita = prodTotal && preco ? prodTotal * preco : gcNum(base.rec);
  var margem = receita ? receita - custo : 0;
  var margemPct = receita ? (margem / receita) * 100 : 0;
  var custoSc = prodTotal ? custo / prodTotal : 0;
  /* Break-even: sc/ha necessários para empatar (custoHa / preço) */
  var breakEven = preco ? custoHa / preco : 0;
  var recLiqHa = area ? margem / area : 0;

  var html = '<div class="gc-module active">';
  html +=
    '<div class="gc-module-head"><i class="bi ' +
    def.icon +
    '"></i> <span>' +
    def.title +
    '</span></div>';

  // ===== IDENTIDADE =====
  if (moduleKey === 'id') {
    var idFields = allFields.filter(function (fl) {
      return (fl.module || 'id') === 'id';
    });
    html += '<div class="gc-field-grid">';
    idFields.forEach(function (fl) {
      html += renderField(fl, culturaId, 'g-', f[fl.key]);
    });
    html += '</div>';
  }

  // ===== CICLO & TEMPO =====
  else if (moduleKey === 'tempo') {
    var plantio = f.plantingDate || '';
    var colheita = f.colheitaDate || '';
    var ciclo = f.cicloDias ? parseInt(f.cicloDias) : 0;
    var janelaInicio = f.janelaInicio || '';
    var janelaFim = f.janelaFim || '';
    var meses = [
      'Jan',
      'Fev',
      'Mar',
      'Abr',
      'Mai',
      'Jun',
      'Jul',
      'Ago',
      'Set',
      'Out',
      'Nov',
      'Dez',
    ];

    // Calcular ciclo a partir das datas se n\u00e3o informado
    if (!ciclo && plantio && colheita) {
      var dpCalc = new Date(plantio);
      var dcCalc = new Date(colheita);
      if (!isNaN(dpCalc.getTime()) && !isNaN(dcCalc.getTime())) {
        ciclo = Math.round((dcCalc - dpCalc) / (1000 * 60 * 60 * 24));
      }
    }
    // Se tem plantio mas n\u00e3o tem colheita, calcular a partir do ciclo
    if (plantio && !colheita && ciclo) {
      var dpC = new Date(plantio);
      if (!isNaN(dpC.getTime())) {
        var dcC = new Date(dpC);
        dcC.setDate(dcC.getDate() + ciclo);
        colheita = dcC.toISOString().slice(0, 10);
      }
    }
    // Se tem colheita mas n\u00e3o tem plantio, calcular a partir do ciclo
    if (colheita && !plantio && ciclo) {
      var dcP = new Date(colheita);
      if (!isNaN(dcP.getTime())) {
        var dpP = new Date(dcP);
        dpP.setDate(dpP.getDate() - ciclo);
        plantio = dpP.toISOString().slice(0, 10);
      }
    }

    var plantioFmt = plantio ? gcFmtDate(plantio) : '\u2014';
    var colheitaFmt = colheita ? gcFmtDate(colheita) : '\u2014';
    var janelaLabel =
      janelaInicio && janelaFim
        ? (meses[parseInt(janelaInicio) - 1] || '?') +
          '\u2013' +
          (meses[parseInt(janelaFim) - 1] || '?')
        : '\u2014';

    // Dias restantes e progresso
    var diasRestantes = '\u2014';
    var diasDecorridos = 0;
    var stagePct = 0;
    var hoje = new Date();
    if (plantio && ciclo) {
      var dPlantio = new Date(plantio);
      if (!isNaN(dPlantio.getTime())) {
        var dColheita = new Date(dPlantio);
        dColheita.setDate(dColheita.getDate() + ciclo);
        var diff = Math.ceil((dColheita - hoje) / (1000 * 60 * 60 * 24));
        diasRestantes = diff > 0 ? diff : 0;
        diasDecorridos = Math.max(0, ciclo - diasRestantes);
        stagePct = ciclo > 0 ? Math.min(100, Math.round((diasDecorridos / ciclo) * 100)) : 0;
      }
    }

    // Idade da lavoura
    var idadeLavoura = '—';
    if (plantio) {
      var dpId = new Date(plantio);
      if (!isNaN(dpId.getTime())) {
        var diasIdade = Math.max(0, Math.round((hoje - dpId) / (1000 * 60 * 60 * 24)));
        var anos = hoje.getFullYear() - dpId.getFullYear();
        var mId = hoje.getMonth() - dpId.getMonth();
        if (mId < 0 || (mId === 0 && hoje.getDate() < dpId.getDate())) anos--;
        idadeLavoura = anos >= 2 ? '≈ ' + anos + ' anos' : diasIdade + ' dias';
      }
    }

    // Datas previstas por fase (ciclo distribuído em 6 fases)
    var faseDatas = [];
    if (plantio && ciclo) {
      var dP0 = new Date(plantio);
      if (!isNaN(dP0.getTime())) {
        for (var fi = 0; fi < 6; fi++) {
          var dIni = new Date(dP0);
          dIni.setDate(dIni.getDate() + Math.round((fi * ciclo) / 6));
          var dFim = new Date(dP0);
          dFim.setDate(dFim.getDate() + Math.round(((fi + 1) * ciclo) / 6));
          faseDatas.push({ ini: dIni, fim: dFim });
        }
      }
    }
    function gcCurta(dt) {
      return ('0' + dt.getDate()).slice(-2) + '/' + ('0' + (dt.getMonth() + 1)).slice(-2);
    }

    // Fases fenol\u00f3gicas — anel sempre usa padrão, barra dinâmica usa API
    var fasePct = ciclo ? Math.round(100 / 5) : 20;
    var faseAtual = Math.min(4, Math.floor(stagePct / fasePct));
    var fases = DEFAULT_PHASES.map(function (p) {
      return {
        id: null,
        nome: p.nome,
        cor: p.cor,
        icone: p.icone,
        tipo: p.tipo,
        concluido: false,
        sub_estagios: [],
        tarefas: [],
      };
    });

    // Tratamentos posicionados no anel
    var treats = st.treatments || [];
    var treatMarkers = [];
    if (ciclo && plantio) {
      var dBase = new Date(plantio);
      treats.forEach(function (t) {
        if (!t.date) return;
        var dT = new Date(t.date);
        if (isNaN(dT.getTime())) return;
        var diasAposPlantio = (dT - dBase) / (1000 * 60 * 60 * 24);
        if (diasAposPlantio < 0 || diasAposPlantio > ciclo) return;
        var pct = diasAposPlantio / ciclo;
        var color = '#16a34a';
        if (t.type === 'pesticida' || t.type === 'inseticida') color = '#f59e0b';
        else if (t.type === 'fungicida' || t.type === 'corretivo') color = '#3b82f6';
        else if (t.type === 'fertilizante') color = '#16a34a';
        treatMarkers.push({
          pct: pct,
          color: color,
          label: t.product || t.type || 'Tratamento',
          date: t.date,
          type: t.type,
        });
      });
    }

    // ===== SVG RING =====
    html += '<div class="gc-cycle-layout">';

    var R = 95;
    var C = 2 * Math.PI * R;
    var segLen = C / 6;

    html +=
      '<svg viewBox="0 0 300 300" style="overflow:visible;width:100%;max-width:280px;justify-self:center;">';
    html += '<g transform="rotate(-90 150 150)">';

    // Fundo do anel
    html +=
      '<circle cx="150" cy="150" r="' + R + '" fill="none" stroke="#e2e8f0" stroke-width="16"/>';

    // 6 fases do ciclo
    fases.forEach(function (fase, idx) {
      var opacity = idx <= faseAtual ? 1 : 0.25;
      var sw = idx === faseAtual ? 20 : 14;
      html +=
        '<circle cx="150" cy="150" r="' +
        R +
        '" fill="none" stroke="' +
        fase.cor +
        '" stroke-width="' +
        sw +
        '" stroke-dasharray="' +
        segLen +
        ' ' +
        C +
        '" stroke-dashoffset="' +
        -idx * segLen +
        '" stroke-linecap="round" opacity="' +
        opacity +
        '"/>';
    });

    // Marcadores de tratamento no anel
    treatMarkers.forEach(function (tm) {
      var angle = tm.pct * 360 - 90;
      var rad = angle * (Math.PI / 180);
      var mx = 150 + R * Math.cos(rad);
      var my = 150 + R * Math.sin(rad);
      html +=
        '<circle cx="' +
        mx.toFixed(1) +
        '" cy="' +
        my.toFixed(1) +
        '" r="5" fill="' +
        tm.color +
        '" stroke="#fff" stroke-width="2" opacity="0.9"/>';
    });

    html += '</g>';

    // Centro do anel
    html += '<circle cx="150" cy="150" r="52" fill="#fff"/>';
    html +=
      '<text x="150" y="140" text-anchor="middle" font-family="Sora,sans-serif" font-size="15" font-weight="700" fill="#0f172a">' +
      gcEsc(fases[Math.min(fases.length - 1, faseAtual)].nome) +
      '</text>';
    html +=
      '<text x="150" y="158" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="22" font-weight="700" fill="' +
      (fases[Math.min(fases.length - 1, faseAtual)].cor || '#6366f1') +
      '">' +
      stagePct +
      '%</text>';
    html +=
      '<text x="150" y="174" text-anchor="middle" font-family="Inter,sans-serif" font-size="10" font-weight="600" fill="#94a3b8">do ciclo</text>';
    var centroExtra =
      typeof diasRestantes === 'number'
        ? diasRestantes > 0
          ? 'faltam ' + diasRestantes + ' dias'
          : 'colheita'
        : '';
    if (centroExtra)
      html +=
        '<text x="150" y="188" text-anchor="middle" font-family="Inter,sans-serif" font-size="10" font-weight="700" fill="#0d9488">' +
        centroExtra +
        '</text>';
    html += '</svg>';

    // ===== INFO =====
    html += '<div class="gc-cycle-info">';
    html +=
      '<h4>Est\u00e1gio atual: ' +
      gcEsc(fases[Math.min(fases.length - 1, faseAtual)].nome) +
      '</h4>';

    // Legenda das fases (com datas previstas no tooltip)
    html += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 16px;">';
    fases.forEach(function (fase, idx) {
      var isActive = idx === faseAtual;
      var bg = isActive ? fase.cor || '#6366f1' : 'transparent';
      var tc = isActive ? '#fff' : fase.cor || '#6366f1';
      var bc = fase.cor || '#6366f1';
      var tip =
        faseDatas[idx] !== undefined
          ? 'Previsto: ' + gcCurta(faseDatas[idx].ini) + ' – ' + gcCurta(faseDatas[idx].fim)
          : fase.nome;
      html +=
        '<span title="' +
        tip +
        '" style="display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;padding:4px 10px;border-radius:100px;border:1.5px solid ' +
        bc +
        ';background:' +
        bg +
        ';color:' +
        tc +
        ';cursor:default;"><i class="bi ' +
        gcEsc(fase.icone || 'bi-circle-fill') +
        '" style="font-size:10px;"></i> ' +
        gcEsc(fase.nome) +
        '</span>';
    });
    html += '</div>';

    // Alertas temporais do ciclo
    var cicloAlertas = [];
    if (plantio && ciclo) {
      var dPl = new Date(plantio);
      if (!isNaN(dPl.getTime())) {
        var dCol = new Date(dPl);
        dCol.setDate(dCol.getDate() + ciclo);
        var diffCol = Math.ceil((dCol - hoje) / (1000 * 60 * 60 * 24));
        var diffPlan = Math.ceil((dPl - hoje) / (1000 * 60 * 60 * 24));
        if (diffPlan > 0)
          cicloAlertas.push({ cls: 'info', ico: 'bi-calendar-event', txt: 'Plantio agendado em ' + diffPlan + ' dias (' + gcFmtDate(plantio) + ').' });
        else if (diffCol < 0)
          cicloAlertas.push({ cls: 'alert', ico: 'bi-exclamation-triangle', txt: 'Ciclo vencido há ' + Math.abs(diffCol) + ' dias — atualize a colheita.' });
        else if (diffCol <= 15)
          cicloAlertas.push({ cls: 'alert', ico: 'bi-alarm', txt: 'Colheita prevista em ' + diffCol + ' dias (' + gcFmtDate(colheita || '') + '). Prepare logística e mão-de-obra.' });
        if (faseDatas[faseAtual] !== undefined && diffCol >= 0 && diffPlan <= 0)
          cicloAlertas.push({ cls: 'info', ico: 'bi-flag', txt: 'Fase ' + fases[faseAtual].nome + ' prevista de ' + gcCurta(faseDatas[faseAtual].ini) + ' a ' + gcCurta(faseDatas[faseAtual].fim) + '.' });
      }
    }
    cicloAlertas.forEach(function (a) {
      html +=
        '<div class="gc-callout ' + a.cls + '" style="margin:0 0 10px;"><i class="bi ' + a.ico + '"></i> ' + a.txt + '</div>';
    });

    // Linhas de info
    html +=
      '<div class="gc-stat-line"><span class="k">Janela de colheita</span><span class="v">' +
      janelaLabel +
      '</span></div>';
    html +=
      '<div class="gc-stat-line"><span class="k">Dias restantes</span><span class="v">' +
      diasRestantes +
      (typeof diasRestantes === 'number' ? ' dias' : '') +
      '</span></div>';
    html +=
      '<div class="gc-stat-line"><span class="k">Dias decorridos</span><span class="v">' +
      diasDecorridos +
      ' dias</span></div>';
    html +=
      '<div class="gc-stat-line"><span class="k">Ciclo total</span><span class="v">' +
      (ciclo ? ciclo + ' dias' : '\u2014') +
      '</span></div>';
    html +=
      '<div class="gc-stat-line"><span class="k">Plantio</span><span class="v">' +
      plantioFmt +
      '</span></div>';
    html +=
      '<div class="gc-stat-line"><span class="k">Colheita prevista</span><span class="v">' +
      colheitaFmt +
      '</span></div>';
    html +=
      '<div class="gc-stat-line"><span class="k">Idade da lavoura</span><span class="v">' +
      idadeLavoura +
      '</span></div>';

    // Tratamentos no anel
    if (treatMarkers.length > 0) {
      html += '<div style="margin-top:14px;">';
      html +=
        '<div style="font-size:11px;font-weight:700;color:#475569;margin-bottom:8px;display:flex;align-items:center;gap:6px;"><i class="bi bi-circle-fill" style="font-size:6px;color:#16a34a;"></i> Tratamentos no ciclo</div>';
      treatMarkers.forEach(function (tm) {
        var typeLabel =
          {
            fertilizante: 'Fertilizante',
            pesticida: 'Pesticida',
            corretivo: 'Corretivo',
            inoculante: 'Inoculante',
            fungicida: 'Fungicida',
            inseticida: 'Inseticida',
            outro: 'Outro',
          }[tm.type] ||
          tm.type ||
          '';
        html +=
          '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:12px;">';
        html +=
          '<span style="width:8px;height:8px;border-radius:50%;background:' +
          tm.color +
          ';flex-shrink:0;"></span>';
        html += '<span style="font-weight:600;color:#0f172a;">' + gcEsc(tm.label) + '</span>';
        html +=
          '<span style="color:#94a3b8;font-size:11px;">\u00b7 ' + gcFmtDate(tm.date) + '</span>';
        html +=
          '<span style="margin-left:auto;font-size:10px;color:#94a3b8;background:' +
          tm.color +
          '18;padding:2px 8px;border-radius:100px;font-weight:600;">' +
          typeLabel +
          '</span>';
        html += '</div>';
      });
      html += '</div>';
    }

    html +=
      '<div class="gc-callout info" style="margin-top:14px;"><i class="bi bi-arrow-repeat"></i> As datas de plantio e colheita definem o ciclo. Tratamentos s\u00e3o posicionados proporcionalmente no tempo.</div>';
    html += '</div></div>';

    // ===== ESTÁGIOS DINÂMICOS — sempre criar =====
    html += '<div style="margin-top:20px;border-top:1px solid #e2e8f0;padding-top:16px;">';
    html +=
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">';
    html +=
      '<span style="font-family:Sora,sans-serif;font-size:13px;font-weight:700;color:#475569;display:flex;align-items:center;gap:7px;"><i class="bi bi-kanban" style="color:#0d9488;"></i> ESTÁGIOS & TAREFAS</span>';
    html += '</div>';
    html += '<div id="gc-phases-' + culturaId + '">';
    html +=
      '<div style="text-align:center;padding:20px;color:#94a3b8;font-size:12px;"><i class="bi bi-hourglass-split"></i> Carregando estágios...</div>';
    html += '</div>';
    html += '</div>';

    // Campos edit\u00e1veis de datas
    html +=
      '<div class="gc-field-grid" style="margin-top:16px;border-top:1px solid #e2e8f0;padding-top:16px;">';
    var tempoFields = allFields.filter(function (fl) {
      return (fl.module || 'id') === 'tempo';
    });
    tempoFields.forEach(function (fl) {
      html += renderField(fl, culturaId, 'g-', f[fl.key]);
    });
    html += '</div>';
  }

  // ===== FINANCEIRO =====
  else if (moduleKey === 'fin') {
    var prodTotalFmt = prodTotal ? gcFmt(prodTotal) : '—';
    var custoFmt = custo ? 'R$ ' + gcFmt(custo, 2) : 'R$ 0';
    var custoHaFmt = custoHa ? 'R$ ' + gcFmt(custoHa, 2) : 'R$ 0';
    var receitaFmt = receita ? 'R$ ' + gcFmt(receita, 2) : 'R$ 0';
    var margemFmt = margem || receita ? 'R$ ' + gcFmt(margem, 2) : 'R$ 0';
    var margemPctFmt = receita ? gcFmt(margemPct, 1) + '%' : '—';
    var custoScFmt = custoSc ? 'R$ ' + gcFmt(custoSc, 2) : '—';
    var breakEvenFmt = breakEven ? gcFmt(breakEven, 1) + ' sc/ha' : '—';
    var recLiqHaFmt = area && receita ? 'R$ ' + gcFmt(recLiqHa, 2) : '—';
    var prodHaFmt = prod ? prod + ' sc/ha' : '—';
    var barCostPct = receita > 0 ? Math.max(0, Math.min(100, Math.round((custo / receita) * 100))) : 0;
    var barMargPct = receita > 0 ? Math.max(0, 100 - barCostPct) : 0;
    var margemCls = margem >= 0 ? '' : ' style="color:#dc2626;"';

    html += '<div class="gc-stat-grid">';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-cash-coin"></i> Custo total' +
      (custoOrigem === 'componentes' ? ' <span style="font-weight:400;opacity:.65;">(Σ itens)</span>' : '') +
      '</div><div class="num">' +
      custoFmt +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-graph-up"></i> Produtividade</div><div class="num">' +
      prodHaFmt +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-boxes"></i> Produção total</div><div class="num">' +
      prodTotalFmt +
      (prodTotal ? '<span>sc</span>' : '') +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-rulers"></i> Custo/ha</div><div class="num">' +
      custoHaFmt +
      (custoHa ? '<span>/ha</span>' : '') +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-tag-fill"></i> Área</div><div class="num">' +
      (area ? gcFmt(area, 1) + '<span>ha</span>' : '—') +
      '</div></div>';
    html +=
      '<div class="gc-stat-card accent"><div class="lbl"><i class="bi bi-piggy-bank-fill"></i> Receita bruta' +
      (prodTotal && preco ? ' <span style="font-weight:400;opacity:.65;">(' + gcFmt(prodTotal) + ' sc × R$ ' + gcFmt(preco, 2) + ')</span>' : '') +
      '</div><div class="num">' +
      receitaFmt +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-percent"></i> Margem</div><div class="num"' + margemCls + '>' +
      margemFmt +
      ' <span style="font-size:11px;opacity:.7;">(' + margemPctFmt + ')</span>' +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-basket"></i> Custo/sc</div><div class="num">' +
      custoScFmt +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-flag"></i> Break-even</div><div class="num">' +
      breakEvenFmt +
      '</div></div>';
    html +=
      '<div class="gc-stat-card"><div class="lbl"><i class="bi bi-wallet2"></i> Líquido/ha</div><div class="num">' +
      recLiqHaFmt +
      '</div></div>';
    html += '</div>';
    html += '<div class="gc-bar-compare">';
    html +=
      '<div class="gc-bar-row"><span>Custo \u00d7 Margem estimada</span><span>' +
      receitaFmt +
      '</span></div>';
    html +=
      '<div class="gc-bar-track"><div class="gc-bar-cost" style="width:' +
      barCostPct +
      '%"></div><div class="gc-bar-margin" style="width:' +
      barMargPct +
      '%"></div></div>';
    html +=
      '<div class="gc-bar-foot"><span><span class="sw" style="background:#8b5a2b"></span> Custo: ' +
      custoFmt +
      '</span><span><span class="sw" style="background:#14b8a6"></span> Margem: ' +
      margemFmt +
      '</span></div>';
    html += '</div>';
    html +=
      '<div class="gc-callout info" style="margin-top:14px;"><i class="bi bi-info-circle-fill"></i> Receita = produ\u00e7\u00e3o total \u00d7 pre\u00e7o/sc. Sem custo total, soma semente + m\u00e3o-de-obra + insumos. Break-even = sc/ha para empatar.</div>';
    var finFields = allFields.filter(function (fl) {
      return (fl.module || 'id') === 'fin';
    });
    html += '<div class="gc-field-grid" style="margin-top:16px;">';
    finFields.forEach(function (fl) {
      html += renderField(fl, culturaId, 'g-', f[fl.key]);
    });
    html += '</div>';
  }

  // ===== TRATAMENTOS =====
  else if (moduleKey === 'trat') {
    var treats = st.treatments || [];
    if (treats.length > 0) {
      html += '<div class="gc-treat-list">';
      treats.forEach(function (t) {
        var icoClass = 'fert';
        var icoIcon = 'bi-flower2';
        if (t.type === 'pesticida' || t.type === 'inseticida') {
          icoClass = 'pest';
          icoIcon = 'bi-bug-fill';
        } else if (t.type === 'fungicida' || t.type === 'corretivo') {
          icoClass = 'fung';
          icoIcon = 'bi-shield-fill-check';
        }
        var typeLabel =
          {
            fertilizante: 'Fertilizante',
            pesticida: 'Pesticida',
            corretivo: 'Corretivo',
            inoculante: 'Inoculante',
            fungicida: 'Fungicida',
            inseticida: 'Inseticida',
            outro: 'Outro',
          }[t.type] ||
          t.type ||
          'Insumo';
        var statusLabel = 'Pendente';
        var statusColor = '#fffbeb';
        var statusText = '#b45309';
        if (t.date) {
          statusLabel = 'Aplicado';
          statusColor = '#f0fdf4';
          statusText = '#15803d';
        }
        var meta = [];
        if (t.date) meta.push('Aplicado em ' + gcFmtDate(t.date));
        if (t.dose) meta.push(t.dose);
        if (t.product) meta.push(t.product);
        html += '<div class="gc-treat-item">';
        html +=
          '<div class="gc-treat-ico ' + icoClass + '"><i class="bi ' + icoIcon + '"></i></div>';
        html += '<div class="gc-treat-body">';
        html += '<div class="gc-treat-title">' + gcEsc(t.product || typeLabel) + '</div>';
        html +=
          '<div class="gc-treat-meta">' + gcEsc(meta.join(' \u00b7 ') || 'Sem detalhes') + '</div>';
        html += '</div>';
        html +=
          '<span class="gc-treat-status" style="background:' +
          statusColor +
          ';color:' +
          statusText +
          ';">' +
          statusLabel +
          '</span>';
        html += '</div>';
      });
      html += '</div>';
    } else {
      html +=
        '<div class="gc-callout info" style="margin-bottom:14px;"><i class="bi bi-info-circle"></i> Nenhum tratamento registrado para este cultivo.</div>';
    }
    html +=
      '<button class="gc-add-row" type="button" onclick="addGuideTreatmentRow(' +
      culturaId +
      ', \'g-\')"><i class="bi bi-plus-circle"></i> Adicionar tratamento ou insumo</button>';
    html += '<div id="g-t-rows-' + culturaId + '" style="margin-top:10px;"></div>';
  }

  // ===== MONITORAMENTO (dispatcher por grupo) =====
  else if (moduleKey === 'mon') {
    if (groupId === 'animal') html += gcRenderMonAnimal(culturaId, culture, f);
    else if (groupId === 'aquatica') html += gcRenderMonAquatica(culturaId, culture, f);
    else if (groupId === 'extrativismo') html += gcRenderMonExtrativismo(culturaId, culture, f);
    else html += gcRenderMonVegetal(culturaId);
  }

  // ===== M\u00f3dulo gen\u00e9rico (fallback) =====
  else {
    var modFields = allFields.filter(function (fl) {
      return (fl.module || 'id') === moduleKey;
    });
    if (modFields.length > 0) {
      html += '<div class="gc-field-grid">';
      modFields.forEach(function (fl) {
        html += renderField(fl, culturaId, 'g-', f[fl.key]);
      });
      html += '</div>';
    } else {
      html +=
        '<div class="gc-callout info"><i class="bi bi-info-circle"></i> Nenhum campo configurado para este m\u00f3dulo.</div>';
    }
  }

  html += '</div>';
  contentPane.innerHTML = html;

  contentPane.querySelectorAll('input,select,textarea').forEach(function (el) {
    el.addEventListener('input', function () {
      gcCaptureField(el, culturaId);
    });
    el.addEventListener('change', function () {
      gcCaptureField(el, culturaId);
    });
  });

  // Carregar e renderizar estágios dinâmicos — SEMPRE para módulo tempo
  if (moduleKey === 'tempo') {
    // Resolver registroId de forma robusta
    var registroId2 = null;
    var car3 = gcCarState(culturaId);
    if (car3 && car3.viewRecId) registroId2 = car3.viewRecId;
    else if (car3 && car3.editingRecId) registroId2 = car3.editingRecId;
    if (!registroId2) {
      var apiRecs2 = (window._guideCache && window._guideCache[culturaId]) || [];
      if (apiRecs2.length > 0) registroId2 = apiRecs2[0].id;
    }
    // Se não tem registro, usar culturaId como fallback para permettir criar estágios
    var regKey = registroId2 || 'temp-' + culturaId;
    gcLoadStages(regKey).then(function (ests) {
      window._gcStageState[regKey] = ests;
      gcRefreshPhases(regKey, culturaId);
    });
  }
}

// ===== Carrossel de registros =====
function gcFmtDate(dt) {
  if (!dt) return '';
  var s = String(dt).trim();
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return m[3] + '/' + m[2] + '/' + m[1];
  var d = new Date(s);
  if (!isNaN(d.getTime())) return d.toLocaleDateString('pt-BR');
  return s;
}

function gcJanelaLabel(inicio, fim) {
  var mes = function (v) {
    var i = parseInt(v, 10);
    var nomes = [
      'Jan',
      'Fev',
      'Mar',
      'Abr',
      'Mai',
      'Jun',
      'Jul',
      'Ago',
      'Set',
      'Out',
      'Nov',
      'Dez',
    ];
    return i >= 1 && i <= 12 ? nomes[i - 1] : '';
  };
  var a = mes(inicio),
    b = mes(fim);
  if (!a || !b) return '';
  return a + '–' + b + (parseInt(fim, 10) < parseInt(inicio, 10) ? '*' : '');
}

function gcCarState(culturaId) {
  if (!window._gcCars) window._gcCars = {};
  if (!window._gcCars[culturaId]) {
    window._gcCars[culturaId] = {
      items: [],
      active: 0,
      prevActive: 0,
      pending: {},
      editingRecId: null,
      viewRecId: null,
      groupId: 'vegetal',
    };
  }
  return window._gcCars[culturaId];
}

function gcBadgeStatus(r, groupId) {
  var uso = false,
    insumo = false,
    alerta = false;
  if (!r) return { uso: uso, insumo: insumo, alerta: alerta };
  var plantio = r.plantingDate || r.date || (r.fields && r.fields.plantingDate) || '';
  var colheita = (r.fields && r.fields.colheitaDate) || '';
  if (groupId === 'vegetal') {
    if (plantio) {
      if (!colheita) {
        uso = true;
      } else {
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var c = new Date(String(colheita));
        if (!isNaN(c.getTime())) uso = c >= today;
        else uso = true;
      }
    }
  } else {
    uso = !!plantio;
  }
  var treats = (r.treatments || []).filter(function (t) {
    return t && t.type;
  });
  insumo = treats.some(function (t) {
    return ['fertilizante', 'pesticida', 'corretivo', 'inoculante'].indexOf(t.type) !== -1;
  });
  alerta = treats.some(function (t) {
    return !t.date || String(t.date).trim() === '';
  });
  return { uso: uso, insumo: insumo, alerta: alerta };
}

function gcBadgeColumns(r, groupId) {
  var f = (r && r.fields) || {};
  var col = function (label, val) {
    return (
      '<div class="gc-badge-cell"><div class="gc-badge-cell-label">' +
      label +
      '</div><div class="gc-badge-cell-val' +
      (val === '—' ? ' gc-badge-blank' : '') +
      '">' +
      val +
      '</div></div>'
    );
  };
  var dt = r ? r.plantingDate || r.date || '' : '';
  if (groupId === 'animal') {
    return (
      col('Cabe\u00e7as', r && r.quantity ? gcFmt(r.quantity) + ' cab' : '—') +
      col(
        'Peso M\u00e9dio',
        f.avgWeight ? gcNum(f.avgWeight).toLocaleString('pt-BR') + ' kg' : '—'
      ) +
      col('Entrada', dt ? gcFmtDate(dt) : '—')
    );
  }
  if (groupId === 'aquatica') {
    return (
      col('Peixes', r && r.quantity ? gcFmt(r.quantity) : '—') +
      col(
        'Biomassa',
        f.initialBiomass ? gcNum(f.initialBiomass).toLocaleString('pt-BR') + ' kg' : '—'
      ) +
      col(
        'Ra\u00e7\u00e3o',
        f.dailyFeed ? gcNum(f.dailyFeed).toLocaleString('pt-BR') + ' kg/dia' : '—'
      )
    );
  }
  if (groupId === 'extrativismo') {
    return (
      col('Volume', r && r.quantity ? gcFmt(r.quantity) + (r.unit ? ' ' + r.unit : '') : '—') +
      col('\u00c1rea', f.exploredArea ? gcFmt(f.exploredArea, 1) + ' ha' : '—') +
      col('Data', dt ? gcFmtDate(dt) : '—')
    );
  }
  return (
    col('\u00c1rea', f.areaHa || f.area ? gcFmt(f.areaHa || f.area, 1) + ' ha' : '—') +
    col('Plantio', dt ? gcFmtDate(dt) : '—') +
    col('Custo', f.custoEstimado ? 'R$ ' + gcFmt(f.custoEstimado, 2) : '—')
  );
}

function gcCarouselHTML(culturaId) {
  var car = gcCarState(culturaId);
  var groupId = car.groupId || window._guideGroup[culturaId] || 'vegetal';
  var h = '<div class="gc-carousel-row">';
  h += '<button type="button" class="gc-carousel-btn prev" onclick="gcCarouselScroll(\'' + culturaId + '\', -1)" aria-label="Anterior"><i class="bi bi-chevron-left"></i></button>';
  h += '<div class="gc-carousel" id="gc-car-' + culturaId + '">';
  car.items.forEach(function (it, i) {
    if (it.type === 'new') {
      h +=
        '<div class="gc-car-card gc-car-new" data-idx="' +
        i +
        '" onclick="gcCarClick(' +
        culturaId +
        ',' +
        i +
        ',event)">';
      h += '<i class="bi bi-plus-circle"></i><span>Novo Registro</span>';
      h += '</div>';
    } else {
      var r = it.rec || {};
      var st = gcBadgeStatus(r, groupId);
      var pending = car.pending[r.id] || false;
      var dots =
        '<div class="gc-car-dots">' +
        '<span class="dot" style="background:' +
        (st.uso ? '#16a34a' : '#e2e8f0') +
        '"></span>' +
        '<span class="dot" style="background:' +
        (st.insumo ? '#f59e0b' : '#e2e8f0') +
        '"></span>' +
        '<span class="dot" style="background:' +
        (st.alerta ? '#dc2626' : '#e2e8f0') +
        '"></span>' +
        '</div>';
      var isActive = i === car.active;
      h +=
        '<div class="gc-car-card' +
        (isActive ? ' active' : '') +
        '" data-idx="' +
        i +
        '" data-rec="' +
        (r.id || '') +
        '" onclick="gcCarClick(' +
        culturaId +
        ',' +
        i +
        ',event)">';
      h += '<div class="gc-car-head">';
      h +=
        '<div class="gc-car-zone"><i class="bi bi-geo-alt-fill"></i> ' +
        gcEsc(r.location || 'Sem local') +
        '</div>';
      h += dots;
      h += '</div>';
      h += '<div class="gc-car-sub">' + gcEsc(r.name || 'Sem nome') + '</div>';
      // Metrics
      var f = r.fields || {};
      h += '<div class="gc-car-metrics">';
      if (groupId === 'vegetal') {
        h +=
          '<div><div class="gc-car-metric-label">\u00c1rea</div><div class="gc-car-metric-val">' +
          (f.areaHa ? gcFmt(f.areaHa, 1) + ' ha' : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Plantio</div><div class="gc-car-metric-val">' +
          gcFmtDate(r.plantingDate || r.date) +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Custo</div><div class="gc-car-metric-val">' +
          (f.custoEstimado ? 'R$ ' + gcFmt(f.custoEstimado, 2) : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Produtividade</div><div class="gc-car-metric-val">' +
          (f.produtividade ? gcFmt(f.produtividade) + ' sc/ha' : '—') +
          '</div></div>';
      } else if (groupId === 'animal') {
        h +=
          '<div><div class="gc-car-metric-label">Cabe\u00e7as</div><div class="gc-car-metric-val">' +
          (r.quantity ? gcFmt(r.quantity) + ' cab' : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Peso M\u00e9d</div><div class="gc-car-metric-val">' +
          (f.avgWeight ? gcNum(f.avgWeight) + ' kg' : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Entrada</div><div class="gc-car-metric-val">' +
          gcFmtDate(r.date) +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Custo</div><div class="gc-car-metric-val">' +
          (f.custoEstimado ? 'R$ ' + gcFmt(f.custoEstimado, 2) : '—') +
          '</div></div>';
      } else if (groupId === 'aquatica') {
        h +=
          '<div><div class="gc-car-metric-label">Peixes</div><div class="gc-car-metric-val">' +
          (r.quantity ? gcFmt(r.quantity) : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Biomassa</div><div class="gc-car-metric-val">' +
          (f.initialBiomass ? gcFmt(f.initialBiomass) + ' kg' : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Ração</div><div class="gc-car-metric-val">' +
          (f.dailyFeed ? gcFmt(f.dailyFeed) + ' kg/dia' : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">pH</div><div class="gc-car-metric-val">' +
          (f.ph || '—') +
          '</div></div>';
      } else {
        h +=
          '<div><div class="gc-car-metric-label">Volume</div><div class="gc-car-metric-val">' +
          (r.quantity ? gcFmt(r.quantity) + (r.unit ? ' ' + r.unit : '') : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">\u00c1rea</div><div class="gc-car-metric-val">' +
          (f.exploredArea ? gcFmt(f.exploredArea, 1) + ' ha' : '—') +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">Data</div><div class="gc-car-metric-val">' +
          gcFmtDate(r.date) +
          '</div></div>';
        h +=
          '<div><div class="gc-car-metric-label">M\u00e9todo</div><div class="gc-car-metric-val">' +
          (f.method || '—') +
          '</div></div>';
      }
      h += '</div>';
      // Stage bar
      var completeness = gcRecordCompleteness(culturaId, r);
      var stageColor = completeness ? '#16a34a' : '#f59e0b';
      var stageWidth = completeness ? '100' : r.name ? '60' : '30';
      h +=
        '<div class="gc-car-stage"><div class="gc-car-stage-fill" style="width:' +
        stageWidth +
        '%;background:' +
        stageColor +
        '"></div></div>';
      h +=
        '<div class="gc-car-stage-label" style="color:' +
        stageColor +
        '">' +
        (completeness ? 'Completo' : 'Incompleto') +
        '</div>';
      h += '</div>';
    }
  });
  h += '</div>';
  h += '<button type="button" class="gc-carousel-btn next" onclick="gcCarouselScroll(\'' + culturaId + '\', 1)" aria-label="Próximo"><i class="bi bi-chevron-right"></i></button>';
  h += '</div>';
  h += '<div class="gc-carousel-slider" id="gc-slider-' + culturaId + '" onmousedown="gcSliderDown(event,\'' + culturaId + '\')"><div class="gc-carousel-thumb" id="gc-thumb-' + culturaId + '"></div></div>';
  return h;
}

function gcRecordStatus(r) {
  if (!r) return '';
  if (r.status) return r.status;
  return 'Salvo';
}

function gcRecordCompleteness(culturaId, r) {
  if (!r) return true;
  var groupId = gcCarState(culturaId).groupId || window._guideGroup[culturaId] || 'vegetal';
  var req = ['name'];
  if (groupId === 'vegetal') req = ['name', 'location', 'plantingDate', 'areaHa'];
  else if (groupId === 'animal' || groupId === 'aquatica')
    req = ['name', 'location', 'date', 'qty'];
  else if (groupId === 'extrativismo') req = ['name', 'location', 'date', 'qty'];
  var vals = {
    name: r.name,
    location: r.location,
    plantingDate: r.plantingDate || r.date,
    date: r.date || r.plantingDate,
    areaHa: r.fields && (r.fields.areaHa || r.fields.area),
    qty: r.quantity || (r.fields && r.fields.quantity) || (r.fields && r.fields.qty),
  };
  return req.every(function (k) {
    return vals[k] !== undefined && vals[k] !== null && String(vals[k]).trim() !== '';
  });
}

function gcSliderDown(e, culturaId){
  e.preventDefault();
  var slider=document.getElementById('gc-slider-'+culturaId);
  var thumb=document.getElementById('gc-thumb-'+culturaId);
  var wrap=document.getElementById('gc-car-'+culturaId);
  if(!slider||!thumb||!wrap) return;
  var rect=slider.getBoundingClientRect();
  var isTouch=e.type==='touchstart';
  var startX=isTouch?e.touches[0].clientX:e.clientX;
  var startLeft=parseFloat(thumb.style.left||'0');
  var maxThumb=rect.width - thumb.offsetWidth;
  function onMove(ev){
    var clientX=isTouch?ev.touches[0].clientX:ev.clientX;
    var dx=clientX-startX;
    var newLeft=Math.max(0, Math.min(maxThumb, startLeft+dx));
    thumb.style.left=newLeft+'px';
    var ratio=maxThumb?newLeft/maxThumb:0;
    var maxScroll=wrap.scrollWidth - wrap.clientWidth;
    wrap.scrollLeft=ratio*maxScroll;
  }
  function onUp(){
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    document.removeEventListener('touchmove', onMove);
    document.removeEventListener('touchend', onUp);
    gcCarouselUpdateButtons(culturaId);
  }
  document.addEventListener('mousemove', onMove);
  document.addEventListener('mouseup', onUp);
  document.addEventListener('touchmove', onMove, {passive:false});
  document.addEventListener('touchend', onUp);
  // click on track to jump
  if(e.target===slider){
    var clickRatio=(startX-rect.left)/rect.width;
    var maxScroll=wrap.scrollWidth - wrap.clientWidth;
    wrap.scrollTo({left: clickRatio*maxScroll, behavior:'smooth'});
    setTimeout(function(){ gcCarouselUpdateSlider(culturaId); }, 300);
  }
}
function gcCarouselUpdateSlider(culturaId){
  var wrap=document.getElementById('gc-car-'+culturaId);
  var thumb=document.getElementById('gc-thumb-'+culturaId);
  var slider=document.getElementById('gc-slider-'+culturaId);
  if(!wrap||!thumb||!slider) return;
  /* touchstart explícito não-passivo (o drag dá preventDefault; inline gerava violation) */
  if(!slider.dataset.touchBound){
    slider.dataset.touchBound='1';
    slider.addEventListener('touchstart', function(ev){ gcSliderDown(ev, culturaId); }, {passive:false});
  }
  var maxScroll=wrap.scrollWidth - wrap.clientWidth;
  var ratio=maxScroll?wrap.scrollLeft/maxScroll:0;
  var sliderW=slider.clientWidth;
  var thumbW=Math.max(40, sliderW * (wrap.clientWidth / wrap.scrollWidth));
  thumb.style.width=thumbW+'px';
  var maxThumb=sliderW - thumbW;
  thumb.style.left=(ratio*maxThumb)+'px';
}
function gcCarouselScroll(culturaId, dir){
  var wrap = document.getElementById('gc-car-' + culturaId);
  if(!wrap) return;
  var cardWidth = 208; // 196 + 12 gap
  var visible = 3;
  var scrollAmount = cardWidth * visible * dir;
  // Use scrollBy for smooth
  wrap.scrollBy({left: scrollAmount, behavior: 'smooth'});
  // Update button states after scroll
  setTimeout(function(){ gcCarouselUpdateButtons(culturaId); }, 300);
}
function gcCarouselUpdateButtons(culturaId){
  var wrap = document.getElementById('gc-car-' + culturaId);
  if(!wrap) return;
  var prev = wrap.parentElement.querySelector('.gc-carousel-btn.prev');
  var next = wrap.parentElement.querySelector('.gc-carousel-btn.next');
  if(!prev || !next) return;
  var maxScroll = wrap.scrollWidth - wrap.clientWidth;
  prev.disabled = wrap.scrollLeft <= 5;
  next.disabled = wrap.scrollLeft >= maxScroll - 5;
}
function gcCarLayout(culturaId) {
  var wrap = document.getElementById('gc-car-' + culturaId);
  if (!wrap) return;
  var car = gcCarState(culturaId);
  var items = wrap.querySelectorAll('.gc-car-card');
  items.forEach(function (el) {
    var i = parseInt(el.getAttribute('data-idx'));
    var isActive = i === car.active;
    el.classList.toggle('active', isActive);
  });
  // Scroll active card into view centered (3 cards visible)
  var activeCard = wrap.querySelector('.gc-car-card.active');
  if (activeCard) {
    activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    setTimeout(function(){ gcCarouselUpdateButtons(culturaId); }, 350);
  } else {
    gcCarouselUpdateButtons(culturaId);
  }
  // init slider on layout
  setTimeout(function(){ gcCarouselUpdateSlider(culturaId); }, 100);
}

function gcCarGoto(culturaId, idx) {
  var car = gcCarState(culturaId);
  if (!car.items[idx] || idx === car.active) return;
  var target = car.items[idx];
  if (target && target.type === 'new') {
    car.prevActive = car.active;
    car.active = idx;
    gcCarSetTarget(culturaId, 'new');
    gcCarLayout(culturaId);
    gcCarMenuHide();
    return;
  }
  // guarda o rascunho atual antes de carregar os dados do registro
  var activeItem = car.items[car.active] || null;
  var wasNew = activeItem && activeItem.type === 'new';
  var cur = gcFormState(culturaId);
  car.savedDraft = wasNew
    ? { fields: Object.assign({}, cur.fields), treatments: getTreatmentRows(culturaId, 'g-') }
    : car.savedDraft || null;
  car.prevActive = car.active;
  car.active = idx;
  gcCarSetTarget(culturaId, 'record');
  gcCarLayout(culturaId);
}

function gcCarBindWheel(culturaId) {
  var wrap = document.getElementById('gc-car-' + culturaId);
  if (!wrap || wrap.dataset.wheelBound) return;
  wrap.dataset.wheelBound = '1';
  var lastMove = 0;
  wrap.addEventListener(
    'wheel',
    function (ev) {
      if (Math.abs(ev.deltaY) < 24) return;
      ev.preventDefault();
      var now = Date.now();
      if (now - lastMove < 280) return;
      lastMove = now;
      var car = gcCarState(culturaId);
      var idx = ev.deltaY > 0 ? car.active + 1 : car.active - 1;
      if (idx < 0 || idx >= car.items.length) return;
      gcCarGoto(culturaId, idx);
    },
    { passive: false }
  );
}

function gcCarClick(culturaId, idx, ev) {
  var car = gcCarState(culturaId);
  if (idx === car.active) return;
  if (ev && ev.stopPropagation) ev.stopPropagation();
  if (ev && ev.preventDefault) ev.preventDefault();
  gcCarGoto(culturaId, idx);
  var target = car.items[idx];
  if (target && target.type !== 'new') gcCarMenu(culturaId, idx, ev);
}

function gcRecToFields(rec) {
  var out = {};
  if (rec && rec.fields) out = Object.assign({}, rec.fields);
  if (rec) {
    if (rec.name !== undefined) out.name = rec.name;
    if (rec.location !== undefined) out.location = rec.location;
    if (rec.plantingDate) {
      out.plantingDate = rec.plantingDate;
    } else if (rec.date) {
      out.plantingDate = rec.date;
      out.date = rec.date;
    }
    if (rec.quantity) out.qty = rec.quantity;
    if (rec.unit) out.unit = rec.unit;
    if (rec.observations) out.observations = rec.observations;
  }
  return out;
}

function gcRenderTrtRows(culturaId, prefix) {
  prefix = prefix || 'g-';
  var container = document.getElementById(prefix + 't-rows-' + culturaId);
  if (!container) return;
  container.innerHTML = '';
  var st = gcFormState(culturaId);
  var list = st.treatments || [];
  list.forEach(function (t, i) {
    container.insertAdjacentHTML('beforeend', renderTreatmentRow(i, culturaId, prefix));
    var id = function (s) {
      return prefix + 't-' + s + '-' + i + '-' + culturaId;
    };
    if (t.date !== undefined) {
      var de = document.getElementById(id('date'));
      if (de) de.value = t.date;
    }
    if (t.type !== undefined) {
      var te = document.getElementById(id('type'));
      if (te) te.value = t.type;
    }
    if (t.product !== undefined) {
      var pe = document.getElementById(id('product'));
      if (pe) pe.value = t.product;
    }
    if (t.dose !== undefined) {
      var dos = document.getElementById(id('dose'));
      if (dos) dos.value = t.dose;
    }
    if (t.method !== undefined) {
      var me = document.getElementById(id('method'));
      if (me) me.value = t.method;
    }
  });
}

function gcCarSetTarget(culturaId, mode) {
  var car = gcCarState(culturaId);
  var editor = document.getElementById('gc-editor-' + culturaId);
  var st = gcFormState(culturaId);
  var rec = (car.items[car.active] && car.items[car.active].rec) || null;
  if (mode === 'new') {
    car.editingRecId = null;
    car.viewRecId = null;
    if (car.savedDraft) {
      st.fields = Object.assign({}, car.savedDraft.fields || {});
      st.treatments = (car.savedDraft.treatments || []).slice();
      car.savedDraft = null;
    } else {
      st.fields = st.fields || {};
      st.treatments = st.treatments || [];
    }
    if (editor) editor.classList.remove('viewing');
  } else {
    car.viewRecId = rec ? rec.id : null;
    car.editingRecId = mode === 'record' ? car.viewRecId : null;
    st.fields = gcRecToFields(rec);
    st.treatments = rec && rec.treatments ? rec.treatments.slice() : [];
    var nEl = document.querySelector('.detail-nome');
    var defs = gcFieldDefaults(nEl ? nEl.textContent : '');
    Object.keys(defs).forEach(function (k) {
      if (st.fields[k] === undefined || st.fields[k] === null || st.fields[k] === '')
        st.fields[k] = defs[k];
    });
    if (editor) editor.classList.toggle('viewing', mode === 'view');
  }
  gcRenderModule(culturaId, car.moduleId || 'id');
  gcRenderTrtRows(culturaId, 'g-');
  gcUpdatePreview(culturaId);
}

function gcCarMenu(culturaId, idx, ev) {
  var car = gcCarState(culturaId);
  var menu = document.getElementById('gcCarMenu');
  if (!menu) return;
  var x = (ev && ev.clientX) || 0;
  var y = (ev && ev.clientY) || 0;
  menu.innerHTML =
    '<div class="gc-car-menu-sep">' +
    (car.items[idx] && car.items[idx].rec ? gcEsc(car.items[idx].rec.name || 'Registro') : '') +
    '</div>' +
    '<button class="gc-car-menu-item" onclick="gcCarAction(' +
    culturaId +
    ',' +
    idx +
    ',\'salvar-editar\')"><i class="bi bi-pencil"></i> Salvar o outro e editar este depois</button>' +
    '<button class="gc-car-menu-item" onclick="gcCarAction(' +
    culturaId +
    ',' +
    idx +
    ',\'copiar\')"><i class="bi bi-files"></i> Copiar dados</button>' +
    '<button class="gc-car-menu-item" onclick="gcCarAction(' +
    culturaId +
    ',' +
    idx +
    ',\'visualizar\')"><i class="bi bi-eye"></i> Visualizar</button>' +
    '<button class="gc-car-menu-item warn" onclick="gcCarAction(' +
    culturaId +
    ',' +
    idx +
    ',\'voltar\')"><i class="bi bi-arrow-left"></i> Voltar</button>';
  menu.style.left = Math.min(x + 8, window.innerWidth - 320) + 'px';
  menu.style.top = Math.min(y + 8, window.innerHeight - 220) + 'px';
  menu.classList.add('open');
}

function gcCarAction(culturaId, idx, action) {
  var car = gcCarState(culturaId);
  var target = car.items[idx];
  var rec = (target && target.rec) || null;
  if (action === 'voltar') {
    car.active = car.prevActive;
    var tv = car.items[car.active];
    gcCarSetTarget(culturaId, tv && tv.type === 'new' ? 'new' : 'record');
    gcCarLayout(culturaId);
    gcCarMenuHide();
    return;
  }
  if (action === 'visualizar') {
    gcCarSetTarget(culturaId, 'view');
    gcCarLayout(culturaId);
    gcCarMenuHide();
    return;
  }
  if (action === 'copiar') {
    var st = gcFormState(culturaId);
    st.fields = gcRecToFields(rec);
    var nEl = document.querySelector('.detail-nome');
    var defs = gcFieldDefaults(nEl ? nEl.textContent : '');
    Object.keys(defs).forEach(function (k) {
      if (st.fields[k] === undefined || st.fields[k] === null || st.fields[k] === '')
        st.fields[k] = defs[k];
    });
    st.treatments = rec && rec.treatments ? rec.treatments.slice() : [];
    car.active = car.items.length - 1;
    car.editingRecId = null;
    car.viewRecId = null;
    var editor = document.getElementById('gc-editor-' + culturaId);
    if (editor) editor.classList.remove('viewing');
    gcRenderModule(culturaId, car.moduleId || 'id');
    gcRenderTrtRows(culturaId, 'g-');
    gcUpdatePreview(culturaId);
    gcCarLayout(culturaId);
    gcCarMenuHide();
    return;
  }
  if (action === 'salvar-editar') {
    // salva o outro (draft ativo) se tiver dados
    var wasNew = car.items[car.prevActive] && car.items[car.prevActive].type === 'new';
    var draft = car.savedDraft || null;
    var haveOther =
      wasNew &&
      draft &&
      draft.fields &&
      draft.fields.name &&
      String(draft.fields.name).trim() !== '';
    var finish = function () {
      car.pending[rec.id] = true;
      var complete = gcRecordCompleteness(culturaId, rec);
      if (!complete) {
        if (typeof showToast === 'function')
          showToast(
            'warning',
            'Registro incompleto: marcado com ponto vermelho, será atualizado depois.'
          );
      }
      car.active = idx;
      car.editingRecId = rec.id;
      car.viewRecId = rec.id;
      var editor = document.getElementById('gc-editor-' + culturaId);
      if (editor) editor.classList.remove('viewing');
      var st2 = gcFormState(culturaId);
      st2.fields = gcRecToFields(rec);
      st2.treatments = (rec.treatments || []).slice();
      gcRenderModule(culturaId, car.moduleId || 'id');
      gcRenderTrtRows(culturaId, 'g-');
      gcCarLayout(culturaId);
      gcCarMenuHide();
    };
    if (haveOther) {
      var saved = gcSaveRecordSilent(culturaId, draft);
      var then = saved && typeof saved.then === 'function' ? saved : Promise.resolve();
      then.then(function (ok) {
        if (ok) car.savedDraft = null;
        finish();
      });
    } else {
      finish();
    }
  }
}

function gcSaveRecordSilent(culturaId, draft) {
  var car = gcCarState(culturaId);
  var groupId = window._guideGroup[culturaId] || car.groupId || 'vegetal';
  var st = draft || gcFormState(culturaId);
  var rec = {
    cultureId: culturaId,
    groupId: groupId,
    status: 'ativo',
    name: st.fields.name || '',
    location: st.fields.location || '',
    fields: Object.keys(st.fields).reduce(function (o, k) {
      if (st.fields[k] !== undefined && st.fields[k] !== null) o[k] = st.fields[k];
      return o;
    }, {}),
    treatments: draft && draft.treatments ? draft.treatments : getTreatmentRows(culturaId, 'g-'),
  };
  return fetch('/api/registros-producao/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
    body: JSON.stringify(rec),
  })
    .then(function (resp) {
      return resp.ok ? resp.json() : null;
    })
    .catch(function () {
      return null;
    });
}

function gcCarMenuHide() {
  var menu = document.getElementById('gcCarMenu');
  if (menu) menu.classList.remove('open');
}

function gcCarViewBack(culturaId) {
  var car = gcCarState(culturaId);
  car.prevActive = car.active;
  car.active = car.items.length - 1;
  gcCarSetTarget(culturaId, 'new');
  gcCarLayout(culturaId);
  gcCarMenuHide();
}

function gcCarViewEdit(culturaId) {
  var car = gcCarState(culturaId);
  car.prevActive = car.active;
  gcCarSetTarget(culturaId, 'record');
  gcCarLayout(culturaId);
  gcCarMenuHide();
}

// ===== Tooltip flutuante do rail =====
function gcRailTooltipOpen(ev) {
  var tip = document.getElementById('gcRailFloat');
  if (!tip) return;
  var btn = ev.target && ev.target.closest ? ev.target.closest('.gc-rail-btn') : null;
  if (!btn) return;
  var title = (btn.getAttribute('data-title') || btn.textContent || '').trim().replace(/\s+/g, ' ');
  tip.textContent = title;
  gcRailTooltipMove(ev);
  tip.classList.add('show');
}

function gcRailTooltipMove(ev) {
  var tip = document.getElementById('gcRailFloat');
  if (!tip) return;
  var ox = 16,
    oy = 18;
  var x = ev.clientX + ox;
  var y = ev.clientY + oy;
  if (x + 220 > window.innerWidth) x = ev.clientX - ox - 200;
  if (y + 44 > window.innerHeight) y = ev.clientY - 48;
  tip.style.transform = 'translate(' + x + 'px,' + y + 'px)';
}

function gcRailHide() {
  var tip = document.getElementById('gcRailFloat');
  if (tip) tip.classList.remove('show');
}

function gcMenuOutsideClickOnce() {
  if (window._gcMenuBound) return;
  window._gcMenuBound = true;
  document.addEventListener('click', function (ev) {
    var menu = document.getElementById('gcCarMenu');
    if (!menu || !menu.classList.contains('open')) return;
    if (ev.target.closest && ev.target.closest('#gcCarMenu')) return;
    gcCarMenuHide();
  });
}

function gcBindRailTooltip() {
  var panel = document.getElementById('culturaDetail');
  if (!panel || panel.dataset.railBound) return;
  panel.dataset.railBound = '1';
  panel.addEventListener(
    'mouseover',
    function (ev) {
      var b = ev.target.closest ? ev.target.closest('.gc-rail-btn') : null;
      if (!b) return;
      gcRailTooltipOpen(ev);
    },
    true
  );
  panel.addEventListener(
    'mouseout',
    function (ev) {
      var b = ev.target.closest ? ev.target.closest('.gc-rail-btn') : null;
      if (!b) return;
      gcRailHide();
    },
    true
  );
  panel.addEventListener(
    'mousemove',
    function (ev) {
      if (!ev.target || !ev.target.closest('.gc-rail-btn')) return;
      gcRailTooltipMove(ev);
    },
    true
  );
}

function showCulturaDetail(culturaId, culturaNome, groupId) {
  groupId = groupId || 'vegetal';
  // Defende contra painéis órfãos de sessões anteriores (ver nota abaixo).
  gcLimparPaineisDuplicados();
  var panel = document.getElementById('culturaDetail');
  var overlay = document.getElementById('culturaOverlay');
  if (!panel) return;
  // O painel FICA dentro de `#content`. Saiu daqui para o `body` para não ser
  // sobrescrito pelo `HTML_UPDATE` do service worker — e foi isso que o
  // transformou em três painéis.
  //
  // MEDIDO 2026-10-06: `document.querySelectorAll('#culturaDetail')` devolvia
  // 3 elementos, todos com `parentElement === BODY` e todos com a classe
  // `active` a true. O `appendChild` tira o painel de `#content`; a navegação
  // seguinte da SPA reescreve `#content.innerHTML` e traz um painel NOVO, sem
  // o antigo. Cada abertura acrescentava um.
  //
  // Depois disto, `closeCulturaDetail()` fechava o primeiro que
  // `getElementById` devolvesse — o órfão mais antigo, invisível. Os dois
  // que estavam à vista continuavam abertos. Era o "não consigo fechar mais,
  // tenho de reiniciar a página": cada clique fechava um painel diferente dos
  // que ninguém via.
  //
  // A troca de conteúdo do painel é feita por `renderGuidePanel`, que escreve
  // em `.detail-body` — não depende de onde o painel mora.
  console.log('showCulturaDetail start', culturaId, culturaNome);
  panel.classList.add('gc-editor-panel');
  panel.querySelector('.detail-nome').textContent = culturaNome;
  panel.querySelector('.detail-body').innerHTML =
    '<div class="text-center py-8 text-slate-400"><i class="bi bi-arrow-repeat animate-spin text-2xl"></i><p class="mt-2 text-xs">Carregando dados...</p></div>';
  panel.classList.add('active');
  console.log('panel set active', culturaId, panel.classList.contains('active'), document.getElementById('culturaDetail')!==null);
  if (overlay) overlay.classList.add('active');
  document.body.classList.add('gc-panel-open');
  // Atualiza URL sem recarregar (SPA) - hibrido
  // Usa a guia correta por tipo: animal/aquatica/vegetal (nunca cai no painel errado)
  try{
    // Guarda a página de LISTA de onde viemos, para o fecho voltar a ela.
    //
    // MEDIDO 2026-10-06: na Guia Sistemas, abrir uma cultura de "Outras
    // Culturas" empurrava `/guias/vegetal/28477/` — o URL passou a dizer que
    // estavamos na guia vegetal com o sistema ainda na pagina de sistemas.
    // Ao fechar, o `closeCulturaDetail` reescrevia para `/guias/vegetal/`, a
    // mesma mentira ao contrario. Recarregar esse URL abria a guia vegetal: a
    // navegacao interna estava partida nos dois sentidos.
    //
    // So' quando o URL e' MESMO uma lista de guia. Se nao for — recarregar
    // `/guias/vegetal/28063/`, ou a SPA trocar o `#content` sem mexer no URL —
    // nao se guarda nada e o fecho usa a base da guia a que o painel pertence.
    // MEDIDO: guardar sem esta guarda tornava o valor "pegajoso" e fechar um
    // painel na guia vegetal devolvia o utilizador a Sistemas.
    var _aqui = location.pathname;
    var _base = '/guias/vegetal/';
    if(groupId === 'animal') _base = '/guias/animal/';
    else if(groupId === 'aquatica') _base = '/guias/aquatica/';

    // A base sai do PROPRIO URL, e nao do `groupId`.
    //
    // MEDIDO 2026-10-06: a Guia Animal abria em `/guias/vegetal/28548/`.
    // `showCulturaDetail` e' chamada TRES vezes por abertura: uma pelo
    // `onclick` do card (com 'animal'), e duas pela rota hibrida, que a
    // volta a chamar SEM `groupId`. Nessas, o default `'vegetal'` ganhava e
    // reescrevia o URL para a guia errada.
    //
    // Duas formas do URL:
    //   /guias/animal/          -> lista: a base e' essa
    //   /guias/animal/28548/    -> detalhe: a base e' o mesmo prefixo
    // Se nenhuma for (pagina de outro sitio), fica o `groupId` do card.
    var _m = /^\/guias\/([a-z]+)\/(\d+)\/?$/.exec(_aqui);
    if (_m) {
      _base = '/guias/' + _m[1] + '/';
    } else if (/^\/guias\/[a-z]+\/$/.test(_aqui)) {
      _base = _aqui;
    }
    // O fecho volta sempre para a base que acabámos de descobrir.
    window._gcListaPath = _base;
    var newUrl = _base + encodeURIComponent(culturaId) + '/';
    if(location.pathname !== newUrl){
      history.pushState({culturaId: culturaId, culturaNome: culturaNome}, '', newUrl);
    }
  }catch(e){}
  var _rendered=false;
  // `showCulturaDetail` arranca até 3 pedidos (2,0s / 2,0s / 2,5s). Se o
  // produtor carregar no X enquanto estão em voo, `closeCulturaDetail` fecha o
  // painel — mas o `Promise.all` continua a andar e o render chega depois,
  // escrevendo por cima de um painel já fechado. Este é o "demora a carregar
  // e volta a abrir sozinho": o fetche não é cancelado, é ignorado.
  var _fechado = false;
  function _safeRender(safras, apiRecords){
    if(_rendered) return;
    // Se entretanto o painel foi fechado para outra cultura, este render
    // já não é de ninguém: escreve no painel errado e rouba o ecrã.
    if(_fechado) { clearTimeout(_fallbackTimer); return; }
    _rendered=true;
    try{ renderAfterFetch(safras, apiRecords); }catch(e){ console.error('renderAfterFetch fail',e); var bd=document.querySelector('#culturaDetail .detail-body'); if(bd) bd.innerHTML='<div class="p-4 text-center text-sm">Erro ao renderizar. <button onclick="location.reload()" style="text-decoration:underline;">Recarregar</button></div>'; }
  }
  var _fallbackTimer=setTimeout(function(){ if(!_rendered){ console.warn('guide fallback render', culturaId); _safeRender([], []); } }, 3500);
  // `closeCulturaDetail` chama isto para travar os renders em voo do painel
  // que está a fechar.
  gcRegistarFechamento(panel, function(){ _fechado = true; clearTimeout(_fallbackTimer); });

  var cultureConfig = null;
  if (window.CulturesLoader) {
    cultureConfig = CulturesLoader.findByTitle(culturaNome);
  }

  gcFormState(culturaId).fields = gcFieldDefaults(culturaNome);
  gcFormState(culturaId).treatments = [];
  if (!window._guideGroup) window._guideGroup = {};
  if (!window._guideCfg) window._guideCfg = {};
  window._guideGroup[culturaId] = groupId;
  window._guideCfg[culturaId] = cultureConfig;

  // Render instantâneo com cache local para não esperar 3 APIs
  try{
    var cachedRecs = (window._guideCache && window._guideCache[culturaId]) || [];
    if(cachedRecs.length){
      // Renderiza imediatamente com cache, depois atualiza em background
      setTimeout(function(){
        try{ renderGuidePanel(culturaId, culturaNome, groupId, cachedRecs); }catch(e){}
      }, 10);
    }
  }catch(e){}

  // Fetch com timeout curto e cache
  function fetchWithTimeout(url, ms){
    var controller = new AbortController();
    var timer = setTimeout(function(){ controller.abort(); }, ms);
    return fetch(url, {credentials:'same-origin', signal: controller.signal}).then(function(r){ clearTimeout(timer); return r.json(); }).catch(function(){ clearTimeout(timer); return null; });
  }
  var cacheKey = 'guide:'+culturaId;
  var cachedData = null;
  try{ cachedData = JSON.parse(sessionStorage.getItem(cacheKey)||'null'); }catch(e){}
  // Hibrido: se tem cache mesmo expirado, mostra 0ms e revalida em background (stale-while-revalidate)
  if(cachedData){
    var isFresh = Date.now() - cachedData.ts < 30000;
    (function(){
      var safras = cachedData.safras || [];
      var apiRecords = cachedData.records || [];
      if (!window._guideCache) window._guideCache = {};
      window._guideCache[culturaId] = Array.isArray(apiRecords) ? apiRecords : [];
      _safeRender(safras, apiRecords);
    })();
    if(isFresh) return;
    // se expirado, continua para fetch em background e atualiza silencioso se mudou
  }


  // fallback: se Promise.all travar (SPA cold start), força render em 3.5s
  Promise.all([
    fetchWithTimeout('/api/safras/?cultura=' + culturaId, 2000).then(function(v){ return Array.isArray(v) ? v : (v && v.results ? v.results : []); }),
    fetchWithTimeout('/api/culturas/' + culturaId + '/', 2000).then(function(v){ return v||{}; }),
    fetchWithTimeout('/api/registros-producao/?cultura=' + encodeURIComponent(culturaId), 2500).then(function(v){ return v||[]; }),
  ]).then(function (results) {
    clearTimeout(_fallbackTimer);
    // hibrido: só re-renderiza se hash mudou (minimo delay)
    try{
      var newHash = JSON.stringify([safras, apiRecords]);
      var oldHash = cachedData ? JSON.stringify([cachedData.safras||[], cachedData.records||[]]) : null;
      if(oldHash && newHash===oldHash){
        // sem mudanca, não re-renderiza, mantém 0ms
        try{ sessionStorage.setItem(cacheKey, JSON.stringify({ts: Date.now(), safras: safras, records: apiRecords})); }catch(e){}
        return;
      }
    }catch(e){}
    var safras = results[0] || [];
    var apiRecords = Array.isArray(results[2]) ? results[2] : (results[2] && results[2].results ? results[2].results : []);
    if (!window._guideCache) window._guideCache = {};
    window._guideCache[culturaId] = Array.isArray(apiRecords) ? apiRecords : [];
    try{ sessionStorage.setItem(cacheKey, JSON.stringify({ts: Date.now(), safras: safras, records: apiRecords})); }catch(e){}
    renderAfterFetch(safras, apiRecords);
    // Pré-carrega async os próximos 3 IDs (28077 → 28078, 28079, 28080) para incrementar instantâneo
    setTimeout(function(){
      var base = parseInt(culturaId, 10);
      if(!isNaN(base)){
        for(var i=1;i<=3;i++){
          (function(nextId){
            var nk = 'guide:'+nextId;
            if(sessionStorage.getItem(nk)) return;
            Promise.all([
              fetchWithTimeout('/api/safras/?cultura=' + nextId, 1500).then(function(v){ return Array.isArray(v) ? v : (v && v.results ? v.results : []); }),
              fetchWithTimeout('/api/registros-producao/?cultura=' + encodeURIComponent(nextId), 1500).then(function(v){ return Array.isArray(v)?v:(v&&v.results?v.results:[]); })
            ]).then(function(res){
              try{ sessionStorage.setItem(nk, JSON.stringify({ts: Date.now(), safras: res[0]||[], records: res[1]||[]})); }catch(e){}
              if(!window._guideCache) window._guideCache={};
              window._guideCache[nextId]=res[1]||[];
            }).catch(function(){});
          })(String(base+i));
        }
      }
    }, 400);
  }).catch(function(){ clearTimeout(_fallbackTimer); _safeRender([], []); });

  function renderAfterFetch(safras, apiRecords){
    // normaliza paginado vs array (evita safras.forEach is not a function)
    safras = Array.isArray(safras) ? safras : (safras && safras.results ? safras.results : []);
    apiRecords = Array.isArray(apiRecords) ? apiRecords : (apiRecords && apiRecords.results ? apiRecords.results : []);
    // Renderiza imediatamente com temp ID para não bloquear (POST em background)
    var hasRecords = window._guideCache[culturaId].length > 0;
    var tempRec = null;
    if(!hasRecords){
      tempRec = {id: 'temp-'+culturaId, _isTemp:true, cultureId: culturaId};
      // Não bloqueia: dispara POST em background e atualiza cache quando retornar
      (function(){
        var groupId2 = groupId || 'vegetal';
        fetch('/api/registros-producao/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
          body: JSON.stringify({ cultureId: culturaId, groupId: groupId2, name: culturaNome, status: 'ativo', fields: {}, treatments: [] }),
        }).then(function(r){ return r.ok?r.json():null; }).then(function(newRec){
          if(newRec && newRec.id){
            // Substitui temp por real no cache
            var idx = window._guideCache[culturaId].indexOf(tempRec);
            if(idx>=0) window._guideCache[culturaId][idx]=newRec; else window._guideCache[culturaId].push(newRec);
            // Migra stages temp
            var tempKey='temp-'+culturaId;
            var tempStages=window._gcStageState[tempKey];
            if(tempStages && tempStages.length){
              tempStages.forEach(function(s){ s.registro=newRec.id; s._synced=false; });
              window._gcStageState[newRec.id]=(window._gcStageState[newRec.id]||[]).concat(tempStages);
              delete window._gcStageState[tempKey];
            }
          }
        }).catch(function(){});
      })();
    }
    // Renderiza imediatamente sem esperar POST
    (function(newRec){
      if(tempRec && !hasRecords){
        // Usa tempRec como newRec para migração inicial (sem id real)
        newRec = tempRec;
      }
      // Migrar stages de temp key para real record ID
      if (newRec && newRec.id) {
        var tempKey = 'temp-' + culturaId;
        var tempStages = window._gcStageState[tempKey];
        if (tempStages && tempStages.length > 0) {
          tempStages.forEach(function (stage) {
            stage.registro = newRec.id;
            stage._synced = false; // marcar para sync posterior
          });
          // Mover para nova key
          window._gcStageState[newRec.id] = (window._gcStageState[newRec.id] || []).concat(
            tempStages
          );
          delete window._gcStageState[tempKey];
        }
      }
      var totalArea = 0,
        totalProd = 0,
        totalRec = 0;
      safras.forEach(function (s) {
        totalArea += parseFloat(s.area_plantada) || 0;
        totalProd += parseFloat(s.producao_total) || 0;
        totalRec += parseFloat(s.receita_estimada) || 0;
      });
      if (!window._gcBase) window._gcBase = {};
      window._gcBase[culturaId] = { area: totalArea, prod: totalProd, rec: totalRec };
      var body = panel.querySelector('.detail-body');

      var configId = cultureConfig
        ? cultureConfig.id
        : 'cultura-' + culturaNome.toLowerCase().replace(/[^a-z0-9]/g, '-');
      var heroIco = HERO_ICONS[groupId] || 'bi-tree';
      var heroLabel =
        {
          vegetal: 'Vegetal',
          animal: 'Animal',
          aquatica: 'Aqu\u00edcola',
          extrativismo: 'Extrativismo',
        }[groupId] || 'Cultura';

      var records = mergeGuideRecords(apiRecords, guideLocalRecords(configId));
      var car = gcCarState(culturaId);
      car.groupId = groupId;
      car.items = records.map(function (r) {
        return { type: 'record', rec: r };
      });
      car.items.push({ type: 'new' });
      var newIdx = car.items.length - 1;
      car.active = newIdx;
      car.prevActive = newIdx;
      car.editingRecId = null;
      car.viewRecId = null;
      car.savedDraft = null;
      car.moduleId = (car.moduleId && window._gcModule && window._gcModule[culturaId]) || 'id';

      var html = '';

      // Context Bar
      html += '<div class="gc-context-bar">';
      html += '<div class="gc-context-left">';
      html += '<div class="gc-brand-mark">A</div>';
      html += '<span class="gc-brand-name">Ampliagro</span>';
      html += '<span class="gc-crumb-sep">/</span>';
      html += '<span class="gc-crumb">Guia ' + heroLabel + '</span>';
      html += '<span class="gc-crumb-sep">/</span>';
      html += '<span class="gc-crumb-current">' + gcEsc(culturaNome) + '</span>';
      html += '</div>';
      html += '</div>';

      // Hero Section
      html += '<div class="gc-hero">';
      html += '<div class="gc-hero-top">';
      html += '<div class="gc-hero-id">';
      html += '<div class="gc-hero-ava"><i class="bi ' + heroIco + '"></i></div>';
      html += '<div>';
      html +=
        '<div class="gc-hero-name" id="gc-hero-name-' +
        culturaId +
        '">' +
        gcEsc(culturaNome) +
        '</div>';
      html += '<div class="gc-hero-sub">Registros de produ\u00e7\u00e3o da cultura</div>';
      html += '<div class="gc-hero-editing"><i class="bi bi-pencil"></i> Editando dados</div>';
      html += '</div>';
      html += '</div>';
      html +=
        '<button class="gc-hero-close" onclick="closeCulturaDetail()" title="Fechar"><i class="bi bi-x-lg"></i></button>';
      html += '</div>';
      // Chips
      html += '<div class="gc-hero-chips">';
      html += '<div class="gc-chip"><i class="bi bi-geo-alt"></i> ' + gcEsc(heroLabel) + '</div>';
      html +=
        '<div class="gc-chip warm"><i class="bi bi-calendar3"></i> ' +
        gcFmt(totalArea, 1) +
        ' ha</div>';
      html +=
        '<div class="gc-chip"><i class="bi bi-graph-up-arrow"></i> ' +
        gcFmt(totalProd) +
        ' produ\u00e7\u00f5es</div>';
      html +=
        '<div class="gc-chip warm"><i class="bi bi-cash-stack"></i> R$ ' +
        gcFmt(totalRec, 2) +
        '</div>';
      html += '</div>';
      html += '</div>';

      // Carousel Section
      html += '<div class="gc-carousel-wrap">';
      html +=
        '<div class="gc-section-label"><h3><i class="bi bi-grid-3x3-gap"></i> Talh\u00f5es da Cultura</h3></div>';
      html += gcCarouselHTML(culturaId);
      html += '</div>';

      // Workspace
      html += '<div class="gc-workspace">';

      // Rail
      html += '<div class="gc-rail">';
      var defs = railDefs(groupId);
      defs.forEach(function (d) {
        html +=
          '<button type="button" class="gc-rail-btn' +
          (d.key === car.moduleId ? ' active' : '') +
          '" data-cultura="' +
          culturaId +
          '" data-module="' +
          d.key +
          '" data-title="' +
          d.title +
          '" onclick="gcRenderModule(' +
          culturaId +
          ",'" +
          d.key +
          '\')"><i class="bi ' +
          d.icon +
          '"></i><span>' +
          d.title +
          '</span></button>';
      });
      html += '</div>';

      // Content Pane
      html += '<div class="gc-content-pane">';
      html += '<div class="gc-module active" id="gc-module-' + culturaId + '"></div>';
      html += '</div>';

      html += '</div>'; // workspace

      // Action Bar
      html += '<div class="gc-action-bar">';
      html +=
        '<button class="gc-btn gc-btn-ghost" onclick="closeCulturaDetail()"><i class="bi bi-x-lg"></i> Cancelar</button>';
      html +=
        '<button class="gc-btn gc-btn-add" onclick="saveGuideProduction(' +
        culturaId +
        ", '" +
        groupId +
        '\', \'add\')"><i class="bi bi-plus-lg"></i> Salvar e Adicionar Outro</button>';
      html +=
        '<button class="gc-btn gc-btn-primary" onclick="saveGuideProduction(' +
        culturaId +
        ", '" +
        groupId +
        '\', \'close\')"><i class="bi bi-check2-circle"></i> Concluir Cadastro</button>';
      html += '</div>';

      body.innerHTML = html;
      ensureGuideStyles();
      gcRenderModule(culturaId, car.moduleId);
      gcUpdatePreview(culturaId);
      gcCarLayout(culturaId);
      gcCarBindWheel(culturaId);
      gcBindRailTooltip();
      if (car.viewRecId) {
        var editor = document.getElementById('gc-editor-' + culturaId);
        if (editor) editor.classList.add('viewing');
        gcRenderModule(culturaId, car.moduleId);
      }
    })(null);
  }
}

window.saveGuideProduction = function (culturaId, groupId, mode) {
  groupId = groupId || 'vegetal';
  var st = gcFormState(culturaId);
  var car = gcCarState(culturaId);
  var extra = {
    cultureId: culturaId,
    groupId: groupId,
    status: 'ativo',
    fields: {},
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  var record = car.editingRecId ? Object.assign({ id: car.editingRecId }, extra) : extra;
  var hasName = false;
  Object.keys(st.fields).forEach(function (key) {
    if (st.fields[key] === undefined || st.fields[key] === null) return;
    var val = st.fields[key];
    if (key === 'name') {
      record.name = val;
      if (String(val).trim()) hasName = true;
    } else if (key === 'location') {
      record.location = val;
    } else if (key === 'plantingDate' || key === 'date') {
      record.date = val;
      record.plantingDate = val;
    } else if (key === 'qty' || key === 'mudasQty') {
      record.quantity = gcNum(val);
    } else if (key === 'unit') {
      record.unit = val;
    } else if (key === 'observations') {
      record.observations = val;
    } else {
      record.fields[key] = val;
    }
  });
  if (!hasName) {
    if (typeof showToast === 'function') showToast('warning', 'Preencha o nome do registro');
    return;
  }
  record.treatments = getTreatmentRows(culturaId, 'g-');
  var nome = document.querySelector('.detail-nome');
  var culturaNome = nome ? nome.textContent : '';
  var payload = {
    cultureId: culturaId,
    groupId: groupId,
    status: record.status,
    name: record.name,
    location: record.location || '',
    date: record.date || record.plantingDate || '',
    plantingDate: record.plantingDate || record.date || '',
    quantity: record.quantity || 0,
    unit: record.unit || '',
    observations: record.observations || '',
    fields: record.fields || {},
    treatments: record.treatments || [],
  };
  fetch('/api/registros-producao/' + (record.id ? record.id + '/' : ''), {
    method: record.id ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
    body: JSON.stringify(payload),
  })
    .then(function (r) {
      if (!r.ok) throw new Error('api');
      return r.json();
    })
    .then(function (saved) {
      var savedId = saved && saved.id;
      if (window.ProductionRegistry) {
        record.id = savedId;
        ProductionRegistry.save(record);
      }
      var car = gcCarState(culturaId);
      var pendingKey = savedId !== undefined && savedId !== null ? savedId : record.id;
      if (car && pendingKey && car.pending) delete car.pending[pendingKey];
      if (typeof showToast === 'function') showToast('success', 'Registro salvo!');
      if (mode === 'close') {
        closeCulturaDetail();
      } else if (culturaNome) {
        showCulturaDetail(culturaId, culturaNome, groupId);
        var first = document.getElementById('g-prod-name-' + culturaId);
        if (first && typeof first.focus === 'function')
          setTimeout(function () {
            first.focus();
          }, 60);
      }
    })
    .catch(function () {
      var saved = null;
      if (window.ProductionRegistry) saved = ProductionRegistry.save(record);
      if (saved && typeof showToast === 'function')
        showToast('success', 'Registro salvo (offline)');
      if (mode === 'close') {
        closeCulturaDetail();
      } else if (culturaNome) {
        showCulturaDetail(culturaId, culturaNome, groupId);
        var fieldNode = document.getElementById('g-prod-name-' + culturaId);
        if (fieldNode && typeof fieldNode.focus === 'function')
          setTimeout(function () {
            fieldNode.focus();
          }, 60);
      }
    });
};

window.deleteGuideProduction = function (id, culturaId, culturaNome, groupId) {
  if (!confirm('Excluir este registro?')) return;
  fetch('/api/registros-producao/' + id + '/', {
    method: 'DELETE',
    headers: { 'X-CSRFToken': guideCsrf() },
  })
    .then(function (r) {
      if (!r.ok) throw new Error('api');
      if (window.ProductionRegistry) ProductionRegistry.remove(id);
      if (typeof showToast === 'function') showToast('success', 'Registro excluído');
      if (culturaNome) showCulturaDetail(culturaId, culturaNome, groupId);
    })
    .catch(function () {
      if (window.ProductionRegistry) ProductionRegistry.remove(id);
      if (culturaNome) showCulturaDetail(culturaId, culturaNome, groupId);
    });
};

// Apaga painéis/overlays órfãos que ficaram no `body`.
//
// MEDIDO 2026-10-06: uma sessão tinha 3 `#culturaDetail` e 2 `#culturaOverlay`
// soltos no `body`, todos com `active`, dois deles visíveis ao mesmo tempo.
// Nasceu disto o painel ser movido para fora de `#content` (ver nota em
// `showCulturaDetail`). O código que os criava já não existe, mas uma aba que
// já ficou com eles continua com eles até recarregar — daí esta limpeza, que
// também serve de rede de segurança se algo os voltar a criar.
// Liga um callback ao fecho do painel.
//
// `showCulturaDetail` deixa pedidos em voo (até 2,5s). Sem isto, fechar o
// painel durante um pedido não o impede de ser reescrito quando a resposta
// chega. O callback diz "ya foi" ao render pendente.
function gcRegistarFechamento(panel, fn) {
  if (!panel) return;
  if (panel.__gcOnClose) panel.__gcOnClose();
  panel.__gcOnClose = fn;
}

function gcLimparPaineisDuplicados() {
  var paineis = document.querySelectorAll('#culturaDetail');
  var overlays = document.querySelectorAll('#culturaOverlay');
  if (paineis.length <= 1 && overlays.length <= 1) return;
  // Mantém o primeiro de cada (o que está dentro de `#content`) e remove os
  // restantes, que são de facto lixo.
  for (var i = 1; i < paineis.length; i++) {
    if (paineis[i] && paineis[i].parentNode) paineis[i].parentNode.removeChild(paineis[i]);
  }
  for (var j = 1; j < overlays.length; j++) {
    if (overlays[j] && overlays[j].parentNode) overlays[j].parentNode.removeChild(overlays[j]);
  }
}

function closeCulturaDetail() {
  // Fecha TODOS os painéis com este id, não só o primeiro. Com o painel
  // duplicado no `body`, `getElementById` devolvia o mais antigo (invisível)
  // e os visíveis ficavam abertos — cada clique fechava um painel que ninguém
  // via, e o que estava à vista continuava lá.
var paineis = document.querySelectorAll('#culturaDetail');
  for (var i = 0; i < paineis.length; i++) {
    paineis[i].classList.remove('active');
    // Avisa os pedidos em voo de que este painel já foi fechado.
    if (typeof paineis[i].__gcOnClose === 'function') {
      try { paineis[i].__gcOnClose(); } catch (e) {}
      paineis[i].__gcOnClose = null;
    }
  }
  var overlays = document.querySelectorAll('#culturaOverlay');
  for (var j = 0; j < overlays.length; j++) overlays[j].classList.remove('active');
document.body.classList.remove('gc-panel-open');
  // Volta a URL para a página de LISTA de onde o painel foi aberto.
  //
  // Antes era uma expressão regular só para `/guias/vegetal/<id>` e escrevia
  // sempre `/guias/vegetal/`. Aberto a partir de Sistemas ou Apicultura, o URL
  // acabava a apontar para a guia vegetal — a página continuava a ser outra.
  try{
    var volta = window._gcListaPath || '/guias/vegetal/';
    if(location.pathname !== volta){
      history.pushState({}, '', volta);
    }
  }catch(e){}
}

// ── Strategy 2: Enriquecimento — badges + quick-insert ──
function decorateGuideCards() {
  document.querySelectorAll('.cultura-card').forEach(function (card) {
    var nameEl = card.querySelector('.cultura-name');
    if (!nameEl) return;
    var nome = nameEl.textContent.trim();

    // IDEMPOTENTE, e o badge do TEMPLATE conta como "ja existe".
    //
    // `guide.js` entra por DOIS sitios no mesmo template (o `data-spa-guide`
    // dentro do `{% block content %}` e o do `{% block scripts %}`), e o SPA
    // executa os scripts de cada partial que injeta. Nos dois caminhos este
    // `decorateGuideCards` corre mais do que uma vez por pagina.
    //
    // E o template JA traz `<span class="cultura-badge"></span>` dentro de
    // cada card. Criar outro aqui produzia dois badges sobrepostos — e era o
    // que aparecia: o do JS com o numero, o do template vazio por cima.
    //
    // MEDIDO 2026-10-06: os 456 cards ficavam com 3 badges cada, e o mesmo
    // para o botao de "adicionar" — ~1370 elementos e 456 handlers de clique
    // que nao pertencem a nada, e que se acumulam a cada navegacao.
    //
    // O badge do template e' REUTILIZADO (e' o elemento certo, ja tem a
    // classe e o sitio no CSS). O botao de adicionar so e' criado se ainda
    // nao existir.
    //
    // A ordem importa: `window._guideStats` e' definido por um script INLINE
    // do `{% block scripts %}`, e `guide.js` pode correr ANTES dele (o
    // `data-spa-guide`, dentro do `{% block content %}`, carrega primeiro).
    // MEDIDO 2026-10-06: com o `return` antecipado, o `updateBadge` nem
    // corria na primeira passagem — badge ficava em "0" mesmo com o
    // `_guideStats` cheio (cultura 28063 tinha 3 registros e mostrava 0).
    // Por isso o `return` so protege a criacao do BOTAO; a contagem corre
    // sempre, e a 2a passagem (com `_guideStats` ja pronto) preenche.
    // O badge so e' actualizado se o TEMPLATE o traz. Nao e' criado aqui.
    //
    // MEDIDO 2026-10-06: `guia-vegetal.html` traz `<span class="cultura-badge">`
    // em cada card; `guia-animal.html` e `guia-aquatica.html` NAO trazem — eles
    // mostram o `.cultura-hist` desenhado pelo servidor, que ou diz "N registos"
    // ou convida a registar. Criar o badge aqui punha "0" em cima de todos os
    // 138 cards de animal e 110 de aquatica, e o proprio template diz que nunca
    // se deve mostrar 0: "0 registos" afirma que o produtor foi ate a tela, viu
    // a raca e decidiu nao registar — e nao foi isso.
    var badge = card.querySelector('.cultura-badge');
    card.style.position = 'relative';

    if (!card.querySelector('.cultura-quick-add')) {

    // Quick-insert hover button
    var quickBtn = document.createElement('button');
    quickBtn.className = 'cultura-quick-add';
    quickBtn.innerHTML = '<i class="bi bi-plus-circle-fill"></i>';
    quickBtn.title = 'Adicionar registro rapido';
    quickBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      // Reuse showCulturaDetail to open the form
      var groupId = 'vegetal';
      // Try to infer group from card's parent tab-content
      var tabContent = card.closest('.tab-content');
      if (tabContent && tabContent.id) {
        var g = tabContent.id.replace('tab-', '');
        if (['vegetal', 'animal', 'aquatica', 'extrativismo'].indexOf(g) >= 0) groupId = g;
      }
      var id = card.dataset.culturaId;
      if (!id) {
        // Fall back to searching CulturesLoader by name
        if (window.CulturesLoader) {
          var found = CulturesLoader.findByTitle(nome);
          if (found) id = found.id;
        }
      }
      if (id) {
        showCulturaDetail(id, nome, groupId);
      } else {
        console.warn('Could not find cultura ID for', nome);
      }
    });
    card.appendChild(quickBtn);
    } // fim: botao criado so uma vez

    // Badge exibe quantia da cultura (registros+safras+talhoes daquela cultura) — não total
    function updateBadge() {
      // Sem badge no template nao ha o que mostrar. A guia animal/aquatica
      // tem o `.cultura-hist` do servidor — este numero seria um segundo
      // lugar para a mesma informacao, e sobriamente um "0" falso.
      if (!badge) return;
      function applyCount(count){
        var n = parseInt(count)||0;
        badge.textContent = n > 99 ? '99+' : String(n);
        badge.style.display = 'flex';
        badge.title = n + ' cadastro(s) nesta cultura';
        badge.style.background = n>0 ? 'var(--cor-primaria)' : 'var(--cor-borda)';
        badge.style.color = n>0 ? '#fff' : 'var(--cor-texto-fraco)';
      }
      var cid = card.dataset.culturaId;
      var count = 0;
      // 1) Tenta _guideStats por id e por nome
      try{
        if(window._guideStats){
          var s = window._guideStats[cid] || window._guideStats[nome] || window._guideStats[String(cid)];
          if(s) count = (s.registros||0)+(s.safras||0)+(s.talhoes||0);
          // se achou por id mas é 0, tenta por nome
          if(!count && window._guideStats[nome]) {
            var s2=window._guideStats[nome];
            count = (s2.registros||0)+(s2.safras||0)+(s2.talhoes||0);
          }
        }
      }catch(e){}
      // 2) Fallback ProductionRegistry + Safra local se ainda 0
      if(!count){
        try{
          if(window.ProductionRegistry){
            var all=ProductionRegistry.getAll();
            var c=0; all.forEach(function(r){
              if(String(r.cultureId)===String(cid) || r.name===nome || r.cultura===nome) c++;
            });
            if(c) count=c;
          }
        }catch(e){}
      }
      // Sem fallback API por card para evitar N+1 flood (20 cards × 3 fetches = 60 req)
      // guide_stats já vem do servidor com contagem bulk para todas as culturas
      applyCount(count);
    }
    updateBadge();
  });
}

// `ligar` corre UMA vez por pagina: sao listeners de `document`, e um
// listener em `document` nao morre com o `innerHTML` do SPA. Sem esta
// separacao, cada navegacao adicionava mais um conjunto, e o `Escape`
// passava a fechar o painel varias vezes.
function ligarGuiaUmaVez() {
  if (window._guiaLigada) return;
  window._guiaLigada = true;
  initSubTabs();
  var closeBtn = document.getElementById('culturaDetailClose');
  if (closeBtn) closeBtn.addEventListener('click', closeCulturaDetail);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeCulturaDetail();
      document.querySelectorAll('.gc-stage-inline.open,.gc-task-inline.open').forEach(function (f) {
        f.classList.remove('open');
      });
    }
  });
}

// A decoracao corre SEMPRE: o `innerHTML` do SPA substitui os cards, e os
// novos precisam de badge e botao. `decorateGuideCards` e' idempotente
// (reusa o badge do template e nao recria o botao se ja existir).
function initGuideReady() {
  ligarGuiaUmaVez();
  decorateGuideCards();
}

// Publicada em `window` de proposito: o script inline do template que le o
// `guideStatsData` chama isto depois de publicar `window._guideStats`, porque
// os badges so' podem ser contados DEPOIS de os dados existirem. Ver o
// comentario em guia-vegetal.html.
window.decorateGuideCards = decorateGuideCards;

// ══════════════════════════════════════════════════════════
//  SISTEMA DE ESTÁGIOS DINÂMICOS + TAREFAS
// ══════════════════════════════════════════════════════════

var DEFAULT_PHASES = [
  { nome: 'Dormência', cor: '#94a3b8', icone: 'bi-moon-fill', tipo: 'estagio' },
  { nome: 'Floração', cor: '#a5b4fc', icone: 'bi-flower1', tipo: 'estagio' },
  { nome: 'Chumbinho', cor: '#86efac', icone: 'bi-circle-fill', tipo: 'estagio' },
  { nome: 'Granação', cor: '#16a34a', icone: 'bi-capsule', tipo: 'estagio' },
  { nome: 'Maturação', cor: '#f59e0b', icone: 'bi-fire', tipo: 'estagio' },
  { nome: 'Colheita', cor: '#dc2626', icone: 'bi-scissors', tipo: 'estagio' },
];

var STAGE_COLORS = [
  '#94a3b8',
  '#a5b4fc',
  '#86efac',
  '#16a34a',
  '#f59e0b',
  '#dc2626',
  '#6366f1',
  '#ec4899',
  '#8b5cf6',
  '#14b8a6',
];

// Estado local dos estágios por registro
window._gcStageState = {};
window._gcActiveStageByCulture = window._gcActiveStageByCulture || {};
function gcStageState(registroId) {
  if (!window._gcStageState[registroId]) window._gcStageState[registroId] = [];
  return window._gcStageState[registroId];
}

// Normaliza a resposta da API numa lista.
//
// MEDIDO 2026-10-06: `/api/estagios-cultura/` responde com o envelope de
// paginação do DRF — `{count, next, previous, results}` — e NAO com um array.
// Passado tal como vem, `gcStageState()` devolvia um objecto e
// `gcRenderPhaseBar` rebentava em `estagios.forEach is not a function`,
// dentro de uma promise, sem se ver nada no painel.
//
// O mesmo estrago ja tinha sido corrigido em `renderAfterFetch` (lá diz
// "normaliza paginado vs array") e ficou por aqui: duas copias do mesmo
// teste de tipo, uma feita e outra nao.
function gcNormalizaLista(v) {
  if (Array.isArray(v)) return v;
  if (v && Array.isArray(v.results)) return v.results;
  return [];
}

// ── Carregar estágios (local primeiro, depois API) ──
function gcLoadStages(registroId) {
  // Carregar do local primeiro
  var local = window.StageRegistry ? StageRegistry.getByRegistro(registroId) : [];
  if (local.length > 0) {
    // Mesclar com dados da API
    return fetch('/api/estagios-cultura/?registro=' + registroId, {
      headers: { 'X-CSRFToken': guideCsrf() },
    })
      .then(function (r) {
        return r.ok ? r.json() : [];
      })
      .then(function (apiData) {
        var remoto = gcNormalizaLista(apiData);
        if (remoto.length === 0) return local;
        // Usar dados da API como fonte de verdade, mas manter locais não sincronizados
        var merged = remoto.slice();
        local.forEach(function (l) {
          if (typeof l.id === 'string' && l.id.indexOf('local-') === 0) {
            merged.push(l);
          }
        });
        return merged;
      })
      .catch(function () {
        return local;
      });
  }
  return fetch('/api/estagios-cultura/?registro=' + registroId, {
    headers: { 'X-CSRFToken': guideCsrf() },
  })
    .then(function (r) {
      return r.ok ? r.json() : [];
    })
    .then(function (apiData) {
      return gcNormalizaLista(apiData);
    })
    .catch(function () {
      return [];
    });
}

// ── Salvar estágio (offline-first) ──
function gcSaveStageApi(data) {
  // Salvar local primeiro
  var local = window.StageRegistry ? StageRegistry.save(data) : data;

  var url =
    data.id && typeof data.id === 'number'
      ? '/api/estagios-cultura/' + data.id + '/'
      : '/api/estagios-cultura/';
  var method = data.id && typeof data.id === 'number' ? 'PATCH' : 'POST';
  return fetch(url, {
    method: method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
    body: JSON.stringify(data),
  })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .then(function (saved) {
      if (saved && window.StageRegistry) {
        // Atualizar ID local com ID do servidor
        local.id = saved.id;
        local._synced = true;
        StageRegistry.save(local);
      }
      return saved || local;
    })
    .catch(function () {
      return local;
    });
}

// ── Deletar estágio (offline-first) ──
function gcDeleteStageApi(id) {
  if (window.StageRegistry) StageRegistry.remove(id);
  if (typeof id === 'string' && id.indexOf('local-') === 0) return Promise.resolve(true);
  return fetch('/api/estagios-cultura/' + id + '/', {
    method: 'DELETE',
    headers: { 'X-CSRFToken': guideCsrf() },
  })
    .then(function (r) {
      return r.ok;
    })
    .catch(function () {
      return true;
    });
}

// ── Salvar tarefa (offline-first) ──
function gcSaveTaskApi(data) {
  var local = window.StageRegistry ? StageRegistry.saveTarefa(data) : data;

  var url =
    data.id && typeof data.id === 'number'
      ? '/api/tarefas-estagio/' + data.id + '/'
      : '/api/tarefas-estagio/';
  var method = data.id && typeof data.id === 'number' ? 'PATCH' : 'POST';
  return fetch(url, {
    method: method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
    body: JSON.stringify(data),
  })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .then(function (saved) {
      if (saved && window.StageRegistry) {
        local.id = saved.id;
        local._synced = true;
        StageRegistry.saveTarefa(local);
      }
      return saved || local;
    })
    .catch(function () {
      return local;
    });
}

// ── Toggle tarefa concluída (offline-first) ──
function gcToggleTaskApi(tarefaId) {
  var local = window.StageRegistry ? StageRegistry.toggleTarefa(tarefaId) : null;
  if (typeof tarefaId === 'string' && tarefaId.indexOf('local-') === 0)
    return Promise.resolve(local);
  return fetch('/api/tarefas-estagio/' + tarefaId + '/toggle_concluida/', {
    method: 'POST',
    headers: { 'X-CSRFToken': guideCsrf() },
  })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .catch(function () {
      return local;
    });
}

// ── Deletar tarefa (offline-first) ──
function gcDeleteTaskApi(id) {
  if (typeof id === 'string' && id.indexOf('local-') === 0) return Promise.resolve(true);
  return fetch('/api/tarefas-estagio/' + id + '/', {
    method: 'DELETE',
    headers: { 'X-CSRFToken': guideCsrf() },
  })
    .then(function (r) {
      return r.ok;
    })
    .catch(function () {
      return true;
    });
}

// ── Buscar funcionários para autocomplete ──
window._gcFuncionariosCache = null;
function gcGetFuncionarios() {
  if (window._gcFuncionariosCache) return Promise.resolve(window._gcFuncionariosCache);
  return fetch('/api/funcionarios/', {
    headers: { 'X-CSRFToken': guideCsrf() },
  })
    .then(function (r) {
      return r.ok ? r.json() : [];
    })
    .then(function (data) {
      window._gcFuncionariosCache = Array.isArray(data) ? data : data.results || [];
      return window._gcFuncionariosCache;
    })
    .catch(function () {
      return [];
    });
}

// ── Renderizar barra de fases ──
function gcRenderPhaseBar(registroId, estagios, culturaId) {
  // Barreira: um `forEach` em vez de array rebentava o painel inteiro, dentro
  // de uma promise, e o unico sintoma era um erro na consola. E' o terceiro
  // sitio onde um valor da API entra sem ser verificado (`renderAfterFetch`,
  // `gcLoadStages`, e agora aqui). Em vez de repetir o `Array.isArray` a cada
  // uso, e' uma funcao so.
  estagios = gcNormalizaLista(estagios);
  var faseAtual = 0;
  var pct = 0;
  var st = gcFormState(culturaId);
  var f = st.fields || {};
  var plantio = f.plantingDate || '';
  var ciclo = f.cicloDias ? parseInt(f.cicloDias) : 0;
  if (!ciclo && plantio && f.colheitaDate) {
    var dp = new Date(plantio);
    var dc = new Date(f.colheitaDate);
    if (!isNaN(dp.getTime()) && !isNaN(dc.getTime()))
      ciclo = Math.round((dc - dp) / (1000 * 60 * 60 * 24));
  }
  if (ciclo && plantio) {
    var dp2 = new Date(plantio);
    if (!isNaN(dp2.getTime())) {
      var hoje = new Date();
      var decorrido = Math.max(0, Math.round((hoje - dp2) / (1000 * 60 * 60 * 24)));
      pct = Math.min(100, Math.round((decorrido / ciclo) * 100));
      faseAtual = Math.min(
        estagios.length - 1,
        Math.floor(pct / (100 / Math.max(1, estagios.length)))
      );
    }
  }

  // Se não tem estágios salvos, usar os 6 padrão como itens visuais
  if (estagios.length === 0) {
    estagios = DEFAULT_PHASES.map(function (p, i) {
      return {
        id: null,
        nome: p.nome,
        cor: p.cor,
        icone: p.icone,
        tipo: 'estagio',
        concluido: false,
        ordem: i,
        sub_estagios: [],
        tarefas: [],
        _isDefault: true,
      };
    });
  }

  // Sempre-quote registroId para onclick
  var rid = String(registroId).replace(/'/g, "\\'");

  var activeIdx = window._gcActiveStageByCulture[culturaId];
  if (typeof activeIdx !== 'number' || activeIdx < 0 || activeIdx >= estagios.length)
    activeIdx = Math.max(0, Math.min(faseAtual, estagios.length - 1));
  window._gcActiveStageByCulture[culturaId] = activeIdx;

  var activeEstagio = estagios[activeIdx];
  var html = '<div class="gc-phase-bar">';
  html += '<div class="gc-stage-tabs-shell">';
  html += '<div class="gc-stage-tabs-track">';

  estagios.forEach(function (est, idx) {
    var tarefas = est.tarefas || [];
    var doneCount = tarefas.filter(function (t) {
      return t.concluida;
    }).length;
    var isDone = tarefas.length > 0 && doneCount === tarefas.length;
    var isActive = idx === activeIdx;
    var draggable = !est._isDefault && est.id !== null && est.id !== undefined;

    html +=
      '<button type="button" class="gc-stage-tab' +
      (isActive ? ' active' : '') +
      '"' +
      (draggable ? ' data-draggable="true"' : '') +
      ' data-idx="' +
      idx +
      '" data-estagio-id="' +
      (est.id !== null && est.id !== undefined ? est.id : 'null') +
      '" onclick="gcSetActiveStage(\'' +
      culturaId +
      "'," +
      idx +
      ')">';
    if (draggable)
      html +=
        '<span class="gc-drag-handle" draggable="true" title="Arrastar para os lados"><i class="bi bi-grip-vertical"></i></span>';
    html +=
      '<span class="gc-stage-tab-dot" style="background:' +
      gcEsc(est.cor || '#6366f1') +
      ';"></span>';
    html +=
      '<span class="gc-stage-tab-name"><i class="bi ' +
      gcEsc(est.icone || 'bi-circle-fill') +
      '" style="font-size:10px;color:' +
      gcEsc(est.cor || '#6366f1') +
      ';"></i>' +
      gcEsc(est.nome) +
      '</span>';
    if (tarefas.length > 0)
      html +=
        '<span class="gc-stage-tab-badge' +
        (isDone ? ' done' : '') +
        '">' +
        doneCount +
        '/' +
        tarefas.length +
        '</span>';
    html += '</button>';
  });
  html += '</div>';
  html +=
    '<button type="button" class="gc-stage-tab-add" onclick="gcToggleStageForm(\'' +
    culturaId +
    "','" +
    rid +
    '\',null)"><i class="bi bi-plus-lg"></i> Novo estágio</button>';
  html += '</div>';

  html += '<div class="gc-stage-panel" data-stage-panel="' + activeIdx + '">';
  if (activeEstagio) {
    var tarefasAtivas = activeEstagio.tarefas || [];
    var activeDraggable =
      !activeEstagio._isDefault && activeEstagio.id !== null && activeEstagio.id !== undefined;
    var activeEstagioIdJs =
      activeEstagio.id !== null && activeEstagio.id !== undefined ? activeEstagio.id : 'null';

    html += '<div class="gc-stage-panel-head">';
    html +=
      '<div class="gc-stage-panel-title"><span class="gc-stage-tab-dot" style="background:' +
      gcEsc(activeEstagio.cor || '#6366f1') +
      ';"></span><i class="bi ' +
      gcEsc(activeEstagio.icone || 'bi-circle-fill') +
      '" style="font-size:11px;color:' +
      gcEsc(activeEstagio.cor || '#6366f1') +
      ';"></i> ' +
      gcEsc(activeEstagio.nome) +
      '</div>';
    if (activeDraggable) {
      html += '<div class="gc-phase-actions">';
      html +=
        '<button onclick="gcToggleStageForm(\'' +
        culturaId +
        "','" +
        rid +
        "'," +
        activeEstagio.id +
        ')" title="Editar"><i class="bi bi-pencil"></i></button>';
      html +=
        '<button class="danger" onclick="gcDeleteStageConfirm(\'' +
        rid +
        "'," +
        activeEstagio.id +
        ",'" +
        culturaId +
        '\')" title="Excluir"><i class="bi bi-trash3"></i></button>';
      html += '</div>';
    } else {
      html += '<div class="gc-stage-panel-hint">fase base</div>';
    }
    html += '</div>';

    html +=
      '<div class="gc-stage-inline" id="gc-stage-edit-' +
      (activeEstagio.id || activeIdx) +
      '-' +
      culturaId +
      '"></div>';

    if (tarefasAtivas.length > 0) {
      html += '<div class="gc-task-list">';
      tarefasAtivas.forEach(function (tarefa, tIdx) {
        var checkClass = 'gc-task-check' + (tarefa.concluida ? ' checked' : '');
        var tarefaIdJs = typeof tarefa.id === 'string' ? "'" + tarefa.id + "'" : tarefa.id;
        html +=
          '<div class="gc-task-item" data-tarefa-id="' +
          tarefa.id +
          '" data-estagio-idx="' +
          activeIdx +
          '" data-tidx="' +
          tIdx +
          '"' +
          (tarefa.id ? ' data-draggable="true"' : '') +
          '>';
        html +=
          '<span class="gc-drag-handle" draggable="true" title="Arrastar para reordenar" onmousedown="event.stopPropagation()"><i class="bi bi-grip-vertical"></i></span>';
        html +=
          '<div class="' +
          checkClass +
          '" onclick="gcToggleTask(\'' +
          rid +
          "'," +
          activeEstagioIdJs +
          ',' +
          tarefaIdJs +
          ",'" +
          culturaId +
          '\')"><i class="bi bi-check2"></i></div>';
        html +=
          '<span class="gc-task-desc' +
          (tarefa.concluida ? ' done' : '') +
          '">' +
          gcEsc(tarefa.descricao || 'Tarefa') +
          '</span>';
        var attrParts = [];
        if (tarefa.funcionario_nome) attrParts.push(tarefa.funcionario_nome);
        if (tarefa.cargo_alvo) attrParts.push(tarefa.cargo_alvo);
        if (tarefa.setor) attrParts.push(tarefa.setor);
        if (attrParts.length > 0)
          html += '<span class="gc-task-attr">' + gcEsc(attrParts.join(' \u00b7 ')) + '</span>';
        if (tarefa.id) {
          html += '<div class="gc-sub-actions">';
          html +=
            '<button onclick="gcToggleInlineTaskEdit(\'' +
            culturaId +
            "','" +
            rid +
            "'," +
            activeEstagioIdJs +
            ',' +
            tarefaIdJs +
            ')" title="Editar"><i class="bi bi-pencil"></i></button>';
          html +=
            '<button class="danger" onclick="gcDeleteTaskConfirm(\'' +
            rid +
            "'," +
            activeEstagioIdJs +
            ',' +
            tarefaIdJs +
            ",'" +
            culturaId +
            '\')" title="Excluir"><i class="bi bi-trash3"></i></button>';
          html += '</div>';
        }
        html += '</div>';
        html +=
          '<div class="gc-task-inline" id="gc-task-edit-' +
          tarefa.id +
          '-' +
          culturaId +
          '"></div>';
      });
      html += '</div>';
    }

    var inlineId = 'gc-task-inline-' + (activeEstagio.id || activeIdx) + '-' + culturaId;
    html +=
      '<button class="gc-task-add-btn" onclick="gcToggleInlineTask(\'' +
      inlineId +
      '\')"><i class="bi bi-plus"></i> Tarefa</button>';
    html += '<div class="gc-task-inline" id="' + inlineId + '">';
    html +=
      '<textarea id="' +
      inlineId +
      '-desc" rows="2" placeholder="Descreva a tarefa..."></textarea>';
    html += '<div class="gc-task-inline-attrs">';
    html +=
      '<select id="' + inlineId + '-func"><option value="">Funcion\u00e1rio</option></select>';
    html +=
      '<select id="' +
      inlineId +
      '-cargo"><option value="">Cargo</option><option value="GERENTE">Gerente</option><option value="TRATORISTA">Tratorista</option><option value="VAQUEIRO">Vaqueiro</option><option value="ADMIN">Administrativo</option><option value="SERVICO">Servi\u00e7os Gerais</option><option value="TECNICO">T\u00e9cnico Agr\u00edcola</option><option value="ENGENHEIRO">Eng. Agr\u00f4nomo</option><option value="OUTRO">Outro</option></select>';
    html += '<input id="' + inlineId + '-setor" placeholder="Setor">';
    html += '</div>';
    html += '<div class="gc-task-inline-btns">';
    html +=
      '<button class="gc-ti-cancel" onclick="gcToggleInlineTask(\'' +
      inlineId +
      '\')">Cancelar</button>';
    html +=
      '<button class="gc-ti-save" onclick="gcSaveInlineTask(\'' +
      inlineId +
      "','" +
      rid +
      "'," +
      activeEstagioIdJs +
      ",'" +
      culturaId +
      '\')"><i class="bi bi-check-lg"></i> Salvar</button>';
    html += '</div>';
    html += '</div>';
  }
  html += '</div>';
  html +=
    '<div class="gc-stage-add-inline-wrap"><div class="gc-stage-inline" id="gc-stage-add-' +
    culturaId +
    '"></div></div>';
  html += '</div>';
  return html;
}

window.gcSetActiveStage = function (culturaId, idx) {
  window._gcActiveStageByCulture[culturaId] = idx;
  var container = document.getElementById('gc-phases-' + culturaId);
  if (!container) return;
  var registroId = container.dataset.registroId;
  if (registroId === undefined || registroId === null || registroId === '') return;
  gcRefreshPhases(registroId, culturaId);
};

// ── Toggle tarefa ──
window.gcToggleTask = function (registroId, estagioId, tarefaId, culturaId) {
  gcToggleTaskApi(tarefaId).then(function (updated) {
    if (updated) {
      // Atualizar estado local
      var ests = gcStageState(registroId);
      ests.forEach(function (est) {
        if (est.id === estagioId && est.tarefas) {
          est.tarefas.forEach(function (t) {
            if (t.id === tarefaId) {
              t.concluida = updated.concluida;
              t.concluida_em = updated.concluida_em;
            }
          });
        }
      });
      gcRefreshPhases(registroId, culturaId);
    }
  });
};

// ── Toggle formulário inline de tarefa ──
window.gcToggleInlineTask = function (inlineId) {
  var el = document.getElementById(inlineId);
  if (!el) return;
  var isOpen = el.classList.contains('open');
  // Fechar todos os outros inline abertos
  document.querySelectorAll('.gc-task-inline.open').forEach(function (f) {
    f.classList.remove('open');
  });
  if (!isOpen) {
    el.classList.add('open');
    // Preencher funcionários
    var funcSel = document.getElementById(inlineId + '-func');
    if (funcSel && funcSel.options.length <= 1) {
      gcGetFuncionarios().then(function (funcs) {
        funcs.forEach(function (fn) {
          funcSel.innerHTML +=
            '<option value="' +
            fn.id +
            '">' +
            gcEsc(fn.nome) +
            (fn.cargo ? ' (' + gcEsc(fn.cargo) + ')' : '') +
            '</option>';
        });
      });
    }
    var desc = document.getElementById(inlineId + '-desc');
    if (desc)
      setTimeout(function () {
        desc.focus();
      }, 100);
  }
};

// ── Salvar tarefa inline ──
window.gcSaveInlineTask = function (inlineId, registroId, estagioId, culturaId) {
  var desc = document.getElementById(inlineId + '-desc');
  var funcSel = document.getElementById(inlineId + '-func');
  var cargoSel = document.getElementById(inlineId + '-cargo');
  var setorInput = document.getElementById(inlineId + '-setor');
  var texto = desc ? desc.value.trim() : '';
  if (!texto) {
    if (desc) desc.focus();
    return;
  }

  // Se estagioId é null/undefined, criar estágio pai primeiro
  var isNewStage =
    !estagioId || estagioId === 'null' || estagioId === null || estagioId === undefined;
  var isTempRegistro = typeof registroId === 'string' && registroId.indexOf('temp-') === 0;

  if (isNewStage) {
    var ests = gcStageState(registroId);
    var defaultEst =
      ests.find(function (e) {
        return e._isDefault;
      }) || ests[0];
    var estPayload = {
      registro: registroId,
      nome: defaultEst ? defaultEst.nome : 'Novo Estágio',
      cor: defaultEst ? defaultEst.cor : '#6366f1',
      icone: defaultEst ? defaultEst.icone : 'bi-circle-fill',
      ordem: defaultEst ? defaultEst.ordem || 0 : 0,
      tipo: 'estagio',
      concluido: false,
    };
    // Se registro é temp, criar apenas localmente (não chamar API)
    if (isTempRegistro) {
      var localId = 'local-s-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
      var localStage = Object.assign({}, estPayload, { id: localId, _synced: false });
      var ests2 = gcStageState(registroId);
      if (
        !ests2.find(function (e) {
          return e.id === localStage.id;
        })
      ) {
        localStage.tarefas = localStage.tarefas || [];
        localStage.sub_estagios = localStage.sub_estagios || [];
        ests2.push(localStage);
      }
      _gcSaveInlineTaskInner(
        localStage.id,
        texto,
        funcSel,
        cargoSel,
        setorInput,
        registroId,
        culturaId,
        inlineId
      );
    } else {
      gcSaveStageApi(estPayload).then(function (saved) {
        if (saved) {
          // Adicionar ao estado local
          var ests2 = gcStageState(registroId);
          if (
            !ests2.find(function (e) {
              return e.id === saved.id;
            })
          ) {
            saved.tarefas = saved.tarefas || [];
            saved.sub_estagios = saved.sub_estagios || [];
            ests2.push(saved);
          }
          _gcSaveInlineTaskInner(
            saved.id,
            texto,
            funcSel,
            cargoSel,
            setorInput,
            registroId,
            culturaId,
            inlineId
          );
        }
      });
    }
  } else {
    _gcSaveInlineTaskInner(
      estagioId,
      texto,
      funcSel,
      cargoSel,
      setorInput,
      registroId,
      culturaId,
      inlineId
    );
  }
};

function _gcSaveInlineTaskInner(
  estagioId,
  texto,
  funcSel,
  cargoSel,
  setorInput,
  registroId,
  culturaId,
  inlineId
) {
  var payload = {
    estagio: estagioId,
    descricao: texto,
    concluida: false,
    ordem: 0,
  };
  if (funcSel && funcSel.value) payload.funcionario = parseInt(funcSel.value);
  if (cargoSel && cargoSel.value) payload.cargo_alvo = cargoSel.value;
  if (setorInput && setorInput.value.trim()) payload.setor = setorInput.value.trim();

  gcSaveTaskApi(payload).then(function (saved) {
    if (saved) {
      // Adicionar ao estado local
      var ests = gcStageState(registroId);
      ests.forEach(function (est) {
        if (est.id === estagioId) {
          est.tarefas = est.tarefas || [];
          est.tarefas.push(saved);
        }
      });
      gcRefreshPhases(registroId, culturaId);
      if (typeof showToast === 'function') showToast('success', 'Tarefa criada!');
    }
  });
}

// ── Refresh das fases na UI ──
function gcRefreshPhases(registroId, culturaId) {
  var container = document.getElementById('gc-phases-' + culturaId);
  if (!container) return;
  container.dataset.registroId = registroId;
  var ests = gcStageState(registroId);
  container.innerHTML = gcRenderPhaseBar(registroId, ests, culturaId);
  gcSetupDnD(culturaId, registroId);
}

// ── Confirmar e deletar estágio ──
window.gcDeleteStageConfirm = function (registroId, estagioId, culturaId) {
  if (!confirm('Excluir este estágio e todas as suas tarefas?')) return;
  gcDeleteStageApi(estagioId).then(function (ok) {
    if (ok) {
      var ests = gcStageState(registroId);
      window._gcStageState[registroId] = ests.filter(function (e) {
        return e.id !== estagioId;
      });
      gcRefreshPhases(registroId, culturaId);
      if (typeof showToast === 'function') showToast('success', 'Estágio excluído');
    }
  });
};

// ── Confirmar e deletar tarefa ──
window.gcDeleteTaskConfirm = function (registroId, estagioId, tarefaId, culturaId) {
  if (!confirm('Excluir esta tarefa?')) return;
  gcDeleteTaskApi(tarefaId).then(function (ok) {
    if (ok) {
      var ests = gcStageState(registroId);
      ests.forEach(function (est) {
        if (est.id === estagioId) {
          est.tarefas = (est.tarefas || []).filter(function (t) {
            return t.id !== tarefaId;
          });
        }
      });
      gcRefreshPhases(registroId, culturaId);
      if (typeof showToast === 'function') showToast('success', 'Tarefa excluída');
    }
  });
};

// ══════════════════════════════════════════════════════════
//  FORM INLINE DE ESTÁGIO (adicionar/editar)
// ══════════════════════════════════════════════════════════

window.gcToggleStageForm = function (culturaId, registroId, estagioId) {
  // Fechar outros forms abertos
  document.querySelectorAll('.gc-stage-inline.open').forEach(function (f) {
    f.classList.remove('open');
  });
  document.querySelectorAll('.gc-task-inline.open').forEach(function (f) {
    f.classList.remove('open');
  });

  var formId,
    container,
    est = null;
  if (estagioId) {
    formId = 'gc-stage-edit-' + estagioId + '-' + culturaId;
    container = document.getElementById(formId);
    var ests = gcStageState(registroId);
    est = ests.find(function (e) {
      return e.id === estagioId;
    });
    if (!est) return;
  } else {
    formId = 'gc-stage-add-' + culturaId;
    container = document.getElementById(formId);
  }
  if (!container) return;

  // Toggle: se já aberto, fechar
  var wasOpen = container.classList.contains('open');
  if (wasOpen) {
    container.classList.remove('open');
    return;
  }

  var estagioIdJs = est && est.id !== null && est.id !== undefined ? est.id : 'null';
  var html =
    '<input type="text" id="' +
    formId +
    '-nome" placeholder="Nome do estágio (ex: Floração, Poda, Adubação...)" value="' +
    gcEsc(est ? est.nome || '' : '') +
    '">';
  html += '<div class="gc-color-row" id="' + formId + '-cores"></div>';
  html += '<div class="gc-stage-inline-btns">';
  html +=
    '<button class="gc-si-cancel" onclick="this.closest(\'.gc-stage-inline\').classList.remove(\'open\')">Cancelar</button>';
  html +=
    '<button class="gc-si-save" onclick="gcSaveStageInline(\'' +
    formId +
    "','" +
    culturaId +
    "','" +
    registroId +
    "'," +
    estagioIdJs +
    ')"><i class="bi bi-check-lg"></i> Salvar</button>';
  html += '</div>';
  container.innerHTML = html;
  container.classList.add('open');

  // Cores
  var colorRow = document.getElementById(formId + '-cores');
  STAGE_COLORS.forEach(function (c) {
    var d = document.createElement('div');
    d.className = 'gc-color-opt' + (est && est.cor === c ? ' active' : '');
    d.style.background = c;
    d.dataset.color = c;
    d.onclick = function () {
      colorRow.querySelectorAll('.gc-color-opt').forEach(function (el) {
        el.classList.remove('active');
      });
      d.classList.add('active');
    };
    colorRow.appendChild(d);
  });
  if (!est) {
    var first = colorRow.querySelector('.gc-color-opt');
    if (first) first.classList.add('active');
  }

  var nomeInput = document.getElementById(formId + '-nome');
  setTimeout(function () {
    nomeInput.focus();
  }, 100);
};

window.gcSaveStageInline = function (formId, culturaId, registroId, estagioId) {
  var nomeInput = document.getElementById(formId + '-nome');
  var nome = nomeInput ? nomeInput.value.trim() : '';
  if (!nome) {
    if (nomeInput) nomeInput.focus();
    return;
  }

  var activeColor = document.querySelector('#' + formId + '-cores .gc-color-opt.active');
  var cor = activeColor ? activeColor.dataset.color : '#6366f1';
  var ests = gcStageState(registroId);
  var payload;

  // Corrigir: estagioId pode vir como string 'null' do onclick
  var isEditing = estagioId !== null && estagioId !== 'null' && estagioId !== undefined;

  if (isEditing) {
    var est = ests.find(function (e) {
      return e.id === estagioId;
    });
    if (!est) return;
    payload = {
      id: estagioId,
      registro: est.registro || registroId,
      nome: nome,
      cor: cor,
      icone: est.icone || 'bi-circle-fill',
      ordem: est.ordem || 0,
      tipo: 'estagio',
      concluido: est.concluido || false,
    };
  } else {
    var maxOrdem = ests.reduce(function (m, e) {
      return Math.max(m, e.ordem || 0);
    }, -1);
    payload = {
      registro: registroId,
      nome: nome,
      cor: cor,
      icone: 'bi-circle-fill',
      ordem: maxOrdem + 1,
      tipo: 'estagio',
      concluido: false,
    };
  }

  gcSaveStageApi(payload).then(function (saved) {
    if (!saved) return;
    var ests2 = gcStageState(registroId);
    var targetIdx = null;
    if (isEditing) {
      var idx = ests2.findIndex(function (e) {
        return e.id === estagioId;
      });
      if (idx >= 0) {
        saved.tarefas = ests2[idx].tarefas || saved.tarefas || [];
        saved.sub_estagios = ests2[idx].sub_estagios || [];
        ests2[idx] = saved;
        targetIdx = idx;
      }
    } else {
      saved.tarefas = saved.tarefas || [];
      saved.sub_estagios = saved.sub_estagios || [];
      ests2.push(saved);
      targetIdx = ests2.length - 1;
    }
    if (targetIdx !== null && targetIdx >= 0) {
      window._gcActiveStageByCulture[culturaId] = targetIdx;
    }
    gcRefreshPhases(registroId, culturaId);
    if (typeof showToast === 'function')
      showToast('success', isEditing ? 'Estágio atualizado' : 'Estágio criado');
  });
};

// ── Editar tarefa inline (pré-preenchido) ──
window.gcToggleInlineTaskEdit = function (culturaId, registroId, estagioId, tarefaId) {
  var formId = 'gc-task-edit-' + tarefaId + '-' + culturaId;
  var el = document.getElementById(formId);
  if (!el) return;
  var wasOpen = el.classList.contains('open');
  document.querySelectorAll('.gc-task-inline.open').forEach(function (f) {
    f.classList.remove('open');
  });
  document.querySelectorAll('.gc-stage-inline.open').forEach(function (f) {
    f.classList.remove('open');
  });
  if (wasOpen) return;

  var tarefa = null;
  gcStageState(registroId).forEach(function (est) {
    if (!tarefa && est.tarefas) {
      tarefa = est.tarefas.find(function (t2) {
        return t2.id === tarefaId;
      });
    }
  });
  if (!tarefa) return;

  var html =
    '<textarea id="' +
    formId +
    '-desc" rows="2" placeholder="Descreva a tarefa...">' +
    gcEsc(tarefa.descricao || '') +
    '</textarea>';
  html += '<div class="gc-task-inline-attrs">';
  html += '<select id="' + formId + '-func"><option value="">Funcionário</option></select>';
  html +=
    '<select id="' +
    formId +
    '-cargo"><option value="">Cargo</option><option value="GERENTE">Gerente</option><option value="TRATORISTA">Tratorista</option><option value="VAQUEIRO">Vaqueiro</option><option value="ADMIN">Administrativo</option><option value="SERVICO">Serviços Gerais</option><option value="TECNICO">Técnico Agrícola</option><option value="ENGENHEIRO">Eng. Agrônomo</option><option value="OUTRO">Outro</option></select>';
  html +=
    '<input id="' +
    formId +
    '-setor" placeholder="Setor" value="' +
    gcEsc(tarefa.setor || '') +
    '">';
  html += '</div>';
  html += '<div class="gc-task-inline-btns">';
  html +=
    '<button class="gc-ti-cancel" onclick="this.closest(\'.gc-task-inline\').classList.remove(\'open\')">Cancelar</button>';
  html +=
    '<button class="gc-ti-save" onclick="gcSaveInlineTaskEdit(\'' +
    formId +
    "','" +
    registroId +
    "',null," +
    (typeof tarefaId === 'string' ? "'" + tarefaId + "'" : tarefaId) +
    ",'" +
    culturaId +
    '\')"><i class="bi bi-check-lg"></i> Salvar</button>';
  html += '</div>';
  el.innerHTML = html;
  el.classList.add('open');

  var cargoSel = document.getElementById(formId + '-cargo');
  if (tarefa.cargo_alvo) cargoSel.value = tarefa.cargo_alvo;
  gcGetFuncionarios().then(function (funcs) {
    var sel = document.getElementById(formId + '-func');
    if (!sel) return;
    sel.innerHTML = '<option value="">Funcionário</option>';
    funcs.forEach(function (fn) {
      sel.innerHTML +=
        '<option value="' +
        fn.id +
        '">' +
        gcEsc(fn.nome) +
        (fn.cargo ? ' (' + gcEsc(fn.cargo) + ')' : '') +
        '</option>';
    });
    if (tarefa.funcionario) sel.value = tarefa.funcionario;
  });
  var descEl = document.getElementById(formId + '-desc');
  setTimeout(function () {
    if (descEl) descEl.focus();
  }, 100);
};

window.gcSaveInlineTaskEdit = function (formId, registroId, estagioId, tarefaId, culturaId) {
  var descEl = document.getElementById(formId + '-desc');
  var texto = descEl ? descEl.value.trim() : '';
  if (!texto) {
    if (descEl) descEl.focus();
    return;
  }

  var tarefa = null;
  var tarefaEstagioId = null;
  gcStageState(registroId).forEach(function (est) {
    if (!tarefa && est.tarefas) {
      tarefa = est.tarefas.find(function (t2) {
        return t2.id === tarefaId;
      });
      if (tarefa) tarefaEstagioId = est.id;
    }
  });
  if (!tarefa) return;

  // Usar o estagioId da tarefa encontrada, não o parâmetro (que pode ser 'null')
  var realEstagioId = tarefa.estagio || tarefaEstagioId;

  var payload = {
    id: tarefaId,
    estagio: realEstagioId,
    descricao: texto,
    concluida: tarefa.concluida || false,
    ordem: tarefa.ordem || 0,
  };
  var funcSel = document.getElementById(formId + '-func');
  if (funcSel && funcSel.value) payload.funcionario = parseInt(funcSel.value);
  var cargoSel = document.getElementById(formId + '-cargo');
  if (cargoSel && cargoSel.value) payload.cargo_alvo = cargoSel.value;
  var setorInput = document.getElementById(formId + '-setor');
  if (setorInput && setorInput.value.trim()) payload.setor = setorInput.value.trim();

  gcSaveTaskApi(payload).then(function (saved) {
    if (!saved) return;
    gcStageState(registroId).forEach(function (est) {
      if (est.tarefas) {
        var idx = est.tarefas.findIndex(function (t2) {
          return t2.id === tarefaId;
        });
        if (idx >= 0) est.tarefas[idx] = saved;
      }
    });
    gcRefreshPhases(registroId, culturaId);
    if (typeof showToast === 'function') showToast('success', 'Tarefa atualizada');
  });
};

// ══════════════════════════════════════════════════════════
//  DRAG & DROP (estágios + tarefas)
// ══════════════════════════════════════════════════════════

var _gcDrag = null;

function gcReorderStagesApi(orders) {
  return fetch('/api/estagios-cultura/reorder/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
    body: JSON.stringify({ orders: orders }),
  })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .catch(function () {
      return null;
    });
}

function gcReorderTasksApi(orders) {
  return fetch('/api/tarefas-estagio/reorder/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': guideCsrf() },
    body: JSON.stringify({ orders: orders }),
  })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .catch(function () {
      return null;
    });
}

window.gcSetupDnD = function (culturaId, registroId) {
  var container = document.getElementById('gc-phases-' + culturaId);
  if (!container || container.dataset.dndBound === '1') return;
  container.dataset.dndBound = '1';

  function clearIndicators() {
    container
      .querySelectorAll('.gc-drop-above,.gc-drop-below,.gc-drop-before,.gc-drop-after')
      .forEach(function (el) {
        el.classList.remove('gc-drop-above', 'gc-drop-below', 'gc-drop-before', 'gc-drop-after');
      });
  }

  container.addEventListener('dragstart', function (e) {
    var handle = e.target.closest ? e.target.closest('.gc-drag-handle') : null;
    if (!handle) {
      e.preventDefault();
      return;
    }
    var stageEl = e.target.closest('.gc-stage-tab[data-draggable="true"]');
    var taskEl = e.target.closest('.gc-task-item[data-draggable="true"]');
    if (stageEl) {
      _gcDrag = {
        type: 'stage',
        el: stageEl,
        idx: parseInt(stageEl.dataset.idx),
        registroId: registroId,
        culturaId: culturaId,
        dropTarget: null,
        dropBefore: false,
      };
      stageEl.classList.add('gc-dragging');
    } else if (taskEl) {
      _gcDrag = {
        type: 'task',
        el: taskEl,
        estagioIdx: parseInt(taskEl.dataset.estagioIdx),
        tidx: parseInt(taskEl.dataset.tidx),
        registroId: registroId,
        culturaId: culturaId,
        dropTarget: null,
        dropAbove: false,
      };
      taskEl.classList.add('gc-dragging');
    } else {
      e.preventDefault();
      return;
    }
    document.body.classList.add('gc-grabbing');
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      try {
        e.dataTransfer.setData('text/plain', 'gc-dnd');
      } catch (err) {}
    }
  });

  container.addEventListener('dragover', function (e) {
    if (!_gcDrag) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
    clearIndicators();
    var target = null;
    if (_gcDrag.type === 'stage') {
      target = e.target.closest('.gc-stage-tab[data-draggable="true"]');
    } else {
      target = e.target.closest('.gc-task-item[data-draggable="true"]');
      if (target && parseInt(target.dataset.estagioIdx) !== _gcDrag.estagioIdx) target = null;
    }
    if (target && target !== _gcDrag.el) {
      var rect = target.getBoundingClientRect();
      if (_gcDrag.type === 'stage') {
        var before = e.clientX - rect.left < rect.width / 2;
        target.classList.add(before ? 'gc-drop-before' : 'gc-drop-after');
        _gcDrag.dropBefore = before;
      } else {
        var above = e.clientY - rect.top < rect.height / 2;
        target.classList.add(above ? 'gc-drop-above' : 'gc-drop-below');
        _gcDrag.dropAbove = above;
      }
      _gcDrag.dropTarget = target;
    } else {
      _gcDrag.dropTarget = null;
    }
  });

  container.addEventListener('drop', function (e) {
    if (!_gcDrag) return;
    e.preventDefault();
    var d = _gcDrag;
    _gcDrag = null;
    document.body.classList.remove('gc-grabbing');
    clearIndicators();
    d.el.classList.remove('gc-dragging');
    if (!d.dropTarget) return;

    var target = d.dropTarget;
    var above = d.dropAbove;

    if (d.type === 'stage') {
      var fromIdx = d.idx;
      var toIdx = parseInt(target.dataset.idx);
      if (fromIdx === toIdx) return;
      var ests = gcStageState(d.registroId);
      var moved = ests.splice(fromIdx, 1)[0];
      var targetNew = toIdx > fromIdx ? toIdx - 1 : toIdx;
      var insertAt = d.dropBefore ? targetNew : targetNew + 1;
      ests.splice(insertAt, 0, moved);
      var orders = [];
      ests.forEach(function (e2, i) {
        if (e2.id) {
          e2.ordem = i;
          orders.push({ id: e2.id, ordem: i });
        }
      });
      gcReorderStagesApi(orders);
      window._gcActiveStageByCulture[d.culturaId] = insertAt;
      gcRefreshPhases(d.registroId, d.culturaId);
    } else {
      var ests2 = gcStageState(d.registroId);
      var est = ests2[d.estagioIdx];
      if (!est || !est.tarefas) return;
      var fromT = d.tidx;
      var toT = parseInt(target.dataset.tidx);
      if (fromT === toT) return;
      var movedT = est.tarefas.splice(fromT, 1)[0];
      var targetNew2 = toT > fromT ? toT - 1 : toT;
      var insertAt2 = above ? targetNew2 : targetNew2 + 1;
      est.tarefas.splice(insertAt2, 0, movedT);
      var orders2 = [];
      est.tarefas.forEach(function (t, i) {
        if (t.id) {
          t.ordem = i;
          orders2.push({ id: t.id, ordem: i });
        }
      });
      gcReorderTasksApi(orders2);
      gcRefreshPhases(d.registroId, d.culturaId);
    }
  });

  container.addEventListener('dragend', function () {
    if (_gcDrag && _gcDrag.el) _gcDrag.el.classList.remove('gc-dragging');
    _gcDrag = null;
    document.body.classList.remove('gc-grabbing');
    clearIndicators();
  });
};

// O ficheiro pode ser EXECUTADO VARIAS VEZES na mesma pagina.
//
// MEDIDO 2026-10-06: a SPA carrega `guide.js` DUAS vezes por navegacao —
// uma pelo bloco `<!--PARTIAL:SCRIPTS-->` e outra pelos `contentScripts`
// (o `<script data-spa-guide>`, que esta dentro do `{% block content %}`).
// Cada execucao recria TODOS os listeners de `document`, e cria um botao
// novo em cada um dos 456 cards.
//
// A guarda abaixo NAO impede a segunda execucao de `decorateGuideCards` —
// e nao deve: o `innerHTML` do SPA substitui os cards, e os novos precisam de
// ser decorados. O que ela impede e' a segunda ronda de `addEventListener`
// em `document`, que era o que multiplicava os handlers a cada navegacao
// sem que nenhum deles se tornasse inacessivel.
var _guideReady = (function () {
  var jaRodou = false;
  return function () {
    if (jaRodou) return;
    jaRodou = true;
    initGuideReady();
  };
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _guideReady);
} else {
  _guideReady();
}
// Hibrido SPA: abre painel se URL ja é /guias/<guia>/<id> (reload/bookmark) e trata back/forward
//
// MEDIDO 2026-10-07: estas duas rotinas (esta e a de baixo, no fim do
// ficheiro) so reconheciam `/guias/vegetal/(\d+)`. Animal, aquatica e
// sistemas abriam o painel por JS, mas recarregar o URL nao reabria nada, e o
// `popstate` passava `'vegetal'` fixo a `showCulturaDetail` — o painel da
// Angus abria com os campos de vegetal.
//
// Passam a ler o guia do proprio URL. `/guias/<guia>/<id>/` devolve o
// prefixo, e o `groupId` e' o que vier no card; sem card, o proprio guia.
(function(){
  function guiaDoUrl(){
    var m = location.pathname.match(/^\/guias\/([a-z]+)\/(\d+)\/?$/);
    if(!m) return null;
    return { guia: m[1], id: m[2] };
  }
  function abrirDoUrl(){
    var alvo = guiaDoUrl();
    if(!alvo) return;
    var card = document.querySelector('.cultura-card[data-cultura-id="'+alvo.id+'"]');
    var nome = card ? card.getAttribute('data-cultura-nome') : alvo.id;
    var grupo = (card && card.getAttribute('data-grupo')) || alvo.guia;
    if(typeof window.safeShowCulturaDetail === 'function'){
      safeShowCulturaDetail(alvo.id, nome, grupo);
    } else if(typeof window.showCulturaDetail === 'function'){
      showCulturaDetail(alvo.id, nome, grupo);
    }
  }
  window.addEventListener('popstate', function(){
    if(guiaDoUrl()){
      abrirDoUrl();
    } else if(/^\/guias\/[a-z]+\/?$/.test(location.pathname)){
      closeCulturaDetail();
    }
  });
  // tenta abrir após DOM pronto (com delay para garantir que guide.js e cards carregaram)
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(abrirDoUrl, 400); });
  } else {
    setTimeout(abrirDoUrl, 400);
  }
})();
