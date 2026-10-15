/* SELECIONAR ÁREA — sem pedir nada ao browser, sem permissão de tela.
 *
 * O PRODUTOR ARRASTA E CONFIRMA, E SÓ
 * ===================================
 * Clique em "Selecionar área" -> uma camada transparente cobre a página ->
 * o produtor arrasta o rectângulo sobre o que quer mostrar -> confirma.
 * O que sai É um SVG: a área selecionada, com o documento deslocado para
 * dentro por um `<svg>` aninhado — e esse SVG aparece como miniatura acima
 * do chat. Só na hora de perguntar ele vira PNG (o Gemini só aceita
 * PNG/JPEG), e a IA da NUVEM VÊ de verdade e responde. NADA aqui extrai
 * texto (nada de OCR, nada de innerText): texto não lê gráfico, e fingir
 * que lê é inventar.
 *
 * PORQUE NÃO É MAIS CAPTURA DE TELA (`getDisplayMedia`)
 * =====================================================
 * Capturar a tela exige que o browser mostre o pedido "Permitir que o app
 * tenha acesso a essa guia?" — e esse pedido é do NAVEGADOR, não nosso:
 * nenhuma página web pode o suprimir, é exigência de segurança da spec
 * Screen Capture.
 *
 * O contorno: em vez de fotografar PÍXEIS (que precisa de permissão), a
 * página DESENHA-SE a si mesma — serializa o DOM para SVG
 * (`foreignObject`) e entrega o SVG direto (`svgDaArea`), sem canvas no
 * meio. Sem canvas, não há onde o PNG morria (tinta, memória, limites).
 * Desenhar o próprio DOM não precisa de autorização de ninguém, por isso
 * não há pedido nenhum. O que se perde: nada fora do DOM (outra janela, a
 * barra do sistema). O que se ganha: zero fricção — e texto em vetor,
 * nítido em qualquer zoom.
 *
 * PORQUE NÃO HÁ CAMINHO DE TEXTO
 * ==============================
 * Tentou-se recolher `innerText` da área — e no dashboard não funcionou:
 * os números vivem dentro de `<canvas>` de gráficos, onde não há texto
 * nenhum no DOM para recolher. Tentou-se OCR — e OCR descreve letra, não
 * gráfico: cor, forma e tendência morrem na extração. Imagem lê gráfico;
 * texto não. Por isso a imagem é o ÚNICO caminho (com `<canvas>`
 * convertidos em `<img>` antes de serializar, senão os gráficos saíam em
 * branco). Se a imagem falha, diz-se porquê — não se entrega texto
 * fingindo ser visão.
 *
 * O código antigo de captura (`pedeEcra`, `capturar`, `abreEditor` e o
 * `Pintor`) continua no ficheiro, DORMENTE, para referência — mas o
 * `selecionar()` já não o chama.
 *
 * UM FRAME, E NÃO UM VÍDEO
 * =========================
 * A primeira versão punha o `<video>` do fluxo ao vivo por baixo do overlay, e
 * falhava de duas maneiras — as duas vistas pelo produtor:
 *
 *   - A tela ficava PRETA. Um `MediaStream` atribuído a `video.srcObject` não
 *     começa a tocar só por causa do atributo `autoplay`; é preciso `play()`, e
 *     é preciso esperar por `readyState >= HAVE_CURRENT_DATA` antes de pintar
 *     seja o que for. Sem isso, o overlay mostra o seu fundo preto.
 *
 *   - O overlay podia acabar DENTRO da captura. `getDisplayMedia` na própria
 *     aba mostra a aba como está renderizada — e um overlay a cobertura toda é
 *     parte dessa renderização. Um print com a moldura e o painel de
 *     ferramentas desenhados em cima era o pior dos dois mundos.
 *
 * Por isso: pedir a tela -> UM frame para um canvas -> fechar a pista -> o
 * overlay passa a mostrar esse frame congelado como `<img>`. O que o produtor vê
 * é exactamente o que vai ser recortado, e nada fica a gravar enquanto ele
 * pensa no que quer marcar.
 *
 * O QUE NÃO ESTÁ AQUI, E PORQUÊ
 * ==============================
 * `html2canvas` e `foreignObject` seriam o caminho óbvio, e ambos estão errados:
 * o `foreignObject` não rasteriza em Firefox nem em Safari, não traz o CSS de
 * fora, não traz `<img>` com `crossorigin`, nem canvas — e, o mais grave, não
 * apanha nada que esteja FORA do DOM. Um print da tela que só fotografa a página
 * não é um print da tela.
 *
 * SÓ NA PÁGINA DO AMPLIAAGRO
 * ==========================
 * O pedido é explícito: isto limita-se ao app/pagina do Ampliagro. A guarda é a
 * mesma que o `base.html` usa para esconder a barra de widgets, acrescida da
 * visibilidade da `#dashboard-appbar` — que o `spa.js` alterna ao trocar de aba
 * sem recarregar, e é por isso que o pathname sozinho mentiria.
 *
 * A razão de não capturar noutras páginas não é técnica: o pedido de
 * autorização é mais fácil de aceitar quando se sabe o que se está a autorizar.
 * "Partilhar este ecrã para a AmplIA ler" é concreto; "partilhar ecrã" numa
 * página de importação financeira não é.
 */

(function () {
  'use strict';

  var AREA_MENOR = 8; /* px: abaixo disto é um clique, não uma área */
  var OVERLAY_ID = 'ia-print-overlay';
  var PEGA = 10; /* meio-lado da pega, em px: a zona que "pega" o rato */

  /* ── WELCOME CARD / PRIMEIRO USO ─────────────────────────────────────────────
   *
   * Mostra um card de boas-vindas na primeira vez que o usuário clica em
   * "Selecionar área". O card explica a funcionalidade e oferece a opção de
   * "não mostrar novamente" guardada no localStorage.
   *
   * A chave do localStorage é 'ia_print_welcome_dismissed' = 'true'.
   */

  function welcomeDismissed() {
    try {
      return localStorage.getItem('ia_print_welcome_dismissed') === 'true';
    } catch (e) {
      return false;
    }
  }

  function setWelcomeDismissed(value) {
    try {
      localStorage.setItem('ia_print_welcome_dismissed', value ? 'true' : 'false');
    } catch (e) {}
  }

  function criaWelcomeCard() {
    var card = document.createElement('div');
    card.id = 'ia-print-welcome';
    card.className = 'ia-print-welcome-card';
    card.innerHTML =
      '<div class="ia-print-welcome-header">' +
      '  <div class="ia-print-welcome-icon" aria-hidden="true">' +
      '    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '      <path d="M3 7V5a2 2 0 0 1 2-2h2"></path><path d="M17 3h2a2 2 0 0 1 2 2v2"></path><path d="M21 17v2a2 2 0 0 1-2 2h-2"></path><path d="M7 21H5a2 2 0 0 1-2-2v-2"></path><path d="M9 9h6v6H9z"></path>' +
      '    </svg>' +
      '  </div>' +
      '  <div class="ia-print-welcome-title">Selecionar área da tela</div>' +
      '</div>' +
      '<div class="ia-print-welcome-body">' +
      '  <p>Arraste um <strong>retângulo sobre a página</strong> e eu gero um <strong>SVG da área</strong> — gráficos e números incluídos, nítido em qualquer zoom — sem pedir permissão nenhuma, sem sair daqui.</p>' +
      '  <ul>' +
      '    <li>Arraste o retângulo sobre a área desejada</li>' +
      '    <li>Solte para confirmar (Esc cancela)</li>' +
      '    <li>A imagem aparece num card acima do campo de chat</li>' +
      '    <li>Toque em "Perguntar à IA" — ela VÊ a imagem e responde sobre ela</li>' +
      '    <li>Atalho: <strong>Alt+A</strong> abre a seleção de onde você estiver</li>' +
      '  </ul>' +
      '  <p class="ia-print-welcome-tip">💡 A leitura usa a IA da nuvem (Gemini). Se ela disser que está desligada, é a chave do servidor (GEMINI_API_KEY) que falta — fale com o administrador.</p>' +
      '</div>' +
      '<div class="ia-print-welcome-footer">' +
      '  <label class="ia-print-welcome-checkbox">' +
      '    <input type="checkbox" id="ia-print-welcome-dismiss">' +
      '    <span>Não mostrar novamente</span>' +
      '  </label>' +
      '  <div class="ia-print-welcome-actions">' +
      '    <button type="button" class="ia-print-welcome-btn ia-print-welcome-btn-secondary" id="ia-print-welcome-cancel">Cancelar</button>' +
      '    <button type="button" class="ia-print-welcome-btn ia-print-welcome-btn-primary" id="ia-print-welcome-continue">Entendi, continuar</button>' +
      '  </div>' +
      '</div>';

    return card;
  }

  function mostraWelcomeCard(resolve) {
    if (welcomeDismissed()) {
      resolve({ showWelcome: false });
      return;
    }

    var card = criaWelcomeCard();
    var overlay = document.createElement('div');
    overlay.id = 'ia-print-welcome-overlay';
    overlay.className = 'ia-print-welcome-overlay';
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    // Focus trap simples - foca no botão principal
    setTimeout(function () {
      var btn = card.querySelector('#ia-print-welcome-continue');
      if (btn) btn.focus();
    }, 50);

    card.querySelector('#ia-print-welcome-continue').addEventListener('click', function () {
      var checkbox = card.querySelector('#ia-print-welcome-dismiss');
      if (checkbox && checkbox.checked) setWelcomeDismissed(true);
      fechaWelcomeCard(overlay);
      resolve({ showWelcome: true, dismissed: checkbox.checked });
    });

    card.querySelector('#ia-print-welcome-cancel').addEventListener('click', function () {
      var checkbox = card.querySelector('#ia-print-welcome-dismiss');
      if (checkbox && checkbox.checked) setWelcomeDismissed(true);
      fechaWelcomeCard(overlay);
      resolve({ showWelcome: true, cancelled: true });
    });

    // ESC para fechar
    function onEsc(e) {
      if (e.key === 'Escape') {
        document.removeEventListener('keydown', onEsc);
        var checkbox = card.querySelector('#ia-print-welcome-dismiss');
        if (checkbox && checkbox.checked) setWelcomeDismissed(true);
        fechaWelcomeCard(overlay);
        resolve({ showWelcome: true, cancelled: true });
      }
    }
    document.addEventListener('keydown', onEsc);

    // Click no overlay para fechar (opcional - apenas se não for no card)
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        document.removeEventListener('keydown', onEsc);
        var checkbox = card.querySelector('#ia-print-welcome-dismiss');
        if (checkbox && checkbox.checked) setWelcomeDismissed(true);
        fechaWelcomeCard(overlay);
        resolve({ showWelcome: true, cancelled: true });
      }
    });
  }

  function fechaWelcomeCard(overlay) {
    if (overlay && overlay.parentNode) {
      overlay.classList.add('ia-print-welcome-hiding');
      setTimeout(function () {
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      }, 200);
    }
  }

  /* As cores. Vermelho é o que o produtor já conhece do Word e do Windows, e
   * uma ferramenta que ninguém reconhece é uma ferramenta que ninguém usa. */
  var CORES = {
    vermelho: '#ef4444',
    amarelo: '#f59e0b',
    azul: '#3b82f6',
  };
  var LARGURA_PIN = 4;

  /* ── A GUARDA DE PÁGINA ──────────────────────────────────────────────────── */

  /* Estar no app do Ampliagro, e não noutra página do mesmo servidor.
   *
   * `#dashboard-appbar` EXISTE em todas as páginas — o `base.html` inclui-a
   * sempre e esconde-a por JavaScript. Por isso "existe" não diz nada; o que
   * diz é se está a MOSTRAR. */
  function ePaginaDoAmpliagro() {
    var appbar = document.getElementById('dashboard-appbar');
    if (!appbar) return false;
    if (appbar.style.getPropertyValue('display') === 'none') return false;

    var p = window.location ? window.location.pathname : '';
    return p === '/' || p === '' || p === '/dashboard/' || p.indexOf('index') > -1;
  }

  function suportado() {
    return Boolean(
      navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === 'function'
    );
  }

  /* Sem captura de tela, não há o que recusar: ler o DOM da própria página
   * não pede permissão, não exige https nem navegador específico. A função
   * continua a existir porque `ia-rail-acoes.js` a consulta antes de chamar
   * `selecionar()` — e resposta vazia significa "pode seguir". */
  function motivoDaRecusa() {
    return '';
  }

  /* ── PEDIR A TELA ──────────────────────────────────────────────────────────
   *
   * `displaySurface` vai NO TOPO, não dentro de `video`.
   *
   * A Screen Capture spec põe `displaySurface`, `surfaceSwitching` e
   * `selfBrowserSurface` em `DisplayMediaStreamOptions` — no objeto de topo. Em
   * `video` são chaves desconhecidas, e um browser estrito lança `TypeError` a
   * construir as restrições. O Chrome é tolerante e por isso isto nunca
   * apareceu aqui; em produção é no Firefox que o produtor vai bater com ele.
   *
   * E `displaySurface` é um FILTRO, não uma dica: `displaySurface:'browser'`
   * proíbe capturar o ecrã inteiro. Deixa-se de fora, e quem quiser escolher
   * escolhe no painel do browser. */
  function pedeEcra() {
    return navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: false,
      preferCurrentTab: true,
      selfBrowserSurface: 'include',
      surfaceSwitching: 'include',
    });
  }

  /* Espera o vídeo ter um frame DECENTE.
   *
   * `loadedmetadata` chega antes de haver imagem, e pintar antes disso é pintar
   * preto. O alarme existe para o caso de o browser nunca dar o frame: sem ele,
   * esta promessa não resolve e o overlay fica preto para sempre. */
  function esperaFrame(video, limiteMs) {
    return new Promise(function (resolve) {
      var feito = false;
      var sair = function () {
        if (feito) return;
        feito = true;
        clearTimeout(alarme);
        resolve();
      };
      var alarme = setTimeout(sair, limiteMs || 4000);

      /* `play()` é obrigatório: `autoplay` não arranca um `MediaStream` que
       * acabou de ser atribuído. E um play recusado não é um problema — o
       * browser já está a mostrar o frame — por isso o `catch` é vazio. */
      var tentativa = video.play();
      if (tentativa && typeof tentativa.catch === 'function') tentativa.catch(function () {});

      var aceitavel = function () {
        if (video.readyState >= 2 && video.videoWidth > 0) sair();
      };
      video.addEventListener('loadeddata', aceitavel);
      video.addEventListener('canplay', aceitavel);
      video.addEventListener('resize', aceitavel);
      aceitavel();
    });
  }

  /* O frame vai para um CANVAS e é ele que fica por todo o lado — não uma
   * string de PNG.
   *
   * Guardar a string e voltar a carregá-la num `new Image()` no fim seria
   * trabalho a mais e uma falha a mais: o `onload` de uma imagem só dispara
   * quando o browser a descodifica, e um print que depende disso tem uma
   * dependência que ninguém pediu. O canvas já tem os píxeis — desenhou-os o
   * browser — e recorte é um `drawImage` a partir dele. */
  function frameParaCanvas(video, w, h) {
    try {
      var c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      c.getContext('2d').drawImage(video, 0, 0, w, h);
      return c;
    } catch (e) {
      return null;
    }
  }

  /* ── GEOMETRIA ──────────────────────────────────────────────────────────── */

  function rectDe(a, b) {
    return {
      left: Math.min(a.x, b.x),
      top: Math.min(a.y, b.y),
      width: Math.abs(b.x - a.x),
      height: Math.abs(b.y - a.y),
    };
  }

  function dentro(r, x, y) {
    return x >= r.left && x <= r.left + r.width && y >= r.top && y <= r.top + r.height;
  }

  /* As oito pegas. Os lados são as chaves, e o que fica de fora é o que o rato
   * NÃO pode arrastar — uma pega que aparece onde não se mexe é uma pega que
   * atrapalha mais do que ajuda. */
  var ORDEM_PEGAS = ['ne', 'nw', 'se', 'sw', 'n', 's', 'w', 'e'];

  function pegasDe(r) {
    var cx = r.left + r.width / 2;
    var cy = r.top + r.height / 2;
    var todas = {
      ne: { x: r.left + r.width, y: r.top },
      nw: { x: r.left, y: r.top },
      se: { x: r.left + r.width, y: r.top + r.height },
      sw: { x: r.left, y: r.top + r.height },
      n: { x: cx, y: r.top },
      s: { x: cx, y: r.top + r.height },
      w: { x: r.left, y: cy },
      e: { x: r.left + r.width, y: cy },
    };
    return ORDEM_PEGAS.map(function (lado) {
      return { lado: lado, x: todas[lado].x, y: todas[lado].y };
    });
  }

  function pegaPerto(r, x, y) {
    var pegas = pegasDe(r);
    for (var i = 0; i < pegas.length; i++) {
      if (Math.abs(x - pegas[i].x) <= PEGA && Math.abs(y - pegas[i].y) <= PEGA) {
        return pegas[i].lado;
      }
    }
    return '';
  }

  /* Ajusta o rectângulo a uma pega.
   *
   * Sem o `if (novo.width < 0)`, arrastar a pega do canto norte para lá do
   * oeste dá largura negativa, o browser recusa a propriedade e a caixa fica
   * presa no sítio onde estava. O `Math.abs` com o deslocamento do `left` é o
   * que faz a pega inverter sem saltar. */
  function redimensiona(r, lado, x, y) {
    var novo = { left: r.left, top: r.top, width: r.width, height: r.height };
    if (lado.indexOf('n') >= 0) {
      novo.top = y;
      novo.height = r.top + r.height - y;
    }
    if (lado.indexOf('s') >= 0) {
      novo.height = y - r.top;
    }
    if (lado.indexOf('w') >= 0) {
      novo.left = x;
      novo.width = r.left + r.width - x;
    }
    if (lado.indexOf('e') >= 0) {
      novo.width = x - r.left;
    }
    if (novo.width < 0) {
      novo.left += novo.width;
      novo.width = -novo.width;
    }
    if (novo.height < 0) {
      novo.top += novo.height;
      novo.height = -novo.height;
    }
    return novo;
  }

  /* ── O PINTOR ──────────────────────────────────────────────────────────────
   *
   * O canvas cobre a TELA INTEIRA e as marcas ficam em píxeis do vídeo. Duas
   * consequências, ambas desejadas:
   *
   *   - não há nada para redimensionar quando a selecção muda: a marca fica
   *     onde foi feita e mudar a selecção só muda o que é recortado;
   *   - as marcas não esticam com a caixa, que é o que acontece quando o canvas
   *     é do tamanho da selecção.
   *
   * A PINTA é uma linha por segmento, sem `quadraticCurveTo`: a curva passa pelo
   * meio de dois traços e altera o que foi escrito, e num print onde o produtor
   * está a apontar números, alterar a marca dele é inaceitável.
   */
  function Pintor(canvas, escalaX, escalaY) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.cx = escalaX;
    this.cy = escalaY;
    this.tracos = [];
    this.a_retracar();
  }

  Pintor.prototype.desenhaUm = function (ctx, t) {
    var p = t.pontos;
    if (!p.length) return;
    var ex = this.cx;
    var ey = this.cy;

    ctx.strokeStyle = t.cor;
    ctx.fillStyle = t.cor;
    ctx.lineWidth = t.largura * ex;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (t.forma === 'seta' && p.length >= 2) {
      var a = p[0];
      var b = p[p.length - 1];
      var ang = Math.atan2(b.y - a.y, b.x - a.x);
      var comp = Math.max(14, t.largura * 5);
      ctx.beginPath();
      ctx.moveTo(a.x * ex, a.y * ey);
      ctx.lineTo(b.x * ex, b.y * ey);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(b.x * ex, b.y * ey);
      ctx.lineTo((b.x - comp * Math.cos(ang - 0.4)) * ex, (b.y - comp * Math.sin(ang - 0.4)) * ey);
      ctx.lineTo((b.x - comp * Math.cos(ang + 0.4)) * ex, (b.y - comp * Math.sin(ang + 0.4)) * ey);
      ctx.closePath();
      ctx.fill();
      return;
    }

    if (t.forma === 'caixa' && p.length >= 2) {
      var q = p[0];
      var r = p[p.length - 1];
      ctx.strokeRect(
        Math.min(q.x, r.x) * ex,
        Math.min(q.y, r.y) * ey,
        Math.abs(r.x - q.x) * ex,
        Math.abs(r.y - q.y) * ey
      );
      return;
    }

    ctx.beginPath();
    for (var j = 0; j < p.length; j++) {
      if (j === 0) ctx.moveTo(p[j].x * ex, p[j].y * ey);
      else ctx.lineTo(p[j].x * ex, p[j].y * ey);
    }
    ctx.stroke();
  };

  Pintor.prototype.a_retracar = function () {
    var ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    for (var i = 0; i < this.tracos.length; i++) this.desenhaUm(ctx, this.tracos[i]);
  };

  Pintor.prototype.novoTraco = function (cor, largura, forma) {
    var t = { cor: cor, largura: largura, forma: forma || null, pontos: [] };
    this.tracos.push(t);
    return t;
  };

  Pintor.prototype.apagaUltimo = function () {
    this.tracos.pop();
    this.a_retracar();
  };

  Pintor.prototype.limpa = function () {
    this.tracos.length = 0;
    this.a_retracar();
  };

  Pintor.prototype.vazio = function () {
    return this.tracos.length === 0;
  };

  /* Desenha os traços só DENTRO da selecção, sobre o recorte. Sem o clip, uma
   * marca feita fora da caixa entrava no print — e o produtor não a via no
   * resultado, que é a pior forma de surpresas. */
  Pintor.prototype.pintaNoRecorte = function (ctx, r, escalaX, escalaY) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(r.left * escalaX, r.top * escalaY, r.width * escalaX, r.height * escalaY);
    ctx.clip();
    ctx.drawImage(this.canvas, 0, 0);
    ctx.restore();
  };

  /* ── O OVERLAY ──────────────────────────────────────────────────────────── */

  /* A PRIMEIRA FERRAMENTA É MOVER, E NÃO DESENHAR.
   *
   * MEDIDO no browser: com o lápis activo por omissão, arrastar DENTRO da caixa
   * desenhava em vez de a mover — e o produtor que acabara de escolher a área
   * via-se a ver uma linha vermelha em cima dela, sem forma de mexer na caixa
   * sem antes trocar de ferramenta. É o oposto do que se pede a um editor.
   *
   * A Ferramenta de Recorte do Windows também começa na seleção: escolher a
   * área é o primeiro gesto, e só depois é que se escreve por cima. */
  var FERRAMENTAS = [
    { id: 'mover', rotulo: '⤢', dica: 'Mover a área escolhida', cor: null },
    { id: 'pin', rotulo: '✎', dica: 'Desenhar à mão livre', cor: CORES.vermelho },
    { id: 'seta', rotulo: '↗', dica: 'Apontar uma seta', cor: CORES.amarelo },
    { id: 'caixa', rotulo: '▭', dica: 'Assinalar com uma caixa', cor: CORES.azul },
    { id: 'apaga', rotulo: '⌫', dica: 'Tocar numa marca para a apagar', cor: null },
  ];

  function montaOverlay(fundoCanvas, escalaX, escalaY) {
    var ov = document.createElement('div');
    ov.id = OVERLAY_ID;
    ov.style.cssText =
      'position:fixed;inset:0;z-index:2147483647;overflow:hidden;background:#0b1220';

    /* O frame congelado, como `<img>`: é garantidamente o que vai ser recortado
     * e não há nada a pintar a meio. O `src` vem do canvas, e o `recorteFinal`
     * usa o canvas — os dois vêm do mesmo frame, um deles nunca é re-descodado. */
    var img = document.createElement('img');
    img.id = 'ia-print-fundo';
    img.alt = '';
    img.style.cssText = 'position:absolute;inset:0;width:100vw;height:100vh;object-fit:fill';
    try {
      img.src = fundoCanvas.toDataURL('image/png');
    } catch (e) {
      img.src = '';
    }
    ov.appendChild(img);

    var tela = document.createElement('canvas');
    tela.id = 'ia-print-tinta';
    tela.width = Math.max(1, Math.round(escalaX * window.innerWidth));
    tela.height = Math.max(1, Math.round(escalaY * window.innerHeight));
    tela.style.cssText = 'position:absolute;inset:0;width:100vw;height:100vh;cursor:crosshair';
    ov.appendChild(tela);

    var moldura = document.createElement('div');
    moldura.id = 'ia-print-moldura';
    moldura.style.cssText =
      'position:absolute;border:2px solid #0f9d6e;background:rgba(15,157,110,.10);display:none';
    ov.appendChild(moldura);

    var pegas = document.createElement('div');
    pegas.id = 'ia-print-pegas';
    pegas.style.cssText = 'position:absolute;inset:0;display:none';
    ORDEM_PEGAS.forEach(function (lado) {
      var p = document.createElement('i');
      p.dataset.lado = lado;
      p.style.cssText =
        'position:absolute;width:10px;height:10px;margin:-5px 0 0 -5px;border-radius:2px;' +
        'background:#fff;border:2px solid #0f9d6e;box-sizing:border-box';
      pegas.appendChild(p);
    });
    ov.appendChild(pegas);

    var painel = document.createElement('div');
    painel.id = 'ia-print-painel';
    painel.style.cssText =
      'position:absolute;display:none;flex-direction:column;gap:4px;padding:5px;' +
      'background:rgba(17,24,39,.96);border:1px solid rgba(255,255,255,.16);border-radius:10px;' +
      'box-shadow:0 10px 30px rgba(0,0,0,.5)';
    ov.appendChild(painel);

    var dica = document.createElement('div');
    dica.id = 'ia-print-dica';
    dica.style.cssText =
      'position:absolute;left:50%;bottom:22px;transform:translateX(-50%);' +
      'background:rgba(0,0,0,.85);color:#fff;font:600 12.5px system-ui,sans-serif;' +
      'padding:8px 14px;border-radius:18px;pointer-events:none;white-space:nowrap';
    ov.appendChild(dica);

    return {
      overlay: ov,
      fundo: img,
      fundoCanvas: fundoCanvas,
      tela: tela,
      moldura: moldura,
      pegas: pegas,
      painel: painel,
      dica: dica,
      pintor: new Pintor(tela, escalaX, escalaY),
    };
  }

  /* O painel AO LADO da selecção, e nunca por cima dela.
   *
   * Se não couber de um lado, vai do outro; se não couber de nenhum, encosta ao
   * fundo. Um editor que tapa o assunto obriga o produtor a mover o assunto —
   * e o assunto é precisamente o que ele quer fotografar. */
  function posicionaPainel(ui, r) {
    var painel = ui.painel;
    painel.style.display = 'flex';
    var l = painel.offsetWidth || 56;
    var a = painel.offsetHeight || 240;
    var margem = 10;

    var x = r.left + r.width + margem;
    if (x + l > window.innerWidth - margem) x = r.left - l - margem;
    if (x < margem) x = Math.max(margem, window.innerWidth - l - margem);

    var y = r.top;
    if (y + a > window.innerHeight - margem) y = Math.max(margem, window.innerHeight - a - margem);

    painel.style.left = Math.round(x) + 'px';
    painel.style.top = Math.round(y) + 'px';
  }

  function botaoPainel(rotulo, dica, tamanho, aoTocar) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = rotulo;
    b.title = dica;
    b.style.cssText =
      'width:' +
      tamanho +
      'px;height:' +
      tamanho +
      'px;border-radius:8px;' +
      'border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08);color:#fff;' +
      'font:600 15px system-ui,sans-serif;cursor:pointer;flex:0 0 auto';
    b.addEventListener('click', aoTocar);
    return b;
  }

  function pintaEstadoFerramentas(ui, estado) {
    var botoes = ui.painel.querySelectorAll('button[data-ferramenta]');
    for (var i = 0; i < botoes.length; i++) {
      var ativo = botoes[i].dataset.ferramenta === estado.ferramenta;
      botoes[i].style.background = ativo ? '#0f9d6e' : 'rgba(255,255,255,.08)';
      botoes[i].style.borderColor = ativo ? '#065f46' : 'rgba(255,255,255,.2)';
    }
  }

  function montaPainel(ui, estado) {
    var painel = ui.painel;
    painel.innerHTML = '';

    FERRAMENTAS.forEach(function (f) {
      var b = botaoPainel(f.rotulo, f.dica, 46, function () {
        estado.ferramenta = f.id;
        pintaEstadoFerramentas(ui, estado);
        ui.tela.style.cursor = f.id === 'apaga' ? 'cell' : 'crosshair';
      });
      b.dataset.ferramenta = f.id;
      if (f.cor) b.style.color = f.cor;
      painel.appendChild(b);
    });

    painel.appendChild(separador());

    var desfazer = botaoPainel('↶', 'Desfazer a última marca', 46, function () {
      ui.pintor.apagaUltimo();
    });
    desfazer.id = 'ia-print-desfazer';
    painel.appendChild(desfazer);

    painel.appendChild(
      botaoPainel('Limpar', 'Tirar todas as marcas', 46, function () {
        ui.pintor.limpa();
      })
    );

    painel.appendChild(separador());

    var ok = botaoPainel('✓', 'Usar este print (Enter)', 46, function () {
      estado.confirmar();
    });
    ok.id = 'ia-print-ok';
    ok.style.background = '#0f9d6e';
    ok.style.borderColor = '#065f46';
    ok.style.fontSize = '18px';
    painel.appendChild(ok);

    painel.appendChild(
      botaoPainel('✕', 'Cancelar (Esc)', 46, function () {
        estado.cancelar('cancelado');
      })
    );

    pintaEstadoFerramentas(ui, estado);
  }

  function separador() {
    var s = document.createElement('div');
    s.style.cssText = 'height:1px;background:rgba(255,255,255,.16);margin:2px 0';
    return s;
  }

  function tiraOverlay() {
    var ov = document.getElementById(OVERLAY_ID);
    if (ov) ov.remove();
  }

  /* ── O CICLO ───────────────────────────────────────────────────────────────
   *
   * Devolve `{ok, dataUrl, rect}` ou `{ok:false, motivo}`. NUNCA levanta: a
   * recusa é o caminho normal, e um `throw` aqui só apareceria como um
   * `TypeError` dentro do `onclick`, que é onde ninguém olha. */
  function capturar() {
    return new Promise(function (resolve) {
      var recusa = motivoDaRecusa();
      if (recusa) {
        resolve({ ok: false, motivo: recusa });
        return;
      }

      var fluxo;
      try {
        fluxo = pedeEcra();
      } catch (e) {
        resolve({ ok: false, motivo: 'erro', erro: String(e) });
        return;
      }

      var video = document.createElement('video');
      video.muted = true;
      video.playsInline = true;

      Promise.resolve(fluxo)
        .then(function (stream) {
          var pista = stream.getVideoTracks()[0];
          var parar = function () {
            stream.getTracks().forEach(function (t) {
              t.stop();
            });
          };
          /* O produtor cancelou pelo painel do browser, ou a autorização
           * acabou. Sem isto o ponto verde ficaria aceso. */
          if (pista) pista.addEventListener('ended', parar);

          video.srcObject = stream;
          return video.play().catch(function () {
            // Ignore play errors (autoplay restrictions) and wait for frame anyway
            return Promise.resolve();
          }).then(function () {
            return esperaFrame(video, 4000);
          }).then(function () {
            var largura = video.videoWidth;
            var altura = video.videoHeight;
            if (!largura || !altura) {
              parar();
              resolve({ ok: false, motivo: 'sem_frame' });
              return;
            }
            var fundo = frameParaCanvas(video, largura, altura);
            /* Fecha-se AQUI, antes de mostrar seja o que for. Um frame chega
             * para o print; continuar a gravar enquanto o produtor olha para a
             * captura seria gravar sem motivo e com a luz acesa. */
            parar();
            video.srcObject = null;
            if (!fundo) {
              resolve({ ok: false, motivo: 'recorte_vazio' });
              return;
            }
            abreEditor(fundo, largura / window.innerWidth, altura / window.innerHeight, resolve);
          });
        })
        .catch(function (e) {
          var nome = e && e.name;
          resolve({
            ok: false,
            motivo: nome === 'NotFoundError' ? 'sem_ecra' : 'negado',
            erro: String((e && e.message) || e),
          });
        });
    });
  }

  /* ── O EDITOR ─────────────────────────────────────────────────────────────
   *
   * Arrastar por fora da selecção cria-a. Arrastar por dentro move-a. Arrastar
   * uma pega muda o lado. Desenhar só acontece DENTRO da selecção — fora dela o
   * gesto é para mexer na caixa, e uma marca feita fora da caixa acabaria no
   * print sem o produtor a ver. */
  function abreEditor(fundoCanvas, escalaX, escalaY, resolve) {
    var ui = montaOverlay(fundoCanvas, escalaX, escalaY);
    document.body.appendChild(ui.overlay);

    var estado = {
      sel: null,
      ferramenta: 'mover',
      confirmar: function () {
        var r = estado.sel;
        if (!r || r.width < AREA_MENOR || r.height < AREA_MENOR) {
          estado.cancelar('area_pequena');
          return;
        }
        /* `recorteFinal` é síncrono: o frame é um canvas que já está em
         * memória, e não há nada para ir buscar. */
        var saida = recorteFinal(ui, r);
        tiraOverlay();
        document.removeEventListener('keydown', aoTeclar);
        resolve(saida);
      },
      cancelar: function (motivo) {
        tiraOverlay();
        document.removeEventListener('keydown', aoTeclar);
        resolve({ ok: false, motivo: motivo || 'cancelado' });
      },
    };

    function aoTeclar(e) {
      if (e.key === 'Escape') estado.cancelar('cancelado');
      else if (e.key === 'Enter') estado.confirmar();
    }
    document.addEventListener('keydown', aoTeclar);

    var inicio = null;
    var modo = ''; /* 'nova' | 'mover' | 'pega' | 'desenho' | 'apagar' */
    var pegaAtiva = '';
    var traco = null;
    var base = null;

    function pintaSelecao() {
      var r = estado.sel;
      if (!r) {
        ui.moldura.style.display = 'none';
        ui.pegas.style.display = 'none';
        return;
      }
      ui.moldura.style.display = 'block';
      ui.pegas.style.display = 'block';
      ui.moldura.style.left = r.left + 'px';
      ui.moldura.style.top = r.top + 'px';
      ui.moldura.style.width = r.width + 'px';
      ui.moldura.style.height = r.height + 'px';
      var filhos = ui.pegas.children;
      var pos = pegasDe(r);
      for (var i = 0; i < filhos.length; i++) {
        filhos[i].style.left = pos[i].x + 'px';
        filhos[i].style.top = pos[i].y + 'px';
      }
      posicionaPainel(ui, r);
    }

    function corDe(id) {
      for (var i = 0; i < FERRAMENTAS.length; i++) {
        if (FERRAMENTAS[i].id === id && FERRAMENTAS[i].cor) return FERRAMENTAS[i].cor;
      }
      return CORES.vermelho;
    }

    ui.overlay.addEventListener('mousedown', function (e) {
      /* O painel é filho do overlay, e clicar numa ferramenta não é mexer na
       * selecção. Sem este `stopPropagation`, o clique redesenha a caixa. */
      if (e.target.closest && e.target.closest('#ia-print-painel')) return;
      if (e.button !== 0) return;
      e.preventDefault();

      var r = estado.sel;

      if (!r) {
        modo = 'nova';
        inicio = { x: e.clientX, y: e.clientY };
        estado.sel = { left: e.clientX, top: e.clientY, width: 0, height: 0 };
        pintaSelecao();
        return;
      }

      var lado = pegaPerto(r, e.clientX, e.clientY);
      if (lado) {
        modo = 'pega';
        pegaAtiva = lado;
        base = r;
        return;
      }

      /* Fora da caixa move-se sempre. Dentro, só quando a ferramenta é MOVER ou
       * APAGAR — com o lápis, o mesmo gesto é para escrever, que é o que o
       * produtor está a tentar fazer ao escolher o lápis. */
      var escreveAqui = dentro(r, e.clientX, e.clientY) && estado.ferramenta !== 'mover';

      if (estado.ferramenta === 'apaga' && dentro(r, e.clientX, e.clientY)) {
        modo = 'apagar';
        var i = marcaEm(ui.pintor.tracos, e.clientX, e.clientY);
        if (i >= 0) {
          ui.pintor.tracos.splice(i, 1);
          ui.pintor.a_retracar();
        }
        return;
      }

      if (escreveAqui) {
        modo = 'desenho';
        traco = ui.pintor.novoTraco(
          corDe(estado.ferramenta),
          LARGURA_PIN,
          estado.ferramenta === 'pin' ? null : estado.ferramenta
        );
        traco.pontos.push({ x: e.clientX, y: e.clientY });
        ui.pintor.a_retracar();
        return;
      }

      modo = 'mover';
      base = r;
      inicio = { x: e.clientX, y: e.clientY, left: r.left, top: r.top };
    });

    function mover(e) {
      if (!modo) return;
      e.preventDefault();

      if (modo === 'nova') {
        /* Passam-se `clientX/clientY` explicitamente. `MouseEvent` tem também
         * `x`/`y` (alias do CSSOM View), e `rectDe` lê `x`/`y` — dava para
         * passar o evento. Mas `rectDe` a ler `b.x` de algo que o chamador
         * passou como `{x, y}` é a mesma regra em dois sítios, e o dia em que
         * alguém trocar o evento por um objeto de outro sítio leva `NaN` para a
         * largura sem dar erro nenhum — `NaN < 8` é `false`. */
        estado.sel = rectDe(inicio, { x: e.clientX, y: e.clientY });
        pintaSelecao();
        return;
      }
      if (modo === 'pega') {
        estado.sel = redimensiona(base, pegaAtiva, e.clientX, e.clientY);
        pintaSelecao();
        return;
      }
      if (modo === 'mover') {
        estado.sel = {
          left: inicio.left + (e.clientX - inicio.x),
          top: inicio.top + (e.clientY - inicio.y),
          width: base.width,
          height: base.height,
        };
        pintaSelecao();
        return;
      }
      if (modo === 'desenho' && traco) {
        var ultimo = traco.pontos[traco.pontos.length - 1];
        if (ultimo && ultimo.x === e.clientX && ultimo.y === e.clientY) return;
        traco.pontos.push({ x: e.clientX, y: e.clientY });
        /* Seta e caixa são de DOIS pontos: a partir do terceiro o gesto é mover
         * a outra ponta, e é isso que faz uma seta continuar a ser uma seta em
         * vez de um rabisco. */
        if (traco.forma && traco.pontos.length > 2) traco.pontos.length = 2;
        ui.pintor.a_retracar();
      }
    }

    function largar() {
      modo = '';
      traco = null;
      pegaAtiva = '';
      if (estado.sel && estado.sel.width < AREA_MENOR) {
        estado.sel = null;
        pintaSelecao();
      }
      ui.dica.textContent = estado.sel
        ? 'Arraste as pegas para mudar o tamanho · desenhe por cima · ✓ para usar'
        : 'Arraste na tela a parte que quer capturar';
    }

    window.addEventListener('mousemove', mover);
    window.addEventListener('mouseup', largar);

    ui.dica.textContent = 'Arraste na tela a parte que quer capturar';
    montaPainel(ui, estado);
  }

  function distanciaAoSegmento(px, py, a, b) {
    var dx = b.x - a.x;
    var dy = b.y - a.y;
    var len2 = dx * dx + dy * dy;
    if (len2 === 0) return Math.hypot(px - a.x, py - a.y);
    var t = ((px - a.x) * dx + (py - a.y) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (a.x + t * dx), py - (a.y + t * dy));
  }

  /* Qual marca cai neste ponto — ou `-1`.
   *
   * Distância ao SEGMENTO, e não ao ponto mais próximo: um traço comprido tem o
   * ponto mais próximo longe da linha, e apagar uma linha que passa ao lado do
   * dedo é o pior resultado que um botão de apagar pode dar.
   *
   * De TRÁS para FRENTE: o que se vê por cima é o que se apaga. Ao contrário, o
   * produtor risca por cima de uma marca antiga, toca no traço novo à espera de
   * o tirar, e a marca antiga é que desaparece. */
  var ALCANCE_APAGAR = 12;

  function marcaEm(tracos, x, y) {
    for (var i = tracos.length - 1; i >= 0; i--) {
      var p = tracos[i].pontos;
      for (var j = 0; j < p.length - 1; j++) {
        if (distanciaAoSegmento(x, y, p[j], p[j + 1]) < ALCANCE_APAGAR) return i;
      }
      if (
        p.length === 1 &&
        Math.abs(p[0].x - x) < ALCANCE_APAGAR &&
        Math.abs(p[0].y - y) < ALCANCE_APAGAR
      ) {
        return i;
      }
    }
    return -1;
  }

  /* O recorte final: o frame congelado pela área, e as marcas por cima.
   *
   * Síncrono, e é o que deve ser: o frame é um canvas em memória. A versão
   * anterior passava por `new Image()` e dependia do `onload` — uma dependência
   * que pode não chegar, e um print que não sai por causa de uma descodificação
   * de imagem é um print que o produtor não tem.
   *
   * As marcas são pintadas com `clip` na área e só DEPOIS de o fundo estar
   * copiado — para que o `drawImage` do fundo não as apague. */
  function recorteFinal(ui, r) {
    try {
      var fonte = ui.fundoCanvas;
      if (!fonte) return { ok: false, motivo: 'recorte_vazio' };
      var ex = ui.pintor.cx;
      var ey = ui.pintor.cy;
      var x = Math.max(0, Math.round(r.left * ex));
      var y = Math.max(0, Math.round(r.top * ey));
      var w = Math.min(Math.round(r.width * ex), fonte.width - x);
      var h = Math.min(Math.round(r.height * ey), fonte.height - y);
      if (w <= 0 || h <= 0) return { ok: false, motivo: 'recorte_vazio' };

      var c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      var ctx = c.getContext('2d');
      ctx.drawImage(fonte, x, y, w, h, 0, 0, w, h);
      ui.pintor.pintaNoRecorte(ctx, r, ex, ey);
      return { ok: true, dataUrl: c.toDataURL('image/png'), rect: r };
    } catch (e) {
      return { ok: false, motivo: 'recorte_vazio', erro: String(e) };
    }
  }

  /* ── O PRINT ACIMA DO CAMPO ────────────────────────────────────────────── */

  /* O print em tamanho real, num `dialog`.
   *
   * `showModal()` e' o que garante o que um `position:fixed` nao garante: com o
   * dialogo aberto, tudo o que esta atras fica inerte. Numa caixa propria, um
   * clique no print acabava a mandar mensagem para a IA ou a fechar o painel —
   * e o produtor fechava o panel sem querer, o print deixava de se ver, e a
   * culpa era da feature. */
  function abreZoom(dataUrl, px, py) {
    if (!dataUrl) return null;
    var dlg = document.querySelector('.ia-print-zoom');
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.className = 'ia-print-zoom';
      /* O `dialog` modal e' dispensado com Escape. `cancel` e' o evento
       * certo para isso; um `click` no fundo tratava um clique no print como
       * um clique fora. */
      dlg.addEventListener('cancel', function () {
        dlg.close();
      });
      document.body.appendChild(dlg);
    }
    dlg.innerHTML =
      '<figure style="margin:0">' +
      '<img alt="Print em tamanho real" />' +
      '<figcaption>Print da tela &middot; ' +
      (px || 0) +
      '&times;' +
      (py || 0) +
      ' &middot; clica fora ou aperta Esc para fechar</figcaption>' +
      '</figure>';
    var grande = dlg.querySelector('img');
    grande.src = dataUrl;
    grande.addEventListener('click', function () {
      dlg.close();
    });
    /* `showModal` pode lancar se o dialogo ja estiver aberto — e Happens se o
     * produtor clica duas vezes muito rapido. Isso nao e' um erro para quem
     * clica: e' um duplo clique, e o segundo clique nao deve partir nada. */
    try {
      if (typeof dlg.showModal === 'function') dlg.showModal();
    } catch (e) {
      dlg.setAttribute('open', 'open');
    }
    return dlg;
  }

  function fechaZoom() {
    var dlg = document.querySelector('.ia-print-zoom');
    if (!dlg) return;
    try {
      if (typeof dlg.close === 'function') dlg.close();
    } catch (e) {
      dlg.removeAttribute('open');
    }
  }

  /* ONDE O PRINT VIVE, E QUANDO ESSE "ONDE" NÃO EXISTE
   *
   * MEDIDO 2026-10-10: o produtor tirou o print com sucesso e leu "Print
   * tirado, mas este painel não tem onde o mostrar". A caixa NÃO EXISTIA no
   * HTML que ele tinha no ecrã.
   *
   * A causa e' a mesma que o `ia-rail-loader.js` ja' documenta noutro sitio: o
   * JavaScript busta o cache com `?v=Date.now()`, e por isso chega sempre
   * novinho; o HTML nao busta nada, e o browser serve a versao que guardou. O
   * produtor ficava com o JS de hoje a correr sobre o HTML de anteontem — o
   * modulo novo a procurar uma caixa que o template novo e' que cria.
   *
   * Nao se resolve com "faz Ctrl+F5". Isso funciona ate a proxima correcao, e
   * enquanto o HTML e' servido de cache qualquer elemento novo volta a faltar.
   * A caixa e' CRIADA AQUI se nao estiver la, e metida em cima do campo: e' a
   * unica posicao em que o produtor a ve e o polegar dele a encontra, e
   * depende so do campo de texto — que e' o elemento que nunca falta. */
  function caixaDoPrint() {
    var caixa = document.getElementById('ia-print-caixa');
    if (caixa) return caixa;

    var campo = document.getElementById('ia-chat-input');
    if (!campo) return null;

    caixa = document.createElement('div');
    caixa.id = 'ia-print-caixa';
    caixa.hidden = true;
    campo.parentNode.insertBefore(caixa, campo);
    return caixa;
  }

  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ── O SELETOR NA PÁGINA (sem permissão, sem captura) ───────────────────────
   *
   * Uma camada fixa e transparente cobre a viewport. Arrastar (rato OU dedo)
   * desenha o rectângulo; soltar com tamanho suficiente confirma; Esc ou o
   * botão ✕ cancela; Enter confirma o rectângulo desenhado. */

  function abrirSeletorPagina() {
    return new Promise(function (resolve) {
      var camada = document.createElement('div');
      camada.id = 'ia-print-overlay';
      camada.className = 'ia-print-seletor';
      camada.innerHTML =
        '<div class="ia-print-seletor-rect" hidden></div>' +
        '<div class="ia-print-seletor-dica">Arraste sobre a área que quer mostrar à IA · Esc cancela</div>' +
        '<button type="button" class="ia-print-seletor-x" aria-label="Cancelar seleção" title="Cancelar (Esc)">×</button>';
      document.body.appendChild(camada);

      /* A barra inferior (`#dashboard-appbar`) vive em z-index máximo, ACIMA
       * desta camada: sem isto, arrastar na faixa de baixo clicava a barra,
       * não o retângulo — e no dashboard parecia que "não funciona". Tira-se
       * o clique dela DURANTE a seleção e devolve-se a seguir: invisível, e
       * só enquanto dura. */
      var appbar = document.getElementById('dashboard-appbar');
      var appbarToque = appbar ? appbar.style.pointerEvents : '';
      if (appbar) {
        try {
          appbar.style.pointerEvents = 'none';
        } catch (e) {}
      }

      var rectEl = camada.querySelector('.ia-print-seletor-rect');
      var inicio = null;
      var sel = null;

      /* Rato e dedo falam o mesmo idioma aqui: um ponto {x, y}. O
       * `changedTouches` do `touchend` não é preciso — o `largar` confirma
       * com o `sel` que o `touchmove` já calculou. */
      function pontoDe(e) {
        try {
          if (e.touches && e.touches.length) {
            return { x: e.touches[0].clientX, y: e.touches[0].clientY };
          }
        } catch (err) {}
        return { x: e.clientX, y: e.clientY };
      }

      function eNoBotao(e) {
        try {
          return Boolean(e.target && e.target.closest && e.target.closest('.ia-print-seletor-x'));
        } catch (err) {
          return false;
        }
      }

      function comecar(p) {
        inicio = p;
        sel = { left: inicio.x, top: inicio.y, width: 0, height: 0 };
        desenha();
      }

      camada.addEventListener('mousedown', function (e) {
        if (e.button !== 0 || eNoBotao(e)) return;
        e.preventDefault();
        comecar({ x: e.clientX, y: e.clientY });
      });

      /* `passive:false` de propósito: sem ele o `preventDefault` do `mover`
       * é ignorado e a página rola por baixo do dedo no meio do gesto. */
      camada.addEventListener(
        'touchstart',
        function (e) {
          if (eNoBotao(e)) return;
          e.preventDefault();
          comecar(pontoDe(e));
        },
        { passive: false }
      );

      camada.querySelector('.ia-print-seletor-x').addEventListener('click', function () {
        encerra();
        camada.remove();
        resolve({ ok: false, motivo: 'cancelado' });
      });

      window.addEventListener('mousemove', mover);
      window.addEventListener('mouseup', largar);
      window.addEventListener('touchmove', moverToque, { passive: false });
      window.addEventListener('touchend', largar);
      window.addEventListener('touchcancel', cancelaToque);
      document.addEventListener('keydown', aoTeclar);

      function mover(e) {
        if (!inicio) return;
        e.preventDefault();
        sel = rectDe(inicio, { x: e.clientX, y: e.clientY });
        desenha();
      }

      function moverToque(e) {
        if (!inicio) return;
        e.preventDefault();
        sel = rectDe(inicio, pontoDe(e));
        desenha();
      }

      function cancelaToque() {
        encerra();
        camada.remove();
        resolve({ ok: false, motivo: 'cancelado' });
      }

      function desenha() {
        if (!sel) {
          rectEl.hidden = true;
          return;
        }
        rectEl.hidden = false;
        rectEl.style.left = sel.left + 'px';
        rectEl.style.top = sel.top + 'px';
        rectEl.style.width = Math.max(0, sel.width) + 'px';
        rectEl.style.height = Math.max(0, sel.height) + 'px';
      }

      function largar() {
        encerra();
        if (!sel || sel.width < AREA_MENOR || sel.height < AREA_MENOR) {
          camada.remove();
          resolve({ ok: false, motivo: sel ? 'area_pequena' : 'cancelado' });
          return;
        }
        camada.remove();
        resolve({ ok: true, rect: sel });
      }

      function aoTeclar(e) {
        if (e.key === 'Escape') {
          encerra();
          camada.remove();
          resolve({ ok: false, motivo: 'cancelado' });
        } else if (
          e.key === 'Enter' &&
          sel &&
          sel.width >= AREA_MENOR &&
          sel.height >= AREA_MENOR
        ) {
          largar();
        }
      }

      function encerra() {
        window.removeEventListener('mousemove', mover);
        window.removeEventListener('mouseup', largar);
        window.removeEventListener('touchmove', moverToque);
        window.removeEventListener('touchend', largar);
        window.removeEventListener('touchcancel', cancelaToque);
        document.removeEventListener('keydown', aoTeclar);
        if (appbar) {
          try {
            appbar.style.pointerEvents = appbarToque;
          } catch (e) {}
        }
      }
    });
  }

  /* ── RASTERIZAR A ÁREA (imagem, sem permissão) ──────────────────────────────
   *
   * Serializa o DOM para SVG (`foreignObject`) e entrega o SVG direto, já
   * recortado na área — sem canvas no meio. É a própria página a
   * desenhar-se — e isso nenhum browser pede para autorizar, porque não sai
   * da página: nada de `getDisplayMedia`, nada de pedido "Permitir que o
   * app tenha acesso a essa guia?".
   *
   * Limites honestos, todos tratados ou assumidos:
   *   - só o que está no DOM sai (nada de outra janela ou da barra do SO);
   *   - `<canvas>` (os gráficos do dashboard!) viram `<img>` com o próprio
   *     PNG antes de serializar — sem isto os gráficos saíam em branco, que
   *     era exactamente o que se queria mostrar;
   *   - imagens same-origin viram dataURL (URL externa é bloqueada dentro
   *     do SVG e a figura saía vazia); cross-origin ficam como estão;
   *   - CSS que o browser não deixa ler (cross-origin) é saltado — o resto
   *     vai embutido numa folha só, porque `<link>` dentro do SVG nem
   *     tentaria carregar;
   *   - `<script>`, a camada de seleção e o welcome saem do retrato. */

  function cssEmbutivel() {
    var blocos = [];
    var folhas = [];
    try {
      folhas = Array.prototype.slice.call(document.styleSheets);
    } catch (e) {
      folhas = [];
    }
    folhas.forEach(function (folha) {
      var regras = null;
      try {
        regras = folha.cssRules;
      } catch (e) {
        regras = null;
      }
      if (!regras) return; /* cross-origin: o browser não deixa ler */
      var texto = '';
      try {
        for (var i = 0; i < regras.length; i++) texto += regras[i].cssText + '\n';
      } catch (e) {
        texto = '';
      }
      if (texto) blocos.push(texto);
    });
    return blocos.join('\n');
  }

  /* Diagnóstico: tudo que falha aqui escreve no console COM a etapa, para
   * colar no "Relatar problema". Uma falha sem etapa é uma falha que ninguém
   * consegue investigar — e "não funciona no dashboard" sem etapa é isso. */
  function diag(etapa, detalhe) {
    try {
      if (window.console && window.console.warn) {
        window.console.warn('[IaPrint] ' + etapa + (detalhe ? ': ' + detalhe : ''));
      }
    } catch (e) {}
  }

  /* Caracteres que o XML 1.0 proíbe em texto (ex.: \x00 vindo de payload
   * de sensor na telemetria): o XMLSerializer rebenta ao serializar e a
   * rasterização morria sem dizer onde. Limpa-se no CLONE — a página real
   * não é tocada. */
  function limpaTextoParaXml(raiz) {
    var pilha = [raiz];
    while (pilha.length) {
      var no = pilha.pop();
      if (!no || !no.childNodes) continue;
      for (var i = 0; i < no.childNodes.length; i++) {
        var f = no.childNodes[i];
        if (f.nodeType === 3) {
          if (f.nodeValue) {
            var limpo = f.nodeValue.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');
            if (limpo !== f.nodeValue) f.nodeValue = limpo;
          }
        } else if (f.nodeType === 1) {
          try {
            var attrs = f.attributes;
            for (var a = 0; attrs && a < attrs.length; a++) {
              var v = attrs[a].value;
              if (v && /[\x00-\x08\x0B\x0C\x0E-\x1F]/.test(v)) {
                attrs[a].value = v.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');
              }
            }
          } catch (e) {}
          pilha.push(f);
        }
      }
    }
  }

  /* `simples` = segunda tentativa: sem folha de estilos e sem conversão de
   * mídia (estrutura pura). Quase sempre decodifica — e uma imagem sem
   * estilo, com os números à vista, vale mais que um "veio vazio". */
  function svgDaArea(r, simples) {
    return new Promise(function (resolve) {
      try {
        var SIMPLES = simples === true;
        var larguraDoc = Math.max(
          document.documentElement.scrollWidth,
          document.body ? document.body.scrollWidth : 0
        );
        var alturaDoc = Math.max(
          document.documentElement.scrollHeight,
          document.body ? document.body.scrollHeight : 0
        );
        if (!larguraDoc || !alturaDoc) {
          diag('documento', 'doc ' + larguraDoc + 'x' + alturaDoc);
          resolve({ ok: false, motivo: 'recorte_vazio', etapa: 'documento' });
          return;
        }
        var clone = document.documentElement.cloneNode(true);

        var tira = function (seletor) {
          var nos = clone.querySelectorAll ? clone.querySelectorAll(seletor) : [];
          for (var i = 0; i < nos.length; i++) {
            if (nos[i].parentNode) nos[i].parentNode.removeChild(nos[i]);
          }
        };
        tira('script');
        tira('#ia-print-seletor');
        tira('#ia-print-welcome-overlay');
        tira('.ia-print-toast');
        limpaTextoParaXml(clone);

        /* Uma só folha de estilos: o que o browser deixou ler. No modo
         * simples não se embute nada: é o CSS que costuma quebrar a
         * decodificação, e estrutura pura quase sempre passa. */
        tira('style');
        tira('link[rel="stylesheet"]');
        if (!SIMPLES) {
          var estilo = document.createElement('style');
          estilo.textContent = cssEmbutivel();
          var cabeca = clone.querySelector('head');
          if (cabeca) cabeca.insertBefore(estilo, cabeca.firstChild);
        }

        /* Canvas não serializam o desenho: viram <img> com o próprio PNG.
         * (Só no modo cheio: no simples, saem como caixas vazias — e uma
         * caixa vazia ainda é melhor que uma falha.) */
        if (!SIMPLES)
          try {
            var originais = document.querySelectorAll('canvas');
            var clonados = clone.querySelectorAll('canvas');
            for (var c = 0; c < clonados.length && c < originais.length; c++) {
              var png = null;
              try {
                png = originais[c].toDataURL('image/png');
              } catch (e) {
                png = null;
              }
              if (!png) continue;
              var img = document.createElement('img');
              img.src = png;
              img.width = originais[c].width;
              img.height = originais[c].height;
              img.setAttribute(
                'style',
                'max-width:100%;' + (originais[c].getAttribute('style') || '')
              );
              clonados[c].parentNode.replaceChild(img, clonados[c]);
            }
          } catch (e) {}

        /* Imagens same-origin viram dataURL. (Só no modo cheio.) */
        if (!SIMPLES)
          try {
            var originaisImg = document.querySelectorAll('img');
            var clonadasImg = clone.querySelectorAll('img');
            for (var g = 0; g < clonadasImg.length && g < originaisImg.length; g++) {
              var src = originaisImg[g].currentSrc || originaisImg[g].src || '';
              if (!src || src.indexOf('data:') === 0) continue;
              var mesma = false;
              try {
                mesma = new URL(src, location.href).origin === location.origin;
              } catch (e) {
                mesma = false;
              }
              if (!mesma) continue;
              try {
                var naturalW = originaisImg[g].naturalWidth || originaisImg[g].width || 0;
                var naturalH = originaisImg[g].naturalHeight || originaisImg[g].height || 0;
                if (!naturalW || !naturalH) continue;
                var tela = document.createElement('canvas');
                tela.width = naturalW;
                tela.height = naturalH;
                tela.getContext('2d').drawImage(originaisImg[g], 0, 0);
                clonadasImg[g].src = tela.toDataURL('image/png');
                clonadasImg[g].removeAttribute('srcset');
              } catch (e) {}
            }
          } catch (e) {}

        clone.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
        var html = '';
        try {
          html = new XMLSerializer().serializeToString(clone);
        } catch (e) {
          diag('serializar', String((e && e.message) || e));
          resolve({ ok: false, motivo: 'recorte_vazio', etapa: 'serializar', erro: String(e) });
          return;
        }

        /* O SVG final JÁ É O RECORTE: viewport do tamanho da área, com o
         * documento deslocado para dentro por um <svg> aninhado em posição
         * negativa. Sem canvas em nenhum ponto — o PNG morria no
         * drawImage/toDataURL (tinta, memória, limites), e este caminho não
         * tem canvas para morrer. */
        var rw = Math.max(1, Math.round(r.width));
        var rh = Math.max(1, Math.round(r.height));
        var ox = Math.round(r.left + (window.scrollX || 0));
        var oy = Math.round(r.top + (window.scrollY || 0));
        var svg =
          '<svg xmlns="http://www.w3.org/2000/svg" width="' +
          rw +
          '" height="' +
          rh +
          '">' +
          '<svg x="' +
          -ox +
          '" y="' +
          -oy +
          '" width="' +
          Math.round(larguraDoc) +
          '" height="' +
          Math.round(alturaDoc) +
          '">' +
          '<foreignObject x="0" y="0" width="100%" height="100%">' +
          html +
          '</foreignObject></svg></svg>';

        var blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var foto = new Image();

        /* A URL fica viva enquanto o card existir (`limpar()` revoga): a
         * miniatura, o zoom, o "Guardar" e o envio à IA bebem dela. Por
         * isso o onload NÃO revoga — revogar aqui apagava a miniatura. */
        var expirou = false;
        var alarme = setTimeout(function () {
          expirou = true;
          try {
            URL.revokeObjectURL(url);
          } catch (e) {}
          diag('tempo', 'svg ' + Math.round(svg.length / 1024) + 'kb');
          resolve({ ok: false, motivo: 'tempo_esgotado', etapa: 'tempo' });
        }, 20000);

        foto.onload = function () {
          if (expirou) return;
          clearTimeout(alarme);
          resolve({
            ok: true,
            modo: 'svg',
            svgUrl: url,
            tamanhoKb: Math.round(svg.length / 1024),
            rect: r,
          });
        };
        foto.onerror = function () {
          if (expirou) return;
          clearTimeout(alarme);
          try {
            URL.revokeObjectURL(url);
          } catch (e) {}
          diag(
            'decodificar',
            'doc ' +
              Math.round(larguraDoc) +
              'x' +
              Math.round(alturaDoc) +
              ' svg ' +
              Math.round(svg.length / 1024) +
              'kb'
          );
          resolve({ ok: false, motivo: 'sem_frame', etapa: 'decodificar' });
        };
        foto.src = url;
      } catch (e) {
        diag('recorte', String((e && e.message) || e));
        resolve({ ok: false, motivo: 'recorte_vazio', etapa: 'recorte', erro: String(e) });
      }
    });
  }

  /* O card da IMAGEM acima do campo: miniatura + "Perguntar à IA" (manda o
   * PNG para a IA da nuvem, que VÊ de verdade — nada de OCR) + "Guardar"
   * (baixa o PNG). */
  function mostraAcimaDoCampo(dataUrl, rect) {
    var caixa = caixaDoPrint();
    if (!caixa) return false;

    var px = rect ? Math.round(rect.width) : 0;
    var py = rect ? Math.round(rect.height) : 0;

    caixa.hidden = false;
    caixa.innerHTML =
      '<div class="ia-print-topo">' +
      '  <div class="ia-print-topo-info">' +
      '    <span class="ia-print-topo-label">Área selecionada</span>' +
      '    <span class="ia-print-topo-size">' +
      px +
      '&times;' +
      py +
      ' px</span>' +
      '  </div>' +
      '  <button type="button" class="ia-print-x" title="Descartar" onclick="window.IaPrint.limpar()">' +
      '    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>' +
      '  </button>' +
      '</div>' +
      '<div class="ia-print-fita">' +
      '  <img class="ia-print-img" alt="Imagem da área que selecionou" />' +
      '  <div class="ia-print-acoes">' +
      '    <button type="button" class="ia-chip ia-print-acao-principal" onclick="window.IaPrint.perguntarSobreImagem()">' +
      '      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z"></path></svg>' +
      '      Perguntar à IA' +
      '    </button>' +
      '    <button type="button" class="ia-chip" onclick="window.IaPrint.guardarComoFicheiro()">' +
      '      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>' +
      '      Guardar' +
      '    </button>' +
      '  </div>' +
      '</div>';

    var img = caixa.querySelector('.ia-print-img');
    /* `src` só depois de o elemento estar no DOM: sem `src` a caixa mostra
     * 0x0 e o `flex` do pai não a empurra — a imagem "aparece" como uma
     * linha vazia em cima do campo. */
    if (img) img.src = dataUrl;

    /* Clicar na imagem abre-a em tamanho real (`dialog` do browser: enquanto
     * está aberto não há scroll nem clique por baixo). */
    if (img) {
      img.addEventListener('click', function () {
        abreZoom(dataUrl, px, py);
      });
      img.title = 'Clique para ver em tamanho real';
    }

    var chat = document.getElementById('ia-chat');
    if (chat && !chat.classList.contains('open')) {
      if (typeof window.iaDockAbrir === 'function') window.iaDockAbrir();
      else chat.classList.add('open');
    }
    return true;
  }

  var PRINT_ATUAL = null;

  function limpar() {
    /* A URL do SVG morre aqui: sem revogar, cada seleção deixava um blob
     * vivo na memória até fechar a aba. */
    try {
      if (PRINT_ATUAL && PRINT_ATUAL.svgUrl) URL.revokeObjectURL(PRINT_ATUAL.svgUrl);
    } catch (e) {}
    PRINT_ATUAL = null;
    /* Tambem fecha o print grande. Dispensar a miniatura e' Rare para o
     * produtor, mas o zoom e' um `dialog` modal: enquanto ele estiver aberto
     * nao ha botao nenhum para fechar, e ele nao fecha sozinho quando a
     * miniatura desaparece. */
    fechaZoom();
    var caixa = document.getElementById('ia-print-caixa');
    if (caixa) {
      /* `hidden`, nunca `remove()`: `caixaDoPrint()` cria a caixa quando ela
       * falta, e um `remove()` deixaria o proximo print recria-la — o que
       * funciona, mas joga fora o elemento que ja estava no template e faz o
       * print piscar a cada ida e volta. */
      caixa.hidden = true;
      caixa.innerHTML = '';
    }
  }

  var PERGUNTA_PADRAO =
    'O que você vê nesta imagem? Descreva os números, gráficos e o estado geral.';

  function csrfDaPagina() {
    try {
      var m = document.cookie.split('; ').find(function (c) {
        return c.indexOf('csrftoken=') === 0;
      });
      return m ? m.split('=')[1] : '';
    } catch (e) {
      return '';
    }
  }

  /* A bolha do usuário COM a miniatura: a pergunta entra na conversa junto
   * da imagem que a motivou — sem isso, reler depois é ler uma pergunta
   * sobre uma imagem que já não está lá. Tudo por DOM (nada de innerHTML
   * com a URL): o `src` vai por propriedade, sem string gigante no HTML. */
  function bolhaUsuarioComImagem(pergunta, dataUrl) {
    var corpo = document.getElementById('ia-chat-body');
    if (!corpo) return null;
    var d = document.createElement('div');
    d.className = 'ia-msg user ia-msg-com-imagem';
    var img = document.createElement('img');
    img.className = 'ia-msg-img';
    img.alt = 'Área selecionada enviada à IA';
    img.src = dataUrl;
    d.appendChild(img);
    var t = document.createElement('span');
    t.textContent = pergunta;
    d.appendChild(t);
    corpo.appendChild(d);
    corpo.scrollTop = corpo.scrollHeight;
    return d;
  }

  function bolhaBot(texto) {
    var corpo = document.getElementById('ia-chat-body');
    if (!corpo) return null;
    var d = document.createElement('div');
    d.className = 'ia-msg bot';
    d.textContent = texto;
    corpo.appendChild(d);
    corpo.scrollTop = corpo.scrollHeight;
    return d;
  }

  /* A imagem NÃO vai para o histórico guardado (`IaSessoes` vive em
   * localStorage): um SVG por mensagem estourava a quota em poucas
   * seleções. Vai o texto, com a nota de que houve imagem. */
  function guardaNaSessao(pergunta, resposta) {
    try {
      if (!window.IaDock || typeof window.IaDock.mensagens !== 'function') return;
      if (!window.IaSessoes || typeof window.IaSessoes.guardar !== 'function') return;
      var h = window.IaDock.mensagens();
      h.push({ role: 'user', content: String(pergunta).slice(0, 500) + ' [imagem da área]' });
      h.push({ role: 'assistant', content: String(resposta).slice(0, 2000) });
      window.IaSessoes.guardar(h);
    } catch (e) {}
  }

  function mensagemVisao(j) {
    var motivo = j && j.motivo;
    var erro = (j && j.erro) || '';
    switch (motivo) {
      case 'sem_chave':
        return erro || 'A visão está desligada: falta a chave do Gemini no servidor.';
      case 'limite':
      case 'limite_local':
      case 'tempo_esgotado':
      case 'falha_nuvem':
        return erro || 'A nuvem falhou agora. Tente de novo em instantes.';
      case 'chave_invalida':
      case 'modelo':
        return erro || 'Problema na configuração da nuvem. Fale com o administrador.';
      case 'imagem_grande':
        return erro || 'A imagem ficou grande demais. Selecione uma área menor.';
      case 'bloqueado':
        return erro || 'A nuvem recusou esta imagem. Tente outra área.';
      default:
        return erro || 'Não consegui mostrar à IA agora. Tente de novo.';
    }
  }

  /* O Gemini só aceita PNG/JPEG: na hora de perguntar, o SVG do card vira
   * JPEG num canvas, com teto de 1600 px no lado maior. É a ÚNICA conversão
   * raster do caminho — e se ela falhar, diz-se (a miniatura continua lá,
   * intacta). Blob same-origin não tinta o canvas.
   *
   * O teto existe porque o PNG de uma área de dashboard em 2x estourava os
   * ~2.5 MB que o Django aceita no corpo da requisição — e a falha vinha
   * como erro genérico de rede. 1600 px em JPEG 0.85 lê número de gráfico
   * folgado e pesa uma fração. A miniatura do card continua SVG (vetor). */
  function svgParaPng(svgUrl, w, h) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.onload = function () {
        try {
          var MAX_LADO = 1600;
          var escalaTela = Math.min(window.devicePixelRatio || 1, 2);
          var maior = Math.max(w, h) * escalaTela;
          var fator = maior > MAX_LADO ? MAX_LADO / maior : 1;
          var c = document.createElement('canvas');
          c.width = Math.max(1, Math.round(w * escalaTela * fator));
          c.height = Math.max(1, Math.round(h * escalaTela * fator));
          var ctx = c.getContext('2d');
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, c.width, c.height);
          ctx.drawImage(img, 0, 0, c.width, c.height);
          resolve({ ok: true, dataUrl: c.toDataURL('image/jpeg', 0.85) });
        } catch (e) {
          diag('png', String((e && e.message) || e));
          resolve({ ok: false, erro: String(e) });
        }
      };
      img.onerror = function () {
        diag('png', 'o SVG não decodificou para o canvas');
        resolve({ ok: false, erro: 'decodificar' });
      };
      img.src = svgUrl;
    });
  }

  /* PERGUNTAR À IA SOBRE A IMAGEM — o botão principal do card.
   *
   * A pergunta é o que está no campo (ou a padrão, se vazio). O SVG vira
   * PNG e vai com a pergunta ao `/api/ia/ver-imagem/`, onde o Gemini VÊ de
   * verdade — nada de OCR, nada de texto extraído em nenhum ponto. A
   * resposta entra na conversa como bolha normal e no histórico (só texto,
   * sem bytes). */
  function perguntarSobreImagem() {
    if (!PRINT_ATUAL || !PRINT_ATUAL.svgUrl) return;
    var inp = document.getElementById('ia-dock-input');
    var pergunta = (inp && inp.value.trim() ? inp.value.trim() : PERGUNTA_PADRAO).slice(0, 500);
    if (inp) inp.value = '';
    var botao = document.querySelector('#ia-print-caixa .ia-print-acao-principal');
    var rotulo = botao ? botao.innerHTML : '';
    if (botao) {
      botao.disabled = true;
      botao.textContent = 'Perguntando…';
    }
    var soltaBotao = function () {
      if (botao) {
        botao.disabled = false;
        botao.innerHTML = rotulo;
      }
    };
    bolhaUsuarioComImagem(pergunta, PRINT_ATUAL.svgUrl);
    var espera = bolhaBot('Vendo a imagem…');
    var mostraFalha = function (msg) {
      if (espera) espera.textContent = msg;
      else bolhaBot(msg);
    };
    svgParaPng(PRINT_ATUAL.svgUrl, PRINT_ATUAL.rect.width, PRINT_ATUAL.rect.height).then(
      function (png) {
        if (!png.ok) {
          soltaBotao();
          mostraFalha(
            'Não consegui preparar a imagem para a nuvem. Guarde o SVG e mande pelo clipe.'
          );
          return;
        }
        fetch('/api/ia/ver-imagem/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfDaPagina() },
          body: JSON.stringify({ imagem: png.dataUrl, pergunta: pergunta }),
        })
          .then(function (r) {
            return r.json().catch(function () {
              return {};
            });
          })
          .then(function (j) {
            soltaBotao();
            var resposta = j && j.ok ? String(j.resposta || '') : mensagemVisao(j);
            if (!resposta) resposta = 'A nuvem não descreveu nada. Tente outra área.';
            if (espera) {
              espera.textContent = resposta;
              var corpo = document.getElementById('ia-chat-body');
              if (corpo) corpo.scrollTop = corpo.scrollHeight;
            } else {
              bolhaBot(resposta);
            }
            if (j && j.ok) guardaNaSessao(pergunta, resposta);
          })
          .catch(function (e) {
            soltaBotao();
            mostraFalha(
              'Não consegui falar com a nuvem agora (' +
                String((e && e.message) || e) +
                '). Tente de novo.'
            );
          });
      }
    );
  }

  function guardarComoFicheiro() {
    if (!PRINT_ATUAL || !PRINT_ATUAL.svgUrl) return;
    var a = document.createElement('a');
    a.href = PRINT_ATUAL.svgUrl;
    a.download = 'area-selecionada.svg';
    a.click();
  }

  /* Roda a rasterização num retângulo fixo e CONTA o que aconteceu — para
   * colar no "Relatar problema" quando "não funciona" numa página. */
  function diagnosticar() {
    var r = { left: 100, top: 100, width: 400, height: 300 };
    var info = [];
    try {
      info.push(
        'doc ' + document.documentElement.scrollWidth + 'x' + document.documentElement.scrollHeight
      );
      info.push('folhas ' + document.styleSheets.length);
      info.push('canvas ' + document.querySelectorAll('canvas').length);
    } catch (e) {}
    window.IaDizer('Diagnóstico: ' + info.join(' · ') + '. Gerando imagem de teste…');
    return svgDaArea(r, false).then(function (img) {
      var relata = function (tag, x) {
        return (
          tag +
          ' ' +
          (x.ok
            ? 'OK (svg ' + (x.tamanhoKb || 0) + ' KB)'
            : 'FALHOU (' + x.motivo + (x.etapa ? '/' + x.etapa : '') + ')')
        );
      };
      if (img.ok) {
        window.IaDizer(
          'Diagnóstico: ' +
            relata('cheia', img) +
            '. Se a sua área falha, é tamanho ou conteúdo dela — diga qual.'
        );
        return img;
      }
      return svgDaArea(r, true).then(function (img2) {
        window.IaDizer(
          'Diagnóstico: ' +
            relata('cheia', img) +
            ' · ' +
            relata('simples', img2) +
            '. Abra o console (F12) e cole as linhas [IaPrint].'
        );
        return img2.ok ? img2 : img;
      });
    });
  }

  /* Trava de reentrada: dois cliques rápidos (ou atalho + clique) abriam
   * dois véus — e o segundo retângulo nascia por cima do primeiro, com duas
   * promessas a disputar a mesma área. */
  var SELECIONANDO = false;

  function selecionar() {
    if (SELECIONANDO) return Promise.resolve({ ok: false, motivo: 'ocupado' });
    SELECIONANDO = true;
    var destravar = function () {
      SELECIONANDO = false;
    };
    // Primeiro mostra o welcome card (se não foi dispensado)
    return new Promise(function (resolveWelcome) {
      mostraWelcomeCard(resolveWelcome);
    })
      .then(function (welcomeResult) {
        // Se cancelou, não continua
        if (welcomeResult.cancelled) {
          return { ok: false, motivo: 'cancelado' };
        }

        // SEM `capturar()`: nada de getDisplayMedia, nada de pedido ao browser.
        // O retângulo é desenhado sobre a própria página e o SVG sai direto
        // do DOM (`svgDaArea`) — e isso não precisa de permissão.
        return abrirSeletorPagina().then(function (r) {
          if (!r.ok) {
            if (r.motivo !== 'cancelado') window.IaDizer(mensagemDe(r));
            return r;
          }
          /* DUAS TENTATIVAS: a cheia (com estilo e mídia) e, se ela falhar
           * na serialização ou na decodificação, a simples (estrutura pura).
           * Sem imagem, diz-se porquê — e NÃO se entrega texto fingindo ser
           * visão. Não se tenta de novo quando a falha é no desenho/recorte:
           * o documento tem o mesmo tamanho nas duas, e daria no mesmo. */
          return svgDaArea(r.rect, false).then(function (img) {
            if (img.ok) {
              PRINT_ATUAL = img;
              mostraAcimaDoCampo(img.svgUrl, img.rect);
              mostraToastSucesso(true, false);
              return img;
            }
            if (
              img.etapa !== 'serializar' &&
              img.etapa !== 'decodificar' &&
              img.etapa !== 'tempo'
            ) {
              window.IaDizer(mensagemDe(img));
              return img;
            }
            diag('tentando-simples', img.etapa);
            return svgDaArea(r.rect, true).then(function (img2) {
              if (!img2.ok) {
                window.IaDizer(mensagemDe(img2));
                return img2;
              }
              img2.simples = true;
              PRINT_ATUAL = img2;
              mostraAcimaDoCampo(img2.svgUrl, img2.rect);
              mostraToastSucesso(true, true);
              window.IaDizer(
                'A imagem saiu simplificada (sem o estilo original) — mas dá para ver os números.'
              );
              return img2;
            });
          });
        });
        /* Destrava em TODAS as saídas (sucesso, cancelamento ou falha): sem
         * isto, um caminho esquecido deixava o botão morto até recarregar. */
      })
      .then(
        function (r) {
          destravar();
          return r;
        },
        function (e) {
          destravar();
          throw e;
        }
      );
  }

  /* Atalho Alt+A: abre a seleção sem passar pela barra.
   *
   * Alt (e não Ctrl): Ctrl+letra é do navegador/aba. Com foco em campo de
   * texto o atalho NÃO dispara — Alt+letra em alguns layouts compõe
   * caractere, e roubar a tecla de quem está digitando é o oposto de
   * atalho. Registrado uma vez só (`_iaPrintAtalhoRegistrado`): este módulo
   * entra por import dinâmico com `?v=` e pode executar de novo. */
  if (!window._iaPrintAtalhoRegistrado) {
    window._iaPrintAtalhoRegistrado = true;
    document.addEventListener('keydown', function (e) {
      try {
        if (!e.altKey || e.ctrlKey || e.metaKey) return;
        if (String(e.key || '').toLowerCase() !== 'a') return;
        var alvo = e.target;
        if (alvo) {
          var tag = String(alvo.tagName || '').toLowerCase();
          if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
          if (alvo.isContentEditable) return;
        }
        if (typeof window.iaSelecionarArea !== 'function') return;
        e.preventDefault();
        window.iaSelecionarArea();
      } catch (err) {}
    });
  }

  /* ── TOAST DE SUCESSO ────────────────────────────────────────────────────────
   *
   * Substitui o `window.IaDizer` baseado em spans por um card toast bonito
   * que aparece temporariamente no canto da tela.
   */

  function mostraToastSucesso(areaMostrou, simples) {
    var toast = document.createElement('div');
    toast.className = 'ia-print-toast';
    toast.innerHTML =
      '<div class="ia-print-toast-content">' +
      '  <div class="ia-print-toast-icon" aria-hidden="true">' +
      '    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
      '      <path d="M20 6 9 17l-5-5"></path>' +
      '    </svg>' +
      '  </div>' +
      '  <div class="ia-print-toast-text">' +
      '    <strong>' +
      (simples ? 'Imagem simplificada' : 'Imagem pronta') +
      '</strong>' +
      '    <span>' +
      (areaMostrou
        ? 'Está no card acima do campo. Toque em "Perguntar à IA" — ela vê a imagem e responde.'
        : 'Imagem gerada, mas não foi possível mostrar no painel.') +
      '</span>' +
      '  </div>' +
      '  <button type="button" class="ia-print-toast-close" aria-label="Fechar">&times;</button>' +
      '</div>';

    document.body.appendChild(toast);

    // Anima entrada
    requestAnimationFrame(function () {
      toast.classList.add('ia-print-toast-show');
    });

    // Auto-remove após 6 segundos
    var timeoutId = setTimeout(function () {
      removeToast(toast);
    }, 6000);

    // Botão fechar
    toast.querySelector('.ia-print-toast-close').addEventListener('click', function () {
      clearTimeout(timeoutId);
      removeToast(toast);
    });

    // Com imagem, o clique no toast abre-a em tamanho real
    if (areaMostrou && PRINT_ATUAL && PRINT_ATUAL.svgUrl) {
      toast.querySelector('.ia-print-toast-content').addEventListener('click', function (e) {
        if (e.target.closest('.ia-print-toast-close')) return;
        clearTimeout(timeoutId);
        removeToast(toast);
        abreZoom(
          PRINT_ATUAL.svgUrl,
          Math.round(PRINT_ATUAL.rect.width),
          Math.round(PRINT_ATUAL.rect.height)
        );
      });
      toast.style.cursor = 'pointer';
      toast.title = 'Clique para ver em tamanho real';
    }
  }

  function removeToast(toast) {
    if (!toast || !toast.parentNode) return;
    toast.classList.remove('ia-print-toast-show');
    toast.classList.add('ia-print-toast-hide');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 250);
  }

  /* ── FALAR COM O PRODUTOR ───────────────────────────────────────────────────
   *
   * MEDIDO 2026-10-10: este módulo dizia tudo o que tinha a dizer através de
   * `window.iaLocalMsg`, e esse gancho NÃO ESTÁ DEFINIDO EM NENHUM SÍTIO DO
   * REPOSITÓRIO (`grep iaLocalMsg\s*=` não devolve uma linha). Cada `if (typeof
   * iaLocalMsg === 'function')` era, na prática, `if (false)`.
   *
   * O efeito era o pior possível: o produtor carregava em "Selecionar área", a
   * captura falhava — por `sem_https`, por o browser negar, por recorta vazio — e
   * o ecrã não mudava. Nenhuma mensagem, nenhum erro, nada. O botão parecia
   * partido e a feature parecia não existir.
   *
   * `ia-rail-acoes.js` já tem o que isto faz falta, e é o que está certo: a
   * mensagem vai para a conversa quando há uma, e para o campo de texto quando não
   * há. Este é o mesmo caminho, com o mesmo fim, para o módulo que carrega
   * primeiro. */
  window.IaDizer = function (texto) {
    if (!texto) return false;
    if (typeof window.iaLocalMsg === 'function') {
      window.iaLocalMsg(texto, 'bot');
      return true;
    }
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
  };

  /* O código da etapa viaja na mensagem de falha — e com ele no "Relatar
   * problema" (que copia a última resposta), a falha chega investigável em
   * vez de chegar como "veio vazio". */
  function codigoEtapa(r) {
    return r && r.etapa ? ' (código: ' + String(r.etapa) + ')' : '';
  }

  function mensagemDe(r) {
    switch (r.motivo) {
      case 'so_no_app':
        return 'O print da tela só funciona no painel do Ampliagro. Abra o painel e tente outra vez.';
      case 'sem_suporte':
        return 'Este navegador não deixa o AmplIA ver a tela. Use o Chrome ou o Edge, ou mande uma foto pelo clipe.';
      case 'sem_https':
        return 'Ver a tela só é permitido numa ligação segura. Abra o Ampliagro por https e tente outra vez.';
      case 'negado':
        return 'Não autorizou o AmplIA a ver a tela. Sem essa autorização não há print — mande uma foto pelo clipe.';
      case 'sem_ecra':
        return 'Não há ecrã para partilhar. Mande uma foto pelo clipe.';
      case 'cancelado':
        return 'Seleção cancelada.';
      case 'area_pequena':
        return 'A área ficou pequena demais. Arraste uma área maior.';
      case 'sem_frame':
        return (
          'O navegador não conseguiu desenhar a página. Tente outra vez, ou mande uma foto pelo clipe.' +
          codigoEtapa(r)
        );
      case 'tempo_esgotado':
        return (
          'Desenhar a página demorou demais (página muito grande?). Tente uma área menor, ou mande uma foto pelo clipe.' +
          codigoEtapa(r)
        );
      case 'recorte_vazio':
        return 'O recorte veio vazio. Tente outra vez, arrastando um pouco maior.' + codigoEtapa(r);
      default:
        return 'Não consegui tirar o print: ' + ((r && r.erro) || 'erro desconhecido') + '.';
    }
  }

  window.IaPrint = {
    capturar: capturar,
    selecionar: selecionar,
    abrirSeletorPagina: abrirSeletorPagina,
    svgDaArea: svgDaArea,
    diagnosticar: diagnosticar,
    perguntarSobreImagem: perguntarSobreImagem,
    guardarComoFicheiro: guardarComoFicheiro,
    limpar: limpar,
    abreZoom: abreZoom,
    mostraAcimaDoCampo: mostraAcimaDoCampo,
    caixaDoPrint: caixaDoPrint,
    ePaginaDoAmpliagro: ePaginaDoAmpliagro,
    suportado: suportado,
    motivoDaRecusa: motivoDaRecusa,
    mensagemDe: mensagemDe,
    rectDe: rectDe,
    dentro: dentro,
    pegasDe: pegasDe,
    pegaPerto: pegaPerto,
    redimensiona: redimensiona,
    marcaEm: marcaEm,
    distanciaAoSegmento: distanciaAoSegmento,
    Pintor: Pintor,
    FERRAMENTAS: FERRAMENTAS,
    actual: function () {
      return PRINT_ATUAL;
    },
  };
})();
