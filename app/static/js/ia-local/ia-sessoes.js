/* AS SESSÕES DA CONVERSA, POR SECÇÃO
 * ==================================
 * A conversa da AmplIA é UMA só no ecrã, mas o produtor trabalha em VÁRIAS
 * secções (Financeiro, Estoque, Agenda). A pergunta "quanto vendi este mês" no
 * Financeiro e a pergunta "quanta ureia tenho" no Estoque não são a mesma
 * conversa, e misturá-las é dar à IA um contexto que não existe.
 *
 * Daqui nasce a SESSÃO: um nome e uma lista de mensagens, guardados por
 * caminho (`/financeiro`, `/estoque`). Trocar de secção troca de conversa, e
 * o botão "Histórico" volta a uma conversa anterior DA MESMA SECÇÃO.
 *
 * PORQUE UM FICHEIRO E UM `window`
 * ===============================
 * MEDIDO 2026-10-10: o botão "Histórico" dizia "Ainda não há conversa para
 * ver" quando havia conversa. A causa: `ia-rail-acoes.js` é um MÓDULO ES
 * (carregado por `import()` no `ia-rail-loader.js`) e `iaHist` vivia no
 * `let iaHist` do `<script type="module">` do `ia_dock.html`. Escopo de
 * módulo não é `window`: `typeof iaHist` noutro módulo é `'undefined'`
 * SEMPRE, e a guarda `typeof iaHist !== 'undefined'` devolvia vazio em
 * silêncio. Duas conversas possíveis, nenhuma delas a funcionar.
 *
 * Por isso a loja vive aqui, registada em `window.IaSessoes`, e tanto o
 * template como as acções da barra falam com ela. Um sítio, um teste, uma
 * verdade.
 *
 * O NOME DA SESSÃO
 * ================
 * O produtor pede "a IA dá um nome à secção". Nomear por MODELO seria mais
 * poético, e não é o que aqui se faz, por uma razão medida: o motor local
 * (`iaLocal.iaChat`) é opcional e descarrega 1,1 GB. Uma sessão cujo nome
 * depende de um download que ainda não aconteceu é uma sessão sem nome no
 * dia em que é criada — que é justamente quando o produtor a quer ver.
 *
 * O nome é portanto a PRIMEIRA PERGUNTA do produtor, truncada. É o produtor
 * que nomeia a conversa, pela primeira coisa que pediu nela, e não há
 * download nenhuma a caminho de o impedir. `renomear()` existe para o caso
 * de querer outro.
 */

(function () {
  'use strict';

  /* SINGLETON.
   *
   * Este ficheiro é carregado por DOIS caminhos com DUAS URLs distintas: o
   * `ia_dock.html` importa-o estaticamente (para garantir que existe antes de
   * o dock correr), e o `ia-rail-loader.js` importa-o dinamicamente com
   * `?v=` — que é o cache-busting do projecto. Duas URLs são dois MÓDULOS, e
   * dois módulos são duas execuções desta IIFE.
   *
   * A segunda execução fazia `window.IaSessoes = api` por cima da primeira,
   * e o observador que a primeira tinha registado ficava órfão: o `pushState`
   * passava a apontar para o `avisa` da segunda, e a lista de ouvintes da
   * primeira já não era chamada por ninguém. O sintoma era o pior possível —
   * a troca de secção funcionava até alguém abrir a barra.
   *
   * Com a guarda, a primeira execução é a que fica. A segunda vê a loja já
   * posta e sai. */
  if (window.IaSessoes) return;

  var PREFIXO = 'amplia_ia_sessoes_';
  var MAX_SESSOES = 20;
  var MAX_MSGS = 20;
  var TAMANHO_TITULO = 40;

  /* O caminho identifica a secção. `/financeiro/` e `/financeiro` são a
     mesma secção — sem esta normalização, o produtor entrava pela barra de
     navegação e pelo botão de voltar e via duas conversas diferentes. */
  function secao() {
    var p = '';
    try {
      p = window.location.pathname || '/';
    } catch (e) {
      p = '/';
    }
    if (p.length > 1 && p.charAt(p.length - 1) === '/') p = p.slice(0, -1);
    return p || '/';
  }

  function chave() {
    return PREFIXO + secao().replace(/[^a-z0-9/_-]/gi, '_');
  }

  function novaId() {
    return 'sess_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  /* Desempate.
   *
   * `atualizada` é um `Date.now()` em MILISSEGUNDOS, e duas conversas criadas
   * no mesmo milissegundo empatam — a lista fica com a ordem que calhou, e a
   * conversa nova NÃO sobe ao topo. MEDIDO: `listar()[0]` devolvia a antiga.
   *
   * O `seq` é um contador: não empata nunca, e cresce com a criação. */
  var seq = 0;
  function proximoSeq() {
    seq += 1;
    return seq;
  }

  function vazia() {
    return { versao: 1, atualId: null, sessoes: [] };
  }

  function ler() {
    try {
      var raw = window.localStorage.getItem(chave());
      if (!raw) return vazia();
      var d = JSON.parse(raw);
      if (!d || typeof d !== 'object') return vazia();
      if (!Array.isArray(d.sessoes)) d.sessoes = [];
      if (typeof d.atualId !== 'string') d.atualId = null;
      return d;
    } catch (e) {
      return vazia();
    }
  }

  function escrever(d) {
    try {
      window.localStorage.setItem(chave(), JSON.stringify(d));
      return true;
    } catch (e) {
      /* Quota cheia ou modo privado. Perder o histórico é melhor do que
         rebentar a conversa: quem está a falar com a IA não pode ficar sem
         resposta por causa de um `setItem`. */
      return false;
    }
  }

  /* O título é a primeira pergunta do produtor.
   *
   * Trunca por palavras, e não aos 40 caracteres: cortar "Qual minha produz"
   * a meio de uma palavra é um nome que ninguém reconhece como sendo a
   * pergunta que fez. */
  function tituloAuto(mensagens) {
    var primeira = null;
    for (var i = 0; i < (mensagens || []).length; i++) {
      if (mensagens[i] && mensagens[i].role === 'user') {
        primeira = mensagens[i];
        break;
      }
    }
    if (!primeira) return '';
    var t = String(primeira.content || '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!t) return '';
    if (t.length <= TAMANHO_TITULO) return t;
    var corte = t.slice(0, TAMANHO_TITULO);
    var espaco = corte.lastIndexOf(' ');
    if (espaco > 12) corte = corte.slice(0, espaco);
    return corte + '…';
  }

  function sanitizaMensagens(mensagens) {
    if (!Array.isArray(mensagens)) return [];
    var out = [];
    for (var i = 0; i < mensagens.length && out.length < MAX_MSGS; i++) {
      var m = mensagens[i];
      if (!m || typeof m !== 'object') continue;
      out.push({
        role: String(m.role || 'user'),
        content: String(m.content == null ? '' : m.content),
      });
    }
    return out;
  }

  function daLista(d) {
    var s = d.sessoes.slice();
    s.sort(function (a, b) {
      var porData = (b.atualizada || b.criada || 0) - (a.atualizada || a.criada || 0);
      if (porData) return porData;
      return (b.seq || 0) - (a.seq || 0);
    });
    return s;
  }

  function atualIdDe(d) {
    if (d.atualId) {
      for (var i = 0; i < d.sessoes.length; i++) {
        if (d.sessoes[i].id === d.atualId) return d.atualId;
      }
    }
    return null;
  }

  /* ── A TROCA DE SECÇÃO ─────────────────────────────────────────────────
   *
   * O SPA muda de secção com `history.pushState`, e o `pushState` NÃO dispara
   * evento nenhum. Sem este gancho, o dock só descobre a troca quando o
   * produtor escreve — e até lá continua a mostrar, e a responder com, a
   * conversa da secção anterior.
   *
   * MEDIDO: o `ia_dock.html` chamava `maybeSwitchPath()` dentro do
   * `iaDockSend()`, que é DEPOIS de o produtor ter escrito na secção nova. A
   * primeira mensagem da secção nova entrava na conversa da secção anterior.
   *
   * PORQUE UMA LISTA DE OUVINTES, E NÃO UM GANCHO POR CHAMADA
   * =========================================================
   * MEDIDO 2026-10-10: a primeira versão embrulhava o `pushState` uma vez e
   * deixava o fecho do PRIMEIRO observador dentro do embrulho. O segundo
   * `observar()` não embrulhava nada — só ouvia `popstate` — e nunca era
   * avisado de uma navegação SPA. Um histórico que só funciona para quem se
   * registou primeiro é um histórico que funciona na demonstração.
   *
   * O ORIGINAL FICA GUARDADO, E O EMBRULHO É REINSTALADO
   * ====================================================
   * Sem o original guardado, um embrulho por cima de outro embrulho chamaria a
   * navegação duas vezes — e o dock desenharia a conversa duas vezes. Com ele,
   * cada execução do módulo aponta o embrulho para o SEU próprio aviso, e a
   * cadeia até ao original tem sempre um elo. */
  var ouvintes = null;

  function garanteGancho() {
    if (ouvintes) return ouvintes;
    ouvintes = [];
    var h = window.history;
    if (!h) return ouvintes;
    if (!h.__iaOriginal) h.__iaOriginal = {};

    var ultima = secao();

    function avisa() {
      var agora = secao();
      if (agora === ultima) return;
      ultima = agora;
      var copia = ouvintes.slice();
      for (var i = 0; i < copia.length; i++) {
        try {
          copia[i](agora);
        } catch (e) {
          /* Um ouvinte que rebenta não pode levar os outros nem a navegação
             abaixo. */
        }
      }
    }

    function embrulha(nome) {
      if (!h.__iaOriginal[nome]) h.__iaOriginal[nome] = h[nome];
      var original = h.__iaOriginal[nome];
      if (typeof original !== 'function') return;
      h[nome] = function () {
        var r = original.apply(this, arguments);
        avisa();
        return r;
      };
    }

    embrulha('pushState');
    embrulha('replaceState');
    window.addEventListener('popstate', avisa);
    return ouvintes;
  }

  var api = {
    secao: secao,
    chave: chave,
    tituloAuto: tituloAuto,
    MAX_SESSOES: MAX_SESSOES,
    MAX_MSGS: MAX_MSGS,

    /* A lista para o painel: a mais recente primeiro. */
    listar: function () {
      return daLista(ler());
    },

    /* A conversa que está no ecrã. Pode ser null — secção nunca aberta. */
    atual: function () {
      var d = ler();
      var id = atualIdDe(d);
      if (!id) {
        var l = daLista(d);
        return l.length ? l[0] : null;
      }
      for (var i = 0; i < d.sessoes.length; i++) {
        if (d.sessoes[i].id === id) return d.sessoes[i];
      }
      return null;
    },

    /* As mensagens da conversa actual. É o que o dock põe no `iaHist`. */
    mensagens: function () {
      var s = api.atual();
      return s && Array.isArray(s.mensagens) ? s.mensagens : [];
    },

    /* Grava o que está no ecrã. Cria a sessão se a secção não tiver nenhuma.
     *
     * `atualizada` muda sempre: é por aí que a lista se ordena, e uma conversa
     * que acabou de receber uma resposta tem de subir ao topo. */
    guardar: function (mensagens) {
      var d = ler();
      var msgs = sanitizaMensagens(mensagens);
      var id = atualIdDe(d);
      var s = null;
      for (var i = 0; i < d.sessoes.length; i++) {
        if (d.sessoes[i].id === id) s = d.sessoes[i];
      }
      if (!s) {
        if (msgs.length) {
          s = {
            id: novaId(),
            titulo: tituloAuto(msgs),
            mensagens: msgs,
            criada: Date.now(),
            atualizada: Date.now(),
            seq: proximoSeq(),
          };
          d.sessoes.push(s);
          d.atualId = s.id;
        }
      } else {
        s.mensagens = msgs;
        s.atualizada = Date.now();
        if (!s.titulo) s.titulo = tituloAuto(msgs);
      }
      while (d.sessoes.length > MAX_SESSOES) d.sessoes.shift();
      escrever(d);
      return s;
    },

    /* Conversa nova nesta secção. A anterior fica no histórico, com nome. */
    nova: function () {
      var d = ler();
      var s = {
        id: novaId(),
        titulo: '',
        mensagens: [],
        criada: Date.now(),
        atualizada: Date.now(),
        seq: proximoSeq(),
      };
      d.sessoes.push(s);
      d.atualId = s.id;
      while (d.sessoes.length > MAX_SESSOES) d.sessoes.shift();
      escrever(d);
      return s;
    },

    /* Voltar a uma conversa antiga. Devolve as mensagens para quem desenha. */
    restaurar: function (id) {
      var d = ler();
      for (var i = 0; i < d.sessoes.length; i++) {
        if (d.sessoes[i].id === id) {
          d.atualId = id;
          escrever(d);
          return d.sessoes[i].mensagens || [];
        }
      }
      return null;
    },

    apagar: function (id) {
      var d = ler();
      var antes = d.sessoes.length;
      d.sessoes = d.sessoes.filter(function (s) {
        return s.id !== id;
      });
      if (d.atualId === id) d.atualId = null;
      escrever(d);
      return d.sessoes.length !== antes;
    },

    renomear: function (id, titulo) {
      var d = ler();
      var t = String(titulo == null ? '' : titulo)
        .replace(/\s+/g, ' ')
        .trim();
      if (!t) return false;
      for (var i = 0; i < d.sessoes.length; i++) {
        if (d.sessoes[i].id === id) {
          d.sessoes[i].titulo = t.slice(0, TAMANHO_TITULO * 2);
          escrever(d);
          return true;
        }
      }
      return false;
    },

    /* ── A TROCA DE SECÇÃO ─────────────────────────────────────────────────
     *
     * O SPA muda de secção com `history.pushState`, e o `pushState` NÃO
     * dispara evento nenhum. Sem este gancho, o dock só descobre a troca
     * quando o produtor escreve — e até lá continua a mostrar, e a responder
     * com, a conversa da secção anterior.
     *
     * MEDIDO: o `ia_dock.html` chamava `maybeSwitchPath()` dentro do
     * `iaDockSend()`, que é DEPOIS de o produtor ter escrito na secção nova.
     * A primeira mensagem da secção nova entrava na conversa da secção
     * anterior.
     *
     * PORQUE UMA LISTA DE OUVINTES, E NÃO UM GANCHO POR CHAMADA
     * =========================================================
     * MEDIDO 2026-10-10: a primeira versão embrulhava o `pushState` uma vez e
     * deixava o fecho do PRIMEIRO observador dentro do embrulho. O segundo
     * `observar()` não embrulhava nada — só ouvia `popstate` — e nunca era
     * avisado de uma navegação SPA. Um histórico que só funciona para quem se
     * registou primeiro é um histórico que funciona na demonstração.
     *
     * O ORIGINAL FICA GUARDADO, E O EMBRULHO É REINSTALADO
     * ====================================================
     * Sem o original guardado, um embrulho por cima de outro embrulho chamaria
     * a navegação duas vezes — e o dock desenharia a conversa duas vezes. Com
     * ele, cada execução do módulo aponta o embrulho para o SEU próprio
     * aviso, e a cadeia até ao original tem sempre um elo. */

    observar: function (cb) {
      if (typeof cb !== 'function') return function () {};
      var lista = garanteGancho();
      lista.push(cb);
      return function () {
        var i = lista.indexOf(cb);
        if (i >= 0) lista.splice(i, 1);
      };
    },
  };

  window.IaSessoes = api;
})();
