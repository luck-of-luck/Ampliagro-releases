/* A barra lateral do AmplIA: ícones que ganham o nome ao expandir.
 *
 * O PRODUTOR VÊ O NOME, OU NÃO VÊ NADA
 * ======================================
 * Uma barra só de ícones obriga a decorar. O produtor do Ampliagro está de pé
 * num talhão, com uma bota e o celular numa mão; o polegar não é cursor, e
 * adivinhar o que um ícone de 20px significa é trabalho, não atalho. Por isso
 * cada item é `ícone + nome`, e o nome cresce de `max-width:0` quando a barra
 * abre. O ícone continua lá em cima — quem conhece não perde nada, e quem não
 * conhece não tem de adivinhar.
 *
 * O QUE ESTE MÓDULO NÃO INVENTA
 * ==============================
 * Cada item aponta para uma função que JÁ EXISTE, em `ia-rail-acoes.js` ou no
 * template. Um botão que parece funcionar e não faz nada é pior do que a
 * ausência dele: o produtor clica, nada acontece, e conclui que a IA está
 * avariada — a mesma razão pela qual uma recusa tem sempre motivo
 * (`app/ia/chamado.py`).
 *
 * Por isso um item tem `accao` OU `menu`, e o `itemHTML` desliga o que não
 * tem nenhum dos dois. Não há aqui uma lista do que "ainda não existe": se um
 * dia entrar um item sem função, ele sai cinzento e a dica diz porquê.
 *
 * A LISTA DE CAMPOS
 * =================
 * O `sandbox` devolve `dados.coleta` em `COLETANDO_DADOS`: os campos do pedido,
 * na ordem, com o que já foi preenchido. Esta parte desenha isso. Não volta a
 * perguntar nada — o texto da pergunta continua a vir no `resposta`, e o cliente
 * MCP e o telefone leem esse.
 */

(function () {
  'use strict';

  var SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">';
  var FIM = '</svg>';

  function ic(corpo) {
    return SVG + corpo + FIM;
  }

  /* Os itens de topo — o primeiro e' o expandir/guardar da propria barra.
   *
   * A ordem e' a que o produtor usa: primeiro o que abre/fecha a lista, depois
   * o que da INFORMACAO a IA (ver a tela, dar-lhe um documento), a seguir o que
   * controla a conversa, e so no fim o que produz pecas. Um separador entre os
   * grupos e' o que impede uma lista de icones iguais de virar uma lista sem
   * lugares.
   *
   * O PRIMEIRO item e' o expandir/guardar da propria barra (`alternar-barra`,
   * icone `bi-layout-sidebar` do pedido do produtor). E' item da lista — e
   * nao botao solto no cabecalho — para viver DENTRO da rail, no topo dela, e
   * ir junto quando ela guarda (`display:none` some tudo, sem lasca). */
  var ITENS = [
    {
      id: 'alternar-barra',
      rotulo: 'Expandir ferramentas',
      dica: 'Mostra ou esconde o nome das ferramentas.',
      /* O `bi-layout-sidebar` EXATO do pedido do produtor — `<svg>` completo,
       * e nao o `ic()` da casa: o `ic()` embrulha em viewBox 24 com
       * `fill="none" stroke=...`, e este desenho e' 16x16 com
       * `fill="currentColor"` (moldura cheia com a divisoria da lateral). Pô-lo
       * dentro do embrulho errado encolhia o traco e virava contorno. O CSS
       * `.ia-rail-item svg` (20px) escala o viewBox 16 sem mexer no desenho. */
      icone:
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-layout-sidebar" viewBox="0 0 16 16">' +
        '<path d="M0 3a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm5-1v12h9a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1zM4 2H2a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h2z"/>' +
        '</svg>',
      accao: 'iaRailToggle',
    },
    { sep: 1 },
    {
      id: 'selecionar-area',
      rotulo: 'Selecionar área',
      dica: 'Arraste na página a área que a IA vai ver em imagem. Sem permissão, sem sair daqui. Atalho: Alt+A.',
      icone: ic(
        '<path d="M3 7V5a2 2 0 0 1 2-2h2"></path><path d="M17 3h2a2 2 0 0 1 2 2v2"></path><path d="M21 17v2a2 2 0 0 1-2 2h-2"></path><path d="M7 21H5a2 2 0 0 1-2-2v-2"></path><path d="M9 9h6v6H9z"></path>'
      ),
      accao: 'iaSelecionarArea',
    },
    {
      id: 'importar-documento',
      rotulo: 'Importar documento',
      dica: 'Foto de nota, NFe em XML, ou a lista de insumos em texto.',
      icone: ic(
        '<path d="M14 3v5h5"></path><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"></path><path d="M12 18v-6"></path><path d="M9.5 14.5 12 12l2.5 2.5"></path>'
      ),
      accao: 'iaImportarDocumento',
    },
    { sep: 2 },
    {
      id: 'nova-conversa',
      rotulo: 'Nova conversa',
      dica: 'Recomeça sem o que ficou para trás.',
      icone: ic('<path d="M12 5v14"></path><path d="M5 12h14"></path>'),
      accao: 'iaChatReset',
    },
    {
      id: 'historico',
      rotulo: 'Histórico',
      dica: 'O que foi dito nesta conversa.',
      icone: ic(
        '<path d="M3 12a9 9 0 1 0 3-6.7"></path><path d="M3 4v5h5"></path><path d="M12 7v5l3 2"></path>'
      ),
      accao: 'iaHistorico',
    },
    { sep: 3 },
    /* Os dois "criar" são CHAVE SELETORA, e não menu.
     *
     * PEDIDO DO PRODUTOR: "não são menus de escolha, mas sim quando
     * escolhadas forçam a IA a responder nesses locais de forma
     * personalizada e menos textual". Ligada, a chave injecta uma DIRECTIVA
     * em cada pergunta (ver `ia-modos.js`) e a resposta vem como PEÇA —
     * planilha e gráfico no chat, widgets no preset do dashboard.
     *
     * `chave` é o nome do modo na loja; `accao` liga/desliga. */
    {
      id: 'criar-no-chat',
      rotulo: 'Criar no chat',
      dica: 'Ligado, as respostas vêm como peça (planilha/gráfico), não como texto.',
      icone: ic(
        '<path d="M4 5h16v11H8l-4 4z"></path><path d="M8 10.5V15"></path><path d="M12 8v7"></path><path d="M16 11v4"></path>'
      ),
      chave: 'chat',
      accao: 'iaAlternarModo',
    },
    {
      id: 'criar-no-painel',
      rotulo: 'Criar no painel',
      dica: 'Ligado, a resposta aterra no preset do dashboard, com widgets.',
      icone: ic(
        '<rect x="3" y="3" width="7" height="9" rx="1.5"></rect><rect x="14" y="3" width="7" height="5" rx="1.5"></rect><rect x="14" y="12" width="7" height="9" rx="1.5"></rect><rect x="3" y="16" width="7" height="5" rx="1.5"></rect>'
      ),
      chave: 'painel',
      accao: 'iaAlternarModo',
    },
    {
      id: 'usar-nuvem',
      rotulo: 'Usar agente da nuvem',
      dica: 'Ligado, usa a API do Gemini (modelos gratuitos) em vez do motor local.',
      icone: ic(
        '<path d="M21 12.5a4 4 0 0 1-3.5 3.9l-.5.07a6 6 0 1 1-7-7l.1-.12a4 4 0 0 1 6.9 2.15z"></path>' +
          '<path d="M12 12v4a2 2 0 0 0 2 2h5a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2h-5a2 2 0 0 0-2-2V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h5"></path>'
      ),
      chave: 'nuvem',
      accao: 'iaAlternarModo',
    },
    { sep: 4 },
    {
      id: 'exportar',
      rotulo: 'Exportar conversa',
      dica: 'Descarrega esta conversa num ficheiro de texto.',
      icone: ic(
        '<path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path>'
      ),
      accao: 'iaExportarConversa',
    },
    {
      id: 'bug',
      rotulo: 'Relatar problema',
      dica: 'Abre o email com o relatório do seu navegador.',
      icone: ic(
        '<path d="M17 11v6a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-6"></path><path d="M14 11V8a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v3"></path><path d="M18 8v3"></path><path d="M6 8v3"></path><circle cx="12" cy="16" r="1"></circle><circle cx="12" cy="16" r="2"></circle>'
      ),
      accao: 'iaRelatarBug',
    },
    /* A ENGRENAGEM, NO FUNDO DA BARRA — a chave do agente da nuvem.
     *
     * Fica no fundo de propósito: é configuração, não ferramenta de
     * trabalho. Abre o painel onde o produtor registra a chave da API do
     * Gemini e liga o agente da nuvem. */
    {
      id: 'config-ia',
      rotulo: 'Agente da nuvem',
      dica: 'Registrar a chave da API do Gemini e ligar o agente da nuvem.',
      icone: ic(
        '<path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"></path><path d="M12 2v3"></path><path d="M12 19v3"></path><path d="M4.9 4.9l2.1 2.1"></path><path d="M17 17l2.1 2.1"></path><path d="M2 12h3"></path><path d="M19 12h3"></path><path d="M4.9 19.1L7 17"></path><path d="M17 7l2.1-2.1"></path>'
      ),
      accao: 'iaAbrirChave',
    },
  ];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function existe(nome) {
    return typeof window[nome] === 'function';
  }

  /* O botão só diz "activo" se o que ele promete existe.
   *
   * MEDIDO, `menu:true` sem `accao` dava `undefined` em `activo`, o botão
   * saía cinzento e o submenu nunca abria — e o produtor via um botão morto
   * sem nenhuma pista do porquê. */
  function itemHTML(it) {
    if (it.sep) return '<div class="ia-rail-sep"></div>';
    var temChave = Boolean(it.chave);
    var temAccao = Boolean(it.accao);
    var activo = temAccao && existe(it.accao);
    var ligada = temChave && window.IaModos && window.IaModos.activo(it.chave);
    var attrs = ['type="button"'];
    if (activo) {
      /* O nome tem de bater certo com a API exportada no fim deste ficheiro.
       * MEDIDO: o HTML dizia `IaRail.passa` e a API exportava `passar`, e o
       * clique dava `TypeError: window.IaRail.passa is not a function`. O botão
       * ficava activo, o submenu nunca abria, e nada na consola dizia o quê —
       * que é a única pista, e só quem abre a consola a vê. */
      attrs.push('onclick="window.IaRail.passar(\'' + it.id + '\')"');
    } else {
      attrs.push('disabled', 'aria-disabled="true"');
    }
    if (temChave) {
      /* `aria-pressed` é o estado do interruptor. Sem ele, o leitor de ecrã
       * anunciaria um botão comum e o produtor não saberia se o modo está
       * ligado. */
      attrs.push('aria-pressed="' + (ligada ? 'true' : 'false') + '"');
      attrs.push('role="switch"');
    }
    var dica = it.dica || it.rotulo;
    if (!activo) dica = it.rotulo + ' — ainda não existe. ' + dica;
    if (temChave) dica = (ligada ? 'Desligar: ' : 'Ligar: ') + dica;
    return (
      '<button class="ia-rail-item' +
      (temChave ? ' ia-rail-item-chave' : '') +
      (ligada ? ' ia-rail-chave-ligada-item' : '') +
      '" data-id="' +
      esc(it.id) +
      '" ' +
      attrs.join(' ') +
      ' title="' +
      esc(dica) +
      '">' +
      it.icone +
      '<span class="ia-rail-txt">' +
      esc(it.rotulo) +
      '</span>' +
      (temChave
        ? '<span class="ia-rail-chave' +
          (ligada ? ' ia-rail-chave-ligada' : '') +
          '" aria-hidden="true"><span class="ia-rail-chave-knob"></span></span>'
        : '') +
      '</button>'
    );
  }

  function monta(container) {
    container.innerHTML = ITENS.map(itemHTML).join('');
    /* O item expandir/guardar anda com a barra: aberta = "Guardar", fechada =
     * "Expandir". Sem isto o rotulo/dica mentia depois do primeiro clique. */
    iaRailSincronizaItem();
    sincronizaChaves();
  }

  /* O rotulo e a dica do `alternar-barra` seguem a classe `.aberta` da rail.
   * Chama-se no `monta()` e no fim do `iaRailToggle()` (que vive no template
   * porque precisa de existir antes dos modulos carregarem). */
  function iaRailSincronizaItem() {
    var rail = document.getElementById('ia-rail');
    if (!rail) return;
    var aberta = rail.classList.contains('aberta');
    var botao = rail.querySelector('.ia-rail-item[data-id="alternar-barra"]');
    if (!botao) return;
    var rotulo = aberta ? 'Guardar ferramentas' : 'Expandir ferramentas';
    var dica = aberta ? 'Esconde o nome das ferramentas.' : 'Mostra o nome das ferramentas.';
    botao.setAttribute('aria-expanded', aberta ? 'true' : 'false');
    botao.setAttribute('title', dica);
    botao.setAttribute('aria-label', rotulo);
    var txt = botao.querySelector('.ia-rail-txt');
    if (txt) txt.textContent = rotulo;
  }

  /* O interruptor desenhado segue a loja `IaModos`.
   *
   * Chama-se no `monta()` e no fim de cada `iaAlternarModo()`. O interruptor
   * é o reflexo VISÍVEL do `aria-pressed`, e o `aria-pressed` é o estado de
   * verdade — por isso os dois andam juntos, e nunca um sem o outro. */
  function sincronizaChaves() {
    var rail = document.getElementById('ia-rail');
    if (!rail || !window.IaModos) return;
    ITENS.forEach(function (it) {
      if (!it.chave) return;
      var botao = rail.querySelector('.ia-rail-item[data-id="' + it.id + '"]');
      if (!botao) return;
      var ligada = window.IaModos.activo(it.chave);
      botao.setAttribute('aria-pressed', ligada ? 'true' : 'false');
      botao.setAttribute('title', (ligada ? 'Desligar: ' : 'Ligar: ') + (it.dica || it.rotulo));
      var chave = botao.querySelector('.ia-rail-chave');
      if (chave) chave.classList.toggle('ia-rail-chave-ligada', ligada);
      botao.classList.toggle('ia-rail-chave-ligada-item', ligada);
    });
  }

  window.IaRail = {
    passar: function (id) {
      var it = ITENS.filter(function (x) {
        return x.id === id;
      })[0];
      if (!it || !it.accao) return;
      if (!existe(it.accao)) return;
      /* Uma chave seletora recebe o NOME DO MODO, não o id do botão: o id é
       * 'criar-no-chat' e o modo é 'chat'. `iaAlternarModo` fala com a loja
       * pelo nome do modo. */
      if (it.chave) {
        window[it.accao](it.chave);
      } else {
        window[it.accao]();
      }
    },
    monta: monta,
    sincronizaAlternar: iaRailSincronizaItem,
    sincronizaChaves: sincronizaChaves,
    ITENS: ITENS,
  };

  /* ── A LISTA DE CAMPOS ──────────────────────────────────────────────────── */

  function linhaHTML(c) {
    var preenchido = c.estado === 'preenchido';
    var n = '<span class="ia-coleta-n">' + esc(c.n) + '</span>';
    var rot = '<span class="ia-coleta-rotulo">' + esc(c.rotulo || c.campo) + '</span>';
    var direita;
    if (preenchido) {
      direita = '<span class="ia-coleta-valor">' + esc(c.valor) + '</span>';
    } else {
      direita =
        '<span class="ia-coleta-vazio">a responder</span>' +
        '<button type="button" class="ia-coleta-pedindo-btn" onclick="window.IaColeta.responde(\'' +
        esc(c.campo) +
        '\')">Responder</button>';
    }
    return (
      '<div class="ia-coleta-linha' +
      (preenchido ? '' : ' ia-coleta-pedindo') +
      '">' +
      n +
      rot +
      direita +
      '</div>'
    );
  }

  var ultimoCampo = null;

  window.IaColeta = {
    /* Recebe `dados.coleta` do `sandbox` e desenha.
     *
     * Devolve quantos campos faltam, para quem chama saber se ha' mais alguma
     * coisa a fazer. Um desenho que não devolve nada deixa o chamador a adivinhar
     * se desenhou alguma coisa. */
    desenha: function (dados) {
      var corpo = document.getElementById('ia-chat-body');
      if (!corpo) return 0;
      var velho = document.getElementById('ia-coleta-box');
      if (velho) velho.remove();
      var campos = (dados && dados.coleta) || [];
      if (!campos.length) return 0;

      var faltam = 0;
      for (var i = 0; i < campos.length; i++) if (campos[i].estado !== 'preenchido') faltam++;

      var box = document.createElement('div');
      box.id = 'ia-coleta-box';
      box.className = 'ia-coleta';
      box.innerHTML =
        '<div class="ia-coleta-topo">' +
        (faltam
          ? 'A IA precisa de ' + faltam + (faltam === 1 ? ' coisa' : ' coisas')
          : 'Tudo preenchido') +
        '</div>' +
        campos.map(linhaHTML).join('');
      corpo.appendChild(box);
      ultimoCampo =
        campos.filter(function (c) {
          return c.estado !== 'preenchido';
        })[0] || null;
      return faltam;
    },

    /* O botão "Responder" põe o cursor no input e diz qual campo e'.
     *
     * O campo vai no texto porque o `sandbox` le-o de lá: é `dados_coletados`
     * que ele guarda. Escrever o nome do campo no input é o que faz o valor
     * chegar ao sítio certo em vez de virar mais uma palavra solta. */
    responde: function (campo) {
      var inp = document.getElementById('ia-dock-input');
      if (inp) {
        inp.value = String(campo).replace(/_/g, ' ') + ': ';
        inp.focus();
      }
    },
    ultimo: function () {
      return ultimoCampo;
    },

    /* "Nova conversa" chama isto: a lista pertence a um pedido, e uma conversa
     * nova sem pedidos não tem lista nenhuma. Sem isto o produtor recomeça e
     * continua a ver os campos da conversa anterior. */
    limpar: function () {
      ultimoCampo = null;
    },
  };
})();
