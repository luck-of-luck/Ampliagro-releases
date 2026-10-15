/* ==========================================================================
   palco-amplia.js — o protocolo que o SmolLM2 usa para mandar a tela
   ==========================================================================

   POR QUE ISTO É UM FICHEIRO SEPARADO, E NÃO MAIS UM BLOCO NO ia-local.js
   ==========================================================================
   `ia-local.js` tem 5753 linhas e está a ser editado neste momento por outra
   sessão. Qualquer `edit` meu dentro dele seria uma colisão: ou o trabalho
   dela some, ou o meu, e a conflito resolve-se sempre com alguém a perder
   trabalho. Um módulo novo ao lado — `window.AmpliaPalco` — não partilha uma
   única linha com ela, e os dois podem mudar em paralelo sem que ninguém
   perca nada.

   Não é também uma questão de estilo. Este protocolo é o contrato entre a
   IA e a tela: quando ele muda, é porque o produto mudou. Ele merece um
   ficheiro que se lê inteiro, não um bloco perdido na terceira milhar.

   ==========================================================================
   O CONTRATO, EMUma LINHA
   ==========================================================================
   A IA não devolve uma tela. Devolve uma INTENÇÃO, e a tela é montada a partir
   do registo de widgets que já existe. Porquê, e o que ganhamos:

     - Um modelo de 1B a gerar HTML livre produz ids duplicados, CSS a vazar
       para o resto da página e zero histórico utilizável.
     - Compôr o registo existente dá renderizadores já testados, layout
       responsivo, e uma assinatura (pergunta → estrutura) que é a mesma
       unidade em todas as linhas do dataset de aprendizado.

   A IA é, portanto, uma mesa. O Alvo é a tela. O valor está nos DADOS.

   ==========================================================================
   O FORMATO QUE O MODELO EMITE
   ==========================================================================
   Um modelo de mil milhões de parâmetros não produz JSON rico de forma
   fiável. Tenta-se, falha-se, e o produtor recebe um traceback na pergunta
   mais importante do produto. Por isso o formato é o mais tolerante possível,
   e o servidor valida antes de guardar (ver `app/ia/palco.py`):

     ```amplia
     kpi-custo | Custo por hectare
     chart-financeiro | Custo contra receita
     table-financeiro
     ```

     - linhas separadas por QUEBRA DE LINHA, não por vírgula;
     - cada linha é TIPO [| TÍTULO];
     - um widget desconhecido é DESCARTADO, e a mesa é montada com o resto.

   Porquê tolerantemente? Porque "descartar o resto" é o comportamento certo
   numa tela. Um gráfico a mais não impede o produtor de ler a resposta; um
   erro de parse devolve uma página em branco e ele perde a confiança no
   produto inteiro.

   ==========================================================================
   O QUE ESTE MÓDULO NÃO FAZ
   ==========================================================================
   Não desenha widgets. Não conhece `WIDGET_TYPES`. Não inventa componentes.
   Ele traduz a intenção da IA para a carga útil canónica, envia ao servidor, e
   a renderização continua a ser a do dashboard. Se este ficheiro crescer um
   renderizador, é sinal de que ele está a fazer o trabalho errado.
   ========================================================================== */

(function () {
  'use strict';

  var API = {
    render: '/api/amplia/palco/render/',
    avaliar: '/api/amplia/palco/avaliar/',
    clonar: '/api/amplia/palco/clonar/',
    info: '/api/amplia/palco/info/',
  };

  var PALCO_SLUG = 'amplia';
  var MARCA = 'amplia';
  var CLASSE_GRID = 'amplia-palco-grid';
  var CLASSE_CARD = 'amplia-palco-card';

  /* --------------------------------------------------------------------------
     parseIntencao — extrai a intenção de um texto do modelo.

     Aceita três formatos, porque um modelo pequeno não é previsível e um
     produtor não pode pagar o preço de um `null` da IA. A ordem é da mais
     explícita para a mais tolerante:

       1. bloco ```amplia ... ``` com uma linha por widget  (ocanónico)
       2. bloco ```amplia ... ``` com JSON                 (o que a IA "quer" escrever)
       3. o texto cru, linha a linha                        (pior caso, ainda útil)

     Devolve sempre uma lista. Vazio é uma resposta válida: significa "a IA
     não mandou nada", e quem chama decide o que fazer — nunca lançamos.
     -------------------------------------------------------------------------- */
  function parseIntencao(texto) {
    var bruto = String(texto || '');
    if (!bruto.trim()) return [];

    var bloco = extrairBloco(bruto);
    if (!bloco) return linhaParaWidgets(bruto);
    if (pareceJSON(bloco)) return jsonParaWidgets(bloco);
    return linhaParaWidgets(bloco);
  }

  function extrairBloco(texto) {
    var re = new RegExp('```(?:' + MARCA + ')?[ \\t]*\\r?\\n([\\s\\S]*?)```', 'i');
    var m = texto.match(re);
    return m ? m[1] : null;
  }

  function pareceJSON(txt) {
    var t = String(txt || '').trim();
    return t.charAt(0) === '{' || t.charAt(0) === '[';
  }

  function jsonParaWidgets(txt) {
    var dados;
    try {
      dados = JSON.parse(txt);
    } catch (e) {
      /* JSON partido não é motivo para perder a mesa: cai na linha-a-linha. */
      return linhaParaWidgets(txt);
    }
    if (Array.isArray(dados)) return dados;
    if (dados && Array.isArray(dados.widgets)) return dados.widgets;
    return [];
  }

  function linhaParaWidgets(texto) {
    var saida = [];
    var linhas = String(texto || '').split(/\r?\n/);
    for (var i = 0; i < linhas.length; i++) {
      var ln = linhas[i].trim();
      if (!ln) continue;
      /* Ignora o resto do texto se o modelo "__acabou__" e voltou ao prosa.
         Uma frase como "espero que ajude!" depois da mesa não é um widget, e
         tratá-la como tal é a forma mais rápida de encher a tela de lixo. */
      if (/^[-#>*]/.test(ln) || ln.length > 120) continue;
      var partes = ln.split('|');
      var tipo = (partes[0] || '').trim();
      if (!/^[\w-]+$/.test(tipo)) continue;
      var w = { tipo: tipo };
      var titulo = (partes[1] || '').trim();
      if (titulo) w.titulo = titulo;
      if (partes.length > 2) {
        try {
          w.config = JSON.parse(partes.slice(2).join('|'));
        } catch (e) {
          /* config ilegível: o widget entra sem config, que o dashboard sabe
             tratar. Perder styling é melhor que perder o widget. */
        }
      }
      saida.push(w);
    }
    return saida;
  }

  /* --------------------------------------------------------------------------
     Estado do palco — o que está no ar AGORA, e o que o produtor pode avaliar.

     Isto é deliberadamente memória de sessão, e não localStorage. A mesa é
     efémera por definição: o que persiste é o que o produtor *aprova*, no
     botão "Salvar como meu Dashboard". Guardar a mesa automática em disco
     faria o dashboard de amanhã abrir com a resposta de ontem, sem ninguém
     ter pedido — e a pergunta "onde foi parar o meu painel?" sem resposta.
     -------------------------------------------------------------------------- */
  var estado = {
    widgets: [],
    layout: 'grid-mixed',
    intent: '',
    assinatura: '',
    origem: null,
  };

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function pedir(url, corpo) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      credentials: 'same-origin',
      body: JSON.stringify(corpo || {}),
    }).then(function (r) {
      if (!r.ok) throw new Error('palco: HTTP ' + r.status);
      return r.json();
    });
  }

  /* --------------------------------------------------------------------------
     render — a IA instrui a tela.

     Devolve uma promessa com o resultado do servidor. A tela é redesenhada
     pelo dashboard a partir de `widgets`; este módulo não desenha nada.
     -------------------------------------------------------------------------- */
  function render(intentTexto, widgets, opcoes) {
    var opts = opcoes || {};
    var lista = widgets && widgets.length ? widgets : parseIntencao(intentTexto);
    if (!lista.length) {
      return Promise.resolve({ ok: false, motivo: 'sem_widgets', widgets: [] });
    }
    return pedir(API.render, {
      intent: String(intentTexto || ''),
      widgets: lista,
      layout: opts.layout || 'grid-mixed',
      contexto: opts.contexto || {},
    })
      .then(function (d) {
        estado.widgets = d.widgets || [];
        estado.layout = d.layout || 'grid-mixed';
        estado.intent = String(intentTexto || '');
        estado.assinatura = d.assinatura || '';
        estado.origem = d.assinatura || null;
        desenhaMesa(estado.widgets);
        completaDadosTopGlobais(estado.widgets);
        emitir('amplia:palco-renderizado', estado);
        return d;
      })
      .catch(function (erro) {
        /* Falha de rede não pode levar o chat junto. O produtor continua a ler
           a resposta em texto, que é o que eleia de qualquer forma. */
        emitir('amplia:palco-erro', { erro: String(erro) });
        return { ok: false, motivo: 'erro', erro: String(erro), widgets: [] };
      });
  }

  /* --------------------------------------------------------------------------
     veredito — Like / Dislike.

     O Like é o sinal POSITIVO de aprendizado: grava (pergunta → estrutura) para
     a próxima vez acertar de primeira. O Dislike é o sinal NEGATIVO, e o
     produto trata os dois de forma assimétrica de propósito — o Like ensaia a
     estrutura, o Dislike devolve uma PERGUNTA, porque só o produtor sabe o que
     faltou.
     -------------------------------------------------------------------------- */
  function veredito(tipo, lacuna) {
    var t = tipo === 'dislike' ? 'dislike' : 'like';
    return pedir(API.avaliar, {
      assinatura: estado.assinatura,
      intent: estado.intent,
      estrutura: { widgets: estado.widgets, layout: estado.layout },
      veredito: t,
      lacuna: lacuna || '',
    }).then(function (d) {
      emitir('amplia:palco-veredito', { veredito: t, resposta: d });
      if (t === 'dislike') {
        /* O Dislike limpa a tela E devolve a pergunta. Não é castigo: é o
           produto a dizer "isto não era o que você queria, diz-me o quê era".
           Sem a pergunta de volta, o produtor fica com a tela apagada e sem
           saber o que fazer a seguir — e o aprendizado nunca recebe a lacuna,
           que é a parte mais valiosa do sinal. */
        limpar();
        var host = document.getElementById('amplia-palco-host');
        if (host && host.__ampliaPergunta) host.__ampliaPergunta();
      }
      return d;
    });
  }

  /* --------------------------------------------------------------------------
     clonar — "Salvar como meu Dashboard".

     Transforma a mesa efémera em algo do produtor. É o único caminho pelo qual
     widgets efémeros passam a persistir, e o servidor trata do slug e da
     unicidade por produtor.
     -------------------------------------------------------------------------- */
  function clonar(nome) {
    if (!estado.widgets.length) {
      return Promise.resolve({ ok: false, motivo: 'mesa_vazia' });
    }
    return pedir(API.clonar, {
      nome: String(nome || 'Minha mesa'),
      estrutura: { widgets: estado.widgets, layout: estado.layout },
      assinatura: estado.origem,
    }).then(function (d) {
      emitir('amplia:palco-clonado', d);
      return d;
    });
  }

  function limpar() {
    estado.widgets = [];
    estado.assinatura = '';
    estado.origem = null;
    emitir('amplia:palco-limpo', estado);
  }

  /* --------------------------------------------------------------------------
     A pergunta de volta, para o Dislike.

     O texto é FIXO de propósito. Se o produto mandar o modelo escrever a
     pergunta, um 1B escreve uma pergunta vaga ("o que faltou?") e o produtor
     percebe que o sistema não o ouviu. O guião é do produto; o modelo só o
     executa.
     -------------------------------------------------------------------------- */
  function perguntaDeVolta() {
    return (
      'Desculpe, o que faltou nesse relatório para eu montar algo útil?\n' +
      'Se responder em uma frase, eu refaço a mesa do zero.'
    );
  }

  function emitir(evento, detalhe) {
    try {
      document.dispatchEvent(new CustomEvent(evento, { detail: detalhe }));
    } catch (e) {
      /* CustomEvent não existe em browser muito antigo: a mesa já foi
         desenhada, e perder o evento é melhor que perder a mesa. */
    }
  }

  /* --------------------------------------------------------------------------
     A TELA — bento grid e os botões.

     ISOLAMENTO VISUAL
     =================
     Tudo o que este módulo cria vive dentro de UM contentor com prefixo
     `amplia-palco-`. Nenhuma classe é global, nenhum id colide com o dashboard,
     e nada é escrito em `document.body`. A razão não é conceptual: este ficheiro
     é novo, e a próxima coisa que alguém faz é juntar-lhe uma regra. Com
     escopo próprio, essa regra não alcança o resto da tela.

     E nada é escrito em `innerHTML`. Os TÍTULOS dos widgets vêm de um modelo de
     1B a responder a um produtor — é texto não-confiável, e injetá-lo como HTML
     é XSS com atraso. `textContent` em todos os títulos, sempre. (Ver também
     `tests_alerta_feed.cjs`, que cobre o mesmo risco no feed da BUILD 4.)
     -------------------------------------------------------------------------- */
  function garanteEstilo() {
    if (document.getElementById('amplia-palco-estilo')) return;
    var s = document.createElement('style');
    s.id = 'amplia-palco-estilo';
    s.textContent = [
      '.' +
        CLASSE_GRID +
        '{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));}',
      '.' +
        CLASSE_CARD +
        '{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);',
      'border-radius:12px;padding:12px;min-height:96px;display:flex;flex-direction:column;gap:6px;}',
      '.' + CLASSE_CARD + ' h4{margin:0;font-size:.82rem;opacity:.75;font-weight:600;}',
      '.amplia-palco-acoes{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}',
      '.amplia-palco-btn{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.2);',
      'color:inherit;border-radius:8px;padding:6px 12px;font-size:.8rem;cursor:pointer;}',
      '.amplia-palco-btn:hover{background:rgba(255,255,255,.16);}',
      '.amplia-palco-btn[aria-pressed="true"]{background:rgba(46,160,67,.35);border-color:rgba(46,160,67,.6);}',
      '.amplia-palco-btn[data-acao="salvar"]{border-color:rgba(255,193,7,.5);}',
      '.amplia-palco-vazio{opacity:.7;font-size:.85rem;padding:16px 0;}',
      /* No celular a grelha vira uma coluna, senão os cards ficam ilegíveis. */
      '.amplia-palco-dados{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:6px 0 0;}',
      '.amplia-palco-dados dt{font-size:.68rem;opacity:.6;}',
      '.amplia-palco-dados dd{margin:0;font-size:.9rem;font-weight:600;}',
      '.amplia-palco-serie{margin:6px 0 0;font-size:.68rem;opacity:.75;line-height:1.5;}',
      '.amplia-palco-vazio{margin:2px 0 0;font-size:.72rem;font-style:italic;',
      'opacity:.55;}',
      '.amplia-palco-simulado{margin-left:6px;font-size:.58rem;letter-spacing:.04em;',
      'text-transform:uppercase;padding:1px 5px;border-radius:6px;',
      'background:rgba(255,193,7,.18);border:1px solid rgba(255,193,7,.45);',
      'color:rgba(255,214,102,.95);font-weight:600;vertical-align:middle;}',
      '@media (max-width:640px){.' + CLASSE_GRID + '{grid-template-columns:1fr;}}',
    ].join('');
    document.head.appendChild(s);
  }

  function botao(texto, acao, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'amplia-palco-btn';
    b.setAttribute('data-acao', acao);
    b.textContent = texto;
    b.addEventListener('click', onClick);
    return b;
  }

  function desenhaMesa(widgets) {
    var host = hostEl();
    if (!host) return;
    garanteEstilo();
    host.textContent = '';

    /* A marca de simulado vem do CATÁLOGO do servidor, e é posta aqui antes
     * de desenhar: o valor só chega depois, e um card que ganhasse a marca
     * tarde deixaria de ser re-renderizado. */
    if (CATALOGO_PRONTO) {
      widgets.forEach(function (w) {
        var entrada = CATALOGO_MESA[w.tipo];
        if (entrada && entrada.simulado) w.simulado = true;
      });
    }

    if (!widgets || !widgets.length) {
      var vazio = document.createElement('p');
      vazio.className = 'amplia-palco-vazio';
      vazio.textContent = 'A IA não achou nada para montar aqui.';
      host.appendChild(vazio);
      return;
    }

    var grid = document.createElement('div');
    grid.className = CLASSE_GRID;
    for (var i = 0; i < widgets.length; i++) {
      var w = widgets[i];
      var card = document.createElement('article');
      card.className = CLASSE_CARD;
      card.setAttribute('data-tipo', w.tipo || '');
      var h = document.createElement('h4');
      /* textContent, nunca innerHTML: o título vem do modelo. */
      h.textContent = w.titulo || w.tipo || '';
      if (w.simulado) {
        /* O NÚMERO É INVENTADO, E DIZE-LO.
         *
         * Estes widgets vêm de `/api/top-globais/<id>/`, cujos handlers são
         * da primeira versão e recebem parâmetros FIXOS (talhao_id=1, lat=-15,
         * sacas=1000) sem nunca saber a quem perguntaram. A resposta agora
         * traz `fonte_dado: "simulado"`, e o card tem de carregar a marca.
         *
         * Um produtor que multiplica 50,4 sc/ha pela área dele, ou que
         * compare uma praga simulada com a fotografia do talhão, está a agir
         * sobre um número inventado — e o pior de um número inventado é que
         * não dá erro nenhum. */
        var s = document.createElement('span');
        s.className = 'amplia-palco-simulado';
        s.setAttribute(
          'title',
          'Valor simulado, sem ligação a sua propriedade. Nao use para decidir.'
        );
        s.textContent = 'simulado';
        h.appendChild(s);
      }
      var corpo = document.createElement('div');
      corpo.className = 'amplia-palco-corpo';
      desenhaDados(corpo, w);
      card.appendChild(h);
      card.appendChild(corpo);
      grid.appendChild(card);
    }
    host.appendChild(grid);
    host.appendChild(barraAccoes());
  }

  /* Os widgets que NÃO são agregados do servidor têm o seu próprio endpoint.
     O campo `fonte` do catálogo é o que diz quais — e o navegador vai buscá-los
     depois de a mesa estar no ecrã, para não atrasar o primeiro desenho.
     Pedir isto também ao servidor significaria o mesmo número por dois
     caminhos, e dois valores diferentes na mesma tela. */
  function completaDadosTopGlobais(widgets) {
    if (!widgets || !widgets.length) return;
    var pendentes = [];
    widgets.forEach(function (w, i) {
      var entrada = CATALOGO_MESA[w.tipo];
      if (
        entrada &&
        entrada.fonte === 'top_globais' &&
        !(w.config && Object.keys(w.config).length)
      ) {
        pendentes.push({ i: i, tipo: w.tipo });
      }
    });
    if (!pendentes.length) return;

    pendentes.forEach(function (p) {
      fetch('/api/top-globais/' + encodeURIComponent(p.tipo) + '/', { credentials: 'same-origin' })
        .then(function (r) {
          return r.ok ? r.json() : null;
        })
        .then(function (j) {
          if (!j) return;
          var d = j.data || j;
          var valor = d.valor;
          if (valor === undefined || valor === null) {
            valor = d.numero;
            if (valor === undefined) valor = d.total;
          }
          /* Sem valor, o card continua vazio. Um "-" no lugar do dado é
             pior do que um card a menos. */
          if (valor === undefined || valor === null || valor === '') return;
          widgets[p.i].config = { valor: valor };
          /* A origem decide se o numero entra como verdade ou como
             simulacao. Uma tela bonita com numeros inventados e' pior do
             que uma tela a dizer que nao sabe. */
          if (j.fonte_dado === 'simulado') widgets[p.i].simulado = true;
          redesenha(widgets);
        })
        .catch(function () {
          /* sem dado, o card fica vazio: honesto */
        });
    });
  }

  var ULTIMA_MESA = [];

  function redesenha(widgets) {
    ULTIMA_MESA = widgets || [];
    desenhaMesa(ULTIMA_MESA);
  }

  /* O QUE O PRODUTOR VÊ: rótulos em português e números como números.
   *
   * O backend entrega chaves de campo cruas — `custo_por_ha`, `area_colhida` —
   * porque são o contrato entre o servidor e o ecrã. Mas "custo_por_ha:
   * 176.33" na tela é lixo: o produtor não sabe o que aquilo é, e uma mesa
   * ilegível é uma mesa que ele deixa de olhar.
   *
   * A formatação também não é enfeite. `Intl.NumberFormat` com pt-BR põe o
   * separador de milhar e a vírgula decimal CERTO — e o produtor compara
   * esse número com a nota que tem no papel. Um `176.33` lido como mil
   * setecentos e sessenta e três, ou `176,33` lido como centésimos, são erros
   * que fazem ele desconfiar da IA inteira.
   */
  var ROTULOS = {
    custo_total: 'Custo total',
    custo_por_ha: 'Custo por hectare',
    area_plantada: 'Área plantada',
    area_colhida: 'Área colhida',
    area_downtime: 'Área em downtime',
    entradas: 'Entradas',
    saidas: 'Saídas',
    saldo: 'Saldo',
    receita_total: 'Receita',
    producao_total: 'Produção',
    produtividade_ha: 'Produtividade (t/ha)',
    roi_pct: 'ROI (%)',
    safras: 'Safras lançadas',
    valor: 'Valor',
    periodo: 'Período',
    lancamentos: 'Lançamentos',
    total: 'Total',
    criticos: 'Críticos',
    atencao: 'Atenção',
    informativos: 'Informativos',
  };

  var CAMPOS_MOEDA = {
    custo_total: 1,
    entradas: 1,
    saidas: 1,
    saldo: 1,
    receita_total: 1,
    total: 1,
  };
  var CAMPOS_AREA = { area_plantada: 1, area_colhida: 1, area_downtime: 1 };

  var fmtMoeda = null;
  var fmtNum = null;
  function formatadores() {
    if (fmtMoeda) return;
    try {
      fmtMoeda = new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
        maximumFractionDigits: 2,
      });
      fmtNum = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });
    } catch (e) {
      fmtMoeda = null;
      fmtNum = null;
    }
  }

  function formata(chave, valor) {
    if (valor === null || valor === undefined || valor === '') return '—';
    if (typeof valor === 'boolean') return valor ? 'sim' : 'não';
    if (typeof valor === 'number' || typeof valor === 'bigint') {
      formatadores();
      var n = Number(valor);
      if (!isFinite(n)) return String(valor);
      if (CAMPOS_MOEDA[chave] && fmtMoeda) return fmtMoeda.format(n);
      if (CAMPOS_AREA[chave] && fmtNum) return fmtNum.format(n) + ' ha';
      if (fmtNum) return fmtNum.format(n);
      return String(valor);
    }
    /* Uma série ou uma tabela é resumida em texto: o card é pequeno, e uma
       tabela dentro de um card de KPI é ilegível nos dois sítios. */
    if (Array.isArray(valor)) {
      if (!valor.length) return '—';
      return valor.length + (valor.length === 1 ? ' registo' : ' registos');
    }
    if (typeof valor === 'object') return Object.keys(valor).length + ' campos';
    return String(valor);
  }

  function desenhaDados(alvo, w) {
    var cfg = w && w.config;
    if (!cfg || typeof cfg !== 'object') return;

    var linhas = [];
    var i, k, v;
    for (k in cfg) {
      if (!Object.prototype.hasOwnProperty.call(cfg, k)) continue;
      v = cfg[k];
      if (v === null || v === undefined || v === '') continue;
      if (k === 'series' || k === 'linhas') continue; /* tem render próprio */
      if (typeof v === 'object' && !Array.isArray(v)) continue;
      linhas.push({ k: k, v: v });
      if (linhas.length >= 6) break;
    }

    /* `sem_dado` é um booleano, por isso passa o filtro de `null` e caía na
     * lista como se fosse um valor. O produtor via uma linha a dizer
     * "sem_dado: sim" ao lado dos números reais do mesmo cartão — uma linha
     * de debug em produção, e pior: uma que se pode ler como "sem dados: há
     * um sim", quando o que o servidor quis dizer é "o cartão está vazio".
     *
     * Não é uma linha: é a ausência de linhas. E a ausência tem de ser
     * VISÍVEL — um cartão que não mostra nada não se distingue de um cartão
     * que a IA esqueceu. Por isso desenhamos "sem dado" no lugar. */
    if (cfg.sem_dado === true) {
      var vazio = document.createElement('p');
      vazio.className = 'amplia-palco-vazio';
      vazio.textContent = 'sem dado';
      vazio.setAttribute(
        'title',
        'Nao existe medicao para este dado. Um zero aqui diria que o valor e zero.'
      );
      alvo.appendChild(vazio);
      return;
    }

    if (!linhas.length) return;

    var lista = document.createElement('dl');
    lista.className = 'amplia-palco-dados';
    for (i = 0; i < linhas.length; i++) {
      var dt = document.createElement('dt');
      dt.textContent = ROTULOS[linhas[i].k] || linhas[i].k;
      var dd = document.createElement('dd');
      /* textContent, sempre: o valor veio do banco E o rótulo pode ter vindo
         do modelo. innerHTML aqui seria XSS com atraso. */
      dd.textContent = formata(linhas[i].k, linhas[i].v);
      lista.appendChild(dt);
      lista.appendChild(dd);
    }
    alvo.appendChild(lista);

    /* A série e a tabela recebem um render próprio, e curto: o que interessa
       é a forma da evolucao, não a lista completa. */
    if (Array.isArray(cfg.series) && cfg.series.length) {
      alvo.appendChild(resumoSerie(cfg.series));
    }
    if (Array.isArray(cfg.linhas) && cfg.linhas.length) {
      alvo.appendChild(resumoTabela(cfg.linhas, cfg.colunas));
    }
  }

  function resumoSerie(serie) {
    var p = document.createElement('p');
    p.className = 'amplia-palco-serie';
    var partes = [];
    for (var i = 0; i < serie.length && i < 4; i++) {
      var l = serie[i] || {};
      var etiqueta = l.ano != null ? l.ano : l.periodo || i + 1;
      var valor =
        l.produtividade != null ? l.produtividade : l.producao != null ? l.producao : l.valor;
      if (valor == null) continue;
      partes.push(String(etiqueta) + ': ' + formata('producao', valor));
    }
    p.textContent = partes.length ? partes.join('  ·  ') : serie.length + ' pontos';
    return p;
  }

  function resumoTabela(linhas, colunas) {
    var p = document.createElement('p');
    p.className = 'amplia-palco-serie';
    var cab = (colunas || []).slice(0, 3);
    var partes = [];
    for (var i = 0; i < linhas.length && i < 3; i++) {
      var l = linhas[i] || {};
      var pedacos = [];
      for (var j = 0; j < cab.length; j++) {
        var chave = cab[j];
        var v = l[chave];
        if (v === undefined || v === null || v === '') continue;
        pedacos.push(String(v));
      }
      if (pedacos.length) partes.push(pedacos.join(' · '));
    }
    p.textContent = partes.length ? partes.join('  |  ') : linhas.length + ' linhas';
    return p;
  }

  /* Os três botões: o Like e o Dislike ensinam a IA, o Salvar dá a mesa ao
   * produtor. A ordem é essa e não outra — é a ordem em que se lê. */
  function barraAccoes() {
    var barra = document.createElement('div');
    barra.className = 'amplia-palco-acoes';

    barra.appendChild(
      botao('Boa mesa', 'like', function (e) {
        e.currentTarget.setAttribute('aria-pressed', 'true');
        veredito('like');
      })
    );
    barra.appendChild(
      botao('Faltou algo', 'dislike', function (e) {
        e.currentTarget.setAttribute('aria-pressed', 'true');
        /* A lacuna vem do produtor, no texto que ele escrever. Aqui dispara-se
           a pergunta; quem tem o chat (o ia-local) é que a faz. */
        var lacuna = window.prompt(perguntaDeVolta());
        if (lacuna === null) {
          e.currentTarget.setAttribute('aria-pressed', 'false');
          return;
        }
        veredito('dislike', lacuna);
      })
    );
    barra.appendChild(
      botao('Salvar como meu Dashboard', 'salvar', function () {
        var nome = window.prompt('Nome do dashboard', 'Minha mesa');
        if (!nome) return;
        clonar(nome);
      })
    );
    return barra;
  }

  function hostEl() {
    var host = document.getElementById('amplia-palco-host');
    if (!host) {
      host = document.createElement('section');
      host.id = 'amplia-palco-host';
      host.className = 'amplia-palco';
      ancoraDoPalco().appendChild(host);
    }
    return host;
  }

  /* --------------------------------------------------------------------------
     O FIO: como a instrução da IA chega à tela.

     HÁ UM CONFLITO REAL AQUI, E ELE MATAVA O PROTOCOLO
     ====================================================
     A primeira versão deste módulo dependia de o modelo escrever um bloco
     ```amplia``` no texto. Isso nunca chegaria ao ecrã: `ia-local.js` passa a
     resposta por `sanitizarResposta`, que remove cercas ``` e todo o JSON
     ANTES de qualquer consumidor a ver. O bloco era apagado a montante, e o
     protocolo — testado, bem escrito, e morto.

     A via certa já existia e é melhor: a IA pede uma TOOL, a tool é um intent
     no sandbox do servidor, o sandbox valida e devolve `dados`, e o palco
     monta-se a partir disso. Benefícios que a cerca não dava: a chamada fica
     na auditoria, os widgets são validados no servidor, e o modelo nunca
     escreve HTML.

     E `iaToolCall` — o caminho antigo — foi DESLIGADA de propósito: saltava o
     sandbox e acionações físicas sem confirmação.

     COMO SE LIGA SEM TOCAR NO ia-local.js
     ======================================
     O `ia-local.js` tem 5753 linhas e está a ser editado por outra sessão. Em
     vez de inserir uma chamada num ficheiro que não é meu, este módulo
     ENVOLVE o `fetch` do host e observa as respostas de `/api/amplia/exec/`.
     É um decorador sobre a E/S de um anfitrião que não controlo: leio o que
     ele envia, não altero o que ele envia.

     Só procura a sua própria marca (`dados.palco === 'amplia'`). Não há
     adivinhação: qualquer outra resposta do sandbox passa intacta, e a
     ferramenta que o produtor pediu continua a ser a que ele pediu.
     -------------------------------------------------------------------------- */
  var ENVOLVIDO = '__ampliaPalcoFetch';

  function espiaExec() {
    if (typeof window.fetch !== 'function') return false;
    if (window.fetch[ENVOLVIDO]) return true; /* já envolvido: idempotente */
    var original = window.fetch;
    var embrulhado = function () {
      var argumentos = arguments;
      var p = original.apply(window, argumentos);
      /* Um spy que levanta rejeição apaga a tela do produtor. Devolve sempre
         a promessa original, intocada. */
      if (!p || typeof p.then !== 'function') return p;
      return p.then(function (resposta) {
        try {
          vigia(resposta);
        } catch (e) {
          /* Observar nunca pode partir quem observa. */
        }
        return resposta;
      });
    };
    embrulhado[ENVOLVIDO] = true;
    embrulhado.__ampliaOriginal = original;
    window.fetch = embrulhado;
    return true;
  }

  var ULTIMO_DADOS = null;

  function vigia(resposta) {
    if (!resposta || typeof resposta.clone !== 'function') return;
    if (!/\/api\/(amplia\/exec|ia\/executar)\//.test(String(resposta.url || ''))) return;
    if (resposta.headers && resposta.headers.get('x-amplia-palco-consumido') === '1') return;

    resposta
      .clone()
      .json()
      .then(function (corpo) {
        if (!corpo || corpo.ok === false) return;
        if (corpo.dados && Array.isArray(corpo.dados.presets_atualizados)) {
          registarPresetsGuardados(corpo.dados.meus_presets, true);
        }

        /* CAMINHO 1 — a composição de topo (Fase 1).
         *
         * O handler que respondeu à pergunta anexa a mesa que quer mostrar. Não
         * é um intent separado: é o mesmo, e por isso o `dados` que volta para
         * o modelo é o mesmo — a pergunta e a resposta ficam ligadas.
         *
         * Vem ANTES do `dados.palco` de propósito: uma composição é explícita,
         * e o palco é o caminho antigo, de quando a IA tinha de chamar
         * `render_preset` à mão. Quando os dois vêm, quem manda é a composição. */
        var composicao = normalizaComposicao(corpo.widget_composicao);
        if (composicao && composicao.length) {
          marcarConsumido(resposta);
          estado.widgets = composicao;
          estado.layout = 'grid-mixed';
          estado.intent = '';
          estado.assinatura = '';
          estado.origem = null;
          desenhaMesa(estado.widgets);
          completaDadosTopGlobais(estado.widgets);
          emitir('amplia:palco-renderizado', estado);
          return;
        }

        /* CAMINHO 2 — o palco de sempre. */
        var dados = corpo.dados;
        if (!dados || dados.palco !== PALCO_SLUG) return; /* não é o palco */
        ULTIMO_DADOS = dados;
        marcarConsumido(resposta);
        montarDoServidor(dados);
      })
      .catch(function () {
        /* resposta sem JSON, ou falso: nada a fazer */
      });
  }

  /* A marca de "esta resposta já foi vista pelo palco".
   *
   * O `dados` continua a seguir para o modelo como contexto — é isso que faz a
   * IA narrar a mesa em vez de repetir widgets. Consumir a resposta inteira faria
   * o modelo cego, e a pergunta seguinte perderia o fio. */
  function marcarConsumido(resposta) {
    try {
      resposta.headers.set('x-amplia-palco-consumido', '1');
    } catch (e) {
      /* headers imutavel: irrelevante, a guarda e' so Optimization. */
    }
  }

  function montarDoServidor(dados) {
    estado.widgets = dados.widgets || [];
    estado.layout = dados.layout || 'grid-mixed';
    estado.intent = dados.intent || '';
    estado.assinatura = dados.assinatura || '';
    estado.origem = dados.assinatura || null;
    desenhaMesa(estado.widgets);
    completaDadosTopGlobais(estado.widgets);
    emitir('amplia:palco-renderizado', estado);
  }

  /* --------------------------------------------------------------------------
     A INTELIGÊNCIA: o que o modelo precisa de saber, e onde isso lhe é dito.

     POR QUE ESTE MÓDULO ENSINA O MODELO
     =====================================
     Um SmolLM2 de 1B não "descobre" uma tool. Ele só faz o que o prompt lhe
     diz. E o prompt do sistema do `ia-local.js` lista as tools à mão — com
     exemplos, um por linha.

     Verifiquei essa lista: `navegar`, `consultar`, `criar`, `iniciar_cadastro`,
     `irrigacao`, `atualizar`, `excluir`, `relatorio`, `buscar_web`. O palco não
     está lá. E mais: NENHUMA chamada ao modelo passa `tools:` — o catálogo é
     buscado em `/api/amplia/tools/`, guardado em cache, e nunca usado numa
     inferência. O modelo via o prompt, não o catálogo.

     Por isso "a IA não desenvolve os widgets" não era o modelo a ser burro.
     Era ninguém lhe ter dito que isto existia. Este módulo acrescenta a
     instrução, no prompt que ele já lê, pela porta que ele já usa.

     E NÃO É UM SEGUNDO PROMPT
     ========================
     Acrescenta-se ao `systemContent` que já existe, em vez de o substituir. Um
     prompt a mais seria um prompt a menos para o modelo, num motor com 4096
     tokens e `max_tokens: 256`. Aqui juntam-se ~40 linhas, e só quando a
     pergunta cheira a analítica.

     SÓ QUANDO A PERGUNTA MERECE
     ===========================
     Seria fácil mandar montar uma mesa em todas as perguntas. Seria um erro: um
     produtor a perguntar "vai chover" receberia um dashboard em vez de uma
     previsão, e no dia seguinte parava de acreditar na IA.      A triagem é barata e previsível — o modelo só recebe a instrução quando há
     comparação, histórico, evolução ou resumo na pergunta.

     COMO SE LIGA SEM TOCAR NO ia-local.js
     ======================================
     Embrulha-se `engine.chat.completions.create`, o mesmo padrão de decorador
     sobre a E/S de um anfitrião. Lê-se o pedido, acrescenta-se o que falta,
     e o pedido segue intacto. O `ia-local.js` continua a chamar exactamente a
     mesma coisa — a sua ponte híbrida, os seus testes e o seu fallback do bloco
     markdown continuam a funcionar sem uma linha alterada.
     -------------------------------------------------------------------------- */
  var MOTOR_ENCOLHIDO = '__ampliaPalcoMotor';
  var TENTATIVAS_MOTOR = 0;
  var MAX_TENTATIVAS_MOTOR = 60; /* ~1 min, enquanto o WebLLM carrega os pesos */

  /* O que faz a pergunta pedir uma mesa. SÃO RAÍZES, não frases prontas, e o
     texto é normalizado antes da comparação — acento incluido.
     A primeira versão casava "por mês" e falhava com "neste mes". Numa app em
     português isso não é um caso raro, é o caso normal: metade dos produtores
     escreve sem acento no telemóvel. A mesma lição da assinatura de
     aprendizado, reaplicada aqui porque é o mesmo bug noutro sitio. */
  var GATILHOS = [
    'histor',
    'evolu',
    'compar',
    'versus',
    'tenden',
    'grafico',
    'tabela',
    'painel',
    'dashboard',
    'relatorio',
    'resumo',
    'consolidad',
    'serie',
    'temporal',
    'ano a ano',
    'safra',
    'custo',
    'custos',
    'receita',
    'despesa',
    'lucro',
    'margem',
    'rendimento',
    'desempenh',
    'produtividade',
    'area',
    'balanc',
    'fluxo de caixa',
    'investimento',
    'retorno',
    'por mes',
    'neste mes',
    'neste ano',
    'ultimos',
    'ultimas',
    'por dia',
    'por semana',
    'rende',
    'ganho',
    'gasto',
  ];

  /* A previsão é o caso em que um dashboard é o pior sítio para gastar
     confiança. Fica de fora mesmo quando a frase traz "gráfico". */
  var NEGATIVOS = [
    'vai chover',
    'vai chove',
    'chove',
    'chuva hoje',
    'chuva amanha',
    'temperatura agora',
    'temperatura de',
    'clima agora',
    'clima de',
    'umidade',
    'vento',
    'qual a temperatura',
    'esta frio',
    'esta quente',
  ];

  /* Tira acento: "histórico" e "historico" têm de dar o mesmo resultado, e a
     comparação tem de ser feita sobre a forma sem acento. */
  function normaliza(texto) {
    var s = String(texto || '').toLowerCase();
    if (s.normalize) {
      try {
        s = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
      } catch (e) {
        /* NFD indisponivel: segue com o texto como esta. */
      }
    }
    return s;
  }

  /* A `widget_composicao` que o servidor mandou, ja em forma de widgets.
   *
   * `normaliza()` normaliza TEXTO (acentos, para o `querMesa`) — nao serve aqui.
   * Esta funcao faz o outro lado: garante que e' lista, que cada item tem `tipo`,
   * e que nao ha repetidos nem mais de 8. O servidor ja normalizou e ja cortou
   * (`sandbox._normalizar_composicao`); repetir aqui e' defesa em profundidade,
   * e nao desperdicio — e' o mesmo contrato em duas linguagens, que e' como o
   * resto deste modulo esta escrito (`parseIntencao` tambem valida o que o
   * modelo devolve). */
  function normalizaComposicao(bruta) {
    var lista = bruta;
    if (lista && !Array.isArray(lista) && Array.isArray(lista.widgets)) {
      lista = lista.widgets;
    }
    if (!Array.isArray(lista)) return [];
    var saida = [];
    var vistos = {};
    for (var i = 0; i < lista.length && saida.length < 8; i++) {
      var item = lista[i];
      if (!item || typeof item !== 'object') continue;
      var tipo = String(item.tipo || item.type || '').trim();
      if (!tipo || vistos[tipo]) continue;
      /* Um id que o servidor inventou e' ruido na tela. A fronteira real continua
         a ser `palco.validar_estrutura` no servidor; aqui so descartamos o que nem
         tem forma de widget, para o `desenhaMesa` nao fazer trabalho a toa. */
      if (!/^[\w-]+$/.test(tipo)) continue;
      vistos[tipo] = true;
      var w = { tipo: tipo };
      if (item.titulo) w.titulo = String(item.titulo).slice(0, 120);
      /* `typeof []` e' 'object' em JavaScript — um array passa a primeira vista
       * e so rebenta depois, em quem consumir o config. O Python ja' recusa
       * (`sandbox._normalizar_composicao`: `isinstance(cfg, dict)`), e um lado
       * aceitar o que o outro recusa e' como os dois lados divergem. */
      if (item.config && typeof item.config === 'object' && !Array.isArray(item.config)) {
        w.config = item.config;
      }
      saida.push(w);
    }
    return saida;
  }

  function querMesa(pergunta) {
    var p = normaliza(pergunta);
    if (!p.trim()) return false;
    var i;
    for (i = 0; i < NEGATIVOS.length; i++) {
      if (p.indexOf(NEGATIVOS[i]) !== -1) return false;
    }
    for (i = 0; i < GATILHOS.length; i++) {
      if (p.indexOf(GATILHOS[i]) !== -1) return true;
    }
    return false;
  }

  /* O CATÁLOGO VEM DO SERVIDOR. Não desta ficha.
   *
   * A primeira versão trazia aqui uma lista de catorze ids escrita à mão, e
   * era mentira: `kpi-custo` e `chart-financeiro` são entradas de LAYOUT do
   * dashboard, não widgets com dados. `/api/top-globais/kpi-custo/` responde
   * 404 "widget desconhecido". O modelo era conduzido a escolher widgets que
   * a camada de dados nunca conheceu — e a mesa montava com títulos e zeros.
   *
   * `/api/amplia/palco/info/` devolve o catálogo com a FONTE de cada widget.
   * Uma lista própria é uma segunda verdade, e a segunda verdade sempre
   * diverge. */
  var CATALOGO_MESA = {}; /* preenchido por carregaCatalogo() */
  var CATALOGO_PRONTO = false;

  /* Enquanto o servidor não responde, isto é o mínimo honesto: os agregados
     do servidor, que são os que respondem a "custo", "safra", "produção". */
  var CATALOGO_MINIMO = {
    'kpi-custo': 'Custo total e custo por hectare',
    'kpi-caixa': 'Fluxo de caixa: entradas, saídas e saldo',
    'kpi-roi': 'Retorno sobre investimento',
    'kpi-produtividade': 'Produção por hectare',
    'kpi-area': 'Área plantada e colhida',
    'chart-safras': 'Produção e produtividade por ano',
    'table-financeiro': 'Lançamentos financeiros por categoria',
    'kpi-alertas': 'Alertas abertos por severidade',
  };

  function idsDoCatalogo() {
    var chaves = Object.keys(CATALOGO_MESA);
    return chaves.length ? chaves : Object.keys(CATALOGO_MINIMO);
  }

  function carregaCatalogo() {
    if (CATALOGO_PRONTO) return Promise.resolve(CATALOGO_MESA);
    return fetch(API.info, { credentials: 'same-origin' })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        var cat = d && d.catalogo;
        if (cat && !Array.isArray(cat) && typeof cat === 'object') {
          CATALOGO_MESA = cat;
          CATALOGO_PRONTO = true;
        }
        // Os presets guardados entram no menu AQUI, e não mais tarde: este é o
        // primeiro momento em que a lista chega ao cliente, e registá-los num
        // `.then()` separado seria correr o risco de um dos dois ficar em
        // espera se o outro falhasse.
        registarPresetsGuardados(d && d.meus_presets);
        return CATALOGO_MESA;
      })
      .catch(function () {
        /* Sem catálogo do servidor, fica o mínimo. A mesa ainda funciona para
           as perguntas financeiras, que são as mais feitas. */
        CATALOGO_MESA = CATALOGO_MINIMO;
        return CATALOGO_MESA;
      });
  }

  /* O que o modelo pode montar. Curto de propósito: um catálogo de 75 schemas
     estoura o contexto; este são os 14 que servem uma mesa, e é o que a tool
     valida no servidor. */
  function blocoInstrucao() {
    var ids = idsDoCatalogo();
    return [
      '',
      '',
      'MESA DE OPERACAO (para perguntas de NUMEROS)',
      'Se a pergunta pede COMPARACAO, HISTORICO, EVOLUCAO ou RESUMO de numeros,',
      'NAO escrevas um paragrafo: monta uma mesa no preset Amplia.',
      'Responde assim, e depois explica em UMA frase curta:',
      '',
      '```amplia',
      'tipo-do-widget | Titulo curto',
      '```',
      '',
      'Widgets que pode usar: ' + ids.join(', ') + '.',
      'Escolha 2 a 5. Repita um tipo de cada vez, nao dois.',
      'Depois da mesa, responda ao produtor em PT-BR, no maximo 1 frase.',
      'Para pergunta de SIM/NÃO ou valor unico, NAO monte mesa.',
      '',
    ].join('\n');
  }

  /* O mesmo catalogo, no formato que a sandbox valida. Uma tool, nao 75. */
  function schemaDaTool() {
    return {
      type: 'function',
      function: {
        name: 'amplia_render_preset',
        description:
          'Monta uma mesa de operacao no preset Amplia. Use para perguntas de ' +
          'numeros que pedem comparacao, historico, evolucao ou resumo. NAO use ' +
          'para pergunta de sim/nao.',
        parameters: {
          type: 'object',
          properties: {
            widgets: {
              type: 'array',
              description: 'Widgets a montar, 2 a 5.',
              items: {
                type: 'object',
                properties: {
                  tipo: { type: 'string', enum: idsDoCatalogo() },
                  titulo: { type: 'string' },
                },
                required: ['tipo'],
              },
            },
            intent: { type: 'string', description: 'A pergunta do produtor.' },
            layout: { type: 'string' },
          },
          required: ['widgets'],
        },
      },
    };
  }

  function ligaMotor() {
    var ia = window.__ampliaIa;
    var motor = ia && typeof ia.engine === 'function' ? ia.engine() : null;
    /* `obterIaEngine` devolve null enquanto o WebLLM carrega. E' por isso que
       isto se repete: o motor nao existe no arranque da pagina. */
    if (!motor || !motor.chat || !motor.chat.completions) return false;
    var create = motor.chat.completions.create;
    if (!create || create[MOTOR_ENCOLHIDO]) return true;

    var embrulhado = function (pedido) {
      var p = pedido || {};
      var mensagens = p.messages || [];
      var system = '';
      var ultima = '';
      for (var i = 0; i < mensagens.length; i++) {
        if (mensagens[i].role === 'system') system = mensagens[i].content || '';
        if (mensagens[i].role === 'user') ultima = mensagens[i].content || '';
      }
      if (system && querMesa(ultima) && system.indexOf('MESA DE OPERACAO') === -1) {
        p = Object.assign({}, p, {
          messages: mensagens.map(function (m) {
            return m.role === 'system'
              ? Object.assign({}, m, { content: m.content + blocoInstrucao() })
              : m;
          }),
          /* Uma tool, e nao o catalogo inteiro. O servidor valida o que vier. */
          tools: p.tools || [schemaDaTool()],
        });
      }
      return create.call(motor.chat.completions, p);
    };
    embrulhado[MOTOR_ENCOLHIDO] = true;
    embrulhado.__ampliaOriginal = create;
    motor.chat.completions.create = embrulhado;
    return true;
  }

  function vigiaMotor() {
    if (ligaMotor()) return true;
    if (TENTATIVAS_MOTOR++ >= MAX_TENTATIVAS_MOTOR) return false;
    setTimeout(vigiaMotor, 1000);
    return false;
  }

  /* --------------------------------------------------------------------------
     O PRESET "AMPLIA" NO MENU
     --------------------------------------------------------------------------
     `WidgetIntelligence.getPresets()` devolve um array CODIFICADO no ficheiro.
     O palco, que vive no servidor, nunca aparecia nele — e sem aparecer, o
     produtor não tem palco nenhum para onde olhar.

     Regista-se por cima do método, e não por dentro do array: assim o ficheiro
     partilhado não é tocado, e se amanhã existir um preset "Amplia" de verdade
     no código, o registo simplesmente cede-lhe o lugar. */
  var REGISTO_PRESET = '__ampliaPalcoPreset';

  var PRESET_AMPLIA = {
    id: 'amplia',
    name: 'Amplia',
    icon: 'bi-stars',
    description: 'A mesa de operacao que a IA monta para a sua pergunta',
    category: 'Amplia',
    widgets: [],
    layout: 'grid-mixed',
    tags: ['ia', 'palco'],
    fluida: true,
  };

  function registaPreset() {
    var wi = window.WidgetIntelligence;
    if (!wi || typeof wi.getPresets !== 'function') return false;
    if (wi.getPresets[REGISTO_PRESET]) return true;
    var original = wi.getPresets;
    var embrulhado = function () {
      var lista;
      try {
        lista = original.apply(this, arguments) || [];
      } catch (e) {
        lista = [];
      }
      for (var i = 0; i < lista.length; i++) {
        if (lista[i] && lista[i].id === PRESET_AMPLIA.id) return lista;
      }
      return [PRESET_AMPLIA].concat(lista);
    };
    embrulhado[REGISTO_PRESET] = true;
    embrulhado.__ampliaOriginal = original;
    wi.getPresets = embrulhado;
    return true;
  }
  /* O palco no sítio certo: dentro do painel, e não colado ao body. */
  function ancoraDoPalco() {
    return (
      document.getElementById('amplia-palco-ancora') ||
      document.getElementById('content') ||
      document.body
    );
  }

  /* --------------------------------------------------------------------------
     Os presets GUARDADOS — o elo que faltava entre a Fase 2 e o ecrã.

     MEDIDO 2026-10-09: o servidor entregava `meus_presets` e NINGUÉM o lia. Um
     preset guardado — pela IA ou pelo botão "Salvar como meu Dashboard" — era
     uma linha na base de dados. Este é o lado do cliente dessa ligação.

     PORQUÊ TRADUZIR, E NÃO COPIAR
     -----------------------------
     Os dois mundos têm formatos diferentes, e a diferença não é de gosto:

       o que a IA grava    `[{ tipo, titulo, config }]` — uma LISTA
       o que o dashboard    `{ 'kpi-custo': { gridX, gridY, ... } }` — um
         desenha                                                          OBJECTO

     O dashboard itera as chaves e posiciona cada widget pela geometria. Sem
     geometria não há desenho. E a IA não tem geometria: a grelha é do
     dashboard, e é aqui que ela é gerada.

     A GEOMETRIA É INVENTADA, E ISTO É DECIDIDO
     -----------------------------------------
     Três colunas, como o `base-ia` (`col(33.3)`), linhas de altura 8. É uma
     escolha visual, não uma medição: a IA pediu um CONJUNTO de widgets, não
     posições. Inventar posições seria inventar um arranjo que o produtor nunca
     viu — por isso a escolha é a mais óbvia e o produtor move tudo depois,
     como move qualquer widget.

     O QUE ESTE CÓDIGO NÃO FAZ
     --------------------------
     Não sobrescreve um preset que já existia, nem toca nos presets do produto
     (`base-ia`, `amplia`): a lista do servidor já vem filtrada por produtor
     (`do_produtore`), e um preset do produto não tem `custom-`.
     -------------------------------------------------------------------------- */
  var GRELHA = { col: 21, altura: 8, folga: 2 };

  function geometria(i) {
    return {
      gridX: (i % 3) * (GRELHA.col + 1),
      gridY: Math.floor(i / 3) * (GRELHA.altura + GRELHA.folga),
      gridW: GRELHA.col,
      gridH: GRELHA.altura,
    };
  }

  function paraGrelha(widgets) {
    var saida = {};
    if (!Array.isArray(widgets)) return saida;
    var n = 0;
    for (var i = 0; i < widgets.length; i++) {
      var w = widgets[i];
      var id = w && (w.tipo || w.id);
      if (!id || saida[id]) continue;
      saida[id] = Object.assign({}, geometria(n++), {
        visible: true,
        title: (w && (w.titulo || w.title)) || '',
        config: _clona(w.config || {}),
      });
    }
    return saida;
  }

  /* Onde o registo tem de cair, e porque NAO e' `window.PRESETS`.
   *
   * MEDIDO 2026-10-09, no browser: registar em `PRESETS` punha o preset no
   * menu com os widgets certos — e a grelha desenhava `chamado-amplia` em vez
   * deles. A causa e' a ORDEM: `pagina-index.js:2434` constroi `PRESETS` a
   * partir de `PRESET_WIDGETS_JSON`, e o `renderPreset` do dashboard
   * (`persistPresetWidgets`, :2848) escreve sempre nessa fonte. Um preset que
   * so' existe em `PRESETS` e' um preset que o proximo render apaga.
   *
   * Por isso se escreve na FONTE. E na mesma funcao de guardados do dashboard
   * que oIJ wrote `persistPresetWidgets`, se existir — reescrever a fonte por
   * baixo dela seria a mesma corrida que a de agora, com mais dps.
   */
  function registarPresetsGuardados(meus, atualizado) {
    if (!Array.isArray(meus) || !meus.length) return 0;
    var PRESETS = window.PRESETS;
    var FONTE = window.PRESET_WIDGETS_JSON;
    if (!PRESETS || !FONTE) return 0;
    var n = 0;
    for (var i = 0; i < meus.length; i++) {
      var p = meus[i];
      if (!p || !p.slug) continue;
      // Ja' tem widgets na FONTE: o produtor pode ter-o arranjado a mao, e o
      // que ele fez e' mais novo do que o que a IA guardou.
      if (!atualizado && FONTE[p.slug] && Object.keys(FONTE[p.slug]).length) continue;
      var widgets = paraGrelha(p.estrutura && p.estrutura.widgets);
      if (!atualizado && !Object.keys(widgets).length) continue;

      FONTE[p.slug] = widgets;
      PRESETS[p.slug] = {
        icon: 'bi-stars',
        label: p.nome || p.slug,
        color: '#0f9d6e',
        widgets: _clona(widgets),
        escritoPorIa: true,
      };
      try {
        // COM ESCOPO DE UTILIZADOR, como todas as outras chaves `matrix-*`.
        //
        // Medido 2026-10-14: esta linha escrevia no localStorage a chave
        // do preset SEM escopo de utilizador, e essa chave sem dono era
        // depois lida por QUALQUER conta que entrasse no mesmo browser — a
        // conta nova do dono acordou com os presets ("Tempo") de outra
        // pessoa na barra de widgets.
        //
        // `scopedKey` vem de `pagina-index.js` (script classico, escopo
        // global partilhado); sem ela, a chave fica sem escopo — que e' o
        // que acontecia quando este ficheiro corria sozinho.
        var _chave =
          typeof scopedKey === 'function'
            ? scopedKey('matrix-preset-json-' + p.slug)
            : 'matrix-preset-json-' + p.slug;
        localStorage.setItem(_chave, JSON.stringify(widgets));
      } catch (e) {
        /* Sem localStorage (modo privado) o preset vive so' nesta sessao. E'
           melhor do que falhar: o menu mostra e o produtor pode usar. */
      }
      n++;
      if (
        atualizado &&
        typeof sget === 'function' &&
        sget('matrix-active-preset') === p.slug &&
        typeof window.loadPreset === 'function'
      ) {
        window.loadPreset(p.slug);
      }
    }
    if (n && typeof window.renderWidgetbarPresets === 'function') {
      window.renderWidgetbarPresets();
    }
    return n;
  }

  function _clona(o) {
    try {
      return JSON.parse(JSON.stringify(o));
    } catch (e) {
      return o;
    }
  }

  window.AmpliaPalco = {
    registarPresetsGuardados: registarPresetsGuardados,
    PALCO_SLUG: PALCO_SLUG,
    parseIntencao: parseIntencao,
    render: render,
    veredito: veredito,
    clonar: clonar,
    limpar: limpar,
    perguntaDeVolta: perguntaDeVolta,
    desenhaMesa: desenhaMesa,
    garanteEstilo: garanteEstilo,
    hostEl: hostEl,
    espiaExec: espiaExec,
    querMesa: querMesa,
    normaliza: normaliza,
    normalizaComposicao: normalizaComposicao,
    blocoInstrucao: blocoInstrucao,
    schemaDaTool: schemaDaTool,
    ligaMotor: ligaMotor,
    vigiaMotor: vigiaMotor,
    registaPreset: registaPreset,
    PRESET_AMPLIA: PRESET_AMPLIA,
    CATALOGO_MESA: CATALOGO_MESA,
    carregaCatalogo: carregaCatalogo,
    completaDadosTopGlobais: completaDadosTopGlobais,
    idsDoCatalogo: idsDoCatalogo,
    montarDoServidor: montarDoServidor,
    ultimoDados: function () {
      return ULTIMO_DADOS;
    },
    estado: estado,
  };

  espiaExec();
  registaPreset();
  vigiaMotor();
  carregaCatalogo();
})();
