/* ════════════════════════════════════════════════════════════
   AMPLIAGRO — Liquid Glass (vanilla)
   Gera SVG displacement + aplica no fundo do .matrix-container
   Port do React generateGlassSvg (liquid-glass/dist/script.js)
   Sem dependências. Respeita tema, resize e SPA.
   ════════════════════════════════════════════════════ */
(function(){
  'use strict';
  if (window.__liquidGlassInit) return;
  window.__liquidGlassInit = true;

  var FILTER_ID_BASE = 'liquidGlassFilter';
  var uid = 0;
  function nextId(){ uid+=1; return FILTER_ID_BASE + '-' + uid + '-' + Date.now().toString(36); }

  function generateGlassSvg(width, height, margin, borderRadius){
    width = Math.max(1, Math.round(width));
    height = Math.max(1, Math.round(height));
    margin = margin == null ? 5 : margin;
    borderRadius = borderRadius == null ? 20 : borderRadius;
    var w = Math.max(1, width - 2*margin);
    var h = Math.max(1, height - 2*margin);
    var r = Math.min(borderRadius, w/2, h/2);
    var x = margin, y = margin;
    var path = [
      'M'+(x+r)+','+y,
      'h'+(w-2*r),
      'a'+r+','+r+' 0 0 1 '+r+','+r,
      'v'+(h-2*r),
      'a'+r+','+r+' 0 0 1 -'+r+','+r,
      'h-'+(w-2*r),
      'a'+r+','+r+' 0 0 1 -'+r+',-'+r,
      'v-'+(h-2*r),
      'a'+r+','+r+' 0 0 1 '+r+',-'+r,
      'z'
    ].join(' ');
    // mesmo shape do dist/script.js, mas inline string já encodada no feImage
    var svgString = "<?xml version='1.0' encoding='UTF-8'?><svg width='"+width+"' height='"+height+"' xmlns='http://www.w3.org/2000/svg' version='1.1' xmlns:xlink='http://www.w3.org/1999/xlink' viewBox='0 0 "+width+" "+height+"'><filter id='blur'><feGaussianBlur stdDeviation='5' /></filter><linearGradient id='xGradient' x1='0%' y1='0%' x2='100%' y2='0%'><stop offset='0%' stop-color='red' stop-opacity='1'></stop><stop offset='100%' stop-color='red' stop-opacity='0'></stop></linearGradient><linearGradient id='yGradient' x1='0%' y1='0%' x2='0%' y2='100%'><stop offset='0%' stop-color='blue' stop-opacity='1'></stop><stop offset='100%' stop-color='blue' stop-opacity='0'></stop></linearGradient><rect id='BG' x='0' y='0' width='"+width+"' height='"+height+"' fill='#000'></rect><rect id='RED_CHANNEL' x='0' y='0' width='"+width+"' height='"+height+"' fill='url(#xGradient)'></rect><rect id='BLUE_CHANNEL' x='0' y='0' width='"+width+"' height='"+height+"' fill='url(#yGradient)' style='mix-blend-mode:screen'></rect><path id='GRAY_AREA' d='"+path+"' fill='rgba(153,153,153,1)' filter='url(#blur)'></path></svg>";
    return 'data:image/svg+xml,' + encodeURIComponent(svgString);
  }

  function ensureStructure(container, filterId){
    // defs SVG
    var existingSvg = container.querySelector('.lg-svg-defs');
    if (existingSvg) existingSvg.remove();
    var svgNS = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class','lg-svg-defs');
    svg.setAttribute('aria-hidden','true');
    svg.style.position='absolute'; svg.style.width='0'; svg.style.height='0';
    // defs
    var defs = document.createElementNS(svgNS,'defs');
    var filter = document.createElementNS(svgNS,'filter');
    filter.setAttribute('id', filterId);
    filter.setAttribute('primitiveUnits','objectBoundingBox');
    filter.setAttribute('x','0'); filter.setAttribute('y','0');
    filter.setAttribute('width','1'); filter.setAttribute('height','1');
    filter.setAttribute('color-interpolation-filters','sRGB');

    var feImage = document.createElementNS(svgNS,'feImage');
    feImage.setAttribute('href','');
    feImage.setAttribute('x','0'); feImage.setAttribute('y','0');
    feImage.setAttribute('width','1'); feImage.setAttribute('height','1');
    feImage.setAttribute('result','lg_map');
    feImage.setAttribute('preserveAspectRatio','none');

    var feBlur = document.createElementNS(svgNS,'feGaussianBlur');
    feBlur.setAttribute('in','SourceGraphic');
    feBlur.setAttribute('stdDeviation','0.012');
    feBlur.setAttribute('result','lg_blur');

    var feDisp = document.createElementNS(svgNS,'feDisplacementMap');
    feDisp.setAttribute('in','lg_blur');
    feDisp.setAttribute('in2','lg_map');
    var disp = parseFloat(getComputedStyle(container).getPropertyValue('--lg-displacement')) || 10;
    // SVG displacement scale é em 0..1 para objectBoundingBox; converte: disp px ≈ disp/1000
    feDisp.setAttribute('scale', String(disp));
    feDisp.setAttribute('xChannelSelector','R');
    feDisp.setAttribute('yChannelSelector','B');
    feDisp.setAttribute('result','lg_disp');

    filter.appendChild(feImage);
    filter.appendChild(feBlur);
    filter.appendChild(feDisp);
    defs.appendChild(filter);
    svg.appendChild(defs);
    container.prepend(svg);
    return { svg: svg, feImage: feImage, feDisp: feDisp };
  }

  function ensureDecor(container){
    if (!container.querySelector(':scope > .lg-border')){
      var b = document.createElement('div'); b.className='lg-border'; b.setAttribute('aria-hidden','true'); container.appendChild(b);
    }
    if (!container.querySelector(':scope > .lg-glow')){
      var g = document.createElement('div'); g.className='lg-glow'; g.setAttribute('aria-hidden','true'); container.appendChild(g);
    }
  }

  function apply(container){
    if (!container) return;
    if (container.dataset.lgApplied === '1') return;
    // respeita reduced-motion? ainda aplica só sem displacement
    var filterId = nextId();
    container.classList.add('liquid-glass');
    container.dataset.lgApplied = '1';
    ensureDecor(container);
    var refs = ensureStructure(container, filterId);

    function update(){
      var rect = container.getBoundingClientRect();
      var w = Math.round(rect.width) || container.offsetWidth || 1200;
      var h = Math.round(rect.height) || container.offsetHeight || 700;
      if (w < 60) w = 900; if (h < 80) h = 600;
      var cs = getComputedStyle(container);
      var r = parseFloat(cs.getPropertyValue('--lg-radius')) || 20;
      var dataUrl = generateGlassSvg(w, h, 6, r);
      // aplica no feImage href (tanto href quanto xlink:href por compat)
      try{
        refs.feImage.setAttribute('href', dataUrl);
        refs.feImage.setAttributeNS('http://www.w3.org/1999/xlink','href', dataUrl);
      }catch(e){ refs.feImage.setAttribute('href', dataUrl); }
      // atualiza scale caso var mudou
      var disp = parseFloat(cs.getPropertyValue('--lg-displacement')) || 10;
      refs.feDisp.setAttribute('scale', String(disp));
      // vincula filtro via CSS var
      container.style.setProperty('--lg-filter', 'url(#'+filterId+')');
      container.style.setProperty('--width', w+'px');
      container.style.setProperty('--height', h+'px');
    }

    update();

    // ResizeObserver + window resize fallback
    var ro;
    if ('ResizeObserver' in window){
      ro = new ResizeObserver(function(){ update(); });
      ro.observe(container);
      container._lgRO = ro;
    }
    var onResize = function(){ update(); };
    window.addEventListener('resize', onResize, {passive:true});
    container._lgOnResize = onResize;
    container._lgUpdate = update;

    // reage a troca de tema (dark) — recalcula glassColor key
    var mo = new MutationObserver(function(muts){
      for(var i=0;i<muts.length;i++){
        if (muts[i].attributeName==='class'){
          // força reflow leve (glassColor por CSS já muda, mas dispara repaint)
          container.style.setProperty('--lg-tick', String(Date.now()%1000));
          break;
        }
      }
    });
    mo.observe(document.documentElement, {attributes:true});
    container._lgMO = mo;
  }

  function initAll(){
    var nodes = document.querySelectorAll('.matrix-container');
    if (!nodes.length) return false;
    nodes.forEach(function(c){ apply(c); });
    return true;
  }

  // SPA: quando navbar troca de página, matrix-container é recriado — observa body
  function watchSPA(){
    var body = document.body;
    if (!body) return;
    var obs = new MutationObserver(function(){
      // se um novo matrix-container sem lg surgir, aplica
      var nodes = document.querySelectorAll('.matrix-container:not([data-lg-applied="1"])');
      nodes.forEach(function(c){ apply(c); });
    });
    obs.observe(body, {childList:true, subtree:true});
  }

  // API global p/ debug / toggle
  window.LiquidGlass = {
    apply: apply,
    init: initAll,
    remove: function(container){
      container = container || document.querySelector('.matrix-container.liquid-glass');
      if (!container) return;
      container.classList.remove('liquid-glass');
      container.removeAttribute('data-lg-applied');
      container.style.removeProperty('--lg-filter');
      var svg = container.querySelector('.lg-svg-defs');
      if (svg) svg.remove();
      var b = container.querySelector('.lg-border'); if(b) b.remove();
      var g = container.querySelector('.lg-glow'); if(g) g.remove();
      if (container._lgRO) try{ container._lgRO.disconnect(); }catch(e){}
      if (container._lgOnResize) try{ window.removeEventListener('resize', container._lgOnResize); }catch(e){}
      if (container._lgMO) try{ container._lgMO.disconnect(); }catch(e){}
      delete container._lgRO; delete container._lgOnResize; delete container._lgMO; delete container._lgUpdate;
    },
    update: function(){ var c=document.querySelector('.matrix-container'); if(c && c._lgUpdate) c._lgUpdate(); }
  };

  function boot(){
    if (initAll()) watchSPA();
    else setTimeout(boot, 400);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  // expose helper — força reapply ao trocar rota SPA
  window.addEventListener('spa:page-changed', function(){ setTimeout(initAll, 80); });
  document.addEventListener('soft-navigated', function(){ setTimeout(initAll, 80); });
})();
