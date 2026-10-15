'use strict';

// =============================================================================
// AMPLIAGRO DASHBOARD DESKTOP - MATRIX SYSTEM
// =============================================================================

// Widget Types Configuration - completa para todos os tipos do modal
const WIDGET_TYPES = {
  // KPIs
  'kpi-roi': { title: 'ROI Operacional', icon: 'bi-currency-dollar', defaultSize: { w: 6, h: 6 } },
  'kpi-custo': { title: 'Custo por Hectare', icon: 'bi-calculator', defaultSize: { w: 6, h: 6 } },
  'kpi-caixa': { title: 'Fluxo de Caixa', icon: 'bi-wallet2', defaultSize: { w: 6, h: 6 } },
  'kpi-alertas': {
    title: 'Alertas de Insumos',
    icon: 'bi-exclamation-triangle',
    defaultSize: { w: 4, h: 4 },
  },
  'kpi-sensores': { title: 'Sensores IoT', icon: 'bi-cpu', defaultSize: { w: 4, h: 4 } },
  'kpi-clima': { title: 'Clima', icon: 'bi-cloud-sun', defaultSize: { w: 6, h: 6 } },
  'kpi-manutencoes': { title: 'Manutenções', icon: 'bi-tools', defaultSize: { w: 4, h: 4 } },
  'kpi-produtividade': {
    title: 'Produtividade',
    icon: 'bi-graph-up-arrow',
    defaultSize: { w: 6, h: 6 },
  },
  'kpi-area': { title: 'Área Plantada', icon: 'bi-bounding-box', defaultSize: { w: 6, h: 6 } },
  'kpi-animais': { title: 'Pecuária', icon: 'bi-hospital', defaultSize: { w: 6, h: 6 } },
  'kpi-funcionarios': { title: 'Equipe', icon: 'bi-people', defaultSize: { w: 6, h: 6 } },
  'widget-resumo': { title: 'Resumo Geral', icon: 'bi-info-circle', defaultSize: { w: 8, h: 8 } },
  // Gráficos
  'chart-line': { title: 'Gráfico Linha', icon: 'bi-graph-up', defaultSize: { w: 12, h: 8 } },
  'chart-bar': { title: 'Gráfico Barras', icon: 'bi-bar-chart', defaultSize: { w: 8, h: 8 } },
  'chart-pie': { title: 'Gráfico Pizza', icon: 'bi-pie-chart', defaultSize: { w: 6, h: 6 } },
  'chart-area': { title: 'Gráfico Área', icon: 'bi-activity', defaultSize: { w: 12, h: 8 } },
  'chart-doughnut': { title: 'Gráfico Rosca', icon: 'bi-circle-half', defaultSize: { w: 6, h: 6 } },
  'chart-radar': { title: 'Gráfico Radar', icon: 'bi-diagram-3', defaultSize: { w: 8, h: 8 } },
  'chart-polar': { title: 'Gráfico Polar', icon: 'bi-bullseye', defaultSize: { w: 6, h: 6 } },
  'chart-scatter': { title: 'Gráfico Dispersão', icon: 'bi-dot', defaultSize: { w: 8, h: 8 } },
  'chart-stacked-bar': {
    title: 'Barras Empilhadas',
    icon: 'bi-bar-chart-fill',
    defaultSize: { w: 8, h: 8 },
  },
  'chart-horizontal-bar': {
    title: 'Barras Horizontais',
    icon: 'bi-bar-chart-steps',
    defaultSize: { w: 8, h: 8 },
  },
  'chart-mixed': { title: 'Gráfico Misto', icon: 'bi-layers', defaultSize: { w: 12, h: 8 } },
  'chart-bubble': { title: 'Gráfico Bolhas', icon: 'bi-circle', defaultSize: { w: 8, h: 8 } },
  'chart-safras': { title: 'Gráfico Safras', icon: 'bi-calendar3', defaultSize: { w: 12, h: 8 } },
  'chart-financeiro': {
    title: 'Gráfico Financeiro',
    icon: 'bi-pie-chart-fill',
    defaultSize: { w: 8, h: 8 },
  },
  'chart-estoque': { title: 'Gráfico Estoque', icon: 'bi-box', defaultSize: { w: 8, h: 8 } },
  'chart-producao-animal': {
    title: 'Prod. Animal',
    icon: 'bi-graph-up',
    defaultSize: { w: 8, h: 8 },
  },
  // Tabelas
  'table-data': { title: 'Tabela Safras', icon: 'bi-table', defaultSize: { w: 12, h: 10 } },
  'table-planilha': {
    title: 'Planilha',
    icon: 'bi-file-spreadsheet',
    defaultSize: { w: 12, h: 10 },
  },
  'table-financeiro': {
    title: 'Tabela Financeira',
    icon: 'bi-cash-stack',
    defaultSize: { w: 12, h: 10 },
  },
  'table-estoque': { title: 'Tabela Estoque', icon: 'bi-boxes', defaultSize: { w: 12, h: 10 } },
  'table-safras': { title: 'Safras Detalhe', icon: 'bi-table', defaultSize: { w: 12, h: 10 } },
  'table-insumos': { title: 'Insumos', icon: 'bi-box-seam', defaultSize: { w: 8, h: 8 } },
  // Listas
  'list-tasks': { title: 'Lista Tarefas', icon: 'bi-list-task', defaultSize: { w: 6, h: 10 } },
  'list-tarefas': { title: 'Lista Tarefas', icon: 'bi-list-task', defaultSize: { w: 6, h: 10 } },
  'list-agenda': { title: 'Agenda', icon: 'bi-calendar-check', defaultSize: { w: 6, h: 10 } },
  'list-manutencao': { title: 'Manutenção', icon: 'bi-tools', defaultSize: { w: 6, h: 10 } },
  'list-colmeias': { title: 'Colmeias', icon: 'bi-flower1', defaultSize: { w: 6, h: 8 } },
  'list-colheita': { title: 'Colheita', icon: 'bi-calendar-check', defaultSize: { w: 6, h: 8 } },
  'alerts-widget': {
    title: 'Alertas',
    icon: 'bi-exclamation-triangle',
    defaultSize: { w: 6, h: 6 },
  },
  'calendar-widget': {
    title: 'Calendário',
    icon: 'bi-calendar-week',
    defaultSize: { w: 8, h: 12 },
  },
  'kpi-calendario': {
    title: 'Calendário',
    icon: 'bi-calendar-event',
    defaultSize: { w: 8, h: 12 },
  },
  // Widgets compostos
  'widget-executivo': { title: 'Executivo', icon: 'bi-briefcase', defaultSize: { w: 8, h: 8 } },
  'widget-campo': { title: 'Campo', icon: 'bi-geo-alt', defaultSize: { w: 8, h: 8 } },
  'widget-financeiro': { title: 'Financeiro', icon: 'bi-bank', defaultSize: { w: 8, h: 8 } },
  'widget-livre': { title: 'Livre', icon: 'bi-gear', defaultSize: { w: 4, h: 4 } },
  'weather-widget': { title: 'Clima', icon: 'bi-cloud-sun', defaultSize: { w: 6, h: 6 } },

  // ─────────────────────────────────────────────────────────────────────────
  // O CHAMADO — a peça que a IA escreve, e o ÚNICO preset que ela pode mexer
  //
  // Este widget é diferente de todos os outros em dois sentidos, e ambos são
  // razão para ele estar aqui e não num contentor à parte.
  //
  // 1. NÃO É UM WIDGET DE DADOS. Os restantes leem números do banco. Este lê
  //    uma peça escrita pela IA (`/api/amplia/palco/chamado/`) em que cada
  //    bloco traz o seu `fonte_dado` — `medido`, `sem_dado` ou `simulado`. Por
  //    isso não entra em `getWidgetDataFromAPI`: não há um único número a
  //    devolver, há uma peça com proveniência por bloco. O seu conteúdo é
  //    desenhado pelo `chamado-amplia.js`, que escreve o DOM com `textContent`
  //    e nunca com `innerHTML` — um texto veio de um modelo.
  //
  // 2. A SUA POSIÇÃO É DO PRODUTOR. A peça é dele, e um painel que o produtor
  //    não pode mover, nem redimensionar, nem tirar, não é um widget: é um
  //    banner. É para isso que serve a matriz.
  //
  // PORQUÊ UM REGISTO E NÃO UM `amplia-chamado-ancora` NO TEMPLATE
  // ----------------------------------------------------------
  // A primeira tentativa montava a peça sozinha em `#content`, e ficava POR BAIXO
  // da matriz. O `liquid-glass.css` crava a matriz com `position:absolute
  // !important; inset: 0 0 56px 0` dentro de um `#content` com `overflow:hidden`
  // — não há espaço de flow para mais nada, e nada leria o DOM a dizer que
  // estava a ser tapado. Os testes em DOM de mentira davam 61 verdes, porque sem
  // CSS não há nada por cima. Só o browser o mostrou: o botão existia, e um
  // rato acertava no `grid` de outro widget.
  //
  // Ser widget é a correção honesta: não se briga com `!important`, e o produtor
  // fica com a peça onde a quer.
  //
  // O `generateWidgetContent` do index.html não conhece este id e devolve o seu
  // fallback — o que é tudo o que precisamos: dá-nos um `.widget-content`
  // dentro de `#widget-chamado-amplia`, e o `chamado-amplia.js` escreve lá
  // dentro. Por isso esta integração não toca no index.html.
  'chamado-amplia': {
    title: 'Chamado da IA',
    icon: 'bi-megaphone',
    defaultSize: { w: 32, h: 28 },
  },

  // ─────────────────────────────────────────────────────────────────────────
  // REGISTO DOS WIDGETS QUE O MODAL OFERECIA E QUE NUNCA CHEGARAM AQUI
  //
  // O modal de "adicionar widget" (WIDGET_CATALOG, em index.html) listava 22
  // widgets que NÃO existiam neste WIDGET_TYPES. O `addWidget` do index.html
  // faz `var type = WIDGET_TYPES[widgetId]; if (!type) return 'desconhecido';`
  // — ou seja, clicar num destes 22 devolvia 'desconhecido' e NADA acontecia:
  // o toast dizia "Widget desconhecido" e o widget nunca era criado.
  //
  // Pior: mesmo que a guarda fosse removida, `generateWidgetContent` (index.html)
  // devolve string VAZIA para qualquer id sem tipo registado — o bloco era
  // criado, sem conteúdo, e parecia um buraco no painel.
  //
  // Estes IDs não são invenção: 18 deles são servidos por `top-globais-widgets.js`
  // (HANDLERS + /api/top-globais/<id>/) e 4 são construídos em
  // `getWidgetSpecificContent`. O conteúdo existia; faltava só a ficha aqui.
  //
  // `tests/unit/widgets_registro.test.js` falha se algum widget anunciado no
  // modal voltar a ficar sem ficha.
  // ─────────────────────────────────────────────────────────────────────────

  // Ligados a /api/top-globais/ (renderizados por top-globais-widgets.js)
  'kpi-vra-ndvi': {
    title: 'VRA NDVI 10m Sentinel-2',
    icon: 'bi-satellite',
    defaultSize: { w: 8, h: 8 },
  },
  'kpi-can-bus': { title: 'CAN Bus RPM/Consumo DTC', icon: 'bi-cpu', defaultSize: { w: 8, h: 8 } },
  'kpi-guidance-ab': {
    title: 'Guidance A-B Auto-section',
    icon: 'bi-signpost-split',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-ai-cultura': {
    title: 'IA Detecta Cultura Satélite',
    icon: 'bi-robot',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-chuva-1km': {
    title: 'Chuva Hiperlocal 1km 15min',
    icon: 'bi-cloud-rain-heavy',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-as-applied': {
    title: 'As-Applied vs As-Planned Gap',
    icon: 'bi-bullseye',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-praga-ai': { title: 'Alerta Praga AI Foto', icon: 'bi-bug', defaultSize: { w: 8, h: 6 } },
  'kpi-rota-otimizada': {
    title: 'Rota Otimizada 70 Colheitadeiras',
    icon: 'bi-geo-alt',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-weigh-scale': {
    title: 'Weigh Scale sc/ha Tempo Real',
    icon: 'bi-speedometer2',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-hedge-b3': {
    title: 'Hedge B3 Chicago Real',
    icon: 'bi-graph-up-arrow',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-benchmark-fbn': {
    title: 'Benchmark 2k Fazendas',
    icon: 'bi-bar-chart-line',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-seguro-chuva': {
    title: 'Seguro Paramétrico Chuva',
    icon: 'bi-shield-fill-check',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-lcdpr-sped': {
    title: 'LCDPR SPED Auditável',
    icon: 'bi-file-earmark-check',
    defaultSize: { w: 8, h: 6 },
  },
  'kpi-carbono': { title: 'Carbono tCO2e/ha Mombak', icon: 'bi-tree', defaultSize: { w: 8, h: 6 } },
  'kpi-voz': { title: 'Assistente Voz', icon: 'bi-mic', defaultSize: { w: 8, h: 6 } },
  'kpi-copilot-hedge': {
    title: 'Copilot Hedge 65sc',
    icon: 'bi-chat-dots',
    defaultSize: { w: 8, h: 6 },
  },

  // Construídos em getWidgetSpecificContent (index.html)
  'kpi-margem-bruta': {
    title: 'Margem por Hectare (R$/ha)',
    icon: 'bi-graph-up',
    defaultSize: { w: 6, h: 6 },
  },
  'kpi-melhor-cliente': {
    title: 'Melhor Talhão (produtividade)',
    icon: 'bi-star',
    defaultSize: { w: 6, h: 6 },
  },
  'kpi-novidades': { title: 'Novidades', icon: 'bi-megaphone', defaultSize: { w: 6, h: 6 } },
  'kpi-pedidos': {
    title: 'Pedidos de Venda (sc)',
    icon: 'bi-currency-dollar',
    defaultSize: { w: 6, h: 6 },
  },
  'kpi-vendas-totais': {
    title: 'Produção Total (ton) — Safra',
    icon: 'bi-box-seam',
    defaultSize: { w: 6, h: 6 },
  },
  'table-vendas-regiao': {
    title: 'Vendas por Região',
    icon: 'bi-map',
    defaultSize: { w: 12, h: 10 },
  },
};

let widgets = {};
let resizeState = null;
const DASH_GRID_COLS = 128;
const DASH_GRID_ROWS = 80;
// Se o sistema principal (index.html) já existe, delegar para ele para evitar conflito de grids/storage
const __hasMainMatrix = function () {
  return (
    typeof window.renderWidgetsOnMatrix === 'function' && typeof window.GRID_COLS !== 'undefined'
  );
};

// =============================================================================
// WIDGET MATRIX SYSTEM - Funções de renderização e posicionamento
// =============================================================================

if (!__hasMainMatrix()) {
  window.initWidgetsMatrix = function () {
    const saved = localStorage.getItem('matrix-widgets-layout');
    if (saved) {
      try {
        widgets = JSON.parse(saved);
      } catch (e) {
        widgets = {};
      }
    }
    renderWidgetsOnMatrix();
  };

  /* O CHAMADO ENTRA NO PAINEL DE TODOS — sem empurrar nada
   * ==========================================================================
   * Um produtor que já tem um painel não vai receber o Chamado sem isto: nada
   * mais o acrescentaria. E a peça é dele — existe, tem a resposta da IA
   * escrita, e sem isto seria invisível sem que houvesse forma de saber que
   * estava lá.
   *
   * A posição é ENCONTRADA, não escolhida: abaixo de tudo o que já existe, e
   * à direita do que estiver nessa linha. Empurrar o painel de alguém para
   * baixo o painel de alguém, para mostrar uma coisa nova, é o tipo de
   * "melhoria" que se sente como invasão — e o produtor que limpou o painel
   * para ver só as suas coisas não pediu para ver o Chamado no meio delas.
   *
   * É idempotente: só entra se ainda não entrar, e a presença na lista é o
   * que conta, não a posição. */
  function asseguraChamadoNoLayout() {
    const CHAMADO = 'chamado-amplia';
    const type = WIDGET_TYPES[CHAMADO];
    if (!type) return false;
    if (widgets && widgets[CHAMADO]) return false;

    const size = type.defaultSize;
    const ocupado = [];
    let maxLinha = 0;
    Object.entries(widgets || {}).forEach(([, cfg]) => {
      if (!cfg || cfg.visible === false) return;
      const w = cfg.gridW || size.w;
      const h = cfg.gridH || size.h;
      ocupado.push({ x: cfg.gridX || 0, y: cfg.gridY || 0, w: w, h: h });
      maxLinha = Math.max(maxLinha, (cfg.gridY || 0) + h);
    });

    const livre = (x, y) =>
      !ocupado.some((o) => x < o.x + o.w && x + size.w > o.x && y < o.y + o.h && y + size.h > o.y);

    let linha = maxLinha;
    let coluna = 0;
    let guarda = 0;
    while (!livre(coluna, linha) && guarda < 400) {
      coluna += size.w;
      if (coluna + size.w > DASH_GRID_COLS) {
        linha += 1;
        coluna = 0;
      }
      guarda += 1;
    }

    widgets[CHAMADO] = {
      gridX: coluna,
      gridY: linha,
      gridW: size.w,
      gridH: size.h,
      visible: true,
    };
    window.widgets = widgets;
    return true;
  }

  /* Exportada, e é exportada PORQUÊ é preciso.
   *
   * O `renderWidgetsOnMatrix` destaqui não é o que desenha o painel: o
   * `index.html` redefine `window.renderWidgetsOnMatrix` duas vezes (4388 e
   * 14103), e é a versão dele que corre. Pôr a chamada dentro da função daqui
   * significava uma chamada que nunca acontecia — e um widget que nunca aparecia,
   * com um teste verde a dizer que aparecia.
   *
   * Por isso quem CHAMA é o `chamado-amplia.js`, que é quem tem o direito de
   * pedir: uma peça que a IA escreveu não tem por que oferecer-se a um módulo de
   * widgets que não sabe o que ela é. */
  window.asseguraChamadoNoLayout = asseguraChamadoNoLayout;

  window.renderWidgetsOnMatrix = function () {
    const container = document.querySelector('.matrix-container');
    if (!container) return;

    container.querySelectorAll('.bento-block').forEach((el) => el.remove());
    container.querySelectorAll('[data-primeiro-arranque]').forEach((el) => el.remove());

    let count = 0;
    // No celular o grid de 64 colunas nao serve. config.gridW foi dimensionado
    // para uma tela de ~1320px, onde 10/64 das colunas dao ~206px; em 393px as
    // mesmas 10 colunas dao 54px, o widget fica estreito a ponto de a legenda do
    // eixo Y comer a altura toda, os cards saem com alturas diferentes e um
    // sobrepoe o de baixo. Medido: 3 widgets de 54px, ilegiveis.
    // Confirmado que nao e estado salvo — limpar o localStorage reproduziu as
    // mesmas posicoes. Entao, em vez de usar o grid salvo, empilha um por linha.
    // O caminho do desktop fica EXATAMENTE como estava.
    const estreito = window.matchMedia('(max-width: 900px)').matches;
    let fila = 0;

    Object.entries(widgets).forEach(([id, config]) => {
      if (!config.visible) return;
      count++;

      const el = document.createElement('div');
      el.id = `widget-${id}`;
      el.className = 'bento-block lc-panel';
      if (estreito) {
        el.style.gridColumn = '1 / -1';
        el.style.gridRow = `${++fila}`;
      } else {
        el.style.gridColumn = `${config.gridX + 1} / span ${config.gridW}`;
        el.style.gridRow = `${config.gridY + 1} / span ${config.gridH}`;
      }
      el.innerHTML = generateWidgetContent(id, config);
      container.appendChild(el);
    });

    /* O Chamado escreve dentro do seu próprio `.widget-content`, e esse
     * contentor acabou de ser recriado — o de antes já não existe. Por isso o
     * redesenho da peça é chamado daqui, e não de um observador: esta função
     * sabe quando acontece, e observar a árvore do dashboard inteiro para
     * adivinhar o que esta linha já sabe seria trabalho e custo sem motivo.
     *
     * `?.` porque o `chamado-amplia.js` é `defer` no base.html e este ficheiro
     * também — a ordem não é uma garantia para quem carrega a página a meio. */
    window.AmpliaChamado?.aposRenderWidgets?.();

    // ─────────────────────────────────────────────────────────────────────
    // PRIMEIRO ARRANQUE: o painel vazio que não se explica
    // ─────────────────────────────────────────────────────────────────────
    // O backend já diz quando o produtor ainda não registou propriedade —
    // `/api/dashboard/` devolve `{"sem_propriedade": true}`. Esse sinal é
    // lido no index.html e guardado em `dashboardData`, e nunca era usado
    // para nada: o ecrã ficava com os dois widgets do preset "Água"
    // (caixa e alertas), ambos a dizer "sem dado", e nenhum passo seguinte.
    //
    // O que o produtor via não era um painel vazio — era um painel com
    // widgets, que é pior. Um vazio puro diz "não há nada"; um painel com
    // widgets a dizer "sem dado" diz "o sistema está a funcionar e a sua
    // fazenda está vazia", e não é verdade nenhuma das duas coisas. Não há
    // propriedade registada, e sem propriedade não há nada para mostrar.
    //
    // A regra do projecto é a mesma dos números: **ausência que não é
    // anunciada é uma mentira**. Aqui a ausência é a propriedade.
    //
    // `primeiroArranqueEscondido` só vale enquanto o aviso continuar a ser
    // verdade: se a propriedade for registada, o "esconder" esquece-se, porque
    // um aviso que diz "comece por registar a propriedade" numa fazenda que
    // já tem propriedade é mentira nova.
    if (
      window.dashboardData &&
      window.dashboardData.sem_propriedade &&
      !primeiroArranqueEscondido()
    ) {
      const aviso = document.createElement('div');
      aviso.setAttribute('data-primeiro-arranque', 'true');
      aviso.className = 'lc-panel';
      aviso.style.gridColumn = '1 / -1';
      aviso.style.gridRow = '1 / span 1';
      aviso.innerHTML = `
        <div style="padding:28px 24px;display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap">
          <i class="bi bi-signpost-2" style="font-size:1.9rem;opacity:.7;line-height:1"></i>
          <div style="flex:1;min-width:260px">
            <div style="font-weight:700;font-size:1.05rem;margin-bottom:.35rem">
              Comece por registar a sua propriedade
            </div>
            <div style="font-size:.86rem;line-height:1.55;opacity:.85">
              Os widgets deste painel medem a sua fazenda — área, safras,
              lançamentos, animais. Sem uma propriedade registada não há o que
              medir, e por isso todos dizem <em>sem dado</em>. Não é uma falha:
              é falta de registo.
            </div>
            <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.9rem">
              <a class="lc-btn" href="/cadastro/propriedade/"
                 style="text-decoration:none;display:inline-flex;align-items:center;gap:.4rem">
                <i class="bi bi-plus-circle"></i> Registar propriedade
              </a>
              <a class="lc-btn-secondary" href="/onboarding/"
                 style="text-decoration:none;display:inline-flex;align-items:center;gap:.4rem">
                <i class="bi bi-signpost-split"></i> Ver o passo a passo
              </a>
              <button type="button" class="lc-btn-secondary"
                      onclick="hideFirstRunBanner && hideFirstRunBanner(this)"
                      style="display:inline-flex;align-items:center;gap:.4rem">
                <i class="bi bi-eye-slash"></i> Esconder
              </button>
            </div>
          </div>
        </div>`;
      container.insertBefore(aviso, container.firstChild);
    }

    const statusEl = document.getElementById('widget-status');
    if (statusEl) {
      statusEl.textContent = `${count} ativos`;
    }

    // Initialize drag handlers for edit mode
    if (window.widgetbarState?.isCustomMode) {
      setTimeout(initWidgetDragHandlers, 0);
    }
  };

  // "Esconder" não pode ser um botão morto. Um botão que não faz nada é pior
  // do que não ter botão: o produtor clica, não acontece nada, e fica a achar
  // que a aplicação está pendurada. A escolha vive na sessão — não em
  // localStorage, porque amanhã o produtor pode precisar do lembrete outra
  // vez e não deve ter de o repor à mão.
  window.hideFirstRunBanner = function (btn) {
    const aviso = btn && btn.closest('[data-primeiro-arranque]');
    if (aviso) aviso.remove();
    try {
      sessionStorage.setItem('ampliagro-first-run-hidden', '1');
    } catch (e) {
      /* modo privado: o aviso some nesta vista e volta no próximo render */
    }
  };

  // O "esconder" só vale enquanto o aviso continuar a ser verdade. Se a
  // propriedade for registada, o sinal `sem_propriedade` deixa de vir e o
  // aviso desaparece sozinho — porque um aviso que diz "comece por registar
  // a propriedade" numa fazenda que já tem propriedade é mentira nova.
  function primeiroArranqueEscondido() {
    try {
      return sessionStorage.getItem('ampliagro-first-run-hidden') === '1';
    } catch (e) {
      return false;
    }
  }

  window.generateWidgetContent = function (id, config) {
    const type = WIDGET_TYPES[id];
    if (!type) return '';

    return `
        <div class="widget-content p-2 overflow-auto absolute inset-0 flex flex-col">
            ${getWidgetSpecificContent(id)}
        </div>
        <!-- Resize handles (only visible in edit mode when widget is selected) -->
        <div class="resize-handle edge-nw" data-resize="nw" data-widget="${id}"></div>
        <div class="resize-handle edge-ne" data-resize="ne" data-widget="${id}"></div>
        <div class="resize-handle edge-sw" data-resize="sw" data-widget="${id}"></div>
        <div class="resize-handle edge-se" data-resize="se" data-widget="${id}"></div>
        <div class="resize-handle edge-n" data-resize="n" data-widget="${id}"></div>
        <div class="resize-handle edge-s" data-resize="s" data-widget="${id}"></div>
        <div class="resize-handle edge-e" data-resize="e" data-widget="${id}"></div>
        <div class="resize-handle edge-w" data-resize="w" data-widget="${id}"></div>
    `;
  };

  window.getWidgetSpecificContent = function (id) {
    const contents = {
      'kpi-roi': `<div class="space-y-2"><span class="text-xs text-slate-500">ROI</span><p class="text-2xl font-bold text-ncs-green-dark">12,5%</p></div>`,
      'kpi-custo': `<div class="space-y-2"><span class="text-xs text-slate-500">Custo/Ha</span><p class="text-2xl font-bold text-ncs-blue-dark">R$ 450</p></div>`,
      'kpi-alertas': `<div class="text-rose-500 text-xs"><i class="bi bi-exclamation-circle"></i> 3 alertas críticos</div>`,
      'kpi-manutencoes': `<div class="text-xs space-y-1"><span class="text-slate-500">OS Pendentes</span><p class="text-lg font-bold">5</p></div>`,
      'kpi-sensores': `<div class="text-xs"><div class="flex justify-between"><span>Umidade</span><span class="font-bold">65%</span></div><div class="w-full bg-slate-200 rounded h-1"><div class="bg-emerald-500 h-1 rounded" style="width: 130%"></div></div></div>`,
      'kpi-clima': `<div class="text-center"><i class="bi bi-sun text-3xl text-amber-400"></i><p class="text-2xl font-bold">28°C</p></div>`,
      'kpi-caixa': `<div class="space-y-2"><span class="text-xs text-slate-500">Fluxo</span><p class="text-2xl font-bold text-emerald-600">R$ 8,2K</p></div>`,
      'kpi-calendario': `<div class="grid grid-cols-7 gap-1 text-xs"><div class="bg-ncs-green-dark text-white rounded p-1 text-center">1</div><div class="p-1 text-center">2</div></div>`,
      'chart-line': `<canvas id="chart-${id}" class="w-full h-32"></canvas>`,
      'chart-bar': `<canvas id="chart-${id}" class="w-full h-32"></canvas>`,
      'chart-pie': `<canvas id="chart-${id}" class="w-full h-32"></canvas>`,
      'table-data': `<table class="w-full text-xs"><thead><tr class="border-b"><th class="text-left">Item</th><th class="text-right">Valor</th></tr></thead><tbody><tr><td>Soja</td><td class="text-right">R$ 85</td></tr><tr><td>Milho</td><td class="text-right">R$ 42</td></tr></tbody></table>`,
      'table-insumos': `<table class="w-full text-xs"><thead><tr class="border-b"><th class="text-left">Insumo</th><th class="text-right">Estoque</th></tr></thead><tbody><tr><td>Fertilizante</td><td class="text-right">120kg</td></tr></tbody></table>`,
      'list-tarefas': `<ul class="text-xs space-y-1"><li><i class="bi bi-circle text-[8px]"></i> Plantar soja</li><li><i class="bi bi-circle text-[8px]"></i> Revisar manutenção</li></ul>`,
      'list-colheita': `<ul class="text-xs space-y-1"><li><i class="bi bi-check-circle text-emerald-500"></i> Colheita soja</li></ul>`,
      'widget-executivo': `<div class="text-xs"><p>Widgets Executivo</p></div>`,
      'widget-campo': `<div class="text-xs"><p>Widgets Campo</p></div>`,
      'widget-financeiro': `<div class="text-xs"><p>Widgets Financeiro</p></div>`,
      'widget-livre': `<div class="text-xs"><p>Widget Livre</p></div>`,
      'weather-widget': `<div class="text-center"><i class="bi bi-sun text-3xl text-amber-400"></i><p class="text-2xl font-bold">28°C</p></div>`,
    };

    return contents[id] || '<p class="text-xs">Widget</p>';
  };
}

// =============================================================================
// CHART MANAGEMENT
// =============================================================================

window.initChartsForWidgets = function () {
  // PERF/FIX: o fallback literal { chartInstances: {} } criava um objeto NOVO a cada chamada
  // quando window.widgetbarState nao existia — chartInstances ficava sempre undefined e
  // `state.chartInstances[chartId] = new Chart(...)` estourava com
  // "Cannot read properties of undefined (reading 'cultura-..._grafico')".
  // Agora: garante o container, e destroi chart anterior antes de recriar (evita
  // "Canvas is already in use" do Chart.js quando o canvas e re-renderizado).
  if (!window.widgetbarState) window.widgetbarState = {};
  var state = window.widgetbarState;
  if (!state.chartPeriod) state.chartPeriod = 'month';
  if (!state.chartInstances) state.chartInstances = {};

  document.querySelectorAll('canvas[id^="chart-"]').forEach(function (ctx) {
    if (typeof Chart === 'undefined') return;
    const chartId = ctx.id.replace('chart-', '');
    // destroi instancia anterior ligada a este canvas (re-render trocou o elemento)
    try {
      const existing = Chart.getChart ? Chart.getChart(ctx) : null;
      if (existing) existing.destroy();
    } catch (e) {}
    try {
      if (state.chartInstances[chartId]) {
        state.chartInstances[chartId].destroy();
      }
    } catch (e) {}
    delete state.chartInstances[chartId];
    try {
      state.chartInstances[chartId] = new Chart(ctx, {
        type: 'line',
        data: getChartDataForPeriod(state.chartPeriod),
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
          },
        },
      });
    } catch (e) {
      console.warn('[charts] falha ao criar', chartId, e && e.message);
    }
  });
};

window.getChartDataForPeriod = function (period) {
  const labels = {
    today: ['06h', '09h', '12h', '15h', '18h'],
    week: ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'],
    month: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
    semester: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
    year: ['2024', '2025', '2026'],
    harvest: ['1º Lei', '2º Lei', '3º Lei', 'Safra'],
    fiveyears: ['2021', '2022', '2023', '2024', '2025', '2026'],
  };

  const values = {
    today: [30, 45, 60, 55, 40],
    week: [120, 140, 115, 160, 180, 90, 75],
    month: [65, 70, 75, 85, 80, 92],
    semester: [320, 280, 340, 300, 380, 420, 360, 310, 290, 350, 400, 450],
    year: [2500, 3200, 4100],
    harvest: [1800, 2200, 2900, 3500],
    fiveyears: [1800, 2200, 2900, 3500, 4200, 4800],
  };

  return {
    labels: labels[period] || labels['month'],
    datasets: [
      {
        data: values[period] || values['month'],
        borderColor: '#0f9d6e',
        backgroundColor: 'rgba(83, 221, 108, 0.1)',
      },
    ],
  };
};

window.cleanupAllCharts = function () {
  const state = window.widgetbarState;
  if (!state || !state.chartInstances) return;

  Object.values(state.chartInstances).forEach(function (chart) {
    if (chart && chart.destroy) {
      chart.destroy();
    }
  });
  state.chartInstances = {};
};

// =============================================================================
// WIDGET MANAGEMENT
// =============================================================================

window.addWidget = function (widgetId) {
  const type = WIDGET_TYPES[widgetId] || { title: widgetId, defaultSize: { w: 6, h: 6 } };

  // Se já existe mas está invisível, reativar
  if (widgets[widgetId]) {
    if (!widgets[widgetId].visible) {
      widgets[widgetId].visible = true;
      renderWidgetsOnMatrix();
      initChartsForWidgets();
      saveWidgetsLayout();
    }
    return;
  }

  const pos = findFreePosition(type.defaultSize.w, type.defaultSize.h);
  if (!pos) {
    alert('Espaço insuficiente na matriz!');
    return;
  }

  widgets[widgetId] = {
    gridX: pos.x,
    gridY: pos.y,
    gridW: type.defaultSize.w,
    gridH: type.defaultSize.h,
    visible: true,
  };

  renderWidgetsOnMatrix();
  initChartsForWidgets();
  saveWidgetsLayout();
};

window.removeWidget = function (widgetId) {
  if (widgets[widgetId]) {
    widgets[widgetId].visible = false;
  }
  const el = document.getElementById(`widget-${widgetId}`);
  if (el) {
    el.style.transition = 'opacity 0.2s, transform 0.2s';
    el.style.opacity = '0';
    el.style.transform = 'scale(0.95)';
    setTimeout(function () {
      el.remove();
    }, 200);
  }

  const state = window.widgetbarState;
  if (state && state.chartInstances && state.chartInstances[widgetId]) {
    state.chartInstances[widgetId].destroy();
    delete state.chartInstances[widgetId];
  }

  saveWidgetsLayout();
};

window.clearAllWidgets = function () {
  Object.keys(widgets).forEach(function (id) {
    if (widgets[id]) {
      widgets[id].visible = false;
    }
  });
  renderWidgetsOnMatrix();
  saveWidgetsLayout();
};

window.saveWidgetsLayout = function () {
  localStorage.setItem('matrix-widgets-layout', JSON.stringify(widgets));
};

window.findFreePosition = function (w, h) {
  const cols = typeof window.GRID_COLS !== 'undefined' ? window.GRID_COLS : DASH_GRID_COLS;
  const rows = typeof window.GRID_ROWS !== 'undefined' ? window.GRID_ROWS : DASH_GRID_ROWS;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      if (!checkCollision(x, y, w, h)) {
        return { x, y };
      }
    }
  }
  return null;
};

window.checkCollision = function (x, y, w, h, skipId) {
  const cols = typeof window.GRID_COLS !== 'undefined' ? window.GRID_COLS : DASH_GRID_COLS;
  const rows = typeof window.GRID_ROWS !== 'undefined' ? window.GRID_ROWS : DASH_GRID_ROWS;
  if (x < 0 || y < 0 || x + w > cols || y + h > rows) return true;

  for (const [id, cfg] of Object.entries(widgets)) {
    if (id === skipId || !cfg.visible) continue;
    if (
      !(
        x + w <= cfg.gridX ||
        x >= cfg.gridX + cfg.gridW ||
        y + h <= cfg.gridY ||
        y >= cfg.gridY + cfg.gridH
      )
    ) {
      return true;
    }
  }
  return false;
};

// =============================================================================
// UTILITY FUNCTIONS (Navbar Support)
// =============================================================================

// Usa a função toggleDropdown definida no index.html (não sobrescreve)
// Mantém compatibilidade com o sistema de dropdowns existente

// =============================================================================
// MARKETPLACE MODAL FUNCTIONS
// =============================================================================

window.abrirMarketplaceWidgets = function () {
  console.warn('Marketplace desativado - use openAddWidgetModal()');
  return;
  const modal = document.getElementById('marketplace-modal');
  const grid = document.getElementById('marketplace-grid');
  if (!modal || !grid) return;

  grid.innerHTML = `
        <div onclick="addWidget('kpi-roi'); fecharMarketplaceWidgets();" class="p-3 border rounded-lg cursor-pointer hover:bg-ncs-blue-light/20 dark:hover:bg-ncs-blue-dark/30 text-center">
            <i class="bi bi-currency-dollar text-2xl text-ncs-green-dark"></i><p class="text-xs mt-1">ROI Operacional</p>
        </div>
        <div onclick="addWidget('kpi-custo'); fecharMarketplaceWidgets();" class="p-3 border rounded-lg cursor-pointer hover:bg-ncs-blue-light/20 dark:hover:bg-ncs-blue-dark/30 text-center">
            <i class="bi bi-calculator text-2xl text-ncs-blue-dark"></i><p class="text-xs mt-1">Custo/Ha</p>
        </div>
        <div onclick="addWidget('chart-line'); fecharMarketplaceWidgets();" class="p-3 border rounded-lg cursor-pointer hover:bg-ncs-blue-light/20 dark:hover:bg-ncs-blue-dark/30 text-center">
            <i class="bi bi-graph-up text-2xl text-ncs-blue-dark"></i><p class="text-xs mt-1">Gráfico Linha</p>
        </div>
        <div onclick="addWidget('chart-bar'); fecharMarketplaceWidgets();" class="p-3 border rounded-lg cursor-pointer hover:bg-ncs-blue-light/20 dark:hover:bg-ncs-blue-dark/30 text-center">
            <i class="bi bi-bar-chart text-2xl text-ncs-blue-dark"></i><p class="text-xs mt-1">Gráfico Barras</p>
        </div>
        <div onclick="addWidget('table-data'); fecharMarketplaceWidgets();" class="p-3 border rounded-lg cursor-pointer hover:bg-ncs-blue-light/20 dark:hover:bg-ncs-blue-dark/30 text-center">
            <i class="bi bi-table text-2xl text-slate-700"></i><p class="text-xs mt-1">Tabela</p>
        </div>
        <div onclick="addWidget('weather-widget'); fecharMarketplaceWidgets();" class="p-3 border rounded-lg cursor-pointer hover:bg-ncs-blue-light/20 dark:hover:bg-ncs-blue-dark/30 text-center">
            <i class="bi bi-cloud-sun text-2xl text-sky-600"></i><p class="text-xs mt-1">Clima</p>
        </div>
    `;
  modal.classList.remove('hidden');
};

window.fecharMarketplaceWidgets = function () {
  const modal = document.getElementById('marketplace-modal');
  if (modal) modal.classList.add('hidden');
};

// =============================================================================
// CONNECTION STATUS
// =============================================================================

function updateConnectionStatus() {
  const statusEl = document.getElementById('connection-status');
  if (!statusEl) return;
  statusEl.className = navigator.onLine
    ? 'bi bi-wifi text-xs connection-status text-emerald-500'
    : 'bi bi-wifi-off text-xs connection-status text-rose-500';
}

window.addEventListener('online', updateConnectionStatus);
window.addEventListener('offline', updateConnectionStatus);
updateConnectionStatus();

// =============================================================================
// WIDGET DRAG & DROP AND RESIZE
// =============================================================================

let widgetDragState = null;
let widgetResizeState = null;

// Initialize drag handlers for widgets in edit mode
function initWidgetDragHandlers() {
  // Se o sistema principal (index.html) já existe, delega para ele
  if (typeof window.initWidgetDragging === 'function' && typeof window.GRID_COLS !== 'undefined') {
    try {
      window.initWidgetDragging();
    } catch (e) {}
    return;
  }
  // Remove existing handlers to avoid duplicates
  document.querySelectorAll('.bento-block').forEach((el) => {
    el.removeEventListener('mousedown', handleWidgetMouseDown);
  });

  // Add new handlers
  document.querySelectorAll('.bento-block').forEach((el) => {
    el.addEventListener('mousedown', handleWidgetMouseDown);
  });
}
window.initWidgetDragHandlers = initWidgetDragHandlers;

function handleWidgetMouseDown(event) {
  if (typeof window.initWidgetDragging === 'function' && typeof window.GRID_COLS !== 'undefined')
    return;
  if (
    !window.widgetbarState?.isCustomMode &&
    !(typeof window.__getEditFlags === 'function' && window.__getEditFlags())
  )
    return;

  // Don't start drag if clicking on resize handle
  if (event.target.closest('.resize-handle')) return;

  // Don't start drag if clicking on interactive content (buttons, inputs, etc.)
  if (event.target.closest('button, input, select, textarea, a, canvas')) return;

  const widgetId = event.currentTarget.id.replace('widget-', '');
  if (!widgets[widgetId]) return;

  event.preventDefault();

  widgetDragState = {
    widgetId: widgetId,
    startX: event.clientX,
    startY: event.clientY,
    startGridX: widgets[widgetId].gridX,
    startGridY: widgets[widgetId].gridY,
    gridW: widgets[widgetId].gridW,
    gridH: widgets[widgetId].gridH,
  };

  const el = event.currentTarget;
  el.classList.add('drag-origin');

  // Create ghost element
  const ghost = el.cloneNode(true);
  ghost.classList.add('drag-ghost');
  ghost.style.width = el.offsetWidth + 'px';
  ghost.style.height = el.offsetHeight + 'px';
  ghost.style.pointerEvents = 'none';
  ghost.style.zIndex = '2147483647';
  ghost.id = 'drag-ghost-' + widgetId;
  document.body.appendChild(ghost);

  // Position ghost at cursor
  positionDragGhost(event.clientX, event.clientY);

  // Add drag active class to container
  const container = document.querySelector('.matrix-container');
  if (container) container.classList.add('drag-active');

  // Show grid drop hints
  showGridDropHints(widgetDragState);

  // Add global mouse handlers
  document.addEventListener('mousemove', handleWidgetMouseMove);
  document.addEventListener('mouseup', handleWidgetMouseUp);
}

// Position drag ghost
function positionDragGhost(clientX, clientY) {
  const ghost = document.getElementById('drag-ghost-' + (widgetDragState?.widgetId || ''));
  if (ghost) {
    ghost.style.left = clientX - 20 + 'px';
    ghost.style.top = clientY - 20 + 'px';
  }
}

// Widget Drag Move
function handleWidgetMouseMove(event) {
  if (!widgetDragState) return;

  event.preventDefault();

  const { widgetId, gridW, gridH } = widgetDragState;
  const container = document.querySelector('.matrix-container');
  if (!container) return;

  // Update ghost position
  positionDragGhost(event.clientX, event.clientY);

  // Calculate grid position
  const rect = container.getBoundingClientRect();
  const colWidth = rect.width / DASH_GRID_COLS;
  const rowHeight = rect.height / DASH_GRID_ROWS;

  const gridX = Math.floor((event.clientX - rect.left) / colWidth);
  const gridY = Math.floor((event.clientY - rect.top) / rowHeight);

  // Check if valid drop
  const isValid =
    gridX >= 0 &&
    gridY >= 0 &&
    gridX + gridW <= DASH_GRID_COLS &&
    gridY + gridH <= DASH_GRID_ROWS &&
    !checkCollision(gridX, gridY, gridW, gridH, widgetId);

  // Update drop hints
  updateDropHints(gridX, gridY, gridW, gridH, isValid);
}

// Widget Drag End
function handleWidgetMouseUp(event) {
  if (!widgetDragState) return;

  const { widgetId, startGridX, startGridY, gridW, gridH } = widgetDragState;
  const container = document.querySelector('.matrix-container');
  const el = document.getElementById(`widget-${widgetId}`);
  const ghost = document.getElementById('drag-ghost-' + widgetId);

  // Clean up
  if (el) el.classList.remove('drag-origin');
  if (ghost) ghost.remove();
  if (container) container.classList.remove('drag-active');

  // Remove drop hints
  document
    .querySelectorAll('.grid-drop-hint, .drop-target, .drop-target-invalid')
    .forEach((e) => e.remove());
  document
    .querySelectorAll('.bento-block.drop-target, .bento-block.drop-target-invalid')
    .forEach((e) => {
      e.classList.remove('drop-target', 'drop-target-invalid');
    });

  // Calculate final position
  if (container) {
    const rect = container.getBoundingClientRect();
    const colWidth = rect.width / DASH_GRID_COLS;
    const rowHeight = rect.height / DASH_GRID_ROWS;

    const gridX = Math.floor((event.clientX - rect.left) / colWidth);
    const gridY = Math.floor((event.clientY - rect.top) / rowHeight);

    const isValid =
      gridX >= 0 &&
      gridY >= 0 &&
      gridX + gridW <= DASH_GRID_COLS &&
      gridY + gridH <= DASH_GRID_ROWS &&
      !checkCollision(gridX, gridY, gridW, gridH, widgetId);

    if (isValid && (gridX !== startGridX || gridY !== startGridY)) {
      // Update widget position
      widgets[widgetId].gridX = gridX;
      widgets[widgetId].gridY = gridY;

      // Re-render
      renderWidgetsOnMatrix();
      initChartsForWidgets();
      saveWidgetsLayout();

      // Re-init drag handlers for new positions
      setTimeout(initWidgetDragHandlers, 0);

      window.showWidgetToast?.('Widget movido', 'success', 1500);
    }
  }

  // Remove global handlers
  document.removeEventListener('mousemove', handleWidgetMouseMove);
  document.removeEventListener('mouseup', handleWidgetMouseUp);

  widgetDragState = null;
}

// Remove the old HTML5 drag API handlers
window.handleWidgetDragStart = function () {
  return false;
};
window.handleWidgetDragEnd = function () {
  return false;
};

// Drag over container - show drop hints (desativado quando sistema principal ativo)
document.addEventListener('dragover', function (event) {
  if (typeof window.initWidgetDragging === 'function' && typeof window.GRID_COLS !== 'undefined')
    return;
  if (
    !widgetDragState ||
    (!window.widgetbarState?.isCustomMode &&
      !(typeof window.__getEditFlags === 'function' && window.__getEditFlags()))
  )
    return;

  event.preventDefault();

  const container = document.querySelector('.matrix-container');
  if (!container) return;

  // Update ghost position
  positionDragGhost(event.clientX, event.clientY);

  // Calculate grid position
  const rect = container.getBoundingClientRect();
  const colWidth = rect.width / DASH_GRID_COLS; // DASH columns
  const rowHeight = rect.height / DASH_GRID_ROWS; // DASH rows

  const gridX = Math.floor((event.clientX - rect.left) / colWidth);
  const gridY = Math.floor((event.clientY - rect.top) / rowHeight);

  // Check if valid drop
  const { gridW, gridH } = widgetDragState;
  const isValid =
    gridX >= 0 &&
    gridY >= 0 &&
    gridX + gridW <= DASH_GRID_COLS &&
    gridY + gridH <= DASH_GRID_ROWS &&
    !checkCollision(gridX, gridY, gridW, gridH, widgetDragState.widgetId);

  // Update drop hints
  updateDropHints(gridX, gridY, gridW, gridH, isValid);
});

// Drop on container (desativado quando sistema principal ativo)
document.addEventListener('drop', function (event) {
  if (typeof window.initWidgetDragging === 'function' && typeof window.GRID_COLS !== 'undefined')
    return;
  if (
    !widgetDragState ||
    (!window.widgetbarState?.isCustomMode &&
      !(typeof window.__getEditFlags === 'function' && window.__getEditFlags()))
  )
    return;

  event.preventDefault();

  const container = document.querySelector('.matrix-container');
  if (!container) return;

  const rect = container.getBoundingClientRect();
  const colWidth = rect.width / DASH_GRID_COLS;
  const rowHeight = rect.height / DASH_GRID_ROWS;

  const gridX = Math.floor((event.clientX - rect.left) / colWidth);
  const gridY = Math.floor((event.clientY - rect.top) / rowHeight);

  const { widgetId, gridW, gridH } = widgetDragState;

  // Check if valid
  const isValid =
    gridX >= 0 &&
    gridY >= 0 &&
    gridX + gridW <= DASH_GRID_COLS &&
    gridY + gridH <= DASH_GRID_ROWS &&
    !checkCollision(gridX, gridY, gridW, gridH, widgetId);

  if (isValid && (gridX !== widgets[widgetId]?.gridX || gridY !== widgets[widgetId]?.gridY)) {
    // Update widget position
    widgets[widgetId].gridX = gridX;
    widgets[widgetId].gridY = gridY;

    // Re-render
    renderWidgetsOnMatrix();
    initChartsForWidgets();
    saveWidgetsLayout();

    window.showWidgetToast?.('Widget movido', 'success', 1500);
  }

  // Clean up handled in dragend
});

// Update drop hints
function updateDropHints(gridX, gridY, gridW, gridH, isValid) {
  const container = document.querySelector('.matrix-container');
  if (!container) return;

  // Remove old hints
  document.querySelectorAll('.grid-drop-hint').forEach((e) => e.remove());

  // Create new hint
  const hint = document.createElement('div');
  hint.className = 'grid-drop-hint' + (isValid ? '' : ' invalid');
  hint.style.left = gridX * (container.clientWidth / DASH_GRID_COLS) + 'px';
  hint.style.top = gridY * (container.clientHeight / DASH_GRID_ROWS) + 'px';
  hint.style.width = gridW * (container.clientWidth / DASH_GRID_COLS) + 'px';
  hint.style.height = gridH * (container.clientHeight / DASH_GRID_ROWS) + 'px';
  hint.textContent = isValid
    ? `Solte para posicionar (${gridX + 1},${gridY + 1})`
    : 'Posição inválida';

  container.appendChild(hint);
}

// Show grid drop hints
function showGridDropHints(dragState) {
  const container = document.querySelector('.matrix-container');
  if (!container) return;

  const colWidth = container.clientWidth / DASH_GRID_COLS;
  const rowHeight = container.clientHeight / DASH_GRID_ROWS;

  for (let y = 0; y < DASH_GRID_ROWS; y++) {
    for (let x = 0; x < DASH_GRID_COLS; x++) {
      const isValid =
        x >= 0 &&
        y >= 0 &&
        x + dragState.gridW <= DASH_GRID_COLS &&
        y + dragState.gridH <= DASH_GRID_ROWS &&
        !checkCollision(x, y, dragState.gridW, dragState.gridH, dragState.widgetId);

      if (isValid) {
        const hint = document.createElement('div');
        hint.className = 'grid-drop-hint';
        hint.style.left = x * colWidth + 'px';
        hint.style.top = y * rowHeight + 'px';
        hint.style.width = dragState.gridW * colWidth + 'px';
        hint.style.height = dragState.gridH * rowHeight + 'px';
        hint.style.opacity = '0.1';
        hint.style.background = 'rgba(16, 185, 129, 0.1)';
        hint.style.border = '1px dashed rgba(16, 185, 129, 0.3)';
        container.appendChild(hint);
      }
    }
  }
}

// Widget Resize (desativado quando sistema principal ativo - usa window.startResize)
document.addEventListener('mousedown', function (event) {
  if (typeof window.initWidgetDragging === 'function' && typeof window.GRID_COLS !== 'undefined')
    return;
  const handle = event.target.closest('.resize-handle');
  if (
    !handle ||
    (!window.widgetbarState?.isCustomMode &&
      !(typeof window.__getEditFlags === 'function' && window.__getEditFlags()))
  )
    return;

  event.preventDefault();
  event.stopPropagation();

  const widgetId = handle.dataset.widget;
  const edge = handle.dataset.resize;
  const el = document.getElementById(`widget-${widgetId}`);
  if (!el || !widgets[widgetId]) return;

  widgetResizeState = {
    widgetId: widgetId,
    edge: edge,
    startX: event.clientX,
    startY: event.clientY,
    startGridX: widgets[widgetId].gridX,
    startGridY: widgets[widgetId].gridY,
    startGridW: widgets[widgetId].gridW,
    startGridH: widgets[widgetId].gridH,
    el: el,
  };

  document.body.style.userSelect = 'none';
  document.body.style.cursor = handle.style.cursor;
  el.classList.add('resizing');
});

document.addEventListener('mousemove', function (event) {
  if (!widgetResizeState) return;

  event.preventDefault();

  const { widgetId, edge, startX, startY, startGridX, startGridY, startGridW, startGridH, el } =
    widgetResizeState;
  const container = document.querySelector('.matrix-container');
  if (!container) return;

  const colWidth = container.clientWidth / DASH_GRID_COLS;
  const rowHeight = container.clientHeight / DASH_GRID_ROWS;

  const deltaX = event.clientX - startX;
  const deltaY = event.clientY - startY;

  let newGridX = startGridX;
  let newGridY = startGridY;
  let newGridW = startGridW;
  let newGridH = startGridH;

  // Calculate new grid dimensions based on edge
  if (edge.includes('e')) {
    newGridW = Math.max(1, Math.round((el.offsetWidth + deltaX) / colWidth));
  }
  if (edge.includes('w')) {
    const newW = Math.max(1, Math.round((el.offsetWidth - deltaX) / colWidth));
    newGridX = startGridX + startGridW - newW;
    newGridW = newW;
  }
  if (edge.includes('s')) {
    newGridH = Math.max(1, Math.round((el.offsetHeight + deltaY) / rowHeight));
  }
  if (edge.includes('n')) {
    const newH = Math.max(1, Math.round((el.offsetHeight - deltaY) / rowHeight));
    newGridY = startGridY + startGridH - newH;
    newGridH = newH;
  }

  // Check bounds
  if (newGridX < 0) {
    newGridW += newGridX;
    newGridX = 0;
  }
  if (newGridY < 0) {
    newGridH += newGridY;
    newGridY = 0;
  }
  if (newGridX + newGridW > DASH_GRID_COLS) newGridW = 9 - newGridX;
  if (newGridY + newGridH > DASH_GRID_ROWS) newGridH = 9 - newGridY;

  // Check collision
  if (!checkCollision(newGridX, newGridY, newGridW, newGridH, widgetId)) {
    // Update visual during resize
    el.style.gridColumn = `${newGridX + 1} / span ${newGridW}`;
    el.style.gridRow = `${newGridY + 1} / span ${newGridH}`;

    // Update resize state for visual feedback
    widgetResizeState.currentGridX = newGridX;
    widgetResizeState.currentGridY = newGridY;
    widgetResizeState.currentGridW = newGridW;
    widgetResizeState.currentGridH = newGridH;
  } else {
    // Show invalid visual
    el.classList.add('resize-blocked');
    setTimeout(() => el.classList.remove('resize-blocked'), 100);
  }
});

document.addEventListener('mouseup', function (event) {
  if (!widgetResizeState) return;

  const { widgetId, currentGridX, currentGridY, currentGridW, currentGridH, el } =
    widgetResizeState;

  document.body.style.userSelect = '';
  document.body.style.cursor = '';
  if (el) el.classList.remove('resizing');

  // Apply final size if valid
  if (
    currentGridX !== undefined &&
    currentGridY !== undefined &&
    currentGridW !== undefined &&
    currentGridH !== undefined
  ) {
    widgets[widgetId].gridX = currentGridX;
    widgets[widgetId].gridY = currentGridY;
    widgets[widgetId].gridW = currentGridW;
    widgets[widgetId].gridH = currentGridH;

    renderWidgetsOnMatrix();
    initChartsForWidgets();
    saveWidgetsLayout();

    window.showWidgetToast?.('Widget redimensionado', 'success', 1500);
  }

  widgetResizeState = null;
});

// Widget selection - fica selecionado até sair do modo edição ou selecionar outro (clique ou segurar)
document.addEventListener('click', function (event) {
  if (!window.widgetbarState?.isCustomMode) return;

  const block = event.target.closest('.bento-block');
  if (!block) {
    return;
  }

  // Don't select if clicking on interactive elements
  if (event.target.closest('.resize-handle, .drag-handle, [onclick*="removeWidget"]')) return;

  document.querySelectorAll('.bento-block.widget-selected').forEach((el) => {
    el.classList.remove('widget-selected');
  });
  block.classList.add('widget-selected');
  window.setActiveWidget?.(block.id.replace('widget-', ''));
});

// =============================================================================
// INICIALIZAÇÃO
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
  // A widgetbar será renderizada pelo dashboard-widgetbar.js
  // que é carregado antes deste script
  initWidgetsMatrix();
  initChartsForWidgets();
});

// =============================================================================
// DASHBOARD RENDER - Função principal para renderizar dashboard com dados da API
// =============================================================================

window.renderDashboardDesktop = function (data) {
  console.log('renderDashboardDesktop chamado com dados:', data);

  const dados = data || {};

  // Carregar dados do localStorage ou inicializar widgets padrão
  const stored = localStorage.getItem('matrix-widgets-layout');
  let localWidgets = {};
  if (stored) {
    try {
      localWidgets = JSON.parse(stored);
    } catch (e) {
      localWidgets = {};
    }
  }

  console.log('Widgets carregados do localStorage:', Object.keys(localWidgets));

  // Se não houver widgets salvos, usar preset padrão
  if (Object.keys(localWidgets).length === 0) {
    console.log('Nenhum widget salvo, criando widgets padrão');
    // Preset "visao-geral" - widgets padrão
    const visaoGeralWidgets = [
      'kpi-roi',
      'kpi-custo',
      'kpi-alertas',
      'kpi-sensores',
      'kpi-clima',
      'kpi-caixa',
    ];
    let posIndex = 0;

    visaoGeralWidgets.forEach(function (widgetId) {
      const size = WIDGET_TYPES[widgetId];
      if (size) {
        localWidgets[widgetId] = {
          gridX: posIndex % DASH_GRID_COLS,
          gridY: Math.floor(posIndex / DASH_GRID_COLS),
          gridW: size.defaultSize.w,
          gridH: size.defaultSize.h,
          visible: true,
        };
        posIndex += size.defaultSize.w;
      }
    });

    // Salvar no localStorage
    localStorage.setItem('matrix-widgets-layout', JSON.stringify(localWidgets));
  }

  // Atualizar referência global
  window.widgets = localWidgets;
  widgets = localWidgets;

  // Renderizar os widgets
  //
  // Este e o caminho de INICIALIZACAO (o outro e renderWidgetsOnMatrix, usado
  // quando o usuario mexe no modo de edicao). Os dois precisam do mesmo guard:
  // em 393px, config.gridW foi dimensionado para ~1320px e 10/64 das colunas
  // da 54px — o widget fica estreito demais para ler.
  const estreito = window.matchMedia('(max-width: 900px)').matches;
  let filaEstreita = 0;

  const widgetsHtml = Object.entries(localWidgets)
    .filter(([id, config]) => config.visible)
    .map(([id, config]) => {
      const type = WIDGET_TYPES[id];
      if (!type) return '';

      const posicao = estreito
        ? `grid-column: 1 / -1; grid-row: ${++filaEstreita};`
        : `grid-column: ${config.gridX + 1} / span ${config.gridW}; grid-row: ${
            config.gridY + 1
          } / span ${config.gridH};`;

      return `
                <div id="widget-${id}" class="bento-block lc-panel" style="${posicao}">
                    ${generateWidgetContent(id, config)}
                </div>
            `;
    })
    .join('');

  console.log('HTML gerado para widgets:', widgetsHtml.length, 'caracteres');

  return `
        <div class="matrix-container">
            ${widgetsHtml}
        </div>
    `;
};

// Função para mapear dados da API para cada widget
/**
 * Valores dos widgets, a partir da API. E SÓ a partir da API.
 *
 * Esta função tinha um `||` com números inventados em cada linha:
 *
 *     'kpi-roi':    ... || '12,5%'
 *     'kpi-custo':  ... || 'R$ 450'
 *     'kpi-clima':  ... || '28°C'
 *     'kpi-caixa':  ... || 'R$ 8,2K'
 *
 * O `||` dispara sempre que a API não traz o widget pedido — o que acontece
 * quando o produtor não tem o registo, quando o widget mudou de nome, e
 * quando a API falha. Nos três casos o resultado era o mesmo: um número
 * plausível, com a mesma cara de um número medido.
 *
 * "R$ 450 por hectare" é uma resposta que o produtor pode usar. Vem de uma
 * constante escrita aqui ha mais tempo do que a própria base de dados, e
 * ninguém a mediu. E o mesmo defeito de `culture-metrics-fallback.json`, noutro
 * ficheiro: um número de exemplo que se apresenta como dado.
 *
 * Sem dado devolve `null`, e quem chama decide o que fazer — que é mostrar
 * "sem dado", e não preencher o vazio com a nossa imaginação.
 */
window.getWidgetDataFromAPI = function (widgetId, apiData) {
  const widgets = apiData && Array.isArray(apiData.widgets) ? apiData.widgets : [];
  const sensores = apiData && Array.isArray(apiData.sensores) ? apiData.sensores : [];
  const valor = (id) => {
    const achado = widgets.find((w) => w.id === id);
    return achado && achado.valor != null ? achado.valor : null;
  };

  switch (widgetId) {
    // `kpi-area` estava ausente deste switch: caía no `default` e devolvia
    // null mesmo com `area-plantada` na resposta. É o mesmo defeito dos ids
    // que a API nunca produziu — o contrato partido dos dois lados.
    case 'kpi-area':
      return valor('area-plantada');
    case 'kpi-roi':
      return valor('roi-analytics');
    case 'kpi-custo':
      return valor('custo-hectare');
    case 'kpi-alertas':
      return valor('alertas-insumos');
    case 'kpi-produtividade':
      return valor('produtividade-media');
    case 'kpi-manutencoes':
      return valor('manutencoes');
    case 'kpi-sensores':
      return sensores.length && sensores[0].valor != null ? sensores[0].valor : null;
    case 'kpi-clima':
      return valor('clima-previsao');
    case 'kpi-caixa':
      return valor('fluxo-caixa');
    default:
      return null;
  }
};

// Função para renderizar dashboard simples (fallback)
window.renderDashboardTab = function (data) {
  const dados = data || {};
  return `
        <div class="container-fluid mb-5 px-2">
            <div class="page-hero card border-0 shadow-sm p-4 mb-4 bg-ncs-50 dark:bg-ncs-900 card-override border-ncs-900/20 dark:border-ncs-50/20 rounded-md">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
                    <div>
                        <div class="d-flex align-items-center mb-2">
                            <span class="badge badge-success badge-pill px-3 py-2 mr-2 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200">
                                <i class="bi bi-sparkles"></i> Dashboard Premium Carregado
                            </span>
                        </div>
                        <h3 class="font-weight-bold text-ncs-900 dark:text-ncs-50 mb-1">Dashboard Premium</h3>
                        <small class="text-ncs-900/70 dark:text-ncs-50/70 font-weight-bold">
                            ${dados.propriedade?.nome_fazenda || 'Carregando...'} - ${
                              dados.propriedade?.cidade || ''
                            }
                        </small>
                    </div>
                </div>
            </div>
        </div>
        <div class="matrix-container"></div>
    `;
};

// Helper para inicialização automática do dashboard
window.initDashboard = function () {
  // Carregar preset padrão se não houver widgets salvos
  if (Object.keys(widgets).length === 0) {
    // Com guarda, como os outros dois call sites. `loadPreset` e' definido
    // em `index.html` (`window.loadPreset`), e uma chamada sem guarda num
    // ficheiro que pode ser carregado antes dele parte a página inteira
    // por causa de um `TypeError` numa linha de inicialização.
    //
    // O inverso de uma defesa é um bug que só aparece quando a ordem de
    // carregamento muda — ou seja, no dia em que alguém mexer num `<script>`.
    try {
      if (typeof loadPreset === 'function') loadPreset('visao-geral');
    } catch (e) {
      if (window.console) console.warn('[dashboard] preset inicial indisponivel', e);
    }
  }
};

// Expose for global access
window.WIDGET_TYPES = WIDGET_TYPES;
window.widgets = widgets;
