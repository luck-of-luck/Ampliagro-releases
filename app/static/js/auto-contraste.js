/*
 * auto-contraste.js — contraste de texto calculado em runtime.
 *
 * PROBLEMA que resolve
 * --------------------
 * Varios superficies do sistema (hero do painel do Servidor, cartoes de destaque,
 * cabecalhos de preset) usam `color: #fff` fixo sobre um `linear-gradient(...)`.
 * Quando o usuario escolhe um tema claro — "Por-do-sol", verdes claros — o tema
 * REESCREVE o gradiente com tons claros e o texto branco fica ilegivel
 * (contraste ~1.3:1). Isso foi observado no video de demonstracao: no hero do
 * painel do Servidor, a linha "Vinculado por: ... Permissoes: ..." e a linha da
 * Fazenda ficavam praticamente invisiveis sobre o gradiente amarelo-limao.
 *
 * Por que CSS sozinho nao resolve: nao existe media query para "qualquer
 * gradiente customized pelo usuario". A unica fonte de verdade e o pixel
 * realmente pintado, entao a correcao tem de acontecer em JS.
 *
 * O QUE FAZ
 * ---------
 * 1. Le o fundo REAL do elemento: se ha `background-image` com gradiente,
 *    extrai TODAS as paradas de cor (`rgb()`/`rgba()` do valor computado).
 *    Se o fundo e semitransparente, caminha para o ancuntil achar a primeira
 *    cor opaca e faz a composicao (alpha blending) corretamente.
 * 2. Converte para luminancia relativa (WCAG 2.1) e calcula a razao de
 *    contraste do texto contra CADA parada do gradiente.
 * 3. Escolhe a cor de texto (claro ou escuro) que maximiza o MINIMO dessas
 *    razoes — isto e o que importa num gradiente, porque a mesma frase passa
 *    por varias cores de fundo enquanto o cursor se move.
 * 4. Define `--texto-auto` no elemento. O CSS consome essa variavel.
 * 5. Quando nenhuma das duas opcoes atinge o alvo (AA 4.5:1 para texto normal,
 *    3:1 para texto grande >=18.66px bold ou >=24px), escurece/clareia a cor
 *    escolhida ate atingir, e adiciona uma sombra suave de apoio.
 *
 * USO
 * ---
 *   <div data-auto-contraste>...</div>     -> aplica sozinho
 *   <div data-auto-contraste="claro">...</div>  -> prefere texto claro
 *   <div data-auto-contraste="escuro">...</div> -> prefere texto escuro
 *
 * Chamadas manuais (apos montar conteudo dinamico):
 *   window.aplicarContrasteAutomatico(el)
 *   window.aplicarContrasteAutomatico(document)
 *
 * Reexecuta sozinho em: DOMContentLoaded, `ampliagro:palette` (troca de preset),
 * `ampliagro:tema`, eMutationObserver em subtrees marcados.
 */
(function () {
  'use strict';

  /* ---------------------------------------------------------------- cores */

  var CACHE_RE = new RegExp('rgba?\\([^)]+\\)', 'gi');
  var cache = Object.create(null);
  var cacheSize = 0;

  function parseColor(str) {
    if (!str) return null;
    var hit = cache[str];
    if (hit !== undefined) return hit;

    var m = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.%]+))?\s*\)/i.exec(str);
    var out = null;
    if (m) {
      var a = m[4] === undefined ? 1 : (String(m[4]).indexOf('%') > -1 ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
      out = [+m[1], +m[2], +m[3], isNaN(a) ? 1 : a];
    } else if (str.charAt(0) === '#') {
      var h = str.slice(1);
      if (h.length === 3 || h.length === 4) {
        h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2] + (h.length === 4 ? h[3] + h[3] : 'ff');
      }
      if (h.length === 6 || h.length === 8) {
        out = [
          parseInt(h.slice(0, 2), 16),
          parseInt(h.slice(2, 4), 16),
          parseInt(h.slice(4, 6), 16),
          h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1,
        ];
      }
    }
    if (!isFinite(out && out[0])) out = null;

    // Cache com limite: as cores de um tema sao um conjunto pequeno e estavel,
    // mas nao queremos crescer sem limite se alguem gerar cores dinamicas.
    if (cacheSize < 4000) { cache[str] = out; cacheSize++; }
    return out;
  }

  // WCAG 2.1 luminancia relativa
  function luminancia(c) {
    var r = c[0] / 255, g = c[1] / 255, b = c[2] / 255;
    if (r <= 0.03928) r = r / 12.92; else r = Math.pow((r + 0.055) / 1.055, 2.4);
    if (g <= 0.03928) g = g / 12.92; else g = Math.pow((g + 0.055) / 1.055, 2.4);
    if (b <= 0.03928) b = b / 12.92; else b = Math.pow((b + 0.055) / 1.055, 2.4);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function razao(l1, l2) {
    var a = Math.max(l1, l2), b = Math.min(l1, l2);
    return (a + 0.05) / (b + 0.05);
  }

  function sobre(c, fundo) {
    var a = c[3] === undefined ? 1 : c[3];
    if (a >= 1) return c;
    return [
      c[0] * a + fundo[0] * (1 - a),
      c[1] * a + fundo[1] * (1 - a),
      c[2] * a + fundo[2] * (1 - a),
      1,
    ];
  }

  function css(c) {
    return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ')';
  }

  function rgb(c) { return [c[0], c[1], c[2], 1]; }

  function escurecer(c, fat) {
    return [c[0] * fat, c[1] * fat, c[2] * fat, 1];
  }

  function clarear(c, fat) {
    return [c[0] + (255 - c[0]) * fat, c[1] + (255 - c[1]) * fat, c[2] + (255 - c[2]) * fat, 1];
  }

  /* ------------------------------------------------------- fundo real */

  // Retorna as cores de fundo que realmente aparecem atras do conteudo do
  // elemento. Para gradiente, TODAS as paradas (o pior caso e a mais clara
  // e a mais escura, e o texto precisa sobreviver as duas).
  function fundosReais(el) {
    var pilha = [];
    var no = el;
    var guarda = 0;

    while (no && no.nodeType === 1 && guarda++ < 40) {
      var cs = getComputedStyle(no);

      // 1) gradiente / imagem de fundo deste no
      var bi = cs.backgroundImage;
      if (bi && bi !== 'none' && bi.indexOf('gradient') > -1) {
        var ms = bi.match(CACHE_RE);
        if (ms) {
          for (var i = 0; i < ms.length; i++) {
            var gc = parseColor(ms[i]);
            if (gc) pilha.push(gc);
          }
          // Um gradiente e opaco o suficiente para decidir: nao ha nada util
          // atras dele, e seguir o ancuntil so traria o fundo da pagina.
          if (pilha.length) return compoe(pilha, no);
        }
      }

      // 2) cor de fundo solida
      var bc = parseColor(cs.backgroundColor);
      if (bc && bc[3] > 0) {
        pilha.push(bc);
        if (bc[3] >= 1) return compoe(pilha, no);
      }

      no = no.parentElement;
      if (no === document.body) break;
    }
    return compoe(pilha, el);
  }

  // Resolve alpha contra o fundo do pai e devolve cores opacas.
  function compoe(pilha, el) {
    if (!pilha.length) pilha = [rgb([255, 255, 255])];
    var fundo = [255, 255, 255];
    var pai = el && el.parentElement;
    for (var i = pilha.length - 1; i >= 0; i--) {
      var c = pilha[i];
      if (c[3] >= 1) { fundo = rgb(c); break; }
      fundo = rgb(sobre(c, fundo));
    }
    var out = [];
    for (var j = 0; j < pilha.length; j++) out.push(sobre(pilha[j], fundo));
    return out;
  }

  /* ------------------------------------------------------- escolha final */

  function minRazao(cores, corTexto) {
    var lt = luminancia(rgb(corTexto));
    var pior = Infinity;
    for (var i = 0; i < cores.length; i++) {
      var r = razao(lt, luminancia(cores[i]));
      if (r < pior) pior = r;
    }
    return pior;
  }

  function maiorLuminancia(cores) {
    var m = -1;
    for (var i = 0; i < cores.length; i++) {
      var l = luminancia(cores[i]);
      if (l > m) m = l;
    }
    return m;
  }

  function resolver(el, opcao) {
    var fundos = fundosReais(el);
    var alvo = opcao === 'claro' ? 3 : 4.5; // texto grande vs texto normal

    var CLARO = [255, 255, 255, 1];
    var ESCURO = [17, 24, 39, 1]; // slate-900: nao e preto puro, fica melhor em tema claro

    var rClaro = minRazao(fundos, CLARO);
    var rEscuro = minRazao(fundos, ESCURO);

    // A opcao "preferida" ganha por default; so troca se a outra for
    // SUBSTANCIALMENTE melhor. Evita texto trepidando entre dois tons
    // quando os dois racoes saem proximos.
    var escolhida, razaoEscolhida;
    if (opcao === 'claro') {
      escolhida = rClaro >= rEscuro * 0.92 ? CLARO : ESCURO;
    } else if (opcao === 'escuro') {
      escolhida = rEscuro >= rClaro * 0.92 ? ESCURO : CLARO;
    } else {
      escolhida = rClaro >= rEscuro ? CLARO : ESCURO;
    }
    razaoEscolhida = minRazao(fundos, escolhida);

    // Ainda abaixo do alvo? Empurra a cor na direcao que aumenta o contraste
    // ate bater. Em gradiente muito claro o branco puro nao salva; o escuro sim.
    var passos = 0;
    while (razaoEscolhida < alvo && passos++ < 8) {
      var fator = razaoEscolhida < alvo * 0.5 ? 0.82 : 0.93;
      var nova = luminancia(rgb(escolhida)) > 0.5 ? escurecer(escolhida, fator) : clarear(escolhida, fator);
      var rNova = minRazao(fundos, nova);
      if (rNova <= razaoEscolhida + 0.01) break; // nao ha ganho: para
      escolhida = nova;
      razaoEscolhida = rNova;
    }

    // Sombra de apoio: em gradiente com varias paradas, um texto de uma cor
    // solida passa por tons intermediarios que a matematica acima nao mede
    // (a parada mais clara e a mais escura sao as extremas). A sombra garante
    // a borda do glifo mesmo no meio do gradiente.
    var precisaSombra = razaoEscolhida < alvo || fundos.length > 1;
    var sombra = precisaSombra
      ? (luminancia(rgb(escolhida)) > 0.5
          ? '0 1px 2px rgba(0,0,0,.55), 0 0 10px rgba(0,0,0,.35)'
          : '0 1px 2px rgba(255,255,255,.45), 0 0 10px rgba(255,255,255,.25)')
      : 'none';

    return { cor: css(escolhida), razao: razaoEscolhida, sombra: sombra, fundoLum: maiorLuminancia(fundos) };
  }

  /* ------------------------------------------------------------ aplicacao */

  var SELECTOR = '[data-auto-contraste]';

  function aplicarUm(el) {
    if (!el || el.nodeType !== 1) return;
    var opcao = el.getAttribute('data-auto-contraste') || '';
    if (opcao === 'off' || opcao === 'false') return;
    var r = resolver(el, opcao);
    el.style.setProperty('--texto-auto', r.cor);
    el.style.setProperty('--sombra-auto', r.sombra);
    el.style.setProperty('--contraste-auto', String(Math.round(r.razao * 100) / 100));
    // Marca para CSS poder reagir (ex.: borda mais forte quando o fundo e busy)
    el.setAttribute('data-contraste-ok', r.razao >= 4.5 ? 'sim' : (r.razao >= 3 ? 'largo' : 'fraco'));
  }

  function aplicarRaiz(raiz) {
    var alvo = raiz && raiz.querySelectorAll ? raiz : document;
    var lista = [];
    if (raiz && raiz.matches && raiz.matches(SELECTOR)) lista.push(raiz);
    var encontrados = alvo.querySelectorAll(SELECTOR);
    for (var i = 0; i < encontrados.length; i++) lista.push(encontrados[i]);
    for (var j = 0; j < lista.length; j++) aplicarUm(lista[j]);
    return lista.length;
  }

  window.aplicarContrasteAutomatico = aplicarRaiz;
  window.AmpliagroContraste = { resolver: resolver, fundosReais: fundosReais, razao: razao, luminancia: luminancia };

  /* ------------------------------------------------------------- wiring */

  function rodar() { try { aplicarRaiz(document); } catch (e) { /* nunca quebrar a pagina */ } }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', rodar);
  } else {
    rodar();
  }

  // Troca de preset/tema muda os gradientes: refaz.
  ['ampliagro:palette', 'ampliagro:tema', 'ampliagro:preset'].forEach(function (evt) {
    document.addEventListener(evt, function () { setTimeout(rodar, 0); });
  });

  // Conteudo dinamico (modais, widgets, SPA): reaplica nos subtrees novos.
  if (window.MutationObserver) {
    var obs = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        for (var j = 0; j < muts[i].addedNodes.length; j++) {
          var n = muts[i].addedNodes[j];
          if (n.nodeType === 1) { try { aplicarRaiz(n); } catch (e) {} }
        }
      }
    });
    var iniciar = function () {
      try { obs.observe(document.body, { childList: true, subtree: true }); } catch (e) {}
    };
    if (document.body) iniciar();
    else document.addEventListener('DOMContentLoaded', iniciar);
  }
})();
