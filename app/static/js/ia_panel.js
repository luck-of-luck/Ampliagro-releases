/* AMPLIAGRO — Painel lateral da IA (estilo Copilot).
   Um só cérebro: o chat do dock (#ia-chat). O painel apenas
   abre/fecha e encaminha o texto para o pipeline do dock. */
(function () {
  'use strict';

  window.IAPanel = window.IAPanel || {};

  function panel() {
    return document.getElementById('ia-panel');
  }
  function overlay() {
    return document.getElementById('ia-panel-overlay');
  }

  window.toggleIAPanel = function (force) {
    var p = panel();
    if (!p) {
      /* Sem painel nesta página: abre o dock direto */
      if (typeof window.iaDockToggle === 'function') window.iaDockToggle();
      return;
    }
    var open =
      typeof force === 'boolean' ? force : !p.classList.contains('open');
    p.classList.toggle('open', open);
    var o = overlay();
    if (o) o.classList.toggle('open', open);
    if (open) {
      var inp = document.getElementById('ia-input');
      if (inp && inp.focus) setTimeout(function () { inp.focus(); }, 60);
    }
  };

  window.sendIAMessage = function () {
    var inp = document.getElementById('ia-input');
    var txt = inp ? inp.value.trim() : '';
    if (!txt) return;
    if (inp) inp.value = '';
    /* Encaminha para o chat do dock (único pipeline da IA) */
    var dockInp = document.getElementById('ia-dock-input');
    if (dockInp) dockInp.value = txt;
    var chat = document.getElementById('ia-chat');
    if (chat && !chat.classList.contains('open') && typeof window.iaDockToggle === 'function') {
      window.iaDockToggle();
    }
    if (typeof window.iaDockSend === 'function') window.iaDockSend();
    else if (dockInp) dockInp.value = txt;
    window.toggleIAPanel(false);
  };

  IAPanel.init = function () {};
  document.addEventListener('DOMContentLoaded', IAPanel.init);
})();
