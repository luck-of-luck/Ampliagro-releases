/* O Chamado Amplia — a peça que a IA escreve, desenhada na widget-bar.
 *
 * ============================================================================
 * POR QUE ESTE FICHEIRO EXISTE E NÃO É DENTRO DO `palco-amplia.js`
 * ============================================================================
 * O cabeçalho de `palco-amplia.js` diz, e com razão: *"Se este ficheiro crescer
 * um renderizador, é sinal de que ele está a fazer o trabalho errado."* Aquele
 * desenha uma MESA de widgets do catálogo `palco` (17 widgets, um gráfico, uma
 * tabela). Este desenha uma PEÇA de blocos (`texto`, `kpi`, `grafico`, `tabela`,
 * `planilha`) que não existe em lado nenhum do registo antigo.
 *
 * São dois catálogos, duas rotas e dois ciclos de vida. Meter o segundo no
 * ficheiro do primeiro dava um módulo que sabe duas coisas incompatíveis e que
 * ninguém consegue desligar um sem partir o outro.
 *
 * ============================================================================
 * A PROVENIÊNCIA É O QUE ESTE FICHEIRO DEFENDE
 * ============================================================================
 * Um bloco traz `fonte_dado`, e há TRÊS valores — `medido`, `sem_dado`,
 * `simulado` — e nenhum outro (ver `app/ia/proveniencia.py::Estado`).
 *
 * O que este ficheiro NÃO faz é mostrar `sem_dado` como `0`. Zero é um número,
 * e um número que não veio de lugar nenhum mente com a confiança de um bom. A
 * diferença entre "a despesa foi zero" e "nunca foi registada nenhuma" é a
 * diferença entre uma tela que ajuda e uma tela que faz o produtor decidir uma
 * safra em cima de nada.
 *
 * E há uma terceira coisa, que é a norma do produto: **um número que a IA
 * escreveu no texto tem de estar numa linha de algum bloco de dado.** Quando não
 * está, o texto desce a `sem_dado` e o produtor vê, em português, quais são os
 * números sem apoio. Avisar, nunca recusar — recusar é devolver "não posso
 * escrever", que é o pior resultado que este produto pode dar a quem pergunta.
 *
 * ============================================================================
 * O QUE NÃO É FEITO AQUI, E POR QUÊ
 * ============================================================================
 * - **Não escreve.** Toda a escrita vai por `/api/amplia/exec/`, que é o
 *   `sandbox.executar` — o caminho único que audita e que pede confirmação ao
 *   produtor. Um POST direto para uma escrita seria um segundo caminho, que é
 *   exactamente o que `app/amplia_mcp/` existe para não ter.
 * - **Não usa `innerHTML`.** Título, texto e célula vêm de um modelo de 1,7B a
 *   responder a um produtor. Injetar isso como HTML é XSS com atraso. Tudo é
 *   `textContent`, sempre.
 * - **Não escreve em `document.body`.** Tudo vive num contentor com prefixo
 *   `amplia-chamado-`, para que a próxima regra de CSS acrescentada aqui não
 *   alcance o resto da tela.
 * ========================================================================== */
(function () {
  'use strict';

  var API = {
    ler: '/api/amplia/palco/chamado/',
    info: '/api/amplia/palco/info/',
    exec: '/api/amplia/exec/',
  };

  var SLUG = 'chamado-amplia';
  var NOME = 'Chamado Amplia';

  /* A MESMA regra de `app/ia/palco.py`: a peça tem de caber num olhar. Acima
     disto deixa de ser visão rápida e passa a ser o relatório que o produtor
     estava a tentar não ler. O teto é uma restrição de produto — e por isso é
     uma constante com nome, e não um número solto na linha. */
  var MAX_BLOCOS = 24;

  var estado = {
    carregado: false,
    existe: false,
    nome: NOME,
    estado: '',
    versao: 0,
    blocos: [],
    sem_dado: [],
    numeros_sem_apoio: [],
    ultimoErro: '',
  };

  /* --------------------------------------------------------------------------
     A marca de proveniência. Três estados, e nenhum outro.
     -------------------------------------------------------------------------- */
  var ROTULO_FONTE = {
    medido: '',
    sem_dado: 'sem dado',
    simulado: 'simulado',
  };

  var TITULO_FONTE = {
    sem_dado: 'Este bloco não tem número medido. Não é zero — é ausência de registo.',
    simulado: 'Valor gerado, sem ligação a esta propriedade. Não use para decidir.',
  };

  /* --------------------------------------------------------------------------
     ARede
     -------------------------------------------------------------------------- */
  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function pedir(url, corpo) {
    var init = {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    };
    if (corpo !== undefined) {
      init.method = 'POST';
      init.headers['Content-Type'] = 'application/json';
      init.headers['X-CSRFToken'] = csrf();
      init.body = JSON.stringify(corpo);
    }
    return fetch(url, init).then(function (r) {
      return r.json().catch(function () {
        return {};
      });
    });
  }

  /* --------------------------------------------------------------------------
     O CONTENTOR
     -------------------------------------------------------------------------- */
  function ancora() {
    return (
      document.getElementById('amplia-chamado-ancora') ||
      document.getElementById('amplia-palco-ancora') ||
      document.getElementById('content') ||
      document.body
    );
  }

  /* O contentor esta TAMPADO?
   *
   * Esta funcao existe por causa de uma coisa que so o browser mostrou. O
   * dashboard crava a matriz bento com `position: absolute !important; inset:
   * 0 0 56px 0` dentro de um `#content` que tem `overflow: hidden`. Ou seja:
   * o `#content` NAO tem espaco de flow para mais nada. Tudo o que for ligado
   * la - incluindo este modulo, quando cai no fallback - fica DEBAixo da
   * matriz.
   *
   * E o que se via antes disto? A peca desenhava-se na mesma, o DOM ficava
   * completo, os testes `.cjs` passavam (eles usam um DOM de mentira, sem CSS
   * nenhuma), e o produtor via... a matriz. O botao "Pedir alteracao" estava
   * no DOM, era clicavel para o Playwright por seletor, e nao por um rato:
   * `elementFromPoint` devolvia o `grid` da matriz. Um painel que se desenha e
   * nao se ve e pior do que um painel que nao se desenha - porque parece
   * funcionar e nao funciona.
   *
   * POR QUE MEDIR E NAO PERGUNTAR AO DOM
   * -------------------------------------
   * A primeira versao decidia por ESTRUTURA — "a matriz e filha do mesmo pai
   * que a ancora?". No browser real a resposta e nao: a ancora de fallback e o
   * `#content` e a matriz e uma filha DELE. O guarda, escrito ao reves, disse
   * que o sitio estava livre e montou por cima da evidencia. Estrutura de DOM
   * adivinha painting. `elementFromPoint` nao adivinha: e o que o RATO alcanca,
   * que e a unica pergunta que interessa quando o assunto e "isto da para
   * carregar".
   */
  function estaCoberto(host) {
    if (!host || !host.getBoundingClientRect || !document.elementFromPoint) {
      return false;
    }
    var r = host.getBoundingClientRect();
    if (!r.width || !r.height) return false;

    /* O PONTO E O CANTO SUPERIOR ESQUERDO, +2px. O meio do elemento falha
     * quando ha colunas de widgets por cima, e o canto superior esquerdo e onde
     * o produtor olha primeiro. */
    var x = r.left + 2;
    var y = r.top + 2;
    if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) {
      return false; /* fora da janela: nao se pode estar tapado */
    }

    var alvo = document.elementFromPoint(x, y);
    if (!alvo) return false;
    /* Nosso, ou filho nosso: nao esta tapado. Qualquer outra coisa esta. */
    return !(alvo === host || host.contains(alvo));
  }

  function ondeFica() {
    return document.getElementById('amplia-chamado-ancora') || ancora();
  }

  function avisaTapado() {
    if (window.console && console.warn) {
      console.warn(
        '[AmpliaChamado] Desenhei a peca e DEPOIS recortei-a: o dashboard ' +
          'crava a matriz bento com position:absolute sobre o #content, e nao ' +
          'ha ancora dedicada para o Chamado. Deixa-la la era deixar um painel ' +
          'invisivel com botoes que nao recebem o clique — pior do que nao ' +
          'mostrar nada, porque parece funcionar.\n' +
          'Para isto aparecer, o Chamado precisa de uma ancora propria ' +
          '(div#amplia-chamado-ancora) fora da matriz, ou de ser um widget ' +
          'bento registado em WIDGET_TYPES. Nao adivinhei qual: e uma ' +
          'decisao de produto.'
      );
    }
  }

  /* CORTA O PAINEL, MAS SO DEPOIS DO LAYOUT.
   *
   * A primeira versao media logo apos `appendChild`. No browser isso mede o
   * momento ERRADO: este script corre com `defer`, enquanto a pagina ainda
   * esta a pintar, e a matriz bento ainda nao esta no sitio. `elementFromPoint`
   * devolvia o proprio host, o guarda dizia "livre", e montava — e um segundo
   * depois a matriz aparecia por cima. O guarda estava certo e a medicao foi
   * feita cedo demais.
   *
   * Por isso a medicao e adiada para depois do primeiro quadro pintado, e
   * repetida no `load` e em cada `resize`: as tres sao as alturas em que o
   * sitio pode mudar. `cortado` impede que dois cortes deem dois avisos. */
  function agendaCorte(host) {
    var cortado = false;

    var tentar = function () {
      if (cortado) return;
      if (!host.parentElement) return; /* ja foi montado noutro sitio */
      if (!estaCoberto(host)) return;

      cortado = true;
      host.parentElement.removeChild(host);
      avisaTapado();
    };

    if (typeof requestAnimationFrame === 'function') {
      /* Dois quadros: o primeiro paints, o segundo ja ve o resultado. Com um
       * so, a matriz pode ainda nao ter chegado. */
      requestAnimationFrame(function () {
        requestAnimationFrame(tentar);
      });
    } else {
      setTimeout(tentar, 0);
    }

    if (window.addEventListener) {
      window.addEventListener('load', tentar);
      window.addEventListener('resize', tentar);
    }
  }

  /* Monta, e manda-SE vigiar. Montar-e-depois-cortar, em vez de adivinhar
   * antes: a medicao e o unico teste que vale, porque responde a pergunta que
   * o produtor faz ("isto da para carregar?"). E o corte e honesto — deixa a
   * peca numa situacao legivel: ausente e com a raza escrita, em vez de
   * presente e morta. */
  function montaSeVisivel() {
    var onde = ondeFica();
    var host = document.createElement('section');
    host.id = 'amplia-chamado-host';
    host.className = 'amplia-chamado';
    onde.appendChild(host);
    agendaCorte(host);
    return host;
  }

  function hostEl() {
    var existente = document.getElementById('amplia-chamado-host');
    if (existente) return existente;

    /* O slot do widget e de outra pessoa: nao se cria um host dentro dele,
     * escreve-se direto. E o que `desenha` usa como contentor. */
    var slot = slotDoWidget();
    if (slot) return slot;

    if (document.getElementById('amplia-chamado-ancora')) return montaSeVisivel();

    avisaSemSitio();
    return null;
  }

  /* ONDE O CHAMADO VIVE
   * ====================
   * Tres sítios, por esta ordem. E a lista e curta de proposito.
   *
   * 1. O SLOT DO WIDGET: `#widget-chamado-amplia .widget-content`. E o
   *    contentor que o proprio `generateWidgetContent` do index.html cria,
   *    porque nao conhece este id e devolve o seu fallback. Nao e preciso tocar
   *    no index.html — o contentor ja nasce, e escreve-se dentro dele. E o
   *    caminho normal, e o produtor escolhe a posicao no painel.
   *
   * 2. UMA ANCORA DEDICADA: `div#amplia-chamado-ancora`, para uma pagina sem
   *    matriz.
   *
   * 3. NADA. E o que acontece quando nao ha nenhum dos dois.
   *
   * Antes havia um quarto, implicito: `#content`, como ultimo recurso. Foi
   * REMOVIDO, e nao por ser feio — porque no dashboard ele e SEMPRE errado. O
   * `liquid-glass.css` crava a matriz com `position:absolute !important; inset:0
   * 0 56px 0` dentro de um `#content` com `overflow:hidden`, e portanto nao ha
   * espaco de flow para mais nada. A peca desenhava-se na mesma, o DOM ficava
   * completo, os 61 testes em DOM de mentira passavam — e o produtor via a
   * matriz.
   *
   * Um contentor que existe mas nao se le e pior do que um contentor que nao
   * existe: o primeiro parece funcionar. Por isso a lista e curta, e quando
   * nao ha sitio o modulo diz isso em vez de tentar um sitio a Fingir que talvez
   * de certo.
   */
  var SLOT_WIDGET = '#widget-chamado-amplia .widget-content';

  function slotDoWidget() {
    if (!document.querySelector) return null;
    return document.querySelector(SLOT_WIDGET);
  }

  function avisaSemSitio() {
    if (window.console && console.warn && !avisaSemSitio.jaDisse) {
      avisaSemSitio.jaDisse = true;
      console.warn(
        '[AmpliaChamado] Nao desenhei nada: nesta pagina nao ha nem o widget ' +
          '`chamado-amplia` na matriz nem uma `div#amplia-chamado-ancora`.\n' +
          'E de proposito. A peca desenhava-se no `#content` e ficava por baixo ' +
          'da matriz bento (position:absolute !important) - invisivel, com ' +
          'botoes que nao recebem o clique. Nao adivinho um sitio novo.'
      );
    }
  }

  function garanteEstilo() {
    if (document.getElementById('amplia-chamado-estilo')) return;
    var s = document.createElement('style');
    s.id = 'amplia-chamado-estilo';
    s.textContent = [
      '.amplia-chamado{margin:0 0 14px;}',
      '.amplia-chamado-cab{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;}',
      '.amplia-chamado-cab h3{margin:0;font-size:.95rem;font-weight:600;}',
      '.amplia-chamado-v{font-size:.7rem;opacity:.6;}',
      '.amplia-chamado-aviso{border-left:3px solid rgba(255,193,7,.7);',
      'background:rgba(255,193,7,.08);padding:8px 10px;border-radius:0 8px 8px 0;',
      'font-size:.78rem;line-height:1.5;margin:8px 0;}',
      '.amplia-chamado-aviso strong{color:rgba(255,214,102,.95);}',
      '.amplia-chamado-blocos{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));}',
      /* Um bloco de texto é LARGO: um parágrafo numa coluna de 240px é uma
         coluna de 4 palavras por linha, e ninguém lê isso. A malha e o gráfico
         é que ficam na grelha. */
      '.amplia-chamado-blocos .amc-texto{grid-column:1/-1;}',
      '.amc{border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px;',
      'background:rgba(255,255,255,.06);display:flex;flex-direction:column;gap:6px;min-width:0;}',
      '.amc h4{margin:0;font-size:.8rem;opacity:.75;font-weight:600;display:flex;gap:6px;align-items:center;}',
      '.amc-texto p{margin:0;font-size:.88rem;line-height:1.6;white-space:pre-wrap;}',
      '.amc-kpi .v{font-size:1.5rem;font-weight:700;line-height:1.1;}',
      '.amc-kpi .d{font-size:.72rem;opacity:.65;}',
      '.amc-marca{font-size:.56rem;letter-spacing:.04em;text-transform:uppercase;',
      'padding:1px 5px;border-radius:6px;font-weight:600;white-space:nowrap;}',
      '.amc-marcado-sem{background:rgba(255,193,7,.18);border:1px solid rgba(255,193,7,.45);',
      'color:rgba(255,214,102,.95);}',
      '.amc-marcado-sim{background:rgba(255,193,7,.18);border:1px solid rgba(255,193,7,.45);',
      'color:rgba(255,214,102,.95);}',
      '.amc-tabela{overflow-x:auto;}',
      '.amc table{border-collapse:collapse;width:100%;font-size:.76rem;}',
      '.amc th{text-align:left;font-weight:600;opacity:.7;border-bottom:1px solid rgba(255,255,255,.14);',
      'padding:4px 8px 4px 0;white-space:nowrap;}',
      '.amc td{padding:3px 8px 3px 0;border-bottom:1px solid rgba(255,255,255,.06);',
      'white-space:nowrap;}',
      /* Gráfico em CSS puro, sem biblioteca. Uma dependência de 40 KB para
         desenhar barras que são quatro `div` é o que faz um painel demorar a
         carregar no 3G do interior do Mato Grosso. */
      '.amc-grafico{display:flex;align-items:flex-end;gap:6px;height:120px;padding-top:6px;}',
      '.amc-col{flex:1 1 0;display:flex;flex-direction:column;justify-content:flex-end;',
      'align-items:center;gap:4px;min-width:0;}',
      '.amc-col i{display:block;width:100%;background:rgba(120,180,255,.55);',
      'border-radius:4px 4px 0 0;min-height:2px;}',
      '.amc-col b{font-size:.6rem;opacity:.65;font-weight:500;text-align:center;',
      'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%;}',
      '.amc-acao{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}',
      '.amc-btn{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);',
      'color:inherit;border-radius:8px;padding:5px 11px;font-size:.76rem;cursor:pointer;}',
      '.amc-btn:hover{background:rgba(255,255,255,.16);}',
      '.amc-btn[disabled]{opacity:.4;cursor:not-allowed;}',
      '.amc-vazio{opacity:.7;font-size:.84rem;padding:12px 0;}',
      '.amc-id{font-size:.6rem;opacity:.45;font-family:ui-monospace,monospace;}',
      '@media (max-width:640px){.amplia-chamado-blocos{grid-template-columns:1fr;}}',
    ].join('');
    document.head.appendChild(s);
  }

  /* --------------------------------------------------------------------------
     Peças pequenas
     -------------------------------------------------------------------------- */
  function botao(texto, accao, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'amc-btn';
    b.setAttribute('data-accao', accao);
    b.textContent = texto;
    if (onClick) b.addEventListener('click', onClick);
    return b;
  }

  function marca(fonte) {
    var texto = ROTULO_FONTE[fonte] || '';
    if (!texto) return null;
    var s = document.createElement('span');
    s.className = 'amc-marca ' + (fonte === 'simulado' ? 'amc-marcado-sim' : 'amc-marcado-sem');
    s.setAttribute('title', TITULO_FONTE[fonte] || '');
    s.textContent = texto;
    return s;
  }

  /* --------------------------------------------------------------------------
     OS BLOCOS
     -------------------------------------------------------------------------- */
  function desenhaTexto(art, b) {
    var cfg = b.config || {};
    var p = document.createElement('p');
    /* textContent: esta frase foi escrita por um modelo. */
    p.textContent = cfg.texto || '';
    art.appendChild(p);
  }

  function desenhaKpi(art, b) {
    var cfg = b.config || {};
    var v = document.createElement('div');
    v.className = 'v';
    /* Um bloco de dado sem valor NÃO escreve 0. Escreve a marca e o motivo. */
    v.textContent =
      cfg.valor === undefined || cfg.valor === null || cfg.valor === '' ? '—' : String(cfg.valor);
    art.appendChild(v);
    if (cfg.descricao) {
      var d = document.createElement('div');
      d.className = 'd';
      d.textContent = String(cfg.descricao);
      art.appendChild(d);
    }
  }

  function numerosDe(linhas) {
    var numeros = [];
    (linhas || []).forEach(function (linha) {
      (linha || []).forEach(function (celula) {
        var n = parseFloat(
          String(celula === null || celula === undefined ? '' : celula).replace(/\./g, '')
        );
        if (!isNaN(n)) numeros.push(n);
      });
    });
    return numeros;
  }

  function desenhaGrafico(art, b) {
    var cfg = b.config || {};
    var linhas = cfg.linhas || [];
    var numeros = numerosDe(linhas);
    if (!numeros.length) {
      var v = document.createElement('p');
      v.className = 'amc-vazio';
      v.textContent = 'Sem linhas para desenhar.';
      art.appendChild(v);
      return;
    }
    var maximo = Math.max.apply(null, numeros.map(Math.abs));
    if (!maximo) maximo = 1;

    var grafico = document.createElement('div');
    grafico.className = 'amc-grafico';
    /* Negative values grow DOWN from the baseline; positive grow UP. Uma coluna
       que "cresce para baixo" é o sinal de um mês no vermelho, e é a coisa mais
       importante que um gráfico de barras tem de mostrar. */
    var zero = Math.min(0, Math.min.apply(null, numeros));
    var amplitude = maximo - zero || 1;

    linhas.forEach(function (linha) {
      var celulas = linha || [];
      var valor = parseFloat(String(celulas[celulas.length - 1]).replace(/\./g, ''));
      if (isNaN(valor)) valor = 0;
      var col = document.createElement('div');
      col.className = 'amc-col';
      var barra = document.createElement('i');
      var altura = (Math.abs(valor) / amplitude) * 100;
      barra.style.height = Math.max(2, altura) + '%';
      if (valor < 0) barra.style.background = 'rgba(220,90,90,.55)';
      col.appendChild(barra);
      var legenda = document.createElement('b');
      legenda.textContent = String(celulas[0] === undefined ? '' : celulas[0]);
      legenda.setAttribute('title', legenda.textContent);
      col.appendChild(legenda);
      grafico.appendChild(col);
    });
    art.appendChild(grafico);
  }

  /* Uma linha da tabela. Uma função, para o corpo não repetir `var td` quatro

   * vezes e para o `textContent` estar num sítio só — que é o sítio onde a

   * célula deixa de ser código e passa a ser texto. */

  function linhaTabela(celulas, cabecalho) {
    var tr = document.createElement('tr');
    (celulas || []).forEach(function (celula) {
      var td = document.createElement(cabecalho ? 'th' : 'td');
      /* textContent: a célula vem do que a IA escreveu. */
      td.textContent = celula === null || celula === undefined ? '' : String(celula);
      tr.appendChild(td);
    });
    return tr;
  }
  function desenhaTabela(art, b, exportavel) {
    var cfg = b.config || {};
    var linhas = cfg.linhas || [];
    var cabecalhos = cfg.colunas && cfg.colunas.length ? cfg.colunas : ['valor'];
    if (!linhas.length) {
      /* Cabeçalho sem linhas é um TÍTULO com uma moldura. O produtor vê um nome
         de tabela e nenhuma tabela, e um painel vazio que parece cheio mente
         com a calma de um painel bem feito.

         E o `motivo` do servidor é a diferença entre "o sistema não funciona" e
         "falta lançar uma despesa" / "a fonte está errada" / "a IA escreveu
         números que foram descartados". São três coisas completamente
         diferentes, e sem o motivo a única leitura possível é a pior. */
      var sem = document.createElement('p');
      sem.className = 'amc-vazio';
      sem.textContent = cfg.motivo || 'Sem linhas. A peça tem o título mas não tem dados.';
      if (cfg.fonte) {
        var de = document.createElement('span');
        de.className = 'amc-id';
        de.textContent = 'fonte: ' + cfg.fonte;
        sem.appendChild(document.createTextNode(' '));
        sem.appendChild(de);
      }
      art.appendChild(sem);
      return;
    }
    var caixa = document.createElement('div');
    caixa.className = 'amc-tabela';
    var tabela = document.createElement('table');
    var thead = document.createElement('thead');
    thead.appendChild(linhaTabela(cabecalhos, true));
    tabela.appendChild(thead);
    var tbody = document.createElement('tbody');
    linhas.forEach(function (linha) {
      tbody.appendChild(linhaTabela(linha, false));
    });
    tabela.appendChild(tbody);
    caixa.appendChild(tabela);
    art.appendChild(caixa);
    /* A FONTE, visível. Um número medido tem de dizer de que consulta veio: um
       `18,4 sc/ha` sem "de onde" é um número que daqui a seis meses ninguém sabe
       a que se refere. É a mesma doutrina de `palco_dados._proveniencia`. */
    if (cfg.fonte) {
      var origem = document.createElement('div');
      origem.className = 'amc-id';
      origem.textContent = 'fonte: ' + cfg.fonte;
      art.appendChild(origem);
    }
    if (exportavel) {
      var barra = document.createElement('div');
      barra.className = 'amc-acao';
      barra.appendChild(
        botao('Exportar planilha (CSV)', 'exportar', function () {
          exportaCsv(linhas, cabecalhos, cfg.titulo || b.titulo || NOME);
        })
      );
      art.appendChild(barra);
    }
  }
  /* O CSV com BOM, porque o Excel em português abre um CSV sem BOM em ANSI e
    transforma "Café" em "Café". O separador é `;` pelo mesmo motivo. */
  function exportaCsv(linhas, colunas, nome) {
    var celula = function (v) {
      var t = v === null || v === undefined ? '' : String(v);
      return /[";\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
    };
    var partes = [(colunas.length ? colunas : ['valor']).map(celula).join(';')];
    (linhas || []).forEach(function (l) {
      partes.push((l || []).map(celula).join(';'));
    });
    var conteudo = '﻿' + partes.join('\r\n');
    try {
      var blob = new Blob([conteudo], { type: 'text/csv;charset=utf-8;' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = (String(nome) || NOME).replace(/[^\w\- ]+/g, '_') + '.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () {
        URL.revokeObjectURL(url);
      }, 0);
    } catch (e) {
      /* Num browser sem `Blob`/`URL`, o produtor fica com o CSV no clipboard
         em vez de ficar sem nada. Perder a exportação com uma explicação é
         melhor que falhar em silêncio. */
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(conteudo);
      }
    }
  }

  var DESENHADORES = {
    texto: desenhaTexto,
    kpi: desenhaKpi,
    grafico: desenhaGrafico,
    tabela: function (art, b) {
      desenhaTabela(art, b, false);
    },
    planilha: function (art, b) {
      desenhaTabela(art, b, true);
    },
  };

  /* --------------------------------------------------------------------------
     O AVISO — a parte que ninguém gosta de escrever e que é a mais importante
     -------------------------------------------------------------------------- */
  function desenhaAviso(host) {
    var partes = [];

    if (estado.sem_dado && estado.sem_dado.length) {
      partes.push(
        'bloco(s) ' +
          estado.sem_dado.join(', ') +
          ' sem número medido. Não é zero — é ausência de registo.'
      );
    }
    if (estado.numeros_sem_apoio && estado.numeros_sem_apoio.length) {
      var vistos = [];
      estado.numeros_sem_apoio.forEach(function (a) {
        if (vistos.indexOf(a.numero) < 0) vistos.push(a.numero);
      });
      partes.push(
        'número(s) escrito(s) no texto que nenhum bloco sustenta: ' +
          vistos.join(', ') +
          '. Vê o que a peça está a afirmar antes de decidir.'
      );
    }
    if (!partes.length) return;

    var aviso = document.createElement('div');
    aviso.className = 'amplia-chamado-aviso';
    var forte = document.createElement('strong');
    forte.textContent = 'Antes de decidir: ';
    aviso.appendChild(forte);
    aviso.appendChild(document.createTextNode(partes.join(' ')));
    host.appendChild(aviso);
  }

  /* --------------------------------------------------------------------------
     DESENHAR
     -------------------------------------------------------------------------- */
  /* `desenha` é a ÚNICA porta que escreve em `estado`, e escreve a partir do
   argumento.
   ---------------------------------------------------------------------------
   A primeira versão lia `estado.sem_dado` sem o popular, porque quem o
   populava era `carrega()`. No browser funcionava por acaso — `carrega` chama
   `desenha` logo a seguir — e no teste falhava: o aviso nunca aparecia porque
   `estado` ainda era o da peça anterior.

   Isso é um defeito de desenho, e não um defeito de teste. Um renderizador que
   depende de estado que OUTRA função mantém tem duas fontes de verdade para a
   mesma tela, e a segunda que desenhar é a que mostra o aviso da peça
   anterior. `estado` passa a ser um cache do argumento, e nada mais. */
  function adota(peca) {
    var c = peca && peca.existe ? peca : {};
    estado.existe = !!(peca && peca.existe);
    estado.nome = c.nome || NOME;
    estado.estado = c.estado || '';
    estado.versao = c.versao || 0;
    estado.blocos = c.blocos || [];
    estado.sem_dado = c.sem_dado || [];
    estado.numeros_sem_apoio = c.numeros_sem_apoio || [];
    return c;
  }

  function desenha(peca) {
    garanteEstilo();
    var c = adota(peca);
    var host = hostEl();

    /* Sem contentor, nao ha desenho. `hostEl` ja disse PORQUE no console; aqui
     * basta nao rebentar. Uma peca que nao cabe nao se desenha torta. */
    if (!host) return null;

    /* O marker do slot vai ANTES de qualquer desenho. Se o desenho rebentar a
     * meio, o slot fica marcado como tendo recebido conteudo e nunca mais
     * aceita um segundo — que e melhor do que redesenhar para cima de um
     * desenho meio feito, sempre. */
    if (host.setAttribute && !host.id) {
      host.setAttribute('data-chamado-pronto', '1');
    }

    host.textContent = '';

    if (!estado.existe) {
      var vazio = document.createElement('p');
      vazio.className = 'amc-vazio';
      vazio.textContent =
        'Ainda não há ' +
        NOME +
        '. Pede à IA um resumo, um gráfico ou uma tabela e ela monta aqui.';
      host.appendChild(vazio);
      return host;
    }

    var cab = document.createElement('div');
    cab.className = 'amplia-chamado-cab';
    var h = document.createElement('h3');
    h.textContent = peca.nome || NOME;
    cab.appendChild(h);
    var versao = document.createElement('span');
    versao.className = 'amplia-chamado-v';
    versao.textContent = 'v' + (peca.versao || 1) + (peca.estado ? ' · ' + peca.estado : '');
    cab.appendChild(versao);
    host.appendChild(cab);

    desenhaAviso(host);

    var blocos = peca.blocos || [];
    if (!blocos.length) {
      var sem = document.createElement('p');
      sem.className = 'amc-vazio';
      sem.textContent = 'A peça está vazia.';
      host.appendChild(sem);
    } else if (blocos.length > MAX_BLOCOS) {
      /* Defensive: o servidor corta em MAX_BLOCOS, e um corte no browser
         quando o servidor já cortou significaria que os dois discordam. */
      blocos = blocos.slice(0, MAX_BLOCOS);
    }

    var grelha = document.createElement('div');
    grelha.className = 'amplia-chamado-blocos';
    blocos.forEach(function (b) {
      var art = document.createElement('article');
      art.className = 'amc amc-' + (b.tipo || 'texto');
      art.setAttribute('data-bloco', b.id || '');
      art.setAttribute('data-fonte', b.fonte_dado || '');

      var titulo = document.createElement('h4');
      /* textContent: o título vem do modelo. */
      titulo.textContent = b.titulo || b.tipo || '';
      var m = marca(b.fonte_dado);
      if (m) titulo.appendChild(m);
      art.appendChild(titulo);

      var desenhador = DESENHADORES[b.tipo];
      if (desenhador) {
        try {
          desenhador(art, b);
        } catch (e) {
          /* Um bloco que não se desenha não pode levar o resto da peça. É a
             mesma doutrina de `palco.validar_estrutura`: um erro isolado
             degrada para "não mostrado", nunca para ecrã em branco.
             Oprodutor vê uma frase; o erro real vai para a consola, senão um
             bloco em silêncio é um bloco que ninguém vai investigar. */
          if (window.console && console.error) {
            console.error(
              '[AmpliaChamado] bloco ' + (b.id || '?') + ' (' + (b.tipo || '?') + '):',
              e
            );
          }
          var d = document.createElement('p');
          d.className = 'amc-vazio';
          d.textContent = 'Este bloco não se conseguiu desenhar.';
          art.appendChild(d);
        }
      }

      if (b.id) {
        var idEl = document.createElement('span');
        idEl.className = 'amc-id';
        idEl.textContent = b.id;
        art.appendChild(idEl);
      }
      grelha.appendChild(art);
    });
    host.appendChild(grelha);
    host.appendChild(barraAccoes(peca));
    return host;
  }

  function barraAccoes(peca) {
    var barra = document.createElement('div');
    barra.className = 'amc-acao';

    if (peca.estado === 'arquivado') {
      /* Arquivado é o produtor a fechar a porta. O botão ESCONDE em vez de
         falhar: um botão que está lá e não faz nada é pior do que um botão
         que não existe. */
      var nota = document.createElement('span');
      nota.className = 'amc-vazio';
      nota.textContent =
        'Arquivado — a IA só lê a partir daqui. Pede para abrir de novo se quiseres que ela escreva.';
      barra.appendChild(nota);
      return barra;
    }

    /* O botao de pedir alteracao SO EXISTE se houver pipeline da IA.
     *
     * Nao e desconfianca do botao: e o facto de um botao que aceita o clique e
     * nao faz nada ser pior do que um botao que nao existe. O primeiro promete
     * ao produtor que ele pode mudar a peca; o segundo nao promete nada. Numa
     * pagina sem dock, o produtor ve a peca e nao pode pedir a alteracao - e le
     * isso, em vez de carregar num botao morto.
     */
    if (temPipelineDaIA()) {
      barra.appendChild(
        botao('Pedir alteracao a IA', 'alterar', function () {
          var pergunta = window.prompt(
            'O que queres mudar no ' +
              NOME +
              '?\n' +
              'Ex.: "acrescenta uma tabela de despesas", "tira o grafico", ' +
              '"reescreve o paragrafo para ser mais curto".'
          );
          if (!pergunta || !pergunta.trim()) return;
          var r = pedirChat(pergunta);
          if (!r.ok) {
            /* o envio falhou DEPOIS do botao existir. Diz-se. */
            if (window.console && console.warn) {
              console.warn('[AmpliaChamado] nao consegui enviar:', r.motivo, r.erro || '');
            }
          }
        })
      );
    } else {
      var semPipeline = document.createElement('span');
      semPipeline.className = 'amc-vazio';
      semPipeline.textContent =
        'O chat da IA nao esta nesta tela - por isso nao ha botao para pedir ' +
        'alteracao. Abre o chat e pergunta a mao.';
      barra.appendChild(semPipeline);
    }

    barra.appendChild(
      botao('Exportar tudo (CSV)', 'exportar-tudo', function () {
        var linhas = [];
        var colunas = ['bloco', 'tipo', 'fonte', 'conteudo'];
        linhas.push(colunas);
        (peca.blocos || []).forEach(function (b) {
          var cfg = b.config || {};
          var conteudo =
            b.tipo === 'texto'
              ? cfg.texto || ''
              : (cfg.linhas || [])
                  .map(function (l) {
                    return (l || []).join(' ');
                  })
                  .join(' | ');
          linhas.push([b.id || '', b.tipo || '', b.fonte_dado || '', conteudo]);
        });
        exportaCsv(linhas, colunas, (peca.nome || NOME) + '-completo');
      })
    );
    return barra;
  }

  /* --------------------------------------------------------------------------
     A ESCRITA, que nao e feita aqui - e o botao que a pede.

     NAO SE PROCURA UM SELETOR. Usa-se `window.iaDockSend`, que e a API
     publica do pipeline unico da IA, e que `ia_panel.js` e `index.html` usam.
     Um seletor chutado produz um botao que funciona na tela de desenvolvimento
     e some em producao - ou nao funciona em lado nenhum, sem erro nenhum, que
     foi o que aconteceu com `#amplia-chat-input`. A convencao esta escrita em
     `whisper-audio.js`, e eu chutei o seletor na mesma.
     -------------------------------------------------------------------------- */
  function temPipelineDaIA() {
    return typeof window.iaDockSend === 'function';
  }

  function pedirChat(pergunta) {
    if (!temPipelineDaIA()) {
      /* Nao ha pipeline nesta pagina. Dize-lo e melhor do que fingir: um botao
         que recebeu o clique e nao fez nada e pior do que nenhum botao. */
      return { ok: false, motivo: 'sem_pipeline' };
    }
    var entrada = document.getElementById('ia-dock-input');
    if (entrada) entrada.value = pergunta;
    if (typeof window.iaDockToggle === 'function') {
      var chat = document.getElementById('ia-chat');
      if (chat && !chat.classList.contains('open')) window.iaDockToggle();
    }
    try {
      window.iaDockSend();
    } catch (e) {
      return { ok: false, motivo: 'erro_ao_enviar', erro: String(e) };
    }
    return { ok: true };
  }

  /* --------------------------------------------------------------------------
     CARREGAR
     -------------------------------------------------------------------------- */
  /* --------------------------------------------------------------------------
     PEDIR LUGAR NO PAINEL
     --------------------------------------------------------------------------
     Estar desenhado não chega: o painel só desenha o que está no LAYOUT do
     produtor, e o layout é do `index.html` — que redefine
     `window.renderWidgetsOnMatrix` duas vezes. Por isso o Chamado não se
     oferece a esse renderizador: pede o seu lugar a ele, que é quem tem o
     direito de pedir.

     `asseguraChamadoNoLayout` (dashboard-desktop.js) acrescenta a ficha se não
     houver, numa linha livre abaixo de tudo o que já existe. Depois é preciso
     MANDAR PINTAR, porque o render já tinha corrido.

     Uma vez só, por duas razões. A técnica: voltar a pedir é um ciclo de
     render. E a de propósito: se o produtor acambar de tirar o widget no modo
     de edição, voltar a metê-lo é ignorar uma decisão dele. */
  var lugarResolvido = false;

  function pedeLugares() {
    if (lugarResolvido) return false;
    var assegura = window.asseguraChamadoNoLayout;
    if (typeof assegura !== 'function') return false;

    /* Ainda nao ha painel: nao ha grid, nao ha colunas, nao ha onde meter nada. */
    if (!document.querySelector || !document.querySelector('.matrix-container')) {
      return false;
    }

    lugarResolvido = true;
    if (!assegura()) return false; /* ja estava no layout: nao ha nada a pedir */

    /* Antes de mandar pintar, embrulha o pintor. Este render é o primeiro de
     * muitos, e é o gancho que faz os próximos trazerem a peça. */
    instalaGancho();

    if (typeof window.renderWidgetsOnMatrix === 'function') {
      try {
        window.renderWidgetsOnMatrix();
      } catch (e) {
        /* Um painel que nao repinta e pior do que um aviso: o produtor fica com
         * o painel antigo, que e bom, e o Chamado aparece ao atualizar. Por
         * isso este erro e engolido de proposito. */
      }
    }
    return true;
  }

  /* Vigia o slot, e nao a primeira pintura.
   *
   * A primeira versão observava `.matrix-container` só para perguntar "já posso
   * entrar?" e desligava. Não chegava: o `index.html` redefine
   * `window.renderWidgetsOnMatrix` DUAS vezes, e é a versão dele que pinta. Cada
   * render apaga e recria TODOS os `.bento-block` — logo também o meu — e
   * quem me redesenha tem de ser notificado de cada uma, não só da primeira.
   *
   * A pista de que é preciso redesenhar é o MARKER: `desenha` põe
   * `data-chamado-pronto` no contentor. Um contentor novo, ou um que perdeu o
   * marker, é um contentor por desenhar. Sem isto, o painel acabava de mostrar
   * a peça e a atualização seguinte punha o texto genérico de widget
   * desconhecido — e o produtor via uma peça que desaparece sozinha.
   *
   * `subtree` porque o `.bento-block` é trocado, não o contentor da matriz. E
   * `aoMudar` é idempotente: se o slot já tem marker, não faz nada — por isso o
   * próprio desenho não volta a disparar o que o desenhou. */
  function aoMudar() {
    /* Primeiro, se o painel substituiu o renderizador, volta a embrulhá-lo.
     * Sem isto, um `renderWidgetsOnMatrix` novo — do `index.html`, ou de outro
     * módulo — ficaria sem a peça e sem que ninguém reparasse. */
    instalaGancho();

    var slot = slotDoWidget();

    /* Sem widget no painel: ainda posso pedir o meu lugar. Uma vez só — se o
     * produtor o tirar no modo de edição, não voltamos a metê-lo. */
    if (!slot) {
      if (!lugarResolvido && pedeLugares()) desenha(ultimaPeca);
      return;
    }

    /* Com o slot lá, se a peça está lá não há nada a fazer. A pergunta é
     * "está a peça lá?", e não "passou por aqui?" — o painel escreve o texto
     * genérico por cima do desenho, e o marcador continua posto. */
    if (slotDesenhado(slot)) return;
    if (!estado.carregado || !ultimaPeca) return;
    desenha(ultimaPeca);
  }

  function vigiaOSlot() {
    if (!window.MutationObserver || !document.querySelector) return false;
    var matriz = document.querySelector('.matrix-container');
    if (!matriz) return false;

    var agendado = false;
    var obs = new MutationObserver(function () {
      /* Um `requestAnimationFrame` de folga, não por elegância: o render
       * insere os bento-blocks um a um, e sem a folga o observador acorda
       * meio dozenas vezes para o mesmo render. */
      if (agendado) return;
      agendado = true;
      var correr = function () {
        agendado = false;
        try {
          aoMudar();
        } catch (e) {
          /* Um render que rebenta a meio não pode levar o observador com ele:
           * sem isto, uma exceção aqui calava o Chamado para o resto da
           * sessão, e o produtor ficava sem nenhuma pista de porquê. */
          if (window.console && console.warn) {
            console.warn('[AmpliaChamado] o observador do slot falhou:', e);
          }
        }
      };
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(correr);
      else setTimeout(correr, 0);
    });
    obs.observe(matriz, { childList: true, subtree: true });
    return true;
  }

  /* Liga o gancho e o observador, e insiste até RESULTAR.
   *
   * A primeira versão chamava `vigiaOSlot()` uma vez, no arranque, e aí está o
   * defeito: a matriz é criada por JavaScript, depois de os dados chegarem, e
   * num painel lento ela ainda não existe quando o módulo corre. O `vigiaOSlot`
   * fazia `return` — sem matriz, sem observador — e nunca mais voltava a
   * tentar.
   *
   * O resultado no ecrã era o pior possível: o Chamado não aparecia, e o módulo
   * não reclamava. Uma ausência que não é anunciada é uma mentira, e era
   * exatamente isso. Nos testes dentro da suite completa, que carrega dozens de
   * widgets em paralelo, a matriz chegava tarde e o widget nunca era semeado.
   *
   * Insiste até alguma das duas entrar. Se nenhuma entrar, desistimos — isto é
   * uma melhoria, e uma melhoria que não consegue aplicar-se não pode passar a
   * ser um bloqueio.
   */
  function ligaComInsistencia() {
    if (ligaComInsistencia.feito) return;
    if (instalaGancho() && vigiaOSlot()) {
      ligaComInsistencia.feito = true;
    }
  }

  /* O painel está a ser EDITADO?
   *
   * A única situação em que o widget não deve voltar é o produtor a tirá-lo à
   * mão. Distinguir as duas coisas é o que separa "o painel comeu o meu widget"
   * de "o produtor tirou-o": o primeiro é um render, o segundo é edição. */
  function emModoEdicao() {
    var w = window;
    return !!(w.widgetEditMode || (w.widgetbarState && w.widgetbarState.isCustomMode));
  }

  /* Embrulha o renderizador do painel.
   *
   * PORQUÊ UM EMBRULHO E NÃO O OBSERVADOR
   * -------------------------------------
   * O observador via a situação DEPOIS: o `.bento-block` já tinha desaparecido,
   * o contentor já não existia, e "o widget tinha de voltar" era uma conclusão.
   * O embrulho age no ANTES: a peça entra no layout, e o render que se segue
   * pinta-a. É a diferença entre restaurar uma coisa e reconstruir o estado de
   * que ela tinha saído.
   *
   * E embrulha-se o que estiver lá, e não uma função concreta: o `index.html`
   * redefine `window.renderWidgetsOnMatrix` DUAS vezes, e o que corre no fim é
   * a versão dele. Embrulhar a nossa seria embrulhar código morto.
   *
   * A instalação repete-se porque o `index.html` pode substituir a função
   * depois de nós a embrulharmos — e daí o `__chamado`: o embrulho de um
   * embrulho seria um render dentro de um render. */
  function instalaGancho() {
    var atual = window.renderWidgetsOnMatrix;
    if (typeof atual !== 'function' || atual.__chamado) return false;

    var embrulho = function () {
      /* ANTES: garante o lugar no layout. Fora do modo de edição, porque em
       * modo de edição a falta do widget é uma decisão do produtor. */
      if (!emModoEdicao()) {
        try {
          window.asseguraChamadoNoLayout();
        } catch (e) {
          /* Um layout que não se deixa mexer é um problema do painel, não
           * motivo para o painel deixar de pintar. */
        }
      }

      var r = atual.apply(this, arguments);

      /* DEPOIS: o contentor é novo, e novo não é desenhado.
       *
       * No PRÓXIMO QUADRO, e não aqui dentro. O `index.html` escreve o conteúdo
       * dos widgets em mais do que um momento — o que mediu isto foi um
       * contentor que ficava marcado como desenhado e vazio, com o texto
       * genérico por cima. Desenhar dentro da mesma chamada é desenhar antes
       * de o painel acabar. */
      try {
        agendaDesenho();
      } catch (e) {
        /* Igual: o painel já pintou, e pintar não pode falhar por nossa causa. */
      }
      return r;
    };
    embrulho.__chamado = true;
    embrulho.__original = atual;
    window.renderWidgetsOnMatrix = embrulho;
    return true;
  }

  /* Repete a instalação durante uns segundos.
   *
   * O `index.html` substitui `window.renderWidgetsOnMatrix` DUAS vezes, e os
   * momentos dessas substituições não são nossos: o gancho pode ser instalado
   * antes de elas acontecerem e ficar a embrulhar código morto. O observador
   * re-instala — mas só quando há uma MUTAÇÃO, e uma página que já pintou e não
   * volta a mexer não gera mutação nenhuma. Foi assim que o widget desaparecia
   * ao primeiro clique em "Atualizar": o gancho certo, sobre a função errada.
   *
   * Por isso, tentativas com prazo. Acabam quando o gancho entra, e mesmo que
   * nunca entrem param ao fim de `TENTATIVAS` é isto é uma melhoria, e uma
   * melhoria que não consegue aplicar-se não pode passar a ser um bloqueio. */
  var TENTATIVAS = 40;
  var INTERVALO_MS = 250;

  function instalaGanchoAteQueEntre() {
    var tentativas = 0;
    if (typeof setInterval !== 'function') return;
    var relogio = setInterval(function () {
      tentativas += 1;
      /* `ligaComInsistencia` é a que sabe o que "entrou" significa: o gancho
       * E o observador. Insistir só pelo gancho deixava o observador de fora,
       * e era o observador que segurava a peça quando o `index.html` trocava a
       * função. */
      ligaComInsistencia();
      if (ligaComInsistencia.feito || tentativas >= TENTATIVAS) {
        clearInterval(relogio);
      }
    }, INTERVALO_MS);
  }

  /* Desenha no próximo quadro, uma vez só por raf.
   *
   * Vários renders no mesmo quadro é ou um render que chama outro é não podem
   * enfileirar um desenho por cada um. Sem esta guarda, um painel que redesenha
   * cinco widgets fazia cinco desenhos da peça, e cada um limpava o anterior:
   * o primeiro a chegar era o último a ficar. */
  var desenhoAgendado = false;

  function agendaDesenho() {
    if (desenhoAgendado) return;
    desenhoAgendado = true;
    var correr = function () {
      desenhoAgendado = false;
      try {
        aposRenderWidgets();
      } catch (e) {
        if (window.console && console.warn) {
          console.warn('[AmpliaChamado] o desenho agendado falhou:', e);
        }
      }
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(correr);
    else setTimeout(correr, 0);
  }

  function carrega() {
    return pedir(API.ler).then(function (d) {
      estado.carregado = true;
      /* A zona de escrita vem do envelope, e não da peça: é uma regra do
         produto, não um estado da peça, e as duas coisas mudam por razões
         diferentes. */
      estado.zona = d && d.zona_escrita ? d.zona_escrita : null;
      ultimaPeca = d && d.chamado ? d.chamado : {};
      desenha(ultimaPeca);
      /* A matriz pode ainda nao ter desenhado. Se ja tiver, o slot existe e
         `desenha` entrou nele; se nao, `aposRenderWidgets` trata quando ela
         aparecer. E antes de tudo, pedir o lugar: um widget que nao esta no
         layout nao e desenhado por mais bem escrito que esteja o `desenha`. */
      if (pedeLugares()) desenha(ultimaPeca);
      aposRenderWidgets();
      emite('amplia:chamado-carregado', estado);
      return estado;
    });
  }

  /* --------------------------------------------------------------------------
     O QUE FAZ QUANDO A MATRIZ SE REDESENHA
     --------------------------------------------------------------------------
     `renderWidgetsOnMatrix` (dashboard-desktop.js) apaga e recria TODOS os
     `.bento-block` de cada vez que o painel muda. O contentor onde a peça foi
     desenhada deixa de existir — e o que fica é o fallback do
     `generateWidgetContent`, o texto genérico de um widget desconhecido.

     Sem isto, o painel acabava de desenhar a peça e um clique em qualquer
     lado a apagava. Não era um caso raro: qualquer `renderDashboardDesktop` com
     dados novos passa por ali.

     Este ponto de retorno é chamado de dentro desse `render`, não de um
     observador. Um `MutationObserver` aqui mediria a árvore inteira do
     dashboard para responder a uma chamada que se sabe quando acontece — e o
     que se sabe quando acontece chama-se, não se adivinha.
     -------------------------------------------------------------------------- */
  var ultimaPeca = null;

  /* O slot tem a PEÇA, ou só o texto de fallback?
   *
   * O marcador não chega, e o browser mostrou porque. A sequência real é:
   *
   *   1. o renderizador cria o `.widget-content` vazio;
   *   2. `aposRenderWidgets` desenha a peça e põe o marcador;
   *   3. o renderizador é mais tarde, ou noutro momento do mesmo render é
   *      escreve o texto genérico de widget desconhecido no MESMO contentor.
   *
   * O contentor fica marcado como desenhado e sem peça nenhuma. Um teste que
   * olhasse só para o marcador dizia que estava tudo bem, com o ecrã a mostrar
   * "Chamado da IA" ao produtor. Por isso o que se pergunta é "está a peça lá?",
   * e não "passou por aqui?".
   *
   * O `.amc-vazio` conta como desenho: é o estado legível de "ainda não há
   * peça", e é uma coisa que o produtor tem de conseguir ler. */
  function slotDesenhado(slot) {
    if (!slot) return false;
    if (slot.getAttribute('data-chamado-pronto') !== '1') return false;
    if (!slot.querySelector) return true; /* um DOM sem isto não se inspecciona */
    return !!(slot.querySelector('.amplia-chamado-cab') || slot.querySelector('.amc-vazio'));
  }

  function aposRenderWidgets() {
    if (!estado.carregado || !ultimaPeca) return false;
    var slot = slotDoWidget();
    if (!slot) return false;
    if (slotDesenhado(slot)) return false;
    desenha(ultimaPeca);
    return true;
  }

  /* --------------------------------------------------------------------------
     A WIDGET-BAR
     -------------------------------------------------------------------------- */
  var PRESET = {
    id: SLUG,
    name: NOME,
    description: 'A peca que a IA escreve. O teu unico preset onde ela pode mexer',
    category: 'Amplia',
    widgets: [],
    layout: 'grid-mixed',
    tags: ['ia', 'chamado'],
    fluida: true,
  };

  function registaPreset() {
    var wi = window.WidgetIntelligence;
    if (!wi || typeof wi.getPresets !== 'function') return false;
    if (wi.getPresets.__ampliaChamado) return true;
    var original = wi.getPresets;
    var embrulhado = function () {
      var lista;
      try {
        lista = original.apply(this, arguments) || [];
      } catch (e) {
        lista = [];
      }
      for (var i = 0; i < lista.length; i++) {
        if (lista[i] && lista[i].id === SLUG) return lista;
      }
      return [PRESET].concat(lista);
    };
    embrulhado.__ampliaChamado = true;
    embrulhado.__ampliaOriginal = original;
    wi.getPresets = embrulhado;
    return true;
  }

  function emite(evento, detalhe) {
    try {
      document.dispatchEvent(new CustomEvent(evento, { detail: detalhe }));
    } catch (e) {
      /* A peça já foi desenhada; perder o evento é melhor que perder a peça. */
    }
  }

  /* --------------------------------------------------------------------------
     ARRANQUE
     -------------------------------------------------------------------------- */
  window.AmpliaChamado = {
    SLUG: SLUG,
    NOME: NOME,
    MAX_BLOCOS: MAX_BLOCOS,
    estado: estado,
    carrega: carrega,
    desenha: desenha,
    hostEl: hostEl,
    /* Chamada de dentro de `renderWidgetsOnMatrix`, que apaga e recria os
       `.bento-block` todos. Sem isto, a peça desaparecia a cada redesenho do
       painel e voltava ao texto genérico de widget desconhecido. */
    aposRenderWidgets: aposRenderWidgets,
    garanteEstilo: garanteEstilo,
    registaPreset: registaPreset,
    exportaCsv: exportaCsv,
    /* Exportadas porque respondem a "existe aqui um caminho para pedir uma
       alteração?", e essa é uma pergunta que outro módulo pode precisar de
       fazer — e que o teste precisa de fazer, porque um botão que aceita o
       clique e não faz nada só se apanha chamando-o. */
    pedirChat: pedirChat,
    temPipelineDaIA: temPipelineDaIA,
    PRESET: PRESET,
    ROTULO_FONTE: ROTULO_FONTE,
  };

  document.addEventListener('amplia:palco-renderizado', function () {
    carrega();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      carrega();
      ligaComInsistencia();
      instalaGanchoAteQueEntre();
    });
  } else {
    carrega();
    ligaComInsistencia();
    instalaGanchoAteQueEntre();
  }
  /* E no `load`, porque a matriz pode pintar depois do DOM pronto: o painel
   * depende de dados que chegam de fora, e essa hora não é nossa. */
  if (window.addEventListener) {
    window.addEventListener('load', function () {
      /* Uma última tentativa. O `load` é o último momento em que se sabe que a
       * página ficou completa — e se a matriz só apareceu agora, é agora que o
       * observador se liga. */
      ligaComInsistencia();
      if (pedeLugares()) desenha(ultimaPeca);
      aposRenderWidgets();
    });
  }
  registaPreset();
})();
