/**
 * Menu lateral do celular.
 *
 * A navbar nao tem espaco para os .nav-pills a 390px — medido: 44 (tema) + 99
 * (marca) + 201 (direita) = 344px ja ocupam a linha, e os pills quebravam a
 * barra em duas linhas de 111px. Entao os pills sao o MESMO elemento: no
 * desktop em linha, no celular um painel dropdown abaixo da navbar (o papel e
 * definido em navbar-premium.css, no media query de 900px).
 *
 * Aqui so alterna uma classe. Nada de criar ou mover markup.
 *
 * O que este arquivo cuida, e que CSS nao cuida:
 *  - fechar ao clicar fora, ao pressionar Esc e ao escolher um item;
 *  - manter aria-expanded em dia, porque botao que abre menu precisa disso;
 *  - fechar se a tela passar de 900px, para nao ficar um painel aberto e
 *    invisivel quando a janela cresce.
 */
(function (global) {
  'use strict';

  var doc = document;
  var LIMITE_CELULAR = 900;
  var aberto = false;

  function botao() {
    return doc.getElementById('nav-menu-btn');
  }

  function pills() {
    // as duas navbars (produtor e servidor) usam ids diferentes
    return doc.getElementById('nav-pills') || doc.getElementById('nav-pills-servidor');
  }

  function abrir() {
    var p = pills();
    var b = botao();
    if (!p) return;
    p.classList.add('aberto');
    aberto = true;
    if (b) b.setAttribute('aria-expanded', 'true');
  }

  function fechar() {
    var p = pills();
    var b = botao();
    if (p) p.classList.remove('aberto');
    aberto = false;
    if (b) b.setAttribute('aria-expanded', 'false');
  }

  function alternar() {
    if (aberto) fechar();
    else abrir();
  }

  function noCelular() {
    return global.innerWidth <= LIMITE_CELULAR;
  }

  function ligar() {
    var b = botao();
    if (!b) return false;
    // evita ligar duas vezes se o script for avaliado de novo
    if (b.dataset.menuLigado === '1') return true;
    b.dataset.menuLigado = '1';

    b.addEventListener('click', function (e) {
      e.stopPropagation();
      alternar();
    });

    // clicar fora fecha
    doc.addEventListener('click', function (e) {
      if (!aberto) return;
      var p = pills();
      if (p && p.contains(e.target)) return;
      if (b.contains(e.target)) return;
      fechar();
    });

    // Esc fecha
    doc.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && aberto) fechar();
    });

    // ao growar a janela alem do limite, o painel sai de cena sozinho
    global.addEventListener(
      'resize',
      function () {
        if (!noCelular() && aberto) fechar();
      },
      { passive: true }
    );

    return true;
  }

  // o #nav-menu-btn so existe a partir deste script; se a navbar ainda nao
  // renderizou, tenta de novo no DOMContentLoaded
  if (!ligar()) {
    doc.addEventListener('DOMContentLoaded', ligar);
    // Ultimo recurso: navbar pode ser injetada depois por outro script
    setTimeout(ligar, 400);
  }

  // exposto para o menu poder ser fechado de fora (ex.: ao navegar)
  global.AmpliaMenuLateral = { abrir: abrir, fechar: fechar, alternar: alternar };
})(window);
