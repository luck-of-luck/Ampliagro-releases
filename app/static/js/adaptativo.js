/**
 * Adaptacoes por modo — substitui IMPLEMENTACOES, nao layout.
 *
 * Este arquivo e o exemplo de referencia de como usar Amplia.dispositivo.
 * A regra da casa:
 *
 *   - LAYOUT (quebra, coluna, reflow) continua em media query no CSS.
 *     Media query e o que reage a largura de verdade.
 *   - COMPORTAMENTO (qual funcao roda, o que aparece, o que some) e decidido
 *     aqui, por CAPACIDADE do aparelho — e nao por marca nem por userAgent.
 *
 * Ou seja: nao trocamos "300px" por "detectei celular". Trocamos
 * "como os cartoes de tema se organizam" por "o aparelho tem dedo ou rato".
 *
 * ---------------------------------------------------------------------------
 *  COMO ADICIONAR UMA NOVA
 * ---------------------------------------------------------------------------
 *
 *  1. provedores que mudam por modo (dados e helpers):
 *       Amplia.adaptar('meu-recurso', {
 *         telefone: function (ctx, dados) { ... },
 *         desktop:  function (ctx, dados) { ... },
 *         reativo:  true,   // reexecuta se o modo mudar (ex.: redimensionou)
 *       });
 *
 *  2. quem chama:
 *       Amplia.aplicar('meu-recurso', dados);
 *
 *  Sem `reativo`, o recurso roda uma vez e fica. Com, ele reexecuta sozinho
 *  quando o modo muda — util quando a janela do desktop encolhe para o tamanho
 *  de um celular, ou quando o usuario gira o tablet.
 */
(function (global) {
  'use strict';

  var Amplia = (global.Amplia = global.Amplia || {});
  var D = Amplia.dispositivo;
  if (!D) {
    if (global.console && console.warn) {
      console.warn('[adaptativo] dispositivo.js nao carregou; adaptacoes desativadas.');
    }
    return;
  }

  /** Atalhos de uso no dia a dia. */
  Amplia.adaptar = function (nome, impl) {
    return D.registrar(nome, impl);
  };
  Amplia.aplicar = function (nome, dados) {
    return D.aplicar(nome, dados);
  };

  /**
   * Reaplica quando o conteudo do alvo e RECONSTRUIDO.
   *
   * Isso e necessario aqui: o theme-presets.js refaz os .nav-mode-card do zero
   * toda vez que o painel de modos e montado. Como o adaptativo.js e defer e
   * roda antes, o estilo que aplicamos no card e apagado em seguida — sem isso
   * a adaptacao pegava so no container, nao nos cards (foi exatamente o que a
   * medicao mostrou: painel virava flex, mas minWidth dos cards ficava vazia).
   */
  function reaplicarQuandoMudar(alvo, fn) {
    if (!alvo || typeof MutationObserver !== 'function') return;
    if (alvo.__observadoAmbiente) return;
    alvo.__observadoAmbiente = true;
    var agendado = false;
    var obs = new MutationObserver(function () {
      if (agendado) return;
      agendado = true;
      // um rAF junta as varias mutacoes do theme-presets num unico trabalho
      requestAnimationFrame(function () {
        agendado = false;
        fn();
      });
    });
    obs.observe(alvo, { childList: true, subtree: true });
  }

  // =========================================================================
  //  1) PAINEL DE MODOS (tema)
  //  Problema: #mode-panel-grid tem style INLINE com repeat(3, 1fr). Tres
  //  cartoes lado a lado numa viewport de 390px dao ~120px cada: o preview
  //  fica inutilizavel e o alvo fica pequeno demais para o dedo.
  //
  //  No desktop mantemos a grade de 3 colunas. No telefone, vira uma fileira
  //  horizontal com scroll-snap: um cartao por vez, do tamanho do alvo, e o
  //  resto aparece arrastando. Nenhum dos dois Precisa de media query, porque
  //  a decisao e "tem dedo?", nao "quantos pixels".
  // =========================================================================
  D.registrar('painel-modos', {
    telefone: function (ctx) {
      var painel = document.getElementById('mode-panel-grid');
      if (!painel) return;
      painel.style.gridTemplateColumns = 'none';
      painel.style.display = 'flex';
      painel.style.gap = '10px';
      painel.style.overflowX = 'auto';
      painel.style.scrollSnapType = 'x mandatory';
      painel.style.scrollbarWidth = 'none';
      painel.style.webkitOverflowScrolling = 'touch';
      painel.style.padding = '2px'; // evita cortar o anel de foco no snap
      // o preview decorativo come a altura e nao ajuda a escolher tema no dedao
      painel.dataset.compacto = 'sim';
      var cartoes = painel.querySelectorAll('.nav-mode-card');
      for (var i = 0; i < cartoes.length; i++) {
        cartoes[i].style.minWidth = '72%';
        cartoes[i].style.scrollSnapAlign = 'center';
        cartoes[i].style.minHeight = '48px';
      }
    },

    desktop: function (ctx) {
      var painel = document.getElementById('mode-panel-grid');
      if (!painel) return;
      // devolve exatamente o que o template trae, sem deixar residuo do telefone
      painel.style.gridTemplateColumns = 'repeat(3, 1fr)';
      painel.style.display = 'grid';
      painel.style.gap = '8px';
      painel.style.overflowX = '';
      painel.style.scrollSnapType = '';
      painel.style.scrollbarWidth = '';
      painel.style.webkitOverflowScrolling = '';
      painel.style.padding = '';
      delete painel.dataset.compacto;
      var cartoes = painel.querySelectorAll('.nav-mode-card');
      for (var i = 0; i < cartoes.length; i++) {
        cartoes[i].style.minWidth = '';
        cartoes[i].style.scrollSnapAlign = '';
        cartoes[i].style.minHeight = '';
      }
    },

    // o painel abre e fecha; reativo cobre a troca de modo e o resize
    reativo: true,
  });

  // o theme-presets.js reconstroi os cards; reaplicamos quando isso acontecer
  reaplicarQuandoMudar(document.getElementById('mode-panel-grid'), function () {
    D.aplicar('painel-modos');
  });

  // =========================================================================
  //  2) ATALHOS DE TECLADO
  //  "Ctrl+K", "Ctrl+/" e afins nao existem no teclado do celular. O
  //  atalho aparece na dica da paleta de busca e nao serve para nada la.
  //  Em vez de esconder por media query, escondemos por CAPACIDADE: um
  //  teclado fisico em modo toque ainda tem Ctrl, e ai a dica e util.
  // =========================================================================
  D.registrar('atalhos-teclado', {
    telefone: function (ctx) {
      document.documentElement.dataset.atalhos = 'sem';
      // remove a dica "<kbd>Ctrl</kbd>+" das opcoes da paleta
      var marcas = document.querySelectorAll('[data-atalho], .search-menu-item kbd');
      for (var i = 0; i < marcas.length; i++) marcas[i].style.display = 'none';
    },
    desktop: function (ctx) {
      document.documentElement.dataset.atalhos = 'com';
      var marcas = document.querySelectorAll('[data-atalho], .search-menu-item kbd');
      for (var i = 0; i < marcas.length; i++) marcas[i].style.display = '';
    },
    reativo: true,
  });

  // Aplica o que ja pode ser aplicado no carregamento. O resto entra por
  // reativo, ou no primeiro registrar() que ja roda na hora.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      D.aplicar('painel-modos');
      D.aplicar('atalhos-teclado');
    });
  } else {
    D.aplicar('painel-modos');
    D.aplicar('atalhos-teclado');
  }
})(window);
