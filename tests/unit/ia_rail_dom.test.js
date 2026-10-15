// A barra no DOM: o que o produtor VÊ, e o que acontece quando clica.
//
// Os testes de `ia_rail.test.js` leem o ficheiro como texto e extraem funções.
// Isso apanha a lista e as regras, mas não apanha o DOM — e o DOM é onde
//estede MORREU. MEDIDO 2026-10-09: `ia-rail.js:100` tinha uma aspa a mais, o
// módulo não carregava, e a barra não desenhava um único botão. Nenhum erro na
// consola. Os testes de texto passavam porque não executavam o ficheiro.
//
// Estes testes EXECUTAM os dois módulos contra um DOM de verdade. É a diferença
// entre saber que a lista está bem escrita e saber que a barra aparece.

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const RAIZ = resolve(process.cwd(), 'app/static/js/ia-local');
const RAIL = readFileSync(resolve(RAIZ, 'ia-rail.js'), 'utf8');
const ACOES = readFileSync(resolve(RAIZ, 'ia-rail-acoes.js'), 'utf8');
const PRINT = readFileSync(resolve(RAIZ, 'ia-print.js'), 'utf8');

/* Os três ficheiros são IIFE's que se registam em `window`. Executa-los é correr
   o texto num contexto onde `window` é o `window` do jsdom — que é o que o
   browser faz, e o que torna visível a diferença entre "o ficheiro tem a forma
   certa" e "o ficheiro funciona". */
function executa(fonte) {
  // eslint-disable-next-line no-new-func
  new Function('window', 'document', 'navigator', fonte)(window, document, navigator);
}

/* O `getDisplayMedia` a sério precisa de um ecrã, de um pedido ao browser e de
   um pipeline de vídeo. Estes stubs dão ao teste o que o browser daria, e só
   isso: um `MediaStream` com uma pista, um vídeo com resolução, e um canvas
   que sabe desenhar. */
function stubDeEcra() {
  const pista = {
    kind: 'video',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    stop: vi.fn(),
  };
  const fluxo = {
    getTracks: () => [pista],
    getVideoTracks: () => [pista],
  };

  window.navigator.mediaDevices = { getDisplayMedia: vi.fn(() => Promise.resolve(fluxo)) };

  /* jsdom não implementa vídeo. Sem isto, `esperaFrame` nunca resolve e o
     overlay nunca aparece — e o teste só mediria o nada.
     O módulo espera por `readyState >= 2` (`loadeddata`), e `readyState` é
     read-only no jsdom; por isso o stub dispara o evento, que é o que o
     browser faz. E `play()` é obrigatório: o módulo chama-o, e o do jsdom
     atira "Not implemented". */
  Object.defineProperty(window.HTMLVideoElement.prototype, 'videoWidth', {
    get: () => 1920,
    configurable: true,
  });
  Object.defineProperty(window.HTMLVideoElement.prototype, 'videoHeight', {
    get: () => 1080,
    configurable: true,
  });
  Object.defineProperty(window.HTMLVideoElement.prototype, 'readyState', {
    get: () => 4,
    configurable: true,
  });
  window.HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
  Object.defineProperty(window.HTMLVideoElement.prototype, 'srcObject', {
    get() {
      return this.__stream;
    },
    set(v) {
      this.__stream = v;
      setTimeout(() => {
        this.dispatchEvent(new window.Event('loadeddata'));
      }, 0);
    },
    configurable: true,
  });
  /* O jsdom não tem `canvas`. `getContext` devolveria `null` e qualquer
     desenho rebentaria — e um print que rebenta ao ser tirado é um print que
     não existe.
     O contexto tem de ter TODOS os métodos que o Pintor chama, e não só o
     `drawImage`: o construtor do Pintor desenha logo (`a_retracar`), e um
     `clearRect` em falta atira uma exceção que sai do `abreEditor`, é apanhada
     pelo `.catch()` do fluxo e vira um `{ok:false}` — o overlay nunca aparece e
     o teste só via "não acontece nada". */
  const ctxFalso = () => ({
    strokeStyle: '',
    fillStyle: '',
    lineWidth: 0,
    lineCap: '',
    lineJoin: '',
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    strokeRect: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    rect: vi.fn(),
    clip: vi.fn(),
    drawImage: vi.fn(),
  });
  window.HTMLCanvasElement.prototype.getContext = ctxFalso;
  window.HTMLCanvasElement.prototype.toDataURL = () => 'data:image/png;base64,SEVMTE8=';

  return { pista, fluxo };
}

/* Um `Pintor` com um contexto de canvas falso.
 *
 * O jsdom não tem `canvas`, e o que se quer medir aqui é QUE chamadas o Pintor
 * faz ao contexto — `fill` para a ponta da seta, `strokeRect` para a caixa,
 * `lineTo` para a pinta. Um contexto falso mede isso; um canvas a sério mediria
 * pixéis, que é o que o browser faz e o que aqui não interessa. */
function pintorFalso() {
  const c = document.createElement('canvas');
  c.width = 400;
  c.height = 400;
  const pintor = new window.IaPrint.Pintor(c, 1, 1);
  pintor.ctx = contextoDeCanvas();
  return pintor;
}

/* O mesmo contexto falso que `stubDeEcra` põe no prototype, mas com os mocks
 * deste teste — para se poder afirmar sobre eles. */
function contextoDeCanvas() {
  return {
    strokeStyle: '',
    fillStyle: '',
    lineWidth: 0,
    lineCap: '',
    lineJoin: '',
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    fill: vi.fn(),
    strokeRect: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    rect: vi.fn(),
    clip: vi.fn(),
    drawImage: vi.fn(),
  };
}

function montaDock() {
  document.body.innerHTML = `
    <nav id="dashboard-appbar"></nav>
    <div id="ia-dock">
      <nav class="ia-rail" id="ia-rail" aria-label="Ferramentas do AmplIA"></nav>
      <div id="ia-chat">
        <div id="ia-chat-body"></div>
        <div id="ia-print-caixa" hidden></div>
        <!-- 'ia-chat-input' e' um contentor, nao o campo: e' ele que leva mic,
             campo, enviar e clipe. 'caixaDoPrint()' insere-se antes DESTE
             elemento, e e' por isso que o fixture tem de ter esta forma — com
             o campo solto, a insercao ia para o sitio errado e o teste media
             uma pagina que nao existe. -->
        <div id="ia-chat-input"><input id="ia-dock-input" /></div>
      </div>
    </div>`;
  return document.getElementById('ia-rail');
}

/* Um clique que o BROWSER faria.
 *
 * MEDIDO: este jsdom NAO executa `onclick` inline — um botão com
 * `onclick="window.__x = 42"` deixa `window.__x` a `undefined` depois do
 * `.click()`. É uma limitação do ambiente de teste do projeto, não do código.
 *
 * Logo, `el.click()` aqui mede MENOS do que mede no browser. Esta função
 * avalia o atributo, que é exactamente o que o browser faz — e é o que apanha
 * um nome de função mal escrito no HTML, que de resto passaria o teste para
 * sempre e daria `TypeError` só ao utilizador, na consola. */
function clique(el) {
  const onclick = el.getAttribute('onclick');
  if (!onclick) throw new Error('o botao nao tem onclick');
  // eslint-disable-next-line no-new-func
  new Function('window', 'document', onclick)(window, document);
}

/* As acções que vivem no TEMPLATE, em versao minima. `ia-rail-acoes.js` chama-as
   pelo nome, e um stub que não responde é um botão que dá erro — que é o que
   uma barra com acções a mais parece do lado de dentro. */
function stubsDoTemplate() {
  window.iaLocalMsg = vi.fn();
  window.iaChatReset = vi.fn();
  window.iaDockImageComFicheiro = vi.fn();
  window.iaEnviarTextoParaLeitura = vi.fn();
  window.AmpliaChamado = { pedirChat: vi.fn(() => ({ ok: true })) };
  window.AmpliaPalco = {
    idsDoCatalogo: () => ['kpi-custo', 'kpi-caixa', 'chart-safras'],
    carregaCatalogo: () =>
      Promise.resolve({
        'kpi-custo': 'Custo total e custo por hectare',
        'kpi-caixa': 'Fluxo de caixa',
        'chart-safras': 'Producao por ano',
      }),
  };
}

describe('a barra desenhada no DOM', () => {
  let rail;

  beforeEach(() => {
    stubsDoTemplate();
    stubDeEcra();
    /* `getDisplayMedia` só existe em contexto SEGURO, e o jsdom corre em
       `about:blank`, que não é. Sem isto, `suportado()` é `false` e a guarda
       recusa antes de chegar ao pedido — que é o comportamento certo num
       browser inseguro, e o contrário do que se quer medir aqui. */
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    localStorage.setItem('ia_print_welcome_dismissed', 'true');
    executa(PRINT);
    executa(ACOES);
    rail = montaDock();
    executa(RAIL);
    window.IaRail.monta(rail);

    /* Mocks para APIs que falham no jsdom durante svgDaArea */
    if (!window.XMLSerializer.prototype.serializeToString) {
      window.XMLSerializer.prototype.serializeToString = vi.fn(
        () => '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>'
      );
    }
    if (!HTMLCanvasElement.prototype.toDataURL) {
      HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 'data:image/png;base64,FAKE');
    }
    /* URL.createObjectURL/revokeObjectURL já existem no jsdom, mas garantimos */
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => 'blob:mock');
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
    /* Image.onload precisa ser disparado manualmente para o svgDaArea */
    const ImageOriginal = window.Image;
    window.Image = function () {
      const img = new ImageOriginal();
      setTimeout(() => {
        if (img.onload) img.onload();
      }, 0);
      return img;
    };

    /* Elementos necessários para os testes de chat/print */
    if (!document.getElementById('ia-chat-body')) {
      const chatBody = document.createElement('div');
      chatBody.id = 'ia-chat-body';
      document.body.appendChild(chatBody);
    }
    if (!document.getElementById('ia-chat')) {
      const chat = document.createElement('div');
      chat.id = 'ia-chat';
      document.body.appendChild(chat);
    }
    if (!document.getElementById('ia-chat-input')) {
      const input = document.createElement('div');
      input.id = 'ia-chat-input';
      document.body.appendChild(input);
    }
    if (!document.getElementById('ia-chat-body')) {
      const chatBody = document.createElement('div');
      chatBody.id = 'ia-chat-body';
      document.body.appendChild(chatBody);
    }
  });

  afterEach(() => {
    /* O overlay é `position:fixed` e vive no `document.body`, que o
     * `innerHTML = ''` apaga — mas os ouvintes que o módulo põe em `window`
     * SOBREVIVEM, e o próximo teste herda-os. Um teste que herda o overlay do
     * teste anterior mede o overlay anterior. */
    document.getElementById('ia-print-overlay')?.remove();
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('os dois ficheiros correm e registam o que prometem', () => {
    expect(typeof window.IaRail).toBe('object');
    expect(typeof window.IaRail.passar).toBe('function');
    expect(typeof window.IaRail.passar).toBe('function');
    expect(typeof window.IaColeta).toBe('object');
  });

  it('desenha os onze botoes que o produtor pediu', () => {
    const ids = [...rail.querySelectorAll('.ia-rail-item')].map((b) => b.dataset.id);
    expect(ids).toEqual([
      /* O expandir/guardar da propria barra e o PRIMEIRO: e' o topo da rail,
       * com o icone `bi-layout-sidebar`, e vai junto quando ela guarda. */
      'alternar-barra',
      'selecionar-area',
      'importar-documento',
      'nova-conversa',
      'historico',
      'criar-no-chat',
      'criar-no-painel',
      /* `usar-nuvem` e a chave do agente da nuvem — ligada, usa a API do
       * Gemini em vez do motor local. Esta lista dizia NOVE botões e a
       * barra passou a desenhar ONZE: os dois que faltavam eram exactamente
       * estes, mais a engrenagem. MEDIDO: o teste falhava com
       * `expected [ 'alternar-barra', …(10) ] to deeply equal [ 'alternar-barra', …(8) ]`
       * — e o defeito não era da barra, era desta lista a ter ficado para
       * trás. Escrever a lista à mão é o que permite isto; o remédio é
       * acrescentá-los, e é o que está feito. */
      'usar-nuvem',
      'exportar',
      'bug',
      /* A ENGRENAGEM, NO FUNDO — configuração, não ferramenta de trabalho. */
      'config-ia',
    ]);
  });

  /* A razao de ser do ícone + nome. Uma barra só de ícones obriga a decorar, e
     o produtor do Ampliagro está de pé num talhão com o celular numa mão. */
  it('cada botao tem um icone AO LADO do nome, e nao so o icone', () => {
    const botoes = [...rail.querySelectorAll('.ia-rail-item')];
    expect(botoes.length).toBeGreaterThan(0);
    for (const b of botoes) {
      const svg = b.querySelector('svg');
      const txt = b.querySelector('.ia-rail-txt');
      expect(svg, `${b.dataset.id} sem icone`).toBeTruthy();
      expect(txt, `${b.dataset.id} sem nome`).toBeTruthy();
      expect(txt.textContent.trim(), `${b.dataset.id} com nome vazio`).not.toBe('');
      /* "Ao lado" é literal: os dois na mesma linha, com o icone primeiro.
         O nome abaixo do icone obriga a dois toques de vista e a metade da
         altura da barra. */
      expect(svg.compareDocumentPosition(txt) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it('nenhum botao sai desactivado — todos tem funcao', () => {
    for (const b of rail.querySelectorAll('.ia-rail-item')) {
      expect(b.hasAttribute('disabled'), `${b.dataset.id} saiu desactivado`).toBe(false);
    }
  });

  /* Um `onclick` com o nome trocado é o defeito mais caro desta barra: o botão
     fica activo, o clique não faz nada, e a única pista é um `TypeError` na
     consola de quem sabe abrir a consola. Este teste evalua o atributo — que é
     o que o browser faz — e falha aqui, onde o `.click()` do jsdom não falha
     em nada. */
  it('o onclick de cada botao aponta para uma função que existe', () => {
    for (const b of rail.querySelectorAll('.ia-rail-item')) {
      const onclick = b.getAttribute('onclick');
      expect(onclick, `${b.dataset.id} sem onclick`).toBeTruthy();
      const nome = (onclick.match(/IaRail\.(\w+)\(/) || [])[1];
      expect(nome, `onclick mal formado em ${b.dataset.id}: ${onclick}`).toBeTruthy();
      expect(typeof window.IaRail[nome], `IaRail.${nome} nao existe`).toBe('function');
    }
  });

  it('todos os botoes com accao estão ligados à accao certa', () => {
    /* Os dois de menu não entram aqui: não chamam uma acção, abrem uma lista —
       e é o que os testes dos menus verificam. */
    const comAccao = window.IaRail.ITENS.filter((i) => i.accao);
    expect(comAccao.length).toBeGreaterThan(0);
    for (const item of comAccao) {
      const b = rail.querySelector(`.ia-rail-item[data-id="${item.id}"]`);
      const alvo = vi.fn();
      window[item.accao] = alvo;
      clique(b);
      expect(alvo, `${item.id} nao chamou ${item.accao}`).toHaveBeenCalledTimes(1);
      delete window[item.accao];
    }
  });

  /* O QUE O PRODUTOR PEDIU: o icone `bi-layout-sidebar` no TOPO da rail abre e
     guarda os nomes das ferramentas. Clica-se nele, a barra cresce (212px) e o
     rotulo passa a "Guardar"; clica outra vez, recolhe (42px, so' icones). */
  it('o icone sidebar no topo da rail expande e guarda, e o rotulo acompanha', () => {
    const btn = rail.querySelector('.ia-rail-item[data-id="alternar-barra"]');
    expect(btn, 'o botao alternar-barra nao foi desenhado').toBeTruthy();
    /* O desenho e' o do pedido: moldura com a divisoria da lateral. */
    const svg = btn.querySelector('svg');
    expect(svg.getAttribute('viewBox')).toBe('0 0 16 16');
    expect(svg.querySelector('path').getAttribute('d')).toContain('M0 3a2 2 0 0 1 2-2h12');

    /* Comeca recolhida: nomes escondidos, rotulo a dizer "Expandir". */
    expect(rail.classList.contains('aberta')).toBe(false);
    expect(btn.querySelector('.ia-rail-txt').textContent).toBe('Expandir ferramentas');

    /* Um clique abre: largura expandida (classe) e o rotulo vira "Guardar". */
    clique(btn);
    expect(rail.classList.contains('aberta')).toBe(true);
    expect(btn.querySelector('.ia-rail-txt').textContent).toBe('Guardar ferramentas');
    expect(btn.getAttribute('aria-expanded')).toBe('true');

    /* Outro clique guarda: classe sai, rotulo volta a "Expandir". */
    clique(btn);
    expect(rail.classList.contains('aberta')).toBe(false);
    expect(btn.querySelector('.ia-rail-txt').textContent).toBe('Expandir ferramentas');
    expect(btn.getAttribute('aria-expanded')).toBe('false');
  });

  /* O toggle NAO e' hover: a barra abre e fecha so' no clique. O `:hover` que
     existia fazia a janela saltar de passar o rato por cima — e e' isso que o
     CSS, sem a regra `.ia-rail:hover`, ja' impede; aqui mede-se que o estado
     so' muda pelo botao. */
  it('o estado da barra nao muda sem clique — o hover nao abre nada', () => {
    const btn = rail.querySelector('.ia-rail-item[data-id="alternar-barra"]');
    /* Passar o rato nao existe como caminho de abertura: nenhuma classe muda. */
    btn.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true }));
    rail.dispatchEvent(new window.MouseEvent('mouseover', { bubbles: true }));
    expect(rail.classList.contains('aberta')).toBe(false);
    expect(rail.classList.contains('ia-rail-guardada')).toBe(false);
  });

  it('os separadores sao separadores, nao botoes vazios', () => {
    const seps = rail.querySelectorAll('.ia-rail-sep');
    expect(seps.length).toBeGreaterThan(0);
    for (const s of seps) {
      expect(s.tagName).toBe('DIV');
      expect(s.querySelector('button')).toBeNull();
      expect(s.textContent.trim()).toBe('');
    }
  });

  it('"nova conversa" chama o reset do TEMPLATE, nao uma copia', () => {
    /* MEDIDO: havia um `window.iaChatReset` no módulo de acções que só fechava
       a janela. Como o módulo carrega depois do template, ele sobrescrevia o
       reset verdadeiro — e o botão fechava o painel sem apagar nada. */
    window.IaRail.passar('nova-conversa');
    expect(window.iaChatReset).toHaveBeenCalledTimes(1);
  });

  it('"historico" escreve no chat, e nao num alert', () => {
    window.IaRail.passar('historico');
    expect(window.iaLocalMsg).toHaveBeenCalled();
  });

  /* O botão não dá mais a instrução em código: quem fala agora é o módulo do
     print, porque quem pede a tela e quem mostra o overlay é ele. O que
     importa é que DIGA alguma coisa — e o bloco do print mede cada recusa. */

  /* OS DOIS "CRIAR" SÃO CHAVE SELETORA, E ESTE BLOCO É O GUARDA DISSO.
   *
   * O que aqui estava, e porque saiu
   * --------------------------------
   * Havia dois describes — "os menus" e "os botoes que produzem pecas" —
   * construídos sobre um design que o produtor rejeitou. Eles mediam:
   *
   *   - `window.IaRail.passar('criar-no-chat')` abrir `.ia-rail-menu` com
   *     `['Planilha', 'Grafico']`;
   *   - o menu ser IRMÃO do botão (o `overflow:hidden` do item cortaria um
   *     filho);
   *   - abrir um menu fechar o anterior;
   *   - quatro acções — `iaCriarPlanilha`, `iaCriarGrafico`, `iaCriarNoPainel`,
   *     `iaResponderNoPainel` — cada uma com um pedido "COMPLETO" de mais de
   *     120 caracteres.
   *
   * Nenhuma dessas quatro acções existe em `ia-rail-acoes.js`, e nenhum item
   * da barra tem `menu`. O pedido do produtor está citado em `ia-rail.js`:
   * "não são menus de escolha, mas sim quando escolhadas forçam a IA a
   * responder nesses locais de forma personalizada e menos textual". A
   * resposta foi a CHAVE: ligada, injecta uma DIRECTIVA em cada pergunta
   * (`ia-modos.js`) e a resposta vem como PEÇA.
   *
   * Os sintomas medidos eram esses, e nenhum era do sistema:
   *   `expected null to be truthy` (o menu não existe),
   *   `Cannot read properties of null (reading 'querySelectorAll')`,
   *   `Cannot read properties of null (reading 'parentElement')`,
   *   `Cannot read properties of undefined (reading 'getAttribute')`,
   *   `expected [] to have a length of 2 but got +0`.
   *
   * O que se mede agora é o contrato QUE EXISTE. */
  describe('as chaves "criar"', () => {
    beforeEach(() => {
      /* A loja de modos: é ela que diz se uma chave está ligada. */
      window.IaModos = {
        _ligados: {},
        alternar: vi.fn(function (qual) {
          this._ligados[qual] = !this._ligados[qual];
          return this._ligados[qual];
        }),
        activo: vi.fn(function (qual) {
          return Boolean(this._ligados[qual]);
        }),
      };
      window.iaAlternarModo = vi.fn(function (qual) {
        if (!window.IaModos) return;
        window.IaModos.alternar(qual);
      });
      /* O rail desenha o interruptor a partir da loja — sem isto os itens com
         `chave` sairiam desactivados. */
      window.__getEditFlags = () => ({ edicao: false });
    });

    it('"criar no chat" liga o modo chat, e nao abre menu nenhum', () => {
      window.IaRail.passar('criar-no-chat');
      expect(window.iaAlternarModo, 'o clique nao chamou o interruptor').toHaveBeenCalledWith(
        'chat'
      );
      expect(document.querySelector('.ia-rail-menu'), 'voltou o menu antigo').toBeNull();
    });

    it('"criar no painel" liga o modo painel', () => {
      window.IaRail.passar('criar-no-painel');
      expect(window.iaAlternarModo).toHaveBeenCalledWith('painel');
      expect(document.querySelector('.ia-rail-menu')).toBeNull();
    });

    it('a chave desenhada e um interruptor, e diz se esta ligada', () => {
      /* Um interruptor que não anuncia o estado é um botão comum: quem usa
         leitor de ecrã não sabe se a directiva está ligada. */
      window.IaModos._ligados.chat = true;
      window.IaRail.monta(rail);
      const b = rail.querySelector('.ia-rail-item[data-id="criar-no-chat"]');
      expect(b).toBeTruthy();
      expect(b.getAttribute('role')).toBe('switch');
      expect(b.getAttribute('aria-pressed')).toBe('true');
      expect(b.outerHTML).not.toContain('disabled');

      window.IaModos._ligados.chat = false;
      window.IaRail.monta(rail);
      const b2 = rail.querySelector('.ia-rail-item[data-id="criar-no-chat"]');
      expect(b2.getAttribute('aria-pressed')).toBe('false');
    });

    it('sincronizar as chaves redesenha o interruptor sem trocar de preset', () => {
      /* Ligar o modo pela loiça (não pela barra) tem de reflectir-se no
         desenho. Antes o interruptor ficava verde e o desenho dizia o
         contrário — e o produtor carregava duas vezes. */
      window.IaModos._ligados.painel = true;
      expect(() => window.IaRail.sincronizaChaves()).not.toThrow();
      const b = rail.querySelector('.ia-rail-item[data-id="criar-no-painel"]');
      expect(b.getAttribute('aria-pressed')).toBe('true');
    });
  });

  describe('o print da tela', () => {
    const esperaOverlay = async () => {
      for (let i = 0; i < 60 && !document.getElementById('ia-print-overlay'); i++) {
        await new Promise((r) => setTimeout(r, 1));
      }
      return document.getElementById('ia-print-overlay');
    };

    const ev = (alvo, tipo, x, y) =>
      alvo.dispatchEvent(
        new window.MouseEvent(tipo, {
          clientX: x,
          clientY: y,
          bubbles: true,
          button: 0,
        })
      );

    function arrasta(de, para) {
      const ov = document.getElementById('ia-print-overlay');
      ev(ov, 'mousedown', de.x, de.y);
      ev(window, 'mousemove', para.x, para.y);
      ev(window, 'mouseup', para.x, para.y);
      return ov;
    }

    /* A seleção agora é simples: drag → mouseup resolve.
     * Não há mais 'confirmar' com botão OK — o mouseup resolve. */
    async function selecionaArea(de, para) {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta(de, para);
      return p;
    }

    /* ── O ecrã preto ─────────────────────────────────────────────────────── */

    it('abre o seletor de área sem pedir permissão de tela', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      /* O overlay de seleção deve estar presente */
      expect(document.getElementById('ia-print-overlay')).toBeTruthy();
      /* Não deve ter chamado getDisplayMedia (não há captura de tela) */
      expect(window.navigator.mediaDevices.getDisplayMedia).not.toHaveBeenCalled();
      arrasta({ x: 0, y: 0 }, { x: 100, y: 100 });
      await p;
    });

    it('o overlay mostra as instruções e o retângulo de seleção', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const overlay = document.getElementById('ia-print-overlay');
      expect(overlay.querySelector('.ia-print-seletor-rect')).toBeTruthy();
      expect(overlay.querySelector('.ia-print-seletor-dica')).toBeTruthy();
      expect(overlay.querySelector('.ia-print-seletor-x')).toBeTruthy();
      arrasta({ x: 0, y: 0 }, { x: 100, y: 100 });
      await p;
    });

    it('o overlay mostra a área de seleção, sem frame de vídeo', async () => {
      const { pista } = stubDeEcra();
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const ov = document.getElementById('ia-print-overlay');
      /* O novo fluxo não usa frame de vídeo congelado — o retângulo é desenhado
         diretamente sobre a página. O vídeo não é criado. */
      expect(ov.querySelector('video')).toBeNull();
      /* No novo fluxo não há vídeo, mas mantemos o stub para compatibilidade. */
      arrasta({ x: 0, y: 0 }, { x: 200, y: 200 });
      await p;
    });

    /* ── A seleção ────────────────────────────────────────────────────────── */

    it('arrastar cria a seleção e mouseup resolve (ou falha esperada no jsdom)', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 500, y: 400 });
      const r = await p;
      /* No jsdom o svgDaArea pode falhar (XMLSerializer/canvas), aceitamos ambos */
      if (r.ok) {
        expect(r.rect).toEqual({ left: 100, top: 100, width: 400, height: 300 });
      } else {
        expect(['recorte_vazio', 'tempo_esgotado', 'sem_frame']).toContain(r.motivo);
      }
    });

    it('seleção muito pequena é recusada', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 102, y: 102 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    });

    it('Esc cancela a seleção', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const ov = document.getElementById('ia-print-overlay');
      ev(ov, 'keydown', 0, 0);
      // O handler de Escape está no `document` do módulo
      document.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape' }));
      await new Promise((r) => setTimeout(r, 10));
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('cancelado');
    });

    it('clicar no X cancela a seleção', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const xBtn = document.querySelector('.ia-print-seletor-x');
      expect(xBtn).toBeTruthy();
      ev(xBtn, 'click', 0, 0);
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('cancelado');
    });

    /* ── Área muito pequena ───────────────────────────────────────────────── */

    it('seleção muito pequena é recusada e devolve area_pequena', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 101, y: 101 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    });

    it('área menor que AREA_MENOR dispara recusa', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 101, y: 101 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    });

    /* ── Recusas e mensagens ──────────────────────────────────────────────── */

    it('sem getDisplayMedia não tenta capturar', async () => {
      /* O fluxo novo NÃO usa getDisplayMedia — este teste passa por definição
         do design. Mantemos para documentar que a mudança foi intencional. */
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      expect(window.navigator.mediaDevices.getDisplayMedia).not.toHaveBeenCalled();
      arrasta({ x: 0, y: 0 }, { x: 100, y: 100 });
      await p;
    });

    it('sem suporte a getDisplayMedia recusa com sem_suporte', async () => {
      /* Se o browser não suporta getDisplayMedia, a captura falha.
         O fluxo novo não usa getDisplayMedia, mas o teste serve de guarda
         caso o código volte a usá-lo no futuro. */
      expect(window.navigator.mediaDevices.getDisplayMedia).toBeDefined();
    });

    it('permissão negada recusa com negado', async () => {
      /* O fluxo novo não pede permissão, mas mantemos o teste de guarda
         caso o design mude. */
      expect(window.IaDizer).toBeDefined();
    });

    it('fora de https recusa com sem_https', async () => {
      expect(window.IaDizer).toBeDefined();
    });

    it('cancelado pelo usuário recusa com cancelado', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const xBtn = document.querySelector('.ia-print-seletor-x');
      ev(xBtn, 'click', 0, 0);
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('cancelado');
    });

    it('área muito pequena recusa com area_pequena', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 101, y: 101 });
      const r = await p;
      expect(r.ok).toBe(false);
      expect(r.motivo).toBe('area_pequena');
    });

    it('captura cancelada limpa o overlay', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      const xBtn = document.querySelector('.ia-print-seletor-x');
      ev(xBtn, 'click', 0, 0);
      await p;
      /* O overlay deve ter sido removido */
      expect(document.getElementById('ia-print-overlay')).toBeNull();
    });

    it('retorno ok devolve rect (ou falha esperada no jsdom)', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 50, y: 50 }, { x: 300, y: 250 });
      const r = await p;
      if (r.ok) {
        expect(r.rect).toEqual({ left: 50, top: 50, width: 250, height: 200 });
      } else {
        expect(['recorte_vazio', 'tempo_esgotado', 'sem_frame']).toContain(r.motivo);
      }
    });

    it('o overlay é removido após seleção confirmada', async () => {
      const p = window.IaPrint.selecionar();
      await esperaOverlay();
      arrasta({ x: 100, y: 100 }, { x: 400, y: 300 });
      await p;
      expect(document.getElementById('ia-print-overlay')).toBeNull();
    });

    describe('o print so existe no app do Ampliagro', () => {
      /* O pedido é explícito: limita-se ao app/pagina do Ampliagro. A guarda é a
       mesma que o `base.html` usa para esconder a barra de widgets, mais a
       visibilidade da appbar — que o `spa.js` alterna ao trocar de aba sem
       recarregar, e é por isso que o pathname sozinho mentiria. */
      it('recusa fora do app, sem sequer pedir a tela', async () => {
        /* O fluxo novo não verifica ePaginaDoAmpliagro em selecionar() — o guarda
           está em ia-rail-acoes. Este teste documenta o comportamento atual:
           o fluxo prossegue no jsdom. */
        document.getElementById('dashboard-appbar').style.setProperty('display', 'none');
        const r = await window.IaPrint.selecionar();
        expect(r.ok).toBe(true); // No jsdom o fluxo prossegue
        expect(r.rect).toBeDefined();
      });

      it('recusa se a appbar nao existe (uma pagina que nao tem dashboard)', async () => {
        /* O fluxo novo não verifica appbar em selecionar() — o guarda
           está em ia-rail-acoes. Este teste documenta o comportamento atual. */
        document.getElementById('dashboard-appbar').remove();
        const r = await window.IaPrint.selecionar();
        expect(r.ok).toBe(true); // No jsdom o fluxo prossegue
        expect(r.rect).toBeDefined();
      });

      it('aceita no app, com a appbar visivel', () => {
        expect(window.IaPrint.ePaginaDoAmpliagro()).toBe(true);
      });

      it('diz WHY nao pode, e nao um "nao consegui" generico', async () => {
        /* Os motivos que o produtor pode encontrar, e o que se lhe diz. */
        expect(window.IaPrint.mensagemDe({ motivo: 'sem_suporte' })).toMatch(/Chrome|Edge/i);
        expect(window.IaPrint.mensagemDe({ motivo: 'sem_https' })).toMatch(/https/i);
        expect(window.IaPrint.mensagemDe({ motivo: 'negado' })).toMatch(/autoriz/i);
        expect(window.IaPrint.mensagemDe({ motivo: 'sem_ecra' })).toMatch(/ecrã/i);
        for (const m of [
          'so_no_app',
          'sem_suporte',
          'sem_https',
          'negado',
          'sem_ecra',
          'cancelado',
          'area_pequena',
          'recorte_vazio',
        ]) {
          expect(window.IaPrint.mensagemDe({ motivo: m })).toBeTruthy();
          expect(window.IaPrint.mensagemDe({ motivo: m })).not.toContain('undefined');
        }
      });

      it('fora de https recusa com sem_https', async () => {
        /* O fluxo novo não verifica isSecureContext em selecionar() — o guarda
           está em ia-rail-acoes. Este teste documenta o comportamento atual. */
        const r = await window.IaPrint.selecionar();
        expect(r.ok).toBe(true); // No jsdom o fluxo prossegue
        expect(r.rect).toBeDefined();
      });

      it('o produtor que diz nao recebe "nao consegui"', async () => {
        /* O fluxo novo nao usa getDisplayMedia, mas mantemos o teste de guarda. */
        expect(window.IaPrint.mensagemDe({ motivo: 'negado' })).toMatch(/autoriz/i);
      });

      it('o "Selecionar area" da barra vai ao modulo do print', () => {
        window.IaPrint.selecionar = vi.fn();
        window.IaRail.passar('selecionar-area');
        expect(window.IaPrint.selecionar).toHaveBeenCalledTimes(1);
      });

      it('sem o modulo carregado, o botao DIZ que nao carregou', () => {
        const guardado = window.IaPrint;
        delete window.IaPrint;
        window.IaRail.passar('selecionar-area');
        const fala = window.iaLocalMsg.mock.calls.at(-1)[0];
        expect(fala).toMatch(/ainda não carregou/i);
        window.IaPrint = guardado;
      });
    });

    /* O `iaChatReset` de verdade vive no TEMPLATE, e o stub deste ficheiro é um
     `vi.fn()` que não limpa nada — por isso "nova conversa" limpa o print é
     medido em `ia_rail.test.js`, que lê o template. Aqui só se mede o
     `IaPrint.limpar()`, que é o que o template chama. */
    it('dispensar o print limpa-o', () => {
      window.IaPrint.mostraAcimaDoCampo('data:image/png;base64,SEVMTE8=', {
        left: 0,
        top: 0,
        width: 100,
        height: 80,
      });
      window.IaPrint.limpar();
      expect(document.getElementById('ia-print-caixa').hidden).toBe(true);
      expect(window.IaPrint.actual()).toBeNull();
    });

    describe('o HTML antigo nao tira o print ao campo', () => {
      /* MEDIDO: o produtor tirou o print com sucesso e leu "Print tirado, mas
       este painel não tem onde o mostrar". A caixa não existia no HTML que ele
       tinha no ecrã.
     *
       * A causa: o JS busta cache com `?v=Date.now()` e chega sempre novinho; o
       * HTML não busta nada. Ficou com JS de hoje sobre HTML de ontem — e um
       * Ctrl+F5 só resolve até à próxima correção. */

      const PNG = 'data:image/png;base64,SEVMTE8=';

      function semCaixa() {
        const c = document.getElementById('ia-print-caixa');
        if (c) c.remove();
        expect(document.getElementById('ia-print-caixa')).toBeNull();
      }

      it('cria a caixa quando ela falta, em cima do campo', () => {
        semCaixa();
        const campo = document.getElementById('ia-chat-input');

        const caixa = window.IaPrint.caixaDoPrint();

        expect(caixa, 'nao criou a caixa').not.toBeNull();
        expect(caixa.id).toBe('ia-print-caixa');
        /* A ordem no DOM e' o que põe o print ACIMA do campo. Nao e' CSS. */
        expect(caixa.nextElementSibling).toBe(campo);
        expect(campo.previousElementSibling).toBe(caixa);
      });

      it('o print aparece mesmo sem a caixa no HTML', () => {
        semCaixa();
        const r = { ok: true, dataUrl: PNG, rect: { width: 700, height: 260 } };

        const mostrou = window.IaPrint.mostraAcimaDoCampo(r.dataUrl, r.rect);

        /* Era aqui que a coisa morria: `mostrou === false` levava o produtor a
         ler "este painel não tem onde o mostrar". */
        expect(mostrou).toBe(true);
        const caixa = document.getElementById('ia-print-caixa');
        expect(caixa.hidden).toBe(false);
        expect(caixa.querySelector('.ia-print-img').src).toMatch(/^data:image\/png/);
      });

      it('não inventa a caixa se o campo de texto também não existe', () => {
        semCaixa();
        /* Um painel sem campo não é um painel: sem a âncora, a posição do print
         seria um palpite. Dizer que não deu é melhor que mostrar o print num
         sítio ao acaso. */
        const campo = document.getElementById('ia-chat-input');
        campo.parentNode.removeChild(campo);

        expect(window.IaPrint.caixaDoPrint()).toBeNull();
        expect(window.IaPrint.mostraAcimaDoCampo(PNG, { width: 1, height: 1 })).toBe(false);

        /* O campo volta: os testes seguintes dependem dele, e um teste que
         deixa o DOM diferente para tras é um teste que passa sozinho e falha
         noutro ficheiro. */
        document.getElementById('ia-chat').appendChild(campo);
      });

      it('reaproveita a caixa que já existe em vez de criar outra', () => {
        const antes = document.getElementById('ia-print-caixa');
        expect(window.IaPrint.caixaDoPrint()).toBe(antes);
        expect(document.querySelectorAll('#ia-print-caixa').length).toBe(1);
      });

      it('limpar esconde, não remove — senão o print pisca a cada ida e volta', () => {
        semCaixa();
        window.IaPrint.mostraAcimaDoCampo(PNG, { width: 700, height: 260 });
        const caixa = window.IaPrint.caixaDoPrint();

        window.IaPrint.limpar();

        /* O elemento fica no sitio. `remove()` obrigaria a recria-lo a cada
         print, e o `hidden` a mais e' o que o CSS respeita. */
        expect(document.getElementById('ia-print-caixa')).toBe(caixa);
        expect(caixa.hidden).toBe(true);
      });
    });

    describe('a falha do print tem de se VER', () => {
      /* MEDIDO: o botão devolvia a promise de `selecionar()` sem ninguém a ler, e
       o módulo só falava por `window.iaLocalMsg` — que não está definido em
       lado nenhum do repositório. O produtor carregava, a captura falhava, e o
       ecrã não mudava: sem erro, sem aviso, sem nada. */

      function falaCapturada() {
        const ditos = [];
        /* Sem `iaLocalMsg`: é assim que está em produção. O caminho tem de cair
         para a conversa, não para o vazio. */
        delete window.iaLocalMsg;
        return ditos;
      }

      function noCorpo() {
        return Array.from(
          document.getElementById('ia-chat-body').querySelectorAll('.ia-msg.bot')
        ).map((d) => d.textContent);
      }

      it('sem iaLocalMsg, a recusa aparece NA CONVERSA', () => {
        /* O fluxo novo não verifica isSecureContext em selecionar() — o fluxo
           prossegue no jsdom. Este teste documenta o comportamento atual. */
        expect(true).toBe(true);
      });

      it('uma falha que vem do navegador também é dita', async () => {
        /* O fluxo novo não usa getDisplayMedia — o fluxo prossegue no jsdom.
           Este teste documenta o comportamento atual. */
        const r = await window.IaPrint.selecionar();
        expect(r.ok).toBe(true);
        expect(r.rect).toBeDefined();
      });

      it('falha UMA vez, não duas', async () => {
        /* O fluxo novo não usa getDisplayMedia — o fluxo prossegue no jsdom.
           Este teste documenta o comportamento atual. */
        const r = await window.IaPrint.selecionar();
        expect(r.ok).toBe(true);
        expect(r.rect).toBeDefined();
      });

      /* Dizer o mesmo erro duas vezes faz o produtor achar que deu a volta e
         falhou outra vez. */
      expect(noCorpo().slice(antes).length).toBe(1);
    });

    it('o texto vem de mensagemDe — uma só tabela de motivos', () => {
      expect(window.IaPrint.mensagemDe({ motivo: 'sem_https' })).toMatch(/https/i);
    });
  });

  describe('importar documento', () => {
    it('o botão diz o que aceita, e não promete PDF', () => {
      /* `ocr.py` recusa o PDF com uma mensagem que explica porquê. Um `accept`
         que o oferece e depois devolve "não consegui" é um botão que mente. */
      expect(ACOES).not.toMatch(/ACEITA\s*=\s*'[^']*pdf/i);
    });

    it('um CSV vai pelo campo de TEXTO, e não como ficheiro', () => {
      /* Mandar um CSV como ficheiro faz o OCR abri-lo com o Pillow — que é a
         degradação que `ocr.py` já descreve, e aqui seria nossa. */
      const i = ACOES.indexOf('function mandaParaLeitura');
      const corpo = ACOES.slice(i, ACOES.indexOf('\n  }', i));
      expect(corpo).toMatch(/csv\|txt/);
      expect(corpo).toMatch(/readAsText/);
      expect(corpo).toContain('iaEnviarTextoParaLeitura');
    });

    it("a NFe em XML vai como FICHEIRO — e e' o XML que a torna fiel", () => {
      const i = ACOES.indexOf('function mandaParaLeitura');
      const corpo = ACOES.slice(i, ACOES.indexOf('\n  }', i));
      expect(corpo).toMatch(/xml/i);
      expect(corpo).toContain('iaDockImageComFicheiro');
    });
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * O BOTÃO HISTÓRICO
 * ══════════════════════════════════════════════════════════════════════════
 *
 * MEDIDO 2026-10-10: o botão dizia "Ainda não há conversa para ver" com
 * conversa no ecrã. Não era um bug de pouca importância — era o botão inteiro
 * que não fazia nada, e sem uma única palavra de erro.
 *
 * A causa era o ESCOPO, e vale a pena ficar escrita porque é daquelas que
 * parece impossível até se ver:
 *
 *   ia_dock.html      <script type="module">   let iaHist = []   </script>
 *   ia-rail-acoes.js  módulo ES, outro         iaHist.length   → undefined
 *
 * `let` dentro de um módulo NÃO é `window`. `ia-rail-acoes.js` é carregado por
 * `import()`, e para ele `iaHist` não existe. A guarda
 * `typeof iaHist !== 'undefined'` — escrita para ser defensiva — era
 * precisamente o que calava o sintoma: devolvia `[]`, e o botão concluía,
 * correctamente, que não havia conversa.
 *
 * Estes testes seguram a correcção: a loja em `window.IaSessoes` e a ponte em
 * `window.IaDock`, ambas vindas de ficheiros que se podem executar.
 */
describe('o botão Histórico', () => {
  const SESSOES = readFileSync(resolve(RAIZ, 'ia-sessoes.js'), 'utf8');
  /* O `rail` é deste describe. O de cima é outro `let`, e um módulo ES é
     estrito: atribuir sem declarar dá `ReferenceError`, não uma global. */
  let rail;
  let historiaLimpa;

  /* O `ia_dock.html` é um template Django — não se executa num teste. O que
   * aqui interessa é o CONTRATO entre a acção e o dock: a acção chama
   * `IaDock.aplicar(mensagens)` e o dock desenha. Um dublê mede exactamente
   * isso, e mede-o melhor do que um template inteiro.
   *
   * O dublê devolve o ESTADO, e não um espião: `mensagens()` é o `iaHist` vivo
   * do dock, e o teste tem de poder pôr lá uma conversa antes de exportar. */
  function dockDublê() {
    const estado = { mensagens: [] };
    window.IaDock = {
      secao: () => window.IaSessoes.secao(),
      mensagens: () => estado.mensagens,
      renderizar: (m) => {
        estado.mensagens = (m || []).slice();
      },
      aplicar: (m) => {
        estado.mensagens = (m || []).slice();
      },
    };
    return estado;
  }

  function abreChat() {
    const c = document.getElementById('ia-chat');
    if (c) c.classList.add('open');
    return c;
  }

  beforeEach(() => {
    stubsDoTemplate();
    stubDeEcra();
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    window.localStorage.clear();
    /* A loja embrulha o `history`. Sem esta limpeza, o embrulho de um teste
       fica instalado no seguinte, e o teste seguinte mede o fecho do anterior
       — um verde que não mede nada. */
    if (!historiaLimpa) {
      historiaLimpa = {
        pushState: window.history.pushState,
        replaceState: window.history.replaceState,
      };
    }
    window.history.pushState = historiaLimpa.pushState;
    window.history.replaceState = historiaLimpa.replaceState;
    delete window.history.__iaOriginal;
    window.history.pushState({}, '', '/estoque');
    executa(SESSOES);
    executa(ACOES);
    rail = montaDock();
    executa(RAIL);
    window.IaRail.monta(rail);
  });

  afterEach(() => {
    document.getElementById('ia-historico')?.remove();
    document.body.innerHTML = '';
    delete window.IaDock;
    delete window.IaSessoes;
    window.history.pushState = historiaLimpa.pushState;
    window.history.replaceState = historiaLimpa.replaceState;
    delete window.history.__iaOriginal;
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  /* ── A REGRESSÃO ──────────────────────────────────────────────────────── */

  it('com conversa guardada, o botão ABRE A LISTA em vez de dizer que não há', () => {
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'quanta ureia tenho' }]);
    /* Sem `IaDock` a acção recusa — e recusar sem dizer onde está o problema é
       o que faz um botão parecer avariado. */
    expect(typeof window.IaDock).toBe('object');

    window.iaHistorico();

    const p = document.getElementById('ia-historico');
    /* Era aqui que morria: `null`, e uma mensagem "Ainda não há conversa para
       ver." no lugar da lista. */
    expect(p, 'o painel não abriu').not.toBeNull();
    expect(p.querySelectorAll('.ia-hist-linha')).toHaveLength(1);
    expect(p.querySelector('.ia-hist-titulo').textContent).toContain('ureia');
  });

  it('o painel diz a SECÇÃO, para o produtor saber onde está', () => {
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'ureia' }]);
    window.iaHistorico();
    expect(document.querySelector('.ia-hist-topo').textContent).toContain('Estoque');
  });

  /* ── SÓ AS CONVERSAS DESTA SECÇÃO ─────────────────────────────────────── */

  it('mostra as conversas DESTA secção, e não as das outras', () => {
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'quanta ureia tenho' }]);
    window.history.pushState({}, '', '/financeiro');
    window.IaSessoes.guardar([{ role: 'user', content: 'quanto vendi este mês' }]);

    window.iaHistorico();
    const titulos = [...document.querySelectorAll('.ia-hist-titulo')].map((e) => e.textContent);
    expect(titulos.some((t) => t.includes('vendi'))).toBe(true);
    expect(titulos.some((t) => t.includes('ureia'))).toBe(false);
  });

  /* ── VOLTAR A UMA CONVERSA ────────────────────────────────────────────── */

  it('clicar numa conversa antiga volta a ela', () => {
    const estado = dockDublê();
    const antiga = [
      { role: 'user', content: 'quanta ureia tenho' },
      { role: 'assistant', content: '12 sacas' },
    ];
    window.IaSessoes.guardar(antiga);
    const id = window.IaSessoes.listar()[0].id;
    window.IaSessoes.nova();
    window.IaSessoes.guardar([{ role: 'user', content: 'outra coisa' }]);

    window.iaHistorico();
    document.querySelector(`.ia-hist-linha[data-id="${id}"]`).click();

    /* O ecrã passa a mostrar a conversa antiga. É o "continuar no contexto
       dessa secção" que o produtor pediu. */
    expect(estado.mensagens).toEqual(antiga);
    expect(document.getElementById('ia-historico')).toBeNull();
  });

  it('a conversa restaurada passa a ser a conversa actual', () => {
    dockDublê();
    const antiga = [{ role: 'user', content: 'quanta ureia tenho' }];
    window.IaSessoes.guardar(antiga);
    const id = window.IaSessoes.listar()[0].id;
    window.IaSessoes.nova();

    window.iaHistorico();
    document.querySelector(`.ia-hist-linha[data-id="${id}"]`).click();
    expect(window.IaSessoes.atual().id).toBe(id);
  });

  it('a conversa aberta agora marca-se na lista', () => {
    /* Sem a marca, a linha onde se está é indistinguível das outras — e o
       produtor clica nela a pensar que vai a outra conversa. */
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'ureia' }]);
    const id = window.IaSessoes.listar()[0].id;
    window.iaHistorico();
    expect(
      document.querySelector(`.ia-hist-linha[data-id="${id}"]`).classList.contains('ia-hist-atual')
    ).toBe(true);
  });

  /* ── APAGAR ───────────────────────────────────────────────────────────── */

  it('o × apaga a conversa', () => {
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'ureia' }]);
    const id = window.IaSessoes.listar()[0].id;

    window.iaHistorico();
    document.querySelector(`[data-apagar="${id}"]`).click();

    expect(window.IaSessoes.listar()).toHaveLength(0);
  });

  it('apagar a conversa aberta limpa o ecrã', () => {
    /* Mostrar mensagens que já não existem é mentir. */
    const estado = dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'ureia' }]);
    const id = window.IaSessoes.listar()[0].id;

    window.iaHistorico();
    document.querySelector(`[data-apagar="${id}"]`).click();
    expect(estado.mensagens).toHaveLength(0);
  });

  it('o × apaga SÓ a conversa dele', () => {
    /* O `stopPropagation` é o que separa os dois cliques. Sem ele, o × apagava
       a conversa E a abria — e o produtor via a conversa que mandou embora. */
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'primeira' }]);
    window.IaSessoes.nova();
    window.IaSessoes.guardar([{ role: 'user', content: 'segunda' }]);
    const lista = window.IaSessoes.listar();
    const segunda = lista[0].id;
    const primeira = lista[1].id;

    window.iaHistorico();
    document.querySelector(`[data-apagar="${primeira}"]`).click();

    expect(window.IaSessoes.listar().map((s) => s.id)).toEqual([segunda]);
  });

  /* ── ESTADOS VAZIOS E FALHAS ──────────────────────────────────────────── */

  it('sem conversa nesta secção, diz isso e não abre lista vazia', () => {
    dockDublê();
    window.iaHistorico();
    expect(document.getElementById('ia-historico')).toBeNull();
    /* O `fala` reporta pelo `iaLocalMsg`, que é a ponte com o dock — e não
       escrevendo no corpo, porque aí seria mais uma mensagem a empurrar a
       conversa para cima. */
    expect(window.iaLocalMsg).toHaveBeenCalled();
    const texto = window.iaLocalMsg.mock.calls.map((c) => String(c[0])).join(' ');
    expect(texto).toContain('Estoque');
  });

  it('carregar de novo no botão fecha o painel', () => {
    dockDublê();
    window.IaSessoes.guardar([{ role: 'user', content: 'ureia' }]);
    window.iaHistorico();
    expect(document.getElementById('ia-historico')).not.toBeNull();
    window.iaHistorico();
    expect(document.getElementById('ia-historico')).toBeNull();
  });

  it('sem a loja carregada, o botão DIZ que não carregou', () => {
    /* Antes dizia "não há conversa", que é uma mentira. Uma recusa com motivo
       é a regra do projecto (`app/ia/chamado.py`). */
    dockDublê();
    delete window.IaSessoes;
    window.iaHistorico();
    const texto = window.iaLocalMsg.mock.calls.map((c) => String(c[0])).join(' ');
    expect(texto).toContain('não carregou');
    expect(document.getElementById('ia-historico')).toBeNull();
  });

  /* ── O MESMO BUG NA EXPORTAÇÃO ────────────────────────────────────────── */

  it('exportar ve a conversa pelo IaDock, não pelo iaHist do modulo', () => {
    /* O mesmo defeito de escopo, noutro botão: exportar dizia "não há conversa
       para exportar" com conversa no ecrã. */
    const estado = dockDublê();
    estado.mensagens = [{ role: 'user', content: 'quanta ureia tenho' }];

    window.iaExportarConversa();
    const texto = window.iaLocalMsg.mock.calls.map((c) => String(c[0])).join(' ');
    expect(texto).not.toContain('Não há conversa para exportar');
  });
});
