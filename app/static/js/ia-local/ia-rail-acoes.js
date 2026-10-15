/* As acções da barra do AmplIA.
 *
 * O QUE UM BOTÃO QUE NÃO FUNCIONA CUSTA
 * ======================================
 * O produtor clica, o ecrã não muda, e ele conclui que a IA está avariada. Por
 * isso um botão só entra na barra quando tem FUNÇÃO — e a função tem de fazer o
 * trabalho, não sórite-lo.
 *
 * "Pôr o texto no input" NÃO é fazer o trabalho
 * ==============================================
 * A primeira versão de "Criar no chat" e "Criar no painel" escrevia
 * "desenha no chat: " no campo e devolvia a mão ao produtor. O botão fazia um
 * gesto e o trabalho continuava todo dele — e o produtor clica num ícone
 * esperando um desenho, recebe um cursor a piscar, e conclui que o ícone está
 * quebrado.
 *
 * Hoje os dois vão pelo `AmpliaChamado.pedirChat`, que é a via que o resto do
 * produto usa: enche o input, envia, e o pedido chega ao `sandbox` do servidor,
 * que é quem decide, valida e devolve a peça. A diferença entre "o botão fez um
 * gesto" e "o botão mandou o pedido" é a diferença entre um ícone decorativo e
 * um atalho.
 *
 * O QUE NÃO SE PODE
 * =================
 * Nenhuma acção escreve fora da porta do sandbox. Não há `fetch` de escrita aqui:
 * `iaCriarNoPainel` e `iaResponderNoPainel` não gravam num preset — eles
 * PEDEM o preset, e o `h_preset_palco` (`app/ia/intents_palco_preset.py`)
 * grava depois de o produtor responder que sim. Um botão com um `POST` próprio
 * seria um caminho novo para o mesmo registo, e é exactamente isso que
 * `app/amplia_mcp/` existe para fechar.
 */

(function () {
  'use strict';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* Uma mensagem NO CHAT. Va para a mesma fila que o texto do produtor, para
   * que a conversa fique com a ordem em que aconteceu — um `alert()` por cima
   * do painel some quando se clica noutro sítio.
   *
   * ESTE MÓDULO NÃO SE REGISTA EM `window.iaLocalMsg`
   * =====================================================
   * `iaLocalMsg` é um gancho do HOST: se a página quiser as mensagens noutro
   * sítio, regista lá a sua função e esta usa-a.
   *
   * Havia aqui `window.iaLocalMsg = fala;` no fim do IIFE, e era um ciclo: o
   * gancho passava a ser `fala` — a única implementação de `iaLocalMsg` em todo
   * o projeto. A guarda `typeof window.iaLocalMsg === 'function'` era então
   * verdadeira para a própria `fala`, e a linha seguinte chamava `fala` outra
   * vez. Cada acção que fala rebentava a pilha:
   *
   *   RangeError: Maximum call stack size exceeded
   *
   * Ou seja: "Selecionar área", "Histórico", "Exportar" e "Relatar problema"
   * rebentavam todas — e sem mensagem, porque o erro acontecia na PRIMEIRA
   * chamada, dentro do `onclick`, onde ninguém o vê. Por isso `iaLocalMsg`
   * aparece em mais lado nenhum do repositório: nunca chegou a funcionar. */
  function fala(texto, bot) {
    var gancho = window.iaLocalMsg;
    if (typeof gancho === 'function' && gancho !== fala) {
      gancho(texto, bot ? 'bot' : 'user');
      return true;
    }
    var inp = document.getElementById('ia-dock-input');
    if (inp && !bot) {
      inp.value = texto;
      inp.focus();
      return true;
    }
    // Sem gancho e sem input: pelo menos diz-se alguma coisa onde se vê.
    var body = document.getElementById('ia-chat-body');
    if (body) {
      var d = document.createElement('div');
      d.className = 'ia-msg bot';
      d.textContent = texto;
      body.appendChild(d);
      body.scrollTop = body.scrollHeight;
      return true;
    }
    return false;
  }

  /* ── 1. PRINT DA TELA ───────────────────────────────────────────────────
   *
   * O botão "Selecionar área" agora tira um PRINT: pede ao browser a tela,
   * mostra-a, deixa o produtor arrastar o rectângulo, e devolve um PNG com os
   * píxeis que estavam no ecrã.
   *
   * Tudo o que isto faz — a guarda de página, o pedido de autorização, o
   * overlay, o recorte e o print em cima do campo — está em `ia-print.js`. A
   * razão de ser um ficheiro à parte: o overlay, o vídeo e o canvas não têm
   * nada a ver com as outras acções da barra, e um ficheiro que faz duas coisas
   * é um ficheiro em que nenhuma delas é feita bem.
   *
   * A versão anterior marcava um rectângulo sobre a página e tentava rasterizar
   * o DOM com `foreignObject`. Falhava no Firefox e no Safari, perdia o CSS de
   * fora, perdia as imagens e os canvas, e — o mais importante — não apanhava
   * nada que estivesse FORA do DOM: nem a barra lateral, nem outra janela. Um
   * print da tela que só fotografa a página não é um print da tela. */
  /* SEM PERMISSÃO, SEM GATE
   * =========================
   * O botão já foi captura de tela (`getDisplayMedia`) — e aí o browser
   * mostrava o pedido "Permitir que o app tenha acesso a essa guia?", que
   * nenhuma página pode suprimir. O contorno foi trocar a captura por
   * rasterização do DOM: `selecionar()` abre o retângulo sobre a própria
   * página e gera uma IMAGEM da área, que a IA da nuvem vê de verdade
   * (nada de OCR, nada de texto extraído). Não há pedido porque não há
   * nada para autorizar — por isso aqui não há mais gate de ambiente.
   *
   * A FALHA TEM DE SE VER (vale como antes): a área vazia ou pequena é dita
   * pelo `selecionar()` via `IaDizer`, e não aqui — dizer nos dois sítios
   * era falar duas vezes do mesmo erro. */
  window.iaSelecionarArea = function () {
    if (!window.IaPrint || typeof window.IaPrint.selecionar !== 'function') {
      fala(
        'O seletor de área ainda não carregou nesta página. Recarrega (Ctrl+F5) e tenta outra vez.',
        true
      );
      return;
    }
    return window.IaPrint.selecionar();
  };

  /* ── 2. IMPORTAR DOCUMENTO ────────────────────────────────────────────────
   *
   * O QUE ESTE BOTÃO ACEITA, E O QUE NÃO ACEITA
   * =============================================
   * A leitura é a que o servidor já faz (`app/ia/ingestao/`), e ela é honesta
   * sobre o que sabe ler:
   *
   *   foto (jpg/png/webp) -> OCR (tesseract). Sem tesseract no servidor, a
   *                          resposta DIZ que não leu — não devolve vazio.
   *   NFe em XML          -> estruturado, confiança 1.0, sem OCR.
   *   texto / CSV         -> enviado como texto, e lido pela heurística
   *                          "NOME quantidade unidade" linha a linha.
   *   PDF, XLSX           -> NÃO são lidos. `ocr.py` recusa o PDF com uma
   *                          mensagem que explica porquê; o XLSX nem chega a ser
   *                          reconhecido como imagem.
   *
   * Um botão de importação que aceita `.pdf` e depois devolve "não consegui" é
   * um botão que mente sobre o que sabe fazer. O `accept` abaixo é a lista
   * verdadeira, e o que não está nela é recusado ANTES de haver ficheiro
   * escolhido — que é o momento em que a decepção é mais barata.
   */
  var ACEITA = '.png,.jpg,.jpeg,.webp,.gif,.xml,.csv,.txt';

  function escolheFicheiro() {
    var inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = ACEITA;
    inp.style.display = 'none';
    document.body.appendChild(inp);
    inp.addEventListener('change', function () {
      var f = inp.files && inp.files[0];
      inp.remove();
      if (!f) return;
      mandaParaLeitura(f);
    });
    /* Safari e Firefox só abrem o diálogo a partir de um gesto do utilizador. */
    inp.click();
  }

  function mandaParaLeitura(ficheiro) {
    var nome = ficheiro.name || 'documento';
    var eNfeXml = /\.xml$/i.test(nome);

    /* Texto não é binário: o `texto` do corpo é o caminho certo, e mandá-lo
     * como ficheiro faz o OCR tentar abrir um CSV como imagem — que é a
     * degradação que `ocr.py` já descreve, e que aqui seria nossa. */
    if (!eNfeXml && /\.(csv|txt)$/i.test(nome)) {
      var leitor = new FileReader();
      leitor.onload = function () {
        fala('A ler ' + nome + '…', true);
        window.iaEnviarTextoParaLeitura(String(leitor.result || ''), nome);
      };
      leitor.onerror = function () {
        fala('Não consegui abrir ' + nome + ' neste navegador.', true);
      };
      leitor.readAsText(ficheiro);
      return;
    }

    if (eNfeXml) {
      /* O XML VAI como ficheiro: `views.py:imagem_estoque` chama
       * `parece_nfe_xml` sobre os bytes, e mandá-lo como texto perderia
       * precisamente o que o tornafiável. */
      fala('A ler a nota ' + nome + '…', true);
    } else {
      fala('A ler a foto ' + nome + '…', true);
    }
    window.iaDockImageComFicheiro(ficheiro);
  }

  window.iaImportarDocumento = function () {
    escolheFicheiro();
  };

  /* ── 3–4. NOVA CONVERSA E HISTÓRICO ───────────────────────────────────────
   *
   * `iaChatReset` NÃO vive aqui. Ele vive no template (`ia_dock.html`), e é o
   * que limpa o histórico, o `localStorage`, o corpo da conversa e a lista de
   * campos.
   *
   * MEDIDO: havia aqui uma segunda cópia que só fechava a janela e limpava o
   * input. Como este módulo é carregado depois do template, ela SOBRESCREVIA o
   * reset verdadeiro — e o botão "Nova conversa" da barra fechava o painel sem
   * apagar nada. Para quem usa a barra, "nova conversa" era um botão que não
   * fazia nova conversa nenhuma.
   *
   * `ia_dock.html` também chama `iaChatReset()` no cabeçalho. Uma função, dois
   * sítios, nenhuma divergência possível.
   *
   * E O HISTÓRICO, que é o que estava partido
   * =========================================
   * MEDIDO 2026-10-10: o botão dizia "Ainda não há conversa para ver" com
   * conversa no ecrã. Lia `iaHist` — um `let` do `<script type="module">` do
   * `ia_dock.html`, e este ficheiro é OUTRO módulo. `typeof iaHist` do lado de
   * cá é `'undefined'` sempre, e a guarda calava o resto: o botão não funcionava
   * e não dizia porquê.
   *
   * Agora lê `window.IaSessoes` (`ia-sessoes.js`), que é onde as conversas
   * vivem, e DESENHA a lista em vez de a despejar em texto. A diferença é a
   * que o produtor sente: despejar a conversa em cima do que ele estava a ler
   * não é consultar o histórico, é perder o que estava a ver.
   */

  var NOMES_SECAO = {
    '/': 'Painel',
    '/financeiro': 'Financeiro',
    '/estoque': 'Estoque',
    '/agenda': 'Agenda',
    '/vendas': 'Vendas',
    '/pecuaria': 'Pecuária',
    '/apiario': 'Apiário',
    '/maquinarios': 'Maquinários',
    '/compras': 'Compras',
    '/visao-geral': 'Visão Geral',
    '/gestão': 'Gestão',
  };

  function nomeDaSecao(caminho) {
    var p = String(caminho || '/');
    if (NOMES_SECAO[p]) return NOMES_SECAO[p];
    var partes = p.split('/').filter(Boolean);
    var ultima = partes.length ? partes[partes.length - 1] : 'Painel';
    return ultima.replace(/[-_]/g, ' ').replace(/\b\w/g, function (c) {
      return c.toUpperCase();
    });
  }

  function dataCurta(ms) {
    if (!ms) return '';
    var d = new Date(ms);
    var hoje = new Date();
    var mesmoDia =
      d.getDate() === hoje.getDate() &&
      d.getMonth() === hoje.getMonth() &&
      d.getFullYear() === hoje.getFullYear();
    if (mesmoDia) {
      return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
    }
    return ('0' + d.getDate()).slice(-2) + '/' + ('0' + (d.getMonth() + 1)).slice(-2);
  }

  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* Uma linha da lista.
   *
   * Sem `onclick` inline: os ids são gerados, e um id com apóstrofo ou aspas
   * dentro de um atributo HTML parte a linha — e a lista inteira com ela. O
   * `data-id` mais um listener é o que aguenta qualquer nome. */
  function linhaSessao(s, atual) {
    var titulo = s.titulo || 'Nova conversa';
    var quantas = (s.mensagens || []).length;
    return (
      '<div class="ia-hist-linha' +
      (atual ? ' ia-hist-atual' : '') +
      '" data-id="' +
      escHtml(s.id) +
      '" role="button" tabindex="0" title="' +
      escHtml(atual ? 'Conversa aberta agora' : 'Voltar a esta conversa') +
      '">' +
      '<div class="ia-hist-texto">' +
      '<span class="ia-hist-titulo">' +
      escHtml(titulo) +
      '</span>' +
      '<span class="ia-hist-meta">' +
      dataCurta(s.atualizada || s.criada) +
      (quantas ? ' · ' + quantas + ' mensagens' : ' · vazia') +
      (atual ? ' · aberta' : '') +
      '</span>' +
      '</div>' +
      '<button type="button" class="ia-hist-apagar" data-apagar="' +
      escHtml(s.id) +
      '" title="Apagar esta conversa" aria-label="Apagar">×</button>' +
      '</div>'
    );
  }

  function fechaPainel() {
    var p = document.getElementById('ia-historico');
    if (p) p.remove();
  }

  /* O painel vive DENTRO do chat, e não no `body`.
   *
   * O `#ia-chat` é `position:fixed` com o seu próprio `overflow`, e um painel
   * solto no body ficaria atrás dele ou fora do ecrã. Dentro, herda o
   * posicionamento e o scroll do chat — que é onde o produtor está a olhar. */
  function desenhaPainel() {
    fechaPainel();
    var chat = document.getElementById('ia-chat');
    if (!chat) return null;
    var sessoes = window.IaSessoes.listar();
    var idAtual = window.IaSessoes.atual();
    idAtual = idAtual ? idAtual.id : null;

    var p = document.createElement('div');
    p.id = 'ia-historico';
    p.className = 'ia-historico';
    p.innerHTML =
      '<div class="ia-hist-topo">' +
      '<span>Conversas — ' +
      escHtml(nomeDaSecao(window.IaSessoes.secao())) +
      '</span>' +
      '<button type="button" class="ia-hist-fechar" title="Fechar" aria-label="Fechar">×</button>' +
      '</div>' +
      '<div class="ia-hist-lista">' +
      (sessoes.length
        ? sessoes
            .map(function (s) {
              return linhaSessao(s, s.id === idAtual);
            })
            .join('')
        : '<div class="ia-hist-vazio">Ainda não há conversa nesta secção.</div>') +
      '</div>';
    chat.appendChild(p);

    p.querySelector('.ia-hist-fechar').addEventListener('click', fechaPainel);

    p.querySelectorAll('[data-apagar]').forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = b.getAttribute('data-apagar');
        window.IaSessoes.apagar(id);
        /* Se apagou a conversa que estava no ecrã, o ecrã tem de mudar:
           mostrar mensagens que já não existem é mentir. */
        if (window.IaDock) {
          var agora = window.IaSessoes.atual();
          window.IaDock.aplicar(agora ? agora.mensagens : []);
        }
        desenhaPainel();
      });
    });

    p.querySelectorAll('.ia-hist-linha').forEach(function (l) {
      function abrir() {
        var id = l.getAttribute('data-id');
        var msgs = window.IaSessoes.restaurar(id);
        if (msgs === null) {
          fala('Esta conversa já não existe.', true);
          desenhaPainel();
          return;
        }
        if (window.IaDock) window.IaDock.aplicar(msgs);
        fechaPainel();
        fala('Conversa aberta de novo.', true);
      }
      l.addEventListener('click', abrir);
      l.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          abrir();
        }
      });
    });
    return p;
  }

  window.iaHistorico = function () {
    if (!window.IaSessoes) {
      fala('O histórico não carregou nesta página. Recarrega (Ctrl+F5) e tenta outra vez.', true);
      return;
    }
    if (!window.IaDock) {
      fala('A conversa não carregou nesta página. Recarrega (Ctrl+F5) e tenta outra vez.', true);
      return;
    }
    var existente = document.getElementById('ia-historico');
    if (existente) {
      fechaPainel();
      return;
    }
    if (!window.IaSessoes.listar().length) {
      fala(
        'Ainda não há conversa guardada em ' + nomeDaSecao(window.IaSessoes.secao()) + '.',
        true
      );
      return;
    }
    /* `iaDockAbrir()`, e NAO `classList.add('open')`: abrir o chat sem tirar
     * a barra do `display:none` deixava a janela sem ferramentas. */
    if (!document.getElementById('ia-chat').classList.contains('open')) {
      if (typeof window.iaDockAbrir === 'function') window.iaDockAbrir();
      else document.getElementById('ia-chat').classList.add('open');
    }
    desenhaPainel();
  };

  window.iaExportarConversa = function () {
    /* `window.IaDock`, e NÃO `iaHist`. O `iaHist` é um `let` do módulo do
       `ia_dock.html`; aqui, noutro módulo, `typeof iaHist` era `'undefined'`
       para sempre e a exportação dizia "não há conversa" com conversa no ecrã.
       MEDIDO 2026-10-10. */
    var h = window.IaDock && window.IaDock.mensagens ? window.IaDock.mensagens() : [];
    if (!h.length) {
      fala('Não há conversa para exportar.', true);
      return;
    }
    var txt =
      'Conversa com a AmplIA\nExportado em ' +
      new Date().toLocaleString('pt-BR') +
      '\n\n' +
      h
        .map(function (m) {
          return (m.role === 'user' ? 'Você' : 'AmplIA') + ': ' + String(m.content || '');
        })
        .join('\n\n');
    var a = document.createElement('a');
    a.href = 'data:text/plain;charset=utf-8,' + encodeURIComponent(txt);
    a.download = 'conversa-amplia.txt';
    a.click();
    fala('Conversa exportada para "conversa-amplia.txt".', true);
  };

  /* ── RELATAR PROBLEMA ─────────────────────────────────────────────────────
   * Local de propósito. Um relatório que depende do servidor não chega ao
   * servidor quando é o servidor que está avariado — e o dia em que mais
   * preciso de um relatório é precisamente esse.
   */
  window.iaRelatarBug = function () {
    var info = [];
    info.push('Navegador: ' + navigator.userAgent);
    info.push('Data: ' + new Date().toString());
    info.push('Ecrã: ' + window.innerWidth + 'x' + window.innerHeight);
    var e = document.querySelector('.ia-msg.bot:last-child');
    if (e) info.push('Última resposta: ' + e.innerText.slice(0, 400));
    var corpo = 'Relatório de problema\n\n' + info.join('\n') + '\n\nDescreva o que aconteceu:\n\n';
    var href =
      'mailto:?subject=' +
      encodeURIComponent('Problema no AmplIA') +
      '&body=' +
      encodeURIComponent(corpo);
    window.location.href = href;
    fala(
      'Abri o seu programa de email com o relatório preparado — escreva o que aconteceu e envie.',
      true
    );
  };

  /* ── AS CHAVES SELETORAS E O AGENTE DA NUVEM ─────────────────────────────
   *
   * O PEDIDO DO PRODUTOR
   * ===================
   * \"Criar no painel\" e \"criar no dashboard\" não são menus de escolha — são
   * chaves seletoras de ligado/desligado. Ligadas, FORÇAM a IA a responder
   * nesses locais, de forma personalizada e menos textual: peça, não prosa.
   *
   * A directiva que faz o força vive em `ia-modos.js` e é injectada em cada
   * pergunta pelo `iaDockSend`. O que esta acção faz é só o INTERRUPTOR:
   * liga/desliga o modo na loja, sincroniza o desenho, e diz ao produtor o
   * que mudou — que é a confirmação de que o clique valeu.
   *
   * `pede()` fica: é a via que o resto do produto usa, e a engrenagem do
   * agente da nuvem usa-a para explicar o que a chave faz.
   */
  function pede(texto, seNaoHouver) {
    var C = window.AmpliaChamado;
    if (!C || typeof C.pedirChat !== 'function') {
      fala(seNaoHouver, true);
      return;
    }
    var r = C.pedirChat(texto);
    if (!r || r.ok !== true) {
      fala(
        'Esta página não tem a conversa da AmplIA aberta, e é por ela que a peça é montada. Abra a conversa e clique outra vez.',
        true
      );
    }
  }

  /* Ligar/desligar um modo de criação.
   *
   * Recebe o NOME DO MODO ('chat' ou 'painel'), e não o id do botão: o id é
   * 'criar-no-chat' e o modo é 'chat'. O `IaRail.passar` faz essa tradução. */
  window.iaAlternarModo = function (qual) {
    if (!window.IaModos) {
      fala('Os modos de criação não carregaram nesta página. Recarrega (Ctrl+F5).', true);
      return;
    }
    var ligado = window.IaModos.alternar(qual);
    /* O interruptor desenhado segue a loja. O `IaRail` pode ainda não ter
     * carregado (módulo diferido) — nesse caso o `monta()` sincroniza no
     * momento em que desenhar. */
    if (window.IaRail && typeof window.IaRail.sincronizaChaves === 'function') {
      try {
        window.IaRail.sincronizaChaves();
      } catch (e) {}
    }
    /* SEM mensagem no chat: ligar/desligar é gesto mudo. A confirmação é
     * VISUAL — a borda verde e o pino do interruptor (`ia-rail.css`). Falar
     * a cada clique enchia a conversa de "LIGADO/desligado" e empurrava a
     * resposta de verdade para cima. A directiva continua a entrar em cada
     * pergunta pelo `systemContent` (`ia-local.js:raciocinarLlm`). */
    /* Ligado, a conversa tem de estar aberta: a directiva injecta-se em cada
     * pergunta, e uma directiva numa conversa fechada é uma directiva que
     * ninguém vê. */
    if (ligado) {
      var chat = document.getElementById('ia-chat');
      if (chat && !chat.classList.contains('open')) {
        if (typeof window.iaDockAbrir === 'function') window.iaDockAbrir();
        else chat.classList.add('open');
      }
    }
  };

  /* A ENGRENAGEM — o painel do agente da nuvem.
   *
   * Fica no fundo da barra, e é onde o produtor registra a chave da API do
   * Gemini. O painel vive em `ia-chave.js` (mesma doutrina do `ia-print.js`:
   * o módulo que desenha é o módulo que testa). Aqui fica só a ponte — e a
   * RECUSA quando o módulo não carregou, porque um botão que aceita o clique
   * e não faz nada é pior do que um botão que diz que não carregou. */
  window.iaAbrirChave = function () {
    if (!window.IaChave || typeof window.IaChave.abrir !== 'function') {
      fala(
        'O painel do agente da nuvem não carregou nesta página. Recarrega (Ctrl+F5) e tenta outra vez.',
        true
      );
      return;
    }
    window.IaChave.abrir();
  };

  /* EXPANDIR/GUARDAR A BARRA — o primeiro item dela (`alternar-barra`, icone
   * `bi-layout-sidebar`).
   *
   * Mora AQUI, e nao no template: `itemHTML` so' ativa um botao cuja funcao
   * existe quando o desenha, e o template e' outro ficheiro que os testes de
   * DOM nao executam — sem isto o botao saia cinzento sem onclick. E' tambem o
   * sitio das outras accoes da barra.
   *
   * Guarda e' CLASSE, nunca hover: a rail abre com `.aberta` (212px) e some por
   * completo com `.ia-rail-guardada` (display:none — sem lasca na tela). */
  window.iaRailToggle = function () {
    var rail = document.getElementById('ia-rail');
    if (!rail || rail.classList.contains('ia-rail-guardada')) return;
    var aberta = !rail.classList.contains('aberta');
    rail.classList.toggle('aberta', aberta);
    /* O rotulo do item ("Expandir"/"Guardar") anda com a classe. `IaRail` vem
     * de `ia-rail.js`, que carrega DEPOIS deste ficheiro — por isso a guarda,
     * e nao chamada direta: um clique antes de ele carregar nao pode rebentar. */
    if (window.IaRail && typeof window.IaRail.sincronizaAlternar === 'function') {
      try {
        window.IaRail.sincronizaAlternar();
      } catch (e) {}
    }
  };

  /* O que fica exposto daqui.
   *
   * `AREA`, `cancelaArea` e `pngDaArea` saíram com a marcação de rectângulo: o
   * rectângulo passou a viver dentro do overlay de `ia-print.js`, e o que lá
   * está é a superfície do vídeo, não coordenadas de página. Deixar aqui uma
   * `pngDaArea` que aponta para um bloco que já não existe seria um botão morto
   * que só descobria quem o chamasse. */
  window.IaFerramentas = {
    fala: fala,
    printActual: function () {
      return window.IaPrint ? window.IaPrint.actual() : null;
    },
  };
})();
