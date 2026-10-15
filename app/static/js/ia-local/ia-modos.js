/* OS MODOS DE CRIAÇÃO — a chave seletora que FORÇA a resposta.
 * ===========================================================
 *
 * O PEDIDO, NA PALAVRA DO PRODUTOR
 * ================================
 * \"Criar no painel\" e \"criar no dashboard\" não são menus de escolha — são
 * CHAVES seletoras de ligado/desligado. Ligadas, FORÇAM a IA a responder
 * nesses locais: menos texto, e peças — planilhas e gráficos no chat, widgets
 * no preset do dashboard. O objectivo é sair do \"pergunta e texto de
 * resposta\".
 *
 * PORQUE UMA LOJA, E NÃO DUAS VARIÁVEIS
 * ======================================
 * O estado tem de ser o MESMO em três sítios: o interruptor desenhado na
 * barra, a directiva que o `iaDockSend` (no template) injeta no prompt, e a
 * confirmação que a acção da barra fala. Três leitores de uma verdade.
 *
 * MEDIDO 2026-10-10 (o padrão que aqui se repete): o `iaHist` vivia no `let`
 * do módulo do template, e `ia-rail-acoes.js` — outro módulo — via
 * `typeof iaHist === 'undefined'` para sempre. Escopo de módulo não é
 * `window`. A loja vive portanto em `window.IaModos`, e os três leitores
 * falam com ela.
 *
 * A DIRECTIVA
 * ===========
 * Ligada a chave, CADA mensagem do produtor leva a directiva à frente. Não é
 * um sistema de intenção: é uma instrução de FORMATO. O produtor escreve
 * \"quanto vendi\" e a IA sabe que a resposta tem de ser uma peça, não um
 * parágrafo. Desligada, a directiva sai e a conversa volta à prosa.
 *
 * A directiva é curta de propósito: o motor local (WebLLM, 1,1 GB) tem
 * contexto curto, e um manual de formatação gasto a cada turno é contexto que
 * não sobra para os dados.
 */

(function () {
  'use strict';

  /* SINGLETON — a mesma razão do `ia-sessoes.js`: este ficheiro entra por
   * dois caminhos (import estático no template e import dinâmico com `?v=`
   * no loader), e duas URLs são dois módulos e duas execuções desta IIFE.
   * A segunda execução faria `window.IaModos = api` por cima da primeira, e
   * o observador que a primeira registou ficaria órfão. Com a guarda, a
   * primeira é a que fica. */
  if (window.IaModos) return;

  var CHAVE_LOJA = 'amplia_ia_modos';

  /* Os três modos. A ordem é a do pedido do produtor. */
  var MODOS = ['chat', 'painel', 'nuvem'];

  /* O que cada modo FORÇA. O texto é o que vai à frente da pergunta. */
  var DIRECTIVAS = {
    chat:
      '[MODO CRIAR NO CHAT — LIGADO] ' +
      'Responde com PEÇA, não com prosa: primeiro uma frase curta do que ' +
      'mostraste, e depois os blocos. Usa bloco "planilha" quando houver ' +
      'linhas para tabular (vendas, despesas, operações, colheitas) e ' +
      'bloco "grafico" quando houver séries para comparar. Nunca inventes ' +
      'números: sem registo, o bloco fica "sem_dado".',
    painel:
      '[MODO CRIAR NO PAINEL — LIGADO] ' +
      'A resposta tem de aterrar no PAINEL do dashboard: escolhe 3 a 4 ' +
      'widgets do catálogo que mostrem o que pedi e preenche-os só com os ' +
      'nossos números medidos. Confirma comigo antes de gravar. Sem texto ' +
      'de enchimento — a peça é o painel.',
    nuvem:
      '[MODO USAR AGENTE DA NUVEM — LIGADO] ' +
      'Usa a API do Google Gemini (modelos gratuitos) para gerar respostas. ' +
      'Quando ligado, ignora o motor local e consulta diretamente a nuvem. ' +
      'Responde com PEÇA quando houver dados para tabular ou gráficos, ' +
      'caso contrário responde em formato de texto claro e objetivo.',
  };

  var NOMES = {
    chat: 'Criar no chat',
    painel: 'Criar no painel',
    nuvem: 'Usar agente da nuvem',
  };

  function ler() {
    var d = { chat: false, painel: false, nuvem: false };
    try {
      var raw = window.localStorage.getItem(CHAVE_LOJA);
      if (raw) {
        var j = JSON.parse(raw);
        MODOS.forEach(function (m) {
          d[m] = Boolean(j && j[m]);
        });
      }
    } catch (e) {
      /* localStorage pode estar cheio ou bloqueado (modo privado). Um modo
         que não grava é um modo que não persiste — e dizer isso ao produtor
         na cara seria pior do que a conversa continuar. */
    }
    return d;
  }

  function escrever(d) {
    try {
      window.localStorage.setItem(CHAVE_LOJA, JSON.stringify(d));
    } catch (e) {}
    return d;
  }

  var ouvintes = [];

  function avisa(qual, ligado) {
    ouvintes.slice().forEach(function (cb) {
      try {
        cb(qual, ligado);
      } catch (e) {
        /* Um observador que rebenta não pode levar os outros. */
      }
    });
  }

  var api = {
    MODOS: MODOS,
    NOMES: NOMES,

    /* O estado de um modo. `undefined` para um nome desconhecido. */
    activo: function (qual) {
      if (MODOS.indexOf(qual) < 0) return false;
      return ler()[qual] === true;
    },

    /* Algum modo ligado? É o que o template pergunta antes de injectar. */
    algumLigado: function () {
      var d = ler();
      return d.chat || d.painel || d.nuvem;
    },

    /* A directiva de um modo. String vazia quando desligado. */
    directiva: function (qual) {
      if (MODOS.indexOf(qual) < 0) return '';
      return ler()[qual] === true ? DIRECTIVAS[qual] || '' : '';
    },

    /* TODAS as directivas ligadas, numa frase. É o que vai à frente da
     * pergunta do produtor. Vazia quando nenhuma está ligada. */
    directivas: function () {
      var partes = [];
      MODOS.forEach(function (m) {
        var d = api.directiva(m);
        if (d) partes.push(d);
      });
      return partes.join(' ');
    },

    /* Liga ou desliga. Devolve o estado novo. */
    alternar: function (qual) {
      if (MODOS.indexOf(qual) < 0) return false;
      var d = ler();
      d[qual] = !d[qual];
      escrever(d);
      avisa(qual, d[qual]);
      return d[qual] === true;
    },

        /* Desliga os três — "Nova conversa" não deve herdar um modo que o
     * produtor já não quer. */
    desligarTodos: function () {
      var d = { chat: false, painel: false, nuvem: false };
      escrever(d);
      MODOS.forEach(function (m) {
        avisa(m, false);
      });
    },

    /* A frase que a barra fala quando se liga ou desliga. */
    fraseDoEstado: function (qual) {
      var nome = NOMES[qual] || qual;
      return api.activo(qual)
        ? nome + ' LIGADO — as próximas respostas vêm como peça, não como texto.'
        : nome + ' desligado — respostas voltam ao texto normal.';
    },

    observar: function (cb) {
      if (typeof cb !== 'function') return function () {};
      ouvintes.push(cb);
      return function () {
        var i = ouvintes.indexOf(cb);
        if (i >= 0) ouvintes.splice(i, 1);
      };
    },
  };

  window.IaModos = api;
})();
