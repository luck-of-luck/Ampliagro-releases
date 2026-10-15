/**
 * Amplia.dispositivo — contexto de uso, para escolher QUAL funcao rodar.
 *
 * ============================================================================
 *  POR QUE NAO USAR userAgent COMO SINAL PRINCIPAL
 * ============================================================================
 *  A intencao original era "detectar se e celular pelo navegador". O problema e
 *  que userAgent congela, browsers reduzem o conteudo por privacidade, e ele
 *  erra nos casos que importam:
 *
 *    - iPad em "Modo Desktop" reporta ponteiro fino e tela grande. Por UA, ele
 *      vira desktop e perde os alvos de toque grandes.
 *    - Uma janela de desktop estreita NAO e um celular. Trocar as funcoes ali
 *      bagunca quem esta trabalhando num monitor.
 *    - Chrome reduz a string de UA para "Chrome/1xx" em desktop: a distincao
 *      some e todo mundo cai no mesmo ramo.
 *
 *  O que responde a pergunta que realmente importa — "este aparelho tem dedo?"
 *  — e CAPACIDADE, e isso nao depende de marca nem de versao de browser:
 *
 *    pointer: coarse     o ponteiro principal e o dedo
 *    hover: none         nao existe estado de hover
 *    maxTouchPoints      quantos toques simultaneos
 *
 *  A largura da viewport entra so como desempate, porque ela responde "quanto
 *  espaco eu tenho", que e outra pergunta. E e ela que faz um celular deitado
 *  virar "tablet" sem ser outro aparelho.
 *
 *  IMPORTANTE — isto nao substitui media query no CSS. Layout continua por
 *  media query, porque e a largura que de fato reflui. O que este modulo resolve
 *  e a OUTRA metade: escolher qual IMPLEMENTACAO de uma funcionalidade rodar.
 *  Layout por media query e comportamento por capacidade sao coisas diferentes.
 *
 * ============================================================================
 *  USO — substituir uma funcionalidade por modo
 * ============================================================================
 *
 *    Amplia.dispositivo.registrar('relatorio', {
 *      telefone : function (ctx) { return renderCompacto(ctx); },
 *      tablet   : function (ctx) { return renderMedio(ctx); },
 *      desktop  : function (ctx) { return renderCompleto(ctx); },
 *      // opcional: reexecutar sozinho quando o modo mudar (ex.: redimensionou
 *      // a janela do desktop para 500px e virou telefone)
 *      reativo : true,
 *    });
 *
 *    Amplia.dispositivo.aplicar('relatorio', { fazenda: f });
 *
 *    // so no telefone, sem registro:
 *    if (Amplia.dispositivo.e('telefone')) { ... }
 *
 *    // reagir a troca de modo (ex.: trocar a tabela por cards ao girar):
 *    document.addEventListener('amplia:modo-mudou', function (e) {
 *      console.log(e.detail.de, '->', e.detail.para);
 *    });
 *
 * ============================================================================
 */
(function (global) {
  'use strict';

  var RAIZ = document.documentElement;

  // Limiares. Telefone = uma mao, portrait. Acima disso, tablet.
  var FONE_ATE = 640;
  var TABLET_ATE = 1100;

  /**
   * Le os sinais do navegador. Tudo aqui e barato: sao media queries e ints,
   * nada de layout. Pode rodar varias vezes por segundo sem custo.
   */
  function lerSinais() {
    var mq = function (q) {
      return !!(global.matchMedia && global.matchMedia(q).matches);
    };
    return {
      largura: global.innerWidth || 0,
      altura: global.innerHeight || 0,
      // ponteiro principal grosso = dedo como input principal
      toque: mq('(pointer: coarse)') || (global.navigator && global.navigator.maxTouchPoints > 0),
      // existe aparelho com dois dedos ao mesmo tempo?
      multitoque: !!(global.navigator && global.navigator.maxTouchPoints > 1),
      // nao existe hover de verdade (touch)
      semHover: mq('(hover: none)'),
      dpr: global.devicePixelRatio || 1,
      // pista de plataforma. NAO decide sozinho: so desempata tablet.
      uaMobile: mq('(any-pointer: coarse)') && /Android|iPhone|iPod/i.test(ua()),
      uaTablet: /iPad|Tablet|Silk|Android(?!.*Mobile)/i.test(ua()),
      // save-data: o usuario pediu economia de dados
    };
  }

  function ua() {
    return (global.navigator && global.navigator.userAgent) || '';
  }

  /** Pista de plataforma via userAgentData quando existir (API moderna, assina). */
  function plataforma() {
    var d = global.navigator && global.navigator.userAgentData;
    if (!d) return null;
    // 'mobile' distingue celular de tablet; platform traz o SO de graca
    return { plataforma: d.platform, movel: d.mobile };
  }

  /**
   * Classifica. Regra: CAPACIDADE decide o familia, LARGURA escolhe o tamanho.
   */
  function classificar(s) {
    // Sem toque e sem hover fino => apontador de rato: computador.
    var temRato = !s.toque || (mqFine() && !s.semHover);
    if (temRato) return 'desktop';

    // Tem dedo. Agora o tamanho decide.
    if (s.largura <= FONE_ATE && !s.uaTablet) return 'telefone';
    return 'tablet';
  }

  function mqFine() {
    return !!(global.matchMedia && global.matchMedia('(pointer: fine)').matches);
  }

  var estado = null;
  var registro = Object.create(null);
  var ultimaContexto = Object.create(null);

  /** Le e (re)classifica. Devolve o contexto completo. */
  function avaliar() {
    var s = lerSinais();
    var modo = classificar(s);
    estado = {
      modo: modo,
      // alias explicitos, para o codigo nao depender de string solta
      eTelefone: modo === 'telefone',
      eTablet: modo === 'tablet',
      eDesktop: modo === 'desktop',
      eToque: s.toque,
      multitoque: s.multitoque,
      semHover: s.semHover,
      paisagem: s.largura > s.altura,
      dpr: s.dpr,
      telaPequena: s.largura < 400, // iPhone SE e parecidos
      plataforma: plataforma(),
      sinais: s,
    };

    // O atributo no <html> deixa o CSS poder falar a mesma lingua, e o
    // devtools mostra em que modo a pagina esta.
    if (RAIZ.getAttribute('data-modo') !== modo) {
      RAIZ.setAttribute('data-modo', modo);
      // data-toque permite afinar CSS por CAPACIDADE, nao so por largura
      RAIZ.setAttribute('data-toque', s.toque ? 'sim' : 'nao');
    }
    return estado;
  }

  // --------------------------------------------------------------------- API

  var api = {
    /** Le o contexto atual (avaliando se ainda nao avaliou). */
    atual: function () {
      if (!estado) avaliar();
      return estado;
    },

    /** true se o modo atual for este (aceita lista). */
    e: function (umOuMais) {
      var m = api.atual().modo;
      if (Array.isArray(umOuMais)) return umOuMais.indexOf(m) !== -1;
      return m === umOuMais;
    },

    /**
     * Registra uma funcionalidade com uma implementacao por modo.
     *   registro('relatorio', { telefone: fn, desktop: fn, reativo: true })
     */
    registrar: function (nome, impl) {
      registro[nome] = impl;
      // Se ja estamos num modo com implementacao, roda na hora — senao o
      // recurso so apareceria na proxima troca de modo.
      if (ultimaContexto[nome] !== undefined) {
        try {
          api.aplicar(nome, ultimaContexto[nome]);
        } catch (e) {
          reportar(nome, e);
        }
      }
      return api;
    },

    /**
     * Executa a implementacao correspondente ao modo atual.
     * Passa (contexto, dados) para a funcao escolhida.
     */
    aplicar: function (nome, dados) {
      var r = registro[nome];
      if (!r) return undefined;
      ultimaContexto[nome] = dados;

      var modo = api.atual().modo;
      // Do mais especifico para o mais generico: se nao houver 'telefone' nem
      // 'tablet', cai no 'default'; sem nada, cai no 'desktop'.
      var fn = r[modo] || r.default || r.desktop;
      if (typeof fn !== 'function') return undefined;
      try {
        return fn(api.atual(), dados);
      } catch (e) {
        reportar(nome, e);
        return undefined;
      }
    },

    /** Reexecuta todos os recursos marcados como reativos. */
    reaplicar: function () {
      for (var nome in registro) {
        if (registro[nome].reativo && ultimaContexto[nome] !== undefined) {
          try {
            api.aplicar(nome, ultimaContexto[nome]);
          } catch (e) {
            reportar(nome, e);
          }
        }
      }
    },

    /** Nomes registrados (util para depurar). */
    listar: function () {
      return Object.keys(registro);
    },
  };

  function reportar(nome, erro) {
    // Falha de recurso substituido nao pode derrubar a pagina: o modo detectado
    // e apenas uma pista, nao uma verdade. Degrada e avisa no console.
    if (global.console && console.warn) {
      console.warn('[dispositivo] recurso "' + nome + '" falhou:', erro && erro.message);
    }
  }

  // ------------------------------------------------------------- reatividade

  var pendente = null;
  function agendar() {
    if (pendente) return;
    pendente = global.requestAnimationFrame(function () {
      pendente = null;
      var antes = estado && estado.modo;
      var agora = avaliar();
      if (antes && agora.modo !== antes) {
        api.reaplicar();
        emitir(agora);
      }
    });
  }

  function emitir(ctx) {
    document.dispatchEvent(
      new CustomEvent('amplia:modo-mudou', {
        detail: { de: estado && estado._de, para: ctx.modo, contexto: ctx },
      })
    );
  }

  // Reavalia quando muda o tamanho OU a orientacao. O 'resize' e o que faz o
  // desktop estreito virar telefone sem recarregar a pagina.
  global.addEventListener('resize', agendar, { passive: true });
  global.addEventListener('orientationchange', agendar, { passive: true });
  // some matchMedia e mede mudanca de capacidade (ex.: conectou um mouse)
  if (global.matchMedia) {
    ['(pointer: coarse)', '(pointer: fine)', '(hover: none)'].forEach(function (q) {
      var mq = global.matchMedia(q);
      if (mq.addEventListener) mq.addEventListener('change', agendar);
      else if (mq.addListener) mq.addListener(agendar); // Safari antigo
    });
  }

  // Primeira avaliacao, o mais cedo possivel, para o CSS ja pintar certo.
  avaliar();

  global.Amplia = global.Amplia || {};
  global.Amplia.dispositivo = api;
})(window);
