/* Ampliagro Cinema — motor da intro (v5).
   SCROLL VIRTUAL: a pagina nao rola (body overflow:hidden). Wheel, toque,
   teclado e auto-scroll acumulam `pos` (px); p=pos/TRACK pilota as fases.
   Sem scroll nativo nao ha vazio — a viewport e o mundo inteiro. */
(function () {
  'use strict';
  var cine = document.getElementById('cine');
  if (!cine) return;
  var bar = document.getElementById('cineBar'),
    pct = document.getElementById('cinePct');
  var autoBtn = document.getElementById('cineAuto'),
    replay = document.getElementById('cineReplay');
  var finale = document.getElementById('final');
  if (finale) finale.tabIndex = -1;
  var panes = Array.prototype.slice.call(cine.querySelectorAll('.pane'));
  var cut = cine.querySelector('.cut'),
    flash = cine.querySelector('.flash'),
    brand = cine.querySelector('.brandphase'),
    hint = cine.querySelector('.hint');
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var P_B = 0.1,
    P_C = 0.35,
    P_D = 0.65,
    P_E = 0.88;
  var FIN0 = 0.9,
    FIN1 = 0.99;
  var FIN_SCROLL = 0.65;
  var TRACK = 3000; // comprimento total do scroll virtual (px)
  function clamp01(x) {
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }
  function clampPos(x) {
    return x < 0 ? 0 : x > TRACK ? TRACK : x;
  }
  function smooth(x) {
    x = clamp01(x);
    return x * x * (3 - 2 * x);
  }
  var pos = 0,
    p = 0;
  function geom(p) {
    var b = smooth((p - P_B) / (P_C - P_B));
    var gapB = 0.06 * b,
      wA = 0.5 - gapB / 2,
      w5 = 0.2;
    var l1 = wA * (1 - b) + w5 * b,
      l2 = wA * (1 - b) + w5 * b * 2,
      l3 = wA * (1 - b) + w5 * b * 3;
    var wMid = 0.001 + (w5 - 0.001) * b;
    return {
      b: b,
      campo: { l: 0, w: wA * (1 - b) + w5 * b },
      tudo: { l: l1, w: wMid },
      log: { l: l2, w: wMid },
      feito: { l: l3, w: wMid },
      coop: { w: wA * (1 - b) + w5 * b },
      brand: smooth((p - P_D) / (P_E - P_D)) * (1 - smooth((p - 0.965) / 0.035)),
    };
  }
  function apply(p) {
    cine.style.setProperty('--p', p.toFixed(4));
    var g = geom(p);
    var map = { campo: g.campo, tudo: g.tudo, log: g.log, feito: g.feito, coop: g.coop };
    panes.forEach(function (el) {
      var k = el.getAttribute('data-k'),
        m = map[k];
      if (!m) return;
      if (k === 'coop') {
        el.style.left = 'auto';
        el.style.right = '0';
        el.style.width = (m.w * 100).toFixed(3) + '%';
      } else {
        el.style.right = 'auto';
        el.style.left = (m.l * 100).toFixed(3) + '%';
        el.style.width = (m.w * 100).toFixed(3) + '%';
      }
      var inner = el.querySelector('.in');
      var op =
        k === 'campo' || k === 'coop' ? clamp01((m.w - 0.06) / 0.1) : clamp01((m.w - 0.04) / 0.08);
      if (inner) {
        inner.style.opacity = op.toFixed(3);
        inner.style.transform = 'translateY(' + ((1 - op) * 26).toFixed(1) + 'px)';
      }
    });
    if (cut) {
      cut.style.left = (g.campo.w * 100).toFixed(3) + '%';
      cut.style.opacity = (1 - smooth((p - P_C) / (P_D - P_C))).toFixed(3);
    }
    if (flash) {
      flash.style.opacity = (clamp01(1 - Math.abs(p - 0.66) / 0.05) * 0.9).toFixed(3);
    }
    var fr = smooth((p - FIN0) / (FIN1 - FIN0));
    if (finale) {
      var fOn = fr > 0.995;
      finale.style.transform = 'translateY(' + ((1 - fr) * 100).toFixed(2) + '%)';
      finale.style.visibility = fr < 0.002 ? 'hidden' : 'visible';
      finale.style.pointerEvents = fOn ? 'auto' : 'none';
      finale.style.overflowY = fOn ? 'auto' : 'hidden';
      if (!fOn && finale.scrollTop) finale.scrollTop = 0;
      if ('inert' in HTMLElement.prototype) finale.inert = !fOn;
    }
    if (brand) {
      brand.style.opacity = (g.brand * (1 - fr)).toFixed(3);
      var h = brand.querySelector('h1');
      if (h) h.style.transform = 'scale(' + (0.92 + 0.18 * g.brand).toFixed(3) + ')';
    }
    if (hint) {
      hint.style.opacity =
        p < 0.03 || p > 0.9 ? '1' : String((1 - smooth((p - 0.03) / 0.1)).toFixed(3));
    }
    var ph = p < P_B ? 'A' : p < P_C ? 'B' : p < P_D ? 'C' : p < P_E ? 'D' : 'E';
    cine.setAttribute('data-phase', ph);
    if (bar) bar.style.width = (p * 100).toFixed(1) + '%';
    if (pct) pct.textContent = String(Math.round(p * 100)).padStart(3, '0') + '%';
    Array.prototype.forEach.call(document.querySelectorAll('.chapters button'), function (btn) {
      btn.setAttribute('aria-current', btn.getAttribute('data-goto') === ph ? 'true' : 'false');
    });
  }
  function render() {
    p = clamp01(pos / TRACK);
    apply(p);
  }

  /* Tween suave para capítulos / rever / teclado */
  var tweening = false,
    tFrom = 0,
    tTo = 0,
    tT0 = 0,
    tDur = 1;
  function tweenTo(target, dur) {
    tFrom = pos;
    tTo = clampPos(target);
    tT0 = performance.now();
    tDur = reduced || !dur ? 0 : dur;
    if (!tDur) {
      pos = tTo;
      tweening = false;
      render();
      return;
    }
    tweening = true;
  }
  function stepTween(now) {
    var k = Math.min(1, (now - tT0) / tDur),
      e = 1 - Math.pow(1 - k, 3);
    pos = tFrom + (tTo - tFrom) * e;
    render();
    if (k >= 1) tweening = false;
  }
  /* Auto-scroll lento: empurra `pos`, nao a pagina */
  var auto = !reduced,
    resumeT = null,
    last = null;
  function speed() {
    return p < 0.6 ? 30 : 18;
  }
  function loop(t) {
    if (last == null) last = t;
    var dt = Math.min(0.05, (t - last) / 1000);
    last = t;
    if (tweening) stepTween(t);
    else if (auto && !document.hidden && pos < TRACK) {
      pos += speed() * dt;
      render();
    }
    requestAnimationFrame(loop);
  }
  function syncBtn() {
    if (autoBtn) {
      autoBtn.innerHTML = auto
        ? '<i class="bi bi-pause-fill"></i> Pausar'
        : '<i class="bi bi-play-fill"></i> Auto-scroll';
    }
  }
  function pauseAuto() {
    tweening = false;
    if (auto) {
      auto = false;
      syncBtn();
    }
    clearTimeout(resumeT);
    resumeT = setTimeout(function () {
      auto = !reduced;
      syncBtn();
    }, 6000);
  }
  /* Handoff: no fim da cena o finale rola por dentro (scroll nativo dele) */
  function finaleCanScroll(dy) {
    if (p < FIN_SCROLL || !finale) return false;
    var st = finale.scrollTop,
      ch = finale.clientHeight,
      sh = finale.scrollHeight;
    if (dy > 0) return st + ch < sh - 1;
    return st > 1;
  }
  window.addEventListener(
    'wheel',
    function (e) {
      var d = e.deltaY;
      if (e.deltaMode === 1) d *= 16;
      else if (e.deltaMode === 2) d *= window.innerHeight || 800;
      /* Handoff: no fim da cena o wheel rola o CONTEUDO do finale,
       em qualquer posicao do cursor (o rail fica por cima do overlay). */
      if (finaleCanScroll(d)) {
        e.preventDefault();
        finale.scrollTop += d;
        pauseAuto();
        return;
      }
      if ((pos >= TRACK && d > 0) || (pos <= 0 && d < 0)) return;
      pos = clampPos(pos + d);
      render();
      pauseAuto();
    },
    { passive: false }
  );
  var tY = null;
  window.addEventListener(
    'touchstart',
    function (e) {
      tY = e.touches[0].clientY;
      pauseAuto();
    },
    { passive: true }
  );
  window.addEventListener(
    'touchmove',
    function (e) {
      if (tY == null) return;
      var y = e.touches[0].clientY,
        d = (tY - y) * 1.2;
      tY = y;
      if (finaleCanScroll(d)) return;
      if ((pos >= TRACK && d > 0) || (pos <= 0 && d < 0)) return;
      pos = clampPos(pos + d);
      render();
    },
    { passive: true }
  );
  window.addEventListener(
    'touchend',
    function () {
      tY = null;
    },
    { passive: true }
  );
  window.addEventListener(
    'touchcancel',
    function () {
      tY = null;
    },
    { passive: true }
  );
  window.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    var k = e.key;
    var ae = document.activeElement;
    var onCtl =
      ae &&
      (ae.tagName === 'BUTTON' ||
        ae.tagName === 'A' ||
        ae.tagName === 'INPUT' ||
        ae.tagName === 'TEXTAREA');
    if (onCtl && (k === ' ' || k === 'Spacebar' || k === 'Enter')) return;
    if (
      finale &&
      ae === finale &&
      (k === 'ArrowDown' ||
        k === 'ArrowUp' ||
        k === 'PageDown' ||
        k === 'PageUp' ||
        k === ' ' ||
        k === 'Spacebar')
    )
      return;
    if (k === 'Home') {
      pauseAuto();
      tweenTo(0, 900);
      return;
    }
    if (k === 'End') {
      pauseAuto();
      tweenTo(TRACK, 1400);
      return;
    }
    var step = 0;
    if (k === 'ArrowDown' || k === 'PageDown' || k === ' ' || k === 'Spacebar') step = 0.035;
    else if (k === 'ArrowUp' || k === 'PageUp') step = -0.035;
    else return;
    if (k === 'PageDown' || k === 'PageUp') step *= 3;
    e.preventDefault();
    pauseAuto();
    tweenTo(pos + step * TRACK, 520);
  });
  if (autoBtn)
    autoBtn.addEventListener('click', function () {
      auto = !auto;
      clearTimeout(resumeT);
      last = null;
      syncBtn();
    });
  if (replay)
    replay.addEventListener('click', function () {
      pauseAuto();
      tweenTo(0, 1100);
      auto = !reduced;
      syncBtn();
      if (finale) finale.scrollTop = 0;
    });
  Array.prototype.forEach.call(document.querySelectorAll('.chapters button'), function (btn) {
    btn.addEventListener('click', function () {
      var g = btn.getAttribute('data-goto');
      var target = { A: 0.02, B: 0.24, C: 0.45, D: 0.7, E: 0.96 }[g] || 0;
      pauseAuto();
      tweenTo(target * TRACK, 1400);
    });
  });
  var skip = document.querySelector('.skip');
  if (skip)
    skip.addEventListener('click', function (e) {
      e.preventDefault();
      pauseAuto();
      tweenTo(TRACK, 1600);
      if (finale)
        setTimeout(function () {
          try {
            finale.focus({ preventScroll: true });
          } catch (err) {
            finale.focus();
          }
        }, 1700);
    });
  window.addEventListener('resize', render);
  render();
  syncBtn();
  requestAnimationFrame(loop);
  // Carousel auto-scroll init
  var fcarousel = document.querySelector('.fcarousel');
  if (fcarousel) {
    fcarousel.classList.add('auto');
    fcarousel.querySelector('.fitems').addEventListener('mouseover', function () {
      fcarousel.classList.remove('auto');
    });
    fcarousel.querySelector('.fitems').addEventListener('mouseout', function () {
      fcarousel.classList.add('auto');
    });
    fcarousel.querySelector('.fcprev').addEventListener('click', function () {
      fcarousel.classList.remove('auto');
      pauseAuto();
    });
    fcarousel.querySelector('.fcnext').addEventListener('click', function () {
      fcarousel.classList.remove('auto');
      pauseAuto();
    });
  }
})();
